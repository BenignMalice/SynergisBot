# Enhanced Data Fields - Data Source Mapping

**Date**: December 11, 2025  
**Status**: ✅ **COMPLETE**  
**Purpose**: Map each field to existing services/functions and identify gaps

---

## Overview

This document maps each of the 9 enhanced data fields to their data sources, identifies dependencies, and documents data quality expectations.

---

## 1. Correlation Context (`correlation_context`)

### Data Sources

1. **Symbol Historical Data (MT5)**
   - **Service**: `infra/mt5_service.py` → `get_bars()` or `copy_rates_from_pos()`
   - **Timeframe**: M5 (5-minute bars)
   - **Count**: 240 bars (4 hours) for 240-minute window
   - **Fields Needed**: `close` prices
   - **Status**: ✅ Available

2. **DXY Historical Data (Yahoo Finance)**
   - **Service**: `infra/market_indices_service.py` → **NEW METHOD NEEDED**: `get_dxy_bars()`
   - **Symbol**: `"DX-Y.NYB"`
   - **Timeframe**: 5-minute intervals
   - **Fields Needed**: `Close` prices
   - **Status**: ⚠️ **GAP** - Currently only `get_dxy()` exists (returns current price only)
   - **Implementation**: Use `yfinance` → `yf.Ticker("DX-Y.NYB").history(period="5d", interval="5m")`

3. **SP500 Historical Data (Yahoo Finance)**
   - **Service**: `infra/market_indices_service.py` → **NEW METHOD NEEDED**: `get_sp500_bars()`
   - **Symbol**: `"^GSPC"` or `"SPY"`
   - **Timeframe**: 5-minute intervals
   - **Fields Needed**: `Close` prices
   - **Status**: ⚠️ **GAP** - Method doesn't exist
   - **Implementation**: Use `yfinance` → `yf.Ticker("^GSPC").history(period="5d", interval="5m")`

4. **US10Y Historical Data (Yahoo Finance)**
   - **Service**: `infra/market_indices_service.py` → **NEW METHOD NEEDED**: `get_us10y_bars()`
   - **Symbol**: `"^TNX"`
   - **Timeframe**: 5-minute intervals
   - **Fields Needed**: `Close` prices
   - **Status**: ⚠️ **GAP** - Currently only `get_us10y()` exists (returns current price only)
   - **Implementation**: Use `yfinance` → `yf.Ticker("^TNX").history(period="5d", interval="5m")`

5. **BTC Historical Data (MT5)**
   - **Service**: `infra/mt5_service.py` → `get_bars()` for `"BTCUSDc"`
   - **Timeframe**: M5 (5-minute bars)
   - **Count**: 240 bars (4 hours)
   - **Fields Needed**: `close` prices
   - **Status**: ✅ Available (for non-BTC symbols only)

6. **Correlation Calculation**
   - **Service**: `app/engine/historical_analysis_engine.py` → `HistoricalAnalysisEngine.calculate_correlation()`
   - **Method**: Static method (`@staticmethod`)
   - **Input**: Two numpy arrays of equal length (returns)
   - **Status**: ✅ Available

### Dependencies

- ✅ MT5 connection (for symbol and BTC data)
- ⚠️ Yahoo Finance API (via `yfinance` - can be unreliable)
- ✅ `pandas` for data alignment
- ✅ `numpy` for correlation calculation

### Data Quality Expectations

- **"good"**: >= 80% data overlap, >= 192 bars (80% of 240)
- **"limited"**: >= 50% data overlap, >= 120 bars (50% of 240)
- **"unavailable"**: < 50% overlap or < 120 bars

### Gaps to Fill

1. **REQUIRED**: Add `get_dxy_bars()` to `market_indices_service.py`
2. **REQUIRED**: Add `get_sp500_bars()` to `market_indices_service.py`
3. **REQUIRED**: Add `get_us10y_bars()` to `market_indices_service.py`
4. **REQUIRED**: Add `get_sp500()` method (current price) to `market_indices_service.py`

---

## 2. Order Flow (`order_flow`)

### Data Sources

1. **MT5 Tick Data (Non-BTC Symbols)**
   - **Service**: `infra/mt5_service.py` → `copy_ticks_from()` or `copy_ticks_range()`
   - **Fields Needed**: `bid`, `ask`, `volume`, `time`
   - **Status**: ✅ Available (but only tick volume, not separate buy/sell)
   - **Note**: MT5 doesn't provide bid/ask volume separately - must use proxy

2. **Volume Delta Proxy**
   - **Service**: `app/engine/volume_delta_proxy.py` → `VolumeDeltaProxy`
   - **Method**: `update_delta()` and `calculate_delta_proxy()`
   - **Input**: Tick data with direction
   - **Status**: ✅ Available (requires `symbol_config` parameter)

3. **Binance AggTrades (BTC Only)**
   - **Service**: `infra/binance_aggtrades_stream.py` or `infra/order_flow_service.py`
   - **Method**: `WhaleDetector.get_pressure()` or `OrderFlowService.get_buy_sell_pressure()`
   - **Fields Needed**: `buy_volume`, `sell_volume`
   - **Status**: ✅ Available (for BTCUSDc only)

### Dependencies

- ✅ MT5 connection (for tick data)
- ✅ `VolumeDeltaProxy` (for non-BTC proxy calculations)
- ✅ `OrderFlowService` or `WhaleDetector` (for BTC true order flow)
- ⚠️ Binance API (for BTC - can have rate limits)

### Data Quality Expectations

- **"good"**: BTC with Binance data (true buy/sell volume)
- **"proxy"**: Non-BTC with MT5 tick data (estimated from tick direction)
- **"limited"**: Insufficient tick data (< 100 ticks in window)
- **"unavailable"**: No tick data available

### Gaps to Fill

1. **REQUIRED**: Verify MT5 tick data availability for non-BTC symbols
2. **REQUIRED**: Create `symbol_config` dict for `VolumeDeltaProxy` initialization
3. **OPTIONAL**: Check if futures/CFD data provides true order flow (broker-dependent)

---

## 3. HTF Levels (`htf_levels`)

### Data Sources

1. **MT5 Daily Bars (D1)**
   - **Service**: `infra/mt5_service.py` → `get_bars()` with `timeframe="D1"`
   - **Count**: 30 days (for previous day high/low)
   - **Fields Needed**: `open`, `high`, `low`, `close`, `time`
   - **Status**: ✅ Available

2. **MT5 Weekly Bars (W1)**
   - **Service**: `infra/mt5_service.py` → `get_bars()` with `timeframe="W1"`
   - **Count**: 4 weeks (for previous week high/low)
   - **Fields Needed**: `open`, `high`, `low`, `close`, `time`
   - **Status**: ✅ Available

3. **MT5 Monthly Bars (MN1)**
   - **Service**: `infra/mt5_service.py` → `get_bars()` with `timeframe="MN1"`
   - **Count**: 3 months (for previous month high/low)
   - **Fields Needed**: `open`, `high`, `low`, `close`, `time`
   - **Status**: ✅ Available

4. **Timezone Conversion**
   - **Service**: `datetime` with `timezone.utc`
   - **Method**: Get MT5 broker timezone, convert to UTC
   - **Status**: ✅ Available (Python standard library)

### Dependencies

- ✅ MT5 connection
- ✅ `datetime` and `timezone` modules
- ⚠️ MT5 broker timezone detection (may vary by broker)

### Data Quality Expectations

- **"good"**: All timeframes available, timezone conversion successful
- **"limited"**: Some timeframes missing (e.g., insufficient monthly data)
- **"unavailable"**: MT5 connection failed or no historical data

### Gaps to Fill

1. **REQUIRED**: Implement timezone conversion logic (MT5 broker timezone → UTC)
2. **REQUIRED**: Calculate weekly/monthly boundaries correctly (Monday 00:00 UTC, 1st of month 00:00 UTC)
3. **NOTE**: Don't reuse existing PDH/PDL logic (it's for M15/M1, not D1/W1/MN1)

---

## 4. Session Risk (`session_risk`)

### Data Sources

1. **Current Time**
   - **Service**: `datetime.now(timezone.utc)`
   - **Status**: ✅ Available

2. **News Service**
   - **Service**: `infra/news_service.py` → `get_upcoming_events()`
   - **Method**: Returns list of events with `time` and `impact` fields
   - **Status**: ✅ Available

3. **Session Detection**
   - **Service**: `infra/feature_session_news.py` → `SessionNewsFeatures`
   - **Method**: `_compute_session_analysis()`
   - **Status**: ✅ Available

4. **Historical Volatility (Session Profile)**
   - **Service**: **NOT YET AVAILABLE** (future enhancement)
   - **Status**: ⚠️ **GAP** - Will default to "normal" if unavailable

### Dependencies

- ✅ `datetime` and `timezone` modules
- ✅ `NewsService` (for upcoming events)
- ✅ `SessionNewsFeatures` (for session detection)
- ⚠️ Historical volatility database (not yet implemented)

### Data Quality Expectations

- **"good"**: All data available (news, session, rollover calculation)
- **"limited"**: Session profile unavailable (defaults to "normal")
- **"unavailable"**: News service or session detection failed

### Gaps to Fill

1. **REQUIRED**: Implement rollover window calculation (00:00 UTC ±30min)
2. **REQUIRED**: Calculate `minutes_to_next_high_impact` from news events
3. **OPTIONAL**: Build historical volatility database for session profile (future enhancement)

---

## 5. Execution Context (`execution_context`)

### Data Sources

1. **Current Spread (MT5)**
   - **Service**: `infra/mt5_service.py` → `get_quote()` or `symbol_info()`
   - **Fields Needed**: `bid`, `ask`
   - **Calculation**: `spread = ask - bid`
   - **Status**: ✅ Available

2. **Historical Spread Data**
   - **Service**: `infra/spread_tracker.py` → `SpreadTracker`
   - **Methods**: `get_average_spread()`, `get_spread_data()`
   - **Status**: ✅ Available

3. **Median Spread**
   - **Service**: `infra/spread_tracker.py` → **NEW METHOD NEEDED**: `get_median_spread()`
   - **Status**: ⚠️ **GAP** - Currently only `get_average_spread()` exists
   - **Alternative**: Use `get_average_spread()` (average ≈ median for large samples)

4. **Trade History (Slippage)**
   - **Service**: Trade history database or MT5 trade history
   - **Fields Needed**: `entry_price`, `requested_price`, `executed_price`
   - **Calculation**: `slippage = abs(executed_price - requested_price)`
   - **Status**: ⚠️ **GAP** - May not be tracked, return `slippage_data_available: False` if unavailable

### Dependencies

- ✅ MT5 connection (for current spread)
- ✅ `SpreadTracker` (for historical spread)
- ⚠️ Trade history database (for slippage - may not exist)

### Data Quality Expectations

- **"good"**: Spread and slippage data available
- **"limited"**: Spread available but slippage unavailable
- **"unavailable"**: MT5 connection failed

### Gaps to Fill

1. **REQUIRED**: Add `get_median_spread()` to `SpreadTracker` OR use `get_average_spread()` as fallback
2. **REQUIRED**: Verify trade history database structure (if exists, query for slippage)
3. **OPTIONAL**: Start tracking slippage for new trades (future enhancement)

---

## 6. Strategy Stats (`strategy_stats`)

### Data Sources

1. **Trade Results Database**
   - **Service**: `infra/strategy_performance_tracker.py` → `StrategyPerformanceTracker`
   - **Database**: `data/strategy_performance.db`
   - **Table**: `trade_results`
   - **Status**: ✅ Available

2. **Regime Column**
   - **Service**: `trade_results` table → **NEW COLUMN NEEDED**: `regime TEXT`
   - **Status**: ⚠️ **GAP** - Column doesn't exist, needs migration

3. **Volatility Regime Detection**
   - **Service**: `infra/volatility_regime_detector.py` or volatility system
   - **Method**: Get current regime classification
   - **Status**: ✅ Available

4. **Regime Matching**
   - **Service**: **NEW LOGIC NEEDED** - Fuzzy matching of regimes
   - **Status**: ⚠️ **GAP** - Needs implementation

### Dependencies

- ✅ SQLite database (`strategy_performance.db`)
- ✅ `StrategyPerformanceTracker` (for querying trades)
- ⚠️ `regime` column in `trade_results` table (needs migration)
- ✅ Volatility regime detection (for current regime)

### Data Quality Expectations

- **"good"**: Sample size >= 30, exact or fuzzy regime match
- **"limited"**: Sample size >= 10, approximate regime match
- **"unavailable"**: Sample size < 10 or no data → return `None`

### Gaps to Fill

1. **REQUIRED**: Add `regime TEXT` column to `trade_results` table (migration)
2. **REQUIRED**: Store volatility regime when recording trades (at entry time)
3. **REQUIRED**: Implement regime matching logic (exact → fuzzy → approximate)
4. **REQUIRED**: For existing trades, infer regime from `entry_time` timestamp

---

## 7. Structure Summary (`structure_summary`)

### Data Sources

1. **M1 Microstructure Data**
   - **Service**: Already in `analyse_symbol_full` response → `response.data.m1_microstructure`
   - **Fields Needed**: `liquidity_zones`, `choch_bos`, `structure`
   - **Status**: ✅ Available (no new fetching needed)

2. **SMC Data**
   - **Service**: Already in `analyse_symbol_full` response → `response.data.smc`
   - **Fields Needed**: `trend`, `structure`
   - **Status**: ✅ Available (no new fetching needed)

3. **HTF Levels (Optional)**
   - **Service**: `htf_levels` field (from Phase 1.3)
   - **Fields Needed**: `current_price_position`, `range_reference`
   - **Status**: ⚠️ **DEPENDENCY** - Requires Phase 1.3 completion

### Dependencies

- ✅ `m1_microstructure` (already in response)
- ✅ `smc` data (already in response)
- ⚠️ `htf_levels` (optional dependency - from Phase 1.3)

### Data Quality Expectations

- **"good"**: All required data available
- **"limited"**: Some fields missing (use defaults)
- **"unavailable"**: M1 microstructure unavailable

### Gaps to Fill

1. **REQUIRED**: Implement interpretation logic (derive from existing data)
2. **REQUIRED**: Use safe data access (`.get()` methods) for missing fields
3. **NOTE**: No new data fetching needed - just interpretation layer

---

## 8. Symbol Constraints (`symbol_constraints`)

### Data Sources

1. **Configuration File**
   - **Service**: `config/symbol_constraints.json` (NEW file)
   - **Format**: JSON with symbol-specific constraints
   - **Status**: ⚠️ **GAP** - File doesn't exist, needs creation

2. **Default Constraints**
   - **Service**: `infra/symbol_constraints_manager.py` → `_get_default_constraints()`
   - **Status**: ⚠️ **GAP** - Needs implementation

### Dependencies

- ✅ JSON file reading (Python standard library)
- ⚠️ Configuration file structure (needs definition)

### Data Quality Expectations

- **"good"**: Config file exists and valid
- **"limited"**: Config file missing, using defaults
- **"unavailable"**: Config file corrupted (use defaults)

### Gaps to Fill

1. **REQUIRED**: Create `config/symbol_constraints.json` with default structure
2. **REQUIRED**: Implement `SymbolConstraintsManager` class
3. **REQUIRED**: Define default constraints structure

---

## Dependency Graph

```
correlation_context
├── MT5 Service (symbol + BTC data) ✅
├── Market Indices Service (DXY, SP500, US10Y) ⚠️ Needs new methods
└── Historical Analysis Engine (correlation calc) ✅

order_flow
├── MT5 Service (tick data) ✅
├── Volume Delta Proxy ⚠️ Needs symbol_config
└── Order Flow Service / WhaleDetector (BTC only) ✅

htf_levels
├── MT5 Service (D1, W1, MN1 bars) ✅
└── Timezone conversion logic ⚠️ Needs implementation

session_risk
├── News Service ✅
├── Session Detection ✅
└── Historical Volatility (session profile) ⚠️ Not yet available

execution_context
├── MT5 Service (current spread) ✅
├── Spread Tracker ⚠️ Needs get_median_spread()
└── Trade History (slippage) ⚠️ May not exist

strategy_stats
├── Strategy Performance Tracker ✅
├── Trade Results Database ⚠️ Needs regime column
└── Regime Matching Logic ⚠️ Needs implementation

structure_summary
├── M1 Microstructure (already in response) ✅
├── SMC Data (already in response) ✅
└── HTF Levels (optional dependency) ⚠️ From Phase 1.3

symbol_constraints
├── Config File ⚠️ Needs creation
└── Default Constraints ⚠️ Needs definition
```

---

## Summary of Gaps

### Critical Gaps (Must Fix)

1. **Market Indices Service**: Add `get_dxy_bars()`, `get_us10y_bars()`, `get_sp500_bars()`, `get_sp500()`
2. **Spread Tracker**: Add `get_median_spread()` OR use `get_average_spread()` as fallback
3. **Strategy Performance Tracker**: Add `regime` column to `trade_results` table (migration)
4. **Symbol Constraints**: Create `config/symbol_constraints.json` and `SymbolConstraintsManager`

### Optional Gaps (Can Default)

1. **Session Profile**: Historical volatility database (default to "normal")
2. **Slippage Tracking**: Trade history database (return `slippage_data_available: False`)

### Implementation Dependencies

1. **Volume Delta Proxy**: Requires `symbol_config` dict (can create with defaults)
2. **HTF Levels**: Requires timezone conversion logic (can implement)
3. **Strategy Stats**: Requires regime matching logic (can implement)
4. **Structure Summary**: Depends on `htf_levels` (optional - can work without)

---

**Status**: ✅ **COMPLETE** - All data sources mapped and gaps identified

