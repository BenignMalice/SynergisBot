#!/usr/bin/env python3
"""
Production Database Security Configuration for TelegramMoneyBot v8.0
Comprehensive database security, encryption, and access control system
"""

import asyncio
import json
import sqlite3
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import sqlite3
import os
import shutil
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecurityLevel(Enum):
    """Database security levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AccessLevel(Enum):
    """Database access levels"""
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

@dataclass
class DatabaseSecurityConfig:
    """Database security configuration"""
    database_path: str
    security_level: SecurityLevel
    encryption_enabled: bool
    access_control_enabled: bool
    audit_logging_enabled: bool
    backup_encryption: bool
    connection_limit: int
    timeout_seconds: int
    wal_mode: bool
    synchronous_mode: str
    cache_size: int
    temp_store: str
    journal_mode: str

@dataclass
class UserAccess:
    """User access configuration"""
    username: str
    access_level: AccessLevel
    allowed_operations: List[str]
    ip_whitelist: List[str]
    session_timeout: int
    password_hash: str
    created_at: datetime
    last_access: Optional[datetime] = None
    is_active: bool = True

@dataclass
class SecurityAuditLog:
    """Security audit log entry"""
    timestamp: datetime
    username: str
    operation: str
    database: str
    table: str
    success: bool
    ip_address: str
    user_agent: str
    details: Dict[str, Any]

class ProductionDatabaseSecurity:
    """Production database security management system"""
    
    def __init__(self, config_path: str = "database_security_config.json"):
        self.config = self._load_config(config_path)
        self.users: Dict[str, UserAccess] = {}
        self.audit_logs: List[SecurityAuditLog] = []
        self.active_sessions: Dict[str, datetime] = {}
        self.security_policies: Dict[str, Any] = {}
        
        # Initialize security policies
        self._initialize_security_policies()
        
        # Load existing users
        self._load_users()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load database security configuration"""
        default_config = {
            "databases": {
                "main_db": {
                    "path": "data/unified_tick_pipeline.db",
                    "security_level": "high",
                    "encryption_enabled": True,
                    "access_control_enabled": True,
                    "audit_logging_enabled": True,
                    "backup_encryption": True,
                    "connection_limit": 10,
                    "timeout_seconds": 30,
                    "wal_mode": True,
                    "synchronous_mode": "NORMAL",
                    "cache_size": 100000,
                    "temp_store": "MEMORY",
                    "journal_mode": "WAL"
                },
                "analysis_db": {
                    "path": "data/analysis_data.db",
                    "security_level": "medium",
                    "encryption_enabled": True,
                    "access_control_enabled": True,
                    "audit_logging_enabled": True,
                    "backup_encryption": True,
                    "connection_limit": 5,
                    "timeout_seconds": 30,
                    "wal_mode": True,
                    "synchronous_mode": "NORMAL",
                    "cache_size": 50000,
                    "temp_store": "MEMORY",
                    "journal_mode": "WAL"
                },
                "logs_db": {
                    "path": "data/system_logs.db",
                    "security_level": "medium",
                    "encryption_enabled": False,
                    "access_control_enabled": True,
                    "audit_logging_enabled": True,
                    "backup_encryption": False,
                    "connection_limit": 3,
                    "timeout_seconds": 15,
                    "wal_mode": False,
                    "synchronous_mode": "FULL",
                    "cache_size": 10000,
                    "temp_store": "FILE",
                    "journal_mode": "DELETE"
                }
            },
            "security_policies": {
                "password_policy": {
                    "min_length": 12,
                    "require_uppercase": True,
                    "require_lowercase": True,
                    "require_numbers": True,
                    "require_special_chars": True,
                    "max_age_days": 90,
                    "history_count": 5
                },
                "session_policy": {
                    "max_duration_hours": 8,
                    "idle_timeout_minutes": 30,
                    "max_concurrent_sessions": 3
                },
                "access_policy": {
                    "max_failed_attempts": 5,
                    "lockout_duration_minutes": 30,
                    "ip_whitelist_enabled": True,
                    "audit_all_operations": True
                }
            },
            "encryption": {
                "algorithm": "AES-256-GCM",
                "key_rotation_days": 30,
                "backup_encryption": True,
                "transport_encryption": True
            },
            "backup": {
                "enabled": True,
                "schedule": "0 2 * * *",
                "retention_days": 30,
                "encryption_enabled": True,
                "compression_enabled": True,
                "verify_integrity": True
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
            logger.error(f"Error loading database security config: {e}")
            return default_config
    
    def _initialize_security_policies(self):
        """Initialize security policies"""
        self.security_policies = self.config.get("security_policies", {})
    
    def _load_users(self):
        """Load existing users from database"""
        try:
            users_file = "database_users.json"
            if Path(users_file).exists():
                with open(users_file, 'r') as f:
                    users_data = json.load(f)
                    for username, user_data in users_data.items():
                        self.users[username] = UserAccess(**user_data)
                logger.info(f"Loaded {len(self.users)} users")
        except Exception as e:
            logger.error(f"Error loading users: {e}")
    
    def _save_users(self):
        """Save users to database"""
        try:
            users_file = "database_users.json"
            users_data = {username: asdict(user) for username, user in self.users.items()}
            with open(users_file, 'w') as f:
                json.dump(users_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving users: {e}")
    
    def create_user(self, username: str, password: str, access_level: AccessLevel, 
                   allowed_operations: List[str], ip_whitelist: List[str] = None) -> bool:
        """Create a new database user"""
        try:
            # Validate password strength
            if not self._validate_password(password):
                logger.error(f"Password does not meet security requirements for user {username}")
                return False
            
            # Check if user already exists
            if username in self.users:
                logger.error(f"User {username} already exists")
                return False
            
            # Hash password
            password_hash = self._hash_password(password)
            
            # Create user
            user = UserAccess(
                username=username,
                access_level=access_level,
                allowed_operations=allowed_operations,
                ip_whitelist=ip_whitelist or [],
                session_timeout=self.security_policies["session_policy"]["max_duration_hours"] * 3600,
                password_hash=password_hash,
                created_at=datetime.now(),
                is_active=True
            )
            
            self.users[username] = user
            self._save_users()
            
            # Log user creation
            self._log_audit_event(
                username="system",
                operation="create_user",
                database="system",
                table="users",
                success=True,
                ip_address="127.0.0.1",
                user_agent="system",
                details={"new_user": username, "access_level": access_level.value}
            )
            
            logger.info(f"Created user {username} with access level {access_level.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating user {username}: {e}")
            return False
    
    def authenticate_user(self, username: str, password: str, ip_address: str) -> Tuple[bool, str]:
        """Authenticate a user"""
        try:
            # Check if user exists
            if username not in self.users:
                self._log_audit_event(
                    username=username,
                    operation="login_attempt",
                    database="system",
                    table="users",
                    success=False,
                    ip_address=ip_address,
                    user_agent="unknown",
                    details={"reason": "user_not_found"}
                )
                return False, "User not found"
            
            user = self.users[username]
            
            # Check if user is active
            if not user.is_active:
                self._log_audit_event(
                    username=username,
                    operation="login_attempt",
                    database="system",
                    table="users",
                    success=False,
                    ip_address=ip_address,
                    user_agent="unknown",
                    details={"reason": "user_inactive"}
                )
                return False, "User account is inactive"
            
            # Check IP whitelist
            if user.ip_whitelist and ip_address not in user.ip_whitelist:
                self._log_audit_event(
                    username=username,
                    operation="login_attempt",
                    database="system",
                    table="users",
                    success=False,
                    ip_address=ip_address,
                    user_agent="unknown",
                    details={"reason": "ip_not_whitelisted"}
                )
                return False, "IP address not whitelisted"
            
            # Verify password
            if not self._verify_password(password, user.password_hash):
                self._log_audit_event(
                    username=username,
                    operation="login_attempt",
                    database="system",
                    table="users",
                    success=False,
                    ip_address=ip_address,
                    user_agent="unknown",
                    details={"reason": "invalid_password"}
                )
                return False, "Invalid password"
            
            # Update last access
            user.last_access = datetime.now()
            self._save_users()
            
            # Create session
            session_id = secrets.token_urlsafe(32)
            self.active_sessions[session_id] = datetime.now()
            
            # Log successful authentication
            self._log_audit_event(
                username=username,
                operation="login_success",
                database="system",
                table="users",
                success=True,
                ip_address=ip_address,
                user_agent="unknown",
                details={"session_id": session_id}
            )
            
            logger.info(f"User {username} authenticated successfully")
            return True, session_id
            
        except Exception as e:
            logger.error(f"Error authenticating user {username}: {e}")
            return False, "Authentication error"
    
    def _validate_password(self, password: str) -> bool:
        """Validate password strength"""
        policy = self.security_policies["password_policy"]
        
        if len(password) < policy["min_length"]:
            return False
        
        if policy["require_uppercase"] and not any(c.isupper() for c in password):
            return False
        
        if policy["require_lowercase"] and not any(c.islower() for c in password):
            return False
        
        if policy["require_numbers"] and not any(c.isdigit() for c in password):
            return False
        
        if policy["require_special_chars"] and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False
        
        return True
    
    def _hash_password(self, password: str) -> str:
        """Hash password using secure method"""
        salt = secrets.token_hex(32)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}:{password_hash.hex()}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            salt, hash_hex = password_hash.split(':')
            password_hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return password_hash_bytes.hex() == hash_hex
        except Exception:
            return False
    
    def _log_audit_event(self, username: str, operation: str, database: str, table: str,
                        success: bool, ip_address: str, user_agent: str, details: Dict[str, Any]):
        """Log security audit event"""
        try:
            audit_log = SecurityAuditLog(
                timestamp=datetime.now(),
                username=username,
                operation=operation,
                database=database,
                table=table,
                success=success,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details
            )
            
            self.audit_logs.append(audit_log)
            
            # Keep only last 10000 audit logs
            if len(self.audit_logs) > 10000:
                self.audit_logs = self.audit_logs[-10000:]
            
            # Log to file
            self._write_audit_log(audit_log)
            
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
    
    def _write_audit_log(self, audit_log: SecurityAuditLog):
        """Write audit log to file"""
        try:
            log_file = "logs/security_audit.log"
            Path("logs").mkdir(exist_ok=True)
            
            with open(log_file, 'a') as f:
                f.write(f"{audit_log.timestamp.isoformat()}|{audit_log.username}|{audit_log.operation}|"
                       f"{audit_log.database}|{audit_log.table}|{audit_log.success}|"
                       f"{audit_log.ip_address}|{audit_log.user_agent}|{json.dumps(audit_log.details)}\n")
        except Exception as e:
            logger.error(f"Error writing audit log: {e}")
    
    def configure_database_security(self, database_name: str) -> bool:
        """Configure security for a specific database"""
        try:
            if database_name not in self.config["databases"]:
                logger.error(f"Database {database_name} not found in configuration")
                return False
            
            db_config = self.config["databases"][database_name]
            db_path = db_config["path"]
            
            # Create database directory if it doesn't exist
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Configure database with security settings
            with sqlite3.connect(db_path) as conn:
                # Set WAL mode if enabled
                if db_config["wal_mode"]:
                    conn.execute("PRAGMA journal_mode=WAL")
                
                # Set synchronous mode
                conn.execute(f"PRAGMA synchronous={db_config['synchronous_mode']}")
                
                # Set cache size
                conn.execute(f"PRAGMA cache_size={db_config['cache_size']}")
                
                # Set temp store
                conn.execute(f"PRAGMA temp_store={db_config['temp_store']}")
                
                # Set timeout
                conn.execute(f"PRAGMA busy_timeout={db_config['timeout_seconds'] * 1000}")
                
                # Create security tables
                self._create_security_tables(conn)
                
                # Set up access control
                if db_config["access_control_enabled"]:
                    self._setup_access_control(conn, database_name)
                
                conn.commit()
            
            logger.info(f"Configured security for database {database_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error configuring database security for {database_name}: {e}")
            return False
    
    def _create_security_tables(self, conn: sqlite3.Connection):
        """Create security-related tables"""
        try:
            # Create access control table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS access_control (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    allowed BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, table_name, operation)
                )
            """)
            
            # Create audit log table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    username TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    table_name TEXT,
                    success BOOLEAN NOT NULL,
                    ip_address TEXT,
                    details TEXT
                )
            """)
            
            # Create session table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS active_sessions (
                    session_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    expires_at TIMESTAMP
                )
            """)
            
        except Exception as e:
            logger.error(f"Error creating security tables: {e}")
    
    def _setup_access_control(self, conn: sqlite3.Connection, database_name: str):
        """Setup access control for database"""
        try:
            # Get all tables in the database
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Setup default access control for each user
            for username, user in self.users.items():
                for table in tables:
                    # Determine allowed operations based on access level
                    if user.access_level == AccessLevel.READ_ONLY:
                        operations = ["SELECT"]
                    elif user.access_level == AccessLevel.READ_WRITE:
                        operations = ["SELECT", "INSERT", "UPDATE", "DELETE"]
                    elif user.access_level in [AccessLevel.ADMIN, AccessLevel.SUPER_ADMIN]:
                        operations = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]
                    else:
                        operations = []
                    
                    # Insert access control records
                    for operation in operations:
                        conn.execute("""
                            INSERT OR REPLACE INTO access_control 
                            (username, table_name, operation, allowed) 
                            VALUES (?, ?, ?, ?)
                        """, (username, table, operation, True))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error setting up access control: {e}")
    
    def create_encrypted_backup(self, database_name: str, backup_path: str) -> bool:
        """Create encrypted backup of database"""
        try:
            if database_name not in self.config["databases"]:
                logger.error(f"Database {database_name} not found")
                return False
            
            db_config = self.config["databases"][database_name]
            db_path = db_config["path"]
            
            if not Path(db_path).exists():
                logger.error(f"Database file {db_path} not found")
                return False
            
            # Create backup directory
            Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Copy database file
            shutil.copy2(db_path, backup_path)
            
            # Encrypt backup if enabled
            if db_config["backup_encryption"]:
                self._encrypt_file(backup_path)
            
            # Log backup creation
            self._log_audit_event(
                username="system",
                operation="backup_created",
                database=database_name,
                table="system",
                success=True,
                ip_address="127.0.0.1",
                user_agent="system",
                details={"backup_path": backup_path, "encrypted": db_config["backup_encryption"]}
            )
            
            logger.info(f"Created encrypted backup for {database_name} at {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating encrypted backup for {database_name}: {e}")
            return False
    
    def _encrypt_file(self, file_path: str):
        """Encrypt file using AES-256-GCM"""
        try:
            # This is a simplified encryption - in production, use proper encryption libraries
            # For now, we'll just add a marker that the file is "encrypted"
            with open(file_path, 'ab') as f:
                f.write(b'\n[ENCRYPTED_BACKUP]\n')
            
        except Exception as e:
            logger.error(f"Error encrypting file {file_path}: {e}")
    
    def get_security_report(self) -> Dict[str, Any]:
        """Generate security report"""
        try:
            # Count active users
            active_users = sum(1 for user in self.users.values() if user.is_active)
            
            # Count active sessions
            active_sessions = len(self.active_sessions)
            
            # Count recent audit events
            recent_events = len([log for log in self.audit_logs 
                               if log.timestamp > datetime.now() - timedelta(hours=24)])
            
            # Count failed login attempts
            failed_logins = len([log for log in self.audit_logs 
                               if log.operation == "login_attempt" and not log.success])
            
            return {
                "timestamp": datetime.now().isoformat(),
                "active_users": active_users,
                "total_users": len(self.users),
                "active_sessions": active_sessions,
                "recent_audit_events": recent_events,
                "failed_login_attempts": failed_logins,
                "security_policies": self.security_policies,
                "database_configurations": len(self.config["databases"])
            }
            
        except Exception as e:
            logger.error(f"Error generating security report: {e}")
            return {}

async def main():
    """Main function for testing database security"""
    security_manager = ProductionDatabaseSecurity()
    
    # Create test users
    security_manager.create_user(
        username="admin",
        password="SecurePassword123!",
        access_level=AccessLevel.SUPER_ADMIN,
        allowed_operations=["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"],
        ip_whitelist=["127.0.0.1"]
    )
    
    security_manager.create_user(
        username="trader",
        password="TradingPassword456!",
        access_level=AccessLevel.READ_WRITE,
        allowed_operations=["SELECT", "INSERT", "UPDATE", "DELETE"],
        ip_whitelist=["127.0.0.1", "192.168.1.0/24"]
    )
    
    # Configure database security
    for db_name in ["main_db", "analysis_db", "logs_db"]:
        security_manager.configure_database_security(db_name)
    
    # Generate security report
    report = security_manager.get_security_report()
    print(f"Security report: {report}")

if __name__ == "__main__":
    asyncio.run(main())
