"""
tests/test_auth_flow.py
Integration tests for the full ATM authentication flow.
Run with: pytest tests/ -v
"""
import pytest
import asyncio
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

# ── Import app after mocking DB ───────────────────────────
# We patch the database before importing the app so tests don't need a real DB


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ── Unit Tests: Voice Service ─────────────────────────────

class TestVoiceService:
    def test_cosine_similarity_identical(self):
        from backend.services.voice_service import cosine_similarity
        v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-5)

    def test_cosine_similarity_orthogonal(self):
        from backend.services.voice_service import cosine_similarity
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-5)

    def test_cosine_similarity_opposite(self):
        from backend.services.voice_service import cosine_similarity
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0], dtype=np.float32)
        assert cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-5)

    def test_verify_voice_pass(self):
        from backend.services.voice_service import verify_voice, embedding_to_bytes
        enrolled = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        live_similar = np.array([0.98, 0.1, 0.05], dtype=np.float32)

        with patch("backend.services.voice_service.extract_embedding", return_value=live_similar):
            passed, score = verify_voice(
                enrolled_embedding_bytes=embedding_to_bytes(enrolled),
                live_audio_bytes=b"fake_audio",
                threshold=0.75,
            )
        assert passed is True
        assert score > 0.75

    def test_verify_voice_fail(self):
        from backend.services.voice_service import verify_voice, embedding_to_bytes
        enrolled = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        live_different = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        with patch("backend.services.voice_service.extract_embedding", return_value=live_different):
            passed, score = verify_voice(
                enrolled_embedding_bytes=embedding_to_bytes(enrolled),
                live_audio_bytes=b"fake_audio",
                threshold=0.75,
            )
        assert passed is False
        assert score < 0.75

    def test_embedding_roundtrip(self):
        from backend.services.voice_service import embedding_to_bytes, bytes_to_embedding
        original = np.random.rand(192).astype(np.float32)
        restored = bytes_to_embedding(embedding_to_bytes(original))
        np.testing.assert_array_almost_equal(original, restored)


# ── Unit Tests: Face Service ──────────────────────────────

class TestFaceService:
    def test_euclidean_distance_identical(self):
        from backend.services.face_service import euclidean_distance
        v = np.random.rand(128)
        assert euclidean_distance(v, v) == pytest.approx(0.0, abs=1e-10)

    def test_euclidean_distance_known(self):
        from backend.services.face_service import euclidean_distance
        a = np.array([0.0, 0.0])
        b = np.array([3.0, 4.0])
        assert euclidean_distance(a, b) == pytest.approx(5.0, abs=1e-5)

    def test_verify_face_pass(self):
        from backend.services.face_service import verify_face, encoding_to_bytes
        enrolled = np.zeros(128, dtype=np.float64)
        # Close encoding (distance < threshold)
        live_close = np.ones(128, dtype=np.float64) * 0.01

        with patch("backend.services.face_service.extract_face_encoding", return_value=live_close):
            passed, dist = verify_face(
                enrolled_encoding_bytes=encoding_to_bytes(enrolled),
                live_image_bytes=b"fake_image",
                threshold=0.55,
            )
        assert passed is True
        assert dist <= 0.55

    def test_verify_face_fail(self):
        from backend.services.face_service import verify_face, encoding_to_bytes
        enrolled = np.zeros(128, dtype=np.float64)
        live_far = np.ones(128, dtype=np.float64)   # distance = sqrt(128) ≈ 11.3

        with patch("backend.services.face_service.extract_face_encoding", return_value=live_far):
            passed, dist = verify_face(
                enrolled_encoding_bytes=encoding_to_bytes(enrolled),
                live_image_bytes=b"fake_image",
                threshold=0.55,
            )
        assert passed is False
        assert dist > 0.55

    def test_verify_face_no_face_detected(self):
        from backend.services.face_service import verify_face, encoding_to_bytes
        enrolled = np.zeros(128, dtype=np.float64)

        with patch("backend.services.face_service.extract_face_encoding", return_value=None):
            passed, dist = verify_face(
                enrolled_encoding_bytes=encoding_to_bytes(enrolled),
                live_image_bytes=b"blank_image",
                threshold=0.55,
            )
        assert passed is False
        assert dist == pytest.approx(9.99)

    def test_encoding_roundtrip(self):
        from backend.services.face_service import encoding_to_bytes, bytes_to_encoding
        original = np.random.rand(128)
        restored = bytes_to_encoding(encoding_to_bytes(original))
        np.testing.assert_array_almost_equal(original, restored)

    def test_combine_face_encodings_averages_multiple_angles(self):
        from backend.services.face_service import combine_face_encodings
        front = np.zeros(128, dtype=np.float64)
        left = np.ones(128, dtype=np.float64)
        right = np.ones(128, dtype=np.float64) * 2

        combined = combine_face_encodings([front, left, right])

        assert combined.shape == (128,)
        np.testing.assert_array_almost_equal(combined, np.ones(128))

    def test_combine_face_encodings_rejects_dimension_mismatch(self):
        from backend.services.face_service import combine_face_encodings
        with pytest.raises(ValueError):
            combine_face_encodings([np.zeros(128), np.zeros(64)])


# ── Unit Tests: Security Utils ────────────────────────────

class TestSecurity:
    def test_pin_hash_and_verify(self):
        from backend.utils.security import hash_pin, verify_pin
        hashed = hash_pin("1234")
        assert verify_pin("1234", hashed) is True
        assert verify_pin("9999", hashed) is False

    def test_session_token_unique(self):
        from backend.utils.security import generate_session_token
        tokens = {generate_session_token() for _ in range(100)}
        assert len(tokens) == 100   # all unique

    def test_face_token_length(self):
        from backend.utils.security import generate_face_token
        token = generate_face_token(32)
        assert len(token) >= 32    # urlsafe_b64 is slightly longer

    def test_is_expired_past(self):
        from backend.utils.security import is_expired
        from datetime import datetime, timezone, timedelta
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert is_expired(past) is True

    def test_is_expired_future(self):
        from backend.utils.security import is_expired
        from datetime import datetime, timezone, timedelta
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        assert is_expired(future) is False

    def test_jwt_roundtrip(self):
        from backend.utils.security import create_jwt, decode_jwt
        payload = {"session_id": "abc-123", "sub": "user-456"}
        token = create_jwt(payload)
        decoded = decode_jwt(token)
        assert decoded["session_id"] == "abc-123"
        assert decoded["sub"] == "user-456"

    def test_jwt_expired_returns_none(self):
        from backend.utils.security import create_jwt, decode_jwt
        from datetime import timedelta
        token = create_jwt({"sub": "test"}, expires_delta=timedelta(seconds=-1))
        assert decode_jwt(token) is None


# ── Unit Tests: SMS Service ───────────────────────────────

class TestSMSService:
    def test_mask_phone_standard(self):
        from backend.services.sms_service import get_masked_phone
        assert get_masked_phone("+2348012345678") == "+234*******678"

    def test_mask_phone_short(self):
        from backend.services.sms_service import get_masked_phone
        # Short numbers shouldn't crash
        result = get_masked_phone("+123")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_send_auth_link_dev_mode(self, monkeypatch):
        """Dev mode (unknown provider) should return True without crashing."""
        from backend.services import sms_service
        monkeypatch.setattr(sms_service.settings, "SMS_PROVIDER", "dev")
        result = await sms_service.send_auth_link(
            "+2348012345678",
            "http://localhost:8000/mobile/face-auth?token=abc",
            "Ada Okonkwo"
        )
        assert result is True


# ── Schema Validation Tests ───────────────────────────────

class TestSchemas:
    def test_card_number_strips_spaces(self):
        from backend.models.schemas import CardInsertRequest
        req = CardInsertRequest(card_number="4111 1111 1111 1111", pin="1234")
        assert req.card_number == "4111111111111111"

    def test_card_number_invalid(self):
        from backend.models.schemas import CardInsertRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CardInsertRequest(card_number="ABCD-XXXX", pin="1234")

    def test_transaction_request_valid(self):
        from backend.models.schemas import TransactionRequest, TransactionType
        req = TransactionRequest(
            session_id="sess-123",
            type=TransactionType.withdrawal,
            amount=5000.0
        )
        assert req.amount == 5000.0

    def test_transaction_type_enum(self):
        from backend.models.schemas import TransactionType
        assert TransactionType.withdrawal == "withdrawal"
        assert TransactionType.balance_inquiry == "balance_inquiry"
