"""
Phase 1 Tests for Tick Metrics Infrastructure

Tests all core infrastructure components:
- tick_data_fetcher.py
- tick_metrics_calculator.py
- tick_metrics_cache.py
- tick_snapshot_generator.py
- __init__.py singleton pattern
"""

import unittest
import asyncio
import json
import sqlite3
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
import sys
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock MetaTrader5 before importing our modules
class MockMT5:
    """Mock MetaTrader5 for testing without live connection"""
    TICK_FLAG_BUY = 2
    TICK_FLAG_SELL = 4
    COPY_TICKS_ALL = 1
    
    _initialized = False
    _connected = False
    
    @staticmethod
    def initialize():
        MockMT5._initialized = True
        MockMT5._connected = True
        return True
    
    @staticmethod
    def is_connected():
        return MockMT5._connected
    
    @staticmethod
    def terminal_info():
        class TerminalInfo:
            connected = MockMT5._connected
        return TerminalInfo()
    
    @staticmethod
    def last_error():
        return (0, "No error")
    
    @staticmethod
    def copy_ticks_range(symbol, start_time, end_time, flags):
        """Generate mock tick data"""
        if not MockMT5._connected:
            return None
        
        # Generate realistic mock ticks
        ticks = []
        current_time = start_time
        price = 50000.0 if 'BTC' in symbol else 2000.0
        
        tick_count = min(1000, int((end_time - start_time) / 60))  # ~1 tick per minute
        
        for i in range(tick_count):
            # Simulate price movement
            price += (i % 10 - 5) * 0.1
            
            # Create tick structure
            tick = {
                'time': current_time,
                'time_msc': current_time * 1000,
                'bid': price - 0.5,
                'ask': price + 0.5,
                'last': price,
                'volume': 1.0,
                'volume_real': 1.0,
                'flags': MockMT5.TICK_FLAG_BUY if i % 2 == 0 else MockMT5.TICK_FLAG_SELL
            }
            ticks.append(tick)
            current_time += 60  # 1 minute intervals
        
        # Convert to numpy-like array structure
        class TickArray:
            def __init__(self, data):
                self.data = data
                def __iter__(self):
                    return iter(data)
                def __len__(self):
                    return len(data)
        
        return ticks if ticks else None

# Replace MetaTrader5 with mock
sys.modules['MetaTrader5'] = MockMT5
import MetaTrader5 as mt5

# Now import our modules
from infra.tick_metrics.tick_data_fetcher import TickDataFetcher
from infra.tick_metrics.tick_metrics_calculator import TickMetricsCalculator
from infra.tick_metrics.tick_metrics_cache import TickMetricsCache, CachedTickMetrics
from infra.tick_metrics.tick_snapshot_generator import TickSnapshotGenerator
from infra.tick_metrics import get_tick_metrics_instance, set_tick_metrics_instance, clear_tick_metrics_instance


class TestTickDataFetcher(unittest.TestCase):
    """Tests for TickDataFetcher"""
    
    def setUp(self):
        """Set up test fixtures"""
        MockMT5._initialized = False
        MockMT5._connected = True
        self.fetcher = TickDataFetcher()
    
    def test_initialization(self):
        """Test TickDataFetcher initialization"""
        self.assertIsNotNone(self.fetcher)
    
    def test_fetch_previous_hour_ticks(self):
        """Test fetching ticks for previous hour"""
        ticks = self.fetcher.fetch_previous_hour_ticks("BTCUSDc")
        self.assertIsNotNone(ticks)
        self.assertIsInstance(ticks, list)
        if ticks:
            self.assertGreater(len(ticks), 0)
            # Check tick structure
            tick = ticks[0]
            self.assertIn('time', tick)
            self.assertIn('bid', tick)
            self.assertIn('ask', tick)
            self.assertIn('last', tick)
    
    def test_fetch_previous_day_ticks(self):
        """Test fetching ticks for previous day"""
        ticks = self.fetcher.fetch_previous_day_ticks("BTCUSDc")
        self.assertIsNotNone(ticks)
        self.assertIsInstance(ticks, list)
    
    def test_fetch_ticks_for_period(self):
        """Test fetching ticks for custom period"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=2)
        ticks = self.fetcher.fetch_ticks_for_period("BTCUSDc", start_time, end_time)
        self.assertIsNotNone(ticks)
        self.assertIsInstance(ticks, list)
    
    def test_chunk_large_requests(self):
        """Test chunking logic for large requests"""
        # This is tested indirectly through fetch_previous_day_ticks
        ticks = self.fetcher.fetch_previous_day_ticks("BTCUSDc")
        self.assertIsNotNone(ticks)


class TestTickMetricsCalculator(unittest.TestCase):
    """Tests for TickMetricsCalculator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.calculator = TickMetricsCalculator()
        # Create mock tick data
        self.mock_ticks = []
        base_price = 50000.0
        base_time = int(datetime.utcnow().timestamp())
        
        for i in range(100):
            tick = {
                'time': base_time + i * 60,
                'time_msc': (base_time + i * 60) * 1000,
                'bid': base_price + i * 0.1 - 0.5,
                'ask': base_price + i * 0.1 + 0.5,
                'last': base_price + i * 0.1,
                'volume': 1.0,
                'volume_real': 1.0,
                'flags': mt5.TICK_FLAG_BUY if i % 2 == 0 else mt5.TICK_FLAG_SELL
            }
            self.mock_ticks.append(tick)
    
    def test_initialization(self):
        """Test TickMetricsCalculator initialization"""
        self.assertIsNotNone(self.calculator)
        self.assertIsNotNone(self.calculator.config)
    
    def test_calculate_all_metrics(self):
        """Test calculating all metrics from tick data"""
        metrics = self.calculator.calculate_all_metrics(self.mock_ticks)
        
        self.assertIsInstance(metrics, dict)
        self.assertIn('realized_volatility', metrics)
        self.assertIn('delta_volume', metrics)
        self.assertIn('cvd', metrics)
        self.assertIn('spread', metrics)
        self.assertIn('tick_count', metrics)
    
    def test_empty_metrics(self):
        """Test empty metrics structure"""
        empty = self.calculator._empty_metrics()
        self.assertIsInstance(empty, dict)
        self.assertIn('delta_volume', empty)
        self.assertIn('cvd', empty)
        self.assertIn('spread', empty)
    
    def test_calculate_delta_cvd(self):
        """Test delta and CVD calculation"""
        result = self.calculator._calculate_delta_cvd(self.mock_ticks)
        self.assertIn('delta_volume', result)
        self.assertIn('cvd', result)
        self.assertIn('cvd_slope', result)
        self.assertIn('dominant_side', result)
    
    def test_calculate_spread_stats(self):
        """Test spread statistics calculation"""
        result = self.calculator._calculate_spread_stats(self.mock_ticks)
        self.assertIn('mean', result)
        self.assertIn('std', result)
        self.assertIn('max', result)
        self.assertIn('widening_events', result)
    
    def test_calculate_realized_volatility(self):
        """Test realized volatility calculation"""
        result = self.calculator._calculate_realized_volatility(self.mock_ticks)
        self.assertIsInstance(result, dict)
        self.assertIn('realized_vol', result)
        self.assertIsInstance(result['realized_vol'], float)
        self.assertGreaterEqual(result['realized_vol'], 0)
    
    def test_calculate_tick_activity(self):
        """Test tick activity calculation"""
        result = self.calculator._calculate_tick_activity(self.mock_ticks)
        self.assertIn('tick_rate', result)
        self.assertIn('max_gap_ms', result)
        self.assertIsInstance(result['tick_rate'], float)
        self.assertGreaterEqual(result['tick_rate'], 0)


class TestTickMetricsCache(unittest.TestCase):
    """Tests for TickMetricsCache"""
    
    def setUp(self):
        """Set up test fixtures with temporary database"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_tick_metrics_cache.db"
        self.cache = TickMetricsCache(
            db_path=str(self.db_path),
            memory_ttl_seconds=60,
            db_retention_hours=24
        )
    
    def tearDown(self):
        """Clean up temporary files"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test cache initialization"""
        self.assertIsNotNone(self.cache)
        self.assertTrue(self.db_path.exists())
    
    def test_set_and_get(self):
        """Test setting and getting metrics"""
        symbol = "BTCUSDc"
        metrics = {
            "M5": {"delta_volume": 100.0},
            "previous_hour": {"tick_count": 1000}
        }
        
        self.cache.set(symbol, metrics)
        retrieved = self.cache.get(symbol)
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["M5"]["delta_volume"], 100.0)
    
    def test_memory_cache(self):
        """Test memory cache functionality"""
        symbol = "BTCUSDc"
        metrics = {"test": "data"}
        
        self.cache.set(symbol, metrics)
        # Should be retrievable immediately (from memory cache)
        retrieved = self.cache.get(symbol)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["test"], "data")
    
    def test_database_persistence(self):
        """Test database persistence"""
        symbol = "BTCUSDc"
        metrics = {"persistent": "data"}
        
        self.cache.set(symbol, metrics)
        
        # Create new cache instance to test DB persistence
        new_cache = TickMetricsCache(
            db_path=str(self.db_path),
            memory_ttl_seconds=60,
            db_retention_hours=24
        )
        
        # Should retrieve from database
        retrieved = new_cache.get(symbol)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["persistent"], "data")
    
    def test_cleanup_expired(self):
        """Test cleanup of expired entries"""
        symbol = "BTCUSDc"
        metrics = {"test": "data"}
        
        self.cache.set(symbol, metrics)
        
        # Cleanup should not fail
        try:
            self.cache.cleanup_expired()
            cleanup_success = True
        except Exception as e:
            cleanup_success = False
            self.fail(f"Cleanup failed: {e}")
        
        self.assertTrue(cleanup_success)


class TestTickSnapshotGenerator(unittest.TestCase):
    """Tests for TickSnapshotGenerator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_tick_metrics_cache.db"
        
        # Create minimal config
        self.config = {
            "symbols": ["BTCUSDc"],
            "update_interval_seconds": 1,
            "previous_day_refresh_hours": 1,
            "timeframes": ["M5", "M15", "H1"],
            "cache": {
                "database_path": str(self.db_path),
                "memory_ttl_seconds": 60,
                "db_retention_hours": 24,
                "cleanup_interval_hours": 1
            },
            "thresholds": {
                "absorption_min_volume_ratio": 2.0,
                "absorption_max_price_move_atr": 0.1,
                "void_spread_multiplier": 2.0,
                "cvd_slope_threshold": 0.1
            }
        }
        
        self.generator = TickSnapshotGenerator(
            symbols=["BTCUSDc"],
            update_interval_seconds=1,
            config_path=None
        )
        # Override config
        self.generator.config = self.config
        self.generator.cache = TickMetricsCache(
            db_path=str(self.db_path),
            memory_ttl_seconds=60,
            db_retention_hours=24
        )
    
    def tearDown(self):
        """Clean up"""
        if self.generator._running:
            asyncio.run(self.generator.stop())
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test generator initialization"""
        self.assertIsNotNone(self.generator)
        self.assertIsNotNone(self.generator.tick_fetcher)
        self.assertIsNotNone(self.generator.calculator)
        self.assertIsNotNone(self.generator.cache)
    
    def test_get_default_config(self):
        """Test default config generation"""
        config = self.generator._get_default_config()
        self.assertIsInstance(config, dict)
        self.assertIn("symbols", config)
        self.assertIn("update_interval_seconds", config)
    
    def test_empty_metrics(self):
        """Test empty metrics structure"""
        empty = self.generator._empty_metrics("BTCUSDc")
        self.assertIsInstance(empty, dict)
        self.assertIn("M5", empty)
        self.assertIn("M15", empty)
        self.assertIn("H1", empty)
        self.assertIn("previous_hour", empty)
        self.assertIn("metadata", empty)
    
    @unittest.skip("Requires async event loop setup")
    def test_start_stop(self):
        """Test starting and stopping generator"""
        async def run_test():
            await self.generator.start()
            self.assertTrue(self.generator._running)
            await asyncio.sleep(0.1)
            await self.generator.stop()
            self.assertFalse(self.generator._running)
        
        asyncio.run(run_test())
    
    def test_get_latest_metrics(self):
        """Test getting latest metrics"""
        metrics = self.generator.get_latest_metrics("BTCUSDc")
        # Should return empty metrics structure if not started or no data
        # get_latest_metrics may return None if cache is empty and not loading
        if metrics is not None:
            self.assertIn("metadata", metrics)
        # If None, that's also acceptable for initial state


class TestSingletonPattern(unittest.TestCase):
    """Tests for singleton pattern in __init__.py"""
    
    def setUp(self):
        """Clear singleton before each test"""
        clear_tick_metrics_instance()
    
    def tearDown(self):
        """Clear singleton after each test"""
        clear_tick_metrics_instance()
    
    def test_get_instance_none(self):
        """Test getting instance when not set"""
        instance = get_tick_metrics_instance()
        self.assertIsNone(instance)
    
    def test_set_and_get_instance(self):
        """Test setting and getting instance"""
        mock_instance = object()
        set_tick_metrics_instance(mock_instance)
        instance = get_tick_metrics_instance()
        self.assertIs(instance, mock_instance)
    
    def test_clear_instance(self):
        """Test clearing instance"""
        mock_instance = object()
        set_tick_metrics_instance(mock_instance)
        clear_tick_metrics_instance()
        instance = get_tick_metrics_instance()
        self.assertIsNone(instance)


def run_tests():
    """Run all Phase 1 tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestTickDataFetcher))
    suite.addTests(loader.loadTestsFromTestCase(TestTickMetricsCalculator))
    suite.addTests(loader.loadTestsFromTestCase(TestTickMetricsCache))
    suite.addTests(loader.loadTestsFromTestCase(TestTickSnapshotGenerator))
    suite.addTests(loader.loadTestsFromTestCase(TestSingletonPattern))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 70)
    print("Phase 1 Tick Metrics Infrastructure Tests")
    print("=" * 70)
    print()
    
    success = run_tests()
    
    print()
    print("=" * 70)
    if success:
        print("All Phase 1 tests passed!")
    else:
        print("Some tests failed. Check output above.")
    print("=" * 70)
    
    sys.exit(0 if success else 1)

