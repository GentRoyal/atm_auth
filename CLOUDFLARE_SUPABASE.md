# Cloudflare Tunnel + Supabase Setup

This is the recommended demo setup when you want the app running locally but the SMS face-auth link to use HTTPS.

## What Stays Local

- FastAPI backend
- ATM page
- Mobile face page
- Voice and face processing

## What Moves to Supabase

- Users
- Accounts
- Sessions
- Auth logs
- Transactions
- Enrolled voice and face binary data

## 1. Configure Supabase

Open Supabase SQL Editor and run:

```sql
-- Paste the full contents of database/schema.sql here
```

Then copy the **Session pooler** connection string from Supabase **Connect**.

Use this format in `backend/.env`:

```env
DATABASE_PROVIDER=supabase
SUPABASE_DATABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?ssl=true
```

If you use the transaction pooler instead, use:

```env
DATABASE_PROVIDER=supabase
SUPABASE_DATABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?ssl=true&statement_cache_size=0
```

## 2. Start the Backend

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

Local ATM:

```text
http://localhost:8001/atm
```

## 3. Start a Cloudflare Quick Tunnel

Quick tunnels are free and do not need a domain, but the URL is temporary.

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --protocol http2 --url http://127.0.0.1:8001
```

Copy the generated URL:

```text
https://something.trycloudflare.com
```

Set it in `backend/.env`:

```env
PUBLIC_BASE_URL=https://something.trycloudflare.com
```

Restart the backend after changing `.env`.

Important: old SMS links break when the quick tunnel URL changes. Start a new ATM auth session after every tunnel restart.

## 4. Twilio

Keep Twilio credentials in `backend/.env`:

```env
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=your_twilio_number
ENABLE_VOICE_AUTH=false
```

## 5. Stable Cloudflare Tunnel

For a stable URL, you need a domain connected to Cloudflare. Then create a named tunnel and route a hostname such as:

```text
atm.yourdomain.com
```

Set:

```env
PUBLIC_BASE_URL=https://atm.yourdomain.com
```

With a named tunnel, SMS links stay stable. With a quick tunnel, SMS links are temporary.
