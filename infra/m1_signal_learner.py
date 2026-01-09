"""
Real-Time Signal Learning Module (Phase 2.2)

Stores signal outcomes and adjusts confidence weighting gradually (reinforcement bias tuning).
Allows the system to learn over time which combinations (symbol + session + confluence) perform best.
"""

from __future__ import annotations
import sqlite3
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import statistics

logger = logging.getLogger(__name__)


class RealTimeSignalLearner:
    """
    Real-Time Signal Learning System
    
    Stores signal outcomes with full context (symbol, session, confluence, volatility state, etc.)
    and provides analytics for adaptive threshold adjustment.
    """
    
    def __init__(self, db_path: str = "data/m1_signal_learning.db"):
        """
        Initialize the signal learner.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Connect to database
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        
        # Create tables
        self._create_tables()
        
        logger.info(f"RealTimeSignalLearner initialized with database: {self.db_path}")
    
    def _create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.conn.cursor()
        
        # Main signal outcomes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                symbol TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                session TEXT NOT NULL,
                confluence REAL NOT NULL,
                signal_outcome TEXT NOT NULL,
                rr_achieved REAL,
                
                -- Microstructure Memory Analytics Metrics:
                signal_to_execution_latency_ms REAL,
                detection_latency_ms REAL,
                initial_confidence REAL,
                confidence_decay REAL,
                signal_age_seconds REAL,
                execution_yield REAL,
                executed BOOLEAN DEFAULT 0,
                trade_id TEXT,
                
                -- Additional Analytics Fields:
                volatility_state TEXT,
                strategy_hint TEXT,
                confidence_volatility_correlation REAL,
                signal_detection_timestamp DATETIME,
                execution_timestamp DATETIME,
                base_confluence REAL,
                
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for fast queries
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_symbol_session ON signal_outcomes(symbol, session)",
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON signal_outcomes(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_session_outcome ON signal_outcomes(session, signal_outcome)",
            "CREATE INDEX IF NOT EXISTS idx_volatility_state ON signal_outcomes(volatility_state)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_hint ON signal_outcomes(strategy_hint)",
            "CREATE INDEX IF NOT EXISTS idx_symbol_outcome ON signal_outcomes(symbol, signal_outcome)",
            "CREATE INDEX IF NOT EXISTS idx_executed ON signal_outcomes(executed)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        self.conn.commit()
        logger.debug("Signal outcomes table and indexes created")
    
    def store_signal_outcome(
        self,
        symbol: str,
        session: str,
        confluence: float,
        signal_outcome: str,  # WIN, LOSS, BREAKEVEN, NO_TRADE
        event_type: str = "CHOCH",  # CHOCH, BOS, CHOCH_BOS_COMBO
        rr_achieved: Optional[float] = None,
        signal_detection_timestamp: Optional[datetime] = None,
        execution_timestamp: Optional[datetime] = None,
        base_confluence: Optional[float] = None,
        volatility_state: Optional[str] = None,
        strategy_hint: Optional[str] = None,
        initial_confidence: Optional[float] = None,
        confidence_decay: Optional[float] = None,
        signal_age_seconds: Optional[float] = None,
        executed: bool = False,
        trade_id: Optional[str] = None
    ) -> str:
        """
        Store a signal outcome with full context.
        
        Args:
            symbol: Trading symbol
            session: Trading session (ASIAN, LONDON, NY, OVERLAP, POST_NY)
            confluence: Confluence score at signal time (0-100)
            signal_outcome: Outcome (WIN, LOSS, BREAKEVEN, NO_TRADE)
            event_type: Type of event (CHOCH, BOS, CHOCH_BOS_COMBO)
            rr_achieved: Risk-to-reward ratio achieved (if executed)
            signal_detection_timestamp: When signal was first detected
            execution_timestamp: When trade was executed
            base_confluence: Original confluence score before adjustments
            volatility_state: Volatility state (CONTRACTING, EXPANDING, STABLE)
            strategy_hint: Strategy hint (RANGE_SCALP, BREAKOUT, etc.)
            initial_confidence: Initial confidence score
            confidence_decay: Change in confidence over time
            signal_age_seconds: Age of signal in seconds
            executed: Whether signal resulted in trade
            trade_id: Trade ID if executed
            
        Returns:
            event_id: Unique event identifier
        """
        try:
            event_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc)
            
            # Calculate signal-to-execution latency if both timestamps available
            signal_to_execution_latency_ms = None
            if signal_detection_timestamp and execution_timestamp:
                if isinstance(signal_detection_timestamp, str):
                    signal_detection_timestamp = datetime.fromisoformat(signal_detection_timestamp.replace('Z', '+00:00'))
                if isinstance(execution_timestamp, str):
                    execution_timestamp = datetime.fromisoformat(execution_timestamp.replace('Z', '+00:00'))
                
                delta = execution_timestamp - signal_detection_timestamp
                signal_to_execution_latency_ms = delta.total_seconds() * 1000
            
            # Normalize symbol
            symbol_norm = symbol.upper().rstrip('Cc') + 'c'
            
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO signal_outcomes (
                    event_id, symbol, event_type, timestamp, session, confluence,
                    signal_outcome, rr_achieved,
                    signal_to_execution_latency_ms, detection_latency_ms,
                    initial_confidence, confidence_decay, signal_age_seconds,
                    execution_yield, executed, trade_id,
                    volatility_state, strategy_hint, confidence_volatility_correlation,
                    signal_detection_timestamp, execution_timestamp, base_confluence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id, symbol_norm, event_type, timestamp, session, confluence,
                signal_outcome, rr_achieved,
                signal_to_execution_latency_ms, None,  # detection_latency_ms (calculated separately if needed)
                initial_confidence, confidence_decay, signal_age_seconds,
                None,  # execution_yield (calculated from aggregate data)
                executed, trade_id,
                volatility_state, strategy_hint, None,  # confidence_volatility_correlation (calculated separately)
                signal_detection_timestamp, execution_timestamp, base_confluence or confluence
            ))
            
            self.conn.commit()
            logger.debug(f"Stored signal outcome: {event_id} - {symbol_norm} - {signal_outcome}")
            return event_id
            
        except Exception as e:
            logger.error(f"Error storing signal outcome: {e}", exc_info=True)
            self.conn.rollback()
            raise
    
    def get_optimal_parameters(
        self,
        symbol: str,
        session: str,
        min_samples: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Get optimal parameters based on historical performance.
        
        Args:
            symbol: Trading symbol
            session: Trading session
            min_samples: Minimum number of samples required
            
        Returns:
            Dictionary with optimal parameters or None if insufficient data
        """
        try:
            symbol_norm = symbol.upper().rstrip('Cc') + 'c'
            
            cursor = self.conn.cursor()
            
            # Get win rate and average R:R for this symbol + session
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_signals,
                    SUM(CASE WHEN signal_outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                    AVG(CASE WHEN signal_outcome = 'WIN' THEN rr_achieved ELSE NULL END) as avg_rr_win,
                    AVG(confluence) as avg_confluence,
                    AVG(CASE WHEN executed = 1 THEN signal_to_execution_latency_ms ELSE NULL END) as avg_latency
                FROM signal_outcomes
                WHERE symbol = ? AND session = ?
            """, (symbol_norm, session))
            
            row = cursor.fetchone()
            if not row or row['total_signals'] < min_samples:
                return None
            
            total_signals = row['total_signals']
            wins = row['wins']
            win_rate = wins / total_signals if total_signals > 0 else 0
            avg_rr_win = row['avg_rr_win'] or 0
            avg_confluence = row['avg_confluence'] or 70
            avg_latency = row['avg_latency'] or 0
            
            # Calculate optimal confluence threshold based on performance
            # Learning algorithm:
            # - Win rate < 60% → increase threshold (be more selective)
            # - Win rate > 75% → decrease threshold (can be more aggressive)
            # - Avg R:R < 2.0 → increase threshold
            # - Avg R:R > 3.5 → decrease threshold
            
            base_threshold = avg_confluence
            adjustment = 0
            
            if win_rate < 0.60:
                adjustment += 5  # Increase threshold
            elif win_rate > 0.75:
                adjustment -= 3  # Decrease threshold
            
            if avg_rr_win > 0:
                if avg_rr_win < 2.0:
                    adjustment += 3
                elif avg_rr_win > 3.5:
                    adjustment -= 2
            
            optimal_threshold = max(50, min(95, base_threshold + adjustment))
            
            # Calculate session bias factor based on win rate
            # Higher win rate → can be more aggressive (lower bias = lower threshold multiplier)
            # Lower win rate → be more conservative (higher bias = higher threshold multiplier)
            if win_rate > 0.70:
                session_bias = 0.95  # Slightly more aggressive
            elif win_rate < 0.55:
                session_bias = 1.10  # More conservative
            else:
                session_bias = 1.0  # Neutral
            
            return {
                'optimal_confluence_threshold': optimal_threshold,
                'session_bias_factor': session_bias,
                'win_rate': win_rate,
                'avg_rr_win': avg_rr_win,
                'total_signals': total_signals,
                'avg_latency_ms': avg_latency,
                'confidence': min(100, int(win_rate * 100))  # Confidence in recommendations
            }
            
        except Exception as e:
            logger.error(f"Error getting optimal parameters: {e}", exc_info=True)
            return None
    
    def get_signal_to_execution_latency(
        self,
        symbol: str,
        session: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get average latency from signal detection to execution.
        
        Args:
            symbol: Trading symbol
            session: Optional session filter
            
        Returns:
            Dictionary with latency statistics
        """
        try:
            symbol_norm = symbol.upper().rstrip('Cc') + 'c'
            
            cursor = self.conn.cursor()
            
            if session:
                cursor.execute("""
                    SELECT 
                        AVG(signal_to_execution_latency_ms) as avg_latency,
                        MIN(signal_to_execution_latency_ms) as min_latency,
                        MAX(signal_to_execution_latency_ms) as max_latency,
                        COUNT(*) as count
                    FROM signal_outcomes
                    WHERE symbol = ? AND session = ? AND executed = 1 
                    AND signal_to_execution_latency_ms IS NOT NULL
                """, (symbol_norm, session))
            else:
                cursor.execute("""
                    SELECT 
                        AVG(signal_to_execution_latency_ms) as avg_latency,
                        MIN(signal_to_execution_latency_ms) as min_latency,
                        MAX(signal_to_execution_latency_ms) as max_latency,
                        COUNT(*) as count
                    FROM signal_outcomes
                    WHERE symbol = ? AND executed = 1 
                    AND signal_to_execution_latency_ms IS NOT NULL
                """, (symbol_norm,))
            
            row = cursor.fetchone()
            if not row or row['count'] == 0:
                return {'avg_latency_ms': 0, 'min_latency_ms': 0, 'max_latency_ms': 0, 'count': 0}
            
            return {
                'avg_latency_ms': row['avg_latency'] or 0,
                'min_latency_ms': row['min_latency'] or 0,
                'max_latency_ms': row['max_latency'] or 0,
                'count': row['count']
            }
            
        except Exception as e:
            logger.error(f"Error getting signal-to-execution latency: {e}", exc_info=True)
            return {'avg_latency_ms': 0, 'min_latency_ms': 0, 'max_latency_ms': 0, 'count': 0}
    
    def get_success_rate_by_session(self, symbol: str) -> Dict[str, float]:
        """
        Get win rate broken down by session.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary mapping session to win rate
        """
        try:
            symbol_norm = symbol.upper().rstrip('Cc') + 'c'
            
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT 
                    session,
                    COUNT(*) as total,
                    SUM(CASE WHEN signal_outcome = 'WIN' THEN 1 ELSE 0 END) as wins
                FROM signal_outcomes
                WHERE symbol = ?
                GROUP BY session
            """, (symbol_norm,))
            
            results = {}
            for row in cursor.fetchall():
                total = row['total']
                wins = row['wins']
                win_rate = wins / total if total > 0 else 0
                results[row['session']] = win_rate
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting success rate by session: {e}", exc_info=True)
            return {}
    
    def get_confidence_volatility_correlation(self, symbol: str) -> float:
        """
        Get correlation coefficient between confidence scores and volatility states.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Correlation coefficient (-1 to 1)
        """
        try:
            symbol_norm = symbol.upper().rstrip('Cc') + 'c'
            
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT initial_confidence, volatility_state
                FROM signal_outcomes
                WHERE symbol = ? 
                AND initial_confidence IS NOT NULL 
                AND volatility_state IS NOT NULL
            """, (symbol_norm,))
            
            rows = cursor.fetchall()
            if len(rows) < 10:  # Need minimum samples for correlation
                return 0.0
            
            # Map volatility states to numeric values
            volatility_map = {'CONTRACTING': 1, 'STABLE': 2, 'EXPANDING': 3}
            
            confidences = []
            volatilities = []
            
            for row in rows:
                confidences.append(row['initial_confidence'])
                volatilities.append(volatility_map.get(row['volatility_state'], 2))
            
            if len(confidences) < 2:
                return 0.0
            
            # Calculate correlation coefficient
            try:
                correlation = statistics.correlation(confidences, volatilities)
                return correlation
            except:
                # Fallback to simple calculation if statistics.correlation not available
                return 0.0
            
        except Exception as e:
            logger.error(f"Error getting confidence-volatility correlation: {e}", exc_info=True)
            return 0.0
    
    def re_evaluate_metrics(self, symbol: str) -> Dict[str, Any]:
        """
        Re-evaluate all metrics and produce adaptive calibration recommendations.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with all metrics and recommendations
        """
        try:
            latency_stats = self.get_signal_to_execution_latency(symbol)
            success_by_session = self.get_success_rate_by_session(symbol)
            confidence_volatility_corr = self.get_confidence_volatility_correlation(symbol)
            
            # Generate recommendations
            recommendations = {}
            
            # Latency optimization
            if latency_stats['avg_latency_ms'] > 5000:  # > 5 seconds
                recommendations['latency'] = "Consider optimizing execution timing"
            
            # Session-specific adjustments
            for session, win_rate in success_by_session.items():
                if win_rate < 0.55:
                    recommendations[f'session_{session}'] = f"Increase threshold for {session} (win rate: {win_rate:.1%})"
                elif win_rate > 0.75:
                    recommendations[f'session_{session}'] = f"Can decrease threshold for {session} (win rate: {win_rate:.1%})"
            
            # Confidence-volatility correlation validation
            if abs(confidence_volatility_corr) < 0.3:
                recommendations['confidence_scaling'] = "Confidence may not scale appropriately with volatility"
            
            return {
                'signal_to_execution_latency_avg': latency_stats['avg_latency_ms'],
                'success_rate_by_session': success_by_session,
                'confidence_volatility_correlation': confidence_volatility_corr,
                'recommended_adjustments': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error re-evaluating metrics: {e}", exc_info=True)
            return {}
    
    def cleanup_old_data(self, days: int = 90):
        """
        Clean up old data to prevent database bloat.
        
        Args:
            days: Number of days to keep
        """
        try:
            cursor = self.conn.cursor()
            cutoff_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            from datetime import timedelta
            cutoff_date = cutoff_date - timedelta(days=days)
            
            cursor.execute("""
                DELETE FROM signal_outcomes
                WHERE timestamp < ?
            """, (cutoff_date,))
            
            deleted = cursor.rowcount
            self.conn.commit()
            
            logger.info(f"Cleaned up {deleted} old signal outcomes (older than {days} days)")
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}", exc_info=True)
            self.conn.rollback()
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.debug("Signal learner database connection closed")

