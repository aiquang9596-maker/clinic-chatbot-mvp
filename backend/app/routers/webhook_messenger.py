"""Facebook Messenger Platform webhook — verify + receive messages."""
import hashlib, hmac, logging, os
from fastapi import APIRouter, Request, Response, HTTPException, Query

router = APIRouter(prefix="/webhook/messenger", tags=["messenger"])
log = logging.getLogger(__name__)


def _clean_env(name: str) -> str:
    """Read env var and strip surrounding quotes/spaces from platform UIs."""
    return os.getenv(name, "").strip().strip('"').strip("'")


VERIFY_TOKEN = _clean_env("MESSENGER_VERIFY_TOKEN")
APP_SECRET   = _clean_env("MESSENGER_APP_SECRET")


@router.get("")
async def verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(403, "Invalid verify token")


@router.post("")
async def receive(request: Request):
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

    if payload.get("object") != "page":
        return {"status": "ignored"}

    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            if "message" in event:
                log.info("Messenger inbound mid: %s from psid: %s",
                         event["message"].get("mid"), event["sender"]["id"])
                from app.services import message_service
                message_service.ingest(channel="messenger", raw_msg=event["message"],
                                       raw_value=event)

    return {"status": "ok"}
