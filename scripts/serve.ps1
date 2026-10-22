<#
.SYNOPSIS
    正式模式：build 前端 -> 啟動 Flask (waitress, 同時 serve API 與前端) -> 開 cloudflared Quick Tunnel。

.DESCRIPTION
    單一 origin 架構：Flask 在 8000 同時處理 /api/* 與前端靜態檔，
    cloudflared Quick Tunnel 把 https://<random>.trycloudflare.com 轉到 http://127.0.0.1:8000。

    產生的臨時網址在關掉本腳本後即失效。

.EXAMPLE
    .\scripts\serve.ps1
#>
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# --- 載入 .env ---
if (Test-Path "$root\.env") {
    Get-Content "$root\.env" | ForEach-Object {
        if ($_ -match "^([A-Z_]+)=(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
}
# 正式模式：關掉 DEBUG，且 app 會依 X-Forwarded-Proto / Cf-Visitor 自動決定 cookie 的 Secure 旗標
$env:FLASK_ENV = "production"

Write-Host "==> 檢查 PostgreSQL..." -ForegroundColor Cyan
if (-not (docker ps --filter "name=facebook_mvp_db" --filter "status=running" --format "{{.Names}}")) {
    Write-Host "    啟動資料庫..." -ForegroundColor Yellow
    docker compose up -d db
    Start-Sleep -Seconds 4
}

Write-Host "==> build 前端" -ForegroundColor Green
Push-Location "$root\frontend"
pnpm build
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "前端 build 失敗" }
Pop-Location

Write-Host "==> 啟動 Flask (waitress :8000)" -ForegroundColor Green
& "$root\scripts\start-backend.ps1"

Write-Host "==> 啟動 cloudflared Quick Tunnel" -ForegroundColor Green
& "$root\scripts\start-tunnel.ps1"

$url = if (Test-Path "$root\.tunnel-url") { (Get-Content "$root\.tunnel-url" -Raw).Trim() } else { "" }
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Green
Write-Host "   臨時網址: $url" -ForegroundColor Green
Write-Host "  ============================================" -ForegroundColor Green
Write-Host "  這個網址關掉腳本就會失效。" -ForegroundColor DarkGray
Write-Host "  收掉: .\scripts\stop-all.ps1" -ForegroundColor DarkGray

while ($true) { Start-Sleep -Seconds 5 }
