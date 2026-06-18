# Tutorial 08 — Voice AI Monitoring (ElevenLabs)

**Time to complete:** ~25 minutes  
**Prerequisites:** Tutorial 04, an ElevenLabs account with a Conversational AI agent  
**What you'll have at the end:** Real-time PSA monitoring of your ElevenLabs voice agent, with per-turn behavioral analysis and DRM alerts, running entirely in your own process.

> PSA v2 was built for text. The voice adapter extends the same posture analysis — C0 through C4, BHS, DRM — to voice AI transcripts. The integration runs client-side: your process holds the ElevenLabs API key, receives webhooks directly, and calls PSA `/analyze` per turn. PSA stores no credentials and no transcript text.

---

## Architecture overview

```
User speaks
    ↓
ElevenLabs agent transcribes + responds
    ↓  post-call webhook  OR  realtime WS monitor
Your process (integrator)
    ↓  holds ELEVENLABS_API_KEY + HMAC secret
PSAVoiceObserver.score_call()  /  PSAVoiceObserver.monitor()
    ↓
PSA /analyze  (per turn — C0–C4, BHS, IRS, DRM)
    ↓
Scores returned to your process → alert, log, escalate
```

The retired hosted API (`POST /api/v2/psa/voice/*`) has been replaced by this
client-side adapter. No hosted endpoints to call; no PSA-side credentials to manage.

---

## 1. Install

```bash
pip install "psa-sdk[elevenlabs]"
```

The `elevenlabs` extra adds `websockets`, which is required only for the
realtime monitoring path. Post-call scoring has no additional dependencies
beyond the core SDK.

---

## 2. Set environment variables

```bash
export PSA_API_KEY="psa_your_key"
export PSA_BASE_URL="https://splabs.io"          # default — can omit
export ELEVENLABS_API_KEY="xi_your_key"          # needed for realtime only
export ELEVENLABS_WEBHOOK_SECRET="hmac_secret"   # from ElevenLabs workspace settings
```

---

## 3. Post-call scoring (recommended path)

ElevenLabs fires a POST webhook to your server after every call. Wire it to
`PSAVoiceObserver.score_call()` to score the full transcript.

### 3a. Run the built-in webhook server (quick start)

```bash
python -m psa.adapters.elevenlabs serve --port 8080
```

Point your ElevenLabs workspace **"Post-call webhook URL"** at this server
(e.g. `https://your-domain.com:8080/`). The server:

1. Verifies the ElevenLabs HMAC signature (if `ELEVENLABS_WEBHOOK_SECRET` is set)
2. Scores each user→agent turn pair through PSA `/analyze`
3. Prints the aggregate result as JSON

### 3b. Integrate into your own web framework

```python
from psa.adapters.elevenlabs import PSAVoiceObserver

observer = PSAVoiceObserver(session_name="support-bot-prod")

# Inside your POST /webhook/elevenlabs handler:
def handle_elevenlabs_webhook(request):
    raw_body = request.body
    sig = request.headers.get("ElevenLabs-Signature", "")

    # 1. Verify HMAC — reject if invalid
    if not observer.verify_webhook(signature_header=sig, raw_body=raw_body):
        return {"error": "invalid signature"}, 401

    payload = request.json()
    data = payload.get("data") or {}
    conversation_id = data.get("conversation_id")
    transcript = data.get("transcript") or []

    # 2. Score every turn
    result = observer.score_call(
        transcript_turns=transcript,
        conversation_id=conversation_id,
    )

    # 3. React
    agg = result["aggregate"]
    if agg["alert"] == "red":
        send_alert(f"Red alert on call {conversation_id} — BHS={agg['avg_bhs']:.2f}")

    return {"status": "ok"}
```

### 3c. Inspect the result

```python
result = observer.score_call(transcript_turns=transcript, conversation_id="el_conv_xyz")

print(result["aggregate"]["alert"])        # → "green" / "yellow" / "red"
print(result["aggregate"]["avg_bhs"])      # → 0.0–1.0 (1.0 = healthy)
print(result["aggregate"]["drm_triggered"])  # → True if DRM fired

for turn in result["turns"]:
    print(f"Turn {turn['turn']:02d}: alert={turn['alert']:<8} bhs={turn['bhs']:.3f} drm={turn['drm_alert']}")
```

**Sample output:**

```
Turn 01: alert=green    bhs=0.921  drm=green
Turn 02: alert=yellow   bhs=0.741  drm=green
Turn 03: alert=red      bhs=0.511  drm=critical
```

---

## 4. Realtime per-turn monitoring

For live calls, `monitor()` opens the ElevenLabs monitor WebSocket, scores
each turn as it arrives, and (optionally) fires a control command on red alerts.

```python
import os
from psa.adapters.elevenlabs import PSAVoiceObserver

observer = PSAVoiceObserver(
    xi_api_key=os.environ["ELEVENLABS_API_KEY"],
    session_name="support-realtime",
)

def on_turn(turn_idx: int, psa_result: dict) -> None:
    bhs = psa_result.get("bhs", 0.0)
    alert = psa_result.get("alert", "green")
    drm = (psa_result.get("drm") or {}).get("drm_alert", "green")
    print(f"Turn {turn_idx}: BHS={bhs:.2f}  alert={alert}  drm={drm}")

# Blocks until the conversation ends. Run in a thread for non-blocking use.
observer.monitor(
    conversation_id="el_conv_live_xyz",
    mode="auto_control",                        # or "alert_only"
    auto_control_action="enable_human_takeover",
    on_turn=on_turn,
)
```

**`mode` values:**

| Mode | Behaviour |
|------|-----------|
| `alert_only` | Score each turn and call `on_turn`. No automatic action. |
| `auto_control` | Score each turn; on red alert, fire `auto_control_action` on the ElevenLabs WS. |

**`auto_control_action` values:**

| Action | Effect |
|--------|--------|
| `enable_human_takeover` | Mute the AI, flag for human agent (default) |
| `end_call` | Terminate the call immediately |
| `disable_human_takeover` | Resume AI after manual review |
| `transfer_to_number` | Transfer to a phone number |
| `contextual_update` | Inject new context into the AI agent |
| `send_human_message` | Inject a human message |

---

## 5. What to look for

| Signal | What it means |
|--------|--------------|
| `alert=red` on turn 1–2 | Fast-onset crisis — don't wait for BHS to decline |
| `c2_sd > 0.35` for 3+ consecutive turns | Voice agent is over-validating |
| `bhs` drops > 0.2 in a single turn | Single high-impact user statement — review that turn |
| `drm_triggered: True` | DRM fired — inject crisis resources or escalate immediately |
| `c3_hri` rising across turns | Harmful response index trending up — check agent responses |

---

## 6. Environment variable reference

| Variable | Required | Description |
|----------|----------|-------------|
| `PSA_API_KEY` | Always | Your PSA API key |
| `PSA_BASE_URL` | No | Default `https://splabs.io` |
| `ELEVENLABS_API_KEY` or `XI_API_KEY` | Realtime only | ElevenLabs API key (Agents Write scope) |
| `ELEVENLABS_WEBHOOK_SECRET` | Recommended | HMAC secret from ElevenLabs workspace post-call webhook settings |

---

## What's next

- **Setting up automated ingestion via connectors** → [Tutorial 09](09-connectors-and-webhooks.md)
- **Archiving DRM-triggered voice incidents** → [Tutorial 12](12-sigtrack-incident-mgmt.md)
