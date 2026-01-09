"""
Tests for Staged Activation System

This module tests the staged activation system including:
- SLO monitoring and threshold evaluation
- Activation criteria checking
- Position size multiplier management
- Rollback mechanisms
- Performance tracking and metrics
- Database operations and persistence
"""

import pytest
import sqlite3
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from infra.staged_activation_system import (
    StagedActivationSystem, StagedActivationConfig, SLOMonitor, ActivationManager,
    SLOThreshold, SLOMeasurement, ActivationEvent, ActivationStage, SLOStatus,
    ActivationTrigger, StagedActivationConfig,
    get_staged_activation_system, create_staged_activation_system,
    start_staged_activation, stop_staged_activation, get_position_size_multiplier,
    record_trade, record_performance_metric, get_activation_status,
    manual_activate, manual_rollback
)


class TestSLOThreshold:
    """Test SLO threshold functionality"""
    
    def test_slo_threshold_creation(self):
        """Test SLO threshold creation"""
        slo = SLOThreshold(
            name="win_rate",
            metric="avg",
            threshold_value=0.8,
            comparison="gte",
            window_size=50,
            severity="critical",
            description="Win rate must be >= 80%"
        )
        
        assert slo.name == "win_rate"
        assert slo.metric == "avg"
        assert slo.threshold_value == 0.8
        assert slo.comparison == "gte"
        assert slo.window_size == 50
        assert slo.severity == "critical"
        assert slo.description == "Win rate must be >= 80%"

    def test_slo_threshold_defaults(self):
        """Test SLO threshold with defaults"""
        slo = SLOThreshold(
            name="latency",
            metric="p95",
            threshold_value=200.0,
            comparison="lte",
            window_size=100,
            severity="warning"
        )
        
        assert slo.name == "latency"
        assert slo.description == ""


class TestSLOMeasurement:
    """Test SLO measurement functionality"""
    
    def test_slo_measurement_creation(self):
        """Test SLO measurement creation"""
        measurement = SLOMeasurement(
            slo_name="win_rate",
            value=0.85,
            threshold=0.8,
            status=SLOStatus.MET,
            timestamp=time.time(),
            window_start=time.time() - 3600,
            window_end=time.time(),
            sample_count=50
        )
        
        assert measurement.slo_name == "win_rate"
        assert measurement.value == 0.85
        assert measurement.threshold == 0.8
        assert measurement.status == SLOStatus.MET
        assert measurement.sample_count == 50

    def test_slo_measurement_with_metadata(self):
        """Test SLO measurement with metadata"""
        metadata = {"raw_values": [0.8, 0.9, 0.85, 0.88]}
        measurement = SLOMeasurement(
            slo_name="win_rate",
            value=0.85,
            threshold=0.8,
            status=SLOStatus.MET,
            timestamp=time.time(),
            window_start=time.time() - 3600,
            window_end=time.time(),
            sample_count=4,
            metadata=metadata
        )
        
        assert measurement.metadata == metadata


class TestActivationEvent:
    """Test activation event functionality"""
    
    def test_activation_event_creation(self):
        """Test activation event creation"""
        event = ActivationEvent(
            event_id="ACT_12345678",
            timestamp=time.time(),
            from_stage=ActivationStage.INITIAL,
            to_stage=ActivationStage.STAGED,
            trigger=ActivationTrigger.TRADE_COUNT,
            reason="Trade count threshold reached",
            slo_status={"win_rate": SLOStatus.MET, "profit_factor": SLOStatus.MET},
            performance_metrics={"win_rate": 0.85, "profit_factor": 2.1}
        )
        
        assert event.event_id == "ACT_12345678"
        assert event.from_stage == ActivationStage.INITIAL
        assert event.to_stage == ActivationStage.STAGED
        assert event.trigger == ActivationTrigger.TRADE_COUNT
        assert event.reason == "Trade count threshold reached"
        assert len(event.slo_status) == 2
        assert len(event.performance_metrics) == 2

    def test_activation_event_with_metadata(self):
        """Test activation event with metadata"""
        metadata = {"trade_count": 200, "elapsed_hours": 24.5}
        event = ActivationEvent(
            event_id="ACT_87654321",
            timestamp=time.time(),
            from_stage=ActivationStage.STAGED,
            to_stage=ActivationStage.FULL,
            trigger=ActivationTrigger.TIME_ELAPSED,
            reason="Time threshold reached",
            slo_status={"win_rate": SLOStatus.MET},
            performance_metrics={"win_rate": 0.85},
            metadata=metadata
        )
        
        assert event.metadata == metadata


class TestStagedActivationConfig:
    """Test staged activation configuration"""
    
    def test_config_creation(self):
        """Test configuration creation with defaults"""
        config = StagedActivationConfig()
        
        assert config.initial_position_size == 0.5
        assert config.full_position_size == 1.0
        assert config.trade_count_threshold == 200
        assert config.time_threshold_hours == 168
        assert config.performance_threshold == 0.8
        assert config.slo_check_interval_seconds == 60
        assert config.activation_cooldown_seconds == 3600
        assert config.rollback_threshold == 3
        assert config.max_rollbacks == 2
        assert config.enable_auto_activation == True
        assert config.enable_auto_rollback == True
        assert config.log_level == "INFO"
        assert config.data_retention_days == 30

    def test_config_custom_values(self):
        """Test configuration with custom values"""
        config = StagedActivationConfig(
            initial_position_size=0.3,
            full_position_size=1.0,
            trade_count_threshold=100,
            time_threshold_hours=72,
            performance_threshold=0.9,
            slo_check_interval_seconds=30,
            activation_cooldown_seconds=1800,
            rollback_threshold=2,
            max_rollbacks=1,
            enable_auto_activation=False,
            enable_auto_rollback=False
        )
        
        assert config.initial_position_size == 0.3
        assert config.full_position_size == 1.0
        assert config.trade_count_threshold == 100
        assert config.time_threshold_hours == 72
        assert config.performance_threshold == 0.9
        assert config.slo_check_interval_seconds == 30
        assert config.activation_cooldown_seconds == 1800
        assert config.rollback_threshold == 2
        assert config.max_rollbacks == 1
        assert config.enable_auto_activation == False
        assert config.enable_auto_rollback == False


class TestSLOMonitor:
    """Test SLO monitoring functionality"""
    
    def setup_method(self):
        """Setup test method"""
        self.config = StagedActivationConfig()
        self.monitor = SLOMonitor(self.config)

    def test_monitor_initialization(self):
        """Test SLO monitor initialization"""
        assert self.monitor.config == self.config
        assert self.monitor.slo_thresholds == {}
        assert len(self.monitor.measurements) == 0

    def test_add_slo_threshold(self):
        """Test adding SLO threshold"""
        slo = SLOThreshold(
            name="win_rate",
            metric="avg",
            threshold_value=0.8,
            comparison="gte",
            window_size=50,
            severity="critical"
        )
        
        self.monitor.add_slo_threshold(slo)
        assert "win_rate" in self.monitor.slo_thresholds
        assert self.monitor.slo_thresholds["win_rate"] == slo

    def test_record_measurement(self):
        """Test recording SLO measurement"""
        self.monitor.record_measurement("win_rate", 0.85)
        
        assert "win_rate" in self.monitor.measurements
        assert len(self.monitor.measurements["win_rate"]) == 1
        assert self.monitor.measurements["win_rate"][0]["value"] == 0.85

    def test_record_measurement_with_timestamp(self):
        """Test recording SLO measurement with timestamp"""
        timestamp = time.time()
        self.monitor.record_measurement("win_rate", 0.85, timestamp)
        
        measurement = self.monitor.measurements["win_rate"][0]
        assert measurement["value"] == 0.85
        assert measurement["timestamp"] == timestamp

    def test_check_slo_status_insufficient_data(self):
        """Test SLO status check with insufficient data"""
        slo = SLOThreshold(
            name="win_rate",
            metric="avg",
            threshold_value=0.8,
            comparison="gte",
            window_size=50,
            severity="critical"
        )
        
        self.monitor.add_slo_threshold(slo)
        
        # Add only 10 measurements (less than window_size of 50)
        for i in range(10):
            self.monitor.record_measurement("win_rate", 0.85)
            
        result = self.monitor.check_slo_status("win_rate")
        assert result is None

    def test_check_slo_status_sufficient_data(self):
        """Test SLO status check with sufficient data"""
        slo = SLOThreshold(
            name="win_rate",
            metric="avg",
            threshold_value=0.8,
            comparison="gte",
            window_size=50,
            severity="critical"
        )
        
        self.monitor.add_slo_threshold(slo)
        
        # Add 50 measurements (equal to window_size)
        for i in range(50):
            self.monitor.record_measurement("win_rate", 0.85)
            
        result = self.monitor.check_slo_status("win_rate")
        assert result is not None
        assert result.slo_name == "win_rate"
        assert result.value == 0.85
        assert result.threshold == 0.8
        assert result.status == SLOStatus.MET
        assert result.sample_count == 50

    def test_check_slo_status_violated(self):
        """Test SLO status check with violated threshold"""
        slo = SLOThreshold(
            name="win_rate",
            metric="avg",
            threshold_value=0.8,
            comparison="gte",
            window_size=50,
            severity="critical"
        )
        
        self.monitor.add_slo_threshold(slo)
        
        # Add 50 measurements with low win rate
        for i in range(50):
            self.monitor.record_measurement("win_rate", 0.75)
            
        result = self.monitor.check_slo_status("win_rate")
        assert result is not None
        assert result.value == 0.75
        assert result.status == SLOStatus.VIOLATED

    def test_get_all_slo_status(self):
        """Test getting all SLO status"""
        slo1 = SLOThreshold(
            name="win_rate",
            metric="avg",
            threshold_value=0.8,
            comparison="gte",
            window_size=50,
            severity="critical"
        )
        
        slo2 = SLOThreshold(
            name="profit_factor",
            metric="avg",
            threshold_value=2.0,
            comparison="gte",
            window_size=50,
            severity="critical"
        )
        
        self.monitor.add_slo_threshold(slo1)
        self.monitor.add_slo_threshold(slo2)
        
        # Add measurements for both SLOs
        for i in range(50):
            self.monitor.record_measurement("win_rate", 0.85)
            self.monitor.record_measurement("profit_factor", 2.1)
            
        status = self.monitor.get_all_slo_status()
        assert len(status) == 2
        assert "win_rate" in status
        assert "profit_factor" in status
        assert status["win_rate"].status == SLOStatus.MET
        assert status["profit_factor"].status == SLOStatus.MET


class TestActivationManager:
    """Test activation manager functionality"""
    
    def setup_method(self):
        """Setup test method"""
        self.config = StagedActivationConfig(
            trade_count_threshold=10,  # Lower for testing
            time_threshold_hours=1,   # Lower for testing
            activation_cooldown_seconds=0,  # No cooldown for testing
            rollback_threshold=1  # Lower for testing
        )
        self.manager = ActivationManager(self.config)

    def test_manager_initialization(self):
        """Test activation manager initialization"""
        assert self.manager.config == self.config
        assert self.manager.current_stage == ActivationStage.INITIAL
        assert self.manager.position_size_multiplier == self.config.initial_position_size
        assert self.manager.trade_count == 0
        assert self.manager.rollback_count == 0
        assert len(self.manager.activation_events) == 0

    def test_record_trade(self):
        """Test recording a trade"""
        trade_data = {
            'pnl': 100.0,
            'profit_factor': 2.1,
            'drawdown': 0.02
        }
        
        self.manager.record_trade(trade_data)
        assert self.manager.trade_count == 1

    def test_record_performance_metric(self):
        """Test recording performance metric"""
        self.manager.record_performance_metric("win_rate", 0.85)
        
        # Check that measurement was recorded
        assert "win_rate" in self.manager.slo_monitor.measurements
        assert len(self.manager.slo_monitor.measurements["win_rate"]) == 1

    def test_check_activation_criteria_trade_count(self):
        """Test activation criteria with trade count threshold"""
        # Record enough trades to meet threshold
        for i in range(self.config.trade_count_threshold):
            self.manager.record_trade({'pnl': 100.0})
            
        can_activate, reason, metadata = self.manager.check_activation_criteria()
        assert can_activate
        assert "Trade count threshold reached" in reason
        assert metadata['trade_count'] == self.config.trade_count_threshold
        assert metadata['trigger'] == ActivationTrigger.TRADE_COUNT

    def test_check_activation_criteria_time_elapsed(self):
        """Test activation criteria with time threshold"""
        # Mock start time to be in the past
        self.manager.start_time = time.time() - (self.config.time_threshold_hours * 3600 + 1)
        
        can_activate, reason, metadata = self.manager.check_activation_criteria()
        assert can_activate
        assert "Time threshold reached" in reason
        assert metadata['trigger'] == ActivationTrigger.TIME_ELAPSED

    def test_check_activation_criteria_not_met(self):
        """Test activation criteria not met"""
        can_activate, reason, metadata = self.manager.check_activation_criteria()
        assert not can_activate
        assert "Criteria not met" in reason

    def test_activate_next_stage_initial_to_staged(self):
        """Test activation from initial to staged stage"""
        success = self.manager.activate_next_stage(
            ActivationTrigger.MANUAL, "Test activation"
        )
        
        assert success
        assert self.manager.current_stage == ActivationStage.STAGED
        assert self.manager.position_size_multiplier == self.config.initial_position_size
        assert len(self.manager.activation_events) == 1

    def test_activate_next_stage_staged_to_full(self):
        """Test activation from staged to full stage"""
        # First activate to staged
        self.manager.activate_next_stage(ActivationTrigger.MANUAL, "Initial activation")
        
        # Then activate to full
        success = self.manager.activate_next_stage(
            ActivationTrigger.MANUAL, "Full activation"
        )
        
        assert success
        assert self.manager.current_stage == ActivationStage.FULL
        assert self.manager.position_size_multiplier == self.config.full_position_size
        assert len(self.manager.activation_events) == 2

    def test_activate_next_stage_cooldown(self):
        """Test activation blocked by cooldown"""
        # First activation
        self.manager.activate_next_stage(ActivationTrigger.MANUAL, "First activation")
        
        # Try immediate second activation (should be blocked by cooldown)
        success = self.manager.activate_next_stage(
            ActivationTrigger.MANUAL, "Second activation"
        )
        
        # With cooldown_seconds=0, this should succeed
        assert success

    def test_check_rollback_criteria(self):
        """Test rollback criteria checking"""
        # Add some SLO violations - need to record enough measurements for window_size
        for i in range(50):
            self.manager.slo_monitor.record_measurement("win_rate", 0.75)  # Below threshold
            
        should_rollback, reason, metadata = self.manager.check_rollback_criteria()
        assert should_rollback
        assert "critical SLO violations detected" in reason

    def test_rollback_stage_full_to_staged(self):
        """Test rollback from full to staged stage"""
        # First activate to staged
        self.manager.activate_next_stage(ActivationTrigger.MANUAL, "Activate to staged")
        # Then activate to full
        self.manager.activate_next_stage(ActivationTrigger.MANUAL, "Activate to full")
        
        # Then rollback
        success = self.manager.rollback_stage("Test rollback")
        
        assert success
        assert self.manager.current_stage == ActivationStage.STAGED
        assert self.manager.rollback_count == 1
        assert len(self.manager.activation_events) == 3

    def test_rollback_stage_max_rollbacks(self):
        """Test rollback blocked by max rollbacks"""
        # Set rollback count to max
        self.manager.rollback_count = self.config.max_rollbacks
        
        success = self.manager.rollback_stage("Test rollback")
        assert not success

    def test_get_position_size_multiplier(self):
        """Test getting position size multiplier"""
        multiplier = self.manager.get_position_size_multiplier()
        assert multiplier == self.config.initial_position_size

    def test_get_activation_status(self):
        """Test getting activation status"""
        status = self.manager.get_activation_status()
        
        assert "current_stage" in status
        assert "position_size_multiplier" in status
        assert "trade_count" in status
        assert "elapsed_time_seconds" in status
        assert "rollback_count" in status
        assert "slo_status" in status
        assert "can_activate" in status
        assert "can_rollback" in status

    def test_get_activation_history(self):
        """Test getting activation history"""
        # Create some activation events
        self.manager.activate_next_stage(ActivationTrigger.MANUAL, "Test activation")
        
        history = self.manager.get_activation_history()
        assert len(history) == 1
        assert history[0]["from_stage"] == ActivationStage.INITIAL.value
        assert history[0]["to_stage"] == ActivationStage.STAGED.value


class TestStagedActivationSystem:
    """Test staged activation system"""
    
    def setup_method(self):
        """Setup test method"""
        self.config = StagedActivationConfig(
            trade_count_threshold=5,  # Lower for testing
            time_threshold_hours=0.1,  # Lower for testing
            slo_check_interval_seconds=1,  # Faster for testing
            activation_cooldown_seconds=0  # No cooldown for testing
        )
        self.system = StagedActivationSystem(self.config)

    def test_system_initialization(self):
        """Test system initialization"""
        assert self.system.config == self.config
        assert self.system.activation_manager is not None
        assert self.system.running == False
        assert self.system.monitor_thread is None

    def test_start_stop_system(self):
        """Test starting and stopping the system"""
        # Start system
        self.system.start()
        assert self.system.running == True
        assert self.system.monitor_thread is not None
        
        # Stop system
        self.system.stop()
        assert self.system.running == False

    def test_record_trade(self):
        """Test recording a trade"""
        trade_data = {
            'pnl': 100.0,
            'profit_factor': 2.1,
            'drawdown': 0.02
        }
        
        self.system.record_trade(trade_data)
        assert self.system.activation_manager.trade_count == 1

    def test_record_performance_metric(self):
        """Test recording performance metric"""
        self.system.record_performance_metric("win_rate", 0.85)
        
        # Check that measurement was recorded
        assert "win_rate" in self.system.activation_manager.slo_monitor.measurements

    def test_get_position_size_multiplier(self):
        """Test getting position size multiplier"""
        multiplier = self.system.get_position_size_multiplier()
        assert multiplier == self.config.initial_position_size

    def test_get_activation_status(self):
        """Test getting activation status"""
        status = self.system.get_activation_status()
        
        assert "current_stage" in status
        assert "position_size_multiplier" in status
        assert "trade_count" in status
        assert "elapsed_time_seconds" in status

    def test_get_activation_history(self):
        """Test getting activation history"""
        history = self.system.get_activation_history()
        assert isinstance(history, list)

    def test_manual_activate(self):
        """Test manual activation"""
        success = self.system.manual_activate("Test manual activation")
        assert success
        assert self.system.activation_manager.current_stage == ActivationStage.STAGED

    def test_manual_rollback(self):
        """Test manual rollback"""
        # First activate
        self.system.manual_activate("Test activation")
        
        # Then rollback
        success = self.system.manual_rollback("Test rollback")
        assert success
        assert self.system.activation_manager.current_stage == ActivationStage.INITIAL

    def test_add_slo_threshold(self):
        """Test adding custom SLO threshold"""
        slo = SLOThreshold(
            name="custom_metric",
            metric="avg",
            threshold_value=0.9,
            comparison="gte",
            window_size=30,
            severity="warning"
        )
        
        self.system.add_slo_threshold(slo)
        assert "custom_metric" in self.system.activation_manager.slo_monitor.slo_thresholds

    def test_get_slo_status(self):
        """Test getting SLO status"""
        status = self.system.get_slo_status()
        assert isinstance(status, dict)


class TestGlobalFunctions:
    """Test global functions"""
    
    def setup_method(self):
        """Setup test method"""
        # Clean up any existing system
        stop_staged_activation()

    def test_create_staged_activation_system(self):
        """Test creating staged activation system"""
        config = StagedActivationConfig()
        system = create_staged_activation_system(config)
        
        assert system is not None
        assert system.config == config
        assert get_staged_activation_system() == system

    def test_start_staged_activation(self):
        """Test starting staged activation"""
        config = StagedActivationConfig()
        system = start_staged_activation(config)
        
        assert system is not None
        assert system.running == True
        assert get_staged_activation_system() == system

    def test_stop_staged_activation(self):
        """Test stopping staged activation"""
        config = StagedActivationConfig()
        start_staged_activation(config)
        
        stop_staged_activation()
        assert get_staged_activation_system() is None

    def test_get_position_size_multiplier(self):
        """Test getting position size multiplier"""
        # No system
        multiplier = get_position_size_multiplier()
        assert multiplier == 1.0  # Default
        
        # With system
        config = StagedActivationConfig()
        start_staged_activation(config)
        
        multiplier = get_position_size_multiplier()
        assert multiplier == config.initial_position_size

    def test_record_trade(self):
        """Test recording trade via global function"""
        config = StagedActivationConfig()
        start_staged_activation(config)
        
        trade_data = {'pnl': 100.0, 'profit_factor': 2.1}
        record_trade(trade_data)
        
        system = get_staged_activation_system()
        assert system.activation_manager.trade_count == 1

    def test_record_performance_metric(self):
        """Test recording performance metric via global function"""
        config = StagedActivationConfig()
        start_staged_activation(config)
        
        record_performance_metric("win_rate", 0.85)
        
        system = get_staged_activation_system()
        assert "win_rate" in system.activation_manager.slo_monitor.measurements

    def test_get_activation_status(self):
        """Test getting activation status via global function"""
        # No system
        status = get_activation_status()
        assert "error" in status
        
        # With system
        config = StagedActivationConfig()
        start_staged_activation(config)
        
        status = get_activation_status()
        assert "current_stage" in status
        assert "position_size_multiplier" in status

    def test_manual_activate(self):
        """Test manual activation via global function"""
        config = StagedActivationConfig()
        start_staged_activation(config)
        
        success = manual_activate("Test manual activation")
        assert success
        
        system = get_staged_activation_system()
        assert system.activation_manager.current_stage == ActivationStage.STAGED

    def test_manual_rollback(self):
        """Test manual rollback via global function"""
        config = StagedActivationConfig()
        start_staged_activation(config)
        
        # First activate
        manual_activate("Test activation")
        
        # Then rollback
        success = manual_rollback("Test rollback")
        assert success
        
        system = get_staged_activation_system()
        assert system.activation_manager.current_stage == ActivationStage.INITIAL


class TestStagedActivationIntegration:
    """Test staged activation integration scenarios"""
    
    def setup_method(self):
        """Setup test method"""
        self.config = StagedActivationConfig(
            trade_count_threshold=3,  # Lower for testing
            time_threshold_hours=0.1,  # Lower for testing
            slo_check_interval_seconds=1,  # Faster for testing
            activation_cooldown_seconds=0,  # No cooldown for testing
            rollback_threshold=1  # Lower for testing
        )
        self.system = StagedActivationSystem(self.config)

    def test_complete_activation_flow(self):
        """Test complete activation flow"""
        # Start system
        self.system.start()
        
        # Record trades to meet threshold
        for i in range(self.config.trade_count_threshold):
            self.system.record_trade({'pnl': 100.0})
            
        # Wait for activation check
        time.sleep(2)
        
        # Check that activation occurred
        status = self.system.get_activation_status()
        assert status['current_stage'] == ActivationStage.STAGED.value
        
        # Record more trades for full activation
        for i in range(self.config.trade_count_threshold):
            self.system.record_trade({'pnl': 100.0})
            
        # Wait for full activation check
        time.sleep(2)
        
        # Check that full activation occurred
        status = self.system.get_activation_status()
        assert status['current_stage'] == ActivationStage.FULL.value
        
        # Stop system
        self.system.stop()

    def test_rollback_flow(self):
        """Test rollback flow"""
        # Start system
        self.system.start()
        
        # Activate to full stage
        self.system.manual_activate("Test activation to staged")
        self.system.manual_activate("Test activation to full")
        
        # Record SLO violations to trigger rollback
        for i in range(50):
            self.system.record_performance_metric("win_rate", 0.75)  # Below threshold
            
        # Wait for rollback check
        time.sleep(2)
        
        # Check that rollback occurred
        status = self.system.get_activation_status()
        assert status['current_stage'] == ActivationStage.STAGED.value
        assert status['rollback_count'] == 1
        
        # Stop system
        self.system.stop()

    def test_database_operations(self):
        """Test database operations"""
        # Start system
        self.system.start()
        
        # Record some data
        self.system.record_trade({'pnl': 100.0})
        self.system.record_performance_metric("win_rate", 0.85)
        
        # Wait for database save
        time.sleep(2)
        
        # Check database was created
        assert self.system.db_path.exists()
        
        # Verify data was saved
        with sqlite3.connect(self.system.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM activation_status")
            status_count = cursor.fetchone()[0]
            assert status_count > 0
            
            cursor.execute("SELECT COUNT(*) FROM slo_measurements")
            measurements_count = cursor.fetchone()[0]
            assert measurements_count > 0
        
        # Stop system
        self.system.stop()

    def test_slo_threshold_evaluation(self):
        """Test SLO threshold evaluation"""
        # Add custom SLO
        slo = SLOThreshold(
            name="custom_metric",
            metric="avg",
            threshold_value=0.8,
            comparison="gte",
            window_size=10,
            severity="critical"
        )
        self.system.add_slo_threshold(slo)
        
        # Record measurements above threshold
        for i in range(10):
            self.system.record_performance_metric("custom_metric", 0.85)
            
        # Check SLO status
        slo_status = self.system.get_slo_status()
        assert "custom_metric" in slo_status
        assert slo_status["custom_metric"].status == SLOStatus.MET
        
        # Record measurements below threshold
        for i in range(10):
            self.system.record_performance_metric("custom_metric", 0.75)
            
        # Check SLO status
        slo_status = self.system.get_slo_status()
        assert "custom_metric" in slo_status
        assert slo_status["custom_metric"].status == SLOStatus.VIOLATED

    def test_activation_criteria_combinations(self):
        """Test different activation criteria combinations"""
        # Test trade count criteria
        for i in range(self.config.trade_count_threshold):
            self.system.record_trade({'pnl': 100.0})
            
        can_activate, reason, metadata = self.system.activation_manager.check_activation_criteria()
        assert can_activate
        assert metadata['trigger'] == ActivationTrigger.TRADE_COUNT
        
        # Reset trade count and test time criteria
        self.system.activation_manager.trade_count = 0
        self.system.activation_manager.start_time = time.time() - (self.config.time_threshold_hours * 3600 + 1)
        
        can_activate, reason, metadata = self.system.activation_manager.check_activation_criteria()
        assert can_activate
        assert metadata['trigger'] == ActivationTrigger.TIME_ELAPSED

    def test_performance_metrics_tracking(self):
        """Test performance metrics tracking"""
        # Record various metrics
        metrics = {
            'win_rate': 0.85,
            'profit_factor': 2.1,
            'max_drawdown': 0.03,
            'latency_p95': 150.0,
            'error_rate': 0.005
        }
        
        for metric_name, value in metrics.items():
            self.system.record_performance_metric(metric_name, value)
            
        # Check that metrics were recorded
        for metric_name in metrics:
            assert metric_name in self.system.activation_manager.slo_monitor.measurements
            assert len(self.system.activation_manager.slo_monitor.measurements[metric_name]) == 1
