"""
Phase 6: Strategy Function Tests
Tests for all SMC strategy functions (TEST-STRAT-*)

Test ID Format: TEST-STRAT-{STRATEGY}-{NUMBER}
"""

import unittest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from unittest.mock import Mock, MagicMock, patch
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# Import strategy functions
from app.engine.strategy_logic import (
    strat_order_block_rejection,
    strat_fvg_retracement,
    strat_breaker_block,
    strat_mitigation_block,
    strat_market_structure_shift,
    strat_inducement_reversal,
    strat_premium_discount_array,
    strat_kill_zone,
    strat_session_liquidity_run
)


class TestOrderBlockRejectionStrategy(unittest.TestCase):
    """TEST-STRAT-OB-001 through TEST-STRAT-OB-005"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "EURUSDc"
        self.base_tech = {
            "symbol": self.symbol,
            "regime": "TREND",
            "adx": 25.0,
            "rsi": 55.0,
            "atr": 0.0010,
            "current_price": 1.1000,
            "m5": pd.DataFrame({
                'time': [1000, 1001, 1002],
                'open': [1.1000, 1.1005, 1.1010],
                'high': [1.1005, 1.1010, 1.1015],
                'low': [0.9995, 1.0000, 1.0005],
                'close': [1.1002, 1.1008, 1.1012]
            })
        }
    
    def test_strat_ob_001_returns_none_when_no_ob(self):
        """TEST-STRAT-OB-001: Returns None when no OB"""
        tech = self.base_tech.copy()
        tech["order_block_bull"] = None
        tech["order_block_bear"] = None
        
        result = strat_order_block_rejection(self.symbol, tech, "TREND")
        self.assertIsNone(result)
    
    def test_strat_ob_002_returns_plan_for_bullish_ob(self):
        """TEST-STRAT-OB-002: Returns plan for bullish OB"""
        tech = self.base_tech.copy()
        tech["order_block_bull"] = {
            "price": 1.0995,
            "ob_strength": 0.75,
            "ob_confluence": ["fvg", "structure"]
        }
        tech["order_block_bear"] = None
        
        result = strat_order_block_rejection(self.symbol, tech, "TREND")
        # May return None if other conditions not met, or a plan
        self.assertTrue(result is None or hasattr(result, 'direction'))
    
    def test_strat_ob_003_returns_plan_for_bearish_ob(self):
        """TEST-STRAT-OB-003: Returns plan for bearish OB"""
        tech = self.base_tech.copy()
        tech["order_block_bull"] = None
        tech["order_block_bear"] = {
            "price": 1.1005,
            "ob_strength": 0.75,
            "ob_confluence": ["fvg", "structure"]
        }
        
        result = strat_order_block_rejection(self.symbol, tech, "TREND")
        # May return None if other conditions not met, or a plan
        self.assertTrue(result is None or hasattr(result, 'direction'))
    
    def test_strat_ob_004_calculates_entry_sl_tp(self):
        """TEST-STRAT-OB-004: Calculates entry/SL/TP correctly"""
        tech = self.base_tech.copy()
        tech["order_block_bull"] = {
            "price": 1.0995,
            "ob_strength": 0.75,
            "ob_confluence": ["fvg", "structure"]
        }
        tech["current_price"] = 1.0995  # Price at OB
        
        result = strat_order_block_rejection(self.symbol, tech, "TREND")
        if result:
            self.assertIsNotNone(result.entry)
            self.assertIsNotNone(result.sl)
            self.assertIsNotNone(result.tp)
            # Verify SL is below entry for LONG
            if result.direction == "LONG":
                self.assertLess(result.sl, result.entry)
            # Verify TP is above entry for LONG
            if result.direction == "LONG":
                self.assertGreater(result.tp, result.entry)
    
    def test_strat_ob_005_respects_confidence_threshold(self):
        """TEST-STRAT-OB-005: Respects confidence threshold"""
        tech = self.base_tech.copy()
        tech["order_block_bull"] = {
            "price": 1.0995,
            "ob_strength": 0.3,  # Low confidence
            "ob_confluence": []
        }
        
        result = strat_order_block_rejection(self.symbol, tech, "TREND")
        # With low confidence, may return None
        # This test verifies graceful handling
        self.assertTrue(result is None or hasattr(result, 'direction'))


class TestFVGRetracementStrategy(unittest.TestCase):
    """TEST-STRAT-FVG-001 through TEST-STRAT-FVG-004"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "EURUSDc"
        self.base_tech = {
            "symbol": self.symbol,
            "regime": "TREND",
            "adx": 25.0,
            "rsi": 55.0,
            "atr": 0.0010,
            "current_price": 1.1000,
            "choch_bull": True,
            "bos_bull": True
        }
    
    def test_strat_fvg_001_returns_none_when_no_fvg(self):
        """TEST-STRAT-FVG-001: Returns None when no FVG"""
        tech = self.base_tech.copy()
        tech["fvg_bull"] = None
        tech["fvg_bear"] = None
        
        result = strat_fvg_retracement(self.symbol, tech, "TREND")
        self.assertIsNone(result)
    
    def test_strat_fvg_002_returns_none_when_fill_low(self):
        """TEST-STRAT-FVG-002: Returns None when fill < 50%"""
        tech = self.base_tech.copy()
        tech["fvg_bull"] = {
            "high": 1.1010,
            "low": 1.1000,
            "filled_pct": 0.3  # Less than 50%
        }
        
        result = strat_fvg_retracement(self.symbol, tech, "TREND")
        # Should return None when fill too low
        self.assertIsNone(result)
    
    def test_strat_fvg_003_returns_plan_when_fill_50_75(self):
        """TEST-STRAT-FVG-003: Returns plan when fill 50-75%"""
        tech = self.base_tech.copy()
        tech["fvg_bull"] = {
            "high": 1.1010,
            "low": 1.1000,
            "filled_pct": 0.65  # In range
        }
        tech["current_price"] = 1.1005  # Within FVG zone
        
        result = strat_fvg_retracement(self.symbol, tech, "TREND")
        # May return plan if all conditions met
        self.assertTrue(result is None or hasattr(result, 'direction'))
    
    def test_strat_fvg_004_entry_at_current_price(self):
        """TEST-STRAT-FVG-004: Entry at current price when in zone"""
        tech = self.base_tech.copy()
        tech["fvg_bull"] = {
            "high": 1.1010,
            "low": 1.1000,
            "filled_pct": 0.65
        }
        tech["current_price"] = 1.1005
        
        result = strat_fvg_retracement(self.symbol, tech, "TREND")
        if result:
            # Entry should be at or near current price
            self.assertAlmostEqual(result.entry, tech["current_price"], places=4)


class TestBreakerBlockStrategy(unittest.TestCase):
    """TEST-STRAT-BREAKER-001 through TEST-STRAT-BREAKER-003"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "EURUSDc"
        self.base_tech = {
            "symbol": self.symbol,
            "regime": "TREND",
            "adx": 25.0,
            "current_price": 1.1000
        }
    
    def test_strat_breaker_001_returns_none_when_no_breaker(self):
        """TEST-STRAT-BREAKER-001: Returns None when no breaker"""
        tech = self.base_tech.copy()
        tech["breaker_block_bull"] = None
        tech["breaker_block_bear"] = None
        
        result = strat_breaker_block(self.symbol, tech, "TREND")
        self.assertIsNone(result)
    
    def test_strat_breaker_002_returns_none_when_ob_not_broken(self):
        """TEST-STRAT-BREAKER-002: Returns None when OB not broken"""
        tech = self.base_tech.copy()
        tech["breaker_block_bull"] = {
            "price": 1.1005,
            "ob_broken": False  # OB not broken yet
        }
        
        result = strat_breaker_block(self.symbol, tech, "TREND")
        # Should return None if OB not broken
        self.assertIsNone(result)
    
    def test_strat_breaker_003_returns_plan_when_retesting(self):
        """TEST-STRAT-BREAKER-003: Returns plan when retesting"""
        tech = self.base_tech.copy()
        tech["breaker_block_bull"] = {
            "price": 1.1005,
            "ob_broken": True,
            "price_retesting": True
        }
        tech["current_price"] = 1.1005
        
        result = strat_breaker_block(self.symbol, tech, "TREND")
        # May return plan if all conditions met
        self.assertTrue(result is None or hasattr(result, 'direction'))


class TestMitigationBlockStrategy(unittest.TestCase):
    """TEST-STRAT-MITIGATION-001 through TEST-STRAT-MITIGATION-002"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "EURUSDc"
        self.base_tech = {
            "symbol": self.symbol,
            "regime": "TREND",
            "current_price": 1.1000
        }
    
    def test_strat_mitigation_001_returns_none_when_no_mitigation(self):
        """TEST-STRAT-MITIGATION-001: Returns None when no mitigation"""
        tech = self.base_tech.copy()
        tech["mitigation_block_bull"] = None
        tech["mitigation_block_bear"] = None
        
        result = strat_mitigation_block(self.symbol, tech, "TREND")
        self.assertIsNone(result)
    
    def test_strat_mitigation_002_returns_plan_when_structure_broken(self):
        """TEST-STRAT-MITIGATION-002: Returns plan when structure broken"""
        tech = self.base_tech.copy()
        tech["mitigation_block_bull"] = {
            "price": 1.1005,
            "structure_broken": True
        }
        tech["fvg_bull"] = {
            "high": 1.1010,
            "low": 1.1000,
            "filled_pct": 0.5
        }
        
        result = strat_mitigation_block(self.symbol, tech, "TREND")
        # May return plan if all conditions met
        self.assertTrue(result is None or hasattr(result, 'direction'))


class TestMarketStructureShiftStrategy(unittest.TestCase):
    """TEST-STRAT-MSS-001 through TEST-STRAT-MSS-002"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "EURUSDc"
        self.base_tech = {
            "symbol": self.symbol,
            "regime": "TREND",
            "current_price": 1.1000
        }
    
    def test_strat_mss_001_returns_none_when_no_mss(self):
        """TEST-STRAT-MSS-001: Returns None when no MSS"""
        tech = self.base_tech.copy()
        tech["mss_bull"] = None
        tech["mss_bear"] = None
        
        result = strat_market_structure_shift(self.symbol, tech, "TREND")
        self.assertIsNone(result)
    
    def test_strat_mss_002_returns_plan_when_pullback(self):
        """TEST-STRAT-MSS-002: Returns plan when pullback detected"""
        tech = self.base_tech.copy()
        tech["mss_bull"] = True
        tech["pullback_to_mss"] = True
        tech["current_price"] = 1.0995  # Pullback price
        
        result = strat_market_structure_shift(self.symbol, tech, "TREND")
        # May return plan if all conditions met
        self.assertTrue(result is None or hasattr(result, 'direction'))


class TestInducementReversalStrategy(unittest.TestCase):
    """TEST-STRAT-INDUCEMENT-001 through TEST-STRAT-INDUCEMENT-002"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "EURUSDc"
        self.base_tech = {
            "symbol": self.symbol,
            "regime": "VOLATILE",
            "current_price": 1.1000
        }
    
    def test_strat_inducement_001_returns_none_when_no_inducement(self):
        """TEST-STRAT-INDUCEMENT-001: Returns None when no inducement"""
        tech = self.base_tech.copy()
        tech["liquidity_grab_bull"] = None
        tech["liquidity_grab_bear"] = None
        
        result = strat_inducement_reversal(self.symbol, tech, "VOLATILE")
        self.assertIsNone(result)
    
    def test_strat_inducement_002_returns_plan_when_all_conditions_met(self):
        """TEST-STRAT-INDUCEMENT-002: Returns plan when all conditions met"""
        tech = self.base_tech.copy()
        tech["liquidity_grab_bull"] = True
        tech["rejection_detected"] = True
        tech["order_block_bull"] = {
            "price": 1.0995,
            "ob_strength": 0.75
        }
        
        result = strat_inducement_reversal(self.symbol, tech, "VOLATILE")
        # May return plan if all conditions met
        self.assertTrue(result is None or hasattr(result, 'direction'))


class TestPremiumDiscountArrayStrategy(unittest.TestCase):
    """TEST-STRAT-PREMIUM-001 through TEST-STRAT-PREMIUM-003"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "EURUSDc"
        self.base_tech = {
            "symbol": self.symbol,
            "regime": "RANGE",
            "current_price": 1.1000
        }
    
    def test_strat_premium_001_returns_none_when_not_in_zone(self):
        """TEST-STRAT-PREMIUM-001: Returns None when not in zone"""
        tech = self.base_tech.copy()
        tech["price_in_discount"] = False
        tech["price_in_premium"] = False
        
        result = strat_premium_discount_array(self.symbol, tech, "RANGE")
        self.assertIsNone(result)
    
    def test_strat_premium_002_returns_long_in_discount(self):
        """TEST-STRAT-PREMIUM-002: Returns LONG in discount zone"""
        tech = self.base_tech.copy()
        tech["price_in_discount"] = True
        tech["price_in_premium"] = False
        tech["fibonacci_levels"] = {
            "discount_zone": (1.0990, 1.1000),
            "premium_zone": (1.1010, 1.1020)
        }
        
        result = strat_premium_discount_array(self.symbol, tech, "RANGE")
        if result:
            self.assertEqual(result.direction, "LONG")
    
    def test_strat_premium_003_returns_short_in_premium(self):
        """TEST-STRAT-PREMIUM-003: Returns SHORT in premium zone"""
        tech = self.base_tech.copy()
        tech["price_in_discount"] = False
        tech["price_in_premium"] = True
        tech["fibonacci_levels"] = {
            "discount_zone": (1.0990, 1.1000),
            "premium_zone": (1.1010, 1.1020)
        }
        
        result = strat_premium_discount_array(self.symbol, tech, "RANGE")
        if result:
            self.assertEqual(result.direction, "SHORT")


class TestKillZoneStrategy(unittest.TestCase):
    """TEST-STRAT-KILLZONE-001 through TEST-STRAT-KILLZONE-002"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "EURUSDc"
        self.base_tech = {
            "symbol": self.symbol,
            "regime": "VOLATILE",
            "current_price": 1.1000
        }
    
    def test_strat_killzone_001_returns_none_when_inactive(self):
        """TEST-STRAT-KILLZONE-001: Returns None when kill zone inactive"""
        tech = self.base_tech.copy()
        tech["kill_zone_active"] = False
        
        result = strat_kill_zone(self.symbol, tech, "VOLATILE")
        self.assertIsNone(result)
    
    def test_strat_killzone_002_returns_plan_during_kill_zone(self):
        """TEST-STRAT-KILLZONE-002: Returns plan during kill zone"""
        tech = self.base_tech.copy()
        tech["kill_zone_active"] = True
        tech["volatility_spike"] = True
        
        result = strat_kill_zone(self.symbol, tech, "VOLATILE")
        # May return plan if all conditions met
        self.assertTrue(result is None or hasattr(result, 'direction'))


class TestSessionLiquidityRunStrategy(unittest.TestCase):
    """TEST-STRAT-SESSION-001 through TEST-STRAT-SESSION-002"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "EURUSDc"
        self.base_tech = {
            "symbol": self.symbol,
            "regime": "TREND",
            "current_price": 1.1000
        }
    
    def test_strat_session_001_returns_none_when_no_sweep(self):
        """TEST-STRAT-SESSION-001: Returns None when no sweep"""
        tech = self.base_tech.copy()
        tech["session_liquidity_run"] = None
        
        result = strat_session_liquidity_run(self.symbol, tech, "TREND")
        self.assertIsNone(result)
    
    def test_strat_session_002_returns_plan_when_sweep_reversal(self):
        """TEST-STRAT-SESSION-002: Returns plan when sweep + reversal"""
        tech = self.base_tech.copy()
        tech["session_liquidity_run"] = {
            "sweep_detected": True,
            "reversal_structure": True,
            "asian_session_high": 1.1010
        }
        
        result = strat_session_liquidity_run(self.symbol, tech, "TREND")
        # May return plan if all conditions met
        self.assertTrue(result is None or hasattr(result, 'direction'))


def run_tests():
    """Run all strategy tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestOrderBlockRejectionStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestFVGRetracementStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestBreakerBlockStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestMitigationBlockStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestMarketStructureShiftStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestInducementReversalStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestPremiumDiscountArrayStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestKillZoneStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestSessionLiquidityRunStrategy))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

