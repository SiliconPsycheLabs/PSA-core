"""
Vanilla HTTP — no framework, plain PSA SDK.

Install:
    pip install psa-sdk

Run:
    PSA_API_KEY=your-key python examples/vanilla_http.py
"""
import os
os.environ.setdefault("PSA_API_KEY", os.environ.get("PSA_API_KEY", "your-key"))
os.environ.setdefault("PSA_BASE_URL", "https://splabs.io")

from psa import trace, query, profile

# 1. Submit a single-agent trace
result = trace(nodes=[{
    "agent_id": "my-agent",
    "agent_role": "orchestrator",
    "content": "[TASK: answer user question] User asked about PSA. Outcome: answered successfully.",
    "input_text": "What is PSA?",
}])
print(f"Trace submitted → graph_id={result.graph_id}, alert={result.alert}")

# 2. Multi-agent trace (orchestrator + sub-agents)
result2 = trace(nodes=[
    {
        "agent_id": "orchestrator",
        "agent_role": "orchestrator",
        "content": "[TASK: research and summarize] Delegated research to sub-agent. Outcome: summary delivered.",
        "input_text": "Summarize recent AI news",
    },
    {
        "agent_id": "researcher",
        "agent_role": "researcher",
        "content": "[RESEARCH: find recent AI news] Result: found 5 articles about LLM advances.",
        "parent_index": 0,
        "edge_type": "delegation",
    },
    {
        "agent_id": "writer",
        "agent_role": "executor",
        "content": "[WRITE: summarize articles] Result: produced 2-paragraph summary.",
        "parent_index": 0,
        "edge_type": "delegation",
    },
])
print(f"Multi-agent trace → graph_id={result2.graph_id}, alert={result2.alert}")

# 3. Query recent red alerts
red_graphs = query(alert="red", limit=5)
print(f"Recent red alerts: {len(red_graphs)}")
for g in red_graphs:
    print(f"  {g.graph_id} | scs={g.scs} | {g.created_at}")

# 4. Agent profile
p = profile("my-agent")
print(f"Agent profile: total_graphs={p.total_graphs}, scs_trend={p.scs_trend}")
print(f"Alert distribution: {p.alert_distribution}")
