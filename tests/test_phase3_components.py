"""
Phase 3 Component Tests
Tests for DTMS integration, dynamic stops, partial scaling, circuit breakers, and trade management
"""

import unittest
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
import tempfile
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine.multi_timeframe_exit_engine import MultiTimeframeExitEngine, ExitType, ExitPriority
from app.engine.dynamic_stop_manager import DynamicStopManager, StopType, StopStatus
from app.engine.partial_scaling_manager import PartialScalingManager, ScalingType, ScalingAction
from app.engine.circuit_breaker_system import CircuitBreakerSystem, BreakerType, BreakerStatus
from app.database.trade_management_db import TradeManagementDB
from app.engine.historical_analysis_engine import HistoricalAnalysisEngine, AnalysisType, AnalysisPeriod

class TestMultiTimeframeExitEngine(unittest.TestCase):
    """Test multi-timeframe exit engine"""
    
    def setUp(self):
        self.config = {
            'symbol': 'EURJPYc',
            'exit_thresholds': {
                'structure_break': 0.7,
                'momentum_loss': 0.6,
                'volume_decline': 0.5
            },
            'max_hold_time_hours': 24,
            'profit_target_ratio': 2.0
        }
        self.exit_engine = MultiTimeframeExitEngine(self.config)
    
    def test_momentum_score_calculation(self):
        """Test momentum score calculation"""
        prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0], dtype=np.float32)
        volumes = np.array([100.0, 120.0, 110.0, 130.0, 140.0], dtype=np.float32)
        
        momentum_score = self.exit_engine.calculate_momentum_score(prices, volumes, 5)
        self.assertIsInstance(momentum_score, float)
    
    def test_structure_break_detection(self):
        """Test structure break detection"""
        highs = np.array([100.0, 101.0, 102.0, 103.0, 104.0], dtype=np.float32)
        lows = np.array([99.0, 100.0, 101.0, 102.0, 103.0], dtype=np.float32)
        closes = np.array([99.5, 100.5, 101.5, 102.5, 103.5], dtype=np.float32)
        current_price = 105.0
        
        structure_broken, break_strength = self.exit_engine.detect_structure_break(
            highs, lows, closes, current_price, 5
        )
        
        self.assertTrue(structure_broken)
        self.assertGreater(break_strength, 0)
    
    def test_multi_timeframe_exit_analysis(self):
        """Test multi-timeframe exit analysis"""
        market_data = {
            'H1': {
                'ohlcv': {
                    'high': [150.0, 151.0, 152.0, 153.0, 154.0],
                    'low': [149.0, 150.0, 151.0, 152.0, 153.0],
                    'close': [149.5, 150.5, 151.5, 152.5, 153.5],
                    'volume': [1000, 1200, 1100, 1300, 1400]
                }
            }
        }
        
        current_trade = {
            'entry_price': 150.0,
            'entry_time': datetime.now(timezone.utc).timestamp() - 3600,
            'direction': 'BUY'
        }
        
        exit_signals = self.exit_engine.analyze_multi_timeframe_exits(market_data, current_trade)
        self.assertIsInstance(exit_signals, list)
    
    def test_exit_signal_prioritization(self):
        """Test exit signal prioritization"""
        # Create mock signals
        signals = []
        
        # Test prioritization
        prioritized = self.exit_engine._prioritize_exit_signals(signals)
        self.assertIsInstance(prioritized, list)
    
    def test_exit_recommendation(self):
        """Test exit recommendation"""
        signals = []
        recommendation = self.exit_engine.get_exit_recommendation(signals)
        self.assertIsNone(recommendation)  # Empty signals should return None
    
    def test_exit_statistics(self):
        """Test exit statistics"""
        stats = self.exit_engine.get_exit_statistics()
        self.assertIsInstance(stats, dict)
        # Statistics will be empty initially, so just check it's a dict
        self.assertIn('symbol', stats)

class TestDynamicStopManager(unittest.TestCase):
    """Test dynamic stop manager"""
    
    def setUp(self):
        self.config = {
            'symbol': 'GBPJPYc',
            'stop_config': {
                'initial_stop_atr_multiplier': 2.0,
                'trailing_stop_atr_multiplier': 1.5,
                'breakeven_threshold': 1.0,
                'max_stop_distance': 0.05
            }
        }
        self.stop_manager = DynamicStopManager(self.config)
    
    def test_atr_stop_calculation(self):
        """Test ATR stop calculation"""
        highs = np.array([100.0, 101.0, 102.0, 103.0, 104.0], dtype=np.float32)
        lows = np.array([99.0, 100.0, 101.0, 102.0, 103.0], dtype=np.float32)
        closes = np.array([99.5, 100.5, 101.5, 102.5, 103.5], dtype=np.float32)
        
        atr_stop = self.stop_manager.calculate_atr_stop(highs, lows, closes, 5, 2.0, 1)
        self.assertIsInstance(atr_stop, float)
    
    def test_structure_stop_calculation(self):
        """Test structure stop calculation"""
        highs = np.array([100.0, 101.0, 102.0, 103.0, 104.0], dtype=np.float32)
        lows = np.array([99.0, 100.0, 101.0, 102.0, 103.0], dtype=np.float32)
        closes = np.array([99.5, 100.5, 101.5, 102.5, 103.5], dtype=np.float32)
        
        structure_stop = self.stop_manager.calculate_structure_stop(highs, lows, closes, 1, 5)
        self.assertIsInstance(structure_stop, float)
    
    def test_initial_stop_creation(self):
        """Test initial stop creation"""
        trade_data = {
            'entry_price': 150.0,
            'direction': 'BUY'
        }
        
        market_data = {
            'ohlcv': {
                'high': [150.0, 151.0, 152.0, 153.0, 154.0],
                'low': [149.0, 150.0, 151.0, 152.0, 153.0],
                'close': [149.5, 150.5, 151.5, 152.5, 153.5]
            }
        }
        
        stop_loss = self.stop_manager.create_initial_stop(trade_data, market_data)
        self.assertIsNotNone(stop_loss)
        self.assertEqual(stop_loss.symbol, 'GBPJPYc')
        self.assertEqual(stop_loss.stop_type, StopType.FIXED)
    
    def test_stop_update(self):
        """Test stop update"""
        # First create a trade
        trade_data = {
            'entry_price': 150.0,
            'direction': 'BUY'
        }
        
        market_data = {
            'ohlcv': {
                'high': [150.0, 151.0, 152.0, 153.0, 154.0],
                'low': [149.0, 150.0, 151.0, 152.0, 153.0],
                'close': [149.5, 150.5, 151.5, 152.5, 153.5]
            }
        }
        
        stop_loss = self.stop_manager.create_initial_stop(trade_data, market_data)
        trade_id = 'test_trade_1'
        self.stop_manager.active_stops[trade_id] = stop_loss
        
        # Update stop
        updated_stop = self.stop_manager.update_stop_loss(trade_id, 152.0, market_data)
        # Updated stop might be None if no changes needed, which is acceptable
        self.assertIsInstance(updated_stop, (type(None), type(self.stop_manager.active_stops[trade_id])))
    
    def test_stop_cancellation(self):
        """Test stop cancellation"""
        # Create a trade first
        trade_data = {
            'entry_price': 150.0,
            'direction': 'BUY'
        }
        
        market_data = {
            'ohlcv': {
                'high': [150.0, 151.0, 152.0, 153.0, 154.0],
                'low': [149.0, 150.0, 151.0, 152.0, 153.0],
                'close': [149.5, 150.5, 151.5, 152.5, 153.5]
            }
        }
        
        stop_loss = self.stop_manager.create_initial_stop(trade_data, market_data)
        trade_id = 'test_trade_1'
        self.stop_manager.active_stops[trade_id] = stop_loss
        
        # Cancel stop
        cancelled_stop = self.stop_manager.cancel_stop(trade_id, "Test cancellation")
        self.assertIsNotNone(cancelled_stop)
        self.assertEqual(cancelled_stop.status, StopStatus.CANCELLED)
    
    def test_stop_statistics(self):
        """Test stop statistics"""
        stats = self.stop_manager.get_stop_statistics()
        self.assertIsInstance(stats, dict)
        # Statistics will be empty initially, so just check it's a dict
        self.assertIn('symbol', stats)

class TestPartialScalingManager(unittest.TestCase):
    """Test partial scaling manager"""
    
    def setUp(self):
        self.config = {
            'symbol': 'EURGBPc',
            'scaling_config': {
                'max_position_size': 1.0,
                'scaling_increment': 0.25,
                'structure_break_threshold': 0.7,
                'momentum_threshold': 0.6,
                'volume_threshold': 1.5
            }
        }
        self.scaling_manager = PartialScalingManager(self.config)
    
    def test_structure_strength_calculation(self):
        """Test structure strength calculation"""
        highs = np.array([100.0, 101.0, 102.0, 103.0, 104.0], dtype=np.float32)
        lows = np.array([99.0, 100.0, 101.0, 102.0, 103.0], dtype=np.float32)
        closes = np.array([99.5, 100.5, 101.5, 102.5, 103.5], dtype=np.float32)
        current_price = 105.0
        
        strength = self.scaling_manager.calculate_structure_strength(
            highs, lows, closes, current_price, 5
        )
        
        self.assertIsInstance(strength, float)
        self.assertGreater(strength, 0)
    
    def test_momentum_score_calculation(self):
        """Test momentum score calculation"""
        prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0], dtype=np.float32)
        volumes = np.array([100.0, 120.0, 110.0, 130.0, 140.0], dtype=np.float32)
        
        momentum_score = self.scaling_manager.calculate_momentum_score(prices, volumes, 5)
        self.assertIsInstance(momentum_score, float)
    
    def test_scaling_opportunities_analysis(self):
        """Test scaling opportunities analysis"""
        market_data = {
            'H1': {
                'ohlcv': {
                    'high': [0.8500, 0.8510, 0.8520, 0.8530, 0.8540],
                    'low': [0.8490, 0.8500, 0.8510, 0.8520, 0.8530],
                    'close': [0.8495, 0.8505, 0.8515, 0.8525, 0.8535],
                    'volume': [1000, 1200, 1100, 1300, 1400]
                }
            }
        }
        
        current_trade = {
            'entry_price': 0.8500,
            'direction': 'BUY',
            'position_size': 0.5
        }
        
        scaling_signals = self.scaling_manager.analyze_scaling_opportunities(market_data, current_trade)
        self.assertIsInstance(scaling_signals, list)
    
    def test_scaling_execution(self):
        """Test scaling execution"""
        # Create a mock scaling signal
        from app.engine.partial_scaling_manager import ScalingSignal
        
        signal = ScalingSignal(
            symbol='EURGBPc',
            scaling_type=ScalingType.STRUCTURE_BREAK,
            action=ScalingAction.ADD_POSITION,
            size_change=0.25,
            price_level=0.8520,
            confidence=0.8,
            reasoning="Test scaling",
            timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
            context={}
        )
        
        current_position = 0.5
        new_position = self.scaling_manager.execute_scaling(signal, current_position)
        
        self.assertEqual(new_position, 0.75)
        self.assertEqual(self.scaling_manager.current_position, 0.75)
    
    def test_scaling_recommendation(self):
        """Test scaling recommendation"""
        signals = []
        recommendation = self.scaling_manager.get_scaling_recommendation(signals)
        self.assertIsNone(recommendation)  # Empty signals should return None
    
    def test_scaling_statistics(self):
        """Test scaling statistics"""
        stats = self.scaling_manager.get_scaling_statistics()
        self.assertIsInstance(stats, dict)
        # Statistics will be empty initially, so just check it's a dict
        self.assertIn('symbol', stats)

class TestCircuitBreakerSystem(unittest.TestCase):
    """Test circuit breaker system"""
    
    def setUp(self):
        self.config = {
            'symbol': 'EURJPYc',
            'breaker_config': {
                'max_drawdown': 0.05,
                'max_loss_limit': 1000.0,
                'max_volatility': 0.02,
                'max_latency_ms': 200,
                'min_data_quality': 0.8,
                'max_system_load': 0.8
            }
        }
        self.breaker_system = CircuitBreakerSystem(self.config)
    
    def test_drawdown_calculation(self):
        """Test drawdown calculation"""
        equity_values = np.array([10000.0, 10500.0, 10200.0, 9800.0, 9500.0], dtype=np.float32)
        
        drawdown = self.breaker_system.calculate_drawdown(equity_values)
        self.assertIsInstance(drawdown, float)
        self.assertGreaterEqual(drawdown, 0)
    
    def test_volatility_calculation(self):
        """Test volatility calculation"""
        prices = np.array([100.0, 101.0, 99.0, 102.0, 98.0], dtype=np.float32)
        
        volatility = self.breaker_system.calculate_volatility(prices, 5)
        self.assertIsInstance(volatility, float)
        self.assertGreaterEqual(volatility, 0)
    
    def test_drawdown_breaker(self):
        """Test drawdown breaker"""
        # Test with high drawdown
        self.breaker_system.performance_metrics['peak_equity'] = 10000.0
        triggered = self.breaker_system.check_drawdown_breaker(9000.0)  # 10% drawdown
        
        self.assertTrue(triggered)
        self.assertTrue(self.breaker_system.is_breaker_open(BreakerType.DRAWDOWN))
    
    def test_loss_limit_breaker(self):
        """Test loss limit breaker"""
        # Test with high loss
        triggered = self.breaker_system.check_loss_limit_breaker(-1200.0)  # -$1200 loss
        
        self.assertTrue(triggered)
        self.assertTrue(self.breaker_system.is_breaker_open(BreakerType.LOSS_LIMIT))
    
    def test_volatility_breaker(self):
        """Test volatility breaker"""
        # Test with high volatility
        price_data = [100.0, 102.0, 98.0, 105.0, 95.0, 110.0, 90.0, 115.0, 85.0, 120.0] * 3
        triggered = self.breaker_system.check_volatility_breaker(price_data)
        
        self.assertTrue(triggered)
        self.assertTrue(self.breaker_system.is_breaker_open(BreakerType.VOLATILITY))
    
    def test_latency_breaker(self):
        """Test latency breaker"""
        # Test with high latency
        triggered = self.breaker_system.check_latency_breaker(250.0)  # 250ms latency
        
        self.assertTrue(triggered)
        self.assertTrue(self.breaker_system.is_breaker_open(BreakerType.LATENCY))
    
    def test_data_quality_breaker(self):
        """Test data quality breaker"""
        # Test with low data quality
        triggered = self.breaker_system.check_data_quality_breaker(0.7)  # 70% quality
        
        self.assertTrue(triggered)
        self.assertTrue(self.breaker_system.is_breaker_open(BreakerType.DATA_QUALITY))
    
    def test_system_overload_breaker(self):
        """Test system overload breaker"""
        # Test with high system load
        triggered = self.breaker_system.check_system_overload_breaker(0.9)  # 90% load
        
        self.assertTrue(triggered)
        self.assertTrue(self.breaker_system.is_breaker_open(BreakerType.SYSTEM_OVERLOAD))
    
    def test_breaker_reset(self):
        """Test breaker reset"""
        # Trigger a breaker first
        self.breaker_system.performance_metrics['peak_equity'] = 10000.0
        self.breaker_system.check_drawdown_breaker(9000.0)
        self.assertTrue(self.breaker_system.is_breaker_open(BreakerType.DRAWDOWN))
        
        # Reset breaker
        self.breaker_system.reset_breaker(BreakerType.DRAWDOWN, "Test reset")
        self.assertFalse(self.breaker_system.is_breaker_open(BreakerType.DRAWDOWN))
    
    def test_breaker_status(self):
        """Test breaker status"""
        status = self.breaker_system.get_breaker_status()
        self.assertIsInstance(status, dict)
        self.assertIn('drawdown', status)
        self.assertIn('loss_limit', status)
    
    def test_breaker_statistics(self):
        """Test breaker statistics"""
        stats = self.breaker_system.get_breaker_statistics()
        self.assertIn('total_events', stats)
        self.assertIn('open_breakers', stats)
        self.assertIn('symbol', stats)
    
    def test_trade_result_update(self):
        """Test trade result update"""
        self.breaker_system.update_trade_result(100.0, 'win')
        self.breaker_system.update_trade_result(-50.0, 'loss')
        
        self.assertEqual(self.breaker_system.performance_metrics['total_trades'], 2)
        self.assertEqual(self.breaker_system.performance_metrics['winning_trades'], 1)
        self.assertEqual(self.breaker_system.performance_metrics['losing_trades'], 1)

class TestTradeManagementDB(unittest.TestCase):
    """Test trade management database"""
    
    def setUp(self):
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.db_manager = TradeManagementDB(self.temp_db.name)
    
    def tearDown(self):
        # Clean up temporary database
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_database_initialization(self):
        """Test database initialization"""
        self.assertTrue(os.path.exists(self.temp_db.name))
    
    def test_trade_creation(self):
        """Test trade creation"""
        trade_data = {
            'symbol': 'EURJPYc',
            'direction': 'BUY',
            'entry_price': 150.0,
            'position_size': 0.5,
            'entry_time': int(datetime.now(timezone.utc).timestamp() * 1000),
            'stop_loss': 149.0,
            'take_profit': 151.0,
            'context': {'strategy': 'multi_timeframe'}
        }
        
        trade_id = self.db_manager.create_trade(trade_data)
        self.assertIsNotNone(trade_id)
        self.assertIsInstance(trade_id, str)
    
    def test_trade_update(self):
        """Test trade update"""
        # Create a trade first
        trade_data = {
            'symbol': 'EURJPYc',
            'direction': 'BUY',
            'entry_price': 150.0,
            'position_size': 0.5,
            'entry_time': int(datetime.now(timezone.utc).timestamp() * 1000)
        }
        
        trade_id = self.db_manager.create_trade(trade_data)
        
        # Update trade
        self.db_manager.update_trade(trade_id, 150.5, 25.0)
        # Should not raise exception
    
    def test_trade_closure(self):
        """Test trade closure"""
        # Create a trade first
        trade_data = {
            'symbol': 'EURJPYc',
            'direction': 'BUY',
            'entry_price': 150.0,
            'position_size': 0.5,
            'entry_time': int(datetime.now(timezone.utc).timestamp() * 1000)
        }
        
        trade_id = self.db_manager.create_trade(trade_data)
        
        # Close trade
        self.db_manager.close_trade(trade_id, 151.0, 50.0, 'closed')
        # Should not raise exception
    
    def test_async_operations(self):
        """Test async operations"""
        async def run_async_test():
            # Start async writer
            await self.db_manager.start_async_writer()
            
            # Create a trade
            trade_data = {
                'symbol': 'EURJPYc',
                'direction': 'BUY',
                'entry_price': 150.0,
                'position_size': 0.5,
                'entry_time': int(datetime.now(timezone.utc).timestamp() * 1000)
            }
            
            trade_id = self.db_manager.create_trade(trade_data)
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Get active trades
            active_trades = await self.db_manager.get_active_trades()
            self.assertIsInstance(active_trades, list)
            
            # Get trade history
            trade_history = await self.db_manager.get_trade_history()
            self.assertIsInstance(trade_history, list)
            
            # Get statistics
            stats = await self.db_manager.get_trade_statistics()
            self.assertIsInstance(stats, dict)
            
            # Stop writer
            await self.db_manager.stop_async_writer()
        
        # Run the async test
        asyncio.run(run_async_test())
    
    def test_performance_stats(self):
        """Test performance statistics"""
        stats = self.db_manager.get_performance_stats()
        self.assertIn('write_count', stats)
        self.assertIn('read_count', stats)
        self.assertIn('error_count', stats)
        self.assertIn('running', stats)

class TestHistoricalAnalysisEngine(unittest.TestCase):
    """Test historical analysis engine"""
    
    def setUp(self):
        self.config = {
            'symbol': 'GBPJPYc',
            'analysis_config': {
                'lookback_periods': {
                    'daily': 30,
                    'weekly': 12,
                    'monthly': 12
                }
            }
        }
        self.analysis_engine = HistoricalAnalysisEngine(self.config)
    
    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation"""
        returns = np.array([0.01, 0.02, -0.01, 0.03, 0.01], dtype=np.float32)
        
        sharpe_ratio = self.analysis_engine.calculate_sharpe_ratio(returns)
        self.assertIsInstance(sharpe_ratio, float)
    
    def test_max_drawdown_calculation(self):
        """Test maximum drawdown calculation"""
        equity_values = np.array([10000.0, 10500.0, 10200.0, 9800.0, 9500.0], dtype=np.float32)
        
        max_drawdown = self.analysis_engine.calculate_max_drawdown(equity_values)
        self.assertIsInstance(max_drawdown, float)
        self.assertGreaterEqual(max_drawdown, 0)
    
    def test_correlation_calculation(self):
        """Test correlation calculation"""
        series1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
        series2 = np.array([2.0, 4.0, 6.0, 8.0, 10.0], dtype=np.float32)
        
        correlation = self.analysis_engine.calculate_correlation(series1, series2)
        self.assertIsInstance(correlation, float)
        self.assertAlmostEqual(correlation, 1.0, places=5)  # Perfect correlation
    
    def test_performance_analysis(self):
        """Test performance analysis"""
        trade_data = [
            {'pnl': 50.0, 'exit_time': 1640995200000},
            {'pnl': -25.0, 'exit_time': 1640998800000},
            {'pnl': 75.0, 'exit_time': 1641002400000},
            {'pnl': 30.0, 'exit_time': 1641006000000},
            {'pnl': -40.0, 'exit_time': 1641009600000}
        ]
        
        result = self.analysis_engine.analyze_performance(trade_data, AnalysisPeriod.DAILY)
        self.assertIsNotNone(result)
        self.assertEqual(result.analysis_type, AnalysisType.PERFORMANCE)
        self.assertIn('total_trades', result.result_data)
        self.assertIn('win_rate', result.result_data)
    
    def test_risk_analysis(self):
        """Test risk analysis"""
        trade_data = [
            {'pnl': 50.0, 'exit_time': 1640995200000},
            {'pnl': -25.0, 'exit_time': 1640998800000},
            {'pnl': 75.0, 'exit_time': 1641002400000}
        ]
        
        result = self.analysis_engine.analyze_risk(trade_data, AnalysisPeriod.DAILY)
        self.assertIsNotNone(result)
        self.assertEqual(result.analysis_type, AnalysisType.RISK)
        self.assertIn('volatility', result.result_data)
        self.assertIn('max_drawdown', result.result_data)
    
    def test_correlation_analysis(self):
        """Test correlation analysis"""
        symbol_data = {
            'EURJPYc': [150.0, 151.0, 152.0, 153.0, 154.0],
            'GBPJPYc': [180.0, 181.0, 182.0, 183.0, 184.0]
        }
        
        result = self.analysis_engine.analyze_correlation(symbol_data, AnalysisPeriod.DAILY)
        self.assertIsNotNone(result)
        self.assertEqual(result.analysis_type, AnalysisType.CORRELATION)
        self.assertIn('correlations', result.result_data)
        self.assertIn('avg_correlation', result.result_data)
    
    def test_seasonality_analysis(self):
        """Test seasonality analysis"""
        trade_data = [
            {'pnl': 50.0, 'exit_time': 1640995200000},  # 2022-01-01 00:00:00
            {'pnl': -25.0, 'exit_time': 1640998800000},  # 2022-01-01 01:00:00
            {'pnl': 75.0, 'exit_time': 1641002400000}    # 2022-01-01 02:00:00
        ]
        
        result = self.analysis_engine.analyze_seasonality(trade_data, AnalysisPeriod.DAILY)
        self.assertIsNotNone(result)
        self.assertEqual(result.analysis_type, AnalysisType.SEASONALITY)
        self.assertIn('hourly_avg', result.result_data)
        self.assertIn('daily_avg', result.result_data)
    
    def test_analysis_result_storage(self):
        """Test analysis result storage"""
        trade_data = [{'pnl': 50.0, 'exit_time': 1640995200000}]
        
        result = self.analysis_engine.analyze_performance(trade_data, AnalysisPeriod.DAILY)
        self.analysis_engine.store_analysis_result(result)
        
        stored_results = self.analysis_engine.get_analysis_results()
        self.assertEqual(len(stored_results), 1)
    
    def test_analysis_statistics(self):
        """Test analysis statistics"""
        # Add some analysis results
        trade_data = [{'pnl': 50.0, 'exit_time': 1640995200000}]
        
        performance_result = self.analysis_engine.analyze_performance(trade_data, AnalysisPeriod.DAILY)
        risk_result = self.analysis_engine.analyze_risk(trade_data, AnalysisPeriod.DAILY)
        
        self.analysis_engine.store_analysis_result(performance_result)
        self.analysis_engine.store_analysis_result(risk_result)
        
        stats = self.analysis_engine.get_analysis_statistics()
        self.assertIn('total_analyses', stats)
        self.assertIn('analysis_type_counts', stats)
        self.assertIn('symbol', stats)

class TestPhase3Integration(unittest.TestCase):
    """Test Phase 3 integration"""
    
    def test_exit_stop_integration(self):
        """Test exit and stop integration"""
        exit_config = {
            'symbol': 'EURJPYc',
            'exit_thresholds': {'structure_break': 0.7, 'momentum_loss': 0.6}
        }
        stop_config = {
            'symbol': 'EURJPYc',
            'stop_config': {'initial_stop_atr_multiplier': 2.0}
        }
        
        exit_engine = MultiTimeframeExitEngine(exit_config)
        stop_manager = DynamicStopManager(stop_config)
        
        # Test integration
        market_data = {
            'ohlcv': {
                'high': [150.0, 151.0, 152.0],
                'low': [149.0, 150.0, 151.0],
                'close': [149.5, 150.5, 151.5],
                'volume': [1000, 1200, 1100]
            }
        }
        
        current_trade = {
            'entry_price': 150.0,
            'direction': 'BUY'
        }
        
        exit_signals = exit_engine.analyze_multi_timeframe_exits(market_data, current_trade)
        self.assertIsInstance(exit_signals, list)
        
        stop_loss = stop_manager.create_initial_stop(current_trade, market_data)
        self.assertIsNotNone(stop_loss)
    
    def test_scaling_breaker_integration(self):
        """Test scaling and breaker integration"""
        scaling_config = {
            'symbol': 'EURGBPc',
            'scaling_config': {'max_position_size': 1.0, 'scaling_increment': 0.25}
        }
        breaker_config = {
            'symbol': 'EURGBPc',
            'breaker_config': {'max_drawdown': 0.05, 'max_loss_limit': 1000.0}
        }
        
        scaling_manager = PartialScalingManager(scaling_config)
        breaker_system = CircuitBreakerSystem(breaker_config)
        
        # Test integration
        market_data = {
            'H1': {
                'ohlcv': {
                    'high': [0.8500, 0.8510, 0.8520],
                    'low': [0.8490, 0.8500, 0.8510],
                    'close': [0.8495, 0.8505, 0.8515],
                    'volume': [1000, 1200, 1100]
                }
            }
        }
        
        current_trade = {
            'entry_price': 0.8500,
            'direction': 'BUY',
            'position_size': 0.5
        }
        
        scaling_signals = scaling_manager.analyze_scaling_opportunities(market_data, current_trade)
        self.assertIsInstance(scaling_signals, list)
        
        # Test breaker
        triggered = breaker_system.check_drawdown_breaker(9000.0)
        self.assertIsInstance(triggered, bool)

def run_phase3_tests():
    """Run all Phase 3 tests"""
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestMultiTimeframeExitEngine,
        TestDynamicStopManager,
        TestPartialScalingManager,
        TestCircuitBreakerSystem,
        TestTradeManagementDB,
        TestHistoricalAnalysisEngine,
        TestPhase3Integration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_phase3_tests()
    if success:
        print("\nAll Phase 3 tests passed!")
    else:
        print("\nSome Phase 3 tests failed!")
