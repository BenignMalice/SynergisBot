"""
Comprehensive Risk Controls Tests
Tests lot caps, circuit breakers, and staleness demotion systems
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch
from typing import Dict, Any

# Import risk control components
from infra.risk_controls import (
    RiskControlManager,
    LotCapGuard,
    CircuitBreaker,
    StalenessDetector,
    LotCapConfig,
    CircuitBreakerConfig,
    StalenessConfig,
    RiskLevel,
    CircuitBreakerState,
    StalenessLevel,
    get_risk_control_manager,
    check_lot_cap,
    check_circuit_breaker,
    update_staleness,
    get_risk_assessment
)

class TestLotCapGuard:
    """Test lot size cap enforcement."""
    
    def test_lot_cap_initialization(self):
        """Test lot cap guard initialization."""
        config = LotCapConfig(
            symbol="BTCUSDc",
            max_lot_size=0.01,
            hard_cap_multiplier=1.5,
            daily_lot_limit=1.0,
            hourly_lot_limit=0.1
        )
        guard = LotCapGuard(config)
        
        assert guard.config.symbol == "BTCUSDc"
        assert guard.config.max_lot_size == 0.01
        assert guard.config.hard_cap_multiplier == 1.5
    
    def test_lot_cap_within_limits(self):
        """Test lot cap check within limits."""
        config = LotCapConfig(symbol="BTCUSDc", max_lot_size=0.01)
        guard = LotCapGuard(config)
        
        allowed, reason, adjusted = guard.check_lot_cap("BTCUSDc", 0.005)
        
        assert allowed is True
        assert "within limits" in reason
        assert adjusted == 0.005
    
    def test_lot_cap_hard_cap_exceeded(self):
        """Test lot cap hard cap exceeded."""
        config = LotCapConfig(symbol="BTCUSDc", max_lot_size=0.01, hard_cap_multiplier=1.5)
        guard = LotCapGuard(config)
        
        allowed, reason, adjusted = guard.check_lot_cap("BTCUSDc", 0.02)
        
        assert allowed is False
        assert "hard cap" in reason
        assert adjusted == 0.0
    
    def test_lot_cap_daily_limit_exceeded(self):
        """Test lot cap daily limit exceeded."""
        config = LotCapConfig(symbol="BTCUSDc", max_lot_size=0.1, daily_lot_limit=0.1)
        guard = LotCapGuard(config)
        
        # First request should pass
        allowed, reason, adjusted = guard.check_lot_cap("BTCUSDc", 0.05)
        assert allowed is True
        
        # Record the usage
        guard.record_lot_usage("BTCUSDc", 0.05)
        
        # Second request should exceed daily limit
        allowed, reason, adjusted = guard.check_lot_cap("BTCUSDc", 0.06)
        assert allowed is False
        assert "Daily lot limit exceeded" in reason
    
    def test_lot_cap_hourly_limit_exceeded(self):
        """Test lot cap hourly limit exceeded."""
        config = LotCapConfig(symbol="BTCUSDc", max_lot_size=0.1, hourly_lot_limit=0.05)
        guard = LotCapGuard(config)
        
        # First request should pass
        allowed, reason, adjusted = guard.check_lot_cap("BTCUSDc", 0.03)
        assert allowed is True
        
        # Record the usage
        guard.record_lot_usage("BTCUSDc", 0.03)
        
        # Second request should exceed hourly limit
        allowed, reason, adjusted = guard.check_lot_cap("BTCUSDc", 0.03)
        assert allowed is False
        assert "Hourly lot limit exceeded" in reason
    
    def test_lot_cap_emergency_stop(self):
        """Test lot cap emergency stop threshold."""
        config = LotCapConfig(symbol="BTCUSDc", max_lot_size=0.1, hourly_lot_limit=0.2, emergency_stop_threshold=0.1)
        guard = LotCapGuard(config)
        
        # Record usage up to emergency threshold
        guard.record_lot_usage("BTCUSDc", 0.09)
        
        # Next request should trigger emergency stop
        allowed, reason, adjusted = guard.check_lot_cap("BTCUSDc", 0.02)
        assert allowed is False
        assert "Emergency stop threshold exceeded" in reason
    
    def test_lot_cap_usage_tracking(self):
        """Test lot cap usage tracking."""
        config = LotCapConfig(symbol="BTCUSDc", max_lot_size=0.1)
        guard = LotCapGuard(config)
        
        # Record usage
        guard.record_lot_usage("BTCUSDc", 0.01)
        guard.record_lot_usage("BTCUSDc", 0.02)
        
        # Check usage stats
        stats = guard.get_usage_stats("BTCUSDc")
        assert stats['current_usage'] == 0.03
        assert stats['position_count'] == 2
        
        # Record reduction
        guard.record_lot_reduction("BTCUSDc", 0.01)
        
        # Check updated stats
        stats = guard.get_usage_stats("BTCUSDc")
        assert abs(stats['current_usage'] - 0.02) < 0.001  # Allow for floating point precision
        assert stats['position_count'] == 1

class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initialization."""
        config = CircuitBreakerConfig(
            name="test_breaker",
            threshold=0.05,
            time_window=300,
            cooldown_period=600
        )
        breaker = CircuitBreaker(config)
        
        assert breaker.config.name == "test_breaker"
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.trigger_count == 0
    
    def test_circuit_breaker_trigger(self):
        """Test circuit breaker triggering."""
        config = CircuitBreakerConfig(
            name="test_breaker",
            threshold=0.05,
            time_window=300,
            cooldown_period=600
        )
        breaker = CircuitBreaker(config)
        
        # Trigger the breaker
        breaker.trigger(0.06, "Test trigger")
        
        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.trigger_count == 1
        assert breaker.is_open() is True
    
    def test_circuit_breaker_cooldown(self):
        """Test circuit breaker cooldown period."""
        config = CircuitBreakerConfig(
            name="test_breaker",
            threshold=0.05,
            time_window=300,
            cooldown_period=1  # 1 second cooldown for testing
        )
        breaker = CircuitBreaker(config)
        
        # Trigger the breaker
        breaker.trigger(0.06, "Test trigger")
        assert breaker.is_open() is True
        
        # Wait for cooldown
        time.sleep(1.1)
        
        # Call is_open to trigger state transition
        breaker.is_open()
        
        # Should be in half-open state
        assert breaker.state == CircuitBreakerState.HALF_OPEN
        assert breaker.is_open() is False
    
    def test_circuit_breaker_ttl_expiration(self):
        """Test circuit breaker TTL expiration."""
        config = CircuitBreakerConfig(
            name="test_breaker",
            threshold=0.05,
            time_window=300,
            cooldown_period=600,
            ttl_seconds=1  # 1 second TTL for testing
        )
        breaker = CircuitBreaker(config)
        
        # Trigger the breaker
        breaker.trigger(0.06, "Test trigger")
        assert breaker.is_open() is True
        
        # Wait for TTL expiration
        time.sleep(1.1)
        
        # Call is_open to trigger state transition
        breaker.is_open()
        
        # Should be closed due to TTL expiration
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.is_open() is False
    
    def test_circuit_breaker_max_triggers(self):
        """Test circuit breaker max trigger count."""
        config = CircuitBreakerConfig(
            name="test_breaker",
            threshold=0.05,
            time_window=300,
            cooldown_period=600,
            max_trigger_count=2
        )
        breaker = CircuitBreaker(config)
        
        # Trigger twice
        breaker.trigger(0.06, "First trigger")
        breaker.trigger(0.07, "Second trigger")
        
        # Should still be open after TTL due to max triggers
        time.sleep(1.1)
        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.is_open() is True
    
    def test_circuit_breaker_status(self):
        """Test circuit breaker status reporting."""
        config = CircuitBreakerConfig(
            name="test_breaker",
            threshold=0.05,
            time_window=300,
            cooldown_period=600
        )
        breaker = CircuitBreaker(config)
        
        status = breaker.get_status()
        
        assert status['name'] == "test_breaker"
        assert status['state'] == CircuitBreakerState.CLOSED.value
        assert status['trigger_count'] == 0
        assert status['enabled'] is True

class TestStalenessDetector:
    """Test staleness detection and demotion."""
    
    def test_staleness_detector_initialization(self):
        """Test staleness detector initialization."""
        config = StalenessConfig(
            symbol="BTCUSDc",
            fresh_threshold=1.0,
            stale_threshold=5.0,
            very_stale_threshold=30.0
        )
        detector = StalenessDetector(config)
        
        assert detector.config.symbol == "BTCUSDc"
        assert detector.config.fresh_threshold == 1.0
        assert detector.demotion_count == 0
    
    def test_staleness_levels(self):
        """Test staleness level detection."""
        config = StalenessConfig(
            symbol="BTCUSDc",
            fresh_threshold=1.0,
            stale_threshold=5.0,
            very_stale_threshold=30.0
        )
        detector = StalenessDetector(config)
        
        current_time = time.time()
        
        # Fresh data
        detector.update_timestamp("BTCUSDc", current_time)
        assert detector.get_staleness_level("BTCUSDc") == StalenessLevel.FRESH
        
        # Stale data
        detector.update_timestamp("BTCUSDc", current_time - 3.0)
        assert detector.get_staleness_level("BTCUSDc") == StalenessLevel.STALE
        
        # Very stale data
        detector.update_timestamp("BTCUSDc", current_time - 15.0)
        assert detector.get_staleness_level("BTCUSDc") == StalenessLevel.VERY_STALE
        
        # Critical stale data
        detector.update_timestamp("BTCUSDc", current_time - 45.0)
        assert detector.get_staleness_level("BTCUSDc") == StalenessLevel.CRITICAL_STALE
    
    def test_staleness_demotion(self):
        """Test staleness demotion logic."""
        config = StalenessConfig(
            symbol="BTCUSDc",
            fresh_threshold=1.0,
            stale_threshold=5.0,
            very_stale_threshold=30.0,
            demotion_enabled=True
        )
        detector = StalenessDetector(config)
        
        current_time = time.time()
        
        # Fresh data should not be demoted
        detector.update_timestamp("BTCUSDc", current_time)
        assert detector.should_demote("BTCUSDc") is False
        
        # Very stale data should be demoted
        detector.update_timestamp("BTCUSDc", current_time - 35.0)
        assert detector.should_demote("BTCUSDc") is True
        
        # Demote the symbol
        demoted = detector.demote_symbol("BTCUSDc")
        assert demoted is True
        assert detector.demotion_count == 1
    
    def test_staleness_stats(self):
        """Test staleness statistics."""
        config = StalenessConfig(symbol="BTCUSDc")
        detector = StalenessDetector(config)
        
        current_time = time.time()
        detector.update_timestamp("BTCUSDc", current_time - 10.0)
        
        stats = detector.get_staleness_stats("BTCUSDc")
        
        assert stats['staleness_level'] == StalenessLevel.VERY_STALE.value
        assert stats['age_seconds'] > 9.0
        assert stats['is_demoted'] is True
        assert 'last_update' in stats

class TestRiskControlManager:
    """Test comprehensive risk control management."""
    
    def test_risk_control_manager_initialization(self):
        """Test risk control manager initialization."""
        manager = RiskControlManager()
        
        assert manager is not None
        assert hasattr(manager, 'lot_caps')
        assert hasattr(manager, 'circuit_breakers')
        assert hasattr(manager, 'staleness_detectors')
        assert hasattr(manager, 'risk_metrics')
    
    def test_add_lot_cap(self):
        """Test adding lot cap configuration."""
        manager = RiskControlManager()
        config = LotCapConfig(symbol="TESTc", max_lot_size=0.02)
        
        manager.add_lot_cap(config)
        
        assert "TESTc" in manager.lot_caps
        assert manager.lot_caps["TESTc"].config.symbol == "TESTc"
    
    def test_add_circuit_breaker(self):
        """Test adding circuit breaker configuration."""
        manager = RiskControlManager()
        config = CircuitBreakerConfig(
            name="test_breaker",
            threshold=0.1,
            time_window=300,
            cooldown_period=600
        )
        
        manager.add_circuit_breaker(config)
        
        assert "test_breaker" in manager.circuit_breakers
        assert manager.circuit_breakers["test_breaker"].config.name == "test_breaker"
    
    def test_add_staleness_detector(self):
        """Test adding staleness detector configuration."""
        manager = RiskControlManager()
        config = StalenessConfig(symbol="TESTc")
        
        manager.add_staleness_detector(config)
        
        assert "TESTc" in manager.staleness_detectors
        assert manager.staleness_detectors["TESTc"].config.symbol == "TESTc"
    
    def test_lot_cap_check(self):
        """Test lot cap checking through manager."""
        manager = RiskControlManager()
        config = LotCapConfig(symbol="TESTc", max_lot_size=0.01)
        manager.add_lot_cap(config)
        
        allowed, reason, adjusted = manager.check_lot_cap("TESTc", 0.005)
        
        assert allowed is True
        assert "within limits" in reason
        assert adjusted == 0.005
    
    def test_circuit_breaker_check(self):
        """Test circuit breaker checking through manager."""
        manager = RiskControlManager()
        config = CircuitBreakerConfig(
            name="test_breaker",
            threshold=0.05,
            time_window=300,
            cooldown_period=600
        )
        manager.add_circuit_breaker(config)
        
        # Check with value below threshold
        is_open = manager.check_circuit_breaker("test_breaker", 0.03)
        assert is_open is False
        
        # Check with value above threshold
        is_open = manager.check_circuit_breaker("test_breaker", 0.06)
        assert is_open is True
    
    def test_staleness_update(self):
        """Test staleness update through manager."""
        manager = RiskControlManager()
        config = StalenessConfig(symbol="TESTc")
        manager.add_staleness_detector(config)
        
        current_time = time.time()
        manager.update_staleness("TESTc", current_time)
        
        # Check staleness level
        staleness = manager.staleness_detectors["TESTc"].get_staleness_level("TESTc")
        assert staleness == StalenessLevel.FRESH
    
    def test_risk_assessment(self):
        """Test risk assessment generation."""
        manager = RiskControlManager()
        
        # Add configurations
        manager.add_lot_cap(LotCapConfig(symbol="TESTc", max_lot_size=0.01))
        manager.add_staleness_detector(StalenessConfig(symbol="TESTc"))
        
        # Update staleness
        manager.update_staleness("TESTc", time.time())
        
        # Get risk assessment
        assessment = manager.get_risk_assessment("TESTc")
        
        assert assessment.symbol == "TESTc"
        assert assessment.risk_level == RiskLevel.LOW
        assert assessment.staleness_level == StalenessLevel.FRESH
    
    def test_system_status(self):
        """Test system status reporting."""
        manager = RiskControlManager()
        
        status = manager.get_system_status()
        
        assert 'total_symbols' in status
        assert 'circuit_breakers' in status
        assert 'staleness_summary' in status
        assert 'lot_cap_summary' in status
        assert 'overall_risk_level' in status
        
        assert status['overall_risk_level'] == RiskLevel.LOW.value

class TestGlobalFunctions:
    """Test global risk control functions."""
    
    def test_get_risk_control_manager(self):
        """Test getting global risk control manager."""
        manager = get_risk_control_manager()
        assert manager is not None
        assert isinstance(manager, RiskControlManager)
    
    def test_check_lot_cap_global(self):
        """Test global lot cap checking."""
        # This will use the global manager
        allowed, reason, adjusted = check_lot_cap("BTCUSDc", 0.005)
        
        # Should work with default configurations
        assert isinstance(allowed, bool)
        assert isinstance(reason, str)
        assert isinstance(adjusted, float)
    
    def test_check_circuit_breaker_global(self):
        """Test global circuit breaker checking."""
        # This will use the global manager
        is_open = check_circuit_breaker("drawdown_breaker", 0.03)
        
        # Should work with default configurations
        assert isinstance(is_open, bool)
    
    def test_update_staleness_global(self):
        """Test global staleness update."""
        # This will use the global manager
        current_time = time.time()
        update_staleness("BTCUSDc", current_time)
        
        # Should work without errors
        assert True
    
    def test_get_risk_assessment_global(self):
        """Test global risk assessment."""
        # This will use the global manager
        assessment = get_risk_assessment("BTCUSDc")
        
        assert assessment.symbol == "BTCUSDc"
        assert hasattr(assessment, 'risk_level')
        assert hasattr(assessment, 'staleness_level')

class TestRiskLevelCalculation:
    """Test risk level calculation logic."""
    
    def test_low_risk_level(self):
        """Test low risk level calculation."""
        manager = RiskControlManager()
        
        # Add fresh data
        manager.add_staleness_detector(StalenessConfig(symbol="TESTc"))
        manager.update_staleness("TESTc", time.time())
        
        assessment = manager.get_risk_assessment("TESTc")
        assert assessment.risk_level == RiskLevel.LOW
    
    def test_high_risk_level(self):
        """Test high risk level calculation."""
        manager = RiskControlManager()
        
        # Add stale data
        manager.add_staleness_detector(StalenessConfig(symbol="TESTc"))
        manager.update_staleness("TESTc", time.time() - 35.0)  # Very stale
        
        assessment = manager.get_risk_assessment("TESTc")
        assert assessment.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    
    def test_critical_risk_level(self):
        """Test critical risk level calculation."""
        manager = RiskControlManager()
        
        # Add very stale data
        manager.add_staleness_detector(StalenessConfig(symbol="TESTc"))
        manager.update_staleness("TESTc", time.time() - 65.0)  # Critical stale
        
        assessment = manager.get_risk_assessment("TESTc")
        assert assessment.risk_level == RiskLevel.CRITICAL

class TestConcurrency:
    """Test concurrent access to risk controls."""
    
    def test_concurrent_lot_cap_checks(self):
        """Test concurrent lot cap checks."""
        manager = RiskControlManager()
        config = LotCapConfig(symbol="TESTc", max_lot_size=0.01)
        manager.add_lot_cap(config)
        
        results = []
        
        def check_lot_cap():
            allowed, reason, adjusted = manager.check_lot_cap("TESTc", 0.005)
            results.append((allowed, reason, adjusted))
        
        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=check_lot_cap)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All results should be the same
        assert len(results) == 10
        for allowed, reason, adjusted in results:
            assert allowed is True
            assert "within limits" in reason
            assert adjusted == 0.005
    
    def test_concurrent_circuit_breaker_checks(self):
        """Test concurrent circuit breaker checks."""
        manager = RiskControlManager()
        config = CircuitBreakerConfig(
            name="test_breaker",
            threshold=0.05,
            time_window=300,
            cooldown_period=600
        )
        manager.add_circuit_breaker(config)
        
        results = []
        
        def check_breaker():
            is_open = manager.check_circuit_breaker("test_breaker", 0.06)
            results.append(is_open)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=check_breaker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All results should be the same
        assert len(results) == 5
        for is_open in results:
            assert is_open is True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
