"""
routers/atm.py
ATM-side endpoints:
  POST /atm/insert-card   – validate card + PIN, create session
  POST /atm/verify-voice  – compare live voice to enrolled embedding
  POST /atm/send-sms      – send face-auth link via SMS
  GET  /atm/session/{id}  – poll session status (ATM screen)
"""
import uuid
import logging
import base64
import io
from urllib.parse import urlencode
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from backend.database import database, users, auth_sessions, auth_logs
from backend.models.schemas import (
    CardInsertRequest, CardInsertResponse,
    VoiceVerifyResponse, SMSSentResponse,
    SessionStatusResponse, SessionStage
)
from backend.services.voice_service import verify_voice
from backend.services.sms_service import send_auth_link, get_masked_phone
from backend.utils.security import (
    verify_pin, generate_session_token, generate_face_token, session_expiry, is_expired
)
from backend.config import settings

router = APIRouter(prefix="/atm", tags=["ATM"])
logger = logging.getLogger(__name__)


def _qr_code_data_url(value: str) -> str | None:
    try:
        import qrcode

        img = qrcode.make(value)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception as exc:
        logger.warning("Could not generate face-link QR code: %s", exc)
        return None


# ── Helpers ──────────────────────────────────────────────

async def _log_event(session_id, user_id, event, success, score=None, detail=None, ip=None):
    await database.execute(
        auth_logs.insert().values(
            id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            event=event,
            success=success,
            score=score,
            detail=detail,
            ip_address=ip,
            created_at=datetime.now(timezone.utc),
        )
    )


# ── 1. Card Insertion ─────────────────────────────────────

@router.post("/insert-card", response_model=CardInsertResponse)
async def insert_card(request: Request, body: CardInsertRequest):
    """
    Validate ATM card number + PIN.
    Creates an auth session and returns session_id.
    """
    try:
        user = await database.fetch_one(
            users.select().where(users.c.card_number == body.card_number)
        )
    except Exception as exc:
        logger.exception("Could not look up card number during insert-card.")
        raise HTTPException(status_code=503, detail="Database lookup failed. Check backend database configuration and schema.") from exc

    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="Card not recognized or account inactive.")

    # Verify PIN
    if not verify_pin(body.pin, user["pin_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect PIN.")

    # Create session
    session_id = str(uuid.uuid4())
    session_token = generate_session_token()

    try:
        await database.execute(
            auth_sessions.insert().values(
                id=session_id,
                user_id=str(user["id"]),
                card_number=body.card_number,
                session_token=session_token,
                stage=SessionStage.card_inserted if settings.ENABLE_VOICE_AUTH else SessionStage.voice_verified,
                expires_at=session_expiry(),
                ip_address=str(request.client.host),
                user_agent=request.headers.get("user-agent"),
                created_at=datetime.now(timezone.utc),
            )
        )

        await _log_event(session_id, str(user["id"]), "card_inserted", True, ip=str(request.client.host))
        if not settings.ENABLE_VOICE_AUTH:
            await _log_event(session_id, str(user["id"]), "voice_skipped", True, detail="Voice authentication disabled by configuration")
    except Exception as exc:
        logger.exception("Could not create auth session during insert-card.")
        raise HTTPException(status_code=503, detail="Could not create authentication session. Check backend database schema.") from exc

    return CardInsertResponse(
        session_id=session_id,
        message=(
            "Card accepted. Please speak your passphrase into the microphone."
            if settings.ENABLE_VOICE_AUTH
            else "Card accepted. Voice authentication is disabled; sending face verification link."
        ),
        stage=SessionStage.card_inserted if settings.ENABLE_VOICE_AUTH else SessionStage.voice_verified,
    )


# ── 2. Voice Verification ─────────────────────────────────

@router.post("/verify-voice", response_model=VoiceVerifyResponse)
async def verify_voice_endpoint(
    request: Request,
    session_id: str = Form(...),
    audio: UploadFile = File(..., description="WAV/OGG audio of user speaking"),
):
    """
    Receive live voice recording, compare against stored embedding.
    On success, update session stage to voice_verified.
    """
    if not settings.ENABLE_VOICE_AUTH:
        raise HTTPException(status_code=404, detail="Voice authentication is disabled.")

    session = await database.fetch_one(
        auth_sessions.select().where(auth_sessions.c.id == session_id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if is_expired(session["expires_at"]):
        await database.execute(
            auth_sessions.update()
            .where(auth_sessions.c.id == session_id)
            .values(stage=SessionStage.expired)
        )
        raise HTTPException(status_code=410, detail="Session expired.")
    if session["stage"] != SessionStage.card_inserted:
        raise HTTPException(status_code=400, detail=f"Invalid stage: {session['stage']}")

    # Load enrolled voice sample
    user = await database.fetch_one(
        users.select().where(users.c.id == session["user_id"])
    )
    if not user or not user["voice_sample"]:
        raise HTTPException(status_code=400, detail="No enrolled voice sample for this user.")

    audio_bytes = await audio.read()
    logger.info(
        "Voice upload: filename=%s content_type=%s size=%s magic=%s",
        audio.filename,
        audio.content_type,
        len(audio_bytes),
        audio_bytes[:16].hex(" "),
    )
    passed, score = verify_voice(
        enrolled_embedding_bytes=bytes(user["voice_sample"]),
        live_audio_bytes=audio_bytes,
        threshold=settings.VOICE_SIMILARITY_THRESHOLD,
    )

    if passed:
        await database.execute(
            auth_sessions.update()
            .where(auth_sessions.c.id == session_id)
            .values(stage=SessionStage.voice_verified, voice_score=score,
                    voice_verified_at=datetime.now(timezone.utc))
        )
        await _log_event(session_id, str(user["id"]), "voice_attempt", True, score=score)
        return VoiceVerifyResponse(
            session_id=session_id, success=True, score=score,
            message="Voice verified ✓ Sending SMS link to your registered number.",
            stage=SessionStage.voice_verified,
        )
    else:
        await _log_event(session_id, str(user["id"]), "voice_attempt", False, score=score)
        raise HTTPException(status_code=401, detail=f"Voice not recognized (score={score:.2f}). Please try again.")


# ── 3. Send SMS Link ──────────────────────────────────────

@router.post("/send-sms", response_model=SMSSentResponse)
async def send_sms_link(request: Request, session_id: str = Form(...)):
    """
    Generate a one-time face-auth link and send it via SMS.
    """
    session = await database.fetch_one(
        auth_sessions.select().where(auth_sessions.c.id == session_id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if is_expired(session["expires_at"]):
        raise HTTPException(status_code=410, detail="Session expired.")
    allowed_stages = (SessionStage.voice_verified,)
    if not settings.ENABLE_VOICE_AUTH:
        allowed_stages = (SessionStage.voice_verified, SessionStage.card_inserted)

    if session["stage"] not in allowed_stages:
        raise HTTPException(status_code=400, detail="Voice must be verified first.")

    user = await database.fetch_one(
        users.select().where(users.c.id == session["user_id"])
    )

    face_token = generate_face_token()
    auth_url = f"{settings.face_link_base_url}/mobile/face-auth?{urlencode({'token': face_token})}"

    # Send SMS, but do not block the QR fallback if the provider is down.
    sent = await send_auth_link(user["phone_number"], auth_url, user["full_name"])
    if not sent:
        logger.warning("SMS failed for session %s; continuing with QR fallback.", session_id)

    await database.execute(
        auth_sessions.update()
        .where(auth_sessions.c.id == session_id)
        .values(
            stage=SessionStage.sms_sent,
            face_token=face_token,
            sms_sent_at=datetime.now(timezone.utc) if sent else None,
        )
    )

    await _log_event(
        session_id,
        str(user["id"]),
        "sms_sent",
        sent,
        detail=None if sent else "SMS provider failed; QR fallback shown",
    )

    return SMSSentResponse(
        session_id=session_id,
        message=(
            "Authentication link sent to your registered phone number."
            if sent
            else "SMS could not be sent. Scan the QR code to continue."
        ),
        phone_masked=get_masked_phone(user["phone_number"]),
        stage=SessionStage.sms_sent,
        sms_sent=sent,
        auth_url=auth_url,
        qr_code_data_url=_qr_code_data_url(auth_url),
    )


# ── 4. Session Status Polling ─────────────────────────────

@router.get("/session/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str):
    """
    ATM polls this to know when face verification is done.
    """
    session = await database.fetch_one(
        auth_sessions.select().where(auth_sessions.c.id == session_id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    stage = session["stage"]
    if is_expired(session["expires_at"]) and stage not in (SessionStage.authenticated, SessionStage.expired):
        stage = SessionStage.expired
        await database.execute(
            auth_sessions.update()
            .where(auth_sessions.c.id == session_id)
            .values(stage=SessionStage.expired)
        )

    user_name = None
    if session["user_id"]:
        user = await database.fetch_one(
            users.select().where(users.c.id == session["user_id"])
        )
        if user:
            user_name = user["full_name"]

    return SessionStatusResponse(
        session_id=session_id,
        stage=stage,
        expires_at=session["expires_at"],
        user_name=user_name,
    )
