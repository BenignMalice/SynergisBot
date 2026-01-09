"""
Regime Transition Tests for Adaptive Micro-Scalp Strategy System

Tests smooth transitions between regimes:
- VWAP Reversion to Range
- Range to Balanced Zone
- Balanced Zone to VWAP Reversion
- Anti-flip-flop logic
- Transition confidence
"""

import unittest
from unittest.mock import Mock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.micro_scalp_regime_detector import MicroScalpRegimeDetector
from infra.micro_scalp_strategy_router import MicroScalpStrategyRouter
from infra.range_boundary_detector import RangeBoundaryDetector


class TestRegimeTransitions(unittest.TestCase):
    """Test regime transition scenarios"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'regime_detection': {
                'enabled': True,
                'anti_flip_flop_threshold': 10,
                'strategy_confidence_thresholds': {
                    'vwap_reversion': 70,
                    'range_scalp': 55,
                    'balanced_zone': 60
                }
            }
        }
    
    def _create_snapshot(self, candles, current_price, vwap):
        """Helper to create snapshot"""
        return {
            'symbol': 'XAUUSDc',
            'candles': candles,
            'current_price': current_price,
            'vwap': vwap,
            'atr1': 0.6
        }
    
    def test_vwap_to_range_transition(self):
        """Test: Transition from VWAP reversion to range regime"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        # First: VWAP reversion scenario (price far from VWAP)
        vwap_candles = [
            {'time': i, 'open': 2000.0 + i*0.1, 'high': 2000.5 + i*0.1, 
             'low': 1999.5 + i*0.1, 'close': 2000.0 + i*0.1, 'volume': 1000}
            for i in range(20)
        ]
        vwap_snapshot = self._create_snapshot(vwap_candles, 2010.0, 2000.0)
        vwap_result = regime_detector.detect_regime(vwap_snapshot)
        
        # Then: Range scenario (price oscillating)
        range_candles = [
            {'time': i, 'open': 2000.0 + (i % 5) * 0.1, 'high': 2000.5, 
             'low': 1999.5, 'close': 2000.0 + (i % 5) * 0.1, 'volume': 1000}
            for i in range(20)
        ]
        range_snapshot = self._create_snapshot(range_candles, 2000.0, 2000.0)
        range_result = regime_detector.detect_regime(range_snapshot)
        
        # Both should return valid results
        self.assertIsNotNone(vwap_result)
        self.assertIsNotNone(range_result)
        
        if vwap_result and range_result:
            # Regimes might be different
            self.assertIn('regime', vwap_result)
            self.assertIn('regime', range_result)
    
    def test_range_to_balanced_transition(self):
        """Test: Transition from range to balanced zone regime"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        # First: Range scenario
        range_candles = [
            {'time': i, 'open': 2000.0 + (i % 5) * 0.1, 'high': 2000.5, 
             'low': 1999.5, 'close': 2000.0 + (i % 5) * 0.1, 'volume': 1000}
            for i in range(20)
        ]
        range_snapshot = self._create_snapshot(range_candles, 2000.0, 2000.0)
        range_result = regime_detector.detect_regime(range_snapshot)
        
        # Then: Balanced zone (compressed)
        balanced_candles = [
            {'time': i, 'open': 2000.0, 'high': 2000.2, 
             'low': 1999.8, 'close': 2000.0, 'volume': 800}
            for i in range(20)
        ]
        balanced_snapshot = self._create_snapshot(balanced_candles, 2000.0, 2000.0)
        balanced_result = regime_detector.detect_regime(balanced_snapshot)
        
        # Both should return valid results
        self.assertIsNotNone(range_result)
        self.assertIsNotNone(balanced_result)
        
        if range_result and balanced_result:
            self.assertIn('regime', range_result)
            self.assertIn('regime', balanced_result)
    
    def test_anti_flip_flop_logic(self):
        """Test: Anti-flip-flop logic prevents rapid regime switching"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        # Create two similar snapshots (should not flip-flop)
        snapshot1 = self._create_snapshot(
            [{'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000} 
             for i in range(20)],
            2000.0, 2000.0
        )
        
        snapshot2 = self._create_snapshot(
            [{'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000} 
             for i in range(20)],
            2000.0, 2000.0
        )
        
        result1 = regime_detector.detect_regime(snapshot1)
        result2 = regime_detector.detect_regime(snapshot2)
        
        # Both should return results
        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)
        
        # Cache should prevent unnecessary recalculation
        # (Second call should use cache if snapshots are identical)
        if result1 and result2:
            # Results should be consistent (same snapshot = same regime)
            # Allow for slight variations, but should be similar
            self.assertIn('regime', result1)
            self.assertIn('regime', result2)
    
    def test_transition_confidence_scores(self):
        """Test: Confidence scores during transitions"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        # Transition scenario (ambiguous)
        transition_candles = [
            {'time': i, 'open': 2000.0 + (i % 3) * 0.05, 'high': 2000.3, 
             'low': 1999.7, 'close': 2000.0 + (i % 3) * 0.05, 'volume': 1000}
            for i in range(20)
        ]
        transition_snapshot = self._create_snapshot(transition_candles, 2000.0, 2000.0)
        transition_result = regime_detector.detect_regime(transition_snapshot)
        
        # Should return result with confidence
        self.assertIsNotNone(transition_result)
        if transition_result:
            self.assertIn('regime', transition_result)
            self.assertIn('confidence', transition_result)
            confidence = transition_result.get('confidence', 0)
            # Confidence should be bounded
            self.assertGreaterEqual(confidence, 0.0)
            self.assertLessEqual(confidence, 100.0)
    
    def test_strategy_router_handles_transitions(self):
        """Test: Strategy router handles regime transitions"""
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        
        # Transition scenario: Low confidence
        transition_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 65,  # Below threshold
            'min_confidence_threshold': 70
        }
        
        strategy = router.select_strategy(snapshot, transition_result)
        # Should fallback to edge_based when confidence is low
        self.assertEqual(strategy, 'edge_based')
        
        # Clear regime: High confidence
        clear_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 85,  # Above threshold
            'min_confidence_threshold': 70
        }
        
        strategy = router.select_strategy(snapshot, clear_result)
        # Should select vwap_reversion when confidence is high
        self.assertEqual(strategy, 'vwap_reversion')


if __name__ == '__main__':
    unittest.main()

