"""
DTMS State Persistence Module

Handles saving and recovering DTMS trade registrations to/from database.
"""

import sqlite3
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import threading

logger = logging.getLogger(__name__)

# Database file path
DB_DIR = "data"
DB_FILE = os.path.join(DB_DIR, "dtms_trades.db")
_db_lock = threading.Lock()


def _ensure_db_dir():
    """Ensure database directory exists"""
    os.makedirs(DB_DIR, exist_ok=True)


def _get_connection() -> sqlite3.Connection:
    """Get database connection (thread-safe)"""
    _ensure_db_dir()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def _init_database():
    """Initialize database schema"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dtms_trades (
                ticket INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                volume REAL NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                registered_at TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
        """)
        
        # Create index on symbol for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol ON dtms_trades(symbol)
        """)
        
        conn.commit()
        conn.close()
        logger.info("✅ DTMS persistence database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize DTMS persistence database: {e}", exc_info=True)
        raise


def save_trade(ticket: int, symbol: str, direction: str, entry_price: float, 
               volume: float, stop_loss: Optional[float] = None, 
               take_profit: Optional[float] = None) -> bool:
    """
    Save trade to database (thread-safe).
    
    Returns:
        True if saved successfully, False otherwise
    """
    with _db_lock:
        try:
            conn = _get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            # Use INSERT OR REPLACE to handle updates
            cursor.execute("""
                INSERT OR REPLACE INTO dtms_trades 
                (ticket, symbol, direction, entry_price, volume, stop_loss, take_profit, registered_at, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, 
                    COALESCE((SELECT registered_at FROM dtms_trades WHERE ticket = ?), ?),
                    ?)
            """, (ticket, symbol, direction, entry_price, volume, stop_loss, take_profit, 
                  ticket, now, now))
            
            conn.commit()
            conn.close()
            logger.debug(f"✅ Saved trade {ticket} to DTMS persistence database")
            return True
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                logger.warning("DTMS trades table not found, initializing database...")
                try:
                    _init_database()
                    # Retry save
                    return save_trade(ticket, symbol, direction, entry_price, volume, stop_loss, take_profit)
                except Exception as init_error:
                    logger.error(f"❌ Failed to initialize database and save trade {ticket}: {init_error}")
                    return False
            else:
                logger.error(f"❌ Database error saving trade {ticket}: {e}", exc_info=True)
                return False
        except Exception as e:
            logger.error(f"❌ Error saving trade {ticket} to database: {e}", exc_info=True)
            return False


def remove_trade(ticket: int) -> bool:
    """
    Remove trade from database (thread-safe).
    
    Returns:
        True if removed successfully, False otherwise
    """
    with _db_lock:
        try:
            conn = _get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM dtms_trades WHERE ticket = ?", (ticket,))
            
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            
            if deleted:
                logger.debug(f"✅ Removed trade {ticket} from DTMS persistence database")
            return deleted
        except Exception as e:
            logger.error(f"❌ Error removing trade {ticket} from database: {e}", exc_info=True)
            return False


def get_all_trades() -> List[Dict[str, Any]]:
    """
    Get all trades from database (thread-safe).
    
    Returns:
        List of trade dictionaries
    """
    with _db_lock:
        try:
            conn = _get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM dtms_trades")
            rows = cursor.fetchall()
            conn.close()
            
            trades = []
            for row in rows:
                trades.append({
                    "ticket": row["ticket"],
                    "symbol": row["symbol"],
                    "direction": row["direction"],
                    "entry_price": row["entry_price"],
                    "volume": row["volume"],
                    "stop_loss": row["stop_loss"],
                    "take_profit": row["take_profit"],
                    "registered_at": row["registered_at"],
                    "last_updated": row["last_updated"]
                })
            
            return trades
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                logger.warning("DTMS trades table not found, initializing database...")
                _init_database()
                return []
            else:
                logger.error(f"❌ Database error getting trades: {e}", exc_info=True)
                return []
        except Exception as e:
            logger.error(f"❌ Error getting trades from database: {e}", exc_info=True)
            return []


def recover_trades_from_database(mt5_service) -> List[Dict[str, Any]]:
    """
    Recover trades from database and verify they still exist in MT5.
    
    Args:
        mt5_service: MT5Service instance to verify trades exist
        
    Returns:
        List of valid trades that exist in both database and MT5
    """
    try:
        # Wait for MT5 connection
        if not mt5_service:
            logger.warning("MT5 service not provided - skipping trade recovery")
            return []
        
        # Check if MT5 is connected
        if not hasattr(mt5_service, '_connected') or not mt5_service._connected:
            # Try to connect if not connected
            if not mt5_service.connect():
                logger.warning("MT5 not connected - skipping trade recovery")
                return []
        
        db_trades = get_all_trades()
        if not db_trades:
            logger.info("No trades found in DTMS persistence database")
            return []
        
        logger.info(f"Found {len(db_trades)} trades in DTMS persistence database, verifying with MT5...")
        
        valid_trades = []
        invalid_tickets = []
        
        for trade in db_trades:
            ticket = trade["ticket"]
            
            try:
                # Verify trade exists in MT5
                positions = mt5_service.get_positions()
                if positions:
                    # Check if ticket exists in positions
                    position_found = False
                    for pos in positions:
                        # Handle both object and dict formats
                        pos_ticket = pos.ticket if hasattr(pos, 'ticket') else pos.get('ticket') if isinstance(pos, dict) else None
                        if pos_ticket == ticket:
                            position_found = True
                            break
                    
                    if position_found:
                        # Trade exists in MT5 - add to valid list
                        valid_trades.append(trade)
                        logger.debug(f"✅ Trade {ticket} verified in MT5")
                    else:
                        # Trade in database but not in MT5 - remove from database
                        logger.warning(f"Trade {ticket} in database but not in MT5 - removing from database")
                        remove_trade(ticket)
                        invalid_tickets.append(ticket)
                else:
                    # No positions in MT5 - remove from database
                    logger.warning(f"Trade {ticket} in database but no positions in MT5 - removing from database")
                    remove_trade(ticket)
                    invalid_tickets.append(ticket)
            except Exception as e:
                logger.warning(f"Error verifying trade {ticket} with MT5: {e}")
                # On error, assume trade is invalid and remove from database
                remove_trade(ticket)
                invalid_tickets.append(ticket)
        
        if invalid_tickets:
            logger.info(f"Removed {len(invalid_tickets)} invalid trades from database: {invalid_tickets}")
        
        logger.info(f"✅ Recovered {len(valid_trades)} valid trades from DTMS persistence database")
        return valid_trades
        
    except Exception as e:
        logger.error(f"❌ Error recovering trades from database: {e}", exc_info=True)
        return []


def cleanup_closed_trades(mt5_service, active_tickets: List[int]) -> int:
    """
    Clean up trades from database that are no longer in MT5.
    
    Args:
        mt5_service: MT5Service instance
        active_tickets: List of tickets that are currently active in DTMS
        
    Returns:
        Number of trades cleaned up
    """
    try:
        db_trades = get_all_trades()
        if not db_trades:
            return 0
        
        cleaned = 0
        for trade in db_trades:
            ticket = trade["ticket"]
            
            # Skip if ticket is in active list
            if ticket in active_tickets:
                continue
            
            try:
                # Check if trade still exists in MT5
                positions = mt5_service.get_positions()
                position_found = False
                if positions:
                    for pos in positions:
                        pos_ticket = pos.ticket if hasattr(pos, 'ticket') else pos.get('ticket') if isinstance(pos, dict) else None
                        if pos_ticket == ticket:
                            position_found = True
                            break
                
                if not position_found:
                    # Trade not in MT5 - remove from database
                    remove_trade(ticket)
                    cleaned += 1
                    logger.debug(f"Cleaned up closed trade {ticket} from database")
            except Exception:
                # On error, assume trade is closed and remove
                remove_trade(ticket)
                cleaned += 1
        
        if cleaned > 0:
            logger.info(f"✅ Cleaned up {cleaned} closed trades from DTMS persistence database")
        
        return cleaned
        
    except Exception as e:
        logger.error(f"❌ Error cleaning up closed trades: {e}", exc_info=True)
        return 0


def handle_database_corruption():
    """Handle database corruption by recreating database"""
    try:
        logger.warning("DTMS persistence database appears corrupted, recreating...")
        
        # Backup old database
        if os.path.exists(DB_FILE):
            backup_file = f"{DB_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(DB_FILE, backup_file)
            logger.info(f"Backed up corrupted database to {backup_file}")
        
        # Recreate database
        _init_database()
        logger.info("✅ DTMS persistence database recreated successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to recreate DTMS persistence database: {e}", exc_info=True)
        return False

