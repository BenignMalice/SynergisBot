"""
Multi-Timeframe Candlestick Streamer for MT5
Streams M5, M15, M30, H1, H4 data efficiently with minimal RAM/SSD usage.

Features:
- Incremental fetching (only new candles)
- Rolling buffers (fixed-size, auto-expiring)
- Smart refresh rates (aligned with timeframe frequencies)
- Optional database persistence with compression
- Automatic cleanup and memory management
"""

import asyncio
import logging
import sqlite3
import time
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
import MetaTrader5 as mt5
import json

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """Single candlestick data"""
    symbol: str
    timeframe: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    spread: float
    real_volume: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'time': self.time.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'spread': self.spread,
            'real_volume': self.real_volume
        }


@dataclass
class StreamerConfig:
    """Configuration for multi-timeframe streamer"""
    # Symbols to stream
    symbols: List[str]
    
    # Buffer sizes (rolling deques maxlen)
    buffer_sizes: Dict[str, int] = None
    
    # Refresh intervals in seconds
    refresh_intervals: Dict[str, int] = None
    
    # Database storage
    enable_database: bool = False
    db_path: str = "data/multi_tf_candles.db"
    retention_days: int = 30
    
    # Safety limits
    max_memory_mb: float = 100.0  # Max total memory usage
    max_db_size_mb: float = 500.0  # Max database size
    batch_write_size: int = 20  # Write N candles at once
    
    def __post_init__(self):
        if self.buffer_sizes is None:
            self.buffer_sizes = {
                'M1': 1440,  # 1 day (24 hours)
                'M5': 300,    # ~2.5 days
                'M15': 150,   # ~2.5 days
                'M30': 100,   # ~2.5 days
                'H1': 100,    # ~4 days
                'H4': 50      # ~8 days
            }
        
        if self.refresh_intervals is None:
            self.refresh_intervals = {
                'M1': 55,     # 55 seconds (slightly faster than 1-min candle completion for freshness)
                'M5': 240,    # 4 minutes (slightly faster than 5-min candle completion for freshness)
                'M15': 840,   # 14 minutes (slightly faster than 15-min candle completion for freshness)
                'M30': 1680,  # 28 minutes (slightly faster than 30-min candle completion for freshness)
                'H1': 3480,   # 58 minutes (slightly faster than 1-hour candle completion for freshness)
                'H4': 13800   # 3 hours 50 minutes (slightly faster than 4-hour candle completion for freshness)
            }


class MultiTimeframeStreamer:
    """
    Efficiently streams candlestick data from multiple timeframes.
    
    Architecture:
    - Incremental fetching: Only fetches new candles since last update
    - Rolling buffers: Fixed-size deques that auto-expire old data
    - Smart refresh: Different intervals for each timeframe
    - Optional persistence: Database storage with compression and cleanup
    """
    
    # MT5 timeframe mapping
    TF_MAP = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4
    }
    
    def __init__(self, config: StreamerConfig, mt5_service=None):
        self.config = config
        self.mt5_service = mt5_service
        
        # Rolling buffers: symbol -> timeframe -> deque
        # Structure: buffers[symbol][timeframe] = deque(maxlen=size)
        self.buffers: Dict[str, Dict[str, deque]] = {}
        
        # Last fetch times: symbol -> timeframe -> datetime
        self.last_fetch_times: Dict[str, Dict[str, datetime]] = {}
        
        # Write queue for database (batched writes)
        self.write_queue: List[Dict[str, Any]] = []
        
        # Database connection (if enabled)
        self.db_connection: Optional[sqlite3.Connection] = None
        
        # State
        self.is_running = False
        self.tasks: List[asyncio.Task] = []
        
        # Metrics
        self.metrics = {
            'total_candles_fetched': 0,
            'total_candles_stored': 0,
            'memory_usage_mb': 0.0,
            'db_size_mb': 0.0,
            'errors': 0,
            'last_update': None
        }
        
        # Callbacks for new candles
        self.callbacks: List[Callable[[Candle], None]] = []
        
        logger.info(f"MultiTimeframeStreamer initialized for {len(config.symbols)} symbols")
    
    def add_callback(self, callback: Callable[[Candle], None]):
        """Add callback to be called when new candles arrive"""
        self.callbacks.append(callback)
    
    def initialize_buffers(self):
        """Initialize rolling buffers for all symbols and timeframes"""
        for symbol in self.config.symbols:
            symbol_norm = self._normalize_symbol(symbol)
            self.buffers[symbol_norm] = {}
            self.last_fetch_times[symbol_norm] = {}
            
            for tf, size in self.config.buffer_sizes.items():
                self.buffers[symbol_norm][tf] = deque(maxlen=size)
                # Initialize last fetch time to now (will fetch recent history on first run)
                self.last_fetch_times[symbol_norm][tf] = datetime.now(timezone.utc)
        
        logger.info(f"Initialized buffers for {len(self.config.symbols)} symbols, {len(self.config.buffer_sizes)} timeframes")
    
    async def initialize_database(self):
        """Initialize database if enabled"""
        if not self.config.enable_database:
            logger.info("Database storage disabled")
            return
        
        try:
            db_path = Path(self.config.db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.db_connection = sqlite3.connect(str(db_path), check_same_thread=False)
            self.db_connection.row_factory = sqlite3.Row
            
            # Optimize SQLite for writes
            self.db_connection.execute("PRAGMA synchronous = NORMAL")
            self.db_connection.execute("PRAGMA journal_mode = WAL")
            self.db_connection.execute("PRAGMA cache_size = -10000")  # 10MB cache
            self.db_connection.execute("PRAGMA temp_store = MEMORY")
            
            # Create table
            cursor = self.db_connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    time_utc TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    spread REAL NOT NULL,
                    real_volume INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timeframe, timestamp)
                )
            """)
            
            # Create indexes for fast queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_tf_time 
                ON candles(symbol, timeframe, timestamp DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON candles(timestamp DESC)
            """)
            
            self.db_connection.commit()
            
            # Check database size
            db_size = db_path.stat().st_size / (1024 * 1024)
            self.metrics['db_size_mb'] = db_size
            
            logger.info(f"Database initialized: {db_path} ({db_size:.2f} MB)")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            self.config.enable_database = False
    
    def _fetch_initial_history(self, symbol: str, timeframe: str) -> List[Candle]:
        """Fetch initial history to populate buffer"""
        try:
            tf_constant = self.TF_MAP.get(timeframe)
            if not tf_constant:
                return []
            
            # Fetch enough bars to fill buffer
            buffer_size = self.config.buffer_sizes.get(timeframe, 100)
            rates = mt5.copy_rates_from_pos(symbol, tf_constant, 0, buffer_size)
            
            if rates is None or len(rates) == 0:
                return []
            
            candles = []
            for rate in rates:
                # MT5 returns numpy structured arrays - access fields directly, not like dict
                candle = Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    time=datetime.fromtimestamp(rate['time'], tz=timezone.utc),
                    open=float(rate['open']),
                    high=float(rate['high']),
                    low=float(rate['low']),
                    close=float(rate['close']),
                    volume=int(rate['tick_volume']),
                    spread=float(rate['spread']),
                    real_volume=int(rate['real_volume']) if 'real_volume' in rate.dtype.names else 0
                )
                candles.append(candle)
            
            if candles:
                # Update last fetch time to most recent candle
                self.last_fetch_times[symbol][timeframe] = candles[-1].time
            
            logger.debug(f"Fetched {len(candles)} historical {timeframe} candles for {symbol}")
            return candles
            
        except Exception as e:
            logger.error(f"Error fetching initial history for {symbol} {timeframe}: {e}")
            return []
    
    def _fetch_new_candles(self, symbol: str, timeframe: str) -> List[Candle]:
        """Fetch only new candles since last fetch"""
        try:
            tf_constant = self.TF_MAP.get(timeframe)
            if not tf_constant:
                return []
            
            last_time = self.last_fetch_times.get(symbol, {}).get(timeframe)
            
            if last_time is None:
                # First fetch - get initial history
                return self._fetch_initial_history(symbol, timeframe)
            
            # CRITICAL: Force MT5 to refresh its internal data cache
            # MT5 may cache candle data, so we need to refresh before fetching
            try:
                # Select symbol to ensure it's in Market Watch
                mt5.symbol_select(symbol, True)
                # Get symbol info to force MT5 to refresh
                mt5.symbol_info(symbol)
                # Small delay to allow MT5 to refresh
                import time
                time.sleep(0.1)
            except Exception as e:
                logger.debug(f"Error refreshing MT5 symbol info for {symbol}: {e}")
            
            # Try copy_rates_from first (incremental)
            last_timestamp = int(last_time.timestamp())
            rates = mt5.copy_rates_from(symbol, tf_constant, last_timestamp, 100)
            
            # If copy_rates_from returns stale data, fallback to copy_rates_from_pos
            # to get the absolute latest candle
            if rates is not None and len(rates) > 0:
                latest_candle_time = datetime.fromtimestamp(rates[-1]['time'], tz=timezone.utc)
                # If latest candle is not newer than last_time, try copy_rates_from_pos
                if latest_candle_time <= last_time:
                    # Fallback: Get latest candle using copy_rates_from_pos
                    latest_rates = mt5.copy_rates_from_pos(symbol, tf_constant, 0, 10)
                    if latest_rates is not None and len(latest_rates) > 0:
                        # Check if we have a newer candle
                        latest_from_pos = datetime.fromtimestamp(latest_rates[-1]['time'], tz=timezone.utc)
                        if latest_from_pos > last_time:
                            # Use the latest candle from copy_rates_from_pos
                            rates = latest_rates
                            logger.debug(f"Using copy_rates_from_pos fallback for {symbol} {timeframe} (latest: {latest_from_pos})")
            
            if rates is None or len(rates) == 0:
                return []
            
            # Filter out candles we already have (by timestamp)
            new_candles = []
            for rate in rates:
                candle_time = datetime.fromtimestamp(rate['time'], tz=timezone.utc)
                
                # Only include if newer than last fetch
                if candle_time > last_time:
                    # MT5 returns numpy structured arrays - access fields directly
                    candle = Candle(
                        symbol=symbol,
                        timeframe=timeframe,
                        time=candle_time,
                        open=float(rate['open']),
                        high=float(rate['high']),
                        low=float(rate['low']),
                        close=float(rate['close']),
                        volume=int(rate['tick_volume']),
                        spread=float(rate['spread']),
                        real_volume=int(rate['real_volume']) if 'real_volume' in rate.dtype.names else 0
                    )
                    new_candles.append(candle)
            
            # Update last fetch time if we got new candles
            if new_candles:
                self.last_fetch_times[symbol][timeframe] = new_candles[-1].time
                logger.debug(f"Fetched {len(new_candles)} new {timeframe} candles for {symbol} (latest: {new_candles[-1].time})")
            else:
                # Log when no new candles found (for debugging)
                if rates is not None and len(rates) > 0:
                    latest_rate_time = datetime.fromtimestamp(rates[-1]['time'], tz=timezone.utc)
                    logger.debug(f"No new {timeframe} candles for {symbol} (latest available: {latest_rate_time}, last fetch: {last_time})")
            
            return new_candles
            
        except Exception as e:
            logger.error(f"Error fetching new candles for {symbol} {timeframe}: {e}")
            self.metrics['errors'] += 1
            return []
    
    def _add_to_buffer(self, symbol: str, timeframe: str, candles: List[Candle]):
        """Add candles to rolling buffer"""
        if symbol not in self.buffers or timeframe not in self.buffers[symbol]:
            return
        
        buffer = self.buffers[symbol][timeframe]
        
        for candle in candles:
            # Check if candle already exists (avoid duplicates)
            if len(buffer) > 0 and buffer[-1].time >= candle.time:
                # Skip duplicate or older candle
                continue
            
            buffer.append(candle)
            self.metrics['total_candles_fetched'] += 1
            
            # Call callbacks
            for callback in self.callbacks:
                try:
                    callback(candle)
                except Exception as e:
                    logger.error(f"Error in callback: {e}")
    
    async def _stream_timeframe(self, symbol: str, timeframe: str):
        """Stream candles for a specific symbol/timeframe (incremental fetching only)"""
        refresh_interval = self.config.refresh_intervals.get(timeframe, 300)
        symbol_norm = self._normalize_symbol(symbol)
        
        # Note: Initial fetch is done in start() method before tasks are created
        # This task only does incremental fetching at intervals
        
        logger.info(f"Started incremental streaming {symbol_norm} {timeframe} (refresh: {refresh_interval}s)")
        
        consecutive_stale_count = 0  # Track consecutive stale fetches
        
        while self.is_running:
            try:
                # Wait for refresh interval
                await asyncio.sleep(refresh_interval)
                
                if not self.is_running:
                    break
                
                # Fetch new candles
                new_candles = self._fetch_new_candles(symbol_norm, timeframe)
                
                if new_candles:
                    self._add_to_buffer(symbol_norm, timeframe, new_candles)
                    
                    # Queue for database write if enabled
                    if self.config.enable_database:
                        for candle in new_candles:
                            self.write_queue.append(candle.to_dict())
                    
                    logger.debug(f"Fetched {len(new_candles)} new {timeframe} candles for {symbol_norm}")
                    consecutive_stale_count = 0  # Reset stale counter
                else:
                    # No new candles - check if this is a problem
                    consecutive_stale_count += 1
                    
                    # Get latest candle to check age
                    latest_candle = self.get_latest_candle(symbol_norm, timeframe)
                    if latest_candle:
                        age_seconds = (datetime.now(timezone.utc) - latest_candle.time).total_seconds()
                        age_minutes = age_seconds / 60
                        
                        # Warn if candles are getting stale
                        if age_minutes > 10 and consecutive_stale_count >= 3:
                            logger.warning(
                                f"⚠️ {symbol_norm} {timeframe}: No new candles for {consecutive_stale_count} fetches. "
                                f"Latest candle age: {age_minutes:.1f} min. "
                                f"MT5 may not be forming new candles (market closed/low volume?)"
                            )
                            # Reset counter to avoid spam
                            consecutive_stale_count = 0
                
            except Exception as e:
                logger.error(f"Error in {timeframe} stream for {symbol_norm}: {e}")
                self.metrics['errors'] += 1
                await asyncio.sleep(60)  # Wait before retry
    
    async def _database_writer(self):
        """Background task to batch-write candles to database"""
        if not self.config.enable_database or not self.db_connection:
            return
        
        # Track last flush time for time-based flushing
        last_flush_time = datetime.now(timezone.utc)
        flush_interval = 30  # Flush every 30 seconds to keep database current
        
        while self.is_running:
            try:
                await asyncio.sleep(5)  # Check queue every 5 seconds
                
                now = datetime.now(timezone.utc)
                should_flush_by_time = (now - last_flush_time).total_seconds() >= flush_interval
                should_flush_by_size = len(self.write_queue) >= self.config.batch_write_size
                
                if should_flush_by_size or (should_flush_by_time and len(self.write_queue) > 0):
                    # Write either a full batch or all pending candles (time-based flush)
                    if should_flush_by_size:
                        # Full batch write
                        batch = self.write_queue[:self.config.batch_write_size]
                        self.write_queue = self.write_queue[self.config.batch_write_size:]
                    else:
                        # Time-based flush: write all pending candles
                        batch = self.write_queue[:]
                        self.write_queue = []
                    
                    if batch:
                        await self._write_batch_to_db(batch)
                        last_flush_time = now
                        logger.debug(f"Flushed {len(batch)} candles to database ({'batch' if should_flush_by_size else 'time-based'})")
                    
            except Exception as e:
                logger.error(f"Error in database writer: {e}")
                await asyncio.sleep(10)
    
    async def _write_batch_to_db(self, batch: List[Dict[str, Any]]):
        """Write a batch of candles to database"""
        if not self.db_connection:
            return
        
        try:
            cursor = self.db_connection.cursor()
            
            for candle_dict in batch:
                timestamp = int(datetime.fromisoformat(candle_dict['time']).timestamp())
                
                cursor.execute("""
                    INSERT OR IGNORE INTO candles 
                    (symbol, timeframe, timestamp, time_utc, open, high, low, close, volume, spread, real_volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    candle_dict['symbol'],
                    candle_dict['timeframe'],
                    timestamp,
                    candle_dict['time'],
                    candle_dict['open'],
                    candle_dict['high'],
                    candle_dict['low'],
                    candle_dict['close'],
                    candle_dict['volume'],
                    candle_dict['spread'],
                    candle_dict.get('real_volume', 0)
                ))
            
            self.db_connection.commit()
            self.metrics['total_candles_stored'] += len(batch)
            
            logger.debug(f"Wrote {len(batch)} candles to database")
            
        except Exception as e:
            logger.error(f"Error writing batch to database: {e}")
            self.metrics['errors'] += 1
    
    async def _cleanup_loop(self):
        """Background task to clean up old database records"""
        if not self.config.enable_database:
            return
        
        try:
            while self.is_running:
                try:
                    await asyncio.sleep(3600)  # Check every hour
                    
                    await self._cleanup_old_data()
                    
                except Exception as e:
                    logger.error(f"Error in cleanup loop: {e}", exc_info=True)
        except Exception as fatal_error:
            logger.critical(f"FATAL ERROR in cleanup loop: {fatal_error}", exc_info=True)
            self.is_running = False
        finally:
            logger.info("Cleanup loop stopped")
    
    async def _cleanup_old_data(self):
        """Clean up old database records"""
        if not self.db_connection:
            return
        
        try:
            cutoff_timestamp = int((datetime.now(timezone.utc) - timedelta(days=self.config.retention_days)).timestamp())
            
            cursor = self.db_connection.cursor()
            cursor.execute("DELETE FROM candles WHERE timestamp < ?", (cutoff_timestamp,))
            deleted = cursor.rowcount
            
            self.db_connection.commit()
            
            if deleted > 0:
                # Vacuum to reclaim space
                self.db_connection.execute("VACUUM")
                self.db_connection.commit()
                
                # Update size metric
                db_path = Path(self.config.db_path)
                if db_path.exists():
                    self.metrics['db_size_mb'] = db_path.stat().st_size / (1024 * 1024)
                
                logger.info(f"Cleaned up {deleted} old candle records")
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    async def _monitoring_loop(self):
        """Background task to monitor memory and database size"""
        try:
            while self.is_running:
                try:
                    await asyncio.sleep(300)  # Check every 5 minutes
                    
                    # Calculate memory usage
                    total_candles = sum(
                        len(buffer) 
                        for symbol_buffers in self.buffers.values()
                        for buffer in symbol_buffers.values()
                    )
                    
                    # Estimate: ~100 bytes per candle
                    memory_bytes = total_candles * 100
                    self.metrics['memory_usage_mb'] = memory_bytes / (1024 * 1024)
                    
                    # Check database size
                    if self.config.enable_database:
                        db_path = Path(self.config.db_path)
                        if db_path.exists():
                            db_size_mb = db_path.stat().st_size / (1024 * 1024)
                            self.metrics['db_size_mb'] = db_size_mb
                            
                            # Warn if approaching limit
                            if db_size_mb > self.config.max_db_size_mb * 0.8:
                                logger.warning(f"Database size ({db_size_mb:.2f} MB) approaching limit ({self.config.max_db_size_mb} MB)")
                    
                    # Warn if memory usage high
                    if self.metrics['memory_usage_mb'] > self.config.max_memory_mb * 0.8:
                        logger.warning(f"Memory usage ({self.metrics['memory_usage_mb']:.2f} MB) approaching limit ({self.config.max_memory_mb} MB)")
                    
                    self.metrics['last_update'] = datetime.now(timezone.utc).isoformat()
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop iteration: {e}", exc_info=True)
        except Exception as fatal_error:
            logger.critical(f"FATAL ERROR in monitoring loop: {fatal_error}", exc_info=True)
            self.is_running = False
        finally:
            logger.info("Monitoring loop stopped")
    
    def get_candles(self, symbol: str, timeframe: str, limit: Optional[int] = None) -> List[Candle]:
        """Get candles from buffer (returns newest first for consistency)"""
        symbol_norm = self._normalize_symbol(symbol)
        
        if symbol_norm not in self.buffers:
            return []
        
        if timeframe not in self.buffers[symbol_norm]:
            return []
        
        buffer = self.buffers[symbol_norm][timeframe]
        candles = list(buffer)  # deque iteration: oldest first
        
        # Always return newest first for consistency
        candles.reverse()  # Now newest first
        
        if limit:
            candles = candles[:limit]  # Take first N (newest N)
        
        return candles
    
    def get_latest_candle(self, symbol: str, timeframe: str) -> Optional[Candle]:
        """Get the latest candle for a symbol/timeframe"""
        candles = self.get_candles(symbol, timeframe, limit=1)
        return candles[0] if candles else None
    
    async def start(self):
        """Start streaming all timeframes for all symbols"""
        if self.is_running:
            logger.warning("Streamer already running")
            return
        
        logger.info("Starting multi-timeframe streamer...")
        
        # Initialize MT5 connection
        if self.mt5_service:
            if not self.mt5_service.connect():
                logger.error("Failed to connect to MT5")
                return False
        elif not mt5.initialize():
            logger.error("Failed to initialize MT5")
            return False
        
        # Initialize buffers
        self.initialize_buffers()
        
        # Initialize database if enabled
        if self.config.enable_database:
            await self.initialize_database()
        
        # IMPORTANT: Fetch initial data for ALL symbol/timeframe combinations immediately
        # This ensures buffers are populated before background tasks start
        logger.info("Fetching initial historical data for all symbols and timeframes...")
        initial_fetch_count = 0
        total_combinations = len(self.config.symbols) * len(self.config.buffer_sizes)
        
        for symbol in self.config.symbols:
            # Normalize symbol: uppercase everything except keep 'c' suffix lowercase
            symbol_norm = self._normalize_symbol(symbol)
            
            # Ensure symbol is available in MT5
            if not mt5.symbol_select(symbol_norm, True):
                logger.warning(f"Symbol {symbol_norm} not available in MT5, skipping...")
                continue
            
            for timeframe in self.config.buffer_sizes.keys():
                try:
                    # Fetch initial history immediately
                    initial_candles = self._fetch_initial_history(symbol_norm, timeframe)
                    
                    if initial_candles:
                        # Add to buffer immediately
                        self._add_to_buffer(symbol_norm, timeframe, initial_candles)
                        
                        # Queue for database if enabled
                        if self.config.enable_database:
                            for candle in initial_candles:
                                self.write_queue.append(candle.to_dict())
                        
                        initial_fetch_count += 1
                        logger.info(f"  ✓ {symbol_norm} {timeframe}: {len(initial_candles)} candles")
                    else:
                        logger.warning(f"  ✗ {symbol_norm} {timeframe}: No data fetched")
                        
                except Exception as e:
                    logger.error(f"  ✗ Error fetching {symbol_norm} {timeframe}: {e}")
                    self.metrics['errors'] += 1
        
        logger.info(f"Initial fetch complete: {initial_fetch_count}/{total_combinations} combinations populated")
        
        self.is_running = True
        
        # Now start streaming tasks for each symbol/timeframe combination
        # These will continue with incremental fetching at intervals
        for symbol in self.config.symbols:
            for timeframe in self.config.buffer_sizes.keys():
                task = asyncio.create_task(self._stream_timeframe(symbol, timeframe))
                self.tasks.append(task)
        
        # Start background tasks
        if self.config.enable_database:
            write_task = asyncio.create_task(self._database_writer())
            self.tasks.append(write_task)
            
            cleanup_task = asyncio.create_task(self._cleanup_loop())
            self.tasks.append(cleanup_task)
        
        monitor_task = asyncio.create_task(self._monitoring_loop())
        self.tasks.append(monitor_task)
        
        logger.info(f"Multi-timeframe streamer started: {len(self.config.symbols)} symbols × {len(self.config.buffer_sizes)} timeframes")
        logger.info(f"Buffers populated with initial data - endpoints are ready to use")
        return True
    
    async def stop(self):
        """Stop streaming and cleanup"""
        if not self.is_running:
            return
        
        logger.info("Stopping multi-timeframe streamer...")
        
        self.is_running = False
        
        # Wait for tasks to complete
        for task in self.tasks:
            task.cancel()
        
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Flush write queue
        if self.config.enable_database and self.write_queue:
            await self._write_batch_to_db(self.write_queue)
            self.write_queue = []
        
        # Close database connection
        if self.db_connection:
            self.db_connection.close()
            self.db_connection = None
        
        logger.info("Multi-timeframe streamer stopped")
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol: uppercase everything except keep 'c' suffix lowercase"""
        # Handle both cases: symbol already has 'c' or 'C', or doesn't have it
        symbol = symbol.strip()
        
        # If it ends with 'c' or 'C', preserve the lowercase 'c'
        if symbol.upper().endswith('C'):
            # Extract base symbol and ensure 'c' is lowercase
            base = symbol[:-1].upper()  # Everything except last char, uppercase
            return base + 'c'  # Add lowercase 'c'
        else:
            # No 'c' suffix, add it
            return symbol.upper() + 'c'
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return {
            **self.metrics,
            'symbols': len(self.config.symbols),
            'timeframes': list(self.config.buffer_sizes.keys()),
            'total_buffers': sum(len(buffers) for buffers in self.buffers.values()),
            'queued_writes': len(self.write_queue),
            'is_running': self.is_running
        }


# Example usage
async def example_usage():
    """Example of how to use the streamer"""
    
    config = StreamerConfig(
        symbols=['BTCUSDc', 'XAUUSDc', 'EURUSDc'],
        enable_database=True,  # Set to False for RAM-only mode
        retention_days=30
    )
    
    streamer = MultiTimeframeStreamer(config)
    
    # Add callback for new candles
    def on_new_candle(candle: Candle):
        print(f"New {candle.timeframe} candle: {candle.symbol} @ {candle.close}")
    
    streamer.add_callback(on_new_candle)
    
    # Start streaming
    await streamer.start()
    
    # Wait and check data
    await asyncio.sleep(60)
    
    # Get latest M5 candle for BTCUSD
    latest = streamer.get_latest_candle('BTCUSDc', 'M5')
    if latest:
        print(f"Latest BTCUSD M5: {latest.close}")
    
    # Get last 50 H1 candles
    candles = streamer.get_candles('XAUUSDc', 'H1', limit=50)
    print(f"Got {len(candles)} H1 candles")
    
    # Get metrics
    metrics = streamer.get_metrics()
    print(f"Memory usage: {metrics['memory_usage_mb']:.2f} MB")
    print(f"Database size: {metrics['db_size_mb']:.2f} MB")
    
    # Stop when done
    await streamer.stop()


if __name__ == "__main__":
    asyncio.run(example_usage())

