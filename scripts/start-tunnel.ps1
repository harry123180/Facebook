# 啟動 cloudflared Quick Tunnel，把 log 寫到 backend/logs/tunnel.log
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root "backend\logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir "tunnel.log"
$err = Join-Path $logDir "tunnel.err.log"
Remove-Item $log, $err -ErrorAction SilentlyContinue

$p = Start-Process -FilePath "cloudflared" `
    -ArgumentList @("tunnel", "--url", "http://127.0.0.1:8000", "--no-autoupdate") `
    -WorkingDirectory $root `
    -RedirectStandardOutput $log -RedirectStandardError $err `
    -WindowStyle Hidden -PassThru

Write-Host "cloudflared 啟動中 (pid $($p.Id))..." -ForegroundColor Cyan
$url = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $content = (Get-Content $log -Raw -ErrorAction SilentlyContinue) + (Get-Content $err -Raw -ErrorAction SilentlyContinue)
    if ($content -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
        $url = $Matches[0]
        break
    }
}

if ($url) {
    Write-Host ""
    Write-Host "  臨時網址: $url" -ForegroundColor Green
    Write-Host "  (存成 .tunnel-url 方便之後查)" -ForegroundColor DarkGray
    Set-Content -Path (Join-Path $root ".tunnel-url") -Value $url -NoNewline
} else {
    Write-Host "  取不到網址，請看 backend/logs/tunnel.err.log" -ForegroundColor Red
    Get-Content $err -ErrorAction SilentlyContinue | Select-Object -Last 15
}
