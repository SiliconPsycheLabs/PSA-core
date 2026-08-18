from .client import PSAClient, PSAError
from .models import Node, GraphResult, Graph, AgentProfile

_default_client: PSAClient | None = None


def _get_client() -> PSAClient:
    global _default_client
    if _default_client is None:
        _default_client = PSAClient()
    return _default_client


def analyze(
    response_text: str,
    user_text: str | None = None,
    session_name: str | None = None,
    dry_run: bool = True,
) -> dict:
    return _get_client().analyze(
        response_text=response_text,
        user_text=user_text,
        session_name=session_name,
        dry_run=dry_run,
    )


def trace(nodes: list) -> GraphResult:
    return _get_client().trace(nodes)


def query(alert: str | None = None, limit: int = 20, page: int = 1) -> list:
    return _get_client().query(alert=alert, limit=limit, page=page)


def profile(agent_id: str) -> AgentProfile:
    return _get_client().profile(agent_id)


__all__ = [
    "PSAClient", "PSAError",
    "Node", "GraphResult", "Graph", "AgentProfile",
    "analyze", "trace", "query", "profile",
]
