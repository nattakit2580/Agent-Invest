$ErrorActionPreference = "Stop"

Write-Host "=== Agent Invest Setup ===" -ForegroundColor Cyan

if (Get-Command python -ErrorAction SilentlyContinue) {
  $pythonLauncher = "python"
  $pythonArgs = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $pythonLauncher = "py"
  $pythonArgs = @("-3")
} else {
  throw "Python 3.11+ was not found. Install it and enable Add Python to PATH."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "Node.js 20 LTS and npm were not found."
}

$venvPath = Join-Path $PSScriptRoot "backend\.venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

Write-Host "`n[Backend 1/3] Preparing virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path -LiteralPath $venvPython)) {
  & $pythonLauncher @pythonArgs -m venv $venvPath
  if ($LASTEXITCODE -ne 0) { throw "Could not create backend/.venv." }
}

Write-Host "[Backend 2/3] Installing pinned dependencies..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip." }
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "backend\requirements.txt") --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "Could not install backend dependencies." }

Write-Host "[Backend 3/3] Preparing local configuration..." -ForegroundColor Yellow
$backendEnv = Join-Path $PSScriptRoot "backend\.env"
if (-not (Test-Path -LiteralPath $backendEnv)) {
  & $venvPython (Join-Path $PSScriptRoot "make_local_env.py")
  if ($LASTEXITCODE -ne 0) { throw "Could not create backend/.env." }
}

Write-Host "`n[Frontend] Installing exact lockfile dependencies..." -ForegroundColor Yellow
Push-Location (Join-Path $PSScriptRoot "frontend")
try {
  npm ci --no-fund --no-audit
  if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
} finally {
  Pop-Location
}

Write-Host "`n=== Setup Complete ===" -ForegroundColor Green
Write-Host "1. Edit backend\.env and set OPENROUTER_API_KEY for AI analysis." -ForegroundColor White
Write-Host "2. Run .\start.ps1 or double-click run.bat." -ForegroundColor White
Write-Host "3. Open http://localhost:3000" -ForegroundColor White
