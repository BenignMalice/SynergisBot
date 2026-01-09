"""
Win Rate Validation System

This module implements a comprehensive validation system to ensure win rate
≥80% with R:R ≥1:3, including trade performance analysis, risk-adjusted returns
validation, win rate calculation, and comprehensive performance metrics.

Key Features:
- Win rate validation ≥80% with R:R ≥1:3
- Trade performance analysis and validation
- Risk-adjusted returns validation
- Win rate calculation and analysis
- Performance metrics validation
- Trade outcome analysis
- Risk management effectiveness validation
- Profit factor validation
- Sharpe ratio validation
- Maximum drawdown validation
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
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class TradeOutcome(Enum):
    """Trade outcome types"""
    WIN = "win"  # Profitable trade
    LOSS = "loss"  # Losing trade
    BREAKEVEN = "breakeven"  # Breakeven trade
    PARTIAL_WIN = "partial_win"  # Partially profitable trade
    PARTIAL_LOSS = "partial_loss"  # Partially losing trade

class WinRateLevel(Enum):
    """Win rate performance levels"""
    EXCELLENT = "excellent"  # ≥90% win rate
    GOOD = "good"  # 80-89% win rate
    FAIR = "fair"  # 70-79% win rate
    POOR = "poor"  # 60-69% win rate
    CRITICAL = "critical"  # <60% win rate

class RRLevel(Enum):
    """Risk-to-Reward ratio levels"""
    EXCELLENT = "excellent"  # ≥1:5 R:R
    GOOD = "good"  # 1:3 to 1:4.9 R:R
    FAIR = "fair"  # 1:2 to 1:2.9 R:R
    POOR = "poor"  # 1:1 to 1:1.9 R:R
    CRITICAL = "critical"  # <1:1 R:R

class ValidationStatus(Enum):
    """Validation status"""
    PASSED = "passed"  # Validation passed
    WARNING = "warning"  # Validation passed with warnings
    FAILED = "failed"  # Validation failed
    PENDING = "pending"  # Validation pending

@dataclass
class Trade:
    """Trade data structure"""
    trade_id: str
    symbol: str
    side: str  # BUY or SELL
    entry_price: float
    exit_price: float
    volume: float
    entry_time: float
    exit_time: float
    stop_loss: float
    take_profit: float
    actual_stop_loss: Optional[float] = None
    actual_take_profit: Optional[float] = None
    pnl: float = 0.0
    pnl_percentage: float = 0.0
    outcome: Optional[TradeOutcome] = None
    risk_amount: float = 0.0
    reward_amount: float = 0.0
    rr_ratio: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: float
    loss_rate: float
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    total_pnl: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    average_rr_ratio: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_percentage: float
    recovery_factor: float
    expectancy: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WinRateValidation:
    """Win rate validation result"""
    timestamp: float
    total_trades: int
    win_rate: float
    target_win_rate: float
    meets_win_rate_target: bool
    rr_ratio: float
    target_rr_ratio: float
    meets_rr_target: bool
    performance_metrics: PerformanceMetrics
    win_rate_level: WinRateLevel
    rr_level: RRLevel
    validation_status: ValidationStatus
    issues_found: List[str]
    recommendations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WinRateReport:
    """Win rate validation report"""
    timestamp: float
    overall_performance_score: float
    win_rate_validation: WinRateValidation
    performance_analysis: Dict[str, Any]
    risk_analysis: Dict[str, Any]
    consistency_analysis: Dict[str, Any]
    recommendations: List[str]
    detailed_metrics: List[PerformanceMetrics]
    metadata: Dict[str, Any] = field(default_factory=dict)

class TradeAnalyzer:
    """Trade analyzer for performance analysis"""
    
    def __init__(self):
        self.analysis_cache: Dict[str, Any] = {}
        self.lock = threading.RLock()
    
    def analyze_trade_performance(self, trades: List[Trade]) -> PerformanceMetrics:
        """Analyze trade performance"""
        with self.lock:
            if not trades:
                return self._create_empty_metrics()
            
            # Calculate basic metrics
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t.pnl > 0)
            losing_trades = sum(1 for t in trades if t.pnl < 0)
            breakeven_trades = sum(1 for t in trades if t.pnl == 0)
            
            win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
            loss_rate = losing_trades / total_trades if total_trades > 0 else 0.0
            
            # Calculate PnL metrics
            total_pnl = sum(t.pnl for t in trades)
            gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
            gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
            
            # Calculate averages
            wins = [t.pnl for t in trades if t.pnl > 0]
            losses = [t.pnl for t in trades if t.pnl < 0]
            
            average_win = sum(wins) / len(wins) if wins else 0.0
            average_loss = sum(losses) / len(losses) if losses else 0.0
            largest_win = max(wins) if wins else 0.0
            largest_loss = min(losses) if losses else 0.0
            
            # Calculate profit factor
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            # Calculate R:R ratios
            rr_ratios = [t.rr_ratio for t in trades if t.rr_ratio > 0]
            average_rr_ratio = sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0.0
            
            # Calculate risk metrics
            returns = [t.pnl_percentage for t in trades]
            sharpe_ratio = self._calculate_sharpe_ratio(returns)
            sortino_ratio = self._calculate_sortino_ratio(returns)
            
            # Calculate drawdown
            max_drawdown, max_drawdown_percentage = self._calculate_max_drawdown(returns)
            
            # Calculate recovery factor
            recovery_factor = gross_profit / abs(max_drawdown) if max_drawdown < 0 else float('inf')
            
            # Calculate expectancy
            expectancy = (win_rate * average_win) - (loss_rate * abs(average_loss))
            
            return PerformanceMetrics(
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                breakeven_trades=breakeven_trades,
                win_rate=win_rate,
                loss_rate=loss_rate,
                average_win=average_win,
                average_loss=average_loss,
                largest_win=largest_win,
                largest_loss=largest_loss,
                total_pnl=total_pnl,
                gross_profit=gross_profit,
                gross_loss=gross_loss,
                profit_factor=profit_factor,
                average_rr_ratio=average_rr_ratio,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                max_drawdown=max_drawdown,
                max_drawdown_percentage=max_drawdown_percentage,
                recovery_factor=recovery_factor,
                expectancy=expectancy,
                metadata={"analysis_timestamp": time.time()}
            )
    
    def _create_empty_metrics(self) -> PerformanceMetrics:
        """Create empty performance metrics"""
        return PerformanceMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            breakeven_trades=0,
            win_rate=0.0,
            loss_rate=0.0,
            average_win=0.0,
            average_loss=0.0,
            largest_win=0.0,
            largest_loss=0.0,
            total_pnl=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            profit_factor=0.0,
            average_rr_ratio=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_percentage=0.0,
            recovery_factor=0.0,
            expectancy=0.0,
            metadata={"analysis_timestamp": time.time()}
        )
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio"""
        if not returns or len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Assuming risk-free rate of 0 for simplicity
        return mean_return / std_return
    
    def _calculate_sortino_ratio(self, returns: List[float]) -> float:
        """Calculate Sortino ratio"""
        if not returns or len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        negative_returns = [r for r in returns if r < 0]
        
        if not negative_returns:
            return float('inf')
        
        downside_std = np.std(negative_returns)
        
        if downside_std == 0:
            return 0.0
        
        return mean_return / downside_std
    
    def _calculate_max_drawdown(self, returns: List[float]) -> Tuple[float, float]:
        """Calculate maximum drawdown"""
        if not returns:
            return 0.0, 0.0
        
        cumulative_returns = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = cumulative_returns - running_max
        
        max_drawdown = np.min(drawdown)
        max_drawdown_percentage = (max_drawdown / np.max(running_max)) * 100 if np.max(running_max) > 0 else 0.0
        
        return max_drawdown, max_drawdown_percentage

class WinRateValidator:
    """Win rate validator for comprehensive validation"""
    
    def __init__(self, target_win_rate: float = 0.80, target_rr_ratio: float = 3.0):
        self.target_win_rate = target_win_rate
        self.target_rr_ratio = target_rr_ratio
        self.analyzer = TradeAnalyzer()
        self.validations: List[WinRateValidation] = []
        self.lock = threading.RLock()
        self.start_time = time.time()
    
    def validate_win_rate(self, trades: List[Trade]) -> WinRateValidation:
        """Validate win rate and R:R ratio"""
        # Analyze trade performance
        performance_metrics = self.analyzer.analyze_trade_performance(trades)
        
        # Check win rate target
        meets_win_rate_target = performance_metrics.win_rate >= self.target_win_rate
        
        # Check R:R ratio target
        meets_rr_target = performance_metrics.average_rr_ratio >= self.target_rr_ratio
        
        # Determine win rate level
        win_rate_level = self._determine_win_rate_level(performance_metrics.win_rate)
        
        # Determine R:R level
        rr_level = self._determine_rr_level(performance_metrics.average_rr_ratio)
        
        # Determine validation status
        validation_status = self._determine_validation_status(
            meets_win_rate_target, meets_rr_target, performance_metrics
        )
        
        # Generate issues and recommendations
        issues_found = self._identify_issues(performance_metrics, meets_win_rate_target, meets_rr_target)
        recommendations = self._generate_recommendations(performance_metrics, issues_found)
        
        validation = WinRateValidation(
            timestamp=time.time(),
            total_trades=performance_metrics.total_trades,
            win_rate=performance_metrics.win_rate,
            target_win_rate=self.target_win_rate,
            meets_win_rate_target=meets_win_rate_target,
            rr_ratio=performance_metrics.average_rr_ratio,
            target_rr_ratio=self.target_rr_ratio,
            meets_rr_target=meets_rr_target,
            performance_metrics=performance_metrics,
            win_rate_level=win_rate_level,
            rr_level=rr_level,
            validation_status=validation_status,
            issues_found=issues_found,
            recommendations=recommendations,
            metadata={
                "target_win_rate": self.target_win_rate,
                "target_rr_ratio": self.target_rr_ratio,
                "validation_time": time.time()
            }
        )
        
        with self.lock:
            self.validations.append(validation)
        
        return validation
    
    def _determine_win_rate_level(self, win_rate: float) -> WinRateLevel:
        """Determine win rate performance level"""
        if win_rate >= 0.90:
            return WinRateLevel.EXCELLENT
        elif win_rate >= 0.80:
            return WinRateLevel.GOOD
        elif win_rate >= 0.70:
            return WinRateLevel.FAIR
        elif win_rate >= 0.60:
            return WinRateLevel.POOR
        else:
            return WinRateLevel.CRITICAL
    
    def _determine_rr_level(self, rr_ratio: float) -> RRLevel:
        """Determine R:R ratio level"""
        if rr_ratio >= 5.0:
            return RRLevel.EXCELLENT
        elif rr_ratio >= 3.0:
            return RRLevel.GOOD
        elif rr_ratio >= 2.0:
            return RRLevel.FAIR
        elif rr_ratio >= 1.0:
            return RRLevel.POOR
        else:
            return RRLevel.CRITICAL
    
    def _determine_validation_status(self, meets_win_rate: bool, meets_rr: bool, 
                                   metrics: PerformanceMetrics) -> ValidationStatus:
        """Determine validation status"""
        if meets_win_rate and meets_rr and metrics.profit_factor >= 2.0:
            return ValidationStatus.PASSED
        elif meets_win_rate and meets_rr:
            return ValidationStatus.PASSED
        elif meets_win_rate or meets_rr:
            return ValidationStatus.WARNING
        else:
            return ValidationStatus.FAILED
    
    def _identify_issues(self, metrics: PerformanceMetrics, meets_win_rate: bool, 
                        meets_rr: bool) -> List[str]:
        """Identify performance issues"""
        issues = []
        
        if not meets_win_rate:
            issues.append(f"Win rate {metrics.win_rate:.1%} below target {self.target_win_rate:.1%}")
        
        if not meets_rr:
            issues.append(f"R:R ratio {metrics.average_rr_ratio:.1f} below target {self.target_rr_ratio:.1f}")
        
        if metrics.profit_factor < 1.5:
            issues.append(f"Low profit factor: {metrics.profit_factor:.2f}")
        
        if metrics.sharpe_ratio < 1.0:
            issues.append(f"Low Sharpe ratio: {metrics.sharpe_ratio:.2f}")
        
        if metrics.max_drawdown_percentage > 20.0:
            issues.append(f"High maximum drawdown: {metrics.max_drawdown_percentage:.1f}%")
        
        if metrics.expectancy < 0:
            issues.append(f"Negative expectancy: {metrics.expectancy:.2f}")
        
        if metrics.total_trades < 10:
            issues.append(f"Insufficient sample size: {metrics.total_trades} trades")
        
        return issues
    
    def _generate_recommendations(self, metrics: PerformanceMetrics, issues: List[str]) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        if not metrics.win_rate >= self.target_win_rate:
            recommendations.append("Improve entry timing and signal quality to increase win rate")
            recommendations.append("Review and optimize M1 filters for better trade selection")
        
        if not metrics.average_rr_ratio >= self.target_rr_ratio:
            recommendations.append("Optimize take profit and stop loss levels for better R:R ratio")
            recommendations.append("Implement dynamic position sizing based on market structure")
        
        if metrics.profit_factor < 2.0:
            recommendations.append("Focus on reducing average loss size and increasing average win size")
            recommendations.append("Implement better risk management and position sizing")
        
        if metrics.sharpe_ratio < 1.5:
            recommendations.append("Improve risk-adjusted returns through better trade management")
            recommendations.append("Consider implementing volatility-based position sizing")
        
        if metrics.max_drawdown_percentage > 15.0:
            recommendations.append("Implement stricter risk controls to reduce maximum drawdown")
            recommendations.append("Consider reducing position sizes during high volatility periods")
        
        if metrics.expectancy < 0:
            recommendations.append("Fundamental strategy review needed - negative expectancy detected")
            recommendations.append("Consider pausing trading until strategy is optimized")
        
        if len(issues) == 0:
            recommendations.append("Excellent performance! Continue current strategy")
        
        # Ensure at least one recommendation
        if not recommendations:
            recommendations.append("Monitor performance metrics and continue current strategy")
        
        return recommendations
    
    def generate_validation_report(self) -> WinRateReport:
        """Generate comprehensive validation report"""
        with self.lock:
            if not self.validations:
                return WinRateReport(
                    timestamp=time.time(),
                    overall_performance_score=0.0,
                    win_rate_validation=WinRateValidation(
                        timestamp=time.time(),
                        total_trades=0,
                        win_rate=0.0,
                        target_win_rate=self.target_win_rate,
                        meets_win_rate_target=False,
                        rr_ratio=0.0,
                        target_rr_ratio=self.target_rr_ratio,
                        meets_rr_target=False,
                        performance_metrics=PerformanceMetrics(
                            total_trades=0, winning_trades=0, losing_trades=0, breakeven_trades=0,
                            win_rate=0.0, loss_rate=0.0, average_win=0.0, average_loss=0.0,
                            largest_win=0.0, largest_loss=0.0, total_pnl=0.0, gross_profit=0.0,
                            gross_loss=0.0, profit_factor=0.0, average_rr_ratio=0.0,
                            sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                            max_drawdown_percentage=0.0, recovery_factor=0.0, expectancy=0.0
                        ),
                        win_rate_level=WinRateLevel.CRITICAL,
                        rr_level=RRLevel.CRITICAL,
                        validation_status=ValidationStatus.FAILED,
                        issues_found=["No validation data available"],
                        recommendations=["No validation data available"]
                    ),
                    performance_analysis={},
                    risk_analysis={},
                    consistency_analysis={},
                    recommendations=["No validation data available"],
                    detailed_metrics=[],
                    metadata={"error": "No validation data available"}
                )
            
            # Get latest validation
            latest_validation = self.validations[-1]
            
            # Calculate overall performance score
            overall_score = self._calculate_overall_performance_score(latest_validation)
            
            # Generate analysis
            performance_analysis = self._analyze_performance(latest_validation)
            risk_analysis = self._analyze_risk(latest_validation)
            consistency_analysis = self._analyze_consistency(latest_validation)
            
            # Generate recommendations
            recommendations = self._generate_report_recommendations(latest_validation)
            
            return WinRateReport(
                timestamp=time.time(),
                overall_performance_score=overall_score,
                win_rate_validation=latest_validation,
                performance_analysis=performance_analysis,
                risk_analysis=risk_analysis,
                consistency_analysis=consistency_analysis,
                recommendations=recommendations,
                detailed_metrics=[v.performance_metrics for v in self.validations],
                metadata={
                    "target_win_rate": self.target_win_rate,
                    "target_rr_ratio": self.target_rr_ratio,
                    "validation_duration": time.time() - self.start_time
                }
            )
    
    def _calculate_overall_performance_score(self, validation: WinRateValidation) -> float:
        """Calculate overall performance score"""
        score = 0.0
        
        # Win rate score (40% weight)
        if validation.meets_win_rate_target:
            score += 0.4
        else:
            score += 0.4 * (validation.win_rate / validation.target_win_rate)
        
        # R:R ratio score (30% weight)
        if validation.meets_rr_target:
            score += 0.3
        else:
            score += 0.3 * (validation.rr_ratio / validation.target_rr_ratio)
        
        # Profit factor score (20% weight)
        profit_factor_score = min(1.0, validation.performance_metrics.profit_factor / 3.0)
        score += 0.2 * profit_factor_score
        
        # Sharpe ratio score (10% weight)
        sharpe_score = min(1.0, validation.performance_metrics.sharpe_ratio / 2.0)
        score += 0.1 * sharpe_score
        
        return max(0.0, min(1.0, score))
    
    def _analyze_performance(self, validation: WinRateValidation) -> Dict[str, Any]:
        """Analyze performance metrics"""
        metrics = validation.performance_metrics
        
        return {
            "win_rate_analysis": {
                "current": metrics.win_rate,
                "target": validation.target_win_rate,
                "meets_target": validation.meets_win_rate_target,
                "level": validation.win_rate_level.value
            },
            "rr_analysis": {
                "current": metrics.average_rr_ratio,
                "target": validation.target_rr_ratio,
                "meets_target": validation.meets_rr_target,
                "level": validation.rr_level.value
            },
            "profitability_analysis": {
                "total_pnl": metrics.total_pnl,
                "profit_factor": metrics.profit_factor,
                "expectancy": metrics.expectancy,
                "gross_profit": metrics.gross_profit,
                "gross_loss": metrics.gross_loss
            },
            "trade_analysis": {
                "total_trades": metrics.total_trades,
                "winning_trades": metrics.winning_trades,
                "losing_trades": metrics.losing_trades,
                "breakeven_trades": metrics.breakeven_trades,
                "average_win": metrics.average_win,
                "average_loss": metrics.average_loss
            }
        }
    
    def _analyze_risk(self, validation: WinRateValidation) -> Dict[str, Any]:
        """Analyze risk metrics"""
        metrics = validation.performance_metrics
        
        return {
            "drawdown_analysis": {
                "max_drawdown": metrics.max_drawdown,
                "max_drawdown_percentage": metrics.max_drawdown_percentage,
                "recovery_factor": metrics.recovery_factor
            },
            "risk_adjusted_returns": {
                "sharpe_ratio": metrics.sharpe_ratio,
                "sortino_ratio": metrics.sortino_ratio
            },
            "risk_metrics": {
                "largest_win": metrics.largest_win,
                "largest_loss": metrics.largest_loss,
                "win_loss_ratio": metrics.average_win / abs(metrics.average_loss) if metrics.average_loss != 0 else 0.0
            }
        }
    
    def _analyze_consistency(self, validation: WinRateValidation) -> Dict[str, Any]:
        """Analyze consistency metrics"""
        metrics = validation.performance_metrics
        
        return {
            "consistency_metrics": {
                "win_rate_consistency": "High" if metrics.win_rate >= 0.8 else "Medium" if metrics.win_rate >= 0.6 else "Low",
                "rr_consistency": "High" if metrics.average_rr_ratio >= 3.0 else "Medium" if metrics.average_rr_ratio >= 2.0 else "Low",
                "profit_factor_consistency": "High" if metrics.profit_factor >= 2.0 else "Medium" if metrics.profit_factor >= 1.5 else "Low"
            },
            "sample_size_analysis": {
                "total_trades": metrics.total_trades,
                "sufficient_sample": metrics.total_trades >= 30,
                "recommended_minimum": 30
            }
        }
    
    def _generate_report_recommendations(self, validation: WinRateValidation) -> List[str]:
        """Generate report recommendations"""
        recommendations = []
        
        if validation.validation_status == ValidationStatus.PASSED:
            recommendations.append("Excellent performance! All targets met.")
        elif validation.validation_status == ValidationStatus.WARNING:
            recommendations.append("Good performance with minor improvements needed.")
        else:
            recommendations.append("Performance needs improvement to meet targets.")
        
        if not validation.meets_win_rate_target:
            recommendations.append(f"Focus on improving win rate from {validation.win_rate:.1%} to {validation.target_win_rate:.1%}")
        
        if not validation.meets_rr_target:
            recommendations.append(f"Optimize R:R ratio from {validation.rr_ratio:.1f} to {validation.target_rr_ratio:.1f}")
        
        if validation.performance_metrics.profit_factor < 2.0:
            recommendations.append("Improve profit factor through better risk management")
        
        if validation.performance_metrics.sharpe_ratio < 1.5:
            recommendations.append("Enhance risk-adjusted returns")
        
        return recommendations

# Global win rate validation manager
_win_rate_validator: Optional[WinRateValidator] = None

def get_win_rate_validator(target_win_rate: float = 0.80, target_rr_ratio: float = 3.0) -> WinRateValidator:
    """Get global win rate validator instance"""
    global _win_rate_validator
    if _win_rate_validator is None:
        _win_rate_validator = WinRateValidator(target_win_rate, target_rr_ratio)
    return _win_rate_validator

def validate_win_rate(trades: List[Trade]) -> WinRateValidation:
    """Validate win rate and R:R ratio"""
    validator = get_win_rate_validator()
    return validator.validate_win_rate(trades)

def generate_win_rate_report() -> WinRateReport:
    """Generate win rate validation report"""
    validator = get_win_rate_validator()
    return validator.generate_validation_report()

if __name__ == "__main__":
    # Example usage
    validator = get_win_rate_validator()
    
    # Example trades
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
    
    validation = validate_win_rate(trades)
    
    print(f"Win Rate Validation:")
    print(f"Total Trades: {validation.total_trades}")
    print(f"Win Rate: {validation.win_rate:.1%}")
    print(f"Target Win Rate: {validation.target_win_rate:.1%}")
    print(f"Meets Win Rate Target: {validation.meets_win_rate_target}")
    print(f"R:R Ratio: {validation.rr_ratio:.1f}")
    print(f"Target R:R Ratio: {validation.target_rr_ratio:.1f}")
    print(f"Meets R:R Target: {validation.meets_rr_target}")
    print(f"Win Rate Level: {validation.win_rate_level.value}")
    print(f"R:R Level: {validation.rr_level.value}")
    print(f"Validation Status: {validation.validation_status.value}")
    
    print("\nPerformance Metrics:")
    metrics = validation.performance_metrics
    print(f"Profit Factor: {metrics.profit_factor:.2f}")
    print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {metrics.max_drawdown_percentage:.1f}%")
    print(f"Expectancy: {metrics.expectancy:.2f}")
    
    print("\nIssues Found:")
    for issue in validation.issues_found:
        print(f"- {issue}")
    
    print("\nRecommendations:")
    for rec in validation.recommendations:
        print(f"- {rec}")
    
    # Generate validation report
    report = generate_win_rate_report()
    
    print(f"\nWin Rate Report:")
    print(f"Overall Performance Score: {report.overall_performance_score:.2f}")
    print(f"Performance Analysis: {len(report.performance_analysis)} metrics")
    print(f"Risk Analysis: {len(report.risk_analysis)} metrics")
    print(f"Consistency Analysis: {len(report.consistency_analysis)} metrics")
    print(f"Recommendations: {len(report.recommendations)} items")
