"""
Unit tests for HTFLevelsCalculator
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
import asyncio

# Import the calculator
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.htf_levels_calculator import HTFLevelsCalculator


class TestHTFLevelsCalculator(unittest.TestCase):
    """Synchronous test cases for HTFLevelsCalculator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mt5_service = Mock()
        self.calculator = HTFLevelsCalculator(mt5_service=self.mt5_service)
    
    def test_initialization(self):
        """Test calculator initialization"""
        self.assertIsNotNone(self.calculator)
        self.assertEqual(self.calculator.mt5_service, self.mt5_service)
    
    def test_get_week_start(self):
        """Test week start calculation"""
        # Test with a Wednesday
        dt = datetime(2025, 12, 11, 14, 30, 0, tzinfo=timezone.utc)  # Wednesday
        week_start = self.calculator._get_week_start(dt)
        
        self.assertEqual(week_start.weekday(), 0)  # Monday
        self.assertEqual(week_start.hour, 0)
        self.assertEqual(week_start.minute, 0)
        self.assertEqual(week_start.date(), datetime(2025, 12, 8, tzinfo=timezone.utc).date())
    
    def test_get_month_start(self):
        """Test month start calculation"""
        dt = datetime(2025, 12, 15, 14, 30, 0, tzinfo=timezone.utc)
        month_start = self.calculator._get_month_start(dt)
        
        self.assertEqual(month_start.day, 1)
        self.assertEqual(month_start.month, 12)
        self.assertEqual(month_start.year, 2025)
        self.assertEqual(month_start.hour, 0)
    
    def test_calculate_price_position_weekly_range(self):
        """Test price position calculation within weekly range"""
        current_price = 100.0
        prev_week_high = 105.0
        prev_week_low = 95.0
        prev_day_high = 102.0
        prev_day_low = 98.0
        
        range_ref, price_pos = self.calculator._calculate_price_position(
            current_price, prev_week_high, prev_week_low, prev_day_high, prev_day_low
        )
        
        self.assertEqual(range_ref, "weekly_range")
        self.assertIn(price_pos, ["discount", "equilibrium", "premium"])
    
    def test_calculate_price_position_premium(self):
        """Test price position in premium zone"""
        current_price = 103.0  # Top 33% of range (95-105)
        prev_week_high = 105.0
        prev_week_low = 95.0
        
        range_ref, price_pos = self.calculator._calculate_price_position(
            current_price, prev_week_high, prev_week_low, None, None
        )
        
        self.assertEqual(price_pos, "premium")
    
    def test_calculate_price_position_discount(self):
        """Test price position in discount zone"""
        current_price = 97.0  # Bottom 33% of range (95-105)
        prev_week_high = 105.0
        prev_week_low = 95.0
        
        range_ref, price_pos = self.calculator._calculate_price_position(
            current_price, prev_week_high, prev_week_low, None, None
        )
        
        self.assertEqual(price_pos, "discount")
    
    def test_calculate_price_position_equilibrium(self):
        """Test price position in equilibrium zone"""
        current_price = 100.0  # Middle 33% of range (95-105)
        prev_week_high = 105.0
        prev_week_low = 95.0
        
        range_ref, price_pos = self.calculator._calculate_price_position(
            current_price, prev_week_high, prev_week_low, None, None
        )
        
        self.assertEqual(price_pos, "equilibrium")
    
    def test_create_unavailable_response(self):
        """Test creating unavailable response"""
        response = self.calculator._create_unavailable_response()
        
        self.assertIsNone(response["weekly_open"])
        self.assertIsNone(response["monthly_open"])
        self.assertEqual(response["range_reference"], "daily_range")
        self.assertEqual(response["current_price_position"], "equilibrium")
        self.assertEqual(response["timezone"], "UTC")


class TestHTFLevelsCalculatorAsync(unittest.IsolatedAsyncioTestCase):
    """Async test cases for HTFLevelsCalculator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mt5_service = Mock()
        self.calculator = HTFLevelsCalculator(mt5_service=self.mt5_service)
    
    async def test_calculate_htf_levels_valid(self):
        """Test calculating HTF levels with valid data"""
        # Mock D1 bars (30 days)
        d1_bars = pd.DataFrame({
            'time': pd.date_range(start='2025-11-12', periods=30, freq='D'),
            'open': np.linspace(100.0, 105.0, 30),
            'high': np.linspace(102.0, 107.0, 30),
            'low': np.linspace(98.0, 103.0, 30),
            'close': np.linspace(101.0, 106.0, 30)
        })
        
        # Mock W1 bars (4 weeks)
        w1_bars = pd.DataFrame({
            'time': pd.date_range(start='2025-11-17', periods=4, freq='W-MON'),
            'open': np.array([100.0, 101.0, 102.0, 103.0]),
            'high': np.array([105.0, 106.0, 107.0, 108.0]),
            'low': np.array([95.0, 96.0, 97.0, 98.0]),
            'close': np.array([101.0, 102.0, 103.0, 104.0])
        })
        
        # Mock MN1 bars (3 months)
        mn1_bars = pd.DataFrame({
            'time': pd.date_range(start='2025-10-01', periods=3, freq='MS'),
            'open': np.array([95.0, 100.0, 105.0]),
            'high': np.array([110.0, 115.0, 120.0]),
            'low': np.array([90.0, 95.0, 100.0]),
            'close': np.array([100.0, 105.0, 110.0])
        })
        
        self.mt5_service.get_bars = Mock(side_effect=[d1_bars, w1_bars, mn1_bars])
        
        # Mock current price
        with patch('infra.htf_levels_calculator.mt5') as mock_mt5:
            mock_tick = Mock()
            mock_tick.bid = 104.0
            mock_tick.ask = 104.1
            mock_mt5.symbol_info_tick.return_value = mock_tick
            
            result = await self.calculator.calculate_htf_levels("XAUUSDc")
            
            self.assertIsNotNone(result)
            self.assertIn("previous_day_high", result)
            self.assertIn("previous_day_low", result)
            self.assertIn("previous_week_high", result)
            self.assertIn("previous_week_low", result)
            self.assertIn("range_reference", result)
            self.assertIn("current_price_position", result)
    
    async def test_calculate_htf_levels_no_mt5_service(self):
        """Test HTF levels when MT5 service not available"""
        calculator = HTFLevelsCalculator(mt5_service=None)
        
        result = await calculator.calculate_htf_levels("XAUUSDc")
        
        self.assertEqual(result["range_reference"], "daily_range")
        self.assertIsNone(result["weekly_open"])
    
    async def test_calculate_htf_levels_no_bars(self):
        """Test HTF levels when no bars available"""
        self.mt5_service.get_bars = Mock(return_value=None)
        
        with patch('infra.htf_levels_calculator.mt5') as mock_mt5:
            mock_tick = Mock()
            mock_tick.bid = 104.0
            mock_tick.ask = 104.1
            mock_mt5.symbol_info_tick.return_value = mock_tick
            
            result = await self.calculator.calculate_htf_levels("XAUUSDc")
            
            self.assertIsNotNone(result)
            # Should return unavailable response
            self.assertIsNone(result["previous_day_high"])
    
    async def test_fetch_bars(self):
        """Test fetching bars"""
        bars = pd.DataFrame({
            'time': pd.date_range(start='2025-12-01', periods=10, freq='D'),
            'open': np.ones(10) * 100.0,
            'high': np.ones(10) * 105.0,
            'low': np.ones(10) * 95.0,
            'close': np.ones(10) * 102.0
        })
        self.mt5_service.get_bars = Mock(return_value=bars)
        
        result = await self.calculator._fetch_bars("XAUUSDc", "D1", 10)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 10)
    
    async def test_calculate_htf_levels_previous_week_calculation(self):
        """Test previous week high/low calculation"""
        # Create W1 bars with clear previous week
        w1_bars = pd.DataFrame({
            'time': pd.date_range(start='2025-11-17', periods=4, freq='W-MON'),
            'open': np.array([100.0, 101.0, 102.0, 103.0]),
            'high': np.array([105.0, 106.0, 107.0, 108.0]),
            'low': np.array([95.0, 96.0, 97.0, 98.0]),
            'close': np.array([101.0, 102.0, 103.0, 104.0])
        })
        
        # Mock minimal D1 and MN1 bars
        d1_bars = pd.DataFrame({
            'time': pd.date_range(start='2025-12-01', periods=2, freq='D'),
            'open': np.array([103.0, 104.0]),
            'high': np.array([108.0, 109.0]),
            'low': np.array([98.0, 99.0]),
            'close': np.array([104.0, 105.0])
        })
        
        mn1_bars = pd.DataFrame({
            'time': pd.date_range(start='2025-10-01', periods=2, freq='MS'),
            'open': np.array([100.0, 105.0]),
            'high': np.array([110.0, 115.0]),
            'low': np.array([95.0, 100.0]),
            'close': np.array([105.0, 110.0])
        })
        
        self.mt5_service.get_bars = Mock(side_effect=[d1_bars, w1_bars, mn1_bars])
        
        with patch('infra.htf_levels_calculator.mt5') as mock_mt5:
            mock_tick = Mock()
            mock_tick.bid = 104.0
            mock_tick.ask = 104.1
            mock_mt5.symbol_info_tick.return_value = mock_tick
            
            result = await self.calculator.calculate_htf_levels("XAUUSDc")
            
            # Previous week should be second-to-last week
            self.assertIsNotNone(result["previous_week_high"])
            self.assertIsNotNone(result["previous_week_low"])
            # Previous week high should be 107.0 (second-to-last)
            self.assertEqual(result["previous_week_high"], 107.0)
            self.assertEqual(result["previous_week_low"], 97.0)


if __name__ == '__main__':
    unittest.main()

