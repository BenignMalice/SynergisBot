#!/usr/bin/env python3
"""
Data Retention Policy for TelegramMoneyBot
==========================================
Automatically manages data retention to prevent disk space issues.
"""

import os
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
import schedule
import time

class DataRetentionManager:
    """Manages data retention policies to prevent disk space issues"""
    
    def __init__(self):
        self.data_dir = Path("data")
        self.logger = logging.getLogger(__name__)
        
        # Retention policies (in days)
        self.policies = {
            'tick_data': 7,      # Keep 7 days of tick data
            'logs': 3,           # Keep 3 days of logs
            'backups': 1,        # Keep 1 day of backups
            'analysis_data': 14, # Keep 14 days of analysis data
            'performance_logs': 7 # Keep 7 days of performance logs
        }
    
    def cleanup_tick_data(self):
        """Clean old tick data"""
        db_path = self.data_dir / "unified_tick_pipeline" / "tick_data.db"
        
        if not db_path.exists():
            return 0
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            original_size = db_path.stat().st_size / (1024 * 1024)
            cutoff_timestamp = int((datetime.now() - timedelta(days=self.policies['tick_data'])).timestamp())
            
            # Clean unified_ticks table
            cursor.execute("DELETE FROM unified_ticks WHERE timestamp_utc < ?", (cutoff_timestamp,))
            deleted_count = cursor.rowcount
            
            # Vacuum to reclaim space
            cursor.execute("VACUUM")
            
            conn.commit()
            conn.close()
            
            new_size = db_path.stat().st_size / (1024 * 1024)
            freed_space = original_size - new_size
            
            self.logger.info(f"Tick data cleanup: deleted {deleted_count:,} records, freed {freed_space:.2f} MB")
            return freed_space
            
        except Exception as e:
            self.logger.error(f"Error cleaning tick data: {e}")
            return 0
    
    def cleanup_logs(self):
        """Clean old log files"""
        log_files = list(self.data_dir.rglob("*.log*"))
        cutoff_date = datetime.now() - timedelta(days=self.policies['logs'])
        
        total_freed = 0
        for log_file in log_files:
            try:
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_time < cutoff_date:
                    size_mb = log_file.stat().st_size / (1024 * 1024)
                    log_file.unlink()
                    total_freed += size_mb
                    self.logger.info(f"Deleted old log: {log_file.name} ({size_mb:.2f} MB)")
            except Exception as e:
                self.logger.error(f"Error deleting {log_file}: {e}")
        
        return total_freed
    
    def cleanup_backups(self):
        """Clean old backup files"""
        backup_patterns = ["*.backup", "*.bak*", "*_backup_*"]
        backup_files = []
        
        for pattern in backup_patterns:
            backup_files.extend(self.data_dir.rglob(pattern))
        
        cutoff_date = datetime.now() - timedelta(days=self.policies['backups'])
        total_freed = 0
        
        for backup_file in backup_files:
            try:
                file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if file_time < cutoff_date:
                    size_mb = backup_file.stat().st_size / (1024 * 1024)
                    backup_file.unlink()
                    total_freed += size_mb
                    self.logger.info(f"Deleted old backup: {backup_file.name} ({size_mb:.2f} MB)")
            except Exception as e:
                self.logger.error(f"Error deleting {backup_file}: {e}")
        
        return total_freed
    
    def cleanup_analysis_data(self):
        """Clean old analysis data from various databases"""
        databases = [
            "data/advanced_analytics.sqlite",
            "data/unified_tick_pipeline/chatgpt_analysis.db",
            "data/unified_tick_pipeline/performance_logs.db",
            "data/unified_tick_pipeline/system_metrics.db"
        ]
        
        total_freed = 0
        cutoff_timestamp = int((datetime.now() - timedelta(days=self.policies['analysis_data'])).timestamp())
        
        for db_path in databases:
            db_file = Path(db_path)
            if not db_file.exists():
                continue
            
            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                
                original_size = db_file.stat().st_size / (1024 * 1024)
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                
                for (table_name,) in tables:
                    try:
                        # Find timestamp column
                        cursor.execute(f"PRAGMA table_info({table_name})")
                        columns = cursor.fetchall()
                        timestamp_col = None
                        
                        for col in columns:
                            col_name = col[1].lower()
                            if any(keyword in col_name for keyword in ['timestamp', 'time', 'created', 'date']):
                                timestamp_col = col[1]
                                break
                        
                        if timestamp_col:
                            cursor.execute(f"DELETE FROM {table_name} WHERE {timestamp_col} < ?", (cutoff_timestamp,))
                            deleted = cursor.rowcount
                            if deleted > 0:
                                self.logger.info(f"Deleted {deleted:,} old records from {table_name}")
                    except sqlite3.Error:
                        continue
                
                # Vacuum
                cursor.execute("VACUUM")
                conn.commit()
                conn.close()
                
                new_size = db_file.stat().st_size / (1024 * 1024)
                freed_space = original_size - new_size
                total_freed += freed_space
                
            except Exception as e:
                self.logger.error(f"Error cleaning {db_path}: {e}")
        
        return total_freed
    
    def run_cleanup(self):
        """Run all cleanup tasks"""
        self.logger.info("Starting data retention cleanup...")
        
        total_freed = 0
        total_freed += self.cleanup_tick_data()
        total_freed += self.cleanup_logs()
        total_freed += self.cleanup_backups()
        total_freed += self.cleanup_analysis_data()
        
        self.logger.info(f"Data retention cleanup complete. Total space freed: {total_freed:.2f} MB")
        return total_freed
    
    def setup_scheduled_cleanup(self):
        """Setup scheduled cleanup tasks"""
        # Run cleanup daily at 2 AM
        schedule.every().day.at("02:00").do(self.run_cleanup)
        
        # Run tick data cleanup every 6 hours
        schedule.every(6).hours.do(self.cleanup_tick_data)
        
        # Run log cleanup every 12 hours
        schedule.every(12).hours.do(self.cleanup_logs)
        
        self.logger.info("Data retention scheduler configured")
    
    def start_scheduler(self):
        """Start the retention scheduler"""
        self.setup_scheduled_cleanup()
        
        self.logger.info("Data retention scheduler started")
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

def main():
    """Main function for manual cleanup"""
    logging.basicConfig(level=logging.INFO)
    
    manager = DataRetentionManager()
    total_freed = manager.run_cleanup()
    
    print(f"Data retention cleanup complete. Freed {total_freed:.2f} MB")

if __name__ == "__main__":
    main()
