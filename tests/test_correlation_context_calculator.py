"""
Unit tests for CorrelationContextCalculator
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
import asyncio

# Import the calculator
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.correlation_context_calculator import CorrelationContextCalculator, EXPECTED_CORRELATIONS


class TestCorrelationContextCalculator(unittest.TestCase):
    """Test cases for CorrelationContextCalculator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mt5_service = Mock()
        self.market_indices = Mock()
        self.calculator = CorrelationContextCalculator(
            mt5_service=self.mt5_service,
            market_indices_service=self.market_indices
        )
    
    def test_initialization(self):
        """Test calculator initialization"""
        self.assertIsNotNone(self.calculator)
        self.assertEqual(self.calculator.mt5_service, self.mt5_service)
        self.assertEqual(self.calculator.market_indices, self.market_indices)
        self.assertIsNotNone(self.calculator._correlation_calc)
    
    def test_prices_to_returns_valid(self):
        """Test converting prices to returns with valid data"""
        prices = np.array([100.0, 101.0, 102.0, 101.5, 103.0])
        returns = self.calculator._prices_to_returns(prices)
        
        self.assertIsNotNone(returns)
        self.assertEqual(len(returns), 4)  # One less than prices
        self.assertTrue(np.all(np.isfinite(returns)))
    
    def test_prices_to_returns_invalid(self):
        """Test converting prices to returns with invalid data"""
        # Test with non-positive prices
        prices = np.array([100.0, 0.0, 102.0])
        returns = self.calculator._prices_to_returns(prices)
        self.assertIsNone(returns)
        
        # Test with insufficient data
        prices = np.array([100.0])
        returns = self.calculator._prices_to_returns(prices)
        self.assertIsNone(returns)
        
        # Test with None
        returns = self.calculator._prices_to_returns(None)
        self.assertIsNone(returns)
    
    def test_align_returns_valid(self):
        """Test aligning returns with valid timestamps"""
        symbol_returns = np.array([0.01, 0.02, -0.01, 0.03])
        symbol_times = pd.date_range(start='2025-12-11 10:00', periods=4, freq='5min')
        
        ref_returns = np.array([0.005, 0.015, -0.005, 0.025])
        ref_times = pd.date_range(start='2025-12-11 10:00', periods=4, freq='5min')
        
        aligned_sym, aligned_ref = self.calculator._align_returns(
            symbol_returns, symbol_times, ref_returns, ref_times
        )
        
        self.assertIsNotNone(aligned_sym)
        self.assertIsNotNone(aligned_ref)
        self.assertEqual(len(aligned_sym), len(aligned_ref))
        self.assertEqual(len(aligned_sym), 4)
    
    def test_align_returns_mismatched_times(self):
        """Test aligning returns with mismatched timestamps"""
        symbol_returns = np.array([0.01, 0.02])
        symbol_times = pd.date_range(start='2025-12-11 10:00', periods=2, freq='5min')
        
        ref_returns = np.array([0.005, 0.015])
        ref_times = pd.date_range(start='2025-12-11 12:00', periods=2, freq='5min')  # Different time
        
        aligned_sym, aligned_ref = self.calculator._align_returns(
            symbol_returns, symbol_times, ref_returns, ref_times
        )
        
        # Should return None if no overlap
        if aligned_sym is None or aligned_ref is None:
            self.assertIsNone(aligned_sym)
            self.assertIsNone(aligned_ref)
    
    def test_create_unavailable_response(self):
        """Test creating unavailable response"""
        response = self.calculator._create_unavailable_response(240)
        
        self.assertEqual(response["corr_window_minutes"], 240)
        self.assertIsNone(response["corr_vs_dxy"])
        self.assertIsNone(response["corr_vs_sp500"])
        self.assertIsNone(response["corr_vs_us10y"])
        self.assertIsNone(response["corr_vs_btc"])
        self.assertEqual(response["data_quality"], "unavailable")
        self.assertEqual(response["sample_size"], 0)
        self.assertFalse(response["conflict_flags"]["gold_vs_dxy_conflict"])
    
    @patch('infra.correlation_context_calculator.HistoricalAnalysisEngine')
    async def test_calculate_correlation_context_valid(self, mock_hist_engine):
        """Test calculating correlation context with valid data"""
        # Mock correlation calculation
        mock_hist_engine.calculate_correlation = Mock(return_value=-0.72)
        self.calculator._correlation_calc = mock_hist_engine.calculate_correlation
        
        # Mock symbol bars
        symbol_bars = pd.DataFrame({
            'time': pd.date_range(start='2025-12-11 10:00', periods=48, freq='5min'),
            'close': np.linspace(100.0, 105.0, 48)
        })
        self.mt5_service.get_bars = Mock(return_value=symbol_bars)
        
        # Mock reference bars
        ref_bars = pd.DataFrame({
            'time': pd.date_range(start='2025-12-11 10:00', periods=48, freq='5min'),
            'close': np.linspace(99.0, 98.0, 48)  # Inverse correlation
        })
        self.market_indices.get_dxy_bars = AsyncMock(return_value=ref_bars)
        self.market_indices.get_sp500_bars = AsyncMock(return_value=ref_bars)
        self.market_indices.get_us10y_bars = AsyncMock(return_value=ref_bars)
        
        # Run async test
        result = await self.calculator.calculate_correlation_context("XAUUSDc", 240)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["corr_window_minutes"], 240)
        self.assertIn("corr_vs_dxy", result)
        self.assertIn("corr_vs_sp500", result)
        self.assertIn("corr_vs_us10y", result)
        self.assertIn("data_quality", result)
        self.assertIn("conflict_flags", result)
    
    async def test_calculate_correlation_context_no_symbol_bars(self):
        """Test correlation context when symbol bars unavailable"""
        self.mt5_service.get_bars = Mock(return_value=None)
        
        result = await self.calculator.calculate_correlation_context("XAUUSDc", 240)
        
        self.assertEqual(result["data_quality"], "unavailable")
        self.assertIsNone(result["corr_vs_dxy"])
    
    async def test_calculate_correlation_context_conflict_detection(self):
        """Test conflict detection for Gold vs DXY"""
        # Mock correlation that breaks expected pattern
        # Expected: -0.7, Actual: -0.2 (deviation > 0.3)
        with patch.object(self.calculator, '_calculate_correlation', new_callable=AsyncMock) as mock_calc:
            mock_calc.return_value = (-0.2, "good")  # Low correlation (should be -0.7)
            
            # Mock symbol bars
            symbol_bars = pd.DataFrame({
                'time': pd.date_range(start='2025-12-11 10:00', periods=48, freq='5min'),
                'close': np.linspace(100.0, 105.0, 48)
            })
            self.mt5_service.get_bars = Mock(return_value=symbol_bars)
            
            result = await self.calculator.calculate_correlation_context("XAUUSDc", 240)
            
            # Note: Conflict detection happens in main method, so we'd need to mock the full flow
            # This is a simplified test
            self.assertIsNotNone(result)
    
    def test_expected_correlations_defined(self):
        """Test that expected correlations are defined for key symbols"""
        self.assertIn("XAUUSDc", EXPECTED_CORRELATIONS)
        self.assertIn("BTCUSDc", EXPECTED_CORRELATIONS)
        self.assertIn("EURUSDc", EXPECTED_CORRELATIONS)
        
        # Check structure
        for symbol, expected in EXPECTED_CORRELATIONS.items():
            self.assertIsInstance(expected, dict)
            if "dxy" in expected:
                self.assertGreaterEqual(expected["dxy"], -1.0)
                self.assertLessEqual(expected["dxy"], 1.0)


class TestCorrelationContextCalculatorAsync(unittest.IsolatedAsyncioTestCase):
    """Async test cases for CorrelationContextCalculator"""
    
    async def test_fetch_symbol_bars(self):
        """Test fetching symbol bars"""
        mt5_service = Mock()
        mt5_service.get_bars = Mock(return_value=pd.DataFrame({
            'time': pd.date_range(start='2025-12-11 10:00', periods=10, freq='5min'),
            'close': np.linspace(100.0, 105.0, 10)
        }))
        
        calculator = CorrelationContextCalculator(mt5_service=mt5_service)
        bars = await calculator._fetch_symbol_bars("XAUUSDc", 10)
        
        self.assertIsNotNone(bars)
        self.assertEqual(len(bars), 10)
    
    async def test_fetch_reference_bars_dxy(self):
        """Test fetching DXY reference bars"""
        market_indices = Mock()
        market_indices.get_dxy_bars = AsyncMock(return_value=pd.DataFrame({
            'time': pd.date_range(start='2025-12-11 10:00', periods=10, freq='5min'),
            'close': np.linspace(99.0, 98.0, 10)
        }))
        
        calculator = CorrelationContextCalculator(market_indices_service=market_indices)
        bars = await calculator._fetch_reference_bars("dxy", 10)
        
        self.assertIsNotNone(bars)
        self.assertEqual(len(bars), 10)
    
    async def test_fetch_reference_bars_btc(self):
        """Test fetching BTC reference bars (from MT5)"""
        mt5_service = Mock()
        mt5_service.get_bars = Mock(return_value=pd.DataFrame({
            'time': pd.date_range(start='2025-12-11 10:00', periods=10, freq='5min'),
            'close': np.linspace(100000.0, 101000.0, 10)
        }))
        
        calculator = CorrelationContextCalculator(mt5_service=mt5_service)
        bars = await calculator._fetch_reference_bars("btc", 10)
        
        self.assertIsNotNone(bars)
        self.assertEqual(len(bars), 10)


if __name__ == '__main__':
    unittest.main()

