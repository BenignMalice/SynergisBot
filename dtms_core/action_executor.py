"""
DTMS Action Executor
Executes defensive trade management actions (SL adjustments, partial closes, hedges)
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from dtms_config import get_config

logger = logging.getLogger(__name__)

@dataclass
class ActionResult:
    """Result of an action execution"""
    success: bool
    action_type: str
    details: Dict[str, Any]
    error_message: Optional[str] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class DTMSActionExecutor:
    """
    Executes defensive trade management actions.
    
    Actions:
    - tighten_sl: Move SL closer to current price
    - partial_close: Close portion of position
    - move_sl_breakeven: Move SL to entry price
    - open_hedge: Open opposite position
    - close_hedge: Close hedge position
    - close_all: Close all positions
    - re_add_position: Re-add closed position
    """
    
    def __init__(self, mt5_service, telegram_service=None):
        self.mt5_service = mt5_service
        self.telegram_service = telegram_service
        self.config = get_config()
        
        # Action history
        self.action_history: List[ActionResult] = []
        
        logger.info("DTMSActionExecutor initialized")
    
    def execute_actions(self, actions: List[Dict[str, Any]], trade_data: Dict[str, Any]) -> List[ActionResult]:
        """
        Execute a list of actions for a trade.
        
        Args:
            actions: List of action dictionaries
            trade_data: Trade information
            
        Returns:
            List of ActionResult objects
        """
        try:
            results = []
            
            for action in actions:
                result = self._execute_single_action(action, trade_data)
                results.append(result)
                self.action_history.append(result)
                
                # Log action
                if result.success:
                    logger.info(f"Action executed successfully: {action['type']} for trade {trade_data.get('ticket')}")
                else:
                    logger.error(f"Action failed: {action['type']} for trade {trade_data.get('ticket')} - {result.error_message}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to execute actions: {e}")
            return [ActionResult(
                success=False,
                action_type="batch_execution",
                details={},
                error_message=str(e)
            )]
    
    def _execute_single_action(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
        """Execute a single action"""
        try:
            action_type = action.get('type', 'unknown')
            
            if action_type == 'tighten_sl':
                return self._tighten_sl(action, trade_data)
            elif action_type == 'partial_close':
                return self._partial_close(action, trade_data)
            elif action_type == 'move_sl_breakeven':
                return self._move_sl_breakeven(action, trade_data)
            elif action_type == 'open_hedge':
                return self._open_hedge(action, trade_data)
            elif action_type == 'close_hedge':
                return self._close_hedge(action, trade_data)
            elif action_type == 'close_all':
                return self._close_all(action, trade_data)
            elif action_type == 're_add_position':
                return self._re_add_position(action, trade_data)
            elif action_type == 'start_flat_timer':
                return self._start_flat_timer(action, trade_data)
            elif action_type == 'stop_flat_timer':
                return self._stop_flat_timer(action, trade_data)
            elif action_type == 'start_recovery_timer':
                return self._start_recovery_timer(action, trade_data)
            else:
                return ActionResult(
                    success=False,
                    action_type=action_type,
                    details=action,
                    error_message=f"Unknown action type: {action_type}"
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=action.get('type', 'unknown'),
                details=action,
                error_message=str(e)
            )
    
    def _tighten_sl(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
        """Tighten stop loss to specified level"""
        try:
            ticket = trade_data.get('ticket')
            symbol = trade_data.get('symbol')
            direction = trade_data.get('direction')
            current_price = trade_data.get('current_price', 0)
            entry_price = trade_data.get('entry_price', 0)
            current_volume = trade_data.get('current_volume', 0)
            
            if not all([ticket, symbol, direction, current_price, entry_price, current_volume]):
                return ActionResult(
                    success=False,
                    action_type='tighten_sl',
                    details=action,
                    error_message="Missing required trade data"
                )
            
            # Calculate new SL based on action parameters
            target_sl = action.get('target_sl', '0.3R_behind_price')
            
            if target_sl == '0.3R_behind_price':
                # Calculate 0.3R behind current price
                risk_size = abs(entry_price - trade_data.get('initial_sl', entry_price))
                if direction == 'BUY':
                    new_sl = current_price - (0.3 * risk_size)
                else:  # SELL
                    new_sl = current_price + (0.3 * risk_size)
            else:
                new_sl = float(target_sl)
            
            # Execute SL modification
            success = self.mt5_service.modify_position(
                ticket=ticket,
                sl=new_sl,
                tp=trade_data.get('take_profit')  # Keep existing TP
            )
            
            if success:
                # Send notification
                self._send_notification(
                    f"🛡️ DTMS: SL tightened for {symbol} {direction}\n"
                    f"Ticket: {ticket}\n"
                    f"New SL: {new_sl:.5f}\n"
                    f"Reason: {action.get('reason', 'WARNING_L1 state')}"
                )
                
                return ActionResult(
                    success=True,
                    action_type='tighten_sl',
                    details={
                        'ticket': ticket,
                        'symbol': symbol,
                        'old_sl': trade_data.get('stop_loss'),
                        'new_sl': new_sl,
                        'reason': action.get('reason')
                    }
                )
            else:
                return ActionResult(
                    success=False,
                    action_type='tighten_sl',
                    details=action,
                    error_message="Failed to modify position in MT5"
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                action_type='tighten_sl',
                details=action,
                error_message=str(e)
            )
    
    def _partial_close(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
        """Close portion of position"""
        try:
            ticket = trade_data.get('ticket')
            symbol = trade_data.get('symbol')
            direction = trade_data.get('direction')
            current_volume = trade_data.get('current_volume', 0)
            close_percentage = action.get('close_percentage', 50)
            
            if not all([ticket, symbol, direction, current_volume]):
                return ActionResult(
                    success=False,
                    action_type='partial_close',
                    details=action,
                    error_message="Missing required trade data"
                )
            
            # Calculate volume to close
            volume_to_close = current_volume * (close_percentage / 100.0)
            
            # Execute partial close
            success = self.mt5_service.close_position_partial(
                ticket=ticket,
                volume=volume_to_close
            )
            
            if success:
                # Send notification
                self._send_notification(
                    f"📉 DTMS: Partial close for {symbol} {direction}\n"
                    f"Ticket: {ticket}\n"
                    f"Closed: {volume_to_close:.2f} lots ({close_percentage}%)\n"
                    f"Remaining: {current_volume - volume_to_close:.2f} lots\n"
                    f"Reason: {action.get('reason', 'WARNING_L2 state')}"
                )
                
                return ActionResult(
                    success=True,
                    action_type='partial_close',
                    details={
                        'ticket': ticket,
                        'symbol': symbol,
                        'volume_closed': volume_to_close,
                        'close_percentage': close_percentage,
                        'remaining_volume': current_volume - volume_to_close,
                        'reason': action.get('reason')
                    }
                )
            else:
                return ActionResult(
                    success=False,
                    action_type='partial_close',
                    details=action,
                    error_message="Failed to close position partially in MT5"
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                action_type='partial_close',
                details=action,
                error_message=str(e)
            )
    
    def _move_sl_breakeven(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
        """Move stop loss to breakeven (entry price)"""
        try:
            ticket = trade_data.get('ticket')
            symbol = trade_data.get('symbol')
            direction = trade_data.get('direction')
            entry_price = trade_data.get('entry_price', 0)
            
            if not all([ticket, symbol, direction, entry_price]):
                return ActionResult(
                    success=False,
                    action_type='move_sl_breakeven',
                    details=action,
                    error_message="Missing required trade data"
                )
            
            # Move SL to entry price (breakeven)
            success = self.mt5_service.modify_position(
                ticket=ticket,
                sl=entry_price,
                tp=trade_data.get('take_profit')  # Keep existing TP
            )
            
            if success:
                # Send notification
                self._send_notification(
                    f"⚖️ DTMS: SL moved to breakeven for {symbol} {direction}\n"
                    f"Ticket: {ticket}\n"
                    f"New SL: {entry_price:.5f}\n"
                    f"Reason: {action.get('reason', 'WARNING_L2 state')}"
                )
                
                return ActionResult(
                    success=True,
                    action_type='move_sl_breakeven',
                    details={
                        'ticket': ticket,
                        'symbol': symbol,
                        'old_sl': trade_data.get('stop_loss'),
                        'new_sl': entry_price,
                        'reason': action.get('reason')
                    }
                )
            else:
                return ActionResult(
                    success=False,
                    action_type='move_sl_breakeven',
                    details=action,
                    error_message="Failed to modify position in MT5"
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                action_type='move_sl_breakeven',
                details=action,
                error_message=str(e)
            )
    
    def _open_hedge(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
        """Open hedge position"""
        try:
            symbol = trade_data.get('symbol')
            direction = trade_data.get('direction')
            hedge_size = action.get('hedge_size', 0)
            hedge_direction = action.get('hedge_direction')
            current_price = trade_data.get('current_price', 0)
            
            if not all([symbol, direction, hedge_size, hedge_direction, current_price]):
                return ActionResult(
                    success=False,
                    action_type='open_hedge',
                    details=action,
                    error_message="Missing required hedge data"
                )
            
            # Calculate hedge SL (0.5 * ATR from entry)
            atr = trade_data.get('atr', 0.001)  # Default ATR
            if hedge_direction == 'BUY':
                hedge_sl = current_price - (0.5 * atr)
            else:  # SELL
                hedge_sl = current_price + (0.5 * atr)
            
            # Execute hedge order
            hedge_ticket = self.mt5_service.place_order(
                symbol=symbol,
                order_type='MARKET',
                direction=hedge_direction,
                volume=hedge_size,
                sl=hedge_sl,
                comment=f"DTMS_HEDGE_{trade_data.get('ticket')}"
            )
            
            if hedge_ticket:
                # Send notification
                self._send_notification(
                    f"🛡️ DTMS: Hedge opened for {symbol}\n"
                    f"Main ticket: {trade_data.get('ticket')}\n"
                    f"Hedge ticket: {hedge_ticket}\n"
                    f"Direction: {hedge_direction}\n"
                    f"Size: {hedge_size:.2f} lots\n"
                    f"SL: {hedge_sl:.5f}\n"
                    f"Reason: {action.get('reason', 'HEDGED state')}"
                )
                
                return ActionResult(
                    success=True,
                    action_type='open_hedge',
                    details={
                        'main_ticket': trade_data.get('ticket'),
                        'hedge_ticket': hedge_ticket,
                        'symbol': symbol,
                        'hedge_direction': hedge_direction,
                        'hedge_size': hedge_size,
                        'hedge_sl': hedge_sl,
                        'reason': action.get('reason')
                    }
                )
            else:
                return ActionResult(
                    success=False,
                    action_type='open_hedge',
                    details=action,
                    error_message="Failed to place hedge order in MT5"
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                action_type='open_hedge',
                details=action,
                error_message=str(e)
            )
    
    def _close_hedge(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
        """Close hedge position"""
        try:
            hedge_ticket = trade_data.get('hedge_ticket')
            
            if not hedge_ticket:
                return ActionResult(
                    success=False,
                    action_type='close_hedge',
                    details=action,
                    error_message="No hedge ticket found"
                )
            
            # Close hedge position
            success = self.mt5_service.close_position(hedge_ticket)
            
            if success:
                # Send notification
                self._send_notification(
                    f"✅ DTMS: Hedge closed for {trade_data.get('symbol')}\n"
                    f"Main ticket: {trade_data.get('ticket')}\n"
                    f"Hedge ticket: {hedge_ticket}\n"
                    f"Reason: {action.get('reason', 'BOS resumed')}"
                )
                
                return ActionResult(
                    success=True,
                    action_type='close_hedge',
                    details={
                        'main_ticket': trade_data.get('ticket'),
                        'hedge_ticket': hedge_ticket,
                        'reason': action.get('reason')
                    }
                )
            else:
                return ActionResult(
                    success=False,
                    action_type='close_hedge',
                    details=action,
                    error_message="Failed to close hedge position in MT5"
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                action_type='close_hedge',
                details=action,
                error_message=str(e)
            )
    
    def _close_all(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
        """Close all positions for a trade"""
        try:
            ticket = trade_data.get('ticket')
            hedge_ticket = trade_data.get('hedge_ticket')
            symbol = trade_data.get('symbol')
            
            if not ticket:
                return ActionResult(
                    success=False,
                    action_type='close_all',
                    details=action,
                    error_message="No main ticket found"
                )
            
            results = []
            
            # Close main position
            main_success = self.mt5_service.close_position(ticket)
            results.append(('main', main_success))
            
            # Close hedge position if exists
            hedge_success = True
            if hedge_ticket:
                hedge_success = self.mt5_service.close_position(hedge_ticket)
                results.append(('hedge', hedge_success))
            
            overall_success = main_success and hedge_success
            
            if overall_success:
                # Send notification
                self._send_notification(
                    f"🔚 DTMS: All positions closed for {symbol}\n"
                    f"Main ticket: {ticket}\n"
                    f"{f'Hedge ticket: {hedge_ticket}' if hedge_ticket else ''}\n"
                    f"Reason: {action.get('reason', 'Trade closed')}"
                )
                
                return ActionResult(
                    success=True,
                    action_type='close_all',
                    details={
                        'main_ticket': ticket,
                        'hedge_ticket': hedge_ticket,
                        'symbol': symbol,
                        'close_results': results,
                        'reason': action.get('reason')
                    }
                )
            else:
                return ActionResult(
                    success=False,
                    action_type='close_all',
                    details=action,
                    error_message=f"Failed to close positions: {results}"
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                action_type='close_all',
                details=action,
                error_message=str(e)
            )
    
    def _re_add_position(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
        """Re-add closed position"""
        try:
            symbol = trade_data.get('symbol')
            direction = trade_data.get('direction')
            re_add_size = action.get('size', 0)
            current_price = trade_data.get('current_price', 0)
            entry_price = trade_data.get('entry_price', 0)
            
            if not all([symbol, direction, re_add_size, current_price]):
                return ActionResult(
                    success=False,
                    action_type='re_add_position',
                    details=action,
                    error_message="Missing required re-add data"
                )
            
            # Place new order at current price
            new_ticket = self.mt5_service.place_order(
                symbol=symbol,
                order_type='MARKET',
                direction=direction,
                volume=re_add_size,
                comment=f"DTMS_READD_{trade_data.get('ticket')}"
            )
            
            if new_ticket:
                # Send notification
                self._send_notification(
                    f"🔄 DTMS: Position re-added for {symbol}\n"
                    f"Original ticket: {trade_data.get('ticket')}\n"
                    f"New ticket: {new_ticket}\n"
                    f"Direction: {direction}\n"
                    f"Size: {re_add_size:.2f} lots\n"
                    f"Price: {current_price:.5f}\n"
                    f"Reason: {action.get('reason', 'Recovery confirmed')}"
                )
                
                return ActionResult(
                    success=True,
                    action_type='re_add_position',
                    details={
                        'original_ticket': trade_data.get('ticket'),
                        'new_ticket': new_ticket,
                        'symbol': symbol,
                        'direction': direction,
                        'size': re_add_size,
                        'price': current_price,
                        'reason': action.get('reason')
                    }
                )
            else:
                return ActionResult(
                    success=False,
                    action_type='re_add_position',
                    details=action,
                    error_message="Failed to place re-add order in MT5"
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                action_type='re_add_position',
                details=action,
                error_message=str(e)
            )
    
    def _start_flat_timer(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
        """Start flat timer (internal action)"""
        return ActionResult(
            success=True,
            action_type='start_flat_timer',
            details={
                'ticket': trade_data.get('ticket'),
                'duration': action.get('duration', 5 * 900),  # 5 * 15 minutes
                'reason': action.get('reason')
            }
        )
    
    def _stop_flat_timer(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
        """Stop flat timer (internal action)"""
        return ActionResult(
            success=True,
            action_type='stop_flat_timer',
            details={
                'ticket': trade_data.get('ticket'),
                'reason': action.get('reason')
            }
        )
    
    def _start_recovery_timer(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
        """Start recovery timer (internal action)"""
        return ActionResult(
            success=True,
            action_type='start_recovery_timer',
            details={
                'ticket': trade_data.get('ticket'),
                'duration': action.get('duration', 2 * 900),  # 2 * 15 minutes
                'reason': action.get('reason')
            }
        )
    
    def _send_notification(self, message: str):
        """Send notification via Telegram"""
        try:
            if self.telegram_service:
                self.telegram_service.send_message(message)
            else:
                logger.info(f"DTMS Notification: {message}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    def get_action_history(self, ticket: Optional[int] = None) -> List[ActionResult]:
        """Get action history, optionally filtered by ticket"""
        try:
            if ticket is None:
                return self.action_history.copy()
            else:
                return [action for action in self.action_history 
                       if action.details.get('ticket') == ticket or 
                          action.details.get('main_ticket') == ticket or
                          action.details.get('original_ticket') == ticket]
        except Exception as e:
            logger.error(f"Failed to get action history: {e}")
            return []
    
    def get_recent_actions(self, hours: int = 24) -> List[ActionResult]:
        """Get recent actions within specified hours"""
        try:
            cutoff_time = time.time() - (hours * 3600)
            return [action for action in self.action_history 
                   if action.timestamp >= cutoff_time]
        except Exception as e:
            logger.error(f"Failed to get recent actions: {e}")
            return []
