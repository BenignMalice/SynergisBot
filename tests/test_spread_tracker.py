"""
Tests for Spread Tracker
"""

import unittest
from infra.spread_tracker import SpreadTracker, SpreadData


class TestSpreadTracker(unittest.TestCase):
    """Test SpreadTracker functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tracker = SpreadTracker(window_size=10)
        self.symbol = "XAUUSDc"
    
    def test_update_spread(self):
        """Test updating spread history"""
        spread = self.tracker.update_spread(self.symbol, 2000.0, 2000.5)
        self.assertEqual(spread, 0.5)
        self.assertEqual(self.tracker.get_sample_count(self.symbol), 1)
    
    def test_get_average_spread(self):
        """Test average spread calculation"""
        # Add multiple spreads (ensure bid < ask)
        for i in range(5):
            self.tracker.update_spread(self.symbol, 2000.0, 2000.0 + ((i + 1) * 0.1))
        
        avg = self.tracker.get_average_spread(self.symbol)
        self.assertGreater(avg, 0.0)
        self.assertEqual(self.tracker.get_sample_count(self.symbol), 5)
    
    def test_get_spread_volatility(self):
        """Test spread volatility calculation"""
        # Add spreads with variation
        spreads = [0.3, 0.4, 0.5, 0.4, 0.6]
        for spread in spreads:
            self.tracker.update_spread(self.symbol, 2000.0, 2000.0 + spread)
        
        volatility = self.tracker.get_spread_volatility(self.symbol)
        self.assertGreater(volatility, 0.0)
    
    def test_get_spread_ratio(self):
        """Test spread ratio calculation"""
        # Add baseline spreads
        for _ in range(5):
            self.tracker.update_spread(self.symbol, 2000.0, 2000.5)
        
        # Add a wider spread
        current_spread = self.tracker.update_spread(self.symbol, 2000.0, 2001.0)
        ratio = self.tracker.get_spread_ratio(self.symbol, current_spread)
        self.assertGreater(ratio, 1.0)  # Should be > 1.0 (wider than average)
    
    def test_is_spread_acceptable(self):
        """Test spread acceptability check"""
        # Add baseline spreads
        for _ in range(5):
            self.tracker.update_spread(self.symbol, 2000.0, 2000.5)
        
        # Normal spread should be acceptable
        self.tracker.update_spread(self.symbol, 2000.0, 2000.5)
        self.assertTrue(self.tracker.is_spread_acceptable(self.symbol, max_ratio=1.5))
        
        # Wide spread should be rejected
        self.tracker.update_spread(self.symbol, 2000.0, 2001.5)
        self.assertFalse(self.tracker.is_spread_acceptable(self.symbol, max_ratio=1.5))
    
    def test_get_spread_data(self):
        """Test comprehensive spread data retrieval"""
        # Add some spreads
        for i in range(5):
            self.tracker.update_spread(self.symbol, 2000.0, 2000.0 + (i * 0.1))
        
        data = self.tracker.get_spread_data(self.symbol)
        self.assertIsInstance(data, SpreadData)
        self.assertGreater(data.current_spread, 0.0)
        self.assertGreater(data.average_spread, 0.0)
        self.assertGreaterEqual(data.sample_count, 1)
    
    def test_detect_asian_session_expansion(self):
        """Test Asian session expansion detection"""
        # Add baseline spreads (0.5 each)
        for _ in range(10):
            self.tracker.update_spread(self.symbol, 2000.0, 2000.5)
        
        # Add expanded spread (1.0, which is 2x the average of 0.5)
        self.tracker.update_spread(self.symbol, 2000.0, 2001.0)
        # Average should be ~0.5, current is 1.0, ratio = 2.0
        # Need at least 10 samples for reliable detection
        self.assertTrue(self.tracker.detect_asian_session_expansion(self.symbol, threshold_multiplier=1.5))
    
    def test_clear_history(self):
        """Test clearing spread history"""
        self.tracker.update_spread(self.symbol, 2000.0, 2000.5)
        self.assertEqual(self.tracker.get_sample_count(self.symbol), 1)
        
        self.tracker.clear_history(self.symbol)
        self.assertEqual(self.tracker.get_sample_count(self.symbol), 0)
    
    def test_multiple_symbols(self):
        """Test tracking multiple symbols"""
        symbol1 = "XAUUSDc"
        symbol2 = "BTCUSDc"
        
        self.tracker.update_spread(symbol1, 2000.0, 2000.5)
        self.tracker.update_spread(symbol2, 50000.0, 50010.0)
        
        self.assertEqual(self.tracker.get_sample_count(symbol1), 1)
        self.assertEqual(self.tracker.get_sample_count(symbol2), 1)
        
        avg1 = self.tracker.get_average_spread(symbol1)
        avg2 = self.tracker.get_average_spread(symbol2)
        
        self.assertNotEqual(avg1, avg2)


if __name__ == '__main__':
    unittest.main()

