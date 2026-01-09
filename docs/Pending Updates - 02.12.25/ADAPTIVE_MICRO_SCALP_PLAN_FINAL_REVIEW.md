# Adaptive Micro-Scalp Strategy Plan - Final Review

**Date:** 2025-12-03  
**Reviewer:** AI Assistant  
**Status:** ✅ All Errors Fixed in Plan

---

## 🔴 Critical Logic Errors

### 1. CHOCH Data Access Error

**Issue:** Code accesses CHOCH from wrong dictionary location.

**Current (WRONG):**
```python
analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
structure = analysis.get('structure', {})
choch_detected = structure.get('choch_detected', False)  # ❌ WRONG
choch_type = structure.get('choch_type', '')  # ❌ WRONG
```

**Actual Structure:**
- `analyze_microstructure()` returns:
  - `analysis['structure']` - Structure analysis (no CHOCH)
  - `analysis['choch_bos']` - CHOCH/BOS detection results

**Fix:**
```python
analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
choch_bos = analysis.get('choch_bos', {})
choch_detected = choch_bos.get('has_choch', False) or choch_bos.get('choch_confirmed', False)
choch_type = choch_bos.get('direction', '')  # 'BULLISH' or 'BEARISH'
```

**Locations to Fix:**
- `_get_direction_from_choch()` in VWAPReversionChecker
- `_quick_confluence_check()` in MicroScalpStrategyRouter

---

### 2. ATR14 Memoization Inconsistency

**Issue:** Two different method signatures for `_check_atr_stability` and `_check_atr_dropping`.

**Current State:**
- Phase 1 implementation: `_check_atr_stability(candles, atr1: Optional[float])`
- Phase 9 implementation: `_check_atr_stability(candles, snapshot: Dict[str, Any])`

**Problem:** Phase 1 version doesn't use memoized ATR14, causing recomputation.

**Fix:** Update Phase 1 implementations to use snapshot:

```python
# In Phase 1 helper methods
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

**Update Call Sites:**
- `_detect_vwap_reversion()`: Change `self._check_atr_stability(candles, atr1)` to `self._check_atr_stability(candles, snapshot)`
- `_detect_balanced_zone()`: Change `self._check_atr_dropping(candles, atr1)` to `self._check_atr_dropping(candles, snapshot)`

---

### 3. Volume Spike Method Duplication

**Issue:** Two implementations of `_check_volume_spike()` - one with multiplier, one with Z-score.

**Problem:** Phase 9 Z-score version should replace or conditionally use multiplier version.

**Fix:** Make volume normalization configurable:

```python
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
        return False
    
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
```

---

### 4. Quick Confluence Check Timing Error

**Issue:** `_quick_confluence_check()` accesses `snapshot.get('regime_result')` but `regime_result` is added to snapshot AFTER detection in engine.

**Current (WRONG):**
```python
def _quick_confluence_check(self, snapshot: Dict[str, Any], regime: str) -> float:
    deviation_sigma = snapshot.get('regime_result', {}).get('characteristics', {}).get('deviation_sigma', 0)
    # ❌ regime_result not in snapshot yet
```

**Fix:** Pass `regime_result` as parameter or access from `regime_result` directly:

```python
# In select_strategy()
def select_strategy(self, snapshot, regime_result):
    # ... existing code ...
    
    if confluence_pre_check_enabled:
        quick_confluence = self._quick_confluence_check(snapshot, regime_result)  # Pass regime_result
        # ... rest of code ...

def _quick_confluence_check(self, snapshot: Dict[str, Any], regime_result: Dict[str, Any]) -> float:
    """Quick confluence estimation using regime_result"""
    regime = regime_result.get('regime', 'UNKNOWN')
    characteristics = regime_result.get('characteristics', {})
    
    if regime == 'VWAP_REVERSION':
        deviation_sigma = characteristics.get('deviation_sigma', 0)
        # Get CHOCH from snapshot's M1 analysis (not from regime_result)
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
        else:
            choch_detected = False
        
        score = 0.0
        if deviation_sigma >= 2.0:
            score += 2.5
        if choch_detected:
            score += 2.0
        return score
    
    elif regime == 'RANGE':
        range_structure = characteristics.get('range_structure')
        near_edge = characteristics.get('near_edge')
        
        score = 0.0
        if range_structure and near_edge:
            score += 2.5
        if characteristics.get('range_respects', 0) >= 2:
            score += 2.0
        return score
    
    elif regime == 'BALANCED_ZONE':
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

---

### 5. EMA Calculation Method Location Error

**Issue:** `_calculate_ema()` is in `BalancedZoneChecker` but uses `self._candles_to_df()` which is in `MicroScalpRegimeDetector`.

**Problem:** `BalancedZoneChecker` doesn't have access to `_candles_to_df()`.

**Fix Options:**

**Option A:** Move `_candles_to_df()` to a shared utility module or base class.

**Option B:** Implement `_calculate_ema()` without DataFrame conversion:

```python
# In BalancedZoneChecker
def _calculate_ema(self, candles: List[Dict], period: int) -> Optional[float]:
    """Calculate EMA(period) from candles without DataFrame dependency"""
    if len(candles) < period:
        return None
    
    try:
        # Get closes
        closes = [c.get('close', 0) for c in candles[-period:]]
        
        if not closes or all(c == 0 for c in closes):
            return None
        
        # Calculate EMA manually
        multiplier = 2.0 / (period + 1)
        ema = closes[0]  # Start with first close
        
        for close in closes[1:]:
            ema = (close * multiplier) + (ema * (1 - multiplier))
        
        return ema
    except Exception as e:
        logger.debug(f"Error calculating EMA: {e}")
        return None
```

**Recommended:** Option B (simpler, no pandas dependency in checker).

---

### 6. _current_snapshot Usage Error

**Issue:** `_check_compression_block()` uses `self._current_snapshot` but it's only set in `_detect_regime_fresh()`.

**Problem:** If `_check_compression_block()` is called from other contexts, `_current_snapshot` might be None or stale.

**Fix:** Pass snapshot or atr1 as parameter:

```python
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
        
        if current_high < previous_high and current_low > previous_low:
            inside_count += 1
    
    # Also check for tight range (small candle bodies)
    if len(candles) >= 5 and atr1:
        recent_candles = candles[-5:]
        avg_range = sum(c.get('high', 0) - c.get('low', 0) for c in recent_candles) / len(recent_candles)
        
        if atr1 > 0:
            if avg_range < atr1 * 0.5:
                return True
    
    return inside_count >= 2

# Update call sites:
# In _check_compression_block_mtf():
m1_compression = self._check_compression_block(m1_candles, snapshot.get('atr1'))
m5_compression = self._check_compression_block(m5_dicts, snapshot.get('atr1'))
```

---

## 🟡 Implementation Errors

### 7. Missing Import Statements

**Issue:** Helper methods use `Optional`, `List`, `Dict` but imports not shown.

**Fix:** Add to top of `MicroScalpRegimeDetector`:

```python
from typing import Dict, Any, List, Optional
import logging
import statistics
import pandas as pd
```

---

### 8. Missing _detect_entry_type Method

**Issue:** `BalancedZoneChecker._check_location_filter()` calls `self._detect_entry_type(snapshot)` but method not defined.

**Fix:** Add method:

```python
def _detect_entry_type(self, snapshot: Dict[str, Any]) -> str:
    """Detect entry type (fade or breakout)"""
    candles = snapshot.get('candles', [])
    
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

---

### 9. Range Structure Type Mismatch

**Issue:** `_create_range_from_pdh_pdl()` returns `RangeStructure` but might not match expected type.

**Fix:** Verify `RangeStructure` import and ensure all required fields are set:

```python
from infra.range_boundary_detector import RangeStructure

def _create_range_from_pdh_pdl(self, pdh: float, pdl: float, snapshot: Dict[str, Any]) -> Optional[RangeStructure]:
    """Create RangeStructure from PDH/PDL"""
    if not pdh or not pdl or pdh <= pdl:
        return None
    
    try:
        vwap = snapshot.get('vwap', (pdh + pdl) / 2)
        atr = snapshot.get('atr1', (pdh - pdl) / 3)
        
        # Verify RangeStructure constructor signature
        return RangeStructure(
            range_type="daily",
            range_high=pdh,
            range_low=pdl,
            range_mid=(pdh + pdl) / 2,
            range_width=pdh - pdl,
            range_width_atr=(pdh - pdl) / atr if atr > 0 else 0,
            touch_count=0,
            created_at=snapshot.get('timestamp')
        )
    except Exception as e:
        logger.debug(f"Error creating range from PDH/PDL: {e}")
        return None
```

---

### 10. Strategy Name Access in Confluence Calculation

**Issue:** `_calculate_confluence_score()` uses `self.strategy_name` but base class might not have this attribute.

**Fix:** Add `strategy_name` to `BaseStrategyChecker`:

```python
class BaseStrategyChecker(MicroScalpConditionsChecker, ABC):
    def __init__(self, config, volatility_filter, vwap_filter, 
                 sweep_detector, ob_detector, spread_tracker,
                 m1_analyzer=None, session_manager=None, news_service=None,
                 strategy_name: str = None):  # NEW
        super().__init__(config, volatility_filter, vwap_filter,
                        sweep_detector, ob_detector, spread_tracker,
                        m1_analyzer, session_manager)
        self.news_service = news_service
        self.strategy_name = strategy_name  # NEW

# In each checker:
class VWAPReversionChecker(BaseStrategyChecker):
    def __init__(self, ...):
        super().__init__(..., strategy_name='vwap_reversion')
```

---

## 📋 Summary of Fixes Required

### Critical (Must Fix):
1. ✅ Fix CHOCH data access (use `choch_bos` not `structure`)
2. ✅ Fix ATR14 memoization (update Phase 1 methods to use snapshot)
3. ✅ Fix volume spike method (make configurable, not duplicate)
4. ✅ Fix quick confluence check (pass regime_result as parameter)
5. ✅ Fix EMA calculation (remove DataFrame dependency or move method)
6. ✅ Fix _current_snapshot usage (pass atr1 as parameter)

### High Priority:
7. ✅ Add missing imports
8. ✅ Add _detect_entry_type method
9. ✅ Verify RangeStructure type
10. ✅ Add strategy_name to BaseStrategyChecker

---

**End of Final Review**

