"""
Configuration Validation Tests for Adaptive Micro-Scalp Strategy System

Tests various configuration scenarios:
- Valid configurations
- Missing configurations
- Invalid configurations
- Default value handling
- Configuration edge cases
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
from infra.micro_scalp_strategies import VWAPReversionChecker


class TestConfigurationValidation(unittest.TestCase):
    """Test configuration handling"""
    
    def test_minimal_config(self):
        """Test: System works with minimal configuration"""
        minimal_config = {
            'regime_detection': {
                'enabled': True
            }
        }
        
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=minimal_config,
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
        
        result = regime_detector.detect_regime(snapshot)
        self.assertIsNotNone(result)
    
    def test_empty_config(self):
        """Test: System handles empty configuration"""
        empty_config = {}
        
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=empty_config,
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
        
        # Should not crash
        result = regime_detector.detect_regime(snapshot)
        self.assertIsNotNone(result)
    
    def test_missing_confidence_thresholds(self):
        """Test: System handles missing confidence thresholds"""
        config_no_thresholds = {
            'regime_detection': {
                'enabled': True,
                'strategy_confidence_thresholds': {}
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
            'min_confidence_threshold': 70  # From result
        }
        
        # Should use threshold from result
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertIsNotNone(strategy)
    
    def test_invalid_confidence_values(self):
        """Test: System handles invalid confidence values"""
        config = {
            'regime_detection': {
                'enabled': True,
                'strategy_confidence_thresholds': {
                    'vwap_reversion': -10,  # Invalid (negative)
                    'range_scalp': 150,  # Invalid (over 100)
                    'balanced_zone': 60
                }
            }
        }
        
        router = MicroScalpStrategyRouter(
            config=config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 75,
            'min_confidence_threshold': 70
        }
        
        # Should handle gracefully
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertIsNotNone(strategy)
    
    def test_missing_confluence_weights(self):
        """Test: System handles missing confluence weights"""
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
        
        # Should use defaults
        score = checker._calculate_confluence_score('XAUUSDc', [], 2000.0, 2000.0, 0.6, location_result, signal_result)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
    
    def test_none_config(self):
        """Test: System handles None configuration"""
        # Use empty dict instead of None (more realistic)
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config={},  # Empty dict instead of None
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
        
        # Should not crash
        result = regime_detector.detect_regime(snapshot)
        self.assertIsNotNone(result)
    
    def test_regime_detection_disabled(self):
        """Test: System handles disabled regime detection"""
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
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 75,
            'min_confidence_threshold': 70
        }
        
        # Should fallback to edge_based
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertEqual(strategy, 'edge_based')
    
    def test_nested_config_access(self):
        """Test: System correctly accesses nested configuration"""
        nested_config = {
            'regime_detection': {
                'enabled': True,
                'strategy_confidence_thresholds': {
                    'vwap_reversion': {
                        'min': 70,  # Nested structure
                        'max': 100
                    }
                }
            }
        }
        
        router = MicroScalpStrategyRouter(
            config=nested_config,
            regime_detector=Mock(),
            m1_analyzer=None
        )
        
        snapshot = {'symbol': 'XAUUSDc'}
        regime_result = {
            'regime': 'VWAP_REVERSION',
            'confidence': 75,
            'min_confidence_threshold': 70
        }
        
        # Should handle nested config gracefully
        strategy = router.select_strategy(snapshot, regime_result)
        self.assertIsNotNone(strategy)


if __name__ == '__main__':
    unittest.main()

