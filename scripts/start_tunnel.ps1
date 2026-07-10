# Khởi động Cloudflare Tunnel trỏ vào backend port 8000
# Chạy: .\scripts\start_tunnel.ps1

$port = 8000
Write-Host "Starting Cloudflare Tunnel → localhost:$port ..."
cloudflared tunnel --url http://localhost:$port
