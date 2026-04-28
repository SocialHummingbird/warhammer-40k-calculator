$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 8810
$Url = "http://127.0.0.1:$Port"
$HealthUrl = "$Url/api/health"
$OutLog = Join-Path $Root "web_ui_desktop.log"
$ErrLog = Join-Path $Root "web_ui_desktop.err.log"

Set-Location $Root

$running = $false
try {
    $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
    $running = [bool]$health.ok
} catch {
    $running = $false
}

if (-not $running) {
    Start-Process -FilePath python `
        -ArgumentList @("-m", "warhammer.webapp", "--csv-dir", "data/10e/latest", "--host", "127.0.0.1", "--port", "$Port") `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -WindowStyle Hidden

    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 1
            if ($health.ok) {
                break
            }
        } catch {
            Start-Sleep -Milliseconds 300
        }
    }
}

Start-Process $Url
