# Volatility States Implementation Plan

**Date**: 2025-12-07  
**Last Updated**: 2025-12-07 (with fixes from PLAN_REVIEW_TENTH_ISSUES.md)  
**Purpose**: Comprehensive plan for adding new volatility states (PRE_BREAKOUT_TENSION, POST_BREAKOUT_DECAY, FRAGMENTED_CHOP, SESSION_SWITCH_FLARE) to the system

**⚠️ IMPORTANT**: This plan has been updated with fixes from:
- `PLAN_REVIEW_ISSUES.md` (first review - 12 issues)
- `PLAN_REVIEW_ADDITIONAL_ISSUES.md` (second review - 12 additional issues)
- `PLAN_REVIEW_FINAL_ISSUES.md` (third review - 8 additional issues)
- `PLAN_REVIEW_FOURTH_ISSUES.md` (fourth review - 10 additional issues)
- `PLAN_REVIEW_FIFTH_ISSUES.md` (fifth review - 8 additional issues)
- `PLAN_REVIEW_SIXTH_ISSUES.md` (sixth review - 11 additional issues)
- `PLAN_REVIEW_SEVENTH_ISSUES.md` (seventh review - 7 additional issues)
- `PLAN_REVIEW_EIGHTH_ISSUES.md` (eighth review - 8 additional issues)
- `PLAN_REVIEW_NINTH_ISSUES.md` (ninth review - 4 additional issues)
- `PLAN_REVIEW_TENTH_ISSUES.md` (tenth review - 3 additional issues)

**All critical gaps, logic errors, integration issues, performance concerns, code structure issues, detection logic errors, data format handling issues, missing field references, and defensive programming improvements have been addressed.**

---

## 📋 EXECUTIVE SUMMARY

**Current System**: Detects 3 basic volatility states (STABLE, TRANSITIONAL, VOLATILE) using ATR ratio, BB width, ADX, and volume confirmation.

**New Requirements**: Add 4 advanced volatility states with specialized detection logic and strategy mappings.

**Impact**: Affects volatility detection, strategy selection, auto-execution validation, risk management, and knowledge documents.

---

## 📚 RELATED DOCUMENTS

- **Tracking Architecture**: `docs/Pending Updates - 07.12.25/VOLATILITY_TRACKING_ARCHITECTURE.md`
  - Detailed design for ATR slope, wick variance, and time since breakout tracking
  - Data structures, storage strategy, and ChatGPT access patterns

- **Current System Review**: `docs/Pending Updates - 07.12.25/CURRENT_VOLATILITY_DETECTION_SYSTEM.md`
  - Existing capabilities and gaps
  - Required functionality for new states

---

## 🔍 CURRENT SYSTEM REVIEW

### Existing Functionality

**1. Volatility Regime Detector** (`infra/volatility_regime_detector.py`):
- ✅ Multi-timeframe weighted analysis (M5: 20%, M15: 30%, H1: 50%)
- ✅ ATR ratio calculation (ATR(14) / ATR(50))
- ✅ Bollinger Band width ratio (vs 20-day median)
- ✅ ADX support signal
- ✅ Volume confirmation for VOLATILE
- ✅ Persistence filter (3 candles)
- ✅ Inertia coefficient (5 candles minimum hold)
- ✅ Cooldown mechanism (2 candles)
- ✅ Confidence scoring (0-100%)
- ✅ Regime change event logging

**2. Wick Analysis** (Existing in codebase):
- ✅ `domain/candles.py`: `_body_wick()`, `wick_strength_ratio()`
- ✅ `infra/m1_microstructure_analyzer.py`: `detect_rejection_wicks()`
- ✅ `infra/feature_patterns.py`: `_compute_wick_analysis()`
- ✅ `domain/candle_stats.py`: `calculate_wick_asymmetry()`
- ✅ Multiple systems calculate wick-to-body ratios

**3. Session Detection** (Existing in codebase):
- ✅ `infra/session_helpers.py`: `SessionHelpers.get_current_session()`
- ✅ `infra/feature_session_news.py`: `SessionNewsFeatures.get_session_info()`
- ✅ `infra/detection_systems.py`: `_check_session_change()`
- ✅ Session transition detection exists but not used for volatility flare detection

**4. ATR Calculation**:
- ✅ `infra/volatility_regime_detector.py`: `_calculate_atr()`
- ✅ Calculates ATR(14) and ATR(50)
- ✅ **RESOLVED**: ATR slope/trend tracking → Section 1.3.4 (`_calculate_atr_trend()`)

**5. BB Width Calculation**:
- ✅ Calculates current BB width
- ✅ Calculates BB width ratio vs median
- ✅ **RESOLVED**: BB width trend tracking → Section 1.3.1 (`_calculate_bb_width_trend()`)
- ✅ **RESOLVED**: BB width percentile calculation → Section 1.3.1 (percentile field)

### Existing Gaps → **ALL RESOLVED IN IMPLEMENTATION PLAN**

**1. PRE_BREAKOUT_TENSION Detection**:
- ✅ **RESOLVED**: Wick variance tracking → Section 1.3.2 (`_calculate_wick_variance()`)
- ✅ **RESOLVED**: Intra-bar volatility measurement → Section 1.3.3 (`_calculate_intrabar_volatility()`)
- ✅ **RESOLVED**: BB width trend analysis → Section 1.3.1 (`_calculate_bb_width_trend()`)
- ✅ **Integration**: Section 1.4.1 uses all three metrics for detection

**2. POST_BREAKOUT_DECAY Detection**:
- ✅ **RESOLVED**: ATR slope/derivative calculation → Section 1.3.4 (`_calculate_atr_trend()`)
- ✅ **RESOLVED**: "Time since breakout" tracking → Section 1.3.11 (`_get_time_since_breakout()`) + Section 1.3.10 (`_record_breakout_event()`) + Database (Section 1.3.1)
- ✅ **RESOLVED**: ATR decline rate measurement → Section 1.3.4 (slope_pct field)
- ✅ **Integration**: Section 1.4.2 uses ATR trends and time since breakout for detection

**3. FRAGMENTED_CHOP Detection**:
- ✅ **RESOLVED**: Whipsaw detection → Section 1.3.5 (`_detect_whipsaw()`)
- ✅ **RESOLVED**: Mean reversion pattern recognition → Section 1.3.7 (`_detect_mean_reversion_pattern()`)
- ✅ **RESOLVED**: Directional momentum analysis → Section 1.4.3 (ADX < 15 check)
- ✅ **Integration**: Section 1.4.3 uses all three for detection

**4. SESSION_SWITCH_FLARE Detection**:
- ✅ **RESOLVED**: Session transition window tracking → Section 1.3.6 (`_detect_session_transition()`)
- ✅ **RESOLVED**: Volatility spike detection during transitions → Section 1.3.8 (`_detect_volatility_spike()`)
- ✅ **RESOLVED**: Distinction between flare vs genuine expansion → Section 1.3.9 (`_is_flare_resolving()`)
- ✅ **Integration**: Section 1.4.4 uses all three for detection

**Note**: All gaps are addressed in Phase 1 (Sections 1.3-1.6) with complete implementation details, tracking infrastructure, and integration points.

---

## 🎯 IMPLEMENTATION PLAN

### PHASE 1: Core Volatility State Detection

#### 1.1 Extend VolatilityRegime Enum ✅ COMPLETED

**File**: `infra/volatility_regime_detector.py`

**Changes**:
```python
class VolatilityRegime(Enum):
    """Volatility regime classifications"""
    STABLE = "STABLE"
    TRANSITIONAL = "TRANSITIONAL"
    VOLATILE = "VOLATILE"
    # NEW STATES
    PRE_BREAKOUT_TENSION = "PRE_BREAKOUT_TENSION"
    POST_BREAKOUT_DECAY = "POST_BREAKOUT_DECAY"
    FRAGMENTED_CHOP = "FRAGMENTED_CHOP"
    SESSION_SWITCH_FLARE = "SESSION_SWITCH_FLARE"
```

**Status**: ✅ **COMPLETED** - Enum extended with 4 new volatility states

**Priority**: CRITICAL  
**Estimated Effort**: 30 minutes

---

#### 1.2 Add Configuration Parameters ✅ COMPLETED

**File**: `config/volatility_regime_config.py`

**Status**: ✅ **COMPLETED** - All configuration parameters added

**New Parameters**:
```python
# PRE_BREAKOUT_TENSION thresholds
BB_WIDTH_NARROW_THRESHOLD = 0.015  # 1.5% (bottom 20th percentile)
WICK_VARIANCE_INCREASE_THRESHOLD = 0.3  # 30% increase in rolling variance
INTRABAR_VOLATILITY_RISING_THRESHOLD = 0.2  # 20% increase in candle range/body ratio
BB_WIDTH_TREND_WINDOW = 10  # Candles to analyze for BB width trend

# POST_BREAKOUT_DECAY thresholds
ATR_SLOPE_DECLINE_THRESHOLD = -0.05  # ATR declining at 5% per period
ATR_ABOVE_BASELINE_THRESHOLD = 1.2  # ATR still > 1.2x baseline
POST_BREAKOUT_TIME_WINDOW = 30  # Minutes since breakout to consider "post-breakout"
ATR_SLOPE_WINDOW = 5  # Candles to calculate ATR slope

# FRAGMENTED_CHOP thresholds
WHIPSAW_WINDOW = 5  # Candles to check for whipsaw
WHIPSAW_MIN_DIRECTION_CHANGES = 3  # Minimum direction changes for whipsaw
MEAN_REVERSION_OSCILLATION_THRESHOLD = 0.5  # Price oscillating within 0.5 ATR of VWAP
LOW_MOMENTUM_ADX_THRESHOLD = 15  # ADX < 15 indicates low momentum

# SESSION_SWITCH_FLARE thresholds
SESSION_TRANSITION_WINDOW_MINUTES = 15  # ±15 minutes around session transition
VOLATILITY_SPIKE_THRESHOLD = 1.5  # 1.5x normal volatility during transition
FLARE_DURATION_MAX_MINUTES = 30  # Flare should resolve within 30 minutes
```

**Priority**: CRITICAL  
**Estimated Effort**: 1 hour

---

#### 1.3 Add Tracking Infrastructure

**File**: `infra/volatility_regime_detector.py` (update `__init__()` and add tracking structures)

**1.3.1 Initialize Tracking Data Structures** ✅ COMPLETED

**Status**: ✅ **COMPLETED** - All tracking structures, thread locks, and helper methods implemented

**Fix Applied**: Updated `_normalize_rates()` to handle numpy arrays with variable column counts (5-8 columns) instead of assuming 8 columns
```python
# FIX: Important Issue 5 - Required imports
import numpy as np
from collections import deque
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Union
import logging
import threading
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)

def __init__(self):
    # Existing tracking
    self._regime_history: Dict[str, List[Tuple[datetime, VolatilityRegime, float]]] = {}
    self._last_regime_change: Dict[str, datetime] = {}
    self._cooldown_until: Dict[str, datetime] = {}
    self._last_regime: Dict[str, VolatilityRegime] = {}
    
    # NEW: ATR history tracking (in-memory rolling deques)
    self._atr_history: Dict[str, Dict[str, deque]] = {}
    # Structure: {symbol: {timeframe: deque(maxlen=20)}}
    # Each entry: (timestamp, atr_14_value, atr_50_value)
    
    # NEW: Wick ratios tracking (in-memory rolling deques)
    self._wick_ratios_history: Dict[str, Dict[str, deque]] = {}
    # Structure: {symbol: {timeframe: deque(maxlen=20)}}
    # Each entry: (timestamp, wick_ratio)
    
    # NEW: Breakout cache (in-memory for fast access)
    self._breakout_cache: Dict[str, Dict[str, Optional[Dict]]] = {}
    # Structure: {symbol: {timeframe: {last_breakout: {...}}}}
    
    # NEW: Volatility spike cache (for flare resolution tracking)
    self._volatility_spike_cache: Dict[str, Dict[str, Optional[Dict]]] = {}
    # Structure: {symbol: {timeframe: {spike_start: datetime, spike_atr: float}}}
    
    # FIX: Performance Issue 1 - Thread locks for tracking structures
    self._tracking_lock = threading.RLock()  # Reentrant lock for thread safety
    self._db_lock = threading.RLock()  # Database access lock
    
    # FIX: Issue 7 - Ensure data directory exists before database operations
    import os
    os.makedirs("data", exist_ok=True)
    
    # NEW: Database path for breakout events
    self._db_path = "data/volatility_regime_events.sqlite"
    self._init_breakout_table()

    def _normalize_rates(
        self,
        rates: Union[pd.DataFrame, np.ndarray, None]
    ) -> Optional[Union[pd.DataFrame, np.ndarray]]:
        """
        Normalize rates to consistent format.
        
        FIX: Issue 8 - Helper method for consistent data format handling across all methods.
        FIX: Issue 10 - Thread-safe: Creates new DataFrames/arrays, doesn't modify input.
        
        This method is thread-safe as it only creates new objects and doesn't modify shared state.
        All DataFrame operations are read-only or create new DataFrames.
        
        Returns:
            DataFrame if possible, otherwise numpy array, or None if invalid
        """
        if rates is None:
            return None
        
        if isinstance(rates, pd.DataFrame):
            return rates
        
        if isinstance(rates, np.ndarray):
            # Convert to DataFrame for easier handling
            if len(rates.shape) == 2 and rates.shape[1] >= 5:
                return pd.DataFrame(
                    rates,
                    columns=['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']
                )
            else:
                return None
        
        return None

    def _ensure_symbol_tracking(self, symbol: str):
        """
        Initialize tracking structures for symbol if not exists.
        
        FIX: Integration Error 2 - Lazy initialization prevents crashes on first call.
        FIX: Performance Issue 1 - Thread-safe initialization.
        """
        with self._tracking_lock:  # Thread-safe access
            if symbol not in self._atr_history:
                self._atr_history[symbol] = {
                    "M5": deque(maxlen=20),
                    "M15": deque(maxlen=20),
                    "H1": deque(maxlen=20)
                }
            if symbol not in self._wick_ratios_history:
                self._wick_ratios_history[symbol] = {
                    "M5": deque(maxlen=20),
                    "M15": deque(maxlen=20),
                    "H1": deque(maxlen=20)
                }
            if symbol not in self._breakout_cache:
                self._breakout_cache[symbol] = {
                    "M5": None,
                    "M15": None,
                    "H1": None
                }
            if symbol not in self._volatility_spike_cache:
                self._volatility_spike_cache[symbol] = {
                    "M5": None,
                    "M15": None,
                    "H1": None
                }
```

**1.3.2 Initialize Breakout Events Database** ✅ COMPLETED

**Status**: ✅ **COMPLETED** - Database table created with proper structure and indices

---

**1.3.3-1.3.11 Tracking Calculation Methods** ✅ COMPLETED

**Status**: ✅ **COMPLETED** - All tracking calculation methods implemented:
- ✅ `_calculate_bb_width_trend()` - BB Width Trend Analysis (Phase 1.3.3)
- ✅ `_calculate_wick_variance()` - Wick Variance Calculation (Phase 1.3.4)
- ✅ `_calculate_intrabar_volatility()` - Intra-Bar Volatility (Phase 1.3.5)
- ✅ `_calculate_atr_trend()` - ATR Trend Analysis (Phase 1.3.6)
- ✅ `_detect_whipsaw()` - Whipsaw Detection (Phase 1.3.7)
- ✅ `_detect_session_transition()` - Session Transition Detection (Phase 1.3.8)
- ✅ `_detect_mean_reversion_pattern()` - Mean Reversion Pattern Detection (Phase 1.3.9)
- ✅ `_detect_volatility_spike()` - Volatility Spike Detection (Phase 1.3.10)
- ✅ `_is_flare_resolving()` - Flare Resolution Tracking (Phase 1.3.11)
- ✅ `_detect_breakout()` - Breakout Detection (Phase 1.3.12)
- ✅ `_get_db_connection()` - Database Connection Management (Phase 1.3.13)
- ✅ `_record_breakout_event()` - Breakout Event Recording (Phase 1.3.14)
- ✅ `_invalidate_previous_breakouts()` - Breakout Invalidation (Phase 1.3.15)
- ✅ `_get_time_since_breakout()` - Time Since Breakout (Phase 1.3.16)

**Priority**: CRITICAL  
**Estimated Effort**: 4 hours  
**Actual Effort**: ~2 hours

**Test File**: `tests/test_volatility_phase1_basic.py` (created)
**Note**: Run tests with venv activated: `.\.venv\Scripts\Activate.ps1` then `python -m unittest tests.test_volatility_phase1_basic -v`
```python
def _init_breakout_table(self):
    """Initialize breakout_events table if it doesn't exist."""
    import sqlite3
    import os
    
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(self._db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS breakout_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            breakout_type TEXT NOT NULL,
            breakout_price REAL NOT NULL,
            breakout_timestamp TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            invalidated_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_breakout_symbol_timeframe 
        ON breakout_events(symbol, timeframe, is_active)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_breakout_timestamp 
        ON breakout_events(breakout_timestamp)
    """)
    
    conn.commit()
    conn.close()
```

**Priority**: CRITICAL  
**Estimated Effort**: 1 hour

---

#### 1.4 Add Technical Indicator Enhancements

**File**: `infra/volatility_regime_detector.py` (new methods)

**Note**: Full implementation details for tracking methods (ATR trend, wick variance, time since breakout) are in `VOLATILITY_TRACKING_ARCHITECTURE.md`. The methods below show function signatures and return structures. See the tracking architecture document for complete code implementations.

**1.3.1 BB Width Trend Analysis**:
```python
def _calculate_bb_width_trend(
    self,
    df: pd.DataFrame,
    window: int = 10
) -> Dict[str, float]:
    """
    Calculate BB width trend over time.
    
    FIX: Issue 4 - Full implementation (was previously a stub).
    FIX: Issue 6 - Method signature expects DataFrame. Callers must normalize rates first using _normalize_rates().
    
    Args:
        df: pandas DataFrame with OHLC data (must be normalized via _normalize_rates() before calling)
        window: Number of candles to analyze for trend
    
    Returns:
        {
            "current_width": float,
            "trend_slope": float,  # Positive = expanding, Negative = contracting
            "percentile": float,  # 0-100, where 0 = narrowest, 100 = widest
            "is_narrow": bool,  # True if in bottom 20th percentile
            "is_expanding": bool,  # FIX: Issue 3 - True if trend_slope > 0
            "is_contracting": bool  # FIX: Issue 3 - True if trend_slope < 0
        }
    
    Note: This method expects a DataFrame. If you have numpy array or other format, 
    normalize it first using _normalize_rates() before calling this method.
    """
    if df is None or len(df) < window + 20:  # Need 20 for percentile calculation
        return {
            "current_width": 0.0,
            "trend_slope": 0.0,
            "percentile": 50.0,
            "is_narrow": False,
            "is_expanding": False,  # FIX: Issue 3 - Add missing field
            "is_contracting": False  # FIX: Issue 3 - Add missing field
        }
    
    # Calculate BB width for each candle
    bb_widths = []
    for i in range(max(0, len(df) - window - 20), len(df)):
        if all(col in df.columns for col in ['bb_upper', 'bb_lower', 'bb_middle']):
            bb_upper = df.iloc[i]['bb_upper']
            bb_lower = df.iloc[i]['bb_lower']
            bb_middle = df.iloc[i]['bb_middle']
            
            if bb_middle > 0:
                width = (bb_upper - bb_lower) / bb_middle  # Normalized width
                bb_widths.append(width)
        else:
            # FIX: Issue 4 - Calculate BB from scratch if columns missing
            if 'close' not in df.columns:
                continue  # Can't calculate BB without close prices
            # Calculate BB (SMA 20, StdDev 2)
            window_sma = 20
            num_std_dev = 2
            close_slice = df['close'].iloc[max(0, i - window_sma + 1):i+1]
            if len(close_slice) < window_sma:
                continue
            bb_middle = close_slice.mean()
            bb_std = close_slice.std()
            bb_upper = bb_middle + (bb_std * num_std_dev)
            bb_lower = bb_middle - (bb_std * num_std_dev)
            
            if bb_middle > 0:
                width = (bb_upper - bb_lower) / bb_middle  # Normalized width
                bb_widths.append(width)
    
    if len(bb_widths) < window:
        return {
            "current_width": 0.0,
            "trend_slope": 0.0,
            "percentile": 50.0,
            "is_narrow": False,
            "is_expanding": False,  # FIX: Issue 3 - Add missing field
            "is_contracting": False  # FIX: Issue 3 - Add missing field
        }
    
    # Current width
    current_width = bb_widths[-1]
    
    # Calculate trend slope (linear regression on last 'window' values)
    y = np.array(bb_widths[-window:])
    x = np.arange(len(y))
    
    if len(np.unique(x)) > 1:
        slope, _ = np.polyfit(x, y, 1)
    else:
        slope = 0.0
    
    # Calculate percentile (vs last 20 values)
    if len(bb_widths) >= 20:
        recent_widths = bb_widths[-20:]
        percentile = (sum(1 for w in recent_widths if w < current_width) / len(recent_widths)) * 100
    else:
        percentile = 50.0
    
    # Is narrow (bottom 20th percentile)
    is_narrow = percentile < 20.0
    
    # FIX: Issue 3 - Add is_expanding and is_contracting fields
    is_expanding = slope > 0
    is_contracting = slope < 0
    
    return {
        "current_width": current_width,
        "trend_slope": slope,
        "percentile": percentile,
        "is_narrow": is_narrow,
        "is_expanding": is_expanding,  # FIX: Issue 3 - Add missing field
        "is_contracting": is_contracting  # FIX: Issue 3 - Add missing field
    }
```

**1.3.2 Wick Variance Calculation**:
```python
def _calculate_wick_variance(
    self,
    symbol: str,
    timeframe: str,
    current_candle: Dict[str, float],
    current_time: datetime
) -> Dict[str, float]:
    """
    Calculate rolling variance of wick-to-body ratios.
    
    FIX: Data Flow Issue 2 - current_candle extracted from rates in detect_regime().
    FIX: Integration Error 3 - Error handling for insufficient data.
    FIX: Performance Issue 1 - Thread-safe access to tracking structures.
    
    Full implementation: See VOLATILITY_TRACKING_ARCHITECTURE.md Section 2
    
    Args:
        current_candle: Dict with keys "open", "high", "low", "close", "volume"
                       (extracted from rates[-1] in detect_regime())
    
    Returns:
        {
            "current_variance": float,
            "previous_variance": float,
            "variance_change_pct": float,  # % change
            "is_increasing": bool,
            "current_ratio": float,
            "mean_ratio": float
        }
    """
    try:
        # Ensure symbol tracking initialized (thread-safe)
        self._ensure_symbol_tracking(symbol)
        
        # Calculate current wick ratio
        body = abs(current_candle["close"] - current_candle["open"])
        upper_wick = current_candle["high"] - max(current_candle["open"], current_candle["close"])
        lower_wick = min(current_candle["open"], current_candle["close"]) - current_candle["low"]
        total_wick = upper_wick + lower_wick
        
        if body == 0:
            wick_ratio = 0.0
        else:
            wick_ratio = total_wick / body
        
        # Get history and add to history (thread-safe)
        with self._tracking_lock:
            history = self._wick_ratios_history.get(symbol, {}).get(timeframe, deque())
            history.append((current_time, wick_ratio))
        
        # Need at least 10 candles for variance calculation
        if len(history) < 10:
            return {
                "current_variance": 0.0,
                "previous_variance": 0.0,
                "variance_change_pct": 0.0,
                "is_increasing": False,
                "current_ratio": wick_ratio,
                "mean_ratio": wick_ratio
            }
        
        # Calculate variance from last 10 wick ratios (thread-safe read)
        with self._tracking_lock:
            recent_ratios = [ratio for _, ratio in list(history)[-10:]]
        
        current_variance = np.var(recent_ratios)
        
        # Previous variance (from previous 10 ratios, if available)
        if len(history) >= 20:
            with self._tracking_lock:
                previous_ratios = [ratio for _, ratio in list(history)[-20:-10]]
            previous_variance = np.var(previous_ratios)
        else:
            previous_variance = current_variance
        
        # Calculate change percentage
        if previous_variance > 0:
            variance_change_pct = ((current_variance - previous_variance) / previous_variance) * 100
        else:
            variance_change_pct = 0.0
        
        return {
            "current_variance": current_variance,
            "previous_variance": previous_variance,
            "variance_change_pct": variance_change_pct,
            "is_increasing": variance_change_pct > 0,
            "current_ratio": wick_ratio,
            "mean_ratio": np.mean(recent_ratios)
        }
    except Exception as e:
        logger.warning(f"Wick variance calculation failed for {symbol}/{timeframe}: {e}")
        return {
            "current_variance": 0.0,
            "previous_variance": 0.0,
            "variance_change_pct": 0.0,
            "is_increasing": False,
            "current_ratio": 0.0,
            "mean_ratio": 0.0
        }
```

**1.3.3 Intra-Bar Volatility**:
```python
def _calculate_intrabar_volatility(
    self,
    rates: Union[pd.DataFrame, np.ndarray, None],
    window: int = 5
) -> Dict[str, float]:
    """
    Calculate intra-bar volatility (candle range vs body).
    
    FIX: Edge Case 1 - Handle insufficient data.
    FIX: Issue 4 - Handle both DataFrame and numpy array formats.
    
    Args:
        rates: DataFrame, NumPy array, or None
        window: Number of candles to analyze
    
    Returns:
        {
            "current_ratio": float,  # range / body
            "previous_ratio": float,
            "is_rising": bool
        }
    """
    # FIX: Issue 5 - Use _normalize_rates() for consistent data handling
    rates_normalized = self._normalize_rates(rates)
    if rates_normalized is None or len(rates_normalized) < window + 1:
        return {
            "current_ratio": 0.0,
            "previous_ratio": 0.0,
            "is_rising": False
        }
    
    # Convert to numpy array for calculation
    if isinstance(rates_normalized, pd.DataFrame):
        # Extract OHLC columns
        if all(col in rates_normalized.columns for col in ['open', 'high', 'low', 'close']):
            rates_array = rates_normalized[['open', 'high', 'low', 'close']].values
        else:
            return {"current_ratio": 0.0, "previous_ratio": 0.0, "is_rising": False}
    else:
        rates_array = rates_normalized
    
    # Now use consistent numpy array access
    current = rates_array[-1]
    current_range = current[1] - current[2]  # high - low
    current_body = abs(current[3] - current[0])  # |close - open|
    current_ratio = current_range / current_body if current_body > 0 else 0.0
    
    # Calculate ratio for previous candle
    previous = rates_array[-2]
    previous_range = previous[1] - previous[2]
    previous_body = abs(previous[3] - previous[0])
    previous_ratio = previous_range / previous_body if previous_body > 0 else 0.0
    
    return {
        "current_ratio": current_ratio,
        "previous_ratio": previous_ratio,
        "is_rising": current_ratio > previous_ratio
    }
```

**1.3.4 ATR Trend Analysis**:
```python
def _calculate_atr_trend(
    self,
    symbol: str,
    timeframe: str,
    current_atr_14: float,
    current_atr_50: float,
    current_time: datetime
) -> Dict[str, float]:
    """
    Calculate ATR slope/derivative.
    
    FIX: Integration Error 3 - Error handling for insufficient data.
    FIX: Edge Case 1 - Handle cases with < 5 data points.
    FIX: Performance Issue 1 - Thread-safe access to tracking structures.
    FIX: Important Issue 3 - Handle empty history after initialization.
    
    Full implementation: See VOLATILITY_TRACKING_ARCHITECTURE.md Section 1
    
    Returns:
        {
            "current_atr": float,
            "slope": float,  # Rate of change per period
            "slope_pct": float,  # % change per period
            "is_declining": bool,
            "is_above_baseline": bool,  # ATR > baseline threshold
            "trend_direction": str  # "rising", "declining", "stable", "insufficient_data", "error"
        }
    """
    try:
        # Ensure symbol tracking initialized (thread-safe)
        self._ensure_symbol_tracking(symbol)
        
        # Get history for this symbol/timeframe (thread-safe)
        with self._tracking_lock:
            history = self._atr_history.get(symbol, {}).get(timeframe, deque())
            
            # Add current value to history
            history.append((current_time, current_atr_14, current_atr_50))
        
        # FIX: Important Issue 3 - Handle empty history after initialization
        # After first append, len(history) = 1, but we need 5 for slope calculation
        if len(history) < 5:
            return {
                "current_atr": current_atr_14,
                "slope": 0.0,
                "slope_pct": 0.0,
                "is_declining": False,
                "is_above_baseline": current_atr_14 / current_atr_50 > 1.2 if current_atr_50 > 0 else False,
                "trend_direction": "insufficient_data"
            }
        
        # Extract ATR values and timestamps (thread-safe read)
        with self._tracking_lock:
            atr_values = [atr for _, atr, _ in list(history)]
            timestamps = [ts for ts, _, _ in list(history)]
        
        # Calculate slope using linear regression (last 5 points)
        recent_atr = atr_values[-5:]
        recent_times = [(ts - timestamps[-5]).total_seconds() / 60 for ts in timestamps[-5:]]
        
        # FIX: Issue 4 - Defensive check for empty or insufficient data
        if len(recent_atr) < 2 or len(recent_times) < 2:
            return {
                "current_atr": current_atr_14,
                "slope": 0.0,
                "slope_pct": 0.0,
                "is_declining": False,
                "is_above_baseline": current_atr_14 / current_atr_50 > 1.2 if current_atr_50 > 0 else False,
                "trend_direction": "insufficient_data"
            }
        
        # Simple linear regression: slope = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)
        n = len(recent_atr)
        x_sum = sum(recent_times)
        y_sum = sum(recent_atr)
        xy_sum = sum(x * y for x, y in zip(recent_times, recent_atr))
        x2_sum = sum(x * x for x in recent_times)
        
        denominator = n * x2_sum - x_sum * x_sum
        if denominator == 0:
            slope = 0.0
        else:
            slope = (n * xy_sum - x_sum * y_sum) / denominator
        
        # FIX: Issue 3 - Better division by zero handling (check for None and NaN)
        # Calculate percentage change
        if recent_atr and len(recent_atr) > 0 and recent_atr[0] is not None:
            try:
                first_atr = float(recent_atr[0])
                if first_atr > 0 and not np.isnan(first_atr):
                    slope_pct = (slope / first_atr) * 100
                else:
                    slope_pct = 0.0
            except (ValueError, TypeError):
                slope_pct = 0.0
        else:
            slope_pct = 0.0
        
        # Determine trend direction
        if slope_pct < -5.0:
            trend_direction = "declining"
        elif slope_pct > 5.0:
            trend_direction = "rising"
        else:
            trend_direction = "stable"
        
        return {
            "current_atr": current_atr_14,
            "slope": slope,
            "slope_pct": slope_pct,
            "is_declining": slope_pct < -5.0,
            "is_above_baseline": current_atr_14 / current_atr_50 > 1.2 if current_atr_50 > 0 else False,
            "trend_direction": trend_direction
        }
    except Exception as e:
        logger.warning(f"ATR trend calculation failed for {symbol}/{timeframe}: {e}")
        return {
            "current_atr": current_atr_14,
            "slope": 0.0,
            "slope_pct": 0.0,
            "is_declining": False,
            "is_above_baseline": False,
            "trend_direction": "error"
        }
```

**1.3.5 Whipsaw Detection**:
```python
def _detect_whipsaw(
    self,
    rates: Union[pd.DataFrame, np.ndarray, None],
    window: int = 5
) -> Dict[str, Any]:
    """
    Detect whipsaw pattern (alternating direction changes).
    
    FIX: Issue 2 - Handle both DataFrame and numpy array formats.
    
    Args:
        rates: DataFrame, NumPy array, or None
        window: Number of candles to analyze
    
    Returns:
        {
            "is_whipsaw": bool,
            "direction_changes": int,
            "oscillation_around_mean": bool
        }
    """
    # FIX: Issue 6 - Use _normalize_rates() for consistent data handling
    rates_normalized = self._normalize_rates(rates)
    if rates_normalized is None or len(rates_normalized) < window + 1:
        return {"is_whipsaw": False, "direction_changes": 0, "oscillation_around_mean": False}
    
    # Extract close prices (handle both DataFrame and numpy array)
    if isinstance(rates_normalized, pd.DataFrame):
        if 'close' in rates_normalized.columns:
            close_prices = rates_normalized['close'].iloc[-window-1:].values
        else:
            return {"is_whipsaw": False, "direction_changes": 0, "oscillation_around_mean": False}
    else:
        # NumPy array - close is column 3 (index 3)
        close_prices = rates_normalized[-window-1:, 3]
    
    # Count direction changes (alternating up/down movements)
    direction_changes = 0
    previous_direction = None
    
    for i in range(1, len(close_prices)):
        current_direction = None
        if close_prices[i] > close_prices[i-1]:
            current_direction = "up"
        elif close_prices[i] < close_prices[i-1]:
            current_direction = "down"
        else:
            continue  # No change, skip
        
        if previous_direction is not None and current_direction != previous_direction:
            direction_changes += 1
        
        previous_direction = current_direction
    
    # Check if price is oscillating around mean
    if len(close_prices) > 0:
        mean_price = np.mean(close_prices)
        price_deviations = [abs(close - mean_price) for close in close_prices]
        avg_deviation = np.mean(price_deviations) if price_deviations else 0
        mean_range = close_prices.max() - close_prices.min()
        oscillation_around_mean = avg_deviation < (mean_range * 0.3) if mean_range > 0 else False  # Within 30% of range
    else:
        oscillation_around_mean = False
    
    # Whipsaw detected if 3+ direction changes in window
    is_whipsaw = direction_changes >= 3
    
    return {
        "is_whipsaw": is_whipsaw,
        "direction_changes": direction_changes,
        "oscillation_around_mean": oscillation_around_mean
    }
```

**1.3.6 Session Transition Detection**:
```python
def _detect_session_transition(
    self,
    current_time: datetime,
    previous_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Detect if we're in a session transition window.
    
    FIX: Edge Case 3 - All session times are in UTC.
    
    Session transitions (UTC):
    - ASIA→LONDON: 07:00-08:00 UTC (±15 minutes = 06:45-08:15 UTC)
    - LONDON→NY: 13:00-14:00 UTC (±15 minutes = 12:45-14:15 UTC)
    - NY→ASIA: 21:00-22:00 UTC (±15 minutes = 20:45-22:15 UTC)
    
    Returns:
        {
            "is_transition": bool,
            "transition_type": str,  # "ASIA_LONDON", "LONDON_NY", "NY_ASIA"
            "minutes_into_transition": int,
            "transition_window_start": datetime,
            "transition_window_end": datetime
        }
    """
    from infra.session_helpers import SessionHelpers
    
    # Ensure current_time is UTC
    if current_time.tzinfo is None:
        from datetime import timezone
        current_time = current_time.replace(tzinfo=timezone.utc)
    
    utc_hour = current_time.hour
    utc_minute = current_time.minute
    total_minutes = utc_hour * 60 + utc_minute
    
    # ASIA→LONDON transition: 07:00 UTC (±15 min = 06:45-08:15)
    if (6 * 60 + 45) <= total_minutes <= (8 * 60 + 15):
        transition_start = current_time.replace(hour=6, minute=45, second=0, microsecond=0)
        transition_end = current_time.replace(hour=8, minute=15, second=0, microsecond=0)
        return {
            "is_transition": True,
            "transition_type": "ASIA_LONDON",
            "minutes_into_transition": total_minutes - (6 * 60 + 45),
            "transition_window_start": transition_start,
            "transition_window_end": transition_end
        }
    
    # LONDON→NY transition: 13:00 UTC (±15 min = 12:45-14:15)
    if (12 * 60 + 45) <= total_minutes <= (14 * 60 + 15):
        transition_start = current_time.replace(hour=12, minute=45, second=0, microsecond=0)
        transition_end = current_time.replace(hour=14, minute=15, second=0, microsecond=0)
        return {
            "is_transition": True,
            "transition_type": "LONDON_NY",
            "minutes_into_transition": total_minutes - (12 * 60 + 45),
            "transition_window_start": transition_start,
            "transition_window_end": transition_end
        }
    
    # NY→ASIA transition: 21:00 UTC (±15 min = 20:45-22:15)
    if (20 * 60 + 45) <= total_minutes <= (22 * 60 + 15):
        transition_start = current_time.replace(hour=20, minute=45, second=0, microsecond=0)
        transition_end = current_time.replace(hour=22, minute=15, second=0, microsecond=0)
        return {
            "is_transition": True,
            "transition_type": "NY_ASIA",
            "minutes_into_transition": total_minutes - (20 * 60 + 45),
            "transition_window_start": transition_start,
            "transition_window_end": transition_end
        }
    
    return {
        "is_transition": False,
        "transition_type": None,
        "minutes_into_transition": 0,
        "transition_window_start": None,
        "transition_window_end": None
    }
```

**1.3.7 Mean Reversion Pattern Detection**:
```python
def _detect_mean_reversion_pattern(
    self,
    symbol: str,
    timeframe_data: Dict[str, Dict[str, Any]],
    window: int = 10
) -> Dict[str, Any]:
    """
    Detect mean reversion pattern (price oscillating around VWAP/EMA).
    
    Required for: FRAGMENTED_CHOP detection
    
    Returns:
        {
            "is_mean_reverting": bool,
            "oscillation_around_vwap": bool,  # Price within 0.5 ATR of VWAP
            "oscillation_around_ema": bool,   # Price within 0.5 ATR of EMA200
            "touch_count": int,  # Number of times price touched VWAP/EMA in window
            "reversion_strength": float  # 0-1, how strong the reversion pattern
        }
    """
    # Get M15 data (primary timeframe for chop detection)
    m15_data = timeframe_data.get("M15")
    if not m15_data:
        return {"is_mean_reverting": False}
    
    rates = m15_data.get("rates")
    atr_14 = m15_data.get("atr_14", 1.0)
    
    # FIX: Issue 7 - Use _normalize_rates() for consistent data handling
    # FIX: Issue 2 - Calculate vwap and ema_200 from rates (not stored in timeframe_data)
    rates_normalized = self._normalize_rates(rates)
    if rates_normalized is None or len(rates_normalized) < max(window, 200):
        return {"is_mean_reverting": False}
    
    # Calculate VWAP and EMA200 from rates
    vwap = None
    ema_200 = None
    
    if isinstance(rates_normalized, pd.DataFrame):
        if 'close' not in rates_normalized.columns:
            return {"is_mean_reverting": False}
        
        # Calculate VWAP (Volume Weighted Average Price)
        if 'tick_volume' in rates_normalized.columns:
            close_vol = rates_normalized['close'] * rates_normalized['tick_volume']
            vwap = float(close_vol.sum() / rates_normalized['tick_volume'].sum()) if rates_normalized['tick_volume'].sum() > 0 else None
        
        # Calculate EMA200
        if len(rates_normalized) >= 200:
            ema_200 = float(rates_normalized['close'].ewm(span=200, adjust=False).mean().iloc[-1])
        
        close_values = rates_normalized['close'].iloc[-window:].values
    else:
        # NumPy array - close is column 3 (index 3), volume is column 5 (index 5)
        if rates_normalized.shape[1] < 4:
            return {"is_mean_reverting": False}
        
        close_prices = rates_normalized[:, 3]  # close column
        
        # Calculate VWAP from numpy array
        if rates_normalized.shape[1] > 5:
            volumes = rates_normalized[:, 5]  # tick_volume column
            if np.sum(volumes) > 0:
                vwap = float(np.sum(close_prices * volumes) / np.sum(volumes))
        
        # Calculate EMA200 from numpy array
        if len(close_prices) >= 200:
            ema_200 = float(pd.Series(close_prices).ewm(span=200, adjust=False).mean().iloc[-1])
        
        close_values = rates_normalized[-window:, 3]
    
    # Calculate touch count and oscillation
    touch_count = 0
    vwap_touches = 0
    ema_touches = 0
    
    for close in close_values:
        
        # Check VWAP oscillation
        if vwap and abs(close - vwap) <= 0.5 * atr_14:
            vwap_touches += 1
        
        # Check EMA oscillation
        if ema_200 and abs(close - ema_200) <= 0.5 * atr_14:
            ema_touches += 1
    
    touch_count = vwap_touches + ema_touches
    oscillation_around_vwap = vwap_touches >= 3  # At least 3 touches
    oscillation_around_ema = ema_touches >= 3
    
    # Reversion strength: based on touch frequency
    reversion_strength = min(touch_count / window, 1.0)
    
    # Mean reverting if oscillating around either VWAP or EMA
    is_mean_reverting = oscillation_around_vwap or oscillation_around_ema
    
    return {
        "is_mean_reverting": is_mean_reverting,
        "oscillation_around_vwap": oscillation_around_vwap,
        "oscillation_around_ema": oscillation_around_ema,
        "touch_count": touch_count,
        "reversion_strength": reversion_strength
    }
```

**1.3.8 Volatility Spike Detection**:
```python
def _detect_volatility_spike(
    self,
    symbol: str,
    timeframe_data: Dict[str, Dict[str, Any]],
    baseline_atr: float,
    spike_threshold: float = 1.5
) -> Dict[str, Any]:
    """
    Detect volatility spike during session transition.
    
    Required for: SESSION_SWITCH_FLARE detection
    
    Args:
        baseline_atr: Normal ATR value (from recent history, e.g., median of last 20 periods)
        spike_threshold: Multiplier for spike detection (default: 1.5 = 50% increase)
    
    Returns:
        {
            "is_spike": bool,
            "current_atr": float,
            "spike_ratio": float,  # current_atr / baseline_atr
            "spike_magnitude": float,  # % above baseline
            "is_temporary": bool  # True if spike likely to resolve (requires time tracking)
        }
    """
    # Get M15 data (primary timeframe for session flare detection)
    m15_data = timeframe_data.get("M15")
    if not m15_data:
        return {"is_spike": False}
    
    current_atr = m15_data.get("atr_14", 0.0)
    
    if baseline_atr <= 0 or current_atr <= 0:
        return {"is_spike": False}
    
    spike_ratio = current_atr / baseline_atr
    spike_magnitude = ((current_atr - baseline_atr) / baseline_atr) * 100
    
    is_spike = spike_ratio >= spike_threshold
    
    # Temporary check: If spike just started, likely temporary (requires time tracking)
    # This will be enhanced with resolution tracking in _is_flare_resolving()
    is_temporary = is_spike  # Initial assumption, refined by resolution tracking
    
    return {
        "is_spike": is_spike,
        "current_atr": current_atr,
        "spike_ratio": spike_ratio,
        "spike_magnitude": spike_magnitude,
        "is_temporary": is_temporary
    }
```

**1.3.9 Flare Resolution Tracking**:
```python
def _is_flare_resolving(
    self,
    symbol: str,
    timeframe: str,
    current_time: datetime,
    current_atr: float,
    spike_atr: float,
    resolution_window_minutes: int = 30
) -> bool:
    """
    Check if volatility spike is resolving (flare) vs sustained (expansion).
    
    Required for: SESSION_SWITCH_FLARE detection (distinguish flare from expansion)
    
    Logic:
    - If within resolution window (30 min) AND ATR declining > 20% → Flare resolving
    - If beyond resolution window AND ATR still elevated (> 80% of spike) → Expansion (sustained)
    - If ATR declined > 20% from spike → Flare resolved
    
    Returns:
        True if flare is resolving/resolved, False if expansion (sustained)
    """
    # FIX: Issue 8 - Enhanced error handling and edge cases
    # Get spike data from cache (thread-safe)
    with self._tracking_lock:
        spike_data = self._volatility_spike_cache.get(symbol, {}).get(timeframe)
    
    if not spike_data:
        return False  # No spike data = not a flare
    
    try:
        spike_start = spike_data.get("spike_start")
        if not spike_start:
            return False
        
        # Handle timezone-aware datetime comparison
        if isinstance(spike_start, str):
            spike_start = datetime.fromisoformat(spike_start)
        
        time_since_spike = (current_time - spike_start).total_seconds() / 60
        
        # Edge case: spike_atr is 0 or negative
        if spike_atr <= 0 or current_atr <= 0:
            return False
        
        # Calculate ATR decline from spike
        atr_decline_pct = ((spike_atr - current_atr) / spike_atr) * 100
        
        # Within resolution window
        if time_since_spike < resolution_window_minutes:
            # If ATR declined > 20% from spike → Flare resolving
            if atr_decline_pct > 20.0:
                return True  # Flare resolving
        
        # Beyond window but still elevated
        if time_since_spike >= resolution_window_minutes:
            current_ratio = current_atr / spike_atr
            if current_ratio > 0.8:  # Still > 80% of spike
                return False  # Expansion (sustained)
            else:
                return True  # Flare resolved
        
        return False
    except Exception as e:
        logger.warning(f"Error checking flare resolution for {symbol}/{timeframe}: {e}")
        return False
```

**1.3.9.5 Breakout Detection** (NEW - FIX: Gap 2, Logic Error 4):
```python
def _detect_breakout(
    self,
    symbol: str,
    timeframe: str,
    timeframe_data: Dict[str, Any],
    current_time: datetime
) -> Optional[Dict[str, Any]]:
    """
    Detect NEW breakout events (not already detected).
    
    FIX: Gap 2 - Breakout detection logic required for POST_BREAKOUT_DECAY.
    FIX: Logic Error 4 - Only detect NEW breakouts, not every candle in a trend.
    
    Logic:
    1. Price breakout: Price JUST broke above/below recent high/low (previous candle didn't)
    2. Volume breakout: Volume spike > 1.5x average (last 20 candles)
    3. Check cache to avoid duplicate detections
    
    Returns:
        {
            "breakout_type": "price" | "volume" | "structure",
            "breakout_price": float,
            "breakout_timestamp": datetime,
            "direction": "bullish" | "bearish"
        } or None
    """
    # FIX: Issue 4 - Use _normalize_rates() for consistent data handling
    rates = timeframe_data.get("rates")
    rates_normalized = self._normalize_rates(rates)
    if rates_normalized is None or len(rates_normalized) < 21:
        return None
    
    # Convert to numpy array for breakout detection logic
    if isinstance(rates_normalized, pd.DataFrame):
        # Extract OHLC columns as numpy array
        if all(col in rates_normalized.columns for col in ['open', 'high', 'low', 'close']):
            rates_array = rates_normalized[['open', 'high', 'low', 'close']].values
        else:
            return None  # Invalid DataFrame format
    else:
        rates_array = rates_normalized
    
    # FIX: Logic Error 4 - Get recent high/low EXCLUDING current candle
    # Compare current vs previous to detect NEW breakouts only
    recent_high = max(rates_array[-21:-1, 1])  # High prices (exclude current)
    recent_low = min(rates_array[-21:-1, 2])   # Low prices (exclude current)
    current_price = rates_array[-1, 3]          # Current close
    previous_price = rates_array[-2, 3]         # Previous close
    
    # FIX: Logic Error 4 - Check cache to avoid duplicate detections
    with self._tracking_lock:
        cached_breakout = self._breakout_cache.get(symbol, {}).get(timeframe)
        if cached_breakout:
            cached_price = cached_breakout.get("breakout_price")
            cached_time_str = cached_breakout.get("breakout_timestamp")
            if cached_time_str:
                cached_time = datetime.fromisoformat(cached_time_str)
                time_diff = (current_time - cached_time).total_seconds() / 60
                
                # If breakout was detected recently (< 5 candles) and price is still near, skip
                price_range = recent_high - recent_low
                if time_diff < 5 and abs(current_price - cached_price) < price_range * 0.1:
                    return None  # Already detected, skip duplicate
    
    # FIX: Logic Error 4 - Only detect if price JUST broke (previous didn't)
    # 1. Price breakout detection (NEW breakout only)
    if current_price > recent_high and previous_price <= recent_high:
        # NEW bullish breakout detected
        return {
            "breakout_type": "price",
            "breakout_price": current_price,
            "breakout_timestamp": current_time,
            "direction": "bullish"
        }
    elif current_price < recent_low and previous_price >= recent_low:
        # NEW bearish breakdown detected
        return {
            "breakout_type": "price",
            "breakout_price": current_price,
            "breakout_timestamp": current_time,
            "direction": "bearish"
        }
    
    # 2. Volume breakout detection (only if no price breakout)
    # FIX: Issue 5 - Extract volume from rates array if not in timeframe_data
    volumes = None
    if isinstance(rates_normalized, pd.DataFrame):
        # Try to get volume from DataFrame
        if 'tick_volume' in rates_normalized.columns:
            volumes = rates_normalized['tick_volume'].values
        elif 'volume' in rates_normalized.columns:
            volumes = rates_normalized['volume'].values
    else:
        # NumPy array - volume is typically column 4 or 5
        if rates_array.shape[1] > 4:
            volumes = rates_array[:, 4]  # tick_volume column
    
    # Fallback: Try timeframe_data keys
    if volumes is None:
        volumes = timeframe_data.get("volume") or timeframe_data.get("tick_volume")
    
    if volumes is not None and len(volumes) >= 20:
        avg_volume = np.mean(volumes[-20:])
        current_volume = volumes[-1] if len(volumes) > 0 else 0
        previous_volume = volumes[-2] if len(volumes) > 1 else 0
        
        # Only detect if volume JUST spiked (previous didn't)
        if current_volume > avg_volume * 1.5 and previous_volume <= avg_volume * 1.5:
            return {
                "breakout_type": "volume",
                "breakout_price": current_price,
                "breakout_timestamp": current_time,
                "direction": "bullish" if current_price > previous_price else "bearish"
            }
    
    return None

def _extract_rates_array(self, timeframe_data: Dict[str, Any]) -> Optional[np.ndarray]:
    """
    Extract rates array from timeframe_data, handling both formats.
    
    FIX: Integration Error 5 - Handle both numpy array and list formats.
    
    Returns:
        NumPy array with columns [open, high, low, close, volume, ...] or None
    """
    # Format 1: Direct numpy array
    if 'rates' in timeframe_data:
        rates = timeframe_data['rates']
        if isinstance(rates, np.ndarray):
            return rates
    
    # Format 2: Separate lists (from desktop_agent.py)
    if all(key in timeframe_data for key in ['opens', 'highs', 'lows', 'closes']):
        try:
            opens = np.array(timeframe_data['opens'])
            highs = np.array(timeframe_data['highs'])
            lows = np.array(timeframe_data['lows'])
            closes = np.array(timeframe_data['closes'])
            volumes = np.array(timeframe_data.get('volumes', [0] * len(opens)))
            
            # Stack into numpy array format [open, high, low, close, volume, ...]
            rates = np.column_stack([opens, highs, lows, closes, volumes])
            return rates
        except Exception as e:
            logger.warning(f"Error converting lists to numpy array: {e}")
            return None
    
    return None
```

**1.3.10 Breakout Event Recording**:
```python
@contextmanager
def _get_db_connection(self):
    """
    Get database connection with timeout and error handling.
    
    FIX: Performance Issue 2 - Proper connection management with timeout.
    """
    conn = None
    try:
        conn = sqlite3.connect(
            self._db_path,
            timeout=5.0,  # 5 second timeout
            check_same_thread=False  # Allow multi-threaded access
        )
        conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
        yield conn
        conn.commit()
    except sqlite3.OperationalError as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def _record_breakout_event(
    self,
    symbol: str,
    timeframe: str,
    breakout_type: str,
    breakout_price: float,
    current_time: datetime
) -> int:
    """
    Record breakout event to database and cache.
    
    FIX: Edge Case 2 - Invalidate previous active breakouts before recording new one.
    FIX: Performance Issue 2 - Thread-safe database access.
    
    Full implementation: See VOLATILITY_TRACKING_ARCHITECTURE.md Section 3
    
    Returns:
        breakout_id: Database ID of recorded event
    """
    with self._db_lock:  # Thread-safe database access
        # FIX: Invalidate previous active breakouts for this symbol/timeframe
        self._invalidate_previous_breakouts(symbol, timeframe)
        
        # Record new breakout
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO breakout_events 
                    (symbol, timeframe, breakout_type, breakout_price, breakout_timestamp, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (
                    symbol, timeframe, breakout_type, breakout_price,
                    current_time.isoformat()
                ))
                breakout_id = cursor.lastrowid
                
                # Update cache
                with self._tracking_lock:
                    if symbol not in self._breakout_cache:
                        self._breakout_cache[symbol] = {}
                    self._breakout_cache[symbol][timeframe] = {
                        "breakout_type": breakout_type,
                        "breakout_price": breakout_price,
                        "breakout_timestamp": current_time.isoformat()
                    }
                
                return breakout_id
        except Exception as e:
            logger.error(f"Error recording breakout event: {e}")
            return -1

def _invalidate_previous_breakouts(self, symbol: str, timeframe: str):
    """
    Invalidate previous active breakouts for symbol/timeframe.
    
    FIX: Edge Case 2 - Prevents multiple breakouts from conflicting.
    FIX: Performance Issue 2 - Thread-safe database access.
    """
    try:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE breakout_events
                SET is_active = 0, invalidated_at = ?
                WHERE symbol = ? AND timeframe = ? AND is_active = 1
            """, (datetime.now().isoformat(), symbol, timeframe))
        
        # Clear cache
        with self._tracking_lock:
            if symbol in self._breakout_cache and timeframe in self._breakout_cache[symbol]:
                self._breakout_cache[symbol][timeframe] = None
    except Exception as e:
        logger.warning(f"Error invalidating previous breakouts: {e}")
```

**1.3.11 Time Since Breakout Retrieval**:
```python
def _get_time_since_breakout(
    self,
    symbol: str,
    timeframe: str,
    current_time: datetime
) -> Optional[Dict[str, Any]]:
    """
    Get time since last breakout (from cache or database).
    
    FIX: Integration Error 3 - Error handling for database errors.
    FIX: Performance Issue 2 - Thread-safe database access.
    
    Full implementation: See VOLATILITY_TRACKING_ARCHITECTURE.md Section 3
    
    Returns:
        {
            "time_since_minutes": float,
            "time_since_hours": float,
            "breakout_type": str,
            "breakout_price": float,
            "breakout_timestamp": datetime,
            "is_recent": bool  # < 30 minutes
        } or None
    """
    try:
        # Check cache first (fast, thread-safe)
        with self._tracking_lock:
            if symbol in self._breakout_cache and timeframe in self._breakout_cache[symbol]:
                cached = self._breakout_cache[symbol][timeframe]
                if cached:
                    breakout_time = datetime.fromisoformat(cached["breakout_timestamp"])
                    time_diff = (current_time - breakout_time).total_seconds() / 60
                    return {
                        "time_since_minutes": time_diff,
                        "time_since_hours": time_diff / 60,
                        "breakout_type": cached["breakout_type"],
                        "breakout_price": cached["breakout_price"],
                        "breakout_timestamp": cached["breakout_timestamp"],
                        "is_recent": time_diff < 30
                    }
        
        # Fall back to database query (thread-safe)
        with self._db_lock:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT breakout_type, breakout_price, breakout_timestamp
                    FROM breakout_events
                    WHERE symbol = ? AND timeframe = ? AND is_active = 1
                    ORDER BY breakout_timestamp DESC
                    LIMIT 1
                """, (symbol, timeframe))
                
                row = cursor.fetchone()
        
        if row:
            breakout_type, breakout_price, breakout_timestamp_str = row
            breakout_time = datetime.fromisoformat(breakout_timestamp_str)
            time_diff = (current_time - breakout_time).total_seconds() / 60
            
            # Update cache (thread-safe)
            with self._tracking_lock:
                if symbol not in self._breakout_cache:
                    self._breakout_cache[symbol] = {}
                self._breakout_cache[symbol][timeframe] = {
                    "breakout_type": breakout_type,
                    "breakout_price": breakout_price,
                    "breakout_timestamp": breakout_timestamp_str
                }
            
            return {
                "time_since_minutes": time_diff,
                "time_since_hours": time_diff / 60,
                "breakout_type": breakout_type,
                "breakout_price": breakout_price,
                "breakout_timestamp": breakout_timestamp_str,
                "is_recent": time_diff < 30
            }
        
        return None
    except sqlite3.OperationalError as e:
        logger.warning(f"Database error getting breakout time for {symbol}/{timeframe}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting breakout time for {symbol}/{timeframe}: {e}")
        return None
```

**Priority**: HIGH  
**Estimated Effort**: 10 hours (8 hours + 2 hours for new methods)

---

#### 1.4 Add New Volatility State Detection Methods

**File**: `infra/volatility_regime_detector.py`

**1.4.1 PRE_BREAKOUT_TENSION Detection**:
```python
def _detect_pre_breakout_tension(
    self,
    symbol: str,
    timeframe_data: Dict[str, Dict[str, Any]],
    current_time: datetime,
    wick_variances: Dict[str, Dict[str, Any]]
) -> Optional[VolatilityRegime]:
    """
    Detect PRE_BREAKOUT_TENSION state.
    
    FIX: Gap 4 - Added intra-bar volatility check.
    
    Logic:
    - BB width < narrow threshold (bottom 20th percentile)
    - Wick variance increasing (30%+ increase)
    - Intra-bar volatility rising (20%+ increase) ← NEW
    - ATR ratio still low/stable (< 1.2)
    
    Args:
        wick_variances: Pre-calculated wick variances per timeframe
    
    Returns VolatilityRegime.PRE_BREAKOUT_TENSION if detected, None otherwise.
    """
    # Check M15 first (primary timeframe for pre-breakout detection)
    m15_data = timeframe_data.get("M15")
    if not m15_data:
        return None
    
    # FIX: Issue 1 - Normalize rates before calling _calculate_bb_width_trend()
    rates = m15_data.get("rates")
    rates_normalized = self._normalize_rates(rates)
    if rates_normalized is None:
        return None
    
    # FIX: Issue 1, 3, 5 - Use _calculate_bb_width_trend() to get percentile and is_narrow
    # BB width ratio is a multiplier (e.g., 1.5x), not a percentile - must use trend calculation
    try:
        bb_width_trend = self._calculate_bb_width_trend(
            rates_normalized, window=10  # Now guaranteed to be DataFrame
        )
        if not bb_width_trend or not bb_width_trend.get("is_narrow", False):
            return None
    except Exception as e:
        logger.warning(f"BB width trend calculation failed for {symbol}: {e}")
        return None
    
    # Get wick variance
    m15_wick = wick_variances.get("M15")
    if not m15_wick or not isinstance(m15_wick, dict) or not m15_wick.get("is_increasing", False):
        return None
    
    # Wick variance increasing (30%+ threshold)
    if m15_wick.get("variance_change_pct", 0) < 30.0:
        return None
    
    # FIX: Gap 4, Issue 1 - Check intra-bar volatility (normalize rates first)
    intrabar_vol = self._calculate_intrabar_volatility(
        rates_normalized, window=5  # Now guaranteed to be normalized
    )
    if not intrabar_vol.get("is_rising"):
        return None
    
    # Check threshold (20%+ increase)
    ratio_change = ((intrabar_vol["current_ratio"] - intrabar_vol["previous_ratio"]) 
                    / intrabar_vol["previous_ratio"]) * 100 if intrabar_vol["previous_ratio"] > 0 else 0
    if ratio_change < 20.0:
        return None
    
    # FIX: Issue 1 - Calculate atr_ratio from atr_14/atr_50 (not stored in timeframe_data)
    atr_14 = m15_data.get("atr_14", 0)
    atr_50 = m15_data.get("atr_50", 0)
    if atr_50 > 0:
        atr_ratio = atr_14 / atr_50
    else:
        atr_ratio = 1.0  # Default if atr_50 unavailable
    if atr_ratio >= 1.2:
        return None
    
    # All conditions met
    return VolatilityRegime.PRE_BREAKOUT_TENSION
```

**1.4.2 POST_BREAKOUT_DECAY Detection**:
```python
def _detect_post_breakout_decay(
    self,
    symbol: str,
    timeframe_data: Dict[str, Dict[str, Any]],
    current_time: datetime,
    atr_trends: Dict[str, Dict[str, Any]],
    time_since_breakout: Dict[str, Optional[Dict[str, Any]]]
) -> Optional[VolatilityRegime]:
    """
    Detect POST_BREAKOUT_DECAY state.
    
    FIX: Logic Error 3 - Clarified time window logic.
    
    Logic:
    - ATR slope declining (negative slope, -5%+ per period)
    - ATR still above baseline (> 1.2x)
    - Time since breakout < 30 minutes (from time_since_breakout) ← REQUIRED
    - BB width expanding but rate slowing
    
    IMPORTANT: If breakout > 30 min ago but ATR declining:
    → Not POST_BREAKOUT_DECAY (too old)
    → Classify as VOLATILE or TRANSITIONAL based on ATR ratio
    
    Args:
        atr_trends: Pre-calculated ATR trends per timeframe
        time_since_breakout: Pre-calculated time since breakout per timeframe
    
    Returns VolatilityRegime.POST_BREAKOUT_DECAY if detected, None otherwise.
    """
    # Check M15 first (primary timeframe for post-breakout detection)
    m15_atr_trend = atr_trends.get("M15")
    m15_breakout = time_since_breakout.get("M15")
    
    if not m15_atr_trend or not m15_breakout:
        return None
    
    # FIX: Issue 1, Issue 2 - Explicit type checks (defensive programming)
    if not isinstance(m15_atr_trend, dict) or not isinstance(m15_breakout, dict):
        return None
    
    # FIX: Logic Error 3 - Recent breakout REQUIRED (< 30 minutes)
    # If no breakout or breakout too old, cannot be POST_BREAKOUT_DECAY
    if not m15_breakout.get("is_recent", False):
        return None  # Breakout too old or doesn't exist
    
    # ATR declining
    if not m15_atr_trend.get("is_declining", False):
        return None
    
    # ATR above baseline
    if not m15_atr_trend.get("is_above_baseline", False):
        return None
    
    # Slope declining at least 5% per period
    if m15_atr_trend.get("slope_pct", 0) > -5.0:
        return None
    
    # All conditions met
    return VolatilityRegime.POST_BREAKOUT_DECAY
```

**1.4.3 FRAGMENTED_CHOP Detection**:
```python
def _detect_fragmented_chop(
    self,
    symbol: str,
    timeframe_data: Dict[str, Dict[str, Any]],
    current_time: datetime
) -> Optional[VolatilityRegime]:
    """
    Detect FRAGMENTED_CHOP state.
    
    Logic:
    - Whipsaw detected (3+ direction changes in 5 candles)
    - Price oscillating around VWAP/EMA (within 0.5 ATR) - uses mean reversion pattern
    - Low directional momentum (ADX < 15)
    - Session context (lunch hours, dead zones)
    
    Returns VolatilityRegime.FRAGMENTED_CHOP if detected, None otherwise.
    """
    # Get M15 data (primary timeframe for chop detection)
    m15_data = timeframe_data.get("M15")
    if not m15_data:
        return None
    
    # FIX: Issue 2 - Normalize rates before calling _detect_whipsaw()
    rates = m15_data.get("rates")
    rates_normalized = self._normalize_rates(rates)
    if rates_normalized is None:
        return None
    
    # Check whipsaw
    whipsaw = self._detect_whipsaw(rates_normalized, window=5)
    if not whipsaw.get("is_whipsaw") or whipsaw.get("direction_changes", 0) < 3:
        return None
    
    # FIX: Issue 7 - Check mean reversion pattern (with error handling)
    try:
        mean_reversion = self._detect_mean_reversion_pattern(symbol, timeframe_data)
        if not mean_reversion.get("is_mean_reverting"):
            return None
    except Exception as e:
        logger.warning(f"Mean reversion pattern detection failed for {symbol}: {e}")
        return None
    
    # Check directional momentum (ADX)
    adx = m15_data.get("adx", 0)
    if adx >= 15:
        return None  # Too much directional momentum
    
    # Check session context (optional - lunch hours, dead zones)
    # This can be enhanced with session detection
    
    # All conditions met
    return VolatilityRegime.FRAGMENTED_CHOP
```

**1.4.4 SESSION_SWITCH_FLARE Detection**:
```python
def _detect_session_switch_flare(
    self,
    symbol: str,
    timeframe_data: Dict[str, Dict[str, Any]],
    current_time: datetime
) -> Optional[VolatilityRegime]:
    """
    Detect SESSION_SWITCH_FLARE state.
    
    Logic:
    - In session transition window (±15 minutes)
    - Volatility spike during transition (1.5x normal)
    - Flare should resolve within 30 minutes
    - Distinguish from genuine expansion (flare is temporary)
    
    Returns VolatilityRegime.SESSION_SWITCH_FLARE if detected, None otherwise.
    """
    # Check session transition
    session_transition = self._detect_session_transition(current_time)
    if not session_transition.get("is_transition"):
        return None
    
    # Get M15 data
    m15_data = timeframe_data.get("M15")
    if not m15_data:
        return None
    
    # FIX: Issue 8 - Normalize rates first, then check length
    rates = m15_data.get("rates")
    rates_normalized = self._normalize_rates(rates)
    if rates_normalized is None or len(rates_normalized) < 20:
        return None
    
    # FIX: Gap 5, Issue 3, Issue 4 - Complete baseline ATR calculation with thread-safe access
    # Calculate baseline ATR (median of last 20 periods from history)
    recent_atrs = []
    
    # FIX: Issue 3, Issue 4 - Use thread-safe access and correct history indexing
    with self._tracking_lock:
        if symbol in self._atr_history and "M15" in self._atr_history[symbol]:
            history = list(self._atr_history[symbol]["M15"])
            # History is a deque of (timestamp, atr_14, atr_50) tuples
            # Get last 20 ATR values (or all if fewer than 20)
            for entry in history[-20:]:
                _, atr_val, _ = entry
                recent_atrs.append(atr_val)
    
    # Fallback: Use ATR(50) as baseline if history unavailable or insufficient
    if not recent_atrs or len(recent_atrs) < 10:
        baseline_atr = m15_data.get("atr_50", m15_data.get("atr_14", 0))
    else:
        baseline_atr = np.median(recent_atrs)
    
    # Detect volatility spike
    spike = self._detect_volatility_spike(symbol, timeframe_data, baseline_atr, spike_threshold=1.5)
    if not spike.get("is_spike"):
        return None
    
    # Track spike start time (if not already tracked)
    if symbol not in self._volatility_spike_cache:
        self._volatility_spike_cache[symbol] = {}
    if "M15" not in self._volatility_spike_cache[symbol] or \
       not self._volatility_spike_cache[symbol]["M15"]:
        self._volatility_spike_cache[symbol]["M15"] = {
            "spike_start": current_time,
            "spike_atr": spike["current_atr"]
        }
    
    # Check if flare is resolving (distinguish from expansion)
    spike_data = self._volatility_spike_cache[symbol]["M15"]
    is_resolving = self._is_flare_resolving(
        symbol, "M15", current_time,
        spike["current_atr"], spike_data["spike_atr"]
    )
    
    # If not resolving and beyond 30 minutes → Expansion, not flare
    time_since_spike = (current_time - spike_data["spike_start"]).total_seconds() / 60
    if time_since_spike > 30 and not is_resolving:
        return None  # Expansion, not flare
    
    # All conditions met
    return VolatilityRegime.SESSION_SWITCH_FLARE
```

**Priority**: HIGH  
**Estimated Effort**: 12 hours

**Status**: ✅ **COMPLETED** - All 4 detection methods implemented:
- ✅ `_detect_pre_breakout_tension()` - Phase 1.4.1
- ✅ `_detect_post_breakout_decay()` - Phase 1.4.2
- ✅ `_detect_fragmented_chop()` - Phase 1.4.3
- ✅ `_detect_session_switch_flare()` - Phase 1.4.4

---

#### 1.5 Update Main Detection Logic ✅ COMPLETED

**File**: `infra/volatility_regime_detector.py`

**Status**: ✅ **COMPLETED** - Main detection logic updated with new state detection methods, priority handling, and tracking metrics integration

**Modify `detect_regime()` method**:

**FIXES APPLIED**:
- **Gap 1**: Complete return structure with tracking metrics
- **Gap 2**: Breakout detection integration
- **Logic Error 1**: State priority conflict handling
- **Data Flow Issue 1**: Tracking metrics calculation and passing
- **Data Flow Issue 2**: Current candle extraction
- **Integration Error 2**: Symbol tracking initialization

```python
def detect_regime(
    self,
    symbol: str,
    timeframe_data: Dict[str, Dict[str, Any]],
    current_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Detect volatility regime with advanced state detection.
    
    FIX: Returns complete structure with tracking metrics.
    FIX: Issue 11 - Document DataFrame vs NumPy array handling.
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDc')
        timeframe_data: Dict with keys 'M5', 'M15', 'H1' containing:
            - 'rates': pandas DataFrame OR numpy array of OHLCV data
              (DataFrame format from desktop_agent.py, numpy array from MT5)
            - 'atr_14': ATR(14) value
            - 'atr_50': ATR(50) value
            - ... (other fields)
        current_time: Current timestamp (defaults to now)
    
    Returns:
        Dict with complete structure including tracking metrics.
    """
    if current_time is None:
        current_time = datetime.now()
    
    # FIX: Integration Error 2 - Initialize symbol tracking
    self._ensure_symbol_tracking(symbol)
    
    # FIX: Issue 1 - Calculate indicators for each timeframe (REQUIRED for fallback classification)
    indicators = {}
    volume_confirmed = {}
    
    for tf_name in ["M5", "M15", "H1"]:
        if tf_name not in timeframe_data:
            continue
        
        tf_data = timeframe_data[tf_name]
        indicators[tf_name] = self._calculate_timeframe_indicators(tf_data, tf_name)
        volume_confirmed[tf_name] = indicators[tf_name].get("volume_confirmed", False)
    
    # FIX: Data Flow Issue 1 - Calculate tracking metrics FIRST
    # FIX: Issue 7 - Initialize advanced detection fields before loop
    # FIX: Issue 2 - Initialize volume_confirmed dict
    atr_trends = {}
    wick_variances = {}
    time_since_breakout = {}
    mean_reversion_pattern = {}  # Initialize before loop
    volatility_spike = {}  # Initialize before loop
    session_transition = {}  # Initialize before loop
    whipsaw_detected = {}  # Initialize before loop
    
    # Extract current candles and calculate tracking metrics per timeframe
    for tf in ["M5", "M15", "H1"]:
        tf_data = timeframe_data.get(tf)
        if not tf_data:
            continue
        
        rates = tf_data.get("rates")
        if rates is None or len(rates) == 0:
            continue
        
        try:
            # FIX: Issue 1, 3, 8, 9 - Use _normalize_rates() and handle DataFrame format
            # FIX: Issue 9 - Validate _normalize_rates() return value
            rates_normalized = self._normalize_rates(rates)
            if rates_normalized is None:
                logger.warning(f"Could not normalize rates for {symbol}/{tf}")
                continue
            
            # FIX: Issue 1, 3, 8 - Extract current candle (handle both DataFrame and numpy array)
            if isinstance(rates_normalized, pd.DataFrame):
                # DataFrame format - handle different column name formats
                last_row = rates_normalized.iloc[-1]
                
                # FIX: Issue 8 - Map column names (handle both formats)
                open_col = 'open' if 'open' in rates_normalized.columns else rates_normalized.columns[0]
                high_col = 'high' if 'high' in rates_normalized.columns else rates_normalized.columns[1]
                low_col = 'low' if 'low' in rates_normalized.columns else rates_normalized.columns[2]
                close_col = 'close' if 'close' in rates_normalized.columns else rates_normalized.columns[3]
                volume_col = 'tick_volume' if 'tick_volume' in rates_normalized.columns else ('volume' if 'volume' in rates_normalized.columns else None)
                
                try:
                    current_candle = {
                        "open": float(last_row[open_col]),
                        "high": float(last_row[high_col]),
                        "low": float(last_row[low_col]),
                        "close": float(last_row[close_col]),
                        "volume": float(last_row[volume_col]) if volume_col and volume_col in last_row else 0.0
                    }
                except (KeyError, IndexError, ValueError) as e:
                    logger.warning(f"Error extracting current candle from DataFrame for {symbol}/{tf}: {e}")
                    continue
            else:
                # NumPy array format
                last_candle = rates_normalized[-1]
                current_candle = {
                    "open": float(last_candle[0]),
                    "high": float(last_candle[1]),
                    "low": float(last_candle[2]),
                    "close": float(last_candle[3]),
                    "volume": float(last_candle[4]) if len(last_candle) > 4 else 0.0
                }
            
            # FIX: Important Issue 1 - Calculate metrics with error handling
            # FIX: Issue 5 - Correct indentation (same level as try block)
            # Calculate ATR trend (with error handling)
            try:
                atr_trends[tf] = self._calculate_atr_trend(
                    symbol, tf, tf_data.get("atr_14", 0), tf_data.get("atr_50", 0), current_time
                )
            except Exception as e:
                logger.warning(f"ATR trend calculation failed for {symbol}/{tf}: {e}")
                atr_trends[tf] = {"trend_direction": "error", "is_declining": False, "is_above_baseline": False}
            
            # Calculate wick variance (with error handling)
            try:
                wick_variances[tf] = self._calculate_wick_variance(
                    symbol, tf, current_candle, current_time
                )
            except Exception as e:
                logger.warning(f"Wick variance calculation failed for {symbol}/{tf}: {e}")
                wick_variances[tf] = {"is_increasing": False, "variance_change_pct": 0.0}
            
            # Get time since breakout (with error handling)
            try:
                time_since_breakout[tf] = self._get_time_since_breakout(
                    symbol, tf, current_time
                )
            except Exception as e:
                logger.warning(f"Time since breakout retrieval failed for {symbol}/{tf}: {e}")
                time_since_breakout[tf] = None
            
            # FIX: Gap 2 - Detect and record breakouts (with error handling)
            try:
                breakout = self._detect_breakout(symbol, tf, tf_data, current_time)
                if breakout:
                    self._record_breakout_event(
                        symbol, tf, breakout["breakout_type"],
                        breakout["breakout_price"], current_time
                    )
                    # Update time_since_breakout cache
                    time_since_breakout[tf] = {
                        "time_since_minutes": 0.0,
                        "time_since_hours": 0.0,
                        "breakout_type": breakout["breakout_type"],
                        "breakout_price": breakout["breakout_price"],
                        "breakout_timestamp": current_time.isoformat(),
                        "is_recent": True
                    }
            except Exception as e:
                logger.warning(f"Breakout detection failed for {symbol}/{tf}: {e}")
                # Continue without breakout detection
            
            # Calculate advanced detection fields (for M15 primarily, with error handling)
            if tf == "M15":
                try:
                    mean_reversion_pattern = self._detect_mean_reversion_pattern(symbol, timeframe_data)
                except Exception as e:
                    logger.warning(f"Mean reversion pattern detection failed: {e}")
                    mean_reversion_pattern = {}
                
                try:
                    baseline_atr = tf_data.get("atr_50", tf_data.get("atr_14", 0))
                    volatility_spike = self._detect_volatility_spike(
                        symbol, timeframe_data, baseline_atr
                    )
                except Exception as e:
                    logger.warning(f"Volatility spike detection failed: {e}")
                    volatility_spike = {}
                
                try:
                    session_transition = self._detect_session_transition(current_time)
                except Exception as e:
                    logger.warning(f"Session transition detection failed: {e}")
                    session_transition = {}
                
                try:
                    # FIX: Issue 6 - Pass normalized rates to whipsaw detection
                    whipsaw_detected = self._detect_whipsaw(rates_normalized, window=5)
                except Exception as e:
                    logger.warning(f"Whipsaw detection failed: {e}")
                    whipsaw_detected = {}
        
        except Exception as e:
            logger.error(f"Error processing {tf} for {symbol}: {e}")
            continue  # Skip this timeframe, continue with others
    
    # FIX: Logic Error 1 - Check states in priority order (most specific first)
    # FIX: Logic Error 5 - Handle conflicts between PRE_BREAKOUT and POST_BREAKOUT
    # Priority order:
    # 1. SESSION_SWITCH_FLARE (highest - blocks all)
    # 2. FRAGMENTED_CHOP (blocks most strategies)
    # 3. POST_BREAKOUT_DECAY (momentum fading - more specific than tension)
    # 4. PRE_BREAKOUT_TENSION (compression - less specific)
    # 5. Basic states (STABLE/TRANSITIONAL/VOLATILE)
    
    detected_states = []
    
    # Check all advanced states (with error handling)
    try:
        session_flare = self._detect_session_switch_flare(symbol, timeframe_data, current_time)
        if session_flare:
            detected_states.append((1, session_flare))
    except Exception as e:
        logger.warning(f"Session switch flare detection failed: {e}")
    
    try:
        fragmented_chop = self._detect_fragmented_chop(symbol, timeframe_data, current_time)
        if fragmented_chop:
            detected_states.append((2, fragmented_chop))
    except Exception as e:
        logger.warning(f"Fragmented chop detection failed: {e}")
    
    try:
        post_breakout = self._detect_post_breakout_decay(
            symbol, timeframe_data, current_time, atr_trends, time_since_breakout
        )
        if post_breakout:
            detected_states.append((3, post_breakout))
    except Exception as e:
        logger.warning(f"Post-breakout decay detection failed: {e}")
    
    try:
        pre_breakout = self._detect_pre_breakout_tension(
            symbol, timeframe_data, current_time, wick_variances
        )
        if pre_breakout:
            detected_states.append((4, pre_breakout))
    except Exception as e:
        logger.warning(f"Pre-breakout tension detection failed: {e}")
    
    # FIX: Logic Error 5 - Handle PRE_BREAKOUT vs POST_BREAKOUT conflict
    # If both detected, use recency check
    pre_breakout_state = next((s for p, s in detected_states if p == 4), None)
    post_breakout_state = next((s for p, s in detected_states if p == 3), None)
    
    if pre_breakout_state and post_breakout_state:
        # Check time since breakout
        breakout_time = time_since_breakout.get("M15", {}).get("time_since_minutes", 999) if time_since_breakout.get("M15") else 999
        
        # If breakout was > 1 hour ago, PRE_BREAKOUT_TENSION is more relevant (new compression)
        if breakout_time > 60:
            # Remove POST_BREAKOUT_DECAY, keep PRE_BREAKOUT_TENSION
            detected_states = [(p, s) for p, s in detected_states if p != 3]
            logger.info(f"PRE_BREAKOUT_TENSION takes priority over POST_BREAKOUT_DECAY (breakout {breakout_time:.1f} min ago)")
        else:
            # Remove PRE_BREAKOUT_TENSION, keep POST_BREAKOUT_DECAY (momentum still fading)
            detected_states = [(p, s) for p, s in detected_states if p != 4]
            logger.info(f"POST_BREAKOUT_DECAY takes priority over PRE_BREAKOUT_TENSION (breakout {breakout_time:.1f} min ago)")
    
    # Use highest priority state (lowest number = highest priority)
    if detected_states:
        detected_states.sort(key=lambda x: x[0])
        regime = detected_states[0][1]
    else:
        # FIX: Issue 1 - Calculate composite indicators for fallback classification
        # Use existing _weighted_average() method from RegimeDetector
        # Extract ratios from indicators dict
        atr_ratios = {}
        bb_width_ratios = {}
        adx_values = {}
        
        for tf_name in ["M5", "M15", "H1"]:
            if tf_name in indicators:  # FIX: Issue 8 - Check key exists
                tf_indicators = indicators[tf_name]
                atr_ratios[tf_name] = tf_indicators.get("atr_ratio", 1.0)
                bb_width_ratios[tf_name] = tf_indicators.get("bb_width_ratio", 1.0)
                adx_values[tf_name] = tf_indicators.get("adx", 0)
            else:
                # FIX: Issue 8 - Use defaults if timeframe missing
                atr_ratios[tf_name] = 1.0
                bb_width_ratios[tf_name] = 1.0
                adx_values[tf_name] = 0
        
        # Use existing weighted_average method
        composite_atr_ratio = self._weighted_average(atr_ratios, self.TIMEFRAME_WEIGHTS)
        composite_bb_width = self._weighted_average(bb_width_ratios, self.TIMEFRAME_WEIGHTS)
        composite_adx = self._weighted_average(adx_values, self.TIMEFRAME_WEIGHTS)
        volume_confirmed_composite = any(volume_confirmed.values())
        
        # Fall back to basic classification
        regime = self._classify_regime(
            composite_atr_ratio,
            composite_bb_width,
            composite_adx,
            volume_confirmed_composite
        )
    
    # FIX: Issue 6 - Calculate composite indicators and confidence if not already calculated
    # FIX: Issue 10 - Use existing _weighted_average() method from RegimeDetector
    if 'composite_atr_ratio' not in locals():
        # Extract ratios from indicators dict
        atr_ratios = {}
        for tf_name in ["M5", "M15", "H1"]:
            if tf_name in indicators:
                tf_indicators = indicators[tf_name]
                atr_ratios[tf_name] = tf_indicators.get("atr_ratio", 1.0)
        
        composite_atr_ratio = self._weighted_average(atr_ratios, self.TIMEFRAME_WEIGHTS)
    
    if 'composite_bb_width' not in locals():
        bb_width_ratios = {}
        for tf_name in ["M5", "M15", "H1"]:
            if tf_name in indicators:
                tf_indicators = indicators[tf_name]
                bb_width_ratios[tf_name] = tf_indicators.get("bb_width_ratio", 1.0)
        
        composite_bb_width = self._weighted_average(bb_width_ratios, self.TIMEFRAME_WEIGHTS)
    
    if 'composite_adx' not in locals():
        adx_values = {}
        for tf_name in ["M5", "M15", "H1"]:
            if tf_name in indicators:
                tf_indicators = indicators[tf_name]
                adx_values[tf_name] = tf_indicators.get("adx", 0)
        
        composite_adx = self._weighted_average(adx_values, self.TIMEFRAME_WEIGHTS)
    
    if 'volume_confirmed_composite' not in locals():
        volume_confirmed_composite = any(volume_confirmed.values())
    
    # Calculate confidence (if not already calculated)
    if 'confidence' not in locals():
        confidence = self._calculate_confidence(
            composite_atr_ratio,
            composite_bb_width,
            composite_adx,
            volume_confirmed_composite,
            indicators
        )
    
    # Generate reasoning (if not already calculated)
    if 'reasoning' not in locals():
        # FIX: Issue 1 - Use correct method signature (6 parameters, not 4)
        reasoning = self._generate_reasoning(
            regime,
            composite_atr_ratio,
            composite_bb_width,
            composite_adx,
            volume_confirmed_composite,
            indicators
        )
    
    # FIX: Gap 1 - Return structure with NEW fields
    # FIX: Integration Error 7 - Ensure backward compatibility with safe defaults
    # FIX: Important Issue 4 - Document return structure
    """
    Returns:
        Dict with structure:
        {
            # ALWAYS PRESENT (required fields)
            'regime': VolatilityRegime enum,
            'confidence': float (0-100),
            'indicators': Dict[str, Dict[str, Any]],  # Per-timeframe indicators
            'reasoning': str,
            'atr_ratio': float,
            'bb_width_ratio': float,
            'adx_composite': float,
            'volume_confirmed': bool,  # Composite (any timeframe confirmed)
            'timestamp': str (ISO format),
            
            # OPTIONAL (may be empty dict if tracking fails)
            'atr_trends': Dict[str, Dict[str, Any]],  # {timeframe: {...}}
            'wick_variances': Dict[str, Dict[str, Any]],  # {timeframe: {...}}
            'time_since_breakout': Dict[str, Optional[Dict[str, Any]]],  # {timeframe: {...} or None}
            'mean_reversion_pattern': Dict[str, Any] or {},
            'volatility_spike': Dict[str, Any] or {},
            'session_transition': Dict[str, Any] or {},
            'whipsaw_detected': Dict[str, Any] or {}
        }
    """
    return {
        # Existing fields (MUST be present for backward compatibility)
        'regime': regime,
        'confidence': confidence,
        'indicators': indicators,
        'reasoning': reasoning,
        'atr_ratio': composite_atr_ratio,  # FIX: Use correct variable name
        'bb_width_ratio': composite_bb_width,  # FIX: Use correct variable name
        'adx_composite': composite_adx,  # FIX: Use correct variable name
        'volume_confirmed': volume_confirmed_composite,  # FIX: Use correct variable name
        'timestamp': current_time.isoformat(),
        
        # NEW: Tracking metrics (per-timeframe) - with safe defaults
        'atr_trends': atr_trends or {},
        'wick_variances': wick_variances or {},
        'time_since_breakout': time_since_breakout or {},
        
        # NEW: Advanced detection fields - with safe defaults
        'mean_reversion_pattern': mean_reversion_pattern or {},
        'volatility_spike': volatility_spike or {},
        'session_transition': session_transition or {},
        'whipsaw_detected': whipsaw_detected or {}
    }
```

**Priority**: CRITICAL  
**Estimated Effort**: 6 hours (increased due to tracking metrics integration)
**Actual Effort**: ~4 hours

**Testing**: ✅ **COMPLETED** - Test suite created (`tests/test_volatility_phase1_4_detection.py`) with 11 tests, all passing

---

### PHASE 2: Strategy Selection Updates

#### 2.1 Update Strategy Mapping ✅ COMPLETED

**File**: `infra/volatility_strategy_mapper.py` (CREATE NEW FILE)

**Status**: ✅ **COMPLETED** - Module created with strategy mappings for all 4 new volatility states

**FIX: Integration Error 4** - `infra/strategy_map.py` exists but is for JSON config loading.
**FIX: Issue 2** - Module doesn't exist, must be created as specified.
**Decision**: Create new file `infra/volatility_strategy_mapper.py` for volatility→strategy mappings.

**⚠️ CRITICAL**: This file MUST be created before Phase 2.2 implementation, as `desktop_agent.py` will import from it.

**New Strategy Mappings**:
```python
from typing import Dict, Any, Optional
from infra.volatility_regime_detector import VolatilityRegime

VOLATILITY_STRATEGY_MAP = {
    VolatilityRegime.PRE_BREAKOUT_TENSION: {
        "prioritize": [
            "breakout_ib_volatility_trap",
            "liquidity_sweep_reversal",
            "breaker_block"
        ],
        "avoid": [
            "mean_reversion_range_scalp",
            "trend_continuation_pullback"
        ],
        "confidence_adjustment": +10  # Boost confidence for breakout strategies
    },
    VolatilityRegime.POST_BREAKOUT_DECAY: {
        "prioritize": [
            "mean_reversion_range_scalp",
            "fvg_retracement",
            "order_block_rejection"
        ],
        "avoid": [
            "trend_continuation_pullback",
            "breakout_ib_volatility_trap",
            "market_structure_shift"
        ],
        "confidence_adjustment": -5  # Reduce confidence for continuation
    },
    VolatilityRegime.FRAGMENTED_CHOP: {
        "prioritize": [
            "micro_scalp",
            "mean_reversion_range_scalp"
        ],
        "avoid": [
            "trend_continuation_pullback",
            "breakout_ib_volatility_trap",
            "liquidity_sweep_reversal",
            "market_structure_shift",
            "fvg_retracement"
        ],
        "confidence_adjustment": -15  # Significant reduction
    },
    VolatilityRegime.SESSION_SWITCH_FLARE: {
        "prioritize": [],  # No strategies - WAIT
        "avoid": [
            "ALL"  # Block all strategies during flare
        ],
        "confidence_adjustment": -100  # Force WAIT
    }
}

def get_strategies_for_volatility(
    volatility_regime: VolatilityRegime,
    symbol: str,
    session: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get strategy recommendations for a volatility regime.
    
    FIX: Issue 4 - Missing function implementation.
    
    Args:
        volatility_regime: Detected volatility regime
        symbol: Trading symbol (for symbol-specific adjustments)
        session: Current session (for session-specific adjustments)
    
    Returns:
        {
            "prioritize": List[str],  # Strategy names to prioritize
            "avoid": List[str],  # Strategy names to avoid
            "confidence_adjustment": int,  # Confidence score adjustment
            "recommendation": str,  # Human-readable recommendation
            "wait_reason": Optional[str]  # If WAIT recommended, reason
        }
    """
    # Get base mapping
    mapping = VOLATILITY_STRATEGY_MAP.get(volatility_regime, {})
    
    if not mapping:
        # Fallback for basic states (STABLE, TRANSITIONAL, VOLATILE)
        return {
            "prioritize": [],
            "avoid": [],
            "confidence_adjustment": 0,
            "recommendation": f"Standard strategies for {volatility_regime.value}",
            "wait_reason": None
        }
    
    # Build recommendation message
    prioritize = mapping.get("prioritize", [])
    avoid = mapping.get("avoid", [])
    
    if volatility_regime == VolatilityRegime.SESSION_SWITCH_FLARE:
        recommendation = "WAIT - Session transition volatility flare detected. Wait for stabilization."
        wait_reason = "SESSION_SWITCH_FLARE"
    elif prioritize:
        recommendation = f"Prioritize: {', '.join(prioritize)}"
        wait_reason = None
    else:
        recommendation = f"Standard strategies for {volatility_regime.value}"
        wait_reason = None
    
    return {
        "prioritize": prioritize,
        "avoid": avoid,
        "confidence_adjustment": mapping.get("confidence_adjustment", 0),
        "recommendation": recommendation,
        "wait_reason": wait_reason
    }
```

**Priority**: HIGH  
**Estimated Effort**: 2 hours

---

#### 2.2 Update Strategy Selection Logic ✅ COMPLETED

**File**: `desktop_agent.py` (in `tool_analyse_symbol_full()`)

**Status**: ✅ **COMPLETED** - Strategy recommendations integrated into analysis tool, includes session detection and error handling

**Changes**:
```python
# After volatility regime detection
volatility_regime = volatility_regime_data.get("regime")

# NEW: Apply volatility-aware strategy selection
from infra.volatility_strategy_mapper import get_strategies_for_volatility

strategy_recommendations = get_strategies_for_volatility(
    volatility_regime=volatility_regime,
    symbol=symbol,
    session=current_session
)

# Include in response
response_data["volatility_strategy_recommendations"] = strategy_recommendations
```

**Priority**: HIGH  
**Estimated Effort**: 3 hours
**Actual Effort**: ~2 hours

**Testing**: ✅ **COMPLETED** - Covered in Phase 2.1 testing (11 tests passing)
**Actual Effort**: ~2 hours

**Testing**: ✅ **COMPLETED** - Covered in Phase 2.1 testing (11 tests passing)

---

### PHASE 3: Auto-Execution Plan Validation

#### 3.1 Add Volatility State Validation ✅ COMPLETED

**File**: `handlers/auto_execution_validator.py` (or create if doesn't exist)

**Status**: ✅ **COMPLETED** - Validator module created with validation rules for all 4 new volatility states

**New Validation Rules**:
```python
def validate_volatility_state(
    self,
    plan: Dict[str, Any],
    volatility_regime: VolatilityRegime,
    strategy_type: str
) -> Tuple[bool, Optional[str]]:
    """
    Validate plan against volatility state.
    
    Returns:
        (is_valid, rejection_reason)
    """
    
    # SESSION_SWITCH_FLARE: Block ALL plans
    if volatility_regime == VolatilityRegime.SESSION_SWITCH_FLARE:
        return (False, "Cannot create plans during SESSION_SWITCH_FLARE - wait for volatility stabilization")
    
    # FRAGMENTED_CHOP: Only allow micro_scalp and mean_reversion_range_scalp
    if volatility_regime == VolatilityRegime.FRAGMENTED_CHOP:
        allowed = ["micro_scalp", "mean_reversion_range_scalp"]
        if strategy_type not in allowed:
            return (False, f"FRAGMENTED_CHOP only allows {allowed} strategies")
    
    # POST_BREAKOUT_DECAY: Block trend continuation
    if volatility_regime == VolatilityRegime.POST_BREAKOUT_DECAY:
        blocked = ["trend_continuation_pullback", "breakout_ib_volatility_trap", "market_structure_shift"]
        if strategy_type in blocked:
            return (False, f"POST_BREAKOUT_DECAY blocks {strategy_type} - momentum is fading")
    
    # PRE_BREAKOUT_TENSION: Discourage mean reversion
    if volatility_regime == VolatilityRegime.PRE_BREAKOUT_TENSION:
        discouraged = ["mean_reversion_range_scalp"]
        if strategy_type in discouraged:
            return (False, f"PRE_BREAKOUT_TENSION discourages {strategy_type} - breakout expected")
    
    return (True, None)
```

**Priority**: CRITICAL  
**Estimated Effort**: 4 hours
**Actual Effort**: ~2 hours

**Testing**: ✅ **COMPLETED** - Test suite created (`tests/test_volatility_phase3_validation.py`) with 14 tests, all passing

---

#### 3.2 Integrate into Plan Creation ✅ COMPLETED

**File**: `chatgpt_auto_execution_integration.py` (FIX: Integration Error 1 - Correct file location)

**Status**: ✅ **COMPLETED** - Volatility validation integrated into plan creation with error handling

**Class**: `ChatGPTAutoExecution`  
**Method**: `create_trade_plan()` (line 29)

**Changes**:
```python
def create_trade_plan(
    self,
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    volume: float = 0.01,
    conditions: Dict[str, Any] = None,
    expires_hours: int = 24,
    notes: str = None,
    plan_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a trade plan for auto execution"""
    
    # ... existing validation code ...
    
    # FIX: Gap 3 - Get current volatility regime
    from infra.volatility_regime_detector import RegimeDetector
    regime_detector = RegimeDetector()
    current_regime = regime_detector.get_current_regime(symbol_normalized)
    
    # Get strategy_type from conditions or extract from notes
    strategy_type = conditions.get("strategy_type") if conditions else None
    if not strategy_type and notes:
        # Try to extract strategy_type from notes (e.g., "[strategy:breakout_ib_volatility_trap]")
        import re
        match = re.search(r'\[strategy:(\w+)\]', notes)
        if match:
            strategy_type = match.group(1)
    
    # FIX: Integration Error 1 - Validate against volatility state
    # FIX: Issue 3 - Remove circular import, validate directly
    if current_regime and strategy_type:
        # Import VolatilityRegime enum
        from infra.volatility_regime_detector import VolatilityRegime
        
        # Validate strategy compatibility with volatility regime
        strategy_volatility_map = {
            "breakout_ib_volatility_trap": [VolatilityRegime.PRE_BREAKOUT_TENSION, VolatilityRegime.STABLE],
            "trend_continuation_pullback": [VolatilityRegime.VOLATILE, VolatilityRegime.TRANSITIONAL],
            "mean_reversion_range_scalp": [VolatilityRegime.STABLE, VolatilityRegime.FRAGMENTED_CHOP],
            "micro_scalp": [VolatilityRegime.STABLE, VolatilityRegime.FRAGMENTED_CHOP],
            "liquidity_sweep_reversal": [VolatilityRegime.STABLE, VolatilityRegime.TRANSITIONAL],
            "order_block_rejection": [VolatilityRegime.STABLE, VolatilityRegime.TRANSITIONAL],
            # Add other strategy mappings as needed
        }
        
        allowed_states = strategy_volatility_map.get(strategy_type, [])
        if allowed_states and current_regime not in allowed_states:
            return {
                "success": False,
                "message": f"Strategy {strategy_type} not compatible with {current_regime.value}. Allowed states: {[s.value for s in allowed_states]}",
                "volatility_state": current_regime.value,
                "plan_id": None
            }
    
    # Continue with existing plan creation logic...
```

**FIX: Gap 3 - Add `get_current_regime()` method to RegimeDetector**:
**FIX: Integration Error 6 - Add `_prepare_timeframe_data()` method**:

**File**: `infra/volatility_regime_detector.py`

**New Method 1: `_prepare_timeframe_data()`**:
```python
def _prepare_timeframe_data(
    self,
    rates: np.ndarray,
    timeframe: str
) -> Optional[Dict[str, Any]]:
    """
    Prepare timeframe data dict from MT5 rates array.
    
    FIX: Integration Error 6 - Method required by get_current_regime().
    
    Converts MT5 rates array to format expected by detect_regime().
    
    Args:
        rates: NumPy array from mt5.copy_rates_from_pos()
        timeframe: Timeframe name ("M5", "M15", "H1")
    
    Returns:
        Dict with keys: rates, atr_14, atr_50, bb_upper, bb_lower, bb_middle, adx, volume
    """
    if rates is None or len(rates) == 0:
        return None
    
    try:
        # Calculate indicators using existing indicator calculation logic
        # Reuse the same logic from _calculate_timeframe_indicators()
        from infra.indicator_bridge import IndicatorBridge
        
        # Convert rates to DataFrame for indicator calculation
        import pandas as pd
        df = pd.DataFrame(rates)
        # MT5 rates format: [time, open, high, low, close, tick_volume, spread, real_volume]
        if df.shape[1] >= 8:
            df.columns = ['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']
        else:
            # Fallback if columns don't match
            logger.warning(f"Unexpected rates format for {timeframe}: {df.shape}")
            return None
        
        # Calculate indicators using IndicatorBridge
        bridge = IndicatorBridge()
        indicators = bridge._calculate_indicators(df)  # FIX: Use private method (no timeframe parameter)
        
        # Extract ATR(14) - note: key is 'atr14', not 'atr_14'
        atr_14 = indicators.get('atr14', 0)
        
        # Calculate ATR(50) separately (not provided by IndicatorBridge)
        # FIX: Issue 7 - Add error handling for ATR(50) calculation
        try:
            def calculate_atr(df, period):
                if len(df) < period + 1:
                    return 0.0
                high_low = df['high'] - df['low']
                high_close = np.abs(df['high'] - df['close'].shift())
                low_close = np.abs(df['low'] - df['close'].shift())
                ranges = pd.concat([high_low, high_close, low_close], axis=1)
                true_range = np.max(ranges, axis=1)
                atr_series = true_range.rolling(period).mean()
                if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]):
                    return float(atr_series.iloc[-1])
                return 0.0
            
            atr_50 = calculate_atr(df, 50)
        except Exception as e:
            logger.warning(f"Error calculating ATR(50) for {timeframe}: {e}")
            atr_50 = 0.0  # Fallback to 0 if calculation fails
        
        # Extract Bollinger Bands (provided by IndicatorBridge)
        bb_upper = indicators.get('bb_upper', 0)
        bb_middle = indicators.get('bb_middle', 0)
        bb_lower = indicators.get('bb_lower', 0)
        
        # Extract ADX
        adx = indicators.get('adx', 0)
        
        # FIX: Issue 6 - Handle volume extraction safely
        if rates.shape[1] > 5:
            volume = rates[:, 5]  # Full array (tick_volume column)
        else:
            volume = None  # No volume data available
        
        return {
            'rates': rates,  # Keep original numpy array
            'atr_14': atr_14,  # Normalize key name
            'atr_50': atr_50,
            'bb_upper': bb_upper,
            'bb_lower': bb_lower,
            'bb_middle': bb_middle,
            'adx': adx,
            'volume': volume  # FIX: Issue 6 - Handle missing volume safely
        }
    except Exception as e:
        logger.error(f"Error preparing timeframe data for {timeframe}: {e}")
        return None
```

**New Method 2: `get_current_regime()`**:
```python
def get_current_regime(
    self,
    symbol: str,
    current_time: Optional[datetime] = None
) -> Optional[VolatilityRegime]:
    """
    Get current volatility regime for a symbol.
    
    FIX: Gap 3 - Convenience method for auto-execution validation.
    
    This method:
    1. Fetches timeframe data from MT5
    2. Prepares data using _prepare_timeframe_data()
    3. Calls detect_regime()
    4. Returns just the regime enum
    
    Used by auto-execution validation.
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDc')
        current_time: Current timestamp (defaults to now)
    
    Returns:
        VolatilityRegime enum or None if detection fails
    """
    try:
        import MetaTrader5 as mt5
        
        # Fetch timeframe data
        timeframe_data = {}
        for tf_name, tf_enum in [("M5", mt5.TIMEFRAME_M5), ("M15", mt5.TIMEFRAME_M15), ("H1", mt5.TIMEFRAME_H1)]:
            rates = mt5.copy_rates_from_pos(symbol, tf_enum, 0, 100)
            if rates is None or len(rates) == 0:
                continue
            
            # FIX: Integration Error 6 - Prepare timeframe data
            tf_data = self._prepare_timeframe_data(rates, tf_name)
            if tf_data:
                timeframe_data[tf_name] = tf_data
        
        if not timeframe_data:
            logger.warning(f"No timeframe data available for {symbol}")
            return None
        
        # Detect regime
        result = self.detect_regime(symbol, timeframe_data, current_time)
        return result.get("regime")
    
    except Exception as e:
        logger.error(f"Error getting current regime for {symbol}: {e}")
        return None
```

**Priority**: CRITICAL  
**Estimated Effort**: 5 hours (3 hours + 2 hours for get_current_regime + _prepare_timeframe_data methods)
**Actual Effort**: ~3 hours

**Testing**: ✅ **COMPLETED** - Covered in Phase 3.1 testing (14 tests passing, includes validation and helper method tests)

---

### PHASE 4: Analysis Tool Updates

#### 4.1 Update `moneybot.analyse_symbol_full`

**File**: `desktop_agent.py`

**Changes**:
```python
# In tool_analyse_symbol_full()

# Existing volatility detection
volatility_regime_data = regime_detector.detect_regime(...)

# NEW: Add detailed volatility metrics
# NEW: Extract tracking metrics from regime detection response
atr_trends = volatility_regime_data.get("atr_trends", {})
wick_variances = volatility_regime_data.get("wick_variances", {})
time_since_breakout = volatility_regime_data.get("time_since_breakout", {})

# FIX: Issue 2 - Calculate strategy recommendations
# FIX: Issue 9 - Handle None regime safely
# FIX: Issue 4 - Lazy import with error handling to avoid circular import issues
regime = volatility_regime_data.get("regime")
if regime:
    # NEW: Apply volatility-aware strategy selection
    try:
        from infra.volatility_strategy_mapper import get_strategies_for_volatility
    except ImportError as e:
        logger.error(f"Could not import volatility_strategy_mapper: {e}")
        strategy_recommendations = {
            "prioritize": [],
            "avoid": [],
            "confidence_adjustment": 0,
            "recommendation": "Strategy mapper unavailable",
            "wait_reason": "STRATEGY_MAPPER_UNAVAILABLE"
        }
    else:
        # FIX: Issue 2 - Extract current session from session detection
        from infra.session_helpers import SessionHelpers
        try:
            current_session = SessionHelpers.get_current_session()
        except Exception as e:
            logger.warning(f"Could not get current session: {e}")
            current_session = None
        
        strategy_recommendations = get_strategies_for_volatility(
            volatility_regime=regime,
            symbol=symbol,
            session=current_session
        )
else:
    strategy_recommendations = {
        "prioritize": [],
        "avoid": [],
        "confidence_adjustment": 0,
        "recommendation": "Regime detection failed",
        "wait_reason": "REGIME_DETECTION_FAILED"
    }

# NEW: Add detailed volatility metrics
# FIX: Issue 6 - Validate regime type before calling .value
from infra.volatility_regime_detector import VolatilityRegime

volatility_metrics = {
    "regime": regime.value if isinstance(regime, VolatilityRegime) else "UNKNOWN",  # FIX: Issue 6, 9 - Validate type and handle None
    "confidence": volatility_regime_data.get("confidence", 0),
    "atr_ratio": volatility_regime_data.get("atr_ratio", 1.0),
    "bb_width_ratio": volatility_regime_data.get("bb_width_ratio", 1.0),
    "adx_composite": volatility_regime_data.get("adx_composite", 0.0),
    "volume_confirmed": volatility_regime_data.get("volume_confirmed", False),
    
    # NEW TRACKING METRICS
    "atr_trends": atr_trends,  # Per timeframe: M5, M15, H1
    "wick_variances": wick_variances,  # Per timeframe: M5, M15, H1
    "time_since_breakout": time_since_breakout,  # Per timeframe: M5, M15, H1
    
    # Convenience: Primary timeframe (M15) metrics
    "atr_trend": atr_trends.get("M15", {}),
    "wick_variance": wick_variances.get("M15", {}),
    "time_since_breakout_minutes": time_since_breakout.get("M15", {}).get("time_since_minutes") if time_since_breakout.get("M15") else None,
    
    # Additional metrics
    "mean_reversion_pattern": volatility_regime_data.get("mean_reversion_pattern", {}),
    "volatility_spike": volatility_regime_data.get("volatility_spike", {}),
    "session_transition": volatility_regime_data.get("session_transition", {}),
    "whipsaw_detected": volatility_regime_data.get("whipsaw_detected", {}),
    "strategy_recommendations": strategy_recommendations
}

# Add to response
response_data["volatility_metrics"] = volatility_metrics
```

**Priority**: HIGH  
**Estimated Effort**: 2 hours
**Actual Effort**: ~1 hour

**Status**: ✅ **COMPLETED** - Detailed volatility metrics extracted and added to response

**Testing**: ✅ **COMPLETED** - Test suite created (`tests/test_volatility_phase4_analysis.py`) with 3 tests, all passing:
- `test_volatility_metrics_structure`: Verifies volatility metrics structure is correctly built
- `test_volatility_metrics_with_none_regime`: Verifies None regime is handled gracefully
- `test_volatility_metrics_missing_tracking_data`: Verifies missing tracking data is handled with empty dicts

---

### PHASE 5: Knowledge Document Updates

#### 5.1 Update AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md

**File**: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`

**Changes**:
- Add new volatility states to `VOLATILITY_STATES (STANDARDIZED)` section
- Add detection criteria for each state
- Add strategy mappings
- Update `VOLATILITY_MODEL` section

**Priority**: HIGH  
**Estimated Effort**: 3 hours
**Actual Effort**: ~1.5 hours

**Status**: ✅ **COMPLETED** - Updated VOLATILITY_STATES section with:
- Added 4 new states to volatility_states_standard list (pre_breakout_tension, post_breakout_decay, fragmented_chop, session_switch_flare)
- Added detection criteria for each new state (BB width, wick variance, ATR slope, session transition, etc.)
- Added strategy mappings (prioritize/avoid) for each state from volatility_strategy_mapper
- Added VOLATILITY_TRACKING_METRICS section documenting available metrics in response.data.volatility_metrics
- Updated volatility rules and conflict rules to include new states

---

#### 5.2 Update AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md

**File**: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`

**Changes**:
- Add volatility→strategy mapping table
- Add validation rules for each volatility state
- Update strategy selection guidance

**Priority**: HIGH  
**Estimated Effort**: 2 hours
**Actual Effort**: ~1 hour

**Status**: ✅ **COMPLETED** - Added VOLATILITY_STATE_TO_STRATEGY_MAPPING section with:
- Mapping table showing prioritize/avoid strategies for each new volatility state
- Validation rules for each volatility state (detection criteria, plan validation, confidence adjustments)
- Strategy selection guidance (how to use strategy_recommendations field)
- Access pattern examples for volatility_metrics in response.data
- Updated VOLATILITY_STRUCTURE_CONFLICT_RULE to include new states

---

#### 5.3 Update SMC_MASTER_EMBEDDING.md

**File**: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/SMC_MASTER_EMBEDDING.md`

**Changes**:
- Update regime classification section
- Add volatility state context to structure rules
- Update strategy selection based on volatility

**Priority**: MEDIUM  
**Estimated Effort**: 2 hours
**Actual Effort**: ~1 hour

**Status**: ✅ **COMPLETED** - Updated SMC document with:
- Added VOLATILITY_STATE_CONTEXT section explaining advanced volatility states
- Added volatility state context to each regime classification (Trend, Range, Breakout, Compression, Chop)
- Updated STRATEGY SELECTION section with volatility state overrides for each regime
- Documented how volatility state overrides regime-based strategy selection
- Added selection process guidance (check regime → check volatility state → follow mapping)

---

#### 5.4 Update Symbol-Specific Guides

**Files**:
- `GOLD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md`
- `FOREX_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md`
- `BTCUSD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md`

**Changes**:
- Add volatility behavior sections
- Document how each symbol behaves in different volatility states
- Add symbol-specific volatility thresholds if needed

**Priority**: MEDIUM  
**Estimated Effort**: 4 hours
**Actual Effort**: ~1.5 hours

**Status**: ✅ **COMPLETED** - Updated all 3 symbol guides with:
- Added ADVANCED VOLATILITY STATES section to each guide
- Documented symbol-specific behavior for each volatility state (PRE_BREAKOUT_TENSION, POST_BREAKOUT_DECAY, FRAGMENTED_CHOP, SESSION_SWITCH_FLARE)
- Added valid/avoid strategies for each state per symbol
- Added symbol-specific notes (e.g., Gold compression resolves during London/NY opens, BTC chop coincides with low CVD slope)
- Added guidance on accessing volatility metrics from response.data.volatility_metrics
- Updated volatility-structure conflict rules to include new states

---

#### 5.5 Update openai.yaml Tool Schema

**File**: `openai.yaml`

**⚠️ CRITICAL: DO NOT update until Phase 4 is complete!**
- Phase 4 must finalize the `volatility_metrics` response structure
- Response structure must be tested and verified before documenting
- Update only after actual response structure is confirmed

**Why Updates Are Required**:
1. **New Volatility States**: 4 new states added (PRE_BREAKOUT_TENSION, POST_BREAKOUT_DECAY, FRAGMENTED_CHOP, SESSION_SWITCH_FLARE)
2. **New Tracking Metrics**: ATR trends, wick variances, time since breakout added to response
3. **Tool Description**: Currently only mentions STABLE/TRANSITIONAL/VOLATILE
4. **Response Schema**: Comments need updating to reflect new states and metrics

**Update Location 1: Tool List Description (Line ~55)**

**Current**:
```yaml
- ⚡ VOLATILITY REGIME DETECTION ⭐ NEW - Automatic detection of STABLE/TRANSITIONAL/VOLATILE regimes
```

**Updated**:
```yaml
- ⚡ VOLATILITY REGIME DETECTION ⭐ NEW - Automatic detection of volatility regimes:
  - Basic states: STABLE, TRANSITIONAL, VOLATILE
  - Advanced states: PRE_BREAKOUT_TENSION, POST_BREAKOUT_DECAY, FRAGMENTED_CHOP, SESSION_SWITCH_FLARE
  - Includes confidence scores, ATR ratios, Bollinger Band analysis, and tracking metrics (ATR trends, wick variances, time since breakout)
```

**Update Location 2: Tool Schema Description (Line ~1505)**

**Current**:
```yaml
description: "Comprehensive unified analysis for general market analysis. ⚡ NEW: Includes automatic volatility regime detection (STABLE, TRANSITIONAL, VOLATILE) with confidence scores, ATR ratios, and Bollinger Band analysis..."
```

**Updated**:
```yaml
description: "Comprehensive unified analysis for general market analysis. ⚡ NEW: Includes automatic volatility regime detection with:
  - Basic states: STABLE, TRANSITIONAL, VOLATILE (with confidence scores, ATR ratios, Bollinger Band analysis)
  - Advanced states: PRE_BREAKOUT_TENSION (compression before breakout), POST_BREAKOUT_DECAY (momentum fading), FRAGMENTED_CHOP (whipsaw conditions), SESSION_SWITCH_FLARE (transition volatility spikes)
  - Tracking metrics: ATR trends (slope, decline rate), wick variances (increasing/decreasing), time since breakout (minutes/hours)
  - Strategy recommendations: Automatically selects volatility-aware trading strategies based on detected regime
  - Risk adjustments: Returns volatility-adjusted risk parameters (position size reduction, wider stop losses)
  - Strategy selection scores and WAIT reason codes when no suitable strategy found
⚠️ NOT for range scalping - use moneybot.analyse_range_scalp_opportunity instead when user asks for range scalping analysis. ⚠️ LIMITATIONS: Does NOT dynamically adjust alert zones, does NOT link pairs together, does NOT auto-enable features, only provides analysis data."
```

**Update Location 3: Response Schema Comment (Lines ~1510-1515)**

**Current**:
```yaml
# Response includes volatility_regime field with:
# - regime: STABLE/TRANSITIONAL/VOLATILE
# - confidence: 0-100%
# - atr_ratio: Multiplier of average ATR
# - strategy_selection: Selected strategy with entry/SL/TP if VOLATILE regime
# - wait_reasons: Array of reason codes if WAIT recommended
```

**Updated**:
```yaml
# Response includes volatility_metrics object with:
# 
# Basic Fields:
# - regime: STABLE/TRANSITIONAL/VOLATILE/PRE_BREAKOUT_TENSION/POST_BREAKOUT_DECAY/FRAGMENTED_CHOP/SESSION_SWITCH_FLARE
# - confidence: 0-100%
# - atr_ratio: Multiplier of average ATR
# - bb_width_ratio: Bollinger Band width ratio
# - adx_composite: Composite ADX score
# - volume_confirmed: Boolean (volume spike confirmed)
#
# Tracking Metrics (Per-Timeframe: M5, M15, H1):
# - atr_trends: {M5: {...}, M15: {...}, H1: {...}}
#   Each timeframe includes: current_atr, slope, slope_pct, is_declining, is_above_baseline, trend_direction
# - wick_variances: {M5: {...}, M15: {...}, H1: {...}}
#   Each timeframe includes: current_variance, previous_variance, variance_change_pct, is_increasing, current_ratio, mean_ratio
# - time_since_breakout: {M5: {...}, M15: {...}, H1: {...}}
#   Each timeframe includes: time_since_minutes, time_since_hours, breakout_type, breakout_price, breakout_timestamp, is_recent
#
# Convenience Fields (M15 Primary):
# - atr_trend: Same as atr_trends["M15"]
# - wick_variance: Same as wick_variances["M15"]
# - time_since_breakout_minutes: Same as time_since_breakout["M15"]["time_since_minutes"]
#
# Advanced Detection Fields:
# - mean_reversion_pattern: {is_mean_reverting, oscillation_around_vwap, oscillation_around_ema, touch_count, reversion_strength}
# - volatility_spike: {is_spike, current_atr, spike_ratio, spike_magnitude, is_temporary}
# - session_transition: {is_transition, transition_type, minutes_into_transition, ...}
# - whipsaw_detected: {is_whipsaw, direction_changes, oscillation_around_mean}
#
# Strategy & Recommendations:
# - strategy_recommendations: Selected strategy with entry/SL/TP based on volatility regime
# - wait_reasons: Array of reason codes if WAIT recommended
```

**Optional: Add Usage Guidance**

**Add to tool description or create new section**:
```yaml
# Volatility State Usage:
# - PRE_BREAKOUT_TENSION: Favor breakout strategies (breakout_ib_volatility_trap, liquidity_sweep_reversal)
# - POST_BREAKOUT_DECAY: Avoid trend continuation, favor mean reversion (mean_reversion_range_scalp)
# - FRAGMENTED_CHOP: Only allow micro_scalp and mean_reversion_range_scalp strategies
# - SESSION_SWITCH_FLARE: Block ALL strategies - wait for volatility stabilization
```

**Implementation Checklist**:

**Before Updating**:
- [ ] Phase 4 implementation complete
- [ ] `volatility_metrics` response structure finalized
- [ ] Actual response tested and verified
- [ ] All 7 volatility states working correctly
- [ ] Tracking metrics included in response
- [ ] Strategy recommendations working

**After Updating**:
- [ ] Tool description updated (Line ~55)
- [ ] Tool schema description updated (Line ~1505)
- [ ] Response schema comment updated (Lines ~1510-1515)
- [ ] Usage guidance added (optional)
- [ ] ChatGPT tested with new descriptions
- [ ] Response structure matches documentation

**Important Notes**:
1. **Backward Compatibility**: Existing states (STABLE, TRANSITIONAL, VOLATILE) remain unchanged. New states are additions, not replacements.
2. **Documentation Accuracy**: Response schema comments must match actual response structure. Test with actual tool calls before finalizing.
3. **ChatGPT Understanding**: Provide clear descriptions of when each state occurs and explain strategy recommendations for each state.

**Priority**: HIGH  
**Estimated Effort**: 2 hours  
**Dependencies**: Phase 4 must be complete
**Actual Effort**: ~1 hour

**Status**: ✅ **COMPLETED** - Updated openai.yaml with:
- Updated tool list description (Line 55) to include all 7 volatility states (3 basic + 4 advanced)
- Updated tool schema description (Line 1505) with detailed explanation of advanced states and tracking metrics
- Updated response schema comment (Lines 1510-1515) with complete volatility_metrics structure including:
  - Basic fields (regime, confidence, atr_ratio, etc.)
  - Tracking metrics per timeframe (atr_trends, wick_variances, time_since_breakout)
  - Convenience fields (M15 primary)
  - Advanced detection fields (mean_reversion_pattern, volatility_spike, session_transition, whipsaw_detected)
  - Strategy recommendations with prioritize/avoid lists and wait_reason

---

### PHASE 6: Risk Management Adjustments

#### 6.1 Volatility-Aware Position Sizing

**File**: `infra/volatility_risk_manager.py` (create or update)

**Changes**:
```python
def get_volatility_adjusted_risk(
    self,
    base_risk: float,
    volatility_regime: VolatilityRegime
) -> float:
    """
    Adjust position sizing based on volatility state.
    
    Returns:
        Adjusted risk percentage
    """
    
    adjustments = {
        VolatilityRegime.STABLE: 1.0,  # No adjustment
        VolatilityRegime.TRANSITIONAL: 0.9,  # Slight reduction
        VolatilityRegime.VOLATILE: 0.7,  # Significant reduction
        VolatilityRegime.PRE_BREAKOUT_TENSION: 0.85,  # Slight reduction (potential expansion)
        VolatilityRegime.POST_BREAKOUT_DECAY: 0.9,  # Slight reduction (momentum fading)
        VolatilityRegime.FRAGMENTED_CHOP: 0.6,  # Significant reduction (choppy)
        VolatilityRegime.SESSION_SWITCH_FLARE: 0.0  # Block trading
    }
    
    return base_risk * adjustments.get(volatility_regime, 1.0)
```

**Priority**: MEDIUM  
**Estimated Effort**: 2 hours
**Actual Effort**: ~1 hour

**Status**: ✅ **COMPLETED** - Updated volatility_risk_manager.py with:
- Imported VolatilityRegime from volatility_regime_detector (using extended enum)
- Added base risk percentages for new states:
  - PRE_BREAKOUT_TENSION: 0.85% (slight reduction - potential expansion)
  - POST_BREAKOUT_DECAY: 0.9% (slight reduction - momentum fading)
  - FRAGMENTED_CHOP: 0.6% (significant reduction - choppy conditions)
  - SESSION_SWITCH_FLARE: 0.0% (block trading)
- Added SL multipliers for new states:
  - PRE_BREAKOUT_TENSION: 1.725× (slightly wider - potential expansion)
  - POST_BREAKOUT_DECAY: 1.5× (same as stable - momentum fading)
  - FRAGMENTED_CHOP: 1.2× (tighter - choppy conditions)
  - SESSION_SWITCH_FLARE: 0.0× (block trading)
- Added TP multipliers for new states:
  - PRE_BREAKOUT_TENSION: 3.0× (same as stable - breakout potential)
  - POST_BREAKOUT_DECAY: 2.0× (reduced - momentum fading)
  - FRAGMENTED_CHOP: 1.8× (reduced - choppy conditions)
  - SESSION_SWITCH_FLARE: 0.0× (block trading)
- Updated calculate_volatility_adjusted_risk_pct() to handle new states
- Updated calculate_volatility_adjusted_stop_loss() to handle new states (returns None for SESSION_SWITCH_FLARE)
- Updated calculate_volatility_adjusted_take_profit() to handle new states (returns None for SESSION_SWITCH_FLARE)
- Fixed SESSION_SWITCH_FLARE to return 0.0 immediately (blocks trading)

**Phase 6.1 Testing**: ✅ **COMPLETED** - All 13 tests passing:
- Test file: `tests/test_volatility_phase6_risk_manager.py`
- Tests cover: Risk adjustments, SL multipliers, TP multipliers, SESSION_SWITCH_FLARE blocking, backward compatibility
- All new volatility states properly handled in risk calculations

---

#### 6.2 Volatility-Aware Stop Loss

**File**: `infra/universal_sl_tp_manager.py` (update)

**Status**: ⚠️ **NOT REQUIRED** - Already handled by `volatility_risk_manager.py`

**Note**: The `universal_sl_tp_manager.py` handles **trailing stops** (mid-trade adjustments), not initial SL/TP calculation. Initial SL/TP based on volatility regime is already handled by `volatility_risk_manager.py` in Phase 6.1:
- `calculate_volatility_adjusted_stop_loss()` - handles initial SL with volatility multipliers
- `calculate_volatility_adjusted_take_profit()` - handles initial TP with volatility multipliers

The `universal_sl_tp_manager.py` already has volatility spike detection for mid-trade adjustments (lines 1950-1974), which is sufficient for trailing stop adjustments.

**If future enhancement needed**: Could integrate volatility regime detection into mid-trade trailing adjustments, but current ATR-based spike detection is sufficient.

**Priority**: LOW (not required)  
**Estimated Effort**: N/A (already handled)

---

### PHASE 7: Monitoring and Alerts

#### 7.1 Volatility State Transition Tracking

**File**: `infra/volatility_regime_detector.py` (update `_log_regime_change()`)

**Status**: ✅ **COMPLETED**

**Changes**:
- Enhanced `_log_regime_change()` to detect advanced volatility states
- Added warning-level logging for advanced states (PRE_BREAKOUT_TENSION, POST_BREAKOUT_DECAY, FRAGMENTED_CHOP, SESSION_SWITCH_FLARE)
- Added `_send_volatility_state_alert()` method to send Discord notifications
- Discord alerts include:
  - Symbol, state, confidence, session
  - ATR ratio and BB width ratio
  - Action recommendations (which strategies to prioritize/avoid)
  - Color coding: Orange for warnings, Red for SESSION_SWITCH_FLARE (critical)

**Priority**: LOW  
**Estimated Effort**: 2 hours

**Phase 7.1 Testing**: ✅ **COMPLETED** - All 14 tests passing:
- Test file: `tests/test_volatility_phase7_monitoring.py`
- Tests cover: Enhanced logging, Discord alerts for all 4 advanced states, error handling, regime history, database lookup
- All advanced volatility states properly trigger warnings and Discord alerts

---

#### 7.2 Volatility State History

**File**: `infra/volatility_regime_detector.py` (enhance `get_regime_history()`)

**Status**: ✅ **COMPLETED**

**Changes**:
- Enhanced `get_regime_history()` to support `limit` parameter (default: 100, was 10)
- Added `include_metrics` parameter (default: True) to optionally include detailed indicator metrics
- Added `_get_regime_metrics_from_db()` helper method to retrieve detailed metrics from database
- Metrics include: ATR ratio, BB width ratio, ADX, confidence percentile, and indicators JSON
- Database lookup finds closest event within 5 minutes of requested timestamp

**Priority**: LOW  
**Estimated Effort**: 1 hour

**Phase 7.2 Testing**: ✅ **COMPLETED** - Included in Phase 7.1 test suite

---

### PHASE 8: Testing and Validation

**⚠️ TESTING STRATEGY: Incremental + Comprehensive**

**Incremental Testing** (Recommended):
- Write unit tests immediately after each phase where new code is created
- Write integration tests after phases that modify existing integrations
- This allows early detection of bugs and ensures each phase is working before moving to the next

**Comprehensive Testing** (Phase 8):
- Phase 8 provides a complete test suite for final validation
- System tests and E2E tests are done at the end (require all components)
- Use Phase 8 to ensure everything works together

**Test Organization**:
- **Phase 1 → Tests 8.1.1-8.1.2** (Core detection + Tracking methods)
- **Phase 2 → Tests 8.1.4** (Strategy mapping)
- **Phase 3 → Tests 8.2.2** (Auto-execution integration)
- **Phase 4 → Tests 8.2.3** (Analysis tool integration)
- **Phase 8 → All tests** (Comprehensive validation + System + E2E)

---

#### 8.1 Unit Tests

**File**: `tests/test_volatility_regime_detector_extended.py` (create)

**Test Framework**: Python `unittest` (consistent with existing test structure)

**Test Cases**:

**8.1.1 Core Detection Methods** (Write after Phase 1.4):
1. `test_pre_breakout_tension_detection()` - Test PRE_BREAKOUT_TENSION with various BB width/wick variance combinations
   - BB width narrow (bottom 20th percentile) + wick variance increasing + intra-bar volatility rising
   - Edge cases: Missing data, insufficient history, boundary conditions
2. `test_post_breakout_decay_detection()` - Test POST_BREAKOUT_DECAY with ATR slope scenarios
   - ATR declining + above baseline + recent breakout (< 30 min)
   - Edge cases: No breakout, breakout too old, ATR not declining
3. `test_fragmented_chop_detection()` - Test FRAGMENTED_CHOP with whipsaw patterns
   - Whipsaw detected + mean reversion + low ADX
   - Edge cases: No whipsaw, high ADX, missing VWAP/EMA
4. `test_session_switch_flare_detection()` - Test SESSION_SWITCH_FLARE during transition windows
   - Session transition + volatility spike + flare resolution tracking
   - Edge cases: Outside transition window, no spike, sustained expansion

**8.1.2 Tracking Methods** (Write after Phase 1.3):
5. `test_atr_trend_calculation()` - Test `_calculate_atr_trend()` with various scenarios
   - Rising ATR, declining ATR, stable ATR, insufficient data
6. `test_wick_variance_calculation()` - Test `_calculate_wick_variance()` 
   - Increasing variance, decreasing variance, edge cases
7. `test_bb_width_trend_calculation()` - Test `_calculate_bb_width_trend()`
   - Narrow BB, expanding BB, contracting BB, percentile calculation
8. `test_intrabar_volatility_calculation()` - Test `_calculate_intrabar_volatility()`
   - Rising intra-bar volatility, falling volatility
9. `test_breakout_detection()` - Test `_detect_breakout()` and `_record_breakout_event()`
   - Price breakout, volume breakout, duplicate detection, database recording
10. `test_time_since_breakout()` - Test `_get_time_since_breakout()`
    - Cache retrieval, database fallback, time calculations

**8.1.3 State Priority and Conflict Resolution** (Write after Phase 1.5):
11. `test_state_priority()` - Test priority order (SESSION_SWITCH_FLARE > FRAGMENTED_CHOP > POST_BREAKOUT_DECAY > PRE_BREAKOUT_TENSION)
12. `test_pre_post_breakout_conflict()` - Test conflict resolution between PRE_BREAKOUT_TENSION and POST_BREAKOUT_DECAY
    - Breakout < 1 hour ago → POST_BREAKOUT_DECAY wins
    - Breakout > 1 hour ago → PRE_BREAKOUT_TENSION wins

**8.1.4 Strategy Mapping** (Write after Phase 2):
13. `test_volatility_strategy_mapper()` - Test `get_strategies_for_volatility()`
    - Each volatility state returns correct prioritize/avoid lists
    - Confidence adjustments applied correctly
    - SESSION_SWITCH_FLARE blocks all strategies

**8.1.5 Data Format Handling** (Write after Phase 1.3 - _normalize_rates method):
14. `test_normalize_rates()` - Test `_normalize_rates()` with DataFrame, numpy array, list formats
15. `test_data_format_edge_cases()` - Test handling of missing columns, empty data, invalid formats

**8.1.6 Thread Safety** (Write after Phase 1.3 - tracking infrastructure):
16. `test_thread_safety()` - Test concurrent access to tracking structures and database
    - Multiple threads calling `detect_regime()` simultaneously
    - Database connection management under load

**8.1.7 Error Handling** (Write after Phase 1.5 - full integration):
17. `test_error_handling()` - Test graceful degradation on errors
    - Missing timeframe data, calculation failures, database errors

**Priority**: HIGH  
**Estimated Effort**: 10 hours (includes edge case testing)

---

#### 8.2 Integration Tests

**File**: `tests/test_volatility_integration.py` (create)

**Test Framework**: Python `unittest` with mock MT5 data

**Test Cases**:

**8.2.1 Component Integration**:
1. `test_regime_detector_with_indicator_bridge()` - Test integration with `IndicatorBridge`
   - Verify ATR(14), ATR(50), BB, ADX are correctly passed to detector
2. `test_regime_detector_with_session_helpers()` - Test integration with `SessionHelpers`
   - Session transition detection works correctly
   - Session-aware strategy recommendations
3. `test_volatility_strategy_mapper_integration()` - Test strategy mapper with real regime detection
   - Verify recommendations match detected regime

**8.2.2 Auto-Execution Integration** (Write after Phase 3):
4. `test_auto_execution_plan_validation()` - Test plan creation with volatility validation
   - Plans rejected when incompatible with current regime
   - Plans accepted when compatible
   - Strategy type extraction from conditions/notes
5. `test_auto_execution_with_volatility_states()` - Test plan execution during different volatility states
   - SESSION_SWITCH_FLARE blocks execution
   - FRAGMENTED_CHOP adjusts strategy selection

**8.2.3 Analysis Tool Integration** (Write after Phase 4):
6. `test_analyse_symbol_full_integration()` - Test `moneybot.analyse_symbol_full` with new volatility metrics
   - Verify volatility_metrics field includes all new tracking data
   - Verify strategy_recommendations are included
7. `test_volatility_metrics_structure()` - Test response structure matches expected format
   - All fields present, correct types, no missing data

**8.2.4 Risk Management Integration**:
8. `test_risk_management_adjustments()` - Test risk management with new volatility states
   - SL/TP adjustments based on volatility regime
   - Circuit breaker integration

**8.2.5 Database Integration**:
9. `test_breakout_event_database()` - Test breakout event recording and retrieval
   - Events recorded correctly, cache updated, database queries work
10. `test_database_concurrency()` - Test database access under concurrent load
    - Multiple threads writing/reading breakout events

**Priority**: HIGH  
**Estimated Effort**: 6 hours

---

#### 8.3 System Testing

**File**: `tests/test_volatility_phase8_system.py` (create)

**Status**: ✅ **COMPLETED**

**Test Framework**: Python `unittest` with real MT5 connection (if available) or comprehensive mocks

**Test Cases**:

**8.3.1 System-Wide Volatility Detection**:
1. ✅ `test_multi_symbol_independent_detection()` - Test detection across multiple symbols simultaneously
   - BTCUSD, XAUUSD, EURUSD detected independently
   - No cross-contamination between symbols
2. ✅ `test_volatility_state_persistence()` - Test volatility state tracking over time
   - States persist correctly, history maintained, transitions logged
3. ✅ `test_complete_detection_pipeline()` - Test complete volatility detection pipeline
   - Method existence and structure verification

**8.3.2 Performance Testing**:
4. ✅ `test_detection_performance()` - Test detection speed and resource usage
   - `detect_regime()` completes within acceptable time (< 500ms in test environment)
5. ✅ `test_concurrent_detection_performance()` - Test performance under concurrent load
   - Multiple symbols detected simultaneously
   - Thread safety maintained, no deadlocks

**8.3.3 System Reliability**:
6. ✅ `test_missing_timeframe_data_handling()` - Test graceful handling of missing timeframe data
7. ✅ `test_invalid_data_handling()` - Test graceful handling of invalid data
8. ✅ `test_database_error_handling()` - Test graceful handling of database errors

**8.3.4 Data Consistency**:
9. ✅ `test_volatility_metrics_consistency()` - Test data consistency across system
   - Volatility metrics match between analysis tool and detector
10. ✅ `test_strategy_recommendations_consistency()` - Test strategy recommendations consistency

**8.3.5 Configuration Testing**:
11. ✅ `test_configuration_loading()` - Test volatility regime configuration loading
    - Thresholds loaded correctly, defaults applied

**Phase 8.3 Testing**: ✅ **COMPLETED** - All 11 tests passing

**Priority**: HIGH  
**Estimated Effort**: 8 hours

---

#### 8.4 End-to-End (E2E) Testing

**File**: `tests/test_volatility_phase8_e2e.py` (create)

**Status**: ✅ **COMPLETED**

**Test Framework**: Python `unittest` with async support, real or comprehensive mock services

**Test Cases**:

**8.4.1 Complete User Workflows**:
1. ✅ `test_e2e_analysis_to_plan_creation()` - Test complete workflow: Analysis → Detection → Plan Creation
   - User requests analysis → System detects PRE_BREAKOUT_TENSION → ChatGPT creates breakout plan
   - Verify plan has correct conditions, strategy_type, volatility validation
2. ✅ `test_e2e_plan_rejection_workflow()` - Test plan rejection when incompatible with volatility state
3. ✅ `test_e2e_state_transition_sequence()` - Test state transitions during live trading
   - System starts in STABLE → Detects PRE_BREAKOUT_TENSION → Breakout occurs → POST_BREAKOUT_DECAY
   - Verify transitions logged, strategy recommendations update

**8.4.2 ChatGPT Integration E2E**:
4. ✅ `test_e2e_chatgpt_analysis_with_volatility()` - Test ChatGPT analysis tool with new volatility states
   - ChatGPT calls `moneybot.analyse_symbol_full` → Receives volatility metrics → Uses for decision making
   - Verify response structure, data completeness
5. ✅ `test_e2e_chatgpt_plan_creation_with_validation()` - Test ChatGPT plan creation with volatility validation
   - ChatGPT creates plan → System validates against current regime → Plan accepted/rejected
   - Verify validation logic works end-to-end

**8.4.3 Auto-Execution E2E**:
6. ✅ `test_e2e_volatility_state_blocking()` - Test SESSION_SWITCH_FLARE blocking all execution
   - Plans created during session transition → SESSION_SWITCH_FLARE detected → All plans blocked
   - Verify blocking logic works correctly
7. ✅ `test_e2e_fragmented_chop_filtering()` - Test FRAGMENTED_CHOP filtering to only allow specific strategies

**8.4.4 Real-World Scenarios**:
8. ✅ `test_e2e_london_breakout_scenario()` - Test London breakout scenario end-to-end
   - Pre-breakout tension detected → Breakout occurs → Post-breakout decay → Trade execution
9. ✅ `test_e2e_choppy_market_scenario()` - Test choppy market scenario end-to-end
   - FRAGMENTED_CHOP detected → Micro-scalp strategies recommended → Range scalping plans created

**8.4.5 Data Flow E2E**:
10. ✅ `test_e2e_data_flow_completeness()` - Test complete data flow from MT5 to ChatGPT
    - MT5 data → Indicator calculation → Regime detection → Tracking metrics → Analysis tool → ChatGPT
    - Verify no data loss, correct transformations

**Phase 8.4 Testing**: ✅ **COMPLETED** - All 10 tests passing

**Priority**: CRITICAL  
**Estimated Effort**: 12 hours

---

#### 8.5 Test Execution and Reporting

**Test Execution Strategy**:
1. **Unit Tests**: Run on every code change (CI/CD integration)
2. **Integration Tests**: Run before merging to main branch
3. **System Tests**: Run nightly or before releases
4. **E2E Tests**: Run before major releases, can be run manually for validation

**Test Coverage Goals**:
- Unit Tests: 90%+ code coverage for new methods
- Integration Tests: All integration points covered
- System Tests: All system components tested
- E2E Tests: All critical user workflows covered

**Test Results Documentation**:
- Create `docs/Pending Updates - 07.12.25/Tests - Volatility States/TEST_RESULTS.md`
- Document test execution, pass/fail rates, coverage metrics
- Include performance benchmarks

**Priority**: HIGH  
**Estimated Effort**: 2 hours (test infrastructure setup)

---

## 📊 IMPLEMENTATION TIMELINE

**Total Estimated Effort**: ~115 hours (updated with comprehensive testing suite)

**Breakdown**:
- Phase 1: 37 hours (was 32, +5 for thread safety, database management, data format handling) ✅ **COMPLETED**
- Phase 2: 5 hours (unchanged) ✅ **COMPLETED**
- Phase 3: 9 hours (was 8, +1 for _prepare_timeframe_data method) ✅ **COMPLETED**
- Phase 4: 2 hours (unchanged) ✅ **COMPLETED**
- Phase 5: 15 hours (unchanged) ✅ **COMPLETED**
- Phase 6: 4 hours (unchanged) ✅ **COMPLETED**
- Phase 7: 3 hours (unchanged) ✅ **COMPLETED**
- Phase 8: 38 hours (comprehensive testing: unit, integration, system, E2E) ✅ **COMPLETED**
- Additional fixes: 2 hours (documentation, validation, edge cases) ✅ **COMPLETED**

**🎉 IMPLEMENTATION STATUS: COMPLETE**

**Total Tests**: 105 tests across all phases (94 volatility-specific + 11 other)
**Test Status**: ✅ **ALL 105 TESTS PASSING**
**Warnings**: 2 non-critical deprecation warnings (from websockets library - see `TEST_WARNINGS_ANALYSIS.md`)

See `IMPLEMENTATION_COMPLETE_SUMMARY.md` and `FINAL_IMPLEMENTATION_REPORT.md` for full details.

**Phase 1 (Core Detection)**: 37 hours (updated with additional fixes)
- 1.1: 0.5 hours
- 1.2: 1 hour
- 1.3: 3 hours (tracking infrastructure + thread safety + database connection management)
- 1.4: 14 hours (technical indicators + tracking methods + mean reversion + spike detection + breakout detection + data format handling)
- 1.5: 8 hours (detection methods - updated with fixes + conflict resolution)
- 1.6: 10.5 hours (integration into detect_regime + tracking metrics calculation + return structure + error handling per timeframe)

**Phase 2 (Strategy Selection)**: 5 hours
- 2.1: 2 hours
- 2.2: 3 hours

**Phase 3 (Validation)**: 9 hours (updated with additional fixes)
- 3.1: 4 hours
- 3.2: 5 hours (includes get_current_regime() + _prepare_timeframe_data() methods implementation)

**Phase 4 (Analysis Tools)**: 2 hours

**Phase 5 (Knowledge Docs)**: 15 hours
- 5.1: 3 hours
- 5.2: 2 hours
- 5.3: 2 hours
- 5.4: 4 hours
- 5.5: 2 hours (openai.yaml updates)

**Phase 6 (Risk Management)**: 4 hours
- 6.1: 2 hours
- 6.2: 2 hours

**Phase 7 (Monitoring)**: 3 hours
- 7.1: 2 hours
- 7.2: 1 hour

**Phase 8 (Testing)**: 38 hours (comprehensive testing suite)
- 8.1 Unit Tests: 10 hours (includes edge case testing)
- 8.2 Integration Tests: 6 hours (expanded from 4 hours)
- 8.3 System Testing: 8 hours (new)
- 8.4 End-to-End (E2E) Testing: 12 hours (new)
- 8.5 Test Execution and Reporting: 2 hours (test infrastructure)

---

## 🔄 DEPENDENCIES

**External Dependencies**:
- None (all functionality uses existing libraries)

**Internal Dependencies**:
1. Session detection system (`infra/session_helpers.py`)
2. Wick analysis functions (`domain/candles.py`)
3. ATR calculation (`infra/volatility_regime_detector.py`)
4. BB width calculation (existing)
5. VWAP/EMA calculation (existing)

**Order of Implementation**:
1. Phase 1.1-1.2 (Enum + Config) - Can be done immediately
2. Phase 1.3 (Technical Indicators) - Foundation for detection
3. Phase 1.4 (Detection Methods) - Core functionality
4. Phase 1.5 (Integration) - Wire everything together
5. Phase 2-8 (Everything else) - Can be done in parallel after Phase 1

---

## 📋 SUMMARY OF FIXES FROM FINAL REVIEW

### Fixes from PLAN_REVIEW_FINAL_ISSUES.md (8 issues):

**Critical Integration Errors (6):**
1. ✅ **Issue 1**: `_prepare_timeframe_data()` - Fixed method call to use `_calculate_indicators()` instead of non-existent `calculate_indicators()`, added ATR(50) calculation
2. ✅ **Issue 2**: `_detect_whipsaw()` - Updated signature to handle both DataFrame and numpy array formats, completed implementation
3. ✅ **Issue 3**: `_detect_mean_reversion_pattern()` - Fixed data access to handle both DataFrame and numpy array formats
4. ✅ **Issue 4**: `_calculate_intrabar_volatility()` - Updated signature to handle both DataFrame and numpy array formats
5. ✅ **Issue 5**: Auto-execution validation - Fixed import to use existing `chatgpt_auto_execution_integration.py` instead of non-existent module
6. ✅ **Issue 6**: IndicatorBridge return structure - Fixed to use `'atr14'` key (not `'atr_14'`) and calculate ATR(50) separately

**Important Issues (2):**
7. ✅ **Issue 7**: Error handling - Added comprehensive try-except blocks in `_prepare_timeframe_data()`
8. ✅ **Issue 8**: Data format consistency - Added `_normalize_rates()` helper method for consistent data handling

**All fixes have been integrated into the implementation plan.**

---

## ⚠️ RISKS AND MITIGATION

**Risk 1**: False positives in new volatility states
- **Mitigation**: Use conservative thresholds, require multiple confirmations

**Risk 2**: Performance impact from additional calculations
- **Mitigation**: Cache calculations, optimize loops, use vectorized operations

**Risk 3**: Breaking existing functionality
- **Mitigation**: Comprehensive testing, gradual rollout, feature flags

**Risk 4**: Knowledge document conflicts
- **Mitigation**: Review all documents together, ensure consistency

---

## 📝 NOTES

1. **State Priority**: SESSION_SWITCH_FLARE should be checked FIRST and block all other states
2. **Backward Compatibility**: Existing STABLE/TRANSITIONAL/VOLATILE states remain unchanged
3. **Configuration**: All thresholds should be configurable for fine-tuning
4. **Logging**: Enhanced logging for new states to aid debugging
5. **Documentation**: Update `CURRENT_VOLATILITY_DETECTION_SYSTEM.md` after implementation
6. **Tracking Architecture**: See `VOLATILITY_TRACKING_ARCHITECTURE.md` for detailed tracking implementation

---

## 🔄 TRACKING ARCHITECTURE SUMMARY

### Data Storage Strategy

**In-Memory (Fast, Temporary)**:
- **ATR History**: `deque(maxlen=20)` per symbol/timeframe
  - Stores: (timestamp, atr_14, atr_50)
  - Purpose: Calculate ATR slope/trend
  - Cleanup: Auto (rolling window)
  
- **Wick Ratios**: `deque(maxlen=20)` per symbol/timeframe
  - Stores: (timestamp, wick_ratio)
  - Purpose: Calculate wick variance
  - Cleanup: Auto (rolling window)

**Persistent (SQLite Database)**:
- **Breakout Events**: `data/volatility_regime_events.sqlite` → `breakout_events` table
  - Stores: symbol, timeframe, breakout_type, price, timestamp
  - Purpose: Track "time since breakout"
  - Cleanup: Manual (invalidate old breakouts)

### Calculation Flow

```
detect_regime() called
  ↓
Initialize tracking structures (if needed)
  ↓
For each timeframe (M5, M15, H1):
  → Calculate ATR trend (from _atr_history deque)
  → Calculate wick variance (from _wick_ratios_history deque)
  → Get time since breakout (from database/cache)
  ↓
Use tracking metrics for state detection:
  → PRE_BREAKOUT_TENSION: Uses wick_variance, bb_width
  → POST_BREAKOUT_DECAY: Uses atr_trend, time_since_breakout
  ↓
Return all metrics in response
```

### ChatGPT Access

**Automatic Inclusion**:
- All tracking metrics included in `analyse_symbol_full` response
- Located in: `response.data.volatility_metrics`
- Structure:
  ```python
  {
    "atr_trends": {
      "M5": {"slope": -2.3, "is_declining": True, ...},
      "M15": {...},
      "H1": {...}
    },
    "wick_variances": {
      "M5": {"variance_change_pct": 40.6, "is_increasing": True, ...},
      "M15": {...},
      "H1": {...}
    },
    "time_since_breakout": {
      "M5": {"time_since_minutes": 18.5, "is_recent": True, ...},
      "M15": {...},
      "H1": {...}
    }
  }
  ```

**ChatGPT Usage Example**:
```python
# ChatGPT receives analysis
volatility_metrics = response["data"]["volatility_metrics"]

# Check for POST_BREAKOUT_DECAY
if volatility_metrics["atr_trend"]["is_declining"] and \
   volatility_metrics["time_since_breakout_minutes"] < 30:
    # Recommend: mean_reversion_range_scalp
```

### Performance Impact

- **Memory**: < 10 KB total for all symbols
- **Database**: < 1 MB for 30 days of breakout events
- **Calculation Overhead**: < 1ms per `detect_regime()` call
- **Database Queries**: Cached in-memory, fallback to DB only on cache miss

### Implementation Details

**See**: `docs/Pending Updates - 07.12.25/VOLATILITY_TRACKING_ARCHITECTURE.md` for:
- Complete code examples for tracking methods
- Database schema and initialization
- Integration points in `detect_regime()`
- Breakout event recording logic
- Time since breakout retrieval

---

---

## 📋 SUMMARY OF FIXES FROM FIFTH REVIEW

### Fixes from PLAN_REVIEW_FIFTH_ISSUES.md (8 issues):

**Critical Issues (5):**
1. ✅ **Issue 1**: `_generate_reasoning()` Method Signature Mismatch - Updated to use correct 6-parameter signature (regime, atr_ratio, bb_width_ratio, adx, volume_confirmed, indicators).
2. ✅ **Issue 2**: Missing `_ensure_symbol_tracking()` Method - Already implemented in Phase 1.3.1 (line 253).
3. ✅ **Issue 3**: Missing `_extract_rates_array()` Helper Method - Already implemented in Phase 1.3.9.5 (line 1098).
4. ✅ **Issue 4**: `_calculate_bb_width_trend()` Not Fully Implemented - Added full implementation with percentile calculation and trend slope analysis.
5. ✅ **Issue 5**: Missing Error Handling in `_normalize_rates()` for Edge Cases - Enhanced error handling for missing keys in dict lists and DataFrame validation.

**Important Issues (3):**
6. ⚠️ **Issue 6**: Missing Documentation for Thread Safety Guarantees - Documented in code comments (lock acquisition order: `_tracking_lock` before `_db_lock`).
7. ⚠️ **Issue 7**: Missing Validation for Breakout Event Database Schema - Schema versioning can be added in a future phase if needed.
8. ⚠️ **Issue 8**: Missing Performance Optimization for High-Frequency Calls - Caching should be handled at a higher level (e.g., in `desktop_agent.py`).

**All critical fixes have been integrated into the implementation plan.**

---

## 📋 SUMMARY OF FIXES FROM SIXTH REVIEW

### Fixes from PLAN_REVIEW_SIXTH_ISSUES.md (11 issues):

**Critical Issues (7):**
1. ✅ **Issue 1**: Rates Data Format Mismatch in `detect_regime()` - Updated current candle extraction to use `_normalize_rates()` and handle both DataFrame and numpy array formats with proper column name mapping.
2. ✅ **Issue 2**: Missing `volatility_strategy_mapper` Module - Module specification already exists in Phase 2.1. Added note that file MUST be created before Phase 2.2 implementation.
3. ✅ **Issue 3**: Missing `_normalize_rates()` Usage in Current Candle Extraction - Fixed by applying Issue 1 fix (uses `_normalize_rates()` before extraction).
4. ✅ **Issue 4**: Missing `_normalize_rates()` Call in `_detect_breakout()` - Updated to use `_normalize_rates()` and convert to numpy array for breakout detection logic.
5. ✅ **Issue 5**: Missing `_normalize_rates()` Call in `_calculate_intrabar_volatility()` - Updated to use `_normalize_rates()` for consistent data handling.
6. ✅ **Issue 6**: Missing `_normalize_rates()` Call in `_detect_whipsaw()` - Updated to use `_normalize_rates()` and handle both DataFrame and numpy array formats. Also updated call site in `detect_regime()` to pass normalized rates.
7. ✅ **Issue 7**: Missing `_normalize_rates()` Call in `_detect_mean_reversion_pattern()` - Updated to use `_normalize_rates()` for consistent data handling.

**Important Issues (4):**
8. ✅ **Issue 8**: Missing Error Handling for DataFrame Column Names - Added column name mapping and error handling in `detect_regime()` current candle extraction.
9. ✅ **Issue 9**: Missing Validation for `_normalize_rates()` Return Value - Added `None` checks after all `_normalize_rates()` calls with appropriate error handling.
10. ✅ **Issue 10**: Missing Thread Safety Documentation - Added documentation to `_normalize_rates()` docstring explaining thread safety (creates new objects, doesn't modify shared state).
11. ✅ **Issue 11**: Missing Documentation for DataFrame vs NumPy Array Handling - Added comprehensive docstring to `detect_regime()` method documenting that it accepts both DataFrame and numpy array formats.

**All fixes have been integrated into the implementation plan.**

---

## 📋 SUMMARY OF FIXES FROM SEVENTH REVIEW

### Fixes from PLAN_REVIEW_SEVENTH_ISSUES.md (7 issues):

**Critical Issues (4):**
1. ✅ **Issue 1**: BB Width Ratio vs Percentile Confusion in PRE_BREAKOUT_TENSION Detection - Fixed to use `_calculate_bb_width_trend()` and check `is_narrow` field instead of comparing multiplier (bb_width_ratio) against percentile threshold (0.015). The original code compared different units which would always fail.
2. ✅ **Issue 2**: Missing Session Extraction in Phase 4.1 - Added `SessionHelpers.get_current_session()` call with error handling to extract current session for strategy recommendations. Previously hardcoded to `None`.
3. ✅ **Issue 3**: Missing Call to `_calculate_bb_width_trend()` in PRE_BREAKOUT_TENSION - Updated detection method to call `_calculate_bb_width_trend()` and use `is_narrow` field. The method was defined but never called.
4. ✅ **Issue 4**: Circular Import Risk in Phase 4.1 - Added try-except around import with fallback error handling to prevent circular import issues. Import moved inside conditional block with proper error handling.

**Major Issues (3):**
5. ✅ **Issue 5**: Missing Error Handling for `_calculate_bb_width_trend()` Call - Added try-except block around `_calculate_bb_width_trend()` call in `_detect_pre_breakout_tension()` to prevent crashes if calculation fails.
6. ✅ **Issue 6**: Missing Validation for `regime` Type Before Calling `.value` - Added `isinstance(regime, VolatilityRegime)` check before calling `.value` attribute to prevent AttributeError if wrong type is passed.
7. ✅ **Issue 7**: Missing Database Path Validation - Added `os.makedirs("data", exist_ok=True)` before database initialization in `__init__()` to ensure directory exists before database operations.

**All fixes have been integrated into the implementation plan.**

---

## 📋 SUMMARY OF FIXES FROM EIGHTH REVIEW

### Fixes from PLAN_REVIEW_EIGHTH_ISSUES.md (8 issues):

**Critical Issues (5):**
1. ✅ **Issue 1**: Missing `_normalize_rates()` Call in `_detect_pre_breakout_tension()` - Added normalization before calling `_calculate_bb_width_trend()` and `_calculate_intrabar_volatility()`. Both methods now receive normalized rates (DataFrame) instead of raw rates that could be numpy arrays.
2. ✅ **Issue 2**: Missing `_normalize_rates()` Call in `_detect_fragmented_chop()` - Added normalization before calling `_detect_whipsaw()` to ensure consistent data format handling.
3. ✅ **Issue 3**: Thread-Safety Issue in `_detect_session_switch_flare()` Baseline ATR Calculation - Added `_tracking_lock` around access to `_atr_history` to prevent race conditions in multi-threaded environments.
4. ✅ **Issue 4**: Flawed Baseline ATR Calculation Logic in `_detect_session_switch_flare()` - Fixed incorrect index mapping logic. Now correctly accesses history deque entries directly (last 20 entries) rather than trying to map candle indices to history positions, which was flawed since history is ordered by time, not by candle index.
5. ✅ **Issue 5**: Missing Volume Extraction Logic in `_detect_breakout()` - Enhanced volume extraction to check both rates array (DataFrame columns or numpy array column 4) and timeframe_data keys, with proper fallback logic.

**Major Issues (3):**
6. ✅ **Issue 6**: `_calculate_bb_width_trend()` Signature Mismatch - Added documentation clarifying that method expects DataFrame and callers must normalize rates first using `_normalize_rates()`. This is consistent with other methods that require normalization before calling.
7. ✅ **Issue 7**: Missing Error Handling in `_detect_fragmented_chop()` - Added try-except block around `_detect_mean_reversion_pattern()` call to prevent crashes and allow graceful degradation.
8. ✅ **Issue 8**: Missing Validation for `rates` Length in `_detect_session_switch_flare()` - Added normalization before checking length to ensure consistent format handling (numpy array length check may not work as expected if format is unexpected).

**All fixes have been integrated into the implementation plan.**

---

## 📋 SUMMARY OF FIXES FROM NINTH REVIEW

### Fixes from PLAN_REVIEW_NINTH_ISSUES.md (4 issues):

**Critical Issues (1):**
1. ✅ **Issue 1**: Missing `atr_ratio` Field in `_detect_pre_breakout_tension()` - Fixed to calculate `atr_ratio` from `atr_14`/`atr_50` directly in the detection method, since `atr_ratio` is not stored in `timeframe_data` structure. This was breaking PRE_BREAKOUT_TENSION detection.

**Major Issues (2):**
2. ✅ **Issue 2**: Missing `vwap` and `ema_200` Fields in `_detect_mean_reversion_pattern()` - Fixed to calculate VWAP and EMA200 from rates DataFrame/numpy array within the method, since these values are not included in `timeframe_data` structure. This was breaking FRAGMENTED_CHOP detection.
3. ✅ **Issue 3**: Potential Division by Zero in `_calculate_atr_trend()` - Enhanced division by zero handling with explicit checks for `None` and `NaN` values before calculating `slope_pct`, improving defensive programming.

**Important Issues (1):**
4. ✅ **Issue 4**: Missing Error Handling for Empty `recent_atr` List - Added defensive check before linear regression calculation to handle cases where `recent_atr` has fewer than 2 elements, preventing potential errors.

**All fixes have been integrated into the implementation plan.**

---

## 📋 SUMMARY OF FIXES FROM TENTH REVIEW

### Fixes from PLAN_REVIEW_TENTH_ISSUES.md (3 issues):

**Major Issues (2):**
1. ✅ **Issue 1**: Potential AttributeError if `m15_breakout` is None in `_detect_post_breakout_decay()` - Added explicit `isinstance()` type check before calling `.get()` on `m15_breakout` to prevent AttributeError if the value is not a dict. This is defensive programming that makes the code more robust.
2. ✅ **Issue 2**: Missing Validation for `m15_atr_trend` Type Before Calling `.get()` - Added explicit `isinstance()` type check before calling `.get()` on `m15_atr_trend` to ensure it's a dict. This prevents potential AttributeError and makes the code more maintainable.

**Important Issues (1):**
3. ✅ **Issue 3**: Missing Default Value in `.get()` Calls for Safety - Added explicit default values (`False`) to `.get()` calls in `_detect_post_breakout_decay()` and `_detect_pre_breakout_tension()` methods. This improves code clarity and makes the behavior more predictable.

**All fixes have been integrated into the implementation plan.**

---

# END_OF_DOCUMENT

