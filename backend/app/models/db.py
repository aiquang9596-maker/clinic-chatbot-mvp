"""Database models — SQLite (local) or PostgreSQL (cloud) via SQLAlchemy."""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Text, Boolean, Float,
    DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship, Session
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/chatbot.db")

# Railway injects postgres:// — SQLAlchemy 2.x needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)

class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    id              = Column(String, primary_key=True)          # UUID
    full_name       = Column(String)
    primary_channel = Column(String)                            # whatsapp | messenger
    external_user_id= Column(String, index=True)               # PSID or WA number
    phone_e164      = Column(String)
    country         = Column(String)
    timezone        = Column(String)
    preferred_language = Column(String, default="en")
    service_interest= Column(String, default="unknown")        # hair | facelift | combo
    lead_status     = Column(String, default="new")            # new | active | hot | quoted | booked | postop | closed
    tags            = Column(JSON, default=list)
    notes           = Column(Text)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    conversations   = relationship("Conversation", back_populates="customer")


class Conversation(Base):
    __tablename__ = "conversations"
    id              = Column(String, primary_key=True)
    customer_id     = Column(String, ForeignKey("customers.id"), index=True)
    channel         = Column(String)                            # whatsapp | messenger
    external_thread_id = Column(String, index=True)
    status          = Column(String, default="open")            # open | pending | closed
    assigned_to     = Column(String)
    human_takeover  = Column(Boolean, default=False)
    escalation_level= Column(String, default="L1")             # L1 | L2 | L3 | L4
    ai_mode         = Column(String, default="suggest")        # off | suggest | limited_auto
    last_summary    = Column(Text)
    last_source_ids = Column(JSON, default=list)
    last_message_at = Column(DateTime)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    customer        = relationship("Customer", back_populates="conversations")
    messages        = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    id                  = Column(String, primary_key=True)
    conversation_id     = Column(String, ForeignKey("conversations.id"), index=True)
    external_message_id = Column(String, unique=True, index=True)  # dedupe key
    channel             = Column(String)
    direction           = Column(String)                           # inbound | outbound
    sender_type         = Column(String)                           # customer | agent | ai
    content_text        = Column(Text)
    attachments         = Column(JSON, default=list)
    message_timestamp   = Column(DateTime)
    delivery_status     = Column(String)
    ai_generated        = Column(Boolean, default=False)
    ai_model            = Column(String)
    ai_confidence       = Column(Float)
    prompt_version      = Column(String)
    source_ids          = Column(JSON, default=list)
    risk_level          = Column(String)                           # low | medium | high | emergency
    sent_by_user_id     = Column(String)
    created_at          = Column(DateTime, default=datetime.utcnow)
    conversation        = relationship("Conversation", back_populates="messages")


class KBSnippet(Base):
    __tablename__ = "kb_snippets"
    id              = Column(String, primary_key=True)
    snippet_id      = Column(String, unique=True, index=True)
    source_path     = Column(String)
    source_section  = Column(String)
    title           = Column(String)
    language        = Column(String, default="vi")
    service         = Column(String)                            # hair | facelift | general
    intent          = Column(String)
    risk_level      = Column(String, default="low")
    customer_visible= Column(Boolean, default=True)
    role            = Column(String, default="supporting")
    answer_text     = Column(Text)
    keywords        = Column(JSON, default=list)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id              = Column(String, primary_key=True)
    message_id      = Column(String, index=True)
    conversation_id = Column(String, index=True)
    event_type      = Column(String)   # inbound | draft | edit | send | takeover | escalate
    actor           = Column(String)   # system | user_id
    detail          = Column(JSON)
    created_at      = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine)
