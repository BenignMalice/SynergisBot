"""
Test session helper functions
"""

import unittest
from datetime import datetime, timezone, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from infra.session_helpers import SessionHelpers, get_session_time_conditions, get_next_session_start


class TestSessionHelpers(unittest.TestCase):
    """Test session helper functions"""
    
    def test_get_current_session(self):
        """Test get_current_session"""
        # Test London session (10:00 UTC)
        london_time = datetime(2025, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
        session = SessionHelpers.get_current_session(london_time)
        self.assertEqual(session, "LONDON")
        
        # Test Overlap session (14:00 UTC)
        overlap_time = datetime(2025, 11, 20, 14, 0, 0, tzinfo=timezone.utc)
        session = SessionHelpers.get_current_session(overlap_time)
        self.assertEqual(session, "OVERLAP")
        
        # Test NY session (18:00 UTC)
        ny_time = datetime(2025, 11, 20, 18, 0, 0, tzinfo=timezone.utc)
        session = SessionHelpers.get_current_session(ny_time)
        self.assertEqual(session, "NY")
        
        # Test Asian session (3:00 UTC)
        asian_time = datetime(2025, 11, 20, 3, 0, 0, tzinfo=timezone.utc)
        session = SessionHelpers.get_current_session(asian_time)
        self.assertEqual(session, "ASIAN")
    
    def test_get_session_time_range(self):
        """Test get_session_time_range"""
        date = datetime(2025, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
        
        # Test London session (08:00-13:00 UTC)
        start, end = SessionHelpers.get_session_time_range("LONDON", date)
        self.assertEqual(start.hour, 8)
        self.assertEqual(end.hour, 13)
        
        # Test Overlap session (13:00-16:00 UTC)
        start, end = SessionHelpers.get_session_time_range("OVERLAP", date)
        self.assertEqual(start.hour, 13)
        self.assertEqual(end.hour, 16)
    
    def test_get_time_conditions_for_session(self):
        """Test get_time_conditions_for_session"""
        date = datetime(2025, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
        
        conditions = SessionHelpers.get_time_conditions_for_session("LONDON", date)
        
        self.assertIn("time_after", conditions)
        self.assertIn("time_before", conditions)
        
        # Verify ISO format
        time_after = datetime.fromisoformat(conditions["time_after"])
        time_before = datetime.fromisoformat(conditions["time_before"])
        
        self.assertEqual(time_after.hour, 8)
        self.assertEqual(time_before.hour, 13)
    
    def test_get_next_session_time(self):
        """Test get_next_session_time"""
        # Current time in London session
        current_time = datetime(2025, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
        
        # Get next NY session
        next_ny = SessionHelpers.get_next_session_time("NY", current_time)
        
        # Should be same day at 16:00 UTC
        self.assertEqual(next_ny.hour, 16)
        self.assertEqual(next_ny.day, 20)
    
    def test_is_session_active(self):
        """Test is_session_active"""
        # Test during London session
        london_time = datetime(2025, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(SessionHelpers.is_session_active("LONDON", london_time))
        self.assertFalse(SessionHelpers.is_session_active("NY", london_time))
    
    def test_get_session_duration_hours(self):
        """Test get_session_duration_hours"""
        # London session: 8 hours (08:00-13:00)
        duration = SessionHelpers.get_session_duration_hours("LONDON")
        self.assertEqual(duration, 5.0)  # 13 - 8 = 5
        
        # Overlap session: 3 hours (13:00-16:00)
        duration = SessionHelpers.get_session_duration_hours("OVERLAP")
        self.assertEqual(duration, 3.0)  # 16 - 13 = 3
    
    def test_convenience_functions(self):
        """Test convenience functions"""
        conditions = get_session_time_conditions("LONDON")
        self.assertIn("time_after", conditions)
        self.assertIn("time_before", conditions)
        
        next_start = get_next_session_start("NY")
        self.assertIsInstance(next_start, str)
        # Should be valid ISO format
        datetime.fromisoformat(next_start)


if __name__ == '__main__':
    unittest.main()

