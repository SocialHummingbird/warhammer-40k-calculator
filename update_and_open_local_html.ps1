param(
    [switch]$SkipFetch,
    [switch]$NoOpen
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

$Python = (Get-Command python -ErrorAction Stop).Source
$UpdateArgs = @("update_database.py")
if ($SkipFetch) {
    $UpdateArgs += "--skip-fetch"
}

& $Python @UpdateArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$HtmlPath = Join-Path $ProjectRoot "warhammer_calculator_local.html"
if (-not (Test-Path -LiteralPath $HtmlPath)) {
    throw "Expected local HTML was not generated: $HtmlPath"
}

if (-not $NoOpen) {
    Start-Process -FilePath $HtmlPath
}
