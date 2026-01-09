"""
AI Recommendation Logger
Tracks all AI-generated trade recommendations for performance analysis
"""

import sqlite3
import time
import logging
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


class RecommendationLogger:
    """Log and track AI trade recommendations"""
    
    def __init__(self, db_path: str = "data/journal.sqlite"):
        self.db_path = Path(db_path)
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Create recommendation tracking table"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                conversation_id INTEGER,
                symbol TEXT NOT NULL,
                direction TEXT CHECK(direction IN ('BUY', 'SELL', 'HOLD')) NOT NULL,
                reasoning TEXT,
                confidence INTEGER,
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                risk_reward REAL,
                timeframe TEXT,
                market_regime TEXT,
                created_at INTEGER NOT NULL,
                executed BOOLEAN DEFAULT 0,
                execution_ticket INTEGER,
                execution_time INTEGER,
                result_pnl REAL,
                result_r REAL,
                model TEXT DEFAULT 'gpt-4o-mini',
                generation_time REAL
            )
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_symbol ON ai_recommendations(symbol)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_created ON ai_recommendations(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_user ON ai_recommendations(user_id)")
        
        con.commit()
        con.close()
        logger.info("AI recommendations table ensured")
    
    def log_recommendation(
        self,
        user_id: int,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        reasoning: str = "",
        confidence: int = 0,
        market_regime: str = "",
        timeframe: str = "M15",
        conversation_id: Optional[int] = None,
        generation_time: float = 0.0,
        model: str = "gpt-4o-mini"
    ) -> int:
        """Log a recommendation and return its ID"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        # Calculate R:R
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        rr = reward / risk if risk > 0 else 0
        
        cur.execute("""
            INSERT INTO ai_recommendations
            (user_id, conversation_id, symbol, direction, reasoning, confidence,
             entry_price, stop_loss, take_profit, risk_reward, timeframe, 
             market_regime, created_at, generation_time, model)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, conversation_id, symbol, direction, reasoning[:500], confidence,
            entry_price, stop_loss, take_profit, rr, timeframe,
            market_regime, int(time.time()), generation_time, model
        ))
        
        rec_id = cur.lastrowid
        con.commit()
        con.close()
        
        logger.info(f"Logged recommendation {rec_id}: {direction} {symbol} @ {entry_price} (RR: {rr:.2f})")
        return rec_id
    
    def mark_executed(self, rec_id: int, ticket: int):
        """Mark recommendation as executed"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            UPDATE ai_recommendations
            SET executed = 1, execution_ticket = ?, execution_time = ?
            WHERE id = ?
        """, (ticket, int(time.time()), rec_id))
        
        con.commit()
        con.close()
        
        logger.info(f"Marked recommendation {rec_id} as executed (ticket {ticket})")
    
    def update_result(self, rec_id: int, pnl: float, r_multiple: float):
        """Update recommendation with trade result"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            UPDATE ai_recommendations
            SET result_pnl = ?, result_r = ?
            WHERE id = ?
        """, (pnl, r_multiple, rec_id))
        
        con.commit()
        con.close()
        
        logger.info(f"Updated recommendation {rec_id} result: P&L ${pnl:.2f}, R: {r_multiple:.2f}")
    
    def get_recent_recommendations(self, user_id: Optional[int] = None, limit: int = 10) -> List[Dict]:
        """Get recent recommendations"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        if user_id:
            cur.execute("""
                SELECT id, symbol, direction, confidence, entry_price, created_at, executed
                FROM ai_recommendations
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
        else:
            cur.execute("""
                SELECT id, symbol, direction, confidence, entry_price, created_at, executed
                FROM ai_recommendations
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        
        recommendations = []
        for row in cur.fetchall():
            recommendations.append({
                "id": row[0],
                "symbol": row[1],
                "direction": row[2],
                "confidence": row[3],
                "entry_price": row[4],
                "created_at": row[5],
                "executed": bool(row[6])
            })
        
        con.close()
        return recommendations
    
    def get_recommendation_stats(self, days: int = 30, symbol: Optional[str] = None) -> Dict:
        """Get recommendation performance statistics"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        if symbol:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed_count,
                    AVG(confidence) as avg_confidence,
                    SUM(CASE WHEN result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result_pnl < 0 THEN 1 ELSE 0 END) as losses,
                    AVG(result_pnl) as avg_pnl,
                    AVG(result_r) as avg_r,
                    AVG(risk_reward) as avg_rr_planned
                FROM ai_recommendations
                WHERE created_at > ? AND symbol = ? AND executed = 1
            """, (cutoff, symbol))
        else:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed_count,
                    AVG(confidence) as avg_confidence,
                    SUM(CASE WHEN result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result_pnl < 0 THEN 1 ELSE 0 END) as losses,
                    AVG(result_pnl) as avg_pnl,
                    AVG(result_r) as avg_r,
                    AVG(risk_reward) as avg_rr_planned
                FROM ai_recommendations
                WHERE created_at > ? AND executed = 1
            """, (cutoff,))
        
        row = cur.fetchone()
        con.close()
        
        total = row[0] or 0
        executed = row[1] or 0
        wins = row[3] or 0
        losses = row[4] or 0
        
        return {
            "total_recommendations": total,
            "execution_rate": (executed / total * 100) if total > 0 else 0,
            "executed_count": executed,
            "avg_confidence": row[2] or 0,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0,
            "avg_pnl": row[5] or 0,
            "avg_r": row[6] or 0,
            "avg_rr_planned": row[7] or 0
        }
    
    def get_by_ticket(self, ticket: int) -> Optional[int]:
        """Get recommendation ID by execution ticket"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            SELECT id FROM ai_recommendations
            WHERE execution_ticket = ?
        """, (ticket,))
        
        row = cur.fetchone()
        con.close()
        
        return row[0] if row else None

