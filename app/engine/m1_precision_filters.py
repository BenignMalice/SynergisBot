"""
M1 Precision Filters for Multi-Timeframe Trading
Post-confirmation filters for execution precision
"""

import numpy as np
from numba import jit, prange
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

@dataclass
class M1FilterResult:
    """M1 filter analysis result"""
    symbol: str
    timestamp_utc: int
    vwap_reclaim: bool
    delta_spike: bool
    micro_bos: bool
    atr_ratio_valid: bool
    spread_valid: bool
    filters_passed: int
    filter_score: float
    confidence: float

@dataclass
class TickData:
    """M1 tick data structure"""
    symbol: str
    timestamp_utc: int
    bid: float
    ask: float
    volume: float
    spread: float

class M1PrecisionFilters:
    """M1 precision filters for execution confirmation"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.tick_buffer = []
        self.vwap_cache = {}
        self.delta_cache = {}
        self.atr_cache = {}
        self.spread_cache = {}
        
    @staticmethod
    @jit(nopython=True, cache=True)  # Remove parallel=True, add cache=True
    def calculate_vwap(ticks: np.ndarray, volumes: np.ndarray) -> np.ndarray:
        """Calculate VWAP using Numba for performance"""
        n = len(ticks)
        vwap = np.zeros(n, dtype=np.float32)  # Use float32 for memory efficiency
        
        if n == 0:
            return vwap
            
        cumulative_volume = 0.0
        cumulative_pv = 0.0
        
        for i in range(n):
            if volumes[i] > 0:
                cumulative_volume += volumes[i]
                cumulative_pv += ticks[i] * volumes[i]
                vwap[i] = cumulative_pv / cumulative_volume
            else:
                vwap[i] = vwap[i-1] if i > 0 else ticks[i]
                
        return vwap
        
    @staticmethod
    @jit(nopython=True, cache=True)  # Remove parallel=True, add cache=True
    def calculate_rolling_median(data: np.ndarray, window: int) -> np.ndarray:
        """Calculate rolling median using Numba"""
        n = len(data)
        median = np.zeros(n, dtype=np.float32)  # Use float32 for memory efficiency
        
        for i in range(n):
            start_idx = max(0, i - window + 1)
            window_data = data[start_idx:i+1]
            median[i] = np.median(window_data)
            
        return median
        
    def check_vwap_reclaim(self, symbol: str, current_price: float, 
                          timestamp_utc: int, lookback_minutes: int = 60) -> bool:
        """Check if price has reclaimed VWAP"""
        try:
            # Get recent ticks for VWAP calculation
            cutoff_time = timestamp_utc - (lookback_minutes * 60)
            recent_ticks = [t for t in self.tick_buffer 
                          if t.symbol == symbol and t.timestamp_utc >= cutoff_time]
            
            if len(recent_ticks) < 10:  # Need minimum data
                return False
                
            # Calculate VWAP
            prices = np.array([(t.bid + t.ask) / 2 for t in recent_ticks])
            volumes = np.array([t.volume for t in recent_ticks])
            vwap = self.calculate_vwap(prices, volumes)
            
            if len(vwap) == 0:
                return False
                
            current_vwap = vwap[-1]
            vwap_threshold = self.symbol_config.get('vwap_threshold', 0.2)
            
            # Check if current price is within VWAP threshold
            price_diff = abs(current_price - current_vwap) / current_vwap
            return price_diff <= vwap_threshold
            
        except Exception as e:
            logger.error(f"Error checking VWAP reclaim for {symbol}: {e}")
            return False
            
    def check_delta_spike(self, symbol: str, current_price: float, 
                         timestamp_utc: int, lookback_minutes: int = 20) -> bool:
        """Check for volume delta spike"""
        try:
            # Get recent ticks for delta calculation
            cutoff_time = timestamp_utc - (lookback_minutes * 60)
            recent_ticks = [t for t in self.tick_buffer 
                          if t.symbol == symbol and t.timestamp_utc >= cutoff_time]
            
            if len(recent_ticks) < 5:
                return False
                
            # Calculate price changes and volume
            prices = np.array([(t.bid + t.ask) / 2 for t in recent_ticks])
            volumes = np.array([t.volume for t in recent_ticks])
            
            if len(prices) < 2:
                return False
                
            # Calculate price changes
            price_changes = np.diff(prices)
            
            # Calculate volume delta (simplified proxy)
            volume_delta = np.sum(volumes[1:]) - np.sum(volumes[:-1])
            
            # Check for spike conditions
            delta_threshold = self.symbol_config.get('delta_threshold', 1.5)
            avg_volume = np.mean(volumes)
            
            # Spike if volume delta is significant and price moved
            volume_spike = abs(volume_delta) > (avg_volume * delta_threshold)
            price_movement = abs(price_changes[-1]) > 0.0001  # Minimum price movement
            
            return volume_spike and price_movement
            
        except Exception as e:
            logger.error(f"Error checking delta spike for {symbol}: {e}")
            return False
            
    def check_micro_bos(self, symbol: str, current_price: float, 
                       timestamp_utc: int, lookback_bars: int = 10) -> bool:
        """Check for micro BOS (Break of Structure) on M1"""
        try:
            # Get recent ticks for micro BOS analysis
            cutoff_time = timestamp_utc - (lookback_bars * 60)  # 1 bar = 1 minute
            recent_ticks = [t for t in self.tick_buffer 
                          if t.symbol == symbol and t.timestamp_utc >= cutoff_time]
            
            if len(recent_ticks) < lookback_bars:
                return False
                
            # Group ticks into 1-minute bars
            bars = self._group_ticks_into_bars(recent_ticks, 60)  # 60 seconds = 1 minute
            
            if len(bars) < lookback_bars:
                return False
                
            # Check for BOS pattern
            highs = [bar['high'] for bar in bars]
            lows = [bar['low'] for bar in bars]
            
            # Find recent high/low
            recent_high = max(highs[-lookback_bars:])
            recent_low = min(lows[-lookback_bars:])
            
            # Check if current price breaks structure
            min_displacement = self.symbol_config.get('min_displacement_atr', 0.25)
            max_displacement = self.symbol_config.get('max_displacement_atr', 0.5)
            
            # Calculate ATR for displacement check
            atr = self._calculate_atr_from_bars(bars)
            if atr == 0:
                return False
                
            # Check displacement
            displacement = abs(current_price - recent_high) / atr
            return min_displacement <= displacement <= max_displacement
            
        except Exception as e:
            logger.error(f"Error checking micro BOS for {symbol}: {e}")
            return False
            
    def check_atr_ratio(self, symbol: str, timestamp_utc: int) -> bool:
        """Check ATR ratio between M1 and M5"""
        try:
            # Get M1 ATR
            m1_atr = self._get_m1_atr(symbol, timestamp_utc)
            m5_atr = self._get_m5_atr(symbol, timestamp_utc)
            
            if m1_atr == 0 or m5_atr == 0:
                return False
                
            atr_ratio = m1_atr / m5_atr
            atr_threshold = self.symbol_config.get('atr_ratio_threshold', 0.5)
            
            return atr_ratio <= atr_threshold
            
        except Exception as e:
            logger.error(f"Error checking ATR ratio for {symbol}: {e}")
            return False
            
    def check_spread_validity(self, symbol: str, timestamp_utc: int, 
                            lookback_minutes: int = 20) -> bool:
        """Check if spread is within normal range"""
        try:
            # Get recent spreads
            cutoff_time = timestamp_utc - (lookback_minutes * 60)
            recent_ticks = [t for t in self.tick_buffer 
                          if t.symbol == symbol and t.timestamp_utc >= cutoff_time]
            
            if len(recent_ticks) < 10:
                return False
                
            spreads = np.array([t.spread for t in recent_ticks])
            
            # Calculate rolling median
            median_window = self.symbol_config.get('spread_median_window', 20)
            rolling_median = self.calculate_rolling_median(spreads, median_window)
            
            if len(rolling_median) == 0:
                return False
                
            current_spread = spreads[-1]
            median_spread = rolling_median[-1]
            
            # Check if current spread is within normal range
            outlier_clip = self.symbol_config.get('spread_outlier_clip', 2.0)
            max_spread = median_spread * outlier_clip
            
            return current_spread <= max_spread
            
        except Exception as e:
            logger.error(f"Error checking spread validity for {symbol}: {e}")
            return False
            
    def analyze_filters(self, symbol: str, current_price: float, 
                       timestamp_utc: int) -> M1FilterResult:
        """Analyze all M1 filters for a symbol"""
        
        # Check each filter
        vwap_reclaim = self.check_vwap_reclaim(symbol, current_price, timestamp_utc)
        delta_spike = self.check_delta_spike(symbol, current_price, timestamp_utc)
        micro_bos = self.check_micro_bos(symbol, current_price, timestamp_utc)
        atr_ratio_valid = self.check_atr_ratio(symbol, timestamp_utc)
        spread_valid = self.check_spread_validity(symbol, timestamp_utc)
        
        # Count passed filters
        filters_passed = int(sum([vwap_reclaim, delta_spike, micro_bos, atr_ratio_valid, spread_valid]))
        
        # Calculate filter score (0-1)
        filter_score = filters_passed / 5.0
        
        # Calculate confidence based on filter alignment
        confidence = self._calculate_filter_confidence(
            vwap_reclaim, delta_spike, micro_bos, atr_ratio_valid, spread_valid
        )
        
        return M1FilterResult(
            symbol=symbol,
            timestamp_utc=timestamp_utc,
            vwap_reclaim=vwap_reclaim,
            delta_spike=delta_spike,
            micro_bos=micro_bos,
            atr_ratio_valid=atr_ratio_valid,
            spread_valid=spread_valid,
            filters_passed=filters_passed,
            filter_score=filter_score,
            confidence=confidence
        )
        
    def _calculate_filter_confidence(self, vwap_reclaim: bool, delta_spike: bool,
                                   micro_bos: bool, atr_ratio_valid: bool,
                                   spread_valid: bool) -> float:
        """Calculate confidence based on filter alignment"""
        base_confidence = 0.3
        
        # VWAP reclaim is most important
        if vwap_reclaim:
            base_confidence += 0.3
            
        # Delta spike adds momentum confirmation
        if delta_spike:
            base_confidence += 0.2
            
        # Micro BOS adds structure confirmation
        if micro_bos:
            base_confidence += 0.2
            
        # ATR and spread are supporting filters
        if atr_ratio_valid:
            base_confidence += 0.1
            
        if spread_valid:
            base_confidence += 0.1
            
        return min(1.0, base_confidence)
        
    def _group_ticks_into_bars(self, ticks: List[TickData], bar_seconds: int) -> List[Dict[str, Any]]:
        """Group ticks into bars"""
        if not ticks:
            return []
            
        bars = []
        current_bar = None
        bar_start_time = None
        
        for tick in ticks:
            bar_time = (tick.timestamp_utc // bar_seconds) * bar_seconds
            
            if current_bar is None or bar_time != bar_start_time:
                # Start new bar
                if current_bar is not None:
                    bars.append(current_bar)
                    
                current_bar = {
                    'timestamp': bar_time,
                    'open': (tick.bid + tick.ask) / 2,
                    'high': (tick.bid + tick.ask) / 2,
                    'low': (tick.bid + tick.ask) / 2,
                    'close': (tick.bid + tick.ask) / 2,
                    'volume': tick.volume
                }
                bar_start_time = bar_time
            else:
                # Update current bar
                price = (tick.bid + tick.ask) / 2
                current_bar['high'] = max(current_bar['high'], price)
                current_bar['low'] = min(current_bar['low'], price)
                current_bar['close'] = price
                current_bar['volume'] += tick.volume
                
        if current_bar is not None:
            bars.append(current_bar)
            
        return bars
        
    def _calculate_atr_from_bars(self, bars: List[Dict[str, Any]], period: int = 14) -> float:
        """Calculate ATR from bars"""
        if len(bars) < period:
            return 0.0
            
        highs = [bar['high'] for bar in bars[-period:]]
        lows = [bar['low'] for bar in bars[-period:]]
        closes = [bar['close'] for bar in bars[-period:]]
        
        # Calculate True Range
        tr_values = []
        for i in range(1, len(highs)):
            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i-1])
            lc = abs(lows[i] - closes[i-1])
            tr_values.append(max(hl, hc, lc))
            
        return np.mean(tr_values) if tr_values else 0.0
        
    def _get_m1_atr(self, symbol: str, timestamp_utc: int) -> float:
        """Get M1 ATR for symbol"""
        # This would typically come from cached data or database
        # For now, return a placeholder
        return 0.001  # Placeholder
        
    def _get_m5_atr(self, symbol: str, timestamp_utc: int) -> float:
        """Get M5 ATR for symbol"""
        # This would typically come from cached data or database
        # For now, return a placeholder
        return 0.005  # Placeholder
        
    def add_tick(self, tick: TickData):
        """Add tick to buffer for analysis"""
        self.tick_buffer.append(tick)
        
        # Keep only recent ticks (last 2 hours)
        cutoff_time = tick.timestamp_utc - (2 * 3600)
        self.tick_buffer = [t for t in self.tick_buffer if t.timestamp_utc >= cutoff_time]
        
    def should_execute_trade(self, symbol: str, current_price: float, 
                           timestamp_utc: int, min_filters: int = 3) -> Tuple[bool, M1FilterResult]:
        """Determine if trade should be executed based on M1 filters"""
        
        filter_result = self.analyze_filters(symbol, current_price, timestamp_utc)
        
        # Execute if minimum filters passed
        should_execute = filter_result.filters_passed >= min_filters
        
        return should_execute, filter_result


# Example usage and testing
if __name__ == "__main__":
    # Test M1 precision filters
    config = {
        'vwap_threshold': 0.2,
        'delta_threshold': 1.5,
        'atr_ratio_threshold': 0.5,
        'min_displacement_atr': 0.25,
        'max_displacement_atr': 0.5,
        'spread_median_window': 20,
        'spread_outlier_clip': 2.0
    }
    
    filters = M1PrecisionFilters(config)
    
    # Test with sample data
    current_time = int(datetime.now(timezone.utc).timestamp())
    test_price = 50000.0
    
    # Add some sample ticks
    for i in range(100):
        tick = TickData(
            symbol="BTCUSDc",
            timestamp_utc=current_time - (100 - i) * 60,  # 1 minute intervals
            bid=test_price - 0.5,
            ask=test_price + 0.5,
            volume=100 + i * 10,
            spread=1.0
        )
        filters.add_tick(tick)
    
    # Test filter analysis
    should_execute, result = filters.should_execute_trade("BTCUSDc", test_price, current_time)
    
    print(f"Should execute: {should_execute}")
    print(f"Filters passed: {result.filters_passed}/5")
    print(f"Filter score: {result.filter_score:.2f}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"VWAP reclaim: {result.vwap_reclaim}")
    print(f"Delta spike: {result.delta_spike}")
    print(f"Micro BOS: {result.micro_bos}")
    print(f"ATR ratio valid: {result.atr_ratio_valid}")
    print(f"Spread valid: {result.spread_valid}")
