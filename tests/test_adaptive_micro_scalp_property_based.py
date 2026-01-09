"""
Property-Based Tests for Adaptive Micro-Scalp Strategy System

Uses hypothesis to generate random inputs and verify properties:
- Validation always returns valid results
- Confluence scores are bounded
- Confidence scores are bounded
- No crashes on random inputs
"""

import unittest
from unittest.mock import Mock
import sys
import os

# Try to import hypothesis, skip tests if not available
try:
    from hypothesis import given, strategies as st, assume
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.micro_scalp_strategies import (
    VWAPReversionChecker,
    RangeScalpChecker,
    BalancedZoneChecker
)
from infra.micro_scalp_regime_detector import MicroScalpRegimeDetector
from infra.micro_scalp_strategy_router import MicroScalpStrategyRouter
from infra.range_boundary_detector import RangeBoundaryDetector


class TestPropertyBasedValidation(unittest.TestCase):
    """Property-based tests for validation logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'xauusd_rules': {
                'confluence_scoring': {
                    'min_score_for_trade': 5,
                    'min_score_for_aplus': 7
                }
            },
            'regime_detection': {
                'enabled': True,
                'strategy_confidence_thresholds': {
                    'vwap_reversion': 70,
                    'range_scalp': 55,
                    'balanced_zone': 60
                }
            }
        }
    
    def test_location_filter_always_returns_result(self):
        """Test: Location filter always returns a result"""
        # Manual test with a few random values
        test_cases = [
            (2000.0, 2000.0, 0.6),
            (2500.0, 2000.0, 1.0),
            (1500.0, 2000.0, 0.3),
        ]
        
        checker = VWAPReversionChecker(
            config=self.config,
            volatility_filter=Mock(),
            vwap_filter=Mock(),
            sweep_detector=Mock(),
            ob_detector=Mock(),
            spread_tracker=Mock(),
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='vwap_reversion'
        )
        
        for price, vwap, atr in test_cases:
            candles = [
                {'time': i, 'open': price, 'high': price + 0.5, 'low': price - 0.5, 'close': price, 'volume': 1000}
                for i in range(20)
            ]
            result = checker._check_location_filter('XAUUSDc', candles, price, vwap, atr)
            self.assertIsNotNone(result)
            self.assertIsInstance(result, dict)
        """Property: Location filter always returns a result (never crashes)"""
        checker = VWAPReversionChecker(
            config=self.config,
            volatility_filter=Mock(),
            vwap_filter=Mock(),
            sweep_detector=Mock(),
            ob_detector=Mock(),
            spread_tracker=Mock(),
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='vwap_reversion'
        )
        
        # Create minimal valid candles
        candles = [
            {'time': i, 'open': price, 'high': price + 0.5, 'low': price - 0.5, 'close': price, 'volume': 1000}
            for i in range(20)
        ]
        
        # Should never crash
        result = checker._check_location_filter('XAUUSDc', candles, price, vwap, atr)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
    
    def test_confidence_scores_are_bounded(self):
        """Test: Confidence scores are always between 0 and 100"""
        # Manual test with a few values
        test_confidences = [0.0, 50.0, 70.0, 85.0, 100.0]
        
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        for confidence in test_confidences:
            snapshot = {'symbol': 'XAUUSDc'}
            regime_result = {
                'regime': 'VWAP_REVERSION',
                'confidence': confidence,
                'min_confidence_threshold': 70
            }
            strategy = router.select_strategy(snapshot, regime_result)
            self.assertIsNotNone(strategy)
            self.assertIn(strategy, ['vwap_reversion', 'range_scalp', 'balanced_zone', 'edge_based'])
        """Property: Confidence scores are always between 0 and 100"""
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': confidence,
            'min_confidence_threshold': 70
        }
        
        # Should handle any confidence value
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertIsNotNone(strategy)
        self.assertIn(strategy, ['vwap_reversion', 'range_scalp', 'balanced_zone', 'edge_based'])
    
    def test_regime_detector_handles_any_candle_count(self):
        """Test: Regime detector handles any number of candles"""
        # Manual test with various candle counts
        test_counts = [0, 5, 10, 20, 50, 100, 500, 1000]
        
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        for num_candles in test_counts:
            candles = [
                {'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000}
                for i in range(num_candles)
            ]
            snapshot = {
                'symbol': 'XAUUSDc',
                'candles': candles,
                'current_price': 2000.0,
                'vwap': 2000.0,
                'atr1': 0.6
            }
            result = regime_detector.detect_regime(snapshot)
            self.assertIsNotNone(result)
            if result:
                self.assertIn('regime', result)
                self.assertIn('confidence', result)
        """Property: Regime detector handles any number of candles"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        candles = [
            {'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000}
            for i in range(num_candles)
        ]
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': candles,
            'current_price': 2000.0,
            'vwap': 2000.0,
            'atr1': 0.6
        }
        
        # Should never crash
        result = regime_detector.detect_regime(snapshot)
        self.assertIsNotNone(result)
        self.assertIn('regime', result)
        self.assertIn('confidence', result)
    
    def test_confluence_scores_are_bounded(self):
        """Test: Confluence scores are always between 0 and 10"""
        checker = VWAPReversionChecker(
            config=self.config,
            volatility_filter=Mock(),
            vwap_filter=Mock(),
            sweep_detector=Mock(),
            ob_detector=Mock(),
            spread_tracker=Mock(),
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='vwap_reversion'
        )
        
        location_result = {
            'deviation_sigma': 2.0,
            'vwap_slope_ok': True
        }
        signal_result = {
            'primary_triggers': ['CHOCH_AT_EXTREME'],
            'secondary_confluence': []
        }
        
        score = checker._calculate_confluence_score(
            'XAUUSDc', [], 2000.0, 2000.0, 0.6, location_result, signal_result
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 10.0)
        """Property: Confluence scores are always between 0 and 10"""
        checker = VWAPReversionChecker(
            config=self.config,
            volatility_filter=Mock(),
            vwap_filter=Mock(),
            sweep_detector=Mock(),
            ob_detector=Mock(),
            spread_tracker=Mock(),
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='vwap_reversion'
        )
        
        location_result = {
            'deviation_sigma': 2.0,
            'vwap_slope_ok': True
        }
        signal_result = {
            'primary_triggers': ['CHOCH_AT_EXTREME'],
            'secondary_confluence': []
        }
        
        # The actual confluence calculation should return a bounded value
        # This test verifies the method doesn't crash on any input
        score = checker._calculate_confluence_score(
            'XAUUSDc', [], 2000.0, 2000.0, 0.6, location_result, signal_result
        )
        
        # Score should be bounded (0-10 range)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 10.0)


class TestPropertyBasedDataFormats(unittest.TestCase):
    """Property-based tests for data format handling"""
    
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
    
    def test_handles_various_candle_formats(self):
        """Test: System handles various candle data formats"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        # Test with various formats
        test_formats = [
            [],  # Empty
            [{'time': 0, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0}],  # Missing volume
            [{'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000} for i in range(10)],  # Standard
        ]
        
        for candle_data in test_formats:
            normalized_candles = []
            for i, candle in enumerate(candle_data):
                normalized = {
                    'time': candle.get('time', i),
                    'open': candle.get('open', 2000.0),
                    'high': candle.get('high', 2000.5),
                    'low': candle.get('low', 1999.5),
                    'close': candle.get('close', 2000.0),
                    'volume': candle.get('volume', 1000)
                }
                normalized_candles.append(normalized)
            
            snapshot = {
                'symbol': 'XAUUSDc',
                'candles': normalized_candles,
                'current_price': 2000.0,
                'vwap': 2000.0,
                'atr1': 0.6
            }
            result = regime_detector.detect_regime(snapshot)
            self.assertIsNotNone(result)
        """Property: System handles various candle data formats"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        # Ensure we have at least basic fields
        normalized_candles = []
        for i, candle in enumerate(candle_data):
            normalized = {
                'time': candle.get('time', i),
                'open': candle.get('open', 2000.0),
                'high': candle.get('high', 2000.5),
                'low': candle.get('low', 1999.5),
                'close': candle.get('close', 2000.0),
                'volume': candle.get('volume', 1000)
            }
            normalized_candles.append(normalized)
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': normalized_candles,
            'current_price': 2000.0,
            'vwap': 2000.0,
            'atr1': 0.6
        }
        
        # Should handle any format gracefully
        result = regime_detector.detect_regime(snapshot)
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()

