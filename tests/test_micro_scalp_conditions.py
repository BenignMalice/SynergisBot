"""
Tests for Micro-Scalp Conditions Checker
"""

import unittest
from unittest.mock import Mock, MagicMock
from datetime import datetime
from infra.micro_scalp_conditions import MicroScalpConditionsChecker, ConditionCheckResult
from infra.micro_scalp_volatility_filter import MicroScalpVolatilityFilter, VolatilityFilterResult
from infra.vwap_micro_filter import VWAPMicroFilter, VWAPProximityResult
from infra.micro_liquidity_sweep_detector import MicroLiquiditySweepDetector, MicroSweepResult
from infra.micro_order_block_detector import MicroOrderBlockDetector
from infra.spread_tracker import SpreadTracker, SpreadData


class TestMicroScalpConditionsChecker(unittest.TestCase):
    """Test MicroScalpConditionsChecker functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Minimal config
        self.config = {
            'xauusd_rules': {
                'pre_trade_filters': {
                    'volatility': {'atr1_min': 0.5, 'm1_range_avg_min': 0.8},
                    'spread': {'max_spread': 0.25}
                },
                'location_filter': {
                    'vwap_band_enabled': True,
                    'prior_session_high_low_enabled': False,
                    'intraday_range_high_low_enabled': True,
                    'clean_ob_zone_enabled': True,
                    'liquidity_cluster_enabled': False
                },
                'candle_signals': {
                    'primary_triggers': {
                        'long_wick_trap_enabled': True,
                        'micro_liquidity_sweep_enabled': True,
                        'vwap_tap_rejection_enabled': True,
                        'strong_engulfing_enabled': True
                    },
                    'secondary_confluence': {
                        'ob_retest_enabled': True,
                        'fresh_micro_choch_enabled': False,
                        'strong_session_momentum_enabled': False,
                        'increasing_volume_enabled': True
                    }
                },
                'confluence_scoring': {
                    'wick_quality_points': 2,
                    'vwap_proximity_points': 2,
                    'edge_location_points': 2,
                    'volatility_state_points': 1,
                    'session_quality_points': 1,
                    'min_score_for_trade': 5,
                    'min_score_for_aplus': 7
                }
            }
        }
        
        # Create mocks
        self.volatility_filter = Mock(spec=MicroScalpVolatilityFilter)
        self.vwap_filter = Mock(spec=VWAPMicroFilter)
        self.sweep_detector = Mock(spec=MicroLiquiditySweepDetector)
        self.ob_detector = Mock(spec=MicroOrderBlockDetector)
        self.spread_tracker = Mock(spec=SpreadTracker)
        
        # Initialize checker
        self.checker = MicroScalpConditionsChecker(
            config=self.config,
            volatility_filter=self.volatility_filter,
            vwap_filter=self.vwap_filter,
            sweep_detector=self.sweep_detector,
            ob_detector=self.ob_detector,
            spread_tracker=self.spread_tracker,
            m1_analyzer=None,
            session_manager=None
        )
    
    def _create_candle(self, time, open, high, low, close, volume=1000):
        """Helper to create candle dict"""
        return {
            'time': time,
            'open': open,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }
    
    def test_pre_trade_filters_fail(self):
        """Test when pre-trade filters fail"""
        candles = [self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0) for i in range(10)]
        
        # Mock pre-trade filter failure
        self.volatility_filter.check_volatility_filters.return_value = VolatilityFilterResult(
            passed=False,
            atr1_value=0.3,
            atr1_passed=False,
            m1_range_avg=0.6,
            m1_range_passed=False,
            spread_passed=True,
            reasons=["ATR(1) too low", "M1 range too small"]
        )
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': candles,
            'current_price': 2000.0,
            'vwap': 2000.0,
            'atr1': 0.3,
            'spread_data': SpreadData(0.1, 0.1, 0.01, 1.0, 10)
        }
        
        result = self.checker.validate(snapshot)
        self.assertFalse(result.passed)
        self.assertFalse(result.pre_trade_passed)
    
    def test_location_filter_fail(self):
        """Test when location filter fails"""
        candles = [self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0) for i in range(10)]
        
        # Mock pre-trade filter pass
        self.volatility_filter.check_volatility_filters.return_value = VolatilityFilterResult(
            passed=True,
            atr1_value=0.6,
            atr1_passed=True,
            m1_range_avg=0.9,
            m1_range_passed=True,
            spread_passed=True,
            reasons=["All passed"]
        )
        
        # Mock VWAP filter - not in band
        self.vwap_filter.is_price_near_vwap.return_value = VWAPProximityResult(
            is_near_vwap=False,
            in_band=False,
            distance_pct=0.002,
            distance_points=4.0,
            is_above_vwap=True,
            is_below_vwap=False,
            band_lower=1999.9,
            band_upper=2000.1
        )
        
        # Mock OB detector - no OBs
        self.ob_detector.detect_micro_obs.return_value = []
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': candles,
            'current_price': 2000.0,
            'vwap': 2000.0,
            'atr1': 0.6,
            'spread_data': SpreadData(0.1, 0.1, 0.01, 1.0, 10)
        }
        
        result = self.checker.validate(snapshot)
        self.assertFalse(result.passed)
        self.assertTrue(result.pre_trade_passed)
        self.assertFalse(result.location_passed)
    
    def test_insufficient_signals(self):
        """Test when signals are insufficient"""
        candles = [self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0) for i in range(10)]
        
        # Mock all filters pass
        self.volatility_filter.check_volatility_filters.return_value = VolatilityFilterResult(
            passed=True, atr1_value=0.6, atr1_passed=True, m1_range_avg=0.9,
            m1_range_passed=True, spread_passed=True, reasons=["All passed"]
        )
        
        self.vwap_filter.is_price_near_vwap.return_value = VWAPProximityResult(
            is_near_vwap=True, in_band=True, distance_pct=0.0003,
            distance_points=0.6, is_above_vwap=False, is_below_vwap=False,
            band_lower=1999.9, band_upper=2000.1
        )
        
        self.ob_detector.detect_micro_obs.return_value = []
        
        # Mock sweep detector - no sweep
        self.sweep_detector.detect_micro_sweep.return_value = MicroSweepResult(
            sweep_detected=False, direction=None, sweep_level=0.0,
            sweep_candle_index=-1, return_confirmed=False, confidence=0.0,
            wick_rejection=False, volume_spike=False
        )
        
        snapshot = {
            'symbol': 'XAUUSDc',
            'candles': candles,
            'current_price': 2000.0,
            'vwap': 2000.0,
            'atr1': 0.6,
            'spread_data': SpreadData(0.1, 0.1, 0.01, 1.0, 10)
        }
        
        result = self.checker.validate(snapshot)
        self.assertFalse(result.passed)
        self.assertTrue(result.pre_trade_passed)
        self.assertTrue(result.location_passed)
        self.assertEqual(result.primary_triggers, 0)  # No primary triggers


if __name__ == '__main__':
    unittest.main()

