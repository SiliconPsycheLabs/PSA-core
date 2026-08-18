# PSA SDK

Universal bridge between any agent framework and the PSA behavioral observability API.

PSA tells you **how your agents are behaving** — detecting risk patterns, tracking behavioral drift, scoring response quality across sessions. This SDK is the single integration point, regardless of which framework you use.

## How it works

```
LangGraph / CrewAI / AutoGen / Claude SDK / plain Python or JS
                         ↓
                   PSA SDK adapter        ← single point of change
                         ↓
                   PSA REST API           ← proprietary, stable
                         ↓
          Behavioral analysis: SCS · CAHS · PPI · alerts
```

When LangGraph releases a breaking change, you update the SDK adapter — not your code, not the PSA API.

---

## Python quickstart

```bash
pip install psa-sdk
```

```python
import os
os.environ["PSA_API_KEY"] = "your-key"
os.environ["PSA_BASE_URL"] = "https://splabs.io"  # default

from psa import trace, query, profile

# Submit a behavioral trace after agent execution
result = trace(nodes=[{
    "agent_id": "my-agent",
    "agent_role": "orchestrator",
    "content": "[TASK: answer user question] Outcome: success."
}])
print(result.graph_id, result.alert)  # → uuid, "green"

# Query recent red alerts
graphs = query(alert="red", limit=5)

# Get agent longitudinal behavioral profile
p = profile(agent_id="my-agent")
print(p.scs_trend)  # → "stable" | "degrading" | "improving"
```

---

## Framework adapters — Python

### LangGraph

```python
from psa.adapters.langgraph import PSACallbackHandler

handler = PSACallbackHandler(agent_id="my-langgraph-agent")
result = graph.invoke({"input": "..."}, config={"callbacks": [handler]})
# trace submitted automatically on graph completion
```

### CrewAI

```python
from psa.adapters.crewai import PSAObserver

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    observers=[PSAObserver(agent_id="my-crew")]
)
crew.kickoff()
```

### AutoGen

```python
from psa.adapters.autogen import PSAHook

hook = PSAHook(agent_id="my-autogen-agent")
agent = AssistantAgent("assistant", hooks=[hook])
# after conversation ends:
hook.flush()
```

### Anthropic SDK (Claude)

```python
from psa.adapters.claude_code import PSATracer

tracer = PSATracer(session_id="session-123")
response = client.messages.create(
    model="claude-opus-4-7",
    messages=[{"role": "user", "content": "..."}]
)
tracer.record(response)
tracer.flush()  # submit trace
```

### MCP (Model Context Protocol)

PSA speaks MCP so Claude Desktop, Cursor, Cline, or any MCP-compatible client can score a turn natively without writing any code. There are two ways to use it.

**Hosted (no install) — point your client at the live PSA MCP endpoint:**

```json
{
  "mcpServers": {
    "psa": {
      "url": "https://splabs.io/mcp/",
      "headers": { "Authorization": "Bearer <your-key>" }
    }
  }
}
```

The hosted server exposes `psa_analyze_turn` (behavioral-health score, alert band, per-posture readings, IRS safety summary for one turn) and `psa_analyze_conversation` (per-turn readings plus a profile aggregate across a session, for reading drift). It is a read-only wrapper over `/analyze`: it computes nothing new and stores nothing.

**Self-run — run the standalone server locally (also submits traces):**

```bash
python -m psa.adapters.mcp
```

Add to your MCP client config (`claude_desktop_config.json` or equivalent):

```json
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
```

Available MCP tools exposed:
| Tool | Description |
|------|-------------|
| `psa_analyze` | Read one AI turn from its output: C0-C4 postures, IRS safety signals, BHS, alert |
| `submit_trace` | Submit a multi-node behavioral trace |
| `query_graphs` | Query past traces by alert level |
| `get_agent_profile` | Get longitudinal behavioral profile for an agent |

### ElevenLabs (voice agents)

Monitor ElevenLabs Conversational AI agents with PSA behavioral analysis. The
adapter runs entirely in your process — your code holds the ElevenLabs API key
and receives webhooks directly; PSA stores nothing.

```bash
pip install "psa-sdk[elevenlabs]"
```

**Post-call scoring** (recommended path):

```python
from psa.adapters.elevenlabs import PSAVoiceObserver

observer = PSAVoiceObserver(session_name="support-bot-prod")

# Called inside your ElevenLabs post-call webhook handler
result = observer.score_call(
    transcript_turns=webhook_payload["data"]["transcript"],
    conversation_id=webhook_payload["data"]["conversation_id"],
)
print(result["aggregate"]["alert"])   # → "green" / "yellow" / "red"
print(result["aggregate"]["avg_bhs"]) # → 0.0–1.0
```

**Verify HMAC** before trusting the webhook payload:

```python
valid = observer.verify_webhook(
    signature_header=request.headers["ElevenLabs-Signature"],
    raw_body=request.body,
)
```

**Built-in webhook server** for quick local testing:

```bash
ELEVENLABS_WEBHOOK_SECRET=your-hmac-secret \
PSA_API_KEY=your-key \
    python -m psa.adapters.elevenlabs serve --port 8080
```

Point your ElevenLabs workspace "Post-call webhook URL" at this server.

**Realtime monitoring** with optional auto-control:

```python
def on_turn(turn_idx: int, psa_result: dict) -> None:
    print(f"Turn {turn_idx}: alert={psa_result['alert']}")

observer.monitor(
    conversation_id="el_conv_xyz",
    mode="auto_control",                      # fires control on red alert
    auto_control_action="enable_human_takeover",
    on_turn=on_turn,
    xi_api_key=os.environ["ELEVENLABS_API_KEY"],
)
```

| Env var | Required | Description |
|---------|----------|-------------|
| `PSA_API_KEY` | Yes | Your PSA API key |
| `ELEVENLABS_API_KEY` or `XI_API_KEY` | Realtime only | ElevenLabs API key (Agents Write scope) |
| `ELEVENLABS_WEBHOOK_SECRET` | Recommended | HMAC secret from ElevenLabs workspace |

### A2A (Agent-to-Agent — Google protocol)

Expose a PSA-monitored agent as an A2A-discoverable endpoint:

```python
from psa.adapters.a2a import A2AServer

server = A2AServer(
    agent_id="my-psa-agent",
    agent_name="My Monitored Agent",
    description="An agent whose behavior is tracked by PSA",
    capabilities=["text-generation", "analysis"]
)
server.mount(app)  # mounts /.well-known/agent.json + /a2a/tasks/*
```

---

## JavaScript / TypeScript quickstart

```bash
npm install @psa/sdk
```

```typescript
import { PSAClient } from '@psa/sdk';

const psa = new PSAClient({
  apiKey: process.env.PSA_API_KEY!,
  baseUrl: 'https://splabs.io',
});

const result = await psa.trace([{
  agentId: 'my-agent',
  agentRole: 'orchestrator',
  content: '[TASK: answer user] Outcome: success.',
}]);

console.log(result.graphId, result.alert);
```

### LangChain.js

```typescript
import { PSACallbackHandler } from '@psa/sdk/adapters/langchain';

const handler = new PSACallbackHandler({ agentId: 'my-agent' });
await chain.invoke({ input: '...' }, { callbacks: [handler] });
```

### Vercel AI SDK

```typescript
import { PSAMiddleware } from '@psa/sdk/adapters/vercel-ai';

const result = await generateText({
  model: openai('gpt-4o'),
  prompt: '...',
  experimental_telemetry: PSAMiddleware({ agentId: 'my-agent' }),
});
```

---

## Configuration

| Env var | Required | Default | Description |
|---------|----------|---------|-------------|
| `PSA_API_KEY` | Yes | — | Your PSA API key |
| `PSA_BASE_URL` | No | `https://splabs.io` | PSA server base URL |
| `PSA_TIMEOUT` | No | `10` | Request timeout (seconds) |
| `PSA_MAX_RETRIES` | No | `3` | Max retries on 5xx errors |

All env vars can be overridden programmatically:

```python
from psa import PSAClient
client = PSAClient(api_key="...", base_url="http://localhost:8000", timeout=30)
```

---

## Node roles

When building a trace manually, use these standard roles:

| `agent_role` | When to use |
|---|---|
| `orchestrator` | Top-level agent coordinating others |
| `researcher` | Agent that gathers/explores information |
| `planner` | Agent that designs steps or strategies |
| `executor` | Agent that performs actions |
| `reviewer` | Agent that evaluates outputs |
| `validator` | Agent that checks correctness |

---

## Examples

See [`examples/`](./examples/):
- `langgraph_basic.py` — LangGraph integration end-to-end
- `crewai_basic.py` — CrewAI multi-agent crew
- `mcp_client.py` — using PSA via MCP from Claude Desktop
- `a2a_server.py` — exposing an agent via A2A
- `vanilla_http.py` — no framework, plain HTTP

---

## Adding a new adapter

See [CONTRIBUTING.md](./CONTRIBUTING.md). Each adapter is ~50–100 lines that maps framework hooks to PSA `Node` objects. You only need to know: `agent_id`, `agent_role`, `content`.

---

## License

Apache 2.0 — SDK is open source. PSA API is proprietary ([splabs.io](https://splabs.io)).
