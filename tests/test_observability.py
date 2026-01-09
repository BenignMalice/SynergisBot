"""
Comprehensive tests for observability system

Tests health monitoring, metrics collection, latency/freshness breakers,
health endpoint functionality, and system health reporting.
"""

import pytest
import time
import json
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional

from infra.observability import (
    SystemHealthMonitor, MetricCollector, HealthEndpoint,
    HealthStatus, MetricType, AlertLevel, MetricValue, HealthCheck,
    SystemMetrics, LatencyBreaker, FreshnessBreaker, Alert,
    get_health_monitor, get_health_endpoint, start_health_monitoring,
    stop_health_monitoring, start_health_endpoint, record_latency,
    record_data_freshness, add_latency_breaker, add_freshness_breaker
)

class TestHealthStatus:
    """Test health status enumeration"""
    
    def test_health_statuses(self):
        """Test all health statuses"""
        statuses = [
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY,
            HealthStatus.CRITICAL
        ]
        
        for status in statuses:
            assert isinstance(status, HealthStatus)
            assert status.value in ["healthy", "degraded", "unhealthy", "critical"]

class TestMetricType:
    """Test metric type enumeration"""
    
    def test_metric_types(self):
        """Test all metric types"""
        metric_types = [
            MetricType.LATENCY,
            MetricType.THROUGHPUT,
            MetricType.ERROR_RATE,
            MetricType.MEMORY_USAGE,
            MetricType.CPU_USAGE,
            MetricType.DISK_USAGE,
            MetricType.NETWORK_USAGE,
            MetricType.DATA_FRESHNESS,
            MetricType.QUEUE_DEPTH,
            MetricType.CONNECTION_COUNT
        ]
        
        for metric_type in metric_types:
            assert isinstance(metric_type, MetricType)
            assert metric_type.value in [
                "latency", "throughput", "error_rate", "memory_usage",
                "cpu_usage", "disk_usage", "network_usage", "data_freshness",
                "queue_depth", "connection_count"
            ]

class TestAlertLevel:
    """Test alert level enumeration"""
    
    def test_alert_levels(self):
        """Test all alert levels"""
        levels = [
            AlertLevel.INFO,
            AlertLevel.WARNING,
            AlertLevel.ERROR,
            AlertLevel.CRITICAL
        ]
        
        for level in levels:
            assert isinstance(level, AlertLevel)
            assert level.value in ["info", "warning", "error", "critical"]

class TestMetricValue:
    """Test metric value data structure"""
    
    def test_metric_value_creation(self):
        """Test metric value creation"""
        metric = MetricValue(
            metric_type=MetricType.LATENCY,
            value=100.5,
            timestamp=time.time(),
            unit="ms",
            tags={"source": "api"}
        )
        
        assert metric.metric_type == MetricType.LATENCY
        assert metric.value == 100.5
        assert metric.timestamp > 0
        assert metric.unit == "ms"
        assert metric.tags["source"] == "api"
    
    def test_metric_value_defaults(self):
        """Test metric value defaults"""
        metric = MetricValue(
            metric_type=MetricType.CPU_USAGE,
            value=50.0,
            timestamp=time.time(),
            unit="%"
        )
        
        assert metric.tags == {}

class TestHealthCheck:
    """Test health check data structure"""
    
    def test_health_check_creation(self):
        """Test health check creation"""
        check = HealthCheck(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Database connection OK",
            timestamp=time.time(),
            response_time_ms=5.0,
            details={"connections": 10}
        )
        
        assert check.name == "database"
        assert check.status == HealthStatus.HEALTHY
        assert check.message == "Database connection OK"
        assert check.timestamp > 0
        assert check.response_time_ms == 5.0
        assert check.details["connections"] == 10
    
    def test_health_check_defaults(self):
        """Test health check defaults"""
        check = HealthCheck(
            name="api",
            status=HealthStatus.HEALTHY,
            message="API OK",
            timestamp=time.time(),
            response_time_ms=10.0
        )
        
        assert check.details == {}

class TestAlert:
    """Test alert data structure"""
    
    def test_alert_creation(self):
        """Test alert creation"""
        alert = Alert(
            level=AlertLevel.WARNING,
            message="High latency detected",
            timestamp=time.time(),
            source="latency_breaker",
            details={"threshold": 1000, "actual": 1500}
        )
        
        assert alert.level == AlertLevel.WARNING
        assert alert.message == "High latency detected"
        assert alert.timestamp > 0
        assert alert.source == "latency_breaker"
        assert alert.details["threshold"] == 1000
    
    def test_alert_defaults(self):
        """Test alert defaults"""
        alert = Alert(
            level=AlertLevel.ERROR,
            message="System error",
            timestamp=time.time(),
            source="system"
        )
        
        assert alert.details == {}

class TestMetricCollector:
    """Test metric collector"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.collector = MetricCollector(max_metrics=100)
    
    def test_collector_initialization(self):
        """Test collector initialization"""
        assert self.collector.max_metrics == 100
        assert len(self.collector.metrics) == 0
        assert self.collector.start_time > 0
    
    def test_record_metric(self):
        """Test recording metrics"""
        self.collector.record_metric(
            MetricType.LATENCY, 100.0, "ms", {"source": "api"}
        )
        
        assert len(self.collector.metrics) == 1
        metric = self.collector.metrics[0]
        assert metric.metric_type == MetricType.LATENCY
        assert metric.value == 100.0
        assert metric.unit == "ms"
        assert metric.tags["source"] == "api"
    
    def test_record_multiple_metrics(self):
        """Test recording multiple metrics"""
        for i in range(5):
            self.collector.record_metric(
                MetricType.LATENCY, float(i * 10), "ms"
            )
        
        assert len(self.collector.metrics) == 5
        assert all(m.metric_type == MetricType.LATENCY for m in self.collector.metrics)
    
    def test_max_metrics_limit(self):
        """Test max metrics limit"""
        # Record more metrics than the limit
        for i in range(150):  # More than max_metrics (100)
            self.collector.record_metric(
                MetricType.LATENCY, float(i), "ms"
            )
        
        # Should only keep the last 100 metrics
        assert len(self.collector.metrics) == 100
        assert self.collector.metrics[0].value == 50.0  # First kept metric
        assert self.collector.metrics[-1].value == 149.0  # Last metric
    
    def test_get_metrics(self):
        """Test getting metrics"""
        # Record some metrics
        for i in range(5):
            self.collector.record_metric(
                MetricType.LATENCY, float(i * 10), "ms"
            )
        
        # Get all metrics
        all_metrics = self.collector.get_metrics()
        assert len(all_metrics) == 5
        
        # Get metrics by type
        latency_metrics = self.collector.get_metrics(MetricType.LATENCY)
        assert len(latency_metrics) == 5
        
        # Get metrics since timestamp
        since_time = time.time() - 1
        recent_metrics = self.collector.get_metrics(since=since_time)
        assert len(recent_metrics) == 5
    
    def test_get_latest_metric(self):
        """Test getting latest metric"""
        # Record some metrics
        for i in range(3):
            self.collector.record_metric(
                MetricType.LATENCY, float(i * 10), "ms"
            )
        
        latest = self.collector.get_latest_metric(MetricType.LATENCY)
        assert latest is not None
        assert latest.value == 20.0  # Last recorded value
        
        # Test non-existent metric type
        latest = self.collector.get_latest_metric(MetricType.CPU_USAGE)
        assert latest is None
    
    def test_get_metric_summary(self):
        """Test getting metric summary"""
        # Record some metrics
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for value in values:
            self.collector.record_metric(
                MetricType.LATENCY, value, "ms"
            )
        
        summary = self.collector.get_metric_summary(MetricType.LATENCY)
        
        assert summary["count"] == 5
        assert summary["avg"] == 30.0
        assert summary["min"] == 10.0
        assert summary["max"] == 50.0
        assert summary["latest"] == 50.0

class TestSystemHealthMonitor:
    """Test system health monitor"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.monitor = SystemHealthMonitor()
    
    def test_monitor_initialization(self):
        """Test monitor initialization"""
        assert isinstance(self.monitor.metric_collector, MetricCollector)
        assert len(self.monitor.health_checks) == 0
        assert len(self.monitor.latency_breakers) == 0
        assert len(self.monitor.freshness_breakers) == 0
        assert len(self.monitor.alerts) == 0
        assert self.monitor.monitoring is False
    
    def test_register_health_check(self):
        """Test registering health check"""
        def test_check():
            return HealthCheck(
                name="test",
                status=HealthStatus.HEALTHY,
                message="Test OK",
                timestamp=time.time(),
                response_time_ms=1.0
            )
        
        self.monitor.register_health_check("test", test_check)
        assert "test" in self.monitor.health_checks
    
    def test_register_latency_breaker(self):
        """Test registering latency breaker"""
        breaker = LatencyBreaker(
            name="api_latency",
            threshold_ms=1000.0,
            window_size=10,
            alert_threshold=1.0
        )
        
        self.monitor.register_latency_breaker(breaker)
        assert "api_latency" in self.monitor.latency_breakers
        assert self.monitor.latency_breakers["api_latency"].threshold_ms == 1000.0
    
    def test_register_freshness_breaker(self):
        """Test registering freshness breaker"""
        breaker = FreshnessBreaker(
            name="data_freshness",
            max_age_seconds=60.0,
            alert_threshold=1.0
        )
        
        self.monitor.register_freshness_breaker(breaker)
        assert "data_freshness" in self.monitor.freshness_breakers
        assert self.monitor.freshness_breakers["data_freshness"].max_age_seconds == 60.0
    
    def test_run_health_checks(self):
        """Test running health checks"""
        def healthy_check():
            return HealthCheck(
                name="healthy",
                status=HealthStatus.HEALTHY,
                message="OK",
                timestamp=time.time(),
                response_time_ms=1.0
            )
        
        def unhealthy_check():
            return HealthCheck(
                name="unhealthy",
                status=HealthStatus.UNHEALTHY,
                message="Failed",
                timestamp=time.time(),
                response_time_ms=2.0
            )
        
        self.monitor.register_health_check("healthy", healthy_check)
        self.monitor.register_health_check("unhealthy", unhealthy_check)
        
        results = self.monitor.run_health_checks()
        
        assert len(results) == 2
        assert results["healthy"].status == HealthStatus.HEALTHY
        assert results["unhealthy"].status == HealthStatus.UNHEALTHY
    
    def test_run_health_checks_exception(self):
        """Test health check with exception"""
        def failing_check():
            raise Exception("Health check failed")
        
        self.monitor.register_health_check("failing", failing_check)
        
        results = self.monitor.run_health_checks()
        
        assert "failing" in results
        assert results["failing"].status == HealthStatus.UNHEALTHY
        assert "Health check failed" in results["failing"].message
    
    def test_get_system_health(self):
        """Test getting system health"""
        def healthy_check():
            return HealthCheck(
                name="test",
                status=HealthStatus.HEALTHY,
                message="OK",
                timestamp=time.time(),
                response_time_ms=1.0
            )
        
        self.monitor.register_health_check("test", healthy_check)
        
        health = self.monitor.get_system_health()
        
        assert "status" in health
        assert "timestamp" in health
        assert "uptime_seconds" in health
        assert "health_checks" in health
        assert "recent_alerts" in health
        assert "metrics_summary" in health
        assert health["status"] == "healthy"
    
    def test_callback_setting(self):
        """Test callback function setting"""
        on_alert = Mock()
        on_health_change = Mock()
        
        self.monitor.set_callbacks(
            on_alert=on_alert,
            on_health_change=on_health_change
        )
        
        assert self.monitor.on_alert == on_alert
        assert self.monitor.on_health_change == on_health_change

class TestLatencyBreaker:
    """Test latency breaker data structure"""
    
    def test_latency_breaker_creation(self):
        """Test latency breaker creation"""
        breaker = LatencyBreaker(
            name="api_latency",
            threshold_ms=1000.0,
            window_size=10,
            alert_threshold=1.0,
            enabled=True
        )
        
        assert breaker.name == "api_latency"
        assert breaker.threshold_ms == 1000.0
        assert breaker.window_size == 10
        assert breaker.alert_threshold == 1.0
        assert breaker.enabled is True
    
    def test_latency_breaker_defaults(self):
        """Test latency breaker defaults"""
        breaker = LatencyBreaker(
            name="test",
            threshold_ms=500.0,
            window_size=5
        )
        
        assert breaker.alert_threshold == 1.0
        assert breaker.enabled is True

class TestFreshnessBreaker:
    """Test freshness breaker data structure"""
    
    def test_freshness_breaker_creation(self):
        """Test freshness breaker creation"""
        breaker = FreshnessBreaker(
            name="data_freshness",
            max_age_seconds=60.0,
            alert_threshold=1.0,
            enabled=True
        )
        
        assert breaker.name == "data_freshness"
        assert breaker.max_age_seconds == 60.0
        assert breaker.alert_threshold == 1.0
        assert breaker.enabled is True
    
    def test_freshness_breaker_defaults(self):
        """Test freshness breaker defaults"""
        breaker = FreshnessBreaker(
            name="test",
            max_age_seconds=30.0
        )
        
        assert breaker.alert_threshold == 1.0
        assert breaker.enabled is True

class TestHealthEndpoint:
    """Test health endpoint"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.monitor = SystemHealthMonitor()
        self.endpoint = HealthEndpoint(self.monitor, port=8080)
    
    def test_endpoint_initialization(self):
        """Test endpoint initialization"""
        assert self.endpoint.health_monitor == self.monitor
        assert self.endpoint.port == 8080
        assert hasattr(self.endpoint, 'app')
    
    def test_health_route(self):
        """Test health route"""
        with self.endpoint.app.test_client() as client:
            response = client.get('/health')
            assert response.status_code == 200
            
            data = response.get_json()
            assert "status" in data
            assert "timestamp" in data
            assert "uptime_seconds" in data
    
    def test_health_checks_route(self):
        """Test health checks route"""
        # Add a health check
        def test_check():
            return HealthCheck(
                name="test",
                status=HealthStatus.HEALTHY,
                message="OK",
                timestamp=time.time(),
                response_time_ms=1.0
            )
        
        self.monitor.register_health_check("test", test_check)
        
        with self.endpoint.app.test_client() as client:
            response = client.get('/health/checks')
            assert response.status_code == 200
            
            data = response.get_json()
            assert "test" in data
            assert data["test"]["status"] == "healthy"
    
    def test_metrics_route(self):
        """Test metrics route"""
        # Add some metrics
        self.monitor.metric_collector.record_metric(
            MetricType.LATENCY, 100.0, "ms"
        )
        
        with self.endpoint.app.test_client() as client:
            response = client.get('/health/metrics')
            assert response.status_code == 200
            
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) >= 1
    
    def test_metrics_route_with_type(self):
        """Test metrics route with type filter"""
        # Add some metrics
        self.monitor.metric_collector.record_metric(
            MetricType.LATENCY, 100.0, "ms"
        )
        self.monitor.metric_collector.record_metric(
            MetricType.CPU_USAGE, 50.0, "%"
        )
        
        with self.endpoint.app.test_client() as client:
            response = client.get('/health/metrics?type=latency')
            assert response.status_code == 200
            
            data = response.get_json()
            assert isinstance(data, list)
            assert all(metric["metric_type"] == "latency" for metric in data)
    
    def test_alerts_route(self):
        """Test alerts route"""
        # Add an alert
        alert = Alert(
            level=AlertLevel.WARNING,
            message="Test alert",
            timestamp=time.time(),
            source="test"
        )
        self.monitor.alerts.append(alert)
        
        with self.endpoint.app.test_client() as client:
            response = client.get('/health/alerts')
            assert response.status_code == 200
            
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) >= 1
    
    def test_breakers_route(self):
        """Test breakers route"""
        # Add breakers
        latency_breaker = LatencyBreaker(
            name="test_latency",
            threshold_ms=1000.0,
            window_size=10,
            alert_threshold=1.0
        )
        freshness_breaker = FreshnessBreaker(
            name="test_freshness",
            max_age_seconds=60.0
        )
        
        self.monitor.register_latency_breaker(latency_breaker)
        self.monitor.register_freshness_breaker(freshness_breaker)
        
        with self.endpoint.app.test_client() as client:
            response = client.get('/health/breakers')
            assert response.status_code == 200
            
            data = response.get_json()
            assert "latency_breakers" in data
            assert "freshness_breakers" in data
            assert "test_latency" in data["latency_breakers"]
            assert "test_freshness" in data["freshness_breakers"]

class TestGlobalFunctions:
    """Test global observability functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global instances
        import infra.observability
        infra.observability._health_monitor = None
        infra.observability._health_endpoint = None
    
    def test_get_health_monitor(self):
        """Test global health monitor access"""
        monitor1 = get_health_monitor()
        monitor2 = get_health_monitor()
        
        # Should return same instance
        assert monitor1 is monitor2
        assert isinstance(monitor1, SystemHealthMonitor)
    
    def test_get_health_endpoint(self):
        """Test global health endpoint access"""
        endpoint1 = get_health_endpoint(8080)
        endpoint2 = get_health_endpoint(8080)
        
        # Should return same instance
        assert endpoint1 is endpoint2
        assert isinstance(endpoint1, HealthEndpoint)
    
    def test_record_latency(self):
        """Test global latency recording"""
        record_latency(100.0, "api")
        
        monitor = get_health_monitor()
        metrics = monitor.metric_collector.get_metrics(MetricType.LATENCY)
        assert len(metrics) >= 1
        assert metrics[-1].value == 100.0
        assert metrics[-1].tags["source"] == "api"
    
    def test_record_data_freshness(self):
        """Test global data freshness recording"""
        timestamp = time.time() - 30  # 30 seconds ago
        record_data_freshness(timestamp, "database")
        
        monitor = get_health_monitor()
        metrics = monitor.metric_collector.get_metrics(MetricType.DATA_FRESHNESS)
        assert len(metrics) >= 1
        assert metrics[-1].value >= 30.0  # Should be at least 30 seconds old
        assert metrics[-1].tags["source"] == "database"
    
    def test_add_latency_breaker(self):
        """Test global latency breaker addition"""
        add_latency_breaker("test_latency", 1000.0, 10)
        
        monitor = get_health_monitor()
        assert "test_latency" in monitor.latency_breakers
        assert monitor.latency_breakers["test_latency"].threshold_ms == 1000.0
    
    def test_add_freshness_breaker(self):
        """Test global freshness breaker addition"""
        add_freshness_breaker("test_freshness", 60.0)
        
        monitor = get_health_monitor()
        assert "test_freshness" in monitor.freshness_breakers
        assert monitor.freshness_breakers["test_freshness"].max_age_seconds == 60.0

class TestObservabilityIntegration:
    """Integration tests for observability system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global instances
        import infra.observability
        infra.observability._health_monitor = None
        infra.observability._health_endpoint = None
    
    def test_comprehensive_health_monitoring(self):
        """Test comprehensive health monitoring"""
        # Add health checks
        def database_check():
            return HealthCheck(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database OK",
                timestamp=time.time(),
                response_time_ms=5.0
            )
        
        def api_check():
            return HealthCheck(
                name="api",
                status=HealthStatus.HEALTHY,
                message="API OK",
                timestamp=time.time(),
                response_time_ms=10.0
            )
        
        monitor = get_health_monitor()
        monitor.register_health_check("database", database_check)
        monitor.register_health_check("api", api_check)
        
        # Add breakers
        add_latency_breaker("api_latency", 1000.0, 10)
        add_freshness_breaker("data_freshness", 60.0)
        
        # Record some metrics
        record_latency(100.0, "api")
        record_latency(200.0, "api")
        record_data_freshness(time.time() - 30, "database")
        
        # Get system health
        health = monitor.get_system_health()
        
        assert health["status"] == "healthy"
        assert "database" in health["health_checks"]
        assert "api" in health["health_checks"]
        assert "latency" in health["metrics_summary"]
        assert "data_freshness" in health["metrics_summary"]
    
    def test_health_endpoint_integration(self):
        """Test health endpoint integration"""
        # Setup monitoring
        monitor = get_health_monitor()
        
        def test_check():
            return HealthCheck(
                name="test",
                status=HealthStatus.HEALTHY,
                message="OK",
                timestamp=time.time(),
                response_time_ms=1.0
            )
        
        monitor.register_health_check("test", test_check)
        
        # Record metrics
        record_latency(100.0, "test")
        
        # Test endpoint
        endpoint = get_health_endpoint(8080)
        
        with endpoint.app.test_client() as client:
            # Test health endpoint
            response = client.get('/health')
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "healthy"
            
            # Test metrics endpoint
            response = client.get('/health/metrics')
            assert response.status_code == 200
            data = response.get_json()
            assert len(data) >= 1
            
            # Test health checks endpoint
            response = client.get('/health/checks')
            assert response.status_code == 200
            data = response.get_json()
            assert "test" in data
    
    def test_alert_system(self):
        """Test alert system"""
        monitor = get_health_monitor()
        
        # Add alert callback
        alert_callback = Mock()
        monitor.set_callbacks(on_alert=alert_callback)
        
        # Add latency breaker
        add_latency_breaker("test_latency", 100.0, 5)
        
        # Record high latency metrics
        for i in range(6):  # More than window size
            record_latency(150.0, "test")  # Above threshold
            time.sleep(0.01)  # Small delay
        
        # Manually trigger breaker check
        monitor._check_latency_breakers()
        
        # Check that alert was triggered
        assert len(monitor.alerts) >= 1
        assert any(alert.source == "latency_breaker" for alert in monitor.alerts)
    
    def test_metrics_collection_performance(self):
        """Test metrics collection performance"""
        monitor = get_health_monitor()
        
        # Record many metrics
        start_time = time.time()
        for i in range(1000):
            monitor.metric_collector.record_metric(
                MetricType.LATENCY, float(i), "ms"
            )
        end_time = time.time()
        
        # Should complete quickly
        assert (end_time - start_time) < 1.0  # Less than 1 second
        
        # Should have all metrics
        metrics = monitor.metric_collector.get_metrics()
        assert len(metrics) == 1000

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
