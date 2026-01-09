# Test Scripts Usage Guide

## Using Virtual Environment (venv)

All test scripts should be run using the project's virtual environment (`.venv`).

### Method 1: Activate venv first (Recommended)

**Windows PowerShell:**
```powershell
# Activate venv
.venv\Scripts\Activate.ps1

# Run test scripts
python test_atr_calculation.py
python monitor_trailing_failures.py
python verify_trade_management.py
```

**Windows Command Prompt:**
```cmd
# Activate venv
.venv\Scripts\activate.bat

# Run test scripts
python test_atr_calculation.py
python monitor_trailing_failures.py
python verify_trade_management.py
```

### Method 2: Use venv Python directly

**Windows:**
```powershell
.venv\Scripts\python.exe test_atr_calculation.py
.venv\Scripts\python.exe monitor_trailing_failures.py
.venv\Scripts\python.exe verify_trade_management.py
```

### Method 3: Use helper script

**Windows PowerShell:**
```powershell
# Show available scripts
.\run_tests_with_venv.ps1

# Run specific script
.\run_tests_with_venv.ps1 test_atr_calculation.py
.\run_tests_with_venv.ps1 monitor_trailing_failures.py
.\run_tests_with_venv.ps1 verify_trade_management.py
```

---

## Available Test Scripts

### 1. `test_atr_calculation.py`

Tests ATR calculation for XAUUSD across multiple methods:
- Streamer Data Access
- Universal Manager
- Direct MT5

Also tests fallback trailing methods (fixed distance and percentage-based).

**Usage:**
```powershell
.venv\Scripts\python.exe test_atr_calculation.py
```

**What it does:**
- Tests ATR calculation for XAUUSD on M1, M5, M15, M30, H1 timeframes
- Tests all three ATR calculation methods
- Tests fallback trailing methods
- Provides recommendations if issues are found

---

### 2. `monitor_trailing_failures.py`

Monitors trailing stop failures and ATR calculation issues:
- Checks log files for ATR failures
- Checks current positions
- Provides monitoring summary

**Usage:**
```powershell
.venv\Scripts\python.exe monitor_trailing_failures.py
```

**What it does:**
- Searches log files for ATR failure warnings
- Lists open positions and their status
- Checks if break-even is set
- Provides recommendations

---

### 3. `verify_trade_management.py`

Verifies that trades are properly managed by Universal Manager:
- Checks trade registration
- Verifies break-even status
- Checks trailing stop activity

**Usage:**
```powershell
.venv\Scripts\python.exe verify_trade_management.py
```

**What it does:**
- Gets all open positions
- Checks if trades are registered with Universal Manager
- Verifies break-even has been triggered
- Indicates if trailing stops should be active

---

## Troubleshooting

### Venv not found

If you get an error that `.venv` doesn't exist:

1. Check if `.venv` directory exists in project root
2. If missing, create venv:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

### Import errors

If you get import errors when running tests:

1. Ensure venv is activated
2. Check that all dependencies are installed:
   ```powershell
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

### MT5 connection errors

If tests fail with MT5 connection errors:

1. Ensure MetaTrader 5 is running
2. Check that MT5 terminal is logged in
3. Verify symbol names (e.g., `XAUUSDc` not `XAUUSD`)

---

## Notes

- All test scripts include venv detection and will warn if not running in venv
- Scripts can still run with system Python, but venv is recommended
- Test scripts use ASCII-only output to avoid encoding issues on Windows
