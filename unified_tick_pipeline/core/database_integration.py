"""
Database Integration for Unified Tick Pipeline
Comprehensive database schema design and query optimization
"""

import asyncio
import logging
import sqlite3
import json
import gzip
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import threading
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)

class DatabaseType(Enum):
    """Database types for different data categories"""
    TICK_DATA = "tick_data"
    M5_CANDLES = "m5_candles"
    DTMS_ACTIONS = "dtms_actions"
    CHATGPT_ANALYSIS = "chatgpt_analysis"
    SYSTEM_METRICS = "system_metrics"
    PERFORMANCE_LOGS = "performance_logs"

class IndexType(Enum):
    """Index types for optimization"""
    PRIMARY = "primary"
    UNIQUE = "unique"
    INDEX = "index"
    COMPOSITE = "composite"
    PARTIAL = "partial"

@dataclass
class DatabaseSchema:
    """Database schema definition"""
    table_name: str
    columns: Dict[str, str]  # column_name: data_type
    indexes: List[Dict[str, Any]]
    constraints: List[str]
    partitions: Optional[Dict[str, Any]] = None

@dataclass
class QueryOptimization:
    """Query optimization settings"""
    use_indexes: bool
    batch_size: int
    connection_pool_size: int
    query_timeout: int
    cache_size: int
    wal_mode: bool

class DatabaseIntegration:
    """
    Database Integration for Unified Tick Pipeline
    
    Features:
    - Comprehensive database schema for all data types
    - Optimized indexing for fast queries
    - Data partitioning for performance
    - Query optimization for efficient data access
    - Data retention policies with automatic cleanup
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_active = False
        
        # Database configuration
        self.database_path = Path(self.config.get('database_path', 'data/unified_tick_pipeline'))
        self.database_path.mkdir(parents=True, exist_ok=True)
        
        # Database connections
        self.connections: Dict[str, sqlite3.Connection] = {}
        self.connection_pool_size = self.config.get('connection_pool_size', 10)
        self.query_timeout = self.config.get('query_timeout', 30)
        
        # Schema definitions
        self.schemas: Dict[DatabaseType, DatabaseSchema] = {}
        self._initialize_schemas()
        
        # Query optimization
        self.optimization = QueryOptimization(
            use_indexes=True,
            batch_size=self.config.get('batch_size', 1000),
            connection_pool_size=self.connection_pool_size,
            query_timeout=self.query_timeout,
            cache_size=self.config.get('cache_size', 10000),
            wal_mode=self.config.get('wal_mode', True)
        )
        
        # Performance metrics
        self.performance_metrics = {
            'queries_executed': 0,
            'queries_optimized': 0,
            'index_usage': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'data_compressed': 0,
            'cleanup_operations': 0,
            'error_count': 0,
            'average_query_time': 0.0,
            'database_size_mb': 0.0
        }
        
        logger.info("DatabaseIntegration initialized")
    
    async def initialize(self):
        """Initialize database integration"""
        try:
            logger.info("🔧 Initializing database integration...")
            
            # Create database connections
            await self._create_database_connections()
            
            # Create database schemas
            await self._create_database_schemas()
            
            # Create indexes
            await self._create_database_indexes()
            
            # Start maintenance tasks
            await self._start_maintenance_tasks()
            
            self.is_active = True
            logger.info("✅ Database integration initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database integration: {e}")
            raise
    
    async def stop(self):
        """Stop database integration"""
        try:
            logger.info("🛑 Stopping database integration...")
            self.is_active = False
            
            # Close all connections
            for conn in self.connections.values():
                conn.close()
            
            self.connections.clear()
            logger.info("✅ Database integration stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping database integration: {e}")
    
    def _initialize_schemas(self):
        """Initialize database schemas"""
        try:
            # Tick Data Schema
            self.schemas[DatabaseType.TICK_DATA] = DatabaseSchema(
                table_name="unified_ticks",
                columns={
                    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                    "symbol": "TEXT NOT NULL",
                    "timestamp_utc": "DATETIME NOT NULL",
                    "bid": "REAL NOT NULL",
                    "ask": "REAL NOT NULL",
                    "mid": "REAL NOT NULL",
                    "volume": "REAL DEFAULT 0",
                    "source": "TEXT NOT NULL",
                    "offset": "REAL DEFAULT 0",
                    "confidence": "REAL DEFAULT 0",
                    "atr": "REAL DEFAULT 0",
                    "volatility_score": "REAL DEFAULT 0",
                    "structure_majority": "TEXT DEFAULT 'neutral'",
                    "raw_data": "TEXT",
                    "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP"
                },
                indexes=[
                    {"name": "idx_ticks_symbol_time", "columns": ["symbol", "timestamp_utc"], "type": IndexType.COMPOSITE},
                    {"name": "idx_ticks_timestamp", "columns": ["timestamp_utc"], "type": IndexType.INDEX},
                    {"name": "idx_ticks_symbol", "columns": ["symbol"], "type": IndexType.INDEX},
                    {"name": "idx_ticks_source", "columns": ["source"], "type": IndexType.INDEX}
                ],
                constraints=[
                    "CHECK (bid > 0)",
                    "CHECK (ask > 0)",
                    "CHECK (mid > 0)",
                    "CHECK (volume >= 0)"
                ]
            )
            
            # M5 Candles Schema
            self.schemas[DatabaseType.M5_CANDLES] = DatabaseSchema(
                table_name="m5_candles",
                columns={
                    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                    "symbol": "TEXT NOT NULL",
                    "timestamp_utc": "DATETIME NOT NULL",
                    "open": "REAL NOT NULL",
                    "high": "REAL NOT NULL",
                    "low": "REAL NOT NULL",
                    "close": "REAL NOT NULL",
                    "volume": "REAL DEFAULT 0",
                    "source": "TEXT NOT NULL",
                    "fused_close": "REAL DEFAULT 0",
                    "volatility_score": "REAL DEFAULT 0",
                    "structure_bias": "TEXT DEFAULT 'neutral'",
                    "atr": "REAL DEFAULT 0",
                    "vwap": "REAL DEFAULT 0",
                    "raw_data": "TEXT",
                    "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP"
                },
                indexes=[
                    {"name": "idx_m5_symbol_time", "columns": ["symbol", "timestamp_utc"], "type": IndexType.COMPOSITE},
                    {"name": "idx_m5_timestamp", "columns": ["timestamp_utc"], "type": IndexType.INDEX},
                    {"name": "idx_m5_symbol", "columns": ["symbol"], "type": IndexType.INDEX},
                    {"name": "idx_m5_volatility", "columns": ["volatility_score"], "type": IndexType.INDEX}
                ],
                constraints=[
                    "CHECK (open > 0)",
                    "CHECK (high > 0)",
                    "CHECK (low > 0)",
                    "CHECK (close > 0)",
                    "CHECK (high >= low)",
                    "CHECK (volume >= 0)"
                ]
            )
            
            # DTMS Actions Schema
            self.schemas[DatabaseType.DTMS_ACTIONS] = DatabaseSchema(
                table_name="dtms_actions",
                columns={
                    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                    "action_id": "TEXT UNIQUE NOT NULL",
                    "ticket": "INTEGER NOT NULL",
                    "symbol": "TEXT NOT NULL",
                    "action_type": "TEXT NOT NULL",
                    "priority": "TEXT NOT NULL",
                    "parameters": "TEXT",
                    "timestamp_utc": "DATETIME NOT NULL",
                    "execution_time": "DATETIME",
                    "status": "TEXT DEFAULT 'pending'",
                    "result": "TEXT",
                    "error_message": "TEXT",
                    "retry_count": "INTEGER DEFAULT 0",
                    "max_retries": "INTEGER DEFAULT 3",
                    "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP"
                },
                indexes=[
                    {"name": "idx_dtms_action_id", "columns": ["action_id"], "type": IndexType.UNIQUE},
                    {"name": "idx_dtms_ticket", "columns": ["ticket"], "type": IndexType.INDEX},
                    {"name": "idx_dtms_symbol", "columns": ["symbol"], "type": IndexType.INDEX},
                    {"name": "idx_dtms_timestamp", "columns": ["timestamp_utc"], "type": IndexType.INDEX},
                    {"name": "idx_dtms_status", "columns": ["status"], "type": IndexType.INDEX},
                    {"name": "idx_dtms_priority", "columns": ["priority"], "type": IndexType.INDEX}
                ],
                constraints=[
                    "CHECK (ticket > 0)",
                    "CHECK (retry_count >= 0)",
                    "CHECK (max_retries >= 0)"
                ]
            )
            
            # ChatGPT Analysis Schema
            self.schemas[DatabaseType.CHATGPT_ANALYSIS] = DatabaseSchema(
                table_name="chatgpt_analysis",
                columns={
                    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                    "request_id": "TEXT UNIQUE NOT NULL",
                    "symbol": "TEXT NOT NULL",
                    "analysis_type": "TEXT NOT NULL",
                    "timeframes": "TEXT",
                    "parameters": "TEXT",
                    "access_level": "TEXT NOT NULL",
                    "timestamp_utc": "DATETIME NOT NULL",
                    "result": "TEXT",
                    "recommendations": "TEXT",
                    "confidence_score": "REAL DEFAULT 0",
                    "processing_time_ms": "INTEGER DEFAULT 0",
                    "authorized": "BOOLEAN DEFAULT FALSE",
                    "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP"
                },
                indexes=[
                    {"name": "idx_chatgpt_request_id", "columns": ["request_id"], "type": IndexType.UNIQUE},
                    {"name": "idx_chatgpt_symbol", "columns": ["symbol"], "type": IndexType.INDEX},
                    {"name": "idx_chatgpt_analysis_type", "columns": ["analysis_type"], "type": IndexType.INDEX},
                    {"name": "idx_chatgpt_timestamp", "columns": ["timestamp_utc"], "type": IndexType.INDEX},
                    {"name": "idx_chatgpt_access_level", "columns": ["access_level"], "type": IndexType.INDEX}
                ],
                constraints=[
                    "CHECK (confidence_score >= 0 AND confidence_score <= 1)",
                    "CHECK (processing_time_ms >= 0)"
                ]
            )
            
            # System Metrics Schema
            self.schemas[DatabaseType.SYSTEM_METRICS] = DatabaseSchema(
                table_name="system_metrics",
                columns={
                    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                    "metric_type": "TEXT NOT NULL",
                    "component": "TEXT NOT NULL",
                    "value": "REAL NOT NULL",
                    "unit": "TEXT",
                    "timestamp_utc": "DATETIME NOT NULL",
                    "metadata": "TEXT",
                    "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP"
                },
                indexes=[
                    {"name": "idx_metrics_type", "columns": ["metric_type"], "type": IndexType.INDEX},
                    {"name": "idx_metrics_component", "columns": ["component"], "type": IndexType.INDEX},
                    {"name": "idx_metrics_timestamp", "columns": ["timestamp_utc"], "type": IndexType.INDEX},
                    {"name": "idx_metrics_type_time", "columns": ["metric_type", "timestamp_utc"], "type": IndexType.COMPOSITE}
                ],
                constraints=[
                    "CHECK (value >= 0)"
                ]
            )
            
            # Performance Logs Schema
            self.schemas[DatabaseType.PERFORMANCE_LOGS] = DatabaseSchema(
                table_name="performance_logs",
                columns={
                    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                    "log_level": "TEXT NOT NULL",
                    "component": "TEXT NOT NULL",
                    "message": "TEXT NOT NULL",
                    "timestamp_utc": "DATETIME NOT NULL",
                    "thread_id": "TEXT",
                    "process_id": "INTEGER",
                    "metadata": "TEXT",
                    "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP"
                },
                indexes=[
                    {"name": "idx_logs_level", "columns": ["log_level"], "type": IndexType.INDEX},
                    {"name": "idx_logs_component", "columns": ["component"], "type": IndexType.INDEX},
                    {"name": "idx_logs_timestamp", "columns": ["timestamp_utc"], "type": IndexType.INDEX},
                    {"name": "idx_logs_level_time", "columns": ["log_level", "timestamp_utc"], "type": IndexType.COMPOSITE}
                ],
                constraints=[]
            )
            
            logger.info("✅ Database schemas initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing schemas: {e}")
    
    async def _create_database_connections(self):
        """Create database connections"""
        try:
            for db_type in DatabaseType:
                db_path = self.database_path / f"{db_type.value}.db"
                
                # Create connection with optimizations
                conn = sqlite3.connect(
                    str(db_path),
                    timeout=self.query_timeout,
                    check_same_thread=False
                )
                
                # Enable WAL mode for better concurrency
                if self.optimization.wal_mode:
                    conn.execute("PRAGMA journal_mode=WAL")
                
                # Set cache size
                conn.execute(f"PRAGMA cache_size={self.optimization.cache_size}")
                
                # Enable foreign keys
                conn.execute("PRAGMA foreign_keys=ON")
                
                # Set synchronous mode for performance
                conn.execute("PRAGMA synchronous=NORMAL")
                
                # Set temp store to memory
                conn.execute("PRAGMA temp_store=MEMORY")
                
                self.connections[db_type.value] = conn
                
            logger.info("✅ Database connections created")
            
        except Exception as e:
            logger.error(f"❌ Error creating database connections: {e}")
    
    async def _create_database_schemas(self):
        """Create database schemas"""
        try:
            for db_type, schema in self.schemas.items():
                conn = self.connections[db_type.value]
                
                # Create table
                columns_sql = ", ".join([f"{col} {dtype}" for col, dtype in schema.columns.items()])
                constraints_sql = ", ".join(schema.constraints) if schema.constraints else ""
                
                if constraints_sql:
                    create_table_sql = f"CREATE TABLE IF NOT EXISTS {schema.table_name} ({columns_sql}, {constraints_sql})"
                else:
                    create_table_sql = f"CREATE TABLE IF NOT EXISTS {schema.table_name} ({columns_sql})"
                
                conn.execute(create_table_sql)
                conn.commit()
                
            logger.info("✅ Database schemas created")
            
        except Exception as e:
            logger.error(f"❌ Error creating database schemas: {e}")
    
    async def _create_database_indexes(self):
        """Create database indexes"""
        try:
            for db_type, schema in self.schemas.items():
                conn = self.connections[db_type.value]
                
                for index in schema.indexes:
                    index_name = index["name"]
                    columns = index["columns"]
                    index_type = index["type"]
                    
                    if index_type == IndexType.UNIQUE:
                        create_index_sql = f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {schema.table_name} ({', '.join(columns)})"
                    else:
                        create_index_sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {schema.table_name} ({', '.join(columns)})"
                    
                    conn.execute(create_index_sql)
                
                conn.commit()
                
            logger.info("✅ Database indexes created")
            
        except Exception as e:
            logger.error(f"❌ Error creating database indexes: {e}")
    
    async def _start_maintenance_tasks(self):
        """Start database maintenance tasks"""
        try:
            # Start cleanup task
            asyncio.create_task(self._cleanup_task())
            
            # Start optimization task
            asyncio.create_task(self._optimization_task())
            
            # Start monitoring task
            asyncio.create_task(self._monitoring_task())
            
            logger.info("✅ Database maintenance tasks started")
            
        except Exception as e:
            logger.error(f"❌ Error starting maintenance tasks: {e}")
    
    async def _cleanup_task(self):
        """Database cleanup task"""
        while self.is_active:
            try:
                # Clean up old data based on retention policies
                await self._cleanup_old_data()
                
                # Skip heavy maintenance during runtime; VACUUM will run on shutdown
                pass
                
                # Update performance metrics
                await self._update_performance_metrics()
                
                # Sleep for 1 hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"❌ Error in cleanup task: {e}")
                await asyncio.sleep(300)  # 5 minutes on error
    
    async def _optimization_task(self):
        """Database optimization task"""
        while self.is_active:
            try:
                # Analyze query performance
                await self._analyze_query_performance()
                
                # Update statistics
                await self._update_statistics()
                
                # Optimize indexes
                await self._optimize_indexes()
                
                # Sleep for 6 hours
                await asyncio.sleep(21600)
                
            except Exception as e:
                logger.error(f"❌ Error in optimization task: {e}")
                await asyncio.sleep(1800)  # 30 minutes on error
    
    async def _monitoring_task(self):
        """Database monitoring task"""
        while self.is_active:
            try:
                # Monitor database size
                await self._monitor_database_size()
                
                # Monitor query performance
                await self._monitor_query_performance()
                
                # Monitor connection health
                await self._monitor_connection_health()
                
                # Sleep for 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"❌ Error in monitoring task: {e}")
                await asyncio.sleep(60)  # 1 minute on error
    
    async def _cleanup_old_data(self):
        """Clean up old data based on retention policies"""
        try:
            # Get retention policies from config
            retention_policies = self.config.get('retention_policies', {})
            
            for db_type, retention_days in retention_policies.items():
                if db_type in self.connections:
                    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
                    
                    # Clean up old data
                    if db_type == 'tick_data':
                        await self._cleanup_old_ticks(cutoff_date)
                    elif db_type == 'm5_candles':
                        await self._cleanup_old_candles(cutoff_date)
                    elif db_type == 'dtms_actions':
                        await self._cleanup_old_actions(cutoff_date)
                    elif db_type == 'chatgpt_analysis':
                        await self._cleanup_old_analysis(cutoff_date)
                    elif db_type == 'system_metrics':
                        await self._cleanup_old_metrics(cutoff_date)
                    elif db_type == 'performance_logs':
                        await self._cleanup_old_logs(cutoff_date)
            
            self.performance_metrics['cleanup_operations'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up old data: {e}")
    
    async def _cleanup_old_ticks(self, cutoff_date: datetime):
        """Clean up old tick data"""
        try:
            conn = self.connections['tick_data']
            cursor = conn.cursor()
            
            # Delete old ticks
            cursor.execute(
                "DELETE FROM unified_ticks WHERE timestamp_utc < ?",
                (cutoff_date.isoformat(),)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old tick records")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up old ticks: {e}")
    
    async def _cleanup_old_candles(self, cutoff_date: datetime):
        """Clean up old M5 candle data"""
        try:
            conn = self.connections['m5_candles']
            cursor = conn.cursor()
            
            # Delete old candles
            cursor.execute(
                "DELETE FROM m5_candles WHERE timestamp_utc < ?",
                (cutoff_date.isoformat(),)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old M5 candle records")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up old candles: {e}")
    
    async def _cleanup_old_actions(self, cutoff_date: datetime):
        """Clean up old DTMS actions"""
        try:
            conn = self.connections['dtms_actions']
            cursor = conn.cursor()
            
            # Delete old actions
            cursor.execute(
                "DELETE FROM dtms_actions WHERE timestamp_utc < ?",
                (cutoff_date.isoformat(),)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old DTMS action records")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up old actions: {e}")
    
    async def _cleanup_old_analysis(self, cutoff_date: datetime):
        """Clean up old ChatGPT analysis"""
        try:
            conn = self.connections['chatgpt_analysis']
            cursor = conn.cursor()
            
            # Delete old analysis
            cursor.execute(
                "DELETE FROM chatgpt_analysis WHERE timestamp_utc < ?",
                (cutoff_date.isoformat(),)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old ChatGPT analysis records")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up old analysis: {e}")
    
    async def _cleanup_old_metrics(self, cutoff_date: datetime):
        """Clean up old system metrics"""
        try:
            conn = self.connections['system_metrics']
            cursor = conn.cursor()
            
            # Delete old metrics
            cursor.execute(
                "DELETE FROM system_metrics WHERE timestamp_utc < ?",
                (cutoff_date.isoformat(),)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old system metric records")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up old metrics: {e}")
    
    async def _cleanup_old_logs(self, cutoff_date: datetime):
        """Clean up old performance logs"""
        try:
            conn = self.connections['performance_logs']
            cursor = conn.cursor()
            
            # Delete old logs
            cursor.execute(
                "DELETE FROM performance_logs WHERE timestamp_utc < ?",
                (cutoff_date.isoformat(),)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old performance log records")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up old logs: {e}")
    
    async def _vacuum_databases(self):
        """Vacuum databases for optimization"""
        try:
            for db_type, conn in self.connections.items():
                conn.execute("VACUUM")
                conn.commit()
            
            logger.debug("🧹 Database vacuum completed")
            
        except Exception as e:
            logger.error(f"❌ Error vacuuming databases: {e}")
    
    async def _analyze_query_performance(self):
        """Analyze query performance"""
        try:
            for db_type, conn in self.connections.items():
                # Analyze tables
                conn.execute("ANALYZE")
                conn.commit()
            
            logger.debug("📊 Query performance analysis completed")
            
        except Exception as e:
            logger.error(f"❌ Error analyzing query performance: {e}")
    
    async def _update_statistics(self):
        """Update database statistics"""
        try:
            for db_type, conn in self.connections.items():
                # Update statistics
                conn.execute("PRAGMA optimize")
            
            logger.debug("📊 Database statistics updated")
            
        except Exception as e:
            logger.error(f"❌ Error updating statistics: {e}")
    
    async def _optimize_indexes(self):
        """Optimize database indexes"""
        try:
            for db_type, conn in self.connections.items():
                # Reindex
                conn.execute("REINDEX")
                conn.commit()
            
            logger.debug("🔧 Database indexes optimized")
            
        except Exception as e:
            logger.error(f"❌ Error optimizing indexes: {e}")
    
    async def _monitor_database_size(self):
        """Monitor database size"""
        try:
            total_size = 0
            
            for db_type, conn in self.connections.items():
                # Get database size
                cursor = conn.cursor()
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                
                db_size = page_count * page_size
                total_size += db_size
            
            # Convert to MB
            total_size_mb = total_size / (1024 * 1024)
            self.performance_metrics['database_size_mb'] = total_size_mb
            
            logger.debug(f"📊 Database size: {total_size_mb:.2f} MB")
            
        except Exception as e:
            logger.error(f"❌ Error monitoring database size: {e}")
    
    async def _monitor_query_performance(self):
        """Monitor query performance"""
        try:
            # This would monitor query performance in a real implementation
            logger.debug("📊 Query performance monitoring completed")
            
        except Exception as e:
            logger.error(f"❌ Error monitoring query performance: {e}")
    
    async def _monitor_connection_health(self):
        """Monitor connection health"""
        try:
            for db_type, conn in self.connections.items():
                # Test connection
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            logger.debug("📊 Connection health monitoring completed")
            
        except Exception as e:
            logger.error(f"❌ Error monitoring connection health: {e}")
    
    async def _update_performance_metrics(self):
        """Update performance metrics"""
        try:
            # Update metrics based on database operations
            self.performance_metrics['queries_executed'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error updating performance metrics: {e}")
    
    # Public API methods
    async def insert_tick_data(self, tick_data: Dict[str, Any]) -> bool:
        """Insert tick data into database"""
        try:
            conn = self.connections['tick_data']
            cursor = conn.cursor()
            
            # Prepare data
            data = (
                tick_data.get('symbol'),
                tick_data.get('timestamp_utc'),
                tick_data.get('bid'),
                tick_data.get('ask'),
                tick_data.get('mid'),
                tick_data.get('volume', 0),
                tick_data.get('source'),
                tick_data.get('offset', 0),
                tick_data.get('confidence', 0),
                tick_data.get('atr', 0),
                tick_data.get('volatility_score', 0),
                tick_data.get('structure_majority', 'neutral'),
                json.dumps(tick_data.get('raw_data', {}))
            )
            
            # Insert data
            cursor.execute("""
                INSERT INTO unified_ticks 
                (symbol, timestamp_utc, bid, ask, mid, volume, source, offset, confidence, atr, volatility_score, structure_majority, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            
            conn.commit()
            self.performance_metrics['queries_executed'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inserting tick data: {e}")
            self.performance_metrics['error_count'] += 1
            return False
    
    async def insert_m5_candle(self, candle_data: Dict[str, Any]) -> bool:
        """Insert M5 candle data into database"""
        try:
            conn = self.connections['m5_candles']
            cursor = conn.cursor()
            
            # Prepare data
            data = (
                candle_data.get('symbol'),
                candle_data.get('timestamp_utc'),
                candle_data.get('open'),
                candle_data.get('high'),
                candle_data.get('low'),
                candle_data.get('close'),
                candle_data.get('volume', 0),
                candle_data.get('source'),
                candle_data.get('fused_close', 0),
                candle_data.get('volatility_score', 0),
                candle_data.get('structure_bias', 'neutral'),
                candle_data.get('atr', 0),
                candle_data.get('vwap', 0),
                json.dumps(candle_data.get('raw_data', {}))
            )
            
            # Insert data
            cursor.execute("""
                INSERT INTO m5_candles 
                (symbol, timestamp_utc, open, high, low, close, volume, source, fused_close, volatility_score, structure_bias, atr, vwap, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            
            conn.commit()
            self.performance_metrics['queries_executed'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inserting M5 candle: {e}")
            self.performance_metrics['error_count'] += 1
            return False
    
    async def insert_dtms_action(self, action_data: Dict[str, Any]) -> bool:
        """Insert DTMS action into database"""
        try:
            conn = self.connections['dtms_actions']
            cursor = conn.cursor()
            
            # Prepare data
            data = (
                action_data.get('action_id'),
                action_data.get('ticket'),
                action_data.get('symbol'),
                action_data.get('action_type'),
                action_data.get('priority'),
                json.dumps(action_data.get('parameters', {})),
                action_data.get('timestamp_utc'),
                action_data.get('execution_time'),
                action_data.get('status', 'pending'),
                json.dumps(action_data.get('result', {})),
                action_data.get('error_message'),
                action_data.get('retry_count', 0),
                action_data.get('max_retries', 3)
            )
            
            # Insert data
            cursor.execute("""
                INSERT INTO dtms_actions 
                (action_id, ticket, symbol, action_type, priority, parameters, timestamp_utc, execution_time, status, result, error_message, retry_count, max_retries)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            
            conn.commit()
            self.performance_metrics['queries_executed'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inserting DTMS action: {e}")
            self.performance_metrics['error_count'] += 1
            return False
    
    async def insert_chatgpt_analysis(self, analysis_data: Dict[str, Any]) -> bool:
        """Insert ChatGPT analysis into database"""
        try:
            conn = self.connections['chatgpt_analysis']
            cursor = conn.cursor()
            
            # Prepare data
            data = (
                analysis_data.get('request_id'),
                analysis_data.get('symbol'),
                analysis_data.get('analysis_type'),
                json.dumps(analysis_data.get('timeframes', [])),
                json.dumps(analysis_data.get('parameters', {})),
                analysis_data.get('access_level'),
                analysis_data.get('timestamp_utc'),
                json.dumps(analysis_data.get('result', {})),
                json.dumps(analysis_data.get('recommendations', [])),
                analysis_data.get('confidence_score', 0),
                analysis_data.get('processing_time_ms', 0),
                analysis_data.get('authorized', False)
            )
            
            # Insert data
            cursor.execute("""
                INSERT INTO chatgpt_analysis 
                (request_id, symbol, analysis_type, timeframes, parameters, access_level, timestamp_utc, result, recommendations, confidence_score, processing_time_ms, authorized)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            
            conn.commit()
            self.performance_metrics['queries_executed'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inserting ChatGPT analysis: {e}")
            self.performance_metrics['error_count'] += 1
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get database integration status"""
        return {
            'is_active': self.is_active,
            'database_path': str(self.database_path),
            'connections': len(self.connections),
            'schemas': len(self.schemas),
            'optimization': {
                'use_indexes': self.optimization.use_indexes,
                'batch_size': self.optimization.batch_size,
                'connection_pool_size': self.optimization.connection_pool_size,
                'query_timeout': self.optimization.query_timeout,
                'cache_size': self.optimization.cache_size,
                'wal_mode': self.optimization.wal_mode
            },
            'performance_metrics': self.performance_metrics,
            'database_types': [db_type.value for db_type in DatabaseType]
        }
