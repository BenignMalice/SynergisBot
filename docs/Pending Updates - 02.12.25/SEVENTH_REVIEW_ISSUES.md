# Seventh Review Issues - Configuration & Integration Gaps

## Critical Configuration Issues

### 1. **Strategy Map JSON Missing New Strategies**

**Issue:** The `app/config/strategy_map.json` file does not contain configurations for any of the 9 new SMC strategies. Strategies need configuration for SL/TP multipliers, RR floors, regime overrides, etc.

**Location:** `app/config/strategy_map.json`

**Current State:**
- Only contains existing strategies: `trend_pullback_ema`, `range_fade_sr`, `opening_range_breakout`, `liquidity_sweep_reversal`, `pattern_breakout_retest`, `hs_or_double_reversal`, etc.
- Missing: `order_block_rejection`, `breaker_block`, `market_structure_shift`, `fvg_retracement`, `mitigation_block`, `inducement_reversal`, `premium_discount_array`, `kill_zone`, `session_liquidity_run`

**Impact:**
- New strategies will use default/fallback configuration
- No symbol-specific or session-specific overrides
- No regime-specific SL/TP adjustments
- RR floors may be incorrect

**Fix Required:**
- **Phase 5.1: Add all 9 new strategies to strategy_map.json**
- Use the configuration structure provided in Phase 5 of the plan
- Ensure all strategies have:
  - `allow_regimes` or `regimes`
  - `sl_tp` configuration
  - `rr_floor`
  - `risk_base_pct`
  - `regime_overrides` (optional)
  - `session_overrides` (optional)
  - `symbol_overrides` (optional)

**Also Fix:** Line 288 has a syntax error - extra braces `{}` that break JSON structure.

### 2. **Strategy Selector STRATEGIES List Missing New Strategies**

**Issue:** The `STRATEGIES` list in `infra/strategy_selector.py` only contains 6 existing strategies. The bandit selector won't learn from new strategies.

**Location:** `infra/strategy_selector.py` (line 41-48)

**Current State:**
```python
STRATEGIES = [
    "trend_pullback_ema",
    "pattern_breakout_retest",
    "opening_range_breakout",
    "range_fade_sr",
    "liquidity_sweep_reversal",
    "hs_or_double_reversal",
]
```

**Missing:**
- `order_block_rejection`
- `breaker_block`
- `market_structure_shift`
- `fvg_retracement`
- `mitigation_block`
- `inducement_reversal`
- `premium_discount_array`
- `kill_zone`
- `session_liquidity_run`

**Impact:**
- Bandit selector won't track performance for new strategies
- No learning/optimization for new strategies
- May not be critical if bandit isn't actively used, but should be updated for consistency

**Fix Required:**
- Add all 9 new strategy names to `STRATEGIES` list
- Ensure names match exactly with strategy function names (after `_fn_to_strategy_name()` conversion)

### 3. **Universal Manager strategy_map Missing New Strategy Types**

**Issue:** The `strategy_map` dictionary in `UniversalDynamicSLTPManager._normalize_strategy_type()` only maps existing strategies. New strategy types will fall back to `DEFAULT_STANDARD`.

**Location:** `infra/universal_sl_tp_manager.py` (lines 407-416)

**Current State:**
```python
strategy_map = {
    "breakout_ib_volatility_trap": StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
    "breakout_bos": StrategyType.BREAKOUT_BOS,
    "trend_continuation_pullback": StrategyType.TREND_CONTINUATION_PULLBACK,
    "trend_continuation_bos": StrategyType.TREND_CONTINUATION_BOS,
    "liquidity_sweep_reversal": StrategyType.LIQUIDITY_SWEEP_REVERSAL,
    "order_block_rejection": StrategyType.ORDER_BLOCK_REJECTION,  # ✅ Exists
    "mean_reversion_range_scalp": StrategyType.MEAN_REVERSION_RANGE_SCALP,
    "mean_reversion_vwap_fade": StrategyType.MEAN_REVERSION_VWAP_FADE,
    "default_standard": StrategyType.DEFAULT_STANDARD,
}
```

**Missing Mappings:**
- `breaker_block` → `StrategyType.BREAKER_BLOCK` (enum doesn't exist yet - Phase 4.5.8)
- `market_structure_shift` → `StrategyType.MARKET_STRUCTURE_SHIFT` (enum doesn't exist yet)
- `fvg_retracement` → `StrategyType.FVG_RETRACEMENT` (enum doesn't exist yet)
- `mitigation_block` → `StrategyType.MITIGATION_BLOCK` (enum doesn't exist yet)
- `inducement_reversal` → `StrategyType.INDUCEMENT_REVERSAL` (enum doesn't exist yet)
- `premium_discount_array` → `StrategyType.PREMIUM_DISCOUNT_ARRAY` (enum doesn't exist yet)
- `session_liquidity_run` → `StrategyType.SESSION_LIQUIDITY_RUN` (enum doesn't exist yet)
- `kill_zone` → `StrategyType.KILL_ZONE` (enum doesn't exist yet)

**Impact:**
- New strategies will use `DEFAULT_STANDARD` trailing rules instead of strategy-specific rules
- May not get optimal SL/TP management
- Performance tracking may be incorrect

**Fix Required:**
- **Phase 4.5.8: After adding enum values, update strategy_map**
- Add all 8 new strategy type mappings to `strategy_map` dictionary
- Ensure string keys match exactly with strategy names used in plans

### 4. **Universal Manager Will Skip New Strategies**

**Issue:** Even after adding enum values and mappings, new strategies won't be managed by Universal Manager unless they're added to `UNIVERSAL_MANAGED_STRATEGIES` list.

**Location:** `infra/universal_sl_tp_manager.py` (lines 61-68, 626-628)

**Current State:**
```python
UNIVERSAL_MANAGED_STRATEGIES = [
    StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
    StrategyType.TREND_CONTINUATION_PULLBACK,
    StrategyType.LIQUIDITY_SWEEP_REVERSAL,
    StrategyType.ORDER_BLOCK_REJECTION,  # ✅ Exists
    StrategyType.MEAN_REVERSION_RANGE_SCALP,
    StrategyType.DEFAULT_STANDARD
]
```

**Code Check:**
```python
if strategy_type_enum not in UNIVERSAL_MANAGED_STRATEGIES:
    logger.debug(f"Trade {ticket} strategy {strategy_type_enum.value} not in UNIVERSAL_MANAGED_STRATEGIES - skipping")
    return None
```

**Impact:**
- New strategies won't get dynamic SL/TP management
- Will fall back to static SL/TP or DTMS
- May not get optimal trade management

**Fix Required:**
- **Phase 4.5.8: After adding enum values, add to UNIVERSAL_MANAGED_STRATEGIES**
- Decide which new strategies should be managed by Universal Manager
- Add them to the list (likely all 8 new strategies should be added)
- Consider if some strategies need different trailing rules (may need config updates)

### 5. **Missing get_volatility_spike() Method in DetectionSystemManager**

**Issue:** Phase 4.5.1 (kill zone check, line 3065) calls `detector.get_volatility_spike()`, but this method is not defined in the DetectionSystemManager interface.

**Location:**
- Phase 4.5.1 (line 3065) - Calls `detector.get_volatility_spike()`
- Phase 0.2.1 (DetectionSystemManager interface) - Method not defined

**Impact:**
- Kill zone condition check will fail with `AttributeError`
- Kill zone auto-execution plans won't execute

**Fix Required:**
- Add `get_volatility_spike()` method to DetectionSystemManager
- Implement volatility spike detection logic
- Or: Use existing volatility detection if available

**Implementation:**
```python
def get_volatility_spike(self, symbol: str, timeframe: str = "M5") -> Optional[Dict]:
    """Get volatility spike detection result"""
    cache_key = self._get_cache_key(symbol, timeframe, "volatility_spike")
    cached = self._get_cached(cache_key)
    if cached:
        return cached
    
    try:
        # Use existing volatility detection or implement new logic
        # Check ATR expansion, volume spike, etc.
        # Return: {"volatility_spike": bool, "atr_expansion": float, ...}
        pass
    except Exception as e:
        logger.warning(f"Volatility spike detection failed for {symbol}: {e}")
    
    return None
```

### 6. **Strategy Map JSON Syntax Error**

**Issue:** Line 288 in `app/config/strategy_map.json` has extra braces `{}` that create invalid JSON structure.

**Location:** `app/config/strategy_map.json` (line 288)

**Current State:**
```json
  },
  {  // ❌ Extra opening brace
  "generic_pending": {
```

**Impact:**
- JSON parsing may fail
- Strategy map may not load correctly
- Fallback to empty dict may occur

**Fix Required:**
- Remove extra `{` on line 288
- Ensure JSON structure is valid
- Test JSON parsing after fix

## Integration Gaps

### 7. **Registry Order Not Documented in Plan**

**Issue:** The plan specifies priority order for strategies, but doesn't show the exact `_REGISTRY` order that should be implemented. The current registry only has 6 strategies.

**Location:**
- Plan: Mentions priority order but doesn't show complete registry
- `app/engine/strategy_logic.py` (line 1979) - Current registry has 6 strategies

**Impact:**
- Implementers may not know exact order
- Priority hierarchy may be incorrect
- Higher-priority strategies may not be checked first

**Fix Required:**
- **Phase 3: Add complete _REGISTRY order to plan**
- Show exact order with all 9 new strategies inserted
- Document priority reasoning
- Example:
  ```python
  _REGISTRY = [
      strat_order_block_rejection,      # Highest priority (Tier 1)
      strat_breaker_block,              # Tier 1
      strat_market_structure_shift,      # Tier 1
      strat_fvg_retracement,             # Tier 2
      strat_mitigation_block,            # Tier 2
      strat_inducement_reversal,         # Tier 2
      strat_premium_discount_array,      # Tier 3
      strat_kill_zone,                   # Tier 3
      strat_session_liquidity_run,       # Tier 3
      strat_liquidity_sweep_reversal,    # Existing (keep)
      strat_trend_pullback_ema,          # Existing (keep)
      # ... etc
  ]
  ```

### 8. **Missing Strategy Configuration Documentation**

**Issue:** Phase 5 shows example configurations, but doesn't specify:
- Which strategies need symbol-specific overrides
- Which strategies need session-specific overrides
- Default values if configuration missing
- How to handle missing config gracefully

**Location:** Phase 5 (lines 3458-3549)

**Impact:**
- Implementers may not know what overrides are needed
- Strategies may use incorrect defaults
- No fallback strategy documented

**Fix Required:**
- Add documentation for:
  - Required vs optional configuration fields
  - Default values for missing fields
  - Symbol-specific requirements (e.g., BTC vs XAU)
  - Session-specific requirements
  - Graceful degradation if config missing

## Recommendations

1. **Fix Strategy Map JSON Syntax Error** (CRITICAL - blocks config loading)
   - Remove extra braces on line 288
   - Validate JSON structure

2. **Add All New Strategies to Strategy Map** (HIGH PRIORITY)
   - Complete Phase 5.1 implementation
   - Add all 9 strategies with full configuration
   - Include symbol and session overrides where needed

3. **Update Universal Manager After Enum Creation** (HIGH PRIORITY)
   - After Phase 4.5.8 creates enum values:
     - Add to `strategy_map` dictionary
     - Add to `UNIVERSAL_MANAGED_STRATEGIES` list
     - Test enum conversion

4. **Add get_volatility_spike() to DetectionSystemManager** (MEDIUM PRIORITY)
   - Implement method in Phase 0.2.1
   - Or: Document that kill zone requires this detection

5. **Update Strategy Selector STRATEGIES List** (LOW PRIORITY)
   - Add new strategies if bandit is actively used
   - Otherwise, document that it's optional

6. **Document Complete Registry Order** (MEDIUM PRIORITY)
   - Show exact _REGISTRY order in Phase 3
   - Include all existing strategies in correct priority

7. **Enhance Configuration Documentation** (MEDIUM PRIORITY)
   - Document required vs optional fields
   - Document default values
   - Document graceful degradation

## Summary

**Most Critical:**
1. Strategy map JSON syntax error (blocks config loading)
2. Missing strategy configurations (9 strategies need config)
3. Universal Manager won't manage new strategies (needs enum + list updates)

**High Priority:**
4. Missing get_volatility_spike() method
5. Registry order not fully documented

**Medium Priority:**
6. Strategy selector STRATEGIES list
7. Configuration documentation gaps

