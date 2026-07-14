"""One-off: backfill Messenger conversations that predate the webhook going live.

Run: py -m app.kb.backfill_messenger
Reads DATABASE_URL / MESSENGER_PAGE_ACCESS_TOKEN from env (.env.backfill).
ponytail: no pagination past 100 conversations / 200 msgs each — this Page's
volume is small; add paging when a Page has more.
"""
import os, uuid, logging
from datetime import datetime, timezone
import httpx
from sqlalchemy.orm import Session

os.environ.setdefault("DATABASE_URL", os.environ.get("BACKFILL_DATABASE_URL", ""))

from app.models.db import engine, Customer, Conversation, Message, init_db

log = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com/v21.0"
PAGE_ID = "1169985979542341"


def _upsert_customer(db: Session, psid: str, name: str) -> Customer:
    c = db.query(Customer).filter_by(external_user_id=psid, primary_channel="messenger").first()
    if not c:
        c = Customer(id=str(uuid.uuid4()), primary_channel="messenger", external_user_id=psid)
        db.add(c)
        db.flush()
    if name and not c.full_name:
        c.full_name = name
    return c


def _get_or_create_conversation(db: Session, customer: Customer, thread_id: str) -> Conversation:
    conv = db.query(Conversation).filter_by(external_thread_id=thread_id).first()
    if not conv:
        conv = Conversation(
            id=str(uuid.uuid4()), customer_id=customer.id, channel="messenger",
            external_thread_id=thread_id, status="open",
        )
        db.add(conv)
        db.flush()
    return conv


def backfill():
    token = os.environ["MESSENGER_PAGE_ACCESS_TOKEN"]
    init_db()
    added_msgs = added_customers = 0

    with httpx.Client(timeout=30) as http, Session(engine) as db:
        convs = http.get(f"{GRAPH}/{PAGE_ID}/conversations", params={
            "access_token": token, "fields": "participants,updated_time", "limit": 100,
        }).json().get("data", [])

        for conv in convs:
            others = [p for p in conv["participants"]["data"] if p["id"] != PAGE_ID]
            if not others:
                continue
            psid, name = others[0]["id"], others[0].get("name", "")

            customer = _upsert_customer(db, psid, name)
            if customer.id and db.new:
                pass  # flush already happened in upsert
            conversation = _get_or_create_conversation(db, customer, conv["id"])

            detail = http.get(f"{GRAPH}/{conv['id']}", params={
                "access_token": token,
                "fields": "messages.limit(200){message,from,created_time,id}",
            }).json()

            msgs = detail.get("messages", {}).get("data", [])
            last_ts = None
            for m in reversed(msgs):  # oldest first
                ext_id = m["id"]
                if db.query(Message).filter_by(external_message_id=ext_id).first():
                    continue
                ts = datetime.fromisoformat(m["created_time"].replace("+0000", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
                is_page = m.get("from", {}).get("id") == PAGE_ID
                db.add(Message(
                    id=str(uuid.uuid4()), conversation_id=conversation.id,
                    external_message_id=ext_id, channel="messenger",
                    direction="outbound" if is_page else "inbound",
                    sender_type="agent" if is_page else "customer",
                    content_text=m.get("message", ""), message_timestamp=ts,
                    delivery_status="sent",
                ))
                last_ts = ts
                added_msgs += 1
            if last_ts:
                conversation.last_message_at = last_ts
            db.commit()
            added_customers += 1
            log.info("Backfilled %s (%s): %d messages", name, psid, len(msgs))

    print(f"Done. Customers touched: {added_customers}, new messages: {added_msgs}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backfill()
