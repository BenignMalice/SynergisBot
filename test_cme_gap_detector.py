"""
Unit tests for CME Gap Detector
Tests gap detection, threshold validation, and reversion plan creation logic.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import sys

# Mock MetaTrader5 before importing CMEGapDetector
sys.modules['MetaTrader5'] = MagicMock()
mt5_mock = MagicMock()
mt5_mock.TIMEFRAME_H1 = 60
mt5_mock.TIMEFRAME_M15 = 15
mt5_mock.initialize.return_value = True
mt5_mock.copy_rates_range.return_value = None  # Default to None, specific tests can override
mt5_mock.symbol_info_tick.return_value = None  # Default to None
sys.modules['MetaTrader5'] = mt5_mock

from infra.cme_gap_detector import CMEGapDetector
from infra.mt5_service import MT5Service


class TestCMEGapDetector(unittest.TestCase):
    """Test cases for CME Gap Detector"""

    def setUp(self):
        self.mock_mt5_service = Mock(spec=MT5Service)
        self.detector = CMEGapDetector(mt5_service=self.mock_mt5_service)

    def test_detect_gap_non_btc_symbol(self):
        """Test that gap detection returns None for non-BTC symbols"""
        gap_info = self.detector.detect_gap("XAUUSDc")
        self.assertIsNone(gap_info)

    def test_detect_gap_insufficient_data(self):
        """Test gap detection when Friday close or Sunday open unavailable"""
        with patch.object(self.detector, '_get_friday_cme_close', return_value=None):
            gap_info = self.detector.detect_gap("BTCUSDc")
            self.assertIsNone(gap_info)

        with patch.object(self.detector, '_get_sunday_reopening_price', return_value=None):
            with patch.object(self.detector, '_get_friday_cme_close', return_value=90000.0):
                gap_info = self.detector.detect_gap("BTCUSDc")
                self.assertIsNone(gap_info)

    def test_detect_gap_gap_down(self):
        """Test gap detection for gap down scenario"""
        friday_close = 90000.0
        sunday_open = 89500.0  # Gap down 500 points (0.56%)
        
        # Mock both methods on the instance
        self.detector._get_friday_cme_close = Mock(return_value=friday_close)
        self.detector._get_sunday_reopening_price = Mock(return_value=sunday_open)
        
        gap_info = self.detector.detect_gap("BTCUSDc")
        
        # Check that gap_info is not None (both prices available)
        self.assertIsNotNone(gap_info, "Gap info should not be None when both prices are available")
        
        self.assertEqual(gap_info['gap_direction'], 'down')
        self.assertAlmostEqual(gap_info['gap_pct'], 0.556, places=2)
        self.assertEqual(gap_info['friday_close'], friday_close)
        self.assertEqual(gap_info['sunday_open'], sunday_open)
        self.assertTrue(gap_info['should_trade'])  # > 0.5% threshold
        
        # Target should be 80% gap fill
        expected_target = friday_close + ((sunday_open - friday_close) * 0.8)
        self.assertAlmostEqual(gap_info['target_price'], expected_target, places=2)

    def test_detect_gap_gap_up(self):
        """Test gap detection for gap up scenario"""
        friday_close = 90000.0
        sunday_open = 90500.0  # Gap up 500 points (0.56%)
        
        # Create a new detector instance and mock methods directly
        detector = CMEGapDetector()
        detector._get_friday_cme_close = lambda symbol: friday_close
        detector._get_sunday_reopening_price = lambda symbol: sunday_open
        
        gap_info = detector.detect_gap("BTCUSDc")
        
        # Check that gap_info is not None (both prices available)
        self.assertIsNotNone(gap_info, "Gap info should not be None when both prices are available")
        
        self.assertEqual(gap_info['gap_direction'], 'up')
        self.assertAlmostEqual(gap_info['gap_pct'], 0.556, places=2)
        self.assertTrue(gap_info['should_trade'])  # > 0.5% threshold

    def test_detect_gap_below_threshold(self):
        """Test gap detection when gap is below 0.5% threshold"""
        friday_close = 90000.0
        sunday_open = 90020.0  # Gap up 20 points (0.022% - below threshold)
        
        # Create a new detector instance and mock methods directly
        detector = CMEGapDetector()
        detector._get_friday_cme_close = lambda symbol: friday_close
        detector._get_sunday_reopening_price = lambda symbol: sunday_open
        
        gap_info = detector.detect_gap("BTCUSDc")
        
        # Check that gap_info is not None (both prices available)
        self.assertIsNotNone(gap_info, "Gap info should not be None when both prices are available")
        
        self.assertFalse(gap_info['should_trade'])  # < 0.5% threshold

    def test_should_create_reversion_plan_true(self):
        """Test should_create_reversion_plan returns True for gap > 0.5%"""
        gap_info = {
            'should_trade': True,
            'gap_pct': 0.6
        }
        
        with patch.object(self.detector, 'detect_gap', return_value=gap_info):
            result = self.detector.should_create_reversion_plan("BTCUSDc")
            self.assertTrue(result)

    def test_should_create_reversion_plan_false(self):
        """Test should_create_reversion_plan returns False for gap < 0.5%"""
        gap_info = {
            'should_trade': False,
            'gap_pct': 0.3
        }
        
        with patch.object(self.detector, 'detect_gap', return_value=gap_info):
            result = self.detector.should_create_reversion_plan("BTCUSDc")
            self.assertFalse(result)

    def test_should_create_reversion_plan_no_gap(self):
        """Test should_create_reversion_plan returns False when no gap detected"""
        with patch.object(self.detector, 'detect_gap', return_value=None):
            result = self.detector.should_create_reversion_plan("BTCUSDc")
            self.assertFalse(result)

    @patch('infra.cme_gap_detector.mt5')
    def test_get_friday_cme_close_success(self, mock_mt5):
        """Test getting Friday CME close price successfully"""
        # Mock MT5 initialization
        mock_mt5.initialize.return_value = True
        
        # Create mock rates (H1 candles)
        now = datetime.now(timezone.utc)
        friday_date = now.date() - timedelta(days=(now.weekday() - 4) % 7)
        if friday_date > now.date():
            friday_date = friday_date - timedelta(days=7)
        
        friday_22_utc = datetime.combine(friday_date, datetime.min.time().replace(hour=22, minute=0))
        friday_22_utc = friday_22_utc.replace(tzinfo=timezone.utc)
        
        # Create mock candle at 22:00 UTC
        mock_rates = [
            {
                'time': int((friday_22_utc - timedelta(hours=1)).timestamp()),
                'close': 90000.0
            },
            {
                'time': int(friday_22_utc.timestamp()),
                'close': 90100.0
            }
        ]
        
        mock_mt5.copy_rates_range.return_value = mock_rates
        
        result = self.detector._get_friday_cme_close("BTCUSDc")
        
        # Should return the close price at or before 22:00 UTC
        self.assertIsNotNone(result)
        self.assertIn(result, [90000.0, 90100.0])

    @patch('infra.cme_gap_detector.mt5')
    def test_get_sunday_reopening_price_success(self, mock_mt5):
        """Test getting Sunday reopening price successfully"""
        # Mock MT5 initialization
        mock_mt5.initialize.return_value = True
        
        # Create mock rates (H1 candles)
        now = datetime.now(timezone.utc)
        sunday_date = now.date() - timedelta(days=(now.weekday() - 6) % 7)
        if sunday_date > now.date():
            sunday_date = sunday_date - timedelta(days=7)
        
        sunday_00_utc = datetime.combine(sunday_date, datetime.min.time().replace(hour=0, minute=0))
        sunday_00_utc = sunday_00_utc.replace(tzinfo=timezone.utc)
        
        # Create mock candle at 00:00 UTC
        mock_rates = [
            {
                'time': int(sunday_00_utc.timestamp()),
                'open': 89500.0
            }
        ]
        
        mock_mt5.copy_rates_range.return_value = mock_rates
        
        result = self.detector._get_sunday_reopening_price("BTCUSDc")
        
        # Should return the open price of first Sunday candle
        self.assertIsNotNone(result)
        self.assertEqual(result, 89500.0)

    @patch('infra.cme_gap_detector.mt5')
    def test_get_sunday_reopening_price_current_tick(self, mock_mt5):
        """Test getting Sunday reopening price from current tick if it's Sunday"""
        # Mock MT5 initialization
        mock_mt5.initialize.return_value = True
        mock_mt5.copy_rates_range.return_value = None  # No historical data
        
        # Mock current time to be Sunday
        with patch('infra.cme_gap_detector.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 12, 10, 0, 0, tzinfo=timezone.utc)  # Sunday
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)  # Allow real datetime calls
            
            # Mock tick
            mock_tick = Mock()
            mock_tick.bid = 89500.0
            mock_tick.ask = 89510.0
            mock_mt5.symbol_info_tick.return_value = mock_tick
            
            result = self.detector._get_sunday_reopening_price("BTCUSDc")
            
            # Should return mid price
            self.assertIsNotNone(result)
            self.assertEqual(result, 89505.0)  # (89500 + 89510) / 2


if __name__ == '__main__':
    unittest.main()

