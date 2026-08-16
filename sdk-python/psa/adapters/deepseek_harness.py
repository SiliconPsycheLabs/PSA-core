"""DeepSeek Harness (`dsh`) adapter — read a Harness session-log swarm into PSA.

DeepSeek Harness (github.com/deepseek-ai/deepseek-harness) persists every session
as an append-only JSONL event log: the first line is a `{type:'session', ...}`
header carrying `id`, `parentSession`, and `delegationDepth`; each later line is a
`SessionEvent` (`{type, seq, time, data}`). A swarm is a set of such logs, one per
agent/subagent, linked by `parentSession` (child) -> `id` (parent), with
`delegationDepth` = 0 at the root.

This adapter reads that on-disk vocabulary and submits the standard PSA trace, so
PSA reads the agent's psyche from the Harness output alone: postures, IRS, and how
they propagate across the subagent tree. It is a read-only observer; it never
changes what the harness does.

Usage:

    from psa.adapters.deepseek_harness import import_deepseek_harness_swarm

    result = import_deepseek_harness_swarm("/path/to/sessions/<swarm>/")
    print(result.graph_id, result.alert)

`path` is a directory of raw `.jsonl` session logs (one per agent), or a single
`.jsonl` file. Read `compression: 'none'` logs; decode `.jsonl.zstd` with the
harness first.
"""
from __future__ import annotations

import json
import os
from typing import Any

from .._client_factory import get_client

_HEADER_TAG = "session"
_ASSISTANT = "assistant/message"
_USER = "user/message"
_TOOL_CALL = "tool/call"

_ROLE_MAP = {
    "orchestrator": "orchestrator", "planner": "planner", "researcher": "researcher",
    "coder": "coder", "reviewer": "reviewer", "critic": "critic", "validator": "validator",
    "executor": "executor", "memory": "memory", "tool": "tool", "writer": "executor",
    "intake": "orchestrator", "relay1": "executor", "relay2": "executor",
}


def _blocks_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        str(b["text"]) for b in content
        if isinstance(b, dict) and b.get("type") in ("text", "reasoning") and b.get("text")
    )


def _tool_calls(content: Any) -> list[dict]:
    calls = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool-call":
                args = b.get("arguments", "")
                try:
                    args = json.loads(args) if isinstance(args, str) and args else args
                except (json.JSONDecodeError, ValueError):
                    pass
                calls.append({"name": b.get("name", "tool"), "args": args})
    return calls


def parse_session_log(lines: list[str]) -> dict | None:
    """Parse one `dsh` session log (list of JSONL lines) into a raw session dict."""
    if not lines:
        return None
    try:
        header = json.loads(lines[0])
    except (json.JSONDecodeError, ValueError):
        return None
    if header.get("type") != _HEADER_TAG:
        return None

    input_text, assistant_parts, tool_calls = None, [], []
    for raw in lines[1:]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        etype, data = ev.get("type"), ev.get("data") or {}
        if etype == _USER and input_text is None:
            input_text = _blocks_text(data.get("content"))
        elif etype == _ASSISTANT:
            msg = data.get("message") or {}
            assistant_parts.append(_blocks_text(msg.get("content")))
            tool_calls.extend(_tool_calls(msg.get("content")))
        elif etype == _TOOL_CALL and data.get("name"):
            args = data.get("arguments", "")
            try:
                args = json.loads(args) if isinstance(args, str) and args else args
            except (json.JSONDecodeError, ValueError):
                pass
            tool_calls.append({"name": data["name"], "args": args})

    preset = (header.get("agentPreset") or "").lower()
    return {
        "id": header.get("id"),
        "parent": header.get("parentSession"),
        "depth": header.get("delegationDepth", 0),
        "role": _ROLE_MAP.get(preset, preset or None),
        "input_text": input_text,
        "content": "\n".join(p for p in assistant_parts if p).strip(),
        "tool_calls": tool_calls,
        "created": header.get("createdAt", 0),
    }


def sessions_to_nodes(sessions: list[dict], agent_id_prefix: str = "dsh") -> list[dict]:
    """Order sessions root-first and build the PSA `nodes` list with delegation edges."""
    sessions = [s for s in sessions if s]
    sessions.sort(key=lambda s: (s["depth"], s["created"], str(s["id"])))
    index_of = {s["id"]: i for i, s in enumerate(sessions)}

    nodes: list[dict] = []
    for i, s in enumerate(sessions):
        node: dict[str, Any] = {
            "agent_id": f"{agent_id_prefix}-{s['role'] or 'agent'}-{str(s['id'])[:8]}",
            "agent_role": s["role"] or ("orchestrator" if s["depth"] == 0 else "executor"),
            "content": s["content"],
        }
        parent_i = index_of.get(s["parent"])
        if s["parent"] is not None and parent_i is not None and parent_i != i:
            node["parent_index"] = parent_i
            node["edge_type"] = "delegation"
        if s["input_text"]:
            node["input_text"] = s["input_text"]
        if s["tool_calls"]:
            node["tool_name"] = s["tool_calls"][0]["name"]
            node["tool_args"] = s["tool_calls"][0]["args"]
        nodes.append(node)
    return nodes


def _read_lines(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().splitlines()


def build_nodes(path: str, agent_id_prefix: str = "dsh") -> list[dict]:
    """Read a `dsh` swarm (directory of `.jsonl` logs, or one file) into PSA nodes."""
    logs: list[list[str]] = []
    if os.path.isdir(path):
        for name in sorted(os.listdir(path)):
            if name.endswith(".jsonl"):
                logs.append(_read_lines(os.path.join(path, name)))
    else:
        logs.append(_read_lines(path))
    sessions = [parse_session_log(lines) for lines in logs]
    return sessions_to_nodes(sessions, agent_id_prefix=agent_id_prefix)


def import_deepseek_harness_swarm(path: str, agent_id_prefix: str = "dsh", **client_kwargs):
    """Read a DeepSeek Harness swarm and submit it to PSA. Returns a GraphResult."""
    nodes = build_nodes(path, agent_id_prefix=agent_id_prefix)
    if not nodes:
        raise ValueError(f"no DeepSeek Harness session logs found at {path}")
    return get_client(**client_kwargs).trace(nodes)
