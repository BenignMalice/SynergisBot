# OpenAI YAML Update Requirements

**Date**: 2025-12-07  
**Purpose**: Document required updates to `openai.yaml` when volatility states implementation is completed

---

## ✅ YES - `openai.yaml` WILL NEED UPDATING

### Why Updates Are Required

1. **New Volatility States**: 4 new states added (PRE_BREAKOUT_TENSION, POST_BREAKOUT_DECAY, FRAGMENTED_CHOP, SESSION_SWITCH_FLARE)
2. **New Tracking Metrics**: ATR trends, wick variances, time since breakout added to response
3. **Tool Description**: Currently only mentions STABLE/TRANSITIONAL/VOLATILE
4. **Response Schema**: Comments need updating to reflect new states and metrics

---

## 📋 REQUIRED UPDATES

### 1. Update Tool Description (Line 55)

**Current**:
```yaml
- ⚡ VOLATILITY REGIME DETECTION ⭐ NEW - Automatic detection of STABLE/TRANSITIONAL/VOLATILE regimes
```

**Updated**:
```yaml
- ⚡ VOLATILITY REGIME DETECTION ⭐ NEW - Automatic detection of volatility regimes:
  - Basic states: STABLE, TRANSITIONAL, VOLATILE
  - Advanced states: PRE_BREAKOUT_TENSION, POST_BREAKOUT_DECAY, FRAGMENTED_CHOP, SESSION_SWITCH_FLARE
  - Includes confidence scores, ATR ratios, Bollinger Band analysis, and tracking metrics (ATR trends, wick variances, time since breakout)
```

---

### 2. Update Tool Description (Line 1505)

**Current**:
```yaml
description: "Comprehensive unified analysis for general market analysis. ⚡ NEW: Includes automatic volatility regime detection (STABLE, TRANSITIONAL, VOLATILE) with confidence scores, ATR ratios, and Bollinger Band analysis. Automatically selects volatility-aware trading strategies when VOLATILE regime detected (Breakout-Continuation, Volatility Reversion Scalp, Post-News Reaction Trade, Inside Bar Volatility Trap). Returns volatility-adjusted risk parameters (position size reduction, wider stop losses). Includes strategy selection scores and WAIT reason codes when no suitable strategy found. ⚠️ NOT for range scalping - use moneybot.analyse_range_scalp_opportunity instead when user asks for range scalping analysis. ⚠️ LIMITATIONS: Does NOT dynamically adjust alert zones, does NOT link pairs together, does NOT auto-enable features, only provides analysis data."
```

**Updated**:
```yaml
description: "Comprehensive unified analysis for general market analysis. ⚡ NEW: Includes automatic volatility regime detection with:
  - Basic states: STABLE, TRANSITIONAL, VOLATILE (with confidence scores, ATR ratios, Bollinger Band analysis)
  - Advanced states: PRE_BREAKOUT_TENSION (compression before breakout), POST_BREAKOUT_DECAY (momentum fading), FRAGMENTED_CHOP (whipsaw conditions), SESSION_SWITCH_FLARE (transition volatility spikes)
  - Tracking metrics: ATR trends (slope, decline rate), wick variances (increasing/decreasing), time since breakout (minutes/hours)
  - Strategy recommendations: Automatically selects volatility-aware trading strategies based on detected regime
  - Risk adjustments: Returns volatility-adjusted risk parameters (position size reduction, wider stop losses)
  - Strategy selection scores and WAIT reason codes when no suitable strategy found
⚠️ NOT for range scalping - use moneybot.analyse_range_scalp_opportunity instead when user asks for range scalping analysis. ⚠️ LIMITATIONS: Does NOT dynamically adjust alert zones, does NOT link pairs together, does NOT auto-enable features, only provides analysis data."
```

---

### 3. Update Response Schema Comment (Lines 1510-1515)

**Current**:
```yaml
# Response includes volatility_regime field with:
# - regime: STABLE/TRANSITIONAL/VOLATILE
# - confidence: 0-100%
# - atr_ratio: Multiplier of average ATR
# - strategy_selection: Selected strategy with entry/SL/TP if VOLATILE regime
# - wait_reasons: Array of reason codes if WAIT recommended
```

**Updated**:
```yaml
# Response includes volatility_metrics field with:
# - regime: STABLE/TRANSITIONAL/VOLATILE/PRE_BREAKOUT_TENSION/POST_BREAKOUT_DECAY/FRAGMENTED_CHOP/SESSION_SWITCH_FLARE
# - confidence: 0-100%
# - atr_ratio: Multiplier of average ATR
# - bb_width_ratio: Bollinger Band width ratio
# - adx_composite: Composite ADX score
# - volume_confirmed: Boolean (volume spike confirmed)
# - atr_trends: Per-timeframe ATR trend data (M5, M15, H1) with slope, slope_pct, is_declining, trend_direction
# - wick_variances: Per-timeframe wick variance data (M5, M15, H1) with current_variance, variance_change_pct, is_increasing
# - time_since_breakout: Per-timeframe time since breakout (M5, M15, H1) with time_since_minutes, breakout_type, is_recent
# - atr_trend: Convenience field (M15 primary timeframe)
# - wick_variance: Convenience field (M15 primary timeframe)
# - time_since_breakout_minutes: Convenience field (M15 primary timeframe)
# - mean_reversion_pattern: Mean reversion detection data (for FRAGMENTED_CHOP)
# - volatility_spike: Volatility spike detection data (for SESSION_SWITCH_FLARE)
# - session_transition: Session transition detection data (for SESSION_SWITCH_FLARE)
# - whipsaw_detected: Whipsaw detection data (for FRAGMENTED_CHOP)
# - strategy_recommendations: Selected strategy with entry/SL/TP based on volatility regime
# - wait_reasons: Array of reason codes if WAIT recommended
```

---

### 4. Update Tool Description (Line 55) - Alternative Shorter Version

If the description is too long, use this shorter version:

**Updated (Shorter)**:
```yaml
- ⚡ VOLATILITY REGIME DETECTION ⭐ NEW - Automatic detection of volatility regimes:
  - Basic: STABLE, TRANSITIONAL, VOLATILE
  - Advanced: PRE_BREAKOUT_TENSION, POST_BREAKOUT_DECAY, FRAGMENTED_CHOP, SESSION_SWITCH_FLARE
  - Includes tracking metrics: ATR trends, wick variances, time since breakout
```

---

### 5. Add Usage Guidance for New States

**Add to tool description or create new section**:

```yaml
# Volatility State Usage:
# - PRE_BREAKOUT_TENSION: Favor breakout strategies (breakout_ib_volatility_trap, liquidity_sweep_reversal)
# - POST_BREAKOUT_DECAY: Avoid trend continuation, favor mean reversion (mean_reversion_range_scalp)
# - FRAGMENTED_CHOP: Only allow micro_scalp and mean_reversion_range_scalp strategies
# - SESSION_SWITCH_FLARE: Block ALL strategies - wait for volatility stabilization
```

---

## 📊 DETAILED UPDATE LOCATIONS

### Location 1: Tool List Description (Line ~55)

**File**: `openai.yaml`  
**Section**: Tool descriptions (near top of file)  
**Current Text**: 
```
- ⚡ VOLATILITY REGIME DETECTION ⭐ NEW - Automatic detection of STABLE/TRANSITIONAL/VOLATILE regimes
```

**Action**: Update to include new states and tracking metrics

---

### Location 2: Tool Schema Description (Line ~1505)

**File**: `openai.yaml`  
**Section**: `analyseSymbolFull` tool description  
**Current Text**: 
```
description: "Comprehensive unified analysis... Includes automatic volatility regime detection (STABLE, TRANSITIONAL, VOLATILE)..."
```

**Action**: Update to list all 7 volatility states and mention tracking metrics

---

### Location 3: Response Schema Comment (Lines ~1510-1515)

**File**: `openai.yaml`  
**Section**: `analyseSymbolFull` example response comment  
**Current Text**: 
```
# Response includes volatility_regime field with:
# - regime: STABLE/TRANSITIONAL/VOLATILE
```

**Action**: Update to show all states and new tracking metrics structure

---

## 🔧 IMPLEMENTATION CHECKLIST

### Phase 4 Completion (Before Updating openai.yaml)

- [ ] Phase 1: Core Detection implemented
- [ ] Phase 2: Strategy Selection updated
- [ ] Phase 3: Auto-Execution Validation added
- [ ] **Phase 4: Analysis Tool Updates** ← **MUST BE COMPLETE**
  - [ ] `desktop_agent.py` updated to return new metrics
  - [ ] `volatility_metrics` object includes all new fields
  - [ ] Response structure tested and verified

### openai.yaml Updates (After Phase 4)

- [ ] Update tool list description (Line ~55)
- [ ] Update tool schema description (Line ~1505)
- [ ] Update response schema comment (Lines ~1510-1515)
- [ ] Add usage guidance for new states (optional)
- [ ] Test tool description clarity
- [ ] Verify ChatGPT can understand new states

---

## 📝 EXAMPLE UPDATED SECTIONS

### Example 1: Tool List Description

```yaml
- ⚡ VOLATILITY REGIME DETECTION ⭐ NEW - Automatic detection of volatility regimes:
  - Basic states: STABLE, TRANSITIONAL, VOLATILE (with confidence scores, ATR ratios, Bollinger Band analysis)
  - Advanced states: PRE_BREAKOUT_TENSION (compression before breakout), POST_BREAKOUT_DECAY (momentum fading), FRAGMENTED_CHOP (whipsaw conditions), SESSION_SWITCH_FLARE (transition volatility spikes)
  - Tracking metrics: ATR trends (slope, decline rate), wick variances (increasing/decreasing), time since breakout (minutes/hours)
  - Strategy recommendations: Automatically selects volatility-aware trading strategies based on detected regime
```

### Example 2: Tool Schema Description

```yaml
analyseSymbolFull:
  summary: Get Unified Analysis (RECOMMENDED - General Analysis)
  description: |
    Comprehensive unified analysis for general market analysis.
    
    ⚡ VOLATILITY REGIME DETECTION:
    - Basic states: STABLE, TRANSITIONAL, VOLATILE
    - Advanced states: PRE_BREAKOUT_TENSION, POST_BREAKOUT_DECAY, FRAGMENTED_CHOP, SESSION_SWITCH_FLARE
    - Tracking metrics: ATR trends (per timeframe), wick variances (per timeframe), time since breakout (per timeframe)
    - Strategy recommendations: Auto-selects best strategy based on volatility regime
    - Risk adjustments: Position size reduction, wider stops for volatile markets
    
    ⚠️ NOT for range scalping - use moneybot.analyse_range_scalp_opportunity instead.
    ⚠️ LIMITATIONS: Does NOT dynamically adjust alert zones, does NOT link pairs together, does NOT auto-enable features, only provides analysis data.
```

### Example 3: Response Schema Comment

```yaml
# Response includes volatility_metrics object with:
# 
# Basic Fields:
# - regime: STABLE/TRANSITIONAL/VOLATILE/PRE_BREAKOUT_TENSION/POST_BREAKOUT_DECAY/FRAGMENTED_CHOP/SESSION_SWITCH_FLARE
# - confidence: 0-100%
# - atr_ratio: Multiplier of average ATR
# - bb_width_ratio: Bollinger Band width ratio
# - adx_composite: Composite ADX score
# - volume_confirmed: Boolean
#
# Tracking Metrics (Per-Timeframe: M5, M15, H1):
# - atr_trends: {M5: {...}, M15: {...}, H1: {...}}
#   Each timeframe includes: current_atr, slope, slope_pct, is_declining, is_above_baseline, trend_direction
# - wick_variances: {M5: {...}, M15: {...}, H1: {...}}
#   Each timeframe includes: current_variance, previous_variance, variance_change_pct, is_increasing, current_ratio, mean_ratio
# - time_since_breakout: {M5: {...}, M15: {...}, H1: {...}}
#   Each timeframe includes: time_since_minutes, time_since_hours, breakout_type, breakout_price, breakout_timestamp, is_recent
#
# Convenience Fields (M15 Primary):
# - atr_trend: Same as atr_trends["M15"]
# - wick_variance: Same as wick_variances["M15"]
# - time_since_breakout_minutes: Same as time_since_breakout["M15"]["time_since_minutes"]
#
# Advanced Detection Fields:
# - mean_reversion_pattern: {is_mean_reverting, oscillation_around_vwap, oscillation_around_ema, touch_count, reversion_strength}
# - volatility_spike: {is_spike, current_atr, spike_ratio, spike_magnitude, is_temporary}
# - session_transition: {is_transition, transition_type, minutes_into_transition, ...}
# - whipsaw_detected: {is_whipsaw, direction_changes, oscillation_around_mean}
#
# Strategy & Recommendations:
# - strategy_recommendations: Selected strategy with entry/SL/TP based on volatility regime
# - wait_reasons: Array of reason codes if WAIT recommended
```

---

## ⚠️ IMPORTANT NOTES

### 1. Update Timing

**DO NOT update `openai.yaml` until Phase 4 is complete**:
- Phase 4 updates `desktop_agent.py` to return new metrics
- Response structure must be finalized before documenting
- Test the actual response structure before updating schema comments

### 2. Backward Compatibility

**Maintain backward compatibility**:
- Existing states (STABLE, TRANSITIONAL, VOLATILE) remain unchanged
- New states are additions, not replacements
- ChatGPT should handle both old and new response structures

### 3. Documentation Accuracy

**Ensure accuracy**:
- Response schema comments must match actual response structure
- Tool descriptions must match actual capabilities
- Test with actual tool calls before finalizing

### 4. ChatGPT Understanding

**Help ChatGPT understand new states**:
- Provide clear descriptions of when each state occurs
- Explain strategy recommendations for each state
- Include usage examples in tool description

---

## ✅ FINAL CHECKLIST

Before updating `openai.yaml`:

- [ ] Phase 4 implementation complete
- [ ] `volatility_metrics` response structure finalized
- [ ] Actual response tested and verified
- [ ] All 7 volatility states working correctly
- [ ] Tracking metrics included in response
- [ ] Strategy recommendations working
- [ ] Auto-execution validation working

After updating `openai.yaml`:

- [ ] Tool description updated (Line ~55)
- [ ] Tool schema description updated (Line ~1505)
- [ ] Response schema comment updated (Lines ~1510-1515)
- [ ] Usage guidance added (optional)
- [ ] ChatGPT tested with new descriptions
- [ ] Response structure matches documentation

---

## 📚 REFERENCE

- **Implementation Plan**: `VOLATILITY_STATES_IMPLEMENTATION_PLAN.md` Phase 4
- **Response Structure**: See Phase 4 Section 4.1 for exact `volatility_metrics` structure
- **Current openai.yaml**: Lines 55, 1505, 1510-1515

---

# END_OF_DOCUMENT

