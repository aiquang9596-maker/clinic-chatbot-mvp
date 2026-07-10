"""FastAPI entry point."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
