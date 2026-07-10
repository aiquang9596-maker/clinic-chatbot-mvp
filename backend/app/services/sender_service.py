"""Outbound message sender — WhatsApp Cloud API + Messenger Send API."""
import os, httpx, logging

log = logging.getLogger(__name__)

WA_TOKEN  = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WA_PHONE  = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
MS_TOKEN  = os.getenv("MESSENGER_PAGE_ACCESS_TOKEN", "")


def send(channel: str, recipient_id: str, text: str) -> str | None:
    """Send a text message. Returns external message ID or None on error."""
    if channel == "whatsapp":
        return _send_whatsapp(recipient_id, text)
    elif channel == "messenger":
        return _send_messenger(recipient_id, text)
    log.error("Unknown channel: %s", channel)
    return None


def _send_whatsapp(to: str, text: str) -> str | None:
    url = f"https://graph.facebook.com/v20.0/{WA_PHONE}/messages"
    try:
        r = httpx.post(
            url,
            headers={"Authorization": f"Bearer {WA_TOKEN}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text},
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("messages", [{}])[0].get("id")
    except Exception as e:
        log.error("WhatsApp send failed: %s", e)
        return None


def _send_messenger(psid: str, text: str) -> str | None:
    url = "https://graph.facebook.com/v20.0/me/messages"
    try:
        r = httpx.post(
            url,
            params={"access_token": MS_TOKEN},
            json={"recipient": {"id": psid}, "message": {"text": text}},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("message_id")
    except Exception as e:
        log.error("Messenger send failed: %s", e)
        return None
