"""
Data Retention and Compression Manager
Implements tiered data retention policies with compression and archival strategies
"""

import asyncio
import sqlite3
import logging
import gzip
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

class RetentionTier(Enum):
    """Data retention tiers based on age and importance."""
    HOT = "hot"           # Recent data (0-7 days) - Full resolution
    WARM = "warm"         # Medium age (7-30 days) - Compressed
    COLD = "cold"         # Old data (30-365 days) - Highly compressed
    ARCHIVE = "archive"   # Very old data (>365 days) - Archived

class CompressionLevel(Enum):
    """Compression levels for different data types."""
    NONE = 0
    LIGHT = 1
    MEDIUM = 2
    HEAVY = 3
    MAXIMUM = 4

@dataclass
class RetentionPolicy:
    """Data retention policy configuration."""
    symbol: str
    timeframe: str
    hot_days: int = 7
    warm_days: int = 30
    cold_days: int = 365
    archive_days: int = 1095  # 3 years
    
    # Compression settings
    hot_compression: CompressionLevel = CompressionLevel.NONE
    warm_compression: CompressionLevel = CompressionLevel.LIGHT
    cold_compression: CompressionLevel = CompressionLevel.HEAVY
    archive_compression: CompressionLevel = CompressionLevel.MAXIMUM
    
    # Sampling settings for older data
    warm_sampling_ratio: float = 0.5    # Keep 50% of warm data
    cold_sampling_ratio: float = 0.1     # Keep 10% of cold data
    archive_sampling_ratio: float = 0.01 # Keep 1% of archive data

@dataclass
class CompressionStats:
    """Compression statistics."""
    original_size: int
    compressed_size: int
    compression_ratio: float
    compression_time_ms: float

class DataRetentionManager:
    """Manages data retention, compression, and archival policies."""
    
    def __init__(self, db_path: str, archive_path: str = "archives"):
        self.db_path = db_path
        self.archive_path = Path(archive_path)
        self.archive_path.mkdir(exist_ok=True)
        
        # Retention policies by symbol/timeframe
        self.policies: Dict[str, RetentionPolicy] = {}
        
        # Background task management
        self.retention_task = None
        self.running = False
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            "compression_operations": 0,
            "archival_operations": 0,
            "deletion_operations": 0,
            "total_space_saved": 0,
            "last_retention_run": None
        }
        
        logger.info(f"DataRetentionManager initialized: {db_path}")
    
    def add_retention_policy(self, policy: RetentionPolicy):
        """Add a retention policy for a specific symbol/timeframe."""
        key = f"{policy.symbol}_{policy.timeframe}"
        self.policies[key] = policy
        logger.info(f"Added retention policy for {key}: {policy.hot_days}d hot, {policy.warm_days}d warm")
    
    def get_retention_tier(self, timestamp: int, policy: RetentionPolicy) -> RetentionTier:
        """Determine retention tier based on data age."""
        now = int(time.time() * 1000)
        age_days = (now - timestamp) / (1000 * 60 * 60 * 24)
        
        if age_days <= policy.hot_days:
            return RetentionTier.HOT
        elif age_days <= policy.warm_days:
            return RetentionTier.WARM
        elif age_days <= policy.cold_days:
            return RetentionTier.COLD
        else:
            return RetentionTier.ARCHIVE
    
    async def compress_data(self, data: bytes, level: CompressionLevel) -> Tuple[bytes, CompressionStats]:
        """Compress data using specified compression level."""
        start_time = time.perf_counter()
        
        if level == CompressionLevel.NONE:
            compressed_data = data
        elif level == CompressionLevel.LIGHT:
            compressed_data = gzip.compress(data, compresslevel=1)
        elif level == CompressionLevel.MEDIUM:
            compressed_data = gzip.compress(data, compresslevel=6)
        elif level == CompressionLevel.HEAVY:
            compressed_data = gzip.compress(data, compresslevel=9)
        else:  # MAXIMUM
            compressed_data = gzip.compress(data, compresslevel=9)
            # Additional compression for maximum level
            compressed_data = gzip.compress(compressed_data, compresslevel=9)
        
        compression_time = (time.perf_counter() - start_time) * 1000
        
        stats = CompressionStats(
            original_size=len(data),
            compressed_size=len(compressed_data),
            compression_ratio=len(compressed_data) / len(data) if len(data) > 0 else 0,
            compression_time_ms=compression_time
        )
        
        return compressed_data, stats
    
    async def sample_data(self, data_points: List[Dict], sampling_ratio: float) -> List[Dict]:
        """Sample data points based on sampling ratio."""
        if sampling_ratio >= 1.0:
            return data_points
        
        sample_size = max(1, int(len(data_points) * sampling_ratio))
        
        # Use systematic sampling to maintain temporal distribution
        if len(data_points) <= sample_size:
            return data_points
        
        step = len(data_points) // sample_size
        sampled = []
        
        for i in range(0, len(data_points), step):
            if len(sampled) >= sample_size:
                break
            sampled.append(data_points[i])
        
        return sampled
    
    async def archive_data(self, symbol: str, timeframe: str, data: List[Dict], 
                          compression_level: CompressionLevel) -> str:
        """Archive data to compressed files."""
        # Create archive directory structure
        archive_dir = self.archive_path / symbol / timeframe
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate archive filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_file = archive_dir / f"{symbol}_{timeframe}_{timestamp}.json.gz"
        
        # Serialize data
        json_data = json.dumps(data, default=str).encode('utf-8')
        
        # Write compressed data to file (gzip.open handles compression)
        with gzip.open(archive_file, 'wb') as f:
            f.write(json_data)
        
        # Calculate compression stats
        compressed_size = archive_file.stat().st_size
        stats = CompressionStats(
            original_size=len(json_data),
            compressed_size=compressed_size,
            compression_ratio=compressed_size / len(json_data) if len(json_data) > 0 else 0,
            compression_time_ms=0
        )
        
        logger.info(f"Archived {len(data)} records to {archive_file} "
                   f"(compression: {stats.compression_ratio:.2%})")
        
        return str(archive_file)
    
    async def process_retention_for_symbol(self, symbol: str, timeframe: str):
        """Process retention for a specific symbol/timeframe."""
        key = f"{symbol}_{timeframe}"
        policy = self.policies.get(key)
        
        if not policy:
            logger.warning(f"No retention policy found for {key}")
            return
        
        logger.info(f"Processing retention for {key}")
        
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get data older than hot tier
            cutoff_timestamp = int((time.time() - policy.hot_days * 24 * 60 * 60) * 1000)
            
            # Query data to process
            cursor.execute("""
                SELECT timestamp_utc, data_json 
                FROM tick_data 
                WHERE symbol = ? AND timeframe = ? AND timestamp_utc < ?
                ORDER BY timestamp_utc
            """, (symbol, timeframe, cutoff_timestamp))
            
            old_data = cursor.fetchall()
            
            if not old_data:
                logger.info(f"No old data found for {key}")
                return
            
            # Group data by retention tier
            tier_data = {
                RetentionTier.WARM: [],
                RetentionTier.COLD: [],
                RetentionTier.ARCHIVE: []
            }
            
            for timestamp, data_json in old_data:
                tier = self.get_retention_tier(timestamp, policy)
                if tier in tier_data:
                    tier_data[tier].append({
                        'timestamp': timestamp,
                        'data': json.loads(data_json)
                    })
            
            # Process each tier
            for tier, data_list in tier_data.items():
                if not data_list:
                    continue
                
                logger.info(f"Processing {len(data_list)} records for {tier.value} tier")
                
                # Apply sampling
                if tier == RetentionTier.WARM:
                    sampled_data = await self.sample_data(data_list, policy.warm_sampling_ratio)
                elif tier == RetentionTier.COLD:
                    sampled_data = await self.sample_data(data_list, policy.cold_sampling_ratio)
                else:  # ARCHIVE
                    sampled_data = await self.sample_data(data_list, policy.archive_sampling_ratio)
                
                # Archive sampled data
                if sampled_data:
                    compression_level = {
                        RetentionTier.WARM: policy.warm_compression,
                        RetentionTier.COLD: policy.cold_compression,
                        RetentionTier.ARCHIVE: policy.archive_compression
                    }[tier]
                    
                    archive_file = await self.archive_data(symbol, timeframe, sampled_data, compression_level)
                    
                    # Delete original data from database
                    timestamps = [item['timestamp'] for item in data_list]
                    placeholders = ','.join(['?' for _ in timestamps])
                    
                    cursor.execute(f"""
                        DELETE FROM tick_data 
                        WHERE symbol = ? AND timeframe = ? AND timestamp_utc IN ({placeholders})
                    """, [symbol, timeframe] + timestamps)
                    
                    self.stats["archival_operations"] += 1
                    self.stats["deletion_operations"] += len(timestamps)
            
            conn.commit()
            conn.close()
            
            logger.info(f"Completed retention processing for {key}")
            
        except Exception as e:
            logger.error(f"Error processing retention for {key}: {e}")
    
    async def run_retention_cycle(self):
        """Run a complete retention cycle for all policies."""
        logger.info("Starting retention cycle")
        start_time = time.time()
        
        try:
            # Process each policy
            for key, policy in self.policies.items():
                symbol, timeframe = key.split('_', 1)
                await self.process_retention_for_symbol(symbol, timeframe)
            
            # Update statistics
            self.stats["last_retention_run"] = datetime.now(timezone.utc)
            
            cycle_time = time.time() - start_time
            logger.info(f"Retention cycle completed in {cycle_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Error in retention cycle: {e}")
    
    async def start_background_retention(self, interval_hours: int = 24):
        """Start background retention processing."""
        if self.running:
            logger.warning("Background retention already running")
            return
        
        self.running = True
        logger.info(f"Starting background retention (interval: {interval_hours}h)")
        
        async def retention_loop():
            while self.running:
                try:
                    await self.run_retention_cycle()
                    await asyncio.sleep(interval_hours * 3600)
                except Exception as e:
                    logger.error(f"Error in retention loop: {e}")
                    await asyncio.sleep(3600)  # Wait 1 hour before retry
        
        self.retention_task = asyncio.create_task(retention_loop())
    
    async def stop_background_retention(self):
        """Stop background retention processing."""
        if not self.running:
            return
        
        self.running = False
        
        if self.retention_task:
            self.retention_task.cancel()
            try:
                await self.retention_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Background retention stopped")
    
    def get_retention_stats(self) -> Dict[str, Any]:
        """Get retention statistics."""
        return {
            "policies_count": len(self.policies),
            "running": self.running,
            "stats": self.stats.copy()
        }
    
    def get_database_size(self) -> Dict[str, int]:
        """Get database size information."""
        try:
            db_size = os.path.getsize(self.db_path)
            
            # Get table sizes
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name, 
                       (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=m.name) as row_count
                FROM sqlite_master m 
                WHERE type='table'
            """)
            
            tables = cursor.fetchall()
            conn.close()
            
            return {
                "total_size_bytes": db_size,
                "total_size_mb": db_size / (1024 * 1024),
                "tables": {name: count for name, count in tables}
            }
            
        except Exception as e:
            logger.error(f"Error getting database size: {e}")
            return {"error": str(e)}
    
    async def cleanup_old_archives(self, max_age_days: int = 365):
        """Clean up old archive files."""
        logger.info(f"Cleaning up archives older than {max_age_days} days")
        
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        deleted_count = 0
        
        for archive_file in self.archive_path.rglob("*.json.gz"):
            if archive_file.stat().st_mtime < cutoff_time:
                try:
                    archive_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting {archive_file}: {e}")
        
        logger.info(f"Deleted {deleted_count} old archive files")

# Default retention policies for common symbols
DEFAULT_RETENTION_POLICIES = {
    "BTCUSDc": {
        "M1": RetentionPolicy("BTCUSDc", "M1", hot_days=7, warm_days=30, cold_days=365),
        "M5": RetentionPolicy("BTCUSDc", "M5", hot_days=14, warm_days=60, cold_days=730),
        "M15": RetentionPolicy("BTCUSDc", "M15", hot_days=30, warm_days=90, cold_days=1095),
        "H1": RetentionPolicy("BTCUSDc", "H1", hot_days=60, warm_days=180, cold_days=1095),
        "H4": RetentionPolicy("BTCUSDc", "H4", hot_days=90, warm_days=365, cold_days=2190)
    },
    "XAUUSDc": {
        "M1": RetentionPolicy("XAUUSDc", "M1", hot_days=7, warm_days=30, cold_days=365),
        "M5": RetentionPolicy("XAUUSDc", "M5", hot_days=14, warm_days=60, cold_days=730),
        "M15": RetentionPolicy("XAUUSDc", "M15", hot_days=30, warm_days=90, cold_days=1095),
        "H1": RetentionPolicy("XAUUSDc", "H1", hot_days=60, warm_days=180, cold_days=1095),
        "H4": RetentionPolicy("XAUUSDc", "H4", hot_days=90, warm_days=365, cold_days=2190)
    },
    "EURUSDc": {
        "M1": RetentionPolicy("EURUSDc", "M1", hot_days=7, warm_days=30, cold_days=365),
        "M5": RetentionPolicy("EURUSDc", "M5", hot_days=14, warm_days=60, cold_days=730),
        "M15": RetentionPolicy("EURUSDc", "M15", hot_days=30, warm_days=90, cold_days=1095),
        "H1": RetentionPolicy("EURUSDc", "H1", hot_days=60, warm_days=180, cold_days=1095),
        "H4": RetentionPolicy("EURUSDc", "H4", hot_days=90, warm_days=365, cold_days=2190)
    }
}

def create_default_retention_manager(db_path: str) -> DataRetentionManager:
    """Create a retention manager with default policies."""
    manager = DataRetentionManager(db_path)
    
    # Add default policies
    for symbol, timeframes in DEFAULT_RETENTION_POLICIES.items():
        for timeframe, policy in timeframes.items():
            manager.add_retention_policy(policy)
    
    return manager
