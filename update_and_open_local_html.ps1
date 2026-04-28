param(
    [switch]$SkipFetch,
    [switch]$SkipMl,
    [int]$MlMaxRows = -1,
    [ValidateSet("", "sample", "sequential")]
    [string]$MlStrategy = "",
    [int]$MlSeed = -1,
    [ValidateSet("", "pre_match", "full")]
    [string]$MlFeatureSet = "",
    [string]$MlModelType = "",
    [string]$MlLabels = "",
    [string[]]$MlLabelKeyColumns = @(),
    [switch]$FailOnReviewIssues,
    [switch]$ReviewFailOnWarnings,
    [string]$ReviewThresholds = "",
    [string]$WriteReviewThresholds = "",
    [int]$MaxSuspiciousWeaponWarnings = -1,
    [int]$MaxLoadoutWarnings = -1,
    [int]$MaxNoWeaponUnits = -1,
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
if ($SkipMl) {
    $UpdateArgs += "--skip-ml"
}
if ($MlMaxRows -ge 0) {
    $UpdateArgs += @("--ml-max-rows", $MlMaxRows.ToString())
}
if ($MlStrategy) {
    $UpdateArgs += @("--ml-strategy", $MlStrategy)
}
if ($MlSeed -ge 0) {
    $UpdateArgs += @("--ml-seed", $MlSeed.ToString())
}
if ($MlFeatureSet) {
    $UpdateArgs += @("--ml-feature-set", $MlFeatureSet)
}
if ($MlModelType) {
    $UpdateArgs += @("--ml-model-type", $MlModelType)
}
if ($MlLabels) {
    $UpdateArgs += @("--ml-labels", $MlLabels)
}
if ($MlLabelKeyColumns.Count -gt 0) {
    $UpdateArgs += "--ml-label-key-columns"
    $UpdateArgs += $MlLabelKeyColumns
}
if ($FailOnReviewIssues) {
    $UpdateArgs += "--fail-on-review-issues"
}
if ($ReviewFailOnWarnings) {
    $UpdateArgs += "--review-fail-on-warnings"
}
if ($ReviewThresholds) {
    $UpdateArgs += @("--review-thresholds", $ReviewThresholds)
}
if ($WriteReviewThresholds) {
    $UpdateArgs += @("--write-review-thresholds", $WriteReviewThresholds)
}
if ($MaxSuspiciousWeaponWarnings -ge 0) {
    $UpdateArgs += @("--max-suspicious-weapon-warnings", $MaxSuspiciousWeaponWarnings.ToString())
}
if ($MaxLoadoutWarnings -ge 0) {
    $UpdateArgs += @("--max-loadout-warnings", $MaxLoadoutWarnings.ToString())
}
if ($MaxNoWeaponUnits -ge 0) {
    $UpdateArgs += @("--max-no-weapon-units", $MaxNoWeaponUnits.ToString())
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
