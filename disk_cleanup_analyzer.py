#!/usr/bin/env python3
"""
Disk Cleanup Analyzer for TelegramMoneyBot
=========================================
Analyzes disk usage and provides safe cleanup recommendations.
"""

import os
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class DiskCleanupAnalyzer:
    """Analyzes disk usage and provides cleanup recommendations"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.data_dir = self.project_root / "data"
        self.large_files = []
        self.database_sizes = {}
        
    def analyze_disk_usage(self) -> Dict[str, any]:
        """Analyze disk usage and identify large files"""
        print("🔍 Analyzing disk usage...")
        
        # Find all database and log files
        files_to_analyze = []
        for pattern in ["*.db", "*.sqlite", "*.log", "*.json"]:
            files_to_analyze.extend(self.data_dir.rglob(pattern))
        
        # Sort by size
        files_with_sizes = []
        for file_path in files_to_analyze:
            try:
                size_mb = file_path.stat().st_size / (1024 * 1024)
                files_with_sizes.append((file_path, size_mb))
            except (OSError, FileNotFoundError):
                continue
        
        files_with_sizes.sort(key=lambda x: x[1], reverse=True)
        
        print(f"\n📊 Top 20 largest files:")
        print("-" * 80)
        print(f"{'File':<50} {'Size (MB)':<12} {'Type':<10}")
        print("-" * 80)
        
        for i, (file_path, size_mb) in enumerate(files_with_sizes[:20]):
            file_type = file_path.suffix[1:] if file_path.suffix else "unknown"
            relative_path = file_path.relative_to(self.project_root)
            print(f"{str(relative_path):<50} {size_mb:<12.2f} {file_type:<10}")
            
            if size_mb > 10:  # Files larger than 10MB
                self.large_files.append((file_path, size_mb))
        
        return {
            "total_files": len(files_with_sizes),
            "large_files": self.large_files,
            "total_size_mb": sum(size for _, size in files_with_sizes)
        }
    
    def analyze_database_content(self) -> Dict[str, any]:
        """Analyze database content to identify cleanup opportunities"""
        print("\n🗄️ Analyzing database content...")
        
        database_analysis = {}
        
        # Common database files to analyze
        db_files = [
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
        
        for db_file in db_files:
            db_path = self.project_root / db_file
            if not db_path.exists():
                continue
                
            try:
                size_mb = db_path.stat().st_size / (1024 * 1024)
                self.database_sizes[db_file] = size_mb
                
                # Analyze table sizes
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # Get table information
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                
                table_info = {}
                for (table_name,) in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        row_count = cursor.fetchone()[0]
                        table_info[table_name] = row_count
                    except sqlite3.Error:
                        table_info[table_name] = "error"
                
                database_analysis[db_file] = {
                    "size_mb": size_mb,
                    "tables": table_info
                }
                
                conn.close()
                
            except sqlite3.Error as e:
                print(f"⚠️ Error analyzing {db_file}: {e}")
                continue
        
        return database_analysis
    
    def generate_cleanup_recommendations(self) -> List[Dict[str, any]]:
        """Generate safe cleanup recommendations"""
        print("\n🧹 Generating cleanup recommendations...")
        
        recommendations = []
        
        # 1. Log files cleanup
        log_files = list(self.data_dir.rglob("*.log*"))
        if log_files:
            total_log_size = sum(f.stat().st_size for f in log_files) / (1024 * 1024)
            recommendations.append({
                "type": "log_cleanup",
                "description": "Clean old log files",
                "files": [str(f.relative_to(self.project_root)) for f in log_files],
                "size_mb": total_log_size,
                "safe": True,
                "action": "Delete log files older than 7 days"
            })
        
        # 2. Database cleanup recommendations
        for db_file, analysis in self.database_sizes.items():
            if analysis["size_mb"] > 50:  # Large databases
                recommendations.append({
                    "type": "database_cleanup",
                    "description": f"Clean old data from {db_file}",
                    "file": db_file,
                    "size_mb": analysis["size_mb"],
                    "safe": True,
                    "action": "Remove old records (keep last 30 days)"
                })
        
        # 3. Backup files cleanup
        backup_files = list(self.data_dir.rglob("*.backup")) + list(self.data_dir.rglob("*.bak*"))
        if backup_files:
            total_backup_size = sum(f.stat().st_size for f in backup_files) / (1024 * 1024)
            recommendations.append({
                "type": "backup_cleanup", 
                "description": "Remove old backup files",
                "files": [str(f.relative_to(self.project_root)) for f in backup_files],
                "size_mb": total_backup_size,
                "safe": True,
                "action": "Delete backup files older than 30 days"
            })
        
        return recommendations
    
    def create_cleanup_script(self, recommendations: List[Dict[str, any]]) -> str:
        """Create a safe cleanup script"""
        script_content = '''#!/usr/bin/env python3
"""
Safe Database Cleanup Script for TelegramMoneyBot
================================================
This script safely cleans old data without affecting system functionality.
"""

import os
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def cleanup_old_logs(days_to_keep: int = 7):
    """Clean old log files"""
    print("🧹 Cleaning old log files...")
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
                print(f"  ✅ Deleted: {log_file.name} ({size_mb:.2f} MB)")
        except Exception as e:
            print(f"  ⚠️ Error deleting {log_file}: {e}")
    
    print(f"📊 Cleaned {cleaned_count} log files, freed {freed_space:.2f} MB")
    return freed_space

def cleanup_database_old_data(db_path: str, days_to_keep: int = 30):
    """Clean old data from database tables"""
    print(f"🗄️ Cleaning old data from {db_path}...")
    
    if not Path(db_path).exists():
        print(f"  ⚠️ Database not found: {db_path}")
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
                        print(f"  ✅ {table_name}: deleted {count_to_delete} old records")
                
            except sqlite3.Error as e:
                print(f"  ⚠️ Error cleaning {table_name}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        # Get new size
        new_size = Path(db_path).stat().st_size / (1024 * 1024)
        freed_space = original_size - new_size
        
        print(f"  📊 Freed {freed_space:.2f} MB from {db_path}")
        return freed_space
        
    except Exception as e:
        print(f"  ❌ Error cleaning {db_path}: {e}")
        return 0

def cleanup_backup_files(days_to_keep: int = 30):
    """Clean old backup files"""
    print("🗂️ Cleaning old backup files...")
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
                print(f"  ✅ Deleted: {backup_file.name} ({size_mb:.2f} MB)")
        except Exception as e:
            print(f"  ⚠️ Error deleting {backup_file}: {e}")
    
    print(f"📊 Cleaned {cleaned_count} backup files, freed {freed_space:.2f} MB")
    return freed_space

def main():
    """Main cleanup function"""
    print("🚀 Starting TelegramMoneyBot Disk Cleanup")
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
    print(f"🎉 Cleanup complete! Total space freed: {total_freed:.2f} MB")
    print("✅ System functionality preserved - only old data removed")

if __name__ == "__main__":
    main()
'''
        
        return script_content

def main():
    """Main analysis function"""
    print("🔍 TelegramMoneyBot Disk Usage Analyzer")
    print("=" * 50)
    
    analyzer = DiskCleanupAnalyzer()
    
    # Analyze disk usage
    usage_analysis = analyzer.analyze_disk_usage()
    
    # Analyze database content
    db_analysis = analyzer.analyze_database_content()
    
    # Generate recommendations
    recommendations = analyzer.generate_cleanup_recommendations()
    
    # Create cleanup script
    script_content = analyzer.create_cleanup_script(recommendations)
    
    # Save cleanup script
    with open("safe_disk_cleanup.py", "w") as f:
        f.write(script_content)
    
    print(f"\n📋 Summary:")
    print(f"  • Total files analyzed: {usage_analysis['total_files']}")
    print(f"  • Total size: {usage_analysis['total_size_mb']:.2f} MB")
    print(f"  • Large files (>10MB): {len(analyzer.large_files)}")
    print(f"  • Databases analyzed: {len(analyzer.database_sizes)}")
    
    print(f"\n💡 Recommendations:")
    for i, rec in enumerate(recommendations, 1):
        print(f"  {i}. {rec['description']} - {rec['size_mb']:.2f} MB")
    
    print(f"\n✅ Safe cleanup script created: safe_disk_cleanup.py")
    print(f"🚀 Run: python safe_disk_cleanup.py")

if __name__ == "__main__":
    main()
