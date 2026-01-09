"""
Streamer Data Access Helper
Provides unified access to Multi-Timeframe Streamer data with automatic fallback to MT5.

Features:
- Get candles from streamer (fast, RAM-based)
- Automatic fallback to direct MT5 if streamer unavailable
- Data freshness validation
- Multi-timeframe support (M1, M5, M15, M30, H1, H4)
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

# Global streamer instance (set by main_api.py)
_streamer_instance = None

def set_streamer(streamer):
    """Set the global streamer instance"""
    global _streamer_instance
    _streamer_instance = streamer

def get_streamer():
    """Get the global streamer instance"""
    return _streamer_instance


class StreamerDataAccess:
    """
    Unified access to candlestick data with automatic fallback.
    
    Priority:
    1. Try streamer (if available and data fresh)
    2. Fallback to direct MT5 API calls
    """
    
    # MT5 timeframe mapping
    TF_MAP = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4
    }
    
    def __init__(self, streamer=None):
        self._explicit_streamer = streamer  # Store explicit streamer if provided
    
    @property
    def streamer(self):
        """Get streamer, checking global instance if not explicitly set"""
        if self._explicit_streamer is not None:
            return self._explicit_streamer
        return get_streamer()
    
    def get_candles(
        self, 
        symbol: str, 
        timeframe: str, 
        limit: Optional[int] = None,
        max_age_seconds: int = 300  # 5 minutes default freshness requirement
    ) -> List[Dict[str, Any]]:
        """
        Get candles for a symbol/timeframe.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDc')
            timeframe: Timeframe ('M1', 'M5', 'M15', 'M30', 'H1', 'H4')
            limit: Maximum number of candles to return
            max_age_seconds: Maximum age of latest candle in seconds (default: 300 = 5 min)
        
        Returns:
            List of candle dictionaries with: time, open, high, low, close, volume, spread
        """
        # Normalize symbol (uppercase with lowercase 'c' suffix)
        symbol = self._normalize_symbol(symbol)
        timeframe = timeframe.upper()
        
        # Try streamer first
        if self.streamer and self.streamer.is_running:
            try:
                candles = self.streamer.get_candles(symbol, timeframe, limit=limit)
                
                if candles:
                    # Check data freshness
                    # Streamer returns newest first, so first candle is most recent
                    latest_candle = candles[0] if hasattr(candles[0], 'time') else candles[0]
                    if isinstance(latest_candle, dict):
                        latest_time = latest_candle.get('time')
                        if isinstance(latest_time, str):
                            latest_time = datetime.fromisoformat(latest_time.replace('Z', '+00:00'))
                    else:
                        latest_time = latest_candle.time if hasattr(latest_candle, 'time') else None
                    
                    if latest_time:
                        age_seconds = (datetime.now(timezone.utc) - latest_time).total_seconds()
                    else:
                        age_seconds = 0
                    
                    if age_seconds <= max_age_seconds:
                        # Data is fresh enough - convert to dict format
                        # Streamer returns newest first, but we'll keep that order
                        # (callers can reverse if needed for chronological order)
                        result = [self._candle_to_dict(c) for c in candles]
                        logger.debug(f"Got {len(result)} {timeframe} candles for {symbol} from streamer (age: {age_seconds:.1f}s)")
                        return result
                    else:
                        logger.debug(f"Streamer data too old ({age_seconds:.1f}s > {max_age_seconds}s), falling back to MT5")
                else:
                    logger.debug(f"No candles in streamer buffer for {symbol} {timeframe}, falling back to MT5")
            except Exception as e:
                logger.warning(f"Error getting candles from streamer: {e}, falling back to MT5")
        
        # Fallback to direct MT5
        return self._fetch_from_mt5(symbol, timeframe, limit)
    
    def get_latest_candle(
        self,
        symbol: str,
        timeframe: str,
        max_age_seconds: int = 300
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest candle for a symbol/timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            max_age_seconds: Maximum age of candle in seconds
        
        Returns:
            Latest candle dictionary or None
        """
        candles = self.get_candles(symbol, timeframe, limit=1, max_age_seconds=max_age_seconds)
        return candles[0] if candles else None
    
    def calculate_atr(
        self,
        symbol: str,
        timeframe: str,
        period: int = 14,
        limit: Optional[int] = None
    ) -> Optional[float]:
        """
        Calculate ATR (Average True Range) for a symbol/timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            period: ATR period (default: 14)
            limit: Number of candles to use (default: period * 4)
        
        Returns:
            ATR value or None if calculation fails
        """
        if limit is None:
            limit = max(period * 4, 50)  # At least 50 candles for ATR
        
        candles = self.get_candles(symbol, timeframe, limit=limit)
        
        if len(candles) < period + 2:
            logger.warning(f"Not enough candles for ATR calculation: {len(candles)} < {period + 2}")
            return None
        
        # Reverse to chronological order (oldest first)
        candles.reverse()
        
        # Calculate True Range
        import numpy as np
        
        highs = np.array([c['high'] for c in candles])
        lows = np.array([c['low'] for c in candles])
        closes = np.array([c['close'] for c in candles])
        
        # Calculate TR: max(high-low, abs(high-prev_close), abs(low-prev_close))
        high_low = highs[1:] - lows[1:]
        high_close = np.abs(highs[1:] - closes[:-1])
        low_close = np.abs(lows[1:] - closes[:-1])
        
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        
        # Calculate ATR as simple moving average of TR
        if len(tr) >= period:
            atr = np.mean(tr[-period:])
            return float(atr)
        
        return None
    
    def detect_structure_break(
        self,
        symbol: str,
        timeframe: str,
        lookback: int = 20
    ) -> Dict[str, Any]:
        """
        Detect structure break on specified timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe to analyze
            lookback: Number of candles to look back
        
        Returns:
            Dictionary with break information: {'break_detected': bool, 'break_type': str, 'details': dict}
        """
        candles = self.get_candles(symbol, timeframe, limit=lookback + 5)
        
        if len(candles) < lookback:
            return {'break_detected': False, 'break_type': None, 'details': {'reason': 'insufficient_data'}}
        
        # Reverse to chronological order
        candles.reverse()
        
        # Find swing highs and lows
        recent_candles = candles[-lookback:]
        highs = [c['high'] for c in recent_candles]
        lows = [c['low'] for c in recent_candles]
        
        # Simple structure break: if latest candle breaks above highest high or below lowest low
        highest_high = max(highs[:-1])  # Exclude latest
        lowest_low = min(lows[:-1])  # Exclude latest
        
        latest = recent_candles[-1]
        
        break_detected = False
        break_type = None
        
        if latest['high'] > highest_high:
            break_detected = True
            break_type = 'bullish'  # Breakout above structure
        elif latest['low'] < lowest_low:
            break_detected = True
            break_type = 'bearish'  # Breakdown below structure
        
        return {
            'break_detected': break_detected,
            'break_type': break_type,
            'details': {
                'latest_high': latest['high'],
                'latest_low': latest['low'],
                'structure_high': highest_high,
                'structure_low': lowest_low,
                'candles_analyzed': len(recent_candles)
            }
        }
    
    def detect_volume_spike(
        self,
        symbol: str,
        timeframe: str,
        lookback: int = 20,
        multiplier: float = 2.0
    ) -> Dict[str, Any]:
        """
        Detect volume spike compared to recent average.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            lookback: Number of candles to compare
            multiplier: Volume must be X times average to be considered a spike
        
        Returns:
            Dictionary with spike information
        """
        candles = self.get_candles(symbol, timeframe, limit=lookback + 2)
        
        if len(candles) < lookback + 1:
            return {'spike_detected': False, 'details': {'reason': 'insufficient_data'}}
        
        # Reverse to chronological order
        candles.reverse()
        
        recent = candles[-lookback:]
        volumes = [c['volume'] for c in recent[:-1]]  # Exclude latest
        latest_volume = recent[-1]['volume']
        
        avg_volume = sum(volumes) / len(volumes) if volumes else 0
        
        spike_detected = latest_volume > avg_volume * multiplier if avg_volume > 0 else False
        
        return {
            'spike_detected': spike_detected,
            'details': {
                'latest_volume': latest_volume,
                'average_volume': avg_volume,
                'multiplier': latest_volume / avg_volume if avg_volume > 0 else 0,
                'threshold': avg_volume * multiplier
            }
        }
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to match streamer format (uppercase with lowercase 'c')"""
        symbol = symbol.upper()
        if symbol.endswith('C'):
            # Already ends with C, but need lowercase 'c'
            symbol = symbol[:-1] + 'c'
        elif not symbol.endswith('c'):
            # Add 'c' suffix if not present
            symbol = symbol + 'c'
        return symbol
    
    def _candle_to_dict(self, candle) -> Dict[str, Any]:
        """Convert Candle object to dictionary"""
        if isinstance(candle, dict):
            return candle
        
        return {
            'time': candle.time if hasattr(candle, 'time') else candle.get('time'),
            'open': float(candle.open) if hasattr(candle, 'open') else float(candle['open']),
            'high': float(candle.high) if hasattr(candle, 'high') else float(candle['high']),
            'low': float(candle.low) if hasattr(candle, 'low') else float(candle['low']),
            'close': float(candle.close) if hasattr(candle, 'close') else float(candle['close']),
            'volume': int(candle.volume) if hasattr(candle, 'volume') else int(candle['volume']),
            'spread': float(candle.spread) if hasattr(candle, 'spread') else float(candle.get('spread', 0)),
            'real_volume': int(candle.real_volume) if hasattr(candle, 'real_volume') else int(candle.get('real_volume', 0))
        }
    
    def _fetch_from_mt5(
        self,
        symbol: str,
        timeframe: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch candles directly from MT5 (fallback)"""
        try:
            # Check if MT5 is already initialized (avoid duplicate initialization)
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                # MT5 not initialized - try to initialize
                if not mt5.initialize():
                    error_code = mt5.last_error()
                    # Check if it's an authorization error
                    if error_code and isinstance(error_code, tuple) and error_code[0] == -6:
                        logger.error(f"MT5 authorization failed: {error_code[1]}. Please ensure MT5 terminal is logged in.")
                    else:
                        logger.warning(f"MT5 initialization failed: {error_code}")
                    return []
            elif not terminal_info.connected:
                # MT5 initialized but not connected to broker
                logger.warning(f"MT5 initialized but not connected to broker. Terminal connected: {terminal_info.connected}")
                return []
            
            tf_constant = self.TF_MAP.get(timeframe)
            if not tf_constant:
                logger.error(f"Invalid timeframe: {timeframe}")
                return []
            
            if limit is None:
                limit = 100
            
            rates = mt5.copy_rates_from_pos(symbol, tf_constant, 0, limit)
            
            if rates is None or len(rates) == 0:
                error_code = mt5.last_error()
                logger.warning(f"No data from MT5 for {symbol} {timeframe} (error: {error_code})")
                return []
            
            # Convert to dictionary format (oldest first for consistency)
            # MT5 returns numpy structured arrays, access fields directly (not with .get())
            candles = []
            for rate in rates:  # MT5 returns oldest first, keep that order
                candle_time = datetime.fromtimestamp(rate['time'], tz=timezone.utc)
                
                # Access numpy array fields directly
                spread = float(rate['spread']) if 'spread' in rate.dtype.names else 0.0
                real_volume = int(rate['real_volume']) if 'real_volume' in rate.dtype.names else 0
                
                candles.append({
                    'time': candle_time,
                    'open': float(rate['open']),
                    'high': float(rate['high']),
                    'low': float(rate['low']),
                    'close': float(rate['close']),
                    'volume': int(rate['tick_volume']),
                    'spread': spread,
                    'real_volume': real_volume
                })
            
            logger.debug(f"Fetched {len(candles)} {timeframe} candles for {symbol} from MT5")
            return candles
            
        except Exception as e:
            logger.error(f"Error fetching from MT5: {e}", exc_info=True)
            return []


# Global instance for easy access
_data_access = StreamerDataAccess()

def get_candles(symbol: str, timeframe: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Convenience function to get candles"""
    return _data_access.get_candles(symbol, timeframe, limit=limit)

def get_latest_candle(symbol: str, timeframe: str, max_age_seconds: int = 300) -> Optional[Dict[str, Any]]:
    """Convenience function to get latest candle"""
    return _data_access.get_latest_candle(symbol, timeframe, max_age_seconds=max_age_seconds)

def calculate_atr(symbol: str, timeframe: str, period: int = 14) -> Optional[float]:
    """Convenience function to calculate ATR"""
    return _data_access.calculate_atr(symbol, timeframe, period=period)

