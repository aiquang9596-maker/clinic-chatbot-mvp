# Tải model AI nhẹ cho CPU-only (phi3:mini ~2.4GB)
# Chạy: .\scripts\load_ollama_model.ps1

Write-Host "Pulling phi3:mini (CPU-friendly, ~2.4GB)..."
ollama pull phi3:mini

Write-Host ""
Write-Host "Test model:"
ollama run phi3:mini "Reply in 1 sentence: What is hair transplant?"
