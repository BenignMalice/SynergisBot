# Stale Candle Diagnostic Fix

## 🔍 **Root Cause Investigation**

The user reports **249.4 minutes old candles** for BTCUSD while the market is **active** (24/7 market). This indicates a **data fetching or storage issue**, not market closure.

## ✅ **Fixes Applied**

### **1. Force Fresh MT5 Connection**
**Problem:** MT5 connection might be stale or cached.

**Fix:**
- Added `force_fresh` parameter to `_check_candle_freshness()`
- When `force_fresh=True`, shutdown and re-initialize MT5 connection
- Ensures fresh data fetch, not cached/stale data

### **2. Explicit Symbol Selection**
**Problem:** Symbol might not be in Market Watch.

**Fix:**
- Explicitly call `mt5.symbol_select(symbol, True)` before fetching
- Verifies symbol is available and selected
- Logs warning if symbol not found

### **3. Enhanced Diagnostic Logging**
**Problem:** No visibility into what's causing stale data.

**Fix:**
- Logs candle time vs. current time
- Logs MT5 server time vs. local UTC time
- Logs MT5 terminal time for comparison
- Detects timezone mismatches

### **4. Better Error Handling**
**Problem:** Errors might be silent.

**Fix:**
- Captures and logs MT5 error codes
- Explicit error messages for initialization failures
- Symbol availability checks

---

## 🔧 **Potential Root Causes**

### **1. Symbol Mismatch**
- Code normalizes to `BTCUSDc` (with 'c' suffix)
- Freshness check might be checking wrong symbol
- **Fix:** Ensure symbol normalization is consistent

### **2. MT5 Connection State**
- Connection might be stale
- Terminal might be disconnected
- **Fix:** Force re-initialization on each check

### **3. Timezone Issue**
- MT5 server time vs. local time mismatch
- Timestamp calculation error
- **Fix:** UTC-aware datetime comparisons

### **4. Data Source Issue**
- IndicatorBridge might be caching data
- Multiple data sources might conflict
- **Fix:** Force fresh MT5 fetch, bypass caching

---

## 📊 **Diagnostic Output**

After fixes, the logs will show:
```
🔍 Candle age check for BTCUSDc: 
  candle_time=2025-11-02T09:00:00+00:00,
  now_utc=2025-11-02T13:04:00+00:00,
  age=249.4 min.
  MT5 server time: 2025-11-02T13:04:00+00:00
  MT5 terminal time: 2025-11-02T13:04:00+00:00
```

This will help identify:
- **If MT5 server time matches local time** → Data fetch issue
- **If MT5 server time is old** → MT5 connection/storage issue
- **If candle_time is old but server time is current** → Symbol/data fetch problem

---

## 🎯 **Next Steps**

1. **Check Symbol:**
   - Verify symbol is `BTCUSDc` (not `BTCUSD`)
   - Check if symbol exists in MT5 Market Watch
   - Verify symbol is active/trading

2. **Check MT5 Connection:**
   - Verify MT5 terminal is connected
   - Check if terminal is receiving live data
   - Verify broker connection status

3. **Check Data Flow:**
   - IndicatorBridge fetches via `get_multi()`
   - Freshness check fetches directly via `copy_rates_from_pos()`
   - Both should return same data - if different, caching issue

4. **Test Direct Fetch:**
   - Test `mt5.copy_rates_from_pos('BTCUSDc', mt5.TIMEFRAME_M5, 0, 1)` directly
   - Compare timestamp with current time
   - If still old, MT5/terminal issue

---

## 🔍 **Debugging Commands**

Run these to diagnose:

```python
import MetaTrader5 as mt5
from datetime import datetime, timezone

mt5.initialize()
symbol = "BTCUSDc"
mt5.symbol_select(symbol, True)

# Get latest candle
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 1)
if rates:
    candle_time = datetime.fromtimestamp(rates[0]['time'], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    age = (now - candle_time).total_seconds() / 60
    print(f"Candle time: {candle_time}")
    print(f"Current time: {now}")
    print(f"Age: {age:.1f} minutes")
    
    # Check MT5 server time
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        server_time = datetime.fromtimestamp(tick.time, tz=timezone.utc)
        print(f"MT5 server time: {server_time}")
        print(f"Server time diff: {(now - server_time).total_seconds() / 60:.1f} min")
```

This will show if the problem is:
- MT5 connection
- Symbol availability
- Data source
- Timezone calculation

