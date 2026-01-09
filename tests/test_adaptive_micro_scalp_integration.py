"""
Integration tests for Adaptive Micro-Scalp Strategy System

Tests the full integration flow:
- MicroScalpEngine with adaptive system
- Regime detection → Strategy routing → Validation → Trade idea generation
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
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
from infra.micro_scalp_conditions import ConditionCheckResult


class TestAdaptiveMicroScalpIntegration(unittest.TestCase):
    """Integration tests for adaptive micro-scalp system"""
    
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
                    },
                    'edge_based': {
                        'location_edge_count': 1.0,
                        'primary_triggers': 1.0,
                        'secondary_confluence': 1.0
                    }
                }
            }
        }
        
        # Create mocks
        self.mt5_service = Mock()
        self.m1_fetcher = Mock()
        self.streamer = Mock()
        self.m1_analyzer = Mock()
        self.session_manager = Mock()
        self.news_service = Mock()
    
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
    
    @patch('infra.micro_scalp_engine.MicroScalpEngine._build_snapshot')
    @patch('builtins.open', create=True)
    def test_engine_uses_adaptive_system(self, mock_open, mock_build_snapshot):
        """Test that engine uses adaptive regime detection and routing"""
        import json
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(self.config)
        
        # Create engine
        engine = MicroScalpEngine(
            config_path="config/micro_scalp_config.json",
            mt5_service=self.mt5_service,
            m1_fetcher=self.m1_fetcher,
            streamer=self.streamer,
            m1_analyzer=self.m1_analyzer,
            session_manager=self.session_manager,
            news_service=self.news_service
        )
        
        # Mock snapshot
        mock_build_snapshot.return_value = {
            'symbol': 'XAUUSDc',
            'candles': [self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0) for i in range(20)],
            'current_price': 2000.0,
            'vwap': 2000.0,
            'atr1': 0.6,
            'atr14': 0.7,
            'vwap_std': 0.3,
            'spread_data': Mock(),
            'm5_candles': [],
            'm15_candles': []
        }
        
        # Verify adaptive components are initialized
        self.assertIsNotNone(engine.regime_detector)
        self.assertIsNotNone(engine.strategy_router)
        self.assertIsInstance(engine.strategy_checkers, dict)
    
    @patch('infra.micro_scalp_engine.MicroScalpEngine._build_snapshot')
    @patch('builtins.open', create=True)
    def test_engine_fallback_to_edge_based(self, mock_open, mock_build_snapshot):
        """Test engine falls back to edge-based when regime detection fails"""
        import json
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(self.config)
        
        engine = MicroScalpEngine(
            config_path="config/micro_scalp_config.json",
            mt5_service=self.mt5_service,
            m1_fetcher=self.m1_fetcher,
            streamer=self.streamer,
            m1_analyzer=self.m1_analyzer,
            session_manager=self.session_manager,
            news_service=self.news_service
        )
        
        # Mock snapshot
        mock_build_snapshot.return_value = {
            'symbol': 'XAUUSDc',
            'candles': [self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0) for i in range(20)],
            'current_price': 2000.0,
            'vwap': 2000.0,
            'atr1': 0.6,
            'atr14': 0.7,
            'vwap_std': 0.3,
            'spread_data': Mock(),
            'm5_candles': [],
            'm15_candles': []
        }
        
        # Mock regime detector to return low confidence
        engine.regime_detector.detect_regime = Mock(return_value={
            'regime': 'VWAP_REVERSION',
            'confidence': 50,  # Below threshold
            'min_confidence_threshold': 70
        })
        
        # Mock strategy router to return edge_based
        engine.strategy_router.select_strategy = Mock(return_value='edge_based')
        
        # Mock checker validate to return passed
        mock_checker = Mock()
        mock_checker.validate.return_value = ConditionCheckResult(
            passed=True,
            pre_trade_passed=True,
            location_passed=True,
            primary_triggers=1,
            secondary_confluence=1,
            confluence_score=6.0,
            is_aplus_setup=False,
            reasons=[],
            details={}
        )
        mock_checker.generate_trade_idea.return_value = {
            'symbol': 'XAUUSDc',
            'direction': 'BUY',
            'entry_price': 2000.0,
            'sl': 1999.0,
            'tp': 2001.0,
            'volume': 0.01
        }
        engine.strategy_checkers['edge_based'] = mock_checker
        
        # Call check_micro_conditions
        result = engine.check_micro_conditions('XAUUSDc')
        
        # Verify fallback was used
        self.assertEqual(result.get('strategy'), 'edge_based')
        engine.strategy_router.select_strategy.assert_called_once()
    
    @patch('builtins.open', create=True)
    def test_strategy_checker_factory(self, mock_open):
        """Test _get_strategy_checker factory method"""
        import json
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(self.config)
        
        engine = MicroScalpEngine(
            config_path="config/micro_scalp_config.json",
            mt5_service=self.mt5_service,
            m1_fetcher=self.m1_fetcher,
            streamer=self.streamer,
            m1_analyzer=self.m1_analyzer,
            session_manager=self.session_manager,
            news_service=self.news_service
        )
        
        # Test getting each strategy checker
        vwap_checker = engine._get_strategy_checker('vwap_reversion')
        self.assertIsInstance(vwap_checker, VWAPReversionChecker)
        
        range_checker = engine._get_strategy_checker('range_scalp')
        self.assertIsInstance(range_checker, RangeScalpChecker)
        
        balanced_checker = engine._get_strategy_checker('balanced_zone')
        self.assertIsInstance(balanced_checker, BalancedZoneChecker)
        
        edge_checker = engine._get_strategy_checker('edge_based')
        self.assertIsInstance(edge_checker, EdgeBasedChecker)
        
        # Test caching
        vwap_checker2 = engine._get_strategy_checker('vwap_reversion')
        self.assertIs(vwap_checker, vwap_checker2)  # Same instance
    
    @patch('builtins.open', create=True)
    @patch('infra.micro_scalp_strategies.vwap_reversion_checker.VWAPReversionChecker')
    def test_strategy_checker_fallback_on_error(self, mock_vwap_checker, mock_open):
        """Test factory falls back to edge-based on error"""
        import json
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(self.config)
        
        engine = MicroScalpEngine(
            config_path="config/micro_scalp_config.json",
            mt5_service=self.mt5_service,
            m1_fetcher=self.m1_fetcher,
            streamer=self.streamer,
            m1_analyzer=self.m1_analyzer,
            session_manager=self.session_manager,
            news_service=self.news_service
        )
        
        # Test fallback when import fails
        mock_vwap_checker.side_effect = ImportError("Test error")
        
        # Should fall back to edge_based
        checker = engine._get_strategy_checker('vwap_reversion')
        self.assertIsInstance(checker, EdgeBasedChecker)


class TestRegimeDetectionIntegration(unittest.TestCase):
    """Test regime detection integration with engine"""
    
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
    
    def test_regime_detector_initializes_with_all_dependencies(self):
        """Test regime detector can be initialized with all dependencies"""
        from infra.micro_scalp_regime_detector import MicroScalpRegimeDetector
        from infra.range_boundary_detector import RangeBoundaryDetector
        
        range_detector = RangeBoundaryDetector({})
        volatility_filter = Mock()
        m1_analyzer = Mock()
        vwap_filter = Mock()
        streamer = Mock()
        news_service = Mock()
        mt5_service = Mock()
        
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=volatility_filter,
            m1_analyzer=m1_analyzer,
            vwap_filter=vwap_filter,
            streamer=streamer,
            news_service=news_service,
            mt5_service=mt5_service
        )
        
        self.assertIsNotNone(regime_detector)
        self.assertEqual(regime_detector.config, self.config)
        self.assertEqual(regime_detector.range_detector, range_detector)
        self.assertEqual(regime_detector.volatility_filter, volatility_filter)
        self.assertEqual(regime_detector.m1_analyzer, m1_analyzer)
        self.assertEqual(regime_detector.vwap_filter, vwap_filter)
        self.assertEqual(regime_detector.streamer, streamer)
        self.assertEqual(regime_detector.news_service, news_service)
        self.assertEqual(regime_detector.mt5_service, mt5_service)


class TestStrategyRouterIntegration(unittest.TestCase):
    """Test strategy router integration"""
    
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
    
    def test_router_integrates_with_regime_detector(self):
        """Test router integrates with regime detector"""
        from infra.micro_scalp_strategy_router import MicroScalpStrategyRouter
        from infra.micro_scalp_regime_detector import MicroScalpRegimeDetector
        from infra.range_boundary_detector import RangeBoundaryDetector
        
        range_detector = RangeBoundaryDetector({})
        regime_detector = MicroScalpRegimeDetector(
            config=self.config,
            range_detector=range_detector,
            volatility_filter=None,
            m1_analyzer=None
        )
        
        router = MicroScalpStrategyRouter(
            config=self.config,
            regime_detector=regime_detector,
            m1_analyzer=None
        )
        
        self.assertIsNotNone(router)
        self.assertEqual(router.regime_detector, regime_detector)


if __name__ == '__main__':
    unittest.main()

