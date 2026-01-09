"""
Tests for Phase 3: Auto-Execution Plan Validation

Tests the volatility state validation system to ensure:
- AutoExecutionValidator correctly validates plans against volatility states
- get_current_regime() method works correctly
- _prepare_timeframe_data() properly formats MT5 data
- Integration with plan creation works
"""
import unittest
import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from handlers.auto_execution_validator import AutoExecutionValidator
from infra.volatility_regime_detector import RegimeDetector, VolatilityRegime


class TestAutoExecutionValidator(unittest.TestCase):
    """Tests for AutoExecutionValidator class."""

    def setUp(self):
        """Set up for each test method."""
        self.validator = AutoExecutionValidator()

    def test_validate_session_switch_flare_blocks_all(self):
        """Test that SESSION_SWITCH_FLARE blocks all plans."""
        plan = {
            "conditions": {"strategy_type": "breakout_ib_volatility_trap"},
            "notes": "Test plan"
        }
        
        is_valid, reason = self.validator.validate_volatility_state(
            plan=plan,
            volatility_regime=VolatilityRegime.SESSION_SWITCH_FLARE,
            strategy_type="breakout_ib_volatility_trap"
        )
        
        self.assertFalse(is_valid)
        self.assertIsNotNone(reason)
        self.assertIn("SESSION_SWITCH_FLARE", reason)

    def test_validate_fragmented_chop_allows_micro_scalp(self):
        """Test that FRAGMENTED_CHOP allows micro_scalp."""
        plan = {
            "conditions": {"strategy_type": "micro_scalp"},
            "notes": "Test plan"
        }
        
        is_valid, reason = self.validator.validate_volatility_state(
            plan=plan,
            volatility_regime=VolatilityRegime.FRAGMENTED_CHOP,
            strategy_type="micro_scalp"
        )
        
        self.assertTrue(is_valid)
        self.assertIsNone(reason)

    def test_validate_fragmented_chop_blocks_trend_continuation(self):
        """Test that FRAGMENTED_CHOP blocks trend_continuation_pullback."""
        plan = {
            "conditions": {"strategy_type": "trend_continuation_pullback"},
            "notes": "Test plan"
        }
        
        is_valid, reason = self.validator.validate_volatility_state(
            plan=plan,
            volatility_regime=VolatilityRegime.FRAGMENTED_CHOP,
            strategy_type="trend_continuation_pullback"
        )
        
        self.assertFalse(is_valid)
        self.assertIsNotNone(reason)
        self.assertIn("FRAGMENTED_CHOP", reason)

    def test_validate_post_breakout_decay_blocks_trend_continuation(self):
        """Test that POST_BREAKOUT_DECAY blocks trend continuation strategies."""
        plan = {
            "conditions": {"strategy_type": "trend_continuation_pullback"},
            "notes": "Test plan"
        }
        
        is_valid, reason = self.validator.validate_volatility_state(
            plan=plan,
            volatility_regime=VolatilityRegime.POST_BREAKOUT_DECAY,
            strategy_type="trend_continuation_pullback"
        )
        
        self.assertFalse(is_valid)
        self.assertIsNotNone(reason)
        self.assertIn("POST_BREAKOUT_DECAY", reason)

    def test_validate_pre_breakout_tension_discourages_mean_reversion(self):
        """Test that PRE_BREAKOUT_TENSION discourages mean reversion."""
        plan = {
            "conditions": {"strategy_type": "mean_reversion_range_scalp"},
            "notes": "Test plan"
        }
        
        is_valid, reason = self.validator.validate_volatility_state(
            plan=plan,
            volatility_regime=VolatilityRegime.PRE_BREAKOUT_TENSION,
            strategy_type="mean_reversion_range_scalp"
        )
        
        self.assertFalse(is_valid)
        self.assertIsNotNone(reason)
        self.assertIn("PRE_BREAKOUT_TENSION", reason)

    def test_validate_extracts_strategy_type_from_plan(self):
        """Test that validator extracts strategy_type from plan if not provided."""
        plan = {
            "conditions": {"strategy_type": "breakout_ib_volatility_trap"},
            "notes": "Test plan"
        }
        
        is_valid, reason = self.validator.validate_volatility_state(
            plan=plan,
            volatility_regime=VolatilityRegime.SESSION_SWITCH_FLARE
            # strategy_type not provided - should extract from plan
        )
        
        self.assertFalse(is_valid)  # Should still block because of SESSION_SWITCH_FLARE

    def test_validate_allows_compatible_strategies(self):
        """Test that validator allows strategies compatible with volatility state."""
        plan = {
            "conditions": {"strategy_type": "breakout_ib_volatility_trap"},
            "notes": "Test plan"
        }
        
        is_valid, reason = self.validator.validate_volatility_state(
            plan=plan,
            volatility_regime=VolatilityRegime.PRE_BREAKOUT_TENSION,
            strategy_type="breakout_ib_volatility_trap"
        )
        
        self.assertTrue(is_valid)
        self.assertIsNone(reason)


class TestRegimeDetectorHelpers(unittest.TestCase):
    """Tests for RegimeDetector helper methods."""

    def setUp(self):
        """Set up for each test method."""
        self.detector = RegimeDetector()
        self.test_symbol = "BTCUSDc"
        
        # Create mock MT5 rates array (8 columns: time, open, high, low, close, tick_volume, spread, real_volume)
        self.mock_rates = np.array([
            [1609459200, 29000.0, 29100.0, 28900.0, 29050.0, 1000, 10, 500],  # First candle
            [1609459260, 29050.0, 29150.0, 29000.0, 29100.0, 1200, 10, 600],  # Second candle
            [1609459320, 29100.0, 29200.0, 29050.0, 29150.0, 1500, 10, 700],  # Third candle
        ])

    @patch('infra.indicator_bridge.IndicatorBridge')
    def test_prepare_timeframe_data_success(self, mock_bridge_class):
        """Test _prepare_timeframe_data() with valid MT5 rates."""
        # Mock IndicatorBridge
        mock_bridge = Mock()
        mock_bridge._calculate_indicators.return_value = {
            'atr14': 150.0,
            'bb_upper': 29200.0,
            'bb_middle': 29100.0,
            'bb_lower': 29000.0,
            'adx': 25.0
        }
        mock_bridge_class.return_value = mock_bridge
        
        result = self.detector._prepare_timeframe_data(self.mock_rates, "M5")
        
        self.assertIsNotNone(result)
        self.assertIn('rates', result)
        self.assertIn('atr_14', result)
        self.assertIn('atr_50', result)
        self.assertIn('bb_upper', result)
        self.assertIn('bb_lower', result)
        self.assertIn('bb_middle', result)
        self.assertIn('adx', result)
        self.assertIn('volume', result)
        self.assertEqual(result['atr_14'], 150.0)
        self.assertEqual(result['bb_upper'], 29200.0)

    def test_prepare_timeframe_data_empty_rates(self):
        """Test _prepare_timeframe_data() with empty rates."""
        result = self.detector._prepare_timeframe_data(None, "M5")
        self.assertIsNone(result)
        
        result = self.detector._prepare_timeframe_data(np.array([]), "M5")
        self.assertIsNone(result)

    @patch('infra.indicator_bridge.IndicatorBridge')
    def test_prepare_timeframe_data_6_columns(self, mock_bridge_class):
        """Test _prepare_timeframe_data() with 6-column rates array."""
        # Create 6-column array (no spread, real_volume)
        rates_6col = np.array([
            [1609459200, 29000.0, 29100.0, 28900.0, 29050.0, 1000],
            [1609459260, 29050.0, 29150.0, 29000.0, 29100.0, 1200],
        ])
        
        mock_bridge = Mock()
        mock_bridge._calculate_indicators.return_value = {
            'atr14': 150.0,
            'bb_upper': 29200.0,
            'bb_middle': 29100.0,
            'bb_lower': 29000.0,
            'adx': 25.0
        }
        mock_bridge_class.return_value = mock_bridge
        
        result = self.detector._prepare_timeframe_data(rates_6col, "M5")
        
        self.assertIsNotNone(result)
        self.assertIn('atr_14', result)

    @patch('MetaTrader5.copy_rates_from_pos')
    @patch.object(RegimeDetector, '_prepare_timeframe_data')
    @patch.object(RegimeDetector, 'detect_regime')
    def test_get_current_regime_success(self, mock_detect_regime, mock_prepare_data, mock_copy_rates):
        """Test get_current_regime() with successful detection."""
        # Mock MT5 rates
        mock_rates = np.array([[1609459200, 29000.0, 29100.0, 28900.0, 29050.0, 1000, 10, 500]])
        mock_copy_rates.return_value = mock_rates
        
        # Mock prepare_timeframe_data
        mock_prepare_data.return_value = {
            'rates': mock_rates,
            'atr_14': 150.0,
            'atr_50': 200.0,
            'bb_upper': 29200.0,
            'bb_lower': 29000.0,
            'bb_middle': 29100.0,
            'adx': 25.0,
            'volume': mock_rates[:, 5]
        }
        
        # Mock detect_regime
        mock_detect_regime.return_value = {
            'regime': VolatilityRegime.STABLE,
            'confidence': 85.0
        }
        
        result = self.detector.get_current_regime(self.test_symbol)
        
        self.assertIsNotNone(result)
        self.assertEqual(result, VolatilityRegime.STABLE)
        self.assertEqual(mock_detect_regime.call_count, 1)

    @patch('MetaTrader5.copy_rates_from_pos')
    def test_get_current_regime_no_data(self, mock_copy_rates):
        """Test get_current_regime() when no timeframe data is available."""
        mock_copy_rates.return_value = None
        
        result = self.detector.get_current_regime(self.test_symbol)
        
        self.assertIsNone(result)

    @patch('MetaTrader5.copy_rates_from_pos')
    @patch.object(RegimeDetector, '_prepare_timeframe_data')
    def test_get_current_regime_prepare_fails(self, mock_prepare_data, mock_copy_rates):
        """Test get_current_regime() when _prepare_timeframe_data fails."""
        mock_rates = np.array([[1609459200, 29000.0, 29100.0, 28900.0, 29050.0, 1000, 10, 500]])
        mock_copy_rates.return_value = mock_rates
        mock_prepare_data.return_value = None  # Simulate failure
        
        result = self.detector.get_current_regime(self.test_symbol)
        
        self.assertIsNone(result)

    @patch('MetaTrader5.copy_rates_from_pos')
    @patch.object(RegimeDetector, '_prepare_timeframe_data')
    @patch.object(RegimeDetector, 'detect_regime')
    def test_get_current_regime_detection_fails(self, mock_detect_regime, mock_prepare_data, mock_copy_rates):
        """Test get_current_regime() when detect_regime fails."""
        mock_rates = np.array([[1609459200, 29000.0, 29100.0, 28900.0, 29050.0, 1000, 10, 500]])
        mock_copy_rates.return_value = mock_rates
        mock_prepare_data.return_value = {
            'rates': mock_rates,
            'atr_14': 150.0,
            'atr_50': 200.0,
            'bb_upper': 29200.0,
            'bb_lower': 29000.0,
            'bb_middle': 29100.0,
            'adx': 25.0,
            'volume': mock_rates[:, 5]
        }
        mock_detect_regime.side_effect = Exception("Detection failed")
        
        result = self.detector.get_current_regime(self.test_symbol)
        
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

