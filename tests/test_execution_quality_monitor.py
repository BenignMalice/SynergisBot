"""
Unit tests for ExecutionQualityMonitor
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

# Import the calculator
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.execution_quality_monitor import ExecutionQualityMonitor
from infra.spread_tracker import SpreadTracker, SpreadData


class TestExecutionQualityMonitor(unittest.TestCase):
    """Synchronous test cases for ExecutionQualityMonitor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mt5_service = Mock()
        self.spread_tracker = SpreadTracker()
        self.monitor = ExecutionQualityMonitor(
            mt5_service=self.mt5_service,
            spread_tracker=self.spread_tracker
        )
    
    def test_initialization(self):
        """Test monitor initialization"""
        self.assertIsNotNone(self.monitor)
        self.assertEqual(self.monitor.mt5_service, self.mt5_service)
        self.assertIsNotNone(self.monitor.spread_tracker)
    
    def test_calculate_execution_quality_good(self):
        """Test execution quality calculation - good"""
        quality = self.monitor._calculate_execution_quality(1.2, 1.1)
        self.assertEqual(quality, "good")
    
    def test_calculate_execution_quality_degraded(self):
        """Test execution quality calculation - degraded"""
        quality = self.monitor._calculate_execution_quality(1.8, None)
        self.assertEqual(quality, "degraded")
        
        quality = self.monitor._calculate_execution_quality(1.2, 1.8)
        self.assertEqual(quality, "degraded")
    
    def test_calculate_execution_quality_poor(self):
        """Test execution quality calculation - poor"""
        quality = self.monitor._calculate_execution_quality(2.5, None)
        self.assertEqual(quality, "poor")
        
        quality = self.monitor._calculate_execution_quality(2.1, 2.1)
        self.assertEqual(quality, "poor")
    
    def test_create_unavailable_response(self):
        """Test creating unavailable response"""
        response = self.monitor._create_unavailable_response()
        
        self.assertEqual(response["current_spread_points"], 0.0)
        self.assertEqual(response["spread_vs_median"], 1.0)
        self.assertFalse(response["is_spread_elevated"])
        self.assertFalse(response["slippage_data_available"])


class TestExecutionQualityMonitorAsync(unittest.IsolatedAsyncioTestCase):
    """Async test cases for ExecutionQualityMonitor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mt5_service = Mock()
        self.spread_tracker = SpreadTracker()
        self.monitor = ExecutionQualityMonitor(
            mt5_service=self.mt5_service,
            spread_tracker=self.spread_tracker
        )
    
    async def test_get_execution_context_valid(self):
        """Test getting execution context with valid data"""
        # Setup spread tracker with history
        self.spread_tracker.update_spread("XAUUSDc", 100.0, 100.1)  # 0.1 spread
        self.spread_tracker.update_spread("XAUUSDc", 100.0, 100.15)  # 0.15 spread
        self.spread_tracker.update_spread("XAUUSDc", 100.0, 100.12)  # 0.12 spread
        
        # Mock MT5 service
        mock_quote = Mock()
        mock_quote.bid = 100.0
        mock_quote.ask = 100.2  # 0.2 spread (elevated)
        self.mt5_service.get_quote = Mock(return_value=mock_quote)
        
        # Mock symbol info for point size
        with patch('infra.execution_quality_monitor.mt5') as mock_mt5:
            mock_symbol_info = Mock()
            mock_symbol_info.point = 0.01
            mock_mt5.symbol_info.return_value = mock_symbol_info
            
            result = await self.monitor.get_execution_context("XAUUSDc")
            
            self.assertIsNotNone(result)
            self.assertIn("current_spread_points", result)
            self.assertIn("spread_vs_median", result)
            self.assertIn("is_spread_elevated", result)
            self.assertIn("execution_quality", result)
            self.assertIn("slippage_data_available", result)
    
    async def test_get_execution_context_no_mt5_service(self):
        """Test execution context when MT5 service not available"""
        monitor = ExecutionQualityMonitor(mt5_service=None)
        
        with patch('infra.execution_quality_monitor.mt5') as mock_mt5:
            mock_tick = Mock()
            mock_tick.bid = 100.0
            mock_tick.ask = 100.1
            mock_mt5.symbol_info_tick.return_value = mock_tick
            
            mock_symbol_info = Mock()
            mock_symbol_info.point = 0.01
            mock_mt5.symbol_info.return_value = mock_symbol_info
            
            result = await monitor.get_execution_context("XAUUSDc")
            
            self.assertIsNotNone(result)
            self.assertIn("current_spread_points", result)
    
    async def test_get_current_spread(self):
        """Test getting current spread"""
        mock_quote = Mock()
        mock_quote.bid = 100.0
        mock_quote.ask = 100.15
        self.mt5_service.get_quote = Mock(return_value=mock_quote)
        
        with patch('infra.execution_quality_monitor.mt5') as mock_mt5:
            mock_symbol_info = Mock()
            mock_symbol_info.point = 0.01
            mock_mt5.symbol_info.return_value = mock_symbol_info
            
            spread = await self.monitor._get_current_spread("XAUUSDc")
            
            self.assertIsNotNone(spread)
            self.assertGreater(spread, 0)
    
    async def test_get_execution_context_elevated_spread(self):
        """Test execution context with elevated spread"""
        # Setup spread tracker with normal spreads
        for i in range(10):
            self.spread_tracker.update_spread("XAUUSDc", 100.0, 100.1)  # Normal spread
        
        # Mock current spread as elevated
        mock_quote = Mock()
        mock_quote.bid = 100.0
        mock_quote.ask = 100.25  # Elevated spread (2.5x normal)
        self.mt5_service.get_quote = Mock(return_value=mock_quote)
        
        with patch('infra.execution_quality_monitor.mt5') as mock_mt5:
            mock_symbol_info = Mock()
            mock_symbol_info.point = 0.01
            mock_mt5.symbol_info.return_value = mock_symbol_info
            
            result = await self.monitor.get_execution_context("XAUUSDc")
            
            self.assertTrue(result["is_spread_elevated"])
            self.assertGreater(result["spread_vs_median"], 1.5)
    
    async def test_calculate_slippage_metrics(self):
        """Test slippage metrics calculation"""
        result = await self.monitor._calculate_slippage_metrics("XAUUSDc")
        
        self.assertFalse(result["slippage_data_available"])
        self.assertIsNone(result["avg_slippage_points"])
        self.assertEqual(result["slippage_sample_size"], 0)


if __name__ == '__main__':
    unittest.main()

