"""
services/voice_service.py
Speaker verification using SpeechBrain ECAPA-TDNN embeddings.
Cosine similarity between enrolled embedding and live sample.
"""
import io
import numpy as np
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-load the model to avoid slow startup
_verification_model = None
MIN_AUDIO_BYTES = 1024


def _get_model():
    global _verification_model
    if _verification_model is None:
        try:
            from speechbrain.inference.speaker import SpeakerRecognition
            _verification_model = SpeakerRecognition.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=str(Path(tempfile.gettempdir()) / "speechbrain_models" / "ecapa"),
            )
            logger.info("SpeechBrain ECAPA-TDNN loaded.")
        except Exception as e:
            logger.error(f"Could not load SpeechBrain model: {e}")
            _verification_model = None
    return _verification_model


def extract_embedding(audio_bytes: bytes) -> np.ndarray | None:
    """
    Given raw audio bytes (WAV/OGG/MP3), return a 192-d speaker embedding.
    Returns None on failure.
    """
    if len(audio_bytes) < MIN_AUDIO_BYTES:
        logger.warning("Voice sample is too small to verify.")
        return None

    model = _get_model()
    if model is None:
        return _fallback_embedding(audio_bytes)

    try:
        import soundfile as sf
        import torch
        import torchaudio

        audio_io = io.BytesIO(audio_bytes)
        samples, sr = sf.read(audio_io, dtype="float32", always_2d=True)
        waveform = torch.from_numpy(samples.T)

        # Resample to 16 kHz if needed
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
            waveform = resampler(waveform)

        # Mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        embedding = model.encode_batch(waveform)
        return embedding.squeeze().detach().numpy()

    except Exception as e:
        logger.error(f"Embedding extraction failed: {e}")
        return None


def _fallback_embedding(audio_bytes: bytes) -> np.ndarray | None:
    """
    Deterministic fallback when torch is unavailable (CI / testing).
    Uses MFCC-based mean as a weak embedding.
    """
    try:
        import librosa
        audio_io = io.BytesIO(audio_bytes)
        y, sr = librosa.load(audio_io, sr=16000, mono=True)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
        return mfccs.mean(axis=1)   # shape (40,)
    except Exception as e:
        logger.error(f"Fallback embedding failed: {e}")
        return None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity in [-1, 1] range."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def verify_voice(
    enrolled_embedding_bytes: bytes,
    live_audio_bytes: bytes,
    threshold: float = 0.75
) -> tuple[bool, float]:
    """
    Compare stored embedding against live audio.
    Returns (passed: bool, score: float).
    """
    enrolled = np.frombuffer(enrolled_embedding_bytes, dtype=np.float32)
    live_embedding = extract_embedding(live_audio_bytes)

    if live_embedding is None:
        return False, 0.0

    if len(enrolled) != len(live_embedding):
        logger.warning(
            "Voice embedding dimension mismatch: enrolled=%s live=%s",
            len(enrolled),
            len(live_embedding),
        )
        return False, 0.0

    score = cosine_similarity(
        enrolled.astype(np.float32),
        live_embedding.astype(np.float32),
    )
    score = max(-1.0, min(1.0, score))

    passed = score >= threshold
    
    logger.info(f"Voice verification: score={score:.4f}, passed={passed}")
    return passed, round(score, 4)


def embedding_to_bytes(embedding: np.ndarray) -> bytes:
    return embedding.astype(np.float32).tobytes()


def bytes_to_embedding(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)
