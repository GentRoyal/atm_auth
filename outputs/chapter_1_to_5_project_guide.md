# Chapter 1 to 5 Project Guide

Project: Multi-Factor ATM Authentication Prototype Using PIN and Face Biometrics with SMS-Based Mobile Verification

This guide reflects the current implementation in the repository after the latest changes:

- Voice authentication is still present in the codebase but disabled by default with `ENABLE_VOICE_AUTH=false`.
- The active authentication flow is now PIN verification followed by SMS/QR mobile face verification.
- Face enrollment now supports multiple face images/angles and stores one averaged face template.
- No fake results, datasets, references, or performance metrics are included here.

## Current Working Status

The codebase currently passes the automated tests:

```powershell
.venv\Scripts\python.exe -m pytest backend\tests -q
```

Current result:

```text
28 passed
```

What this confirms:

- PIN hashing and verification helpers work.
- Token generation and expiry helpers work.
- JWT helper functions work, although JWT route protection is not currently integrated.
- Voice utility functions still work in tests, even though voice is disabled in the live authentication flow.
- Face distance, encoding serialization, and multi-angle face-template averaging work in tests.
- SMS development-mode behavior and phone masking are tested.
- Pydantic request schema validation is tested.

What this does not fully confirm:

- A full live end-to-end run with a real PostgreSQL/Supabase database, Twilio SMS, mobile browser camera, and real face images still needs manual testing.
- Actual biometric accuracy is not measured in the repository.
- No formal dataset-based evaluation is included.

## Current Implemented System Summary

The implemented system is a web-based ATM authentication prototype. It simulates the process of a customer accessing an ATM by entering their card/PIN details and completing a mobile face verification step.

The system originally included PIN, voice authentication, SMS handoff, and face authentication. The voice authentication code has not been deleted, but it is disabled by default. This means the current live flow is:

1. User enters card number and PIN at the ATM page.
2. Backend verifies the card number and PIN.
3. Backend creates an authentication session.
4. Since voice is disabled, the session is moved forward to the SMS/face-verification stage.
5. Backend generates a temporary face-verification token.
6. Backend sends an SMS link to the registered phone number through the configured SMS provider.
7. ATM also displays a QR code fallback for the face-verification link.
8. User opens the mobile link and captures a selfie.
9. Backend compares the selfie with the enrolled face template.
10. If the face check passes before token expiry, the session becomes authenticated.
11. The ATM page detects authentication through polling and unlocks banking operations.
12. User can perform balance inquiry, withdrawal, deposit, or transfer.

Voice can be restored later by setting:

```env
ENABLE_VOICE_AUTH=true
```

When voice is enabled, the flow becomes:

```text
Card/PIN -> Voice verification -> SMS/QR face link -> Mobile face verification -> Transactions
```

## Key Source Files

- `backend/main.py`: FastAPI application setup, route registration, static/frontend serving, database startup/shutdown.
- `backend/config.py`: environment settings, including `ENABLE_VOICE_AUTH`, thresholds, database URL, SMS credentials, and public URL.
- `backend/database.py`: async database connection and SQLAlchemy Core table definitions.
- `database/schema.sql`: PostgreSQL/Supabase schema.
- `backend/routers/atm.py`: ATM authentication flow.
- `backend/routers/mobile.py`: mobile face verification flow.
- `backend/routers/enrollment.py`: user, voice, and multi-angle face enrollment endpoints.
- `backend/routers/transactions.py`: banking operations after authentication.
- `backend/services/face_service.py`: face encoding, face comparison, and multi-angle encoding averaging.
- `backend/services/voice_service.py`: retained voice embedding and verification code.
- `backend/services/sms_service.py`: Twilio and development SMS logic.
- `backend/utils/security.py`: PIN hashing, token generation, JWT helpers, and expiry helpers.
- `frontend/atm/index.html`: ATM web interface.
- `frontend/mobile/face_auth.html`: mobile face verification page.
- `backend/tests/test_auth_flow.py`: automated tests.

## Chapter One: Introduction

### Suggested Chapter Focus

Chapter One should introduce the general ATM authentication problem and explain why relying only on ATM cards and PINs is not strong enough. The chapter should present the need for additional authentication factors and introduce the implemented prototype as a software-based solution.

### Background of the Study

Automated Teller Machines allow customers to perform banking operations without entering a bank branch. Traditional ATM authentication commonly depends on possession of a bank card and knowledge of a PIN. However, card-and-PIN authentication can be weakened by card theft, shoulder surfing, PIN disclosure, skimming, social engineering, and unauthorized access when a PIN is compromised.

To improve security, the implemented project adds another layer of identity verification using facial biometrics. Instead of allowing access immediately after PIN verification, the system sends a temporary verification link to the customer's registered phone number. The customer then completes facial verification on a mobile device before ATM access is granted.

### Problem Statement

The problem addressed by this system is that a PIN alone may not reliably prove that the person using an ATM is the legitimate account holder. If an attacker obtains a user's card details and PIN, they may be able to access the account. A stronger method is needed to verify both what the user knows and who the user is.

The implemented prototype addresses this by combining:

- Card/PIN verification.
- SMS-based mobile verification handoff.
- Face biometric verification.
- Session tracking and token expiry.

### Aim of the Study

The aim is to design and implement a multi-factor ATM authentication prototype that improves ATM access control by combining PIN verification, SMS-based mobile handoff, and facial verification.

### Suggested Objectives

1. To design a web-based ATM authentication prototype.
2. To implement PIN-based user verification using securely hashed PINs.
3. To generate temporary mobile face-verification links after successful PIN verification.
4. To send the face-verification link to the user's registered phone number using an SMS provider.
5. To implement mobile facial verification using enrolled face templates.
6. To support multi-angle face enrollment by accepting multiple face images during registration.
7. To allow authenticated users to perform basic banking operations.
8. To test important system components such as security utilities, biometric comparison helpers, SMS logic, and schema validation.

### Research Questions

These should be phrased carefully because the project does not contain formal biometric accuracy experiments.

Possible research questions:

1. How can PIN verification and face biometrics be combined to improve ATM authentication?
2. How can SMS-based mobile handoff be used to complete facial verification during ATM access?
3. How can multiple face angles during enrollment improve the stored face reference used by the prototype?
4. What are the functional components required to implement a web-based multi-factor ATM authentication prototype?

Avoid claiming that the project proves a specific accuracy rate unless separate experiments are later performed.

### Scope of the Study

The scope is limited to a software prototype. It includes:

- ATM browser interface.
- Mobile browser face verification page.
- FastAPI backend.
- PostgreSQL/Supabase-compatible database schema.
- PIN verification.
- SMS link generation and delivery.
- QR fallback for mobile verification.
- Face enrollment and verification.
- Multi-angle face enrollment.
- Basic banking operations after authentication.

Out of scope:

- Real ATM card reader hardware.
- Cash dispenser hardware.
- Bank core banking integration.
- Production-grade biometric liveness detection.
- Formal biometric dataset evaluation.
- Real fraud monitoring dashboard.

### Significance of the Study

The project demonstrates how layered authentication can improve the security design of ATM access. It also shows how mobile phones can be used as a bridge for biometric verification without requiring special ATM camera hardware. The implementation may serve as a foundation for future work involving stronger biometric evaluation, liveness detection, and integration with real banking infrastructure.

## Chapter Two: Literature Review

### Suggested Chapter Focus

Chapter Two should discuss existing concepts and related work, but you must add real academic references separately. The codebase itself does not contain literature review sources or performance results.

### Topics to Review

1. ATM security and traditional card/PIN authentication.
2. Weaknesses of PIN-only ATM authentication.
3. Multi-factor authentication.
4. Biometric authentication in banking systems.
5. Face recognition for identity verification.
6. Mobile-assisted authentication.
7. SMS-based authentication and its limitations.
8. Biometric template storage and security concerns.
9. Liveness detection and anti-spoofing as future improvements.

### Important Methodology Correction

The original project idea mentioned keystroke dynamics and voice authentication. The current implemented system does not implement keystroke dynamics. Voice authentication still exists in code but is disabled by default. Therefore, the literature review can mention voice biometrics and keystroke dynamics as related approaches, but the implemented method should be clearly described as PIN + SMS/mobile handoff + face biometrics.

### What Not to Claim

Do not claim:

- A specific face recognition accuracy.
- A specific false acceptance rate or false rejection rate.
- That a dataset was used.
- That liveness detection was implemented.
- That the system is production-ready.

These are not present in the repository.

## Chapter Three: Methodology / System Analysis and Design

### Suggested Chapter Focus

Chapter Three should describe how the system was designed, the architecture, database structure, authentication workflow, and technologies used.

### Current Methodology

The methodology follows a prototype-based software development approach:

1. Requirement analysis.
2. System architecture design.
3. Database schema design.
4. Backend API implementation.
5. Frontend ATM interface implementation.
6. Mobile face verification interface implementation.
7. Biometric enrollment and verification implementation.
8. SMS/public URL setup for mobile handoff.
9. Transaction feature implementation.
10. Testing and documentation.

### Active Authentication Workflow

```text
User enters card number and PIN
        |
        v
Backend validates card and bcrypt-hashed PIN
        |
        v
Auth session is created with expiry time
        |
        v
Voice step is skipped because ENABLE_VOICE_AUTH=false
        |
        v
Backend generates face_token
        |
        v
SMS link and QR code are generated
        |
        v
User opens mobile face verification page
        |
        v
Mobile camera captures selfie
        |
        v
Backend compares selfie with enrolled face template
        |
        v
If match succeeds before expiry, session becomes authenticated
        |
        v
ATM unlocks banking operations
```

### Optional Voice Workflow

Voice authentication is retained but disabled. If enabled, the system requires the user to record a voice sample after PIN verification. The backend extracts a voice embedding and compares it with the stored voice embedding using cosine similarity. The route is `POST /atm/verify-voice`.

### Multi-Angle Face Enrollment Design

The face enrollment endpoint is:

```text
POST /enroll/face/{user_id}
```

It now accepts:

- `image`: a single face image.
- `images`: multiple face images from different angles.

Recommended images:

- Front-facing image.
- Slight-left face angle.
- Slight-right face angle.

The backend extracts a face encoding from each valid image. It then averages the valid encodings using `combine_face_encodings()` in `backend/services/face_service.py`. The averaged encoding is stored in the existing `users.face_encoding` column.

This improves enrollment coverage without changing the database schema.

### System Architecture

```text
ATM Interface
  frontend/atm/index.html
        |
        v
FastAPI Backend
  backend/main.py
  backend/routers/atm.py
        |
        +--> PostgreSQL/Supabase Database
        |      users, accounts, auth_sessions, transactions, auth_logs
        |
        +--> SMS Service
        |      Twilio / dev logging
        |
        +--> Face Service
               face_recognition / OpenCV fallback

SMS or QR Link
        |
        v
Mobile Face Page
  frontend/mobile/face_auth.html
        |
        v
POST /mobile/verify-face
        |
        v
Session authenticated
        |
        v
ATM transaction menu
```

### Database Design

Main tables from `database/schema.sql`:

- `users`: stores user identity, account number, phone number, card number, PIN hash, voice sample, face encoding, active status, and timestamps.
- `accounts`: stores user account balance, account type, currency, frozen status, and timestamps.
- `auth_sessions`: stores authentication sessions, stage, tokens, biometric scores, expiry, IP, user agent, and timestamps.
- `transactions`: stores banking operation records.
- `auth_logs`: stores authentication-related events.

Important fields:

- `users.pin_hash`: bcrypt-hashed PIN.
- `users.face_encoding`: stored face template, now possibly averaged from multiple enrollment images.
- `users.voice_sample`: retained voice embedding field.
- `auth_sessions.face_token`: temporary mobile verification token.
- `auth_sessions.stage`: tracks progress such as `voice_verified`, `sms_sent`, `authenticated`, `expired`, and `failed`.
- `auth_sessions.expires_at`: controls token/session expiry.
- `transactions.type`: withdrawal, deposit, transfer, or balance inquiry.

### Technologies Used

Backend:

- Python.
- FastAPI.
- Pydantic and pydantic-settings.
- SQLAlchemy Core.
- databases and asyncpg.
- PostgreSQL/Supabase.
- passlib and bcrypt.
- python-jose.
- NumPy.
- Pillow.
- face_recognition.
- OpenCV fallback.
- SpeechBrain/Torch/Torchaudio/SoundFile/Librosa retained for optional voice authentication.
- Twilio for SMS.
- qrcode for QR fallback.

Frontend:

- HTML.
- CSS.
- JavaScript.
- Browser microphone API retained in commented/disabled voice flow.
- Browser camera API for mobile selfie capture.
- Canvas API for image capture.

Testing:

- pytest.
- pytest-asyncio.
- unittest.mock.
- httpx is imported for possible ASGI testing support.

Deployment/testing setup:

- Uvicorn local server.
- Cloudflare Tunnel for public mobile testing.
- Supabase PostgreSQL option.
- Dockerfile for deployment.
- Hugging Face Space deployment notes exist, but earlier free build limitations were documented.

## Chapter Four: Implementation and Testing

### Suggested Chapter Focus

Chapter Four should explain how the system was built and tested. It should include screenshots of the ATM page, mobile face page, API docs, database tables, and successful test output if needed.

### Backend Implementation

The backend is implemented with FastAPI. `backend/main.py` creates the app, sets up CORS, serves the frontend pages, connects to the database, and includes all routers.

Routers:

- `backend/routers/atm.py`: card/PIN verification, optional voice route, SMS link generation, and session polling.
- `backend/routers/mobile.py`: mobile face page, session info, and face verification.
- `backend/routers/enrollment.py`: user enrollment, voice enrollment, and multi-angle face enrollment.
- `backend/routers/transactions.py`: balance inquiry, withdrawal, deposit, transfer, and transaction history.

### Frontend Implementation

ATM frontend:

- File: `frontend/atm/index.html`.
- Handles card/PIN entry.
- Skips the voice step when backend returns stage `voice_verified`.
- Requests SMS/QR face link.
- Polls session status.
- Displays transaction menu after authentication.

Mobile frontend:

- File: `frontend/mobile/face_auth.html`.
- Validates token through the backend.
- Starts the mobile camera.
- Captures a selfie through canvas.
- Uploads the selfie to the backend.
- Shows success or error status.

### Face Enrollment Implementation

Face enrollment is handled by `POST /enroll/face/{user_id}`. The implementation supports both old and new usage:

- Old: upload one file as `image`.
- New: upload multiple files as `images`.

For every uploaded image:

1. Image bytes are read.
2. `extract_face_encoding()` attempts to detect and encode a face.
3. Invalid images are skipped and listed in `failed_images`.
4. Valid encodings are averaged.
5. The averaged encoding is stored as `face_encoding`.

Response includes:

- `message`
- `encoding_dim`
- `images_received`
- `valid_images`
- `failed_images`
- `recommendation`

### Face Verification Implementation

Face verification is handled by `POST /mobile/verify-face`. The backend:

1. Looks up the session using `face_token`.
2. Checks token/session expiry.
3. Confirms the session is in the correct stage.
4. Loads the enrolled face encoding.
5. Extracts the live selfie encoding.
6. Compares the encodings using Euclidean distance.
7. Uses `FACE_SIMILARITY_THRESHOLD`, default `0.55`.
8. Marks the session as `authenticated` if the distance is within threshold.

### Voice Implementation Status

Voice files still exist:

- `backend/services/voice_service.py`
- `POST /enroll/voice/{user_id}`
- `POST /atm/verify-voice`
- Voice recording block in `frontend/atm/index.html`

However, active runtime behavior is controlled by:

```env
ENABLE_VOICE_AUTH=false
```

When disabled:

- After PIN verification, the backend stores the session at `voice_verified` stage so the SMS step can proceed.
- A `voice_skipped` auth log is written.
- `/atm/verify-voice` returns an error indicating voice is disabled.
- The ATM frontend skips the voice screen and sends the SMS face link.

### SMS Implementation

SMS logic is in `backend/services/sms_service.py`. It supports:

- Development logging mode.
- Twilio.

The current real SMS flow uses Twilio when configured with:

```env
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=...
```

The SMS message contains the mobile face verification link and expires in 10 minutes.

### Banking Operations Implementation

Banking operations require an authenticated session. Implemented operations:

- Balance inquiry.
- Withdrawal.
- Deposit.
- Transfer.
- Transaction history.

Validation includes:

- Session must exist.
- Session must not be expired.
- Session stage must be `authenticated`.
- Account must exist.
- Frozen accounts are rejected.
- Withdrawal requires sufficient balance.
- Withdrawal has a single withdrawal limit of ₦150,000.
- Transfer requires recipient account and sufficient balance.

### Testing Summary

Test file:

```text
backend/tests/test_auth_flow.py
```

Current test result:

```text
28 passed
```

Tested areas:

- Voice cosine similarity.
- Voice verification helper using mocked embeddings.
- Voice embedding byte serialization.
- Face Euclidean distance.
- Face verification helper using mocked encodings.
- Face no-detection handling.
- Face encoding byte serialization.
- Multi-angle face encoding averaging.
- Rejection of mismatched face encoding dimensions.
- PIN hashing and verification.
- Session token uniqueness.
- Face token length.
- Expiry helper.
- JWT helper.
- SMS masking and development-mode send.
- Card number schema validation.
- Transaction request schema validation.

Missing tests:

- Full database-backed end-to-end authentication test.
- Twilio live SMS test.
- Browser UI tests.
- Real face image verification test.
- Real deployed Cloudflare/mobile test.
- Transaction atomicity test.

## Chapter Five: Summary, Conclusion, and Recommendation

### Suggested Chapter Focus

Chapter Five should summarize what was achieved, conclude whether the prototype met its aim, and recommend future improvements.

### Summary

The project successfully implements a web-based ATM authentication prototype using PIN verification and facial verification through a mobile SMS handoff. The backend verifies user credentials, creates temporary sessions, sends face-verification links, validates uploaded selfies, and unlocks ATM transaction features after successful authentication.

The system also supports multi-angle face enrollment. During registration, multiple face images can be uploaded, and their encodings are averaged into a single stored face template. This improves the quality of the stored reference compared to relying on only one face image.

Voice authentication was retained in the codebase but disabled by default, allowing the project to meet the new requirement without permanently deleting the voice work.

### Conclusion

The prototype demonstrates how ATM authentication can be strengthened by combining:

- PIN verification.
- Registered mobile phone access through SMS.
- Face biometric verification.
- Expiring session tokens.
- Authentication-stage tracking.

Although not production-ready, the system provides a functional proof of concept for a layered ATM authentication approach.

### Recommendations

Recommended future work:

1. Add liveness detection for face verification.
2. Add anti-spoofing measures against printed photos, replayed images, and screen captures.
3. Protect enrollment endpoints with admin/teller authentication.
4. Add rate limiting and account lockout after repeated failures.
5. Encrypt biometric templates at application level before database storage.
6. Add full end-to-end API tests with a test database.
7. Add frontend/browser automation tests.
8. Add formal biometric evaluation using a properly approved dataset.
9. Add stable deployment using a named Cloudflare Tunnel, VPS, or production hosting.
10. Integrate with real ATM hardware in future work.
11. Use database transactions for transfer debit/credit atomicity.
12. If voice is restored, calibrate the voice threshold and add phrase challenge-response.

## Final Methodology Statement

The implemented methodology is a prototype-based design and implementation of a multi-factor ATM authentication system. The system verifies the user's card and PIN, creates a temporary authentication session, sends a secure mobile face-verification link through SMS, and verifies the user's face through a mobile browser before granting ATM transaction access. Face enrollment is strengthened by accepting multiple face images from different angles and averaging their encodings into one stored biometric reference. Voice authentication remains in the codebase for optional future activation but is disabled in the current active workflow.

## Important Wording for the Thesis

Use:

> The implemented system uses PIN verification, SMS-based mobile handoff, and face biometric verification.

Do not say:

> The implemented system uses keystroke dynamics.

Do not say:

> The system has proven biometric accuracy of X%.

Unless you perform separate experiments, the repository does not contain those results.
