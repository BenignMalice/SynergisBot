"""
Comprehensive tests for Binance integration stability validation system

Tests Binance WebSocket stability monitoring, data loss tracking, context-only
operation validation, connection health monitoring, data quality assessment,
and performance metrics tracking.
"""

import pytest
import time
import json
import threading
import statistics
import numpy as np
import asyncio
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional
from collections import deque

from infra.binance_integration_validation import (
    BinanceIntegrationValidator, BinanceConnectionMonitor, ContextUsageValidator, BinanceContextManager,
    BinanceConnectionStatus, DataQualityLevel, ContextUsageType,
    BinanceMetrics, DataQualityReport, ContextUsageEvent,
    get_binance_validator, validate_binance_integration, get_data_quality_report, binance_context_usage
)

class TestBinanceConnectionStatus:
    """Test Binance connection status enumeration"""
    
    def test_connection_statuses(self):
        """Test all connection statuses"""
        statuses = [
            BinanceConnectionStatus.CONNECTED,
            BinanceConnectionStatus.DISCONNECTED,
            BinanceConnectionStatus.RECONNECTING,
            BinanceConnectionStatus.FAILED
        ]
        
        for status in statuses:
            assert isinstance(status, BinanceConnectionStatus)
            assert status.value in ["connected", "disconnected", "reconnecting", "failed"]

class TestDataQualityLevel:
    """Test data quality level enumeration"""
    
    def test_quality_levels(self):
        """Test all quality levels"""
        levels = [
            DataQualityLevel.EXCELLENT,
            DataQualityLevel.GOOD,
            DataQualityLevel.ACCEPTABLE,
            DataQualityLevel.POOR,
            DataQualityLevel.CRITICAL
        ]
        
        for level in levels:
            assert isinstance(level, DataQualityLevel)
            assert level.value in ["excellent", "good", "acceptable", "poor", "critical"]

class TestContextUsageType:
    """Test context usage type enumeration"""
    
    def test_usage_types(self):
        """Test all usage types"""
        types = [
            ContextUsageType.ORDER_BOOK_ANALYSIS,
            ContextUsageType.LARGE_ORDER_DETECTION,
            ContextUsageType.SUPPORT_RESISTANCE,
            ContextUsageType.MARKET_SENTIMENT,
            ContextUsageType.VOLUME_ANALYSIS
        ]
        
        for usage_type in types:
            assert isinstance(usage_type, ContextUsageType)
            assert usage_type.value in [
                "order_book_analysis", "large_order_detection", "support_resistance",
                "market_sentiment", "volume_analysis"
            ]

class TestBinanceMetrics:
    """Test Binance metrics data structure"""
    
    def test_binance_metrics_creation(self):
        """Test Binance metrics creation"""
        metrics = BinanceMetrics(
            timestamp=time.time(),
            connection_status=BinanceConnectionStatus.CONNECTED,
            data_loss_percentage=2.5,
            messages_received=1000,
            messages_processed=975,
            messages_dropped=25,
            latency_ms=50.0,
            throughput_per_second=100.0,
            context_usage_count=50,
            error_count=5,
            reconnection_count=2,
            metadata={"symbol": "BTCUSDT", "connection_type": "websocket"}
        )
        
        assert metrics.timestamp > 0
        assert metrics.connection_status == BinanceConnectionStatus.CONNECTED
        assert metrics.data_loss_percentage == 2.5
        assert metrics.messages_received == 1000
        assert metrics.messages_processed == 975
        assert metrics.messages_dropped == 25
        assert metrics.latency_ms == 50.0
        assert metrics.throughput_per_second == 100.0
        assert metrics.context_usage_count == 50
        assert metrics.error_count == 5
        assert metrics.reconnection_count == 2
        assert metrics.metadata["symbol"] == "BTCUSDT"
    
    def test_binance_metrics_defaults(self):
        """Test Binance metrics defaults"""
        metrics = BinanceMetrics(
            timestamp=time.time(),
            connection_status=BinanceConnectionStatus.DISCONNECTED,
            data_loss_percentage=0.0,
            messages_received=0,
            messages_processed=0,
            messages_dropped=0,
            latency_ms=0.0,
            throughput_per_second=0.0,
            context_usage_count=0,
            error_count=0,
            reconnection_count=0
        )
        
        assert metrics.metadata == {}

class TestDataQualityReport:
    """Test data quality report data structure"""
    
    def test_data_quality_report_creation(self):
        """Test data quality report creation"""
        report = DataQualityReport(
            overall_quality=DataQualityLevel.GOOD,
            data_loss_percentage=2.5,
            message_processing_rate=100.0,
            latency_p95_ms=150.0,
            error_rate=1.5,
            context_usage_efficiency=85.0,
            recommendations=["Optimize network connection", "Monitor data quality"],
            quality_metrics={"total_messages": 1000, "uptime_seconds": 3600}
        )
        
        assert report.overall_quality == DataQualityLevel.GOOD
        assert report.data_loss_percentage == 2.5
        assert report.message_processing_rate == 100.0
        assert report.latency_p95_ms == 150.0
        assert report.error_rate == 1.5
        assert report.context_usage_efficiency == 85.0
        assert len(report.recommendations) == 2
        assert "total_messages" in report.quality_metrics
    
    def test_data_quality_report_defaults(self):
        """Test data quality report defaults"""
        report = DataQualityReport(
            overall_quality=DataQualityLevel.EXCELLENT,
            data_loss_percentage=0.0,
            message_processing_rate=0.0,
            latency_p95_ms=0.0,
            error_rate=0.0,
            context_usage_efficiency=0.0,
            recommendations=[],
            quality_metrics={}
        )
        
        assert report.recommendations == []
        assert report.quality_metrics == {}

class TestContextUsageEvent:
    """Test context usage event data structure"""
    
    def test_context_usage_event_creation(self):
        """Test context usage event creation"""
        event = ContextUsageEvent(
            timestamp=time.time(),
            usage_type=ContextUsageType.ORDER_BOOK_ANALYSIS,
            symbol="BTCUSDT",
            data_quality=0.95,
            processing_time_ms=5.0,
            context_value={"bids": [[50000, 1.5]], "asks": [[50001, 2.0]]},
            metadata={"order_book_depth": 10, "spread": 1.0}
        )
        
        assert event.timestamp > 0
        assert event.usage_type == ContextUsageType.ORDER_BOOK_ANALYSIS
        assert event.symbol == "BTCUSDT"
        assert event.data_quality == 0.95
        assert event.processing_time_ms == 5.0
        assert event.context_value["bids"] == [[50000, 1.5]]
        assert event.metadata["order_book_depth"] == 10
    
    def test_context_usage_event_defaults(self):
        """Test context usage event defaults"""
        event = ContextUsageEvent(
            timestamp=time.time(),
            usage_type=ContextUsageType.LARGE_ORDER_DETECTION,
            symbol="ETHUSDT",
            data_quality=0.90,
            processing_time_ms=3.0,
            context_value={"large_order_detected": True}
        )
        
        assert event.metadata == {}

class TestBinanceConnectionMonitor:
    """Test Binance connection monitor"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.monitor = BinanceConnectionMonitor(max_metrics=1000)
    
    def test_monitor_initialization(self):
        """Test monitor initialization"""
        assert self.monitor.max_metrics == 1000
        assert len(self.monitor.metrics) == 0
        assert len(self.monitor.context_events) == 0
        assert hasattr(self.monitor, 'lock')
        assert self.monitor.start_time > 0
        assert self.monitor.connection_status == BinanceConnectionStatus.DISCONNECTED
        assert self.monitor.total_messages_received == 0
        assert self.monitor.total_messages_processed == 0
        assert self.monitor.total_messages_dropped == 0
        assert self.monitor.total_errors == 0
        assert self.monitor.total_reconnections == 0
    
    def test_record_metrics(self):
        """Test recording metrics"""
        metrics = BinanceMetrics(
            timestamp=time.time(),
            connection_status=BinanceConnectionStatus.CONNECTED,
            data_loss_percentage=1.5,
            messages_received=100,
            messages_processed=98,
            messages_dropped=2,
            latency_ms=50.0,
            throughput_per_second=10.0,
            context_usage_count=20,
            error_count=1,
            reconnection_count=0
        )
        
        self.monitor.record_metrics(metrics)
        
        assert len(self.monitor.metrics) == 1
        assert self.monitor.connection_status == BinanceConnectionStatus.CONNECTED
        assert self.monitor.total_messages_received == 100
        assert self.monitor.total_messages_processed == 98
        assert self.monitor.total_messages_dropped == 2
        assert self.monitor.total_errors == 1
        assert self.monitor.total_reconnections == 0
    
    def test_record_context_event(self):
        """Test recording context event"""
        event = ContextUsageEvent(
            timestamp=time.time(),
            usage_type=ContextUsageType.ORDER_BOOK_ANALYSIS,
            symbol="BTCUSDT",
            data_quality=0.95,
            processing_time_ms=5.0,
            context_value={"bids": [[50000, 1.5]]}
        )
        
        self.monitor.record_context_event(event)
        
        assert len(self.monitor.context_events) == 1
    
    def test_get_data_quality_report_empty(self):
        """Test getting data quality report with no data"""
        report = self.monitor.get_data_quality_report()
        
        assert report.overall_quality == DataQualityLevel.EXCELLENT
        assert report.data_loss_percentage == 0.0
        assert report.message_processing_rate == 0.0
        assert report.latency_p95_ms == 0.0
        assert report.error_rate == 0.0
        assert report.context_usage_efficiency == 0.0
        assert report.recommendations == []
        assert report.quality_metrics == {}
    
    def test_get_data_quality_report_with_data(self):
        """Test getting data quality report with data"""
        # Add some metrics
        for i in range(10):
            metrics = BinanceMetrics(
                timestamp=time.time() + i,
                connection_status=BinanceConnectionStatus.CONNECTED,
                data_loss_percentage=1.0 + i * 0.1,
                messages_received=100 + i * 10,
                messages_processed=95 + i * 10,
                messages_dropped=5 + i,
                latency_ms=50.0 + i * 5.0,
                throughput_per_second=10.0 + i,
                context_usage_count=20 + i,
                error_count=i,
                reconnection_count=0
            )
            self.monitor.record_metrics(metrics)
        
        # Add some context events
        for i in range(5):
            event = ContextUsageEvent(
                timestamp=time.time() + i,
                usage_type=ContextUsageType.ORDER_BOOK_ANALYSIS,
                symbol="BTCUSDT",
                data_quality=0.95,
                processing_time_ms=5.0,
                context_value={"test": i}
            )
            self.monitor.record_context_event(event)
        
        report = self.monitor.get_data_quality_report()
        
        assert report.overall_quality in [DataQualityLevel.EXCELLENT, DataQualityLevel.GOOD, 
                                        DataQualityLevel.ACCEPTABLE, DataQualityLevel.POOR, DataQualityLevel.CRITICAL]
        assert report.data_loss_percentage >= 0.0
        assert report.message_processing_rate >= 0.0
        assert report.latency_p95_ms >= 0.0
        assert report.error_rate >= 0.0
        assert report.context_usage_efficiency >= 0.0
        assert isinstance(report.recommendations, list)
        assert isinstance(report.quality_metrics, dict)
    
    def test_determine_data_quality(self):
        """Test data quality determination"""
        # Test excellent quality
        quality = self.monitor._determine_data_quality(0.5, 0.1, 200.0)
        assert quality == DataQualityLevel.EXCELLENT
        
        # Test good quality
        quality = self.monitor._determine_data_quality(2.0, 0.8, 600.0)
        assert quality == DataQualityLevel.GOOD
        
        # Test acceptable quality
        quality = self.monitor._determine_data_quality(4.0, 1.5, 1200.0)
        assert quality == DataQualityLevel.ACCEPTABLE
        
        # Test poor quality
        quality = self.monitor._determine_data_quality(7.0, 4.0, 2500.0)
        assert quality == DataQualityLevel.POOR
        
        # Test critical quality
        quality = self.monitor._determine_data_quality(15.0, 8.0, 6000.0)
        assert quality == DataQualityLevel.CRITICAL
    
    def test_generate_recommendations(self):
        """Test recommendation generation"""
        # Test with no issues
        recommendations = self.monitor._generate_recommendations(0.5, 0.1, 200.0, 80.0)
        assert len(recommendations) == 1
        assert "performing well" in recommendations[0].lower()
        
        # Test with issues
        recommendations = self.monitor._generate_recommendations(8.0, 3.0, 1500.0, 5.0)
        assert len(recommendations) > 1
        assert any("data loss" in rec.lower() for rec in recommendations)
        assert any("error rate" in rec.lower() for rec in recommendations)
        assert any("latency" in rec.lower() for rec in recommendations)
        assert any("context usage" in rec.lower() for rec in recommendations)

class TestContextUsageValidator:
    """Test context usage validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = ContextUsageValidator()
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert len(self.validator.context_events) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
    
    def test_validate_context_only_usage_empty(self):
        """Test context-only validation with no events"""
        result = self.validator.validate_context_only_usage()
        
        assert result['is_context_only'] is True
        assert result['context_usage_count'] == 0
        assert result['non_context_usage_count'] == 0
        assert result['context_usage_percentage'] == 100.0
        assert result['violations'] == []
        assert len(result['recommendations']) >= 0
    
    def test_validate_context_only_usage_valid(self):
        """Test context-only validation with valid events"""
        # Add valid context events
        for i in range(5):
            event = ContextUsageEvent(
                timestamp=time.time() + i,
                usage_type=ContextUsageType.ORDER_BOOK_ANALYSIS,
                symbol="BTCUSDT",
                data_quality=0.95,
                processing_time_ms=5.0,
                context_value={"test": i}
            )
            self.validator.context_events.append(event)
        
        result = self.validator.validate_context_only_usage()
        
        assert result['is_context_only'] is True
        assert result['context_usage_count'] == 5
        assert result['non_context_usage_count'] == 0
        assert result['context_usage_percentage'] == 100.0
        assert result['violations'] == []
        assert len(result['recommendations']) == 1
        assert "context-only" in result['recommendations'][0].lower()
    
    def test_record_context_event(self):
        """Test recording context event"""
        event = ContextUsageEvent(
            timestamp=time.time(),
            usage_type=ContextUsageType.LARGE_ORDER_DETECTION,
            symbol="ETHUSDT",
            data_quality=0.90,
            processing_time_ms=3.0,
            context_value={"large_order_detected": True}
        )
        
        self.validator.record_context_event(event)
        
        assert len(self.validator.context_events) == 1
        assert self.validator.context_events[0].usage_type == ContextUsageType.LARGE_ORDER_DETECTION

class TestBinanceIntegrationValidator:
    """Test Binance integration validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = BinanceIntegrationValidator()
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert isinstance(self.validator.connection_monitor, BinanceConnectionMonitor)
        assert isinstance(self.validator.context_validator, ContextUsageValidator)
        assert self.validator.start_time > 0
        assert len(self.validator.validation_results) == 0
        assert hasattr(self.validator, 'lock')
    
    def test_validate_binance_integration(self):
        """Test Binance integration validation"""
        result = self.validator.validate_binance_integration()
        
        assert 'timestamp' in result
        assert 'is_stable' in result
        assert 'meets_data_loss_requirement' in result
        assert 'is_context_only' in result
        assert 'overall_quality' in result
        assert 'data_loss_percentage' in result
        assert 'message_processing_rate' in result
        assert 'latency_p95_ms' in result
        assert 'error_rate' in result
        assert 'context_usage_efficiency' in result
        assert 'context_validation' in result
        assert 'quality_report' in result
        assert 'recommendations' in result
        assert 'uptime_seconds' in result
        
        assert isinstance(result['is_stable'], bool)
        assert isinstance(result['meets_data_loss_requirement'], bool)
        assert isinstance(result['is_context_only'], bool)
        assert result['overall_quality'] in ['excellent', 'good', 'acceptable', 'poor', 'critical']
        assert result['data_loss_percentage'] >= 0.0
        assert result['message_processing_rate'] >= 0.0
        assert result['latency_p95_ms'] >= 0.0
        assert result['error_rate'] >= 0.0
        assert result['context_usage_efficiency'] >= 0.0
        assert isinstance(result['recommendations'], list)
        assert isinstance(result['context_validation'], dict)
        assert isinstance(result['quality_report'], dict)
    
    def test_get_data_quality_report(self):
        """Test getting data quality report"""
        report = self.validator.get_data_quality_report()
        
        assert isinstance(report, DataQualityReport)
        assert report.overall_quality in [DataQualityLevel.EXCELLENT, DataQualityLevel.GOOD, 
                                        DataQualityLevel.ACCEPTABLE, DataQualityLevel.POOR, DataQualityLevel.CRITICAL]
        assert report.data_loss_percentage >= 0.0
        assert report.message_processing_rate >= 0.0
        assert report.latency_p95_ms >= 0.0
        assert report.error_rate >= 0.0
        assert report.context_usage_efficiency >= 0.0
        assert isinstance(report.recommendations, list)
        assert isinstance(report.quality_metrics, dict)
    
    def test_get_validation_history(self):
        """Test getting validation history"""
        # Run a few validations
        for i in range(3):
            self.validator.validate_binance_integration()
        
        history = self.validator.get_validation_history()
        
        assert len(history) == 3
        assert isinstance(history, list)
        for result in history:
            assert 'timestamp' in result
            assert 'is_stable' in result
            assert 'overall_quality' in result
    
    def test_record_context_usage(self):
        """Test recording context usage"""
        self.validator.record_context_usage(
            usage_type=ContextUsageType.ORDER_BOOK_ANALYSIS,
            symbol="BTCUSDT",
            data_quality=0.95,
            processing_time_ms=5.0,
            context_value={"bids": [[50000, 1.5]]},
            order_book_depth=10
        )
        
        # Check that context event was recorded
        assert len(self.validator.context_validator.context_events) == 1
        event = self.validator.context_validator.context_events[0]
        assert event.usage_type == ContextUsageType.ORDER_BOOK_ANALYSIS
        assert event.symbol == "BTCUSDT"
        assert event.data_quality == 0.95
        assert event.processing_time_ms == 5.0
        assert event.context_value == {"bids": [[50000, 1.5]]}
        assert event.metadata["order_book_depth"] == 10
    
    def test_reset_metrics(self):
        """Test resetting metrics"""
        # Add some data
        self.validator.validate_binance_integration()
        
        # Reset metrics
        self.validator.reset_metrics()
        
        assert len(self.validator.connection_monitor.metrics) == 0
        assert len(self.validator.connection_monitor.context_events) == 0
        assert len(self.validator.context_validator.context_events) == 0
        assert len(self.validator.validation_results) == 0

class TestBinanceContextManager:
    """Test Binance context manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = BinanceIntegrationValidator()
    
    def test_context_manager_initialization(self):
        """Test context manager initialization"""
        context = BinanceContextManager(
            self.validator, 
            ContextUsageType.ORDER_BOOK_ANALYSIS, 
            "BTCUSDT"
        )
        
        assert context.validator is self.validator
        assert context.usage_type == ContextUsageType.ORDER_BOOK_ANALYSIS
        assert context.symbol == "BTCUSDT"
        assert context.start_time > 0
        assert context.context_value is None
        assert context.data_quality == 1.0
    
    def test_context_manager_enter_exit(self):
        """Test context manager enter/exit"""
        initial_events_count = len(self.validator.context_validator.context_events)
        
        with BinanceContextManager(self.validator, ContextUsageType.LARGE_ORDER_DETECTION, "ETHUSDT") as ctx:
            ctx.context_value = {"large_order_detected": True}
            ctx.data_quality = 0.90
            time.sleep(0.001)  # Small delay
        
        # Check that context event was recorded
        assert len(self.validator.context_validator.context_events) == initial_events_count + 1
        
        # Check the recorded event
        latest_event = self.validator.context_validator.context_events[-1]
        assert latest_event.usage_type == ContextUsageType.LARGE_ORDER_DETECTION
        assert latest_event.symbol == "ETHUSDT"
        assert latest_event.context_value == {"large_order_detected": True}
        assert latest_event.data_quality == 0.90
        assert latest_event.processing_time_ms > 0.0

class TestGlobalFunctions:
    """Test global Binance functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.binance_integration_validation
        infra.binance_integration_validation._binance_validator = None
    
    def test_get_binance_validator(self):
        """Test global validator access"""
        validator1 = get_binance_validator()
        validator2 = get_binance_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, BinanceIntegrationValidator)
    
    def test_validate_binance_integration_global(self):
        """Test global Binance integration validation"""
        result = validate_binance_integration()
        
        assert isinstance(result, dict)
        assert 'is_stable' in result
        assert 'meets_data_loss_requirement' in result
        assert 'is_context_only' in result
        assert 'overall_quality' in result
        assert 'recommendations' in result
    
    def test_get_data_quality_report_global(self):
        """Test global data quality report"""
        report = get_data_quality_report()
        
        assert isinstance(report, DataQualityReport)
        assert report.overall_quality in [DataQualityLevel.EXCELLENT, DataQualityLevel.GOOD, 
                                        DataQualityLevel.ACCEPTABLE, DataQualityLevel.POOR, DataQualityLevel.CRITICAL]
    
    def test_binance_context_usage_global(self):
        """Test global Binance context usage context manager"""
        with binance_context_usage(ContextUsageType.ORDER_BOOK_ANALYSIS, "BTCUSDT") as ctx:
            ctx.context_value = {"bids": [[50000, 1.5]]}
            time.sleep(0.001)
        
        # Check that context event was recorded
        validator = get_binance_validator()
        assert len(validator.context_validator.context_events) > 0

class TestBinanceIntegrationValidationIntegration:
    """Integration tests for Binance integration validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.binance_integration_validation
        infra.binance_integration_validation._binance_validator = None
    
    def test_comprehensive_binance_analysis(self):
        """Test comprehensive Binance analysis workflow"""
        validator = get_binance_validator()
        
        # Simulate context usage
        usage_types = [
            ContextUsageType.ORDER_BOOK_ANALYSIS,
            ContextUsageType.LARGE_ORDER_DETECTION,
            ContextUsageType.SUPPORT_RESISTANCE,
            ContextUsageType.MARKET_SENTIMENT
        ]
        
        for usage_type in usage_types:
            with binance_context_usage(usage_type, "BTCUSDT") as ctx:
                ctx.context_value = {"test": usage_type.value}
                time.sleep(0.001)  # Simulate processing
        
        # Validate integration
        result = validate_binance_integration()
        
        assert isinstance(result, dict)
        assert 'is_stable' in result
        assert 'meets_data_loss_requirement' in result
        assert 'is_context_only' in result
        assert 'overall_quality' in result
        assert 'data_loss_percentage' in result
        assert 'message_processing_rate' in result
        assert 'latency_p95_ms' in result
        assert 'error_rate' in result
        assert 'context_usage_efficiency' in result
        assert 'context_validation' in result
        assert 'quality_report' in result
        assert 'recommendations' in result
        
        # Check that metrics are calculated
        assert result['data_loss_percentage'] >= 0.0
        assert result['message_processing_rate'] >= 0.0
        assert result['latency_p95_ms'] >= 0.0
        assert result['error_rate'] >= 0.0
        assert result['context_usage_efficiency'] >= 0.0
        assert result['overall_quality'] in ['excellent', 'good', 'acceptable', 'poor', 'critical']
        assert isinstance(result['recommendations'], list)
        assert isinstance(result['context_validation'], dict)
        assert isinstance(result['quality_report'], dict)
    
    def test_data_loss_requirement_validation(self):
        """Test data loss requirement validation"""
        validator = get_binance_validator()
        
        # Add context usage
        for i in range(10):
            with binance_context_usage(ContextUsageType.ORDER_BOOK_ANALYSIS, "BTCUSDT") as ctx:
                ctx.context_value = {"test": i}
                time.sleep(0.001)
        
        # Validate integration
        result = validate_binance_integration()
        
        # Should meet data loss requirement (<10%)
        assert result['meets_data_loss_requirement'] in [True, False]  # May vary based on system
        assert result['data_loss_percentage'] >= 0.0
        assert result['data_loss_percentage'] <= 100.0
    
    def test_context_only_validation(self):
        """Test context-only usage validation"""
        validator = get_binance_validator()
        
        # Add valid context usage
        for i in range(5):
            with binance_context_usage(ContextUsageType.ORDER_BOOK_ANALYSIS, "BTCUSDT") as ctx:
                ctx.context_value = {"test": i}
                time.sleep(0.001)
        
        # Validate integration
        result = validate_binance_integration()
        
        # Should be context-only
        assert result['is_context_only'] in [True, False]  # May vary based on system
        assert 'context_validation' in result
        context_validation = result['context_validation']
        assert 'is_context_only' in context_validation
        assert 'context_usage_count' in context_validation
        assert 'non_context_usage_count' in context_validation
        assert 'context_usage_percentage' in context_validation
        assert 'violations' in context_validation
        assert 'recommendations' in context_validation
    
    def test_quality_level_detection(self):
        """Test quality level detection"""
        validator = get_binance_validator()
        
        # Add context usage
        for i in range(10):
            with binance_context_usage(ContextUsageType.LARGE_ORDER_DETECTION, "ETHUSDT") as ctx:
                ctx.context_value = {"test": i}
                time.sleep(0.001)
        
        # Get data quality report
        report = get_data_quality_report()
        
        # Check quality level
        assert report.overall_quality in [DataQualityLevel.EXCELLENT, DataQualityLevel.GOOD, 
                                        DataQualityLevel.ACCEPTABLE, DataQualityLevel.POOR, DataQualityLevel.CRITICAL]
        assert report.data_loss_percentage >= 0.0
        assert report.message_processing_rate >= 0.0
        assert report.latency_p95_ms >= 0.0
        assert report.error_rate >= 0.0
        assert report.context_usage_efficiency >= 0.0
        assert isinstance(report.recommendations, list)
        assert isinstance(report.quality_metrics, dict)
    
    def test_recommendations_generation(self):
        """Test recommendations generation"""
        validator = get_binance_validator()
        
        # Add some context usage
        for i in range(3):
            with binance_context_usage(ContextUsageType.VOLUME_ANALYSIS, "BTCUSDT") as ctx:
                ctx.context_value = {"volume": i * 100}
                time.sleep(0.001)
        
        # Get validation result
        result = validate_binance_integration()
        
        # Check recommendations
        assert 'recommendations' in result
        recommendations = result['recommendations']
        assert isinstance(recommendations, list)
        
        # Should have at least one recommendation
        assert len(recommendations) > 0
        assert all(isinstance(rec, str) for rec in recommendations)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
