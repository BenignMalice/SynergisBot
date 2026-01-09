"""
Tests for Micro Order Block Detector
"""

import unittest
from infra.micro_order_block_detector import MicroOrderBlockDetector, MicroOrderBlock


class TestMicroOrderBlockDetector(unittest.TestCase):
    """Test MicroOrderBlockDetector functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = MicroOrderBlockDetector(lookback=3)
    
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
    
    def test_bullish_micro_ob_detected(self):
        """Test bullish micro OB detection"""
        candles = []
        # Create base candles
        for i in range(3):
            candles.append(self._create_candle(i, 2000.0, 2000.05, 1999.95, 2000.0))
        
        # Strong bullish candle (body = 0.08, range within ATR threshold)
        candles.append(self._create_candle(3, 2000.0, 2000.12, 2000.0, 2000.08))
        # Small consolidation candle (body = 0.02, much smaller)
        candles.append(self._create_candle(4, 2000.08, 2000.10, 2000.06, 2000.09))
        
        obs = self.detector.detect_micro_obs(candles, atr_value=0.5, current_price=2000.09)
        self.assertGreater(len(obs), 0)
        if obs:
            self.assertEqual(obs[0].direction, "BULLISH")
    
    def test_bearish_micro_ob_detected(self):
        """Test bearish micro OB detection"""
        candles = []
        # Create base candles
        for i in range(3):
            candles.append(self._create_candle(i, 2000.0, 2000.05, 1999.95, 2000.0))
        
        # Strong bearish candle (body = 0.08, range within ATR threshold)
        candles.append(self._create_candle(3, 2000.0, 2000.0, 1999.88, 1999.92))
        # Small consolidation candle (body = 0.02, much smaller)
        candles.append(self._create_candle(4, 1999.92, 1999.94, 1999.90, 1999.91))
        
        obs = self.detector.detect_micro_obs(candles, atr_value=0.5, current_price=1999.91)
        self.assertGreater(len(obs), 0)
        if obs:
            self.assertEqual(obs[0].direction, "BEARISH")
    
    def test_validate_ob_retest(self):
        """Test OB retest validation"""
        candles = []
        for i in range(5):
            candles.append(self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0))
        
        ob_range = (1999.5, 2000.5)
        
        # Price retesting OB
        candles.append(self._create_candle(5, 2000.0, 2000.4, 1999.6, 2000.2))
        
        validated = self.detector.validate_ob_retest(candles, ob_range, "BULLISH")
        self.assertTrue(validated)
    
    def test_insufficient_candles(self):
        """Test with insufficient candles"""
        candles = [self._create_candle(0, 2000.0, 2000.5, 1999.5, 2000.0)]
        obs = self.detector.detect_micro_obs(candles)
        self.assertEqual(len(obs), 0)


if __name__ == '__main__':
    unittest.main()

