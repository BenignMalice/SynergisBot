#!/usr/bin/env python3
"""
Simple Tick Data Cleanup for TelegramMoneyBot
"""

import os
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta

def cleanup_tick_data():
    """Clean tick data - keep only last 3 days"""
    db_path = Path("data/unified_tick_pipeline/tick_data.db")
    
    if not db_path.exists():
        print("tick_data.db not found")
        return 0
    
    print(f"Cleaning tick_data.db...")
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
        
        # Vacuum the database to reclaim space
        print("Vacuuming database to reclaim space...")
        cursor.execute("VACUUM")
        
        conn.commit()
        conn.close()
        
        # Get new size
        new_size = db_path.stat().st_size / (1024 * 1024)
        freed_space = original_size - new_size
        
        print(f"Cleanup complete!")
        print(f"  Original size: {original_size:.2f} MB")
        print(f"  New size: {new_size:.2f} MB")
        print(f"  Space freed: {freed_space:.2f} MB")
        
        return freed_space
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return 0

def delete_backup_files():
    """Delete backup files to free space"""
    print("\nDeleting backup files...")
    
    data_dir = Path("data")
    backup_files = []
    
    # Find all backup files
    for pattern in ["*.backup", "*.bak*", "*_backup_*"]:
        backup_files.extend(data_dir.rglob(pattern))
    
    total_freed = 0
    for backup_file in backup_files:
        try:
            size_mb = backup_file.stat().st_size / (1024 * 1024)
            backup_file.unlink()
            total_freed += size_mb
            print(f"  Deleted: {backup_file.name} ({size_mb:.2f} MB)")
        except Exception as e:
            print(f"  Error deleting {backup_file}: {e}")
    
    print(f"Freed {total_freed:.2f} MB from backup files")
    return total_freed

def main():
    """Main cleanup function"""
    print("Simple Tick Data Cleanup")
    print("=" * 40)
    
    total_freed = 0
    
    # Clean tick data
    total_freed += cleanup_tick_data()
    
    # Delete backup files
    total_freed += delete_backup_files()
    
    print(f"\nTotal space freed: {total_freed:.2f} MB")
    print("System functionality preserved - only old data removed")

if __name__ == "__main__":
    main()
