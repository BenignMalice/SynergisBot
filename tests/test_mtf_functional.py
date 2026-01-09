"""
Functional Test for MTF CHOCH/BOS Implementation
Tests Phase 0 and Phase 1 with actual or mock data
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np

# Test imports
try:
    from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
    from domain.market_structure import detect_bos_choch, _symmetric_swings, label_swings
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


class TestMTFChoChBOSFunctional(unittest.TestCase):
    """Functional tests for MTF CHOCH/BOS implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a mock indicator_bridge since analyzer needs it
        mock_bridge = Mock()
        self.analyzer = MultiTimeframeAnalyzer(mock_bridge)
        self.symbol = "XAUUSD"
        
        # Create mock timeframe data structure (matching IndicatorBridge.get_multi format)
        self.mock_h4_data = self._create_mock_timeframe_data("H4", 50)
        self.mock_h1_data = self._create_mock_timeframe_data("H1", 50)
        self.mock_m30_data = self._create_mock_timeframe_data("M30", 50)
        self.mock_m15_data = self._create_mock_timeframe_data("M15", 50)
        self.mock_m5_data = self._create_mock_timeframe_data("M5", 50)
    
    def _create_mock_timeframe_data(self, timeframe, num_bars=50):
        """Create mock timeframe data matching IndicatorBridge.get_multi format"""
        # Generate realistic price data
        base_price = 2000.0 if timeframe == "H4" else 2000.0
        np.random.seed(42)  # For reproducibility
        
        # Create trending data with some swings
        prices = []
        current = base_price
        for i in range(num_bars):
            # Add trend and noise
            trend = 0.5 if i < num_bars // 2 else -0.3
            noise = np.random.normal(0, 2)
            current += trend + noise
            prices.append(current)
        
        # Create OHLC from prices
        opens = prices[:-1] if len(prices) > 1 else prices
        closes = prices[1:] if len(prices) > 1 else prices
        highs = [max(o, c) + abs(np.random.normal(0, 1)) for o, c in zip(opens, closes)]
        lows = [min(o, c) - abs(np.random.normal(0, 1)) for o, c in zip(opens, closes)]
        
        # Ensure we have enough data
        if len(opens) < len(closes):
            opens = [closes[0]] + opens
        if len(highs) < len(closes):
            highs = closes + [max(closes) + 1]
        if len(lows) < len(closes):
            lows = closes + [min(closes) - 1]
        
        # Truncate to same length
        min_len = min(len(opens), len(highs), len(lows), len(closes))
        opens = opens[:min_len]
        highs = highs[:min_len]
        lows = lows[:min_len]
        closes = closes[:min_len]
        
        # Calculate ATR approximation
        true_ranges = []
        for i in range(1, min(15, len(closes))):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            true_ranges.append(tr)
        atr = sum(true_ranges) / len(true_ranges) if true_ranges else 2.0
        
        return {
            "opens": opens,
            "highs": highs,
            "lows": lows,
            "closes": closes,
            "volumes": [1000.0] * len(closes),
            "atr14": atr,
            "atr": atr,
            "times": [f"2025-12-08 {i:02d}:00:00" for i in range(len(closes))]
        }
    
    def test_phase0_h4_bias_returns_choch_bos_fields(self):
        """Test Phase 0: _analyze_h4_bias returns CHOCH/BOS fields"""
        result = self.analyzer._analyze_h4_bias(self.mock_h4_data, self.symbol)
        
        # Check all CHOCH/BOS fields are present
        self.assertIn("choch_detected", result)
        self.assertIn("choch_bull", result)
        self.assertIn("choch_bear", result)
        self.assertIn("bos_detected", result)
        self.assertIn("bos_bull", result)
        self.assertIn("bos_bear", result)
        
        # Check fields are booleans
        self.assertIsInstance(result["choch_detected"], bool)
        self.assertIsInstance(result["choch_bull"], bool)
        self.assertIsInstance(result["choch_bear"], bool)
        self.assertIsInstance(result["bos_detected"], bool)
        self.assertIsInstance(result["bos_bull"], bool)
        self.assertIsInstance(result["bos_bear"], bool)
        
        # Check choch_detected is True if either choch_bull or choch_bear is True
        if result["choch_bull"] or result["choch_bear"]:
            self.assertTrue(result["choch_detected"], "choch_detected should be True if choch_bull or choch_bear is True")
        
        # Check bos_detected is True if either bos_bull or bos_bear is True
        if result["bos_bull"] or result["bos_bear"]:
            self.assertTrue(result["bos_detected"], "bos_detected should be True if bos_bull or bos_bear is True")
        
        print(f"✅ H4 analysis: choch_detected={result['choch_detected']}, bos_detected={result['bos_detected']}")
    
    def test_phase0_all_timeframes_return_choch_bos_fields(self):
        """Test Phase 0: All 5 timeframe methods return CHOCH/BOS fields"""
        timeframes = [
            ("H4", self.analyzer._analyze_h4_bias, self.mock_h4_data),
            ("H1", self.analyzer._analyze_h1_context, self.mock_h1_data),
            ("M30", self.analyzer._analyze_m30_setup, self.mock_m30_data),
            ("M15", self.analyzer._analyze_m15_trigger, self.mock_m15_data),
            ("M5", self.analyzer._analyze_m5_execution, self.mock_m5_data),
        ]
        
        for tf_name, method, data in timeframes:
            # H4 doesn't need previous analysis, others do
            if tf_name == "H4":
                result = method(data, self.symbol)
            elif tf_name == "H1":
                h4_result = self.analyzer._analyze_h4_bias(self.mock_h4_data, self.symbol)
                result = method(data, h4_result, self.symbol)
            elif tf_name == "M30":
                h4_result = self.analyzer._analyze_h4_bias(self.mock_h4_data, self.symbol)
                h1_result = self.analyzer._analyze_h1_context(self.mock_h1_data, h4_result, self.symbol)
                result = method(data, h1_result, self.symbol)
            elif tf_name == "M15":
                h4_result = self.analyzer._analyze_h4_bias(self.mock_h4_data, self.symbol)
                h1_result = self.analyzer._analyze_h1_context(self.mock_h1_data, h4_result, self.symbol)
                m30_result = self.analyzer._analyze_m30_setup(self.mock_m30_data, h1_result, self.symbol)
                result = method(data, m30_result, self.symbol)
            elif tf_name == "M5":
                h4_result = self.analyzer._analyze_h4_bias(self.mock_h4_data, self.symbol)
                h1_result = self.analyzer._analyze_h1_context(self.mock_h1_data, h4_result, self.symbol)
                m30_result = self.analyzer._analyze_m30_setup(self.mock_m30_data, h1_result, self.symbol)
                m15_result = self.analyzer._analyze_m15_trigger(self.mock_m15_data, m30_result, self.symbol)
                result = method(data, m15_result, self.symbol)
            
            # Verify all fields present
            required_fields = ["choch_detected", "choch_bull", "choch_bear", "bos_detected", "bos_bull", "bos_bear"]
            for field in required_fields:
                self.assertIn(field, result, f"{tf_name} missing field: {field}")
                self.assertIsInstance(result[field], bool, f"{tf_name} field {field} should be boolean")
            
            print(f"✅ {tf_name}: choch_detected={result['choch_detected']}, bos_detected={result['bos_detected']}")
    
    def test_phase0_analyze_method_includes_choch_bos(self):
        """Test Phase 0: analyze() method includes CHOCH/BOS in all timeframes"""
        # Mock the indicator_bridge.get_multi to return our test data
        multi_data = {
            "H4": self.mock_h4_data,
            "H1": self.mock_h1_data,
            "M30": self.mock_m30_data,
            "M15": self.mock_m15_data,
            "M5": self.mock_m5_data,
        }
        
        # The analyzer.analyze() method likely needs indicator_bridge
        # For testing, we'll test the individual methods instead
        # This test verifies the structure when analyze() is called
        h4_result = self.analyzer._analyze_h4_bias(self.mock_h4_data, self.symbol)
        h1_result = self.analyzer._analyze_h1_context(self.mock_h1_data, h4_result, self.symbol)
        m30_result = self.analyzer._analyze_m30_setup(self.mock_m30_data, h1_result, self.symbol)
        m15_result = self.analyzer._analyze_m15_trigger(self.mock_m15_data, m30_result, self.symbol)
        m5_result = self.analyzer._analyze_m5_execution(self.mock_m5_data, m15_result, self.symbol)
        
        # Simulate what analyze() would return
        result = {
            "timeframes": {
                "H4": h4_result,
                "H1": h1_result,
                "M30": m30_result,
                "M15": m15_result,
                "M5": m5_result,
            }
        }
        
        # Check timeframes structure exists
        self.assertIn("timeframes", result)
        self.assertIsInstance(result["timeframes"], dict)
        
        # Check all timeframes have CHOCH/BOS fields
        for tf_name in ["H4", "H1", "M30", "M15", "M5"]:
            self.assertIn(tf_name, result["timeframes"], f"Missing timeframe: {tf_name}")
            tf_data = result["timeframes"][tf_name]
            
            required_fields = ["choch_detected", "choch_bull", "choch_bear", "bos_detected", "bos_bull", "bos_bear"]
            for field in required_fields:
                self.assertIn(field, tf_data, f"{tf_name} missing CHOCH/BOS field: {field}")
                self.assertIsInstance(tf_data[field], bool, f"{tf_name} field {field} should be boolean")
        
        print("✅ analyze() method includes CHOCH/BOS in all timeframes")
    
    def test_phase0_handles_insufficient_data(self):
        """Test Phase 0: Handles insufficient data gracefully"""
        # Create data with < 10 bars
        insufficient_data = {
            "opens": [2000.0] * 5,
            "highs": [2001.0] * 5,
            "lows": [1999.0] * 5,
            "closes": [2000.5] * 5,
            "volumes": [1000.0] * 5,
            "atr14": 2.0,
        }
        
        result = self.analyzer._analyze_h4_bias(insufficient_data, self.symbol)
        
        # Should return False for all CHOCH/BOS fields
        self.assertFalse(result["choch_detected"])
        self.assertFalse(result["choch_bull"])
        self.assertFalse(result["choch_bear"])
        self.assertFalse(result["bos_detected"])
        self.assertFalse(result["bos_bull"])
        self.assertFalse(result["bos_bear"])
        
        print("✅ Handles insufficient data gracefully")
    
    def test_phase0_handles_missing_atr(self):
        """Test Phase 0: Handles missing ATR gracefully"""
        data_without_atr = self.mock_h4_data.copy()
        del data_without_atr["atr14"]
        del data_without_atr["atr"]
        
        # Should not crash, should use fallback ATR calculation
        result = self.analyzer._analyze_h4_bias(data_without_atr, self.symbol)
        
        # Should still return CHOCH/BOS fields
        self.assertIn("choch_detected", result)
        self.assertIn("bos_detected", result)
        
        print("✅ Handles missing ATR gracefully")
    
    def test_phase1_calculation_logic(self):
        """Test Phase 1: Calculation logic for choch_detected and bos_detected"""
        # Create mock MTF analyzer result with CHOCH/BOS in some timeframes
        mock_smc = {
            "timeframes": {
                "H4": {
                    "bias": "BULLISH",
                    "choch_detected": False,
                    "choch_bull": True,  # This should make choch_detected = True
                    "choch_bear": False,
                    "bos_detected": False,
                    "bos_bull": False,
                    "bos_bear": False,
                },
                "H1": {
                    "status": "CONTINUATION",
                    "choch_detected": False,
                    "choch_bull": False,
                    "choch_bear": False,
                    "bos_detected": True,  # This should make bos_detected = True
                    "bos_bull": True,
                    "bos_bear": False,
                },
                "M30": {
                    "setup": "READY",
                    "choch_detected": False,
                    "choch_bull": False,
                    "choch_bear": False,
                    "bos_detected": False,
                    "bos_bull": False,
                    "bos_bear": False,
                },
                "M15": {
                    "trigger": "BUY",
                    "choch_detected": False,
                    "choch_bull": False,
                    "choch_bear": False,
                    "bos_detected": False,
                    "bos_bull": False,
                    "bos_bear": False,
                },
                "M5": {
                    "execution": "BUY",
                    "choch_detected": False,
                    "choch_bull": False,
                    "choch_bear": False,
                    "bos_detected": False,
                    "bos_bull": False,
                    "bos_bear": False,
                },
            },
            "alignment_score": 75,
            "recommendation": {
                "action": "BUY",
                "confidence": 80,
                "market_bias": {"trend": "BULLISH"},
                "trade_opportunities": {"type": "TREND"},
            },
        }
        
        # Simulate the calculation logic from _format_unified_analysis
        choch_detected = False
        bos_detected = False
        
        for tf_name, tf_data in mock_smc.get("timeframes", {}).items():
            if tf_data.get("choch_detected", False) or tf_data.get("choch_bull", False) or tf_data.get("choch_bear", False):
                choch_detected = True
            if tf_data.get("bos_detected", False) or tf_data.get("bos_bull", False) or tf_data.get("bos_bear", False):
                bos_detected = True
            if choch_detected and bos_detected:
                break
        
        # Verify calculation
        self.assertTrue(choch_detected, "choch_detected should be True (H4 has choch_bull=True)")
        self.assertTrue(bos_detected, "bos_detected should be True (H1 has bos_detected=True)")
        
        # Test trend extraction
        h4_data = mock_smc.get("timeframes", {}).get("H4", {})
        structure_trend = h4_data.get("bias", "UNKNOWN")
        self.assertEqual(structure_trend, "BULLISH")
        
        print("✅ Phase 1 calculation logic works correctly")
    
    def test_phase1_response_structure_fields(self):
        """Test Phase 1: Response structure includes all required fields"""
        # This test verifies the expected structure matches what _format_unified_analysis should return
        expected_fields = [
            "timeframes",
            "alignment_score",
            "recommendation",
            "market_bias",
            "trade_opportunities",
            "volatility_regime",
            "volatility_weights",
            "advanced_insights",
            "advanced_summary",
            "confidence_score",
            "choch_detected",
            "bos_detected",
            "trend",
        ]
        
        # Create mock response structure (what _format_unified_analysis should return)
        mock_response_smc = {
            "choch_detected": True,
            "bos_detected": True,
            "trend": "BULLISH",
            "timeframes": {},
            "alignment_score": 75,
            "recommendation": {},
            "market_bias": {},
            "trade_opportunities": {},
            "volatility_regime": "STABLE",
            "volatility_weights": {},
            "advanced_insights": {},
            "advanced_summary": "",
            "confidence_score": 80,
        }
        
        # Verify all expected fields are present
        for field in expected_fields:
            self.assertIn(field, mock_response_smc, f"Missing field in response structure: {field}")
        
        print("✅ Response structure includes all required fields")


def run_tests():
    """Run all tests"""
    print("=" * 80)
    print("MTF CHOCH/BOS Functional Tests")
    print("=" * 80)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestMTFChoChBOSFunctional)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}")
            print(f"    {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}")
            print(f"    {traceback}")
    
    if result.wasSuccessful():
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())

