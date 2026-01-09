# Missing Conditions Implementation Requirements

**Date**: 2026-01-07  
**Purpose**: Explain what would be required to implement the 12 unsupported conditions

---

## Overview

To make the 12 currently non-executing plans work, you would need to implement **15 missing conditions** across 4 categories:

1. **Quantitative Conditions** (3 conditions)
2. **Correlation Conditions** (5 conditions)  
3. **Session Conditions** (4 conditions)
4. **Pattern Conditions** (2 conditions)

---

## 1. Quantitative Conditions (3 conditions)

### 1.1 `bb_retest` (Bollinger Band Retest)

**What It Means**: Price touches or retests a Bollinger Band (upper or lower) after initially breaking away, then bounces back.

**Required Implementation**:
- **Data Needed**: 
  - Recent candles (20-50 bars) on specified timeframe
  - Bollinger Band calculations (upper, middle, lower bands)
  - Price history to detect initial break and retest
  
- **Logic Required**:
  1. Calculate BB upper/lower bands (SMA ± 2 standard deviations)
  2. Detect if price previously broke above/below BB (within last N candles)
  3. Check if price is now retesting that same BB level (within tolerance)
  4. Verify bounce/rejection (price moves away from BB after retest)
  
- **Where to Add**: 
  - In `auto_execution_system.py::_check_conditions()` 
  - After existing `bb_expansion` check (around line 5160)
  - Can reuse existing BB calculation logic from `bb_expansion`
  
- **Complexity**: **MEDIUM**
  - Similar to existing `bb_expansion` logic
  - Requires price history tracking
  - Need to distinguish between "break" and "retest"

- **Dependencies**: 
  - Existing BB calculation (already exists)
  - Candle data fetching (already exists)
  - Price history tracking (may need to add)

---

### 1.2 `zscore` / `z_threshold` (Z-Score Statistical Mean Reversion)

**What It Means**: Price has deviated significantly from its mean (statistically), indicating potential mean reversion opportunity.

**Required Implementation**:
- **Data Needed**:
  - Recent price history (typically 20-50 periods)
  - Mean (average) price over lookback period
  - Standard deviation of prices
  
- **Logic Required**:
  1. Calculate mean price over lookback period (e.g., last 20 candles)
  2. Calculate standard deviation of prices
  3. Calculate Z-score: `(current_price - mean) / standard_deviation`
  4. Check if Z-score exceeds threshold (e.g., 2.0 = 2 standard deviations)
  5. For mean reversion: Z-score > threshold suggests price is "overextended" and may revert
  
- **Where to Add**:
  - In `auto_execution_system.py::_check_conditions()`
  - New section for statistical conditions
  - Can use existing candle fetching logic
  
- **Complexity**: **LOW-MEDIUM**
  - Straightforward statistical calculation
  - Similar to existing volatility calculations
  - No external dependencies
  
- **Dependencies**:
  - Candle data (already exists)
  - Basic statistical calculations (numpy/pandas or manual)

---

### 1.3 `atr_stretch` / `atr_multiple` (ATR Stretch Reversal)

**What It Means**: Price has moved more than X times the ATR (Average True Range) from a reference point, indicating potential reversal.

**Required Implementation**:
- **Data Needed**:
  - Recent candles for ATR calculation (14-20 periods)
  - Reference price (entry price, recent high/low, VWAP, etc.)
  - Current price
  
- **Logic Required**:
  1. Calculate ATR using existing ATR calculation (already exists in codebase)
  2. Determine reference price (from plan conditions or recent swing)
  3. Calculate distance from reference: `abs(current_price - reference_price)`
  4. Calculate stretch ratio: `distance / ATR`
  5. Check if stretch ratio >= `atr_multiple` (e.g., 2.5x ATR)
  6. For reversal: If stretched too far, expect reversal back toward mean
  
- **Where to Add**:
  - In `auto_execution_system.py::_check_conditions()`
  - Can reuse existing `_calculate_atr()` helper (line 5737)
  - Add after existing volatility conditions
  
- **Complexity**: **LOW**
  - ATR calculation already exists
  - Simple distance/ratio calculation
  - Straightforward logic
  
- **Dependencies**:
  - Existing ATR calculation (already exists)
  - Candle data (already exists)

---

## 2. Correlation Conditions (5 conditions)

### 2.1 `correlation_asset: SPX` / `spx_up_pct`

**What It Means**: Check if S&P 500 (SPX) is moving in a specific direction (up/down) by a certain percentage, indicating risk-on/risk-off sentiment that affects BTC.

**Required Implementation**:
- **Data Sources Needed**:
  - S&P 500 price data (Yahoo Finance: `^GSPC` or `SPY`)
  - Historical prices to calculate percentage change
  - Real-time or near-real-time updates (every 1-5 minutes)
  
- **Logic Required**:
  1. Fetch SPX current price and historical prices
  2. Calculate percentage change over specified window (e.g., last 15 minutes, 1 hour)
  3. Check if change >= `spx_up_pct` threshold (e.g., 0.5% = 0.5)
  4. For BTC: Positive SPX correlation means BTC should move in same direction
  
- **Where to Add**:
  - In `auto_execution_system.py::_check_conditions()` 
  - In Phase III correlation section (around line 4232)
  - Similar to existing `dxy_change_pct` logic (line 4239)
  
- **Complexity**: **MEDIUM**
  - Similar to existing DXY correlation logic
  - Need to add SPX data fetching
  - May need caching to avoid excessive API calls
  
- **Dependencies**:
  - External data source (Yahoo Finance via `yfinance` - already used in codebase)
  - `correlation_calculator` service (already exists, may need extension)
  - Caching mechanism (already exists for DXY)

**Note**: The `correlation_context_calculator.py` already has SP500 correlation calculation (line 153), but it's for correlation coefficient, not percentage change. Would need to add percentage change calculation.

---

### 2.2 `correlation_asset: US10Y` / `yield_drop`

**What It Means**: Check if US 10-Year Treasury yield is dropping, which typically indicates risk-on sentiment (good for BTC).

**Required Implementation**:
- **Data Sources Needed**:
  - US 10-Year Treasury yield data (Yahoo Finance: `^TNX`)
  - Historical yield data to calculate change
  - Real-time or near-real-time updates
  
- **Logic Required**:
  1. Fetch US10Y current yield and historical yields
  2. Calculate yield change over specified window
  3. Check if yield drop >= `yield_drop` threshold (e.g., 0.05 = 5 basis points)
  4. For BTC: Yield drop = risk-on = bullish for BTC
  
- **Where to Add**:
  - In `auto_execution_system.py::_check_conditions()`
  - In Phase III correlation section
  - Similar to SPX logic above
  
- **Complexity**: **MEDIUM**
  - Similar to SPX implementation
  - Same data source (Yahoo Finance)
  - Same caching requirements
  
- **Dependencies**:
  - External data source (Yahoo Finance - already used)
  - `correlation_calculator` service extension
  - Caching mechanism

**Note**: The codebase already fetches US10Y data in `desktop_agent.py` (line 6258), but it's for display purposes, not condition checking.

---

### 2.3 `correlation_asset: DXY` / `correlation_divergence`

**What It Means**: Check if DXY (Dollar Index) and the trading symbol are moving in opposite directions (divergence), which can indicate strength in the symbol independent of dollar weakness.

**Required Implementation**:
- **Data Sources Needed**:
  - DXY price data (already fetched)
  - Symbol price data (already available)
  - Historical prices for both to calculate correlation
  
- **Logic Required**:
  1. Fetch recent price movements for both DXY and symbol
  2. Calculate correlation coefficient over lookback window (e.g., last 60 minutes)
  3. Check if correlation is negative (moving in opposite directions)
  4. Verify divergence is significant (correlation < -0.5 or similar threshold)
  5. For BTC: DXY down + BTC up = bullish divergence
  
- **Where to Add**:
  - In `auto_execution_system.py::_check_conditions()`
  - In Phase III correlation section
  - Can use existing `correlation_calculator` for correlation coefficient
  
- **Complexity**: **MEDIUM-HIGH**
  - Requires correlation calculation (already exists)
  - Need to track both assets' movements
  - More complex than simple percentage change
  
- **Dependencies**:
  - `correlation_calculator` service (already exists)
  - DXY data fetching (already exists)
  - Symbol price data (already available)

**Note**: The `correlation_context_calculator.py` already calculates DXY correlation (line 147), but it's for correlation coefficient, not divergence detection. Would need to add divergence logic.

---

## 3. Session Conditions (4 conditions)

### 3.1 `volatility_decay`

**What It Means**: Volatility is decreasing as the session progresses (typically near session end), indicating potential reversal or range-bound behavior.

**Required Implementation**:
- **Data Needed**:
  - ATR values over recent periods (e.g., last 10-20 candles)
  - Session timing information
  - Current session and time within session
  
- **Logic Required**:
  1. Calculate ATR for recent periods (e.g., last 5 candles vs previous 5 candles)
  2. Compare recent ATR to earlier ATR in the session
  3. Check if ATR is decreasing (decay): `recent_ATR < earlier_ATR * decay_threshold`
  4. Verify we're in appropriate session (e.g., NY close)
  5. For reversal: Low volatility near session end suggests mean reversion
  
- **Where to Add**:
  - In `auto_execution_system.py::_check_conditions()`
  - New section for session-specific conditions
  - Can use existing ATR calculation and session helpers
  
- **Complexity**: **MEDIUM**
  - Requires ATR tracking over time
  - Session timing logic (already exists)
  - Trend detection (decreasing volatility)
  
- **Dependencies**:
  - Existing ATR calculation (already exists)
  - Session helpers (already exists: `infra/session_helpers.py`)
  - Candle data (already exists)

---

### 3.2 `momentum_follow`

**What It Means**: Price momentum is strong and continuing in the current direction, indicating trend continuation rather than reversal.

**Required Implementation**:
- **Data Needed**:
  - Recent price movements (returns or price changes)
  - Momentum indicators (RSI, MACD, or simple price change)
  - Session context
  
- **Logic Required**:
  1. Calculate momentum over recent periods (e.g., last 5-10 candles)
  2. Check if momentum is consistent (same direction over multiple periods)
  3. Verify momentum strength (magnitude of price changes)
  4. Check if we're in appropriate session (e.g., NY session for momentum)
  5. For continuation: Strong, consistent momentum suggests trend will continue
  
- **Where to Add**:
  - In `auto_execution_system.py::_check_conditions()`
  - Session conditions section
  - Can use existing momentum/trend detection logic if available
  
- **Complexity**: **MEDIUM-HIGH**
  - Requires momentum calculation
  - Trend consistency detection
  - May need technical indicators (RSI, MACD)
  
- **Dependencies**:
  - Candle data (already exists)
  - Momentum calculation (may need to implement)
  - Session helpers (already exists)

---

### 3.3 `fakeout_sweep`

**What It Means**: Price briefly breaks a key level (liquidity zone, support/resistance) but quickly reverses, "sweeping" stops before moving in opposite direction.

**Required Implementation**:
- **Data Needed**:
  - Recent price action (highs/lows)
  - Key levels (support/resistance, recent highs/lows)
  - Price movement patterns (wicks, rejections)
  
- **Logic Required**:
  1. Identify key levels (recent swing highs/lows, support/resistance)
  2. Detect if price broke above/below level recently (within last N candles)
  3. Check if price quickly reversed (moved back through level)
  4. Verify rejection pattern (long wick, rejection candle)
  5. For reversal: Fakeout suggests opposite direction move
  
- **Where to Add**:
  - In `auto_execution_system.py::_check_conditions()`
  - Session conditions section
  - Similar to existing liquidity sweep detection
  
- **Complexity**: **HIGH**
  - Requires pattern recognition
  - Level identification
  - Price action analysis
  - Similar to existing liquidity sweep logic (can reuse some)
  
- **Dependencies**:
  - Candle data (already exists)
  - Level identification (may need to implement or use existing)
  - Pattern recognition (similar to liquidity sweep - already exists)

---

### 3.4 `flat_vol_hours`

**What It Means**: Volatility has been flat (low and stable) for a specified number of hours, indicating compression before potential expansion.

**Required Implementation**:
- **Data Needed**:
  - ATR values over extended period (multiple hours)
  - Historical volatility measurements
  - Time tracking
  
- **Logic Required**:
  1. Calculate ATR for each hour over lookback period (e.g., last 5 hours)
  2. Check if ATR values are consistently low (below threshold)
  3. Verify ATR is stable (low variance between hours)
  4. Count consecutive hours with flat volatility
  5. Check if count >= `flat_vol_hours` threshold (e.g., 3 hours)
  6. For expansion: Flat volatility suggests upcoming breakout
  
- **Where to Add**:
  - In `auto_execution_system.py::_check_conditions()`
  - Session conditions section
  - Can use existing ATR calculation
  
- **Complexity**: **MEDIUM**
  - Requires extended period data (multiple hours)
  - ATR calculation over time
  - Stability/variance calculation
  
- **Dependencies**:
  - Existing ATR calculation (already exists)
  - Extended candle data (may need H1 or H4 candles)
  - Time tracking (already exists)

---

## 4. Pattern Conditions (2 conditions)

### 4.1 `pattern_evening_morning_star`

**What It Means**: Three-candle reversal pattern - Evening Star (bearish) or Morning Star (bullish) indicating potential trend reversal.

**Required Implementation**:
- **Data Needed**:
  - Recent candles (minimum 3 candles)
  - Candle body and wick analysis
  - Pattern recognition logic
  
- **Logic Required**:
  1. Identify three consecutive candles
  2. **Evening Star (Bearish)**:
     - First candle: Bullish (green/up)
     - Second candle: Small body, gaps up (star)
     - Third candle: Bearish (red/down), closes below first candle's midpoint
  3. **Morning Star (Bullish)**:
     - First candle: Bearish (red/down)
     - Second candle: Small body, gaps down (star)
     - Third candle: Bullish (green/up), closes above first candle's midpoint
  4. Verify pattern strength (body sizes, gaps, wicks)
  
- **Where to Add**:
  - In `auto_execution_system.py::_check_conditions()`
  - Pattern recognition section
  - Similar to existing `pattern_double_bottom` logic
  
- **Complexity**: **MEDIUM**
  - Requires candle pattern recognition
  - Body/wick analysis
  - Gap detection
  - Similar complexity to existing pattern recognition
  
- **Dependencies**:
  - Candle data (already exists)
  - Pattern recognition framework (may need to extend existing)

---

### 4.2 `pattern_three_drive`

**What It Means**: Harmonic pattern with three equal price moves to a level, indicating potential reversal at the third touch.

**Required Implementation**:
- **Data Needed**:
  - Extended price history (swing highs/lows)
  - Fibonacci retracement levels
  - Pattern geometry analysis
  
- **Logic Required**:
  1. Identify swing points (highs for bearish, lows for bullish)
  2. Find three drives to similar level:
     - Drive 1: First touch of level
     - Drive 2: Second touch (retracement then return)
     - Drive 3: Third touch (retracement then return)
  3. Verify drives are approximately equal (Fibonacci ratios: 1.0, 1.272, 1.414)
  4. Check if third drive is completing (price at level)
  5. For reversal: Third drive completion suggests reversal
  
- **Where to Add**:
  - In `auto_execution_system.py::_check_conditions()`
  - Pattern recognition section
  - More complex than other patterns
  
- **Complexity**: **HIGH**
  - Requires swing point identification
  - Fibonacci ratio calculations
  - Pattern geometry analysis
  - Extended price history needed
  
- **Dependencies**:
  - Extended candle data (already exists)
  - Swing point detection (may need to implement)
  - Fibonacci calculations (may need to implement)
  - Pattern recognition framework

---

## Summary: Implementation Effort

| Category | Conditions | Complexity | Estimated Effort |
|----------|------------|------------|------------------|
| **Quantitative** | 3 | Low-Medium | 2-3 days |
| **Correlation** | 5 | Medium | 3-4 days |
| **Session** | 4 | Medium-High | 4-5 days |
| **Pattern** | 2 | Medium-High | 3-4 days |
| **TOTAL** | **15** | - | **12-16 days** |

---

## Implementation Priority Recommendations

### High Priority (Easy Wins):
1. **`atr_stretch`** - Low complexity, reuses existing ATR
2. **`zscore`** - Simple statistical calculation
3. **`bb_retest`** - Similar to existing `bb_expansion`

### Medium Priority (Moderate Effort):
4. **`spx_up_pct`** - Similar to existing DXY logic
5. **`yield_drop`** - Similar to SPX, data already fetched
6. **`volatility_decay`** - Uses existing ATR and session logic
7. **`flat_vol_hours`** - Uses existing ATR, needs extended data

### Lower Priority (Higher Complexity):
8. **`correlation_divergence`** - More complex correlation logic
9. **`momentum_follow`** - Requires momentum indicators
10. **`fakeout_sweep`** - Complex pattern recognition
11. **`pattern_evening_morning_star`** - Pattern recognition
12. **`pattern_three_drive`** - Most complex, harmonic patterns

---

## Key Dependencies Already Available

✅ **Already Implemented**:
- ATR calculation (`_calculate_atr()`)
- Bollinger Band calculation (in `bb_expansion`)
- Session helpers (`SessionHelpers.get_current_session()`)
- Correlation calculator (`CorrelationContextCalculator`)
- Candle data fetching (`_get_recent_candles()`)
- Yahoo Finance integration (`yfinance` for SPX, US10Y)
- Pattern recognition framework (for `pattern_double_bottom`)

⚠️ **May Need to Add**:
- Extended candle history (for `flat_vol_hours`, `pattern_three_drive`)
- Momentum indicators (for `momentum_follow`)
- Swing point detection (for `pattern_three_drive`)
- Pattern recognition extensions (for new patterns)

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-07

