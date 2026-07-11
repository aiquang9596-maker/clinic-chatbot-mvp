"""WhatsApp Cloud API webhook — verify + receive messages."""
import hashlib, hmac, logging, os
from fastapi import APIRouter, Request, Response, HTTPException, Query

router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])
log = logging.getLogger(__name__)


def _clean_env(name: str) -> str:
    """Read env var and strip surrounding quotes/spaces from platform UIs."""
    return os.getenv(name, "").strip().strip('"').strip("'")


VERIFY_TOKEN = _clean_env("WHATSAPP_VERIFY_TOKEN")
APP_SECRET   = _clean_env("WHATSAPP_APP_SECRET")


@router.get("")
async def verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
):
    """Meta webhook verification challenge."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(403, "Invalid verify token")


@router.post("")
async def receive(request: Request):
    """Receive inbound WhatsApp events — ack immediately, process async."""
    # 1. Verify signature (optional but recommended)
    if APP_SECRET:
        sig = request.headers.get("X-Hub-Signature-256", "")
        body = await request.body()
        expected = "sha256=" + hmac.new(
            APP_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(403, "Bad signature")
    else:
        body = await request.body()

    payload = await request.json() if not APP_SECRET else __import__("json").loads(body)

    # 2. Parse & enqueue (fire-and-forget)
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                log.info("WA inbound: %s from %s", msg.get("id"), msg.get("from"))
                # ponytail: enqueue to background worker; add when volume grows
                _handle_inbound_message("whatsapp", msg, value)

    return {"status": "ok"}


def _handle_inbound_message(channel: str, msg: dict, value: dict):
    """Normalize and store. Expand here or delegate to message_service."""
    from app.services import message_service
    message_service.ingest(channel=channel, raw_msg=msg, raw_value=value)
