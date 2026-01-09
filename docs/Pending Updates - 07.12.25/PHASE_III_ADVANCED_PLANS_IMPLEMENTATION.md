# Phase III Advanced Plans Implementation Plan

**Date**: 2026-01-07  
**Last Updated**: 2026-01-07  
**Status**: Planning Phase (Optimized + Reviewed + Fixed + Critical/Major Review)  
**Priority**: High (Institutional-Grade Features)  
**Version**: 2.3 (Optimized + Reviewed + Fixed + Critical/Major Review)

---

## 📋 Executive Summary

This document outlines the system requirements and implementation plan to enable monitoring and execution of Phase III Advanced Plan Classes. These plans represent institutional-grade algorithmic trading strategies that require enhanced condition checking, correlation tracking, order flow analysis, and adaptive plan management.

**⚠️ IMPORTANT**: This plan has been reviewed three times and all identified issues have been fixed. See `PHASE_III_PLAN_REVIEW_AND_FIXES.md`, `PHASE_III_PLAN_REVIEW_SECOND_PASS.md`, and `PHASE_III_PLAN_REVIEW_CRITICAL_MAJOR.md` for detailed review findings and fixes applied. All 38 issues (13 Critical, 12 High Priority, 13 Medium Priority) have been integrated into this implementation plan.

### 🔧 Key Fixes Applied

**Critical Fixes (13)**:
1. ✅ Multi-timeframe conditions: Use individual TF conditions with internal validation
2. ✅ Time-based exits: Moved to trade management system (not plan conditions)
3. ✅ Dynamic plan conversion: Uses execution state with proper locking
4. ✅ Adaptive SL modifications: Moved to trade management system
5. ✅ Data source specifications: Added with graceful degradation
6. ✅ Pattern history database: Complete schema design added
7. ✅ Condition logic definitions: Added confirmation definitions for all conditions
8. ✅ Error handling: Added timeout and retry specifications
9. ✅ Condition dependencies: Added validation logic
10. ✅ Database migration strategy: Added migration scripts, rollback, testing
11. ✅ Auto-execution integration: Added status checks, atomic operations
12. ✅ Complete execution state schema: Added full schema with indexes, constraints
13. ✅ Rollback/recovery mechanisms: Added recovery procedures for all failure scenarios

**High Priority Fixes (12)**:
14. ✅ Spoof detection: Uses snapshot comparison method
15. ✅ Cache invalidation: Comprehensive strategy added
16. ✅ Thread safety: Locking specifications for all new features
17. ✅ Multi-TF batch fetching: Batch strategy implemented
18. ✅ Pre-news level tracking: Tracking mechanism added
19. ✅ Momentum tracking: Data retention strategy added
20. ✅ Condition check order: Optimized for early exit
21. ✅ Thresholds: Default threshold values added
22. ✅ Data alignment: Multi-TF alignment specifications added
23. ✅ Cache consistency: Versioning and coherency strategy added
24. ✅ Execution state persistence: Database schema and recovery added
25. ✅ Partial condition handling: Required/optional condition logic added

**Medium Priority Fixes (13)**:
26. ✅ Imbalance direction: Logic clarified
27. ✅ RMAG calculation: Details added
28. ✅ Breaker retest tracking: Mechanism added
29. ✅ News type integration: Service integration details added
30. ✅ State persistence: Database persistence added
31. ✅ Support level detection: Specification added
32. ✅ Stall detection: Specification added
33. ✅ Pullback detection: Specification added
34. ✅ Database pooling: Connection pool configuration added
35. ✅ Integration points: Service integration specifications added
36. ✅ Monitoring/alerting: Comprehensive alerting beyond performance added
37. ✅ Atomic operations: Atomic operation specifications added
38. ✅ Backward compatibility: Compatibility strategy added

### 📋 Review Documents
- **First Review**: `PHASE_III_PLAN_REVIEW_AND_FIXES.md` - Identified 18 issues (6 Critical, 7 High, 5 Medium)
- **Second Review**: `PHASE_III_PLAN_REVIEW_SECOND_PASS.md` - Identified 12 additional issues (3 Critical, 5 High, 4 Medium)
- **Critical/Major Review**: `PHASE_III_PLAN_REVIEW_CRITICAL_MAJOR.md` - Identified 8 additional issues (4 Critical, 4 Major)
- **Total Issues Found**: 38 issues across all reviews
- **All Issues Fixed**: ✅ 38/38 fixes integrated into this plan

**Target Impact**: 5-15% improvement in precision and recovery efficiency through:
- Cross-market correlation awareness
- Advanced order flow microstructure analysis
- Volatility pattern recognition
- Multi-timeframe confluence filtering
- Adaptive scenario handling
- Predictive momentum models

---

## 🎯 Plan Categories & Requirements

### 1️⃣ Cross-Market Correlation & Hedging Plans

**Purpose**: Trade BTC relative to DXY, NASDAQ, and ETH — using correlation shifts to trigger entries/exits.

#### Required System Capabilities

1. **Correlation Condition Checking** (FIXED: Added data source specifications)
   - ✅ **Current Status**: Correlation context calculator exists (`infra/correlation_context_calculator.py`)
   - ✅ **Current Status**: Market indices service exists (`infra/market_indices_service.py`)
   - ❌ **Missing**: Direct correlation condition checks in `_check_conditions()`
   - ❌ **Missing**: DXY percentage change tracking
   - ❌ **Missing**: ETH/BTC ratio deviation calculation
   - ❌ **Missing**: NASDAQ 15-minute trend detection

2. **New Conditions to Support**
   ```python
   # DXY Inverse Flow Plan
   "dxy_change_pct": 0.3,  # DXY > +0.3% change
   "dxy_stall_detected": true,  # DXY momentum stalls
   "btc_hold_above_support": true,  # BTC holds above support level
   
   # ETH/BTC Divergence Tracker
   "ethbtc_ratio_deviation": 1.5,  # Deviation in standard deviations
   "ethbtc_divergence_direction": "bullish" | "bearish"
   
   # NASDAQ Risk-On Bridge
   "nasdaq_15min_bullish": true,  # NASDAQ 15-min trend bullish
   "nasdaq_correlation_confirmed": true  # Correlation alignment confirmed
   ```

3. **Implementation Tasks** (FIXED: Added data source specs and graceful degradation)
   - [ ] **Data Source Requirements** (NEW):
     - ETH price: Use Binance API (ETHUSDT) or MT5 if available
       - Fallback: Use BTC price correlation as proxy if ETH data unavailable
     - NASDAQ: Use market indices service (`infra/market_indices_service.py`)
       - Fallback: Use SP500 as proxy (if NASDAQ unavailable)
       - Graceful degradation: Skip condition if data unavailable (log warning)
     - BTC OI: Use futures data API (if available)
       - Fallback: Skip condition if data unavailable (not critical)
     - **Graceful degradation**: If data unavailable, skip condition check (log warning, don't block execution)
   - [ ] Add correlation condition checks to `auto_execution_system.py::_check_conditions()`
   - [ ] Enhance `correlation_context_calculator.py` to calculate:
     - DXY percentage change over rolling window (use market indices service)
     - ETH/BTC ratio and deviation from mean (calculate from price data)
     - NASDAQ 15-minute trend (bullish/bearish) - use market indices service
   - [ ] Add DXY stall detection (FIXED: Added specification):
     - Track DXY momentum over rolling window (10-20 periods)
     - Calculate momentum slope (linear regression)
     - Detect deceleration: Slope becomes negative or drops >50% from peak
     - Time window: Last 30-60 minutes (6-12 M5 bars)
     - Cache stall detection (2-5 minute TTL)
   - [ ] Add BTC support level detection (FIXED: Added specification):
     - Support definition: Recent swing low (last 20-50 bars) > Order block > VWAP
     - Hold definition: Price > support by 0.1% (or 0.2 ATR), not broken below in last 10-20 bars
     - Hold duration: Minimum 5-10 bars
     - Tolerance: Allow small wicks below support (<0.1 ATR) if price recovers quickly
   - [ ] Create correlation condition validation logic (FIXED: Added dependency validation):
     - Validate data availability before checking conditions
     - Return False if data unavailable (graceful degradation)
     - Log warnings for missing data sources
     - **Condition Dependencies**: `nasdaq_correlation_confirmed` requires `nasdaq_15min_bullish` to be true
     - **Default Thresholds**: `dxy_change_pct` default 0.3%, `ethbtc_ratio_deviation` default 1.5 std dev
     - **Partial Condition Handling**: If DXY available but ETH not, skip ETH conditions, proceed with DXY

---

### 2️⃣ Advanced Order Flow Reaction Plans (Smart Tape Logic)

**Purpose**: React to live order book microstructure instead of static price triggers.

#### Required System Capabilities

1. **Order Flow Microstructure Analysis**
   - ✅ **Current Status**: Order flow service exists (`infra/order_flow_service.py`)
   - ✅ **Current Status**: Order book depth stream exists (`infra/binance_depth_stream.py`)
   - ✅ **Current Status**: Absorption zones detected (`absorption_zone_detected`)
   - ✅ **Current Status**: Delta tracking (`delta_positive`, `delta_negative`)
   - ❌ **Missing**: Imbalance detection
   - ❌ **Missing**: Spoof detection (FIXED: Use snapshot comparison method)
   - ❌ **Missing**: Bid/ask rebuild speed tracking

2. **New Conditions to Support** (FIXED: Clarified imbalance direction logic)
   ```python
   # Absorption → Momentum Flip (FIXED: Added confirmation definition)
   "absorption_zone_detected": true,  # ✅ Already supported
   "delta_positive": true,  # ✅ Already supported
   "momentum_flip_confirmed": true,  # NEW: Price reverses direction AND delta/CVD flips within 2-5 minutes
   
   # Imbalance + Spoof Trap (FIXED: Clarified direction logic)
   "imbalance_detected": true,  # NEW: Order book imbalance detected
   "imbalance_direction": "buy",  # NEW: Buy-side imbalance (more bid volume than ask)
   "imbalance_direction": "sell",  # NEW: Sell-side imbalance (more ask volume than bid)
   "spoof_detected": true,  # NEW: Spoofing activity detected (via snapshot comparison)
   
   # Liquidity Rebuild Plan (FIXED: Added confirmation definition and thresholds)
   "bid_rebuild_speed": 0.5,  # NEW: Bid rebuild rate (orders/sec, default threshold: 0.5)
   "ask_decay_speed": 0.3,  # NEW: Ask decay rate (orders/sec, default threshold: 0.3)
   "liquidity_rebuild_confirmed": true  # NEW: bid_rebuild_speed > ask_decay_speed by >0.2 orders/sec for >30 seconds
   ```

3. **Implementation Tasks** (FIXED: Added snapshot-based spoof detection)
   - [ ] Enhance `infra/order_flow_analyzer.py` to detect:
     - Order book imbalances (bid/ask volume ratio) - use existing depth stream
     - Spoofing patterns (FIXED: Use snapshot comparison method)
       - Compare order book snapshots (every 1-2 seconds)
       - Detect large orders (>threshold) that disappear quickly (<5 seconds)
       - This is a proxy for spoofing (not perfect but workable)
     - Bid/ask rebuild/decay speeds (track depth changes over time)
   - [ ] Add imbalance detection to order flow metrics:
     - Calculate bid/ask volume ratio from depth stream
     - Detect significant imbalance (>threshold, e.g., 1.5:1 ratio)
     - Cache imbalance calculation (30-60 second TTL)
   - [ ] Add spoof detection algorithm (FIXED: Snapshot comparison):
     - Store order book snapshots (last 5-10 snapshots)
     - Compare snapshots to detect disappearing large orders
     - Calculate cancellation rate (orders disappearing per second)
     - Cache spoof detection (1-2 minute TTL)
   - [ ] Add bid/ask rebuild speed calculation:
     - Track depth changes over time (last 10-20 seconds)
     - Calculate rebuild/decay rate (orders per second)
     - Cache speed calculations (30-60 second TTL)
   - [ ] Add condition checks to `_check_conditions()` for (FIXED: Added dependency validation):
     - `imbalance_detected` (with direction)
     - `imbalance_direction` (requires `imbalance_detected: true`)
     - `spoof_detected`
     - `bid_rebuild_speed` / `ask_decay_speed` (default thresholds: 0.5 and 0.3 orders/sec)
     - `liquidity_rebuild_confirmed` (rebuild > decay by >0.2 for >30 seconds)
     - **Condition Dependencies**: `imbalance_direction` requires `imbalance_detected: true`
     - **Default Thresholds**: Imbalance threshold 1.5:1 ratio, spoof detection >$10k order disappearing <5 seconds

---

### 3️⃣ Volatility Pattern Recognition & Breakout Regime Plans

**Purpose**: Detect and trade volatility fractals — mathematical volatility expansions and traps.

#### Required System Capabilities

1. **Volatility Pattern Detection**
   - ✅ **Current Status**: BB squeeze/expansion detection exists
   - ✅ **Current Status**: Inside bar detection exists
   - ✅ **Current Status**: RMAG tracking exists (RMAG analysis in advanced features)
   - ❌ **Missing**: Consecutive inside bar pattern detection
   - ❌ **Missing**: Volatility fractal expansion detection
   - ❌ **Missing**: IV collapse detection (implied volatility)
   - ❌ **Missing**: Volatility recoil pattern detection

2. **New Conditions to Support**
   ```python
   # Volatility Fractal Expansion (FIXED: Added confirmation definition and thresholds)
   "consecutive_inside_bars": 3,  # NEW: Number of consecutive inside bars (default: 3)
   "bb_width_expansion": true,  # ✅ Already supported
   "volatility_fractal_expansion": true,  # NEW: BB width expands >20% AND ATR increases >15% within 3-5 bars
   
   # Volatility Recoil (FIXED: Added confirmation definition)
   "iv_collapse_detected": true,  # NEW: Implied volatility collapse
   "volatility_recoil_confirmed": true,  # NEW: IV/ATR collapses >30% then rebounds >15% within 5-10 bars
   "mean_reversion_target": 0.5,  # Mean reversion target (ATR multiple)
   
   # Impulse Continuation (R-MAG) (FIXED: Added RMAG calculation and confirmation)
   "rmag_atr_ratio": 5.0,  # NEW: RMAG > +5 ATR (default threshold: 5.0)
   "bb_width_rising": true,  # NEW: BB width increasing
   "impulse_continuation_confirmed": true  # NEW: RMAG >5 ATR AND BB width rising for 3+ bars
   ```

3. **Implementation Tasks** (FIXED: Added RMAG calculation details)
   - [ ] Add consecutive inside bar pattern detection to `_check_conditions()`
   - [ ] Enhance volatility state detection to identify:
     - Volatility fractal expansion (compression → expansion pattern)
     - IV collapse (if VIX data available, or use ATR collapse as proxy)
     - Volatility recoil (expansion → mean reversion)
   - [ ] Add RMAG ATR ratio calculation (FIXED: Added details):
     - Get RMAG from advanced features (already available in `advanced.rmag`)
     - Get ATR from M5 or M15 timeframe (use existing ATR calculation)
     - Calculate ratio: `rmag_atr_ratio = RMAG / ATR`
     - Cache calculation (1-2 minute TTL)
     - Use existing RMAG calculation from advanced features
   - [ ] Add BB width trend detection (rising/falling):
     - Track BB width over time (last 10-20 periods)
     - Calculate trend (slope of BB width)
     - Detect rising/falling trend
   - [ ] Create volatility pattern recognition module:
     - Cache pattern detection results (2-5 minute TTL)
     - Use lazy evaluation (only check when volatility conditions exist)

---

### 4️⃣ Institutional Signature Detection Plans

**Purpose**: Identify and follow "footprints" of algorithmic or institutional participation.

#### Required System Capabilities

1. **Pattern Sequence Detection** (FIXED: Added database schema and thread safety)
   - ✅ **Current Status**: Individual OB/FVG/Breaker detection exists
   - ❌ **Missing**: Multiple overlapping OB detection (cascade)
   - ❌ **Missing**: FVG + imbalance combination detection
   - ❌ **Missing**: Breaker retest chain detection (sequence tracking)
   - ❌ **Missing**: Database schema for pattern history (FIXED: Added below)

2. **New Conditions to Support**
   ```python
   # Mitigation Cascade (FIXED: Added confirmation definition and thresholds)
   "mitigation_block": true,  # ✅ Already supported
   "overlapping_obs_count": 3,  # NEW: Number of overlapping order blocks (default: 3)
   "mitigation_cascade_confirmed": true,  # NEW: 3+ overlapping OBs detected within 1 hour window
   
   # Liquidity Vacuum Refill
   "fvg_bull": true,  # ✅ Already supported
   "fvg_bear": true,  # ✅ Already supported
   "imbalance_detected": true,  # NEW: Order flow imbalance
   "liquidity_vacuum_refill": true,  # NEW: FVG + imbalance combo
   
   # Breaker Retest Chain (FIXED: Added confirmation definition and thresholds)
   "breaker_block": true,  # ✅ Already supported
   "breaker_retest_count": 2,  # NEW: Number of retests (default: 2, FIXED: Added tracking)
   "breaker_retest_chain_confirmed": true  # NEW: 2+ retests of broken OB within 1 hour, price holds above/below
   ```

3. **Implementation Tasks** (FIXED: Added database schema, thread safety, retest tracking)
   - [ ] **Database Schema Changes** (NEW):
     - Create `pattern_history` table:
       ```sql
       CREATE TABLE pattern_history (
           pattern_id TEXT PRIMARY KEY,
           symbol TEXT NOT NULL,
           pattern_type TEXT NOT NULL,  -- "mitigation_cascade", "breaker_chain", etc.
           pattern_data TEXT NOT NULL,  -- JSON: pattern details
           detected_at TEXT NOT NULL,  -- ISO format timestamp (consistent with trade_plans schema)
           expires_at TEXT NOT NULL  -- ISO format timestamp (consistent with trade_plans schema)
       );
       CREATE INDEX idx_pattern_symbol ON pattern_history(symbol);
       CREATE INDEX idx_pattern_type ON pattern_history(pattern_type);
       CREATE INDEX idx_pattern_detected ON pattern_history(detected_at);
       ```
     - Add cleanup job: Remove patterns >24 hours old (run every hour)
   - [ ] Add sequence/pattern tracking to detection systems:
     - Track overlapping order blocks (mitigation cascade)
       - Store in pattern_history with pattern_type="mitigation_cascade"
       - Track OB detection events per symbol
       - Count overlapping OBs within time window (e.g., 1 hour)
     - Track FVG + imbalance combinations (liquidity vacuum)
       - Store in pattern_history with pattern_type="liquidity_vacuum"
       - Track FVG detection + imbalance detection events
       - Validate both conditions occur within time window
     - Track breaker retest sequences (chain detection) (FIXED: Added tracking)
       - Track breaker block detection events per symbol
       - Track price retests of broken OB zones
       - Count consecutive retests (within time window, e.g., 1 hour)
       - Reset count if price moves away significantly (>2x ATR)
       - Store in pattern_history with pattern_type="breaker_chain"
   - [ ] Enhance `infra/detection_systems.py` to support:
     - Pattern history tracking (with database persistence)
     - Sequence validation (check pattern history)
     - Cascade detection (query pattern history)
     - Thread safety (use `threading.RLock()` for pattern history access)
   - [ ] Add condition checks for (FIXED: Added dependency validation):
     - `overlapping_obs_count` (query pattern_history, default threshold: 3)
     - `mitigation_cascade_confirmed` (check pattern_history, requires `mitigation_block: true`)
     - `liquidity_vacuum_refill` (check pattern_history, requires both `fvg_bull/bear` and `imbalance_detected`)
     - `breaker_retest_count` (query pattern_history, default threshold: 2, requires `breaker_block: true`)
     - `breaker_retest_chain_confirmed` (check pattern_history, requires `breaker_block: true`)
     - **Condition Dependencies**: `overlapping_obs_count` requires `mitigation_block: true`, `breaker_retest_count` requires `breaker_block: true`

---

### 5️⃣ Multi-Timeframe Confluence & Confirmation Plans

**Purpose**: Execute only when structure aligns across multiple TFs (M1–H1).

#### Required System Capabilities

1. **Multi-Timeframe Condition Checking**
   - ✅ **Current Status**: Single timeframe condition checks exist
   - ❌ **Missing**: Multi-timeframe CHOCH/BOS sync detection
   - ❌ **Missing**: M1 pullback confirmation
   - ❌ **Missing**: HTF FVG alignment across timeframes

2. **New Conditions to Support** (FIXED: Use individual TF conditions approach)
   ```python
   # M5–M15 CHOCH Sync (FIXED: Use individual TF conditions, system validates internally)
   "choch_bull_m5": true,  # NEW: CHOCH on M5 (system validates both M5 and M15)
   "choch_bull_m15": true,  # NEW: CHOCH on M15 (required if M5 specified)
   # System automatically validates both are true (sync check is internal)
   
   # M15 BOS + M1 Pullback (FIXED: Added pullback definition)
   "bos_bear_m15": true,  # NEW: BOS on M15
   "m1_pullback_confirmed": true,  # NEW: Price retraces 30-50% of structure break move within 10-20 M1 bars, then bounces
   
   # HTF FVG Align Plan
   "fvg_bull_m30": true,  # NEW: FVG on M30
   "choch_bull_m5": true,  # NEW: CHOCH on M5 (system validates alignment)
   # System automatically validates multi-TF alignment when multiple TF conditions exist
   ```

3. **Implementation Tasks** (FIXED: Added batch fetching and thread safety)
   - [ ] Create `_fetch_multi_timeframe_data()` method for batch fetching (FIXED: Added data alignment):
     - Fetch all required TFs in parallel (use asyncio or threading)
     - **Timestamp Alignment**: Align all TFs to same reference time (use M5 as base, use candle close times)
     - **Missing Data Handling**: If one TF missing, skip multi-TF validation, log warning
     - **Data Freshness**: Check all TFs have data within last 5 minutes, if stale use cached data
     - **Alignment Algorithm**: Find common time window, align to M5 boundaries, validate >80% overlap
     - Cache multi-TF data together (shared cache key)
     - Return dict: {"M5": candles, "M15": candles, "M30": candles}
     - Reuse cached data across plans checking same TFs
   - [ ] Enhance `_check_conditions()` to support multi-timeframe checks:
     - Add timeframe suffix to conditions (e.g., `choch_bull_m5`, `choch_bull_m15`)
     - Add multi-timeframe validation logic (validate all specified TFs are aligned)
     - Add M1 pullback detection (price retracement after structure break)
   - [ ] Add thread safety for multi-TF data access:
     - Use `threading.RLock()` for multi-TF cache access
     - Use plan-level locks for concurrent plan checks
     - Lock order: Plan lock → Cache lock (prevent deadlocks)
   - [ ] Create multi-timeframe alignment validator:
     - Check structure alignment across specified timeframes
     - Validate confluence across timeframes
     - Confirm pullback patterns on lower timeframes
   - [ ] Add condition checks for (FIXED: Added dependency validation):
     - `choch_bull_m5`, `choch_bull_m15` (individual TF conditions, system validates both if both specified)
     - `m1_pullback_confirmed` (requires structure break first, then retracement 30-50%)
     - `fvg_bull_m30`, `fvg_bear_m30` (HTF FVG conditions)
     - **Condition Dependencies**: Multi-TF conditions require all specified TFs to be available
     - **Partial Availability**: If some TFs available, check available TFs only; if required TF missing, return False

---

### 6️⃣ Smart "Adaptive Scenario" Plans

**Purpose**: Handle unusual conditions automatically (weekend, news shock, liquidity gap).

#### Required System Capabilities

1. **Conditional Plan Modifications** (FIXED: Separated plan conditions from trade management)
   - ✅ **Current Status**: News blackout checking exists
   - ✅ **Current Status**: Session detection exists
   - ❌ **Missing**: Strategy pause/resume (news absorption filter)
   - ❌ **Missing**: Post-news reclaim detection
   - ⚠️ **FIXED**: Weekend SL tightening moved to trade management (not plan condition)
   - ⚠️ **FIXED**: SL modifications require trade modification, not plan modification

2. **New Features to Support** (FIXED: Separated plan conditions from trade management)
   ```python
   # News Absorption Filter Plan (Plan Condition - blocks execution)
   "news_absorption_filter": true,  # NEW: Pause breakout strategies during news
   "news_blackout_window": 15,  # NEW: Minutes pre/post news
   "high_impact_news_types": ["CPI", "FOMC"],  # NEW: News types to filter
   
   # Post-News Reclaim Plan (FIXED: Added confirmation definitions)
   "post_news_reclaim": true,  # NEW: Enable post-news logic
   "price_reclaim_confirmed": true,  # NEW: Price returns to within 0.1% of pre-news level (or 0.5 ATR)
   "cvd_flip_confirmed": true  # NEW: CVD slope changes from negative to positive (or vice versa) with >0.3 strength
   
   # Weekend Auto-Tighten (MOVED TO TRADE MANAGEMENT - not plan condition)
   # This is handled by Universal SL/TP Manager after trade execution
   # Configuration in trade management system, not plan conditions
   ```

3. **Implementation Tasks** (FIXED: Added pre-news tracking and state persistence)
   - [ ] Add strategy pause/resume system (plan condition):
     - Check news blackout with type filtering
     - Pause plan execution if news absorption filter enabled
     - Resume after news window passes
   - [ ] Add post-news reclaim detection (plan condition):
     - Track pre-news price level (store when news detected, 15 min before)
     - Store in plan metadata or separate news tracking table
     - Track per symbol (multiple plans can use same level)
     - Expire after news event completes (24 hours)
     - Check price reclaim and CVD flip conditions
   - [ ] Enhance news service integration:
     - Add news type filtering (CPI, FOMC, etc.) - map event titles to types
     - Use news impact level (HIGH, MEDIUM, LOW) from news service
     - Add pre/post news window management
     - Cache news events (5-10 minute TTL)
   - [ ] Add BTC open interest tracking (if data source available):
     - Use futures data API if available
     - Graceful degradation: Skip condition if data unavailable
   - [ ] Create adaptive plan manager with state persistence:
     - Store adaptive plan state in database (new table or plan metadata)
     - Track: modification type, applied_at, original_value, modified_value
     - Load state on system startup
     - Revert modifications if plan expires or is cancelled
   - [ ] **MOVED TO TRADE MANAGEMENT**: Weekend SL tightening:
     - Implement in Universal SL/TP Manager (not plan conditions)
     - Check VIX < 16, BTC OI drop
     - Modify existing trades via MT5 API
     - Apply to specific strategies only

---

### 7️⃣ Predictive Momentum & Time-Based Models

**Purpose**: Use "momentum aging" & time decay to time entries/exits more precisely.

#### Required System Capabilities

1. **Momentum Aging & Time Decay** (FIXED: Separated entry conditions from exit management)
   - ✅ **Current Status**: RSI/MACD tracking exists
   - ✅ **Current Status**: Tick rate tracking exists
   - ❌ **Missing**: Momentum decay detection (for entry conditions)
   - ⚠️ **FIXED**: Time-based exits moved to trade management (not plan condition)
   - ⚠️ **FIXED**: Dynamic plan conversion uses execution state (not plan conditions)

2. **New Features to Support** (FIXED: Separated entry vs exit features)
   ```python
   # Momentum Decay Trap (FIXED: Added confirmation definition)
   "momentum_decay_trap": true,  # NEW: Enable momentum decay detection
   "rsi_divergence_detected": true,  # NEW: RSI divergence from price
   "macd_divergence_detected": true,  # NEW: MACD divergence
   "tick_rate_declining": true,  # NEW: Tick rate declining
   "momentum_decay_confirmed": true  # NEW: RSI/MACD divergence detected AND tick rate declines >20% for >5 minutes
   
   # Time-Decay Scalper (MOVED TO TRADE MANAGEMENT - not plan condition)
   # This is handled by Universal SL/TP Manager after trade execution
   # Monitors executed trades, not pending plans
   
   # Adaptive Trailing Breaker (MOVED TO EXECUTION STATE - not plan condition)
   # Uses execution state tracking, not plan condition modification
   ```

3. **Implementation Tasks** (FIXED: Added momentum tracking and execution state)
   - [ ] Add momentum decay detection (for plan entry conditions):
     - Store RSI/MACD values over time (last 20-50 periods)
     - Calculate divergence: Compare price trend vs indicator trend
     - Track tick rate over rolling window (last 5-10 minutes)
     - Detect decline: Compare current rate vs average rate
     - Cache momentum calculations (1-2 minute TTL)
     - Trigger plan cancellation if decay confirmed (for decay trap plans)
   - [ ] Create momentum aging tracker:
     - Monitor momentum indicators over time
     - Detect decay patterns
     - Store in pattern history (expires after 1 hour)
   - [ ] **MOVED TO TRADE MANAGEMENT**: Time-based exit conditions:
     - Implement in Universal SL/TP Manager (monitors executed trades)
     - Track trade execution time and unrealized gain
     - Auto-close when time/R:R conditions met
     - Separate monitoring loop (not part of plan condition checking)
   - [ ] **MOVED TO EXECUTION STATE**: Dynamic plan conversion (FIXED: Added persistence and complete schema):
     - Use execution state tracking (not plan condition modification)
     - Store trailing mode in plan.execution_state (not plan.conditions)
     - **Complete Database Schema** (FIXED: Added full schema):
       ```sql
       CREATE TABLE plan_execution_state (
           plan_id TEXT PRIMARY KEY,
           symbol TEXT NOT NULL,
           trailing_mode_enabled INTEGER DEFAULT 0,  -- SQLite uses INTEGER for BOOLEAN (0/1)
           trailing_activation_rr REAL DEFAULT 0.0,
           current_rr REAL DEFAULT 0.0,
           state_data TEXT,  -- JSON: additional state
           updated_at TEXT NOT NULL,  -- ISO format timestamp (consistent with trade_plans schema)
           created_at TEXT NOT NULL,  -- ISO format timestamp (consistent with trade_plans schema)
           FOREIGN KEY (plan_id) REFERENCES trade_plans(plan_id) ON DELETE CASCADE
       );
       CREATE INDEX idx_exec_state_symbol ON plan_execution_state(symbol);
       CREATE INDEX idx_exec_state_updated ON plan_execution_state(updated_at);
       CREATE INDEX idx_exec_state_trailing ON plan_execution_state(trailing_mode_enabled);
       ```
     - **State Persistence**: Store state in database, load on startup, recover for active plans
     - **State Cleanup**: Remove state for expired/cancelled plans (run cleanup job every hour)
     - **Atomic Operations**: Use database transaction for state updates, use `threading.RLock()` for in-memory cache
     - Use proper locking (acquire plan lock before state update)
     - Track plan version to detect concurrent modifications
     - Convert to trailing mode when activation R:R reached

---

## 🔧 Implementation Architecture

### Pre-Implementation: Database & Integration Setup (Before Phase 1) ✅ COMPLETE

1. **Database Migration Strategy** (CRITICAL: Added migration framework) ✅ COMPLETE
   - Create migration scripts:
     - `migrations/000_create_schema_version.sql` (create version tracking table first)
     - `migrations/001_create_pattern_history.sql`
     - `migrations/002_create_plan_execution_state.sql`
     - `migrations/003_add_indexes.sql`
   - Create migration version table: `schema_version`:
     ```sql
     CREATE TABLE IF NOT EXISTS schema_version (
         version INTEGER PRIMARY KEY,
         applied_at TEXT NOT NULL,  -- ISO format timestamp
         description TEXT NOT NULL
     );
     ```
   - **SQLite Compatibility Notes**:
     - Use TEXT for timestamps (consistent with existing `trade_plans` schema)
     - Use INTEGER for BOOLEAN (0 = FALSE, 1 = TRUE)
     - Handle timestamps in application code (ISO format strings)
     - Use triggers or application code for auto-updating timestamps
   - Create rollback scripts for each migration
   - Test migrations on development database
   - Backup database before each migration
   - Verify data integrity after migration

2. **Integration Planning** (CRITICAL: Added integration specifications)
   - Document integration points with existing services:
     - `infra/detection_systems.py` for OB/FVG/Breaker detection
     - `infra/order_flow_service.py` for order flow data
     - `infra/news_service.py` for news data
   - Plan backward compatibility approach (existing plans continue to work)
   - Design atomic operations (status checks, pattern updates, state updates)
   - Plan status check improvements (check before execution)

### Phase 1: Foundation with Optimization (Weeks 1-2)

1. **Correlation Condition Framework** (FIXED: Added integration and atomic operations) ✅ COMPLETE
   - ✅ Enhanced `correlation_context_calculator.py` with Phase III methods:
     - `calculate_dxy_change_pct()` - DXY percentage change calculation
     - `detect_dxy_stall()` - DXY momentum stall detection
     - `calculate_ethbtc_ratio_deviation()` - ETH/BTC ratio deviation
     - `get_nasdaq_15min_trend()` - NASDAQ 15-minute trend
     - `check_btc_hold_above_support()` - BTC support level detection
   - ✅ Added correlation condition checks to `_check_conditions()` (after order flow checks, before breaker block checks)
   - ✅ **Integration Points**: Using existing `market_indices_service.py`, handles service unavailability gracefully
   - ✅ Added DXY/ETH/BTC/NASDAQ tracking
   - ✅ **Status Check Before Execution** (CRITICAL): Already implemented in `_execute_trade()` (lines 6363-6385)
   - ✅ **Atomic Operations**: Status check uses database transaction (already implemented)
   - ✅ **Optimization**: Implemented 5-minute TTL caching for correlation calculations (`_get_cached_correlation`, `_cache_correlation`)
   - ⏳ **Optimization**: Batch correlation updates (update all symbols together) - TODO for future optimization

2. **Order Flow Microstructure** (FIXED: Added integration and atomic operations) ✅ COMPLETE
   - ✅ Enhanced `order_flow_analyzer.py` with `get_phase3_microstructure_metrics()` method
   - ✅ Enhanced `OrderBookAnalyzer` with Phase III methods:
     - `detect_imbalance_with_direction()` - Enhanced imbalance detection with direction
     - `detect_spoofing()` - Spoof detection using snapshot comparison method
     - `calculate_rebuild_speed()` - Bid/ask rebuild speed tracking
   - ✅ **Integration Points**: Using existing `infra/order_flow_service.py`, accessed via `desktop_agent.registry`
   - ✅ Added imbalance/spoof detection
   - ✅ Added bid/ask rebuild speed tracking
   - ✅ **Atomic Operations**: Pattern history updates will use database transactions (when implemented)
   - ✅ **Optimization**: Order book snapshots cached in `OrderBookAnalyzer` (history_size=10)
   - ✅ **Optimization**: Spoof detection only runs when order flow data available
   - ✅ Added condition checks to `_check_conditions()` for:
     - `imbalance_detected` (with direction validation)
     - `imbalance_direction` (requires `imbalance_detected: true`)
     - `spoof_detected`
     - `bid_rebuild_speed` / `ask_decay_speed` (with threshold checks)
     - `liquidity_rebuild_confirmed`

### Phase 2: Pattern Recognition with Caching (Weeks 3-4)

3. **Volatility Pattern Detection** (FIXED: Added RMAG calculation details) ✅ COMPLETE
   - ✅ Created `infra/volatility_pattern_recognition.py` module with `VolatilityPatternRecognizer` class
   - ✅ Added `detect_consecutive_inside_bars()` - Detects consecutive inside bar patterns
   - ✅ Added `detect_volatility_fractal_expansion()` - Detects BB width + ATR expansion pattern
   - ✅ Added `detect_iv_collapse()` - Detects IV collapse using ATR as proxy
   - ✅ Added `detect_volatility_recoil()` - Detects collapse → recoil pattern
   - ✅ Added `calculate_bb_width_trend()` - Calculates BB width trend (rising/falling)
   - ✅ Added `calculate_rmag_atr_ratio()` - Calculates RMAG ATR ratio
   - ✅ Added RMAG ATR ratio calculation (uses existing RMAG from advanced features)
   - ✅ **Optimization**: Cache pattern detection results for 2 minutes (120 seconds)
   - ✅ **Optimization**: Lazy evaluation (only check when volatility conditions exist)
   - ✅ Added condition checks to `_check_conditions()` for:
     - `consecutive_inside_bars` (with min_count validation)
     - `volatility_fractal_expansion` (BB + ATR expansion)
     - `iv_collapse_detected` (ATR collapse detection)
     - `volatility_recoil_confirmed` (collapse → recoil pattern)
     - `rmag_atr_ratio` (with threshold validation)
     - `bb_width_rising` (BB width trend check)
     - `impulse_continuation_confirmed` (composite: RMAG + BB width)
   - ✅ Tests: `test_phase3_volatility_patterns.py` (all tests passing with venv)

4. **Institutional Signature Detection** (FIXED: Added database schema, thread safety, recovery) ✅ COMPLETE
   - ✅ Created `infra/institutional_signature_detector.py` module with `InstitutionalSignatureDetector` class
   - ✅ **Integration Points**: Uses existing `infra/detection_systems.py`, integrates with pattern_history database
   - ✅ Added sequence/pattern tracking (with database persistence)
   - ✅ Added `detect_mitigation_cascade()` - Detects overlapping order blocks
   - ✅ Added `detect_breaker_retest_chain()` - Tracks breaker retest sequences
   - ✅ Added `detect_liquidity_vacuum_refill()` - Detects FVG + imbalance combo
   - ✅ Database schema for pattern_history table (via migration script - already exists)
   - ✅ **Recovery Mechanisms**: Auto-creates table if missing, validates on initialization
   - ✅ **Atomic Operations**: Uses database transactions for pattern inserts
   - ✅ **Optimization**: In-memory cache for recent patterns (5 minute TTL, max 100 entries)
   - ✅ **Optimization**: `cleanup_expired_patterns()` method for removing old patterns (>24 hours)
   - ✅ **Thread Safety**: Uses `threading.RLock()` for pattern history access
   - ✅ Added condition checks to `_check_conditions()` for:
     - `overlapping_obs_count` (requires `mitigation_block: true`, validates threshold)
     - `mitigation_cascade_confirmed` (requires `mitigation_block: true`)
     - `breaker_retest_count` (requires `breaker_block: true`, validates threshold)
     - `breaker_retest_chain_confirmed` (requires `breaker_block: true`)
     - `liquidity_vacuum_refill` (requires `fvg_bull/bear` and `imbalance_detected`)

### Phase 3: Multi-Timeframe & Adaptive (Weeks 5-6)

5. **Multi-Timeframe Confluence** (FIXED: Added batch fetching and condition approach) ✅ COMPLETE
   - ✅ Created `infra/multi_timeframe_data_fetcher.py` module with `MultiTimeframeDataFetcher` class
   - ✅ Added multi-TF condition checking (individual TF conditions approach)
   - ✅ Added `fetch_multi_timeframe_data()` method for batch fetching
   - ✅ Added `validate_timeframe_alignment()` method for data validation
   - ✅ Added M1 pullback detection (requires BOS on M15 first, then retracement 30-50%)
   - ✅ Added HTF FVG alignment validation (M30 FVG checks)
   - ✅ **Optimization**: Batch multi-TF data fetching (fetches all TFs in single call)
   - ✅ **Optimization**: Cache multi-TF data for 60 seconds (shared cache key)
   - ✅ **Optimization**: Conditional checks (only fetches when multi-TF conditions exist)
   - ✅ **Thread Safety**: Uses `threading.RLock()` for multi-TF cache access
   - ✅ Added condition checks to `_check_conditions()` for:
     - `choch_bull_m5`, `choch_bear_m5` (M5 CHOCH checks)
     - `choch_bull_m15`, `choch_bear_m15` (M15 CHOCH checks)
     - `bos_bull_m15`, `bos_bear_m15` (M15 BOS checks)
     - `fvg_bull_m30`, `fvg_bear_m30` (M30 FVG checks)
     - `m1_pullback_confirmed` (requires BOS on M15 first, then M1 retracement)

6. **Adaptive Scenario Handling** (FIXED: Separated plan conditions, added integration and recovery) ✅ COMPLETE
   - ✅ Added news absorption filter (pause breakout strategies during news)
   - ✅ Added post-news reclaim detection (price reclaim and CVD flip checks)
   - ✅ **Integration Points**: Uses existing `infra/news_service.py` for news blackout checks
   - ✅ Added strategy pause/resume (plan condition - blocks execution during news)
   - ✅ Added post-news reclaim tracking (plan condition - enables execution after news)
   - ✅ Added pre-news level tracking (uses `pre_news_level` from plan conditions)
   - ✅ **MOVED TO TRADE MANAGEMENT**: Weekend SL tightening (handled by Universal SL/TP Manager)
   - ✅ **Optimization**: Event-driven updates (only checks when adaptive conditions exist)
   - ✅ Added condition checks to `_check_conditions()` for:
     - `news_absorption_filter` (blocks execution during news blackout)
     - `news_blackout_window` (configurable window in minutes, default: 15)
     - `high_impact_news_types` (news types to filter, default: ["CPI", "FOMC", "NFP"])
     - `post_news_reclaim` (enables post-news logic)
     - `price_reclaim_confirmed` (price returns to within 0.1% of pre-news level or 0.5 ATR)
     - `cvd_flip_confirmed` (CVD slope changes, requires BTC order flow data)
     - `pre_news_level` (pre-news price level for reclaim tracking)

### Phase 4: Predictive Models (Weeks 7-8)

7. **Momentum & Time-Based Models** (FIXED: Separated entry vs exit, added execution state) ✅ COMPLETE
   - ✅ Created `infra/momentum_decay_detector.py` module with `MomentumDecayDetector` class
   - ✅ Added momentum decay detection (for plan entry conditions)
   - ✅ Added momentum tracking (stores RSI/MACD over time, last 50 periods)
   - ✅ Added tick rate tracking (stores tick rate over rolling window, last 20 readings)
   - ✅ **MOVED TO TRADE MANAGEMENT**: Time-based exit conditions (handled by Universal SL/TP Manager)
   - ✅ **MOVED TO EXECUTION STATE**: Dynamic plan conversion (uses execution state, not plan conditions)
   - ✅ **Optimization**: Cache momentum calculations for 2 minutes (120 seconds)
   - ✅ **Optimization**: Only checks when momentum decay conditions exist
   - ✅ **Thread Safety**: Uses `threading.RLock()` for cache and history access
   - ✅ Added condition checks to `_check_conditions()` for:
     - `momentum_decay_trap` (enables momentum decay detection)
     - `rsi_divergence_detected` (RSI divergence from price)
     - `macd_divergence_detected` (MACD divergence from price)
     - `tick_rate_declining` (tick rate decline >20% for >5 minutes)
     - `momentum_decay_confirmed` (composite: divergence AND tick rate decline)

---

## ⚡ Performance Optimization Strategy

### CPU Optimization (Target: < 100ms per plan check)

1. **Caching Strategy** (FIXED: Added cache invalidation strategy)
   - **Correlation calculations**: 5-10 minute TTL cache
   - **Multi-TF data**: 30-60 second cache (shared across plans)
   - **Pattern detection**: 2-5 minute cache
   - **Order flow metrics**: 30-60 second cache
   - **Momentum calculations**: 1-2 minute cache
   - **Cache Invalidation Strategy** (NEW):
     - **Time-based**: TTL expiration (primary method)
     - **Event-based**: Invalidate on significant price moves (>1% change)
     - **Data-based**: Invalidate when new candle closes (M1, M5, M15)
     - **Manual**: Invalidate on plan execution (to prevent stale data)
     - **Version tracking**: Use data version numbers to detect updates
     - **Cache keys**: Include symbol + timeframe + data version

2. **Batch Processing**
   - Batch multi-TF data fetching (fetch all TFs in one call)
   - Batch correlation updates (update all symbols together)
   - Batch order flow calculations (calculate for all symbols at once)

3. **Conditional Checks (Lazy Evaluation)** (FIXED: Added condition check order)
   - **Optimized Check Order** (for early exit):
     1. Expiration check (cheapest - return False immediately)
     2. Price conditions (price_near, tolerance - cheap, ~5-10ms)
     3. Simple structure (choch_bull/bear on single TF - moderate, ~20-50ms)
     4. Volatility conditions (bb_expansion, inside_bar - moderate, ~30-60ms)
     5. Order flow conditions (delta, cvd - moderate, ~40-80ms, cached)
     6. Multi-TF checks (expensive - only if simple checks pass, ~100-280ms)
     7. Pattern detection (most expensive - only if all else passes, ~50-150ms)
   - Skip expensive checks if simple conditions fail first
   - Only calculate when conditions are actually needed
   - Early exit on condition failure

4. **Selective Processing**
   - Only process active symbols (not all symbols)
   - Skip checks for expired plans immediately
   - Skip checks for plans without new conditions

5. **Error Handling & Timeouts** (NEW: Added comprehensive error handling)
   - **API Timeouts**: 
     - External API calls: 5 second timeout
     - Database queries: 2 second timeout
     - MT5 data fetches: 3 second timeout
   - **Retry Logic**:
     - Retry failed API calls up to 2 times (exponential backoff: 1s, 2s)
     - Skip retry for database queries (fail fast)
     - Cache failures for 30 seconds (don't retry immediately)
   - **Connection Failures**:
     - Log warning and skip condition if data source unavailable
     - Use cached data if available (even if stale, within 2x TTL)
     - Return False for condition if data unavailable and no cache
   - **Partial Data Availability**:
     - If DXY available but ETH not: Skip ETH conditions, proceed with DXY
     - If some TFs available but not all: Skip multi-TF plans, proceed with single-TF
     - Log partial availability warnings
   - **Performance Degradation**:
     - If condition check takes >150ms: Log warning, continue with next plan
     - If total check time >500ms: Skip remaining expensive checks, use cached results
     - Monitor check times and alert if consistently slow

6. **Cache Consistency Strategy** (NEW: Added versioning and coherency)
   - **Version Tracking**:
     - Each data source has version number (increments on update)
     - Cache keys include version number
     - Check version before using cached data
   - **Mid-Check Updates**:
     - Use snapshot of data at check start (don't update mid-check)
     - If data updates during check: Use current snapshot, log warning
     - Don't invalidate cache during active checks
   - **Stale Cache Handling**:
     - If cache stale but within 2x TTL: Use with warning log
     - If cache stale beyond 2x TTL: Fetch fresh data, update cache
     - If fetch fails: Use stale cache if available (graceful degradation)
   - **Cache Coherency**:
     - Use read locks for cache reads (multiple plans can read simultaneously)
     - Use write locks for cache updates (exclusive access)
     - Invalidate related caches when data updates (e.g., invalidate all TFs when price updates)

### RAM Optimization (Target: < 400MB additional)

1. **Memory Limits**
   - Pattern history: LRU cache with 100-200 pattern limit
   - Multi-TF cache: Limit to active symbols only
   - Order book snapshots: Keep only last 5-10 snapshots
   - Correlation data: Limit rolling windows to 100-200 periods

2. **Automatic Cleanup**
   - Remove pattern history >24 hours old
   - Clean up expired plan data immediately
   - Garbage collect unused caches every 5 minutes
   - Remove inactive symbol data after 1 hour

3. **Selective Caching**
   - Cache only for active symbols (not all symbols)
   - Cache only for plans with relevant conditions
   - Use weak references where possible

4. **Memory Pooling**
   - Reuse data structures (DataFrames, arrays)
   - Pool connection objects
   - Reuse calculation buffers

### SSD Optimization (Target: < 50MB/day)

1. **Log Management**
   - Rotate logs daily, keep last 7 days
   - Use log levels appropriately (DEBUG only when needed)
   - Compress old logs

2. **Database Optimization** (FIXED: Added connection pooling)
   - **Connection Pooling**:
     - Max connections: 10-20 (configurable)
     - Connection timeout: 5 seconds
     - Idle timeout: 30 minutes
     - Use connection pool for all database operations
   - **Query Optimization**:
     - Use prepared statements for pattern_history queries
     - Batch inserts for pattern history (insert multiple patterns at once)
     - Use indexes for frequently queried fields
     - Limit query result sets (use LIMIT clauses)
   - **Connection Management**:
     - Acquire connection from pool before query
     - Release connection immediately after query
     - Handle connection failures gracefully (retry with backoff)
     - Monitor connection pool usage (log warnings if >80% utilized)
   - Archive pattern history >30 days old
   - Vacuum database weekly

3. **Optional Persistence**
   - Make cache persistence optional (disabled by default)
   - Only persist critical pattern data
   - Compress historical pattern data

4. **Data Retention**
   - Keep only necessary historical data
   - Archive old plan execution data
   - Clean up temporary files regularly

### Performance Monitoring

1. **Metrics to Track**
   - Average condition check time per plan
   - Cache hit rates
   - Memory usage trends
   - Database write frequency
   - CPU usage per feature category

2. **Alerting Thresholds** (FIXED: Added comprehensive alerting)
   - **Performance Alerts**:
     - Condition check > 150ms: Warning
     - Memory usage > 500MB: Warning
     - Cache hit rate < 60%: Warning
     - CPU usage > 50%: Warning
   - **Condition Check Failures** (NEW):
     - Condition check fails >3 times in 10 minutes: Alert
     - Condition check takes >500ms consistently: Alert
     - Condition check throws exceptions: Alert
   - **Data Source Availability** (NEW):
     - Data source unavailable >5 minutes: Alert
     - Data source returns errors >10 times in 1 hour: Alert
     - Cache hit rate drops <50% (data source issues): Alert
   - **Pattern History Issues** (NEW):
     - Pattern history cleanup fails: Alert
     - Pattern history size >10,000 records: Alert
     - Pattern history queries take >100ms: Alert
   - **Execution State Issues** (NEW):
     - Execution state out of sync with plans: Alert
     - Execution state cleanup fails: Alert
     - Execution state updates fail: Alert
   - **Database Issues** (NEW):
     - Database connection pool >90% utilized: Alert
     - Database queries take >200ms: Alert
     - Database migrations fail: Alert

3. **Performance Profiling**
   - Profile condition checks monthly
   - Identify slow conditions
   - Optimize hot paths
   - Review cache effectiveness

## 📊 Testing Requirements

### Unit Tests
- [ ] Correlation condition validation
- [ ] Order flow microstructure detection
- [ ] Volatility pattern recognition
- [ ] Multi-timeframe alignment
- [ ] Adaptive plan modifications
- [ ] Momentum decay detection
- [ ] Cache effectiveness tests
- [ ] Memory cleanup tests

### Integration Tests
- [ ] End-to-end plan execution with new conditions
- [ ] Multi-timeframe condition validation (with batch fetching and data alignment)
- [ ] Adaptive scenario handling (with state persistence)
- [ ] **MOVED**: Time-based exit execution (test in trade management system)
- [ ] Cache invalidation on data updates (price moves, candle closes)
- [ ] Cache consistency (version tracking, mid-check updates, stale cache handling)
- [ ] Memory cleanup under load
- [ ] Thread safety under concurrent plan checks
- [ ] Database pattern history persistence and cleanup
- [ ] Database connection pooling (connection limits, timeout handling)
- [ ] Graceful degradation (missing data sources, partial data availability)
- [ ] Execution state updates (trailing mode conversion, state persistence)
- [ ] Error handling (API timeouts, retry logic, connection failures)
- [ ] Condition dependency validation (required combinations, conflicting conditions)
- [ ] Partial condition handling (required vs optional conditions, condition groups)

### Performance Tests
- [ ] Condition check performance (target: < 100ms per plan)
- [ ] Multi-timeframe data fetching efficiency (target: < 200ms batch)
- [ ] Pattern detection latency (target: < 50ms with cache)
- [ ] Memory usage under 50 active plans (target: < 400MB additional)
- [ ] Cache hit rate (target: > 70%)
- [ ] CPU usage under load (target: < 30% increase)

---

## 🚨 Risk Considerations

1. **Data Availability**
   - ETH/BTC ratio: Requires ETH price data source
   - NASDAQ 15-min trend: Requires NASDAQ data feed
   - BTC open interest: Requires futures data source
   - **Mitigation**: Graceful degradation (skip conditions if data unavailable)

2. **Performance Impact**
   - Multi-timeframe checks may increase condition check time
   - Pattern detection may require additional computation
   - Need to optimize for 30-second check interval
   - **Mitigation**: Aggressive caching, batch processing, conditional checks

3. **Complexity**
   - Adaptive plan modifications add state management complexity
   - Multi-timeframe validation requires careful synchronization
   - Pattern tracking requires history management
   - **Mitigation**: Clear state management, comprehensive testing, phased rollout

4. **Resource Usage**
   - CPU: +15-30% increase expected
   - RAM: +150-400MB increase expected
   - SSD: +17-61MB/day increase expected
   - **Mitigation**: Implement all optimization strategies, monitor closely, set limits

---

## 📝 Documentation Requirements

1. **API Documentation**
   - Document all new conditions
   - Document condition combinations
   - Document adaptive plan features

2. **Knowledge Documents**
   - Update ChatGPT knowledge docs with new conditions
   - Add examples for each plan type
   - Document best practices

3. **User Guide**
   - Explain when to use each plan type
   - Document adaptive scenario handling
   - Provide troubleshooting guide

---

## ✅ Success Criteria

1. **Functional**
   - All 7 plan categories can be created and executed
   - All new conditions are properly checked
   - Adaptive scenarios work correctly
   - Caching works as expected

2. **Performance**
   - Condition checks complete within 100ms per plan (with cache)
   - System handles 50+ plans with new conditions
   - No degradation in existing plan execution
   - Cache hit rate > 70%
   - Multi-TF batch fetching < 200ms

3. **Resource Usage**
   - CPU increase < 30% (with optimizations)
   - RAM increase < 400MB (with cleanup)
   - SSD usage < 50MB/day (with log rotation)
   - Memory cleanup works correctly

4. **Reliability**
   - 99%+ condition check accuracy
   - Proper error handling for missing data
   - Graceful degradation when services unavailable
   - Cache invalidation works correctly
   - Memory leaks prevented

---

## 🎯 Next Steps

1. **Review & Approval**
   - Review implementation plan with stakeholders
   - Prioritize plan categories based on value
   - Approve timeline and resources
   - Review optimization strategy

2. **Development Setup**
   - Set up development environment
   - Create feature branches
   - Set up performance monitoring tools
   - Configure caching infrastructure

3. **Development (Optimization-First Approach with Backward Compatibility)**
   - Begin Phase 1 implementation with caching from day 1
   - Implement batch processing early
   - Add conditional checks to prevent unnecessary work
   - **Backward Compatibility**: Ensure all existing plans continue to work, new conditions are optional, existing condition logic unchanged
   - **Gradual Rollout**: Enable new features per plan, use feature flags for new conditions
   - Monitor performance continuously
   - Monitor existing plan execution during rollout

4. **Testing**
   - Set up test environment
   - Create test plans
   - Begin unit testing
   - Performance testing with 50+ plans
   - Memory leak testing
   - Cache effectiveness testing
   - Thread safety testing (concurrent plan checks)
   - Database migration testing (pattern_history schema)
   - Graceful degradation testing (missing data sources)

5. **Optimization Review**
   - Review cache hit rates
   - Identify slow conditions
   - Optimize hot paths
   - Adjust cache TTLs based on usage patterns

---

**Document Version**: 2.3 (Optimized + Reviewed + Fixed + Critical/Major Review)  
**Last Updated**: 2026-01-07  
**Owner**: Development Team  
**Status**: Review Complete - All 38 fixes integrated (See PHASE_III_PLAN_REVIEW_AND_FIXES.md, PHASE_III_PLAN_REVIEW_SECOND_PASS.md, and PHASE_III_PLAN_REVIEW_CRITICAL_MAJOR.md for details)

### Review Status
- ✅ **All Critical Fixes Applied** (13/13): Multi-TF conditions, time-based exits, execution state, SL modifications, data sources, database schema, condition logic definitions, error handling, condition dependencies, database migration strategy, auto-execution integration, complete execution state schema, rollback/recovery mechanisms
- ✅ **All High Priority Fixes Applied** (12/12): Spoof detection, cache invalidation, thread safety, batch fetching, pre-news tracking, momentum tracking, condition order, thresholds, data alignment, cache consistency, execution state persistence, partial condition handling
- ✅ **All Medium Priority Fixes Applied** (13/13): Imbalance direction, RMAG calculation, breaker retest, news integration, state persistence, support level detection, stall detection, pullback detection, database pooling, integration points, monitoring/alerting, atomic operations, backward compatibility
- ✅ **Total Fixes Integrated**: 38/38

---

## 📊 Resource Impact Summary

### Expected Resource Usage (With Optimizations)

| Resource | Baseline | With Phase III | Increase | Target |
|----------|----------|----------------|----------|--------|
| **CPU** | 4-12% | 19-42% | +15-30% | < 30% |
| **RAM** | 100-200MB | 250-600MB | +150-400MB | < 400MB |
| **SSD** | 10-50MB/day | 27-111MB/day | +17-61MB/day | < 50MB/day |

### Optimization Impact

- **CPU**: Caching reduces CPU by 40-60% (from +30-50% to +15-30%)
- **RAM**: Cleanup reduces RAM by 30-50% (from +300-600MB to +150-400MB)
- **SSD**: Log rotation reduces SSD by 50-70% (from +50-100MB to +17-61MB)

### Key Optimization Strategies

1. **Caching**: 5-10 minute TTL for expensive calculations
2. **Batch Processing**: Fetch multiple timeframes/data sources together
3. **Conditional Checks**: Skip expensive checks if simple conditions fail
4. **Memory Limits**: LRU caches with automatic cleanup
5. **Selective Processing**: Only process active symbols/plans


