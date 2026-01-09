# Monitor Thread Reliability Fixes
**Date:** 2025-12-16  
**Status:** ✅ **FIXES IMPLEMENTED**

---

## 🔴 Critical Issue: Monitor Thread Keeps Stopping

### Root Cause Analysis

From error logs, I found:

1. **Fatal Errors Kill Thread**: When a fatal exception occurs in the monitor loop (one that breaks out of the `while` loop), the thread dies and `self.running` is set to `False`, but the thread doesn't restart automatically.

2. **Health Check Too Infrequent**: Health check was running every 5 minutes (300 seconds), which means a dead thread could go undetected for up to 5 minutes.

3. **Limited Restart Attempts**: Only 5 restart attempts before giving up.

4. **No Recovery from Fatal Errors**: Fatal errors that break the while loop don't trigger automatic restart.

---

## ✅ Fixes Implemented

### 1. More Aggressive Health Checking
**Before:** Health check every 5 minutes (300 seconds)  
**After:** Health check every 1 minute (60 seconds)

**Location:** `auto_execution_system.py` line 204
```python
self.health_check_interval = 60  # Check thread health every 1 minute (more aggressive)
```

**Impact:** Dead threads are detected and restarted within 1 minute instead of 5 minutes.

---

### 2. Increased Restart Attempts
**Before:** Maximum 5 restart attempts  
**After:** Maximum 10 restart attempts

**Location:** `auto_execution_system.py` line 206
```python
self.max_thread_restarts = 10  # Maximum restarts before giving up (increased from 5)
```

**Impact:** System can recover from more transient failures before giving up.

---

### 3. Improved Health Check Logic
**Enhancement:** Health check now detects when system should be running but thread is dead (e.g., after fatal error).

**Location:** `auto_execution_system.py` lines 5065-5083
```python
# Check if thread is alive
if not self.running:
    # If system should be running but thread is dead, restart it
    # This handles cases where fatal errors killed the thread
    if self.monitor_thread is None or not self.monitor_thread.is_alive():
        logger.warning(
            "System should be running but thread is dead. "
            "Attempting to restart (may have been killed by fatal error)..."
        )
        self.running = True  # Reset flag to allow restart
        self._restart_monitor_thread()
    return
```

**Impact:** System can recover even when `self.running` is False but thread died unexpectedly.

---

### 4. Enhanced Restart Method
**Enhancement:** Restart method now:
- Properly cleans up old thread before starting new one
- Verifies new thread actually started
- Handles edge cases where old thread is still alive

**Location:** `auto_execution_system.py` lines 5098-5140
```python
def _restart_monitor_thread(self):
    """Restart the monitor thread if it died"""
    # ... validation ...
    
    try:
        # Clean up old thread reference
        old_thread = self.monitor_thread
        if old_thread and old_thread.is_alive():
            logger.warning("Old monitor thread still alive, attempting to stop it...")
            self.running = False
            try:
                old_thread.join(timeout=2.0)
            except Exception as e:
                logger.debug(f"Error joining old thread: {e}")
        
        # ... start new thread ...
        
        # Verify thread actually started
        if self.monitor_thread.is_alive():
            logger.info("Monitor thread restarted successfully")
        else:
            logger.error("Monitor thread failed to start after restart attempt")
            self.running = False
```

**Impact:** More reliable thread restart with proper cleanup and verification.

---

### 5. Better Fatal Error Handling
**Enhancement:** Fatal errors now log that health check will restart the thread.

**Location:** `auto_execution_system.py` lines 4991-5008
```python
except Exception as fatal_error:
    # ... log error ...
    
    # Mark system as not running, but don't prevent restart
    # The health check will detect the thread died and restart it
    self.running = False
    
    # Log that health check should restart the thread
    logger.warning(
        f"Monitor thread died due to fatal error. "
        f"Health check will attempt to restart (max {self.max_thread_restarts} attempts remaining)"
    )
```

**Impact:** Clear logging that system will attempt to recover from fatal errors.

---

### 6. Error Handling in get_status()
**Enhancement:** Health check in `get_status()` now has error handling to prevent status check from failing if health check has issues.

**Location:** `auto_execution_system.py` lines 5132-5138
```python
def get_status(self, include_all_statuses: bool = False) -> Dict[str, Any]:
    """Get system status"""
    # ALWAYS check thread health before returning status (critical for reliability)
    # This ensures the thread is restarted if it died, even if health_check_interval hasn't passed
    try:
        self._check_thread_health()
    except Exception as e:
        logger.error(f"Error in health check during get_status: {e}", exc_info=True)
```

**Impact:** Status endpoint is more resilient and always attempts health check.

---

## 📊 Expected Behavior After Fixes

### Normal Operation:
1. Monitor thread runs continuously
2. Health check runs every 60 seconds
3. If thread dies, health check detects it within 60 seconds
4. Thread is automatically restarted (up to 10 times)
5. System continues monitoring plans

### After Fatal Error:
1. Fatal error occurs in monitor loop
2. Thread dies, `self.running` set to `False`
3. Error is logged with full traceback
4. Health check detects dead thread (within 60 seconds)
5. Thread is automatically restarted
6. System continues monitoring plans

### Recovery Limits:
- **Maximum restarts:** 10 attempts
- **Health check frequency:** Every 60 seconds
- **Thread restart timeout:** 2 seconds to join old thread

---

## 🔍 Monitoring & Debugging

### Check System Status:
```python
from auto_execution_system import get_auto_execution_system
system = get_auto_execution_system()
status = system.get_status()
print(f"Running: {status['running']}")
print(f"Thread alive: {system.monitor_thread.is_alive() if system.monitor_thread else 'None'}")
```

### Check Logs for Errors:
- Look for: `"FATAL ERROR in monitor loop"`
- Look for: `"Monitor thread died! Restarting..."`
- Look for: `"Monitor thread restarted successfully"`

### Common Error Patterns:
1. **Fatal errors** → Thread dies → Health check restarts (within 60s)
2. **MT5 connection failures** → Thread continues (handled gracefully)
3. **Database errors** → Thread continues (handled gracefully)
4. **Plan execution errors** → Thread continues (handled gracefully)

---

## ✅ Verification

After these fixes:
- ✅ Health check runs every 60 seconds (instead of 300)
- ✅ System can restart up to 10 times (instead of 5)
- ✅ Health check detects dead threads even when `self.running` is False
- ✅ Restart method properly cleans up old threads
- ✅ Fatal errors trigger automatic recovery
- ✅ Status endpoint always attempts health check

---

## 🎯 Next Steps

1. **Monitor logs** for fatal errors to identify root causes
2. **Track restart count** to see if 10 is sufficient
3. **Consider reducing health check interval further** if needed (e.g., 30 seconds)
4. **Add alerting** when restart count approaches maximum

---

**Files Modified:**
- `auto_execution_system.py` (lines 203-206, 4991-5008, 5053-5096, 5098-5140, 5132-5138)

