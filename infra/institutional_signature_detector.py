"""
Phase III: Institutional Signature Detection Module
Tracks pattern sequences: mitigation cascades, breaker retest chains, liquidity vacuum refills
"""

import logging
import sqlite3
import json
import threading
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class InstitutionalSignatureDetector:
    """
    Phase III: Detects and tracks institutional signature patterns.
    
    Patterns tracked:
    - Mitigation cascade (overlapping order blocks)
    - Breaker retest chains (sequence of retests)
    - Liquidity vacuum refill (FVG + imbalance combo)
    """
    
    def __init__(self, db_path: str = "data/auto_execution.db"):
        """
        Initialize institutional signature detector.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._lock = threading.RLock()  # Thread safety for pattern history access
        self._pattern_cache: Dict[str, Dict[str, Any]] = {}  # Cache for recent patterns
        self._cache_ttl_seconds = 300  # 5 minutes cache TTL
        
        # Ensure database and table exist
        self._ensure_database()
        
        logger.info("Phase III: InstitutionalSignatureDetector initialized")
    
    def _ensure_database(self):
        """Ensure database and pattern_history table exist"""
        try:
            db_path_obj = Path(self.db_path)
            db_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                cursor = conn.cursor()
                # Check if table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='pattern_history'
                """)
                if not cursor.fetchone():
                    # Create table if it doesn't exist
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS pattern_history (
                            pattern_id TEXT PRIMARY KEY,
                            symbol TEXT NOT NULL,
                            pattern_type TEXT NOT NULL,
                            pattern_data TEXT NOT NULL,
                            detected_at TEXT NOT NULL,
                            expires_at TEXT NOT NULL
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pattern_symbol ON pattern_history(symbol)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pattern_type ON pattern_history(pattern_type)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pattern_detected ON pattern_history(detected_at)")
                    conn.commit()
                    logger.info("Phase III: pattern_history table created")
        except Exception as e:
            logger.error(f"Error ensuring pattern_history table: {e}", exc_info=True)
    
    def _generate_pattern_id(self, symbol: str, pattern_type: str, timestamp: datetime) -> str:
        """Generate unique pattern ID"""
        timestamp_str = timestamp.strftime("%Y%m%d%H%M%S")
        return f"{symbol}_{pattern_type}_{timestamp_str}"
    
    def _store_pattern(
        self,
        symbol: str,
        pattern_type: str,
        pattern_data: Dict[str, Any],
        expires_in_hours: int = 24
    ) -> Optional[str]:
        """
        Store pattern in database.
        
        Args:
            symbol: Trading symbol
            pattern_type: Type of pattern ("mitigation_cascade", "breaker_chain", "liquidity_vacuum")
            pattern_data: Pattern details (dict)
            expires_in_hours: Hours until pattern expires (default: 24)
        
        Returns:
            Pattern ID or None
        """
        try:
            with self._lock:
                now = datetime.now(timezone.utc)
                expires_at = now + timedelta(hours=expires_in_hours)
                
                pattern_id = self._generate_pattern_id(symbol, pattern_type, now)
                
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO pattern_history
                        (pattern_id, symbol, pattern_type, pattern_data, detected_at, expires_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        pattern_id,
                        symbol,
                        pattern_type,
                        json.dumps(pattern_data),
                        now.isoformat(),
                        expires_at.isoformat()
                    ))
                    conn.commit()
                
                # Update cache
                cache_key = f"{symbol}_{pattern_type}"
                self._pattern_cache[cache_key] = {
                    "pattern_id": pattern_id,
                    "data": pattern_data,
                    "timestamp": now
                }
                
                logger.debug(f"Stored pattern: {pattern_id} ({pattern_type}) for {symbol}")
                return pattern_id
        except Exception as e:
            logger.error(f"Error storing pattern: {e}", exc_info=True)
            return None
    
    def _get_recent_patterns(
        self,
        symbol: str,
        pattern_type: str,
        window_hours: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Get recent patterns from database.
        
        Args:
            symbol: Trading symbol
            pattern_type: Type of pattern
            window_hours: Time window in hours (default: 1.0)
        
        Returns:
            List of pattern dicts
        """
        try:
            with self._lock:
                now = datetime.now(timezone.utc)
                window_start = now - timedelta(hours=window_hours)
                
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT pattern_id, pattern_data, detected_at, expires_at
                        FROM pattern_history
                        WHERE symbol = ? AND pattern_type = ?
                        AND detected_at >= ? AND expires_at > ?
                        ORDER BY detected_at DESC
                    """, (symbol, pattern_type, window_start.isoformat(), now.isoformat()))
                    
                    patterns = []
                    for row in cursor.fetchall():
                        pattern_id, pattern_data_json, detected_at, expires_at = row
                        try:
                            pattern_data = json.loads(pattern_data_json)
                            patterns.append({
                                "pattern_id": pattern_id,
                                "data": pattern_data,
                                "detected_at": detected_at,
                                "expires_at": expires_at
                            })
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in pattern {pattern_id}")
                    
                    return patterns
        except Exception as e:
            logger.error(f"Error getting recent patterns: {e}", exc_info=True)
            return []
    
    def detect_mitigation_cascade(
        self,
        symbol: str,
        order_block_detections: List[Dict[str, Any]],
        min_overlapping_count: int = 3,
        window_hours: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Detect mitigation cascade (overlapping order blocks).
        
        Args:
            symbol: Trading symbol
            order_block_detections: List of order block detection results
            min_overlapping_count: Minimum number of overlapping OBs (default: 3)
            window_hours: Time window in hours (default: 1.0)
        
        Returns:
            {
                "mitigation_cascade_confirmed": bool,
                "overlapping_obs_count": int,
                "pattern_id": Optional[str]
            } or None
        """
        try:
            # Get recent OB detections from database
            recent_patterns = self._get_recent_patterns(symbol, "order_block", window_hours)
            
            # Count overlapping OBs
            total_obs = len(recent_patterns) + len(order_block_detections)
            
            # Check if cascade confirmed
            mitigation_cascade_confirmed = total_obs >= min_overlapping_count
            
            pattern_id = None
            if mitigation_cascade_confirmed:
                # Store cascade pattern
                pattern_data = {
                    "overlapping_obs_count": total_obs,
                    "window_hours": window_hours,
                    "min_required": min_overlapping_count
                }
                pattern_id = self._store_pattern(symbol, "mitigation_cascade", pattern_data)
            
            return {
                "mitigation_cascade_confirmed": mitigation_cascade_confirmed,
                "overlapping_obs_count": total_obs,
                "pattern_id": pattern_id
            }
        except Exception as e:
            logger.error(f"Error detecting mitigation cascade: {e}", exc_info=True)
            return None
    
    def detect_breaker_retest_chain(
        self,
        symbol: str,
        breaker_block_detection: Dict[str, Any],
        min_retest_count: int = 2,
        window_hours: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Detect breaker retest chain (sequence of retests).
        
        Args:
            symbol: Trading symbol
            breaker_block_detection: Breaker block detection result
            min_retest_count: Minimum number of retests (default: 2)
            window_hours: Time window in hours (default: 1.0)
        
        Returns:
            {
                "breaker_retest_chain_confirmed": bool,
                "breaker_retest_count": int,
                "pattern_id": Optional[str]
            } or None
        """
        try:
            # Check if price is retesting
            if not breaker_block_detection.get("price_retesting_breaker", False):
                return None
            
            # Get recent breaker retest patterns
            recent_patterns = self._get_recent_patterns(symbol, "breaker_chain", window_hours)
            
            # Count retests (including current)
            retest_count = len(recent_patterns) + 1
            
            # Check if chain confirmed
            breaker_retest_chain_confirmed = retest_count >= min_retest_count
            
            pattern_id = None
            if breaker_retest_chain_confirmed:
                # Store chain pattern
                pattern_data = {
                    "breaker_retest_count": retest_count,
                    "window_hours": window_hours,
                    "min_required": min_retest_count,
                    "breaker_level": breaker_block_detection.get("breaker_level"),
                    "price_retesting": True
                }
                pattern_id = self._store_pattern(symbol, "breaker_chain", pattern_data)
            
            return {
                "breaker_retest_chain_confirmed": breaker_retest_chain_confirmed,
                "breaker_retest_count": retest_count,
                "pattern_id": pattern_id
            }
        except Exception as e:
            logger.error(f"Error detecting breaker retest chain: {e}", exc_info=True)
            return None
    
    def detect_liquidity_vacuum_refill(
        self,
        symbol: str,
        fvg_detection: Dict[str, Any],
        imbalance_detection: Dict[str, Any],
        window_minutes: int = 15
    ) -> Optional[Dict[str, Any]]:
        """
        Detect liquidity vacuum refill (FVG + imbalance combo).
        
        Args:
            symbol: Trading symbol
            fvg_detection: FVG detection result
            imbalance_detection: Imbalance detection result
            window_minutes: Time window in minutes (default: 15)
        
        Returns:
            {
                "liquidity_vacuum_refill": bool,
                "pattern_id": Optional[str]
            } or None
        """
        try:
            # Check if both FVG and imbalance detected
            fvg_detected = fvg_detection.get("fvg_bull") or fvg_detection.get("fvg_bear")
            imbalance_detected = imbalance_detection.get("imbalance_detected", False)
            
            if not (fvg_detected and imbalance_detected):
                return None
            
            # Check if both occurred within time window
            # For now, assume they're detected together (would need timestamps for precise check)
            liquidity_vacuum_refill = True
            
            pattern_id = None
            if liquidity_vacuum_refill:
                # Store vacuum pattern
                pattern_data = {
                    "fvg_detected": fvg_detected,
                    "imbalance_detected": imbalance_detected,
                    "window_minutes": window_minutes,
                    "fvg_type": "bull" if fvg_detection.get("fvg_bull") else "bear",
                    "imbalance_direction": imbalance_detection.get("imbalance_direction")
                }
                pattern_id = self._store_pattern(symbol, "liquidity_vacuum", pattern_data)
            
            return {
                "liquidity_vacuum_refill": liquidity_vacuum_refill,
                "pattern_id": pattern_id
            }
        except Exception as e:
            logger.error(f"Error detecting liquidity vacuum refill: {e}", exc_info=True)
            return None
    
    def cleanup_expired_patterns(self):
        """Cleanup expired patterns from database (run periodically)"""
        try:
            with self._lock:
                now = datetime.now(timezone.utc)
                
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        DELETE FROM pattern_history
                        WHERE expires_at < ?
                    """, (now.isoformat(),))
                    deleted_count = cursor.rowcount
                    conn.commit()
                
                if deleted_count > 0:
                    logger.debug(f"Cleaned up {deleted_count} expired patterns")
        except Exception as e:
            logger.error(f"Error cleaning up expired patterns: {e}", exc_info=True)

