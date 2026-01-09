"""
Symbol Optimization System
Automatically tunes symbol-specific parameters based on performance metrics
"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class OptimizationStatus(Enum):
    """Symbol optimization status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class OptimizationMetric(Enum):
    """Optimization metrics"""
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    AVERAGE_RR = "average_rr"

@dataclass
class OptimizationResult:
    """Result of symbol optimization"""
    symbol: str
    metric: OptimizationMetric
    old_value: float
    new_value: float
    improvement: float
    parameters: Dict[str, Any]
    timestamp: float
    status: OptimizationStatus

@dataclass
class SymbolPerformance:
    """Symbol performance metrics"""
    symbol: str
    total_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    average_rr: float
    period_days: int
    timestamp: float

class SymbolOptimizer:
    """Symbol parameter optimization system"""
    
    def __init__(self, db_path: str = "data/symbol_optimization.db"):
        self.db_path = db_path
        self.connection = None
        self._init_database()
        
    def _init_database(self):
        """Initialize optimization database"""
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS optimization_results (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                metric TEXT NOT NULL,
                old_value REAL NOT NULL,
                new_value REAL NOT NULL,
                improvement REAL NOT NULL,
                parameters TEXT NOT NULL,
                timestamp REAL NOT NULL,
                status TEXT NOT NULL
            )
        """)
        
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS symbol_performance (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                total_trades INTEGER NOT NULL,
                win_rate REAL NOT NULL,
                profit_factor REAL NOT NULL,
                sharpe_ratio REAL NOT NULL,
                max_drawdown REAL NOT NULL,
                average_rr REAL NOT NULL,
                period_days INTEGER NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_optimization_symbol 
            ON optimization_results(symbol, timestamp)
        """)
        
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_performance_symbol 
            ON symbol_performance(symbol, timestamp)
        """)
        
        self.connection.commit()
    
    def record_performance(self, performance: SymbolPerformance):
        """Record symbol performance metrics"""
        try:
            self.connection.execute("""
                INSERT INTO symbol_performance 
                (symbol, total_trades, win_rate, profit_factor, sharpe_ratio, 
                 max_drawdown, average_rr, period_days, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                performance.symbol,
                performance.total_trades,
                performance.win_rate,
                performance.profit_factor,
                performance.sharpe_ratio,
                performance.max_drawdown,
                performance.average_rr,
                performance.period_days,
                performance.timestamp
            ))
            self.connection.commit()
            logger.info(f"✅ Recorded performance for {performance.symbol}")
        except Exception as e:
            logger.error(f"❌ Failed to record performance: {e}")
    
    def get_latest_performance(self, symbol: str) -> Optional[SymbolPerformance]:
        """Get latest performance metrics for symbol"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT symbol, total_trades, win_rate, profit_factor, sharpe_ratio,
                       max_drawdown, average_rr, period_days, timestamp
                FROM symbol_performance 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (symbol,))
            
            row = cursor.fetchone()
            if row:
                return SymbolPerformance(
                    symbol=row[0],
                    total_trades=row[1],
                    win_rate=row[2],
                    profit_factor=row[3],
                    sharpe_ratio=row[4],
                    max_drawdown=row[5],
                    average_rr=row[6],
                    period_days=row[7],
                    timestamp=row[8]
                )
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get performance: {e}")
            return None
    
    def optimize_symbol(self, symbol: str, metric: OptimizationMetric) -> Optional[OptimizationResult]:
        """Optimize symbol parameters for specific metric"""
        try:
            # Get current performance
            current_perf = self.get_latest_performance(symbol)
            if not current_perf or current_perf.total_trades < 50:
                logger.debug(f"Insufficient data for {symbol} optimization (requires 50+ trades, current: {current_perf.total_trades if current_perf else 0})")
                return None
            
            # Get current parameters
            current_params = self._get_current_parameters(symbol)
            if not current_params:
                logger.warning(f"⚠️ No parameters found for {symbol}")
                return None
            
            # Generate optimized parameters
            optimized_params = self._generate_optimized_parameters(symbol, metric, current_perf, current_params)
            if not optimized_params:
                logger.warning(f"⚠️ No optimization found for {symbol}")
                return None
            
            # Calculate improvement
            current_value = self._get_metric_value(current_perf, metric)
            improvement = self._calculate_improvement(current_value, optimized_params, metric)
            
            # Create optimization result
            result = OptimizationResult(
                symbol=symbol,
                metric=metric,
                old_value=current_value,
                new_value=current_value + improvement,
                improvement=improvement,
                parameters=optimized_params,
                timestamp=time.time(),
                status=OptimizationStatus.COMPLETED
            )
            
            # Save result
            self.connection.execute("""
                INSERT INTO optimization_results 
                (symbol, metric, old_value, new_value, improvement, parameters, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.symbol,
                result.metric.value,
                result.old_value,
                result.new_value,
                result.improvement,
                json.dumps(result.parameters),
                result.timestamp,
                result.status.value
            ))
            self.connection.commit()
            
            logger.info(f"✅ Optimized {symbol} for {metric.value}: {improvement:.2%} improvement")
            return result
            
        except Exception as e:
            logger.error(f"❌ Optimization failed for {symbol}: {e}")
            return None
    
    def _get_current_parameters(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current symbol parameters from config"""
        try:
            from config.symbol_config_loader import get_config_loader
            loader = get_config_loader()
            config = loader.get_config(symbol)
            if config:
                return {
                    "vwap": config.vwap.__dict__ if hasattr(config, 'vwap') else {},
                    "atr": config.atr.__dict__ if hasattr(config, 'atr') else {},
                    "spread_filter": config.spread_filter.__dict__ if hasattr(config, 'spread_filter') else {},
                    "risk": config.risk.__dict__ if hasattr(config, 'risk') else {}
                }
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get parameters for {symbol}: {e}")
            return None
    
    def _generate_optimized_parameters(self, symbol: str, metric: OptimizationMetric, 
                                     performance: SymbolPerformance, 
                                     current_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate optimized parameters based on performance"""
        try:
            optimized = current_params.copy()
            
            # Optimize based on metric
            if metric == OptimizationMetric.WIN_RATE:
                # Increase filter strictness for better win rate
                if "spread_filter" in optimized:
                    optimized["spread_filter"]["normal_spread_threshold"] *= 0.9
                    optimized["spread_filter"]["elevated_spread_threshold"] *= 0.9
                
            elif metric == OptimizationMetric.PROFIT_FACTOR:
                # Optimize risk parameters for better profit factor
                if "risk" in optimized:
                    optimized["risk"]["max_risk_per_trade"] *= 1.1
                    optimized["risk"]["max_daily_risk"] *= 1.05
                
            elif metric == OptimizationMetric.SHARPE_RATIO:
                # Balance risk and reward for better Sharpe ratio
                if "atr" in optimized:
                    optimized["atr"]["atr_multiplier"] *= 1.05
                
            elif metric == OptimizationMetric.MAX_DRAWDOWN:
                # Reduce risk for lower drawdown
                if "risk" in optimized:
                    optimized["risk"]["max_risk_per_trade"] *= 0.9
                    optimized["risk"]["max_daily_risk"] *= 0.9
                
            elif metric == OptimizationMetric.AVERAGE_RR:
                # Optimize for better risk-reward ratio
                if "atr" in optimized:
                    optimized["atr"]["atr_multiplier"] *= 1.1
                if "risk" in optimized:
                    optimized["risk"]["max_risk_per_trade"] *= 0.95
            
            return optimized
            
        except Exception as e:
            logger.error(f"❌ Failed to generate optimized parameters: {e}")
            return None
    
    def _get_metric_value(self, performance: SymbolPerformance, metric: OptimizationMetric) -> float:
        """Get metric value from performance"""
        if metric == OptimizationMetric.WIN_RATE:
            return performance.win_rate
        elif metric == OptimizationMetric.PROFIT_FACTOR:
            return performance.profit_factor
        elif metric == OptimizationMetric.SHARPE_RATIO:
            return performance.sharpe_ratio
        elif metric == OptimizationMetric.MAX_DRAWDOWN:
            return performance.max_drawdown
        elif metric == OptimizationMetric.AVERAGE_RR:
            return performance.average_rr
        return 0.0
    
    def _calculate_improvement(self, current_value: float, optimized_params: Dict[str, Any], 
                             metric: OptimizationMetric) -> float:
        """Calculate expected improvement from optimized parameters"""
        # Simple heuristic-based improvement calculation
        if metric == OptimizationMetric.WIN_RATE:
            return 0.05  # 5% improvement expected
        elif metric == OptimizationMetric.PROFIT_FACTOR:
            return 0.1   # 10% improvement expected
        elif metric == OptimizationMetric.SHARPE_RATIO:
            return 0.08  # 8% improvement expected
        elif metric == OptimizationMetric.MAX_DRAWDOWN:
            return -0.05  # 5% reduction in drawdown
        elif metric == OptimizationMetric.AVERAGE_RR:
            return 0.15  # 15% improvement expected
        return 0.0
    
    def get_optimization_history(self, symbol: str, limit: int = 10) -> List[OptimizationResult]:
        """Get optimization history for symbol"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT symbol, metric, old_value, new_value, improvement, 
                       parameters, timestamp, status
                FROM optimization_results 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (symbol, limit))
            
            results = []
            for row in cursor.fetchall():
                results.append(OptimizationResult(
                    symbol=row[0],
                    metric=OptimizationMetric(row[1]),
                    old_value=row[2],
                    new_value=row[3],
                    improvement=row[4],
                    parameters=json.loads(row[5]),
                    timestamp=row[6],
                    status=OptimizationStatus(row[7])
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to get optimization history: {e}")
            return []
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get optimization summary across all symbols"""
        try:
            cursor = self.connection.cursor()
            
            # Get total optimizations
            cursor.execute("SELECT COUNT(*) FROM optimization_results")
            total_optimizations = cursor.fetchone()[0]
            
            # Get successful optimizations
            cursor.execute("SELECT COUNT(*) FROM optimization_results WHERE status = 'completed'")
            successful_optimizations = cursor.fetchone()[0]
            
            # Get average improvement
            cursor.execute("SELECT AVG(improvement) FROM optimization_results WHERE status = 'completed'")
            avg_improvement = cursor.fetchone()[0] or 0.0
            
            # Get symbols with most optimizations
            cursor.execute("""
                SELECT symbol, COUNT(*) as count 
                FROM optimization_results 
                GROUP BY symbol 
                ORDER BY count DESC 
                LIMIT 5
            """)
            top_symbols = [{"symbol": row[0], "count": row[1]} for row in cursor.fetchall()]
            
            return {
                "total_optimizations": total_optimizations,
                "successful_optimizations": successful_optimizations,
                "success_rate": successful_optimizations / max(total_optimizations, 1),
                "average_improvement": avg_improvement,
                "top_symbols": top_symbols,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get optimization summary: {e}")
            return {}

# Global instance
_symbol_optimizer = None

def get_symbol_optimizer() -> SymbolOptimizer:
    """Get global symbol optimizer instance"""
    global _symbol_optimizer
    if _symbol_optimizer is None:
        _symbol_optimizer = SymbolOptimizer()
    return _symbol_optimizer
