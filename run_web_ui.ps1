Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

$Python = (Get-Command python -ErrorAction Stop).Source
& $Python -m warhammer.webapp --csv-dir data/latest --host 127.0.0.1 --port 8765
