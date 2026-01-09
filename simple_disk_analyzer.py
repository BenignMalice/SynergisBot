#!/usr/bin/env python3
"""
Simple Disk Usage Analyzer for TelegramMoneyBot
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

def analyze_disk_usage():
    """Analyze disk usage and show largest files"""
    print("Analyzing disk usage...")
    
    data_dir = Path("data")
    files_with_sizes = []
    
    # Find all database and log files
    for pattern in ["*.db", "*.sqlite", "*.log", "*.json"]:
        for file_path in data_dir.rglob(pattern):
            try:
                size_mb = file_path.stat().st_size / (1024 * 1024)
                files_with_sizes.append((file_path, size_mb))
            except (OSError, FileNotFoundError):
                continue
    
    # Sort by size
    files_with_sizes.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\nTop 20 largest files:")
    print("-" * 80)
    print(f"{'File':<50} {'Size (MB)':<12}")
    print("-" * 80)
    
    total_size = 0
    for i, (file_path, size_mb) in enumerate(files_with_sizes[:20]):
        relative_path = file_path.relative_to(Path("."))
        print(f"{str(relative_path):<50} {size_mb:<12.2f}")
        total_size += size_mb
    
    print(f"\nTotal size of analyzed files: {total_size:.2f} MB")
    return files_with_sizes

def create_safe_cleanup_script():
    """Create a safe cleanup script"""
    script_content = '''#!/usr/bin/env python3
"""
Safe Database Cleanup Script for TelegramMoneyBot
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

def cleanup_old_logs(days_to_keep=7):
    """Clean old log files"""
    print("Cleaning old log files...")
    data_dir = Path("data")
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    log_files = list(data_dir.rglob("*.log*"))
    cleaned_count = 0
    freed_space = 0
    
    for log_file in log_files:
        try:
            file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
            if file_time < cutoff_date:
                size_mb = log_file.stat().st_size / (1024 * 1024)
                log_file.unlink()
                cleaned_count += 1
                freed_space += size_mb
                print(f"  Deleted: {log_file.name} ({size_mb:.2f} MB)")
        except Exception as e:
            print(f"  Error deleting {log_file}: {e}")
    
    print(f"Cleaned {cleaned_count} log files, freed {freed_space:.2f} MB")
    return freed_space

def cleanup_database_old_data(db_path, days_to_keep=30):
    """Clean old data from database tables"""
    print(f"Cleaning old data from {db_path}...")
    
    if not Path(db_path).exists():
        print(f"  Database not found: {db_path}")
        return 0
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current size
        original_size = Path(db_path).stat().st_size / (1024 * 1024)
        
        # Common timestamp columns to clean
        timestamp_columns = ['timestamp', 'created_at', 'timestamp_utc', 'time_utc', 'date_utc']
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
                    if col[1] in timestamp_columns:
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
                        print(f"  {table_name}: deleted {count_to_delete} old records")
                
            except sqlite3.Error as e:
                print(f"  Error cleaning {table_name}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        # Get new size
        new_size = Path(db_path).stat().st_size / (1024 * 1024)
        freed_space = original_size - new_size
        
        print(f"  Freed {freed_space:.2f} MB from {db_path}")
        return freed_space
        
    except Exception as e:
        print(f"  Error cleaning {db_path}: {e}")
        return 0

def cleanup_backup_files(days_to_keep=30):
    """Clean old backup files"""
    print("Cleaning old backup files...")
    data_dir = Path("data")
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    backup_patterns = ["*.backup", "*.bak*", "*_backup_*"]
    backup_files = []
    
    for pattern in backup_patterns:
        backup_files.extend(data_dir.rglob(pattern))
    
    cleaned_count = 0
    freed_space = 0
    
    for backup_file in backup_files:
        try:
            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_time < cutoff_date:
                size_mb = backup_file.stat().st_size / (1024 * 1024)
                backup_file.unlink()
                cleaned_count += 1
                freed_space += size_mb
                print(f"  Deleted: {backup_file.name} ({size_mb:.2f} MB)")
        except Exception as e:
            print(f"  Error deleting {backup_file}: {e}")
    
    print(f"Cleaned {cleaned_count} backup files, freed {freed_space:.2f} MB")
    return freed_space

def main():
    """Main cleanup function"""
    print("Starting TelegramMoneyBot Disk Cleanup")
    print("=" * 50)
    
    total_freed = 0
    
    # Clean logs
    total_freed += cleanup_old_logs(7)
    
    # Clean databases
    databases_to_clean = [
        "data/bot.sqlite",
        "data/journal.sqlite", 
        "data/recommendations.sqlite",
        "data/conversations.sqlite",
        "data/historical_database.sqlite",
        "data/clean_historical_database.sqlite",
        "data/advanced_analytics.sqlite",
        "data/mtf_trading.db",
        "data/auto_execution.db",
        "data/oco_tracker.db",
        "data/risk_performance.db",
        "data/symbol_optimization.db",
        "data/unified_tick_pipeline/tick_data.db",
        "data/unified_tick_pipeline/chatgpt_analysis.db",
        "data/unified_tick_pipeline/dtms_actions.db",
        "data/unified_tick_pipeline/m5_candles.db",
        "data/unified_tick_pipeline/performance_logs.db",
        "data/unified_tick_pipeline/system_metrics.db"
    ]
    
    for db_path in databases_to_clean:
        if Path(db_path).exists():
            total_freed += cleanup_database_old_data(db_path, 30)
    
    # Clean backup files
    total_freed += cleanup_backup_files(30)
    
    print("\\n" + "=" * 50)
    print(f"Cleanup complete! Total space freed: {total_freed:.2f} MB")
    print("System functionality preserved - only old data removed")

if __name__ == "__main__":
    main()
'''
    
    with open("safe_disk_cleanup.py", "w") as f:
        f.write(script_content)
    
    print("Safe cleanup script created: safe_disk_cleanup.py")

def main():
    """Main analysis function"""
    print("TelegramMoneyBot Disk Usage Analyzer")
    print("=" * 50)
    
    # Analyze disk usage
    files_with_sizes = analyze_disk_usage()
    
    # Create cleanup script
    create_safe_cleanup_script()
    
    print(f"\nRecommendations:")
    print("1. Run: python safe_disk_cleanup.py")
    print("2. This will safely remove old data while preserving system functionality")
    print("3. Only removes data older than 30 days (databases) and 7 days (logs)")

if __name__ == "__main__":
    main()
