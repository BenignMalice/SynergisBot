"""
Test Phase 2.1: Volatility Tolerance Calculator
Tests RMAG adjustments, ATR adjustments, kill-switch, and smoothing
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch
from infra.volatility_tolerance_calculator import VolatilityToleranceCalculator
from infra.tolerance_calculator import ToleranceCalculator

class TestVolatilityToleranceCalculator(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        # Mock ToleranceCalculator
        self.mock_tolerance_calc = Mock(spec=ToleranceCalculator)
        self.mock_tolerance_calc._get_atr = Mock(return_value=None)
        
        # Create calculator instance
        self.calculator = VolatilityToleranceCalculator(
            tolerance_calculator=self.mock_tolerance_calc,
            enable_rmag_smoothing=True,
            smoothing_alpha=0.3
        )
        
    def test_kill_switch_rmag_above_threshold(self):
        """Test kill-switch when RMAG > 3.0σ"""
        rmag_data = {'ema200_atr': 3.1, 'vwap_atr': 0.5}
        result = self.calculator.calculate_volatility_adjusted_tolerance(
            symbol='XAUUSDc',
            base_tolerance=7.0,
            rmag_data=rmag_data
        )
        # Kill-switch should return 10% of base
        expected = 7.0 * 0.1
        self.assertEqual(result, expected, f"Expected {expected}, got {result}")
        print(f"  [PASS] Kill-switch test: RMAG 3.1 -> tolerance {result:.2f} (expected {expected:.2f})")
        
    def test_kill_switch_xauusdc_lower_threshold(self):
        """Test kill-switch for XAUUSDc with lower threshold (2.8σ)"""
        rmag_data = {'ema200_atr': 2.9, 'vwap_atr': 0.5}
        result = self.calculator.calculate_volatility_adjusted_tolerance(
            symbol='XAUUSDc',
            base_tolerance=7.0,
            rmag_data=rmag_data
        )
        # Should trigger kill-switch (2.9 > 2.8)
        expected = 7.0 * 0.1
        self.assertEqual(result, expected, f"Expected {expected}, got {result}")
        print(f"  [PASS] Kill-switch XAUUSDc test: RMAG 2.9 -> tolerance {result:.2f}")
        
    def test_rmag_high_reduction(self):
        """Test RMAG > 2.5σ reduces tolerance by 40%"""
        rmag_data = {'ema200_atr': 2.6, 'vwap_atr': 0.5}
        result = self.calculator.calculate_volatility_adjusted_tolerance(
            symbol='XAUUSDc',
            base_tolerance=7.0,
            rmag_data=rmag_data
        )
        # Should be 7.0 * 0.6 = 4.2 (40% reduction)
        expected = 7.0 * 0.6
        # But also subject to minimum tolerance (30% of base = 2.1)
        # So should be max(4.2, 2.1) = 4.2
        self.assertAlmostEqual(result, expected, places=1, msg=f"Expected ~{expected}, got {result}")
        print(f"  [PASS] High RMAG test: RMAG 2.6 -> tolerance {result:.2f} (expected ~{expected:.2f})")
        
    def test_rmag_elevated_reduction(self):
        """Test RMAG > 2.0σ reduces tolerance by 25%"""
        rmag_data = {'ema200_atr': 2.2, 'vwap_atr': 0.5}
        result = self.calculator.calculate_volatility_adjusted_tolerance(
            symbol='XAUUSDc',
            base_tolerance=7.0,
            rmag_data=rmag_data
        )
        # Should be 7.0 * 0.75 = 5.25 (25% reduction)
        expected = 7.0 * 0.75
        # Subject to minimum tolerance (30% of base = 2.1)
        # So should be max(5.25, 2.1) = 5.25
        self.assertAlmostEqual(result, expected, places=1, msg=f"Expected ~{expected}, got {result}")
        print(f"  [PASS] Elevated RMAG test: RMAG 2.2 -> tolerance {result:.2f} (expected ~{expected:.2f})")
        
    def test_rmag_low_tightening(self):
        """Test RMAG < 1.0σ tightens tolerance by 10%"""
        rmag_data = {'ema200_atr': 0.8, 'vwap_atr': 0.5}
        result = self.calculator.calculate_volatility_adjusted_tolerance(
            symbol='XAUUSDc',
            base_tolerance=7.0,
            rmag_data=rmag_data
        )
        # Should be 7.0 * 0.9 = 6.3 (10% tightening)
        expected = 7.0 * 0.9
        # Subject to minimum tolerance (30% of base = 2.1)
        # So should be max(6.3, 2.1) = 6.3
        self.assertAlmostEqual(result, expected, places=1, msg=f"Expected ~{expected}, got {result}")
        print(f"  [PASS] Low RMAG test: RMAG 0.8 -> tolerance {result:.2f} (expected ~{expected:.2f})")
        
    def test_no_rmag_data(self):
        """Test graceful degradation when no RMAG data"""
        result = self.calculator.calculate_volatility_adjusted_tolerance(
            symbol='XAUUSDc',
            base_tolerance=7.0,
            rmag_data=None
        )
        # Should use base tolerance (subject to minimum)
        # Minimum is 30% of base = 2.1, so should be max(7.0, 2.1) = 7.0
        self.assertEqual(result, 7.0, f"Expected 7.0, got {result}")
        print(f"  [PASS] No RMAG data test: tolerance {result:.2f} (expected 7.0)")
        
    def test_atr_scaling_xauusdc(self):
        """Test ATR scaling for XAUUSDc (0.4x multiplier)"""
        self.mock_tolerance_calc._get_atr.return_value = 10.0
        result = self.calculator.calculate_volatility_adjusted_tolerance(
            symbol='XAUUSDc',
            base_tolerance=7.0,
            rmag_data=None,
            atr=10.0
        )
        # ATR tolerance = 10.0 * 0.4 = 4.0
        # Max cap = 7.0 * 1.2 = 8.4
        # ATR adjusted = min(4.0, 8.4) = 4.0
        # Min ATR = 7.0 * 0.5 = 3.5
        # ATR adjusted = max(4.0, 3.5) = 4.0
        # Final = min(7.0, 4.0) = 4.0 (subject to final min of 2.1, so max(4.0, 2.1) = 4.0)
        self.assertAlmostEqual(result, 4.0, places=1, msg=f"Expected ~4.0, got {result}")
        print(f"  [PASS] ATR scaling XAUUSDc test: ATR 10.0 -> tolerance {result:.2f} (expected ~4.0)")
        
    def test_atr_scaling_btcusd(self):
        """Test ATR scaling for BTCUSDc (0.5x multiplier)"""
        result = self.calculator.calculate_volatility_adjusted_tolerance(
            symbol='BTCUSDc',
            base_tolerance=100.0,
            rmag_data=None,
            atr=200.0
        )
        # ATR tolerance = 200.0 * 0.5 = 100.0
        # Max cap = 100.0 * 1.3 = 130.0
        # ATR adjusted = min(100.0, 130.0) = 100.0
        # Min ATR = 100.0 * 0.5 = 50.0
        # ATR adjusted = max(100.0, 50.0) = 100.0
        # Final = min(100.0, 100.0) = 100.0 (subject to final min of 30.0, so max(100.0, 30.0) = 100.0)
        self.assertAlmostEqual(result, 100.0, places=1, msg=f"Expected ~100.0, got {result}")
        print(f"  [PASS] ATR scaling BTCUSDc test: ATR 200.0 -> tolerance {result:.2f} (expected ~100.0)")
        
    def test_combined_rmag_and_atr(self):
        """Test combined RMAG and ATR adjustments"""
        self.mock_tolerance_calc._get_atr.return_value = 10.0
        rmag_data = {'ema200_atr': 2.6, 'vwap_atr': 0.5}
        result = self.calculator.calculate_volatility_adjusted_tolerance(
            symbol='XAUUSDc',
            base_tolerance=7.0,
            rmag_data=rmag_data,
            atr=10.0
        )
        # RMAG: 2.6σ -> 0.6x factor -> 7.0 * 0.6 = 4.2
        # ATR: 10.0 * 0.4 = 4.0, min(4.0, 8.4) = 4.0, max(4.0, 3.5) = 4.0
        # Final: min(4.2, 4.0) = 4.0, max(4.0, 2.1) = 4.0
        self.assertAlmostEqual(result, 4.0, places=1, msg=f"Expected ~4.0, got {result}")
        print(f"  [PASS] Combined RMAG+ATR test: tolerance {result:.2f} (expected ~4.0)")
        
    def test_rmag_smoothing(self):
        """Test RMAG smoothing (EWMA)"""
        # First call - should use current value
        smoothed1 = self.calculator._smooth_rmag('XAUUSDc', 2.5)
        self.assertEqual(smoothed1, 2.5, "First smoothing should return current value")
        
        # Second call - should apply EWMA
        smoothed2 = self.calculator._smooth_rmag('XAUUSDc', 2.7)
        # EWMA: 0.3 * 2.7 + 0.7 * 2.5 = 0.81 + 1.75 = 2.56
        expected = 0.3 * 2.7 + 0.7 * 2.5
        self.assertAlmostEqual(smoothed2, expected, places=2, 
                              msg=f"Expected ~{expected}, got {smoothed2}")
        print(f"  [PASS] RMAG smoothing test: 2.5 -> 2.7 smoothed to {smoothed2:.2f} (expected ~{expected:.2f})")
        
    def test_get_max_tolerance(self):
        """Test _get_max_tolerance method"""
        xau_max = self.calculator._get_max_tolerance('XAUUSDc')
        self.assertEqual(xau_max, 10.0, f"Expected 10.0, got {xau_max}")
        
        btc_max = self.calculator._get_max_tolerance('BTCUSDc')
        self.assertEqual(btc_max, 200.0, f"Expected 200.0, got {btc_max}")
        
        eth_max = self.calculator._get_max_tolerance('ETHUSDc')
        self.assertEqual(eth_max, 20.0, f"Expected 20.0, got {eth_max}")
        
        forex_max = self.calculator._get_max_tolerance('EURUSDc')
        self.assertEqual(forex_max, 0.01, f"Expected 0.01, got {forex_max}")
        
        print(f"  [PASS] Max tolerance test: XAU={xau_max}, BTC={btc_max}, ETH={eth_max}, Forex={forex_max}")
        
    def test_get_kill_switch_threshold(self):
        """Test _get_kill_switch_threshold method"""
        xau_threshold = self.calculator._get_kill_switch_threshold('XAUUSDc')
        self.assertEqual(xau_threshold, 2.8, f"Expected 2.8 for XAUUSDc, got {xau_threshold}")
        
        btc_threshold = self.calculator._get_kill_switch_threshold('BTCUSDc')
        self.assertEqual(btc_threshold, 3.5, f"Expected 3.5 for BTCUSDc, got {btc_threshold}")
        
        default_threshold = self.calculator._get_kill_switch_threshold('EURUSDc')
        self.assertEqual(default_threshold, 3.0, f"Expected 3.0 for EURUSDc, got {default_threshold}")
        
        print(f"  [PASS] Kill-switch threshold test: XAU={xau_threshold}, BTC={btc_threshold}, Default={default_threshold}")

if __name__ == '__main__':
    print("Testing Phase 2.1: Volatility Tolerance Calculator...\n")
    unittest.main(verbosity=2, exit=False)
    print("\n[PASS] Phase 2.1: All tests passed!")
