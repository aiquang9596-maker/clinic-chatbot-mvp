"""FastAPI entry point."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

load_dotenv()

from app.models.db import init_db
from app.services.kb_service import setup_fts
from app.routers import webhook_whatsapp, webhook_messenger, inbox


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    setup_fts()
    yield


app = FastAPI(title="Chatbot MVP", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_whatsapp.router)
app.include_router(webhook_messenger.router)
app.include_router(inbox.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/privacy-policy", response_class=HTMLResponse)
def privacy_policy():
    return """<!doctype html><html><head><meta charset="utf-8">
<title>Privacy Policy — APEX Care Plus Clinic Chatbot</title></head><body style="font-family:sans-serif;max-width:700px;margin:2rem auto;line-height:1.6">
<h1>Privacy Policy</h1>
<p>This chatbot ("the Service") helps APEX Care Plus International Clinic respond to
customer inquiries via Facebook Messenger and WhatsApp.</p>
<h2>Data we collect</h2>
<p>When you message our Page or WhatsApp number, we receive your name, phone number or
Messenger ID, and the content of your messages, in order to respond to your inquiry and
provide customer support.</p>
<h2>How we use your data</h2>
<p>Data is used solely to reply to your messages, manage your booking/lead record, and
follow up regarding services you asked about. We do not sell or share your data with
third parties for marketing purposes.</p>
<h2>Data retention</h2>
<p>Conversation records are retained for as long as needed to provide support and
maintain business records, and can be deleted on request.</p>
<h2>Contact</h2>
<p>For questions or data deletion requests, contact us at
<a href="mailto:tunq.dev@gmail.com">tunq.dev@gmail.com</a>.</p>
</body></html>"""
