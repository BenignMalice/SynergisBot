"""
Phase 2 Component Tests
Tests for advanced filters, database management, and enhanced Binance integration
"""

import unittest
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timezone
import tempfile
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine.advanced_vwap_calculator import AdvancedVWAPCalculator
from app.engine.volume_delta_proxy import VolumeDeltaProxy
from app.engine.advanced_atr_filters import AdvancedATRFilters
from app.database.mtf_database_manager import MTFDatabaseManager, DatabaseConfig
from infra.enhanced_binance_integration import EnhancedBinanceIntegration

class TestAdvancedVWAPCalculator(unittest.TestCase):
    """Test advanced VWAP calculator"""
    
    def setUp(self):
        self.config = {
            'symbol': 'BTCUSDc',
            'session_anchor': '24/7',
            'vwap_sigma_window_minutes': 60
        }
        self.calculator = AdvancedVWAPCalculator(self.config)
    
    def test_vwap_calculation(self):
        """Test VWAP calculation"""
        # Test incremental VWAP calculation
        result = self.calculator.calculate_vwap_incremental(0.0, 100.0, 50000.0, 0.0, 0.0)
        self.assertEqual(result[0], 500.0)  # 50000 / 100 = 500
        self.assertEqual(result[1], 100.0)  # cumulative volume
        self.assertEqual(result[2], 50000.0)  # cumulative PV
    
    def test_session_anchor_24_7(self):
        """Test 24/7 session anchor (crypto)"""
        current_time = datetime.now(timezone.utc)
        should_reset = self.calculator.update_session_anchor(current_time)
        self.assertFalse(should_reset)  # 24/7 should never reset
    
    def test_session_anchor_fx(self):
        """Test FX session anchor"""
        self.calculator.session_anchor = "FX"
        current_time = datetime.now(timezone.utc)
        should_reset = self.calculator.update_session_anchor(current_time)
        # Should reset on first call or new day
        self.assertTrue(should_reset)
    
    def test_vwap_update(self):
        """Test VWAP update with tick data"""
        tick_data = {
            'timestamp_utc': 1640995200,
            'bid': 50000.0,
            'ask': 50010.0,
            'volume': 100.0
        }
        
        result = self.calculator.update_vwap(tick_data)
        self.assertIn('vwap', result)
        self.assertIn('cumulative_volume', result)
        self.assertIn('is_new_session', result)
    
    def test_sigma_bands_calculation(self):
        """Test sigma bands calculation"""
        price_history = np.array([50000.0, 50100.0, 50200.0, 50300.0, 50400.0])
        volume_history = np.array([100.0, 150.0, 200.0, 250.0, 300.0])
        
        bands = self.calculator.calculate_sigma_bands(price_history, volume_history)
        self.assertIn('upper_band', bands)
        self.assertIn('lower_band', bands)
        self.assertIn('sigma', bands)
    
    def test_vwap_reclaim_check(self):
        """Test VWAP reclaim check"""
        # Set up VWAP
        self.calculator.current_vwap = 50000.0
        
        # Test reclaim
        result = self.calculator.check_vwap_reclaim(50050.0, threshold=0.2)
        self.assertIn('reclaimed', result)
        self.assertIn('distance_pips', result)
        self.assertIn('threshold_met', result)

class TestVolumeDeltaProxy(unittest.TestCase):
    """Test volume delta proxy"""
    
    def setUp(self):
        self.config = {
            'symbol': 'BTCUSDc',
            'delta_threshold': 1.5,
            'delta_lookback_ticks': 100,
            'delta_spike_threshold': 2.0,
            'delta_spike_cooldown_ticks': 50
        }
        self.delta_proxy = VolumeDeltaProxy(self.config)
    
    def test_tick_direction_calculation(self):
        """Test tick direction calculation"""
        # Test up direction
        direction = self.delta_proxy.calculate_tick_direction(50100.0, 50000.0)
        self.assertEqual(direction, 1)
        
        # Test down direction
        direction = self.delta_proxy.calculate_tick_direction(49900.0, 50000.0)
        self.assertEqual(direction, -1)
        
        # Test unchanged
        direction = self.delta_proxy.calculate_tick_direction(50000.0, 50000.0)
        self.assertEqual(direction, 0)
    
    def test_delta_proxy_calculation(self):
        """Test delta proxy calculation"""
        directions = np.array([1, 1, -1, 1, -1], dtype=np.float32)
        volumes = np.array([100.0, 150.0, 200.0, 250.0, 300.0], dtype=np.float32)
        
        delta, delta_ma, delta_std = self.delta_proxy.calculate_delta_proxy(
            directions, volumes, len(directions)
        )
        
        self.assertIsInstance(delta, float)
        self.assertIsInstance(delta_ma, float)
        self.assertIsInstance(delta_std, float)
    
    def test_delta_update(self):
        """Test delta update with tick data"""
        tick_data = {
            'timestamp_utc': 1640995200,
            'bid': 50000.0,
            'ask': 50010.0,
            'volume': 100.0
        }
        
        result = self.delta_proxy.update_delta(tick_data)
        self.assertIn('delta', result)
        self.assertIn('delta_ma', result)
        self.assertIn('delta_std', result)
        self.assertIn('spike_detected', result)
    
    def test_delta_spike_detection(self):
        """Test delta spike detection"""
        # Add some data first
        for i in range(20):
            tick_data = {
                'timestamp_utc': 1640995200 + i,
                'bid': 50000.0 + i,
                'ask': 50010.0 + i,
                'volume': 100.0 + i
            }
            self.delta_proxy.update_delta(tick_data)
        
        result = self.delta_proxy.check_delta_spike(50100.0, 1640995300)
        self.assertIn('spike_detected', result)
        self.assertIn('delta_strength', result)
        self.assertIn('confidence', result)
    
    def test_delta_metrics(self):
        """Test delta metrics retrieval"""
        metrics = self.delta_proxy.get_delta_metrics()
        self.assertIn('current_delta', metrics)
        self.assertIn('delta_ma', metrics)
        self.assertIn('delta_std', metrics)
        self.assertIn('data_points', metrics)

class TestAdvancedATRFilters(unittest.TestCase):
    """Test advanced ATR filters"""
    
    def setUp(self):
        self.config = {
            'symbol': 'BTCUSDc',
            'atr_multiplier_m1': 1.5,
            'atr_multiplier_m5': 2.0,
            'max_allowed_spread': 10.0,
            'spread_median_window': 20
        }
        self.atr_filters = AdvancedATRFilters(self.config)
    
    def test_atr_calculation(self):
        """Test ATR calculation"""
        highs = np.array([100.0, 101.0, 102.0, 103.0, 104.0], dtype=np.float32)
        lows = np.array([99.0, 100.0, 101.0, 102.0, 103.0], dtype=np.float32)
        closes = np.array([99.5, 100.5, 101.5, 102.5, 103.5], dtype=np.float32)
        
        atr = self.atr_filters.calculate_atr(highs, lows, closes, 5)
        self.assertIsInstance(atr, float)
        self.assertGreater(atr, 0)
    
    def test_rolling_median_calculation(self):
        """Test rolling median calculation"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
        median = self.atr_filters.calculate_rolling_median(data, 3)
        # For the last 3 elements [3.0, 4.0, 5.0], median should be 4.0
        self.assertEqual(median, 4.0)
    
    def test_atr_m1_update(self):
        """Test M1 ATR update"""
        ohlcv_data = {
            'high': [100.0, 101.0, 102.0, 103.0, 104.0],
            'low': [99.0, 100.0, 101.0, 102.0, 103.0],
            'close': [99.5, 100.5, 101.5, 102.5, 103.5]
        }
        
        atr = self.atr_filters.update_atr_m1(ohlcv_data)
        self.assertIsInstance(atr, float)
    
    def test_atr_m5_update(self):
        """Test M5 ATR update"""
        ohlcv_data = {
            'high': [100.0, 102.0, 104.0, 106.0, 108.0],
            'low': [99.0, 101.0, 103.0, 105.0, 107.0],
            'close': [99.5, 101.5, 103.5, 105.5, 107.5]
        }
        
        atr = self.atr_filters.update_atr_m5(ohlcv_data)
        self.assertIsInstance(atr, float)
    
    def test_atr_ratio_calculation(self):
        """Test ATR ratio calculation"""
        self.atr_filters.current_m1_atr = 10.0
        self.atr_filters.current_m5_atr = 20.0
        
        ratio = self.atr_filters.calculate_atr_ratio()
        self.assertEqual(ratio, 0.5)
    
    def test_atr_ratio_validity(self):
        """Test ATR ratio validity check"""
        self.atr_filters.current_m1_atr = 10.0
        self.atr_filters.current_m5_atr = 20.0
        
        result = self.atr_filters.check_atr_ratio_validity()
        self.assertIn('valid', result)
        self.assertIn('ratio', result)
        self.assertIn('m1_atr', result)
        self.assertIn('m5_atr', result)
    
    def test_spread_update(self):
        """Test spread update"""
        tick_data = {
            'bid': 50000.0,
            'ask': 50010.0
        }
        
        spread = self.atr_filters.update_spread(tick_data)
        self.assertEqual(spread, 10.0)
    
    def test_spread_validity(self):
        """Test spread validity check"""
        # Add some spread data
        for i in range(10):
            tick_data = {'bid': 50000.0, 'ask': 50000.0 + i}
            self.atr_filters.update_spread(tick_data)
        
        result = self.atr_filters.check_spread_validity(5.0)
        self.assertIn('valid', result)
        self.assertIn('current_spread', result)
        self.assertIn('median_spread', result)

class TestMTFDatabaseManager(unittest.TestCase):
    """Test multi-timeframe database manager"""
    
    def setUp(self):
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.config = DatabaseConfig(
            db_path=self.temp_db.name,
            batch_size=10,
            flush_interval=0.5
        )
        self.db_manager = MTFDatabaseManager(self.config)
    
    def tearDown(self):
        # Clean up temporary database
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_database_initialization(self):
        """Test database initialization"""
        self.assertTrue(os.path.exists(self.temp_db.name))
    
    def test_operation_queueing(self):
        """Test operation queueing"""
        operation = {
            'type': 'insert_tick',
            'symbol': 'BTCUSDc',
            'timestamp_ms': 1640995200000,
            'bid': 50000.0,
            'ask': 50010.0,
            'volume': 100.0,
            'source': 'mt5'
        }
        
        # Should not raise exception
        self.db_manager.queue_operation(operation)
        self.assertEqual(self.db_manager.write_queue.qsize(), 1)
    
    def test_performance_stats(self):
        """Test performance statistics"""
        stats = self.db_manager.get_performance_stats()
        self.assertIn('write_count', stats)
        self.assertIn('read_count', stats)
        self.assertIn('error_count', stats)
        self.assertIn('queue_size', stats)
        self.assertIn('running', stats)

class TestEnhancedBinanceIntegration(unittest.TestCase):
    """Test enhanced Binance integration"""
    
    def setUp(self):
        self.config = {
            'symbol': 'BTCUSDc',
            'binance_symbol': 'BTCUSDT',
            'large_order_threshold': 50000,
            'support_resistance_levels': 3,
            'order_book_depth': 20
        }
        self.binance = EnhancedBinanceIntegration(self.config)
    
    def test_initialization(self):
        """Test initialization"""
        self.assertEqual(self.binance.symbol, 'BTCUSDc')
        self.assertEqual(self.binance.binance_symbol, 'BTCUSDT')
        self.assertEqual(self.binance.large_order_threshold, 50000)
        self.assertFalse(self.binance.connected)
    
    def test_large_order_detection(self):
        """Test large order detection"""
        trade = {
            'price': 50000.0,
            'quantity': 2.0,  # $100k order
            'timestamp': 1640995200000,
            'is_buyer_maker': False
        }
        
        # Should detect large order
        self.binance.large_orders.append(trade)
        self.assertEqual(len(self.binance.large_orders), 1)
    
    def test_price_cluster_detection(self):
        """Test price cluster detection"""
        prices = np.array([50000.0, 50001.0, 50002.0, 50003.0, 50004.0, 51000.0, 51001.0, 51002.0])
        
        clusters = self.binance._find_price_clusters(prices, 'support')
        self.assertIsInstance(clusters, list)
    
    def test_performance_stats(self):
        """Test performance statistics"""
        stats = self.binance.get_performance_stats()
        self.assertIn('connected', stats)
        self.assertIn('update_count', stats)
        self.assertIn('error_count', stats)
        self.assertIn('data_points', stats)

class TestPhase2Integration(unittest.TestCase):
    """Test Phase 2 integration"""
    
    def test_vwap_delta_integration(self):
        """Test VWAP and delta integration"""
        vwap_config = {
            'symbol': 'BTCUSDc',
            'session_anchor': '24/7',
            'vwap_sigma_window_minutes': 60
        }
        delta_config = {
            'symbol': 'BTCUSDc',
            'delta_threshold': 1.5,
            'delta_lookback_ticks': 100
        }
        
        vwap_calc = AdvancedVWAPCalculator(vwap_config)
        delta_proxy = VolumeDeltaProxy(delta_config)
        
        # Test integration
        tick_data = {
            'timestamp_utc': 1640995200,
            'bid': 50000.0,
            'ask': 50010.0,
            'volume': 100.0
        }
        
        vwap_result = vwap_calc.update_vwap(tick_data)
        delta_result = delta_proxy.update_delta(tick_data)
        
        self.assertIn('vwap', vwap_result)
        self.assertIn('delta', delta_result)
    
    def test_atr_spread_integration(self):
        """Test ATR and spread integration"""
        atr_config = {
            'symbol': 'BTCUSDc',
            'atr_multiplier_m1': 1.5,
            'max_allowed_spread': 10.0
        }
        
        atr_filters = AdvancedATRFilters(atr_config)
        
        # Test ATR calculation
        ohlcv_data = {
            'high': [100.0, 101.0, 102.0],
            'low': [99.0, 100.0, 101.0],
            'close': [99.5, 100.5, 101.5]
        }
        
        atr = atr_filters.update_atr_m1(ohlcv_data)
        self.assertIsInstance(atr, float)
        
        # Test spread calculation
        tick_data = {'bid': 50000.0, 'ask': 50010.0}
        spread = atr_filters.update_spread(tick_data)
        self.assertEqual(spread, 10.0)

def run_phase2_tests():
    """Run all Phase 2 tests"""
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestAdvancedVWAPCalculator,
        TestVolumeDeltaProxy,
        TestAdvancedATRFilters,
        TestMTFDatabaseManager,
        TestEnhancedBinanceIntegration,
        TestPhase2Integration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_phase2_tests()
    if success:
        print("\nAll Phase 2 tests passed!")
    else:
        print("\nSome Phase 2 tests failed!")
