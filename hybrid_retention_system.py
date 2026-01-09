#!/usr/bin/env python3
"""
Hybrid Retention System
=======================
Implements intelligent data retention with tiered storage strategy.
"""

import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HybridRetentionSystem:
    """
    Hybrid retention system with tiered data management:
    - Recent data (0-6 hours): Keep all
    - Older data (6-24 hours): Sample every 3rd record
    - Very old data (24+ hours): Delete completely
    - Analysis data: Keep 7 days
    """
    
    def __init__(self, db_path="data/unified_tick_pipeline/tick_data.db"):
        self.db_path = Path(db_path)
        self.is_running = False
        self.cleanup_task = None
        
        # Retention policies
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
            },
            'system_metrics': {
                'retention_days': 3,    # Keep system metrics for 3 days
                'max_size_mb': 50       # Maximum system metrics size
            },
            'logs': {
                'retention_days': 7,    # Keep logs for 7 days
                'max_size_mb': 100      # Maximum log size
            }
        }
        
        # Cleanup schedule
        self.cleanup_interval_hours = 1  # Run every hour
        self.last_cleanup = None
        
        logger.info("HybridRetentionSystem initialized")
    
    async def start(self):
        """Start the retention system"""
        if self.is_running:
            logger.warning("Retention system already running")
            return
        
        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Hybrid retention system started")
    
    async def stop(self):
        """Stop the retention system"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Hybrid retention system stopped")
    
    async def _cleanup_loop(self):
        """Main cleanup loop - runs every hour"""
        while self.is_running:
            try:
                await asyncio.sleep(self.cleanup_interval_hours * 3600)  # Convert hours to seconds
                
                if not self.is_running:
                    break
                
                logger.info("Starting scheduled retention cleanup...")
                await self.run_retention_cleanup()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def run_retention_cleanup(self):
        """Run the complete retention cleanup process"""
        try:
            # Get current database info
            info = self.get_database_info()
            if "error" in info:
                logger.error(f"Database error: {info['error']}")
                return
            
            logger.info(f"Starting retention cleanup - Current size: {info['file_size_mb']}MB")
            
            # Step 1: Clean up very old data (24+ hours)
            await self._cleanup_very_old_data()
            
            # Step 2: Sample older data (6-24 hours)
            await self._sample_older_data()
            
            # Step 3: Clean up analysis data (older than 7 days)
            await self._cleanup_old_analysis_data()
            
            # Step 4: Clean up system metrics (older than 3 days)
            await self._cleanup_old_system_metrics()
            
            # Step 5: Optimize database
            await self._optimize_database()
            
            # Step 6: Check size limits
            await self._enforce_size_limits()
            
            # Update last cleanup time
            self.last_cleanup = datetime.now()
            
            # Get final info
            final_info = self.get_database_info()
            logger.info(f"Retention cleanup completed - Final size: {final_info['file_size_mb']}MB")
            
        except Exception as e:
            logger.error(f"Error in retention cleanup: {e}")
    
    async def _cleanup_very_old_data(self):
        """Delete data older than 24 hours"""
        logger.info("Cleaning up data older than 24 hours...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff_date = datetime.now() - timedelta(hours=24)
            cutoff_str = cutoff_date.isoformat()
            
            # Delete old tick data
            cursor.execute("""
                DELETE FROM unified_ticks 
                WHERE timestamp_utc < ?
            """, (cutoff_str,))
            
            deleted_ticks = cursor.rowcount
            logger.info(f"Deleted {deleted_ticks} very old tick records")
            
            conn.commit()
            
        finally:
            conn.close()
    
    async def _sample_older_data(self):
        """Sample data from 6-24 hours (keep every 3rd record)"""
        logger.info("Sampling data from 6-24 hours (keeping every 3rd record)...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
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
                logger.info("No records in 6-24 hour range to sample")
                return
            
            # Keep every 3rd record (delete 2 out of 3)
            records_to_delete = []
            for i, (record_id,) in enumerate(records):
                if i % 3 != 0:  # Keep every 3rd record (0, 3, 6, 9, ...)
                    records_to_delete.append(record_id)
            
            # Delete non-sampled records
            if records_to_delete:
                placeholders = ','.join(['?' for _ in records_to_delete])
                cursor.execute(f"""
                    DELETE FROM unified_ticks 
                    WHERE id IN ({placeholders})
                """, records_to_delete)
                
                deleted_count = cursor.rowcount
                logger.info(f"Sampled {total_records} records, deleted {deleted_count}, kept {total_records - deleted_count}")
            
            conn.commit()
            
        finally:
            conn.close()
    
    async def _cleanup_old_analysis_data(self):
        """Clean up analysis data older than 7 days"""
        logger.info("Cleaning up analysis data older than 7 days...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff_date = datetime.now() - timedelta(days=7)
            cutoff_str = cutoff_date.isoformat()
            
            # Clean up ChatGPT analysis history
            cursor.execute("""
                DELETE FROM chatgpt_analysis_history 
                WHERE timestamp < ?
            """, (cutoff_str,))
            
            deleted_analysis = cursor.rowcount
            logger.info(f"Deleted {deleted_analysis} old analysis records")
            
            conn.commit()
            
        finally:
            conn.close()
    
    async def _cleanup_old_system_metrics(self):
        """Clean up system metrics older than 3 days"""
        logger.info("Cleaning up system metrics older than 3 days...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff_date = datetime.now() - timedelta(days=3)
            cutoff_str = cutoff_date.isoformat()
            
            # Clean up system health records
            cursor.execute("""
                DELETE FROM system_health 
                WHERE timestamp < ?
            """, (cutoff_str,))
            
            deleted_metrics = cursor.rowcount
            logger.info(f"Deleted {deleted_metrics} old system metric records")
            
            conn.commit()
            
        finally:
            conn.close()
    
    async def _optimize_database(self):
        """Optimize database performance"""
        logger.info("Optimizing database...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Enable WAL mode
            cursor.execute("PRAGMA journal_mode=WAL")
            
            # Optimize
            cursor.execute("PRAGMA optimize")
            
            # Vacuum to reclaim space
            cursor.execute("VACUUM")
            
            # Analyze for better query planning
            cursor.execute("ANALYZE")
            
            conn.commit()
            logger.info("Database optimization completed")
            
        finally:
            conn.close()
    
    async def _enforce_size_limits(self):
        """Enforce database size limits"""
        info = self.get_database_info()
        if "error" in info:
            return
        
        current_size_mb = info['file_size_mb']
        max_size_mb = self.retention_policies['tick_data']['max_size_mb']
        emergency_size_mb = self.retention_policies['tick_data']['emergency_size_mb']
        
        if current_size_mb > emergency_size_mb:
            logger.warning(f"EMERGENCY: Database size {current_size_mb}MB exceeds emergency limit {emergency_size_mb}MB")
            await self._emergency_cleanup()
        elif current_size_mb > max_size_mb:
            logger.warning(f"Database size {current_size_mb}MB exceeds target limit {max_size_mb}MB")
            await self._aggressive_cleanup()
    
    async def _emergency_cleanup(self):
        """Emergency cleanup - keep only last 6 hours"""
        logger.warning("Performing emergency cleanup - keeping only last 6 hours")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff_date = datetime.now() - timedelta(hours=6)
            cutoff_str = cutoff_date.isoformat()
            
            cursor.execute("""
                DELETE FROM unified_ticks 
                WHERE timestamp_utc < ?
            """, (cutoff_str,))
            
            deleted_count = cursor.rowcount
            logger.warning(f"Emergency cleanup deleted {deleted_count} records")
            
            conn.commit()
            
        finally:
            conn.close()
    
    async def _aggressive_cleanup(self):
        """Aggressive cleanup - sample recent data more aggressively"""
        logger.warning("Performing aggressive cleanup")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Sample recent data more aggressively (keep every 5th record)
            cursor.execute("""
                DELETE FROM unified_ticks 
                WHERE id NOT IN (
                    SELECT id FROM unified_ticks 
                    WHERE id % 5 = 0
                )
            """)
            
            deleted_count = cursor.rowcount
            logger.warning(f"Aggressive cleanup deleted {deleted_count} records")
            
            conn.commit()
            
        finally:
            conn.close()
    
    def get_database_info(self):
        """Get current database information"""
        if not self.db_path.exists():
            return {"error": "Database file not found"}
        
        file_size = self.db_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
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
            
            return {
                "file_size_mb": round(file_size_mb, 2),
                "tables": tables,
                "record_counts": record_counts,
                "last_cleanup": self.last_cleanup.isoformat() if self.last_cleanup else None
            }
            
        finally:
            conn.close()
    
    def get_retention_status(self):
        """Get current retention system status"""
        return {
            "is_running": self.is_running,
            "cleanup_interval_hours": self.cleanup_interval_hours,
            "last_cleanup": self.last_cleanup.isoformat() if self.last_cleanup else None,
            "retention_policies": self.retention_policies
        }

async def main():
    """Main function to demonstrate the retention system"""
    print("=" * 80)
    print("HYBRID RETENTION SYSTEM")
    print("=" * 80)
    
    retention_system = HybridRetentionSystem()
    
    # Show current status
    info = retention_system.get_database_info()
    if "error" in info:
        print(f"ERROR: {info['error']}")
        return
    
    print(f"Current database size: {info['file_size_mb']}MB")
    print(f"Record counts:")
    for table, count in info['record_counts'].items():
        print(f"  - {table}: {count:,} records")
    
    print("\nRETENTION POLICIES:")
    policies = retention_system.retention_policies
    for data_type, policy in policies.items():
        print(f"  - {data_type}: {policy}")
    
    print("\n" + "=" * 80)
    print("To start the retention system:")
    print("  python hybrid_retention_system.py --start")
    print("To run manual cleanup:")
    print("  python hybrid_retention_system.py --cleanup")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        retention_system = HybridRetentionSystem()
        
        if sys.argv[1] == "--start":
            print("Starting hybrid retention system...")
            asyncio.run(retention_system.start())
        elif sys.argv[1] == "--cleanup":
            print("Running manual retention cleanup...")
            asyncio.run(retention_system.run_retention_cleanup())
        elif sys.argv[1] == "--status":
            info = retention_system.get_database_info()
            status = retention_system.get_retention_status()
            print(f"Database: {info}")
            print(f"Retention Status: {status}")
        else:
            print("Unknown option. Use --start, --cleanup, or --status")
    else:
        asyncio.run(main())
