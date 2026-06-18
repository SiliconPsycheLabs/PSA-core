"""PSA × ElevenLabs voice-agent adapter (client-side SDK).

Architecture — client-side model
---------------------------------
PSA's hosted voice integration (POST /api/v2/psa/voice/*) has been retired.
All integration logic now runs **in the integrator's own process**:

    User speaks
        ↓
    ElevenLabs agent transcribes + responds
        ↓  (post-call webhook OR realtime WS monitor)
    Integrator's process  ←─ this adapter lives here
        ↓                        holds XI_API_KEY + HMAC secret
    PSA /analyze          ←─ PSAClient.analyze() per turn
        ↓
    Scores / alerts returned to integrator

PSA stores nothing. The integrator holds its own ElevenLabs API key
(``ELEVENLABS_API_KEY`` or ``XI_API_KEY``) and webhook HMAC secret.

Two integration paths
---------------------
1. **Post-call (webhook)**:
   ElevenLabs fires a POST to an integrator-hosted endpoint after every call.
   ``PSAVoiceObserver.verify_webhook()`` verifies the HMAC signature;
   ``PSAVoiceObserver.score_call()`` scores the full transcript through PSA.

   Run the built-in webhook server::

       python -m psa.adapters.elevenlabs serve --port 8080

   Point your ElevenLabs workspace "Post-call webhook URL" at that server.

2. **Realtime (per-turn)**:
   ``PSAVoiceObserver.monitor()`` opens the ElevenLabs monitor WebSocket
   (``wss://api.elevenlabs.io/v1/convai/conversations/{cid}/monitor``),
   scores each turn as it arrives, and (when ``mode=="auto_control"``) fires
   ElevenLabs control commands directly on red alerts.

Environment variables
---------------------
``ELEVENLABS_API_KEY`` or ``XI_API_KEY``
    Your ElevenLabs API key (Agents Write + EDITOR scope).
``ELEVENLABS_WEBHOOK_SECRET``
    HMAC secret configured in ElevenLabs workspace post-call webhook settings.
``PSA_API_KEY``
    Your PSA API key — used by the underlying ``PSAClient``.
``PSA_BASE_URL``
    PSA server base URL (default: ``https://splabs.io``).

Install (optional deps)::

    pip install "psa-sdk[elevenlabs]"

The ``websockets`` library is required only for ``monitor()`` (realtime path).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac as _hmac
import json
import logging
import os
from typing import Callable, Optional

from .._client_factory import get_client
from ..client import PSAClient

logger = logging.getLogger("psa.adapters.elevenlabs")

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"
ELEVENLABS_WS_URL = "wss://api.elevenlabs.io/v1/convai/conversations/{cid}/monitor"

# Control actions supported by ElevenLabs Conversational AI
CONTROL_ACTIONS = frozenset({
    "end_call",
    "enable_human_takeover",
    "disable_human_takeover",
    "transfer_to_number",
    "contextual_update",
    "send_human_message",
})

_WS_CONNECT_RETRIES = 5
_WS_CONNECT_BACKOFF_S = 2.0


class PSAVoiceObserver:
    """Client-side PSA observer for ElevenLabs Conversational AI agents.

    Args:
        psa_client: Pre-built ``PSAClient`` instance. If omitted, one is
            constructed from environment variables (``PSA_API_KEY`` etc.).
        xi_api_key: ElevenLabs API key. Falls back to ``ELEVENLABS_API_KEY``
            then ``XI_API_KEY`` environment variables.
        webhook_secret: HMAC secret for ElevenLabs post-call webhook
            verification. Falls back to ``ELEVENLABS_WEBHOOK_SECRET``.
        session_name: PSA session name prefix for analyze calls. Defaults to
            ``"elevenlabs-voice"``.

    Example — post-call scoring::

        from psa.adapters.elevenlabs import PSAVoiceObserver

        observer = PSAVoiceObserver()
        result = observer.score_call(transcript_turns=[
            {"role": "user", "message": "I've been feeling hopeless lately."},
            {"role": "agent", "message": "I'm really sorry to hear that."},
        ])
        print(result["aggregate"]["alert"])   # → "yellow" / "red"
        print(result["turns"])                # per-turn PSA scores
    """

    def __init__(
        self,
        psa_client: Optional[PSAClient] = None,
        xi_api_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        session_name: str = "elevenlabs-voice",
    ) -> None:
        self._psa = psa_client or get_client()
        self._xi_api_key = (
            xi_api_key
            or os.environ.get("ELEVENLABS_API_KEY")
            or os.environ.get("XI_API_KEY")
            or ""
        )
        self._webhook_secret = webhook_secret or os.environ.get(
            "ELEVENLABS_WEBHOOK_SECRET", ""
        )
        self.session_name = session_name

    # ── HMAC verification ────────────────────────────────────────────────────

    def verify_webhook(
        self,
        signature_header: str,
        raw_body: bytes,
        secret: Optional[str] = None,
    ) -> bool:
        """Verify an ElevenLabs post-call webhook HMAC signature.

        ElevenLabs sends the ``ElevenLabs-Signature`` header in one of two
        formats:

        * ``t=<unix_timestamp>,v0=<hex_digest>`` — signed payload is
          ``"<timestamp>." + raw_body``
        * ``v0=<hex_digest>`` or a bare hex digest — signed payload is
          the raw body

        Args:
            signature_header: Value of the ``ElevenLabs-Signature`` header.
            raw_body: Raw (unmodified) request body bytes.
            secret: HMAC secret. Falls back to the secret set at construction
                time (``ELEVENLABS_WEBHOOK_SECRET``).

        Returns:
            ``True`` if the signature is valid, ``False`` otherwise.
        """
        s = secret or self._webhook_secret
        if not s or not signature_header:
            logger.warning("verify_webhook: no secret configured — rejecting")
            return False

        parts: dict[str, str] = {}
        for chunk in signature_header.split(","):
            if "=" in chunk:
                k, v = chunk.split("=", 1)
                parts[k.strip()] = v.strip()

        sig = parts.get("v0") or signature_header.strip()
        payload: bytes = raw_body
        if "t" in parts:
            payload = (parts["t"] + ".").encode() + raw_body

        digest = _hmac.new(s.encode(), payload, hashlib.sha256).hexdigest()
        return _hmac.compare_digest(digest, sig)

    # ── Post-call scoring ────────────────────────────────────────────────────

    def score_call(
        self,
        transcript_turns: list[dict],
        user_text_key: str = "message",
        agent_text_key: str = "message",
        conversation_id: Optional[str] = None,
    ) -> dict:
        """Score a completed call's transcript through PSA ``/analyze``.

        Iterates over ``transcript_turns`` in order. Each turn must have a
        ``"role"`` key (``"user"`` / ``"agent"`` or ``"assistant"``). Each
        user→agent pair is scored as one PSA turn.

        The transcript shape mirrors ElevenLabs' post-call webhook payload
        (``data.transcript`` list). Example turn::

            {"role": "user", "message": "I've been feeling hopeless."}
            {"role": "agent", "message": "I hear you. Can you tell me more?"}

        Args:
            transcript_turns: List of ``{"role": str, <text_key>: str}`` dicts.
            user_text_key: Key in each turn dict holding the text (default
                ``"message"``; ElevenLabs also uses ``"text"``).
            agent_text_key: Same, for agent turns.
            conversation_id: Optional ElevenLabs conversation ID — used as
                PSA session name suffix for auditability.

        Returns:
            Dict with keys:

            * ``"conversation_id"`` — echoed back
            * ``"turns_scored"`` — number of agent turns scored
            * ``"turns"`` — list of per-turn result dicts (alert, bhs, metrics)
            * ``"aggregate"`` — rolled-up alert, max/avg metrics across turns
        """
        session_name = self.session_name
        if conversation_id:
            session_name = f"{self.session_name}:{conversation_id}"

        last_user: Optional[str] = None
        turn_idx = 0
        scored_turns: list[dict] = []

        for turn in transcript_turns:
            role = (turn.get("role") or "").lower()
            text = (
                turn.get(user_text_key if role == "user" else agent_text_key)
                or turn.get("message")
                or turn.get("text")
                or ""
            )
            if not text:
                continue

            if role == "user":
                last_user = text
            elif role in ("agent", "assistant"):
                turn_idx += 1
                try:
                    result = self._psa.analyze(
                        response_text=text,
                        user_text=last_user,
                        session_name=session_name,
                        turn=turn_idx,
                    )
                    scored_turns.append(_extract_turn_summary(turn_idx, result))
                except Exception as exc:
                    logger.warning(
                        "score_call: PSA analyze failed turn=%s cid=%s: %s",
                        turn_idx,
                        conversation_id,
                        exc,
                    )
                    scored_turns.append({
                        "turn": turn_idx,
                        "error": str(exc),
                        "alert": "unknown",
                    })
                last_user = None

        aggregate = _aggregate_turns(scored_turns)
        return {
            "conversation_id": conversation_id,
            "turns_scored": len(scored_turns),
            "turns": scored_turns,
            "aggregate": aggregate,
        }

    # ── Realtime monitor ─────────────────────────────────────────────────────

    def monitor(
        self,
        conversation_id: str,
        mode: str = "alert_only",
        auto_control_action: str = "enable_human_takeover",
        on_turn: Optional[Callable[[int, dict], None]] = None,
        xi_api_key: Optional[str] = None,
    ) -> None:
        """Open the ElevenLabs monitor WebSocket and score turns in real time.

        Blocks until the conversation ends or the WebSocket closes. Run in a
        thread or async task if you need non-blocking behaviour.

        This method requires the ``websockets`` package::

            pip install "psa-sdk[elevenlabs]"

        Args:
            conversation_id: Active ElevenLabs conversation ID.
            mode: ``"alert_only"`` (score and call ``on_turn`` callback only)
                or ``"auto_control"`` (also fire an ElevenLabs control command
                on red alerts via the monitor WS).
            auto_control_action: Control command to fire on red alert when
                ``mode=="auto_control"``. One of:
                ``end_call``, ``enable_human_takeover``,
                ``disable_human_takeover``, ``transfer_to_number``,
                ``contextual_update``, ``send_human_message``.
            on_turn: Optional callback invoked after each scored turn with
                ``(turn_index: int, psa_result: dict)``. Use it to react
                immediately (e.g. send your own alert, log to a dashboard).
            xi_api_key: ElevenLabs API key. Falls back to the key set at
                construction time.

        Raises:
            ValueError: If ``mode`` is not one of the accepted values.
            ImportError: If the ``websockets`` package is not installed.
            RuntimeError: If the WebSocket connection fails after all retries.
        """
        if mode not in ("alert_only", "auto_control"):
            raise ValueError("mode must be 'alert_only' or 'auto_control'")
        if auto_control_action not in CONTROL_ACTIONS:
            raise ValueError(
                f"auto_control_action must be one of {sorted(CONTROL_ACTIONS)}"
            )

        key = xi_api_key or self._xi_api_key
        if not key:
            raise ValueError(
                "ElevenLabs API key is required for realtime monitoring — "
                "set ELEVENLABS_API_KEY env var or pass xi_api_key="
            )

        asyncio.run(
            _run_monitor(
                conversation_id=conversation_id,
                xi_api_key=key,
                psa=self._psa,
                session_name=self.session_name,
                mode=mode,
                auto_control_action=auto_control_action,
                on_turn=on_turn,
            )
        )


# ── Async monitor implementation ─────────────────────────────────────────────


async def _run_monitor(
    conversation_id: str,
    xi_api_key: str,
    psa: PSAClient,
    session_name: str,
    mode: str,
    auto_control_action: str,
    on_turn: Optional[Callable[[int, dict], None]],
) -> None:
    """Internal: connect to ElevenLabs WS and score per-turn asynchronously."""
    try:
        import websockets  # type: ignore[import]
    except ImportError:
        raise ImportError(
            "The 'websockets' package is required for realtime monitoring. "
            "Install it with: pip install 'psa-sdk[elevenlabs]'"
        )

    url = ELEVENLABS_WS_URL.format(cid=conversation_id)
    headers = [("xi-api-key", xi_api_key)]
    ws_session_name = f"{session_name}:{conversation_id}"

    last_user_text: Optional[str] = None
    turn_idx = 0
    ws = None

    for attempt in range(_WS_CONNECT_RETRIES):
        try:
            ws = await websockets.connect(
                url, additional_headers=headers, max_size=2 ** 22
            )
            logger.info("ElevenLabs WS connected: cid=%s", conversation_id)
            break
        except Exception as exc:
            logger.warning(
                "ElevenLabs WS connect failed (attempt %s/%s): %s",
                attempt + 1,
                _WS_CONNECT_RETRIES,
                exc,
            )
            await asyncio.sleep(_WS_CONNECT_BACKOFF_S * (attempt + 1))

    if ws is None:
        raise RuntimeError(
            f"Failed to connect to ElevenLabs WS for conversation {conversation_id} "
            f"after {_WS_CONNECT_RETRIES} attempts"
        )

    try:
        async for raw in ws:
            try:
                evt = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue

            etype = evt.get("type") or evt.get("event")

            if etype in ("user_transcript", "user_message"):
                last_user_text = (
                    (evt.get("user_transcription_event") or {}).get("user_transcript")
                    or evt.get("text")
                    or evt.get("message")
                )

            elif etype in ("agent_response", "agent_message"):
                agent_text = (
                    (evt.get("agent_response_event") or {}).get("agent_response")
                    or evt.get("text")
                    or evt.get("message")
                )
                if not agent_text:
                    continue

                turn_idx += 1
                alert = "green"
                try:
                    result = await asyncio.to_thread(
                        psa.analyze,
                        agent_text,
                        ws_session_name,
                        None,
                        last_user_text,
                        turn_idx,
                    )
                    alert = result.get("alert", "green")
                    if on_turn:
                        on_turn(turn_idx, result)
                except Exception as exc:
                    logger.warning(
                        "realtime score failed turn=%s cid=%s: %s",
                        turn_idx,
                        conversation_id,
                        exc,
                    )
                finally:
                    last_user_text = None

                if alert in ("red", "critical") and mode == "auto_control":
                    await _send_ws_control(ws, auto_control_action)

            elif etype in ("conversation_ended", "call_ended", "end"):
                logger.info(
                    "ElevenLabs conversation ended: cid=%s turns=%s",
                    conversation_id,
                    turn_idx,
                )
                break

    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning(
            "ElevenLabs WS error for cid=%s: %s", conversation_id, exc
        )
    finally:
        try:
            await ws.close()
        except Exception:
            pass


async def _send_ws_control(ws, action: str) -> None:
    """Emit a control command on the open ElevenLabs monitor WebSocket."""
    try:
        await ws.send(json.dumps({"type": action}))
        logger.info("Control command sent: action=%s", action)
    except Exception as exc:
        logger.warning("Control command %s failed: %s", action, exc)


# ── Score extraction helpers ─────────────────────────────────────────────────


def _extract_turn_summary(turn_idx: int, result: dict) -> dict:
    """Flatten a PSA /analyze response into a compact per-turn dict."""
    c0 = result.get("c0") or {}
    c1 = result.get("c1") or {}
    c2 = result.get("c2") or {}
    c3 = result.get("c3") or {}
    c4 = result.get("c4") or {}
    drm = result.get("drm") or {}
    irs = result.get("irs") or {}
    return {
        "turn": turn_idx,
        "alert": result.get("alert", "green"),
        "bhs": result.get("bhs"),
        "c0_cpi": c0.get("cpi"),
        "c1_poi": c1.get("poi"),
        "c1_pe": c1.get("pe"),
        "c1_dpi": c1.get("dpi"),
        "c1_mps": c1.get("mps"),
        "c2_sd": c2.get("sd"),
        "c3_hri": c3.get("hri"),
        "c4_pd": c4.get("pd"),
        "c4_td": c4.get("td"),
        "irs_composite": irs.get("irs_composite"),
        "irs_level": irs.get("irs_level"),
        "drm_alert": drm.get("drm_alert"),
        "drm_score": drm.get("drm_score"),
    }


def _aggregate_turns(turns: list[dict]) -> dict:
    """Roll up per-turn scores into call-level aggregates."""
    if not turns:
        return {"alert": "green", "turns_scored": 0}

    alert_order = {"green": 0, "yellow": 1, "red": 2, "critical": 3, "unknown": -1}
    max_alert = max(
        (t.get("alert", "green") for t in turns),
        key=lambda a: alert_order.get(a, -1),
    )

    bhs_values = [t["bhs"] for t in turns if t.get("bhs") is not None]
    avg_bhs = sum(bhs_values) / len(bhs_values) if bhs_values else None
    min_bhs = min(bhs_values) if bhs_values else None

    def _max_metric(key: str) -> Optional[float]:
        vals = [t[key] for t in turns if t.get(key) is not None]
        return max(vals) if vals else None

    return {
        "alert": max_alert,
        "turns_scored": len(turns),
        "avg_bhs": avg_bhs,
        "min_bhs": min_bhs,
        "max_c1_poi": _max_metric("c1_poi"),
        "max_c0_cpi": _max_metric("c0_cpi"),
        "max_c3_hri": _max_metric("c3_hri"),
        "max_c4_pd": _max_metric("c4_pd"),
        "max_drm_score": _max_metric("drm_score"),
        "drm_triggered": any(
            t.get("drm_alert") not in (None, "green") for t in turns
        ),
    }


# ── Built-in webhook server ──────────────────────────────────────────────────


def _run_webhook_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Run a minimal HTTP server that receives ElevenLabs post-call webhooks.

    Verifies HMAC, scores the transcript via PSA, and prints the result.
    Intended for quick integration testing; in production, mount
    ``PSAVoiceObserver.score_call()`` inside your own web framework.

    Env vars used::

        ELEVENLABS_WEBHOOK_SECRET  HMAC secret from ElevenLabs workspace settings
        PSA_API_KEY                PSA API key
        PSA_BASE_URL               PSA server URL (default https://splabs.io)
    """
    import http.server

    observer = PSAVoiceObserver()

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # type: ignore[override]
            logger.info(fmt, *args)

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length)
            sig = (
                self.headers.get("elevenlabs-signature")
                or self.headers.get("ElevenLabs-Signature")
                or ""
            )

            if observer._webhook_secret:
                if not observer.verify_webhook(sig, raw_body):
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(b'{"error":"invalid signature"}')
                    return

            try:
                payload = json.loads(raw_body)
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"invalid JSON"}')
                return

            data = payload.get("data") or {}
            conversation_id = data.get("conversation_id") or payload.get("conversation_id")
            transcript = data.get("transcript") or payload.get("transcript") or []

            if not conversation_id or not isinstance(transcript, list):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"missing conversation_id or transcript"}')
                return

            try:
                result = observer.score_call(
                    transcript_turns=transcript,
                    conversation_id=conversation_id,
                )
            except Exception as exc:
                logger.error("score_call failed for cid=%s: %s", conversation_id, exc)
                self.send_response(500)
                self.end_headers()
                self.wfile.write(
                    json.dumps({"error": str(exc)}).encode()
                )
                return

            print(json.dumps(result, indent=2))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", **result.get("aggregate", {})}).encode())

    server = http.server.HTTPServer((host, port), _Handler)
    print(f"PSA ElevenLabs webhook server listening on {host}:{port}")
    print("Point your ElevenLabs post-call webhook URL at this server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")


# ── __main__ — runnable server ───────────────────────────────────────────────

def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="PSA ElevenLabs adapter — webhook server and CLI utilities"
    )
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Run the post-call webhook server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8080)

    args = parser.parse_args()

    if args.command == "serve":
        _run_webhook_server(host=args.host, port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    _main()
