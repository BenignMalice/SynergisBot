# PowerShell script to run tests with venv
# Usage: .\run_tests_with_venv.ps1 [test_script_name]

param(
    [string]$TestScript = ""
)

$venvPython = ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: Venv not found at $venvPython" -ForegroundColor Red
    Write-Host "Please ensure .venv exists in the project root" -ForegroundColor Yellow
    exit 1
}

Write-Host "Using venv Python: $venvPython" -ForegroundColor Green

if ($TestScript -eq "") {
    Write-Host ""
    Write-Host "Available test scripts:" -ForegroundColor Cyan
    Write-Host "  1. test_atr_calculation.py - Test ATR calculation"
    Write-Host "  2. monitor_trailing_failures.py - Monitor trailing stop failures"
    Write-Host "  3. verify_trade_management.py - Verify trade management"
    Write-Host ""
    Write-Host "Usage: .\run_tests_with_venv.ps1 <script_name>" -ForegroundColor Yellow
    Write-Host "Example: .\run_tests_with_venv.ps1 test_atr_calculation.py" -ForegroundColor Yellow
} else {
    if (-not (Test-Path $TestScript)) {
        Write-Host "ERROR: Test script not found: $TestScript" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Running: $TestScript" -ForegroundColor Cyan
    Write-Host ""
    & $venvPython $TestScript
}
