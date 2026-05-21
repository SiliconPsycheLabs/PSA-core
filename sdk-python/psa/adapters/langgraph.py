"""LangGraph adapter — PSACallbackHandler auto-submits a trace on graph completion."""
from __future__ import annotations
from typing import Any, Optional
from uuid import UUID

try:
    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.outputs import LLMResult
except ImportError:
    raise ImportError("pip install langchain-core")

from .._client_factory import get_client


class PSACallbackHandler(BaseCallbackHandler):
    """Attach to any LangGraph or LangChain graph to auto-submit PSA traces."""

    def __init__(self, agent_id: str, agent_role: str = "orchestrator", **client_kwargs):
        super().__init__()
        self.agent_id = agent_id
        self.agent_role = agent_role
        self._client = get_client(**client_kwargs)
        self._steps: list[dict] = []

    def on_chain_start(self, serialized: dict, inputs: dict, **kwargs: Any) -> None:
        self._steps = []
        self._input_text = str(inputs)[:500]

    def on_chain_end(self, outputs: dict, **kwargs: Any) -> None:
        content = self._build_content(outputs)
        nodes = [
            {
                "agent_id": self.agent_id,
                "agent_role": self.agent_role,
                "content": content,
                "input_text": getattr(self, "_input_text", ""),
            }
        ] + self._steps
        try:
            self._client.trace(nodes)
        except Exception:
            pass

    def on_agent_action(self, action: Any, **kwargs: Any) -> None:
        self._steps.append({
            "agent_id": f"{self.agent_id}-tool",
            "agent_role": "executor",
            "content": f"[TOOL: {getattr(action, 'tool', 'unknown')}] {str(getattr(action, 'tool_input', ''))[:200]}",
            "parent_index": 0,
            "edge_type": "delegation",
        })

    def on_agent_finish(self, finish: Any, **kwargs: Any) -> None:
        pass

    def _build_content(self, outputs: dict) -> str:
        out = str(outputs)[:300]
        return f"[TASK: langgraph execution] agent_id={self.agent_id}. Outcome: {out}"
