# API Server Log Check Instructions

## 🔍 Where to Find API Server Logs

The API server (`app/main_api.py`) runs in a **separate console window** opened by `start_all_services.bat`.

**Window Title**: `App API (8000)`

The logs are displayed in **real-time** in that console window (stdout/stderr).

## ✅ What to Look For

### Expected Startup Messages

When the API server starts, you should see these messages in sequence:

1. **Initialization Start**:
   ```
   [INFO] Initializing services...
   ```

2. **Auto-Execution System Initialization**:
   ```
   [INFO] 🤖 Initializing Auto-Execution System...
   ```

3. **Auto-Execution System Started**:
   ```
   [INFO] ✅ Auto-Execution System started
   [INFO]    → Monitoring pending trade plans
   [INFO]    → Checking conditions every 30 seconds
   [INFO]    → Automatic execution when conditions are met
   ```

4. **Monitor Thread Started** (from auto_execution_system.py):
   ```
   [INFO] Auto execution system monitoring loop started (thread: AutoExecutionMonitor)
   ```

5. **Watchdog Thread Started** (from auto_execution_system.py):
   ```
   [INFO] Watchdog thread started (thread: AutoExecutionWatchdog)
   [INFO] Watchdog thread started successfully
   [INFO] Auto execution system started (thread: AutoExecutionMonitor, daemon: False)
   [INFO] Watchdog thread started for continuous health monitoring
   ```

### Error Messages to Watch For

If you see any of these, there's a problem:

1. **Initialization Failed**:
   ```
   [ERROR] ❌ Auto-Execution System initialization failed: <error message>
   [WARNING]    → Auto-execution plans will not be monitored
   ```

2. **Exception During Startup**:
   ```
   [ERROR] Startup error: <error message>
   ```

3. **Import Errors**:
   ```
   [ERROR] ModuleNotFoundError: No module named 'auto_execution_system'
   ```

## 🔧 How to Check

1. **Find the Console Window**:
   - Look for a window titled `App API (8000)`
   - This is where the API server logs are displayed

2. **Scroll to Startup Messages**:
   - Scroll up to see the startup sequence
   - Look for the messages listed above

3. **Check for Errors**:
   - Look for any `[ERROR]` or `[WARNING]` messages
   - Pay special attention to messages containing "Auto-Execution" or "execution"

## 📊 Current Status

- **API Server Process**: Running (PID 29860, Port 8000)
- **Server Status**: Listening on port 8000
- **API Endpoint**: Timing out (may be busy or still initializing)

## 🎯 Next Steps

1. **Check the Console Window**:
   - Open the `App API (8000)` window
   - Scroll to the top to see startup messages
   - Look for the auto-execution system initialization messages

2. **If Messages Are Missing**:
   - The startup event may not be executing
   - Check for exceptions in the console
   - Verify the server started successfully

3. **If Errors Are Present**:
   - Note the exact error message
   - Check if it's an import error, initialization error, or runtime error
   - The error message will indicate what needs to be fixed

## 💡 Alternative: Check via Code

The startup code is in `app/main_api.py` lines 1397-1410:

```python
# Initialize and start Auto-Execution System
try:
    logger.info("🤖 Initializing Auto-Execution System...")
    from auto_execution_system import start_auto_execution_system
    
    # Start the auto-execution system monitoring
    start_auto_execution_system()
    logger.info("✅ Auto-Execution System started")
    logger.info("   → Monitoring pending trade plans")
    logger.info("   → Checking conditions every 30 seconds")
    logger.info("   → Automatic execution when conditions are met")
except Exception as e:
    logger.error(f"❌ Auto-Execution System initialization failed: {e}", exc_info=True)
    logger.warning("   → Auto-execution plans will not be monitored")
```

This code **should** execute when the API server starts via the `startup_event()` function.

