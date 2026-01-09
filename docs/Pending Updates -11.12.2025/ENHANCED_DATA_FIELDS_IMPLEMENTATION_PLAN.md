# Implementation Plan: Enhanced Data Fields for ChatGPT Market Snapshot

**Date**: December 11, 2025  
**Status**: 📋 **PLANNING** - Ready for implementation  
**Priority**: **HIGH** - Enhances ChatGPT's analytical capabilities  
**Estimated Effort**: 3-4 weeks (phased implementation)

---

## Overview

This plan details the implementation of 9 new data blocks to be added to the `analyse_symbol_full` response, significantly enhancing ChatGPT's ability to perform sophisticated market analysis and trade recommendations. These fields provide correlation context, order flow signals, HTF levels, session risk flags, execution quality metrics, strategy performance stats, structure summaries, and symbol constraints.

**Goal**: Provide structured, actionable data that ChatGPT can use to:
- Identify cross-asset divergences and correlations
- Assess order flow quality and momentum
- Reference HTF key levels in analysis
- Flag session risk and news windows
- Evaluate execution quality vs. normal conditions
- Reference historical strategy performance in similar regimes
- Interpret microstructure patterns more effectively
- Respect symbol-specific trading constraints

---

## ⚠️ CRITICAL ISSUES IDENTIFIED & FIXED

### Issue 1: Correlation Calculation - Use Existing Infrastructure ✅
**Problem**: Plan suggested creating new correlation calculator, but `HistoricalAnalysisEngine.calculate_correlation()` already exists.

**Fix**: Reuse existing `app/engine/historical_analysis_engine.py` correlation calculation method. Only need to create wrapper service that:
- Fetches historical data for symbol (from MT5)
- Fetches historical data for reference assets (DXY, SP500 from Yahoo Finance via `market_indices_service`)
- Aligns timeframes (both need same bar count and time alignment)
- Calculates rolling correlation using existing method

**⚠️ CRITICAL FIX (Review Round 1)**:
- `HistoricalAnalysisEngine.__init__` requires `symbol_config: Dict[str, Any]` parameter - cannot instantiate without it
- **Solution**: Create a lightweight wrapper that uses `HistoricalAnalysisEngine.calculate_correlation()` as a static method (it's already `@staticmethod`)
- Convert price data to returns (percentage changes) before correlation calculation
- `calculate_correlation()` takes two numpy arrays of equal length - ensure proper alignment

### Issue 2: Order Flow for Non-BTC - Data Limitations ⚠️
**Problem**: MT5 doesn't provide bid/ask volume separately - only tick volume. True order flow requires separate buy/sell volume.

**Fix**: 
- For BTC: Use existing `btc_order_flow_metrics` (Binance data)
- For other symbols: Use proxy methods from `app/engine/volume_delta_proxy.py` OR limited futures/CFD data if available
- **CRITICAL**: Mark data quality clearly (`data_quality: "proxy" | "limited" | "good"`)
- ChatGPT must understand limitations: "Proxy order flow - less reliable than true order flow"

**⚠️ CRITICAL FIX (Review Round 1)**:
- `VolumeDeltaProxy.__init__` requires `symbol_config: Dict[str, Any]` parameter - cannot instantiate without it
- **Solution**: Create symbol config dict with required fields: `{'delta_threshold': 1.5, 'delta_lookback_ticks': 100, 'delta_spike_threshold': 2.0}`
- Verify MT5 provides tick data for non-BTC symbols (may need to use `copy_ticks_from()` or `copy_ticks_range()`)
- If tick data unavailable, fallback to price-action proxy (less accurate but still useful)

### Issue 3: HTF Levels - Timezone Alignment ⚠️
**Problem**: MT5 uses broker timezone, need to align with UTC for weekly/monthly calculations.

**Fix**: 
- Use MT5's `copy_rates_from()` with proper timezone conversion
- Calculate weekly/monthly boundaries in UTC
- Handle broker timezone offset correctly
- Previous week/month calculations need proper date handling (not just -7 days)

### Issue 4: Session Risk - Rollover Window Definition ⚠️
**Problem**: Rollover window definition unclear - is it 00:00 UTC or broker time?

**Fix**: 
- Use 00:00 UTC ±30min for rollover window (standard FX rollover)
- Check `infra/circuit_breaker.py` for existing rollover logic (uses UTC+2 midnight)
- Align with existing session detection in `infra/feature_session_news.py`

### Issue 5: Execution Context - Reuse Existing Spread Tracker ✅
**Problem**: Plan suggested creating new spread tracker, but `infra/spread_tracker.py` already exists.

**Fix**: 
- Reuse `SpreadTracker` class from `infra/spread_tracker.py`
- Extend with slippage tracking (may need trade history query)
- Add execution quality scoring based on spread + slippage

**⚠️ CRITICAL FIX (Review Round 1)**:
- `SpreadTracker` has `get_average_spread()` but NOT `get_median_spread()` - plan references median
- **Solution**: Add `get_median_spread()` method to `SpreadTracker` OR use `get_average_spread()` (average is close to median for large samples)
- For slippage tracking: Verify if trade history database exists and has slippage data
- If slippage data unavailable, return `slippage_data_available: False` and skip slippage calculations
- `SpreadTracker.get_spread_data()` returns `SpreadData` with `spread_ratio` (current/average) - can use this for `spread_vs_median`

### Issue 6: Strategy Stats - Regime Filtering Missing ⚠️
**Problem**: `StrategyPerformanceTracker` exists but doesn't filter by volatility regime.

**Fix**: 
- Extend `StrategyPerformanceTracker` to accept regime filter
- Match current regime to historical regimes (fuzzy matching: "STABLE" matches "stable_vol_range_compression")
- Handle cases where no historical data exists for regime (return `None` with `sample_size: 0`)

**⚠️ CRITICAL FIX (Review Round 1)**:
- Database schema (`trade_results` table) does NOT have `regime` column - needs to be added
- **Solution**: Add migration to add `regime TEXT` column to `trade_results` table
- When recording trades, store the volatility regime at trade time
- For existing trades without regime, use fuzzy matching on `created_at` timestamp to infer regime from volatility history
- Regime matching logic: Define mapping (e.g., "STABLE" → ["stable_vol_range_compression", "stable_vol_trending"])
- Minimum sample size: Require at least 10 trades for confidence calculation

### Issue 7: Structure Summary - Derive from Existing Data ✅
**Problem**: Plan suggested new calculation, but can derive from existing `m1_microstructure` data.

**Fix**: 
- Create helper function that interprets `m1_microstructure` data
- Extract liquidity zones, sweeps, range state from existing structure
- No new data fetching needed - just interpretation layer

### Issue 8: Integration - Both `_format_unified_analysis` Functions ⚠️
**Problem**: Plan mentioned updating `_format_unified_analysis` but there are TWO instances (line ~861 and ~6502).

**Fix**: 
- Update BOTH instances of `_format_unified_analysis`
- Ensure consistent parameter signatures
- Test both code paths

### Issue 9: Data Source Alignment - Yahoo Finance vs MT5 ⚠️
**Problem**: Correlation calculation needs to align MT5 data (symbol) with Yahoo Finance data (DXY, SP500) - different timeframes and data quality.

**Fix**: 
- Fetch both datasets with same bar count
- Align timestamps (handle missing bars)
- Use interpolation if needed
- Mark data quality in response

**⚠️ CRITICAL FIX (Review Round 1)**:
- Yahoo Finance data may have gaps (weekends, holidays) - MT5 data may not
- **Solution**: Use pandas `merge_asof()` or `reindex()` to align timestamps
- Convert both to same timezone (UTC) before alignment
- Handle missing bars: Forward-fill last known value OR skip bars with missing data
- Minimum overlap requirement: Require at least 50% of bars to overlap for valid correlation
- Data quality indicator: "limited" if <80% overlap, "good" if >=80% overlap

---

## New Data Fields Summary

### 1. **correlation_context** - Cross-Asset Correlation Analysis
### 2. **order_flow** - Volume & Order Flow Signals (Non-BTC)
### 3. **htf_levels** - Higher Timeframe Key Levels Map
### 4. **session_risk** - Session & Danger Zone Flags
### 5. **execution_context** - Spread, Slippage & Execution Quality
### 6. **strategy_stats** - Historical Strategy Performance
### 7. **structure_summary** - Range/Microstructure Story Flags
### 8. **symbol_constraints** - Trade/Risk Constraints per Symbol
### 9. **Enhanced order_flow** - Extend existing BTC order flow for all symbols

---

## Phase 0: Data Structure Design & Planning

**Status**: ✅ **COMPLETE**

### Tasks

1. **Define Data Structures**
   - Create Python type definitions/dataclasses for all 9 new blocks
   - Document field types, ranges, and nullability
   - Define validation rules
   - Create example JSON structures

2. **Identify Data Sources & Dependencies**
   - Map each field to existing services/functions
   - Identify gaps requiring new implementations
   - Document dependencies and data quality expectations
   - Create dependency graph

3. **Create Implementation Checklist**
   - Break down each field into implementation tasks
   - Estimate effort per field
   - Identify dependencies between fields
   - Create test plan

**Deliverables**:
- `docs/Pending Updates -11.12.2025/ENHANCED_DATA_FIELDS_STRUCTURE.md` - Data structure definitions
- `docs/Pending Updates -11.12.2025/ENHANCED_DATA_FIELDS_SOURCES.md` - Data source mapping
- `docs/Pending Updates -11.12.2025/ENHANCED_DATA_FIELDS_TEST_PLAN.md` - Testing strategy

---

## Phase 1: Backend Implementation - Core Data Fields

**Status**: 📋 **PENDING**

### 1.1 Correlation Context (`correlation_context`)

**Status**: ✅ **COMPLETE** - Implementation and tests passing

**Location**: New service: `infra/correlation_context_calculator.py`

**Implementation**:
```python
class CorrelationContextCalculator:
    def __init__(self, mt5_service=None, market_indices_service=None):
        self.mt5_service = mt5_service
        self.market_indices = market_indices_service
        # Reuse existing correlation calculation (static method - no instantiation needed)
        from app.engine.historical_analysis_engine import HistoricalAnalysisEngine
        # Note: calculate_correlation is @staticmethod - call directly, no instantiation needed
    
    def calculate_correlation_context(
        self, 
        symbol: str, 
        window_minutes: int = 240
    ) -> Dict[str, Any]:
        """
        Calculate rolling correlation vs DXY, SP500, US10Y, BTC (if relevant)
        
        Returns:
        {
            "corr_window_minutes": 240,
            "corr_vs_dxy": -0.72,  # -1 to +1, or None if unavailable
            "corr_vs_sp500": 0.15,
            "corr_vs_us10y": -0.48,
            "corr_vs_btc": 0.05,  # Only for non-BTC symbols
            "conflict_flags": {
                "gold_vs_dxy_conflict": True,  # If correlation breaks expected pattern
                "sp500_divergence": False
            },
            "data_quality": "good" | "limited" | "unavailable",  # Based on sample size
            "sample_size": 240  # Number of bars used
        }
        """
        # 1. Fetch symbol historical data (M5 bars from MT5)
        # 2. Convert prices to returns: returns = np.diff(prices) / prices[:-1]
        # 3. Fetch DXY/SP500/US10Y data (Yahoo Finance via market_indices_service)
        # 4. Convert to returns and align timestamps (pandas merge_asof or reindex)
        # 5. Ensure equal length arrays (handle missing bars - forward fill or skip)
        # 6. Calculate correlation using HistoricalAnalysisEngine.calculate_correlation(series1, series2)
        # 7. Validate minimum overlap (require >=50% for "limited", >=80% for "good")
        # 8. Detect conflicts (e.g., gold should be -0.7 vs DXY, but showing -0.2)
        # 9. Return with data quality indicator
```

**Data Sources**:
- MT5 historical data for symbol (M5 timeframe, last N bars)
- `infra/market_indices_service.py` for DXY, SP500, US10Y (Yahoo Finance) - **REQUIRES NEW METHODS** (see Issue 26, 27)
- MT5 historical data for BTCUSDc (M5 timeframe) for `corr_vs_btc` (see Issue 28)
- `app/engine/historical_analysis_engine.py` for correlation calculation

**⚠️ CRITICAL FIX (Review Round 2)**:
- `market_indices_service` currently only has `get_dxy()`, `get_us10y()` which return current price, NOT historical bars
- **REQUIRED**: Add `get_dxy_bars()`, `get_us10y_bars()`, `get_sp500_bars()` methods to fetch historical M5 bars
- Use `yfinance` to fetch: `yf.Ticker(symbol).history(period="5d", interval="5m")`
- For BTC correlation: Use MT5 `BTCUSDc` M5 bars (same source as symbol for consistency)

**Integration Point**: `desktop_agent.py` → `tool_analyse_symbol_full` → call before `_format_unified_analysis`

**Files to Modify**:
- `infra/correlation_context_calculator.py` (NEW - async methods)
- `infra/market_indices_service.py` (ADD: `get_dxy_bars()`, `get_us10y_bars()`, `get_sp500_bars()`, `get_sp500()` - all async)
- `desktop_agent.py` (add correlation calculation call in both `tool_analyse_symbol_full` functions - wrap in try-except)

**⚠️ CRITICAL FIX (Review Round 2)**:
- **All calculation methods must be async** (`async def`) since called from async `tool_analyse_symbol_full`
- Use `await asyncio.to_thread()` for blocking calls (MT5, yfinance)
- Parallelize independent calculations: `await asyncio.gather(corr_context, htf_levels, ...)`
- Wrap in try-except for error isolation (don't crash entire analysis)

**⚠️ CRITICAL FIXES**:
- Reuse `HistoricalAnalysisEngine.calculate_correlation()` - don't recreate
- Handle timezone alignment between MT5 and Yahoo Finance data
- Mark data quality clearly (Yahoo Finance can be unreliable)
- Handle missing data gracefully (return `None` for unavailable correlations)

---

### 1.2 Order Flow (Non-BTC) (`order_flow`)

**Status**: ✅ **COMPLETE** - Implementation and tests passing

**Location**: New service: `infra/general_order_flow_metrics.py`

**Implementation**:
```python
class GeneralOrderFlowMetrics:
    def __init__(self, mt5_service=None, order_flow_service=None):
        self.mt5_service = mt5_service
        self.order_flow_service = order_flow_service
        # For proxy calculations (requires symbol_config)
        from app.engine.volume_delta_proxy import VolumeDeltaProxy
        # Create symbol config with defaults
        symbol_config = {
            'delta_threshold': 1.5,
            'delta_lookback_ticks': 100,
            'delta_spike_threshold': 2.0,
            'delta_spike_cooldown_ticks': 50
        }
        self.volume_proxy = VolumeDeltaProxy(symbol_config)
    
    def get_order_flow_metrics(
        self,
        symbol: str,
        window_minutes: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate order flow metrics for non-BTC symbols.
        Uses MT5 tick data or proxy methods.
        
        Returns:
        {
            "cvd_value": 132.5,  # Cumulative volume delta (proxy)
            "cvd_slope": "falling",  # "up", "down", "flat"
            "aggressor_ratio": 0.84,  # buy_vol / sell_vol (proxy)
            "imbalance_score": 30,  # 0-100 (how one-sided)
            "large_trade_count": 2,  # Blocks > X size in N mins (if available)
            "data_quality": "proxy",  # "proxy" | "limited" | "good" | "unavailable"
            "data_source": "mt5_tick_proxy",  # Source of data
            "window_minutes": 30
        }
        """
        # 1. Try to get true order flow (if futures/CFD data available with bid/ask volume)
        # 2. Fallback to proxy: Use MT5 tick data (copy_ticks_from or copy_ticks_range)
        # 3. If tick data unavailable, use VolumeDeltaProxy with price-action proxy
        # 4. Calculate volume delta: delta = tick_direction * volume (for proxy)
        # 5. Calculate CVD: cumulative sum of deltas
        # 6. Calculate CVD slope: Compare last 10 bars (up/down/flat based on ±5% change)
        # 7. Calculate aggressor ratio: buy_volume / sell_volume (proxy: positive_delta / negative_delta)
        # 8. Calculate imbalance score: 0-100 based on delta ratio
        # 9. Mark data quality clearly ("proxy" for tick-based, "limited" if insufficient data)
```

**Data Sources**:
- MT5 tick data (proxy method via `VolumeDeltaProxy`)
- Futures/CFD tick data (if available - check broker)
- Fallback: Price-action based proxy (less accurate)

**Integration Point**: `desktop_agent.py` → `tool_analyse_symbol_full` → call before `_format_unified_analysis`

**Files to Modify**:
- `infra/general_order_flow_metrics.py` (NEW - async methods)
- `desktop_agent.py` (add order flow calculation call - wrap in try-except, parallelize with other calculations)

**⚠️ CRITICAL FIXES**:
- **CRITICAL**: Mark `data_quality: "proxy"` - ChatGPT must understand limitations
- Use existing `VolumeDeltaProxy` for tick-based calculations
- Don't claim "true order flow" if using proxy methods
- Return `None` if data completely unavailable (don't return misleading data)

---

### 1.3 HTF Levels (`htf_levels`)

**Status**: ✅ **COMPLETE** - Implementation and tests passing

**Location**: New service: `infra/htf_levels_calculator.py`

**Implementation**:
```python
class HTFLevelsCalculator:
    def __init__(self, mt5_service=None):
        self.mt5_service = mt5_service
    
    def calculate_htf_levels(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Calculate higher timeframe key levels.
        
        Returns:
        {
            "weekly_open": 4175.0,  # Current week's open (Monday 00:00 UTC)
            "monthly_open": 4120.0,  # Current month's open (1st day 00:00 UTC)
            "previous_week_high": 4225.0,
            "previous_week_low": 4085.0,
            "previous_day_high": 4210.0,  # Align with PDH naming
            "previous_day_low": 4190.0,   # Align with PDL naming
            "range_reference": "weekly_range",  # "weekly_range" | "asia_session_range" | "daily_range"
            "current_price_position": "premium",  # "discount" | "equilibrium" | "premium"
            "discount_threshold": 0.33,  # Bottom 33% of range
            "premium_threshold": 0.66,   # Top 33% of range
            "timezone": "UTC"  # Timezone used for calculations
        }
        """
        # 1. Get MT5 broker timezone: mt5.get_terminal_info().timezone or symbol_info.timezone
        # 2. Fetch D1 bars from MT5 (last 30 days for previous day high/low)
        # 3. Fetch W1 bars from MT5 (last 4 weeks for previous week high/low)
        # 4. Fetch MN1 bars from MT5 (last 3 months for previous month high/low)
        # 5. Convert all timestamps to UTC using broker timezone offset
        # 6. Calculate weekly boundary: Find Monday 00:00 UTC (not broker time)
        # 7. Calculate monthly boundary: Find 1st of month 00:00 UTC
        # 8. Get previous week/month highs/lows from historical bars
        # 9. Calculate current price position in range (discount/equilibrium/premium using 33%/66% thresholds)
        # 10. Determine range reference:
        #     - If price within weekly range: "weekly_range"
        #     - If broke weekly but within daily: "daily_range"
        #     - If broke daily: "session_range" (based on current session)
        #     - Use ATR to validate range is meaningful (range_width > 2*ATR)
        # 11. Convert all datetime objects to ISO strings for JSON serialization
        # 12. Note: Don't reuse existing PDH/PDL logic (it's for M15/M1, not D1/W1/MN1)
```

**Data Sources**:
- MT5 historical data (D1, W1, MN1 timeframes)
- Existing PDH/PDL calculation (reuse logic if available)

**Integration Point**: `desktop_agent.py` → `tool_analyse_symbol_full` → call before `_format_unified_analysis`

**Files to Modify**:
- `infra/htf_levels_calculator.py` (NEW - async methods)
- `desktop_agent.py` (add HTF levels calculation call - wrap in try-except, parallelize with other calculations)

**⚠️ CRITICAL FIXES**:
- Handle timezone conversion (MT5 broker timezone → UTC)
- Calculate weekly boundaries correctly (Monday 00:00 UTC, not just -7 days)
- Calculate monthly boundaries correctly (1st of month 00:00 UTC)
- Align with existing PDH/PDL naming conventions

---

### 1.4 Session Risk (`session_risk`)

**Status**: ✅ **COMPLETE** - Implementation and tests passing

**Location**: Helper function in `infra/session_risk_calculator.py` (NEW)

**Implementation**:
```python
def calculate_session_risk(
    session_info: Dict,
    news_service: NewsService,
    symbol: str,
    current_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Calculate session risk flags and danger zones.
    
    Returns:
    {
        "is_rollover_window": False,  # True during daily rollover (00:00 UTC ±30min)
        "is_news_lock_active": False,  # True if high-impact news in ±30min window
        "minutes_to_next_high_impact": 75,  # Minutes until next HIGH/ULTRA event
        "is_in_high_impact_window": False,  # True if within ±30min of high-impact event
        "session_profile": "normal",  # "quiet" | "normal" | "explosive" (based on historical vol)
        "session_volatility_multiplier": 1.0,  # Historical vol multiplier for this session
        "rollover_window_start": "2025-12-11T00:00:00Z",  # Next rollover time
        "rollover_window_end": "2025-12-11T00:30:00Z"
    }
    """
    # 1. Calculate rollover window: current_time between 00:00 UTC ±30min
    #    - next_rollover = (current_time.date() + timedelta(days=1)).replace(hour=0, minute=0, second=0)
    #    - rollover_start = next_rollover - timedelta(minutes=30)
    #    - rollover_end = next_rollover + timedelta(minutes=30)
    #    - is_rollover_window = rollover_start <= current_time <= rollover_end
    # 2. Check news service for high-impact events:
    #    - events = news_service.get_upcoming_events(limit=10, hours_ahead=24)
    #    - high_impact = [e for e in events if e.get("impact") in ["HIGH", "ULTRA"]]
    #    - if high_impact: next_event = min(high_impact, key=lambda e: e["time"])
    #    - minutes_to_next = (next_event["time"] - current_time).total_seconds() / 60
    #    - is_in_window = abs(minutes_to_next) <= 30
    # 3. Calculate session profile from historical volatility (if available) - default to "normal" if unavailable
    # 4. Return all flags with proper timezone handling (UTC)
```

**Data Sources**:
- `infra/feature_session_news.py` (session info)
- `infra/news_service.py` (upcoming events)
- Historical volatility data (for session profile - may not exist initially)

**Integration Point**: `desktop_agent.py` → `_format_unified_analysis` (already has session/news data)

**Files to Modify**:
- `desktop_agent.py` (add `session_risk` calculation in `_format_unified_analysis` - can be synchronous helper function)

**⚠️ CRITICAL FIXES**:
- Rollover window: 00:00 UTC ±30min (standard FX rollover, not broker time)
- Check `infra/circuit_breaker.py` for existing rollover logic reference
- Session profile may be unavailable initially - return "normal" as default
- Handle missing news data gracefully

---

### 1.5 Execution Context (`execution_context`)

**Status**: ✅ **COMPLETE** - Implementation and tests passing

**Location**: New service: `infra/execution_quality_monitor.py` (wrapper around SpreadTracker)

**Implementation**:
```python
class ExecutionQualityMonitor:
    def __init__(self, mt5_service=None, spread_tracker=None):
        self.mt5_service = mt5_service
        # Reuse existing SpreadTracker
        from infra.spread_tracker import SpreadTracker
        self.spread_tracker = spread_tracker or SpreadTracker()
    
    def get_execution_context(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Monitor spread, slippage, and execution quality.
        
        Returns:
        {
            "current_spread_points": 19,  # Current spread in points
            "spread_vs_median": 2.1,  # Multiple of median spread (e.g., 2.1x)
            "is_spread_elevated": True,  # True if spread_vs_median > 1.5
            "avg_slippage_points": 6,  # Average slippage from last N trades (if available)
            "slippage_vs_normal": 1.8,  # Multiple of normal slippage
            "is_slippage_elevated": True,  # True if slippage_vs_normal > 1.5
            "execution_quality": "degraded",  # "good" | "degraded" | "poor"
            "slippage_sample_size": 10,  # Number of trades used for slippage calc
            "slippage_data_available": True  # False if no trade history
        }
        """
        # 1. Get current spread from MT5: quote.ask - quote.bid
        # 2. Use SpreadTracker.get_spread_data() to get average spread and spread_ratio
        # 3. Add get_median_spread() method to SpreadTracker OR use average (close for large samples)
        # 4. Calculate spread_vs_median: current_spread / median_spread (or average)
        # 5. Query trade history database for slippage (entry_price vs requested_price)
        # 6. If slippage data unavailable, return slippage_data_available: False
        # 7. Calculate execution quality: "good" if spread_vs_median < 1.5 and slippage_vs_normal < 1.5
        # 8. "degraded" if either > 1.5, "poor" if both > 2.0
```

**Data Sources**:
- MT5 symbol info (current spread)
- `infra/spread_tracker.py` (historical spread data)
- Trade history database (for slippage - may not exist initially)

**Integration Point**: `desktop_agent.py` → `tool_analyse_symbol_full` → call before `_format_unified_analysis`

**Files to Modify**:
- `infra/spread_tracker.py` (ADD: `get_median_spread()` method)
- `infra/execution_quality_monitor.py` (NEW - wrapper around SpreadTracker, async methods)
- `desktop_agent.py` (add execution context calculation call - wrap in try-except)

**⚠️ CRITICAL FIXES**:
- **Reuse `SpreadTracker`** - don't recreate spread tracking logic
- Slippage data may not be available initially - return `None` with `slippage_data_available: False`
- Handle missing trade history gracefully
- Use MT5 trade history API if available, otherwise query database

---

### 1.6 Strategy Stats (`strategy_stats`)

**Status**: ✅ **COMPLETE** - Implementation and tests passing

**Location**: Extended `infra/strategy_performance_tracker.py`

**Implementation**:
```python
class StrategyPerformanceTracker:
    # ... existing code ...
    
    def get_strategy_stats_by_regime(
        self,
        symbol: str,
        strategy_name: str,
        current_regime: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get historical performance stats for strategy in similar regime.
        
        Returns:
        {
            "strategy": "INSIDE_BAR_VOLATILITY_TRAP",
            "regime": "stable_vol_range_compression",  # Matched regime
            "sample_size": 47,  # Number of trades in similar regime
            "win_rate": 0.62,  # 0.0 to 1.0
            "avg_rr": 1.9,  # Average risk:reward
            "max_drawdown_rr": -1.3,  # Worst case R:R
            "median_holding_time_minutes": 95,
            "confidence": "high",  # "high" | "medium" | "low" (based on sample size)
            "regime_match_quality": "exact"  # "exact" | "fuzzy" | "approximate"
        }
        OR None if no data available
        """
        # 1. Add regime column to trade_results table if not exists (migration)
        # 2. Define regime mapping: REGIME_MAPPING = {"STABLE": [...], "EXPANDING": [...], ...}
        # 3. Match current_regime to historical regimes (exact → fuzzy → approximate)
        # 4. Query trade_results filtered by strategy + regime (use IN clause for fuzzy matches)
        # 5. Calculate stats from filtered trades: win_rate, avg_rr, max_drawdown_rr, median_holding_time
        # 6. Determine confidence: "high" if exact/fuzzy and sample_size >= 30, "medium" if sample_size >= 10, "low" if < 10
        # 7. Determine regime_match_quality: "exact" if exact match, "fuzzy" if matched via mapping, "approximate" if closest
        # 8. Return None if sample_size < 10 (insufficient data)
```

**Data Sources**:
- `infra/strategy_performance_tracker.py` database (trade history)
- Regime classification from volatility system

**Integration Point**: `desktop_agent.py` → `tool_analyse_symbol_full` → call after strategy selection

**Files to Modify**:
- `infra/strategy_performance_tracker.py` (ADD: `get_strategy_stats_by_regime` method - async, ADD: regime column migration)
- `desktop_agent.py` (add strategy stats call after strategy selection - wrap in try-except)
- Database migration script (ADD: `regime TEXT` column to `trade_results` table)

**⚠️ CRITICAL FIXES**:
- **Extend existing class** - don't create new one
- Add regime matching logic (fuzzy match: "STABLE" → "stable_vol_range_compression")
- Handle cases where no historical data exists (return `None`)
- Require minimum sample size (e.g., 10 trades) for confidence
- Add `regime_match_quality` to indicate how well regime matched

---

### 1.7 Structure Summary (`structure_summary`)

**Status**: ✅ **COMPLETE** - Implementation and tests passing

**Location**: Helper function in `desktop_agent.py` (derive from existing data)

**Implementation**:
```python
def calculate_structure_summary(
    m1_microstructure: Dict,
    smc_data: Dict,
    current_price: float,
    htf_levels: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Create compressed structure interpretation flags.
    
    Returns:
    {
        "current_range_type": "balanced_range",  # "balanced_range" | "trend_channel" | "breakout" | "distribution" | "accumulation"
        "range_state": "mid_range",  # "mid_range" | "near_range_high" | "near_range_low" | "just_broke_range"
        "has_liquidity_sweep": True,
        "sweep_type": "bear",  # "bull" | "bear" | "none"
        "sweep_level": 4188.95,  # Price level if sweep detected
        "discount_premium_state": "seeking_premium_liquidity",  # "seeking_premium_liquidity" | "seeking_discount_liquidity" | "balanced"
        "range_high": 4207.11,  # From M1 microstructure liquidity zones
        "range_low": 4188.96,   # From M1 microstructure liquidity zones
        "range_mid": 4198.04    # Calculated
    }
    """
        # 1. Validate m1_microstructure structure (use safe access with .get())
        # 2. Extract liquidity zones from m1_microstructure.get('liquidity_zones', [])
        # 3. Extract range boundaries: range_high = max(zone['price'] for zone in zones), range_low = min(...)
        # 4. Determine range type from structure (use smc_data.trend and m1_microstructure.structure)
        # 5. Check for liquidity sweeps: m1_microstructure.get('choch_bos', {}).get('sweep_detected', False)
        # 6. Calculate discount/premium state: Compare current_price to range (use htf_levels if available)
        # 7. Determine range state: "mid_range" if 33%-66%, "near_range_high" if >66%, "near_range_low" if <33%
        # 8. "just_broke_range" if price outside range and recent break detected
        # 9. Provide default values if data missing (e.g., "balanced_range", "mid_range")
```

**Data Sources**:
- `m1_microstructure` (already in response)
- `smc` data (already in response)
- `htf_levels` (optional - for range reference)

**Integration Point**: `desktop_agent.py` → `_format_unified_analysis` (use existing data)

**Files to Modify**:
- `desktop_agent.py` (add `structure_summary` calculation in `_format_unified_analysis` - can be synchronous helper function, use safe data access)

**⚠️ CRITICAL FIXES**:
- **Derive from existing data** - no new data fetching needed
- Interpret `m1_microstructure.liquidity_zones` for range boundaries
- Use `m1_microstructure.choch_bos` for sweep detection
- Handle missing data gracefully (return default values)

---

### 1.8 Symbol Constraints (`symbol_constraints`)

**Location**: Configuration file + service: `infra/symbol_constraints_manager.py`

**Implementation**:
```python
class SymbolConstraintsManager:
    def __init__(self, config_path: str = "config/symbol_constraints.json"):
        self.config_path = Path(config_path)
        self.constraints = self._load_constraints()
    
    def _load_constraints(self) -> Dict[str, Dict[str, Any]]:
        """Load constraints from JSON file"""
        if not self.config_path.exists():
            # Return default constraints
            return self._get_default_constraints()
        
        with open(self.config_path, 'r') as f:
            return json.load(f)
    
    def get_symbol_constraints(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Get trading constraints for symbol.
        
        Returns:
        {
            "max_concurrent_trades_for_symbol": 2,
            "max_total_risk_on_symbol_pct": 3.0,  # Max % of account risk on this symbol
            "allowed_strategies": [
                "INSIDE_BAR_VOLATILITY_TRAP",
                "VOLATILITY_REVERSION_SCALP"
            ],
            "risk_profile": "normal",  # "aggressive" | "normal" | "conservative"
            "banned_strategies": ["SWING_TREND_FOLLOWING"],  # Strategies not allowed
            "max_position_size_pct": 5.0  # Max position size as % of account
        }
        """
        # Return symbol-specific constraints or defaults
        # Default constraints (if symbol not in config):
        # {
        #     "max_concurrent_trades_for_symbol": 2,
        #     "max_total_risk_on_symbol_pct": 3.0,
        #     "allowed_strategies": [],  # Empty = all allowed
        #     "risk_profile": "normal",
        #     "banned_strategies": [],
        #     "max_position_size_pct": 5.0
        # }
```

**Data Sources**:
- Configuration file: `config/symbol_constraints.json` (NEW)

**Integration Point**: `desktop_agent.py` → `tool_analyse_symbol_full` → call before `_format_unified_analysis`

**Files to Modify**:
- `config/symbol_constraints.json` (NEW - with default structure documented)
- `infra/symbol_constraints_manager.py` (NEW - with default constraints defined)
- `desktop_agent.py` (add symbol constraints call - wrap in try-except)

**⚠️ CRITICAL FIXES**:
- Provide sensible defaults if config file doesn't exist
- Validate config file structure on load
- Handle missing symbol gracefully (return defaults)

---

### 1.9 Integration into `_format_unified_analysis`

**Status**: ✅ **COMPLETE** - All fields integrated into both instances and calculations added to tool_analyse_symbol_full (both instances)

**Location**: `desktop_agent.py` (BOTH instances: ~line 861 and ~line 6502)

**Implementation**:
```python
def _format_unified_analysis(
    ...
    correlation_context: Optional[Dict[str, Any]] = None,
    order_flow: Optional[Dict[str, Any]] = None,  # Enhanced for non-BTC
    htf_levels: Optional[Dict[str, Any]] = None,
    session_risk: Optional[Dict[str, Any]] = None,
    execution_context: Optional[Dict[str, Any]] = None,
    strategy_stats: Optional[Dict[str, Any]] = None,
    structure_summary: Optional[Dict[str, Any]] = None,
    symbol_constraints: Optional[Dict[str, Any]] = None,
    ...
) -> Dict[str, Any]:
    # ⚠️ CRITICAL: All new parameters are optional with None defaults for backward compatibility
    # ⚠️ CRITICAL: Convert all numpy types and datetime objects to JSON-serializable types
    ...
    return {
        "summary": summary,
        "data": {
            ...
            # NEW FIELDS (all optional - can be None or empty dict)
            "correlation_context": correlation_context or {},
            "order_flow": order_flow or {},  # Enhanced (was BTC-only, now for all)
            "htf_levels": htf_levels or {},
            "session_risk": session_risk or {},
            "execution_context": execution_context or {},
            "strategy_stats": strategy_stats,  # Can be None
            "structure_summary": structure_summary or {},
            "symbol_constraints": symbol_constraints or {},
            ...
        }
    }
```

**Files to Modify**:
- `desktop_agent.py` (update BOTH `_format_unified_analysis` functions - line ~861 and ~6502)

**⚠️ CRITICAL FIXES**:
- **Update BOTH instances** - there are two `_format_unified_analysis` functions (line ~861 and ~6502)
- All new fields are optional (can be `None` or empty dict) - **MUST have None defaults**
- Ensure consistent parameter signatures in both functions
- Update BOTH calls in `tool_analyse_symbol_full` (line ~2688 and ~8332)
- Use keyword arguments when calling to avoid parameter order issues
- Test both code paths and backward compatibility (existing calls without new parameters)
- Convert all return values to JSON-serializable types (no numpy, no datetime objects)

---

## Phase 2: Tool Schema Updates (`openai.yaml`)

**Status**: ✅ **COMPLETE** - Schema documentation updated

**⚠️ CRITICAL**: DO NOT update until Phase 1 is complete and response structure is finalized!

### Tasks

1. **Update `analyseSymbolFull` Tool Description** (Line ~1517-1527)
   - Add section documenting all 9 new data fields
   - Provide example structures with actual field names
   - Explain usage context and interpretation rules
   - **CRITICAL**: Add prominent warnings about data quality indicators
   - **CRITICAL**: Document proxy data limitations for non-BTC symbols
   - Add examples of how ChatGPT should use each field

2. **Add Response Schema Comments** (After line ~1549)
   - Document all 9 new fields in response structure comments
   - Include field types, ranges, and nullability
   - Document data quality values and their meanings
   - Provide example values for each field

3. **Add Data Quality Warnings**
   - Create dedicated section explaining data quality indicators
   - Document when to ignore fields based on data quality
   - Explain proxy vs. true data differences
   - Add examples of proper data quality checking

**Files to Modify**:
- `openai.yaml` (update `analyseSymbolFull` tool description and response schema comments)

**Detailed Update Requirements**:

#### 2.1 Update Tool Description (Line ~1517)

**Add to description after volatility regime section**:
```yaml
description: |
  ...existing volatility regime description...
  
  📊 ENHANCED DATA FIELDS ⭐ NEW - Additional market context for sophisticated analysis:
  
  - correlation_context: Cross-asset correlation analysis (DXY, SP500, US10Y, BTC)
    ⚠️ Use to identify divergences: "Gold normally trades -0.7 vs DXY, but showing -0.2 → underperformance"
    ⚠️ ALWAYS check data_quality before using: "good" = reliable, "limited" = small sample, "unavailable" = ignore field
    ⚠️ conflict_flags indicate when correlations break expected patterns (e.g., gold_vs_dxy_conflict: true)
  
  - order_flow: Volume & order flow signals (CVD, aggressor ratio, imbalance score)
    ⚠️ Use to assess momentum quality: "Structure bullish but CVD rolling over → don't chase"
    ⚠️ CRITICAL: data_quality may be "proxy" for non-BTC symbols - less reliable than true order flow
    ⚠️ For BTC: Uses Binance data (true order flow). For others: Uses MT5 tick proxy (estimated)
    ⚠️ If data_quality == "proxy", use with caution and prefer structure confirmation
  
  - htf_levels: Higher timeframe key levels (weekly/monthly opens, previous week/day highs/lows)
    ⚠️ Use for HTF context: "Inside weekly premium, pushing into prior week high → only shorts if sweep + CHOCH"
    ⚠️ current_price_position: "discount" (bottom 33%), "equilibrium" (middle), "premium" (top 33%)
    ⚠️ range_reference: "weekly_range" | "daily_range" | "session_range" - indicates which range is active
  
  - session_risk: Session & danger zone flags (rollover, news lock, session profile)
    ⚠️ Use for timing: "Setup decent but high-impact news in 15 minutes → skip until after news"
    ⚠️ is_rollover_window: True during 00:00 UTC ±30min (FX daily rollover - avoid trading)
    ⚠️ is_news_lock_active: True if HIGH/ULTRA impact event within ±30min window
    ⚠️ session_profile: "quiet" | "normal" | "explosive" (based on historical volatility, may default to "normal")
  
  - execution_context: Spread, slippage & execution quality metrics
    ⚠️ Use for risk management: "EV positive but spread/slippage elevated → reduce size or no trade"
    ⚠️ execution_quality: "good" (spread/slippage normal), "degraded" (elevated), "poor" (very elevated)
    ⚠️ slippage_data_available: False if no trade history (slippage metrics will be None)
  
  - strategy_stats: Historical strategy performance in similar volatility regimes
    ⚠️ Use for strategy validation: "In this exact regime, this setup wins 62% with ~1.9R; good edge"
    ⚠️ Can be None if no historical data available for current regime (sample_size < 10)
    ⚠️ confidence: "high" (sample_size >= 30), "medium" (>= 10), "low" (< 10)
    ⚠️ regime_match_quality: "exact" | "fuzzy" | "approximate" - indicates how well regime matched
  
  - structure_summary: Compressed structure interpretation flags
    ⚠️ Use for structure interpretation: "Bear sweep at range low → only longs if M5 CHOCH + order-flow confirms"
    ⚠️ current_range_type: "balanced_range" | "trend_channel" | "breakout" | "distribution" | "accumulation"
    ⚠️ range_state: "mid_range" | "near_range_high" | "near_range_low" | "just_broke_range"
    ⚠️ has_liquidity_sweep: True if recent sweep detected (check sweep_type: "bull" | "bear" | "none")
  
  - symbol_constraints: Trading constraints per symbol (max trades, allowed/banned strategies)
    ⚠️ Use to respect limits: "Do not propose swing strategy if it's banned for this symbol"
    ⚠️ allowed_strategies: Empty array = all strategies allowed
    ⚠️ banned_strategies: Array of strategy names not allowed for this symbol
  
  ⚠️ DATA QUALITY RULES - CRITICAL:
  - ALWAYS check data_quality field before using any field value
  - If data_quality == "unavailable", IGNORE the field entirely (do not use in analysis)
  - If data_quality == "limited", use with caution (small sample size or gaps in data)
  - If data_quality == "proxy", understand it's estimated/calculated, not true data (less reliable)
  - If data_quality == "good", data is reliable and can be used with confidence
  - For order_flow: "proxy" means tick-based estimation (non-BTC symbols), "good" means true buy/sell volume (BTC only)
```

#### 2.2 Add Response Schema Comments (After line ~1549)

**Add comprehensive response structure documentation**:
```yaml
# Enhanced Data Fields (response.data.*):
#
# correlation_context: {
#   corr_window_minutes: 240,
#   corr_vs_dxy: -0.72,  # -1 to +1, or None if unavailable
#   corr_vs_sp500: 0.15,
#   corr_vs_us10y: -0.48,
#   corr_vs_btc: 0.05,  # Only for non-BTC symbols
#   conflict_flags: {
#     gold_vs_dxy_conflict: true,  # If correlation breaks expected pattern
#     sp500_divergence: false
#   },
#   data_quality: "good" | "limited" | "unavailable",  # ALWAYS check before using
#   sample_size: 240  # Number of bars used
# }
#
# order_flow: {
#   cvd_value: 132.5,  # Cumulative volume delta (proxy for non-BTC)
#   cvd_slope: "falling",  # "up" | "down" | "flat"
#   aggressor_ratio: 0.84,  # buy_vol / sell_vol (proxy)
#   imbalance_score: 30,  # 0-100 (how one-sided)
#   large_trade_count: 2,  # Blocks > X size (if available)
#   data_quality: "proxy" | "limited" | "good" | "unavailable",  # CRITICAL: "proxy" = less reliable
#   data_source: "mt5_tick_proxy" | "binance_aggtrades",  # Source of data
#   window_minutes: 30
# }
#
# htf_levels: {
#   weekly_open: 4175.0,  # Current week's open (Monday 00:00 UTC)
#   monthly_open: 4120.0,  # Current month's open (1st day 00:00 UTC)
#   previous_week_high: 4225.0,
#   previous_week_low: 4085.0,
#   previous_day_high: 4210.0,  # Aligns with PDH naming
#   previous_day_low: 4190.0,   # Aligns with PDL naming
#   range_reference: "weekly_range" | "asia_session_range" | "daily_range",
#   current_price_position: "premium",  # "discount" | "equilibrium" | "premium"
#   discount_threshold: 0.33,  # Bottom 33% of range
#   premium_threshold: 0.66,   # Top 33% of range
#   timezone: "UTC"  # Timezone used for calculations
# }
#
# session_risk: {
#   is_rollover_window: false,  # True during daily rollover (00:00 UTC ±30min)
#   is_news_lock_active: false,  # True if high-impact news in ±30min window
#   minutes_to_next_high_impact: 75,  # Minutes until next HIGH/ULTRA event
#   is_in_high_impact_window: false,  # True if within ±30min of high-impact event
#   session_profile: "normal",  # "quiet" | "normal" | "explosive" (may default to "normal" if historical data unavailable)
#   session_volatility_multiplier: 1.0,  # Historical vol multiplier for this session
#   rollover_window_start: "2025-12-11T00:00:00Z",  # Next rollover time
#   rollover_window_end: "2025-12-11T00:30:00Z"
# }
#
# execution_context: {
#   current_spread_points: 19,  # Current spread in points
#   spread_vs_median: 2.1,  # Multiple of median spread (e.g., 2.1x)
#   is_spread_elevated: true,  # True if spread_vs_median > 1.5
#   avg_slippage_points: 6,  # Average slippage from last N trades (if available)
#   slippage_vs_normal: 1.8,  # Multiple of normal slippage
#   is_slippage_elevated: true,  # True if slippage_vs_normal > 1.5
#   execution_quality: "degraded",  # "good" | "degraded" | "poor"
#   slippage_sample_size: 10,  # Number of trades used for slippage calc
#   slippage_data_available: true  # False if no trade history
# }
#
# strategy_stats: {
#   strategy: "INSIDE_BAR_VOLATILITY_TRAP",
#   regime: "stable_vol_range_compression",  # Matched regime
#   sample_size: 47,  # Number of trades in similar regime
#   win_rate: 0.62,  # 0.0 to 1.0
#   avg_rr: 1.9,  # Average risk:reward
#   max_drawdown_rr: -1.3,  # Worst case R:R
#   median_holding_time_minutes: 95,
#   confidence: "high",  # "high" | "medium" | "low" (based on sample size)
#   regime_match_quality: "exact"  # "exact" | "fuzzy" | "approximate"
# } OR None if no data available
#
# structure_summary: {
#   current_range_type: "balanced_range",  # "balanced_range" | "trend_channel" | "breakout" | "distribution" | "accumulation"
#   range_state: "mid_range",  # "mid_range" | "near_range_high" | "near_range_low" | "just_broke_range"
#   has_liquidity_sweep: true,
#   sweep_type: "bear",  # "bull" | "bear" | "none"
#   sweep_level: 4188.95,  # Price level if sweep detected
#   discount_premium_state: "seeking_premium_liquidity",  # "seeking_premium_liquidity" | "seeking_discount_liquidity" | "balanced"
#   range_high: 4207.11,  # From M1 microstructure liquidity zones
#   range_low: 4188.96,   # From M1 microstructure liquidity zones
#   range_mid: 4198.04    # Calculated
# }
#
# symbol_constraints: {
#   max_concurrent_trades_for_symbol: 2,
#   max_total_risk_on_symbol_pct: 3.0,  # Max % of account risk on this symbol
#   allowed_strategies: [
#     "INSIDE_BAR_VOLATILITY_TRAP",
#     "VOLATILITY_REVERSION_SCALP"
#   ],
#   risk_profile: "normal",  # "aggressive" | "normal" | "conservative"
#   banned_strategies: ["SWING_TREND_FOLLOWING"],  # Strategies not allowed
#   max_position_size_pct: 5.0  # Max position size as % of account
# }
```

#### 2.3 Add Data Quality Section (New section after response schema)

**Add dedicated data quality documentation**:
```yaml
# ⚠️ DATA QUALITY INDICATORS - CRITICAL RULES:
#
# All enhanced data fields include a "data_quality" field (where applicable) with standardized values:
# - "good": High-quality data, reliable, can be used with confidence
# - "limited": Some data available but sample size small or gaps present - use with caution
# - "proxy": Estimated/calculated data, less reliable than true data - use with caution and prefer structure confirmation
# - "unavailable": No data available - IGNORE the field entirely, do not use in analysis
#
# MANDATORY CHECKING RULES:
# 1. ALWAYS check data_quality before using any field value
# 2. If data_quality == "unavailable", do NOT use the field in analysis or reasoning
# 3. If data_quality == "limited", acknowledge uncertainty and use with caution
# 4. If data_quality == "proxy", understand limitations and prefer structure confirmation
# 5. If data_quality == "good", data is reliable and can be used with confidence
#
# FIELD-SPECIFIC QUALITY NOTES:
# - correlation_context: "limited" if <80% data overlap, "unavailable" if <50% overlap
# - order_flow: "proxy" for non-BTC symbols (tick-based estimation), "good" for BTC (Binance true order flow)
# - strategy_stats: Can be None if sample_size < 10 (insufficient data for confidence)
# - execution_context: slippage_data_available: false if no trade history (slippage metrics will be None)
# - session_risk: session_profile may default to "normal" if historical volatility data unavailable
```

**⚠️ CRITICAL FIXES (Review Round 2)**:
- **DO NOT update until Phase 1 is complete** - response structure must be finalized first
- Test actual response structure before documenting
- Ensure all field names match actual implementation
- Include prominent warnings about data quality checking
- Document proxy data limitations clearly
- Provide concrete usage examples for each field

---

## Phase 3: Knowledge Document Updates

**Status**: ✅ **COMPLETE** - All knowledge documents updated with comprehensive Enhanced Data Fields documentation

**⚠️ CRITICAL**: Update knowledge documents AFTER Phase 1 and Phase 2 are complete!

### Documents to Update

1. **1.KNOWLEDGE_DOC_EMBEDDING.md** (Core Knowledge Document)
   - **Add new section**: "Enhanced Data Fields Usage"
   - Document data quality checking rules (MANDATORY)
   - Add correlation interpretation guidelines
   - Add order flow interpretation guidelines (proxy vs. true data)
   - Document when to ignore fields based on data quality
   - Add examples of cross-field reasoning
   - **CRITICAL**: Emphasize checking `data_quality` before using any field

2. **2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md** (General Instructions)
   - **Add new section**: "Enhanced Data Fields Analysis Behavior"
   - Document mandatory data quality checks
   - Add interpretation examples for each field
   - Document cross-field reasoning patterns
   - Add examples of proper vs. improper usage
   - **CRITICAL**: Add rule: "NEVER use field if data_quality == 'unavailable'"

3. **10.SMC_MASTER_EMBEDDING.md** (Smart Money Concepts)
   - **Add section**: "Structure Summary Integration"
   - Document how `structure_summary` complements SMC analysis
   - Explain HTF levels integration with SMC structure
   - Add correlation context rules for SMC setups
   - Document when correlation conflicts invalidate SMC signals
   - Add examples: "Structure bullish but correlation conflict → wait"

4. **13.GOLD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md** (Gold-Specific)
   - **Add section**: "Enhanced Data Fields for Gold"
   - Document correlation context for XAUUSD:
     - Expected correlations: DXY (-0.7), US10Y (-0.5), SP500 (+0.2)
     - Conflict detection: If actual correlation deviates >0.3 from expected
     - Usage: "Gold should move inverse to DXY - if not, investigate"
   - Document execution quality considerations (spread can be wide)
   - Add symbol constraints (if any specific to Gold)
   - Document HTF levels usage for Gold (weekly/monthly ranges)
   - **CRITICAL**: Emphasize checking correlation conflicts before trade decisions

5. **14.BTCUSD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md** (BTC-Specific)
   - **Add section**: "Enhanced Data Fields for BTC"
   - Document enhanced order flow (already has BTC-specific, but clarify it's "good" quality)
   - Add correlation context:
     - Expected correlations: SP500 (+0.6), DXY (-0.3), US10Y (+0.1)
     - Usage: "BTC often follows SP500 - check correlation before trading"
   - Add strategy stats usage (regime-based performance)
   - Document execution quality (spread typically tight for BTC)
   - **CRITICAL**: Clarify that BTC order flow is "good" quality (true Binance data)

6. **15.FOREX_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md** (Forex-Specific)
   - **Add section**: "Enhanced Data Fields for Forex"
   - Add correlation context for FX pairs:
     - EURUSD: DXY (-0.9), US10Y (-0.4), SP500 (+0.3)
     - Usage: "EURUSD strongly inverse to DXY - check correlation"
   - Document execution quality (spread varies by pair and session)
   - Add session risk interpretation:
     - Rollover window: Avoid trading during 00:00 UTC ±30min
     - News lock: Skip trades if high-impact within ±30min
   - Document HTF levels usage (weekly/monthly ranges important for FX)
   - **CRITICAL**: Emphasize session risk for FX (rollover and news timing)

7. **6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md** (Auto-Execution Instructions)
   - **Add section**: "Enhanced Data Fields for Plan Validation"
   - Document using new fields for plan validation:
     - Check `correlation_context.conflict_flags` - if conflicts, warn user
     - Check `execution_context.execution_quality` - if "poor", warn or reject
     - Check `session_risk.is_news_lock_active` - if true, warn about timing
     - Check `symbol_constraints.banned_strategies` - reject if strategy banned
   - Add correlation conflict checks:
     - "If gold_vs_dxy_conflict: true, warn user about unusual correlation"
   - Add execution quality filters:
     - "If execution_quality == 'poor', warn user about elevated spread/slippage"
   - Add symbol constraints validation:
     - "Check symbol_constraints.allowed_strategies - only propose allowed strategies"
     - "Check symbol_constraints.banned_strategies - never propose banned strategies"

8. **7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md** (Auto-Execution Knowledge)
   - **Add section**: "Enhanced Data Fields for Plan Management"
   - Document strategy stats usage:
     - "Use strategy_stats to validate strategy selection"
     - "If win_rate < 0.5 and sample_size >= 10, consider alternative strategy"
     - "If confidence == 'low', acknowledge uncertainty in recommendation"
   - Add symbol constraints validation:
     - "Respect max_concurrent_trades_for_symbol limit"
     - "Respect max_total_risk_on_symbol_pct limit"
   - Add session risk checks:
     - "If is_rollover_window: true, warn user about rollover risk"
     - "If is_news_lock_active: true, warn user about news timing"
   - Document HTF levels for invalidation:
     - "If price breaks htf_levels.previous_week_high/low, invalidate range-based plans"
     - "Use htf_levels.current_price_position to adjust entry zones"

**Files to Modify**:
- All knowledge documents listed above

**⚠️ CRITICAL FIXES (Review Round 2)**:
- **Update timing**: Only update AFTER Phase 1 and Phase 2 are complete
- **Data quality emphasis**: Every document must emphasize checking `data_quality` before using fields
- **Proxy data warnings**: Clearly explain proxy vs. true data differences
- **Usage examples**: Include concrete examples of proper vs. improper usage
- **Cross-field reasoning**: Document how to combine multiple fields for analysis
- **Error handling**: Document what to do when fields are unavailable or have poor quality

---

## Phase 4: Testing & Validation

**Status**: ✅ **COMPLETE** - All tests passing, enhanced data fields validated end-to-end

### Test Types

1. **Unit Tests**
   - Test each new calculator/service independently
   - Validate data structure correctness
   - Test edge cases and null handling
   - Test data quality indicators

2. **Integration Tests**
   - Test full data flow from calculation to response
   - Validate all fields appear in `analyse_symbol_full` response
   - Test with real symbols (XAUUSD, BTCUSD, EURUSD)
   - Test both `_format_unified_analysis` code paths

3. **ChatGPT Integration Tests**
   - Verify ChatGPT can access all new fields
   - Test interpretation and usage in analysis
   - Validate cross-field reasoning
   - Test data quality handling

4. **Performance Tests**
   - Ensure calculation time is acceptable (<500ms per field)
   - Test concurrent calls
   - Validate memory usage
   - Test caching effectiveness

**Test Files Created**:
- ✅ `tests/test_correlation_context_calculator.py` - Unit tests passing
- ✅ `tests/test_general_order_flow_metrics.py` - Unit tests passing
- ✅ `tests/test_htf_levels_calculator.py` - Unit tests passing
- ✅ `tests/test_execution_quality_monitor.py` - Unit tests passing
- ✅ `tests/test_strategy_performance_tracker_regime.py` - Unit tests passing
- ✅ `tests/test_session_risk_calculator.py` - Unit tests passing
- ✅ `tests/test_structure_summary.py` - Unit tests passing
- ✅ `tests/test_symbol_constraints_manager.py` - Unit tests passing
- ✅ `tests/test_enhanced_data_fields_integration.py` - Integration test created
- ✅ `test_enhanced_fields_validation.py` - Validation script created (manual testing)

**Status**:
- ✅ All unit tests created and passing
- ✅ Integration test file created
- ✅ Validation script created for manual testing
- ⏳ Ready for end-to-end validation with real symbols

---

## Implementation Order (Recommended)

### Week 1: Core Infrastructure
1. **Day 1**: Phase 0 (Data Structure Design)
2. **Day 2-3**: Correlation Context (1.1) - Reuse existing correlation calc
3. **Day 4-5**: HTF Levels (1.3) - Handle timezone correctly

### Week 2: Order Flow & Risk
1. **Day 1-2**: Order Flow (Non-BTC) (1.2) - Mark as proxy clearly
2. **Day 3**: Session Risk (1.4) - Use 00:00 UTC rollover
3. **Day 4-5**: Execution Context (1.5) - Reuse SpreadTracker

### Week 3: Strategy & Structure
1. **Day 1-2**: Strategy Stats (1.6) - Extend existing tracker
2. **Day 3**: Structure Summary (1.7) - Derive from existing data
3. **Day 4**: Symbol Constraints (1.8) - Simple config
4. **Day 5**: Integration into `_format_unified_analysis` (1.9) - **BOTH instances**

### Week 4: Documentation & Testing
1. **Day 1-2**: Phase 2 (openai.yaml updates)
2. **Day 3-4**: Phase 3 (Knowledge document updates)
3. **Day 5**: Phase 4 (Testing & validation)

---

## Dependencies & Prerequisites

### Existing Services Required
- ✅ `infra/market_indices_service.py` (for DXY, SP500, US10Y)
- ✅ `infra/news_service.py` (for news events)
- ✅ `infra/feature_session_news.py` (for session info)
- ✅ `infra/btc_order_flow_metrics.py` (reference for non-BTC implementation)
- ✅ `infra/spread_tracker.py` (for execution context)
- ✅ `infra/strategy_performance_tracker.py` (extend for regime filtering)
- ✅ `app/engine/historical_analysis_engine.py` (for correlation calculation)
- ✅ `app/engine/volume_delta_proxy.py` (for proxy order flow)
- ✅ MT5 connection (for historical data, spread, tick data)

### New Services to Create
- `infra/correlation_context_calculator.py`
- `infra/general_order_flow_metrics.py`
- `infra/htf_levels_calculator.py`
- `infra/execution_quality_monitor.py` (wrapper around SpreadTracker)
- `infra/symbol_constraints_manager.py`

### Configuration Files
- `config/symbol_constraints.json` (NEW)

### Database Considerations
- **REQUIRED**: Add `regime TEXT` column to `trade_results` table (migration needed)
- **REQUIRED**: Start storing volatility regime when recording trades
- **OPTIONAL**: Trade history storage for slippage tracking (if not already implemented)
- **OPTIONAL**: Historical volatility database for session profile (can be built over time)

---

## Success Criteria

1. ✅ All 9 new data fields appear in `analyse_symbol_full` response
2. ✅ All fields have correct data types and structures
3. ✅ All fields include data quality indicators where applicable
4. ✅ ChatGPT can access and interpret all fields
5. ✅ Knowledge documents updated with usage guidelines
6. ✅ Tool schema (`openai.yaml`) documents all fields with data quality warnings
7. ✅ All tests pass (unit, integration, ChatGPT integration)
8. ✅ Performance impact < 500ms per field calculation
9. ✅ No breaking changes to existing response structure
10. ✅ Both `_format_unified_analysis` functions updated consistently

---

## Notes & Considerations

### Data Availability
- Some fields may have limited data (e.g., order flow for non-BTC symbols)
- Use `data_quality` flags to indicate availability and reliability
- Provide fallback values or null handling
- **CRITICAL**: ChatGPT must understand data quality limitations

### Performance
- **Caching Strategy**:
  - Correlation context: Cache key = `(symbol, window_minutes)` - TTL 5 minutes
  - HTF levels: Cache key = `symbol` - TTL 1 hour (levels change daily/weekly/monthly)
  - Strategy stats: Cache key = `(symbol, strategy_name, regime)` - TTL 1 hour
  - Order flow: Cache key = `(symbol, window_minutes)` - TTL 30 seconds (changes frequently)
  - Execution context: Cache key = `symbol` - TTL 10 seconds (spread changes frequently)
  - Session risk: Cache key = `(symbol, current_time_hour)` - TTL 5 minutes
- Use thread-safe caching (similar to confluence cache implementation)
- **CRITICAL**: All calculation methods must be async (`async def`)
- Use `await asyncio.to_thread()` for blocking calls (MT5, yfinance)
- Parallelize independent calculations: `await asyncio.gather(corr_context, htf_levels, execution_context, ...)`
- **Target**: Total additional time < 2 seconds for all 9 fields combined
- Profile each calculation and optimize slowest ones first

### Backward Compatibility
- All new fields are optional (can be `null` or empty dict)
- Existing response structure unchanged
- Existing fields remain in same locations
- Graceful degradation if services unavailable

### Data Quality Indicators
- **CRITICAL**: Always include `data_quality` field where applicable
- **Standardized values** (use consistently across all fields):
  - `"good"`: High-quality data, reliable
  - `"limited"`: Some data available but sample size small or gaps present
  - `"proxy"`: Estimated/calculated data, less reliable than true data
  - `"unavailable"`: No data available, field should be ignored
- ChatGPT must check data quality before using field
- Document in knowledge docs what each quality level means
- If `data_quality == "unavailable"`, ChatGPT should ignore the field entirely

---

## Review Checklist

Before starting implementation, verify:
- [ ] All existing services identified and understood
- [ ] Data source limitations documented
- [ ] Timezone handling clarified
- [ ] Both `_format_unified_analysis` functions identified
- [ ] Data quality indicators planned for all fields
- [ ] ChatGPT usage patterns documented
- [ ] Test strategy defined
- [ ] Performance targets set

---

**Next Steps**: Begin Phase 0 (Data Structure Design) to create detailed type definitions and validate approach.

---

**Status**: ✅ **PLAN REVIEWED & FIXED** - Ready for implementation

---

## 🔍 REVIEW ROUND 1: ADDITIONAL CRITICAL ISSUES IDENTIFIED

### Issue 10: HistoricalAnalysisEngine Instantiation ⚠️
**Problem**: Plan shows `HistoricalAnalysisEngine()` instantiated without required `symbol_config` parameter.

**Fix**: 
- `HistoricalAnalysisEngine.__init__` requires `symbol_config: Dict[str, Any]`
- **Solution**: Use `HistoricalAnalysisEngine.calculate_correlation()` as static method directly (it's `@staticmethod`)
- No need to instantiate the class - just call the static method with two numpy arrays
- Convert price data to returns before calling: `returns = np.diff(prices) / prices[:-1]`

### Issue 11: VolumeDeltaProxy Instantiation ⚠️
**Problem**: Plan shows `VolumeDeltaProxy()` instantiated without required `symbol_config` parameter.

**Fix**:
- `VolumeDeltaProxy.__init__` requires `symbol_config: Dict[str, Any]`
- **Solution**: Create symbol config dict: `{'delta_threshold': 1.5, 'delta_lookback_ticks': 100, 'delta_spike_threshold': 2.0, 'delta_spike_cooldown_ticks': 50}`
- Or use default values from `config/symbol_config.py` if available

### Issue 12: SpreadTracker Median Calculation ⚠️
**Problem**: Plan references `get_median_spread()` but `SpreadTracker` only has `get_average_spread()`.

**Fix**:
- **Option 1**: Add `get_median_spread()` method to `SpreadTracker` class
- **Option 2**: Use `get_average_spread()` (average ≈ median for large samples)
- **Option 3**: Use `get_spread_data().spread_ratio` which is `current / average` - can calculate `current / median` if median added
- **Recommended**: Add `get_median_spread()` for accuracy (median is more robust to outliers)

### Issue 13: Strategy Stats Database Schema ⚠️
**Problem**: `trade_results` table doesn't have `regime` column for filtering.

**Fix**:
- Add database migration: `ALTER TABLE trade_results ADD COLUMN regime TEXT`
- When recording trades, store volatility regime at trade time
- For existing trades: Query volatility history by timestamp to infer regime (fuzzy matching)
- Regime matching: Define explicit mapping (e.g., "STABLE" → ["stable_vol_range_compression", "stable_vol_trending", "STABLE"])

### Issue 14: Slippage Data Availability ⚠️
**Problem**: Plan assumes slippage data exists, but may not be tracked.

**Fix**:
- Verify if trade history includes slippage (entry_price vs requested_price)
- If unavailable, return `slippage_data_available: False` and skip slippage calculations
- Execution quality can still be calculated from spread alone
- Future enhancement: Start tracking slippage for new trades

### Issue 15: HTF Levels PDH/PDL Alignment ⚠️
**Problem**: Existing PDH/PDL calculations use M15/M1 timeframes, but HTF levels need D1/W1/MN1.

**Fix**:
- Don't reuse existing PDH/PDL logic (it's for different timeframe)
- Fetch D1 bars from MT5 for daily levels
- Fetch W1 bars for weekly levels
- Fetch MN1 bars for monthly levels
- Calculate boundaries correctly (Monday 00:00 UTC for weekly, 1st of month for monthly)

### Issue 16: Session Profile Historical Data ⚠️
**Problem**: Session profile calculation requires historical volatility data which may not exist.

**Fix**:
- If historical volatility unavailable, return `session_profile: "normal"` as default
- `session_volatility_multiplier: 1.0` as default
- Future enhancement: Build historical volatility database over time
- For now, focus on rollover window and news lock flags (which don't require historical data)

### Issue 17: Structure Summary Data Validation ⚠️
**Problem**: Plan assumes `m1_microstructure` has specific fields, but structure may vary.

**Fix**:
- Verify `m1_microstructure` structure before accessing fields
- Use safe access: `m1_microstructure.get('liquidity_zones', [])`
- Provide default values if fields missing
- Test with actual `m1_microstructure` data structure

### Issue 18: Symbol Constraints Config Reuse ⚠️
**Problem**: Plan creates new config file, but existing symbol configs may exist.

**Fix**:
- Check if `config/symbol_config.py` or `config/symbol_constraints.json` already exists
- Reuse existing config structure if compatible
- Merge with existing symbol-specific settings
- Provide sensible defaults for symbols not in config

### Issue 19: Correlation Window Size Validation ⚠️
**Problem**: Plan uses 240 minutes (4 hours) window, but may not have enough data.

**Fix**:
- Validate minimum window size: Require at least 48 bars (4 hours of M5 data)
- If insufficient data, reduce window or return `data_quality: "limited"`
- For shorter windows, correlation may be less reliable
- Document minimum sample size requirement (e.g., 30 bars minimum)

### Issue 20: Order Flow CVD Calculation ⚠️
**Problem**: Plan mentions CVD but doesn't specify how to calculate cumulative sum.

**Fix**:
- CVD = cumulative sum of volume delta: `cvd[i] = sum(delta[0:i])`
- For proxy: Use tick direction * volume as delta proxy
- Calculate CVD slope: Compare last N values (e.g., last 10 bars)
- Slope classification: "up" if increasing, "down" if decreasing, "flat" if stable (±5% change)

### Issue 21: Timezone Handling for HTF Levels ⚠️
**Problem**: MT5 uses broker timezone, but weekly/monthly boundaries need UTC.

**Fix**:
- Get MT5 broker timezone: `mt5.symbol_info(symbol).timezone` or `mt5.get_terminal_info().timezone`
- Convert all timestamps to UTC before calculating boundaries
- Weekly boundary: Find Monday 00:00 UTC (not broker time)
- Monthly boundary: Find 1st of month 00:00 UTC
- Use `datetime` with `timezone.utc` for all calculations

### Issue 22: Regime Matching Logic Definition ⚠️
**Problem**: Plan mentions "fuzzy matching" but doesn't define the mapping.

**Fix**:
- Define explicit regime mapping dictionary:
  ```python
  REGIME_MAPPING = {
      "STABLE": ["stable_vol_range_compression", "stable_vol_trending", "STABLE"],
      "EXPANDING": ["expanding_vol_breakout", "expanding_vol_trending", "EXPANDING"],
      "CONTRACTING": ["contracting_vol_squeeze", "contracting_vol_range", "CONTRACTING"]
  }
  ```
- Match quality: "exact" if exact match, "fuzzy" if matched via mapping, "approximate" if closest match
- Confidence: "high" if exact/fuzzy, "medium" if approximate, "low" if sample_size < 10

### Issue 23: Performance Caching Strategy ⚠️
**Problem**: Plan mentions caching but doesn't specify cache keys and invalidation.

**Fix**:
- Correlation context: Cache key = `(symbol, window_minutes)` - TTL 5 minutes
- HTF levels: Cache key = `symbol` - TTL 1 hour (levels change daily/weekly/monthly)
- Strategy stats: Cache key = `(symbol, strategy_name, regime)` - TTL 1 hour
- Order flow: Cache key = `(symbol, window_minutes)` - TTL 30 seconds (changes frequently)
- Execution context: Cache key = `symbol` - TTL 10 seconds (spread changes frequently)
- Use thread-safe caching (similar to confluence cache implementation)

### Issue 24: Error Handling and Fallbacks ⚠️
**Problem**: Plan doesn't specify error handling for service failures.

**Fix**:
- If MT5 connection fails: Return `None` or empty dict with `data_quality: "unavailable"`
- If Yahoo Finance API fails: Return `None` for that correlation, mark others as available
- If database query fails: Return `None` for strategy stats, log error
- If calculation fails: Return default values, log warning
- Never crash `analyse_symbol_full` - always return partial data if possible

### Issue 25: Integration Order Dependencies ⚠️
**Problem**: Some fields depend on others (e.g., `structure_summary` uses `htf_levels`).

**Fix**:
- Calculate independent fields first: `correlation_context`, `order_flow`, `htf_levels`, `session_risk`, `execution_context`, `symbol_constraints`
- Then calculate dependent fields: `structure_summary` (uses `htf_levels`), `strategy_stats` (uses strategy selection)
- If dependency unavailable, use `None` or default values
- Document dependencies clearly in implementation

---

**Status**: ✅ **PLAN REVIEWED & FIXED (Round 1)** - All critical issues addressed

---

## 🔍 REVIEW ROUND 2: ADDITIONAL CRITICAL ISSUES IDENTIFIED

### Issue 26: Market Indices Service - Historical Data Missing ⚠️
**Problem**: `market_indices_service.get_dxy()` and `get_us10y()` only return current price, not historical bars needed for correlation.

**Fix**:
- **CRITICAL**: Add new methods to `MarketIndicesService`:
  - `get_dxy_bars(period: str = "5d", interval: str = "5m") -> pd.DataFrame` - Returns historical bars
  - `get_us10y_bars(period: str = "5d", interval: str = "5m") -> pd.DataFrame` - Returns historical bars
  - `get_sp500_bars(period: str = "5d", interval: str = "5m") -> pd.DataFrame` - Returns historical bars (SP500 not currently supported)
- Use `yfinance` to fetch historical data: `yf.Ticker(symbol).history(period=period, interval=interval)`
- Return DataFrame with columns: `['time', 'open', 'high', 'low', 'close', 'volume']`
- Align with MT5 M5 bars (5-minute intervals)

### Issue 27: SP500 Data Source Missing ⚠️
**Problem**: Plan mentions SP500 correlation but `market_indices_service` doesn't have `get_sp500()` method.

**Fix**:
- Add `get_sp500()` method to `MarketIndicesService` using `yfinance` with symbol `"^GSPC"` or `"SPY"`
- Add `get_sp500_bars()` for historical data
- Cache SP500 data similar to DXY/VIX/US10Y (15-minute cache)

### Issue 28: BTC Historical Data Source ⚠️
**Problem**: Plan mentions `corr_vs_btc` for non-BTC symbols but doesn't specify data source.

**Fix**:
- **Option 1 (Recommended)**: Use MT5 `BTCUSDc` historical bars (M5 timeframe) - same source as symbol
- **Option 2**: Use Binance historical data via `yfinance` with symbol `"BTC-USD"`
- **Decision**: Use MT5 for consistency and alignment (same broker, same timezone)
- If MT5 unavailable, fallback to Binance via `yfinance`

### Issue 29: News Service Minutes Calculation ⚠️
**Problem**: Plan references `minutes_to_next_high_impact` but `news_service.get_upcoming_events()` returns list, not calculated minutes.

**Fix**:
- `NewsService.get_upcoming_events()` returns list of events with `time` field
- Calculate `minutes_to_next_high_impact`:
  ```python
  high_impact = [e for e in events if e.get("impact") in ["HIGH", "ULTRA"]]
  if high_impact:
      next_event = min(high_impact, key=lambda e: e["time"])
      minutes = (next_event["time"] - current_time).total_seconds() / 60
  ```
- Verify `news_service.get_upcoming_events()` returns events with `time` as datetime object
- Handle timezone correctly (ensure UTC)

### Issue 30: Async/Await Requirements ⚠️
**Problem**: Plan doesn't specify if calculations should be async (MT5 and Yahoo Finance calls can be slow).

**Fix**:
- **All new calculation methods should be async** (`async def`)
- Use `await` for MT5 calls: `await asyncio.to_thread(mt5_service.get_bars, ...)`
- Use `await` for Yahoo Finance calls: `await asyncio.to_thread(yf.Ticker(...).history, ...)`
- `tool_analyse_symbol_full` is already async - all calculations called from it should be async
- Parallelize independent calculations: `await asyncio.gather(corr_context, htf_levels, execution_context)`

### Issue 31: Parameter Passing to `_format_unified_analysis` ⚠️
**Problem**: Adding 9 new optional parameters might cause issues if not all calls are updated.

**Fix**:
- **All 9 new parameters MUST be optional** with `Optional[Dict[str, Any]] = None` default
- Update BOTH `_format_unified_analysis` function signatures (line ~861 and ~6502)
- Update BOTH calls in `tool_analyse_symbol_full` (line ~2688 and ~8332)
- Test that existing calls without new parameters still work (backward compatibility)
- Use keyword arguments when calling to avoid parameter order issues

### Issue 32: Data Type Serialization ⚠️
**Problem**: Return values may contain numpy types, datetime objects, or other non-JSON-serializable types.

**Fix**:
- Convert all numpy types to native Python: `float(corr_value)` instead of `np.float64`
- Convert datetime to ISO string: `dt.isoformat()` or `dt.strftime("%Y-%m-%dT%H:%M:%SZ")`
- Convert numpy arrays to lists: `array.tolist()`
- Test JSON serialization: `json.dumps(result)` should not raise errors
- Use `json.dumps(result, default=str)` as fallback for edge cases

### Issue 33: Correlation Window Size vs Data Availability ⚠️
**Problem**: 240 minutes (4 hours) window may not have enough data during low-liquidity periods.

**Fix**:
- Validate minimum data requirement: Require at least 48 bars (4 hours of M5 data)
- If insufficient data, reduce window to available data or return `data_quality: "limited"`
- For "limited" quality: Require at least 24 bars (2 hours) for any correlation calculation
- Document minimum sample size in response: `sample_size` field shows actual bars used
- If `sample_size < 24`, return `data_quality: "unavailable"` and `corr_vs_*: None`

### Issue 34: Conflict Detection Logic Definition ⚠️
**Problem**: Plan mentions "conflict_flags" but doesn't define expected correlation patterns.

**Fix**:
- Define expected correlation patterns:
  ```python
  EXPECTED_CORRELATIONS = {
      "XAUUSD": {"dxy": -0.7, "us10y": -0.5, "sp500": 0.2},  # Gold
      "BTCUSD": {"dxy": -0.3, "sp500": 0.6, "us10y": 0.1},  # Bitcoin
      "EURUSD": {"dxy": -0.9, "us10y": -0.4, "sp500": 0.3},  # EUR
  }
  ```
- Conflict detection: If actual correlation deviates >0.3 from expected, flag as conflict
- Example: Gold vs DXY expected -0.7, actual -0.2 → `gold_vs_dxy_conflict: True`
- Only flag conflicts for symbols with defined expected correlations

### Issue 35: Rollover Window Calculation Logic ⚠️
**Problem**: Plan mentions 00:00 UTC ±30min but doesn't specify exact calculation.

**Fix**:
- Calculate rollover window: `current_time` between `00:00 UTC - 30min` and `00:00 UTC + 30min`
- Next rollover: `next_rollover = (current_time.date() + timedelta(days=1)).replace(hour=0, minute=0, second=0)`
- Window: `rollover_start = next_rollover - timedelta(minutes=30)`, `rollover_end = next_rollover + timedelta(minutes=30)`
- Check: `is_rollover_window = rollover_start <= current_time <= rollover_end`
- Use UTC timezone for all calculations: `datetime.now(timezone.utc)`

### Issue 36: Session Profile Calculation Missing ⚠️
**Problem**: Plan mentions "session_profile" based on historical volatility but doesn't specify calculation.

**Fix**:
- If historical volatility database unavailable, return defaults:
  - `session_profile: "normal"`
  - `session_volatility_multiplier: 1.0`
- Future enhancement: Build historical volatility database over time
- For now, focus on rollover and news flags (which don't require historical data)
- Document that session profile will be enhanced in future update

### Issue 37: Order Flow Aggressor Ratio Calculation ⚠️
**Problem**: Plan mentions `aggressor_ratio = buy_vol / sell_vol` but for proxy methods, buy/sell volume is estimated.

**Fix**:
- For proxy methods: `buy_vol = sum(volume for tick where direction > 0)`, `sell_vol = sum(volume for tick where direction < 0)`
- If no tick data: Use price-action proxy: `buy_vol = sum(volume where price_change > 0)`, `sell_vol = sum(volume where price_change < 0)`
- Handle division by zero: If `sell_vol == 0`, return `aggressor_ratio: None` or `aggressor_ratio: float('inf')` with flag
- Mark clearly in response: `data_quality: "proxy"` indicates estimated values

### Issue 38: HTF Levels Range Reference Logic ⚠️
**Problem**: Plan mentions "range_reference" but doesn't specify how to determine weekly vs daily vs session.

**Fix**:
- Determine range reference based on current market state:
  - If price within weekly range (previous_week_low to previous_week_high): `"weekly_range"`
  - If price broke weekly range but within daily range: `"daily_range"`
  - If price broke daily range: `"session_range"` or `"asia_session_range"` (based on current session)
- Use ATR to determine if range is meaningful (range_width > 2*ATR)
- Default to `"daily_range"` if unable to determine

### Issue 39: Strategy Stats Regime Storage Timing ⚠️
**Problem**: Plan mentions storing regime when recording trades, but doesn't specify when regime is captured.

**Fix**:
- Capture volatility regime **at trade entry time** (not exit time)
- Store regime in `trade_results` table when trade is opened
- For existing trades without regime: Query volatility history by `entry_time` timestamp
- Use volatility regime detector to infer regime from historical data if not stored
- Regime should match the regime that existed when trade decision was made

### Issue 40: Symbol Constraints Default Values ⚠️
**Problem**: Plan mentions defaults but doesn't specify what they should be.

**Fix**:
- Define sensible defaults:
  ```python
  DEFAULT_CONSTRAINTS = {
      "max_concurrent_trades_for_symbol": 2,
      "max_total_risk_on_symbol_pct": 3.0,
      "allowed_strategies": [],  # Empty = all allowed
      "risk_profile": "normal",
      "banned_strategies": [],
      "max_position_size_pct": 5.0
  }
  ```
- Per-symbol overrides in config file override defaults
- If symbol not in config, return defaults
- Validate config file structure on load (catch JSON errors)

### Issue 41: Integration Call Order and Error Isolation ⚠️
**Problem**: If one field calculation fails, should it fail entire analysis or just return None?

**Fix**:
- **Error isolation**: Each field calculation should be wrapped in try-except
- If calculation fails, log warning and return `None` or empty dict for that field
- Never crash `tool_analyse_symbol_full` - always return partial data
- Example: If correlation calculation fails, return `correlation_context: {}` and continue
- Log all errors with context: `logger.warning(f"Correlation calculation failed for {symbol}: {e}")`
- Return partial response with available fields

### Issue 42: Performance Impact Assessment ⚠️
**Problem**: Plan mentions <500ms per field but doesn't account for cumulative impact.

**Fix**:
- Calculate total time: 9 fields × 500ms = 4.5 seconds maximum (unacceptable)
- **Optimization required**:
  - Parallelize independent calculations: `await asyncio.gather(...)`
  - Use caching aggressively (5min-1hr TTL depending on field)
  - Batch MT5 calls where possible (fetch multiple timeframes in one call)
  - Use async Yahoo Finance calls (non-blocking)
- Target: Total additional time < 2 seconds for all 9 fields combined
- Profile each calculation and optimize slowest ones first

### Issue 43: Backward Compatibility Testing ⚠️
**Problem**: Plan doesn't specify how to ensure existing code still works.

**Fix**:
- **All new fields are optional** - existing code should work without changes
- Test that `_format_unified_analysis` works with all new parameters as `None`
- Test that `tool_analyse_symbol_full` works if new calculations are disabled
- Test that response structure is backward compatible (existing fields unchanged)
- Test that ChatGPT can handle responses with missing new fields (graceful degradation)

### Issue 44: Data Quality Indicator Consistency ⚠️
**Problem**: Different fields use different data quality values ("good", "limited", "proxy", "unavailable").

**Fix**:
- Standardize data quality values across all fields:
  - `"good"`: High-quality data, reliable
  - `"limited"`: Some data available but sample size small or gaps present
  - `"proxy"`: Estimated/calculated data, less reliable than true data
  - `"unavailable"`: No data available, field should be ignored
- Document in knowledge docs what each quality level means
- ChatGPT should check `data_quality` before using field values

### Issue 45: Correlation Returns Calculation Edge Cases ⚠️
**Problem**: Converting prices to returns can fail if prices are zero or negative.

**Fix**:
- Validate prices before conversion: `if any(p <= 0 for p in prices): return None`
- Handle division by zero: `returns = np.diff(prices) / prices[:-1]` - check `prices[:-1] != 0`
- Handle NaN/Inf: Filter out NaN and Inf values before correlation
- Minimum price requirement: Require at least 10 non-zero prices for valid returns
- If validation fails, return `corr_vs_*: None` with `data_quality: "unavailable"`

---

**Status**: ✅ **PLAN REVIEWED & FIXED (Round 2)** - All additional critical issues addressed

