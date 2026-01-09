# Adaptive Micro-Scalp Strategy Plan - Integration & Logic Review

**Date:** 2025-12-03  
**Reviewer:** AI Assistant  
**Status:** Issues Identified - Requires Updates

---

## 🔴 Critical Integration Issues

### 1. Missing Data Access Dependencies

**Issue:** `MicroScalpRegimeDetector` requires M5 and M15 data, but these are not included in the snapshot or dependencies.

**Current State:**
- `MicroScalpEngine._build_snapshot()` only includes M1 candles
- Snapshot does not include M5 candles (needed for balanced zone MTF confirmation)
- Snapshot does not include M15 candles (needed for range detection and trend checking)
- Snapshot does not include VWAP std (needed for deviation calculation)

**Impact:**
- Balanced zone detection cannot perform M1-M5 multi-timeframe confirmation
- Range detection cannot use M15 data for trend checking
- VWAP reversion detection cannot calculate deviation in standard deviations

**Solution:**
1. **Enhance `_build_snapshot()` to include M5/M15 data:**
   ```python
   # In MicroScalpEngine._build_snapshot()
   # Add MultiTimeframeStreamer dependency
   if self.streamer:  # MultiTimeframeStreamer
       m5_candles = self.streamer.get_candles(symbol_norm, 'M5', count=10)
       m15_candles = self.streamer.get_candles(symbol_norm, 'M15', count=20)
   else:
       m5_candles = None
       m15_candles = None
   
   # Get VWAP std from M1MicrostructureAnalyzer
   if self.m1_analyzer:
       analysis = self.m1_analyzer.analyze_microstructure(symbol_norm, candles)
       vwap_std = analysis.get('vwap', {}).get('std', 0.0)
   else:
       vwap_std = None
   
   snapshot = {
       # ... existing fields ...
       'm5_candles': m5_candles,  # NEW
       'm15_candles': m15_candles,  # NEW
       'vwap_std': vwap_std,  # NEW
   }
   ```

2. **Update `MicroScalpEngine.__init__()` to accept `streamer`:**
   ```python
   def __init__(self, config_path: str = "config/micro_scalp_config.json",
                mt5_service: Optional[MT5Service] = None,
                m1_fetcher: Optional[M1DataFetcher] = None,
                streamer: Optional[MultiTimeframeStreamer] = None,  # NEW
                m1_analyzer=None,
                session_manager=None,
                btc_order_flow=None):
       # ... existing code ...
       self.streamer = streamer  # NEW
   ```

3. **Update `MicroScalpRegimeDetector.__init__()` to accept `streamer` and `news_service`:**
   ```python
   def __init__(self, config, m1_analyzer, vwap_filter, range_detector, 
                volatility_filter, streamer=None, news_service=None, mt5_service=None):
       # ... existing code ...
       self.streamer = streamer  # NEW: For M5/M15 data
       self.news_service = news_service  # NEW: For balanced zone news check
       self.mt5_service = mt5_service  # NEW: For M15 trend checking
   ```

---

### 2. Data Format Mismatch: RangeBoundaryDetector

**Issue:** `RangeBoundaryDetector.detect_range()` expects `candles_df: pd.DataFrame`, but snapshot provides `candles: List[Dict]`.

**Current State:**
- Plan shows: `candles_df=self._candles_to_df(candles)` (helper method not defined)
- `RangeBoundaryDetector` requires DataFrame with datetime index and OHLC columns

**Impact:**
- Range detection will fail without proper DataFrame conversion
- Missing helper method `_candles_to_df()` implementation

**Solution:**
1. **Implement `_candles_to_df()` in `MicroScalpRegimeDetector`:**
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
   ```

2. **Update range detection call:**
   ```python
   # In _detect_range()
   m15_candles = snapshot.get('m15_candles', [])
   if m15_candles:
       m15_df = self._candles_to_df(m15_candles)
   else:
       m15_df = None
   
   range_structure = self.range_detector.detect_range(
       symbol=symbol,
       timeframe="M15",
       range_type="dynamic",
       candles_df=m15_df,  # Use M15 DataFrame
       vwap=snapshot.get('vwap'),
       atr=snapshot.get('atr1')
   )
   ```

---

### 3. Missing M5 Candle Fetching Implementation

**Issue:** Plan references `_fetch_m5_candles()` but method is not defined.

**Current State:**
- `_check_compression_block_mtf()` calls `self._fetch_m5_candles(symbol, count=10)`
- Method does not exist in plan or codebase

**Impact:**
- Balanced zone detection will fail when trying to fetch M5 candles

**Solution:**
1. **Implement `_fetch_m5_candles()` in `MicroScalpRegimeDetector`:**
   ```python
   def _fetch_m5_candles(self, symbol: str, count: int = 10) -> Optional[List[Dict[str, Any]]]:
       """Fetch M5 candles from streamer or snapshot"""
       # First try snapshot (if available)
       if hasattr(self, '_current_snapshot') and self._current_snapshot:
           m5_candles = self._current_snapshot.get('m5_candles')
           if m5_candles:
               return m5_candles[:count] if len(m5_candles) >= count else m5_candles
       
       # Fallback to streamer
       if self.streamer:
           try:
               m5_candles_objects = self.streamer.get_candles(symbol, 'M5', limit=count)
               if m5_candles_objects:
                   # Convert Candle objects to dicts
                   return [self._candle_to_dict(c) for c in m5_candles_objects]
           except Exception as e:
               logger.debug(f"Error fetching M5 candles from streamer: {e}")
       
       return None
   
   def _candle_to_dict(self, candle) -> Dict[str, Any]:
       """Convert Candle object to dict"""
       if hasattr(candle, 'to_dict'):
           return candle.to_dict()
       elif hasattr(candle, '__dict__'):
           return candle.__dict__
       else:
           # Assume it's already a dict
           return candle
   ```

2. **Alternative: Use snapshot data (preferred):**
   - Pass snapshot to `_detect_balanced_zone()` method
   - Extract M5 candles from snapshot directly
   - No need for separate fetching method

---

### 4. Missing M15 Trend Checking Implementation

**Issue:** Plan references `_check_m15_trend()` but method is not defined.

**Current State:**
- Range detection calls `m15_trend = self._check_m15_trend(symbol)`
- Method does not exist

**Impact:**
- Range detection cannot check if M15 trend is neutral (required condition)

**Solution:**
1. **Implement `_check_m15_trend()` in `MicroScalpRegimeDetector`:**
   ```python
   def _check_m15_trend(self, symbol: str) -> str:
       """Check M15 trend (should be neutral for range trading)"""
       # Get M15 candles from snapshot
       if hasattr(self, '_current_snapshot') and self._current_snapshot:
           m15_candles = self._current_snapshot.get('m15_candles', [])
           if m15_candles and len(m15_candles) >= 20:
               m15_df = self._candles_to_df(m15_candles)
               if m15_df is not None:
                   # Calculate ADX or use structure detection
                   # For simplicity, use structure detection
                   try:
                       from domain.market_structure import label_structure
                       structure = label_structure(m15_df, lookback=10)
                       trend = structure.get('trend', 'UNKNOWN')
                       
                       # Convert to neutral check
                       if trend in ['UP', 'DOWN']:
                           # Check ADX to determine if trend is strong
                           # If ADX < threshold, consider it neutral
                           # For now, return trend and let caller decide
                           return trend
                       else:
                           return 'NEUTRAL'
                   except Exception as e:
                       logger.debug(f"Error checking M15 trend: {e}")
       
       # Fallback: Use MT5Service to get M15 bars and calculate ADX
       if self.mt5_service:
           try:
               m15_bars = self.mt5_service.get_bars(symbol, 'M15', 50)
               if m15_bars is not None and len(m15_bars) >= 20:
                   # Calculate ADX
                   adx = self._calculate_adx(m15_bars)
                   max_adx = self.config.get('regime_detection', {}).get('range_scalp', {}).get('m15_trend_max_adx', 20)
                   if adx and adx < max_adx:
                       return 'NEUTRAL'
                   else:
                       return 'TRENDING'
           except Exception as e:
               logger.debug(f"Error checking M15 trend via MT5: {e}")
       
       return 'UNKNOWN'  # Default to unknown if can't determine
   
   def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> Optional[float]:
       """Calculate ADX from DataFrame"""
       # Implementation needed - can use existing ADX calculation from codebase
       # Or use ta-lib if available
       pass
   ```

2. **Alternative: Use existing structure detection:**
   - Leverage `domain.market_structure.label_structure()` which already exists
   - Check if trend is 'RANGE' or if ADX is low

---

### 5. Missing News Service Integration

**Issue:** Balanced zone detection requires news blackout check, but `NewsService` is not passed to `MicroScalpRegimeDetector`.

**Current State:**
- Plan shows news check in balanced zone: `"No news incoming (<15 min)"`
- `MicroScalpRegimeDetector.__init__()` does not accept `news_service`
- `MicroScalpEngine` does not pass `news_service` to regime detector

**Impact:**
- Balanced zone detection cannot check for news blackout
- May trade during high-impact news events

**Solution:**
1. **Update `MicroScalpEngine.__init__()` to accept and pass `news_service`:**
   ```python
   def __init__(self, config_path: str = "config/micro_scalp_config.json",
                mt5_service: Optional[MT5Service] = None,
                m1_fetcher: Optional[M1DataFetcher] = None,
                streamer: Optional[MultiTimeframeStreamer] = None,
                m1_analyzer=None,
                session_manager=None,
                btc_order_flow=None,
                news_service=None):  # NEW
       # ... existing code ...
       self.news_service = news_service  # NEW
   ```

2. **Update regime detector initialization:**
   ```python
   self.regime_detector = MicroScalpRegimeDetector(
       config=self.config,
       m1_analyzer=m1_analyzer,
       vwap_filter=self.vwap_filter,
       range_detector=RangeBoundaryDetector(self.config),
       volatility_filter=self.volatility_filter,
       streamer=streamer,  # NEW
       news_service=news_service,  # NEW
       mt5_service=mt5_service  # NEW
   )
   ```

3. **Implement news check in balanced zone detection:**
   ```python
   # In _detect_balanced_zone()
   # Check news blackout
   news_blackout_minutes = self.config.get('regime_detection', {}).get('balanced_zone', {}).get('news_blackout_minutes', 15)
   news_ok = True
   if self.news_service:
       try:
           # Check if news is incoming within blackout window
           from datetime import datetime, timedelta
           now = datetime.utcnow()
           blackout_end = now + timedelta(minutes=news_blackout_minutes)
           
           # Check for macro news
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
       return {'detected': False, 'confidence': 0, 'reason': 'news_blackout'}
   ```

---

## 🟡 Logic Issues

### 6. Strategy Router Confidence Threshold Inconsistency

**Issue:** Strategy router uses global `min_confidence` from config, but each detection method returns its own threshold.

**Current State:**
- Router code: `min_confidence = self.config.get('regime_detection', {}).get('min_confidence', 60)`
- But VWAP reversion returns: `min_confidence_threshold: 70`
- Range scalp returns: `min_confidence_threshold: 55`
- Balanced zone returns: `min_confidence_threshold: 65`

**Impact:**
- Router may reject valid regimes if using wrong threshold
- Inconsistent behavior between detection and routing

**Solution:**
1. **Use strategy-specific threshold from detection result:**
   ```python
   def select_strategy(self, snapshot, regime_result):
       regime = regime_result.get('regime', 'UNKNOWN')
       confidence = regime_result.get('confidence', 0)
       
       # Use strategy-specific threshold from detection result
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

---

### 7. Multiple Regime Detection Priority Logic

**Issue:** Plan does not specify what happens if multiple regimes are detected simultaneously.

**Current State:**
- `_detect_regime_fresh()` should check all three regimes
- But plan doesn't show how to handle multiple detections
- Priority ordering is in router, but detection should only return one regime

**Impact:**
- Unclear which regime wins if multiple are detected
- May miss higher-priority opportunities

**Solution:**
1. **Implement priority-based regime selection in `_detect_regime_fresh()`:**
   ```python
   def _detect_regime_fresh(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
       """Perform fresh regime detection (uncached)"""
       # Check all regimes
       vwap_result = self._detect_vwap_reversion(snapshot)
       range_result = self._detect_range(snapshot)
       balanced_result = self._detect_balanced_zone(snapshot)
       
       # Priority ordering: VWAP Reversion > Range > Balanced Zone
       # Select highest priority detected regime
       candidates = []
       
       if vwap_result.get('detected') and vwap_result.get('confidence', 0) >= 70:
           candidates.append(('VWAP_REVERSION', vwap_result))
       
       if range_result.get('detected') and range_result.get('confidence', 0) >= 55:
           candidates.append(('RANGE', range_result))
       
       if balanced_result.get('detected') and balanced_result.get('confidence', 0) >= 65:
           candidates.append(('BALANCED_ZONE', balanced_result))
       
       if not candidates:
           return {
               'regime': 'UNKNOWN',
               'confidence': 0,
               'characteristics': {},
               'strategy_hint': 'edge_based'
           }
       
       # Select highest priority (first in list = highest priority)
       selected_regime, selected_result = candidates[0]
       
       return {
           'regime': selected_regime,
           'confidence': selected_result.get('confidence', 0),
           'characteristics': selected_result,
           'strategy_hint': selected_regime.lower().replace('_', '_'),
           'min_confidence_threshold': selected_result.get('min_confidence_threshold', 60)
       }
   ```

---

### 8. Cache Invalidation Logic Missing

**Issue:** Cache consistency check doesn't handle regime changes properly.

**Current State:**
- Cache requires 2+ bars with same regime
- But what if regime legitimately changes? Cache will block new regime
- No cache expiration or invalidation logic

**Impact:**
- System may stick to old regime even when market conditions change
- Delayed adaptation to market regime shifts

**Solution:**
1. **Add cache expiration and change detection:**
   ```python
   def _get_cached_regime(self, symbol: str) -> Optional[Dict[str, Any]]:
       """Get cached regime from rolling memory (3-bar)"""
       if symbol not in self.regime_cache:
           return None
       
       cache = self.regime_cache[symbol]
       if len(cache) < 2:
           return None
       
       # Check if cache is stale (older than 3 bars = 3 minutes for M1)
       # For now, assume cache is fresh if it exists
       
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
   ```

2. **Add timestamp to cache entries for expiration:**
   ```python
   def _update_regime_cache(self, symbol: str, regime_result: Dict[str, Any]):
       """Update rolling regime cache (3-bar memory)"""
       if symbol not in self.regime_cache:
           self.regime_cache[symbol] = []
       
       # Add timestamp
       from datetime import datetime
       regime_result['cache_timestamp'] = datetime.now()
       
       cache = self.regime_cache[symbol]
       cache.append(regime_result)
       
       # Keep only last N entries
       if len(cache) > self.cache_size:
           cache.pop(0)
       
       # Invalidate cache if regime changed (optional - for faster adaptation)
       if len(cache) >= 2:
           prev_regime = cache[-2].get('regime')
           curr_regime = cache[-1].get('regime')
           if prev_regime != curr_regime:
               logger.debug(f"Regime changed: {prev_regime} -> {curr_regime}, cache may be invalidated")
               # Optionally clear cache on regime change for faster adaptation
               # cache.clear()  # Uncomment if needed
   ```

---

### 9. VWAP Slope Calculation Location Unclear

**Issue:** Plan mentions VWAP slope calculation but doesn't specify where it's implemented.

**Current State:**
- Plan shows: `vwap_slope = self._calculate_vwap_slope(candles, vwap)`
- Method not defined
- Should it be in `VWAPMicroFilter` or `MicroScalpRegimeDetector`?

**Impact:**
- VWAP reversion detection will fail
- Missing implementation

**Solution:**
1. **Implement in `MicroScalpRegimeDetector` (regime-specific logic):**
   ```python
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
   ```

---

### 10. ATR(14) Calculation Verification

**Issue:** Plan mentions ATR(14) for stability check, but `MicroScalpVolatilityFilter` only has `calculate_atr1()`.

**Current State:**
- Plan shows: `atr_stable = self._check_atr_stability(candles, atr1)`
- Method should check ATR(14) stable or rising
- `MicroScalpVolatilityFilter` doesn't have ATR(14) calculation

**Impact:**
- ATR stability check will fail
- VWAP reversion detection incomplete

**Solution:**
1. **Add ATR(14) calculation to `MicroScalpVolatilityFilter`:**
   ```python
   def calculate_atr14(self, candles: List[Dict[str, Any]]) -> float:
       """Calculate ATR(14) from M1 candles"""
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

2. **Implement `_check_atr_stability()` in `MicroScalpRegimeDetector`:**
   ```python
   def _check_atr_stability(self, candles: List[Dict[str, Any]], atr1: Optional[float]) -> bool:
       """Check if ATR(14) is stable or rising (not collapsing)"""
       if len(candles) < 20:
           return False
       
       # Calculate ATR(14) for recent and previous periods
       recent_candles = candles[-14:]
       previous_candles = candles[-28:-14] if len(candles) >= 28 else candles[:14]
       
       recent_atr14 = self.volatility_filter.calculate_atr14(recent_candles)
       previous_atr14 = self.volatility_filter.calculate_atr14(previous_candles)
       
       if previous_atr14 == 0:
           return recent_atr14 > 0  # At least some volatility
       
       # Check if ATR is stable (within 10% of previous) or rising
       atr_ratio = recent_atr14 / previous_atr14
       return 0.9 <= atr_ratio <= 1.5  # Stable or rising (not collapsing)
   ```

---

## 🟠 Medium Priority Issues

### 11. Strategy Checker Factory Missing Error Handling

**Issue:** `_get_strategy_checker()` factory method doesn't handle import errors or initialization failures.

**Current State:**
- Factory method assumes all imports succeed
- No error handling if checker initialization fails

**Impact:**
- System may crash if strategy checker module has errors
- No graceful degradation

**Solution:**
1. **Add error handling:**
   ```python
   def _get_strategy_checker(self, strategy_name: str) -> BaseStrategyChecker:
       """Get or create strategy-specific checker"""
       if strategy_name in self.strategy_checkers:
           return self.strategy_checkers[strategy_name]
       
       try:
           if strategy_name == 'vwap_reversion':
               from infra.micro_scalp_strategies.vwap_reversion_checker import VWAPReversionChecker
               checker = VWAPReversionChecker(...)
           # ... other strategies ...
           else:  # edge_based (fallback)
               from infra.micro_scalp_strategies.edge_based_checker import EdgeBasedChecker
               checker = EdgeBasedChecker(...)
           
           self.strategy_checkers[strategy_name] = checker
           return checker
       except ImportError as e:
           logger.error(f"Failed to import strategy checker {strategy_name}: {e}")
           # Fallback to edge-based
           return self._get_strategy_checker('edge_based')
       except Exception as e:
           logger.error(f"Failed to initialize strategy checker {strategy_name}: {e}", exc_info=True)
           # Fallback to edge-based
           return self._get_strategy_checker('edge_based')
   ```

---

### 12. Snapshot Enhancement Not Documented in Integration

**Issue:** Plan doesn't show how `MicroScalpMonitor` passes `streamer` to `MicroScalpEngine`.

**Current State:**
- `MicroScalpMonitor` has `streamer` available
- But `MicroScalpEngine` initialization doesn't show `streamer` parameter
- Monitor creates engine but doesn't pass streamer

**Impact:**
- Engine won't have access to M5/M15 data
- Regime detection will fail

**Solution:**
1. **Update `MicroScalpMonitor` to pass `streamer` to engine:**
   ```python
   # In MicroScalpMonitor.__init__() or where engine is created
   # Engine should be created with streamer
   # Check how engine is currently initialized in monitor
   ```

2. **Document integration point:**
   - Add note in Phase 4 that `MicroScalpMonitor` must pass `streamer` to engine
   - Update engine initialization signature

---

### 13. VWAP Reversion Entry Logic Issue

**Issue:** Entry price calculation uses `last_candle['high']` for BUY, but this may have already been broken.

**Current State:**
- Plan shows: `entry_price = last_candle['high']  # Break of high`
- But if price already broke high, entry is too late
- Should wait for next candle or use current price

**Impact:**
- Late entries on VWAP reversions
- May miss optimal entry point

**Solution:**
1. **Clarify entry logic:**
   ```python
   # Entry: Break of signal candle high/low
   last_candle = candles[-1]
   if direction == 'BUY':
       # Wait for break of signal candle high
       # If current price already above high, use current price
       signal_high = last_candle['high']
       entry_price = max(current_price, signal_high)  # Use higher of current or signal high
   else:  # SELL
       signal_low = last_candle['low']
       entry_price = min(current_price, signal_low)  # Use lower of current or signal low
   ```

---

### 14. Range Scalp SL Calculation Error

**Issue:** SL calculation for range scalp has incorrect logic.

**Current State:**
- Plan shows: `sl_distance = abs(sweep_low - current_price) * 1.15`
- But `sweep_low` is below `current_price`, so `abs(sweep_low - current_price)` is positive
- Multiplying by 1.15 makes SL even further away (wrong direction)

**Impact:**
- SL placed incorrectly
- Risk management broken

**Solution:**
1. **Fix SL calculation:**
   ```python
   if near_edge == 'low':
       direction = 'BUY'
       entry_price = current_price
       sweep_low = min(c.get('low', current_price) for c in snapshot['candles'][-5:])
       # SL: 0.15-0.20% beyond sweep (below sweep)
       if symbol.upper().startswith('BTC'):
           # Distance from entry to sweep
           distance_to_sweep = entry_price - sweep_low
           # Add 15% buffer beyond sweep
           sl_distance = distance_to_sweep * 1.15
           sl = entry_price - sl_distance  # SL below entry
       else:  # XAU
           sl = entry_price - 3  # 3-6 pts below entry
   ```

---

### 15. Balanced Zone News Check Timing

**Issue:** News check happens in detection, but should also happen in strategy checker validation.

**Current State:**
- News check in `_detect_balanced_zone()` (regime detection)
- But news may arrive between detection and execution
- Strategy checker should re-check news

**Impact:**
- May execute trades during news even if detected before news

**Solution:**
1. **Add news check to Balanced Zone Checker Layer 1:**
   ```python
   # In BalancedZoneChecker._check_pre_trade_filters()
   # Check news blackout
   news_blackout_minutes = self.config.get('regime_detection', {}).get('balanced_zone', {}).get('news_blackout_minutes', 15)
   if self.news_service:
       # Re-check news (conditions may have changed since regime detection)
       macro_blackout = self.news_service.is_blackout(category="macro")
       if macro_blackout:
           return VolatilityFilterResult(
               passed=False,
               reasons=[f"News blackout active (macro)"]
           )
   ```

---

## 🔵 Minor Issues

### 16. Missing VWAP Std in Snapshot

**Issue:** VWAP std is calculated but not included in snapshot.

**Solution:**
- Already addressed in Issue #1 (snapshot enhancement)

### 17. Configuration Duplication

**Issue:** Confidence thresholds are defined in both `regime_detection.strategy_confidence_thresholds` and in each detection method.

**Solution:**
- Use config values in detection methods instead of hardcoding
- Single source of truth

### 18. Missing Bollinger Band Calculation

**Issue:** `_check_bb_compression()` references Bollinger Band width but calculation not shown.

**Solution:**
- Implement BB width calculation or use existing indicator bridge
- Add to helper methods

---

## 📋 Summary of Required Changes

### Critical (Must Fix Before Implementation):
1. ✅ Add `streamer`, `news_service`, `mt5_service` to `MicroScalpRegimeDetector` dependencies
2. ✅ Enhance `_build_snapshot()` to include M5/M15 candles and VWAP std
3. ✅ Implement `_candles_to_df()` helper method
4. ✅ Implement `_fetch_m5_candles()` or use snapshot data
5. ✅ Implement `_check_m15_trend()` method
6. ✅ Implement `_calculate_vwap_slope()` method
7. ✅ Add ATR(14) calculation to `MicroScalpVolatilityFilter`
8. ✅ Fix strategy router to use detection-specific confidence thresholds
9. ✅ Fix range scalp SL calculation logic
10. ✅ Implement multiple regime priority selection in `_detect_regime_fresh()`

### High Priority (Should Fix):
11. ✅ Add cache invalidation logic
12. ✅ Add error handling to strategy checker factory
13. ✅ Fix VWAP reversion entry price logic
14. ✅ Add news check to Balanced Zone Checker (not just detection)

### Medium Priority (Nice to Have):
15. ✅ Use config values instead of hardcoded thresholds
16. ✅ Implement BB compression check
17. ✅ Document all integration points clearly

---

## 🔧 Recommended Implementation Order

1. **Phase 0.5: Data Access Enhancement** (NEW PHASE)
   - Enhance snapshot building
   - Add M5/M15 data access
   - Add VWAP std to snapshot

2. **Phase 1: Regime Detection** (with fixes)
   - Implement all helper methods
   - Fix data access issues
   - Add news service integration

3. **Phase 2: Strategy Router** (with fixes)
   - Use detection-specific thresholds
   - Add error handling

4. **Continue with remaining phases...**

---

**End of Review**

