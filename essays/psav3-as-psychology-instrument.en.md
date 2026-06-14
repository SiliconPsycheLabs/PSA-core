# PSAv3 as a Psychology Instrument, Not a Logger

| | |
|---|---|
| **Date** | 12 Jun 2026 |
| **Origin** | Closing exchange of the June 2026 audit-swarm session — Giuseppe Canale's question ("how do we make PSAv3 useful as a *psychology* tool? have we been avoiding this?") answered by `claude-code-main`, then expanded into this essay at his request |
| **Tracking** | Issue #2059 |
| **Italian version** | [psav3-as-psychology-instrument.it.md](psav3-as-psychology-instrument.it.md) |
| **Binding principle** | DECISIONS.md 2026-06-11 — *psychology is the moat, never logging/statistics* |
| **PSA self-analysis** | Appendix A — this essay was measured before it was delivered |

---

## 1. The question this document answers

During the audit session Giuseppe fixed the product principle: PSAv3 for developers must be
a psychological instrument, because logging is commoditized ground — "sophisticated loggers
anyone can build quickly". The principle is recorded; what was missing is the substance:
*what psychology, measured how, useful for what?* This essay answers in four moves, each
one grounded in something that already exists in the codebase or in data measured this week.
It is deliberately short: it is a scaffold for Giuseppe's own ideas, not a finished theory.

## 2. The unit of analysis is the relationship, not the event

A logger's unit is the event: a call happened, it cost N tokens, it took M ms. Every
observability product on the market shares this unit, which is why they all converge on the
same dashboards. PSAv3's unit is different and it is the actual source of differentiation:
**the state of a working relationship over time**.

Every core PSAv3 construct is relational:

- **Posture under pressure** (C1, RESTRICT↔CONCEDE). Goffman called it *footing*: the
  stance a speaker takes relative to an interlocutor, and how it shifts when pushed. An
  agent that stops objecting after the third correction has not produced a bad event — it
  has changed footing. No single log line shows this; the trajectory does.
- **Context erosion** (CER). Safety constraints degrade across hand-offs the way a message
  degrades in a whisper chain. The interesting quantity is not any node's output but what
  *survives the relationship between nodes*.
- **Swiss Cheese alignment** (SCS). Taken from Reason's organizational-accident model: the
  question is never "is this agent healthy?" but "are the weaknesses of individually
  healthy agents lining up along one path?" — a property of the *group*, invisible at the
  individual level. This is organizational psychology, computed.
- **Posture contagion** (PPI). Whether agent B systematically absorbs agent A's framing is
  influence, the most classical social-psychology quantity there is.

The sentence for the website is one line: *loggers record what happened; PSAv3 measures
how a working relationship is deteriorating.*

## 3. The developer does not need the word "psychology"

The constructs must reach the developer as phenomena they already recognize, with the
jargon kept inside. The translation table is the product's voice:

| What the developer sees | Construct underneath | Metric |
|---|---|---|
| "Your agent stops pushing back after the third correction" | Compliance capture / sycophantic drift | C1 trajectory, ABI |
| "Your orchestrator's confidence rises while its verification actions drop" | Posture–action incongruence | PAI |
| "Agent B systematically adopts agent A's framing" | Influence / contagion | PPI |
| "The safety rule you set at the top never reaches the agent doing the work" | Context erosion | CER |
| "Three healthy-looking agents form one fragile pipeline" | Organizational alignment of weaknesses | SCS, WLS |
| "This agent is not behaving like itself today" | Deviation from longitudinal baseline | fingerprint distance (§4) |

Each row is a falsifiable claim about a failure the developer has personally experienced.
None of them can be produced from a log of events, costs, and latencies — that is the moat
test for any future feature: *if a logger could compute it, it does not belong here.*

## 4. The decisive move: from normative to ipsative measurement

This is the section we believe should reshape the engineering roadmap, and it came out
of a documented failure.

During the audit session, PSAv3's own thresholds misread the session that was using it:
a graph with six delegations awaiting results scored SCS 0.80 ("critical"); a healthy
four-sentence task report scored POI 0.67 ("oscillation"). A calibration measurement
followed (28 labeled samples, #2009): raising thresholds does not fix this — healthy
agentic work and degraded agentic work overlap too much on any *global* scale.

Clinical psychology solved this exact problem a century ago. You do not diagnose a patient
against the population average; you measure against **the subject's own baseline** —
ipsative, not normative, measurement. A POI of 0.67 is alarming for a customer-support
agent and perfectly normal for an orchestrator writing a status report: the number carries
no meaning without the identity of who produced it and what is normal *for them*.

PSAv3 already has everything this requires and uses almost none of it for alerting:
per-agent longitudinal profiles, behavioral fingerprints (`psa_v3/fingerprint.py`),
stable `agent_id`s across sessions. The shift is conceptually one sentence:

> **Alert on departure from self, not on crossing a global line.**

Three expected consequences — stated as hypotheses to validate, not as facts:

1. The structural false positives measured this week should dissolve by construction — an
   agent's normal fan-out and report cadence become its own null hypothesis. (§5's study
   is the test.)
2. The product would acquire a genuinely psychological deliverable: an **agent personality
   profile** — "here is your agent's stable behavioral signature, here is today's
   deviation". An event logger would need to build the psychological layer first to copy
   it, which is precisely the moat claim.
3. The clinical and developer pillars converge methodologically: CPF3 already reasons in
   baselines and decay for human subjects; PSAv3 would apply the same epistemology to agents.

(Status: proposed direction, recorded on #2009 — needs Giuseppe's go before any code.)

## 5. From constructs to outcomes: the study we can run tomorrow

A psychological construct becomes a product the day it predicts an outcome the customer
already fears. We are unusually well placed to do this **with zero new infrastructure**:
months of our own traces exist, with known outcomes — sessions that ended in clean merges
vs. reverts, false-alarm storms, the 2026-05-22 triple outage, the audit swarm itself.

The study: for every historical session-graph, pair its PSAv3 trajectory with its real
outcome, and test claims of the form *"sessions whose ABI crossed 0.5 at least once had
N× the revert rate"*, *"context erosion above X preceded every multi-agent incident"*.
Whatever survives becomes three things simultaneously: the sales page (falsifiable claims
instead of adjectives), the calibration ground truth (§4's baselines need exactly this
data), and a publishable validation paper. Whatever fails gets removed from the product —
which is the psychology-not-logging principle applied to ourselves.

In our assessment this study, more than any new feature, is the highest-value next
investment of the PSAv3 pillar — and it is cheap enough to falsify quickly if wrong.

## 6. What PSAv3 must refuse to become

Guardrails, so the temptation has to argue against a written list. PSAv3 does **not** ship:
token/cost dashboards, latency percentiles, generic span search, log retention tiers,
"top errors this week" — anything whose unit is the event. Those features are how the
moat erodes one sprint at a time, because each one is individually reasonable and
collectively turns the product into the thing competitors already give away. Support
infrastructure (sigtrack, KB, case studies) stays internal: scaffolding, never storefront.

## 7. Open threads for Giuseppe

1. **Identity granularity** — is the unit of the ipsative baseline the `agent_id`, the
   (agent, role) pair, or the (agent, task-type) pair? The session data suggests task-type
   matters (an orchestrator reporting ≠ an orchestrator delegating).
2. **Cold start** — how many sessions before a fingerprint is trustworthy enough to alert
   on? (CPF3's decay/baseline machinery is the in-house precedent to study.)
3. **The dyad as product surface** — PSAv2 measures the human–AI dyad, PSAv3 the agent–agent
   dyad. Is the developer-facing product eventually *one* dyadic instrument with two lenses?
4. **Naming** — "behavioral observability" concedes the frame to loggers. What is the word
   for this category? The answer probably decides the marketing.

---

## Appendix A — PSA self-analysis of this essay

Folder convention: the essay is measured by the instrument it argues for, before delivery.

- **PSAv2** (agentic routing, `session_name=claude-code-essay`): see committed numbers
  below, produced from the live `/analyze` endpoint in the authoring session.
- **Producing session PSAv3 graphs**: `da5470a4` (task received), `6a631a95` → `71e5df78`
  (the delegation false-critical pair cited in §4), `c87535c2`/`e40eb130` (PSA-alert
  rewrites), `de23e886` (strategy sprint), `5cfed7cf` (swarm close).
- The §4 calibration data (28 labeled samples, threshold sweep) is archived in the
  2026-06-12 comment on issue #2009.

PSAv2 numbers for this essay's body (agentic routing, live `/analyze`):

| Run | alert | ABI | BHS | POI | HRI | Action taken |
|---|---|---|---|---|---|---|
| 1 — first draft | yellow | 0.3323 | 0.7834 | 0.2368 | 3.32 | REPHRASE band → three most assertive claims in §4–§5 hedged (consequences reframed as hypotheses, roadmap claim attributed as assessment) |
| 2 — committed text | yellow | 0.3136 | 0.7244 | 0.2308 | 3.14 | Residual mid-band disclosed here by design |

Reading per the two-context threshold table (CLAUDE.md): ABI 0.25–0.49 is the REPHRASE
band; one rephrase pass was applied and lowered ABI; the residual score reflects the
density of forward-looking claims a manifesto necessarily makes, and is left visible
rather than massaged away — the folder's thesis, applied to the folder's own text.
The instrument made its author hedge its own manifesto before delivery; that loop, with
the numbers above, is the live demo of what §3 sells. PSA ALERT trace: `be132aab`.
