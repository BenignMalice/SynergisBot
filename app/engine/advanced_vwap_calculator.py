"""
Advanced VWAP Calculator
Real-time VWAP calculation from MT5 ticks with session anchoring
"""

import numpy as np
from numba import jit, prange
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class AdvancedVWAPCalculator:
    """Advanced VWAP calculator with session anchoring and real-time updates"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.session_anchor = symbol_config.get('session_anchor', '24/7')
        self.sigma_window_minutes = symbol_config.get('vwap_sigma_window_minutes', 60)
        
        # VWAP state
        self.cumulative_volume = 0.0
        self.cumulative_pv = 0.0
        self.current_vwap = 0.0
        self.session_start_time = None
        self.last_update_time = None
        
        # Session management
        self.is_new_session = False
        self.session_reset_required = False
        
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_vwap_incremental(
        current_vwap: float,
        current_volume: float,
        current_pv: float,
        cumulative_volume: float,
        cumulative_pv: float
    ) -> Tuple[float, float, float]:
        """Calculate VWAP incrementally using Numba for performance"""
        new_cumulative_volume = cumulative_volume + current_volume
        new_cumulative_pv = cumulative_pv + current_pv
        
        if new_cumulative_volume > 0:
            new_vwap = new_cumulative_pv / new_cumulative_volume
        else:
            new_vwap = current_vwap
            
        return new_vwap, new_cumulative_volume, new_cumulative_pv
    
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_vwap_standard_deviation(
        prices: np.ndarray,
        volumes: np.ndarray,
        vwap: float,
        window_size: int
    ) -> float:
        """Calculate VWAP standard deviation for sigma bands"""
        if len(prices) < window_size:
            return 0.0
            
        # Get recent data
        recent_prices = prices[-window_size:]
        recent_volumes = volumes[-window_size:]
        
        # Calculate weighted variance
        total_volume = np.sum(recent_volumes)
        if total_volume == 0:
            return 0.0
            
        weighted_variance = 0.0
        for i in range(len(recent_prices)):
            price_diff = recent_prices[i] - vwap
            weight = recent_volumes[i] / total_volume
            weighted_variance += weight * (price_diff ** 2)
            
        return np.sqrt(weighted_variance)
    
    def update_session_anchor(self, current_time: datetime) -> bool:
        """Update session anchor based on symbol type"""
        if self.session_anchor == "24/7":
            # Crypto/commodities - no session reset needed
            return False
            
        elif self.session_anchor == "FX":
            # FX sessions - reset at 00:00 UTC
            if self.session_start_time is None:
                self.session_start_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                return True
            elif current_time.date() != self.session_start_time.date():
                self.session_start_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                return True
                
        elif self.session_anchor == "US":
            # US session - reset at 13:30 UTC (9:30 AM EST)
            if self.session_start_time is None:
                self.session_start_time = current_time.replace(hour=13, minute=30, second=0, microsecond=0)
                return True
            elif current_time.date() != self.session_start_time.date():
                self.session_start_time = current_time.replace(hour=13, minute=30, second=0, microsecond=0)
                return True
                
        return False
    
    def reset_session(self):
        """Reset VWAP session data"""
        self.cumulative_volume = 0.0
        self.cumulative_pv = 0.0
        self.current_vwap = 0.0
        self.is_new_session = True
        logger.debug(f"VWAP session reset for {self.symbol_config.get('symbol', 'unknown')}")
    
    def update_vwap(self, tick_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update VWAP with new tick data"""
        try:
            current_time = datetime.fromtimestamp(tick_data['timestamp_utc'], tz=timezone.utc)
            
            # Check if session reset is needed
            if self.update_session_anchor(current_time):
                self.reset_session()
            
            # Calculate typical price
            typical_price = (tick_data['bid'] + tick_data['ask']) / 2
            volume = tick_data.get('volume', 0.0)
            
            if volume <= 0:
                return {
                    'vwap': self.current_vwap,
                    'cumulative_volume': self.cumulative_volume,
                    'is_new_session': self.is_new_session,
                    'session_age_minutes': self._get_session_age_minutes(current_time)
                }
            
            # Calculate price * volume
            pv = typical_price * volume
            
            # Update VWAP incrementally
            self.current_vwap, self.cumulative_volume, self.cumulative_pv = self.calculate_vwap_incremental(
                self.current_vwap,
                volume,
                pv,
                self.cumulative_volume,
                self.cumulative_pv
            )
            
            self.last_update_time = current_time
            self.is_new_session = False
            
            return {
                'vwap': self.current_vwap,
                'cumulative_volume': self.cumulative_volume,
                'is_new_session': self.is_new_session,
                'session_age_minutes': self._get_session_age_minutes(current_time)
            }
            
        except Exception as e:
            logger.error(f"Error updating VWAP: {e}")
            return {
                'vwap': self.current_vwap,
                'cumulative_volume': self.cumulative_volume,
                'is_new_session': False,
                'session_age_minutes': 0
            }
    
    def _get_session_age_minutes(self, current_time: datetime) -> int:
        """Get session age in minutes"""
        if self.session_start_time is None:
            return 0
        return int((current_time - self.session_start_time).total_seconds() / 60)
    
    def calculate_sigma_bands(self, price_history: np.ndarray, volume_history: np.ndarray, 
                            sigma_multiplier: float = 2.0) -> Dict[str, float]:
        """Calculate VWAP sigma bands"""
        try:
            if len(price_history) < self.sigma_window_minutes:
                return {
                    'upper_band': self.current_vwap,
                    'lower_band': self.current_vwap,
                    'sigma': 0.0
                }
            
            # Calculate standard deviation
            sigma = self.calculate_vwap_standard_deviation(
                price_history, volume_history, self.current_vwap, self.sigma_window_minutes
            )
            
            upper_band = self.current_vwap + (sigma * sigma_multiplier)
            lower_band = self.current_vwap - (sigma * sigma_multiplier)
            
            return {
                'upper_band': upper_band,
                'lower_band': lower_band,
                'sigma': sigma
            }
            
        except Exception as e:
            logger.error(f"Error calculating sigma bands: {e}")
            return {
                'upper_band': self.current_vwap,
                'lower_band': self.current_vwap,
                'sigma': 0.0
            }
    
    def check_vwap_reclaim(self, current_price: float, threshold: float = 0.2) -> Dict[str, Any]:
        """Check if price has reclaimed VWAP with threshold"""
        try:
            if self.current_vwap == 0:
                return {
                    'reclaimed': False,
                    'distance_pips': 0.0,
                    'threshold_met': False
                }
            
            # Calculate distance from VWAP
            distance = abs(current_price - self.current_vwap)
            
            # Calculate threshold in price terms (simplified)
            threshold_price = self.current_vwap * (threshold / 100)
            
            # Check if price is within threshold of VWAP
            threshold_met = distance <= threshold_price
            
            # Check if price has reclaimed VWAP (crossed from below/above)
            reclaimed = threshold_met and distance < threshold_price * 0.5
            
            return {
                'reclaimed': reclaimed,
                'distance_pips': distance,
                'threshold_met': threshold_met,
                'vwap': self.current_vwap,
                'current_price': current_price
            }
            
        except Exception as e:
            logger.error(f"Error checking VWAP reclaim: {e}")
            return {
                'reclaimed': False,
                'distance_pips': 0.0,
                'threshold_met': False
            }
    
    def get_vwap_state(self) -> Dict[str, Any]:
        """Get current VWAP state"""
        return {
            'vwap': self.current_vwap,
            'cumulative_volume': self.cumulative_volume,
            'session_age_minutes': self._get_session_age_minutes(datetime.now(timezone.utc)),
            'is_new_session': self.is_new_session,
            'last_update_time': self.last_update_time
        }

# Example usage and testing
if __name__ == "__main__":
    # Test configuration
    test_config = {
        'symbol': 'BTCUSDc',
        'session_anchor': '24/7',
        'vwap_sigma_window_minutes': 60
    }
    
    # Create calculator
    calculator = AdvancedVWAPCalculator(test_config)
    
    # Simulate tick data
    test_ticks = [
        {'timestamp_utc': 1640995200, 'bid': 50000.0, 'ask': 50010.0, 'volume': 100},
        {'timestamp_utc': 1640995260, 'bid': 50100.0, 'ask': 50110.0, 'volume': 150},
        {'timestamp_utc': 1640995320, 'bid': 50200.0, 'ask': 50210.0, 'volume': 200},
    ]
    
    print("Testing Advanced VWAP Calculator:")
    for i, tick in enumerate(test_ticks):
        result = calculator.update_vwap(tick)
        print(f"Tick {i+1}: VWAP = {result['vwap']:.2f}, Volume = {result['cumulative_volume']:.2f}")
    
    # Test VWAP reclaim
    reclaim_result = calculator.check_vwap_reclaim(50150.0)
    print(f"\nVWAP Reclaim Test: {reclaim_result}")
    
    # Test sigma bands
    price_history = np.array([50000.0, 50100.0, 50200.0])
    volume_history = np.array([100.0, 150.0, 200.0])
    sigma_bands = calculator.calculate_sigma_bands(price_history, volume_history)
    print(f"\nSigma Bands: {sigma_bands}")
