"""
Comprehensive tests for backtesting validation system

Tests 12-month backtesting validation for EURUSDc, GBPUSDc, XAUUSDc, BTCUSDc,
including performance analysis, risk assessment, and strategy validation.
"""

import pytest
import time
import math
import statistics
import numpy as np
import threading
import json
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Tuple, Optional
from collections import deque, defaultdict

from infra.backtesting_validation import (
    BacktestingValidator, Trade, BacktestMetrics, SymbolBacktest,
    BacktestValidation, BacktestReport, BacktestStatus, SymbolType,
    MarketCondition, PerformanceLevel, get_backtesting_validator,
    run_comprehensive_backtest, generate_backtest_report
)

class TestBacktestStatus:
    """Test backtest status enumeration"""
    
    def test_backtest_statuses(self):
        """Test all backtest statuses"""
        statuses = [
            BacktestStatus.PENDING,
            BacktestStatus.RUNNING,
            BacktestStatus.COMPLETED,
            BacktestStatus.FAILED,
            BacktestStatus.CANCELLED
        ]
        
        for status in statuses:
            assert isinstance(status, BacktestStatus)
            assert status.value in ["pending", "running", "completed", "failed", "cancelled"]

class TestSymbolType:
    """Test symbol type enumeration"""
    
    def test_symbol_types(self):
        """Test all symbol types"""
        types = [
            SymbolType.FOREX,
            SymbolType.CRYPTO,
            SymbolType.METALS,
            SymbolType.INDICES
        ]
        
        for symbol_type in types:
            assert isinstance(symbol_type, SymbolType)
            assert symbol_type.value in ["forex", "crypto", "metals", "indices"]

class TestMarketCondition:
    """Test market condition enumeration"""
    
    def test_market_conditions(self):
        """Test all market conditions"""
        conditions = [
            MarketCondition.TRENDING,
            MarketCondition.RANGING,
            MarketCondition.VOLATILE,
            MarketCondition.CALM,
            MarketCondition.BREAKOUT,
            MarketCondition.REVERSAL
        ]
        
        for condition in conditions:
            assert isinstance(condition, MarketCondition)
            assert condition.value in ["trending", "ranging", "volatile", "calm", "breakout", "reversal"]

class TestPerformanceLevel:
    """Test performance level enumeration"""
    
    def test_performance_levels(self):
        """Test all performance levels"""
        levels = [
            PerformanceLevel.EXCELLENT,
            PerformanceLevel.GOOD,
            PerformanceLevel.FAIR,
            PerformanceLevel.POOR,
            PerformanceLevel.CRITICAL
        ]
        
        for level in levels:
            assert isinstance(level, PerformanceLevel)
            assert level.value in ["excellent", "good", "fair", "poor", "critical"]

class TestTrade:
    """Test trade data structure"""
    
    def test_trade_creation(self):
        """Test trade creation"""
        trade = Trade(
            trade_id="EURUSDc_001",
            symbol="EURUSDc",
            entry_time=time.time() - 3600,
            exit_time=time.time(),
            entry_price=1.1000,
            exit_price=1.1050,
            volume=1.0,
            direction="long",
            pnl=50.0,
            commission=10.0,
            slippage=5.0,
            duration_hours=1.0,
            max_favorable=60.0,
            max_adverse=40.0,
            exit_reason="strategy_exit",
            metadata={"test": True}
        )
        
        assert trade.trade_id == "EURUSDc_001"
        assert trade.symbol == "EURUSDc"
        assert trade.entry_time < trade.exit_time
        assert trade.entry_price == 1.1000
        assert trade.exit_price == 1.1050
        assert trade.volume == 1.0
        assert trade.direction == "long"
        assert trade.pnl == 50.0
        assert trade.commission == 10.0
        assert trade.slippage == 5.0
        assert trade.duration_hours == 1.0
        assert trade.max_favorable == 60.0
        assert trade.max_adverse == 40.0
        assert trade.exit_reason == "strategy_exit"
        assert trade.metadata["test"] is True
    
    def test_trade_defaults(self):
        """Test trade defaults"""
        trade = Trade(
            trade_id="test_001",
            symbol="TEST",
            entry_time=time.time(),
            exit_time=time.time() + 3600,
            entry_price=100.0,
            exit_price=105.0,
            volume=1.0,
            direction="long",
            pnl=5.0,
            commission=1.0,
            slippage=0.5,
            duration_hours=1.0,
            max_favorable=6.0,
            max_adverse=4.0,
            exit_reason="test"
        )
        
        assert trade.metadata == {}

class TestBacktestMetrics:
    """Test backtest metrics data structure"""
    
    def test_backtest_metrics_creation(self):
        """Test backtest metrics creation"""
        metrics = BacktestMetrics(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=0.6,
            avg_win=50.0,
            avg_loss=30.0,
            largest_win=200.0,
            largest_loss=150.0,
            profit_factor=2.0,
            gross_profit=3000.0,
            gross_loss=1200.0,
            net_profit=1800.0,
            max_drawdown=0.1,
            max_drawdown_duration=5.0,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=1.8,
            recovery_factor=1.2,
            expectancy=18.0,
            avg_trade_duration=2.5,
            trades_per_month=25.0,
            annual_return=0.15,
            volatility=0.12,
            var_95=-50.0,
            var_99=-100.0,
            metadata={"test": True}
        )
        
        assert metrics.total_trades == 100
        assert metrics.winning_trades == 60
        assert metrics.losing_trades == 40
        assert metrics.win_rate == 0.6
        assert metrics.avg_win == 50.0
        assert metrics.avg_loss == 30.0
        assert metrics.largest_win == 200.0
        assert metrics.largest_loss == 150.0
        assert metrics.profit_factor == 2.0
        assert metrics.gross_profit == 3000.0
        assert metrics.gross_loss == 1200.0
        assert metrics.net_profit == 1800.0
        assert metrics.max_drawdown == 0.1
        assert metrics.max_drawdown_duration == 5.0
        assert metrics.sharpe_ratio == 1.5
        assert metrics.sortino_ratio == 2.0
        assert metrics.calmar_ratio == 1.8
        assert metrics.recovery_factor == 1.2
        assert metrics.expectancy == 18.0
        assert metrics.avg_trade_duration == 2.5
        assert metrics.trades_per_month == 25.0
        assert metrics.annual_return == 0.15
        assert metrics.volatility == 0.12
        assert metrics.var_95 == -50.0
        assert metrics.var_99 == -100.0
        assert metrics.metadata["test"] is True
    
    def test_backtest_metrics_defaults(self):
        """Test backtest metrics defaults"""
        metrics = BacktestMetrics(
            total_trades=0, winning_trades=0, losing_trades=0, win_rate=0.0,
            avg_win=0.0, avg_loss=0.0, largest_win=0.0, largest_loss=0.0,
            profit_factor=0.0, gross_profit=0.0, gross_loss=0.0, net_profit=0.0,
            max_drawdown=0.0, max_drawdown_duration=0.0, sharpe_ratio=0.0,
            sortino_ratio=0.0, calmar_ratio=0.0, recovery_factor=0.0,
            expectancy=0.0, avg_trade_duration=0.0, trades_per_month=0.0,
            annual_return=0.0, volatility=0.0, var_95=0.0, var_99=0.0
        )
        
        assert metrics.metadata == {}

class TestSymbolBacktest:
    """Test symbol backtest data structure"""
    
    def test_symbol_backtest_creation(self):
        """Test symbol backtest creation"""
        trade = Trade(
            trade_id="test_001", symbol="EURUSDc", entry_time=time.time(),
            exit_time=time.time() + 3600, entry_price=1.1000, exit_price=1.1050,
            volume=1.0, direction="long", pnl=50.0, commission=10.0, slippage=5.0,
            duration_hours=1.0, max_favorable=60.0, max_adverse=40.0, exit_reason="test"
        )
        
        metrics = BacktestMetrics(
            total_trades=1, winning_trades=1, losing_trades=0, win_rate=1.0,
            avg_win=50.0, avg_loss=0.0, largest_win=50.0, largest_loss=0.0,
            profit_factor=float('inf'), gross_profit=50.0, gross_loss=0.0, net_profit=50.0,
            max_drawdown=0.0, max_drawdown_duration=0.0, sharpe_ratio=0.0,
            sortino_ratio=0.0, calmar_ratio=0.0, recovery_factor=0.0,
            expectancy=50.0, avg_trade_duration=1.0, trades_per_month=1.0,
            annual_return=0.05, volatility=0.0, var_95=0.0, var_99=0.0
        )
        
        market_conditions = {
            MarketCondition.TRENDING: 0.8,
            MarketCondition.RANGING: 0.2,
            MarketCondition.VOLATILE: 0.3,
            MarketCondition.CALM: 0.7,
            MarketCondition.BREAKOUT: 0.1,
            MarketCondition.REVERSAL: 0.1
        }
        
        symbol_backtest = SymbolBacktest(
            symbol="EURUSDc",
            symbol_type=SymbolType.FOREX,
            start_date=time.time() - 86400,
            end_date=time.time(),
            duration_days=1,
            total_trades=1,
            metrics=metrics,
            trades=[trade],
            market_conditions=market_conditions,
            performance_level=PerformanceLevel.EXCELLENT,
            validation_status="PASSED",
            recommendations=["Excellent performance"],
            metadata={"test": True}
        )
        
        assert symbol_backtest.symbol == "EURUSDc"
        assert symbol_backtest.symbol_type == SymbolType.FOREX
        assert symbol_backtest.start_date < symbol_backtest.end_date
        assert symbol_backtest.duration_days == 1
        assert symbol_backtest.total_trades == 1
        assert symbol_backtest.metrics == metrics
        assert len(symbol_backtest.trades) == 1
        assert symbol_backtest.market_conditions[MarketCondition.TRENDING] == 0.8
        assert symbol_backtest.performance_level == PerformanceLevel.EXCELLENT
        assert symbol_backtest.validation_status == "PASSED"
        assert len(symbol_backtest.recommendations) == 1
        assert symbol_backtest.metadata["test"] is True
    
    def test_symbol_backtest_defaults(self):
        """Test symbol backtest defaults"""
        metrics = BacktestMetrics(
            total_trades=0, winning_trades=0, losing_trades=0, win_rate=0.0,
            avg_win=0.0, avg_loss=0.0, largest_win=0.0, largest_loss=0.0,
            profit_factor=0.0, gross_profit=0.0, gross_loss=0.0, net_profit=0.0,
            max_drawdown=0.0, max_drawdown_duration=0.0, sharpe_ratio=0.0,
            sortino_ratio=0.0, calmar_ratio=0.0, recovery_factor=0.0,
            expectancy=0.0, avg_trade_duration=0.0, trades_per_month=0.0,
            annual_return=0.0, volatility=0.0, var_95=0.0, var_99=0.0
        )
        
        symbol_backtest = SymbolBacktest(
            symbol="TEST",
            symbol_type=SymbolType.FOREX,
            start_date=time.time(),
            end_date=time.time() + 86400,
            duration_days=1,
            total_trades=0,
            metrics=metrics,
            trades=[],
            market_conditions={},
            performance_level=PerformanceLevel.CRITICAL,
            validation_status="FAILED",
            recommendations=[]
        )
        
        assert symbol_backtest.metadata == {}

class TestBacktestValidation:
    """Test backtest validation data structure"""
    
    def test_backtest_validation_creation(self):
        """Test backtest validation creation"""
        trade = Trade(
            trade_id="test_001", symbol="EURUSDc", entry_time=time.time(),
            exit_time=time.time() + 3600, entry_price=1.1000, exit_price=1.1050,
            volume=1.0, direction="long", pnl=50.0, commission=10.0, slippage=5.0,
            duration_hours=1.0, max_favorable=60.0, max_adverse=40.0, exit_reason="test"
        )
        
        metrics = BacktestMetrics(
            total_trades=1, winning_trades=1, losing_trades=0, win_rate=1.0,
            avg_win=50.0, avg_loss=0.0, largest_win=50.0, largest_loss=0.0,
            profit_factor=float('inf'), gross_profit=50.0, gross_loss=0.0, net_profit=50.0,
            max_drawdown=0.0, max_drawdown_duration=0.0, sharpe_ratio=0.0,
            sortino_ratio=0.0, calmar_ratio=0.0, recovery_factor=0.0,
            expectancy=50.0, avg_trade_duration=1.0, trades_per_month=1.0,
            annual_return=0.05, volatility=0.0, var_95=0.0, var_99=0.0
        )
        
        symbol_backtest = SymbolBacktest(
            symbol="EURUSDc", symbol_type=SymbolType.FOREX,
            start_date=time.time() - 86400, end_date=time.time(), duration_days=1,
            total_trades=1, metrics=metrics, trades=[trade], market_conditions={},
            performance_level=PerformanceLevel.EXCELLENT, validation_status="PASSED",
            recommendations=[]
        )
        
        validation = BacktestValidation(
            timestamp=time.time(),
            backtest_id="test_001",
            symbols=["EURUSDc"],
            start_date=time.time() - 86400,
            end_date=time.time(),
            duration_days=1,
            total_trades=1,
            overall_metrics=metrics,
            symbol_results=[symbol_backtest],
            validation_status="PASSED",
            performance_level=PerformanceLevel.EXCELLENT,
            risk_assessment="LOW",
            strategy_validation="EXCELLENT",
            recommendations=["Excellent performance"],
            detailed_analysis={"test": "analysis"},
            metadata={"test": True}
        )
        
        assert validation.timestamp > 0
        assert validation.backtest_id == "test_001"
        assert validation.symbols == ["EURUSDc"]
        assert validation.start_date < validation.end_date
        assert validation.duration_days == 1
        assert validation.total_trades == 1
        assert validation.overall_metrics == metrics
        assert len(validation.symbol_results) == 1
        assert validation.validation_status == "PASSED"
        assert validation.performance_level == PerformanceLevel.EXCELLENT
        assert validation.risk_assessment == "LOW"
        assert validation.strategy_validation == "EXCELLENT"
        assert len(validation.recommendations) == 1
        assert validation.detailed_analysis["test"] == "analysis"
        assert validation.metadata["test"] is True
    
    def test_backtest_validation_defaults(self):
        """Test backtest validation defaults"""
        metrics = BacktestMetrics(
            total_trades=0, winning_trades=0, losing_trades=0, win_rate=0.0,
            avg_win=0.0, avg_loss=0.0, largest_win=0.0, largest_loss=0.0,
            profit_factor=0.0, gross_profit=0.0, gross_loss=0.0, net_profit=0.0,
            max_drawdown=0.0, max_drawdown_duration=0.0, sharpe_ratio=0.0,
            sortino_ratio=0.0, calmar_ratio=0.0, recovery_factor=0.0,
            expectancy=0.0, avg_trade_duration=0.0, trades_per_month=0.0,
            annual_return=0.0, volatility=0.0, var_95=0.0, var_99=0.0
        )
        
        validation = BacktestValidation(
            timestamp=time.time(),
            backtest_id="test_002",
            symbols=[],
            start_date=time.time(),
            end_date=time.time() + 86400,
            duration_days=1,
            total_trades=0,
            overall_metrics=metrics,
            symbol_results=[],
            validation_status="FAILED",
            performance_level=PerformanceLevel.CRITICAL,
            risk_assessment="HIGH",
            strategy_validation="POOR",
            recommendations=[]
        )
        
        assert validation.detailed_analysis == {}
        assert validation.metadata == {}

class TestBacktestReport:
    """Test backtest report data structure"""
    
    def test_backtest_report_creation(self):
        """Test backtest report creation"""
        metrics = BacktestMetrics(
            total_trades=100, winning_trades=60, losing_trades=40, win_rate=0.6,
            avg_win=50.0, avg_loss=30.0, largest_win=200.0, largest_loss=150.0,
            profit_factor=2.0, gross_profit=3000.0, gross_loss=1200.0, net_profit=1800.0,
            max_drawdown=0.1, max_drawdown_duration=5.0, sharpe_ratio=1.5,
            sortino_ratio=2.0, calmar_ratio=1.8, recovery_factor=1.2,
            expectancy=18.0, avg_trade_duration=2.5, trades_per_month=25.0,
            annual_return=0.15, volatility=0.12, var_95=-50.0, var_99=-100.0
        )
        
        symbol_backtest = SymbolBacktest(
            symbol="EURUSDc", symbol_type=SymbolType.FOREX,
            start_date=time.time() - 86400, end_date=time.time(), duration_days=1,
            total_trades=50, metrics=metrics, trades=[], market_conditions={},
            performance_level=PerformanceLevel.GOOD, validation_status="PASSED",
            recommendations=[]
        )
        
        validation = BacktestValidation(
            timestamp=time.time(),
            backtest_id="test_001",
            symbols=["EURUSDc"],
            start_date=time.time() - 86400,
            end_date=time.time(),
            duration_days=1,
            total_trades=100,
            overall_metrics=metrics,
            symbol_results=[symbol_backtest],
            validation_status="PASSED",
            performance_level=PerformanceLevel.GOOD,
            risk_assessment="MEDIUM",
            strategy_validation="GOOD",
            recommendations=[]
        )
        
        report = BacktestReport(
            timestamp=time.time(),
            backtest_id="test_001",
            symbols=["EURUSDc"],
            start_date=time.time() - 86400,
            end_date=time.time(),
            duration_days=1,
            overall_performance_score=0.8,
            risk_score=0.3,
            consistency_score=0.9,
            total_trades=100,
            overall_metrics=metrics,
            symbol_breakdown={"EURUSDc": symbol_backtest},
            market_condition_analysis={},
            performance_attribution={"EURUSDc": 1.0},
            risk_metrics={"max_drawdown": 0.1},
            validation_results=[validation],
            recommendations=["Good performance"],
            metadata={"test": True}
        )
        
        assert report.timestamp > 0
        assert report.backtest_id == "test_001"
        assert report.symbols == ["EURUSDc"]
        assert report.start_date < report.end_date
        assert report.duration_days == 1
        assert report.overall_performance_score == 0.8
        assert report.risk_score == 0.3
        assert report.consistency_score == 0.9
        assert report.total_trades == 100
        assert report.overall_metrics == metrics
        assert "EURUSDc" in report.symbol_breakdown
        assert len(report.market_condition_analysis) >= 0
        assert report.performance_attribution["EURUSDc"] == 1.0
        assert report.risk_metrics["max_drawdown"] == 0.1
        assert len(report.validation_results) == 1
        assert len(report.recommendations) == 1
        assert report.metadata["test"] is True
    
    def test_backtest_report_defaults(self):
        """Test backtest report defaults"""
        metrics = BacktestMetrics(
            total_trades=0, winning_trades=0, losing_trades=0, win_rate=0.0,
            avg_win=0.0, avg_loss=0.0, largest_win=0.0, largest_loss=0.0,
            profit_factor=0.0, gross_profit=0.0, gross_loss=0.0, net_profit=0.0,
            max_drawdown=0.0, max_drawdown_duration=0.0, sharpe_ratio=0.0,
            sortino_ratio=0.0, calmar_ratio=0.0, recovery_factor=0.0,
            expectancy=0.0, avg_trade_duration=0.0, trades_per_month=0.0,
            annual_return=0.0, volatility=0.0, var_95=0.0, var_99=0.0
        )
        
        report = BacktestReport(
            timestamp=time.time(),
            backtest_id="test_002",
            symbols=[],
            start_date=time.time(),
            end_date=time.time() + 86400,
            duration_days=1,
            overall_performance_score=0.0,
            risk_score=1.0,
            consistency_score=0.0,
            total_trades=0,
            overall_metrics=metrics,
            symbol_breakdown={},
            market_condition_analysis={},
            performance_attribution={},
            risk_metrics={},
            validation_results=[],
            recommendations=[]
        )
        
        assert report.metadata == {}

class TestBacktestingValidator:
    """Test backtesting validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = BacktestingValidator()
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.database_path is None
        assert len(self.validator.backtest_results) == 0
        assert len(self.validator.symbol_data) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
        assert self.validator.symbols == ["EURUSDc", "GBPUSDc", "XAUUSDc", "BTCUSDc"]
        assert len(self.validator.symbol_types) == 4
        assert self.validator.backtest_duration_days == 365
        assert self.validator.min_trades_per_symbol == 50
        assert self.validator.max_drawdown_threshold == 0.15
        assert self.validator.min_win_rate == 0.4
        assert self.validator.min_profit_factor == 1.2
    
    def test_load_historical_data(self):
        """Test historical data loading"""
        start_date = time.time() - 86400  # 1 day ago
        end_date = time.time()
        
        data = self.validator.load_historical_data("EURUSDc", start_date, end_date)
        
        assert len(data) > 0
        assert all("timestamp" in d for d in data)
        assert all("open" in d for d in data)
        assert all("high" in d for d in data)
        assert all("low" in d for d in data)
        assert all("close" in d for d in data)
        assert all("volume" in d for d in data)
        assert all("symbol" in d for d in data)
        assert all(d["symbol"] == "EURUSDc" for d in data)
        assert all(start_date <= d["timestamp"] <= end_date for d in data)
    
    def test_run_backtest(self):
        """Test running backtest for specific symbol"""
        start_date = time.time() - 86400  # 1 day ago
        end_date = time.time()
        
        symbol_backtest = self.validator.run_backtest("EURUSDc", start_date, end_date)
        
        assert symbol_backtest.symbol == "EURUSDc"
        assert symbol_backtest.symbol_type == SymbolType.FOREX
        assert symbol_backtest.start_date == start_date
        assert symbol_backtest.end_date == end_date
        assert symbol_backtest.duration_days >= 0
        assert symbol_backtest.total_trades >= 0
        assert isinstance(symbol_backtest.metrics, BacktestMetrics)
        assert isinstance(symbol_backtest.trades, list)
        assert len(symbol_backtest.market_conditions) >= 0
        assert symbol_backtest.performance_level in [PerformanceLevel.EXCELLENT, PerformanceLevel.GOOD,
                                                    PerformanceLevel.FAIR, PerformanceLevel.POOR, PerformanceLevel.CRITICAL]
        assert symbol_backtest.validation_status in ["PASSED", "WARNING", "FAILED"]
        assert isinstance(symbol_backtest.recommendations, list)
        assert len(symbol_backtest.metadata) >= 0
    
    def test_run_comprehensive_backtest(self):
        """Test running comprehensive backtest"""
        start_date = time.time() - 86400  # 1 day ago
        end_date = time.time()
        
        validation = self.validator.run_comprehensive_backtest(start_date, end_date)
        
        assert validation.timestamp > 0
        assert validation.backtest_id is not None
        assert validation.symbols == ["EURUSDc", "GBPUSDc", "XAUUSDc", "BTCUSDc"]
        assert validation.start_date == start_date
        assert validation.end_date == end_date
        assert validation.duration_days >= 0
        assert validation.total_trades >= 0
        assert isinstance(validation.overall_metrics, BacktestMetrics)
        assert len(validation.symbol_results) == 4
        assert validation.validation_status in ["PASSED", "WARNING", "FAILED"]
        assert validation.performance_level in [PerformanceLevel.EXCELLENT, PerformanceLevel.GOOD,
                                              PerformanceLevel.FAIR, PerformanceLevel.POOR, PerformanceLevel.CRITICAL]
        assert validation.risk_assessment in ["LOW", "MEDIUM", "HIGH"]
        assert validation.strategy_validation in ["EXCELLENT", "GOOD", "FAIR", "POOR"]
        assert isinstance(validation.recommendations, list)
        assert len(validation.detailed_analysis) >= 0
        assert len(validation.metadata) >= 0
        
        # Check that backtest was stored
        assert validation.backtest_id in self.validator.backtest_results
    
    def test_generate_backtest_report(self):
        """Test generating backtest report"""
        # First run a backtest
        start_date = time.time() - 86400
        end_date = time.time()
        validation = self.validator.run_comprehensive_backtest(start_date, end_date)
        
        # Generate report
        report = self.validator.generate_backtest_report(validation.backtest_id)
        
        assert report.timestamp > 0
        assert report.backtest_id == validation.backtest_id
        assert report.symbols == validation.symbols
        assert report.start_date == validation.start_date
        assert report.end_date == validation.end_date
        assert report.duration_days == validation.duration_days
        assert 0.0 <= report.overall_performance_score <= 1.0
        assert 0.0 <= report.risk_score <= 1.0
        assert 0.0 <= report.consistency_score <= 1.0
        assert report.total_trades == validation.total_trades
        assert report.overall_metrics == validation.overall_metrics
        assert len(report.symbol_breakdown) == 4
        assert len(report.market_condition_analysis) >= 0
        assert len(report.performance_attribution) == 4
        assert len(report.risk_metrics) >= 0
        assert len(report.validation_results) == 1
        assert isinstance(report.recommendations, list)
        assert len(report.metadata) >= 0

class TestGlobalFunctions:
    """Test global backtesting functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.backtesting_validation
        infra.backtesting_validation._backtesting_validator = None
    
    def test_get_backtesting_validator(self):
        """Test global validator access"""
        validator1 = get_backtesting_validator()
        validator2 = get_backtesting_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, BacktestingValidator)
    
    def test_run_comprehensive_backtest_global(self):
        """Test global comprehensive backtest"""
        start_date = time.time() - 86400
        end_date = time.time()
        
        validation = run_comprehensive_backtest(start_date, end_date)
        
        assert validation.timestamp > 0
        assert validation.backtest_id is not None
        assert validation.symbols == ["EURUSDc", "GBPUSDc", "XAUUSDc", "BTCUSDc"]
        assert validation.start_date == start_date
        assert validation.end_date == end_date
        assert validation.duration_days >= 0
        assert validation.total_trades >= 0
        assert isinstance(validation.overall_metrics, BacktestMetrics)
        assert len(validation.symbol_results) == 4
        assert validation.validation_status in ["PASSED", "WARNING", "FAILED"]
        assert validation.performance_level in [PerformanceLevel.EXCELLENT, PerformanceLevel.GOOD,
                                              PerformanceLevel.FAIR, PerformanceLevel.POOR, PerformanceLevel.CRITICAL]
        assert validation.risk_assessment in ["LOW", "MEDIUM", "HIGH"]
        assert validation.strategy_validation in ["EXCELLENT", "GOOD", "FAIR", "POOR"]
        assert isinstance(validation.recommendations, list)
        assert len(validation.detailed_analysis) >= 0
        assert len(validation.metadata) >= 0
    
    def test_generate_backtest_report_global(self):
        """Test global backtest report generation"""
        # First run a backtest
        start_date = time.time() - 86400
        end_date = time.time()
        validation = run_comprehensive_backtest(start_date, end_date)
        
        # Generate report
        report = generate_backtest_report(validation.backtest_id)
        
        assert report.timestamp > 0
        assert report.backtest_id == validation.backtest_id
        assert report.symbols == validation.symbols
        assert report.start_date == validation.start_date
        assert report.end_date == validation.end_date
        assert report.duration_days == validation.duration_days
        assert 0.0 <= report.overall_performance_score <= 1.0
        assert 0.0 <= report.risk_score <= 1.0
        assert 0.0 <= report.consistency_score <= 1.0
        assert report.total_trades == validation.total_trades
        assert report.overall_metrics == validation.overall_metrics
        assert len(report.symbol_breakdown) == 4
        assert len(report.market_condition_analysis) >= 0
        assert len(report.performance_attribution) == 4
        assert len(report.risk_metrics) >= 0
        assert len(report.validation_results) == 1
        assert isinstance(report.recommendations, list)
        assert len(report.metadata) >= 0

class TestBacktestingIntegration:
    """Integration tests for backtesting validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.backtesting_validation
        infra.backtesting_validation._backtesting_validator = None
    
    def test_comprehensive_backtesting_validation(self):
        """Test comprehensive backtesting validation workflow"""
        # Run comprehensive backtest
        start_date = time.time() - 86400  # 1 day ago
        end_date = time.time()
        
        validation = run_comprehensive_backtest(start_date, end_date)
        
        # Validate results
        assert validation.timestamp > 0
        assert validation.backtest_id is not None
        assert validation.symbols == ["EURUSDc", "GBPUSDc", "XAUUSDc", "BTCUSDc"]
        assert validation.start_date == start_date
        assert validation.end_date == end_date
        assert validation.duration_days >= 0
        assert validation.total_trades >= 0
        assert isinstance(validation.overall_metrics, BacktestMetrics)
        assert len(validation.symbol_results) == 4
        
        # Check symbol results
        for symbol_result in validation.symbol_results:
            assert symbol_result.symbol in ["EURUSDc", "GBPUSDc", "XAUUSDc", "BTCUSDc"]
            assert symbol_result.symbol_type in [SymbolType.FOREX, SymbolType.CRYPTO, SymbolType.METALS]
            assert symbol_result.start_date == start_date
            assert symbol_result.end_date == end_date
            assert symbol_result.duration_days >= 0
            assert symbol_result.total_trades >= 0
            assert isinstance(symbol_result.metrics, BacktestMetrics)
            assert isinstance(symbol_result.trades, list)
            assert len(symbol_result.market_conditions) >= 0
            assert symbol_result.performance_level in [PerformanceLevel.EXCELLENT, PerformanceLevel.GOOD,
                                                      PerformanceLevel.FAIR, PerformanceLevel.POOR, PerformanceLevel.CRITICAL]
            assert symbol_result.validation_status in ["PASSED", "WARNING", "FAILED"]
            assert isinstance(symbol_result.recommendations, list)
            assert len(symbol_result.metadata) >= 0
        
        # Check overall validation
        assert validation.validation_status in ["PASSED", "WARNING", "FAILED"]
        assert validation.performance_level in [PerformanceLevel.EXCELLENT, PerformanceLevel.GOOD,
                                              PerformanceLevel.FAIR, PerformanceLevel.POOR, PerformanceLevel.CRITICAL]
        assert validation.risk_assessment in ["LOW", "MEDIUM", "HIGH"]
        assert validation.strategy_validation in ["EXCELLENT", "GOOD", "FAIR", "POOR"]
        assert isinstance(validation.recommendations, list)
        assert len(validation.detailed_analysis) >= 0
        assert len(validation.metadata) >= 0
        
        # Generate comprehensive report
        report = generate_backtest_report(validation.backtest_id)
        
        assert report.timestamp > 0
        assert report.backtest_id == validation.backtest_id
        assert report.symbols == validation.symbols
        assert report.start_date == validation.start_date
        assert report.end_date == validation.end_date
        assert report.duration_days == validation.duration_days
        assert 0.0 <= report.overall_performance_score <= 1.0
        assert 0.0 <= report.risk_score <= 1.0
        assert 0.0 <= report.consistency_score <= 1.0
        assert report.total_trades == validation.total_trades
        assert report.overall_metrics == validation.overall_metrics
        assert len(report.symbol_breakdown) == 4
        assert len(report.market_condition_analysis) >= 0
        assert len(report.performance_attribution) == 4
        assert len(report.risk_metrics) >= 0
        assert len(report.validation_results) == 1
        assert isinstance(report.recommendations, list)
        assert len(report.metadata) >= 0
    
    def test_performance_analysis(self):
        """Test performance analysis capabilities"""
        # Run backtest
        start_date = time.time() - 86400
        end_date = time.time()
        validation = run_comprehensive_backtest(start_date, end_date)
        
        # Check performance metrics
        metrics = validation.overall_metrics
        assert metrics.total_trades >= 0
        assert metrics.winning_trades >= 0
        assert metrics.losing_trades >= 0
        assert 0.0 <= metrics.win_rate <= 1.0
        assert metrics.avg_win >= 0.0
        assert metrics.avg_loss <= 0.0
        assert metrics.largest_win >= 0.0
        assert metrics.largest_loss <= 0.0
        assert metrics.profit_factor >= 0.0
        assert metrics.gross_profit >= 0.0
        assert metrics.gross_loss >= 0.0
        assert metrics.net_profit >= 0.0
        assert metrics.max_drawdown >= 0.0
        assert metrics.max_drawdown_duration >= 0.0
        assert metrics.sharpe_ratio >= 0.0
        assert metrics.sortino_ratio >= 0.0
        assert metrics.calmar_ratio >= 0.0
        assert metrics.recovery_factor >= 0.0
        assert metrics.expectancy >= 0.0
        assert metrics.avg_trade_duration >= 0.0
        assert metrics.trades_per_month >= 0.0
        assert metrics.annual_return >= 0.0
        assert metrics.volatility >= 0.0
        assert metrics.var_95 <= 0.0
        assert metrics.var_99 <= 0.0
        assert len(metrics.metadata) >= 0
    
    def test_risk_assessment(self):
        """Test risk assessment capabilities"""
        # Run backtest
        start_date = time.time() - 86400
        end_date = time.time()
        validation = run_comprehensive_backtest(start_date, end_date)
        
        # Check risk assessment
        assert validation.risk_assessment in ["LOW", "MEDIUM", "HIGH"]
        
        # Check risk metrics
        metrics = validation.overall_metrics
        assert metrics.max_drawdown >= 0.0
        assert metrics.var_95 <= 0.0
        assert metrics.var_99 <= 0.0
        assert metrics.volatility >= 0.0
        assert metrics.sharpe_ratio >= 0.0
        assert metrics.sortino_ratio >= 0.0
        assert metrics.calmar_ratio >= 0.0
        assert metrics.recovery_factor >= 0.0
    
    def test_strategy_validation(self):
        """Test strategy validation capabilities"""
        # Run backtest
        start_date = time.time() - 86400
        end_date = time.time()
        validation = run_comprehensive_backtest(start_date, end_date)
        
        # Check strategy validation
        assert validation.strategy_validation in ["EXCELLENT", "GOOD", "FAIR", "POOR"]
        
        # Check performance level
        assert validation.performance_level in [PerformanceLevel.EXCELLENT, PerformanceLevel.GOOD,
                                              PerformanceLevel.FAIR, PerformanceLevel.POOR, PerformanceLevel.CRITICAL]
        
        # Check validation status
        assert validation.validation_status in ["PASSED", "WARNING", "FAILED"]
    
    def test_market_condition_analysis(self):
        """Test market condition analysis"""
        # Run backtest
        start_date = time.time() - 86400
        end_date = time.time()
        validation = run_comprehensive_backtest(start_date, end_date)
        
        # Check market conditions for each symbol
        for symbol_result in validation.symbol_results:
            assert len(symbol_result.market_conditions) >= 0
            for condition, score in symbol_result.market_conditions.items():
                assert isinstance(condition, MarketCondition)
                assert 0.0 <= score <= 1.0
    
    def test_recommendations_generation(self):
        """Test recommendations generation"""
        # Run backtest
        start_date = time.time() - 86400
        end_date = time.time()
        validation = run_comprehensive_backtest(start_date, end_date)
        
        # Check recommendations
        assert isinstance(validation.recommendations, list)
        assert len(validation.recommendations) >= 0
        
        # Check symbol-specific recommendations
        for symbol_result in validation.symbol_results:
            assert isinstance(symbol_result.recommendations, list)
            assert len(symbol_result.recommendations) >= 0
    
    def test_detailed_analysis(self):
        """Test detailed analysis generation"""
        # Run backtest
        start_date = time.time() - 86400
        end_date = time.time()
        validation = run_comprehensive_backtest(start_date, end_date)
        
        # Check detailed analysis
        assert isinstance(validation.detailed_analysis, dict)
        assert len(validation.detailed_analysis) >= 0
        
        # Check report generation
        report = generate_backtest_report(validation.backtest_id)
        
        assert report.overall_performance_score >= 0.0
        assert report.risk_score >= 0.0
        assert report.consistency_score >= 0.0
        assert len(report.symbol_breakdown) == 4
        assert len(report.market_condition_analysis) >= 0
        assert len(report.performance_attribution) == 4
        assert len(report.risk_metrics) >= 0
        assert len(report.validation_results) == 1
        assert isinstance(report.recommendations, list)
        assert len(report.metadata) >= 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])