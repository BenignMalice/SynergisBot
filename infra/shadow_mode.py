"""
Shadow Mode System

This module implements a comprehensive shadow mode system that allows running
DTMS (Dynamic Trade Management System) alongside Intelligent Exits for 2-3 weeks
to compare performance and validate the new system before full deployment.

Key Features:
- Parallel execution of DTMS and Intelligent Exits
- Performance comparison and metrics collection
- A/B testing capabilities with configurable traffic splitting
- Shadow mode duration management and automatic expiration
- Decision trace comparison and analysis
- Risk-free validation of new trading logic
"""

import time
import json
import logging
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
import asyncio

logger = logging.getLogger(__name__)

class ShadowModeStatus(Enum):
    """Shadow mode status"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    EXPIRED = "expired"
    DISABLED = "disabled"
    ERROR = "error"

class ExecutionMode(Enum):
    """Execution mode for trades"""
    INTELLIGENT_EXIT = "intelligent_exit"
    DTMS = "dtms"
    SHADOW = "shadow"
    COMPARISON = "comparison"

class ComparisonResult(Enum):
    """Comparison result between systems"""
    DTMS_BETTER = "dtms_better"
    INTELLIGENT_BETTER = "intelligent_better"
    EQUIVALENT = "equivalent"
    INCONCLUSIVE = "inconclusive"

class ShadowModeConfig:
    """Shadow mode configuration"""
    def __init__(self,
                 duration_days: int = 14,
                 traffic_split: float = 0.5,
                 enable_metrics: bool = True,
                 enable_traces: bool = True,
                 auto_expire: bool = True,
                 comparison_threshold: float = 0.05):
        self.duration_days = duration_days
        self.traffic_split = traffic_split  # 0.0 to 1.0, portion for DTMS
        self.enable_metrics = enable_metrics
        self.enable_traces = enable_traces
        self.auto_expire = auto_expire
        self.comparison_threshold = comparison_threshold

@dataclass
class ShadowTrade:
    """Shadow trade execution"""
    trade_id: str
    symbol: str
    timestamp: float
    intelligent_exit_result: Dict[str, Any]
    dtms_result: Dict[str, Any]
    execution_mode: ExecutionMode
    comparison_result: Optional[ComparisonResult] = None
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    trace_hash: Optional[str] = None

@dataclass
class ShadowMetrics:
    """Shadow mode performance metrics"""
    total_trades: int = 0
    dtms_trades: int = 0
    intelligent_trades: int = 0
    shadow_trades: int = 0
    dtms_better_count: int = 0
    intelligent_better_count: int = 0
    equivalent_count: int = 0
    inconclusive_count: int = 0
    avg_dtms_latency_ms: float = 0.0
    avg_intelligent_latency_ms: float = 0.0
    dtms_success_rate: float = 0.0
    intelligent_success_rate: float = 0.0
    dtms_profit_factor: float = 0.0
    intelligent_profit_factor: float = 0.0

@dataclass
class ShadowTrace:
    """Shadow mode decision trace"""
    trace_id: str
    timestamp: float
    symbol: str
    intelligent_trace: Dict[str, Any]
    dtms_trace: Dict[str, Any]
    comparison_analysis: Dict[str, Any]
    performance_delta: Dict[str, float]

class ShadowModeManager:
    """Manages shadow mode execution and comparison"""
    
    def __init__(self, config: ShadowModeConfig):
        self.config = config
        self.status = ShadowModeStatus.INACTIVE
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.trades: List[ShadowTrade] = []
        self.traces: List[ShadowTrace] = []
        self.metrics = ShadowMetrics()
        self.lock = threading.RLock()
        
        # Callbacks
        self.on_trade_executed: Optional[Callable[[ShadowTrade], None]] = None
        self.on_comparison_completed: Optional[Callable[[ShadowTrade], None]] = None
        self.on_metrics_updated: Optional[Callable[[ShadowMetrics], None]] = None
        self.on_status_changed: Optional[Callable[[ShadowModeStatus], None]] = None
        
        # Executors
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    def set_callbacks(self,
                      on_trade_executed: Optional[Callable[[ShadowTrade], None]] = None,
                      on_comparison_completed: Optional[Callable[[ShadowTrade], None]] = None,
                      on_metrics_updated: Optional[Callable[[ShadowMetrics], None]] = None,
                      on_status_changed: Optional[Callable[[ShadowModeStatus], None]] = None) -> None:
        """Set callback functions for shadow mode events"""
        self.on_trade_executed = on_trade_executed
        self.on_comparison_completed = on_comparison_completed
        self.on_metrics_updated = on_metrics_updated
        self.on_status_changed = on_status_changed
    
    def start_shadow_mode(self) -> bool:
        """Start shadow mode"""
        with self.lock:
            if self.status != ShadowModeStatus.INACTIVE:
                logger.warning(f"Cannot start shadow mode, current status: {self.status}")
                return False
            
            self.start_time = time.time()
            self.end_time = self.start_time + (self.config.duration_days * 24 * 60 * 60)
            self.status = ShadowModeStatus.ACTIVE
            
            # Reset metrics
            self.metrics = ShadowMetrics()
            
            logger.info(f"Started shadow mode for {self.config.duration_days} days")
            
            # Call status changed callback
            if self.on_status_changed:
                try:
                    self.on_status_changed(self.status)
                except Exception as e:
                    logger.error(f"Error in on_status_changed callback: {e}")
            
            return True
    
    def stop_shadow_mode(self) -> bool:
        """Stop shadow mode"""
        with self.lock:
            if self.status not in [ShadowModeStatus.ACTIVE, ShadowModeStatus.ERROR]:
                logger.warning(f"Cannot stop shadow mode, current status: {self.status}")
                return False
            
            self.status = ShadowModeStatus.INACTIVE
            self.end_time = time.time()
            
            logger.info("Stopped shadow mode")
            
            # Call status changed callback
            if self.on_status_changed:
                try:
                    self.on_status_changed(self.status)
                except Exception as e:
                    logger.error(f"Error in on_status_changed callback: {e}")
            
            return True
    
    def check_expiration(self) -> bool:
        """Check if shadow mode has expired"""
        with self.lock:
            if not self.config.auto_expire or self.status != ShadowModeStatus.ACTIVE:
                return False
            
            if time.time() >= self.end_time:
                self.status = ShadowModeStatus.EXPIRED
                logger.info("Shadow mode expired")
                
                # Call status changed callback
                if self.on_status_changed:
                    try:
                        self.on_status_changed(self.status)
                    except Exception as e:
                        logger.error(f"Error in on_status_changed callback: {e}")
                
                return True
            
            return False
    
    def execute_shadow_trade(self, symbol: str, trade_data: Dict[str, Any]) -> ShadowTrade:
        """Execute a trade in shadow mode"""
        with self.lock:
            if self.status != ShadowModeStatus.ACTIVE:
                raise RuntimeError(f"Shadow mode not active, status: {self.status}")
            
            trade_id = str(uuid.uuid4())
            timestamp = time.time()
            
            # Determine execution mode based on traffic split
            execution_mode = self._determine_execution_mode()
            
            # Execute both systems
            intelligent_result = self._execute_intelligent_exit(symbol, trade_data)
            dtms_result = self._execute_dtms(symbol, trade_data)
            
            # Create shadow trade
            shadow_trade = ShadowTrade(
                trade_id=trade_id,
                symbol=symbol,
                timestamp=timestamp,
                intelligent_exit_result=intelligent_result,
                dtms_result=dtms_result,
                execution_mode=execution_mode
            )
            
            # Compare results if both systems executed
            if execution_mode in [ExecutionMode.SHADOW, ExecutionMode.COMPARISON]:
                shadow_trade.comparison_result = self._compare_results(
                    intelligent_result, dtms_result
                )
                shadow_trade.performance_metrics = self._calculate_performance_metrics(
                    intelligent_result, dtms_result
                )
            
            # Add to trades list
            self.trades.append(shadow_trade)
            
            # Update metrics
            self._update_metrics(shadow_trade)
            
            # Call trade executed callback
            if self.on_trade_executed:
                try:
                    self.on_trade_executed(shadow_trade)
                except Exception as e:
                    logger.error(f"Error in on_trade_executed callback: {e}")
            
            return shadow_trade
    
    def _determine_execution_mode(self) -> ExecutionMode:
        """Determine execution mode based on traffic split"""
        import random
        if random.random() < self.config.traffic_split:
            return ExecutionMode.DTMS
        else:
            return ExecutionMode.INTELLIGENT_EXIT
    
    def _execute_intelligent_exit(self, symbol: str, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute intelligent exit system"""
        start_time = time.time()
        
        try:
            # Simulate intelligent exit execution
            # In real implementation, this would call the actual intelligent exit system
            result = {
                "action": "hold",  # or "exit", "partial_exit"
                "confidence": 0.75,
                "reasoning": "Market structure analysis",
                "latency_ms": (time.time() - start_time) * 1000,
                "timestamp": time.time()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing intelligent exit: {e}")
            return {
                "action": "error",
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
                "timestamp": time.time()
            }
    
    def _execute_dtms(self, symbol: str, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute DTMS system"""
        start_time = time.time()
        
        try:
            # Simulate DTMS execution
            # In real implementation, this would call the actual DTMS system
            result = {
                "action": "partial_exit",  # or "hold", "exit"
                "confidence": 0.82,
                "reasoning": "Multi-timeframe analysis",
                "latency_ms": (time.time() - start_time) * 1000,
                "timestamp": time.time()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing DTMS: {e}")
            return {
                "action": "error",
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
                "timestamp": time.time()
            }
    
    def _compare_results(self, intelligent_result: Dict[str, Any], 
                        dtms_result: Dict[str, Any]) -> ComparisonResult:
        """Compare results between intelligent exit and DTMS"""
        try:
            # Compare confidence levels
            intelligent_confidence = intelligent_result.get("confidence", 0.0)
            dtms_confidence = dtms_result.get("confidence", 0.0)
            
            confidence_diff = abs(intelligent_confidence - dtms_confidence)
            
            if confidence_diff < self.config.comparison_threshold:
                return ComparisonResult.EQUIVALENT
            elif dtms_confidence > intelligent_confidence:
                return ComparisonResult.DTMS_BETTER
            elif intelligent_confidence > dtms_confidence:
                return ComparisonResult.INTELLIGENT_BETTER
            else:
                return ComparisonResult.INCONCLUSIVE
                
        except Exception as e:
            logger.error(f"Error comparing results: {e}")
            return ComparisonResult.INCONCLUSIVE
    
    def _calculate_performance_metrics(self, intelligent_result: Dict[str, Any], 
                                     dtms_result: Dict[str, Any]) -> Dict[str, float]:
        """Calculate performance metrics"""
        try:
            intelligent_latency = intelligent_result.get("latency_ms", 0.0)
            dtms_latency = dtms_result.get("latency_ms", 0.0)
            
            return {
                "latency_delta_ms": dtms_latency - intelligent_latency,
                "confidence_delta": dtms_result.get("confidence", 0.0) - intelligent_result.get("confidence", 0.0),
                "intelligent_latency_ms": intelligent_latency,
                "dtms_latency_ms": dtms_latency
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {}
    
    def _update_metrics(self, shadow_trade: ShadowTrade) -> None:
        """Update shadow mode metrics"""
        with self.lock:
            self.metrics.total_trades += 1
            
            if shadow_trade.execution_mode == ExecutionMode.DTMS:
                self.metrics.dtms_trades += 1
            elif shadow_trade.execution_mode == ExecutionMode.INTELLIGENT_EXIT:
                self.metrics.intelligent_trades += 1
            elif shadow_trade.execution_mode == ExecutionMode.SHADOW:
                self.metrics.shadow_trades += 1
            
            if shadow_trade.comparison_result:
                if shadow_trade.comparison_result == ComparisonResult.DTMS_BETTER:
                    self.metrics.dtms_better_count += 1
                elif shadow_trade.comparison_result == ComparisonResult.INTELLIGENT_BETTER:
                    self.metrics.intelligent_better_count += 1
                elif shadow_trade.comparison_result == ComparisonResult.EQUIVALENT:
                    self.metrics.equivalent_count += 1
                else:
                    self.metrics.inconclusive_count += 1
            
            # Update latency metrics
            if shadow_trade.performance_metrics:
                intelligent_latency = shadow_trade.performance_metrics.get("intelligent_latency_ms", 0.0)
                dtms_latency = shadow_trade.performance_metrics.get("dtms_latency_ms", 0.0)
                
                # Update running averages
                if self.metrics.intelligent_trades > 0:
                    self.metrics.avg_intelligent_latency_ms = (
                        (self.metrics.avg_intelligent_latency_ms * (self.metrics.intelligent_trades - 1) + intelligent_latency) 
                        / self.metrics.intelligent_trades
                    )
                
                if self.metrics.dtms_trades > 0:
                    self.metrics.avg_dtms_latency_ms = (
                        (self.metrics.avg_dtms_latency_ms * (self.metrics.dtms_trades - 1) + dtms_latency) 
                        / self.metrics.dtms_trades
                    )
            
            # Call metrics updated callback
            if self.on_metrics_updated:
                try:
                    self.on_metrics_updated(self.metrics)
                except Exception as e:
                    logger.error(f"Error in on_metrics_updated callback: {e}")
    
    def get_shadow_metrics(self) -> ShadowMetrics:
        """Get current shadow mode metrics"""
        with self.lock:
            return ShadowMetrics(
                total_trades=self.metrics.total_trades,
                dtms_trades=self.metrics.dtms_trades,
                intelligent_trades=self.metrics.intelligent_trades,
                shadow_trades=self.metrics.shadow_trades,
                dtms_better_count=self.metrics.dtms_better_count,
                intelligent_better_count=self.metrics.intelligent_better_count,
                equivalent_count=self.metrics.equivalent_count,
                inconclusive_count=self.metrics.inconclusive_count,
                avg_dtms_latency_ms=self.metrics.avg_dtms_latency_ms,
                avg_intelligent_latency_ms=self.metrics.avg_intelligent_latency_ms,
                dtms_success_rate=self.metrics.dtms_success_rate,
                intelligent_success_rate=self.metrics.intelligent_success_rate,
                dtms_profit_factor=self.metrics.dtms_profit_factor,
                intelligent_profit_factor=self.metrics.intelligent_profit_factor
            )
    
    def get_shadow_trades(self, limit: Optional[int] = None) -> List[ShadowTrade]:
        """Get shadow trades"""
        with self.lock:
            if limit:
                return self.trades[-limit:]
            return list(self.trades)
    
    def get_shadow_traces(self, limit: Optional[int] = None) -> List[ShadowTrace]:
        """Get shadow traces"""
        with self.lock:
            if limit:
                return self.traces[-limit:]
            return list(self.traces)
    
    def generate_comparison_report(self) -> Dict[str, Any]:
        """Generate comprehensive comparison report"""
        with self.lock:
            if not self.trades:
                return {"error": "No trades to compare"}
            
            # Calculate success rates
            dtms_successful = sum(1 for trade in self.trades 
                                if trade.dtms_result.get("action") != "error")
            intelligent_successful = sum(1 for trade in self.trades 
                                       if trade.intelligent_exit_result.get("action") != "error")
            
            dtms_success_rate = dtms_successful / len(self.trades) if self.trades else 0.0
            intelligent_success_rate = intelligent_successful / len(self.trades) if self.trades else 0.0
            
            # Calculate comparison statistics
            total_comparisons = sum(1 for trade in self.trades if trade.comparison_result)
            dtms_better_pct = (self.metrics.dtms_better_count / total_comparisons * 100) if total_comparisons > 0 else 0.0
            intelligent_better_pct = (self.metrics.intelligent_better_count / total_comparisons * 100) if total_comparisons > 0 else 0.0
            equivalent_pct = (self.metrics.equivalent_count / total_comparisons * 100) if total_comparisons > 0 else 0.0
            
            return {
                "summary": {
                    "total_trades": len(self.trades),
                    "duration_days": (time.time() - self.start_time) / (24 * 60 * 60) if self.start_time else 0,
                    "status": self.status.value
                },
                "performance": {
                    "dtms_success_rate": dtms_success_rate,
                    "intelligent_success_rate": intelligent_success_rate,
                    "avg_dtms_latency_ms": self.metrics.avg_dtms_latency_ms,
                    "avg_intelligent_latency_ms": self.metrics.avg_intelligent_latency_ms
                },
                "comparison": {
                    "dtms_better_pct": dtms_better_pct,
                    "intelligent_better_pct": intelligent_better_pct,
                    "equivalent_pct": equivalent_pct,
                    "total_comparisons": total_comparisons
                },
                "recommendation": self._generate_recommendation()
            }
    
    def _generate_recommendation(self) -> str:
        """Generate recommendation based on comparison results"""
        if not self.trades:
            return "Insufficient data for recommendation"
        
        total_comparisons = sum(1 for trade in self.trades if trade.comparison_result)
        if total_comparisons == 0:
            return "No comparisons available"
        
        dtms_better_pct = (self.metrics.dtms_better_count / total_comparisons * 100)
        intelligent_better_pct = (self.metrics.intelligent_better_count / total_comparisons * 100)
        
        if dtms_better_pct > intelligent_better_pct + 10:  # 10% threshold
            return "Recommend switching to DTMS - significantly better performance"
        elif intelligent_better_pct > dtms_better_pct + 10:
            return "Recommend keeping Intelligent Exits - significantly better performance"
        else:
            return "Performance is equivalent - consider gradual migration to DTMS"

class ShadowModeController:
    """Controller for shadow mode operations"""
    
    def __init__(self):
        self.managers: Dict[str, ShadowModeManager] = {}
        self.lock = threading.RLock()
    
    def create_shadow_mode(self, name: str, config: ShadowModeConfig) -> ShadowModeManager:
        """Create a new shadow mode manager"""
        with self.lock:
            if name in self.managers:
                raise ValueError(f"Shadow mode '{name}' already exists")
            
            manager = ShadowModeManager(config)
            self.managers[name] = manager
            logger.info(f"Created shadow mode '{name}'")
            return manager
    
    def get_shadow_mode(self, name: str) -> Optional[ShadowModeManager]:
        """Get shadow mode manager by name"""
        with self.lock:
            return self.managers.get(name)
    
    def remove_shadow_mode(self, name: str) -> bool:
        """Remove shadow mode manager"""
        with self.lock:
            if name not in self.managers:
                return False
            
            manager = self.managers[name]
            if manager.status == ShadowModeStatus.ACTIVE:
                manager.stop_shadow_mode()
            
            del self.managers[name]
            logger.info(f"Removed shadow mode '{name}'")
            return True
    
    def list_shadow_modes(self) -> List[str]:
        """List all shadow mode names"""
        with self.lock:
            return list(self.managers.keys())
    
    def get_all_metrics(self) -> Dict[str, ShadowMetrics]:
        """Get metrics for all shadow modes"""
        with self.lock:
            return {name: manager.get_shadow_metrics() for name, manager in self.managers.items()}

# Global shadow mode controller
_shadow_controller: Optional[ShadowModeController] = None

def get_shadow_controller() -> ShadowModeController:
    """Get global shadow mode controller"""
    global _shadow_controller
    if _shadow_controller is None:
        _shadow_controller = ShadowModeController()
    return _shadow_controller

def create_shadow_mode(name: str, config: ShadowModeConfig) -> ShadowModeManager:
    """Create a new shadow mode"""
    controller = get_shadow_controller()
    return controller.create_shadow_mode(name, config)

def get_shadow_mode(name: str) -> Optional[ShadowModeManager]:
    """Get shadow mode by name"""
    controller = get_shadow_controller()
    return controller.get_shadow_mode(name)

def start_shadow_mode(name: str) -> bool:
    """Start shadow mode"""
    manager = get_shadow_mode(name)
    if not manager:
        return False
    return manager.start_shadow_mode()

def stop_shadow_mode(name: str) -> bool:
    """Stop shadow mode"""
    manager = get_shadow_mode(name)
    if not manager:
        return False
    return manager.stop_shadow_mode()

def execute_shadow_trade(name: str, symbol: str, trade_data: Dict[str, Any]) -> Optional[ShadowTrade]:
    """Execute a trade in shadow mode"""
    manager = get_shadow_mode(name)
    if not manager:
        return None
    return manager.execute_shadow_trade(symbol, trade_data)

if __name__ == "__main__":
    # Example usage
    config = ShadowModeConfig(
        duration_days=14,
        traffic_split=0.5,
        enable_metrics=True,
        enable_traces=True
    )
    
    # Create shadow mode
    manager = create_shadow_mode("dtms_validation", config)
    
    # Start shadow mode
    manager.start_shadow_mode()
    
    # Execute some shadow trades
    for i in range(5):
        trade_data = {
            "symbol": "BTCUSDc",
            "price": 50000.0 + i * 100,
            "volume": 0.01,
            "timestamp": time.time()
        }
        
        shadow_trade = manager.execute_shadow_trade("BTCUSDc", trade_data)
        print(f"Trade {i+1}: {shadow_trade.execution_mode.value}")
    
    # Generate comparison report
    report = manager.generate_comparison_report()
    print(f"Comparison report: {json.dumps(report, indent=2)}")
    
    # Stop shadow mode
    manager.stop_shadow_mode()
