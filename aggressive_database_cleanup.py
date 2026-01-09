#!/usr/bin/env python3
"""
Aggressive Database Cleanup
===========================
More aggressive cleanup strategies for large tick databases.
"""

import sqlite3
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AggressiveDatabaseCleanup:
    """Aggressive database cleanup strategies"""
    
    def __init__(self, db_path="data/unified_tick_pipeline/tick_data.db"):
        self.db_path = Path(db_path)
        self.backup_path = Path(f"{db_path}.backup")
        
    def get_database_info(self):
        """Get current database information"""
        if not self.db_path.exists():
            return {"error": "Database file not found"}
        
        file_size = self.db_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM unified_ticks")
            total_records = cursor.fetchone()[0]
            
            # Get date range
            cursor.execute("SELECT MIN(timestamp_utc), MAX(timestamp_utc) FROM unified_ticks")
            result = cursor.fetchone()
            oldest, newest = result
            
            return {
                "file_size_mb": round(file_size_mb, 2),
                "total_records": total_records,
                "oldest": oldest,
                "newest": newest
            }
            
        finally:
            conn.close()
    
    def cleanup_by_hours(self, hours_to_keep=24):
        """Clean up data older than specified hours"""
        logger.info(f"Cleaning up data older than {hours_to_keep} hours...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff_date = datetime.now() - timedelta(hours=hours_to_keep)
            cutoff_str = cutoff_date.isoformat()
            
            cursor.execute("""
                DELETE FROM unified_ticks 
                WHERE timestamp_utc < ?
            """, (cutoff_str,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Deleted {deleted_count} records older than {hours_to_keep} hours")
            return deleted_count
            
        finally:
            conn.close()
    
    def cleanup_by_sample_rate(self, keep_every_nth=10):
        """Keep only every Nth record to reduce data density"""
        logger.info(f"Sampling data - keeping every {keep_every_nth}th record...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Create a temporary table with sampled data
            cursor.execute("""
                CREATE TEMPORARY TABLE sampled_ticks AS
                SELECT * FROM unified_ticks 
                WHERE id % ? = 0
            """, (keep_every_nth,))
            
            # Count sampled records
            cursor.execute("SELECT COUNT(*) FROM sampled_ticks")
            sampled_count = cursor.fetchone()[0]
            
            # Replace original table
            cursor.execute("DELETE FROM unified_ticks")
            cursor.execute("""
                INSERT INTO unified_ticks 
                SELECT * FROM sampled_ticks
            """)
            
            conn.commit()
            
            logger.info(f"Sampled {sampled_count} records from original data")
            return sampled_count
            
        finally:
            conn.close()
    
    def cleanup_by_volume_threshold(self, min_volume=0.001):
        """Remove low-volume ticks to reduce noise"""
        logger.info(f"Removing ticks with volume < {min_volume}...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM unified_ticks 
                WHERE volume < ?
            """, (min_volume,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Deleted {deleted_count} low-volume records")
            return deleted_count
            
        finally:
            conn.close()
    
    def cleanup_duplicates(self):
        """Remove duplicate records"""
        logger.info("Removing duplicate records...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Find duplicates
            cursor.execute("""
                SELECT symbol, timestamp_utc, bid, ask, COUNT(*) as count
                FROM unified_ticks 
                GROUP BY symbol, timestamp_utc, bid, ask
                HAVING COUNT(*) > 1
            """)
            
            duplicates = cursor.fetchall()
            logger.info(f"Found {len(duplicates)} duplicate groups")
            
            # Remove duplicates (keep first occurrence)
            cursor.execute("""
                DELETE FROM unified_ticks 
                WHERE id NOT IN (
                    SELECT MIN(id) 
                    FROM unified_ticks 
                    GROUP BY symbol, timestamp_utc, bid, ask
                )
            """)
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Deleted {deleted_count} duplicate records")
            return deleted_count
            
        finally:
            conn.close()
    
    def aggressive_cleanup(self):
        """Perform aggressive cleanup with multiple strategies"""
        logger.info("Starting aggressive database cleanup...")
        
        # Create backup first
        if not self.create_backup():
            logger.error("Backup failed, aborting cleanup")
            return False
        
        try:
            initial_info = self.get_database_info()
            logger.info(f"Initial size: {initial_info['file_size_mb']}MB, Records: {initial_info['total_records']:,}")
            
            # Strategy 1: Remove duplicates
            self.cleanup_duplicates()
            
            # Strategy 2: Remove low-volume ticks
            self.cleanup_by_volume_threshold(min_volume=0.001)
            
            # Strategy 3: Sample data (keep every 5th record)
            self.cleanup_by_sample_rate(keep_every_nth=5)
            
            # Strategy 4: Keep only last 12 hours
            self.cleanup_by_hours(hours_to_keep=12)
            
            # Optimize database
            self.optimize_database()
            
            final_info = self.get_database_info()
            logger.info(f"Final size: {final_info['file_size_mb']}MB, Records: {final_info['total_records']:,}")
            
            size_reduction = initial_info['file_size_mb'] - final_info['file_size_mb']
            record_reduction = initial_info['total_records'] - final_info['total_records']
            
            logger.info(f"Reduction: {size_reduction:.2f}MB ({size_reduction/initial_info['file_size_mb']*100:.1f}%), {record_reduction:,} records")
            
            return True
            
        except Exception as e:
            logger.error(f"Aggressive cleanup failed: {e}")
            return False
    
    def create_backup(self):
        """Create a backup of the database"""
        logger.info("Creating database backup...")
        
        if not self.db_path.exists():
            logger.error("Database file not found")
            return False
        
        try:
            shutil.copy2(self.db_path, self.backup_path)
            logger.info(f"Backup created: {self.backup_path}")
            return True
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False
    
    def optimize_database(self):
        """Optimize database performance and size"""
        logger.info("Optimizing database...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA optimize")
            cursor.execute("VACUUM")
            cursor.execute("ANALYZE")
            conn.commit()
            logger.info("Database optimization completed")
            
        finally:
            conn.close()

def main():
    """Main function"""
    print("=" * 80)
    print("AGGRESSIVE DATABASE CLEANUP")
    print("=" * 80)
    
    cleanup = AggressiveDatabaseCleanup()
    
    # Show current status
    info = cleanup.get_database_info()
    if "error" in info:
        print(f"ERROR: {info['error']}")
        return
    
    print(f"Current size: {info['file_size_mb']}MB")
    print(f"Total records: {info['total_records']:,}")
    print(f"Date range: {info['oldest']} to {info['newest']}")
    
    print("\nCLEANUP STRATEGIES:")
    print("1. Remove duplicates")
    print("2. Remove low-volume ticks")
    print("3. Sample data (keep every 5th record)")
    print("4. Keep only last 12 hours")
    print("5. Full aggressive cleanup (all strategies)")
    
    print("\n" + "=" * 80)
    print("To run aggressive cleanup:")
    print("  python aggressive_database_cleanup.py --aggressive")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--aggressive":
        cleanup = AggressiveDatabaseCleanup()
        success = cleanup.aggressive_cleanup()
        print(f"Aggressive cleanup {'completed' if success else 'failed'}")
    else:
        main()
