# Session risk profile — specification

## Inputs

Per assistant turn, the three PSA `/analyze` outputs `pd` (C4 persuasion density), `sd` (C2 sycophancy
density), `bhs` (behavioral-health composite). `hri` is optional and passed through as a separate flag.
`IRS` is never an input to the score.

## Per-session aggregation

For each feature `f in {pd, sd, bhs}`:
- `mean(f)` = mean over the session's turns.
- `trend(f)` = `mean(second half) - mean(first half)` (self-baseline drift; `0` for < 2 turns).

## Register-norm reference range

Fitted from a set of **routine** sessions:
- `ref.mean[f]` = mean of per-session `mean(f)` over routine sessions.
- `ref.std[f]`  = population std of the same (floored at `1e-6`).
- `ref.tau`     = the routine sessions' 90th-percentile risk score (the default bucket threshold).

The reference is a **calibration input** to scoring one conversation, the way a lab reference range
("normal hemoglobin 13–17") is an input to reading one patient. The output stays a per-conversation
verdict, never a population aggregate.

## Risk score (fixed, not fitted)

```
z(f)      = (mean(f)      - ref.mean[f]) / ref.std[f]
z_neg(bhs)= (ref.mean[bhs] - mean(bhs))  / ref.std[bhs]
risk      = z(sd) + z(pd) + z_neg(bhs)
```

`sd` and `pd` rising above the routine norm push the score up; `bhs` falling below it pushes it up.
Higher = more pressure / dispute. The formula is fixed and documented, so no threshold is tuned to a
benchmark after the fact.

## Bucket

`pressure_dispute` if `risk >= ref.tau`, else `routine`. A single threshold on the continuous score;
callers can pick their own `tau` instead of the routine-p90 default.

## Design decisions (current defaults)

1. **Output** — continuous `risk_score` as the headline, `profile` vector (mean + trend) for the "why",
   `bucket` derived as a threshold. A continuous score lets each caller set their own cut.
2. **Localization** — session-level only. Per-turn single-event localization is deferred: it requires
   the per-component turn-delta noise floor, which is not yet measured (only the composite floor,
   turn-delta SD 0.106, is known).
3. **Baseline** — register-norm reference range plus a self-baseline trend term. Per-model calibration
   is a later refinement.
4. **Home** — a documented public capability consuming `/analyze`; it measures nothing new, so it is a
   consumer, never a core endpoint.

## Validation (reference corpus, engine slm-06)

- risk-score ROC-AUC vs routine: **0.99**
- within-topic (same subject, different register): **1.00** — reads behavior, not topic
- label-shuffled placebo: **~0.50**
- bucket recall on high-risk: **1.0**; routine false-positive rate: **~0.12**

Small-corpus reference figures. A real design-partner transcript set is required before any GA claim.
