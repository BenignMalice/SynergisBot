"""
Performance Dashboard
Query functions for analytics and insights across all logging systems
"""

import sqlite3
import time
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class PerformanceDashboard:
    """Query functions for performance analytics"""
    
    def __init__(self, db_path: str = "data/journal.sqlite"):
        self.db_path = Path(db_path)
    
    def get_recommendation_performance(self, days: int = 30, symbol: Optional[str] = None) -> Dict:
        """Get AI recommendation performance metrics"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        # Overall stats
        if symbol:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed,
                    SUM(CASE WHEN result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result_pnl < 0 THEN 1 ELSE 0 END) as losses,
                    AVG(confidence) as avg_confidence,
                    AVG(result_pnl) as avg_pnl,
                    AVG(result_r) as avg_r,
                    AVG(risk_reward) as avg_rr
                FROM ai_recommendations
                WHERE created_at > ? AND symbol = ?
            """, (cutoff, symbol))
        else:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed,
                    SUM(CASE WHEN result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result_pnl < 0 THEN 1 ELSE 0 END) as losses,
                    AVG(confidence) as avg_confidence,
                    AVG(result_pnl) as avg_pnl,
                    AVG(result_r) as avg_r,
                    AVG(risk_reward) as avg_rr
                FROM ai_recommendations
                WHERE created_at > ?
            """, (cutoff,))
        
        row = cur.fetchone()
        
        # By symbol breakdown
        cur.execute("""
            SELECT 
                symbol,
                COUNT(*) as count,
                SUM(CASE WHEN result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result_pnl < 0 THEN 1 ELSE 0 END) as losses,
                AVG(result_pnl) as avg_pnl,
                AVG(result_r) as avg_r
            FROM ai_recommendations
            WHERE created_at > ? AND executed = 1
            GROUP BY symbol
            ORDER BY count DESC
        """, (cutoff,))
        
        by_symbol = {}
        for sym_row in cur.fetchall():
            wins = sym_row[2] or 0
            losses = sym_row[3] or 0
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            
            by_symbol[sym_row[0]] = {
                "count": sym_row[1],
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "avg_pnl": sym_row[4] or 0,
                "avg_r": sym_row[5] or 0
            }
        
        con.close()
        
        total = row[0] or 0
        executed = row[1] or 0
        wins = row[2] or 0
        losses = row[3] or 0
        
        return {
            "total_recommendations": total,
            "execution_rate": (executed / total * 100) if total > 0 else 0,
            "executed_count": executed,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0,
            "avg_confidence": row[4] or 0,
            "avg_pnl": row[5] or 0,
            "avg_r": row[6] or 0,
            "avg_rr": row[7] or 0,
            "by_symbol": by_symbol
        }
    
    def get_user_engagement(self, days: int = 30) -> Dict:
        """Get user engagement metrics"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        # Total actions
        cur.execute("""
            SELECT COUNT(*), COUNT(DISTINCT user_id)
            FROM user_actions
            WHERE timestamp > ?
        """, (cutoff,))
        
        total_actions, unique_users = cur.fetchone()
        
        # Most popular actions
        cur.execute("""
            SELECT action_type, COUNT(*) as count
            FROM user_actions
            WHERE timestamp > ?
            GROUP BY action_type
            ORDER BY count DESC
            LIMIT 10
        """, (cutoff,))
        
        popular_actions = {row[0]: row[1] for row in cur.fetchall()}
        
        con.close()
        
        return {
            "total_actions": total_actions or 0,
            "unique_users": unique_users or 0,
            "avg_actions_per_user": (total_actions / unique_users) if unique_users > 0 else 0,
            "popular_actions": popular_actions
        }
    
    def get_chatgpt_stats(self, days: int = 30) -> Dict:
        """Get ChatGPT conversation statistics"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_conversations,
                COUNT(DISTINCT user_id) as unique_users,
                SUM(message_count) as total_messages,
                SUM(total_tokens) as total_tokens,
                AVG(message_count) as avg_messages_per_conv,
                AVG(total_tokens) as avg_tokens_per_conv
            FROM chatgpt_conversations
            WHERE started_at > ?
        """, (cutoff,))
        
        row = cur.fetchone()
        con.close()
        
        return {
            "total_conversations": row[0] or 0,
            "unique_users": row[1] or 0,
            "total_messages": row[2] or 0,
            "total_tokens": row[3] or 0,
            "avg_messages_per_conv": row[4] or 0,
            "avg_tokens_per_conv": row[5] or 0
        }
    
    def get_trading_stats(self, days: int = 30) -> Dict:
        """Get trading statistics from journal"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        # Trade stats
        cur.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                AVG(r_multiple) as avg_r,
                AVG(duration_sec) as avg_duration
            FROM trades
            WHERE closed_ts > ? AND closed_ts IS NOT NULL
        """, (cutoff,))
        
        row = cur.fetchone()
        
        # OCO stats
        cur.execute("""
            SELECT 
                COUNT(*) as total_oco,
                SUM(CASE WHEN event = 'oco_triggered' THEN 1 ELSE 0 END) as triggered,
                SUM(CASE WHEN event = 'oco_failure' THEN 1 ELSE 0 END) as failures
            FROM events
            WHERE ts > ? AND event IN ('oco_triggered', 'oco_failure')
        """, (cutoff,))
        
        oco_row = cur.fetchone()
        
        # Trailing stop stats
        cur.execute("""
            SELECT COUNT(*)
            FROM events
            WHERE ts > ? AND event = 'trailing_stop_adjusted'
        """, (cutoff,))
        
        trailing_count = cur.fetchone()[0]
        
        con.close()
        
        total_trades = row[0] or 0
        wins = row[1] or 0
        losses = row[2] or 0
        
        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / total_trades * 100) if total_trades > 0 else 0,
            "total_pnl": row[3] or 0,
            "avg_pnl": row[4] or 0,
            "avg_r": row[5] or 0,
            "avg_duration_minutes": (row[6] / 60) if row[6] else 0,
            "oco_triggered": oco_row[1] or 0,
            "oco_failures": oco_row[2] or 0,
            "trailing_stops_adjusted": trailing_count or 0
        }
    
    def get_full_dashboard(self, days: int = 30) -> Dict:
        """Get complete dashboard with all metrics"""
        return {
            "period_days": days,
            "generated_at": int(time.time()),
            "recommendations": self.get_recommendation_performance(days),
            "engagement": self.get_user_engagement(days),
            "chatgpt": self.get_chatgpt_stats(days),
            "trading": self.get_trading_stats(days)
        }
    
    def get_top_performers(self, days: int = 30, limit: int = 5) -> Dict:
        """Get top performing recommendations and symbols"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        # Best recommendations by P&L
        cur.execute("""
            SELECT 
                id, symbol, direction, entry_price, result_pnl, result_r, created_at
            FROM ai_recommendations
            WHERE created_at > ? AND result_pnl IS NOT NULL
            ORDER BY result_pnl DESC
            LIMIT ?
        """, (cutoff, limit))
        
        best_trades = []
        for row in cur.fetchall():
            best_trades.append({
                "id": row[0],
                "symbol": row[1],
                "direction": row[2],
                "entry": row[3],
                "pnl": row[4],
                "r": row[5],
                "date": row[6]
            })
        
        # Worst recommendations by P&L
        cur.execute("""
            SELECT 
                id, symbol, direction, entry_price, result_pnl, result_r, created_at
            FROM ai_recommendations
            WHERE created_at > ? AND result_pnl IS NOT NULL
            ORDER BY result_pnl ASC
            LIMIT ?
        """, (cutoff, limit))
        
        worst_trades = []
        for row in cur.fetchall():
            worst_trades.append({
                "id": row[0],
                "symbol": row[1],
                "direction": row[2],
                "entry": row[3],
                "pnl": row[4],
                "r": row[5],
                "date": row[6]
            })
        
        con.close()
        
        return {
            "best_trades": best_trades,
            "worst_trades": worst_trades
        }
    
    def get_symbol_dashboard(self, symbol: str, days: int = 30) -> Dict:
        """Get comprehensive dashboard for a specific symbol"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        # Recommendation stats for symbol
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed,
                SUM(CASE WHEN result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result_pnl < 0 THEN 1 ELSE 0 END) as losses,
                AVG(confidence) as avg_confidence,
                SUM(result_pnl) as total_pnl,
                AVG(result_pnl) as avg_pnl,
                AVG(result_r) as avg_r,
                AVG(risk_reward) as avg_rr
            FROM ai_recommendations
            WHERE symbol = ? AND created_at > ?
        """, (symbol, cutoff))
        
        row = cur.fetchone()
        
        total = row[0] or 0
        executed = row[1] or 0
        wins = row[2] or 0
        losses = row[3] or 0
        
        # Direction breakdown
        cur.execute("""
            SELECT 
                direction,
                COUNT(*) as count,
                SUM(CASE WHEN result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                AVG(result_pnl) as avg_pnl
            FROM ai_recommendations
            WHERE symbol = ? AND created_at > ? AND executed = 1
            GROUP BY direction
        """, (symbol, cutoff))
        
        by_direction = {}
        for dir_row in cur.fetchall():
            direction, count, dir_wins, dir_pnl = dir_row
            by_direction[direction] = {
                "count": count,
                "wins": dir_wins or 0,
                "avg_pnl": dir_pnl or 0
            }
        
        # Recent recommendations
        cur.execute("""
            SELECT 
                direction, confidence, entry_price, result_pnl, result_r, created_at
            FROM ai_recommendations
            WHERE symbol = ? AND created_at > ?
            ORDER BY created_at DESC
            LIMIT 10
        """, (symbol, cutoff))
        
        recent = []
        for rec_row in cur.fetchall():
            recent.append({
                "direction": rec_row[0],
                "confidence": rec_row[1],
                "entry": rec_row[2],
                "pnl": rec_row[3],
                "r": rec_row[4],
                "timestamp": rec_row[5]
            })
        
        con.close()
        
        return {
            "symbol": symbol,
            "period_days": days,
            "total_recommendations": total,
            "executed": executed,
            "execution_rate": (executed / total * 100) if total > 0 else 0,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0,
            "avg_confidence": row[4] or 0,
            "total_pnl": row[5] or 0,
            "avg_pnl": row[6] or 0,
            "avg_r": row[7] or 0,
            "avg_rr": row[8] or 0,
            "by_direction": by_direction,
            "recent_recommendations": recent
        }
    
    def get_performance_trends(self, days: int = 90, interval_days: int = 7) -> Dict:
        """Get performance trends over time"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        interval_sec = interval_days * 86400
        
        # Get time series of performance
        cur.execute("""
            SELECT 
                (created_at / ?) * ? as period_start,
                COUNT(*) as total,
                SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed,
                SUM(CASE WHEN result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result_pnl < 0 THEN 1 ELSE 0 END) as losses,
                SUM(result_pnl) as total_pnl,
                AVG(confidence) as avg_confidence
            FROM ai_recommendations
            WHERE created_at > ?
            GROUP BY period_start
            ORDER BY period_start ASC
        """, (interval_sec, interval_sec, cutoff))
        
        trends = []
        cumulative_pnl = 0.0
        
        for trend_row in cur.fetchall():
            period_start = trend_row[0]
            total = trend_row[1] or 0
            executed = trend_row[2] or 0
            wins = trend_row[3] or 0
            losses = trend_row[4] or 0
            pnl = trend_row[5] or 0
            confidence = trend_row[6] or 0
            
            cumulative_pnl += pnl
            
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            
            trends.append({
                "period_start": period_start,
                "total": total,
                "executed": executed,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "pnl": pnl,
                "cumulative_pnl": cumulative_pnl,
                "avg_confidence": confidence
            })
        
        con.close()
        
        return {
            "interval_days": interval_days,
            "total_periods": len(trends),
            "trends": trends,
            "final_cumulative_pnl": cumulative_pnl
        }
    
    def get_confidence_correlation(self, days: int = 30) -> Dict:
        """Analyze correlation between confidence and outcome"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        # Bucket by confidence ranges
        confidence_ranges = [
            (0, 50, "Low (0-50)"),
            (50, 70, "Medium (50-70)"),
            (70, 85, "High (70-85)"),
            (85, 100, "Very High (85-100)")
        ]
        
        results = []
        
        for min_conf, max_conf, label in confidence_ranges:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed,
                    SUM(CASE WHEN result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result_pnl < 0 THEN 1 ELSE 0 END) as losses,
                    AVG(result_pnl) as avg_pnl,
                    AVG(result_r) as avg_r,
                    AVG(confidence) as avg_confidence
                FROM ai_recommendations
                WHERE confidence >= ? AND confidence < ? 
                AND created_at > ? AND executed = 1
            """, (min_conf, max_conf, cutoff))
            
            row = cur.fetchone()
            
            total = row[0] or 0
            executed = row[1] or 0
            wins = row[2] or 0
            losses = row[3] or 0
            
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            
            results.append({
                "range": label,
                "min_confidence": min_conf,
                "max_confidence": max_conf,
                "total": total,
                "executed": executed,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "avg_pnl": row[4] or 0,
                "avg_r": row[5] or 0,
                "avg_confidence": row[6] or 0
            })
        
        con.close()
        
        return {
            "period_days": days,
            "confidence_ranges": results
        }

