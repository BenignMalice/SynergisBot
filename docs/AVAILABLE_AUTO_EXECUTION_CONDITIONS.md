# Available Auto-Execution Plan Conditions

## Overview

Auto-execution plans can use various conditions beyond structure-based conditions (like `order_block`, `choch_bull`, etc.). This document lists all available non-structure conditions.

---

## 📊 **CONFLUENCE CONDITIONS**

### 1. `min_confluence` (0-100)
**Purpose:** Minimum confluence score threshold for general strategies  
**Usage:** Confluence-only mode or hybrid mode  
**Example:**
```json
{
  "min_confluence": 75,
  "price_near": 87500,
  "tolerance": 200
}
```
**When to Use:**
- Range-bound/compression markets
- Early trend formation
- Session transitions
- Stable macro context

**Symbol-Specific Defaults:**
- BTCUSDc: 75
- XAUUSDc: 80
- Default: 80

### 2. `range_scalp_confluence` (0-100)
**Purpose:** Minimum confluence for range scalping (takes precedence over `min_confluence`)  
**Usage:** Range scalping strategies only  
**Example:**
```json
{
  "range_scalp_confluence": 80,
  "structure_confirmation": true,
  "price_near": 87500,
  "tolerance": 200
}
```
**Note:** Use this for range scalping, NOT `min_confluence`

---

## 📈 **VOLATILITY CONDITIONS**

### 3. `min_volatility`
**Purpose:** Minimum volatility threshold (ATR-based)  
**Usage:** Ensure sufficient volatility for strategy  
**Example:**
```json
{
  "min_volatility": 1.2,  // 1.2x ATR
  "price_near": 87500,
  "tolerance": 200
}
```

### 4. `max_volatility`
**Purpose:** Maximum volatility threshold (ATR-based)  
**Usage:** Avoid excessive volatility  
**Example:**
```json
{
  "max_volatility": 2.5,  // Max 2.5x ATR
  "price_near": 87500,
  "tolerance": 200
}
```

### 5. `atr_5m_threshold`
**Purpose:** ATR threshold on M5 timeframe  
**Usage:** Volatility filter on specific timeframe  
**Example:**
```json
{
  "atr_5m_threshold": 1.5,
  "price_near": 87500,
  "tolerance": 200
}
```

### 6. `vix_threshold`
**Purpose:** VIX (volatility index) threshold  
**Usage:** Market-wide volatility filter  
**Example:**
```json
{
  "vix_threshold": 20,  // VIX must be above 20
  "price_near": 87500,
  "tolerance": 200
}
```

### 7. `bb_squeeze`
**Purpose:** Bollinger Band squeeze detection  
**Usage:** Wait for volatility compression before breakout  
**Example:**
```json
{
  "bb_squeeze": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### 8. `bb_expansion`
**Purpose:** Bollinger Band expansion detection  
**Usage:** Confirm volatility breakout  
**Example:**
```json
{
  "bb_expansion": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### 9. `bb_width_threshold`
**Purpose:** Bollinger Band width threshold  
**Usage:** Custom BB width filter  
**Example:**
```json
{
  "bb_width_threshold": 0.02,  // 2% width
  "price_near": 87500,
  "tolerance": 200
}
```

---

## 📊 **VOLUME CONDITIONS**

### 10. `volume_confirmation`
**Purpose:** Require volume confirmation  
**Usage:** Ensure volume supports the move  
**Example:**
```json
{
  "volume_confirmation": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### 11. `volume_ratio`
**Purpose:** Volume ratio threshold (current vs average)  
**Usage:** Require above-average volume  
**Example:**
```json
{
  "volume_ratio": 1.5,  // 1.5x average volume
  "price_near": 87500,
  "tolerance": 200
}
```

### 12. `volume_above`
**Purpose:** Minimum volume threshold  
**Usage:** Filter low-volume setups  
**Example:**
```json
{
  "volume_above": 1000000,  // Minimum volume
  "price_near": 87500,
  "tolerance": 200
}
```

### 13. `volume_spike`
**Purpose:** Volume spike detection  
**Usage:** Wait for sudden volume increase  
**Example:**
```json
{
  "volume_spike": true,
  "price_near": 87500,
  "tolerance": 200
}
```

---

## ⏰ **TIME CONDITIONS**

### 14. `time_after`
**Purpose:** Execute only after specific time  
**Usage:** Session-based or news-avoidance  
**Example:**
```json
{
  "time_after": "09:30",  // After 9:30 AM
  "price_near": 87500,
  "tolerance": 200
}
```

### 15. `time_before`
**Purpose:** Execute only before specific time  
**Usage:** Avoid late-session trades  
**Example:**
```json
{
  "time_before": "15:00",  // Before 3:00 PM
  "price_near": 87500,
  "tolerance": 200
}
```

---

## 📍 **PRICE CONDITIONS**

### 16. `price_above`
**Purpose:** Price must be above level (breakout)  
**Usage:** Breakout strategies  
**Example:**
```json
{
  "price_above": 88000,
  "price_near": 88000,  // Must match!
  "tolerance": 200
}
```

### 17. `price_below`
**Purpose:** Price must be below level (breakdown)  
**Usage:** Breakdown strategies  
**Example:**
```json
{
  "price_below": 87000,
  "price_near": 87000,  // Must match!
  "tolerance": 200
}
```

### 18. `price_near`
**Purpose:** Price proximity to entry (always include with tolerance)  
**Usage:** All plans should include this  
**Example:**
```json
{
  "price_near": 87500,
  "tolerance": 200
}
```

---

## 🎯 **PATTERN CONDITIONS**

### 19. `inside_bar`
**Purpose:** Inside bar pattern detection  
**Usage:** Volatility compression setups  
**Example:**
```json
{
  "inside_bar": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### 20. `equal_highs`
**Purpose:** Equal highs pattern (double top)  
**Usage:** Resistance level confirmation  
**Example:**
```json
{
  "equal_highs": true,
  "price_near": 88000,
  "tolerance": 200
}
```

### 21. `equal_lows`
**Purpose:** Equal lows pattern (double bottom)  
**Usage:** Support level confirmation  
**Example:**
```json
{
  "equal_lows": true,
  "price_near": 87000,
  "tolerance": 200
}
```

---

## 📊 **VWAP CONDITIONS**

### 22. `vwap_deviation`
**Purpose:** VWAP deviation detection  
**Usage:** Mean reversion strategies  
**Example:**
```json
{
  "vwap_deviation": true,
  "vwap_deviation_direction": "below",  // or "above"
  "price_near": 87500,
  "tolerance": 200
}
```

---

## ✅ **CONFIRMATION CONDITIONS**

### 23. `structure_confirmation`
**Purpose:** Require structure confirmation  
**Usage:** Filter false breakouts  
**Example:**
```json
{
  "structure_confirmation": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### 24. `range_scalp_confluence` (with structure_confirmation)
**Purpose:** Range scalping with structure confirmation  
**Usage:** Range-bound markets  
**Example:**
```json
{
  "range_scalp_confluence": 80,
  "structure_confirmation": true,
  "price_near": 87500,
  "tolerance": 200
}
```

---

## 🚀 **IMMEDIATE EXECUTION**

### 25. `execute_immediately`
**Purpose:** Execute without waiting for conditions  
**Usage:** Manual override (use with caution)  
**Example:**
```json
{
  "execute_immediately": true
}
```

---

## 💰 **PREMIUM/DISCOUNT CONDITIONS**

### 26. `price_in_discount`
**Purpose:** Price must be in discount zone (below VWAP)  
**Usage:** Mean reversion BUY setups  
**Example:**
```json
{
  "price_in_discount": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### 27. `price_in_premium`
**Purpose:** Price must be in premium zone (above VWAP)  
**Usage:** Mean reversion SELL setups  
**Example:**
```json
{
  "price_in_premium": true,
  "price_near": 88000,
  "tolerance": 200
}
```

---

## 🌏 **SESSION CONDITIONS**

### 28. `asian_session_high`
**Purpose:** Price at Asian session high  
**Usage:** Session-based resistance  
**Example:**
```json
{
  "asian_session_high": true,
  "price_near": 88000,
  "tolerance": 200
}
```

### 29. `asian_session_low`
**Purpose:** Price at Asian session low  
**Usage:** Session-based support  
**Example:**
```json
{
  "asian_session_low": true,
  "price_near": 87000,
  "tolerance": 200
}
```

---

## 🔄 **LIQUIDITY CONDITIONS**

### 30. `liquidity_grab_bull`
**Purpose:** Bullish liquidity grab detected  
**Usage:** Liquidity sweep reversal  
**Example:**
```json
{
  "liquidity_grab_bull": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### 31. `liquidity_grab_bear`
**Purpose:** Bearish liquidity grab detected  
**Usage:** Liquidity sweep reversal  
**Example:**
```json
{
  "liquidity_grab_bear": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### 32. `liquidity_sweep`
**Purpose:** Liquidity sweep detection  
**Usage:** Stop hunt reversal setups  
**Example:**
```json
{
  "liquidity_sweep": true,
  "price_below": 87000,  // or price_above
  "price_near": 87000,
  "tolerance": 200
}
```

---

## 📊 **FVG (FAIR VALUE GAP) CONDITIONS**

### 33. `fvg_bull`
**Purpose:** Bullish FVG detected  
**Usage:** FVG retracement setups  
**Example:**
```json
{
  "fvg_bull": true,
  "fvg_filled_pct": 0.65,  // 65% filled
  "price_near": 87500,
  "tolerance": 200
}
```

### 34. `fvg_bear`
**Purpose:** Bearish FVG detected  
**Usage:** FVG retracement setups  
**Example:**
```json
{
  "fvg_bear": true,
  "fvg_filled_pct": 0.75,  // 75% filled
  "price_near": 87500,
  "tolerance": 200
}
```

---

## 🎯 **MARKET STRUCTURE SHIFT (MSS) CONDITIONS**

### 35. `mss_bull`
**Purpose:** Bullish Market Structure Shift  
**Usage:** MSS pullback setups  
**Example:**
```json
{
  "mss_bull": true,
  "pullback_to_mss": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### 36. `mss_bear`
**Purpose:** Bearish Market Structure Shift  
**Usage:** MSS pullback setups  
**Example:**
```json
{
  "mss_bear": true,
  "pullback_to_mss": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### 37. `pullback_to_mss`
**Purpose:** Price pulling back to MSS level  
**Usage:** MSS continuation setups  
**Example:**
```json
{
  "mss_bull": true,
  "pullback_to_mss": true,
  "price_near": 87500,
  "tolerance": 200
}
```

---

## 🛡️ **MITIGATION BLOCK CONDITIONS**

### 38. `mitigation_block_bull`
**Purpose:** Bullish mitigation block  
**Usage:** Structure break retest  
**Example:**
```json
{
  "mitigation_block_bull": true,
  "structure_broken": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### 39. `mitigation_block_bear`
**Purpose:** Bearish mitigation block  
**Usage:** Structure break retest  
**Example:**
```json
{
  "mitigation_block_bear": true,
  "structure_broken": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### 40. `structure_broken`
**Purpose:** Structure has been broken  
**Usage:** Mitigation block setups  
**Example:**
```json
{
  "mitigation_block_bull": true,
  "structure_broken": true,
  "price_near": 87500,
  "tolerance": 200
}
```

---

## 📋 **CONDITION COMBINATIONS**

### **Confluence-Only Mode**
For range-bound/stable markets:
```json
{
  "min_confluence": 75,
  "price_near": 87500,
  "tolerance": 200
}
```

### **Hybrid Mode**
Confluence + other conditions:
```json
{
  "min_confluence": 75,
  "bb_expansion": true,
  "volume_confirmation": true,
  "price_near": 87500,
  "tolerance": 200
}
```

### **Volatility-Based**
```json
{
  "bb_squeeze": true,
  "bb_expansion": true,
  "price_above": 88000,
  "price_near": 88000,
  "tolerance": 200
}
```

### **Volume-Confirmed**
```json
{
  "volume_spike": true,
  "volume_ratio": 1.5,
  "price_near": 87500,
  "tolerance": 200
}
```

### **Time-Restricted**
```json
{
  "time_after": "09:30",
  "time_before": "15:00",
  "price_near": 87500,
  "tolerance": 200
}
```

---

## 🎯 **RECOMMENDATIONS BY MARKET CONDITION**

### **Range-Bound Market**
```json
{
  "min_confluence": 60-75,
  "structure_confirmation": true,
  "price_near": entry,
  "tolerance": X
}
```

### **Volatile/Breakout Market**
```json
{
  "bb_expansion": true,
  "volume_spike": true,
  "price_above": entry,  // or price_below
  "price_near": entry,
  "tolerance": X
}
```

### **Low Volatility/Compression**
```json
{
  "bb_squeeze": true,
  "inside_bar": true,
  "price_near": entry,
  "tolerance": X
}
```

### **Session-Based**
```json
{
  "time_after": "09:30",
  "min_confluence": 70,
  "price_near": entry,
  "tolerance": X
}
```

---

## ⚠️ **IMPORTANT NOTES**

1. **Always include `price_near` + `tolerance`** - Even with other conditions
2. **`price_above`/`price_below` must match `price_near`** - Use same value
3. **Don't mix `price_above` and `price_below`** - They're contradictory
4. **Use `range_scalp_confluence` for range scalping** - NOT `min_confluence`
5. **Confluence-only plans still need price conditions** - At least `price_near`

---

## 📊 **CONDITION PRIORITY**

When multiple conditions are present:
1. **Price conditions** (`price_near`, `price_above`, `price_below`) - Must pass first
2. **Confluence** (`min_confluence`, `range_scalp_confluence`) - Quality filter
3. **Structure** (`order_block`, `choch_bull`, etc.) - Confirmation
4. **Volatility** (`bb_expansion`, `bb_squeeze`) - Regime filter
5. **Volume** (`volume_spike`, `volume_confirmation`) - Momentum filter
6. **Time** (`time_after`, `time_before`) - Session filter

All conditions must pass for execution (AND logic).
