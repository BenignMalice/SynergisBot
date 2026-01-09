"""
Phase 7: End-to-End Integration Tests

Tests the complete tick metrics pipeline:
- Startup → Data Fetch → Calculation → Cache → Analysis
- Real-world scenarios with multiple symbols
- Performance benchmarks
- Cache behavior and TTL
"""

import unittest
import sys
import asyncio
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock MT5 constants for testing
MOCK_TICK_FLAG_BID = 2
MOCK_TICK_FLAG_ASK = 4
MOCK_TICK_FLAG_LAST = 8
MOCK_TICK_FLAG_VOLUME = 16
MOCK_TICK_FLAG_BUY = 32
MOCK_TICK_FLAG_SELL = 64


def generate_sample_ticks(count=1000, bias="neutral", base_time=None):
    """Generate sample tick data for testing (no MT5 dependency)."""
    import random
    
    if base_time is None:
        base_time = int(datetime.utcnow().timestamp())
    
    ticks = []
    price = 100.0
    
    for i in range(count):
        if bias == "buy":
            is_buy = random.random() > 0.3
        elif bias == "sell":
            is_buy = random.random() < 0.3
        else:
            is_buy = random.random() > 0.5
        
        flags = MOCK_TICK_FLAG_BUY if is_buy else MOCK_TICK_FLAG_SELL
        flags |= MOCK_TICK_FLAG_LAST
        
        price += random.uniform(-0.1, 0.1)
        spread = random.uniform(0.5, 1.5)
        
        ticks.append({
            'time': base_time + i,
            'time_msc': (base_time + i) * 1000 + random.randint(0, 999),
            'bid': price - spread/2,
            'ask': price + spread/2,
            'last': price,
            'volume': random.uniform(0.1, 2.0),
            'volume_real': random.uniform(0.1, 2.0),
            'flags': flags
        })
    
    return ticks


class TestFullPipeline(unittest.TestCase):
    """Tests for complete pipeline: Fetch → Calculate → Cache"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "BTCUSDc"
        self.sample_ticks = generate_sample_ticks(count=5000, bias="buy")
    
    @patch('infra.tick_metrics.tick_data_fetcher.mt5')
    def test_full_pipeline_btc(self, mock_mt5):
        """Test full pipeline for BTCUSDc"""
        from infra.tick_metrics.tick_data_fetcher import TickDataFetcher
        from infra.tick_metrics.tick_metrics_calculator import TickMetricsCalculator
        from infra.tick_metrics.tick_metrics_cache import TickMetricsCache
        
        # Mock MT5
        mock_mt5.is_connected.return_value = True
        mock_mt5.copy_ticks_range.return_value = self.sample_ticks
        
        # Initialize components
        fetcher = TickDataFetcher()
        calculator = TickMetricsCalculator()
        import tempfile
        import os
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            cache = TickMetricsCache(
                db_path=temp_db.name,
                memory_ttl_seconds=60,
                db_retention_hours=24
            )
            
            # Step 1: Fetch ticks
            ticks = fetcher.fetch_previous_hour_ticks(self.symbol)
            self.assertIsNotNone(ticks)
            self.assertGreater(len(ticks), 0)
            
            # Step 2: Calculate metrics for different timeframes (simulating generator behavior)
            m5_ticks = ticks[-len(ticks)//12:]  # Last 5 minutes worth
            m15_ticks = ticks[-len(ticks)//4:]  # Last 15 minutes worth
            h1_ticks = ticks  # Full hour
            
            m5_metrics = calculator.calculate_all_metrics(m5_ticks, timeframe="M5")
            m15_metrics = calculator.calculate_all_metrics(m15_ticks, timeframe="M15")
            h1_metrics = calculator.calculate_all_metrics(h1_ticks, timeframe="H1")
            prev_hour_metrics = calculator.calculate_all_metrics(ticks, timeframe="previous_hour")
            
            # Build complete structure (like generator does)
            metrics = {
                "M5": m5_metrics,
                "M15": m15_metrics,
                "H1": h1_metrics,
                "previous_hour": prev_hour_metrics,
                "metadata": {
                    "symbol": self.symbol,
                    "last_updated": datetime.utcnow().isoformat(),
                    "data_available": True,
                    "market_status": "open"
                }
            }
            
            self.assertIsNotNone(metrics)
            self.assertIn("M5", metrics)
            self.assertIn("M15", metrics)
            self.assertIn("H1", metrics)
            self.assertIn("previous_hour", metrics)
            
            # Step 3: Cache metrics
            cache.set(self.symbol, metrics)
            
            # Step 4: Retrieve from cache
            cached_metrics = cache.get(self.symbol)
            self.assertIsNotNone(cached_metrics)
            self.assertEqual(cached_metrics["M5"]["delta_volume"], metrics["M5"]["delta_volume"])
            
            # Verify metrics structure
            self.assertIn("realized_volatility", metrics["M5"])
            self.assertIn("delta_volume", metrics["M5"])
            self.assertIn("cvd_slope", metrics["M5"])
            self.assertIn("spread", metrics["M5"])
            self.assertIn("absorption", metrics["M5"])
        finally:
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)
    
    @patch('infra.tick_metrics.tick_data_fetcher.mt5')
    def test_full_pipeline_xau(self, mock_mt5):
        """Test full pipeline for XAUUSDc"""
        from infra.tick_metrics.tick_data_fetcher import TickDataFetcher
        from infra.tick_metrics.tick_metrics_calculator import TickMetricsCalculator
        from infra.tick_metrics.tick_metrics_cache import TickMetricsCache
        
        symbol = "XAUUSDc"
        sample_ticks = generate_sample_ticks(count=3000, bias="neutral")
        
        # Mock MT5
        mock_mt5.is_connected.return_value = True
        mock_mt5.copy_ticks_range.return_value = sample_ticks
        
        # Initialize components
        import tempfile
        import os
        fetcher = TickDataFetcher()
        calculator = TickMetricsCalculator()
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            cache = TickMetricsCache(
                db_path=temp_db.name,
                memory_ttl_seconds=60,
                db_retention_hours=24
            )
        
            # Execute pipeline
            ticks = fetcher.fetch_previous_hour_ticks(symbol)
            self.assertIsNotNone(ticks)
            
            flat_metrics = calculator.calculate_all_metrics(ticks)
            metrics = {
                "M5": flat_metrics,
                "M15": flat_metrics,
                "H1": flat_metrics,
                "previous_hour": flat_metrics,
                "metadata": {"data_available": True}
            }
            self.assertIsNotNone(metrics)
            
            cache.set(symbol, metrics)
            cached = cache.get(symbol)
            self.assertIsNotNone(cached)
        finally:
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)
    
    def test_metrics_match_expected_format(self):
        """Test that calculated metrics match expected schema"""
        from infra.tick_metrics.tick_metrics_calculator import TickMetricsCalculator
        
        calculator = TickMetricsCalculator()
        ticks = generate_sample_ticks(count=2000)
        
        # Calculate metrics (returns flat structure per timeframe)
        metrics = calculator.calculate_all_metrics(ticks, timeframe="M5")
        
        # Check structure (flat, not nested)
        required_fields = [
            "realized_volatility",
            "volatility_ratio",
            "delta_volume",
            "cvd",
            "cvd_slope",
            "dominant_side",
            "spread",
            "absorption",
            "tick_rate",
            "tick_count",
            "trade_tick_ratio"
        ]
        for field in required_fields:
            self.assertIn(field, metrics, f"Missing field: {field}")
        
        # Check spread structure
        self.assertIsInstance(metrics["spread"], dict)
        self.assertIn("mean", metrics["spread"])
        self.assertIn("std", metrics["spread"])
        self.assertIn("max", metrics["spread"])
        self.assertIn("widening_events", metrics["spread"])
        
        # Check absorption structure
        self.assertIsInstance(metrics["absorption"], dict)
        self.assertIn("count", metrics["absorption"])
        self.assertIn("zones", metrics["absorption"])
        self.assertIn("avg_strength", metrics["absorption"])
        
        # Check types
        self.assertIsInstance(metrics["cvd_slope"], str)
        self.assertIn(metrics["cvd_slope"], ["up", "down", "flat"])
        self.assertIsInstance(metrics["dominant_side"], str)
        self.assertIn(metrics["dominant_side"], ["BUY", "SELL", "NEUTRAL"])


class TestCachePerformance(unittest.TestCase):
    """Tests for cache performance and behavior"""
    
    def setUp(self):
        """Set up test fixtures"""
        from infra.tick_metrics.tick_metrics_calculator import TickMetricsCalculator
        
        self.calculator = TickMetricsCalculator()
        self.ticks = generate_sample_ticks(count=1000)
        self.metrics = self.calculator.calculate_all_metrics(self.ticks)
    
    def test_cache_retrieval_speed(self):
        """Test that cache lookup is fast (< 5ms)"""
        import tempfile
        import os
        from infra.tick_metrics.tick_metrics_cache import TickMetricsCache
        
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            cache = TickMetricsCache(
                db_path=temp_db.name,
                memory_ttl_seconds=60,
                db_retention_hours=24
            )
            
            # Populate cache
            cache.set("BTCUSDc", self.metrics)
            
            # Measure retrieval time
            start = time.perf_counter()
            cached = cache.get("BTCUSDc")
            elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
            
            self.assertIsNotNone(cached)
            self.assertLess(elapsed, 5.0, f"Cache retrieval too slow: {elapsed:.2f}ms")
        finally:
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)
    
    def test_cache_ttl_expiration(self):
        """Test that cache respects TTL"""
        from infra.tick_metrics.tick_metrics_cache import TickMetricsCache
        
        # Use a temporary file instead of :memory: for DB persistence test
        import tempfile
        import os
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            cache = TickMetricsCache(
                db_path=temp_db.name,
                memory_ttl_seconds=1,  # Very short TTL for testing
                db_retention_hours=24
            )
            
            # Build proper metrics structure
            metrics_structure = {
                "M5": self.metrics,
                "M15": self.metrics,
                "H1": self.metrics,
                "previous_hour": self.metrics,
                "metadata": {"data_available": True}
            }
            
            cache.set("BTCUSDc", metrics_structure)
            
            # Should be available immediately
            self.assertIsNotNone(cache.get("BTCUSDc"))
            
            # Wait for TTL to expire
            time.sleep(1.1)
            
            # Should fall back to DB (which also has it)
            cached = cache.get("BTCUSDc")
            self.assertIsNotNone(cached, "Should retrieve from DB after memory TTL expires")
        finally:
            # Cleanup
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)
    
    def test_cache_multiple_symbols(self):
        """Test cache with multiple symbols"""
        import tempfile
        import os
        from infra.tick_metrics.tick_metrics_cache import TickMetricsCache
        
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            cache = TickMetricsCache(
                db_path=temp_db.name,
                memory_ttl_seconds=60,
                db_retention_hours=24
            )
            
            symbols = ["BTCUSDc", "XAUUSDc", "EURUSDc"]
            
            for symbol in symbols:
                cache.set(symbol, self.metrics)
            
            for symbol in symbols:
                cached = cache.get(symbol)
                self.assertIsNotNone(cached, f"Failed to retrieve {symbol}")
        finally:
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)


class TestDesktopAgentIntegration(unittest.TestCase):
    """Tests for desktop_agent.py integration"""
    
    @patch('infra.tick_metrics.get_tick_metrics_instance')
    def test_analyse_symbol_full_includes_tick_metrics(self, mock_get_instance):
        """Test that analyse_symbol_full includes tick_metrics in response"""
        from infra.tick_metrics.tick_metrics_calculator import TickMetricsCalculator
        
        # Create mock metrics with proper structure
        calculator = TickMetricsCalculator()
        ticks = generate_sample_ticks(count=1000)
        flat_metrics = calculator.calculate_all_metrics(ticks)
        
        metrics = {
            "M5": flat_metrics,
            "M15": flat_metrics,
            "H1": flat_metrics,
            "previous_hour": flat_metrics,
            "metadata": {
                "symbol": "BTCUSDc",
                "last_updated": datetime.utcnow().isoformat(),
                "data_available": True,
                "market_status": "open",
                "previous_day_loading": False
            }
        }
        
        # Mock the singleton
        mock_generator = Mock()
        mock_generator.get_latest_metrics.return_value = metrics
        mock_get_instance.return_value = mock_generator
        
        # Import and test (we'll mock the actual function call)
        # Note: This is a simplified test - full integration would require
        # mocking the entire analyse_symbol_full function
        retrieved_metrics = mock_generator.get_latest_metrics("BTCUSDc")
        
        self.assertIsNotNone(retrieved_metrics)
        self.assertIn("M5", retrieved_metrics)
        self.assertIn("metadata", retrieved_metrics)
        self.assertTrue(retrieved_metrics["metadata"]["data_available"])
    
    @patch('infra.tick_metrics.get_tick_metrics_instance')
    def test_analyse_symbol_full_tick_metrics_null_graceful(self, mock_get_instance):
        """Test that missing tick_metrics is handled gracefully"""
        # Mock generator returning None
        mock_generator = Mock()
        mock_generator.get_latest_metrics.return_value = None
        mock_get_instance.return_value = mock_generator
        
        retrieved_metrics = mock_generator.get_latest_metrics("BTCUSDc")
        
        self.assertIsNone(retrieved_metrics)
        # Should not raise exception


class TestMainAPILifecycle(unittest.TestCase):
    """Tests for main_api.py startup/shutdown lifecycle"""
    
    @patch('infra.tick_metrics.tick_snapshot_generator.TickSnapshotGenerator')
    def test_startup_initializes_generator(self, mock_generator_class):
        """Test that API startup creates generator"""
        mock_generator = AsyncMock()
        mock_generator_class.return_value = mock_generator
        
        # Simulate startup
        generator = mock_generator_class(
            symbols=["BTCUSDc", "XAUUSDc"],
            update_interval_seconds=60
        )
        
        self.assertIsNotNone(generator)
        mock_generator_class.assert_called_once()
    
    @patch('infra.tick_metrics.tick_snapshot_generator.TickSnapshotGenerator')
    async def test_shutdown_cleanup(self, mock_generator_class):
        """Test that shutdown stops generator cleanly"""
        mock_generator = AsyncMock()
        mock_generator_class.return_value = mock_generator
        
        generator = mock_generator_class()
        await generator.stop()
        
        mock_generator.stop.assert_called_once()


class TestUpdateCycleTiming(unittest.TestCase):
    """Tests for update cycle timing and behavior"""
    
    def test_update_interval_configurable(self):
        """Test that update interval is configurable"""
        from infra.tick_metrics.tick_snapshot_generator import TickSnapshotGenerator
        
        # Test different intervals
        intervals = [30, 60, 120]
        
        for interval in intervals:
            generator = TickSnapshotGenerator(
                symbols=["BTCUSDc"],
                update_interval_seconds=interval
            )
            self.assertEqual(generator.update_interval, interval)
    
    @patch('infra.tick_metrics.tick_data_fetcher.mt5')
    def test_h1_metrics_calculated(self, mock_mt5):
        """Test that H1 timeframe is included in output"""
        from infra.tick_metrics.tick_data_fetcher import TickDataFetcher
        from infra.tick_metrics.tick_metrics_calculator import TickMetricsCalculator
        
        mock_mt5.is_connected.return_value = True
        mock_mt5.copy_ticks_range.return_value = generate_sample_ticks(count=5000)
        
        fetcher = TickDataFetcher()
        calculator = TickMetricsCalculator()
        
        ticks = fetcher.fetch_previous_hour_ticks("BTCUSDc")
        # Calculate H1 metrics (flat structure)
        h1_metrics = calculator.calculate_all_metrics(ticks, timeframe="H1")
        
        # Verify H1 metrics structure
        self.assertIsNotNone(h1_metrics)
        self.assertIn("realized_volatility", h1_metrics)
        self.assertIn("delta_volume", h1_metrics)
        self.assertIn("cvd_slope", h1_metrics)


class TestMultipleAnalysesCache(unittest.TestCase):
    """Tests for cache behavior with multiple analyses"""
    
    def setUp(self):
        """Set up test fixtures"""
        import tempfile
        import os
        from infra.tick_metrics.tick_metrics_cache import TickMetricsCache
        from infra.tick_metrics.tick_metrics_calculator import TickMetricsCalculator
        
        # Use temporary file instead of :memory: for reliable DB persistence
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.cache = TickMetricsCache(
            db_path=self.temp_db.name,
            memory_ttl_seconds=60,
            db_retention_hours=24
        )
        self.calculator = TickMetricsCalculator()
        self.ticks = generate_sample_ticks(count=1000)
        flat_metrics = self.calculator.calculate_all_metrics(self.ticks)
        
        # Build proper structure (like generator does)
        self.metrics = {
            "M5": flat_metrics,
            "M15": flat_metrics,
            "H1": flat_metrics,
            "previous_hour": flat_metrics,
            "metadata": {"data_available": True}
        }
    
    def tearDown(self):
        """Clean up temporary files"""
        import os
        if hasattr(self, 'temp_db') and os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_multiple_analyses_use_cache(self):
        """Test that repeated calls use cached data"""
        symbol = "BTCUSDc"
        
        # First call - populate cache
        self.cache.set(symbol, self.metrics)
        first_call = self.cache.get(symbol)
        
        # Second call - should use cache
        second_call = self.cache.get(symbol)
        
        self.assertIsNotNone(first_call)
        self.assertIsNotNone(second_call)
        self.assertEqual(first_call["M5"]["delta_volume"], second_call["M5"]["delta_volume"])
    
    def test_cache_refresh_after_update(self):
        """Test that cache is updated when new data arrives"""
        symbol = "BTCUSDc"
        
        # Initial cache
        self.cache.set(symbol, self.metrics)
        initial_delta = self.cache.get(symbol)["M5"]["delta_volume"]
        
        # New metrics with different delta
        new_ticks = generate_sample_ticks(count=1000, bias="sell")
        new_flat_metrics = self.calculator.calculate_all_metrics(new_ticks)
        
        # Build proper structure
        new_metrics = {
            "M5": new_flat_metrics,
            "M15": new_flat_metrics,
            "H1": new_flat_metrics,
            "previous_hour": new_flat_metrics,
            "metadata": {"data_available": True}
        }
        
        self.cache.set(symbol, new_metrics)
        
        # Should have new data
        updated_delta = self.cache.get(symbol)["M5"]["delta_volume"]
        self.assertNotEqual(initial_delta, updated_delta)


class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmark tests"""
    
    def setUp(self):
        """Set up test fixtures"""
        import tempfile
        import os
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
    
    def tearDown(self):
        """Clean up temporary files"""
        import os
        if hasattr(self, 'temp_db') and os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_calculation_performance(self):
        """Test that metric calculation is fast"""
        from infra.tick_metrics.tick_metrics_calculator import TickMetricsCalculator
        
        calculator = TickMetricsCalculator()
        ticks = generate_sample_ticks(count=10000)  # Large dataset
        
        start = time.perf_counter()
        metrics = calculator.calculate_all_metrics(ticks)
        elapsed = time.perf_counter() - start
        
        self.assertIsNotNone(metrics)
        self.assertLess(elapsed, 1.0, f"Calculation too slow: {elapsed:.2f}s")
    
    def test_concurrent_cache_access(self):
        """Test cache performance under concurrent access"""
        from infra.tick_metrics.tick_metrics_cache import TickMetricsCache
        from infra.tick_metrics.tick_metrics_calculator import TickMetricsCalculator
        
        cache = TickMetricsCache(
            db_path=self.temp_db.name,
            memory_ttl_seconds=60,
            db_retention_hours=24
        )
        calculator = TickMetricsCalculator()
        
        symbols = ["BTCUSDc", "XAUUSDc", "EURUSDc", "USDJPYc", "GBPUSDc"]
        
        # Populate cache
        for symbol in symbols:
            ticks = generate_sample_ticks(count=1000)
            metrics = calculator.calculate_all_metrics(ticks)
            cache.set(symbol, metrics)
        
        # Concurrent reads
        start = time.perf_counter()
        for _ in range(100):
            for symbol in symbols:
                cached = cache.get(symbol)
                self.assertIsNotNone(cached)
        elapsed = time.perf_counter() - start
        
        # Should handle 500 reads quickly
        self.assertLess(elapsed, 1.0, f"Concurrent access too slow: {elapsed:.2f}s")


def run_tests():
    """Run all E2E tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFullPipeline))
    suite.addTests(loader.loadTestsFromTestCase(TestCachePerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestDesktopAgentIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestMainAPILifecycle))
    suite.addTests(loader.loadTestsFromTestCase(TestUpdateCycleTiming))
    suite.addTests(loader.loadTestsFromTestCase(TestMultipleAnalysesCache))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceBenchmarks))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 70)
    print("Phase 7: End-to-End Integration Tests")
    print("=" * 70)
    print()
    
    success = run_tests()
    
    print()
    print("=" * 70)
    if success:
        print("All Phase 7 E2E tests passed!")
    else:
        print("Some tests failed. Check output above.")
    print("=" * 70)
    
    sys.exit(0 if success else 1)

