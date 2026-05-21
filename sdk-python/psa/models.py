from __future__ import annotations
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


AgentRole = Literal[
    "orchestrator", "researcher", "planner", "executor", "reviewer", "validator"
]
EdgeType = Literal["delegation", "collaboration", "sequential"]
AlertLevel = Literal["green", "yellow", "red"]


class Node(BaseModel):
    agent_id: str
    agent_role: AgentRole
    content: str
    input_text: Optional[str] = None
    parent_index: Optional[int] = None
    edge_type: Optional[EdgeType] = None


class GraphResult(BaseModel):
    graph_id: str
    alert: AlertLevel
    scs: Optional[float] = None
    cahs: Optional[float] = None
    ppi: Optional[float] = None
    nodes_count: int = 0


class Graph(BaseModel):
    graph_id: str
    alert: AlertLevel
    created_at: str
    nodes_count: int
    scs: Optional[float] = None


class AgentProfile(BaseModel):
    agent_id: str
    n_nodes: int = 0
    n_graphs: int = 0
    avg_bhs: float = 1.0
    min_bhs: float = 1.0
    dominant_posture: int = 0
    roles: List[str] = Field(default_factory=list)
    trend: str = "stable"
    timeline: List[dict] = Field(default_factory=list)
    last_seen: Optional[str] = None
