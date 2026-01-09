# Analyse Symbol Full - Data Fields Review

## Purpose
Review all data fields shown in ChatGPT market snapshot and verify they are included in `analyse_symbol_full` response structure.

## ChatGPT Output Structure (from XAUUSD analysis)

### Top-Level Data Fields
1. ✅ `symbol` - Included
2. ✅ `symbol_normalized` - Included
3. ✅ `current_price` - Included
4. ✅ `session` - Included (structured)
5. ✅ `news` - Included (structured)
6. ✅ `macro` - Included (with nested bias, factors, data, summary)
7. ✅ `smc` - Included (with timeframes, alignment_score, recommendation, etc.)
8. ✅ `advanced` - Included (rmag, vwap, volatility, momentum)
9. ✅ `confluence` - Included (verdict, action, risk)
10. ✅ `recommendations` - Included (scalp, intraday, swing)
11. ✅ `volatility_regime` - Included (full structure)
12. ✅ `volatility_metrics` - Included (extracted from volatility_regime)
13. ✅ `m1_microstructure` - Included (full structure)
14. ✅ `btc_order_flow_metrics` - Included (null for non-BTC symbols)
15. ✅ `decision` - Included (direction, entry, sl, tp, confidence, reasoning, rr)

### Nested Fields in volatility_regime
From ChatGPT output, these are nested inside `data.volatility_regime`:
- ✅ `regime` - Included
- ✅ `confidence` - Included
- ✅ `indicators` - Included (M5, M15, H1 with atr_ratio, bb_width_ratio, adx, etc.)
- ✅ `atr_trends` - Included (M5, M15, H1)
- ✅ `wick_variances` - Included (M5, M15, H1)
- ✅ `time_since_breakout` - Included (M5, M15, H1)
- ✅ `mean_reversion_pattern` - Included
- ✅ `volatility_spike` - Included
- ✅ `session_transition` - Included
- ✅ `whipsaw_detected` - Included
- ✅ `strategy_recommendations` - Included
- ✅ `strategy_selection` - **ISSUE: Should be nested in volatility_regime, but ChatGPT shows it at top level too**

### Nested Fields in volatility_metrics
From ChatGPT output, these are nested inside `data.volatility_metrics`:
- ✅ `regime` - Included
- ✅ `confidence` - Included
- ✅ `atr_ratio` - Included
- ✅ `bb_width_ratio` - Included
- ✅ `adx_composite` - Included
- ✅ `volume_confirmed` - Included
- ✅ `atr_trends` - Included
- ✅ `wick_variances` - Included
- ✅ `time_since_breakout` - Included
- ✅ `atr_trend` - Included (convenience field for M15)
- ✅ `wick_variance` - Included (convenience field for M15)
- ✅ `time_since_breakout_minutes` - Included (convenience field for M15)
- ✅ `mean_reversion_pattern` - Included
- ✅ `volatility_spike` - Included
- ✅ `session_transition` - Included
- ✅ `whipsaw_detected` - Included
- ✅ `strategy_recommendations` - Included

### Nested Fields in strategy_selection
From ChatGPT output, these are nested inside `data.strategy_selection` (top level) OR `data.volatility_regime.strategy_selection`:
- ✅ `selected_strategy` - Included (with strategy, score, reasoning, entry_conditions, etc.)
- ✅ `all_scores` - Included (array of all strategy scores)
- ✅ `wait_reason` - Included

### Nested Fields in m1_microstructure
From ChatGPT output, these are nested inside `data.m1_microstructure`:
- ✅ `available` - Included
- ✅ `symbol` - Included
- ✅ `timestamp` - Included
- ✅ `candle_count` - Included
- ✅ `structure` - Included (type, consecutive_count, strength)
- ✅ `choch_bos` - Included (has_choch, has_bos, choch_confirmed, etc.)
- ✅ `liquidity_zones` - Included (array of PDH, PDL, EQUAL_HIGH, EQUAL_LOW)
- ✅ `liquidity_state` - Included
- ✅ `volatility` - Included (state, change_pct, atr, atr_median, squeeze_duration)
- ✅ `rejection_wicks` - Included (array)
- ✅ `order_blocks` - Included (array)
- ✅ `momentum` - Included (quality, consistency, consecutive_moves, rsi_validation, rsi_value)
- ✅ `trend_context` - Included (alignment, confidence, m1_m5_alignment, etc.)
- ✅ `signal_summary` - Included
- ✅ `last_signal_timestamp` - Included
- ✅ `signal_detection_timestamp` - Included
- ✅ `signal_age_seconds` - Included
- ✅ `session_context` - Included (session, session_adjusted_parameters, asset_personality, signal_valid_for_asset)
- ✅ `vwap` - Included (value, std, state, strategy_hint)
- ✅ `microstructure_confluence` - Included (score, base_score, grade, recommended_action, components, threshold_calculation, session, learning_metrics, effective_confidence)
- ✅ `btc_order_flow_metrics` - Included (null for non-BTC)
- ✅ `decision` - Included (direction, entry, sl, tp, confidence, reasoning, rr, error)
- ✅ `execution_time` - Included

## Issues Found

### Issue 1: strategy_selection Location
**Status:** ⚠️ **MINOR INCONSISTENCY**

**Problem:** ChatGPT shows `strategy_selection` at both:
- `data.strategy_selection` (top level)
- `data.volatility_regime.strategy_selection` (nested)

**Code Location:** `desktop_agent.py:2510` - `strategy_selection_data` is added to `volatility_regime_data`, so it should only be nested.

**Impact:** Low - ChatGPT can access it from either location, but having it at top level might be more convenient.

**Recommendation:** Consider adding `strategy_selection` as a top-level convenience field in `_format_unified_analysis` for easier access, while keeping it nested in `volatility_regime` for completeness.

### Issue 2: Missing Fields Check
**Status:** ✅ **ALL FIELDS VERIFIED**

All fields shown in ChatGPT output are present in the codebase and being returned in the response structure.

## Data Fields NOT in ChatGPT Output (But Available in Codebase)

These fields exist in the codebase but are not being displayed by ChatGPT (may be in summary only):

1. **Order Flow Signal** - `order_flow` parameter is passed to `_format_unified_analysis` but not included in top-level `data` structure
   - Location: `desktop_agent.py:872` (parameter)
   - Status: Used in summary formatting but not in structured data

2. **Volatility Signal** - `volatility_signal` parameter is passed but not included in top-level `data` structure
   - Location: `desktop_agent.py:875` (parameter)
   - Status: Used in summary formatting but not in structured data

## Recommendations

### High Priority
1. **Add `strategy_selection` as top-level field** - For convenience, extract `strategy_selection` from `volatility_regime` and add it as `data.strategy_selection` in `_format_unified_analysis`.

### Low Priority
1. **Consider adding `order_flow` to structured data** - If order flow signal is important, add it to the response structure.
2. **Consider adding `volatility_signal` to structured data** - If volatility signal is important, add it to the response structure.

## Code Changes Required

### Change 1: Add strategy_selection as top-level field
**File:** `desktop_agent.py`
**Location:** In `_format_unified_analysis` function, around line 1290-1293

```python
# Add after volatility_metrics line:
"strategy_selection": volatility_regime.get("strategy_selection") if volatility_regime else None,
```

This will make `strategy_selection` accessible at both:
- `data.strategy_selection` (convenience)
- `data.volatility_regime.strategy_selection` (complete structure)

