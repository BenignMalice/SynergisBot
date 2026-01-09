"""
Comprehensive tests for shadow mode system

Tests shadow mode execution, comparison logic, metrics collection,
A/B testing capabilities, and performance validation.
"""

import pytest
import time
import json
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional

from infra.shadow_mode import (
    ShadowModeManager, ShadowModeController, ShadowModeConfig,
    ShadowModeStatus, ExecutionMode, ComparisonResult,
    ShadowTrade, ShadowMetrics, ShadowTrace,
    get_shadow_controller, create_shadow_mode, get_shadow_mode,
    start_shadow_mode, stop_shadow_mode, execute_shadow_trade
)

class TestShadowModeStatus:
    """Test shadow mode status enumeration"""
    
    def test_shadow_mode_statuses(self):
        """Test all shadow mode statuses"""
        statuses = [
            ShadowModeStatus.INACTIVE,
            ShadowModeStatus.ACTIVE,
            ShadowModeStatus.EXPIRED,
            ShadowModeStatus.DISABLED,
            ShadowModeStatus.ERROR
        ]
        
        for status in statuses:
            assert isinstance(status, ShadowModeStatus)
            assert status.value in ["inactive", "active", "expired", "disabled", "error"]

class TestExecutionMode:
    """Test execution mode enumeration"""
    
    def test_execution_modes(self):
        """Test all execution modes"""
        modes = [
            ExecutionMode.INTELLIGENT_EXIT,
            ExecutionMode.DTMS,
            ExecutionMode.SHADOW,
            ExecutionMode.COMPARISON
        ]
        
        for mode in modes:
            assert isinstance(mode, ExecutionMode)
            assert mode.value in ["intelligent_exit", "dtms", "shadow", "comparison"]

class TestComparisonResult:
    """Test comparison result enumeration"""
    
    def test_comparison_results(self):
        """Test all comparison results"""
        results = [
            ComparisonResult.DTMS_BETTER,
            ComparisonResult.INTELLIGENT_BETTER,
            ComparisonResult.EQUIVALENT,
            ComparisonResult.INCONCLUSIVE
        ]
        
        for result in results:
            assert isinstance(result, ComparisonResult)
            assert result.value in ["dtms_better", "intelligent_better", "equivalent", "inconclusive"]

class TestShadowModeConfig:
    """Test shadow mode configuration"""
    
    def test_config_creation(self):
        """Test configuration creation"""
        config = ShadowModeConfig(
            duration_days=14,
            traffic_split=0.5,
            enable_metrics=True,
            enable_traces=True,
            auto_expire=True,
            comparison_threshold=0.05
        )
        
        assert config.duration_days == 14
        assert config.traffic_split == 0.5
        assert config.enable_metrics is True
        assert config.enable_traces is True
        assert config.auto_expire is True
        assert config.comparison_threshold == 0.05
    
    def test_config_defaults(self):
        """Test configuration defaults"""
        config = ShadowModeConfig()
        
        assert config.duration_days == 14
        assert config.traffic_split == 0.5
        assert config.enable_metrics is True
        assert config.enable_traces is True
        assert config.auto_expire is True
        assert config.comparison_threshold == 0.05

class TestShadowTrade:
    """Test shadow trade data structure"""
    
    def test_shadow_trade_creation(self):
        """Test shadow trade creation"""
        trade = ShadowTrade(
            trade_id="test_trade_1",
            symbol="BTCUSDc",
            timestamp=time.time(),
            intelligent_exit_result={"action": "hold", "confidence": 0.75},
            dtms_result={"action": "partial_exit", "confidence": 0.82},
            execution_mode=ExecutionMode.SHADOW,
            comparison_result=ComparisonResult.DTMS_BETTER,
            performance_metrics={"latency_delta_ms": 5.0},
            trace_hash="abc123"
        )
        
        assert trade.trade_id == "test_trade_1"
        assert trade.symbol == "BTCUSDc"
        assert trade.timestamp > 0
        assert trade.intelligent_exit_result["action"] == "hold"
        assert trade.dtms_result["action"] == "partial_exit"
        assert trade.execution_mode == ExecutionMode.SHADOW
        assert trade.comparison_result == ComparisonResult.DTMS_BETTER
        assert trade.performance_metrics["latency_delta_ms"] == 5.0
        assert trade.trace_hash == "abc123"
    
    def test_shadow_trade_defaults(self):
        """Test shadow trade defaults"""
        trade = ShadowTrade(
            trade_id="test_trade_2",
            symbol="ETHUSDc",
            timestamp=time.time(),
            intelligent_exit_result={"action": "exit"},
            dtms_result={"action": "hold"},
            execution_mode=ExecutionMode.DTMS
        )
        
        assert trade.comparison_result is None
        assert trade.performance_metrics == {}
        assert trade.trace_hash is None

class TestShadowMetrics:
    """Test shadow metrics data structure"""
    
    def test_shadow_metrics_creation(self):
        """Test shadow metrics creation"""
        metrics = ShadowMetrics(
            total_trades=100,
            dtms_trades=50,
            intelligent_trades=30,
            shadow_trades=20,
            dtms_better_count=25,
            intelligent_better_count=15,
            equivalent_count=8,
            inconclusive_count=2,
            avg_dtms_latency_ms=45.0,
            avg_intelligent_latency_ms=50.0,
            dtms_success_rate=0.85,
            intelligent_success_rate=0.80,
            dtms_profit_factor=1.5,
            intelligent_profit_factor=1.3
        )
        
        assert metrics.total_trades == 100
        assert metrics.dtms_trades == 50
        assert metrics.intelligent_trades == 30
        assert metrics.shadow_trades == 20
        assert metrics.dtms_better_count == 25
        assert metrics.intelligent_better_count == 15
        assert metrics.equivalent_count == 8
        assert metrics.inconclusive_count == 2
        assert metrics.avg_dtms_latency_ms == 45.0
        assert metrics.avg_intelligent_latency_ms == 50.0
        assert metrics.dtms_success_rate == 0.85
        assert metrics.intelligent_success_rate == 0.80
        assert metrics.dtms_profit_factor == 1.5
        assert metrics.intelligent_profit_factor == 1.3
    
    def test_shadow_metrics_defaults(self):
        """Test shadow metrics defaults"""
        metrics = ShadowMetrics()
        
        assert metrics.total_trades == 0
        assert metrics.dtms_trades == 0
        assert metrics.intelligent_trades == 0
        assert metrics.shadow_trades == 0
        assert metrics.dtms_better_count == 0
        assert metrics.intelligent_better_count == 0
        assert metrics.equivalent_count == 0
        assert metrics.inconclusive_count == 0
        assert metrics.avg_dtms_latency_ms == 0.0
        assert metrics.avg_intelligent_latency_ms == 0.0
        assert metrics.dtms_success_rate == 0.0
        assert metrics.intelligent_success_rate == 0.0
        assert metrics.dtms_profit_factor == 0.0
        assert metrics.intelligent_profit_factor == 0.0

class TestShadowModeManager:
    """Test shadow mode manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = ShadowModeConfig(duration_days=1, traffic_split=0.5)
        self.manager = ShadowModeManager(self.config)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert self.manager.config == self.config
        assert self.manager.status == ShadowModeStatus.INACTIVE
        assert self.manager.start_time is None
        assert self.manager.end_time is None
        assert len(self.manager.trades) == 0
        assert len(self.manager.traces) == 0
        assert isinstance(self.manager.metrics, ShadowMetrics)
        assert hasattr(self.manager.executor, 'submit')  # Check if it's a thread pool executor
    
    def test_start_shadow_mode(self):
        """Test starting shadow mode"""
        success = self.manager.start_shadow_mode()
        
        assert success is True
        assert self.manager.status == ShadowModeStatus.ACTIVE
        assert self.manager.start_time is not None
        assert self.manager.end_time is not None
        assert self.manager.end_time > self.manager.start_time
    
    def test_start_shadow_mode_already_active(self):
        """Test starting shadow mode when already active"""
        self.manager.start_shadow_mode()
        success = self.manager.start_shadow_mode()
        
        assert success is False
    
    def test_stop_shadow_mode(self):
        """Test stopping shadow mode"""
        self.manager.start_shadow_mode()
        success = self.manager.stop_shadow_mode()
        
        assert success is True
        assert self.manager.status == ShadowModeStatus.INACTIVE
    
    def test_stop_shadow_mode_not_active(self):
        """Test stopping shadow mode when not active"""
        success = self.manager.stop_shadow_mode()
        
        assert success is False
    
    def test_check_expiration(self):
        """Test expiration checking"""
        # Test when not active
        expired = self.manager.check_expiration()
        assert expired is False
        
        # Test when active but not expired
        self.manager.start_shadow_mode()
        expired = self.manager.check_expiration()
        assert expired is False
        
        # Test when expired
        self.manager.end_time = time.time() - 1  # Set end time in the past
        expired = self.manager.check_expiration()
        assert expired is True
        assert self.manager.status == ShadowModeStatus.EXPIRED
    
    def test_execute_shadow_trade(self):
        """Test executing shadow trade"""
        self.manager.start_shadow_mode()
        
        trade_data = {
            "symbol": "BTCUSDc",
            "price": 50000.0,
            "volume": 0.01,
            "timestamp": time.time()
        }
        
        shadow_trade = self.manager.execute_shadow_trade("BTCUSDc", trade_data)
        
        assert shadow_trade is not None
        assert shadow_trade.symbol == "BTCUSDc"
        assert shadow_trade.trade_id is not None
        assert shadow_trade.timestamp > 0
        assert shadow_trade.intelligent_exit_result is not None
        assert shadow_trade.dtms_result is not None
        assert shadow_trade.execution_mode in [ExecutionMode.DTMS, ExecutionMode.INTELLIGENT_EXIT]
    
    def test_execute_shadow_trade_not_active(self):
        """Test executing shadow trade when not active"""
        trade_data = {"symbol": "BTCUSDc", "price": 50000.0}
        
        with pytest.raises(RuntimeError):
            self.manager.execute_shadow_trade("BTCUSDc", trade_data)
    
    def test_determine_execution_mode(self):
        """Test execution mode determination"""
        # Test multiple calls to see distribution
        modes = []
        for _ in range(100):
            mode = self.manager._determine_execution_mode()
            modes.append(mode)
        
        # Should have both DTMS and INTELLIGENT_EXIT modes
        assert ExecutionMode.DTMS in modes
        assert ExecutionMode.INTELLIGENT_EXIT in modes
    
    def test_compare_results(self):
        """Test result comparison"""
        # Test DTMS better
        intelligent_result = {"confidence": 0.7}
        dtms_result = {"confidence": 0.8}
        comparison = self.manager._compare_results(intelligent_result, dtms_result)
        assert comparison == ComparisonResult.DTMS_BETTER
        
        # Test Intelligent better
        intelligent_result = {"confidence": 0.8}
        dtms_result = {"confidence": 0.7}
        comparison = self.manager._compare_results(intelligent_result, dtms_result)
        assert comparison == ComparisonResult.INTELLIGENT_BETTER
        
        # Test equivalent
        intelligent_result = {"confidence": 0.75}
        dtms_result = {"confidence": 0.76}  # Within threshold
        comparison = self.manager._compare_results(intelligent_result, dtms_result)
        assert comparison == ComparisonResult.EQUIVALENT
    
    def test_calculate_performance_metrics(self):
        """Test performance metrics calculation"""
        intelligent_result = {
            "latency_ms": 50.0,
            "confidence": 0.75
        }
        dtms_result = {
            "latency_ms": 45.0,
            "confidence": 0.80
        }
        
        metrics = self.manager._calculate_performance_metrics(intelligent_result, dtms_result)
        
        assert metrics["latency_delta_ms"] == -5.0  # DTMS faster
        assert abs(metrics["confidence_delta"] - 0.05) < 0.001  # DTMS higher confidence (with tolerance)
        assert metrics["intelligent_latency_ms"] == 50.0
        assert metrics["dtms_latency_ms"] == 45.0
    
    def test_update_metrics(self):
        """Test metrics update"""
        shadow_trade = ShadowTrade(
            trade_id="test",
            symbol="BTCUSDc",
            timestamp=time.time(),
            intelligent_exit_result={"latency_ms": 50.0},
            dtms_result={"latency_ms": 45.0},
            execution_mode=ExecutionMode.DTMS,
            comparison_result=ComparisonResult.DTMS_BETTER,
            performance_metrics={"latency_delta_ms": -5.0}
        )
        
        self.manager._update_metrics(shadow_trade)
        
        assert self.manager.metrics.total_trades == 1
        assert self.manager.metrics.dtms_trades == 1
        assert self.manager.metrics.dtms_better_count == 1
    
    def test_get_shadow_metrics(self):
        """Test getting shadow metrics"""
        # Add some trades
        for i in range(5):
            shadow_trade = ShadowTrade(
                trade_id=f"test_{i}",
                symbol="BTCUSDc",
                timestamp=time.time(),
                intelligent_exit_result={"latency_ms": 50.0},
                dtms_result={"latency_ms": 45.0},
                execution_mode=ExecutionMode.DTMS,
                comparison_result=ComparisonResult.DTMS_BETTER,
                performance_metrics={"latency_delta_ms": -5.0}
            )
            self.manager._update_metrics(shadow_trade)
        
        metrics = self.manager.get_shadow_metrics()
        
        assert metrics.total_trades == 5
        assert metrics.dtms_trades == 5
        assert metrics.dtms_better_count == 5
    
    def test_get_shadow_trades(self):
        """Test getting shadow trades"""
        # Add some trades
        for i in range(3):
            shadow_trade = ShadowTrade(
                trade_id=f"test_{i}",
                symbol="BTCUSDc",
                timestamp=time.time(),
                intelligent_exit_result={"action": "hold"},
                dtms_result={"action": "exit"},
                execution_mode=ExecutionMode.DTMS
            )
            self.manager.trades.append(shadow_trade)
        
        trades = self.manager.get_shadow_trades()
        assert len(trades) == 3
        
        trades_limited = self.manager.get_shadow_trades(limit=2)
        assert len(trades_limited) == 2
    
    def test_generate_comparison_report(self):
        """Test generating comparison report"""
        # Add some trades
        for i in range(3):
            shadow_trade = ShadowTrade(
                trade_id=f"test_{i}",
                symbol="BTCUSDc",
                timestamp=time.time(),
                intelligent_exit_result={"action": "hold", "latency_ms": 50.0},
                dtms_result={"action": "exit", "latency_ms": 45.0},
                execution_mode=ExecutionMode.DTMS,
                comparison_result=ComparisonResult.DTMS_BETTER,
                performance_metrics={"latency_delta_ms": -5.0}
            )
            self.manager.trades.append(shadow_trade)
            self.manager._update_metrics(shadow_trade)
        
        report = self.manager.generate_comparison_report()
        
        assert "summary" in report
        assert "performance" in report
        assert "comparison" in report
        assert "recommendation" in report
        assert report["summary"]["total_trades"] == 3
    
    def test_generate_recommendation(self):
        """Test recommendation generation"""
        # Test with no trades
        recommendation = self.manager._generate_recommendation()
        assert "Insufficient data" in recommendation
        
        # Test with DTMS better
        for i in range(10):
            shadow_trade = ShadowTrade(
                trade_id=f"test_{i}",
                symbol="BTCUSDc",
                timestamp=time.time(),
                intelligent_exit_result={"confidence": 0.7},
                dtms_result={"confidence": 0.8},
                execution_mode=ExecutionMode.DTMS,
                comparison_result=ComparisonResult.DTMS_BETTER
            )
            self.manager.trades.append(shadow_trade)
            self.manager._update_metrics(shadow_trade)
        
        recommendation = self.manager._generate_recommendation()
        assert "DTMS" in recommendation
    
    def test_callback_setting(self):
        """Test callback function setting"""
        on_trade_executed = Mock()
        on_comparison_completed = Mock()
        on_metrics_updated = Mock()
        on_status_changed = Mock()
        
        self.manager.set_callbacks(
            on_trade_executed=on_trade_executed,
            on_comparison_completed=on_comparison_completed,
            on_metrics_updated=on_metrics_updated,
            on_status_changed=on_status_changed
        )
        
        assert self.manager.on_trade_executed == on_trade_executed
        assert self.manager.on_comparison_completed == on_comparison_completed
        assert self.manager.on_metrics_updated == on_metrics_updated
        assert self.manager.on_status_changed == on_status_changed

class TestShadowModeController:
    """Test shadow mode controller"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.controller = ShadowModeController()
    
    def test_controller_initialization(self):
        """Test controller initialization"""
        assert len(self.controller.managers) == 0
        assert hasattr(self.controller, 'lock')
    
    def test_create_shadow_mode(self):
        """Test creating shadow mode"""
        config = ShadowModeConfig(duration_days=7)
        manager = self.controller.create_shadow_mode("test_mode", config)
        
        assert isinstance(manager, ShadowModeManager)
        assert "test_mode" in self.controller.managers
        assert self.controller.managers["test_mode"] == manager
    
    def test_create_shadow_mode_duplicate(self):
        """Test creating duplicate shadow mode"""
        config = ShadowModeConfig()
        self.controller.create_shadow_mode("test_mode", config)
        
        with pytest.raises(ValueError):
            self.controller.create_shadow_mode("test_mode", config)
    
    def test_get_shadow_mode(self):
        """Test getting shadow mode"""
        config = ShadowModeConfig()
        manager = self.controller.create_shadow_mode("test_mode", config)
        
        retrieved_manager = self.controller.get_shadow_mode("test_mode")
        assert retrieved_manager == manager
        
        # Test non-existent mode
        non_existent = self.controller.get_shadow_mode("non_existent")
        assert non_existent is None
    
    def test_remove_shadow_mode(self):
        """Test removing shadow mode"""
        config = ShadowModeConfig()
        manager = self.controller.create_shadow_mode("test_mode", config)
        manager.start_shadow_mode()
        
        success = self.controller.remove_shadow_mode("test_mode")
        assert success is True
        assert "test_mode" not in self.controller.managers
        assert manager.status == ShadowModeStatus.INACTIVE
        
        # Test removing non-existent mode
        success = self.controller.remove_shadow_mode("non_existent")
        assert success is False
    
    def test_list_shadow_modes(self):
        """Test listing shadow modes"""
        config = ShadowModeConfig()
        self.controller.create_shadow_mode("mode1", config)
        self.controller.create_shadow_mode("mode2", config)
        
        modes = self.controller.list_shadow_modes()
        assert len(modes) == 2
        assert "mode1" in modes
        assert "mode2" in modes
    
    def test_get_all_metrics(self):
        """Test getting all metrics"""
        config = ShadowModeConfig()
        manager1 = self.controller.create_shadow_mode("mode1", config)
        manager2 = self.controller.create_shadow_mode("mode2", config)
        
        all_metrics = self.controller.get_all_metrics()
        assert len(all_metrics) == 2
        assert "mode1" in all_metrics
        assert "mode2" in all_metrics
        assert isinstance(all_metrics["mode1"], ShadowMetrics)
        assert isinstance(all_metrics["mode2"], ShadowMetrics)

class TestGlobalFunctions:
    """Test global shadow mode functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global controller
        import infra.shadow_mode
        infra.shadow_mode._shadow_controller = None
    
    def test_get_shadow_controller(self):
        """Test global shadow controller access"""
        controller1 = get_shadow_controller()
        controller2 = get_shadow_controller()
        
        # Should return same instance
        assert controller1 is controller2
        assert isinstance(controller1, ShadowModeController)
    
    def test_create_shadow_mode_global(self):
        """Test global shadow mode creation"""
        config = ShadowModeConfig(duration_days=7)
        manager = create_shadow_mode("test_mode", config)
        
        assert isinstance(manager, ShadowModeManager)
        assert get_shadow_mode("test_mode") == manager
    
    def test_get_shadow_mode_global(self):
        """Test global shadow mode retrieval"""
        config = ShadowModeConfig()
        manager = create_shadow_mode("test_mode", config)
        
        retrieved_manager = get_shadow_mode("test_mode")
        assert retrieved_manager == manager
        
        # Test non-existent mode
        non_existent = get_shadow_mode("non_existent")
        assert non_existent is None
    
    def test_start_stop_shadow_mode_global(self):
        """Test global start/stop shadow mode"""
        config = ShadowModeConfig()
        create_shadow_mode("test_mode", config)
        
        # Start shadow mode
        success = start_shadow_mode("test_mode")
        assert success is True
        
        manager = get_shadow_mode("test_mode")
        assert manager.status == ShadowModeStatus.ACTIVE
        
        # Stop shadow mode
        success = stop_shadow_mode("test_mode")
        assert success is True
        
        assert manager.status == ShadowModeStatus.INACTIVE
    
    def test_execute_shadow_trade_global(self):
        """Test global shadow trade execution"""
        config = ShadowModeConfig()
        create_shadow_mode("test_mode", config)
        start_shadow_mode("test_mode")
        
        trade_data = {
            "symbol": "BTCUSDc",
            "price": 50000.0,
            "volume": 0.01
        }
        
        shadow_trade = execute_shadow_trade("test_mode", "BTCUSDc", trade_data)
        
        assert shadow_trade is not None
        assert shadow_trade.symbol == "BTCUSDc"
        assert shadow_trade.trade_id is not None

class TestShadowModeIntegration:
    """Integration tests for shadow mode system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global controller
        import infra.shadow_mode
        infra.shadow_mode._shadow_controller = None
    
    def test_comprehensive_shadow_mode_workflow(self):
        """Test comprehensive shadow mode workflow"""
        # Create shadow mode
        config = ShadowModeConfig(
            duration_days=1,
            traffic_split=0.5,
            enable_metrics=True,
            enable_traces=True
        )
        
        manager = create_shadow_mode("dtms_validation", config)
        
        # Set up callbacks
        trade_callback = Mock()
        metrics_callback = Mock()
        status_callback = Mock()
        
        manager.set_callbacks(
            on_trade_executed=trade_callback,
            on_metrics_updated=metrics_callback,
            on_status_changed=status_callback
        )
        
        # Start shadow mode
        success = start_shadow_mode("dtms_validation")
        assert success is True
        assert manager.status == ShadowModeStatus.ACTIVE
        
        # Execute multiple trades
        for i in range(10):
            trade_data = {
                "symbol": "BTCUSDc",
                "price": 50000.0 + i * 100,
                "volume": 0.01,
                "timestamp": time.time()
            }
            
            shadow_trade = execute_shadow_trade("dtms_validation", "BTCUSDc", trade_data)
            assert shadow_trade is not None
        
        # Check callbacks were called
        assert trade_callback.call_count == 10
        assert metrics_callback.call_count >= 10
        assert status_callback.call_count >= 1
        
        # Get metrics
        metrics = manager.get_shadow_metrics()
        assert metrics.total_trades == 10
        assert metrics.dtms_trades + metrics.intelligent_trades == 10
        
        # Generate comparison report
        report = manager.generate_comparison_report()
        assert "summary" in report
        assert "performance" in report
        assert "comparison" in report
        assert "recommendation" in report
        assert report["summary"]["total_trades"] == 10
        
        # Stop shadow mode
        success = stop_shadow_mode("dtms_validation")
        assert success is True
        assert manager.status == ShadowModeStatus.INACTIVE
    
    def test_multiple_shadow_modes(self):
        """Test multiple shadow modes running simultaneously"""
        # Create multiple shadow modes
        config1 = ShadowModeConfig(duration_days=1, traffic_split=0.3)
        config2 = ShadowModeConfig(duration_days=2, traffic_split=0.7)
        
        manager1 = create_shadow_mode("mode1", config1)
        manager2 = create_shadow_mode("mode2", config2)
        
        # Start both modes
        start_shadow_mode("mode1")
        start_shadow_mode("mode2")
        
        assert manager1.status == ShadowModeStatus.ACTIVE
        assert manager2.status == ShadowModeStatus.ACTIVE
        
        # Execute trades in both modes
        for i in range(5):
            trade_data = {"symbol": "BTCUSDc", "price": 50000.0 + i * 100}
            execute_shadow_trade("mode1", "BTCUSDc", trade_data)
            execute_shadow_trade("mode2", "ETHUSDc", trade_data)
        
        # Check both modes have trades
        assert manager1.metrics.total_trades == 5
        assert manager2.metrics.total_trades == 5
        
        # Get all metrics
        controller = get_shadow_controller()
        all_metrics = controller.get_all_metrics()
        
        assert len(all_metrics) == 2
        assert "mode1" in all_metrics
        assert "mode2" in all_metrics
        assert all_metrics["mode1"].total_trades == 5
        assert all_metrics["mode2"].total_trades == 5
    
    def test_shadow_mode_expiration(self):
        """Test shadow mode expiration"""
        # Create shadow mode with short duration
        config = ShadowModeConfig(duration_days=0.001)  # Very short duration
        manager = create_shadow_mode("short_mode", config)
        
        # Start shadow mode
        start_shadow_mode("short_mode")
        assert manager.status == ShadowModeStatus.ACTIVE
        
        # Manually set end time to past to trigger expiration
        manager.end_time = time.time() - 1
        
        # Check expiration
        expired = manager.check_expiration()
        assert expired is True
        assert manager.status == ShadowModeStatus.EXPIRED
    
    def test_shadow_mode_error_handling(self):
        """Test shadow mode error handling"""
        config = ShadowModeConfig()
        manager = create_shadow_mode("error_mode", config)
        
        # Test executing trade without starting
        with pytest.raises(RuntimeError):
            manager.execute_shadow_trade("BTCUSDc", {"price": 50000.0})
        
        # Test starting already active mode
        manager.start_shadow_mode()
        success = manager.start_shadow_mode()
        assert success is False
        
        # Test stopping already stopped mode
        manager.stop_shadow_mode()
        success = manager.stop_shadow_mode()
        assert success is False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])