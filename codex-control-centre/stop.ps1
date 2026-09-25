# Codex Control Centre - Safe Stop Script
# Gracefully terminates backend and frontend process trees tracked in PID files.

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ROOT) { $ROOT = (Get-Location).Path }

$backendPidFile = Join-Path $ROOT ".codex_backend.pid"
$frontendPidFile = Join-Path $ROOT ".codex_frontend.pid"

function Stop-TrackedProcess {
    param (
        [string]$Name,
        [string]$PidFilePath,
        [int]$GraceTimeoutSeconds = 10
    )

    if (-not (Test-Path $PidFilePath)) {
        Write-Output "No PID file found for $Name ($($PidFilePath)). Process assumed stopped."
        return
    }

    $rawPid = (Get-Content $PidFilePath -Raw).Trim()
    if ($rawPid -notmatch "^\d+$") {
        Write-Output "Invalid PID in $($PidFilePath): '$rawPid'. Removing stale file."
        Remove-Item $PidFilePath -Force -ErrorAction SilentlyContinue
        return
    }

    $targetPid = [int]$rawPid
    $proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue

    if (-not $proc) {
        Write-Output "$Name (PID: $targetPid) is not currently running. Removing stale PID file."
        Remove-Item $PidFilePath -Force -ErrorAction SilentlyContinue
        return
    }

    Write-Output "Stopping $Name (PID: $targetPid and child processes)..."

    # Send graceful termination signal to process tree
    & taskkill /T /PID $targetPid 2>$null
    try {
        Stop-Process -Id $targetPid -ErrorAction SilentlyContinue
    } catch {}

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $exitedCleanly = $false

    while ($stopwatch.Elapsed.TotalSeconds -lt $GraceTimeoutSeconds) {
        $check = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
        if (-not $check -or $check.HasExited) {
            $exitedCleanly = $true
            break
        }
        Start-Sleep -Milliseconds 500
    }
    $stopwatch.Stop()

    if ($exitedCleanly) {
        Write-Output "  [OK] $Name (PID: $targetPid) exited gracefully."
    } else {
        Write-Output "  [WARN] $Name (PID: $targetPid) did not exit within $($GraceTimeoutSeconds) s. Forcing tree termination..."
        try {
            & taskkill /T /F /PID $targetPid 2>$null
            Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
        } catch {}
    }

    Remove-Item $PidFilePath -Force -ErrorAction SilentlyContinue
}

Write-Output "=== Stopping Codex Control Centre Services ==="

Stop-TrackedProcess -Name "Frontend" -PidFilePath $frontendPidFile -GraceTimeoutSeconds 10
Stop-TrackedProcess -Name "Backend" -PidFilePath $backendPidFile -GraceTimeoutSeconds 10

Write-Output "=== All tracked Codex Control Centre services stopped ==="
