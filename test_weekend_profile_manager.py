"""
Unit tests for Weekend Profile Manager
Tests weekend detection, subsession detection, and edge cases.
"""

import unittest
from datetime import datetime, timezone, timedelta
from infra.weekend_profile_manager import WeekendProfileManager


class TestWeekendProfileManager(unittest.TestCase):
    """Test cases for Weekend Profile Manager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = WeekendProfileManager()
    
    def test_friday_23_00_weekend_active(self):
        """Test that Friday 23:00 UTC is weekend"""
        # Friday 23:00 UTC
        test_time = datetime(2025, 1, 10, 23, 0, 0, tzinfo=timezone.utc)  # Friday
        self.assertTrue(self.manager.is_weekend_active(test_time))
    
    def test_friday_22_59_not_weekend(self):
        """Test that Friday 22:59 UTC is NOT weekend"""
        # Friday 22:59 UTC
        test_time = datetime(2025, 1, 10, 22, 59, 0, tzinfo=timezone.utc)  # Friday
        self.assertFalse(self.manager.is_weekend_active(test_time))
    
    def test_saturday_all_day_weekend(self):
        """Test that Saturday (all day) is weekend"""
        # Saturday 12:00 UTC
        test_time = datetime(2025, 1, 11, 12, 0, 0, tzinfo=timezone.utc)  # Saturday
        self.assertTrue(self.manager.is_weekend_active(test_time))
    
    def test_sunday_all_day_weekend(self):
        """Test that Sunday (all day) is weekend"""
        # Sunday 12:00 UTC
        test_time = datetime(2025, 1, 12, 12, 0, 0, tzinfo=timezone.utc)  # Sunday
        self.assertTrue(self.manager.is_weekend_active(test_time))
    
    def test_monday_02_59_weekend_active(self):
        """Test that Monday 02:59 UTC is still weekend"""
        # Monday 02:59 UTC
        test_time = datetime(2025, 1, 13, 2, 59, 0, tzinfo=timezone.utc)  # Monday
        self.assertTrue(self.manager.is_weekend_active(test_time))
    
    def test_monday_03_00_not_weekend(self):
        """Test that Monday 03:00 UTC is NOT weekend"""
        # Monday 03:00 UTC
        test_time = datetime(2025, 1, 13, 3, 0, 0, tzinfo=timezone.utc)  # Monday
        self.assertFalse(self.manager.is_weekend_active(test_time))
    
    def test_weekday_not_weekend(self):
        """Test that weekdays (Mon-Thu) are not weekend"""
        # Tuesday 12:00 UTC
        test_time = datetime(2025, 1, 7, 12, 0, 0, tzinfo=timezone.utc)  # Tuesday
        self.assertFalse(self.manager.is_weekend_active(test_time))
    
    def test_friday_23_00_subsession(self):
        """Test Friday 23:00 subsession"""
        test_time = datetime(2025, 1, 10, 23, 0, 0, tzinfo=timezone.utc)  # Friday 23:00
        subsession = self.manager.get_weekend_subsession(test_time)
        self.assertEqual(subsession, "ASIAN_RETAIL_BURST")
    
    def test_saturday_03_00_subsession(self):
        """Test Saturday 03:00 subsession"""
        test_time = datetime(2025, 1, 11, 3, 0, 0, tzinfo=timezone.utc)  # Saturday 03:00
        subsession = self.manager.get_weekend_subsession(test_time)
        self.assertEqual(subsession, "ASIAN_RETAIL_BURST")
    
    def test_saturday_12_00_subsession(self):
        """Test Saturday 12:00 subsession"""
        test_time = datetime(2025, 1, 11, 12, 0, 0, tzinfo=timezone.utc)  # Saturday 12:00
        subsession = self.manager.get_weekend_subsession(test_time)
        self.assertEqual(subsession, "LOW_LIQUIDITY_RANGE")
    
    def test_saturday_20_00_subsession(self):
        """Test Saturday 20:00 subsession"""
        test_time = datetime(2025, 1, 11, 20, 0, 0, tzinfo=timezone.utc)  # Saturday 20:00
        subsession = self.manager.get_weekend_subsession(test_time)
        self.assertEqual(subsession, "DEAD_ZONE")
    
    def test_sunday_06_00_subsession(self):
        """Test Sunday 06:00 subsession"""
        test_time = datetime(2025, 1, 12, 6, 0, 0, tzinfo=timezone.utc)  # Sunday 06:00
        subsession = self.manager.get_weekend_subsession(test_time)
        self.assertEqual(subsession, "DEAD_ZONE")
    
    def test_sunday_18_00_subsession(self):
        """Test Sunday 18:00 subsession"""
        test_time = datetime(2025, 1, 12, 18, 0, 0, tzinfo=timezone.utc)  # Sunday 18:00
        subsession = self.manager.get_weekend_subsession(test_time)
        self.assertEqual(subsession, "CME_ANTICIPATION")
    
    def test_sunday_23_00_subsession(self):
        """Test Sunday 23:00 subsession"""
        test_time = datetime(2025, 1, 12, 23, 0, 0, tzinfo=timezone.utc)  # Sunday 23:00
        subsession = self.manager.get_weekend_subsession(test_time)
        self.assertEqual(subsession, "CME_GAP_REVERSION")
    
    def test_monday_01_00_subsession(self):
        """Test Monday 01:00 subsession"""
        test_time = datetime(2025, 1, 13, 1, 0, 0, tzinfo=timezone.utc)  # Monday 01:00
        subsession = self.manager.get_weekend_subsession(test_time)
        self.assertEqual(subsession, "CME_GAP_REVERSION")
    
    def test_weekday_no_subsession(self):
        """Test that weekday returns None for subsession"""
        test_time = datetime(2025, 1, 7, 12, 0, 0, tzinfo=timezone.utc)  # Tuesday
        subsession = self.manager.get_weekend_subsession(test_time)
        self.assertIsNone(subsession)
    
    def test_is_weekend_active_at_time(self):
        """Test is_weekend_active_at_time method"""
        # Friday 23:00 UTC
        test_time = datetime(2025, 1, 10, 23, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(self.manager.is_weekend_active_at_time(test_time))
        
        # Tuesday 12:00 UTC
        test_time = datetime(2025, 1, 7, 12, 0, 0, tzinfo=timezone.utc)
        self.assertFalse(self.manager.is_weekend_active_at_time(test_time))
    
    def test_time_until_weekend_ends_friday(self):
        """Test time until weekend ends calculation (Friday)"""
        # Friday 23:00 UTC
        test_time = datetime(2025, 1, 10, 23, 0, 0, tzinfo=timezone.utc)
        # Mock current time
        original_method = self.manager.is_weekend_active
        self.manager.is_weekend_active = lambda check_time=None: True if check_time is None else original_method(check_time)
        
        time_str = self.manager.get_time_until_weekend_ends()
        self.assertIsNotNone(time_str)
        self.assertIn("hours", time_str.lower() or "days" in time_str.lower())
    
    def test_time_until_weekend_starts_weekday(self):
        """Test time until weekend starts calculation (weekday)"""
        # Tuesday 12:00 UTC
        test_time = datetime(2025, 1, 7, 12, 0, 0, tzinfo=timezone.utc)
        # Mock current time
        original_method = self.manager.is_weekend_active
        self.manager.is_weekend_active = lambda check_time=None: False if check_time is None else original_method(check_time)
        
        time_str = self.manager.get_time_until_weekend_starts()
        self.assertIsNotNone(time_str)
        self.assertIn("hours", time_str.lower() or "days" in time_str.lower())


if __name__ == '__main__':
    unittest.main()

