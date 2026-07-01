# Agent Invest - Cloudflare Tunnel
# เปิด URL สาธารณะให้คนอื่นเข้าได้ผ่าน Cloudflare

Write-Host "=== Agent Invest - Cloudflare Tunnel ===" -ForegroundColor Cyan

# ตรวจสอบว่า cloudflared ติดตั้งแล้วหรือยัง
$localExe = "$PSScriptRoot\cloudflared.exe"
$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue

if (Test-Path $localExe) {
    $cloudflaredExe = $localExe
    Write-Host "cloudflared.exe พร้อมใช้งาน" -ForegroundColor Green
} elseif ($cloudflared) {
    $cloudflaredExe = "cloudflared"
    Write-Host "cloudflared (system) พร้อมใช้งาน" -ForegroundColor Green
} else {
    Write-Host "`n[!] กำลัง download cloudflared..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile $localExe -UseBasicParsing
    $cloudflaredExe = $localExe
    Write-Host "Downloaded OK" -ForegroundColor Green
}

Write-Host "`n[*] ตรวจสอบว่า Backend (port 8000) และ Frontend (port 3000) ทำงานอยู่..." -ForegroundColor Yellow

$backendOk = $false
$frontendOk = $false

try {
    $r = Invoke-WebRequest "http://localhost:8000/health" -TimeoutSec 3 -ErrorAction Stop
    if ($r.StatusCode -eq 200) { $backendOk = $true }
} catch {}

try {
    $r = Invoke-WebRequest "http://localhost:3000" -TimeoutSec 3 -ErrorAction Stop
    if ($r.StatusCode -eq 200) { $frontendOk = $true }
} catch {}

if (-not $backendOk) {
    Write-Host "[!] Backend ยังไม่ได้รัน - กรุณารัน .\start.ps1 ก่อน" -ForegroundColor Red
}
if (-not $frontendOk) {
    Write-Host "[!] Frontend ยังไม่ได้รัน - กรุณารัน .\start.ps1 ก่อน" -ForegroundColor Red
}

if (-not $backendOk -or -not $frontendOk) {
    Write-Host "`nเปิด Tunnel ต่อไหมแม้ระบบยังไม่พร้อม? (y/n)" -ForegroundColor Yellow
    $ans = Read-Host
    if ($ans -ne "y") { exit }
}

Write-Host "`n[*] กำลังเปิด Cloudflare Tunnel สำหรับ Frontend (port 3000)..." -ForegroundColor Cyan
Write-Host "    URL สาธารณะจะแสดงใน 5-10 วินาที รอสักครู่..." -ForegroundColor Gray
Write-Host ""
Write-Host "=== URL จะขึ้นในบรรทัดที่มี 'trycloudflare.com' ===" -ForegroundColor Green
Write-Host "    ส่ง URL นั้นให้คนอื่นเปิดได้เลย" -ForegroundColor Green
Write-Host ""
Write-Host "กด Ctrl+C เพื่อปิด Tunnel`n" -ForegroundColor Gray

& $cloudflaredExe tunnel --url http://localhost:3000
