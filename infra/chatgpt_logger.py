"""
ChatGPT Conversation Logger
Persists ChatGPT conversations to database for analytics and history
"""

import sqlite3
import time
import logging
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ChatGPTLogger:
    """Log and retrieve ChatGPT conversations"""
    
    def __init__(self, db_path: str = "data/journal.sqlite"):
        self.db_path = Path(db_path)
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Create conversation tracking tables"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        # Conversations table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chatgpt_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                started_at INTEGER NOT NULL,
                ended_at INTEGER,
                message_count INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                openai_cost REAL DEFAULT 0.0
            )
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON chatgpt_conversations(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_started ON chatgpt_conversations(started_at)")
        
        # Messages table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chatgpt_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT CHECK(role IN ('user', 'assistant', 'system')) NOT NULL,
                content TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                tokens_used INTEGER,
                model TEXT DEFAULT 'gpt-4o-mini',
                FOREIGN KEY(conversation_id) REFERENCES chatgpt_conversations(id) ON DELETE CASCADE
            )
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON chatgpt_messages(conversation_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_msg_ts ON chatgpt_messages(timestamp)")
        
        con.commit()
        con.close()
        logger.info("ChatGPT conversation tables ensured")
    
    def start_conversation(self, user_id: int, chat_id: int) -> int:
        """Start a new conversation and return conversation_id"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            INSERT INTO chatgpt_conversations (user_id, chat_id, started_at)
            VALUES (?, ?, ?)
        """, (user_id, chat_id, int(time.time())))
        
        conversation_id = cur.lastrowid
        con.commit()
        con.close()
        
        logger.info(f"Started conversation {conversation_id} for user {user_id}")
        return conversation_id
    
    def log_message(
        self, 
        conversation_id: int, 
        role: str, 
        content: str, 
        tokens_used: Optional[int] = None,
        model: str = "gpt-4o-mini"
    ):
        """Log a single message"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            INSERT INTO chatgpt_messages 
            (conversation_id, role, content, timestamp, tokens_used, model)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (conversation_id, role, content, int(time.time()), tokens_used, model))
        
        # Update conversation statistics
        cur.execute("""
            UPDATE chatgpt_conversations
            SET message_count = message_count + 1,
                total_tokens = total_tokens + COALESCE(?, 0)
            WHERE id = ?
        """, (tokens_used or 0, conversation_id))
        
        con.commit()
        con.close()
    
    def end_conversation(self, conversation_id: int):
        """Mark conversation as ended"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            UPDATE chatgpt_conversations
            SET ended_at = ?
            WHERE id = ?
        """, (int(time.time()), conversation_id))
        
        con.commit()
        con.close()
        
        logger.info(f"Ended conversation {conversation_id}")
    
    def get_conversation_history(self, conversation_id: int) -> List[Dict]:
        """Retrieve all messages from a conversation"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            SELECT role, content, timestamp, tokens_used
            FROM chatgpt_messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        """, (conversation_id,))
        
        messages = []
        for row in cur.fetchall():
            messages.append({
                "role": row[0],
                "content": row[1],
                "timestamp": row[2],
                "tokens_used": row[3]
            })
        
        con.close()
        return messages
    
    def get_user_conversations(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get recent conversations for a user"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            SELECT id, started_at, ended_at, message_count, total_tokens
            FROM chatgpt_conversations
            WHERE user_id = ?
            ORDER BY started_at DESC
            LIMIT ?
        """, (user_id, limit))
        
        conversations = []
        for row in cur.fetchall():
            conversations.append({
                "id": row[0],
                "started_at": row[1],
                "ended_at": row[2],
                "message_count": row[3],
                "total_tokens": row[4]
            })
        
        con.close()
        return conversations
    
    def get_conversation_stats(self, days: int = 30) -> Dict:
        """Get conversation statistics"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_conversations,
                COUNT(DISTINCT user_id) as unique_users,
                SUM(message_count) as total_messages,
                SUM(total_tokens) as total_tokens,
                AVG(message_count) as avg_messages_per_conv
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
            "avg_messages_per_conv": row[4] or 0
        }

