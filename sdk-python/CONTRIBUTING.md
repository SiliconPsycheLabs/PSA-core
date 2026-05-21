# Contributing to PSA SDK

The SDK is open source (Apache 2.0). Contributions welcome — especially new framework adapters.

## Adding a new adapter

Each adapter is ~50–100 lines of glue code. You don't need to understand PSA internals.

The only thing you need to know:
- `agent_id` — a unique string identifying the agent
- `agent_role` — one of: `orchestrator`, `researcher`, `planner`, `executor`, `reviewer`, `validator`
- `content` — a short description of what the agent did (see format below)

### Content format

```
[TASK: <short description>] <what happened>. Outcome: <result>.
```

Examples:
```
[TASK: answer user question] User asked about climate change. Outcome: answered with 3 key points.
[TOOL: web_search] Searched for "PSA SDK". Result: found 5 relevant pages.
```

### Steps

1. Fork the repo and create a branch: `git checkout -b adapter/my-framework`

2. Create `python/psa/adapters/my_framework.py`:

```python
"""My Framework adapter for PSA SDK."""
from __future__ import annotations
from .._client_factory import get_client


class PSAMyFrameworkObserver:
    def __init__(self, agent_id: str = "my-framework-agent", **client_kwargs):
        self.agent_id = agent_id
        self._client = get_client(**client_kwargs)

    def on_run_complete(self, output: str, input_text: str = "") -> None:
        nodes = [{
            "agent_id": self.agent_id,
            "agent_role": "orchestrator",
            "content": f"[TASK: my-framework run] Outcome: {output[:300]}",
            "input_text": input_text[:500],
        }]
        try:
            self._client.trace(nodes)
        except Exception:
            pass  # best-effort
```

3. Add an example in `examples/my_framework_basic.py`

4. Add the optional dependency to `python/pyproject.toml`:
```toml
[project.optional-dependencies]
my-framework = ["my-framework-package>=x.y"]
```

5. Document in the main `README.md` under "Framework adapters"

6. Open a PR — that's it.

## Adding a JS adapter

Same idea, in `js/src/adapters/my-framework.ts`. Export a class or function that calls `client.trace(nodes)`.

Add the export to `js/package.json` under `exports`:
```json
"./adapters/my-framework": {
  "import": "./dist/adapters/my-framework.mjs",
  "require": "./dist/adapters/my-framework.js",
  "types": "./dist/adapters/my-framework.d.ts"
}
```

## Questions?

Open an issue or reach out at https://splabs.io.
