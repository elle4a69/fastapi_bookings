param(
    [int]$Port = 8000,
    [int]$StartupTimeoutSeconds = 45,
    [int]$StartDelaySeconds = 5,
    [int]$RequestDelayMilliseconds = 100
)

$ErrorActionPreference = "Stop"

$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ToolDir "..\..")
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PrepareScript = Join-Path $ToolDir "prepare_authenticated_sweep.py"
$CleanupScript = Join-Path $ToolDir "cleanup_authenticated_sweep.py"
$Collection = Join-Path $ToolDir "FastAPI-Bookings-Local-Authenticated.postman_collection.json"
$Environment = Join-Path $ToolDir "SimplyDemo-Local.postman_environment.json"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$RunDir = Join-Path $ToolDir ("reports\run-" + $Timestamp)
$ConsoleLog = Join-Path $RunDir "console.log"
$JsonReport = Join-Path $RunDir "authenticated-sweep.json"
$HtmlReport = Join-Path $RunDir "authenticated-sweep.html"
$ServerOut = Join-Path $RunDir "uvicorn.stdout.log"
$ServerErr = Join-Path $RunDir "uvicorn.stderr.log"
$SummaryFile = Join-Path $RunDir "summary.txt"
$BaseUrl = "http://127.0.0.1:$Port"
$HealthUrl = "$BaseUrl/health"
$StartedServer = $false
$ServerProcess = $null
$ExitCode = 1

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Write-RunLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    $line | Tee-Object -FilePath $ConsoleLog -Append
}

function Test-ApiHealth {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $HealthUrl -TimeoutSec 3
        return ($response.StatusCode -eq 200)
    }
    catch {
        return $false
    }
}

try {
    Write-RunLog "Run directory: $RunDir"

    if (-not (Test-ApiHealth)) {
        Write-RunLog "API is not responding on port $Port. Starting Uvicorn."

        if (-not (Test-Path $Python)) {
            throw "Python virtual environment not found at $Python"
        }

        $ServerProcess = Start-Process `
            -FilePath $Python `
            -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port") `
            -WorkingDirectory $ProjectRoot `
            -RedirectStandardOutput $ServerOut `
            -RedirectStandardError $ServerErr `
            -WindowStyle Hidden `
            -PassThru
        $StartedServer = $true

        $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
        while ((Get-Date) -lt $deadline) {
            if ($ServerProcess.HasExited) {
                throw "Uvicorn exited before becoming healthy. Check $ServerErr"
            }
            if (Test-ApiHealth) {
                break
            }
            Start-Sleep -Seconds 1
        }

        if (-not (Test-ApiHealth)) {
            throw "API did not become healthy within $StartupTimeoutSeconds seconds."
        }
    }
    else {
        Write-RunLog "API is already healthy at $HealthUrl"
    }

    Write-RunLog "Preparing authenticated collection and temporary JWTs."
    $env:POSTMAN_BASE_URL = $BaseUrl
    Push-Location $ProjectRoot
    try {
        & $Python $PrepareScript 2>&1 | Tee-Object -FilePath $ConsoleLog -Append
        if ($LASTEXITCODE -ne 0) {
            throw "Authentication preparation failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }

    Write-RunLog "Waiting $StartDelaySeconds second(s) before Newman execution."
    Start-Sleep -Seconds $StartDelaySeconds

    Write-RunLog "Running authenticated Newman sweep."
    Push-Location $ToolDir
    try {
        & npx newman run $Collection `
            -e $Environment `
            --env-var "baseUrl=$BaseUrl" `
            --reporters "cli,json,htmlextra" `
            --reporter-json-export $JsonReport `
            --reporter-htmlextra-export $HtmlReport `
            --timeout-request 15000 `
            --delay-request $RequestDelayMilliseconds 2>&1 | Tee-Object -FilePath $ConsoleLog -Append
        $ExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    @(
        "Timestamp: $Timestamp"
        "Base URL: $BaseUrl"
        "Newman exit code: $ExitCode"
        "JSON report: $JsonReport"
        "HTML report: $HtmlReport"
        "Console log: $ConsoleLog"
        "Server started by script: $StartedServer"
    ) | Set-Content -Path $SummaryFile -Encoding UTF8

    Write-RunLog "Sweep finished with Newman exit code $ExitCode"
    Write-RunLog "JSON report: $JsonReport"
    Write-RunLog "HTML report: $HtmlReport"
    Write-RunLog "Summary: $SummaryFile"
}
catch {
    Write-RunLog ("ERROR: " + $_.Exception.Message)
    @(
        "Timestamp: $Timestamp"
        "Base URL: $BaseUrl"
        "Status: FAILED BEFORE COMPLETION"
        "Error: $($_.Exception.Message)"
        "Console log: $ConsoleLog"
        "Server stderr: $ServerErr"
    ) | Set-Content -Path $SummaryFile -Encoding UTF8
    $ExitCode = 1
}
finally {
    Write-RunLog "Cleaning up temporary sweep identity and token material."
    if (Test-Path $Python) {
        Push-Location $ProjectRoot
        try {
            & $Python $CleanupScript 2>&1 | Tee-Object -FilePath $ConsoleLog -Append
        }
        catch {
            Write-RunLog ("Cleanup warning: " + $_.Exception.Message)
        }
        finally {
            Pop-Location
        }
    }

    if ($StartedServer -and $ServerProcess -and -not $ServerProcess.HasExited) {
        Write-RunLog "Stopping the Uvicorn process started by this launcher."
        Stop-Process -Id $ServerProcess.Id -Force
    }
}

exit $ExitCode
