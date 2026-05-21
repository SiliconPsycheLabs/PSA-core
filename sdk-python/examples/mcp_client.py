"""
MCP + PSA — how to use PSA as an MCP server from any MCP client.

This file shows:
  1. How to configure Claude Desktop / Cursor / Cline to use PSA as MCP tool
  2. How to manually test the MCP server from Python

=== STEP 1: Install ===
    pip install psa-sdk[mcp]

=== STEP 2: Start MCP server ===
    PSA_API_KEY=your-key PSA_BASE_URL=https://splabs.io python -m psa.adapters.mcp

=== STEP 3: Add to Claude Desktop config ===
    File: ~/Library/Application Support/Claude/claude_desktop_config.json (macOS)
          %APPDATA%\Claude\claude_desktop_config.json (Windows)

    {
      "mcpServers": {
        "psa": {
          "command": "python",
          "args": ["-m", "psa.adapters.mcp"],
          "env": {
            "PSA_API_KEY": "your-key",
            "PSA_BASE_URL": "https://splabs.io"
          }
        }
      }
    }

=== STEP 4: Available tools in Claude Desktop ===
    - submit_trace   → send a behavioral trace to PSA
    - query_graphs   → query past traces by alert level
    - get_agent_profile → get longitudinal profile for an agent

=== Manual test from Python (no MCP client needed) ===
"""
import os
os.environ.setdefault("PSA_API_KEY", os.environ.get("PSA_API_KEY", "your-key"))
os.environ.setdefault("PSA_BASE_URL", "https://splabs.io")

from psa import trace, query, profile

# submit_trace equivalent
result = trace(nodes=[{
    "agent_id": "mcp-test-agent",
    "agent_role": "orchestrator",
    "content": "[TASK: MCP test] Testing PSA SDK from examples/mcp_client.py. Outcome: success.",
    "input_text": "Test MCP integration",
}])
print(f"submit_trace → graph_id={result.graph_id}, alert={result.alert}")

# query_graphs equivalent
graphs = query(alert="green", limit=3)
print(f"query_graphs → {len(graphs)} recent green traces")

# get_agent_profile equivalent
p = profile("mcp-test-agent")
print(f"get_agent_profile → total_graphs={p.total_graphs}, scs_trend={p.scs_trend}")
