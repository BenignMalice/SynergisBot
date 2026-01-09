"""
Data Retention System
Multi-layer storage with memory management and compression
"""

import asyncio
import logging
import sqlite3
import json
import gzip
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
# Note: pandas and numpy imports removed as not currently used
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class RetentionConfig:
    """Data retention configuration"""
    tick_buffer_size: int
    compression_threshold: int
    retention_hours: int
    archive_format: str
    enable_database_storage: bool = True  # Set to False to disable tick data saving to database

class DataRetentionSystem:
    """
    Multi-layer data retention system
    
    Features:
    - In-memory tick buffers
    - SQLite short-term storage
    - Compressed long-term archive
    - Memory spike control
    - Automatic compression
    """
    
    def __init__(self, config: Dict[str, Any]):
        # Ensure enable_database_storage has a default value if not provided
        if 'enable_database_storage' not in config:
            config['enable_database_storage'] = False  # Default to disabled
        self.config = RetentionConfig(**config)
        self.is_active = False
        
        # Storage paths
        self.data_dir = Path("data/unified_tick_pipeline")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Database connection
        self.db_path = self.data_dir / "tick_data.db"
        self.db_connection: Optional[sqlite3.Connection] = None
        
        # In-memory buffers
        self.tick_buffers: Dict[str, List[Dict]] = {}
        self.compression_queue: List[Dict] = []
        
        # Performance metrics
        self.performance_metrics = {
            'ticks_stored': 0,
            'compressions_performed': 0,
            'memory_usage_mb': 0,
            'last_compression': None,
            'error_count': 0,
            'spike_events': 0,
            'auto_compressions': 0,
            'memory_cleanups': 0
        }
        
        # Spike controller
        self.spike_threshold = 1000  # Ticks per second threshold
        self.spike_window = 60  # Seconds to monitor for spikes
        self.recent_tick_counts: List[Tuple[datetime, int]] = []
        self.is_spike_active = False
        
        # Background tasks
        self.tasks: List[asyncio.Task] = []
        
        logger.info("DataRetentionSystem initialized")
    
    async def initialize(self):
        """Initialize data retention system"""
        try:
            logger.info("🔧 Initializing data retention system...")
            
            # Initialize database only if storage is enabled
            if self.config.enable_database_storage:
                await self._initialize_database()
                logger.info("✅ Database storage enabled for tick data")
            else:
                logger.info("ℹ️ Database storage disabled for tick data (in-memory buffers only)")
            
            # Start background tasks only if storage is enabled
            if self.config.enable_database_storage:
                await self._start_background_tasks()
            
            self.is_active = True
            logger.info("✅ Data retention system initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize data retention system: {e}")
            raise
    
    async def _initialize_database(self):
        """Initialize SQLite database"""
        try:
            self.db_connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.db_connection.row_factory = sqlite3.Row
            
            # Create tables
            await self._create_tables()
            
            logger.info("✅ Database initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise
    
    async def _create_tables(self):
        """Create database tables"""
        try:
            cursor = self.db_connection.cursor()
            
            # Unified ticks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS unified_ticks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp_utc DATETIME NOT NULL,
                    bid REAL NOT NULL,
                    ask REAL NOT NULL,
                    mid REAL NOT NULL,
                    volume REAL,
                    source TEXT NOT NULL,
                    offset_applied REAL DEFAULT 0.0,
                    raw_data TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index separately
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_timestamp 
                ON unified_ticks (symbol, timestamp_utc)
            """)
            
            # M5 candles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS m5_candles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp_utc DATETIME NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL,
                    atr_14 REAL,
                    vwap REAL,
                    volatility_state TEXT,
                    structure TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for M5 candles
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_m5_symbol_timestamp 
                ON m5_candles (symbol, timestamp_utc)
            """)
            
            # DTMS actions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dtms_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    timestamp_utc DATETIME NOT NULL,
                    reason TEXT,
                    parameters TEXT,
                    result TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for DTMS actions
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_dtms_ticket_timestamp 
                ON dtms_actions (ticket, timestamp_utc)
            """)
            
            # ChatGPT analysis history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chatgpt_analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp_utc DATETIME NOT NULL,
                    analysis_type TEXT NOT NULL,
                    timeframe_data TEXT,
                    analysis_result TEXT,
                    recommendations TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for ChatGPT analysis
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chatgpt_symbol_timestamp 
                ON chatgpt_analysis_history (symbol, timestamp_utc)
            """)
            
            self.db_connection.commit()
            logger.info("✅ Database tables created")
            
        except Exception as e:
            logger.error(f"❌ Failed to create database tables: {e}")
            raise
    
    async def _start_background_tasks(self):
        """Start background tasks"""
        try:
            # Compression task
            compression_task = asyncio.create_task(self._compression_loop())
            self.tasks.append(compression_task)
            
            # Memory monitoring task
            memory_task = asyncio.create_task(self._memory_monitoring_loop())
            self.tasks.append(memory_task)
            
            # Cleanup task
            cleanup_task = asyncio.create_task(self._cleanup_loop())
            self.tasks.append(cleanup_task)
            
            logger.info("✅ Background tasks started")
            
        except Exception as e:
            logger.error(f"❌ Failed to start background tasks: {e}")
            raise
    
    async def stop(self):
        """Stop data retention system"""
        try:
            logger.info("🛑 Stopping data retention system...")
            
            self.is_active = False
            
            # Cancel background tasks
            for task in self.tasks:
                task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(*self.tasks, return_exceptions=True)
            
            # Close database connection
            if self.db_connection:
                self.db_connection.close()
            
            logger.info("✅ Data retention system stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping data retention system: {e}")
    
    async def store_tick(self, tick_data: Dict):
        """Store tick data in retention system with spike control"""
        try:
            # Check for spike conditions
            await self._check_spike_conditions()
            
            # Add to in-memory buffer
            symbol = tick_data.get('symbol', 'UNKNOWN')
            if symbol not in self.tick_buffers:
                self.tick_buffers[symbol] = []
            
            self.tick_buffers[symbol].append(tick_data)
            
            # Maintain buffer size
            if len(self.tick_buffers[symbol]) > self.config.tick_buffer_size:
                self.tick_buffers[symbol] = self.tick_buffers[symbol][-self.config.tick_buffer_size:]
            
            # Store in database only if enabled
            if self.config.enable_database_storage:
                await self._store_tick_in_db(tick_data)
            # Note: Metrics still updated for in-memory buffer operations
            
            # Update metrics
            self.performance_metrics['ticks_stored'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error storing tick data: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _store_tick_in_db(self, tick_data: Dict):
        """Store tick data in database"""
        try:
            cursor = self.db_connection.cursor()
            
            cursor.execute("""
                INSERT INTO unified_ticks 
                (symbol, timestamp_utc, bid, ask, mid, volume, source, offset_applied, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tick_data.get('symbol'),
                tick_data.get('timestamp_utc').isoformat() if tick_data.get('timestamp_utc') else None,
                tick_data.get('bid'),
                tick_data.get('ask'),
                tick_data.get('mid'),
                tick_data.get('volume'),
                tick_data.get('source'),
                tick_data.get('offset_applied', 0.0),
                json.dumps(tick_data.get('raw_data', {}))
            ))
            
            self.db_connection.commit()
            
        except Exception as e:
            logger.error(f"❌ Error storing tick in database: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def get_tick_data(self, symbol: str, hours_back: int = 4) -> List[Dict]:
        """Get tick data from retention system"""
        try:
            # First try in-memory buffer
            if symbol in self.tick_buffers and self.tick_buffers[symbol]:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
                recent_ticks = [
                    tick for tick in self.tick_buffers[symbol]
                    if datetime.fromisoformat(tick.get('timestamp', '').replace('Z', '+00:00')) >= cutoff_time
                ]
                
                if recent_ticks:
                    return recent_ticks
            
            # Fallback to database only if storage is enabled
            if self.config.enable_database_storage:
                return await self._get_tick_data_from_db(symbol, hours_back)
            else:
                # Only return in-memory buffer data
                return []
            
        except Exception as e:
            logger.error(f"❌ Error getting tick data: {e}")
            return []
    
    async def _get_tick_data_from_db(self, symbol: str, hours_back: int) -> List[Dict]:
        """Get tick data from database"""
        try:
            cursor = self.db_connection.cursor()
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            
            cursor.execute("""
                SELECT * FROM unified_ticks 
                WHERE symbol = ? AND timestamp_utc >= ?
                ORDER BY timestamp_utc DESC
                LIMIT 10000
            """, (symbol, cutoff_time.isoformat()))
            
            rows = cursor.fetchall()
            
            return [
                {
                    'symbol': row['symbol'],
                    'timestamp': row['timestamp_utc'],
                    'bid': row['bid'],
                    'ask': row['ask'],
                    'mid': row['mid'],
                    'volume': row['volume'],
                    'source': row['source'],
                    'offset_applied': row['offset_applied'],
                    'raw_data': json.loads(row['raw_data']) if row['raw_data'] else {}
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"❌ Error getting tick data from database: {e}")
            return []
    
    async def get_aggregated_data(self, symbol: str, timeframe: str, hours_back: int) -> List[Dict]:
        """Get aggregated data for timeframe"""
        try:
            # Calculate timeframe in minutes
            timeframe_minutes = {
                'M1': 1,
                'M5': 5,
                'M15': 15,
                'H1': 60,
                'H4': 240
            }.get(timeframe, 5)
            
            # Get raw tick data
            tick_data = await self.get_tick_data(symbol, hours_back)
            
            if not tick_data:
                return []
            
            # Aggregate into candles
            candles = await self._aggregate_ticks_to_candles(tick_data, timeframe_minutes)
            
            return candles
            
        except Exception as e:
            logger.error(f"❌ Error getting aggregated data: {e}")
            return []
    
    async def _aggregate_ticks_to_candles(self, tick_data: List[Dict], timeframe_minutes: int) -> List[Dict]:
        """Aggregate tick data into candles"""
        try:
            if not tick_data:
                return []
            
            # Sort by timestamp
            tick_data.sort(key=lambda x: x.get('timestamp', ''))
            
            candles = []
            current_candle = None
            candle_start_time = None
            
            for tick in tick_data:
                tick_time = datetime.fromisoformat(tick.get('timestamp', '').replace('Z', '+00:00'))
                
                # Calculate candle start time
                minutes_since_epoch = int(tick_time.timestamp() // 60)
                candle_minutes = (minutes_since_epoch // timeframe_minutes) * timeframe_minutes
                candle_start = datetime.fromtimestamp(candle_minutes * 60, tz=timezone.utc)
                
                # Check if we need a new candle
                if current_candle is None or candle_start != candle_start_time:
                    # Save previous candle
                    if current_candle is not None:
                        candles.append(current_candle)
                    
                    # Start new candle
                    current_candle = {
                        'timestamp': candle_start.isoformat(),
                        'open': tick.get('mid', 0),
                        'high': tick.get('mid', 0),
                        'low': tick.get('mid', 0),
                        'close': tick.get('mid', 0),
                        'volume': tick.get('volume', 0)
                    }
                    candle_start_time = candle_start
                else:
                    # Update current candle
                    current_candle['high'] = max(current_candle['high'], tick.get('mid', 0))
                    current_candle['low'] = min(current_candle['low'], tick.get('mid', 0))
                    current_candle['close'] = tick.get('mid', 0)
                    current_candle['volume'] += tick.get('volume', 0)
            
            # Add final candle
            if current_candle is not None:
                candles.append(current_candle)
            
            return candles
            
        except Exception as e:
            logger.error(f"❌ Error aggregating ticks to candles: {e}")
            return []
    
    async def _compression_loop(self):
        """Background compression loop"""
        while self.is_active:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                # Check if compression is needed
                total_ticks = sum(len(buffer) for buffer in self.tick_buffers.values())
                
                if total_ticks > self.config.compression_threshold:
                    await self._perform_compression()
                
            except Exception as e:
                logger.error(f"❌ Error in compression loop: {e}")
                await asyncio.sleep(60)
    
    async def _perform_compression(self):
        """Perform data compression"""
        try:
            # Check if database storage is disabled - skip compression if so
            if not self.config.enable_database_storage:
                return  # No compression needed when database storage is disabled
            
            # Check if there's any data to compress
            total_ticks = sum(len(buffer) for buffer in self.tick_buffers.values())
            if total_ticks == 0:
                return  # No data to compress, skip logging
            
            logger.info("🗜️ Performing data compression...")
            
            # Compress old data
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.config.retention_hours)
            compressed_count = 0
            
            for symbol in self.tick_buffers:
                # Get old data
                old_ticks = [
                    tick for tick in self.tick_buffers[symbol]
                    if tick.get('timestamp') and datetime.fromisoformat(tick.get('timestamp', '').replace('Z', '+00:00')) < cutoff_time
                ]
                
                if old_ticks:
                    # Compress and archive
                    await self._archive_data(symbol, old_ticks)
                    compressed_count += len(old_ticks)
                    
                    # Remove from buffer
                    self.tick_buffers[symbol] = [
                        tick for tick in self.tick_buffers[symbol]
                        if tick.get('timestamp') and datetime.fromisoformat(tick.get('timestamp', '').replace('Z', '+00:00')) >= cutoff_time
                    ]
            
            self.performance_metrics['compressions_performed'] += 1
            self.performance_metrics['last_compression'] = datetime.now(timezone.utc)
            
            if compressed_count > 0:
                logger.info(f"✅ Data compression completed: {compressed_count} ticks compressed")
            else:
                logger.debug("✅ Data compression completed: no old data to compress")
            
        except Exception as e:
            logger.error(f"❌ Error performing compression: {e}")
    
    async def _archive_data(self, symbol: str, data: List[Dict]):
        """Archive data to compressed file"""
        try:
            # Create archive directory
            archive_dir = self.data_dir / "archive"
            archive_dir.mkdir(exist_ok=True)
            
            # Create filename with timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"{symbol}_{timestamp}.json.gz"
            filepath = archive_dir / filename
            
            # Compress and save
            with gzip.open(filepath, 'wt') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"📦 Archived {len(data)} ticks for {symbol} to {filename}")
            
        except Exception as e:
            logger.error(f"❌ Error archiving data: {e}")
    
    async def _memory_monitoring_loop(self):
        """Background memory monitoring loop"""
        while self.is_active:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Calculate memory usage
                total_ticks = sum(len(buffer) for buffer in self.tick_buffers.values())
                memory_usage_mb = total_ticks * 0.001  # Rough estimate
                
                self.performance_metrics['memory_usage_mb'] = memory_usage_mb
                
                # Log memory usage
                if memory_usage_mb > 100:  # More than 100MB
                    logger.warning(f"⚠️ High memory usage: {memory_usage_mb:.1f}MB")
                
            except Exception as e:
                logger.error(f"❌ Error in memory monitoring: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_loop(self):
        """Background cleanup loop"""
        while self.is_active:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                # Clean up old database records
                await self._cleanup_old_records()
                
            except Exception as e:
                logger.error(f"❌ Error in cleanup loop: {e}")
                await asyncio.sleep(3600)
    
    async def _cleanup_old_records(self):
        """Clean up old database records"""
        try:
            cursor = self.db_connection.cursor()
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)
            
            # Clean up old ticks
            cursor.execute("""
                DELETE FROM unified_ticks 
                WHERE timestamp_utc < ?
            """, (cutoff_time.isoformat(),))
            
            deleted_count = cursor.rowcount
            self.db_connection.commit()
            
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old records")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up old records: {e}")
    
    async def process_retention(self):
        """Process data retention (called by pipeline)"""
        try:
            # Skip if database storage is disabled
            if not self.config.enable_database_storage:
                return
            
            # This method is called by the pipeline to trigger retention processing
            await self._perform_compression()
            
        except Exception as e:
            logger.error(f"❌ Error processing retention: {e}")
    
    async def _check_spike_conditions(self):
        """Check for spike conditions and trigger automatic compression"""
        try:
            current_time = datetime.now(timezone.utc)
            
            # Add current tick count
            self.recent_tick_counts.append((current_time, 1))
            
            # Remove old entries (older than spike window)
            cutoff_time = current_time - timedelta(seconds=self.spike_window)
            self.recent_tick_counts = [
                (timestamp, count) for timestamp, count in self.recent_tick_counts
                if timestamp >= cutoff_time
            ]
            
            # Calculate ticks per second
            if len(self.recent_tick_counts) > 0:
                total_ticks = sum(count for _, count in self.recent_tick_counts)
                ticks_per_second = total_ticks / self.spike_window
                
                # Check if spike is active
                if ticks_per_second > self.spike_threshold:
                    if not self.is_spike_active:
                        logger.warning(f"🚨 Spike detected: {ticks_per_second:.1f} ticks/sec (threshold: {self.spike_threshold})")
                        self.is_spike_active = True
                        self.performance_metrics['spike_events'] += 1
                    
                    # Trigger automatic compression
                    await self._trigger_spike_compression()
                else:
                    if self.is_spike_active:
                        logger.info(f"✅ Spike ended: {ticks_per_second:.1f} ticks/sec")
                        self.is_spike_active = False
                        
        except Exception as e:
            logger.error(f"❌ Error checking spike conditions: {e}")
    
    async def _trigger_spike_compression(self):
        """Trigger compression during spike conditions"""
        try:
            logger.info("🔄 Triggering spike compression...")
            
            # Compress all buffers
            for symbol in self.tick_buffers.keys():
                await self._compress_buffer(symbol)
            
            # Clean up memory
            await self._cleanup_memory()
            
            self.performance_metrics['auto_compressions'] += 1
            self.performance_metrics['last_compression'] = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"❌ Error triggering spike compression: {e}")
    
    async def _cleanup_memory(self):
        """Clean up memory during spike conditions"""
        try:
            # Reduce buffer sizes by 50% during spikes
            for symbol in self.tick_buffers.keys():
                if len(self.tick_buffers[symbol]) > 100:
                    # Keep only the most recent 50% of ticks
                    keep_count = len(self.tick_buffers[symbol]) // 2
                    self.tick_buffers[symbol] = self.tick_buffers[symbol][-keep_count:]
            
            # Clear compression queue if it's too large
            if len(self.compression_queue) > 1000:
                self.compression_queue = self.compression_queue[-500:]
            
            self.performance_metrics['memory_cleanups'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up memory: {e}")
    
    def is_active(self) -> bool:
        """Check if retention system is active"""
        return self.is_active
    
    def get_status(self) -> Dict[str, Any]:
        """Get retention system status"""
        return {
            'is_active': self.is_active,
            'buffer_sizes': {symbol: len(buffer) for symbol, buffer in self.tick_buffers.items()},
            'performance_metrics': self.performance_metrics,
            'database_path': str(self.db_path),
            'data_directory': str(self.data_dir)
        }
