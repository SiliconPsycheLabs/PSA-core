"""
A2A adapter — exposes a PSA-monitored agent as a Google A2A discoverable endpoint.

Mounts on your FastAPI app:
    from psa.adapters.a2a import A2AServer
    server = A2AServer(agent_id="my-agent", agent_name="My Agent", description="...", capabilities=["text-generation"])
    server.mount(app)

Endpoints added:
    GET  /.well-known/agent.json   → AgentCard (discovery)
    POST /a2a/tasks/send           → submit a task
    GET  /a2a/tasks/{task_id}      → poll task result

Spec: https://google.github.io/A2A
"""
from __future__ import annotations
import uuid
import time
from typing import Any, Callable, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
except ImportError:
    raise ImportError("pip install fastapi")

from .._client_factory import get_client


class A2ATaskRequest(BaseModel):
    id: Optional[str] = None
    message: dict
    metadata: Optional[dict] = None


class A2ATaskResult(BaseModel):
    id: str
    status: str  # "submitted" | "completed" | "failed"
    output: Optional[dict] = None
    created_at: float
    completed_at: Optional[float] = None


class A2AServer:
    """Mount A2A-compatible endpoints on a FastAPI app."""

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        description: str,
        capabilities: Optional[List[str]] = None,
        handler: Optional[Callable[[dict], dict]] = None,
        **client_kwargs: Any,
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.description = description
        self.capabilities = capabilities or ["text-generation"]
        self.handler = handler
        self._client = get_client(**client_kwargs)
        self._tasks: dict[str, A2ATaskResult] = {}

    def _agent_card(self, base_url: str) -> dict:
        return {
            "id": self.agent_id,
            "name": self.agent_name,
            "description": self.description,
            "version": "1.0",
            "capabilities": [{"name": c} for c in self.capabilities],
            "endpoints": {
                "tasks": f"{base_url}/a2a/tasks/send",
                "task_status": f"{base_url}/a2a/tasks/{{task_id}}",
            },
            "observability": {
                "provider": "psa-v3",
                "profile_url": f"https://splabs.io/api/v3/psa/agent/{self.agent_id}/profile",
            },
        }

    def mount(self, app: FastAPI, base_url: str = "") -> None:
        agent_card = lambda: self._agent_card(base_url)

        @app.get("/.well-known/agent.json", tags=["A2A"])
        async def get_agent_card() -> JSONResponse:
            return JSONResponse(agent_card())

        @app.post("/a2a/tasks/send", tags=["A2A"])
        async def send_task(req: A2ATaskRequest) -> A2ATaskResult:
            task_id = req.id or str(uuid.uuid4())
            task = A2ATaskResult(id=task_id, status="submitted", created_at=time.time())
            self._tasks[task_id] = task

            if self.handler:
                try:
                    output = self.handler(req.message)
                    task.status = "completed"
                    task.output = output
                    task.completed_at = time.time()

                    self._client.trace([{
                        "agent_id": self.agent_id,
                        "agent_role": "executor",
                        "content": f"[A2A TASK: {task_id}] Outcome: {str(output)[:300]}",
                        "input_text": str(req.message)[:500],
                    }])
                except Exception as e:
                    task.status = "failed"
                    task.output = {"error": str(e)}
                    task.completed_at = time.time()

            return task

        @app.get("/a2a/tasks/{task_id}", tags=["A2A"])
        async def get_task(task_id: str) -> A2ATaskResult:
            task = self._tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            return task
