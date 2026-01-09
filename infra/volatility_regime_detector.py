"""
Volatility Regime Detector - Phase 1 Implementation

Detects market volatility regimes (STABLE, TRANSITIONAL, VOLATILE) using:
- ATR ratio analysis (ATR(14) / ATR(50))
- Bollinger Band width evaluation
- ADX threshold checking
- Multi-timeframe weighting (M5: 20%, M15: 30%, H1: 50%)
- Persistence filters to prevent false signals
- Regime Inertia Coefficient to prevent rapid flips
- Auto-Cooldown Mechanism to ignore fast reversals
- Volume confirmation for volatile regimes

Phase 1: Foundation & Detection
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List, Union
from datetime import datetime, timedelta, timezone
from enum import Enum
from collections import deque
import uuid
import json
import threading
import sqlite3
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class VolatilityRegime(Enum):
    """Volatility regime classifications"""
    STABLE = "STABLE"
    TRANSITIONAL = "TRANSITIONAL"
    VOLATILE = "VOLATILE"
    # NEW: Advanced volatility states (Phase 1.1)
    PRE_BREAKOUT_TENSION = "PRE_BREAKOUT_TENSION"
    POST_BREAKOUT_DECAY = "POST_BREAKOUT_DECAY"
    FRAGMENTED_CHOP = "FRAGMENTED_CHOP"
    SESSION_SWITCH_FLARE = "SESSION_SWITCH_FLARE"


class RegimeDetector:
    """Volatility regime detection system"""
    
    # Thresholds (using parameter bands to prevent over-optimization)
    ATR_RATIO_STABLE = 1.2  # Below this = STABLE
    ATR_RATIO_TRANSITIONAL_LOW = 1.2
    ATR_RATIO_TRANSITIONAL_HIGH = 1.4  # Between 1.2-1.4 = TRANSITIONAL
    ATR_RATIO_VOLATILE = 1.4  # Above this = VOLATILE
    
    BOLLINGER_WIDTH_MULTIPLIER_STABLE = 1.5  # Below this = STABLE
    BOLLINGER_WIDTH_MULTIPLIER_TRANSITIONAL = 1.8  # Between 1.5-1.8 = TRANSITIONAL
    BOLLINGER_WIDTH_MULTIPLIER_VOLATILE = 1.8  # Above this = VOLATILE
    
    ADX_THRESHOLD_WEAK = 20  # Below this = weak/no trend
    ADX_THRESHOLD_STRONG = 25  # Above this = strong trend
    
    # Multi-timeframe weights
    TIMEFRAME_WEIGHTS = {
        "M5": 0.20,   # 20%
        "M15": 0.30,  # 30%
        "H1": 0.50    # 50%
    }
    
    # Persistence filter: require N consecutive candles showing same regime
    PERSISTENCE_REQUIRED = 3
    
    # Regime Inertia: minimum candles a regime must hold before changing
    INERTIA_MIN_HOLD = 5
    
    # Auto-Cooldown: ignore reversals within N candles
    COOLDOWN_WINDOW = 2
    
    # Volume confirmation: require volume spike when ATR increases
    VOLUME_SPIKE_THRESHOLD = 1.5  # 150% of average
    
    def __init__(self):
        """Initialize the regime detector"""
        # State tracking for persistence and inertia
        self._regime_history: Dict[str, List[Tuple[datetime, VolatilityRegime, float]]] = {}
        self._last_regime_change: Dict[str, datetime] = {}
        self._cooldown_until: Dict[str, datetime] = {}
        self._last_regime: Dict[str, VolatilityRegime] = {}  # Track last confirmed regime for change detection
        
        # NEW: ATR history tracking (in-memory rolling deques) - Phase 1.3.1
        self._atr_history: Dict[str, Dict[str, deque]] = {}
        # Structure: {symbol: {timeframe: deque(maxlen=20)}}
        # Each entry: (timestamp, atr_14_value, atr_50_value)
        
        # NEW: Wick ratios tracking (in-memory rolling deques) - Phase 1.3.1
        self._wick_ratios_history: Dict[str, Dict[str, deque]] = {}
        # Structure: {symbol: {timeframe: deque(maxlen=20)}}
        # Each entry: (timestamp, wick_ratio)
        
        # NEW: Breakout cache (in-memory for fast access) - Phase 1.3.1
        self._breakout_cache: Dict[str, Dict[str, Optional[Dict]]] = {}
        # Structure: {symbol: {timeframe: {last_breakout: {...}}}}
        
        # NEW: Volatility spike cache (for flare resolution tracking) - Phase 1.3.1
        self._volatility_spike_cache: Dict[str, Dict[str, Optional[Dict]]] = {}
        # Structure: {symbol: {timeframe: {spike_start: datetime, spike_atr: float}}}
        
        # FIX: Performance Issue 1 - Thread locks for tracking structures
        self._tracking_lock = threading.RLock()  # Reentrant lock for thread safety
        self._db_lock = threading.RLock()  # Database access lock
        
        # FIX: Issue 7 - Ensure data directory exists before database operations
        os.makedirs("data", exist_ok=True)
        
        # NEW: Database path for breakout events - Phase 1.3.2
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
                # Handle different column counts (MT5 can return 5, 6, 7, or 8 columns)
                num_cols = rates.shape[1]
                column_names = ['time', 'open', 'high', 'low', 'close']
                if num_cols >= 6:
                    column_names.append('tick_volume')
                if num_cols >= 7:
                    column_names.append('spread')
                if num_cols >= 8:
                    column_names.append('real_volume')
                
                # Use only the columns we have
                return pd.DataFrame(
                    rates,
                    columns=column_names[:num_cols]
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
    
    def _init_breakout_table(self):
        """
        Initialize breakout_events table if it doesn't exist.
        
        Phase 1.3.2 - Database initialization for persistent breakout tracking.
        """
        try:
            conn = sqlite3.connect(self._db_path, timeout=10.0)
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
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timeframe, breakout_timestamp)
                )
            """)
            
            # Create indices for fast lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_timeframe_active 
                ON breakout_events(symbol, timeframe, is_active)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_breakout_timestamp 
                ON breakout_events(breakout_timestamp)
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error initializing breakout table: {e}")
    
    def _calculate_bb_width_trend(
        self,
        df: pd.DataFrame,
        window: int = 10
    ) -> Dict[str, Any]:
        """
        Calculate BB width trend over time.
        
        Phase 1.3.3 - BB Width Trend Analysis
        
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
                "is_expanding": bool,  # True if trend_slope > 0
                "is_contracting": bool  # True if trend_slope < 0
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
                "is_expanding": False,
                "is_contracting": False
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
                "is_expanding": False,
                "is_contracting": False
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
            "is_expanding": is_expanding,
            "is_contracting": is_contracting
        }
    
    def _calculate_wick_variance(
        self,
        symbol: str,
        timeframe: str,
        current_candle: Dict[str, float],
        current_time: datetime
    ) -> Dict[str, Any]:
        """
        Calculate rolling variance of wick-to-body ratios.
        
        Phase 1.3.3 - Wick Variance Tracking
        
        FIX: Data Flow Issue 2 - current_candle extracted from rates in detect_regime().
        FIX: Integration Error 3 - Error handling for insufficient data.
        FIX: Performance Issue 1 - Thread-safe access to tracking structures.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (M5, M15, H1)
            current_candle: Dict with keys "open", "high", "low", "close", "volume"
                           (extracted from rates[-1] in detect_regime())
            current_time: Current timestamp
        
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
    
    def _calculate_intrabar_volatility(
        self,
        rates: Union[pd.DataFrame, np.ndarray, None],
        window: int = 5
    ) -> Dict[str, Any]:
        """
        Calculate intra-bar volatility (candle range vs body).
        
        Phase 1.3.3 - Intra-Bar Volatility
        
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
        if len(rates_array) >= 2:
            previous = rates_array[-2]
            previous_range = previous[1] - previous[2]
            previous_body = abs(previous[3] - previous[0])
            previous_ratio = previous_range / previous_body if previous_body > 0 else 0.0
        else:
            previous_ratio = current_ratio
        
        return {
            "current_ratio": current_ratio,
            "previous_ratio": previous_ratio,
            "is_rising": current_ratio > previous_ratio
        }
    
    def _calculate_atr_trend(
        self,
        symbol: str,
        timeframe: str,
        current_atr_14: float,
        current_atr_50: float,
        current_time: datetime
    ) -> Dict[str, Any]:
        """
        Calculate ATR slope/derivative.
        
        Phase 1.3.4 - ATR Trend Analysis
        
        FIX: Integration Error 3 - Error handling for insufficient data.
        FIX: Edge Case 1 - Handle cases with < 5 data points.
        FIX: Performance Issue 1 - Thread-safe access to tracking structures.
        FIX: Important Issue 3 - Handle empty history after initialization.
        FIX: Issue 2 - Calculate period_seconds based on timeframe.
        FIX: Issue 3 - Handle edge case for np.polyfit.
        FIX: Issue 9 - Enhanced division by zero handling.
        
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
                history.append((current_time, current_atr_14, current_atr_50))
            
            # Need at least 5 data points for trend calculation
            if len(history) < 5:
                return {
                    "current_atr": current_atr_14,
                    "slope": 0.0,
                    "slope_pct": 0.0,
                    "is_declining": False,
                    "is_above_baseline": current_atr_14 > (current_atr_50 * 1.2),
                    "trend_direction": "insufficient_data"
                }
            
            # Extract recent ATR values (last 5)
            with self._tracking_lock:
                recent_atr = [atr_14 for _, atr_14, _ in list(history)[-5:]]
            
            # FIX: Issue 11 - Check for sufficient data before linear regression
            if len(recent_atr) < 2:
                return {
                    "current_atr": current_atr_14,
                    "slope": 0.0,
                    "slope_pct": 0.0,
                    "is_declining": False,
                    "is_above_baseline": current_atr_14 > (current_atr_50 * 1.2),
                    "trend_direction": "insufficient_data"
                }
            
            # Calculate period_seconds based on timeframe
            timeframe_seconds = {
                "M5": 300,
                "M15": 900,
                "H1": 3600
            }
            period_seconds = timeframe_seconds.get(timeframe, 300)
            
            # Calculate time periods (x-axis for regression)
            with self._tracking_lock:
                timestamps = [ts for ts, _, _ in list(history)[-5:]]
            
            if len(timestamps) < 2:
                return {
                    "current_atr": current_atr_14,
                    "slope": 0.0,
                    "slope_pct": 0.0,
                    "is_declining": False,
                    "is_above_baseline": current_atr_14 > (current_atr_50 * 1.2),
                    "trend_direction": "insufficient_data"
                }
            
            # Convert timestamps to periods (seconds since first timestamp)
            first_ts = timestamps[0]
            x_periods = np.array([(ts - first_ts).total_seconds() / period_seconds for ts in timestamps])
            y_atr = np.array(recent_atr)
            
            # FIX: Issue 3 - Check if we have enough unique x values
            if len(np.unique(x_periods)) > 1 and len(y_atr) >= 2:
                slope, _ = np.polyfit(x_periods, y_atr, 1)
            else:
                slope = 0.0
            
            # Calculate slope percentage
            if current_atr_14 is not None and current_atr_14 > 0 and not np.isnan(current_atr_14):
                slope_pct = (slope / current_atr_14) * 100
            else:
                slope_pct = 0.0
            
            # Determine trend direction
            if abs(slope_pct) < 0.1:
                trend_direction = "stable"
            elif slope_pct < 0:
                trend_direction = "declining"
            elif slope_pct > 0:
                trend_direction = "rising"
            else:
                trend_direction = "insufficient_data"
            
            # Check if above baseline
            baseline_atr = current_atr_50 * 1.2  # 1.2x ATR(50) baseline
            is_above_baseline = current_atr_14 > baseline_atr
            
            return {
                "current_atr": current_atr_14,
                "slope": slope,
                "slope_pct": slope_pct,
                "is_declining": slope_pct < 0,
                "is_above_baseline": is_above_baseline,
                "trend_direction": trend_direction
            }
        except Exception as e:
            logger.warning(f"ATR trend calculation failed for {symbol}/{timeframe}: {e}")
            return {
                "current_atr": current_atr_14,
                "slope": 0.0,
                "slope_pct": 0.0,
                "is_declining": False,
                "is_above_baseline": current_atr_14 > (current_atr_50 * 1.2) if current_atr_50 else False,
                "trend_direction": "error"
            }
    
    def _detect_whipsaw(
        self,
        rates: Union[pd.DataFrame, np.ndarray, None],
        window: int = 5
    ) -> Dict[str, Any]:
        """
        Detect whipsaw pattern (alternating direction changes).
        
        Phase 1.3.5 - Whipsaw Detection
        
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
            # NumPy array - close is column 3 (index 3) or column index 4 if 0-indexed
            # Assuming standard MT5 format: [time, open, high, low, close, ...]
            if rates_normalized.shape[1] >= 5:
                close_prices = rates_normalized[-window-1:, 4]  # close is index 4
            else:
                return {"is_whipsaw": False, "direction_changes": 0, "oscillation_around_mean": False}
        
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
    
    def _detect_session_transition(
        self,
        current_time: datetime,
        previous_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Detect if we're in a session transition window.
        
        Phase 1.3.6 - Session Transition Detection
        
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
        # Ensure current_time is UTC
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        else:
            # Convert to UTC if not already
            current_time = current_time.astimezone(timezone.utc)
        
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
        
        # Not in transition
        return {
            "is_transition": False,
            "transition_type": None,
            "minutes_into_transition": 0,
            "transition_window_start": None,
            "transition_window_end": None
        }
    
    def _detect_mean_reversion_pattern(
        self,
        symbol: str,
        timeframe_data: Dict[str, Dict[str, Any]],
        window: int = 10
    ) -> Dict[str, Any]:
        """
        Detect mean reversion pattern (price oscillating around VWAP/EMA).
        
        Phase 1.3.7 - Mean Reversion Pattern Detection
        
        Required for: FRAGMENTED_CHOP detection
        
        FIX: Issue 2 - Calculate vwap and ema_200 from rates (not stored in timeframe_data)
        
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
            return {"is_mean_reverting": False, "oscillation_around_vwap": False, "oscillation_around_ema": False, "touch_count": 0, "reversion_strength": 0.0}
        
        rates = m15_data.get("rates")
        atr_14 = m15_data.get("atr_14", 1.0)
        
        # FIX: Issue 7 - Use _normalize_rates() for consistent data handling
        # FIX: Issue 2 - Calculate vwap and ema_200 from rates (not stored in timeframe_data)
        rates_normalized = self._normalize_rates(rates)
        if rates_normalized is None or len(rates_normalized) < max(window, 200):
            return {"is_mean_reverting": False, "oscillation_around_vwap": False, "oscillation_around_ema": False, "touch_count": 0, "reversion_strength": 0.0}
        
        # Calculate VWAP and EMA200 from rates
        vwap = None
        ema_200 = None
        
        if isinstance(rates_normalized, pd.DataFrame):
            if 'close' not in rates_normalized.columns:
                return {"is_mean_reverting": False, "oscillation_around_vwap": False, "oscillation_around_ema": False, "touch_count": 0, "reversion_strength": 0.0}
            
            # Calculate VWAP (Volume Weighted Average Price)
            if 'tick_volume' in rates_normalized.columns:
                close_vol = rates_normalized['close'] * rates_normalized['tick_volume']
                vwap = float(close_vol.sum() / rates_normalized['tick_volume'].sum()) if rates_normalized['tick_volume'].sum() > 0 else None
            
            # Calculate EMA200
            if len(rates_normalized) >= 200:
                ema_200 = float(rates_normalized['close'].ewm(span=200, adjust=False).mean().iloc[-1])
            
            close_values = rates_normalized['close'].iloc[-window:].values
        else:
            # NumPy array - close is column 4 (index 4), volume is column 5 (index 5)
            if rates_normalized.shape[1] < 5:
                return {"is_mean_reverting": False, "oscillation_around_vwap": False, "oscillation_around_ema": False, "touch_count": 0, "reversion_strength": 0.0}
            
            close_prices = rates_normalized[:, 4]  # close column (assuming normalized format)
            
            # Calculate VWAP from numpy array
            if rates_normalized.shape[1] > 5:
                volumes = rates_normalized[:, 5]  # tick_volume column
                if np.sum(volumes) > 0:
                    vwap = float(np.sum(close_prices * volumes) / np.sum(volumes))
            
            # Calculate EMA200 from numpy array
            if len(close_prices) >= 200:
                ema_200 = float(pd.Series(close_prices).ewm(span=200, adjust=False).mean().iloc[-1])
            
            close_values = rates_normalized[-window:, 4]
        
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
        reversion_strength = min(touch_count / window, 1.0) if window > 0 else 0.0
        
        # Mean reverting if oscillating around either VWAP or EMA
        is_mean_reverting = oscillation_around_vwap or oscillation_around_ema
        
        return {
            "is_mean_reverting": is_mean_reverting,
            "oscillation_around_vwap": oscillation_around_vwap,
            "oscillation_around_ema": oscillation_around_ema,
            "touch_count": touch_count,
            "reversion_strength": reversion_strength
        }
    
    def _detect_volatility_spike(
        self,
        symbol: str,
        timeframe_data: Dict[str, Dict[str, Any]],
        baseline_atr: float,
        spike_threshold: float = 1.5
    ) -> Dict[str, Any]:
        """
        Detect volatility spike during session transition.
        
        Phase 1.3.8 - Volatility Spike Detection
        
        Required for: SESSION_SWITCH_FLARE detection
        
        Args:
            symbol: Trading symbol
            timeframe_data: Dict with timeframe data
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
            return {"is_spike": False, "current_atr": 0.0, "spike_ratio": 1.0, "spike_magnitude": 0.0, "is_temporary": False}
        
        current_atr = m15_data.get("atr_14", 0.0)
        
        if baseline_atr <= 0:
            return {"is_spike": False, "current_atr": current_atr, "spike_ratio": 1.0, "spike_magnitude": 0.0, "is_temporary": False}
        
        spike_ratio = current_atr / baseline_atr
        is_spike = spike_ratio >= spike_threshold
        spike_magnitude = ((current_atr - baseline_atr) / baseline_atr) * 100 if baseline_atr > 0 else 0.0
        
        # Cache spike detection for time-based tracking
        with self._tracking_lock:
            if symbol not in self._volatility_spike_cache:
                self._volatility_spike_cache[symbol] = {}
            self._volatility_spike_cache[symbol]["M15"] = {
                "is_spike": is_spike,
                "timestamp": datetime.now(timezone.utc),
                "spike_ratio": spike_ratio
            }
        
        # For now, assume spikes are temporary (will be enhanced with time tracking)
        is_temporary = is_spike  # All spikes are considered potentially temporary
        
        return {
            "is_spike": is_spike,
            "current_atr": current_atr,
            "spike_ratio": spike_ratio,
            "spike_magnitude": spike_magnitude,
            "is_temporary": is_temporary
        }
    
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
        
        Phase 1.3.9 - Flare Resolution Tracking
        
        Required for: SESSION_SWITCH_FLARE detection (distinguish flare from expansion)
        
        FIX: Issue 8 - Enhanced error handling and edge cases
        
        Logic:
        - If within resolution window (30 min) AND ATR declining > 20% → Flare resolving
        - If beyond resolution window AND ATR still elevated (> 80% of spike) → Expansion (sustained)
        - If ATR declined > 20% from spike → Flare resolved
        
        Returns:
            True if flare is resolving/resolved, False if expansion (sustained)
        """
        # Get spike data from cache (thread-safe)
        with self._tracking_lock:
            spike_data = self._volatility_spike_cache.get(symbol, {}).get(timeframe)
        
        if not spike_data:
            return False  # No spike data = not a flare
        
        try:
            spike_timestamp = spike_data.get("timestamp")
            if not spike_timestamp:
                return False
            
            # Handle timezone-aware datetime comparison
            if isinstance(spike_timestamp, str):
                try:
                    spike_timestamp = datetime.fromisoformat(spike_timestamp.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    # Fallback: try parsing as timestamp
                    try:
                        spike_timestamp = datetime.fromtimestamp(float(spike_timestamp), tz=timezone.utc)
                    except (ValueError, TypeError):
                        return False
            
            # Ensure both are timezone-aware
            if spike_timestamp.tzinfo is None:
                spike_timestamp = spike_timestamp.replace(tzinfo=timezone.utc)
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)
            
            time_since_spike = (current_time - spike_timestamp).total_seconds() / 60
            
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
    
    def _detect_breakout(
        self,
        symbol: str,
        timeframe: str,
        timeframe_data: Dict[str, Any],
        current_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Detect NEW breakout events (not already detected).
        
        Phase 1.3.9.5 - Breakout Detection
        
        FIX: Gap 2 - Breakout detection logic required for POST_BREAKOUT_DECAY.
        FIX: Logic Error 4 - Only detect NEW breakouts, not every candle in a trend.
        FIX: Critical Issue 5 - Volume confirmation for breakouts.
        
        Logic:
        1. Price breakout: Price JUST broke above/below recent high/low (previous candle didn't)
        2. Volume breakout: Volume spike > 1.5x average (last 20 candles)
        3. Cache check: Only detect if not already cached (prevents duplicate detection)
        
        Returns:
            Dict with breakout info or None if no new breakout
        """
        try:
            # Get rates data
            rates = timeframe_data.get("rates")
            if rates is None:
                return None
            
            # Normalize rates
            rates_normalized = self._normalize_rates(rates)
            if rates_normalized is None or len(rates_normalized) < 20:
                return None
            
            # Extract close prices and volumes
            if isinstance(rates_normalized, pd.DataFrame):
                if 'close' not in rates_normalized.columns:
                    return None
                close_prices = rates_normalized['close'].values
                volumes = rates_normalized['tick_volume'].values if 'tick_volume' in rates_normalized.columns else None
            else:
                # NumPy array - close is column 4
                if rates_normalized.shape[1] < 5:
                    return None
                close_prices = rates_normalized[:, 4]
                volumes = rates_normalized[:, 5] if rates_normalized.shape[1] > 5 else None
            
            # Check if we have enough data
            if len(close_prices) < 20:
                return None
            
            # Get recent high/low (last 20 candles)
            recent_high = np.max(close_prices[-20:])
            recent_low = np.min(close_prices[-20:])
            current_close = close_prices[-1]
            previous_close = close_prices[-2] if len(close_prices) >= 2 else current_close
            
            # Detect breakout direction
            breakout_type = None
            breakout_price = None
            
            # Bullish breakout: price just broke above recent high
            if current_close > recent_high and previous_close <= recent_high:
                breakout_type = "BULLISH"
                breakout_price = current_close
            
            # Bearish breakout: price just broke below recent low
            elif current_close < recent_low and previous_close >= recent_low:
                breakout_type = "BEARISH"
                breakout_price = current_close
            
            if not breakout_type:
                return None  # No breakout detected
            
            # Volume confirmation (if available)
            volume_confirmed = True  # Default to True if no volume data
            if volumes is not None and len(volumes) >= 20:
                avg_volume = np.mean(volumes[-20:])
                current_volume = volumes[-1]
                volume_confirmed = current_volume >= (avg_volume * 1.5)  # 1.5x average
            
            # Check cache to avoid duplicate detection
            with self._tracking_lock:
                cached_breakout = self._breakout_cache.get(symbol, {}).get(timeframe)
                if cached_breakout:
                    # Check if this is the same breakout (within 1% of cached price)
                    cached_price = cached_breakout.get("breakout_price")
                    if cached_price and abs(breakout_price - cached_price) / breakout_price < 0.01:
                        return None  # Already detected
            
            # New breakout detected - cache it
            breakout_info = {
                "breakout_type": breakout_type,
                "breakout_price": breakout_price,
                "breakout_timestamp": current_time,
                "volume_confirmed": volume_confirmed
            }
            
            with self._tracking_lock:
                if symbol not in self._breakout_cache:
                    self._breakout_cache[symbol] = {}
                self._breakout_cache[symbol][timeframe] = breakout_info
            
            return breakout_info
            
        except Exception as e:
            logger.warning(f"Breakout detection failed for {symbol}/{timeframe}: {e}")
            return None
    
    @contextmanager
    def _get_db_connection(self):
        """
        Get database connection with timeout and error handling.
        
        Phase 1.3.10 - Database Connection Management
        
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
        
        Phase 1.3.10 - Breakout Event Recording
        
        FIX: Edge Case 2 - Invalidate previous active breakouts before recording new one.
        FIX: Performance Issue 2 - Thread-safe database access.
        
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
        
        Phase 1.3.10 - Breakout Invalidation
        
        FIX: Edge Case 2 - Prevents multiple breakouts from conflicting.
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE breakout_events
                    SET is_active = 0, invalidated_at = ?
                    WHERE symbol = ? AND timeframe = ? AND is_active = 1
                """, (datetime.now(timezone.utc).isoformat(), symbol, timeframe))
        except Exception as e:
            logger.warning(f"Error invalidating previous breakouts: {e}")
    
    def _get_time_since_breakout(
        self,
        symbol: str,
        timeframe: str,
        current_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Get time since last breakout event.
        
        Phase 1.3.11 - Time Since Breakout
        
        FIX: Integration Error 3 - Error handling for insufficient data.
        FIX: Performance Issue 1 - Thread-safe access to tracking structures.
        
        Returns:
            {
                "time_since_minutes": float,
                "breakout_type": str,
                "breakout_price": float,
                "is_recent": bool  # True if < 60 minutes
            } or None if no breakout found
        """
        try:
            # First check cache (fast)
            with self._tracking_lock:
                cached_breakout = self._breakout_cache.get(symbol, {}).get(timeframe)
            
            if cached_breakout:
                breakout_timestamp_str = cached_breakout.get("breakout_timestamp")
                if breakout_timestamp_str:
                    try:
                        breakout_timestamp = datetime.fromisoformat(breakout_timestamp_str.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        # Fallback: query database
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
                                breakout_type, breakout_price, timestamp_str = row
                                breakout_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            else:
                                return None
                    
                    # Ensure timezone-aware
                    if breakout_timestamp.tzinfo is None:
                        breakout_timestamp = breakout_timestamp.replace(tzinfo=timezone.utc)
                    if current_time.tzinfo is None:
                        current_time = current_time.replace(tzinfo=timezone.utc)
                    
                    time_since = (current_time - breakout_timestamp).total_seconds() / 60
                    
                    return {
                        "time_since_minutes": time_since,
                        "breakout_type": cached_breakout.get("breakout_type", "unknown"),
                        "breakout_price": cached_breakout.get("breakout_price", 0.0),
                        "is_recent": time_since < 60.0
                    }
            
            # Fallback: query database
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
                    breakout_type, breakout_price, timestamp_str = row
                    breakout_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    
                    # Ensure timezone-aware
                    if breakout_timestamp.tzinfo is None:
                        breakout_timestamp = breakout_timestamp.replace(tzinfo=timezone.utc)
                    if current_time.tzinfo is None:
                        current_time = current_time.replace(tzinfo=timezone.utc)
                    
                    time_since = (current_time - breakout_timestamp).total_seconds() / 60
                    
                    return {
                        "time_since_minutes": time_since,
                        "breakout_type": breakout_type,
                        "breakout_price": breakout_price,
                        "is_recent": time_since < 60.0
                    }
            
            return None
        except Exception as e:
            logger.warning(f"Error getting time since breakout for {symbol}/{timeframe}: {e}")
            return None
    
    def _detect_pre_breakout_tension(
        self,
        symbol: str,
        timeframe_data: Dict[str, Dict[str, Any]],
        current_time: datetime,
        wick_variances: Dict[str, Dict[str, Any]]
    ) -> Optional[VolatilityRegime]:
        """
        Detect PRE_BREAKOUT_TENSION state.
        
        Phase 1.4.1 - PRE_BREAKOUT_TENSION Detection
        
        FIX: Gap 4 - Added intra-bar volatility check.
        
        Logic:
        - BB width < narrow threshold (bottom 20th percentile)
        - Wick variance increasing (30%+ increase)
        - Intra-bar volatility rising (20%+ increase)
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
        try:
            bb_width_trend = self._calculate_bb_width_trend(
                rates_normalized, window=10
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
        
        # FIX: Gap 4, Issue 1 - Check intra-bar volatility
        intrabar_vol = self._calculate_intrabar_volatility(
            rates_normalized, window=5
        )
        if not intrabar_vol.get("is_rising", False):
            return None
        
        # Check threshold (20%+ increase)
        if intrabar_vol.get("previous_ratio", 0) > 0:
            ratio_change = ((intrabar_vol["current_ratio"] - intrabar_vol["previous_ratio"]) 
                          / intrabar_vol["previous_ratio"]) * 100
            if ratio_change < 20.0:
                return None
        else:
            return None  # Can't calculate change without previous ratio
        
        # FIX: Issue 1 - Calculate atr_ratio from atr_14/atr_50
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
        
        Phase 1.4.2 - POST_BREAKOUT_DECAY Detection
        
        FIX: Logic Error 3 - Clarified time window logic.
        FIX: Issue 1, Issue 2 - Explicit type checks (defensive programming).
        
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
    
    def _detect_fragmented_chop(
        self,
        symbol: str,
        timeframe_data: Dict[str, Dict[str, Any]],
        current_time: datetime
    ) -> Optional[VolatilityRegime]:
        """
        Detect FRAGMENTED_CHOP state.
        
        Phase 1.4.3 - FRAGMENTED_CHOP Detection
        
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
        if not whipsaw.get("is_whipsaw", False) or whipsaw.get("direction_changes", 0) < 3:
            return None
        
        # FIX: Issue 7 - Check mean reversion pattern (with error handling)
        try:
            mean_reversion = self._detect_mean_reversion_pattern(symbol, timeframe_data)
            if not mean_reversion.get("is_mean_reverting", False):
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
    
    def _detect_session_switch_flare(
        self,
        symbol: str,
        timeframe_data: Dict[str, Dict[str, Any]],
        current_time: datetime
    ) -> Optional[VolatilityRegime]:
        """
        Detect SESSION_SWITCH_FLARE state.
        
        Phase 1.4.4 - SESSION_SWITCH_FLARE Detection
        
        Logic:
        - In session transition window (±15 minutes)
        - Volatility spike during transition (1.5x normal)
        - Flare should resolve within 30 minutes
        - Distinguish from genuine expansion (flare is temporary)
        
        Returns VolatilityRegime.SESSION_SWITCH_FLARE if detected, None otherwise.
        """
        # Check session transition
        session_transition = self._detect_session_transition(current_time)
        if not session_transition.get("is_transition", False):
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
        if not spike.get("is_spike", False):
            return None
        
        # Track spike start time (if not already tracked)
        with self._tracking_lock:
            if symbol not in self._volatility_spike_cache:
                self._volatility_spike_cache[symbol] = {}
            if "M15" not in self._volatility_spike_cache[symbol] or \
               not self._volatility_spike_cache[symbol]["M15"]:
                self._volatility_spike_cache[symbol]["M15"] = {
                    "timestamp": current_time,
                    "spike_atr": spike["current_atr"]
                }
        
        # Check if flare is resolving (distinguish from expansion)
        with self._tracking_lock:
            spike_data = self._volatility_spike_cache.get(symbol, {}).get("M15")
        
        if spike_data:
            is_resolving = self._is_flare_resolving(
                symbol, "M15", current_time,
                spike["current_atr"], spike_data.get("spike_atr", spike["current_atr"])
            )
            
            # If not resolving and beyond 30 minutes → Expansion, not flare
            spike_timestamp = spike_data.get("timestamp")
            if spike_timestamp:
                # Ensure timezone-aware
                if isinstance(spike_timestamp, str):
                    try:
                        spike_timestamp = datetime.fromisoformat(spike_timestamp.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        spike_timestamp = current_time
                if spike_timestamp.tzinfo is None:
                    spike_timestamp = spike_timestamp.replace(tzinfo=timezone.utc)
                if current_time.tzinfo is None:
                    current_time = current_time.replace(tzinfo=timezone.utc)
                
                time_since_spike = (current_time - spike_timestamp).total_seconds() / 60
                if time_since_spike > 30 and not is_resolving:
                    return None  # Expansion, not flare
        
        # All conditions met
        return VolatilityRegime.SESSION_SWITCH_FLARE
    
    def detect_regime(
        self,
        symbol: str,
        timeframe_data: Dict[str, Dict[str, Any]],
        current_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Detect volatility regime for a symbol across multiple timeframes
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDc')
            timeframe_data: Dict with keys 'M5', 'M15', 'H1' containing:
                - 'rates': numpy array of OHLCV data
                - 'atr_14': ATR(14) value
                - 'atr_50': ATR(50) value
                - 'bb_upper': Bollinger Band upper
                - 'bb_lower': Bollinger Band lower
                - 'bb_middle': Bollinger Band middle (SMA)
                - 'adx': ADX(14) value
                - 'volume': Volume array
            current_time: Current timestamp (defaults to now)
        
        Returns:
            Dict with:
                - 'regime': VolatilityRegime enum
                - 'confidence': float (0-100)
                - 'indicators': Dict of indicator values per timeframe
                - 'reasoning': str explanation
                - 'atr_ratio': float composite ATR ratio
                - 'bb_width_ratio': float composite BB width ratio
                - 'adx_composite': float composite ADX
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        # FIX: Integration Error 2 - Initialize symbol tracking
        self._ensure_symbol_tracking(symbol)
        
        # Initialize symbol history if needed
        if symbol not in self._regime_history:
            self._regime_history[symbol] = []
            self._last_regime_change[symbol] = current_time
        
        try:
            # FIX: Issue 1 - Calculate indicators for each timeframe (REQUIRED for fallback classification)
            indicators = {}
            volume_confirmed = {}
            
            for tf_name in ["M5", "M15", "H1"]:
                if tf_name not in timeframe_data:
                    continue
                
                tf_data = timeframe_data[tf_name]
                indicators[tf_name] = self._calculate_timeframe_indicators(tf_data, tf_name)
                volume_confirmed[tf_name] = indicators[tf_name].get("volume_confirmed", False)
            
            if not indicators:
                raise ValueError(f"No timeframe data available for {symbol}")
            
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
            confidence = self._calculate_confidence(
                composite_atr_ratio,
                composite_bb_width,
                composite_adx,
                volume_confirmed_composite,
                indicators
            )
            
            # Generate reasoning (if not already calculated)
            reasoning = self._generate_reasoning(
                regime,
                composite_atr_ratio,
                composite_bb_width,
                composite_adx,
                volume_confirmed_composite,
                indicators
            )
            
            # Apply persistence filter
            regime = self._apply_persistence_filter(symbol, regime, current_time)
            
            # Apply inertia coefficient
            regime = self._apply_inertia_coefficient(symbol, regime, current_time)
            
            # Apply cooldown mechanism
            regime = self._apply_cooldown(symbol, regime, current_time)
            
            # Check for regime change and log event (after all filters applied)
            last_regime = self._last_regime.get(symbol)
            if last_regime is not None and regime != last_regime:
                # Regime change detected - log event
                self._log_regime_change(
                    symbol=symbol,
                    old_regime=last_regime,
                    new_regime=regime,
                    confidence=confidence,
                    atr_ratio=composite_atr_ratio,
                    bb_width_ratio=composite_bb_width,
                    adx=composite_adx,
                    timestamp=current_time
                )
            
            # Update last regime
            self._last_regime[symbol] = regime
            
            # Store in history
            self._regime_history[symbol].append((current_time, regime, confidence))
            
            # Keep only last 100 entries per symbol
            if len(self._regime_history[symbol]) > 100:
                self._regime_history[symbol] = self._regime_history[symbol][-100:]
            
            # FIX: Gap 1 - Return structure with NEW fields
            # FIX: Integration Error 7 - Ensure backward compatibility with safe defaults
            return {
                # Existing fields (MUST be present for backward compatibility)
                "regime": regime,
                "confidence": confidence,
                "indicators": indicators,
                "reasoning": reasoning,
                "atr_ratio": composite_atr_ratio,
                "bb_width_ratio": composite_bb_width,
                "adx_composite": composite_adx,
                "volume_confirmed": volume_confirmed_composite,
                "timestamp": current_time.isoformat(),
                
                # NEW fields (tracking metrics - may be empty dict if tracking fails)
                "atr_trends": atr_trends,
                "wick_variances": wick_variances,
                "time_since_breakout": time_since_breakout,
                "mean_reversion_pattern": mean_reversion_pattern,
                "volatility_spike": volatility_spike,
                "session_transition": session_transition,
                "whipsaw_detected": whipsaw_detected
            }
            
        except Exception as e:
            logger.error(f"Error detecting regime for {symbol}: {e}", exc_info=True)
            # Return default stable regime on error
            return {
                "regime": VolatilityRegime.STABLE,
                "confidence": 0.0,
                "indicators": {},
                "reasoning": f"Error during detection: {str(e)}",
                "atr_ratio": 1.0,
                "bb_width_ratio": 1.0,
                "adx_composite": 0.0,
                "volume_confirmed": False,
                "timestamp": current_time.isoformat() if current_time else datetime.now().isoformat()
            }
    
    def _calculate_timeframe_indicators(
        self,
        tf_data: Dict[str, Any],
        tf_name: str
    ) -> Dict[str, Any]:
        """Calculate indicators for a single timeframe"""
        try:
            rates = tf_data.get("rates")
            
            # Convert to DataFrame if needed
            df = None
            if rates is not None:
                if isinstance(rates, pd.DataFrame):
                    df = rates
                elif isinstance(rates, np.ndarray):
                    # Handle numpy array from MT5
                    if len(rates.shape) == 2 and rates.shape[1] >= 5:
                        df = pd.DataFrame(rates, columns=['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume'])
                    else:
                        # Structured array
                        try:
                            df = pd.DataFrame(rates)
                        except:
                            df = None
                elif isinstance(rates, list):
                    # Handle list of dictionaries
                    if len(rates) > 0 and isinstance(rates[0], dict):
                        df = pd.DataFrame(rates)
                    elif len(rates) > 0:
                        # Try to convert
                        try:
                            df = pd.DataFrame(rates)
                        except:
                            df = None
            
            # If no DataFrame, we can still work with provided indicators
            # df is optional - we can use provided ATR/BB/ADX values
            
            # Get ATR values (prefer provided values)
            atr_14 = tf_data.get("atr_14") or tf_data.get("atr14")  # Support both formats
            atr_50 = tf_data.get("atr_50")
            
            # Calculate ATR ratio
            if atr_14 is not None and atr_50 is not None and atr_50 > 0:
                # Use provided ATR values
                atr_ratio = atr_14 / atr_50
                logger.debug(f"{tf_name}: Using provided ATR values - ATR(14)={atr_14:.4f}, ATR(50)={atr_50:.4f}, ratio={atr_ratio:.2f}")
            elif atr_14 is not None and df is not None and len(df) >= 50:
                # Have ATR(14) but need ATR(50) - calculate it
                try:
                    atr_50_calc = self._calculate_atr(df, 50)
                    if atr_50_calc > 0:
                        atr_ratio = atr_14 / atr_50_calc
                        atr_50 = atr_50_calc
                        logger.debug(f"{tf_name}: Calculated ATR(50) from data - ATR(14)={atr_14:.4f}, ATR(50)={atr_50:.4f}, ratio={atr_ratio:.2f}")
                    else:
                        atr_ratio = 1.0
                        atr_50 = None
                        logger.warning(f"Could not calculate ATR(50) for {tf_name} (result=0), using default ratio 1.0")
                except Exception as e:
                    atr_ratio = 1.0
                    atr_50 = None
                    logger.warning(f"Error calculating ATR(50) for {tf_name}: {e}, using default ratio 1.0")
            elif df is not None and len(df) >= 50:
                # Calculate both ATRs from DataFrame
                try:
                    atr_14_calc = self._calculate_atr(df, 14)
                    atr_50_calc = self._calculate_atr(df, 50)
                    if atr_50_calc > 0:
                        atr_ratio = atr_14_calc / atr_50_calc
                        atr_14 = atr_14_calc
                        atr_50 = atr_50_calc
                        logger.debug(f"{tf_name}: Calculated ATR from data - ATR(14)={atr_14:.4f}, ATR(50)={atr_50:.4f}, ratio={atr_ratio:.2f}")
                    else:
                        atr_ratio = 1.0
                        atr_14 = None
                        atr_50 = None
                        logger.warning(f"Could not calculate ATR for {tf_name} (atr_50=0), using default 1.0")
                except Exception as e:
                    atr_ratio = 1.0
                    atr_14 = None
                    atr_50 = None
                    logger.warning(f"Error calculating ATR for {tf_name}: {e}, using default 1.0")
            else:
                # No data available - use defaults
                atr_ratio = 1.0
                if atr_14 is None:
                    atr_14 = None
                if atr_50 is None:
                    atr_50 = None
                logger.debug(f"{tf_name}: Using default ATR ratio 1.0 (no data available)")
            
            # Get Bollinger Bands
            bb_upper = tf_data.get("bb_upper")
            bb_lower = tf_data.get("bb_lower")
            bb_middle = tf_data.get("bb_middle")
            
            # Calculate BB width ratio
            if bb_upper is not None and bb_lower is not None and bb_middle is not None:
                # BB width = (upper - lower) / middle
                bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
                
                # Calculate 20-day median of BB width for comparison
                try:
                    if isinstance(df, pd.DataFrame) and len(df) >= 20:
                        # Calculate historical BB widths
                        historical_widths = []
                        for i in range(20, len(df)):
                            if i < len(df):
                                try:
                                    hist_upper = df.iloc[i-20:i]['high'].max()
                                    hist_lower = df.iloc[i-20:i]['low'].min()
                                    hist_middle = df.iloc[i-20:i]['close'].mean()
                                    if hist_middle > 0:
                                        hist_width = (hist_upper - hist_lower) / hist_middle
                                        historical_widths.append(hist_width)
                                except (KeyError, IndexError):
                                    continue
                        
                        if historical_widths:
                            median_width = np.median(historical_widths)
                            bb_width_ratio = bb_width / median_width if median_width > 0 else 1.0
                        else:
                            # Fallback: use provided BB width directly
                            bb_width_ratio = bb_width / 0.02 if bb_width > 0 else 1.0  # Assume 2% median as fallback
                    else:
                        # Fallback: use provided BB width directly
                        bb_width_ratio = bb_width / 0.02 if bb_width > 0 else 1.0
                except Exception as e:
                    logger.warning(f"Error calculating BB width ratio for {tf_name}: {e}, using provided width")
                    bb_width_ratio = bb_width / 0.02 if bb_width > 0 else 1.0
            else:
                # Fallback: calculate BB ourselves if possible
                try:
                    if isinstance(df, pd.DataFrame) and len(df) >= 20 and 'close' in df.columns:
                        from infra.feature_builder_advanced import FeatureBuilderAdvanced
                        # Use a simple BB calculation
                        sma = df['close'].rolling(20).mean()
                        std = df['close'].rolling(20).std()
                        if len(sma) > 0 and not pd.isna(sma.iloc[-1]):
                            bb_middle_calc = sma.iloc[-1]
                            bb_width_calc = (std.iloc[-1] * 4) / bb_middle_calc if bb_middle_calc > 0 else 0.02
                            bb_width_ratio = bb_width_calc / 0.02  # Normalize to 2% median
                        else:
                            bb_width_ratio = 1.0
                    else:
                        bb_width_ratio = 1.0
                except Exception as e:
                    logger.warning(f"Could not calculate BB width ratio for {tf_name}: {e}, using default 1.0")
                    bb_width_ratio = 1.0
            
            # Get ADX
            adx = tf_data.get("adx")
            if adx is None:
                adx = 0.0
                logger.warning(f"No ADX value for {tf_name}, using 0.0")
            
            # Check volume confirmation
            volume_confirmed = True  # Default to True if volume check fails
            if "volume" in tf_data and tf_data["volume"] is not None:
                volume_array = tf_data["volume"]
                if len(volume_array) > 0:
                    current_volume = volume_array[-1] if hasattr(volume_array, '__getitem__') else volume_array
                    avg_volume = np.mean(volume_array) if len(volume_array) > 0 else current_volume
                    
                    # Volume confirmation: if ATR is rising, volume should also be elevated
                    if atr_ratio > 1.3:  # ATR is elevated
                        if avg_volume > 0:
                            volume_ratio = current_volume / avg_volume
                            volume_confirmed = volume_ratio >= RegimeDetector.VOLUME_SPIKE_THRESHOLD
                        else:
                            volume_confirmed = True  # Can't confirm if no volume data
                    else:
                        volume_confirmed = True  # No volume confirmation needed for stable regimes
            
            return {
                "atr_ratio": atr_ratio,
                "bb_width_ratio": bb_width_ratio,
                "adx": adx,
                "volume_confirmed": volume_confirmed,
                "atr_14": atr_14,
                "atr_50": atr_50
            }
            
        except Exception as e:
            logger.error(f"Error calculating indicators for {tf_name}: {e}", exc_info=True)
            return {
                "atr_ratio": 1.0,
                "bb_width_ratio": 1.0,
                "adx": 0.0,
                "volume_confirmed": True,
                "atr_14": None,
                "atr_50": None
            }
    
    def _calculate_atr(self, df: pd.DataFrame, period: int) -> float:
        """Calculate Average True Range"""
        try:
            if len(df) < period + 1:
                return 0.0
            
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            # Calculate True Range
            tr_list = []
            for i in range(1, len(df)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                tr = max(tr1, tr2, tr3)
                tr_list.append(tr)
            
            if len(tr_list) >= period:
                # ATR = SMA of TR
                atr = np.mean(tr_list[-period:])
                return atr
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}", exc_info=True)
            return 0.0
    
    def _weighted_average(
        self,
        values: Dict[str, float],
        weights: Dict[str, float]
    ) -> float:
        """Calculate weighted average of values"""
        total = 0.0
        total_weight = 0.0
        
        for key, value in values.items():
            if key in weights:
                weight = weights[key]
                total += value * weight
                total_weight += weight
        
        if total_weight > 0:
            return total / total_weight
        else:
            # Fallback: simple average
            if values:
                return sum(values.values()) / len(values)
            return 1.0
    
    def _classify_regime(
        self,
        atr_ratio: float,
        bb_width_ratio: float,
        adx: float,
        volume_confirmed: bool
    ) -> VolatilityRegime:
        """Classify regime based on composite indicators"""
        # Count signals for each regime
        volatile_signals = 0
        stable_signals = 0
        
        # ATR ratio signals
        if atr_ratio >= RegimeDetector.ATR_RATIO_VOLATILE:
            volatile_signals += 1
        elif atr_ratio <= RegimeDetector.ATR_RATIO_STABLE:
            stable_signals += 1
        
        # BB width signals
        if bb_width_ratio >= RegimeDetector.BOLLINGER_WIDTH_MULTIPLIER_VOLATILE:
            volatile_signals += 1
        elif bb_width_ratio <= RegimeDetector.BOLLINGER_WIDTH_MULTIPLIER_STABLE:
            stable_signals += 1
        
        # ADX signals (high ADX = strong trend, but check for reversals)
        if adx >= RegimeDetector.ADX_THRESHOLD_STRONG:
            # High ADX can indicate volatile regime if paired with high ATR
            if atr_ratio >= RegimeDetector.ATR_RATIO_TRANSITIONAL_LOW:
                volatile_signals += 0.5  # Half signal
        elif adx <= RegimeDetector.ADX_THRESHOLD_WEAK:
            stable_signals += 0.5
        
        # Classify based on majority
        if volatile_signals >= 2 and volume_confirmed:
            return VolatilityRegime.VOLATILE
        elif stable_signals >= 2:
            return VolatilityRegime.STABLE
        else:
            return VolatilityRegime.TRANSITIONAL
    
    def _apply_persistence_filter(
        self,
        symbol: str,
        proposed_regime: VolatilityRegime,
        current_time: datetime
    ) -> VolatilityRegime:
        """Apply persistence filter: require N consecutive candles"""
        history = self._regime_history.get(symbol, [])
        
        if len(history) < RegimeDetector.PERSISTENCE_REQUIRED:
            # Not enough history, return proposed regime
            return proposed_regime
        
        # Check last N entries
        recent_regimes = [regime for _, regime, _ in history[-RegimeDetector.PERSISTENCE_REQUIRED:]]
        
        # Check if all recent regimes match proposed regime
        if all(r == proposed_regime for r in recent_regimes):
            return proposed_regime
        
        # Not persistent enough, return last confirmed regime
        if history:
            return history[-1][1]  # Return last confirmed regime
        
        return proposed_regime
    
    def _apply_inertia_coefficient(
        self,
        symbol: str,
        proposed_regime: VolatilityRegime,
        current_time: datetime
    ) -> VolatilityRegime:
        """Apply inertia: prevent rapid regime changes"""
        history = self._regime_history.get(symbol, [])
        
        if len(history) < RegimeDetector.INERTIA_MIN_HOLD:
            return proposed_regime
        
        # Get last regime change time
        last_change = self._last_regime_change.get(symbol)
        if last_change is None:
            return proposed_regime
        
        # Count how long current regime has been active
        current_regime = history[-1][1] if history else proposed_regime
        regime_count = 0
        
        for _, regime, _ in reversed(history):
            if regime == current_regime:
                regime_count += 1
            else:
                break
        
        # If current regime hasn't held long enough, don't change
        if proposed_regime != current_regime:
            if regime_count < RegimeDetector.INERTIA_MIN_HOLD:
                return current_regime  # Keep current regime
        
        # Regime can change, update last change time
        if proposed_regime != current_regime:
            self._last_regime_change[symbol] = current_time
        
        return proposed_regime
    
    def _apply_cooldown(
        self,
        symbol: str,
        proposed_regime: VolatilityRegime,
        current_time: datetime
    ) -> VolatilityRegime:
        """Apply cooldown: ignore fast reversals"""
        cooldown_until = self._cooldown_until.get(symbol)
        
        if cooldown_until and current_time < cooldown_until:
            # Still in cooldown, return last confirmed regime
            history = self._regime_history.get(symbol, [])
            if history:
                return history[-1][1]
            return proposed_regime
        
        # Check for rapid reversal
        history = self._regime_history.get(symbol, [])
        if len(history) >= 2:
            last_regime = history[-1][1]
            prev_regime = history[-2][1]
            
            # If regime changed recently and now trying to change back, apply cooldown
            if last_regime != prev_regime and proposed_regime == prev_regime:
                # Rapid reversal detected, apply cooldown
                self._cooldown_until[symbol] = current_time + timedelta(minutes=RegimeDetector.COOLDOWN_WINDOW * 5)  # 5 min per candle as rough estimate
                return last_regime  # Keep current regime
        
        return proposed_regime
    
    def _calculate_confidence(
        self,
        atr_ratio: float,
        bb_width_ratio: float,
        adx: float,
        volume_confirmed: bool,
        indicators: Dict[str, Dict[str, Any]]
    ) -> float:
        """Calculate confidence score (0-100)"""
        confidence_factors = []
        
        # ATR ratio strength
        if atr_ratio >= RegimeDetector.ATR_RATIO_VOLATILE:
            atr_confidence = min(100, 70 + (atr_ratio - RegimeDetector.ATR_RATIO_VOLATILE) * 20)
        elif atr_ratio <= RegimeDetector.ATR_RATIO_STABLE:
            atr_confidence = min(100, 70 + (RegimeDetector.ATR_RATIO_STABLE - atr_ratio) * 20)
        else:
            atr_confidence = 60  # Transitional
        confidence_factors.append(atr_confidence)
        
        # BB width strength
        if bb_width_ratio >= RegimeDetector.BOLLINGER_WIDTH_MULTIPLIER_VOLATILE:
            bb_confidence = min(100, 70 + (bb_width_ratio - RegimeDetector.BOLLINGER_WIDTH_MULTIPLIER_VOLATILE) * 15)
        elif bb_width_ratio <= RegimeDetector.BOLLINGER_WIDTH_MULTIPLIER_STABLE:
            bb_confidence = min(100, 70 + (RegimeDetector.BOLLINGER_WIDTH_MULTIPLIER_STABLE - bb_width_ratio) * 15)
        else:
            bb_confidence = 60
        confidence_factors.append(bb_confidence)
        
        # ADX strength
        if adx >= RegimeDetector.ADX_THRESHOLD_STRONG:
            adx_confidence = min(100, 60 + (adx - RegimeDetector.ADX_THRESHOLD_STRONG) * 2)
        else:
            adx_confidence = 40
        confidence_factors.append(adx_confidence)
        
        # Volume confirmation bonus
        if volume_confirmed:
            volume_bonus = 10
        else:
            volume_bonus = -10  # Penalty for lack of volume confirmation
        confidence_factors.append(volume_bonus)
        
        # Multi-timeframe alignment bonus
        if len(indicators) >= 3:
            # Check if all timeframes agree
            atr_ratios = [ind["atr_ratio"] for ind in indicators.values()]
            if len(set([r >= self.ATR_RATIO_VOLATILE for r in atr_ratios])) == 1:
                alignment_bonus = 10  # All timeframes agree
            else:
                alignment_bonus = 0
        else:
            alignment_bonus = -5  # Penalty for missing timeframes
        
        # Calculate weighted average
        base_confidence = np.mean(confidence_factors[:3])  # ATR, BB, ADX
        base_confidence += volume_bonus
        base_confidence += alignment_bonus
        
        # Clamp to 0-100
        confidence = max(0, min(100, base_confidence))
        
        return round(confidence, 1)
    
    def _generate_reasoning(
        self,
        regime: VolatilityRegime,
        atr_ratio: float,
        bb_width_ratio: float,
        adx: float,
        volume_confirmed: bool,
        indicators: Dict[str, Dict[str, Any]]
    ) -> str:
        """Generate human-readable reasoning"""
        parts = []
        
        parts.append(f"ATR ratio: {atr_ratio:.2f}x")
        
        if bb_width_ratio > 0:
            parts.append(f"BB width: {bb_width_ratio:.2f}x median")
        
        parts.append(f"ADX: {adx:.1f}")
        
        if volume_confirmed:
            parts.append("Volume confirmed")
        else:
            parts.append("Volume not confirmed")
        
        # Add timeframe breakdown
        tf_breakdown = []
        for tf_name, ind_data in indicators.items():
            tf_breakdown.append(f"{tf_name}: ATR {ind_data['atr_ratio']:.2f}x")
        
        if tf_breakdown:
            parts.append(f"Timeframes: {', '.join(tf_breakdown)}")
        
        return " | ".join(parts)
    
    def get_regime_history(
        self,
        symbol: str,
        limit: int = 100,
        include_metrics: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get regime history with optional detailed metrics.
        
        Phase 7.2: Enhanced regime history with detailed metrics.
        
        Args:
            symbol: Trading symbol
            limit: Maximum number of history entries to return (default: 100)
            include_metrics: If True, include detailed indicator metrics (default: True)
        
        Returns:
            List of regime snapshots with full indicator data
        """
        history = self._regime_history.get(symbol, [])
        
        result = []
        for timestamp, regime, confidence in history[-limit:]:
            entry = {
                "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp),
                "regime": regime.value if isinstance(regime, VolatilityRegime) else str(regime),
                "confidence": confidence
            }
            
            # Phase 7.2: Include detailed metrics if requested
            if include_metrics:
                # Try to get additional metrics from database if available
                try:
                    metrics = self._get_regime_metrics_from_db(symbol, timestamp)
                    if metrics:
                        entry.update(metrics)
                except Exception as e:
                    # If database lookup fails, continue without metrics
                    logger.debug(f"Could not retrieve detailed metrics for {symbol} at {timestamp}: {e}")
            
            result.append(entry)
        
        return result
    
    def _get_regime_metrics_from_db(
        self,
        symbol: str,
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve detailed metrics from database for a specific timestamp.
        
        Phase 7.2: Database lookup for detailed regime metrics.
        
        Args:
            symbol: Trading symbol
            timestamp: Timestamp to look up
        
        Returns:
            Dictionary with detailed metrics or None if not found
        """
        try:
            import sqlite3
            from pathlib import Path
            
            db_path = Path("data/volatility_regime_events.sqlite")
            if not db_path.exists():
                return None
            
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Find closest event to timestamp (within 5 minutes)
            timestamp_str = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
            
            cursor.execute("""
                SELECT 
                    atr_ratio, bb_width_ratio, adx,
                    indicators_json, confidence_percentile
                FROM regime_events
                WHERE symbol = ? 
                AND ABS(JULIANDAY(timestamp) - JULIANDAY(?)) < 0.0035
                ORDER BY ABS(JULIANDAY(timestamp) - JULIANDAY(?))
                LIMIT 1
            """, (symbol, timestamp_str, timestamp_str))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                metrics = {
                    "atr_ratio": row["atr_ratio"],
                    "bb_width_ratio": row["bb_width_ratio"],
                    "adx": row["adx"],
                    "confidence_percentile": row["confidence_percentile"]
                }
                
                # Parse indicators JSON if available
                if row["indicators_json"]:
                    try:
                        import json
                        indicators = json.loads(row["indicators_json"])
                        metrics["indicators"] = indicators
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                return metrics
            
            return None
            
        except Exception as e:
            logger.debug(f"Error retrieving regime metrics from database: {e}")
            return None
    
    def _log_regime_change(
        self,
        symbol: str,
        old_regime: VolatilityRegime,
        new_regime: VolatilityRegime,
        confidence: float,
        atr_ratio: float,
        bb_width_ratio: float,
        adx: float,
        timestamp: datetime
    ) -> None:
        """
        Log regime change event with structured format
        
        Format includes:
        - event_id: Unique identifier
        - session_tag: Trading session (London/NY/Asian)
        - confidence_percentile: Confidence score
        - old_regime, new_regime: Regime transition
        - indicators: ATR ratio, BB width, ADX
        """
        try:
            import uuid
            from datetime import datetime
            
            # Generate unique event ID
            event_id = str(uuid.uuid4())
            
            # Determine trading session
            hour = timestamp.hour
            if 7 <= hour < 16:  # London session
                session_tag = "LONDON"
            elif 13 <= hour < 22:  # New York session (overlaps with London)
                session_tag = "NY"
            else:  # Asian session
                session_tag = "ASIAN"
            
            # Build structured event data
            event_data = {
                "event_id": event_id,
                "event_type": "REGIME_CHANGE",
                "timestamp": timestamp.isoformat(),
                "symbol": symbol,
                "session_tag": session_tag,
                "old_regime": old_regime.value if isinstance(old_regime, VolatilityRegime) else str(old_regime),
                "new_regime": new_regime.value if isinstance(new_regime, VolatilityRegime) else str(new_regime),
                "confidence": confidence,
                "confidence_percentile": confidence,  # Same as confidence for now
                "indicators": {
                    "atr_ratio": atr_ratio,
                    "bb_width_ratio": bb_width_ratio,
                    "adx": adx
                },
                "transition": f"{old_regime.value if isinstance(old_regime, VolatilityRegime) else str(old_regime)} → {new_regime.value if isinstance(new_regime, VolatilityRegime) else str(new_regime)}"
            }
            
            # Phase 7.1: Enhanced logging for advanced volatility states
            advanced_states = [
                VolatilityRegime.PRE_BREAKOUT_TENSION,
                VolatilityRegime.POST_BREAKOUT_DECAY,
                VolatilityRegime.FRAGMENTED_CHOP,
                VolatilityRegime.SESSION_SWITCH_FLARE
            ]
            
            is_advanced_state = new_regime in advanced_states
            
            # Log to console with enhanced context for advanced states
            if is_advanced_state:
                logger.warning(
                    f"⚠️ Advanced Volatility State Detected [{event_id[:8]}] {symbol}: "
                    f"{event_data['old_regime']} → {event_data['new_regime']} "
                    f"(Confidence: {confidence:.1f}%, Session: {session_tag})"
                )
            else:
                logger.info(
                    f"📊 Regime Change Event [{event_id[:8]}] {symbol}: "
                    f"{event_data['old_regime']} → {event_data['new_regime']} "
                    f"(Confidence: {confidence:.1f}%, Session: {session_tag})"
                )
            
            # Phase 7.1: Send Discord alert for advanced volatility states
            if is_advanced_state:
                try:
                    self._send_volatility_state_alert(
                        symbol=symbol,
                        new_regime=new_regime,
                        confidence=confidence,
                        session_tag=session_tag,
                        atr_ratio=atr_ratio,
                        bb_width_ratio=bb_width_ratio
                    )
                except Exception as e:
                    # Log but don't fail if Discord alert fails
                    logger.debug(f"Could not send volatility state alert to Discord: {e}")
            
            # Try to log to database if available
            try:
                self._log_to_database(event_data)
            except Exception as e:
                # Log but don't fail if database logging fails
                logger.debug(f"Could not log regime event to database: {e}")
            
        except Exception as e:
            logger.error(f"Error logging regime change: {e}", exc_info=True)
    
    def _send_volatility_state_alert(
        self,
        symbol: str,
        new_regime: VolatilityRegime,
        confidence: float,
        session_tag: str,
        atr_ratio: float,
        bb_width_ratio: float
    ) -> None:
        """
        Send Discord alert for advanced volatility state detection.
        
        Phase 7.1: Enhanced alerting for new volatility states.
        
        Args:
            symbol: Trading symbol
            new_regime: Detected volatility regime
            confidence: Confidence score (0-100)
            session_tag: Trading session (LONDON/NY/ASIAN)
            atr_ratio: ATR ratio
            bb_width_ratio: Bollinger Band width ratio
        """
        try:
            # Try to import Discord notifier (optional - don't fail if not available)
            try:
                from discord_notifications import DiscordNotifier
                notifier = DiscordNotifier()
            except (ImportError, AttributeError):
                # Discord notifier not available - skip alert
                logger.debug("Discord notifier not available - skipping volatility state alert")
                return
            
            if not notifier.enabled:
                logger.debug("Discord notifications disabled - skipping volatility state alert")
                return
            
            # Build alert message based on regime
            regime_name = new_regime.value if isinstance(new_regime, VolatilityRegime) else str(new_regime)
            
            if new_regime == VolatilityRegime.PRE_BREAKOUT_TENSION:
                title = f"⚠️ PRE-BREAKOUT TENSION Detected"
                message = (
                    f"**Symbol**: {symbol}\n"
                    f"**State**: PRE_BREAKOUT_TENSION\n"
                    f"**Confidence**: {confidence:.1f}%\n"
                    f"**Session**: {session_tag}\n"
                    f"**ATR Ratio**: {atr_ratio:.2f}\n"
                    f"**BB Width Ratio**: {bb_width_ratio:.2f}\n\n"
                    f"**Action**: Prioritize breakout strategies (breakout_ib_volatility_trap, liquidity_sweep_reversal, breaker_block)\n"
                    f"Avoid mean reversion strategies."
                )
                color = 0xff9900  # Orange (warning)
            elif new_regime == VolatilityRegime.POST_BREAKOUT_DECAY:
                title = f"⚠️ POST-BREAKOUT DECAY Detected"
                message = (
                    f"**Symbol**: {symbol}\n"
                    f"**State**: POST_BREAKOUT_DECAY\n"
                    f"**Confidence**: {confidence:.1f}%\n"
                    f"**Session**: {session_tag}\n"
                    f"**ATR Ratio**: {atr_ratio:.2f}\n"
                    f"**BB Width Ratio**: {bb_width_ratio:.2f}\n\n"
                    f"**Action**: Prioritize mean reversion strategies (mean_reversion_range_scalp, fvg_retracement, order_block_rejection)\n"
                    f"Avoid trend continuation strategies."
                )
                color = 0xff9900  # Orange (warning)
            elif new_regime == VolatilityRegime.FRAGMENTED_CHOP:
                title = f"⚠️ FRAGMENTED CHOP Detected"
                message = (
                    f"**Symbol**: {symbol}\n"
                    f"**State**: FRAGMENTED_CHOP\n"
                    f"**Confidence**: {confidence:.1f}%\n"
                    f"**Session**: {session_tag}\n"
                    f"**ATR Ratio**: {atr_ratio:.2f}\n"
                    f"**BB Width Ratio**: {bb_width_ratio:.2f}\n\n"
                    f"**Action**: Only allow micro_scalp and mean_reversion_range_scalp strategies.\n"
                    f"All other strategies blocked."
                )
                color = 0xff9900  # Orange (warning)
            elif new_regime == VolatilityRegime.SESSION_SWITCH_FLARE:
                title = f"🚨 SESSION SWITCH FLARE Detected"
                message = (
                    f"**Symbol**: {symbol}\n"
                    f"**State**: SESSION_SWITCH_FLARE\n"
                    f"**Confidence**: {confidence:.1f}%\n"
                    f"**Session**: {session_tag}\n"
                    f"**ATR Ratio**: {atr_ratio:.2f}\n"
                    f"**BB Width Ratio**: {bb_width_ratio:.2f}\n\n"
                    f"**Action**: ⛔ **ALL TRADING BLOCKED** - Wait for volatility stabilization.\n"
                    f"No auto-execution plans will be created or executed."
                )
                color = 0xff0000  # Red (critical)
            else:
                # Unknown advanced state - generic message
                title = f"⚠️ Advanced Volatility State Detected"
                message = (
                    f"**Symbol**: {symbol}\n"
                    f"**State**: {regime_name}\n"
                    f"**Confidence**: {confidence:.1f}%\n"
                    f"**Session**: {session_tag}"
                )
                color = 0xff9900  # Orange (warning)
            
            # Send to Discord (private channel)
            notifier.send_message(
                message=message,
                message_type="ALERT",
                color=color,
                channel="private",
                custom_title=title
            )
            
            logger.info(f"✅ Volatility state alert sent to Discord: {regime_name} for {symbol}")
            
        except Exception as e:
            # Don't fail if alert sending fails
            logger.debug(f"Error sending volatility state alert: {e}")
    
    def _log_to_database(self, event_data: Dict[str, Any]) -> None:
        """Log regime event to SQLite database"""
        try:
            import sqlite3
            from pathlib import Path
            
            db_path = Path("data/volatility_regime_events.sqlite")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS regime_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    session_tag TEXT,
                    old_regime TEXT NOT NULL,
                    new_regime TEXT NOT NULL,
                    confidence REAL,
                    confidence_percentile REAL,
                    atr_ratio REAL,
                    bb_width_ratio REAL,
                    adx REAL,
                    transition TEXT,
                    indicators_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Insert event
            cursor.execute("""
                INSERT INTO regime_events (
                    event_id, event_type, timestamp, symbol, session_tag,
                    old_regime, new_regime, confidence, confidence_percentile,
                    atr_ratio, bb_width_ratio, adx, transition, indicators_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_data["event_id"],
                event_data["event_type"],
                event_data["timestamp"],
                event_data["symbol"],
                event_data["session_tag"],
                event_data["old_regime"],
                event_data["new_regime"],
                event_data["confidence"],
                event_data["confidence_percentile"],
                event_data["indicators"]["atr_ratio"],
                event_data["indicators"]["bb_width_ratio"],
                event_data["indicators"]["adx"],
                event_data["transition"],
                json.dumps(event_data["indicators"]),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"✅ Regime event logged to database: {event_data['event_id'][:8]}")
            
        except Exception as e:
            logger.debug(f"Database logging failed (non-critical): {e}")
            # Don't raise - this is optional functionality
    
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
            import pandas as pd
            from infra.indicator_bridge import IndicatorBridge
            
            # Convert rates to DataFrame for indicator calculation
            df = pd.DataFrame(rates)
            # MT5 rates format: [time, open, high, low, close, tick_volume, spread, real_volume]
            if df.shape[1] >= 8:
                df.columns = ['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']
            elif df.shape[1] >= 6:
                df.columns = ['time', 'open', 'high', 'low', 'close', 'tick_volume']
            else:
                logger.warning(f"Unexpected rates format for {timeframe}: {df.shape}")
                return None
            
            # Calculate indicators using IndicatorBridge
            bridge = IndicatorBridge()
            indicators = bridge._calculate_indicators(df)
            
            # Extract ATR(14) - note: key is 'atr14', not 'atr_14'
            atr_14 = indicators.get('atr14', 0)
            
            # Calculate ATR(50) separately (not provided by IndicatorBridge)
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
            
            # Handle volume extraction safely
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
                'volume': volume
            }
        except Exception as e:
            logger.error(f"Error preparing timeframe data for {timeframe}: {e}")
            return None
    
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

