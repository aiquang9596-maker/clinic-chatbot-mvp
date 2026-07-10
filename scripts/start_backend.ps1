# Khởi động FastAPI backend
# Chạy: .\scripts\start_backend.ps1

Set-Location "$PSScriptRoot\..\backend"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[!] .env created from .env.example — fill in your tokens before running!" -ForegroundColor Yellow
}

Write-Host "Starting backend on http://localhost:8000 ..."
py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
