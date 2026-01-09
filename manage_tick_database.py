#!/usr/bin/env python3
"""
Tick Database Management Script
===============================
Manages the size of tick_data.db through various optimization techniques.
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

class TickDatabaseManager:
    """Manages tick database size and optimization"""
    
    def __init__(self, db_path="data/unified_tick_pipeline/tick_data.db"):
        self.db_path = Path(db_path)
        self.backup_path = Path(f"{db_path}.backup")
        
    def get_database_info(self):
        """Get current database information"""
        if not self.db_path.exists():
            return {"error": "Database file not found"}
        
        # Get file size
        file_size = self.db_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        # Connect to database
        conn = sqlite3.connect(self.db_path)
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
            
            # Get oldest and newest records
            oldest_newest = {}
            if 'unified_ticks' in tables:
                cursor.execute("SELECT MIN(timestamp_utc), MAX(timestamp_utc) FROM unified_ticks")
                result = cursor.fetchone()
                oldest_newest['unified_ticks'] = {
                    'oldest': result[0],
                    'newest': result[1]
                }
            
            return {
                "file_size_mb": round(file_size_mb, 2),
                "tables": tables,
                "record_counts": record_counts,
                "oldest_newest": oldest_newest
            }
            
        finally:
            conn.close()
    
    def cleanup_old_data(self, days_to_keep=7):
        """Clean up old tick data"""
        logger.info(f"Cleaning up data older than {days_to_keep} days...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cutoff_str = cutoff_date.isoformat()
            
            # Clean up old ticks
            cursor.execute("""
                DELETE FROM unified_ticks 
                WHERE timestamp_utc < ?
            """, (cutoff_str,))
            
            deleted_ticks = cursor.rowcount
            logger.info(f"Deleted {deleted_ticks} old tick records")
            
            # Clean up old M5 candles if table exists
            try:
                cursor.execute("""
                    DELETE FROM m5_candles 
                    WHERE timestamp_utc < ?
                """, (cutoff_str,))
                deleted_candles = cursor.rowcount
                logger.info(f"Deleted {deleted_candles} old M5 candle records")
            except sqlite3.OperationalError:
                logger.info("M5 candles table not found, skipping")
            
            conn.commit()
            
            return {
                "deleted_ticks": deleted_ticks,
                "deleted_candles": deleted_candles if 'deleted_candles' in locals() else 0
            }
            
        finally:
            conn.close()
    
    def optimize_database(self):
        """Optimize database performance and size"""
        logger.info("Optimizing database...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Enable WAL mode for better performance
            cursor.execute("PRAGMA journal_mode=WAL")
            
            # Optimize database
            cursor.execute("PRAGMA optimize")
            
            # Vacuum database to reclaim space
            cursor.execute("VACUUM")
            
            # Analyze tables for better query planning
            cursor.execute("ANALYZE")
            
            conn.commit()
            logger.info("Database optimization completed")
            
        finally:
            conn.close()
    
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
    
    def restore_backup(self):
        """Restore database from backup"""
        if not self.backup_path.exists():
            logger.error("Backup file not found")
            return False
        
        try:
            shutil.copy2(self.backup_path, self.db_path)
            logger.info("Database restored from backup")
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
    
    def compress_database(self):
        """Compress database by removing old data and optimizing"""
        logger.info("Starting database compression...")
        
        # Create backup first
        if not self.create_backup():
            return False
        
        try:
            # Clean up old data (keep only 7 days)
            cleanup_result = self.cleanup_old_data(days_to_keep=7)
            
            # Optimize database
            self.optimize_database()
            
            # Get new size
            new_info = self.get_database_info()
            
            logger.info(f"Compression completed. New size: {new_info['file_size_mb']}MB")
            return True
            
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            # Restore backup if compression failed
            self.restore_backup()
            return False
    
    def archive_old_data(self, days_to_archive=30):
        """Archive old data to separate file"""
        logger.info(f"Archiving data older than {days_to_archive} days...")
        
        # This would require more complex implementation
        # For now, just clean up old data
        return self.cleanup_old_data(days_to_keep=7)
    
    def get_recommendations(self):
        """Get recommendations for database management"""
        info = self.get_database_info()
        
        if "error" in info:
            return ["Database not found"]
        
        recommendations = []
        
        # Size-based recommendations
        if info["file_size_mb"] > 1000:  # > 1GB
            recommendations.append("Database is very large (>1GB). Consider cleaning up old data.")
        
        if info["file_size_mb"] > 500:  # > 500MB
            recommendations.append("Database is large (>500MB). Run optimization.")
        
        # Record count recommendations
        if "unified_ticks" in info["record_counts"]:
            tick_count = info["record_counts"]["unified_ticks"]
            if tick_count > 1000000:  # > 1M records
                recommendations.append(f"High tick count ({tick_count:,}). Consider data retention policies.")
        
        # Age-based recommendations
        if "unified_ticks" in info["oldest_newest"]:
            oldest = info["oldest_newest"]["unified_ticks"]["oldest"]
            if oldest:
                try:
                    oldest_date = datetime.fromisoformat(oldest.replace('Z', '+00:00'))
                    days_old = (datetime.now() - oldest_date.replace(tzinfo=None)).days
                    if days_old > 30:
                        recommendations.append(f"Oldest data is {days_old} days old. Consider archiving.")
                except:
                    pass
        
        return recommendations

def main():
    """Main function for database management"""
    print("=" * 80)
    print("TICK DATABASE MANAGEMENT")
    print("=" * 80)
    
    manager = TickDatabaseManager()
    
    # Get current database info
    print("\n📊 CURRENT DATABASE STATUS")
    print("-" * 40)
    info = manager.get_database_info()
    
    if "error" in info:
        print(f"❌ {info['error']}")
        return
    
    print(f"File size: {info['file_size_mb']}MB")
    print(f"Tables: {', '.join(info['tables'])}")
    print(f"Record counts:")
    for table, count in info['record_counts'].items():
        print(f"  - {table}: {count:,} records")
    
    # Get recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-" * 40)
    recommendations = manager.get_recommendations()
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    
    # Show management options
    print("\n🔧 MANAGEMENT OPTIONS")
    print("-" * 40)
    print("1. Clean up old data (keep 7 days)")
    print("2. Optimize database")
    print("3. Compress database (cleanup + optimize)")
    print("4. Create backup")
    print("5. Show detailed info")
    
    print("\n" + "=" * 80)
    print("To run specific operations, use:")
    print("  python manage_tick_database.py --cleanup")
    print("  python manage_tick_database.py --optimize")
    print("  python manage_tick_database.py --compress")
    print("  python manage_tick_database.py --backup")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        manager = TickDatabaseManager()
        
        if sys.argv[1] == "--cleanup":
            result = manager.cleanup_old_data()
            print(f"Cleanup completed: {result}")
        elif sys.argv[1] == "--optimize":
            manager.optimize_database()
            print("Optimization completed")
        elif sys.argv[1] == "--compress":
            success = manager.compress_database()
            print(f"Compression {'completed' if success else 'failed'}")
        elif sys.argv[1] == "--backup":
            success = manager.create_backup()
            print(f"Backup {'completed' if success else 'failed'}")
        else:
            print("Unknown option. Use --cleanup, --optimize, --compress, or --backup")
    else:
        main()
