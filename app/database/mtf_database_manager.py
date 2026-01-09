"""
Multi-Timeframe Database Manager
Advanced database management for multi-timeframe trading data
"""

import sqlite3
import asyncio
import aiosqlite
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import numpy as np
from dataclasses import dataclass
import threading
from queue import Queue, Empty

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Database configuration"""
    db_path: str = "data/mtf_trading_data.db"
    max_connections: int = 10
    connection_timeout: int = 30
    batch_size: int = 100
    flush_interval: float = 1.0
    enable_wal: bool = True
    enable_optimization: bool = True

class MTFDatabaseManager:
    """Multi-timeframe database manager with async operations"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection_pool = []
        self.pool_lock = threading.Lock()
        self.write_queue = Queue()
        self.running = False
        self.worker_task = None
        
        # Performance tracking
        self.write_count = 0
        self.read_count = 0
        self.error_count = 0
        
        # Initialize database
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database with optimized settings"""
        try:
            conn = sqlite3.connect(self.config.db_path)
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrency
            if self.config.enable_wal:
                cursor.execute("PRAGMA journal_mode=WAL")
            
            # Optimize SQLite settings
            if self.config.enable_optimization:
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA cache_size=100000")
                cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
            
            # Create tables if they don't exist
            self._create_tables(cursor)
            
            # Create indexes for performance
            self._create_indexes(cursor)
            
            conn.commit()
            conn.close()
            
            logger.info(f"Database initialized at {self.config.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def _create_tables(self, cursor):
        """Create database tables"""
        # Raw ticks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                bid REAL NOT NULL,
                ask REAL NOT NULL,
                last REAL,
                volume REAL,
                source TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(symbol, timestamp_ms, source)
            )
        """)
        
        # OHLCV bars table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_bars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp_open_ms INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL,
                tick_volume INTEGER,
                spread REAL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(symbol, timeframe, timestamp_open_ms)
            )
        """)
        
        # Market structure table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_structure (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                type TEXT NOT NULL,
                price_level REAL NOT NULL,
                direction TEXT,
                details TEXT,
                confidence REAL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(symbol, timeframe, timestamp_ms, type)
            )
        """)
        
        # M1 filter signals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS m1_filter_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                filter_type TEXT NOT NULL,
                signal_value REAL,
                is_confirmed BOOLEAN NOT NULL,
                vwap REAL,
                atr REAL,
                delta REAL,
                volume_delta REAL,
                details TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(symbol, timestamp_ms, filter_type)
            )
        """)
        
        # Trade decisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                decision_type TEXT NOT NULL,
                direction TEXT,
                price REAL,
                volume REAL,
                reason TEXT,
                decision_context TEXT,
                confidence REAL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(symbol, timestamp_ms, decision_type)
            )
        """)
        
        # Performance metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT,
                timestamp_ms INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                details TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(symbol, timeframe, timestamp_ms, metric_name)
            )
        """)
    
    def _create_indexes(self, cursor):
        """Create database indexes for performance"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_raw_ticks_symbol_time ON raw_ticks(symbol, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_tf_time ON ohlcv_bars(symbol, timeframe, timestamp_open_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_market_structure_symbol_tf ON market_structure(symbol, timeframe, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_m1_filters_symbol_time ON m1_filter_signals(symbol, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_trade_decisions_symbol_time ON trade_decisions(symbol, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_performance_symbol_tf ON performance_metrics(symbol, timeframe, timestamp_ms DESC)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
    
    async def start_async_writer(self):
        """Start async database writer"""
        if self.running:
            return
        
        self.running = True
        self.worker_task = asyncio.create_task(self._async_writer_worker())
        logger.info("Async database writer started")
    
    async def stop_async_writer(self):
        """Stop async database writer"""
        self.running = False
        if self.worker_task:
            await self.worker_task
        logger.info("Async database writer stopped")
    
    async def _async_writer_worker(self):
        """Async database writer worker"""
        batch = []
        last_flush = asyncio.get_event_loop().time()
        
        while self.running:
            try:
                # Collect batch
                while len(batch) < self.config.batch_size:
                    try:
                        operation = self.write_queue.get_nowait()
                        batch.append(operation)
                    except Empty:
                        break
                
                # Flush batch if ready or timeout
                current_time = asyncio.get_event_loop().time()
                if batch and (len(batch) >= self.config.batch_size or 
                            (current_time - last_flush) >= self.config.flush_interval):
                    await self._flush_batch(batch)
                    batch.clear()
                    last_flush = current_time
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error in async writer worker: {e}")
                self.error_count += 1
                await asyncio.sleep(0.1)
    
    async def _flush_batch(self, batch: List[Dict[str, Any]]):
        """Flush batch of operations to database"""
        try:
            async with aiosqlite.connect(self.config.db_path) as conn:
                cursor = await conn.cursor()
                
                for operation in batch:
                    await self._execute_operation(cursor, operation)
                
                await conn.commit()
                self.write_count += len(batch)
                
        except Exception as e:
            logger.error(f"Error flushing batch: {e}")
            self.error_count += 1
    
    async def _execute_operation(self, cursor, operation: Dict[str, Any]):
        """Execute a single database operation"""
        try:
            op_type = operation.get('type')
            
            if op_type == 'insert_tick':
                await cursor.execute("""
                    INSERT OR REPLACE INTO raw_ticks 
                    (symbol, timestamp_ms, bid, ask, last, volume, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    operation['symbol'],
                    operation['timestamp_ms'],
                    operation['bid'],
                    operation['ask'],
                    operation.get('last'),
                    operation.get('volume'),
                    operation['source']
                ))
                
                # Trigger bar formation for M1 timeframe
                await self._form_bars(cursor, operation['symbol'], 'M1')
            
            elif op_type == 'insert_ohlcv':
                await cursor.execute("""
                    INSERT OR REPLACE INTO ohlcv_bars
                    (symbol, timeframe, timestamp_open_ms, open, high, low, close, volume, tick_volume, spread)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    operation['symbol'],
                    operation['timeframe'],
                    operation['timestamp_open_ms'],
                    operation['open'],
                    operation['high'],
                    operation['low'],
                    operation['close'],
                    operation.get('volume'),
                    operation.get('tick_volume'),
                    operation.get('spread')
                ))
            
            elif op_type == 'insert_structure':
                await cursor.execute("""
                    INSERT OR REPLACE INTO market_structure
                    (symbol, timeframe, timestamp_ms, type, price_level, direction, details, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    operation['symbol'],
                    operation['timeframe'],
                    operation['timestamp_ms'],
                    operation['type'],
                    operation['price_level'],
                    operation.get('direction'),
                    json.dumps(operation.get('details', {})),
                    operation.get('confidence', 0.0)
                ))
            
            elif op_type == 'insert_m1_filter':
                await cursor.execute("""
                    INSERT OR REPLACE INTO m1_filter_signals
                    (symbol, timestamp_ms, filter_type, signal_value, is_confirmed, vwap, atr, delta, volume_delta, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    operation['symbol'],
                    operation['timestamp_ms'],
                    operation['filter_type'],
                    operation['signal_value'],
                    operation['is_confirmed'],
                    operation.get('vwap', 0.0),
                    operation.get('atr', 0.0),
                    operation.get('delta', 0.0),
                    operation.get('volume_delta', 0.0),
                    json.dumps(operation.get('details', {}))
                ))
            
            elif op_type == 'insert_trade_decision':
                await cursor.execute("""
                    INSERT OR REPLACE INTO trade_decisions
                    (symbol, timestamp_ms, decision_type, direction, price, volume, reason, decision_context, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    operation['symbol'],
                    operation['timestamp_ms'],
                    operation['decision_type'],
                    operation.get('direction'),
                    operation.get('price'),
                    operation.get('volume'),
                    operation.get('reason'),
                    json.dumps(operation.get('decision_context', {})),
                    operation.get('confidence', 0.0)
                ))
            
            elif op_type == 'insert_performance':
                await cursor.execute("""
                    INSERT OR REPLACE INTO performance_metrics
                    (symbol, timeframe, timestamp_ms, metric_name, metric_value, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    operation['symbol'],
                    operation.get('timeframe'),
                    operation['timestamp_ms'],
                    operation['metric_name'],
                    operation['metric_value'],
                    json.dumps(operation.get('details', {}))
                ))
                
        except Exception as e:
            logger.error(f"Error executing operation {operation.get('type', 'unknown')}: {e}")
            self.error_count += 1
    
    async def _form_bars(self, cursor, symbol: str, timeframe: str):
        """Form OHLCV bars from raw ticks"""
        try:
            # Group ticks by minute for M1 bars
            if timeframe == 'M1':
                # Get all ticks for the symbol, grouped by minute
                await cursor.execute("""
                    SELECT 
                        (timestamp_ms / 60000) * 60000 as minute_start,
                        MIN(timestamp_ms) as first_tick,
                        MAX(timestamp_ms) as last_tick,
                        COUNT(*) as tick_count,
                        MIN((bid + ask) / 2) as min_price,
                        MAX((bid + ask) / 2) as max_price,
                        AVG((bid + ask) / 2) as avg_price,
                        SUM(volume) as total_volume,
                        AVG(ask - bid) as avg_spread
                    FROM raw_ticks 
                    WHERE symbol = ? 
                    GROUP BY (timestamp_ms / 60000) * 60000
                    HAVING tick_count >= 2
                    ORDER BY minute_start DESC
                """, (symbol,))
                
                minute_groups = await cursor.fetchall()
                
                for group in minute_groups:
                    minute_start = group[0]
                    
                    # Check if we already have a bar for this minute
                    await cursor.execute("""
                        SELECT COUNT(*) FROM ohlcv_bars 
                        WHERE symbol = ? AND timeframe = ? AND timestamp_open_ms = ?
                    """, (symbol, timeframe, minute_start))
                    
                    count_result = await cursor.fetchone()
                    if count_result[0] > 0:
                        continue  # Bar already exists
                    
                    # Get the first and last tick for this minute to get proper OHLC
                    await cursor.execute("""
                        SELECT timestamp_ms, bid, ask, last, volume
                        FROM raw_ticks 
                        WHERE symbol = ? AND timestamp_ms >= ? AND timestamp_ms < ?
                        ORDER BY timestamp_ms ASC
                    """, (symbol, minute_start, minute_start + 60000))
                    
                    minute_ticks = await cursor.fetchall()
                    if len(minute_ticks) < 2:
                        continue
                    
                    # Calculate OHLCV
                    prices = []
                    volumes = []
                    spreads = []
                    
                    for tick in minute_ticks:
                        mid_price = (tick[1] + tick[2]) / 2  # (bid + ask) / 2
                        prices.append(mid_price)
                        volumes.append(tick[4] or 0)
                        spreads.append(tick[2] - tick[1])  # ask - bid
                    
                    open_price = prices[0]
                    high_price = max(prices)
                    low_price = min(prices)
                    close_price = prices[-1]
                    total_volume = sum(volumes)
                    avg_spread = sum(spreads) / len(spreads) if spreads else 0
                    
                    # Insert the bar
                    await cursor.execute("""
                        INSERT OR IGNORE INTO ohlcv_bars 
                        (symbol, timeframe, timestamp_open_ms, open, high, low, close, volume, tick_volume, spread)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol, timeframe, minute_start, open_price, high_price, 
                        low_price, close_price, total_volume, len(minute_ticks), avg_spread
                    ))
                
        except Exception as e:
            logger.error(f"Error forming bars: {e}")
            self.error_count += 1
    
    def queue_operation(self, operation: Dict[str, Any]):
        """Queue a database operation for async processing"""
        try:
            self.write_queue.put(operation, block=False)
        except Exception as e:
            logger.error(f"Error queueing operation: {e}")
            self.error_count += 1
    
    async def store_tick_data(self, tick_data: Any):
        """Store tick data (convenience method)"""
        try:
            # Convert tick data to dictionary format
            if hasattr(tick_data, '__dict__'):
                tick_dict = tick_data.__dict__
            else:
                tick_dict = tick_data
            
            operation = {
                'type': 'insert_tick',
                'symbol': tick_dict.get('symbol', ''),
                'timestamp_ms': tick_dict.get('timestamp_ms', 0),
                'bid': tick_dict.get('bid', 0.0),
                'ask': tick_dict.get('ask', 0.0),
                'last': tick_dict.get('last', 0.0),
                'volume': tick_dict.get('volume', 0.0),
                'source': tick_dict.get('source', 'unknown')
            }
            
            self.queue_operation(operation)
            
            # Start async writer if not running
            if not self.running:
                await self.start_async_writer()
            
            # Wait a bit for processing
            await asyncio.sleep(0.1)
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing tick data: {e}")
            self.error_count += 1
            return False
    
    async def get_bars(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get OHLCV bars for a symbol and timeframe"""
        try:
            async with aiosqlite.connect(self.config.db_path) as conn:
                cursor = await conn.cursor()
                
                await cursor.execute("""
                    SELECT * FROM ohlcv_bars 
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY timestamp_open_ms DESC 
                    LIMIT ?
                """, (symbol, timeframe, limit))
                
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                result = []
                for row in rows:
                    result.append(dict(zip(columns, row)))
                
                self.read_count += 1
                return result
                
        except Exception as e:
            logger.error(f"Error getting bars: {e}")
            self.error_count += 1
            return []
    
    async def store_binance_data(self, binance_data: Any) -> bool:
        """Store Binance order book data"""
        try:
            # Convert binance data to tick format
            if hasattr(binance_data, 'bids') and hasattr(binance_data, 'asks'):
                if binance_data.bids and binance_data.asks:
                    bid_price = float(binance_data.bids[0][0])
                    ask_price = float(binance_data.asks[0][0])
                    mid_price = (bid_price + ask_price) / 2
                    
                    operation = {
                        'type': 'insert_tick',
                        'symbol': binance_data.symbol,
                        'timestamp_ms': binance_data.timestamp_ms,
                        'bid': bid_price,
                        'ask': ask_price,
                        'last': mid_price,
                        'volume': 0.0,
                        'source': 'binance'
                    }
                    
                    self.queue_operation(operation)
                    
                    # Start async writer if not running
                    if not self.running:
                        await self.start_async_writer()
                    
                    # Wait a bit for processing
                    await asyncio.sleep(0.1)
                    
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error storing Binance data: {e}")
            self.error_count += 1
            return False
    
    async def get_fused_data(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get fused data combining MT5 and Binance data"""
        try:
            async with aiosqlite.connect(self.config.db_path) as conn:
                cursor = await conn.cursor()
                
                await cursor.execute("""
                    SELECT * FROM raw_ticks 
                    WHERE symbol = ?
                    ORDER BY timestamp_ms DESC 
                    LIMIT ?
                """, (symbol, limit))
                
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                result = []
                for row in rows:
                    result.append(dict(zip(columns, row)))
                
                self.read_count += 1
                return result
                
        except Exception as e:
            logger.error(f"Error getting fused data: {e}")
            self.error_count += 1
            return []
    
    async def get_recent_data(self, symbol: str, timeframe: str = None, 
                            limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent data for a symbol"""
        try:
            async with aiosqlite.connect(self.config.db_path) as conn:
                cursor = await conn.cursor()
                
                if timeframe:
                    await cursor.execute("""
                        SELECT * FROM ohlcv_bars 
                        WHERE symbol = ? AND timeframe = ?
                        ORDER BY timestamp_open_ms DESC 
                        LIMIT ?
                    """, (symbol, timeframe, limit))
                else:
                    await cursor.execute("""
                        SELECT * FROM raw_ticks 
                        WHERE symbol = ?
                        ORDER BY timestamp_ms DESC 
                        LIMIT ?
                    """, (symbol, limit))
                
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                result = []
                for row in rows:
                    result.append(dict(zip(columns, row)))
                
                self.read_count += 1
                return result
                
        except Exception as e:
            logger.error(f"Error getting recent data: {e}")
            self.error_count += 1
            return []
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get database performance statistics"""
        return {
            'write_count': self.write_count,
            'read_count': self.read_count,
            'error_count': self.error_count,
            'queue_size': self.write_queue.qsize(),
            'running': self.running
        }

# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_database_manager():
        # Create configuration
        config = DatabaseConfig(
            db_path="test_mtf_data.db",
            batch_size=10,
            flush_interval=0.5
        )
        
        # Create manager
        manager = MTFDatabaseManager(config)
        
        # Start async writer
        await manager.start_async_writer()
        
        # Test operations
        print("Testing MTF Database Manager:")
        
        # Queue some operations
        manager.queue_operation({
            'type': 'insert_tick',
            'symbol': 'BTCUSDc',
            'timestamp_ms': 1640995200000,
            'bid': 50000.0,
            'ask': 50010.0,
            'volume': 100.0,
            'source': 'mt5'
        })
        
        manager.queue_operation({
            'type': 'insert_ohlcv',
            'symbol': 'BTCUSDc',
            'timeframe': 'M1',
            'timestamp_open_ms': 1640995200000,
            'open': 50000.0,
            'high': 50050.0,
            'low': 49950.0,
            'close': 50025.0,
            'volume': 1000.0
        })
        
        # Wait for processing
        await asyncio.sleep(1.0)
        
        # Get recent data
        recent_data = await manager.get_recent_data('BTCUSDc', limit=10)
        print(f"Recent data: {len(recent_data)} records")
        
        # Get performance stats
        stats = manager.get_performance_stats()
        print(f"Performance stats: {stats}")
        
        # Stop writer
        await manager.stop_async_writer()
        print("Database manager test completed")
    
    # Run test
    asyncio.run(test_database_manager())
