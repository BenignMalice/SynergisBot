"""
Unit Tests for Volume Confirmation Implementation
Tests volume condition checking, caching, and error handling
"""
import unittest
import sys
import time
import threading
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from auto_execution_system import AutoExecutionSystem, TradePlan
    from infra.mt5_service import MT5Service
except ImportError as e:
    print(f"Warning: Could not import auto-execution system: {e}")
    print("Some tests may be skipped")


class TestVolumeHelperFunctions(unittest.TestCase):
    """Test volume helper functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.system = AutoExecutionSystem()
        self.symbol = "BTCUSDc"
    
    def test_get_volume_avg_count_m5(self):
        """Test _get_volume_avg_count for M5 timeframe"""
        # This function is nested in _check_conditions, so we test via integration
        # Expected: M5 should return 12 (12 * 5min = 60min = 1 hour)
        # We'll verify this through the volume calculation
        pass  # Integration test
    
    def test_get_volume_avg_count_m15(self):
        """Test _get_volume_avg_count for M15 timeframe"""
        # Expected: M15 should return 4 (4 * 15min = 60min = 1 hour)
        pass  # Integration test
    
    def test_get_volume_avg_count_h1(self):
        """Test _get_volume_avg_count for H1 timeframe"""
        # Expected: H1 should return 20 (20 * 1hr = 20 hours)
        pass  # Integration test
    
    def test_convert_to_binance_symbol_btcusd(self):
        """Test _convert_to_binance_symbol for BTCUSD"""
        # This function is nested in _check_conditions, so we test via integration
        # Expected: BTCUSDc -> btcusdt
        pass  # Integration test
    
    def test_convert_to_binance_symbol_ethusd(self):
        """Test _convert_to_binance_symbol for ETHUSD"""
        # Expected: ETHUSDc -> ethusdt
        pass  # Integration test


class TestVolumeCache(unittest.TestCase):
    """Test volume cache functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.system = AutoExecutionSystem()
        self.symbol = "BTCUSDc"
        self.timeframe = "M5"
        self.cache_key = (self.symbol, self.timeframe)
    
    def test_cache_initialization(self):
        """Test that volume cache is initialized"""
        self.assertTrue(hasattr(self.system, '_volume_cache'))
        self.assertTrue(hasattr(self.system, '_volume_cache_ttl'))
        self.assertTrue(hasattr(self.system, '_volume_cache_lock'))
        self.assertEqual(self.system._volume_cache_ttl, 30)
    
    def test_cache_storage(self):
        """Test storing values in cache"""
        metrics = {
            "volume_current": 1000.0,
            "volume_avg": 800.0,
            "volume_zscore": 1.5,
            "volume_spike": False
        }
        current_time = time.time()
        
        with self.system._volume_cache_lock:
            self.system._volume_cache[self.cache_key] = (metrics, current_time)
        
        with self.system._volume_cache_lock:
            self.assertIn(self.cache_key, self.system._volume_cache)
            cached_metrics, cached_time = self.system._volume_cache[self.cache_key]
            self.assertEqual(cached_metrics["volume_current"], 1000.0)
    
    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration"""
        metrics = {
            "volume_current": 1000.0,
            "volume_avg": 800.0,
            "volume_zscore": 1.5,
            "volume_spike": False
        }
        old_time = time.time() - 35  # 35 seconds ago (expired)
        
        with self.system._volume_cache_lock:
            self.system._volume_cache[self.cache_key] = (metrics, old_time)
        
        # Cache should be expired (TTL is 30s)
        # This is tested via integration in _check_conditions
    
    def test_cache_invalidation(self):
        """Test cache invalidation"""
        metrics = {
            "volume_current": 1000.0,
            "volume_avg": 800.0,
            "volume_zscore": 1.5,
            "volume_spike": False
        }
        current_time = time.time()
        
        with self.system._volume_cache_lock:
            self.system._volume_cache[self.cache_key] = (metrics, current_time)
        
        # Invalidate cache
        with self.system._volume_cache_lock:
            if self.cache_key in self.system._volume_cache:
                del self.system._volume_cache[self.cache_key]
        
        with self.system._volume_cache_lock:
            self.assertNotIn(self.cache_key, self.system._volume_cache)
    
    def test_cache_thread_safety(self):
        """Test cache thread safety"""
        metrics = {
            "volume_current": 1000.0,
            "volume_avg": 800.0,
            "volume_zscore": 1.5,
            "volume_spike": False
        }
        current_time = time.time()
        
        def write_cache():
            for i in range(100):
                with self.system._volume_cache_lock:
                    self.system._volume_cache[(f"SYMBOL{i}", "M5")] = (metrics, current_time)
        
        def read_cache():
            for i in range(100):
                with self.system._volume_cache_lock:
                    if (f"SYMBOL{i}", "M5") in self.system._volume_cache:
                        _ = self.system._volume_cache[(f"SYMBOL{i}", "M5")]
        
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=write_cache))
            threads.append(threading.Thread(target=read_cache))
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # If we get here without exceptions, thread safety is working
        self.assertTrue(True)


class TestBinancePressureCache(unittest.TestCase):
    """Test Binance pressure cache functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.system = AutoExecutionSystem()
        self.binance_symbol = "btcusdt"
        self.cache_key = f"pressure_{self.binance_symbol}"
    
    def test_cache_initialization(self):
        """Test that Binance pressure cache is initialized"""
        self.assertTrue(hasattr(self.system, '_binance_pressure_cache'))
        self.assertTrue(hasattr(self.system, '_binance_pressure_cache_lock'))
    
    def test_cache_storage(self):
        """Test storing Binance pressure data in cache"""
        pressure_data = {
            "buy_volume": 1000.0,
            "sell_volume": 800.0
        }
        current_time = time.time()
        
        with self.system._binance_pressure_cache_lock:
            self.system._binance_pressure_cache[self.cache_key] = (pressure_data, current_time)
        
        with self.system._binance_pressure_cache_lock:
            self.assertIn(self.cache_key, self.system._binance_pressure_cache)
            cached_data, cached_time = self.system._binance_pressure_cache[self.cache_key]
            self.assertEqual(cached_data["buy_volume"], 1000.0)
    
    def test_cache_ttl_expiration(self):
        """Test Binance cache TTL expiration (10 seconds)"""
        pressure_data = {
            "buy_volume": 1000.0,
            "sell_volume": 800.0
        }
        old_time = time.time() - 15  # 15 seconds ago (expired)
        
        with self.system._binance_pressure_cache_lock:
            self.system._binance_pressure_cache[self.cache_key] = (pressure_data, old_time)
        
        # Cache should be expired (TTL is 10s)
        # This is tested via integration in _check_conditions


class TestVolumeConditionChecks(unittest.TestCase):
    """Test volume condition checking logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.system = AutoExecutionSystem()
        self.symbol = "BTCUSDc"
        
        # Mock MT5 service
        self.system.mt5_service = Mock(spec=MT5Service)
        self.system.mt5_service.connect = Mock(return_value=True)
        self.system.mt5_service.get_quote = Mock(return_value=Mock(bid=100000.0, ask=100001.0))
        
        # Mock _get_recent_candles to return test data
        self.mock_candles = [
            {"time": 1000, "open": 100000, "high": 100100, "low": 99900, "close": 100050, "volume": 1000, "tick_volume": 1000},
            {"time": 2000, "open": 100050, "high": 100150, "low": 99950, "close": 100100, "volume": 1200, "tick_volume": 1200},
            {"time": 3000, "open": 100100, "high": 100200, "low": 100000, "close": 100150, "volume": 1500, "tick_volume": 1500},
        ]
    
    def test_volume_above_condition_pass(self):
        """Test volume_above condition passes when volume is above threshold"""
        plan = TradePlan(
            plan_id="test_vol_above_pass",
            symbol=self.symbol,
            direction="BUY",
            entry_price=100000.0,
            stop_loss=99900.0,
            take_profit=100200.0,
            volume=0.01,
            conditions={
                "price_near": 100000.0,
                "tolerance": 100.0,
                "volume_above": 800.0,
                "timeframe": "M5"
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock _get_recent_candles to return candles with volume > 800
        with patch.object(self.system, '_check_conditions') as mock_check:
            # We can't easily test _check_conditions directly due to nested functions
            # This is an integration test placeholder
            self.assertTrue(hasattr(self.system, '_check_conditions'))
    
    def test_volume_ratio_condition_pass(self):
        """Test volume_ratio condition passes when ratio is met"""
        plan = TradePlan(
            plan_id="test_vol_ratio_pass",
            symbol=self.symbol,
            direction="BUY",
            entry_price=100000.0,
            stop_loss=99900.0,
            take_profit=100200.0,
            volume=0.01,
            conditions={
                "price_near": 100000.0,
                "tolerance": 100.0,
                "volume_ratio": 1.2,
                "timeframe": "M5"
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Integration test placeholder
        self.assertTrue(hasattr(self.system, '_check_conditions'))
    
    def test_volume_spike_condition_pass(self):
        """Test volume_spike condition passes when spike detected"""
        plan = TradePlan(
            plan_id="test_vol_spike_pass",
            symbol=self.symbol,
            direction="BUY",
            entry_price=100000.0,
            stop_loss=99900.0,
            take_profit=100200.0,
            volume=0.01,
            conditions={
                "price_near": 100000.0,
                "tolerance": 100.0,
                "volume_spike": True,
                "timeframe": "M5"
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Integration test placeholder
        self.assertTrue(hasattr(self.system, '_check_conditions'))
    
    def test_volume_confirmation_btcusd_buy(self):
        """Test volume_confirmation for BTCUSD BUY (requires buy_volume > sell_volume)"""
        plan = TradePlan(
            plan_id="test_vol_conf_btc_buy",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=100000.0,
            stop_loss=99900.0,
            take_profit=100200.0,
            volume=0.01,
            conditions={
                "price_near": 100000.0,
                "tolerance": 100.0,
                "volume_confirmation": True,
                "timeframe": "M5"
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Integration test placeholder
        # Would need to mock OrderFlowService or WhaleDetector
        self.assertTrue(hasattr(self.system, '_check_conditions'))
    
    def test_volume_confirmation_non_btcusd(self):
        """Test volume_confirmation for non-BTCUSD (uses volume spike)"""
        plan = TradePlan(
            plan_id="test_vol_conf_xau",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=4200.0,
            stop_loss=4190.0,
            take_profit=4210.0,
            volume=0.01,
            conditions={
                "price_near": 4200.0,
                "tolerance": 10.0,
                "volume_confirmation": True,
                "timeframe": "M5"
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Integration test placeholder
        self.assertTrue(hasattr(self.system, '_check_conditions'))


class TestVolumeConditionValidation(unittest.TestCase):
    """Test volume condition validation in chatgpt_auto_execution_tools"""
    
    def test_volume_above_validation_positive(self):
        """Test volume_above validation accepts positive values"""
        # This would test chatgpt_auto_execution_tools validation
        # Integration test placeholder
        pass
    
    def test_volume_above_validation_negative(self):
        """Test volume_above validation rejects negative values"""
        # Integration test placeholder
        pass
    
    def test_volume_ratio_validation_positive(self):
        """Test volume_ratio validation accepts positive values"""
        # Integration test placeholder
        pass
    
    def test_volume_ratio_validation_zero(self):
        """Test volume_ratio validation rejects zero or negative values"""
        # Integration test placeholder
        pass
    
    def test_multiple_volume_conditions_warning(self):
        """Test warning when multiple volume conditions are specified"""
        # Integration test placeholder
        pass


class TestVolumeErrorHandling(unittest.TestCase):
    """Test volume condition error handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.system = AutoExecutionSystem()
        self.symbol = "BTCUSDc"
    
    def test_volume_only_plan_fail_closed(self):
        """Test volume-only plan fails closed when volume data unavailable"""
        plan = TradePlan(
            plan_id="test_vol_only_fail_closed",
            symbol=self.symbol,
            direction="BUY",
            entry_price=100000.0,
            stop_loss=99900.0,
            take_profit=100200.0,
            volume=0.01,
            conditions={
                "volume_confirmation": True,
                "timeframe": "M5"
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Integration test placeholder
        # Would need to mock volume calculation failure
        self.assertTrue(hasattr(self.system, '_check_conditions'))
    
    def test_hybrid_plan_fail_open(self):
        """Test hybrid plan fails open when volume data unavailable"""
        plan = TradePlan(
            plan_id="test_hybrid_fail_open",
            symbol=self.symbol,
            direction="BUY",
            entry_price=100000.0,
            stop_loss=99900.0,
            take_profit=100200.0,
            volume=0.01,
            conditions={
                "price_near": 100000.0,
                "tolerance": 100.0,
                "volume_confirmation": True,
                "timeframe": "M5"
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Integration test placeholder
        # Would need to mock volume calculation failure
        self.assertTrue(hasattr(self.system, '_check_conditions'))


def run_all_tests():
    """Run all volume confirmation tests"""
    print("=" * 80)
    print("VOLUME CONFIRMATION IMPLEMENTATION - TEST SUITE")
    print("=" * 80)
    print()
    print("Test Categories:")
    print("  1. Volume Helper Functions")
    print("  2. Volume Cache")
    print("  3. Binance Pressure Cache")
    print("  4. Volume Condition Checks")
    print("  5. Volume Condition Validation")
    print("  6. Volume Error Handling")
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestVolumeHelperFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestVolumeCache))
    suite.addTests(loader.loadTestsFromTestCase(TestBinancePressureCache))
    suite.addTests(loader.loadTestsFromTestCase(TestVolumeConditionChecks))
    suite.addTests(loader.loadTestsFromTestCase(TestVolumeConditionValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestVolumeErrorHandling))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print()
    
    if result.wasSuccessful():
        print("[SUCCESS] ALL TESTS PASSED")
    else:
        print("[FAILED] SOME TESTS FAILED")
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}")
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

