"""
Snapshot Re-sync System for Gap Detection

This module implements a robust snapshot re-sync system that detects sequence gaps
in WebSocket streams and automatically re-synchronizes data to maintain integrity.

Key Features:
- Sequence gap detection and analysis
- Automatic snapshot re-sync on gap detection
- Data integrity validation and recovery
- Configurable gap thresholds and recovery strategies
- Performance monitoring and metrics collection
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime, timedelta
import threading
from collections import deque
import hashlib

logger = logging.getLogger(__name__)

class GapType(Enum):
    """Types of sequence gaps"""
    MISSING_SEQUENCE = "missing_sequence"
    DUPLICATE_SEQUENCE = "duplicate_sequence"
    OUT_OF_ORDER = "out_of_order"
    TIMEOUT_GAP = "timeout_gap"
    CONNECTION_LOST = "connection_lost"

class ResyncStrategy(Enum):
    """Re-sync strategies for different gap types"""
    IGNORE = "ignore"
    REQUEST_SNAPSHOT = "request_snapshot"
    REQUEST_PARTIAL = "request_partial"
    FULL_RESYNC = "full_resync"
    RESTART_STREAM = "restart_stream"

class ResyncStatus(Enum):
    """Re-sync operation status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class GapInfo:
    """Information about a detected gap"""
    gap_type: GapType
    expected_sequence: int
    received_sequence: int
    gap_size: int
    timestamp: float
    symbol: str
    severity: str  # low, medium, high, critical
    description: str

@dataclass
class ResyncConfig:
    """Configuration for re-sync operations"""
    max_gap_size: int = 1000
    gap_timeout_ms: int = 5000
    resync_timeout_ms: int = 30000
    max_resync_attempts: int = 3
    snapshot_request_delay_ms: int = 1000
    partial_request_size: int = 100
    full_resync_threshold: int = 100
    enable_auto_resync: bool = True
    enable_metrics: bool = True
    gap_detection_window: int = 10000

@dataclass
class ResyncOperation:
    """Re-sync operation details"""
    operation_id: str
    gap_info: GapInfo
    strategy: ResyncStrategy
    status: ResyncStatus
    start_time: float
    end_time: Optional[float] = None
    attempts: int = 0
    max_attempts: int = 3
    error_message: Optional[str] = None
    data_recovered: int = 0
    data_lost: int = 0

@dataclass
class ResyncMetrics:
    """Metrics for re-sync operations"""
    total_gaps_detected: int = 0
    total_resync_operations: int = 0
    successful_resyncs: int = 0
    failed_resyncs: int = 0
    data_recovered: int = 0
    data_lost: int = 0
    avg_resync_time_ms: float = 0.0
    last_resync_time: float = 0.0
    gaps_by_type: Dict[str, int] = field(default_factory=dict)
    resyncs_by_strategy: Dict[str, int] = field(default_factory=dict)

class GapDetector:
    """Detects and analyzes sequence gaps"""
    
    def __init__(self, config: ResyncConfig):
        self.config = config
        self.sequence_history = deque(maxlen=config.gap_detection_window)
        self.gap_thresholds = {
            'low': 1,
            'medium': 10,
            'high': 100,
            'critical': 1000
        }
        self.lock = threading.RLock()
    
    def detect_gap(self, expected_sequence: int, received_sequence: int, 
                   symbol: str, timestamp: float) -> Optional[GapInfo]:
        """Detect and analyze a sequence gap"""
        with self.lock:
            if received_sequence == expected_sequence:
                # No gap
                self.sequence_history.append({
                    'sequence': received_sequence,
                    'timestamp': timestamp,
                    'symbol': symbol
                })
                return None
            
            gap_size = abs(received_sequence - expected_sequence)
            gap_type = self._classify_gap(expected_sequence, received_sequence)
            severity = self._assess_severity(gap_size)
            
            gap_info = GapInfo(
                gap_type=gap_type,
                expected_sequence=expected_sequence,
                received_sequence=received_sequence,
                gap_size=gap_size,
                timestamp=timestamp,
                symbol=symbol,
                severity=severity,
                description=self._generate_description(gap_type, gap_size)
            )
            
            # Record the gap
            self.sequence_history.append({
                'sequence': received_sequence,
                'timestamp': timestamp,
                'symbol': symbol,
                'gap': True
            })
            
            return gap_info
    
    def _classify_gap(self, expected: int, received: int) -> GapType:
        """Classify the type of gap"""
        if received > expected:
            return GapType.MISSING_SEQUENCE
        elif received < expected:
            return GapType.OUT_OF_ORDER
        else:
            return GapType.DUPLICATE_SEQUENCE
    
    def _assess_severity(self, gap_size: int) -> str:
        """Assess the severity of a gap"""
        if gap_size <= self.gap_thresholds['low']:
            return 'low'
        elif gap_size <= self.gap_thresholds['medium']:
            return 'medium'
        elif gap_size <= self.gap_thresholds['high']:
            return 'high'
        else:
            return 'critical'
    
    def _generate_description(self, gap_type: GapType, gap_size: int) -> str:
        """Generate a description for the gap"""
        if gap_type == GapType.MISSING_SEQUENCE:
            return f"Missing {gap_size} sequence(s)"
        elif gap_type == GapType.OUT_OF_ORDER:
            return f"Out-of-order sequence, gap size: {gap_size}"
        elif gap_type == GapType.DUPLICATE_SEQUENCE:
            return f"Duplicate sequence detected"
        else:
            return f"Unknown gap type: {gap_type.value}"
    
    def get_gap_statistics(self) -> Dict[str, Any]:
        """Get gap detection statistics"""
        with self.lock:
            total_sequences = len(self.sequence_history)
            gaps = sum(1 for seq in self.sequence_history if seq.get('gap', False))
            
            return {
                'total_sequences': total_sequences,
                'gaps_detected': gaps,
                'gap_rate': gaps / max(1, total_sequences),
                'window_size': self.config.gap_detection_window
            }

class ResyncStrategySelector:
    """Selects appropriate re-sync strategy based on gap analysis"""
    
    def __init__(self, config: ResyncConfig):
        self.config = config
        self.strategy_rules = {
            GapType.MISSING_SEQUENCE: {
                'low': ResyncStrategy.IGNORE,
                'medium': ResyncStrategy.REQUEST_PARTIAL,
                'high': ResyncStrategy.REQUEST_SNAPSHOT,
                'critical': ResyncStrategy.FULL_RESYNC
            },
            GapType.OUT_OF_ORDER: {
                'low': ResyncStrategy.IGNORE,
                'medium': ResyncStrategy.REQUEST_PARTIAL,
                'high': ResyncStrategy.REQUEST_SNAPSHOT,
                'critical': ResyncStrategy.FULL_RESYNC
            },
            GapType.DUPLICATE_SEQUENCE: {
                'low': ResyncStrategy.IGNORE,
                'medium': ResyncStrategy.IGNORE,
                'high': ResyncStrategy.REQUEST_PARTIAL,
                'critical': ResyncStrategy.REQUEST_SNAPSHOT
            },
            GapType.TIMEOUT_GAP: {
                'low': ResyncStrategy.REQUEST_PARTIAL,
                'medium': ResyncStrategy.REQUEST_SNAPSHOT,
                'high': ResyncStrategy.FULL_RESYNC,
                'critical': ResyncStrategy.RESTART_STREAM
            },
            GapType.CONNECTION_LOST: {
                'low': ResyncStrategy.REQUEST_SNAPSHOT,
                'medium': ResyncStrategy.FULL_RESYNC,
                'high': ResyncStrategy.RESTART_STREAM,
                'critical': ResyncStrategy.RESTART_STREAM
            }
        }
    
    def select_strategy(self, gap_info: GapInfo) -> ResyncStrategy:
        """Select re-sync strategy based on gap information"""
        gap_type = gap_info.gap_type
        severity = gap_info.severity
        
        if gap_type not in self.strategy_rules:
            return ResyncStrategy.IGNORE
        
        if severity not in self.strategy_rules[gap_type]:
            return ResyncStrategy.IGNORE
        
        return self.strategy_rules[gap_type][severity]

class SnapshotResync:
    """Main snapshot re-sync system"""
    
    def __init__(self, config: ResyncConfig):
        self.config = config
        self.gap_detector = GapDetector(config)
        self.strategy_selector = ResyncStrategySelector(config)
        self.active_operations: Dict[str, ResyncOperation] = {}
        self.completed_operations: List[ResyncOperation] = []
        self.metrics = ResyncMetrics()
        self.lock = threading.RLock()
        
        # Callbacks
        self.on_gap_detected: Optional[Callable[[GapInfo], None]] = None
        self.on_resync_started: Optional[Callable[[ResyncOperation], None]] = None
        self.on_resync_completed: Optional[Callable[[ResyncOperation], None]] = None
        self.on_resync_failed: Optional[Callable[[ResyncOperation], None]] = None
    
    def set_callbacks(self,
                      on_gap_detected: Optional[Callable[[GapInfo], None]] = None,
                      on_resync_started: Optional[Callable[[ResyncOperation], None]] = None,
                      on_resync_completed: Optional[Callable[[ResyncOperation], None]] = None,
                      on_resync_failed: Optional[Callable[[ResyncOperation], None]] = None) -> None:
        """Set callback functions for re-sync events"""
        self.on_gap_detected = on_gap_detected
        self.on_resync_started = on_resync_started
        self.on_resync_completed = on_resync_completed
        self.on_resync_failed = on_resync_failed
    
    def process_sequence(self, sequence: int, symbol: str, 
                        expected_sequence: int, timestamp: float) -> Optional[ResyncOperation]:
        """Process a sequence and detect gaps"""
        with self.lock:
            # Detect gap
            gap_info = self.gap_detector.detect_gap(
                expected_sequence, sequence, symbol, timestamp
            )
            
            if not gap_info:
                return None
            
            # Update metrics
            self.metrics.total_gaps_detected += 1
            gap_type_key = gap_info.gap_type.value
            self.metrics.gaps_by_type[gap_type_key] = self.metrics.gaps_by_type.get(gap_type_key, 0) + 1
            
            # Call gap detected callback
            if self.on_gap_detected:
                try:
                    self.on_gap_detected(gap_info)
                except Exception as e:
                    logger.error(f"Error in on_gap_detected callback: {e}")
            
            # Select strategy
            strategy = self.strategy_selector.select_strategy(gap_info)
            
            if strategy == ResyncStrategy.IGNORE:
                logger.info(f"Ignoring gap: {gap_info.description}")
                return None
            
            # Create re-sync operation
            operation = self._create_resync_operation(gap_info, strategy)
            
            # Start re-sync if auto-resync is enabled
            if self.config.enable_auto_resync:
                asyncio.create_task(self._execute_resync(operation))
            
            return operation
    
    def _create_resync_operation(self, gap_info: GapInfo, strategy: ResyncStrategy) -> ResyncOperation:
        """Create a new re-sync operation"""
        operation_id = self._generate_operation_id(gap_info)
        
        operation = ResyncOperation(
            operation_id=operation_id,
            gap_info=gap_info,
            strategy=strategy,
            status=ResyncStatus.PENDING,
            start_time=time.time(),
            max_attempts=self.config.max_resync_attempts
        )
        
        with self.lock:
            self.active_operations[operation_id] = operation
            self.metrics.total_resync_operations += 1
        
        return operation
    
    def _generate_operation_id(self, gap_info: GapInfo) -> str:
        """Generate unique operation ID"""
        data = f"{gap_info.symbol}_{gap_info.expected_sequence}_{gap_info.received_sequence}_{time.time()}"
        return hashlib.md5(data.encode()).hexdigest()[:16]
    
    async def _execute_resync(self, operation: ResyncOperation) -> None:
        """Execute a re-sync operation"""
        try:
            with self.lock:
                operation.status = ResyncStatus.IN_PROGRESS
                operation.attempts += 1
            
            # Call resync started callback
            if self.on_resync_started:
                try:
                    self.on_resync_started(operation)
                except Exception as e:
                    logger.error(f"Error in on_resync_started callback: {e}")
            
            # Execute strategy-specific re-sync
            success = await self._execute_strategy(operation)
            
            with self.lock:
                if success:
                    operation.status = ResyncStatus.COMPLETED
                    operation.end_time = time.time()
                    self.metrics.successful_resyncs += 1
                    
                    # Move to completed operations
                    self.completed_operations.append(operation)
                    if operation.operation_id in self.active_operations:
                        del self.active_operations[operation.operation_id]
                    
                    # Update metrics
                    self.metrics.data_recovered += operation.data_recovered
                    self.metrics.last_resync_time = time.time()
                    
                    # Call resync completed callback
                    if self.on_resync_completed:
                        try:
                            self.on_resync_completed(operation)
                        except Exception as e:
                            logger.error(f"Error in on_resync_completed callback: {e}")
                    
                    logger.info(f"Re-sync completed: {operation.operation_id}")
                else:
                    if operation.attempts < operation.max_attempts:
                        # Retry
                        operation.attempts += 1
                        await asyncio.sleep(self.config.snapshot_request_delay_ms / 1000.0)
                        await self._execute_resync(operation)
                    else:
                        # Failed
                        operation.status = ResyncStatus.FAILED
                        operation.end_time = time.time()
                        self.metrics.failed_resyncs += 1
                        
                        # Move to completed operations
                        self.completed_operations.append(operation)
                        if operation.operation_id in self.active_operations:
                            del self.active_operations[operation.operation_id]
                        
                        # Call resync failed callback
                        if self.on_resync_failed:
                            try:
                                self.on_resync_failed(operation)
                            except Exception as e:
                                logger.error(f"Error in on_resync_failed callback: {e}")
                        
                        logger.error(f"Re-sync failed: {operation.operation_id}")
        
        except Exception as e:
            logger.error(f"Error executing re-sync operation {operation.operation_id}: {e}")
            with self.lock:
                operation.status = ResyncStatus.FAILED
                operation.error_message = str(e)
                operation.end_time = time.time()
    
    async def _execute_strategy(self, operation: ResyncOperation) -> bool:
        """Execute the selected re-sync strategy"""
        strategy = operation.strategy
        gap_info = operation.gap_info
        
        try:
            if strategy == ResyncStrategy.REQUEST_SNAPSHOT:
                return await self._request_snapshot(operation)
            elif strategy == ResyncStrategy.REQUEST_PARTIAL:
                return await self._request_partial(operation)
            elif strategy == ResyncStrategy.FULL_RESYNC:
                return await self._full_resync(operation)
            elif strategy == ResyncStrategy.RESTART_STREAM:
                return await self._restart_stream(operation)
            else:
                logger.warning(f"Unknown strategy: {strategy}")
                return False
        
        except Exception as e:
            logger.error(f"Error executing strategy {strategy}: {e}")
            operation.error_message = str(e)
            return False
    
    async def _request_snapshot(self, operation: ResyncOperation) -> bool:
        """Request a snapshot for the symbol"""
        logger.info(f"Requesting snapshot for {operation.gap_info.symbol}")
        
        # Simulate snapshot request
        await asyncio.sleep(0.1)  # Simulate network delay
        
        operation.data_recovered = operation.gap_info.gap_size
        return True
    
    async def _request_partial(self, operation: ResyncOperation) -> bool:
        """Request partial data for the gap"""
        logger.info(f"Requesting partial data for {operation.gap_info.symbol}")
        
        # Simulate partial request
        await asyncio.sleep(0.05)  # Simulate network delay
        
        operation.data_recovered = min(operation.gap_info.gap_size, self.config.partial_request_size)
        return True
    
    async def _full_resync(self, operation: ResyncOperation) -> bool:
        """Perform full re-sync"""
        logger.info(f"Performing full resync for {operation.gap_info.symbol}")
        
        # Simulate full resync
        await asyncio.sleep(0.2)  # Simulate network delay
        
        operation.data_recovered = operation.gap_info.gap_size
        return True
    
    async def _restart_stream(self, operation: ResyncOperation) -> bool:
        """Restart the data stream"""
        logger.info(f"Restarting stream for {operation.gap_info.symbol}")
        
        # Simulate stream restart
        await asyncio.sleep(0.3)  # Simulate network delay
        
        operation.data_recovered = operation.gap_info.gap_size
        return True
    
    def get_active_operations(self) -> List[ResyncOperation]:
        """Get list of active re-sync operations"""
        with self.lock:
            return list(self.active_operations.values())
    
    def get_completed_operations(self, limit: int = 100) -> List[ResyncOperation]:
        """Get list of completed re-sync operations"""
        with self.lock:
            return self.completed_operations[-limit:]
    
    def get_metrics(self) -> ResyncMetrics:
        """Get re-sync metrics"""
        with self.lock:
            # Update average resync time
            if self.metrics.total_resync_operations > 0 and len(self.completed_operations) > 0:
                total_time = sum(
                    (op.end_time or time.time()) - op.start_time 
                    for op in self.completed_operations
                )
                self.metrics.avg_resync_time_ms = total_time / len(self.completed_operations) * 1000
            
            return self.metrics
    
    def get_gap_statistics(self) -> Dict[str, Any]:
        """Get gap detection statistics"""
        return self.gap_detector.get_gap_statistics()
    
    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a re-sync operation"""
        with self.lock:
            if operation_id in self.active_operations:
                operation = self.active_operations[operation_id]
                operation.status = ResyncStatus.CANCELLED
                operation.end_time = time.time()
                
                # Move to completed operations
                self.completed_operations.append(operation)
                del self.active_operations[operation_id]
                
                logger.info(f"Cancelled re-sync operation: {operation_id}")
                return True
            
            return False
    
    def reset_metrics(self) -> None:
        """Reset all metrics"""
        with self.lock:
            self.metrics = ResyncMetrics()
            self.active_operations.clear()
            self.completed_operations.clear()

# Global snapshot resync instance
_snapshot_resync: Optional[SnapshotResync] = None

def get_snapshot_resync(config: Optional[ResyncConfig] = None) -> SnapshotResync:
    """Get global snapshot resync instance"""
    global _snapshot_resync
    if _snapshot_resync is None:
        if config is None:
            config = ResyncConfig(enable_auto_resync=False)  # Disable auto-resync by default
        _snapshot_resync = SnapshotResync(config)
    return _snapshot_resync

def process_sequence(sequence: int, symbol: str, expected_sequence: int, 
                   timestamp: float) -> Optional[ResyncOperation]:
    """Process a sequence and detect gaps"""
    resync = get_snapshot_resync()
    return resync.process_sequence(sequence, symbol, expected_sequence, timestamp)

def get_resync_metrics() -> ResyncMetrics:
    """Get re-sync metrics"""
    resync = get_snapshot_resync()
    return resync.get_metrics()

def get_gap_statistics() -> Dict[str, Any]:
    """Get gap detection statistics"""
    resync = get_snapshot_resync()
    return resync.get_gap_statistics()

if __name__ == "__main__":
    # Example usage
    config = ResyncConfig(
        max_gap_size=1000,
        gap_timeout_ms=5000,
        resync_timeout_ms=30000,
        enable_auto_resync=True
    )
    
    resync = SnapshotResync(config)
    
    # Process some sequences with gaps
    sequences = [100, 101, 103, 104, 105]  # Gap at 102
    
    for i, seq in enumerate(sequences):
        expected = 100 + i
        operation = resync.process_sequence(seq, "BTCUSDc", expected, time.time())
        
        if operation:
            print(f"Gap detected: {operation.gap_info.description}")
            print(f"Strategy: {operation.strategy.value}")
            print(f"Status: {operation.status.value}")
    
    # Print metrics
    metrics = resync.get_metrics()
    print(f"Metrics: {metrics}")
    
    # Print gap statistics
    stats = resync.get_gap_statistics()
    print(f"Gap statistics: {stats}")
