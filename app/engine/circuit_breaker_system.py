"""
Circuit Breaker System
System protection mechanisms for risk management
"""

import numpy as np
from numba import jit, prange
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import logging
from dataclasses import dataclass
from enum import Enum
import threading
import time

logger = logging.getLogger(__name__)

class BreakerType(Enum):
    """Circuit breaker types"""
    DRAWDOWN = "drawdown"
    LOSS_LIMIT = "loss_limit"
    VOLATILITY = "volatility"
    LATENCY = "latency"
    DATA_QUALITY = "data_quality"
    SYSTEM_OVERLOAD = "system_overload"

class BreakerStatus(Enum):
    """Circuit breaker status"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Breaker triggered, operations stopped
    HALF_OPEN = "half_open"  # Testing if conditions have improved

@dataclass
class BreakerEvent:
    """Circuit breaker event"""
    breaker_type: BreakerType
    status: BreakerStatus
    trigger_value: float
    threshold: float
    timestamp_ms: int
    duration_ms: int
    reasoning: str
    context: Dict[str, Any]

class CircuitBreakerSystem:
    """Circuit breaker system for risk management"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.symbol = symbol_config.get('symbol', 'unknown')
        
        # Breaker configuration
        self.breaker_config = symbol_config.get('breaker_config', {})
        self.max_drawdown = self.breaker_config.get('max_drawdown', 0.05)  # 5%
        self.max_loss_limit = self.breaker_config.get('max_loss_limit', 1000.0)
        self.max_volatility = self.breaker_config.get('max_volatility', 0.02)  # 2%
        self.max_latency_ms = self.breaker_config.get('max_latency_ms', 200)
        self.min_data_quality = self.breaker_config.get('min_data_quality', 0.8)
        self.max_system_load = self.breaker_config.get('max_system_load', 0.8)
        
        # Breaker state
        self.breakers = {
            BreakerType.DRAWDOWN: BreakerStatus.CLOSED,
            BreakerType.LOSS_LIMIT: BreakerStatus.CLOSED,
            BreakerType.VOLATILITY: BreakerStatus.CLOSED,
            BreakerType.LATENCY: BreakerStatus.CLOSED,
            BreakerType.DATA_QUALITY: BreakerStatus.CLOSED,
            BreakerType.SYSTEM_OVERLOAD: BreakerStatus.CLOSED
        }
        
        # Breaker history
        self.breaker_history = []
        self.breaker_events = []
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Performance tracking
        self.performance_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown_seen': 0.0,
            'current_drawdown': 0.0,
            'peak_equity': 0.0
        }
        
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_drawdown(equity_values: np.ndarray) -> float:
        """Calculate current drawdown using Numba"""
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
    def calculate_volatility(prices: np.ndarray, lookback: int) -> float:
        """Calculate price volatility using Numba"""
        if len(prices) < lookback:
            return 0.0
        
        recent_prices = prices[-lookback:]
        returns = np.zeros(len(recent_prices) - 1)
        
        for i in range(1, len(recent_prices)):
            returns[i-1] = (recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]
        
        return np.std(returns)
    
    def check_drawdown_breaker(self, current_equity: float) -> bool:
        """Check drawdown circuit breaker"""
        try:
            with self.lock:
                # Update performance metrics
                self.performance_metrics['peak_equity'] = max(
                    self.performance_metrics['peak_equity'], current_equity
                )
                
                # Calculate current drawdown
                if self.performance_metrics['peak_equity'] > 0:
                    current_drawdown = (self.performance_metrics['peak_equity'] - current_equity) / self.performance_metrics['peak_equity']
                    self.performance_metrics['current_drawdown'] = current_drawdown
                    self.performance_metrics['max_drawdown_seen'] = max(
                        self.performance_metrics['max_drawdown_seen'], current_drawdown
                    )
                    
                    # Check if drawdown exceeds threshold
                    if current_drawdown > self.max_drawdown:
                        self._trigger_breaker(
                            BreakerType.DRAWDOWN,
                            current_drawdown,
                            self.max_drawdown,
                            f"Drawdown {current_drawdown:.3f} exceeds limit {self.max_drawdown:.3f}"
                        )
                        return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error checking drawdown breaker: {e}")
            return False
    
    def check_loss_limit_breaker(self, trade_pnl: float) -> bool:
        """Check loss limit circuit breaker"""
        try:
            with self.lock:
                # Update total PnL
                self.performance_metrics['total_pnl'] += trade_pnl
                
                # Check if loss limit exceeded
                if self.performance_metrics['total_pnl'] < -self.max_loss_limit:
                    self._trigger_breaker(
                        BreakerType.LOSS_LIMIT,
                        abs(self.performance_metrics['total_pnl']),
                        self.max_loss_limit,
                        f"Loss limit {abs(self.performance_metrics['total_pnl']):.2f} exceeds limit {self.max_loss_limit:.2f}"
                    )
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error checking loss limit breaker: {e}")
            return False
    
    def check_volatility_breaker(self, price_data: List[float]) -> bool:
        """Check volatility circuit breaker"""
        try:
            if len(price_data) < 20:
                return False
            
            prices = np.array(price_data, dtype=np.float32)
            volatility = self.calculate_volatility(prices, 20)
            
            if volatility > self.max_volatility:
                self._trigger_breaker(
                    BreakerType.VOLATILITY,
                    volatility,
                    self.max_volatility,
                    f"Volatility {volatility:.4f} exceeds limit {self.max_volatility:.4f}"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking volatility breaker: {e}")
            return False
    
    def check_latency_breaker(self, latency_ms: float) -> bool:
        """Check latency circuit breaker"""
        try:
            if latency_ms > self.max_latency_ms:
                self._trigger_breaker(
                    BreakerType.LATENCY,
                    latency_ms,
                    self.max_latency_ms,
                    f"Latency {latency_ms:.1f}ms exceeds limit {self.max_latency_ms}ms"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking latency breaker: {e}")
            return False
    
    def check_data_quality_breaker(self, data_quality_score: float) -> bool:
        """Check data quality circuit breaker"""
        try:
            if data_quality_score < self.min_data_quality:
                self._trigger_breaker(
                    BreakerType.DATA_QUALITY,
                    data_quality_score,
                    self.min_data_quality,
                    f"Data quality {data_quality_score:.3f} below limit {self.min_data_quality:.3f}"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking data quality breaker: {e}")
            return False
    
    def check_system_overload_breaker(self, system_load: float) -> bool:
        """Check system overload circuit breaker"""
        try:
            if system_load > self.max_system_load:
                self._trigger_breaker(
                    BreakerType.SYSTEM_OVERLOAD,
                    system_load,
                    self.max_system_load,
                    f"System load {system_load:.3f} exceeds limit {self.max_system_load:.3f}"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking system overload breaker: {e}")
            return False
    
    def _trigger_breaker(
        self, 
        breaker_type: BreakerType, 
        trigger_value: float, 
        threshold: float, 
        reasoning: str
    ):
        """Trigger a circuit breaker"""
        try:
            with self.lock:
                # Update breaker status
                self.breakers[breaker_type] = BreakerStatus.OPEN
                
                # Create breaker event
                event = BreakerEvent(
                    breaker_type=breaker_type,
                    status=BreakerStatus.OPEN,
                    trigger_value=trigger_value,
                    threshold=threshold,
                    timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                    duration_ms=0,
                    reasoning=reasoning,
                    context={
                        'symbol': self.symbol,
                        'performance_metrics': self.performance_metrics.copy()
                    }
                )
                
                # Store event
                self.breaker_events.append(event)
                self.breaker_history.append(event)
                
                # Keep only recent history
                if len(self.breaker_history) > 1000:
                    self.breaker_history = self.breaker_history[-1000:]
                
                logger.warning(f"Circuit breaker triggered: {breaker_type.value} - {reasoning}")
                
        except Exception as e:
            logger.error(f"Error triggering breaker {breaker_type.value}: {e}")
    
    def reset_breaker(self, breaker_type: BreakerType, reasoning: str = "Manual reset"):
        """Reset a circuit breaker"""
        try:
            with self.lock:
                if self.breakers[breaker_type] == BreakerStatus.OPEN:
                    self.breakers[breaker_type] = BreakerStatus.CLOSED
                    
                    # Create reset event
                    event = BreakerEvent(
                        breaker_type=breaker_type,
                        status=BreakerStatus.CLOSED,
                        trigger_value=0.0,
                        threshold=0.0,
                        timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                        duration_ms=0,
                        reasoning=reasoning,
                        context={'symbol': self.symbol}
                    )
                    
                    self.breaker_events.append(event)
                    logger.info(f"Circuit breaker reset: {breaker_type.value} - {reasoning}")
                
        except Exception as e:
            logger.error(f"Error resetting breaker {breaker_type.value}: {e}")
    
    def is_breaker_open(self, breaker_type: BreakerType) -> bool:
        """Check if a specific breaker is open"""
        with self.lock:
            return self.breakers[breaker_type] == BreakerStatus.OPEN
    
    def is_any_breaker_open(self) -> bool:
        """Check if any breaker is open"""
        with self.lock:
            return any(status == BreakerStatus.OPEN for status in self.breakers.values())
    
    def get_open_breakers(self) -> List[BreakerType]:
        """Get list of open breakers"""
        with self.lock:
            return [breaker_type for breaker_type, status in self.breakers.items() 
                   if status == BreakerStatus.OPEN]
    
    def get_breaker_status(self) -> Dict[str, str]:
        """Get status of all breakers"""
        with self.lock:
            return {breaker_type.value: status.value for breaker_type, status in self.breakers.items()}
    
    def get_breaker_statistics(self) -> Dict[str, Any]:
        """Get breaker statistics"""
        with self.lock:
            # Count by breaker type
            breaker_type_counts = {}
            for event in self.breaker_history:
                breaker_type = event.breaker_type.value
                breaker_type_counts[breaker_type] = breaker_type_counts.get(breaker_type, 0) + 1
            
            # Count by status
            status_counts = {}
            for event in self.breaker_history:
                status = event.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Calculate average trigger values
            trigger_values = {}
            for event in self.breaker_history:
                breaker_type = event.breaker_type.value
                if breaker_type not in trigger_values:
                    trigger_values[breaker_type] = []
                trigger_values[breaker_type].append(event.trigger_value)
            
            avg_trigger_values = {}
            for breaker_type, values in trigger_values.items():
                avg_trigger_values[breaker_type] = np.mean(values) if values else 0.0
            
            return {
                'total_events': len(self.breaker_history),
                'open_breakers': len(self.get_open_breakers()),
                'breaker_type_counts': breaker_type_counts,
                'status_counts': status_counts,
                'average_trigger_values': avg_trigger_values,
                'performance_metrics': self.performance_metrics.copy(),
                'symbol': self.symbol
            }
    
    def update_trade_result(self, trade_pnl: float, trade_result: str):
        """Update performance metrics with trade result"""
        try:
            with self.lock:
                self.performance_metrics['total_trades'] += 1
                self.performance_metrics['total_pnl'] += trade_pnl
                
                if trade_result == 'win':
                    self.performance_metrics['winning_trades'] += 1
                elif trade_result == 'loss':
                    self.performance_metrics['losing_trades'] += 1
                
                # Update peak equity
                current_equity = self.performance_metrics['total_pnl']
                self.performance_metrics['peak_equity'] = max(
                    self.performance_metrics['peak_equity'], current_equity
                )
                
        except Exception as e:
            logger.error(f"Error updating trade result: {e}")

# Example usage and testing
if __name__ == "__main__":
    # Test configuration
    test_config = {
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
    
    # Create circuit breaker system
    breaker_system = CircuitBreakerSystem(test_config)
    
    print("Testing Circuit Breaker System:")
    
    # Test drawdown breaker
    print(f"Testing drawdown breaker (limit: {test_config['breaker_config']['max_drawdown']})")
    breaker_system.performance_metrics['peak_equity'] = 10000.0
    drawdown_triggered = breaker_system.check_drawdown_breaker(9000.0)  # 10% drawdown
    print(f"Drawdown breaker triggered: {drawdown_triggered}")
    
    # Test loss limit breaker
    print(f"Testing loss limit breaker (limit: {test_config['breaker_config']['max_loss_limit']})")
    loss_triggered = breaker_system.check_loss_limit_breaker(-1200.0)  # -$1200 loss
    print(f"Loss limit breaker triggered: {loss_triggered}")
    
    # Test volatility breaker
    print(f"Testing volatility breaker (limit: {test_config['breaker_config']['max_volatility']})")
    price_data = [100.0, 102.0, 98.0, 105.0, 95.0, 110.0, 90.0, 115.0, 85.0, 120.0] * 3
    volatility_triggered = breaker_system.check_volatility_breaker(price_data)
    print(f"Volatility breaker triggered: {volatility_triggered}")
    
    # Test latency breaker
    print(f"Testing latency breaker (limit: {test_config['breaker_config']['max_latency_ms']}ms)")
    latency_triggered = breaker_system.check_latency_breaker(250.0)  # 250ms latency
    print(f"Latency breaker triggered: {latency_triggered}")
    
    # Get breaker status
    status = breaker_system.get_breaker_status()
    print(f"Breaker Status: {status}")
    
    # Get statistics
    stats = breaker_system.get_breaker_statistics()
    print(f"Breaker Statistics: {stats}")
