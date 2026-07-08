"""
models/schemas.py  –  Pydantic request/response schemas
"""
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum


# ── Enums ────────────────────────────────────────────────

class SessionStage(str, Enum):
    card_inserted   = "card_inserted"
    voice_verified  = "voice_verified"
    sms_sent        = "sms_sent"
    face_verified   = "face_verified"
    authenticated   = "authenticated"
    expired         = "expired"
    failed          = "failed"


class TransactionType(str, Enum):
    withdrawal       = "withdrawal"
    deposit          = "deposit"
    transfer         = "transfer"
    balance_inquiry  = "balance_inquiry"


# ── ATM / Card Insertion ─────────────────────────────────

class CardInsertRequest(BaseModel):
    card_number: str
    pin: str                  # plain PIN, validated against hash server-side

    @field_validator("card_number")
    @classmethod
    def card_must_be_numeric(cls, v):
        if not v.replace(" ", "").isdigit():
            raise ValueError("Card number must be numeric")
        return v.replace(" ", "")


class CardInsertResponse(BaseModel):
    session_id: str
    message: str
    stage: SessionStage


# ── Voice Auth ───────────────────────────────────────────

class VoiceVerifyResponse(BaseModel):
    session_id: str
    success: bool
    score: float
    message: str
    stage: SessionStage


# ── SMS Link ─────────────────────────────────────────────

class SMSSentResponse(BaseModel):
    session_id: str
    message: str
    phone_masked: str          # e.g. "+234******678"
    stage: SessionStage
    sms_sent: bool = True
    auth_url: Optional[str] = None
    qr_code_data_url: Optional[str] = None


# ── Face Auth ────────────────────────────────────────────

class FaceVerifyResponse(BaseModel):
    session_id: str
    success: bool
    score: float
    message: str
    stage: SessionStage


# ── Session Status ───────────────────────────────────────

class SessionStatusResponse(BaseModel):
    session_id: str
    stage: SessionStage
    expires_at: datetime
    user_name: Optional[str] = None


# ── Transactions ─────────────────────────────────────────

class TransactionRequest(BaseModel):
    session_id: str
    type: TransactionType
    amount: Optional[float] = None
    recipient_account: Optional[str] = None
    description: Optional[str] = None


class TransactionResponse(BaseModel):
    transaction_id: str
    type: TransactionType
    amount: Optional[float]
    balance_after: Optional[float]
    status: str
    message: str
    created_at: datetime


# ── User Enrollment ──────────────────────────────────────

class EnrollUserRequest(BaseModel):
    full_name: str
    account_number: str
    phone_number: str
    card_number: str
    pin: str


class EnrollUserResponse(BaseModel):
    user_id: str
    message: str


# ── Generic ──────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
