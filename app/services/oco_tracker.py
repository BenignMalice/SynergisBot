"""
OCO (One-Cancels-Other) Order Tracker for API
==============================================

Tracks paired orders and automatically cancels the opposite order when one fills.
Designed for the FastAPI integration where ChatGPT places bracket trades.
"""

import sqlite3
import time
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = "data/oco_tracker.db"

@dataclass
class OCOPair:
    """Represents a pair of orders linked by OCO logic"""
    id: Optional[int]
    oco_group_id: str  # Unique identifier for this OCO pair
    symbol: str
    order_a_ticket: int  # MT5 ticket number for first order
    order_b_ticket: int  # MT5 ticket number for second order
    order_a_side: str  # "BUY" or "SELL"
    order_b_side: str  # "BUY" or "SELL"
    order_a_entry: float
    order_b_entry: float
    status: str  # "ACTIVE", "FILLED_A", "FILLED_B", "CANCELLED", "BOTH_FILLED"
    created_at: int
    updated_at: int
    chat_id: Optional[int] = None  # For notifications (optional)
    comment: str = ""


def ensure_schema():
    """Create the OCO tracking database table if it doesn't exist"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS oco_pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oco_group_id TEXT NOT NULL UNIQUE,
            symbol TEXT NOT NULL,
            order_a_ticket INTEGER NOT NULL,
            order_b_ticket INTEGER NOT NULL,
            order_a_side TEXT NOT NULL,
            order_b_side TEXT NOT NULL,
            order_a_entry REAL NOT NULL,
            order_b_entry REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            chat_id INTEGER,
            comment TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_oco_status ON oco_pairs(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_oco_group ON oco_pairs(oco_group_id)")
    con.commit()
    con.close()


def create_oco_pair(
    symbol: str,
    order_a_ticket: int,
    order_b_ticket: int,
    order_a_side: str,
    order_b_side: str,
    order_a_entry: float,
    order_b_entry: float,
    oco_group_id: Optional[str] = None,
    chat_id: Optional[int] = None,
    comment: str = ""
) -> str:
    """
    Register a new OCO pair.
    
    Returns:
        oco_group_id: The unique identifier for this OCO pair
    """
    ensure_schema()
    
    if not oco_group_id:
        oco_group_id = f"OCO_{symbol}_{int(time.time())}_{order_a_ticket}"
    
    now = int(time.time())
    
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    try:
        cur.execute("""
            INSERT INTO oco_pairs (
                oco_group_id, symbol, order_a_ticket, order_b_ticket,
                order_a_side, order_b_side, order_a_entry, order_b_entry,
                status, created_at, updated_at, chat_id, comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?)
        """, (
            oco_group_id, symbol, order_a_ticket, order_b_ticket,
            order_a_side, order_b_side, order_a_entry, order_b_entry,
            now, now, chat_id, comment
        ))
        con.commit()
        logger.info(f"Created OCO pair: {oco_group_id} ({order_a_ticket} + {order_b_ticket})")
        return oco_group_id
    except sqlite3.IntegrityError:
        logger.error(f"OCO pair {oco_group_id} already exists")
        raise
    finally:
        con.close()


def get_active_oco_pairs() -> List[OCOPair]:
    """Get all active OCO pairs that need monitoring"""
    ensure_schema()
    
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    cur.execute("""
        SELECT id, oco_group_id, symbol, order_a_ticket, order_b_ticket,
               order_a_side, order_b_side, order_a_entry, order_b_entry,
               status, created_at, updated_at, chat_id, comment
        FROM oco_pairs
        WHERE status = 'ACTIVE'
    """)
    
    rows = cur.fetchall()
    con.close()
    
    pairs = []
    for row in rows:
        pairs.append(OCOPair(
            id=row[0],
            oco_group_id=row[1],
            symbol=row[2],
            order_a_ticket=row[3],
            order_b_ticket=row[4],
            order_a_side=row[5],
            order_b_side=row[6],
            order_a_entry=row[7],
            order_b_entry=row[8],
            status=row[9],
            created_at=row[10],
            updated_at=row[11],
            chat_id=row[12],
            comment=row[13] or ""
        ))
    
    return pairs


def get_pair_by_group(oco_group_id: str) -> Optional[OCOPair]:
    """Fetch a single OCO pair by its group id regardless of status."""
    ensure_schema()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    try:
        cur.execute(
            """
            SELECT id, oco_group_id, symbol, order_a_ticket, order_b_ticket,
                   order_a_side, order_b_side, order_a_entry, order_b_entry,
                   status, created_at, updated_at, chat_id, comment
            FROM oco_pairs
            WHERE oco_group_id = ?
            """,
            (oco_group_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return OCOPair(
            id=row[0],
            oco_group_id=row[1],
            symbol=row[2],
            order_a_ticket=row[3],
            order_b_ticket=row[4],
            order_a_side=row[5],
            order_b_side=row[6],
            order_a_entry=row[7],
            order_b_entry=row[8],
            status=row[9],
            created_at=row[10],
            updated_at=row[11],
            chat_id=row[12],
            comment=row[13] or "",
        )
    finally:
        con.close()


def update_oco_status(oco_group_id: str, new_status: str, comment: str = ""):
    """Update the status of an OCO pair"""
    ensure_schema()
    
    now = int(time.time())
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    if comment:
        cur.execute("""
            UPDATE oco_pairs
            SET status = ?, updated_at = ?, comment = ?
            WHERE oco_group_id = ?
        """, (new_status, now, comment, oco_group_id))
    else:
        cur.execute("""
            UPDATE oco_pairs
            SET status = ?, updated_at = ?
            WHERE oco_group_id = ?
        """, (new_status, now, oco_group_id))
    
    con.commit()
    con.close()
    
    logger.info(f"Updated OCO {oco_group_id}: {new_status}")


def check_order_exists(mt5_service, ticket: int) -> Tuple[bool, str]:
    """
    Check if an MT5 order still exists (pending) or has been filled/cancelled.
    
    Returns:
        (exists_as_pending, state) where state is "pending", "filled", or "cancelled"
    """
    import MetaTrader5 as mt5
    
    try:
        mt5_service.connect()
        
        # Check if order is still pending
        orders = mt5.orders_get(ticket=ticket)
        if orders and len(orders) > 0:
            return True, "pending"
        
        # Check history to see if order was filled or cancelled
        from_date = datetime(2025, 1, 1)  # Start of 2025
        to_date = datetime.now()
        
        # Get order history - this shows the final state of the order
        history_orders = mt5.history_orders_get(
            from_date,
            to_date,
            position=ticket
        )
        
        if history_orders:
            for hist_order in history_orders:
                if hist_order.ticket == ticket:
                    # Check the order state
                    if hist_order.state == mt5.ORDER_STATE_FILLED:
                        return False, "filled"
                    elif hist_order.state in [mt5.ORDER_STATE_CANCELED, mt5.ORDER_STATE_REJECTED, mt5.ORDER_STATE_EXPIRED]:
                        return False, "cancelled"
        
        # If not in history, check recent deals for this ticket
        deals = mt5.history_deals_get(from_date, to_date)
        if deals:
            for deal in deals:
                if deal.order == ticket:
                    return False, "filled"
        
        # Order doesn't exist anywhere - likely cancelled or very old
        return False, "cancelled"
        
    except Exception as e:
        logger.error(f"Error checking order {ticket}: {e}")
        return False, "unknown"


def cancel_order(mt5_service, ticket: int, symbol: str) -> bool:
    """Cancel a pending order in MT5"""
    import MetaTrader5 as mt5
    
    try:
        mt5_service.connect()
        mt5_service.ensure_symbol(symbol)
        
        # Get the order first
        orders = mt5.orders_get(ticket=ticket)
        if not orders or len(orders) == 0:
            logger.warning(f"Order {ticket} not found (already filled/cancelled?)")
            return False
        
        order = orders[0]
        
        # Create close request
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
            "symbol": symbol,
        }
        
        result = mt5.order_send(request)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Successfully cancelled order {ticket}")
            return True
        else:
            error_msg = f"Failed to cancel order {ticket}: retcode={result.retcode if result else 'None'}"
            logger.error(error_msg)
            return False
            
    except Exception as e:
        logger.error(f"Error cancelling order {ticket}: {e}", exc_info=True)
        return False


def monitor_oco_pairs(mt5_service) -> Dict[str, str]:
    """
    Monitor all active OCO pairs and cancel opposite orders when one fills.
    
    Returns:
        Dictionary of {oco_group_id: action_taken}
    """
    pairs = get_active_oco_pairs()
    
    if not pairs:
        return {}
    
    actions = {}
    
    for pair in pairs:
        try:
            # Check status of both orders
            a_exists, a_state = check_order_exists(mt5_service, pair.order_a_ticket)
            b_exists, b_state = check_order_exists(mt5_service, pair.order_b_ticket)
            
            # Case 1: Order A filled, cancel Order B
            if a_state == "filled" and b_exists and b_state == "pending":
                logger.info(f"OCO {pair.oco_group_id}: Order A ({pair.order_a_ticket}) filled, cancelling Order B ({pair.order_b_ticket})")
                success = cancel_order(mt5_service, pair.order_b_ticket, pair.symbol)
                if success:
                    update_oco_status(pair.oco_group_id, "FILLED_A", f"Order A filled, B cancelled")
                    actions[pair.oco_group_id] = f"Order A ({pair.order_a_side} @ {pair.order_a_entry}) filled → cancelled B"
                    
                    # Log to journal
                    _log_oco_result(pair, "A", pair.order_a_ticket, pair.order_b_ticket)
                else:
                    actions[pair.oco_group_id] = f"Order A filled but failed to cancel B"
            
            # Case 2: Order B filled, cancel Order A
            elif b_state == "filled" and a_exists and a_state == "pending":
                logger.info(f"OCO {pair.oco_group_id}: Order B ({pair.order_b_ticket}) filled, cancelling Order A ({pair.order_a_ticket})")
                success = cancel_order(mt5_service, pair.order_a_ticket, pair.symbol)
                if success:
                    update_oco_status(pair.oco_group_id, "FILLED_B", f"Order B filled, A cancelled")
                    actions[pair.oco_group_id] = f"Order B ({pair.order_b_side} @ {pair.order_b_entry}) filled → cancelled A"
                    
                    # Log to journal
                    _log_oco_result(pair, "B", pair.order_b_ticket, pair.order_a_ticket)
                else:
                    actions[pair.oco_group_id] = f"Order B filled but failed to cancel A"
            
            # Case 3: Both filled (shouldn't happen, but track it)
            elif a_state == "filled" and b_state == "filled":
                logger.warning(f"OCO {pair.oco_group_id}: BOTH orders filled! OCO failed.")
                update_oco_status(pair.oco_group_id, "BOTH_FILLED", "WARNING: Both orders filled")
                actions[pair.oco_group_id] = "BOTH FILLED (OCO FAILURE)"
                
                # Log OCO failure
                _log_oco_failure(pair)
            
            # Case 4: Both cancelled/gone
            elif not a_exists and not b_exists:
                logger.info(f"OCO {pair.oco_group_id}: Both orders gone, marking as cancelled")
                update_oco_status(pair.oco_group_id, "CANCELLED", "Both orders cancelled/expired")
                actions[pair.oco_group_id] = "Both cancelled"
            
        except Exception as e:
            logger.error(f"Error monitoring OCO pair {pair.oco_group_id}: {e}", exc_info=True)
            actions[pair.oco_group_id] = f"Error: {str(e)}"
    
    return actions


def _log_oco_result(pair: OCOPair, filled_order: str, filled_ticket: int, cancelled_ticket: int):
    """Log OCO execution result to journal"""
    try:
        from infra.journal_repo import JournalRepo
        journal = JournalRepo()
        
        filled_side = pair.order_a_side if filled_order == "A" else pair.order_b_side
        filled_entry = pair.order_a_entry if filled_order == "A" else pair.order_b_entry
        cancelled_side = pair.order_b_side if filled_order == "A" else pair.order_a_side
        
        journal.log_event(
            "oco_triggered",
            ticket=filled_ticket,
            symbol=pair.symbol,
            side=filled_side,
            price=filled_entry,
            notes=(
                f"OCO {pair.oco_group_id}: {filled_side} order filled @ {filled_entry:.5f}, "
                f"cancelled opposite {cancelled_side} order (ticket {cancelled_ticket})"
            ),
        )
        logger.info(f"Logged OCO result to journal: {pair.oco_group_id}")
    except Exception as e:
        logger.error(f"Failed to log OCO result: {e}")


def _log_oco_failure(pair: OCOPair):
    """Log OCO failure (both orders filled)"""
    try:
        from infra.journal_repo import JournalRepo
        journal = JournalRepo()
        
        journal.log_event(
            "oco_failure",
            symbol=pair.symbol,
            notes=(
                f"OCO FAILURE {pair.oco_group_id}: BOTH orders filled! "
                f"A: {pair.order_a_side} @ {pair.order_a_entry:.5f} (ticket {pair.order_a_ticket}), "
                f"B: {pair.order_b_side} @ {pair.order_b_entry:.5f} (ticket {pair.order_b_ticket})"
            ),
        )
        logger.warning(f"Logged OCO failure to journal: {pair.oco_group_id}")
    except Exception as e:
        logger.error(f"Failed to log OCO failure: {e}")


def get_oco_stats() -> Dict[str, int]:
    """Get statistics about OCO pairs"""
    ensure_schema()
    
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    cur.execute("SELECT status, COUNT(*) FROM oco_pairs GROUP BY status")
    rows = cur.fetchall()
    con.close()
    
    stats = {row[0]: row[1] for row in rows}
    return stats


def link_existing_orders(
    mt5_service,
    symbol: str,
    ticket_a: int,
    ticket_b: int
) -> Optional[str]:
    """
    Link two existing MT5 orders as an OCO pair.
    Useful for manually linking orders that were already placed.
    
    Returns:
        oco_group_id if successful, None if failed
    """
    import MetaTrader5 as mt5
    
    try:
        mt5_service.connect()
        
        # Get both orders
        orders_a = mt5.orders_get(ticket=ticket_a)
        orders_b = mt5.orders_get(ticket=ticket_b)
        
        if not orders_a or len(orders_a) == 0:
            logger.error(f"Order {ticket_a} not found")
            return None
        
        if not orders_b or len(orders_b) == 0:
            logger.error(f"Order {ticket_b} not found")
            return None
        
        order_a = orders_a[0]
        order_b = orders_b[0]
        
        # Determine sides
        side_a = "BUY" if order_a.type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP] else "SELL"
        side_b = "BUY" if order_b.type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP] else "SELL"
        
        # Create OCO pair
        oco_group_id = create_oco_pair(
            symbol=symbol,
            order_a_ticket=ticket_a,
            order_b_ticket=ticket_b,
            order_a_side=side_a,
            order_b_side=side_b,
            order_a_entry=order_a.price_open,
            order_b_entry=order_b.price_open,
            comment="Manually linked via API"
        )
        
        logger.info(f"Successfully linked orders {ticket_a} + {ticket_b} as OCO: {oco_group_id}")
        return oco_group_id
        
    except Exception as e:
        logger.error(f"Error linking orders: {e}", exc_info=True)
        return None

