"""
Tests for Phase 2: Volatility Strategy Mapper

Tests the volatility_strategy_mapper module to ensure:
- Strategy mappings are correct for all new volatility states
- get_strategies_for_volatility() returns correct recommendations
- Fallback behavior for basic states (STABLE, TRANSITIONAL, VOLATILE)
- Session-specific adjustments (if implemented)
"""
import unittest
import sys
import os

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.volatility_strategy_mapper import (
    get_strategies_for_volatility,
    VOLATILITY_STRATEGY_MAP
)
from infra.volatility_regime_detector import VolatilityRegime


class TestVolatilityStrategyMapper(unittest.TestCase):
    """Tests for volatility strategy mapper module."""

    def setUp(self):
        """Set up for each test method."""
        self.test_symbol = "BTCUSDc"
        self.test_session = "LONDON"

    # --- Test Strategy Mappings ---
    def test_pre_breakout_tension_mapping(self):
        """Verify PRE_BREAKOUT_TENSION strategy mapping."""
        mapping = VOLATILITY_STRATEGY_MAP.get(VolatilityRegime.PRE_BREAKOUT_TENSION)
        self.assertIsNotNone(mapping)
        self.assertIn("breakout_ib_volatility_trap", mapping.get("prioritize", []))
        self.assertIn("liquidity_sweep_reversal", mapping.get("prioritize", []))
        self.assertIn("breaker_block", mapping.get("prioritize", []))
        self.assertIn("mean_reversion_range_scalp", mapping.get("avoid", []))
        self.assertEqual(mapping.get("confidence_adjustment"), +10)

    def test_post_breakout_decay_mapping(self):
        """Verify POST_BREAKOUT_DECAY strategy mapping."""
        mapping = VOLATILITY_STRATEGY_MAP.get(VolatilityRegime.POST_BREAKOUT_DECAY)
        self.assertIsNotNone(mapping)
        self.assertIn("mean_reversion_range_scalp", mapping.get("prioritize", []))
        self.assertIn("fvg_retracement", mapping.get("prioritize", []))
        self.assertIn("order_block_rejection", mapping.get("prioritize", []))
        self.assertIn("trend_continuation_pullback", mapping.get("avoid", []))
        self.assertEqual(mapping.get("confidence_adjustment"), -5)

    def test_fragmented_chop_mapping(self):
        """Verify FRAGMENTED_CHOP strategy mapping."""
        mapping = VOLATILITY_STRATEGY_MAP.get(VolatilityRegime.FRAGMENTED_CHOP)
        self.assertIsNotNone(mapping)
        self.assertIn("micro_scalp", mapping.get("prioritize", []))
        self.assertIn("mean_reversion_range_scalp", mapping.get("prioritize", []))
        self.assertIn("trend_continuation_pullback", mapping.get("avoid", []))
        self.assertEqual(mapping.get("confidence_adjustment"), -15)

    def test_session_switch_flare_mapping(self):
        """Verify SESSION_SWITCH_FLARE strategy mapping."""
        mapping = VOLATILITY_STRATEGY_MAP.get(VolatilityRegime.SESSION_SWITCH_FLARE)
        self.assertIsNotNone(mapping)
        self.assertEqual(len(mapping.get("prioritize", [])), 0)  # No strategies
        self.assertIn("ALL", mapping.get("avoid", []))
        self.assertEqual(mapping.get("confidence_adjustment"), -100)

    # --- Test get_strategies_for_volatility() Function ---
    def test_get_strategies_pre_breakout_tension(self):
        """Test get_strategies_for_volatility() for PRE_BREAKOUT_TENSION."""
        result = get_strategies_for_volatility(
            volatility_regime=VolatilityRegime.PRE_BREAKOUT_TENSION,
            symbol=self.test_symbol,
            session=self.test_session
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn("prioritize", result)
        self.assertIn("avoid", result)
        self.assertIn("confidence_adjustment", result)
        self.assertIn("recommendation", result)
        self.assertIn("wait_reason", result)
        
        self.assertIn("breakout_ib_volatility_trap", result["prioritize"])
        self.assertEqual(result["confidence_adjustment"], +10)
        self.assertIsNone(result["wait_reason"])

    def test_get_strategies_session_switch_flare(self):
        """Test get_strategies_for_volatility() for SESSION_SWITCH_FLARE."""
        result = get_strategies_for_volatility(
            volatility_regime=VolatilityRegime.SESSION_SWITCH_FLARE,
            symbol=self.test_symbol,
            session=self.test_session
        )
        
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result["prioritize"]), 0)
        self.assertIn("ALL", result["avoid"])
        self.assertEqual(result["confidence_adjustment"], -100)
        self.assertIn("WAIT", result["recommendation"])
        self.assertEqual(result["wait_reason"], "SESSION_SWITCH_FLARE")

    def test_get_strategies_fallback_stable(self):
        """Test get_strategies_for_volatility() fallback for STABLE."""
        result = get_strategies_for_volatility(
            volatility_regime=VolatilityRegime.STABLE,
            symbol=self.test_symbol,
            session=self.test_session
        )
        
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result["prioritize"]), 0)
        self.assertEqual(len(result["avoid"]), 0)
        self.assertEqual(result["confidence_adjustment"], 0)
        self.assertIn("STABLE", result["recommendation"])
        self.assertIsNone(result["wait_reason"])

    def test_get_strategies_fallback_transitional(self):
        """Test get_strategies_for_volatility() fallback for TRANSITIONAL."""
        result = get_strategies_for_volatility(
            volatility_regime=VolatilityRegime.TRANSITIONAL,
            symbol=self.test_symbol,
            session=self.test_session
        )
        
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result["prioritize"]), 0)
        self.assertEqual(len(result["avoid"]), 0)
        self.assertEqual(result["confidence_adjustment"], 0)
        self.assertIn("TRANSITIONAL", result["recommendation"])

    def test_get_strategies_fallback_volatile(self):
        """Test get_strategies_for_volatility() fallback for VOLATILE."""
        result = get_strategies_for_volatility(
            volatility_regime=VolatilityRegime.VOLATILE,
            symbol=self.test_symbol,
            session=self.test_session
        )
        
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result["prioritize"]), 0)
        self.assertEqual(len(result["avoid"]), 0)
        self.assertEqual(result["confidence_adjustment"], 0)
        self.assertIn("VOLATILE", result["recommendation"])

    def test_get_strategies_with_none_session(self):
        """Test get_strategies_for_volatility() with None session."""
        result = get_strategies_for_volatility(
            volatility_regime=VolatilityRegime.PRE_BREAKOUT_TENSION,
            symbol=self.test_symbol,
            session=None
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn("prioritize", result)
        self.assertIn("avoid", result)

    def test_get_strategies_recommendation_format(self):
        """Test that recommendation string is properly formatted."""
        result = get_strategies_for_volatility(
            volatility_regime=VolatilityRegime.PRE_BREAKOUT_TENSION,
            symbol=self.test_symbol,
            session=self.test_session
        )
        
        self.assertIsInstance(result["recommendation"], str)
        self.assertGreater(len(result["recommendation"]), 0)
        # Should contain strategy names
        self.assertIn("breakout_ib_volatility_trap", result["recommendation"])


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

