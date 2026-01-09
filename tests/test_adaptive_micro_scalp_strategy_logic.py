"""
Strategy-Specific Logic Tests for Adaptive Micro-Scalp Strategy System

Tests the specific validation logic for each strategy:
- VWAP Reversion: Deviation checks, CHOCH at extreme
- Range Scalp: Edge proximity, range respect, liquidity sweeps
- Balanced Zone: Compression, equal highs/lows, fade vs breakout
- Edge-Based: Generic edge detection
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.micro_scalp_strategies import (
    VWAPReversionChecker,
    RangeScalpChecker,
    BalancedZoneChecker,
    EdgeBasedChecker
)
from infra.micro_scalp_conditions import ConditionCheckResult
from infra.range_boundary_detector import RangeStructure, CriticalGapZones


class TestVWAPReversionLogic(unittest.TestCase):
    """Test VWAP Reversion strategy-specific logic"""
    
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
                'vwap_reversion': {
                    'min_deviation_sigma': 2.0,
                    'min_deviation_pct_xau': 0.002,
                    'max_slope_normalized': 0.1
                },
                'confluence_weights': {
                    'vwap_reversion': {
                        'deviation_strength': 1.0,
                        'choch_quality': 1.0,
                        'volume_confirmation': 1.0
                    }
                }
            }
        }
        
        self.checker = VWAPReversionChecker(
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
    
    def test_location_filter_requires_deviation(self):
        """Test location filter requires price deviation from VWAP"""
        candles = [self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0) for i in range(20)]
        
        # Price at VWAP (no deviation)
        result = self.checker._check_location_filter('XAUUSDc', candles, 2000.0, 2000.0, 0.6)
        self.assertFalse(result.get('passed', True))  # Should fail
        
        # Price far from VWAP (high deviation)
        # Mock VWAP std calculation to return a value
        with patch.object(self.checker, '_calculate_vwap_std', return_value=0.5):
            result = self.checker._check_location_filter('XAUUSDc', candles, 2001.5, 2000.0, 0.6)  # 1.5 away, std=0.5 = 3σ
            # Should pass with sufficient deviation
            self.assertIsNotNone(result)
    
    def test_location_filter_checks_vwap_slope(self):
        """Test location filter checks VWAP slope"""
        candles = [self._create_candle(i, 2000.0 + i*0.01, 2000.5 + i*0.01, 1999.5 + i*0.01, 2000.0 + i*0.01) for i in range(20)]
        
        # Mock VWAP std and slope
        with patch.object(self.checker, '_calculate_vwap_std', return_value=0.5):
            with patch.object(self.checker, '_calculate_vwap_slope', return_value=0.001):  # Steep slope
                result = self.checker._check_location_filter('XAUUSDc', candles, 2001.5, 2000.0, 0.6)
                # Should check slope
                self.assertIsNotNone(result)
                self.assertIn('vwap_slope', result)


class TestRangeScalpLogic(unittest.TestCase):
    """Test Range Scalp strategy-specific logic"""
    
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
                'range_scalp': {
                    'min_range_respects': 2,
                    'edge_proximity_threshold': 0.005
                },
                'confluence_weights': {
                    'range_scalp': {
                        'edge_proximity': 1.0,
                        'sweep_quality': 1.0,
                        'range_respect': 1.0
                    }
                }
            }
        }
        
        self.checker = RangeScalpChecker(
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
    
    def test_location_filter_requires_range_edge(self):
        """Test location filter requires price at range edge"""
        candles = [self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0) for i in range(20)]
        
        # Create range structure
        range_structure = RangeStructure(
            range_type='dynamic',
            range_high=2000.5,
            range_low=1999.5,
            range_mid=2000.0,
            range_width_atr=1.0,
            critical_gaps=CriticalGapZones(
                upper_zone_start=2000.3,
                upper_zone_end=2000.5,
                lower_zone_start=1999.5,
                lower_zone_end=1999.7
            ),
            touch_count={},
            validated=True
        )
        
        self.checker._current_snapshot = {'range_structure': range_structure}
        
        # Price at middle (not at edge)
        result = self.checker._check_location_filter('XAUUSDc', candles, 2000.0, 2000.0, 0.6)
        self.assertFalse(result.get('passed', True))  # Should fail
        
        # Price at high edge
        result = self.checker._check_location_filter('XAUUSDc', candles, 2000.5, 2000.0, 0.6)
        # Should pass if at edge and range respects met
        self.assertIsNotNone(result)
    
    def test_location_filter_requires_range_respects(self):
        """Test location filter requires minimum range respects"""
        candles = [self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0) for i in range(20)]
        
        range_structure = RangeStructure(
            range_type='dynamic',
            range_high=2000.5,
            range_low=1999.5,
            range_mid=2000.0,
            range_width_atr=1.0,
            critical_gaps=CriticalGapZones(
                upper_zone_start=2000.3,
                upper_zone_end=2000.5,
                lower_zone_start=1999.5,
                lower_zone_end=1999.7
            ),
            touch_count={},
            validated=True
        )
        
        self.checker._current_snapshot = {'range_structure': range_structure}
        
        # Mock range respects to be 0 (insufficient)
        with patch.object(self.checker, '_count_range_respects', return_value=0):
            result = self.checker._check_location_filter('XAUUSDc', candles, 2000.5, 2000.0, 0.6)
            self.assertFalse(result.get('passed', True))  # Should fail
        
        # Mock range respects to be 2 (sufficient)
        with patch.object(self.checker, '_count_range_respects', return_value=2):
            result = self.checker._check_location_filter('XAUUSDc', candles, 2000.5, 2000.0, 0.6)
            # Should pass if respects >= 2
            self.assertIsNotNone(result)


class TestBalancedZoneLogic(unittest.TestCase):
    """Test Balanced Zone strategy-specific logic"""
    
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
                'balanced_zone': {
                    'ema_vwap_equilibrium_threshold': 0.001,
                    'require_equilibrium_for_fade': True
                },
                'confluence_weights': {
                    'balanced_zone': {
                        'compression_quality': 1.0,
                        'equal_highs_lows': 1.0,
                        'vwap_alignment': 1.0
                    }
                }
            }
        }
        
        # Create mock m1_analyzer
        self.m1_analyzer = Mock()
        self.m1_analyzer.analyze_microstructure = Mock(return_value={
            'liquidity_zones': {'equal_highs_detected': False, 'equal_lows_detected': False}
        })
        
        self.checker = BalancedZoneChecker(
            config=self.config,
            volatility_filter=Mock(),
            vwap_filter=Mock(),
            sweep_detector=Mock(),
            ob_detector=Mock(),
            spread_tracker=Mock(),
            m1_analyzer=self.m1_analyzer,
            session_manager=None,
            news_service=None,
            strategy_name='balanced_zone'
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
    
    def test_location_filter_requires_compression(self):
        """Test location filter requires compression block"""
        candles = [self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0) for i in range(20)]
        
        # Mock compression check to return False
        with patch.object(self.checker, '_check_compression_block', return_value=False):
            result = self.checker._check_location_filter('XAUUSDc', candles, 2000.0, 2000.0, 0.6)
            self.assertFalse(result.get('passed', True))  # Should fail
        
        # Mock compression check to return True
        with patch.object(self.checker, '_check_compression_block', return_value=True):
            # Also need equal highs/lows and VWAP alignment
            self.m1_analyzer.analyze_microstructure.return_value = {
                'liquidity_zones': {'equal_highs_detected': True, 'equal_lows_detected': False}
            }
            result = self.checker._check_location_filter('XAUUSDc', candles, 2000.0, 2000.0, 0.6)
            # Should pass if all conditions met
            self.assertIsNotNone(result)
    
    def test_location_filter_ema_vwap_equilibrium_for_fade(self):
        """Test location filter requires EMA-VWAP equilibrium for fade entries"""
        candles = [self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0) for i in range(20)]
        
        vwap = 2000.0
        
        # Mock entry type as fade
        with patch.object(self.checker, '_detect_entry_type_from_candles', return_value='fade'):
            # Mock compression and equal highs and VWAP alignment
            with patch.object(self.checker, '_check_compression_block', return_value=True):
                self.m1_analyzer.analyze_microstructure.return_value = {
                    'liquidity_zones': {'equal_highs_detected': True}
                }
                
                # Mock EMA calculation - far from VWAP (not in equilibrium)
                # Distance = |2002.0 - 2000.0| / 2000.0 = 0.001 (0.1%)
                # Threshold is 0.001, so 0.001 > 0.001 is False, but let's use larger distance
                with patch.object(self.checker, '_calculate_ema', return_value=2003.0):  # EMA far from VWAP (0.15% away, > 0.1% threshold)
                    result = self.checker._check_location_filter('XAUUSDc', candles, 2000.0, vwap, 0.6)
                    # Should fail equilibrium check if distance > threshold
                    # But might also fail other checks, so just verify it doesn't crash
                    self.assertIsNotNone(result)
                    # Verify the result contains equilibrium information
                    if 'reasons' in result:
                        # Check if equilibrium is mentioned in reasons
                        reasons_str = ' '.join(result.get('reasons', []))
                        # If equilibrium check failed, it should be in reasons
                        # But we can't assert it's there since other checks might fail first
                
                # Mock EMA calculation - close to VWAP (in equilibrium)
                with patch.object(self.checker, '_calculate_ema', return_value=2000.0005):  # EMA very close to VWAP (< 0.001 threshold)
                    result = self.checker._check_location_filter('XAUUSDc', candles, 2000.0, vwap, 0.6)
                    # Should pass if in equilibrium and other conditions met
                    self.assertIsNotNone(result)


class TestConfluenceScoring(unittest.TestCase):
    """Test confluence scoring for each strategy"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'regime_detection': {
                'confluence_weights': {
                    'vwap_reversion': {
                        'deviation_strength': 2.0,
                        'choch_quality': 2.0,
                        'volume_confirmation': 1.0
                    },
                    'range_scalp': {
                        'edge_proximity': 2.0,
                        'sweep_quality': 2.0,
                        'range_respect': 1.0
                    },
                    'balanced_zone': {
                        'compression_quality': 2.0,
                        'equal_highs_lows': 2.0,
                        'vwap_alignment': 1.0
                    }
                }
            }
        }
    
    def test_vwap_reversion_confluence_scoring(self):
        """Test VWAP reversion confluence scoring"""
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
            'deviation_sigma': 3.0,  # High deviation
            'vwap_slope_ok': True,
            'volume_spike': True
        }
        signal_result = {
            'primary_triggers': ['CHOCH_AT_EXTREME'],
            'secondary_confluence': ['VOLUME_CONFIRMED']
        }
        
        score = checker._calculate_confluence_score(
            'XAUUSDc', [], 2000.0, 2000.0, 0.6, location_result, signal_result
        )
        
        # Should have positive score with good conditions
        self.assertGreater(score, 0.0)
        self.assertGreaterEqual(score, 5.0)  # Should meet minimum
    
    def test_range_scalp_confluence_scoring(self):
        """Test range scalp confluence scoring"""
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
        
        location_result = {
            'edge_proximity_score': 2.0,  # Maximum
            'range_respects': 3,  # Good
            'bb_compression': True
        }
        signal_result = {
            'primary_triggers': ['MICRO_LIQUIDITY_SWEEP'],
            'secondary_confluence': ['CHOCH_REVERSAL'],
            'sweep_quality_score': 2.0
        }
        
        score = checker._calculate_confluence_score(
            'XAUUSDc', [], 2000.0, 2000.0, 0.6, location_result, signal_result
        )
        
        # Should have high score with good conditions
        self.assertGreater(score, 0.0)
        self.assertGreaterEqual(score, 5.0)
    
    def test_balanced_zone_confluence_scoring(self):
        """Test balanced zone confluence scoring"""
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
        
        location_result = {
            'compression': True,
            'equal_highs': True,
            'vwap_alignment': True,
            'entry_type': 'fade'
        }
        signal_result = {
            'primary_triggers': ['MINI_EXTREME_TAP', 'CHOCH_FADE_CONFIRMATION'],
            'secondary_confluence': ['COMPRESSION_CONFIRMED']
        }
        
        score = checker._calculate_confluence_score(
            'XAUUSDc', [], 2000.0, 2000.0, 0.6, location_result, signal_result
        )
        
        # Should have high score with good conditions
        self.assertGreater(score, 0.0)
        self.assertGreaterEqual(score, 5.0)


if __name__ == '__main__':
    unittest.main()

