# Chatbot MVP — Clinic WhatsApp + Messenger Inbox

Ứng dụng inbox Windows nhận/gợi ý trả lời tin nhắn WhatsApp & Messenger cho clinic.

## Cấu trúc

```
chatbot-mvp/
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── main.py             # Entry point
│   │   ├── models/db.py        # SQLAlchemy models + schema
│   │   ├── routers/
│   │   │   ├── webhook_whatsapp.py
│   │   │   └── webhook_messenger.py
│   │   ├── services/
│   │   │   ├── message_service.py  # Ingest + AI pipeline
│   │   │   ├── ai_service.py       # Ollama classify + draft
│   │   │   ├── kb_service.py       # SQLite FTS retrieval
│   │   │   └── sender_service.py   # Send via Meta APIs
│   │   └── kb/
│   │       └── load_wiki.py        # Load wiki/Chatbot → DB
│   ├── .env.example
│   └── requirements.txt
├── frontend/                   # React inbox UI (phase 2)
├── scripts/
│   ├── start_backend.ps1
│   ├── start_tunnel.ps1
│   └── load_ollama_model.ps1
├── META_SETUP_CHECKLIST.md     # Hướng dẫn setup Meta Dev App
└── README.md
```

## Khởi động nhanh

### 1. Cài Ollama model (CPU-friendly, ~2.4GB)
```powershell
.\scripts\load_ollama_model.ps1
```

### 2. Setup .env
```powershell
Copy-Item backend\.env.example backend\.env
# Rồi mở backend\.env và điền tokens sau khi làm META_SETUP_CHECKLIST.md
```

### 3. Load KB từ wiki
```powershell
Set-Location backend
py -m app.kb.load_wiki
```

### 4. Khởi động backend
```powershell
.\scripts\start_backend.ps1
```

### 5. Khởi động tunnel (terminal mới)
```powershell
.\scripts\start_tunnel.ps1
# Copy URL tunnel → dán vào Meta webhook settings
```

### 6. Test health
```
GET http://localhost:8000/health
```

## AI safety defaults
- `AUTO_REPLY_ENABLED=false` — mặc định tắt, chỉ gợi ý
- High-risk intents luôn force human takeover
- Emergency → takeover ngay lập tức
- Nguồn KB được trace trong mọi draft

## Mở rộng sau
- Frontend React inbox: `frontend/`
- PWA / iPhone: build React responsive → serve qua backend
- Postgres: đổi `DATABASE_URL` trong `.env`
- Cloud AI fallback: thêm vào `ai_service.py`
