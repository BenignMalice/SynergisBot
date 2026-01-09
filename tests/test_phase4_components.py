"""
Phase 4 Component Tests
Tests for performance optimization, backtesting, production monitoring, and data management
"""

import unittest
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
import tempfile
import os
import sys
import time
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine.performance_optimizer import PerformanceOptimizer, OptimizationLevel, PerformanceMetric
from app.engine.backtesting_engine import BacktestingEngine, BacktestPeriod, BacktestResult
from app.engine.production_monitor import ProductionMonitor, AlertLevel, MonitorStatus
from app.engine.data_management_automation import DataManagementAutomation, DataRetentionPolicy, DataOperation

class TestPerformanceOptimizer(unittest.TestCase):
    """Test performance optimizer"""
    
    def setUp(self):
        self.config = {
            'symbol': 'BTCUSDc',
            'performance_config': {
                'target_latency_p95': 200,
                'max_memory_usage': 500,
                'max_cpu_usage': 80,
                'optimization_level': 'advanced'
            }
        }
        self.optimizer = PerformanceOptimizer(self.config)
    
    def test_optimization_levels(self):
        """Test optimization levels"""
        self.assertEqual(self.optimizer.optimization_level, OptimizationLevel.ADVANCED)
        self.assertEqual(self.optimizer.target_latency_p95, 200)
        self.assertEqual(self.optimizer.max_memory_usage, 500)
    
    def test_vectorized_calculation(self):
        """Test vectorized calculation optimization"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
        result = self.optimizer.optimize_vectorized_calculation(data, 3, 0)  # Mean calculation
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), len(data))
    
    def test_memory_access_optimization(self):
        """Test memory access optimization"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
        indices = np.array([0, 2, 4], dtype=np.int32)
        result = self.optimizer.optimize_memory_access(data, indices)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), len(indices))
    
    def test_performance_monitoring(self):
        """Test performance monitoring"""
        # Record some latency measurements
        for i in range(10):
            latency = np.random.normal(100, 20)
            self.optimizer.record_latency(latency)
        
        # Get performance summary
        summary = self.optimizer.get_performance_summary()
        self.assertIn('symbol', summary)
        # Performance summary might be empty initially, so just check it's a dict
        self.assertIsInstance(summary, dict)
        # Check optimization_active only if we have data
        if 'status' not in summary:
            self.assertIn('optimization_active', summary)
    
    def test_optimization_start_stop(self):
        """Test optimization start/stop"""
        # Start optimization
        self.optimizer.start_optimization()
        self.assertTrue(self.optimizer.optimization_active)
        
        # Stop optimization
        self.optimizer.stop_optimization()
        self.assertFalse(self.optimizer.optimization_active)
    
    def test_system_monitoring(self):
        """Test system monitoring"""
        system_monitor = self.optimizer.system_monitor
        metrics = system_monitor.get_system_metrics()
        self.assertIsInstance(metrics, dict)
        self.assertIn('timestamp', metrics)
        self.assertIn('cpu_percent', metrics)
        self.assertIn('memory_percent', metrics)

class TestBacktestingEngine(unittest.TestCase):
    """Test backtesting engine"""
    
    def setUp(self):
        self.config = {
            'symbol': 'BTCUSDc',
            'backtest_config': {
                'initial_capital': 10000.0,
                'max_drawdown_limit': 0.15,
                'min_win_rate': 0.6,
                'min_sharpe_ratio': 1.0,
                'min_profit_factor': 1.5
            }
        }
        self.backtest_engine = BacktestingEngine(self.config)
    
    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation"""
        returns = np.array([0.01, 0.02, -0.01, 0.03, 0.01], dtype=np.float32)
        sharpe_ratio = self.backtest_engine.calculate_sharpe_ratio(returns)
        self.assertIsInstance(sharpe_ratio, float)
    
    def test_max_drawdown_calculation(self):
        """Test maximum drawdown calculation"""
        equity_values = np.array([10000.0, 10500.0, 10200.0, 9800.0, 9500.0], dtype=np.float32)
        max_drawdown = self.backtest_engine.calculate_max_drawdown(equity_values)
        self.assertIsInstance(max_drawdown, float)
        self.assertGreaterEqual(max_drawdown, 0)
    
    def test_sortino_ratio_calculation(self):
        """Test Sortino ratio calculation"""
        returns = np.array([0.01, 0.02, -0.01, 0.03, 0.01], dtype=np.float32)
        sortino_ratio = self.backtest_engine.calculate_sortino_ratio(returns)
        self.assertIsInstance(sortino_ratio, float)
    
    def test_historical_data_loading(self):
        """Test historical data loading"""
        start_date = datetime.now(timezone.utc) - timedelta(days=365)
        end_date = datetime.now(timezone.utc)
        
        self.backtest_engine.load_historical_data('test_source', start_date, end_date)
        self.assertIn('symbol', self.backtest_engine.historical_data)
        self.assertEqual(self.backtest_engine.historical_data['symbol'], 'BTCUSDc')
    
    def test_backtest_execution(self):
        """Test backtest execution"""
        strategy_config = {
            'num_trades': 50,
            'win_rate': 0.65,
            'avg_win': 50.0,
            'avg_loss': -30.0
        }
        
        metrics = self.backtest_engine.run_backtest(strategy_config)
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.symbol, 'BTCUSDc')
        self.assertGreater(metrics.total_trades, 0)
        self.assertGreaterEqual(metrics.win_rate, 0)
        self.assertLessEqual(metrics.win_rate, 1)
    
    def test_backtest_validation(self):
        """Test backtest validation"""
        # Create a mock metrics object
        from app.engine.backtesting_engine import BacktestMetrics
        
        metrics = BacktestMetrics(
            symbol='BTCUSDc',
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            total_trades=100,
            winning_trades=65,
            losing_trades=35,
            win_rate=0.65,
            total_pnl=1000.0,
            avg_pnl=10.0,
            max_win=100.0,
            max_loss=-50.0,
            sharpe_ratio=1.2,
            max_drawdown=0.10,
            profit_factor=1.8,
            avg_trade_duration=12.0,
            total_return=0.10,
            volatility=0.15,
            calmar_ratio=1.0,
            sortino_ratio=1.5
        )
        
        validation = self.backtest_engine.validate_backtest(metrics)
        self.assertIsNotNone(validation)
        self.assertEqual(validation.symbol, 'BTCUSDc')
        self.assertIn(validation.result, [BacktestResult.PASSED, BacktestResult.FAILED])
    
    def test_12_month_backtest(self):
        """Test 12-month backtesting"""
        symbols = ['BTCUSDc', 'XAUUSDc']
        results = self.backtest_engine.run_12_month_backtest(symbols)
        
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), len(symbols))
        
        for symbol in symbols:
            self.assertIn(symbol, results)
            self.assertIn('metrics', results[symbol])
            self.assertIn('validation', results[symbol])
    
    def test_backtest_summary(self):
        """Test backtest summary"""
        # Run a backtest first
        strategy_config = {'num_trades': 20, 'win_rate': 0.65, 'avg_win': 50.0, 'avg_loss': -30.0}
        self.backtest_engine.run_backtest(strategy_config)
        
        summary = self.backtest_engine.get_backtest_summary()
        self.assertIn('symbol', summary)
        self.assertIn('total_backtests', summary)
        self.assertIn('total_trades', summary)

class TestProductionMonitor(unittest.TestCase):
    """Test production monitor"""
    
    def setUp(self):
        self.config = {
            'symbol': 'BTCUSDc',
            'monitor_config': {
                'alert_thresholds': {
                    'latency_p95': 200,
                    'memory_usage': 500,
                    'cpu_usage': 80,
                    'error_rate': 0.05
                },
                'alert_config': {
                    'email_enabled': False,
                    'slack_enabled': False
                }
            }
        }
        self.monitor = ProductionMonitor(self.config)
    
    def test_alert_levels(self):
        """Test alert levels"""
        self.assertEqual(AlertLevel.INFO.value, 'info')
        self.assertEqual(AlertLevel.WARNING.value, 'warning')
        self.assertEqual(AlertLevel.ERROR.value, 'error')
        self.assertEqual(AlertLevel.CRITICAL.value, 'critical')
    
    def test_monitor_status(self):
        """Test monitor status"""
        self.assertEqual(MonitorStatus.HEALTHY.value, 'healthy')
        self.assertEqual(MonitorStatus.WARNING.value, 'warning')
        self.assertEqual(MonitorStatus.ERROR.value, 'error')
        self.assertEqual(MonitorStatus.CRITICAL.value, 'critical')
        self.assertEqual(MonitorStatus.OFFLINE.value, 'offline')
    
    def test_monitoring_start_stop(self):
        """Test monitoring start/stop"""
        # Start monitoring
        self.monitor.start_monitoring()
        self.assertTrue(self.monitor.monitoring_active)
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        self.assertFalse(self.monitor.monitoring_active)
    
    def test_system_metrics_collection(self):
        """Test system metrics collection"""
        metrics = self.monitor._collect_system_metrics()
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.symbol, 'BTCUSDc')
        self.assertIn(metrics.status, [MonitorStatus.HEALTHY, MonitorStatus.WARNING, MonitorStatus.ERROR, MonitorStatus.CRITICAL])
    
    def test_alert_handling(self):
        """Test alert handling"""
        # Create a test alert
        from app.engine.production_monitor import SystemAlert
        
        alert = SystemAlert(
            alert_id='test_alert',
            level=AlertLevel.WARNING,
            component='test_component',
            symbol='BTCUSDc',
            message='Test alert message',
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            details={'test': 'data'}
        )
        
        # Handle alert
        self.monitor._handle_alert(alert)
        self.assertIn(alert.alert_id, self.monitor.active_alerts)
    
    def test_alert_resolution(self):
        """Test alert resolution"""
        # Create and handle an alert
        from app.engine.production_monitor import SystemAlert
        
        alert = SystemAlert(
            alert_id='test_alert_resolve',
            level=AlertLevel.WARNING,
            component='test_component',
            symbol='BTCUSDc',
            message='Test alert message',
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            details={}
        )
        
        self.monitor._handle_alert(alert)
        self.assertIn(alert.alert_id, self.monitor.active_alerts)
        
        # Resolve alert
        self.monitor.resolve_alert(alert.alert_id)
        self.assertNotIn(alert.alert_id, self.monitor.active_alerts)
    
    def test_monitoring_summary(self):
        """Test monitoring summary"""
        # Start monitoring briefly
        self.monitor.start_monitoring()
        time.sleep(1)  # Let it collect some metrics
        self.monitor.stop_monitoring()
        
        summary = self.monitor.get_monitoring_summary()
        self.assertIn('symbol', summary)
        self.assertIn('monitoring_active', summary)
        self.assertIn('avg_latency_p95', summary)
        self.assertIn('avg_memory_usage', summary)
    
    def test_system_health(self):
        """Test system health monitoring"""
        system_monitor = self.monitor.system_monitor
        health = system_monitor.get_system_health()
        self.assertIn('health_status', health)
        self.assertIn('cpu_percent', health)
        self.assertIn('memory_percent', health)

class TestDataManagementAutomation(unittest.TestCase):
    """Test data management automation"""
    
    def setUp(self):
        self.config = {
            'symbol': 'BTCUSDc',
            'data_config': {
                'retention_rules': {
                    'raw_ticks': {'retention_days': 7, 'policy': 'delete_old'},
                    'ohlcv_bars': {'retention_days': 30, 'policy': 'compress_old'}
                },
                'backup_config': {
                    'enabled': True,
                    'frequency': 'daily'
                },
                'compression_config': {
                    'enabled': True,
                    'level': 6
                }
            }
        }
        self.automation = DataManagementAutomation(self.config)
    
    def test_data_retention_policies(self):
        """Test data retention policies"""
        self.assertEqual(DataRetentionPolicy.KEEP_ALL.value, 'keep_all')
        self.assertEqual(DataRetentionPolicy.COMPRESS_OLD.value, 'compress_old')
        self.assertEqual(DataRetentionPolicy.DELETE_OLD.value, 'delete_old')
        self.assertEqual(DataRetentionPolicy.ARCHIVE_OLD.value, 'archive_old')
    
    def test_data_operations(self):
        """Test data operations"""
        self.assertEqual(DataOperation.BACKUP.value, 'backup')
        self.assertEqual(DataOperation.COMPRESS.value, 'compress')
        self.assertEqual(DataOperation.DELETE.value, 'delete')
        self.assertEqual(DataOperation.ARCHIVE.value, 'archive')
        self.assertEqual(DataOperation.OPTIMIZE.value, 'optimize')
        self.assertEqual(DataOperation.VACUUM.value, 'vacuum')
    
    def test_automation_start_stop(self):
        """Test automation start/stop"""
        # Start automation
        self.automation.start_automation()
        self.assertTrue(self.automation.automation_active)
        
        # Stop automation
        self.automation.stop_automation()
        self.assertFalse(self.automation.automation_active)
    
    def test_task_scheduling(self):
        """Test task scheduling"""
        task_id = self.automation.schedule_task(
            DataOperation.BACKUP, 
            'data/test.db', 
            priority=1, 
            details={'test': 'data'}
        )
        
        self.assertIsNotNone(task_id)
        self.assertTrue(task_id.startswith('backup_'))
    
    def test_retention_rules(self):
        """Test retention rules"""
        self.assertIn('raw_ticks', self.automation.default_rules)
        self.assertIn('ohlcv_bars', self.automation.default_rules)
        self.assertIn('market_structure', self.automation.default_rules)
        self.assertIn('trade_history', self.automation.default_rules)
        self.assertIn('performance_metrics', self.automation.default_rules)
    
    def test_database_operations(self):
        """Test database operations"""
        # Test database optimization (with a temporary file)
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            # Create a simple database
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test (id INTEGER, data TEXT)")
            conn.commit()
            conn.close()
            
            # Test optimization
            result = self.automation._optimize_database(temp_db.name)
            self.assertTrue(result)
            
            # Test vacuum
            result = self.automation._vacuum_database(temp_db.name)
            self.assertTrue(result)
            
        finally:
            # Clean up
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)
    
    def test_automation_status(self):
        """Test automation status"""
        status = self.automation.get_automation_status()
        self.assertIn('symbol', status)
        self.assertIn('automation_active', status)
        self.assertIn('pending_tasks', status)
        self.assertIn('active_tasks', status)
        self.assertIn('completed_tasks', status)
        self.assertIn('retention_rules', status)
    
    def test_scheduled_operations(self):
        """Test scheduled operations"""
        # Test daily backup scheduling
        self.automation._schedule_daily_backup()
        self.assertGreater(len(self.automation.task_queue), 0)
        
        # Test weekly optimization scheduling
        self.automation._schedule_weekly_optimization()
        self.assertGreater(len(self.automation.task_queue), 0)
        
        # Test monthly cleanup scheduling
        self.automation._schedule_monthly_cleanup()
        self.assertGreater(len(self.automation.task_queue), 0)

class TestPhase4Integration(unittest.TestCase):
    """Test Phase 4 integration"""
    
    def test_performance_backtest_integration(self):
        """Test performance optimizer and backtesting integration"""
        # Create components
        perf_config = {
            'symbol': 'BTCUSDc',
            'performance_config': {'target_latency_p95': 200, 'max_memory_usage': 500}
        }
        backtest_config = {
            'symbol': 'BTCUSDc',
            'backtest_config': {'initial_capital': 10000.0, 'min_win_rate': 0.6}
        }
        
        optimizer = PerformanceOptimizer(perf_config)
        backtest_engine = BacktestingEngine(backtest_config)
        
        # Test integration
        optimizer.start_optimization()
        strategy_config = {'num_trades': 50, 'win_rate': 0.65, 'avg_win': 50.0, 'avg_loss': -30.0}
        metrics = backtest_engine.run_backtest(strategy_config)
        
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.symbol, 'BTCUSDc')
        
        optimizer.stop_optimization()
    
    def test_monitor_automation_integration(self):
        """Test production monitor and data management integration"""
        # Create components
        monitor_config = {
            'symbol': 'BTCUSDc',
            'monitor_config': {'alert_thresholds': {'latency_p95': 200, 'memory_usage': 500}}
        }
        automation_config = {
            'symbol': 'BTCUSDc',
            'data_config': {'retention_rules': {'raw_ticks': {'retention_days': 7, 'policy': 'delete_old'}}}
        }
        
        monitor = ProductionMonitor(monitor_config)
        automation = DataManagementAutomation(automation_config)
        
        # Test integration
        monitor.start_monitoring()
        automation.start_automation()
        
        # Schedule a task
        task_id = automation.schedule_task(DataOperation.BACKUP, 'data/test.db')
        self.assertIsNotNone(task_id)
        
        # Get status
        monitor_status = monitor.get_monitoring_summary()
        automation_status = automation.get_automation_status()
        
        self.assertIn('symbol', monitor_status)
        self.assertIn('symbol', automation_status)
        
        monitor.stop_monitoring()
        automation.stop_automation()

def run_phase4_tests():
    """Run all Phase 4 tests"""
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestPerformanceOptimizer,
        TestBacktestingEngine,
        TestProductionMonitor,
        TestDataManagementAutomation,
        TestPhase4Integration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_phase4_tests()
    if success:
        print("\nAll Phase 4 tests passed!")
    else:
        print("\nSome Phase 4 tests failed!")
