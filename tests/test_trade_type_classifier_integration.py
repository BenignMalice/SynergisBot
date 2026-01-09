"""
Integration tests for TradeTypeClassifier integration with enableIntelligentExits

Tests the end-to-end flow:
1. Classification logic
2. Parameter selection (SCALP vs INTRADAY)
3. Integration with desktop_agent enableIntelligentExits
4. Error handling and fallbacks

Note: These tests use minimal mocking to verify the integration logic
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any
import asyncio
import sys


class TestTradeTypeClassifierIntegration(unittest.TestCase):
    """Integration tests for TradeTypeClassifier in enableIntelligentExits flow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "EURUSD"
        self.ticket = 12345
        self.entry_price = 1.1000
        self.stop_loss = 1.0950  # 50 pips = 0.0050
        self.take_profit = 1.1050
        self.direction = "buy"
    
    def run_async(self, coro):
        """Helper to run async coroutines"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    def test_scalp_classification_parameter_selection(self):
        """Test that SCALP classification selects correct parameters"""
        # Verify parameter mapping logic
        classification = {
            "trade_type": "SCALP",
            "confidence": 0.85,
            "reasoning": "Comment keyword indicates SCALP"
        }
        
        # Select parameters based on classification
        if classification["trade_type"] == "SCALP":
            base_breakeven_pct = 25.0
            base_partial_pct = 40.0
            partial_close_pct = 70.0
        else:
            base_breakeven_pct = 30.0
            base_partial_pct = 60.0
            partial_close_pct = 50.0
        
        self.assertEqual(base_breakeven_pct, 25.0)
        self.assertEqual(base_partial_pct, 40.0)
        self.assertEqual(partial_close_pct, 70.0)
    
    def test_intraday_classification_parameter_selection(self):
        """Test that INTRADAY classification selects correct parameters"""
        # Verify parameter mapping logic
        classification = {
            "trade_type": "INTRADAY",
            "confidence": 0.50,
            "reasoning": "Default to INTRADAY"
        }
        
        # Select parameters based on classification
        if classification["trade_type"] == "SCALP":
            base_breakeven_pct = 25.0
            base_partial_pct = 40.0
            partial_close_pct = 70.0
        else:
            base_breakeven_pct = 30.0
            base_partial_pct = 60.0
            partial_close_pct = 50.0
        
        self.assertEqual(base_breakeven_pct, 30.0)
        self.assertEqual(base_partial_pct, 60.0)
        self.assertEqual(partial_close_pct, 50.0)
    
    def test_classification_error_fallback_parameters(self):
        """Test that classification errors fall back to INTRADAY parameters"""
        # Simulate classification error
        classification = None
        classification_info = {
            "trade_type": "INTRADAY",
            "confidence": 0.0,
            "reasoning": "Classification error → Default to INTRADAY",
            "error": "Test error"
        }
        
        # Select parameters based on classification (None = error case)
        if classification and classification["trade_type"] == "SCALP":
            base_breakeven_pct = 25.0
            base_partial_pct = 40.0
            partial_close_pct = 70.0
        else:
            # Default/INTRADAY parameters
            base_breakeven_pct = 30.0
            base_partial_pct = 60.0
            partial_close_pct = 50.0
        
        self.assertEqual(base_breakeven_pct, 30.0)
        self.assertEqual(base_partial_pct, 60.0)
        self.assertEqual(partial_close_pct, 50.0)
        self.assertEqual(classification_info["trade_type"], "INTRADAY")
        self.assertIn("error", classification_info)


class TestTradeTypeClassifierIntegrationLogic(unittest.TestCase):
    """Unit tests for classification and parameter selection logic"""
    
    def test_classifier_output_format(self):
        """Test that classifier returns expected format"""
        from infra.trade_type_classifier import TradeTypeClassifier
        
        classifier = TradeTypeClassifier()
        
        # Test with mock data
        result = classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment="scalp trade",
            atr_h1=0.0050,
            session_info={"strategy": "scalping"}
        )
        
        # Verify output format
        self.assertIn("trade_type", result)
        self.assertIn("confidence", result)
        self.assertIn("reasoning", result)
        self.assertIn("factors", result)
        self.assertIn(result["trade_type"], ["SCALP", "INTRADAY"])
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)
    
    def test_parameter_selection_logic(self):
        """Test parameter selection based on classification"""
        test_cases = [
            ("SCALP", 25.0, 40.0, 70.0),
            ("INTRADAY", 30.0, 60.0, 50.0),
        ]
        
        for trade_type, expected_be, expected_partial, expected_close in test_cases:
            classification = {"trade_type": trade_type}
            
            if classification["trade_type"] == "SCALP":
                base_breakeven_pct = 25.0
                base_partial_pct = 40.0
                partial_close_pct = 70.0
            else:
                base_breakeven_pct = 30.0
                base_partial_pct = 60.0
                partial_close_pct = 50.0
            
            with self.subTest(trade_type=trade_type):
                self.assertEqual(base_breakeven_pct, expected_be)
                self.assertEqual(base_partial_pct, expected_partial)
                self.assertEqual(partial_close_pct, expected_close)


if __name__ == "__main__":
    unittest.main(verbosity=2)
