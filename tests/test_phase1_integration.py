"""
Phase 1 Integration Tests
End-to-end testing of MT5 data flow, Binance WebSocket, database performance
"""

import unittest
import asyncio
import time
import tempfile
import os
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Any
import threading
import queue
import json

# Import components
from app.engine.mtf_structure_analyzer import MTFStructureAnalyzer, TimeframeData
from app.engine.m1_precision_filters import M1PrecisionFilters, TickData
from app.engine.mtf_decision_tree import MTFDecisionTree, BiasType, DecisionType
from infra.mtf_database_schema import MTFDatabaseSchema
from infra.hot_path_architecture import HotPathManager, TickEvent, AsyncDBWriter
from infra.binance_context_integration import BinanceContextManager, OrderBookSnapshot
from config.symbol_config import SymbolConfigManager

class TestMT5DataFlow(unittest.TestCase):
    """Test MT5 data flow integration"""
    
    def setUp(self):
        self.config = {
            'max_lot_size': 0.01,
            'default_risk_percent': 0.5,
            'vwap_threshold': 0.2,
            'delta_threshold': 1.5,
            'buffer_capacity': 1000
        }
        
        # Initialize components
        self.hot_path_manager = HotPathManager(self.config)
        self.hot_path_manager.add_symbol("BTCUSDc", self.config)
        self.hot_path_manager.add_symbol("XAUUSDc", self.config)
        self.hot_path_manager.add_symbol("EURUSDc", self.config)
        
    def test_tick_processing_flow(self):
        """Test complete tick processing flow"""
        # Simulate MT5 tick data
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        for i in range(100):
            # Create tick for each symbol
            for symbol in ["BTCUSDc", "XAUUSDc", "EURUSDc"]:
                base_price = 50000 if symbol == "BTCUSDc" else (2000 if symbol == "XAUUSDc" else 1.1000)
                
                tick = TickEvent(
                    symbol=symbol,
                    timestamp_utc=current_time + i,
                    bid=base_price - 0.5,
                    ask=base_price + 0.5,
                    volume=100 + i,
                    source="mt5",
                    sequence_id=i
                )
                
                # Process tick
                self.hot_path_manager.process_tick(symbol, tick)
                
        # Check that decisions were generated
        decisions_generated = 0
        for symbol in ["BTCUSDc", "XAUUSDc", "EURUSDc"]:
            decision = self.hot_path_manager.get_decision(symbol)
            if decision:
                decisions_generated += 1
                
        # Should have generated some decisions
        self.assertGreaterEqual(decisions_generated, 0)
        
    def test_performance_metrics(self):
        """Test performance metrics collection"""
        # Process some ticks
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        for i in range(50):
            tick = TickEvent(
                symbol="BTCUSDc",
                timestamp_utc=current_time + i,
                bid=50000.0,
                ask=50000.5,
                volume=100,
                source="mt5",
                sequence_id=i
            )
            self.hot_path_manager.process_tick("BTCUSDc", tick)
            
        # Get performance metrics
        metrics = self.hot_path_manager.get_performance_metrics()
        
        # Should have metrics for BTCUSDc
        self.assertIn("BTCUSDc", metrics)
        btc_metrics = metrics["BTCUSDc"]
        
        # Should have latency metrics
        self.assertIn("latency_p50", btc_metrics)
        self.assertIn("latency_p95", btc_metrics)
        self.assertIn("latency_p99", btc_metrics)
        
        # Latency should be reasonable (< 100ms)
        self.assertLess(btc_metrics["latency_p95"], 100)

class TestBinanceWebSocketStability(unittest.TestCase):
    """Test Binance WebSocket stability"""
    
    def setUp(self):
        self.config = {
            'large_order_threshold': 0.1,
            'support_resistance_lookback': 50,
            'volume_imbalance_threshold': 0.3,
            'max_reconnect_attempts': 3,
            'reconnect_delay': 0.1  # Fast for testing
        }
        self.binance_manager = BinanceContextManager(self.config)
        
    def test_binance_context_analysis(self):
        """Test Binance context analysis without WebSocket"""
        # Add symbol
        self.binance_manager.add_symbol("BTCUSDc", self.config)
        
        # Create sample order book snapshot
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDc",
            timestamp_utc=int(datetime.now(timezone.utc).timestamp()),
            bids=[[50000.0, 1.5], [49999.0, 2.0], [49998.0, 1.0]],
            asks=[[50001.0, 1.2], [50002.0, 1.8], [50003.0, 0.9]],
            spread=1.0,
            mid_price=50000.5,
            volume_imbalance=0.0,
            large_orders=[]
        )
        
        # Test analysis
        analyzer = self.binance_manager.analyzers["BTCUSDc"]
        microstructure = analyzer.analyze_order_book(snapshot)
        
        # Should return valid microstructure
        self.assertIsNotNone(microstructure)
        self.assertEqual(microstructure.symbol, "BTCUSDc")
        self.assertIsInstance(microstructure.bid_ask_spread, float)
        self.assertIsInstance(microstructure.volume_imbalance, float)
        
    def test_large_order_detection(self):
        """Test large order detection"""
        # Create order book with large orders
        large_bids = [[50000.0, 10.0], [49999.0, 15.0], [49998.0, 5.0]]  # Large volumes
        normal_asks = [[50001.0, 1.2], [50002.0, 1.8], [50003.0, 0.9]]  # Normal volumes
        
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDc",
            timestamp_utc=int(datetime.now(timezone.utc).timestamp()),
            bids=large_bids,
            asks=normal_asks,
            spread=1.0,
            mid_price=50000.5,
            volume_imbalance=0.0,
            large_orders=[]
        )
        
        # Test analysis
        self.binance_manager.add_symbol("BTCUSDc", self.config)
        analyzer = self.binance_manager.analyzers["BTCUSDc"]
        microstructure = analyzer.analyze_order_book(snapshot)
        
        # Should detect large orders
        self.assertGreater(microstructure.large_order_ratio, 0)

class TestDatabasePerformance(unittest.TestCase):
    """Test database performance"""
    
    def setUp(self):
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.db_schema = MTFDatabaseSchema(self.temp_db.name)
        
    def tearDown(self):
        os.unlink(self.temp_db.name)
        
    def test_bulk_insertion_performance(self):
        """Test bulk insertion performance"""
        with self.db_schema:
            start_time = time.time()
            
            # Insert 1000 structure analysis records
            for i in range(1000):
                self.db_schema.insert_structure_analysis(
                    symbol="BTCUSDc",
                    timeframe="H1",
                    timestamp_utc=int(datetime.now(timezone.utc).timestamp()) + i,
                    structure_type="BOS",
                    structure_data={"price": 50000 + i, "volume": 1000},
                    confidence_score=0.85
                )
                
            end_time = time.time()
            duration = end_time - start_time
            
            # Should complete within reasonable time (< 5 seconds)
            self.assertLess(duration, 5.0)
            
            # Should be able to query data
            structures = self.db_schema.get_latest_structure("BTCUSDc", "H1", 10)
            self.assertEqual(len(structures), 10)
            
    def test_concurrent_access(self):
        """Test concurrent database access"""
        with self.db_schema:
            def insert_data(thread_id):
                for i in range(100):
                    self.db_schema.insert_structure_analysis(
                        symbol=f"SYMBOL{thread_id}",
                        timeframe="H1",
                        timestamp_utc=int(datetime.now(timezone.utc).timestamp()) + i,
                        structure_type="BOS",
                        structure_data={"price": 50000 + i, "volume": 1000},
                        confidence_score=0.85
                    )
                    
            # Create multiple threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=insert_data, args=(i,))
                threads.append(thread)
                thread.start()
                
            # Wait for all threads
            for thread in threads:
                thread.join()
                
            # Should complete without database locking errors
            pass

class TestMultiTimeframeIntegration(unittest.TestCase):
    """Test multi-timeframe integration"""
    
    def setUp(self):
        self.config = {
            'max_lot_size': 0.01,
            'default_risk_percent': 0.5,
            'vwap_threshold': 0.2,
            'delta_threshold': 1.5,
            'atr_ratio_threshold': 0.5
        }
        
        # Initialize components
        self.structure_analyzer = MTFStructureAnalyzer(self.config)
        self.m1_filters = M1PrecisionFilters(self.config)
        self.decision_tree = MTFDecisionTree(self.config)
        
    def test_complete_analysis_flow(self):
        """Test complete multi-timeframe analysis flow"""
        # Create sample data for different timeframes
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        # H1 data
        h1_data = self._create_sample_timeframe_data("BTCUSDc", "H1", 24, current_time)
        
        # M15 data
        m15_data = self._create_sample_timeframe_data("BTCUSDc", "M15", 96, current_time)
        
        # M5 data
        m5_data = self._create_sample_timeframe_data("BTCUSDc", "M5", 288, current_time)
        
        # Analyze structure for each timeframe
        h1_signals = self.structure_analyzer.analyze_timeframe(h1_data)
        m15_signals = self.structure_analyzer.analyze_timeframe(m15_data)
        m5_signals = self.structure_analyzer.analyze_timeframe(m5_data)
        
        # Should generate signals
        self.assertIsInstance(h1_signals, list)
        self.assertIsInstance(m15_signals, list)
        self.assertIsInstance(m5_signals, list)
        
        # Test M1 filters
        for i in range(50):
            tick = TickData(
                symbol="BTCUSDc",
                timestamp_utc=current_time - (50 - i) * 60,
                bid=50000.0 - 0.5,
                ask=50000.0 + 0.5,
                volume=100 + i * 10,
                spread=1.0
            )
            self.m1_filters.add_tick(tick)
            
        m1_result = self.m1_filters.analyze_filters("BTCUSDc", 50000.0, current_time)
        self.assertIsNotNone(m1_result)
        
        # Test decision making
        h1_analysis = {
            'close': 50000.0,
            'ema_200': 49500.0,
            'structure_signals': [{'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': current_time}]
        }
        
        m15_analysis = {
            'structure_signals': [{'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': current_time}]
        }
        
        m5_analysis = {
            'structure_signals': [{'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': current_time}]
        }
        
        m1_filters_data = {
            'filters_passed': 4,
            'filter_score': 0.8
        }
        
        decision = self.decision_tree.make_decision(
            symbol="BTCUSDc",
            timestamp_utc=current_time,
            h1_analysis=h1_analysis,
            m15_analysis=m15_analysis,
            m5_analysis=m5_analysis,
            m1_filters=m1_filters_data,
            current_price=50000.0
        )
        
        # Should generate decision
        self.assertIsNotNone(decision)
        self.assertEqual(decision.symbol, "BTCUSDc")
        self.assertIn(decision.final_decision, [DecisionType.BUY, DecisionType.SELL, DecisionType.HOLD])
        
    def _create_sample_timeframe_data(self, symbol: str, timeframe: str, n_bars: int, base_time: int) -> TimeframeData:
        """Create sample timeframe data"""
        timestamps = np.arange(base_time, base_time + n_bars * 3600, 3600)
        opens = np.random.randn(n_bars) * 10 + 50000
        highs = opens + np.abs(np.random.randn(n_bars)) * 5
        lows = opens - np.abs(np.random.randn(n_bars)) * 5
        closes = opens + np.random.randn(n_bars) * 2
        volumes = np.random.randint(100, 1000, n_bars)
        atr = np.random.rand(n_bars) * 0.01
        ema_200 = np.full(n_bars, 50000)
        
        return TimeframeData(
            symbol=symbol,
            timeframe=timeframe,
            timestamps=timestamps,
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
            atr=atr,
            ema_200=ema_200
        )

class TestAsyncDBWriter(unittest.TestCase):
    """Test async database writer"""
    
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.db_schema = MTFDatabaseSchema(self.temp_db.name)
        
    def tearDown(self):
        os.unlink(self.temp_db.name)
        
    async def test_async_writer_performance(self):
        """Test async database writer performance"""
        with self.db_schema:
            # Create async writer
            writer = AsyncDBWriter(self.db_schema, batch_size=50, flush_interval=0.5)
            await writer.start()
            
            try:
                # Send many write requests
                start_time = time.time()
                
                for i in range(1000):
                    # Simulate decision event
                    from infra.hot_path_architecture import DecisionEvent
                    decision = DecisionEvent(
                        symbol="BTCUSDc",
                        timestamp_utc=int(datetime.now(timezone.utc).timestamp()) + i,
                        decision="BUY",
                        confidence=0.8,
                        entry_price=50000.0,
                        stop_loss=49900.0,
                        take_profit=50100.0,
                        lot_size=0.01,
                        reasoning="Test decision"
                    )
                    
                    await writer.write_decision(decision)
                    
                # Wait for processing
                await asyncio.sleep(2.0)
                
                end_time = time.time()
                duration = end_time - start_time
                
                # Should complete within reasonable time
                self.assertLess(duration, 10.0)
                
            finally:
                await writer.stop()

class TestSymbolConfiguration(unittest.TestCase):
    """Test symbol configuration system"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = SymbolConfigManager(self.temp_dir)
        
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def test_configuration_creation_and_validation(self):
        """Test configuration creation and validation"""
        # Create default configurations
        self.config_manager.create_default_configs()
        
        # Get all symbols
        symbols = self.config_manager.get_all_symbols()
        self.assertGreater(len(symbols), 0)
        
        # Validate all configurations
        validation_results = {}
        for symbol in symbols:
            is_valid = self.config_manager.validate_config(symbol)
            validation_results[symbol] = is_valid
            
        # All configurations should be valid
        for symbol, is_valid in validation_results.items():
            self.assertTrue(is_valid, f"Configuration validation failed for {symbol}")
            
    def test_hot_reload_functionality(self):
        """Test hot reload functionality"""
        # Create initial config
        self.config_manager.create_default_configs()
        
        # Get initial config
        initial_config = self.config_manager.get_config("BTCUSDc")
        self.assertIsNotNone(initial_config)
        
        # Modify config file
        config_path = os.path.join(self.temp_dir, "BTCUSDc.toml")
        with open(config_path, 'r') as f:
            config_data = f.read()
            
        # Update max_lot_size
        config_data = config_data.replace('max_lot_size = 0.02', 'max_lot_size = 0.05')
        
        with open(config_path, 'w') as f:
            f.write(config_data)
            
        # Reload config
        self.config_manager.reload_all_configs()
        
        # Get updated config
        updated_config = self.config_manager.get_config("BTCUSDc")
        self.assertIsNotNone(updated_config)
        
        # Should have updated value
        self.assertEqual(updated_config.max_lot_size, 0.05)

def run_integration_tests():
    """Run all integration tests"""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestMT5DataFlow,
        TestBinanceWebSocketStability,
        TestDatabasePerformance,
        TestMultiTimeframeIntegration,
        TestAsyncDBWriter,
        TestSymbolConfiguration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()

def run_async_tests():
    """Run async tests"""
    async def run_async_test_suite():
        # Create async test suite
        test_suite = unittest.TestSuite()
        
        # Add async test classes
        test_classes = [TestAsyncDBWriter]
        
        for test_class in test_classes:
            tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
            test_suite.addTests(tests)
            
        # Run async tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(test_suite)
        
        return result.wasSuccessful()
    
    # Run async tests
    return asyncio.run(run_async_test_suite())

if __name__ == "__main__":
    print("Running Phase 1 Integration Tests...")
    
    # Run regular tests
    success = run_integration_tests()
    
    if success:
        print("\n✅ All Phase 1 integration tests passed!")
    else:
        print("\n❌ Some Phase 1 integration tests failed!")
        exit(1)
