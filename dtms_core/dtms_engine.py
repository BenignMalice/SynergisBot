"""
DTMS Engine
Main orchestrator for the Defensive Trade Management System
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from dtms_core.data_manager import DTMSDataManager
from dtms_core.regime_classifier import DTMSRegimeClassifier
from dtms_core.signal_scorer import DTMSSignalScorer
from dtms_core.state_machine import DTMSStateMachine, TradeState
from dtms_core.action_executor import DTMSActionExecutor
from dtms_config import get_config

logger = logging.getLogger(__name__)

class DTMSEngine:
    """
    Main DTMS Engine that orchestrates all defensive trade management components.
    
    Responsibilities:
    - Initialize and coordinate all DTMS modules
    - Manage monitoring loops (fast check, deep check)
    - Process trade state updates
    - Execute defensive actions
    - Provide status and health monitoring
    """
    
    def __init__(self, mt5_service, binance_service=None, telegram_service=None, order_flow_service=None):
        self.mt5_service = mt5_service
        self.binance_service = binance_service
        self.telegram_service = telegram_service
        self.order_flow_service = order_flow_service  # NEW: Order Flow Service for BTCUSD
        self.config = get_config()
        
        # Initialize DTMS components
        self.data_manager = DTMSDataManager(mt5_service, binance_service)
        self.regime_classifier = DTMSRegimeClassifier()
        self.signal_scorer = DTMSSignalScorer()
        self.state_machine = DTMSStateMachine()
        self.action_executor = DTMSActionExecutor(mt5_service, telegram_service)
        
        # Monitoring state
        self.monitoring_active = False
        self.last_fast_check = {}
        self.last_deep_check = {}
        self.deep_check_cooldown = {}
        
        # Performance tracking
        self.performance_stats = {
            'fast_checks_total': 0,
            'deep_checks_total': 0,
            'actions_executed': 0,
            'state_transitions': 0,
            'start_time': time.time()
        }
        
        logger.info("DTMSEngine initialized")
    
    def start_monitoring(self) -> bool:
        """Start DTMS monitoring"""
        try:
            if self.monitoring_active:
                logger.warning("DTMS monitoring already active")
                return True
            
            self.monitoring_active = True
            logger.info("DTMS monitoring started")
            
            # Send startup notification
            self._send_notification("🛡️ DTMS: Defensive Trade Management System started")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start DTMS monitoring: {e}")
            return False
    
    def stop_monitoring(self) -> bool:
        """Stop DTMS monitoring"""
        try:
            self.monitoring_active = False
            logger.info("DTMS monitoring stopped")
            
            # Send shutdown notification
            self._send_notification("🛑 DTMS: Defensive Trade Management System stopped")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop DTMS monitoring: {e}")
            return False
    
    def add_trade_monitoring(
        self, 
        ticket: int, 
        symbol: str, 
        direction: str, 
        entry_price: float, 
        volume: float,
        stop_loss: float = None,
        take_profit: float = None
    ) -> bool:
        """
        Add a trade to DTMS monitoring.
        
        Args:
            ticket: Trade ticket number
            symbol: Trading symbol
            direction: 'BUY' or 'SELL'
            entry_price: Entry price
            volume: Position volume
            stop_loss: Initial stop loss (optional)
            take_profit: Initial take profit (optional)
        """
        try:
            # Initialize symbol data if needed
            if not self.data_manager.initialize_symbol(symbol):
                logger.error(f"Failed to initialize data for {symbol}")
                return False
            
            # Add trade to state machine
            if not self.state_machine.add_trade(ticket, symbol, direction, entry_price, volume):
                logger.error(f"Failed to add trade {ticket} to state machine")
                return False
            
            # Initialize monitoring timestamps
            current_time = time.time()
            self.last_fast_check[ticket] = current_time
            self.last_deep_check[ticket] = current_time
            self.deep_check_cooldown[ticket] = current_time
            
            logger.info(f"Added trade {ticket} ({symbol} {direction}) to DTMS monitoring")
            
            # Send notification
            self._send_notification(
                f"📊 DTMS: Monitoring started for {symbol} {direction}\n"
                f"Ticket: {ticket}\n"
                f"Entry: {entry_price:.5f}\n"
                f"Volume: {volume:.2f} lots"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add trade monitoring for {ticket}: {e}")
            return False
    
    def remove_trade_monitoring(self, ticket: int) -> bool:
        """Remove a trade from DTMS monitoring"""
        try:
            # Remove from state machine
            if not self.state_machine.remove_trade(ticket):
                logger.warning(f"Trade {ticket} not found in state machine")
            
            # Clean up monitoring data
            self.last_fast_check.pop(ticket, None)
            self.last_deep_check.pop(ticket, None)
            self.deep_check_cooldown.pop(ticket, None)
            
            logger.info(f"Removed trade {ticket} from DTMS monitoring")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove trade monitoring for {ticket}: {e}")
            return False
    
    async def run_monitoring_cycle(self):
        """Run one monitoring cycle for all active trades"""
        try:
            if not self.monitoring_active:
                logger.debug("DTMS monitoring not active, skipping cycle")
                return
            
            current_time = time.time()
            active_trades = self.state_machine.get_all_trades_status()
            
            if not active_trades:
                logger.debug("No active trades in DTMS monitoring cycle")
                return
            
            logger.info(f"🔄 Running DTMS monitoring cycle - {len(active_trades)} active trades")
            
            for trade_status in active_trades:
                ticket = trade_status['ticket']
                symbol = trade_status['symbol']
                state = trade_status['state']
                
                # Skip closed trades
                if state == 'CLOSED':
                    continue
                
                # Determine monitoring cadence based on state and market conditions
                should_fast_check = self._should_run_fast_check(ticket, current_time)
                should_deep_check = self._should_run_deep_check(ticket, current_time)
                
                if should_fast_check:
                    logger.info(f"⚡ Fast check for trade {ticket} ({symbol}) - state: {state}")
                    await self._run_fast_check(ticket, symbol)
                
                if should_deep_check:
                    logger.info(f"🔍 Deep check for trade {ticket} ({symbol}) - state: {state}")
                    await self._run_deep_check(ticket, symbol)
            
            # Cleanup closed trades
            self.state_machine.cleanup_closed_trades()
            
        except Exception as e:
            logger.error(f"Failed to run monitoring cycle: {e}")
    
    def _should_run_fast_check(self, ticket: int, current_time: float) -> bool:
        """Determine if fast check should run"""
        try:
            last_check = self.last_fast_check.get(ticket, 0)
            base_interval = self.config.monitoring['fast_check_interval']
            
            # Get trade state for adaptive timing
            trade_status = self.state_machine.get_trade_status(ticket)
            if not trade_status:
                return False
            
            state = trade_status['state']
            
            # Adaptive timing based on state
            if state in ['WARNING_L1', 'WARNING_L2']:
                interval = base_interval  # 30s
            elif state == 'HEDGED':
                interval = base_interval * 2  # 60s (less critical)
            else:
                interval = base_interval  # 30s
            
            # High volatility override (would need ATR data)
            # if atr_ratio > 1.3:
            #     interval = min(interval, self.config.monitoring['high_vol_override'])
            
            return (current_time - last_check) >= interval
            
        except Exception as e:
            logger.error(f"Failed to check fast check timing for {ticket}: {e}")
            return False
    
    def _should_run_deep_check(self, ticket: int, current_time: float) -> bool:
        """Determine if deep check should run"""
        try:
            last_check = self.last_deep_check.get(ticket, 0)
            cooldown_until = self.deep_check_cooldown.get(ticket, 0)
            
            # Check cooldown period
            if current_time < cooldown_until:
                return False
            
            # Base interval: 15 minutes
            base_interval = self.config.monitoring['deep_check_interval']
            
            # Check if enough time has passed
            return (current_time - last_check) >= base_interval
            
        except Exception as e:
            logger.error(f"Failed to check deep check timing for {ticket}: {e}")
            return False
    
    async def _run_fast_check(self, ticket: int, symbol: str):
        """Run fast check for a trade"""
        try:
            current_time = time.time()
            
            # Get current price
            current_price = self._get_current_price(symbol)
            if current_price is None:
                logger.warning(f"Failed to get current price for {symbol}")
                return
            
            # Get VWAP data
            vwap_current = self.data_manager.get_current_vwap(symbol)
            vwap_slope = self.data_manager.get_vwap_slope(symbol, periods=3)
            
            # Get trade data
            trade_status = self.state_machine.get_trade_status(ticket)
            if not trade_status:
                return
            
            # Update VWAP cross counter
            direction = trade_status['direction']
            vwap_cross_counter = trade_status['vwap_cross_counter']
            
            if direction == 'BUY':
                if current_price < vwap_current:
                    vwap_cross_counter += 1
                else:
                    vwap_cross_counter = max(0, vwap_cross_counter - 1)
            else:  # SELL
                if current_price > vwap_current:
                    vwap_cross_counter += 1
                else:
                    vwap_cross_counter = max(0, vwap_cross_counter - 1)
            
            # Check for event-driven deep check triggers
            should_trigger_deep = self._check_fast_check_triggers(
                ticket, symbol, current_price, vwap_slope, vwap_cross_counter
            )
            
            if should_trigger_deep:
                # Override cooldown for event-driven deep check
                self.deep_check_cooldown[ticket] = current_time - 1
                await self._run_deep_check(ticket, symbol)
            
            # Update last fast check time
            self.last_fast_check[ticket] = current_time
            self.performance_stats['fast_checks_total'] += 1
            
        except Exception as e:
            logger.error(f"Failed to run fast check for {ticket}: {e}")
    
    async def _run_deep_check(self, ticket: int, symbol: str):
        """Run deep check for a trade"""
        try:
            current_time = time.time()
            
            # Update data
            self.data_manager.update_incremental_data(symbol, 'M5')
            self.data_manager.update_incremental_data(symbol, 'M15')
            
            # Get data
            m5_data = self.data_manager.get_m5_dataframe(symbol)
            m15_data = self.data_manager.get_m15_dataframe(symbol)
            
            if m5_data is None or m15_data is None:
                logger.warning(f"Insufficient data for deep check: {symbol}")
                return
            
            # Classify regime
            regime = self.regime_classifier.classify_regime(symbol, m5_data, m15_data)
            
            # Get current price and VWAP
            current_price = self._get_current_price(symbol)
            if current_price is None:
                logger.warning(f"Failed to get current price for {symbol}, skipping deep check")
                return
            vwap_current = self.data_manager.get_current_vwap(symbol)
            vwap_slope = self.data_manager.get_vwap_slope(symbol, periods=3)
            
            # Get trade data
            trade_status = self.state_machine.get_trade_status(ticket)
            if not trade_status:
                return
            
            # Get Binance data (if available)
            binance_data = self._get_binance_data(symbol)
            
            # Calculate signal score
            score_data = self.signal_scorer.calculate_signal_score(
                symbol=symbol,
                trade_direction=trade_status['direction'],
                m5_data=m5_data,
                m15_data=m15_data,
                regime=regime,
                vwap_current=vwap_current,
                vwap_slope=vwap_slope,
                vwap_cross_counter=trade_status['vwap_cross_counter'],
                binance_data=binance_data
            )
            
            # Update state machine
            transition_result = self.state_machine.update_trade_state(
                ticket=ticket,
                score_data=score_data,
                current_price=current_price,
                vwap_current=vwap_current,
                vwap_slope=vwap_slope
            )
            
            # Execute actions if state changed
            if transition_result.get('new_state') != transition_result.get('previous_state'):
                await self._execute_state_actions(ticket, transition_result)
                self.performance_stats['state_transitions'] += 1
            
            # Update timestamps
            self.last_deep_check[ticket] = current_time
            self.deep_check_cooldown[ticket] = current_time + self.config.monitoring['cooldown_period']
            self.performance_stats['deep_checks_total'] += 1
            
            # Log deep check
            logger.debug(f"Deep check completed for {ticket}: score={score_data.get('total_score', 0):.2f}, state={transition_result.get('new_state')}")
            
        except Exception as e:
            logger.error(f"Failed to run deep check for {ticket}: {e}")
    
    def _check_fast_check_triggers(
        self, 
        ticket: int, 
        symbol: str, 
        current_price: float, 
        vwap_slope: float, 
        vwap_cross_counter: int
    ) -> bool:
        """Check if fast check should trigger deep check"""
        try:
            # Get adaptive VWAP threshold
            m15_data = self.data_manager.get_m15_dataframe(symbol)
            if m15_data is None:
                return False
            
            regime = self.regime_classifier.classify_regime(symbol, None, m15_data)
            thresholds = self.regime_classifier.get_adaptive_thresholds(symbol, regime)
            vwap_threshold = thresholds.get('vwap_threshold', 0.001)
            
            # VWAP flip trigger
            if abs(vwap_slope) >= vwap_threshold and vwap_cross_counter >= 2:
                logger.info(f"Fast check trigger: VWAP flip for {ticket}")
                return True
            
            # Micro structure threat (simplified)
            # This would normally check distance to last swing
            # For now, just check if price moved significantly
            trade_status = self.state_machine.get_trade_status(ticket)
            if trade_status:
                entry_price = trade_status.get('entry_price', 0)
                if entry_price > 0:
                    price_move = abs(current_price - entry_price) / entry_price
                    if price_move > 0.002:  # 0.2% move
                        logger.info(f"Fast check trigger: Price move for {ticket}")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check fast check triggers for {ticket}: {e}")
            return False
    
    async def _execute_state_actions(self, ticket: int, transition_result: Dict[str, Any]):
        """Execute actions resulting from state transition"""
        try:
            actions = transition_result.get('actions', [])
            if not actions:
                return
            
            # Get trade data for action execution
            trade_status = self.state_machine.get_trade_status(ticket)
            if not trade_status:
                logger.warning(f"No trade status found for {ticket}")
                return
            
            # Final verification: position still exists before executing actions (race condition protection)
            try:
                import MetaTrader5 as mt5
                verify_pos = mt5.positions_get(ticket=ticket)
                if not verify_pos or len(verify_pos) == 0:
                    logger.warning(f"Position {ticket} was closed before action execution, skipping")
                    # Mark trade as closed
                    if ticket in self.state_machine.active_trades:
                        self.state_machine.active_trades[ticket].state = TradeState.CLOSED
                    return
            except Exception as e:
                logger.warning(f"Failed to verify position {ticket} before action execution: {e}")
                return
            
            # Prepare trade data for action executor
            current_price = self._get_current_price(trade_status['symbol'])
            if current_price is None:
                logger.warning(f"Cannot execute actions for {ticket}: failed to get current price")
                return
            
            trade_data = {
                'ticket': ticket,
                'symbol': trade_status['symbol'],
                'direction': trade_status['direction'],
                'current_price': current_price,
                'entry_price': trade_status.get('entry_price', 0),
                'current_volume': trade_status.get('current_volume', 0),
                'stop_loss': trade_status.get('stop_loss'),
                'take_profit': trade_status.get('take_profit'),
                'hedge_ticket': trade_status.get('hedge_ticket')
            }
            
            # Execute actions
            results = self.action_executor.execute_actions(actions, trade_data)
            
            # Update performance stats
            self.performance_stats['actions_executed'] += len(results)
            
            # Update trade volume after partial closes
            for result in results:
                if result.success and result.action_type == 'partial_close':
                    # Refresh volume from MT5 after successful partial close
                    try:
                        import MetaTrader5 as mt5
                        mt5_positions = mt5.positions_get(ticket=ticket)
                        if mt5_positions and len(mt5_positions) > 0:
                            actual_volume = mt5_positions[0].volume
                            trade_status = self.state_machine.get_trade_status(ticket)
                            if trade_status:
                                # Update state machine with actual volume
                                trade = self.state_machine.active_trades.get(ticket)
                                if trade:
                                    trade.current_volume = float(actual_volume)
                                    logger.debug(f"Updated volume for {ticket} to {actual_volume} after partial close")
                    except Exception as e:
                        logger.warning(f"Failed to update volume for {ticket} after partial close: {e}")
            
            # Log results
            for result in results:
                if result.success:
                    logger.info(f"Action executed: {result.action_type} for {ticket}")
                else:
                    logger.error(f"Action failed: {result.action_type} for {ticket} - {result.error_message}")
            
        except Exception as e:
            logger.error(f"Failed to execute state actions for {ticket}: {e}")
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        try:
            # MT5Service has get_quote(), not get_tick()
            quote = self.mt5_service.get_quote(symbol)
            if quote:
                return (quote.bid + quote.ask) / 2
            return None
        except Exception as e:
            logger.error(f"Failed to get current price for {symbol}: {e}")
            return None
    
    def _get_binance_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get Binance order flow data"""
        try:
            # ⭐ NEW: Try OrderFlowService first (BTCUSD only)
            if self.order_flow_service and self.order_flow_service.running:
                binance_symbol = self._convert_to_binance_symbol(symbol)
                pressure_data = self.order_flow_service.get_buy_sell_pressure(binance_symbol, window=30)
                if pressure_data:
                    # Calculate delta Z-score (simplified)
                    delta = pressure_data.get('net_volume', 0)
                    delta_z = delta / 1000.0 if delta != 0 else 0.0  # Simplified normalization
                    
                    return {
                        'buy_volume': pressure_data.get('buy_volume', 0),
                        'sell_volume': pressure_data.get('sell_volume', 0),
                        'delta_z_score': delta_z,
                        'pressure': pressure_data.get('pressure', 1.0),
                        'source': 'order_flow_service'  # Mark source
                    }
            
            # Fallback: BinanceService (if available, but doesn't have get_pressure method)
            # This path currently returns None, but kept for future compatibility
            if not self.binance_service:
                return None
            
            # Note: BinanceService.get_pressure() doesn't exist - OrderFlowService is required
            return None
            
        except Exception as e:
            logger.debug(f"Failed to get Binance order flow data for {symbol}: {e}")
            return None
    
    def _convert_to_binance_symbol(self, mt5_symbol: str) -> str:
        """Convert MT5 symbol to Binance symbol"""
        symbol = mt5_symbol.upper()
        
        # Remove 'c' suffix
        if symbol.endswith("C"):
            symbol = symbol[:-1]
        
        # Add USDT for crypto pairs
        if symbol.startswith(("BTC", "ETH", "LTC", "XRP", "ADA")):
            if not symbol.endswith("USDT"):
                symbol = symbol.replace("USD", "USDT")
        
        return symbol.lower()
    
    def _send_notification(self, message: str):
        """Send notification via Telegram"""
        try:
            if self.telegram_service:
                self.telegram_service.send_message(message)
            else:
                logger.info(f"DTMS: {message}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive DTMS system status"""
        try:
            current_time = time.time()
            uptime = current_time - self.performance_stats['start_time']
            
            # Get active trades
            active_trades = self.state_machine.get_all_trades_status()
            
            # Get data health
            data_health = {}
            for trade in active_trades:
                symbol = trade['symbol']
                if symbol not in data_health:
                    data_health[symbol] = self.data_manager.get_data_health(symbol)
            
            # Calculate performance metrics
            fast_checks_per_hour = (self.performance_stats['fast_checks_total'] / uptime) * 3600 if uptime > 0 else 0
            deep_checks_per_hour = (self.performance_stats['deep_checks_total'] / uptime) * 3600 if uptime > 0 else 0
            
            return {
                'monitoring_active': self.monitoring_active,
                'uptime_seconds': uptime,
                'uptime_human': str(timedelta(seconds=int(uptime))),
                'active_trades': len(active_trades),
                'trades_by_state': self._count_trades_by_state(active_trades),
                'performance': {
                    'fast_checks_total': self.performance_stats['fast_checks_total'],
                    'deep_checks_total': self.performance_stats['deep_checks_total'],
                    'actions_executed': self.performance_stats['actions_executed'],
                    'state_transitions': self.performance_stats['state_transitions'],
                    'fast_checks_per_hour': fast_checks_per_hour,
                    'deep_checks_per_hour': deep_checks_per_hour
                },
                'data_health': data_health,
                'last_update': current_time
            }
            
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {'error': str(e)}
    
    def _count_trades_by_state(self, active_trades: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count trades by state"""
        state_counts = {}
        for trade in active_trades:
            state = trade.get('state', 'UNKNOWN')
            state_counts[state] = state_counts.get(state, 0) + 1
        return state_counts
    
    def get_trade_status(self, ticket: int) -> Optional[Dict[str, Any]]:
        """Get detailed status for a specific trade"""
        try:
            return self.state_machine.get_trade_status(ticket)
        except Exception as e:
            logger.error(f"Failed to get trade status for {ticket}: {e}")
            return None
    
    def get_action_history(self, ticket: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get action history"""
        try:
            results = self.action_executor.get_action_history(ticket)
            return [
                {
                    'success': result.success,
                    'action_type': result.action_type,
                    'details': result.details,
                    'error_message': result.error_message,
                    'timestamp': result.timestamp,
                    'time_human': datetime.fromtimestamp(result.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                }
                for result in results
            ]
        except Exception as e:
            logger.error(f"Failed to get action history: {e}")
            return []
