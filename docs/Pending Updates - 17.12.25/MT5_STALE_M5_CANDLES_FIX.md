# MT5 Stale M5 Candles Fix

## 🔍 Problem

MT5 is returning stale M5 candles (66-67 minutes old) even though:
- Tick data is fresh (0.0 min old)
- Diagnostic shows fresh candles available (3.69 min old)
- Symbol is properly subscribed and selected

## 📊 Diagnostic Results

**Fresh Data Available:**
- Latest M5 candle: 2025-12-17 18:15:00 (3.69 min old) ✅
- Tick data: Fresh (0.02 min old) ✅
- Symbol: Properly selected ✅

**But Code Reports:**
- Latest M5 candle: 2025-12-17 17:10:00 (67 min old) ❌

## 🐛 Root Cause

The issue is in how the code identifies the "latest" candle:

1. **`copy_rates_from_pos` returns candles in reverse order:**
   - `rates[0]` = **OLDEST** candle (not newest!)
   - `rates[-1]` = **NEWEST** candle

2. **Code bug at line 659:**
   ```python
   latest_candle_time = datetime.fromtimestamp(rates[0]['time'], tz=timezone.utc)
   ```
   This gets the **OLDEST** candle, not the newest!

3. **Code bug at line 757:**
   ```python
   latest_candle = rates[0]
   ```
   Again using the wrong index!

## ✅ Fix

Change all references from `rates[0]` to `rates[-1]` when getting the latest candle:

```python
# WRONG (current):
latest_candle = rates[0]
latest_candle_time = datetime.fromtimestamp(rates[0]['time'], tz=timezone.utc)

# CORRECT (fixed):
latest_candle = rates[-1]  # Last element = newest
latest_candle_time = datetime.fromtimestamp(rates[-1]['time'], tz=timezone.utc)
```

## 📝 MT5 Candle Array Order

**`copy_rates_from_pos` and `copy_rates_from` return:**
- `rates[0]` = Oldest candle (first in chronological order)
- `rates[-1]` = Newest candle (last in chronological order)

**Always use `rates[-1]` for the latest candle!**

## 🔧 Files to Fix

1. `infra/range_scalping_risk_filters.py`:
   - Line 659: `rates[0]` → `rates[-1]`
   - Line 680: `fresh_rates_1[0]` → `fresh_rates_1[-1]`
   - Line 697: `fresh_rates_2[0]` → `fresh_rates_2[-1]`
   - Line 714: `fresh_rates_3[0]` → `fresh_rates_3[-1]`
   - Line 757: `rates[0]` → `rates[-1]`

## 💡 Impact

**Before Fix:**
- Code checks oldest candle (67 min old) ❌
- Reports stale data incorrectly
- May block trading unnecessarily

**After Fix:**
- Code checks newest candle (3.69 min old) ✅
- Reports fresh data correctly
- Trading proceeds normally

## 🎯 Summary

The stale candle issue is a **code bug**, not a data issue. MT5 is providing fresh candles, but the code is checking the wrong end of the array. Fix: Use `rates[-1]` instead of `rates[0]` for the latest candle.

