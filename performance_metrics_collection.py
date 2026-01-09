#!/usr/bin/env python3
"""
Performance Metrics Collection System for TelegramMoneyBot v8.0
Comprehensive performance metrics collection and analysis system
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
from collections import defaultdict, deque
import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MetricCategory(Enum):
    """Metric categories"""
    SYSTEM = "system"
    APPLICATION = "application"
    BUSINESS = "business"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"

class MetricType(Enum):
    """Metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"

class PerformanceLevel(Enum):
    """Performance levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"

@dataclass
class PerformanceMetric:
    """Performance metric data structure"""
    metric_id: str
    name: str
    value: float
    timestamp: datetime
    category: MetricCategory
    metric_type: MetricType
    component: str
    labels: Dict[str, str]
    unit: str
    description: str

@dataclass
class PerformanceAnalysis:
    """Performance analysis result"""
    analysis_id: str
    timestamp: datetime
    time_range: Tuple[datetime, datetime]
    total_metrics: int
    performance_level: PerformanceLevel
    system_metrics: Dict[str, float]
    application_metrics: Dict[str, float]
    business_metrics: Dict[str, float]
    performance_metrics: Dict[str, float]
    availability_metrics: Dict[str, float]
    bottlenecks: List[str]
    recommendations: List[str]
    trends: Dict[str, Any]

@dataclass
class PerformanceThreshold:
    """Performance threshold configuration"""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    unit: str
    description: str

class PerformanceMetricsCollection:
    """Performance metrics collection system"""
    
    def __init__(self, config_path: str = "performance_metrics_config.json"):
        self.config = self._load_config(config_path)
        self.metrics: List[PerformanceMetric] = []
        self.analyses: List[PerformanceAnalysis] = []
        self.thresholds: Dict[str, PerformanceThreshold] = {}
        self.running = False
        
        # Initialize performance thresholds
        self._initialize_thresholds()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load performance metrics configuration"""
        default_config = {
            "collection": {
                "interval_seconds": 10.0,
                "retention_days": 30,
                "batch_size": 1000,
                "compression_enabled": True
            },
            "metrics": {
                "system_metrics": {
                    "enabled": True,
                    "cpu_usage": True,
                    "memory_usage": True,
                    "disk_usage": True,
                    "network_io": True,
                    "process_count": True
                },
                "application_metrics": {
                    "enabled": True,
                    "response_time": True,
                    "throughput": True,
                    "error_rate": True,
                    "active_connections": True,
                    "queue_depth": True
                },
                "business_metrics": {
                    "enabled": True,
                    "trades_executed": True,
                    "trades_successful": True,
                    "profit_loss": True,
                    "win_rate": True,
                    "drawdown": True
                },
                "performance_metrics": {
                    "enabled": True,
                    "latency": True,
                    "throughput": True,
                    "efficiency": True,
                    "utilization": True,
                    "scalability": True
                },
                "availability_metrics": {
                    "enabled": True,
                    "uptime": True,
                    "downtime": True,
                    "recovery_time": True,
                    "failover_time": True,
                    "reliability": True
                }
            },
            "thresholds": {
                "cpu_usage": {
                    "warning": 80.0,
                    "critical": 90.0,
                    "unit": "percent"
                },
                "memory_usage": {
                    "warning": 85.0,
                    "critical": 95.0,
                    "unit": "percent"
                },
                "disk_usage": {
                    "warning": 80.0,
                    "critical": 90.0,
                    "unit": "percent"
                },
                "response_time": {
                    "warning": 1000.0,
                    "critical": 2000.0,
                    "unit": "milliseconds"
                },
                "error_rate": {
                    "warning": 5.0,
                    "critical": 10.0,
                    "unit": "percent"
                },
                "latency": {
                    "warning": 200.0,
                    "critical": 500.0,
                    "unit": "milliseconds"
                }
            },
            "analysis": {
                "analysis_interval": 300.0,  # 5 minutes
                "trend_detection": True,
                "anomaly_detection": True,
                "bottleneck_detection": True,
                "performance_scoring": True
            },
            "monitoring": {
                "alert_on_threshold_breach": True,
                "performance_degradation_detection": True,
                "capacity_planning": True,
                "optimization_recommendations": True
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
                return default_config
            else:
                # Save default config
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            logger.error(f"Error loading performance metrics config: {e}")
            return default_config
    
    def _initialize_thresholds(self):
        """Initialize performance thresholds"""
        try:
            for metric_name, threshold_config in self.config["thresholds"].items():
                threshold = PerformanceThreshold(
                    metric_name=metric_name,
                    warning_threshold=threshold_config["warning"],
                    critical_threshold=threshold_config["critical"],
                    unit=threshold_config["unit"],
                    description=f"Performance threshold for {metric_name}"
                )
                self.thresholds[metric_name] = threshold
            
            logger.info(f"Initialized {len(self.thresholds)} performance thresholds")
            
        except Exception as e:
            logger.error(f"Error initializing performance thresholds: {e}")
    
    async def start_metrics_collection(self):
        """Start the performance metrics collection system"""
        try:
            logger.info("Starting performance metrics collection system")
            self.running = True
            
            # Start collection tasks
            tasks = [
                asyncio.create_task(self._collect_system_metrics()),
                asyncio.create_task(self._collect_application_metrics()),
                asyncio.create_task(self._collect_business_metrics()),
                asyncio.create_task(self._collect_performance_metrics()),
                asyncio.create_task(self._collect_availability_metrics()),
                asyncio.create_task(self._analyze_performance()),
                asyncio.create_task(self._cleanup_old_metrics())
            ]
            
            # Wait for all tasks
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"Error starting metrics collection: {e}")
            self.running = False
    
    async def _collect_system_metrics(self):
        """Collect system metrics"""
        try:
            while self.running:
                if not self.config["metrics"]["system_metrics"]["enabled"]:
                    await asyncio.sleep(self.config["collection"]["interval_seconds"])
                    continue
                
                # Collect system metrics
                cpu_usage = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                network = psutil.net_io_counters()
                
                # Create system metrics
                system_metrics = [
                    PerformanceMetric(
                        metric_id=f"cpu_usage_{int(time.time())}",
                        name="cpu_usage",
                        value=cpu_usage,
                        timestamp=datetime.now(),
                        category=MetricCategory.SYSTEM,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"host": "localhost"},
                        unit="percent",
                        description="CPU usage percentage"
                    ),
                    PerformanceMetric(
                        metric_id=f"memory_usage_{int(time.time())}",
                        name="memory_usage",
                        value=memory.percent,
                        timestamp=datetime.now(),
                        category=MetricCategory.SYSTEM,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"host": "localhost"},
                        unit="percent",
                        description="Memory usage percentage"
                    ),
                    PerformanceMetric(
                        metric_id=f"disk_usage_{int(time.time())}",
                        name="disk_usage",
                        value=disk.percent,
                        timestamp=datetime.now(),
                        category=MetricCategory.SYSTEM,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"host": "localhost"},
                        unit="percent",
                        description="Disk usage percentage"
                    ),
                    PerformanceMetric(
                        metric_id=f"network_io_{int(time.time())}",
                        name="network_io",
                        value=network.bytes_sent + network.bytes_recv,
                        timestamp=datetime.now(),
                        category=MetricCategory.SYSTEM,
                        metric_type=MetricType.COUNTER,
                        component="system",
                        labels={"host": "localhost"},
                        unit="bytes",
                        description="Network I/O bytes"
                    ),
                    PerformanceMetric(
                        metric_id=f"process_count_{int(time.time())}",
                        name="process_count",
                        value=len(psutil.pids()),
                        timestamp=datetime.now(),
                        category=MetricCategory.SYSTEM,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"host": "localhost"},
                        unit="count",
                        description="Number of running processes"
                    )
                ]
                
                # Store metrics
                self.metrics.extend(system_metrics)
                
                # Wait for next collection
                await asyncio.sleep(self.config["collection"]["interval_seconds"])
                
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    async def _collect_application_metrics(self):
        """Collect application metrics"""
        try:
            while self.running:
                if not self.config["metrics"]["application_metrics"]["enabled"]:
                    await asyncio.sleep(self.config["collection"]["interval_seconds"])
                    continue
                
                # Simulate application metrics collection
                app_metrics = [
                    PerformanceMetric(
                        metric_id=f"response_time_{int(time.time())}",
                        name="response_time",
                        value=np.random.uniform(50, 500),
                        timestamp=datetime.now(),
                        category=MetricCategory.APPLICATION,
                        metric_type=MetricType.HISTOGRAM,
                        component="api",
                        labels={"endpoint": "trading"},
                        unit="milliseconds",
                        description="API response time"
                    ),
                    PerformanceMetric(
                        metric_id=f"throughput_{int(time.time())}",
                        name="throughput",
                        value=np.random.uniform(10, 100),
                        timestamp=datetime.now(),
                        category=MetricCategory.APPLICATION,
                        metric_type=MetricType.GAUGE,
                        component="api",
                        labels={"endpoint": "trading"},
                        unit="requests_per_second",
                        description="API throughput"
                    ),
                    PerformanceMetric(
                        metric_id=f"error_rate_{int(time.time())}",
                        name="error_rate",
                        value=np.random.uniform(0, 5),
                        timestamp=datetime.now(),
                        category=MetricCategory.APPLICATION,
                        metric_type=MetricType.GAUGE,
                        component="api",
                        labels={"endpoint": "trading"},
                        unit="percent",
                        description="API error rate"
                    ),
                    PerformanceMetric(
                        metric_id=f"active_connections_{int(time.time())}",
                        name="active_connections",
                        value=np.random.randint(10, 100),
                        timestamp=datetime.now(),
                        category=MetricCategory.APPLICATION,
                        metric_type=MetricType.GAUGE,
                        component="api",
                        labels={"endpoint": "trading"},
                        unit="count",
                        description="Active connections"
                    ),
                    PerformanceMetric(
                        metric_id=f"queue_depth_{int(time.time())}",
                        name="queue_depth",
                        value=np.random.randint(0, 50),
                        timestamp=datetime.now(),
                        category=MetricCategory.APPLICATION,
                        metric_type=MetricType.GAUGE,
                        component="api",
                        labels={"endpoint": "trading"},
                        unit="count",
                        description="Queue depth"
                    )
                ]
                
                # Store metrics
                self.metrics.extend(app_metrics)
                
                # Wait for next collection
                await asyncio.sleep(self.config["collection"]["interval_seconds"])
                
        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
    
    async def _collect_business_metrics(self):
        """Collect business metrics"""
        try:
            while self.running:
                if not self.config["metrics"]["business_metrics"]["enabled"]:
                    await asyncio.sleep(self.config["collection"]["interval_seconds"])
                    continue
                
                # Simulate business metrics collection
                business_metrics = [
                    PerformanceMetric(
                        metric_id=f"trades_executed_{int(time.time())}",
                        name="trades_executed",
                        value=np.random.randint(50, 200),
                        timestamp=datetime.now(),
                        category=MetricCategory.BUSINESS,
                        metric_type=MetricType.COUNTER,
                        component="trading",
                        labels={"symbol": "BTCUSDc"},
                        unit="count",
                        description="Number of trades executed"
                    ),
                    PerformanceMetric(
                        metric_id=f"trades_successful_{int(time.time())}",
                        name="trades_successful",
                        value=np.random.randint(40, 180),
                        timestamp=datetime.now(),
                        category=MetricCategory.BUSINESS,
                        metric_type=MetricType.COUNTER,
                        component="trading",
                        labels={"symbol": "BTCUSDc"},
                        unit="count",
                        description="Number of successful trades"
                    ),
                    PerformanceMetric(
                        metric_id=f"profit_loss_{int(time.time())}",
                        name="profit_loss",
                        value=np.random.uniform(-1000, 2000),
                        timestamp=datetime.now(),
                        category=MetricCategory.BUSINESS,
                        metric_type=MetricType.GAUGE,
                        component="trading",
                        labels={"symbol": "BTCUSDc"},
                        unit="dollars",
                        description="Profit/Loss"
                    ),
                    PerformanceMetric(
                        metric_id=f"win_rate_{int(time.time())}",
                        name="win_rate",
                        value=np.random.uniform(0.6, 0.9),
                        timestamp=datetime.now(),
                        category=MetricCategory.BUSINESS,
                        metric_type=MetricType.GAUGE,
                        component="trading",
                        labels={"symbol": "BTCUSDc"},
                        unit="ratio",
                        description="Win rate"
                    ),
                    PerformanceMetric(
                        metric_id=f"drawdown_{int(time.time())}",
                        name="drawdown",
                        value=np.random.uniform(0, 0.1),
                        timestamp=datetime.now(),
                        category=MetricCategory.BUSINESS,
                        metric_type=MetricType.GAUGE,
                        component="trading",
                        labels={"symbol": "BTCUSDc"},
                        unit="ratio",
                        description="Maximum drawdown"
                    )
                ]
                
                # Store metrics
                self.metrics.extend(business_metrics)
                
                # Wait for next collection
                await asyncio.sleep(self.config["collection"]["interval_seconds"])
                
        except Exception as e:
            logger.error(f"Error collecting business metrics: {e}")
    
    async def _collect_performance_metrics(self):
        """Collect performance metrics"""
        try:
            while self.running:
                if not self.config["metrics"]["performance_metrics"]["enabled"]:
                    await asyncio.sleep(self.config["collection"]["interval_seconds"])
                    continue
                
                # Simulate performance metrics collection
                perf_metrics = [
                    PerformanceMetric(
                        metric_id=f"latency_{int(time.time())}",
                        name="latency",
                        value=np.random.uniform(10, 200),
                        timestamp=datetime.now(),
                        category=MetricCategory.PERFORMANCE,
                        metric_type=MetricType.HISTOGRAM,
                        component="system",
                        labels={"stage": "processing"},
                        unit="milliseconds",
                        description="System latency"
                    ),
                    PerformanceMetric(
                        metric_id=f"throughput_{int(time.time())}",
                        name="throughput",
                        value=np.random.uniform(50, 200),
                        timestamp=datetime.now(),
                        category=MetricCategory.PERFORMANCE,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"stage": "processing"},
                        unit="operations_per_second",
                        description="System throughput"
                    ),
                    PerformanceMetric(
                        metric_id=f"efficiency_{int(time.time())}",
                        name="efficiency",
                        value=np.random.uniform(0.7, 1.0),
                        timestamp=datetime.now(),
                        category=MetricCategory.PERFORMANCE,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"stage": "processing"},
                        unit="ratio",
                        description="System efficiency"
                    ),
                    PerformanceMetric(
                        metric_id=f"utilization_{int(time.time())}",
                        name="utilization",
                        value=np.random.uniform(0.5, 0.9),
                        timestamp=datetime.now(),
                        category=MetricCategory.PERFORMANCE,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"stage": "processing"},
                        unit="ratio",
                        description="Resource utilization"
                    ),
                    PerformanceMetric(
                        metric_id=f"scalability_{int(time.time())}",
                        name="scalability",
                        value=np.random.uniform(0.8, 1.0),
                        timestamp=datetime.now(),
                        category=MetricCategory.PERFORMANCE,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"stage": "processing"},
                        unit="ratio",
                        description="System scalability"
                    )
                ]
                
                # Store metrics
                self.metrics.extend(perf_metrics)
                
                # Wait for next collection
                await asyncio.sleep(self.config["collection"]["interval_seconds"])
                
        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
    
    async def _collect_availability_metrics(self):
        """Collect availability metrics"""
        try:
            while self.running:
                if not self.config["metrics"]["availability_metrics"]["enabled"]:
                    await asyncio.sleep(self.config["collection"]["interval_seconds"])
                    continue
                
                # Simulate availability metrics collection
                avail_metrics = [
                    PerformanceMetric(
                        metric_id=f"uptime_{int(time.time())}",
                        name="uptime",
                        value=np.random.uniform(0.95, 1.0),
                        timestamp=datetime.now(),
                        category=MetricCategory.AVAILABILITY,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"service": "trading"},
                        unit="ratio",
                        description="System uptime"
                    ),
                    PerformanceMetric(
                        metric_id=f"downtime_{int(time.time())}",
                        name="downtime",
                        value=np.random.uniform(0, 0.05),
                        timestamp=datetime.now(),
                        category=MetricCategory.AVAILABILITY,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"service": "trading"},
                        unit="ratio",
                        description="System downtime"
                    ),
                    PerformanceMetric(
                        metric_id=f"recovery_time_{int(time.time())}",
                        name="recovery_time",
                        value=np.random.uniform(10, 300),
                        timestamp=datetime.now(),
                        category=MetricCategory.AVAILABILITY,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"service": "trading"},
                        unit="seconds",
                        description="Recovery time"
                    ),
                    PerformanceMetric(
                        metric_id=f"failover_time_{int(time.time())}",
                        name="failover_time",
                        value=np.random.uniform(5, 60),
                        timestamp=datetime.now(),
                        category=MetricCategory.AVAILABILITY,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"service": "trading"},
                        unit="seconds",
                        description="Failover time"
                    ),
                    PerformanceMetric(
                        metric_id=f"reliability_{int(time.time())}",
                        name="reliability",
                        value=np.random.uniform(0.9, 1.0),
                        timestamp=datetime.now(),
                        category=MetricCategory.AVAILABILITY,
                        metric_type=MetricType.GAUGE,
                        component="system",
                        labels={"service": "trading"},
                        unit="ratio",
                        description="System reliability"
                    )
                ]
                
                # Store metrics
                self.metrics.extend(avail_metrics)
                
                # Wait for next collection
                await asyncio.sleep(self.config["collection"]["interval_seconds"])
                
        except Exception as e:
            logger.error(f"Error collecting availability metrics: {e}")
    
    async def _analyze_performance(self):
        """Analyze performance metrics"""
        try:
            while self.running:
                # Get recent metrics
                recent_metrics = self._get_recent_metrics(self.config["analysis"]["analysis_interval"])
                
                if not recent_metrics:
                    await asyncio.sleep(self.config["analysis"]["analysis_interval"])
                    continue
                
                # Analyze performance
                analysis = await self._perform_performance_analysis(recent_metrics)
                
                # Store analysis
                self.analyses.append(analysis)
                
                # Wait for next analysis
                await asyncio.sleep(self.config["analysis"]["analysis_interval"])
                
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
    
    def _get_recent_metrics(self, time_window_seconds: float) -> List[PerformanceMetric]:
        """Get recent metrics within time window"""
        try:
            cutoff_time = datetime.now() - timedelta(seconds=time_window_seconds)
            return [metric for metric in self.metrics if metric.timestamp >= cutoff_time]
        except Exception as e:
            logger.error(f"Error getting recent metrics: {e}")
            return []
    
    async def _perform_performance_analysis(self, metrics: List[PerformanceMetric]) -> PerformanceAnalysis:
        """Perform performance analysis"""
        try:
            # Group metrics by category
            system_metrics = self._group_metrics_by_category(metrics, MetricCategory.SYSTEM)
            application_metrics = self._group_metrics_by_category(metrics, MetricCategory.APPLICATION)
            business_metrics = self._group_metrics_by_category(metrics, MetricCategory.BUSINESS)
            performance_metrics = self._group_metrics_by_category(metrics, MetricCategory.PERFORMANCE)
            availability_metrics = self._group_metrics_by_category(metrics, MetricCategory.AVAILABILITY)
            
            # Calculate performance level
            performance_level = self._calculate_performance_level(metrics)
            
            # Detect bottlenecks
            bottlenecks = self._detect_bottlenecks(metrics)
            
            # Analyze trends
            trends = self._analyze_trends(metrics)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(metrics, performance_level, bottlenecks)
            
            # Create analysis result
            analysis = PerformanceAnalysis(
                analysis_id=f"performance_analysis_{int(time.time())}",
                timestamp=datetime.now(),
                time_range=(metrics[0].timestamp, metrics[-1].timestamp),
                total_metrics=len(metrics),
                performance_level=performance_level,
                system_metrics=system_metrics,
                application_metrics=application_metrics,
                business_metrics=business_metrics,
                performance_metrics=performance_metrics,
                availability_metrics=availability_metrics,
                bottlenecks=bottlenecks,
                recommendations=recommendations,
                trends=trends
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error performing performance analysis: {e}")
            return PerformanceAnalysis(
                analysis_id=f"performance_analysis_{int(time.time())}",
                timestamp=datetime.now(),
                time_range=(datetime.now(), datetime.now()),
                total_metrics=0,
                performance_level=PerformanceLevel.CRITICAL,
                system_metrics={},
                application_metrics={},
                business_metrics={},
                performance_metrics={},
                availability_metrics={},
                bottlenecks=[],
                recommendations=[],
                trends={}
            )
    
    def _group_metrics_by_category(self, metrics: List[PerformanceMetric], category: MetricCategory) -> Dict[str, float]:
        """Group metrics by category"""
        try:
            category_metrics = [m for m in metrics if m.category == category]
            grouped = {}
            
            for metric in category_metrics:
                if metric.name in grouped:
                    grouped[metric.name] = (grouped[metric.name] + metric.value) / 2
                else:
                    grouped[metric.name] = metric.value
            
            return grouped
            
        except Exception as e:
            logger.error(f"Error grouping metrics by category: {e}")
            return {}
    
    def _calculate_performance_level(self, metrics: List[PerformanceMetric]) -> PerformanceLevel:
        """Calculate overall performance level"""
        try:
            if not metrics:
                return PerformanceLevel.CRITICAL
            
            # Check thresholds
            critical_count = 0
            warning_count = 0
            
            for metric in metrics:
                if metric.name in self.thresholds:
                    threshold = self.thresholds[metric.name]
                    
                    if metric.value >= threshold.critical_threshold:
                        critical_count += 1
                    elif metric.value >= threshold.warning_threshold:
                        warning_count += 1
            
            # Determine performance level
            if critical_count > 0:
                return PerformanceLevel.CRITICAL
            elif warning_count > 2:
                return PerformanceLevel.POOR
            elif warning_count > 0:
                return PerformanceLevel.FAIR
            else:
                return PerformanceLevel.EXCELLENT
                
        except Exception as e:
            logger.error(f"Error calculating performance level: {e}")
            return PerformanceLevel.CRITICAL
    
    def _detect_bottlenecks(self, metrics: List[PerformanceMetric]) -> List[str]:
        """Detect performance bottlenecks"""
        try:
            bottlenecks = []
            
            # Check for high CPU usage
            cpu_metrics = [m for m in metrics if m.name == "cpu_usage"]
            if cpu_metrics and np.mean([m.value for m in cpu_metrics]) > 90:
                bottlenecks.append("High CPU usage detected")
            
            # Check for high memory usage
            memory_metrics = [m for m in metrics if m.name == "memory_usage"]
            if memory_metrics and np.mean([m.value for m in memory_metrics]) > 90:
                bottlenecks.append("High memory usage detected")
            
            # Check for high response time
            response_metrics = [m for m in metrics if m.name == "response_time"]
            if response_metrics and np.mean([m.value for m in response_metrics]) > 1000:
                bottlenecks.append("High response time detected")
            
            # Check for high error rate
            error_metrics = [m for m in metrics if m.name == "error_rate"]
            if error_metrics and np.mean([m.value for m in error_metrics]) > 5:
                bottlenecks.append("High error rate detected")
            
            return bottlenecks
            
        except Exception as e:
            logger.error(f"Error detecting bottlenecks: {e}")
            return []
    
    def _analyze_trends(self, metrics: List[PerformanceMetric]) -> Dict[str, Any]:
        """Analyze performance trends"""
        try:
            if not metrics:
                return {}
            
            # Group metrics by name
            metric_groups = defaultdict(list)
            for metric in metrics:
                metric_groups[metric.name].append(metric.value)
            
            # Calculate trends
            trends = {}
            for name, values in metric_groups.items():
                if len(values) > 1:
                    # Calculate trend direction
                    trend_direction = "stable"
                    if len(values) >= 2:
                        first_half = np.mean(values[:len(values)//2])
                        second_half = np.mean(values[len(values)//2:])
                        
                        if second_half > first_half * 1.1:
                            trend_direction = "increasing"
                        elif second_half < first_half * 0.9:
                            trend_direction = "decreasing"
                    
                    trends[name] = {
                        "direction": trend_direction,
                        "avg_value": np.mean(values),
                        "min_value": np.min(values),
                        "max_value": np.max(values),
                        "std_value": np.std(values)
                    }
            
            return trends
            
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            return {}
    
    def _generate_recommendations(self, metrics: List[PerformanceMetric], 
                                performance_level: PerformanceLevel, 
                                bottlenecks: List[str]) -> List[str]:
        """Generate performance recommendations"""
        try:
            recommendations = []
            
            if performance_level == PerformanceLevel.CRITICAL:
                recommendations.append("Critical performance issues detected. Immediate attention required.")
            
            if "High CPU usage detected" in bottlenecks:
                recommendations.append("Consider CPU optimization or horizontal scaling")
            
            if "High memory usage detected" in bottlenecks:
                recommendations.append("Consider memory optimization or increasing RAM")
            
            if "High response time detected" in bottlenecks:
                recommendations.append("Consider database optimization or caching")
            
            if "High error rate detected" in bottlenecks:
                recommendations.append("Investigate and fix error sources")
            
            # Check for specific metric issues
            for metric in metrics:
                if metric.name in self.thresholds:
                    threshold = self.thresholds[metric.name]
                    if metric.value >= threshold.warning_threshold:
                        recommendations.append(f"Monitor {metric.name} - currently {metric.value:.2f} {threshold.unit}")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []
    
    async def _cleanup_old_metrics(self):
        """Clean up old metrics"""
        try:
            while self.running:
                # Remove metrics older than retention period
                retention_days = self.config["collection"]["retention_days"]
                cutoff_date = datetime.now() - timedelta(days=retention_days)
                
                # Clean up metrics
                self.metrics = [metric for metric in self.metrics if metric.timestamp > cutoff_date]
                
                # Clean up analyses
                self.analyses = [analysis for analysis in self.analyses if analysis.timestamp > cutoff_date]
                
                # Wait for next cleanup
                await asyncio.sleep(3600)  # Run cleanup every hour
                
        except Exception as e:
            logger.error(f"Error cleaning up old metrics: {e}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary"""
        try:
            if not self.analyses:
                return {"message": "No performance analyses available"}
            
            # Get latest analysis
            latest_analysis = self.analyses[-1]
            
            # Calculate totals
            total_metrics = len(self.metrics)
            total_analyses = len(self.analyses)
            
            return {
                "total_metrics": total_metrics,
                "total_analyses": total_analyses,
                "latest_analysis": asdict(latest_analysis),
                "performance_level": latest_analysis.performance_level.value,
                "bottlenecks": latest_analysis.bottlenecks,
                "recommendations": latest_analysis.recommendations
            }
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {}
    
    def stop_metrics_collection(self):
        """Stop the performance metrics collection system"""
        try:
            logger.info("Stopping performance metrics collection system")
            self.running = False
        except Exception as e:
            logger.error(f"Error stopping metrics collection: {e}")

async def main():
    """Main function for testing performance metrics collection"""
    metrics_collector = PerformanceMetricsCollection()
    
    try:
        # Start metrics collection
        await metrics_collector.start_metrics_collection()
    except KeyboardInterrupt:
        logger.info("Performance metrics collection stopped by user")
    finally:
        metrics_collector.stop_metrics_collection()

if __name__ == "__main__":
    asyncio.run(main())
