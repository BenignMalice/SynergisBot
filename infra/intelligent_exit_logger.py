"""
Intelligent Exit Logger - Database logging for all intelligent exit actions.
Logs: breakeven, partial profits, trailing stops, hybrid adjustments, etc.
"""

import sqlite3
import time
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class IntelligentExitLogger:
    """
    Logs all intelligent exit management actions to SQLite database.
    
    Table: intelligent_exit_actions
    - id: Auto-increment primary key
    - timestamp: Action timestamp
    - ticket: MT5 position ticket
    - symbol: Trading symbol
    - action_type: breakeven, partial_profit, trailing_stop, hybrid_adjustment, rule_added, rule_removed
    - old_sl: Previous stop loss
    - new_sl: New stop loss
    - old_tp: Previous take profit (for partial profits)
    - new_tp: New take profit
    - volume_closed: Volume closed (for partial profits)
    - volume_remaining: Volume remaining after partial
    - profit_realized: Profit realized (for partial profits)
    - profit_pct: Percentage of potential profit achieved
    - r_achieved: R-multiple achieved
    - atr_value: ATR value (for trailing stops)
    - vix_value: VIX value (for hybrid adjustments)
    - details: JSON with additional details
    - success: Boolean success flag
    - error_message: Error message if failed
    """
    
    def __init__(self, db_path: str = "./data/journal.sqlite"):
        """Initialize logger with database path"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"IntelligentExitLogger initialized with database: {self.db_path}")
    
    def _init_db(self):
        """Create table if it doesn't exist"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS intelligent_exit_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    ticket INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    old_sl REAL,
                    new_sl REAL,
                    old_tp REAL,
                    new_tp REAL,
                    volume_closed REAL,
                    volume_remaining REAL,
                    profit_realized REAL,
                    profit_pct REAL,
                    r_achieved REAL,
                    atr_value REAL,
                    vix_value REAL,
                    details TEXT,
                    success INTEGER DEFAULT 1,
                    error_message TEXT
                )
            """)
            
            # Create indexes for efficient queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_exit_ticket 
                ON intelligent_exit_actions(ticket)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_exit_timestamp 
                ON intelligent_exit_actions(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_exit_symbol 
                ON intelligent_exit_actions(symbol)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_exit_action_type 
                ON intelligent_exit_actions(action_type)
            """)
            
            conn.commit()
            conn.close()
            logger.info("Intelligent exit actions table initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
    
    def log_action(
        self,
        ticket: int,
        symbol: str,
        action_type: str,
        old_sl: Optional[float] = None,
        new_sl: Optional[float] = None,
        old_tp: Optional[float] = None,
        new_tp: Optional[float] = None,
        volume_closed: Optional[float] = None,
        volume_remaining: Optional[float] = None,
        profit_realized: Optional[float] = None,
        profit_pct: Optional[float] = None,
        r_achieved: Optional[float] = None,
        atr_value: Optional[float] = None,
        vix_value: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> Optional[int]:
        """
        Log an intelligent exit action to the database.
        
        Args:
            ticket: MT5 position ticket
            symbol: Trading symbol
            action_type: Type of action (breakeven, partial_profit, trailing_stop, hybrid_adjustment, etc.)
            old_sl: Previous stop loss level
            new_sl: New stop loss level
            old_tp: Previous take profit level
            new_tp: New take profit level
            volume_closed: Volume closed (for partial profits)
            volume_remaining: Volume remaining
            profit_realized: Profit amount realized
            profit_pct: Percentage of potential profit achieved
            r_achieved: R-multiple achieved
            atr_value: ATR value used
            vix_value: VIX value used
            details: Additional details as dict
            success: Whether the action succeeded
            error_message: Error message if failed
            
        Returns:
            Action ID if successful, None otherwise
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Convert details dict to JSON string
            details_json = json.dumps(details) if details else None
            
            cursor.execute("""
                INSERT INTO intelligent_exit_actions (
                    timestamp, ticket, symbol, action_type,
                    old_sl, new_sl, old_tp, new_tp,
                    volume_closed, volume_remaining,
                    profit_realized, profit_pct, r_achieved,
                    atr_value, vix_value, details,
                    success, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(time.time()),
                ticket,
                symbol,
                action_type,
                old_sl,
                new_sl,
                old_tp,
                new_tp,
                volume_closed,
                volume_remaining,
                profit_realized,
                profit_pct,
                r_achieved,
                atr_value,
                vix_value,
                details_json,
                1 if success else 0,
                error_message
            ))
            
            action_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.debug(f"Logged {action_type} action for ticket {ticket}: ID {action_id}")
            return action_id
            
        except Exception as e:
            logger.error(f"Failed to log action: {e}", exc_info=True)
            return None
    
    def get_actions_for_ticket(
        self,
        ticket: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all actions for a specific ticket.
        
        Args:
            ticket: MT5 position ticket
            limit: Optional limit on number of results
            
        Returns:
            List of action dictionaries
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM intelligent_exit_actions
                WHERE ticket = ?
                ORDER BY timestamp DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query, (ticket,))
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get actions for ticket {ticket}: {e}", exc_info=True)
            return []
    
    def get_recent_actions(
        self,
        hours: int = 24,
        action_type: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent actions within the specified time window.
        
        Args:
            hours: Number of hours to look back
            action_type: Optional filter by action type
            symbol: Optional filter by symbol
            
        Returns:
            List of action dictionaries
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            since_ts = int(time.time()) - (hours * 3600)
            
            query = "SELECT * FROM intelligent_exit_actions WHERE timestamp >= ?"
            params = [since_ts]
            
            if action_type:
                query += " AND action_type = ?"
                params.append(action_type)
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            query += " ORDER BY timestamp DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get recent actions: {e}", exc_info=True)
            return []
    
    def get_statistics(
        self,
        symbol: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get statistics on intelligent exit actions.
        
        Args:
            symbol: Optional filter by symbol
            days: Number of days to analyze
            
        Returns:
            Dictionary with statistics
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            since_ts = int(time.time()) - (days * 86400)
            
            # Base query
            where_clause = "WHERE timestamp >= ?"
            params = [since_ts]
            
            if symbol:
                where_clause += " AND symbol = ?"
                params.append(symbol)
            
            # Count by action type
            cursor.execute(f"""
                SELECT action_type, COUNT(*) as count
                FROM intelligent_exit_actions
                {where_clause}
                GROUP BY action_type
            """, params)
            
            action_counts = {row['action_type']: row['count'] for row in cursor.fetchall()}
            
            # Average R achieved for breakeven
            cursor.execute(f"""
                SELECT AVG(r_achieved) as avg_r
                FROM intelligent_exit_actions
                {where_clause} AND action_type = 'breakeven' AND r_achieved IS NOT NULL
            """, params)
            
            avg_r_breakeven = cursor.fetchone()['avg_r']
            
            # Average profit % for partial profits
            cursor.execute(f"""
                SELECT AVG(profit_pct) as avg_pct, SUM(profit_realized) as total_profit
                FROM intelligent_exit_actions
                {where_clause} AND action_type = 'partial_profit' AND profit_realized IS NOT NULL
            """, params)
            
            partial_stats = cursor.fetchone()
            
            # Trailing stop adjustments
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total_adjustments,
                    AVG(new_sl - old_sl) as avg_adjustment
                FROM intelligent_exit_actions
                {where_clause} AND action_type = 'trailing_stop' AND old_sl IS NOT NULL AND new_sl IS NOT NULL
            """, params)
            
            trailing_stats = cursor.fetchone()
            
            # Success rate
            cursor.execute(f"""
                SELECT 
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                    COUNT(*) as total
                FROM intelligent_exit_actions
                {where_clause}
            """, params)
            
            success_stats = cursor.fetchone()
            success_rate = (success_stats['successes'] / success_stats['total'] * 100) if success_stats['total'] > 0 else 0
            
            conn.close()
            
            return {
                "period_days": days,
                "symbol": symbol or "ALL",
                "action_counts": action_counts,
                "total_actions": sum(action_counts.values()),
                "breakeven": {
                    "count": action_counts.get("breakeven", 0),
                    "avg_r_achieved": round(avg_r_breakeven, 3) if avg_r_breakeven else None
                },
                "partial_profits": {
                    "count": action_counts.get("partial_profit", 0),
                    "avg_profit_pct": round(partial_stats['avg_pct'], 2) if partial_stats['avg_pct'] else None,
                    "total_profit_realized": round(partial_stats['total_profit'], 2) if partial_stats['total_profit'] else 0
                },
                "trailing_stops": {
                    "count": action_counts.get("trailing_stop", 0),
                    "total_adjustments": trailing_stats['total_adjustments'],
                    "avg_adjustment": round(trailing_stats['avg_adjustment'], 5) if trailing_stats['avg_adjustment'] else None
                },
                "hybrid_adjustments": {
                    "count": action_counts.get("hybrid_adjustment", 0)
                },
                "success_rate": round(success_rate, 2),
                "total_successes": success_stats['successes'],
                "total_failures": success_stats['total'] - success_stats['successes']
            }
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            return {}
    
    def format_action_for_display(self, action: Dict[str, Any]) -> str:
        """Format an action for human-readable display"""
        try:
            timestamp = datetime.fromtimestamp(action['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            action_type = action['action_type'].replace('_', ' ').title()
            
            msg = f"[{timestamp}] {action_type}\n"
            msg += f"  Ticket: {action['ticket']} | Symbol: {action['symbol']}\n"
            
            if action['old_sl'] and action['new_sl']:
                msg += f"  SL: {action['old_sl']:.5f} -> {action['new_sl']:.5f}\n"
            
            if action['volume_closed']:
                msg += f"  Volume Closed: {action['volume_closed']:.2f} lots\n"
            
            if action['profit_realized']:
                msg += f"  Profit Realized: ${action['profit_realized']:.2f}\n"
            
            if action['profit_pct']:
                msg += f"  Profit %: {action['profit_pct']:.1f}%\n"
            
            if action['r_achieved']:
                msg += f"  R Achieved: {action['r_achieved']:.2f}R\n"
            
            if action['atr_value']:
                msg += f"  ATR: {action['atr_value']:.5f}\n"
            
            if action['vix_value']:
                msg += f"  VIX: {action['vix_value']:.2f}\n"
            
            if not action['success'] and action['error_message']:
                msg += f"  ERROR: {action['error_message']}\n"
            
            return msg
            
        except Exception as e:
            return f"Error formatting action: {e}"


# Global instance
_exit_logger = None


def get_exit_logger(db_path: str = "./data/journal.sqlite") -> IntelligentExitLogger:
    """Get or create the global exit logger instance"""
    global _exit_logger
    if _exit_logger is None:
        _exit_logger = IntelligentExitLogger(db_path)
    return _exit_logger

