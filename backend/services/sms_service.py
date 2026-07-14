"""
services/sms_service.py
Send OTP/auth links via Twilio or development logging.
"""
import logging
from backend.config import settings

logger = logging.getLogger(__name__)


def _mask_phone(phone: str) -> str:
    """Mask middle digits: +2348012345678 → +234******678"""
    if len(phone) < 7:
        return phone
    return phone[:4] + "*" * (len(phone) - 7) + phone[-3:]


async def send_auth_link(phone_number: str, auth_url: str, user_name: str) -> bool:
    """
    Send the face-auth link to the user's phone number.
    Returns True if sent successfully.
    """
    first_name = (user_name or "Customer").split()[0]
    message = (
        f"SecureBank ATM face verification for {first_name}:\n"
        f"{auth_url}\n"
        "Expires in 10 minutes."
    )

    provider = settings.SMS_PROVIDER.lower()

    if provider in ("dev", "console", "log"):
        logger.info(f"[DEV SMS] To {phone_number}:\n{message}")
        return True
    if provider == "twilio":
        return await _send_via_twilio(phone_number, message)
    if provider == "termii":
        return await _send_via_termii(phone_number, message)
    if provider in ("smsto", "sms_to", "sms.to"):
        return await _send_via_smsto(phone_number, message)

    logger.error("Unsupported SMS_PROVIDER=%s", settings.SMS_PROVIDER)
    return False


async def _send_via_twilio(phone: str, message: str) -> bool:
    try:
        if not all((settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_FROM_NUMBER)):
            logger.error("Twilio credentials are not configured.")
            return False
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=message,
            from_=settings.TWILIO_FROM_NUMBER,
            to=phone
        )
        logger.info(f"Twilio SID: {msg.sid}, status: {msg.status}")
        return msg.status in ("queued", "sent", "delivered")
    except Exception as e:
        logger.error(f"Twilio send failed: {e}")
        return False


def _format_termii_phone(phone: str) -> str:
    return phone.strip().replace(" ", "").replace("-", "").lstrip("+")


async def _send_via_termii(phone: str, message: str) -> bool:
    try:
        if not all((settings.TERMII_API_KEY, settings.TERMII_SENDER_ID)):
            logger.error("Termii credentials are not configured.")
            return False

        import httpx

        base_url = settings.TERMII_BASE_URL.rstrip("/")
        payload = {
            "to": _format_termii_phone(phone),
            "from": settings.TERMII_SENDER_ID,
            "sms": message,
            "type": "plain",
            "channel": settings.TERMII_CHANNEL,
            "api_key": settings.TERMII_API_KEY,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(f"{base_url}/api/sms/send", json=payload)
            response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            data = {}

        logger.info("Termii SMS accepted for %s: %s", _mask_phone(phone), data)
        return True
    except Exception as e:
        logger.error(f"Termii send failed: {e}")
        return False




def _format_smsto_phone(phone: str) -> str:
    clean = phone.strip().replace(" ", "").replace("-", "")
    if clean.startswith("+"):
        return clean
    return f"+{clean}"


async def _send_via_smsto(phone: str, message: str) -> bool:
    try:
        if not all((settings.SMSTO_API_KEY, settings.SMSTO_SENDER_ID)):
            logger.error("SMS.to credentials are not configured.")
            return False

        import httpx

        base_url = settings.SMSTO_BASE_URL.rstrip("/")
        payload = {
            "to": _format_smsto_phone(phone),
            "message": message,
            "sender_id": settings.SMSTO_SENDER_ID,
        }
        headers = {
            "Authorization": f"Bearer {settings.SMSTO_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(f"{base_url}/sms/send", json=payload, headers=headers)
            response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            data = {}

        logger.info("SMS.to SMS accepted for %s: %s", _mask_phone(phone), data)
        return True
    except Exception as e:
        logger.error(f"SMS.to send failed: {e}")
        return False

def get_masked_phone(phone: str) -> str:
    return _mask_phone(phone)



