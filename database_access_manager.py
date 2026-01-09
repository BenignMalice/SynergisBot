#!/usr/bin/env python3
"""
Database Access Manager - Separate Database Architecture
======================================================
This module manages database access for the separate database architecture:
- Main Database: ChatGPT Bot (WRITE) + Others (READ)
- Analysis Database: Desktop Agent (WRITE) + Others (READ)  
- Logs Database: API Server (WRITE) + Others (READ)
"""

import sqlite3
import json
import time
import os
import threading
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class DatabaseAccessManager:
    """Manages database access to prevent conflicts with separate databases."""
    
    def __init__(self, process_type: str = "unknown"):
        """
        Initialize database access manager.
        
        Args:
            process_type: Type of process ('chatgpt_bot', 'desktop_agent', 'api_server')
        """
        self.process_type = process_type
        self.main_db = 'unified_tick_pipeline.db'
        self.analysis_db = 'analysis_data.db'
        self.logs_db = 'system_logs.db'
        self.shared_memory_file = 'shared_memory.json'
        
        # Thread locks for each database
        self.locks = {
            'main_db': threading.Lock(),
            'analysis_db': threading.Lock(),
            'logs_db': threading.Lock()
        }
        
        # Process access permissions
        self.access_permissions = self._get_access_permissions()
        
        logger.info(f"DatabaseAccessManager initialized for {process_type}")
        logger.info(f"Access permissions: {self.access_permissions}")
    
    def _get_access_permissions(self) -> Dict[str, str]:
        """Get access permissions for this process type."""
        permissions = {
            'chatgpt_bot': {
                'main_db': 'write',
                'analysis_db': 'read',
                'logs_db': 'read'
            },
            'desktop_agent': {
                'main_db': 'read',
                'analysis_db': 'write',
                'logs_db': 'read'
            },
            'api_server': {
                'main_db': 'read',
                'analysis_db': 'read',
                'logs_db': 'write'
            }
        }
        
        return permissions.get(self.process_type, {
            'main_db': 'read',
            'analysis_db': 'read',
            'logs_db': 'read'
        })
    
    def _configure_database(self, db_path: str, read_only: bool = False):
        """Configure database connection for optimal performance."""
        conn = sqlite3.connect(db_path, timeout=60.0)
        cursor = conn.cursor()
        
        # Configure for optimal performance
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA cache_size=20000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA foreign_keys=ON")
        
        if read_only:
            cursor.execute("PRAGMA query_only=ON")
        
        return conn
    
    @contextmanager
    def get_main_db_connection(self, read_only: Optional[bool] = None):
        """
        Get connection to main database.
        
        Args:
            read_only: Force read-only mode (overrides process permissions)
        """
        if read_only is None:
            read_only = self.access_permissions['main_db'] == 'read'
        
        if not read_only and self.access_permissions['main_db'] == 'read':
            raise PermissionError(f"Process {self.process_type} only has READ access to main_db")
        
        with self.locks['main_db']:
            conn = None
            try:
                conn = self._configure_database(self.main_db, read_only)
                yield conn
            except Exception as e:
                logger.error(f"Error with main database connection: {e}")
                if conn:
                    conn.rollback()
                raise
            finally:
                if conn:
                    conn.close()
    
    @contextmanager
    def get_analysis_db_connection(self, read_only: Optional[bool] = None):
        """
        Get connection to analysis database.
        
        Args:
            read_only: Force read-only mode (overrides process permissions)
        """
        if read_only is None:
            read_only = self.access_permissions['analysis_db'] == 'read'
        
        if not read_only and self.access_permissions['analysis_db'] == 'read':
            raise PermissionError(f"Process {self.process_type} only has READ access to analysis_db")
        
        with self.locks['analysis_db']:
            conn = None
            try:
                conn = self._configure_database(self.analysis_db, read_only)
                yield conn
            except Exception as e:
                logger.error(f"Error with analysis database connection: {e}")
                if conn:
                    conn.rollback()
                raise
            finally:
                if conn:
                    conn.close()
    
    @contextmanager
    def get_logs_db_connection(self, read_only: Optional[bool] = None):
        """
        Get connection to logs database.
        
        Args:
            read_only: Force read-only mode (overrides process permissions)
        """
        if read_only is None:
            read_only = self.access_permissions['logs_db'] == 'read'
        
        if not read_only and self.access_permissions['logs_db'] == 'read':
            raise PermissionError(f"Process {self.process_type} only has READ access to logs_db")
        
        with self.locks['logs_db']:
            conn = None
            try:
                conn = self._configure_database(self.logs_db, read_only)
                yield conn
            except Exception as e:
                logger.error(f"Error with logs database connection: {e}")
                if conn:
                    conn.rollback()
                raise
            finally:
                if conn:
                    conn.close()
    
    def update_shared_memory(self, key: str, value: Any):
        """Update shared memory file for inter-process communication."""
        try:
            # Load existing data
            if Path(self.shared_memory_file).exists():
                try:
                    with open(self.shared_memory_file, 'r') as f:
                        content = f.read().strip()
                        if content:  # Check if file is not empty
                            data = json.loads(content)
                        else:
                            raise json.JSONDecodeError("Empty file", content, 0)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Corrupted shared memory file, recreating: {e}")
                    data = {
                        "last_update": time.time(),
                        "tick_count": 0,
                        "system_status": "initializing",
                        "active_processes": [],
                        "database_locks": {
                            "main_db": "unlocked",
                            "analysis_db": "unlocked",
                            "logs_db": "unlocked"
                        }
                    }
            else:
                data = {
                    "last_update": time.time(),
                    "tick_count": 0,
                    "system_status": "initializing",
                    "active_processes": [],
                    "database_locks": {
                        "main_db": "unlocked",
                        "analysis_db": "unlocked",
                        "logs_db": "unlocked"
                    }
                }
            
            # Update the key
            data[key] = value
            data['last_update'] = time.time()
            
            # Add this process to active processes
            if 'active_processes' not in data:
                data['active_processes'] = []
            
            process_info = {
                'type': self.process_type,
                'pid': os.getpid(),
                'last_seen': time.time()
            }
            
            # Update or add process info
            existing_process = None
            for i, proc in enumerate(data['active_processes']):
                if proc['type'] == self.process_type:
                    existing_process = i
                    break
            
            if existing_process is not None:
                data['active_processes'][existing_process] = process_info
            else:
                data['active_processes'].append(process_info)
            
            # Save updated data
            with open(self.shared_memory_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error updating shared memory: {e}")
    
    def get_shared_memory(self) -> Dict[str, Any]:
        """Get shared memory data."""
        try:
            if Path(self.shared_memory_file).exists():
                with open(self.shared_memory_file, 'r') as f:
                    return json.load(f)
            else:
                return {
                    "last_update": time.time(),
                    "tick_count": 0,
                    "system_status": "initializing",
                    "active_processes": [],
                    "database_locks": {
                        "main_db": "unlocked",
                        "analysis_db": "unlocked",
                        "logs_db": "unlocked"
                    }
                }
        except Exception as e:
            logger.error(f"Error reading shared memory: {e}")
            return {}
    
    def get_database_status(self) -> Dict[str, Any]:
        """Get status of all databases."""
        status = {
            'main_db': {'accessible': False, 'record_count': 0},
            'analysis_db': {'accessible': False, 'record_count': 0},
            'logs_db': {'accessible': False, 'record_count': 0}
        }
        
        # Check main database
        try:
            with self.get_main_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM unified_ticks")
                count = cursor.fetchone()[0]
                status['main_db'] = {'accessible': True, 'record_count': count}
        except Exception as e:
            logger.warning(f"Main database not accessible: {e}")
        
        # Check analysis database
        try:
            with self.get_analysis_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM analysis_results")
                count = cursor.fetchone()[0]
                status['analysis_db'] = {'accessible': True, 'record_count': count}
        except Exception as e:
            logger.warning(f"Analysis database not accessible: {e}")
        
        # Check logs database
        try:
            with self.get_logs_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM api_logs")
                count = cursor.fetchone()[0]
                status['logs_db'] = {'accessible': True, 'record_count': count}
        except Exception as e:
            logger.warning(f"Logs database not accessible: {e}")
        
        return status
    
    def test_database_access(self) -> Dict[str, bool]:
        """Test database access for this process."""
        results = {
            'main_db_read': False,
            'main_db_write': False,
            'analysis_db_read': False,
            'analysis_db_write': False,
            'logs_db_read': False,
            'logs_db_write': False
        }
        
        # Test main database
        try:
            with self.get_main_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                results['main_db_read'] = True
        except Exception as e:
            logger.warning(f"Main database read test failed: {e}")
        
        if self.access_permissions['main_db'] == 'write':
            try:
                with self.get_main_db_connection(read_only=False) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    results['main_db_write'] = True
            except Exception as e:
                logger.warning(f"Main database write test failed: {e}")
        
        # Test analysis database
        try:
            with self.get_analysis_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                results['analysis_db_read'] = True
        except Exception as e:
            logger.warning(f"Analysis database read test failed: {e}")
        
        if self.access_permissions['analysis_db'] == 'write':
            try:
                with self.get_analysis_db_connection(read_only=False) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    results['analysis_db_write'] = True
            except Exception as e:
                logger.warning(f"Analysis database write test failed: {e}")
        
        # Test logs database
        try:
            with self.get_logs_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                results['logs_db_read'] = True
        except Exception as e:
            logger.warning(f"Logs database read test failed: {e}")
        
        if self.access_permissions['logs_db'] == 'write':
            try:
                with self.get_logs_db_connection(read_only=False) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    results['logs_db_write'] = True
            except Exception as e:
                logger.warning(f"Logs database write test failed: {e}")
        
        return results

# Global instance for easy access
_db_manager: Optional[DatabaseAccessManager] = None

def initialize_database_manager(process_type: str = "unknown") -> DatabaseAccessManager:
    """Initialize the global database manager."""
    global _db_manager
    _db_manager = DatabaseAccessManager(process_type)
    return _db_manager

def get_database_manager() -> Optional[DatabaseAccessManager]:
    """Get the global database manager."""
    return _db_manager

# Convenience functions for easy access
def get_main_db_connection(read_only: Optional[bool] = None):
    """Get main database connection."""
    if _db_manager is None:
        raise RuntimeError("Database manager not initialized")
    return _db_manager.get_main_db_connection(read_only)

def get_analysis_db_connection(read_only: Optional[bool] = None):
    """Get analysis database connection."""
    if _db_manager is None:
        raise RuntimeError("Database manager not initialized")
    return _db_manager.get_analysis_db_connection(read_only)

def get_logs_db_connection(read_only: Optional[bool] = None):
    """Get logs database connection."""
    if _db_manager is None:
        raise RuntimeError("Database manager not initialized")
    return _db_manager.get_logs_db_connection(read_only)

if __name__ == "__main__":
    # Test the database access manager
    import os
    
    print("Testing Database Access Manager...")
    
    # Test ChatGPT Bot access
    print("\n=== ChatGPT Bot Access ===")
    chatgpt_manager = DatabaseAccessManager("chatgpt_bot")
    chatgpt_results = chatgpt_manager.test_database_access()
    print(f"Main DB - Read: {chatgpt_results['main_db_read']}, Write: {chatgpt_results['main_db_write']}")
    print(f"Analysis DB - Read: {chatgpt_results['analysis_db_read']}, Write: {chatgpt_results['analysis_db_write']}")
    print(f"Logs DB - Read: {chatgpt_results['logs_db_read']}, Write: {chatgpt_results['logs_db_write']}")
    
    # Test Desktop Agent access
    print("\n=== Desktop Agent Access ===")
    desktop_manager = DatabaseAccessManager("desktop_agent")
    desktop_results = desktop_manager.test_database_access()
    print(f"Main DB - Read: {desktop_results['main_db_read']}, Write: {desktop_results['main_db_write']}")
    print(f"Analysis DB - Read: {desktop_results['analysis_db_read']}, Write: {desktop_results['analysis_db_write']}")
    print(f"Logs DB - Read: {desktop_results['logs_db_read']}, Write: {desktop_results['logs_db_write']}")
    
    # Test API Server access
    print("\n=== API Server Access ===")
    api_manager = DatabaseAccessManager("api_server")
    api_results = api_manager.test_database_access()
    print(f"Main DB - Read: {api_results['main_db_read']}, Write: {api_results['main_db_write']}")
    print(f"Analysis DB - Read: {api_results['analysis_db_read']}, Write: {api_results['analysis_db_write']}")
    print(f"Logs DB - Read: {api_results['logs_db_read']}, Write: {api_results['logs_db_write']}")
    
    print("\nDatabase Access Manager test completed!")
