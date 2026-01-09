"""
DTMS State Machine
Finite State Machine for defensive trade management states and transitions
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from dtms_config import get_config, STATE_CONFIG

logger = logging.getLogger(__name__)

class TradeState(Enum):
    """Trade state enumeration"""
    HEALTHY = "HEALTHY"
    WARNING_L1 = "WARNING_L1"
    WARNING_L2 = "WARNING_L2"
    HEDGED = "HEDGED"
    RECOVERING = "RECOVERING"
    CLOSED = "CLOSED"

@dataclass
class TradeStateData:
    """Data structure for trade state management"""
    ticket: int
    symbol: str
    direction: str  # 'BUY' or 'SELL'
    entry_price: float
    current_volume: float
    initial_volume: float
    closed_volume: float = 0.0
    
    # State tracking
    state: TradeState = TradeState.HEALTHY
    state_entry_time: float = field(default_factory=time.time)
    previous_state: Optional[TradeState] = None
    
    # Score tracking
    current_score: float = 0.0
    score_history: List[Tuple[float, float]] = field(default_factory=list)  # (score, timestamp)
    
    # Warning counters (with decay)
    warnings: Dict[str, int] = field(default_factory=dict)
    warning_decay_times: Dict[str, float] = field(default_factory=dict)
    
    # Timers
    flat_timer_start: Optional[float] = None
    flat_timer_duration: float = 0.0  # seconds
    recovery_timer_start: Optional[float] = None
    recovery_timer_duration: float = 0.0  # seconds
    
    # VWAP tracking
    vwap_cross_counter: int = 0
    vwap_flip_active: bool = False
    
    # Actions taken
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    
    # Recovery data
    recovery_target_volume: float = 0.0
    hedge_ticket: Optional[int] = None
    hedge_volume: float = 0.0

class DTMSStateMachine:
    """
    Finite State Machine for defensive trade management.
    
    States:
    - HEALTHY: Normal monitoring, trail SL on BOS
    - WARNING_L1: Tighten SL, start flat timer
    - WARNING_L2: Partial close 50%, move SL to breakeven
    - HEDGED: Hedge opened, maintain net risk ≤ 0
    - RECOVERING: BOS resumed, re-add position
    - CLOSED: Trade closed (terminal state)
    """
    
    def __init__(self):
        self.config = get_config()
        self.state_config = STATE_CONFIG
        
        # Active trades
        self.active_trades: Dict[int, TradeStateData] = {}
        
        logger.info("DTMSStateMachine initialized")
    
    def add_trade(self, ticket: int, symbol: str, direction: str, entry_price: float, volume: float) -> bool:
        """Add a new trade for monitoring"""
        try:
            trade_data = TradeStateData(
                ticket=ticket,
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                current_volume=volume,
                initial_volume=volume
            )
            
            self.active_trades[ticket] = trade_data
            
            logger.info(f"Added trade {ticket} ({symbol} {direction}) to DTMS monitoring")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add trade {ticket}: {e}")
            return False
    
    def remove_trade(self, ticket: int) -> bool:
        """Remove trade from monitoring"""
        try:
            if ticket in self.active_trades:
                del self.active_trades[ticket]
                logger.info(f"Removed trade {ticket} from DTMS monitoring")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to remove trade {ticket}: {e}")
            return False
    
    def update_trade_state(
        self, 
        ticket: int, 
        score_data: Dict[str, Any],
        current_price: float,
        vwap_current: float,
        vwap_slope: float
    ) -> Dict[str, Any]:
        """
        Update trade state based on signal score and market conditions.
        
        Args:
            ticket: Trade ticket number
            score_data: Signal scoring results
            current_price: Current market price
            vwap_current: Current VWAP
            vwap_slope: VWAP slope
            
        Returns:
            Dict with state transition info and actions to take
        """
        try:
            if ticket not in self.active_trades:
                return {'error': f'Trade {ticket} not found in monitoring'}
            
            # Verify position still exists in MT5 before updating state
            import MetaTrader5 as mt5
            mt5_positions = mt5.positions_get(ticket=ticket)
            if not mt5_positions or len(mt5_positions) == 0:
                logger.warning(f"Trade {ticket} no longer exists in MT5 - marking as CLOSED")
                trade = self.active_trades[ticket]
                trade.state = TradeState.CLOSED
                return {
                    'previous_state': trade.state.value,
                    'new_state': 'CLOSED',
                    'actions': [],
                    'reason': 'Position closed in MT5'
                }
            
            trade = self.active_trades[ticket]
            current_state = trade.state
            total_score = score_data.get('total_score', 0.0)
            warnings = score_data.get('warnings', {})
            confluence = score_data.get('confluence', {})
            
            # Update trade data
            trade.current_score = total_score
            trade.score_history.append((total_score, time.time()))
            
            # Refresh volume from MT5 (handles partial closes outside DTMS)
            try:
                mt5_pos = mt5_positions[0]  # Already verified above
                actual_volume = float(mt5_pos.volume)
                if abs(actual_volume - trade.current_volume) > 0.001:  # Volume changed
                    logger.debug(f"Volume updated for {ticket}: {trade.current_volume} → {actual_volume}")
                    trade.current_volume = actual_volume
                    trade.closed_volume = trade.initial_volume - actual_volume
            except Exception:
                pass  # If volume refresh fails, continue with existing value
            
            # Update VWAP tracking
            self._update_vwap_tracking(trade, current_price, vwap_current, vwap_slope)
            
            # Update warning counters
            self._update_warning_counters(trade, warnings)
            
            # Check for state transitions
            transition_result = self._evaluate_state_transition(
                trade, total_score, warnings, confluence, current_price
            )
            
            # Update timers
            self._update_timers(trade)
            
            # Log state update
            logger.debug(f"Trade {ticket} state update: {current_state.value} -> {trade.state.value}, score: {total_score:.2f}")
            
            return transition_result
            
        except Exception as e:
            logger.error(f"Failed to update trade state for {ticket}: {e}")
            return {'error': str(e)}
    
    def _update_vwap_tracking(self, trade: TradeStateData, current_price: float, vwap_current: float, vwap_slope: float):
        """Update VWAP cross counter and flip status"""
        try:
            # Update VWAP cross counter
            if trade.direction == 'BUY':
                if current_price < vwap_current:
                    trade.vwap_cross_counter += 1
                else:
                    trade.vwap_cross_counter = max(0, trade.vwap_cross_counter - 1)
            else:  # SELL
                if current_price > vwap_current:
                    trade.vwap_cross_counter += 1
                else:
                    trade.vwap_cross_counter = max(0, trade.vwap_cross_counter - 1)
            
            # Update VWAP flip status (simplified)
            # This would normally use adaptive thresholds from regime classifier
            vwap_threshold = 0.001  # Base threshold, should be adaptive
            
            if abs(vwap_slope) >= vwap_threshold and trade.vwap_cross_counter >= 2:
                trade.vwap_flip_active = True
            elif abs(vwap_slope) < (0.7 * vwap_threshold):
                trade.vwap_flip_active = False
                
        except Exception as e:
            logger.error(f"Failed to update VWAP tracking: {e}")
    
    def _update_warning_counters(self, trade: TradeStateData, warnings: Dict[str, int]):
        """Update warning counters with decay logic"""
        try:
            current_time = time.time()
            
            # Update active warnings
            for warning_type, count in warnings.items():
                if count > 0:
                    trade.warnings[warning_type] = count
                    trade.warning_decay_times[warning_type] = current_time + 1800  # 30 minutes
            
            # Decay expired warnings
            expired_warnings = []
            for warning_type, decay_time in trade.warning_decay_times.items():
                if current_time > decay_time:
                    expired_warnings.append(warning_type)
            
            for warning_type in expired_warnings:
                trade.warnings[warning_type] = max(0, trade.warnings[warning_type] - 1)
                if trade.warnings[warning_type] == 0:
                    del trade.warning_decay_times[warning_type]
                    
        except Exception as e:
            logger.error(f"Failed to update warning counters: {e}")
    
    def _evaluate_state_transition(
        self, 
        trade: TradeStateData, 
        total_score: float, 
        warnings: Dict[str, int],
        confluence: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """Evaluate state transitions based on score and conditions"""
        try:
            current_state = trade.state
            transition_result = {
                'ticket': trade.ticket,
                'symbol': trade.symbol,
                'previous_state': current_state.value,
                'new_state': current_state.value,
                'transition_reason': '',
                'actions': [],
                'score': total_score,
                'warnings': warnings
            }
            
            # Check for terminal conditions first
            if self._check_terminal_conditions(trade, total_score, confluence):
                self._transition_to_state(trade, TradeState.CLOSED, "Terminal condition met")
                transition_result['new_state'] = TradeState.CLOSED.value
                transition_result['transition_reason'] = "Terminal condition met"
                transition_result['actions'].append({'type': 'close_all', 'reason': 'Terminal condition'})
                return transition_result
            
            # State-specific transition logic
            if current_state == TradeState.HEALTHY:
                transition_result = self._handle_healthy_state(trade, total_score, transition_result)
            elif current_state == TradeState.WARNING_L1:
                transition_result = self._handle_warning_l1_state(trade, total_score, transition_result)
            elif current_state == TradeState.WARNING_L2:
                transition_result = self._handle_warning_l2_state(trade, total_score, confluence, transition_result)
            elif current_state == TradeState.HEDGED:
                transition_result = self._handle_hedged_state(trade, total_score, transition_result)
            elif current_state == TradeState.RECOVERING:
                transition_result = self._handle_recovering_state(trade, total_score, transition_result)
            
            return transition_result
            
        except Exception as e:
            logger.error(f"Failed to evaluate state transition: {e}")
            return {'error': str(e)}
    
    def _check_terminal_conditions(self, trade: TradeStateData, total_score: float, confluence: Dict[str, Any]) -> bool:
        """Check for terminal conditions that force trade closure"""
        try:
            # CHOCH confirmed opposite direction (would need structure detection)
            # This is a placeholder - actual implementation would check for CHOCH
            choch_opposite = False  # Would be determined by structure analysis
            
            if choch_opposite:
                logger.warning(f"Trade {trade.ticket}: CHOCH opposite confirmed - forcing closure")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check terminal conditions: {e}")
            return False
    
    def _handle_healthy_state(self, trade: TradeStateData, total_score: float, transition_result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle HEALTHY state transitions"""
        try:
            if total_score <= self.config.state_transitions['HEALTHY_to_WARNING_L1']:
                # Transition to WARNING_L1
                self._transition_to_state(trade, TradeState.WARNING_L1, f"Score {total_score:.2f}")
                transition_result['new_state'] = TradeState.WARNING_L1.value
                transition_result['transition_reason'] = f"Score deteriorated to {total_score:.2f}"
                transition_result['actions'].append({
                    'type': 'tighten_sl',
                    'reason': 'Entering WARNING_L1',
                    'target_sl': '0.3R_behind_price'
                })
                transition_result['actions'].append({
                    'type': 'start_flat_timer',
                    'reason': 'WARNING_L1 state'
                })
            
            return transition_result
            
        except Exception as e:
            logger.error(f"Failed to handle HEALTHY state: {e}")
            return transition_result
    
    def _handle_warning_l1_state(self, trade: TradeStateData, total_score: float, transition_result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle WARNING_L1 state transitions"""
        try:
            # Check for recovery (with hysteresis)
            recovery_threshold = self.config.state_transitions['recovery_hysteresis']['WARNING_L1_to_HEALTHY']
            if total_score >= recovery_threshold:
                self._transition_to_state(trade, TradeState.HEALTHY, f"Score recovered to {total_score:.2f}")
                transition_result['new_state'] = TradeState.HEALTHY.value
                transition_result['transition_reason'] = f"Score recovered to {total_score:.2f}"
                transition_result['actions'].append({
                    'type': 'stop_flat_timer',
                    'reason': 'Recovering to HEALTHY'
                })
            
            # Check for deterioration
            elif total_score <= self.config.state_transitions['WARNING_L1_to_WARNING_L2']:
                self._transition_to_state(trade, TradeState.WARNING_L2, f"Score deteriorated to {total_score:.2f}")
                transition_result['new_state'] = TradeState.WARNING_L2.value
                transition_result['transition_reason'] = f"Score deteriorated to {total_score:.2f}"
                transition_result['actions'].append({
                    'type': 'partial_close',
                    'reason': 'Entering WARNING_L2',
                    'close_percentage': 50
                })
                transition_result['actions'].append({
                    'type': 'move_sl_breakeven',
                    'reason': 'WARNING_L2 state'
                })
            
            return transition_result
            
        except Exception as e:
            logger.error(f"Failed to handle WARNING_L1 state: {e}")
            return transition_result
    
    def _handle_warning_l2_state(self, trade: TradeStateData, total_score: float, confluence: Dict[str, Any], transition_result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle WARNING_L2 state transitions"""
        try:
            # Check for recovery (with hysteresis)
            recovery_threshold = self.config.state_transitions['recovery_hysteresis']['WARNING_L2_to_WARNING_L1']
            if total_score >= recovery_threshold:
                self._transition_to_state(trade, TradeState.WARNING_L1, f"Score improved to {total_score:.2f}")
                transition_result['new_state'] = TradeState.WARNING_L1.value
                transition_result['transition_reason'] = f"Score improved to {total_score:.2f}"
            
            # Check for hedge trigger
            elif (total_score <= self.config.state_transitions['WARNING_L2_to_HEDGED'] or 
                  self._check_hedge_confluence(trade, confluence)):
                
                self._transition_to_state(trade, TradeState.HEDGED, "Hedge trigger conditions met")
                transition_result['new_state'] = TradeState.HEDGED.value
                transition_result['transition_reason'] = "Hedge trigger conditions met"
                transition_result['actions'].append({
                    'type': 'open_hedge',
                    'reason': 'Entering HEDGED state',
                    'hedge_size': 0.5 * trade.current_volume,
                    'hedge_direction': 'SELL' if trade.direction == 'BUY' else 'BUY'
                })
                transition_result['actions'].append({
                    'type': 'start_flat_timer',
                    'reason': 'HEDGED state',
                    'duration': 5 * 900  # 5 * 15 minutes
                })
            
            return transition_result
            
        except Exception as e:
            logger.error(f"Failed to handle WARNING_L2 state: {e}")
            return transition_result
    
    def _handle_hedged_state(self, trade: TradeStateData, total_score: float, transition_result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle HEDGED state transitions"""
        try:
            # Check flat timer expiration
            if self._is_flat_timer_expired(trade):
                self._transition_to_state(trade, TradeState.CLOSED, "Flat timer expired")
                transition_result['new_state'] = TradeState.CLOSED.value
                transition_result['transition_reason'] = "Flat timer expired"
                transition_result['actions'].append({
                    'type': 'close_all',
                    'reason': 'Flat timer expired'
                })
            
            # Check for BOS resume (would need structure detection)
            # This is a placeholder - actual implementation would check for BOS
            bos_resumed = False  # Would be determined by structure analysis
            
            if bos_resumed:
                self._transition_to_state(trade, TradeState.RECOVERING, "BOS resumed original direction")
                transition_result['new_state'] = TradeState.RECOVERING.value
                transition_result['transition_reason'] = "BOS resumed original direction"
                transition_result['actions'].append({
                    'type': 'close_hedge',
                    'reason': 'BOS resumed'
                })
                transition_result['actions'].append({
                    'type': 'start_recovery_timer',
                    'reason': 'RECOVERING state',
                    'duration': 2 * 900  # 2 * 15 minutes
                })
            
            return transition_result
            
        except Exception as e:
            logger.error(f"Failed to handle HEDGED state: {e}")
            return transition_result
    
    def _handle_recovering_state(self, trade: TradeStateData, total_score: float, transition_result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle RECOVERING state transitions"""
        try:
            # Check recovery timer expiration
            if self._is_recovery_timer_expired(trade):
                if total_score >= 1.0:  # Recovery confirmed
                    self._transition_to_state(trade, TradeState.HEALTHY, "Recovery confirmed")
                    transition_result['new_state'] = TradeState.HEALTHY.value
                    transition_result['transition_reason'] = "Recovery confirmed"
                    transition_result['actions'].append({
                        'type': 're_add_position',
                        'reason': 'Recovery confirmed',
                        'size': 0.5 * trade.closed_volume
                    })
                else:
                    # Recovery failed
                    self._transition_to_state(trade, TradeState.CLOSED, "Recovery timer expired without confirmation")
                    transition_result['new_state'] = TradeState.CLOSED.value
                    transition_result['transition_reason'] = "Recovery timer expired without confirmation"
                    transition_result['actions'].append({
                        'type': 'close_all',
                        'reason': 'Recovery failed'
                    })
            
            return transition_result
            
        except Exception as e:
            logger.error(f"Failed to handle RECOVERING state: {e}")
            return transition_result
    
    def _check_hedge_confluence(self, trade: TradeStateData, confluence: Dict[str, Any]) -> bool:
        """Check if hedge confluence conditions are met"""
        try:
            # VWAP flip + volume flip confluence
            vwap_flip = trade.vwap_flip_active
            volume_flip = confluence.get('direction') == ('BEARISH' if trade.direction == 'BUY' else 'BULLISH')
            
            return vwap_flip and volume_flip
            
        except Exception as e:
            logger.error(f"Failed to check hedge confluence: {e}")
            return False
    
    def _transition_to_state(self, trade: TradeStateData, new_state: TradeState, reason: str):
        """Transition trade to new state"""
        try:
            trade.previous_state = trade.state
            trade.state = new_state
            trade.state_entry_time = time.time()
            
            # Log transition
            action_log = {
                'timestamp': time.time(),
                'from_state': trade.previous_state.value,
                'to_state': new_state.value,
                'reason': reason,
                'score': trade.current_score
            }
            trade.actions_taken.append(action_log)
            
            logger.info(f"Trade {trade.ticket} transitioned: {trade.previous_state.value} -> {new_state.value} ({reason})")
            
        except Exception as e:
            logger.error(f"Failed to transition trade {trade.ticket}: {e}")
    
    def _update_timers(self, trade: TradeStateData):
        """Update trade timers"""
        try:
            current_time = time.time()
            
            # Update flat timer
            if trade.flat_timer_start is not None:
                trade.flat_timer_duration = current_time - trade.flat_timer_start
            
            # Update recovery timer
            if trade.recovery_timer_start is not None:
                trade.recovery_timer_duration = current_time - trade.recovery_timer_start
                
        except Exception as e:
            logger.error(f"Failed to update timers for trade {trade.ticket}: {e}")
    
    def _is_flat_timer_expired(self, trade: TradeStateData) -> bool:
        """Check if flat timer has expired"""
        if trade.flat_timer_start is None:
            return False
        
        current_time = time.time()
        elapsed = current_time - trade.flat_timer_start
        
        # Flat timer duration: 5 * 15 minutes = 75 minutes
        return elapsed >= (5 * 900)
    
    def _is_recovery_timer_expired(self, trade: TradeStateData) -> bool:
        """Check if recovery timer has expired"""
        if trade.recovery_timer_start is None:
            return False
        
        current_time = time.time()
        elapsed = current_time - trade.recovery_timer_start
        
        # Recovery timer duration: 2 * 15 minutes = 30 minutes
        return elapsed >= (2 * 900)
    
    def get_trade_status(self, ticket: int) -> Optional[Dict[str, Any]]:
        """Get current status of a trade"""
        try:
            if ticket not in self.active_trades:
                return None
            
            trade = self.active_trades[ticket]
            
            return {
                'ticket': trade.ticket,
                'symbol': trade.symbol,
                'direction': trade.direction,
                'state': trade.state.value,
                'state_entry_time': trade.state_entry_time,
                'current_score': trade.current_score,
                'warnings': trade.warnings.copy(),
                'vwap_cross_counter': trade.vwap_cross_counter,
                'vwap_flip_active': trade.vwap_flip_active,
                'flat_timer_remaining': self._get_flat_timer_remaining(trade),
                'recovery_timer_remaining': self._get_recovery_timer_remaining(trade),
                'actions_taken': len(trade.actions_taken)
            }
            
        except Exception as e:
            logger.error(f"Failed to get trade status for {ticket}: {e}")
            return None
    
    def _get_flat_timer_remaining(self, trade: TradeStateData) -> float:
        """Get remaining flat timer duration"""
        if trade.flat_timer_start is None:
            return 0.0
        
        current_time = time.time()
        elapsed = current_time - trade.flat_timer_start
        remaining = (5 * 900) - elapsed  # 5 * 15 minutes
        
        return max(0.0, remaining)
    
    def _get_recovery_timer_remaining(self, trade: TradeStateData) -> float:
        """Get remaining recovery timer duration"""
        if trade.recovery_timer_start is None:
            return 0.0
        
        current_time = time.time()
        elapsed = current_time - trade.recovery_timer_start
        remaining = (2 * 900) - elapsed  # 2 * 15 minutes
        
        return max(0.0, remaining)
    
    def get_all_trades_status(self) -> List[Dict[str, Any]]:
        """Get status of all monitored trades"""
        try:
            status_list = []
            for ticket in self.active_trades:
                status = self.get_trade_status(ticket)
                if status:
                    status_list.append(status)
            
            return status_list
            
        except Exception as e:
            logger.error(f"Failed to get all trades status: {e}")
            return []
    
    def cleanup_closed_trades(self):
        """Remove trades in CLOSED state from monitoring and verify positions still exist in MT5"""
        try:
            import MetaTrader5 as mt5
            
            closed_tickets = []
            stale_tickets = []
            
            # Get current open positions from MT5
            # Check if MT5 is initialized before calling positions_get
            if not mt5.initialize():
                logger.warning("MT5 not initialized, skipping position verification in cleanup")
                # Still remove CLOSED state trades even if MT5 is unavailable
                for ticket, trade in self.active_trades.items():
                    if trade.state == TradeState.CLOSED:
                        closed_tickets.append(ticket)
                for ticket in closed_tickets:
                    del self.active_trades[ticket]
                    logger.info(f"Cleaned up closed trade {ticket} (MT5 unavailable)")
                if closed_tickets:
                    logger.info(f"Cleaned up {len(closed_tickets)} closed trades (MT5 unavailable)")
                return
            
            mt5_positions = mt5.positions_get()
            open_tickets = {pos.ticket for pos in mt5_positions} if mt5_positions else set()
            
            for ticket, trade in self.active_trades.items():
                # Check if trade is in CLOSED state
                if trade.state == TradeState.CLOSED:
                    closed_tickets.append(ticket)
                # Check if position no longer exists in MT5 (manually closed outside DTMS)
                elif ticket not in open_tickets:
                    logger.warning(f"Trade {ticket} ({trade.symbol}) no longer exists in MT5 - marking as stale")
                    stale_tickets.append(ticket)
            
            # Remove closed trades
            for ticket in closed_tickets:
                del self.active_trades[ticket]
                logger.info(f"Cleaned up closed trade {ticket}")
            
            # Remove stale trades (closed outside DTMS)
            for ticket in stale_tickets:
                del self.active_trades[ticket]
                logger.info(f"Cleaned up stale trade {ticket} (position closed outside DTMS)")
            
            total_cleaned = len(closed_tickets) + len(stale_tickets)
            if total_cleaned > 0:
                logger.info(f"Cleaned up {total_cleaned} trades ({len(closed_tickets)} closed, {len(stale_tickets)} stale)")
                
        except Exception as e:
            logger.error(f"Failed to cleanup closed trades: {e}")
