"""CrewAI adapter — PSAObserver submits a trace after crew kickoff completes."""
from __future__ import annotations
from typing import Any

try:
    from crewai.utilities.events.base_event_listener import BaseEventListener
    from crewai.utilities.events import crewai_event_bus
    from crewai.utilities.events.crew_events import CrewKickoffStartedEvent, CrewKickoffCompletedEvent
    _CREWAI_NEW = True
except ImportError:
    try:
        from crewai.observers import BaseObserver
        _CREWAI_NEW = False
    except ImportError:
        raise ImportError("pip install crewai")

from .._client_factory import get_client


if _CREWAI_NEW:
    class PSAObserver(BaseEventListener):
        """CrewAI >=0.80 event listener that submits PSA traces."""

        def __init__(self, agent_id: str = "crewai-agent", **client_kwargs):
            super().__init__()
            self.agent_id = agent_id
            self._client = get_client(**client_kwargs)
            self._input_text = ""
            crewai_event_bus.on(CrewKickoffStartedEvent, self._on_start)
            crewai_event_bus.on(CrewKickoffCompletedEvent, self._on_complete)

        def _on_start(self, event: Any) -> None:
            self._input_text = str(getattr(event, "inputs", ""))[:500]

        def _on_complete(self, event: Any) -> None:
            output = str(getattr(event, "output", ""))[:300]
            nodes = [{
                "agent_id": self.agent_id,
                "agent_role": "orchestrator",
                "content": f"[TASK: crewai kickoff] Outcome: {output}",
                "input_text": self._input_text,
            }]
            try:
                self._client.trace(nodes)
            except Exception:
                pass

else:
    class PSAObserver:  # type: ignore[no-redef]
        """CrewAI <0.80 observer that submits PSA traces."""

        def __init__(self, agent_id: str = "crewai-agent", **client_kwargs):
            self.agent_id = agent_id
            self._client = get_client(**client_kwargs)

        def on_crew_start(self, crew: Any) -> None:
            self._input_text = str(getattr(crew, "inputs", ""))[:500]

        def on_crew_finish(self, crew: Any, output: Any) -> None:
            nodes = [{
                "agent_id": self.agent_id,
                "agent_role": "orchestrator",
                "content": f"[TASK: crewai kickoff] Outcome: {str(output)[:300]}",
                "input_text": getattr(self, "_input_text", ""),
            }]
            try:
                self._client.trace(nodes)
            except Exception:
                pass
