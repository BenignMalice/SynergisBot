"""
Phase 1 Component Tests
Unit tests for structure detection, M1 filters, database operations
"""

import unittest
import numpy as np
import asyncio
import tempfile
import os
from datetime import datetime, timezone
from typing import Dict, List, Any

# Import components to test
from app.engine.mtf_structure_analyzer import MTFStructureAnalyzer, TimeframeData, StructureSignal
from app.engine.m1_precision_filters import M1PrecisionFilters, TickData, M1FilterResult
from app.engine.mtf_decision_tree import MTFDecisionTree, BiasType, SetupType, DecisionType
from infra.mtf_database_schema import MTFDatabaseSchema
from infra.hot_path_architecture import HotPathProcessor, TickEvent, RingBuffer
from infra.binance_context_integration import BinanceContextAnalyzer, OrderBookSnapshot
from config.symbol_config import SymbolConfigManager, SymbolConfig

class TestMTFStructureAnalyzer(unittest.TestCase):
    """Test multi-timeframe structure analyzer"""
    
    def setUp(self):
        self.config = {
            'vwap_threshold': 0.2,
            'delta_threshold': 1.5,
            'atr_ratio_threshold': 0.5
        }
        self.analyzer = MTFStructureAnalyzer(self.config)
        
    def test_atr_calculation(self):
        """Test ATR calculation"""
        highs = np.array([100, 102, 101, 103, 105])
        lows = np.array([99, 100, 99, 101, 103])
        closes = np.array([101, 101, 102, 104, 104])
        
        atr = self.analyzer.calculate_atr(highs, lows, closes, period=3)
        
        # Should have non-zero ATR values
        self.assertGreater(len(atr), 0)
        self.assertTrue(np.all(atr >= 0))
        
    def test_ema_calculation(self):
        """Test EMA calculation"""
        prices = np.array([100, 101, 102, 103, 104, 105])
        ema = self.analyzer.calculate_ema(prices, period=3)
        
        # Should have same length as input
        self.assertEqual(len(ema), len(prices))
        # First value should be same as input
        self.assertEqual(ema[0], prices[0])
        
    def test_bos_detection(self):
        """Test Break of Structure detection"""
        # Create sample data with BOS pattern
        n_bars = 50
        timestamps = np.arange(1000, 1000 + n_bars * 3600, 3600)
        opens = np.random.randn(n_bars) * 10 + 50000
        highs = opens + np.abs(np.random.randn(n_bars)) * 5
        lows = opens - np.abs(np.random.randn(n_bars)) * 5
        closes = opens + np.random.randn(n_bars) * 2
        volumes = np.random.randint(100, 1000, n_bars)
        atr = np.random.rand(n_bars) * 0.01
        ema_200 = np.full(n_bars, 50000)
        
        data = TimeframeData(
            symbol="BTCUSDc",
            timeframe="H1",
            timestamps=timestamps,
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
            atr=atr,
            ema_200=ema_200
        )
        
        signals = self.analyzer.detect_bos(data)
        
        # Should return list of signals
        self.assertIsInstance(signals, list)
        
    def test_choch_detection(self):
        """Test Change of Character detection"""
        # Create sample data
        n_bars = 30
        timestamps = np.arange(1000, 1000 + n_bars * 3600, 3600)
        opens = np.random.randn(n_bars) * 10 + 50000
        highs = opens + np.abs(np.random.randn(n_bars)) * 5
        lows = opens - np.abs(np.random.randn(n_bars)) * 5
        closes = opens + np.random.randn(n_bars) * 2
        volumes = np.random.randint(100, 1000, n_bars)
        atr = np.random.rand(n_bars) * 0.01
        ema_200 = np.full(n_bars, 50000)
        
        data = TimeframeData(
            symbol="BTCUSDc",
            timeframe="H1",
            timestamps=timestamps,
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
            atr=atr,
            ema_200=ema_200
        )
        
        signals = self.analyzer.detect_choch(data)
        
        # Should return list of signals
        self.assertIsInstance(signals, list)

class TestM1PrecisionFilters(unittest.TestCase):
    """Test M1 precision filters"""
    
    def setUp(self):
        self.config = {
            'vwap_threshold': 0.2,
            'delta_threshold': 1.5,
            'atr_ratio_threshold': 0.5,
            'min_displacement_atr': 0.25,
            'max_displacement_atr': 0.5,
            'spread_median_window': 20,
            'spread_outlier_clip': 2.0
        }
        self.filters = M1PrecisionFilters(self.config)
        
    def test_vwap_calculation(self):
        """Test VWAP calculation"""
        ticks = np.array([50000, 50001, 50002, 50003, 50004])
        volumes = np.array([100, 150, 200, 120, 180])
        
        vwap = self.filters.calculate_vwap(ticks, volumes)
        
        # Should have same length as input
        self.assertEqual(len(vwap), len(ticks))
        # Should be monotonically increasing (cumulative)
        self.assertTrue(np.all(np.diff(vwap) >= 0))
        
    def test_rolling_median(self):
        """Test rolling median calculation"""
        data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        window = 3
        
        median = self.filters.calculate_rolling_median(data, window)
        
        # Should have same length as input
        self.assertEqual(len(median), len(data))
        
    def test_filter_analysis(self):
        """Test M1 filter analysis"""
        # Add sample ticks
        current_time = int(datetime.now(timezone.utc).timestamp())
        for i in range(50):
            tick = TickData(
                symbol="BTCUSDc",
                timestamp_utc=current_time - (50 - i) * 60,
                bid=50000.0 - 0.5,
                ask=50000.0 + 0.5,
                volume=100 + i * 10,
                spread=1.0
            )
            self.filters.add_tick(tick)
        
        # Test filter analysis
        result = self.filters.analyze_filters("BTCUSDc", 50000.0, current_time)
        
        # Should return M1FilterResult
        self.assertIsInstance(result, M1FilterResult)
        self.assertEqual(result.symbol, "BTCUSDc")
        self.assertIsInstance(result.filters_passed, int)
        self.assertIsInstance(result.filter_score, float)
        self.assertIsInstance(result.confidence, float)

class TestMTFDecisionTree(unittest.TestCase):
    """Test multi-timeframe decision tree"""
    
    def setUp(self):
        self.config = {
            'max_lot_size': 0.01,
            'default_risk_percent': 0.5,
            'min_m1_filters': 3,
            'atr_value': 0.001
        }
        self.decision_tree = MTFDecisionTree(self.config)
        
    def test_h1_bias_analysis(self):
        """Test H1 bias analysis"""
        h1_data = {
            'close': 50000.0,
            'ema_200': 49500.0,
            'structure_signals': [
                {'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': 1000}
            ]
        }
        
        bias = self.decision_tree.analyze_h1_bias(h1_data)
        
        # Should return BiasType enum
        self.assertIn(bias, [BiasType.BULLISH, BiasType.BEARISH, BiasType.NEUTRAL])
        
    def test_m15_setup_analysis(self):
        """Test M15 setup analysis"""
        m15_data = {
            'structure_signals': [
                {'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': 1000}
            ]
        }
        
        setup = self.decision_tree.analyze_m15_setup(m15_data, BiasType.BULLISH)
        
        # Should return SetupType enum
        self.assertIn(setup, [SetupType.BOS, SetupType.CHOCH, SetupType.OB_RETEST, SetupType.NONE])
        
    def test_decision_making(self):
        """Test complete decision making process"""
        h1_analysis = {
            'close': 50000.0,
            'ema_200': 49500.0,
            'structure_signals': [
                {'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': 1000}
            ]
        }
        
        m15_analysis = {
            'structure_signals': [
                {'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': 1000}
            ]
        }
        
        m5_analysis = {
            'structure_signals': [
                {'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': 1000}
            ]
        }
        
        m1_filters = {
            'filters_passed': 4,
            'filter_score': 0.8
        }
        
        decision = self.decision_tree.make_decision(
            symbol="BTCUSDc",
            timestamp_utc=int(datetime.now(timezone.utc).timestamp()),
            h1_analysis=h1_analysis,
            m15_analysis=m15_analysis,
            m5_analysis=m5_analysis,
            m1_filters=m1_filters,
            current_price=50000.0
        )
        
        # Should return MTFDecision
        self.assertIsNotNone(decision)
        self.assertEqual(decision.symbol, "BTCUSDc")
        self.assertIn(decision.final_decision, [DecisionType.BUY, DecisionType.SELL, DecisionType.HOLD])

class TestMTFDatabaseSchema(unittest.TestCase):
    """Test multi-timeframe database schema"""
    
    def setUp(self):
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.db_schema = MTFDatabaseSchema(self.temp_db.name)
        
    def tearDown(self):
        # Clean up temporary database
        os.unlink(self.temp_db.name)
        
    def test_database_creation(self):
        """Test database table creation"""
        with self.db_schema:
            # Should create tables without error
            pass
            
    def test_structure_analysis_insertion(self):
        """Test structure analysis data insertion"""
        with self.db_schema:
            self.db_schema.insert_structure_analysis(
                symbol="BTCUSDc",
                timeframe="H1",
                timestamp_utc=int(datetime.now(timezone.utc).timestamp()),
                structure_type="BOS",
                structure_data={"price": 50000, "volume": 1000},
                confidence_score=0.85
            )
            
    def test_m1_filters_insertion(self):
        """Test M1 filters data insertion"""
        with self.db_schema:
            self.db_schema.insert_m1_filters(
                symbol="BTCUSDc",
                timestamp_utc=int(datetime.now(timezone.utc).timestamp()),
                vwap_reclaim=True,
                delta_spike=True,
                micro_bos=False,
                atr_ratio_valid=True,
                spread_valid=True,
                filters_passed=4,
                filter_score=0.8
            )
            
    def test_trade_decision_insertion(self):
        """Test trade decision data insertion"""
        with self.db_schema:
            self.db_schema.insert_trade_decision(
                symbol="BTCUSDc",
                timestamp_utc=int(datetime.now(timezone.utc).timestamp()),
                h4_bias="BULLISH",
                h1_bias="BULLISH",
                m30_setup="BOS",
                m15_setup="OB_RETEST",
                m5_structure="BULLISH",
                m1_confirmation=True,
                decision="BUY",
                confidence=0.88,
                risk_reward=3.2
            )

class TestHotPathArchitecture(unittest.TestCase):
    """Test hot path architecture components"""
    
    def setUp(self):
        self.config = {
            'buffer_capacity': 1000,
            'batch_size': 50,
            'flush_interval': 1.0
        }
        
    def test_ring_buffer(self):
        """Test ring buffer functionality"""
        buffer = RingBuffer(10)
        
        # Add values
        for i in range(15):  # More than capacity
            buffer.append(float(i))
            
        # Should only keep latest values
        latest = buffer.get_latest(5)
        self.assertEqual(len(latest), 5)
        
        # Should be the last 5 values added
        expected = [10, 11, 12, 13, 14]
        np.testing.assert_array_almost_equal(latest, expected)
        
    def test_hot_path_processor(self):
        """Test hot path processor"""
        processor = HotPathProcessor("BTCUSDc", self.config)
        
        # Add sample tick
        tick = TickEvent(
            symbol="BTCUSDc",
            timestamp_utc=int(datetime.now(timezone.utc).timestamp()),
            bid=50000.0,
            ask=50000.5,
            volume=100.0,
            source="mt5",
            sequence_id=1
        )
        
        processor.add_tick(tick)
        
        # Should process without error
        metrics = processor.get_performance_metrics()
        self.assertIsInstance(metrics, dict)

class TestBinanceContextIntegration(unittest.TestCase):
    """Test Binance context integration"""
    
    def setUp(self):
        self.config = {
            'large_order_threshold': 0.1,
            'support_resistance_lookback': 50,
            'volume_imbalance_threshold': 0.3
        }
        self.analyzer = BinanceContextAnalyzer("BTCUSDc", self.config)
        
    def test_order_book_analysis(self):
        """Test order book analysis"""
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
        
        microstructure = self.analyzer.analyze_order_book(snapshot)
        
        # Should return MarketMicrostructure
        self.assertIsNotNone(microstructure)
        self.assertEqual(microstructure.symbol, "BTCUSDc")
        self.assertIsInstance(microstructure.bid_ask_spread, float)
        self.assertIsInstance(microstructure.volume_imbalance, float)

class TestSymbolConfigManager(unittest.TestCase):
    """Test symbol configuration manager"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = SymbolConfigManager(self.temp_dir)
        
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def test_config_creation(self):
        """Test configuration file creation"""
        self.config_manager.create_default_configs()
        
        # Should create config files
        symbols = self.config_manager.get_all_symbols()
        self.assertGreater(len(symbols), 0)
        
        # Should include test symbols
        self.assertIn("BTCUSDc", symbols)
        self.assertIn("XAUUSDc", symbols)
        self.assertIn("EURUSDc", symbols)
        
    def test_config_validation(self):
        """Test configuration validation"""
        self.config_manager.create_default_configs()
        
        # Should validate all configs
        results = {}
        symbols = self.config_manager.get_all_symbols()
        for symbol in symbols:
            results[symbol] = self.config_manager.validate_config(symbol)
            
        # All configs should be valid
        for symbol, is_valid in results.items():
            self.assertTrue(is_valid, f"Config validation failed for {symbol}")

class TestIntegration(unittest.TestCase):
    """Integration tests for Phase 1 components"""
    
    def test_end_to_end_decision_flow(self):
        """Test complete decision flow from data to decision"""
        # This would test the complete flow:
        # 1. Structure analysis
        # 2. M1 filters
        # 3. Decision tree
        # 4. Database storage
        
        # For now, just test that components can be instantiated together
        config = {
            'max_lot_size': 0.01,
            'default_risk_percent': 0.5,
            'vwap_threshold': 0.2,
            'delta_threshold': 1.5
        }
        
        # Test component instantiation
        from app.engine.mtf_structure_analyzer import MTFStructureAnalyzer
        from app.engine.m1_precision_filters import M1PrecisionFilters
        from app.engine.mtf_decision_tree import MTFDecisionTree
        
        analyzer = MTFStructureAnalyzer(config)
        filters = M1PrecisionFilters(config)
        decision_tree = MTFDecisionTree(config)
        
        # Should instantiate without error
        self.assertIsNotNone(analyzer)
        self.assertIsNotNone(filters)
        self.assertIsNotNone(decision_tree)

def run_phase1_tests():
    """Run all Phase 1 tests"""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestMTFStructureAnalyzer,
        TestM1PrecisionFilters,
        TestMTFDecisionTree,
        TestMTFDatabaseSchema,
        TestHotPathArchitecture,
        TestBinanceContextIntegration,
        TestSymbolConfigManager,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_phase1_tests()
    if success:
        print("\n✅ All Phase 1 tests passed!")
    else:
        print("\n❌ Some Phase 1 tests failed!")
        exit(1)
