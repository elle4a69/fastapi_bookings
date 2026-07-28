param(
    [int]$StartDelaySeconds = 5,
    [int]$RequestDelayMilliseconds = 100,
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Tenant = "simplydemo"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptRoot

$collection = Join-Path $scriptRoot "FastAPI-Bookings-Local.postman_collection.json"
$reportsDir = Join-Path $scriptRoot "reports"
$jsonReport = Join-Path $reportsDir "sweep.json"
$htmlReport = Join-Path $reportsDir "sweep.html"

if (-not (Test-Path $collection)) {
    throw "Collection not found: $collection"
}

New-Item -ItemType Directory -Path $reportsDir -Force | Out-Null

Write-Host "Starting Newman sweep in $StartDelaySeconds second(s)..."
Start-Sleep -Seconds $StartDelaySeconds

& npx newman run $collection `
    --env-var "baseUrl=$BaseUrl" `
    --env-var "X-Tenant=$Tenant" `
    --reporters "cli,json,htmlextra" `
    --reporter-json-export $jsonReport `
    --reporter-htmlextra-export $htmlReport `
    --timeout-request 15000 `
    --delay-request $RequestDelayMilliseconds

$exitCode = $LASTEXITCODE
Write-Host "Newman finished with exit code $exitCode"
Write-Host "JSON report: $jsonReport"
Write-Host "HTML report: $htmlReport"
exit $exitCode
