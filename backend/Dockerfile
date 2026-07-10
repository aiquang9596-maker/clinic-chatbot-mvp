FROM python:3.13-slim

WORKDIR /app

# Deps first for layer cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Create data dir (SQLite fallback; Railway uses Postgres via DATABASE_URL)
RUN mkdir -p data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
