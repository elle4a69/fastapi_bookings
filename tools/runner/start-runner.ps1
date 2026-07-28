param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8011
)

$ErrorActionPreference = "Stop"
$RunnerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $RunnerDir "..\..")
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$KeyFile = Join-Path $RunnerDir "state\runner-api-key.txt"

if (-not (Test-Path $Python)) {
    throw "Project Python environment not found: $Python"
}

New-Item -ItemType Directory -Force -Path (Join-Path $RunnerDir "state\jobs") | Out-Null

Write-Host "Starting restricted HTTP runner on http://$HostAddress`:$Port"
Write-Host "Health endpoint: http://$HostAddress`:$Port/health"
Write-Host "API key file: $KeyFile"
Write-Host "The runner accepts only the authenticated Postman sweep command."

Push-Location $ProjectRoot
try {
    & $Python -m uvicorn tools.runner.app:app --host $HostAddress --port $Port
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
