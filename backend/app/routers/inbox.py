"""Inbox API for local frontend."""
import uuid
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from app.models.db import engine, Conversation, Customer, Message, AuditLog
from app.services import sender_service, ai_service, kb_service

router = APIRouter(prefix="/api", tags=["inbox"])


class SendMessageBody(BaseModel):
    text: str


class SuggestBody(BaseModel):
    instruction: str = ""


def _serialize_conversation(conv, cust):
    return {
        "id": conv.id,
        "channel": conv.channel,
        "status": conv.status,
        "human_takeover": conv.human_takeover,
        "escalation_level": conv.escalation_level,
        "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
        "customer": {
            "id": cust.id,
            "name": cust.full_name or cust.external_user_id or "Unknown",
            "external_user_id": cust.external_user_id,
            "service_interest": cust.service_interest,
            "lead_status": cust.lead_status,
            "tags": cust.tags or [],
        },
    }


def _serialize_message(m):
    return {
        "id": m.id,
        "channel": m.channel,
        "direction": m.direction,
        "sender_type": m.sender_type,
        "content_text": m.content_text,
        "message_timestamp": m.message_timestamp.isoformat() if m.message_timestamp else None,
        "delivery_status": m.delivery_status,
        "ai_generated": m.ai_generated,
        "ai_confidence": m.ai_confidence,
        "risk_level": m.risk_level,
        "source_ids": m.source_ids or [],
    }


def _load_conversation(db: Session, conversation_id: str):
    row = (
        db.query(Conversation, Customer)
        .join(Customer, Conversation.customer_id == Customer.id)
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Conversation not found")
    return row


def _load_messages(db: Session, conversation_id: str):
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.message_timestamp.asc(), Message.created_at.asc())
        .all()
    )


@router.get("/conversations")
def list_conversations():
    with Session(engine) as db:
        rows = (
            db.query(Conversation, Customer)
            .join(Customer, Conversation.customer_id == Customer.id)
            .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
            .all()
        )
        return [_serialize_conversation(conv, cust) for conv, cust in rows]


@router.get("/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str):
    with Session(engine) as db:
        conv = db.get(Conversation, conversation_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        msgs = _load_messages(db, conversation_id)
        return [_serialize_message(m) for m in msgs]


@router.post("/conversations/{conversation_id}/send")
def send_message(conversation_id: str, body: SendMessageBody):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "Message text is required")

    with Session(engine) as db:
        conv, cust = _load_conversation(db, conversation_id)
        external_message_id = sender_service.send(
            channel=conv.channel,
            recipient_id=cust.external_user_id,
            text=text,
        )
        if not external_message_id:
            raise HTTPException(502, "Message send failed")

        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            external_message_id=external_message_id,
            channel=conv.channel,
            direction="outbound",
            sender_type="agent",
            content_text=text,
            message_timestamp=datetime.utcnow(),
            delivery_status="sent",
            ai_generated=False,
            risk_level="manual",
        )
        db.add(msg)
        db.add(AuditLog(
            id=str(uuid.uuid4()),
            message_id=msg.id,
            conversation_id=conv.id,
            event_type="send",
            actor="system",
            detail={"channel": conv.channel, "external_message_id": external_message_id},
        ))
        conv.last_message_at = msg.message_timestamp
        db.commit()
        return {"ok": True, "message_id": msg.id}


@router.post("/conversations/{conversation_id}/suggestions")
def get_suggestions(conversation_id: str, body: SuggestBody):
    with Session(engine) as db:
        conv, cust = _load_conversation(db, conversation_id)
        history = _load_messages(db, conversation_id)
        latest_inbound = next((m for m in reversed(history) if m.direction == "inbound" and m.content_text), None)
        if not latest_inbound:
            raise HTTPException(400, "No inbound customer message found")

        intent, risk = ai_service.classify(latest_inbound.content_text, history)
        sources = kb_service.retrieve(
            latest_inbound.content_text,
            intent=intent,
            service=cust.service_interest,
            top_k=4,
        )
        result = ai_service.suggest_options(history, sources, instruction=(body.instruction or "").strip())
        return {
            "conversation_id": conversation_id,
            "intent": intent,
            "risk_level": result.get("risk_level", risk),
            "confidence": result.get("confidence", 0.0),
            "notes": result.get("notes", ""),
            "options": result.get("options", []),
            "sources": [
                {
                    "snippet_id": s.get("snippet_id"),
                    "title": s.get("title"),
                    "source_path": s.get("source_path"),
                }
                for s in sources
            ],
        }
