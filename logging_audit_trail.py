#!/usr/bin/env python3
"""
Logging and Audit Trail System for TelegramMoneyBot v8.0
Comprehensive logging, audit trail, and compliance system
"""

import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import hashlib
import threading
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import sys
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LogLevel(Enum):
    """Log levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AuditEventType(Enum):
    """Audit event types"""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"
    SECURITY_EVENT = "security_event"
    TRADING_EVENT = "trading_event"
    DATABASE_OPERATION = "database_operation"
    CONFIGURATION_CHANGE = "configuration_change"
    BACKUP_OPERATION = "backup_operation"
    RECOVERY_OPERATION = "recovery_operation"

class ComplianceLevel(Enum):
    """Compliance levels"""
    BASIC = "basic"
    STANDARD = "standard"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class AuditEvent:
    """Audit event record"""
    event_id: str
    timestamp: datetime
    event_type: AuditEventType
    level: LogLevel
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    event_description: str
    event_data: Dict[str, Any]
    compliance_level: ComplianceLevel
    retention_days: int
    encrypted: bool = False

@dataclass
class LogConfig:
    """Log configuration"""
    log_file: str
    max_size_mb: int
    backup_count: int
    rotation_type: str  # size, time
    rotation_interval: str  # daily, weekly, monthly
    compression: bool
    encryption: bool
    retention_days: int

class LoggingAuditTrail:
    """Logging and audit trail management system"""
    
    def __init__(self, config_path: str = "logging_audit_config.json"):
        self.config = self._load_config(config_path)
        self.audit_events: List[AuditEvent] = []
        self.loggers: Dict[str, logging.Logger] = {}
        self.audit_db_path = "data/audit_trail.db"
        self.running = False
        
        # Initialize logging system
        self._initialize_logging_system()
        
        # Initialize audit database
        self._initialize_audit_database()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load logging and audit configuration"""
        default_config = {
            "logging": {
                "application_log": {
                    "log_file": "logs/application.log",
                    "max_size_mb": 100,
                    "backup_count": 5,
                    "rotation_type": "size",
                    "rotation_interval": "daily",
                    "compression": True,
                    "encryption": False,
                    "retention_days": 30
                },
                "security_log": {
                    "log_file": "logs/security.log",
                    "max_size_mb": 50,
                    "backup_count": 10,
                    "rotation_type": "size",
                    "rotation_interval": "daily",
                    "compression": True,
                    "encryption": True,
                    "retention_days": 365
                },
                "trading_log": {
                    "log_file": "logs/trading.log",
                    "max_size_mb": 200,
                    "backup_count": 3,
                    "rotation_type": "size",
                    "rotation_interval": "daily",
                    "compression": True,
                    "encryption": True,
                    "retention_days": 2555  # 7 years
                },
                "system_log": {
                    "log_file": "logs/system.log",
                    "max_size_mb": 100,
                    "backup_count": 5,
                    "rotation_type": "size",
                    "rotation_interval": "daily",
                    "compression": True,
                    "encryption": False,
                    "retention_days": 90
                },
                "audit_log": {
                    "log_file": "logs/audit.log",
                    "max_size_mb": 50,
                    "backup_count": 20,
                    "rotation_type": "size",
                    "rotation_interval": "daily",
                    "compression": True,
                    "encryption": True,
                    "retention_days": 2555  # 7 years
                }
            },
            "audit_trail": {
                "enabled": True,
                "database_path": "data/audit_trail.db",
                "retention_days": 2555,  # 7 years
                "encryption_enabled": True,
                "integrity_check_enabled": True,
                "backup_enabled": True
            },
            "compliance": {
                "sox_compliance": True,
                "gdpr_compliance": True,
                "pci_compliance": False,
                "hipaa_compliance": False,
                "audit_retention_years": 7,
                "data_encryption_required": True,
                "access_logging_required": True
            },
            "monitoring": {
                "log_monitoring_enabled": True,
                "error_threshold": 10,
                "warning_threshold": 50,
                "alert_on_critical": True,
                "log_analysis_enabled": True
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
            logger.error(f"Error loading logging config: {e}")
            return default_config
    
    def _initialize_logging_system(self):
        """Initialize the logging system"""
        try:
            # Create logs directory
            Path("logs").mkdir(exist_ok=True)
            
            # Initialize loggers for each log type
            for log_name, log_config in self.config["logging"].items():
                self._create_logger(log_name, log_config)
            
            logger.info("Logging system initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing logging system: {e}")
    
    def _create_logger(self, log_name: str, log_config: Dict[str, Any]):
        """Create a logger with specific configuration"""
        try:
            # Create logger
            logger_obj = logging.getLogger(log_name)
            logger_obj.setLevel(logging.DEBUG)
            
            # Clear existing handlers
            logger_obj.handlers.clear()
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # Create file handler based on rotation type
            if log_config["rotation_type"] == "size":
                handler = RotatingFileHandler(
                    log_config["log_file"],
                    maxBytes=log_config["max_size_mb"] * 1024 * 1024,
                    backupCount=log_config["backup_count"]
                )
            else:  # time-based rotation
                handler = TimedRotatingFileHandler(
                    log_config["log_file"],
                    when=log_config["rotation_interval"],
                    backupCount=log_config["backup_count"]
                )
            
            # Set formatter
            handler.setFormatter(formatter)
            
            # Add handler to logger
            logger_obj.addHandler(handler)
            
            # Store logger
            self.loggers[log_name] = logger_obj
            
        except Exception as e:
            logger.error(f"Error creating logger {log_name}: {e}")
    
    def _initialize_audit_database(self):
        """Initialize audit trail database"""
        try:
            # Create database directory
            Path(self.audit_db_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Create audit database
            with sqlite3.connect(self.audit_db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_events (
                        event_id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        level TEXT NOT NULL,
                        user_id TEXT,
                        session_id TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        event_description TEXT NOT NULL,
                        event_data TEXT NOT NULL,
                        compliance_level TEXT NOT NULL,
                        retention_days INTEGER NOT NULL,
                        encrypted BOOLEAN DEFAULT FALSE,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON audit_events(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_compliance_level ON audit_events(compliance_level)")
                
                conn.commit()
            
            logger.info("Audit trail database initialized")
            
        except Exception as e:
            logger.error(f"Error initializing audit database: {e}")
    
    def log_event(self, log_name: str, level: LogLevel, message: str, **kwargs):
        """Log an event to a specific logger"""
        try:
            if log_name not in self.loggers:
                logger.error(f"Logger {log_name} not found")
                return
            
            logger_obj = self.loggers[log_name]
            
            # Get log level
            log_level = getattr(logging, level.value.upper())
            
            # Log the message
            logger_obj.log(log_level, message, extra=kwargs)
            
        except Exception as e:
            logger.error(f"Error logging event: {e}")
    
    def create_audit_event(self, event_type: AuditEventType, level: LogLevel,
                          event_description: str, user_id: Optional[str] = None,
                          session_id: Optional[str] = None, ip_address: Optional[str] = None,
                          user_agent: Optional[str] = None, event_data: Dict[str, Any] = None,
                          compliance_level: ComplianceLevel = ComplianceLevel.STANDARD) -> str:
        """Create an audit event"""
        try:
            # Generate event ID
            event_id = f"{event_type.value}_{int(time.time())}_{secrets.token_hex(8)}"
            
            # Create audit event
            audit_event = AuditEvent(
                event_id=event_id,
                timestamp=datetime.now(),
                event_type=event_type,
                level=level,
                user_id=user_id,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                event_description=event_description,
                event_data=event_data or {},
                compliance_level=compliance_level,
                retention_days=self._get_retention_days(compliance_level)
            )
            
            # Store audit event
            self.audit_events.append(audit_event)
            
            # Store in database
            self._store_audit_event(audit_event)
            
            # Log to appropriate logger
            self._log_audit_event(audit_event)
            
            return event_id
            
        except Exception as e:
            logger.error(f"Error creating audit event: {e}")
            return ""
    
    def _get_retention_days(self, compliance_level: ComplianceLevel) -> int:
        """Get retention days based on compliance level"""
        retention_map = {
            ComplianceLevel.BASIC: 30,
            ComplianceLevel.STANDARD: 365,
            ComplianceLevel.HIGH: 1095,  # 3 years
            ComplianceLevel.CRITICAL: 2555  # 7 years
        }
        return retention_map.get(compliance_level, 365)
    
    def _store_audit_event(self, audit_event: AuditEvent):
        """Store audit event in database"""
        try:
            with sqlite3.connect(self.audit_db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO audit_events (
                        event_id, timestamp, event_type, level, user_id, session_id,
                        ip_address, user_agent, event_description, event_data,
                        compliance_level, retention_days, encrypted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    audit_event.event_id,
                    audit_event.timestamp.isoformat(),
                    audit_event.event_type.value,
                    audit_event.level.value,
                    audit_event.user_id,
                    audit_event.session_id,
                    audit_event.ip_address,
                    audit_event.user_agent,
                    audit_event.event_description,
                    json.dumps(audit_event.event_data),
                    audit_event.compliance_level.value,
                    audit_event.retention_days,
                    audit_event.encrypted
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing audit event: {e}")
    
    def _log_audit_event(self, audit_event: AuditEvent):
        """Log audit event to appropriate logger"""
        try:
            # Determine which logger to use based on event type
            if audit_event.event_type in [AuditEventType.SECURITY_EVENT, AuditEventType.USER_LOGIN, AuditEventType.USER_LOGOUT]:
                log_name = "security_log"
            elif audit_event.event_type == AuditEventType.TRADING_EVENT:
                log_name = "trading_log"
            elif audit_event.event_type == AuditEventType.SYSTEM_EVENT:
                log_name = "system_log"
            else:
                log_name = "audit_log"
            
            # Create log message
            log_message = f"[{audit_event.event_id}] {audit_event.event_description}"
            if audit_event.user_id:
                log_message += f" (User: {audit_event.user_id})"
            if audit_event.ip_address:
                log_message += f" (IP: {audit_event.ip_address})"
            
            # Log the event
            self.log_event(log_name, audit_event.level, log_message, extra={
                "event_id": audit_event.event_id,
                "event_type": audit_event.event_type.value,
                "user_id": audit_event.user_id,
                "session_id": audit_event.session_id,
                "ip_address": audit_event.ip_address,
                "event_data": audit_event.event_data
            })
            
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
    
    async def start_audit_service(self):
        """Start the audit service"""
        logger.info("Starting audit trail service...")
        self.running = True
        
        try:
            while self.running:
                # Clean up old audit events
                await self._cleanup_old_audit_events()
                
                # Verify audit database integrity
                await self._verify_audit_integrity()
                
                # Monitor log files
                await self._monitor_log_files()
                
                # Wait for next check
                await asyncio.sleep(300)  # Check every 5 minutes
                
        except KeyboardInterrupt:
            logger.info("Stopping audit service...")
            self.running = False
        except Exception as e:
            logger.error(f"Error in audit service: {e}")
            self.running = False
    
    async def _cleanup_old_audit_events(self):
        """Clean up old audit events based on retention policy"""
        try:
            with sqlite3.connect(self.audit_db_path) as conn:
                # Get current time
                current_time = datetime.now()
                
                # Find events to delete
                cursor = conn.execute("""
                    SELECT event_id, timestamp, retention_days 
                    FROM audit_events 
                    WHERE datetime(timestamp) < datetime('now', '-' || retention_days || ' days')
                """)
                
                events_to_delete = cursor.fetchall()
                
                # Delete old events
                for event_id, timestamp, retention_days in events_to_delete:
                    conn.execute("DELETE FROM audit_events WHERE event_id = ?", (event_id,))
                
                conn.commit()
                
                if events_to_delete:
                    logger.info(f"Cleaned up {len(events_to_delete)} old audit events")
                
        except Exception as e:
            logger.error(f"Error cleaning up old audit events: {e}")
    
    async def _verify_audit_integrity(self):
        """Verify audit database integrity"""
        try:
            with sqlite3.connect(self.audit_db_path) as conn:
                # Check database integrity
                cursor = conn.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                
                if result[0] != 'ok':
                    logger.error(f"Audit database integrity check failed: {result[0]}")
                    return False
                
                # Check for missing indexes
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
                indexes = [row[0] for row in cursor.fetchall()]
                
                required_indexes = ['idx_timestamp', 'idx_event_type', 'idx_user_id', 'idx_compliance_level']
                missing_indexes = [idx for idx in required_indexes if idx not in indexes]
                
                if missing_indexes:
                    logger.warning(f"Missing indexes: {missing_indexes}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error verifying audit integrity: {e}")
            return False
    
    async def _monitor_log_files(self):
        """Monitor log files for issues"""
        try:
            for log_name, log_config in self.config["logging"].items():
                log_file = Path(log_config["log_file"])
                
                if log_file.exists():
                    # Check file size
                    file_size_mb = log_file.stat().st_size / (1024 * 1024)
                    max_size_mb = log_config["max_size_mb"]
                    
                    if file_size_mb > max_size_mb * 0.9:  # 90% of max size
                        logger.warning(f"Log file {log_name} is approaching size limit: {file_size_mb:.2f}MB / {max_size_mb}MB")
                    
                    # Check for errors in log file
                    error_count = await self._count_errors_in_log(log_file)
                    if error_count > self.config["monitoring"]["error_threshold"]:
                        logger.warning(f"High error count in {log_name}: {error_count} errors")
                
        except Exception as e:
            logger.error(f"Error monitoring log files: {e}")
    
    async def _count_errors_in_log(self, log_file: Path) -> int:
        """Count errors in log file"""
        try:
            error_count = 0
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if 'ERROR' in line or 'CRITICAL' in line:
                        error_count += 1
            return error_count
        except Exception as e:
            logger.error(f"Error counting errors in log file: {e}")
            return 0
    
    def get_audit_report(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate audit report for date range"""
        try:
            with sqlite3.connect(self.audit_db_path) as conn:
                # Get audit events in date range
                cursor = conn.execute("""
                    SELECT event_type, level, COUNT(*) as count
                    FROM audit_events 
                    WHERE datetime(timestamp) BETWEEN ? AND ?
                    GROUP BY event_type, level
                    ORDER BY count DESC
                """, (start_date.isoformat(), end_date.isoformat()))
                
                event_summary = cursor.fetchall()
                
                # Get user activity
                cursor = conn.execute("""
                    SELECT user_id, COUNT(*) as activity_count
                    FROM audit_events 
                    WHERE datetime(timestamp) BETWEEN ? AND ? AND user_id IS NOT NULL
                    GROUP BY user_id
                    ORDER BY activity_count DESC
                """, (start_date.isoformat(), end_date.isoformat()))
                
                user_activity = cursor.fetchall()
                
                # Get security events
                cursor = conn.execute("""
                    SELECT COUNT(*) as security_events
                    FROM audit_events 
                    WHERE datetime(timestamp) BETWEEN ? AND ? AND event_type = 'security_event'
                """, (start_date.isoformat(), end_date.isoformat()))
                
                security_events = cursor.fetchone()[0]
                
                return {
                    "report_period": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    },
                    "event_summary": event_summary,
                    "user_activity": user_activity,
                    "security_events": security_events,
                    "total_events": sum(count for _, _, count in event_summary)
                }
                
        except Exception as e:
            logger.error(f"Error generating audit report: {e}")
            return {}
    
    def get_logging_status(self) -> Dict[str, Any]:
        """Get logging system status"""
        return {
            "running": self.running,
            "loggers": len(self.loggers),
            "audit_events": len(self.audit_events),
            "audit_database_path": self.audit_db_path,
            "compliance_enabled": self.config["audit_trail"]["enabled"],
            "encryption_enabled": self.config["audit_trail"]["encryption_enabled"]
        }

async def main():
    """Main function for testing logging and audit trail"""
    audit_system = LoggingAuditTrail()
    
    # Create some test audit events
    audit_system.create_audit_event(
        event_type=AuditEventType.USER_LOGIN,
        level=LogLevel.INFO,
        event_description="User login successful",
        user_id="test_user",
        ip_address="127.0.0.1",
        compliance_level=ComplianceLevel.STANDARD
    )
    
    audit_system.create_audit_event(
        event_type=AuditEventType.TRADING_EVENT,
        level=LogLevel.INFO,
        event_description="Trade executed",
        user_id="trader",
        event_data={"symbol": "BTCUSDc", "side": "buy", "quantity": 0.01},
        compliance_level=ComplianceLevel.HIGH
    )
    
    # Start audit service
    await audit_system.start_audit_service()

if __name__ == "__main__":
    asyncio.run(main())
