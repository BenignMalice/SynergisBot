"""
Staged Activation System

This module implements a staged activation system that:
- Starts with 50% position size for initial validation
- Monitors SLOs (Service Level Objectives) continuously
- Increases to full position size after 200 trades if SLOs are met
- Provides rollback capability if SLOs are violated
- Tracks performance metrics and activation status
"""

import asyncio
import json
import logging
import sqlite3
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
import uuid

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ActivationStage(Enum):
    """Activation stage types"""
    INITIAL = "initial"
    STAGED = "staged"
    FULL = "full"
    ROLLBACK = "rollback"
    SUSPENDED = "suspended"


class SLOStatus(Enum):
    """SLO status types"""
    MET = "met"
    WARNING = "warning"
    VIOLATED = "violated"
    CRITICAL = "critical"


class ActivationTrigger(Enum):
    """Activation trigger types"""
    TRADE_COUNT = "trade_count"
    TIME_ELAPSED = "time_elapsed"
    PERFORMANCE_THRESHOLD = "performance_threshold"
    MANUAL = "manual"
    SLO_VIOLATION = "slo_violation"


@dataclass
class SLOThreshold:
    """SLO threshold definition"""
    name: str
    metric: str
    threshold_value: float
    comparison: str  # 'gt', 'lt', 'gte', 'lte', 'eq'
    window_size: int  # Number of samples to consider
    severity: str  # 'warning', 'critical'
    description: str = ""


@dataclass
class SLOMeasurement:
    """SLO measurement data"""
    slo_name: str
    value: float
    threshold: float
    status: SLOStatus
    timestamp: float
    window_start: float
    window_end: float
    sample_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActivationCriteria:
    """Activation criteria definition"""
    trigger: ActivationTrigger
    threshold_value: float
    window_size: int
    required_slos: List[str]  # SLOs that must be met
    excluded_slos: List[str]  # SLOs that must not be violated
    cooldown_seconds: int = 0
    description: str = ""


@dataclass
class ActivationEvent:
    """Activation event record"""
    event_id: str
    timestamp: float
    from_stage: ActivationStage
    to_stage: ActivationStage
    trigger: ActivationTrigger
    reason: str
    slo_status: Dict[str, SLOStatus]
    performance_metrics: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StagedActivationConfig:
    """Staged activation configuration"""
    initial_position_size: float = 0.5  # 50% of normal position size
    full_position_size: float = 1.0  # 100% of normal position size
    trade_count_threshold: int = 200  # Number of trades to reach before full activation
    time_threshold_hours: int = 168  # 7 days in hours
    performance_threshold: float = 0.8  # Performance score threshold
    slo_check_interval_seconds: int = 60  # How often to check SLOs
    activation_cooldown_seconds: int = 3600  # 1 hour cooldown between activations
    rollback_threshold: int = 3  # Number of SLO violations before rollback
    max_rollbacks: int = 2  # Maximum number of rollbacks allowed
    enable_auto_activation: bool = True
    enable_auto_rollback: bool = True
    log_level: str = "INFO"
    data_retention_days: int = 30


class SLOMonitor:
    """SLO monitoring system"""
    
    def __init__(self, config: StagedActivationConfig):
        self.config = config
        self.slo_thresholds: Dict[str, SLOThreshold] = {}
        self.measurements: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.lock = threading.Lock()
        
    def add_slo_threshold(self, slo: SLOThreshold):
        """Add an SLO threshold"""
        with self.lock:
            self.slo_thresholds[slo.name] = slo
            
    def record_measurement(self, slo_name: str, value: float, timestamp: float = None):
        """Record an SLO measurement"""
        if timestamp is None:
            timestamp = time.time()
            
        with self.lock:
            self.measurements[slo_name].append({
                'value': value,
                'timestamp': timestamp
            })
            
    def check_slo_status(self, slo_name: str) -> Optional[SLOMeasurement]:
        """Check the status of a specific SLO"""
        if slo_name not in self.slo_thresholds:
            return None
            
        slo = self.slo_thresholds[slo_name]
        measurements = self.measurements[slo_name]
        
        if len(measurements) < slo.window_size:
            return None
            
        # Get recent measurements
        recent_measurements = list(measurements)[-slo.window_size:]
        values = [m['value'] for m in recent_measurements]
        timestamps = [m['timestamp'] for m in recent_measurements]
        
        # Calculate aggregated value
        if slo.metric in ['avg', 'mean']:
            aggregated_value = np.mean(values)
        elif slo.metric in ['max', 'maximum']:
            aggregated_value = np.max(values)
        elif slo.metric in ['min', 'minimum']:
            aggregated_value = np.min(values)
        elif slo.metric in ['p95', 'percentile_95']:
            aggregated_value = np.percentile(values, 95)
        elif slo.metric in ['p99', 'percentile_99']:
            aggregated_value = np.percentile(values, 99)
        else:
            aggregated_value = np.mean(values)  # Default to mean
            
        # Check threshold
        status = self._evaluate_threshold(aggregated_value, slo.threshold_value, slo.comparison)
        
        return SLOMeasurement(
            slo_name=slo_name,
            value=aggregated_value,
            threshold=slo.threshold_value,
            status=status,
            timestamp=time.time(),
            window_start=min(timestamps),
            window_end=max(timestamps),
            sample_count=len(values),
            metadata={'raw_values': values}
        )
        
    def _evaluate_threshold(self, value: float, threshold: float, comparison: str) -> SLOStatus:
        """Evaluate threshold comparison"""
        if comparison == 'gt':
            meets_threshold = value > threshold
        elif comparison == 'lt':
            meets_threshold = value < threshold
        elif comparison == 'gte':
            meets_threshold = value >= threshold
        elif comparison == 'lte':
            meets_threshold = value <= threshold
        elif comparison == 'eq':
            meets_threshold = value == threshold
        else:
            meets_threshold = False
            
        if meets_threshold:
            return SLOStatus.MET
        else:
            return SLOStatus.VIOLATED
            
    def get_all_slo_status(self) -> Dict[str, SLOMeasurement]:
        """Get status of all SLOs"""
        status = {}
        for slo_name in self.slo_thresholds:
            measurement = self.check_slo_status(slo_name)
            if measurement:
                status[slo_name] = measurement
        return status


class ActivationManager:
    """Manages staged activation process"""
    
    def __init__(self, config: StagedActivationConfig):
        self.config = config
        self.current_stage = ActivationStage.INITIAL
        self.position_size_multiplier = config.initial_position_size
        self.slo_monitor = SLOMonitor(config)
        self.activation_events: List[ActivationEvent] = []
        self.performance_metrics: Dict[str, float] = {}
        self.trade_count = 0
        self.start_time = time.time()
        self.last_activation_time = 0
        self.rollback_count = 0
        self.lock = threading.Lock()
        
        # Setup default SLOs
        self._setup_default_slos()
        
    def _setup_default_slos(self):
        """Setup default SLO thresholds"""
        default_slos = [
            SLOThreshold(
                name="win_rate",
                metric="avg",
                threshold_value=0.8,
                comparison="gte",
                window_size=50,
                severity="critical",
                description="Win rate must be >= 80%"
            ),
            SLOThreshold(
                name="profit_factor",
                metric="avg",
                threshold_value=2.0,
                comparison="gte",
                window_size=50,
                severity="critical",
                description="Profit factor must be >= 2.0"
            ),
            SLOThreshold(
                name="max_drawdown",
                metric="max",
                threshold_value=0.05,
                comparison="lte",
                window_size=100,
                severity="critical",
                description="Max drawdown must be <= 5%"
            ),
            SLOThreshold(
                name="latency_p95",
                metric="p95",
                threshold_value=200.0,
                comparison="lte",
                window_size=100,
                severity="warning",
                description="P95 latency must be <= 200ms"
            ),
            SLOThreshold(
                name="error_rate",
                metric="avg",
                threshold_value=0.01,
                comparison="lte",
                window_size=100,
                severity="critical",
                description="Error rate must be <= 1%"
            )
        ]
        
        for slo in default_slos:
            self.slo_monitor.add_slo_threshold(slo)
            
    def record_trade(self, trade_data: Dict[str, Any]):
        """Record a trade for activation tracking"""
        with self.lock:
            self.trade_count += 1
            
            # Record performance metrics
            if 'pnl' in trade_data:
                self.slo_monitor.record_measurement('win_rate', 1.0 if trade_data['pnl'] > 0 else 0.0)
                
            if 'profit_factor' in trade_data:
                self.slo_monitor.record_measurement('profit_factor', trade_data['profit_factor'])
                
            if 'drawdown' in trade_data:
                self.slo_monitor.record_measurement('max_drawdown', trade_data['drawdown'])
                
    def record_performance_metric(self, metric_name: str, value: float):
        """Record a performance metric"""
        self.slo_monitor.record_measurement(metric_name, value)
        
    def check_activation_criteria(self) -> Tuple[bool, str, Dict[str, Any]]:
        """Check if activation criteria are met"""
        with self.lock:
            # Check trade count threshold
            if self.trade_count >= self.config.trade_count_threshold:
                slo_status = self.slo_monitor.get_all_slo_status()
                
                # Check if required SLOs are met
                critical_violations = 0
                for slo_name, measurement in slo_status.items():
                    if measurement.status == SLOStatus.VIOLATED:
                        slo = self.slo_monitor.slo_thresholds[slo_name]
                        if slo.severity == 'critical':
                            critical_violations += 1
                            
                if critical_violations == 0:
                    return True, f"Trade count threshold reached ({self.trade_count}/{self.config.trade_count_threshold}) with all SLOs met", {
                        'trade_count': self.trade_count,
                        'slo_status': slo_status,
                        'trigger': ActivationTrigger.TRADE_COUNT
                    }
                else:
                    return False, f"Trade count threshold reached but {critical_violations} critical SLOs violated", {
                        'trade_count': self.trade_count,
                        'slo_status': slo_status,
                        'critical_violations': critical_violations
                    }
                    
            # Check time threshold
            elapsed_hours = (time.time() - self.start_time) / 3600
            if elapsed_hours >= self.config.time_threshold_hours:
                slo_status = self.slo_monitor.get_all_slo_status()
                critical_violations = sum(1 for m in slo_status.values() if m.status == SLOStatus.VIOLATED)
                
                if critical_violations == 0:
                    return True, f"Time threshold reached ({elapsed_hours:.1f}h/{self.config.time_threshold_hours}h) with all SLOs met", {
                        'elapsed_hours': elapsed_hours,
                        'slo_status': slo_status,
                        'trigger': ActivationTrigger.TIME_ELAPSED
                    }
                else:
                    return False, f"Time threshold reached but {critical_violations} critical SLOs violated", {
                        'elapsed_hours': elapsed_hours,
                        'slo_status': slo_status,
                        'critical_violations': critical_violations
                    }
                    
            return False, f"Criteria not met: {self.trade_count}/{self.config.trade_count_threshold} trades, {elapsed_hours:.1f}h/{self.config.time_threshold_hours}h elapsed", {
                'trade_count': self.trade_count,
                'elapsed_hours': elapsed_hours
            }
            
    def activate_next_stage(self, trigger: ActivationTrigger, reason: str, metadata: Dict[str, Any] = None) -> bool:
        """Activate the next stage"""
        with self.lock:
            # Check cooldown
            if time.time() - self.last_activation_time < self.config.activation_cooldown_seconds:
                logger.warning(f"Activation blocked by cooldown: {self.config.activation_cooldown_seconds}s remaining")
                return False
                
            # Determine next stage
            if self.current_stage == ActivationStage.INITIAL:
                next_stage = ActivationStage.STAGED
                new_multiplier = self.config.initial_position_size
            elif self.current_stage == ActivationStage.STAGED:
                next_stage = ActivationStage.FULL
                new_multiplier = self.config.full_position_size
            else:
                logger.warning(f"Cannot activate from stage {self.current_stage}")
                return False
                
            # Create activation event
            event = ActivationEvent(
                event_id=f"ACT_{uuid.uuid4().hex[:8]}",
                timestamp=time.time(),
                from_stage=self.current_stage,
                to_stage=next_stage,
                trigger=trigger,
                reason=reason,
                slo_status={name: m.status for name, m in self.slo_monitor.get_all_slo_status().items()},
                performance_metrics=self.performance_metrics.copy(),
                metadata=metadata or {}
            )
            
            # Update state
            self.current_stage = next_stage
            self.position_size_multiplier = new_multiplier
            self.last_activation_time = time.time()
            self.activation_events.append(event)
            
            logger.info(f"Activated stage {next_stage.value} with position size multiplier {new_multiplier}")
            return True
            
    def check_rollback_criteria(self) -> Tuple[bool, str, Dict[str, Any]]:
        """Check if rollback criteria are met"""
        with self.lock:
            slo_status = self.slo_monitor.get_all_slo_status()
            critical_violations = 0
            
            # Count critical violations
            for slo_name, measurement in slo_status.items():
                if measurement.status == SLOStatus.VIOLATED:
                    slo = self.slo_monitor.slo_thresholds.get(slo_name)
                    if slo and slo.severity == 'critical':
                        critical_violations += 1
            
            if critical_violations >= self.config.rollback_threshold:
                return True, f"{critical_violations} critical SLO violations detected", {
                    'critical_violations': critical_violations,
                    'slo_status': slo_status,
                    'rollback_threshold': self.config.rollback_threshold
                }
                
            return False, f"Rollback criteria not met: {critical_violations}/{self.config.rollback_threshold} critical violations", {
                'critical_violations': critical_violations,
                'slo_status': slo_status
            }
            
    def rollback_stage(self, reason: str, metadata: Dict[str, Any] = None) -> bool:
        """Rollback to previous stage"""
        with self.lock:
            if self.rollback_count >= self.config.max_rollbacks:
                logger.error(f"Maximum rollbacks ({self.config.max_rollbacks}) exceeded")
                return False
                
            # Determine rollback stage
            if self.current_stage == ActivationStage.FULL:
                rollback_stage = ActivationStage.STAGED
                new_multiplier = self.config.initial_position_size
            elif self.current_stage == ActivationStage.STAGED:
                rollback_stage = ActivationStage.INITIAL
                new_multiplier = self.config.initial_position_size * 0.5  # Even smaller
            else:
                logger.warning(f"Cannot rollback from stage {self.current_stage}")
                return False
                
            # Create rollback event
            event = ActivationEvent(
                event_id=f"RB_{uuid.uuid4().hex[:8]}",
                timestamp=time.time(),
                from_stage=self.current_stage,
                to_stage=rollback_stage,
                trigger=ActivationTrigger.SLO_VIOLATION,
                reason=reason,
                slo_status={name: m.status for name, m in self.slo_monitor.get_all_slo_status().items()},
                performance_metrics=self.performance_metrics.copy(),
                metadata=metadata or {}
            )
            
            # Update state
            self.current_stage = rollback_stage
            self.position_size_multiplier = new_multiplier
            self.rollback_count += 1
            self.activation_events.append(event)
            
            logger.warning(f"Rolled back to stage {rollback_stage.value} with position size multiplier {new_multiplier}")
            return True
            
    def get_position_size_multiplier(self) -> float:
        """Get current position size multiplier"""
        with self.lock:
            return self.position_size_multiplier
            
    def get_activation_status(self) -> Dict[str, Any]:
        """Get current activation status"""
        with self.lock:
            slo_status = self.slo_monitor.get_all_slo_status()
            elapsed_time = time.time() - self.start_time
            
            return {
                'current_stage': self.current_stage.value,
                'position_size_multiplier': self.position_size_multiplier,
                'trade_count': self.trade_count,
                'elapsed_time_seconds': elapsed_time,
                'elapsed_time_hours': elapsed_time / 3600,
                'rollback_count': self.rollback_count,
                'last_activation_time': self.last_activation_time,
                'slo_status': {name: {
                    'status': m.status.value,
                    'value': m.value,
                    'threshold': m.threshold,
                    'sample_count': m.sample_count
                } for name, m in slo_status.items()},
                'activation_events_count': len(self.activation_events),
                'can_activate': self.current_stage in [ActivationStage.INITIAL, ActivationStage.STAGED],
                'can_rollback': self.current_stage in [ActivationStage.STAGED, ActivationStage.FULL]
            }
            
    def get_activation_history(self) -> List[Dict[str, Any]]:
        """Get activation event history"""
        with self.lock:
            return [{
                'event_id': event.event_id,
                'timestamp': event.timestamp,
                'from_stage': event.from_stage.value,
                'to_stage': event.to_stage.value,
                'trigger': event.trigger.value,
                'reason': event.reason,
                'slo_status': {name: status.value for name, status in event.slo_status.items()},
                'performance_metrics': event.performance_metrics,
                'metadata': event.metadata
            } for event in self.activation_events]


class StagedActivationSystem:
    """Main staged activation system"""
    
    def __init__(self, config: StagedActivationConfig):
        self.config = config
        self.activation_manager = ActivationManager(config)
        self.running = False
        self.monitor_thread = None
        self.db_path = Path("staged_activation.db")
        self.setup_database()
        
    def setup_database(self):
        """Setup SQLite database for activation data"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activation_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    from_stage TEXT NOT NULL,
                    to_stage TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    slo_status TEXT NOT NULL,
                    performance_metrics TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS slo_measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slo_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    window_start REAL,
                    window_end REAL,
                    sample_count INTEGER
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activation_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    current_stage TEXT NOT NULL,
                    position_size_multiplier REAL NOT NULL,
                    trade_count INTEGER NOT NULL,
                    elapsed_time_seconds REAL NOT NULL,
                    rollback_count INTEGER NOT NULL,
                    slo_status TEXT NOT NULL
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activation_events_timestamp ON activation_events(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_slo_measurements_slo_name_timestamp ON slo_measurements(slo_name, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activation_status_timestamp ON activation_status(timestamp)")
            
    def start(self):
        """Start the staged activation system"""
        if self.running:
            logger.warning("Staged activation system is already running")
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Staged activation system started")
        
    def stop(self):
        """Stop the staged activation system"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        logger.info("Staged activation system stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self._check_activation_criteria()
                self._check_rollback_criteria()
                self._save_status_to_database()
                time.sleep(self.config.slo_check_interval_seconds)
            except Exception as e:
                logger.error(f"Error in staged activation monitor: {e}")
                time.sleep(10)
                
    def _check_activation_criteria(self):
        """Check if activation criteria are met"""
        if not self.config.enable_auto_activation:
            return
            
        can_activate, reason, metadata = self.activation_manager.check_activation_criteria()
        
        if can_activate:
            trigger = metadata.get('trigger', ActivationTrigger.MANUAL)
            success = self.activation_manager.activate_next_stage(trigger, reason, metadata)
            if success:
                self._save_activation_event()
                
    def _check_rollback_criteria(self):
        """Check if rollback criteria are met"""
        if not self.config.enable_auto_rollback:
            return
            
        should_rollback, reason, metadata = self.activation_manager.check_rollback_criteria()
        
        if should_rollback:
            success = self.activation_manager.rollback_stage(reason, metadata)
            if success:
                self._save_activation_event()
                
    def _save_activation_event(self):
        """Save activation event to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get the latest event
                if self.activation_manager.activation_events:
                    event = self.activation_manager.activation_events[-1]
                    conn.execute("""
                        INSERT OR REPLACE INTO activation_events (
                            event_id, timestamp, from_stage, to_stage, trigger,
                            reason, slo_status, performance_metrics, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event.event_id,
                        event.timestamp,
                        event.from_stage.value,
                        event.to_stage.value,
                        event.trigger.value,
                        event.reason,
                        json.dumps({name: status.value for name, status in event.slo_status.items()}),
                        json.dumps(event.performance_metrics),
                        json.dumps(event.metadata)
                    ))
        except Exception as e:
            logger.error(f"Error saving activation event: {e}")
            
    def _save_status_to_database(self):
        """Save current status to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                status = self.activation_manager.get_activation_status()
                conn.execute("""
                    INSERT INTO activation_status (
                        timestamp, current_stage, position_size_multiplier,
                        trade_count, elapsed_time_seconds, rollback_count, slo_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    time.time(),
                    status['current_stage'],
                    status['position_size_multiplier'],
                    status['trade_count'],
                    status['elapsed_time_seconds'],
                    status['rollback_count'],
                    json.dumps(status['slo_status'])
                ))
                
                # Also save SLO measurements
                for slo_name, measurements in self.activation_manager.slo_monitor.measurements.items():
                    for measurement in measurements:
                        conn.execute("""
                            INSERT INTO slo_measurements (
                                slo_name, value, timestamp, window_start, window_end, sample_count
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            slo_name,
                            measurement['value'],
                            measurement['timestamp'],
                            measurement.get('window_start', measurement['timestamp']),
                            measurement.get('window_end', measurement['timestamp']),
                            measurement.get('sample_count', 1)
                        ))
        except Exception as e:
            logger.error(f"Error saving activation status: {e}")
            
    def record_trade(self, trade_data: Dict[str, Any]):
        """Record a trade for activation tracking"""
        self.activation_manager.record_trade(trade_data)
        
    def record_performance_metric(self, metric_name: str, value: float):
        """Record a performance metric"""
        self.activation_manager.record_performance_metric(metric_name, value)
        
    def get_position_size_multiplier(self) -> float:
        """Get current position size multiplier"""
        return self.activation_manager.get_position_size_multiplier()
        
    def get_activation_status(self) -> Dict[str, Any]:
        """Get current activation status"""
        return self.activation_manager.get_activation_status()
        
    def get_activation_history(self) -> List[Dict[str, Any]]:
        """Get activation event history"""
        return self.activation_manager.get_activation_history()
        
    def manual_activate(self, reason: str = "Manual activation") -> bool:
        """Manually trigger activation"""
        return self.activation_manager.activate_next_stage(ActivationTrigger.MANUAL, reason)
        
    def manual_rollback(self, reason: str = "Manual rollback") -> bool:
        """Manually trigger rollback"""
        return self.activation_manager.rollback_stage(reason)
        
    def add_slo_threshold(self, slo: SLOThreshold):
        """Add a custom SLO threshold"""
        self.activation_manager.slo_monitor.add_slo_threshold(slo)
        
    def get_slo_status(self) -> Dict[str, SLOMeasurement]:
        """Get current SLO status"""
        return self.activation_manager.slo_monitor.get_all_slo_status()


# Global functions for easy access
_staged_activation_system: Optional[StagedActivationSystem] = None

def get_staged_activation_system() -> Optional[StagedActivationSystem]:
    """Get the global staged activation system instance"""
    return _staged_activation_system

def create_staged_activation_system(config: StagedActivationConfig) -> StagedActivationSystem:
    """Create a new staged activation system"""
    global _staged_activation_system
    _staged_activation_system = StagedActivationSystem(config)
    return _staged_activation_system

def start_staged_activation(config: StagedActivationConfig) -> StagedActivationSystem:
    """Start staged activation with the given configuration"""
    system = create_staged_activation_system(config)
    system.start()
    return system

def stop_staged_activation():
    """Stop staged activation"""
    global _staged_activation_system
    if _staged_activation_system:
        _staged_activation_system.stop()
        _staged_activation_system = None

def get_position_size_multiplier() -> float:
    """Get current position size multiplier"""
    if _staged_activation_system:
        return _staged_activation_system.get_position_size_multiplier()
    return 1.0  # Default to full size if not initialized

def record_trade(trade_data: Dict[str, Any]):
    """Record a trade for activation tracking"""
    if _staged_activation_system:
        _staged_activation_system.record_trade(trade_data)

def record_performance_metric(metric_name: str, value: float):
    """Record a performance metric"""
    if _staged_activation_system:
        _staged_activation_system.record_performance_metric(metric_name, value)

def get_activation_status() -> Dict[str, Any]:
    """Get current activation status"""
    if _staged_activation_system:
        return _staged_activation_system.get_activation_status()
    return {"error": "Staged activation system not initialized"}

def manual_activate(reason: str = "Manual activation") -> bool:
    """Manually trigger activation"""
    if _staged_activation_system:
        return _staged_activation_system.manual_activate(reason)
    return False

def manual_rollback(reason: str = "Manual rollback") -> bool:
    """Manually trigger rollback"""
    if _staged_activation_system:
        return _staged_activation_system.manual_rollback(reason)
    return False
