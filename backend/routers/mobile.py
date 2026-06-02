"""
routers/mobile.py
Mobile-side endpoints:
  GET  /mobile/face-auth          – serve the face capture HTML page
  GET  /mobile/session-info       – return session info for the token
  POST /mobile/verify-face        – receive image, run face check, authenticate
"""
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse

from backend.database import database, users, auth_sessions, auth_logs
from backend.models.schemas import FaceVerifyResponse, SessionStage
from backend.services.face_service import verify_face
from backend.utils.security import is_expired
from backend.config import settings

router = APIRouter(prefix="/mobile", tags=["Mobile"])
logger = logging.getLogger(__name__)
NO_STORE_HEADERS = {"Cache-Control": "no-store, max-age=0"}


async def _log_event(session_id, user_id, event, success, score=None, detail=None):
    await database.execute(
        auth_logs.insert().values(
            id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            event=event,
            success=success,
            score=score,
            detail=detail,
            created_at=datetime.now(timezone.utc),
        )
    )


# ── 1. Serve Mobile Face-Auth Page ────────────────────────

@router.get("/face-auth", response_class=HTMLResponse)
async def face_auth_page(token: str = Query(...)):
    """
    User opens this link on their phone.
    Serve the face-capture HTML (reads from frontend/mobile/).
    """
    # Validate token exists
    session = await database.fetch_one(
        auth_sessions.select().where(auth_sessions.c.face_token == token)
    )
    if not session:
        return HTMLResponse("<h2>Invalid or expired link.</h2>", status_code=404, headers=NO_STORE_HEADERS)
    if is_expired(session["expires_at"]):
        return HTMLResponse("<h2>This link has expired. Please visit the ATM again.</h2>", status_code=410, headers=NO_STORE_HEADERS)
    if session["stage"] not in (SessionStage.sms_sent, SessionStage.authenticated):
        return HTMLResponse("<h2>This link is no longer valid.</h2>", status_code=400, headers=NO_STORE_HEADERS)

    # Read and inject token into HTML
    html_path = Path(__file__).resolve().parents[2] / "frontend" / "mobile" / "face_auth.html"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        html = html.replace("{{FACE_TOKEN}}", token)
        html = html.replace("{{API_BASE}}", "")
        return HTMLResponse(html, headers=NO_STORE_HEADERS)

    return HTMLResponse(f"<h2>Face auth page not found</h2>", status_code=500, headers=NO_STORE_HEADERS)


# ── 2. Session Info (called by mobile JS) ─────────────────

@router.get("/session-info")
async def session_info(token: str = Query(...)):
    session = await database.fetch_one(
        auth_sessions.select().where(auth_sessions.c.face_token == token)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Invalid token.")
    if is_expired(session["expires_at"]):
        await database.execute(
            auth_sessions.update()
            .where(auth_sessions.c.id == str(session["id"]))
            .values(stage=SessionStage.expired)
        )
        raise HTTPException(status_code=410, detail="Link expired.")

    user = await database.fetch_one(
        users.select().where(users.c.id == session["user_id"])
    )

    return {
        "stage": session["stage"],
        "expires_at": session["expires_at"].isoformat(),
        "user_name": user["full_name"].split()[0] if user else "User",
        "expired": is_expired(session["expires_at"]),
    }


# ── 3. Face Verification ──────────────────────────────────

@router.post("/verify-face", response_model=FaceVerifyResponse)
async def verify_face_endpoint(
    token: str = Form(...),
    image: UploadFile = File(..., description="JPEG/PNG selfie from phone camera"),
):
    """
    Receive a selfie image, compare against stored face encoding.
    On success, mark session as authenticated.
    """
    session = await database.fetch_one(
        auth_sessions.select().where(auth_sessions.c.face_token == token)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Invalid token.")
    if is_expired(session["expires_at"]):
        raise HTTPException(status_code=410, detail="Link expired. Please restart at the ATM.")
    if session["stage"] not in (SessionStage.sms_sent,):
        if session["stage"] == SessionStage.authenticated:
            raise HTTPException(status_code=400, detail="Already authenticated.")
        raise HTTPException(status_code=400, detail=f"Invalid session stage: {session['stage']}")

    user = await database.fetch_one(
        users.select().where(users.c.id == session["user_id"])
    )
    if not user or not user["face_encoding"]:
        raise HTTPException(status_code=400, detail="No enrolled face for this user.")

    image_bytes = await image.read()
    passed, distance = verify_face(
        enrolled_encoding_bytes=bytes(user["face_encoding"]),
        live_image_bytes=image_bytes,
        threshold=settings.FACE_SIMILARITY_THRESHOLD,
    )

    if passed:
        await database.execute(
            auth_sessions.update()
            .where(auth_sessions.c.id == str(session["id"]))
            .values(
                stage=SessionStage.authenticated,
                face_score=distance,
                face_verified_at=datetime.now(timezone.utc),
                authenticated_at=datetime.now(timezone.utc),
            )
        )
        await _log_event(str(session["id"]), str(user["id"]), "face_attempt", True, score=distance)
        return FaceVerifyResponse(
            session_id=str(session["id"]),
            success=True,
            score=distance,
            message="Face verified ✓ You may now proceed at the ATM.",
            stage=SessionStage.authenticated,
        )
    else:
        await _log_event(str(session["id"]), str(user["id"]), "face_attempt", False, score=distance)
        raise HTTPException(
            status_code=401,
            detail=f"Face not recognized (distance={distance:.3f}). Please try again in better lighting."
        )
