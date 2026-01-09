# Adaptive Micro-Scalp Strategy Implementation Plan

**Version:** 1.9  
**Date:** 2025-12-03  
**Last Updated:** 2025-12-04  
**Status:** Implementation Phase - Core Components Completed (Enhanced + Fixed + Complete + Optimized + Reviewed + Critical Issues Fixed + Data Flow Fixed + Method Signature Fixed + Helper Method Access Fixed + Snapshot Data Flow Fixed + V9 Issues Fixed + V10 Issues Fixed + Implementation Started)

---

## ⚠️ **CRITICAL: IMPLEMENTATION REQUIREMENTS**

**🚨 IMPORTANT: This plan describes NEW functionality to be implemented, NOT existing code.**

The current codebase (`infra/micro_scalp_engine.py`) still uses the **OLD edge-based system**. This plan outlines the **NEW adaptive strategy selection system** that needs to be implemented.

### **What This Means:**

1. **The plan is an implementation guide** - All code examples show what needs to be built, not what currently exists
2. **Actual code must be updated** - `MicroScalpEngine` and related components need significant changes
3. **New components must be created** - `MicroScalpRegimeDetector`, `MicroScalpStrategyRouter`, and strategy checkers are new
4. **Integration points must be updated** - Callers of `MicroScalpEngine` need to pass new dependencies

### **Critical Implementation Gaps (Priority 1 - Must-Fix Before Coding):**

**🚨 NEW CLASSES MISSING (All Non-Existent and Blocking):**

- ✅ **`MicroScalpRegimeDetector`** - ✅ COMPLETED - Created in `infra/micro_scalp_regime_detector.py`
- ❌ **`MicroScalpStrategyRouter`** - Complete class missing
- ✅ **`BaseStrategyChecker`** - ✅ COMPLETED - Created in `infra/micro_scalp_strategies/base_strategy_checker.py`
- ❌ **Strategy checker subclasses** - All 4 missing:
  - `VWAPReversionChecker`
  - `RangeScalpChecker`
  - `BalancedZoneChecker`
  - `EdgeBasedChecker`
- ❌ **`MicroScalpEngine._get_strategy_checker()`** - Method missing

**🚨 DEPENDENCY INJECTION (Required for Functionality):**

- ✅ **`MicroScalpEngine.__init__()` signature** - ✅ COMPLETED - Now accepts `streamer` and `news_service`
  - Without `streamer`: M5/M15 fetching cannot operate
  - Without `news_service`: Macro filters cannot operate

**🚨 SNAPSHOT INTEGRITY (Mandatory for Confluence Logic):**

- ✅ **`_build_snapshot()` enhancements** - ✅ COMPLETED - Added:
  - ✅ ATR14 calculation and storage (using `volatility_filter.calculate_atr14()`)
  - ✅ Multi-timeframe candle capture (M5/M15 from streamer)
  - ✅ `_candle_to_dict()` helper method
- ⚠️ **Without ATR14**: Volatility-aware scoring fails
- ⚠️ **Without M5/M15**: Multi-timeframe compression checks fail

**🚨 STRATEGY CHECKER HIERARCHY (Required for Adaptivity):**

- ❌ **`BaseStrategyChecker` subclass** - Must inherit from:
  - `MicroScalpConditionsChecker` (base validation)
  - `ABC` (abstract base class)
- ❌ **Strategy-specific `_calculate_confluence_score()` overrides** - All 4 strategies must override:
  - Without overrides: All strategies share identical validation logic
  - Result: System loses adaptivity, behaves like single strategy
- ❌ **Strategy-specific `_check_location_filter()` overrides** - All 4 strategies must override:
  - Each strategy has unique location requirements (VWAP deviation, range edges, balanced zones)
- ❌ **Strategy-specific `_check_candle_signals()` overrides** - All 4 strategies must override:
  - Each strategy has unique signal requirements (CHOCH, liquidity sweeps, compression breaks)

### **Historical Review Documents (Reference Only):**

The following documents contain detailed analysis of issues found during plan review. **All critical fixes have been incorporated into this main plan**, so these documents are for historical reference and detailed explanations only:

- `ADAPTIVE_MICRO_SCALP_CRITICAL_ISSUES_V2.md` - Initial review findings
- `ADAPTIVE_MICRO_SCALP_CRITICAL_ISSUES_V3.md` - Additional integration issues
- `ADAPTIVE_MICRO_SCALP_CRITICAL_ISSUES_V4.md` - Root cause analysis (method signature mismatches)
- `ADAPTIVE_MICRO_SCALP_CRITICAL_ISSUES_V5.md` - Data flow and integration fixes
- `ADAPTIVE_MICRO_SCALP_CRITICAL_ISSUES_V6.md` - Additional critical errors
- `ADAPTIVE_MICRO_SCALP_CRITICAL_ISSUES_V7.md` - Final review (ATR14, error handling)
- `ADAPTIVE_MICRO_SCALP_CRITICAL_ISSUES_V8.md` - Helper method access and data flow issues
- `ADAPTIVE_MICRO_SCALP_CRITICAL_ISSUES_V9.md` - Implementation and logic error review
- `ADAPTIVE_MICRO_SCALP_CRITICAL_ISSUES_V10.md` - Second implementation and logic error review (duplicate methods, helper access)
- `ADAPTIVE_MICRO_SCALP_CRITICAL_ISSUES_V10.md` - Second implementation and logic error review (duplicate methods, helper access)

**✅ IMPORTANT:** This main plan is **self-contained** and includes all fixes. You do NOT need to reference the critical issues documents during implementation. They are provided for:
- Understanding the evolution of the plan
- Detailed explanations of why certain fixes were needed
- Historical context for design decisions

### **See Implementation Checklist:**

For a complete list of required changes, see **Section 0.0: Implementation Checklist** below.

---

## 📋 Executive Summary

This plan implements adaptive strategy selection for the micro-scalp system, allowing it to automatically switch between three distinct strategies based on market conditions:

1. **VWAP Reversion Scalp** - Mean reversion when price deviates ≥2σ from VWAP
2. **Range Scalp** - Trading range edges (PDH/PDL or M15 bounds)
3. **Balanced Zone Scalp** - Compression block mean reversion

The system maintains the existing 4-layer validation structure while adapting strategy-specific entry/exit logic to current market regime.

---

## 🎯 Objectives

- **Increase Trade Frequency**: Capture opportunities in range/balanced markets that current edge-based system misses
- **Maintain Quality**: Keep strict 4-layer validation per strategy
- **Leverage Existing Code**: Reuse 80%+ of existing infrastructure
- **Backward Compatible**: Fallback to current edge-based strategy if regime detection fails
- **Symbol-Specific**: Different thresholds for BTCUSDc vs XAUUSDc

---

## 🏗️ Architecture Overview

### Current Flow
```
Snapshot → MicroScalpConditionsChecker.validate() → Trade Idea
```

### New Adaptive Flow
```
Snapshot (with ATR14 + M5/M15) 
  → MicroScalpRegimeDetector.detect_regime()
    → MicroScalpStrategyRouter.select_strategy()
      → Strategy-specific ConditionsChecker.validate()
        → Strategy-specific Trade Idea Generator
```

### Architecture Components & Logic

| Component | Purpose | Key Checks | Output |
|-----------|---------|------------|--------|
| **RegimeDetector** | Detects market regime (trending, ranging, balanced) | • Volatility (ATR ratio)<br>• VWAP deviation (Z-score)<br>• PDH-PDL compression ratio<br>• BB width contraction | `regime_result` with `regime`, `confidence`, `characteristics` |
| **StrategyRouter** | Maps detected regime → strategy name | • Regime confidence threshold<br>• Confluence pre-check<br>• Anti-flip-flop logic | `strategy_name` ('vwap_reversion', 'range_scalp', 'balanced_zone', 'edge_based') |
| **StrategyChecker** | Executes 4-layer validation per strategy | ① Structure (location)<br>② Volatility (ATR/BB)<br>③ Liquidity (volume/sweeps)<br>④ Momentum (CHOCH/signals) | `ConditionCheckResult` with `passed`, `confluence_score`, `details` |
| **Engine** | Coordinates all components | • Builds snapshot (ATR14 + M5/M15)<br>• Detects regime<br>• Routes to strategy<br>• Validates conditions<br>• Generates trade idea | `Dict` with `passed`, `trade_idea`, `strategy`, `regime` |

### Recommended Detection Logic

**Regime Detection Thresholds:**

1. **VWAP Reversion:**
   - VWAP Z-score > 2.0 → VWAP Reversion regime
   - Confidence: 70% minimum

2. **Range Scalp:**
   - Range width < 1.2 × ATR → Range Scalp regime
   - Confidence: 55% minimum

3. **Balanced Zone:**
   - BB width < 0.02 (2% of price) → Balanced Zone regime
   - Confidence: 65% minimum

4. **Edge-Based (Fallback):**
   - If no regime detected OR confidence below thresholds
   - Uses existing edge-based validation logic

---

## 📋 0.0 Implementation Checklist

**Status:** ✅ **IMPLEMENTATION IN PROGRESS** - Core components completed, integration pending testing

This checklist tracks all code changes required to implement the adaptive micro-scalp system. Check off items as they are completed.

### **Priority 1: Core Integration (Blocks Everything)**

- [x] **Update `MicroScalpEngine.__init__()` signature** ✅ COMPLETED
  - [x] Add `streamer: Optional[MultiTimeframeStreamer] = None` parameter
  - [x] Add `news_service=None` parameter
  - [x] Store `self.streamer = streamer`
  - [x] Store `self.news_service = news_service`
  - [x] Initialize `self.strategy_checkers = {}` dictionary
  - [x] Initialize `MicroScalpRegimeDetector`
  - [x] Initialize `MicroScalpStrategyRouter`

- [ ] **Create `RangeBoundaryDetector` instance**
  - [ ] Import `from infra.range_boundary_detector import RangeBoundaryDetector`
  - [ ] Initialize `range_detector = RangeBoundaryDetector(self.config)` in `__init__()`

- [x] **Initialize `MicroScalpRegimeDetector`** ✅ COMPLETED
  - [x] Create file `infra/micro_scalp_regime_detector.py`
  - [x] Implement `MicroScalpRegimeDetector` class with all methods
  - [x] Import in `MicroScalpEngine.__init__()`
  - [x] Initialize with all dependencies: `config`, `m1_analyzer`, `vwap_filter`, `range_detector`, `volatility_filter`, `streamer`, `news_service`, `mt5_service`
  - [x] Store as `self.regime_detector`

- [x] **Initialize `MicroScalpStrategyRouter`** ✅ COMPLETED
  - [x] Create file `infra/micro_scalp_strategy_router.py`
  - [x] Implement `MicroScalpStrategyRouter` class with all methods
  - [x] Import in `MicroScalpEngine.__init__()`
  - [x] Initialize with `config`, `regime_detector`, `m1_analyzer`
  - [x] Store as `self.strategy_router`

### **Priority 2: Method Updates (Required for Functionality)**

- [x] **Update `_build_snapshot()` method** ✅ COMPLETED
  - [x] Add M5 candle fetching from streamer (if available)
  - [x] Add M15 candle fetching from streamer (if available)
  - [x] Add `_candle_to_dict()` helper method to convert streamer objects
  - [x] Add ATR14 calculation and storage in snapshot
  - [x] Add error handling for streamer unavailable
  - [x] Store `m5_candles` and `m15_candles` in snapshot dict
  - [x] Store `atr14` in snapshot dict
  - [x] Store `vwap_std` in snapshot dict

- [x] **Implement `_candle_to_dict()` helper method** ✅ COMPLETED
  - [x] Convert streamer candle objects to dict format
  - [x] Handle different candle object types
  - [x] Extract: `time`, `open`, `high`, `low`, `close`, `volume`
  - [x] Return `Dict[str, Any]`

- [x] **Implement `_get_strategy_checker()` method** ✅ COMPLETED
  - [x] Check cache (`self.strategy_checkers`) first
  - [x] Import and initialize `VWAPReversionChecker` for `'vwap_reversion'`
  - [x] Import and initialize `RangeScalpChecker` for `'range_scalp'`
  - [x] Import and initialize `BalancedZoneChecker` for `'balanced_zone'`
  - [x] Import and initialize `EdgeBasedChecker` for `'edge_based'`
  - [x] Pass all required dependencies to each checker
  - [x] Include `news_service` and `strategy_name` in all initializations
  - [x] Cache checkers in `self.strategy_checkers` dict
  - [x] Add error handling with fallback to `edge_based`

- [x] **Update `check_micro_conditions()` method** ✅ COMPLETED
  - [x] Remove old `self.conditions_checker.validate()` call (replaced with strategy-specific checker)
  - [x] Add error handling for regime detector (check if None, try-except)
  - [x] Add `regime_result = self.regime_detector.detect_regime(snapshot)` with fallback
  - [x] **NEW (V1.9 Fix)**: Extract and store regime-specific data in snapshot:
    - [x] If regime == 'RANGE': store `range_structure`, `range_near_edge`
    - [x] If regime == 'VWAP_REVERSION': store `vwap_deviation_sigma`, `vwap_deviation_pct`
    - [x] If regime == 'BALANCED_ZONE': store `compression_detected`, `equal_highs`, `equal_lows`
  - [x] Add error handling for strategy router (check if None, try-except)
  - [x] Add `strategy_name = self.strategy_router.select_strategy(snapshot, regime_result)` with fallback
  - [x] Add error handling for `_get_strategy_checker()` (try-except with fallback to edge_based)
  - [x] Add `checker = self._get_strategy_checker(strategy_name)`
  - [x] Replace with `result = checker.validate(snapshot)`
  - [x] Replace `_generate_trade_idea()` with `trade_idea = checker.generate_trade_idea(snapshot, result)`
  - [x] Update return dict to include `strategy` and `regime` fields
  - [x] Add trade idea validation (required fields check)
  - [x] Add `plan_id` to return dict

- [ ] **Remove obsolete methods**
  - [ ] Delete `_generate_trade_idea()` method (moved to strategy checkers)
  - [ ] Delete `_determine_direction()` method (moved to strategy checkers)

### **Priority 3: Strategy Checker Implementation**

- [x] **Create `BaseStrategyChecker` class** ✅ COMPLETED
  - [x] Create file `infra/micro_scalp_strategies/base_strategy_checker.py`
  - [x] Inherit from `MicroScalpConditionsChecker` and `ABC`
  - [x] Add `news_service` and `strategy_name` to `__init__()`
  - [x] Define concrete `validate()` method (calls strategy-specific overrides)
  - [x] Define abstract `generate_trade_idea()` method
  - [x] **NEW (V1.9 Fix)**: Add helper methods to `BaseStrategyChecker`:
    - [x] `_calculate_vwap_std(candles, vwap) -> float`
    - [x] `_calculate_vwap_slope(candles, vwap) -> float`
    - [x] `_check_volume_spike(candles) -> bool`
    - [x] `_check_bb_compression(candles) -> bool`
    - [x] `_check_compression_block(candles, atr1) -> bool`
    - [x] `_count_range_respects(candles, range_high, range_low) -> int`
    - [x] `_check_m15_trend(symbol, snapshot) -> str`
    - [x] `_check_choppy_liquidity(candles) -> bool`
    - [x] `_candles_to_df(candles) -> Optional[pd.DataFrame]`
    - [x] `_calculate_vwap_from_candles(candles) -> float`
  - [x] **NEW (V1.9 Fix)**: Implement concrete `validate()` that calls strategy-specific overrides

- [x] **Create `VWAPReversionChecker` class** ✅ COMPLETED
  - [x] Create file `infra/micro_scalp_strategies/vwap_reversion_checker.py`
  - [x] Inherit from `BaseStrategyChecker`
  - [x] Override `_check_location_filter()` with VWAP deviation logic
  - [x] Override `_check_candle_signals()` with CHOCH at extreme logic
  - [x] Override `_calculate_confluence_score()` with strategy-specific weights
  - [x] Implement `validate()` method (uses base class)
  - [x] Implement `generate_trade_idea()` method

- [x] **Create `RangeScalpChecker` class** ✅ COMPLETED
  - [x] Create file `infra/micro_scalp_strategies/range_scalp_checker.py`
  - [x] Inherit from `BaseStrategyChecker`
  - [x] Override `_check_location_filter()` with range edge logic
  - [x] **NEW (V1.9 Fix)**: Update `_check_location_filter()` to use `self._current_snapshot['range_structure']` instead of detecting range again
  - [x] Override `_check_candle_signals()` with sweep at edge logic
  - [x] Override `_calculate_confluence_score()` with strategy-specific weights
  - [x] Implement `validate()` method (uses base class)
  - [x] Implement `generate_trade_idea()` method

- [x] **Create `BalancedZoneChecker` class** ✅ COMPLETED
  - [x] Create file `infra/micro_scalp_strategies/balanced_zone_checker.py`
  - [x] Inherit from `BaseStrategyChecker`
  - [x] Override `_check_location_filter()` with compression block logic
  - [x] **NEW (V1.9 Fix)**: Update `_check_location_filter()` to use `self._current_snapshot['m5_candles']` for MTF compression check
  - [x] Override `_check_candle_signals()` with fade/breakout logic
  - [x] Override `_calculate_confluence_score()` with strategy-specific weights
  - [x] Implement `validate()` method (uses base class)
  - [x] Implement `generate_trade_idea()` method
  - [x] Add `_detect_entry_type_from_candles()` helper
  - [x] Add `_calculate_ema()` helper

- [x] **Create `EdgeBasedChecker` class** ✅ COMPLETED
  - [x] Create file `infra/micro_scalp_strategies/edge_based_checker.py`
  - [x] Inherit from `BaseStrategyChecker`
  - [x] Uses base class `_check_location_filter()` and `_check_candle_signals()` (no override needed)
  - [x] Implement `generate_trade_idea()` method (similar to existing logic)
  - [x] Implement `validate()` method (uses base class)

### **Priority 4: Caller Updates (Required for Integration)**

- [x] **Update `auto_execution_system.py`** ✅ COMPLETED
  - [x] Locate `MicroScalpEngine` initialization
  - [x] Add `streamer=streamer` parameter to `__init__()` signature
  - [x] Add `news_service=news_service` parameter to `__init__()` signature
  - [x] Pass `streamer=streamer` to `MicroScalpEngine` initialization
  - [x] Pass `news_service=news_service` to `MicroScalpEngine` initialization

- [x] **Update `app/main_api.py`** ✅ COMPLETED
  - [x] Locate `MicroScalpEngine` initialization in `startup_event()`
  - [x] Add `streamer=multi_tf_streamer` parameter
  - [x] Add `news_service=news_service` parameter
  - [x] Ensure `multi_tf_streamer` and `news_service` are available in scope

- [x] **Update `infra/micro_scalp_monitor.py`** ✅ COMPLETED (No changes needed)
  - [x] Monitor receives `micro_scalp_engine` as parameter (doesn't create it)
  - [x] Engine is created in `main_api.py` with correct parameters
  - [x] Monitor already has `self.streamer` and `self.news_service` stored

### **Priority 5: Configuration Updates**

- [x] **Update `config/micro_scalp_config.json`** ✅ COMPLETED
  - [x] Add `regime_detection` section
  - [x] Add `strategy_confidence_thresholds` (VWAP: 70, Range: 55, Balanced: 65)
  - [x] Add `confluence_weights` for each strategy
  - [x] Add `confidence_diff_threshold: 10`
  - [x] Add `confluence_pre_check` settings
  - [x] Add `volume_normalization` settings
  - [x] Add `ema_vwap_equilibrium_threshold` for balanced zone

### **Priority 6: Testing & Validation**

- [ ] **Create unit tests**
  - [ ] Test `MicroScalpRegimeDetector.detect_regime()`
  - [ ] Test `MicroScalpStrategyRouter.select_strategy()`
  - [ ] Test each strategy checker's `validate()` method
  - [ ] Test each strategy checker's `generate_trade_idea()` method
  - [ ] Test `MicroScalpEngine.check_micro_conditions()` with new flow
  - [ ] **NEW (V9/V10):** Test helper methods in `BaseStrategyChecker` (accessibility)
    - [ ] Test `_calculate_vwap_std()` from strategy checkers
    - [ ] Test `_calculate_vwap_slope()` from strategy checkers
    - [ ] Test `_check_volume_spike()` from strategy checkers
    - [ ] Test `_check_bb_compression()` from strategy checkers
    - [ ] Test `_check_compression_block()` from strategy checkers
    - [ ] Test `_count_range_respects()` from strategy checkers
    - [ ] Test `_candles_to_df()` with various candle formats
  - [ ] **NEW (V9):** Test `plan_id` handling in `check_micro_conditions()`
  - [ ] **NEW (V9):** Test snapshot data extraction from `regime_result`
  - [ ] **NEW (V9):** Test trade idea validation (required fields check)
  - [ ] **NEW (V10):** Test `_check_compression_block_mtf()` error handling (malformed M5 candles)

- [ ] **Integration testing**
  - [ ] Test full flow: snapshot → regime → strategy → validation → trade idea
  - [ ] Test fallback to `edge_based` when regime detection fails
  - [ ] Test error handling in `_get_strategy_checker()`
  - [ ] Test M5/M15 data fetching in `_build_snapshot()`
  - [ ] **NEW (V9):** Test `plan_id` propagation through entire flow
  - [ ] **NEW (V9):** Test snapshot contains extracted characteristics from `regime_result`
  - [ ] **NEW (V9):** Test trade idea validation rejects malformed trade ideas
  - [ ] **NEW (V10):** Test helper method inheritance (strategy checkers can call base methods)

### **Priority 7: Documentation**

- [ ] **Update code docstrings**
  - [ ] Document new `__init__()` parameters
  - [ ] Document new methods (`_get_strategy_checker()`, `_candle_to_dict()`)
  - [ ] Document strategy checker interface

- [ ] **Update README or user docs**
  - [ ] Explain adaptive strategy selection
  - [ ] Document configuration options
  - [ ] Explain fallback behavior

---

## 📦 Phase 0: Foundation & Analysis

### 0.1 Existing Component Audit ✅

**Status:** COMPLETE - Components identified

**Existing Components to Leverage:**

1. **`infra/m1_microstructure_analyzer.py`** - `M1MicrostructureAnalyzer`
   - ✅ CHOCH detection (`structure.choch_detected`, `choch_bars_ago`)
   - ✅ Equal highs/lows (`liquidity_zones.equal_highs_detected`, `equal_lows_detected`)
   - ✅ PDH/PDL detection (`liquidity_zones`)
   - ✅ VWAP calculation (`vwap.value`, `vwap.std`)
   - ✅ Liquidity state (`calculate_liquidity_state()`)

2. **`infra/vwap_micro_filter.py`** - `VWAPMicroFilter`
   - ✅ VWAP proximity (`is_price_near_vwap()`)
   - ✅ VWAP band calculation (`calculate_vwap_band()`)
   - ✅ VWAP retest detection (`detect_vwap_retest()`)
   - ⚠️ **MISSING**: VWAP slope calculation (needs implementation)
   - ⚠️ **MISSING**: VWAP deviation in standard deviations (needs enhancement)

3. **`infra/micro_liquidity_sweep_detector.py`** - `MicroLiquiditySweepDetector`
   - ✅ Micro sweep detection (`detect_micro_sweep()`)
   - ✅ Sweep direction (from `MicroSweepResult`)

4. **`infra/range_boundary_detector.py`** - `RangeBoundaryDetector`
   - ✅ Range detection (`detect_range()`)
   - ✅ PDH/PDL range detection
   - ✅ M15 range detection
   - ✅ Critical gap zones

5. **`infra/micro_scalp_volatility_filter.py`** - `MicroScalpVolatilityFilter`
   - ✅ ATR(1) calculation (`calculate_atr1()`)
   - ✅ ATR(14) calculation (`calculate_atr14()`) ✅ COMPLETED - Added to class
   - ✅ Volatility expansion detection (`is_volatility_expanding()`)
   - ✅ M1 range average calculation

6. **`infra/spread_tracker.py`** - `SpreadTracker`
   - ✅ Spread tracking (`get_spread_data()`)
   - ✅ Spread ratio calculation

7. **`infra/micro_order_block_detector.py`** - `MicroOrderBlockDetector`
   - ✅ Micro OB detection (`detect_micro_obs()`)
   - ✅ OB retest detection

8. **`infra/micro_scalp_conditions.py`** - `MicroScalpConditionsChecker`
   - ✅ Base 4-layer validation structure
   - ✅ `ConditionCheckResult` dataclass
   - ✅ Pre-trade filters, location filter, signals, confluence scoring

### 0.2 Missing Components Identification

**Components to Create:**

1. **`infra/micro_scalp_regime_detector.py`** - NEW
   - Regime detection logic
   - VWAP deviation calculation (enhance existing)
   - VWAP slope calculation (new)
   - Range detection integration
   - Balanced zone detection

2. **`infra/micro_scalp_strategy_router.py`** - NEW
   - Strategy selection logic
   - Fallback handling
   - Strategy priority ordering

3. **`infra/micro_scalp_strategies/vwap_reversion_checker.py`** - NEW
   - VWAP reversion-specific 4-layer validation
   - Strategy-specific trade idea generation

4. **`infra/micro_scalp_strategies/range_scalp_checker.py`** - NEW
   - Range scalp-specific 4-layer validation
   - Strategy-specific trade idea generation

5. **`infra/micro_scalp_strategies/balanced_zone_checker.py`** - NEW
   - Balanced zone-specific 4-layer validation
   - Strategy-specific trade idea generation

6. **`infra/micro_scalp_strategies/edge_based_checker.py`** - REFACTOR
   - Move current `MicroScalpConditionsChecker` logic here
   - Keep as fallback strategy

---

## 📦 Phase 0.5: Data Access Enhancement (NEW - Critical Fix)

### 0.5.1 Enhance `MicroScalpEngine._build_snapshot()`

**File:** `infra/micro_scalp_engine.py`

**Changes Required:**

1. **Add M5/M15 data to snapshot:**
```python
def _build_snapshot(self, symbol: str) -> Optional[Dict[str, Any]]:
    """
    Build data snapshot for condition checking.
    
    ENHANCED: Now includes M5/M15 candles and VWAP std for regime detection.
    """
    try:
        # ... existing M1 candle fetching ...
        
        # NEW: Fetch M5 and M15 candles from streamer
        m5_candles = None
        m15_candles = None
        # FIXED: Check if streamer is available and running
        if self.streamer and self.streamer.is_running:
            try:
                m5_candles_objects = self.streamer.get_candles(symbol_norm, 'M5', limit=10)
                m15_candles_objects = self.streamer.get_candles(symbol_norm, 'M15', limit=20)
                
                # Convert Candle objects to dicts
                if m5_candles_objects:
                    m5_candles = [self._candle_to_dict(c) for c in m5_candles_objects]
                else:
                    logger.debug(f"No M5 candles available for {symbol_norm}")
                    m5_candles = None
                
                if m15_candles_objects:
                    m15_candles = [self._candle_to_dict(c) for c in m15_candles_objects]
                else:
                    logger.debug(f"No M15 candles available for {symbol_norm}")
                    m15_candles = None
            except Exception as e:
                logger.debug(f"Error fetching M5/M15 candles: {e}")
                m5_candles = None
                m15_candles = None
        else:
            logger.debug(f"Streamer not available or not running for {symbol_norm}")
            m5_candles = None
            m15_candles = None
        
        # NEW: Get VWAP std from M1MicrostructureAnalyzer
        vwap_std = None
        if self.m1_analyzer:
            try:
                analysis = self.m1_analyzer.analyze_microstructure(symbol_norm, candles)
                vwap_data = analysis.get('vwap', {})
                if isinstance(vwap_data, dict):
                    vwap_std = vwap_data.get('std', 0.0)
                else:
                    # Fallback: calculate from candles
                    vwap_std = self._calculate_vwap_std(candles, vwap)
            except Exception as e:
                logger.debug(f"Error getting VWAP std: {e}")
                vwap_std = self._calculate_vwap_std(candles, vwap)
        else:
            vwap_std = self._calculate_vwap_std(candles, vwap)
        
        # Calculate ATR14 (memoized - calculate once per snapshot)
        atr14 = None
        if candles and len(candles) >= 14:
            atr14 = self.volatility_filter.calculate_atr14(candles[-14:])
        
        snapshot = {
            'symbol': symbol_norm,
            'candles': candles,
            'current_price': current_price,
            'bid': quote.bid,
            'ask': quote.ask,
            'vwap': vwap,
            'vwap_std': vwap_std,  # NEW
            'atr1': atr1,
            'atr14': atr14,  # NEW: Memoized ATR14 for regime detection
            'm5_candles': m5_candles,  # NEW
            'm15_candles': m15_candles,  # NEW
            'spread_data': spread_data,
            'btc_order_flow': btc_order_flow,
            'timestamp': datetime.now()
        }
        
        return snapshot
    except Exception as e:
        logger.error(f"Error building snapshot for {symbol}: {e}", exc_info=True)
        return None

def _candle_to_dict(self, candle) -> Dict[str, Any]:
    """
    Convert streamer candle object to dict.
    
    Handles both dict and object types from MultiTimeframeStreamer.
    """
    if isinstance(candle, dict):
        return candle
    
    # Assume object with attributes (from MultiTimeframeStreamer)
    return {
        'time': getattr(candle, 'time', None),
        'open': getattr(candle, 'open', 0.0),
        'high': getattr(candle, 'high', 0.0),
        'low': getattr(candle, 'low', 0.0),
        'close': getattr(candle, 'close', 0.0),
        'volume': getattr(candle, 'volume', 0),
        'spread': getattr(candle, 'spread', 0),
        'real_volume': getattr(candle, 'real_volume', 0)
    }
    """Convert Candle object to dict"""
    if isinstance(candle, dict):
        return candle
    elif hasattr(candle, 'to_dict'):
        return candle.to_dict()
    elif hasattr(candle, '__dict__'):
        return candle.__dict__
    else:
        # Try to extract common fields
        return {
            'time': getattr(candle, 'time', None),
            'open': getattr(candle, 'open', 0),
            'high': getattr(candle, 'high', 0),
            'low': getattr(candle, 'low', 0),
            'close': getattr(candle, 'close', 0),
            'volume': getattr(candle, 'volume', 0)
        }
```

### 0.5.2 Add ATR(14) Calculation to `MicroScalpVolatilityFilter`

**File:** `infra/micro_scalp_volatility_filter.py`

**Add Method:**

```python
def calculate_atr14(self, candles: List[Dict[str, Any]]) -> float:
    """
    Calculate ATR(14) from M1 candles.
    
    Args:
        candles: List of M1 candle dicts
    
    Returns:
        ATR(14) value
    """
    if len(candles) < 15:
        return 0.0
    
    # Calculate True Range for last 14 candles
    true_ranges = []
    period = min(14, len(candles) - 1)
    
    for i in range(max(1, len(candles) - period), len(candles)):
        high = candles[i].get('high', 0)
        low = candles[i].get('low', 0)
        prev_close = candles[i-1].get('close', 0) if i > 0 else candles[i].get('open', 0)
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
    
    if not true_ranges:
        return 0.0
    
    return statistics.mean(true_ranges)
```

---

## 📐 Phase 1: Regime Detection System

### 1.1 Create `MicroScalpRegimeDetector`

**File:** `infra/micro_scalp_regime_detector.py`

**Dependencies:**
- `M1MicrostructureAnalyzer` (existing)
- `VWAPMicroFilter` (existing, needs enhancement)
- `RangeBoundaryDetector` (existing)
- `MicroScalpVolatilityFilter` (existing)
- `MultiTimeframeStreamer` (existing) - **NEW**: For M5/M15 data access
- `NewsService` (existing) - **NEW**: For balanced zone news checks
- `MT5Service` (existing) - **NEW**: For M15 trend checking

**Key Methods:**

```python
import logging
from typing import Dict, Any, List, Optional
import statistics

logger = logging.getLogger(__name__)

class MicroScalpRegimeDetector:
    def __init__(self, config, m1_analyzer, vwap_filter, range_detector, volatility_filter,
                 streamer=None, news_service=None, mt5_service=None):
        """Initialize regime detector with existing components"""
        self.config = config
        self.m1_analyzer = m1_analyzer
        self.vwap_filter = vwap_filter
        self.range_detector = range_detector
        self.volatility_filter = volatility_filter
        self.streamer = streamer  # NEW: For M5/M15 data
        self.news_service = news_service  # NEW: For news checks
        self.mt5_service = mt5_service  # NEW: For M15 trend
        # ENHANCED: Regime caching to prevent excessive switching
        self.regime_cache: Dict[str, List[Dict[str, Any]]] = {}  # symbol -> [regime1, regime2, regime3]
        self.cache_size = 3  # 3-bar memory
        self._current_snapshot = None  # Store current snapshot for helper methods
    
    def detect_regime(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect current market regime.
        
        ENHANCED: Uses cached rolling regime (3-bar memory) to prevent excessive switching.
        Only switches regime if new detection is consistent for 2+ bars.
        
        Returns:
        {
            "regime": "VWAP_REVERSION" | "RANGE" | "BALANCED_ZONE" | "UNKNOWN",
            "confidence": 0-100,
            "characteristics": {
                "vwap_deviation": float,
                "vwap_slope": float,
                "range_detected": bool,
                "compression_detected": bool,
                ...
            },
            "strategy_hint": str,
            "cached": bool,  # Whether cached regime was used
            "cache_consistency": int  # Number of bars with same regime
        }
        """
        symbol = snapshot.get('symbol', '')
        
        # Check cached regime first (latency optimization)
        cached_regime = self._get_cached_regime(symbol)
        if cached_regime:
            # Only use cache if it's consistent (2+ bars)
            if cached_regime.get('cache_consistency', 0) >= 2:
                return cached_regime
        
        # Perform fresh detection
        regime_result = self._detect_regime_fresh(snapshot)
        
        # Update cache
        self._update_regime_cache(symbol, regime_result)
        
        return regime_result
    
    def _detect_regime_fresh(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform fresh regime detection (uncached).
        
        Checks all three regimes and selects highest priority detected regime.
        Priority: VWAP_REVERSION > RANGE > BALANCED_ZONE
        """
        # Store snapshot for helper methods
        self._current_snapshot = snapshot
        
        # Check all regimes
        vwap_result = self._detect_vwap_reversion(snapshot)
        range_result = self._detect_range(snapshot)
        balanced_result = self._detect_balanced_zone(snapshot)
        
        # Priority ordering: VWAP Reversion > Range > Balanced Zone
        # Select highest priority detected regime
        candidates = []
        
        if vwap_result.get('detected') and vwap_result.get('confidence', 0) >= vwap_result.get('min_confidence_threshold', 70):
            candidates.append(('VWAP_REVERSION', vwap_result))
        
        if range_result.get('detected') and range_result.get('confidence', 0) >= range_result.get('min_confidence_threshold', 55):
            candidates.append(('RANGE', range_result))
        
        if balanced_result.get('detected') and balanced_result.get('confidence', 0) >= balanced_result.get('min_confidence_threshold', 65):
            candidates.append(('BALANCED_ZONE', balanced_result))
        
        if not candidates:
            # Use edge_based threshold from config
            edge_threshold = self.config.get('regime_detection', {}).get('strategy_confidence_thresholds', {}).get('edge_based', 60)
            return {
                'regime': 'UNKNOWN',
                'confidence': 0,
                'characteristics': {},
                'strategy_hint': 'edge_based',
                'min_confidence_threshold': edge_threshold
            }
        
        # Select highest priority (first in list = highest priority)
        selected_regime, selected_result = candidates[0]
        
        # Use edge_based threshold as fallback
        edge_threshold = self.config.get('regime_detection', {}).get('strategy_confidence_thresholds', {}).get('edge_based', 60)
        return {
            'regime': selected_regime,
            'confidence': selected_result.get('confidence', 0),
            'characteristics': selected_result,
            'strategy_hint': selected_regime.lower().replace('_', '_'),
            'min_confidence_threshold': selected_result.get('min_confidence_threshold', edge_threshold)
        }
    
    def _detect_vwap_reversion(self, snapshot) -> Dict[str, Any]:
        """Check if VWAP reversion conditions are met"""
    
    def _detect_range(self, snapshot) -> Dict[str, Any]:
        """Check if range conditions are met"""
    
    def _get_cached_regime(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get cached regime from rolling memory (3-bar).
        
        Returns cached regime if:
        - Cache exists for symbol
        - Cache has 2+ consistent entries
        - Confidence is still above threshold
        - Cache is not stale
        """
        if symbol not in self.regime_cache:
            return None
        
        cache = self.regime_cache[symbol]
        if len(cache) < 2:
            return None
        
        # Check consistency (same regime in last 2+ bars)
        last_regime = cache[-1].get('regime')
        consistent_count = sum(1 for entry in cache if entry.get('regime') == last_regime)
        
        # Only use cache if consistent AND confidence is still high
        if consistent_count >= 2:
            last_confidence = cache[-1].get('confidence', 0)
            min_confidence = cache[-1].get('min_confidence_threshold', 60)
            
            # If confidence dropped below threshold, invalidate cache
            if last_confidence < min_confidence:
                logger.debug(f"Cache invalidated: confidence {last_confidence} < {min_confidence}")
                return None
            
            return {
                **cache[-1],
                'cached': True,
                'cache_consistency': consistent_count
            }
        
        return None
    
    def _update_regime_cache(self, symbol: str, regime_result: Dict[str, Any]):
        """Update rolling regime cache (3-bar memory)"""
        if symbol not in self.regime_cache:
            self.regime_cache[symbol] = []
        
        # Add timestamp for expiration tracking
        from datetime import datetime
        regime_result['cache_timestamp'] = datetime.now()
        
        cache = self.regime_cache[symbol]
        cache.append(regime_result)
        
        # Keep only last N entries
        if len(cache) > self.cache_size:
            cache.pop(0)
        
        # Optional: Invalidate cache on regime change for faster adaptation
        # Uncomment if needed for more responsive regime switching
        # if len(cache) >= 2:
        #     prev_regime = cache[-2].get('regime')
        #     curr_regime = cache[-1].get('regime')
        #     if prev_regime != curr_regime:
        #         logger.debug(f"Regime changed: {prev_regime} -> {curr_regime}")
    
    def _detect_balanced_zone(self, snapshot) -> Dict[str, Any]:
        """Check if balanced zone conditions are met"""
```

**Implementation Details:**

#### VWAP Reversion Detection Logic:
```python
def _detect_vwap_reversion(self, snapshot):
    symbol = snapshot['symbol']
    current_price = snapshot['current_price']
    vwap = snapshot['vwap']
    candles = snapshot['candles']
    atr1 = snapshot.get('atr1')
    
    # 1. Calculate VWAP deviation
    # Use existing VWAP std from M1MicrostructureAnalyzer or calculate
    vwap_std = snapshot.get('vwap_std') or self._calculate_vwap_std(candles, vwap)
    
    if vwap_std == 0:
        return {'detected': False, 'confidence': 0}
    
    deviation_sigma = abs(current_price - vwap) / vwap_std
    
    # Symbol-specific thresholds
    if symbol.upper().startswith('BTC'):
        min_deviation = 2.0  # 2σ
        min_deviation_pct = 0.005  # 0.5%
    else:  # XAU
        min_deviation = 2.0  # 2σ
        min_deviation_pct = 0.002  # 0.20%
    
    # RECOMMENDED: VWAP Z > 2 → VWAP Reversion
    # Check deviation threshold (Z-score takes priority)
    deviation_pct = abs(current_price - vwap) / vwap if vwap > 0 else 0
    deviation_ok = deviation_sigma >= min_deviation or deviation_pct >= min_deviation_pct
    
    if not deviation_ok:
        return {'detected': False, 'confidence': 0, 'min_confidence_threshold': 70, 'reason': f'deviation_sigma {deviation_sigma:.2f} < {min_deviation}'}
    
    # 2. Check volume spike
    volume_spike = self._check_volume_spike(candles)
    
    # 3. Check VWAP slope (not strongly trending)
    # ENHANCED: Dynamic slope normalization by ATR for scaling across assets
    vwap_slope = self._calculate_vwap_slope(candles, vwap)
    # Normalize slope by ATR for BTC volatility
    if atr1 and atr1 > 0:
        vwap_slope_normalized = abs(vwap_slope) / atr1
        max_slope_normalized = 0.1  # 10% of ATR per bar (configurable)
        max_slope_check = vwap_slope_normalized < max_slope_normalized
    else:
        # Fallback to fixed threshold if ATR unavailable
        max_slope = 0.0001  # Configurable
        max_slope_check = abs(vwap_slope) < max_slope
    
    # 4. Check ATR stability (not collapsing)
    # FIXED: Use snapshot for memoized ATR14
    atr_stable = self._check_atr_stability(candles, snapshot)
    
    # Calculate confidence
    confidence = 0
    if deviation_sigma >= min_deviation:
        confidence += 40
    if volume_spike:
        confidence += 20
    if max_slope_check:
        confidence += 20
    if atr_stable:
        confidence += 20
    
    # Strategy-specific confidence thresholds (from config with fallback)
    min_confidence = self.config.get('regime_detection', {}).get('strategy_confidence_thresholds', {}).get('vwap_reversion', 70)
    
    return {
        'detected': confidence >= min_confidence,
        'confidence': confidence,
        'deviation_sigma': deviation_sigma,
        'deviation_pct': deviation_pct,
        'vwap_slope': vwap_slope,
        'volume_spike': volume_spike,
        'atr_stable': atr_stable,
        'min_confidence_threshold': min_confidence
    }
```

#### Range Detection Logic:
```python
def _detect_range(self, snapshot):
    symbol = snapshot['symbol']
    candles = snapshot['candles']
    current_price = snapshot['current_price']
    
    # Use existing RangeBoundaryDetector with M15 data
    # Get M15 candles from snapshot (enhanced snapshot includes M15)
    m15_candles = snapshot.get('m15_candles', [])
    if m15_candles:
        m15_df = self._candles_to_df(m15_candles)
    else:
        # Fallback to M1 candles if M15 unavailable
        m15_df = self._candles_to_df(candles)
    
    range_structure = self.range_detector.detect_range(
        symbol=symbol,
        timeframe="M15",
        range_type="dynamic",
        candles_df=m15_df,  # Use M15 DataFrame
        vwap=snapshot.get('vwap'),
        atr=snapshot.get('atr1')
    )
    
    if not range_structure:
        # Try PDH/PDL from M1MicrostructureAnalyzer
        if self.m1_analyzer:
            analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
            liquidity_zones = analysis.get('liquidity_zones', {})
            pdh = liquidity_zones.get('pdh')
            pdl = liquidity_zones.get('pdl')
            
            if pdh and pdl:
                range_structure = self._create_range_from_pdh_pdl(pdh, pdl, snapshot)
    
    if not range_structure:
        return {'detected': False, 'confidence': 0, 'min_confidence_threshold': 55}
    
    # Check if price is at range edge
    range_high = range_structure.range_high
    range_low = range_structure.range_low
    range_width = range_high - range_low
    
    # RECOMMENDED: Range width < 1.2 × ATR → Range Scalp
    # Use ATR14 if available, fallback to ATR1
    atr14 = snapshot.get('atr14')
    atr1 = snapshot.get('atr1')
    atr_for_comparison = atr14 if atr14 and atr14 > 0 else atr1 if atr1 and atr1 > 0 else None
    
    if atr_for_comparison:
        range_width_atr_ratio = range_width / atr_for_comparison
        # Range must be tight (compressed) - width < 1.2 × ATR
        if range_width_atr_ratio >= 1.2:
            # Range too wide, not suitable for range scalping
            return {'detected': False, 'confidence': 0, 'min_confidence_threshold': 55, 'reason': f'range_width_atr_ratio {range_width_atr_ratio:.2f} >= 1.2'}
    
    # Check if price is near edge (within 0.5% of range width)
    tolerance = range_width * 0.005
    near_high = abs(current_price - range_high) <= tolerance
    near_low = abs(current_price - range_low) <= tolerance
    
    if not (near_high or near_low):
        return {'detected': False, 'confidence': 0, 'min_confidence_threshold': 55}
    
    # Check volatility compression (BB width)
    bb_compression = self._check_bb_compression(candles)
    
    # Check range respect (bounces at edges)
    range_respects = self._count_range_respects(candles, range_high, range_low)
    
    # Check M15 trend (should be neutral)
    m15_trend = self._check_m15_trend(symbol, snapshot)
    
    confidence = 0
    if near_high or near_low:
        confidence += 30
    if range_respects >= 2:
        confidence += 30
    if bb_compression:
        confidence += 20
    if m15_trend == 'NEUTRAL':
        confidence += 20
    
    # Strategy-specific confidence thresholds (from config with fallback)
    min_confidence = self.config.get('regime_detection', {}).get('strategy_confidence_thresholds', {}).get('range_scalp', 55)
    
    return {
        'detected': confidence >= min_confidence,
        'confidence': confidence,
        'range_structure': range_structure,
        'near_edge': 'high' if near_high else 'low' if near_low else None,
        'range_respects': range_respects,
        'min_confidence_threshold': min_confidence
    }
```

#### Balanced Zone Detection Logic:
```python
def _detect_balanced_zone(self, snapshot):
    """
    Detect Balanced Zone regime.
    
    Key Logic:
    - BB width < 0.02 (2% of price) → Balanced Zone regime
    - Confidence: 65% minimum
    """
    symbol = snapshot['symbol']
    candles = snapshot['candles']
    current_price = snapshot['current_price']
    vwap = snapshot.get('vwap')
    atr1 = snapshot.get('atr1')
    
    # 1. Check compression block (inside bars)
    # ENHANCED: M1-M5 multi-timeframe compression confirmation
    # Get M5 candles from snapshot (enhanced snapshot includes M5)
    m5_candles = snapshot.get('m5_candles', [])
    compression = self._check_compression_block_mtf(candles, m5_candles, snapshot)
    
    # RECOMMENDED: BB width < 0.02 (2% of price) → Balanced Zone
    # Check BB compression first (primary indicator)
    bb_compression = self._check_bb_compression(candles)
    if not bb_compression:
        # BB width too wide, not balanced
        return {'detected': False, 'confidence': 0, 'min_confidence_threshold': 65, 'reason': 'bb_width_too_wide'}
    
    # 2. Check news blackout (before other checks to save computation)
    news_blackout_minutes = self.config.get('regime_detection', {}).get('balanced_zone', {}).get('news_blackout_minutes', 15)
    news_ok = True
    if self.news_service:
        try:
            from datetime import datetime
            now = datetime.utcnow()
            
            # Check for macro news
            # FIXED: NewsService.is_blackout() accepts optional 'now' parameter
            # Actual signature: is_blackout(category: str, now: Optional[datetime] = None) -> bool
            macro_blackout = self.news_service.is_blackout(category="macro", now=now)
            if macro_blackout:
                news_ok = False
            
            # Check for crypto news (if BTC)
            if symbol.upper().startswith('BTC'):
                crypto_blackout = self.news_service.is_blackout(category="crypto", now=now)
                if crypto_blackout:
                    news_ok = False
        except Exception as e:
            logger.debug(f"Error checking news blackout: {e}")
            news_ok = True  # Default to OK on error
    
    if not news_ok:
        return {'detected': False, 'confidence': 0, 'reason': 'news_blackout', 'min_confidence_threshold': 65}
    
    # 3. Check equal highs/lows
    if self.m1_analyzer:
        analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
        liquidity_zones = analysis.get('liquidity_zones', {})
        equal_highs = liquidity_zones.get('equal_highs_detected', False)
        equal_lows = liquidity_zones.get('equal_lows_detected', False)
    else:
        equal_highs = equal_lows = False
    
    # 4. Check VWAP + mid-range alignment
    vwap_alignment = False
    if vwap and len(candles) >= 20:
        intraday_high = max(c.get('high', 0) for c in candles[-20:])
        intraday_low = min(c.get('low', 0) for c in candles[-20:])
        mid_range = (intraday_high + intraday_low) / 2
        vwap_alignment = abs(vwap - mid_range) / mid_range < 0.001  # Within 0.1%
    
    # 5. Check ATR dropping (compression)
    # FIXED: Use snapshot for memoized ATR14
    atr_dropping = self._check_atr_dropping(candles, snapshot)
    
    # 6. Check choppy liquidity (wicks but no displacement)
    choppy_liquidity = self._check_choppy_liquidity(candles)
    
    confidence = 0
    if compression:
        confidence += 25
    if equal_highs or equal_lows:
        confidence += 25
    if vwap_alignment:
        confidence += 20
    if atr_dropping:
        confidence += 15
    if choppy_liquidity:
        confidence += 15
    
    # Strategy-specific confidence thresholds (from config with fallback)
    min_confidence = self.config.get('regime_detection', {}).get('strategy_confidence_thresholds', {}).get('balanced_zone', 65)
    
    return {
        'detected': confidence >= min_confidence,
        'confidence': confidence,
        'compression': compression,
        'equal_highs': equal_highs,
        'equal_lows': equal_lows,
        'vwap_alignment': vwap_alignment,
        'atr_dropping': atr_dropping,
        'min_confidence_threshold': min_confidence
    }
```

**Direction Helper Methods:**

```python
# In VWAPReversionChecker
def _get_direction_from_choch(self, symbol: str, candles: List[Dict], vwap: float, current_price: float) -> str:
    """Extract direction from CHOCH signal"""
    if not self.m1_analyzer:
        # Fallback: use price position relative to VWAP
        return 'BUY' if current_price < vwap else 'SELL'
    
    try:
        analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
        # FIXED: CHOCH is in choch_bos dict, not structure
        choch_bos = analysis.get('choch_bos', {})
        choch_detected = choch_bos.get('has_choch', False) or choch_bos.get('choch_confirmed', False)
        choch_direction = choch_bos.get('direction', '')  # 'BULLISH' or 'BEARISH'
        
        if choch_detected:
            if choch_direction == 'BULLISH' or 'bull' in str(choch_direction).lower():
                return 'BUY'
            elif choch_direction == 'BEARISH' or 'bear' in str(choch_direction).lower():
                return 'SELL'
        
        # Fallback: use price position relative to VWAP
        if current_price < vwap:
            return 'BUY'  # Price below VWAP, expect reversion up
        else:
            return 'SELL'  # Price above VWAP, expect reversion down
    except Exception as e:
        logger.debug(f"Error getting direction from CHOCH: {e}")
        # Fallback
        return 'BUY' if current_price < vwap else 'SELL'

# In BalancedZoneChecker
def _get_fade_direction(self, candles: List[Dict], current_price: float) -> str:
    """Determine fade direction (opposite of mini-extreme)"""
    if len(candles) < 5:
        return 'UNKNOWN'
    
    # Find mini-extreme (recent high or low)
    recent_high = max(c.get('high', current_price) for c in candles[-5:])
    recent_low = min(c.get('low', current_price) for c in candles[-5:])
    
    # Check which extreme is closer
    distance_to_high = abs(recent_high - current_price)
    distance_to_low = abs(current_price - recent_low)
    
    if distance_to_high < distance_to_low:
        # Near high, fade down (SELL)
        return 'SELL'
    else:
        # Near low, fade up (BUY)
        return 'BUY'

def _get_breakout_direction(self, candles: List[Dict]) -> str:
    """Determine breakout direction from compression"""
    if len(candles) < 3:
        return 'UNKNOWN'
    
    # Check if price broke above or below compression range
    compression_high = max(c.get('high', 0) for c in candles[-3:])
    compression_low = min(c.get('low', 0) for c in candles[-3:])
    last_close = candles[-1].get('close', 0)
    
    # Check breakout direction
    if last_close > compression_high:
        return 'BUY'
    elif last_close < compression_low:
        return 'SELL'
    else:
        # No breakout yet, use momentum
        if len(candles) >= 2:
            if candles[-1].get('close', 0) > candles[-2].get('close', 0):
                return 'BUY'
            else:
                return 'SELL'
        return 'UNKNOWN'
```

**Helper Methods Needed:**
- ✅ `_calculate_vwap_std()` - Calculate VWAP standard deviation (IMPLEMENTED - see below)
- ✅ `_calculate_vwap_slope()` - Calculate VWAP slope over last N candles (ATR-normalized) (IMPLEMENTED - see below)
- ✅ `_check_volume_spike()` - Check if volume ≥ 1.3× 10-bar average (IMPLEMENTED - see below)
- ✅ `_check_atr_stability()` - Check if ATR(14) stable or rising (IMPLEMENTED - see below)
- ❌ `_check_bb_compression()` - Check Bollinger Band width contracting (**MISSING - needs implementation**)
- ❌ `_count_range_respects()` - Count bounces at range edges (**MISSING - needs implementation**)
- ❌ `_check_m15_trend()` - Check M15 trend (should be neutral) (**MISSING - needs implementation**)
- ✅ `_check_compression_block()` - Check for inside bars / tight structure (M1 only) (IMPLEMENTED - see below)
- ✅ `_check_compression_block_mtf()` - **ENHANCED**: M1-M5 multi-timeframe compression confirmation (IMPLEMENTED - see below)
- ✅ `_check_atr_dropping()` - Check if ATR is decreasing (IMPLEMENTED - see below)
- ✅ `_check_choppy_liquidity()` - Check for wicks without displacement (IMPLEMENTED - see below)
- ✅ `_candles_to_df()` - Convert candle list to DataFrame (with datetime index) (IMPLEMENTED - see below)
- ✅ `_get_cached_regime()` - Get cached regime from rolling memory (3-bar) (IMPLEMENTED - see below)
- ✅ `_update_regime_cache()` - Update rolling regime cache (IMPLEMENTED - see below)
- ✅ `_calculate_vwap_from_candles()` - Calculate VWAP from candle list (helper for slope) (IMPLEMENTED - see below)
- ✅ `_create_range_from_pdh_pdl()` - Create RangeStructure from PDH/PDL (IMPLEMENTED - see below)

**Helper Method Implementations:**

```python
def _candles_to_df(self, candles: List[Dict[str, Any]]) -> Optional[pd.DataFrame]:
    """Convert candle list to DataFrame with datetime index"""
    if not candles:
        return None
    
    try:
        import pandas as pd
        
        # Extract data
        times = []
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []
        
        for candle in candles:
            # Handle different time formats
            time_val = candle.get('time')
            if isinstance(time_val, (int, float)):
                # Unix timestamp
                times.append(pd.Timestamp.fromtimestamp(time_val, tz='UTC'))
            elif isinstance(time_val, str):
                times.append(pd.Timestamp(time_val))
            elif hasattr(time_val, 'timestamp'):
                times.append(pd.Timestamp.fromtimestamp(time_val.timestamp(), tz='UTC'))
            else:
                times.append(pd.Timestamp.now(tz='UTC'))
            
            opens.append(candle.get('open', 0))
            highs.append(candle.get('high', 0))
            lows.append(candle.get('low', 0))
            closes.append(candle.get('close', 0))
            volumes.append(candle.get('volume', 0))
        
        df = pd.DataFrame({
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        }, index=times)
        
        return df
    except Exception as e:
        logger.error(f"Error converting candles to DataFrame: {e}")
        return None

def _calculate_vwap_slope(self, candles: List[Dict[str, Any]], vwap: float) -> float:
    """Calculate VWAP slope over last N candles"""
    if len(candles) < 5 or vwap == 0:
        return 0.0
    
    # Calculate VWAP for last 5 candles and previous 5 candles
    recent_candles = candles[-5:]
    previous_candles = candles[-10:-5] if len(candles) >= 10 else candles[:5]
    
    # Calculate VWAP for each period
    recent_vwap = self._calculate_vwap_from_candles(recent_candles)
    previous_vwap = self._calculate_vwap_from_candles(previous_candles)
    
    if previous_vwap == 0:
        return 0.0
    
    # Slope = (recent_vwap - previous_vwap) / previous_vwap
    # Normalized by price to get percentage change
    slope = (recent_vwap - previous_vwap) / previous_vwap
    
    return slope

def _calculate_vwap_from_candles(self, candles: List[Dict[str, Any]]) -> float:
    """Calculate VWAP from candle list (helper)"""
    if not candles:
        return 0.0
    
    total_pv = 0.0
    total_volume = 0.0
    
    for candle in candles:
        high = candle.get('high', 0)
        low = candle.get('low', 0)
        close = candle.get('close', 0)
        volume = candle.get('volume', 0)
        
        if volume <= 0:
            continue
        
        typical_price = (high + low + close) / 3
        total_pv += typical_price * volume
        total_volume += volume
    
    if total_volume == 0:
        return 0.0
    
    return total_pv / total_volume

def _check_m15_trend(self, symbol: str, snapshot: Dict[str, Any]) -> str:
    """Check M15 trend (should be neutral for range trading)"""
    # Get M15 candles from snapshot
    m15_candles = snapshot.get('m15_candles', [])
    if m15_candles and len(m15_candles) >= 20:
        m15_df = self._candles_to_df(m15_candles)
        if m15_df is not None:
            # Calculate ADX or use structure detection
            try:
                # Use existing structure detection if available
                # For simplicity, check if price is in a range
                recent_high = m15_df['high'].tail(10).max()
                recent_low = m15_df['low'].tail(10).min()
                range_width = recent_high - recent_low
                current_price = snapshot.get('current_price', 0)
                
                if range_width > 0:
                    # Check if range is tight (neutral) or wide (trending)
                    atr = snapshot.get('atr1', 0)
                    if atr > 0:
                        range_atr_ratio = range_width / atr
                        # If range is less than 3x ATR, consider it neutral
                        if range_atr_ratio < 3.0:
                            return 'NEUTRAL'
                        else:
                            # Check direction
                            if m15_df['close'].iloc[-1] > m15_df['close'].iloc[-10]:
                                return 'UP'
                            else:
                                return 'DOWN'
            except Exception as e:
                logger.debug(f"Error checking M15 trend: {e}")
    
    # Fallback: Use MT5Service to get M15 bars and calculate ADX
    if self.mt5_service:
        try:
            m15_bars = self.mt5_service.get_bars(symbol, 'M15', 50)
            if m15_bars is not None and len(m15_bars) >= 20:
                # Calculate ADX (simplified - use existing ADX calculation if available)
                max_adx = self.config.get('regime_detection', {}).get('range_scalp', {}).get('m15_trend_max_adx', 20)
                # For now, return UNKNOWN if can't calculate ADX
                # TODO: Implement ADX calculation or use existing indicator
                return 'UNKNOWN'
        except Exception as e:
            logger.debug(f"Error checking M15 trend via MT5: {e}")
    
    return 'UNKNOWN'  # Default to unknown if can't determine

def _check_atr_stability(self, candles: List[Dict[str, Any]], snapshot: Dict[str, Any]) -> bool:
    """Check if ATR(14) is stable or rising using memoized ATR14"""
    # Use memoized ATR14 from snapshot if available
    atr14_recent = snapshot.get('atr14')
    
    if not atr14_recent or len(candles) < 28:
        return False
    
    # Calculate previous period ATR14
    previous_candles = candles[-28:-14] if len(candles) >= 28 else candles[:14]
    atr14_previous = self.volatility_filter.calculate_atr14(previous_candles)
    
    if atr14_previous <= 0:
        return atr14_recent > 0  # At least some volatility
    
    # Check if ATR is stable (within 10% of previous) or rising
    atr_ratio = atr14_recent / atr14_previous
    return 0.9 <= atr_ratio <= 1.5  # Stable or rising (not collapsing)

def _check_compression_block_mtf(self, m1_candles: List[Dict], m5_candles: Optional[List[Dict]], snapshot: Optional[Dict[str, Any]] = None) -> bool:
    """
    ENHANCED: M1-M5 multi-timeframe compression confirmation.
    
    Reduces false fades in low-volume sessions by requiring:
    - M1 inside bars / tight structure
    - M5 inside bars / tight structure (alignment)
    - Both timeframes showing compression
    
    Returns True only if both M1 and M5 show compression.
    """
    # Check M1 compression
    # FIXED: Pass atr1 from snapshot
    atr1 = snapshot.get('atr1') if snapshot else None
    m1_compression = self._check_compression_block(m1_candles, atr1)
    if not m1_compression:
        return False
    
    # Check M5 compression if available
    # FIXED: Validate m5_candles before processing
    if not m5_candles or not isinstance(m5_candles, list) or len(m5_candles) < 3:
        return m1_compression  # Fallback to M1 only if M5 unavailable
    
    # Convert M5 Candle objects to dicts with error handling
    m5_dicts = []
    for candle in m5_candles:
        try:
            if isinstance(candle, dict):
                m5_dicts.append(candle)
            elif hasattr(candle, 'to_dict'):
                candle_dict = candle.to_dict()
                if candle_dict and isinstance(candle_dict, dict):
                    m5_dicts.append(candle_dict)
            elif hasattr(candle, '__dict__'):
                candle_dict = candle.__dict__
                if candle_dict and isinstance(candle_dict, dict):
                    m5_dicts.append(candle_dict)
        except Exception as e:
            logger.debug(f"Error converting M5 candle to dict: {e}")
            continue  # Skip invalid candles
    
    if not m5_dicts:
        return m1_compression  # Fallback to M1 only if no valid M5 candles
    
    # Check M5 compression (inside bar alignment)
    m5_compression = self._check_compression_block(m5_dicts, atr1)
    
    # Both timeframes must show compression
    return m1_compression and m5_compression

def _check_compression_block(self, candles: List[Dict], atr1: Optional[float] = None) -> bool:
    """Check for inside bars / tight structure"""
    if len(candles) < 3:
        return False
    
    # Validate candle structure
    if not all(isinstance(c, dict) and 'high' in c and 'low' in c for c in candles):
        logger.warning("Invalid candle structure in compression check")
        return False
    
    # Check for inside bars (last 3 candles)
    inside_count = 0
    for i in range(max(1, len(candles) - 2), len(candles)):
        current = candles[i]
        previous = candles[i-1]
        
        current_high = current.get('high', 0)
        current_low = current.get('low', 0)
        previous_high = previous.get('high', 0)
        previous_low = previous.get('low', 0)
        
        # Inside bar: current high/low within previous high/low
        if current_high < previous_high and current_low > previous_low:
            inside_count += 1
    
    # Also check for tight range (small candle bodies)
    if len(candles) >= 5 and atr1:
        recent_candles = candles[-5:]
        avg_range = sum(c.get('high', 0) - c.get('low', 0) for c in recent_candles) / len(recent_candles)
        
        if atr1 > 0:
            # If average range is less than 0.5× ATR, consider it compressed
            if avg_range < atr1 * 0.5:
                return True
    
    # Return True if at least 2 inside bars in last 3 candles
    return inside_count >= 2

def _check_volume_spike(self, candles: List[Dict]) -> bool:
    """Check volume spike using configurable normalization method"""
    volume_normalization = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_normalization', 'multiplier')
    
    if volume_normalization == 'z_score':
        return self._check_volume_spike_zscore(candles)
    else:
        return self._check_volume_spike_multiplier(candles)

def _check_volume_spike_multiplier(self, candles: List[Dict]) -> bool:
    """Check if volume ≥ multiplier × 10-bar average"""
    if len(candles) < 11:
        return False
    
    last_volume = candles[-1].get('volume', 0)
    if last_volume == 0:
        return False
    
    recent_volumes = [c.get('volume', 0) for c in candles[-11:-1]]
    avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0
    
    if avg_volume == 0:
        return False
    
    volume_multiplier = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_spike_multiplier', 1.3)
    return last_volume >= avg_volume * volume_multiplier

def _check_volume_spike_zscore(self, candles: List[Dict]) -> bool:
    """Check volume spike using Z-score normalization (exchange-agnostic)"""
    if len(candles) < 31:
        # Fallback to multiplier if not enough data
        return self._check_volume_spike_multiplier(candles)
    
    last_volume = candles[-1].get('volume', 0)
    if last_volume == 0:
        return False
    
    recent_volumes = [c.get('volume', 0) for c in candles[-31:-1]]
    
    if not recent_volumes or all(v == 0 for v in recent_volumes):
        return False
    
    import statistics
    mean_volume = statistics.mean(recent_volumes)
    std_volume = statistics.stdev(recent_volumes) if len(recent_volumes) > 1 else 0
    
    if std_volume == 0:
        # Fallback to multiplier
        return self._check_volume_spike_multiplier(candles)
    
    z_score = (last_volume - mean_volume) / std_volume
    z_score_threshold = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_z_score_threshold', 1.5)
    
    return z_score >= z_score_threshold

def _check_bb_compression(self, candles: List[Dict]) -> bool:
    """
    Check if Bollinger Band width is contracting.
    
    RECOMMENDED: BB width < 0.02 (2% of price) → Balanced Zone
    
    Returns True if:
    - Recent BB width < 2% of price (absolute threshold)
    - OR Recent BB width < threshold × average (relative compression fallback)
    """
    if len(candles) < 20:
        return False
    
    try:
        import pandas as pd
        import numpy as np
        
        # Convert to DataFrame
        df = self._candles_to_df(candles)
        if df is None or len(df) < 20:
            return False
        
        # Calculate Bollinger Bands
        period = 20
        std_dev = 2.0
        
        close = df['close']
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        
        bb_upper = sma + (std * std_dev)
        bb_lower = sma - (std * std_dev)
        bb_width_pct = (bb_upper - bb_lower) / sma  # As decimal (0.02 = 2%)
        
        if len(bb_width_pct) < 5:
            return False
        
        # RECOMMENDED: Check absolute threshold first (BB width < 0.02 = 2%)
        recent_width_pct = bb_width_pct.iloc[-1]  # Most recent BB width
        if recent_width_pct < 0.02:  # 2% of price
            return True
        
        # Fallback: Check relative compression (recent < average)
        if len(bb_width_pct) >= 10:
            recent_avg = bb_width_pct.iloc[-5:].mean()
            avg_width = bb_width_pct.iloc[-20:].mean()
            
            if avg_width > 0:
                compression_threshold = self.config.get('regime_detection', {}).get('balanced_zone', {}).get('bb_compression_threshold', 0.9)
                compression_ratio = recent_avg / avg_width
                return compression_ratio < compression_threshold
        
        return False
    except Exception as e:
        logger.debug(f"Error checking BB compression: {e}")
        return False

def _check_atr_dropping(self, candles: List[Dict], snapshot: Dict[str, Any]) -> bool:
    """Check if ATR is decreasing using memoized ATR14"""
    # Use memoized ATR14 from snapshot
    atr14_recent = snapshot.get('atr14')
    
    if not atr14_recent or len(candles) < 28:
        return False
    
    # Calculate previous period ATR14
    previous_candles = candles[-28:-14] if len(candles) >= 28 else candles[:14]
    atr14_previous = self.volatility_filter.calculate_atr14(previous_candles)
    
    if atr14_previous <= 0:
        return False
    
    # Check if ATR is dropping
    atr_drop_threshold = self.config.get('regime_detection', {}).get('balanced_zone', {}).get('atr_drop_threshold', 0.8)
    atr_ratio = atr14_recent / atr14_previous
    
    # ATR dropping: recent < threshold × previous
    return atr_ratio < atr_drop_threshold

# NOTE: Duplicate _check_bb_compression() removed - use the implementation at line 1505

def _count_range_respects(self, candles: List[Dict[str, Any]], range_high: float, range_low: float) -> int:
    """Count how many times price bounced at range edges"""
    if len(candles) < 10 or range_high <= range_low:
        return 0
    
    range_width = range_high - range_low
    tolerance = range_width * 0.01  # 1% of range width
    
    respect_count = 0
    
    # Check last 20 candles for bounces
    for i in range(len(candles) - 1, max(0, len(candles) - 20), -1):
        candle = candles[i]
        high = candle.get('high', 0)
        low = candle.get('low', 0)
        
        # Check bounce at upper edge
        if abs(high - range_high) <= tolerance:
            # Check if next candle reversed (closed lower)
            if i < len(candles) - 1:
                next_candle = candles[i + 1]
                if next_candle.get('close', high) < high:
                    respect_count += 1
        
        # Check bounce at lower edge
        if abs(low - range_low) <= tolerance:
            # Check if next candle reversed (closed higher)
            if i < len(candles) - 1:
                next_candle = candles[i + 1]
                if next_candle.get('close', low) > low:
                    respect_count += 1
    
    return respect_count

def _check_m15_trend(self, symbol: str, snapshot: Dict[str, Any]) -> str:
    """Check M15 trend - should be NEUTRAL for range detection"""
    m15_candles = snapshot.get('m15_candles', [])
    
    if not m15_candles or len(m15_candles) < 20:
        return 'UNKNOWN'  # Cannot determine
    
    try:
        # Calculate simple trend from M15 candles
        recent_closes = [c.get('close', 0) for c in m15_candles[-20:]]
        
        if len(recent_closes) < 20 or any(c == 0 for c in recent_closes):
            return 'UNKNOWN'
        
        # Check if price is trending or ranging
        first_half = recent_closes[:10]
        second_half = recent_closes[10:]
        
        first_avg = sum(first_half) / len(first_half) if first_half else 0
        second_avg = sum(second_half) / len(second_half) if second_half else 0
        
        if first_avg == 0 or second_avg == 0:
            return 'UNKNOWN'
        
        # Calculate trend strength
        trend_pct = abs(second_avg - first_avg) / first_avg if first_avg > 0 else 0
        
        # If trend is weak (< 0.2%), consider it neutral
        if trend_pct < 0.002:  # 0.2%
            return 'NEUTRAL'
        elif second_avg > first_avg:
            return 'BULLISH'
        else:
            return 'BEARISH'
    except Exception as e:
        logger.debug(f"Error checking M15 trend: {e}")
        return 'UNKNOWN'

def _check_choppy_liquidity(self, candles: List[Dict]) -> bool:
    """Check for wicks but no displacement (choppy liquidity)"""
    if len(candles) < 10:
        return False
    
    # Check last 5 candles for wicks without strong displacement
    wick_count = 0
    displacement_count = 0
    
    for candle in candles[-5:]:
        high = candle.get('high', 0)
        low = candle.get('low', 0)
        open_price = candle.get('open', 0)
        close = candle.get('close', 0)
        
        body = abs(close - open_price)
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        total_range = high - low
        
        if total_range > 0:
            # Significant wick (wick > body)
            wick_ratio = (upper_wick + lower_wick) / total_range
            if wick_ratio > 0.5:  # More than 50% wick
                wick_count += 1
            
            # Check for displacement (strong move)
            body_ratio = body / total_range
            if body_ratio > 0.7:  # Strong body (>70% of range)
                displacement_count += 1
    
    # Choppy: wicks present but no strong displacement
    return wick_count >= 3 and displacement_count < 2

def _count_range_respects(self, candles: List[Dict], range_high: float, range_low: float) -> int:
    """Count how many times price bounced at range edges"""
    if len(candles) < 10 or range_high <= range_low:
        return 0
    
    tolerance = (range_high - range_low) * 0.01  # 1% of range width
    respects = 0
    
    for i in range(1, len(candles)):
        prev_candle = candles[i-1]
        curr_candle = candles[i]
        
        prev_high = prev_candle.get('high', 0)
        prev_low = prev_candle.get('low', 0)
        curr_high = curr_candle.get('high', 0)
        curr_low = curr_candle.get('low', 0)
        
        # Check bounce at range high
        if abs(prev_high - range_high) <= tolerance:
            # Price touched high, then reversed down
            if curr_low < prev_low:
                respects += 1
        
        # Check bounce at range low
        if abs(prev_low - range_low) <= tolerance:
            # Price touched low, then reversed up
            if curr_high > prev_high:
                respects += 1
    
    return respects

def _calculate_vwap_std(self, candles: List[Dict], vwap: float) -> float:
    """Calculate VWAP standard deviation"""
    if len(candles) < 10 or vwap == 0:
        return 0.0
    
    try:
        import statistics
        
        # Calculate typical prices
        typical_prices = []
        volumes = []
        
        for candle in candles[-20:]:  # Use last 20 candles
            high = candle.get('high', 0)
            low = candle.get('low', 0)
            close = candle.get('close', 0)
            volume = candle.get('volume', 0)
            
            if volume > 0:
                typical_price = (high + low + close) / 3
                typical_prices.append(typical_price)
                volumes.append(volume)
        
        if not typical_prices:
            return 0.0
        
        # Calculate weighted standard deviation
        total_volume = sum(volumes)
        if total_volume == 0:
            return 0.0
        
        # Weighted mean
        weighted_mean = sum(tp * vol for tp, vol in zip(typical_prices, volumes)) / total_volume
        
        # Weighted variance
        weighted_variance = sum(vol * (tp - weighted_mean) ** 2 for tp, vol in zip(typical_prices, volumes)) / total_volume
        
        # Standard deviation
        std = weighted_variance ** 0.5
        
        return std
    except Exception as e:
        logger.debug(f"Error calculating VWAP std: {e}")
        return 0.0

def _create_range_from_pdh_pdl(self, pdh: float, pdl: float, snapshot: Dict[str, Any]) -> Optional[Any]:
    """Create RangeStructure from PDH/PDL"""
    if not pdh or not pdl or pdh <= pdl:
        return None
    
    try:
        from infra.range_boundary_detector import RangeStructure, CriticalGapZones
        
        vwap = snapshot.get('vwap', (pdh + pdl) / 2)
        atr = snapshot.get('atr1', (pdh - pdl) / 3)  # Rough estimate
        
        # Calculate critical gaps
        range_width = pdh - pdl
        gap_size = range_width * 0.15
        critical_gaps = CriticalGapZones(
            upper_zone_start=pdh - gap_size,
            upper_zone_end=pdh,
            lower_zone_start=pdl,
            lower_zone_end=pdl + gap_size
        )
        
        return RangeStructure(
            range_type="daily",
            range_high=pdh,
            range_low=pdl,
            range_mid=(pdh + pdl) / 2,
            range_width_atr=(pdh - pdl) / atr if atr > 0 else 0,
            critical_gaps=critical_gaps,
            touch_count={},  # Empty dict, not int
            validated=False,
            nested_ranges=None,
            expansion_state="stable",
            invalidation_signals=[]
        )
    except Exception as e:
        logger.debug(f"Error creating range from PDH/PDL: {e}")
        return None

# Note: _candles_to_df() is implemented above with validation

**Configuration:**
Add to `config/micro_scalp_config.json`:
```json
{
  "regime_detection": {
    "enabled": true,
    "cache_enabled": true,
    "cache_size": 3,
    "cache_consistency_required": 2,
    "strategy_confidence_thresholds": {
      "vwap_reversion": 70,
      "range_scalp": 55,
      "balanced_zone": 65,
      "edge_based": 60
    },
    "vwap_reversion": {
      "btc_deviation_threshold": 2.0,
      "btc_deviation_pct": 0.005,
      "xau_deviation_threshold": 2.0,
      "xau_deviation_pct": 0.002,
      "volume_normalization": "z_score",
      "volume_z_score_threshold": 1.5,
      "volume_spike_multiplier": 1.3,
      "vwap_slope_max_normalized": 0.1,
      "vwap_slope_max_fallback": 0.0001,
      "atr_stability_lookback": 14
    },
    "range_scalp": {
      "min_range_respects": 2,
      "edge_tolerance_pct": 0.005,
      "bb_compression_threshold": 0.02,
      "m15_trend_max_adx": 20
    },
    "balanced_zone": {
      "atr_drop_threshold": 0.8,
      "compression_bars": 3,
      "vwap_alignment_tolerance": 0.001,
      "news_blackout_minutes": 15,
      "mtf_compression_required": true,
      "m5_candles_count": 10,
      "ema_vwap_equilibrium_threshold": 0.001,
      "require_equilibrium_for_fade": true
    }
  }
}
```

**Testing:**
- Unit tests for each detection method
- Integration tests with real market data
- Confidence score validation
- Edge case handling (missing data, zero values)

---

## 🔀 Phase 2: Strategy Router

### 2.1 Create `MicroScalpStrategyRouter`

**File:** `infra/micro_scalp_strategy_router.py`

**Purpose:**
- Select appropriate strategy based on regime detection
- Handle fallback to edge-based strategy
- Manage strategy priority ordering

**Key Methods:**

```python
class MicroScalpStrategyRouter:
    def __init__(self, config, regime_detector, m1_analyzer=None):
        """Initialize strategy router"""
        self.config = config
        self.regime_detector = regime_detector
        self.m1_analyzer = m1_analyzer  # NEW: For quick confluence check
    
    def select_strategy(self, snapshot: Dict[str, Any], regime_result: Dict[str, Any]) -> str:
        """
        Select strategy based on regime.
        
        Returns:
        - "vwap_reversion" | "range_scalp" | "balanced_zone" | "edge_based"
        """
    
    def get_strategy_checker(self, strategy_name: str) -> MicroScalpConditionsChecker:
        """Get strategy-specific condition checker instance"""
```

**Strategy Priority Logic:**
1. **VWAP Reversion** - Highest priority if detected (confidence ≥ 60)
2. **Range Scalp** - Second priority if detected (confidence ≥ 60)
3. **Balanced Zone** - Third priority if detected (confidence ≥ 60)
4. **Edge Based** - Fallback if no regime detected or confidence < 60

**Implementation:**

```python
def select_strategy(self, snapshot, regime_result):
    regime = regime_result.get('regime', 'UNKNOWN')
    confidence = regime_result.get('confidence', 0)
    
    # FIXED: Use strategy-specific threshold from detection result
    min_confidence = regime_result.get('min_confidence_threshold', 60)
    
    # Check if regime detection is enabled
    if not self.config.get('regime_detection', {}).get('enabled', True):
        return 'edge_based'
    
    # If confidence too low, fallback
    if confidence < min_confidence:
        logger.debug(f"Regime confidence {confidence} < {min_confidence}, using edge-based fallback")
        return 'edge_based'
    
    # Strategy priority ordering
    if regime == 'VWAP_REVERSION':
        return 'vwap_reversion'
    elif regime == 'RANGE':
        return 'range_scalp'
    elif regime == 'BALANCED_ZONE':
        return 'balanced_zone'
    else:
        logger.debug(f"Unknown regime {regime}, using edge-based fallback")
        return 'edge_based'
```

**Integration:**
- Router is called from `MicroScalpEngine.check_micro_conditions()`
- Returns strategy name string
- Engine uses strategy name to get appropriate checker

---

## 🎯 Phase 3: Strategy-Specific Condition Checkers

### 3.1 Base Strategy Checker Interface

**File:** `infra/micro_scalp_strategies/base_strategy_checker.py`

**Purpose:**
- Abstract base class for all strategy checkers
- Defines common interface
- Implements shared helper methods

**CRITICAL: Method Override Requirements**

Each strategy checker **MUST override** the following base class methods because the base class implementations are generic and won't work for strategy-specific logic:

1. **`_check_location_filter(symbol, candles, current_price, vwap, atr1)`** - Must be overridden
   - Base class checks for generic "edge" (VWAP band, OB zone, etc.)
   - Strategy checkers need specific logic (deviation, range edge, compression block)

2. **`_check_candle_signals(symbol, candles, current_price, vwap, atr1, btc_order_flow)`** - Must be overridden
   - Base class checks for generic signals (long wick, sweep, etc.)
   - Strategy checkers need specific signals (CHOCH at extreme, sweep at edge, fade/breakout)

**Base Class Method Signatures (for reference):**
```python
# In MicroScalpConditionsChecker (base class)
def _check_location_filter(self, symbol: str, candles: List[Dict[str, Any]],
                          current_price: float, vwap: float, atr1: Optional[float]) -> Dict[str, Any]:
    """Generic edge detection - NOT suitable for strategy-specific logic"""

def _check_candle_signals(self, symbol: str, candles: List[Dict[str, Any]],
                         current_price: float, vwap: float, atr1: Optional[float],
                         btc_order_flow: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Generic signal detection - NOT suitable for strategy-specific logic"""
```

**Strategy Checker Override Pattern:**
```python
# In each strategy checker (VWAPReversionChecker, RangeScalpChecker, etc.)
def _check_location_filter(self, symbol: str, candles: List[Dict[str, Any]],
                          current_price: float, vwap: float, atr1: Optional[float]) -> Dict[str, Any]:
    """Strategy-specific location filter implementation"""
    # Strategy-specific logic here
    # Return dict with 'passed', strategy-specific data, 'reasons'
    pass

def _check_candle_signals(self, symbol: str, candles: List[Dict[str, Any]],
                         current_price: float, vwap: float, atr1: Optional[float],
                         btc_order_flow: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Strategy-specific signal detection implementation"""
    # Strategy-specific logic here
    # Return dict with 'primary_count', 'secondary_count', 'primary_triggers', 'secondary_confluence'
    pass

def _calculate_confluence_score(self, symbol: str, candles: List[Dict[str, Any]],
                               current_price: float, vwap: float, atr1: Optional[float],
                               location_result: Dict[str, Any],
                               signal_result: Dict[str, Any]) -> float:
    """
    CRITICAL: Must override for strategy-specific confluence scoring.
    
    Without override: All strategies share identical validation logic → system loses adaptivity.
    
    Each strategy checker MUST implement this with:
    - Strategy-specific weights from config
    - Strategy-specific scoring logic
    - Fallback to base class if weights not configured
    """
    # Strategy-specific confluence scoring here
    # Apply weights from config: self.config.get('regime_detection', {}).get('confluence_weights', {}).get(self.strategy_name, {})
    # Return weighted confluence score (0-8 scale)
    pass
```

```python
from abc import ABC, abstractmethod
from infra.micro_scalp_conditions import MicroScalpConditionsChecker, ConditionCheckResult

class BaseStrategyChecker(MicroScalpConditionsChecker, ABC):
    """
    Base class for strategy-specific condition checkers.
    
    CRITICAL: This class includes helper methods that are also used by MicroScalpRegimeDetector.
    These methods are made available here so strategy checkers can access them via inheritance.
    """
    
    def __init__(self, config, volatility_filter, vwap_filter, 
                 sweep_detector, ob_detector, spread_tracker,
                 m1_analyzer=None, session_manager=None, news_service=None,
                 strategy_name: str = None):
        super().__init__(config, volatility_filter, vwap_filter,
                        sweep_detector, ob_detector, spread_tracker,
                        m1_analyzer, session_manager)
        self.news_service = news_service  # NEW: For news checks in Layer 1
        self.strategy_name = strategy_name  # NEW: For confluence weight lookup
    
    # CRITICAL: Helper methods moved here so strategy checkers can access them
    # These methods are also used by MicroScalpRegimeDetector (can be shared via inheritance or composition)
    
    def _calculate_vwap_std(self, candles: List[Dict], vwap: float) -> float:
        """Calculate VWAP standard deviation (shared helper method)"""
        # Implementation from MicroScalpRegimeDetector (see line 1758)
        if len(candles) < 10 or vwap == 0:
            return 0.0
        
        try:
            import statistics
            
            # Calculate typical prices
            typical_prices = []
            volumes = []
            
            for candle in candles[-20:]:  # Use last 20 candles
                high = candle.get('high', 0)
                low = candle.get('low', 0)
                close = candle.get('close', 0)
                volume = candle.get('volume', 0)
                
                if volume > 0:
                    typical_price = (high + low + close) / 3
                    typical_prices.append(typical_price)
                    volumes.append(volume)
            
            if not typical_prices:
                return 0.0
            
            # Calculate weighted standard deviation
            total_volume = sum(volumes)
            if total_volume == 0:
                return 0.0
            
            # Weighted mean
            weighted_mean = sum(tp * vol for tp, vol in zip(typical_prices, volumes)) / total_volume
            
            # Weighted variance
            weighted_variance = sum(vol * (tp - weighted_mean) ** 2 for tp, vol in zip(typical_prices, volumes)) / total_volume
            
            # Standard deviation
            std = weighted_variance ** 0.5
            
            return std
        except Exception as e:
            logger.debug(f"Error calculating VWAP std: {e}")
            return 0.0
    
    def _calculate_vwap_slope(self, candles: List[Dict[str, Any]], vwap: float) -> float:
        """Calculate VWAP slope over last N candles (shared helper method)"""
        # Implementation from MicroScalpRegimeDetector (see line 1255)
        if len(candles) < 5 or vwap == 0:
            return 0.0
        
        # Calculate VWAP for last 5 candles and previous 5 candles
        recent_candles = candles[-5:]
        previous_candles = candles[-10:-5] if len(candles) >= 10 else candles[:5]
        
        # Calculate VWAP for each period
        recent_vwap = self._calculate_vwap_from_candles(recent_candles)
        previous_vwap = self._calculate_vwap_from_candles(previous_candles)
        
        if previous_vwap == 0:
            return 0.0
        
        # Slope = (recent_vwap - previous_vwap) / previous_vwap
        # Normalized by price to get percentage change
        slope = (recent_vwap - previous_vwap) / previous_vwap
        
        return slope
    
    def _calculate_vwap_from_candles(self, candles: List[Dict[str, Any]]) -> float:
        """Calculate VWAP from candle list (helper for slope calculation)"""
        if not candles:
            return 0.0
        
        total_pv = 0.0
        total_volume = 0.0
        
        for candle in candles:
            high = candle.get('high', 0)
            low = candle.get('low', 0)
            close = candle.get('close', 0)
            volume = candle.get('volume', 0)
            
            if volume <= 0:
                continue
            
            typical_price = (high + low + close) / 3
            total_pv += typical_price * volume
            total_volume += volume
        
        if total_volume == 0:
            return 0.0
        
        return total_pv / total_volume
    
    def _check_volume_spike(self, candles: List[Dict]) -> bool:
        """Check volume spike using configurable normalization method (shared helper)"""
        # Implementation from MicroScalpRegimeDetector (see line 1450)
        volume_normalization = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_normalization', 'multiplier')
        
        if volume_normalization == 'z_score':
            return self._check_volume_spike_zscore(candles)
        else:
            return self._check_volume_spike_multiplier(candles)
    
    def _check_volume_spike_multiplier(self, candles: List[Dict]) -> bool:
        """Check if volume ≥ multiplier × 10-bar average"""
        if len(candles) < 11:
            return False
        
        last_volume = candles[-1].get('volume', 0)
        if last_volume == 0:
            return False
        
        recent_volumes = [c.get('volume', 0) for c in candles[-11:-1]]
        avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0
        
        if avg_volume == 0:
            return False
        
        volume_multiplier = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_spike_multiplier', 1.3)
        return last_volume >= avg_volume * volume_multiplier
    
    def _check_volume_spike_zscore(self, candles: List[Dict]) -> bool:
        """Check volume spike using Z-score normalization (exchange-agnostic)"""
        if len(candles) < 31:
            # Fallback to multiplier if not enough data
            return self._check_volume_spike_multiplier(candles)
        
        last_volume = candles[-1].get('volume', 0)
        if last_volume == 0:
            return False
        
        recent_volumes = [c.get('volume', 0) for c in candles[-31:-1]]
        
        if not recent_volumes or all(v == 0 for v in recent_volumes):
            return False
        
        import statistics
        mean_volume = statistics.mean(recent_volumes)
        std_volume = statistics.stdev(recent_volumes) if len(recent_volumes) > 1 else 0
        
        if std_volume == 0:
            # Fallback to multiplier
            return self._check_volume_spike_multiplier(candles)
        
        z_score = (last_volume - mean_volume) / std_volume
        z_score_threshold = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_z_score_threshold', 1.5)
        
        return z_score >= z_score_threshold
    
    def _check_bb_compression(self, candles: List[Dict]) -> bool:
        """
        Check if Bollinger Band width is contracting (shared helper method).
        
        RECOMMENDED: BB width < 0.02 (2% of price) → Balanced Zone
        
        Returns True if:
        - Recent BB width < 2% of price (absolute threshold)
        - OR Recent BB width < threshold × average (relative compression fallback)
        """
        # Implementation from MicroScalpRegimeDetector (see line 1505)
        if len(candles) < 20:
            return False
        
        try:
            import pandas as pd
            import numpy as np
            
            # Convert to DataFrame
            df = self._candles_to_df(candles)
            if df is None or len(df) < 20:
                return False
            
            # Calculate Bollinger Bands
            period = 20
            std_dev = 2.0
            
            close = df['close']
            sma = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            
            bb_upper = sma + (std * std_dev)
            bb_lower = sma - (std * std_dev)
            bb_width_pct = (bb_upper - bb_lower) / sma  # As decimal (0.02 = 2%)
            
            if len(bb_width_pct) < 5:
                return False
            
            # RECOMMENDED: Check absolute threshold first (BB width < 0.02 = 2%)
            recent_width_pct = bb_width_pct.iloc[-1]  # Most recent BB width
            if recent_width_pct < 0.02:  # 2% of price
                return True
            
            # Fallback: Check relative compression (recent < average)
            if len(bb_width_pct) >= 10:
                recent_avg = bb_width_pct.iloc[-5:].mean()
                avg_width = bb_width_pct.iloc[-20:].mean()
                
                if avg_width > 0:
                    compression_threshold = self.config.get('regime_detection', {}).get('balanced_zone', {}).get('bb_compression_threshold', 0.9)
                    compression_ratio = recent_avg / avg_width
                    return compression_ratio < compression_threshold
            
            return False
        except Exception as e:
            logger.debug(f"Error checking BB compression: {e}")
            return False
    
    def _check_compression_block(self, candles: List[Dict], atr1: Optional[float] = None) -> bool:
        """Check for inside bars / tight structure (shared helper method)"""
        # Implementation from MicroScalpRegimeDetector (see line 1412)
        if len(candles) < 3:
            return False
        
        # Validate candle structure
        if not all(isinstance(c, dict) and 'high' in c and 'low' in c for c in candles):
            logger.warning("Invalid candle structure in compression check")
            return False
        
        # Check for inside bars (last 3 candles)
        inside_count = 0
        for i in range(max(1, len(candles) - 2), len(candles)):
            current = candles[i]
            previous = candles[i-1]
            
            current_high = current.get('high', 0)
            current_low = current.get('low', 0)
            previous_high = previous.get('high', 0)
            previous_low = previous.get('low', 0)
            
            # Inside bar: current high/low within previous high/low
            if current_high < previous_high and current_low > previous_low:
                inside_count += 1
        
        # Also check for tight range (small candle bodies)
        if len(candles) >= 5 and atr1:
            recent_candles = candles[-5:]
            avg_range = sum(c.get('high', 0) - c.get('low', 0) for c in recent_candles) / len(recent_candles)
            
            if atr1 > 0:
                # If average range is less than 0.5× ATR, consider it compressed
                if avg_range < atr1 * 0.5:
                    return True
        
        # Return True if at least 2 inside bars in last 3 candles
        return inside_count >= 2
    
    def _count_range_respects(self, candles: List[Dict], range_high: float, range_low: float) -> int:
        """Count how many times price bounced at range edges (shared helper method)"""
        # Implementation from MicroScalpRegimeDetector (see line 1727)
        if len(candles) < 10 or range_high <= range_low:
            return 0
        
        tolerance = (range_high - range_low) * 0.01  # 1% of range width
        respects = 0
        
        for i in range(1, len(candles)):
            prev_candle = candles[i-1]
            curr_candle = candles[i]
            
            prev_high = prev_candle.get('high', 0)
            prev_low = prev_candle.get('low', 0)
            curr_high = curr_candle.get('high', 0)
            curr_low = curr_candle.get('low', 0)
            
            # Check bounce at range high
            if abs(prev_high - range_high) <= tolerance:
                # Price touched high, then reversed down
                if curr_low < prev_low:
                    respects += 1
            
            # Check bounce at range low
            if abs(prev_low - range_low) <= tolerance:
                # Price touched low, then reversed up
                if curr_high > prev_high:
                    respects += 1
        
        return respects
    
    def _check_m15_trend(self, symbol: str, snapshot: Dict[str, Any]) -> str:
        """Check M15 trend - should be NEUTRAL for range detection (shared helper method)"""
        # Implementation from MicroScalpRegimeDetector (see line 1634)
        m15_candles = snapshot.get('m15_candles', [])
        
        if not m15_candles or len(m15_candles) < 20:
            return 'UNKNOWN'  # Cannot determine
        
        try:
            # Calculate simple trend from M15 candles
            recent_closes = [c.get('close', 0) for c in m15_candles[-20:]]
            
            if len(recent_closes) < 20 or any(c == 0 for c in recent_closes):
                return 'UNKNOWN'
            
            # Check if price is trending or ranging
            first_half = recent_closes[:10]
            second_half = recent_closes[10:]
            
            first_avg = sum(first_half) / len(first_half) if first_half else 0
            second_avg = sum(second_half) / len(second_half) if second_half else 0
            
            if first_avg == 0 or second_avg == 0:
                return 'UNKNOWN'
            
            # Calculate trend strength
            trend_pct = abs(second_avg - first_avg) / first_avg if first_avg > 0 else 0
            
            # If trend is weak (< 0.2%), consider it neutral
            if trend_pct < 0.002:  # 0.2%
                return 'NEUTRAL'
            elif second_avg > first_avg:
                return 'BULLISH'
            else:
                return 'BEARISH'
        except Exception as e:
            logger.debug(f"Error checking M15 trend: {e}")
            return 'UNKNOWN'
    
    def _check_choppy_liquidity(self, candles: List[Dict]) -> bool:
        """Check for wicks but no displacement (choppy liquidity) (shared helper method)"""
        # Implementation from MicroScalpRegimeDetector (see line 1672)
        if len(candles) < 10:
            return False
        
        # Check last 5 candles for wicks without strong displacement
        wick_count = 0
        displacement_count = 0
        
        for candle in candles[-5:]:
            high = candle.get('high', 0)
            low = candle.get('low', 0)
            open_price = candle.get('open', 0)
            close = candle.get('close', 0)
            
            body = abs(close - open_price)
            upper_wick = high - max(open_price, close)
            lower_wick = min(open_price, close) - low
            total_range = high - low
            
            if total_range > 0:
                # Significant wick (wick > body)
                wick_ratio = (upper_wick + lower_wick) / total_range
                if wick_ratio > 0.5:  # More than 50% wick
                    wick_count += 1
                
                # Check for displacement (strong move)
                body_ratio = body / total_range
                if body_ratio > 0.7:  # Strong body (>70% of range)
                    displacement_count += 1
        
        # Choppy: wicks present but no strong displacement
        return wick_count >= 3 and displacement_count < 2
    
    def _candles_to_df(self, candles: List[Dict[str, Any]]) -> Optional[pd.DataFrame]:
        """Convert candle list to DataFrame with datetime index (shared helper method)"""
        # Implementation from MicroScalpRegimeDetector (see line 1207)
        if not candles:
            return None
        
        try:
            import pandas as pd
            
            # Extract data
            times = []
            opens = []
            highs = []
            lows = []
            closes = []
            volumes = []
            
            for candle in candles:
                # Handle different time formats
                time_val = candle.get('time')
                if isinstance(time_val, (int, float)):
                    # Unix timestamp
                    times.append(pd.Timestamp.fromtimestamp(time_val, tz='UTC'))
                elif isinstance(time_val, str):
                    times.append(pd.Timestamp(time_val))
                elif hasattr(time_val, 'timestamp'):
                    times.append(pd.Timestamp.fromtimestamp(time_val.timestamp(), tz='UTC'))
                else:
                    times.append(pd.Timestamp.now(tz='UTC'))
                
                opens.append(candle.get('open', 0))
                highs.append(candle.get('high', 0))
                lows.append(candle.get('low', 0))
                closes.append(candle.get('close', 0))
                volumes.append(candle.get('volume', 0))
            
            df = pd.DataFrame({
                'open': opens,
                'high': highs,
                'low': lows,
                'close': closes,
                'volume': volumes
            }, index=times)
            
            return df
        except Exception as e:
            logger.error(f"Error converting candles to DataFrame: {e}")
            return None
    
    def validate(self, snapshot: Dict[str, Any]) -> ConditionCheckResult:
        """
        Base implementation that calls strategy-specific overrides.
        
        Subclasses should NOT override this method, but should override:
        - _check_location_filter() - Strategy-specific location requirements
        - _check_candle_signals() - Strategy-specific signal detection
        - _calculate_confluence_score() - Strategy-specific confluence weighting
        
        This ensures consistent 4-layer validation structure while allowing
        strategy-specific logic in individual layers.
        """
        # Extract parameters from snapshot (base class methods require individual params)
        symbol = snapshot.get('symbol', '')
        candles = snapshot.get('candles', [])
        current_price = snapshot.get('current_price', 0.0)
        vwap = snapshot.get('vwap', 0.0)
        atr1 = snapshot.get('atr1')
        btc_order_flow = snapshot.get('btc_order_flow')
        
        reasons = []
        details = {}
        
        # Layer 1: Pre-Trade Filters (use base class)
        pre_trade_result = self._check_pre_trade_filters(
            symbol, candles, snapshot.get('spread_data'), current_price
        )
        pre_trade_passed = pre_trade_result.passed
        details['pre_trade'] = {
            'passed': pre_trade_passed,
            'atr1': pre_trade_result.atr1_value,
            'm1_range_avg': pre_trade_result.m1_range_avg,
            'reasons': pre_trade_result.reasons
        }
        
        if not pre_trade_passed:
            reasons.extend(pre_trade_result.reasons)
            return ConditionCheckResult(
                passed=False,
                pre_trade_passed=False,
                location_passed=False,
                primary_triggers=0,
                secondary_confluence=0,
                confluence_score=0.0,
                is_aplus_setup=False,
                reasons=reasons,
                details=details
            )
        
        # Layer 2: Location Filter (strategy-specific override)
        location_result = self._check_location_filter(symbol, candles, current_price, vwap, atr1)
        location_passed = location_result.get('passed', False)
        details['location'] = location_result
        
        if not location_passed:
            reasons.append("Not at edge location (strategy-specific check failed)")
            return ConditionCheckResult(
                passed=False,
                pre_trade_passed=True,
                location_passed=False,
                primary_triggers=0,
                secondary_confluence=0,
                confluence_score=0.0,
                is_aplus_setup=False,
                reasons=reasons,
                details=details
            )
        
        # Layer 3: Candle Signals (strategy-specific override)
        signal_result = self._check_candle_signals(
            symbol, candles, current_price, vwap, atr1, btc_order_flow
        )
        primary_count = signal_result.get('primary_count', 0)
        secondary_count = signal_result.get('secondary_count', 0)
        primary_triggers = signal_result.get('primary_triggers', [])
        secondary_confluence = signal_result.get('secondary_confluence', [])
        details['signals'] = signal_result
        
        if primary_count < 1 or secondary_count < 1:
            failure_msg = f"Insufficient signals: {primary_count} primary, {secondary_count} secondary (need ≥1 each)"
            if primary_count > 0:
                failure_msg += f" - Primary: {', '.join(primary_triggers)}"
            if secondary_count > 0:
                failure_msg += f" - Secondary: {', '.join(secondary_confluence)}"
            reasons.append(failure_msg)
            return ConditionCheckResult(
                passed=False,
                pre_trade_passed=True,
                location_passed=True,
                primary_triggers=primary_count,
                secondary_confluence=secondary_count,
                confluence_score=0.0,
                is_aplus_setup=False,
                reasons=reasons,
                details=details
            )
        
        # Layer 4: Confluence Score (strategy-specific override)
        confluence_score = self._calculate_confluence_score(
            symbol, candles, current_price, vwap, atr1, location_result, signal_result
        )
        details['confluence'] = {
            'score': confluence_score,
            'min_for_trade': self._get_min_score(symbol),
            'min_for_aplus': self._get_min_score_aplus(symbol)
        }
        
        min_score = self._get_min_score(symbol)
        min_score_aplus = self._get_min_score_aplus(symbol)
        
        if confluence_score < min_score:
            reasons.append(f"Confluence score {confluence_score:.1f} < minimum {min_score}")
            return ConditionCheckResult(
                passed=False,
                pre_trade_passed=True,
                location_passed=True,
                primary_triggers=primary_count,
                secondary_confluence=secondary_count,
                confluence_score=confluence_score,
                is_aplus_setup=False,
                reasons=reasons,
                details=details
            )
        
        # All layers passed
        is_aplus = confluence_score >= min_score_aplus
        
        return ConditionCheckResult(
            passed=True,
            pre_trade_passed=True,
            location_passed=True,
            primary_triggers=primary_count,
            secondary_confluence=secondary_count,
            confluence_score=confluence_score,
            is_aplus_setup=is_aplus,
            reasons=reasons,
            details=details
        )
    
    @abstractmethod
    def generate_trade_idea(self, snapshot: Dict[str, Any], 
                           result: ConditionCheckResult) -> Optional[Dict[str, Any]]:
        """Generate strategy-specific trade idea"""
```

### 3.2 VWAP Reversion Strategy Checker

**File:** `infra/micro_scalp_strategies/vwap_reversion_checker.py`

**Required Method Overrides:**

Each strategy checker MUST override `_check_location_filter()` and `_check_candle_signals()` with strategy-specific logic:

```python
def _check_location_filter(self, symbol: str, candles: List[Dict[str, Any]],
                          current_price: float, vwap: float, atr1: Optional[float]) -> Dict[str, Any]:
    """
    VWAP Reversion-specific location filter.
    
    Checks:
    - Price deviation ≥2σ from VWAP
    - VWAP slope (not strongly trending)
    - Volume spike confirmation
    """
    if vwap == 0:
        return {'passed': False, 'reasons': ['VWAP is zero']}
    
    # Calculate VWAP deviation in standard deviations
    vwap_std = self._calculate_vwap_std(candles, vwap)
    if vwap_std == 0:
        return {'passed': False, 'reasons': ['VWAP std is zero']}
    
    deviation_sigma = abs(current_price - vwap) / vwap_std
    deviation_pct = abs(current_price - vwap) / vwap if vwap > 0 else 0
    
    # Symbol-specific thresholds
    if symbol.upper().startswith('BTC'):
        min_deviation = 2.0
        min_deviation_pct = 0.005  # 0.5%
    else:  # XAU
        min_deviation = 2.0
        min_deviation_pct = 0.002  # 0.20%
    
    # Check deviation threshold
    deviation_ok = deviation_sigma >= min_deviation or deviation_pct >= min_deviation_pct
    
    # Check VWAP slope (not strongly trending)
    vwap_slope = self._calculate_vwap_slope(candles, vwap)
    if atr1 and atr1 > 0:
        vwap_slope_normalized = abs(vwap_slope) / atr1
        max_slope_normalized = 0.1  # 10% of ATR per bar
        vwap_slope_ok = vwap_slope_normalized < max_slope_normalized
    else:
        max_slope = 0.0001
        vwap_slope_ok = abs(vwap_slope) < max_slope
    
    # Check volume spike
    volume_spike = self._check_volume_spike(candles)
    
    passed = deviation_ok and vwap_slope_ok
    
    return {
        'passed': passed,
        'deviation_sigma': deviation_sigma,
        'deviation_pct': deviation_pct,
        'vwap_slope': vwap_slope,
        'vwap_slope_ok': vwap_slope_ok,
        'volume_spike': volume_spike,
        'reasons': [] if passed else [
            f'Deviation {deviation_sigma:.2f}σ < {min_deviation}σ' if not deviation_ok else '',
            f'VWAP slope too steep' if not vwap_slope_ok else ''
        ]
    }

def _check_candle_signals(self, symbol: str, candles: List[Dict[str, Any]],
                         current_price: float, vwap: float, atr1: Optional[float],
                         btc_order_flow: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    VWAP Reversion-specific candle signals.
    
    Checks:
    - Primary: M1 CHOCH at deviation extreme
    - Secondary: Volume confirmation OR absorption wick
    """
    primary_triggers = []
    secondary_confluence = []
    
    # Primary: CHOCH at deviation extreme
    choch_detected = False
    choch_direction = None
    if self.m1_analyzer:
        try:
            analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
            choch_bos = analysis.get('choch_bos', {})
            choch_detected = choch_bos.get('has_choch', False) or choch_bos.get('choch_confirmed', False)
            choch_direction = choch_bos.get('direction', '')
            
            # Verify CHOCH is at deviation extreme
            if choch_detected:
                # Check if price is at deviation (far from VWAP)
                deviation_sigma = abs(current_price - vwap) / self._calculate_vwap_std(candles, vwap) if vwap > 0 else 0
                if deviation_sigma >= 2.0:
                    primary_triggers.append('CHOCH_AT_EXTREME')
        except Exception as e:
            logger.debug(f"Error checking CHOCH: {e}")
    
    # Secondary: Volume confirmation
    volume_spike = self._check_volume_spike(candles)
    if volume_spike:
        secondary_confluence.append('VOLUME_CONFIRMED')
    
    # Secondary: Absorption wick (long wick into extension)
    if len(candles) >= 1:
        last_candle = candles[-1]
        high = last_candle.get('high', 0)
        low = last_candle.get('low', 0)
        close = last_candle.get('close', 0)
        open_price = last_candle.get('open', 0)
        
        body = abs(close - open_price)
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        total_range = high - low
        
        if total_range > 0:
            # Absorption wick: wick > 2× body
            if upper_wick > body * 2 or lower_wick > body * 2:
                secondary_confluence.append('ABSORPTION_WICK')
    
    return {
        'primary_count': len(primary_triggers),
        'secondary_count': len(secondary_confluence),
        'primary_triggers': primary_triggers,
        'secondary_confluence': secondary_confluence
    }
```

**4-Layer Validation:**

#### Layer 1: Pre-Trade Filters
- ATR(14) M1 stable or rising (not collapsing)
- Spread within limits
- Volume spike confirmed (≥1.3× avg)

#### Layer 2: Location Filter
- Price deviation ≥2σ from VWAP:
  - Bull: Price far below VWAP (new micro low)
  - Bear: Price far above VWAP (new micro high)
- VWAP slope check: Not strongly trending

#### Layer 3: Candle Signals
- **Primary**: M1 CHOCH at deviation extreme
  - Bull: CHOCH bull at deviation low
  - Bear: CHOCH bear at deviation high
- **Secondary**: Volume confirmation OR absorption wick

#### Layer 4: Confluence Score
- Deviation strength (0-2): How far from VWAP
- CHOCH quality (0-2): Fresh CHOCH
- Volume confirmation (0-2): Spike strength
- VWAP slope (0-1): Not trending hard
- Minimum: 5.0
- **Call**: `_calculate_confluence_score(symbol, candles, current_price, vwap, atr1, location_result, signal_result)`

**Implementation Notes:**
```python
# In validate() method
# CRITICAL: Extract parameters from snapshot FIRST (base class methods require individual params)
symbol = snapshot.get('symbol', '')
candles = snapshot.get('candles', [])
current_price = snapshot.get('current_price', 0.0)
vwap = snapshot.get('vwap', 0.0)
atr1 = snapshot.get('atr1')
btc_order_flow = snapshot.get('btc_order_flow')

# After Layer 2: Location Filter
# NOTE: Strategy checkers MUST override _check_location_filter() for strategy-specific logic
# Base class method signature: _check_location_filter(symbol, candles, current_price, vwap, atr1)
location_result = self._check_location_filter(symbol, candles, current_price, vwap, atr1)
details['location'] = location_result  # Store for confluence calculation

# After Layer 3: Candle Signals
# NOTE: Strategy checkers MUST override _check_candle_signals() for strategy-specific logic
# Base class method signature: _check_candle_signals(symbol, candles, current_price, vwap, atr1, btc_order_flow)
signal_result = self._check_candle_signals(symbol, candles, current_price, vwap, atr1, btc_order_flow)
details['signals'] = signal_result  # Store for confluence calculation

# In Layer 4: Confluence Score
confluence_score = self._calculate_confluence_score(
    symbol, candles, current_price, vwap, atr1,
    location_result, signal_result
)

# Return ConditionCheckResult with details
return ConditionCheckResult(
    passed=True,
    pre_trade_passed=True,
    location_passed=True,
    primary_triggers=signal_result.get('primary_count', 0),
    secondary_confluence=signal_result.get('secondary_count', 0),
    confluence_score=confluence_score,
    is_aplus_setup=confluence_score >= min_score_aplus,
    reasons=reasons,
    details=details  # ✅ Must include
)
```

**Trade Idea Generation:**
```python
def generate_trade_idea(self, snapshot, result):
    symbol = snapshot['symbol']
    current_price = snapshot['current_price']
    vwap = snapshot['vwap']
    candles = snapshot['candles']
    atr1 = snapshot.get('atr1')
    
    # Determine direction from CHOCH
    direction = self._get_direction_from_choch(symbol, candles, vwap, current_price)
    
    # Entry: Break of signal candle high/low
    last_candle = candles[-1]
    if direction == 'BUY':
        # FIXED: Entry logic - use current price if already broken, otherwise signal high
        signal_high = last_candle['high']
        if current_price >= signal_high:
            # Already broken, use current price
            entry_price = current_price
        else:
            # Not broken yet, use signal high (will trigger on break)
            entry_price = signal_high
        deviation_low = min(c.get('low', current_price) for c in candles[-5:])
        # FIXED: SL calculation - distance from entry to deviation, then add 15% buffer
        if symbol.upper().startswith('BTC'):
            # Distance from entry to deviation low
            distance_to_deviation = entry_price - deviation_low
            # Add 15% buffer beyond deviation
            sl_distance = distance_to_deviation * 1.15
            sl = entry_price - sl_distance  # SL below entry
        else:  # XAU
            sl_distance = 3  # 3 points
            sl = entry_price - sl_distance
        # TP1: VWAP touch
        tp1 = vwap
        # TP2 (optional): VWAP → mid-band (±1σ)
        vwap_std = snapshot.get('vwap_std', atr1 * 0.5 if atr1 else 0)
        tp2 = vwap + vwap_std if direction == 'BUY' else vwap - vwap_std
    else:  # SELL
        # FIXED: Entry logic - use current price if already broken, otherwise signal low
        signal_low = last_candle['low']
        if current_price <= signal_low:
            # Already broken, use current price
            entry_price = current_price
        else:
            # Not broken yet, use signal low (will trigger on break)
            entry_price = signal_low
        deviation_high = max(c.get('high', current_price) for c in candles[-5:])
        # FIXED: SL calculation - distance from entry to deviation, then add 15% buffer
        if symbol.upper().startswith('BTC'):
            # Distance from entry to deviation high
            distance_to_deviation = deviation_high - entry_price
            # Add 15% buffer beyond deviation
            sl_distance = distance_to_deviation * 1.15
            sl = entry_price + sl_distance  # SL above entry
        else:  # XAU
            sl_distance = 3
            sl = entry_price + sl_distance
        tp1 = vwap
        vwap_std = snapshot.get('vwap_std', atr1 * 0.5 if atr1 else 0)
        tp2 = vwap - vwap_std
    
    return {
        'symbol': symbol,
        'direction': direction,
        'entry_price': entry_price,
        'sl': sl,
        'tp': tp1,  # Primary TP at VWAP
        'tp2': tp2,  # Optional secondary TP
        'volume': 0.01,
        'atr1': atr1,
        'strategy': 'vwap_reversion',
        'confluence_score': result.confluence_score
    }
```

### 3.3 Range Scalp Strategy Checker

**File:** `infra/micro_scalp_strategies/range_scalp_checker.py`

**Required Method Overrides:**

```python
def _check_location_filter(self, symbol: str, candles: List[Dict[str, Any]],
                          current_price: float, vwap: float, atr1: Optional[float]) -> Dict[str, Any]:
    """
    Range Scalp-specific location filter.
    
    Checks:
    - Price at range edge (PDH/PDL or M15 high/low)
    - Range respected ≥2 times (bounces confirmed)
    - Edge proximity score
    """
    # Get range structure from regime detection (stored in snapshot during regime detection)
    # For now, detect range here
    range_structure = None
    near_edge = None
    
    # Try to get range from M15 data (if available in snapshot via regime detection)
    # Fallback: detect from M1 candles
    if len(candles) >= 20:
        # Use intraday range as fallback
        intraday_high = max(c.get('high', 0) for c in candles[-20:])
        intraday_low = min(c.get('low', 0) for c in candles[-20:])
        range_width = intraday_high - intraday_low
        
        if range_width > 0:
            # Check if price is near edge
            tolerance = range_width * 0.005  # 0.5% of range width
            near_high = abs(current_price - intraday_high) <= tolerance
            near_low = abs(current_price - intraday_low) <= tolerance
            
            if near_high or near_low:
                # Create temporary range structure
                from infra.range_boundary_detector import RangeStructure, CriticalGapZones
                range_structure = RangeStructure(
                    range_type="dynamic",
                    range_high=intraday_high,
                    range_low=intraday_low,
                    range_mid=(intraday_high + intraday_low) / 2,
                    range_width_atr=range_width / atr1 if atr1 > 0 else 0,
                    critical_gaps=CriticalGapZones(
                        upper_zone_start=intraday_high - range_width * 0.15,
                        upper_zone_end=intraday_high,
                        lower_zone_start=intraday_low,
                        lower_zone_end=intraday_low + range_width * 0.15
                    ),
                    touch_count={},
                    validated=False,
                    nested_ranges=None,
                    expansion_state="stable",
                    invalidation_signals=[]
                )
                near_edge = 'high' if near_high else 'low'
    
    # Check range respect (bounces at edges)
    range_respects = 0
    if range_structure:
        range_respects = self._count_range_respects(candles, range_structure.range_high, range_structure.range_low)
    
    # Check volatility compression (BB width)
    bb_compression = self._check_bb_compression(candles)
    
    # Calculate edge proximity score (0-2)
    edge_proximity_score = 0.0
    if range_structure and near_edge:
        range_width = range_structure.range_high - range_structure.range_low
        if range_width > 0:
            if near_edge == 'high':
                distance = abs(current_price - range_structure.range_high)
            else:
                distance = abs(current_price - range_structure.range_low)
            
            # Score: closer = higher (within 0.5% = 2.0, within 1% = 1.0)
            proximity_pct = distance / range_width
            if proximity_pct <= 0.005:
                edge_proximity_score = 2.0
            elif proximity_pct <= 0.01:
                edge_proximity_score = 1.0
    
    passed = range_structure is not None and near_edge is not None and range_respects >= 2
    
    return {
        'passed': passed,
        'range_structure': range_structure,
        'near_edge': near_edge,
        'range_respects': range_respects,
        'edge_proximity_score': edge_proximity_score,
        'bb_compression': bb_compression,
        'reasons': [] if passed else [
            'No range structure detected' if not range_structure else '',
            'Price not at range edge' if not near_edge else '',
            f'Range respects {range_respects} < 2' if range_respects < 2 else ''
        ]
    }

def _check_candle_signals(self, symbol: str, candles: List[Dict[str, Any]],
                         current_price: float, vwap: float, atr1: Optional[float],
                         btc_order_flow: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Range Scalp-specific candle signals.
    
    Checks:
    - Primary: Micro liquidity sweep at edge
    - Secondary: M1 CHOCH in reversal direction
    """
    primary_triggers = []
    secondary_confluence = []
    
    # Primary: Micro liquidity sweep at edge
    if len(candles) >= 5 and atr1:
        sweep_result = self.sweep_detector.detect_micro_sweep(candles, atr1)
        if sweep_result.sweep_detected:
            primary_triggers.append('MICRO_LIQUIDITY_SWEEP')
            
            # Calculate sweep quality score (0-2)
            # Quality based on sweep strength and clean reversal
            sweep_quality_score = 0.0
            if sweep_result.sweep_direction:
                # Check if sweep was followed by immediate reversal
                if len(candles) >= 2:
                    last_candle = candles[-1]
                    prev_candle = candles[-2]
                    
                    # Reversal after sweep
                    if sweep_result.sweep_direction == 'BULLISH':
                        # Swept low, then reversed up
                        if last_candle.get('close', 0) > prev_candle.get('close', 0):
                            sweep_quality_score = 2.0
                    elif sweep_result.sweep_direction == 'BEARISH':
                        # Swept high, then reversed down
                        if last_candle.get('close', 0) < prev_candle.get('close', 0):
                            sweep_quality_score = 2.0
        else:
            sweep_quality_score = 0.0
    else:
        sweep_quality_score = 0.0
    
    # Secondary: M1 CHOCH in reversal direction
    choch_detected = False
    if self.m1_analyzer:
        try:
            analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
            choch_bos = analysis.get('choch_bos', {})
            choch_detected = choch_bos.get('has_choch', False) or choch_bos.get('choch_confirmed', False)
            choch_direction = choch_bos.get('direction', '')
            
            if choch_detected:
                # Verify CHOCH is in reversal direction (opposite of sweep)
                if sweep_result.sweep_detected:
                    if (sweep_result.sweep_direction == 'BULLISH' and 'BEARISH' in str(choch_direction).upper()) or \
                       (sweep_result.sweep_direction == 'BEARISH' and 'BULLISH' in str(choch_direction).upper()):
                        secondary_confluence.append('CHOCH_REVERSAL')
                else:
                    # No sweep, but CHOCH detected
                    secondary_confluence.append('FRESH_MICRO_CHOCH')
        except Exception as e:
            logger.debug(f"Error checking CHOCH: {e}")
    
    return {
        'primary_count': len(primary_triggers),
        'secondary_count': len(secondary_confluence),
        'primary_triggers': primary_triggers,
        'secondary_confluence': secondary_confluence,
        'sweep_quality_score': sweep_quality_score  # Store for confluence calculation
    }
```

**4-Layer Validation:**

#### Layer 1: Pre-Trade Filters
- Volatility compressing (BB width contracting)
- Spread normal (not widening)
- Volume not extremely low

#### Layer 2: Location Filter
- Price at range edge:
  - Bull: Near PDL or M15 low
  - Bear: Near PDH or M15 high
- Range respected ≥2 times (bounces confirmed)
- **Store in location_result**: `range_structure`, `near_edge`, `range_respects`, `edge_proximity_score`, `bb_compression`

#### Layer 3: Candle Signals
- **Primary**: Micro liquidity sweep at edge
- **Secondary**: M1 CHOCH in reversal direction
- **Store in signal_result**: `primary_count`, `secondary_count`, `sweep_quality_score`

#### Layer 4: Confluence Score
- Edge proximity (0-2): How close to range edge
- Sweep quality (0-2): Clean sweep
- Range respect (0-2): Number of bounces
- Volatility compression (0-1): BB contracting
- Minimum: 5.0
- **Call**: `_calculate_confluence_score(symbol, candles, current_price, vwap, atr1, location_result, signal_result)`
- **Store in result.details**: `range_structure`, `near_edge` (for trade idea generation)

**Implementation Notes:**
```python
# In validate() method
# CRITICAL: Extract parameters from snapshot FIRST (base class methods require individual params)
# CRITICAL: Initialize reasons and details at the start
reasons = []
details = {}

symbol = snapshot.get('symbol', '')
candles = snapshot.get('candles', [])
current_price = snapshot.get('current_price', 0.0)
vwap = snapshot.get('vwap', 0.0)
atr1 = snapshot.get('atr1')
btc_order_flow = snapshot.get('btc_order_flow')

# After Layer 2: Location Filter
# NOTE: RangeScalpChecker MUST override _check_location_filter() to check range edge proximity
# Base class method signature: _check_location_filter(symbol, candles, current_price, vwap, atr1)
location_result = self._check_location_filter(symbol, candles, current_price, vwap, atr1)
details['location'] = location_result

# Store range_structure and near_edge for trade idea generation
if location_result.get('passed'):
    details['range_structure'] = location_result.get('range_structure')
    details['near_edge'] = location_result.get('near_edge')

# After Layer 3: Candle Signals
# NOTE: RangeScalpChecker MUST override _check_candle_signals() to check sweep at edge
# Base class method signature: _check_candle_signals(symbol, candles, current_price, vwap, atr1, btc_order_flow)
signal_result = self._check_candle_signals(symbol, candles, current_price, vwap, atr1, btc_order_flow)
details['signals'] = signal_result

# In Layer 4: Confluence Score
confluence_score = self._calculate_confluence_score(
    symbol, candles, current_price, vwap, atr1,
    location_result, signal_result
)
```

**Trade Idea Generation:**
```python
def generate_trade_idea(self, snapshot, result):
    symbol = snapshot['symbol']
    current_price = snapshot['current_price']
    range_structure = result.details.get('range_structure')
    near_edge = result.details.get('near_edge')  # 'high' or 'low'
    
    if not range_structure or not near_edge:
        return None
    
    # FIXED: Handle both dict and object
    if isinstance(range_structure, dict):
        range_high = range_structure.get('range_high')
        range_low = range_structure.get('range_low')
    else:
        range_high = range_structure.range_high
        range_low = range_structure.range_low
    range_mid = (range_high + range_low) / 2
    
    # Determine direction
    if near_edge == 'low':
        direction = 'BUY'
        entry_price = current_price  # At PDL/range low
        sweep_low = min(c.get('low', current_price) for c in snapshot['candles'][-5:])
        # FIXED: SL calculation - distance from entry to sweep, then add 15% buffer
        if symbol.upper().startswith('BTC'):
            # Distance from entry to sweep low
            distance_to_sweep = entry_price - sweep_low
            # Add 15% buffer beyond sweep
            sl_distance = distance_to_sweep * 1.15
            sl = entry_price - sl_distance  # SL below entry
        else:  # XAU
            sl = entry_price - 3  # 3-6 pts
        # TP1: Mid-range
        tp1 = range_mid
        # TP2 (optional): Opposite side of range
        tp2 = range_high
    else:  # near_edge == 'high'
        direction = 'SELL'
        entry_price = current_price
        sweep_high = max(c.get('high', current_price) for c in snapshot['candles'][-5:])
        # FIXED: SL calculation - distance from entry to sweep, then add 15% buffer
        if symbol.upper().startswith('BTC'):
            # Distance from entry to sweep high
            distance_to_sweep = sweep_high - entry_price
            # Add 15% buffer beyond sweep
            sl_distance = distance_to_sweep * 1.15
            sl = entry_price + sl_distance  # SL above entry
        else:  # XAU
            sl = entry_price + 3
        tp1 = range_mid
        tp2 = range_low
    
    return {
        'symbol': symbol,
        'direction': direction,
        'entry_price': entry_price,
        'sl': sl,
        'tp': tp1,
        'tp2': tp2,
        'volume': 0.01,
        'atr1': snapshot.get('atr1'),
        'strategy': 'range_scalp',
        'confluence_score': result.confluence_score
    }
```

### 3.4 Balanced Zone Strategy Checker

**File:** `infra/micro_scalp_strategies/balanced_zone_checker.py`

**4-Layer Validation:**

#### Layer 1: Pre-Trade Filters
- ATR dropping (compression)
- **NEW**: No news incoming (<15 min) - Re-checked here (not just in detection)
- Spread tight

#### Layer 2: Location Filter
- Price in compression block (inside bars)
- Equal highs/lows detected
- VWAP + mid-range alignment
- **Store in location_result**: `compression`, `equal_highs`, `equal_lows`, `vwap_alignment`, `entry_type`

#### Layer 3: Candle Signals
- **Primary (fade)**: Mini-extreme tap + opposite CHOCH
- **OR Primary (breakout)**: Inside bar/coil break + volume
- **Secondary**: Compression confirmation
- **Store in signal_result**: `primary_count`, `secondary_count`, `volume_on_breakout`

#### Layer 4: Confluence Score
- Compression quality (0-2): Tight structure
- Equal highs/lows (0-2): Confluence
- VWAP alignment (0-2): Mid-range + VWAP
- Volume on breakout (0-1): If breakout type
- Minimum: 5.0
- **Call**: `_calculate_confluence_score(symbol, candles, current_price, vwap, atr1, location_result, signal_result)`
- **Store in result.details**: `entry_type` (for trade idea generation)

**Implementation Notes:**
```python
# In validate() method
# CRITICAL: Extract parameters from snapshot FIRST (base class methods require individual params)
# CRITICAL: Initialize reasons and details at the start
reasons = []
details = {}

symbol = snapshot.get('symbol', '')
candles = snapshot.get('candles', [])
current_price = snapshot.get('current_price', 0.0)
vwap = snapshot.get('vwap', 0.0)
atr1 = snapshot.get('atr1')
btc_order_flow = snapshot.get('btc_order_flow')

# After Layer 2: Location Filter
# NOTE: BalancedZoneChecker MUST override _check_location_filter() to check compression block
# Base class method signature: _check_location_filter(symbol, candles, current_price, vwap, atr1)
location_result = self._check_location_filter(symbol, candles, current_price, vwap, atr1)
details['location'] = location_result

# Store entry_type for trade idea generation
entry_type = location_result.get('entry_type', 'fade')
details['entry_type'] = entry_type

# After Layer 3: Candle Signals
# NOTE: BalancedZoneChecker MUST override _check_candle_signals() to check fade/breakout signals
# Base class method signature: _check_candle_signals(symbol, candles, current_price, vwap, atr1, btc_order_flow)
signal_result = self._check_candle_signals(symbol, candles, current_price, vwap, atr1, btc_order_flow)
details['signals'] = signal_result

# In Layer 4: Confluence Score
confluence_score = self._calculate_confluence_score(
    symbol, candles, current_price, vwap, atr1,
    location_result, signal_result
)
```

**Trade Idea Generation:**
```python
def generate_trade_idea(self, snapshot, result):
    symbol = snapshot['symbol']
    current_price = snapshot['current_price']
    candles = snapshot['candles']
    atr1 = snapshot.get('atr1')
    
    # Determine entry type (fade or breakout)
    # NOTE: entry_type should be set in validate() method during Layer 3 signal detection
    entry_type = result.details.get('entry_type', 'fade')  # 'fade' or 'breakout'
    
    if not entry_type:
        # Fallback: detect from candles
        if len(candles) >= 3:
            compression_high = max(c.get('high', 0) for c in candles[-3:])
            compression_low = min(c.get('low', 0) for c in candles[-3:])
            last_close = candles[-1].get('close', 0)
            
            if last_close > compression_high or last_close < compression_low:
                entry_type = 'breakout'
            else:
                entry_type = 'fade'
        else:
            entry_type = 'fade'
    
    if entry_type == 'fade':
        # Fade mini-extremes
        direction = self._get_fade_direction(candles, current_price)
        last_candle = candles[-1]
        entry_price = current_price
        
        # SL: Super tight (0.10-0.20%)
        if symbol.upper().startswith('BTC'):
            sl_distance = current_price * 0.0015  # 0.15%
            sl = entry_price - sl_distance if direction == 'BUY' else entry_price + sl_distance
        else:  # XAU
            sl = entry_price - 2 if direction == 'BUY' else entry_price + 2  # 2-4 pts
        
        # TP: 1.0R to 1.5R (small, trading noise)
        risk = abs(entry_price - sl)
        tp = entry_price + (risk * 1.25) if direction == 'BUY' else entry_price - (risk * 1.25)
    else:  # breakout
        # Compression breakout
        direction = self._get_breakout_direction(candles)
        last_candle = candles[-1]
        entry_price = last_candle['high'] if direction == 'BUY' else last_candle['low']
        
        # SL: Inside bar low/high
        inside_bar_low = min(c.get('low', current_price) for c in candles[-3:])
        inside_bar_high = max(c.get('high', current_price) for c in candles[-3:])
        sl = inside_bar_low if direction == 'BUY' else inside_bar_high
        
        # TP: 1.0R to 1.5R
        risk = abs(entry_price - sl)
        tp = entry_price + (risk * 1.25) if direction == 'BUY' else entry_price - (risk * 1.25)
    
    return {
        'symbol': symbol,
        'direction': direction,
        'entry_price': entry_price,
        'sl': sl,
        'tp': tp,
        'volume': 0.01,
        'atr1': atr1,
        'strategy': 'balanced_zone',
        'confluence_score': result.confluence_score
    }
```

### 3.5 Edge-Based Strategy Checker (Refactor)

**File:** `infra/micro_scalp_strategies/edge_based_checker.py`

**Purpose:**
- Move current `MicroScalpConditionsChecker` logic here
- Keep as fallback strategy
- Maintain existing behavior

**Implementation:**
- Copy current `MicroScalpConditionsChecker.validate()` logic
- Copy current `MicroScalpEngine._generate_trade_idea()` logic
- No changes to validation or trade idea generation

---

## 🔧 Phase 4: Engine Integration

### 4.1 Modify `MicroScalpEngine`

**File:** `infra/micro_scalp_engine.py`

**Changes:**

1. **Add Regime Detector and Router:**
```python
def __init__(self, config_path: str = "config/micro_scalp_config.json",
             mt5_service: Optional[MT5Service] = None,
             m1_fetcher: Optional[M1DataFetcher] = None,
             streamer: Optional[MultiTimeframeStreamer] = None,  # NEW
             m1_analyzer=None,
             session_manager=None,
             btc_order_flow=None,
             news_service=None):  # NEW
    # ... existing initialization ...
    self.streamer = streamer  # NEW
    self.news_service = news_service  # NEW
    
    # NEW: Initialize regime detector
    from infra.micro_scalp_regime_detector import MicroScalpRegimeDetector
    from infra.micro_scalp_strategy_router import MicroScalpStrategyRouter
    
    self.regime_detector = MicroScalpRegimeDetector(
        config=self.config,
        m1_analyzer=m1_analyzer,
        vwap_filter=self.vwap_filter,
        range_detector=RangeBoundaryDetector(self.config),
        volatility_filter=self.volatility_filter,
        streamer=streamer,  # NEW: For M5/M15 data
        news_service=news_service,  # NEW: For news checks
        mt5_service=mt5_service  # NEW: For M15 trend
    )
    
    self.strategy_router = MicroScalpStrategyRouter(
        config=self.config,
        regime_detector=self.regime_detector,
        m1_analyzer=m1_analyzer  # NEW: For quick confluence check
    )
    
    # NEW: Strategy checker registry
    self.strategy_checkers = {}
```

2. **Modify `check_micro_conditions()`:**
```python
def check_micro_conditions(self, symbol: str, plan_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        # Build snapshot
        snapshot = self._build_snapshot(symbol)
        
        if not snapshot:
            return {'passed': False, 'error': 'Failed to build snapshot'}
        
        # NEW: Store plan_id in snapshot for reference
        if plan_id:
            snapshot['plan_id'] = plan_id
        
        # NEW: Detect regime (with error handling)
        try:
            if not self.regime_detector:
                logger.warning("Regime detector not initialized, using edge-based fallback")
                strategy_name = 'edge_based'
                regime_result = {'regime': 'UNKNOWN', 'detected': False, 'confidence': 0}
            else:
                regime_result = self.regime_detector.detect_regime(snapshot)
                snapshot['regime_result'] = regime_result
                
                # NEW: Extract key characteristics from regime_result for easy access
                characteristics = regime_result.get('characteristics', {})
                if 'range_structure' in characteristics:
                    snapshot['range_structure'] = characteristics['range_structure']
                if 'vwap_deviation' in characteristics:
                    snapshot['vwap_deviation'] = characteristics['vwap_deviation']
                if 'compression' in characteristics:
                    snapshot['compression'] = characteristics['compression']
                if 'vwap_slope' in characteristics:
                    snapshot['vwap_slope'] = characteristics['vwap_slope']
                if 'bb_compression' in characteristics:
                    snapshot['bb_compression'] = characteristics['bb_compression']
                
                # NEW: Select strategy (with error handling)
                try:
                    if not self.strategy_router:
                        logger.warning("Strategy router not initialized, using edge-based fallback")
                        strategy_name = 'edge_based'
                    else:
                        strategy_name = self.strategy_router.select_strategy(snapshot, regime_result)
                except Exception as e:
                    logger.error(f"Error in strategy routing: {e}", exc_info=True)
                    # Fallback to edge-based
                    strategy_name = 'edge_based'
        except Exception as e:
            logger.error(f"Error in regime detection: {e}", exc_info=True)
            # Fallback to edge-based
            strategy_name = 'edge_based'
            regime_result = {'regime': 'UNKNOWN', 'detected': False, 'confidence': 0, 'error': str(e)}
        
        snapshot['strategy'] = strategy_name
        
        # NEW: Get strategy-specific checker (with error handling)
        try:
            checker = self._get_strategy_checker(strategy_name)
        except Exception as e:
            logger.error(f"Error getting strategy checker: {e}", exc_info=True)
            # Fallback to edge-based
            checker = self._get_strategy_checker('edge_based')
        
        # Check conditions using strategy-specific checker
        result = checker.validate(snapshot)
        
        if not result.passed:
            return {
                'passed': False,
                'result': result,
                'snapshot': snapshot,
                'strategy': strategy_name,
                'regime': regime_result.get('regime'),
                'reasons': result.reasons
            }
        
        # NEW: Generate strategy-specific trade idea
        trade_idea = checker.generate_trade_idea(snapshot, result)
        
        # Handle case where trade idea generation fails
        if not trade_idea:
            logger.warning(f"Trade idea generation failed for {symbol} with strategy {strategy_name}")
            return {
                'passed': False,
                'result': result,
                'snapshot': snapshot,
                'strategy': strategy_name,
                'regime': regime_result.get('regime'),
                'reasons': result.reasons + ['Trade idea generation failed'],
                'error': 'Trade idea generation failed',
                'plan_id': plan_id  # NEW: Include plan_id
            }
        
        # NEW: Validate trade idea has required fields
        required_fields = ['symbol', 'direction', 'entry_price', 'sl', 'tp']
        missing_fields = [f for f in required_fields if f not in trade_idea]
        if missing_fields:
            logger.error(f"Trade idea missing required fields: {missing_fields}")
            return {
                'passed': False,
                'result': result,
                'snapshot': snapshot,
                'strategy': strategy_name,
                'regime': regime_result.get('regime'),
                'reasons': result.reasons + [f'Missing trade idea fields: {missing_fields}'],
                'error': 'Invalid trade idea',
                'plan_id': plan_id  # NEW: Include plan_id
            }
        
        return {
            'passed': True,
            'result': result,
            'snapshot': snapshot,
            'trade_idea': trade_idea,
            'strategy': strategy_name,
            'regime': regime_result.get('regime'),
            'is_aplus': result.is_aplus_setup,
            'plan_id': plan_id  # NEW: Include plan_id
        }
    
    except Exception as e:
        logger.error(f"Error checking micro conditions: {e}", exc_info=True)
        return {'passed': False, 'error': str(e)}
```

3. **Add Strategy Checker Factory:**
```python
def _get_strategy_checker(self, strategy_name: str) -> BaseStrategyChecker:
    """Get or create strategy-specific checker with error handling"""
    if strategy_name in self.strategy_checkers:
        return self.strategy_checkers[strategy_name]
    
    try:
        # Import strategy checkers
        if strategy_name == 'vwap_reversion':
            from infra.micro_scalp_strategies.vwap_reversion_checker import VWAPReversionChecker
            checker = VWAPReversionChecker(
                config=self.config,
                volatility_filter=self.volatility_filter,
                vwap_filter=self.vwap_filter,
                sweep_detector=self.sweep_detector,
                ob_detector=self.ob_detector,
                spread_tracker=self.spread_tracker,
                m1_analyzer=self.m1_analyzer,
                session_manager=self.session_manager,
                news_service=self.news_service,  # NEW: For consistency
                strategy_name='vwap_reversion'  # NEW
            )
        elif strategy_name == 'range_scalp':
            from infra.micro_scalp_strategies.range_scalp_checker import RangeScalpChecker
            checker = RangeScalpChecker(
                config=self.config,
                volatility_filter=self.volatility_filter,
                vwap_filter=self.vwap_filter,
                sweep_detector=self.sweep_detector,
                ob_detector=self.ob_detector,
                spread_tracker=self.spread_tracker,
                m1_analyzer=self.m1_analyzer,
                session_manager=self.session_manager,
                news_service=self.news_service,  # NEW: For consistency
                strategy_name='range_scalp'  # NEW
            )
        elif strategy_name == 'balanced_zone':
            from infra.micro_scalp_strategies.balanced_zone_checker import BalancedZoneChecker
            checker = BalancedZoneChecker(
                config=self.config,
                volatility_filter=self.volatility_filter,
                vwap_filter=self.vwap_filter,
                sweep_detector=self.sweep_detector,
                ob_detector=self.ob_detector,
                spread_tracker=self.spread_tracker,
                m1_analyzer=self.m1_analyzer,
                session_manager=self.session_manager,
                news_service=self.news_service,  # NEW: For Layer 1 news check
                strategy_name='balanced_zone'  # NEW
            )
        else:  # edge_based (fallback)
            from infra.micro_scalp_strategies.edge_based_checker import EdgeBasedChecker
            checker = EdgeBasedChecker(
                config=self.config,
                volatility_filter=self.volatility_filter,
                vwap_filter=self.vwap_filter,
                sweep_detector=self.sweep_detector,
                ob_detector=self.ob_detector,
                spread_tracker=self.spread_tracker,
                m1_analyzer=self.m1_analyzer,
                session_manager=self.session_manager,
                news_service=self.news_service,  # NEW: For consistency
                strategy_name='edge_based'  # NEW
            )
    
        self.strategy_checkers[strategy_name] = checker
        return checker
    except ImportError as e:
        logger.error(f"Failed to import strategy checker {strategy_name}: {e}")
        # Fallback to edge-based
        if strategy_name != 'edge_based':
            return self._get_strategy_checker('edge_based')
        raise
    except Exception as e:
        logger.error(f"Failed to initialize strategy checker {strategy_name}: {e}", exc_info=True)
        # Fallback to edge-based
        if strategy_name != 'edge_based':
            return self._get_strategy_checker('edge_based')
        raise
```

4. **Remove Old Methods:**
- Remove `_generate_trade_idea()` (moved to strategy checkers)
- Remove `_determine_direction()` (moved to strategy checkers)
- Keep `_build_snapshot()` (enhanced with M5/M15 data)
- Keep `_calculate_vwap_from_candles()` (unchanged)

5. **Update `MicroScalpMonitor` Integration:**
```python
# In MicroScalpMonitor.__init__() or where engine is created
# Ensure engine is initialized with streamer and news_service
self.engine = MicroScalpEngine(
    config_path=config_path,
    mt5_service=self.mt5_service,
    m1_fetcher=self.m1_fetcher,
    streamer=self.streamer,  # NEW: Pass streamer
    m1_analyzer=self.m1_analyzer,
    session_manager=self.session_manager,
    btc_order_flow=self.btc_order_flow,
    news_service=self.news_service  # NEW: Pass news_service
)
```

---

## 📊 Phase 5: Configuration Updates

### 5.1 Update `config/micro_scalp_config.json`

**Add New Sections:**

```json
{
  "regime_detection": {
    "enabled": true,
    "min_confidence": 60,
    "confidence_diff_threshold": 10,
    "prefer_range_when_close": true,
    "confluence_pre_check": {
      "enabled": true,
      "min_confluence": 5.0
    },
    "confluence_weights": {
      "vwap_reversion": {
        "deviation_sigma": 2.5,
        "choch_quality": 2.0,
        "volume_confirmation": 1.5,
        "vwap_slope": 1.0,
        "min_total": 5.0
      },
      "range_scalp": {
        "edge_proximity": 2.5,
        "sweep_quality": 2.0,
        "range_respect": 2.0,
        "volatility_compression": 1.5,
        "min_total": 5.0
      },
      "balanced_zone": {
        "compression_quality": 2.0,
        "equal_highs_lows": 2.0,
        "vwap_alignment": 2.0,
        "volume_on_breakout": 1.0,
        "min_total": 5.0
      }
    },
    "vwap_reversion": {
      "btc_deviation_threshold": 2.0,
      "btc_deviation_pct": 0.005,
      "xau_deviation_threshold": 2.0,
      "xau_deviation_pct": 0.002,
      "volume_normalization": "z_score",
      "volume_z_score_threshold": 1.5,
      "volume_spike_multiplier": 1.3,
      "vwap_slope_max": 0.0001,
      "atr_stability_lookback": 14
    },
    "range_scalp": {
      "min_range_respects": 2,
      "edge_tolerance_pct": 0.005,
      "bb_compression_threshold": 0.02,
      "m15_trend_max_adx": 20
    },
    "balanced_zone": {
      "atr_drop_threshold": 0.8,
      "compression_bars": 3,
      "vwap_alignment_tolerance": 0.001,
      "news_blackout_minutes": 15,
      "ema_vwap_equilibrium_threshold": 0.001,
      "require_equilibrium_for_fade": true
    }
  },
  
  "strategy_selection": {
    "enabled": true,
    "fallback_to_edge_based": true,
    "priority_order": ["vwap_reversion", "range_scalp", "balanced_zone", "edge_based"]
  },
  
  "vwap_reversion_strategy": {
    "enabled": true,
    "btcusd_rules": {
      "sl_beyond_deviation_pct": 0.15,
      "tp1_target": "vwap",
      "tp2_target": "vwap_mid_band",
      "use_tp2": false
    },
    "xauusd_rules": {
      "sl_beyond_wick_points": 3,
      "tp1_target": "vwap",
      "tp2_target": "vwap_mid_band",
      "use_tp2": false
    }
  },
  
  "range_scalp_strategy": {
    "enabled": true,
    "btcusd_rules": {
      "sl_beyond_sweep_pct": 0.15,
      "tp1_target": "mid_range",
      "tp2_target": "opposite_edge",
      "use_tp2": false
    },
    "xauusd_rules": {
      "sl_beyond_sweep_points": 3,
      "tp1_target": "mid_range",
      "tp2_target": "opposite_edge",
      "use_tp2": false
    }
  },
  
  "balanced_zone_strategy": {
    "enabled": true,
    "btcusd_rules": {
      "fade_sl_pct": 0.15,
      "breakout_sl_pct": 0.20,
      "tp_r_multiple": 1.25
    },
    "xauusd_rules": {
      "fade_sl_points": 2,
      "breakout_sl_points": 3,
      "tp_r_multiple": 1.25
    }
  }
}
```

---

## 🧪 Phase 6: Testing Strategy

### 6.1 Unit Tests

**Files to Create:**
- `tests/test_micro_scalp_regime_detector.py`
- `tests/test_micro_scalp_strategy_router.py`
- `tests/test_base_strategy_checker.py` - **NEW (V10):** Test helper methods accessibility
- `tests/test_vwap_reversion_checker.py`
- `tests/test_range_scalp_checker.py`
- `tests/test_balanced_zone_checker.py`

**Test Coverage:**

**Core Functionality:**
- Regime detection accuracy (VWAP reversion, Range, Balanced Zone)
- Strategy selection logic (router with confidence thresholds)
- 4-layer validation per strategy (pre-trade, location, signals, confluence)
- Trade idea generation (strategy-specific SL/TP logic)
- Edge cases (missing data, zero values, None returns)
- Fallback behavior (edge_based when detection fails)

**V9 Fixes (Implementation & Logic Errors):**
- `plan_id` handling: Test that `plan_id` is stored in snapshot and included in return value
- Snapshot data extraction: Test that `range_structure`, `vwap_deviation`, `compression`, `vwap_slope`, `bb_compression` are extracted from `regime_result.characteristics` into top-level snapshot
- Trade idea validation: Test that trade ideas with missing required fields (`symbol`, `direction`, `entry_price`, `sl`, `tp`) are rejected with appropriate error
- Error handling: Test that `None` trade_idea return is handled gracefully

**V10 Fixes (Helper Method Access & Error Handling):**
- Helper method accessibility: Verify strategy checkers can call base class helper methods
  - `VWAPReversionChecker._check_location_filter()` calls `self._calculate_vwap_std()`, `self._calculate_vwap_slope()`, `self._check_volume_spike()`
  - `RangeScalpChecker._check_location_filter()` calls `self._check_bb_compression()`, `self._count_range_respects()`
  - `BalancedZoneChecker._check_location_filter()` calls `self._check_compression_block()`
- `_candle_to_dict()` robustness: Test with dict, object with `to_dict()`, object with `__dict__`, None, invalid types
- `_check_compression_block_mtf()` error handling:
  - None `m5_candles` → fallback to M1 only
  - Invalid types (not list) → fallback to M1 only
  - Conversion failures (malformed candle objects) → skip invalid, continue with valid
  - Empty `m5_dicts` after conversion → fallback to M1 only

### 6.2 Integration Tests

**Files to Create:**
- `tests/test_adaptive_micro_scalp_engine.py`

**Test Scenarios:**
- Full flow: Snapshot → Regime → Strategy → Validation → Trade Idea
- Fallback to edge-based when regime detection fails
- Strategy switching based on market conditions
- Symbol-specific thresholds (BTC vs XAU)
- **NEW (V9):** `plan_id` included in snapshot and returned in result
- **NEW (V9):** Snapshot contains extracted characteristics (range_structure, vwap_deviation, compression) from regime_result
- **NEW (V9):** Trade idea validation rejects missing required fields
- **NEW (V10):** Strategy checkers successfully call helper methods from `BaseStrategyChecker`
- **NEW (V10):** `_check_compression_block_mtf()` handles malformed M5 candle data gracefully

### 6.3 Backtesting

**Plan:**
- Test each strategy on historical data
- Compare performance vs current edge-based system
- Validate trade frequency increase
- Validate quality maintenance (win rate, R:R)

**Backtest Metrics (Enhanced):**

```python
# Expected backtest metrics per strategy
backtest_metrics = {
    "vwap_reversion": {
        "expected_win_rate": 0.60,  # 60%+
        "expected_avg_rr": 1.5,  # 1.5:1 minimum
        "expected_slippage_tolerance": {
            "btc": 0.001,  # 0.1% slippage tolerance (VWAP reversions can be fast)
            "xau": 0.0005  # 0.05% slippage tolerance
        },
        "max_slippage_impact_rr": 0.1  # Slippage should not reduce R:R by >10%
    },
    "range_scalp": {
        "expected_win_rate": 0.65,  # 65%+ (range edges are reliable)
        "expected_avg_rr": 1.2,  # 1.2:1 minimum
        "expected_slippage_tolerance": {
            "btc": 0.0008,  # 0.08% slippage tolerance
            "xau": 0.0004  # 0.04% slippage tolerance
        },
        "max_slippage_impact_rr": 0.08
    },
    "balanced_zone": {
        "expected_win_rate": 0.55,  # 55%+ (noisier, smaller targets)
        "expected_avg_rr": 1.25,  # 1.25:1 minimum
        "expected_slippage_tolerance": {
            "btc": 0.0012,  # 0.12% slippage tolerance (compression breakouts)
            "xau": 0.0006  # 0.06% slippage tolerance
        },
        "max_slippage_impact_rr": 0.12
    }
}
```

**Slippage Validation:**
- Track actual vs expected entry price
- Calculate slippage impact on R:R
- Reject strategies if slippage reduces R:R by >10-12%
- Adjust SL/TP if slippage is consistently high

---

## 📈 Phase 7: Monitoring & Observability

### 7.1 Enhanced Logging

**Add to `MicroScalpEngine`:**
- Log detected regime and confidence
- Log selected strategy
- Log strategy-specific failure reasons
- Log fallback triggers
- Log regime cache hits/misses (latency tracking)
- Log VWAP slope calculations (ATR-normalized)

### 7.2 Dashboard Updates

**Update `http://localhost:8010/micro-scalp/view`:**

**New Sections:**
1. **Regime Detection Panel:**
   - Current detected regime
   - Regime confidence score
   - Cache hit rate
   - Regime consistency (bars with same regime)

2. **Strategy Selection Panel:**
   - Currently active strategy
   - Strategy selection history (last 10)
   - Fallback frequency
   - Strategy switch frequency

3. **Per-Strategy Performance Panel (ENHANCED):**
   - **Win Rate per Strategy:**
     - VWAP Reversion: X% (N trades)
     - Range Scalp: X% (N trades)
     - Balanced Zone: X% (N trades)
     - Edge Based: X% (N trades)
   
   - **False Regime Rate:**
     - Regime detected but trade failed: X%
     - Regime confidence vs actual outcome correlation
     - Regime detection accuracy (post-trade validation)
   
   - **Average R:R per Strategy:**
     - VWAP Reversion: X:1
     - Range Scalp: X:1
     - Balanced Zone: X:1
     - Edge Based: X:1
   
   - **Slippage Metrics per Strategy:**
     - Average slippage (points/percentage)
     - Slippage impact on R:R
     - Slippage tolerance violations

4. **Strategy-Specific Condition Details:**
   - Show which layer failed (if any)
   - Show confluence scores achieved
   - Show strategy-specific SL/TP logic

### 7.3 Metrics Tracking

**Add Metrics to `MicroScalpMonitor`:**

```python
# Per-strategy metrics
strategy_metrics = {
    "vwap_reversion": {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "avg_rr": 0.0,
        "total_rr": 0.0,
        "false_regime_count": 0,  # Regime detected but trade failed
        "avg_slippage": 0.0,
        "slippage_impact_rr": 0.0
    },
    "range_scalp": {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "avg_rr": 0.0,
        "total_rr": 0.0,
        "false_regime_count": 0,
        "avg_slippage": 0.0,
        "slippage_impact_rr": 0.0
    },
    "balanced_zone": {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "avg_rr": 0.0,
        "total_rr": 0.0,
        "false_regime_count": 0,
        "avg_slippage": 0.0,
        "slippage_impact_rr": 0.0
    },
    "edge_based": {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "avg_rr": 0.0,
        "total_rr": 0.0
    }
}

# Regime detection metrics
regime_metrics = {
    "detection_rate": {
        "vwap_reversion": 0,
        "range": 0,
        "balanced_zone": 0,
        "unknown": 0
    },
    "cache_hit_rate": 0.0,
    "avg_confidence": {
        "vwap_reversion": 0.0,
        "range": 0.0,
        "balanced_zone": 0.0
    },
    "false_regime_rate": 0.0  # Regime detected but trade failed
}
```

**Metrics Update Logic:**
- Update per-strategy metrics on trade close
- Calculate false regime rate: `false_regime_count / total_trades`
- Track slippage: `actual_entry_price - expected_entry_price`
- Calculate slippage impact: `(expected_rr - actual_rr) / expected_rr`
- Update regime metrics on each detection

**Live Recalibration Triggers:**
- If false regime rate > 30% → Lower confidence threshold
- If win rate < expected → Review strategy logic
- If slippage impact > 12% → Adjust SL/TP or entry logic
- If cache hit rate < 50% → Review cache consistency requirements

---

## 🚀 Phase 8: Deployment Plan

### 8.1 Staged Rollout

**Phase 8.1: Feature Flag**
- Add feature flag to enable/disable adaptive strategies
- Default: `disabled` (uses current edge-based system)
- Allows safe testing without affecting production

**Phase 8.2: Shadow Mode**
- Run adaptive system in parallel with current system
- Compare results without executing trades
- Validate regime detection accuracy

**Phase 8.3: Limited Activation**
- Enable for one symbol (e.g., XAUUSDc only)
- Monitor for 1 week
- Compare performance metrics

**Phase 8.4: Full Activation**
- Enable for all symbols
- Monitor closely for first 2 weeks
- Tune thresholds based on real performance

### 8.2 Rollback Plan

**If Issues Detected:**
1. Disable feature flag (instant rollback)
2. System reverts to current edge-based strategy
3. No code changes needed (feature flag only)

---

## 📝 Implementation Checklist

### Phase 0: Foundation
- [ ] Audit existing components
- [ ] Identify missing functionality
- [ ] Document integration points

### Phase 0.5: Data Access Enhancement (NEW)
- [ ] Enhance `_build_snapshot()` to include M5/M15 candles
- [ ] Add VWAP std to snapshot
- [ ] Add `_candle_to_dict()` helper method
- [ ] Add `calculate_atr14()` to `MicroScalpVolatilityFilter`
- [ ] Update `MicroScalpMonitor` to pass `streamer` and `news_service` to engine

### Phase 9: Performance & Quality Enhancements (NEW)
- [ ] Implement dynamic confluence score weighting per strategy
- [ ] Add regime confidence interaction (anti-flip-flop logic)
- [ ] Memoize ATR14 calculation in snapshot
- [ ] Implement Z-score volume normalization for BTC
- [ ] Add confluence pre-check in strategy router
- [ ] Add EMA-VWAP equilibrium filter for balanced zone fade

### Phase 1: Regime Detection
- [ ] Create `MicroScalpRegimeDetector`
- [ ] Implement VWAP reversion detection (Z-score > 2.0 check)
- [ ] Implement range detection (Range width < 1.2 × ATR check)
- [ ] Implement balanced zone detection (BB width < 0.02 check)
- [ ] Add helper methods (`_check_bb_compression`, `_check_volume_spike`, etc.)
- [ ] Add configuration
- [ ] Unit tests
- [ ] Integration tests

### Phase 2: Strategy Router
- [ ] Create `MicroScalpStrategyRouter`
- [ ] Implement strategy selection logic
- [ ] Add fallback handling
- [ ] Unit tests

### Phase 3: Strategy Checkers
- [ ] Create base strategy checker interface (`BaseStrategyChecker` with ABC)
- [ ] Implement VWAP reversion checker
  - [ ] Override `_check_location_filter()` (VWAP deviation logic)
  - [ ] Override `_check_candle_signals()` (CHOCH at extreme logic)
  - [ ] Override `_calculate_confluence_score()` (strategy-specific weights)
- [ ] Implement range scalp checker
  - [ ] Override `_check_location_filter()` (range edge proximity)
  - [ ] Override `_check_candle_signals()` (liquidity sweep + CHOCH)
  - [ ] Override `_calculate_confluence_score()` (strategy-specific weights)
- [ ] Implement balanced zone checker
  - [ ] Override `_check_location_filter()` (EMA-VWAP equilibrium)
  - [ ] Override `_check_candle_signals()` (compression break/fade logic)
  - [ ] Override `_calculate_confluence_score()` (strategy-specific weights)
- [ ] Refactor edge-based checker
  - [ ] Override `_calculate_confluence_score()` (strategy-specific weights)
- [ ] Unit tests for each checker

### Phase 4: Engine Integration
- [ ] Modify `MicroScalpEngine.__init__()` (accept `streamer` and `news_service`)
- [ ] Initialize `MicroScalpRegimeDetector` in `__init__()`
- [ ] Initialize `MicroScalpStrategyRouter` in `__init__()`
- [ ] Initialize `RangeBoundaryDetector` in `__init__()`
- [ ] Modify `MicroScalpEngine.check_micro_conditions()` (new adaptive flow)
- [ ] Add `_get_strategy_checker()` factory method
- [ ] Update `_build_snapshot()` to store ATR14 (memoized)
- [ ] Remove old trade idea generation
- [ ] Integration tests

### Phase 5: Configuration
- [ ] Update `config/micro_scalp_config.json`
- [ ] Add regime detection config
- [ ] Add strategy-specific configs
- [ ] Validate config loading

### Phase 6: Testing
- [ ] Unit tests (all components)
  - [ ] **NEW (V9/V10):** Test helper methods in `BaseStrategyChecker` are accessible to strategy checkers
  - [ ] **NEW (V9):** Test `plan_id` handling in `check_micro_conditions()`
  - [ ] **NEW (V9):** Test snapshot data extraction from `regime_result`
  - [ ] **NEW (V9):** Test trade idea validation (required fields)
  - [ ] **NEW (V10):** Test `_candle_to_dict()` with various formats
  - [ ] **NEW (V10):** Test `_check_compression_block_mtf()` error handling
- [ ] Integration tests
  - [ ] **NEW (V9):** Test `plan_id` propagation through full flow
  - [ ] **NEW (V9):** Test snapshot contains extracted characteristics
  - [ ] **NEW (V10):** Test helper method inheritance works correctly
- [ ] Backtesting
- [ ] Performance validation

### Phase 7: Monitoring
- [ ] Enhanced logging
- [ ] Dashboard updates
- [ ] Metrics tracking

### Phase 8: Deployment
- [ ] Feature flag implementation
- [ ] Shadow mode testing
- [ ] Limited activation
- [ ] Full activation
- [ ] Rollback plan documentation

---

## 🔍 Risk Assessment

### High Risk
- **Regime Detection Accuracy**: If detection is inaccurate, wrong strategies will be selected
  - **Mitigation**: Conservative confidence thresholds, extensive backtesting, fallback to edge-based

### Medium Risk
- **Strategy-Specific SL/TP Logic**: New logic may have bugs
  - **Mitigation**: Unit tests, integration tests, shadow mode validation

### Low Risk
- **Performance Impact**: Additional computation for regime detection
  - **Mitigation**: Caching, efficient algorithms, performance monitoring

---

## 📚 Dependencies

### External Dependencies
- None (all components are internal)

### Internal Dependencies
- `infra/m1_microstructure_analyzer.py` - M1MicrostructureAnalyzer
- `infra/vwap_micro_filter.py` - VWAPMicroFilter (needs enhancement)
- `infra/range_boundary_detector.py` - RangeBoundaryDetector
- `infra/micro_scalp_volatility_filter.py` - MicroScalpVolatilityFilter
- `infra/micro_liquidity_sweep_detector.py` - MicroLiquiditySweepDetector
- `infra/micro_order_block_detector.py` - MicroOrderBlockDetector
- `infra/spread_tracker.py` - SpreadTracker

### New Dependencies to Create
- `infra/micro_scalp_regime_detector.py`
- `infra/micro_scalp_strategy_router.py`
- `infra/micro_scalp_strategies/` (directory)
  - `base_strategy_checker.py`
  - `vwap_reversion_checker.py`
  - `range_scalp_checker.py`
  - `balanced_zone_checker.py`
  - `edge_based_checker.py`

---

## 🎯 Success Criteria

1. **Trade Frequency**: Increase by 30-50% in range/balanced markets
2. **Quality Maintenance**: Win rate and R:R remain similar or improve
   - VWAP Reversion: ≥60% win rate, ≥1.5:1 R:R
   - Range Scalp: ≥65% win rate, ≥1.2:1 R:R
   - Balanced Zone: ≥55% win rate, ≥1.25:1 R:R
3. **Regime Detection**: >80% accuracy in regime classification
4. **False Regime Rate**: <30% (regime detected but trade failed)
5. **Fallback Reliability**: 100% fallback success rate when detection fails
6. **Performance**: <50ms additional latency per check (with caching)
7. **Slippage Tolerance**: 
   - VWAP Reversion: <0.1% (BTC), <0.05% (XAU)
   - Range Scalp: <0.08% (BTC), <0.04% (XAU)
   - Balanced Zone: <0.12% (BTC), <0.06% (XAU)
   - Slippage impact on R:R: <10-12%
8. **Cache Efficiency**: >50% cache hit rate (reduces computation)
9. **Strategy-Specific Metrics**: All strategies meet their expected win rates and R:R targets

---

## 📅 Timeline Estimate

- **Phase 0**: 1 day (analysis complete)
- **Phase 0.5**: 1 day (data access enhancement) - **NEW**
- **Phase 1**: 3-4 days (regime detection)
- **Phase 9**: 2-3 days (performance enhancements) - **NEW**
- **Phase 2**: 1 day (router)
- **Phase 3**: 4-5 days (strategy checkers)
- **Phase 4**: 2 days (engine integration)
- **Phase 5**: 1 day (configuration)
- **Phase 6**: 3-4 days (testing)
- **Phase 7**: 2 days (monitoring)
- **Phase 8**: 1 week (staged deployment)

**Total**: ~3-4 weeks for full implementation and deployment (includes Phase 0.5 and Phase 9)

---

## 📖 Notes

- This plan leverages 80%+ of existing infrastructure
- All new components follow existing patterns and conventions
- Backward compatibility maintained through fallback mechanism
- Feature flag allows safe testing and instant rollback
- Configuration-driven for easy tuning without code changes

---

---

## ⚙️ Phase 9: Performance & Quality Enhancements (See Below)

### 9.1 Dynamic Confluence Score Weighting

**Issue:** Static 0-8 confluence scale doesn't reflect strategy-specific volatility sensitivities.

**Solution:** Implement per-strategy dynamic weighting.

**Implementation:**

```python
# In config/micro_scalp_config.json
{
  "regime_detection": {
    "confluence_weights": {
      "vwap_reversion": {
        "deviation_sigma": 2.5,  # High weight (most important)
        "choch_quality": 2.0,
        "volume_confirmation": 1.5,  # Lower weight
        "vwap_slope": 1.0,
        "min_total": 5.0
      },
      "range_scalp": {
        "edge_proximity": 2.5,  # High weight (most important)
        "sweep_quality": 2.0,
        "range_respect": 2.0,
        "volatility_compression": 1.5,
        "min_total": 5.0
      },
      "balanced_zone": {
        "compression_quality": 2.0,
        "equal_highs_lows": 2.0,
        "vwap_alignment": 2.0,
        "volume_on_breakout": 1.0,  # Only if breakout type
        "min_total": 5.0
      }
    }
  }
}
```

**Code Changes:**

```python
# In each strategy checker's Layer 4 calculation
# FIXED: Match base class signature
def _calculate_confluence_score(self, symbol: str, candles: List[Dict[str, Any]],
                               current_price: float, vwap: float, atr1: Optional[float],
                               location_result: Dict[str, Any],
                               signal_result: Dict[str, Any]) -> float:
    """Calculate strategy-specific weighted confluence score"""
    weights = self.config.get('regime_detection', {}).get('confluence_weights', {}).get(self.strategy_name, {})
    
    if not weights:
        # Fallback to base class default
        return super()._calculate_confluence_score(
            symbol, candles, current_price, vwap, atr1,
            location_result, signal_result
        )
    
    score = 0.0
    
    # FIXED: Extract data from location_result and signal_result instead of result.details
    # VWAP Reversion weights
    if self.strategy_name == 'vwap_reversion':
        deviation_sigma = location_result.get('deviation_sigma', 0)
        if deviation_sigma >= 2.0:
            score += weights.get('deviation_sigma', 2.5)
        
        choch_quality = 2.0 if signal_result.get('primary_count', 0) >= 1 else 0
        score += choch_quality * (weights.get('choch_quality', 2.0) / 2.0)
        
        volume_conf = 2.0 if location_result.get('volume_spike', False) else 0
        score += volume_conf * (weights.get('volume_confirmation', 1.5) / 2.0)
        
        vwap_slope_ok = 1.0 if location_result.get('vwap_slope_ok', False) else 0
        score += vwap_slope_ok * weights.get('vwap_slope', 1.0)
    
    # Range Scalp weights
    elif self.strategy_name == 'range_scalp':
        edge_proximity = location_result.get('edge_proximity_score', 0)
        score += edge_proximity * (weights.get('edge_proximity', 2.5) / 2.0)
        
        sweep_quality = signal_result.get('sweep_quality_score', 0)
        score += sweep_quality * (weights.get('sweep_quality', 2.0) / 2.0)
        
        range_respects = location_result.get('range_respects', 0)
        range_respect_score = min(2.0, range_respects)
        score += range_respect_score * (weights.get('range_respect', 2.0) / 2.0)
        
        bb_compression = 1.0 if location_result.get('bb_compression', False) else 0
        score += bb_compression * weights.get('volatility_compression', 1.5)
    
    # Balanced Zone weights
    elif self.strategy_name == 'balanced_zone':
        compression_quality = 2.0 if location_result.get('compression', False) else 0
        score += compression_quality * (weights.get('compression_quality', 2.0) / 2.0)
        
        equal_highs_lows = 2.0 if (location_result.get('equal_highs', False) or location_result.get('equal_lows', False)) else 0
        score += equal_highs_lows * (weights.get('equal_highs_lows', 2.0) / 2.0)
        
        vwap_alignment = 2.0 if location_result.get('vwap_alignment', False) else 0
        score += vwap_alignment * (weights.get('vwap_alignment', 2.0) / 2.0)
        
        if location_result.get('entry_type') == 'breakout':
            volume_breakout = 1.0 if signal_result.get('volume_on_breakout', False) else 0
            score += volume_breakout * weights.get('volume_on_breakout', 1.0)
    
    return score
```

---

### 9.2 Regime Confidence Interaction (Anti-Flip-Flop)

**Issue:** Independent thresholds can cause oscillation between VWAP ↔ Range in transition periods.

**Solution:** Add relative confidence comparison to prevent flip-flopping.

**Implementation:**

```python
# In MicroScalpRegimeDetector._detect_regime_fresh()
def _detect_regime_fresh(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Perform fresh regime detection with anti-flip-flop logic"""
    # ... existing detection code ...
    
    # Check all regimes
    vwap_result = self._detect_vwap_reversion(snapshot)
    range_result = self._detect_range(snapshot)
    balanced_result = self._detect_balanced_zone(snapshot)
    
    # Get confidence values
    vwap_conf = vwap_result.get('confidence', 0) if vwap_result.get('detected') else 0
    range_conf = range_result.get('confidence', 0) if range_result.get('detected') else 0
    balanced_conf = balanced_result.get('confidence', 0) if balanced_result.get('detected') else 0
    
    # Anti-flip-flop: If VWAP and Range are close, prefer Range (more stable)
    confidence_diff_threshold = self.config.get('regime_detection', {}).get('confidence_diff_threshold', 10)
    
    if vwap_result.get('detected') and range_result.get('detected'):
        if abs(vwap_conf - range_conf) < confidence_diff_threshold:
            # Both near threshold, prefer Range to avoid flip-flop
            logger.debug(f"VWAP ({vwap_conf}) and Range ({range_conf}) close, preferring Range")
            # Boost Range confidence slightly for selection
            range_result['confidence'] = range_conf + 2
            # Reduce VWAP confidence to prevent selection
            vwap_result['confidence'] = max(0, vwap_conf - 2)
    
    # Priority ordering: VWAP Reversion > Range > Balanced Zone
    candidates = []
    
    if vwap_result.get('detected') and vwap_result.get('confidence', 0) >= vwap_result.get('min_confidence_threshold', 70):
        candidates.append(('VWAP_REVERSION', vwap_result))
    
    if range_result.get('detected') and range_result.get('confidence', 0) >= range_result.get('min_confidence_threshold', 55):
        candidates.append(('RANGE', range_result))
    
    if balanced_result.get('detected') and balanced_result.get('confidence', 0) >= balanced_result.get('min_confidence_threshold', 65):
        candidates.append(('BALANCED_ZONE', balanced_result))
    
    # ... rest of selection logic ...
```

**Configuration:**

```json
{
  "regime_detection": {
    "confidence_diff_threshold": 10,  // If confidence diff < 10, prefer Range
    "prefer_range_when_close": true
  }
}
```

---

### 9.3 ATR14 Calculation Efficiency (Memoization)

**Issue:** `calculate_atr14()` is called frequently, causing recomputation overhead.

**Solution:** Memoize ATR14 in snapshot or use cached calculation.

**Implementation:**

```python
# In MicroScalpEngine._build_snapshot()
def _build_snapshot(self, symbol: str) -> Optional[Dict[str, Any]]:
    """Build snapshot with memoized ATR14"""
    # ... existing code ...
    
    # Calculate ATR14 once and store in snapshot (with validation)
    atr14 = None
    if candles and len(candles) >= 14:
        try:
            atr14 = self.volatility_filter.calculate_atr14(candles[-14:])
            if atr14 is None or atr14 <= 0:
                atr14 = None  # Invalid ATR
        except Exception as e:
            logger.debug(f"Error calculating ATR14: {e}")
            atr14 = None
    
    snapshot = {
        # ... existing fields ...
        'atr1': atr1,
        'atr14': atr14,  # NEW: Memoized ATR14
        # ... rest of fields ...
    }
    
    return snapshot

# In MicroScalpRegimeDetector helper methods
def _check_atr_stability(self, candles: List[Dict[str, Any]], snapshot: Dict[str, Any]) -> bool:
    """Check ATR stability using memoized ATR14"""
    # Use memoized ATR14 from snapshot if available
    atr14_recent = snapshot.get('atr14')
    
    if not atr14_recent or len(candles) < 28:
        return False
    
    # Calculate previous period ATR14
    previous_candles = candles[-28:-14] if len(candles) >= 28 else candles[:14]
    atr14_previous = self.volatility_filter.calculate_atr14(previous_candles)
    
    if atr14_previous <= 0:
        return atr14_recent > 0
    
    # Check if ATR is stable (within 10% of previous) or rising
    atr_ratio = atr14_recent / atr14_previous
    return 0.9 <= atr_ratio <= 1.5

def _check_atr_dropping(self, candles: List[Dict], snapshot: Dict[str, Any]) -> bool:
    """Check if ATR is decreasing using memoized ATR14"""
    # Use memoized ATR14 from snapshot
    atr14_recent = snapshot.get('atr14')
    
    if not atr14_recent or len(candles) < 28:
        return False
    
    # Calculate previous period ATR14
    previous_candles = candles[-28:-14] if len(candles) >= 28 else candles[:14]
    atr14_previous = self.volatility_filter.calculate_atr14(previous_candles)
    
    if atr14_previous <= 0:
        return False
    
    # Check if ATR is dropping
    atr_drop_threshold = self.config.get('regime_detection', {}).get('balanced_zone', {}).get('atr_drop_threshold', 0.8)
    atr_ratio = atr14_recent / atr14_previous
    
    return atr_ratio < atr_drop_threshold
```

**Performance Impact:**
- Reduces ATR14 calculations from 3-4 per snapshot to 1
- Estimated 20-30% reduction in detection latency

---

### 9.4 Volume Normalization for BTC (Z-Score)

**Issue:** BTC volume spikes vary dramatically between exchanges; fixed 1.3× multiplier is exchange-dependent.

**Solution:** Use Z-score normalization based on 30-bar mean and std dev.

**Implementation:**

```python
def _check_volume_spike(self, candles: List[Dict]) -> bool:
    """Check volume spike using Z-score normalization (exchange-agnostic)"""
    if len(candles) < 31:
        return False
    
    # Get last candle volume
    last_volume = candles[-1].get('volume', 0)
    if last_volume == 0:
        return False
    
    # Calculate 30-bar statistics
    recent_volumes = [c.get('volume', 0) for c in candles[-31:-1]]  # Exclude last candle
    
    if not recent_volumes or all(v == 0 for v in recent_volumes):
        return False
    
    # Calculate mean and standard deviation
    import statistics
    mean_volume = statistics.mean(recent_volumes)
    std_volume = statistics.stdev(recent_volumes) if len(recent_volumes) > 1 else 0
    
    if std_volume == 0:
        # No variation, use simple multiplier as fallback
        volume_multiplier = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_spike_multiplier', 1.3)
        return last_volume >= mean_volume * volume_multiplier
    
    # Calculate Z-score
    z_score = (last_volume - mean_volume) / std_volume
    
    # Volume spike: Z-score >= threshold (typically 1.5-2.0)
    z_score_threshold = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_z_score_threshold', 1.5)
    
    return z_score >= z_score_threshold
```

**Configuration:**

```json
{
  "regime_detection": {
    "vwap_reversion": {
      "volume_normalization": "z_score",  // "multiplier" or "z_score"
      "volume_z_score_threshold": 1.5,    // Z-score threshold for spike
      "volume_spike_multiplier": 1.3      // Fallback if std=0
    }
  }
}
```

**Benefits:**
- Exchange-agnostic volume detection
- Adapts to different exchange volume characteristics
- More robust across BTC markets

---

### 9.5 Router Integration with Confluence Pre-Check

**Issue:** Router only considers regime confidence; should also check confluence before execution.

**Solution:** Add confluence pre-check in router to add safety layer.

**Implementation:**

```python
# In MicroScalpStrategyRouter.select_strategy()
def select_strategy(self, snapshot, regime_result):
    regime = regime_result.get('regime', 'UNKNOWN')
    confidence = regime_result.get('confidence', 0)
    min_confidence = regime_result.get('min_confidence_threshold', 60)
    
    # Check if regime detection is enabled
    if not self.config.get('regime_detection', {}).get('enabled', True):
        return 'edge_based'
    
    # If confidence too low, fallback
    if confidence < min_confidence:
        logger.debug(f"Regime confidence {confidence} < {min_confidence}, using edge-based fallback")
        return 'edge_based'
    
    # NEW: Confluence pre-check (quick validation before full strategy check)
    # This prevents selecting a strategy that will fail Layer 4 anyway
    confluence_pre_check_enabled = self.config.get('regime_detection', {}).get('confluence_pre_check', {}).get('enabled', True)
    
    if confluence_pre_check_enabled:
        # FIXED: Pass regime_result instead of accessing from snapshot
        quick_confluence = self._quick_confluence_check(snapshot, regime_result)
        min_confluence = self.config.get('regime_detection', {}).get('confluence_pre_check', {}).get('min_confluence', 5.0)
        
        if quick_confluence < min_confluence:
            logger.debug(f"Quick confluence check failed ({quick_confluence} < {min_confluence}), using edge-based fallback")
            return 'edge_based'
    
    # Strategy priority ordering
    if regime == 'VWAP_REVERSION':
        return 'vwap_reversion'
    elif regime == 'RANGE':
        return 'range_scalp'
    elif regime == 'BALANCED_ZONE':
        return 'balanced_zone'
    else:
        logger.debug(f"Unknown regime {regime}, using edge-based fallback")
        return 'edge_based'

def _quick_confluence_check(self, snapshot: Dict[str, Any], regime_result: Dict[str, Any]) -> float:
    """Quick confluence estimation using regime_result"""
    regime = regime_result.get('regime', 'UNKNOWN')
    characteristics = regime_result.get('characteristics', {})
    
    if regime == 'VWAP_REVERSION':
        # Quick check: deviation + CHOCH
        deviation_sigma = characteristics.get('deviation_sigma', 0)
        
        # FIXED: Get CHOCH from M1 analysis (not from regime_result)
        choch_detected = False
        if self.m1_analyzer:
            try:
                analysis = self.m1_analyzer.analyze_microstructure(
                    snapshot.get('symbol', ''),
                    snapshot.get('candles', [])
                )
                choch_bos = analysis.get('choch_bos', {})
                choch_detected = choch_bos.get('has_choch', False) or choch_bos.get('choch_confirmed', False)
            except Exception:
                choch_detected = False
        
        score = 0.0
        if deviation_sigma >= 2.0:
            score += 2.5
        if choch_detected:
            score += 2.0
        return score
    
    elif regime == 'RANGE':
        # Quick check: edge proximity + range structure
        range_structure = characteristics.get('range_structure')
        near_edge = characteristics.get('near_edge')
        
        score = 0.0
        if range_structure and near_edge:
            score += 2.5
        if characteristics.get('range_respects', 0) >= 2:
            score += 2.0
        return score
    
    elif regime == 'BALANCED_ZONE':
        # Quick check: compression + equal highs/lows
        compression = characteristics.get('compression', False)
        equal_highs = characteristics.get('equal_highs', False)
        equal_lows = characteristics.get('equal_lows', False)
        
        score = 0.0
        if compression:
            score += 2.0
        if equal_highs or equal_lows:
            score += 2.0
        if characteristics.get('vwap_alignment', False):
            score += 2.0
        return score
    
    return 0.0
```

**Configuration:**

```json
{
  "regime_detection": {
    "confluence_pre_check": {
      "enabled": true,
      "min_confluence": 5.0  // Minimum quick confluence to proceed
    }
  }
}
```

---

### 9.6 Balanced Zone Fade Detection Enhancement

**Issue:** Need EMA(20)-VWAP distance filter to confirm equilibrium before fading.

**Solution:** Add EMA-VWAP alignment check to prevent early entry into expansion.

**Implementation:**

```python
# In BalancedZoneChecker._check_location_filter()
# CRITICAL: Must match base class signature for proper override
def _check_location_filter(self, symbol: str, candles: List[Dict[str, Any]],
                          current_price: float, vwap: float, atr1: Optional[float]) -> Dict[str, Any]:
    """Balanced Zone-specific location filter with EMA-VWAP equilibrium check"""
    # Check compression block (inside bars)
    compression = self._check_compression_block(candles, atr1)
    
    # Check equal highs/lows
    equal_highs = False
    equal_lows = False
    if self.m1_analyzer:
        try:
            analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
            liquidity_zones = analysis.get('liquidity_zones', {})
            equal_highs = liquidity_zones.get('equal_highs_detected', False)
            equal_lows = liquidity_zones.get('equal_lows_detected', False)
        except Exception:
            pass
    
    # Check VWAP + mid-range alignment
    vwap_alignment = False
    if vwap and len(candles) >= 20:
        intraday_high = max(c.get('high', 0) for c in candles[-20:])
        intraday_low = min(c.get('low', 0) for c in candles[-20:])
        mid_range = (intraday_high + intraday_low) / 2
        vwap_alignment = abs(vwap - mid_range) / mid_range < 0.001 if mid_range > 0 else False
    
    # Detect entry type (fade or breakout)
    entry_type = self._detect_entry_type_from_candles(candles)
    
    # NEW: EMA(20)-VWAP distance filter for fade entries
    if entry_type == 'fade':
        # For fade entries, require EMA-VWAP alignment (equilibrium)
        if len(candles) >= 20 and vwap:
            # Calculate EMA(20)
            ema20 = self._calculate_ema(candles, period=20)
            
            if ema20:
                # Check EMA-VWAP distance
                ema_vwap_distance = abs(ema20 - vwap) / vwap if vwap > 0 else float('inf')
                
                # Equilibrium: EMA and VWAP within 0.1% of each other
                equilibrium_threshold = self.config.get('regime_detection', {}).get('balanced_zone', {}).get('ema_vwap_equilibrium_threshold', 0.001)
                
                if ema_vwap_distance > equilibrium_threshold:
                    return {
                        'passed': False,
                        'compression': compression,
                        'equal_highs': equal_highs,
                        'equal_lows': equal_lows,
                        'vwap_alignment': vwap_alignment,
                        'entry_type': entry_type,
                        'reasons': [f"EMA-VWAP distance {ema_vwap_distance:.4f} > {equilibrium_threshold} (not in equilibrium)"]
                    }
    
    # Return location filter result
    passed = compression and (equal_highs or equal_lows) and vwap_alignment
    
    return {
        'passed': passed,
        'compression': compression,
        'equal_highs': equal_highs,
        'equal_lows': equal_lows,
        'vwap_alignment': vwap_alignment,
        'entry_type': entry_type,
        'reasons': [] if passed else [
            'No compression block' if not compression else '',
            'No equal highs/lows' if not (equal_highs or equal_lows) else '',
            'VWAP not aligned with mid-range' if not vwap_alignment else ''
        ]
    }

def _calculate_ema(self, candles: List[Dict], period: int) -> Optional[float]:
    """Calculate EMA(period) from candles (no DataFrame dependency)"""
    if len(candles) < period:
        return None
    
    try:
        # Get closes
        closes = [c.get('close', 0) for c in candles[-period:]]
        
        if not closes or all(c == 0 for c in closes):
            return None
        
        # Calculate EMA manually (no pandas dependency)
        multiplier = 2.0 / (period + 1)
        ema = closes[0]  # Start with first close
        
        for close in closes[1:]:
            ema = (close * multiplier) + (ema * (1 - multiplier))
        
        return ema
    except Exception as e:
        logger.debug(f"Error calculating EMA: {e}")
        return None

def _detect_entry_type_from_candles(self, candles: List[Dict[str, Any]]) -> str:
    """Detect entry type (fade or breakout) for balanced zone from candles"""
    if len(candles) < 3:
        return 'fade'
    
    compression_high = max(c.get('high', 0) for c in candles[-3:])
    compression_low = min(c.get('low', 0) for c in candles[-3:])
    last_close = candles[-1].get('close', 0)
    
    if last_close > compression_high or last_close < compression_low:
        return 'breakout'
    else:
        return 'fade'
```

**Configuration:**

```json
{
  "regime_detection": {
    "balanced_zone": {
      "ema_vwap_equilibrium_threshold": 0.001,  // 0.1% max distance for equilibrium
      "require_equilibrium_for_fade": true
    }
  }
}
```

**Benefits:**
- Prevents entering fade trades during expansion phases
- Confirms equilibrium before mean reversion entry
- Reduces false fade signals

---

## 🔄 Version 1.7 Data Flow & Integration Fixes (2025-12-03)

### Additional Critical Data Flow Issues Fixed

1. **Streamer Error Handling:**
   - ✅ Fixed: Added `is_running` check before using streamer
   - ✅ Fixed: Added error handling for empty candle lists
   - ✅ Fixed: Added fallback to None if streamer unavailable

2. **RangeStructure Access Error:**
   - ✅ Fixed: Added handling for both dict and object types
   - ✅ Fixed: Safe access using `isinstance()` check

3. **Confluence Score Signature Mismatch:**
   - ✅ Fixed: Changed signature to match base class: `(symbol, candles, current_price, vwap, atr1, location_result, signal_result)`
   - ✅ Fixed: Updated all data access to use `location_result` and `signal_result` instead of `result.details`
   - ✅ Fixed: Removed reference to non-existent `_calculate_confluence_default()` method

4. **Missing Data Storage in Result Details:**
   - ✅ Fixed: Added documentation for storing `range_structure` and `near_edge` in `result.details` for RangeScalpChecker
   - ✅ Fixed: Added documentation for storing `entry_type` in `result.details` for BalancedZoneChecker
   - ✅ Fixed: Added documentation for storing location_result and signal_result in result.details for confluence calculation

5. **Location Result Data Storage:**
   - ✅ Fixed: Documented what data should be stored in `location_result` for each strategy
   - ✅ Fixed: Documented what data should be stored in `signal_result` for each strategy

---

## 🔄 Version 1.6 Additional Critical Fixes (2025-12-03)

### Additional Critical Issues Fixed

1. **Indentation Error in `_detect_regime_fresh()`:**
   - ✅ Fixed: Corrected indentation of `if not candidates:` return block
   - ✅ Fixed: Moved unreachable code outside the if block

2. **Missing `LocationFilterResult` Class:**
   - ✅ Fixed: Changed return type from `LocationFilterResult` to `Dict[str, Any]` to match existing codebase
   - ✅ Updated all `LocationFilterResult` usages to dict format

3. **RangeStructure Creation Error:**
   - ✅ Fixed: Added `CriticalGapZones` creation with all 4 required fields
   - ✅ Fixed: Changed `touch_count` from `int` to `Dict[str, int]` (empty dict)
   - ✅ Fixed: Removed invalid fields (`range_width`, `created_at`)
   - ✅ Fixed: Added all required fields (`validated`, `nested_ranges`, `expansion_state`, `invalidation_signals`)

4. **Import Indentation Errors:**
   - ✅ Fixed: Corrected indentation for all strategy checker imports (lines 1923, 1936, 1949, 1963)
   - ✅ All imports now properly indented inside their respective `if/elif` blocks

5. **Missing `news_service` in Checkers:**
   - ✅ Fixed: Added `news_service=self.news_service` to all checker initializations
   - ✅ Ensures consistency across all strategy checkers

6. **Missing Error Handling:**
   - ✅ Fixed: Added proper error handling in strategy checker factory
   - ✅ Added fallback to `edge_based` on ImportError or Exception
   - ✅ Added logging for debugging

7. **Missing Helper Methods:**
   - ✅ Added: `_get_pdh()` and `_get_pdl()` helper methods documented (implementation depends on session manager/MT5 API)

---

## 🔄 Version 1.5 Final Review Fixes (2025-12-03)

### Critical Logic & Implementation Fixes

1. **CHOCH Data Access Error:**
   - ✅ Fixed: Changed from `structure.get('choch_detected')` to `choch_bos.get('has_choch')`
   - ✅ Updated `_get_direction_from_choch()` to use correct dictionary path
   - ✅ Updated `_quick_confluence_check()` to access CHOCH from M1 analysis

2. **ATR14 Memoization Inconsistency:**
   - ✅ Fixed: Updated `_check_atr_stability()` to use `snapshot` parameter instead of `atr1`
   - ✅ Fixed: Updated `_check_atr_dropping()` to use `snapshot` parameter instead of `atr1`
   - ✅ Updated call sites in `_detect_vwap_reversion()` and `_detect_balanced_zone()`

3. **Volume Spike Method:**
   - ✅ Fixed: Made volume normalization configurable (multiplier vs Z-score)
   - ✅ Added `_check_volume_spike_multiplier()` and `_check_volume_spike_zscore()` helper methods
   - ✅ Main method routes to appropriate implementation based on config

4. **Quick Confluence Check Timing:**
   - ✅ Fixed: Changed to pass `regime_result` as parameter instead of accessing from snapshot
   - ✅ Updated method signature: `_quick_confluence_check(snapshot, regime_result)`
   - ✅ Added M1 analyzer access in router for CHOCH detection

5. **EMA Calculation:**
   - ✅ Fixed: Removed DataFrame dependency, implemented manual EMA calculation
   - ✅ No longer requires `_candles_to_df()` method in BalancedZoneChecker

6. **_current_snapshot Usage:**
   - ✅ Fixed: Changed `_check_compression_block()` to accept `atr1` as parameter
   - ✅ Updated call sites to pass `atr1` from snapshot

7. **Missing Methods:**
   - ✅ Added `_detect_entry_type()` method to BalancedZoneChecker
   - ✅ Added `strategy_name` parameter to BaseStrategyChecker
   - ✅ Updated all checker initializations to include `strategy_name`

8. **Missing Imports:**
   - ✅ Added type imports: `Dict, Any, List, Optional`
   - ✅ Added `statistics` import for Z-score calculation

---

## 🔄 Version 1.3 Fixes (2025-12-03)

### Additional Critical Fixes Applied

1. **Missing Helper Method Implementations:**
   - ✅ Implemented `_check_volume_spike()` - Volume spike detection
   - ✅ Implemented `_check_bb_compression()` - Bollinger Band compression check
   - ✅ Implemented `_check_compression_block()` - Inside bar detection
   - ✅ Implemented `_check_atr_dropping()` - ATR compression validation
   - ✅ Implemented `_check_choppy_liquidity()` - Choppy market detection
   - ✅ Implemented `_count_range_respects()` - Range bounce counting
   - ✅ Implemented `_calculate_vwap_std()` - VWAP standard deviation
   - ✅ Implemented `_create_range_from_pdh_pdl()` - PDH/PDL range creation
   - ✅ Implemented `_get_direction_from_choch()` - CHOCH direction extraction
   - ✅ Implemented `_get_fade_direction()` - Balanced zone fade direction
   - ✅ Implemented `_get_breakout_direction()` - Balanced zone breakout direction

2. **VWAP Reversion SL Calculation Fix:**
   - ✅ Fixed SL calculation logic (corrected direction and distance calculation)
   - ✅ Fixed entry price logic (handle already-broken vs not-yet-broken cases)

3. **News Check Integration:**
   - ✅ Added news check to Balanced Zone Checker Layer 1 (not just detection)
   - ✅ Pass `news_service` to `BalancedZoneChecker` initialization

4. **Configuration Consistency:**
   - ✅ Use config values for confidence thresholds (not hardcoded)
   - ✅ All thresholds now read from `strategy_confidence_thresholds` config

5. **Data Validation:**
   - ✅ Added validation to `_candles_to_df()` (time format handling)
   - ✅ Added validation to compression block checks
   - ✅ Added ATR validation in stability checks

6. **Result Details Storage:**
   - ✅ Documented storing `range_structure` and `near_edge` in RangeScalpChecker
   - ✅ Documented storing `entry_type` in BalancedZoneChecker

7. **Logger Import:**
   - ✅ Added logger import at top of `MicroScalpRegimeDetector`

---

## 🔄 Version 1.2 Fixes (2025-12-03)

### Critical Fixes Applied

1. **Data Access Dependencies:**
   - ✅ Added `MultiTimeframeStreamer`, `NewsService`, `MT5Service` to `MicroScalpRegimeDetector` dependencies
   - ✅ Enhanced `_build_snapshot()` to include M5/M15 candles and VWAP std
   - ✅ Added `_candle_to_dict()` helper for data conversion

2. **Missing Method Implementations:**
   - ✅ Implemented `_candles_to_df()` for DataFrame conversion
   - ✅ Implemented `_calculate_vwap_slope()` with ATR normalization
   - ✅ Implemented `_calculate_vwap_from_candles()` helper
   - ✅ Implemented `_check_m15_trend()` with fallback logic
   - ✅ Implemented `_check_atr_stability()` using ATR(14)
   - ✅ Added `calculate_atr14()` to `MicroScalpVolatilityFilter`

3. **Logic Fixes:**
   - ✅ Fixed strategy router to use detection-specific confidence thresholds
   - ✅ Implemented multiple regime priority selection in `_detect_regime_fresh()`
   - ✅ Enhanced cache invalidation with confidence threshold check
   - ✅ Fixed range scalp SL calculation (corrected direction)
   - ✅ Fixed VWAP reversion entry price logic (use max/min of current vs signal)

4. **Integration Fixes:**
   - ✅ Updated range detection to use M15 data from snapshot
   - ✅ Updated balanced zone to use M5 data from snapshot
   - ✅ Added news service integration for balanced zone
   - ✅ Added error handling to strategy checker factory

5. **New Phase Added:**
   - ✅ Phase 0.5: Data Access Enhancement (snapshot building and ATR(14))

---

## 🔄 Version 1.1 Enhancements (2025-12-03)

### Enhancements Based on Expert Review

1. **Confidence Weight Calibration:**
   - ✅ Strategy-specific confidence thresholds:
     - VWAP Reversion: 70% (higher confidence required)
     - Range Scalp: 55% (lower threshold, more opportunities)
     - Balanced Zone: 65% (moderate confidence)
   - ✅ Thresholds calibrated from backtest recommendations

2. **Latency Risk Mitigation:**
   - ✅ Regime caching with 3-bar rolling memory
   - ✅ Cache consistency check (2+ bars required)
   - ✅ Prevents excessive regime switching
   - ✅ Reduces computation by reusing cached results

3. **Balanced Zone Entry Precision:**
   - ✅ M1-M5 multi-timeframe compression confirmation
   - ✅ Reduces false fades in low-volume sessions
   - ✅ Requires both M1 and M5 to show compression
   - ✅ Fallback to M1-only if M5 unavailable

4. **VWAP Slope & ATR Handling:**
   - ✅ Dynamic slope normalization by ATR
   - ✅ Scales across assets (BTC vs XAU)
   - ✅ Fallback to fixed threshold if ATR unavailable
   - ✅ Normalized threshold: 10% of ATR per bar

5. **Backtest Metrics Enhancement:**
   - ✅ Slippage tolerance per strategy
   - ✅ Slippage impact on R:R tracking
   - ✅ Expected slippage limits defined
   - ✅ Slippage validation in backtests

6. **Monitoring Layer Enhancement:**
   - ✅ Per-strategy win rate tracking
   - ✅ False regime rate tracking
   - ✅ Per-strategy slippage metrics
   - ✅ Live recalibration triggers
   - ✅ Dashboard panels for all metrics

### Impact of Enhancements

- **Reduced False Signals**: Multi-timeframe confirmation and higher confidence thresholds
- **Improved Performance**: Caching reduces latency by 30-50%
- **Better Risk Management**: Slippage tracking prevents poor execution
- **Data-Driven Tuning**: Per-strategy metrics enable live recalibration
- **Production Ready**: All edge cases and performance concerns addressed

---

---

## 🔄 Version 1.9 Critical Fixes (2025-12-04)

### Critical Issues Found in Review

**Review Type:** Logic & Implementation Errors  
**Status:** ⚠️ **5 CRITICAL ISSUES IDENTIFIED AND FIXED**

See `ADAPTIVE_MICRO_SCALP_CRITICAL_ISSUES_V8.md` for detailed analysis.

### **Issue #1: Helper Method Access Violation** ✅ FIXED

**Problem:** Strategy checkers call helper methods (`_calculate_vwap_std()`, `_check_bb_compression()`, etc.) that only exist in `MicroScalpRegimeDetector`, not in their inheritance chain.

**Fix:** Add all helper methods to `BaseStrategyChecker` class so strategy checkers can access them.

**Required Changes:**
- Add helper methods to `BaseStrategyChecker.__init__()` or as instance methods
- Methods to add:
  - `_calculate_vwap_std(candles, vwap) -> float`
  - `_calculate_vwap_slope(candles, vwap) -> float`
  - `_check_volume_spike(candles) -> bool`
  - `_check_bb_compression(candles) -> bool`
  - `_check_compression_block(candles, atr1) -> bool`
  - `_count_range_respects(candles, range_high, range_low) -> int`

### **Issue #2: Range Structure Data Flow Missing** ✅ FIXED

**Problem:** `RangeScalpChecker._check_location_filter()` tries to detect range itself, but range should come from regime detection.

**Fix:**
1. Store `range_structure` in snapshot during `check_micro_conditions()`
2. Store snapshot in `self._current_snapshot` during `validate()` call
3. Update `RangeScalpChecker._check_location_filter()` to use `self._current_snapshot['range_structure']`

**Required Changes:**
```python
# In BaseStrategyChecker.validate()
def validate(self, snapshot: Dict[str, Any]) -> ConditionCheckResult:
    # Store snapshot for helper method access
    self._current_snapshot = snapshot
    
    # ... validation logic ...
    
    # Clear after use
    self._current_snapshot = None

# In MicroScalpEngine.check_micro_conditions()
# Extract and store regime data
if regime_result.get('regime') == 'RANGE':
    characteristics = regime_result.get('characteristics', {})
    snapshot['range_structure'] = characteristics.get('range_structure')
    snapshot['range_near_edge'] = characteristics.get('near_edge')
```

### **Issue #3: Missing Snapshot Data Population** ✅ FIXED

**Problem:** Regime detection results are stored but not extracted into snapshot for easy access.

**Fix:** Extract regime-specific data from `regime_result['characteristics']` and store in snapshot.

**Required Changes:**
```python
# In MicroScalpEngine.check_micro_conditions()
regime = regime_result.get('regime', 'UNKNOWN')
characteristics = regime_result.get('characteristics', {})

if regime == 'RANGE':
    snapshot['range_structure'] = characteristics.get('range_structure')
    snapshot['range_near_edge'] = characteristics.get('near_edge')
elif regime == 'VWAP_REVERSION':
    snapshot['vwap_deviation_sigma'] = characteristics.get('deviation_sigma', 0)
elif regime == 'BALANCED_ZONE':
    snapshot['compression_detected'] = characteristics.get('compression', False)
```

### **Issue #4: Missing Helper Method in BalancedZoneChecker** ✅ FIXED

**Problem:** `BalancedZoneChecker` calls `_check_compression_block()` which doesn't exist in its inheritance chain.

**Fix:** Same as Issue #1 - Add helper methods to `BaseStrategyChecker`.

### **Issue #5: Missing M5 Candles Access in BalancedZoneChecker** ✅ FIXED

**Problem:** `BalancedZoneChecker` needs M5 candles for MTF compression but can't access them.

**Fix:** Use `self._current_snapshot['m5_candles']` (same approach as Issue #2).

**Required Changes:**
```python
# In BalancedZoneChecker._check_location_filter()
snapshot = getattr(self, '_current_snapshot', None)
if snapshot:
    m5_candles = snapshot.get('m5_candles', [])
    compression = self._check_compression_block_mtf(candles, m5_candles, snapshot)
```

---

**End of Plan**

