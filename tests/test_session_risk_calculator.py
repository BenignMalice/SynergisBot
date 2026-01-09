"""
Unit tests for Session Risk Calculator
"""

import unittest
from unittest.mock import Mock
from datetime import datetime, timezone, timedelta

# Import the calculator
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.session_risk_calculator import (
    calculate_session_risk,
    _calculate_rollover_window,
    _calculate_news_risk,
    _create_default_response
)


class TestSessionRiskCalculator(unittest.TestCase):
    """Test cases for Session Risk Calculator"""
    
    def test_calculate_rollover_window_not_in_window(self):
        """Test rollover window calculation when not in window"""
        # Test at 14:30 UTC (not in rollover window)
        current_time = datetime(2025, 12, 11, 14, 30, 0, tzinfo=timezone.utc)
        result = _calculate_rollover_window(current_time)
        
        self.assertFalse(result["is_rollover_window"])
        self.assertIn("rollover_window_start", result)
        self.assertIn("rollover_window_end", result)
    
    def test_calculate_rollover_window_in_window(self):
        """Test rollover window calculation when in window"""
        # Test at 00:15 UTC (in rollover window)
        current_time = datetime(2025, 12, 11, 0, 15, 0, tzinfo=timezone.utc)
        result = _calculate_rollover_window(current_time)
        
        self.assertTrue(result["is_rollover_window"])
    
    def test_calculate_rollover_window_at_start(self):
        """Test rollover window at start boundary"""
        # Test at 23:30 UTC (start of rollover window)
        current_time = datetime(2025, 12, 10, 23, 30, 0, tzinfo=timezone.utc)
        result = _calculate_rollover_window(current_time)
        
        self.assertTrue(result["is_rollover_window"])
    
    def test_calculate_rollover_window_at_end(self):
        """Test rollover window at end boundary"""
        # Test at 00:30 UTC (end of rollover window)
        current_time = datetime(2025, 12, 11, 0, 30, 0, tzinfo=timezone.utc)
        result = _calculate_rollover_window(current_time)
        
        self.assertTrue(result["is_rollover_window"])
    
    def test_calculate_news_risk_no_service(self):
        """Test news risk calculation when service not available"""
        result = _calculate_news_risk(None, datetime.now(timezone.utc))
        
        self.assertFalse(result["is_news_lock_active"])
        self.assertIsNone(result["minutes_to_next_high_impact"])
        self.assertFalse(result["is_in_high_impact_window"])
    
    def test_calculate_news_risk_no_events(self):
        """Test news risk calculation when no events"""
        news_service = Mock()
        news_service.get_upcoming_events = Mock(return_value=[])
        
        result = _calculate_news_risk(news_service, datetime.now(timezone.utc))
        
        self.assertFalse(result["is_news_lock_active"])
        self.assertIsNone(result["minutes_to_next_high_impact"])
    
    def test_calculate_news_risk_high_impact_event(self):
        """Test news risk calculation with high-impact event"""
        news_service = Mock()
        current_time = datetime(2025, 12, 11, 14, 0, 0, tzinfo=timezone.utc)
        event_time = current_time + timedelta(minutes=20)  # 20 minutes from now
        
        events = [
            {
                "time": event_time.isoformat(),
                "event": "NFP Release",
                "impact": "HIGH"
            }
        ]
        news_service.get_upcoming_events = Mock(return_value=events)
        
        result = _calculate_news_risk(news_service, current_time)
        
        self.assertTrue(result["is_news_lock_active"])
        self.assertIsNotNone(result["minutes_to_next_high_impact"])
        self.assertEqual(result["minutes_to_next_high_impact"], 20)
        self.assertTrue(result["is_in_high_impact_window"])
    
    def test_calculate_news_risk_event_far_away(self):
        """Test news risk calculation with event far away"""
        news_service = Mock()
        current_time = datetime(2025, 12, 11, 14, 0, 0, tzinfo=timezone.utc)
        event_time = current_time + timedelta(hours=2)  # 2 hours from now
        
        events = [
            {
                "time": event_time.isoformat(),
                "event": "FOMC Meeting",
                "impact": "ULTRA"
            }
        ]
        news_service.get_upcoming_events = Mock(return_value=events)
        
        result = _calculate_news_risk(news_service, current_time)
        
        self.assertFalse(result["is_news_lock_active"])
        self.assertIsNotNone(result["minutes_to_next_high_impact"])
        self.assertEqual(result["minutes_to_next_high_impact"], 120)
        self.assertFalse(result["is_in_high_impact_window"])
    
    def test_calculate_news_risk_low_impact_filtered(self):
        """Test that low-impact events are filtered out"""
        news_service = Mock()
        current_time = datetime(2025, 12, 11, 14, 0, 0, tzinfo=timezone.utc)
        
        events = [
            {
                "time": (current_time + timedelta(minutes=10)).isoformat(),
                "event": "Low Impact Event",
                "impact": "LOW"
            }
        ]
        news_service.get_upcoming_events = Mock(return_value=events)
        
        result = _calculate_news_risk(news_service, current_time)
        
        self.assertFalse(result["is_news_lock_active"])
        self.assertIsNone(result["minutes_to_next_high_impact"])
    
    def test_calculate_session_risk_full(self):
        """Test full session risk calculation"""
        news_service = Mock()
        current_time = datetime(2025, 12, 11, 14, 30, 0, tzinfo=timezone.utc)
        event_time = current_time + timedelta(minutes=25)
        
        events = [
            {
                "time": event_time.isoformat(),
                "event": "CPI Release",
                "impact": "HIGH"
            }
        ]
        news_service.get_upcoming_events = Mock(return_value=events)
        
        result = calculate_session_risk(news_service, "XAUUSDc", current_time)
        
        self.assertIn("is_rollover_window", result)
        self.assertIn("is_news_lock_active", result)
        self.assertIn("minutes_to_next_high_impact", result)
        self.assertIn("session_profile", result)
        self.assertIn("rollover_window_start", result)
        self.assertIn("rollover_window_end", result)
        self.assertEqual(result["session_profile"], "normal")
        self.assertEqual(result["session_volatility_multiplier"], 1.0)
    
    def test_calculate_session_risk_no_news_service(self):
        """Test session risk calculation without news service"""
        current_time = datetime(2025, 12, 11, 14, 30, 0, tzinfo=timezone.utc)
        
        result = calculate_session_risk(None, "XAUUSDc", current_time)
        
        self.assertFalse(result["is_news_lock_active"])
        self.assertIsNone(result["minutes_to_next_high_impact"])
        self.assertFalse(result["is_rollover_window"])
    
    def test_calculate_session_risk_defaults_current_time(self):
        """Test session risk calculation with default current time"""
        result = calculate_session_risk()
        
        self.assertIn("is_rollover_window", result)
        self.assertIn("is_news_lock_active", result)
        self.assertIn("session_profile", result)
    
    def test_create_default_response(self):
        """Test creating default response"""
        current_time = datetime(2025, 12, 11, 14, 30, 0, tzinfo=timezone.utc)
        result = _create_default_response(current_time)
        
        self.assertFalse(result["is_rollover_window"])
        self.assertFalse(result["is_news_lock_active"])
        self.assertEqual(result["session_profile"], "normal")
        self.assertIn("rollover_window_start", result)


if __name__ == '__main__':
    unittest.main()

