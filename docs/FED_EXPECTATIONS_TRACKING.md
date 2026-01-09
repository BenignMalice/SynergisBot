# Fed Expectations Tracking - Implementation Complete

**Date:** 2025-10-29  
**Status:** ✅ Implemented

---

## Overview

Fed expectations tracking uses the 2Y-10Y Treasury spread (T10Y2Y) from FRED to infer Federal Reserve policy expectations. This enhances macro bias calculations with forward-looking monetary policy signals.

---

## How It Works

### Spread Interpretation

1. **Inverted Spread (< -0.2%)**
   - **Signal:** Recession warning
   - **Fed Implication:** Likely to cut rates
   - **Gold Impact:** +0.15 bias (bullish) - safe-haven appeal increases
   - **USD Pairs Impact:** +0.2 bias (bullish for EUR/GBP) - USD weakens

2. **Steep Spread (> +0.5%)**
   - **Signal:** Growth expectations
   - **Fed Implication:** Likely to hold/hike rates
   - **Gold Impact:** -0.15 bias (bearish) - safe-haven appeal decreases
   - **USD Pairs Impact:** -0.2 bias (bearish for EUR/GBP) - USD strengthens

3. **Flat Spread (-0.2% to +0.5%)**
   - **Signal:** Neutral expectations
   - **Fed Implication:** Status quo
   - **Impact:** Neutral (0.0 bias)

---

## Implementation Details

### 1. FRED Service
- **Method:** `get_2y10y_spread()`
- **Series ID:** `T10Y2Y` (2Y-10Y Treasury Spread)
- **Cache:** 60 minutes (daily frequency)
- **Status:** ✅ Already implemented

### 2. Macro Bias Calculator Integration

**Gold (XAUUSD):**
- Added to `_calculate_gold_bias()`
- Inverted spread: +0.15 bias points
- Steep spread: -0.15 bias points
- Integrated into explanation generation

**USD Pairs (EURUSD, GBPUSD):**
- Added to `_calculate_usd_pair_bias()`
- Inverted spread: +0.2 bias points (USD weakens)
- Steep spread: -0.2 bias points (USD strengthens)
- Context added to explanation

### 3. Formatting Integration

**`format_macro_bias_summary()`:**
- Displays Fed expectations prominently when present
- Format: `📊 Fed Expectations: 2Y-10Y spread inverted (-0.5%) - recession signal, Fed likely to cut (bullish for Gold)`
- Appears before macro bias score for visibility

---

## Example Output

### Before:
```
🟢 Macro Bias: BULLISH (moderate) - Score: +0.65
   Falling 10Y (down) and weakening DXY (down) support XAUUSD — bullish bias valid unless structure breaks down.
```

### After (With Fed Expectations):
```
📊 Fed Expectations: 2Y-10Y spread inverted (-0.3%) - recession signal, Fed likely to cut (bullish for Gold)
🟢 Macro Bias: BULLISH (moderate) - Score: +0.80
   Falling 10Y (down) and weakening DXY (down) support XAUUSD. Recession risk (inverted yield curve) increases Gold's safe-haven appeal. — bullish bias valid unless structure breaks down.
```

---

## Data Flow

```
FRED API (T10Y2Y)
    ↓
get_2y10y_spread()
    ↓
_calculate_gold_bias() or _calculate_usd_pair_bias()
    ↓
factors['fed_expectations'] = {
    'value': ±0.15 or ±0.2,
    'reason': '...'
}
    ↓
format_macro_bias_summary()
    ↓
ChatGPT Analysis Output
```

---

## Testing

To verify Fed expectations tracking:

1. **Check FRED Service:**
   ```python
   from infra.fred_service import create_fred_service
   fred = create_fred_service()
   spread = fred.get_2y10y_spread()
   print(f"2Y-10Y Spread: {spread}%")
   ```

2. **Check Macro Bias:**
   ```python
   from infra.macro_bias_calculator import create_macro_bias_calculator
   # Run analysis for XAUUSD or EURUSD
   # Check if factors['fed_expectations'] is present
   ```

---

## Configuration

### Thresholds (in `macro_bias_calculator.py`):

- **Inverted:** `< -0.2%` (recession signal)
- **Steep:** `> +0.5%` (growth expectations)
- **Flat:** `-0.2% to +0.5%` (neutral)

### Impact Weights:

- **Gold (XAUUSD):** ±0.15 bias points
- **USD Pairs (EURUSD, GBPUSD):** ±0.2 bias points

These can be adjusted based on historical performance.

---

## Use Cases

### Gold Trading:
- **Inverted yield curve** → Increased safe-haven demand → Higher Gold bias
- **Steep yield curve** → Risk-on environment → Lower Gold bias

### USD Pair Trading:
- **Inverted yield curve** → Fed cuts expected → USD weakens → Bullish for EUR/GBP
- **Steep yield curve** → Fed hikes expected → USD strengthens → Bearish for EUR/GBP

---

## Integration Status

✅ **FRED Service:** `get_2y10y_spread()` implemented  
✅ **Gold Bias:** Fed expectations integrated  
✅ **USD Pair Bias:** Fed expectations integrated  
✅ **Formatting:** Fed expectations displayed in summary  
✅ **Explanations:** Fed context added to bias explanations  

---

## Next Steps (Optional Enhancements)

1. **Track 2Y Yield Changes:**
   - Monitor 2Y yield momentum (rising/falling)
   - Add as secondary Fed expectations signal

2. **Add to Other Pairs:**
   - USDJPY (already tracks yield spreads)
   - Cross pairs (GBPJPY, EURJPY) for carry trade impact

3. **Historical Context:**
   - Compare current spread to 30-day average
   - Flag "spreading inversion" vs "narrowing inversion"

---

**Status:** ✅ **READY FOR PRODUCTION**

Fed expectations tracking is fully integrated and will enhance macro bias calculations for Gold and USD pairs.

