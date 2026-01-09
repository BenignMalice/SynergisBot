# Logging Enhancement Implementation Plan

## 📋 Overview
Comprehensive plan to implement Priority 1, 2, and 3 logging enhancements for `chatgpt_bot.py`.

**Total Estimated Time**: ~6 hours
**Files to Modify**: 5
**New Files to Create**: 3
**Database Tables to Add**: 6

---

## 🎯 Priority 1: Essential Features (~2 hours)

### 1.1 File Logging with Rotation ⏱️ 15 min

**Objective**: Add persistent file-based logging with automatic rotation

**Files to Modify**:
- `chatgpt_bot.py`

**Implementation**:
```python
# Add to chatgpt_bot.py after imports
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_file_logging():
    """Configure file logging with rotation"""
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create rotating file handler
    file_handler = RotatingFileHandler(
        log_dir / "chatgpt_bot.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    
    # Set format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Add to root logger
    logging.getLogger().addHandler(file_handler)
    
    # Separate error log
    error_handler = RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    logging.getLogger().addHandler(error_handler)
    
    logger.info("File logging initialized")

# Call in main() before any other operations
def main():
    setup_file_logging()
    logger.info("🤖 Starting ChatGPT Telegram Bot...")
```

**Testing**:
```bash
# Check logs are being created
ls -lh data/logs/
tail -f data/logs/chatgpt_bot.log
```

---

### 1.2 ChatGPT Conversation Database ⏱️ 45 min

**Objective**: Persist ChatGPT conversations to database

**Files to Create**:
- `infra/chatgpt_logger.py` (new)

**Files to Modify**:
- `chatgpt_bot.py`
- `infra/journal_repo.py` (add new tables)

**Database Schema**:
```sql
-- Add to journal.sqlite
CREATE TABLE IF NOT EXISTS chatgpt_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    started_at INTEGER NOT NULL,
    ended_at INTEGER,
    message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    openai_cost REAL DEFAULT 0.0,
    INDEX idx_user_id (user_id),
    INDEX idx_started_at (started_at)
);

CREATE TABLE IF NOT EXISTS chatgpt_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT CHECK(role IN ('user', 'assistant', 'system')) NOT NULL,
    content TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    tokens_used INTEGER,
    model TEXT DEFAULT 'gpt-4o-mini',
    FOREIGN KEY(conversation_id) REFERENCES chatgpt_conversations(id) ON DELETE CASCADE,
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_timestamp (timestamp)
);
```

**Implementation** (`infra/chatgpt_logger.py`):
```python
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
    
    def log_message(self, conversation_id: int, role: str, content: str, 
                    tokens_used: Optional[int] = None):
        """Log a single message"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            INSERT INTO chatgpt_messages 
            (conversation_id, role, content, timestamp, tokens_used)
            VALUES (?, ?, ?, ?, ?)
        """, (conversation_id, role, content, int(time.time()), tokens_used))
        
        # Update message count
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
```

**Modify `chatgpt_bot.py`**:
```python
from infra.chatgpt_logger import ChatGPTLogger

# Global
chatgpt_logger = None

def main():
    global chatgpt_logger
    # ... existing setup ...
    
    chatgpt_logger = ChatGPTLogger()
    logger.info("✅ ChatGPT logger initialized")

# In chatgpt_start()
async def chatgpt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Start conversation in database
    conversation_id = chatgpt_logger.start_conversation(user_id, chat_id)
    
    user_conversations[user_id] = {
        "conversation_id": conversation_id,  # Add this
        "messages": [],
        "started_at": datetime.now().isoformat(),
        "chat_id": chat_id
    }

# In chatgpt_message() after each message
async def chatgpt_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing code ...
    
    conversation_id = user_conversations[user_id]["conversation_id"]
    
    # Log user message
    chatgpt_logger.log_message(conversation_id, "user", user_message)
    
    # After OpenAI response
    chatgpt_logger.log_message(
        conversation_id, 
        "assistant", 
        assistant_reply,
        tokens_used=response.usage.total_tokens
    )

# In chatgpt_end()
async def chatgpt_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing code ...
    
    conversation_id = user_conversations[user_id].get("conversation_id")
    if conversation_id:
        chatgpt_logger.end_conversation(conversation_id)
```

---

### 1.3 AI Recommendations Tracking ⏱️ 30 min

**Objective**: Log all AI-generated trade recommendations

**Files to Create**:
- `infra/recommendation_logger.py` (new)

**Database Schema**:
```sql
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
    generation_time REAL,
    FOREIGN KEY(conversation_id) REFERENCES chatgpt_conversations(id) ON DELETE SET NULL,
    INDEX idx_rec_symbol (symbol),
    INDEX idx_rec_created (created_at),
    INDEX idx_rec_user (user_id)
);
```

**Implementation** (`infra/recommendation_logger.py`):
```python
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
        conversation_id: Optional[int] = None,
        generation_time: float = 0.0
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
             entry_price, stop_loss, take_profit, risk_reward, market_regime,
             created_at, generation_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, conversation_id, symbol, direction, reasoning[:500], confidence,
            entry_price, stop_loss, take_profit, rr, market_regime,
            int(time.time()), generation_time
        ))
        
        rec_id = cur.lastrowid
        con.commit()
        con.close()
        
        logger.info(f"Logged recommendation {rec_id}: {direction} {symbol} @ {entry_price}")
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
    
    def get_recommendation_stats(self, days: int = 30) -> Dict:
        """Get recommendation performance statistics"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed_count,
                AVG(confidence) as avg_confidence,
                SUM(CASE WHEN result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result_pnl < 0 THEN 1 ELSE 0 END) as losses,
                AVG(result_pnl) as avg_pnl,
                AVG(result_r) as avg_r
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
            "avg_confidence": row[2] or 0,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0,
            "avg_pnl": row[5] or 0,
            "avg_r": row[6] or 0
        }
```

**Modify `chatgpt_bot.py`**:
```python
from infra.recommendation_logger import RecommendationLogger

recommendation_logger = None

def main():
    global recommendation_logger
    recommendation_logger = RecommendationLogger()

# In gpt_trade_ button handler
async def menu_button_handler(update, context):
    # ... after getting recommendation ...
    
    # Log the recommendation
    rec_id = recommendation_logger.log_recommendation(
        user_id=user_id,
        symbol=symbol,
        direction=direction,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        reasoning=reasoning,
        confidence=confidence,
        market_regime=regime,
        conversation_id=user_conversations[user_id].get("conversation_id"),
        generation_time=generation_duration
    )
    
    # Store rec_id in context for potential execution tracking
    context.user_data["last_rec_id"] = rec_id
```

---

### 1.4 Signal Scanner Logging ⏱️ 20 min

**Objective**: Record all signals detected by background scanner

**Database Schema**:
```sql
CREATE TABLE IF NOT EXISTS signal_scanner_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT,
    direction TEXT CHECK(direction IN ('BUY', 'SELL', 'HOLD')) NOT NULL,
    confidence INTEGER,
    rsi REAL,
    adx REAL,
    atr REAL,
    market_regime TEXT,
    reason TEXT,
    detected_at INTEGER NOT NULL,
    notified BOOLEAN DEFAULT 0,
    INDEX idx_signal_detected (detected_at),
    INDEX idx_signal_symbol (symbol)
);
```

**Modify `chatgpt_bot.py`**:
```python
async def scan_for_signals(app: Application):
    """Background task: Scan markets for trade signals"""
    global monitored_chat_id
    if not monitored_chat_id:
        return
    
    try:
        symbols = ["XAUUSD", "BTCUSD", "ETHUSD"]
        
        for symbol in symbols:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"http://localhost:8000/ai/analysis/{symbol}")
            
            if response.status_code == 200:
                data = response.json()
                tech = data.get("technical_analysis", {})
                rec = tech.get("trade_recommendation", {})
                indicators = tech.get("indicators", {})
                
                direction = rec.get("direction", "HOLD")
                confidence = rec.get("confidence", 0)
                
                # Log signal to database
                con = sqlite3.connect("data/journal.sqlite")
                cur = con.cursor()
                cur.execute("""
                    INSERT INTO signal_scanner_results
                    (symbol, timeframe, direction, confidence, rsi, adx, atr,
                     market_regime, reason, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, "M15", direction, confidence,
                    indicators.get("rsi", 50),
                    indicators.get("adx", 0),
                    indicators.get("atr14", 0),
                    tech.get("market_regime", "UNKNOWN"),
                    rec.get("reasoning", ""),
                    int(time.time())
                ))
                con.commit()
                con.close()
                
                logger.info(f"Signal logged: {symbol} {direction} ({confidence}%)")
                
                # Only notify on high-confidence signals
                if confidence >= 70:
                    await app.bot.send_message(
                        chat_id=monitored_chat_id,
                        text=f"🎯 *High-Confidence Signal Detected!*\n\n"
                             f"Symbol: {symbol}\n"
                             f"Direction: {direction}\n"
                             f"Confidence: {confidence}%\n"
                             f"Use /chatgpt to analyze!",
                        parse_mode="Markdown"
                    )
                    
                    # Mark as notified
                    con = sqlite3.connect("data/journal.sqlite")
                    cur = con.cursor()
                    cur.execute("""
                        UPDATE signal_scanner_results
                        SET notified = 1
                        WHERE symbol = ? AND detected_at = (
                            SELECT MAX(detected_at) FROM signal_scanner_results WHERE symbol = ?
                        )
                    """, (symbol, symbol))
                    con.commit()
                    con.close()
    
    except Exception as e:
        logger.error(f"Error scanning for signals: {e}")
```

---

## 🎯 Priority 2: Important Features (~2 hours)

### 2.1 User Action Analytics ⏱️ 45 min

**Database Schema**:
```sql
CREATE TABLE IF NOT EXISTS user_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    action_data TEXT,
    timestamp INTEGER NOT NULL,
    INDEX idx_action_user (user_id),
    INDEX idx_action_ts (timestamp),
    INDEX idx_action_type (action_type)
);
```

**Files to Create**:
- `infra/analytics_logger.py`

**Implementation**:
```python
# infra/analytics_logger.py
import sqlite3
import time
import json
import logging
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

class AnalyticsLogger:
    """Track user actions and behavior"""
    
    def __init__(self, db_path: str = "data/journal.sqlite"):
        self.db_path = Path(db_path)
        self._ensure_schema()
    
    def _ensure_schema(self):
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
        
        cur.execute("""
            SELECT action_type, COUNT(*) as count
            FROM user_actions
            WHERE user_id = ? AND timestamp > ?
            GROUP BY action_type
            ORDER BY count DESC
        """, (user_id, cutoff))
        
        stats = {}
        for row in cur.fetchall():
            stats[row[0]] = row[1]
        
        con.close()
        return stats
```

**Modify `chatgpt_bot.py`**:
```python
from infra.analytics_logger import AnalyticsLogger

analytics_logger = None

def main():
    global analytics_logger
    analytics_logger = AnalyticsLogger()

# Track all button clicks
async def menu_button_handler(update, context):
    query = update.callback_query
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Log the action
    analytics_logger.log_action(
        user_id=user_id,
        chat_id=chat_id,
        action_type="button_click",
        action_data={"button": query.data}
    )
    
    # ... rest of handler ...

# Track analysis requests
async def analyze_symbol(symbol, user_id, chat_id):
    analytics_logger.log_action(
        user_id=user_id,
        chat_id=chat_id,
        action_type="analysis_request",
        action_data={"symbol": symbol}
    )
```

---

### 2.2 OCO Execution Results ⏱️ 30 min

**Modify `app/services/oco_tracker.py`**:
```python
def monitor_oco_pairs(mt5_service) -> Dict[str, str]:
    """Monitor OCO pairs and log execution results"""
    # ... existing code ...
    
    # After successful cancellation, log to journal
    if success:
        update_oco_status(pair.oco_group_id, "FILLED_A", f"Order A filled, B cancelled")
        
        # Log to journal
        try:
            from infra.journal_repo import JournalRepo
            journal = JournalRepo()
            journal.log_event({
                "event": "oco_triggered",
                "ticket": pair.order_a_ticket,
                "symbol": pair.symbol,
                "side": pair.order_a_side,
                "notes": f"OCO {pair.oco_group_id}: Order A filled, cancelled order B ({pair.order_b_ticket})"
            })
        except Exception as e:
            logger.error(f"Failed to log OCO result: {e}")
```

---

### 2.3 Trailing Stop Adjustments ⏱️ 45 min

**Modify `infra/trade_monitor.py`**:
```python
def check_trailing_stops(self) -> List[Dict[str, Any]]:
    """Check and log trailing stop adjustments"""
    actions = []
    
    # ... existing code ...
    
    if result.trailed:
        # Log the adjustment
        try:
            self.journal.log_event({
                "event": "trailing_stop_adjusted",
                "ticket": position.ticket,
                "symbol": position.symbol,
                "side": "BUY" if position.type == 0 else "SELL",
                "price": position.price_current,
                "sl": result.new_sl,
                "notes": (
                    f"Trailed from {position.sl:.5f} to {result.new_sl:.5f} | "
                    f"Method: {result.trail_method} | "
                    f"Momentum: {result.momentum_state} | "
                    f"R: {result.unrealized_r:.2f} | "
                    f"Distance: {result.trail_distance_atr:.2f}× ATR"
                )
            })
        except Exception as e:
            logger.error(f"Failed to log trailing stop: {e}")
```

---

## 🎯 Priority 3: Nice to Have (~2 hours)

### 3.1 Performance Dashboard ⏱️ 60 min

**Files to Create**:
- `infra/dashboard_queries.py`

**Implementation**:
```python
# infra/dashboard_queries.py
import sqlite3
from typing import Dict, List
from pathlib import Path

class PerformanceDashboard:
    """Query functions for performance analytics"""
    
    def __init__(self, db_path: str = "data/journal.sqlite"):
        self.db_path = Path(db_path)
    
    def get_recommendation_performance(self, days: int = 30) -> Dict:
        """Get AI recommendation performance metrics"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        # Overall stats
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed,
                SUM(CASE WHEN result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result_pnl < 0 THEN 1 ELSE 0 END) as losses,
                AVG(confidence) as avg_confidence,
                AVG(result_pnl) as avg_pnl,
                AVG(result_r) as avg_r
            FROM ai_recommendations
            WHERE created_at > ?
        """, (cutoff,))
        
        row = cur.fetchone()
        
        # By symbol
        cur.execute("""
            SELECT 
                symbol,
                COUNT(*) as count,
                SUM(CASE WHEN result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                AVG(result_pnl) as avg_pnl
            FROM ai_recommendations
            WHERE created_at > ? AND executed = 1
            GROUP BY symbol
            ORDER BY count DESC
        """, (cutoff,))
        
        by_symbol = {row[0]: {"count": row[1], "wins": row[2], "avg_pnl": row[3]} 
                     for row in cur.fetchall()}
        
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
    
    def get_signal_scanner_stats(self, days: int = 7) -> Dict:
        """Get signal scanner statistics"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cutoff = int(time.time()) - (days * 86400)
        
        cur.execute("""
            SELECT 
                symbol,
                direction,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence,
                SUM(CASE WHEN notified = 1 THEN 1 ELSE 0 END) as notified_count
            FROM signal_scanner_results
            WHERE detected_at > ?
            GROUP BY symbol, direction
            ORDER BY count DESC
        """, (cutoff,))
        
        signals = []
        for row in cur.fetchall():
            signals.append({
                "symbol": row[0],
                "direction": row[1],
                "count": row[2],
                "avg_confidence": row[3],
                "notified_count": row[4]
            })
        
        con.close()
        return {"signals": signals}
```

**Add dashboard command**:
```python
# In chatgpt_bot.py
async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show performance dashboard"""
    from infra.dashboard_queries import PerformanceDashboard
    
    dashboard = PerformanceDashboard()
    
    # Get stats
    rec_perf = dashboard.get_recommendation_performance(days=30)
    engagement = dashboard.get_user_engagement(days=30)
    
    msg = (
        f"📊 *Performance Dashboard (30 days)*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*AI Recommendations*\n"
        f"• Total: {rec_perf['total_recommendations']}\n"
        f"• Executed: {rec_perf['executed_count']} ({rec_perf['execution_rate']:.1f}%)\n"
        f"• Win Rate: {rec_perf['win_rate']:.1f}%\n"
        f"• Avg P&L: ${rec_perf['avg_pnl']:.2f}\n"
        f"• Avg R: {rec_perf['avg_r']:.2f}\n\n"
        f"*User Engagement*\n"
        f"• Total Actions: {engagement['total_actions']}\n"
        f"• Active Users: {engagement['unique_users']}\n"
        f"• Avg Actions/User: {engagement['avg_actions_per_user']:.1f}\n"
    )
    
    await update.message.reply_text(msg, parse_mode="Markdown")

# Register handler
app.add_handler(CommandHandler("dashboard", dashboard_command))
```

---

### 3.2 ML Training Data Export ⏱️ 30 min

**Files to Create**:
- `tools/export_ml_data.py`

**Implementation**:
```python
# tools/export_ml_data.py
import sqlite3
import pandas as pd
from pathlib import Path

def export_recommendation_training_data(output_path: str = "data/ml_training_data.csv"):
    """Export recommendation data for ML training"""
    con = sqlite3.connect("data/journal.sqlite")
    
    query = """
        SELECT 
            symbol,
            direction,
            confidence,
            entry_price,
            stop_loss,
            take_profit,
            risk_reward,
            market_regime,
            executed,
            result_pnl,
            result_r,
            CASE 
                WHEN result_pnl > 0 THEN 1 
                WHEN result_pnl < 0 THEN 0 
                ELSE NULL 
            END as win
        FROM ai_recommendations
        WHERE executed = 1 AND result_pnl IS NOT NULL
    """
    
    df = pd.read_sql_query(query, con)
    con.close()
    
    # Save to CSV
    df.to_csv(output_path, index=False)
    print(f"Exported {len(df)} recommendations to {output_path}")
    
    return df

if __name__ == "__main__":
    export_recommendation_training_data()
```

---

### 3.3 A/B Testing Framework ⏱️ 30 min

**Database Schema**:
```sql
CREATE TABLE IF NOT EXISTS ab_test_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    variant_a TEXT NOT NULL,
    variant_b TEXT NOT NULL,
    started_at INTEGER NOT NULL,
    ended_at INTEGER,
    active BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ab_test_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    variant TEXT CHECK(variant IN ('A', 'B')) NOT NULL,
    assigned_at INTEGER NOT NULL,
    FOREIGN KEY(experiment_id) REFERENCES ab_test_experiments(id),
    UNIQUE(experiment_id, user_id)
);
```

---

## 📅 Implementation Timeline

### Week 1: Priority 1
- **Day 1**: File logging + ChatGPT conversation DB
- **Day 2**: Recommendation logging + Signal scanner logging
- **Day 3**: Testing & bug fixes

### Week 2: Priority 2
- **Day 4**: User action analytics
- **Day 5**: OCO results + Trailing stop logs
- **Day 6**: Testing & integration

### Week 3: Priority 3
- **Day 7**: Performance dashboard
- **Day 8**: ML export + A/B testing framework
- **Day 9**: Final testing & documentation

---

## ✅ Testing Checklist

### Priority 1
- [ ] Log files created in `data/logs/`
- [ ] Log rotation works (test with 10MB limit)
- [ ] ChatGPT conversations saved to DB
- [ ] Conversations persist across bot restarts
- [ ] Recommendations logged with all fields
- [ ] Signal scanner results in DB
- [ ] High-confidence signals trigger notifications

### Priority 2
- [ ] User actions tracked for all buttons
- [ ] OCO execution results logged
- [ ] Trailing stop adjustments recorded
- [ ] Analytics queries return correct data

### Priority 3
- [ ] Dashboard command shows metrics
- [ ] ML export generates valid CSV
- [ ] A/B test assignments work

---

## 📊 Success Metrics

After implementation:
- ✅ 100% of trades logged
- ✅ 100% of recommendations tracked
- ✅ Full conversation history preserved
- ✅ Signal detection rate visible
- ✅ User behavior analytics available
- ✅ Performance metrics accessible
- ✅ ML training data exportable

---

**Status**: Ready for implementation 🚀
**Total Effort**: ~6 hours
**Priority**: HIGH

