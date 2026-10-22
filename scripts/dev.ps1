<#
.SYNOPSIS
    開發模式：同時啟動 Flask 後端 (8000) 與 Vite 前端 (5173)。

.DESCRIPTION
    後端在 127.0.0.1:8000，前端 Vite dev server 在 5173。
    Vite 已設定 proxy 把 /api 轉到後端，所以不需要 CORS，也沒有跨來源 cookie 問題。

.EXAMPLE
    .\scripts\dev.ps1
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

Write-Host "==> 檢查 PostgreSQL (docker)..." -ForegroundColor Cyan
if (-not (docker ps --filter "name=facebook_mvp_db" --filter "status=running" --format "{{.Names}}")) {
    Write-Host "    資料庫未啟動，執行 docker compose up -d db" -ForegroundColor Yellow
    docker compose up -d db
    Start-Sleep -Seconds 4
}

Write-Host "==> 啟動 Flask 後端 :8000" -ForegroundColor Green
& "$root\scripts\start-backend.ps1"

Write-Host "==> 啟動 Vite 前端 :5173" -ForegroundColor Green
$frontend = Start-Process -FilePath "powershell" -ArgumentList @(
    "-NoExit", "-Command", "cd '$root\frontend'; pnpm dev"
) -PassThru

Write-Host ""
Write-Host "  前端 (Vite)  : http://localhost:5173" -ForegroundColor Cyan
Write-Host "  後端 API     : http://127.0.0.1:8000/api/health" -ForegroundColor Cyan
Write-Host "  收掉前端: Stop-Process -Id $($frontend.Id)" -ForegroundColor DarkGray
Write-Host "  收掉後端: .\scripts\stop-all.ps1" -ForegroundColor DarkGray

while ($true) { Start-Sleep -Seconds 5 }
