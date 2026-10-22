# 啟動後端（背景），把 log 寫到 backend/logs/server.log
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root "backend\logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir "server.log"
$err = Join-Path $logDir "server.err.log"

Set-Location (Join-Path $root "backend")
$p = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList @("-m", "waitress", "--port=8000", "--call", "wsgi:create_app") `
    -WorkingDirectory (Join-Path $root "backend") `
    -RedirectStandardOutput $log -RedirectStandardError $err `
    -WindowStyle Hidden -PassThru

Start-Sleep -Seconds 5
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 10
    Write-Host "server up (pid $($p.Id)): $($r.Content)" -ForegroundColor Green
} catch {
    Write-Host "server FAILED to start" -ForegroundColor Red
    Get-Content $err -ErrorAction SilentlyContinue | Select-Object -Last 20
}
