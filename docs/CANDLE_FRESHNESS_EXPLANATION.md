# Why Candles Appear "Stale" - Explanation

## 🔍 **The Issue**

The data quality check reported:
```
❌ MT5 candles unavailable/stale (3.3 min old) - BLOCKING TRADE
```

## 📊 **Why This Happens**

### **1. M5 Candle Period (Most Likely Cause)**

**M5 (5-minute) candles** work like this:
- **12:40:00** - Candle opens
- **12:40:01 to 12:44:59** - Candle is **forming** (not available via MT5 API)
- **12:45:00** - Candle **closes and becomes available**

**Example Timeline:**
```
Current Time: 12:43:15 UTC
Latest COMPLETE M5 Candle: 12:40:00 UTC (closed at 12:40:00)
Age: 3 minutes 15 seconds (3.25 minutes) ✅ NORMAL
```

**The problem:** The check uses `copy_rates_from_pos()` which only returns **completed candles**, not the currently forming candle.

### **2. How MT5 Candle Data Works**

```python
# This gets the LATEST COMPLETE candle (not the forming one)
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 1)
```

- **Position 0** = Latest **completed** candle
- If we're at **12:43:15**, the latest complete candle is from **12:40:00**
- The **12:40-12:45 candle** is still **forming** (not available yet)

### **3. Why This is Actually Normal**

For **M5 candles**, a 3-4 minute age is **expected** if we're in the middle of a 5-minute period:

| Current Time | Latest Complete Candle | Age |
|-------------|----------------------|-----|
| 12:40:00 | 12:40:00 | 0 min (just closed) |
| 12:41:30 | 12:40:00 | 1.5 min ✅ |
| 12:43:15 | 12:40:00 | 3.25 min ✅ |
| 12:44:59 | 12:40:00 | 4.98 min ✅ |
| 12:45:00 | 12:45:00 | 0 min (new candle closed) |

---

## ✅ **Solutions**

### **Option 1: Adjust Threshold for M5 (Recommended)**

For M5 candles, allow up to **4.9 minutes** (just before next candle closes):

```python
# In _check_candle_freshness()
if timeframe == mt5.TIMEFRAME_M5:
    max_age_minutes = 4.9  # Allow up to 4.9 min (before next M5 candle closes)
elif timeframe == mt5.TIMEFRAME_M1:
    max_age_minutes = 0.9  # Allow up to 0.9 min for M1
elif timeframe == mt5.TIMEFRAME_M15:
    max_age_minutes = 14.9  # Allow up to 14.9 min for M15
```

### **Option 2: Use Tick Data for Real-Time Check**

Instead of checking candle age, check if **recent ticks** are available:

```python
def _check_tick_freshness(self, symbol: str, max_age_seconds: int = 30):
    """Check if recent ticks are available (real-time data)"""
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        tick_time = datetime.fromtimestamp(tick.time)
        age_seconds = (datetime.now() - tick_time).total_seconds()
        return age_seconds <= max_age_seconds, age_seconds
    return False, float('inf')
```

### **Option 3: Check Forming Candle (Advanced)**

Use `symbol_info()` to get current price and manually check if it's "reasonable":

```python
def _check_market_active(self, symbol: str):
    """Check if market is active (has recent price updates)"""
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return False
    
    # Check if bid/ask are reasonable (not stale)
    if tick.bid <= 0 or tick.ask <= 0:
        return False
    
    # Check tick time is recent (< 1 minute)
    tick_age = (datetime.now() - datetime.fromtimestamp(tick.time)).total_seconds()
    return tick_age < 60
```

---

## 🎯 **Recommended Fix**

**For range scalping**, use **Option 1** (adjust threshold) because:

1. ✅ **M5 candles** are the primary timeframe for range detection
2. ✅ **3-4 minute age** is normal during the candle formation period
3. ✅ **Simpler** - no need for tick data checks
4. ✅ **Matches MT5 behavior** - only completed candles are available

**Implementation:**

```python
def _check_candle_freshness(
    self,
    symbol: str,
    max_age_minutes: int = 2,
    timeframe: int = mt5.TIMEFRAME_M5
) -> Tuple[bool, float, Dict[str, Any]]:
    """Check if MT5 candles are fresh"""
    try:
        # Adjust threshold based on timeframe
        tf_thresholds = {
            mt5.TIMEFRAME_M1: 0.9,   # Allow up to 0.9 min for M1
            mt5.TIMEFRAME_M5: 4.9,   # Allow up to 4.9 min for M5 (before next candle)
            mt5.TIMEFRAME_M15: 14.9, # Allow up to 14.9 min for M15
            mt5.TIMEFRAME_H1: 59.9   # Allow up to 59.9 min for H1
        }
        
        effective_threshold = tf_thresholds.get(timeframe, max_age_minutes)
        
        # Get latest candle
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)
        if rates is None or len(rates) == 0:
            return False, float('inf'), {"error": "No candles available"}
        
        latest_candle = rates[0]
        candle_time = datetime.fromtimestamp(latest_candle['time'])
        age_minutes = (datetime.now() - candle_time).total_seconds() / 60
        
        is_fresh = age_minutes <= effective_threshold
        # ... rest of logic
```

---

## 📝 **Summary**

**Why candles were "stale":**
- ✅ **Not actually stale** - this is normal behavior for MT5 M5 candles
- ✅ The latest **completed** M5 candle is from 12:40:00
- ✅ At 12:43:15, the age is 3.25 minutes (expected during candle formation)
- ✅ The **forming candle** (12:40-12:45) is not available via MT5 API

**The 2-minute threshold is too strict** for M5 candles. It should be **4.9 minutes** to account for the 5-minute formation period.

