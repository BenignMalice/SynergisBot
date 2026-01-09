"""
Reconnect Strategy for WebSocket Connections

This module implements a robust reconnection strategy for WebSocket connections
with jittered exponential backoff, sequence ID validation, and connection health monitoring.

Key Features:
- Jittered exponential backoff to prevent thundering herd
- Sequence ID validation for data integrity
- Connection health monitoring and automatic recovery
- Circuit breaker pattern for persistent failures
- Configurable retry policies and timeouts
"""

import asyncio
import time
import random
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime, timedelta
import threading
from collections import deque

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """WebSocket connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    CIRCUIT_OPEN = "circuit_open"

class ReconnectReason(Enum):
    """Reasons for reconnection"""
    INITIAL = "initial"
    DISCONNECT = "disconnect"
    TIMEOUT = "timeout"
    ERROR = "error"
    SEQUENCE_GAP = "sequence_gap"
    HEARTBEAT_MISSED = "heartbeat_missed"
    MANUAL = "manual"

@dataclass
class ReconnectConfig:
    """Configuration for reconnection strategy"""
    max_retries: int = 10
    base_delay_ms: int = 1000  # 1 second
    max_delay_ms: int = 30000  # 30 seconds
    jitter_factor: float = 0.1  # 10% jitter
    backoff_multiplier: float = 2.0
    circuit_breaker_threshold: int = 5  # failures before circuit opens
    circuit_breaker_timeout_ms: int = 60000  # 1 minute
    sequence_validation_window: int = 1000  # sequence IDs to track
    heartbeat_timeout_ms: int = 30000  # 30 seconds
    connection_timeout_ms: int = 10000  # 10 seconds
    health_check_interval_ms: int = 5000  # 5 seconds

@dataclass
class ConnectionMetrics:
    """Connection performance metrics"""
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    reconnect_attempts: int = 0
    last_connection_time: float = 0.0
    last_disconnection_time: float = 0.0
    uptime_seconds: float = 0.0
    sequence_gaps: int = 0
    heartbeat_misses: int = 0

@dataclass
class ReconnectAttempt:
    """Individual reconnection attempt"""
    attempt_number: int
    timestamp: float
    reason: ReconnectReason
    delay_ms: int
    success: bool = False
    error_message: Optional[str] = None

class SequenceValidator:
    """Validates sequence IDs for data integrity"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.expected_sequence = 0
        self.received_sequences = deque(maxlen=window_size)
        self.gaps_detected = 0
        self.last_valid_sequence = 0
    
    def validate_sequence(self, sequence_id: int) -> Tuple[bool, Optional[str]]:
        """Validate a sequence ID and return (is_valid, error_message)"""
        if sequence_id < 0:
            return False, f"Invalid sequence ID: {sequence_id}"
        
        # First sequence
        if self.expected_sequence == 0:
            self.expected_sequence = sequence_id
            self.last_valid_sequence = sequence_id
            self.received_sequences.append(sequence_id)
            return True, None
        
        # Check for gaps
        if sequence_id > self.expected_sequence:
            gap_size = sequence_id - self.expected_sequence
            self.gaps_detected += 1
            self.expected_sequence = sequence_id
            self.last_valid_sequence = sequence_id
            self.received_sequences.append(sequence_id)
            return True, f"Sequence gap detected: {gap_size} missing sequences"
        
        # Check for duplicate or out-of-order
        if sequence_id <= self.last_valid_sequence:
            if sequence_id in self.received_sequences:
                return False, f"Duplicate sequence ID: {sequence_id}"
            else:
                return False, f"Out-of-order sequence ID: {sequence_id}"
        
        # Valid sequence
        self.expected_sequence = sequence_id + 1
        self.last_valid_sequence = sequence_id
        self.received_sequences.append(sequence_id)
        return True, None
    
    def get_sequence_stats(self) -> Dict[str, Any]:
        """Get sequence validation statistics"""
        return {
            'expected_sequence': self.expected_sequence,
            'last_valid_sequence': self.last_valid_sequence,
            'gaps_detected': self.gaps_detected,
            'received_count': len(self.received_sequences),
            'window_size': self.window_size
        }

class CircuitBreaker:
    """Circuit breaker for persistent connection failures"""
    
    def __init__(self, threshold: int = 5, timeout_ms: int = 60000):
        self.threshold = threshold
        self.timeout_ms = timeout_ms
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "closed"  # closed, open, half_open
    
    def record_success(self) -> None:
        """Record a successful operation"""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self) -> None:
        """Record a failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def can_attempt(self) -> bool:
        """Check if an attempt can be made"""
        if self.state == "closed":
            return True
        
        if self.state == "open":
            # Check if timeout has passed
            if time.time() - self.last_failure_time > (self.timeout_ms / 1000.0):
                self.state = "half_open"
                return True
            return False
        
        if self.state == "half_open":
            return True
        
        return False
    
    def get_state(self) -> str:
        """Get current circuit breaker state"""
        return self.state

class ReconnectStrategy:
    """Main reconnection strategy implementation"""
    
    def __init__(self, config: ReconnectConfig):
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self.metrics = ConnectionMetrics()
        self.sequence_validator = SequenceValidator(config.sequence_validation_window)
        self.circuit_breaker = CircuitBreaker(
            config.circuit_breaker_threshold,
            config.circuit_breaker_timeout_ms
        )
        self.reconnect_attempts: List[ReconnectAttempt] = []
        self.last_heartbeat = 0.0
        self.connection_start_time = 0.0
        self.lock = threading.RLock()
        
        # Callbacks
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.on_reconnect: Optional[Callable] = None
        self.on_circuit_open: Optional[Callable] = None
    
    def set_callbacks(self, 
                      on_connect: Optional[Callable] = None,
                      on_disconnect: Optional[Callable] = None,
                      on_reconnect: Optional[Callable] = None,
                      on_circuit_open: Optional[Callable] = None) -> None:
        """Set callback functions for connection events"""
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_reconnect = on_reconnect
        self.on_circuit_open = on_circuit_open
    
    def calculate_delay(self, attempt_number: int) -> int:
        """Calculate delay for reconnection attempt with jitter"""
        # Exponential backoff
        delay = min(
            self.config.base_delay_ms * (self.config.backoff_multiplier ** attempt_number),
            self.config.max_delay_ms
        )
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(
            -self.config.jitter_factor * delay,
            self.config.jitter_factor * delay
        )
        
        return max(0, int(delay + jitter))
    
    def should_reconnect(self) -> bool:
        """Determine if reconnection should be attempted"""
        with self.lock:
            # Check circuit breaker
            if not self.circuit_breaker.can_attempt():
                return False
            
            # Check max retries
            if len(self.reconnect_attempts) >= self.config.max_retries:
                return False
            
            # Check if already connected
            if self.state == ConnectionState.CONNECTED:
                return False
            
            return True
    
    def record_connection_attempt(self, reason: ReconnectReason) -> ReconnectAttempt:
        """Record a connection attempt"""
        with self.lock:
            attempt_number = len(self.reconnect_attempts) + 1
            delay_ms = self.calculate_delay(attempt_number - 1)
            
            attempt = ReconnectAttempt(
                attempt_number=attempt_number,
                timestamp=time.time(),
                reason=reason,
                delay_ms=delay_ms
            )
            
            self.reconnect_attempts.append(attempt)
            self.metrics.reconnect_attempts += 1
            
            return attempt
    
    def record_connection_success(self) -> None:
        """Record successful connection"""
        with self.lock:
            self.state = ConnectionState.CONNECTED
            self.connection_start_time = time.time()
            self.last_heartbeat = time.time()
            self.metrics.successful_connections += 1
            self.metrics.total_connections += 1
            
            # Update last attempt
            if self.reconnect_attempts:
                self.reconnect_attempts[-1].success = True
            
            # Reset circuit breaker
            self.circuit_breaker.record_success()
            
            # Clear old attempts
            self.reconnect_attempts.clear()
            
            logger.info(f"Connection established successfully (attempt {len(self.reconnect_attempts) + 1})")
            
            # Call callback
            if self.on_connect:
                try:
                    self.on_connect()
                except Exception as e:
                    logger.error(f"Error in on_connect callback: {e}")
    
    def record_connection_failure(self, error_message: str) -> None:
        """Record connection failure"""
        with self.lock:
            self.state = ConnectionState.FAILED
            self.metrics.failed_connections += 1
            self.metrics.total_connections += 1
            
            # Update last attempt
            if self.reconnect_attempts:
                self.reconnect_attempts[-1].error_message = error_message
            
            # Record circuit breaker failure
            self.circuit_breaker.record_failure()
            
            logger.error(f"Connection failed: {error_message}")
            
            # Check if circuit should open
            if self.circuit_breaker.get_state() == "open":
                self.state = ConnectionState.CIRCUIT_OPEN
                logger.warning("Circuit breaker opened - stopping reconnection attempts")
                
                if self.on_circuit_open:
                    try:
                        self.on_circuit_open()
                    except Exception as e:
                        logger.error(f"Error in on_circuit_open callback: {e}")
    
    def record_disconnection(self, reason: ReconnectReason = ReconnectReason.DISCONNECT) -> None:
        """Record disconnection"""
        with self.lock:
            if self.state == ConnectionState.CONNECTED:
                self.state = ConnectionState.DISCONNECTED
                self.metrics.last_disconnection_time = time.time()
                
                # Calculate uptime
                if self.connection_start_time > 0:
                    self.metrics.uptime_seconds = time.time() - self.connection_start_time
                
                logger.info(f"Connection lost: {reason.value}")
                
                if self.on_disconnect:
                    try:
                        self.on_disconnect()
                    except Exception as e:
                        logger.error(f"Error in on_disconnect callback: {e}")
    
    def validate_sequence_id(self, sequence_id: int) -> Tuple[bool, Optional[str]]:
        """Validate sequence ID for data integrity"""
        is_valid, error_message = self.sequence_validator.validate_sequence(sequence_id)
        
        if not is_valid and "Sequence gap" in (error_message or ""):
            self.metrics.sequence_gaps += 1
            logger.warning(f"Sequence gap detected: {error_message}")
            
            # Trigger reconnection for sequence gaps
            if self.state == ConnectionState.CONNECTED:
                self.record_disconnection(ReconnectReason.SEQUENCE_GAP)
        
        return is_valid, error_message
    
    def update_heartbeat(self) -> None:
        """Update heartbeat timestamp"""
        with self.lock:
            self.last_heartbeat = time.time()
    
    def check_heartbeat(self) -> bool:
        """Check if heartbeat is still valid"""
        with self.lock:
            if self.state != ConnectionState.CONNECTED:
                return False
            
            current_time = time.time()
            heartbeat_age = current_time - self.last_heartbeat
            
            if heartbeat_age > (self.config.heartbeat_timeout_ms / 1000.0):
                self.metrics.heartbeat_misses += 1
                logger.warning(f"Heartbeat timeout: {heartbeat_age:.2f}s")
                return False
            
            return True
    
    def get_connection_state(self) -> ConnectionState:
        """Get current connection state"""
        with self.lock:
            return self.state
    
    def get_metrics(self) -> ConnectionMetrics:
        """Get connection metrics"""
        with self.lock:
            # Update uptime
            if self.state == ConnectionState.CONNECTED and self.connection_start_time > 0:
                self.metrics.uptime_seconds = time.time() - self.connection_start_time
            
            return self.metrics
    
    def get_sequence_stats(self) -> Dict[str, Any]:
        """Get sequence validation statistics"""
        return self.sequence_validator.get_sequence_stats()
    
    def get_circuit_breaker_state(self) -> str:
        """Get circuit breaker state"""
        return self.circuit_breaker.get_state()
    
    def get_reconnect_attempts(self) -> List[ReconnectAttempt]:
        """Get list of reconnection attempts"""
        with self.lock:
            return list(self.reconnect_attempts)
    
    def reset_metrics(self) -> None:
        """Reset connection metrics"""
        with self.lock:
            self.metrics = ConnectionMetrics()
            self.reconnect_attempts.clear()
            self.sequence_validator = SequenceValidator(self.config.sequence_validation_window)
            self.circuit_breaker = CircuitBreaker(
                self.config.circuit_breaker_threshold,
                self.config.circuit_breaker_timeout_ms
            )
    
    def force_reconnect(self) -> None:
        """Force a reconnection attempt"""
        with self.lock:
            if self.state == ConnectionState.CONNECTED:
                self.record_disconnection(ReconnectReason.MANUAL)
            
            self.state = ConnectionState.RECONNECTING
            logger.info("Forcing reconnection...")
    
    def get_next_delay(self) -> int:
        """Get delay for next reconnection attempt"""
        if not self.reconnect_attempts:
            return 0
        
        return self.calculate_delay(len(self.reconnect_attempts))

class ReconnectManager:
    """Manages multiple reconnection strategies"""
    
    def __init__(self):
        self.strategies: Dict[str, ReconnectStrategy] = {}
        self.lock = threading.RLock()
    
    def add_strategy(self, name: str, config: ReconnectConfig) -> ReconnectStrategy:
        """Add a reconnection strategy"""
        with self.lock:
            strategy = ReconnectStrategy(config)
            self.strategies[name] = strategy
            return strategy
    
    def get_strategy(self, name: str) -> Optional[ReconnectStrategy]:
        """Get a reconnection strategy"""
        with self.lock:
            return self.strategies.get(name)
    
    def remove_strategy(self, name: str) -> bool:
        """Remove a reconnection strategy"""
        with self.lock:
            if name in self.strategies:
                del self.strategies[name]
                return True
            return False
    
    def get_all_strategies(self) -> Dict[str, ReconnectStrategy]:
        """Get all reconnection strategies"""
        with self.lock:
            return dict(self.strategies)
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get global metrics for all strategies"""
        with self.lock:
            total_connections = 0
            successful_connections = 0
            failed_connections = 0
            active_connections = 0
            circuit_open_count = 0
            
            for strategy in self.strategies.values():
                metrics = strategy.get_metrics()
                total_connections += metrics.total_connections
                successful_connections += metrics.successful_connections
                failed_connections += metrics.failed_connections
                
                if strategy.get_connection_state() == ConnectionState.CONNECTED:
                    active_connections += 1
                elif strategy.get_connection_state() == ConnectionState.CIRCUIT_OPEN:
                    circuit_open_count += 1
            
            return {
                'total_strategies': len(self.strategies),
                'active_connections': active_connections,
                'circuit_open_connections': circuit_open_count,
                'total_connections': total_connections,
                'successful_connections': successful_connections,
                'failed_connections': failed_connections,
                'success_rate': successful_connections / max(1, total_connections)
            }

# Global reconnect manager
_reconnect_manager: Optional[ReconnectManager] = None

def get_reconnect_manager() -> ReconnectManager:
    """Get global reconnect manager instance"""
    global _reconnect_manager
    if _reconnect_manager is None:
        _reconnect_manager = ReconnectManager()
    return _reconnect_manager

def create_reconnect_strategy(name: str, config: ReconnectConfig) -> ReconnectStrategy:
    """Create a new reconnection strategy"""
    manager = get_reconnect_manager()
    return manager.add_strategy(name, config)

def get_reconnect_strategy(name: str) -> Optional[ReconnectStrategy]:
    """Get a reconnection strategy"""
    manager = get_reconnect_manager()
    return manager.get_strategy(name)

def get_global_metrics() -> Dict[str, Any]:
    """Get global reconnection metrics"""
    manager = get_reconnect_manager()
    return manager.get_global_metrics()

if __name__ == "__main__":
    # Example usage
    config = ReconnectConfig(
        max_retries=5,
        base_delay_ms=1000,
        max_delay_ms=10000,
        jitter_factor=0.1,
        backoff_multiplier=2.0
    )
    
    strategy = create_reconnect_strategy("binance_ws", config)
    
    # Simulate connection attempts
    for i in range(3):
        attempt = strategy.record_connection_attempt(ReconnectReason.INITIAL)
        print(f"Attempt {attempt.attempt_number}: delay={attempt.delay_ms}ms")
        
        if i == 2:  # Simulate success on 3rd attempt
            strategy.record_connection_success()
            break
        else:
            strategy.record_connection_failure(f"Connection failed: attempt {i+1}")
    
    # Print metrics
    metrics = strategy.get_metrics()
    print(f"Metrics: {metrics}")
    
    # Print global metrics
    global_metrics = get_global_metrics()
    print(f"Global metrics: {global_metrics}")
