# Session risk profile

PSA reads a machine's behavior from its output, the way a psychiatrist reads a patient: no access to
the model, the weights, or the training data. This capability lifts that reading from the single turn
to the whole **conversation**. It turns the postures PSA already returns into a per-session behavioral
**profile**, a continuous **business-risk score**, and a coarse **register bucket** (`routine` vs
`pressure_dispute`).

It measures nothing new. It is a pure consumer of PSA `/analyze` output, holds no weights and no scoring
path, and stays inside the identity wall: it reads a conversation's **behavioral register**, it does
not route on topic or intent.

## What it reads

Only signals PSA already returns, per assistant turn:

| signal | what it is |
|---|---|
| `pd` | C4 persuasion density — how hard the assistant pushes |
| `sd` | C2 sycophancy density — how much the assistant bends toward the user (**the discriminator**) |
| `bhs` | behavioral-health composite — higher is a healthier conversation |

`IRS` (a safety channel) is deliberately **excluded** from the business-risk score. `HRI`
(hallucination risk) is reported as a **separate flag**, never folded in.

## The score

A fixed, documented formula, never fitted to labels:

```
risk = z(sd) + z(pd) + z_neg(bhs)
```

Each `z` is taken against a **register-norm** reference range (what a routine conversation of this kind
looks like), and the profile also carries a self-baseline **trend** term (how each posture drifts from
the session's own calm opening). Higher score = more pressure / dispute. The bucket is simply a
threshold on the score, so the operator sets their own cut instead of inheriting ours. See
[`SPEC.md`](SPEC.md).

## Validated

On the reference corpus (engine `slm-06`): the risk score separates pressure/dispute from routine at
**ROC-AUC 0.99**, and **1.00 within a single topic** — so it reads behavior, not topic — against
**~0.50** under a label-shuffled placebo. This is a small-corpus reference implementation; a real
design-partner transcript set is the honest next step before a general-availability claim.

## Use

```python
from psa import PSA                      # the psa-core Python SDK (../../sdk-python)
from psa_session_profile import profile_session, fit_reference, ReferenceRange

psa = PSA(api_key="...")

def read_turns(conversation):
    """Score each assistant turn through PSA /analyze -> the pd/sd/bhs this capability consumes."""
    turns = []
    for user_text, assistant_text in conversation:
        r = psa.analyze(response_text=assistant_text, user_text=user_text)
        turns.append({"pd": r.c4.pd, "sd": r.c2.sd, "bhs": r.bhs, "hri": r.hri})
    return turns

# 1) build a register-norm reference once, from a batch of routine conversations
reference = fit_reference([read_turns(c) for c in routine_conversations])

# 2) read any session against it
profile = profile_session(read_turns(a_conversation), reference)
# -> {"profile": {...}, "risk_score": 9.24, "bucket": "pressure_dispute", "hri_flag": None, ...}
```

Persist the reference with `reference.to_dict()` and restore it with `ReferenceRange.from_dict(...)`.
The module is pure standard library (no numpy / sklearn); `python psa_session_profile.py` runs a
self-contained synthetic demo.

## Status

Reference implementation. Output shape, single-event localization (per-turn, not just session-level),
baseline choice (register-norm vs per-model), and packaging are open refinements tracked with the
requesting design partner.
