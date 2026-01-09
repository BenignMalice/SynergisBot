"""
Advanced ATR Ratio and Spread Filters
Symbol-specific ATR ratio calculations and spread filtering
"""

import numpy as np
from numba import jit, prange
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
import logging
from collections import deque

logger = logging.getLogger(__name__)

class AdvancedATRFilters:
    """Advanced ATR ratio and spread filters with symbol-specific multipliers"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.symbol = symbol_config.get('symbol', 'unknown')
        
        # ATR configuration
        self.atr_period = symbol_config.get('atr_period', 14)
        self.atr_multiplier_m1 = symbol_config.get('atr_multiplier_m1', 1.5)
        self.atr_multiplier_m5 = symbol_config.get('atr_multiplier_m5', 2.0)
        self.atr_ratio_threshold = symbol_config.get('atr_ratio_threshold', 0.5)
        
        # Spread configuration
        self.spread_median_window = symbol_config.get('spread_median_window', 20)
        self.spread_outlier_threshold = symbol_config.get('spread_outlier_threshold', 3.0)
        self.max_allowed_spread = symbol_config.get('max_allowed_spread', 0.0002)
        
        # Data storage
        self.m1_atr_history = deque(maxlen=100)
        self.m5_atr_history = deque(maxlen=100)
        self.spread_history = deque(maxlen=self.spread_median_window)
        self.price_history = deque(maxlen=100)
        
        # Current values
        self.current_m1_atr = 0.0
        self.current_m5_atr = 0.0
        self.current_atr_ratio = 0.0
        self.current_spread_median = 0.0
        self.spread_valid = True
        
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        """Calculate ATR using Numba for performance"""
        if len(highs) < period:
            return 0.0
        
        # Calculate True Range
        tr_values = np.zeros(len(highs))
        tr_values[0] = highs[0] - lows[0]
        
        for i in range(1, len(highs)):
            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i-1])
            lc = abs(lows[i] - closes[i-1])
            tr_values[i] = max(hl, hc, lc)
        
        # Calculate ATR as SMA of TR
        if len(tr_values) >= period:
            return np.mean(tr_values[-period:])
        else:
            return np.mean(tr_values)
    
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_rolling_median(data: np.ndarray, window: int) -> float:
        """Calculate rolling median using Numba"""
        if len(data) < window:
            return np.median(data)
        else:
            return np.median(data[-window:])
    
    def update_atr_m1(self, ohlcv_data: Dict[str, Any]) -> float:
        """Update M1 ATR calculation"""
        try:
            if len(ohlcv_data.get('high', [])) < self.atr_period:
                return self.current_m1_atr
            
            highs = np.array(ohlcv_data['high'], dtype=np.float32)
            lows = np.array(ohlcv_data['low'], dtype=np.float32)
            closes = np.array(ohlcv_data['close'], dtype=np.float32)
            
            self.current_m1_atr = self.calculate_atr(highs, lows, closes, self.atr_period)
            self.m1_atr_history.append(self.current_m1_atr)
            
            return self.current_m1_atr
            
        except Exception as e:
            logger.error(f"Error updating M1 ATR: {e}")
            return self.current_m1_atr
    
    def update_atr_m5(self, ohlcv_data: Dict[str, Any]) -> float:
        """Update M5 ATR calculation"""
        try:
            if len(ohlcv_data.get('high', [])) < self.atr_period:
                return self.current_m5_atr
            
            highs = np.array(ohlcv_data['high'], dtype=np.float32)
            lows = np.array(ohlcv_data['low'], dtype=np.float32)
            closes = np.array(ohlcv_data['close'], dtype=np.float32)
            
            self.current_m5_atr = self.calculate_atr(highs, lows, closes, self.atr_period)
            self.m5_atr_history.append(self.current_m5_atr)
            
            return self.current_m5_atr
            
        except Exception as e:
            logger.error(f"Error updating M5 ATR: {e}")
            return self.current_m5_atr
    
    def calculate_atr_ratio(self) -> float:
        """Calculate ATR ratio (M1 ATR vs M5 ATR)"""
        try:
            if self.current_m5_atr == 0:
                return 0.0
            
            self.current_atr_ratio = self.current_m1_atr / self.current_m5_atr
            return self.current_atr_ratio
            
        except Exception as e:
            logger.error(f"Error calculating ATR ratio: {e}")
            return 0.0
    
    def check_atr_ratio_validity(self) -> Dict[str, Any]:
        """Check if ATR ratio is within valid range"""
        try:
            ratio = self.calculate_atr_ratio()
            
            # Check if ratio is within acceptable range
            ratio_valid = 0.1 <= ratio <= 10.0  # Reasonable range
            
            # Check if M1 ATR is not too high relative to M5
            m1_atr_valid = self.current_m1_atr <= (self.current_m5_atr * self.atr_multiplier_m1)
            
            # Check if M5 ATR is not too high relative to M1
            m5_atr_valid = self.current_m5_atr <= (self.current_m1_atr * self.atr_multiplier_m5)
            
            overall_valid = ratio_valid and m1_atr_valid and m5_atr_valid
            
            return {
                'valid': overall_valid,
                'ratio': ratio,
                'm1_atr': self.current_m1_atr,
                'm5_atr': self.current_m5_atr,
                'ratio_valid': ratio_valid,
                'm1_atr_valid': m1_atr_valid,
                'm5_atr_valid': m5_atr_valid
            }
            
        except Exception as e:
            logger.error(f"Error checking ATR ratio validity: {e}")
            return {
                'valid': False,
                'ratio': 0.0,
                'm1_atr': 0.0,
                'm5_atr': 0.0,
                'ratio_valid': False,
                'm1_atr_valid': False,
                'm5_atr_valid': False
            }
    
    def update_spread(self, tick_data: Dict[str, Any]) -> float:
        """Update spread calculation"""
        try:
            spread = tick_data['ask'] - tick_data['bid']
            self.spread_history.append(spread)
            
            # Calculate rolling median
            if len(self.spread_history) >= 3:
                spread_array = np.array(self.spread_history, dtype=np.float32)
                self.current_spread_median = self.calculate_rolling_median(
                    spread_array, min(self.spread_median_window, len(spread_array))
                )
            
            return spread
            
        except Exception as e:
            logger.error(f"Error updating spread: {e}")
            return 0.0
    
    def check_spread_validity(self, current_spread: float) -> Dict[str, Any]:
        """Check if current spread is valid"""
        try:
            # Check against maximum allowed spread
            max_spread_valid = current_spread <= self.max_allowed_spread
            
            # Check against rolling median (outlier detection)
            if len(self.spread_history) >= 5:
                spread_array = np.array(self.spread_history, dtype=np.float32)
                median_spread = np.median(spread_array)
                std_spread = np.std(spread_array)
                
                # Check if current spread is within reasonable range
                outlier_threshold = median_spread + (std_spread * self.spread_outlier_threshold)
                outlier_valid = current_spread <= outlier_threshold
            else:
                outlier_valid = True
            
            # Overall spread validity
            spread_valid = max_spread_valid and outlier_valid
            
            return {
                'valid': spread_valid,
                'current_spread': current_spread,
                'median_spread': self.current_spread_median,
                'max_allowed': self.max_allowed_spread,
                'max_spread_valid': max_spread_valid,
                'outlier_valid': outlier_valid
            }
            
        except Exception as e:
            logger.error(f"Error checking spread validity: {e}")
            return {
                'valid': False,
                'current_spread': current_spread,
                'median_spread': 0.0,
                'max_allowed': self.max_allowed_spread,
                'max_spread_valid': False,
                'outlier_valid': False
            }
    
    def get_filter_status(self) -> Dict[str, Any]:
        """Get current filter status"""
        atr_ratio_status = self.check_atr_ratio_validity()
        
        return {
            'atr_ratio': atr_ratio_status,
            'm1_atr': self.current_m1_atr,
            'm5_atr': self.current_m5_atr,
            'spread_median': self.current_spread_median,
            'data_points': len(self.m1_atr_history),
            'symbol': self.symbol
        }
    
    def reset_filters(self):
        """Reset all filter data"""
        self.m1_atr_history.clear()
        self.m5_atr_history.clear()
        self.spread_history.clear()
        self.price_history.clear()
        self.current_m1_atr = 0.0
        self.current_m5_atr = 0.0
        self.current_atr_ratio = 0.0
        self.current_spread_median = 0.0
        self.spread_valid = True
        logger.debug(f"ATR filters reset for {self.symbol}")

# Example usage and testing
if __name__ == "__main__":
    # Test configuration for different symbols
    test_configs = {
        'BTCUSDc': {
            'symbol': 'BTCUSDc',
            'atr_multiplier_m1': 1.5,
            'atr_multiplier_m5': 2.0,
            'max_allowed_spread': 10.0,
            'spread_median_window': 20
        },
        'EURUSDc': {
            'symbol': 'EURUSDc',
            'atr_multiplier_m1': 1.2,
            'atr_multiplier_m5': 1.8,
            'max_allowed_spread': 0.0002,
            'spread_median_window': 20
        }
    }
    
    print("Testing Advanced ATR Filters:")
    
    for symbol, config in test_configs.items():
        print(f"\n--- {symbol} ---")
        atr_filters = AdvancedATRFilters(config)
        
        # Simulate M1 data
        m1_data = {
            'high': [100.0, 101.0, 102.0, 103.0, 104.0],
            'low': [99.0, 100.0, 101.0, 102.0, 103.0],
            'close': [99.5, 100.5, 101.5, 102.5, 103.5]
        }
        
        # Simulate M5 data
        m5_data = {
            'high': [100.0, 102.0, 104.0, 106.0, 108.0],
            'low': [99.0, 101.0, 103.0, 105.0, 107.0],
            'close': [99.5, 101.5, 103.5, 105.5, 107.5]
        }
        
        # Update ATR calculations
        m1_atr = atr_filters.update_atr_m1(m1_data)
        m5_atr = atr_filters.update_atr_m5(m5_data)
        
        print(f"M1 ATR: {m1_atr:.4f}")
        print(f"M5 ATR: {m5_atr:.4f}")
        
        # Check ATR ratio validity
        atr_status = atr_filters.check_atr_ratio_validity()
        print(f"ATR Ratio Status: {atr_status}")
        
        # Test spread validity
        test_spread = 0.0001 if symbol == 'EURUSDc' else 5.0
        spread_status = atr_filters.check_spread_validity(test_spread)
        print(f"Spread Status: {spread_status}")
        
        # Get overall status
        status = atr_filters.get_filter_status()
        print(f"Overall Status: {status}")
