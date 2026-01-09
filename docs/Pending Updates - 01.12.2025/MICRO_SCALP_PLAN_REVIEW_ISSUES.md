# Micro-Scalp Automation Plan Review - Issues Found

**Date:** 2025-12-01  
**Reviewer:** AI Assistant  
**Status:** Issues identified, fixes needed

---

## 🔴 **Critical Issues**

### **1. Variable Name Mismatch in `_execute_micro_scalp()`**

**Location:** Phase 1.1, `_execute_micro_scalp()` method

**Problem:**
- In `__init__`: `self.execution = execution_manager` (line 82)
- In `_execute_micro_scalp()`: `self.execution_manager.execute_trade()` (line 256)
- This will cause `AttributeError: 'MicroScalpMonitor' object has no attribute 'execution_manager'`

**Fix:**
```python
# Change line 256 from:
result = self.execution_manager.execute_trade(
# To:
result = self.execution.execute_trade(
```

---

### **2. Return Value Check Mismatch**

**Location:** Phase 1.1, `_execute_micro_scalp()` method

**Problem:**
- `execute_trade()` returns `{'ok': True/False, 'ticket': ..., 'message': ...}`
- Plan checks `result.get('success')` (line 265)
- Should check `result.get('ok')`

**Fix:**
```python
# Change line 265 from:
if result.get('success'):
# To:
if result.get('ok'):
```

**Also fix line 285:**
```python
# Change from:
logger.warning(f"Micro-scalp execution failed for {symbol}: {result.get('error')}")
# To:
logger.warning(f"Micro-scalp execution failed for {symbol}: {result.get('message')}")
```

---

### **3. Trade Idea Field Name Mismatches**

**Location:** Phase 1.1, `_execute_micro_scalp()` method

**Problem:**
- `_generate_trade_idea()` returns: `'entry_price'`, `'sl'`, `'tp'`, `'direction'`, `'volume'`
- Plan accesses: `trade_idea.get('entry')`, `trade_idea.get('sl')`, `trade_idea.get('tp')`
- Missing `'entry'` field, should use `'entry_price'`

**Fix:**
```python
# Change lines 259-262 from:
result = self.execution.execute_trade(
    symbol=symbol,
    direction=trade_idea.get('direction'),
    entry_price=trade_idea.get('entry'),  # ❌ Wrong field name
    stop_loss=trade_idea.get('sl'),
    take_profit=trade_idea.get('tp'),
    volume=trade_idea.get('volume', 0.01)
)

# To:
result = self.execution.execute_trade(
    symbol=symbol,
    direction=trade_idea.get('direction'),
    entry_price=trade_idea.get('entry_price'),  # ✅ Correct field name
    sl=trade_idea.get('sl'),  # ✅ Parameter name is 'sl', not 'stop_loss'
    tp=trade_idea.get('tp'),  # ✅ Parameter name is 'tp', not 'take_profit'
    volume=trade_idea.get('volume', 0.01)
)
```

**Also fix Discord notification (Phase 5.6):**
```python
# Change from:
f"**Entry:** {trade_idea.get('entry'):.5f}\n"
# To:
f"**Entry:** {trade_idea.get('entry_price'):.5f}\n"
```

---

### **4. `get_status()` Method Bug**

**Location:** Phase 1.1, `get_status()` method

**Problem:**
- Line 303-304: `time.isoformat()` where `time` is the imported module, not a datetime object
- This will cause `AttributeError: module 'time' has no attribute 'isoformat'`

**Fix:**
```python
# Change lines 302-305 from:
'last_execution_times': {
    symbol: time.isoformat() 
    for symbol, time in self.last_execution_time.items()
}

# To:
'last_execution_times': {
    symbol: dt.isoformat() 
    for symbol, dt in self.last_execution_time.items()
}
```

---

## 🟡 **Medium Issues**

### **5. Missing `timedelta` Import**

**Location:** Phase 5.6, Discord notifications section

**Problem:**
- Code uses `timedelta(hours=24)` but `timedelta` is not in the imports list
- Will cause `NameError: name 'timedelta' is not defined`

**Fix:**
```python
# Add to imports (Phase 1.1):
from datetime import datetime, timedelta  # Add timedelta
```

---

### **6. Missing `json` Import for Config Loading**

**Location:** Phase 2.2, Configuration loading

**Problem:**
- Code uses `json.load(f)` but `json` is not in the imports list

**Fix:**
```python
# Add to imports (Phase 1.1):
import json
```

---

### **7. Missing `Optional` Type Hint**

**Location:** Phase 1.1, `_get_m1_candles()` return type

**Problem:**
- Method signature shows `-> Optional[List[Dict]]` but `Optional` is not imported

**Fix:**
```python
# Already in imports, but verify:
from typing import Dict, List, Optional, Any
```

---

### **8. `MultiTimeframeStreamer.get_candles()` Return Type**

**Location:** Phase 1.1, `_get_m1_candles()` method

**Problem:**
- `streamer.get_candles()` returns `List[Candle]` (dataclass objects)
- Plan expects `List[Dict]` (dictionaries)
- Need to convert or handle the difference

**Fix:**
```python
def _get_m1_candles(self, symbol: str, limit: int = 50) -> Optional[List[Dict]]:
    """Get M1 candles from streamer (fast, in-memory)"""
    try:
        candles = self.streamer.get_candles(symbol, 'M1', limit=limit)
        if candles and len(candles) >= 10:
            # Convert Candle objects to dicts if needed
            # Check if candles are already dicts or Candle objects
            if candles and hasattr(candles[0], 'open'):
                # Convert Candle objects to dicts
                candles = [
                    {
                        'time': c.time,
                        'open': c.open,
                        'high': c.high,
                        'low': c.low,
                        'close': c.close,
                        'volume': c.volume
                    }
                    for c in candles
                ]
            return candles
    except Exception as e:
        logger.debug(f"Failed to get M1 candles for {symbol}: {e}")
    
    return None
```

**Alternative:** Check if `MicroScalpEngine` expects `Candle` objects or dicts. If it expects `Candle` objects, don't convert.

---

### **9. Missing Error Handling for `check_micro_conditions()`**

**Location:** Phase 1.1, `_monitor_loop()` method

**Problem:**
- `check_micro_conditions()` can raise exceptions
- Plan wraps it in try/except in circuit breaker section, but not in the main loop

**Fix:**
Already handled in circuit breaker section (Phase 5, Risk 2), but verify the main loop also has error handling.

---

### **10. Discord Notification Field Names**

**Location:** Phase 5.6, `_execute_micro_scalp()` Discord notification

**Problem:**
- Uses `trade_idea.get('entry')` but should be `trade_idea.get('entry_price')`

**Fix:**
Already covered in Issue #3.

---

## 🟢 **Minor Issues**

### **11. Inconsistent Parameter Names in Documentation**

**Location:** Throughout plan

**Problem:**
- Some places use `stop_loss`/`take_profit`, others use `sl`/`tp`
- Should be consistent: use `sl`/`tp` to match actual method signature

**Fix:**
Update all documentation to use `sl`/`tp` consistently.

---

### **12. Missing `atr1` Parameter in Execution**

**Location:** Phase 1.1, `_execute_micro_scalp()` method

**Problem:**
- `execute_trade()` accepts optional `atr1` parameter
- `trade_idea` contains `'atr1'` field
- Plan doesn't pass it

**Fix:**
```python
result = self.execution.execute_trade(
    symbol=symbol,
    direction=trade_idea.get('direction'),
    entry_price=trade_idea.get('entry_price'),
    sl=trade_idea.get('sl'),
    tp=trade_idea.get('tp'),
    volume=trade_idea.get('volume', 0.01),
    atr1=trade_idea.get('atr1')  # ✅ Add this
)
```

---

### **13. Missing `error` Field Handling**

**Location:** Phase 1.1, error logging

**Problem:**
- Plan checks `result.get('error')` but `execute_trade()` returns `'message'` not `'error'`

**Fix:**
Already covered in Issue #2.

---

### **14. Type Hints for `trade_idea` Parameter**

**Location:** Phase 1.1, `_execute_micro_scalp()` method signature

**Problem:**
- Method signature shows `trade_idea: Dict` but should be more specific

**Fix:**
```python
def _execute_micro_scalp(self, symbol: str, trade_idea: Optional[Dict[str, Any]]):
```

---

## ✅ **Summary**

**Critical Issues:** 4  
**Medium Issues:** 6  
**Minor Issues:** 4  

**Total Issues:** 14

**Priority Fixes:**
1. Variable name mismatch (`execution` vs `execution_manager`)
2. Return value check (`success` vs `ok`)
3. Trade idea field names (`entry` vs `entry_price`)
4. `get_status()` bug (`time.isoformat()`)

**Estimated Fix Time:** 15-20 minutes

---

## 🔧 **Recommended Fix Order**

1. Fix variable name mismatch (Issue #1)
2. Fix return value checks (Issue #2)
3. Fix trade idea field names (Issue #3)
4. Fix `get_status()` bug (Issue #4)
5. Add missing imports (Issues #5, #6)
6. Fix `get_candles()` return type handling (Issue #8)
7. Add `atr1` parameter (Issue #12)
8. Update documentation for consistency (Issue #11)

---

**Status:** Ready for fixes  
**Next Step:** Apply fixes to plan

