"""
Volume Delta Proxy System
Proxy for volume delta analysis using mid-price changes and tick direction
"""

import numpy as np
from numba import jit, prange
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
import logging
from collections import deque

logger = logging.getLogger(__name__)

class VolumeDeltaProxy:
    """Volume delta proxy using mid-price changes and tick direction"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.delta_threshold = symbol_config.get('delta_threshold', 1.5)
        self.lookback_ticks = symbol_config.get('delta_lookback_ticks', 100)
        self.spike_threshold = symbol_config.get('delta_spike_threshold', 2.0)
        
        # Delta tracking
        self.tick_directions = deque(maxlen=self.lookback_ticks)
        self.price_changes = deque(maxlen=self.lookback_ticks)
        self.volumes = deque(maxlen=self.lookback_ticks)
        self.last_price = None
        self.last_timestamp = None
        
        # Delta calculations
        self.current_delta = 0.0
        self.delta_ma = 0.0
        self.delta_std = 0.0
        
        # Spike detection
        self.spike_detected = False
        self.spike_cooldown = 0
        self.spike_cooldown_ticks = symbol_config.get('delta_spike_cooldown_ticks', 50)
        
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_tick_direction(current_price: float, previous_price: float) -> int:
        """Calculate tick direction: 1 for up, -1 for down, 0 for unchanged"""
        if current_price > previous_price:
            return 1
        elif current_price < previous_price:
            return -1
        else:
            return 0
    
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_delta_proxy(
        tick_directions: np.ndarray,
        volumes: np.ndarray,
        lookback: int
    ) -> Tuple[float, float, float]:
        """Calculate delta proxy using Numba for performance"""
        if len(tick_directions) < lookback:
            return 0.0, 0.0, 0.0
        
        # Get recent data
        recent_directions = tick_directions[-lookback:]
        recent_volumes = volumes[-lookback:]
        
        # Calculate delta proxy
        delta = 0.0
        for i in range(len(recent_directions)):
            delta += recent_directions[i] * recent_volumes[i]
        
        # Calculate moving average
        delta_ma = delta / len(recent_directions)
        
        # Calculate standard deviation
        variance = 0.0
        for i in range(len(recent_directions)):
            diff = (recent_directions[i] * recent_volumes[i]) - delta_ma
            variance += diff * diff
        delta_std = np.sqrt(variance / len(recent_directions))
        
        return delta, delta_ma, delta_std
    
    def update_delta(self, tick_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update delta proxy with new tick data"""
        try:
            current_time = tick_data['timestamp_utc']
            current_price = (tick_data['bid'] + tick_data['ask']) / 2
            volume = tick_data.get('volume', 0.0)
            
            # Calculate tick direction
            if self.last_price is not None:
                direction = self.calculate_tick_direction(current_price, self.last_price)
                price_change = abs(current_price - self.last_price)
            else:
                direction = 0
                price_change = 0.0
            
            # Store data
            self.tick_directions.append(direction)
            self.price_changes.append(price_change)
            self.volumes.append(volume)
            
            # Calculate delta proxy
            if len(self.tick_directions) >= 10:  # Minimum data for calculation
                directions_array = np.array(self.tick_directions, dtype=np.float32)
                volumes_array = np.array(self.volumes, dtype=np.float32)
                
                self.current_delta, self.delta_ma, self.delta_std = self.calculate_delta_proxy(
                    directions_array, volumes_array, min(50, len(self.tick_directions))
                )
            
            # Update spike detection
            self._update_spike_detection()
            
            # Update state
            self.last_price = current_price
            self.last_timestamp = current_time
            
            return {
                'delta': self.current_delta,
                'delta_ma': self.delta_ma,
                'delta_std': self.delta_std,
                'spike_detected': self.spike_detected,
                'direction': direction,
                'price_change': price_change
            }
            
        except Exception as e:
            logger.error(f"Error updating delta proxy: {e}")
            return {
                'delta': self.current_delta,
                'delta_ma': self.delta_ma,
                'delta_std': self.delta_std,
                'spike_detected': False,
                'direction': 0,
                'price_change': 0.0
            }
    
    def _update_spike_detection(self):
        """Update spike detection logic"""
        if self.spike_cooldown > 0:
            self.spike_cooldown -= 1
            self.spike_detected = False
            return
        
        # Check for delta spike
        if self.delta_std > 0:
            z_score = abs(self.current_delta - self.delta_ma) / self.delta_std
            if z_score > self.spike_threshold:
                self.spike_detected = True
                self.spike_cooldown = self.spike_cooldown_ticks
            else:
                self.spike_detected = False
        else:
            self.spike_detected = False
    
    def check_delta_spike(self, current_price: float, timestamp_utc: int) -> Dict[str, Any]:
        """Check for volume delta spike"""
        try:
            # Calculate current delta if we have enough data
            if len(self.tick_directions) < 10:
                return {
                    'spike_detected': False,
                    'delta_strength': 0.0,
                    'confidence': 0.0,
                    'reason': 'insufficient_data'
                }
            
            # Calculate delta strength
            delta_strength = abs(self.current_delta) / max(self.delta_ma, 1.0)
            
            # Calculate confidence based on consistency
            recent_directions = list(self.tick_directions)[-20:]  # Last 20 ticks
            direction_consistency = sum(1 for d in recent_directions if d == recent_directions[-1]) / len(recent_directions)
            
            # Check if spike threshold is met
            spike_threshold_met = delta_strength > self.delta_threshold
            
            # Check if we have a sustained move
            sustained_move = direction_consistency > 0.6 and len(recent_directions) >= 10
            
            # Overall spike detection
            spike_detected = spike_threshold_met and sustained_move and self.spike_detected
            
            return {
                'spike_detected': spike_detected,
                'delta_strength': delta_strength,
                'confidence': direction_consistency,
                'reason': 'spike_detected' if spike_detected else 'no_spike',
                'delta': self.current_delta,
                'delta_ma': self.delta_ma,
                'delta_std': self.delta_std
            }
            
        except Exception as e:
            logger.error(f"Error checking delta spike: {e}")
            return {
                'spike_detected': False,
                'delta_strength': 0.0,
                'confidence': 0.0,
                'reason': 'error'
            }
    
    def get_delta_metrics(self) -> Dict[str, Any]:
        """Get current delta metrics"""
        return {
            'current_delta': self.current_delta,
            'delta_ma': self.delta_ma,
            'delta_std': self.delta_std,
            'spike_detected': self.spike_detected,
            'data_points': len(self.tick_directions),
            'last_price': self.last_price,
            'last_timestamp': self.last_timestamp
        }
    
    def reset_delta(self):
        """Reset delta calculations"""
        self.tick_directions.clear()
        self.price_changes.clear()
        self.volumes.clear()
        self.current_delta = 0.0
        self.delta_ma = 0.0
        self.delta_std = 0.0
        self.spike_detected = False
        self.spike_cooldown = 0
        self.last_price = None
        self.last_timestamp = None
        logger.debug("Delta proxy reset")

# Example usage and testing
if __name__ == "__main__":
    # Test configuration
    test_config = {
        'symbol': 'BTCUSDc',
        'delta_threshold': 1.5,
        'delta_lookback_ticks': 100,
        'delta_spike_threshold': 2.0,
        'delta_spike_cooldown_ticks': 50
    }
    
    # Create delta proxy
    delta_proxy = VolumeDeltaProxy(test_config)
    
    # Simulate tick data with volume delta
    test_ticks = [
        {'timestamp_utc': 1640995200, 'bid': 50000.0, 'ask': 50010.0, 'volume': 100},
        {'timestamp_utc': 1640995260, 'bid': 50100.0, 'ask': 50110.0, 'volume': 200},  # Up move with higher volume
        {'timestamp_utc': 1640995320, 'bid': 50200.0, 'ask': 50210.0, 'volume': 300},  # Another up move
        {'timestamp_utc': 1640995380, 'bid': 50150.0, 'ask': 50160.0, 'volume': 150},  # Down move
    ]
    
    print("Testing Volume Delta Proxy:")
    for i, tick in enumerate(test_ticks):
        result = delta_proxy.update_delta(tick)
        print(f"Tick {i+1}: Delta = {result['delta']:.2f}, MA = {result['delta_ma']:.2f}, Spike = {result['spike_detected']}")
    
    # Test spike detection
    spike_result = delta_proxy.check_delta_spike(50250.0, 1640995440)
    print(f"\nDelta Spike Test: {spike_result}")
    
    # Get metrics
    metrics = delta_proxy.get_delta_metrics()
    print(f"\nDelta Metrics: {metrics}")
