param(
    [switch]$SkipTests,
    [switch]$SkipReviewGate,
    [string]$Thresholds = "config\review_thresholds_10e.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

$Python = (Get-Command python -ErrorAction Stop).Source
$VerifyArgs = @("verify_release.py")
if ($SkipTests) {
    $VerifyArgs += "--skip-tests"
}
if ($SkipReviewGate) {
    $VerifyArgs += "--skip-review-gate"
}
if ($Thresholds) {
    $VerifyArgs += @("--thresholds", $Thresholds)
}

& $Python @VerifyArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
