# Codex Control Centre - Safe Persistent Launch Script
# Only terminates processes tracked in dedicated PID files (.codex_backend.pid, .codex_frontend.pid).
# Refuses to start and reports an actionable error if untracked processes occupy ports 8100 or 5180.

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ROOT) { $ROOT = (Get-Location).Path }
$BACKEND = Join-Path $ROOT "backend"
$FRONTEND = Join-Path $ROOT "frontend"

Write-Output "=== Codex Control Centre Launcher ==="

$backendPidFile = Join-Path $ROOT ".codex_backend.pid"
$frontendPidFile = Join-Path $ROOT ".codex_frontend.pid"

# 1. Gracefully terminate previously tracked processes using stop.ps1
$stopScript = Join-Path $ROOT "stop.ps1"
if (Test-Path $stopScript) {
    & $stopScript
} else {
    if (Test-Path $backendPidFile) {
        $oldPid = (Get-Content $backendPidFile -Raw).Trim()
        if ($oldPid -match "^\d+$") {
            try { Stop-Process -Id [int]$oldPid -Force -ErrorAction SilentlyContinue } catch {}
        }
        Remove-Item $backendPidFile -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $frontendPidFile) {
        $oldPid = (Get-Content $frontendPidFile -Raw).Trim()
        if ($oldPid -match "^\d+$") {
            try { Stop-Process -Id [int]$oldPid -Force -ErrorAction SilentlyContinue } catch {}
        }
        Remove-Item $frontendPidFile -Force -ErrorAction SilentlyContinue
    }
}

# 2. Check for port conflicts with UNTRACKED processes (do NOT indiscriminately taskkill)
function Test-PortAvailability {
    param (
        [int]$Port,
        [string]$ServiceName
    )

    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $owningPids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $owningPids) {
            if ($p -gt 4) {
                $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
                if ($proc) {
                    $procName = $proc.ProcessName
                    Write-Output "  [ERROR] Port $Port ($ServiceName) is occupied by untracked process: '$procName' (PID: $p)."
                    Write-Output "          Indiscriminate taskkill is disabled for safety."
                    Write-Output "          Please terminate or reconfigure the conflicting process and retry."
                    return $false
                }
            }
        }
    }
    return $true
}

$backendPortFree = Test-PortAvailability -Port 8100 -ServiceName "Backend API"
$frontendPortFree = Test-PortAvailability -Port 5180 -ServiceName "Frontend UI"

if (-not $backendPortFree -or -not $frontendPortFree) {
    Write-Output ""
    Write-Output "=== Startup Aborted due to port conflict ==="
    [Environment]::Exit(1)
}

Start-Sleep -Seconds 1

# 3. Start Backend (FastAPI via run_server.py on port 8100)
$backendOut = Join-Path $env:TEMP "codex_backend.out.log"
$backendErr = Join-Path $env:TEMP "codex_backend.err.log"
$frontendOut = Join-Path $env:TEMP "codex_frontend.out.log"
$frontendErr = Join-Path $env:TEMP "codex_frontend.err.log"

Write-Output "Starting Backend (uvicorn backend.main:app on 127.0.0.1:8100)..."
$backendProc = Start-Process -FilePath "pythonw.exe" `
    -ArgumentList "run_server.py" `
    -WorkingDirectory $ROOT `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr `
    -WindowStyle Hidden `
    -PassThru

if ($backendProc -and $backendProc.Id) {
    $backendProc.Id | Out-File -FilePath $backendPidFile -Encoding ascii
    Write-Output "Backend started with PID: $($backendProc.Id)"
} else {
    Write-Error "Failed to start backend process."
    exit 1
}

# 4. Start Frontend (Vite on port 5180)
Write-Output "Starting Frontend (npm run dev on :5180)..."
$frontendProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c npm run dev" `
    -WorkingDirectory $FRONTEND `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr `
    -WindowStyle Hidden `
    -PassThru

if ($frontendProc -and $frontendProc.Id) {
    $frontendProc.Id | Out-File -FilePath $frontendPidFile -Encoding ascii
    Write-Output "Frontend started with PID: $($frontendProc.Id)"
} else {
    Write-Error "Failed to start frontend process."
    exit 1
}

# 5. Poll health endpoints
Write-Output ""
Write-Output "Waiting for services to become healthy..."
$backendHealthy = $false
$frontendHealthy = $false
$timeoutSeconds = 60
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

while ($stopwatch.Elapsed.TotalSeconds -lt $timeoutSeconds) {
    if (-not $backendHealthy) {
        try {
            $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8100/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($resp -and $resp.status -eq "healthy") {
                $backendHealthy = $true
                Write-Output "  [OK] Backend healthy (HTTP 200) at http://127.0.0.1:8100/health"
            }
        } catch {}
    }

    if (-not $frontendHealthy) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:5180/" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($resp -and $resp.StatusCode -eq 200) {
                $frontendHealthy = $true
                Write-Output "  [OK] Frontend active (HTTP 200) at http://127.0.0.1:5180/"
            }
        } catch {}
    }

    if ($backendHealthy -and $frontendHealthy) {
        break
    }

    Start-Sleep -Seconds 1
}

$stopwatch.Stop()

Write-Output ""
if ($backendHealthy -and $frontendHealthy) {
    Write-Output "=== Codex Control Centre is UP and HEALTHY ==="
    Write-Output "  Backend:  http://127.0.0.1:8100/ (PID: $($backendProc.Id))"
    Write-Output "  Frontend: http://127.0.0.1:5180/ (PID: $($frontendProc.Id))"
    exit 0
} else {
    if (-not $backendHealthy) {
        Write-Output "  [FAIL] Backend did not respond on http://127.0.0.1:8100/health"
    }
    if (-not $frontendHealthy) {
        Write-Output "  [FAIL] Frontend did not respond on http://127.0.0.1:5180/"
    }
    exit 1
}
