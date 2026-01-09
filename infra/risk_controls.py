"""
Advanced Risk Controls System
Comprehensive risk management with lot caps, circuit breakers, and staleness demotion
"""

import asyncio
import logging
import time
import threading
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import os
from collections import defaultdict, deque
import numpy as np

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    """Risk level classifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Breaker triggered, blocking operations
    HALF_OPEN = "half_open"  # Testing if conditions have improved

class StalenessLevel(Enum):
    """Data staleness levels."""
    FRESH = "fresh"        # < 1 second old
    STALE = "stale"        # 1-5 seconds old
    VERY_STALE = "very_stale"  # 5-30 seconds old
    CRITICAL_STALE = "critical_stale"  # > 30 seconds old

@dataclass
class LotCapConfig:
    """Lot size cap configuration."""
    symbol: str
    max_lot_size: float = 0.01
    hard_cap_multiplier: float = 1.5  # Hard cap = max_lot_size * multiplier
    daily_lot_limit: float = 1.0
    hourly_lot_limit: float = 0.1
    position_size_limit: float = 0.05
    emergency_stop_threshold: float = 0.1

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    name: str
    threshold: float
    time_window: int  # seconds
    cooldown_period: int  # seconds
    max_trigger_count: int = 3
    ttl_seconds: int = 300  # 5 minutes default TTL
    enabled: bool = True

@dataclass
class StalenessConfig:
    """Staleness detection configuration."""
    symbol: str
    fresh_threshold: float = 1.0  # seconds
    stale_threshold: float = 5.0  # seconds
    very_stale_threshold: float = 30.0  # seconds
    critical_stale_threshold: float = 60.0  # seconds
    demotion_enabled: bool = True
    auto_recovery: bool = True

@dataclass
class RiskMetrics:
    """Risk metrics tracking."""
    symbol: str
    current_lot_size: float = 0.0
    daily_lot_usage: float = 0.0
    hourly_lot_usage: float = 0.0
    position_count: int = 0
    total_exposure: float = 0.0
    last_update: float = 0.0
    staleness_level: StalenessLevel = StalenessLevel.FRESH
    risk_level: RiskLevel = RiskLevel.LOW

class LotCapGuard:
    """Lot size cap enforcement with hard guards."""
    
    def __init__(self, config: LotCapConfig):
        self.config = config
        self.current_usage = defaultdict(float)
        self.daily_usage = defaultdict(float)
        self.hourly_usage = defaultdict(float)
        self.position_counts = defaultdict(int)
        self.last_reset = time.time()
        self.lock = threading.RLock()
        
    def check_lot_cap(self, symbol: str, requested_lot: float) -> Tuple[bool, str, float]:
        """
        Check if lot size request is within caps.
        Returns: (is_allowed, reason, adjusted_lot_size)
        """
        with self.lock:
            current_time = time.time()
            
            # Reset daily/hourly counters if needed
            if current_time - self.last_reset > 3600:  # 1 hour
                self._reset_hourly_counters()
            if current_time - self.last_reset > 86400:  # 24 hours
                self._reset_daily_counters()
            
            # Check hard cap (absolute maximum)
            hard_cap = self.config.max_lot_size * self.config.hard_cap_multiplier
            if requested_lot > hard_cap:
                return False, f"Requested lot {requested_lot} exceeds hard cap {hard_cap}", 0.0
            
            # Check daily limit
            daily_usage = self.daily_usage[symbol]
            if daily_usage + requested_lot > self.config.daily_lot_limit:
                return False, f"Daily lot limit exceeded: {daily_usage + requested_lot} > {self.config.daily_lot_limit}", 0.0
            
            # Check hourly limit
            hourly_usage = self.hourly_usage[symbol]
            if hourly_usage + requested_lot > self.config.hourly_lot_limit:
                return False, f"Hourly lot limit exceeded: {hourly_usage + requested_lot} > {self.config.hourly_lot_limit}", 0.0
            
            # Check position size limit
            current_positions = self.position_counts[symbol]
            if current_positions >= 1 and requested_lot > self.config.position_size_limit:
                return False, f"Position size limit exceeded: {requested_lot} > {self.config.position_size_limit}", 0.0
            
            # Check emergency stop threshold
            if daily_usage + requested_lot > self.config.emergency_stop_threshold:
                return False, f"Emergency stop threshold exceeded: {daily_usage + requested_lot} > {self.config.emergency_stop_threshold}", 0.0
            
            # All checks passed
            return True, "Lot size within limits", requested_lot
    
    def record_lot_usage(self, symbol: str, lot_size: float):
        """Record lot usage for tracking."""
        with self.lock:
            current_time = time.time()
            self.current_usage[symbol] += lot_size
            self.daily_usage[symbol] += lot_size
            self.hourly_usage[symbol] += lot_size
            self.position_counts[symbol] += 1
    
    def record_lot_reduction(self, symbol: str, lot_size: float):
        """Record lot size reduction (position closure)."""
        with self.lock:
            self.current_usage[symbol] = max(0, self.current_usage[symbol] - lot_size)
            self.position_counts[symbol] = max(0, self.position_counts[symbol] - 1)
    
    def _reset_hourly_counters(self):
        """Reset hourly usage counters."""
        self.hourly_usage.clear()
        self.last_reset = time.time()
    
    def _reset_daily_counters(self):
        """Reset daily usage counters."""
        self.daily_usage.clear()
        self.last_reset = time.time()
    
    def get_usage_stats(self, symbol: str) -> Dict[str, float]:
        """Get usage statistics for a symbol."""
        with self.lock:
            return {
                'current_usage': self.current_usage[symbol],
                'daily_usage': self.daily_usage[symbol],
                'hourly_usage': self.hourly_usage[symbol],
                'position_count': self.position_counts[symbol],
                'daily_limit_remaining': self.config.daily_lot_limit - self.daily_usage[symbol],
                'hourly_limit_remaining': self.config.hourly_lot_limit - self.hourly_usage[symbol]
            }

class CircuitBreaker:
    """Circuit breaker with TTL and automatic recovery."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.trigger_count = 0
        self.last_trigger_time = 0
        self.last_reset_time = time.time()
        self.trigger_history = deque(maxlen=100)
        self.lock = threading.RLock()
        
    def check_condition(self, value: float) -> bool:
        """Check if circuit breaker condition is met."""
        return value >= self.config.threshold
    
    def trigger(self, value: float, reason: str = ""):
        """Trigger the circuit breaker."""
        with self.lock:
            current_time = time.time()
            
            # Record trigger
            self.trigger_history.append({
                'timestamp': current_time,
                'value': value,
                'reason': reason
            })
            
            # Update state
            self.state = CircuitBreakerState.OPEN
            self.trigger_count += 1
            self.last_trigger_time = current_time
            
            logger.warning(f"Circuit breaker '{self.config.name}' triggered: {value} >= {self.config.threshold} ({reason})")
    
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        with self.lock:
            if self.state == CircuitBreakerState.CLOSED:
                return False
            
            current_time = time.time()
            
            # Check cooldown period first
            if current_time - self.last_trigger_time > self.config.cooldown_period:
                self.state = CircuitBreakerState.HALF_OPEN
                return False
            
            # Check TTL expiration
            if current_time - self.last_trigger_time > self.config.ttl_seconds:
                self._attempt_reset()
                return False
            
            return True
    
    def _attempt_reset(self):
        """Attempt to reset the circuit breaker."""
        with self.lock:
            if self.trigger_count >= self.config.max_trigger_count:
                # Too many triggers, keep open
                return
            
            self.state = CircuitBreakerState.CLOSED
            self.trigger_count = 0
            self.last_reset_time = time.time()
            logger.info(f"Circuit breaker '{self.config.name}' reset")
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        with self.lock:
            return {
                'name': self.config.name,
                'state': self.state.value,
                'trigger_count': self.trigger_count,
                'last_trigger_time': self.last_trigger_time,
                'time_since_last_trigger': time.time() - self.last_trigger_time,
                'enabled': self.config.enabled
            }

class StalenessDetector:
    """Data staleness detection and demotion system."""
    
    def __init__(self, config: StalenessConfig):
        self.config = config
        self.last_update_times = {}
        self.staleness_levels = {}
        self.demotion_count = 0
        self.auto_recovery_enabled = config.auto_recovery
        self.lock = threading.RLock()
        
    def update_timestamp(self, symbol: str, timestamp: float):
        """Update timestamp for a symbol."""
        with self.lock:
            self.last_update_times[symbol] = timestamp
            self._update_staleness_level(symbol)
    
    def _update_staleness_level(self, symbol: str):
        """Update staleness level for a symbol."""
        if symbol not in self.last_update_times:
            self.staleness_levels[symbol] = StalenessLevel.CRITICAL_STALE
            return
        
        current_time = time.time()
        age = current_time - self.last_update_times[symbol]
        
        if age <= self.config.fresh_threshold:
            self.staleness_levels[symbol] = StalenessLevel.FRESH
        elif age <= self.config.stale_threshold:
            self.staleness_levels[symbol] = StalenessLevel.STALE
        elif age <= self.config.very_stale_threshold:
            self.staleness_levels[symbol] = StalenessLevel.VERY_STALE
        else:
            self.staleness_levels[symbol] = StalenessLevel.CRITICAL_STALE
    
    def get_staleness_level(self, symbol: str) -> StalenessLevel:
        """Get current staleness level for a symbol."""
        with self.lock:
            self._update_staleness_level(symbol)
            return self.staleness_levels.get(symbol, StalenessLevel.CRITICAL_STALE)
    
    def should_demote(self, symbol: str) -> bool:
        """Check if symbol should be demoted due to staleness."""
        if not self.config.demotion_enabled:
            return False
        
        staleness = self.get_staleness_level(symbol)
        return staleness in [StalenessLevel.VERY_STALE, StalenessLevel.CRITICAL_STALE]
    
    def demote_symbol(self, symbol: str) -> bool:
        """Demote symbol due to staleness."""
        if self.should_demote(symbol):
            self.demotion_count += 1
            logger.warning(f"Symbol {symbol} demoted due to staleness: {self.get_staleness_level(symbol).value}")
            return True
        return False
    
    def get_staleness_stats(self, symbol: str) -> Dict[str, Any]:
        """Get staleness statistics for a symbol."""
        with self.lock:
            if symbol not in self.last_update_times:
                return {
                    'staleness_level': StalenessLevel.CRITICAL_STALE.value,
                    'age_seconds': float('inf'),
                    'is_demoted': True
                }
            
            current_time = time.time()
            age = current_time - self.last_update_times[symbol]
            staleness = self.get_staleness_level(symbol)
            
            return {
                'staleness_level': staleness.value,
                'age_seconds': age,
                'is_demoted': self.should_demote(symbol),
                'last_update': self.last_update_times[symbol]
            }

class RiskControlManager:
    """Comprehensive risk control management system."""
    
    def __init__(self):
        self.lot_caps: Dict[str, LotCapGuard] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.staleness_detectors: Dict[str, StalenessDetector] = {}
        self.risk_metrics: Dict[str, RiskMetrics] = {}
        self.alert_callbacks: List[callable] = []
        self.lock = threading.RLock()
        
        # Initialize default configurations
        self._initialize_default_configs()
    
    def _initialize_default_configs(self):
        """Initialize default risk control configurations."""
        # Default lot cap configurations for major symbols
        default_symbols = ["BTCUSDc", "XAUUSDc", "EURUSDc", "GBPUSDc", "USDJPYc"]
        
        for symbol in default_symbols:
            self.add_lot_cap(LotCapConfig(symbol=symbol))
            self.add_staleness_detector(StalenessConfig(symbol=symbol))
        
        # Default circuit breakers
        self.add_circuit_breaker(CircuitBreakerConfig(
            name="drawdown_breaker",
            threshold=0.05,  # 5% drawdown
            time_window=300,  # 5 minutes
            cooldown_period=600,  # 10 minutes
            ttl_seconds=1800  # 30 minutes
        ))
        
        self.add_circuit_breaker(CircuitBreakerConfig(
            name="latency_breaker",
            threshold=500,  # 500ms latency
            time_window=60,  # 1 minute
            cooldown_period=300,  # 5 minutes
            ttl_seconds=900  # 15 minutes
        ))
        
        self.add_circuit_breaker(CircuitBreakerConfig(
            name="error_rate_breaker",
            threshold=0.1,  # 10% error rate
            time_window=300,  # 5 minutes
            cooldown_period=600,  # 10 minutes
            ttl_seconds=1800  # 30 minutes
        ))
    
    def add_lot_cap(self, config: LotCapConfig):
        """Add lot cap configuration for a symbol."""
        with self.lock:
            self.lot_caps[config.symbol] = LotCapGuard(config)
            logger.info(f"Added lot cap for {config.symbol}: max={config.max_lot_size}, daily={config.daily_lot_limit}")
    
    def add_circuit_breaker(self, config: CircuitBreakerConfig):
        """Add circuit breaker configuration."""
        with self.lock:
            self.circuit_breakers[config.name] = CircuitBreaker(config)
            logger.info(f"Added circuit breaker '{config.name}': threshold={config.threshold}")
    
    def add_staleness_detector(self, config: StalenessConfig):
        """Add staleness detector for a symbol."""
        with self.lock:
            self.staleness_detectors[config.symbol] = StalenessDetector(config)
            logger.info(f"Added staleness detector for {config.symbol}")
    
    def check_lot_cap(self, symbol: str, requested_lot: float) -> Tuple[bool, str, float]:
        """Check if lot size request is within caps."""
        if symbol not in self.lot_caps:
            return True, "No lot cap configured", requested_lot
        
        return self.lot_caps[symbol].check_lot_cap(symbol, requested_lot)
    
    def record_lot_usage(self, symbol: str, lot_size: float):
        """Record lot usage for tracking."""
        if symbol in self.lot_caps:
            self.lot_caps[symbol].record_lot_usage(symbol, lot_size)
    
    def record_lot_reduction(self, symbol: str, lot_size: float):
        """Record lot size reduction."""
        if symbol in self.lot_caps:
            self.lot_caps[symbol].record_lot_reduction(symbol, lot_size)
    
    def check_circuit_breaker(self, name: str, value: float) -> bool:
        """Check if circuit breaker is open."""
        if name not in self.circuit_breakers:
            return False
        
        breaker = self.circuit_breakers[name]
        if breaker.is_open():
            return True
        
        # Check if condition is met
        if breaker.check_condition(value):
            breaker.trigger(value, f"Value {value} exceeds threshold")
            return True
        
        return False
    
    def update_staleness(self, symbol: str, timestamp: float):
        """Update staleness information for a symbol."""
        if symbol in self.staleness_detectors:
            self.staleness_detectors[symbol].update_timestamp(symbol, timestamp)
    
    def check_staleness_demotion(self, symbol: str) -> bool:
        """Check if symbol should be demoted due to staleness."""
        if symbol not in self.staleness_detectors:
            return False
        
        return self.staleness_detectors[symbol].should_demote(symbol)
    
    def demote_stale_symbol(self, symbol: str) -> bool:
        """Demote symbol due to staleness."""
        if symbol not in self.staleness_detectors:
            return False
        
        return self.staleness_detectors[symbol].demote_symbol(symbol)
    
    def get_risk_assessment(self, symbol: str) -> RiskMetrics:
        """Get comprehensive risk assessment for a symbol."""
        with self.lock:
            if symbol not in self.risk_metrics:
                self.risk_metrics[symbol] = RiskMetrics(symbol=symbol)
            
            metrics = self.risk_metrics[symbol]
            
            # Update lot usage
            if symbol in self.lot_caps:
                usage_stats = self.lot_caps[symbol].get_usage_stats(symbol)
                metrics.current_lot_size = usage_stats['current_usage']
                metrics.daily_lot_usage = usage_stats['daily_usage']
                metrics.hourly_lot_usage = usage_stats['hourly_usage']
                metrics.position_count = usage_stats['position_count']
            
            # Update staleness
            if symbol in self.staleness_detectors:
                metrics.staleness_level = self.staleness_detectors[symbol].get_staleness_level(symbol)
            
            # Calculate risk level
            metrics.risk_level = self._calculate_risk_level(metrics)
            metrics.last_update = time.time()
            
            return metrics
    
    def _calculate_risk_level(self, metrics: RiskMetrics) -> RiskLevel:
        """Calculate overall risk level based on metrics."""
        risk_score = 0
        
        # Lot usage risk
        if metrics.current_lot_size > 0.05:
            risk_score += 2
        elif metrics.current_lot_size > 0.02:
            risk_score += 1
        
        # Staleness risk
        if metrics.staleness_level == StalenessLevel.CRITICAL_STALE:
            risk_score += 5  # Critical staleness should be critical risk
        elif metrics.staleness_level == StalenessLevel.VERY_STALE:
            risk_score += 3
        elif metrics.staleness_level == StalenessLevel.STALE:
            risk_score += 1
        
        # Position count risk
        if metrics.position_count > 3:
            risk_score += 2
        elif metrics.position_count > 1:
            risk_score += 1
        
        # Determine risk level
        if risk_score >= 5:
            return RiskLevel.CRITICAL
        elif risk_score >= 3:
            return RiskLevel.HIGH
        elif risk_score >= 1:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system risk status."""
        with self.lock:
            status = {
                'total_symbols': len(self.risk_metrics),
                'circuit_breakers': {},
                'staleness_summary': {},
                'lot_cap_summary': {},
                'overall_risk_level': RiskLevel.LOW.value
            }
            
            # Circuit breaker status
            for name, breaker in self.circuit_breakers.items():
                status['circuit_breakers'][name] = breaker.get_status()
            
            # Staleness summary
            for symbol, detector in self.staleness_detectors.items():
                status['staleness_summary'][symbol] = detector.get_staleness_stats(symbol)
            
            # Lot cap summary
            for symbol, lot_cap in self.lot_caps.items():
                status['lot_cap_summary'][symbol] = lot_cap.get_usage_stats(symbol)
            
            # Overall risk level
            max_risk = RiskLevel.LOW
            for metrics in self.risk_metrics.values():
                if metrics.risk_level.value > max_risk.value:
                    max_risk = metrics.risk_level
            
            status['overall_risk_level'] = max_risk.value
            
            return status
    
    def add_alert_callback(self, callback: callable):
        """Add alert callback for risk events."""
        self.alert_callbacks.append(callback)
    
    def _trigger_alert(self, symbol: str, event_type: str, message: str):
        """Trigger alert for risk events."""
        for callback in self.alert_callbacks:
            try:
                callback(symbol, event_type, message)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

# Global risk control manager instance
risk_control_manager = RiskControlManager()

def get_risk_control_manager() -> RiskControlManager:
    """Get the global risk control manager instance."""
    return risk_control_manager

def check_lot_cap(symbol: str, requested_lot: float) -> Tuple[bool, str, float]:
    """Check if lot size request is within caps."""
    return risk_control_manager.check_lot_cap(symbol, requested_lot)

def check_circuit_breaker(name: str, value: float) -> bool:
    """Check if circuit breaker is open."""
    return risk_control_manager.check_circuit_breaker(name, value)

def update_staleness(symbol: str, timestamp: float):
    """Update staleness information for a symbol."""
    risk_control_manager.update_staleness(symbol, timestamp)

def get_risk_assessment(symbol: str) -> RiskMetrics:
    """Get comprehensive risk assessment for a symbol."""
    return risk_control_manager.get_risk_assessment(symbol)

if __name__ == "__main__":
    # Example usage
    manager = RiskControlManager()
    
    # Test lot cap
    allowed, reason, adjusted = manager.check_lot_cap("BTCUSDc", 0.005)
    print(f"Lot cap check: {allowed}, {reason}, {adjusted}")
    
    # Test circuit breaker
    breaker_open = manager.check_circuit_breaker("drawdown_breaker", 0.06)
    print(f"Circuit breaker open: {breaker_open}")
    
    # Test staleness
    manager.update_staleness("BTCUSDc", time.time())
    is_demoted = manager.check_staleness_demotion("BTCUSDc")
    print(f"Symbol demoted: {is_demoted}")
    
    # Get system status
    status = manager.get_system_status()
    print(f"System status: {json.dumps(status, indent=2, default=str)}")
