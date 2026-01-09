# =====================================
# tests/test_phase5_8_e2e.py
# =====================================
"""
Tests for Phase 5.8: End-to-End Testing
Tests complete workflows and scenarios
"""

import unittest
import sys
import os
import tempfile
import shutil
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_data_fetcher import M1DataFetcher
from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
from infra.m1_refresh_manager import M1RefreshManager
from infra.m1_snapshot_manager import M1SnapshotManager
from infra.m1_monitoring import M1Monitoring


class TestPhase5_8E2E(unittest.TestCase):
    """Test cases for Phase 5.8 End-to-End Testing"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock MT5Service
        self.mock_mt5 = Mock()
        self.mock_mt5.get_bars = Mock(return_value=self._generate_mock_bars(200))
        self.mock_mt5.get_quote = Mock(return_value=Mock(bid=2400.0, ask=2400.1))
        
        # Initialize components
        self.fetcher = M1DataFetcher(data_source=self.mock_mt5, max_candles=200, cache_ttl=300)
        self.analyzer = M1MicrostructureAnalyzer()
        self.monitoring = M1Monitoring()
        
        # Temp directory for snapshots
        self.temp_dir = tempfile.mkdtemp()
        
        # Refresh manager
        self.refresh_manager = M1RefreshManager(
            fetcher=self.fetcher,
            refresh_interval_active=30,
            refresh_interval_inactive=300,
            monitoring=self.monitoring
        )
        
        # Snapshot manager
        self.snapshot_manager = M1SnapshotManager(
            fetcher=self.fetcher,
            snapshot_directory=self.temp_dir,
            use_compression=False  # Disable for faster tests
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _generate_mock_bars(self, count: int):
        """Generate mock candlestick data"""
        base_time = datetime.now(timezone.utc) - timedelta(minutes=count)
        bars = []
        for i in range(count):
            bars.append({
                'time': base_time + timedelta(minutes=i),
                'open': 2400.0 + (i * 0.1),
                'high': 2400.5 + (i * 0.1),
                'low': 2399.5 + (i * 0.1),
                'close': 2400.2 + (i * 0.1),
                'tick_volume': 100 + i
            })
        return bars
    
    def _generate_mock_candles(self, count: int, symbol: str = 'XAUUSD'):
        """Generate mock candle dicts"""
        base_time = datetime.now(timezone.utc) - timedelta(minutes=count)
        candles = []
        for i in range(count):
            candles.append({
                'timestamp': base_time + timedelta(minutes=i),
                'open': 2400.0 + (i * 0.1),
                'high': 2400.5 + (i * 0.1),
                'low': 2399.5 + (i * 0.1),
                'close': 2400.2 + (i * 0.1),
                'volume': 100 + i,
                'symbol': f'{symbol}c'
            })
        return candles
    
    def test_complete_analysis_flow(self):
        """Test Complete Analysis Flow: User requests analysis → M1 data fetched → Analyzed → Included in response"""
        symbol = 'XAUUSD'
        
        # Step 1: Fetch M1 data
        candles = self.fetcher.fetch_m1_data(symbol, count=200)
        self.assertGreater(len(candles), 0, "Should fetch M1 data")
        
        # Step 2: Analyze
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        self.assertIsNotNone(analysis, "Should analyze M1 data")
        self.assertTrue(analysis.get('available', False), "Analysis should be available")
        
        # Step 3: Verify all M1 insights are present
        self.assertIn('choch_bos', analysis, "Should have CHOCH/BOS")
        self.assertIn('liquidity_zones', analysis, "Should have liquidity zones")
        self.assertIn('volatility', analysis, "Should have volatility state")
        self.assertIn('signal_summary', analysis, "Should have signal summary")
        self.assertIn('microstructure_confluence', analysis, "Should have confluence")
        
        # Step 4: Verify insights are accurate (basic checks)
        signal_summary = analysis.get('signal_summary', '')
        self.assertIsInstance(signal_summary, str, "Signal summary should be string")
        self.assertGreater(len(signal_summary), 0, "Signal summary should not be empty")
        
        confluence = analysis.get('microstructure_confluence', {})
        if confluence:
            base_score = confluence.get('base_score', 0)
            self.assertGreaterEqual(base_score, 0, "Confluence score should be >= 0")
            self.assertLessEqual(base_score, 100, "Confluence score should be <= 100")
    
    def test_auto_execution_flow(self):
        """Test Auto-Execution Flow: Create CHOCH plan → M1 monitors conditions → M1 detects CHOCH → Plan executes"""
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(200)
        
        # Step 1: Analyze M1 data
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        self.assertIsNotNone(analysis, "Should analyze M1 data")
        
        # Step 2: Check for CHOCH/BOS
        choch_bos = analysis.get('choch_bos', {})
        self.assertIsNotNone(choch_bos, "Should have CHOCH/BOS data")
        
        # Step 3: Verify confidence weighting
        confluence = analysis.get('microstructure_confluence', {})
        if confluence:
            base_score = confluence.get('base_score', 0)
            self.assertGreaterEqual(base_score, 0, "Should have confidence score")
            
            # Check dynamic threshold if available
            dynamic_threshold = analysis.get('dynamic_threshold')
            if dynamic_threshold:
                self.assertGreater(dynamic_threshold, 0, "Dynamic threshold should be > 0")
        
        # Step 4: Verify M1 context is available for logging
        signal_summary = analysis.get('signal_summary', '')
        self.assertIsNotNone(signal_summary, "Should have signal summary for logging")
        
        # Note: Actual plan execution would require AutoExecutionSystem integration
        # This test verifies that M1 data is ready for auto-execution
    
    def test_crash_recovery_flow(self):
        """Test Crash Recovery Flow: System running → Snapshot created → System crashes → System restarts → Snapshot loaded → Continues monitoring"""
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(200)
        
        # Step 1: System running - fetch and analyze
        self.fetcher.fetch_m1_data(symbol, count=200)
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        self.assertTrue(analysis.get('available', False), "System should be running")
        
        # Step 2: Create snapshot
        snapshot_created = self.snapshot_manager.create_snapshot_atomic(symbol, candles)
        self.assertTrue(snapshot_created, "Snapshot should be created")
        
        # Step 3: Simulate crash - clear fetcher cache
        self.fetcher._data_cache.clear()
        
        # Step 4: System restarts - load snapshot
        loaded_candles = self.snapshot_manager.load_snapshot(symbol, max_age_seconds=3600)
        self.assertIsNotNone(loaded_candles, "Should load snapshot")
        self.assertGreater(len(loaded_candles), 0, "Loaded candles should not be empty")
        
        # Step 5: Verify data integrity
        self.assertEqual(len(loaded_candles), len(candles), "Loaded candles count should match")
        
        # Step 6: Verify can continue monitoring
        restored_analysis = self.analyzer.analyze_microstructure(symbol, loaded_candles)
        self.assertIsNotNone(restored_analysis, "Should be able to continue analysis")
        self.assertTrue(restored_analysis.get('available', False), "Analysis should be available after recovery")
        
        # Verify no data loss
        self.assertEqual(restored_analysis['symbol'], analysis['symbol'], "Symbol should match")
        self.assertEqual(restored_analysis['candle_count'], analysis['candle_count'], "Candle count should match")
    
    def test_multi_symbol_flow(self):
        """Test Multi-Symbol Flow: Monitor 5 symbols simultaneously → All refresh correctly → All analyze correctly"""
        symbols = ['XAUUSD', 'BTCUSD', 'EURUSD', 'GBPUSD', 'USDJPY']
        
        # Step 1: Fetch data for all symbols
        fetched_data = {}
        for symbol in symbols:
            candles = self.fetcher.fetch_m1_data(symbol, count=200)
            fetched_data[symbol] = candles
            self.assertGreater(len(candles), 0, f"Should fetch data for {symbol}")
        
        # Step 2: Analyze all symbols
        analyses = {}
        for symbol in symbols:
            candles = fetched_data[symbol]
            analysis = self.analyzer.analyze_microstructure(symbol, candles)
            analyses[symbol] = analysis
            self.assertIsNotNone(analysis, f"Should analyze {symbol}")
            self.assertTrue(analysis.get('available', False), f"Analysis should be available for {symbol}")
        
        # Step 3: Verify all symbols analyzed correctly
        self.assertEqual(len(analyses), len(symbols), "All symbols should be analyzed")
        
        # Step 4: Verify resource usage stays within limits
        # Check cache sizes
        fetcher_cache_size = len(self.fetcher._data_cache)
        analyzer_cache_size = len(self.analyzer._analysis_cache)
        
        # Cache should not grow unbounded
        self.assertLessEqual(fetcher_cache_size, len(symbols) * 2, "Fetcher cache should be reasonable")
        self.assertLessEqual(analyzer_cache_size, len(symbols) * 2, "Analyzer cache should be reasonable")
        
        # Step 5: Verify no interference between symbols
        for symbol in symbols:
            analysis = analyses[symbol]
            self.assertEqual(analysis['symbol'], symbol.rstrip('c'), f"Symbol should match for {symbol}")
    
    def test_refresh_during_analysis(self):
        """Test that M1 data can be refreshed during analysis"""
        symbol = 'XAUUSD'
        
        # Step 1: Initial fetch
        candles1 = self.fetcher.fetch_m1_data(symbol, count=200)
        self.assertGreater(len(candles1), 0, "Should fetch initial data")
        
        # Step 2: Analyze
        analysis1 = self.analyzer.analyze_microstructure(symbol, candles1)
        self.assertTrue(analysis1.get('available', False), "Initial analysis should work")
        
        # Step 3: Refresh data
        refresh_success = self.refresh_manager.refresh_symbol(symbol, force=True)
        self.assertTrue(refresh_success, "Refresh should succeed")
        
        # Step 4: Fetch refreshed data
        candles2 = self.fetcher.fetch_m1_data(symbol, count=200)
        self.assertGreater(len(candles2), 0, "Should fetch refreshed data")
        
        # Step 5: Analyze refreshed data
        analysis2 = self.analyzer.analyze_microstructure(symbol, candles2)
        self.assertTrue(analysis2.get('available', False), "Refreshed analysis should work")
        
        # Both analyses should be valid
        self.assertIsNotNone(analysis1, "Initial analysis should be valid")
        self.assertIsNotNone(analysis2, "Refreshed analysis should be valid")
    
    def test_batch_operations(self):
        """Test batch operations for multiple symbols"""
        symbols = ['XAUUSD', 'BTCUSD', 'EURUSD']
        
        # Step 1: Batch fetch
        fetched_data = {}
        for symbol in symbols:
            candles = self.fetcher.fetch_m1_data(symbol, count=200)
            fetched_data[symbol] = candles
        
        # Step 2: Batch analyze
        analyses = {}
        for symbol in symbols:
            candles = fetched_data[symbol]
            analysis = self.analyzer.analyze_microstructure(symbol, candles)
            analyses[symbol] = analysis
        
        # Step 3: Batch refresh (async)
        async def batch_refresh():
            await self.refresh_manager.refresh_symbols_batch(symbols)
        
        asyncio.run(batch_refresh())
        
        # Step 4: Verify all operations completed
        self.assertEqual(len(fetched_data), len(symbols), "All symbols should be fetched")
        self.assertEqual(len(analyses), len(symbols), "All symbols should be analyzed")
        
        # All analyses should be available
        for symbol, analysis in analyses.items():
            self.assertTrue(analysis.get('available', False), f"Analysis should be available for {symbol}")
    
    def test_error_recovery_flow(self):
        """Test error recovery flow: Error occurs → System recovers → Continues operation"""
        symbol = 'XAUUSD'
        
        # Step 1: Normal operation
        candles = self.fetcher.fetch_m1_data(symbol, count=200)
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        self.assertTrue(analysis.get('available', False), "Normal operation should work")
        
        # Step 2: Simulate error (connection failure)
        self.mock_mt5.get_bars = Mock(side_effect=Exception("Connection failed"))
        
        # Step 3: Try to fetch (should handle gracefully)
        error_candles = self.fetcher.fetch_m1_data(symbol, count=200)
        # Should return empty list or cached data
        self.assertIsNotNone(error_candles, "Should handle error gracefully")
        
        # Step 4: Restore connection
        self.mock_mt5.get_bars = Mock(return_value=self._generate_mock_bars(200))
        
        # Step 5: Verify system recovers
        recovered_candles = self.fetcher.fetch_m1_data(symbol, count=200)
        self.assertGreater(len(recovered_candles), 0, "Should recover from error")
        
        recovered_analysis = self.analyzer.analyze_microstructure(symbol, recovered_candles)
        self.assertTrue(recovered_analysis.get('available', False), "Should continue operation after recovery")


if __name__ == '__main__':
    unittest.main()

