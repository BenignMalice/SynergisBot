# =====================================
# tests/test_phase4_1_monitoring.py
# =====================================
"""
Tests for Phase 4.1: Resource Monitoring
Tests M1Monitoring metrics tracking and reporting
"""

import unittest
import sys
import os
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_monitoring import M1Monitoring


class TestPhase4_1Monitoring(unittest.TestCase):
    """Test cases for Phase 4.1 Resource Monitoring"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.monitoring = M1Monitoring(max_history=50)
    
    def test_record_refresh_success(self):
        """Test recording successful refresh"""
        symbol = "XAUUSD"
        
        self.monitoring.record_refresh(
            symbol=symbol,
            success=True,
            latency_ms=25.5,
            data_age_seconds=30.0,
            expected_age_seconds=30.0
        )
        
        metrics = self.monitoring.get_refresh_metrics(symbol)
        
        self.assertEqual(metrics['total_refreshes'], 1)
        self.assertEqual(metrics['avg_latency_ms'], 25.5)
        self.assertEqual(metrics['success_rate'], 100.0)
        self.assertEqual(metrics['avg_data_age_seconds'], 30.0)
        self.assertEqual(metrics['avg_drift_seconds'], 0.0)
    
    def test_record_refresh_failure(self):
        """Test recording failed refresh"""
        symbol = "BTCUSD"
        
        self.monitoring.record_refresh(
            symbol=symbol,
            success=False,
            latency_ms=100.0,
            data_age_seconds=None,
            expected_age_seconds=None
        )
        
        metrics = self.monitoring.get_refresh_metrics(symbol)
        
        self.assertEqual(metrics['total_refreshes'], 1)
        self.assertEqual(metrics['avg_latency_ms'], 100.0)
        self.assertEqual(metrics['success_rate'], 0.0)
        self.assertIsNone(metrics['avg_data_age_seconds'])
        self.assertIsNone(metrics['avg_drift_seconds'])
    
    def test_record_multiple_refreshes(self):
        """Test recording multiple refreshes"""
        symbol = "EURUSD"
        
        # Record multiple refreshes
        for i in range(10):
            self.monitoring.record_refresh(
                symbol=symbol,
                success=(i % 2 == 0),  # Alternate success/failure
                latency_ms=20.0 + i * 5.0,
                data_age_seconds=30.0 + i,
                expected_age_seconds=30.0
            )
        
        metrics = self.monitoring.get_refresh_metrics(symbol)
        
        self.assertEqual(metrics['total_refreshes'], 10)
        self.assertEqual(metrics['success_rate'], 50.0)  # 5 successes out of 10
        self.assertGreater(metrics['avg_latency_ms'], 20.0)
        self.assertLess(metrics['avg_latency_ms'], 70.0)
    
    def test_data_age_drift_calculation(self):
        """Test data age drift calculation"""
        symbol = "XAUUSD"
        
        # Record refresh with drift
        self.monitoring.record_refresh(
            symbol=symbol,
            success=True,
            latency_ms=25.0,
            data_age_seconds=45.0,  # 15 seconds older than expected
            expected_age_seconds=30.0
        )
        
        metrics = self.monitoring.get_refresh_metrics(symbol)
        
        self.assertEqual(metrics['avg_drift_seconds'], 15.0)
    
    def test_get_all_refresh_metrics(self):
        """Test getting metrics for all symbols"""
        symbols = ["XAUUSD", "BTCUSD", "EURUSD"]
        
        for symbol in symbols:
            self.monitoring.record_refresh(
                symbol=symbol,
                success=True,
                latency_ms=25.0,
                data_age_seconds=30.0,
                expected_age_seconds=30.0
            )
        
        all_metrics = self.monitoring.get_all_refresh_metrics()
        
        self.assertEqual(len(all_metrics), 3)
        for symbol in symbols:
            self.assertIn(symbol, all_metrics)
            self.assertEqual(all_metrics[symbol]['total_refreshes'], 1)
    
    def test_get_resource_usage(self):
        """Test getting resource usage"""
        # Update resource usage
        self.monitoring.update_resource_usage()
        
        resource_usage = self.monitoring.get_resource_usage()
        
        self.assertIn('cpu_percent', resource_usage)
        self.assertIn('memory_mb', resource_usage)
        
        # Verify CPU metrics
        cpu = resource_usage['cpu_percent']
        self.assertIn('current', cpu)
        self.assertIn('avg', cpu)
        self.assertIn('max', cpu)
        self.assertIn('min', cpu)
        self.assertGreaterEqual(cpu['current'], 0)
        
        # Verify memory metrics
        memory = resource_usage['memory_mb']
        self.assertIn('current', memory)
        self.assertIn('avg', memory)
        self.assertIn('max', memory)
        self.assertIn('min', memory)
        # Note: If psutil not available, memory will be 0, which is acceptable
        self.assertGreaterEqual(memory['current'], 0)
    
    def test_record_snapshot(self):
        """Test recording snapshot creation time"""
        symbol = "XAUUSD"
        
        self.monitoring.record_snapshot(symbol, snapshot_time_ms=150.5)
        
        metrics = self.monitoring.get_snapshot_metrics(symbol)
        
        self.assertEqual(metrics['total_snapshots'], 1)
        self.assertEqual(metrics['avg_time_ms'], 150.5)
        self.assertEqual(metrics['min_time_ms'], 150.5)
        self.assertEqual(metrics['max_time_ms'], 150.5)
    
    def test_get_snapshot_metrics_no_snapshots(self):
        """Test getting snapshot metrics when no snapshots exist"""
        symbol = "NONEXISTENT"
        
        metrics = self.monitoring.get_snapshot_metrics(symbol)
        
        self.assertEqual(metrics['total_snapshots'], 0)
        self.assertIsNone(metrics['avg_time_ms'])
        self.assertIsNone(metrics['min_time_ms'])
        self.assertIsNone(metrics['max_time_ms'])
    
    def test_get_refresh_diagnostics(self):
        """Test getting refresh diagnostics"""
        symbol = "XAUUSD"
        
        # Record multiple refreshes
        for i in range(5):
            self.monitoring.record_refresh(
                symbol=symbol,
                success=True,
                latency_ms=20.0 + i * 5.0,
                data_age_seconds=30.0 + i,
                expected_age_seconds=30.0
            )
        
        diagnostics = self.monitoring.get_refresh_diagnostics(symbol, limit=3)
        
        self.assertEqual(len(diagnostics), 3)  # Should return last 3
        
        # Verify diagnostic structure
        for diag in diagnostics:
            self.assertIn('timestamp', diag)
            self.assertIn('symbol', diag)
            self.assertIn('success', diag)
            self.assertIn('latency_ms', diag)
            self.assertIn('data_age_seconds', diag)
            self.assertIn('expected_age_seconds', diag)
            self.assertIn('drift_seconds', diag)
    
    def test_get_summary(self):
        """Test getting comprehensive summary"""
        # Record some metrics
        self.monitoring.record_refresh("XAUUSD", True, 25.0, 30.0, 30.0)
        self.monitoring.update_resource_usage()
        
        summary = self.monitoring.get_summary()
        
        self.assertIn('resource_usage', summary)
        self.assertIn('refresh_metrics', summary)
        self.assertIn('timestamp', summary)
        
        # Verify structure
        self.assertIn('cpu_percent', summary['resource_usage'])
        self.assertIn('memory_mb', summary['resource_usage'])
        self.assertIn('XAUUSD', summary['refresh_metrics'])
    
    def test_log_summary(self):
        """Test logging summary (should not raise exception)"""
        # Record some metrics
        self.monitoring.record_refresh("XAUUSD", True, 25.0, 30.0, 30.0)
        self.monitoring.update_resource_usage()
        
        # Should not raise exception
        try:
            self.monitoring.log_summary()
        except Exception as e:
            self.fail(f"log_summary raised exception: {e}")
    
    def test_reset_single_symbol(self):
        """Test resetting metrics for a single symbol"""
        symbol = "XAUUSD"
        
        # Record some metrics
        self.monitoring.record_refresh(symbol, True, 25.0, 30.0, 30.0)
        self.monitoring.record_snapshot(symbol, 150.0)
        
        # Verify metrics exist
        metrics = self.monitoring.get_refresh_metrics(symbol)
        self.assertEqual(metrics['total_refreshes'], 1)
        
        # Reset
        self.monitoring.reset(symbol)
        
        # Verify metrics cleared
        metrics_after = self.monitoring.get_refresh_metrics(symbol)
        self.assertEqual(metrics_after['total_refreshes'], 0)
    
    def test_reset_all(self):
        """Test resetting all metrics"""
        symbols = ["XAUUSD", "BTCUSD"]
        
        # Record metrics for multiple symbols
        for symbol in symbols:
            self.monitoring.record_refresh(symbol, True, 25.0, 30.0, 30.0)
        
        # Verify metrics exist
        all_metrics = self.monitoring.get_all_refresh_metrics()
        self.assertEqual(len(all_metrics), 2)
        
        # Reset all
        self.monitoring.reset()
        
        # Verify all metrics cleared
        all_metrics_after = self.monitoring.get_all_refresh_metrics()
        self.assertEqual(len(all_metrics_after), 0)
    
    def test_max_history_limit(self):
        """Test that max_history limit is respected"""
        symbol = "XAUUSD"
        max_history = 10
        
        monitoring = M1Monitoring(max_history=max_history)
        
        # Record more than max_history refreshes
        for i in range(max_history + 5):
            monitoring.record_refresh(symbol, True, 25.0, 30.0, 30.0)
        
        metrics = monitoring.get_refresh_metrics(symbol)
        
        # Should only keep max_history records
        self.assertLessEqual(metrics['total_refreshes'], max_history)
    
    def test_latency_statistics(self):
        """Test latency statistics (min, max, avg)"""
        symbol = "XAUUSD"
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        
        for latency in latencies:
            self.monitoring.record_refresh(symbol, True, latency, 30.0, 30.0)
        
        metrics = self.monitoring.get_refresh_metrics(symbol)
        
        self.assertEqual(metrics['avg_latency_ms'], 30.0)
        self.assertEqual(metrics['min_latency_ms'], 10.0)
        self.assertEqual(metrics['max_latency_ms'], 50.0)
    
    def test_success_rate_calculation(self):
        """Test success rate calculation"""
        symbol = "XAUUSD"
        
        # Record 10 refreshes: 7 success, 3 failure
        for i in range(10):
            success = i < 7
            self.monitoring.record_refresh(symbol, success, 25.0, 30.0, 30.0)
        
        metrics = self.monitoring.get_refresh_metrics(symbol)
        
        self.assertEqual(metrics['success_rate'], 70.0)  # 7/10 = 70%
    
    def test_multiple_snapshots_statistics(self):
        """Test snapshot statistics with multiple snapshots"""
        symbol = "XAUUSD"
        snapshot_times = [100.0, 150.0, 200.0, 120.0, 180.0]
        
        for snapshot_time in snapshot_times:
            self.monitoring.record_snapshot(symbol, snapshot_time)
        
        metrics = self.monitoring.get_snapshot_metrics(symbol)
        
        self.assertEqual(metrics['total_snapshots'], 5)
        self.assertEqual(metrics['avg_time_ms'], 150.0)  # (100+150+200+120+180)/5
        self.assertEqual(metrics['min_time_ms'], 100.0)
        self.assertEqual(metrics['max_time_ms'], 200.0)
    
    def test_refresh_diagnostics_limit(self):
        """Test that refresh diagnostics limit is respected"""
        symbol = "XAUUSD"
        
        # Record more than limit
        for i in range(20):
            self.monitoring.record_refresh(symbol, True, 25.0, 30.0, 30.0)
        
        # Get diagnostics with limit
        diagnostics = self.monitoring.get_refresh_diagnostics(symbol, limit=5)
        
        self.assertLessEqual(len(diagnostics), 5)
    
    def test_empty_metrics_handling(self):
        """Test handling of empty metrics"""
        symbol = "NONEXISTENT"
        
        metrics = self.monitoring.get_refresh_metrics(symbol)
        
        self.assertEqual(metrics['total_refreshes'], 0)
        self.assertEqual(metrics['avg_latency_ms'], 0)
        self.assertEqual(metrics['success_rate'], 0)
        self.assertIsNone(metrics['avg_data_age_seconds'])
        self.assertIsNone(metrics['last_refresh'])


if __name__ == '__main__':
    unittest.main()

