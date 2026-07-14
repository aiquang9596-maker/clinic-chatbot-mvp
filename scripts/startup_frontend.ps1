# Startup script — chạy tự động khi đăng nhập Windows
# Chỉ khởi động Frontend (Backend đã chạy trên Railway cloud)
# Setup: xem README.md phần "Windows Startup"

$frontendPath = "D:\Projects\chatbot-mvp\frontend"
$logPath = "D:\Projects\chatbot-mvp\logs"

New-Item -ItemType Directory -Force -Path $logPath | Out-Null

Write-Host "[$(Get-Date)] Starting Chatbot MVP Frontend..." -ForegroundColor Cyan

Set-Location $frontendPath
npm run dev 2>&1 | Tee-Object -FilePath "$logPath\frontend.log"
