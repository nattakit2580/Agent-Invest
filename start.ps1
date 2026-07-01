# Agent Invest - Start Script
Write-Host "=== Agent Invest ===" -ForegroundColor Cyan

# Start Backend
Write-Host "`n[1/2] Starting Backend (FastAPI)..." -ForegroundColor Yellow
$backend = Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "cd '$PSScriptRoot\backend'; uvicorn main:app --reload --port 8000" -PassThru

Start-Sleep -Seconds 3

# Start Frontend
Write-Host "[2/2] Starting Frontend (Next.js)..." -ForegroundColor Yellow
$frontend = Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "cd '$PSScriptRoot\frontend'; npm run dev" -PassThru

Write-Host "`n=== Started ===" -ForegroundColor Green
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "`nกด Enter เพื่อหยุดระบบ..."
Read-Host
$backend.Kill()
$frontend.Kill()
