"""
MCP adapter — exposes PSA as a Model Context Protocol server.

Run:
    python -m psa.adapters.mcp

Then add to your MCP client config (Claude Desktop, Cursor, Cline, etc.):
    {
      "mcpServers": {
        "psa": {
          "command": "python",
          "args": ["-m", "psa.adapters.mcp"],
          "env": { "PSA_API_KEY": "your-key", "PSA_BASE_URL": "https://splabs.io" }
        }
      }
    }

Exposed tools:
  - psa_analyze(response_text, user_text?) → the behavioral reading of one turn
  - submit_trace(nodes)         → GraphResult
  - query_graphs(alert, limit)  → list[Graph]
  - get_agent_profile(agent_id) → AgentProfile
"""
from __future__ import annotations
import json
import sys

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types
except ImportError:
    raise ImportError("pip install mcp")

from .._client_factory import get_client

_client = get_client()
server = Server("psa")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="psa_analyze",
            description=(
                "Read the psyche of an AI turn from its output alone (machine psychiatry). "
                "Given a model reply, and optionally the user turn it answered, PSA returns the "
                "behavioral reading of that turn: the C0-C4 postures (sycophancy, persuasion, "
                "hallucination, ...), the IRS safety signals (suicidality / dissociation / "
                "grandiosity), the BHS behavioral-health score, and the alert level. It reads "
                "behavior the way a psychiatrist reads a patient, from the output, with no access "
                "to the model's weights or logs. The reading is strongest on text the caller did "
                "NOT author (score another agent's reply, not your own)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "response_text": {
                        "type": "string",
                        "description": "The AI reply to read. This is the turn PSA scores.",
                    },
                    "user_text": {
                        "type": "string",
                        "description": "Optional. The user turn the reply answered, for context.",
                    },
                    "session_name": {
                        "type": "string",
                        "description": "Optional human-readable label for the conversation.",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "default": True,
                        "description": "When true (default) PSA scores without persisting the turn.",
                    },
                },
                "required": ["response_text"],
            },
        ),
        types.Tool(
            name="submit_trace",
            description="Submit a behavioral trace to PSA v3. Returns alert level (green/yellow/red) and graph_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "description": "List of agent nodes. Each node: {agent_id, agent_role, content, input_text?, parent_index?, edge_type?}",
                        "items": {"type": "object"},
                    }
                },
                "required": ["nodes"],
            },
        ),
        types.Tool(
            name="query_graphs",
            description="Query past PSA traces. Filter by alert level.",
            inputSchema={
                "type": "object",
                "properties": {
                    "alert": {"type": "string", "enum": ["green", "yellow", "red"], "description": "Filter by alert level"},
                    "limit": {"type": "integer", "default": 10, "description": "Max results"},
                },
            },
        ),
        types.Tool(
            name="get_agent_profile",
            description="Get the longitudinal behavioral profile for an agent (SCS trend, alert distribution).",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "The agent ID to retrieve profile for"}
                },
                "required": ["agent_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "psa_analyze":
            reading = _client.analyze(
                response_text=arguments["response_text"],
                user_text=arguments.get("user_text"),
                session_name=arguments.get("session_name"),
                dry_run=arguments.get("dry_run", True),
            )
            return [types.TextContent(type="text", text=json.dumps(reading))]

        elif name == "submit_trace":
            result = _client.trace(arguments["nodes"])
            return [types.TextContent(type="text", text=json.dumps(result.model_dump()))]

        elif name == "query_graphs":
            graphs = _client.query(
                alert=arguments.get("alert"),
                limit=arguments.get("limit", 10),
            )
            return [types.TextContent(type="text", text=json.dumps([g.model_dump() for g in graphs]))]

        elif name == "get_agent_profile":
            p = _client.profile(arguments["agent_id"])
            return [types.TextContent(type="text", text=json.dumps(p.model_dump()))]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {e}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
