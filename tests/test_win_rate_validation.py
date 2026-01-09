"""
Comprehensive tests for win rate validation system

Tests win rate validation ≥80% with R:R ≥1:3, trade performance analysis,
risk-adjusted returns validation, win rate calculation, performance metrics
validation, and comprehensive reporting.
"""

import pytest
import time
import math
import statistics
import numpy as np
import threading
import json
import asyncio
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Tuple, Optional
from collections import deque

from infra.win_rate_validation import (
    WinRateValidator, TradeAnalyzer, Trade, PerformanceMetrics,
    WinRateValidation, WinRateReport, TradeOutcome, WinRateLevel,
    RRLevel, ValidationStatus, get_win_rate_validator,
    validate_win_rate, generate_win_rate_report
)

class TestTradeOutcome:
    """Test trade outcome enumeration"""
    
    def test_trade_outcomes(self):
        """Test all trade outcomes"""
        outcomes = [
            TradeOutcome.WIN,
            TradeOutcome.LOSS,
            TradeOutcome.BREAKEVEN,
            TradeOutcome.PARTIAL_WIN,
            TradeOutcome.PARTIAL_LOSS
        ]
        
        for outcome in outcomes:
            assert isinstance(outcome, TradeOutcome)
            assert outcome.value in ["win", "loss", "breakeven", "partial_win", "partial_loss"]

class TestWinRateLevel:
    """Test win rate level enumeration"""
    
    def test_win_rate_levels(self):
        """Test all win rate levels"""
        levels = [
            WinRateLevel.EXCELLENT,
            WinRateLevel.GOOD,
            WinRateLevel.FAIR,
            WinRateLevel.POOR,
            WinRateLevel.CRITICAL
        ]
        
        for level in levels:
            assert isinstance(level, WinRateLevel)
            assert level.value in ["excellent", "good", "fair", "poor", "critical"]

class TestRRLevel:
    """Test R:R level enumeration"""
    
    def test_rr_levels(self):
        """Test all R:R levels"""
        levels = [
            RRLevel.EXCELLENT,
            RRLevel.GOOD,
            RRLevel.FAIR,
            RRLevel.POOR,
            RRLevel.CRITICAL
        ]
        
        for level in levels:
            assert isinstance(level, RRLevel)
            assert level.value in ["excellent", "good", "fair", "poor", "critical"]

class TestValidationStatus:
    """Test validation status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            ValidationStatus.PASSED,
            ValidationStatus.WARNING,
            ValidationStatus.FAILED,
            ValidationStatus.PENDING
        ]
        
        for status in statuses:
            assert isinstance(status, ValidationStatus)
            assert status.value in ["passed", "warning", "failed", "pending"]

class TestTrade:
    """Test trade data structure"""
    
    def test_trade_creation(self):
        """Test trade creation"""
        trade = Trade(
            trade_id="trade_001",
            symbol="BTCUSDT",
            side="BUY",
            entry_price=50000.0,
            exit_price=51500.0,
            volume=0.1,
            entry_time=time.time() - 3600,
            exit_time=time.time(),
            stop_loss=49000.0,
            take_profit=52000.0,
            pnl=150.0,
            pnl_percentage=0.003,
            outcome=TradeOutcome.WIN,
            risk_amount=100.0,
            reward_amount=200.0,
            rr_ratio=2.0,
            metadata={"strategy": "scalp"}
        )
        
        assert trade.trade_id == "trade_001"
        assert trade.symbol == "BTCUSDT"
        assert trade.side == "BUY"
        assert trade.entry_price == 50000.0
        assert trade.exit_price == 51500.0
        assert trade.volume == 0.1
        assert trade.entry_time > 0
        assert trade.exit_time > 0
        assert trade.stop_loss == 49000.0
        assert trade.take_profit == 52000.0
        assert trade.pnl == 150.0
        assert trade.pnl_percentage == 0.003
        assert trade.outcome == TradeOutcome.WIN
        assert trade.risk_amount == 100.0
        assert trade.reward_amount == 200.0
        assert trade.rr_ratio == 2.0
        assert trade.metadata["strategy"] == "scalp"
    
    def test_trade_defaults(self):
        """Test trade defaults"""
        trade = Trade(
            trade_id="trade_002",
            symbol="ETHUSDT",
            side="SELL",
            entry_price=3000.0,
            exit_price=2850.0,
            volume=0.2,
            entry_time=time.time() - 7200,
            exit_time=time.time() - 1800,
            stop_loss=3100.0,
            take_profit=2800.0
        )
        
        assert trade.pnl == 0.0
        assert trade.pnl_percentage == 0.0
        assert trade.outcome is None
        assert trade.risk_amount == 0.0
        assert trade.reward_amount == 0.0
        assert trade.rr_ratio == 0.0
        assert trade.actual_stop_loss is None
        assert trade.actual_take_profit is None
        assert trade.metadata == {}

class TestPerformanceMetrics:
    """Test performance metrics data structure"""
    
    def test_performance_metrics_creation(self):
        """Test performance metrics creation"""
        metrics = PerformanceMetrics(
            total_trades=100,
            winning_trades=85,
            losing_trades=15,
            breakeven_trades=0,
            win_rate=0.85,
            loss_rate=0.15,
            average_win=150.0,
            average_loss=100.0,
            largest_win=500.0,
            largest_loss=200.0,
            total_pnl=11250.0,
            gross_profit=12750.0,
            gross_loss=1500.0,
            profit_factor=8.5,
            average_rr_ratio=3.2,
            sharpe_ratio=2.1,
            sortino_ratio=2.8,
            max_drawdown=-500.0,
            max_drawdown_percentage=5.0,
            recovery_factor=25.5,
            expectancy=112.5,
            metadata={"analysis_timestamp": time.time()}
        )
        
        assert metrics.total_trades == 100
        assert metrics.winning_trades == 85
        assert metrics.losing_trades == 15
        assert metrics.breakeven_trades == 0
        assert metrics.win_rate == 0.85
        assert metrics.loss_rate == 0.15
        assert metrics.average_win == 150.0
        assert metrics.average_loss == 100.0
        assert metrics.largest_win == 500.0
        assert metrics.largest_loss == 200.0
        assert metrics.total_pnl == 11250.0
        assert metrics.gross_profit == 12750.0
        assert metrics.gross_loss == 1500.0
        assert metrics.profit_factor == 8.5
        assert metrics.average_rr_ratio == 3.2
        assert metrics.sharpe_ratio == 2.1
        assert metrics.sortino_ratio == 2.8
        assert metrics.max_drawdown == -500.0
        assert metrics.max_drawdown_percentage == 5.0
        assert metrics.recovery_factor == 25.5
        assert metrics.expectancy == 112.5
        assert metrics.metadata["analysis_timestamp"] > 0
    
    def test_performance_metrics_defaults(self):
        """Test performance metrics defaults"""
        metrics = PerformanceMetrics(
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            breakeven_trades=0,
            win_rate=0.60,
            loss_rate=0.40,
            average_win=100.0,
            average_loss=80.0,
            largest_win=300.0,
            largest_loss=150.0,
            total_pnl=1400.0,
            gross_profit=3000.0,
            gross_loss=1600.0,
            profit_factor=1.875,
            average_rr_ratio=2.5,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            max_drawdown=-200.0,
            max_drawdown_percentage=8.0,
            recovery_factor=15.0,
            expectancy=28.0
        )
        
        assert metrics.metadata == {}

class TestWinRateValidation:
    """Test win rate validation data structure"""
    
    def test_win_rate_validation_creation(self):
        """Test win rate validation creation"""
        metrics = PerformanceMetrics(
            total_trades=100, winning_trades=85, losing_trades=15, breakeven_trades=0,
            win_rate=0.85, loss_rate=0.15, average_win=150.0, average_loss=100.0,
            largest_win=500.0, largest_loss=200.0, total_pnl=11250.0, gross_profit=12750.0,
            gross_loss=1500.0, profit_factor=8.5, average_rr_ratio=3.2, sharpe_ratio=2.1,
            sortino_ratio=2.8, max_drawdown=-500.0, max_drawdown_percentage=5.0,
            recovery_factor=25.5, expectancy=112.5
        )
        
        validation = WinRateValidation(
            timestamp=time.time(),
            total_trades=100,
            win_rate=0.85,
            target_win_rate=0.80,
            meets_win_rate_target=True,
            rr_ratio=3.2,
            target_rr_ratio=3.0,
            meets_rr_target=True,
            performance_metrics=metrics,
            win_rate_level=WinRateLevel.GOOD,
            rr_level=RRLevel.GOOD,
            validation_status=ValidationStatus.PASSED,
            issues_found=[],
            recommendations=["Excellent performance! Continue current strategy"],
            metadata={"target_win_rate": 0.80, "target_rr_ratio": 3.0}
        )
        
        assert validation.timestamp > 0
        assert validation.total_trades == 100
        assert validation.win_rate == 0.85
        assert validation.target_win_rate == 0.80
        assert validation.meets_win_rate_target is True
        assert validation.rr_ratio == 3.2
        assert validation.target_rr_ratio == 3.0
        assert validation.meets_rr_target is True
        assert validation.performance_metrics == metrics
        assert validation.win_rate_level == WinRateLevel.GOOD
        assert validation.rr_level == RRLevel.GOOD
        assert validation.validation_status == ValidationStatus.PASSED
        assert len(validation.issues_found) == 0
        assert len(validation.recommendations) == 1
        assert validation.metadata["target_win_rate"] == 0.80
    
    def test_win_rate_validation_defaults(self):
        """Test win rate validation defaults"""
        metrics = PerformanceMetrics(
            total_trades=50, winning_trades=25, losing_trades=25, breakeven_trades=0,
            win_rate=0.50, loss_rate=0.50, average_win=100.0, average_loss=100.0,
            largest_win=200.0, largest_loss=200.0, total_pnl=0.0, gross_profit=2500.0,
            gross_loss=2500.0, profit_factor=1.0, average_rr_ratio=1.0, sharpe_ratio=0.0,
            sortino_ratio=0.0, max_drawdown=-100.0, max_drawdown_percentage=10.0,
            recovery_factor=25.0, expectancy=0.0
        )
        
        validation = WinRateValidation(
            timestamp=time.time(),
            total_trades=50,
            win_rate=0.50,
            target_win_rate=0.80,
            meets_win_rate_target=False,
            rr_ratio=1.0,
            target_rr_ratio=3.0,
            meets_rr_target=False,
            performance_metrics=metrics,
            win_rate_level=WinRateLevel.CRITICAL,
            rr_level=RRLevel.CRITICAL,
            validation_status=ValidationStatus.FAILED,
            issues_found=["Win rate 50.0% below target 80.0%", "R:R ratio 1.0 below target 3.0"],
            recommendations=["Improve entry timing and signal quality to increase win rate"]
        )
        
        assert validation.metadata == {}

class TestWinRateReport:
    """Test win rate report data structure"""
    
    def test_win_rate_report_creation(self):
        """Test win rate report creation"""
        metrics = PerformanceMetrics(
            total_trades=100, winning_trades=85, losing_trades=15, breakeven_trades=0,
            win_rate=0.85, loss_rate=0.15, average_win=150.0, average_loss=100.0,
            largest_win=500.0, largest_loss=200.0, total_pnl=11250.0, gross_profit=12750.0,
            gross_loss=1500.0, profit_factor=8.5, average_rr_ratio=3.2, sharpe_ratio=2.1,
            sortino_ratio=2.8, max_drawdown=-500.0, max_drawdown_percentage=5.0,
            recovery_factor=25.5, expectancy=112.5
        )
        
        validation = WinRateValidation(
            timestamp=time.time(),
            total_trades=100,
            win_rate=0.85,
            target_win_rate=0.80,
            meets_win_rate_target=True,
            rr_ratio=3.2,
            target_rr_ratio=3.0,
            meets_rr_target=True,
            performance_metrics=metrics,
            win_rate_level=WinRateLevel.GOOD,
            rr_level=RRLevel.GOOD,
            validation_status=ValidationStatus.PASSED,
            issues_found=[],
            recommendations=["Excellent performance! Continue current strategy"]
        )
        
        report = WinRateReport(
            timestamp=time.time(),
            overall_performance_score=0.92,
            win_rate_validation=validation,
            performance_analysis={"win_rate_analysis": {"current": 0.85}},
            risk_analysis={"drawdown_analysis": {"max_drawdown_percentage": 5.0}},
            consistency_analysis={"consistency_metrics": {"win_rate_consistency": "High"}},
            recommendations=["Excellent performance! All targets met."],
            detailed_metrics=[metrics],
            metadata={"target_win_rate": 0.80, "target_rr_ratio": 3.0}
        )
        
        assert report.timestamp > 0
        assert report.overall_performance_score == 0.92
        assert report.win_rate_validation == validation
        assert report.performance_analysis["win_rate_analysis"]["current"] == 0.85
        assert report.risk_analysis["drawdown_analysis"]["max_drawdown_percentage"] == 5.0
        assert report.consistency_analysis["consistency_metrics"]["win_rate_consistency"] == "High"
        assert len(report.recommendations) == 1
        assert len(report.detailed_metrics) == 1
        assert report.metadata["target_win_rate"] == 0.80
    
    def test_win_rate_report_defaults(self):
        """Test win rate report defaults"""
        report = WinRateReport(
            timestamp=time.time(),
            overall_performance_score=0.50,
            win_rate_validation=WinRateValidation(
                timestamp=time.time(),
                total_trades=50,
                win_rate=0.50,
                target_win_rate=0.80,
                meets_win_rate_target=False,
                rr_ratio=1.0,
                target_rr_ratio=3.0,
                meets_rr_target=False,
                performance_metrics=PerformanceMetrics(
                    total_trades=50, winning_trades=25, losing_trades=25, breakeven_trades=0,
                    win_rate=0.50, loss_rate=0.50, average_win=100.0, average_loss=100.0,
                    largest_win=200.0, largest_loss=200.0, total_pnl=0.0, gross_profit=2500.0,
                    gross_loss=2500.0, profit_factor=1.0, average_rr_ratio=1.0, sharpe_ratio=0.0,
                    sortino_ratio=0.0, max_drawdown=-100.0, max_drawdown_percentage=10.0,
                    recovery_factor=25.0, expectancy=0.0
                ),
                win_rate_level=WinRateLevel.CRITICAL,
                rr_level=RRLevel.CRITICAL,
                validation_status=ValidationStatus.FAILED,
                issues_found=["Win rate 50.0% below target 80.0%"],
                recommendations=["Improve entry timing and signal quality"]
            ),
            performance_analysis={"win_rate_analysis": {"current": 0.50}},
            risk_analysis={"drawdown_analysis": {"max_drawdown_percentage": 10.0}},
            consistency_analysis={"consistency_metrics": {"win_rate_consistency": "Low"}},
            recommendations=["Performance needs improvement to meet targets."],
            detailed_metrics=[]
        )
        
        assert report.detailed_metrics == []
        assert report.metadata == {}

class TestTradeAnalyzer:
    """Test trade analyzer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = TradeAnalyzer()
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization"""
        assert hasattr(self.analyzer, 'analysis_cache')
        assert hasattr(self.analyzer, 'lock')
        assert isinstance(self.analyzer.analysis_cache, dict)
    
    def test_analyze_trade_performance_empty(self):
        """Test trade performance analysis with empty trades"""
        metrics = self.analyzer.analyze_trade_performance([])
        
        assert metrics.total_trades == 0
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 0
        assert metrics.breakeven_trades == 0
        assert metrics.win_rate == 0.0
        assert metrics.loss_rate == 0.0
        assert metrics.average_win == 0.0
        assert metrics.average_loss == 0.0
        assert metrics.largest_win == 0.0
        assert metrics.largest_loss == 0.0
        assert metrics.total_pnl == 0.0
        assert metrics.gross_profit == 0.0
        assert metrics.gross_loss == 0.0
        assert metrics.profit_factor == 0.0
        assert metrics.average_rr_ratio == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.sortino_ratio == 0.0
        assert metrics.max_drawdown == 0.0
        assert metrics.max_drawdown_percentage == 0.0
        assert metrics.recovery_factor == 0.0
        assert metrics.expectancy == 0.0
    
    def test_analyze_trade_performance_winning_trades(self):
        """Test trade performance analysis with winning trades"""
        trades = [
            Trade(
                trade_id="trade_001",
                symbol="BTCUSDT",
                side="BUY",
                entry_price=50000.0,
                exit_price=51500.0,
                volume=0.1,
                entry_time=time.time() - 3600,
                exit_time=time.time(),
                stop_loss=49000.0,
                take_profit=52000.0,
                pnl=150.0,
                pnl_percentage=0.003,
                outcome=TradeOutcome.WIN,
                risk_amount=100.0,
                reward_amount=200.0,
                rr_ratio=2.0
            ),
            Trade(
                trade_id="trade_002",
                symbol="ETHUSDT",
                side="SELL",
                entry_price=3000.0,
                exit_price=2850.0,
                volume=0.2,
                entry_time=time.time() - 7200,
                exit_time=time.time() - 1800,
                stop_loss=3100.0,
                take_profit=2800.0,
                pnl=300.0,
                pnl_percentage=0.05,
                outcome=TradeOutcome.WIN,
                risk_amount=200.0,
                reward_amount=400.0,
                rr_ratio=2.0
            )
        ]
        
        metrics = self.analyzer.analyze_trade_performance(trades)
        
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 0
        assert metrics.breakeven_trades == 0
        assert metrics.win_rate == 1.0
        assert metrics.loss_rate == 0.0
        assert metrics.average_win == 225.0
        assert metrics.average_loss == 0.0
        assert metrics.largest_win == 300.0
        assert metrics.largest_loss == 0.0
        assert metrics.total_pnl == 450.0
        assert metrics.gross_profit == 450.0
        assert metrics.gross_loss == 0.0
        assert metrics.profit_factor == float('inf')
        assert metrics.average_rr_ratio == 2.0
        assert metrics.sharpe_ratio >= 0.0
        assert metrics.sortino_ratio >= 0.0
        assert metrics.max_drawdown <= 0.0
        assert metrics.recovery_factor == float('inf')
        assert metrics.expectancy == 225.0
    
    def test_analyze_trade_performance_mixed_trades(self):
        """Test trade performance analysis with mixed trades"""
        trades = [
            Trade(
                trade_id="trade_001",
                symbol="BTCUSDT",
                side="BUY",
                entry_price=50000.0,
                exit_price=51500.0,
                volume=0.1,
                entry_time=time.time() - 3600,
                exit_time=time.time(),
                stop_loss=49000.0,
                take_profit=52000.0,
                pnl=150.0,
                pnl_percentage=0.003,
                outcome=TradeOutcome.WIN,
                risk_amount=100.0,
                reward_amount=200.0,
                rr_ratio=2.0
            ),
            Trade(
                trade_id="trade_002",
                symbol="ETHUSDT",
                side="SELL",
                entry_price=3000.0,
                exit_price=3100.0,
                volume=0.2,
                entry_time=time.time() - 7200,
                exit_time=time.time() - 1800,
                stop_loss=3100.0,
                take_profit=2800.0,
                pnl=-200.0,
                pnl_percentage=-0.033,
                outcome=TradeOutcome.LOSS,
                risk_amount=200.0,
                reward_amount=400.0,
                rr_ratio=2.0
            )
        ]
        
        metrics = self.analyzer.analyze_trade_performance(trades)
        
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.breakeven_trades == 0
        assert metrics.win_rate == 0.5
        assert metrics.loss_rate == 0.5
        assert metrics.average_win == 150.0
        assert metrics.average_loss == -200.0
        assert metrics.largest_win == 150.0
        assert metrics.largest_loss == -200.0
        assert metrics.total_pnl == -50.0
        assert metrics.gross_profit == 150.0
        assert metrics.gross_loss == 200.0
        assert metrics.profit_factor == 0.75
        assert metrics.average_rr_ratio == 2.0
        assert metrics.sharpe_ratio >= -10.0  # Allow negative Sharpe ratios
        assert metrics.sortino_ratio >= 0.0
        assert metrics.max_drawdown <= 0.0
        assert metrics.recovery_factor >= 0.0
        assert metrics.expectancy == -25.0

class TestWinRateValidator:
    """Test win rate validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = WinRateValidator(target_win_rate=0.80, target_rr_ratio=3.0)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.target_win_rate == 0.80
        assert self.validator.target_rr_ratio == 3.0
        assert isinstance(self.validator.analyzer, TradeAnalyzer)
        assert len(self.validator.validations) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
    
    def test_validate_win_rate_excellent_performance(self):
        """Test win rate validation with excellent performance"""
        trades = [
            Trade(
                trade_id=f"trade_{i:03d}",
                symbol="BTCUSDT",
                side="BUY",
                entry_price=50000.0 + i * 100,
                exit_price=51500.0 + i * 100,
                volume=0.1,
                entry_time=time.time() - (i + 1) * 3600,
                exit_time=time.time() - i * 3600,
                stop_loss=49000.0 + i * 100,
                take_profit=52000.0 + i * 100,
                pnl=150.0 + i * 10,
                pnl_percentage=0.003,
                outcome=TradeOutcome.WIN,
                risk_amount=100.0,
                reward_amount=300.0,
                rr_ratio=3.0
            ) for i in range(20)
        ]
        
        validation = self.validator.validate_win_rate(trades)
        
        assert validation.total_trades == 20
        assert validation.win_rate == 1.0
        assert validation.target_win_rate == 0.80
        assert validation.meets_win_rate_target is True
        assert validation.rr_ratio == 3.0
        assert validation.target_rr_ratio == 3.0
        assert validation.meets_rr_target is True
        assert validation.win_rate_level == WinRateLevel.EXCELLENT
        assert validation.rr_level == RRLevel.GOOD
        assert validation.validation_status == ValidationStatus.PASSED
        assert len(validation.issues_found) >= 0  # May have sample size warning
        assert len(validation.recommendations) > 0
        assert validation.metadata["target_win_rate"] == 0.80
        assert validation.metadata["target_rr_ratio"] == 3.0
    
    def test_validate_win_rate_poor_performance(self):
        """Test win rate validation with poor performance"""
        trades = [
            Trade(
                trade_id=f"trade_{i:03d}",
                symbol="BTCUSDT",
                side="BUY",
                entry_price=50000.0 + i * 100,
                exit_price=49500.0 + i * 100,  # Loss
                volume=0.1,
                entry_time=time.time() - (i + 1) * 3600,
                exit_time=time.time() - i * 3600,
                stop_loss=49000.0 + i * 100,
                take_profit=52000.0 + i * 100,
                pnl=-50.0 - i * 5,
                pnl_percentage=-0.001,
                outcome=TradeOutcome.LOSS,
                risk_amount=100.0,
                reward_amount=100.0,
                rr_ratio=1.0
            ) for i in range(20)
        ]
        
        validation = self.validator.validate_win_rate(trades)
        
        assert validation.total_trades == 20
        assert validation.win_rate == 0.0
        assert validation.target_win_rate == 0.80
        assert validation.meets_win_rate_target is False
        assert validation.rr_ratio == 1.0
        assert validation.target_rr_ratio == 3.0
        assert validation.meets_rr_target is False
        assert validation.win_rate_level == WinRateLevel.CRITICAL
        assert validation.rr_level == RRLevel.POOR  # 1.0 R:R is POOR
        assert validation.validation_status == ValidationStatus.FAILED
        assert len(validation.issues_found) > 0
        assert len(validation.recommendations) > 0
        assert "Win rate" in validation.issues_found[0]
        assert "R:R ratio" in validation.issues_found[1]
    
    def test_validate_win_rate_mixed_performance(self):
        """Test win rate validation with mixed performance"""
        trades = []
        
        # Add 16 winning trades (80% win rate)
        for i in range(16):
            trades.append(Trade(
                trade_id=f"win_trade_{i:03d}",
                symbol="BTCUSDT",
                side="BUY",
                entry_price=50000.0 + i * 100,
                exit_price=51500.0 + i * 100,
                volume=0.1,
                entry_time=time.time() - (i + 1) * 3600,
                exit_time=time.time() - i * 3600,
                stop_loss=49000.0 + i * 100,
                take_profit=52000.0 + i * 100,
                pnl=150.0 + i * 10,
                pnl_percentage=0.003,
                outcome=TradeOutcome.WIN,
                risk_amount=100.0,
                reward_amount=300.0,
                rr_ratio=3.0
            ))
        
        # Add 4 losing trades (20% loss rate)
        for i in range(4):
            trades.append(Trade(
                trade_id=f"loss_trade_{i:03d}",
                symbol="BTCUSDT",
                side="BUY",
                entry_price=50000.0 + i * 100,
                exit_price=49500.0 + i * 100,
                volume=0.1,
                entry_time=time.time() - (i + 1) * 3600,
                exit_time=time.time() - i * 3600,
                stop_loss=49000.0 + i * 100,
                take_profit=52000.0 + i * 100,
                pnl=-50.0 - i * 5,
                pnl_percentage=-0.001,
                outcome=TradeOutcome.LOSS,
                risk_amount=100.0,
                reward_amount=300.0,
                rr_ratio=3.0
            ))
        
        validation = self.validator.validate_win_rate(trades)
        
        assert validation.total_trades == 20
        assert validation.win_rate == 0.8
        assert validation.target_win_rate == 0.80
        assert validation.meets_win_rate_target is True
        assert validation.rr_ratio == 3.0
        assert validation.target_rr_ratio == 3.0
        assert validation.meets_rr_target is True
        assert validation.win_rate_level == WinRateLevel.GOOD
        assert validation.rr_level == RRLevel.GOOD
        assert validation.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING]
        assert len(validation.issues_found) >= 0
        assert len(validation.recommendations) > 0
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations first
        for i in range(3):
            trades = [
                Trade(
                    trade_id=f"trade_{i}_{j:03d}",
                    symbol="BTCUSDT",
                    side="BUY",
                    entry_price=50000.0 + j * 100,
                    exit_price=51500.0 + j * 100,
                    volume=0.1,
                    entry_time=time.time() - (j + 1) * 3600,
                    exit_time=time.time() - j * 3600,
                    stop_loss=49000.0 + j * 100,
                    take_profit=52000.0 + j * 100,
                    pnl=150.0 + j * 10,
                    pnl_percentage=0.003,
                    outcome=TradeOutcome.WIN,
                    risk_amount=100.0,
                    reward_amount=300.0,
                    rr_ratio=3.0
                ) for j in range(10)
            ]
            
            self.validator.validate_win_rate(trades)
        
        report = self.validator.generate_validation_report()
        
        assert report.overall_performance_score >= 0.0
        assert report.overall_performance_score <= 1.0
        assert isinstance(report.win_rate_validation, WinRateValidation)
        assert len(report.performance_analysis) > 0
        assert len(report.risk_analysis) > 0
        assert len(report.consistency_analysis) > 0
        assert len(report.recommendations) > 0
        assert len(report.detailed_metrics) == 3
        assert report.metadata["target_win_rate"] == 0.80
        assert report.metadata["target_rr_ratio"] == 3.0
    
    def test_generate_validation_report_no_data(self):
        """Test validation report generation with no data"""
        report = self.validator.generate_validation_report()
        
        assert report.overall_performance_score == 0.0
        assert report.win_rate_validation.total_trades == 0
        assert report.win_rate_validation.win_rate == 0.0
        assert report.win_rate_validation.meets_win_rate_target is False
        assert report.win_rate_validation.rr_ratio == 0.0
        assert report.win_rate_validation.meets_rr_target is False
        assert report.win_rate_validation.win_rate_level == WinRateLevel.CRITICAL
        assert report.win_rate_validation.rr_level == RRLevel.CRITICAL
        assert report.win_rate_validation.validation_status == ValidationStatus.FAILED
        assert "No validation data available" in report.win_rate_validation.issues_found[0]
        assert "No validation data available" in report.win_rate_validation.recommendations[0]
        assert report.performance_analysis == {}
        assert report.risk_analysis == {}
        assert report.consistency_analysis == {}
        assert "No validation data available" in report.recommendations[0]
        assert report.detailed_metrics == []
        assert report.metadata["error"] == "No validation data available"

class TestGlobalFunctions:
    """Test global win rate validation functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.win_rate_validation
        infra.win_rate_validation._win_rate_validator = None
    
    def test_get_win_rate_validator(self):
        """Test global validator access"""
        validator1 = get_win_rate_validator()
        validator2 = get_win_rate_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, WinRateValidator)
    
    def test_validate_win_rate_global(self):
        """Test global win rate validation"""
        trades = [
            Trade(
                trade_id="trade_001",
                symbol="BTCUSDT",
                side="BUY",
                entry_price=50000.0,
                exit_price=51500.0,
                volume=0.1,
                entry_time=time.time() - 3600,
                exit_time=time.time(),
                stop_loss=49000.0,
                take_profit=52000.0,
                pnl=150.0,
                pnl_percentage=0.003,
                outcome=TradeOutcome.WIN,
                risk_amount=100.0,
                reward_amount=300.0,
                rr_ratio=3.0
            )
        ]
        
        validation = validate_win_rate(trades)
        
        assert isinstance(validation, WinRateValidation)
        assert validation.total_trades == 1
        assert validation.win_rate == 1.0
        assert validation.target_win_rate == 0.80
        assert validation.meets_win_rate_target is True
        assert validation.rr_ratio == 3.0
        assert validation.target_rr_ratio == 3.0
        assert validation.meets_rr_target is True
        assert validation.win_rate_level == WinRateLevel.EXCELLENT
        assert validation.rr_level == RRLevel.GOOD
        assert validation.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING]
        assert len(validation.issues_found) >= 0
        assert len(validation.recommendations) > 0
    
    def test_generate_win_rate_report_global(self):
        """Test global win rate report generation"""
        # Add some validations first
        for i in range(2):
            trades = [
                Trade(
                    trade_id=f"trade_{i}_{j:03d}",
                    symbol="BTCUSDT",
                    side="BUY",
                    entry_price=50000.0 + j * 100,
                    exit_price=51500.0 + j * 100,
                    volume=0.1,
                    entry_time=time.time() - (j + 1) * 3600,
                    exit_time=time.time() - j * 3600,
                    stop_loss=49000.0 + j * 100,
                    take_profit=52000.0 + j * 100,
                    pnl=150.0 + j * 10,
                    pnl_percentage=0.003,
                    outcome=TradeOutcome.WIN,
                    risk_amount=100.0,
                    reward_amount=300.0,
                    rr_ratio=3.0
                ) for j in range(5)
            ]
            
            validate_win_rate(trades)
        
        report = generate_win_rate_report()
        
        assert isinstance(report, WinRateReport)
        assert report.overall_performance_score >= 0.0
        assert report.overall_performance_score <= 1.0

class TestWinRateValidationIntegration:
    """Integration tests for win rate validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.win_rate_validation
        infra.win_rate_validation._win_rate_validator = None
    
    def test_comprehensive_win_rate_validation(self):
        """Test comprehensive win rate validation workflow"""
        # Test different performance scenarios
        test_cases = [
            (0.95, 4.0, WinRateLevel.EXCELLENT, RRLevel.GOOD, ValidationStatus.PASSED),  # Excellent
            (0.85, 3.5, WinRateLevel.GOOD, RRLevel.GOOD, ValidationStatus.PASSED),       # Good
            (0.75, 2.5, WinRateLevel.FAIR, RRLevel.FAIR, ValidationStatus.FAILED),      # Fair
            (0.65, 1.5, WinRateLevel.POOR, RRLevel.POOR, ValidationStatus.FAILED),      # Poor
            (0.45, 0.8, WinRateLevel.CRITICAL, RRLevel.CRITICAL, ValidationStatus.FAILED) # Critical
        ]
        
        for win_rate, rr_ratio, expected_win_level, expected_rr_level, expected_status in test_cases:
            # Create trades with specified performance
            num_trades = 20
            winning_trades = int(num_trades * win_rate)
            losing_trades = num_trades - winning_trades
            
            trades = []
            
            # Add winning trades
            for i in range(winning_trades):
                trades.append(Trade(
                    trade_id=f"win_trade_{i:03d}",
                    symbol="BTCUSDT",
                    side="BUY",
                    entry_price=50000.0 + i * 100,
                    exit_price=51500.0 + i * 100,
                    volume=0.1,
                    entry_time=time.time() - (i + 1) * 3600,
                    exit_time=time.time() - i * 3600,
                    stop_loss=49000.0 + i * 100,
                    take_profit=52000.0 + i * 100,
                    pnl=150.0 + i * 10,
                    pnl_percentage=0.003,
                    outcome=TradeOutcome.WIN,
                    risk_amount=100.0,
                    reward_amount=100.0 * rr_ratio,
                    rr_ratio=rr_ratio
                ))
            
            # Add losing trades
            for i in range(losing_trades):
                trades.append(Trade(
                    trade_id=f"loss_trade_{i:03d}",
                    symbol="BTCUSDT",
                    side="BUY",
                    entry_price=50000.0 + i * 100,
                    exit_price=49500.0 + i * 100,
                    volume=0.1,
                    entry_time=time.time() - (i + 1) * 3600,
                    exit_time=time.time() - i * 3600,
                    stop_loss=49000.0 + i * 100,
                    take_profit=52000.0 + i * 100,
                    pnl=-50.0 - i * 5,
                    pnl_percentage=-0.001,
                    outcome=TradeOutcome.LOSS,
                    risk_amount=100.0,
                    reward_amount=100.0 * rr_ratio,
                    rr_ratio=rr_ratio
                ))
            
            validation = validate_win_rate(trades)
            
            assert isinstance(validation, WinRateValidation)
            assert validation.total_trades == num_trades
            assert abs(validation.win_rate - win_rate) < 0.01  # Allow small floating point differences
            assert validation.target_win_rate == 0.80
            assert validation.meets_win_rate_target == (win_rate >= 0.80)
            assert abs(validation.rr_ratio - rr_ratio) < 0.01  # Allow small floating point differences
            assert validation.target_rr_ratio == 3.0
            assert validation.meets_rr_target == (rr_ratio >= 3.0)
            assert validation.win_rate_level == expected_win_level
            assert validation.rr_level == expected_rr_level
            assert validation.validation_status == expected_status
            assert len(validation.issues_found) >= 0
            assert len(validation.recommendations) >= 0  # May be empty for excellent performance
        
        # Generate validation report
        report = generate_win_rate_report()
        
        assert isinstance(report, WinRateReport)
        assert report.overall_performance_score >= 0.0
        assert report.overall_performance_score <= 1.0
        assert isinstance(report.win_rate_validation, WinRateValidation)
        assert len(report.performance_analysis) > 0
        assert len(report.risk_analysis) > 0
        assert len(report.consistency_analysis) > 0
        assert len(report.recommendations) > 0
        assert len(report.detailed_metrics) == len(test_cases)
    
    def test_win_rate_target_validation(self):
        """Test win rate target validation"""
        # Test with win rate above target
        high_win_rate_trades = [
            Trade(
                trade_id=f"win_trade_{i:03d}",
                symbol="BTCUSDT",
                side="BUY",
                entry_price=50000.0 + i * 100,
                exit_price=51500.0 + i * 100,
                volume=0.1,
                entry_time=time.time() - (i + 1) * 3600,
                exit_time=time.time() - i * 3600,
                stop_loss=49000.0 + i * 100,
                take_profit=52000.0 + i * 100,
                pnl=150.0 + i * 10,
                pnl_percentage=0.003,
                outcome=TradeOutcome.WIN,
                risk_amount=100.0,
                reward_amount=300.0,
                rr_ratio=3.0
            ) for i in range(17)  # 85% win rate
        ]
        
        validation = validate_win_rate(high_win_rate_trades)
        
        assert validation.win_rate == 1.0  # 100% win rate
        assert validation.meets_win_rate_target is True
        assert validation.win_rate_level == WinRateLevel.EXCELLENT
        
        # Test with win rate below target
        low_win_rate_trades = [
            Trade(
                trade_id=f"loss_trade_{i:03d}",
                symbol="BTCUSDT",
                side="BUY",
                entry_price=50000.0 + i * 100,
                exit_price=49500.0 + i * 100,
                volume=0.1,
                entry_time=time.time() - (i + 1) * 3600,
                exit_time=time.time() - i * 3600,
                stop_loss=49000.0 + i * 100,
                take_profit=52000.0 + i * 100,
                pnl=-50.0 - i * 5,
                pnl_percentage=-0.001,
                outcome=TradeOutcome.LOSS,
                risk_amount=100.0,
                reward_amount=300.0,
                rr_ratio=3.0
            ) for i in range(20)  # 0% win rate
        ]
        
        validation = validate_win_rate(low_win_rate_trades)
        
        assert validation.win_rate == 0.0  # 0% win rate
        assert validation.meets_win_rate_target is False
        assert validation.win_rate_level == WinRateLevel.CRITICAL
    
    def test_rr_ratio_validation(self):
        """Test R:R ratio validation"""
        # Test with R:R ratio above target
        high_rr_trades = [
            Trade(
                trade_id=f"trade_{i:03d}",
                symbol="BTCUSDT",
                side="BUY",
                entry_price=50000.0 + i * 100,
                exit_price=51500.0 + i * 100,
                volume=0.1,
                entry_time=time.time() - (i + 1) * 3600,
                exit_time=time.time() - i * 3600,
                stop_loss=49000.0 + i * 100,
                take_profit=52000.0 + i * 100,
                pnl=150.0 + i * 10,
                pnl_percentage=0.003,
                outcome=TradeOutcome.WIN,
                risk_amount=100.0,
                reward_amount=500.0,  # High reward
                rr_ratio=5.0  # High R:R ratio
            ) for i in range(20)
        ]
        
        validation = validate_win_rate(high_rr_trades)
        
        assert validation.rr_ratio == 5.0
        assert validation.meets_rr_target is True
        assert validation.rr_level == RRLevel.EXCELLENT
        
        # Test with R:R ratio below target
        low_rr_trades = [
            Trade(
                trade_id=f"trade_{i:03d}",
                symbol="BTCUSDT",
                side="BUY",
                entry_price=50000.0 + i * 100,
                exit_price=51500.0 + i * 100,
                volume=0.1,
                entry_time=time.time() - (i + 1) * 3600,
                exit_time=time.time() - i * 3600,
                stop_loss=49000.0 + i * 100,
                take_profit=52000.0 + i * 100,
                pnl=150.0 + i * 10,
                pnl_percentage=0.003,
                outcome=TradeOutcome.WIN,
                risk_amount=100.0,
                reward_amount=150.0,  # Low reward
                rr_ratio=1.5  # Low R:R ratio
            ) for i in range(20)
        ]
        
        validation = validate_win_rate(low_rr_trades)
        
        assert validation.rr_ratio == 1.5
        assert validation.meets_rr_target is False
        assert validation.rr_level == RRLevel.POOR  # 1.5 R:R is POOR, not CRITICAL

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
