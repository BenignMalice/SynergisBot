# Candle Fetch Root Cause Analysis

## 🔍 **Deep Analysis of "inf min old" Issue**

After thorough investigation, the root cause is:

### **1. MT5 Connection Broken by `mt5.shutdown()`**

**Problem:**
- `desktop_agent.py` initializes `MT5Service` and connects successfully
- When `force_fresh=True`, `_check_candle_freshness()` calls `mt5.shutdown()`
- This **disconnects the existing MT5Service connection**
- Subsequent `mt5.initialize()` might fail or not work properly
- Result: `rates = mt5.copy_rates_from_pos()` returns `None` or empty
- This causes `age_minutes = float('inf')` → "inf min old" error

**Code Flow:**
```
desktop_agent.py:
  └─> MT5Service.connect() ✅ Connected
  └─> Calls range scalping analysis
      └─> check_data_quality()
          └─> _check_candle_freshness(force_fresh=True)
              └─> mt5.shutdown() ❌ BREAKS EXISTING CONNECTION
              └─> mt5.initialize() ❌ Might fail
              └─> copy_rates_from_pos() ❌ Returns None/empty
              └─> age_minutes = float('inf')
```

### **2. Streamer Not Accessible**

**Problem:**
- Streamer initialized in `main_api.py` (FastAPI server)
- `desktop_agent.py` runs as **separate process**
- `get_streamer()` returns `None` (different process memory)
- Falls back to direct MT5, which also fails

### **3. Symbol Normalization Mismatch**

**Potential Issue:**
- Streamer uses `_normalize_symbol()` which might normalize differently
- Range scalping uses `symbol_normalized = symbol if symbol.endswith('c') else f"{symbol}c"`
- If mismatch, streamer won't find candles for the symbol

---

## ✅ **Fixes Applied**

### **1. Don't Shutdown MT5 (CRITICAL FIX)**

**Changed:**
- `force_fresh=False` by default (don't call `mt5.shutdown()`)
- Use existing MT5Service connection if available
- Only initialize MT5 if not already initialized

**Code:**
```python
# OLD (BROKEN):
if force_fresh:
    mt5.shutdown()  # ❌ BREAKS EXISTING CONNECTION
    mt5.initialize()

# NEW (FIXED):
if self.mt5_service:
    if self.mt5_service.connect():  # ✅ Use existing connection
        mt5_initialized = True
elif not mt5.terminal_info().connected:
    mt5.initialize()  # Only if not connected
```

### **2. Pass MT5Service to Risk Filters**

**Changed:**
- `desktop_agent.py` now passes `mt5_service` in `market_data`
- `range_scalping_analysis.py` extracts and passes to `RangeScalpingRiskFilters`
- Risk filters use existing MT5Service connection

**Code:**
```python
# desktop_agent.py
market_data = {
    ...
    "mt5_service": mt5_service  # ✅ Pass existing service
}

# range_scalping_analysis.py
mt5_service = market_data.get("mt5_service")
risk_filters = RangeScalpingRiskFilters(config, mt5_service=mt5_service)
```

### **3. Enhanced Diagnostic Logging**

**Added:**
- Streamer availability check with INFO-level logging
- MT5 initialization status logging
- Symbol availability checks
- Detailed error messages

---

## 🎯 **Expected Results After Fix**

1. ✅ **No `mt5.shutdown()` call** - Existing connection preserved
2. ✅ **MT5Service connection reused** - Faster, more reliable
3. ✅ **Better error messages** - Can diagnose specific failures
4. ✅ **Streamer diagnostic info** - Shows why streamer not used

---

## 📝 **Why This Happened**

The `force_fresh=True` parameter was meant to ensure fresh data, but calling `mt5.shutdown()` **breaks the existing MT5Service connection** that `desktop_agent.py` relies on. This is a **classic connection management bug** - trying to be "too helpful" by forcing a fresh connection actually broke the working connection.

**Lesson:** Never call `mt5.shutdown()` if there's an existing MT5Service connection active. Always check and reuse existing connections first.

