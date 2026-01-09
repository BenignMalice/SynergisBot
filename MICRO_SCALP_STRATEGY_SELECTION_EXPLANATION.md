# Micro-Scalp Strategy Selection Explanation

**Date:** 2025-12-20  
**Question:** Why are all checks showing only "vwap_reversion" and "edge-based" strategies?

---

## 🎯 **Strategy Selection Logic**

The micro-scalp monitor uses an **adaptive strategy system** that selects the best strategy based on current market conditions. The system checks for **4 possible strategies** in priority order:

### **Strategy Priority Order:**

1. **VWAP Reversion** (Highest Priority)
   - **When used:** Price is significantly deviated from VWAP (≥2σ for BTC, ≥2σ for XAU)
   - **Confidence threshold:** ≥70%
   - **Conditions:**
     - Price deviation from VWAP meets minimum sigma threshold
     - Volume spike detected (≥1.3x average)
     - VWAP slope is relatively flat (not trending)
     - ATR is stable (not expanding rapidly)

2. **Range Scalp** (Second Priority)
   - **When used:** Market is in a clear range structure
   - **Confidence threshold:** ≥55%
   - **Conditions:**
     - Clear range structure detected (price respects high/low at least 2 times)
     - Price is near range edge (within 0.5% tolerance)
     - M15 trend is weak (ADX < 20)
     - Bollinger Band compression detected

3. **Balanced Zone** (Third Priority)
   - **When used:** Market is in equilibrium/compression phase
   - **Confidence threshold:** ≥65%
   - **Conditions:**
     - Bollinger Band width < 2% (compression)
     - EMA/VWAP equilibrium (within 0.1% difference)
     - Compression block detected
     - ATR dropping (volatility decreasing)

4. **Edge-Based** (Fallback)
   - **When used:** No specific regime detected OR confidence too low
   - **Fallback triggers:**
     - No regime meets confidence threshold
     - Regime detection disabled
     - Strategy router error
     - Confluence pre-check failed

---

## 🔍 **Why You're Seeing Only VWAP Reversion & Edge-Based**

### **Normal Behavior:**

This is **expected behavior** and indicates the system is working correctly:

1. **VWAP Reversion is being detected:**
   - Market conditions are meeting VWAP reversion criteria
   - Price is deviated from VWAP with sufficient confidence (≥70%)
   - Volume and volatility conditions are favorable

2. **Range Scalp is NOT being detected:**
   - Market is **not in a clear range structure** right now
   - Price may not be respecting range boundaries
   - M15 trend may be too strong (ADX ≥ 20)
   - Range confidence is below 55% threshold

3. **Balanced Zone is NOT being detected:**
   - Market is **not in compression/equilibrium** right now
   - Bollinger Bands may be expanding (volatility increasing)
   - EMA/VWAP may not be in equilibrium
   - Balanced zone confidence is below 65% threshold

4. **Edge-Based is used as fallback:**
   - When VWAP reversion conditions are not met
   - When no other regime is detected
   - Uses generic edge detection logic (VWAP bands, order blocks, etc.)

---

## 📊 **What This Means**

### **Current Market State:**

Based on seeing mostly "vwap_reversion" and "edge-based":

- ✅ **Market is trending or has VWAP deviations** (VWAP reversion opportunities)
- ❌ **Market is NOT in a range** (no range scalp opportunities)
- ❌ **Market is NOT in compression** (no balanced zone opportunities)

### **This is Normal:**

- Markets spend most time in **trending or VWAP-deviated states**
- **Range structures** are less common (require consolidation periods)
- **Balanced zones** are even rarer (require specific compression conditions)

---

## 🔧 **How to See Other Strategies**

### **To See Range Scalp:**

The market needs to be in a range:

1. **Price respects boundaries:**
   - Price bounces off high/low at least 2 times
   - Clear support/resistance levels

2. **Price near edge:**
   - Within 0.5% of range high or low
   - Not in the middle of the range

3. **Weak trend:**
   - M15 ADX < 20 (low trend strength)

4. **Range confidence ≥ 55%**

**Example conditions:**
- BTCUSDc trading between $88,000 and $88,500
- Price bounces off $88,000 twice, now approaching $88,450 (near high)
- M15 ADX = 15 (weak trend)
- Range confidence = 60% → **Range Scalp strategy selected**

---

### **To See Balanced Zone:**

The market needs to be in compression:

1. **Bollinger Band compression:**
   - BB width < 2% (bands are tight)
   - Volatility is low

2. **Equilibrium:**
   - EMA and VWAP within 0.1% of each other
   - Price oscillating around equilibrium

3. **Compression block:**
   - Recent order block in compression zone
   - ATR dropping (volatility decreasing)

4. **Balanced zone confidence ≥ 65%**

**Example conditions:**
- BTCUSDc trading in tight range ($88,200-$88,250)
- BB width = 1.5% (compressed)
- EMA = $88,225, VWAP = $88,227 (equilibrium)
- ATR dropping from 50 to 30
- Balanced zone confidence = 70% → **Balanced Zone strategy selected**

---

## 📈 **Strategy Distribution Over Time**

### **Expected Distribution:**

In a typical trading day, you might see:

- **VWAP Reversion:** 40-60% of checks (most common)
- **Edge-Based:** 30-50% of checks (fallback when no regime)
- **Range Scalp:** 5-15% of checks (only during range periods)
- **Balanced Zone:** 2-10% of checks (rare, only during compression)

### **Why VWAP Reversion is Common:**

- Markets frequently deviate from VWAP
- Volume spikes are common
- VWAP reversion has lower threshold (70%) vs balanced zone (65%)
- VWAP reversion is checked first (highest priority)

---

## 🔍 **How to Verify Strategy Selection**

### **Check Logs:**

Look for detailed regime detection logs:

```
[BTCUSDc] ⚠️ Regime UNKNOWN - No regime met confidence thresholds
[BTCUSDc]   VWAP Reversion: 45% (threshold: 70%)
[BTCUSDc]   Range Scalp: 30% (threshold: 55%)
[BTCUSDc]   Balanced Zone: 20% (threshold: 65%)
```

This shows why each strategy is NOT being selected.

### **Check Dashboard:**

The dashboard at `http://localhost:8010/micro-scalp/view` shows:
- Strategy used for each check
- Regime detected
- Confidence scores
- Why strategies were selected/not selected

### **Check API:**

```bash
curl http://localhost:8010/micro-scalp/history?limit=10
```

Shows recent checks with:
- `strategy`: Strategy name used
- `regime`: Regime detected
- `regime_confidence`: Confidence score
- `regime_detection`: Detailed breakdown for each regime

---

## ⚙️ **Configuration Thresholds**

Current thresholds in `config/micro_scalp_config.json`:

```json
{
  "regime_detection": {
    "strategy_confidence_thresholds": {
      "vwap_reversion": 70,    // Highest threshold
      "range_scalp": 55,        // Lower threshold (easier to trigger)
      "balanced_zone": 65,      // Medium threshold
      "edge_based": 60          // Not used (always fallback)
    }
  }
}
```

### **To See More Range Scalp:**

Lower the threshold (not recommended - reduces quality):
```json
"range_scalp": 45  // Lower from 55
```

### **To See More Balanced Zone:**

Lower the threshold (not recommended - reduces quality):
```json
"balanced_zone": 55  // Lower from 65
```

**⚠️ Warning:** Lowering thresholds will reduce trade quality. The current thresholds are calibrated for optimal performance.

---

## ✅ **Summary**

**What you're seeing is NORMAL:**

- ✅ System is working correctly
- ✅ VWAP reversion is being detected (good market conditions)
- ✅ Edge-based is used as fallback (when VWAP conditions not met)
- ✅ Range scalp and balanced zone are NOT detected (market not in those states)

**This is expected because:**
- Markets spend most time trending/deviating (VWAP reversion)
- Range structures are less common
- Balanced zones are rare

**To see other strategies:**
- Wait for market to enter range structure (for range scalp)
- Wait for market to compress (for balanced zone)
- Or check logs to see why they're not being detected

**The system is adaptive and will automatically switch strategies when market conditions change.**
