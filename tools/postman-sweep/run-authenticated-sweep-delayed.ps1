param(
    [int]$StartDelaySeconds = 5,
    [int]$RequestDelayMilliseconds = 100
)

$ErrorActionPreference = "Stop"
$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ToolDir "..\..")
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Collection = Join-Path $ToolDir "FastAPI-Bookings-Local-Authenticated.postman_collection.json"
$Environment = Join-Path $ToolDir "SimplyDemo-Local.postman_environment.json"
$Reports = Join-Path $ToolDir "reports"
$ServerOut = Join-Path $Reports "uvicorn.out.log"
$ServerErr = Join-Path $Reports "uvicorn.err.log"
$code = 1
$serverProcess = $null
$startedServer = $false

New-Item -ItemType Directory -Force -Path $Reports | Out-Null

function Test-ApiHealth {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

try {
    if (-not (Test-ApiHealth)) {
        Write-Host "API is not running. Starting Uvicorn on port 8000..."
        $serverProcess = Start-Process -FilePath $Python `
            -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
            -WorkingDirectory $ProjectRoot `
            -RedirectStandardOutput $ServerOut `
            -RedirectStandardError $ServerErr `
            -PassThru
        $startedServer = $true

        $healthy = $false
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            if (Test-ApiHealth) {
                $healthy = $true
                break
            }
            if ($serverProcess.HasExited) {
                break
            }
        }
        if (-not $healthy) {
            throw "Uvicorn did not become healthy. Check $ServerErr"
        }
    }

    Write-Host "Preparing authenticated local sweep..."
    Push-Location $ProjectRoot
    try {
        & $Python (Join-Path $ToolDir "prepare_authenticated_sweep.py")
        if ($LASTEXITCODE -ne 0) { throw "Sweep preparation failed with exit code $LASTEXITCODE" }
    }
    finally {
        Pop-Location
    }

    Write-Host "Starting authenticated Newman sweep in $StartDelaySeconds second(s)..."
    Start-Sleep -Seconds $StartDelaySeconds

    Push-Location $ToolDir
    try {
        & npx newman run $Collection `
            -e $Environment `
            --reporters "cli,json,htmlextra" `
            --reporter-json-export (Join-Path $Reports "authenticated-sweep.json") `
            --reporter-htmlextra-export (Join-Path $Reports "authenticated-sweep.html") `
            --timeout-request 15000 `
            --delay-request $RequestDelayMilliseconds
        $code = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
finally {
    Write-Host "Cleaning up temporary sweep identity..."
    Push-Location $ProjectRoot
    try {
        & $Python (Join-Path $ToolDir "cleanup_authenticated_sweep.py")
    }
    finally {
        Pop-Location
    }

    if ($startedServer -and $serverProcess -and -not $serverProcess.HasExited) {
        Write-Host "Stopping sweep-started Uvicorn process..."
        Stop-Process -Id $serverProcess.Id -Force
    }
}

Write-Host "Newman finished with exit code $code"
Write-Host "JSON report: $(Join-Path $Reports 'authenticated-sweep.json')"
Write-Host "HTML report: $(Join-Path $Reports 'authenticated-sweep.html')"
exit $code
