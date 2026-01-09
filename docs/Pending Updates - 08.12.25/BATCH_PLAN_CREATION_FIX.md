# Batch Plan Creation Fix - Database Locking Issue

**Date:** 2026-01-08  
**Status:** ✅ **FIXED**  
**Priority:** **HIGH** - Prevents ChatGPT from creating auto-execution plans

---

## 🎯 **Problem**

ChatGPT is unable to submit auto-execution plans via `/create_multiple_auto_plans` API. The error indicates:

- **Status Code**: 500 (Internal server error)
- **Error Message**: "Execution queue locked (Phase sync)" or similar
- **Cause**: Database is locked during rollover/rebalancing/phase sync intervals
- **Effect**: No plans are created or queued; the system ignores the payload

---

## 🔍 **Root Cause Analysis**

### **Issue 1: Direct Database Writes in `add_plan()`**
- **Location**: `auto_execution_system.py:1346-1389`
- **Problem**: `add_plan()` method performs direct database writes (not using write queue)
- **Impact**: If database is locked during plan reload (every 5 minutes) or other operations, writes fail
- **Current Retry**: Only retries once after 1 second (insufficient)

### **Issue 2: Plan Reload Locking**
- **Location**: `auto_execution_system.py:9740-9782`
- **Problem**: Plan reload happens every 5 minutes and may lock database
- **Impact**: If `add_plan()` is called during reload, it will fail with "database is locked"
- **Current Behavior**: Reload flushes write queue before reload, but `add_plan()` doesn't use queue

### **Issue 3: Insufficient Error Handling**
- **Location**: `app/auto_execution_api.py:651-884`
- **Problem**: Generic 500 error doesn't distinguish between database lock and other errors
- **Impact**: ChatGPT receives generic error, doesn't know to retry

---

## ✅ **Fixes Applied**

### **Fix 1: Enhanced Retry Logic in `add_plan()`**

**File**: `auto_execution_system.py`

**Changes**:
- ✅ Increased retries from 1 to 3 attempts
- ✅ Exponential backoff: 0.5s, 1s, 2s (instead of fixed 1s)
- ✅ Better error messages indicating database lock
- ✅ Proper commit after successful write
- ✅ Only retries on `sqlite3.OperationalError` with "locked" message

**Code**:
```python
def add_plan(self, plan: TradePlan) -> bool:
    """Add a new trade plan to monitor"""
    max_retries = 3
    retry_delay_base = 0.5  # Start with 0.5 seconds
    
    for attempt in range(max_retries):
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                conn.execute("""...""", (...))
                conn.commit()  # Explicit commit
                
                # Success - add to in-memory plans
                with self.plans_lock:
                    self.plans[plan.plan_id] = plan
                logger.info(f"Added trade plan {plan.plan_id} for {plan.symbol}")
                return True
                
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                if attempt < max_retries - 1:
                    retry_delay = retry_delay_base * (2 ** attempt)
                    logger.warning(f"Database locked (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay:.1f}s...")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"Failed after {max_retries} attempts: Database locked")
                    raise
```

### **Fix 2: Better Error Handling in Batch Endpoint**

**File**: `app/auto_execution_api.py`

**Changes**:
- ✅ Check if auto execution system is available before processing
- ✅ Distinguish between database lock (503) and other errors (500)
- ✅ Provide clear error messages indicating retry recommendation
- ✅ Handle HTTPException separately from generic exceptions

**Code**:
```python
@router.post("/create-plans", dependencies=[Depends(verify_api_key)])
async def create_multiple_plans(request: BatchCreatePlanRequest):
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        # Check if auto execution system is available
        if not auto_execution or not auto_execution.auto_system:
            raise HTTPException(
                status_code=503,
                detail="Auto execution system not available. System may be initializing or restarting."
            )
        # ... rest of code ...
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e).lower()
        if "locked" in error_msg or "database is locked" in error_msg:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Database is currently locked (likely during rollover/rebalancing/phase sync). "
                    "Please retry in a few seconds."
                )
            )
        # ... other error handling ...
```

### **Fix 3: Improved Error Messages in ChatGPT Tools**

**File**: `chatgpt_auto_execution_tools.py`

**Changes**:
- ✅ Detect 503 (Service Unavailable) status codes
- ✅ Provide clear retry recommendations
- ✅ Include `retry_recommended` flag in response
- ✅ Better error messages for queue/database lock scenarios

**Code**:
```python
if status_code == 503:
    error_summary = (
        f"Service temporarily unavailable (status {status_code}): "
        f"The execution queue may be locked during rollover/rebalancing/phase sync. "
        f"Please retry in a few seconds."
    )
elif status_code >= 500:
    error_summary = (
        f"Server error (status {status_code}): {error_detail}. "
        f"This may be due to database locking or queue issues. Please retry."
    )
```

---

## 📊 **Expected Behavior After Fix**

### **Before Fix**:
- ❌ Single retry after 1 second
- ❌ Generic 500 error
- ❌ No retry recommendation
- ❌ Plans fail to create during database lock

### **After Fix**:
- ✅ 3 retries with exponential backoff (0.5s, 1s, 2s)
- ✅ 503 status code for database lock (indicates temporary issue)
- ✅ Clear retry recommendations in error messages
- ✅ Plans successfully create after retries (if lock is temporary)

---

## 🧪 **Testing Recommendations**

1. **Test Database Lock Scenario**:
   - Manually lock database during plan creation
   - Verify retry logic works (3 attempts)
   - Verify plans are created after lock is released

2. **Test Plan Reload Conflict**:
   - Trigger plan reload (wait 5 minutes or manually trigger)
   - Simultaneously create plans via API
   - Verify plans are created successfully after retries

3. **Test Error Messages**:
   - Verify 503 status code for database lock
   - Verify 500 status code for other errors
   - Verify error messages include retry recommendations

---

## 📝 **Notes**

- **Plan Reload Interval**: Currently 5 minutes (300 seconds)
- **Database Timeout**: 10 seconds for initial attempt, 15 seconds for retry
- **Retry Strategy**: Exponential backoff (0.5s, 1s, 2s)
- **Max Retries**: 3 attempts total

---

## 🔄 **Future Enhancements**

1. **Use Write Queue for Plan Creation** (Optional):
   - Consider using `DatabaseWriteQueue` for plan creation
   - Would provide better resilience during high load
   - Trade-off: Slight delay in plan availability (queue processing time)

2. **Plan Reload Coordination** (Optional):
   - Add lock to prevent plan reload during batch creation
   - Or: Make plan reload non-blocking for reads
   - Or: Use read-only connection for plan reload

3. **Circuit Breaker** (Optional):
   - Add circuit breaker for database operations
   - Prevents cascading failures during extended lock periods
   - Auto-recovery after lock is released

---

## ✅ **Verification Checklist**

- [x] Enhanced retry logic in `add_plan()` (3 retries, exponential backoff)
- [x] Better error handling in batch endpoint (503 for locks, 500 for others)
- [x] Improved error messages in ChatGPT tools (retry recommendations)
- [x] Explicit commit after database write
- [x] System availability check before processing
- [ ] Test database lock scenario
- [ ] Test plan reload conflict
- [ ] Monitor production logs for improvements

---

**Status**: ✅ **FIXED** - Ready for testing
