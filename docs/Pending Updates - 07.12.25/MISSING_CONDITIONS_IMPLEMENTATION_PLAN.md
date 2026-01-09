# Missing Conditions Implementation Plan

**Date**: 2026-01-07  
**Total Conditions**: 15 conditions across 4 categories  
**Estimated Effort**: 12-16 days  
**Priority**: High (60% of pending plans depend on these)

---

## Executive Summary

This plan outlines the implementation of 15 missing conditions that prevent 12 pending plans (60% of total) from executing. Conditions are organized by complexity and priority for phased implementation.

### Implementation Phases

| Phase | Category | Conditions | Effort | Priority |
|-------|----------|------------|--------|----------|
| **Phase 1** | Quantitative (Quick Wins) | 3 | 2-3 days | **HIGH** |
| **Phase 2** | Correlation (Moderate) | 3 | 2-3 days | **HIGH** |
| **Phase 3** | Session (Moderate-High) | 4 | 4-5 days | **MEDIUM** |
| **Phase 4** | Pattern (High Complexity) | 2 | 3-4 days | **LOW** |
| **Phase 5** | Correlation (Advanced) | 2 | 1-2 days | **MEDIUM** |
| **TOTAL** | - | **15** | **12-17 days** | - |

---

## Phase 1: Quantitative Conditions (Quick Wins)

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Priority**: **HIGH**  
**Effort**: 2-3 days  
**Impact**: 5 plans will execute

### 1.1 `bb_retest` - Bollinger Band Retest

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: Medium  
**Dependencies**: Existing BB calculation, candle fetching  
**Estimated Time**: 1 day

#### Implementation Steps

**Step 1.1.1: Add Condition Check Location**
- **File**: `auto_execution_system.py`
- **Location**: After `bb_expansion` check (around line 5204)
- **Action**: Add new condition check block

**Step 1.1.2: Implement On-the-Fly Price History Tracking**
- **Approach**: Calculate BB history from recent candles (no persistent state)
- **Data Needed**: 30-50 recent candles on specified timeframe
- **Logic**:
  1. Fetch recent candles (50 candles for sufficient history)
  2. Calculate BB for each candle in history (rolling 20-period window)
  3. Scan backwards to find most recent BB break
  4. Check if price is now retesting that BB level (within tolerance)
  5. Verify bounce/rejection (price moves away from BB after retest)

**Step 1.1.3: Break Detection Logic**
```python
# Pseudo-code structure
for each candle in history (backwards from recent):
    calculate BB (upper, lower, middle) for that point in time
    compare current candle high/low to previous candle's BB level
    
    if bullish break detected (high > upper BB, previous didn't):
        store break info: level, direction, timestamp
        break
    
    if bearish break detected (low < lower BB, previous didn't):
        store break info: level, direction, timestamp
        break
```

**Step 1.1.4: Retest Detection Logic**
```python
# Check recent candles (last 2-3) for retest
for recent candle:
    calculate distance from broken BB level
    if distance <= tolerance (default 0.5%):
        retest detected
        verify bounce (price moves away from BB)
```

**Step 1.1.5: Configuration Parameters**
- `bb_retest_tolerance`: Default 0.5% (configurable per plan)
- `bb_retest_lookback`: Default 30 candles (configurable)
- `bb_retest_require_bounce`: Default True (require rejection after retest)

**Step 1.1.6: Integration Points**
- **CRITICAL**: `_get_recent_candles()` and `_normalize_candles()` are **LOCAL functions** defined inside `_check_conditions()` (lines 3188, 3230)
- These are NOT instance methods - they're accessible within the `_check_conditions` method scope
- Reuse BB calculation logic from `bb_expansion` (lines 5184-5191)
- **Placement**: Add condition check immediately after `bb_expansion` check (after line 5204)

**Step 1.1.7: Testing Requirements**
- **See "Testing Strategy" section for detailed unit and integration test specifications**
- Functional test cases:
  - Test bullish break → retest → bounce
  - Test bearish break → retest → bounce
  - Test break without retest (should fail)
  - Test retest without bounce (should fail if `require_bounce=True`)
  - Test with different timeframes (M5, M15, H1)
  - Test with different tolerance values
- **Unit Tests**: See `TestBBRetestCondition` in `test_missing_conditions_phase1_quantitative.py`
- **Integration Tests**: See Phase 1 integration tests

**Step 1.1.8: Error Handling**
- Wrap in try/except block (follow existing pattern)
- Handle insufficient candles (< 30) - return False with debug log
- Handle missing BB calculation data - return False
- Handle edge cases (price exactly at BB level)
- Log debug messages for troubleshooting (use `logger.debug()` for failures, `logger.info()` for successes)
- **CRITICAL**: Return `False` immediately if condition not met (fail-fast pattern)

**Step 1.1.9: Add to has_conditions Check**
- **File**: `auto_execution_system.py`
- **Location**: Line 6161 (in `has_conditions` list)
- **Action**: Add `"bb_retest" in plan.conditions` to the list
- **Purpose**: Ensures plans with `bb_retest` are recognized as having conditions

**Files to Modify**:
- `auto_execution_system.py` (add condition check ~line 5204, add to has_conditions ~line 6161)

**Estimated Effort**: 1 day

---

### 1.2 `zscore` / `z_threshold` - Statistical Mean Reversion

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: Low  
**Dependencies**: Candle data, basic statistics  
**Estimated Time**: 0.5 days

#### Implementation Steps

**Step 1.2.1: Add Condition Check Location**
- **File**: `auto_execution_system.py`
- **Location**: After volatility conditions section (after `bb_expansion`/`bb_retest` checks, around line 5236)
- **Action**: Add new condition check block for statistical conditions
- **Note**: Add before "Phase III: Volatility Pattern Recognition" section (line 5238)

**Step 1.2.2: Calculate Z-Score**
```python
# Formula: z_score = (current_price - mean_price) / std_dev_price

# 1. Fetch recent candles (20-50 periods)
# 2. Extract close prices
# 3. Calculate mean: sum(prices) / len(prices)
# 4. Calculate standard deviation: sqrt(sum((price - mean)^2) / len(prices))
# 5. Calculate z-score: (current_price - mean) / std_dev
# 6. Check if |z_score| >= threshold
```

**Step 1.2.3: Mean Reversion Logic**
- For **mean reversion** strategies: Z-score > threshold suggests price is "overextended"
- Direction check: If plan direction is BUY and z_score < -threshold (price below mean), condition met
- If plan direction is SELL and z_score > threshold (price above mean), condition met

**Step 1.2.4: Configuration Parameters**
- `z_threshold`: Default 2.0 (2 standard deviations)
- `zscore_lookback`: Default 20 periods (configurable)
- `zscore_direction`: Optional - "above" or "below" mean

**Step 1.2.5: Integration Points**
- **CRITICAL**: `_get_recent_candles()` is a **LOCAL function** inside `_check_conditions()` (line 3230)
- Use manual calculation for mean/std_dev (simple math, no external dependencies needed)
- **Placement**: Add after volatility conditions section (after `bb_expansion`/`bb_retest` checks)

**Step 1.2.6: Add to has_conditions Check**
- **File**: `auto_execution_system.py`
- **Location**: Line 6161 (in `has_conditions` list)
- **Action**: Add `"zscore" in plan.conditions` to the list

**Step 1.2.7: Testing Requirements**
- **See "Testing Strategy" section for detailed unit and integration test specifications**
- Functional test cases:
  - Test with z_score = 2.5 (above threshold)
  - Test with z_score = 1.5 (below threshold, should fail)
  - Test with different lookback periods
  - Test with different threshold values
  - Test mean reversion direction logic
- **Unit Tests**: See `TestZScoreCondition` in `test_missing_conditions_phase1_quantitative.py`
- **Integration Tests**: See Phase 1 integration tests

**Files to Modify**:
- `auto_execution_system.py` (add condition check)

**Estimated Effort**: 0.5 days

---

### 1.3 `atr_stretch` / `atr_multiple` - ATR Stretch Reversal

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: Low  
**Dependencies**: Existing ATR calculation  
**Estimated Time**: 0.5 days

#### Implementation Steps

**Step 1.3.1: Add Condition Check Location**
- **File**: `auto_execution_system.py`
- **Location**: After `zscore` check (same section as statistical conditions)
- **Action**: Add new condition check block for ATR stretch
- **Note**: Add in same statistical conditions section as `zscore` (before "Phase III: Volatility Pattern Recognition")

**Step 1.3.2: Reuse Existing ATR Calculation**
- **CRITICAL**: `_calculate_atr()` is a **LOCAL helper function** defined inside `_check_conditions()` (line 5737)
- **Note**: There's also `_calculate_atr_simple()` at line 3245 - use `_calculate_atr()` (line 5737) which is more complete
- **Reuse**: Call `_calculate_atr(candles, period=14)` directly (it's in scope within `_check_conditions`)

**Step 1.3.3: Calculate Stretch Ratio**
```python
# 1. Calculate ATR using existing _calculate_atr() function
# 2. Determine reference price:
#    - Option 1: Entry price from plan
#    - Option 2: Recent swing high/low
#    - Option 3: VWAP or moving average
# 3. Calculate distance: abs(current_price - reference_price)
# 4. Calculate stretch: distance / ATR
# 5. Check if stretch >= atr_multiple (e.g., 2.5x ATR)
```

**Step 1.3.4: Reference Price Selection**
- **Priority 1**: Use `entry_price` from plan if available
- **Priority 2**: Use recent swing high/low (last 20 candles)
- **Priority 3**: Use VWAP or SMA if available
- **Configurable**: Via `atr_stretch_reference` parameter

**Step 1.3.5: Configuration Parameters**
- `atr_multiple`: Default 2.5 (configurable per plan)
- `atr_stretch_reference`: "entry", "swing_high", "swing_low", "vwap", "sma"
- `atr_period`: Default 14 (reuse existing ATR period)

**Step 1.3.6: Integration Points**
- **CRITICAL**: `_calculate_atr()` is a **LOCAL function** inside `_check_conditions()` (line 5737)
- Reuse `_get_recent_candles()` local function (line 3230)
- May need swing point detection (can be simple: max/min of recent candles)
- **Placement**: Add after existing ATR-based volatility conditions (around line 5766, after `_calculate_atr` helper definition)

**Step 1.3.7: Add to has_conditions Check**
- **File**: `auto_execution_system.py`
- **Location**: Line 6161 (in `has_conditions` list)
- **Action**: Add `"atr_stretch" in plan.conditions` or `"atr_multiple" in plan.conditions` to the list

**Step 1.3.8: Testing Requirements**
- **See "Testing Strategy" section for detailed unit and integration test specifications**
- Functional test cases:
  - Test with stretch = 3.0x ATR (above threshold)
  - Test with stretch = 2.0x ATR (below threshold, should fail)
  - Test with different reference prices
  - Test with different ATR multiples
  - Test reversal logic (stretched price should revert)
- **Unit Tests**: See `TestATRStretchCondition` in `test_missing_conditions_phase1_quantitative.py`
- **Integration Tests**: See Phase 1 integration tests

**Files to Modify**:
- `auto_execution_system.py` (add condition check)

**Estimated Effort**: 0.5 days

---

## Phase 2: Correlation Conditions (Moderate Complexity)

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Priority**: **HIGH**  
**Effort**: 2-3 days  
**Impact**: 4 plans will execute

### 2.1 `spx_up_pct` - S&P 500 Percentage Change

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: Medium  
**Dependencies**: Yahoo Finance integration, correlation calculator  
**Estimated Time**: 1 day

#### Implementation Steps

**Step 2.1.1: Add Method to Correlation Calculator**
- **File**: `infra/correlation_context_calculator.py`
- **Action**: **MUST add new method** `calculate_spx_change_pct()` - similar to existing `calculate_dxy_change_pct()` (line 558)
- **Pattern**: Follow exact same pattern as `calculate_dxy_change_pct()`:
  - Check if `self.market_indices` exists (graceful degradation)
  - Use `yfinance` directly: `yf.Ticker("^GSPC")`
  - Fetch historical data: `history(period="2d", interval="5m")`
  - Calculate percentage change: `((current_price - past_price) / past_price) * 100`
  - Return `Optional[float]` (percentage change) or `None` if unavailable

**Step 2.1.2: Method Implementation Details**
- **CRITICAL**: Method signature: `async def calculate_spx_change_pct(self, window_minutes: int = 60) -> Optional[float]`
- **Data Source**: Yahoo Finance (`^GSPC` symbol)
- **Error Handling**: Must handle `yfinance` failures gracefully (return None, log warning)
- **Dependency**: Method should work even if `market_indices` is None (use `yfinance` directly)
- **Note**: Do NOT use `market_indices_service.get_sp500_bars()` - that returns historical bars, not percentage change

**Step 2.1.3: Calculate Percentage Change**
```python
# 1. Fetch SPX current price
# 2. Fetch SPX price N minutes/hours ago (window from conditions)
# 3. Calculate: (current_price - past_price) / past_price * 100
# 4. Check if change >= spx_up_pct threshold (e.g., 0.5%)
```

**Step 2.1.4: Add Condition Check**
- **File**: `auto_execution_system.py`
- **Location**: In Phase III correlation section (around line 4232)
- **CRITICAL**: Must be inside `if self.correlation_calculator:` block (line 4236)
- **Pattern**: Similar to existing `dxy_change_pct` logic (line 4239)
- **Placement**: Add after `dxy_change_pct` check (after line 4265) or after `dxy_stall_detected` check

**Step 2.1.5: Caching Strategy**
- Cache SPX data for 1-5 minutes (avoid excessive API calls)
- Use same caching pattern as DXY (lines 4242-4257)
- **CRITICAL**: Use instance methods `self._get_cached_correlation()` and `self._cache_correlation()` (lines 7356, 7377)
- Cache key: `f"spx_change_{plan.symbol}_{window_minutes}"`
- **Pattern**: Check cache first, if None, calculate and cache, then check threshold

**Step 2.1.6: Configuration Parameters**
- `spx_up_pct`: Threshold percentage (e.g., 0.5 = 0.5%)
- `spx_change_window`: Time window in minutes (default: 15 or 60)
- `correlation_asset`: Must be "SPX" or "SP500"

**Step 2.1.7: Integration Points**
- **CRITICAL**: Must check `if self.correlation_calculator:` exists (line 4236)
- **CRITICAL**: New method `calculate_spx_change_pct()` MUST be added to `correlation_context_calculator.py` (not optional)
- **CRITICAL**: Method must handle `market_indices` being None (use `yfinance` directly, like `calculate_dxy_change_pct()` does)
- Reuse correlation caching: `self._get_cached_correlation()` and `self._cache_correlation()`
- Follow same async pattern as `dxy_change_pct` (lines 4245-4257) - use `asyncio.get_event_loop()` or `asyncio.new_event_loop()`
- **Error Handling**: Wrap in try/except, return False on error (fail-closed pattern)
- **Call Pattern**: `loop.run_until_complete(self.correlation_calculator.calculate_spx_change_pct(window_minutes=60))`

**Step 2.1.8: Add to has_conditions Check**
- **File**: `auto_execution_system.py`
- **Location**: Line 6161 (in `has_conditions` list)
- **Action**: Add `"spx_up_pct" in plan.conditions` or `"correlation_asset" in plan.conditions` to the list

**Step 2.1.9: Testing Requirements**
- **See "Testing Strategy" section for detailed unit and integration test specifications**
- Functional test cases:
  - Test with SPX up 0.6% (above threshold)
  - Test with SPX up 0.3% (below threshold, should fail)
  - Test with different time windows
  - Test caching behavior
  - Test error handling (Yahoo Finance unavailable)
- **Unit Tests**: See `TestSPXChangeCondition` in `test_missing_conditions_phase2_correlation.py`
- **Integration Tests**: See Phase 2 integration tests

**Files to Modify**:
- `auto_execution_system.py` (add condition check ~line 4232)
- **REQUIRED**: `infra/correlation_context_calculator.py` (add `calculate_spx_change_pct()` method - NOT optional)

**Estimated Effort**: 1 day

---

### 2.2 `yield_drop` - US 10Y Yield Change

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: Medium  
**Dependencies**: Yahoo Finance integration (already fetches US10Y)  
**Estimated Time**: 0.5 days

#### Implementation Steps

**Step 2.2.1: Add Method to Correlation Calculator**
- **File**: `infra/correlation_context_calculator.py`
- **Action**: **MUST add new method** `calculate_us10y_yield_change()` - similar to `calculate_dxy_change_pct()` (line 558)
- **Pattern**: Follow exact same pattern as `calculate_dxy_change_pct()`:
  - Check if `self.market_indices` exists (graceful degradation)
  - Use `yfinance` directly: `yf.Ticker("^TNX")`
  - Fetch historical data: `history(period="2d", interval="5m")`
  - Calculate yield change: `current_yield - past_yield` (in basis points or percentage)
  - Return `Optional[float]` (yield change) or `None` if unavailable
- **Note**: Do NOT use `market_indices_service.get_us10y_bars()` - that returns historical bars, not yield change

**Step 2.2.2: Calculate Yield Change**
```python
# 1. Fetch US10Y current yield (^TNX from Yahoo Finance)
# 2. Fetch US10Y yield N minutes/hours ago
# 3. Calculate change: current_yield - past_yield
# 4. Check if yield_drop >= threshold (e.g., 0.05 = 5 basis points)
# Note: For "drop", we check if change is negative and magnitude >= threshold
```

**Step 2.2.3: Add Condition Check**
- **File**: `auto_execution_system.py`
- **Location**: In Phase III correlation section (after SPX check)
- **CRITICAL**: Must be inside `if self.correlation_calculator:` block (line 4236)
- **Pattern**: Similar to SPX implementation
- **Placement**: Add after SPX check, before `ethbtc_ratio_deviation` check (around line 4313)

**Step 2.2.4: Caching Strategy**
- Cache US10Y data for 1-5 minutes
- **CRITICAL**: Use instance methods `self._get_cached_correlation()` and `self._cache_correlation()`
- Cache key: `f"us10y_change_{plan.symbol}_{window_minutes}"`

**Step 2.2.5: Configuration Parameters**
- `yield_drop`: Threshold in basis points (e.g., 0.05 = 5 bps)
- `yield_change_window`: Time window in minutes (default: 15 or 60)
- `correlation_asset`: Must be "US10Y" or "TNX"

**Step 2.2.6: Integration Points**
- **CRITICAL**: Must check `if self.correlation_calculator:` exists (line 4236)
- **CRITICAL**: New method `calculate_us10y_yield_change()` MUST be added to `correlation_context_calculator.py` (not optional)
- **CRITICAL**: Method must handle `market_indices` being None (use `yfinance` directly, like `calculate_dxy_change_pct()` does)
- Reuse Yahoo Finance integration (`yfinance` library)
- Follow SPX implementation pattern (async with event loop)
- Reuse correlation caching: `self._get_cached_correlation()` and `self._cache_correlation()`
- **Error Handling**: Wrap in try/except, return False on error
- **Call Pattern**: `loop.run_until_complete(self.correlation_calculator.calculate_us10y_yield_change(window_minutes=60))`

**Step 2.2.7: Add to has_conditions Check**
- **File**: `auto_execution_system.py`
- **Location**: Line 6161 (in `has_conditions` list)
- **Action**: Add `"yield_drop" in plan.conditions` to the list

**Step 2.2.8: Testing Requirements**
- **See "Testing Strategy" section for detailed unit and integration test specifications**
- Functional test cases:
  - Test with yield drop of 6 bps (above threshold)
  - Test with yield drop of 3 bps (below threshold, should fail)
  - Test with yield increase (should fail for "drop" condition)
  - Test caching behavior
  - Test error handling
- **Unit Tests**: See `TestUS10YYieldChangeCondition` in `test_missing_conditions_phase2_correlation.py`
- **Integration Tests**: See Phase 2 integration tests

**Files to Modify**:
- `auto_execution_system.py` (add condition check)

**Estimated Effort**: 0.5 days

---

### 2.3 `correlation_divergence` - DXY and Symbol Divergence

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: Medium-High  
**Dependencies**: Correlation calculator (already calculates DXY correlation)  
**Estimated Time**: 1 day

#### Implementation Steps

**Step 2.3.1: Extend Correlation Calculator**
- **File**: `infra/correlation_context_calculator.py`
- **Existing**: Already calculates `corr_vs_dxy` (line 150)
- **Action**: Add divergence detection method

**Step 2.3.2: Calculate Divergence**
```python
# 1. Fetch recent price movements for both DXY and symbol (last 60 minutes)
# 2. Calculate correlation coefficient over lookback window
# 3. Check if correlation is negative (moving in opposite directions)
# 4. Verify divergence is significant (correlation < -0.5 or similar threshold)
# 5. For BTC: DXY down + BTC up = bullish divergence
```

**Step 2.3.3: Divergence Detection Logic**
- **Direction Check**: 
  - If DXY moving down AND symbol moving up → Bullish divergence
  - If DXY moving up AND symbol moving down → Bearish divergence
- **Strength Check**: Correlation coefficient < -0.5 (strong negative correlation)

**Step 2.3.4: Add Condition Check**
- **File**: `auto_execution_system.py`
- **Location**: In Phase III correlation section
- **CRITICAL**: Must be inside `if self.correlation_calculator:` block (line 4236)
- **Pattern**: Use existing correlation calculator methods
- **Placement**: Add after existing correlation checks (after NASDAQ check, around line 4377)

**Step 2.3.5: Configuration Parameters**
- `correlation_divergence`: Boolean (true = require divergence)
- `divergence_threshold`: Correlation threshold (default: -0.5)
- `divergence_window`: Lookback window in minutes (default: 60)
- `correlation_asset`: Must be "DXY"

**Step 2.3.6: Integration Points**
- **CRITICAL**: Must check `if self.correlation_calculator:` exists (line 4236)
- Reuse `correlation_calculator.calculate_correlation_context()` - already calculates `corr_vs_dxy`
- **Action**: Add new method `detect_dxy_divergence()` to `correlation_context_calculator.py`
- Method should return: `{"divergence_detected": bool, "correlation": float, "dxy_direction": str, "symbol_direction": str}`
- Use async pattern with event loop (same as other correlation checks)
- **Error Handling**: Wrap in try/except, return False on error

**Step 2.3.7: Add to has_conditions Check**
- **File**: `auto_execution_system.py`
- **Location**: Line 6161 (in `has_conditions` list)
- **Action**: Add `"correlation_divergence" in plan.conditions` to the list

**Step 2.3.8: Testing Requirements**
- **See "Testing Strategy" section for detailed unit and integration test specifications**
- Functional test cases:
  - Test with strong divergence (correlation = -0.7)
  - Test with weak divergence (correlation = -0.3, should fail)
  - Test with positive correlation (should fail)
  - Test with different time windows
  - Test direction logic (DXY down + symbol up)
- **Unit Tests**: See `TestCorrelationDivergenceCondition` in `test_missing_conditions_phase2_correlation.py`
- **Integration Tests**: See Phase 2 integration tests

**Files to Modify**:
- `auto_execution_system.py` (add condition check)
- `infra/correlation_context_calculator.py` (add divergence method)

**Estimated Effort**: 1 day

---

## Phase 3: Session Conditions (Moderate-High Complexity)

**Priority**: **MEDIUM**  
**Effort**: 4-5 days  
**Impact**: 4 plans will execute

### 3.1 `volatility_decay` - ATR Decreasing Over Time

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: Medium  
**Dependencies**: Existing ATR calculation, session helpers  
**Estimated Time**: 1 day

#### Implementation Steps

**Step 3.1.1: Add Condition Check Location**
- **File**: `auto_execution_system.py`
- **Location**: After order flow conditions section (around line 5647, where session-based conditions are checked)
- **Action**: Add new condition check block in session conditions section
- **Note**: There's already a "Check session-based conditions" comment at line 5647 - add after that section

**Step 3.1.2: Track ATR Over Time**
```python
# 1. Calculate ATR for recent periods (e.g., last 5 candles)
# 2. Calculate ATR for earlier periods in session (e.g., 5-10 candles ago)
# 3. Compare: recent_ATR < earlier_ATR * decay_threshold (e.g., 0.8 = 20% decrease)
# 4. Verify we're in appropriate session (e.g., NY close)
```

**Step 3.1.3: Session Context**
- **Requirement**: Must be in appropriate session (e.g., NY close for volatility decay)
- **Integration**: Use `SessionHelpers.get_current_session()` static method (already exists in `infra/session_helpers.py`)
- **CRITICAL**: Check session FIRST before doing expensive ATR calculations (performance optimization)
- **Check**: Verify session matches plan's `session` condition
- **Import**: `from infra.session_helpers import SessionHelpers`

**Step 3.1.4: ATR Comparison Logic**
- Calculate ATR for recent window (last 5 candles)
- Calculate ATR for earlier window (5-10 candles ago)
- Check if recent ATR < earlier ATR * threshold (e.g., 0.8 = 20% decay)

**Step 3.1.5: Configuration Parameters**
- `volatility_decay`: Boolean (true = require decay)
- `decay_threshold`: Percentage threshold (default: 0.8 = 20% decrease)
- `decay_window`: Number of candles to compare (default: 5)
- `session`: Required session (e.g., "NY_close")

**Step 3.1.6: Integration Points**
- **CRITICAL**: `_calculate_atr()` is a **LOCAL function** inside `_check_conditions()` (line 5737)
- Reuse `SessionHelpers.get_current_session()` static method (import from `infra.session_helpers`)
- Reuse `_get_recent_candles()` local function (line 3230)
- **Placement**: Add in existing session-based conditions section (around line 5647, after "Check session-based conditions" comment)
- **Performance**: Check session FIRST, then do ATR calculations only if session matches
- **Note**: There's already a session conditions section starting at line 5647 - add new conditions there

**Step 3.1.7: Add to has_conditions Check**
- **File**: `auto_execution_system.py`
- **Location**: Line 6161 (in `has_conditions` list)
- **Action**: Add `"volatility_decay" in plan.conditions` to the list

**Step 3.1.8: Testing Requirements**
- **See "Testing Strategy" section for detailed unit and integration test specifications**
- Functional test cases:
  - Test with ATR decreasing 25% (above threshold)
  - Test with ATR decreasing 10% (below threshold, should fail)
  - Test with ATR increasing (should fail)
  - Test session validation
  - Test with different time windows
- **Unit Tests**: See `TestVolatilityDecayCondition` in `test_missing_conditions_phase3_session.py`
- **Integration Tests**: See Phase 3 integration tests

**Files to Modify**:
- `auto_execution_system.py` (add condition check)

**Estimated Effort**: 1 day

---

### 3.2 `momentum_follow` - Consistent Price Momentum

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: Medium-High  
**Dependencies**: Momentum calculation, may need technical indicators  
**Estimated Time**: 1.5 days

#### Implementation Steps

**Step 3.2.1: Calculate Momentum**
```python
# Option 1: Simple momentum (price change over periods)
# - Calculate price change over last 5-10 candles
# - Check if changes are consistent (same direction)
# - Check if magnitude is significant

# Option 2: Technical indicators (RSI, MACD)
# - Calculate RSI (if available)
# - Check if RSI > 50 for bullish, < 50 for bearish
# - Check if RSI is trending (increasing/decreasing)
```

**Step 3.2.2: Momentum Consistency Check**
- Calculate momentum for each recent period (e.g., last 5 candles)
- Check if all momentum values are in same direction
- Check if momentum magnitude is increasing (strengthening)

**Step 3.2.3: Session Context**
- **Requirement**: Must be in appropriate session (e.g., NY for momentum)
- **Integration**: Use `SessionHelpers.get_current_session()` static method
- **CRITICAL**: Check session FIRST before doing momentum calculations (performance optimization)
- **Import**: `from infra.session_helpers import SessionHelpers`

**Step 3.2.4: Configuration Parameters**
- `momentum_follow`: Boolean (true = require momentum)
- `momentum_periods`: Number of periods to check (default: 5)
- `momentum_threshold`: Minimum momentum magnitude (default: 0.5%)
- `session`: Required session (e.g., "NY")

**Step 3.2.5: Integration Points**
- **CRITICAL**: `_get_recent_candles()` is a **LOCAL function** inside `_check_conditions()` (line 3230)
- Reuse candle fetching logic
- **Recommendation**: Start with simple momentum (price change over periods) - no RSI/MACD needed initially
- Reuse `SessionHelpers.get_current_session()` static method
- **Placement**: Add in session-specific conditions section (after `volatility_decay`)

**Step 3.2.6: Add to has_conditions Check**
- **File**: `auto_execution_system.py`
- **Location**: Line 6161 (in `has_conditions` list)
- **Action**: Add `"momentum_follow" in plan.conditions` to the list

**Step 3.2.7: Testing Requirements**
- **See "Testing Strategy" section for detailed unit and integration test specifications**
- Functional test cases:
  - Test with strong consistent momentum
  - Test with weak/inconsistent momentum (should fail)
  - Test with momentum in wrong direction (should fail)
  - Test session validation
- **Unit Tests**: See `TestMomentumFollowCondition` in `test_missing_conditions_phase3_session.py`
- **Integration Tests**: See Phase 3 integration tests

**Files to Modify**:
- `auto_execution_system.py` (add condition check)
- May need to add momentum calculation helper

**Estimated Effort**: 1.5 days

---

### 3.3 `fakeout_sweep` - False Breakout Then Reversal

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: High  
**Dependencies**: Level identification, pattern recognition (similar to liquidity sweep)  
**Estimated Time**: 1.5 days

#### Implementation Steps

**Step 3.3.1: Identify Key Levels**
```python
# 1. Identify key levels (recent swing highs/lows, support/resistance)
# 2. Detect if price broke above/below level recently (within last N candles)
# 3. Check if price quickly reversed (moved back through level)
# 4. Verify rejection pattern (long wick, rejection candle)
```

**Step 3.3.2: Breakout Detection**
- Similar to existing liquidity sweep logic
- Detect price breaking above/below key level
- Store break level and direction

**Step 3.3.3: Reversal Detection**
- Check if price moved back through level (opposite direction)
- Verify rejection pattern (long wick, closes away from level)
- Check if reversal happened quickly (within 2-5 candles)

**Step 3.3.4: Session Context**
- **Requirement**: Must be in appropriate session (e.g., London for fakeout)
- **Integration**: Use `SessionHelpers.get_current_session()` static method
- **CRITICAL**: Check session FIRST before doing expensive level identification (performance optimization)
- **Import**: `from infra.session_helpers import SessionHelpers`

**Step 3.3.5: Configuration Parameters**
- `fakeout_sweep`: Boolean (true = require fakeout)
- `fakeout_level`: Optional - specific level to check
- `fakeout_reversal_candles`: Max candles for reversal (default: 5)
- `session`: Required session (e.g., "London")

**Step 3.3.6: Integration Points**
- **CRITICAL**: `_get_recent_candles()` is a **LOCAL function** inside `_check_conditions()` (line 3230)
- Reuse liquidity sweep detection logic - check if `liquidity_sweep` condition logic exists (around line 3000+)
- Reuse level identification - may need simple swing point detection (max/min of recent candles)
- Reuse `SessionHelpers.get_current_session()` static method
- May need to add rejection pattern detection (long wick, closes away from level)
- **Placement**: Add in session-specific conditions section (after `momentum_follow`)

**Step 3.3.7: Add to has_conditions Check**
- **File**: `auto_execution_system.py`
- **Location**: Line 6161 (in `has_conditions` list)
- **Action**: Add `"fakeout_sweep" in plan.conditions` to the list

**Step 3.3.8: Testing Requirements**
- **See "Testing Strategy" section for detailed unit and integration test specifications**
- Functional test cases:
  - Test with clear fakeout (break → quick reversal)
  - Test with sustained breakout (should fail)
  - Test with slow reversal (should fail)
  - Test rejection pattern validation
  - Test session validation
- **Unit Tests**: See `TestFakeoutSweepCondition` in `test_missing_conditions_phase3_session.py`
- **Integration Tests**: See Phase 3 integration tests

**Files to Modify**:
- `auto_execution_system.py` (add condition check)
- May need to add level identification helper

**Estimated Effort**: 1.5 days

---

### 3.4 `flat_vol_hours` - Low Stable Volatility for N Hours

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: Medium  
**Dependencies**: Existing ATR calculation, extended period data  
**Estimated Time**: 1 day

#### Implementation Steps

**Step 3.4.1: Fetch Extended Period Data**
```python
# 1. Fetch candles for extended period (multiple hours)
# 2. Calculate ATR for each hour over lookback period (e.g., last 5 hours)
# 3. Check if ATR values are consistently low (below threshold)
# 4. Verify ATR is stable (low variance between hours)
# 5. Count consecutive hours with flat volatility
# 6. Check if count >= flat_vol_hours threshold (e.g., 3 hours)
```

**Step 3.4.2: Hourly ATR Calculation**
- Fetch H1 candles (or aggregate M15 candles into hours)
- Calculate ATR for each hour
- Store ATR values in array

**Step 3.4.3: Stability Check**
- Check if all ATR values are below threshold (low volatility)
- Check if ATR variance is low (stable, not fluctuating)
- Count consecutive hours meeting criteria

**Step 3.4.4: Configuration Parameters**
- `flat_vol_hours`: Number of hours required (default: 3)
- `flat_vol_threshold`: ATR threshold (default: 1.0x average ATR)
- `flat_vol_stability`: Max variance allowed (default: 0.2)

**Step 3.4.5: Integration Points**
- **CRITICAL**: `_calculate_atr()` is a **LOCAL function** inside `_check_conditions()` (line 5737)
- **CRITICAL**: `_get_recent_candles()` supports H1 timeframe (line 3236) - use `timeframe="H1"`
- Need to fetch H1 candles (or aggregate M15 candles into hours)
- May need extended candle fetching (more than usual - e.g., 10-20 H1 candles for 10-20 hours)
- **Placement**: Add in session-specific conditions section (after `fakeout_sweep`)

**Step 3.4.6: Add to has_conditions Check**
- **File**: `auto_execution_system.py`
- **Location**: Line 6161 (in `has_conditions` list)
- **Action**: Add `"flat_vol_hours" in plan.conditions` to the list

**Step 3.4.7: Testing Requirements**
- **See "Testing Strategy" section for detailed unit and integration test specifications**
- Functional test cases:
  - Test with 4 hours of flat volatility (above threshold)
  - Test with 2 hours of flat volatility (below threshold, should fail)
  - Test with volatile periods (should fail)
  - Test with unstable volatility (should fail)
- **Unit Tests**: See `TestFlatVolHoursCondition` in `test_missing_conditions_phase3_session.py`
- **Integration Tests**: See Phase 3 integration tests

**Files to Modify**:
- `auto_execution_system.py` (add condition check)

**Estimated Effort**: 1 day

---

## Phase 4: Pattern Conditions (High Complexity)

**Priority**: **LOW**  
**Effort**: 3-4 days  
**Impact**: 2 plans will execute

### 4.1 `pattern_evening_morning_star` - Three-Candle Reversal Pattern

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: Medium-High  
**Dependencies**: Candle pattern recognition  
**Estimated Time**: 2 days

#### Implementation Steps

**Step 4.1.1: Add Condition Check Location**
- **File**: `auto_execution_system.py`
- **Location**: After session conditions section (after line 5700+, where session conditions end)
- **Action**: Add new condition check block for pattern recognition
- **Note**: Add before confluence check (line 6155+)

**Step 4.1.2: Pattern Recognition Logic**
```python
# Evening Star (Bearish):
# - First candle: Bullish (green/up) - close > open
# - Second candle: Small body, gaps up (star) - small body, gap from first
# - Third candle: Bearish (red/down) - close < open, closes below first candle's midpoint

# Morning Star (Bullish):
# - First candle: Bearish (red/down) - close < open
# - Second candle: Small body, gaps down (star) - small body, gap from first
# - Third candle: Bullish (green/up) - close > open, closes above first candle's midpoint
```

**Step 4.1.3: Candle Analysis**
- Fetch last 3 candles
- Analyze body size (open vs close)
- Analyze gaps (between candles)
- Analyze wicks (high/low vs body)

**Step 4.1.4: Pattern Validation**
- Check body colors (bullish/bearish)
- Check gap between first and second candle
- Check second candle body size (should be small)
- Check third candle closes beyond first candle's midpoint

**Step 4.1.5: Configuration Parameters**
- `pattern_evening_morning_star`: Boolean (true = require pattern)
- `star_body_ratio`: Max body size for star candle (default: 0.3 = 30% of range)
- `gap_threshold`: Min gap size (default: 0.5% of price)

**Step 4.1.6: Integration Points**
- **CRITICAL**: `_get_recent_candles()` is a **LOCAL function** inside `_check_conditions()` (line 3230)
- Reuse candle fetching logic
- May need to add candle pattern recognition helper (or implement inline)
- Similar to existing `pattern_double_bottom` logic - check if it exists in codebase
- **Placement**: Add in pattern recognition section (after existing pattern checks, if any)

**Step 4.1.7: Add to has_conditions Check**
- **File**: `auto_execution_system.py`
- **Location**: Line 6161 (in `has_conditions` list)
- **Action**: Add `"pattern_evening_morning_star" in plan.conditions` to the list

**Step 4.1.8: Testing Requirements**
- **See "Testing Strategy" section for detailed unit and integration test specifications**
- Functional test cases:
  - Test with valid evening star pattern
  - Test with valid morning star pattern
  - Test with invalid patterns (should fail)
  - Test with different body sizes
  - Test gap detection
- **Unit Tests**: See `TestEveningMorningStarCondition` in `test_missing_conditions_phase4_pattern.py`
- **Integration Tests**: See Phase 4 integration tests

**Files to Modify**:
- `auto_execution_system.py` (add condition check)
- May need to add pattern recognition helper

**Estimated Effort**: 2 days

---

### 4.2 `pattern_three_drive` - Harmonic Pattern

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: High  
**Dependencies**: Swing point detection, Fibonacci calculations  
**Estimated Time**: 2 days

#### Implementation Steps

**Step 4.2.1: Swing Point Detection**
```python
# 1. Identify swing points (highs for bearish, lows for bullish)
# 2. Find three drives to similar level:
#    - Drive 1: First touch of level
#    - Drive 2: Second touch (retracement then return)
#    - Drive 3: Third touch (retracement then return)
# 3. Verify drives are approximately equal (Fibonacci ratios: 1.0, 1.272, 1.414)
# 4. Check if third drive is completing (price at level)
```

**Step 4.2.2: Swing Point Identification**
- Scan price history for local highs/lows
- Use swing point detection algorithm (e.g., look for price > previous N candles and next N candles)
- Store swing points with timestamps

**Step 4.2.3: Drive Detection**
- Find three drives to similar level (within tolerance)
- Calculate drive lengths
- Verify Fibonacci ratios (1.0, 1.272, 1.414)

**Step 4.2.4: Fibonacci Calculations**
- Calculate Fibonacci retracement levels
- Verify drive ratios match Fibonacci levels
- Check if third drive is at completion point

**Step 4.2.5: Configuration Parameters**
- `pattern_three_drive`: Boolean (true = require pattern)
- `drive_tolerance`: Level tolerance for drives (default: 1% of price)
- `fibonacci_tolerance`: Ratio tolerance (default: 0.1)

**Step 4.2.6: Integration Points**
- **CRITICAL**: `_get_recent_candles()` is a **LOCAL function** inside `_check_conditions()` (line 3230)
- Need extended price history (50-100 candles) - fetch with `count=100`
- Need swing point detection (may need to implement - can use simple algorithm: local max/min with window)
- Need Fibonacci calculations (may need to implement - simple ratios: 1.0, 1.272, 1.414, 1.618)
- **Placement**: Add in pattern recognition section (after `pattern_evening_morning_star`, before confluence check)

**Step 4.2.7: Add to has_conditions Check**
- **File**: `auto_execution_system.py`
- **Location**: Line 6161 (in `has_conditions` list)
- **Action**: Add `"pattern_three_drive" in plan.conditions` to the list

**Step 4.2.8: Testing Requirements**
- **See "Testing Strategy" section for detailed unit and integration test specifications**
- Functional test cases:
  - Test with valid three-drive pattern
  - Test with invalid patterns (should fail)
  - Test Fibonacci ratio validation
  - Test swing point detection
  - Test with different timeframes
- **Unit Tests**: See `TestThreeDriveCondition` in `test_missing_conditions_phase4_pattern.py`
- **Integration Tests**: See Phase 4 integration tests

**Files to Modify**:
- `auto_execution_system.py` (add condition check)
- May need to add swing point detection helper
- May need to add Fibonacci calculation helper

**Estimated Effort**: 2 days

---

## Phase 5: Additional Correlation Conditions

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Priority**: **MEDIUM**  
**Effort**: 1-2 days  
**Impact**: 2 plans will execute

### 5.1 `correlation_asset: SPX` - SPX Asset Specification

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: Low  
**Dependencies**: SPX percentage change (Phase 2.1)  
**Estimated Time**: 0.5 days

#### Implementation Steps

**Step 5.1.1: Add Asset Validation**
- **File**: `auto_execution_system.py`
- **Location**: In correlation condition checks
- **Action**: Validate `correlation_asset` parameter

**Step 5.1.2: Asset Routing Logic**
```python
# When correlation_asset = "SPX" or "SP500":
# - Route to SPX percentage change check (Phase 2.1)
# - Use spx_up_pct condition

# When correlation_asset = "US10Y" or "TNX":
# - Route to US10Y yield change check (Phase 2.2)
# - Use yield_drop condition

# When correlation_asset = "DXY":
# - Route to DXY correlation check (existing or Phase 2.3)
# - Use correlation_divergence or dxy_change_pct condition
```

**Step 5.1.3: Integration**
- This is mostly routing logic
- Depends on Phase 2.1 and 2.2 implementations
- Validates asset type and routes to appropriate check

**Files to Modify**:
- `auto_execution_system.py` (add asset routing)

**Estimated Effort**: 0.5 days

---

### 5.2 `correlation_asset: US10Y` - US10Y Asset Specification

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Complexity**: Low  
**Dependencies**: US10Y yield change (Phase 2.2)  
**Estimated Time**: 0.5 days

#### Implementation Steps

**Step 5.2.1: Add Asset Validation**
- Similar to SPX asset validation
- Route to US10Y yield change check

**Files to Modify**:
- `auto_execution_system.py` (add asset routing)

**Estimated Effort**: 0.5 days

---

## Integration Tests

**Status**: ✅ **COMPLETE** (2026-01-07)  
**Test File**: `tests/test_missing_conditions_integration.py`  
**Total Tests**: 12 integration tests (all passing)

### Test Coverage

**Integration Test Scenarios:**
1. ✅ **Quantitative Conditions Combined** - Testing bb_retest + zscore + atr_stretch together
2. ✅ **Correlation Conditions with Asset Validation** - Testing SPX correlation with proper asset routing
3. ✅ **Correlation Conditions Missing Asset** - Testing validation fails without correlation_asset
4. ✅ **Session Conditions with Session Validation** - Testing volatility_decay with proper session check
5. ✅ **Session Conditions Wrong Session** - Testing condition fails with wrong session
6. ✅ **Session Conditions Combined** - Testing volatility_decay + momentum_follow together
7. ✅ **Pattern Conditions Combined** - Testing pattern_evening_morning_star + pattern_three_drive together
8. ✅ **Mixed Conditions Realistic Scenario** - Testing conditions from multiple phases together
9. ✅ **Correlation Caching Behavior** - Testing that correlation data is cached across checks
10. ✅ **Graceful Degradation** - Testing system handles missing correlation_calculator gracefully
11. ✅ **Session Check Performance** - Testing session is checked FIRST (performance optimization)
12. ✅ **All Condition Types Stress Test** - Testing plan with all condition types together

**Test Results**: 12/12 passing ✅

---

## Critical Implementation Notes

### ⚠️ **IMPORTANT: Function Scope Issues**

**Local Functions in `_check_conditions()`**:
- `_get_recent_candles()` - **LOCAL function** (line 3230), NOT instance method
- `_normalize_candles()` - **LOCAL function** (line 3188), NOT instance method  
- `_calculate_atr()` - **LOCAL function** (line 5737), NOT instance method
- These are accessible within `_check_conditions()` method scope only
- **DO NOT** try to call as `self._get_recent_candles()` - call directly as `_get_recent_candles()`

**Instance Methods**:
- `self._get_cached_correlation()` - Instance method (line 7356)
- `self._cache_correlation()` - Instance method (line 7377)
- Use `self.` prefix for these

**Static Methods**:
- `SessionHelpers.get_current_session()` - Static method (import from `infra.session_helpers`)
- Use class name prefix, no instance needed

### ⚠️ **IMPORTANT: Condition Check Order**

1. **Early Checks** (lines 2826-2925): MT5 connection, symbol validation
2. **Price Conditions** (lines 1253-1262): Check price_near, price_above, price_below FIRST
3. **Structure Conditions** (lines 3600+): CHOCH, BOS, multi-timeframe
4. **Volatility Conditions** (lines 5159+): BB expansion, BB squeeze, inside bar
5. **Correlation Conditions** (lines 4232+): DXY, SPX, US10Y - **MUST be inside `if self.correlation_calculator:` block**
6. **Session Conditions**: Add new section after correlation
7. **Pattern Conditions**: Add after session conditions
8. **Confluence Check** (lines 6155+): Final validation

### ⚠️ **IMPORTANT: has_conditions Check**

**Location**: Line 6161 in `auto_execution_system.py`

**Action Required**: Add ALL new conditions to this list:
```python
has_conditions = any([
    # ... existing conditions ...
    "bb_retest" in plan.conditions,
    "zscore" in plan.conditions,
    "atr_stretch" in plan.conditions,
    "atr_multiple" in plan.conditions,
    "spx_up_pct" in plan.conditions,
    "yield_drop" in plan.conditions,
    "correlation_divergence" in plan.conditions,
    "volatility_decay" in plan.conditions,
    "momentum_follow" in plan.conditions,
    "fakeout_sweep" in plan.conditions,
    "flat_vol_hours" in plan.conditions,
    "pattern_evening_morning_star" in plan.conditions,
    "pattern_three_drive" in plan.conditions,
    # ... rest of existing conditions ...
])
```

**Purpose**: Ensures plans with these conditions are recognized as having conditions (prevents "no conditions" warning)

### ⚠️ **IMPORTANT: Error Handling Pattern**

**Standard Pattern**:
```python
if plan.conditions.get("condition_name"):
    try:
        # Check condition logic
        if condition_not_met:
            logger.debug(f"Plan {plan.plan_id}: Condition not met - reason")
            return False  # Fail-fast
        
        logger.info(f"Plan {plan.plan_id}: Condition met")
        # Continue to next condition
    except Exception as e:
        logger.error(f"Error checking condition for {plan.plan_id}: {e}", exc_info=True)
        return False  # Fail-closed on error
```

**Key Points**:
- Always wrap in try/except
- Use `logger.debug()` for failures (not met)
- Use `logger.info()` for successes (condition met)
- Return `False` immediately if condition not met (fail-fast)
- Return `False` on exceptions (fail-closed)

### ⚠️ **IMPORTANT: Correlation Calculator Checks**

**CRITICAL**: All correlation conditions MUST check:
```python
if self.correlation_calculator:
    try:
        # Correlation condition checks here
    except Exception as e:
        logger.error(...)
        return False
```

**If `correlation_calculator` is None**: Condition check should return `False` (graceful degradation)

---

## Critical Implementation Notes

### ⚠️ **IMPORTANT: Function Scope Issues**

**Local Functions in `_check_conditions()`**:
- `_get_recent_candles()` - **LOCAL function** (line 3230), NOT instance method
- `_normalize_candles()` - **LOCAL function** (line 3188), NOT instance method  
- `_calculate_atr()` - **LOCAL function** (line 5737), NOT instance method
- These are accessible within `_check_conditions()` method scope only
- **DO NOT** try to call as `self._get_recent_candles()` - call directly as `_get_recent_candles()`

**Instance Methods**:
- `self._get_cached_correlation()` - Instance method (line 7356)
- `self._cache_correlation()` - Instance method (line 7377)
- Use `self.` prefix for these

**Static Methods**:
- `SessionHelpers.get_current_session()` - Static method (import from `infra.session_helpers`)
- Use class name prefix, no instance needed

### ⚠️ **IMPORTANT: Condition Check Order**

1. **Early Checks** (lines 2826-2925): MT5 connection, symbol validation
2. **Price Conditions** (lines 1253-1262): Check price_near, price_above, price_below FIRST
3. **Structure Conditions** (lines 3600+): CHOCH, BOS, multi-timeframe
4. **Volatility Conditions** (lines 5159+): BB expansion, BB squeeze, inside bar
5. **Correlation Conditions** (lines 4232+): DXY, SPX, US10Y - **MUST be inside `if self.correlation_calculator:` block**
6. **Session Conditions**: Add new section after correlation
7. **Pattern Conditions**: Add after session conditions
8. **Confluence Check** (lines 6155+): Final validation

### ⚠️ **IMPORTANT: has_conditions Check**

**Location**: Line 6161 in `auto_execution_system.py`

**Action Required**: Add ALL new conditions to this list:
```python
has_conditions = any([
    # ... existing conditions ...
    "bb_retest" in plan.conditions,
    "zscore" in plan.conditions,
    "atr_stretch" in plan.conditions,
    "atr_multiple" in plan.conditions,
    "spx_up_pct" in plan.conditions,
    "yield_drop" in plan.conditions,
    "correlation_divergence" in plan.conditions,
    "volatility_decay" in plan.conditions,
    "momentum_follow" in plan.conditions,
    "fakeout_sweep" in plan.conditions,
    "flat_vol_hours" in plan.conditions,
    "pattern_evening_morning_star" in plan.conditions,
    "pattern_three_drive" in plan.conditions,
    # ... rest of existing conditions ...
])
```

**Purpose**: Ensures plans with these conditions are recognized as having conditions (prevents "no conditions" warning)

### ⚠️ **IMPORTANT: Error Handling Pattern**

**Standard Pattern**:
```python
if plan.conditions.get("condition_name"):
    try:
        # Check condition logic
        if condition_not_met:
            logger.debug(f"Plan {plan.plan_id}: Condition not met - reason")
            return False  # Fail-fast
        
        logger.info(f"Plan {plan.plan_id}: Condition met")
        # Continue to next condition
    except Exception as e:
        logger.error(f"Error checking condition for {plan.plan_id}: {e}", exc_info=True)
        return False  # Fail-closed on error
```

**Key Points**:
- Always wrap in try/except
- Use `logger.debug()` for failures (not met)
- Use `logger.info()` for successes (condition met)
- Return `False` immediately if condition not met (fail-fast)
- Return `False` on exceptions (fail-closed)

### ⚠️ **IMPORTANT: Correlation Calculator Checks**

**CRITICAL**: All correlation conditions MUST check:
```python
if self.correlation_calculator:
    try:
        # Correlation condition checks here
    except Exception as e:
        logger.error(...)
        return False
```

**If `correlation_calculator` is None**: Condition check should return `False` (graceful degradation)

### ⚠️ **IMPORTANT: Session Check Performance**

**CRITICAL**: For session conditions, check session FIRST before expensive calculations:
```python
if plan.conditions.get("session"):
    from infra.session_helpers import SessionHelpers
    current_session = SessionHelpers.get_current_session()
    required_session = plan.conditions.get("session")
    
    # Check session FIRST (fast check)
    if current_session.upper() != required_session.upper():
        logger.debug(f"Plan {plan.plan_id}: Wrong session ({current_session} != {required_session})")
        return False  # Fail-fast, avoid expensive calculations
    
    # Only do expensive calculations if session matches
    # ... ATR calculations, momentum calculations, etc.
```

---

## Implementation Timeline

### Week 1: Quick Wins (Phase 1)
- **Day 1**: `bb_retest` implementation
- **Day 2**: `zscore` and `atr_stretch` implementation
- **Day 3**: Testing and refinement

### Week 2: Correlation (Phase 2 + Phase 5)
- **Day 4**: `spx_up_pct` implementation
- **Day 5**: `yield_drop` implementation
- **Day 6**: `correlation_divergence` implementation
- **Day 7**: Asset routing (Phase 5) and testing

### Week 3: Session Conditions (Phase 3)
- **Day 8**: `volatility_decay` implementation
- **Day 9**: `momentum_follow` implementation
- **Day 10**: `fakeout_sweep` implementation
- **Day 11**: `flat_vol_hours` implementation
- **Day 12**: Testing and refinement

### Week 4: Pattern Conditions (Phase 4)
- **Day 13-14**: `pattern_evening_morning_star` implementation
- **Day 15-16**: `pattern_three_drive` implementation
- **Day 17**: Final testing and documentation

---

## Testing Strategy

### Overview

Each condition implementation **MUST** include:
1. **Unit Tests**: Test condition logic in isolation with mocked data
2. **Integration Tests**: Test condition with real auto-execution system
3. **Edge Case Tests**: Test error handling, boundary conditions, and failure modes

### Test File Structure

**Location**: `tests/test_missing_conditions_*.py`

**Naming Convention**:
- `test_missing_conditions_phase1_quantitative.py` - Phase 1 tests
- `test_missing_conditions_phase2_correlation.py` - Phase 2 tests
- `test_missing_conditions_phase3_session.py` - Phase 3 tests
- `test_missing_conditions_phase4_pattern.py` - Phase 4 tests
- `test_missing_conditions_phase5_asset_routing.py` - Phase 5 tests
- `test_missing_conditions_integration.py` - Cross-phase integration tests

### Unit Test Requirements

**For Each Condition**:
1. **Test Structure**:
   ```python
   class TestBBRetestCondition(unittest.TestCase):
       def setUp(self):
           # Mock MT5 service
           # Mock candle data
           # Create test plan
       
       def test_condition_met_bullish_break_retest(self):
           # Test successful condition
       
       def test_condition_not_met_no_break(self):
           # Test failure case
       
       def test_condition_not_met_no_retest(self):
           # Test failure case
       
       def test_edge_case_insufficient_candles(self):
           # Test error handling
   ```

2. **Required Test Cases** (per condition):
   - ✅ Condition met (positive case)
   - ✅ Condition not met (negative case)
   - ✅ Insufficient data (error handling)
   - ✅ Invalid parameters (error handling)
   - ✅ Edge cases (boundary conditions)
   - ✅ Different timeframes (if applicable)
   - ✅ Different symbols (if applicable)

3. **Mock Requirements**:
   - Mock `MT5Service` (no real MT5 connection)
   - Mock candle data (synthetic price history)
   - Mock correlation calculator (for correlation conditions)
   - Mock session helpers (for session conditions)

### Integration Test Requirements

**For Each Phase**:
1. **Test Structure**:
   ```python
   class TestPhase1Integration(unittest.TestCase):
       def setUp(self):
           # Initialize auto-execution system
           # Create test database
           # Load test plans
       
       def test_bb_retest_with_real_plan(self):
           # Test condition with actual plan execution
       
       def test_multiple_conditions_together(self):
           # Test condition combinations
   ```

2. **Required Test Cases**:
   - ✅ Condition check in `_check_conditions()` method
   - ✅ Plan execution when condition met
   - ✅ Plan blocking when condition not met
   - ✅ Multiple conditions together
   - ✅ Condition with different symbols (BTC, XAU)
   - ✅ Condition with different timeframes
   - ✅ Caching behavior (for correlation conditions)
   - ✅ Error recovery (graceful degradation)

3. **Test Data Requirements**:
   - Realistic price history (synthetic or historical)
   - Multiple test plans with different configurations
   - Edge case scenarios (low volatility, high volatility, etc.)

### Phase-Specific Test Details

#### Phase 1: Quantitative Conditions

**Unit Tests** (`test_missing_conditions_phase1_quantitative.py`):
- `TestBBRetestCondition`: 8 test cases
  - Bullish break → retest → bounce
  - Bearish break → retest → bounce
  - Break without retest
  - Retest without bounce
  - Insufficient candles
  - Different timeframes (M5, M15, H1)
  - Different tolerance values
  - Edge case: price exactly at BB level

- `TestZScoreCondition`: 6 test cases
  - Z-score above threshold (BUY direction)
  - Z-score below threshold (SELL direction)
  - Z-score below threshold (should fail)
  - Different lookback periods
  - Different threshold values
  - Insufficient data

- `TestATRStretchCondition`: 7 test cases
  - Stretch above threshold
  - Stretch below threshold (should fail)
  - Different reference prices (entry, swing, VWAP)
  - Different ATR multiples
  - Insufficient candles
  - ATR calculation failure
  - Edge case: zero ATR

**Integration Tests**:
- Test all 3 conditions with real plans
- Test condition combinations
- Test with BTC and XAU symbols
- Test caching and performance

#### Phase 2: Correlation Conditions

**Unit Tests** (`test_missing_conditions_phase2_correlation.py`):
- `TestSPXChangeCondition`: 7 test cases
  - SPX up above threshold
  - SPX up below threshold (should fail)
  - Yahoo Finance unavailable
  - Caching behavior
  - Different time windows
  - Invalid correlation_asset value
  - Async event loop handling

- `TestUS10YYieldChangeCondition`: 7 test cases
  - Yield drop above threshold
  - Yield drop below threshold (should fail)
  - Yield increase (should fail for "drop")
  - Yahoo Finance unavailable
  - Caching behavior
  - Different time windows
  - Async event loop handling

- `TestCorrelationDivergenceCondition`: 8 test cases
  - Strong divergence (correlation = -0.7)
  - Weak divergence (correlation = -0.3, should fail)
  - Positive correlation (should fail)
  - DXY down + symbol up (bullish)
  - DXY up + symbol down (bearish)
  - Correlation calculator unavailable
  - Different time windows
  - Async event loop handling

**Integration Tests**:
- Test with real correlation calculator
- Test caching across multiple plans
- Test graceful degradation when calculator unavailable
- Test async event loop handling

#### Phase 3: Session Conditions

**Unit Tests** (`test_missing_conditions_phase3_session.py`):
- `TestVolatilityDecayCondition`: 7 test cases
  - ATR decreasing 25% (above threshold)
  - ATR decreasing 10% (below threshold)
  - ATR increasing (should fail)
  - Wrong session (should fail)
  - Insufficient candles
  - Session helper unavailable
  - Different decay thresholds

- `TestMomentumFollowCondition`: 6 test cases
  - Strong consistent momentum
  - Weak/inconsistent momentum (should fail)
  - Momentum in wrong direction (should fail)
  - Wrong session (should fail)
  - Insufficient data
  - Different momentum periods

- `TestFakeoutSweepCondition`: 7 test cases
  - Clear fakeout (break → quick reversal)
  - Sustained breakout (should fail)
  - Slow reversal (should fail)
  - Wrong session (should fail)
  - No key level identified
  - Rejection pattern not detected
  - Insufficient candles

- `TestFlatVolHoursCondition`: 6 test cases
  - 4 hours of flat volatility (above threshold)
  - 2 hours of flat volatility (below threshold)
  - Volatile periods (should fail)
  - Unstable volatility (should fail)
  - Insufficient H1 candles
  - ATR calculation failure

**Integration Tests**:
- Test session validation before expensive calculations
- Test with different sessions (Asian, London, NY)
- Test session helper integration
- Test performance (session check first)

#### Phase 4: Pattern Conditions

**Unit Tests** (`test_missing_conditions_phase4_pattern.py`):
- `TestEveningMorningStarCondition`: 7 test cases
  - Valid evening star pattern
  - Valid morning star pattern
  - Invalid patterns (should fail)
  - Different body sizes
  - Gap detection
  - Insufficient candles (< 3)
  - Edge case: no gap

- `TestThreeDriveCondition`: 8 test cases
  - Valid three-drive pattern
  - Invalid patterns (should fail)
  - Fibonacci ratio validation
  - Swing point detection
  - Different timeframes
  - Insufficient candles (< 100)
  - Drive tolerance validation
  - Edge case: drives not equal

**Integration Tests**:
- Test pattern recognition accuracy
- Test with extended price history
- Test swing point detection
- Test Fibonacci calculations

#### Phase 5: Asset Routing

**Unit Tests** (`test_missing_conditions_phase5_asset_routing.py`):
- `TestSPXAssetRouting`: 4 test cases
  - Routes to SPX percentage change check
  - Validates SPX/SP500 asset names
  - Invalid asset name (should fail)
  - Missing spx_up_pct condition (should fail)

- `TestUS10YAssetRouting`: 4 test cases
  - Routes to US10Y yield change check
  - Validates US10Y/TNX asset names
  - Invalid asset name (should fail)
  - Missing yield_drop condition (should fail)

**Integration Tests**:
- Test asset routing with real plans
- Test routing with multiple correlation conditions
- Test error handling for invalid assets

### Cross-Phase Integration Tests

**File**: `test_missing_conditions_integration.py`

**Test Cases**:
1. **Multiple Conditions Together**:
   - Test plans with 2+ new conditions
   - Test condition dependencies
   - Test condition order of evaluation

2. **Real Plan Execution**:
   - Create test plans with new conditions
   - Verify plans execute when conditions met
   - Verify plans don't execute when conditions not met
   - Monitor execution logs

3. **Performance Tests**:
   - Test condition check performance
   - Test caching effectiveness
   - Test with 50+ plans simultaneously

4. **Error Recovery**:
   - Test graceful degradation
   - Test error handling
   - Test system stability

### Test Execution

**Run All Tests**:
```bash
# Unit tests
python -m pytest tests/test_missing_conditions_phase1_quantitative.py -v
python -m pytest tests/test_missing_conditions_phase2_correlation.py -v
python -m pytest tests/test_missing_conditions_phase3_session.py -v
python -m pytest tests/test_missing_conditions_phase4_pattern.py -v
python -m pytest tests/test_missing_conditions_phase5_asset_routing.py -v

# Integration tests
python -m pytest tests/test_missing_conditions_integration.py -v

# All tests
python -m pytest tests/test_missing_conditions_*.py -v
```

**Test Coverage Goal**: Minimum 80% code coverage for each condition implementation

### Validation Tests

**Manual Validation**:
- Verify plans execute when conditions are met
- Verify plans don't execute when conditions aren't met
- Monitor execution logs for correctness
- Check UI display of conditions
- Verify database storage of conditions

---

## Documentation Updates

### Required Updates
1. **ChatGPT Knowledge Docs**: Remove unsupported conditions, add new conditions
2. **openai.yaml**: Update tool descriptions with new conditions
3. **Implementation Guide**: Document each condition's usage
4. **Testing Guide**: Add test cases for new conditions

---

## Risk Mitigation

### Technical Risks
- **Data Availability**: External data sources (Yahoo Finance) may be unavailable
  - **Mitigation**: Add fallback values, error handling, graceful degradation

- **Performance**: Additional condition checks may slow down execution
  - **Mitigation**: Use caching, optimize calculations, batch operations

- **Complexity**: Pattern recognition may have false positives
  - **Mitigation**: Strict validation, multiple confirmation signals

### Implementation Risks
- **Scope Creep**: Conditions may require more work than estimated
  - **Mitigation**: Start with simpler implementations, iterate

- **Dependencies**: May discover missing dependencies during implementation
  - **Mitigation**: Review dependencies before starting each phase

---

## Success Criteria

### Phase 1 Success
- ✅ All 3 quantitative conditions implemented and tested
- ✅ 5 plans can execute with these conditions

### Phase 2 Success
- ✅ All 3 correlation conditions implemented and tested
- ✅ 4 plans can execute with these conditions

### Phase 3 Success
- ✅ All 4 session conditions implemented and tested
- ✅ 4 plans can execute with these conditions

### Phase 4 Success
- ✅ All 2 pattern conditions implemented and tested
- ✅ 2 plans can execute with these conditions

### Overall Success
- ✅ All 15 conditions implemented
- ✅ All 12 previously non-executing plans can now execute
- ✅ No regression in existing functionality
- ✅ Documentation updated

---

## Next Steps

1. **Review and Approve Plan**: Review this plan and prioritize phases
2. **Set Up Development Environment**: Ensure all dependencies are available
3. **Start Phase 1**: Begin with `bb_retest` implementation
4. **Iterate and Test**: Implement, test, refine for each condition
5. **Monitor Progress**: Track implementation against timeline

---

---

## Review Summary: Issues Fixed

### ✅ **Logic Issues Fixed**
1. **Function Scope**: Clarified that helper functions are LOCAL, not instance methods
2. **Condition Order**: Documented proper placement in `_check_conditions()` flow
3. **Error Handling**: Standardized try/except pattern with fail-fast/fail-closed logic
4. **has_conditions Check**: Added requirement to update line 6161 for all new conditions

### ✅ **Integration Issues Fixed**
1. **Correlation Calculator**: Added requirement to check `if self.correlation_calculator:` exists
2. **Session Helpers**: Clarified static method usage (`SessionHelpers.get_current_session()`)
3. **Caching Methods**: Clarified instance method usage (`self._get_cached_correlation()`)
4. **Async Pattern**: Documented async event loop pattern for correlation checks
5. **Performance**: Added session check FIRST before expensive calculations

### ✅ **Implementation Issues Fixed**
1. **Function Names**: Corrected references to local vs instance methods
2. **Placement**: Specified exact locations in `_check_conditions()` method
3. **Dependencies**: Clarified what needs to be imported vs what's already available
4. **Missing Steps**: Added "Add to has_conditions Check" step for all conditions
5. **Error Patterns**: Standardized error handling approach

---

---

## Review Summary: Issues Fixed

### ✅ **Logic Issues Fixed**
1. **Function Scope**: Clarified that helper functions (`_get_recent_candles`, `_normalize_candles`, `_calculate_atr`) are LOCAL functions inside `_check_conditions()`, NOT instance methods
2. **Condition Order**: Documented proper placement in `_check_conditions()` flow (price → structure → volatility → correlation → session → pattern → confluence)
3. **Error Handling**: Standardized try/except pattern with fail-fast/fail-closed logic
4. **has_conditions Check**: Added requirement to update line 6161 for all 15 new conditions

### ✅ **Integration Issues Fixed**
1. **Correlation Calculator**: Added requirement to check `if self.correlation_calculator:` exists before correlation checks (line 4236)
2. **Session Helpers**: Clarified static method usage (`SessionHelpers.get_current_session()` - import from `infra.session_helpers`)
3. **Caching Methods**: Clarified instance method usage (`self._get_cached_correlation()`, `self._cache_correlation()`)
4. **Async Pattern**: Documented async event loop pattern for correlation checks (use `asyncio.get_event_loop()` or `asyncio.new_event_loop()`)
5. **Performance**: Added requirement to check session FIRST before expensive calculations (fail-fast optimization)

### ✅ **Implementation Issues Fixed**
1. **Function Names**: Corrected all references - local functions vs instance methods vs static methods
2. **Placement**: Specified exact locations in `_check_conditions()` method for each condition
3. **Dependencies**: Clarified what needs to be imported (`from infra.session_helpers import SessionHelpers`) vs what's already available
4. **Missing Steps**: Added "Add to has_conditions Check" step (Step X.X.7 or X.X.8) for all 15 conditions
5. **Error Patterns**: Standardized error handling approach (try/except, logger.debug for failures, logger.info for successes, return False on failure)

### ✅ **Additional Fixes (Second Pass)**
1. **Line Numbers**: Fixed incorrect line number references:
   - Price conditions: Corrected from 1253-1262 to 3406-3527 (price_above: 3407, price_below: 3411, price_near: 3512)
   - Session conditions: Corrected placement to line 5647 (existing "Check session-based conditions" section)
   - Statistical conditions: Corrected placement to before line 5238 ("Phase III: Volatility Pattern Recognition")
2. **Condition Order**: Updated to include Order Flow section (line 4384+) between correlation and session
3. **Placement Details**: Added specific placement notes for each condition type:
   - Statistical conditions: Before "Phase III: Volatility Pattern Recognition" (line 5238)
   - Session conditions: In existing session section (line 5647)
   - Pattern conditions: After session conditions, before confluence check (line 6155+)
4. **BB Retest**: Added detailed price history tracking implementation (from BB_RETEST guide)
5. **ATR Stretch**: Clarified which ATR function to use (`_calculate_atr` at line 5737, not `_calculate_atr_simple`)
6. **Correlation Conditions**: Added requirement for async event loop handling
7. **Session Conditions**: Added performance optimization (check session first) and correct placement reference

---

**Document Version**: 2.3  
**Last Updated**: 2026-01-07  
**Status**: ✅ Testing Specifications Added - Ready for Implementation

