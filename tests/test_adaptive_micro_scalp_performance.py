"""
Performance and Stress Tests for Adaptive Micro-Scalp Strategy System

Tests performance characteristics:
- Large dataset handling
- Multiple concurrent checks
- Memory usage
- Response times
"""

import unittest
from unittest.mock import Mock, patch
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.micro_scalp_regime_detector import MicroScalpRegimeDetector
from infra.micro_scalp_strategy_router import MicroScalpStrategyRouter
from infra.range_boundary_detector import RangeBoundaryDetector


class TestPerformance(unittest.TestCase):
    """Test performance characteristics"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'regime_detection': {
                'enabled': True,
                'strategy_confidence_thresholds': {
                    'vwap_reversion': 70,
                    'range_scalp': 55,
                    'balanced_zone': 60
                }
            }
        }
    
    def test_regime_detection_with_large_candle_set(self):
        """Test regime detection performance with large candle dataset"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        # Create large candle set (1000 candles)
        large_candles = [
            {'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000}
            for i in range(1000)
        ]
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': large_candles,
            'current_price': 2000.0,
            'vwap': 2000.0,
            'atr1': 0.6
        }
        
        # Measure time
        start_time = time.time()
        result = regime_detector.detect_regime(snapshot)
        elapsed = time.time() - start_time
        
        # Should complete in reasonable time (< 1 second)
        self.assertLess(elapsed, 1.0)
        self.assertIsNotNone(result)
    
    def test_strategy_router_performance(self):
        """Test strategy router performance with multiple calls"""
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 75,
            'min_confidence_threshold': 70
        }
        
        # Measure time for multiple calls
        start_time = time.time()
        for _ in range(100):
            strategy = router.select_strategy(snapshot, regime_result)
        elapsed = time.time() - start_time
        
        # Should be fast (< 0.1 seconds for 100 calls)
        self.assertLess(elapsed, 0.1)
        self.assertEqual(strategy, 'vwap_reversion')
    
    def test_regime_cache_performance(self):
        """Test regime cache improves performance on repeated calls"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': [{'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000} for i in range(20)],
            'current_price': 2000.0,
            'vwap': 2000.0,
            'atr1': 0.6
        }
        
        # First call (cache miss)
        start_time = time.time()
        result1 = regime_detector.detect_regime(snapshot)
        first_call_time = time.time() - start_time
        
        # Second call (cache hit)
        start_time = time.time()
        result2 = regime_detector.detect_regime(snapshot)
        second_call_time = time.time() - start_time
        
        # Second call should be faster (cached)
        self.assertLessEqual(second_call_time, first_call_time)
        self.assertEqual(result1['regime'], result2['regime'])


if __name__ == '__main__':
    unittest.main()

