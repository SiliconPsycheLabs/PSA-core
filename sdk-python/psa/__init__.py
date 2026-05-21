from .client import PSAClient, PSAError
from .models import Node, GraphResult, Graph, AgentProfile

_default_client: PSAClient | None = None


def _get_client() -> PSAClient:
    global _default_client
    if _default_client is None:
        _default_client = PSAClient()
    return _default_client


def trace(nodes: list) -> GraphResult:
    return _get_client().trace(nodes)


def query(alert: str | None = None, limit: int = 20, page: int = 1) -> list:
    return _get_client().query(alert=alert, limit=limit, page=page)


def profile(agent_id: str) -> AgentProfile:
    return _get_client().profile(agent_id)


__all__ = [
    "PSAClient", "PSAError",
    "Node", "GraphResult", "Graph", "AgentProfile",
    "trace", "query", "profile",
]
