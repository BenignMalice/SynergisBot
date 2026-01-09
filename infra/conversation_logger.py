"""
Conversation Logger
Logs ChatGPT conversations for audit trail and analysis.
Tracks analysis requests, decisions, and recommendations.
"""

import logging
import sqlite3
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ConversationLogger:
    """
    Logs ChatGPT conversations to database.
    Tracks user queries, assistant responses, tool calls, and outcomes.
    """
    
    def __init__(self, db_path: str = "data/conversations.sqlite"):
        """
        Initialize conversation logger.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        logger.info(f"ConversationLogger initialized (DB: {self.db_path})")
    
    def _init_database(self):
        """Create tables if they don't exist"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    user_query TEXT NOT NULL,
                    assistant_response TEXT,
                    tool_calls TEXT,  -- JSON array of tool calls
                    symbol TEXT,
                    action TEXT,  -- ANALYZE, EXECUTE, MODIFY, STATUS, etc.
                    confidence INTEGER,
                    recommendation TEXT,
                    reasoning TEXT,
                    execution_result TEXT,  -- success/failure
                    ticket INTEGER,
                    source TEXT,  -- desktop_agent, telegram_bot, custom_gpt
                    chat_id TEXT,  -- For Telegram
                    extra TEXT  -- JSON blob for additional data
                )
            """)
            
            # Analysis requests table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT,
                    analysis_type TEXT,  -- technical, fundamental, sentiment, etc.
                    direction TEXT,  -- BUY, SELL, HOLD
                    confidence INTEGER,
                    key_levels TEXT,  -- JSON: support, resistance, targets
                    indicators TEXT,  -- JSON: RSI, MACD, ADX, etc.
                    reasoning TEXT,
                    advanced_features TEXT,  -- JSON: V8 enrichment fields
                    source TEXT,
                    conversation_id INTEGER,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            
            # Recommendations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,  -- BUY, SELL, HOLD
                    confidence INTEGER NOT NULL,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    reasoning TEXT,
                    was_executed INTEGER DEFAULT 0,  -- Boolean
                    ticket INTEGER,  -- If executed
                    outcome TEXT,  -- win, loss, breakeven, open
                    conversation_id INTEGER,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_symbol ON conversations(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_action ON conversations(action)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_ticket ON conversations(ticket)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_symbol ON analysis_requests(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_symbol ON recommendations(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_executed ON recommendations(was_executed)")
            
            conn.commit()
            conn.close()
            
            logger.debug("Conversation database initialized")
            
        except Exception as e:
            logger.error(f"Error initializing conversation database: {e}", exc_info=True)
    
    def log_conversation(
        self,
        user_query: str,
        assistant_response: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        symbol: Optional[str] = None,
        action: Optional[str] = None,
        confidence: Optional[int] = None,
        recommendation: Optional[str] = None,
        reasoning: Optional[str] = None,
        execution_result: Optional[str] = None,
        ticket: Optional[int] = None,
        source: str = "unknown",
        chat_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Log a conversation to database.
        
        Args:
            user_query: User's question or command
            assistant_response: ChatGPT's response
            tool_calls: List of tool calls made (if any)
            symbol: Trading symbol (if applicable)
            action: Action type (ANALYZE, EXECUTE, MODIFY, STATUS, etc.)
            confidence: Confidence score (0-100)
            recommendation: Trading recommendation (if applicable)
            reasoning: Reasoning behind recommendation
            execution_result: success/failure (if trade was executed)
            ticket: MT5 ticket number (if trade was executed)
            source: Source of conversation (desktop_agent, telegram_bot, custom_gpt)
            chat_id: Telegram chat ID (if applicable)
            extra: Additional data as dict
            
        Returns:
            Conversation ID
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Convert tool_calls to JSON
            tool_calls_json = json.dumps(tool_calls) if tool_calls else None
            extra_json = json.dumps(extra) if extra else None
            
            cursor.execute("""
                INSERT INTO conversations (
                    timestamp, user_query, assistant_response, tool_calls,
                    symbol, action, confidence, recommendation, reasoning,
                    execution_result, ticket, source, chat_id, extra
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(time.time()),
                user_query,
                assistant_response,
                tool_calls_json,
                symbol,
                action,
                confidence,
                recommendation,
                reasoning,
                execution_result,
                ticket,
                source,
                chat_id,
                extra_json
            ))
            
            conversation_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.debug(f"Logged conversation ID {conversation_id}: action={action}, symbol={symbol}")
            return conversation_id
            
        except Exception as e:
            logger.error(f"Error logging conversation: {e}", exc_info=True)
            return -1
    
    def log_analysis(
        self,
        symbol: str,
        direction: str,
        confidence: int,
        reasoning: str,
        timeframe: Optional[str] = None,
        analysis_type: str = "technical",
        key_levels: Optional[Dict[str, Any]] = None,
        indicators: Optional[Dict[str, Any]] = None,
        advanced_features: Optional[Dict[str, Any]] = None,
        source: str = "unknown",
        conversation_id: Optional[int] = None
    ) -> int:
        """
        Log an analysis request to database.
        
        Args:
            symbol: Trading symbol
            direction: BUY, SELL, or HOLD
            confidence: Confidence score (0-100)
            reasoning: Analysis reasoning
            timeframe: Timeframe analyzed (M5, M15, H1, etc.)
            analysis_type: Type of analysis
            key_levels: Dict with support, resistance, targets
            indicators: Dict with indicator values
            advanced_features: Dict with V8 enrichment fields
            source: Source of analysis
            conversation_id: Parent conversation ID
            
        Returns:
            Analysis ID
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Convert dicts to JSON
            key_levels_json = json.dumps(key_levels) if key_levels else None
            indicators_json = json.dumps(indicators) if indicators else None
            v8_features_json = json.dumps(advanced_features) if advanced_features else None
            
            cursor.execute("""
                INSERT INTO analysis_requests (
                    timestamp, symbol, timeframe, analysis_type,
                    direction, confidence, key_levels, indicators,
                    reasoning, advanced_features, source, conversation_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(time.time()),
                symbol,
                timeframe,
                analysis_type,
                direction,
                confidence,
                key_levels_json,
                indicators_json,
                reasoning,
                v8_features_json,
                source,
                conversation_id
            ))
            
            analysis_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.debug(f"Logged analysis ID {analysis_id}: {symbol} {direction} ({confidence}%)")
            return analysis_id
            
        except Exception as e:
            logger.error(f"Error logging analysis: {e}", exc_info=True)
            return -1
    
    def log_recommendation(
        self,
        symbol: str,
        action: str,
        confidence: int,
        reasoning: str,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        conversation_id: Optional[int] = None
    ) -> int:
        """
        Log a trading recommendation to database.
        
        Args:
            symbol: Trading symbol
            action: BUY, SELL, or HOLD
            confidence: Confidence score (0-100)
            reasoning: Recommendation reasoning
            entry_price: Recommended entry price
            stop_loss: Recommended stop loss
            take_profit: Recommended take profit
            conversation_id: Parent conversation ID
            
        Returns:
            Recommendation ID
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO recommendations (
                    timestamp, symbol, action, confidence,
                    entry_price, stop_loss, take_profit,
                    reasoning, conversation_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(time.time()),
                symbol,
                action,
                confidence,
                entry_price,
                stop_loss,
                take_profit,
                reasoning,
                conversation_id
            ))
            
            recommendation_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.debug(f"Logged recommendation ID {recommendation_id}: {symbol} {action} ({confidence}%)")
            return recommendation_id
            
        except Exception as e:
            logger.error(f"Error logging recommendation: {e}", exc_info=True)
            return -1
    
    def update_recommendation_execution(
        self,
        recommendation_id: int,
        was_executed: bool,
        ticket: Optional[int] = None
    ) -> bool:
        """
        Update recommendation with execution status.
        
        Args:
            recommendation_id: Recommendation ID to update
            was_executed: Whether the recommendation was executed
            ticket: MT5 ticket number (if executed)
            
        Returns:
            True if successful
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE recommendations
                SET was_executed = ?, ticket = ?
                WHERE id = ?
            """, (1 if was_executed else 0, ticket, recommendation_id))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Updated recommendation {recommendation_id}: executed={was_executed}, ticket={ticket}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating recommendation: {e}", exc_info=True)
            return False
    
    def get_recent_conversations(
        self,
        limit: int = 10,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversations from database.
        
        Args:
            limit: Maximum number of conversations to return
            symbol: Filter by symbol (optional)
            
        Returns:
            List of conversation dicts
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if symbol:
                cursor.execute("""
                    SELECT * FROM conversations
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (symbol, limit))
            else:
                cursor.execute("""
                    SELECT * FROM conversations
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            conversations = [dict(row) for row in rows]
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting recent conversations: {e}", exc_info=True)
            return []


# Global instance
_conversation_logger_instance = None


def get_conversation_logger() -> ConversationLogger:
    """
    Get or create the global ConversationLogger instance.
    
    Returns:
        ConversationLogger instance
    """
    global _conversation_logger_instance
    
    if _conversation_logger_instance is None:
        _conversation_logger_instance = ConversationLogger()
    
    return _conversation_logger_instance

