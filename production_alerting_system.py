#!/usr/bin/env python3
"""
Production Alerting System for TelegramMoneyBot v8.0
Comprehensive alerting system for production monitoring and system health
"""

import asyncio
import json
import logging
import time
import smtplib
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import threading
import queue
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import psutil
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertStatus(Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"

class NotificationChannel(Enum):
    """Notification channels"""
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    WEBHOOK = "webhook"
    CONSOLE = "console"

@dataclass
class AlertRule:
    """Alert rule configuration"""
    rule_id: str
    name: str
    description: str
    metric_name: str
    condition: str  # ">", "<", ">=", "<=", "==", "!="
    threshold: float
    severity: AlertSeverity
    enabled: bool = True
    cooldown_minutes: int = 5
    notification_channels: List[NotificationChannel] = None

@dataclass
class Alert:
    """Alert instance"""
    alert_id: str
    rule_id: str
    severity: AlertSeverity
    message: str
    timestamp: datetime
    component: str
    metric_name: str
    current_value: float
    threshold: float
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    notification_sent: bool = False

@dataclass
class Notification:
    """Notification data"""
    notification_id: str
    alert_id: str
    channel: NotificationChannel
    recipient: str
    message: str
    timestamp: datetime
    sent: bool = False
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None

class ProductionAlertingSystem:
    """Production alerting system"""
    
    def __init__(self, config_path: str = "alerting_system_config.json"):
        self.config = self._load_config(config_path)
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.notifications: List[Notification] = []
        self.running = False
        
        # Initialize alert rules
        self._initialize_alert_rules()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load alerting system configuration"""
        default_config = {
            "alert_rules": {
                "cpu_usage_high": {
                    "rule_id": "cpu_usage_high",
                    "name": "High CPU Usage",
                    "description": "CPU usage exceeds threshold",
                    "metric_name": "cpu_usage_percent",
                    "condition": ">",
                    "threshold": 85.0,
                    "severity": "high",
                    "enabled": True,
                    "cooldown_minutes": 5,
                    "notification_channels": ["email", "slack"]
                },
                "memory_usage_high": {
                    "rule_id": "memory_usage_high",
                    "name": "High Memory Usage",
                    "description": "Memory usage exceeds threshold",
                    "metric_name": "memory_usage_percent",
                    "condition": ">",
                    "threshold": 90.0,
                    "severity": "high",
                    "enabled": True,
                    "cooldown_minutes": 5,
                    "notification_channels": ["email", "slack"]
                },
                "disk_usage_high": {
                    "rule_id": "disk_usage_high",
                    "name": "High Disk Usage",
                    "description": "Disk usage exceeds threshold",
                    "metric_name": "disk_usage_percent",
                    "condition": ">",
                    "threshold": 85.0,
                    "severity": "medium",
                    "enabled": True,
                    "cooldown_minutes": 10,
                    "notification_channels": ["email"]
                },
                "response_time_high": {
                    "rule_id": "response_time_high",
                    "name": "High Response Time",
                    "description": "API response time exceeds threshold",
                    "metric_name": "response_time_ms",
                    "condition": ">",
                    "threshold": 2000.0,
                    "severity": "high",
                    "enabled": True,
                    "cooldown_minutes": 5,
                    "notification_channels": ["email", "slack"]
                },
                "error_rate_high": {
                    "rule_id": "error_rate_high",
                    "name": "High Error Rate",
                    "description": "Error rate exceeds threshold",
                    "metric_name": "error_rate_percent",
                    "condition": ">",
                    "threshold": 10.0,
                    "severity": "critical",
                    "enabled": True,
                    "cooldown_minutes": 2,
                    "notification_channels": ["email", "sms", "slack"]
                },
                "component_down": {
                    "rule_id": "component_down",
                    "name": "Component Down",
                    "description": "Critical component is down",
                    "metric_name": "component_status",
                    "condition": "==",
                    "threshold": 0.0,
                    "severity": "critical",
                    "enabled": True,
                    "cooldown_minutes": 1,
                    "notification_channels": ["email", "sms", "slack", "webhook"]
                }
            },
            "notification_channels": {
                "email": {
                    "enabled": True,
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "username": "alerts@company.com",
                    "password": "password",
                    "from_email": "alerts@company.com",
                    "recipients": ["admin@company.com", "ops@company.com"]
                },
                "sms": {
                    "enabled": True,
                    "api_key": "your_sms_api_key",
                    "from_number": "+1234567890",
                    "recipients": ["+1234567890"]
                },
                "slack": {
                    "enabled": True,
                    "webhook_url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
                    "channel": "#alerts",
                    "username": "AlertBot"
                },
                "webhook": {
                    "enabled": True,
                    "url": "https://your-webhook-endpoint.com/alerts",
                    "headers": {
                        "Authorization": "Bearer your-token",
                        "Content-Type": "application/json"
                    }
                }
            },
            "alerting": {
                "evaluation_interval": 30.0,
                "retention_days": 30,
                "max_alerts_per_minute": 10,
                "suppression_rules": {
                    "maintenance_window": {
                        "enabled": False,
                        "start_time": "02:00",
                        "end_time": "04:00",
                        "timezone": "UTC"
                    }
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
                return default_config
            else:
                # Save default config
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            logger.error(f"Error loading alerting system config: {e}")
            return default_config
    
    def _initialize_alert_rules(self):
        """Initialize alert rules"""
        try:
            for rule_id, rule_data in self.config["alert_rules"].items():
                alert_rule = AlertRule(
                    rule_id=rule_data["rule_id"],
                    name=rule_data["name"],
                    description=rule_data["description"],
                    metric_name=rule_data["metric_name"],
                    condition=rule_data["condition"],
                    threshold=rule_data["threshold"],
                    severity=AlertSeverity(rule_data["severity"]),
                    enabled=rule_data["enabled"],
                    cooldown_minutes=rule_data["cooldown_minutes"],
                    notification_channels=[NotificationChannel(ch) for ch in rule_data["notification_channels"]]
                )
                self.alert_rules[rule_id] = alert_rule
            
            logger.info(f"Initialized {len(self.alert_rules)} alert rules")
            
        except Exception as e:
            logger.error(f"Error initializing alert rules: {e}")
    
    async def start_alerting(self):
        """Start the alerting system"""
        try:
            logger.info("Starting production alerting system")
            self.running = True
            
            # Start alerting tasks
            tasks = [
                asyncio.create_task(self._evaluate_alerts()),
                asyncio.create_task(self._process_notifications()),
                asyncio.create_task(self._cleanup_old_alerts())
            ]
            
            # Wait for all tasks
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"Error starting alerting system: {e}")
            self.running = False
    
    async def _evaluate_alerts(self):
        """Evaluate alert conditions"""
        try:
            while self.running:
                for rule_id, rule in self.alert_rules.items():
                    if not rule.enabled:
                        continue
                    
                    # Check if rule is in cooldown
                    if self._is_rule_in_cooldown(rule_id):
                        continue
                    
                    # Get current metric value
                    current_value = await self._get_metric_value(rule.metric_name)
                    
                    if current_value is not None:
                        # Check alert condition
                        if self._evaluate_condition(current_value, rule.condition, rule.threshold):
                            # Create alert
                            await self._create_alert(rule, current_value)
                        else:
                            # Resolve existing alert if any
                            await self._resolve_alert(rule_id)
                
                # Wait for next evaluation
                await asyncio.sleep(self.config["alerting"]["evaluation_interval"])
                
        except Exception as e:
            logger.error(f"Error evaluating alerts: {e}")
    
    def _is_rule_in_cooldown(self, rule_id: str) -> bool:
        """Check if rule is in cooldown period"""
        try:
            rule = self.alert_rules[rule_id]
            
            # Check if there's an active alert for this rule
            for alert in self.active_alerts.values():
                if (alert.rule_id == rule_id and 
                    alert.status == AlertStatus.ACTIVE and
                    (datetime.now() - alert.timestamp).total_seconds() < rule.cooldown_minutes * 60):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking rule cooldown: {e}")
            return False
    
    async def _get_metric_value(self, metric_name: str) -> Optional[float]:
        """Get current metric value"""
        try:
            # Simulate getting metric value
            # In real implementation, this would query the monitoring system
            
            if metric_name == "cpu_usage_percent":
                return psutil.cpu_percent()
            elif metric_name == "memory_usage_percent":
                return psutil.virtual_memory().percent
            elif metric_name == "disk_usage_percent":
                return psutil.disk_usage('/').percent
            elif metric_name == "response_time_ms":
                return 150.0  # Simulated response time
            elif metric_name == "error_rate_percent":
                return 2.5  # Simulated error rate
            elif metric_name == "component_status":
                return 1.0  # Simulated component status (1 = up, 0 = down)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting metric value for {metric_name}: {e}")
            return None
    
    def _evaluate_condition(self, current_value: float, condition: str, threshold: float) -> bool:
        """Evaluate alert condition"""
        try:
            if condition == ">":
                return current_value > threshold
            elif condition == "<":
                return current_value < threshold
            elif condition == ">=":
                return current_value >= threshold
            elif condition == "<=":
                return current_value <= threshold
            elif condition == "==":
                return current_value == threshold
            elif condition == "!=":
                return current_value != threshold
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False
    
    async def _create_alert(self, rule: AlertRule, current_value: float):
        """Create a new alert"""
        try:
            alert_id = f"{rule.rule_id}_{int(time.time())}"
            
            alert = Alert(
                alert_id=alert_id,
                rule_id=rule.rule_id,
                severity=rule.severity,
                message=f"{rule.name}: {rule.metric_name} is {current_value:.2f}, {rule.condition} {rule.threshold}",
                timestamp=datetime.now(),
                component="system",
                metric_name=rule.metric_name,
                current_value=current_value,
                threshold=rule.threshold
            )
            
            # Store alert
            self.active_alerts[alert_id] = alert
            
            # Create notifications
            await self._create_notifications(alert, rule)
            
            logger.warning(f"Alert created: {alert.message}")
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
    
    async def _resolve_alert(self, rule_id: str):
        """Resolve existing alert"""
        try:
            for alert_id, alert in self.active_alerts.items():
                if alert.rule_id == rule_id and alert.status == AlertStatus.ACTIVE:
                    alert.status = AlertStatus.RESOLVED
                    alert.resolved_at = datetime.now()
                    
                    logger.info(f"Alert resolved: {alert.alert_id}")
                    
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
    
    async def _create_notifications(self, alert: Alert, rule: AlertRule):
        """Create notifications for alert"""
        try:
            for channel in rule.notification_channels:
                if channel == NotificationChannel.EMAIL:
                    await self._create_email_notification(alert)
                elif channel == NotificationChannel.SMS:
                    await self._create_sms_notification(alert)
                elif channel == NotificationChannel.SLACK:
                    await self._create_slack_notification(alert)
                elif channel == NotificationChannel.WEBHOOK:
                    await self._create_webhook_notification(alert)
                elif channel == NotificationChannel.CONSOLE:
                    await self._create_console_notification(alert)
                    
        except Exception as e:
            logger.error(f"Error creating notifications: {e}")
    
    async def _create_email_notification(self, alert: Alert):
        """Create email notification"""
        try:
            email_config = self.config["notification_channels"]["email"]
            if not email_config["enabled"]:
                return
            
            notification = Notification(
                notification_id=f"email_{alert.alert_id}",
                alert_id=alert.alert_id,
                channel=NotificationChannel.EMAIL,
                recipient=email_config["recipients"][0],
                message=self._format_alert_message(alert),
                timestamp=datetime.now()
            )
            
            self.notifications.append(notification)
            
        except Exception as e:
            logger.error(f"Error creating email notification: {e}")
    
    async def _create_sms_notification(self, alert: Alert):
        """Create SMS notification"""
        try:
            sms_config = self.config["notification_channels"]["sms"]
            if not sms_config["enabled"]:
                return
            
            notification = Notification(
                notification_id=f"sms_{alert.alert_id}",
                alert_id=alert.alert_id,
                channel=NotificationChannel.SMS,
                recipient=sms_config["recipients"][0],
                message=self._format_alert_message(alert),
                timestamp=datetime.now()
            )
            
            self.notifications.append(notification)
            
        except Exception as e:
            logger.error(f"Error creating SMS notification: {e}")
    
    async def _create_slack_notification(self, alert: Alert):
        """Create Slack notification"""
        try:
            slack_config = self.config["notification_channels"]["slack"]
            if not slack_config["enabled"]:
                return
            
            notification = Notification(
                notification_id=f"slack_{alert.alert_id}",
                alert_id=alert.alert_id,
                channel=NotificationChannel.SLACK,
                recipient=slack_config["channel"],
                message=self._format_alert_message(alert),
                timestamp=datetime.now()
            )
            
            self.notifications.append(notification)
            
        except Exception as e:
            logger.error(f"Error creating Slack notification: {e}")
    
    async def _create_webhook_notification(self, alert: Alert):
        """Create webhook notification"""
        try:
            webhook_config = self.config["notification_channels"]["webhook"]
            if not webhook_config["enabled"]:
                return
            
            notification = Notification(
                notification_id=f"webhook_{alert.alert_id}",
                alert_id=alert.alert_id,
                channel=NotificationChannel.WEBHOOK,
                recipient=webhook_config["url"],
                message=self._format_alert_message(alert),
                timestamp=datetime.now()
            )
            
            self.notifications.append(notification)
            
        except Exception as e:
            logger.error(f"Error creating webhook notification: {e}")
    
    async def _create_console_notification(self, alert: Alert):
        """Create console notification"""
        try:
            notification = Notification(
                notification_id=f"console_{alert.alert_id}",
                alert_id=alert.alert_id,
                channel=NotificationChannel.CONSOLE,
                recipient="console",
                message=self._format_alert_message(alert),
                timestamp=datetime.now()
            )
            
            self.notifications.append(notification)
            
        except Exception as e:
            logger.error(f"Error creating console notification: {e}")
    
    def _format_alert_message(self, alert: Alert) -> str:
        """Format alert message"""
        try:
            severity_emoji = {
                AlertSeverity.LOW: "🟡",
                AlertSeverity.MEDIUM: "🟠",
                AlertSeverity.HIGH: "🔴",
                AlertSeverity.CRITICAL: "🚨"
            }
            
            emoji = severity_emoji.get(alert.severity, "⚠️")
            
            return f"{emoji} {alert.severity.value.upper()} ALERT\n\n" \
                   f"Rule: {alert.rule_id}\n" \
                   f"Message: {alert.message}\n" \
                   f"Timestamp: {alert.timestamp.isoformat()}\n" \
                   f"Component: {alert.component}\n" \
                   f"Current Value: {alert.current_value:.2f}\n" \
                   f"Threshold: {alert.threshold:.2f}"
                   
        except Exception as e:
            logger.error(f"Error formatting alert message: {e}")
            return f"Alert: {alert.message}"
    
    async def _process_notifications(self):
        """Process pending notifications"""
        try:
            while self.running:
                # Process pending notifications
                for notification in self.notifications:
                    if not notification.sent:
                        await self._send_notification(notification)
                
                # Wait for next processing
                await asyncio.sleep(5.0)
                
        except Exception as e:
            logger.error(f"Error processing notifications: {e}")
    
    async def _send_notification(self, notification: Notification):
        """Send notification"""
        try:
            if notification.channel == NotificationChannel.EMAIL:
                await self._send_email(notification)
            elif notification.channel == NotificationChannel.SMS:
                await self._send_sms(notification)
            elif notification.channel == NotificationChannel.SLACK:
                await self._send_slack(notification)
            elif notification.channel == NotificationChannel.WEBHOOK:
                await self._send_webhook(notification)
            elif notification.channel == NotificationChannel.CONSOLE:
                await self._send_console(notification)
            
            notification.sent = True
            notification.sent_at = datetime.now()
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            notification.error_message = str(e)
    
    async def _send_email(self, notification: Notification):
        """Send email notification"""
        try:
            email_config = self.config["notification_channels"]["email"]
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = email_config["from_email"]
            msg['To'] = notification.recipient
            msg['Subject'] = f"Alert: {notification.alert_id}"
            msg.attach(MIMEText(notification.message, 'plain'))
            
            # Send email
            server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
            server.starttls()
            server.login(email_config["username"], email_config["password"])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email notification sent: {notification.notification_id}")
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            raise
    
    async def _send_sms(self, notification: Notification):
        """Send SMS notification"""
        try:
            # Simulate SMS sending
            logger.info(f"SMS notification sent: {notification.notification_id}")
            
        except Exception as e:
            logger.error(f"Error sending SMS notification: {e}")
            raise
    
    async def _send_slack(self, notification: Notification):
        """Send Slack notification"""
        try:
            slack_config = self.config["notification_channels"]["slack"]
            
            payload = {
                "channel": notification.recipient,
                "username": slack_config["username"],
                "text": notification.message
            }
            
            response = requests.post(slack_config["webhook_url"], json=payload)
            response.raise_for_status()
            
            logger.info(f"Slack notification sent: {notification.notification_id}")
            
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            raise
    
    async def _send_webhook(self, notification: Notification):
        """Send webhook notification"""
        try:
            webhook_config = self.config["notification_channels"]["webhook"]
            
            payload = {
                "alert_id": notification.alert_id,
                "message": notification.message,
                "timestamp": notification.timestamp.isoformat()
            }
            
            response = requests.post(
                webhook_config["url"],
                json=payload,
                headers=webhook_config["headers"]
            )
            response.raise_for_status()
            
            logger.info(f"Webhook notification sent: {notification.notification_id}")
            
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
            raise
    
    async def _send_console(self, notification: Notification):
        """Send console notification"""
        try:
            print(f"CONSOLE ALERT: {notification.message}")
            logger.info(f"Console notification sent: {notification.notification_id}")
            
        except Exception as e:
            logger.error(f"Error sending console notification: {e}")
            raise
    
    async def _cleanup_old_alerts(self):
        """Clean up old alerts"""
        try:
            while self.running:
                # Remove alerts older than retention period
                retention_days = self.config["alerting"]["retention_days"]
                cutoff_date = datetime.now() - timedelta(days=retention_days)
                
                # Clean up active alerts
                alerts_to_remove = []
                for alert_id, alert in self.active_alerts.items():
                    if alert.timestamp < cutoff_date:
                        alerts_to_remove.append(alert_id)
                
                for alert_id in alerts_to_remove:
                    del self.active_alerts[alert_id]
                
                # Clean up notifications
                self.notifications = [
                    n for n in self.notifications 
                    if n.timestamp > cutoff_date
                ]
                
                # Wait for next cleanup
                await asyncio.sleep(3600)  # Run every hour
                
        except Exception as e:
            logger.error(f"Error cleaning up old alerts: {e}")
    
    def get_alerting_summary(self) -> Dict[str, Any]:
        """Get alerting system summary"""
        try:
            active_alerts = len([a for a in self.active_alerts.values() if a.status == AlertStatus.ACTIVE])
            total_alerts = len(self.active_alerts)
            total_notifications = len(self.notifications)
            sent_notifications = len([n for n in self.notifications if n.sent])
            
            return {
                "active_alerts": active_alerts,
                "total_alerts": total_alerts,
                "total_notifications": total_notifications,
                "sent_notifications": sent_notifications,
                "alert_rules": len(self.alert_rules),
                "enabled_rules": len([r for r in self.alert_rules.values() if r.enabled])
            }
            
        except Exception as e:
            logger.error(f"Error getting alerting summary: {e}")
            return {}
    
    def stop_alerting(self):
        """Stop the alerting system"""
        try:
            logger.info("Stopping production alerting system")
            self.running = False
        except Exception as e:
            logger.error(f"Error stopping alerting system: {e}")

async def main():
    """Main function for testing alerting system"""
    alerting_system = ProductionAlertingSystem()
    
    try:
        # Start alerting
        await alerting_system.start_alerting()
    except KeyboardInterrupt:
        logger.info("Alerting system stopped by user")
    finally:
        alerting_system.stop_alerting()

if __name__ == "__main__":
    asyncio.run(main())
