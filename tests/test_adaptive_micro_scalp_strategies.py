"""
Unit tests for Adaptive Micro-Scalp Strategy System

Tests the new adaptive components:
- BaseStrategyChecker
- Strategy-specific checkers (VWAP Reversion, Range Scalp, Balanced Zone, Edge-Based)
- MicroScalpRegimeDetector
- MicroScalpStrategyRouter
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.micro_scalp_strategies import (
    BaseStrategyChecker,
    VWAPReversionChecker,
    RangeScalpChecker,
    BalancedZoneChecker,
    EdgeBasedChecker
)
from infra.micro_scalp_regime_detector import MicroScalpRegimeDetector
from infra.micro_scalp_strategy_router import MicroScalpStrategyRouter
from infra.micro_scalp_conditions import ConditionCheckResult
from infra.micro_scalp_volatility_filter import MicroScalpVolatilityFilter
from infra.vwap_micro_filter import VWAPMicroFilter
from infra.micro_liquidity_sweep_detector import MicroLiquiditySweepDetector
from infra.micro_order_block_detector import MicroOrderBlockDetector
from infra.spread_tracker import SpreadTracker
from infra.range_boundary_detector import RangeBoundaryDetector


class TestBaseStrategyChecker(unittest.TestCase):
    """Test BaseStrategyChecker functionality"""
    
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
                'confluence_weights': {
                    'edge_based': {
                        'location_edge_count': 1.0,
                        'primary_triggers': 1.0,
                        'secondary_confluence': 1.0
                    }
                }
            }
        }
        
        # Create mocks
        self.volatility_filter = Mock(spec=MicroScalpVolatilityFilter)
        self.vwap_filter = Mock(spec=VWAPMicroFilter)
        self.sweep_detector = Mock(spec=MicroLiquiditySweepDetector)
        self.ob_detector = Mock(spec=MicroOrderBlockDetector)
        self.spread_tracker = Mock(spec=SpreadTracker)
        
        # Create a concrete checker (EdgeBasedChecker) for testing
        self.checker = EdgeBasedChecker(
            config=self.config,
            volatility_filter=self.volatility_filter,
            vwap_filter=self.vwap_filter,
            sweep_detector=self.sweep_detector,
            ob_detector=self.ob_detector,
            spread_tracker=self.spread_tracker,
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='edge_based'
        )
    
    def _create_candle(self, time, open_price, high, low, close, volume=1000):
        """Helper to create candle dict"""
        return {
            'time': time,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }
    
    def test_helper_methods_exist(self):
        """Test that helper methods are accessible"""
        candles = [self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0) for i in range(20)]
        
        # Test _calculate_vwap_std
        vwap_std = self.checker._calculate_vwap_std(candles, 2000.0)
        self.assertIsInstance(vwap_std, float)
        self.assertGreaterEqual(vwap_std, 0.0)
        
        # Test _calculate_vwap_slope
        vwap_slope = self.checker._calculate_vwap_slope(candles, 2000.0)
        self.assertIsInstance(vwap_slope, float)
        
        # Test _check_volume_spike
        volume_spike = self.checker._check_volume_spike(candles)
        self.assertIsInstance(volume_spike, bool)
        
        # Test _check_bb_compression
        bb_compression = self.checker._check_bb_compression(candles)
        self.assertIsInstance(bb_compression, bool)
    
    def test_detect_entry_type_from_candles(self):
        """Test entry type detection"""
        # Test fade (inside bars)
        candles_fade = [
            self._create_candle(1, 2000.0, 2000.5, 1999.5, 2000.0),
            self._create_candle(2, 2000.0, 2000.4, 1999.6, 2000.0),
            self._create_candle(3, 2000.0, 2000.3, 1999.7, 2000.0)  # Inside previous
        ]
        entry_type = self.checker._detect_entry_type_from_candles(candles_fade)
        self.assertEqual(entry_type, 'fade')
        
        # Test breakout (close breaks above compression high)
        candles_breakout = [
            self._create_candle(1, 2000.0, 2000.5, 1999.5, 2000.0),
            self._create_candle(2, 2000.0, 2000.4, 1999.6, 2000.0),
            self._create_candle(3, 2000.0, 2000.5, 1999.5, 2000.6)  # Close (2000.6) > compression high (2000.5)
        ]
        entry_type = self.checker._detect_entry_type_from_candles(candles_breakout)
        self.assertEqual(entry_type, 'breakout')


class TestStrategyCheckers(unittest.TestCase):
    """Test strategy-specific checkers"""
    
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
                'confluence_weights': {
                    'vwap_reversion': {
                        'deviation_strength': 1.0,
                        'choch_quality': 1.0,
                        'volume_confirmation': 1.0
                    },
                    'range_scalp': {
                        'edge_proximity': 1.0,
                        'sweep_quality': 1.0,
                        'range_respect': 1.0
                    },
                    'balanced_zone': {
                        'compression_quality': 1.0,
                        'equal_highs_lows': 1.0,
                        'vwap_alignment': 1.0
                    }
                }
            }
        }
        
        # Create mocks
        self.volatility_filter = Mock(spec=MicroScalpVolatilityFilter)
        self.vwap_filter = Mock(spec=VWAPMicroFilter)
        self.sweep_detector = Mock(spec=MicroLiquiditySweepDetector)
        self.ob_detector = Mock(spec=MicroOrderBlockDetector)
        self.spread_tracker = Mock(spec=SpreadTracker)
    
    def test_vwap_reversion_checker_initialization(self):
        """Test VWAPReversionChecker can be initialized"""
        checker = VWAPReversionChecker(
            config=self.config,
            volatility_filter=self.volatility_filter,
            vwap_filter=self.vwap_filter,
            sweep_detector=self.sweep_detector,
            ob_detector=self.ob_detector,
            spread_tracker=self.spread_tracker,
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='vwap_reversion'
        )
        self.assertIsInstance(checker, VWAPReversionChecker)
        self.assertEqual(checker.strategy_name, 'vwap_reversion')
    
    def test_range_scalp_checker_initialization(self):
        """Test RangeScalpChecker can be initialized"""
        checker = RangeScalpChecker(
            config=self.config,
            volatility_filter=self.volatility_filter,
            vwap_filter=self.vwap_filter,
            sweep_detector=self.sweep_detector,
            ob_detector=self.ob_detector,
            spread_tracker=self.spread_tracker,
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='range_scalp'
        )
        self.assertIsInstance(checker, RangeScalpChecker)
        self.assertEqual(checker.strategy_name, 'range_scalp')
    
    def test_balanced_zone_checker_initialization(self):
        """Test BalancedZoneChecker can be initialized"""
        checker = BalancedZoneChecker(
            config=self.config,
            volatility_filter=self.volatility_filter,
            vwap_filter=self.vwap_filter,
            sweep_detector=self.sweep_detector,
            ob_detector=self.ob_detector,
            spread_tracker=self.spread_tracker,
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='balanced_zone'
        )
        self.assertIsInstance(checker, BalancedZoneChecker)
        self.assertEqual(checker.strategy_name, 'balanced_zone')
    
    def test_edge_based_checker_initialization(self):
        """Test EdgeBasedChecker can be initialized"""
        checker = EdgeBasedChecker(
            config=self.config,
            volatility_filter=self.volatility_filter,
            vwap_filter=self.vwap_filter,
            sweep_detector=self.sweep_detector,
            ob_detector=self.ob_detector,
            spread_tracker=self.spread_tracker,
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='edge_based'
        )
        self.assertIsInstance(checker, EdgeBasedChecker)
        self.assertEqual(checker.strategy_name, 'edge_based')


class TestRegimeDetector(unittest.TestCase):
    """Test MicroScalpRegimeDetector"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'regime_detection': {
                'enabled': True,
                'strategy_confidence_thresholds': {
                    'vwap_reversion': 70,
                    'range_scalp': 55,
                    'balanced_zone': 60
                },
                'confidence_diff_threshold': 10
            }
        }
        
        # Create mocks
        self.range_detector = Mock(spec=RangeBoundaryDetector)
        self.volatility_filter = Mock(spec=MicroScalpVolatilityFilter)
        self.m1_analyzer = Mock()
        
        self.regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=self.range_detector,
            volatility_filter=self.volatility_filter,
            m1_analyzer=self.m1_analyzer,
            vwap_filter=None,
            streamer=None,
            news_service=None,
            mt5_service=None
        )
    
    def test_regime_detector_initialization(self):
        """Test regime detector can be initialized"""
        self.assertIsNotNone(self.regime_detector)
        self.assertEqual(self.regime_detector.config, self.config)
    
    def test_regime_detector_has_helper_methods(self):
        """Test that helper methods exist"""
        candles = [
            {'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000}
            for i in range(20)
        ]
        
        # Test helper methods exist
        self.assertTrue(hasattr(self.regime_detector, '_calculate_vwap_std'))
        self.assertTrue(hasattr(self.regime_detector, '_check_volume_spike'))
        self.assertTrue(hasattr(self.regime_detector, '_check_bb_compression'))
        
        # Test they can be called
        vwap_std = self.regime_detector._calculate_vwap_std(candles, 2000.0)
        self.assertIsInstance(vwap_std, float)


class TestStrategyRouter(unittest.TestCase):
    """Test MicroScalpStrategyRouter"""
    
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
        
        # Create mock regime detector
        self.regime_detector = Mock(spec=MicroScalpRegimeDetector)
        self.m1_analyzer = Mock()
        
        self.router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=self.regime_detector,
            m1_analyzer=self.m1_analyzer
        )
    
    def test_router_initialization(self):
        """Test router can be initialized"""
        self.assertIsNotNone(self.router)
        self.assertEqual(self.router.config, self.config)
    
    def test_router_selects_vwap_reversion(self):
        """Test router selects VWAP reversion strategy"""
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 75,
            'min_confidence_threshold': 70
        }
        
        strategy = self.router.select_strategy(snapshot, regime_result)
        self.assertEqual(strategy, 'vwap_reversion')
    
    def test_router_selects_range_scalp(self):
        """Test router selects range scalp strategy"""
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'RANGE',
            'confidence': 60,
            'min_confidence_threshold': 55
        }
        
        strategy = self.router.select_strategy(snapshot, regime_result)
        self.assertEqual(strategy, 'range_scalp')
    
    def test_router_fallback_to_edge_based(self):
        """Test router falls back to edge-based when confidence is low"""
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 50,  # Below threshold
            'min_confidence_threshold': 70
        }
        
        strategy = self.router.select_strategy(snapshot, regime_result)
        self.assertEqual(strategy, 'edge_based')
    
    def test_router_fallback_when_regime_detection_disabled(self):
        """Test router falls back when regime detection is disabled"""
        self.config['regime_detection']['enabled'] = False
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=self.regime_detector,
            m1_analyzer=self.m1_analyzer
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 75,
            'min_confidence_threshold': 70
        }
        
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertEqual(strategy, 'edge_based')


if __name__ == '__main__':
    unittest.main()

