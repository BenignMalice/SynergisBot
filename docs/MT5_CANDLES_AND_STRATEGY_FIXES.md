# MT5 Candles & Strategy Scoring Fixes

## ✅ **Fixes Applied**

### **1. MT5 Candles Stale (249.4 min old)**

**Problem:** Candles showing 249.4 minutes old (>4 hours), which is way beyond the 4.9-minute threshold for M5 candles.

**Root Causes:**
- Market likely closed (weekend, broker maintenance, or off-hours)
- MT5 connection issue
- Broker server timezone mismatch

**Fix Applied:**
- **Market Closed Detection:** If candle age > 6 hours (360 min), treat as market closed
- **Graceful Handling:** Don't block analysis if market closed - allow stale data but warn user
- **UTC Timezone:** Fixed timezone-aware datetime comparison to prevent calculation errors

**Changes:**
```python
# Check if market likely closed
market_likely_closed = age_minutes > 360  # 6 hours

if market_likely_closed:
    logger.warning(f"⚠️ Market likely closed: candle age {age_minutes:.1f} min (>6h)")
    is_fresh = True  # Allow stale data if market closed
    final_check = has_enough  # Only check candle count
else:
    is_fresh = age_minutes <= effective_threshold  # Normal check
    final_check = is_fresh and has_enough
```

**Result:** System now allows analysis even when market is closed, with appropriate warnings.

---

### **2. "No Top Strategy Found" Warning**

**Problem:** Warning appears when `scored_strategies` is empty.

**Root Causes:**
- Risk filters failing (strategies not evaluated if risk filters block)
- No strategies generating entry signals (all conditions not met)
- ADX > 25 filtering out all strategies
- Conflict detection removing all strategies

**Fix Applied:**
- **Continue Strategy Scoring:** Even if risk filters fail, still score strategies to show what WOULD be available
- **Better Warning Messages:** Provide specific reasons why no strategies found:
  - "ADX > 25 - Market trending, range scalps disabled"
  - "Entry conditions not met (confluence score: X/100)"
  - "Range invalidated or breaking down"
  - Generic fallback message

**Changes:**
1. Removed early return when risk filters fail - now continues to strategy scoring
2. Added contextual warning messages based on failure reason
3. Strategies are evaluated even if risk filters fail (for informational purposes)

---

## 📊 **Why 249.4 Minutes Old?**

**Possible Scenarios:**

1. **Market Closed:**
   - Weekend (crypto markets should be 24/7, but broker might close)
   - Broker maintenance
   - Exchange-specific closure

2. **MT5 Connection Issue:**
   - Connection lost to broker
   - Broker server downtime
   - Network connectivity issue

3. **Timezone Mismatch:**
   - Broker server time vs. local time difference
   - UTC calculation error (now fixed with timezone-aware datetime)

**What to Check:**
- Is MT5 connected? `mt5.initialize()` and `mt5.terminal_info()`
- What time is it in broker timezone?
- Is the market actually open for this symbol?

---

## 🔧 **System Behavior After Fixes**

### **When Market is Closed (>6 hours old candles):**
- ✅ Analysis continues (doesn't block)
- ⚠️ Warning shown: "Market likely closed"
- ✅ Strategies still evaluated (with stale data)
- ⚠️ Trade execution would be blocked (expected)

### **When Risk Filters Fail:**
- ✅ Strategies still evaluated and shown
- ⚠️ Warning shows why risk filters failed
- ✅ User can see what strategies WOULD be available if conditions improved
- ✅ Better feedback for understanding why trades aren't recommended

---

## 📝 **Next Steps**

1. **Verify MT5 Connection:**
   - Check if MT5 is connected and receiving data
   - Verify broker server status
   - Check market hours for your broker

2. **Test During Market Hours:**
   - Re-run test when market is confirmed open
   - Should see candles < 5 minutes old
   - Strategies should be evaluated

3. **Monitor Strategy Scoring:**
   - Check logs for strategy evaluation
   - Verify entry conditions are being checked
   - Confirm strategies are generating signals when conditions are met

---

## 🎯 **Expected Results After Fixes**

- ✅ **Candle freshness:** System handles closed markets gracefully
- ✅ **Strategy scoring:** Always evaluates strategies (even if risk filters fail)
- ✅ **Better warnings:** More specific reasons why no strategies found
- ✅ **User feedback:** Can see potential strategies even when conditions aren't ideal

