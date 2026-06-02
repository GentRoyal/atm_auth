"""
services/sms_service.py
Send OTP/auth links via Africa's Talking or Twilio.
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
    if provider == "africastalking":
        return await _send_via_africastalking(phone_number, message)
    if provider == "twilio":
        return await _send_via_twilio(phone_number, message)

    logger.error("Unsupported SMS_PROVIDER=%s", settings.SMS_PROVIDER)
    return False


async def _send_via_africastalking(phone: str, message: str) -> bool:
    try:
        if not settings.AT_API_KEY:
            logger.error("Africa's Talking credentials are not configured.")
            return False
        import africastalking
        africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
        sms = africastalking.SMS
        response = sms.send(message, [phone])
        logger.info(f"Africa's Talking response: {response}")
        # Check status
        recipients = response.get("SMSMessageData", {}).get("Recipients", [])
        if recipients:
            status = recipients[0].get("status", "")
            return status.lower() in ("success", "sent")
        return False
    except Exception as e:
        logger.error(f"Africa's Talking send failed: {e}")
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


def get_masked_phone(phone: str) -> str:
    return _mask_phone(phone)
