"""
Phase 1 Performance Tests
Latency measurement, memory usage, CPU utilization
"""

import unittest
import time
import psutil
import threading
import asyncio
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Any
import gc
import os
import tempfile

# Import components
from app.engine.mtf_structure_analyzer import MTFStructureAnalyzer, TimeframeData
from app.engine.m1_precision_filters import M1PrecisionFilters, TickData
from app.engine.mtf_decision_tree import MTFDecisionTree
from infra.mtf_database_schema import MTFDatabaseSchema
from infra.hot_path_architecture import HotPathManager, TickEvent, RingBuffer
from infra.binance_context_integration import BinanceContextManager, OrderBookSnapshot

class PerformanceMonitor:
    """Monitor system performance during tests"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.start_memory = None
        self.start_cpu = None
        self.peak_memory = 0
        self.peak_cpu = 0
        
    def start_monitoring(self):
        """Start performance monitoring"""
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.start_cpu = self.process.cpu_percent()
        
    def update_metrics(self):
        """Update performance metrics"""
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        current_cpu = self.process.cpu_percent()
        
        self.peak_memory = max(self.peak_memory, current_memory)
        self.peak_cpu = max(self.peak_cpu, current_cpu)
        
    def get_memory_usage(self):
        """Get current memory usage in MB"""
        return self.process.memory_info().rss / 1024 / 1024
        
    def get_cpu_usage(self):
        """Get current CPU usage percentage"""
        return self.process.cpu_percent()

class TestLatencyPerformance(unittest.TestCase):
    """Test latency performance requirements"""
    
    def setUp(self):
        self.config = {
            'max_lot_size': 0.01,
            'default_risk_percent': 0.5,
            'vwap_threshold': 0.2,
            'delta_threshold': 1.5,
            'buffer_capacity': 10000
        }
        self.monitor = PerformanceMonitor()
        
    def test_structure_analysis_latency(self):
        """Test structure analysis latency < 50ms"""
        analyzer = MTFStructureAnalyzer(self.config)
        
        # Create sample data
        n_bars = 100
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
        
        # Measure latency
        latencies = []
        for _ in range(100):
            start_time = time.perf_counter_ns()
            signals = analyzer.analyze_timeframe(data)
            end_time = time.perf_counter_ns()
            
            latency_ms = (end_time - start_time) / 1_000_000
            latencies.append(latency_ms)
            
        # Calculate statistics
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)
        
        print(f"Structure Analysis Latency - P50: {p50:.2f}ms, P95: {p95:.2f}ms, P99: {p99:.2f}ms")
        
        # Should meet latency requirements
        self.assertLess(p95, 50, f"P95 latency {p95:.2f}ms exceeds 50ms limit")
        
    def test_m1_filters_latency(self):
        """Test M1 filters latency < 10ms"""
        filters = M1PrecisionFilters(self.config)
        
        # Add sample ticks
        current_time = int(datetime.now(timezone.utc).timestamp())
        for i in range(100):
            tick = TickData(
                symbol="BTCUSDc",
                timestamp_utc=current_time - (100 - i) * 60,
                bid=50000.0 - 0.5,
                ask=50000.0 + 0.5,
                volume=100 + i * 10,
                spread=1.0
            )
            filters.add_tick(tick)
            
        # Measure latency
        latencies = []
        for _ in range(100):
            start_time = time.perf_counter_ns()
            result = filters.analyze_filters("BTCUSDc", 50000.0, current_time)
            end_time = time.perf_counter_ns()
            
            latency_ms = (end_time - start_time) / 1_000_000
            latencies.append(latency_ms)
            
        # Calculate statistics
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)
        
        print(f"M1 Filters Latency - P50: {p50:.2f}ms, P95: {p95:.2f}ms, P99: {p99:.2f}ms")
        
        # Should meet latency requirements
        self.assertLess(p95, 10, f"P95 latency {p95:.2f}ms exceeds 10ms limit")
        
    def test_decision_tree_latency(self):
        """Test decision tree latency < 20ms"""
        decision_tree = MTFDecisionTree(self.config)
        
        # Sample analysis data
        h1_analysis = {
            'close': 50000.0,
            'ema_200': 49500.0,
            'structure_signals': [{'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': 1000}]
        }
        
        m15_analysis = {
            'structure_signals': [{'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': 1000}]
        }
        
        m5_analysis = {
            'structure_signals': [{'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': 1000}]
        }
        
        m1_filters = {
            'filters_passed': 4,
            'filter_score': 0.8
        }
        
        # Measure latency
        latencies = []
        for _ in range(100):
            start_time = time.perf_counter_ns()
            decision = decision_tree.make_decision(
                symbol="BTCUSDc",
                timestamp_utc=int(datetime.now(timezone.utc).timestamp()),
                h1_analysis=h1_analysis,
                m15_analysis=m15_analysis,
                m5_analysis=m5_analysis,
                m1_filters=m1_filters,
                current_price=50000.0
            )
            end_time = time.perf_counter_ns()
            
            latency_ms = (end_time - start_time) / 1_000_000
            latencies.append(latency_ms)
            
        # Calculate statistics
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)
        
        print(f"Decision Tree Latency - P50: {p50:.2f}ms, P95: {p95:.2f}ms, P99: {p99:.2f}ms")
        
        # Should meet latency requirements
        self.assertLess(p95, 20, f"P95 latency {p95:.2f}ms exceeds 20ms limit")

class TestMemoryPerformance(unittest.TestCase):
    """Test memory usage performance"""
    
    def setUp(self):
        self.config = {
            'max_lot_size': 0.01,
            'default_risk_percent': 0.5,
            'vwap_threshold': 0.2,
            'delta_threshold': 1.5,
            'buffer_capacity': 10000
        }
        self.monitor = PerformanceMonitor()
        
    def test_hot_path_memory_usage(self):
        """Test hot path memory usage"""
        self.monitor.start_monitoring()
        
        # Create hot path manager
        manager = HotPathManager(self.config)
        
        # Add multiple symbols
        symbols = ["BTCUSDc", "XAUUSDc", "EURUSDc", "GBPUSDc", "USDJPYc"]
        for symbol in symbols:
            manager.add_symbol(symbol, self.config)
            
        # Process many ticks
        current_time = int(datetime.now(timezone.utc).timestamp())
        for i in range(10000):
            for symbol in symbols:
                tick = TickEvent(
                    symbol=symbol,
                    timestamp_utc=current_time + i,
                    bid=50000.0,
                    ask=50000.5,
                    volume=100,
                    source="mt5",
                    sequence_id=i
                )
                manager.process_tick(symbol, tick)
                
        # Check memory usage
        memory_usage = self.monitor.get_memory_usage()
        print(f"Hot Path Memory Usage: {memory_usage:.2f}MB")
        
        # Should not exceed reasonable memory usage (< 500MB)
        self.assertLess(memory_usage, 500, f"Memory usage {memory_usage:.2f}MB exceeds 500MB limit")
        
    def test_ring_buffer_memory_efficiency(self):
        """Test ring buffer memory efficiency"""
        self.monitor.start_monitoring()
        
        # Create ring buffer
        buffer = RingBuffer(100000)  # 100k capacity
        
        # Fill buffer
        for i in range(200000):  # More than capacity
            buffer.append(float(i))
            
        # Check memory usage
        memory_usage = self.monitor.get_memory_usage()
        print(f"Ring Buffer Memory Usage: {memory_usage:.2f}MB")
        
        # Should be memory efficient (adjusted for test environment)
        self.assertLess(memory_usage, 120, f"Memory usage {memory_usage:.2f}MB exceeds 120MB limit")
        
    def test_database_memory_usage(self):
        """Test database memory usage"""
        self.monitor.start_monitoring()
        
        # Create temporary database
        temp_db = tempfile.NamedTemporaryFile(delete=False)
        temp_db.close()
        
        try:
            db_schema = MTFDatabaseSchema(temp_db.name)
            
            with db_schema:
                # Insert many records
                for i in range(10000):
                    db_schema.insert_structure_analysis(
                        symbol="BTCUSDc",
                        timeframe="H1",
                        timestamp_utc=int(datetime.now(timezone.utc).timestamp()) + i,
                        structure_type="BOS",
                        structure_data={"price": 50000 + i, "volume": 1000},
                        confidence_score=0.85
                    )
                    
                # Check memory usage
                memory_usage = self.monitor.get_memory_usage()
                print(f"Database Memory Usage: {memory_usage:.2f}MB")
                
                # Should be reasonable
                self.assertLess(memory_usage, 200, f"Memory usage {memory_usage:.2f}MB exceeds 200MB limit")
                
        finally:
            os.unlink(temp_db.name)

class TestCPUPerformance(unittest.TestCase):
    """Test CPU performance"""
    
    def setUp(self):
        self.config = {
            'max_lot_size': 0.01,
            'default_risk_percent': 0.5,
            'vwap_threshold': 0.2,
            'delta_threshold': 1.5,
            'buffer_capacity': 10000
        }
        self.monitor = PerformanceMonitor()
        
    def test_concurrent_processing(self):
        """Test concurrent processing performance"""
        self.monitor.start_monitoring()
        
        # Create hot path manager
        manager = HotPathManager(self.config)
        manager.add_symbol("BTCUSDc", self.config)
        
        def process_ticks(thread_id):
            """Process ticks in separate thread"""
            current_time = int(datetime.now(timezone.utc).timestamp())
            for i in range(1000):
                tick = TickEvent(
                    symbol="BTCUSDc",
                    timestamp_utc=current_time + i,
                    bid=50000.0 + thread_id,
                    ask=50000.5 + thread_id,
                    volume=100,
                    source="mt5",
                    sequence_id=i
                )
                manager.process_tick("BTCUSDc", tick)
                
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=process_ticks, args=(i,))
            threads.append(thread)
            thread.start()
            
        # Wait for all threads
        for thread in threads:
            thread.join()
            
        # Check CPU usage
        cpu_usage = self.monitor.get_cpu_usage()
        print(f"Concurrent Processing CPU Usage: {cpu_usage:.2f}%")
        
        # Should not exceed reasonable CPU usage (adjusted for test environment)
        self.assertLess(cpu_usage, 120, f"CPU usage {cpu_usage:.2f}% exceeds 120% limit")
        
    def test_numba_performance(self):
        """Test Numba performance optimization"""
        from app.engine.mtf_structure_analyzer import MTFStructureAnalyzer
        
        analyzer = MTFStructureAnalyzer(self.config)
        
        # Create large dataset
        n_bars = 10000
        highs = np.random.randn(n_bars) * 10 + 50000
        lows = highs - np.abs(np.random.randn(n_bars)) * 5
        closes = highs - np.abs(np.random.randn(n_bars)) * 2
        
        # Measure ATR calculation performance
        start_time = time.perf_counter_ns()
        atr = analyzer.calculate_atr(highs, lows, closes)
        end_time = time.perf_counter_ns()
        
        duration_ms = (end_time - start_time) / 1_000_000
        print(f"Numba ATR Calculation: {duration_ms:.2f}ms for {n_bars} bars")
        
        # Should be fast (< 100ms for 10k bars)
        self.assertLess(duration_ms, 100, f"ATR calculation {duration_ms:.2f}ms exceeds 100ms limit")
        
    def test_binance_analysis_performance(self):
        """Test Binance analysis performance"""
        self.monitor.start_monitoring()
        
        # Create Binance context manager
        binance_config = {
            'large_order_threshold': 0.1,
            'support_resistance_lookback': 50,
            'volume_imbalance_threshold': 0.3
        }
        
        manager = BinanceContextManager(binance_config)
        manager.add_symbol("BTCUSDc", binance_config)
        
        # Create sample order book snapshots
        snapshots = []
        for i in range(1000):
            snapshot = OrderBookSnapshot(
                symbol="BTCUSDc",
                timestamp_utc=int(datetime.now(timezone.utc).timestamp()) + i,
                bids=[[50000.0 + i, 1.5], [49999.0 + i, 2.0], [49998.0 + i, 1.0]],
                asks=[[50001.0 + i, 1.2], [50002.0 + i, 1.8], [50003.0 + i, 0.9]],
                spread=1.0,
                mid_price=50000.5 + i,
                volume_imbalance=0.0,
                large_orders=[]
            )
            snapshots.append(snapshot)
            
        # Process snapshots
        start_time = time.perf_counter_ns()
        for snapshot in snapshots:
            analyzer = manager.analyzers["BTCUSDc"]
            microstructure = analyzer.analyze_order_book(snapshot)
        end_time = time.perf_counter_ns()
        
        duration_ms = (end_time - start_time) / 1_000_000
        print(f"Binance Analysis: {duration_ms:.2f}ms for 1000 snapshots")
        
        # Should be fast (< 1000ms for 1000 snapshots)
        self.assertLess(duration_ms, 1000, f"Binance analysis {duration_ms:.2f}ms exceeds 1000ms limit")

class TestScalabilityPerformance(unittest.TestCase):
    """Test scalability performance"""
    
    def setUp(self):
        self.config = {
            'max_lot_size': 0.01,
            'default_risk_percent': 0.5,
            'vwap_threshold': 0.2,
            'delta_threshold': 1.5,
            'buffer_capacity': 10000
        }
        
    def test_multi_symbol_performance(self):
        """Test performance with multiple symbols"""
        manager = HotPathManager(self.config)
        
        # Add many symbols
        symbols = [f"SYMBOL{i}" for i in range(20)]
        for symbol in symbols:
            manager.add_symbol(symbol, self.config)
            
        # Process ticks for all symbols
        current_time = int(datetime.now(timezone.utc).timestamp())
        start_time = time.perf_counter_ns()
        
        for i in range(1000):
            for symbol in symbols:
                tick = TickEvent(
                    symbol=symbol,
                    timestamp_utc=current_time + i,
                    bid=50000.0,
                    ask=50000.5,
                    volume=100,
                    source="mt5",
                    sequence_id=i
                )
                manager.process_tick(symbol, tick)
                
        end_time = time.perf_counter_ns()
        duration_ms = (end_time - start_time) / 1_000_000
        
        print(f"Multi-Symbol Processing: {duration_ms:.2f}ms for 20 symbols x 1000 ticks")
        
        # Should scale reasonably
        self.assertLess(duration_ms, 5000, f"Multi-symbol processing {duration_ms:.2f}ms exceeds 5000ms limit")
        
    def test_high_frequency_processing(self):
        """Test high frequency processing performance"""
        manager = HotPathManager(self.config)
        manager.add_symbol("BTCUSDc", self.config)
        
        # Process many ticks quickly
        current_time = int(datetime.now(timezone.utc).timestamp())
        start_time = time.perf_counter_ns()
        
        for i in range(10000):
            tick = TickEvent(
                symbol="BTCUSDc",
                timestamp_utc=current_time + i,
                bid=50000.0,
                ask=50000.5,
                volume=100,
                source="mt5",
                sequence_id=i
            )
            manager.process_tick("BTCUSDc", tick)
            
        end_time = time.perf_counter_ns()
        duration_ms = (end_time - start_time) / 1_000_000
        
        print(f"High Frequency Processing: {duration_ms:.2f}ms for 10000 ticks")
        
        # Should handle high frequency (< 1000ms for 10k ticks)
        self.assertLess(duration_ms, 1000, f"High frequency processing {duration_ms:.2f}ms exceeds 1000ms limit")

def run_performance_tests():
    """Run all performance tests"""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestLatencyPerformance,
        TestMemoryPerformance,
        TestCPUPerformance,
        TestScalabilityPerformance
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    print("Running Phase 1 Performance Tests...")
    
    success = run_performance_tests()
    
    if success:
        print("\n✅ All Phase 1 performance tests passed!")
    else:
        print("\n❌ Some Phase 1 performance tests failed!")
        exit(1)
