<#
.SYNOPSIS
    收掉本專案啟動的後端與 cloudflared tunnel。
#>
$ErrorActionPreference = "SilentlyContinue"

foreach ($port in @(8000)) {
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen
    foreach ($l in $listeners) {
        Write-Host "停止 port $port 上的行程 pid=$($l.OwningProcess)" -ForegroundColor Yellow
        Stop-Process -Id $l.OwningProcess -Force
    }
}

Get-Process cloudflared | ForEach-Object {
    Write-Host "停止 cloudflared pid=$($_.Id)" -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force
}

Remove-Item (Join-Path (Split-Path -Parent $PSScriptRoot) ".tunnel-url") -Force

Write-Host "已全部停止" -ForegroundColor Green
