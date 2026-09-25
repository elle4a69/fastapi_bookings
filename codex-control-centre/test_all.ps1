# Codex Control Centre - Master Quality Gates Verification Runner
# Executes all backend and frontend quality gates and prints a unified status matrix.

$ErrorActionPreference = "Continue"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ROOT) { $ROOT = (Get-Location).Path }
$FRONTEND = Join-Path $ROOT "frontend"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "       CODEX CONTROL CENTRE - MASTER QUALITY GATES RUNNER        " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Root Directory: $ROOT" -ForegroundColor Gray
Write-Host ""

$gates = [System.Collections.Generic.List[PSCustomObject]]::new()

function Run-Gate {
    param (
        [string]$GateId,
        [string]$GateName,
        [scriptblock]$Command,
        [string]$Directory = $ROOT
    )
    Write-Host ">> Executing Gate [$GateId]: $GateName..." -ForegroundColor Yellow
    $startTime = Get-Date
    $passed = $false
    $errorMsg = ""
    
    try {
        Push-Location $Directory
        & $Command
        if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
            $passed = $true
        } else {
            $errorMsg = "Exited with code " + $LASTEXITCODE
        }
    } catch {
        $errorMsg = $_.Exception.Message
    } finally {
        Pop-Location
    }

    $duration = [Math]::Round(((Get-Date) - $startTime).TotalSeconds, 2)
    $statusStr = if ($passed) { "PASS" } else { "FAIL" }
    
    if ($passed) {
        $msg = "   [PASS] " + $GateName + " [" + $duration + "s]"
        Write-Host $msg -ForegroundColor Green
    } else {
        $msg = "   [FAIL] " + $GateName + " - " + $errorMsg + " [" + $duration + "s]"
        Write-Host $msg -ForegroundColor Red
    }
    Write-Host ""

    $gates.Add([PSCustomObject]@{
        GateId   = $GateId
        Name     = $GateName
        Status   = $statusStr
        Duration = "$duration s"
        Details  = if ($passed) { "Passed without errors" } else { $errorMsg }
    })
}

# -----------------------------------------------------------------------------
# 1. Backend Quality Gates
# -----------------------------------------------------------------------------
Write-Host "--- BACKEND QUALITY GATES ---" -ForegroundColor Magenta

Run-Gate -GateId "QG-BE-01" -GateName "Python Ruff Linting" -Command {
    python -m ruff check backend tests
}

Run-Gate -GateId "QG-BE-02" -GateName "Python Mypy Typechecking" -Command {
    python -m mypy backend
}

Run-Gate -GateId "QG-BE-03" -GateName "Pytest Suite (Unit, Integration, E2E)" -Command {
    python -m pytest tests/ -v
}

Run-Gate -GateId "QG-BE-04" -GateName "Python Dependency Security Audit" -Command {
    python scripts/audit_dependencies.py
}

# -----------------------------------------------------------------------------
# 2. Frontend Quality Gates
# -----------------------------------------------------------------------------
Write-Host "--- FRONTEND QUALITY GATES ---" -ForegroundColor Magenta

Run-Gate -GateId "QG-FE-01" -GateName "Frontend Syntax and Static Analysis" -Directory $FRONTEND -Command {
    npm run lint
}

Run-Gate -GateId "QG-FE-02" -GateName "Frontend TypeScript Typechecking" -Directory $FRONTEND -Command {
    npm run typecheck
}

Run-Gate -GateId "QG-FE-03" -GateName "Frontend Vitest Unit and WCAG A11y Suite" -Directory $FRONTEND -Command {
    npm test
}

Run-Gate -GateId "QG-FE-04" -GateName "Frontend Production Build and Code Splitting" -Directory $FRONTEND -Command {
    npm run build
}

Run-Gate -GateId "QG-FE-05" -GateName "Node Dependency Audit" -Directory $FRONTEND -Command {
    npm audit --package-lock-only
}

# -----------------------------------------------------------------------------
# Summary Matrix Report
# -----------------------------------------------------------------------------
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "                QUALITY GATES VERIFICATION MATRIX                " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$allPassed = $true
foreach ($g in $gates) {
    $statusColor = if ($g.Status -eq "PASS") { "Green" } else { "Red" }
    $row = "  " + $g.GateId.PadRight(10) + " | " + $g.Name.PadRight(44) + " | " + $g.Status.PadRight(6) + " | " + $g.Duration
    Write-Host $row -ForegroundColor $statusColor
    if ($g.Status -ne "PASS") { $allPassed = $false }
}

Write-Host "-----------------------------------------------------------------" -ForegroundColor Gray

if ($allPassed) {
    Write-Host "ALL QUALITY GATES PASSED (100 Percent SUCCESS)!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "SOME QUALITY GATES FAILED. Please review the output above." -ForegroundColor Red
    exit 1
}
