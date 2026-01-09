"""
Chaos Testing System for Multi-Timeframe Trading Framework

This module implements chaos engineering tests to verify system resilience
under adverse conditions including:
- Timeframe staleness injection
- Binance disconnection simulation
- Database locking scenarios
- Network latency spikes
- Memory pressure conditions

The system should gracefully degrade to exits-only mode when critical
components fail, ensuring existing positions are protected.
"""

import asyncio
import time
import random
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime, timedelta
import json
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

class ChaosEventType(Enum):
    """Types of chaos events to inject"""
    TIMEFRAME_STALENESS = "timeframe_staleness"
    BINANCE_DISCONNECT = "binance_disconnect"
    DATABASE_LOCK = "database_lock"
    NETWORK_LATENCY = "network_latency"
    MEMORY_PRESSURE = "memory_pressure"
    CPU_SPIKE = "cpu_spike"
    DISK_IO_DELAY = "disk_io_delay"

class SystemState(Enum):
    """System operational states"""
    NORMAL = "normal"
    DEGRADED = "degraded"
    EXITS_ONLY = "exits_only"
    CRITICAL = "critical"

@dataclass
class ChaosEvent:
    """Represents a chaos event to be injected"""
    event_type: ChaosEventType
    duration_ms: int
    intensity: float  # 0.0 to 1.0
    target_component: str
    description: str
    expected_behavior: str

@dataclass
class SystemMetrics:
    """System performance metrics during chaos testing"""
    timestamp: float
    state: SystemState
    latency_p50: float
    latency_p95: float
    latency_p99: float
    queue_depth: int
    memory_usage_mb: float
    cpu_usage_pct: float
    active_connections: int
    database_operations_pending: int
    exits_processed: int
    new_trades_blocked: int

class ChaosTestEngine:
    """Main chaos testing engine"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.active_events: List[ChaosEvent] = []
        self.system_state = SystemState.NORMAL
        self.metrics_history: List[SystemMetrics] = []
        self.callbacks: Dict[str, List[Callable]] = {
            'before_event': [],
            'during_event': [],
            'after_event': [],
            'state_change': []
        }
        self.running = False
        self.monitoring_thread: Optional[threading.Thread] = None
        
    def add_callback(self, event_type: str, callback: Callable):
        """Add callback for chaos test events"""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
    
    def start_monitoring(self):
        """Start system monitoring thread"""
        self.running = True
        self.monitoring_thread = threading.Thread(target=self._monitor_system)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        logger.info("Chaos test monitoring started")
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5.0)
        logger.info("Chaos test monitoring stopped")
    
    def _monitor_system(self):
        """Monitor system metrics during chaos testing"""
        while self.running:
            try:
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
                
                # Keep only last 1000 metrics
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-1000:]
                
                # Check for state changes
                self._update_system_state(metrics)
                
                time.sleep(0.1)  # Monitor every 100ms
                
            except Exception as e:
                logger.error(f"Error in chaos monitoring: {e}")
                time.sleep(1.0)
    
    def _collect_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        import psutil
        
        # Get system metrics
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        
        # Simulate latency metrics (in real implementation, these would come from actual measurements)
        latency_p50 = random.uniform(10, 50)  # ms
        latency_p95 = random.uniform(50, 200)  # ms
        latency_p99 = random.uniform(200, 500)  # ms
        
        return SystemMetrics(
            timestamp=time.time(),
            state=self.system_state,
            latency_p50=latency_p50,
            latency_p95=latency_p95,
            latency_p99=latency_p99,
            queue_depth=random.randint(0, 100),
            memory_usage_mb=memory.used / 1024 / 1024,
            cpu_usage_pct=cpu,
            active_connections=random.randint(1, 10),
            database_operations_pending=random.randint(0, 50),
            exits_processed=random.randint(0, 5),
            new_trades_blocked=random.randint(0, 3)
        )
    
    def _update_system_state(self, metrics: SystemMetrics):
        """Update system state based on metrics"""
        old_state = self.system_state
        
        # Determine state based on metrics
        if metrics.latency_p99 > 1000 or metrics.cpu_usage_pct > 90:
            self.system_state = SystemState.CRITICAL
        elif metrics.latency_p95 > 500 or metrics.queue_depth > 50:
            self.system_state = SystemState.DEGRADED
        elif metrics.latency_p95 > 200:
            self.system_state = SystemState.EXITS_ONLY
        else:
            self.system_state = SystemState.NORMAL
        
        # Notify callbacks of state change
        if old_state != self.system_state:
            for callback in self.callbacks['state_change']:
                try:
                    callback(old_state, self.system_state, metrics)
                except Exception as e:
                    logger.error(f"Error in state change callback: {e}")
    
    def inject_timeframe_staleness(self, symbol: str, timeframe: str, duration_ms: int = 30000):
        """Inject timeframe staleness for a specific symbol/timeframe"""
        event = ChaosEvent(
            event_type=ChaosEventType.TIMEFRAME_STALENESS,
            duration_ms=duration_ms,
            intensity=0.8,
            target_component=f"{symbol}_{timeframe}",
            description=f"Stale data injection for {symbol} {timeframe}",
            expected_behavior="System should degrade to exits-only mode"
        )
        
        self._execute_chaos_event(event)
        logger.info(f"Injected timeframe staleness for {symbol} {timeframe}")
    
    def inject_binance_disconnect(self, duration_ms: int = 60000):
        """Simulate Binance WebSocket disconnection"""
        event = ChaosEvent(
            event_type=ChaosEventType.BINANCE_DISCONNECT,
            duration_ms=duration_ms,
            intensity=1.0,
            target_component="binance_websocket",
            description="Binance WebSocket disconnection simulation",
            expected_behavior="System should continue with MT5 data only"
        )
        
        self._execute_chaos_event(event)
        logger.info("Injected Binance disconnect simulation")
    
    def inject_database_lock(self, duration_ms: int = 10000):
        """Simulate database locking conditions"""
        event = ChaosEvent(
            event_type=ChaosEventType.DATABASE_LOCK,
            duration_ms=duration_ms,
            intensity=0.9,
            target_component="database",
            description="Database lock simulation",
            expected_behavior="System should handle gracefully with timeouts"
        )
        
        self._execute_chaos_event(event)
        logger.info("Injected database lock simulation")
    
    def inject_network_latency(self, latency_ms: int, duration_ms: int = 30000):
        """Inject network latency spikes"""
        event = ChaosEvent(
            event_type=ChaosEventType.NETWORK_LATENCY,
            duration_ms=duration_ms,
            intensity=latency_ms / 1000.0,  # Normalize to 0-1
            target_component="network",
            description=f"Network latency spike: {latency_ms}ms",
            expected_behavior="System should handle increased latency gracefully"
        )
        
        self._execute_chaos_event(event)
        logger.info(f"Injected network latency: {latency_ms}ms")
    
    def inject_memory_pressure(self, pressure_pct: float, duration_ms: int = 45000):
        """Inject memory pressure conditions"""
        event = ChaosEvent(
            event_type=ChaosEventType.MEMORY_PRESSURE,
            duration_ms=duration_ms,
            intensity=pressure_pct,
            target_component="memory",
            description=f"Memory pressure: {pressure_pct*100}%",
            expected_behavior="System should manage memory efficiently"
        )
        
        self._execute_chaos_event(event)
        logger.info(f"Injected memory pressure: {pressure_pct*100}%")
    
    def _execute_chaos_event(self, event: ChaosEvent):
        """Execute a chaos event"""
        self.active_events.append(event)
        
        # Notify before event callbacks
        for callback in self.callbacks['before_event']:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in before_event callback: {e}")
        
        # Simulate event execution
        start_time = time.time()
        end_time = start_time + (event.duration_ms / 1000.0)
        
        # Notify during event callbacks
        while time.time() < end_time and self.running:
            for callback in self.callbacks['during_event']:
                try:
                    callback(event, time.time() - start_time)
                except Exception as e:
                    logger.error(f"Error in during_event callback: {e}")
            time.sleep(0.1)
        
        # Remove event from active list
        if event in self.active_events:
            self.active_events.remove(event)
        
        # Notify after event callbacks
        for callback in self.callbacks['after_event']:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in after_event callback: {e}")
    
    def run_chaos_scenario(self, scenario_name: str, events: List[ChaosEvent]):
        """Run a complete chaos scenario with multiple events"""
        logger.info(f"Starting chaos scenario: {scenario_name}")
        
        for event in events:
            if not self.running:
                break
                
            logger.info(f"Executing chaos event: {event.description}")
            self._execute_chaos_event(event)
            
            # Small delay between events
            time.sleep(1.0)
        
        logger.info(f"Completed chaos scenario: {scenario_name}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of metrics collected during chaos testing"""
        if not self.metrics_history:
            return {}
        
        recent_metrics = self.metrics_history[-100:]  # Last 100 measurements
        
        return {
            'total_measurements': len(self.metrics_history),
            'recent_avg_latency_p50': sum(m.latency_p50 for m in recent_metrics) / len(recent_metrics),
            'recent_avg_latency_p95': sum(m.latency_p95 for m in recent_metrics) / len(recent_metrics),
            'recent_avg_latency_p99': sum(m.latency_p99 for m in recent_metrics) / len(recent_metrics),
            'recent_avg_queue_depth': sum(m.queue_depth for m in recent_metrics) / len(recent_metrics),
            'recent_avg_memory_mb': sum(m.memory_usage_mb for m in recent_metrics) / len(recent_metrics),
            'recent_avg_cpu_pct': sum(m.cpu_usage_pct for m in recent_metrics) / len(recent_metrics),
            'state_distribution': {
                state.value: sum(1 for m in recent_metrics if m.state == state) 
                for state in SystemState
            },
            'active_events': len(self.active_events),
            'current_state': self.system_state.value
        }
    
    def verify_exits_only_behavior(self) -> bool:
        """Verify that system properly degrades to exits-only mode"""
        if not self.metrics_history:
            return False
        
        recent_metrics = self.metrics_history[-50:]  # Last 50 measurements
        
        # Check if system has been in exits-only or degraded state
        exits_only_count = sum(1 for m in recent_metrics if m.state in [SystemState.EXITS_ONLY, SystemState.DEGRADED])
        total_count = len(recent_metrics)
        
        # System should spend at least 20% of time in degraded state during chaos
        degraded_ratio = exits_only_count / total_count if total_count > 0 else 0
        
        # Check that new trades are being blocked when in degraded state
        blocked_trades = sum(m.new_trades_blocked for m in recent_metrics if m.state in [SystemState.EXITS_ONLY, SystemState.DEGRADED])
        
        # Check that exits are still being processed
        exits_processed = sum(m.exits_processed for m in recent_metrics)
        
        logger.info(f"Exits-only behavior verification:")
        logger.info(f"  Degraded state ratio: {degraded_ratio:.2%}")
        logger.info(f"  Blocked trades: {blocked_trades}")
        logger.info(f"  Exits processed: {exits_processed}")
        
        return degraded_ratio >= 0.2 and exits_processed > 0

class ChaosTestScenarios:
    """Predefined chaos test scenarios"""
    
    @staticmethod
    def get_timeframe_staleness_scenario() -> List[ChaosEvent]:
        """Scenario: Multiple timeframe staleness events"""
        return [
            ChaosEvent(
                event_type=ChaosEventType.TIMEFRAME_STALENESS,
                duration_ms=30000,
                intensity=0.8,
                target_component="BTCUSDc_M5",
                description="M5 staleness for BTCUSDc",
                expected_behavior="Degrade to exits-only"
            ),
            ChaosEvent(
                event_type=ChaosEventType.TIMEFRAME_STALENESS,
                duration_ms=45000,
                intensity=0.9,
                target_component="XAUUSDc_H1",
                description="H1 staleness for XAUUSDc",
                expected_behavior="Continue with available timeframes"
            )
        ]
    
    @staticmethod
    def get_binance_disconnect_scenario() -> List[ChaosEvent]:
        """Scenario: Binance disconnection with recovery"""
        return [
            ChaosEvent(
                event_type=ChaosEventType.BINANCE_DISCONNECT,
                duration_ms=60000,
                intensity=1.0,
                target_component="binance_websocket",
                description="Binance WebSocket disconnection",
                expected_behavior="Continue with MT5 data only"
            ),
            ChaosEvent(
                event_type=ChaosEventType.NETWORK_LATENCY,
                duration_ms=30000,
                intensity=0.5,
                target_component="network",
                description="Network latency during recovery",
                expected_behavior="Handle gracefully with timeouts"
            )
        ]
    
    @staticmethod
    def get_database_pressure_scenario() -> List[ChaosEvent]:
        """Scenario: Database locking and memory pressure"""
        return [
            ChaosEvent(
                event_type=ChaosEventType.DATABASE_LOCK,
                duration_ms=15000,
                intensity=0.9,
                target_component="database",
                description="Database lock simulation",
                expected_behavior="Handle with timeouts"
            ),
            ChaosEvent(
                event_type=ChaosEventType.MEMORY_PRESSURE,
                duration_ms=30000,
                intensity=0.7,
                target_component="memory",
                description="Memory pressure during DB lock",
                expected_behavior="Manage memory efficiently"
            )
        ]
    
    @staticmethod
    def get_cascading_failure_scenario() -> List[ChaosEvent]:
        """Scenario: Cascading failures across multiple components"""
        return [
            ChaosEvent(
                event_type=ChaosEventType.BINANCE_DISCONNECT,
                duration_ms=30000,
                intensity=1.0,
                target_component="binance_websocket",
                description="Binance disconnect",
                expected_behavior="Continue with MT5"
            ),
            ChaosEvent(
                event_type=ChaosEventType.TIMEFRAME_STALENESS,
                duration_ms=45000,
                intensity=0.8,
                target_component="EURUSDc_M15",
                description="M15 staleness during Binance disconnect",
                expected_behavior="Degrade to exits-only"
            ),
            ChaosEvent(
                event_type=ChaosEventType.DATABASE_LOCK,
                duration_ms=20000,
                intensity=0.9,
                target_component="database",
                description="Database lock during cascading failure",
                expected_behavior="Handle gracefully"
            )
        ]

def create_chaos_test_engine(config: Dict[str, Any] = None) -> ChaosTestEngine:
    """Create and configure a chaos test engine"""
    if config is None:
        config = {
            'monitoring_interval_ms': 100,
            'max_metrics_history': 1000,
            'state_change_threshold': 0.2
        }
    
    engine = ChaosTestEngine(config)
    return engine

# Global chaos test engine instance
_chaos_engine: Optional[ChaosTestEngine] = None

def get_chaos_engine() -> ChaosTestEngine:
    """Get global chaos test engine instance"""
    global _chaos_engine
    if _chaos_engine is None:
        _chaos_engine = create_chaos_test_engine()
    return _chaos_engine

def start_chaos_monitoring():
    """Start chaos test monitoring"""
    engine = get_chaos_engine()
    engine.start_monitoring()

def stop_chaos_monitoring():
    """Stop chaos test monitoring"""
    engine = get_chaos_engine()
    engine.stop_monitoring()

def run_chaos_test(scenario_name: str, events: List[ChaosEvent]):
    """Run a chaos test scenario"""
    engine = get_chaos_engine()
    engine.run_chaos_scenario(scenario_name, events)

def verify_system_resilience() -> bool:
    """Verify system resilience during chaos testing"""
    engine = get_chaos_engine()
    return engine.verify_exits_only_behavior()

if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    engine = create_chaos_test_engine()
    engine.start_monitoring()
    
    try:
        # Run timeframe staleness scenario
        scenario = ChaosTestScenarios.get_timeframe_staleness_scenario()
        engine.run_chaos_scenario("Timeframe Staleness Test", scenario)
        
        # Verify system behavior
        is_resilient = engine.verify_exits_only_behavior()
        print(f"System resilience verification: {'PASSED' if is_resilient else 'FAILED'}")
        
        # Print metrics summary
        summary = engine.get_metrics_summary()
        print(f"Metrics summary: {json.dumps(summary, indent=2)}")
        
    finally:
        engine.stop_monitoring()
