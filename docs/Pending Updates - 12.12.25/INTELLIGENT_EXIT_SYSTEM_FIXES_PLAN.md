# Intelligent Exit System & DTMS Comprehensive Fix Plan

**Date:** 2025-12-12  
**Status:** Planning Phase  
**Priority:** CRITICAL

---

## 🎯 Executive Summary

This plan addresses **10 critical issues** in the Intelligent Exit Management system and DTMS that are causing:
- All trades to get tightened exits unnecessarily (RMAG always triggering)
- Trailing stops to never activate (gates blocking all trailing)
- Trades closing prematurely after breakeven (no trailing protection)
- DTMS system not taking any defensive actions (engine not initialized)
- DTMS webpage endpoints returning 404 (cannot view trade details)
- Potential race conditions in rules dictionary (thread safety)

---

## 📊 Issues Identified

### **CRITICAL Issues (Blocking Core Functionality)**

| # | Issue | Severity | Impact |
|---|-------|----------|--------|
| 1 | RMAG threshold too sensitive for BTCUSD | **CRITICAL** | All trades get 20%/40% instead of 30%/60% |
| 2 | Trailing gates blocking all activation | **CRITICAL** | Trailing stops never work, trades close at breakeven |
| 3 | DTMS engine not initialized | **CRITICAL** | No defensive trade management |
| 4 | Advanced triggers calculated once, never refreshed | **HIGH** | Exit parameters don't adapt to changing market conditions |

### **HIGH Priority Issues**

| # | Issue | Severity | Impact |
|---|-------|----------|--------|
| 6 | Breakeven buffer too tight (spread-only) | **HIGH** | Trades close on minor retracements |
| 7 | Advanced provider not set | **HIGH** | Trailing gates never refresh, use stale data |
| 8 | Thread safety for rules dictionary | **HIGH** | Potential race conditions and data corruption |
| 9 | No logging of trailing gate failures | **MEDIUM** | Can't diagnose why trailing doesn't activate |
| 10 | Trade Type Classifier not integrated | **MEDIUM** | SCALP/INTRADAY classification not used |

---

## 🔧 Implementation Plan

### **Phase 1: RMAG Threshold Fix (Asset-Specific)** ✅ **COMPLETED**

**Problem:** RMAG threshold of 2.0σ is too sensitive for BTCUSD (shows -6.0σ regularly)

**Solution:** Implement asset-specific RMAG thresholds

**Files to Modify:**
- `infra/intelligent_exit_manager.py` (lines 319-380, 1212-1242)
- `config/settings.py` (add RMAG threshold config)

**Logic Issues Found:**
- ❌ `_calculate_advanced_triggers()` doesn't take `symbol` parameter
- ❌ Symbol normalization needed (BTCUSD vs BTCUSDc)
- ❌ Threshold lookup needs to handle both normalized and raw symbols

**Changes:**
1. Add asset-specific RMAG thresholds to `config/settings.py`:
   ```python
   # RMAG Stretch Thresholds (asset-specific)
   # Thresholds determine when price is "stretched" enough to tighten exits
   RMAG_STRETCH_THRESHOLDS = {
       "BTCUSDc": 4.0,   # BTCUSD can stretch to 4σ normally (high volatility)
       "BTCUSD": 4.0,    # Handle both with/without 'c' suffix
       "XAUUSDc": 2.0,   # Gold more sensitive to stretch
       "XAUUSD": 2.0,
       "DEFAULT": 2.0    # Default for other assets
   }
   ```

2. Add helper method to get RMAG threshold (reuse existing symbol normalization pattern):
   ```python
   def _get_rmag_threshold(self, symbol: str) -> float:
       """Get asset-specific RMAG threshold, handling symbol normalization
       
       Uses same normalization pattern as desktop_agent.py (lines 2129-2131)
       """
       from config.settings import RMAG_STRETCH_THRESHOLDS
       
       # Normalize symbol (same pattern as desktop_agent.py)
       symbol_normalized = symbol.upper()
       if symbol_normalized not in ['DXY', 'VIX', 'US10Y', 'SPX']:
           if not symbol_normalized.endswith('C'):
               symbol_normalized = symbol_normalized + 'C'
           else:
               symbol_normalized = symbol_normalized.rstrip('cC') + 'C'
       
       # Try exact match first
       if symbol_normalized in RMAG_STRETCH_THRESHOLDS:
           return RMAG_STRETCH_THRESHOLDS[symbol_normalized]
       
       # Try without 'c' suffix
       symbol_base = symbol_normalized.rstrip('cC')
       if symbol_base in RMAG_STRETCH_THRESHOLDS:
           return RMAG_STRETCH_THRESHOLDS[symbol_base]
       
       # Default
       return RMAG_STRETCH_THRESHOLDS.get("DEFAULT", 2.0)
   ```
   
   **Why reuse existing pattern:**
   - ✅ Consistent with codebase (desktop_agent.py normalization)
   - ✅ Handles edge cases (DXY, VIX, etc.)
   - ✅ Tested and proven

3. Modify `_calculate_advanced_triggers()` signature to include symbol:
   ```python
   def _calculate_advanced_triggers(
       self, 
       advanced_features: Optional[Dict[str, Any]],
       base_breakeven_pct: float = 30.0,
       base_partial_pct: float = 60.0,
       symbol: Optional[str] = None  # NEW: Add symbol parameter
   ) -> Dict[str, Any]:
   ```

4. Use asset-specific threshold in calculation:
   ```python
   # Get asset-specific threshold
   rmag_threshold = self._get_rmag_threshold(symbol or "UNKNOWN")
   
   if abs(ema200_atr) > rmag_threshold or abs(vwap_atr) > (rmag_threshold * 0.9):
       # Only tighten if EXTREME stretch
       breakeven_pct = 20.0
       partial_pct = 40.0
       stretch_direction = "above" if ema200_atr > 0 else "below"
       adjustments.append(f"RMAG stretched ({ema200_atr:.1f}σ {stretch_direction} EMA200, threshold={rmag_threshold}σ) → TIGHTEN to 20%/40%")
       advanced_factors.append("rmag_stretched")
   ```

5. Update all call sites to pass symbol:
   ```python
   # In add_rule_advanced()
   advanced_result = self._calculate_advanced_triggers(
       advanced_features=advanced_features,
       base_breakeven_pct=base_breakeven_pct,
       base_partial_pct=base_partial_pct,
       symbol=symbol  # NEW
   )
   ```

6. Update trailing gate RMAG check to use same threshold:
   ```python
   # In _trailing_gates_pass()
   rmag_threshold = self._get_rmag_threshold(rule.symbol)
   rmag_ok = abs(float(g.get("ema200_atr", 0))) <= rmag_threshold
   ```

**Integration Issues:**
- ✅ Symbol passed from `add_rule_advanced()` - already available
- ✅ Need to import `RMAG_STRETCH_THRESHOLDS` from `config.settings`

**Testing:**
- Verify BTCUSD trades use 4.0σ threshold
- Verify XAUUSD trades use 2.0σ threshold
- Verify other assets use 2.0σ default
- Verify symbol normalization works (BTCUSD vs BTCUSDc)

**Estimated Time:** 2 hours

---

### **Phase 2: Trailing Gates Fix (Make Gates Advisory)** ✅ **COMPLETED**

**Problem:** Trailing gates are too strict - RMAG gate always fails, blocking all trailing

**Solution:** Make gates advisory with fallback behavior

**Files to Modify:**
- `infra/intelligent_exit_manager.py` (lines 1153, 1178, 1183, 1212-1242, 1821-1950)

**Logic Issues Found:**
- ❌ Return type change from `bool` to `Tuple[bool, Dict]` will break existing call sites (lines 1153, 1178)
- ❌ `_trail_stop_atr()` doesn't accept multiplier parameter
- ❌ Need to update all call sites to handle new return type
- ❌ Symbol needed for RMAG threshold lookup

**Changes:**
1. Implement tiered gate system with backward-compatible return:
   ```python
   def _trailing_gates_pass(
       self, 
       rule: ExitRule, 
       profit_pct: float, 
       r_achieved: float,
       return_details: bool = False  # NEW: Optional detailed return
   ) -> Union[bool, Tuple[bool, Dict[str, Any]]]:
       """Returns bool (backward compat) or (bool, dict) if return_details=True"""
       
       g = getattr(rule, "advanced_gate", {}) or {}
       
       # Get asset-specific RMAG threshold
       rmag_threshold = self._get_rmag_threshold(rule.symbol)
       
       # CRITICAL gates (must pass)
       partial_or_r = bool(rule.partial_triggered) or (r_achieved >= 0.6)
       
       # ADVISORY gates (warn but allow trailing with wider distance)
       vol_ok = str(g.get("vol_state", "")).find("squeeze") == -1
       mtf_ok = int(g.get("mtf_total", 0)) >= 2
       rmag_ok = abs(float(g.get("ema200_atr", 0))) <= rmag_threshold
       vwap_ok = str(g.get("vwap_zone", "inside")) != "outer"
       hvn_ok = float(g.get("hvn_dist_atr", 999)) >= 0.3
       
       # Count advisory gate failures
       advisory_failures = sum([not vol_ok, not mtf_ok, not rmag_ok, not vwap_ok, not hvn_ok])
       
       # Gate status for logging
       gate_status = {
           "partial_or_r": partial_or_r,
           "vol_ok": vol_ok,
           "mtf_ok": mtf_ok,
           "mtf_total": g.get("mtf_total", 0),
           "rmag_ok": rmag_ok,
           "rmag_value": g.get("ema200_atr", 0),
           "rmag_threshold": rmag_threshold,
           "vwap_ok": vwap_ok,
           "vwap_zone": g.get("vwap_zone", "unknown"),
           "hvn_ok": hvn_ok,
           "hvn_dist": g.get("hvn_dist_atr", 999),
           "advisory_failures": advisory_failures
       }
       
       # Allow trailing if critical gate passes
       # But use wider trailing distance if advisory gates fail
       if partial_or_r:
           if advisory_failures <= 2:  # Allow up to 2 advisory failures
               multiplier = 1.5
               gate_status_str = "normal"
           else:  # 3+ failures - use wider trailing
               multiplier = 2.0
               gate_status_str = "wide"
           
           # Log gate status
           logger.info(
               f"Trailing gates for {rule.symbol} ticket {rule.ticket}: "
               f"partial_or_r={partial_or_r} vol={vol_ok} mtf={mtf_ok}({gate_status['mtf_total']}) "
               f"rmag={rmag_ok}({gate_status['rmag_value']:.2f}σ, threshold={rmag_threshold}σ) "
               f"vwap={vwap_ok}({gate_status['vwap_zone']}) hvn={hvn_ok}({gate_status['hvn_dist']:.2f}) "
               f"failures={advisory_failures} → ALLOW trailing (multiplier={multiplier}x, status={gate_status_str})"
           )
           
           if return_details:
               return (True, {"trailing_multiplier": multiplier, "gate_status": gate_status, "status": gate_status_str})
           else:
               return True
       else:
           logger.info(
               f"Trailing gates for {rule.symbol} ticket {rule.ticket}: "
               f"partial_or_r={partial_or_r} → BLOCK trailing (need partial or R>=0.6)"
           )
           if return_details:
               return (False, {"reason": "partial_or_r_failed", "gate_status": gate_status})
           else:
               return False
   ```

2. Update call sites to use new return type:
   ```python
   # Line 1153: Post-partial activation
   gate_result = self._trailing_gates_pass(rule, profit_pct, r_achieved, return_details=True)
   if isinstance(gate_result, tuple) and gate_result[0]:
       rule.trailing_active = True
       rule.trailing_multiplier = gate_result[1].get("trailing_multiplier", 1.5)  # Store multiplier
       logger.info(f"✅ Trailing stops ACTIVATED (post-partial) for ticket {rule.ticket}")
   
   # Line 1178: Gate check during trailing
   gate_result = self._trailing_gates_pass(rule, profit_pct, r_achieved, return_details=True)
   if isinstance(gate_result, tuple):
       should_trail, gate_info = gate_result
       if not should_trail:
           logger.info(f"⏳ Trailing gated for ticket {rule.ticket} — holding off trailing updates")
           rule.trailing_active = False
       else:
           # Update multiplier if changed
           rule.trailing_multiplier = gate_info.get("trailing_multiplier", 1.5)
   ```

3. Update `_trail_stop_atr()` to accept multiplier parameter:
   ```python
   def _trail_stop_atr(
       self,
       rule: ExitRule,
       position,
       current_price: float,
       trailing_multiplier: Optional[float] = None  # NEW: Optional multiplier
   ) -> Optional[Dict[str, Any]]:
       """Trailing stop with configurable multiplier"""
       
       # Use stored multiplier or default
       multiplier = trailing_multiplier or getattr(rule, "trailing_multiplier", None) or 1.5
       
       # ... existing ATR calculation ...
       
       # Use multiplier instead of hardcoded 1.5
       trailing_distance = atr * multiplier
   ```

4. Update trailing call to pass multiplier:
   ```python
   # Line 1184: Trailing activation
   if rule.trailing_active and rule.breakeven_triggered:
       multiplier = getattr(rule, "trailing_multiplier", 1.5)
       action = self._trail_stop_atr(rule, position, current_price, trailing_multiplier=multiplier)
   ```

**Integration Issues:**
- ✅ Need to add `trailing_multiplier` attribute to `ExitRule` class
- ✅ Need to handle backward compatibility for existing rules (default to 1.5)

**Testing:**
- Verify trailing activates even when RMAG > 2.0σ
- Verify wider trailing distance used when gates fail
- Verify logging shows gate status
- Verify backward compatibility (existing rules work)

**Estimated Time:** 3 hours

---

### **Phase 3: Breakeven Buffer Enhancement** ✅ **COMPLETED**

**Problem:** Breakeven set at exact entry + spread, no buffer for normal retracements

**Solution:** Add ATR-based buffer to breakeven

**Files to Modify:**
- `infra/intelligent_exit_manager.py` (lines 1244-1331)

**Logic Issues Found:**
- ❌ `calculate_atr()` function doesn't exist - need to use existing ATR calculation pattern
- ❌ Buffer calculation might move SL backwards if not careful
- ❌ Need to handle cases where ATR calculation fails

**Changes:**
1. **USE EXISTING ATR UTILITY** - Reuse `infra/streamer_data_access.calculate_atr()`:
   ```python
   def _calculate_atr(self, symbol: str, timeframe: str = "M15", period: int = 14) -> Optional[float]:
       """Calculate ATR using existing streamer utility (preferred) with MT5 fallback"""
       try:
           # Try streamer ATR first (fast, uses cached data)
           from infra.streamer_data_access import calculate_atr as streamer_atr
           atr = streamer_atr(symbol, timeframe, period=period)
           if atr and atr > 0:
               return atr
       except Exception as e:
           logger.debug(f"Streamer ATR failed for {symbol} {timeframe}, using MT5 fallback: {e}")
       
       # Fallback to direct MT5 (same pattern as existing code)
       try:
           import MetaTrader5 as mt5
           if not mt5.initialize():
               return None
           
           # Map timeframe string to MT5 enum
           tf_map = {
               "M1": mt5.TIMEFRAME_M1,
               "M5": mt5.TIMEFRAME_M5,
               "M15": mt5.TIMEFRAME_M15,
               "M30": mt5.TIMEFRAME_M30,
               "H1": mt5.TIMEFRAME_H1,
               "H4": mt5.TIMEFRAME_H4
           }
           tf_enum = tf_map.get(timeframe, mt5.TIMEFRAME_M15)
           
           bars = mt5.copy_rates_from_pos(symbol, tf_enum, 0, 50)
           if bars is None or len(bars) < period + 1:
               return None
           
           import numpy as np
           high_low = bars['high'][1:] - bars['low'][1:]
           high_close = np.abs(bars['high'][1:] - bars['close'][:-1])
           low_close = np.abs(bars['low'][1:] - bars['close'][:-1])
           tr = np.maximum(high_low, np.maximum(high_close, low_close))
           atr = np.mean(tr[-period:]) if len(tr) >= period else 0
           
           return atr if atr > 0 else None
       except Exception as e:
           logger.debug(f"MT5 ATR calculation failed for {symbol}: {e}")
           return None
   ```
   
   **Why use streamer utility:**
   - ✅ Faster (uses cached streamer data)
   - ✅ Consistent with rest of codebase
   - ✅ Automatic fallback to MT5 if streamer unavailable
   - ✅ Already tested and proven

2. Modify `_move_to_breakeven()` to add ATR buffer (using existing utility):
   ```python
   def _move_to_breakeven(self, rule: ExitRule, position, current_price: float) -> Optional[Dict[str, Any]]:
       """Move stop loss to breakeven (entry price) with ATR buffer"""
       try:
           # Calculate breakeven SL (entry + small buffer for spread)
           symbol_info = mt5.symbol_info(rule.symbol)
           if not symbol_info:
               logger.error(f"Could not get symbol info for {rule.symbol}")
               return None
           
           spread = symbol_info.spread * symbol_info.point
           
           # Calculate ATR buffer (0.3× ATR allows normal retracements)
           # USE EXISTING UTILITY - streamer_data_access.calculate_atr()
           atr = self._calculate_atr(rule.symbol, "M15", 14)  # Use string timeframe
           if atr and atr > 0:
               atr_buffer = atr * 0.3
           else:
               # Fallback: use 0.1% of entry price as buffer if ATR unavailable
               atr_buffer = rule.entry_price * 0.001
               logger.debug(f"ATR unavailable for {rule.symbol}, using 0.1% price buffer")
           
           # Calculate breakeven with buffer
           if rule.direction == "buy":
               new_sl = rule.entry_price + spread - atr_buffer  # Below entry for buffer
           else:
               new_sl = rule.entry_price - spread + atr_buffer  # Above entry for buffer
           
           # Don't move SL backwards
           current_sl = position.sl if position.sl else rule.initial_sl
           if rule.direction == "buy":
               new_sl = max(new_sl, current_sl)  # Can't go below current SL
           else:
               new_sl = min(new_sl, current_sl)  # Can't go above current SL
           
           # Verify buffer didn't make SL worse than entry
           if rule.direction == "buy" and new_sl >= rule.entry_price:
               # Buffer too large, use entry + spread only
               new_sl = rule.entry_price + spread
           elif rule.direction == "sell" and new_sl <= rule.entry_price:
               # Buffer too large, use entry - spread only
               new_sl = rule.entry_price - spread
           
           # ... rest of existing code ...
   ```

**Integration Issues:**
- ✅ ATR calculation pattern already exists in `_trail_stop_atr()` - reuse it
- ✅ Need to handle MT5 initialization (already handled in existing code)

**Testing:**
- Verify breakeven has buffer for normal retracements
- Verify trades don't close on minor pullbacks
- Verify buffer scales with volatility
- Verify fallback works when ATR unavailable
- Verify SL never moves backwards

**Estimated Time:** 2 hours

---

### **Phase 4: Advanced Provider Integration** ✅ **COMPLETED**

**Problem:** Advanced provider not set, so trailing gates use stale data from entry

**Solution:** Set advanced provider in Intelligent Exit Manager initialization

**Files to Modify:**
- `chatgpt_bot.py` (lines 1950-1960)
- `infra/intelligent_exit_manager.py` (factory function, `_update_advanced_gate()`)

**Logic Issues Found:**
- ❌ `IndicatorBridge.get_multi()` returns raw OHLCV data, NOT Advanced features
- ❌ `_update_advanced_gate()` expects Advanced features structure, not raw data
- ❌ Need to use `build_features_advanced()` to get actual Advanced features
- ✅ `IndicatorBridge` is already passed as `advanced_provider` in `chatgpt_bot.py` line 1958

**Changes:**
1. Create Advanced provider wrapper that converts `get_multi()` to Advanced features:
   ```python
   # In infra/intelligent_exit_manager.py or new file infra/advanced_provider_wrapper.py
   class AdvancedProviderWrapper:
       """Wrapper to convert IndicatorBridge.get_multi() to Advanced features format"""
       
       def __init__(self, indicator_bridge, mt5_service=None):
           self.indicator_bridge = indicator_bridge
           self.mt5_service = mt5_service
           self._cache = {}  # Cache Advanced features (refresh every 60 seconds)
           self._cache_timestamps = {}
       
       def get_advanced_features(self, symbol: str) -> Dict[str, Any]:
           """Get Advanced features for symbol, using cache to avoid excessive calls"""
           import time
           
           # Check cache (refresh every 60 seconds)
           cache_key = symbol
           if cache_key in self._cache:
               cache_age = time.time() - self._cache_timestamps.get(cache_key, 0)
               if cache_age < 60:  # Cache valid for 60 seconds
                   return self._cache[cache_key]
           
           try:
               # Use build_features_advanced to get actual Advanced features
               from infra.feature_builder_advanced import build_features_advanced
               
               if not self.mt5_service:
                   # Try to get MT5 service from indicator_bridge if available
                   if hasattr(self.indicator_bridge, 'mt5_service'):
                       mt5_svc = self.indicator_bridge.mt5_service
                   else:
                       logger.warning(f"MT5 service unavailable for Advanced features: {symbol}")
                       return {}
               else:
                   mt5_svc = self.mt5_service
               
               # Build Advanced features
               features = build_features_advanced(
                   symbol=symbol,
                   mt5svc=mt5_svc,
                   bridge=self.indicator_bridge,
                   timeframes=["M5", "M15", "H1"]
               )
               
               if features and "features" in features:
                   # Cache result
                   self._cache[cache_key] = features
                   self._cache_timestamps[cache_key] = time.time()
                   return features
               
               return {}
           except Exception as e:
               logger.warning(f"Failed to get Advanced features for {symbol}: {e}")
               return {}
       
       def get_multi(self, symbol: str) -> Dict[str, Any]:
           """Fallback: return get_multi() result (for compatibility)"""
           if hasattr(self.indicator_bridge, 'get_multi'):
               return self.indicator_bridge.get_multi(symbol)
           return {}
   ```

2. Update `chatgpt_bot.py` to wrap IndicatorBridge:
   ```python
   # In chatgpt_bot.py, after indicator_bridge is created
   from infra.intelligent_exit_manager import AdvancedProviderWrapper
   
   # Wrap indicator_bridge to provide Advanced features
   advanced_provider = AdvancedProviderWrapper(
       indicator_bridge=indicator_bridge,
       mt5_service=mt5_service
   )
   
   intelligent_exit_manager = create_exit_manager(
       mt5_service,
       binance_service=binance_service,
       order_flow_service=order_flow_service,
       advanced_provider=advanced_provider,  # Use wrapper instead of raw indicator_bridge
   )
   ```

3. Verify `_update_advanced_gate()` handles both formats:
   ```python
   # Already handles get_advanced_features() and get_multi()
   # But ensure it works with new wrapper
   ```

**Integration Issues:**
- ✅ `IndicatorBridge` already passed as provider, but doesn't return Advanced features
- ✅ Need to wrap it to convert to Advanced features format
- ✅ Cache needed to avoid excessive `build_features_advanced()` calls

**Testing:**
- Verify Advanced gates refresh each cycle
- Verify trailing gates use current market data
- Verify RMAG values update during trade
- Verify cache works (doesn't call build_features_advanced() every cycle)
- Verify fallback works if Advanced features unavailable

**Estimated Time:** 2 hours

---

### **Phase 5: Enhanced Logging for Trailing Gates** ✅ **COMPLETED**

**Problem:** No visibility into why trailing gates fail
**Note:** Already implemented in Phase 2 - comprehensive logging added to `_trailing_gates_pass()`

**Solution:** Add comprehensive logging

**Files to Modify:**
- `infra/intelligent_exit_manager.py` (lines 1212-1242)

**Changes:**
1. Add detailed logging:
   ```python
   def _trailing_gates_pass(self, rule: ExitRule, profit_pct: float, r_achieved: float) -> Tuple[bool, Dict[str, Any]]:
       g = getattr(rule, "advanced_gate", {}) or {}
       
       # ... gate checks ...
       
       # Log gate status
       gate_status = {
           "partial_or_r": partial_or_r,
           "vol_ok": vol_ok,
           "mtf_ok": mtf_ok,
           "mtf_total": g.get("mtf_total", 0),
           "rmag_ok": rmag_ok,
           "rmag_value": g.get("ema200_atr", 0),
           "vwap_ok": vwap_ok,
           "vwap_zone": g.get("vwap_zone", "unknown"),
           "hvn_ok": hvn_ok,
           "hvn_dist": g.get("hvn_dist_atr", 999)
       }
       
       logger.info(
           f"Trailing gates for {rule.symbol} ticket {rule.ticket}: "
           f"partial_or_r={partial_or_r} vol={vol_ok} mtf={mtf_ok}({gate_status['mtf_total']}) "
           f"rmag={rmag_ok}({gate_status['rmag_value']:.2f}σ) vwap={vwap_ok} hvn={hvn_ok} "
           f"→ decision={decision} multiplier={multiplier}"
       )
       
       return (decision, {"trailing_multiplier": multiplier, "gate_status": gate_status})
   ```

**Testing:**
- Verify logs show all gate values
- Verify logs show why trailing is blocked/allowed
- Verify logs help diagnose issues

**Estimated Time:** 1 hour

---

### **Phase 6: DTMS Engine Initialization Fix** ✅ **COMPLETED**

**Problem:** DTMS engine never initialized, alerts sent but no actions taken

**Solution:** Initialize DTMS engine and ensure monitoring runs

**Files to Modify:**
- `chatgpt_bot.py` (lines 1920-1948) - Verify DTMS initialization
- `app/main_api.py` (startup_event) - Add DTMS if not in chatgpt_bot
- `dtms_integration.py` - Verify `run_dtms_monitoring_cycle()` is async
- `app/main_api.py` (lines 1955-2139) - Fix DTMS trade detail endpoint

**Logic Issues Found:**
- ✅ DTMS already initialized in `chatgpt_bot.py` line 1927
- ❌ Need to verify monitoring cycle is running
- ❌ `run_dtms_monitoring_cycle()` is async - need async background task
- ❌ Need to verify `auto_register_dtms()` is called after trades
- ❌ **CRITICAL**: DTMS trade detail webpage returns 404 - wrong port/endpoint

**Changes:**
1. Verify DTMS initialization in `chatgpt_bot.py` (already exists, but verify it works):
   ```python
   # Lines 1920-1948 already initialize DTMS
   # Verify it's working by checking logs
   # If not working, add error handling
   ```

2. Add/verify background monitoring task in `chatgpt_bot.py`:
   ```python
   # In main() function, after DTMS initialization
   if dtms_engine:
       # Add background task for DTMS monitoring
       async def dtms_monitoring_background_task():
           """Run DTMS monitoring cycle every 30 seconds"""
           from dtms_integration import run_dtms_monitoring_cycle
           
           while True:
               try:
                   await run_dtms_monitoring_cycle()
               except Exception as e:
                   logger.error(f"DTMS monitoring cycle error: {e}", exc_info=True)
               await asyncio.sleep(30)
       
       # Start background task
       asyncio.create_task(dtms_monitoring_background_task())
       logger.info("✅ DTMS monitoring background task started")
   ```

3. Verify `auto_register_dtms()` is called (check existing call sites):
   - ✅ `desktop_agent.py` line 3895 - called after trade execution
   - ✅ `handlers/trading.py` line 4447 - called after trade execution
   - ✅ `app/main_api.py` line 1822 - called after trade execution
   - ✅ `auto_execution_system.py` line 4440 - called but disabled (line 4436)

4. Fix `auto_execution_system.py` DTMS registration (currently disabled):
   ```python
   # Line 4436: Currently `if False:` - change to check if Universal Manager registered
   if not universal_manager_registered:  # Only register if not managed by Universal Manager
       try:
           from dtms_integration import auto_register_dtms
           result_dict = {
               'symbol': symbol_norm,
               'direction': direction,
               'entry_price': executed_price,
               'volume': lot_size,
               'stop_loss': plan.stop_loss,
               'take_profit': plan.take_profit
           }
           auto_register_dtms(ticket, result_dict)
       except Exception as e:
           logger.warning(f"DTMS registration failed: {e}")
   ```

5. Add diagnostic logging to verify DTMS is working:
   ```python
   # In dtms_integration.py, add logging to auto_register_dtms()
   def auto_register_dtms(ticket: int, result_or_details: Dict[str, Any]) -> bool:
       """Auto-register trade to DTMS with error handling"""
       try:
           if not _dtms_engine:
               logger.warning(f"DTMS engine not initialized - cannot register ticket {ticket}")
               return False
           
           # ... existing registration code ...
           
           logger.info(f"✅ Trade {ticket} registered to DTMS successfully")
           return True
       except Exception as e:
           logger.error(f"❌ DTMS registration failed for ticket {ticket}: {e}", exc_info=True)
           return False
   ```

6. **CRITICAL FIX: DTMS Trade Detail Webpage Endpoint**
   **Problem:** `/dtms/trade/{ticket}` webpage returns 404 - HTML page tries to fetch from wrong port
   
   **Root Cause:**
   - HTML page (line 1996) fetches from `http://localhost:8002/dtms/trade/${ticket}`
   - DTMS API server runs on port 8001 (not 8002)
   - No JSON endpoint exists in `app/main_api.py` for `/dtms/trade/{ticket}`
   
   **Solution:** Add JSON endpoint in `app/main_api.py`:
   ```python
   @app.get("/dtms/trade/{ticket}", response_class=HTMLResponse)
   async def view_dtms_trade_details(ticket: int):
       """DTMS trade details page for a specific ticket."""
       # ... existing HTML code ...
   
   # ADD THIS NEW ENDPOINT for JSON API
   @app.get("/api/dtms/trade/{ticket}")
   async def get_dtms_trade_info_api(ticket: int):
       """Get DTMS trade information as JSON (for webpage fetch)"""
       try:
           from dtms_integration import get_dtms_trade_status
           from infra.mt5_service import MT5Service
           import MetaTrader5 as mt5
           
           # Get DTMS trade status
           trade_info = get_dtms_trade_status(ticket)
           
           if trade_info and not trade_info.get('error'):
               # Enrich with MT5 position details
               mt5_details = {}
               try:
                   mt5_service = MT5Service()
                   if mt5_service.connect():
                       positions = mt5.positions_get(ticket=ticket)
                       if positions:
                           pos = positions[0]
                           mt5_details = {
                               "symbol": pos.symbol,
                               "type": "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                               "volume": pos.volume,
                               "open_price": pos.price_open,
                               "current_price": pos.price_current,
                               "profit": pos.profit,
                               "sl": pos.sl,
                               "tp": pos.tp
                           }
               except Exception:
                   pass
               
               # Get intelligent exits status
               intelligent_exits = {}
               try:
                   from chatgpt_bot import intelligent_exit_manager
                   if intelligent_exit_manager:
                       rule = intelligent_exit_manager.rules.get(ticket)
                       if rule:
                           intelligent_exits = {
                               "breakeven_triggered": rule.breakeven_triggered,
                               "partial_profit_triggered": rule.partial_triggered,
                               "trailing_stop_active": rule.trailing_active
                           }
               except Exception:
                   pass
               
               return {
                   "success": True,
                   "summary": f"Trade {ticket} is in {trade_info.get('state', 'Unknown')} state",
                   "trade_info": {
                       "ticket": ticket,
                       "symbol": mt5_details.get('symbol') or trade_info.get('symbol'),
                       "type": mt5_details.get('type'),
                       "volume": mt5_details.get('volume'),
                       "open_price": mt5_details.get('open_price'),
                       "current_price": mt5_details.get('current_price'),
                       "profit": mt5_details.get('profit'),
                       "sl": mt5_details.get('sl'),
                       "tp": mt5_details.get('tp'),
                       "state": trade_info.get('state'),
                       "current_score": trade_info.get('current_score'),
                       "state_entry_time": trade_info.get('state_entry_time_human'),
                       "warnings": trade_info.get('warnings', {}),
                       "actions_taken": trade_info.get('actions_taken', []),
                       "performance": trade_info.get('performance', {}),
                       "protection_active": bool(trade_info.get('state') != 'CLOSED'),
                       "intelligent_exits": intelligent_exits
                   }
               }
           else:
               error_msg = trade_info.get('error', 'Trade not found in DTMS') if trade_info else 'Trade not found in DTMS'
               return {
                   "success": False,
                   "summary": f"Could not get DTMS info for trade {ticket}: {error_msg}",
                   "error": error_msg,
                   "trade_info": None
               }
       except Exception as e:
           return {
               "success": False,
               "summary": f"Failed to get DTMS trade info: {str(e)}",
               "error": str(e)
           }
   ```
   
   **Fix HTML page port reference:**
   ```javascript
   // Line 1996: Change from port 8002 to relative URL or correct port
   // OLD:
   const res = await fetch(`http://localhost:8002/dtms/trade/${ticket}`);
   
   // NEW (use relative URL - same server):
   const res = await fetch(`/api/dtms/trade/${ticket}`);
   
   // OR if DTMS API server is separate:
   const res = await fetch(`http://localhost:8001/dtms/trade/${ticket}`);
   ```
   
   **Why this fix:**
   - ✅ Webpage can fetch trade data from same server (no CORS issues)
   - ✅ Works even if DTMS API server is separate
   - ✅ Provides intelligent exits status integration
   - ✅ Enriches with MT5 position data

**Integration Issues:**
- ✅ DTMS already initialized in `chatgpt_bot.py`
- ❌ Need to verify monitoring cycle runs
- ❌ Need to ensure trades register (some paths may skip registration)

**Testing:**
- Verify DTMS engine initializes on startup
- Verify trades register to DTMS (check logs)
- Verify monitoring cycle runs every 30 seconds
- Verify DTMS takes defensive actions when needed
- Verify registration works from all trade execution paths

**Estimated Time:** 4 hours

---

### **Phase 7: DTMS Webpage Endpoint Fix** ✅ **COMPLETED**

**Problem:** `/dtms/trade/{ticket}` webpage returns 404 - HTML page tries to fetch from wrong port

**Solution:** Add JSON endpoint in main_api.py and fix port references

**Files to Modify:**
- `app/main_api.py` (lines 1955-2139, 7366, 7418, 7589)

**Logic Issues Found:**
- ❌ HTML page (line 1996) fetches from `http://localhost:8002/dtms/trade/${ticket}` (wrong port)
- ❌ DTMS API server runs on port 8001 (not 8002)
- ❌ No JSON endpoint exists in `app/main_api.py` for `/dtms/trade/{ticket}`
- ❌ Multiple port references use 8002 (should be 8001 or relative URL)

**Changes:**
1. Add JSON endpoint in `app/main_api.py`:
   ```python
   @app.get("/api/dtms/trade/{ticket}")
   async def get_dtms_trade_info_api(ticket: int):
       """Get DTMS trade information as JSON (for webpage fetch)"""
       try:
           from dtms_integration import get_dtms_trade_status
           from infra.mt5_service import MT5Service
           import MetaTrader5 as mt5
           
           # Get DTMS trade status
           trade_info = get_dtms_trade_status(ticket)
           
           if trade_info and not trade_info.get('error'):
               # Enrich with MT5 position details
               mt5_details = {}
               try:
                   mt5_service = MT5Service()
                   if mt5_service.connect():
                       positions = mt5.positions_get(ticket=ticket)
                       if positions:
                           pos = positions[0]
                           mt5_details = {
                               "symbol": pos.symbol,
                               "type": "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                               "volume": pos.volume,
                               "open_price": pos.price_open,
                               "current_price": pos.price_current,
                               "profit": pos.profit,
                               "sl": pos.sl,
                               "tp": pos.tp
                           }
               except Exception:
                   pass
               
               # Get intelligent exits status
               intelligent_exits = {}
               try:
                   from chatgpt_bot import intelligent_exit_manager
                   if intelligent_exit_manager:
                       rule = intelligent_exit_manager.rules.get(ticket)
                       if rule:
                           intelligent_exits = {
                               "breakeven_triggered": rule.breakeven_triggered,
                               "partial_profit_triggered": rule.partial_triggered,
                               "trailing_stop_active": rule.trailing_active
                           }
               except Exception:
                   pass
               
               return {
                   "success": True,
                   "summary": f"Trade {ticket} is in {trade_info.get('state', 'Unknown')} state",
                   "trade_info": {
                       "ticket": ticket,
                       "symbol": mt5_details.get('symbol') or trade_info.get('symbol'),
                       "type": mt5_details.get('type'),
                       "volume": mt5_details.get('volume'),
                       "open_price": mt5_details.get('open_price'),
                       "current_price": mt5_details.get('current_price'),
                       "profit": mt5_details.get('profit'),
                       "sl": mt5_details.get('sl'),
                       "tp": mt5_details.get('tp'),
                       "state": trade_info.get('state'),
                       "current_score": trade_info.get('current_score'),
                       "state_entry_time": trade_info.get('state_entry_time_human'),
                       "warnings": trade_info.get('warnings', {}),
                       "actions_taken": trade_info.get('actions_taken', []),
                       "performance": trade_info.get('performance', {}),
                       "protection_active": bool(trade_info.get('state') != 'CLOSED'),
                       "intelligent_exits": intelligent_exits
                   }
               }
           else:
               error_msg = trade_info.get('error', 'Trade not found in DTMS') if trade_info else 'Trade not found in DTMS'
               return {
                   "success": False,
                   "summary": f"Could not get DTMS info for trade {ticket}: {error_msg}",
                   "error": error_msg,
                   "trade_info": None
               }
       except Exception as e:
           return {
               "success": False,
               "summary": f"Failed to get DTMS trade info: {str(e)}",
               "error": str(e)
           }
   ```

2. Fix HTML page port references (use relative URL):
   ```javascript
   // Line 1996: Change from port 8002 to relative URL
   // OLD:
   const res = await fetch(`http://localhost:8002/dtms/trade/${ticket}`);
   
   // NEW (use relative URL - same server):
   const res = await fetch(`/api/dtms/trade/${ticket}`);
   ```

3. Fix other port references in DTMS status page:
   ```javascript
   // Line 7366: DTMS status
   // OLD: const res = await fetch('http://localhost:8002/dtms/status');
   // NEW: Use relative URL or correct port
   const res = await fetch('/api/dtms/status');  // If endpoint exists
   // OR: const res = await fetch('http://localhost:8001/dtms/status');  // If DTMS API server separate
   
   // Line 7418: DTMS engine
   // Similar fix needed
   
   // Line 7589: DTMS actions
   // Similar fix needed
   ```

**Integration Issues:**
- ✅ Need to check if `/api/dtms/status` endpoint exists in main_api.py
- ✅ If DTMS API server is separate, need to proxy or use correct port
- ✅ Intelligent exits integration adds value to webpage

**Testing:**
- Verify `/api/dtms/trade/{ticket}` endpoint returns JSON
- Verify webpage loads trade details correctly
- Verify intelligent exits status displays
- Verify all port references are correct

**Estimated Time:** 1 hour

---

### **Phase 8: Trade Type Classifier Integration Verification** ✅ **COMPLETED**

**Problem:** Trade Type Classifier exists but may not be properly integrated

**Solution:** Verify and fix integration

**Files to Check:**
- `desktop_agent.py` (lines 4027-4063)
- `chatgpt_bot.py` (auto_enable_intelligent_exits_async)

**Changes:**
1. Verify Trade Type Classifier is called:
   ```python
   # In auto_enable_intelligent_exits_async or execute_trade
   from infra.trade_type_classifier import TradeTypeClassifier
   
   classifier = TradeTypeClassifier(mt5_service, session_service)
   classification = classifier.classify(...)
   
   # Use classification to set base_breakeven_pct and base_partial_pct
   if classification["trade_type"] == "SCALP":
       base_breakeven_pct = 25.0
       base_partial_pct = 40.0
   else:
       base_breakeven_pct = 30.0
       base_partial_pct = 60.0
   ```

2. Verify classification is logged and used

**Testing:**
- Verify SCALP trades get 25%/40% base triggers
- Verify INTRADAY trades get 30%/60% base triggers
- Verify Advanced adjustments still apply on top

**Estimated Time:** 1 hour

---

### **Phase 9: Thread Safety for Rules Dictionary** ✅ **COMPLETED**

**Problem:** `self.rules` dictionary accessed without locks - potential race conditions

**Solution:** Add threading lock to protect `self.rules` dictionary

**Files to Modify:**
- `infra/intelligent_exit_manager.py` (lines 177, 2127-2162, all methods that access `self.rules`)

**Logic Issues Found:**
- ❌ `self.rules` dictionary accessed from multiple threads (monitoring loop, API calls, rule updates)
- ❌ `_save_rules()` uses atomic write but doesn't protect dictionary access
- ❌ Race condition: Dictionary modified during iteration could cause errors
- ✅ `_save_rules()` already uses atomic write (good), but needs lock for dictionary access

**Changes:**
1. Add threading lock in `__init__`:
   ```python
   import threading
   
   def __init__(self, ...):
       # ... existing code ...
       self.rules: Dict[int, ExitRule] = {}  # ticket -> ExitRule
       self.rules_lock = threading.Lock()  # NEW: Protect rules dictionary
   ```

2. Protect all dictionary access:
   ```python
   def add_rule_advanced(self, ...):
       with self.rules_lock:
           rule = ExitRule(...)
           self.rules[ticket] = rule
       self._save_rules()  # Save after releasing lock
   
   def remove_rule(self, ticket: int) -> bool:
       with self.rules_lock:
           if ticket in self.rules:
               del self.rules[ticket]
               self._save_rules()
               return True
       return False
   
   def check_exits(self, ...):
       # Create snapshot of tickets to avoid iteration issues
       with self.rules_lock:
           tickets = list(self.rules.keys())
       
       # Iterate over snapshot (safe even if rules modified during iteration)
       for ticket in tickets:
           with self.rules_lock:
               rule = self.rules.get(ticket)
               if not rule:
                   continue  # Rule removed, skip
           
           # Process rule (outside lock to avoid deadlock)
           # ... existing check logic ...
   ```

3. Protect `_save_rules()` dictionary access:
   ```python
   def _save_rules(self):
       """Save rules to JSON file (thread-safe with atomic write)"""
       try:
           # Create snapshot while holding lock
           with self.rules_lock:
               data = {str(ticket): rule.to_dict() for ticket, rule in self.rules.items()}
           
           # Write to file (outside lock to avoid blocking)
           # ... existing atomic write code ...
       except Exception as e:
           logger.error(f"Error saving exit rules: {e}", exc_info=True)
   ```

**Integration Issues:**
- ✅ Lock protects dictionary, atomic write protects file
- ✅ Snapshot pattern prevents iteration errors
- ✅ Lock released before file I/O to avoid blocking

**Testing:**
- Verify no race conditions when multiple threads access rules
- Verify dictionary iteration doesn't fail when rules modified
- Verify file writes are atomic and don't corrupt data
- Verify performance impact is minimal (lock held briefly)

**Estimated Time:** 1 hour

---

### **Phase 10: Advanced Triggers Refresh (Optional Enhancement)** ✅ **COMPLETED**

**Problem:** Advanced-Enhanced triggers calculated once at entry, never refresh

**Solution:** Allow mid-trade refresh of Advanced triggers (optional, Phase 2 feature)

**Files to Modify:**
- `infra/intelligent_exit_manager.py` (add refresh method)

**Changes:**
1. Add method to refresh Advanced triggers:
   ```python
   def refresh_advanced_triggers(self, ticket: int, advanced_features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
       """Refresh Advanced triggers mid-trade (optional enhancement)"""
       with self.rules_lock:  # Use lock for thread safety
           rule = self.rules.get(ticket)
           if not rule:
               return None
       
       # Only refresh if breakeven not yet triggered (conservative)
       if rule.breakeven_triggered:
           return None  # Don't change triggers after breakeven
       
       # Recalculate triggers
       advanced_result = self._calculate_advanced_triggers(
           advanced_features=advanced_features,
           base_breakeven_pct=rule.breakeven_profit_pct,  # Use current as base
           base_partial_pct=rule.partial_profit_pct,
           symbol=rule.symbol  # Pass symbol for asset-specific thresholds
       )
       
       # Update rule (only if different)
       with self.rules_lock:
           if advanced_result["breakeven_pct"] != rule.breakeven_profit_pct:
               rule.breakeven_profit_pct = advanced_result["breakeven_pct"]
               rule.partial_profit_pct = advanced_result["partial_pct"]
               self._save_rules()
               logger.info(f"Refreshed Advanced triggers for {rule.symbol} ticket {ticket}")
       
       return advanced_result
   ```

**Note:** This is optional - can be deferred to Phase 2 if needed

**Estimated Time:** 2 hours

**Problem:** `self.rules` dictionary accessed without locks - potential race conditions

**Solution:** Add threading lock to protect `self.rules` dictionary

**Files to Modify:**
- `infra/intelligent_exit_manager.py` (lines 177, 2127-2162, all methods that access `self.rules`)

**Logic Issues Found:**
- ❌ `self.rules` dictionary accessed from multiple threads (monitoring loop, API calls, rule updates)
- ❌ `_save_rules()` uses atomic write but doesn't protect dictionary access
- ❌ Race condition: Dictionary modified during iteration could cause errors
- ✅ `_save_rules()` already uses atomic write (good), but needs lock for dictionary access

**Changes:**
1. Add threading lock in `__init__`:
   ```python
   import threading
   
   def __init__(self, ...):
       # ... existing code ...
       self.rules: Dict[int, ExitRule] = {}  # ticket -> ExitRule
       self.rules_lock = threading.Lock()  # NEW: Protect rules dictionary
   ```

2. Protect all dictionary access:
   ```python
   def add_rule_advanced(self, ...):
       with self.rules_lock:
           rule = ExitRule(...)
           self.rules[ticket] = rule
       self._save_rules()  # Save after releasing lock
   
   def remove_rule(self, ticket: int) -> bool:
       with self.rules_lock:
           if ticket in self.rules:
               del self.rules[ticket]
               self._save_rules()
               return True
       return False
   
   def check_exits(self, ...):
       # Create snapshot of tickets to avoid iteration issues
       with self.rules_lock:
           tickets = list(self.rules.keys())
       
       # Iterate over snapshot (safe even if rules modified during iteration)
       for ticket in tickets:
           with self.rules_lock:
               rule = self.rules.get(ticket)
               if not rule:
                   continue  # Rule removed, skip
           
           # Process rule (outside lock to avoid deadlock)
           # ... existing check logic ...
   ```

3. Protect `_save_rules()` dictionary access:
   ```python
   def _save_rules(self):
       """Save rules to JSON file (thread-safe with atomic write)"""
       try:
           # Create snapshot while holding lock
           with self.rules_lock:
               data = {str(ticket): rule.to_dict() for ticket, rule in self.rules.items()}
           
           # Write to file (outside lock to avoid blocking)
           # ... existing atomic write code ...
       except Exception as e:
           logger.error(f"Error saving exit rules: {e}", exc_info=True)
   ```

**Integration Issues:**
- ✅ Lock protects dictionary, atomic write protects file
- ✅ Snapshot pattern prevents iteration errors
- ✅ Lock released before file I/O to avoid blocking

**Testing:**
- Verify no race conditions when multiple threads access rules
- Verify dictionary iteration doesn't fail when rules modified
- Verify file writes are atomic and don't corrupt data
- Verify performance impact is minimal (lock held briefly)

**Estimated Time:** 1 hour

---

## 📋 Implementation Order

### **Week 1: Critical Fixes**

**Day 1-2:**
- ✅ Phase 1: RMAG Threshold Fix
- ✅ Phase 2: Trailing Gates Fix

**Day 3-4:**
- ✅ Phase 3: Breakeven Buffer Enhancement
- ✅ Phase 4: Advanced Provider Integration

**Day 5:**
- ✅ Phase 6: DTMS Engine Initialization Fix

### **Week 2: Enhancements**

**Day 1-2:**
- ✅ Phase 5: Enhanced Logging
- ✅ Phase 7: DTMS Webpage Endpoint Fix
- ✅ Phase 8: Trade Type Classifier Verification

**Day 3-4:**
- ✅ Phase 9: Thread Safety for Rules Dictionary
- ✅ Phase 10: Advanced Triggers Refresh (Optional - if needed)
- ✅ Testing and validation

**Day 5:**
- ✅ Documentation updates
- ✅ Deployment

---

## 🧪 Comprehensive Testing Plan

### **Unit Tests**

**File:** `tests/test_intelligent_exit_fixes.py`

#### **Test 1: RMAG Threshold Asset-Specific Logic**
```python
def test_rmag_threshold_asset_specific():
    """Test asset-specific RMAG thresholds"""
    from infra.intelligent_exit_manager import IntelligentExitManager
    from config.settings import RMAG_STRETCH_THRESHOLDS
    
    manager = IntelligentExitManager(mock_mt5_service)
    
    # Test BTCUSD threshold
    threshold_btc = manager._get_rmag_threshold("BTCUSDc")
    assert threshold_btc == 4.0, f"Expected 4.0 for BTCUSDc, got {threshold_btc}"
    
    # Test XAUUSD threshold
    threshold_xau = manager._get_rmag_threshold("XAUUSDc")
    assert threshold_xau == 2.0, f"Expected 2.0 for XAUUSDc, got {threshold_xau}"
    
    # Test default threshold
    threshold_default = manager._get_rmag_threshold("EURUSDc")
    assert threshold_default == 2.0, f"Expected 2.0 default, got {threshold_default}"
    
    # Test symbol normalization
    threshold_btc_no_c = manager._get_rmag_threshold("BTCUSD")
    assert threshold_btc_no_c == 4.0, "Should handle symbol without 'c' suffix"
```

#### **Test 2: Trailing Gates Tiered System**
```python
def test_trailing_gates_tiered_system():
    """Test trailing gates with advisory system"""
    from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
    
    manager = IntelligentExitManager(mock_mt5_service)
    
    # Create rule with stretched RMAG
    rule = ExitRule(
        ticket=123,
        symbol="BTCUSDc",
        entry_price=92000,
        direction="buy",
        initial_sl=91000,
        initial_tp=93000
    )
    rule.partial_triggered = True  # Critical gate passes
    rule.advanced_gate = {
        "ema200_atr": -5.0,  # Stretched (above 4.0 threshold)
        "mtf_total": 1,      # Low alignment
        "vol_state": "normal",
        "vwap_zone": "inside",
        "hvn_dist_atr": 0.5
    }
    
    # Test with return_details=True
    result = manager._trailing_gates_pass(rule, 50.0, 0.7, return_details=True)
    assert isinstance(result, tuple), "Should return tuple when return_details=True"
    should_trail, gate_info = result
    
    assert should_trail == True, "Should allow trailing when critical gate passes"
    assert gate_info["trailing_multiplier"] == 2.0, "Should use wider multiplier with 3+ failures"
    assert gate_info["status"] == "wide", "Should indicate wide trailing"
    
    # Test backward compatibility (return_details=False)
    result_bool = manager._trailing_gates_pass(rule, 50.0, 0.7, return_details=False)
    assert isinstance(result_bool, bool), "Should return bool when return_details=False"
    assert result_bool == True, "Should return True for backward compatibility"
```

#### **Test 3: Breakeven Buffer Calculation**
```python
def test_breakeven_buffer_calculation():
    """Test ATR-based breakeven buffer"""
    from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
    import MetaTrader5 as mt5
    
    manager = IntelligentExitManager(mock_mt5_service)
    
    # Mock ATR calculation
    with patch.object(manager, '_calculate_atr', return_value=100.0):
        rule = ExitRule(
            ticket=123,
            symbol="XAUUSDc",
            entry_price=2400.0,
            direction="buy",
            initial_sl=2350.0,
            initial_tp=2450.0
        )
        
        mock_position = Mock()
        mock_position.sl = 2350.0
        
        # Calculate expected buffer
        atr = 100.0
        buffer = atr * 0.3  # 30 points
        spread = 0.5  # Mock spread
        
        # For BUY: entry + spread - buffer
        expected_sl = 2400.0 + spread - buffer  # 2400.5 - 30 = 2370.5
        
        action = manager._move_to_breakeven(rule, mock_position, 2405.0)
        
        assert action is not None, "Should return action dict"
        assert action["new_sl"] == expected_sl, f"Expected SL {expected_sl}, got {action['new_sl']}"
        assert action["new_sl"] > mock_position.sl, "Should not move SL backwards"
```

#### **Test 4: Advanced Provider Integration**
```python
def test_advanced_provider_integration():
    """Test Advanced provider wrapper"""
    from infra.intelligent_exit_manager import AdvancedProviderWrapper
    
    mock_bridge = Mock()
    mock_mt5 = Mock()
    
    provider = AdvancedProviderWrapper(mock_bridge, mock_mt5)
    
    # Mock build_features_advanced
    with patch('infra.intelligent_exit_manager.build_features_advanced') as mock_build:
        mock_build.return_value = {
            "features": {
                "M15": {
                    "rmag": {"ema200_atr": -3.5},
                    "vol_trend": {"state": "normal"}
                }
            }
        }
        
        result = provider.get_advanced_features("BTCUSDc")
        
        assert "features" in result, "Should return features dict"
        assert "M15" in result["features"], "Should include M15 timeframe"
        assert result["features"]["M15"]["rmag"]["ema200_atr"] == -3.5
        
        # Test caching
        result2 = provider.get_advanced_features("BTCUSDc")
        assert mock_build.call_count == 1, "Should cache result, not call again"
```

### **Integration Tests**

**File:** `tests/test_intelligent_exit_integration.py`

#### **Test 1: End-to-End Trade Flow with New Fixes**
```python
def test_e2e_trade_flow_with_fixes():
    """Test complete trade flow with all fixes applied"""
    # 1. Create trade
    # 2. Enable intelligent exits with Advanced features
    # 3. Verify RMAG threshold is asset-specific
    # 4. Verify breakeven has buffer
    # 5. Verify trailing activates with gates
    # 6. Verify trailing uses correct multiplier
    pass
```

#### **Test 2: Trailing Stop Activation with Gates**
```python
def test_trailing_activation_with_gates():
    """Test trailing stop activation through gate system"""
    # 1. Create trade, reach breakeven
    # 2. Verify trailing gates are checked
    # 3. Verify trailing activates even with RMAG > 2.0σ (for BTCUSD)
    # 4. Verify wider multiplier used when gates fail
    # 5. Verify trailing stop moves correctly
    pass
```

#### **Test 3: DTMS Initialization and Monitoring**
```python
def test_dtms_initialization_and_monitoring():
    """Test DTMS initialization and trade registration"""
    # 1. Verify DTMS initializes on startup
    # 2. Verify trade registers to DTMS
    # 3. Verify monitoring cycle runs
    # 4. Verify DTMS takes actions when needed
    pass
```

#### **Test 4: Advanced Triggers Calculation**
```python
def test_advanced_triggers_calculation():
    """Test Advanced-Enhanced trigger calculation with asset-specific thresholds"""
    # 1. Test BTCUSD with -5.0σ (should NOT trigger with 4.0σ threshold)
    # 2. Test XAUUSD with -2.5σ (should trigger with 2.0σ threshold)
    # 3. Verify triggers are calculated correctly
    # 4. Verify symbol parameter is passed correctly
    pass
```

### **End-to-End Tests**

**File:** `tests/test_intelligent_exit_e2e.py`

#### **Test 1: Complete Trade Lifecycle - BTCUSD**
```python
def test_complete_trade_lifecycle_btcusd():
    """Test complete trade lifecycle for BTCUSD with all fixes"""
    # Setup
    # 1. Execute BTCUSD trade
    # 2. Verify RMAG threshold is 4.0σ (not 2.0σ)
    # 3. Verify Advanced triggers use 4.0σ threshold
    # 4. Trade reaches breakeven (with buffer)
    # 5. Verify trailing gates pass (even with RMAG -5.0σ)
    # 6. Verify trailing activates with wider multiplier
    # 7. Verify trailing stop moves correctly
    # 8. Trade closes at TP or trailing stop
    # 9. Verify all logs show correct gate status
    pass
```

#### **Test 2: Complete Trade Lifecycle - XAUUSD**
```python
def test_complete_trade_lifecycle_xauusd():
    """Test complete trade lifecycle for XAUUSD"""
    # Similar to BTCUSD but verify 2.0σ threshold
    pass
```

#### **Test 3: Breakeven Buffer Protection**
```python
def test_breakeven_buffer_protection():
    """Test that breakeven buffer prevents premature closures"""
    # 1. Trade reaches breakeven
    # 2. Price retraces by 0.2× ATR (should NOT close)
    # 3. Price retraces by 0.4× ATR (should close)
    # 4. Verify trade stayed open during minor retracement
    pass
```

#### **Test 4: Advanced Gates Refresh**
```python
def test_advanced_gates_refresh():
    """Test that Advanced gates refresh during trade"""
    # 1. Trade opens with RMAG -3.0σ
    # 2. During trade, RMAG changes to -5.0σ
    # 3. Verify gates refresh and use new RMAG value
    # 4. Verify trailing gates use updated RMAG
    pass
```

#### **Test 5: DTMS Defensive Actions**
```python
def test_dtms_defensive_actions():
    """Test DTMS takes defensive actions when needed"""
    # 1. Trade registered to DTMS
    # 2. Simulate adverse market conditions
    # 3. Verify DTMS detects warning state
    # 4. Verify DTMS takes defensive action (SL adjustment, partial close, etc.)
    # 5. Verify Discord notification sent
    pass
```

### **Manual Testing Checklist**

#### **Phase 1: RMAG Threshold Fix**
- [ ] Execute BTCUSD trade, verify log shows "RMAG threshold: 4.0σ"
- [ ] Execute XAUUSD trade, verify log shows "RMAG threshold: 2.0σ"
- [ ] Execute EURUSD trade, verify log shows "RMAG threshold: 2.0σ (default)"
- [ ] Verify Advanced-Enhanced exits message shows correct threshold
- [ ] Verify BTCUSD trade with -5.0σ does NOT trigger RMAG tightening

#### **Phase 2: Trailing Gates Fix**
- [ ] Execute trade, reach breakeven
- [ ] Verify log shows "Trailing gates: ... → ALLOW trailing"
- [ ] Verify trailing activates even when RMAG > 2.0σ (for BTCUSD)
- [ ] Verify log shows "multiplier=2.0x" when gates fail
- [ ] Verify trailing stop moves correctly with multiplier
- [ ] Verify backward compatibility (existing trades work)

#### **Phase 3: Breakeven Buffer**
- [ ] Execute trade, reach breakeven
- [ ] Verify breakeven SL is below entry (for BUY) or above entry (for SELL)
- [ ] Verify trade doesn't close on minor retracement (0.2× ATR)
- [ ] Verify trade closes on larger retracement (0.4× ATR)
- [ ] Verify buffer scales with volatility (high ATR = larger buffer)

#### **Phase 4: Advanced Provider**
- [ ] Execute trade, enable intelligent exits
- [ ] Wait 30 seconds, check logs for "Gates refresh"
- [ ] Verify RMAG values update during trade
- [ ] Verify trailing gates use current market data
- [ ] Verify cache works (doesn't call build_features_advanced() every cycle)

#### **Phase 5: Enhanced Logging**
- [ ] Execute trade, reach breakeven
- [ ] Check logs for detailed gate status
- [ ] Verify all gate values are logged
- [ ] Verify reason for trailing allow/block is clear

#### **Phase 6: DTMS**
- [ ] Verify DTMS initializes on bot startup
- [ ] Execute trade, verify Discord alert "DTMS Protection Auto-Enabled"
- [ ] Check logs for "DTMS monitoring cycle" every 30 seconds
- [ ] Simulate adverse conditions, verify DTMS takes action
- [ ] Verify DTMS state transitions logged

### **Performance Tests**

#### **Test 1: Advanced Provider Cache Performance**
```python
def test_advanced_provider_cache_performance():
    """Test that Advanced provider cache reduces API calls"""
    # 1. Call get_advanced_features() 10 times in 30 seconds
    # 2. Verify build_features_advanced() called only once (cached)
    # 3. Wait 61 seconds, call again
    # 4. Verify cache refreshed (called again)
    pass
```

#### **Test 2: Trailing Stop Calculation Performance**
```python
def test_trailing_stop_performance():
    """Test trailing stop calculation doesn't block monitoring"""
    # 1. Create 10 open trades
    # 2. All reach breakeven
    # 3. Verify trailing stop calculation completes in < 1 second
    # 4. Verify monitoring cycle completes in < 5 seconds
    pass
```

### **Regression Tests**

#### **Test 1: Existing Functionality Still Works**
```python
def test_regression_existing_functionality():
    """Test that existing functionality still works after fixes"""
    # 1. Test breakeven still works (without buffer initially)
    # 2. Test partial profits still work
    # 3. Test VIX adjustments still work
    # 4. Test hybrid ATR+VIX still works
    # 5. Test existing trades load correctly
    pass
```

#### **Test 2: Backward Compatibility**
```python
def test_backward_compatibility():
    """Test backward compatibility with existing exit rules"""
    # 1. Load existing intelligent_exits.json
    # 2. Verify old rules work with new code
    # 3. Verify trailing_multiplier defaults to 1.5 for old rules
    # 4. Verify RMAG threshold defaults to 2.0 for unknown symbols
    pass
```

---

## 📊 Success Metrics

### **Primary Metrics**
1. **RMAG Trigger Rate:** < 50% of trades (currently 100%)
2. **Trailing Activation Rate:** > 80% of trades after breakeven (currently 0%)
3. **Breakeven Hit Rate:** < 30% of trades close at breakeven (currently high)
4. **DTMS Action Rate:** > 0% (currently 0%)

### **Secondary Metrics**
- Average profit per trade (should increase)
- Trade duration (should increase for winners)
- Win rate (should improve)

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Asset-specific thresholds too permissive | Start conservative, adjust based on results |
| Trailing gates too lenient | Monitor and tighten if needed |
| Breakeven buffer too wide | Use 0.3× ATR (conservative) |
| DTMS initialization fails | Add fallback, log errors clearly |
| Performance impact from Advanced refresh | Cache results, refresh every 60 seconds |

---

## 📝 Documentation Updates

1. Update `docs/ADVANCED_INTELLIGENT_EXITS_COMPLETE.md` with new thresholds
2. Update `docs/ADVANCED_EXITS_RULES.md` with gate system changes
3. Create `docs/DTMS_INITIALIZATION_GUIDE.md`
4. Update `docs/TRAILING_STOPS_EXPLAINED.md` with new gate logic

---

## 🚀 Deployment Strategy

1. **Development:** Implement fixes in feature branch
2. **Testing:** Run comprehensive tests
3. **Staging:** Deploy to staging, monitor for 48 hours
4. **Production:** Deploy with feature flags (can disable if issues)
5. **Monitoring:** Monitor metrics for 1 week, adjust as needed

---

## ✅ Completion Criteria

- [ ] All 12 phases implemented (9 core + 1 optional + 2 enhancements)
- [ ] All tests passing
- [ ] Manual testing complete
- [ ] Documentation updated
- [ ] Metrics show improvement
- [ ] No regressions introduced
- [ ] DTMS webpage endpoints working
- [ ] Thread safety verified

---

**Total Estimated Time:** 28 hours (3.5-4 days of focused work)
- Implementation: 25 hours (reduced by reusing existing utilities)
- Testing: 3 hours

**Priority:** CRITICAL - These fixes are blocking core functionality

---

## 🔍 Critical Issues Review Summary

### **Issues Found and Fixed:**

1. ✅ **DTMS Webpage Endpoint (NEW)**: `/dtms/trade/{ticket}` returns 404 - fixed by adding JSON endpoint and correcting port references
2. ✅ **Thread Safety (NEW)**: `self.rules` dictionary accessed without locks - fixed by adding threading lock
3. ✅ **ATR Calculation Redundancy**: Plan proposed reimplementing - fixed by using existing `streamer_data_access.calculate_atr()`
4. ✅ **Symbol Normalization**: Plan proposed new logic - fixed by reusing existing pattern from `desktop_agent.py`
5. ✅ **Advanced Provider Interface**: Mismatch between `get_multi()` and Advanced features - fixed by creating wrapper
6. ✅ **Port Configuration**: Multiple inconsistent port references (8001, 8002) - fixed by standardizing on relative URLs
7. ✅ **ChatGPT Integration**: Missing documentation updates - fixed by adding comprehensive integration section

### **No Additional Critical Issues Found:**
- ✅ Data persistence: Atomic writes already implemented
- ✅ Error handling: Comprehensive try/except blocks present
- ✅ Integration points: All identified and addressed
- ✅ Backward compatibility: Maintained throughout

---

## 🤖 ChatGPT Integration Requirements

### **openai.yaml Updates Needed**

**Current Status:** ✅ Intelligent exits already documented in openai.yaml
- Lines 626-629: `toggle_intelligent_exits`, `enableIntelligentExits`, `start_trailing_stops`
- Lines 1479-1497: Tool definitions and examples
- Lines 1085-1087: `strategy_type` parameter for Universal Manager vs Intelligent Exits

**Updates Required:**
1. **Add note about asset-specific RMAG thresholds:**
   ```yaml
   # In moneybot.toggle_intelligent_exits description
   - Note: Advanced-Enhanced exits use asset-specific RMAG thresholds:
     * BTCUSD: 4.0σ threshold (high volatility asset)
     * XAUUSD: 2.0σ threshold (standard)
     * Other assets: 2.0σ default
     * Triggers tighten to 20%/40% only when RMAG exceeds asset-specific threshold
   ```

2. **Update trailing stops description:**
   ```yaml
   # In moneybot.start_trailing_stops description
   - Trailing stops now use tiered gate system:
     * Activates even when RMAG > 2.0σ (for BTCUSD, uses 4.0σ threshold)
     * Uses wider trailing distance (2.0× ATR) when advisory gates fail
     * Normal trailing distance (1.5× ATR) when gates pass
   ```

3. **Add breakeven buffer note:**
   ```yaml
   # In intelligent exits description
   - Breakeven now includes ATR-based buffer (0.3× ATR):
     * Prevents premature closures on minor retracements
     * Buffer scales with volatility (high ATR = larger buffer)
     * Fallback to 0.1% price buffer if ATR unavailable
   ```

### **Knowledge Document Updates Needed**

**File:** `docs/ChatGPT Knowledge Documents/ChatGPT_Knowledge_Document.md`

**Current Status:** ✅ Intelligent exits already documented (lines 2296-2607)
- Percentage-based system explained
- Advanced-adjusted triggers documented
- Examples provided

**Updates Required:**
1. **Add asset-specific RMAG thresholds section (after line 2422):**
   ```markdown
   ### Asset-Specific RMAG Thresholds (NEW - December 2025)
   
   The system now uses asset-specific RMAG thresholds to prevent unnecessary tightening:
   
   - **BTCUSD**: 4.0σ threshold (high volatility, can stretch further)
   - **XAUUSD**: 2.0σ threshold (standard sensitivity)
   - **Other assets**: 2.0σ default
   
   **Why This Matters:**
   - BTCUSD regularly shows -6.0σ (normal for crypto)
   - Old system: Always tightened to 20%/40% (too aggressive)
   - New system: Only tightens if RMAG > asset-specific threshold
   - Result: BTCUSD trades get 30%/60% base triggers (not 20%/40%)
   
   **Example:**
   ```
   BTCUSD trade with RMAG -5.0σ:
   - Old: 20%/40% (always tightened)
   - New: 30%/60% (RMAG -5.0σ < 4.0σ threshold, no tightening)
   ```
   ```

2. **Update trailing stops section (around line 2345):**
   ```markdown
   #### 4. Continuous ATR Trailing (ENHANCED - December 2025)
   - **When**: After breakeven triggered
   - **Frequency**: Every 30 seconds
   - **Distance**: 1.5× ATR (normal) or 2.0× ATR (when gates fail)
   - **Gates**: Tiered system (advisory, not blocking)
     * Trailing activates even when RMAG > 2.0σ (uses asset-specific threshold)
     * Wider distance used when 3+ advisory gates fail
     * Normal distance when gates pass
   - **Direction**: BUY trails UP, SELL trails DOWN
   ```

3. **Add breakeven buffer section (after line 2327):**
   ```markdown
   #### 1. Breakeven with ATR Buffer (ENHANCED - December 2025)
   - **Trigger**: When price reaches 30% of distance to TP
   - **Action**: Move SL to entry price + spread - (0.3× ATR buffer)
   - **Buffer Purpose**: Prevents premature closures on minor retracements
   - **Buffer Size**: 0.3× ATR (scales with volatility)
   - **Fallback**: 0.1% of entry price if ATR unavailable
   - **R-Multiple**: 0.3R for 1:1 R:R trades, 0.6R for 2:1 trades
   
   **Example:**
   ```
   XAUUSD trade: Entry 2400, TP 2405, ATR = 5.0
   - Breakeven trigger: 30% of $5 = $1.50 (at 2401.50)
   - Breakeven SL: 2400 + 0.5 (spread) - 1.5 (ATR buffer) = 2399.00
   - Buffer allows normal retracements without closing trade
   ```
   ```

4. **Update Advanced-adjusted triggers section (around line 2392):**
   ```markdown
   **Asset-Specific Thresholds:**
   - BTCUSD: Only tightens if RMAG > 4.0σ (not 2.0σ)
   - XAUUSD: Tightens if RMAG > 2.0σ
   - Other assets: Tightens if RMAG > 2.0σ (default)
   
   **Result:**
   - BTCUSD trades rarely get tightened (RMAG -5.0σ < 4.0σ threshold)
   - XAUUSD trades tighten appropriately (RMAG -2.5σ > 2.0σ threshold)
   ```

5. **Add symbol-specific parameters section (new):**
   ```markdown
   ### Symbol-Specific Exit Parameters (NEW - December 2025)
   
   The system now uses symbol-specific parameters optimized for each asset's volatility:
   
   **Trailing Stop Multipliers:**
   - BTCUSD: 2.0× ATR (wider - accommodates high volatility)
   - XAUUSD: 1.5× ATR (standard)
   - Forex majors (EURUSD, GBPUSD, USDJPY): 1.2× ATR (tighter - lower volatility)
   
   **Breakeven Buffers:**
   - BTCUSD: 0.5× ATR (larger buffer for volatile retracements)
   - XAUUSD: 0.3× ATR (standard)
   - Forex majors: 0.2× ATR (smaller buffer - more stable)
   
   **Session Adjustments:**
   - Parameters adjust based on trading session
   - Asia session: Wider trailing/buffer (lower liquidity)
   - Overlap session: Tighter trailing/buffer (high liquidity)
   - London/NY: Standard parameters
   
   **Benefits:**
   - Reduced premature closures on volatile assets
   - Better profit capture on stable assets
   - Optimized for each asset's volatility profile
   ```

### **Priority for ChatGPT Updates**

**HIGH Priority (Update Immediately):**
1. ✅ Asset-specific RMAG thresholds (affects user expectations)
2. ✅ Trailing stops tiered gates (affects user understanding)
3. ✅ Breakeven buffer (affects user expectations)

**MEDIUM Priority (Update After Implementation):**
4. Advanced provider refresh (technical detail)
5. Enhanced logging (technical detail)

**Action Items:**
- [ ] Update `openai.yaml` with asset-specific RMAG notes
- [ ] Update `ChatGPT_Knowledge_Document.md` with new features
- [ ] Test ChatGPT responses after updates
- [ ] Verify examples work correctly

---

## 🔄 Reuse Existing System Functionality

### **ATR Calculation**
- ✅ **USE**: `infra/streamer_data_access.calculate_atr()` (preferred)
- ✅ **FALLBACK**: Direct MT5 calculation (existing pattern)
- ❌ **DON'T**: Reimplement ATR calculation from scratch
- **Benefit**: Faster (cached data), consistent, tested

### **Symbol Normalization**
- ✅ **USE**: Pattern from `desktop_agent.py` (lines 2129-2131)
- ✅ **HANDLES**: DXY, VIX, US10Y edge cases
- ❌ **DON'T**: Create new normalization logic
- **Benefit**: Consistent with codebase, handles all edge cases

### **Asset-Specific Configuration**
- ✅ **USE**: `config/settings.py` for RMAG thresholds (simple dict)
- ✅ **CONSIDER**: `config/symbol_config_loader.py` for future expansion
- ❌ **DON'T**: Create new config system
- **Benefit**: Simple, maintainable, follows existing patterns

### **Advanced Features Building**
- ✅ **USE**: `infra/feature_builder_advanced.build_features_advanced()`
- ✅ **ALREADY**: Integrated in `AdvancedProviderWrapper`
- ❌ **DON'T**: Rebuild Advanced features
- **Benefit**: Reuses proven, tested code

### **Indicator Bridge**
- ✅ **USE**: `IndicatorBridge.get_multi()` (already passed as provider)
- ✅ **WRAP**: Create `AdvancedProviderWrapper` to convert to Advanced format
- ❌ **DON'T**: Modify IndicatorBridge directly
- **Benefit**: Non-invasive, maintains backward compatibility

---

## 🔍 Additional Issues Found During Review

### **Issue 9: Symbol Normalization**
**Problem:** Symbols may come with/without 'c' suffix (BTCUSD vs BTCUSDc)
**Fix:** ✅ Reuse existing normalization pattern from `desktop_agent.py` (Phase 1)

### **Issue 10: ExitRule Missing trailing_multiplier Attribute**
**Problem:** `ExitRule` class doesn't have `trailing_multiplier` attribute
**Fix:** Add to `ExitRule.__init__()` with default 1.5 (addressed in Phase 2)

### **Issue 11: Advanced Provider Cache Needed**
**Problem:** `build_features_advanced()` is expensive, called every cycle
**Fix:** ✅ Add 60-second cache to `AdvancedProviderWrapper` (addressed in Phase 4)

### **Issue 12: DTMS Registration May Be Skipped**
**Problem:** Some trade execution paths may skip DTMS registration
**Fix:** ✅ Verify all paths register trades (addressed in Phase 6)

### **Issue 13: ATR Calculation Redundancy**
**Problem:** Plan proposed reimplementing ATR calculation
**Fix:** ✅ Use existing `infra/streamer_data_access.calculate_atr()` utility (Phase 3)

### **Issue 14: Missing ChatGPT Integration**
**Problem:** Plan didn't address ChatGPT knowledge document updates
**Fix:** ✅ Added comprehensive ChatGPT integration section (see above)

### **Issue 15: Configuration Management**
**Problem:** Could use existing asset config systems
**Fix:** ✅ Use `config/settings.py` for RMAG thresholds (simple, maintainable)

### **Issue 16: DTMS Webpage Endpoint Missing**
**Problem:** `/dtms/trade/{ticket}` webpage returns 404 - HTML page tries to fetch from wrong port
**Fix:** ✅ Add JSON endpoint in `app/main_api.py` and fix port references (addressed in Phase 6)

### **Issue 17: Thread Safety for Rules Dictionary**
**Problem:** `self.rules` dictionary accessed without locks - potential race conditions
**Fix:** ✅ Add threading lock to protect `self.rules` dictionary (addressed in Phase 9)

### **Issue 18: DTMS Port Configuration Inconsistency**
**Problem:** Multiple port references (8001, 8002) causing confusion
**Fix:** ✅ Standardize on relative URLs or document correct ports (addressed in Phase 7)

---

## 📋 Final Review Summary

### **Critical Issues Identified:**
1. ✅ **RMAG Threshold** - Asset-specific thresholds needed (Phase 1)
2. ✅ **Trailing Gates** - Too strict, blocking all trailing (Phase 2)
3. ✅ **DTMS Initialization** - Engine not initialized (Phase 6)
4. ✅ **DTMS Webpage** - Endpoint missing, wrong port (Phase 7) - **NEW**
5. ✅ **Thread Safety** - Rules dictionary race conditions (Phase 9) - **NEW**
6. ✅ **Breakeven Buffer** - Too tight, no ATR buffer (Phase 3)
7. ✅ **Advanced Provider** - Not set, stale data (Phase 4)
8. ✅ **Enhanced Logging** - Missing gate failure logs (Phase 5)
9. ✅ **Trade Type Classifier** - Not integrated (Phase 8)
10. ✅ **Advanced Triggers Refresh** - Optional enhancement (Phase 10)
11. ✅ **Symbol-Specific Parameters** - Optimization for XAU/BTC/Forex (Phase 11) - **NEW**
12. ✅ **Error Handling & Robustness** - Conflict prevention, circuit breakers, validation (Phase 12) - **NEW**

### **Major Issues Fixed:**
- ✅ ATR calculation redundancy → Use existing utility
- ✅ Symbol normalization → Reuse existing pattern
- ✅ ChatGPT integration → Comprehensive documentation added
- ✅ Port configuration → Standardized on relative URLs

### **No Additional Critical Issues Found:**
- ✅ Data persistence: Atomic writes already implemented
- ✅ Error handling: Comprehensive try/except blocks present
- ✅ Integration points: All identified and addressed
- ✅ Backward compatibility: Maintained throughout

### **Plan Status:**
- ✅ All logic issues identified and addressed
- ✅ All integration issues identified and addressed
- ✅ All critical issues have fixes documented
- ✅ Comprehensive test coverage included
- ✅ ChatGPT integration requirements documented
- ✅ Ready for implementation

---

## 🎯 Phase 11: Symbol-Specific Parameter Optimization (ENHANCEMENT) ✅ **COMPLETED**

**Problem:** Intelligent exits use hardcoded parameters (1.5x ATR trailing, 0.3x ATR breakeven buffer) for all symbols, ignoring volatility differences

**Solution:** Implement symbol-specific parameters for XAUUSD, BTCUSD, and forex majors

**Files to Modify:**
- `config/settings.py` (add symbol-specific exit parameters)
- `infra/intelligent_exit_manager.py` (use symbol-specific parameters)
- `config/asset_profiles.json` (extend with exit parameters)

**Rationale:**
- **BTCUSD**: Very high volatility (1.5-2.0x ATR range) → needs wider trailing (2.0x ATR) and larger breakeven buffer (0.5x ATR)
- **XAUUSD**: High volatility (1.0-1.2x ATR range) → needs moderate trailing (1.5x ATR) and standard buffer (0.3x ATR)
- **Forex Majors**: Moderate volatility (0.8-1.0x ATR range) → needs tighter trailing (1.2x ATR) and smaller buffer (0.2x ATR)

**Changes:**

1. **Add Symbol-Specific Exit Parameters to `config/settings.py`:**
   ```python
   # Symbol-Specific Intelligent Exit Parameters
   INTELLIGENT_EXIT_SYMBOL_PARAMS = {
       "BTCUSDc": {
           "trailing_atr_multiplier": 2.0,      # Wider trailing (high volatility)
           "breakeven_buffer_atr_mult": 0.5,     # Larger buffer (0.5x ATR)
           "breakeven_trigger_pct": 30.0,        # Standard 30%
           "partial_profit_pct": 60.0,           # Standard 60%
           "atr_timeframe": "M15",               # M15 ATR for BTC
           "trailing_timeframe": "M5",           # M5 for trailing updates
           "min_sl_change_pct": 0.1,             # 0.1% minimum change
           "trailing_gate_rmag_threshold": 4.0,  # Already set (Phase 1)
           "session_adjustments": {
               "ASIAN": {"trailing_mult": 2.2, "buffer_mult": 0.6},  # Wider in Asia
               "LONDON": {"trailing_mult": 2.0, "buffer_mult": 0.5},
               "NY": {"trailing_mult": 2.0, "buffer_mult": 0.5},
               "OVERLAP": {"trailing_mult": 1.8, "buffer_mult": 0.4}  # Tighter in overlap
           }
       },
       "BTCUSD": {  # Handle without 'c' suffix
           "trailing_atr_multiplier": 2.0,
           "breakeven_buffer_atr_mult": 0.5,
           "breakeven_trigger_pct": 30.0,
           "partial_profit_pct": 60.0,
           "atr_timeframe": "M15",
           "trailing_timeframe": "M5",
           "min_sl_change_pct": 0.1,
           "trailing_gate_rmag_threshold": 4.0
       },
       "XAUUSDc": {
           "trailing_atr_multiplier": 1.5,      # Standard trailing
           "breakeven_buffer_atr_mult": 0.3,    # Standard buffer
           "breakeven_trigger_pct": 30.0,
           "partial_profit_pct": 60.0,
           "atr_timeframe": "M15",               # M15 ATR for XAU
           "trailing_timeframe": "M5",
           "min_sl_change_pct": 0.08,            # 0.08% minimum (tighter)
           "trailing_gate_rmag_threshold": 2.0,  # Already set (Phase 1)
           "session_adjustments": {
               "ASIAN": {"trailing_mult": 1.8, "buffer_mult": 0.4},  # Wider in Asia
               "LONDON": {"trailing_mult": 1.5, "buffer_mult": 0.3},
               "NY": {"trailing_mult": 1.5, "buffer_mult": 0.3},
               "OVERLAP": {"trailing_mult": 1.3, "buffer_mult": 0.25}  # Tighter in overlap
           }
       },
       "XAUUSD": {
           "trailing_atr_multiplier": 1.5,
           "breakeven_buffer_atr_mult": 0.3,
           "breakeven_trigger_pct": 30.0,
           "partial_profit_pct": 60.0,
           "atr_timeframe": "M15",
           "trailing_timeframe": "M5",
           "min_sl_change_pct": 0.08,
           "trailing_gate_rmag_threshold": 2.0
       },
       "EURUSDc": {
           "trailing_atr_multiplier": 1.2,      # Tighter trailing (lower volatility)
           "breakeven_buffer_atr_mult": 0.2,     # Smaller buffer (0.2x ATR)
           "breakeven_trigger_pct": 30.0,
           "partial_profit_pct": 60.0,
           "atr_timeframe": "M15",
           "trailing_timeframe": "M5",
           "min_sl_change_pct": 0.05,            # 0.05% minimum (very tight)
           "trailing_gate_rmag_threshold": 2.0,
           "session_adjustments": {
               "ASIAN": {"trailing_mult": 1.4, "buffer_mult": 0.25},
               "LONDON": {"trailing_mult": 1.2, "buffer_mult": 0.2},
               "NY": {"trailing_mult": 1.2, "buffer_mult": 0.2},
               "OVERLAP": {"trailing_mult": 1.1, "buffer_mult": 0.15}
           }
       },
       "EURUSD": {
           "trailing_atr_multiplier": 1.2,
           "breakeven_buffer_atr_mult": 0.2,
           "breakeven_trigger_pct": 30.0,
           "partial_profit_pct": 60.0,
           "atr_timeframe": "M15",
           "trailing_timeframe": "M5",
           "min_sl_change_pct": 0.05,
           "trailing_gate_rmag_threshold": 2.0
       },
       "GBPUSDc": {
           "trailing_atr_multiplier": 1.3,      # Slightly wider than EURUSD
           "breakeven_buffer_atr_mult": 0.25,    # Slightly larger buffer
           "breakeven_trigger_pct": 30.0,
           "partial_profit_pct": 60.0,
           "atr_timeframe": "M15",
           "trailing_timeframe": "M5",
           "min_sl_change_pct": 0.06,
           "trailing_gate_rmag_threshold": 2.0,
           "session_adjustments": {
               "ASIAN": {"trailing_mult": 1.5, "buffer_mult": 0.3},
               "LONDON": {"trailing_mult": 1.3, "buffer_mult": 0.25},
               "NY": {"trailing_mult": 1.3, "buffer_mult": 0.25},
               "OVERLAP": {"trailing_mult": 1.2, "buffer_mult": 0.2}
           }
       },
       "GBPUSD": {
           "trailing_atr_multiplier": 1.3,
           "breakeven_buffer_atr_mult": 0.25,
           "breakeven_trigger_pct": 30.0,
           "partial_profit_pct": 60.0,
           "atr_timeframe": "M15",
           "trailing_timeframe": "M5",
           "min_sl_change_pct": 0.06,
           "trailing_gate_rmag_threshold": 2.0
       },
       "USDJPYc": {
           "trailing_atr_multiplier": 1.2,      # Similar to EURUSD
           "breakeven_buffer_atr_mult": 0.2,
           "breakeven_trigger_pct": 30.0,
           "partial_profit_pct": 60.0,
           "atr_timeframe": "M15",
           "trailing_timeframe": "M5",
           "min_sl_change_pct": 0.05,
           "trailing_gate_rmag_threshold": 2.0,
           "session_adjustments": {
               "ASIAN": {"trailing_mult": 1.4, "buffer_mult": 0.25},  # JPY active in Asia
               "LONDON": {"trailing_mult": 1.2, "buffer_mult": 0.2},
               "NY": {"trailing_mult": 1.2, "buffer_mult": 0.2},
               "OVERLAP": {"trailing_mult": 1.1, "buffer_mult": 0.15}
           }
       },
       "USDJPY": {
           "trailing_atr_multiplier": 1.2,
           "breakeven_buffer_atr_mult": 0.2,
           "breakeven_trigger_pct": 30.0,
           "partial_profit_pct": 60.0,
           "atr_timeframe": "M15",
           "trailing_timeframe": "M5",
           "min_sl_change_pct": 0.05,
           "trailing_gate_rmag_threshold": 2.0
       },
       "DEFAULT": {
           "trailing_atr_multiplier": 1.5,      # Default for unknown symbols
           "breakeven_buffer_atr_mult": 0.3,
           "breakeven_trigger_pct": 30.0,
           "partial_profit_pct": 60.0,
           "atr_timeframe": "M15",
           "trailing_timeframe": "M5",
           "min_sl_change_pct": 0.1,
           "trailing_gate_rmag_threshold": 2.0
       }
   }
   ```

2. **Add Helper Method to Get Symbol-Specific Parameters:**
   ```python
   def _get_symbol_exit_params(self, symbol: str, session: Optional[str] = None) -> Dict[str, Any]:
       """Get symbol-specific exit parameters with session adjustments"""
       from config.settings import INTELLIGENT_EXIT_SYMBOL_PARAMS
       
       # Normalize symbol (same pattern as Phase 1)
       symbol_normalized = symbol.upper()
       if symbol_normalized not in ['DXY', 'VIX', 'US10Y', 'SPX']:
           if not symbol_normalized.endswith('C'):
               symbol_normalized = symbol_normalized + 'C'
           else:
               symbol_normalized = symbol_normalized.rstrip('cC') + 'C'
       
       # Get base params
       params = INTELLIGENT_EXIT_SYMBOL_PARAMS.get(symbol_normalized) or \
                INTELLIGENT_EXIT_SYMBOL_PARAMS.get(symbol_normalized.rstrip('cC')) or \
                INTELLIGENT_EXIT_SYMBOL_PARAMS.get("DEFAULT", {})
       
       # Apply session adjustments if available
       if session and "session_adjustments" in params:
           session_adj = params["session_adjustments"].get(session, {})
           if "trailing_mult" in session_adj:
               params = params.copy()  # Don't modify original
               params["trailing_atr_multiplier"] = session_adj["trailing_mult"]
           if "buffer_mult" in session_adj:
               params = params.copy()
               params["breakeven_buffer_atr_mult"] = session_adj["buffer_mult"]
       
       return params
   ```

3. **Update `_trail_stop_atr()` to Use Symbol-Specific Multiplier:**
   ```python
   def _trail_stop_atr(self, rule: ExitRule, position, current_price: float, trailing_multiplier: Optional[float] = None) -> Optional[Dict[str, Any]]:
       """Trailing stop with symbol-specific multiplier"""
       
       # Get symbol-specific params
       from infra.session_detector import get_current_session
       session = get_current_session()  # Get current trading session
       symbol_params = self._get_symbol_exit_params(rule.symbol, session)
       
       # Use provided multiplier, symbol-specific, or stored multiplier
       if trailing_multiplier is None:
           trailing_multiplier = getattr(rule, "trailing_multiplier", None) or \
                                 symbol_params.get("trailing_atr_multiplier", 1.5)
       
       # Get ATR timeframe from symbol params
       atr_timeframe = symbol_params.get("atr_timeframe", "M15")
       
       # Calculate ATR (reuse existing utility)
       atr = self._calculate_atr(rule.symbol, atr_timeframe, 14)
       if not atr or atr <= 0:
           return None
       
       # Use symbol-specific multiplier
       trailing_distance = atr * trailing_multiplier
       
       # ... rest of existing code ...
   ```

4. **Update `_move_to_breakeven()` to Use Symbol-Specific Buffer:**
   ```python
   def _move_to_breakeven(self, rule: ExitRule, position, current_price: float) -> Optional[Dict[str, Any]]:
       """Move stop loss to breakeven with symbol-specific buffer"""
       
       # Get symbol-specific params
       from infra.session_detector import get_current_session
       session = get_current_session()
       symbol_params = self._get_symbol_exit_params(rule.symbol, session)
       
       # Get buffer multiplier from symbol params
       buffer_mult = symbol_params.get("breakeven_buffer_atr_mult", 0.3)
       
       # Get ATR timeframe
       atr_timeframe = symbol_params.get("atr_timeframe", "M15")
       
       # Calculate ATR buffer
       atr = self._calculate_atr(rule.symbol, atr_timeframe, 14)
       if atr and atr > 0:
           atr_buffer = atr * buffer_mult
       else:
           # Fallback: use 0.1% of entry price
           atr_buffer = rule.entry_price * 0.001
       
       # ... rest of existing code ...
   ```

5. **Update `_trailing_gates_pass()` to Use Symbol-Specific RMAG Threshold:**
   ```python
   def _trailing_gates_pass(self, rule: ExitRule, profit_pct: float, r_achieved: float, return_details: bool = False) -> Union[bool, Tuple[bool, Dict[str, Any]]]:
       """Trailing gates with symbol-specific RMAG threshold"""
       
       # Get symbol-specific params (RMAG threshold already set in Phase 1, but use symbol params for consistency)
       symbol_params = self._get_symbol_exit_params(rule.symbol)
       rmag_threshold = symbol_params.get("trailing_gate_rmag_threshold") or \
                       self._get_rmag_threshold(rule.symbol)  # Fallback to Phase 1 method
       
       # ... rest of existing code ...
   ```

**Integration Issues:**
- ✅ Need to import `get_current_session()` from `infra.session_detector` (or similar)
- ✅ Session detection may not be available - use None as fallback
- ✅ Symbol normalization already implemented in Phase 1

**Testing:**
- Verify BTCUSD uses 2.0x ATR trailing (wider)
- Verify XAUUSD uses 1.5x ATR trailing (standard)
- Verify EURUSD uses 1.2x ATR trailing (tighter)
- Verify session adjustments apply correctly
- Verify breakeven buffers scale with volatility
- Verify fallback to DEFAULT works for unknown symbols

**Logic Issues Found:**
- ❌ Session detection may not be available - need graceful fallback
- ❌ No validation that symbol parameters are within reasonable ranges
- ❌ Missing error handling if session detection fails

**Additional Changes:**
1. Add graceful fallback for session detection:
   ```python
   def _get_symbol_exit_params(self, symbol: str, session: Optional[str] = None) -> Dict[str, Any]:
       """Get symbol-specific exit parameters with session adjustments"""
       from config.settings import INTELLIGENT_EXIT_SYMBOL_PARAMS
       
       # ... existing normalization code ...
       
       # Get base params
       params = INTELLIGENT_EXIT_SYMBOL_PARAMS.get(symbol_normalized) or \
                INTELLIGENT_EXIT_SYMBOL_PARAMS.get(symbol_normalized.rstrip('cC')) or \
                INTELLIGENT_EXIT_SYMBOL_PARAMS.get("DEFAULT", {})
       
       # Validate parameters are within reasonable ranges
       params = self._validate_symbol_params(params, symbol)
       
       # Apply session adjustments if available AND session detected
       if session and "session_adjustments" in params:
           session_adj = params["session_adjustments"].get(session, {})
           if "trailing_mult" in session_adj:
               params = params.copy()
               params["trailing_atr_multiplier"] = session_adj["trailing_mult"]
           if "buffer_mult" in session_adj:
               params = params.copy()
               params["breakeven_buffer_atr_mult"] = session_adj["buffer_mult"]
       # If session is None, use base params (graceful fallback)
       
       return params
   
   def _validate_symbol_params(self, params: Dict[str, Any], symbol: str) -> Dict[str, Any]:
       """Validate symbol parameters are within reasonable ranges"""
       validated = params.copy()
       
       # Validate trailing multiplier (0.5x to 3.0x ATR)
       trailing_mult = validated.get("trailing_atr_multiplier", 1.5)
       if not (0.5 <= trailing_mult <= 3.0):
           logger.warning(f"Invalid trailing_atr_multiplier {trailing_mult} for {symbol}, using 1.5")
           validated["trailing_atr_multiplier"] = 1.5
       
       # Validate buffer multiplier (0.1x to 1.0x ATR)
       buffer_mult = validated.get("breakeven_buffer_atr_mult", 0.3)
       if not (0.1 <= buffer_mult <= 1.0):
           logger.warning(f"Invalid breakeven_buffer_atr_mult {buffer_mult} for {symbol}, using 0.3")
           validated["breakeven_buffer_atr_mult"] = 0.3
       
       # Validate percentages (0-100)
       breakeven_pct = validated.get("breakeven_trigger_pct", 30.0)
       if not (0 <= breakeven_pct <= 100):
           logger.warning(f"Invalid breakeven_trigger_pct {breakeven_pct} for {symbol}, using 30.0")
           validated["breakeven_trigger_pct"] = 30.0
       
       return validated
   ```

2. Add graceful session detection fallback:
   ```python
   # In _trail_stop_atr() and _move_to_breakeven()
   try:
       from infra.session_detector import get_current_session
       session = get_current_session()
   except (ImportError, AttributeError, Exception) as e:
       logger.debug(f"Session detection unavailable: {e}, using base parameters")
       session = None  # Graceful fallback - use base params
   ```

**Integration Issues:**
- ✅ Need to import `get_current_session()` from `infra.session_detector` (or similar)
- ✅ Session detection may not be available - use None as fallback (graceful degradation)
- ✅ Symbol normalization already implemented in Phase 1
- ✅ Parameter validation prevents invalid configurations

**Testing:**
- Verify BTCUSD uses 2.0x ATR trailing (wider)
- Verify XAUUSD uses 1.5x ATR trailing (standard)
- Verify EURUSD uses 1.2x ATR trailing (tighter)
- Verify session adjustments apply correctly
- Verify fallback works when session detection unavailable
- Verify parameter validation catches invalid values
- Verify breakeven buffers scale with volatility
- Verify fallback to DEFAULT works for unknown symbols

**Estimated Time:** 3 hours

**Benefits:**
- ✅ **Better Risk Management**: Wider trailing for volatile assets (BTC), tighter for stable assets (EURUSD)
- ✅ **Reduced Premature Closures**: Larger buffers for volatile assets prevent stop-outs on normal retracements
- ✅ **Session Optimization**: Adjusts parameters based on trading session (wider in Asia for BTC, tighter in overlap)
- ✅ **Improved Win Rate**: Symbol-specific parameters match asset volatility characteristics
- ✅ **Robust Error Handling**: Graceful fallback when session detection unavailable
- ✅ **Data Validation**: Prevents invalid configurations from causing issues

---

### **Phase 12: Error Handling & System Robustness (CRITICAL)** ✅ **COMPLETED**

**Problem:** Missing error handling, conflict prevention, and system robustness features

**Solution:** Add comprehensive error handling, conflict prevention, and robustness features

**Files to Modify:**
- `infra/intelligent_exit_manager.py` (all methods)
- `infra/advanced_provider_wrapper.py` (new file or in intelligent_exit_manager.py)

**Logic Issues Found:**
- ❌ No conflict prevention with Universal Manager or DTMS
- ❌ Advanced provider cache not thread-safe
- ❌ No circuit breaker for repeated ATR failures
- ❌ No JSON validation on load
- ❌ No retry logic for position modifications
- ❌ Cache grows unbounded (memory leak)
- ❌ No health check or diagnostics

**Changes:**

1. **Add Trade Registry Conflict Prevention:**
   ```python
   def _modify_position_sl(self, ticket: int, new_sl: float, current_tp: float) -> bool:
       """Modify position SL in MT5 with conflict prevention"""
       try:
           # CRITICAL: Check trade registry to prevent conflicts
           try:
               from infra.trade_registry import get_trade_state
               trade_state = get_trade_state(ticket)
               if trade_state:
                   managed_by = trade_state.get("managed_by", "")
                   # Skip if managed by Universal Manager (unless DTMS in defensive mode)
                   if managed_by == "universal_sl_tp_manager":
                       # Check if DTMS is in defensive mode (can override)
                       if not self._is_dtms_in_defensive_mode(ticket):
                           logger.debug(f"Skipping SL modification for {ticket}: managed by Universal Manager")
                           return False
                   # Skip if managed by DTMS in defensive mode
                   elif managed_by == "dtms_manager":
                       dtms_state = self._get_dtms_state(ticket)
                       if dtms_state in ["HEDGED", "WARNING_L2"]:
                           logger.debug(f"Skipping SL modification for {ticket}: DTMS in defensive mode")
                           return False
           except (ImportError, AttributeError, Exception) as e:
               logger.debug(f"Trade registry unavailable: {e}, proceeding with modification")
           
           # ... rest of existing modification code ...
       except Exception as e:
           logger.error(f"Error modifying position SL for ticket {ticket}: {e}", exc_info=True)
           return False
   
   def _is_dtms_in_defensive_mode(self, ticket: int) -> bool:
       """Check if DTMS is in defensive mode"""
       try:
           from dtms_integration import get_dtms_trade_status
           status = get_dtms_trade_status(ticket)
           if status and not status.get('error'):
               state = status.get('state', '')
               return state in ['HEDGED', 'WARNING_L2']
       except Exception:
           pass
       return False
   ```

2. **Add Thread Safety to Advanced Provider Cache:**
   ```python
   class AdvancedProviderWrapper:
       """Wrapper to convert IndicatorBridge.get_multi() to Advanced features format"""
       
       def __init__(self, indicator_bridge, mt5_service=None):
           self.indicator_bridge = indicator_bridge
           self.mt5_service = mt5_service
           self._cache = {}  # Cache Advanced features
           self._cache_timestamps = {}
           self._cache_lock = threading.Lock()  # NEW: Thread safety
           self._max_cache_size = 50  # NEW: Limit cache size
           self._cache_ttl = 60  # Cache TTL in seconds
       
       def get_advanced_features(self, symbol: str) -> Dict[str, Any]:
           """Get Advanced features for symbol, using cache to avoid excessive calls"""
           import time
           
           # Check cache (thread-safe)
           with self._cache_lock:
               cache_key = symbol
               if cache_key in self._cache:
                   cache_age = time.time() - self._cache_timestamps.get(cache_key, 0)
                   if cache_age < self._cache_ttl:
                       return self._cache[cache_key]
               
               # Cleanup old entries if cache too large
               if len(self._cache) >= self._max_cache_size:
                   self._cleanup_cache()
           
           # Build features (outside lock to avoid blocking)
           try:
               from infra.feature_builder_advanced import build_features_advanced
               # ... existing build logic ...
               
               features = build_features_advanced(...)
               
               if features and "features" in features:
                   # Store in cache (thread-safe)
                   with self._cache_lock:
                       self._cache[cache_key] = features
                       self._cache_timestamps[cache_key] = time.time()
                   return features
           except Exception as e:
               logger.warning(f"Failed to get Advanced features for {symbol}: {e}")
               # Return stale cache if available (graceful degradation)
               with self._cache_lock:
                   if cache_key in self._cache:
                       cache_age = time.time() - self._cache_timestamps.get(cache_key, 0)
                       if cache_age < self._cache_ttl * 2:  # Allow stale cache up to 2x TTL
                           logger.debug(f"Using stale cache for {symbol} (age: {cache_age:.0f}s)")
                           return self._cache[cache_key]
               return {}
       
       def _cleanup_cache(self):
           """Remove oldest cache entries"""
           import time
           current_time = time.time()
           
           # Remove expired entries first
           expired_keys = [
               k for k, ts in self._cache_timestamps.items()
               if current_time - ts > self._cache_ttl * 2
           ]
           for key in expired_keys:
               self._cache.pop(key, None)
               self._cache_timestamps.pop(key, None)
           
           # If still too large, remove oldest entries
           if len(self._cache) >= self._max_cache_size:
               sorted_keys = sorted(
                   self._cache_timestamps.items(),
                   key=lambda x: x[1]
               )
               keys_to_remove = [
                   k for k, _ in sorted_keys[:len(self._cache) - self._max_cache_size + 10]
               ]
               for key in keys_to_remove:
                   self._cache.pop(key, None)
                   self._cache_timestamps.pop(key, None)
   ```

3. **Add Circuit Breaker for ATR Calculation:**
   ```python
   def __init__(self, ...):
       # ... existing code ...
       self._atr_failure_count = {}  # Track ATR failures per symbol
       self._atr_circuit_breaker_threshold = 5  # Open circuit after 5 failures
       self._atr_circuit_breaker_timeout = 300  # 5 minutes before retry
       self._atr_circuit_breaker_timestamps = {}  # When circuit opened
       self._atr_fallback_values = {}  # Fallback ATR values per symbol
   
   def _calculate_atr(self, symbol: str, timeframe: str = "M15", period: int = 14) -> Optional[float]:
       """Calculate ATR with circuit breaker"""
       # Check circuit breaker
       if symbol in self._atr_circuit_breaker_timestamps:
           time_since_open = time.time() - self._atr_circuit_breaker_timestamps[symbol]
           if time_since_open < self._atr_circuit_breaker_timeout:
               # Circuit open - use fallback
               fallback = self._atr_fallback_values.get(symbol)
               if fallback:
                   logger.debug(f"ATR circuit breaker open for {symbol}, using fallback: {fallback}")
                   return fallback
               return None
           else:
               # Circuit timeout expired - reset
               logger.info(f"ATR circuit breaker reset for {symbol}, retrying")
               self._atr_circuit_breaker_timestamps.pop(symbol, None)
               self._atr_failure_count.pop(symbol, None)
       
       try:
           # ... existing ATR calculation ...
           atr = streamer_atr(symbol, timeframe, period=period)
           if atr and atr > 0:
               # Success - reset failure count
               self._atr_failure_count.pop(symbol, None)
               # Update fallback value
               self._atr_fallback_values[symbol] = atr
               return atr
       except Exception as e:
           logger.debug(f"ATR calculation failed for {symbol}: {e}")
       
       # Failure - increment count
       self._atr_failure_count[symbol] = self._atr_failure_count.get(symbol, 0) + 1
       
       # Check if circuit should open
       if self._atr_failure_count[symbol] >= self._atr_circuit_breaker_threshold:
           logger.warning(f"ATR circuit breaker opened for {symbol} after {self._atr_failure_count[symbol]} failures")
           self._atr_circuit_breaker_timestamps[symbol] = time.time()
           # Use fallback if available
           return self._atr_fallback_values.get(symbol)
       
       # Use fallback if available
       return self._atr_fallback_values.get(symbol)
   ```

4. **Add JSON Validation on Load:**
   ```python
   def _load_rules(self):
       """Load rules from JSON file with validation"""
       if not self.storage_file.exists():
           logger.info("No existing exit rules file found, starting fresh")
           return
       
       try:
           with open(self.storage_file, 'r') as f:
               data = json.load(f)
           
           # Validate structure
           if not isinstance(data, dict):
               logger.error(f"Invalid rules file structure: expected dict, got {type(data)}")
               # Backup corrupted file
               backup_file = self.storage_file.with_suffix('.corrupted')
               self.storage_file.rename(backup_file)
               logger.warning(f"Backed up corrupted file to {backup_file}")
               return
           
           # Load rules with validation
           loaded_count = 0
           for ticket_str, rule_data in data.items():
               try:
                   ticket = int(ticket_str)
                   # Validate rule data structure
                   if not isinstance(rule_data, dict):
                       logger.warning(f"Invalid rule data for ticket {ticket_str}, skipping")
                       continue
                   
                   # Validate required fields
                   required_fields = ["ticket", "symbol", "entry_price", "direction", "initial_sl", "initial_tp"]
                   if not all(field in rule_data for field in required_fields):
                       logger.warning(f"Missing required fields for ticket {ticket_str}, skipping")
                       continue
                   
                   rule = ExitRule.from_dict(rule_data)
                   self.rules[ticket] = rule
                   loaded_count += 1
               except (ValueError, KeyError, TypeError) as e:
                   logger.warning(f"Error loading rule for ticket {ticket_str}: {e}, skipping")
                   continue
           
           if loaded_count > 0:
               logger.info(f"✅ Loaded {loaded_count} exit rules from storage")
               # Auto-cleanup stale rules
               self._cleanup_stale_rules()
           else:
               logger.warning("No valid rules loaded from file")
               
       except json.JSONDecodeError as e:
           logger.error(f"JSON decode error in rules file: {e}")
           # Backup corrupted file
           backup_file = self.storage_file.with_suffix('.corrupted')
           self.storage_file.rename(backup_file)
           logger.warning(f"Backed up corrupted file to {backup_file}")
       except Exception as e:
           logger.error(f"Error loading exit rules: {e}", exc_info=True)
   ```

5. **Add Retry Logic for Position Modifications:**
   ```python
   def _modify_position_sl(self, ticket: int, new_sl: float, current_tp: float, max_retries: int = 3) -> bool:
       """Modify position SL with retry logic"""
       import time
       
       for attempt in range(max_retries):
           try:
               # ... existing modification code ...
               if success:
                   return True
               
               # If failed, wait before retry (exponential backoff)
               if attempt < max_retries - 1:
                   wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                   logger.debug(f"Retry {attempt + 1}/{max_retries} for ticket {ticket} in {wait_time}s")
                   time.sleep(wait_time)
           except Exception as e:
               logger.warning(f"Attempt {attempt + 1} failed for ticket {ticket}: {e}")
               if attempt < max_retries - 1:
                   time.sleep((2 ** attempt) * 0.5)
       
       logger.error(f"Failed to modify position {ticket} after {max_retries} attempts")
       return False
   ```

6. **Add Health Check Method:**
   ```python
   def get_health_status(self) -> Dict[str, Any]:
       """Get system health status"""
       status = {
           "status": "healthy",
           "active_rules": len(self.rules),
           "atr_circuit_breakers": {},
           "cache_status": {},
           "errors": []
       }
       
       # Check ATR circuit breakers
       for symbol, timestamp in self._atr_circuit_breaker_timestamps.items():
           time_since_open = time.time() - timestamp
           status["atr_circuit_breakers"][symbol] = {
               "open": True,
               "time_since_open": time_since_open,
               "will_reset_in": max(0, self._atr_circuit_breaker_timeout - time_since_open)
           }
       
       # Check Advanced provider cache
       if self.advanced_provider and hasattr(self.advanced_provider, '_cache'):
           with self.advanced_provider._cache_lock:
               status["cache_status"] = {
                   "size": len(self.advanced_provider._cache),
                   "max_size": getattr(self.advanced_provider, '_max_cache_size', 50)
               }
       
       # Check for errors
       if status["atr_circuit_breakers"]:
           status["status"] = "degraded"
           status["errors"].append("ATR circuit breakers open")
       
       return status
   ```

**Integration Issues:**
- ✅ Trade registry may not be available - graceful fallback
- ✅ Thread safety prevents race conditions
- ✅ Circuit breaker prevents cascading failures
- ✅ JSON validation prevents crashes from corrupted files

**Testing:**
- Verify conflict prevention works with Universal Manager
- Verify conflict prevention works with DTMS
- Verify cache thread safety under concurrent access
- Verify circuit breaker opens after repeated failures
- Verify circuit breaker resets after timeout
- Verify JSON validation catches corrupted files
- Verify retry logic works for transient failures
- Verify health check returns accurate status

**Estimated Time:** 4 hours

**Benefits:**
- ✅ **Conflict Prevention**: No conflicts with other systems
- ✅ **Thread Safety**: No race conditions in cache
- ✅ **Resilience**: Circuit breaker prevents cascading failures
- ✅ **Data Integrity**: JSON validation prevents crashes
- ✅ **Reliability**: Retry logic handles transient failures
- ✅ **Observability**: Health check enables monitoring

---

## 📝 Implementation Notes

### **Breaking Changes**
- `_trailing_gates_pass()` return type changes (but backward compatible with `return_details=False`)
- `_calculate_advanced_triggers()` now requires `symbol` parameter
- `_trail_stop_atr()` now accepts optional `trailing_multiplier` parameter

### **Migration Path**
- Existing rules in `intelligent_exits.json` will work with defaults
- `trailing_multiplier` defaults to 1.5 for existing rules
- RMAG threshold defaults to 2.0 for unknown symbols
- No data migration needed

### **Feature Flags (Optional)**
Consider adding feature flags for gradual rollout:
```python
# config/settings.py
ENABLE_ASSET_SPECIFIC_RMAG = True
ENABLE_TRAILING_GATES_TIERED = True
ENABLE_BREAKEVEN_BUFFER = True
ENABLE_ADVANCED_PROVIDER_REFRESH = True
```

---

## ✅ Sign-Off Checklist

Before deployment:
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] All end-to-end tests passing
- [ ] Manual testing complete
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Feature flags added (if needed)
- [ ] Rollback plan prepared
- [ ] Monitoring alerts configured

