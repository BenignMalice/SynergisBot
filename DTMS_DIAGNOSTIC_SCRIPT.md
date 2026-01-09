# DTMS Diagnostic Script

## Overview

The `diagnose_dtms.py` script provides comprehensive diagnostics for the DTMS (Defensive Trade Management System) initialization and status.

## Features

The diagnostic script checks:

1. **DTMS Engine Status** (`dtms_integration.py`)
   - Initialization status
   - Monitoring status
   - Active trades count
   - System uptime
   - Component availability (data manager, signal scorer, action executor)

2. **DTMS Unified Pipeline Integration**
   - Initialization status
   - Active status
   - Monitored trades count
   - Integration with Unified Tick Pipeline

3. **Service Dependencies**
   - MT5 Service availability
   - Binance Service availability
   - OrderFlow Service availability

4. **Trade Registration**
   - Engine initialization check
   - `auto_register_dtms` function availability
   - Active trades count and details

5. **Monitoring Status**
   - Monitoring active/inactive status
   - Background task status
   - Monitoring cycle execution

6. **Summary Report**
   - List of detected issues
   - Actionable recommendations
   - Key status overview

## Usage

```bash
python diagnose_dtms.py
```

## Expected Output

The script will output:
- Status for each component (OK, FAIL, WARN, INFO)
- Detailed information about each check
- Summary of issues found
- Recommendations for fixing issues
- Key status overview

## Example Output

```
================================================================================
DTMS DIAGNOSTIC TOOL
================================================================================

[1/6] Checking DTMS Engine (dtms_integration.py)...
  [OK] DTMS Engine initialized
  [OK] Monitoring active: True
  [OK] Active trades: 2
  [OK] Uptime: 2:15:30

[2/6] Checking DTMS Unified Pipeline Integration...
  [OK] DTMS Unified Pipeline initialized: True
  [OK] DTMS Unified Pipeline active: True
  [INFO] Monitored trades: 2

[3/6] Checking Service Dependencies...
  [OK] MT5 service available
  [OK] Binance service available
  [OK] OrderFlow service available

[4/6] Checking Trade Registration...
  [OK] 2 trades registered and monitored
    - Ticket 12345: BTCUSDc BUY (State: NORMAL)
    - Ticket 12346: EURUSDc SELL (State: WARNING)

[5/6] Checking Monitoring Status...
  [OK] DTMS monitoring is active

[6/6] Generating Summary...

================================================================================
DIAGNOSTIC SUMMARY
================================================================================

[SUCCESS] No issues detected!

[KEY STATUS]

  DTMS Engine: [OK] Initialized
  Monitoring: [OK] Active
  Active Trades: 2

  Services:
    MT5: [OK]
    Binance: [OK]
    OrderFlow: [OK]
```

## Common Issues Detected

1. **DTMS Engine Not Initialized**
   - **Cause**: `initialize_dtms()` not called in `chatgpt_bot.py` or `main_api.py`
   - **Fix**: Ensure DTMS initialization code runs on startup

2. **Monitoring Not Active**
   - **Cause**: `start_dtms_monitoring()` not called after initialization
   - **Fix**: Call `start_dtms_monitoring()` after successful initialization

3. **Services Not Available**
   - **Cause**: Services not initialized or running in different process
   - **Fix**: Ensure services are initialized before DTMS initialization

4. **No Trades Registered**
   - **Cause**: `auto_register_dtms()` not called after trade execution, or engine not initialized
   - **Fix**: Ensure `auto_register_dtms()` is called after trade execution

## Integration Points

The diagnostic script checks:
- `dtms_integration.py` - Main DTMS integration module
- `dtms_integration/dtms_system.py` - DTMS system functions
- `dtms_unified_pipeline_integration.py` - Unified pipeline integration
- `chatgpt_bot.py` - DTMS initialization in ChatGPT bot
- `app/main_api.py` - DTMS initialization in main API
- `dtms_core/dtms_engine.py` - DTMS engine core

## Notes

- The script can be run independently without requiring the main application to be running
- Some checks (like Unified Pipeline) may show warnings if `main_api.py` is not running - this is expected
- Service availability checks look for instances in `chatgpt_bot.py` or `desktop_agent.py` modules
- The script handles import errors gracefully and provides informative messages

