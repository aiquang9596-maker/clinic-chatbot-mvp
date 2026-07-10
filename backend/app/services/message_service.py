"""Core message ingestion, routing, AI draft pipeline."""
import uuid, logging, os, httpx
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.db import engine, Customer, Conversation, Message, AuditLog

log = logging.getLogger(__name__)

# ── Safety: intents blocked from auto-reply ──────────────────────────────────
BLOCKED_INTENTS = {
    "medical_candidacy", "drug_medication", "complication_postop",
    "complaint_refund", "guarantee_promise", "price_final",
    "diagnosis", "emergency", "revision_request",
}

AUTO_REPLY_ENABLED = False   # master kill-switch; toggled via UI or env


def ingest(channel: str, raw_msg: dict, raw_value: dict):
    """Normalize inbound event, dedupe, persist, trigger pipeline."""
    # Dedupe by external message ID
    ext_id = raw_msg.get("id") or raw_msg.get("mid")
    if not ext_id:
        log.warning("Message without external ID; skipping")
        return

    with Session(engine) as db:
        existing = db.query(Message).filter_by(external_message_id=ext_id).first()
        if existing:
            log.debug("Duplicate message %s; skipping", ext_id)
            return

        # Normalize
        sender_id, text, ts = _extract(channel, raw_msg, raw_value)

        # Upsert customer
        customer = _upsert_customer(db, channel, sender_id)

        # Get or create conversation
        conversation = _get_or_create_conversation(db, customer, channel)

        # Store message
        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            external_message_id=ext_id,
            channel=channel,
            direction="inbound",
            sender_type="customer",
            content_text=text,
            message_timestamp=ts,
            risk_level="unknown",
        )
        db.add(msg)
        db.add(AuditLog(
            id=str(uuid.uuid4()),
            message_id=msg.id,
            conversation_id=conversation.id,
            event_type="inbound",
            actor="system",
            detail={"channel": channel, "ext_id": ext_id},
        ))
        conversation.last_message_at = ts
        db.commit()
        db.refresh(msg)

        # Trigger AI pipeline (if not in human takeover)
        if not conversation.human_takeover:
            _run_ai_pipeline(db, conversation, msg)


def _extract(channel, raw_msg, raw_value):
    """Return (sender_id, text, timestamp)."""
    if channel == "whatsapp":
        sender_id = raw_value.get("contacts", [{}])[0].get("wa_id", "unknown")
        text = (raw_msg.get("text") or {}).get("body", "")
        ts_epoch = raw_msg.get("timestamp")
        ts = datetime.utcfromtimestamp(int(ts_epoch)) if ts_epoch else datetime.utcnow()
    else:  # messenger
        sender_id = (raw_value.get("sender") or {}).get("id", "unknown")
        text = (raw_msg.get("text") or "")
        ts = datetime.utcnow()
    return sender_id, text, ts


def _fetch_messenger_profile(psid: str) -> dict | None:
    """Fetch user profile from Messenger Graph API. Returns None on error."""
    token = os.getenv("MESSENGER_PAGE_ACCESS_TOKEN", "")
    if not token:
        return None
    try:
        r = httpx.get(
            f"https://graph.facebook.com/v20.0/{psid}",
            params={
                "fields": "first_name,last_name,name",
                "access_token": token,
            },
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.warning("Messenger profile fetch failed for %s: %s", psid, e)
    return None


def _upsert_customer(db: Session, channel: str, external_id: str) -> Customer:
    customer = db.query(Customer).filter_by(
        external_user_id=external_id, primary_channel=channel
    ).first()
    if not customer:
        customer = Customer(
            id=str(uuid.uuid4()),
            primary_channel=channel,
            external_user_id=external_id,
        )
        db.add(customer)
        db.flush()

    # Attempt to fill customer name from profile if blank
    if not customer.full_name:
        profile = _fetch_messenger_profile(external_id) if channel == "messenger" else None
        if profile:
            customer.full_name = profile.get("name") or profile.get("first_name") or customer.full_name

    return customer


def _get_or_create_conversation(db: Session, customer: Customer, channel: str) -> Conversation:
    conv = (
        db.query(Conversation)
        .filter_by(customer_id=customer.id, channel=channel, status="open")
        .order_by(Conversation.created_at.desc())
        .first()
    )
    if not conv:
        conv = Conversation(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            channel=channel,
            status="open",
        )
        db.add(conv)
        db.flush()
    return conv


def _run_ai_pipeline(db: Session, conv: Conversation, msg: Message):
    """Classify → retrieve KB → draft → decide. Errors here must NOT crash ingest."""
    try:
        from app.services import ai_service, kb_service
        history = _get_recent_history(db, conv.id, limit=10)
        intent, risk = ai_service.classify(msg.content_text, history)
        msg.risk_level = risk
        if risk == "emergency":
            _force_human_takeover(db, conv, reason="emergency risk detected")
            return

        sources = kb_service.retrieve(msg.content_text, intent, service=conv.customer.service_interest)
        draft, confidence = ai_service.draft_reply(msg.content_text, history, sources)

        # Auto-reply only if explicitly enabled AND intent is safe AND confidence high
        if (
            AUTO_REPLY_ENABLED
            and intent not in BLOCKED_INTENTS
            and risk == "low"
            and confidence >= float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.85"))
        ):
            _send_and_log(db, conv, msg, draft, "auto", confidence, sources)
        else:
            # Just save the suggestion for the operator UI
            _save_suggestion(db, conv, msg, draft, confidence, sources)
    except Exception as e:
        log.exception("AI pipeline failed for message %s: %s", msg.id, e)


def _get_recent_history(db: Session, conv_id: str, limit: int = 10):
    return (
        db.query(Message)
        .filter_by(conversation_id=conv_id)
        .order_by(Message.message_timestamp.desc())
        .limit(limit)
        .all()
    )


def _force_human_takeover(db: Session, conv: Conversation, reason: str):
    conv.human_takeover = True
    conv.escalation_level = "L4"
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        event_type="takeover",
        actor="system",
        detail={"reason": reason},
    ))
    db.flush()
    log.warning("Human takeover forced for conv %s: %s", conv.id, reason)


def _save_suggestion(db, conv, msg, draft, confidence, sources):
    """Store AI suggestion as a draft message (not sent)."""
    db.add(Message(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        external_message_id="draft:" + msg.id,
        channel=msg.channel,
        direction="outbound",
        sender_type="ai",
        content_text=draft,
        message_timestamp=datetime.utcnow(),
        delivery_status="draft",
        ai_generated=True,
        ai_confidence=confidence,
        source_ids=[s.get("snippet_id") for s in (sources or [])],
        risk_level=msg.risk_level,
    ))
    db.flush()


def _send_and_log(db, conv, msg, draft, mode, confidence, sources):
    import os
    from app.services import sender_service
    sent_id = sender_service.send(channel=conv.channel, recipient_id=conv.customer.external_user_id, text=draft)
    db.add(Message(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        external_message_id=sent_id or ("auto:" + msg.id),
        channel=msg.channel,
        direction="outbound",
        sender_type="ai",
        content_text=draft,
        message_timestamp=datetime.utcnow(),
        delivery_status="sent",
        ai_generated=True,
        ai_confidence=confidence,
        source_ids=[s.get("snippet_id") for s in (sources or [])],
        risk_level=msg.risk_level,
    ))
    db.flush()
