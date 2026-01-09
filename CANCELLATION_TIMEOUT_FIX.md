# Cancellation Timeout Fix

**Date:** 2025-11-30  
**Issue:** Cancellation requests timing out due to lock contention

---

## 🔍 **Problem**

Cancellation requests were timing out with error:
```
⚠️ The cancellation request for plan chatgpt_6322ced2 is still failing due to a server-side response timeout — likely the agent is busy syncing auto-plan states.
```

**Root Cause:**
1. `cancel_plan()` method held `plans_lock` for too long
2. `_cleanup_plan_resources()` also used `plans_lock`, causing nested lock acquisition
3. If monitoring thread was checking conditions, it could hold the lock for >30 seconds
4. HTTP timeout was only 30 seconds, causing client-side timeout

---

## ✅ **Fixes Applied**

### **1. Optimized `cancel_plan()` Method**
**File:** `auto_execution_system.py`

**Changes:**
- ✅ Database update first (fast, no lock needed)
- ✅ Minimize `plans_lock` time - only get symbol and remove from dict
- ✅ Move cleanup outside of `plans_lock` to avoid nested locks
- ✅ Added database timeout (5 seconds) to prevent hanging

**Before:**
```python
with self.plans_lock:
    if plan_id in self.plans:
        plan_symbol = self.plans[plan_id].symbol
        del self.plans[plan_id]
        self._cleanup_plan_resources(plan_id, plan_symbol)  # Nested lock!
```

**After:**
```python
# Get symbol quickly (minimal lock time)
plan_symbol = None
with self.plans_lock:
    if plan_id in self.plans:
        plan_symbol = self.plans[plan_id].symbol
        del self.plans[plan_id]

# Clean up separately (no nested lock)
if plan_symbol:
    self._cleanup_plan_resources(plan_id, plan_symbol)
```

### **2. Optimized `_cleanup_plan_resources()` Method**
**File:** `auto_execution_system.py`

**Changes:**
- ✅ Use non-blocking lock acquisition for cache cleanup
- ✅ If lock is held, skip cache cleanup (non-critical operation)
- ✅ Prevents blocking cancellation if monitoring thread is active

**Before:**
```python
with self.plans_lock:  # Could block if monitoring thread holds it
    other_plans_use_symbol = any(...)
    if not other_plans_use_symbol:
        # Clean up cache
```

**After:**
```python
# Try to acquire lock with timeout (non-blocking check)
if self.plans_lock.acquire(blocking=False):
    try:
        # Check and clean up
    finally:
        self.plans_lock.release()
else:
    # Lock is held - skip cache cleanup (non-critical)
    logger.debug("Could not acquire plans_lock for cache cleanup")
```

### **3. Increased HTTP Timeout**
**File:** `chatgpt_auto_execution_tools.py`

**Changes:**
- ✅ Increased timeout from 30s to 60s for cancellation requests
- ✅ Gives more time for lock acquisition if needed

**Before:**
```python
async with httpx.AsyncClient(timeout=30.0) as client:
```

**After:**
```python
# Use longer timeout for cancellation (60s) as it may need to wait for locks
async with httpx.AsyncClient(timeout=60.0) as client:
```

### **4. Improved API Response**
**File:** `app/auto_execution_api.py`

**Changes:**
- ✅ Better error handling and logging
- ✅ Idempotent response (returns success even if plan not found)
- ✅ More informative error messages

**Before:**
```python
result = auto_execution.cancel_plan(plan_id)
return result  # Just returns boolean
```

**After:**
```python
result = auto_execution.cancel_plan(plan_id)
if result:
    return {"success": True, "message": f"Plan {plan_id} cancelled successfully"}
else:
    # Idempotent - still return success
    return {"success": True, "message": f"Plan {plan_id} not found or already cancelled"}
```

---

## 📊 **Expected Impact**

1. **Faster Cancellation:**
   - Lock time reduced from potentially 30s+ to <1s
   - Database update is fast (no lock needed)
   - Cache cleanup is non-blocking

2. **Better Reliability:**
   - Cancellation won't timeout even if monitoring thread is active
   - Non-critical operations (cache cleanup) won't block cancellation
   - Idempotent operation (safe to retry)

3. **Improved Error Handling:**
   - Better logging for debugging
   - More informative error messages
   - Graceful degradation if locks are held

---

## ✅ **Status: COMPLETE**

All fixes have been applied and tested. Cancellation should now be:
- ✅ **Faster** (minimal lock time)
- ✅ **More reliable** (non-blocking cleanup)
- ✅ **More resilient** (longer timeout, better error handling)

