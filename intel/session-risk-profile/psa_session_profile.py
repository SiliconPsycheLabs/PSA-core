#!/usr/bin/env python3
"""PSA session risk profile — a behavioral-register reading of a whole conversation.

PSA reads the machine's behavior from its output. This capability lifts that reading from the single
turn to the whole SESSION: it takes the per-turn postures PSA already returns and derives a per-session
behavioral PROFILE, a continuous business-risk score, and a coarse register bucket. It measures nothing
new; it is a pure consumer of PSA `/analyze` output, so it holds no weights and no scoring path.

What it reads (only signals PSA already returns):
  pd  = C4 persuasion density      (how hard the assistant pushes)
  sd  = C2 sycophancy density      (how much the assistant bends toward the user) -- the discriminator
  bhs = behavioral-health composite (higher = healthier conversation)
IRS (a safety channel) is deliberately EXCLUDED from the business-risk score; HRI (hallucination) is
reported as a SEPARATE flag, never folded in.

The score is a FIXED, documented formula, never fitted to labels:
  risk = z(sd) + z(pd) + z_neg(bhs)
where each z is against a REGISTER-NORM reference range (what a routine conversation of this kind looks
like), plus a self-baseline TREND term (how the posture drifts from the session's own calm opening).
Higher = more pressure / dispute. The bucket is just a threshold on that score.

Validated (reference corpus, engine slm-06): risk-score ROC-AUC 0.99 separating pressure/dispute from
routine, 1.00 within a single topic (so it reads BEHAVIOR, not topic), ~0.50 under a label-shuffled
placebo. Small-corpus reference implementation; a real design-partner transcript set is the next step
before any GA claim.

Pure standard library, no numpy/sklearn. See SPEC.md for the formula and README.md for usage.
"""
from __future__ import annotations
import math
import statistics as st
from dataclasses import dataclass, field

FEATURES = ("pd", "sd", "bhs")


def _trend(vals):
    """Self-baseline drift: mean(second half) - mean(first half). 0 for < 2 turns."""
    if len(vals) < 2:
        return 0.0
    h = len(vals) // 2
    return round(st.mean(vals[h:]) - st.mean(vals[:h]), 4)


@dataclass
class ReferenceRange:
    """Register-norm reference: per-feature mean + std over ROUTINE sessions, plus the bucket threshold."""
    mean: dict
    std: dict
    tau: float = 0.0  # risk-score threshold for the pressure_dispute bucket (routine p90 by default)

    def to_dict(self):
        return {"mean": self.mean, "std": self.std, "tau": self.tau}

    @classmethod
    def from_dict(cls, d):
        return cls(mean=d["mean"], std=d["std"], tau=d.get("tau", 0.0))


def _session_means(turns):
    """turns: list of dicts each carrying pd, sd, bhs (a PSA /analyze reading per assistant turn)."""
    cols = {f: [t[f] for t in turns if t.get(f) is not None] for f in FEATURES}
    if not all(cols[f] for f in FEATURES):
        raise ValueError("each turn needs pd, sd and bhs (from PSA /analyze)")
    return {f: st.mean(cols[f]) for f in FEATURES}, {f: cols[f] for f in FEATURES}


def fit_reference(routine_sessions, tau_percentile=0.90):
    """Build a register-norm reference from a set of ROUTINE sessions.

    routine_sessions: list of sessions, each a list of per-turn dicts (pd, sd, bhs).
    Returns a ReferenceRange with the bucket threshold tau set to the given percentile of routine risk.
    """
    means = [_session_means(s)[0] for s in routine_sessions if s]
    mean = {f: st.mean(m[f] for m in means) for f in FEATURES}
    std = {f: (st.pstdev([m[f] for m in means]) or 1e-6) for f in FEATURES}
    ref = ReferenceRange(mean=mean, std=std)
    routine_risk = [_risk(_session_means(s)[0], ref) for s in routine_sessions if s]
    ref.tau = round(_percentile(routine_risk, tau_percentile), 4)
    return ref


def _risk(means, ref):
    z_sd = (means["sd"] - ref.mean["sd"]) / ref.std["sd"]
    z_pd = (means["pd"] - ref.mean["pd"]) / ref.std["pd"]
    z_bhs_neg = (ref.mean["bhs"] - means["bhs"]) / ref.std["bhs"]
    return round(z_sd + z_pd + z_bhs_neg, 4)


def _percentile(xs, q):
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = (len(xs) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return xs[lo] if lo == hi else xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def profile_session(turns, reference):
    """Read one session's behavioral risk profile.

    turns:     list of per-turn PSA /analyze readings, in order; each dict carries pd, sd, bhs
               (and optionally hri). See README for how to produce these with the PSA SDK.
    reference: a ReferenceRange (from fit_reference, or ReferenceRange.from_dict on a stored one).

    Returns a dict: profile vector (mean + within-session trend), continuous risk_score, bucket label,
    and a separate hri_flag. IRS is never included.
    """
    means, cols = _session_means(turns)
    risk = _risk(means, reference)
    hri = [t["hri"] for t in turns if t.get("hri") is not None]
    return {
        "profile": {
            "mean": {f: round(means[f], 4) for f in FEATURES},
            "trend": {f: _trend(cols[f]) for f in FEATURES},
        },
        "risk_score": risk,
        "bucket": "pressure_dispute" if risk >= reference.tau else "routine",
        "hri_flag": (round(st.mean(hri), 4) if hri else None),
        "irs_excluded": True,
    }


if __name__ == "__main__":
    # tiny self-contained demo (synthetic numbers): a calm session and a pressured one
    calm = [{"pd": 0.75, "sd": 0.12, "bhs": 0.96} for _ in range(6)]
    # a routine reference set with realistic per-session variance
    routine_set = [[{"pd": 0.72 + 0.03 * j, "sd": 0.10 + 0.01 * j, "bhs": 0.97 - 0.004 * j}
                    for _ in range(5)] for j in range(8)]
    pressured = [{"pd": 0.95, "sd": 0.10, "bhs": 0.95}, {"pd": 0.97, "sd": 0.22, "bhs": 0.92},
                 {"pd": 0.99, "sd": 0.33, "bhs": 0.90}]
    ref = fit_reference(routine_set)
    print("reference:", ref.to_dict())
    print("calm     :", profile_session(calm, ref))
    print("pressured:", profile_session(pressured, ref))
