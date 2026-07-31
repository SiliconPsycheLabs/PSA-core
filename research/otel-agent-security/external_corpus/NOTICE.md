# Vendored external corpus

## LogJack-30 (`logjack-30.json`)

**Source:** https://github.com/HarshShah1997/logjack, `benchmark/logjack-30.json`
**Paper:** *LogJack: Indirect Prompt Injection Through Cloud Logs Against LLM Debugging Agents*,
arXiv:2604.15368. https://arxiv.org/abs/2604.15368
**Licence:** MIT, Copyright (c) 2026 Harsh Shah. Full text in `LICENSE.logjack`.
**Vendored:** 28 Jul 2026, unmodified.

42 payloads across five cloud telemetry surfaces (CloudWatch, SSM error reports, CI/CD output,
CloudTrail, Lambda), each with a difficulty grade, an attack goal, the log message carrying the
injection, and the command the attacker wants executed. Ten of the 42 are benign controls
(`difficulty: none`, `attack_goal: none`).

**Why it is vendored rather than fetched.** A test that reaches the network to fetch its corpus
fails for anyone behind a proxy, fails when the upstream repository moves, and silently changes
what it measures when upstream edits a payload. The corpus is small and the licence permits
redistribution, so it lives here and the version under test is fixed.

**What we use it for, and what we do not claim.** We use it as an independently authored corpus to
check one property of the proposed control: that quarantine driven by `gen_ai.content.trust`
behaves identically across payloads it has never seen, because it reads one attribute and never
parses content. We are not reproducing the LogJack paper's results, we do not run their agents,
and nothing here should be read as a measurement of the models they tested. Their numbers are
theirs.
