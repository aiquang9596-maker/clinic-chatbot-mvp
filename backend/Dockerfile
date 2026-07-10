FROM python:3.13-slim

WORKDIR /app

# Build context on Railway is repo root, so copy from backend/
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY backend/ ./

# Create data dir (SQLite fallback; Railway uses Postgres via DATABASE_URL)
RUN mkdir -p data

EXPOSE 8000

# Railway injects PORT at runtime; fall back to 8000 locally
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
