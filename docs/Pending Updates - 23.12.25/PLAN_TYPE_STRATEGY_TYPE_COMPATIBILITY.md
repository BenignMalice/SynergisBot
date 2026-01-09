# plan_type / strategy_type Compatibility Fix

**Date:** 2025-12-24  
**Status:** ✅ **IMPLEMENTED**

---

## 🔍 **Problem**

ChatGPT was using `plan_type` in conditions instead of `strategy_type`, causing plans to show as "unknown" strategy type and be blocked in Asian session even when they had appropriate strategies like `range_scalp`.

**Example:**
```json
{
  "conditions": {
    "plan_type": "range_scalp",  // ❌ ChatGPT used plan_type
    "require_active_session": true
  }
}
```

**Result:** System checked `strategy_type` (not found) → treated as "unknown" → blocked in Asian session

---

## ✅ **Solution**

Updated system to accept **both** `strategy_type` and `plan_type` for compatibility.

---

## 🔧 **Implementation**

### **Files Updated:**

1. **`auto_execution_system.py`** - Session blocking logic (line 4088-4090)
2. **`auto_execution_system.py`** - Strategy validation (line 3369)
3. **`auto_execution_system.py`** - Trade execution (line 6422)

### **Code Changes:**

**Before:**
```python
strategy_type = plan.conditions.get("strategy_type") or plan.strategy_type
```

**After:**
```python
# Accept both strategy_type and plan_type for compatibility
strategy_type = (
    plan.conditions.get("strategy_type") or 
    plan.conditions.get("plan_type") or 
    plan.strategy_type or
    getattr(plan, 'plan_type', None)
)
```

---

## 📊 **Impact**

### **Before Fix:**
- Plans with `plan_type: "range_scalp"` → Showed as "unknown" → **BLOCKED** in Asian session
- 4 plans incorrectly blocked

### **After Fix:**
- Plans with `plan_type: "range_scalp"` → Correctly detected as `range_scalp` → **ALLOWED** in Asian session
- All 4 plans now valid ✅

---

## ✅ **Validation Results**

**After fix:**
- ✅ `chatgpt_b420dcd2` (XAUUSDc BUY) - `plan_type: range_scalp` → **Valid, allowed in Asian session**
- ✅ `chatgpt_cd288d7b` (XAUUSDc BUY) - `plan_type: range_scalp` → **Valid, allowed in Asian session**
- ✅ `chatgpt_b14df55f` (XAUUSDc SELL) - `plan_type: range_scalp` → **Valid, allowed in Asian session**
- ✅ `chatgpt_1c775984` (XAUUSDc SELL) - `plan_type: range_scalp` → **Valid, allowed in Asian session**

**Still blocked (correctly):**
- ❌ `chatgpt_0980d189` (XAUUSDc BUY) - `strategy_type: trend_continuation_pullback` → **Correctly blocked** (inappropriate for Asian session)

---

## 📝 **Locations Updated**

1. **Session Blocking Logic** (`auto_execution_system.py` line 4088-4090):
   - Checks both `strategy_type` and `plan_type` when determining if strategy is Asian-appropriate

2. **Strategy Validation** (`auto_execution_system.py` line 3369):
   - Validates strategy-specific conditions using both fields

3. **Trade Execution** (`auto_execution_system.py` line 6422):
   - Gets strategy type for Universal Manager registration using both fields

---

## 🎯 **Result**

**System now accepts both:**
- ✅ `strategy_type: "range_scalp"` (preferred)
- ✅ `plan_type: "range_scalp"` (also accepted)

**Both work identically** - system treats them the same way.

---

## ✅ **Summary**

**Problem:** ChatGPT using `plan_type` instead of `strategy_type` caused plans to be incorrectly blocked.

**Solution:** System now accepts both `strategy_type` and `plan_type` for compatibility.

**Result:** Plans with `plan_type: "range_scalp"` are now correctly detected and allowed in Asian session.

**Status:** ✅ **FIXED** - All plans with `plan_type` are now correctly validated.
