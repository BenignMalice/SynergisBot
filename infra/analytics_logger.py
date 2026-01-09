"""
Analytics Logger
Tracks user actions and behavior for analytics and insights
"""

import sqlite3
import time
import json
import logging
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


class AnalyticsLogger:
    """Track user actions and behavior"""
    
    def __init__(self, db_path: str = "data/journal.sqlite"):
        self.db_path = Path(db_path)
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Create user actions table"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                action_data TEXT,
                timestamp INTEGER NOT NULL
            )
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_action_user ON user_actions(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_action_ts ON user_actions(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_action_type ON user_actions(action_type)")
        
        con.commit()
        con.close()
        logger.info("User actions table ensured")
    
    def log_action(
        self,
        user_id: int,
        chat_id: int,
        action_type: str,
        action_data: Optional[Dict] = None
    ):
        """Log a user action"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        data_json = json.dumps(action_data) if action_data else None
        
        cur.execute("""
            INSERT INTO user_actions (user_id, chat_id, action_type, action_data, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, chat_id, action_type, data_json, int(time.time())))
        
        con.commit()
        con.close()
    
    def get_user_stats(self, user_id: int, days: int = 30) -> Dict:
        """Get user activity statistics"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        # Total actions
        cur.execute("""
            SELECT COUNT(*) FROM user_actions
            WHERE user_id = ? AND timestamp > ?
        """, (user_id, cutoff))
        total_actions = cur.fetchone()[0]
        
        # Actions by type
        cur.execute("""
            SELECT action_type, COUNT(*) as count
            FROM user_actions
            WHERE user_id = ? AND timestamp > ?
            GROUP BY action_type
            ORDER BY count DESC
        """, (user_id, cutoff))
        
        actions_by_type = {}
        for row in cur.fetchall():
            actions_by_type[row[0]] = row[1]
        
        # Most recent action
        cur.execute("""
            SELECT action_type, timestamp FROM user_actions
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (user_id,))
        
        recent = cur.fetchone()
        last_action = recent[0] if recent else None
        last_action_time = recent[1] if recent else None
        
        con.close()
        
        return {
            "user_id": user_id,
            "total_actions": total_actions,
            "actions_by_type": actions_by_type,
            "last_action": last_action,
            "last_action_time": last_action_time
        }
    
    def get_popular_actions(self, days: int = 30, limit: int = 10) -> List[Dict]:
        """Get most popular actions across all users"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        cur.execute("""
            SELECT action_type, COUNT(*) as count, COUNT(DISTINCT user_id) as unique_users
            FROM user_actions
            WHERE timestamp > ?
            GROUP BY action_type
            ORDER BY count DESC
            LIMIT ?
        """, (cutoff, limit))
        
        popular = []
        for row in cur.fetchall():
            popular.append({
                "action_type": row[0],
                "count": row[1],
                "unique_users": row[2]
            })
        
        con.close()
        return popular
    
    def get_user_engagement(self, days: int = 30) -> Dict:
        """Get overall user engagement metrics"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        # Total actions and unique users
        cur.execute("""
            SELECT COUNT(*) as total_actions, COUNT(DISTINCT user_id) as unique_users
            FROM user_actions
            WHERE timestamp > ?
        """, (cutoff,))
        
        row = cur.fetchone()
        total_actions = row[0] or 0
        unique_users = row[1] or 0
        
        # Actions per user
        cur.execute("""
            SELECT user_id, COUNT(*) as action_count
            FROM user_actions
            WHERE timestamp > ?
            GROUP BY user_id
            ORDER BY action_count DESC
        """, (cutoff,))
        
        user_action_counts = [row[1] for row in cur.fetchall()]
        
        con.close()
        
        return {
            "total_actions": total_actions,
            "unique_users": unique_users,
            "avg_actions_per_user": total_actions / unique_users if unique_users > 0 else 0,
            "most_active_user_actions": user_action_counts[0] if user_action_counts else 0
        }
    
    def get_action_timeline(self, user_id: int, limit: int = 20) -> List[Dict]:
        """Get recent action timeline for a user"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            SELECT action_type, action_data, timestamp
            FROM user_actions
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
        
        timeline = []
        for row in cur.fetchall():
            data = json.loads(row[1]) if row[1] else None
            timeline.append({
                "action_type": row[0],
                "action_data": data,
                "timestamp": row[2]
            })
        
        con.close()
        return timeline

