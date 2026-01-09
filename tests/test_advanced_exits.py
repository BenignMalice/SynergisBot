"""
Unit tests for Advanced-Enhanced Intelligent Exits
Tests the _calculate_advanced_triggers() logic with various market scenarios
"""

import unittest
from infra.intelligent_exit_manager import IntelligentExitManager


class TestAdvancedEnhancedExits(unittest.TestCase):
    """Test Advanced-enhanced intelligent exit trigger calculations"""
    
    def setUp(self):
        """Create a mock manager for testing (no MT5 service needed)"""
        self.manager = IntelligentExitManager.__new__(IntelligentExitManager)
    
    def test_extreme_stretch_tightens_triggers(self):
        """Test: RMAG stretched -5.5σ should TIGHTEN to 20%/40%"""
        advanced_features = {
            "rmag": {"ema200_atr": -5.5, "vwap_atr": -2.1},
            "ema_slope": {"ema50": -0.08, "ema200": -0.02},
            "vol_trend": {"state": "expansion_weak_trend"},
            "pressure": {"is_fake": False},
            "mtf_score": {"score": 1},
            "liquidity": {"pdl_dist_atr": 5.0, "pdh_dist_atr": 5.0, "equal_highs": False, "equal_lows": False},
            "vwap_dev": {"zone": "inside"}
        }
        
        result = self.manager._calculate_advanced_triggers(advanced_features)
        
        self.assertEqual(result["breakeven_pct"], 20.0, "Extreme stretch should tighten to 20%")
        self.assertEqual(result["partial_pct"], 40.0, "Extreme stretch should tighten to 40%")
        self.assertIn("rmag_stretched", result["advanced_factors"])
        self.assertIn("RMAG stretched", result["reasoning"])
    
    def test_quality_trend_widens_triggers(self):
        """Test: Quality trend + MTF alignment should WIDEN to 40%/80%"""
        advanced_features = {
            "rmag": {"ema200_atr": 0.8, "vwap_atr": 0.5},
            "ema_slope": {"ema50": 0.22, "ema200": 0.08},
            "vol_trend": {"state": "expansion_strong_trend"},
            "pressure": {"is_fake": False},
            "mtf_score": {"score": 3},
            "liquidity": {"pdl_dist_atr": 5.0, "pdh_dist_atr": 5.0, "equal_highs": False, "equal_lows": False},
            "vwap_dev": {"zone": "inside"}
        }
        
        result = self.manager._calculate_advanced_triggers(advanced_features)
        
        self.assertEqual(result["breakeven_pct"], 40.0, "Quality trend + MTF should widen to 40%")
        self.assertEqual(result["partial_pct"], 80.0, "Quality trend + MTF should widen to 80%")
        self.assertIn("quality_trend", result["advanced_factors"])
        self.assertIn("mtf_aligned", result["advanced_factors"])
    
    def test_fake_momentum_tightens(self):
        """Test: Fake momentum (high RSI + weak ADX) should TIGHTEN to 20%/40%"""
        advanced_features = {
            "rmag": {"ema200_atr": 0.3, "vwap_atr": 0.2},
            "ema_slope": {"ema50": 0.05, "ema200": 0.02},
            "vol_trend": {"state": "expansion_weak_trend"},
            "pressure": {"is_fake": True},
            "mtf_score": {"score": 1},
            "liquidity": {"pdl_dist_atr": 5.0, "pdh_dist_atr": 5.0, "equal_highs": False, "equal_lows": False},
            "vwap_dev": {"zone": "inside"}
        }
        
        result = self.manager._calculate_advanced_triggers(advanced_features)
        
        self.assertEqual(result["breakeven_pct"], 20.0, "Fake momentum should tighten to 20%")
        self.assertEqual(result["partial_pct"], 40.0, "Fake momentum should tighten to 40%")
        self.assertIn("fake_momentum", result["advanced_factors"])
    
    def test_liquidity_zone_tightens(self):
        """Test: Near liquidity zone (PDL/PDH) should TIGHTEN to 25%/50%"""
        advanced_features = {
            "rmag": {"ema200_atr": 0.3, "vwap_atr": 0.2},
            "ema_slope": {"ema50": 0.05, "ema200": 0.02},
            "vol_trend": {"state": "expansion_weak_trend"},
            "pressure": {"is_fake": False},
            "mtf_score": {"score": 1},
            "liquidity": {"pdl_dist_atr": 0.3, "pdh_dist_atr": 5.0, "equal_highs": False, "equal_lows": False},
            "vwap_dev": {"zone": "inside"}
        }
        
        result = self.manager._calculate_advanced_triggers(advanced_features)
        
        self.assertEqual(result["breakeven_pct"], 25.0, "Near liquidity should tighten to 25%")
        self.assertEqual(result["partial_pct"], 50.0, "Near liquidity should tighten to 50%")
        self.assertIn("liquidity_risk", result["advanced_factors"])
    
    def test_equal_highs_lows_tightens(self):
        """Test: Equal highs/lows detected should TIGHTEN to 25%/50%"""
        advanced_features = {
            "rmag": {"ema200_atr": 0.3, "vwap_atr": 0.2},
            "ema_slope": {"ema50": 0.05, "ema200": 0.02},
            "vol_trend": {"state": "expansion_weak_trend"},
            "pressure": {"is_fake": False},
            "mtf_score": {"score": 1},
            "liquidity": {"pdl_dist_atr": 5.0, "pdh_dist_atr": 5.0, "equal_highs": True, "equal_lows": False},
            "vwap_dev": {"zone": "inside"}
        }
        
        result = self.manager._calculate_advanced_triggers(advanced_features)
        
        self.assertEqual(result["breakeven_pct"], 25.0, "Equal highs should tighten to 25%")
        self.assertEqual(result["partial_pct"], 50.0, "Equal highs should tighten to 50%")
        self.assertIn("liquidity_risk", result["advanced_factors"])
    
    def test_squeeze_tightens(self):
        """Test: Volatility squeeze should TIGHTEN to 25%/50%"""
        advanced_features = {
            "rmag": {"ema200_atr": 0.3, "vwap_atr": 0.2},
            "ema_slope": {"ema50": 0.05, "ema200": 0.02},
            "vol_trend": {"state": "squeeze_no_trend"},
            "pressure": {"is_fake": False},
            "mtf_score": {"score": 1},
            "liquidity": {"pdl_dist_atr": 5.0, "pdh_dist_atr": 5.0, "equal_highs": False, "equal_lows": False},
            "vwap_dev": {"zone": "inside"}
        }
        
        result = self.manager._calculate_advanced_triggers(advanced_features)
        
        self.assertEqual(result["breakeven_pct"], 25.0, "Squeeze should tighten to 25%")
        self.assertEqual(result["partial_pct"], 50.0, "Squeeze should tighten to 50%")
        self.assertIn("squeeze", result["advanced_factors"])
    
    def test_vwap_outer_zone_tightens(self):
        """Test: Outer VWAP zone should TIGHTEN to 25%/45%"""
        advanced_features = {
            "rmag": {"ema200_atr": 0.3, "vwap_atr": 0.2},
            "ema_slope": {"ema50": 0.05, "ema200": 0.02},
            "vol_trend": {"state": "expansion_weak_trend"},
            "pressure": {"is_fake": False},
            "mtf_score": {"score": 1},
            "liquidity": {"pdl_dist_atr": 5.0, "pdh_dist_atr": 5.0, "equal_highs": False, "equal_lows": False},
            "vwap_dev": {"zone": "outer"}
        }
        
        result = self.manager._calculate_advanced_triggers(advanced_features)
        
        self.assertEqual(result["breakeven_pct"], 25.0, "Outer VWAP zone should tighten to 25%")
        self.assertEqual(result["partial_pct"], 45.0, "Outer VWAP zone should tighten to 45%")
        self.assertIn("vwap_outer", result["advanced_factors"])
    
    def test_normal_market_no_adjustment(self):
        """Test: Normal market conditions should use standard 30%/60%"""
        advanced_features = {
            "rmag": {"ema200_atr": 0.3, "vwap_atr": 0.2},
            "ema_slope": {"ema50": 0.05, "ema200": 0.02},
            "vol_trend": {"state": "expansion_weak_trend"},
            "pressure": {"is_fake": False},
            "mtf_score": {"score": 1},
            "liquidity": {"pdl_dist_atr": 5.0, "pdh_dist_atr": 5.0, "equal_highs": False, "equal_lows": False},
            "vwap_dev": {"zone": "inside"}
        }
        
        result = self.manager._calculate_advanced_triggers(advanced_features)
        
        self.assertEqual(result["breakeven_pct"], 30.0, "Normal conditions should use 30%")
        self.assertEqual(result["partial_pct"], 60.0, "Normal conditions should use 60%")
        self.assertEqual(len(result["advanced_factors"]), 0, "No V8 factors should be applied")
        self.assertIn("No Advanced adjustments needed", result["reasoning"])
    
    def test_no_advanced_features_fallback(self):
        """Test: No Advanced features should fallback to standard triggers"""
        result = self.manager._calculate_advanced_triggers(advanced_features=None)
        
        self.assertEqual(result["breakeven_pct"], 30.0, "Should fallback to 30%")
        self.assertEqual(result["partial_pct"], 60.0, "Should fallback to 60%")
        self.assertIn("No Advanced features available", result["reasoning"])
    
    def test_multiple_tightening_factors(self):
        """Test: Multiple tightening factors should all apply (most restrictive wins)"""
        advanced_features = {
            "rmag": {"ema200_atr": -5.5, "vwap_atr": -2.1},  # TIGHTEN to 20/40
            "ema_slope": {"ema50": -0.08, "ema200": -0.02},
            "vol_trend": {"state": "squeeze_no_trend"},  # TIGHTEN to 25/50
            "pressure": {"is_fake": True},  # TIGHTEN to 20/40
            "mtf_score": {"score": 1},
            "liquidity": {"pdl_dist_atr": 0.3, "pdh_dist_atr": 5.0, "equal_highs": False, "equal_lows": False},  # TIGHTEN to 25/50
            "vwap_dev": {"zone": "outer"}  # TIGHTEN to 25/45
        }
        
        result = self.manager._calculate_advanced_triggers(advanced_features)
        
        # RMAG and fake momentum should dominate (most restrictive: 20/40)
        self.assertEqual(result["breakeven_pct"], 20.0, "Most restrictive should win (20%)")
        self.assertEqual(result["partial_pct"], 40.0, "Most restrictive should win (40%)")
        self.assertGreaterEqual(len(result["advanced_factors"]), 2, "Multiple factors should be detected")
    
    def test_nested_advanced_insights_structure(self):
        """Test: Handle Advanced features from v8_insights → timeframes → M15"""
        advanced_features = {
            "v8_insights": {
                "timeframes": {
                    "M15": {
                        "rmag": {"ema200_atr": -5.5, "vwap_atr": -2.1},
                        "ema_slope": {"ema50": -0.08, "ema200": -0.02},
                        "vol_trend": {"state": "expansion_weak_trend"},
                        "pressure": {"is_fake": False},
                        "mtf_score": {"score": 1},
                        "liquidity": {"pdl_dist_atr": 5.0, "pdh_dist_atr": 5.0, "equal_highs": False, "equal_lows": False},
                        "vwap_dev": {"zone": "inside"}
                    }
                }
            }
        }
        
        result = self.manager._calculate_advanced_triggers(advanced_features)
        
        self.assertEqual(result["breakeven_pct"], 20.0, "Should extract from nested structure")
        self.assertEqual(result["partial_pct"], 40.0, "Should extract from nested structure")
        self.assertIn("rmag_stretched", result["advanced_factors"])


if __name__ == "__main__":
    print("🧪 Testing Advanced-Enhanced Intelligent Exits...")
    print("=" * 60)
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestV8EnhancedExits)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ ALL V8 EXIT TESTS PASSED!")
        print(f"   {result.testsRun} tests executed successfully")
        print("\n🚀 Advanced-Enhanced Intelligent Exits are READY for production!")
    else:
        print(f"❌ {len(result.failures)} test(s) failed")
        print(f"❌ {len(result.errors)} test(s) had errors")

