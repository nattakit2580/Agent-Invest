$ErrorActionPreference = "Stop"

Write-Host "=== Agent Invest ===" -ForegroundColor Cyan

$venvPython = Join-Path $PSScriptRoot "backend\.venv\Scripts\python.exe"
$nodeModules = Join-Path $PSScriptRoot "frontend\node_modules"

if (-not (Test-Path -LiteralPath $venvPython) -or -not (Test-Path -LiteralPath $nodeModules)) {
  throw "Dependencies are missing. Run .\setup.ps1 first."
}

$backendEnv = Join-Path $PSScriptRoot "backend\.env"
if (-not (Test-Path -LiteralPath $backendEnv)) {
  & $venvPython (Join-Path $PSScriptRoot "make_local_env.py")
  if ($LASTEXITCODE -ne 0) { throw "Could not create backend/.env." }
}

Write-Host "`n[1/2] Starting Backend (FastAPI)..." -ForegroundColor Yellow
$backendCommand = "Set-Location -LiteralPath '$PSScriptRoot\backend'; & '$venvPython' -m uvicorn main:app --reload --port 8000"
$backend = Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCommand -PassThru

Start-Sleep -Seconds 3

Write-Host "[2/2] Starting Frontend (Next.js)..." -ForegroundColor Yellow
$frontendCommand = "Set-Location -LiteralPath '$PSScriptRoot\frontend'; npm run dev"
$frontend = Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCommand -PassThru

Write-Host "`n=== Started ===" -ForegroundColor Green
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "`nPress Enter to stop both processes."
Read-Host

if (-not $backend.HasExited) { $backend.Kill() }
if (-not $frontend.HasExited) { $frontend.Kill() }
