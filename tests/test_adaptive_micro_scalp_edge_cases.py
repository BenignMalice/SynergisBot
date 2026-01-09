"""
Edge Case and Error Handling Tests for Adaptive Micro-Scalp Strategy System

Tests edge cases, error scenarios, and boundary conditions:
- Missing data scenarios
- Invalid inputs
- Boundary conditions
- Error recovery
- Configuration edge cases
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.micro_scalp_engine import MicroScalpEngine
from infra.micro_scalp_strategies import (
    VWAPReversionChecker,
    RangeScalpChecker,
    BalancedZoneChecker,
    EdgeBasedChecker
)
from infra.micro_scalp_regime_detector import MicroScalpRegimeDetector
from infra.micro_scalp_strategy_router import MicroScalpStrategyRouter
from infra.micro_scalp_conditions import ConditionCheckResult
from infra.range_boundary_detector import RangeBoundaryDetector


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""
    
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
    
    def test_regime_detector_with_empty_snapshot(self):
        """Test regime detector handles empty snapshot"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        empty_snapshot = {}
        result = regime_detector.detect_regime(empty_snapshot)
        
        # Should return a result (even if low confidence)
        self.assertIsNotNone(result)
        self.assertIn('regime', result)
        self.assertIn('confidence', result)
    
    def test_regime_detector_with_insufficient_candles(self):
        """Test regime detector with insufficient candle data"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': [{'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000} for i in range(5)],  # Only 5 candles
            'current_price': 2000.0,
            'vwap': 2000.0
        }
        
        result = regime_detector.detect_regime(snapshot)
        # Should handle gracefully
        self.assertIsNotNone(result)
    
    def test_strategy_router_with_none_regime_detector(self):
        """Test router handles None regime detector gracefully"""
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=None,
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {'regime': 'VWAP_REVERSION', 'confidence': 75}
        
        # Should not crash
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertIsNotNone(strategy)
    
    def test_strategy_checker_with_missing_snapshot_fields(self):
        """Test strategy checker handles missing snapshot fields"""
        checker = EdgeBasedChecker(
            config=self.config,
            volatility_filter=Mock(),
            vwap_filter=Mock(),
            sweep_detector=Mock(),
            ob_detector=Mock(),
            spread_tracker=Mock(),
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='edge_based'
        )
        
        # Snapshot missing required fields
        incomplete_snapshot = {
            'symbol': 'XAUUSDc'
            # Missing candles, current_price, vwap, etc.
        }
        
        # Should handle gracefully
        result = checker.validate(incomplete_snapshot)
        self.assertIsNotNone(result)
        self.assertFalse(result.passed)  # Should fail validation
    
    def test_strategy_checker_with_zero_vwap(self):
        """Test strategy checker handles zero VWAP"""
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
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': [{'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000} for i in range(20)],
            'current_price': 2000.0,
            'vwap': 0.0,  # Zero VWAP
            'atr1': 0.6
        }
        
        # Should handle gracefully
        result = checker._check_location_filter('XAUUSDc', snapshot['candles'], 2000.0, 0.0, 0.6)
        self.assertIsNotNone(result)
        self.assertFalse(result.get('passed', True))  # Should fail with zero VWAP
    
    def test_range_scalp_checker_without_range_structure(self):
        """Test range scalp checker handles missing range structure"""
        checker = RangeScalpChecker(
            config=self.config,
            volatility_filter=Mock(),
            vwap_filter=Mock(),
            sweep_detector=Mock(),
            ob_detector=Mock(),
            spread_tracker=Mock(),
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='range_scalp'
        )
        
        # Set empty snapshot (no range_structure)
        checker._current_snapshot = {
            'symbol': 'XAUUSDc',
            'candles': [{'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000} for i in range(20)],
            'current_price': 2000.0,
            'vwap': 2000.0,
            'atr1': 0.6
        }
        
        result = checker._check_location_filter('XAUUSDc', checker._current_snapshot['candles'], 2000.0, 2000.0, 0.6)
        # Should handle missing range structure
        self.assertIsNotNone(result)
    
    def test_balanced_zone_checker_with_insufficient_candles(self):
        """Test balanced zone checker with insufficient candles"""
        checker = BalancedZoneChecker(
            config=self.config,
            volatility_filter=Mock(),
            vwap_filter=Mock(),
            sweep_detector=Mock(),
            ob_detector=Mock(),
            spread_tracker=Mock(),
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='balanced_zone'
        )
        
        # Only 5 candles (need 20+ for some checks)
        candles = [{'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000} for i in range(5)]
        
        result = checker._check_location_filter('XAUUSDc', candles, 2000.0, 2000.0, 0.6)
        # Should handle gracefully
        self.assertIsNotNone(result)
    
    def test_confluence_scoring_with_missing_weights(self):
        """Test confluence scoring handles missing config weights"""
        config_no_weights = {
            'xauusd_rules': {
                'confluence_scoring': {
                    'min_score_for_trade': 5,
                    'min_score_for_aplus': 7
                }
            },
            'regime_detection': {
                'enabled': True,
                'confluence_weights': {}  # Empty weights
            }
        }
        
        checker = VWAPReversionChecker(
            config=config_no_weights,
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
        
        location_result = {'deviation_sigma': 2.5, 'vwap_slope_ok': True}
        signal_result = {'primary_triggers': ['CHOCH_AT_EXTREME'], 'secondary_confluence': ['VOLUME_CONFIRMED']}
        
        # Should handle missing weights gracefully (use defaults)
        score = checker._calculate_confluence_score('XAUUSDc', [], 2000.0, 2000.0, 0.6, location_result, signal_result)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)


class TestDataFlow(unittest.TestCase):
    """Test data flow through the system"""
    
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
    
    def test_snapshot_data_extraction(self):
        """Test that regime-specific data is extracted to snapshot"""
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
        
        regime_result = regime_detector.detect_regime(snapshot)
        
        # Verify regime result has expected structure
        self.assertIn('regime', regime_result)
        self.assertIn('confidence', regime_result)
        self.assertIn('characteristics', regime_result)
    
    def test_strategy_checker_accesses_range_structure(self):
        """Test that range scalp checker can access range_structure from snapshot"""
        checker = RangeScalpChecker(
            config=self.config,
            volatility_filter=Mock(),
            vwap_filter=Mock(),
            sweep_detector=Mock(),
            ob_detector=Mock(),
            spread_tracker=Mock(),
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='range_scalp'
        )
        
        # Create snapshot with range_structure
        from infra.range_boundary_detector import RangeStructure, CriticalGapZones
        # Use actual RangeStructure dataclass
        range_structure = RangeStructure(
            range_type='dynamic',
            range_high=2000.5,
            range_low=1999.5,
            range_mid=2000.0,
            range_width_atr=1.0,  # Note: range_width_atr, not range_width
            critical_gaps=CriticalGapZones(
                upper_zone_start=2000.3,
                upper_zone_end=2000.5,
                lower_zone_start=1999.5,
                lower_zone_end=1999.7
            ),
            touch_count={},
            validated=True
        )
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': [{'time': i, 'open': 2000.0, 'high': 2000.5, 'low': 1999.5, 'close': 2000.0, 'volume': 1000} for i in range(20)],
            'current_price': 2000.0,
            'vwap': 2000.0,
            'atr1': 0.6,
            'range_structure': range_structure
        }
        
        # Set snapshot for checker
        checker._current_snapshot = snapshot
        
        # Should be able to access range_structure
        result = checker._check_location_filter('XAUUSDc', snapshot['candles'], 2000.0, 2000.0, 0.6)
        self.assertIsNotNone(result)


class TestConfigurationEdgeCases(unittest.TestCase):
    """Test configuration edge cases"""
    
    def test_regime_detection_disabled(self):
        """Test system behavior when regime detection is disabled"""
        config_disabled = {
            'regime_detection': {
                'enabled': False
            }
        }
        
        router = MicroScalpStrategyRouter(
            config=config_disabled,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {'regime': 'VWAP_REVERSION', 'confidence': 75}
        
        strategy = router.select_strategy(snapshot, regime_result)
        # Should fallback to edge_based when disabled
        self.assertEqual(strategy, 'edge_based')
    
    def test_missing_confidence_thresholds(self):
        """Test system handles missing confidence thresholds"""
        config_no_thresholds = {
            'regime_detection': {
                'enabled': True,
                'strategy_confidence_thresholds': {}  # Empty
            }
        }
        
        router = MicroScalpStrategyRouter(
            config=config_no_thresholds,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 75,
            'min_confidence_threshold': 60  # From result
        }
        
        # Should use threshold from result
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertIsNotNone(strategy)


class TestBoundaryConditions(unittest.TestCase):
    """Test boundary conditions"""
    
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
    
    def test_confidence_at_threshold_boundary(self):
        """Test router behavior at confidence threshold boundary"""
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        
        # Exactly at threshold
        regime_result_at_threshold = {
            'regime': 'VWAP_REVERSION',
            'confidence': 70,  # Exactly at threshold
            'min_confidence_threshold': 70
        }
        strategy = router.select_strategy(snapshot, regime_result_at_threshold)
        self.assertEqual(strategy, 'vwap_reversion')
        
        # Just below threshold
        regime_result_below = {
            'regime': 'VWAP_REVERSION',
            'confidence': 69,  # Just below
            'min_confidence_threshold': 70
        }
        strategy = router.select_strategy(snapshot, regime_result_below)
        self.assertEqual(strategy, 'edge_based')  # Should fallback
    
    def test_zero_confidence(self):
        """Test system handles zero confidence"""
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 0,  # Zero confidence
            'min_confidence_threshold': 70
        }
        
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertEqual(strategy, 'edge_based')
    
    def test_very_high_confidence(self):
        """Test system handles very high confidence"""
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 100,  # Maximum confidence
            'min_confidence_threshold': 70
        }
        
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertEqual(strategy, 'vwap_reversion')


class TestErrorRecovery(unittest.TestCase):
    """Test error recovery mechanisms"""
    
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
    
    def test_regime_detector_error_recovery(self):
        """Test regime detector recovers from errors"""
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        # Invalid snapshot that might cause errors
        invalid_snapshot = {
            'symbol': 'XAUUSDc',
            'candles': [],  # Empty list instead of None (more realistic)
            'current_price': None,
            'vwap': None
        }
        
        # Should not crash
        result = regime_detector.detect_regime(invalid_snapshot)
        self.assertIsNotNone(result)
    
    @patch('builtins.open', create=True)
    def test_engine_handles_missing_config(self, mock_open):
        """Test engine handles missing config file"""
        import json
        mock_open.side_effect = FileNotFoundError("Config not found")
        
        engine = MicroScalpEngine(
            config_path="nonexistent_config.json",
            mt5_service=Mock(),
            m1_fetcher=Mock(),
            streamer=None,
            m1_analyzer=None,
            session_manager=None,
            news_service=None
        )
        
        # Should use empty config, not crash
        self.assertIsNotNone(engine.config)
        self.assertEqual(engine.config, {})


if __name__ == '__main__':
    unittest.main()

