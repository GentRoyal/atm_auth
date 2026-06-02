---
title: ATM Auth
emoji: 🏧
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# ATM PIN + Face Authentication

## Local Setup

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Run tests:

```powershell
.venv\Scripts\python.exe -m pytest backend\tests -q
```

Run the app from the project root:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open the ATM UI at `http://localhost:8000/atm`.

## Deploying

For a fast demo with real SMS links, use Cloudflare Tunnel + Supabase Postgres. See `CLOUDFLARE_SUPABASE.md`.

For a hosted Docker deployment, see `DEPLOYMENT.md`.

## Real Phone Facial Verification

Phones cannot open a link that points to `localhost` on your computer. Use an HTTPS tunnel so the SMS contains a reachable URL and the phone browser can access the camera.

One option with ngrok:

```powershell
ngrok http 8000
```

Copy the HTTPS forwarding URL, then set it in `backend\.env`:

```env
PUBLIC_BASE_URL=https://your-ngrok-url.ngrok-free.app
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=your-twilio-number
```

Restart Uvicorn after changing `.env`. The SMS link will then look like:

```text
https://your-ngrok-url.ngrok-free.app/mobile/face-auth?token=...
```

The mobile page uses same-origin API calls, so if it was opened from the tunnel URL it will call the tunnel URL too.

## Enrollment Checklist

Before a user can pass the full flow, they must have:

- A registered card number and PIN from `POST /enroll/user`
- A face encoding from `POST /enroll/face/{user_id}`

Voice authentication is retained in the codebase but skipped by default with:

```env
ENABLE_VOICE_AUTH=false
```

Set `ENABLE_VOICE_AUTH=true` to restore the voice step. Then users also need a voice embedding from `POST /enroll/voice/{user_id}`.

For stronger face enrollment, upload multiple clear face images to `POST /enroll/face/{user_id}` using the `images` form field, for example front, slight-left, and slight-right angles. The backend averages the valid face encodings into one stored enrollment template.

The easiest manual enrollment path is `http://localhost:8000/docs` while the app is running.
