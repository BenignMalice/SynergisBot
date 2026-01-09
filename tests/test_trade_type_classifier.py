"""
Unit tests for TradeTypeClassifier

Tests classification logic:
- Keyword matching (case-insensitive)
- Stop/ATR ratio calculations
- Session strategy matching
- Priority order (keyword > stop size > session)
- Manual override patterns
- Default behavior (ambiguous → INTRADAY)
- Edge cases
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from infra.trade_type_classifier import TradeTypeClassifier


class TestTradeTypeClassifier(unittest.TestCase):
    """Test cases for TradeTypeClassifier"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.classifier = TradeTypeClassifier()
        
        # Sample session info for testing
        self.scalp_session = {
            "name": "Asian Session",
            "strategy": "scalping",
            "volatility": "low"
        }
        
        self.intraday_session = {
            "name": "London Session",
            "strategy": "trend_following",
            "volatility": "high"
        }
        
        self.breakout_session = {
            "name": "London/NY Overlap",
            "strategy": "breakout_and_trend",
            "volatility": "very_high"
        }
        
        # Sample ATR H1 value (in price units, same as entry/stop)
        # For EURUSD: 50 pips = 0.0050 in price units
        self.atr_h1 = 0.0050  # 50 pips for EURUSD
    
    # ==================== Manual Override Tests ====================
    
    def test_manual_override_force_scalp(self):
        """Test manual override !force:scalp"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment="!force:scalp",
            atr_h1=self.atr_h1,
            session_info=self.intraday_session
        )
        
        self.assertEqual(result["trade_type"], "SCALP")
        self.assertEqual(result["confidence"], 1.0)
        self.assertTrue(result["factors"]["manual_override"])
        self.assertEqual(result["factors"]["override_type"], "scalp")
    
    def test_manual_override_force_scalp_uppercase(self):
        """Test manual override !force:SCALP (uppercase)"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment="Quick trade !force:SCALP",
            atr_h1=self.atr_h1,
            session_info=self.intraday_session
        )
        
        self.assertEqual(result["trade_type"], "SCALP")
        self.assertEqual(result["confidence"], 1.0)
    
    def test_manual_override_force_intraday(self):
        """Test manual override !force:intraday"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment="!force:intraday",
            atr_h1=self.atr_h1,
            session_info=self.scalp_session
        )
        
        self.assertEqual(result["trade_type"], "INTRADAY")
        self.assertEqual(result["confidence"], 1.0)
        self.assertTrue(result["factors"]["manual_override"])
        self.assertEqual(result["factors"]["override_type"], "intraday")
    
    # ==================== Keyword Matching Tests ====================
    
    def test_scalp_keyword_match(self):
        """Test SCALP keyword detection"""
        test_cases = [
            "scalp trade",
            "SCALPING opportunity",
            "Quick scalp",
            "micro trade",
            "fast exit",
            "rapid scalping"
        ]
        
        for comment in test_cases:
            with self.subTest(comment=comment):
                result = self.classifier.classify(
                    symbol="EURUSD",
                    entry_price=1.1000,
                    stop_loss=1.0950,
                    comment=comment,
                    atr_h1=self.atr_h1,
                    session_info=self.intraday_session
                )
                
                self.assertEqual(result["trade_type"], "SCALP", f"Failed for: {comment}")
                self.assertEqual(result["factors"]["comment_match"], "scalp")
                self.assertGreaterEqual(result["confidence"], 0.85)
    
    def test_intraday_keyword_match(self):
        """Test INTRADAY keyword detection"""
        test_cases = [
            "swing trade",
            "INTRADAY hold",
            "position trade",
            "trend following",
            "let it run",
            "daily target"
        ]
        
        for comment in test_cases:
            with self.subTest(comment=comment):
                result = self.classifier.classify(
                    symbol="EURUSD",
                    entry_price=1.1000,
                    stop_loss=1.0950,
                    comment=comment,
                    atr_h1=self.atr_h1,
                    session_info=self.scalp_session
                )
                
                self.assertEqual(result["trade_type"], "INTRADAY", f"Failed for: {comment}")
                self.assertEqual(result["factors"]["comment_match"], "intraday")
                self.assertGreaterEqual(result["confidence"], 0.85)
    
    def test_keyword_priority_over_stop_size(self):
        """Test that keywords override stop size classification"""
        # Stop size suggests SCALP (0.8× ATR)
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0960,  # 40 pips = 0.8× ATR (50 pips)
            comment="swing trade",  # Keyword suggests INTRADAY
            atr_h1=self.atr_h1,
            session_info=self.scalp_session
        )
        
        # Keyword should win (higher priority)
        self.assertEqual(result["trade_type"], "INTRADAY")
        self.assertEqual(result["factors"]["comment_match"], "intraday")
    
    # ==================== Stop Size vs ATR Tests ====================
    
    def test_stop_size_scalp_threshold(self):
        """Test stop size ≤ 1.0× ATR classified as SCALP"""
        # Stop = 50 pips (0.0050), ATR = 50 pips (0.0050) → 1.0× ATR (threshold)
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,  # 50 pips = 0.0050
            comment=None,
            atr_h1=0.0050,  # 50 pips = 0.0050 (price units)
            session_info=None
        )
        
        self.assertEqual(result["trade_type"], "SCALP")
        self.assertAlmostEqual(result["factors"]["stop_atr_ratio"], 1.0, places=2)
        self.assertGreaterEqual(result["confidence"], 0.70)
    
    def test_stop_size_scalp_below_threshold(self):
        """Test stop size < 1.0× ATR classified as SCALP"""
        # Stop = 40 pips (0.0040), ATR = 50 pips (0.0050) → 0.8× ATR
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0960,  # 40 pips = 0.0040
            comment=None,
            atr_h1=0.0050,  # 50 pips = 0.0050 (price units)
            session_info=None
        )
        
        self.assertEqual(result["trade_type"], "SCALP")
        self.assertAlmostEqual(result["factors"]["stop_atr_ratio"], 0.8, places=2)
        self.assertGreaterEqual(result["confidence"], 0.70)
    
    def test_stop_size_intraday_above_threshold(self):
        """Test stop size > 1.0× ATR classified as INTRADAY"""
        # Stop = 100 pips (0.0100), ATR = 50 pips (0.0050) → 2.0× ATR
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0900,  # 100 pips = 0.0100
            comment=None,
            atr_h1=0.0050,  # 50 pips = 0.0050 (price units)
            session_info=None
        )
        
        self.assertEqual(result["trade_type"], "INTRADAY")
        self.assertAlmostEqual(result["factors"]["stop_atr_ratio"], 2.0, places=2)
        self.assertGreaterEqual(result["confidence"], 0.70)
    
    def test_stop_size_sell_trade(self):
        """Test stop size calculation for SELL trades"""
        # SELL: entry = 1.1000, stop = 1.1050 (50 pips above = 0.0050)
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.1050,  # Stop above entry (SELL trade) = 0.0050
            comment=None,
            atr_h1=0.0050,  # 50 pips = 0.0050 (price units)
            session_info=None
        )
        
        self.assertEqual(result["trade_type"], "SCALP")  # 1.0× ATR = threshold
        self.assertAlmostEqual(result["factors"]["stop_atr_ratio"], 1.0, places=2)
    
    # ==================== Session Strategy Tests ====================
    
    def test_session_strategy_scalping(self):
        """Test session strategy 'scalping' classified as SCALP"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment=None,
            atr_h1=None,  # No ATR
            session_info=self.scalp_session
        )
        
        self.assertEqual(result["trade_type"], "SCALP")
        self.assertEqual(result["factors"]["session_strategy"], "scalping")
        self.assertGreaterEqual(result["confidence"], 0.65)
    
    def test_session_strategy_trend_following(self):
        """Test session strategy 'trend_following' classified as INTRADAY"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment=None,
            atr_h1=None,  # No ATR
            session_info=self.intraday_session
        )
        
        self.assertEqual(result["trade_type"], "INTRADAY")
        self.assertEqual(result["factors"]["session_strategy"], "trend_following")
        self.assertGreaterEqual(result["confidence"], 0.65)
    
    def test_session_strategy_breakout(self):
        """Test session strategy 'breakout_and_trend' classified as INTRADAY"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment=None,
            atr_h1=None,
            session_info=self.breakout_session
        )
        
        self.assertEqual(result["trade_type"], "INTRADAY")
        self.assertEqual(result["factors"]["session_strategy"], "breakout_and_trend")
    
    def test_session_strategy_range_trading(self):
        """Test session strategy 'range_trading' classified as SCALP"""
        range_session = {
            "name": "Range Session",
            "strategy": "range_trading",
            "volatility": "low"
        }
        
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment=None,
            atr_h1=None,
            session_info=range_session
        )
        
        self.assertEqual(result["trade_type"], "SCALP")
        self.assertEqual(result["factors"]["session_strategy"], "range_trading")
    
    # ==================== Priority Order Tests ====================
    
    def test_priority_keyword_overrides_all(self):
        """Test keyword has highest priority"""
        # Stop suggests INTRADAY (2.0× ATR), session suggests INTRADAY
        # But keyword suggests SCALP → should be SCALP
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0900,  # 100 pips = 0.0100 = 2.0× ATR (INTRADAY)
            comment="scalp trade",  # Keyword (SCALP) - should win
            atr_h1=0.0050,  # 50 pips = 0.0050 (price units)
            session_info=self.intraday_session  # INTRADAY session
        )
        
        self.assertEqual(result["trade_type"], "SCALP")
        self.assertEqual(result["factors"]["comment_match"], "scalp")
    
    def test_priority_stop_over_session(self):
        """Test stop size has priority over session"""
        # Session suggests SCALP, but stop suggests INTRADAY (2.0× ATR)
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0900,  # 100 pips = 0.0100 = 2.0× ATR (INTRADAY)
            comment=None,  # No keyword
            atr_h1=0.0050,  # 50 pips = 0.0050 (price units)
            session_info=self.scalp_session  # SCALP session
        )
        
        self.assertEqual(result["trade_type"], "INTRADAY")
        self.assertAlmostEqual(result["factors"]["stop_atr_ratio"], 2.0, places=2)
    
    # ==================== Default Behavior Tests ====================
    
    @patch.object(TradeTypeClassifier, '_fetch_atr_h1', return_value=None)
    @patch.object(TradeTypeClassifier, '_fetch_session_info', return_value=None)
    def test_default_intraday_when_ambiguous(self, mock_session, mock_atr):
        """Test default to INTRADAY when all factors are ambiguous"""
        # No keyword, no ATR, no session info
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment=None,
            atr_h1=None,
            session_info=None
        )
        
        self.assertEqual(result["trade_type"], "INTRADAY")
        self.assertEqual(result["confidence"], 0.50)
        self.assertIn("Default", result["reasoning"])
    
    @patch.object(TradeTypeClassifier, '_fetch_session_info', return_value=None)
    def test_default_intraday_invalid_stop(self, mock_session):
        """Test default to INTRADAY when stop size is invalid"""
        # Invalid: stop = entry (zero stop size)
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.1000,  # Same as entry (invalid)
            comment=None,
            atr_h1=0.0050,  # Won't be used since stop is invalid
            session_info=None
        )
        
        self.assertEqual(result["trade_type"], "INTRADAY")
    
    # ==================== Edge Case Tests ====================
    
    def test_missing_atr_data(self):
        """Test classification when ATR is unavailable"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment=None,
            atr_h1=None,  # ATR unavailable
            session_info=self.scalp_session
        )
        
        # Should use session strategy
        self.assertEqual(result["trade_type"], "SCALP")
        self.assertIsNone(result["factors"]["stop_atr_ratio"])
    
    def test_missing_session_data(self):
        """Test classification when session info is unavailable"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0960,  # 40 pips = 0.0040 = 0.8× ATR (SCALP)
            comment=None,
            atr_h1=0.0050,  # 50 pips = 0.0050 (price units)
            session_info=None  # Session unavailable
        )
        
        # Should use stop size
        self.assertEqual(result["trade_type"], "SCALP")
        self.assertIsNone(result["factors"]["session_strategy"])
    
    def test_missing_comment(self):
        """Test classification when comment is None"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0960,  # 40 pips = 0.0040 = 0.8× ATR (SCALP)
            comment=None,
            atr_h1=0.0050,  # 50 pips = 0.0050 (price units)
            session_info=self.scalp_session
        )
        
        # Should use stop size or session
        self.assertIn(result["trade_type"], ["SCALP", "INTRADAY"])
        self.assertIsNone(result["factors"]["comment_match"])
    
    def test_empty_comment_string(self):
        """Test classification with empty comment string"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0960,  # 40 pips = 0.0040 = 0.8× ATR
            comment="",  # Empty string
            atr_h1=0.0050,  # 50 pips = 0.0050 (price units)
            session_info=self.scalp_session
        )
        
        self.assertIn(result["trade_type"], ["SCALP", "INTRADAY"])
        self.assertIsNone(result["factors"]["comment_match"])
    
    def test_zero_atr_handling(self):
        """Test handling when ATR is zero"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment=None,
            atr_h1=0.0,  # Zero ATR (invalid)
            session_info=self.scalp_session
        )
        
        # Should fall back to session
        self.assertEqual(result["trade_type"], "SCALP")
        self.assertIsNone(result["factors"]["stop_atr_ratio"])
    
    def test_negative_atr_handling(self):
        """Test handling when ATR is negative"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment=None,
            atr_h1=-10.0,  # Negative ATR (invalid)
            session_info=self.scalp_session
        )
        
        # Should fall back to session
        self.assertEqual(result["trade_type"], "SCALP")
    
    @patch.object(TradeTypeClassifier, '_fetch_atr_h1', return_value=None)
    @patch.object(TradeTypeClassifier, '_fetch_session_info', return_value=None)
    def test_error_handling_graceful_degradation(self, mock_session, mock_atr):
        """Test that errors result in safe INTRADAY fallback"""
        # Cause error by passing invalid symbol that might fail ATR fetch
        result = self.classifier.classify(
            symbol="INVALID_SYMBOL_12345",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment=None,
            atr_h1=None,  # Will try to fetch (mocked to return None)
            session_info=None  # Will try to fetch (mocked to return None)
        )
        
        # Should default to INTRADAY on error/ambiguous
        self.assertEqual(result["trade_type"], "INTRADAY")
        self.assertEqual(result["confidence"], 0.50)
    
    # ==================== Confidence Score Tests ====================
    
    def test_confidence_manual_override(self):
        """Test confidence score for manual override"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment="!force:scalp",
            atr_h1=self.atr_h1,
            session_info=self.intraday_session
        )
        
        self.assertEqual(result["confidence"], 1.0)
    
    def test_confidence_keyword_match(self):
        """Test confidence score for keyword match"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment="scalp trade",
            atr_h1=self.atr_h1,
            session_info=self.intraday_session
        )
        
        self.assertGreaterEqual(result["confidence"], 0.85)
        self.assertLessEqual(result["confidence"], 1.0)
    
    def test_confidence_stop_size(self):
        """Test confidence score for stop size classification"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0960,  # 40 pips = 0.0040 = 0.8× ATR
            comment=None,
            atr_h1=0.0050,  # 50 pips = 0.0050 (price units)
            session_info=None
        )
        
        self.assertGreaterEqual(result["confidence"], 0.70)
        self.assertLessEqual(result["confidence"], 0.75)
    
    def test_confidence_session_strategy(self):
        """Test confidence score for session strategy"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment=None,
            atr_h1=None,
            session_info=self.scalp_session
        )
        
        self.assertGreaterEqual(result["confidence"], 0.65)
        self.assertLessEqual(result["confidence"], 0.70)
    
    @patch.object(TradeTypeClassifier, '_fetch_atr_h1', return_value=None)
    @patch.object(TradeTypeClassifier, '_fetch_session_info', return_value=None)
    def test_confidence_default(self, mock_session, mock_atr):
        """Test confidence score for default fallback"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment=None,
            atr_h1=None,
            session_info=None
        )
        
        self.assertEqual(result["confidence"], 0.50)
    
    # ==================== Reasoning Tests ====================
    
    def test_reasoning_includes_keyword(self):
        """Test that reasoning explains keyword-based classification"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment="scalp trade",
            atr_h1=self.atr_h1,
            session_info=self.intraday_session
        )
        
        self.assertIn("keyword", result["reasoning"].lower())
        self.assertIn("scalp", result["reasoning"].lower())
    
    def test_reasoning_includes_stop_size(self):
        """Test that reasoning explains stop size-based classification"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0960,  # 40 pips = 0.0040 = 0.8× ATR
            comment=None,
            atr_h1=0.0050,  # 50 pips = 0.0050 (price units)
            session_info=None
        )
        
        self.assertIn("atr", result["reasoning"].lower())
        # Check that ratio is included (could be 0.80 or 0.8 depending on formatting)
        self.assertTrue("0.8" in result["reasoning"] or "0.80" in result["reasoning"])
    
    def test_reasoning_includes_session(self):
        """Test that reasoning explains session-based classification"""
        result = self.classifier.classify(
            symbol="EURUSD",
            entry_price=1.1000,
            stop_loss=1.0950,
            comment=None,
            atr_h1=None,
            session_info=self.scalp_session
        )
        
        self.assertIn("session", result["reasoning"].lower())
        self.assertIn("scalp", result["reasoning"].lower())


if __name__ == "__main__":
    unittest.main()

