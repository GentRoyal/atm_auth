# Technical System Summary for Thesis Preparation

This report summarizes only what is present in the repository at `C:\Users\USER\Desktop\atm_auth`. It does not invent datasets, experimental results, performance metrics, references, or production features.

## 1. Project Overview

The project implements a web-based multi-factor ATM authentication prototype named "ATM Voice + Face Authentication System" in `backend/main.py`. It simulates an ATM login flow where a user enters card details and PIN, performs voice verification, receives an SMS link for mobile facial verification, and then gains access to basic banking operations.

The main problem addressed is the weakness of card-and-PIN-only ATM authentication. The prototype adds biometric and possession-based factors: voice biometrics, mobile phone access through SMS, and face biometrics.

The system type is a software prototype, not a production ATM hardware integration. It consists of a FastAPI backend, HTML/CSS/JavaScript frontend pages, PostgreSQL-compatible database schema, biometric service modules, SMS integration, and tests.

Main actors implemented in the code are:

- ATM user/customer: uses the ATM interface and mobile face verification page.
- Enrollment/admin/teller actor: implied by `/enroll/*` endpoints for registering users, voice samples, and face images.
- Backend API: validates credentials, sessions, biometrics, SMS delivery, and transactions.
- SMS provider: Twilio, Africa's Talking, or development logging mode depending on configuration.

## 2. Actual Implemented Authentication Flow

The implemented flow begins at `GET /atm`, which serves `frontend/atm/index.html`.

1. The user enters a card number and PIN in the ATM interface.
2. The frontend calls `POST /atm/insert-card` in `backend/routers/atm.py`.
3. The backend looks up the user by `users.card_number`, rejects inactive/unknown cards, and verifies the PIN using `verify_pin()` from `backend/utils/security.py`.
4. If the PIN is valid, the backend creates a row in `atm_schema.auth_sessions` with stage `card_inserted`, a generated `session_token`, expiry time from `session_expiry()`, client IP, user agent, and an auth log event.
5. The ATM page asks the user to record a voice passphrase. The frontend records about five seconds of microphone audio and encodes it as WAV in JavaScript using `AudioContext`, `createScriptProcessor`, and `encodeWav()`.
6. The frontend sends the WAV file and `session_id` to `POST /atm/verify-voice`.
7. The backend requires the session stage to be `card_inserted`, checks expiry, loads the stored `users.voice_sample`, and calls `verify_voice()` from `backend/services/voice_service.py`.
8. `verify_voice()` converts the stored binary embedding to a NumPy array, extracts an embedding from the live audio, and compares both using cosine similarity. The configured threshold is `settings.VOICE_SIMILARITY_THRESHOLD`.
9. If voice verification succeeds, the session is updated to `voice_verified`, `voice_score` and `voice_verified_at` are stored, and a successful `voice_attempt` auth log is written.
10. The frontend then calls `POST /atm/send-sms`.
11. The backend requires stage `voice_verified`, generates a lowercase hex `face_token` using `generate_face_token()`, constructs `/mobile/face-auth?token=...` using `settings.face_link_base_url`, and sends the link with `send_auth_link()`.
12. If SMS sending succeeds, the session is updated to `sms_sent`, `face_token` and `sms_sent_at` are stored, and the response includes the masked phone number, the auth URL, and a QR code data URL if QR generation succeeds.
13. The ATM screen polls `GET /atm/session/{session_id}` every three seconds while waiting for face verification.
14. The user opens the SMS link or scans the QR code on a mobile device. `GET /mobile/face-auth?token=...` validates the token, checks expiry, checks that the stage is `sms_sent` or `authenticated`, injects the token into `frontend/mobile/face_auth.html`, and serves the mobile page.
15. The mobile page calls `GET /mobile/session-info?token=...` to load user/session details and expiry.
16. The user grants camera access and captures a selfie. The JavaScript captures the video frame to a canvas and uploads it as `selfie.jpg` to `POST /mobile/verify-face`.
17. The backend requires the stage to be `sms_sent`, loads `users.face_encoding`, and calls `verify_face()` from `backend/services/face_service.py`.
18. `verify_face()` extracts a live face encoding and compares it to the stored encoding using Euclidean distance. The configured threshold is `settings.FACE_SIMILARITY_THRESHOLD`.
19. If the face check passes, the session is updated to `authenticated`, `face_score`, `face_verified_at`, and `authenticated_at` are stored, and a successful `face_attempt` log is written.
20. The ATM polling request sees stage `authenticated` and displays the transaction menu.

Failure and denial behavior:

- Unknown/inactive cards or bad PINs return HTTP 401.
- Expired sessions return HTTP 410 or are updated to stage `expired`.
- Voice verification failure logs `voice_attempt` with `success=False` and returns HTTP 401.
- SMS provider failure logs `sms_sent` with `success=False` and returns HTTP 502.
- Invalid face tokens return HTTP 404.
- Expired face links return HTTP 410.
- Invalid session stages return HTTP 400.
- Failed face verification logs `face_attempt` with `success=False` and returns HTTP 401.
- Transactions require stage `authenticated`; otherwise `backend/routers/transactions.py` returns HTTP 403.

## 3. System Architecture

Backend architecture:

- `backend/main.py` creates the FastAPI application, configures CORS, mounts `/static`, includes routers, serves `/atm` and `/mobile`, and connects/disconnects the async database during lifespan startup/shutdown.
- `backend/database.py` defines the async `databases.Database` connection, sync SQLAlchemy engine, and SQLAlchemy Core table metadata matching `database/schema.sql`.
- Routers are split by responsibility: ATM flow (`backend/routers/atm.py`), mobile face flow (`backend/routers/mobile.py`), transactions (`backend/routers/transactions.py`), and enrollment (`backend/routers/enrollment.py`).
- Service modules isolate biometric and SMS operations: `voice_service.py`, `face_service.py`, and `sms_service.py`.
- `backend/utils/security.py` handles PIN hashing/verification, token generation, JWT helpers, and expiry helpers.

Frontend architecture:

- `frontend/atm/index.html` is a single-page ATM simulation with embedded CSS and JavaScript.
- `frontend/mobile/face_auth.html` is a mobile-oriented face verification page with embedded CSS and JavaScript.
- Both frontends use same-origin API calls by setting `API` or `API_BASE` to an empty string, so they work through localhost, a tunnel URL, or a hosted URL.

Simple architecture diagram:

```text
ATM Browser UI (/atm)
  -> POST /atm/insert-card
  -> POST /atm/verify-voice
  -> POST /atm/send-sms
  -> GET /atm/session/{session_id} polling

FastAPI Backend
  -> PostgreSQL/Supabase tables
  -> Voice service: SpeechBrain or MFCC fallback
  -> Face service: face_recognition or OpenCV fallback
  -> SMS service: Twilio / Africa's Talking / dev log

SMS / QR Link
  -> Mobile Browser UI (/mobile/face-auth?token=...)
  -> GET /mobile/session-info
  -> POST /mobile/verify-face

Authenticated ATM Session
  -> POST /transactions/
  -> GET /transactions/history
```

## 4. Technologies and Libraries Actually Used

- Python: main backend language. Used across `backend/`.
- FastAPI: web API framework. Used in `backend/main.py` and all files in `backend/routers/`.
- Uvicorn: ASGI server. Referenced in README, Dockerfile, and app run commands.
- Pydantic / pydantic-settings: request/response schemas and environment config. Used in `backend/models/schemas.py` and `backend/config.py`.
- SQLAlchemy Core: table metadata and sync engine. Used in `backend/database.py`.
- databases + asyncpg: async PostgreSQL access. Used in `backend/database.py` and routers through `database.fetch_one`, `database.execute`, `database.fetch_all`.
- PostgreSQL / Supabase: schema target. Defined in `database/schema.sql`; Supabase setup documented in `CLOUDFLARE_SUPABASE.md` and `DEPLOYMENT.md`.
- psycopg: sync PostgreSQL driver for SQLAlchemy engine. Used indirectly by `_sync_database_url()` in `backend/database.py`.
- passlib[bcrypt] / bcrypt: PIN hashing and verification. Used in `backend/utils/security.py`.
- python-jose: JWT encode/decode helpers. Used in `backend/utils/security.py`, though bearer-auth routes are not implemented.
- secrets: secure token generation. Used in `backend/utils/security.py`.
- SpeechBrain: ECAPA-TDNN speaker embedding model. Used in `backend/services/voice_service.py`.
- torch and torchaudio: waveform tensor handling and resampling for SpeechBrain. Used in `voice_service.py`.
- soundfile: decodes uploaded WAV/OGG/MP3 audio bytes. Used in `voice_service.py`.
- librosa: MFCC fallback embedding when SpeechBrain/Torch is unavailable. Used in `voice_service.py`.
- NumPy: array handling for voice and face embeddings. Used in `voice_service.py`, `face_service.py`, and tests.
- Pillow: image decoding. Used in `face_service.py`.
- face_recognition: dlib-based face detection and 128-dimensional face encodings. Used in `face_service.py`.
- OpenCV (`opencv-python-headless`): Haar cascade and HOG fallback for face encoding when `face_recognition` is unavailable. Used in `face_service.py`.
- Twilio: SMS sending. Used in `backend/services/sms_service.py`.
- Africa's Talking: alternate SMS provider. Used in `sms_service.py`.
- qrcode: generates QR code data URL for the mobile face-auth link. Used in `_qr_code_data_url()` in `backend/routers/atm.py`.
- python-multipart: required by FastAPI for file/form uploads. Used indirectly by endpoints accepting `Form(...)` and `File(...)`.
- HTML/CSS/JavaScript: frontend UI and browser APIs. Used in `frontend/atm/index.html` and `frontend/mobile/face_auth.html`.
- Browser APIs: microphone via `navigator.mediaDevices.getUserMedia({ audio: true })`; camera via `getUserMedia({ video: ... })`; canvas capture via `canvas.toBlob()`.
- pytest / pytest-asyncio: testing. Used in `backend/tests/test_auth_flow.py`.
- httpx: imported in tests for `AsyncClient` and `ASGITransport`, though the present tests are mostly service/schema tests.
- python-dotenv: listed in requirements, but environment loading is implemented through `pydantic-settings` with `backend/.env`.
- Cloudflare Tunnel: documented setup for public HTTPS URL in `CLOUDFLARE_SUPABASE.md`; not a Python dependency.
- Docker: `Dockerfile` for container deployment using `backend/requirements.deploy.txt`.
- GitHub Actions: `.github/workflows/deploy-hf-space.yml` pushes to a Hugging Face Space when configured.
- Packages listed but not clearly used in source: `aiofiles`, `pyotp`, and `httpx` outside tests.

## 5. Database Design

The database schema is defined in `database/schema.sql` under schema `atm_schema`, and mirrored in SQLAlchemy Core tables in `backend/database.py`.

Main tables:

- `users`: stores identity, account number, phone number, card number, PIN hash, voice embedding bytes, face encoding bytes, active status, and timestamps.
- `accounts`: stores bank account information linked to `users.id`, including account type, balance, currency, frozen status, and timestamps.
- `auth_sessions`: stores each authentication attempt/session, linked to `users.id`, card number, `session_token`, `face_token`, current stage, biometric scores, timestamps for SMS/voice/face/authentication, expiry, IP address, user agent, and creation time.
- `transactions`: stores banking operations linked to `auth_sessions.id` and `accounts.id`, including type, amount, recipient account, description, status, and creation time.
- `auth_logs`: stores security/audit events linked to session and user, including event name, success flag, score, detail, IP address, and creation time.

Relationships:

- One user can have accounts through `accounts.user_id -> users.id`.
- Auth sessions link to users through `auth_sessions.user_id -> users.id`.
- Transactions link to sessions and accounts through `transactions.session_id` and `transactions.account_id`.
- Auth logs link to sessions and users.

Biometric storage:

- Voice data is stored as binary `users.voice_sample`. The code stores an embedding, not the original raw recording, using `embedding_to_bytes()` in `backend/services/voice_service.py`.
- Face data is stored as binary `users.face_encoding` using `encoding_to_bytes()` in `backend/services/face_service.py`.

Temporary tokens:

- `auth_sessions.session_token` is generated at card/PIN success using `generate_session_token()`, but it is not exposed as bearer authentication in the current routes.
- `auth_sessions.face_token` is generated before SMS delivery using `generate_face_token()` and is used by mobile face verification routes.
- Expiry is stored in `auth_sessions.expires_at` and checked with `is_expired()`.

## 6. API Endpoints

Application/root endpoints in `backend/main.py`:

- `GET /`: redirects to `/atm`.
- `GET /atm`: serves `frontend/atm/index.html`.
- `GET /mobile`: serves `frontend/mobile/face_auth.html`.
- `GET /verify/face/{token}`: redirects to `/mobile/face-auth?token={token}`.
- `GET /health`: returns `{"status": "ok", "version": "1.0.0"}`.

ATM endpoints in `backend/routers/atm.py`:

- `POST /atm/insert-card`: accepts JSON `card_number` and `pin`; verifies card/PIN; creates session; returns `session_id`, message, and stage `card_inserted`.
- `POST /atm/verify-voice`: accepts multipart form `session_id` and audio file; verifies stored voice embedding against uploaded audio; returns success, score, message, and stage `voice_verified`, or an error.
- `POST /atm/send-sms`: accepts multipart form `session_id`; generates `face_token`; sends mobile face link; stores SMS/token data; returns masked phone, stage `sms_sent`, auth URL, and optional QR code data URL.
- `GET /atm/session/{session_id}`: returns current stage, expiry, and user name for ATM polling; updates expired sessions to `expired`.

Mobile endpoints in `backend/routers/mobile.py`:

- `GET /mobile/face-auth?token=...`: validates face token and serves the mobile face capture page with token injected.
- `GET /mobile/session-info?token=...`: returns stage, expiry, first name, and expired flag for the mobile page.
- `POST /mobile/verify-face`: accepts multipart form `token` and image file; verifies selfie against stored face encoding; updates session to `authenticated` on success.

Enrollment endpoints in `backend/routers/enrollment.py`:

- `POST /enroll/user`: accepts `full_name`, `account_number`, `phone_number`, `card_number`, and `pin`; creates user with hashed PIN and default savings account.
- `POST /enroll/voice/{user_id}`: accepts audio file; extracts voice embedding; stores it in `users.voice_sample`.
- `POST /enroll/face/{user_id}`: accepts image file; extracts face encoding; stores it in `users.face_encoding`.

Transaction endpoints in `backend/routers/transactions.py`:

- `POST /transactions/`: accepts `session_id`, transaction `type`, optional `amount`, optional `recipient_account`, and optional `description`; requires authenticated session; performs balance inquiry, withdrawal, deposit, or transfer.
- `GET /transactions/history?session_id=...&limit=10`: requires authenticated session; returns recent transactions for the user's account.

## 7. Frontend Pages and User Interfaces

ATM interface:

- File: `frontend/atm/index.html`.
- Provides a styled ATM machine interface with staged screens: card/PIN, voice recording, SMS/QR waiting, authenticated transaction menu, amount entry, and receipt.
- Uses JavaScript functions such as `handleCardInsert()`, `startVoiceRecord()`, `submitVoice()`, `startPolling()`, `submitTransaction()`, and `showReceipt()`.
- Records audio with `navigator.mediaDevices.getUserMedia({ audio: true })`.
- Encodes the recording as WAV using `createWavRecorder()`, `encodeWav()`, and `writeAscii()`.
- Calls `/atm/insert-card`, `/atm/verify-voice`, `/atm/send-sms`, `/atm/session/{session_id}`, and `/transactions/`.
- Shows SMS delivery details, masked phone number, QR code, and mobile link if returned by the backend.

Mobile face verification interface:

- File: `frontend/mobile/face_auth.html`.
- Provides a mobile-friendly face verification page with session loading, expiry timer, camera preview, face oval guide, capture button, retry button, and success/error screens.
- Uses `FACE_TOKEN` injected by the backend, or falls back to reading `token` from the URL query string.
- Calls `/mobile/session-info` and `/mobile/verify-face`.
- Uses `navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })` to access the camera.
- Captures a frame to a hidden `<canvas>` and uploads it as JPEG with `canvas.toBlob()`.

## 8. Biometric Verification Implementation

Voice enrollment:

- Endpoint: `POST /enroll/voice/{user_id}` in `backend/routers/enrollment.py`.
- The uploaded audio is passed to `extract_embedding()` in `backend/services/voice_service.py`.
- The resulting NumPy embedding is converted to `float32` bytes with `embedding_to_bytes()` and stored in `users.voice_sample`.
- The endpoint docstring says the user should read a fixed passphrase clearly, but the code performs speaker embedding similarity, not explicit speech-to-text phrase matching.

Voice verification:

- Endpoint: `POST /atm/verify-voice`.
- Stored `users.voice_sample` is loaded as bytes and converted back to a `float32` NumPy array.
- Live uploaded audio is decoded with `soundfile`, resampled to 16 kHz with `torchaudio` if necessary, converted to mono, and encoded using SpeechBrain `speechbrain/spkrec-ecapa-voxceleb`.
- If the SpeechBrain model cannot load, `_fallback_embedding()` attempts an MFCC-based embedding with `librosa`.
- Matching uses cosine similarity through `cosine_similarity()`.
- Decision rule: `score >= settings.VOICE_SIMILARITY_THRESHOLD`.
- Current default in `backend/config.py` is `VOICE_SIMILARITY_THRESHOLD = 0.00`, with a commented value `#0.65`. This is a very low threshold and should be described as prototype/testing configuration, not production security.
- If embedding extraction fails, verification returns `(False, 0.0)`.
- If enrolled and live embedding dimensions differ, verification fails.

Face enrollment:

- Endpoint: `POST /enroll/face/{user_id}`.
- Uploaded image bytes are passed to `extract_face_encoding()` in `backend/services/face_service.py`.
- The face encoding is converted to `float64` bytes with `encoding_to_bytes()` and stored in `users.face_encoding`.

Face verification:

- Endpoint: `POST /mobile/verify-face`.
- Stored `users.face_encoding` is loaded as `float64`.
- Uploaded selfie bytes are decoded with Pillow to RGB NumPy array.
- `face_recognition.face_locations(..., model="hog")` detects faces.
- If no face is detected, verification fails.
- If multiple faces are detected, the code selects the largest face.
- `face_recognition.face_encodings()` extracts a 128-dimensional encoding.
- If `face_recognition` is unavailable, `_fallback_face_encoding()` tries OpenCV Haar cascade detection and HOG features.
- Matching uses Euclidean distance through `euclidean_distance()`.
- Decision rule: `distance <= settings.FACE_SIMILARITY_THRESHOLD`.
- Current default in `backend/config.py` is `FACE_SIMILARITY_THRESHOLD = 0.55`.
- If no live encoding is produced, `verify_face()` returns `(False, 9.99)`.

Limitations/assumptions:

- No speech recognition confirms that the spoken phrase matches an expected sentence.
- Voice threshold is currently set very low by default.
- Face matching uses a single enrolled encoding per user.
- No liveness detection, anti-spoofing, replay detection, or challenge-response phrase selection is implemented.
- No dataset, accuracy evaluation, FAR/FRR/EER metrics, or biometric benchmark results are present in the repository.

## 9. Security Features

Implemented security-related features:

- PINs are stored as bcrypt hashes through `hash_pin()` and verified through `verify_pin()`.
- Card/PIN must pass before voice authentication.
- Voice verification must pass before SMS link generation.
- Face verification must pass before transaction access.
- `generate_session_token()` and `generate_face_token()` use Python `secrets`.
- Face tokens are lowercase hexadecimal to avoid SMS URL splitting issues.
- Sessions expire based on `SESSION_EXPIRE_MINUTES`, default 10 minutes.
- Mobile links are checked for validity and expiry.
- Session stage tracking prevents steps from being executed out of order.
- Authentication attempts are logged in `auth_logs`.
- Sensitive settings are expected in `backend/.env`, which is ignored by `.gitignore` and `.dockerignore`.
- SMS links use `PUBLIC_BASE_URL` when configured so mobile devices can reach the app through a public HTTPS URL.
- CORS origins are configurable in `backend/config.py`.

Not implemented or weak areas:

- No production-grade user authentication or admin authorization protects enrollment endpoints.
- No rate limiting or account lockout for repeated PIN, voice, or face failures.
- No CSRF protection is visible.
- No liveness detection for face or voice.
- No encryption-at-rest layer for biometric embeddings beyond database storage.
- `session_token` is generated but not used as a bearer token in transaction routes.
- JWT helpers exist but are not integrated into route authorization.
- Transfer updates are not wrapped in an explicit database transaction, so production atomicity is not guaranteed from the code.
- Voice threshold default is `0.00`, which is not suitable for production.

## 10. Banking Operations

Banking features are implemented in `backend/routers/transactions.py` and exposed through the ATM frontend.

All transaction endpoints call `_require_authenticated_session()`, which requires:

- Session exists.
- Session is not expired.
- Session stage is `authenticated`.

Implemented operations:

- Balance inquiry: inserts a `transactions` row with type `balance_inquiry`, does not change balance, returns current balance.
- Withdrawal: requires positive amount, sufficient balance, and amount not above ₦150,000. It deducts from sender account, updates `accounts.balance`, records a completed transaction, and returns remaining balance.
- Deposit: requires positive amount. It adds to account balance, records a completed transaction, and returns new balance.
- Transfer: requires positive amount, recipient account number, sufficient balance, existing recipient user and account. It debits sender, credits recipient, records a completed transfer transaction, and returns sender balance.
- Transaction history: `GET /transactions/history` returns recent rows for the authenticated user's account.

Frontend transaction support:

- `frontend/atm/index.html` has buttons for balance, withdraw, deposit, and transfer.
- It displays receipt-style transaction output including type, amount, balance, status, and transaction reference.

## 11. Testing

Testing framework:

- `pytest` and `pytest-asyncio`.
- Test file: `backend/tests/test_auth_flow.py`.
- Current local result from this workspace: `26 passed in 3.76s`.

Covered tests:

- Voice cosine similarity for identical, orthogonal, and opposite vectors.
- Voice verification pass/fail with mocked live embeddings.
- Voice embedding byte roundtrip.
- Face Euclidean distance.
- Face verification pass/fail/no-face paths with mocked live encodings.
- Face encoding byte roundtrip.
- PIN hashing and verification.
- Session token uniqueness over 100 generated tokens.
- Face token length.
- Expiry helper for past/future datetimes.
- JWT create/decode and expired-token behavior.
- SMS phone masking and dev-mode SMS sending.
- Pydantic schema validation for card numbers and transaction request/enums.

Missing tests:

- No full API integration test for the complete route sequence using a real or mocked database.
- No frontend/browser tests.
- No Twilio or Africa's Talking integration tests.
- No actual SpeechBrain model extraction tests.
- No actual face_recognition extraction tests using real images.
- No database transaction/rollback tests.
- No tests for rate limiting or account lockout because those features are not implemented.

## 12. Configuration and Deployment/Testing Setup

Local run setup from `README.md`:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/atm
```

Environment variables are defined in `backend/config.py` and loaded from `backend/.env`. Keys detected in the local `.env` are:

- `DATABASE_URL`
- `PUBLIC_BASE_URL`
- `SMS_PROVIDER`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`

Other supported settings in code include:

- `DATABASE_URL_SYNC`
- `SECRET_KEY`
- `ALGORITHM`
- `SESSION_EXPIRE_MINUTES`
- `AT_USERNAME`
- `AT_API_KEY`
- `BASE_URL`
- `MOBILE_FACE_URL`
- `VOICE_SIMILARITY_THRESHOLD`
- `FACE_SIMILARITY_THRESHOLD`
- `CORS_ORIGINS`

Database setup:

- Run `database/schema.sql` in PostgreSQL or Supabase SQL Editor.
- Supabase session pooler format is documented in `CLOUDFLARE_SUPABASE.md` and `DEPLOYMENT.md`.
- `backend/database.py` converts Supabase-style `sslmode`/`ssl` options for async and sync drivers.

Twilio setup:

- Set `SMS_PROVIDER=twilio`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER`.
- `sms_service.py` returns success for Twilio message statuses `queued`, `sent`, or `delivered`.

Cloudflare/local mobile testing:

- `CLOUDFLARE_SUPABASE.md` documents a Cloudflare Quick Tunnel command exposing local port 8001.
- Set `PUBLIC_BASE_URL=https://something.trycloudflare.com` and restart the backend.
- Quick tunnel URLs are temporary; old SMS links break after tunnel restart.
- Stable Cloudflare Tunnel requires a Cloudflare-connected domain and named tunnel.

Deployment:

- `Dockerfile` uses Python 3.11 slim and installs `backend/requirements.deploy.txt`.
- `requirements.deploy.txt` intentionally omits heavier SpeechBrain/Torch/dlib dependencies and relies on fallback biometric implementations.
- `DEPLOYMENT.md` describes Hugging Face Spaces Docker deployment with Supabase.
- `.github/workflows/deploy-hf-space.yml` pushes the repository to a Hugging Face Space using GitHub secrets `HF_TOKEN` and `HF_SPACE_REPO`.

## 13. Limitations of the Implemented Prototype

Implemented prototype limitations based on code:

- It is a browser/web prototype, not integrated with real ATM card readers, cash dispensers, receipt printers, or bank core systems.
- Enrollment endpoints are not protected by admin authentication.
- Voice threshold is currently configured as `0.00` by default, which is insecure outside testing.
- Voice verification checks speaker similarity only; it does not verify the spoken words.
- Face verification uses single-image/encoding comparison without liveness detection.
- No anti-spoofing protections are implemented for replayed audio, printed photos, screen photos, masks, or deepfakes.
- No formal biometric dataset, evaluation protocol, accuracy results, FAR, FRR, or EER metrics are included.
- SMS delivery depends on external providers and phone connectivity.
- Mobile face verification depends on browser camera permission and a reachable public URL.
- Cloudflare Quick Tunnel links are temporary unless a named tunnel/domain is configured.
- No rate limiting, lockout, fraud scoring, or monitoring dashboard is implemented.
- No encryption of stored biometric embeddings is implemented at application level.
- Transaction transfer updates are not explicitly atomic in the code.
- Free Docker deployment uses fallback biometric methods and is not equivalent to the full local biometric stack.

## 14. Recommended Thesis Chapter Mapping

Chapter One: Introduction

- Problem of PIN-only ATM security.
- Motivation for multi-factor authentication.
- Implemented factors: card/PIN, voice biometrics, SMS/mobile handoff, face biometrics.
- Scope: software prototype, not production ATM hardware.
- Actors and high-level workflow.

Chapter Two: Literature Review

- Discuss ATM authentication, PIN vulnerabilities, biometric authentication, speaker verification, face recognition, and SMS/mobile verification.
- Do not claim project-specific accuracy or cite fake studies.
- Use external academic sources selected separately by the thesis writer.
- Clearly state that the implementation differs from the original keystroke-dynamics idea.

Chapter Three: Methodology / System Analysis and Design

- Use the implemented flow from Section 2.
- Include architecture from Section 3.
- Include database design from Section 5.
- Include API and session-stage design.
- Include tools/libraries from Section 4.
- Include security design and limitations.

Chapter Four: Implementation and Testing

- Describe implemented files/modules, endpoints, frontend behavior, biometric services, SMS service, and transactions.
- Include screenshots or diagrams from the running app if available.
- Report only actual tests: `backend/tests/test_auth_flow.py`, 26 passing tests.
- Avoid claiming biometric accuracy experiments unless new experiments are conducted.

Chapter Five: Summary, Conclusion, and Recommendation

- Summarize the completed prototype.
- State that the system demonstrates layered ATM authentication.
- Discuss limitations such as threshold tuning, liveness detection, protected enrollment, rate limiting, and real ATM integration.
- Recommend future work: production threshold calibration, biometric evaluation dataset, liveness checks, secure admin enrollment, account lockout/rate limiting, encryption of biometric templates, hardware integration, and stable deployment.

## 15. Files/Folders Map

- `backend/main.py`: FastAPI app entry point, route inclusion, CORS, static mount, HTML serving, health check.
- `backend/config.py`: environment-driven settings for database, security, SMS, URLs, thresholds, and CORS.
- `backend/database.py`: async database connection, sync SQLAlchemy engine, SQLAlchemy Core table definitions.
- `backend/models/schemas.py`: Pydantic request/response schemas and enums for sessions and transactions.
- `backend/routers/atm.py`: ATM authentication endpoints for card/PIN, voice, SMS link, and session polling.
- `backend/routers/mobile.py`: mobile face-auth page, session info, and face verification endpoints.
- `backend/routers/enrollment.py`: user, voice, and face enrollment endpoints.
- `backend/routers/transactions.py`: authenticated banking transaction endpoints.
- `backend/services/voice_service.py`: voice embedding extraction, fallback MFCC embedding, cosine similarity, voice matching.
- `backend/services/face_service.py`: image decoding, face encoding extraction, OpenCV fallback, Euclidean distance, face matching.
- `backend/services/sms_service.py`: SMS message construction and providers for dev mode, Africa's Talking, and Twilio.
- `backend/utils/security.py`: PIN hashing/verification, token generation, JWT helpers, expiry helpers.
- `backend/tests/test_auth_flow.py`: unit tests for voice, face, security, SMS, and schemas.
- `backend/requirements.txt`: full local dependency stack including SpeechBrain, Torch, face_recognition, Twilio, pytest, etc.
- `backend/requirements.deploy.txt`: lightweight deployment dependency stack with fallback biometric support.
- `database/schema.sql`: PostgreSQL schema, tables, constraints, and indexes.
- `frontend/atm/index.html`: complete ATM simulation UI and JavaScript flow.
- `frontend/mobile/face_auth.html`: mobile face verification UI and JavaScript camera/capture flow.
- `README.md`: local setup, running, enrollment checklist, and public URL explanation.
- `CLOUDFLARE_SUPABASE.md`: Cloudflare Tunnel + Supabase testing setup.
- `DEPLOYMENT.md`: Hugging Face Spaces and Supabase deployment notes.
- `Dockerfile`: Docker deployment using lightweight requirements.
- `.github/workflows/deploy-hf-space.yml`: GitHub Actions workflow for pushing to Hugging Face Space.
- `.gitignore` / `.dockerignore`: exclude virtualenv, caches, logs, and `backend/.env`.
- `outputs/` and `tools/`: generated presentation/report artifacts and helper script; not core runtime system files.

## Implemented vs Planned/Recommended Features

Implemented:

- Card number and PIN verification.
- bcrypt PIN hashing.
- Voice enrollment and voice verification by embedding similarity.
- SMS face-auth link delivery through configurable providers.
- QR code fallback for the mobile face-auth URL.
- Mobile face capture and face verification.
- Session stages and expiry.
- Auth logs.
- Basic banking transactions after authentication.
- PostgreSQL/Supabase-compatible schema.
- Local and Docker deployment documentation.
- Unit tests for core utilities and matching logic.

Planned/recommended but not implemented:

- Keystroke dynamics.
- Production ATM hardware integration.
- Voice phrase recognition.
- Face or voice liveness detection.
- Admin authentication for enrollment endpoints.
- Rate limiting and account lockout.
- Formal biometric accuracy evaluation.
- Encrypted biometric template storage at application level.
- Transaction atomicity hardening.
- Stable public deployment unless configured separately.
