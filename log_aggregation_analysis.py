#!/usr/bin/env python3
"""
Log Aggregation and Analysis System for TelegramMoneyBot v8.0
Comprehensive log aggregation, analysis, and monitoring system
"""

import asyncio
import json
import logging
import time
import sqlite3
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import threading
import queue
from collections import defaultdict, Counter
import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LogLevel(Enum):
    """Log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogSource(Enum):
    """Log sources"""
    CHATGPT_BOT = "chatgpt_bot"
    DESKTOP_AGENT = "desktop_agent"
    MAIN_API = "main_api"
    DATABASE = "database"
    MT5 = "mt5"
    BINANCE = "binance"
    SYSTEM = "system"

class AnalysisType(Enum):
    """Analysis types"""
    ERROR_ANALYSIS = "error_analysis"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    PATTERN_ANALYSIS = "pattern_analysis"
    ANOMALY_DETECTION = "anomaly_detection"
    TREND_ANALYSIS = "trend_analysis"

@dataclass
class LogEntry:
    """Log entry data structure"""
    entry_id: str
    timestamp: datetime
    level: LogLevel
    source: LogSource
    message: str
    component: str
    thread_id: str
    process_id: str
    file_path: str
    line_number: int
    function_name: str
    metadata: Dict[str, Any]

@dataclass
class LogAnalysis:
    """Log analysis result"""
    analysis_id: str
    analysis_type: AnalysisType
    timestamp: datetime
    time_range: Tuple[datetime, datetime]
    total_logs: int
    error_count: int
    warning_count: int
    critical_count: int
    unique_errors: int
    error_patterns: List[str]
    performance_metrics: Dict[str, float]
    anomalies: List[str]
    trends: Dict[str, Any]
    recommendations: List[str]

@dataclass
class LogMetrics:
    """Log metrics"""
    timestamp: datetime
    total_logs: int
    error_rate: float
    warning_rate: float
    critical_rate: float
    avg_log_size: float
    log_volume_per_minute: float
    unique_sources: int
    unique_components: int

class LogAggregationAnalysis:
    """Log aggregation and analysis system"""
    
    def __init__(self, config_path: str = "log_aggregation_config.json"):
        self.config = self._load_config(config_path)
        self.log_entries: List[LogEntry] = []
        self.log_analyses: List[LogAnalysis] = []
        self.log_metrics: List[LogMetrics] = []
        self.running = False
        
        # Initialize log sources
        self._initialize_log_sources()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load log aggregation configuration"""
        default_config = {
            "log_sources": {
                "chatgpt_bot": {
                    "enabled": True,
                    "log_file": "logs/chatgpt_bot.log",
                    "log_format": "json",
                    "rotation_size": "100MB",
                    "retention_days": 30
                },
                "desktop_agent": {
                    "enabled": True,
                    "log_file": "logs/desktop_agent.log",
                    "log_format": "json",
                    "rotation_size": "100MB",
                    "retention_days": 30
                },
                "main_api": {
                    "enabled": True,
                    "log_file": "logs/main_api.log",
                    "log_format": "json",
                    "rotation_size": "100MB",
                    "retention_days": 30
                },
                "database": {
                    "enabled": True,
                    "log_file": "logs/database.log",
                    "log_format": "json",
                    "rotation_size": "50MB",
                    "retention_days": 30
                },
                "mt5": {
                    "enabled": True,
                    "log_file": "logs/mt5.log",
                    "log_format": "json",
                    "rotation_size": "50MB",
                    "retention_days": 30
                },
                "binance": {
                    "enabled": True,
                    "log_file": "logs/binance.log",
                    "log_format": "json",
                    "rotation_size": "50MB",
                    "retention_days": 30
                },
                "system": {
                    "enabled": True,
                    "log_file": "logs/system.log",
                    "log_format": "json",
                    "rotation_size": "100MB",
                    "retention_days": 30
                }
            },
            "analysis": {
                "error_analysis": {
                    "enabled": True,
                    "analysis_interval": 300.0,  # 5 minutes
                    "error_threshold": 10,
                    "pattern_detection": True
                },
                "performance_analysis": {
                    "enabled": True,
                    "analysis_interval": 600.0,  # 10 minutes
                    "performance_threshold": 1000.0,  # ms
                    "trend_detection": True
                },
                "anomaly_detection": {
                    "enabled": True,
                    "analysis_interval": 1800.0,  # 30 minutes
                    "anomaly_threshold": 3.0,  # standard deviations
                    "pattern_recognition": True
                },
                "trend_analysis": {
                    "enabled": True,
                    "analysis_interval": 3600.0,  # 1 hour
                    "trend_window_hours": 24,
                    "trend_detection": True
                }
            },
            "aggregation": {
                "collection_interval": 10.0,
                "batch_size": 1000,
                "retention_days": 30,
                "compression_enabled": True,
                "indexing_enabled": True
            },
            "monitoring": {
                "log_volume_threshold": 10000,  # logs per minute
                "error_rate_threshold": 5.0,  # percentage
                "critical_rate_threshold": 1.0,  # percentage
                "alert_on_anomalies": True
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
            logger.error(f"Error loading log aggregation config: {e}")
            return default_config
    
    def _initialize_log_sources(self):
        """Initialize log sources"""
        try:
            logger.info(f"Initialized {len(self.config['log_sources'])} log sources")
        except Exception as e:
            logger.error(f"Error initializing log sources: {e}")
    
    async def start_log_aggregation(self):
        """Start the log aggregation system"""
        try:
            logger.info("Starting log aggregation and analysis system")
            self.running = True
            
            # Start aggregation tasks
            tasks = [
                asyncio.create_task(self._collect_logs()),
                asyncio.create_task(self._analyze_logs()),
                asyncio.create_task(self._generate_metrics()),
                asyncio.create_task(self._cleanup_old_logs())
            ]
            
            # Wait for all tasks
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"Error starting log aggregation: {e}")
            self.running = False
    
    async def _collect_logs(self):
        """Collect logs from all sources"""
        try:
            while self.running:
                for source_name, source_config in self.config["log_sources"].items():
                    if not source_config["enabled"]:
                        continue
                    
                    try:
                        # Simulate log collection
                        await self._collect_source_logs(source_name, source_config)
                    except Exception as e:
                        logger.error(f"Error collecting logs from {source_name}: {e}")
                
                # Wait for next collection
                await asyncio.sleep(self.config["aggregation"]["collection_interval"])
                
        except Exception as e:
            logger.error(f"Error in log collection: {e}")
    
    async def _collect_source_logs(self, source_name: str, source_config: Dict[str, Any]):
        """Collect logs from a specific source"""
        try:
            # Simulate log collection
            log_count = np.random.randint(10, 100)
            
            for i in range(log_count):
                # Create simulated log entry
                log_entry = LogEntry(
                    entry_id=f"{source_name}_{int(time.time())}_{i}",
                    timestamp=datetime.now(),
                    level=LogLevel(np.random.choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])),
                    source=LogSource(source_name),
                    message=f"Simulated log message from {source_name} - {i}",
                    component=f"{source_name}_component",
                    thread_id=str(np.random.randint(1000, 9999)),
                    process_id=str(np.random.randint(1000, 9999)),
                    file_path=f"/app/{source_name}.py",
                    line_number=np.random.randint(1, 1000),
                    function_name=f"function_{i}",
                    metadata={"source": source_name, "simulated": True}
                )
                
                self.log_entries.append(log_entry)
            
            logger.debug(f"Collected {log_count} logs from {source_name}")
            
        except Exception as e:
            logger.error(f"Error collecting logs from {source_name}: {e}")
    
    async def _analyze_logs(self):
        """Analyze collected logs"""
        try:
            while self.running:
                # Run different types of analysis
                if self.config["analysis"]["error_analysis"]["enabled"]:
                    await self._run_error_analysis()
                
                if self.config["analysis"]["performance_analysis"]["enabled"]:
                    await self._run_performance_analysis()
                
                if self.config["analysis"]["anomaly_detection"]["enabled"]:
                    await self._run_anomaly_detection()
                
                if self.config["analysis"]["trend_analysis"]["enabled"]:
                    await self._run_trend_analysis()
                
                # Wait for next analysis
                await asyncio.sleep(60.0)  # Run analysis every minute
                
        except Exception as e:
            logger.error(f"Error in log analysis: {e}")
    
    async def _run_error_analysis(self):
        """Run error analysis"""
        try:
            analysis_config = self.config["analysis"]["error_analysis"]
            
            # Get recent logs
            recent_logs = self._get_recent_logs(analysis_config["analysis_interval"])
            
            if not recent_logs:
                return
            
            # Analyze errors
            error_logs = [log for log in recent_logs if log.level in [LogLevel.ERROR, LogLevel.CRITICAL]]
            warning_logs = [log for log in recent_logs if log.level == LogLevel.WARNING]
            
            # Detect error patterns
            error_patterns = self._detect_error_patterns(error_logs)
            
            # Create analysis result
            analysis = LogAnalysis(
                analysis_id=f"error_analysis_{int(time.time())}",
                analysis_type=AnalysisType.ERROR_ANALYSIS,
                timestamp=datetime.now(),
                time_range=(recent_logs[0].timestamp, recent_logs[-1].timestamp),
                total_logs=len(recent_logs),
                error_count=len(error_logs),
                warning_count=len(warning_logs),
                critical_count=len([log for log in error_logs if log.level == LogLevel.CRITICAL]),
                unique_errors=len(set(log.message for log in error_logs)),
                error_patterns=error_patterns,
                performance_metrics={},
                anomalies=[],
                trends={},
                recommendations=[]
            )
            
            # Generate recommendations
            analysis.recommendations = self._generate_error_recommendations(analysis)
            
            # Store analysis
            self.log_analyses.append(analysis)
            
            logger.info(f"Error analysis completed: {analysis.error_count} errors, {analysis.unique_errors} unique")
            
        except Exception as e:
            logger.error(f"Error in error analysis: {e}")
    
    async def _run_performance_analysis(self):
        """Run performance analysis"""
        try:
            analysis_config = self.config["analysis"]["performance_analysis"]
            
            # Get recent logs
            recent_logs = self._get_recent_logs(analysis_config["analysis_interval"])
            
            if not recent_logs:
                return
            
            # Analyze performance metrics
            performance_metrics = self._calculate_performance_metrics(recent_logs)
            
            # Create analysis result
            analysis = LogAnalysis(
                analysis_id=f"performance_analysis_{int(time.time())}",
                analysis_type=AnalysisType.PERFORMANCE_ANALYSIS,
                timestamp=datetime.now(),
                time_range=(recent_logs[0].timestamp, recent_logs[-1].timestamp),
                total_logs=len(recent_logs),
                error_count=0,
                warning_count=0,
                critical_count=0,
                unique_errors=0,
                error_patterns=[],
                performance_metrics=performance_metrics,
                anomalies=[],
                trends={},
                recommendations=[]
            )
            
            # Generate recommendations
            analysis.recommendations = self._generate_performance_recommendations(analysis)
            
            # Store analysis
            self.log_analyses.append(analysis)
            
            logger.info(f"Performance analysis completed: {performance_metrics}")
            
        except Exception as e:
            logger.error(f"Error in performance analysis: {e}")
    
    async def _run_anomaly_detection(self):
        """Run anomaly detection"""
        try:
            analysis_config = self.config["analysis"]["anomaly_detection"]
            
            # Get recent logs
            recent_logs = self._get_recent_logs(analysis_config["analysis_interval"])
            
            if not recent_logs:
                return
            
            # Detect anomalies
            anomalies = self._detect_anomalies(recent_logs)
            
            # Create analysis result
            analysis = LogAnalysis(
                analysis_id=f"anomaly_detection_{int(time.time())}",
                analysis_type=AnalysisType.ANOMALY_DETECTION,
                timestamp=datetime.now(),
                time_range=(recent_logs[0].timestamp, recent_logs[-1].timestamp),
                total_logs=len(recent_logs),
                error_count=0,
                warning_count=0,
                critical_count=0,
                unique_errors=0,
                error_patterns=[],
                performance_metrics={},
                anomalies=anomalies,
                trends={},
                recommendations=[]
            )
            
            # Generate recommendations
            analysis.recommendations = self._generate_anomaly_recommendations(analysis)
            
            # Store analysis
            self.log_analyses.append(analysis)
            
            logger.info(f"Anomaly detection completed: {len(anomalies)} anomalies found")
            
        except Exception as e:
            logger.error(f"Error in anomaly detection: {e}")
    
    async def _run_trend_analysis(self):
        """Run trend analysis"""
        try:
            analysis_config = self.config["analysis"]["trend_analysis"]
            
            # Get recent logs
            recent_logs = self._get_recent_logs(analysis_config["analysis_interval"])
            
            if not recent_logs:
                return
            
            # Analyze trends
            trends = self._analyze_trends(recent_logs)
            
            # Create analysis result
            analysis = LogAnalysis(
                analysis_id=f"trend_analysis_{int(time.time())}",
                analysis_type=AnalysisType.TREND_ANALYSIS,
                timestamp=datetime.now(),
                time_range=(recent_logs[0].timestamp, recent_logs[-1].timestamp),
                total_logs=len(recent_logs),
                error_count=0,
                warning_count=0,
                critical_count=0,
                unique_errors=0,
                error_patterns=[],
                performance_metrics={},
                anomalies=[],
                trends=trends,
                recommendations=[]
            )
            
            # Generate recommendations
            analysis.recommendations = self._generate_trend_recommendations(analysis)
            
            # Store analysis
            self.log_analyses.append(analysis)
            
            logger.info(f"Trend analysis completed: {trends}")
            
        except Exception as e:
            logger.error(f"Error in trend analysis: {e}")
    
    def _get_recent_logs(self, time_window_seconds: float) -> List[LogEntry]:
        """Get recent logs within time window"""
        try:
            cutoff_time = datetime.now() - timedelta(seconds=time_window_seconds)
            return [log for log in self.log_entries if log.timestamp >= cutoff_time]
        except Exception as e:
            logger.error(f"Error getting recent logs: {e}")
            return []
    
    def _detect_error_patterns(self, error_logs: List[LogEntry]) -> List[str]:
        """Detect error patterns in logs"""
        try:
            if not error_logs:
                return []
            
            # Group errors by message pattern
            error_groups = defaultdict(list)
            for log in error_logs:
                # Extract error pattern (simplified)
                pattern = re.sub(r'\d+', 'N', log.message)  # Replace numbers with N
                pattern = re.sub(r'[a-f0-9]{8,}', 'HASH', pattern)  # Replace hashes
                error_groups[pattern].append(log)
            
            # Find patterns with multiple occurrences
            patterns = []
            for pattern, logs in error_groups.items():
                if len(logs) > 1:
                    patterns.append(f"{pattern} ({len(logs)} occurrences)")
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting error patterns: {e}")
            return []
    
    def _calculate_performance_metrics(self, logs: List[LogEntry]) -> Dict[str, float]:
        """Calculate performance metrics from logs"""
        try:
            if not logs:
                return {}
            
            # Calculate basic metrics
            total_logs = len(logs)
            error_logs = [log for log in logs if log.level in [LogLevel.ERROR, LogLevel.CRITICAL]]
            warning_logs = [log for log in logs if log.level == LogLevel.WARNING]
            
            # Calculate rates
            error_rate = (len(error_logs) / total_logs) * 100 if total_logs > 0 else 0
            warning_rate = (len(warning_logs) / total_logs) * 100 if total_logs > 0 else 0
            
            # Calculate log volume
            time_span = (logs[-1].timestamp - logs[0].timestamp).total_seconds()
            log_volume_per_minute = (total_logs / time_span) * 60 if time_span > 0 else 0
            
            # Calculate average log size
            avg_log_size = np.mean([len(log.message) for log in logs])
            
            return {
                "total_logs": total_logs,
                "error_rate": error_rate,
                "warning_rate": warning_rate,
                "log_volume_per_minute": log_volume_per_minute,
                "avg_log_size": avg_log_size
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {}
    
    def _detect_anomalies(self, logs: List[LogEntry]) -> List[str]:
        """Detect anomalies in logs"""
        try:
            if not logs:
                return []
            
            anomalies = []
            
            # Detect volume anomalies
            log_counts = defaultdict(int)
            for log in logs:
                hour = log.timestamp.hour
                log_counts[hour] += 1
            
            if log_counts:
                avg_count = np.mean(list(log_counts.values()))
                std_count = np.std(list(log_counts.values()))
                
                for hour, count in log_counts.items():
                    if count > avg_count + 2 * std_count:
                        anomalies.append(f"High log volume at hour {hour}: {count} logs")
            
            # Detect error spikes
            error_counts = defaultdict(int)
            for log in logs:
                if log.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                    minute = log.timestamp.minute
                    error_counts[minute] += 1
            
            if error_counts:
                avg_errors = np.mean(list(error_counts.values()))
                if avg_errors > 5:  # Threshold for error spike
                    anomalies.append(f"Error spike detected: {avg_errors:.1f} errors per minute")
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return []
    
    def _analyze_trends(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Analyze trends in logs"""
        try:
            if not logs:
                return {}
            
            # Analyze log level trends
            level_counts = Counter(log.level.value for log in logs)
            
            # Analyze source trends
            source_counts = Counter(log.source.value for log in logs)
            
            # Analyze time trends
            hour_counts = Counter(log.timestamp.hour for log in logs)
            
            return {
                "level_distribution": dict(level_counts),
                "source_distribution": dict(source_counts),
                "hourly_distribution": dict(hour_counts),
                "total_logs": len(logs)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            return {}
    
    def _generate_error_recommendations(self, analysis: LogAnalysis) -> List[str]:
        """Generate error analysis recommendations"""
        recommendations = []
        
        if analysis.error_count > 50:
            recommendations.append("High error count detected. Investigate error sources.")
        
        if analysis.unique_errors > 10:
            recommendations.append("Many unique errors detected. Review error handling.")
        
        if analysis.critical_count > 5:
            recommendations.append("Critical errors detected. Immediate attention required.")
        
        if analysis.error_patterns:
            recommendations.append(f"Error patterns detected: {', '.join(analysis.error_patterns)}")
        
        return recommendations
    
    def _generate_performance_recommendations(self, analysis: LogAnalysis) -> List[str]:
        """Generate performance analysis recommendations"""
        recommendations = []
        
        if analysis.performance_metrics.get("error_rate", 0) > 5:
            recommendations.append("High error rate detected. Review system stability.")
        
        if analysis.performance_metrics.get("log_volume_per_minute", 0) > 1000:
            recommendations.append("High log volume detected. Consider log rotation.")
        
        return recommendations
    
    def _generate_anomaly_recommendations(self, analysis: LogAnalysis) -> List[str]:
        """Generate anomaly detection recommendations"""
        recommendations = []
        
        if analysis.anomalies:
            recommendations.append(f"Anomalies detected: {', '.join(analysis.anomalies)}")
        
        return recommendations
    
    def _generate_trend_recommendations(self, analysis: LogAnalysis) -> List[str]:
        """Generate trend analysis recommendations"""
        recommendations = []
        
        if analysis.trends.get("total_logs", 0) > 10000:
            recommendations.append("High log volume trend detected. Monitor system performance.")
        
        return recommendations
    
    async def _generate_metrics(self):
        """Generate log metrics"""
        try:
            while self.running:
                # Calculate current metrics
                current_time = datetime.now()
                recent_logs = self._get_recent_logs(60)  # Last minute
                
                if recent_logs:
                    error_count = len([log for log in recent_logs if log.level in [LogLevel.ERROR, LogLevel.CRITICAL]])
                    warning_count = len([log for log in recent_logs if log.level == LogLevel.WARNING])
                    critical_count = len([log for log in recent_logs if log.level == LogLevel.CRITICAL])
                    
                    error_rate = (error_count / len(recent_logs)) * 100
                    warning_rate = (warning_count / len(recent_logs)) * 100
                    critical_rate = (critical_count / len(recent_logs)) * 100
                    
                    avg_log_size = np.mean([len(log.message) for log in recent_logs])
                    log_volume_per_minute = len(recent_logs)
                    
                    unique_sources = len(set(log.source.value for log in recent_logs))
                    unique_components = len(set(log.component for log in recent_logs))
                    
                    metrics = LogMetrics(
                        timestamp=current_time,
                        total_logs=len(recent_logs),
                        error_rate=error_rate,
                        warning_rate=warning_rate,
                        critical_rate=critical_rate,
                        avg_log_size=avg_log_size,
                        log_volume_per_minute=log_volume_per_minute,
                        unique_sources=unique_sources,
                        unique_components=unique_components
                    )
                    
                    self.log_metrics.append(metrics)
                
                # Wait for next metrics generation
                await asyncio.sleep(60.0)  # Generate metrics every minute
                
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
    
    async def _cleanup_old_logs(self):
        """Clean up old logs"""
        try:
            while self.running:
                # Remove logs older than retention period
                retention_days = self.config["aggregation"]["retention_days"]
                cutoff_date = datetime.now() - timedelta(days=retention_days)
                
                # Clean up log entries
                self.log_entries = [log for log in self.log_entries if log.timestamp > cutoff_date]
                
                # Clean up analyses
                self.log_analyses = [analysis for analysis in self.log_analyses if analysis.timestamp > cutoff_date]
                
                # Clean up metrics
                self.log_metrics = [metrics for metrics in self.log_metrics if metrics.timestamp > cutoff_date]
                
                # Wait for next cleanup
                await asyncio.sleep(3600)  # Run cleanup every hour
                
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}")
    
    def get_log_analysis_summary(self) -> Dict[str, Any]:
        """Get log analysis summary"""
        try:
            if not self.log_analyses:
                return {"message": "No log analyses available"}
            
            # Get latest analysis
            latest_analysis = self.log_analyses[-1]
            
            # Calculate totals
            total_analyses = len(self.log_analyses)
            total_logs = sum(analysis.total_logs for analysis in self.log_analyses)
            total_errors = sum(analysis.error_count for analysis in self.log_analyses)
            total_anomalies = sum(len(analysis.anomalies) for analysis in self.log_analyses)
            
            return {
                "total_analyses": total_analyses,
                "total_logs_analyzed": total_logs,
                "total_errors": total_errors,
                "total_anomalies": total_anomalies,
                "latest_analysis": asdict(latest_analysis),
                "log_metrics": [asdict(metrics) for metrics in self.log_metrics[-10:]]  # Last 10 metrics
            }
            
        except Exception as e:
            logger.error(f"Error getting log analysis summary: {e}")
            return {}
    
    def stop_log_aggregation(self):
        """Stop the log aggregation system"""
        try:
            logger.info("Stopping log aggregation and analysis system")
            self.running = False
        except Exception as e:
            logger.error(f"Error stopping log aggregation: {e}")

async def main():
    """Main function for testing log aggregation"""
    log_aggregator = LogAggregationAnalysis()
    
    try:
        # Start log aggregation
        await log_aggregator.start_log_aggregation()
    except KeyboardInterrupt:
        logger.info("Log aggregation stopped by user")
    finally:
        log_aggregator.stop_log_aggregation()

if __name__ == "__main__":
    asyncio.run(main())
