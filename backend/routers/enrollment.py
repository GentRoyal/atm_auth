"""
routers/enrollment.py
Biometric enrollment endpoints (admin/teller use):
  POST /enroll/user           – create a new user
  POST /enroll/voice/{user_id} – upload and store voice embedding
  POST /enroll/face/{user_id}  – upload and store face encoding
"""
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File, Path
from backend.database import database, users, accounts
from backend.models.schemas import EnrollUserRequest, EnrollUserResponse
from backend.services.voice_service import extract_embedding, embedding_to_bytes
from backend.services.face_service import extract_face_encoding, combine_face_encodings, encoding_to_bytes
from backend.utils.security import hash_pin

router = APIRouter(prefix="/enroll", tags=["Enrollment"])
logger = logging.getLogger(__name__)


@router.post("/user", response_model=EnrollUserResponse)
async def create_user(body: EnrollUserRequest):
    """Create a new user account (teller/admin)."""
    existing = await database.fetch_one(
        users.select().where(users.c.card_number == body.card_number)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Card number already registered.")

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await database.execute(
        users.insert().values(
            id=user_id,
            full_name=body.full_name,
            account_number=body.account_number,
            phone_number=body.phone_number,
            card_number=body.card_number,
            pin_hash=hash_pin(body.pin),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )

    # Create default savings account
    await database.execute(
        accounts.insert().values(
            id=str(uuid.uuid4()),
            user_id=user_id,
            account_type="savings",
            balance=0.00,
            currency="NGN",
            is_frozen=False,
            created_at=now,
            updated_at=now,
        )
    )

    return EnrollUserResponse(user_id=user_id, message="User created successfully.")


@router.post("/voice/{user_id}")
async def enroll_voice(
    user_id: str = Path(...),
    audio: UploadFile = File(..., description="WAV/OGG recording of user's passphrase"),
):
    """
    Extract speaker embedding from audio and store it for the user.
    The user should read a fixed passphrase clearly.
    """
    user = await database.fetch_one(users.select().where(users.c.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    audio_bytes = await audio.read()
    logger.info(
        "Voice enrollment upload: filename=%s content_type=%s size=%s magic=%s",
        audio.filename,
        audio.content_type,
        len(audio_bytes),
        audio_bytes[:16].hex(" "),
    )
    embedding = extract_embedding(audio_bytes)

    if embedding is None:
        raise HTTPException(status_code=422, detail="Could not extract voice embedding. Check audio quality.")

    await database.execute(
        users.update()
        .where(users.c.id == user_id)
        .values(voice_sample=embedding_to_bytes(embedding), updated_at=datetime.now(timezone.utc))
    )

    return {"message": "Voice enrolled successfully.", "embedding_dim": len(embedding)}


@router.post("/face/{user_id}")
async def enroll_face(
    user_id: str = Path(...),
    image: UploadFile | None = File(None, description="Single JPEG/PNG photo of user's face"),
    images: list[UploadFile] | None = File(None, description="Multiple JPEG/PNG face photos from different angles"),
):
    """
    Detect faces in one or more photos, average their encodings, and store one
    enrollment template. For better coverage, upload front, slight-left, and
    slight-right face images using the "images" field.
    """
    user = await database.fetch_one(users.select().where(users.c.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    uploads = []
    if images:
        uploads.extend(images)
    if image:
        uploads.append(image)
    if not uploads:
        raise HTTPException(status_code=422, detail="Upload at least one clear face image.")

    encodings = []
    failed_images = []
    for index, upload in enumerate(uploads, start=1):
        image_bytes = await upload.read()
        encoding = extract_face_encoding(image_bytes)
        if encoding is None:
            failed_images.append(upload.filename or f"image_{index}")
            continue
        encodings.append(encoding)

    if not encodings:
        raise HTTPException(status_code=422, detail="No usable face detected. Use clear, well-lit face photos.")

    try:
        enrollment_template = combine_face_encodings(encodings)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await database.execute(
        users.update()
        .where(users.c.id == user_id)
        .values(face_encoding=encoding_to_bytes(enrollment_template), updated_at=datetime.now(timezone.utc))
    )

    return {
        "message": "Face enrolled successfully.",
        "encoding_dim": len(enrollment_template),
        "images_received": len(uploads),
        "valid_images": len(encodings),
        "failed_images": failed_images,
        "recommendation": "Use front, slight-left, and slight-right images for stronger enrollment coverage.",
    }

