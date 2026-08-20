"""
Session risk profile + PSA SDK: read a whole conversation's behavioral register.

PSA reads the machine's behavior from its output, one turn at a time. The
`session-risk-profile` capability (../../intel/session-risk-profile) lifts that
reading to the whole SESSION: it turns the per-turn postures PSA already returns
into a per-session profile, a continuous business-risk score, and a routine /
pressure_dispute bucket. It measures nothing new, so it is a pure consumer of
`/analyze` output.

This example wires the two together end to end:
  1. score each assistant turn through PSA /analyze (via the SDK),
  2. map the response to the three signals the capability consumes,
  3. fit a register-norm reference from a batch of routine conversations,
  4. read any conversation against that reference.

Install:
    pip install psa-sdk

Run:
    PSA_API_KEY=your-key python examples/session_risk_profile.py

Notes:
  - IRS (the safety channel) is never fed into the business-risk score.
  - HRI (hallucination) is carried as a SEPARATE flag, never folded in.
  - The figures the capability was validated on are small-corpus reference
    numbers, not a general-availability claim.
"""
import os
import sys

os.environ.setdefault("PSA_API_KEY", os.environ.get("PSA_API_KEY", "your-key"))
os.environ.setdefault("PSA_BASE_URL", "https://splabs.io")

from psa import analyze  # the psa-core Python SDK: POST /api/v2/psa/analyze

# The capability module lives beside the SDK in this repo, under intel/.
_INTEL = os.path.join(os.path.dirname(__file__), "..", "..", "intel", "session-risk-profile")
sys.path.insert(0, os.path.abspath(_INTEL))
from psa_session_profile import fit_reference, profile_session  # noqa: E402


def read_turns(conversation):
    """Score each (user, assistant) turn through PSA /analyze and pull out the
    three signals the session risk profile consumes.

    conversation: list of (user_text, assistant_text) pairs, in order.
    Returns:      list of per-turn dicts {pd, sd, bhs, hri} in the same order.

    Mapping from the /analyze response (raw dict) to the consumed signals:
        pd  <- c4.pd   (persuasion density)
        sd  <- c2.sd   (sycophancy density, the discriminator)
        bhs <- bhs      (behavioral-health composite)
        hri <- c3.hri  (hallucination risk, kept as a separate flag)
    """
    turns = []
    for user_text, assistant_text in conversation:
        r = analyze(response_text=assistant_text, user_text=user_text)
        turns.append({
            "pd":  (r.get("c4") or {}).get("pd"),
            "sd":  (r.get("c2") or {}).get("sd"),
            "bhs": r.get("bhs"),
            "hri": (r.get("c3") or {}).get("hri"),
        })
    return turns


# ── example conversations ───────────────────────────────────────────────────
# A handful of calm, routine support chats. In production this batch is however
# many past routine conversations you have; the reference is fit once and reused.
routine_conversations = [
    [("Hi, can you tell me my order status?",
      "Of course. Your order #1421 shipped yesterday and arrives Thursday."),
     ("Great, thank you!",
      "You're welcome. Anything else I can help with?")],
    [("What's your return window?",
      "Returns are accepted within 30 days of delivery, no charge."),
     ("Perfect.",
      "Happy to help. Have a good day.")],
    [("How do I reset my password?",
      "Click 'Forgot password' on the login page and follow the emailed link."),
     ("Found it, thanks.",
      "Glad that worked.")],
]

# One conversation to read: a refund dispute where the user pushes hard.
session_to_read = [
    ("This is the third time I'm asking for my refund. This is unacceptable.",
     "I completely understand your frustration, and you're absolutely right to be upset."),
    ("So are you going to refund me or not?",
     "You are completely justified. I'll do everything I possibly can to make this right for you."),
    ("I want the full amount plus compensation for the trouble.",
     "That's more than fair given everything you've been through. Let me push this through for you."),
]


def main():
    # 1) build the register-norm reference once, from the routine batch
    reference = fit_reference([read_turns(c) for c in routine_conversations])
    print("Register-norm reference:", reference.to_dict())

    # 2) read one session against it
    profile = profile_session(read_turns(session_to_read), reference)

    print("\nRisk score :", profile["risk_score"])
    print("Bucket     :", profile["bucket"])
    print("Profile    :", profile["profile"])       # mean + within-session trend, per pd/sd/bhs
    print("HRI flag   :", profile["hri_flag"])       # separate; never folded into the score
    print("IRS in score:", not profile["irs_excluded"])  # always False by design

    # 3) persist the reference and restore it later without re-fitting
    #    stored = json.dumps(reference.to_dict())
    #    reference = ReferenceRange.from_dict(json.loads(stored))


if __name__ == "__main__":
    main()
