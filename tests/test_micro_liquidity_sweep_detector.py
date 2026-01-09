"""
Tests for Micro Liquidity Sweep Detector
"""

import unittest
from infra.micro_liquidity_sweep_detector import MicroLiquiditySweepDetector, MicroSweepResult


class TestMicroLiquiditySweepDetector(unittest.TestCase):
    """Test MicroLiquiditySweepDetector functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = MicroLiquiditySweepDetector(lookback=10)
    
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
    
    def test_no_sweep_detected(self):
        """Test when no sweep is present"""
        candles = []
        for i in range(12):
            candles.append(self._create_candle(
                i, 2000.0, 2000.5, 1999.5, 2000.0
            ))
        
        result = self.detector.detect_micro_sweep(candles)
        self.assertFalse(result.sweep_detected)
    
    def test_bullish_sweep_detected(self):
        """Test bullish sweep detection"""
        candles = []
        # Create candles with local high at 2000.5 (need lookback + 2 = 12 total)
        for i in range(11):
            candles.append(self._create_candle(
                i, 2000.0, 2000.5, 1999.5, 2000.0
            ))
        
        # Last candle breaks above (high=2001.0 > 2000.5) and returns below (close=2000.4 < 2000.5)
        candles.append(self._create_candle(
            11, 2000.0, 2001.0, 1999.5, 2000.4, volume=2000  # Close below local high 2000.5
        ))
        
        result = self.detector.detect_micro_sweep(candles)
        self.assertTrue(result.sweep_detected, f"Expected sweep but got: {result}")
        self.assertEqual(result.direction, "BULLISH")
        self.assertGreater(result.confidence, 0.0)
    
    def test_bearish_sweep_detected(self):
        """Test bearish sweep detection"""
        candles = []
        # Create candles with local low at 1999.5 (need lookback + 2 = 12 total)
        for i in range(11):
            candles.append(self._create_candle(
                i, 2000.0, 2000.5, 1999.5, 2000.0
            ))
        
        # Last candle breaks below (low=1998.5 < 1999.5) and returns above (close=1999.6 > 1999.5)
        candles.append(self._create_candle(
            11, 2000.0, 2000.5, 1998.5, 1999.6, volume=2000  # Low wick, volume spike, close above local low
        ))
        
        result = self.detector.detect_micro_sweep(candles)
        self.assertTrue(result.sweep_detected, f"Expected sweep but got: {result}")
        self.assertEqual(result.direction, "BEARISH")
        self.assertGreater(result.confidence, 0.0)
    
    def test_wick_rejection_confirmation(self):
        """Test wick rejection confirmation"""
        candles = []
        for i in range(10):
            candles.append(self._create_candle(
                i, 2000.0, 2000.5, 1999.5, 2000.0
            ))
        
        # Candle with long upper wick (rejection)
        candles.append(self._create_candle(
            10, 2000.0, 2001.0, 1999.5, 2000.2  # High wick = 0.8, body = 0.2, ratio = 4.0
        ))
        
        result = self.detector.detect_micro_sweep(candles)
        if result.sweep_detected:
            self.assertTrue(result.wick_rejection)
    
    def test_volume_spike_confirmation(self):
        """Test volume spike confirmation"""
        candles = []
        for i in range(10):
            candles.append(self._create_candle(
                i, 2000.0, 2000.5, 1999.5, 2000.0, volume=1000
            ))
        
        # Candle with volume spike
        candles.append(self._create_candle(
            10, 2000.0, 2001.0, 1999.5, 2000.3, volume=2500  # 2.5x average
        ))
        
        result = self.detector.detect_micro_sweep(candles)
        if result.sweep_detected:
            self.assertTrue(result.volume_spike)
    
    def test_validate_post_sweep(self):
        """Test post-sweep validation"""
        candles = []
        for i in range(12):
            candles.append(self._create_candle(
                i, 2000.0, 2000.5, 1999.5, 2000.0
            ))
        
        # Bullish sweep at 2000.5
        sweep_level = 2000.5
        
        # Price returns below
        candles.append(self._create_candle(
            12, 2000.3, 2000.4, 1999.8, 2000.2  # Close below sweep level
        ))
        
        validated = self.detector.validate_post_sweep(candles, sweep_level, "BULLISH")
        self.assertTrue(validated)
    
    def test_insufficient_candles(self):
        """Test with insufficient candles"""
        candles = [self._create_candle(0, 2000.0, 2000.5, 1999.5, 2000.0)]
        result = self.detector.detect_micro_sweep(candles)
        self.assertFalse(result.sweep_detected)
    
    def test_get_sweep_confidence(self):
        """Test confidence score retrieval"""
        candles = []
        for i in range(10):
            candles.append(self._create_candle(
                i, 2000.0, 2000.5, 1999.5, 2000.0
            ))
        
        # Strong sweep with wick and volume
        candles.append(self._create_candle(
            10, 2000.0, 2001.0, 1999.5, 2000.2, volume=2500
        ))
        
        result = self.detector.detect_micro_sweep(candles)
        if result.sweep_detected:
            confidence = self.detector.get_sweep_confidence(result)
            self.assertGreaterEqual(confidence, 0.0)
            self.assertLessEqual(confidence, 1.0)


if __name__ == '__main__':
    unittest.main()

