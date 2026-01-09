#!/usr/bin/env python3
"""
Aggressive Cleanup Script for TelegramMoneyBot
==============================================
This script provides more aggressive cleanup options for the large tick_data.db file.
"""

import os
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta

def analyze_tick_data_db():
    """Analyze the tick_data.db file to understand its structure"""
    db_path = Path("data/unified_tick_pipeline/tick_data.db")
    
    if not db_path.exists():
        print("tick_data.db not found")
        return
    
    print(f"Analyzing {db_path}...")
    print(f"Current size: {db_path.stat().st_size / (1024 * 1024):.2f} MB")
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get table information
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"\nTables in tick_data.db:")
        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table_name}: {count:,} records")
        
        # Check for timestamp columns
        for (table_name,) in tables:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            timestamp_cols = [col[1] for col in columns if 'time' in col[1].lower() or 'timestamp' in col[1].lower()]
            if timestamp_cols:
                print(f"  {table_name} timestamp columns: {timestamp_cols}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error analyzing database: {e}")

def cleanup_tick_data_aggressive(days_to_keep=7):
    """Aggressively clean tick data - keep only last 7 days"""
    db_path = Path("data/unified_tick_pipeline/tick_data.db")
    
    if not db_path.exists():
        print("tick_data.db not found")
        return 0
    
    print(f"Aggressively cleaning tick_data.db (keeping last {days_to_keep} days)...")
    
    # Create backup first
    backup_path = db_path.with_suffix('.db.backup')
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        original_size = db_path.stat().st_size / (1024 * 1024)
        cutoff_timestamp = int((datetime.now() - timedelta(days=days_to_keep)).timestamp())
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        total_deleted = 0
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
                    # Count records to delete
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {timestamp_col} < ?", (cutoff_timestamp,))
                    count_to_delete = cursor.fetchone()[0]
                    
                    if count_to_delete > 0:
                        # Delete old records
                        cursor.execute(f"DELETE FROM {table_name} WHERE {timestamp_col} < ?", (cutoff_timestamp,))
                        total_deleted += count_to_delete
                        print(f"  {table_name}: deleted {count_to_delete:,} old records")
                
            except sqlite3.Error as e:
                print(f"  Error cleaning {table_name}: {e}")
                continue
        
        # Vacuum the database to reclaim space
        print("  Vacuuming database to reclaim space...")
        cursor.execute("VACUUM")
        
        conn.commit()
        conn.close()
        
        # Get new size
        new_size = db_path.stat().st_size / (1024 * 1024)
        freed_space = original_size - new_size
        
        print(f"  Freed {freed_space:.2f} MB from tick_data.db")
        print(f"  New size: {new_size:.2f} MB")
        
        return freed_space
        
    except Exception as e:
        print(f"  Error cleaning tick_data.db: {e}")
        # Restore backup if something went wrong
        if backup_path.exists():
            print("  Restoring backup due to error...")
            shutil.copy2(backup_path, db_path)
        return 0

def create_minimal_tick_data_db():
    """Create a minimal tick_data.db with only essential data"""
    db_path = Path("data/unified_tick_pipeline/tick_data.db")
    
    if not db_path.exists():
        print("tick_data.db not found")
        return 0
    
    print("Creating minimal tick_data.db...")
    
    # Create backup
    backup_path = db_path.with_suffix('.db.full_backup')
    print(f"Creating full backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        original_size = db_path.stat().st_size / (1024 * 1024)
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        # For each table, keep only the most recent 1000 records
        for (table_name,) in tables:
            try:
                # Get total count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                total_count = cursor.fetchone()[0]
                
                if total_count > 1000:
                    # Find the primary key or rowid
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()
                    
                    # Try to find a primary key
                    pk_col = None
                    for col in columns:
                        if col[5]:  # Primary key flag
                            pk_col = col[1]
                            break
                    
                    if not pk_col:
                        pk_col = "rowid"
                    
                    # Delete all but the most recent 1000 records
                    cursor.execute(f"""
                        DELETE FROM {table_name} 
                        WHERE {pk_col} NOT IN (
                            SELECT {pk_col} FROM {table_name} 
                            ORDER BY {pk_col} DESC 
                            LIMIT 1000
                        )
                    """)
                    
                    deleted_count = cursor.rowcount
                    print(f"  {table_name}: kept 1000 most recent records, deleted {deleted_count:,} old records")
                
            except sqlite3.Error as e:
                print(f"  Error cleaning {table_name}: {e}")
                continue
        
        # Vacuum the database
        print("  Vacuuming database...")
        cursor.execute("VACUUM")
        
        conn.commit()
        conn.close()
        
        # Get new size
        new_size = db_path.stat().st_size / (1024 * 1024)
        freed_space = original_size - new_size
        
        print(f"  Freed {freed_space:.2f} MB from tick_data.db")
        print(f"  New size: {new_size:.2f} MB")
        
        return freed_space
        
    except Exception as e:
        print(f"  Error creating minimal database: {e}")
        # Restore backup if something went wrong
        if backup_path.exists():
            print("  Restoring backup due to error...")
            shutil.copy2(backup_path, db_path)
        return 0

def main():
    """Main cleanup function with options"""
    print("Aggressive Disk Cleanup for TelegramMoneyBot")
    print("=" * 50)
    
    # Analyze current state
    analyze_tick_data_db()
    
    print("\nCleanup options:")
    print("1. Aggressive cleanup (keep last 7 days)")
    print("2. Minimal database (keep 1000 most recent records per table)")
    print("3. Exit")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        freed = cleanup_tick_data_aggressive(7)
        print(f"\nAggressive cleanup complete! Freed {freed:.2f} MB")
    elif choice == "2":
        freed = create_minimal_tick_data_db()
        print(f"\nMinimal database created! Freed {freed:.2f} MB")
    elif choice == "3":
        print("Exiting...")
        return
    else:
        print("Invalid choice")
        return
    
    print("\nNote: Backups were created before cleanup")
    print("If you experience issues, you can restore from the backup files")

if __name__ == "__main__":
    main()
