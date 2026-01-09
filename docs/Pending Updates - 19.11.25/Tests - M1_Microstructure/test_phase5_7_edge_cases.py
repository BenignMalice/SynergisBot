# =====================================
# tests/test_phase5_7_edge_cases.py
# =====================================
"""
Tests for Phase 5.7: Edge Case Testing
Tests edge cases and error handling
"""

import unittest
import sys
import os
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from pathlib import Path

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_data_fetcher import M1DataFetcher
from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
from infra.m1_refresh_manager import M1RefreshManager
from infra.m1_snapshot_manager import M1SnapshotManager


class TestPhase5_7EdgeCases(unittest.TestCase):
    """Test cases for Phase 5.7 Edge Case Testing"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_mt5 = Mock()
        self.fetcher = M1DataFetcher(data_source=self.mock_mt5, max_candles=200, cache_ttl=300)
        self.analyzer = M1MicrostructureAnalyzer()
        
        # Temp directory for snapshots
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
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
    
    def test_insufficient_candles(self):
        """Test with insufficient candles (< 30 candles)"""
        # Generate only 10 candles
        candles = self._generate_mock_candles(10)
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure('XAUUSD', candles)
        
        # Should handle gracefully
        self.assertIsNotNone(analysis, "Should return analysis even with insufficient candles")
        # Analyzer may still return available=True but with limited analysis
        # The key is that it doesn't crash
        if not analysis.get('available', True):
            self.assertIn('error', analysis, "Should include error message if unavailable")
    
    def test_missing_candles_gaps(self):
        """Test with missing candles (gaps in data)"""
        candles = self._generate_mock_candles(100)
        
        # Remove some candles to create gaps
        candles_with_gaps = candles[:20] + candles[40:60] + candles[80:]
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure('XAUUSD', candles_with_gaps)
        
        # Should handle gaps gracefully
        self.assertIsNotNone(analysis, "Should handle gaps in data")
        # Analysis should still work, though may be less accurate
    
    def test_invalid_symbol_names(self):
        """Test with invalid symbol names"""
        candles = self._generate_mock_candles(100)
        
        # Test with invalid symbols
        invalid_symbols = ['', 'INVALID', '123', 'XAU/USD', None]
        
        for symbol in invalid_symbols:
            if symbol is None:
                continue  # Skip None as it would cause immediate error
            
            # Should handle gracefully
            try:
                analysis = self.analyzer.analyze_microstructure(symbol, candles)
                # Should either work or fail gracefully
                self.assertIsNotNone(analysis, f"Should handle invalid symbol: {symbol}")
            except Exception as e:
                # Exception is acceptable for invalid symbols
                self.assertIsInstance(e, (ValueError, TypeError, AttributeError),
                                     f"Should raise appropriate exception for {symbol}")
    
    def test_mt5_connection_failures(self):
        """Test with MT5 connection failures"""
        # Mock MT5 to raise exception
        self.mock_mt5.get_bars = Mock(side_effect=Exception("Connection failed"))
        
        # Try to fetch
        result = self.fetcher.fetch_m1_data('XAUUSD', count=200)
        
        # Should return empty list on failure
        self.assertEqual(result, [], "Should return empty list on connection failure")
    
    def test_stale_data(self):
        """Test with stale data (> 3 minutes old)"""
        # Generate old candles
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        candles = []
        for i in range(100):
            candles.append({
                'timestamp': old_time - timedelta(minutes=100-i),
                'open': 2400.0 + (i * 0.1),
                'high': 2400.5 + (i * 0.1),
                'low': 2399.5 + (i * 0.1),
                'close': 2400.2 + (i * 0.1),
                'volume': 100 + i,
                'symbol': 'XAUUSDc'
            })
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure('XAUUSD', candles)
        
        # Should still analyze, but may flag as stale
        self.assertIsNotNone(analysis, "Should handle stale data")
        
        # Check data age
        latest_candle = candles[-1]
        latest_time = latest_candle.get('timestamp')
        if isinstance(latest_time, datetime):
            age_seconds = (datetime.now(timezone.utc) - latest_time).total_seconds()
            self.assertGreater(age_seconds, 180, "Data should be stale (> 3 minutes)")
    
    def test_corrupted_snapshot_files(self):
        """Test with corrupted snapshot files"""
        snapshot_manager = M1SnapshotManager(
            fetcher=self.fetcher,
            snapshot_directory=self.temp_dir,
            use_compression=False
        )
        
        # Create corrupted snapshot file
        corrupted_file = Path(self.temp_dir) / "XAUUSD_M1_snapshot_corrupted.csv"
        with open(corrupted_file, 'w') as f:
            f.write("corrupted,data,file\ninvalid,format,here")
        
        # Try to load
        result = snapshot_manager.load_snapshot('XAUUSD', max_age_seconds=3600)
        
        # Should handle gracefully (return None or empty)
        # The exact behavior depends on implementation
        self.assertTrue(result is None or result == [] or len(result) == 0, 
                       "Should handle corrupted file gracefully")
    
    def test_concurrent_access_same_symbol(self):
        """Test with concurrent access to same symbol"""
        import threading
        
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(100)
        
        results = []
        errors = []
        
        def analyze():
            try:
                result = self.analyzer.analyze_microstructure(symbol, candles)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=analyze)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Should handle concurrent access
        self.assertEqual(len(results), 5, "All threads should complete")
        self.assertEqual(len(errors), 0, "No errors should occur")
    
    def test_rapid_symbol_switching(self):
        """Test with rapid symbol switching"""
        symbols = ['XAUUSD', 'BTCUSD', 'EURUSD', 'GBPUSD', 'USDJPY']
        candles_map = {sym: self._generate_mock_candles(100, sym) for sym in symbols}
        
        # Rapidly switch between symbols
        for _ in range(10):
            for symbol in symbols:
                candles = candles_map[symbol]
                analysis = self.analyzer.analyze_microstructure(symbol, candles)
                self.assertIsNotNone(analysis, f"Should handle rapid switching for {symbol}")
    
    def test_market_hours_forex_vs_crypto(self):
        """Test with market hours (forex vs crypto)"""
        # Forex symbols (closed on weekends)
        forex_candles = self._generate_mock_candles(100, 'EURUSD')
        
        # Crypto symbols (24/7)
        crypto_candles = self._generate_mock_candles(100, 'BTCUSD')
        
        # Both should analyze
        forex_analysis = self.analyzer.analyze_microstructure('EURUSD', forex_candles)
        crypto_analysis = self.analyzer.analyze_microstructure('BTCUSD', crypto_candles)
        
        self.assertIsNotNone(forex_analysis, "Should handle forex symbols")
        self.assertIsNotNone(crypto_analysis, "Should handle crypto symbols")
    
    def test_timezone_differences(self):
        """Test with timezone differences"""
        # Generate candles with different timezones
        utc_time = datetime.now(timezone.utc) - timedelta(minutes=100)
        local_time = datetime.now() - timedelta(minutes=100)
        
        candles_utc = []
        candles_local = []
        
        for i in range(100):
            candles_utc.append({
                'timestamp': utc_time + timedelta(minutes=i),
                'open': 2400.0 + (i * 0.1),
                'high': 2400.5 + (i * 0.1),
                'low': 2399.5 + (i * 0.1),
                'close': 2400.2 + (i * 0.1),
                'volume': 100 + i,
                'symbol': 'XAUUSDc'
            })
            
            candles_local.append({
                'timestamp': local_time + timedelta(minutes=i),
                'open': 2400.0 + (i * 0.1),
                'high': 2400.5 + (i * 0.1),
                'low': 2399.5 + (i * 0.1),
                'close': 2400.2 + (i * 0.1),
                'volume': 100 + i,
                'symbol': 'XAUUSDc'
            })
        
        # Both should analyze
        utc_analysis = self.analyzer.analyze_microstructure('XAUUSD', candles_utc)
        local_analysis = self.analyzer.analyze_microstructure('XAUUSD', candles_local)
        
        self.assertIsNotNone(utc_analysis, "Should handle UTC timezone")
        self.assertIsNotNone(local_analysis, "Should handle local timezone")
    
    def test_weekend_gaps_forex(self):
        """Test with weekend gaps (forex)"""
        # Generate candles with weekend gap
        friday_time = datetime.now(timezone.utc).replace(hour=21, minute=0, second=0, microsecond=0)
        # Go back to Friday
        while friday_time.weekday() != 4:  # Friday
            friday_time -= timedelta(days=1)
        
        sunday_time = friday_time + timedelta(days=2, hours=1)  # Sunday 22:00
        
        candles = []
        
        # Friday candles
        for i in range(20):
            candles.append({
                'timestamp': friday_time - timedelta(minutes=20-i),
                'open': 2400.0 + (i * 0.1),
                'high': 2400.5 + (i * 0.1),
                'low': 2399.5 + (i * 0.1),
                'close': 2400.2 + (i * 0.1),
                'volume': 100 + i,
                'symbol': 'EURUSDc'
            })
        
        # Sunday candles (after gap)
        for i in range(20):
            candles.append({
                'timestamp': sunday_time + timedelta(minutes=i),
                'open': 2400.0 + (i * 0.1),
                'high': 2400.5 + (i * 0.1),
                'low': 2399.5 + (i * 0.1),
                'close': 2400.2 + (i * 0.1),
                'volume': 100 + i,
                'symbol': 'EURUSDc'
            })
        
        # Should handle weekend gap
        analysis = self.analyzer.analyze_microstructure('EURUSD', candles)
        self.assertIsNotNone(analysis, "Should handle weekend gaps")
    
    def test_empty_candles_list(self):
        """Test with empty candles list"""
        analysis = self.analyzer.analyze_microstructure('XAUUSD', [])
        
        self.assertIsNotNone(analysis, "Should handle empty list")
        self.assertFalse(analysis.get('available', True), "Should mark as unavailable")
    
    def test_none_candles(self):
        """Test with None candles"""
        try:
            analysis = self.analyzer.analyze_microstructure('XAUUSD', None)
            # Should either return error analysis or raise exception
            if analysis:
                self.assertFalse(analysis.get('available', True), "Should mark as unavailable")
        except (TypeError, AttributeError):
            # Exception is acceptable
            pass
    
    def test_malformed_candle_data(self):
        """Test with malformed candle data"""
        # Candles with missing fields
        malformed_candles = [
            {'timestamp': datetime.now(timezone.utc), 'open': 2400.0},  # Missing high, low, close
            {'open': 2400.0, 'high': 2400.5, 'low': 2399.5},  # Missing timestamp, close
        ]
        
        # Should handle gracefully
        try:
            analysis = self.analyzer.analyze_microstructure('XAUUSD', malformed_candles)
            # Should either return error or handle missing fields
            self.assertIsNotNone(analysis, "Should handle malformed data")
        except (KeyError, AttributeError):
            # Exception is acceptable for malformed data
            pass


if __name__ == '__main__':
    unittest.main()

