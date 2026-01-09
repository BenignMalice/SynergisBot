"""
Recommendation Tracker - Track ChatGPT recommendations and their outcomes
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


class RecommendationTracker:
    """Track ChatGPT trade recommendations and their outcomes"""
    
    def __init__(self, db_path: str = "data/recommendations.sqlite"):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        """Create database and tables if they don't exist"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Recommendations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                confidence INTEGER NOT NULL,
                reasoning TEXT,
                order_type TEXT,
                timeframe TEXT,
                market_regime TEXT,
                session TEXT,
                confluence_score REAL,
                
                -- Outcome tracking
                executed INTEGER DEFAULT 0,
                execution_time TEXT,
                mt5_ticket INTEGER,
                outcome TEXT,
                exit_price REAL,
                exit_time TEXT,
                profit_loss REAL,
                risk_reward_achieved REAL,
                hold_time_minutes INTEGER,
                
                -- Metadata
                user_id INTEGER,
                conversation_id TEXT
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol ON recommendations(symbol)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trade_type ON recommendations(trade_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_outcome ON recommendations(outcome)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON recommendations(timestamp)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"RecommendationTracker initialized with database: {self.db_path}")
    
    def log_recommendation(
        self,
        symbol: str,
        trade_type: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        confidence: int,
        reasoning: str = "",
        order_type: str = "market",
        timeframe: str = "",
        market_regime: str = "",
        session: str = "",
        confluence_score: float = None,
        user_id: int = None,
        conversation_id: str = None
    ) -> int:
        """
        Log a new recommendation
        
        Returns:
            recommendation_id: ID of the logged recommendation
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO recommendations (
                timestamp, symbol, trade_type, direction, entry_price,
                stop_loss, take_profit, confidence, reasoning, order_type,
                timeframe, market_regime, session, confluence_score,
                user_id, conversation_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            symbol.upper(),
            trade_type.lower(),
            direction.lower(),
            entry_price,
            stop_loss,
            take_profit,
            confidence,
            reasoning,
            order_type.lower(),
            timeframe,
            market_regime,
            session,
            confluence_score,
            user_id,
            conversation_id
        ))
        
        recommendation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Logged recommendation #{recommendation_id}: {symbol} {direction} @ {entry_price}")
        return recommendation_id
    
    def mark_executed(
        self,
        recommendation_id: int,
        mt5_ticket: int,
        execution_time: datetime = None
    ):
        """Mark a recommendation as executed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE recommendations
            SET executed = 1,
                execution_time = ?,
                mt5_ticket = ?
            WHERE id = ?
        """, (
            (execution_time or datetime.utcnow()).isoformat(),
            mt5_ticket,
            recommendation_id
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Marked recommendation #{recommendation_id} as executed (ticket: {mt5_ticket})")
    
    def update_outcome(
        self,
        recommendation_id: int = None,
        mt5_ticket: int = None,
        outcome: str = None,
        exit_price: float = None,
        exit_time: datetime = None,
        profit_loss: float = None
    ):
        """
        Update recommendation outcome
        
        Args:
            recommendation_id: Recommendation ID (if known)
            mt5_ticket: MT5 ticket (alternative lookup)
            outcome: 'win', 'loss', 'breakeven', 'cancelled'
            exit_price: Exit price
            exit_time: Exit timestamp
            profit_loss: Profit/loss in dollars
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find recommendation
        if recommendation_id:
            cursor.execute("SELECT * FROM recommendations WHERE id = ?", (recommendation_id,))
        elif mt5_ticket:
            cursor.execute("SELECT * FROM recommendations WHERE mt5_ticket = ?", (mt5_ticket,))
        else:
            logger.error("Must provide either recommendation_id or mt5_ticket")
            conn.close()
            return
        
        row = cursor.fetchone()
        if not row:
            logger.warning(f"Recommendation not found: id={recommendation_id}, ticket={mt5_ticket}")
            conn.close()
            return
        
        # Calculate metrics
        # Schema: id, timestamp, symbol, trade_type, direction, entry_price, stop_loss, take_profit, ...
        rec_id = row[0]
        direction = row[4]
        entry_price = float(row[5]) if row[5] else 0
        stop_loss = float(row[6]) if row[6] else 0
        take_profit = float(row[7]) if row[7] else 0
        execution_time_str = row[16]  # executed=15, execution_time=16
        
        # Calculate risk:reward achieved
        risk_reward_achieved = None
        if exit_price and entry_price and stop_loss:
            if direction == "buy":
                risk = entry_price - stop_loss
                reward = exit_price - entry_price
            else:  # sell
                risk = stop_loss - entry_price
                reward = entry_price - exit_price
            
            if risk > 0:
                risk_reward_achieved = reward / risk
        
        # Calculate hold time
        hold_time_minutes = None
        if exit_time and execution_time_str:
            try:
                execution_time = datetime.fromisoformat(execution_time_str)
                hold_time_minutes = int((exit_time - execution_time).total_seconds() / 60)
            except:
                pass
        
        # Update database
        cursor.execute("""
            UPDATE recommendations
            SET outcome = ?,
                exit_price = ?,
                exit_time = ?,
                profit_loss = ?,
                risk_reward_achieved = ?,
                hold_time_minutes = ?
            WHERE id = ?
        """, (
            outcome,
            exit_price,
            exit_time.isoformat() if exit_time else None,
            profit_loss,
            risk_reward_achieved,
            hold_time_minutes,
            rec_id
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated outcome for recommendation #{rec_id}: {outcome}, P/L: ${profit_loss:.2f}, R:R: {risk_reward_achieved:.2f}R" if risk_reward_achieved else f"Updated outcome for recommendation #{rec_id}: {outcome}")
    
    def get_pending_recommendations(self) -> List[Dict]:
        """
        Get all recommendations that have been executed but don't have an outcome yet
        
        Returns:
            List of pending recommendations with their details
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, symbol, direction, entry_price, stop_loss, take_profit,
                   mt5_ticket, execution_time, trade_type, timeframe
            FROM recommendations
            WHERE executed = 1 AND outcome IS NULL
            ORDER BY execution_time DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        pending = []
        for row in rows:
            pending.append({
                "id": row[0],
                "symbol": row[1],
                "direction": row[2],
                "entry_price": row[3],
                "stop_loss": row[4],
                "take_profit": row[5],
                "mt5_ticket": row[6],
                "execution_time": row[7],
                "trade_type": row[8],
                "timeframe": row[9]
            })
        
        return pending
    
    def get_stats(
        self,
        symbol: str = None,
        trade_type: str = None,
        timeframe: str = None,
        session: str = None,
        days_back: int = 30
    ) -> Dict:
        """
        Get performance statistics
        
        Returns:
            dict with win_rate, avg_rr, total_trades, etc.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build query
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                AVG(CASE WHEN outcome IN ('win', 'loss') THEN risk_reward_achieved END) as avg_rr,
                AVG(CASE WHEN outcome = 'win' THEN risk_reward_achieved END) as avg_win_rr,
                AVG(CASE WHEN outcome = 'loss' THEN risk_reward_achieved END) as avg_loss_rr,
                SUM(CASE WHEN outcome IN ('win', 'loss') THEN profit_loss ELSE 0 END) as total_pnl,
                AVG(CASE WHEN outcome IN ('win', 'loss') THEN hold_time_minutes END) as avg_hold_time,
                AVG(confidence) as avg_confidence
            FROM recommendations
            WHERE executed = 1
                AND timestamp >= ?
        """
        
        params = [
            (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        ]
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper())
        
        if trade_type:
            query += " AND trade_type = ?"
            params.append(trade_type.lower())
        
        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)
        
        if session:
            query += " AND session = ?"
            params.append(session.lower())
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        conn.close()
        
        if not row or row[0] == 0:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "avg_rr_achieved": 0.0,
                "avg_win_rr": 0.0,
                "avg_loss_rr": 0.0,
                "total_pnl": 0.0,
                "avg_hold_time_minutes": 0,
                "avg_confidence": 0,
                "profit_factor": 0.0
            }
        
        total, wins, losses, avg_rr, avg_win_rr, avg_loss_rr, total_pnl, avg_hold_time, avg_confidence = row
        
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0
        
        # Calculate profit factor
        profit_factor = 0.0
        if avg_win_rr and avg_loss_rr and wins > 0 and losses > 0:
            total_wins = avg_win_rr * wins
            total_losses = abs(avg_loss_rr) * losses
            profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
        
        return {
            "total_trades": wins + losses,
            "wins": wins or 0,
            "losses": losses or 0,
            "win_rate": round(win_rate, 2),
            "avg_rr_achieved": round(avg_rr or 0, 2),
            "avg_win_rr": round(avg_win_rr or 0, 2),
            "avg_loss_rr": round(avg_loss_rr or 0, 2),
            "total_pnl": round(total_pnl or 0, 2),
            "avg_hold_time_minutes": int(avg_hold_time or 0),
            "avg_confidence": int(avg_confidence or 0),
            "profit_factor": round(profit_factor, 2)
        }
    
    def get_recent_recommendations(
        self,
        limit: int = 10,
        symbol: str = None,
        executed_only: bool = False
    ) -> List[Dict]:
        """Get recent recommendations"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM recommendations WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper())
        
        if executed_only:
            query += " AND executed = 1"
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_best_setups(self, min_trades: int = 5) -> List[Dict]:
        """Get best performing setups"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                symbol,
                trade_type,
                timeframe,
                session,
                COUNT(*) as total_trades,
                SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
                AVG(CASE WHEN outcome IN ('win', 'loss') THEN risk_reward_achieved END) as avg_rr,
                SUM(CASE WHEN outcome IN ('win', 'loss') THEN profit_loss ELSE 0 END) as total_pnl
            FROM recommendations
            WHERE executed = 1 AND outcome IN ('win', 'loss')
            GROUP BY symbol, trade_type, timeframe, session
            HAVING total_trades >= ?
            ORDER BY (wins * 1.0 / total_trades) DESC, avg_rr DESC
            LIMIT 10
        """, (min_trades,))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            symbol, trade_type, timeframe, session, total, wins, avg_rr, total_pnl = row
            win_rate = (wins / total * 100) if total > 0 else 0
            
            results.append({
                "symbol": symbol,
                "trade_type": trade_type,
                "timeframe": timeframe,
                "session": session,
                "total_trades": total,
                "win_rate": round(win_rate, 2),
                "avg_rr": round(avg_rr or 0, 2),
                "total_pnl": round(total_pnl or 0, 2)
            })
        
        return results
