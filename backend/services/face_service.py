"""
services/face_service.py
Face verification using dlib-based 128-d face encodings via face_recognition
when available. Lightweight deployments fall back to a Pillow/NumPy image
descriptor so Vercel does not need dlib or OpenCV.
Lower Euclidean distance = better match (threshold ~0.55 is strict, 0.6 is default).
"""
import io
import numpy as np
import logging
from PIL import Image

logger = logging.getLogger(__name__)


def decode_image(image_bytes: bytes) -> np.ndarray | None:
    """Convert image bytes (JPEG/PNG/WebP) to RGB numpy array."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return np.array(img)
    except Exception as e:
        logger.error(f"Image decode error: {e}")
        return None


def extract_face_encoding(image_bytes: bytes) -> np.ndarray | None:
    """
    Detect a face in the image and return its 128-d encoding.
    Returns None if no face detected or multiple faces found.
    """
    try:
        import face_recognition
        rgb_image = decode_image(image_bytes)
        if rgb_image is None:
            return None

        face_locations = face_recognition.face_locations(rgb_image, model="hog")

        if len(face_locations) == 0:
            logger.warning("No face detected in image.")
            return None

        if len(face_locations) > 1:
            logger.warning(f"Multiple faces detected ({len(face_locations)}). Using largest.")
            # Pick the largest face by bounding box area
            def area(loc):
                top, right, bottom, left = loc
                return (bottom - top) * (right - left)
            face_locations = [max(face_locations, key=area)]

        encodings = face_recognition.face_encodings(rgb_image, face_locations)
        if not encodings:
            return None

        return encodings[0]   # 128-d float64 array

    except ImportError:
        logger.error("face_recognition not installed. Using fallback.")
        return _fallback_face_encoding(image_bytes)
    except Exception as e:
        logger.error(f"Face encoding error: {e}")
        return None


def _fallback_face_encoding(image_bytes: bytes) -> np.ndarray | None:
    """
    Lightweight fallback when dlib/face_recognition is not available.
    This is a rough image descriptor for demos, not production face recognition.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        width, height = img.size
        if width < 32 or height < 32:
            return None

        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        crop = img.crop((left, top, left + side, top + side)).resize((16, 8))
        descriptor = np.asarray(crop, dtype=np.float64).flatten() / 255.0
        descriptor = descriptor - descriptor.mean()
        norm = np.linalg.norm(descriptor)
        if norm == 0:
            return None
        return descriptor / norm
    except Exception as e:
        logger.error(f"Fallback face encoding failed: {e}")
        return None


def euclidean_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a.astype(float) - b.astype(float)))


def verify_face(
    enrolled_encoding_bytes: bytes,
    live_image_bytes: bytes,
    threshold: float = 0.55
) -> tuple[bool, float]:
    """
    Compare stored face encoding against a live image.
    Returns (passed: bool, distance: float).
    Lower distance = better match.
    """
    enrolled = np.frombuffer(enrolled_encoding_bytes, dtype=np.float64)
    live_encoding = extract_face_encoding(live_image_bytes)

    if live_encoding is None:
        return False, 9.99

    min_dim = min(len(enrolled), len(live_encoding))
    distance = euclidean_distance(
        enrolled[:min_dim].astype(np.float64),
        live_encoding[:min_dim].astype(np.float64)
    )

    passed = distance <= threshold
    logger.info(f"Face verification: distance={distance:.4f}, passed={passed}")
    return passed, round(distance, 4)


def combine_face_encodings(encodings: list[np.ndarray]) -> np.ndarray:
    """
    Create one enrollment template from multiple face angles.
    The template is the arithmetic mean of same-sized face encodings.
    """
    if not encodings:
        raise ValueError("At least one face encoding is required.")

    first_dim = len(encodings[0])
    if any(len(encoding) != first_dim for encoding in encodings):
        raise ValueError("Face encodings must have matching dimensions.")

    return np.mean(np.vstack([encoding.astype(np.float64) for encoding in encodings]), axis=0)


def encoding_to_bytes(encoding: np.ndarray) -> bytes:
    return encoding.astype(np.float64).tobytes()


def bytes_to_encoding(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float64)
