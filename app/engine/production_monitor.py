"""
Production Monitoring System
Real-time monitoring and alerting for production deployment
"""

import numpy as np
import asyncio
import aiosqlite
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import logging
from dataclasses import dataclass
from enum import Enum
import threading
import time
import psutil
import os
from collections import deque
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """Alert levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MonitorStatus(Enum):
    """Monitor status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    OFFLINE = "offline"

@dataclass
class SystemAlert:
    """System alert"""
    alert_id: str
    level: AlertLevel
    component: str
    symbol: str
    message: str
    timestamp: int
    details: Dict[str, Any]
    resolved: bool = False

@dataclass
class SystemMetrics:
    """System metrics"""
    timestamp: int
    symbol: str
    component: str
    latency_p95: float
    throughput: float
    memory_usage: float
    cpu_usage: float
    queue_depth: int
    error_rate: float
    status: MonitorStatus

class ProductionMonitor:
    """Production monitoring system"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.symbol = symbol_config.get('symbol', 'unknown')
        
        # Monitoring configuration
        self.monitor_config = symbol_config.get('monitor_config', {})
        self.alert_thresholds = self.monitor_config.get('alert_thresholds', {})
        self.latency_threshold = self.alert_thresholds.get('latency_p95', 200)  # ms
        self.memory_threshold = self.alert_thresholds.get('memory_usage', 500)  # MB
        self.cpu_threshold = self.alert_thresholds.get('cpu_usage', 80)  # %
        self.error_rate_threshold = self.alert_thresholds.get('error_rate', 0.05)  # 5%
        
        # Alert configuration
        self.alert_config = self.monitor_config.get('alert_config', {})
        self.email_enabled = self.alert_config.get('email_enabled', False)
        self.email_recipients = self.alert_config.get('email_recipients', [])
        self.slack_enabled = self.alert_config.get('slack_enabled', False)
        self.slack_webhook = self.alert_config.get('slack_webhook', '')
        
        # Monitoring state
        self.metrics_history = deque(maxlen=1000)
        self.active_alerts = {}
        self.alert_history = deque(maxlen=1000)
        self.monitoring_active = False
        self.monitor_thread = None
        
        # System monitoring
        self.process = psutil.Process(os.getpid())
        self.system_monitor = SystemMonitor()
        
    def start_monitoring(self):
        """Start production monitoring"""
        try:
            if not self.monitoring_active:
                self.monitoring_active = True
                self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
                self.monitor_thread.start()
                logger.info(f"Production monitoring started for {self.symbol}")
                
        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")
    
    def stop_monitoring(self):
        """Stop production monitoring"""
        try:
            if self.monitoring_active:
                self.monitoring_active = False
                if self.monitor_thread:
                    self.monitor_thread.join(timeout=1.0)
                logger.info(f"Production monitoring stopped for {self.symbol}")
                
        except Exception as e:
            logger.error(f"Error stopping monitoring: {e}")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Collect system metrics
                metrics = self._collect_system_metrics()
                self.metrics_history.append(metrics)
                
                # Check for alerts
                alerts = self._check_alerts(metrics)
                for alert in alerts:
                    self._handle_alert(alert)
                
                # Sleep for monitoring interval
                time.sleep(1.0)  # Check every second
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5.0)  # Wait longer on error
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect system metrics"""
        try:
            # Get system metrics
            memory_usage = self.process.memory_info().rss / (1024 * 1024)  # MB
            cpu_usage = self.process.cpu_percent()
            
            # Calculate latency from recent metrics
            if self.metrics_history:
                recent_latencies = [m.latency_p95 for m in list(self.metrics_history)[-10:]]
                latency_p95 = np.percentile(recent_latencies, 95) if recent_latencies else 0.0
            else:
                latency_p95 = 0.0
            
            # Calculate throughput
            throughput = self._calculate_throughput()
            
            # Calculate error rate
            error_rate = self._calculate_error_rate()
            
            # Determine status
            status = self._determine_status(latency_p95, memory_usage, cpu_usage, error_rate)
            
            return SystemMetrics(
                timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
                symbol=self.symbol,
                component='production_monitor',
                latency_p95=latency_p95,
                throughput=throughput,
                memory_usage=memory_usage,
                cpu_usage=cpu_usage,
                queue_depth=0,  # Will be updated by specific components
                error_rate=error_rate,
                status=status
            )
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics(
                timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
                symbol=self.symbol,
                component='production_monitor',
                latency_p95=0.0, throughput=0.0, memory_usage=0.0, cpu_usage=0.0,
                queue_depth=0, error_rate=0.0, status=MonitorStatus.ERROR
            )
    
    def _calculate_throughput(self) -> float:
        """Calculate system throughput"""
        try:
            # This would typically calculate actual throughput
            # For now, we'll simulate based on recent metrics
            if len(self.metrics_history) >= 2:
                recent_metrics = list(self.metrics_history)[-2:]
                time_diff = (recent_metrics[-1].timestamp - recent_metrics[0].timestamp) / 1000.0
                if time_diff > 0:
                    return 1000.0 / time_diff  # Simulated throughput
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating throughput: {e}")
            return 0.0
    
    def _calculate_error_rate(self) -> float:
        """Calculate system error rate"""
        try:
            # This would typically calculate actual error rate
            # For now, we'll simulate based on recent metrics
            if len(self.metrics_history) >= 10:
                recent_metrics = list(self.metrics_history)[-10:]
                error_count = sum(1 for m in recent_metrics if m.status == MonitorStatus.ERROR)
                return error_count / len(recent_metrics)
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating error rate: {e}")
            return 0.0
    
    def _determine_status(
        self, 
        latency_p95: float, 
        memory_usage: float, 
        cpu_usage: float, 
        error_rate: float
    ) -> MonitorStatus:
        """Determine system status based on metrics"""
        try:
            # Check critical thresholds
            if (latency_p95 > self.latency_threshold * 2 or 
                memory_usage > self.memory_threshold * 2 or 
                cpu_usage > self.cpu_threshold * 2 or 
                error_rate > self.error_rate_threshold * 2):
                return MonitorStatus.CRITICAL
            
            # Check warning thresholds
            if (latency_p95 > self.latency_threshold or 
                memory_usage > self.memory_threshold or 
                cpu_usage > self.cpu_threshold or 
                error_rate > self.error_rate_threshold):
                return MonitorStatus.WARNING
            
            return MonitorStatus.HEALTHY
            
        except Exception as e:
            logger.error(f"Error determining status: {e}")
            return MonitorStatus.ERROR
    
    def _check_alerts(self, metrics: SystemMetrics) -> List[SystemAlert]:
        """Check for alerts based on metrics"""
        alerts = []
        
        try:
            # Latency alert
            if metrics.latency_p95 > self.latency_threshold:
                alert = SystemAlert(
                    alert_id=f"latency_{metrics.timestamp}",
                    level=AlertLevel.WARNING if metrics.latency_p95 < self.latency_threshold * 2 else AlertLevel.CRITICAL,
                    component='latency_monitor',
                    symbol=self.symbol,
                    message=f"High latency detected: {metrics.latency_p95:.2f}ms (threshold: {self.latency_threshold}ms)",
                    timestamp=metrics.timestamp,
                    details={'latency_p95': metrics.latency_p95, 'threshold': self.latency_threshold}
                )
                alerts.append(alert)
            
            # Memory alert
            if metrics.memory_usage > self.memory_threshold:
                alert = SystemAlert(
                    alert_id=f"memory_{metrics.timestamp}",
                    level=AlertLevel.WARNING if metrics.memory_usage < self.memory_threshold * 2 else AlertLevel.CRITICAL,
                    component='memory_monitor',
                    symbol=self.symbol,
                    message=f"High memory usage: {metrics.memory_usage:.2f}MB (threshold: {self.memory_threshold}MB)",
                    timestamp=metrics.timestamp,
                    details={'memory_usage': metrics.memory_usage, 'threshold': self.memory_threshold}
                )
                alerts.append(alert)
            
            # CPU alert
            if metrics.cpu_usage > self.cpu_threshold:
                alert = SystemAlert(
                    alert_id=f"cpu_{metrics.timestamp}",
                    level=AlertLevel.WARNING if metrics.cpu_usage < self.cpu_threshold * 2 else AlertLevel.CRITICAL,
                    component='cpu_monitor',
                    symbol=self.symbol,
                    message=f"High CPU usage: {metrics.cpu_usage:.2f}% (threshold: {self.cpu_threshold}%)",
                    timestamp=metrics.timestamp,
                    details={'cpu_usage': metrics.cpu_usage, 'threshold': self.cpu_threshold}
                )
                alerts.append(alert)
            
            # Error rate alert
            if metrics.error_rate > self.error_rate_threshold:
                alert = SystemAlert(
                    alert_id=f"error_rate_{metrics.timestamp}",
                    level=AlertLevel.WARNING if metrics.error_rate < self.error_rate_threshold * 2 else AlertLevel.CRITICAL,
                    component='error_monitor',
                    symbol=self.symbol,
                    message=f"High error rate: {metrics.error_rate:.2%} (threshold: {self.error_rate_threshold:.2%})",
                    timestamp=metrics.timestamp,
                    details={'error_rate': metrics.error_rate, 'threshold': self.error_rate_threshold}
                )
                alerts.append(alert)
            
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
        
        return alerts
    
    def _handle_alert(self, alert: SystemAlert):
        """Handle system alert"""
        try:
            # Check if alert already exists
            if alert.alert_id in self.active_alerts:
                return
            
            # Add to active alerts
            self.active_alerts[alert.alert_id] = alert
            self.alert_history.append(alert)
            
            # Log alert
            logger.warning(f"ALERT [{alert.level.value.upper()}] {alert.component}: {alert.message}")
            
            # Send notifications
            if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
                self._send_notifications(alert)
            
        except Exception as e:
            logger.error(f"Error handling alert: {e}")
    
    def _send_notifications(self, alert: SystemAlert):
        """Send alert notifications"""
        try:
            # Email notification
            if self.email_enabled and self.email_recipients:
                self._send_email_alert(alert)
            
            # Slack notification
            if self.slack_enabled and self.slack_webhook:
                self._send_slack_alert(alert)
                
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
    
    def _send_email_alert(self, alert: SystemAlert):
        """Send email alert"""
        try:
            # This would typically send actual emails
            # For now, we'll just log the email content
            email_content = f"""
            Alert: {alert.level.value.upper()}
            Component: {alert.component}
            Symbol: {alert.symbol}
            Message: {alert.message}
            Timestamp: {datetime.fromtimestamp(alert.timestamp / 1000, tz=timezone.utc)}
            Details: {json.dumps(alert.details, indent=2)}
            """
            
            logger.info(f"Email alert sent: {email_content}")
            
        except Exception as e:
            logger.error(f"Error sending email alert: {e}")
    
    def _send_slack_alert(self, alert: SystemAlert):
        """Send Slack alert"""
        try:
            # This would typically send actual Slack messages
            # For now, we'll just log the Slack content
            slack_content = f"""
            🚨 *{alert.level.value.upper()} ALERT*
            *Component:* {alert.component}
            *Symbol:* {alert.symbol}
            *Message:* {alert.message}
            *Timestamp:* {datetime.fromtimestamp(alert.timestamp / 1000, tz=timezone.utc)}
            """
            
            logger.info(f"Slack alert sent: {slack_content}")
            
        except Exception as e:
            logger.error(f"Error sending Slack alert: {e}")
    
    def resolve_alert(self, alert_id: str):
        """Resolve an alert"""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved = True
                del self.active_alerts[alert_id]
                logger.info(f"Alert resolved: {alert_id}")
                
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get monitoring summary"""
        try:
            if not self.metrics_history:
                return {'symbol': self.symbol, 'status': 'no_data'}
            
            # Get recent metrics
            recent_metrics = list(self.metrics_history)[-10:]  # Last 10 measurements
            
            # Calculate averages
            avg_latency = np.mean([m.latency_p95 for m in recent_metrics])
            avg_throughput = np.mean([m.throughput for m in recent_metrics])
            avg_memory = np.mean([m.memory_usage for m in recent_metrics])
            avg_cpu = np.mean([m.cpu_usage for m in recent_metrics])
            avg_error_rate = np.mean([m.error_rate for m in recent_metrics])
            
            # Status distribution
            status_counts = {}
            for metric in recent_metrics:
                status = metric.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Active alerts
            active_alert_count = len(self.active_alerts)
            critical_alerts = sum(1 for alert in self.active_alerts.values() if alert.level == AlertLevel.CRITICAL)
            
            return {
                'symbol': self.symbol,
                'monitoring_active': self.monitoring_active,
                'avg_latency_p95': avg_latency,
                'avg_throughput': avg_throughput,
                'avg_memory_usage': avg_memory,
                'avg_cpu_usage': avg_cpu,
                'avg_error_rate': avg_error_rate,
                'status_distribution': status_counts,
                'active_alerts': active_alert_count,
                'critical_alerts': critical_alerts,
                'total_alerts': len(self.alert_history)
            }
            
        except Exception as e:
            logger.error(f"Error getting monitoring summary: {e}")
            return {'symbol': self.symbol, 'error': str(e)}

class SystemMonitor:
    """System-wide monitoring"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.system_metrics = deque(maxlen=100)
        
    def get_system_health(self) -> Dict[str, Any]:
        """Get system health status"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Process metrics
            process_memory = self.process.memory_info().rss / (1024 * 1024)  # MB
            process_cpu = self.process.cpu_percent()
            
            # Determine health status
            if (cpu_percent > 90 or memory.percent > 90 or disk.percent > 90):
                health_status = 'critical'
            elif (cpu_percent > 80 or memory.percent > 80 or disk.percent > 80):
                health_status = 'warning'
            else:
                health_status = 'healthy'
            
            return {
                'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),
                'health_status': health_status,
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent,
                'process_memory_mb': process_memory,
                'process_cpu_percent': process_cpu
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {'health_status': 'error', 'error': str(e)}

# Example usage and testing
if __name__ == "__main__":
    # Test configuration
    test_config = {
        'symbol': 'BTCUSDc',
        'monitor_config': {
            'alert_thresholds': {
                'latency_p95': 200,
                'memory_usage': 500,
                'cpu_usage': 80,
                'error_rate': 0.05
            },
            'alert_config': {
                'email_enabled': False,
                'slack_enabled': False
            }
        }
    }
    
    # Create production monitor
    monitor = ProductionMonitor(test_config)
    
    print("Testing Production Monitor:")
    
    # Start monitoring
    monitor.start_monitoring()
    
    # Simulate some metrics
    for i in range(5):
        time.sleep(1)
        # Monitor will collect metrics automatically
    
    # Get monitoring summary
    summary = monitor.get_monitoring_summary()
    print(f"Monitoring Summary: {summary}")
    
    # Stop monitoring
    monitor.stop_monitoring()
    print("Production monitoring test completed")
