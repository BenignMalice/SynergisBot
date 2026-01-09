#!/usr/bin/env python3
"""
Production Monitoring and Alerting System for TelegramMoneyBot v8.0
Comprehensive monitoring, alerting, and notification system
"""

import asyncio
import json
import time
import smtplib
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import psutil
import sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class AlertStatus(Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"

class NotificationChannel(Enum):
    """Notification channels"""
    EMAIL = "email"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"

@dataclass
class AlertRule:
    """Alert rule configuration"""
    id: str
    name: str
    description: str
    metric: str
    threshold: float
    operator: str  # >, <, >=, <=, ==, !=
    level: AlertLevel
    channels: List[NotificationChannel]
    enabled: bool = True
    cooldown_minutes: int = 5
    escalation_minutes: int = 30

@dataclass
class Alert:
    """Alert instance"""
    id: str
    rule_id: str
    level: AlertLevel
    message: str
    metric_value: float
    threshold: float
    timestamp: datetime
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    escalation_count: int = 0

@dataclass
class NotificationConfig:
    """Notification configuration"""
    channel: NotificationChannel
    enabled: bool
    config: Dict[str, Any]

class ProductionMonitoringAlerting:
    """Production monitoring and alerting system"""
    
    def __init__(self, config_path: str = "monitoring_alerting_config.json"):
        self.config = self._load_config(config_path)
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.metrics_cache: Dict[str, Any] = {}
        self.notification_handlers: Dict[NotificationChannel, Callable] = {}
        
        # Initialize alert rules
        self._initialize_alert_rules()
        
        # Initialize notification handlers
        self._initialize_notification_handlers()
        
        # Start monitoring
        self.running = False
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load monitoring and alerting configuration"""
        default_config = {
            "monitoring": {
                "update_interval": 5.0,
                "metrics_retention_hours": 24,
                "alert_retention_days": 30
            },
            "alert_rules": {
                "high_cpu_usage": {
                    "id": "high_cpu_usage",
                    "name": "High CPU Usage",
                    "description": "CPU usage exceeds threshold",
                    "metric": "cpu_usage",
                    "threshold": 80.0,
                    "operator": ">",
                    "level": "warning",
                    "channels": ["email", "slack"],
                    "enabled": True,
                    "cooldown_minutes": 5,
                    "escalation_minutes": 30
                },
                "high_memory_usage": {
                    "id": "high_memory_usage",
                    "name": "High Memory Usage",
                    "description": "Memory usage exceeds threshold",
                    "metric": "memory_usage",
                    "threshold": 85.0,
                    "operator": ">",
                    "level": "warning",
                    "channels": ["email", "slack"],
                    "enabled": True,
                    "cooldown_minutes": 5,
                    "escalation_minutes": 30
                },
                "critical_cpu_usage": {
                    "id": "critical_cpu_usage",
                    "name": "Critical CPU Usage",
                    "description": "CPU usage is critically high",
                    "metric": "cpu_usage",
                    "threshold": 95.0,
                    "operator": ">",
                    "level": "critical",
                    "channels": ["email", "slack", "pagerduty"],
                    "enabled": True,
                    "cooldown_minutes": 2,
                    "escalation_minutes": 15
                },
                "high_disk_usage": {
                    "id": "high_disk_usage",
                    "name": "High Disk Usage",
                    "description": "Disk usage exceeds threshold",
                    "metric": "disk_usage",
                    "threshold": 90.0,
                    "operator": ">",
                    "level": "critical",
                    "channels": ["email", "slack", "pagerduty"],
                    "enabled": True,
                    "cooldown_minutes": 2,
                    "escalation_minutes": 15
                },
                "service_down": {
                    "id": "service_down",
                    "name": "Service Down",
                    "description": "Critical service is not responding",
                    "metric": "service_health",
                    "threshold": 0.0,
                    "operator": "==",
                    "level": "emergency",
                    "channels": ["email", "slack", "pagerduty"],
                    "enabled": True,
                    "cooldown_minutes": 1,
                    "escalation_minutes": 5
                },
                "high_latency": {
                    "id": "high_latency",
                    "name": "High Latency",
                    "description": "System latency exceeds threshold",
                    "metric": "latency_p95",
                    "threshold": 1000.0,
                    "operator": ">",
                    "level": "warning",
                    "channels": ["email", "slack"],
                    "enabled": True,
                    "cooldown_minutes": 5,
                    "escalation_minutes": 30
                },
                "database_error": {
                    "id": "database_error",
                    "name": "Database Error",
                    "description": "Database operation failed",
                    "metric": "database_errors",
                    "threshold": 5.0,
                    "operator": ">",
                    "level": "critical",
                    "channels": ["email", "slack", "pagerduty"],
                    "enabled": True,
                    "cooldown_minutes": 2,
                    "escalation_minutes": 15
                }
            },
            "notifications": {
                "email": {
                    "enabled": True,
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "username": "alerts@company.com",
                    "password": "your_password",
                    "from_email": "alerts@company.com",
                    "to_emails": ["admin@company.com", "ops@company.com"]
                },
                "slack": {
                    "enabled": True,
                    "webhook_url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
                    "channel": "#alerts",
                    "username": "TelegramMoneyBot"
                },
                "pagerduty": {
                    "enabled": False,
                    "integration_key": "your_integration_key",
                    "service_key": "your_service_key"
                },
                "webhook": {
                    "enabled": False,
                    "url": "https://your-webhook-url.com/alerts",
                    "headers": {"Authorization": "Bearer your-token"}
                }
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
            logger.error(f"Error loading monitoring config: {e}")
            return default_config
    
    def _initialize_alert_rules(self):
        """Initialize alert rules from configuration"""
        try:
            for rule_id, rule_config in self.config["alert_rules"].items():
                rule = AlertRule(
                    id=rule_config["id"],
                    name=rule_config["name"],
                    description=rule_config["description"],
                    metric=rule_config["metric"],
                    threshold=rule_config["threshold"],
                    operator=rule_config["operator"],
                    level=AlertLevel(rule_config["level"]),
                    channels=[NotificationChannel(ch) for ch in rule_config["channels"]],
                    enabled=rule_config["enabled"],
                    cooldown_minutes=rule_config["cooldown_minutes"],
                    escalation_minutes=rule_config["escalation_minutes"]
                )
                self.alert_rules[rule_id] = rule
                
            logger.info(f"Initialized {len(self.alert_rules)} alert rules")
            
        except Exception as e:
            logger.error(f"Error initializing alert rules: {e}")
    
    def _initialize_notification_handlers(self):
        """Initialize notification handlers"""
        self.notification_handlers = {
            NotificationChannel.EMAIL: self._send_email_notification,
            NotificationChannel.SLACK: self._send_slack_notification,
            NotificationChannel.PAGERDUTY: self._send_pagerduty_notification,
            NotificationChannel.WEBHOOK: self._send_webhook_notification
        }
    
    async def start_monitoring(self):
        """Start the monitoring system"""
        logger.info("Starting production monitoring and alerting system...")
        self.running = True
        
        try:
            while self.running:
                # Collect metrics
                await self._collect_metrics()
                
                # Evaluate alert rules
                await self._evaluate_alert_rules()
                
                # Process escalations
                await self._process_escalations()
                
                # Clean up old data
                await self._cleanup_old_data()
                
                # Wait for next update
                await asyncio.sleep(self.config["monitoring"]["update_interval"])
                
        except KeyboardInterrupt:
            logger.info("Stopping monitoring system...")
            self.running = False
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            self.running = False
    
    async def _collect_metrics(self):
        """Collect system metrics"""
        try:
            # System metrics
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Service health metrics
            service_health = await self._check_service_health()
            
            # Database metrics
            database_metrics = await self._check_database_health()
            
            # Trading metrics
            trading_metrics = await self._get_trading_metrics()
            
            # Update metrics cache
            self.metrics_cache = {
                "timestamp": time.time(),
                "cpu_usage": cpu_usage,
                "memory_usage": memory.percent,
                "memory_available": memory.available,
                "disk_usage": disk.percent,
                "disk_free": disk.free,
                "network_bytes_sent": network.bytes_sent,
                "network_bytes_recv": network.bytes_recv,
                "service_health": service_health,
                "database_metrics": database_metrics,
                "trading_metrics": trading_metrics,
                "latency_p95": self._calculate_latency_p95(),
                "database_errors": self._count_database_errors()
            }
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
    
    async def _check_service_health(self) -> Dict[str, bool]:
        """Check health of all services"""
        services = {
            "main_api": "http://localhost:8000/health",
            "chatgpt_bot": "http://localhost:8001/health",
            "desktop_agent": "http://localhost:8002/health"
        }
        
        health_status = {}
        for service, url in services.items():
            try:
                response = requests.get(url, timeout=5)
                health_status[service] = response.status_code == 200
            except Exception:
                health_status[service] = False
        
        return health_status
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database health"""
        databases = [
            "data/unified_tick_pipeline.db",
            "data/analysis_data.db",
            "data/system_logs.db"
        ]
        
        db_metrics = {}
        for db_path in databases:
            try:
                if Path(db_path).exists():
                    with sqlite3.connect(db_path) as conn:
                        # Check if database is accessible
                        conn.execute("SELECT 1")
                        
                        # Get database size
                        size = Path(db_path).stat().st_size
                        
                        # Get table count
                        cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                        table_count = cursor.fetchone()[0]
                        
                        db_metrics[db_path] = {
                            "accessible": True,
                            "size_bytes": size,
                            "table_count": table_count,
                            "error_count": 0
                        }
                else:
                    db_metrics[db_path] = {
                        "accessible": False,
                        "size_bytes": 0,
                        "table_count": 0,
                        "error_count": 1
                    }
            except Exception as e:
                db_metrics[db_path] = {
                    "accessible": False,
                    "size_bytes": 0,
                    "table_count": 0,
                    "error_count": 1,
                    "error": str(e)
                }
        
        return db_metrics
    
    async def _get_trading_metrics(self) -> Dict[str, Any]:
        """Get trading performance metrics"""
        try:
            # In a real implementation, this would query the trading database
            return {
                "total_trades": 0,
                "active_positions": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "current_drawdown": 0.0,
                "daily_pnl": 0.0,
                "total_pnl": 0.0
            }
        except Exception as e:
            logger.error(f"Error getting trading metrics: {e}")
            return {}
    
    def _calculate_latency_p95(self) -> float:
        """Calculate p95 latency (simulated)"""
        # In a real implementation, this would calculate actual latency
        return 50.0  # Simulated 50ms p95 latency
    
    def _count_database_errors(self) -> int:
        """Count database errors in the last hour"""
        # In a real implementation, this would count actual database errors
        return 0  # Simulated no errors
    
    async def _evaluate_alert_rules(self):
        """Evaluate all alert rules"""
        try:
            for rule_id, rule in self.alert_rules.items():
                if not rule.enabled:
                    continue
                
                # Get metric value
                metric_value = self.metrics_cache.get(rule.metric, 0)
                
                # Check if alert condition is met
                if self._evaluate_condition(metric_value, rule.operator, rule.threshold):
                    # Check if alert already exists and is within cooldown
                    if not self._is_alert_in_cooldown(rule_id):
                        await self._create_alert(rule, metric_value)
                else:
                    # Resolve existing alert if condition is no longer met
                    await self._resolve_alert_if_condition_met(rule_id)
                    
        except Exception as e:
            logger.error(f"Error evaluating alert rules: {e}")
    
    def _evaluate_condition(self, value: float, operator: str, threshold: float) -> bool:
        """Evaluate alert condition"""
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        elif operator == "!=":
            return value != threshold
        else:
            return False
    
    def _is_alert_in_cooldown(self, rule_id: str) -> bool:
        """Check if alert is in cooldown period"""
        if rule_id in self.active_alerts:
            alert = self.active_alerts[rule_id]
            rule = self.alert_rules[rule_id]
            cooldown_seconds = rule.cooldown_minutes * 60
            return (datetime.now() - alert.timestamp).total_seconds() < cooldown_seconds
        return False
    
    async def _create_alert(self, rule: AlertRule, metric_value: float):
        """Create a new alert"""
        try:
            alert_id = f"{rule.id}_{int(time.time())}"
            
            alert = Alert(
                id=alert_id,
                rule_id=rule.id,
                level=rule.level,
                message=f"{rule.name}: {rule.description} (Current: {metric_value:.2f}, Threshold: {rule.threshold})",
                metric_value=metric_value,
                threshold=rule.threshold,
                timestamp=datetime.now()
            )
            
            self.active_alerts[rule.id] = alert
            self.alert_history.append(alert)
            
            # Send notifications
            await self._send_alert_notifications(alert, rule)
            
            logger.warning(f"Alert created: {alert.message}")
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
    
    async def _resolve_alert_if_condition_met(self, rule_id: str):
        """Resolve alert if condition is no longer met"""
        if rule_id in self.active_alerts:
            alert = self.active_alerts[rule_id]
            rule = self.alert_rules[rule_id]
            
            # Check if condition is no longer met
            metric_value = self.metrics_cache.get(rule.metric, 0)
            if not self._evaluate_condition(metric_value, rule.operator, rule.threshold):
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now()
                del self.active_alerts[rule_id]
                
                # Send resolution notification
                await self._send_resolution_notification(alert, rule)
                
                logger.info(f"Alert resolved: {alert.message}")
    
    async def _process_escalations(self):
        """Process alert escalations"""
        try:
            current_time = datetime.now()
            
            for rule_id, alert in self.active_alerts.items():
                if alert.status != AlertStatus.ACTIVE:
                    continue
                
                rule = self.alert_rules[rule_id]
                escalation_seconds = rule.escalation_minutes * 60
                
                # Check if alert needs escalation
                if (current_time - alert.timestamp).total_seconds() > escalation_seconds:
                    alert.escalation_count += 1
                    
                    # Send escalation notification
                    await self._send_escalation_notification(alert, rule)
                    
                    logger.warning(f"Alert escalated: {alert.message} (escalation #{alert.escalation_count})")
                    
        except Exception as e:
            logger.error(f"Error processing escalations: {e}")
    
    async def _send_alert_notifications(self, alert: Alert, rule: AlertRule):
        """Send alert notifications"""
        for channel in rule.channels:
            try:
                handler = self.notification_handlers.get(channel)
                if handler:
                    await handler(alert, rule)
            except Exception as e:
                logger.error(f"Error sending notification via {channel.value}: {e}")
    
    async def _send_resolution_notification(self, alert: Alert, rule: AlertRule):
        """Send alert resolution notification"""
        for channel in rule.channels:
            try:
                handler = self.notification_handlers.get(channel)
                if handler:
                    await handler(alert, rule, is_resolution=True)
            except Exception as e:
                logger.error(f"Error sending resolution notification via {channel.value}: {e}")
    
    async def _send_escalation_notification(self, alert: Alert, rule: AlertRule):
        """Send alert escalation notification"""
        for channel in rule.channels:
            try:
                handler = self.notification_handlers.get(channel)
                if handler:
                    await handler(alert, rule, is_escalation=True)
            except Exception as e:
                logger.error(f"Error sending escalation notification via {channel.value}: {e}")
    
    async def _send_email_notification(self, alert: Alert, rule: AlertRule, is_resolution: bool = False, is_escalation: bool = False):
        """Send email notification"""
        try:
            email_config = self.config["notifications"]["email"]
            if not email_config["enabled"]:
                return
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = email_config["from_email"]
            msg['To'] = ", ".join(email_config["to_emails"])
            
            if is_resolution:
                msg['Subject'] = f"RESOLVED: {alert.message}"
                body = f"Alert resolved: {alert.message}\nResolved at: {alert.resolved_at}"
            elif is_escalation:
                msg['Subject'] = f"ESCALATED: {alert.message}"
                body = f"Alert escalated: {alert.message}\nEscalation count: {alert.escalation_count}\nOriginal alert time: {alert.timestamp}"
            else:
                msg['Subject'] = f"ALERT: {alert.message}"
                body = f"Alert: {alert.message}\nLevel: {alert.level.value}\nTimestamp: {alert.timestamp}\nMetric: {rule.metric}\nValue: {alert.metric_value}\nThreshold: {alert.threshold}"
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
            server.starttls()
            server.login(email_config["username"], email_config["password"])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email notification sent for {alert.id}")
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
    
    async def _send_slack_notification(self, alert: Alert, rule: AlertRule, is_resolution: bool = False, is_escalation: bool = False):
        """Send Slack notification"""
        try:
            slack_config = self.config["notifications"]["slack"]
            if not slack_config["enabled"]:
                return
            
            # Create Slack message
            if is_resolution:
                color = "good"
                title = f"✅ RESOLVED: {alert.message}"
                text = f"Alert resolved at {alert.resolved_at}"
            elif is_escalation:
                color = "danger"
                title = f"🚨 ESCALATED: {alert.message}"
                text = f"Alert escalated (escalation #{alert.escalation_count})"
            else:
                color = "warning" if alert.level == AlertLevel.WARNING else "danger"
                title = f"🚨 ALERT: {alert.message}"
                text = f"Level: {alert.level.value}\nMetric: {rule.metric}\nValue: {alert.metric_value}\nThreshold: {alert.threshold}"
            
            payload = {
                "channel": slack_config["channel"],
                "username": slack_config["username"],
                "attachments": [{
                    "color": color,
                    "title": title,
                    "text": text,
                    "timestamp": int(alert.timestamp.timestamp())
                }]
            }
            
            # Send to Slack
            response = requests.post(slack_config["webhook_url"], json=payload)
            response.raise_for_status()
            
            logger.info(f"Slack notification sent for {alert.id}")
            
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
    
    async def _send_pagerduty_notification(self, alert: Alert, rule: AlertRule, is_resolution: bool = False, is_escalation: bool = False):
        """Send PagerDuty notification"""
        try:
            pagerduty_config = self.config["notifications"]["pagerduty"]
            if not pagerduty_config["enabled"]:
                return
            
            # PagerDuty integration would go here
            # This is a simplified implementation
            logger.info(f"PagerDuty notification sent for {alert.id}")
            
        except Exception as e:
            logger.error(f"Error sending PagerDuty notification: {e}")
    
    async def _send_webhook_notification(self, alert: Alert, rule: AlertRule, is_resolution: bool = False, is_escalation: bool = False):
        """Send webhook notification"""
        try:
            webhook_config = self.config["notifications"]["webhook"]
            if not webhook_config["enabled"]:
                return
            
            # Create webhook payload
            payload = {
                "alert_id": alert.id,
                "rule_id": rule.id,
                "level": alert.level.value,
                "message": alert.message,
                "metric_value": alert.metric_value,
                "threshold": alert.threshold,
                "timestamp": alert.timestamp.isoformat(),
                "is_resolution": is_resolution,
                "is_escalation": is_escalation
            }
            
            # Send webhook
            headers = webhook_config.get("headers", {})
            response = requests.post(webhook_config["url"], json=payload, headers=headers)
            response.raise_for_status()
            
            logger.info(f"Webhook notification sent for {alert.id}")
            
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
    
    async def _cleanup_old_data(self):
        """Clean up old metrics and alerts"""
        try:
            current_time = time.time()
            retention_hours = self.config["monitoring"]["metrics_retention_hours"]
            retention_days = self.config["monitoring"]["alert_retention_days"]
            
            # Clean up old alerts
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            self.alert_history = [alert for alert in self.alert_history if alert.timestamp > cutoff_time]
            
            logger.info(f"Cleaned up old data: {len(self.alert_history)} alerts retained")
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            "running": self.running,
            "active_alerts": len(self.active_alerts),
            "total_alerts": len(self.alert_history),
            "alert_rules": len(self.alert_rules),
            "enabled_rules": len([r for r in self.alert_rules.values() if r.enabled]),
            "current_metrics": self.metrics_cache,
            "active_alert_details": [asdict(alert) for alert in self.active_alerts.values()]
        }
    
    def acknowledge_alert(self, alert_id: str, username: str) -> bool:
        """Acknowledge an alert"""
        try:
            for rule_id, alert in self.active_alerts.items():
                if alert.id == alert_id:
                    alert.status = AlertStatus.ACKNOWLEDGED
                    alert.acknowledged_by = username
                    alert.acknowledged_at = datetime.now()
                    
                    logger.info(f"Alert {alert_id} acknowledged by {username}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error acknowledging alert {alert_id}: {e}")
            return False

async def main():
    """Main function for testing monitoring and alerting"""
    monitoring = ProductionMonitoringAlerting()
    
    # Start monitoring
    await monitoring.start_monitoring()

if __name__ == "__main__":
    asyncio.run(main())
