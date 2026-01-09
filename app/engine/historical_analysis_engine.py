"""
Historical Analysis Engine
Historical analysis data storage and analysis
"""

import numpy as np
from numba import jit, prange
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import logging
from dataclasses import dataclass
from enum import Enum
import pandas as pd

logger = logging.getLogger(__name__)

class AnalysisType(Enum):
    """Analysis types"""
    PERFORMANCE = "performance"
    RISK = "risk"
    CORRELATION = "correlation"
    SEASONALITY = "seasonality"
    VOLATILITY = "volatility"
    MOMENTUM = "momentum"

class AnalysisPeriod(Enum):
    """Analysis periods"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

@dataclass
class AnalysisResult:
    """Analysis result data structure"""
    symbol: str
    analysis_type: AnalysisType
    period: AnalysisPeriod
    timestamp_ms: int
    result_data: Dict[str, Any]
    confidence: float
    context: Dict[str, Any]

class HistoricalAnalysisEngine:
    """Historical analysis engine for data storage and analysis"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.symbol = symbol_config.get('symbol', 'unknown')
        
        # Analysis configuration
        self.analysis_config = symbol_config.get('analysis_config', {})
        self.lookback_periods = self.analysis_config.get('lookback_periods', {
            'daily': 30,
            'weekly': 12,
            'monthly': 12,
            'quarterly': 4,
            'yearly': 2
        })
        
        # Analysis results storage
        self.analysis_results = {}
        self.analysis_history = []
        
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio using Numba"""
        if len(returns) == 0:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        mean_excess = np.mean(excess_returns)
        std_excess = np.std(excess_returns)
        
        if std_excess == 0:
            return 0.0
        
        return (mean_excess / std_excess) * np.sqrt(252)  # Annualized
    
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_max_drawdown(equity_values: np.ndarray) -> float:
        """Calculate maximum drawdown using Numba"""
        if len(equity_values) == 0:
            return 0.0
        
        peak = equity_values[0]
        max_drawdown = 0.0
        
        for i in range(1, len(equity_values)):
            if equity_values[i] > peak:
                peak = equity_values[i]
            else:
                drawdown = (peak - equity_values[i]) / peak
                max_drawdown = max(max_drawdown, drawdown)
        
        return max_drawdown
    
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_correlation(series1: np.ndarray, series2: np.ndarray) -> float:
        """Calculate correlation coefficient using Numba"""
        if len(series1) != len(series2) or len(series1) == 0:
            return 0.0
        
        # Calculate means
        mean1 = np.mean(series1)
        mean2 = np.mean(series2)
        
        # Calculate correlation
        numerator = 0.0
        sum_sq1 = 0.0
        sum_sq2 = 0.0
        
        for i in range(len(series1)):
            diff1 = series1[i] - mean1
            diff2 = series2[i] - mean2
            numerator += diff1 * diff2
            sum_sq1 += diff1 * diff1
            sum_sq2 += diff2 * diff2
        
        if sum_sq1 == 0 or sum_sq2 == 0:
            return 0.0
        
        return numerator / np.sqrt(sum_sq1 * sum_sq2)
    
    def analyze_performance(self, trade_data: List[Dict[str, Any]], period: AnalysisPeriod) -> AnalysisResult:
        """Analyze trading performance"""
        try:
            if not trade_data:
                return self._create_empty_result(AnalysisType.PERFORMANCE, period)
            
            # Extract PnL data
            pnl_values = [trade.get('pnl', 0.0) for trade in trade_data]
            pnl_array = np.array(pnl_values, dtype=np.float32)
            
            # Calculate performance metrics
            total_trades = len(pnl_values)
            winning_trades = sum(1 for pnl in pnl_values if pnl > 0)
            losing_trades = sum(1 for pnl in pnl_values if pnl < 0)
            
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            total_pnl = np.sum(pnl_array)
            avg_pnl = np.mean(pnl_array)
            max_win = np.max(pnl_array) if len(pnl_array) > 0 else 0
            max_loss = np.min(pnl_array) if len(pnl_array) > 0 else 0
            
            # Calculate Sharpe ratio
            if len(pnl_array) > 1:
                returns = np.diff(pnl_array)
                sharpe_ratio = self.calculate_sharpe_ratio(returns)
            else:
                sharpe_ratio = 0.0
            
            # Calculate maximum drawdown
            if len(pnl_array) > 1:
                cumulative_pnl = np.cumsum(pnl_array)
                max_drawdown = self.calculate_max_drawdown(cumulative_pnl)
            else:
                max_drawdown = 0.0
            
            # Calculate profit factor
            gross_profit = sum(pnl for pnl in pnl_values if pnl > 0)
            gross_loss = abs(sum(pnl for pnl in pnl_values if pnl < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            result_data = {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'max_win': max_win,
                'max_loss': max_loss,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'profit_factor': profit_factor,
                'gross_profit': gross_profit,
                'gross_loss': gross_loss
            }
            
            # Calculate confidence based on data quality
            confidence = min(total_trades / 100, 1.0)  # More trades = higher confidence
            
            return AnalysisResult(
                symbol=self.symbol,
                analysis_type=AnalysisType.PERFORMANCE,
                period=period,
                timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                result_data=result_data,
                confidence=confidence,
                context={'data_points': total_trades, 'period': period.value}
            )
            
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            return self._create_empty_result(AnalysisType.PERFORMANCE, period)
    
    def analyze_risk(self, trade_data: List[Dict[str, Any]], period: AnalysisPeriod) -> AnalysisResult:
        """Analyze risk metrics"""
        try:
            if not trade_data:
                return self._create_empty_result(AnalysisType.RISK, period)
            
            # Extract risk data
            pnl_values = [trade.get('pnl', 0.0) for trade in trade_data]
            pnl_array = np.array(pnl_values, dtype=np.float32)
            
            # Calculate risk metrics
            if len(pnl_array) > 1:
                returns = np.diff(pnl_array)
                volatility = np.std(returns) * np.sqrt(252)  # Annualized
                var_95 = np.percentile(returns, 5)  # 95% VaR
                var_99 = np.percentile(returns, 1)  # 99% VaR
            else:
                volatility = 0.0
                var_95 = 0.0
                var_99 = 0.0
            
            # Calculate maximum drawdown
            if len(pnl_array) > 1:
                cumulative_pnl = np.cumsum(pnl_array)
                max_drawdown = self.calculate_max_drawdown(cumulative_pnl)
            else:
                max_drawdown = 0.0
            
            # Calculate consecutive losses
            consecutive_losses = 0
            max_consecutive_losses = 0
            current_consecutive = 0
            
            for pnl in pnl_values:
                if pnl < 0:
                    current_consecutive += 1
                    max_consecutive_losses = max(max_consecutive_losses, current_consecutive)
                else:
                    current_consecutive = 0
            
            # Calculate total PnL for risk-adjusted return
            total_pnl = sum(pnl_values)
            
            result_data = {
                'volatility': volatility,
                'var_95': var_95,
                'var_99': var_99,
                'max_drawdown': max_drawdown,
                'max_consecutive_losses': max_consecutive_losses,
                'risk_adjusted_return': total_pnl / max_drawdown if max_drawdown > 0 else 0
            }
            
            # Calculate confidence
            confidence = min(len(pnl_values) / 50, 1.0)
            
            return AnalysisResult(
                symbol=self.symbol,
                analysis_type=AnalysisType.RISK,
                period=period,
                timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                result_data=result_data,
                confidence=confidence,
                context={'data_points': len(pnl_values), 'period': period.value}
            )
            
        except Exception as e:
            logger.error(f"Error analyzing risk: {e}")
            return self._create_empty_result(AnalysisType.RISK, period)
    
    def analyze_correlation(self, symbol_data: Dict[str, List[float]], period: AnalysisPeriod) -> AnalysisResult:
        """Analyze correlation between symbols"""
        try:
            if len(symbol_data) < 2:
                return self._create_empty_result(AnalysisType.CORRELATION, period)
            
            symbols = list(symbol_data.keys())
            correlations = {}
            
            # Calculate pairwise correlations
            for i, symbol1 in enumerate(symbols):
                for j, symbol2 in enumerate(symbols[i+1:], i+1):
                    series1 = np.array(symbol_data[symbol1], dtype=np.float32)
                    series2 = np.array(symbol_data[symbol2], dtype=np.float32)
                    
                    if len(series1) == len(series2) and len(series1) > 1:
                        correlation = self.calculate_correlation(series1, series2)
                        correlations[f"{symbol1}_{symbol2}"] = correlation
            
            # Calculate average correlation
            if correlations:
                avg_correlation = np.mean(list(correlations.values()))
                max_correlation = np.max(list(correlations.values()))
                min_correlation = np.min(list(correlations.values()))
            else:
                avg_correlation = 0.0
                max_correlation = 0.0
                min_correlation = 0.0
            
            result_data = {
                'correlations': correlations,
                'avg_correlation': avg_correlation,
                'max_correlation': max_correlation,
                'min_correlation': min_correlation,
                'symbol_count': len(symbols)
            }
            
            # Calculate confidence
            confidence = min(len(symbols) / 5, 1.0)
            
            return AnalysisResult(
                symbol=self.symbol,
                analysis_type=AnalysisType.CORRELATION,
                period=period,
                timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                result_data=result_data,
                confidence=confidence,
                context={'symbols': symbols, 'period': period.value}
            )
            
        except Exception as e:
            logger.error(f"Error analyzing correlation: {e}")
            return self._create_empty_result(AnalysisType.CORRELATION, period)
    
    def analyze_seasonality(self, trade_data: List[Dict[str, Any]], period: AnalysisPeriod) -> AnalysisResult:
        """Analyze seasonal patterns"""
        try:
            if not trade_data:
                return self._create_empty_result(AnalysisType.SEASONALITY, period)
            
            # Extract time-based data
            hourly_pnl = {}
            daily_pnl = {}
            monthly_pnl = {}
            
            for trade in trade_data:
                if 'exit_time' in trade and trade['exit_time']:
                    exit_time = datetime.fromtimestamp(trade['exit_time'] / 1000, tz=timezone.utc)
                    hour = exit_time.hour
                    day = exit_time.weekday()
                    month = exit_time.month
                    
                    pnl = trade.get('pnl', 0.0)
                    
                    # Aggregate by time periods
                    if hour not in hourly_pnl:
                        hourly_pnl[hour] = []
                    hourly_pnl[hour].append(pnl)
                    
                    if day not in daily_pnl:
                        daily_pnl[day] = []
                    daily_pnl[day].append(pnl)
                    
                    if month not in monthly_pnl:
                        monthly_pnl[month] = []
                    monthly_pnl[month].append(pnl)
            
            # Calculate seasonal metrics
            hourly_avg = {hour: np.mean(pnl_list) for hour, pnl_list in hourly_pnl.items()}
            daily_avg = {day: np.mean(pnl_list) for day, pnl_list in daily_pnl.items()}
            monthly_avg = {month: np.mean(pnl_list) for month, pnl_list in monthly_pnl.items()}
            
            # Find best/worst times
            best_hour = max(hourly_avg.items(), key=lambda x: x[1]) if hourly_avg else (0, 0.0)
            worst_hour = min(hourly_avg.items(), key=lambda x: x[1]) if hourly_avg else (0, 0.0)
            best_day = max(daily_avg.items(), key=lambda x: x[1]) if daily_avg else (0, 0.0)
            worst_day = min(daily_avg.items(), key=lambda x: x[1]) if daily_avg else (0, 0.0)
            best_month = max(monthly_avg.items(), key=lambda x: x[1]) if monthly_avg else (0, 0.0)
            worst_month = min(monthly_avg.items(), key=lambda x: x[1]) if monthly_avg else (0, 0.0)
            
            result_data = {
                'hourly_avg': hourly_avg,
                'daily_avg': daily_avg,
                'monthly_avg': monthly_avg,
                'best_hour': best_hour,
                'worst_hour': worst_hour,
                'best_day': best_day,
                'worst_day': worst_day,
                'best_month': best_month,
                'worst_month': worst_month
            }
            
            # Calculate confidence
            confidence = min(len(trade_data) / 100, 1.0)
            
            return AnalysisResult(
                symbol=self.symbol,
                analysis_type=AnalysisType.SEASONALITY,
                period=period,
                timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                result_data=result_data,
                confidence=confidence,
                context={'data_points': len(trade_data), 'period': period.value}
            )
            
        except Exception as e:
            logger.error(f"Error analyzing seasonality: {e}")
            return self._create_empty_result(AnalysisType.SEASONALITY, period)
    
    def _create_empty_result(self, analysis_type: AnalysisType, period: AnalysisPeriod) -> AnalysisResult:
        """Create empty analysis result"""
        return AnalysisResult(
            symbol=self.symbol,
            analysis_type=analysis_type,
            period=period,
            timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
            result_data={},
            confidence=0.0,
            context={'error': 'insufficient_data', 'period': period.value}
        )
    
    def store_analysis_result(self, result: AnalysisResult):
        """Store analysis result"""
        try:
            key = f"{result.analysis_type.value}_{result.period.value}"
            if key not in self.analysis_results:
                self.analysis_results[key] = []
            
            self.analysis_results[key].append(result)
            self.analysis_history.append(result)
            
            # Keep only recent history
            if len(self.analysis_history) > 1000:
                self.analysis_history = self.analysis_history[-1000:]
                
        except Exception as e:
            logger.error(f"Error storing analysis result: {e}")
    
    def get_analysis_results(self, analysis_type: AnalysisType = None, period: AnalysisPeriod = None) -> List[AnalysisResult]:
        """Get analysis results"""
        try:
            if analysis_type and period:
                key = f"{analysis_type.value}_{period.value}"
                return self.analysis_results.get(key, [])
            elif analysis_type:
                return [result for result in self.analysis_history if result.analysis_type == analysis_type]
            elif period:
                return [result for result in self.analysis_history if result.period == period]
            else:
                return self.analysis_history.copy()
                
        except Exception as e:
            logger.error(f"Error getting analysis results: {e}")
            return []
    
    def get_analysis_statistics(self) -> Dict[str, Any]:
        """Get analysis statistics"""
        try:
            # Count by analysis type
            analysis_type_counts = {}
            for result in self.analysis_history:
                analysis_type = result.analysis_type.value
                analysis_type_counts[analysis_type] = analysis_type_counts.get(analysis_type, 0) + 1
            
            # Count by period
            period_counts = {}
            for result in self.analysis_history:
                period = result.period.value
                period_counts[period] = period_counts.get(period, 0) + 1
            
            # Calculate average confidence
            if self.analysis_history:
                avg_confidence = sum(result.confidence for result in self.analysis_history) / len(self.analysis_history)
            else:
                avg_confidence = 0.0
            
            return {
                'total_analyses': len(self.analysis_history),
                'analysis_type_counts': analysis_type_counts,
                'period_counts': period_counts,
                'average_confidence': avg_confidence,
                'symbol': self.symbol
            }
            
        except Exception as e:
            logger.error(f"Error getting analysis statistics: {e}")
            return {}

# Example usage and testing
if __name__ == "__main__":
    # Test configuration
    test_config = {
        'symbol': 'GBPJPYc',
        'analysis_config': {
            'lookback_periods': {
                'daily': 30,
                'weekly': 12,
                'monthly': 12
            }
        }
    }
    
    # Create analysis engine
    analysis_engine = HistoricalAnalysisEngine(test_config)
    
    # Simulate trade data
    trade_data = [
        {'pnl': 50.0, 'exit_time': 1640995200000},
        {'pnl': -25.0, 'exit_time': 1640998800000},
        {'pnl': 75.0, 'exit_time': 1641002400000},
        {'pnl': 30.0, 'exit_time': 1641006000000},
        {'pnl': -40.0, 'exit_time': 1641009600000}
    ]
    
    print("Testing Historical Analysis Engine:")
    
    # Analyze performance
    performance_result = analysis_engine.analyze_performance(trade_data, AnalysisPeriod.DAILY)
    print(f"Performance Analysis: {performance_result.result_data}")
    
    # Analyze risk
    risk_result = analysis_engine.analyze_risk(trade_data, AnalysisPeriod.DAILY)
    print(f"Risk Analysis: {risk_result.result_data}")
    
    # Analyze seasonality
    seasonality_result = analysis_engine.analyze_seasonality(trade_data, AnalysisPeriod.DAILY)
    print(f"Seasonality Analysis: {seasonality_result.result_data}")
    
    # Store results
    analysis_engine.store_analysis_result(performance_result)
    analysis_engine.store_analysis_result(risk_result)
    analysis_engine.store_analysis_result(seasonality_result)
    
    # Get statistics
    stats = analysis_engine.get_analysis_statistics()
    print(f"Analysis Statistics: {stats}")
