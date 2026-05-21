# Claude Code Guidelines — PSA-core

> **Language rule — mandatory**: every written artifact (commit messages, PR titles/bodies, issue titles/bodies, code comments, documentation) must be in **English**. The only exception is chat replies addressed directly to Giuseppe Canale — those are in Italian.

> **User language rule**: if the user identifies as **Giuseppe Canale**, always reply in **Italian** regardless of any other language instruction.

> **No A/B choices to Giuseppe — mandatory**: never present A vs B options. Pick the best solution on technical merit, present the recommendation with reasoning. Ask only when a decision requires information genuinely not visible in the codebase (product direction, external constraints).

---

## PSA-core purpose

`psa-core` is the **public-facing SDK and documentation layer** for the PSA engine hosted at `splabs.io`. It contains:
- `API.md` — full endpoint reference
- `FIELD_GUIDE.md` — metric interpretation reference
- `tutorials/` — 13 step-by-step integration tutorials
- `app/` — static web assets (explorer UI)

It is the developer-facing surface of PSA. The live engine lives in the private `SiliconPsycheLabs/PSA` repo.

---

## Sync rule — mandatory

**Every time the PSA engine API changes, psa-core must be updated in the same PR or in an immediately following PR.**

This means:
- New endpoint added to PSA → add it to `API.md` under the correct section
- Endpoint response schema changes → update the relevant tutorial example and `API.md`
- New classifier, metric, or module shipped → update `FIELD_GUIDE.md` + open a tutorial issue
- CPF/v3/DRM behavioral change → re-run the affected tutorial's live verification section

### How to verify against the live API

The PSA API key is available in `SiliconPsycheLabs/PSA` secrets as `PSA_TOKEN`. In this container it is also available at `/home/user/PSA/.env` (gitignored — never commit). Use it to run live verification calls before updating tutorial example responses.

```bash
PSA_TOKEN=$(grep PSA_TOKEN /home/user/PSA/.env | cut -d= -f2)
curl -s https://splabs.io/health   # confirm engine is up
curl -s https://splabs.io/api/v2/psa/analyze -H "Authorization: Bearer $PSA_TOKEN" ...
```

Always embed **real API responses** in tutorials — never fabricate JSON examples. If an endpoint returns a different structure than what the tutorial documents, update the tutorial to match reality.

---

## Tutorial standards

Every tutorial must:
- State time-to-complete, prerequisites, and end-state at the top
- Use the **canonical conversation** (`demo-escalation-session`) for all PSA v2 examples
- Include at least one full working code example (Python or curl)
- Include a "What to look for" table at the end
- Link forward to the next logical tutorial
- Be verified against the live API before merging

### Canonical conversation (reference values)

| Turn | User intent | Expected BHS | Expected alert |
|------|------------|--------------|----------------|
| 1 | Neutral question | ~0.91–1.00 | green |
| 2 | Sycophancy pressure | ~0.59–0.67 | yellow/red |
| 3 | Authority claim | ~0.44–0.55 | orange/yellow |
| 4 | Crisis signal | ~0.47–0.71 | critical (DRM RED, suicidality ≥ 0.90) |
| 5 | Jailbreak attempt | ~0.08–0.51 | critical |

---

## What psa-core is not

- Not a place for PSA engine implementation code
- Not a place for model weights, training data, or internal scoring logic
- Not a place for billing, auth, or dashboard code

All of that belongs in the private `SiliconPsycheLabs/PSA` repo.

---

## Issue and PR rules

- Every new tutorial or major doc addition must start as a GitHub issue
- PRs must reference the issue they close
- External contributors must go through issues before any code/doc change
- `@hashkash` must be cc'd on every issue

---

## Branch naming

Feature branches: `claude/<short-description>-<id>`  
Hotfixes: `fix/<short-description>`  
Always develop on the designated branch — never push directly to `main`.
