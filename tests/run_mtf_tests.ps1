# PowerShell script to run MTF functional tests in virtual environment
# Usage: .\tests\run_mtf_tests.ps1

Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host "MTF CHOCH/BOS Implementation - Functional Tests" -ForegroundColor Cyan
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
$venvPath = ".\.venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "❌ Virtual environment not found at $venvPath" -ForegroundColor Red
    Write-Host "Please create a virtual environment first:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# Use venv Python directly (more reliable than activation)
$venvPython = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "❌ Python executable not found at $venvPython" -ForegroundColor Red
    exit 1
}

Write-Host "Using virtual environment Python: $venvPython" -ForegroundColor Green
Write-Host ""

# Check Python version
Write-Host "Python version:" -ForegroundColor Yellow
& $venvPython --version
Write-Host ""

# Check if required packages are installed
Write-Host "Checking required packages..." -ForegroundColor Yellow
$requiredPackages = @("pandas", "numpy")
$missingPackages = @()

foreach ($package in $requiredPackages) {
    $result = & $venvPython -c "import $package" 2>&1
    if ($LASTEXITCODE -ne 0) {
        $missingPackages += $package
        Write-Host "  ❌ $package not installed" -ForegroundColor Red
    } else {
        Write-Host "  ✅ $package installed" -ForegroundColor Green
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host ""
    Write-Host "⚠️  Missing packages detected. Installing..." -ForegroundColor Yellow
    & $venvPython -m pip install $missingPackages
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install required packages" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Running functional tests..." -ForegroundColor Yellow
Write-Host ""

# Run the test
& $venvPython tests/test_mtf_functional.py

$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "=================================================================================" -ForegroundColor Green
    Write-Host "✅ ALL TESTS PASSED" -ForegroundColor Green
    Write-Host "=================================================================================" -ForegroundColor Green
} else {
    Write-Host "=================================================================================" -ForegroundColor Red
    Write-Host "❌ SOME TESTS FAILED" -ForegroundColor Red
    Write-Host "=================================================================================" -ForegroundColor Red
}

exit $exitCode

