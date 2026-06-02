"""
utils/security.py
Token generation, JWT creation, PIN hashing and verification.
"""
import secrets
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from backend.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── PIN helpers ──────────────────────────────────────────

def hash_pin(pin: str) -> str:
    return pwd_context.hash(pin)


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    return pwd_context.verify(plain_pin, hashed_pin)


# ── Token helpers ─────────────────────────────────────────

def generate_session_token(length: int = 64) -> str:
    """Cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(length)


def generate_face_token(length: int = 32) -> str:
    """
    SMS-safe one-time token.

    Some SMS apps/carriers split clickable URLs around "_" or "-" in query
    values. A lowercase hex token avoids punctuation in the URL token.
    """
    return secrets.token_hex(length)


# ── JWT (optional, for API bearer auth) ──────────────────

def create_jwt(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ── Timing helpers ────────────────────────────────────────

def session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)


def is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expires_at
