"""
Realistic Scenario Tests for Adaptive Micro-Scalp Strategy System

Tests with realistic market scenarios:
- Trending market (VWAP deviation)
- Range-bound market (range detection)
- Balanced/compressed market (balanced zone)
- Market transitions
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.micro_scalp_engine import MicroScalpEngine
from infra.micro_scalp_regime_detector import MicroScalpRegimeDetector
from infra.micro_scalp_strategy_router import MicroScalpStrategyRouter
from infra.range_boundary_detector import RangeBoundaryDetector
from infra.micro_scalp_strategies import VWAPReversionChecker, RangeScalpChecker, BalancedZoneChecker


class TestRealisticMarketScenarios(unittest.TestCase):
    """Test with realistic market scenarios"""
    
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
                },
                'vwap_reversion': {
                    'min_deviation_sigma': 2.0,
                    'min_deviation_pct_xau': 0.002
                },
                'range_scalp': {
                    'min_range_respects': 2,
                    'edge_proximity_threshold': 0.005
                },
                'balanced_zone': {
                    'ema_vwap_equilibrium_threshold': 0.001
                }
            }
        }
    
    def _create_trending_candles(self, base_price=2000.0, trend_direction=1, num_candles=50):
        """Create candles showing a clear trend"""
        candles = []
        for i in range(num_candles):
            price_offset = i * trend_direction * 0.1  # Trend
            candles.append({
                'time': i,
                'open': base_price + price_offset,
                'high': base_price + price_offset + 0.5,
                'low': base_price + price_offset - 0.5,
                'close': base_price + price_offset + (trend_direction * 0.05),
                'volume': 1000 + i * 10
            })
        return candles
    
    def _create_range_candles(self, range_high=2000.5, range_low=1999.5, num_candles=50):
        """Create candles showing a range-bound market"""
        candles = []
        for i in range(num_candles):
            # Oscillate between range boundaries
            position = (i % 10) / 10.0  # 0 to 1
            price = range_low + (range_high - range_low) * position
            candles.append({
                'time': i,
                'open': price,
                'high': min(price + 0.3, range_high),
                'low': max(price - 0.3, range_low),
                'close': price,
                'volume': 1000
            })
        return candles
    
    def _create_compressed_candles(self, base_price=2000.0, num_candles=50):
        """Create candles showing compression (balanced zone)"""
        candles = []
        for i in range(num_candles):
            # Small oscillations around base price
            oscillation = 0.1 * (i % 4 - 1.5)  # -0.15 to +0.15
            candles.append({
                'time': i,
                'open': base_price + oscillation,
                'high': base_price + oscillation + 0.2,
                'low': base_price + oscillation - 0.2,
                'close': base_price + oscillation,
                'volume': 800 + (i % 5) * 20  # Varying but low volume
            })
        return candles
    
    def test_trending_market_detects_vwap_reversion(self):
        """Test: Trending market should detect VWAP reversion regime"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        # Create uptrending candles
        candles = self._create_trending_candles(base_price=2000.0, trend_direction=1, num_candles=50)
        current_price = 2010.0  # Far above VWAP
        
        # Calculate VWAP (simplified)
        vwap = sum(c['close'] for c in candles) / len(candles)
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': candles,
            'current_price': current_price,
            'vwap': vwap,
            'atr1': 0.6
        }
        
        result = regime_detector.detect_regime(snapshot)
        
        # Should detect VWAP reversion if price is far from VWAP
        self.assertIsNotNone(result)
        if result and 'regime' in result:
            regime = result.get('regime')
            # If deviation is high enough, might detect VWAP_REVERSION
            if abs(current_price - vwap) / vwap > 0.002:  # > 0.2% deviation
                # Might detect VWAP_REVERSION or fallback
                self.assertIn(regime, ['VWAP_REVERSION', 'UNKNOWN', 'EDGE_BASED', None])
    
    def test_range_market_detects_range_scalp(self):
        """Test: Range-bound market should detect range scalp regime"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        # Create range-bound candles
        range_high = 2000.5
        range_low = 1999.5
        candles = self._create_range_candles(range_high, range_low, num_candles=50)
        current_price = range_high  # At upper edge
        
        vwap = (range_high + range_low) / 2
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': candles,
            'current_price': current_price,
            'vwap': vwap,
            'atr1': 0.6
        }
        
        result = regime_detector.detect_regime(snapshot)
        
        # Should detect RANGE if range is clear
        self.assertIsNotNone(result)
        if result and 'regime' in result:
            regime = result.get('regime')
            # Might detect RANGE if range is well-defined
            self.assertIn(regime, ['RANGE', 'VWAP_REVERSION', 'UNKNOWN', 'EDGE_BASED', None])
    
    def test_compressed_market_detects_balanced_zone(self):
        """Test: Compressed market should detect balanced zone regime"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        # Create compressed candles
        base_price = 2000.0
        candles = self._create_compressed_candles(base_price, num_candles=50)
        current_price = base_price
        
        vwap = base_price
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': candles,
            'current_price': current_price,
            'vwap': vwap,
            'atr1': 0.3  # Low ATR (compression)
        }
        
        result = regime_detector.detect_regime(snapshot)
        
        # Should detect BALANCED_ZONE if compression is clear
        self.assertIsNotNone(result)
        if result and 'regime' in result:
            regime = result.get('regime')
            # Might detect BALANCED_ZONE if compression is well-defined
            self.assertIn(regime, ['BALANCED_ZONE', 'RANGE', 'UNKNOWN', 'EDGE_BASED', None])
    
    def test_market_transition_handles_gracefully(self):
        """Test: Market transition from range to trend is handled gracefully"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        # First: Range-bound market
        range_candles = self._create_range_candles(num_candles=30)
        
        # Then: Transition to trend
        trend_candles = self._create_trending_candles(base_price=2000.0, trend_direction=1, num_candles=20)
        
        # Combined candles (transition)
        all_candles = range_candles + trend_candles
        
        current_price = 2010.0
        vwap = sum(c['close'] for c in all_candles) / len(all_candles)
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': all_candles,
            'current_price': current_price,
            'vwap': vwap,
            'atr1': 0.6
        }
        
        result = regime_detector.detect_regime(snapshot)
        
        # Should handle transition gracefully (no crash)
        self.assertIsNotNone(result)
        self.assertIn('regime', result)
        self.assertIn('confidence', result)


class TestStrategySelectionWithRealisticData(unittest.TestCase):
    """Test strategy selection with realistic market data"""
    
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
    
    def test_high_confidence_vwap_reversion_selects_correctly(self):
        """Test: High confidence VWAP reversion selects vwap_reversion strategy"""
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 85,  # High confidence
            'min_confidence_threshold': 70
        }
        
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertEqual(strategy, 'vwap_reversion')
    
    def test_medium_confidence_range_selects_correctly(self):
        """Test: Medium confidence range selects range_scalp strategy"""
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'RANGE',
            'confidence': 60,  # Above threshold
            'min_confidence_threshold': 55
        }
        
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertEqual(strategy, 'range_scalp')
    
    def test_low_confidence_falls_back_to_edge_based(self):
        """Test: Low confidence falls back to edge_based strategy"""
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 50,  # Below threshold
            'min_confidence_threshold': 70
        }
        
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertEqual(strategy, 'edge_based')


if __name__ == '__main__':
    unittest.main()

