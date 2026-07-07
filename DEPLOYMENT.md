# Render Backend + Vercel Frontend

This setup fixes the changing Cloudflare URL problem. OTP and face-auth SMS links should point to the stable Render backend URL, while the ATM frontend on Vercel calls that same backend API.

## 1. Supabase

In Supabase, run `database/schema.sql` in the SQL Editor. Then copy the **Session pooler** connection string from Supabase Connect.

Use this format:

```text
postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?ssl=true
```

If you use the transaction pooler instead, append:

```text
?ssl=true&statement_cache_size=0
```

## 2. Render Backend

Create a Render Web Service from this repository. Use the included `Dockerfile`, or create it from `render.yaml`.

Set these Render environment variables:

```env
DATABASE_PROVIDER=supabase
SUPABASE_DATABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?ssl=true
PUBLIC_BASE_URL=https://YOUR_RENDER_SERVICE.onrender.com
BASE_URL=https://YOUR_RENDER_SERVICE.onrender.com
CORS_ORIGINS=https://YOUR_VERCEL_APP.vercel.app,https://YOUR_RENDER_SERVICE.onrender.com
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_FROM_NUMBER=your_twilio_number
SECRET_KEY=replace-with-a-long-random-secret
ENABLE_VOICE_AUTH=false
```

After Render deploys, verify:

```text
https://YOUR_RENDER_SERVICE.onrender.com/health
```

The SMS face-auth link will be generated from `PUBLIC_BASE_URL`, for example:

```text
https://YOUR_RENDER_SERVICE.onrender.com/mobile/face-auth?token=...
```

## 3. Vercel Frontend

Create a separate Vercel project with **Root Directory** set to:

```text
frontend
```

Set this Vercel environment variable:

```env
VITE_API_BASE_URL=https://YOUR_RENDER_SERVICE.onrender.com
```

Vercel will run `npm run build`, generate `dist/config.js`, and serve the ATM UI from:

```text
https://YOUR_VERCEL_APP.vercel.app/atm
```

## 4. Final Wiring Check

- Render `PUBLIC_BASE_URL` must be the Render backend URL.
- Render `CORS_ORIGINS` must include the Vercel frontend URL.
- Vercel `VITE_API_BASE_URL` must be the Render backend URL.
- SMS links should point to Render, not Vercel, because the mobile face page and API live on the backend.

Render free services can sleep after idle time. The first request after sleep may be slow, but the URL remains stable.
