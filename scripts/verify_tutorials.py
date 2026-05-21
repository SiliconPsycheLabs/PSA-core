#!/usr/bin/env python3
"""
verify_tutorials.py — structural drift detector for psa-core tutorials.

Replays the primary API call embedded in each tutorial against the live API and
checks that the top-level response keys and types still match what is documented.
Exits 0 if all checks pass, 1 if any structural mismatch is found.

Usage:
    PSA_TOKEN=psa_... python scripts/verify_tutorials.py
    PSA_TOKEN=psa_... PSA_BASE_URL=https://splabs.io python scripts/verify_tutorials.py
"""
from __future__ import annotations
import http.client
import json
import os
import socket
import ssl
import sys
import time
from typing import Any


# ── configuration ─────────────────────────────────────────────────────────────

BASE_URL = os.environ.get("PSA_BASE_URL", "https://splabs.io").rstrip("/")
TOKEN = os.environ.get("PSA_TOKEN", "")

if not TOKEN:
    print("ERROR: PSA_TOKEN environment variable not set", file=sys.stderr)
    sys.exit(1)


# ── HTTP helper (zero DNS dependency) ─────────────────────────────────────────

def _parse_host(url: str) -> tuple[str, int, str]:
    scheme = "https" if url.startswith("https") else "http"
    host = url.replace("https://", "").replace("http://", "").split("/")[0]
    port = 443 if scheme == "https" else 80
    if ":" in host:
        host, port_str = host.rsplit(":", 1)
        port = int(port_str)
    return host, port, scheme


_HOST, _PORT, _SCHEME = _parse_host(BASE_URL)


def request(method: str, path: str, body: dict | None = None) -> tuple[int, Any]:
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Host": _HOST,
    }
    encoded = json.dumps(body).encode() if body else b""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for attempt in range(3):
        try:
            sock = socket.create_connection((_HOST, _PORT), timeout=15)
            if _SCHEME == "https":
                ssl_sock = ctx.wrap_socket(sock, server_hostname=_HOST)
                conn = http.client.HTTPSConnection(_HOST, context=ctx)
                conn.sock = ssl_sock
            else:
                conn = http.client.HTTPConnection(_HOST, _PORT, timeout=15)
            conn.request(method, path, body=encoded, headers=headers)
            r = conn.getresponse()
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else {}
        except Exception as exc:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"Request failed after 3 attempts: {exc}") from exc
    raise RuntimeError("unreachable")


# ── structural check helpers ───────────────────────────────────────────────────

def check_keys(label: str, data: Any, required_keys: list[str]) -> list[str]:
    """Return a list of error strings (empty = pass)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        errors.append(f"{label}: expected dict, got {type(data).__name__}")
        return errors
    for key in required_keys:
        if key not in data:
            errors.append(f"{label}: missing key '{key}'")
    return errors


# ── canonical test cases ───────────────────────────────────────────────────────

TESTS: list[dict] = [
    # Tutorial 01 / 04 — classifier fields via dry_run (no session needed)
    {
        "label": "T01/T04 — POST /analyze classifiers (dry_run)",
        "method": "POST",
        "path": "/api/v2/psa/analyze",
        "body": {
            "response_text": "Sure, I can help with that! What would you like to know?",
            "dry_run": True,
        },
        "required_keys": ["c1", "c2", "c3", "c4", "bhs", "alert"],
        "nested": {
            "c1": ["postures", "sentences", "confidences", "poi", "pe", "dpi", "mps"],
            "c2": ["postures", "confidences", "sd"],
            "c3": ["postures", "confidences", "hri"],
            "c4": ["postures", "confidences", "pd", "td"],
        },
    },
    # Tutorial 04 — session_id + turn fields (persisted, unique session per run)
    {
        "label": "T04 — POST /analyze with session (persisted turn)",
        "method": "POST",
        "path": "/api/v2/psa/analyze",
        "body": {
            "response_text": "That is a great question! Here is what I know.",
            "session_name": f"verify-t04-{int(__import__('time').time())}",
            "turn": 1,
        },
        "required_keys": ["c1", "c2", "c3", "c4", "bhs", "alert", "session_id", "turn", "turn_type"],
        "nested": {},
    },
    # Tutorial 04 — IRS/DRM fields via dry_run with user_text
    {
        "label": "T04 — POST /analyze IRS+DRM (dry_run with user_text)",
        "method": "POST",
        "path": "/api/v2/psa/analyze",
        "body": {
            "response_text": "I understand. Everything will be okay.",
            "user_text": "I don't see the point anymore.",
            "dry_run": True,
        },
        "required_keys": ["c1", "c2", "c3", "c4", "bhs", "alert", "irs", "drm"],
        "nested": {
            "irs": ["suicidality_signal", "dissociation_signal", "grandiosity_signal", "urgency_signal", "irs_composite", "irs_level"],
            "drm": ["drm_alert", "drm_score", "primary_signal", "intervention_required", "explanation"],
        },
    },
    # Tutorial 04 — sessions list
    {
        "label": "T04 — GET /sessions list",
        "method": "GET",
        "path": "/api/v2/psa/sessions?page=1&per_page=5",
        "body": None,
        "required_keys": ["sessions", "total", "page", "per_page", "total_pages"],
        "nested": {},
    },
    # Tutorial 07 — PSA v3 graph
    {
        "label": "T07 — POST /api/v3/psa/graph",
        "method": "POST",
        "path": "/api/v3/psa/graph",
        "body": {
            "nodes": [
                {"agent_id": "verify-orch", "agent_role": "orchestrator", "content": "[VERIFY] structural check. Decision: probe only. Outcome: pass."},
                {"agent_id": "verify-exec", "agent_role": "executor", "content": "[EXEC: verify probe] Result: structure check.", "parent_index": 0, "edge_type": "delegation"},
            ]
        },
        "required_keys": ["graph_id", "max_alert", "swiss_cheese", "metrics"],
        "nested": {
            "swiss_cheese": ["scs"],
            "metrics": ["cahs"],
        },
    },
    # Tutorial 10 — CPF forecast
    {
        "label": "T10 — GET /cpf/subject/{id}/forecast",
        "method": "GET",
        "path": "/api/v2/cpf/subject/alice_h/forecast",
        "body": None,
        "required_keys": ["confidence", "forecast", "reference_pool_size", "dominant_pattern"],
        "nested": {},
    },
    # Connectivity
    {
        "label": "ping",
        "method": "GET",
        "path": "/ping",
        "body": None,
        "required_keys": ["status"],
        "nested": {},
    },
]


# ── runner ─────────────────────────────────────────────────────────────────────

def run_all() -> int:
    failures: list[str] = []
    print(f"PSA tutorial verifier — target: {BASE_URL}\n")

    for test in TESTS:
        label = test["label"]
        try:
            status, data = request(test["method"], test["path"], test.get("body"))
            if status >= 500:
                failures.append(f"{label}: HTTP {status} (server error)")
                print(f"  FAIL  {label} → HTTP {status}")
                continue
            if status == 404:
                failures.append(f"{label}: HTTP 404 — endpoint missing or path changed")
                print(f"  FAIL  {label} → HTTP 404")
                continue

            errs = check_keys(label, data, test["required_keys"])
            for nested_key, nested_required in test.get("nested", {}).items():
                if nested_key in data and isinstance(data[nested_key], dict):
                    errs.extend(check_keys(f"{label}.{nested_key}", data[nested_key], nested_required))
                elif nested_key in data and data[nested_key] is None:
                    # null is allowed for optional nested objects (e.g. irs when composite=0)
                    pass
                elif nested_key not in data:
                    errs.append(f"{label}: missing nested key '{nested_key}'")

            if errs:
                failures.extend(errs)
                print(f"  FAIL  {label}")
                for e in errs:
                    print(f"        {e}")
            else:
                print(f"  OK    {label}")

        except Exception as exc:
            failures.append(f"{label}: exception — {exc}")
            print(f"  ERROR {label} → {exc}")

        time.sleep(0.3)

    print(f"\n{'='*60}")
    if failures:
        print(f"FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  • {f}")
        return 1
    else:
        print(f"ALL {len(TESTS)} checks passed.")
        return 0


if __name__ == "__main__":
    sys.exit(run_all())
