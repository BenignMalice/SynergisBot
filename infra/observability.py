"""
Observability System

This module implements a comprehensive observability system with a lightweight
/health endpoint for latency and freshness breakers, providing real-time
system health monitoring and alerting capabilities.

Key Features:
- Lightweight /health endpoint for system health checks
- Latency monitoring and alerting
- Freshness breakers for data staleness detection
- System metrics collection and reporting
- Health status aggregation and reporting
- Performance monitoring and alerting
"""

import time
import json
import logging
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor
import psutil
import requests
from flask import Flask, jsonify, request

try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False

logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"

class MetricType(Enum):
    """Metric types"""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    DISK_USAGE = "disk_usage"
    NETWORK_USAGE = "network_usage"
    DATA_FRESHNESS = "data_freshness"
    QUEUE_DEPTH = "queue_depth"
    CONNECTION_COUNT = "connection_count"

class AlertLevel(Enum):
    """Alert levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class MetricValue:
    """Individual metric value"""
    metric_type: MetricType
    value: float
    timestamp: float
    unit: str
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class HealthCheck:
    """Health check result"""
    name: str
    status: HealthStatus
    message: str
    timestamp: float
    response_time_ms: float
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SystemMetrics:
    """System metrics collection"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, int]
    process_count: int
    load_average: List[float]

@dataclass
class LatencyBreaker:
    """Latency breaker configuration"""
    name: str
    threshold_ms: float
    window_size: int
    alert_threshold: float = 1.0
    enabled: bool = True

@dataclass
class FreshnessBreaker:
    """Freshness breaker configuration"""
    name: str
    max_age_seconds: float
    alert_threshold: float = 1.0
    enabled: bool = True

@dataclass
class Alert:
    """System alert"""
    level: AlertLevel
    message: str
    timestamp: float
    source: str
    details: Dict[str, Any] = field(default_factory=dict)

class MetricCollector:
    """Collects and stores system metrics"""
    
    def __init__(self, max_metrics: int = 10000):
        self.max_metrics = max_metrics
        self.metrics: List[MetricValue] = []
        self.lock = threading.RLock()
        self.start_time = time.time()
    
    def record_metric(self, metric_type: MetricType, value: float, 
                     unit: str = "", tags: Dict[str, str] = None) -> None:
        """Record a metric value"""
        with self.lock:
            metric = MetricValue(
                metric_type=metric_type,
                value=value,
                timestamp=time.time(),
                unit=unit,
                tags=tags or {}
            )
            
            self.metrics.append(metric)
            
            # Maintain max metrics limit
            if len(self.metrics) > self.max_metrics:
                self.metrics = self.metrics[-self.max_metrics:]
    
    def get_metrics(self, metric_type: Optional[MetricType] = None, 
                   since: Optional[float] = None) -> List[MetricValue]:
        """Get metrics, optionally filtered by type and time"""
        with self.lock:
            filtered_metrics = self.metrics
            
            if metric_type:
                filtered_metrics = [m for m in filtered_metrics if m.metric_type == metric_type]
            
            if since:
                filtered_metrics = [m for m in filtered_metrics if m.timestamp >= since]
            
            return filtered_metrics
    
    def get_latest_metric(self, metric_type: MetricType) -> Optional[MetricValue]:
        """Get the latest metric of a specific type"""
        with self.lock:
            for metric in reversed(self.metrics):
                if metric.metric_type == metric_type:
                    return metric
            return None
    
    def get_metric_summary(self, metric_type: MetricType, 
                          window_seconds: float = 300) -> Dict[str, Any]:
        """Get metric summary for a time window"""
        with self.lock:
            cutoff_time = time.time() - window_seconds
            recent_metrics = [
                m for m in self.metrics 
                if m.metric_type == metric_type and m.timestamp >= cutoff_time
            ]
            
            if not recent_metrics:
                return {"count": 0, "avg": 0, "min": 0, "max": 0, "latest": 0}
            
            values = [m.value for m in recent_metrics]
            
            return {
                "count": len(values),
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "latest": values[-1] if values else 0
            }

class SystemHealthMonitor:
    """Monitors system health and collects metrics"""
    
    def __init__(self):
        self.metric_collector = MetricCollector()
        self.health_checks: Dict[str, Callable[[], HealthCheck]] = {}
        self.latency_breakers: Dict[str, LatencyBreaker] = {}
        self.freshness_breakers: Dict[str, FreshnessBreaker] = {}
        self.alerts: List[Alert] = []
        self.lock = threading.RLock()
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.on_alert: Optional[Callable[[Alert], None]] = None
        self.on_health_change: Optional[Callable[[str, HealthStatus], None]] = None
    
    def set_callbacks(self,
                      on_alert: Optional[Callable[[Alert], None]] = None,
                      on_health_change: Optional[Callable[[str, HealthStatus], None]] = None) -> None:
        """Set callback functions for health events"""
        self.on_alert = on_alert
        self.on_health_change = on_health_change
    
    def register_health_check(self, name: str, check_func: Callable[[], HealthCheck]) -> None:
        """Register a health check function"""
        with self.lock:
            self.health_checks[name] = check_func
    
    def register_latency_breaker(self, breaker: LatencyBreaker) -> None:
        """Register a latency breaker"""
        with self.lock:
            self.latency_breakers[breaker.name] = breaker
    
    def register_freshness_breaker(self, breaker: FreshnessBreaker) -> None:
        """Register a freshness breaker"""
        with self.lock:
            self.freshness_breakers[breaker.name] = breaker
    
    def start_monitoring(self, interval_seconds: float = 1.0) -> None:
        """Start system monitoring"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Started system health monitoring")
    
    def stop_monitoring(self) -> None:
        """Stop system monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        logger.info("Stopped system health monitoring")
    
    def _monitor_loop(self, interval_seconds: float) -> None:
        """Main monitoring loop"""
        while self.monitoring:
            try:
                self._collect_system_metrics()
                self._check_latency_breakers()
                self._check_freshness_breakers()
                time.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(interval_seconds)
    
    def _collect_system_metrics(self) -> None:
        """Collect system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.metric_collector.record_metric(
                MetricType.CPU_USAGE, cpu_percent, "%"
            )
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.metric_collector.record_metric(
                MetricType.MEMORY_USAGE, memory.percent, "%"
            )
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.metric_collector.record_metric(
                MetricType.DISK_USAGE, disk_percent, "%"
            )
            
            # Network I/O
            network = psutil.net_io_counters()
            self.metric_collector.record_metric(
                MetricType.NETWORK_USAGE, network.bytes_sent, "bytes",
                {"direction": "sent"}
            )
            self.metric_collector.record_metric(
                MetricType.NETWORK_USAGE, network.bytes_recv, "bytes",
                {"direction": "received"}
            )
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def _check_latency_breakers(self) -> None:
        """Check latency breakers"""
        for name, breaker in self.latency_breakers.items():
            if not breaker.enabled:
                continue
            
            # Get recent latency metrics
            recent_metrics = self.metric_collector.get_metrics(
                MetricType.LATENCY, since=time.time() - breaker.window_size
            )
            
            if not recent_metrics:
                continue
            
            # Calculate average latency
            avg_latency = sum(m.value for m in recent_metrics) / len(recent_metrics)
            
            if avg_latency > breaker.threshold_ms:
                alert = Alert(
                    level=AlertLevel.WARNING,
                    message=f"Latency breaker triggered: {name} - {avg_latency:.2f}ms > {breaker.threshold_ms}ms",
                    timestamp=time.time(),
                    source="latency_breaker",
                    details={
                        "breaker_name": name,
                        "threshold_ms": breaker.threshold_ms,
                        "actual_latency_ms": avg_latency,
                        "window_size": breaker.window_size
                    }
                )
                
                self._add_alert(alert)
    
    def _check_freshness_breakers(self) -> None:
        """Check freshness breakers"""
        for name, breaker in self.freshness_breakers.items():
            if not breaker.enabled:
                continue
            
            # Get latest data freshness metric
            freshness_metric = self.metric_collector.get_latest_metric(MetricType.DATA_FRESHNESS)
            
            if not freshness_metric:
                continue
            
            age_seconds = time.time() - freshness_metric.timestamp
            
            if age_seconds > breaker.max_age_seconds:
                alert = Alert(
                    level=AlertLevel.WARNING,
                    message=f"Freshness breaker triggered: {name} - {age_seconds:.2f}s > {breaker.max_age_seconds}s",
                    timestamp=time.time(),
                    source="freshness_breaker",
                    details={
                        "breaker_name": name,
                        "max_age_seconds": breaker.max_age_seconds,
                        "actual_age_seconds": age_seconds
                    }
                )
                
                self._add_alert(alert)
    
    def _add_alert(self, alert: Alert) -> None:
        """Add an alert"""
        with self.lock:
            self.alerts.append(alert)
            
            # Keep only recent alerts
            cutoff_time = time.time() - 3600  # 1 hour
            self.alerts = [a for a in self.alerts if a.timestamp >= cutoff_time]
            
            # Call alert callback
            if self.on_alert:
                try:
                    self.on_alert(alert)
                except Exception as e:
                    logger.error(f"Error in on_alert callback: {e}")
    
    def run_health_checks(self) -> Dict[str, HealthCheck]:
        """Run all registered health checks"""
        results = {}
        
        for name, check_func in self.health_checks.items():
            try:
                start_time = time.time()
                result = check_func()
                result.response_time_ms = (time.time() - start_time) * 1000
                results[name] = result
            except Exception as e:
                result = HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {str(e)}",
                    timestamp=time.time(),
                    response_time_ms=0
                )
                results[name] = result
        
        return results
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        health_checks = self.run_health_checks()
        
        # Determine overall status
        statuses = [check.status for check in health_checks.values()]
        if not statuses:
            overall_status = HealthStatus.HEALTHY
        elif HealthStatus.CRITICAL in statuses:
            overall_status = HealthStatus.CRITICAL
        elif HealthStatus.UNHEALTHY in statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Get recent alerts
        recent_alerts = [
            alert for alert in self.alerts 
            if time.time() - alert.timestamp < 300  # Last 5 minutes
        ]
        
        return {
            "status": overall_status.value,
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self.metric_collector.start_time,
            "health_checks": {name: {
                "name": check.name,
                "status": check.status.value,
                "message": check.message,
                "timestamp": check.timestamp,
                "response_time_ms": check.response_time_ms,
                "details": check.details
            } for name, check in health_checks.items()},
            "recent_alerts": [{
                "level": alert.level.value,
                "message": alert.message,
                "timestamp": alert.timestamp,
                "source": alert.source,
                "details": alert.details
            } for alert in recent_alerts],
            "metrics_summary": self._get_metrics_summary()
        }
    
    def _get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        summary = {}
        
        for metric_type in MetricType:
            metric_summary = self.metric_collector.get_metric_summary(metric_type)
            summary[metric_type.value] = metric_summary
        
        return summary

class HealthEndpoint:
    """Lightweight health endpoint"""
    
    def __init__(self, health_monitor: SystemHealthMonitor, port: int = 8080):
        self.health_monitor = health_monitor
        self.port = port
        self.app = Flask(__name__)
        if CORS_AVAILABLE:
            CORS(self.app)
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Setup Flask routes"""
        
        @self.app.route('/health', methods=['GET'])
        def health():
            """Main health endpoint"""
            try:
                health_data = self.health_monitor.get_system_health()
                return jsonify(health_data), 200
            except Exception as e:
                logger.error(f"Error in health endpoint: {e}")
                return jsonify({
                    "status": "error",
                    "message": str(e),
                    "timestamp": time.time()
                }), 500
        
        @self.app.route('/health/checks', methods=['GET'])
        def health_checks():
            """Health checks endpoint"""
            try:
                checks = self.health_monitor.run_health_checks()
                return jsonify({name: {
                "name": check.name,
                "status": check.status.value,
                "message": check.message,
                "timestamp": check.timestamp,
                "response_time_ms": check.response_time_ms,
                "details": check.details
            } for name, check in checks.items()}), 200
            except Exception as e:
                logger.error(f"Error in health checks endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/health/metrics', methods=['GET'])
        def metrics():
            """Metrics endpoint"""
            try:
                metric_type = request.args.get('type')
                since = request.args.get('since', type=float)
                
                if metric_type:
                    try:
                        metric_type_enum = MetricType(metric_type)
                        metrics = self.health_monitor.metric_collector.get_metrics(
                            metric_type_enum, since
                        )
                    except ValueError:
                        return jsonify({"error": f"Invalid metric type: {metric_type}"}), 400
                else:
                    metrics = self.health_monitor.metric_collector.get_metrics(since=since)
                
                return jsonify([{
                    "metric_type": metric.metric_type.value,
                    "value": metric.value,
                    "timestamp": metric.timestamp,
                    "unit": metric.unit,
                    "tags": metric.tags
                } for metric in metrics]), 200
            except Exception as e:
                logger.error(f"Error in metrics endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/health/alerts', methods=['GET'])
        def alerts():
            """Alerts endpoint"""
            try:
                since = request.args.get('since', type=float)
                level = request.args.get('level')
                
                alerts = self.health_monitor.alerts
                if since:
                    alerts = [a for a in alerts if a.timestamp >= since]
                if level:
                    try:
                        alert_level = AlertLevel(level)
                        alerts = [a for a in alerts if a.level == alert_level]
                    except ValueError:
                        return jsonify({"error": f"Invalid alert level: {level}"}), 400
                
                return jsonify([{
                    "level": alert.level.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp,
                    "source": alert.source,
                    "details": alert.details
                } for alert in alerts]), 200
            except Exception as e:
                logger.error(f"Error in alerts endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/health/breakers', methods=['GET'])
        def breakers():
            """Breakers endpoint"""
            try:
                return jsonify({
                    "latency_breakers": {
                        name: {
                            "name": breaker.name,
                            "threshold_ms": breaker.threshold_ms,
                            "window_size": breaker.window_size,
                            "alert_threshold": breaker.alert_threshold,
                            "enabled": breaker.enabled
                        } for name, breaker in self.health_monitor.latency_breakers.items()
                    },
                    "freshness_breakers": {
                        name: {
                            "name": breaker.name,
                            "max_age_seconds": breaker.max_age_seconds,
                            "alert_threshold": breaker.alert_threshold,
                            "enabled": breaker.enabled
                        } for name, breaker in self.health_monitor.freshness_breakers.items()
                    }
                }), 200
            except Exception as e:
                logger.error(f"Error in breakers endpoint: {e}")
                return jsonify({"error": str(e)}), 500
    
    def start(self, host: str = '0.0.0.0', debug: bool = False) -> None:
        """Start the health endpoint server"""
        logger.info(f"Starting health endpoint on {host}:{self.port}")
        self.app.run(host=host, port=self.port, debug=debug, threaded=True)
    
    def stop(self) -> None:
        """Stop the health endpoint server"""
        logger.info("Stopping health endpoint")

# Global health monitor
_health_monitor: Optional[SystemHealthMonitor] = None
_health_endpoint: Optional[HealthEndpoint] = None

def get_health_monitor() -> SystemHealthMonitor:
    """Get global health monitor instance"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = SystemHealthMonitor()
    return _health_monitor

def get_health_endpoint(port: int = 8080) -> HealthEndpoint:
    """Get global health endpoint instance"""
    global _health_endpoint
    if _health_endpoint is None:
        health_monitor = get_health_monitor()
        _health_endpoint = HealthEndpoint(health_monitor, port)
    return _health_endpoint

def start_health_monitoring(interval_seconds: float = 1.0) -> None:
    """Start health monitoring"""
    monitor = get_health_monitor()
    monitor.start_monitoring(interval_seconds)

def stop_health_monitoring() -> None:
    """Stop health monitoring"""
    monitor = get_health_monitor()
    monitor.stop_monitoring()

def start_health_endpoint(host: str = '0.0.0.0', port: int = 8080, debug: bool = False) -> None:
    """Start health endpoint server"""
    endpoint = get_health_endpoint(port)
    endpoint.start(host, debug)

def record_latency(latency_ms: float, source: str = "") -> None:
    """Record latency metric"""
    monitor = get_health_monitor()
    monitor.metric_collector.record_metric(
        MetricType.LATENCY, latency_ms, "ms", {"source": source}
    )

def record_data_freshness(timestamp: float, source: str = "") -> None:
    """Record data freshness metric"""
    monitor = get_health_monitor()
    age_seconds = time.time() - timestamp
    monitor.metric_collector.record_metric(
        MetricType.DATA_FRESHNESS, age_seconds, "seconds", {"source": source}
    )

def add_latency_breaker(name: str, threshold_ms: float, window_size: int = 10) -> None:
    """Add latency breaker"""
    monitor = get_health_monitor()
    breaker = LatencyBreaker(
        name=name,
        threshold_ms=threshold_ms,
        window_size=window_size,
        alert_threshold=1.0
    )
    monitor.register_latency_breaker(breaker)

def add_freshness_breaker(name: str, max_age_seconds: float) -> None:
    """Add freshness breaker"""
    monitor = get_health_monitor()
    breaker = FreshnessBreaker(
        name=name,
        max_age_seconds=max_age_seconds,
        alert_threshold=1.0
    )
    monitor.register_freshness_breaker(breaker)

if __name__ == "__main__":
    # Example usage
    monitor = get_health_monitor()
    
    # Add some health checks
    def database_health_check():
        return HealthCheck(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Database connection OK",
            timestamp=time.time(),
            response_time_ms=5.0
        )
    
    monitor.register_health_check("database", database_health_check)
    
    # Add latency breaker
    add_latency_breaker("api_latency", 1000.0, 10)
    
    # Add freshness breaker
    add_freshness_breaker("data_freshness", 60.0)
    
    # Start monitoring
    start_health_monitoring(1.0)
    
    # Start health endpoint
    start_health_endpoint(port=8080)
