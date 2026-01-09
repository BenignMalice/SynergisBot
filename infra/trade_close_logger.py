"""
Trade Close Logger
Detects and logs manually closed trades (or trades closed by SL/TP).
Shared utility for both desktop_agent.py and chatgpt_bot.py.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Set
from datetime import datetime

import MetaTrader5 as mt5

from infra.journal_repo import JournalRepo

logger = logging.getLogger(__name__)


class TradeCloseLogger:
    """
    Monitors open trades and logs when they close.
    Detects manual closes, SL/TP hits, and other close reasons.
    """
    
    def __init__(self, journal_repo: JournalRepo):
        """
        Initialize trade close logger.
        
        Args:
            journal_repo: JournalRepo instance for database logging
        """
        self.journal_repo = journal_repo
        self.tracked_tickets: Set[int] = set()  # Tickets we're currently tracking
        logger.info("TradeCloseLogger initialized")
    
    def sync_tracked_tickets(self, current_mt5_tickets: Set[int]) -> None:
        """
        Sync our tracked tickets with current MT5 positions.
        
        Args:
            current_mt5_tickets: Set of ticket numbers currently open in MT5
        """
        # Add any new MT5 positions we're not tracking yet
        new_tickets = current_mt5_tickets - self.tracked_tickets
        if new_tickets:
            logger.info(f"📊 Now tracking {len(new_tickets)} new positions: {new_tickets}")
            self.tracked_tickets.update(new_tickets)
    
    def check_for_closed_trades(self) -> List[Dict[str, Any]]:
        """
        Check for trades that have closed since last check.
        
        Returns:
            List of dictionaries with close information:
            [
                {
                    "ticket": int,
                    "symbol": str,
                    "close_price": float,
                    "close_time": int (timestamp),
                    "close_reason": str,
                    "profit": float,
                    "volume": float,
                    "comment": str
                },
                ...
            ]
        """
        # Get current open positions from MT5
        positions = mt5.positions_get()
        current_mt5_tickets = {pos.ticket for pos in positions} if positions else set()
        
        # Find tickets that closed (were tracked but are now gone)
        closed_tickets = self.tracked_tickets - current_mt5_tickets
        
        if not closed_tickets:
            return []
        
        logger.info(f"🔍 Detected {len(closed_tickets)} closed trades: {closed_tickets}")
        
        closed_trades = []
        
        for ticket in closed_tickets:
            try:
                # Get trade history for this ticket
                close_info = self._get_close_info_from_history(ticket)
                
                if close_info:
                    closed_trades.append(close_info)
                    
                    # Log to database
                    self._log_trade_close(close_info)
                    
                    logger.info(f"✅ Logged close for ticket {ticket}: {close_info['close_reason']}")
                else:
                    logger.warning(f"⚠️ Could not find history for ticket {ticket}")
            
            except Exception as e:
                logger.error(f"❌ Error processing closed ticket {ticket}: {e}", exc_info=True)
        
        # Remove closed tickets from tracking
        self.tracked_tickets -= closed_tickets
        
        return closed_trades
    
    def _get_close_info_from_history(self, ticket: int) -> Optional[Dict[str, Any]]:
        """
        Get close information from MT5 history.
        
        Args:
            ticket: Position ticket number
            
        Returns:
            Dictionary with close information, or None if not found
        """
        try:
            # Get deals for this ticket
            deals = mt5.history_deals_get(position=ticket)
            
            if not deals or len(deals) == 0:
                return None
            
            # Find the closing deal (last deal for the position)
            close_deal = None
            open_deal = None
            
            for deal in deals:
                if deal.entry == mt5.DEAL_ENTRY_IN:  # Entry deal
                    open_deal = deal
                elif deal.entry == mt5.DEAL_ENTRY_OUT:  # Exit deal
                    close_deal = deal
            
            if not close_deal:
                logger.warning(f"No closing deal found for ticket {ticket}")
                return None
            
            # Determine close reason
            close_reason = self._determine_close_reason(close_deal, open_deal)
            
            # Calculate profit
            profit = close_deal.profit if close_deal else 0.0
            
            return {
                "ticket": ticket,
                "symbol": close_deal.symbol if close_deal else "UNKNOWN",
                "close_price": close_deal.price if close_deal else 0.0,
                "close_time": close_deal.time if close_deal else int(time.time()),
                "close_reason": close_reason,
                "profit": profit,
                "volume": close_deal.volume if close_deal else 0.0,
                "comment": close_deal.comment if close_deal else ""
            }
        
        except Exception as e:
            logger.error(f"Error getting close info for ticket {ticket}: {e}", exc_info=True)
            return None
    
    def _determine_close_reason(self, close_deal, open_deal) -> str:
        """
        Determine why the trade was closed based on deal information.
        
        Args:
            close_deal: MT5 deal object for close
            open_deal: MT5 deal object for open (optional)
            
        Returns:
            Human-readable close reason
        """
        if not close_deal:
            return "unknown"
        
        comment = close_deal.comment.lower()
        
        # Check comment for clues
        if "sl" in comment or "stop loss" in comment:
            return "stop_loss"
        elif "tp" in comment or "take profit" in comment:
            return "take_profit"
        elif "loss_cut" in comment or "profit_protect" in comment:
            return comment  # Use the specific reason from our bot
        elif "partial" in comment:
            return "partial_profit"
        elif "manual" in comment or comment == "":
            return "manual"
        elif "rollover" in comment:
            return "rollover"
        elif "margin" in comment:
            return "margin_call"
        else:
            # If comment doesn't tell us, check deal reason
            if hasattr(close_deal, 'reason'):
                reason = close_deal.reason
                if reason == mt5.DEAL_REASON_SL:
                    return "stop_loss"
                elif reason == mt5.DEAL_REASON_TP:
                    return "take_profit"
                elif reason == mt5.DEAL_REASON_SO:
                    return "margin_call"
            
            # Default to manual if we can't determine
            return "manual"
    
    def _log_trade_close(self, close_info: Dict[str, Any]) -> None:
        """
        Log trade close to database.
        
        Args:
            close_info: Dictionary with close information
        """
        try:
            # Update trade in database
            trade_found = self.journal_repo.close_trade(
                ticket=close_info["ticket"],
                closed_ts=close_info["close_time"],
                exit_price=close_info["close_price"],
                close_reason=close_info["close_reason"],
                pnl=close_info["profit"]
            )
            
            # If trade not found in DB, it was probably never logged (old trade)
            if not trade_found:
                logger.debug(f"Skipping close logging for ticket {close_info['ticket']} (not in database)")
                return
            
            # Also add an event
            self.journal_repo.add_event(
                event="trade_closed",
                ticket=close_info["ticket"],
                symbol=close_info["symbol"],
                price=close_info["close_price"],
                pnl=close_info["profit"],
                reason=close_info["close_reason"],
                extra={
                    "volume": close_info["volume"],
                    "comment": close_info["comment"],
                    "detected_by": "trade_close_logger"
                }
            )
            
            logger.debug(f"Logged close to database for ticket {close_info['ticket']}")
            
            # ============================================================================
            # UPDATE V8 ANALYTICS (NEW)
            # ============================================================================
            try:
                from infra.advanced_analytics import V8FeatureTracker
                
                # Calculate R-multiple if we have the history
                deals = mt5.history_deals_get(position=close_info["ticket"])
                if deals and len(deals) >= 2:
                    entry_deal = deals[0]  # First deal (entry)
                    close_deal = deals[-1]  # Last deal (exit)
                    
                    entry_price = entry_deal.price
                    exit_price = close_deal.price
                    profit = close_info["profit"]
                    
                    # Calculate R-multiple (rough estimate)
                    # This is simplified - ideally we'd get SL from database
                    if abs(profit) > 0.01:  # Avoid division by zero
                        # Estimate based on profit
                        r_multiple = profit / 100.0  # Rough estimate
                    else:
                        r_multiple = 0.0
                    
                    # Determine outcome
                    if profit > 0:
                        outcome = "win"
                    elif profit < 0:
                        outcome = "loss"
                    else:
                        outcome = "breakeven"
                    
                    # Update V8 analytics
                    v8_tracker = V8FeatureTracker()
                    v8_tracker.update_trade_outcome(
                        ticket=close_info["ticket"],
                        outcome=outcome,
                        exit_price=exit_price,
                        profit_loss=profit,
                        r_multiple=r_multiple
                    )
                    
                    logger.debug(f"Updated V8 analytics for ticket {close_info['ticket']}: {outcome}, R={r_multiple:.2f}")
            
            except Exception as e:
                logger.debug(f"Could not update V8 analytics for ticket {close_info['ticket']}: {e}")
                # Not critical, continue
            
        except Exception as e:
            logger.error(f"Failed to log trade close to database: {e}", exc_info=True)
    
    def force_check_all_open_trades(self) -> None:
        """
        Force check all trades in database that are marked as open
        and verify they're still open in MT5. Close any that aren't.
        
        This is useful on startup to catch any trades that closed
        while the system was offline.
        """
        logger.info("🔍 Force checking all open trades in database...")
        
        try:
            # Get all open trades from database
            open_trades = self.journal_repo.get_open_trades()
            
            if not open_trades:
                logger.info("No open trades in database")
                return
            
            # Get current MT5 positions
            positions = mt5.positions_get()
            current_mt5_tickets = {pos.ticket for pos in positions} if positions else set()
            
            # Check each database trade
            for trade in open_trades:
                ticket = trade.get('ticket')
                
                if not ticket:
                    continue
                
                if ticket not in current_mt5_tickets:
                    # Trade is marked open in DB but not in MT5 - it must have closed
                    logger.warning(f"⚠️ Trade {ticket} is open in DB but not in MT5 - logging close")
                    
                    close_info = self._get_close_info_from_history(ticket)
                    
                    if close_info:
                        self._log_trade_close(close_info)
                        logger.info(f"✅ Logged missed close for ticket {ticket}")
                    else:
                        # Couldn't find history, mark as closed with unknown reason
                        logger.debug(f"⚠️ No history found for {ticket}, attempting to mark as closed (unknown)")
                        trade_found = self.journal_repo.close_trade(
                            ticket=ticket,
                            closed_ts=int(time.time()),
                            exit_price=0.0,
                            close_reason="unknown_offline_close",
                            pnl=0.0
                        )
                        if trade_found:
                            logger.info(f"✅ Marked ticket {ticket} as closed (unknown)")
                        else:
                            logger.debug(f"Skipping {ticket} (not in database)")
                else:
                    # Trade is still open - add to tracked tickets
                    self.tracked_tickets.add(ticket)
            
            logger.info(f"✅ Force check complete. Now tracking {len(self.tracked_tickets)} open trades")
            
        except Exception as e:
            logger.error(f"Error during force check: {e}", exc_info=True)


# Global instance (can be shared)
_close_logger_instance = None


def get_close_logger() -> TradeCloseLogger:
    """
    Get or create the global TradeCloseLogger instance.
    
    Returns:
        TradeCloseLogger instance
    """
    global _close_logger_instance
    
    if _close_logger_instance is None:
        journal_repo = JournalRepo()
        _close_logger_instance = TradeCloseLogger(journal_repo)
    
    return _close_logger_instance

