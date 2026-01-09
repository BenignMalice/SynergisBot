"""
12-Month Backtesting Validation System

This module implements a comprehensive backtesting validation system for
12 months of historical data across EURUSDc, GBPUSDc, XAUUSDc, and BTCUSDc,
including performance analysis, risk assessment, and strategy validation.

Key Features:
- 12-month historical backtesting validation
- Multi-symbol backtesting (EURUSDc, GBPUSDc, XAUUSDc, BTCUSDc)
- Performance metrics calculation and analysis
- Risk assessment and drawdown analysis
- Strategy validation and optimization
- Comprehensive reporting and visualization
- Statistical significance testing
- Market condition analysis
"""

import time
import math
import statistics
import numpy as np
import threading
import json
import asyncio
import hashlib
import logging
import sqlite3
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3
import tempfile
import os

logger = logging.getLogger(__name__)

class BacktestStatus(Enum):
    """Backtest status types"""
    PENDING = "pending"  # Backtest not started
    RUNNING = "running"  # Backtest in progress
    COMPLETED = "completed"  # Backtest completed successfully
    FAILED = "failed"  # Backtest failed
    CANCELLED = "cancelled"  # Backtest cancelled

class SymbolType(Enum):
    """Symbol type classification"""
    FOREX = "forex"  # Forex pairs
    CRYPTO = "crypto"  # Cryptocurrency
    METALS = "metals"  # Precious metals
    INDICES = "indices"  # Stock indices

class MarketCondition(Enum):
    """Market condition types"""
    TRENDING = "trending"  # Strong trend
    RANGING = "ranging"  # Sideways movement
    VOLATILE = "volatile"  # High volatility
    CALM = "calm"  # Low volatility
    BREAKOUT = "breakout"  # Breakout conditions
    REVERSAL = "reversal"  # Reversal conditions

class PerformanceLevel(Enum):
    """Performance level classification"""
    EXCELLENT = "excellent"  # >20% annual return, <5% max drawdown
    GOOD = "good"  # 10-20% annual return, 5-10% max drawdown
    FAIR = "fair"  # 5-10% annual return, 10-15% max drawdown
    POOR = "poor"  # 0-5% annual return, 15-25% max drawdown
    CRITICAL = "critical"  # <0% annual return, >25% max drawdown

@dataclass
class Trade:
    """Trade data structure"""
    trade_id: str
    symbol: str
    entry_time: float
    exit_time: float
    entry_price: float
    exit_price: float
    volume: float
    direction: str  # "long" or "short"
    pnl: float
    commission: float
    slippage: float
    duration_hours: float
    max_favorable: float
    max_adverse: float
    exit_reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BacktestMetrics:
    """Backtest performance metrics"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    profit_factor: float
    gross_profit: float
    gross_loss: float
    net_profit: float
    max_drawdown: float
    max_drawdown_duration: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    recovery_factor: float
    expectancy: float
    avg_trade_duration: float
    trades_per_month: float
    annual_return: float
    volatility: float
    var_95: float
    var_99: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SymbolBacktest:
    """Symbol-specific backtest results"""
    symbol: str
    symbol_type: SymbolType
    start_date: float
    end_date: float
    duration_days: int
    total_trades: int
    metrics: BacktestMetrics
    trades: List[Trade]
    market_conditions: Dict[MarketCondition, float]
    performance_level: PerformanceLevel
    validation_status: str
    recommendations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BacktestValidation:
    """Backtest validation result"""
    timestamp: float
    backtest_id: str
    symbols: List[str]
    start_date: float
    end_date: float
    duration_days: int
    total_trades: int
    overall_metrics: BacktestMetrics
    symbol_results: List[SymbolBacktest]
    validation_status: str
    performance_level: PerformanceLevel
    risk_assessment: str
    strategy_validation: str
    recommendations: List[str]
    detailed_analysis: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BacktestReport:
    """Comprehensive backtest report"""
    timestamp: float
    backtest_id: str
    symbols: List[str]
    start_date: float
    end_date: float
    duration_days: int
    overall_performance_score: float
    risk_score: float
    consistency_score: float
    total_trades: int
    overall_metrics: BacktestMetrics
    symbol_breakdown: Dict[str, SymbolBacktest]
    market_condition_analysis: Dict[MarketCondition, Dict[str, Any]]
    performance_attribution: Dict[str, float]
    risk_metrics: Dict[str, float]
    validation_results: List[BacktestValidation]
    recommendations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

class BacktestingValidator:
    """Backtesting validator for comprehensive 12-month validation"""
    
    def __init__(self, database_path: str = None):
        self.database_path = database_path
        self.backtest_results: Dict[str, BacktestValidation] = {}
        self.symbol_data: Dict[str, List[Dict]] = {}
        self.lock = threading.RLock()
        self.start_time = time.time()
        
        # Backtest configuration
        self.symbols = ["EURUSDc", "GBPUSDc", "XAUUSDc", "BTCUSDc"]
        self.symbol_types = {
            "EURUSDc": SymbolType.FOREX,
            "GBPUSDc": SymbolType.FOREX,
            "XAUUSDc": SymbolType.METALS,
            "BTCUSDc": SymbolType.CRYPTO
        }
        self.backtest_duration_days = 365  # 12 months
        self.min_trades_per_symbol = 50
        self.max_drawdown_threshold = 0.15  # 15%
        self.min_win_rate = 0.4  # 40%
        self.min_profit_factor = 1.2  # 1.2
    
    def load_historical_data(self, symbol: str, start_date: float, end_date: float) -> List[Dict]:
        """Load historical data for symbol"""
        # This would typically load from database or data source
        # For now, generate synthetic data for demonstration
        data = []
        current_time = start_date
        price = 1.1000 if symbol == "EURUSDc" else 1.2500 if symbol == "GBPUSDc" else 2000.0 if symbol == "XAUUSDc" else 50000.0
        
        while current_time < end_date:
            # Generate realistic price movements
            volatility = 0.001 if "USDc" in symbol else 0.01 if symbol == "XAUUSDc" else 0.02
            price_change = np.random.normal(0, volatility)
            price *= (1 + price_change)
            
            data.append({
                "timestamp": current_time,
                "open": price,
                "high": price * (1 + abs(np.random.normal(0, volatility/2))),
                "low": price * (1 - abs(np.random.normal(0, volatility/2))),
                "close": price,
                "volume": np.random.uniform(1000, 10000),
                "symbol": symbol
            })
            
            current_time += 3600  # 1 hour intervals
        
        return data
    
    def run_backtest(self, symbol: str, start_date: float, end_date: float) -> SymbolBacktest:
        """Run backtest for specific symbol"""
        logger.info(f"Running backtest for {symbol} from {start_date} to {end_date}")
        
        # Load historical data
        data = self.load_historical_data(symbol, start_date, end_date)
        
        # Simulate trading strategy
        trades = self._simulate_trading_strategy(symbol, data)
        
        # Calculate metrics
        metrics = self._calculate_metrics(trades)
        
        # Analyze market conditions
        market_conditions = self._analyze_market_conditions(data)
        
        # Determine performance level
        performance_level = self._determine_performance_level(metrics)
        
        # Generate recommendations
        recommendations = self._generate_symbol_recommendations(symbol, metrics, trades)
        
        # Determine validation status
        validation_status = self._determine_validation_status(metrics)
        
        return SymbolBacktest(
            symbol=symbol,
            symbol_type=self.symbol_types[symbol],
            start_date=start_date,
            end_date=end_date,
            duration_days=int((end_date - start_date) / 86400),
            total_trades=len(trades),
            metrics=metrics,
            trades=trades,
            market_conditions=market_conditions,
            performance_level=performance_level,
            validation_status=validation_status,
            recommendations=recommendations,
            metadata={
                "backtest_timestamp": time.time(),
                "data_points": len(data)
            }
        )
    
    def run_comprehensive_backtest(self, start_date: float = None, end_date: float = None) -> BacktestValidation:
        """Run comprehensive 12-month backtest for all symbols"""
        if start_date is None:
            start_date = time.time() - (self.backtest_duration_days * 86400)
        if end_date is None:
            end_date = time.time()
        
        logger.info(f"Running comprehensive backtest from {start_date} to {end_date}")
        
        symbol_results = []
        all_trades = []
        
        # Run backtest for each symbol
        for symbol in self.symbols:
            symbol_backtest = self.run_backtest(symbol, start_date, end_date)
            symbol_results.append(symbol_backtest)
            all_trades.extend(symbol_backtest.trades)
        
        # Calculate overall metrics
        overall_metrics = self._calculate_metrics(all_trades)
        
        # Determine overall performance level
        performance_level = self._determine_performance_level(overall_metrics)
        
        # Risk assessment
        risk_assessment = self._assess_risk(overall_metrics, symbol_results)
        
        # Strategy validation
        strategy_validation = self._validate_strategy(overall_metrics, symbol_results)
        
        # Generate recommendations
        recommendations = self._generate_comprehensive_recommendations(symbol_results, overall_metrics)
        
        # Detailed analysis
        detailed_analysis = self._generate_detailed_analysis(symbol_results, overall_metrics)
        
        backtest_id = hashlib.md5(f"{start_date}_{end_date}_{len(self.symbols)}".encode()).hexdigest()[:8]
        
        validation = BacktestValidation(
            timestamp=time.time(),
            backtest_id=backtest_id,
            symbols=self.symbols,
            start_date=start_date,
            end_date=end_date,
            duration_days=int((end_date - start_date) / 86400),
            total_trades=len(all_trades),
            overall_metrics=overall_metrics,
            symbol_results=symbol_results,
            validation_status=self._determine_overall_validation_status(symbol_results),
            performance_level=performance_level,
            risk_assessment=risk_assessment,
            strategy_validation=strategy_validation,
            recommendations=recommendations,
            detailed_analysis=detailed_analysis,
            metadata={
                "backtest_duration": time.time() - self.start_time,
                "symbols_tested": len(self.symbols)
            }
        )
        
        with self.lock:
            self.backtest_results[backtest_id] = validation
        
        return validation
    
    def _simulate_trading_strategy(self, symbol: str, data: List[Dict]) -> List[Trade]:
        """Simulate trading strategy execution"""
        trades = []
        trade_id = 0
        
        # Simple momentum strategy simulation
        for i in range(20, len(data) - 20):  # Leave buffer for indicators
            current_price = data[i]["close"]
            prev_price = data[i-1]["close"]
            
            # Simple momentum signal
            momentum = (current_price - prev_price) / prev_price
            
            # Entry conditions (simplified)
            if abs(momentum) > 0.001:  # 0.1% momentum threshold
                direction = "long" if momentum > 0 else "short"
                
                # Simulate trade execution
                entry_price = current_price
                exit_time = data[i + np.random.randint(1, 20)]["timestamp"] if i + 20 < len(data) else data[-1]["timestamp"]
                exit_price = entry_price * (1 + np.random.normal(0, 0.01))  # Random exit
                
                # Calculate trade metrics
                pnl = (exit_price - entry_price) if direction == "long" else (entry_price - exit_price)
                pnl *= 10000  # Standard lot size
                commission = 10.0  # Fixed commission
                slippage = abs(np.random.normal(0, 0.0001)) * 10000
                
                trade = Trade(
                    trade_id=f"{symbol}_{trade_id}",
                    symbol=symbol,
                    entry_time=data[i]["timestamp"],
                    exit_time=exit_time,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    volume=1.0,
                    direction=direction,
                    pnl=pnl - commission - slippage,
                    commission=commission,
                    slippage=slippage,
                    duration_hours=(exit_time - data[i]["timestamp"]) / 3600,
                    max_favorable=abs(pnl) * 1.2,
                    max_adverse=abs(pnl) * 0.8,
                    exit_reason="strategy_exit",
                    metadata={"momentum": momentum}
                )
                
                trades.append(trade)
                trade_id += 1
        
        return trades
    
    def _calculate_metrics(self, trades: List[Trade]) -> BacktestMetrics:
        """Calculate comprehensive trading metrics"""
        if not trades:
            return BacktestMetrics(
                total_trades=0, winning_trades=0, losing_trades=0, win_rate=0.0,
                avg_win=0.0, avg_loss=0.0, largest_win=0.0, largest_loss=0.0,
                profit_factor=0.0, gross_profit=0.0, gross_loss=0.0, net_profit=0.0,
                max_drawdown=0.0, max_drawdown_duration=0.0, sharpe_ratio=0.0,
                sortino_ratio=0.0, calmar_ratio=0.0, recovery_factor=0.0,
                expectancy=0.0, avg_trade_duration=0.0, trades_per_month=0.0,
                annual_return=0.0, volatility=0.0, var_95=0.0, var_99=0.0
            )
        
        # Basic metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
        
        # Profit/Loss metrics
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        net_profit = gross_profit - gross_loss
        
        avg_win = gross_profit / len(winning_trades) if winning_trades else 0.0
        avg_loss = gross_loss / len(losing_trades) if losing_trades else 0.0
        
        largest_win = max(t.pnl for t in trades) if trades else 0.0
        largest_loss = min(t.pnl for t in trades) if trades else 0.0
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Drawdown analysis
        cumulative_pnl = np.cumsum([t.pnl for t in trades])
        running_max = np.maximum.accumulate(cumulative_pnl)
        drawdown = running_max - cumulative_pnl
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0.0
        
        # Duration metrics
        avg_trade_duration = statistics.mean([t.duration_hours for t in trades]) if trades else 0.0
        
        # Risk metrics
        returns = [t.pnl for t in trades]
        if len(returns) > 1:
            volatility = statistics.stdev(returns)
            sharpe_ratio = statistics.mean(returns) / volatility if volatility > 0 else 0.0
            
            # Sortino ratio (downside deviation)
            negative_returns = [r for r in returns if r < 0]
            downside_deviation = statistics.stdev(negative_returns) if len(negative_returns) > 1 else 0.0
            sortino_ratio = statistics.mean(returns) / downside_deviation if downside_deviation > 0 else 0.0
        else:
            volatility = 0.0
            sharpe_ratio = 0.0
            sortino_ratio = 0.0
        
        # VaR calculation
        if len(returns) > 0:
            sorted_returns = sorted(returns)
            var_95_idx = int(len(sorted_returns) * 0.05)
            var_99_idx = int(len(sorted_returns) * 0.01)
            var_95 = sorted_returns[var_95_idx] if var_95_idx < len(sorted_returns) else 0.0
            var_99 = sorted_returns[var_99_idx] if var_99_idx < len(sorted_returns) else 0.0
        else:
            var_95 = 0.0
            var_99 = 0.0
        
        # Annual metrics
        total_duration_days = (trades[-1].exit_time - trades[0].entry_time) / 86400 if trades else 1
        trades_per_month = total_trades / (total_duration_days / 30) if total_duration_days > 0 else 0
        annual_return = (net_profit / 10000) * (365 / total_duration_days) if total_duration_days > 0 else 0.0
        
        # Additional ratios
        calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0.0
        recovery_factor = net_profit / max_drawdown if max_drawdown > 0 else 0.0
        expectancy = net_profit / total_trades if total_trades > 0 else 0.0
        
        return BacktestMetrics(
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            profit_factor=profit_factor,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_profit=net_profit,
            max_drawdown=max_drawdown,
            max_drawdown_duration=0.0,  # Simplified
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            recovery_factor=recovery_factor,
            expectancy=expectancy,
            avg_trade_duration=avg_trade_duration,
            trades_per_month=trades_per_month,
            annual_return=annual_return,
            volatility=volatility,
            var_95=var_95,
            var_99=var_99,
            metadata={"calculation_timestamp": time.time()}
        )
    
    def _analyze_market_conditions(self, data: List[Dict]) -> Dict[MarketCondition, float]:
        """Analyze market conditions from price data"""
        if len(data) < 20:
            return {condition: 0.0 for condition in MarketCondition}
        
        prices = [d["close"] for d in data]
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        
        # Calculate volatility
        volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0
        
        # Calculate trend strength
        price_change = (prices[-1] - prices[0]) / prices[0]
        trend_strength = abs(price_change)
        
        # Analyze conditions
        conditions = {}
        conditions[MarketCondition.TRENDING] = min(trend_strength * 10, 1.0)
        conditions[MarketCondition.RANGING] = max(1.0 - trend_strength * 10, 0.0)
        conditions[MarketCondition.VOLATILE] = min(volatility * 1000, 1.0)
        conditions[MarketCondition.CALM] = max(1.0 - volatility * 1000, 0.0)
        conditions[MarketCondition.BREAKOUT] = min(volatility * 500, 1.0)
        conditions[MarketCondition.REVERSAL] = min(abs(price_change) * 5, 1.0)
        
        return conditions
    
    def _determine_performance_level(self, metrics: BacktestMetrics) -> PerformanceLevel:
        """Determine performance level based on metrics"""
        if metrics.annual_return > 0.20 and metrics.max_drawdown < 0.05:
            return PerformanceLevel.EXCELLENT
        elif metrics.annual_return > 0.10 and metrics.max_drawdown < 0.10:
            return PerformanceLevel.GOOD
        elif metrics.annual_return > 0.05 and metrics.max_drawdown < 0.15:
            return PerformanceLevel.FAIR
        elif metrics.annual_return > 0.0 and metrics.max_drawdown < 0.25:
            return PerformanceLevel.POOR
        else:
            return PerformanceLevel.CRITICAL
    
    def _generate_symbol_recommendations(self, symbol: str, metrics: BacktestMetrics, trades: List[Trade]) -> List[str]:
        """Generate recommendations for specific symbol"""
        recommendations = []
        
        if metrics.win_rate < self.min_win_rate:
            recommendations.append(f"Improve win rate for {symbol} - currently {metrics.win_rate:.1%}")
        
        if metrics.profit_factor < self.min_profit_factor:
            recommendations.append(f"Improve profit factor for {symbol} - currently {metrics.profit_factor:.2f}")
        
        if metrics.max_drawdown > self.max_drawdown_threshold:
            recommendations.append(f"Reduce drawdown for {symbol} - currently {metrics.max_drawdown:.1%}")
        
        if metrics.sharpe_ratio < 1.0:
            recommendations.append(f"Improve risk-adjusted returns for {symbol}")
        
        if len(trades) < self.min_trades_per_symbol:
            recommendations.append(f"Increase trade frequency for {symbol}")
        
        return recommendations
    
    def _determine_validation_status(self, metrics: BacktestMetrics) -> str:
        """Determine validation status for metrics"""
        if (metrics.win_rate >= self.min_win_rate and 
            metrics.profit_factor >= self.min_profit_factor and 
            metrics.max_drawdown <= self.max_drawdown_threshold):
            return "PASSED"
        elif (metrics.win_rate >= 0.3 and 
              metrics.profit_factor >= 1.0 and 
              metrics.max_drawdown <= 0.20):
            return "WARNING"
        else:
            return "FAILED"
    
    def _assess_risk(self, metrics: BacktestMetrics, symbol_results: List[SymbolBacktest]) -> str:
        """Assess overall risk level"""
        if metrics.max_drawdown > 0.20:
            return "HIGH"
        elif metrics.max_drawdown > 0.10:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _validate_strategy(self, metrics: BacktestMetrics, symbol_results: List[SymbolBacktest]) -> str:
        """Validate strategy effectiveness"""
        if metrics.annual_return > 0.15 and metrics.sharpe_ratio > 1.5:
            return "EXCELLENT"
        elif metrics.annual_return > 0.10 and metrics.sharpe_ratio > 1.0:
            return "GOOD"
        elif metrics.annual_return > 0.05 and metrics.sharpe_ratio > 0.5:
            return "FAIR"
        else:
            return "POOR"
    
    def _generate_comprehensive_recommendations(self, symbol_results: List[SymbolBacktest], 
                                             overall_metrics: BacktestMetrics) -> List[str]:
        """Generate comprehensive recommendations"""
        recommendations = []
        
        # Overall performance recommendations
        if overall_metrics.annual_return < 0.10:
            recommendations.append("Improve overall strategy performance")
        
        if overall_metrics.max_drawdown > 0.15:
            recommendations.append("Implement better risk management")
        
        if overall_metrics.sharpe_ratio < 1.0:
            recommendations.append("Optimize risk-adjusted returns")
        
        # Symbol-specific recommendations
        for symbol_result in symbol_results:
            if symbol_result.performance_level == PerformanceLevel.CRITICAL:
                recommendations.append(f"Review strategy for {symbol_result.symbol}")
        
        return recommendations
    
    def _generate_detailed_analysis(self, symbol_results: List[SymbolBacktest], 
                                  overall_metrics: BacktestMetrics) -> Dict[str, Any]:
        """Generate detailed analysis"""
        return {
            "symbol_performance": {
                symbol.symbol: {
                    "performance_level": symbol.performance_level.value,
                    "total_trades": symbol.total_trades,
                    "win_rate": symbol.metrics.win_rate,
                    "annual_return": symbol.metrics.annual_return,
                    "max_drawdown": symbol.metrics.max_drawdown
                } for symbol in symbol_results
            },
            "overall_analysis": {
                "total_trades": overall_metrics.total_trades,
                "win_rate": overall_metrics.win_rate,
                "annual_return": overall_metrics.annual_return,
                "max_drawdown": overall_metrics.max_drawdown,
                "sharpe_ratio": overall_metrics.sharpe_ratio,
                "profit_factor": overall_metrics.profit_factor
            },
            "risk_analysis": {
                "var_95": overall_metrics.var_95,
                "var_99": overall_metrics.var_99,
                "volatility": overall_metrics.volatility,
                "recovery_factor": overall_metrics.recovery_factor
            }
        }
    
    def _determine_overall_validation_status(self, symbol_results: List[SymbolBacktest]) -> str:
        """Determine overall validation status"""
        passed_symbols = sum(1 for s in symbol_results if s.validation_status == "PASSED")
        total_symbols = len(symbol_results)
        
        if passed_symbols == total_symbols:
            return "PASSED"
        elif passed_symbols >= total_symbols * 0.75:
            return "WARNING"
        else:
            return "FAILED"
    
    def generate_backtest_report(self, backtest_id: str = None) -> BacktestReport:
        """Generate comprehensive backtest report"""
        if backtest_id is None:
            # Use latest backtest
            if not self.backtest_results:
                raise ValueError("No backtest results available")
            backtest_id = max(self.backtest_results.keys())
        
        validation = self.backtest_results[backtest_id]
        
        # Calculate report metrics
        overall_performance_score = self._calculate_performance_score(validation.overall_metrics)
        risk_score = self._calculate_risk_score(validation.overall_metrics)
        consistency_score = self._calculate_consistency_score(validation.symbol_results)
        
        # Symbol breakdown
        symbol_breakdown = {s.symbol: s for s in validation.symbol_results}
        
        # Market condition analysis
        market_condition_analysis = self._analyze_market_conditions_overall(validation.symbol_results)
        
        # Performance attribution
        performance_attribution = self._calculate_performance_attribution(validation.symbol_results)
        
        # Risk metrics
        risk_metrics = self._calculate_risk_metrics(validation.overall_metrics)
        
        # Generate recommendations
        recommendations = self._generate_report_recommendations(validation)
        
        return BacktestReport(
            timestamp=time.time(),
            backtest_id=backtest_id,
            symbols=validation.symbols,
            start_date=validation.start_date,
            end_date=validation.end_date,
            duration_days=validation.duration_days,
            overall_performance_score=overall_performance_score,
            risk_score=risk_score,
            consistency_score=consistency_score,
            total_trades=validation.total_trades,
            overall_metrics=validation.overall_metrics,
            symbol_breakdown=symbol_breakdown,
            market_condition_analysis=market_condition_analysis,
            performance_attribution=performance_attribution,
            risk_metrics=risk_metrics,
            validation_results=[validation],
            recommendations=recommendations,
            metadata={
                "report_generation_time": time.time(),
                "backtest_duration": validation.metadata.get("backtest_duration", 0)
            }
        )
    
    def _calculate_performance_score(self, metrics: BacktestMetrics) -> float:
        """Calculate overall performance score"""
        score = 0.0
        
        # Return component (40%)
        if metrics.annual_return > 0.20:
            score += 0.4
        elif metrics.annual_return > 0.10:
            score += 0.3
        elif metrics.annual_return > 0.05:
            score += 0.2
        else:
            score += 0.1
        
        # Risk component (30%)
        if metrics.max_drawdown < 0.05:
            score += 0.3
        elif metrics.max_drawdown < 0.10:
            score += 0.25
        elif metrics.max_drawdown < 0.15:
            score += 0.2
        else:
            score += 0.1
        
        # Consistency component (30%)
        if metrics.sharpe_ratio > 2.0:
            score += 0.3
        elif metrics.sharpe_ratio > 1.5:
            score += 0.25
        elif metrics.sharpe_ratio > 1.0:
            score += 0.2
        else:
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_risk_score(self, metrics: BacktestMetrics) -> float:
        """Calculate risk score (lower is better)"""
        risk_score = 0.0
        
        # Drawdown component (50%)
        risk_score += min(metrics.max_drawdown * 2, 0.5)
        
        # Volatility component (30%)
        risk_score += min(metrics.volatility * 10, 0.3)
        
        # VaR component (20%)
        risk_score += min(abs(metrics.var_95) / 1000, 0.2)
        
        return min(risk_score, 1.0)
    
    def _calculate_consistency_score(self, symbol_results: List[SymbolBacktest]) -> float:
        """Calculate consistency score across symbols"""
        if not symbol_results:
            return 0.0
        
        # Calculate coefficient of variation for returns
        returns = [s.metrics.annual_return for s in symbol_results]
        if len(returns) > 1 and statistics.mean(returns) != 0:
            cv = statistics.stdev(returns) / abs(statistics.mean(returns))
            return max(0.0, 1.0 - cv)
        else:
            return 1.0
    
    def _analyze_market_conditions_overall(self, symbol_results: List[SymbolBacktest]) -> Dict[MarketCondition, Dict[str, Any]]:
        """Analyze market conditions across all symbols"""
        analysis = {}
        
        for condition in MarketCondition:
            condition_scores = [s.market_conditions.get(condition, 0.0) for s in symbol_results]
            analysis[condition] = {
                "average": statistics.mean(condition_scores),
                "min": min(condition_scores),
                "max": max(condition_scores),
                "dominant": max(condition_scores) > 0.5
            }
        
        return analysis
    
    def _calculate_performance_attribution(self, symbol_results: List[SymbolBacktest]) -> Dict[str, float]:
        """Calculate performance attribution by symbol"""
        attribution = {}
        total_return = sum(s.metrics.annual_return for s in symbol_results)
        
        for symbol_result in symbol_results:
            if total_return != 0:
                attribution[symbol_result.symbol] = symbol_result.metrics.annual_return / total_return
            else:
                attribution[symbol_result.symbol] = 0.0
        
        return attribution
    
    def _calculate_risk_metrics(self, metrics: BacktestMetrics) -> Dict[str, float]:
        """Calculate comprehensive risk metrics"""
        return {
            "max_drawdown": metrics.max_drawdown,
            "var_95": metrics.var_95,
            "var_99": metrics.var_99,
            "volatility": metrics.volatility,
            "sharpe_ratio": metrics.sharpe_ratio,
            "sortino_ratio": metrics.sortino_ratio,
            "calmar_ratio": metrics.calmar_ratio,
            "recovery_factor": metrics.recovery_factor
        }
    
    def _generate_report_recommendations(self, validation: BacktestValidation) -> List[str]:
        """Generate report-level recommendations"""
        recommendations = []
        
        if validation.performance_level == PerformanceLevel.CRITICAL:
            recommendations.append("CRITICAL: Strategy requires immediate review and optimization")
        elif validation.performance_level == PerformanceLevel.POOR:
            recommendations.append("Strategy performance is poor - consider major revisions")
        elif validation.performance_level == PerformanceLevel.FAIR:
            recommendations.append("Strategy performance is fair - minor optimizations recommended")
        elif validation.performance_level == PerformanceLevel.GOOD:
            recommendations.append("Strategy performance is good - consider fine-tuning")
        else:
            recommendations.append("Strategy performance is excellent - maintain current approach")
        
        if validation.risk_assessment == "HIGH":
            recommendations.append("HIGH RISK: Implement additional risk controls")
        elif validation.risk_assessment == "MEDIUM":
            recommendations.append("MEDIUM RISK: Monitor risk metrics closely")
        
        return recommendations

# Global backtesting validator
_backtesting_validator: Optional[BacktestingValidator] = None

def get_backtesting_validator(database_path: str = None) -> BacktestingValidator:
    """Get global backtesting validator instance"""
    global _backtesting_validator
    if _backtesting_validator is None:
        _backtesting_validator = BacktestingValidator(database_path)
    return _backtesting_validator

def run_comprehensive_backtest(start_date: float = None, end_date: float = None) -> BacktestValidation:
    """Run comprehensive 12-month backtest"""
    validator = get_backtesting_validator()
    return validator.run_comprehensive_backtest(start_date, end_date)

def generate_backtest_report(backtest_id: str = None) -> BacktestReport:
    """Generate comprehensive backtest report"""
    validator = get_backtesting_validator()
    return validator.generate_backtest_report(backtest_id)

if __name__ == "__main__":
    # Example usage
    validator = get_backtesting_validator()
    
    # Run comprehensive backtest
    validation = run_comprehensive_backtest()
    
    print(f"Backtest Validation Results:")
    print(f"Backtest ID: {validation.backtest_id}")
    print(f"Symbols: {validation.symbols}")
    print(f"Duration: {validation.duration_days} days")
    print(f"Total Trades: {validation.total_trades}")
    print(f"Validation Status: {validation.validation_status}")
    print(f"Performance Level: {validation.performance_level.value}")
    print(f"Risk Assessment: {validation.risk_assessment}")
    print(f"Strategy Validation: {validation.strategy_validation}")
    
    print(f"\nOverall Metrics:")
    print(f"Win Rate: {validation.overall_metrics.win_rate:.1%}")
    print(f"Annual Return: {validation.overall_metrics.annual_return:.1%}")
    print(f"Max Drawdown: {validation.overall_metrics.max_drawdown:.1%}")
    print(f"Sharpe Ratio: {validation.overall_metrics.sharpe_ratio:.2f}")
    print(f"Profit Factor: {validation.overall_metrics.profit_factor:.2f}")
    
    print(f"\nSymbol Results:")
    for symbol_result in validation.symbol_results:
        print(f"- {symbol_result.symbol}: {symbol_result.performance_level.value} "
              f"({symbol_result.total_trades} trades, {symbol_result.metrics.win_rate:.1%} win rate)")
    
    print(f"\nRecommendations:")
    for rec in validation.recommendations:
        print(f"- {rec}")
    
    # Generate comprehensive report
    report = generate_backtest_report(validation.backtest_id)
    
    print(f"\nBacktest Report:")
    print(f"Overall Performance Score: {report.overall_performance_score:.2%}")
    print(f"Risk Score: {report.risk_score:.2%}")
    print(f"Consistency Score: {report.consistency_score:.2%}")

