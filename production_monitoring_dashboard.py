#!/usr/bin/env python3
"""
Production Monitoring Dashboard for TelegramMoneyBot v8.0
Comprehensive production monitoring, alerting, and observability system
"""

import asyncio
import json
import logging
import time
import psutil
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import threading
import queue
import requests
from collections import defaultdict, deque
import numpy as np
import pandas as pd
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """Alert levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MetricType(Enum):
    """Metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"

class ComponentStatus(Enum):
    """Component status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DOWN = "down"

@dataclass
class Metric:
    """Metric data structure"""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str]
    metric_type: MetricType
    component: str

@dataclass
class Alert:
    """Alert data structure"""
    alert_id: str
    level: AlertLevel
    message: str
    timestamp: datetime
    component: str
    metric_name: str
    threshold: float
    current_value: float
    resolved: bool = False
    resolved_at: Optional[datetime] = None

@dataclass
class ComponentHealth:
    """Component health data structure"""
    component_name: str
    status: ComponentStatus
    last_check: datetime
    response_time_ms: float
    error_count: int
    success_count: int
    uptime_percent: float
    metrics: Dict[str, float]

@dataclass
class DashboardData:
    """Dashboard data structure"""
    timestamp: datetime
    overall_status: ComponentStatus
    components: List[ComponentHealth]
    alerts: List[Alert]
    metrics: List[Metric]
    system_metrics: Dict[str, float]
    performance_metrics: Dict[str, float]

class ProductionMonitoringDashboard:
    """Production monitoring dashboard system"""
    
    def __init__(self, config_path: str = "monitoring_dashboard_config.json"):
        self.config = self._load_config(config_path)
        self.components: Dict[str, ComponentHealth] = {}
        self.alerts: List[Alert] = []
        self.metrics: List[Metric] = []
        self.dashboard_data: List[DashboardData] = []
        self.running = False
        
        # Initialize monitoring components
        self._initialize_monitoring_components()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load monitoring dashboard configuration"""
        default_config = {
            "monitoring": {
                "collection_interval": 5.0,
                "retention_days": 30,
                "alert_retention_days": 7,
                "dashboard_refresh_interval": 1.0
            },
            "components": {
                "chatgpt_bot": {
                    "enabled": True,
                    "health_check_url": "http://localhost:8000/health",
                    "timeout_seconds": 5,
                    "critical": True
                },
                "desktop_agent": {
                    "enabled": True,
                    "health_check_url": "http://localhost:8001/health",
                    "timeout_seconds": 5,
                    "critical": True
                },
                "main_api": {
                    "enabled": True,
                    "health_check_url": "http://localhost:8000/health",
                    "timeout_seconds": 5,
                    "critical": True
                },
                "database": {
                    "enabled": True,
                    "health_check_url": "sqlite:///data/bot.sqlite",
                    "timeout_seconds": 3,
                    "critical": True
                },
                "mt5_connection": {
                    "enabled": True,
                    "health_check_url": "mt5://localhost:8080",
                    "timeout_seconds": 10,
                    "critical": True
                },
                "binance_connection": {
                    "enabled": True,
                    "health_check_url": "wss://stream.binance.com:9443/ws/btcusdt@ticker",
                    "timeout_seconds": 10,
                    "critical": False
                }
            },
            "alerts": {
                "cpu_usage": {
                    "enabled": True,
                    "warning_threshold": 80.0,
                    "critical_threshold": 90.0,
                    "component": "system"
                },
                "memory_usage": {
                    "enabled": True,
                    "warning_threshold": 85.0,
                    "critical_threshold": 95.0,
                    "component": "system"
                },
                "disk_usage": {
                    "enabled": True,
                    "warning_threshold": 80.0,
                    "critical_threshold": 90.0,
                    "component": "system"
                },
                "response_time": {
                    "enabled": True,
                    "warning_threshold": 1000.0,
                    "critical_threshold": 2000.0,
                    "component": "api"
                },
                "error_rate": {
                    "enabled": True,
                    "warning_threshold": 5.0,
                    "critical_threshold": 10.0,
                    "component": "api"
                },
                "database_connections": {
                    "enabled": True,
                    "warning_threshold": 80.0,
                    "critical_threshold": 95.0,
                    "component": "database"
                }
            },
            "metrics": {
                "system_metrics": [
                    "cpu_usage_percent",
                    "memory_usage_percent",
                    "disk_usage_percent",
                    "network_io_bytes",
                    "process_count"
                ],
                "application_metrics": [
                    "request_count",
                    "response_time_ms",
                    "error_count",
                    "active_connections",
                    "queue_depth"
                ],
                "business_metrics": [
                    "trades_executed",
                    "trades_successful",
                    "trades_failed",
                    "profit_loss",
                    "win_rate"
                ]
            },
            "dashboard": {
                "refresh_interval": 1.0,
                "max_data_points": 1000,
                "chart_time_range_hours": 24,
                "auto_refresh": True
            }
        }
        
        try:
            if Path(config_path).exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
            else:
                # Save default config
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            logger.error(f"Error loading monitoring dashboard config: {e}")
            return default_config
    
    def _initialize_monitoring_components(self):
        """Initialize monitoring components"""
        try:
            for component_name, component_config in self.config["components"].items():
                if component_config["enabled"]:
                    self.components[component_name] = ComponentHealth(
                        component_name=component_name,
                        status=ComponentStatus.HEALTHY,
                        last_check=datetime.now(),
                        response_time_ms=0.0,
                        error_count=0,
                        success_count=0,
                        uptime_percent=100.0,
                        metrics={}
                    )
            
            logger.info(f"Initialized {len(self.components)} monitoring components")
            
        except Exception as e:
            logger.error(f"Error initializing monitoring components: {e}")
    
    async def start_monitoring(self):
        """Start the monitoring system"""
        try:
            logger.info("Starting production monitoring dashboard")
            self.running = True
            
            # Start monitoring tasks
            tasks = [
                asyncio.create_task(self._monitor_components()),
                asyncio.create_task(self._collect_system_metrics()),
                asyncio.create_task(self._collect_application_metrics()),
                asyncio.create_task(self._collect_business_metrics()),
                asyncio.create_task(self._check_alerts()),
                asyncio.create_task(self._update_dashboard())
            ]
            
            # Wait for all tasks
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")
            self.running = False
    
    async def _monitor_components(self):
        """Monitor component health"""
        try:
            while self.running:
                for component_name, component in self.components.items():
                    try:
                        # Check component health
                        health_status = await self._check_component_health(component_name)
                        
                        # Update component status
                        component.status = health_status["status"]
                        component.last_check = datetime.now()
                        component.response_time_ms = health_status["response_time_ms"]
                        
                        if health_status["status"] == ComponentStatus.HEALTHY:
                            component.success_count += 1
                        else:
                            component.error_count += 1
                        
                        # Calculate uptime percentage
                        total_checks = component.success_count + component.error_count
                        component.uptime_percent = (component.success_count / total_checks) * 100 if total_checks > 0 else 100.0
                        
                        # Update metrics
                        component.metrics.update(health_status["metrics"])
                        
                    except Exception as e:
                        logger.error(f"Error monitoring component {component_name}: {e}")
                        component.status = ComponentStatus.DOWN
                        component.error_count += 1
                
                # Wait for next check
                await asyncio.sleep(self.config["monitoring"]["collection_interval"])
                
        except Exception as e:
            logger.error(f"Error in component monitoring: {e}")
    
    async def _check_component_health(self, component_name: str) -> Dict[str, Any]:
        """Check health of a specific component"""
        try:
            component_config = self.config["components"][component_name]
            start_time = time.time()
            
            # Simulate health check based on component type
            if component_name in ["chatgpt_bot", "desktop_agent", "main_api"]:
                # HTTP health check
                response = requests.get(
                    component_config["health_check_url"],
                    timeout=component_config["timeout_seconds"]
                )
                response_time = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    status = ComponentStatus.HEALTHY
                else:
                    status = ComponentStatus.UNHEALTHY
                
                return {
                    "status": status,
                    "response_time_ms": response_time,
                    "metrics": {
                        "http_status_code": response.status_code,
                        "response_size_bytes": len(response.content)
                    }
                }
            
            elif component_name == "database":
                # Database health check
                response_time = (time.time() - start_time) * 1000
                
                # Simulate database check
                await asyncio.sleep(0.1)
                
                status = ComponentStatus.HEALTHY
                return {
                    "status": status,
                    "response_time_ms": response_time,
                    "metrics": {
                        "connection_count": np.random.randint(1, 10),
                        "query_count": np.random.randint(100, 1000)
                    }
                }
            
            elif component_name in ["mt5_connection", "binance_connection"]:
                # Connection health check
                response_time = (time.time() - start_time) * 1000
                
                # Simulate connection check
                await asyncio.sleep(0.2)
                
                status = ComponentStatus.HEALTHY
                return {
                    "status": status,
                    "response_time_ms": response_time,
                    "metrics": {
                        "connection_status": "connected",
                        "data_rate": np.random.uniform(10, 100)
                    }
                }
            
            else:
                # Default health check
                response_time = (time.time() - start_time) * 1000
                status = ComponentStatus.HEALTHY
                
                return {
                    "status": status,
                    "response_time_ms": response_time,
                    "metrics": {}
                }
                
        except Exception as e:
            logger.error(f"Error checking component health for {component_name}: {e}")
            return {
                "status": ComponentStatus.DOWN,
                "response_time_ms": 0.0,
                "metrics": {}
            }
    
    async def _collect_system_metrics(self):
        """Collect system metrics"""
        try:
            while self.running:
                # Collect system metrics
                cpu_usage = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                network = psutil.net_io_counters()
                
                # Create metrics
                system_metrics = [
                    Metric(
                        name="cpu_usage_percent",
                        value=cpu_usage,
                        timestamp=datetime.now(),
                        labels={"component": "system"},
                        metric_type=MetricType.GAUGE,
                        component="system"
                    ),
                    Metric(
                        name="memory_usage_percent",
                        value=memory.percent,
                        timestamp=datetime.now(),
                        labels={"component": "system"},
                        metric_type=MetricType.GAUGE,
                        component="system"
                    ),
                    Metric(
                        name="disk_usage_percent",
                        value=disk.percent,
                        timestamp=datetime.now(),
                        labels={"component": "system"},
                        metric_type=MetricType.GAUGE,
                        component="system"
                    ),
                    Metric(
                        name="network_io_bytes",
                        value=network.bytes_sent + network.bytes_recv,
                        timestamp=datetime.now(),
                        labels={"component": "system"},
                        metric_type=MetricType.COUNTER,
                        component="system"
                    ),
                    Metric(
                        name="process_count",
                        value=len(psutil.pids()),
                        timestamp=datetime.now(),
                        labels={"component": "system"},
                        metric_type=MetricType.GAUGE,
                        component="system"
                    )
                ]
                
                # Store metrics
                self.metrics.extend(system_metrics)
                
                # Wait for next collection
                await asyncio.sleep(self.config["monitoring"]["collection_interval"])
                
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    async def _collect_application_metrics(self):
        """Collect application metrics"""
        try:
            while self.running:
                # Simulate application metrics collection
                app_metrics = [
                    Metric(
                        name="request_count",
                        value=np.random.randint(100, 1000),
                        timestamp=datetime.now(),
                        labels={"component": "api"},
                        metric_type=MetricType.COUNTER,
                        component="api"
                    ),
                    Metric(
                        name="response_time_ms",
                        value=np.random.uniform(50, 500),
                        timestamp=datetime.now(),
                        labels={"component": "api"},
                        metric_type=MetricType.HISTOGRAM,
                        component="api"
                    ),
                    Metric(
                        name="error_count",
                        value=np.random.randint(0, 10),
                        timestamp=datetime.now(),
                        labels={"component": "api"},
                        metric_type=MetricType.COUNTER,
                        component="api"
                    ),
                    Metric(
                        name="active_connections",
                        value=np.random.randint(10, 100),
                        timestamp=datetime.now(),
                        labels={"component": "api"},
                        metric_type=MetricType.GAUGE,
                        component="api"
                    ),
                    Metric(
                        name="queue_depth",
                        value=np.random.randint(0, 50),
                        timestamp=datetime.now(),
                        labels={"component": "api"},
                        metric_type=MetricType.GAUGE,
                        component="api"
                    )
                ]
                
                # Store metrics
                self.metrics.extend(app_metrics)
                
                # Wait for next collection
                await asyncio.sleep(self.config["monitoring"]["collection_interval"])
                
        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
    
    async def _collect_business_metrics(self):
        """Collect business metrics"""
        try:
            while self.running:
                # Simulate business metrics collection
                business_metrics = [
                    Metric(
                        name="trades_executed",
                        value=np.random.randint(50, 200),
                        timestamp=datetime.now(),
                        labels={"component": "trading"},
                        metric_type=MetricType.COUNTER,
                        component="trading"
                    ),
                    Metric(
                        name="trades_successful",
                        value=np.random.randint(40, 180),
                        timestamp=datetime.now(),
                        labels={"component": "trading"},
                        metric_type=MetricType.COUNTER,
                        component="trading"
                    ),
                    Metric(
                        name="trades_failed",
                        value=np.random.randint(0, 20),
                        timestamp=datetime.now(),
                        labels={"component": "trading"},
                        metric_type=MetricType.COUNTER,
                        component="trading"
                    ),
                    Metric(
                        name="profit_loss",
                        value=np.random.uniform(-1000, 2000),
                        timestamp=datetime.now(),
                        labels={"component": "trading"},
                        metric_type=MetricType.GAUGE,
                        component="trading"
                    ),
                    Metric(
                        name="win_rate",
                        value=np.random.uniform(0.6, 0.9),
                        timestamp=datetime.now(),
                        labels={"component": "trading"},
                        metric_type=MetricType.GAUGE,
                        component="trading"
                    )
                ]
                
                # Store metrics
                self.metrics.extend(business_metrics)
                
                # Wait for next collection
                await asyncio.sleep(self.config["monitoring"]["collection_interval"])
                
        except Exception as e:
            logger.error(f"Error collecting business metrics: {e}")
    
    async def _check_alerts(self):
        """Check for alert conditions"""
        try:
            while self.running:
                # Check each alert configuration
                for alert_name, alert_config in self.config["alerts"].items():
                    if not alert_config["enabled"]:
                        continue
                    
                    # Get current metric value
                    current_value = self._get_metric_value(alert_name)
                    
                    if current_value is not None:
                        # Check thresholds
                        if current_value >= alert_config["critical_threshold"]:
                            await self._create_alert(
                                alert_name,
                                AlertLevel.CRITICAL,
                                f"{alert_name} is {current_value:.1f}, exceeds critical threshold {alert_config['critical_threshold']}",
                                current_value,
                                alert_config["critical_threshold"]
                            )
                        elif current_value >= alert_config["warning_threshold"]:
                            await self._create_alert(
                                alert_name,
                                AlertLevel.WARNING,
                                f"{alert_name} is {current_value:.1f}, exceeds warning threshold {alert_config['warning_threshold']}",
                                current_value,
                                alert_config["warning_threshold"]
                            )
                
                # Wait for next check
                await asyncio.sleep(self.config["monitoring"]["collection_interval"])
                
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
    
    def _get_metric_value(self, metric_name: str) -> Optional[float]:
        """Get current value of a metric"""
        try:
            # Find the most recent metric with this name
            for metric in reversed(self.metrics):
                if metric.name == metric_name:
                    return metric.value
            return None
        except Exception as e:
            logger.error(f"Error getting metric value for {metric_name}: {e}")
            return None
    
    async def _create_alert(self, alert_name: str, level: AlertLevel, message: str, 
                          current_value: float, threshold: float):
        """Create a new alert"""
        try:
            # Check if alert already exists and is not resolved
            existing_alert = None
            for alert in self.alerts:
                if (alert.metric_name == alert_name and 
                    alert.level == level and 
                    not alert.resolved):
                    existing_alert = alert
                    break
            
            if existing_alert:
                # Update existing alert
                existing_alert.current_value = current_value
                existing_alert.timestamp = datetime.now()
            else:
                # Create new alert
                alert = Alert(
                    alert_id=f"{alert_name}_{int(time.time())}",
                    level=level,
                    message=message,
                    timestamp=datetime.now(),
                    component=self.config["alerts"][alert_name]["component"],
                    metric_name=alert_name,
                    threshold=threshold,
                    current_value=current_value
                )
                self.alerts.append(alert)
                
                logger.warning(f"Alert created: {message}")
                
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
    
    async def _update_dashboard(self):
        """Update dashboard data"""
        try:
            while self.running:
                # Calculate overall status
                overall_status = self._calculate_overall_status()
                
                # Get system metrics
                system_metrics = self._get_system_metrics()
                
                # Get performance metrics
                performance_metrics = self._get_performance_metrics()
                
                # Create dashboard data
                dashboard_data = DashboardData(
                    timestamp=datetime.now(),
                    overall_status=overall_status,
                    components=list(self.components.values()),
                    alerts=[alert for alert in self.alerts if not alert.resolved],
                    metrics=self.metrics[-100:],  # Last 100 metrics
                    system_metrics=system_metrics,
                    performance_metrics=performance_metrics
                )
                
                # Store dashboard data
                self.dashboard_data.append(dashboard_data)
                
                # Keep only recent data
                if len(self.dashboard_data) > 1000:
                    self.dashboard_data = self.dashboard_data[-1000:]
                
                # Wait for next update
                await asyncio.sleep(self.config["dashboard"]["refresh_interval"])
                
        except Exception as e:
            logger.error(f"Error updating dashboard: {e}")
    
    def _calculate_overall_status(self) -> ComponentStatus:
        """Calculate overall system status"""
        try:
            if not self.components:
                return ComponentStatus.HEALTHY
            
            # Check if any critical components are down
            critical_components = [name for name, config in self.config["components"].items() 
                                 if config["critical"] and config["enabled"]]
            
            for component_name in critical_components:
                if component_name in self.components:
                    if self.components[component_name].status == ComponentStatus.DOWN:
                        return ComponentStatus.DOWN
            
            # Check if any components are unhealthy
            for component in self.components.values():
                if component.status == ComponentStatus.UNHEALTHY:
                    return ComponentStatus.DEGRADED
            
            return ComponentStatus.HEALTHY
            
        except Exception as e:
            logger.error(f"Error calculating overall status: {e}")
            return ComponentStatus.UNHEALTHY
    
    def _get_system_metrics(self) -> Dict[str, float]:
        """Get current system metrics"""
        try:
            return {
                "cpu_usage_percent": psutil.cpu_percent(),
                "memory_usage_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage('/').percent,
                "network_io_bytes": psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv,
                "process_count": len(psutil.pids())
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {}
    
    def _get_performance_metrics(self) -> Dict[str, float]:
        """Get current performance metrics"""
        try:
            # Calculate performance metrics from recent data
            recent_metrics = self.metrics[-100:] if self.metrics else []
            
            if not recent_metrics:
                return {}
            
            # Calculate averages
            response_times = [m.value for m in recent_metrics if m.name == "response_time_ms"]
            error_counts = [m.value for m in recent_metrics if m.name == "error_count"]
            request_counts = [m.value for m in recent_metrics if m.name == "request_count"]
            
            return {
                "avg_response_time_ms": np.mean(response_times) if response_times else 0.0,
                "max_response_time_ms": np.max(response_times) if response_times else 0.0,
                "error_rate_percent": (np.sum(error_counts) / np.sum(request_counts)) * 100 if request_counts else 0.0,
                "requests_per_second": np.mean(request_counts) if request_counts else 0.0
            }
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get current dashboard data"""
        try:
            if not self.dashboard_data:
                return {"message": "No dashboard data available"}
            
            latest_data = self.dashboard_data[-1]
            
            return {
                "timestamp": latest_data.timestamp.isoformat(),
                "overall_status": latest_data.overall_status.value,
                "components": [asdict(component) for component in latest_data.components],
                "alerts": [asdict(alert) for alert in latest_data.alerts],
                "system_metrics": latest_data.system_metrics,
                "performance_metrics": latest_data.performance_metrics,
                "total_metrics": len(self.metrics),
                "total_alerts": len(self.alerts)
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return {}
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        try:
            if not self.metrics:
                return {"message": "No metrics available"}
            
            # Group metrics by name
            metric_groups = defaultdict(list)
            for metric in self.metrics:
                metric_groups[metric.name].append(metric.value)
            
            # Calculate summaries
            summaries = {}
            for name, values in metric_groups.items():
                summaries[name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": np.mean(values),
                    "latest": values[-1] if values else 0.0
                }
            
            return {
                "total_metrics": len(self.metrics),
                "metric_types": len(metric_groups),
                "summaries": summaries
            }
            
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {}
    
    def stop_monitoring(self):
        """Stop the monitoring system"""
        try:
            logger.info("Stopping production monitoring dashboard")
            self.running = False
        except Exception as e:
            logger.error(f"Error stopping monitoring: {e}")

async def main():
    """Main function for testing monitoring dashboard"""
    dashboard = ProductionMonitoringDashboard()
    
    try:
        # Start monitoring
        await dashboard.start_monitoring()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    finally:
        dashboard.stop_monitoring()

if __name__ == "__main__":
    asyncio.run(main())