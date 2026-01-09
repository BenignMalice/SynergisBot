"""
Tick Metrics Cache

Dual-layer caching: in-memory (fast) + SQLite (persistent).
Provides fast retrieval with crash recovery capability.
"""
import logging
import sqlite3
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import time

logger = logging.getLogger(__name__)


@dataclass
class CachedTickMetrics:
    """In-memory cache entry."""
    symbol: str
    timestamp: datetime
    expires_at: datetime
    metrics: Dict[str, Any]


class TickMetricsCache:
    """Dual-layer cache: memory + SQLite persistence."""
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        memory_ttl_seconds: int = 60,
        db_retention_hours: int = 24
    ):
        """
        Initialize cache.
        
        Args:
            db_path: Path to SQLite database (default: data/unified_tick_pipeline/tick_metrics_cache.db)
            memory_ttl_seconds: Memory cache TTL in seconds (default: 60)
            db_retention_hours: SQLite retention in hours (default: 24)
        """
        self.db_path = Path(db_path or "data/unified_tick_pipeline/tick_metrics_cache.db")
        
        # Ensure directory exists (unified_tick_pipeline may not exist if disabled)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.memory_ttl = memory_ttl_seconds
        self.db_retention_hours = db_retention_hours
        
        # In-memory cache (thread-safe)
        self._memory_cache: Dict[str, CachedTickMetrics] = {}
        self._cache_lock = threading.Lock()
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database with schema."""
        try:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA cache_size=-100000")  # 100MB cache
            cursor.execute("PRAGMA busy_timeout=5000")
            
            # Create table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tick_metrics_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timestamp)
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tick_metrics_symbol 
                ON tick_metrics_cache(symbol)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tick_metrics_expires 
                ON tick_metrics_cache(expires_at)
            """)
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Tick metrics cache database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing tick metrics cache database: {e}", exc_info=True)
            raise
    
    def get(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get metrics from cache (memory first, fallback to SQLite).
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Metrics dictionary or None if not found/expired
        """
        # Try memory cache first
        with self._cache_lock:
            cached = self._memory_cache.get(symbol)
            if cached:
                if datetime.utcnow() < cached.expires_at:
                    return cached.metrics
                else:
                    # Expired, remove from memory
                    del self._memory_cache[symbol]
        
        # Fallback to SQLite
        return self.get_from_db(symbol)
    
    def set(self, symbol: str, metrics: Dict[str, Any]):
        """
        Store metrics in both memory and SQLite.
        
        Args:
            symbol: Trading symbol
            metrics: Metrics dictionary
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=self.memory_ttl)
        db_expires_at = now + timedelta(hours=self.db_retention_hours)
        
        # Store in memory
        with self._cache_lock:
            self._memory_cache[symbol] = CachedTickMetrics(
                symbol=symbol,
                timestamp=now,
                expires_at=expires_at,
                metrics=metrics
            )
        
        # Store in SQLite
        try:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            
            timestamp_str = now.isoformat()
            expires_str = db_expires_at.isoformat()
            metrics_json = json.dumps(metrics)
            
            cursor.execute("""
                INSERT OR REPLACE INTO tick_metrics_cache 
                (symbol, timestamp, expires_at, metrics_json)
                VALUES (?, ?, ?, ?)
            """, (symbol, timestamp_str, expires_str, metrics_json))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing metrics in SQLite for {symbol}: {e}", exc_info=True)
    
    def get_from_db(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get metrics from SQLite database.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Metrics dictionary or None if not found/expired
        """
        try:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            
            now_str = datetime.utcnow().isoformat()
            
            cursor.execute("""
                SELECT metrics_json, expires_at
                FROM tick_metrics_cache
                WHERE symbol = ? AND expires_at > ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (symbol, now_str))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                metrics_json, expires_at = row
                metrics = json.loads(metrics_json)
                
                # Also update memory cache
                expires_dt = datetime.fromisoformat(expires_at)
                with self._cache_lock:
                    self._memory_cache[symbol] = CachedTickMetrics(
                        symbol=symbol,
                        timestamp=datetime.utcnow(),
                        expires_at=expires_dt,
                        metrics=metrics
                    )
                
                return metrics
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving metrics from SQLite for {symbol}: {e}", exc_info=True)
            return None
    
    def cleanup_expired(self):
        """Remove expired entries from SQLite database."""
        try:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            
            now_str = datetime.utcnow().isoformat()
            
            cursor.execute("""
                DELETE FROM tick_metrics_cache
                WHERE expires_at < ?
            """, (now_str,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                logger.debug(f"Cleaned up {deleted_count} expired tick metrics cache entries")
            
        except Exception as e:
            logger.error(f"Error cleaning up expired cache entries: {e}", exc_info=True)
    
    def get_historical(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Query historical metrics for debugging/analysis.
        
        Args:
            symbol: Trading symbol
            start_time: Start datetime
            end_time: End datetime
        
        Returns:
            List of metrics dictionaries
        """
        try:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            
            start_str = start_time.isoformat()
            end_str = end_time.isoformat()
            
            cursor.execute("""
                SELECT metrics_json, timestamp
                FROM tick_metrics_cache
                WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
            """, (symbol, start_str, end_str))
            
            rows = cursor.fetchall()
            conn.close()
            
            results = []
            for row in rows:
                metrics_json, timestamp = row
                metrics = json.loads(metrics_json)
                results.append({
                    'timestamp': timestamp,
                    'metrics': metrics
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error querying historical metrics for {symbol}: {e}", exc_info=True)
            return []

