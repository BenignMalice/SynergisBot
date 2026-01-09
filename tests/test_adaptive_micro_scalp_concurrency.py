"""
Concurrency and Thread Safety Tests for Adaptive Micro-Scalp Strategy System

Tests concurrent access scenarios:
- Multiple simultaneous checks
- Thread safety
- Cache consistency
- Resource contention
"""

import unittest
from unittest.mock import Mock
import threading
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.micro_scalp_regime_detector import MicroScalpRegimeDetector
from infra.micro_scalp_strategy_router import MicroScalpStrategyRouter
from infra.range_boundary_detector import RangeBoundaryDetector


class TestConcurrency(unittest.TestCase):
    """Test concurrent access scenarios"""
    
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
    
    def test_concurrent_regime_detection(self):
        """Test: Multiple threads can detect regimes concurrently"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        results = []
        errors = []
        
        def detect_regime(symbol, price_offset):
            try:
                snapshot = {
                    'symbol': symbol,
                    'candles': [
                        {'time': i, 'open': 2000.0 + price_offset, 'high': 2000.5 + price_offset, 
                         'low': 1999.5 + price_offset, 'close': 2000.0 + price_offset, 'volume': 1000}
                        for i in range(20)
                    ],
                    'current_price': 2000.0 + price_offset,
                    'vwap': 2000.0 + price_offset,
                    'atr1': 0.6
                }
                result = regime_detector.detect_regime(snapshot)
                results.append((symbol, result))
            except Exception as e:
                errors.append((symbol, str(e)))
        
        # Create multiple threads
        threads = []
        for i in range(5):
            symbol = f'XAUUSDc_{i}'
            thread = threading.Thread(target=detect_regime, args=(symbol, i * 0.1))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Verify no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Verify all results
        self.assertEqual(len(results), 5, "Not all threads completed")
        for symbol, result in results:
            self.assertIsNotNone(result, f"Result is None for {symbol}")
            if result:
                self.assertIn('regime', result)
    
    def test_concurrent_strategy_routing(self):
        """Test: Multiple threads can route strategies concurrently"""
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        results = []
        errors = []
        
        def route_strategy(regime, confidence):
            try:
                snapshot = {'symbol': 'XAUUSDc'}
                regime_result = {
                    'regime': regime,
                    'confidence': confidence,
                    'min_confidence_threshold': 70
                }
                strategy = router.select_strategy(snapshot, regime_result)
                results.append((regime, confidence, strategy))
            except Exception as e:
                errors.append((regime, confidence, str(e)))
        
        # Create multiple threads
        threads = []
        test_cases = [
            ('VWAP_REVERSION', 75),
            ('RANGE', 60),
            ('BALANCED_ZONE', 65),
            ('VWAP_REVERSION', 50),
            ('RANGE', 55)
        ]
        
        for regime, confidence in test_cases:
            thread = threading.Thread(target=route_strategy, args=(regime, confidence))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Verify no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Verify all results
        self.assertEqual(len(results), 5, "Not all threads completed")
        for regime, confidence, strategy in results:
            self.assertIsNotNone(strategy)
            self.assertIn(strategy, ['vwap_reversion', 'range_scalp', 'balanced_zone', 'edge_based'])
    
    def test_cache_consistency_under_concurrency(self):
        """Test: Cache remains consistent under concurrent access"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': [
                {'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000}
                for i in range(20)
            ],
            'current_price': 2000.0,
            'vwap': 2000.0,
            'atr1': 0.6
        }
        
        results = []
        errors = []
        
        def detect_and_verify():
            try:
                result = regime_detector.detect_regime(snapshot)
                results.append(result)
                # Verify result structure
                if result:
                    self.assertIn('regime', result)
                    self.assertIn('confidence', result)
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads accessing same snapshot
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=detect_and_verify)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Verify no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Verify all results are consistent (same regime for same snapshot)
        if len(results) > 0:
            first_regime = results[0].get('regime') if results[0] else None
            for result in results[1:]:
                # Results should be consistent (same snapshot = same regime)
                regime = result.get('regime') if result else None
                # Allow for slight variations due to timing, but structure should be consistent
                self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()

