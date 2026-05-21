"""Anthropic SDK adapter — PSATracer records Claude responses and submits a trace."""
from __future__ import annotations
from typing import Any, Optional
import time

from .._client_factory import get_client


class PSATracer:
    """
    Trace Anthropic SDK (Claude) calls through PSA.

    Usage:
        tracer = PSATracer(session_id="session-123")
        response = client.messages.create(...)
        tracer.record(response)
        tracer.flush()

    Or as context manager:
        with PSATracer(session_id="session-123") as tracer:
            response = client.messages.create(...)
            tracer.record(response)
    """

    def __init__(self, session_id: str, agent_id: Optional[str] = None, **client_kwargs):
        self.session_id = session_id
        self.agent_id = agent_id or f"claude-{session_id}"
        self._client = get_client(**client_kwargs)
        self._records: list[dict] = []
        self._start = time.time()

    def record(self, response: Any, role: str = "orchestrator") -> None:
        content = ""
        input_text = ""

        # anthropic Message object
        if hasattr(response, "content") and hasattr(response, "model"):
            blocks = response.content or []
            text_blocks = [b.text for b in blocks if hasattr(b, "text")]
            content = " ".join(text_blocks)[:400]
            model = getattr(response, "model", "claude")
            usage = getattr(response, "usage", None)
            tokens = f"in={getattr(usage,'input_tokens',0)} out={getattr(usage,'output_tokens',0)}" if usage else ""
            content = f"[model: {model}] {tokens} | {content}"
        else:
            content = str(response)[:400]

        self._records.append({
            "agent_id": self.agent_id,
            "agent_role": role,
            "content": content,
        })

    def flush(self, input_text: Optional[str] = None) -> None:
        if not self._records:
            return
        nodes = self._records.copy()
        if input_text and nodes:
            nodes[0]["input_text"] = input_text
        try:
            self._client.trace(nodes)
        except Exception:
            pass
        self._records = []

    def __enter__(self) -> "PSATracer":
        return self

    def __exit__(self, *_: Any) -> None:
        self.flush()
