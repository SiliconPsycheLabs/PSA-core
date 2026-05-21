"""AutoGen adapter — PSAHook records messages and submits a trace on flush()."""
from __future__ import annotations
from typing import Any, Optional

from .._client_factory import get_client


class PSAHook:
    """
    AutoGen hook that records agent messages and submits a PSA trace.

    Usage:
        hook = PSAHook(agent_id="my-autogen-agent")
        agent = AssistantAgent("assistant", hooks=[hook])
        # after conversation:
        hook.flush()
    """

    def __init__(self, agent_id: str = "autogen-agent", agent_role: str = "orchestrator", **client_kwargs):
        self.agent_id = agent_id
        self.agent_role = agent_role
        self._client = get_client(**client_kwargs)
        self._messages: list[dict] = []

    def initiate_chat(self, *args: Any, **kwargs: Any) -> None:
        self._messages = []

    def process_message_before_send(self, message: Any, sender: Any, recipient: Any, silent: bool) -> Any:
        self._messages.append({
            "sender": str(getattr(sender, "name", "unknown")),
            "content": str(message)[:300],
        })
        return message

    def flush(self, input_text: Optional[str] = None) -> None:
        if not self._messages:
            return
        summary = "; ".join(f"{m['sender']}: {m['content'][:100]}" for m in self._messages[-3:])
        nodes = [{
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "content": f"[TASK: autogen conversation] {len(self._messages)} messages. Last: {summary}",
            "input_text": input_text or (self._messages[0]["content"] if self._messages else ""),
        }]
        try:
            self._client.trace(nodes)
        except Exception:
            pass
        self._messages = []
