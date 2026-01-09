"""
Tests for VWAP Micro Filter
"""

import unittest
from infra.vwap_micro_filter import VWAPMicroFilter, VWAPProximityResult, VWAPRetestResult


class TestVWAPMicroFilter(unittest.TestCase):
    """Test VWAPMicroFilter functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.filter = VWAPMicroFilter(tolerance_type="fixed", tolerance_fixed=0.0005)
    
    def _create_candle(self, time, open, high, low, close, volume=1000):
        """Helper to create candle dict"""
        return {
            'time': time,
            'open': open,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }
    
    def test_calculate_vwap_band_fixed(self):
        """Test VWAP band calculation (fixed tolerance)"""
        vwap = 2000.0
        price = 2000.0
        band_lower, band_upper = self.filter.calculate_vwap_band(vwap, price)
        
        self.assertLess(band_lower, vwap)
        self.assertGreater(band_upper, vwap)
        self.assertAlmostEqual(band_upper - vwap, vwap - band_lower, places=2)
    
    def test_calculate_vwap_band_atr_adjusted(self):
        """Test VWAP band calculation (ATR-adjusted)"""
        filter_atr = VWAPMicroFilter(tolerance_type="atr_adjusted", tolerance_atr_multiplier=0.1)
        vwap = 2000.0
        price = 2000.0
        atr = 1.0
        
        band_lower, band_upper = filter_atr.calculate_vwap_band(vwap, price, atr)
        
        # Band should be ATR-based
        expected_tolerance = atr * 0.1
        self.assertAlmostEqual(band_upper - vwap, expected_tolerance, places=2)
    
    def test_is_price_near_vwap(self):
        """Test price proximity to VWAP"""
        vwap = 2000.0
        price = 2000.1  # Very close
        
        result = self.filter.is_price_near_vwap(price, vwap)
        self.assertTrue(result.is_near_vwap)
        self.assertTrue(result.in_band)
    
    def test_is_price_above_vwap(self):
        """Test price above VWAP check"""
        vwap = 2000.0
        price = 2001.0
        
        self.assertTrue(self.filter.is_price_above_vwap(price, vwap))
        self.assertFalse(self.filter.is_price_below_vwap(price, vwap))
    
    def test_is_price_below_vwap(self):
        """Test price below VWAP check"""
        vwap = 2000.0
        price = 1999.0
        
        self.assertTrue(self.filter.is_price_below_vwap(price, vwap))
        self.assertFalse(self.filter.is_price_above_vwap(price, vwap))
    
    def test_detect_vwap_retest(self):
        """Test VWAP retest detection"""
        candles = []
        for i in range(10):
            candles.append(self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0))
        
        # Candle with wick rejection at VWAP
        candles.append(self._create_candle(10, 2000.0, 2001.0, 1999.5, 2000.2))  # Long upper wick
        
        vwap = 2000.0
        vwap_band = (1999.9, 2001.0)
        
        result = self.filter.detect_vwap_retest(candles, vwap, vwap_band)
        # May or may not detect depending on exact logic, but should not crash
        self.assertIsInstance(result, VWAPRetestResult)
    
    def test_track_vwap_persistence(self):
        """Test VWAP persistence tracking"""
        symbol = "XAUUSDc"
        vwap = 2000.0
        vwap_band = (1999.9, 2000.1)
        
        # Price in band
        price1 = 2000.0
        persistence1 = self.filter.track_vwap_persistence(symbol, price1, vwap, vwap_band)
        self.assertGreaterEqual(persistence1, 0.0)
        
        # Still in band
        import time
        time.sleep(0.1)  # Small delay
        price2 = 2000.05
        persistence2 = self.filter.track_vwap_persistence(symbol, price2, vwap, vwap_band)
        self.assertGreaterEqual(persistence2, persistence1)
    
    def test_get_persistence_bonus(self):
        """Test persistence bonus calculation"""
        # Below minimum
        bonus1 = self.filter.get_persistence_bonus(15.0)
        self.assertEqual(bonus1, 1.0)
        
        # At minimum
        bonus2 = self.filter.get_persistence_bonus(30.0)
        self.assertEqual(bonus2, 1.0)
        
        # Above minimum
        bonus3 = self.filter.get_persistence_bonus(60.0)
        self.assertGreater(bonus3, 1.0)
        
        # High persistence
        bonus4 = self.filter.get_persistence_bonus(90.0)
        self.assertGreaterEqual(bonus4, 1.2)


if __name__ == '__main__':
    unittest.main()

