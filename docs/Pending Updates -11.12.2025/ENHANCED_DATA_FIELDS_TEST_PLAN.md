# Enhanced Data Fields - Testing Strategy

**Date**: December 11, 2025  
**Status**: ✅ **COMPLETE**  
**Purpose**: Define comprehensive testing strategy for all 9 enhanced data fields

---

## Overview

This document outlines the testing strategy for all 9 enhanced data fields, including unit tests, integration tests, and ChatGPT integration tests.

---

## Test Structure

### Test Files to Create

1. `tests/test_correlation_context_calculator.py` - Correlation context tests
2. `tests/test_general_order_flow_metrics.py` - Order flow tests
3. `tests/test_htf_levels_calculator.py` - HTF levels tests
4. `tests/test_execution_quality_monitor.py` - Execution context tests
5. `tests/test_strategy_performance_tracker_regime.py` - Strategy stats tests
6. `tests/test_structure_summary.py` - Structure summary tests
7. `tests/test_symbol_constraints_manager.py` - Symbol constraints tests
8. `tests/test_enhanced_data_fields_integration.py` - Integration tests
9. `tests/test_data_quality_indicators.py` - Data quality tests

---

## 1. Correlation Context Tests

### Unit Tests

**File**: `tests/test_correlation_context_calculator.py`

**Test Cases**:
1. ✅ Test initialization with MT5 and market indices services
2. ✅ Test `calculate_correlation_context()` with valid data
3. ✅ Test correlation calculation for DXY (expected negative for Gold)
4. ✅ Test correlation calculation for SP500
5. ✅ Test correlation calculation for US10Y
6. ✅ Test correlation calculation for BTC (non-BTC symbols only)
7. ✅ Test conflict detection (gold_vs_dxy_conflict when correlation breaks pattern)
8. ✅ Test data quality "good" (>=80% overlap, >=192 bars)
9. ✅ Test data quality "limited" (>=50% overlap, >=120 bars)
10. ✅ Test data quality "unavailable" (<50% overlap or <120 bars)
11. ✅ Test missing MT5 data (returns unavailable)
12. ✅ Test missing Yahoo Finance data (returns None for that correlation)
13. ✅ Test timestamp alignment (pandas merge_asof)
14. ✅ Test returns calculation (prices to returns conversion)
15. ✅ Test edge cases (zero prices, negative prices, NaN values)
16. ✅ Test async/await functionality
17. ✅ Test error isolation (doesn't crash on single correlation failure)

**Mock Requirements**:
- Mock `mt5_service.get_bars()` for symbol and BTC
- Mock `market_indices_service.get_dxy_bars()`, `get_sp500_bars()`, `get_us10y_bars()`
- Mock `HistoricalAnalysisEngine.calculate_correlation()` (static method)

**Integration Tests**:
- Test with real MT5 connection (if available)
- Test with real Yahoo Finance API (may be flaky)
- Test full data flow from calculation to response

---

## 2. Order Flow Tests

### Unit Tests

**File**: `tests/test_general_order_flow_metrics.py`

**Test Cases**:
1. ✅ Test initialization with MT5 and order flow services
2. ✅ Test `get_order_flow_metrics()` for non-BTC symbols (proxy)
3. ✅ Test `get_order_flow_metrics()` for BTC (true order flow)
4. ✅ Test CVD calculation (cumulative volume delta)
5. ✅ Test CVD slope detection ("up", "down", "flat")
6. ✅ Test aggressor ratio calculation (buy_vol / sell_vol)
7. ✅ Test imbalance score calculation (0-100)
8. ✅ Test data quality "good" (BTC with Binance data)
9. ✅ Test data quality "proxy" (non-BTC with MT5 tick data)
10. ✅ Test data quality "limited" (insufficient tick data)
11. ✅ Test data quality "unavailable" (no tick data)
12. ✅ Test division by zero handling (aggressor_ratio when sell_vol == 0)
13. ✅ Test tick data processing (direction detection)
14. ✅ Test VolumeDeltaProxy integration
15. ✅ Test OrderFlowService integration (BTC)
16. ✅ Test async/await functionality
17. ✅ Test error isolation

**Mock Requirements**:
- Mock `mt5_service.copy_ticks_from()` or `copy_ticks_range()`
- Mock `VolumeDeltaProxy` for non-BTC
- Mock `OrderFlowService` or `WhaleDetector` for BTC

**Integration Tests**:
- Test with real MT5 tick data (if available)
- Test with real Binance API (for BTC)
- Test full data flow

---

## 3. HTF Levels Tests

### Unit Tests

**File**: `tests/test_htf_levels_calculator.py`

**Test Cases**:
1. ✅ Test initialization with MT5 service
2. ✅ Test `calculate_htf_levels()` with valid data
3. ✅ Test weekly open calculation (Monday 00:00 UTC)
4. ✅ Test monthly open calculation (1st of month 00:00 UTC)
5. ✅ Test previous week high/low calculation
6. ✅ Test previous day high/low calculation (aligns with PDH/PDL)
7. ✅ Test timezone conversion (MT5 broker timezone → UTC)
8. ✅ Test current price position calculation ("discount", "equilibrium", "premium")
9. ✅ Test range reference determination ("weekly_range", "daily_range", "session_range")
10. ✅ Test discount/premium thresholds (33%/66%)
11. ✅ Test missing D1 data handling
12. ✅ Test missing W1 data handling
13. ✅ Test missing MN1 data handling
14. ✅ Test edge cases (single bar, no historical data)
15. ✅ Test async/await functionality
16. ✅ Test error isolation

**Mock Requirements**:
- Mock `mt5_service.get_bars()` for D1, W1, MN1
- Mock MT5 broker timezone detection

**Integration Tests**:
- Test with real MT5 connection
- Test timezone conversion accuracy
- Test full data flow

---

## 4. Session Risk Tests

### Unit Tests

**File**: `tests/test_session_risk.py` (helper function, not separate service)

**Test Cases**:
1. ✅ Test `calculate_session_risk()` with valid data
2. ✅ Test rollover window detection (00:00 UTC ±30min)
3. ✅ Test news lock detection (high-impact within ±30min)
4. ✅ Test `minutes_to_next_high_impact` calculation
5. ✅ Test `is_in_high_impact_window` detection
6. ✅ Test session profile default ("normal" if historical data unavailable)
7. ✅ Test session volatility multiplier default (1.0 if unavailable)
8. ✅ Test missing news service handling
9. ✅ Test missing session data handling
10. ✅ Test edge cases (no upcoming events, multiple events)
11. ✅ Test timezone handling (UTC)
12. ✅ Test error isolation

**Mock Requirements**:
- Mock `NewsService.get_upcoming_events()`
- Mock `SessionNewsFeatures._compute_session_analysis()`

**Integration Tests**:
- Test with real news service
- Test with real session detection
- Test full data flow

---

## 5. Execution Context Tests

### Unit Tests

**File**: `tests/test_execution_quality_monitor.py`

**Test Cases**:
1. ✅ Test initialization with MT5 and spread tracker
2. ✅ Test `get_execution_context()` with valid data
3. ✅ Test current spread calculation
4. ✅ Test spread_vs_median calculation
5. ✅ Test is_spread_elevated detection (>1.5x)
6. ✅ Test slippage calculation (if available)
7. ✅ Test slippage_vs_normal calculation
8. ✅ Test is_slippage_elevated detection (>1.5x)
9. ✅ Test execution_quality "good" (spread and slippage normal)
10. ✅ Test execution_quality "degraded" (either elevated)
11. ✅ Test execution_quality "poor" (both very elevated)
12. ✅ Test missing slippage data (slippage_data_available: False)
13. ✅ Test SpreadTracker integration
14. ✅ Test get_median_spread() OR get_average_spread() fallback
15. ✅ Test async/await functionality
16. ✅ Test error isolation

**Mock Requirements**:
- Mock `mt5_service.get_quote()` or `symbol_info()`
- Mock `SpreadTracker.get_spread_data()`
- Mock trade history database (for slippage)

**Integration Tests**:
- Test with real MT5 connection
- Test with real SpreadTracker
- Test full data flow

---

## 6. Strategy Stats Tests

### Unit Tests

**File**: `tests/test_strategy_performance_tracker_regime.py`

**Test Cases**:
1. ✅ Test `get_strategy_stats_by_regime()` with valid data
2. ✅ Test exact regime match
3. ✅ Test fuzzy regime match (via REGIME_MAPPING)
4. ✅ Test approximate regime match (closest match)
5. ✅ Test win_rate calculation
6. ✅ Test avg_rr calculation
7. ✅ Test max_drawdown_rr calculation
8. ✅ Test median_holding_time_minutes calculation
9. ✅ Test confidence "high" (sample_size >= 30, exact/fuzzy match)
10. ✅ Test confidence "medium" (sample_size >= 10)
11. ✅ Test return None if sample_size < 10
12. ✅ Test regime_match_quality determination
13. ✅ Test database query with regime filter
14. ✅ Test missing regime column handling (migration check)
15. ✅ Test existing trades without regime (infer from timestamp)
16. ✅ Test async/await functionality
17. ✅ Test error isolation

**Mock Requirements**:
- Mock SQLite database
- Mock `StrategyPerformanceTracker` database queries
- Mock volatility regime detection

**Integration Tests**:
- Test with real database (create test database)
- Test regime matching accuracy
- Test full data flow

---

## 7. Structure Summary Tests

### Unit Tests

**File**: `tests/test_structure_summary.py` (helper function, not separate service)

**Test Cases**:
1. ✅ Test `calculate_structure_summary()` with valid data
2. ✅ Test current_range_type determination
3. ✅ Test range_state calculation ("mid_range", "near_range_high", etc.)
4. ✅ Test liquidity sweep detection
5. ✅ Test sweep_type determination ("bull", "bear", "none")
6. ✅ Test discount_premium_state calculation
7. ✅ Test range boundaries extraction (from m1_microstructure)
8. ✅ Test missing m1_microstructure handling (use defaults)
9. ✅ Test missing smc data handling (use defaults)
10. ✅ Test missing htf_levels handling (optional dependency)
11. ✅ Test safe data access (`.get()` methods)
12. ✅ Test error isolation

**Mock Requirements**:
- Mock `m1_microstructure` data structure
- Mock `smc` data structure
- Mock `htf_levels` (optional)

**Integration Tests**:
- Test with real `analyse_symbol_full` response
- Test full data flow

---

## 8. Symbol Constraints Tests

### Unit Tests

**File**: `tests/test_symbol_constraints_manager.py`

**Test Cases**:
1. ✅ Test initialization with config file
2. ✅ Test `get_symbol_constraints()` with symbol in config
3. ✅ Test `get_symbol_constraints()` with symbol not in config (returns defaults)
4. ✅ Test missing config file handling (returns defaults)
5. ✅ Test corrupted config file handling (returns defaults, logs error)
6. ✅ Test default constraints structure
7. ✅ Test config file validation
8. ✅ Test JSON parsing errors
9. ✅ Test file path handling
10. ✅ Test error isolation

**Mock Requirements**:
- Mock config file (create/delete for tests)
- Mock file system operations

**Integration Tests**:
- Test with real config file
- Test config file updates
- Test full data flow

---

## 9. Integration Tests

### File: `tests/test_enhanced_data_fields_integration.py`

**Test Cases**:
1. ✅ Test all 9 fields appear in `analyse_symbol_full` response
2. ✅ Test field data types are correct
3. ✅ Test all fields are JSON-serializable (no numpy, no datetime objects)
4. ✅ Test data quality indicators are present where applicable
5. ✅ Test with real symbols (XAUUSD, BTCUSD, EURUSD)
6. ✅ Test both `_format_unified_analysis` code paths (line ~861 and ~6502)
7. ✅ Test error isolation (one field failure doesn't crash entire analysis)
8. ✅ Test backward compatibility (existing fields unchanged)
9. ✅ Test performance (<2 seconds total for all 9 fields)
10. ✅ Test parallelization (independent fields calculated in parallel)
11. ✅ Test caching effectiveness
12. ✅ Test with missing services (graceful degradation)

---

## 10. Data Quality Tests

### File: `tests/test_data_quality_indicators.py`

**Test Cases**:
1. ✅ Test data quality "good" across all applicable fields
2. ✅ Test data quality "limited" across all applicable fields
3. ✅ Test data quality "proxy" (order_flow for non-BTC)
4. ✅ Test data quality "unavailable" across all applicable fields
5. ✅ Test ChatGPT ignores fields with "unavailable" quality
6. ✅ Test ChatGPT uses "limited" fields with caution
7. ✅ Test ChatGPT understands "proxy" limitations
8. ✅ Test data quality consistency across fields

---

## Performance Tests

### Test Cases

1. ✅ Test correlation calculation < 500ms
2. ✅ Test order flow calculation < 500ms
3. ✅ Test HTF levels calculation < 500ms
4. ✅ Test session risk calculation < 100ms (simple calculation)
5. ✅ Test execution context calculation < 200ms
6. ✅ Test strategy stats calculation < 300ms
7. ✅ Test structure summary calculation < 100ms (derived from existing data)
8. ✅ Test symbol constraints calculation < 50ms (config file read)
9. ✅ Test total time < 2 seconds for all 9 fields combined
10. ✅ Test parallelization reduces total time
11. ✅ Test caching reduces repeated calculation time

---

## ChatGPT Integration Tests

### Test Cases

1. ✅ Test ChatGPT can access all 9 new fields
2. ✅ Test ChatGPT checks data_quality before using fields
3. ✅ Test ChatGPT ignores fields with "unavailable" quality
4. ✅ Test ChatGPT uses "proxy" fields with caution
5. ✅ Test ChatGPT interprets correlation conflicts correctly
6. ✅ Test ChatGPT uses order flow for momentum assessment
7. ✅ Test ChatGPT uses HTF levels for context
8. ✅ Test ChatGPT respects session risk flags
9. ✅ Test ChatGPT uses execution quality for risk management
10. ✅ Test ChatGPT uses strategy stats for validation
11. ✅ Test ChatGPT uses structure summary for interpretation
12. ✅ Test ChatGPT respects symbol constraints
13. ✅ Test cross-field reasoning (combining multiple fields)
14. ✅ Test error handling (graceful degradation when fields unavailable)

---

## Test Execution Order

### Phase 1: Unit Tests (Per Field)
1. Correlation Context
2. Order Flow
3. HTF Levels
4. Session Risk
5. Execution Context
6. Strategy Stats
7. Structure Summary
8. Symbol Constraints

### Phase 2: Integration Tests
1. Full data flow tests
2. Error isolation tests
3. Performance tests

### Phase 3: ChatGPT Integration Tests
1. Field access tests
2. Data quality handling tests
3. Interpretation tests

---

## Test Data Requirements

### Mock Data

- MT5 historical bars (M5, D1, W1, MN1)
- MT5 tick data
- Yahoo Finance historical data (DXY, SP500, US10Y)
- News events data
- Trade history data
- Strategy performance data

### Real Data (Integration Tests)

- Real MT5 connection (if available)
- Real Yahoo Finance API (may be flaky)
- Real Binance API (for BTC order flow)
- Real database (create test database)

---

## Success Criteria

### Unit Tests
- ✅ All unit tests pass
- ✅ Code coverage >= 80% for new code
- ✅ All edge cases handled
- ✅ All error cases handled

### Integration Tests
- ✅ All integration tests pass
- ✅ All fields appear in response
- ✅ All fields are JSON-serializable
- ✅ Performance targets met (<2s total)

### ChatGPT Integration Tests
- ✅ ChatGPT can access all fields
- ✅ ChatGPT checks data quality correctly
- ✅ ChatGPT interprets fields correctly
- ✅ ChatGPT handles unavailable fields gracefully

---

**Status**: ✅ **COMPLETE** - Comprehensive testing strategy defined

