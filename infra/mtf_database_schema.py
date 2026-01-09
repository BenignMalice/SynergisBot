"""
Multi-Timeframe Database Schema Implementation
Institutional-grade database schema for multi-timeframe trading system
"""

import sqlite3
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class MTFDatabaseSchema:
    """Multi-timeframe database schema with optimized indexes and SQLite configuration"""
    
    def __init__(self, db_path: str = "data/mtf_trading.db"):
        self.db_path = db_path
        self.connection = None
        
    def connect(self):
        """Connect to database with optimized SQLite settings"""
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._configure_sqlite()
        self._create_tables()
        self._create_indexes()
        
    def _configure_sqlite(self):
        """Configure SQLite for optimal performance"""
        pragmas = [
            "PRAGMA journal_mode=WAL",
            "PRAGMA synchronous=NORMAL", 
            "PRAGMA temp_store=MEMORY",
            "PRAGMA busy_timeout=5000",
            "PRAGMA cache_size=-100000"
        ]
        
        for pragma in pragmas:
            self.connection.execute(pragma)
            
    def _create_tables(self):
        """Create all multi-timeframe tables"""
        
        # Multi-timeframe structure analysis
        self.connection.execute("""
        CREATE TABLE IF NOT EXISTS mtf_structure_analysis (
            id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp_utc INTEGER NOT NULL,
            structure_type TEXT, -- 'BOS', 'CHOCH', 'OB', 'FVG'
            structure_data TEXT, -- JSON as TEXT
            confidence_score REAL,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
        """)
        
        # M1 precision filters
        self.connection.execute("""
        CREATE TABLE IF NOT EXISTS m1_precision_filters (
            id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            timestamp_utc INTEGER NOT NULL,
            vwap_reclaim BOOLEAN,
            delta_spike BOOLEAN,
            micro_bos BOOLEAN,
            atr_ratio_valid BOOLEAN,
            spread_valid BOOLEAN,
            filters_passed INTEGER,
            filter_score REAL,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
        """)
        
        # MTF M1 filters (alias for backward compatibility)
        self.connection.execute("""
        CREATE TABLE IF NOT EXISTS mtf_m1_filters (
            id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            timestamp_utc INTEGER NOT NULL,
            vwap_reclaim BOOLEAN,
            delta_spike BOOLEAN,
            micro_bos BOOLEAN,
            atr_ratio_valid BOOLEAN,
            spread_valid BOOLEAN,
            filters_passed INTEGER,
            filter_score REAL,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
        """)
        
        # Multi-timeframe trade decisions
        self.connection.execute("""
        CREATE TABLE IF NOT EXISTS mtf_trade_decisions (
            id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            timestamp_utc INTEGER NOT NULL,
            h4_bias TEXT, -- 'BULLISH', 'BEARISH', 'NEUTRAL'
            h1_bias TEXT,
            m30_setup TEXT,
            m15_setup TEXT,
            m5_structure TEXT,
            m1_confirmation BOOLEAN,
            decision TEXT, -- 'BUY', 'SELL', 'HOLD'
            confidence REAL,
            risk_reward REAL,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
        """)
        
        # Multi-timeframe trade signals
        self.connection.execute("""
        CREATE TABLE IF NOT EXISTS mtf_trade_signals (
            id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            timestamp_utc INTEGER NOT NULL,
            signal_type TEXT, -- 'BUY', 'SELL', 'HOLD'
            timeframe TEXT, -- 'H4', 'H1', 'M30', 'M15', 'M5', 'M1'
            signal_strength REAL, -- 0.0 to 1.0
            confidence_score REAL, -- 0.0 to 1.0
            price_level REAL,
            stop_loss REAL,
            take_profit REAL,
            risk_reward_ratio REAL,
            market_structure TEXT, -- 'BOS', 'CHOCH', 'OB', 'FVG'
            bias_alignment BOOLEAN,
            volume_confirmation BOOLEAN,
            news_impact TEXT, -- 'POSITIVE', 'NEGATIVE', 'NEUTRAL'
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
        """)
        
        # DTMS multi-timeframe exits
        self.connection.execute("""
        CREATE TABLE IF NOT EXISTS mtf_dtms_exits (
            id INTEGER PRIMARY KEY,
            ticket INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            timestamp_utc INTEGER NOT NULL,
            h4_signal TEXT,
            h1_signal TEXT,
            m30_signal TEXT,
            m15_signal TEXT,
            m5_signal TEXT,
            m1_signal TEXT,
            exit_action TEXT, -- 'CLOSE', 'PARTIAL', 'TIGHTEN_SL'
            exit_percentage REAL,
            new_sl_price REAL,
            new_tp_price REAL,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
        """)
        
        # Performance metrics by timeframe
        self.connection.execute("""
        CREATE TABLE IF NOT EXISTS mtf_performance_metrics (
            id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            date_utc INTEGER NOT NULL,
            total_signals INTEGER,
            successful_signals INTEGER,
            win_rate REAL,
            avg_rr REAL,
            max_drawdown REAL,
            latency_p50 REAL,
            latency_p95 REAL,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
        """)
        
        # Binance order book data (context only)
        self.connection.execute("""
        CREATE TABLE IF NOT EXISTS binance_orderbook (
            id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            timestamp_utc INTEGER NOT NULL,
            bid_price REAL,
            ask_price REAL,
            bid_volume REAL,
            ask_volume REAL,
            spread REAL,
            depth_data TEXT, -- JSON as TEXT
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
        """)
        
        # Hot path performance metrics
        self.connection.execute("""
        CREATE TABLE IF NOT EXISTS hot_path_metrics (
            id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            stage TEXT NOT NULL, -- 'ingestion', 'compute', 'decision', 'write'
            timestamp_utc INTEGER NOT NULL,
            latency_ms REAL,
            queue_depth INTEGER,
            memory_mb REAL,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
        """)
        
        self.connection.commit()
        logger.info("Multi-timeframe database tables created successfully")
        
    def _create_indexes(self):
        """Create critical indexes for performance"""
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_mtf_struct ON mtf_structure_analysis(symbol, timeframe, timestamp_utc DESC)",
            "CREATE INDEX IF NOT EXISTS idx_mtf_decisions ON mtf_trade_decisions(symbol, timestamp_utc DESC)",
            "CREATE INDEX IF NOT EXISTS idx_mtf_exits ON mtf_dtms_exits(symbol, timestamp_utc DESC)",
            "CREATE INDEX IF NOT EXISTS idx_m1_filters ON m1_precision_filters(symbol, timestamp_utc DESC)",
            "CREATE INDEX IF NOT EXISTS idx_binance_ob ON binance_orderbook(symbol, timestamp_utc DESC)",
            "CREATE INDEX IF NOT EXISTS idx_hot_path ON hot_path_metrics(symbol, stage, timestamp_utc DESC)",
            "CREATE INDEX IF NOT EXISTS idx_performance ON mtf_performance_metrics(symbol, timeframe, date_utc DESC)"
        ]
        
        for index_sql in indexes:
            self.connection.execute(index_sql)
            
        self.connection.commit()
        logger.info("Database indexes created successfully")
        
    def insert_structure_analysis(self, symbol: str, timeframe: str, timestamp_utc: int, 
                                structure_type: str, structure_data: Dict[str, Any], 
                                confidence_score: float):
        """Insert structure analysis data"""
        try:
            self.connection.execute("""
                INSERT INTO mtf_structure_analysis 
                (symbol, timeframe, timestamp_utc, structure_type, structure_data, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (symbol, timeframe, timestamp_utc, structure_type, 
                  json.dumps(structure_data), confidence_score))
            self.connection.commit()
        except Exception as e:
            logger.error(f"Error inserting structure analysis: {e}")
            
    def insert_m1_filters(self, symbol: str, timestamp_utc: int, vwap_reclaim: bool,
                         delta_spike: bool, micro_bos: bool, atr_ratio_valid: bool,
                         spread_valid: bool, filters_passed: int, filter_score: float):
        """Insert M1 precision filter data"""
        try:
            self.connection.execute("""
                INSERT INTO m1_precision_filters 
                (symbol, timestamp_utc, vwap_reclaim, delta_spike, micro_bos, 
                 atr_ratio_valid, spread_valid, filters_passed, filter_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, timestamp_utc, vwap_reclaim, delta_spike, micro_bos,
                  atr_ratio_valid, spread_valid, filters_passed, filter_score))
            self.connection.commit()
        except Exception as e:
            logger.error(f"Error inserting M1 filters: {e}")
            
    def insert_trade_decision(self, symbol: str, timestamp_utc: int, h4_bias: str,
                            h1_bias: str, m30_setup: str, m15_setup: str, m5_structure: str,
                            m1_confirmation: bool, decision: str, confidence: float, 
                            risk_reward: float):
        """Insert multi-timeframe trade decision"""
        try:
            self.connection.execute("""
                INSERT INTO mtf_trade_decisions 
                (symbol, timestamp_utc, h4_bias, h1_bias, m30_setup, m15_setup, 
                 m5_structure, m1_confirmation, decision, confidence, risk_reward)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, timestamp_utc, h4_bias, h1_bias, m30_setup, m15_setup,
                  m5_structure, m1_confirmation, decision, confidence, risk_reward))
            self.connection.commit()
        except Exception as e:
            logger.error(f"Error inserting trade decision: {e}")
            
    def insert_dtms_exit(self, ticket: int, symbol: str, timestamp_utc: int,
                        h4_signal: str, h1_signal: str, m30_signal: str, m15_signal: str,
                        m5_signal: str, m1_signal: str, exit_action: str,
                        exit_percentage: float, new_sl_price: float, new_tp_price: float):
        """Insert DTMS exit decision"""
        try:
            self.connection.execute("""
                INSERT INTO mtf_dtms_exits 
                (ticket, symbol, timestamp_utc, h4_signal, h1_signal, m30_signal, 
                 m15_signal, m5_signal, m1_signal, exit_action, exit_percentage, 
                 new_sl_price, new_tp_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ticket, symbol, timestamp_utc, h4_signal, h1_signal, m30_signal,
                  m15_signal, m5_signal, m1_signal, exit_action, exit_percentage,
                  new_sl_price, new_tp_price))
            self.connection.commit()
        except Exception as e:
            logger.error(f"Error inserting DTMS exit: {e}")
            
    def insert_binance_orderbook(self, symbol: str, timestamp_utc: int, bid_price: float,
                                ask_price: float, bid_volume: float, ask_volume: float,
                                spread: float, depth_data: Dict[str, Any]):
        """Insert Binance order book data (context only)"""
        try:
            self.connection.execute("""
                INSERT INTO binance_orderbook 
                (symbol, timestamp_utc, bid_price, ask_price, bid_volume, ask_volume, 
                 spread, depth_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, timestamp_utc, bid_price, ask_price, bid_volume, ask_volume,
                  spread, json.dumps(depth_data)))
            self.connection.commit()
        except Exception as e:
            logger.error(f"Error inserting Binance order book: {e}")
            
    def insert_hot_path_metrics(self, symbol: str, stage: str, timestamp_utc: int,
                               latency_ms: float, queue_depth: int, memory_mb: float):
        """Insert hot path performance metrics"""
        try:
            self.connection.execute("""
                INSERT INTO hot_path_metrics 
                (symbol, stage, timestamp_utc, latency_ms, queue_depth, memory_mb)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (symbol, stage, timestamp_utc, latency_ms, queue_depth, memory_mb))
            self.connection.commit()
        except Exception as e:
            logger.error(f"Error inserting hot path metrics: {e}")
            
    def get_latest_structure(self, symbol: str, timeframe: str, limit: int = 10):
        """Get latest structure analysis for symbol/timeframe"""
        try:
            cursor = self.connection.execute("""
                SELECT * FROM mtf_structure_analysis 
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp_utc DESC LIMIT ?
            """, (symbol, timeframe, limit))
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting latest structure: {e}")
            return []
            
    def get_latest_m1_filters(self, symbol: str, limit: int = 10):
        """Get latest M1 filters for symbol"""
        try:
            cursor = self.connection.execute("""
                SELECT * FROM m1_precision_filters 
                WHERE symbol = ?
                ORDER BY timestamp_utc DESC LIMIT ?
            """, (symbol, limit))
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting latest M1 filters: {e}")
            return []
            
    def get_performance_metrics(self, symbol: str, timeframe: str, days: int = 7):
        """Get performance metrics for symbol/timeframe"""
        try:
            cutoff_time = int(datetime.now(timezone.utc).timestamp()) - (days * 24 * 3600)
            cursor = self.connection.execute("""
                SELECT * FROM mtf_performance_metrics 
                WHERE symbol = ? AND timeframe = ? AND date_utc >= ?
                ORDER BY date_utc DESC
            """, (symbol, timeframe, cutoff_time))
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return []
            
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old data based on retention policy"""
        try:
            cutoff_time = int(datetime.now(timezone.utc).timestamp()) - (days_to_keep * 24 * 3600)
            
            # Clean up old structure analysis (keep 30 days)
            self.connection.execute("""
                DELETE FROM mtf_structure_analysis 
                WHERE timestamp_utc < ?
            """, (cutoff_time,))
            
            # Clean up old M1 filters (keep 7 days)
            m1_cutoff = int(datetime.now(timezone.utc).timestamp()) - (7 * 24 * 3600)
            self.connection.execute("""
                DELETE FROM m1_precision_filters 
                WHERE timestamp_utc < ?
            """, (m1_cutoff,))
            
            # Clean up old hot path metrics (keep 3 days)
            hot_path_cutoff = int(datetime.now(timezone.utc).timestamp()) - (3 * 24 * 3600)
            self.connection.execute("""
                DELETE FROM hot_path_metrics 
                WHERE timestamp_utc < ?
            """, (hot_path_cutoff,))
            
            self.connection.commit()
            logger.info(f"Cleaned up data older than {days_to_keep} days")
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Example usage and testing
if __name__ == "__main__":
    # Test database schema
    with MTFDatabaseSchema("test_mtf.db") as db:
        # Test structure analysis insertion
        db.insert_structure_analysis(
            symbol="BTCUSDc",
            timeframe="H1", 
            timestamp_utc=int(datetime.now(timezone.utc).timestamp()),
            structure_type="BOS",
            structure_data={"price": 50000, "volume": 1000},
            confidence_score=0.85
        )
        
        # Test M1 filters insertion
        db.insert_m1_filters(
            symbol="BTCUSDc",
            timestamp_utc=int(datetime.now(timezone.utc).timestamp()),
            vwap_reclaim=True,
            delta_spike=True,
            micro_bos=False,
            atr_ratio_valid=True,
            spread_valid=True,
            filters_passed=4,
            filter_score=0.8
        )
        
        # Test trade decision insertion
        db.insert_trade_decision(
            symbol="BTCUSDc",
            timestamp_utc=int(datetime.now(timezone.utc).timestamp()),
            h4_bias="BULLISH",
            h1_bias="BULLISH", 
            m30_setup="BOS",
            m15_setup="OB_RETEST",
            m5_structure="BULLISH",
            m1_confirmation=True,
            decision="BUY",
            confidence=0.88,
            risk_reward=3.2
        )
        
        print("Database schema test completed successfully!")

