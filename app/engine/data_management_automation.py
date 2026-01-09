"""
Data Management Automation
Automated data management and optimization for production
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
import os
import shutil
from collections import deque
import json
import gzip
import sqlite3

logger = logging.getLogger(__name__)

class DataRetentionPolicy(Enum):
    """Data retention policies"""
    KEEP_ALL = "keep_all"
    COMPRESS_OLD = "compress_old"
    DELETE_OLD = "delete_old"
    ARCHIVE_OLD = "archive_old"

class DataOperation(Enum):
    """Data operations"""
    BACKUP = "backup"
    COMPRESS = "compress"
    DELETE = "delete"
    ARCHIVE = "archive"
    OPTIMIZE = "optimize"
    VACUUM = "vacuum"

@dataclass
class DataManagementTask:
    """Data management task"""
    task_id: str
    operation: DataOperation
    target_path: str
    priority: int
    created_at: int
    status: str
    details: Dict[str, Any]

@dataclass
class DataRetentionRule:
    """Data retention rule"""
    table_name: str
    retention_days: int
    policy: DataRetentionPolicy
    compression_level: int = 6
    archive_path: Optional[str] = None

class DataManagementAutomation:
    """Automated data management system"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.symbol = symbol_config.get('symbol', 'unknown')
        
        # Data management configuration
        self.data_config = symbol_config.get('data_config', {})
        self.retention_rules = self.data_config.get('retention_rules', {})
        self.backup_config = self.data_config.get('backup_config', {})
        self.compression_config = self.data_config.get('compression_config', {})
        
        # Default retention rules
        self.default_rules = {
            'raw_ticks': DataRetentionRule('raw_ticks', 7, DataRetentionPolicy.DELETE_OLD),
            'ohlcv_bars': DataRetentionRule('ohlcv_bars', 30, DataRetentionPolicy.COMPRESS_OLD),
            'market_structure': DataRetentionRule('market_structure', 90, DataRetentionPolicy.ARCHIVE_OLD),
            'trade_history': DataRetentionRule('trade_history', 365, DataRetentionPolicy.KEEP_ALL),
            'performance_metrics': DataRetentionRule('performance_metrics', 180, DataRetentionPolicy.COMPRESS_OLD)
        }
        
        # Task management
        self.task_queue = deque()
        self.active_tasks = {}
        self.completed_tasks = deque(maxlen=1000)
        self.automation_active = False
        self.automation_thread = None
        
        # Database paths
        self.db_paths = {
            'main': 'data/mtf_trading_data.db',
            'trade_management': 'data/trade_management.db',
            'backup': 'data/backups/',
            'archive': 'data/archives/'
        }
        
    def start_automation(self):
        """Start data management automation"""
        try:
            if not self.automation_active:
                self.automation_active = True
                self.automation_thread = threading.Thread(target=self._automation_loop, daemon=True)
                self.automation_thread.start()
                logger.info(f"Data management automation started for {self.symbol}")
                
        except Exception as e:
            logger.error(f"Error starting automation: {e}")
    
    def stop_automation(self):
        """Stop data management automation"""
        try:
            if self.automation_active:
                self.automation_active = False
                if self.automation_thread:
                    self.automation_thread.join(timeout=1.0)
                logger.info(f"Data management automation stopped for {self.symbol}")
                
        except Exception as e:
            logger.error(f"Error stopping automation: {e}")
    
    def _automation_loop(self):
        """Main automation loop"""
        while self.automation_active:
            try:
                # Process pending tasks
                self._process_tasks()
                
                # Check for scheduled operations
                self._check_scheduled_operations()
                
                # Sleep for automation interval
                time.sleep(60.0)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in automation loop: {e}")
                time.sleep(300.0)  # Wait 5 minutes on error
    
    def _process_tasks(self):
        """Process pending data management tasks"""
        try:
            while self.task_queue:
                task = self.task_queue.popleft()
                self.active_tasks[task.task_id] = task
                
                # Execute task
                success = self._execute_task(task)
                
                # Update task status
                task.status = 'completed' if success else 'failed'
                self.completed_tasks.append(task)
                
                if task.task_id in self.active_tasks:
                    del self.active_tasks[task.task_id]
                
        except Exception as e:
            logger.error(f"Error processing tasks: {e}")
    
    def _execute_task(self, task: DataManagementTask) -> bool:
        """Execute a data management task"""
        try:
            if task.operation == DataOperation.BACKUP:
                return self._backup_database(task.target_path)
            elif task.operation == DataOperation.COMPRESS:
                return self._compress_data(task.target_path, task.details)
            elif task.operation == DataOperation.DELETE:
                return self._delete_old_data(task.target_path, task.details)
            elif task.operation == DataOperation.ARCHIVE:
                return self._archive_data(task.target_path, task.details)
            elif task.operation == DataOperation.OPTIMIZE:
                return self._optimize_database(task.target_path)
            elif task.operation == DataOperation.VACUUM:
                return self._vacuum_database(task.target_path)
            else:
                logger.warning(f"Unknown operation: {task.operation}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing task {task.task_id}: {e}")
            return False
    
    def _backup_database(self, db_path: str) -> bool:
        """Backup database"""
        try:
            if not os.path.exists(db_path):
                logger.warning(f"Database not found: {db_path}")
                return False
            
            # Create backup directory
            backup_dir = self.db_paths['backup']
            os.makedirs(backup_dir, exist_ok=True)
            
            # Generate backup filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{os.path.basename(db_path)}_{timestamp}.db"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Copy database
            shutil.copy2(db_path, backup_path)
            
            # Compress backup
            compressed_path = f"{backup_path}.gz"
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove uncompressed backup
            os.remove(backup_path)
            
            logger.info(f"Database backed up: {backup_path} -> {compressed_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error backing up database: {e}")
            return False
    
    def _compress_data(self, table_name: str, details: Dict[str, Any]) -> bool:
        """Compress old data"""
        try:
            # This would typically compress old data in the database
            # For now, we'll simulate the operation
            logger.info(f"Compressing data for table: {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error compressing data: {e}")
            return False
    
    def _delete_old_data(self, table_name: str, details: Dict[str, Any]) -> bool:
        """Delete old data based on retention rules"""
        try:
            retention_days = details.get('retention_days', 30)
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            cutoff_timestamp = int(cutoff_date.timestamp() * 1000)
            
            # This would typically delete old data from the database
            # For now, we'll simulate the operation
            logger.info(f"Deleting old data from {table_name} before {cutoff_date}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting old data: {e}")
            return False
    
    def _archive_data(self, table_name: str, details: Dict[str, Any]) -> bool:
        """Archive old data"""
        try:
            # This would typically archive old data to a separate location
            # For now, we'll simulate the operation
            logger.info(f"Archiving data for table: {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error archiving data: {e}")
            return False
    
    def _optimize_database(self, db_path: str) -> bool:
        """Optimize database"""
        try:
            if not os.path.exists(db_path):
                logger.warning(f"Database not found: {db_path}")
                return False
            
            # Connect to database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Optimize database
            cursor.execute("PRAGMA optimize")
            cursor.execute("ANALYZE")
            
            conn.commit()
            conn.close()
            
            logger.info(f"Database optimized: {db_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            return False
    
    def _vacuum_database(self, db_path: str) -> bool:
        """Vacuum database to reclaim space"""
        try:
            if not os.path.exists(db_path):
                logger.warning(f"Database not found: {db_path}")
                return False
            
            # Connect to database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Vacuum database
            cursor.execute("VACUUM")
            
            conn.commit()
            conn.close()
            
            logger.info(f"Database vacuumed: {db_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error vacuuming database: {e}")
            return False
    
    def _check_scheduled_operations(self):
        """Check for scheduled data management operations"""
        try:
            current_time = datetime.now(timezone.utc)
            
            # Check if it's time for daily backup
            if current_time.hour == 2 and current_time.minute == 0:  # 2:00 AM
                self._schedule_daily_backup()
            
            # Check if it's time for weekly optimization
            if current_time.weekday() == 0 and current_time.hour == 3 and current_time.minute == 0:  # Monday 3:00 AM
                self._schedule_weekly_optimization()
            
            # Check if it's time for monthly cleanup
            if current_time.day == 1 and current_time.hour == 4 and current_time.minute == 0:  # 1st of month 4:00 AM
                self._schedule_monthly_cleanup()
                
        except Exception as e:
            logger.error(f"Error checking scheduled operations: {e}")
    
    def _schedule_daily_backup(self):
        """Schedule daily backup"""
        try:
            for db_path in self.db_paths.values():
                if db_path.endswith('.db'):
                    task = DataManagementTask(
                        task_id=f"backup_{int(time.time())}",
                        operation=DataOperation.BACKUP,
                        target_path=db_path,
                        priority=1,
                        created_at=int(time.time()),
                        status='pending',
                        details={}
                    )
                    self.task_queue.append(task)
            
            logger.info("Daily backup scheduled")
            
        except Exception as e:
            logger.error(f"Error scheduling daily backup: {e}")
    
    def _schedule_weekly_optimization(self):
        """Schedule weekly optimization"""
        try:
            for db_path in self.db_paths.values():
                if db_path.endswith('.db'):
                    task = DataManagementTask(
                        task_id=f"optimize_{int(time.time())}",
                        operation=DataOperation.OPTIMIZE,
                        target_path=db_path,
                        priority=2,
                        created_at=int(time.time()),
                        status='pending',
                        details={}
                    )
                    self.task_queue.append(task)
            
            logger.info("Weekly optimization scheduled")
            
        except Exception as e:
            logger.error(f"Error scheduling weekly optimization: {e}")
    
    def _schedule_monthly_cleanup(self):
        """Schedule monthly cleanup"""
        try:
            # Apply retention rules
            for table_name, rule in self.default_rules.items():
                if rule.policy == DataRetentionPolicy.DELETE_OLD:
                    task = DataManagementTask(
                        task_id=f"delete_{table_name}_{int(time.time())}",
                        operation=DataOperation.DELETE,
                        target_path=table_name,
                        priority=3,
                        created_at=int(time.time()),
                        status='pending',
                        details={'retention_days': rule.retention_days}
                    )
                    self.task_queue.append(task)
                elif rule.policy == DataRetentionPolicy.COMPRESS_OLD:
                    task = DataManagementTask(
                        task_id=f"compress_{table_name}_{int(time.time())}",
                        operation=DataOperation.COMPRESS,
                        target_path=table_name,
                        priority=3,
                        created_at=int(time.time()),
                        status='pending',
                        details={'compression_level': rule.compression_level}
                    )
                    self.task_queue.append(task)
                elif rule.policy == DataRetentionPolicy.ARCHIVE_OLD:
                    task = DataManagementTask(
                        task_id=f"archive_{table_name}_{int(time.time())}",
                        operation=DataOperation.ARCHIVE,
                        target_path=table_name,
                        priority=3,
                        created_at=int(time.time()),
                        status='pending',
                        details={'archive_path': rule.archive_path}
                    )
                    self.task_queue.append(task)
            
            logger.info("Monthly cleanup scheduled")
            
        except Exception as e:
            logger.error(f"Error scheduling monthly cleanup: {e}")
    
    def schedule_task(self, operation: DataOperation, target_path: str, priority: int = 5, details: Dict[str, Any] = None) -> str:
        """Schedule a data management task"""
        try:
            task_id = f"{operation.value}_{int(time.time())}"
            task = DataManagementTask(
                task_id=task_id,
                operation=operation,
                target_path=target_path,
                priority=priority,
                created_at=int(time.time()),
                status='pending',
                details=details or {}
            )
            
            # Insert task in priority order
            inserted = False
            for i, existing_task in enumerate(self.task_queue):
                if task.priority < existing_task.priority:
                    self.task_queue.insert(i, task)
                    inserted = True
                    break
            
            if not inserted:
                self.task_queue.append(task)
            
            logger.info(f"Task scheduled: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Error scheduling task: {e}")
            return ""
    
    def get_automation_status(self) -> Dict[str, Any]:
        """Get automation status"""
        try:
            return {
                'symbol': self.symbol,
                'automation_active': self.automation_active,
                'pending_tasks': len(self.task_queue),
                'active_tasks': len(self.active_tasks),
                'completed_tasks': len(self.completed_tasks),
                'retention_rules': {name: {
                    'retention_days': rule.retention_days,
                    'policy': rule.policy.value,
                    'compression_level': rule.compression_level
                } for name, rule in self.default_rules.items()}
            }
            
        except Exception as e:
            logger.error(f"Error getting automation status: {e}")
            return {'symbol': self.symbol, 'error': str(e)}

# Example usage and testing
if __name__ == "__main__":
    # Test configuration
    test_config = {
        'symbol': 'BTCUSDc',
        'data_config': {
            'retention_rules': {
                'raw_ticks': {'retention_days': 7, 'policy': 'delete_old'},
                'ohlcv_bars': {'retention_days': 30, 'policy': 'compress_old'}
            },
            'backup_config': {
                'enabled': True,
                'frequency': 'daily'
            },
            'compression_config': {
                'enabled': True,
                'level': 6
            }
        }
    }
    
    # Create data management automation
    automation = DataManagementAutomation(test_config)
    
    print("Testing Data Management Automation:")
    
    # Start automation
    automation.start_automation()
    
    # Schedule some tasks
    task_id1 = automation.schedule_task(DataOperation.BACKUP, 'data/test.db', priority=1)
    task_id2 = automation.schedule_task(DataOperation.OPTIMIZE, 'data/test.db', priority=2)
    
    print(f"Scheduled tasks: {task_id1}, {task_id2}")
    
    # Wait for tasks to process
    time.sleep(2)
    
    # Get automation status
    status = automation.get_automation_status()
    print(f"Automation Status: {status}")
    
    # Stop automation
    automation.stop_automation()
    print("Data management automation test completed")
