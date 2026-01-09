"""
Phase 2 Tests for Tick Metrics Integration

Tests integration of tick_metrics into desktop_agent.py and analysis_formatting_helpers.py:
- tick_metrics retrieval in tool_analyse_symbol_full
- format_tick_metrics_summary function
- Integration between components
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock MetaTrader5 before importing
class MockMT5:
    TICK_FLAG_BUY = 2
    TICK_FLAG_SELL = 4
    COPY_TICKS_ALL = 1
    
    @staticmethod
    def initialize():
        return True
    
    @staticmethod
    def is_connected():
        return True
    
    @staticmethod
    def terminal_info():
        class TerminalInfo:
            connected = True
        return TerminalInfo()
    
    @staticmethod
    def last_error():
        return (0, "No error")
    
    @staticmethod
    def symbol_info_tick(symbol):
        class Tick:
            bid = 50000.0
            ask = 50001.0
        return Tick()

sys.modules['MetaTrader5'] = MockMT5
import MetaTrader5 as mt5

# Import modules to test
from infra.analysis_formatting_helpers import format_tick_metrics_summary
from infra.tick_metrics import get_tick_metrics_instance, set_tick_metrics_instance, clear_tick_metrics_instance


class TestFormatTickMetricsSummary(unittest.TestCase):
    """Tests for format_tick_metrics_summary function"""
    
    def setUp(self):
        """Set up test fixtures"""
        pass
    
    def test_empty_tick_metrics(self):
        """Test with None/empty tick_metrics"""
        result = format_tick_metrics_summary(None)
        self.assertEqual(result, "")
        
        result = format_tick_metrics_summary({})
        self.assertEqual(result, "")
    
    def test_market_closed(self):
        """Test with market closed (data_available: false)"""
        tick_metrics = {
            "metadata": {
                "data_available": False,
                "market_status": "closed"
            }
        }
        result = format_tick_metrics_summary(tick_metrics)
        self.assertIn("Market closed", result)
        self.assertIn("no tick data", result)
    
    def test_previous_day_loading(self):
        """Test with previous_day still loading"""
        tick_metrics = {
            "metadata": {
                "data_available": True,
                "previous_day_loading": True
            },
            "M5": {
                "delta_volume": 1000.0,
                "dominant_side": "BUY",
                "cvd_slope": "up",
                "spread": {"mean": 1.5, "std": 0.3}
            }
        }
        result = format_tick_metrics_summary(tick_metrics)
        self.assertIn("previous_day loading", result)
        self.assertIn("M5", result)
    
    def test_full_metrics_formatting(self):
        """Test with complete tick metrics"""
        tick_metrics = {
            "metadata": {
                "data_available": True,
                "previous_day_loading": False
            },
            "M5": {
                "delta_volume": -42500.0,
                "dominant_side": "SELL",
                "cvd_slope": "down",
                "spread": {"mean": 1.8, "std": 0.3}
            },
            "M15": {
                "realized_volatility": 0.0012,
                "volatility_ratio": 1.2,
                "absorption": {"count": 3}
            },
            "H1": {
                "volatility_ratio": 1.35,
                "tick_rate": 18.2
            },
            "previous_hour": {
                "tick_count": 52000,
                "net_delta": -180000.0,
                "dominant_side": "SELL"
            }
        }
        result = format_tick_metrics_summary(tick_metrics)
        
        # Check header
        self.assertIn("TICK MICROSTRUCTURE", result)
        
        # Check M5 summary
        self.assertIn("M5", result)
        self.assertIn("SELL", result)
        self.assertIn("down", result)
        
        # Check M15 summary
        self.assertIn("M15", result)
        self.assertIn("3 zones", result)
        
        # Check H1 summary
        self.assertIn("H1", result)
        self.assertIn("expanding", result)
        self.assertIn("18.2/sec", result)
        
        # Check previous hour summary
        self.assertIn("Hour", result)
        self.assertIn("52K ticks", result)
        self.assertIn("-180K", result)
    
    def test_partial_metrics(self):
        """Test with partial metrics (only M5 available)"""
        tick_metrics = {
            "metadata": {
                "data_available": True,
                "previous_day_loading": False
            },
            "M5": {
                "delta_volume": 5000.0,
                "dominant_side": "BUY",
                "cvd_slope": "up",
                "spread": {"mean": 2.0, "std": 0.5}
            }
        }
        result = format_tick_metrics_summary(tick_metrics)
        self.assertIn("M5", result)
        self.assertIn("BUY", result)
    
    def test_error_handling(self):
        """Test error handling in formatting"""
        # Invalid structure that might cause errors
        tick_metrics = {
            "metadata": {
                "data_available": True
            },
            "M5": None  # Invalid value
        }
        # Should not raise exception, should return error message or empty string
        try:
            result = format_tick_metrics_summary(tick_metrics)
            # Should either return empty string or error message
            self.assertIsInstance(result, str)
        except Exception as e:
            self.fail(f"format_tick_metrics_summary raised exception: {e}")


class TestTickMetricsIntegration(unittest.TestCase):
    """Tests for tick_metrics integration in desktop_agent"""
    
    def setUp(self):
        """Set up test fixtures"""
        clear_tick_metrics_instance()
    
    def tearDown(self):
        """Clean up"""
        clear_tick_metrics_instance()
    
    def test_get_tick_metrics_instance_none(self):
        """Test getting instance when not set"""
        instance = get_tick_metrics_instance()
        self.assertIsNone(instance)
    
    def test_set_and_get_instance(self):
        """Test setting and getting instance"""
        mock_generator = Mock()
        mock_generator.get_latest_metrics = Mock(return_value={
            "M5": {"delta_volume": 1000.0},
            "metadata": {"data_available": True}
        })
        
        set_tick_metrics_instance(mock_generator)
        instance = get_tick_metrics_instance()
        self.assertIs(instance, mock_generator)
    
    def test_get_latest_metrics_call(self):
        """Test that get_latest_metrics is called correctly"""
        mock_generator = Mock()
        mock_metrics = {
            "M5": {"delta_volume": 1000.0},
            "metadata": {"data_available": True, "symbol": "BTCUSDc"}
        }
        mock_generator.get_latest_metrics = Mock(return_value=mock_metrics)
        
        set_tick_metrics_instance(mock_generator)
        
        # Simulate the code in tool_analyse_symbol_full
        tick_generator = get_tick_metrics_instance()
        if tick_generator:
            tick_metrics = tick_generator.get_latest_metrics("BTCUSDc")
        
        self.assertIsNotNone(tick_metrics)
        self.assertEqual(tick_metrics, mock_metrics)
        mock_generator.get_latest_metrics.assert_called_once_with("BTCUSDc")
    
    def test_get_latest_metrics_none(self):
        """Test when generator returns None"""
        mock_generator = Mock()
        mock_generator.get_latest_metrics = Mock(return_value=None)
        
        set_tick_metrics_instance(mock_generator)
        
        tick_generator = get_tick_metrics_instance()
        if tick_generator:
            tick_metrics = tick_generator.get_latest_metrics("BTCUSDc")
        
        self.assertIsNone(tick_metrics)
    
    def test_integration_format_tick_metrics(self):
        """Test integration: get metrics and format them"""
        # Create mock generator
        mock_generator = Mock()
        mock_metrics = {
            "metadata": {
                "data_available": True,
                "previous_day_loading": False
            },
            "M5": {
                "delta_volume": -10000.0,
                "dominant_side": "SELL",
                "cvd_slope": "down",
                "spread": {"mean": 2.0, "std": 0.5}
            },
            "previous_hour": {
                "tick_count": 10000,
                "net_delta": -50000.0,
                "dominant_side": "SELL"
            }
        }
        mock_generator.get_latest_metrics = Mock(return_value=mock_metrics)
        
        set_tick_metrics_instance(mock_generator)
        
        # Simulate tool_analyse_symbol_full flow
        tick_metrics = None
        try:
            tick_generator = get_tick_metrics_instance()
            if tick_generator:
                tick_metrics = tick_generator.get_latest_metrics("BTCUSDc")
        except Exception:
            pass
        
        # Format the metrics
        if tick_metrics:
            formatted = format_tick_metrics_summary(tick_metrics)
            self.assertIsNotNone(formatted)
            self.assertIn("TICK MICROSTRUCTURE", formatted)
            self.assertIn("M5", formatted)
            self.assertIn("SELL", formatted)


class TestFormatTickMetricsEdgeCases(unittest.TestCase):
    """Tests for edge cases in format_tick_metrics_summary"""
    
    def test_missing_timeframes(self):
        """Test with missing timeframes"""
        tick_metrics = {
            "metadata": {
                "data_available": True,
                "previous_day_loading": False
            }
            # No M5, M15, H1, previous_hour
        }
        result = format_tick_metrics_summary(tick_metrics)
        # Should return header only or empty
        self.assertIsInstance(result, str)
    
    def test_zero_values(self):
        """Test with zero values"""
        tick_metrics = {
            "metadata": {
                "data_available": True,
                "previous_day_loading": False
            },
            "M5": {
                "delta_volume": 0.0,
                "dominant_side": "NEUTRAL",
                "cvd_slope": "flat",
                "spread": {"mean": 0.0, "std": 0.0}
            }
        }
        result = format_tick_metrics_summary(tick_metrics)
        self.assertIn("M5", result)
        self.assertIn("NEUTRAL", result)
    
    def test_very_large_values(self):
        """Test with very large delta values"""
        tick_metrics = {
            "metadata": {
                "data_available": True,
                "previous_day_loading": False
            },
            "M5": {
                "delta_volume": 1000000.0,  # 1M
                "dominant_side": "BUY",
                "cvd_slope": "up",
                "spread": {"mean": 10.0, "std": 2.0}
            },
            "previous_hour": {
                "tick_count": 1000000,  # 1M ticks
                "net_delta": 5000000.0,  # 5M
                "dominant_side": "BUY"
            }
        }
        result = format_tick_metrics_summary(tick_metrics)
        # Should format large numbers correctly (e.g., "1000.0K")
        self.assertIn("M5", result)
        self.assertIn("BUY", result)


def run_tests():
    """Run all Phase 2 tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFormatTickMetricsSummary))
    suite.addTests(loader.loadTestsFromTestCase(TestTickMetricsIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestFormatTickMetricsEdgeCases))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 70)
    print("Phase 2 Tick Metrics Integration Tests")
    print("=" * 70)
    print()
    
    success = run_tests()
    
    print()
    print("=" * 70)
    if success:
        print("All Phase 2 tests passed!")
    else:
        print("Some tests failed. Check output above.")
    print("=" * 70)
    
    sys.exit(0 if success else 1)

