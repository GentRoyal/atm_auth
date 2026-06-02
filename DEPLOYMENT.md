# Free Deployment Options

## Recommended: Hugging Face Spaces Docker + Free Postgres

The full local app can use heavy biometric dependencies (`torch`, `speechbrain`, `face_recognition`, `dlib`). Free Docker builders may run out of memory with that stack, so the included `Dockerfile` uses `backend/requirements.deploy.txt`, a lighter deployment stack:

- Voice falls back to MFCC embeddings through `librosa`.
- Face falls back to OpenCV-based encoding.
- Local development can still use `backend/requirements.txt` for the heavier models.

Use Supabase Postgres, then set the app environment variables in the Space settings.

### Steps

1. Push this repository to GitHub.
2. Create a new Hugging Face Space.
3. Choose `Docker` as the Space SDK.
4. Connect GitHub to the Space by mirroring your GitHub repo into the Space repo.

   A Hugging Face Space is itself a git repository. The easiest GitHub-based setup is the included GitHub Actions workflow:

   - In Hugging Face, create a token with write access.
   - In GitHub, open your repo settings and add these repository secrets:
     - `HF_TOKEN`: your Hugging Face token
     - `HF_SPACE_REPO`: `your-hf-username/your-space-name`
   - Push to GitHub `main`. The workflow at `.github/workflows/deploy-hf-space.yml` pushes the repo to the Space.

   You can also skip GitHub Actions and push directly:

   ```powershell
   git remote add hf https://huggingface.co/spaces/YOUR_HF_USERNAME/YOUR_SPACE_NAME
   git push hf main
   ```

5. In Supabase, open your project, click **Connect**, and copy the **Session pooler** connection string.

Use the session pooler for this app. Supabase recommends it for persistent app servers that need IPv4, and unlike transaction mode it supports prepared statements.

The string usually looks like this:

```text
postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
```

Append `?ssl=true` to it for this app:

```text
postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?ssl=true
```

If you use Supabase's **Transaction pooler** instead, append:

```text
?ssl=true&statement_cache_size=0
```

6. Add these Space secrets:

```env
DATABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?ssl=true
PUBLIC_BASE_URL=https://YOUR_SPACE_USERNAME-YOUR_SPACE_NAME.hf.space
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_FROM_NUMBER=your_twilio_number
SECRET_KEY=replace-with-a-long-random-secret
CORS_ORIGINS=https://YOUR_SPACE_USERNAME-YOUR_SPACE_NAME.hf.space
VOICE_SIMILARITY_THRESHOLD=0.65
FACE_SIMILARITY_THRESHOLD=0.55
ENABLE_VOICE_AUTH=false
```

7. Load `database/schema.sql` into Supabase:

   - Open Supabase SQL Editor.
   - Paste the full contents of `database/schema.sql`.
   - Run it.

8. Open `https://YOUR_SPACE_USERNAME-YOUR_SPACE_NAME.hf.space/atm`.

The SMS face-auth link should now use the stable `hf.space` URL instead of an ephemeral tunnel.

### If Build Fails With Exit 137 / OOMKilled

Exit `137` means the builder ran out of memory. Make sure the Space is using the current `Dockerfile`, which installs `backend/requirements.deploy.txt` instead of the full local `backend/requirements.txt`.

If you need production-grade SpeechBrain + dlib face recognition on Hugging Face, upgrade the Space hardware or deploy to a larger VPS/GPU machine. The free deployment profile is intended for a working demo.

## Other Options

- Render Free: good stable HTTPS URL, simple FastAPI deployment, but free services spin down after idle and may struggle with the biometric dependency stack.
- Railway Trial/Free: simple deployment, but free credits are limited and the trial can have network restrictions.
- Koyeb Free: stable HTTPS, but the free instance is too small for this app's current ML dependencies.
- Cloudflare Tunnel named tunnel: stable and excellent if you own a domain on Cloudflare, but it is not a deployment; your laptop/server must stay on.
