"""
ATR Baseline Calculator
Calculates ATR baseline for weekend volatility classification.

Baseline = 14-period ATR average over previous 5 weekdays (Mon-Fri).
Uses H1 timeframe for weekend volatility classification.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
import numpy as np

logger = logging.getLogger(__name__)


class ATRBaselineCalculator:
    """
    Calculates ATR baseline for weekend volatility classification.
    Baseline = 14-period ATR average over previous 5 weekdays (Mon-Fri).
    """
    
    def __init__(self, mt5_service=None, streamer_data_access=None):
        """
        Initialize ATR Baseline Calculator.
        
        Args:
            mt5_service: Optional MT5Service instance
            streamer_data_access: Optional StreamerDataAccess instance
        """
        self.mt5_service = mt5_service
        self.streamer_data_access = streamer_data_access
        self._baseline_cache: Dict[str, tuple[datetime, float]] = {}  # symbol -> (timestamp, baseline)
        self._cache_ttl = timedelta(hours=12)  # Refresh baseline every 12 hours
    
    def calculate_baseline(
        self, 
        symbol: str, 
        timeframe: str = "H1", 
        period: int = 14
    ) -> Optional[float]:
        """
        Calculate ATR baseline from previous week's weekday data.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDc")
            timeframe: ATR timeframe - "H1" (default) for weekend volatility classification
            period: ATR period (default: 14)
        
        Returns:
            Average ATR over previous 5 weekdays, or None if insufficient data
        
        Implementation:
        - Get MOST RECENT 5 weekdays (Mon-Fri) of H1 candles (not previous week)
        - If current day is weekend: Get last 5 weekdays before weekend started
        - If current day is weekday: Get last 5 weekdays including today if it's a weekday
        - Calculate 14-period ATR for each weekday
        - Average the 5 ATR values
        - Return baseline
        """
        cache_key = f"{symbol}_{timeframe}_{period}"
        now = datetime.now(timezone.utc)
        
        # Check cache
        if cache_key in self._baseline_cache:
            timestamp, cached_baseline = self._baseline_cache[cache_key]
            if now - timestamp < self._cache_ttl:
                logger.debug(f"Using cached ATR baseline for {symbol}: {cached_baseline:.2f}")
                return cached_baseline
        
        try:
            # Get the 5 most recent weekdays
            weekdays = self._get_recent_weekdays(5)
            
            if len(weekdays) < 5:
                logger.warning(f"Could not get 5 weekdays for {symbol}. Got {len(weekdays)} weekdays.")
                # Fallback: use current ATR as conservative baseline
                current_atr = self._get_current_atr(symbol, timeframe, period)
                if current_atr:
                    logger.warning(f"Insufficient data for 5-weekday ATR baseline for {symbol}. Using current ATR ({current_atr:.2f}) as fallback.")
                    self._baseline_cache[cache_key] = (now, current_atr)
                    return current_atr
                return None
            
            # Calculate ATR for each weekday
            atr_values = []
            for weekday_date in weekdays:
                weekday_atr = self._calculate_weekday_atr(symbol, timeframe, period, weekday_date)
                if weekday_atr is not None:
                    atr_values.append(weekday_atr)
            
            if len(atr_values) < 3:  # Need at least 3 weekdays for reliable baseline
                logger.warning(f"Insufficient ATR values for {symbol}. Got {len(atr_values)} values.")
                # Fallback: use current ATR
                current_atr = self._get_current_atr(symbol, timeframe, period)
                if current_atr:
                    logger.warning(f"Using current ATR ({current_atr:.2f}) as fallback for {symbol}.")
                    self._baseline_cache[cache_key] = (now, current_atr)
                    return current_atr
                return None
            
            # Calculate average ATR
            baseline = sum(atr_values) / len(atr_values)
            
            # Cache result
            self._baseline_cache[cache_key] = (now, baseline)
            logger.info(f"Calculated ATR baseline for {symbol}: {baseline:.2f} (from {len(atr_values)} weekdays)")
            
            return baseline
            
        except Exception as e:
            logger.error(f"Error calculating ATR baseline for {symbol}: {e}")
            # Fallback: use current ATR if available
            current_atr = self._get_current_atr(symbol, timeframe, period)
            if current_atr:
                logger.warning(f"Error calculating baseline, using current ATR ({current_atr:.2f}) as fallback for {symbol}.")
                return current_atr
            return None
    
    def _get_recent_weekdays(self, count: int) -> list[datetime]:
        """
        Get the most recent N weekdays (Mon-Fri).
        
        Args:
            count: Number of weekdays to get
        
        Returns:
            List of datetime objects for weekdays (most recent first)
        """
        weekdays = []
        now = datetime.now(timezone.utc)
        current_date = now.date()
        
        # Start from today (or yesterday if today is weekend)
        # If today is weekend, start from last Friday
        if now.weekday() >= 5:  # Saturday or Sunday
            # Go back to last Friday
            days_back = (now.weekday() - 4) % 7
            if days_back == 0:
                days_back = 7  # If Sunday, go back to Friday
            current_date = current_date - timedelta(days=days_back)
        
        # Collect weekdays going backwards
        date = current_date
        while len(weekdays) < count:
            weekday = date.weekday()
            if weekday < 5:  # Monday (0) to Friday (4)
                weekdays.append(datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc))
            
            # Go back one day
            date = date - timedelta(days=1)
            
            # Safety limit: don't go back more than 14 days
            if (current_date - date).days > 14:
                break
        
        return weekdays
    
    def _calculate_weekday_atr(
        self, 
        symbol: str, 
        timeframe: str, 
        period: int, 
        weekday_date: datetime
    ) -> Optional[float]:
        """
        Calculate ATR for a specific weekday.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., "H1")
            period: ATR period
            weekday_date: Date of the weekday (start of day UTC)
        
        Returns:
            ATR value for that weekday, or None if calculation fails
        """
        try:
            # Get candles for that weekday (24 hours of H1 candles = 24 candles)
            # We need at least period + 2 candles for ATR calculation
            candles = self._get_weekday_candles(symbol, timeframe, weekday_date, limit=period + 10)
            
            if not candles or len(candles) < period + 2:
                logger.debug(f"Insufficient candles for {symbol} on {weekday_date.date()}: {len(candles) if candles else 0}")
                return None
            
            # Calculate ATR from candles
            # Candles should be in chronological order (oldest first)
            highs = np.array([c['high'] for c in candles])
            lows = np.array([c['low'] for c in candles])
            closes = np.array([c['close'] for c in candles])
            
            # Calculate True Range
            high_low = highs[1:] - lows[1:]
            high_close = np.abs(highs[1:] - closes[:-1])
            low_close = np.abs(lows[1:] - closes[:-1])
            
            tr = np.maximum(high_low, np.maximum(high_close, low_close))
            
            # Calculate ATR as simple moving average of TR
            if len(tr) >= period:
                atr = np.mean(tr[-period:])
                return float(atr)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error calculating weekday ATR for {symbol} on {weekday_date.date()}: {e}")
            return None
    
    def _get_weekday_candles(
        self, 
        symbol: str, 
        timeframe: str, 
        weekday_date: datetime, 
        limit: int = 30
    ) -> Optional[list[Dict[str, Any]]]:
        """
        Get candles for a specific weekday.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., "H1")
            weekday_date: Date of the weekday (start of day UTC)
            limit: Maximum number of candles to get
        
        Returns:
            List of candle dictionaries or None if failed
        """
        try:
            # Map timeframe to MT5 constant
            tf_map = {
                'M1': mt5.TIMEFRAME_M1,
                'M5': mt5.TIMEFRAME_M5,
                'M15': mt5.TIMEFRAME_M15,
                'M30': mt5.TIMEFRAME_M30,
                'H1': mt5.TIMEFRAME_H1,
                'H4': mt5.TIMEFRAME_H4
            }
            
            mt5_tf = tf_map.get(timeframe.upper())
            if not mt5_tf:
                logger.warning(f"Unsupported timeframe for ATR baseline: {timeframe}")
                return None
            
            # Calculate date range for the weekday
            # Start: weekday_date 00:00 UTC
            # End: weekday_date 23:59 UTC
            start_time = weekday_date
            end_time = weekday_date + timedelta(days=1) - timedelta(seconds=1)
            
            # Convert to Unix timestamps
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())
            
            # Try to get candles from MT5 using copy_rates_range
            if not mt5.initialize():
                logger.warning("MT5 not initialized for ATR baseline calculation")
                return None
            
            rates = mt5.copy_rates_range(symbol, mt5_tf, start_timestamp, end_timestamp)
            
            if rates is None or len(rates) == 0:
                logger.debug(f"No candles returned for {symbol} on {weekday_date.date()}")
                return None
            
            # Convert to list of dictionaries
            candles = []
            for rate in rates:
                candles.append({
                    'time': datetime.fromtimestamp(rate['time'], tz=timezone.utc),
                    'open': float(rate['open']),
                    'high': float(rate['high']),
                    'low': float(rate['low']),
                    'close': float(rate['close']),
                    'volume': int(rate['tick_volume']) if 'tick_volume' in rate else 0
                })
            
            # Sort by time (oldest first)
            candles.sort(key=lambda x: x['time'])
            
            return candles
            
        except Exception as e:
            logger.debug(f"Error getting weekday candles for {symbol} on {weekday_date.date()}: {e}")
            return None
    
    def _get_current_atr(self, symbol: str, timeframe: str, period: int) -> Optional[float]:
        """
        Get current ATR value as fallback.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            period: ATR period
        
        Returns:
            Current ATR value or None
        """
        try:
            # Try streamer first
            if self.streamer_data_access:
                atr = self.streamer_data_access.calculate_atr(symbol, timeframe, period=period)
                if atr is not None:
                    return atr
            
            # Fallback to MT5
            if self.mt5_service and hasattr(self.mt5_service, 'get_bars'):
                # Use MT5Service if available
                bars = self.mt5_service.get_bars(symbol, timeframe, count=max(period * 4, 50))
                if bars is not None and len(bars) >= period + 2:
                    highs = bars['high'].values
                    lows = bars['low'].values
                    closes = bars['close'].values
                    
                    # Calculate True Range
                    high_low = highs[1:] - lows[1:]
                    high_close = np.abs(highs[1:] - closes[:-1])
                    low_close = np.abs(lows[1:] - closes[:-1])
                    
                    tr = np.maximum(high_low, np.maximum(high_close, low_close))
                    
                    if len(tr) >= period:
                        atr = np.mean(tr[-period:])
                        return float(atr)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting current ATR for {symbol}: {e}")
            return None
    
    def get_atr_state(self, symbol: str, current_atr: float, timeframe: str = "H1") -> str:
        """
        Classify current ATR state relative to baseline.
        
        Args:
            symbol: Trading symbol
            current_atr: Current ATR value
            timeframe: Timeframe (default: "H1")
        
        Returns:
            "stable" (< 1.0×), "cautious" (1.0-1.3×), "high" (> 1.3×)
        """
        baseline = self.calculate_baseline(symbol, timeframe)
        if not baseline or baseline <= 0:
            return "cautious"  # Default if baseline unavailable
        
        ratio = current_atr / baseline
        
        if ratio < 1.0:
            return "stable"
        elif ratio <= 1.3:
            return "cautious"
        else:
            return "high"

