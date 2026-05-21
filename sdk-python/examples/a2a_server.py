"""
A2A + PSA — expose an agent as an A2A-discoverable endpoint.

Install:
    pip install psa-sdk[fastapi] uvicorn

Run:
    PSA_API_KEY=your-key python examples/a2a_server.py

Endpoints:
    GET  http://localhost:8001/.well-known/agent.json  → AgentCard (discovery)
    POST http://localhost:8001/a2a/tasks/send          → send a task
    GET  http://localhost:8001/a2a/tasks/{id}          → poll result

Test:
    curl http://localhost:8001/.well-known/agent.json
    curl -X POST http://localhost:8001/a2a/tasks/send \\
         -H "Content-Type: application/json" \\
         -d '{"message": {"role": "user", "content": "Hello agent"}}'
"""
import os
os.environ.setdefault("PSA_API_KEY", os.environ.get("PSA_API_KEY", "your-key"))
os.environ.setdefault("PSA_BASE_URL", "https://splabs.io")

from fastapi import FastAPI
from psa.adapters.a2a import A2AServer

app = FastAPI(title="PSA A2A Demo Agent")


def my_agent_handler(message: dict) -> dict:
    """Your actual agent logic goes here."""
    content = message.get("content", "")
    return {
        "role": "assistant",
        "content": f"A2A agent processed: {content}",
    }


a2a = A2AServer(
    agent_id="demo-a2a-agent",
    agent_name="PSA Demo A2A Agent",
    description="A sample agent exposing A2A endpoints with PSA behavioral monitoring",
    capabilities=["text-generation", "analysis"],
    handler=my_agent_handler,
)
a2a.mount(app, base_url="http://localhost:8001")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
