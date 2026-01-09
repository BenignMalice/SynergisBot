# Negative Candle Age Fix

**Date:** 2025-12-21  
**Issue:** Negative candle age (-177 minutes) occurring frequently  
**Status:** ✅ **FIXED**

---

## 🔍 **Root Cause**

**Problem:** MT5 candle timestamps are in UTC, but `datetime.fromtimestamp()` without `tz` parameter interprets them as **local time**, causing negative age when system timezone differs from UTC.

**Example:**
- MT5 timestamp: `1734780000` (UTC: 2024-12-21 08:00:00 UTC)
- System timezone: UTC+3 (for example)
- `datetime.fromtimestamp(1734780000)` → Creates `2024-12-21 11:00:00` (local time)
- `datetime.now(timezone.utc)` → `2024-12-21 08:00:00 UTC`
- Age calculation: `08:00 - 11:00 = -3 hours` ❌

**Correct:**
- `datetime.fromtimestamp(1734780000, tz=timezone.utc)` → Creates `2024-12-21 08:00:00 UTC`
- Age calculation: `08:00 - 08:00 = 0 hours` ✅

---

## ✅ **Fixes Applied**

### **1. Fixed `infra/range_scalping_risk_filters.py`**

**Line 819 (MT5 Direct Fetch):**
```python
# BEFORE (WRONG):
candle_time = datetime.fromtimestamp(latest_candle['time'])
if candle_time.tzinfo is None:
    candle_time = candle_time.replace(tzinfo=timezone.utc)

# AFTER (FIXED):
candle_time = datetime.fromtimestamp(latest_candle['time'], tz=timezone.utc)
# Already UTC-aware from fromtimestamp with tz parameter
```

**Line 1029 (VWAP Check):**
```python
# BEFORE (WRONG):
latest_time = datetime.fromtimestamp(rates[-1]['time'])
age_minutes = (datetime.now() - latest_time).total_seconds() / 60

# AFTER (FIXED):
latest_time = datetime.fromtimestamp(rates[-1]['time'], tz=timezone.utc)
now_utc = datetime.now(timezone.utc)
age_seconds = (now_utc - latest_time).total_seconds()
age_minutes = age_seconds / 60
```

**Added Negative Age Handling:**
- All age calculations now check for negative values
- Negative ages are clamped to 0 (treating as fresh)
- Detailed warning logs explain the issue

---

### **2. Fixed `infra/micro_scalp_execution.py`**

**Line 254 (`_get_current_m1_candle_time`):**
```python
# BEFORE (WRONG):
return datetime.fromtimestamp(candle_time)

# AFTER (FIXED):
return datetime.fromtimestamp(candle_time, tz=timezone.utc)
```

**Line 381 (`_check_adverse_candle`):**
```python
# BEFORE (WRONG):
candle_time = datetime.fromtimestamp(candle_time)

# AFTER (FIXED):
candle_time = datetime.fromtimestamp(candle_time, tz=timezone.utc)
```

**Added timezone import:**
```python
from datetime import datetime, timedelta, timezone
```

---

### **3. Added Negative Age Validation**

**All age calculations now include:**
```python
# CRITICAL FIX: Handle negative age (candle timestamp in future)
if age_minutes < 0:
    logger.warning(
        f"⚠️ NEGATIVE CANDLE AGE DETECTED for {symbol}: {age_minutes:.1f} min\n"
        f"   └─ Candle time: {candle_time.isoformat()}\n"
        f"   └─ Current time: {now_utc.isoformat()}\n"
        f"   └─ Possible causes:\n"
        f"      1. MT5 server time ahead of system time\n"
        f"      2. Timezone mismatch in timestamp parsing\n"
        f"      3. Clock synchronization issue\n"
        f"   └─ Action: Clamping age to 0 (treating as fresh) and continuing"
    )
    age_minutes = 0.0  # Clamp negative age to 0 (treat as fresh)
```

---

## 📊 **Impact**

**Before Fix:**
- Negative ages: -177 minutes (candle in future)
- System incorrectly treats data as stale
- May block execution unnecessarily
- Confusing error messages

**After Fix:**
- All MT5 timestamps correctly parsed as UTC
- Negative ages prevented (clamped to 0 if detected)
- Clear warning logs if issue persists
- System continues functioning correctly

---

## ✅ **Files Modified**

1. ✅ `infra/range_scalping_risk_filters.py`
   - Line 819: Fixed MT5 direct fetch timestamp parsing
   - Line 1029: Fixed VWAP check timestamp parsing
   - Added negative age validation in 3 locations

2. ✅ `infra/micro_scalp_execution.py`
   - Line 254: Fixed M1 candle time parsing
   - Line 381: Fixed adverse candle check timestamp parsing
   - Added timezone import

---

## 🔍 **Verification**

**All instances of `datetime.fromtimestamp()` for MT5 data now use:**
```python
datetime.fromtimestamp(timestamp, tz=timezone.utc)
```

**Negative age handling:**
- ✅ Detects negative ages
- ✅ Logs detailed warnings
- ✅ Clamps to 0 (treats as fresh)
- ✅ Continues execution

---

## 📝 **Summary**

**Status:** ✅ **FIXED**

**Changes:**
1. ✅ Fixed all MT5 timestamp parsing to use UTC timezone
2. ✅ Added negative age detection and handling
3. ✅ Added detailed warning logs
4. ✅ System continues functioning even if negative age detected

**The negative candle age issue should no longer occur. If it does, the system will:**
- Log a detailed warning explaining the cause
- Clamp the age to 0 (treating as fresh)
- Continue execution normally
