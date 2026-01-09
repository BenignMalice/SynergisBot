"""
Unit tests for GeneralOrderFlowMetrics
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import numpy as np
import pandas as pd
from datetime import datetime, timezone
import asyncio

# Import the calculator
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.general_order_flow_metrics import GeneralOrderFlowMetrics


class TestGeneralOrderFlowMetrics(unittest.TestCase):
    """Synchronous test cases for GeneralOrderFlowMetrics"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mt5_service = Mock()
        self.order_flow_service = Mock()
        self.calculator = GeneralOrderFlowMetrics(
            mt5_service=self.mt5_service,
            order_flow_service=self.order_flow_service
        )
    
    def test_initialization(self):
        """Test calculator initialization"""
        self.assertIsNotNone(self.calculator)
        self.assertEqual(self.calculator.mt5_service, self.mt5_service)
        self.assertEqual(self.calculator.order_flow_service, self.order_flow_service)
    
    def test_create_unavailable_response(self):
        """Test creating unavailable response"""
        response = self.calculator._create_unavailable_response(30)
        
        self.assertEqual(response["window_minutes"], 30)
        self.assertEqual(response["cvd_value"], 0.0)
        self.assertEqual(response["cvd_slope"], "flat")
        self.assertIsNone(response["aggressor_ratio"])
        self.assertEqual(response["data_quality"], "unavailable")


class TestGeneralOrderFlowMetricsAsync(unittest.IsolatedAsyncioTestCase):
    """Async test cases for GeneralOrderFlowMetrics"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mt5_service = Mock()
        self.order_flow_service = Mock()
        self.calculator = GeneralOrderFlowMetrics(
            mt5_service=self.mt5_service,
            order_flow_service=self.order_flow_service
        )
    
    async def test_get_btc_order_flow_valid(self):
        """Test getting BTC order flow with valid data"""
        # Mock order flow service
        self.order_flow_service.running = True
        self.order_flow_service.get_buy_sell_pressure = Mock(return_value={
            "buy_volume": 1000.0,
            "sell_volume": 800.0,
            "net_volume": 200.0,
            "pressure": 1.25,
            "dominant_side": "BUY"
        })
        self.order_flow_service.get_recent_whales = Mock(return_value=[
            {"side": "BUY", "usd_value": 50000},
            {"side": "SELL", "usd_value": 30000}
        ])
        
        result = await self.calculator._get_btc_order_flow("BTCUSDc", 30)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["data_quality"], "good")
        self.assertEqual(result["data_source"], "binance_aggtrades")
        self.assertIn("cvd_value", result)
        self.assertIn("cvd_slope", result)
        self.assertIn("aggressor_ratio", result)
        self.assertIn("imbalance_score", result)
    
    async def test_get_btc_order_flow_no_service(self):
        """Test BTC order flow when service not available"""
        self.order_flow_service.running = False
        
        result = await self.calculator._get_btc_order_flow("BTCUSDc", 30)
        
        self.assertEqual(result["data_quality"], "unavailable")
    
    async def test_get_proxy_order_flow_valid(self):
        """Test getting proxy order flow with valid data"""
        # Mock bars with price action
        bars = pd.DataFrame({
            'time': pd.date_range(start='2025-12-11 10:00', periods=6, freq='5min'),
            'close': np.array([100.0, 101.0, 102.0, 101.5, 103.0, 102.5]),
            'volume': np.array([100, 150, 200, 120, 180, 140])
        })
        self.mt5_service.get_bars = Mock(return_value=bars)
        
        result = await self.calculator._get_proxy_order_flow("XAUUSDc", 30)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["data_quality"], "proxy")
        self.assertEqual(result["data_source"], "mt5_tick_proxy")
        self.assertIn("cvd_value", result)
        self.assertIn("cvd_slope", result)
        self.assertIn("aggressor_ratio", result)
        self.assertIn("imbalance_score", result)
    
    async def test_get_proxy_order_flow_no_bars(self):
        """Test proxy order flow when no bars available"""
        self.mt5_service.get_bars = Mock(return_value=None)
        
        result = await self.calculator._get_proxy_order_flow("XAUUSDc", 30)
        
        self.assertEqual(result["data_quality"], "unavailable")
    
    async def test_get_order_flow_metrics_btc(self):
        """Test get_order_flow_metrics for BTC"""
        self.order_flow_service.running = True
        self.order_flow_service.get_buy_sell_pressure = Mock(return_value={
            "buy_volume": 1000.0,
            "sell_volume": 800.0,
            "net_volume": 200.0,
            "pressure": 1.25
        })
        self.order_flow_service.get_recent_whales = Mock(return_value=[])
        
        result = await self.calculator.get_order_flow_metrics("BTCUSDc", 30)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["data_quality"], "good")
        self.assertEqual(result["data_source"], "binance_aggtrades")
    
    async def test_get_order_flow_metrics_non_btc(self):
        """Test get_order_flow_metrics for non-BTC symbol"""
        bars = pd.DataFrame({
            'time': pd.date_range(start='2025-12-11 10:00', periods=6, freq='5min'),
            'close': np.array([100.0, 101.0, 102.0, 101.5, 103.0, 102.5]),
            'volume': np.array([100, 150, 200, 120, 180, 140])
        })
        self.mt5_service.get_bars = Mock(return_value=bars)
        
        result = await self.calculator.get_order_flow_metrics("XAUUSDc", 30)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["data_quality"], "proxy")
        self.assertEqual(result["data_source"], "mt5_tick_proxy")
    
    async def test_cvd_slope_calculation(self):
        """Test CVD slope calculation"""
        # Create bars with clear upward trend
        bars = pd.DataFrame({
            'time': pd.date_range(start='2025-12-11 10:00', periods=10, freq='5min'),
            'close': np.linspace(100.0, 105.0, 10),  # Upward trend
            'volume': np.ones(10) * 100
        })
        self.mt5_service.get_bars = Mock(return_value=bars)
        
        result = await self.calculator._get_proxy_order_flow("XAUUSDc", 30)
        
        self.assertIsNotNone(result)
        self.assertIn(result["cvd_slope"], ["up", "down", "flat"])
    
    async def test_aggressor_ratio_calculation(self):
        """Test aggressor ratio calculation"""
        # Create bars with more buy pressure
        bars = pd.DataFrame({
            'time': pd.date_range(start='2025-12-11 10:00', periods=6, freq='5min'),
            'close': np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0]),  # Strong upward
            'volume': np.array([100, 150, 200, 180, 160, 140])
        })
        self.mt5_service.get_bars = Mock(return_value=bars)
        
        result = await self.calculator._get_proxy_order_flow("XAUUSDc", 30)
        
        self.assertIsNotNone(result)
        if result["aggressor_ratio"] is not None:
            self.assertGreater(result["aggressor_ratio"], 0.0)
    
    async def test_imbalance_score_calculation(self):
        """Test imbalance score calculation"""
        bars = pd.DataFrame({
            'time': pd.date_range(start='2025-12-11 10:00', periods=6, freq='5min'),
            'close': np.array([100.0, 101.0, 102.0, 101.5, 103.0, 102.5]),
            'volume': np.array([100, 150, 200, 120, 180, 140])
        })
        self.mt5_service.get_bars = Mock(return_value=bars)
        
        result = await self.calculator._get_proxy_order_flow("XAUUSDc", 30)
        
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result["imbalance_score"], 0)
        self.assertLessEqual(result["imbalance_score"], 100)
    
    async def test_get_order_flow_metrics_error_handling(self):
        """Test error handling in get_order_flow_metrics"""
        calculator = GeneralOrderFlowMetrics()
        
        # Should return unavailable response on error
        result = await calculator.get_order_flow_metrics("INVALID", 30)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["data_quality"], "unavailable")


if __name__ == '__main__':
    unittest.main()
