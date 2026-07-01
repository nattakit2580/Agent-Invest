# Agent Invest - Setup Script
Write-Host "=== Agent Invest Setup ===" -ForegroundColor Cyan

# Backend setup
Write-Host "`n[Backend] Installing Python dependencies..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\backend"

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example - Please edit ANTHROPIC_API_KEY!" -ForegroundColor Red
}

pip install -r requirements.txt

# Frontend setup
Write-Host "`n[Frontend] Installing Node dependencies..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\frontend"

if (-not (Test-Path ".env.local")) {
  Set-Content ".env.local" "NEXT_PUBLIC_API_URL=http://localhost:8000"
  Write-Host "Created frontend/.env.local" -ForegroundColor Green
}

npm install

Write-Host "`n=== Setup Complete ===" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Edit backend/.env and set ANTHROPIC_API_KEY=sk-ant-..." -ForegroundColor White
Write-Host "2. Run .\start.ps1 to launch the system" -ForegroundColor White
Write-Host "3. Open http://localhost:3000" -ForegroundColor White
