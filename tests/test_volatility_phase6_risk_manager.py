"""
Phase 6.1 Testing: Volatility Risk Manager Updates

Tests for volatility-aware position sizing and SL/TP adjustments with new volatility states
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from infra.volatility_regime_detector import VolatilityRegime
from infra.volatility_risk_manager import VolatilityRiskManager


class TestVolatilityRiskManagerPhase6(unittest.TestCase):
    """Test volatility risk manager with new volatility states"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.risk_manager = VolatilityRiskManager()
        
        # Base risk percentage for testing
        self.base_risk = 1.0  # 1.0%
        
        # Mock volatility regime data structures
        self.create_mock_regime_data = lambda regime, confidence=85.0: {
            "regime": regime,
            "confidence": confidence,
            "atr_ratio": 1.0,
            "bb_width_ratio": 1.0,
            "adx_composite": 25.0,
            "volume_confirmed": True
        }
    
    def test_pre_breakout_tension_risk_adjustment(self):
        """Test PRE_BREAKOUT_TENSION risk adjustment"""
        regime_data = self.create_mock_regime_data(VolatilityRegime.PRE_BREAKOUT_TENSION, 85.0)
        
        adjusted_risk = self.risk_manager.calculate_volatility_adjusted_risk_pct(
            volatility_regime=regime_data,
            base_risk_pct=None  # Use regime-specific default
        )
        
        # PRE_BREAKOUT_TENSION: 0.85% base risk
        # With 85% confidence: 0.85 * 0.85 = 0.7225%
        expected_risk = 0.85 * 0.85  # base_risk * confidence_factor
        self.assertAlmostEqual(adjusted_risk, expected_risk, places=2)
        self.assertLess(adjusted_risk, self.base_risk)  # Should be reduced
    
    def test_post_breakout_decay_risk_adjustment(self):
        """Test POST_BREAKOUT_DECAY risk adjustment"""
        regime_data = self.create_mock_regime_data(VolatilityRegime.POST_BREAKOUT_DECAY, 80.0)
        
        adjusted_risk = self.risk_manager.calculate_volatility_adjusted_risk_pct(
            volatility_regime=regime_data,
            base_risk_pct=None  # Use regime-specific default
        )
        
        # POST_BREAKOUT_DECAY: 0.9% base risk
        # With 80% confidence: 0.9 * 0.8 = 0.72%
        expected_risk = 0.9 * 0.8
        self.assertAlmostEqual(adjusted_risk, expected_risk, places=2)
        self.assertLess(adjusted_risk, self.base_risk)  # Should be reduced
    
    def test_fragmented_chop_risk_adjustment(self):
        """Test FRAGMENTED_CHOP risk adjustment"""
        regime_data = self.create_mock_regime_data(VolatilityRegime.FRAGMENTED_CHOP, 75.0)
        
        adjusted_risk = self.risk_manager.calculate_volatility_adjusted_risk_pct(
            volatility_regime=regime_data,
            base_risk_pct=None  # Use regime-specific default
        )
        
        # FRAGMENTED_CHOP: 0.6% base risk
        # With 75% confidence: 0.6 * 0.75 = 0.45%
        expected_risk = 0.6 * 0.75
        self.assertAlmostEqual(adjusted_risk, expected_risk, places=2)
        self.assertLess(adjusted_risk, self.base_risk)  # Should be significantly reduced
    
    def test_session_switch_flare_blocks_trading(self):
        """Test SESSION_SWITCH_FLARE blocks trading (0% risk)"""
        regime_data = self.create_mock_regime_data(VolatilityRegime.SESSION_SWITCH_FLARE, 90.0)
        
        adjusted_risk = self.risk_manager.calculate_volatility_adjusted_risk_pct(
            volatility_regime=regime_data,
            base_risk_pct=None  # Use regime-specific default
        )
        
        # SESSION_SWITCH_FLARE: 0.0% base risk (blocks trading)
        self.assertEqual(adjusted_risk, 0.0)
    
    def test_pre_breakout_tension_sl_multiplier(self):
        """Test PRE_BREAKOUT_TENSION stop loss multiplier"""
        regime_data = self.create_mock_regime_data(VolatilityRegime.PRE_BREAKOUT_TENSION)
        entry_price = 100.0
        direction = "BUY"
        atr = 2.0
        
        sl = self.risk_manager.calculate_volatility_adjusted_stop_loss(
            entry_price=entry_price,
            direction=direction,
            atr=atr,
            volatility_regime=regime_data
        )
        
        # PRE_BREAKOUT_TENSION: 1.725× ATR
        # SL distance = 2.0 * 1.725 = 3.45
        # BUY: SL = 100.0 - 3.45 = 96.55
        expected_sl = entry_price - (atr * 1.725)
        self.assertAlmostEqual(sl, expected_sl, places=2)
    
    def test_post_breakout_decay_sl_multiplier(self):
        """Test POST_BREAKOUT_DECAY stop loss multiplier"""
        regime_data = self.create_mock_regime_data(VolatilityRegime.POST_BREAKOUT_DECAY)
        entry_price = 100.0
        direction = "SELL"
        atr = 2.0
        
        sl = self.risk_manager.calculate_volatility_adjusted_stop_loss(
            entry_price=entry_price,
            direction=direction,
            atr=atr,
            volatility_regime=regime_data
        )
        
        # POST_BREAKOUT_DECAY: 1.5× ATR (same as stable)
        # SL distance = 2.0 * 1.5 = 3.0
        # SELL: SL = 100.0 + 3.0 = 103.0
        expected_sl = entry_price + (atr * 1.5)
        self.assertAlmostEqual(sl, expected_sl, places=2)
    
    def test_fragmented_chop_sl_multiplier(self):
        """Test FRAGMENTED_CHOP stop loss multiplier (tighter)"""
        regime_data = self.create_mock_regime_data(VolatilityRegime.FRAGMENTED_CHOP)
        entry_price = 100.0
        direction = "BUY"
        atr = 2.0
        
        sl = self.risk_manager.calculate_volatility_adjusted_stop_loss(
            entry_price=entry_price,
            direction=direction,
            atr=atr,
            volatility_regime=regime_data
        )
        
        # FRAGMENTED_CHOP: 1.2× ATR (tighter)
        # SL distance = 2.0 * 1.2 = 2.4
        # BUY: SL = 100.0 - 2.4 = 97.6
        expected_sl = entry_price - (atr * 1.2)
        self.assertAlmostEqual(sl, expected_sl, places=2)
        # Should be tighter than stable (1.5×)
        stable_sl = entry_price - (atr * 1.5)
        self.assertGreater(sl, stable_sl)  # Higher SL = tighter stop
    
    def test_session_switch_flare_blocks_sl_calculation(self):
        """Test SESSION_SWITCH_FLARE blocks SL calculation"""
        regime_data = self.create_mock_regime_data(VolatilityRegime.SESSION_SWITCH_FLARE)
        entry_price = 100.0
        direction = "BUY"
        atr = 2.0
        
        sl = self.risk_manager.calculate_volatility_adjusted_stop_loss(
            entry_price=entry_price,
            direction=direction,
            atr=atr,
            volatility_regime=regime_data
        )
        
        # SESSION_SWITCH_FLARE should return None (blocks trading)
        self.assertIsNone(sl)
    
    def test_pre_breakout_tension_tp_multiplier(self):
        """Test PRE_BREAKOUT_TENSION take profit multiplier"""
        regime_data = self.create_mock_regime_data(VolatilityRegime.PRE_BREAKOUT_TENSION)
        entry_price = 100.0
        stop_loss = 97.0  # 3.0 distance
        direction = "BUY"
        atr = 2.0
        
        tp = self.risk_manager.calculate_volatility_adjusted_take_profit(
            entry_price=entry_price,
            stop_loss=stop_loss,
            direction=direction,
            atr=atr,
            volatility_regime=regime_data
        )
        
        # PRE_BREAKOUT_TENSION: 3.0× ATR
        # TP distance = 2.0 * 3.0 = 6.0
        # BUY: TP = 100.0 + 6.0 = 106.0
        expected_tp = entry_price + (atr * 3.0)
        self.assertAlmostEqual(tp, expected_tp, places=2)
    
    def test_post_breakout_decay_tp_multiplier(self):
        """Test POST_BREAKOUT_DECAY take profit multiplier (reduced)"""
        regime_data = self.create_mock_regime_data(VolatilityRegime.POST_BREAKOUT_DECAY)
        entry_price = 100.0
        stop_loss = 97.0
        direction = "BUY"
        atr = 2.0
        
        tp = self.risk_manager.calculate_volatility_adjusted_take_profit(
            entry_price=entry_price,
            stop_loss=stop_loss,
            direction=direction,
            atr=atr,
            volatility_regime=regime_data
        )
        
        # POST_BREAKOUT_DECAY: 2.0× ATR (reduced)
        # TP distance = 2.0 * 2.0 = 4.0
        # BUY: TP = 100.0 + 4.0 = 104.0
        expected_tp = entry_price + (atr * 2.0)
        self.assertAlmostEqual(tp, expected_tp, places=2)
        # Should be lower than stable (3.0×)
        stable_tp = entry_price + (atr * 3.0)
        self.assertLess(tp, stable_tp)
    
    def test_fragmented_chop_tp_multiplier(self):
        """Test FRAGMENTED_CHOP take profit multiplier (reduced)"""
        regime_data = self.create_mock_regime_data(VolatilityRegime.FRAGMENTED_CHOP)
        entry_price = 100.0
        stop_loss = 97.6  # 2.4 distance (1.2× ATR)
        direction = "BUY"
        atr = 2.0
        
        tp = self.risk_manager.calculate_volatility_adjusted_take_profit(
            entry_price=entry_price,
            stop_loss=stop_loss,
            direction=direction,
            atr=atr,
            volatility_regime=regime_data
        )
        
        # FRAGMENTED_CHOP: 1.8× ATR (reduced)
        # TP distance = 2.0 * 1.8 = 3.6
        # BUY: TP = 100.0 + 3.6 = 103.6
        expected_tp = entry_price + (atr * 1.8)
        self.assertAlmostEqual(tp, expected_tp, places=2)
        # Should be lower than stable (3.0×)
        stable_tp = entry_price + (atr * 3.0)
        self.assertLess(tp, stable_tp)
    
    def test_session_switch_flare_blocks_tp_calculation(self):
        """Test SESSION_SWITCH_FLARE blocks TP calculation"""
        regime_data = self.create_mock_regime_data(VolatilityRegime.SESSION_SWITCH_FLARE)
        entry_price = 100.0
        stop_loss = 97.0
        direction = "BUY"
        atr = 2.0
        
        tp = self.risk_manager.calculate_volatility_adjusted_take_profit(
            entry_price=entry_price,
            stop_loss=stop_loss,
            direction=direction,
            atr=atr,
            volatility_regime=regime_data
        )
        
        # SESSION_SWITCH_FLARE should return None (blocks trading)
        self.assertIsNone(tp)
    
    def test_backward_compatibility_basic_states(self):
        """Test backward compatibility with basic volatility states"""
        # Test STABLE
        stable_data = self.create_mock_regime_data(VolatilityRegime.STABLE, 90.0)
        stable_risk = self.risk_manager.calculate_volatility_adjusted_risk_pct(
            volatility_regime=stable_data,
            base_risk_pct=None  # Use regime-specific default
        )
        # STABLE: 1.0% base risk, 90% confidence = 0.9%
        self.assertAlmostEqual(stable_risk, 1.0 * 0.9, places=2)
        
        # Test VOLATILE
        volatile_data = self.create_mock_regime_data(VolatilityRegime.VOLATILE, 80.0)
        volatile_risk = self.risk_manager.calculate_volatility_adjusted_risk_pct(
            volatility_regime=volatile_data,
            base_risk_pct=None  # Use regime-specific default
        )
        # VOLATILE: 0.5% base risk, 80% confidence = 0.4%
        self.assertAlmostEqual(volatile_risk, 0.5 * 0.8, places=2)
        
        # Test TRANSITIONAL
        transitional_data = self.create_mock_regime_data(VolatilityRegime.TRANSITIONAL, 85.0)
        transitional_risk = self.risk_manager.calculate_volatility_adjusted_risk_pct(
            volatility_regime=transitional_data,
            base_risk_pct=None  # Use regime-specific default
        )
        # TRANSITIONAL: 0.75% base risk, 85% confidence = 0.6375%
        self.assertAlmostEqual(transitional_risk, 0.75 * 0.85, places=2)


if __name__ == '__main__':
    unittest.main()

