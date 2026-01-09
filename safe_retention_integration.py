#!/usr/bin/env python3
"""
Safe Retention Integration
=========================
Integrates hybrid retention system with existing bot architecture
without causing database locking or Binance disconnect issues.
"""

import asyncio
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import queue
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SafeRetentionSystem:
    """
    Safe retention system that integrates with existing bot architecture
    without causing database locking or Binance disconnect issues.
    """
    
    def __init__(self, db_path="data/unified_tick_pipeline/tick_data.db"):
        self.db_path = Path(db_path)
        self.is_running = False
        self.cleanup_thread = None
        self.cleanup_queue = queue.Queue()
        
        # Retention policies (same as hybrid system)
        self.retention_policies = {
            'tick_data': {
                'recent_hours': 6,      # Keep all data for 6 hours
                'sampling_hours': 18,   # Sample every 3rd record for 6-24 hours
                'delete_after_hours': 24,  # Delete after 24 hours
                'max_size_mb': 500,     # Maximum database size
                'emergency_size_mb': 1000  # Emergency limit
            },
            'analysis_data': {
                'retention_days': 7,     # Keep analysis data for 7 days
                'max_size_mb': 100      # Maximum analysis data size
            }
        }
        
        # Safety settings
        self.safety_settings = {
            'max_cleanup_duration_seconds': 30,  # Maximum cleanup time
            'cleanup_interval_hours': 2,          # Run every 2 hours (less frequent)
            'database_lock_timeout_seconds': 5,    # Short lock timeout
            'retry_attempts': 3,                  # Retry on lock failure
            'cooldown_seconds': 60,               # Wait between attempts
            'emergency_cleanup_only': False       # Only emergency cleanup if needed
        }
        
        # Status tracking
        self.last_cleanup = None
        self.cleanup_in_progress = False
        self.cleanup_errors = 0
        self.max_cleanup_errors = 5
        
        logger.info("SafeRetentionSystem initialized with safety measures")
    
    def start(self):
        """Start the safe retention system"""
        if self.is_running:
            logger.warning("Retention system already running")
            return
        
        self.is_running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        logger.info("Safe retention system started with safety measures")
    
    def stop(self):
        """Stop the retention system"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        
        logger.info("Safe retention system stopped")
    
    def _cleanup_worker(self):
        """Background worker that runs cleanup safely"""
        while self.is_running:
            try:
                # Wait for cleanup interval
                time.sleep(self.safety_settings['cleanup_interval_hours'] * 3600)
                
                if not self.is_running:
                    break
                
                # Check if cleanup is needed
                if self._should_run_cleanup():
                    logger.info("Starting safe retention cleanup...")
                    self._run_safe_cleanup()
                
            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}")
                self.cleanup_errors += 1
                
                # If too many errors, stop trying
                if self.cleanup_errors >= self.max_cleanup_errors:
                    logger.error("Too many cleanup errors, stopping retention system")
                    self.is_running = False
                    break
                
                # Wait before retrying
                time.sleep(self.safety_settings['cooldown_seconds'])
    
    def _should_run_cleanup(self):
        """Check if cleanup is needed based on database size"""
        try:
            if not self.db_path.exists():
                return False
            
            # Get database size
            file_size = self.db_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            # Check if cleanup is needed
            max_size = self.retention_policies['tick_data']['max_size_mb']
            emergency_size = self.retention_policies['tick_data']['emergency_size_mb']
            
            if file_size_mb > emergency_size:
                logger.warning(f"Emergency cleanup needed: {file_size_mb}MB > {emergency_size}MB")
                return True
            elif file_size_mb > max_size:
                logger.info(f"Regular cleanup needed: {file_size_mb}MB > {max_size}MB")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if cleanup needed: {e}")
            return False
    
    def _run_safe_cleanup(self):
        """Run cleanup with safety measures to prevent database locking"""
        if self.cleanup_in_progress:
            logger.warning("Cleanup already in progress, skipping")
            return
        
        self.cleanup_in_progress = True
        start_time = time.time()
        
        try:
            # Step 1: Check database accessibility
            if not self._check_database_accessibility():
                logger.warning("Database not accessible, skipping cleanup")
                return
            
            # Step 2: Run cleanup with timeout
            cleanup_success = self._run_cleanup_with_timeout()
            
            if cleanup_success:
                self.cleanup_errors = 0  # Reset error count on success
                self.last_cleanup = datetime.now()
                logger.info("Safe cleanup completed successfully")
            else:
                logger.warning("Cleanup failed or timed out")
            
        except Exception as e:
            logger.error(f"Error in safe cleanup: {e}")
            self.cleanup_errors += 1
        finally:
            self.cleanup_in_progress = False
            
            # Log cleanup duration
            duration = time.time() - start_time
            logger.info(f"Cleanup duration: {duration:.2f} seconds")
    
    def _check_database_accessibility(self):
        """Check if database is accessible without locking"""
        try:
            # Try to open database with short timeout
            conn = sqlite3.connect(
                self.db_path, 
                timeout=self.safety_settings['database_lock_timeout_seconds']
            )
            
            # Quick query to test access
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master")
            cursor.fetchone()
            
            conn.close()
            return True
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                logger.warning("Database is locked, skipping cleanup")
                return False
            else:
                logger.error(f"Database accessibility error: {e}")
                return False
        except Exception as e:
            logger.error(f"Database accessibility check failed: {e}")
            return False
    
    def _run_cleanup_with_timeout(self):
        """Run cleanup with timeout to prevent long locks"""
        try:
            # Use threading to run cleanup with timeout
            result = [False]
            exception = [None]
            
            def cleanup_worker():
                try:
                    self._perform_cleanup()
                    result[0] = True
                except Exception as e:
                    exception[0] = e
            
            # Start cleanup in separate thread
            cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
            cleanup_thread.start()
            
            # Wait for completion or timeout
            cleanup_thread.join(timeout=self.safety_settings['max_cleanup_duration_seconds'])
            
            if cleanup_thread.is_alive():
                logger.warning("Cleanup timed out, stopping")
                return False
            
            if exception[0]:
                raise exception[0]
            
            return result[0]
            
        except Exception as e:
            logger.error(f"Cleanup with timeout failed: {e}")
            return False
    
    def _perform_cleanup(self):
        """Perform the actual cleanup operations"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.safety_settings['database_lock_timeout_seconds']
        )
        cursor = conn.cursor()
        
        try:
            # Step 1: Delete very old data (24+ hours)
            self._delete_very_old_data(cursor)
            
            # Step 2: Sample older data (6-24 hours)
            self._sample_older_data(cursor)
            
            # Step 3: Clean up analysis data
            self._cleanup_analysis_data(cursor)
            
            # Step 4: Optimize database
            self._optimize_database(cursor)
            
            conn.commit()
            logger.info("Database cleanup operations completed")
            
        finally:
            conn.close()
    
    def _delete_very_old_data(self, cursor):
        """Delete data older than 24 hours"""
        try:
            cutoff_date = datetime.now() - timedelta(hours=24)
            cutoff_str = cutoff_date.isoformat()
            
            cursor.execute("""
                DELETE FROM unified_ticks 
                WHERE timestamp_utc < ?
            """, (cutoff_str,))
            
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} very old tick records")
            
        except Exception as e:
            logger.error(f"Error deleting very old data: {e}")
            raise
    
    def _sample_older_data(self, cursor):
        """Sample data from 6-24 hours (keep every 3rd record)"""
        try:
            # Calculate time ranges
            now = datetime.now()
            six_hours_ago = now - timedelta(hours=6)
            twenty_four_hours_ago = now - timedelta(hours=24)
            
            six_hours_str = six_hours_ago.isoformat()
            twenty_four_hours_str = twenty_four_hours_ago.isoformat()
            
            # Get records in the 6-24 hour range
            cursor.execute("""
                SELECT id FROM unified_ticks 
                WHERE timestamp_utc >= ? AND timestamp_utc < ?
                ORDER BY id
            """, (twenty_four_hours_str, six_hours_str))
            
            records = cursor.fetchall()
            total_records = len(records)
            
            if total_records == 0:
                return
            
            # Keep every 3rd record (delete 2 out of 3)
            records_to_delete = []
            for i, (record_id,) in enumerate(records):
                if i % 3 != 0:  # Keep every 3rd record
                    records_to_delete.append(record_id)
            
            # Delete non-sampled records in batches
            if records_to_delete:
                batch_size = 1000
                for i in range(0, len(records_to_delete), batch_size):
                    batch = records_to_delete[i:i + batch_size]
                    placeholders = ','.join(['?' for _ in batch])
                    cursor.execute(f"""
                        DELETE FROM unified_ticks 
                        WHERE id IN ({placeholders})
                    """, batch)
                
                deleted_count = len(records_to_delete)
                logger.info(f"Sampled {total_records} records, deleted {deleted_count}, kept {total_records - deleted_count}")
            
        except Exception as e:
            logger.error(f"Error sampling older data: {e}")
            raise
    
    def _cleanup_analysis_data(self, cursor):
        """Clean up analysis data older than 7 days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=7)
            cutoff_str = cutoff_date.isoformat()
            
            # Clean up ChatGPT analysis history
            cursor.execute("""
                DELETE FROM chatgpt_analysis_history 
                WHERE timestamp < ?
            """, (cutoff_str,))
            
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} old analysis records")
            
        except Exception as e:
            logger.error(f"Error cleaning up analysis data: {e}")
            raise
    
    def _optimize_database(self, cursor):
        """Optimize database performance"""
        try:
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            
            # Optimize
            cursor.execute("PRAGMA optimize")
            
            # Vacuum to reclaim space
            cursor.execute("VACUUM")
            
            # Analyze for better query planning
            cursor.execute("ANALYZE")
            
            logger.info("Database optimization completed")
            
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            raise
    
    def get_status(self):
        """Get current retention system status"""
        return {
            "is_running": self.is_running,
            "cleanup_in_progress": self.cleanup_in_progress,
            "last_cleanup": self.last_cleanup.isoformat() if self.last_cleanup else None,
            "cleanup_errors": self.cleanup_errors,
            "max_cleanup_errors": self.max_cleanup_errors,
            "safety_settings": self.safety_settings,
            "retention_policies": self.retention_policies
        }
    
    def get_database_info(self):
        """Get current database information"""
        if not self.db_path.exists():
            return {"error": "Database file not found"}
        
        try:
            file_size = self.db_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            conn = sqlite3.connect(
                self.db_path,
                timeout=self.safety_settings['database_lock_timeout_seconds']
            )
            cursor = conn.cursor()
            
            try:
                # Get table information
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                # Get record counts
                record_counts = {}
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    record_counts[table] = cursor.fetchone()[0]
                
                return {
                    "file_size_mb": round(file_size_mb, 2),
                    "tables": tables,
                    "record_counts": record_counts,
                    "last_cleanup": self.last_cleanup.isoformat() if self.last_cleanup else None
                }
                
            finally:
                conn.close()
                
        except Exception as e:
            return {"error": str(e)}

def main():
    """Main function to demonstrate safe retention system"""
    print("=" * 80)
    print("SAFE RETENTION SYSTEM")
    print("=" * 80)
    
    retention_system = SafeRetentionSystem()
    
    # Show current status
    info = retention_system.get_database_info()
    if "error" in info:
        print(f"ERROR: {info['error']}")
        return
    
    print(f"Current database size: {info['file_size_mb']}MB")
    print(f"Record counts:")
    for table, count in info['record_counts'].items():
        print(f"  - {table}: {count:,} records")
    
    print("\nSAFETY SETTINGS:")
    settings = retention_system.safety_settings
    for key, value in settings.items():
        print(f"  - {key}: {value}")
    
    print("\nRETENTION POLICIES:")
    policies = retention_system.retention_policies
    for data_type, policy in policies.items():
        print(f"  - {data_type}: {policy}")
    
    print("\n" + "=" * 80)
    print("To start the safe retention system:")
    print("  python safe_retention_integration.py --start")
    print("To check status:")
    print("  python safe_retention_integration.py --status")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        retention_system = SafeRetentionSystem()
        
        if sys.argv[1] == "--start":
            print("Starting safe retention system...")
            retention_system.start()
            try:
                while True:
                    time.sleep(60)  # Keep running
            except KeyboardInterrupt:
                print("\nStopping retention system...")
                retention_system.stop()
        elif sys.argv[1] == "--status":
            info = retention_system.get_database_info()
            status = retention_system.get_status()
            print(f"Database: {info}")
            print(f"Status: {status}")
        else:
            print("Unknown option. Use --start or --status")
    else:
        main()
