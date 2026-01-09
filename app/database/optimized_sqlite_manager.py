"""
Optimized SQLite Database Manager
Implements high-performance SQLite optimizations for trading data
"""

import sqlite3
import asyncio
import aiosqlite
import logging
import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import os
import json

logger = logging.getLogger(__name__)

@dataclass
class SQLiteOptimizationConfig:
    """Configuration for SQLite optimizations"""
    # WAL mode for better concurrency
    journal_mode: str = 'WAL'
    
    # NORMAL sync for better performance (vs FULL)
    synchronous: str = 'NORMAL'
    
    # MEMORY temp store for temporary tables
    temp_store: str = 'MEMORY'
    
    # 100MB cache size
    cache_size: int = -100000
    
    # 256MB memory-mapped I/O
    mmap_size: int = 268435456
    
    # 4KB page size (default)
    page_size: int = 4096
    
    # Optimize for speed
    optimize: bool = True
    
    # Enable foreign keys
    foreign_keys: bool = True
    
    # Enable recursive triggers
    recursive_triggers: bool = True
    
    # Query timeout (30 seconds)
    busy_timeout: int = 30000
    
    # Connection pool settings
    max_connections: int = 10
    connection_timeout: int = 30

class OptimizedSQLiteManager:
    """
    High-performance SQLite database manager with optimizations
    Implements WAL mode, connection pooling, and performance tuning
    """
    
    def __init__(self, db_path: str, config: Optional[SQLiteOptimizationConfig] = None):
        self.db_path = db_path
        self.config = config or SQLiteOptimizationConfig()
        
        # Connection pool
        self.connection_pool: List[sqlite3.Connection] = []
        self.pool_lock = threading.RLock()
        self.pool_semaphore = threading.Semaphore(self.config.max_connections)
        
        # Performance monitoring
        self.stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'avg_query_time_ms': 0.0,
            'max_query_time_ms': 0.0,
            'connection_pool_size': 0,
            'active_connections': 0
        }
        
        # Initialize database
        self._initialize_database()
        
        logger.info(f"OptimizedSQLiteManager initialized for {db_path}")
    
    def _initialize_database(self):
        """Initialize database with optimizations"""
        try:
            # Create database directory if it doesn't exist
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            # Create initial connection and apply optimizations
            conn = sqlite3.connect(self.db_path)
            self._apply_optimizations(conn)
            
            # Create tables with optimized indexes
            self._create_optimized_schema(conn)
            
            conn.close()
            
            # Initialize connection pool
            self._initialize_connection_pool()
            
            logger.info("Database initialized with optimizations")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _apply_optimizations(self, conn: sqlite3.Connection):
        """Apply SQLite performance optimizations"""
        optimizations = [
            f"PRAGMA journal_mode={self.config.journal_mode}",
            f"PRAGMA synchronous={self.config.synchronous}",
            f"PRAGMA temp_store={self.config.temp_store}",
            f"PRAGMA cache_size={self.config.cache_size}",
            f"PRAGMA mmap_size={self.config.mmap_size}",
            f"PRAGMA page_size={self.config.page_size}",
            f"PRAGMA foreign_keys={'ON' if self.config.foreign_keys else 'OFF'}",
            f"PRAGMA recursive_triggers={'ON' if self.config.recursive_triggers else 'OFF'}",
            f"PRAGMA busy_timeout={self.config.busy_timeout}",
        ]
        
        if self.config.optimize:
            optimizations.append("PRAGMA optimize")
        
        for pragma in optimizations:
            try:
                conn.execute(pragma)
            except Exception as e:
                logger.warning(f"Failed to apply optimization {pragma}: {e}")
    
    def _create_optimized_schema(self, conn: sqlite3.Connection):
        """Create database schema with optimized indexes"""
        cursor = conn.cursor()
        
        # Raw ticks table with optimized indexes
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
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(symbol, timestamp_ms, decision_type)
            )
        """)
        
        # DTMS exit signals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dtms_exit_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                trade_id TEXT,
                timestamp_ms INTEGER NOT NULL,
                exit_type TEXT NOT NULL,
                exit_price REAL NOT NULL,
                reason TEXT,
                exit_context TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(symbol, timestamp_ms, exit_type)
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
        
        # Binance order book table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS binance_order_book (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                bids TEXT NOT NULL,
                asks TEXT NOT NULL,
                last_update_id INTEGER,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(symbol, timestamp_ms)
            )
        """)
        
        # Create optimized indexes
        self._create_optimized_indexes(cursor)
        
        conn.commit()
        logger.info("Database schema created with optimized indexes")
    
    def _create_optimized_indexes(self, cursor: sqlite3.Cursor):
        """Create optimized indexes for performance"""
        indexes = [
            # Raw ticks indexes
            "CREATE INDEX IF NOT EXISTS idx_raw_ticks_symbol_ts ON raw_ticks (symbol, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_raw_ticks_source ON raw_ticks (source)",
            "CREATE INDEX IF NOT EXISTS idx_raw_ticks_created_at ON raw_ticks (created_at)",
            
            # OHLCV bars indexes
            "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_tf_ts ON ohlcv_bars (symbol, timeframe, timestamp_open_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_ohlcv_timeframe ON ohlcv_bars (timeframe)",
            "CREATE INDEX IF NOT EXISTS idx_ohlcv_created_at ON ohlcv_bars (created_at)",
            
            # Market structure indexes
            "CREATE INDEX IF NOT EXISTS idx_market_structure_symbol_tf_ts ON market_structure (symbol, timeframe, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_market_structure_type ON market_structure (type)",
            "CREATE INDEX IF NOT EXISTS idx_market_structure_direction ON market_structure (direction)",
            
            # M1 filter signals indexes
            "CREATE INDEX IF NOT EXISTS idx_m1_signals_symbol_ts ON m1_filter_signals (symbol, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_m1_signals_filter_type ON m1_filter_signals (filter_type)",
            "CREATE INDEX IF NOT EXISTS idx_m1_signals_confirmed ON m1_filter_signals (is_confirmed)",
            
            # Trade decisions indexes
            "CREATE INDEX IF NOT EXISTS idx_trade_decisions_symbol_ts ON trade_decisions (symbol, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_trade_decisions_type ON trade_decisions (decision_type)",
            "CREATE INDEX IF NOT EXISTS idx_trade_decisions_direction ON trade_decisions (direction)",
            
            # DTMS exit signals indexes
            "CREATE INDEX IF NOT EXISTS idx_dtms_exits_symbol_ts ON dtms_exit_signals (symbol, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_dtms_exits_type ON dtms_exit_signals (exit_type)",
            "CREATE INDEX IF NOT EXISTS idx_dtms_exits_trade_id ON dtms_exit_signals (trade_id)",
            
            # Performance metrics indexes
            "CREATE INDEX IF NOT EXISTS idx_perf_metrics_symbol_ts ON performance_metrics (symbol, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_perf_metrics_name ON performance_metrics (metric_name)",
            "CREATE INDEX IF NOT EXISTS idx_perf_metrics_timeframe ON performance_metrics (timeframe)",
            
            # Binance order book indexes
            "CREATE INDEX IF NOT EXISTS idx_binance_ob_symbol_ts ON binance_order_book (symbol, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_binance_ob_update_id ON binance_order_book (last_update_id)",
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception as e:
                logger.warning(f"Failed to create index: {e}")
    
    def _initialize_connection_pool(self):
        """Initialize connection pool with optimizations"""
        with self.pool_lock:
            for _ in range(self.config.max_connections):
                try:
                    conn = sqlite3.connect(
                        self.db_path,
                        timeout=self.config.connection_timeout,
                        check_same_thread=False
                    )
                    self._apply_optimizations(conn)
                    self.connection_pool.append(conn)
                except Exception as e:
                    logger.error(f"Failed to create connection: {e}")
    
    def get_connection(self) -> sqlite3.Connection:
        """Get connection from pool (blocking)"""
        self.pool_semaphore.acquire()
        
        with self.pool_lock:
            if self.connection_pool:
                conn = self.connection_pool.pop()
                self.stats['active_connections'] += 1
                return conn
            else:
                # Create new connection if pool is empty
                conn = sqlite3.connect(
                    self.db_path,
                    timeout=self.config.connection_timeout,
                    check_same_thread=False
                )
                self._apply_optimizations(conn)
                self.stats['active_connections'] += 1
                return conn
    
    def return_connection(self, conn: sqlite3.Connection):
        """Return connection to pool"""
        try:
            # Reset connection state
            conn.rollback()
            
            with self.pool_lock:
                if len(self.connection_pool) < self.config.max_connections:
                    self.connection_pool.append(conn)
                else:
                    conn.close()
                
                self.stats['active_connections'] -= 1
                self.stats['connection_pool_size'] = len(self.connection_pool)
                
        except Exception as e:
            logger.error(f"Error returning connection: {e}")
            try:
                conn.close()
            except:
                pass
        finally:
            self.pool_semaphore.release()
    
    def execute_query(self, query: str, params: Tuple = (), fetch: bool = True) -> Optional[List[Tuple]]:
        """Execute query with performance monitoring"""
        start_time = time.perf_counter_ns()
        conn = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(query, params)
            
            if fetch:
                result = cursor.fetchall()
            else:
                conn.commit()
                result = None
            
            # Update statistics
            end_time = time.perf_counter_ns()
            query_time_ms = (end_time - start_time) / 1_000_000
            
            self.stats['total_queries'] += 1
            self.stats['successful_queries'] += 1
            self.stats['avg_query_time_ms'] = (
                (self.stats['avg_query_time_ms'] * (self.stats['total_queries'] - 1) + query_time_ms) 
                / self.stats['total_queries']
            )
            self.stats['max_query_time_ms'] = max(self.stats['max_query_time_ms'], query_time_ms)
            
            return result
            
        except Exception as e:
            self.stats['total_queries'] += 1
            self.stats['failed_queries'] += 1
            logger.error(f"Query execution failed: {e}")
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def execute_batch(self, queries: List[Tuple[str, Tuple]]) -> List[Any]:
        """Execute batch of queries efficiently"""
        start_time = time.perf_counter_ns()
        conn = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            results = []
            for query, params in queries:
                cursor.execute(query, params)
                if query.strip().upper().startswith('SELECT'):
                    results.append(cursor.fetchall())
                else:
                    results.append(None)
            
            conn.commit()
            
            # Update statistics
            end_time = time.perf_counter_ns()
            batch_time_ms = (end_time - start_time) / 1_000_000
            
            self.stats['total_queries'] += len(queries)
            self.stats['successful_queries'] += len(queries)
            
            return results
            
        except Exception as e:
            self.stats['total_queries'] += len(queries)
            self.stats['failed_queries'] += len(queries)
            logger.error(f"Batch execution failed: {e}")
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def insert_tick(self, symbol: str, timestamp_ms: int, bid: float, ask: float, 
                   volume: float = 0.0, source: str = 'mt5', last: Optional[float] = None):
        """Insert tick data efficiently"""
        query = """
            INSERT OR IGNORE INTO raw_ticks 
            (symbol, timestamp_ms, bid, ask, last, volume, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (symbol, timestamp_ms, bid, ask, last, volume, source)
        self.execute_query(query, params, fetch=False)
    
    def insert_ohlcv_bar(self, symbol: str, timeframe: str, timestamp_open_ms: int,
                        open_price: float, high: float, low: float, close: float,
                        volume: float = 0.0, tick_volume: int = 0, spread: float = 0.0):
        """Insert OHLCV bar efficiently"""
        query = """
            INSERT OR IGNORE INTO ohlcv_bars
            (symbol, timeframe, timestamp_open_ms, open, high, low, close, volume, tick_volume, spread)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (symbol, timeframe, timestamp_open_ms, open_price, high, low, close, volume, tick_volume, spread)
        self.execute_query(query, params, fetch=False)
    
    def get_latest_ticks(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get latest ticks for a symbol"""
        query = """
            SELECT symbol, timestamp_ms, bid, ask, last, volume, source
            FROM raw_ticks
            WHERE symbol = ?
            ORDER BY timestamp_ms DESC
            LIMIT ?
        """
        results = self.execute_query(query, (symbol, limit))
        
        return [
            {
                'symbol': row[0],
                'timestamp_ms': row[1],
                'bid': row[2],
                'ask': row[3],
                'last': row[4],
                'volume': row[5],
                'source': row[6]
            }
            for row in results or []
        ]
    
    def get_ohlcv_bars(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get OHLCV bars for a symbol and timeframe"""
        query = """
            SELECT symbol, timeframe, timestamp_open_ms, open, high, low, close, volume, tick_volume, spread
            FROM ohlcv_bars
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp_open_ms DESC
            LIMIT ?
        """
        results = self.execute_query(query, (symbol, timeframe, limit))
        
        return [
            {
                'symbol': row[0],
                'timeframe': row[1],
                'timestamp_open_ms': row[2],
                'open': row[3],
                'high': row[4],
                'low': row[5],
                'close': row[6],
                'volume': row[7],
                'tick_volume': row[8],
                'spread': row[9]
            }
            for row in results or []
        ]
    
    def vacuum_and_analyze(self):
        """Perform database maintenance"""
        try:
            logger.info("Starting database maintenance...")
            
            # VACUUM to reclaim space
            self.execute_query("VACUUM", fetch=False)
            
            # ANALYZE to update statistics
            self.execute_query("ANALYZE", fetch=False)
            
            logger.info("Database maintenance completed")
            
        except Exception as e:
            logger.error(f"Database maintenance failed: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.pool_lock:
            return {
                'stats': dict(self.stats),
                'config': {
                    'journal_mode': self.config.journal_mode,
                    'synchronous': self.config.synchronous,
                    'temp_store': self.config.temp_store,
                    'cache_size': self.config.cache_size,
                    'mmap_size': self.config.mmap_size,
                    'page_size': self.config.page_size
                },
                'connection_pool': {
                    'max_connections': self.config.max_connections,
                    'current_pool_size': len(self.connection_pool),
                    'active_connections': self.stats['active_connections']
                }
            }
    
    def close(self):
        """Close all connections"""
        with self.pool_lock:
            for conn in self.connection_pool:
                try:
                    conn.close()
                except:
                    pass
            self.connection_pool.clear()
        
        logger.info("Database connections closed")

# Global database manager instance
_db_manager: Optional[OptimizedSQLiteManager] = None

def get_db_manager() -> Optional[OptimizedSQLiteManager]:
    """Get the global database manager instance"""
    return _db_manager

def initialize_db_manager(db_path: str, config: Optional[SQLiteOptimizationConfig] = None) -> bool:
    """Initialize the global database manager"""
    global _db_manager
    
    try:
        _db_manager = OptimizedSQLiteManager(db_path, config)
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database manager: {e}")
        return False

def close_db_manager():
    """Close the global database manager"""
    global _db_manager
    
    if _db_manager:
        _db_manager.close()
        _db_manager = None
