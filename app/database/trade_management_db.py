"""
Trade Management Database Integration
Database operations for trade management and historical analysis
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
class TradeRecord:
    """Trade record data structure"""
    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    exit_price: Optional[float]
    position_size: float
    entry_time: int
    exit_time: Optional[int]
    pnl: float
    status: str
    context: Dict[str, Any]

class TradeManagementDB:
    """Trade management database operations"""
    
    def __init__(self, db_path: str = "data/trade_management.db"):
        self.db_path = db_path
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
        """Initialize trade management database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA cache_size=100000")
            
            # Create tables
            self._create_tables(cursor)
            
            # Create indexes
            self._create_indexes(cursor)
            
            conn.commit()
            conn.close()
            
            logger.info(f"Trade management database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing trade management database: {e}")
            raise
    
    def _create_tables(self, cursor):
        """Create database tables"""
        # Active trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_trades (
                trade_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                position_size REAL NOT NULL,
                entry_time INTEGER NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                current_price REAL,
                unrealized_pnl REAL,
                status TEXT NOT NULL DEFAULT 'active',
                context TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        # Trade history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                trade_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                position_size REAL NOT NULL,
                entry_time INTEGER NOT NULL,
                exit_time INTEGER,
                pnl REAL,
                status TEXT NOT NULL,
                context TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        # Trade performance table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                details TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(symbol, timeframe, timestamp_ms, metric_name)
            )
        """)
        
        # Risk metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                threshold REAL,
                status TEXT NOT NULL,
                details TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(symbol, timestamp_ms, metric_name)
            )
        """)
        
        # Circuit breaker events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS circuit_breaker_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                breaker_type TEXT NOT NULL,
                status TEXT NOT NULL,
                trigger_value REAL NOT NULL,
                threshold REAL NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                duration_ms INTEGER,
                reasoning TEXT,
                context TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """)
    
    def _create_indexes(self, cursor):
        """Create database indexes"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_active_trades_symbol ON active_trades(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_active_trades_status ON active_trades(status)",
            "CREATE INDEX IF NOT EXISTS idx_trade_history_symbol ON trade_history(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_trade_history_status ON trade_history(status)",
            "CREATE INDEX IF NOT EXISTS idx_trade_history_entry_time ON trade_history(entry_time DESC)",
            "CREATE INDEX IF NOT EXISTS idx_trade_performance_symbol_tf ON trade_performance(symbol, timeframe, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_risk_metrics_symbol_time ON risk_metrics(symbol, timestamp_ms DESC)",
            "CREATE INDEX IF NOT EXISTS idx_circuit_breaker_symbol_time ON circuit_breaker_events(symbol, timestamp_ms DESC)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
    
    async def start_async_writer(self):
        """Start async database writer"""
        if self.running:
            return
        
        self.running = True
        self.worker_task = asyncio.create_task(self._async_writer_worker())
        logger.info("Async trade management writer started")
    
    async def stop_async_writer(self):
        """Stop async database writer"""
        self.running = False
        if self.worker_task:
            await self.worker_task
        logger.info("Async trade management writer stopped")
    
    async def _async_writer_worker(self):
        """Async database writer worker"""
        batch = []
        last_flush = asyncio.get_event_loop().time()
        
        while self.running:
            try:
                # Collect batch
                while len(batch) < 50:  # Smaller batch size for trade data
                    try:
                        operation = self.write_queue.get_nowait()
                        batch.append(operation)
                    except Empty:
                        break
                
                # Flush batch if ready or timeout
                current_time = asyncio.get_event_loop().time()
                if batch and (len(batch) >= 50 or (current_time - last_flush) >= 0.5):
                    await self._flush_batch(batch)
                    batch.clear()
                    last_flush = current_time
                
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error in async writer worker: {e}")
                self.error_count += 1
                await asyncio.sleep(0.1)
    
    async def _flush_batch(self, batch: List[Dict[str, Any]]):
        """Flush batch of operations to database"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
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
            
            if op_type == 'insert_active_trade':
                await cursor.execute("""
                    INSERT OR REPLACE INTO active_trades
                    (trade_id, symbol, direction, entry_price, position_size, entry_time, 
                     stop_loss, take_profit, current_price, unrealized_pnl, status, context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    operation['trade_id'],
                    operation['symbol'],
                    operation['direction'],
                    operation['entry_price'],
                    operation['position_size'],
                    operation['entry_time'],
                    operation.get('stop_loss'),
                    operation.get('take_profit'),
                    operation.get('current_price'),
                    operation.get('unrealized_pnl'),
                    operation.get('status', 'active'),
                    json.dumps(operation.get('context', {}))
                ))
            
            elif op_type == 'update_active_trade':
                await cursor.execute("""
                    UPDATE active_trades SET
                    current_price = ?, unrealized_pnl = ?, updated_at = ?
                    WHERE trade_id = ?
                """, (
                    operation['current_price'],
                    operation['unrealized_pnl'],
                    operation['timestamp_ms'],
                    operation['trade_id']
                ))
            
            elif op_type == 'close_trade':
                # Move from active to history
                await cursor.execute("""
                    INSERT INTO trade_history
                    (trade_id, symbol, direction, entry_price, exit_price, position_size,
                     entry_time, exit_time, pnl, status, context)
                    SELECT trade_id, symbol, direction, entry_price, ?, position_size,
                           entry_time, ?, ?, ?, context
                    FROM active_trades WHERE trade_id = ?
                """, (
                    operation['exit_price'],
                    operation['exit_time'],
                    operation['pnl'],
                    operation['status'],
                    operation['trade_id']
                ))
                
                # Remove from active trades
                await cursor.execute("DELETE FROM active_trades WHERE trade_id = ?", (operation['trade_id'],))
            
            elif op_type == 'insert_performance_metric':
                await cursor.execute("""
                    INSERT OR REPLACE INTO trade_performance
                    (symbol, timeframe, timestamp_ms, metric_name, metric_value, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    operation['symbol'],
                    operation['timeframe'],
                    operation['timestamp_ms'],
                    operation['metric_name'],
                    operation['metric_value'],
                    json.dumps(operation.get('details', {}))
                ))
            
            elif op_type == 'insert_risk_metric':
                await cursor.execute("""
                    INSERT OR REPLACE INTO risk_metrics
                    (symbol, timestamp_ms, metric_name, metric_value, threshold, status, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    operation['symbol'],
                    operation['timestamp_ms'],
                    operation['metric_name'],
                    operation['metric_value'],
                    operation.get('threshold'),
                    operation['status'],
                    json.dumps(operation.get('details', {}))
                ))
            
            elif op_type == 'insert_circuit_breaker_event':
                await cursor.execute("""
                    INSERT INTO circuit_breaker_events
                    (symbol, breaker_type, status, trigger_value, threshold, timestamp_ms,
                     duration_ms, reasoning, context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    operation['symbol'],
                    operation['breaker_type'],
                    operation['status'],
                    operation['trigger_value'],
                    operation['threshold'],
                    operation['timestamp_ms'],
                    operation.get('duration_ms'),
                    operation['reasoning'],
                    json.dumps(operation.get('context', {}))
                ))
                
        except Exception as e:
            logger.error(f"Error executing operation {operation.get('type', 'unknown')}: {e}")
            self.error_count += 1
    
    def queue_operation(self, operation: Dict[str, Any]):
        """Queue a database operation for async processing"""
        try:
            self.write_queue.put(operation, block=False)
        except Exception as e:
            logger.error(f"Error queueing operation: {e}")
            self.error_count += 1
    
    def create_trade(self, trade_data: Dict[str, Any]) -> str:
        """Create a new trade"""
        try:
            trade_id = trade_data.get('trade_id', f"{trade_data['symbol']}_{int(datetime.now().timestamp())}")
            
            operation = {
                'type': 'insert_active_trade',
                'trade_id': trade_id,
                'symbol': trade_data['symbol'],
                'direction': trade_data['direction'],
                'entry_price': trade_data['entry_price'],
                'position_size': trade_data['position_size'],
                'entry_time': trade_data['entry_time'],
                'stop_loss': trade_data.get('stop_loss'),
                'take_profit': trade_data.get('take_profit'),
                'current_price': trade_data['entry_price'],
                'unrealized_pnl': 0.0,
                'status': 'active',
                'context': trade_data.get('context', {})
            }
            
            self.queue_operation(operation)
            return trade_id
            
        except Exception as e:
            logger.error(f"Error creating trade: {e}")
            raise
    
    def update_trade(self, trade_id: str, current_price: float, unrealized_pnl: float):
        """Update trade with current price and PnL"""
        try:
            operation = {
                'type': 'update_active_trade',
                'trade_id': trade_id,
                'current_price': current_price,
                'unrealized_pnl': unrealized_pnl,
                'timestamp_ms': int(datetime.now(timezone.utc).timestamp() * 1000)
            }
            
            self.queue_operation(operation)
            
        except Exception as e:
            logger.error(f"Error updating trade: {e}")
    
    def close_trade(self, trade_id: str, exit_price: float, pnl: float, status: str = 'closed'):
        """Close a trade"""
        try:
            operation = {
                'type': 'close_trade',
                'trade_id': trade_id,
                'exit_price': exit_price,
                'exit_time': int(datetime.now(timezone.utc).timestamp() * 1000),
                'pnl': pnl,
                'status': status
            }
            
            self.queue_operation(operation)
            
        except Exception as e:
            logger.error(f"Error closing trade: {e}")
    
    async def get_active_trades(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Get active trades"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                if symbol:
                    await cursor.execute("""
                        SELECT * FROM active_trades WHERE symbol = ?
                        ORDER BY entry_time DESC
                    """, (symbol,))
                else:
                    await cursor.execute("""
                        SELECT * FROM active_trades ORDER BY entry_time DESC
                    """)
                
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                result = []
                for row in rows:
                    trade_dict = dict(zip(columns, row))
                    if trade_dict.get('context'):
                        trade_dict['context'] = json.loads(trade_dict['context'])
                    result.append(trade_dict)
                
                self.read_count += 1
                return result
                
        except Exception as e:
            logger.error(f"Error getting active trades: {e}")
            self.error_count += 1
            return []
    
    async def get_trade_history(
        self, 
        symbol: str = None, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get trade history"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                if symbol:
                    await cursor.execute("""
                        SELECT * FROM trade_history WHERE symbol = ?
                        ORDER BY exit_time DESC LIMIT ?
                    """, (symbol, limit))
                else:
                    await cursor.execute("""
                        SELECT * FROM trade_history ORDER BY exit_time DESC LIMIT ?
                    """, (limit,))
                
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                result = []
                for row in rows:
                    trade_dict = dict(zip(columns, row))
                    if trade_dict.get('context'):
                        trade_dict['context'] = json.loads(trade_dict['context'])
                    result.append(trade_dict)
                
                self.read_count += 1
                return result
                
        except Exception as e:
            logger.error(f"Error getting trade history: {e}")
            self.error_count += 1
            return []
    
    async def get_trade_statistics(self, symbol: str = None) -> Dict[str, Any]:
        """Get trade statistics"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                # Get basic statistics
                if symbol:
                    await cursor.execute("""
                        SELECT 
                            COUNT(*) as total_trades,
                            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                            SUM(pnl) as total_pnl,
                            AVG(pnl) as avg_pnl,
                            MAX(pnl) as max_win,
                            MIN(pnl) as max_loss
                        FROM trade_history WHERE symbol = ?
                    """, (symbol,))
                else:
                    await cursor.execute("""
                        SELECT 
                            COUNT(*) as total_trades,
                            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                            SUM(pnl) as total_pnl,
                            AVG(pnl) as avg_pnl,
                            MAX(pnl) as max_win,
                            MIN(pnl) as max_loss
                        FROM trade_history
                    """)
                
                row = await cursor.fetchone()
                if row:
                    total_trades, winning_trades, losing_trades, total_pnl, avg_pnl, max_win, max_loss = row
                    
                    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                    
                    return {
                        'total_trades': total_trades or 0,
                        'winning_trades': winning_trades or 0,
                        'losing_trades': losing_trades or 0,
                        'win_rate': win_rate,
                        'total_pnl': total_pnl or 0.0,
                        'avg_pnl': avg_pnl or 0.0,
                        'max_win': max_win or 0.0,
                        'max_loss': max_loss or 0.0,
                        'symbol': symbol or 'all'
                    }
                
                return {}
                
        except Exception as e:
            logger.error(f"Error getting trade statistics: {e}")
            self.error_count += 1
            return {}
    
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
    
    async def test_trade_management_db():
        # Create database manager
        db_manager = TradeManagementDB("test_trade_management.db")
        
        # Start async writer
        await db_manager.start_async_writer()
        
        print("Testing Trade Management Database:")
        
        # Create a trade
        trade_data = {
            'symbol': 'EURJPYc',
            'direction': 'BUY',
            'entry_price': 150.0,
            'position_size': 0.5,
            'entry_time': int(datetime.now(timezone.utc).timestamp() * 1000),
            'stop_loss': 149.0,
            'take_profit': 151.0,
            'context': {'strategy': 'multi_timeframe', 'confidence': 0.8}
        }
        
        trade_id = db_manager.create_trade(trade_data)
        print(f"Created trade: {trade_id}")
        
        # Update trade
        db_manager.update_trade(trade_id, 150.5, 25.0)
        print("Updated trade")
        
        # Wait for processing
        await asyncio.sleep(1.0)
        
        # Get active trades
        active_trades = await db_manager.get_active_trades()
        print(f"Active trades: {len(active_trades)}")
        
        # Close trade
        db_manager.close_trade(trade_id, 151.0, 50.0, 'closed')
        print("Closed trade")
        
        # Wait for processing
        await asyncio.sleep(1.0)
        
        # Get trade history
        trade_history = await db_manager.get_trade_history()
        print(f"Trade history: {len(trade_history)}")
        
        # Get statistics
        stats = await db_manager.get_trade_statistics()
        print(f"Trade statistics: {stats}")
        
        # Get performance stats
        perf_stats = db_manager.get_performance_stats()
        print(f"Performance stats: {perf_stats}")
        
        # Stop writer
        await db_manager.stop_async_writer()
        print("Trade management database test completed")
    
    # Run test
    asyncio.run(test_trade_management_db())
