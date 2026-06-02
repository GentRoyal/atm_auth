param(
    [int]$Port = 8000,
    [string]$EnvPath = "backend\.env",
    [string]$CloudflaredPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe",
    [switch]$StopExisting,
    [switch]$RestartBackend
)

$ErrorActionPreference = "Stop"

if (!(Test-Path -LiteralPath $CloudflaredPath)) {
    throw "cloudflared was not found at '$CloudflaredPath'. Install Cloudflare Tunnel first or pass -CloudflaredPath."
}

if ($StopExisting) {
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
}

if (!(Test-Path -LiteralPath $EnvPath)) {
    New-Item -ItemType File -Path $EnvPath -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stdout = "cloudflared-tunnel-$timestamp.log"
$stderr = "cloudflared-tunnel-$timestamp.err.log"

$process = Start-Process `
    -FilePath $CloudflaredPath `
    -ArgumentList @("tunnel", "--protocol", "http2", "--url", "http://127.0.0.1:$Port") `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru

$url = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path -LiteralPath $stderr) {
        $content = Get-Content -LiteralPath $stderr -Raw
        $match = [regex]::Match($content, "https://[a-z0-9-]+\.trycloudflare\.com")
        if ($match.Success) {
            $url = $match.Value
            break
        }
    }
}

if (!$url) {
    Write-Host "cloudflared process started with PID $($process.Id), but no tunnel URL was detected yet."
    Write-Host "Check log: $stderr"
    exit 1
}

$lines = Get-Content -LiteralPath $EnvPath
$hasPublicBaseUrl = $false
$updated = foreach ($line in $lines) {
    if ($line -match "^PUBLIC_BASE_URL=") {
        $hasPublicBaseUrl = $true
        "PUBLIC_BASE_URL=$url"
    } else {
        $line
    }
}

if (!$hasPublicBaseUrl) {
    $updated += "PUBLIC_BASE_URL=$url"
}

Set-Content -LiteralPath $EnvPath -Value $updated

Write-Host "New Cloudflare URL:"
Write-Host $url
Write-Host ""
Write-Host "Updated $EnvPath with PUBLIC_BASE_URL=$url"
Write-Host "cloudflared PID: $($process.Id)"

if ($RestartBackend) {
    Get-Process uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 1
    $backendOut = "uvicorn-dev-$Port-$timestamp.log"
    $backendErr = "uvicorn-dev-$Port-$timestamp.err.log"
    $backend = Start-Process `
        -FilePath ".venv\Scripts\python.exe" `
        -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "$Port") `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr `
        -WindowStyle Hidden `
        -PassThru
    Write-Host "Restarted backend on port $Port with PID $($backend.Id)"
}

Write-Host ""
Write-Host "Start a NEW ATM session so SMS links use the fresh URL."
