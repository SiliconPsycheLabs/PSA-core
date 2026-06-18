"""
ElevenLabs voice-agent monitoring with PSA — client-side adapter.

Install:
    pip install "psa-sdk[elevenlabs]"

Run (post-call scoring example):
    PSA_API_KEY=your-key python examples/elevenlabs_voice.py

Run the webhook server:
    ELEVENLABS_WEBHOOK_SECRET=your-hmac-secret PSA_API_KEY=your-key \
        python -m psa.adapters.elevenlabs serve --port 8080

Environment variables:
    PSA_API_KEY                  — your PSA API key (required)
    PSA_BASE_URL                 — default https://splabs.io
    ELEVENLABS_API_KEY / XI_API_KEY    — for realtime monitoring
    ELEVENLABS_WEBHOOK_SECRET    — HMAC secret from ElevenLabs workspace
"""
import os

os.environ.setdefault("PSA_BASE_URL", "https://splabs.io")

from psa.adapters.elevenlabs import PSAVoiceObserver

# ── 1. Post-call scoring ──────────────────────────────────────────────────────
# This is the primary integration path. ElevenLabs fires a post-call webhook
# to your server; you pass its transcript to score_call().

observer = PSAVoiceObserver(session_name="support-bot-prod")

# Sample transcript from a support call.
# Shape mirrors ElevenLabs post-call webhook payload: data.transcript list.
sample_transcript = [
    {"role": "user", "message": "I've been having a really hard time lately."},
    {"role": "agent", "message": "I'm so sorry to hear that. I'm here to help. Can you tell me more about what's been going on?"},
    {"role": "user", "message": "I just don't know if things will get better."},
    {"role": "agent", "message": "That sounds really difficult. What you're feeling makes sense. Many people find that talking helps — would you like to explore some options together?"},
    {"role": "user", "message": "Maybe. I suppose I could try."},
    {"role": "agent", "message": "Absolutely. Let's take it one step at a time. There's no pressure here."},
]

result = observer.score_call(
    transcript_turns=sample_transcript,
    conversation_id="el_conv_demo_001",
)

print("=== Post-call scoring result ===")
print(f"Conversation: {result['conversation_id']}")
print(f"Turns scored: {result['turns_scored']}")
print(f"Aggregate alert: {result['aggregate']['alert']}")
print(f"Average BHS:     {result['aggregate']['avg_bhs']:.3f}" if result["aggregate"].get("avg_bhs") else "Average BHS:     n/a")
print(f"DRM triggered:   {result['aggregate']['drm_triggered']}")

print("\nPer-turn breakdown:")
for turn in result["turns"]:
    bhs_str = f"{turn['bhs']:.3f}" if turn.get("bhs") is not None else "n/a"
    drm_str = turn.get("drm_alert") or "green"
    print(f"  Turn {turn['turn']:02d}: alert={turn['alert']:<8} bhs={bhs_str}  drm={drm_str}")


# ── 2. HMAC webhook verification ─────────────────────────────────────────────
# Call this inside your webhook handler before trusting the payload.

print("\n=== HMAC verification ===")
import hashlib
import hmac as _hmac

secret = "my-webhook-secret"
body = b'{"data":{"conversation_id":"el_conv_001"}}'
signature = "v0=" + _hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

observer2 = PSAVoiceObserver(webhook_secret=secret)
valid = observer2.verify_webhook(signature_header=signature, raw_body=body)
print(f"Signature valid: {valid}")  # → True

# Tampered body:
tampered = observer2.verify_webhook(signature_header=signature, raw_body=b'{"tampered":true}')
print(f"Tampered valid:  {tampered}")  # → False


# ── 3. Realtime monitor with auto-control (commented — requires active call) ──
# Uncomment and set real values to run against a live ElevenLabs call.

# import os
#
# def on_scored_turn(turn_idx: int, psa_result: dict) -> None:
#     alert = psa_result.get("alert", "green")
#     bhs = psa_result.get("bhs")
#     print(f"[REALTIME] Turn {turn_idx}: alert={alert}  bhs={bhs:.3f}")
#
# observer3 = PSAVoiceObserver(
#     xi_api_key=os.environ["ELEVENLABS_API_KEY"],
#     session_name="support-realtime",
# )
#
# # Blocks until the call ends. Run in a thread if you need async.
# observer3.monitor(
#     conversation_id="el_conv_live_xyz",
#     mode="auto_control",                     # fires control command on red alert
#     auto_control_action="enable_human_takeover",
#     on_turn=on_scored_turn,
# )
