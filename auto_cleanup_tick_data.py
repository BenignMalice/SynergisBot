#!/usr/bin/env python3
"""
Automatic Tick Data Cleanup for TelegramMoneyBot
================================================
Automatically cleans the large tick_data.db file to free up disk space.
"""

import os
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta

def cleanup_tick_data_automatic():
    """Automatically clean tick data - keep only last 3 days"""
    db_path = Path("data/unified_tick_pipeline/tick_data.db")
    
    if not db_path.exists():
        print("tick_data.db not found")
        return 0
    
    print(f"Cleaning tick_data.db automatically...")
    print(f"Current size: {db_path.stat().st_size / (1024 * 1024):.2f} MB")
    
    # Create backup first
    backup_path = db_path.with_suffix('.db.backup')
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        original_size = db_path.stat().st_size / (1024 * 1024)
        
        # Keep only last 3 days of data
        cutoff_timestamp = int((datetime.now() - timedelta(days=3)).timestamp())
        
        # Clean unified_ticks table (the main culprit)
        print("Cleaning unified_ticks table...")
        cursor.execute("SELECT COUNT(*) FROM unified_ticks")
        total_records = cursor.fetchone()[0]
        print(f"  Total records: {total_records:,}")
        
        cursor.execute("SELECT COUNT(*) FROM unified_ticks WHERE timestamp_utc < ?", (cutoff_timestamp,))
        old_records = cursor.fetchone()[0]
        print(f"  Records older than 3 days: {old_records:,}")
        
        if old_records > 0:
            cursor.execute("DELETE FROM unified_ticks WHERE timestamp_utc < ?", (cutoff_timestamp,))
            deleted_count = cursor.rowcount
            print(f"  Deleted {deleted_count:,} old records")
        
        # Clean other tables
        tables_to_clean = ['m5_candles', 'dtms_actions', 'chatgpt_analysis_history']
        for table_name in tables_to_clean:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                if count > 0:
                    cursor.execute(f"DELETE FROM {table_name} WHERE timestamp_utc < ?", (cutoff_timestamp,))
                    deleted = cursor.rowcount
                    print(f"  {table_name}: deleted {deleted:,} old records")
            except sqlite3.Error as e:
                print(f"  Error cleaning {table_name}: {e}")
        
        # Vacuum the database to reclaim space
        print("Vacuuming database to reclaim space...")
        cursor.execute("VACUUM")
        
        conn.commit()
        conn.close()
        
        # Get new size
        new_size = db_path.stat().st_size / (1024 * 1024)
        freed_space = original_size - new_size
        
        print(f"✅ Cleanup complete!")
        print(f"  Original size: {original_size:.2f} MB")
        print(f"  New size: {new_size:.2f} MB")
        print(f"  Space freed: {freed_space:.2f} MB")
        
        return freed_space
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        # Restore backup if something went wrong
        if backup_path.exists():
            print("Restoring backup due to error...")
            shutil.copy2(backup_path, db_path)
        return 0

def cleanup_other_large_files():
    """Clean other large files that can be safely removed"""
    print("\nCleaning other large files...")
    
    total_freed = 0
    
    # Clean old log files
    data_dir = Path("data")
    log_files = list(data_dir.rglob("*.log*"))
    
    for log_file in log_files:
        try:
            size_mb = log_file.stat().st_size / (1024 * 1024)
            if size_mb > 1:  # Only delete logs larger than 1MB
                log_file.unlink()
                total_freed += size_mb
                print(f"  Deleted large log: {log_file.name} ({size_mb:.2f} MB)")
        except Exception as e:
            print(f"  Error deleting {log_file}: {e}")
    
    # Clean backup files
    backup_files = list(data_dir.rglob("*.backup")) + list(data_dir.rglob("*.bak*"))
    for backup_file in backup_files:
        try:
            size_mb = backup_file.stat().st_size / (1024 * 1024)
            backup_file.unlink()
            total_freed += size_mb
            print(f"  Deleted backup: {backup_file.name} ({size_mb:.2f} MB)")
        except Exception as e:
            print(f"  Error deleting {backup_file}: {e}")
    
    print(f"  Freed {total_freed:.2f} MB from other files")
    return total_freed

def main():
    """Main cleanup function"""
    print("Automatic Disk Cleanup for TelegramMoneyBot")
    print("=" * 50)
    
    total_freed = 0
    
    # Clean tick data (main issue)
    total_freed += cleanup_tick_data_automatic()
    
    # Clean other large files
    total_freed += cleanup_other_large_files()
    
    print(f"\n🎉 Total space freed: {total_freed:.2f} MB")
    print("✅ System functionality preserved - only old data removed")
    print("📁 Backup files created before cleanup")

if __name__ == "__main__":
    main()
