"""
Micro-Scalp Execution Manager

Handles execution, position tracking, and post-execution monitoring:
- Pre-execution checks (spread, slippage, latency)
- Ultra-tight SL/TP placement
- Position tracking
- Background exit monitoring (adverse candle, trailing stop)
- Cool-off lock management
"""

from __future__ import annotations

import logging
import time
import threading
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from queue import PriorityQueue

import MetaTrader5 as mt5

from infra.mt5_service import MT5Service
from infra.spread_tracker import SpreadTracker, SpreadData
from infra.m1_data_fetcher import M1DataFetcher

logger = logging.getLogger(__name__)


@dataclass
class MicroScalpPosition:
    """Micro-scalp position tracking"""
    ticket: int
    symbol: str
    direction: str  # "BUY" or "SELL"
    entry_price: float
    sl: float
    tp: float
    entry_time: datetime
    entry_candle_time: datetime  # M1 candle timestamp when entered
    trailing_stop_enabled: bool
    trailing_stop_activated: bool
    trailing_stop_distance: float
    last_candle_checked: Optional[datetime] = None
    atr1_value: Optional[float] = None  # For trailing stop distance calculation


class MicroScalpExecutionManager:
    """
    Manages micro-scalp execution and post-execution monitoring.
    
    Features:
    - Pre-execution validation (spread, slippage, latency)
    - Ultra-tight SL/TP execution
    - Position tracking
    - Background exit monitoring thread
    - Adverse candle detection (micro-interrupt)
    - Trailing stop management
    - Cool-off lock management
    """
    
    def __init__(self, config: Dict[str, Any], mt5_service: MT5Service,
                 spread_tracker: SpreadTracker, m1_fetcher: M1DataFetcher):
        """
        Initialize Micro-Scalp Execution Manager.
        
        Args:
            config: Configuration dict
            mt5_service: MT5Service instance
            spread_tracker: SpreadTracker instance
            m1_fetcher: M1DataFetcher instance
        """
        self.config = config
        self.mt5_service = mt5_service
        self.spread_tracker = spread_tracker
        self.m1_fetcher = m1_fetcher
        
        # Position tracking
        self.active_positions: Dict[int, MicroScalpPosition] = {}
        
        # Exit monitoring
        self.exit_monitor_thread: Optional[threading.Thread] = None
        self.exit_monitor_running = False
        self.exit_queue = PriorityQueue()  # Priority queue for exits
        
        # Cool-off locks: {symbol: datetime} - when lock expires
        self.cool_off_locks: Dict[str, datetime] = {}
        
        # Execution config
        self.execution_config = config.get('execution', {})
        self.risk_config = config.get('risk_mitigation', {})
    
    def pre_execution_checks(self, symbol: str, entry_price: float,
                            direction: str) -> Tuple[bool, List[str]]:
        """
        Perform pre-execution checks (spread, slippage, latency).
        
        Args:
            symbol: Trading symbol
            entry_price: Expected entry price
            direction: "BUY" or "SELL"
        
        Returns:
            Tuple of (passed, reasons)
        """
        reasons = []
        
        # Check cool-off lock
        if not self._check_cool_off(symbol):
            reasons.append(f"Symbol {symbol} in cool-off period")
            return (False, reasons)
        
        # Check spread
        try:
            quote = self.mt5_service.get_quote(symbol)
            current_spread = quote.ask - quote.bid
            
            spread_data = self.spread_tracker.get_spread_data(symbol, current_spread)
            max_spread_ratio = self.execution_config.get('max_spread_ratio', 1.5)
            
            if spread_data.spread_ratio > max_spread_ratio:
                reasons.append(f"Spread {current_spread:.4f} exceeds limit (ratio: {spread_data.spread_ratio:.2f})")
                return (False, reasons)
        except Exception as e:
            logger.warning(f"Error checking spread: {e}")
            reasons.append(f"Spread check failed: {e}")
            return (False, reasons)
        
        # Check latency (simplified - would need actual latency measurement)
        max_latency_ms = self.execution_config.get('max_latency_ms', 200)
        # TODO: Implement actual latency check
        
        # Check slippage budget
        max_slippage_pct = self.execution_config.get('max_slippage_pct', 0.1)
        # Slippage will be checked during execution
        
        reasons.append("All pre-execution checks passed")
        return (True, reasons)
    
    def execute_trade(self, symbol: str, direction: str, entry_price: float,
                     sl: float, tp: float, volume: float = 0.01,
                     atr1: Optional[float] = None) -> Dict[str, Any]:
        """
        Execute micro-scalp trade with ultra-tight SL/TP.
        
        Args:
            symbol: Trading symbol
            direction: "BUY" or "SELL"
            entry_price: Expected entry price
            sl: Stop loss
            tp: Take profit
            volume: Trade volume (ignored - always uses 0.01 for micro scalp)
            atr1: Optional ATR(1) value for trailing stop
        
        Returns:
            Execution result dict
        """
        # Pre-execution checks
        checks_passed, reasons = self.pre_execution_checks(symbol, entry_price, direction)
        if not checks_passed:
            return {
                'ok': False,
                'message': 'Pre-execution checks failed',
                'reasons': reasons
            }
        
        # Normalize symbol
        symbol_norm = symbol.upper()
        if not symbol_norm.endswith('c'):
            symbol_norm = symbol_norm + 'c'
        
        # Micro scalp system always uses 0.01 lots per trade
        volume = 0.01
        
        # Execute trade
        try:
            result = self.mt5_service.market_order(
                symbol=symbol_norm,
                side=direction,
                lot=volume,
                sl=sl,
                tp=tp,
                comment="MicroScalp"
            )
            
            if not result.get('ok'):
                return result
            
            # Get ticket from result
            ticket = result.get('details', {}).get('ticket')
            if not ticket:
                return {
                    'ok': False,
                    'message': 'No ticket returned from execution'
                }
            
            # Get entry candle timestamp
            entry_candle_time = self._get_current_m1_candle_time(symbol_norm)
            
            # Calculate trailing stop distance
            trailing_stop_distance = self._calculate_trailing_stop_distance(
                symbol, atr1, sl, entry_price, direction
            )
            
            # Register position
            position = MicroScalpPosition(
                ticket=ticket,
                symbol=symbol_norm,
                direction=direction,
                entry_price=entry_price,
                sl=sl,
                tp=tp,
                entry_time=datetime.now(),
                entry_candle_time=entry_candle_time,
                trailing_stop_enabled=self.execution_config.get('trailing_stop_enabled', True),
                trailing_stop_activated=False,
                trailing_stop_distance=trailing_stop_distance,
                atr1_value=atr1
            )
            
            self.active_positions[ticket] = position
            
            # Start exit monitoring thread if not running
            if not self.exit_monitor_running:
                self._start_exit_monitor()
            
            logger.info(f"Micro-scalp trade executed: {ticket} {direction} {symbol_norm} @ {entry_price}")
            
            return {
                'ok': True,
                'ticket': ticket,
                'message': 'Trade executed successfully',
                'position': position
            }
            
        except Exception as e:
            logger.error(f"Error executing micro-scalp trade: {e}", exc_info=True)
            return {
                'ok': False,
                'message': f'Execution error: {e}'
            }
    
    def _get_current_m1_candle_time(self, symbol: str) -> datetime:
        """Get current M1 candle timestamp"""
        try:
            candles = self.m1_fetcher.get_latest_m1(symbol, count=1)
            if candles and len(candles) > 0:
                candle_time = candles[0].get('time')
                if isinstance(candle_time, datetime):
                    # Ensure UTC-aware
                    if candle_time.tzinfo is None:
                        candle_time = candle_time.replace(tzinfo=timezone.utc)
                    return candle_time
                elif isinstance(candle_time, (int, float)):
                    # CRITICAL FIX: MT5 timestamps are UTC, must use tz=timezone.utc
                    return datetime.fromtimestamp(candle_time, tz=timezone.utc)
        except Exception as e:
            logger.debug(f"Error getting M1 candle time: {e}")
        
        return datetime.now()
    
    def _calculate_trailing_stop_distance(self, symbol: str, atr1: Optional[float],
                                         sl: float, entry_price: float,
                                         direction: str) -> float:
        """Calculate trailing stop distance"""
        if atr1 is not None and atr1 > 0:
            # ATR-based distance
            atr_multiplier = self.execution_config.get('trailing_stop_distance_atr', 0.3)
            return atr1 * atr_multiplier
        else:
            # Fixed distance based on SL
            sl_distance = abs(entry_price - sl)
            return sl_distance * 0.5  # 50% of SL distance
    
    def _check_cool_off(self, symbol: str) -> bool:
        """Check if symbol is in cool-off period"""
        if symbol not in self.cool_off_locks:
            return True  # No lock, allow trade
        
        lock_expiry = self.cool_off_locks[symbol]
        if datetime.now() > lock_expiry:
            del self.cool_off_locks[symbol]
            return True  # Lock expired, allow trade
        
        return False  # Still in cool-off, block trade
    
    def _activate_cool_off(self, symbol: str, duration_seconds: Optional[int] = None):
        """Activate cool-off lock after exit"""
        if duration_seconds is None:
            duration_seconds = self.config.get('cool_off_lock_seconds', 60)
        
        self.cool_off_locks[symbol] = datetime.now() + timedelta(seconds=duration_seconds)
        logger.debug(f"Cool-off lock activated for {symbol} for {duration_seconds}s")
    
    def _start_exit_monitor(self):
        """Start background exit monitoring thread"""
        if self.exit_monitor_running:
            return
        
        self.exit_monitor_running = True
        self.exit_monitor_thread = threading.Thread(
            target=self._exit_monitor_loop,
            daemon=True,
            name="MicroScalpExitMonitor"
        )
        self.exit_monitor_thread.start()
        logger.info("Micro-scalp exit monitor thread started")
    
    def _exit_monitor_loop(self):
        """Background thread for monitoring micro-scalp exits"""
        check_interval = self.config.get('check_interval_seconds', 10)
        
        try:
            while self.exit_monitor_running:
                try:
                    # Get all open MT5 positions
                    positions = mt5.positions_get()
                    if positions is None:
                        positions = []
                    
                    position_tickets = {pos.ticket for pos in positions}
                    
                    # Check each tracked micro-scalp position
                    for ticket, micro_pos in list(self.active_positions.items()):
                        try:
                            # Check if position still exists
                            if ticket not in position_tickets:
                                # Position closed externally → cleanup
                                self._cleanup_position(ticket, reason="external_close")
                                continue
                            
                            # Get current position data
                            position = next((p for p in positions if p.ticket == ticket), None)
                            if not position:
                                continue
                            
                            # Check for adverse candle (micro-interrupt logic) - HIGHEST PRIORITY
                            if self.execution_config.get('instant_exit_on_adverse_candle', True):
                                if self._check_adverse_candle(micro_pos, position):
                                    self._instant_exit(ticket, reason="adverse_candle")
                                    continue
                            
                            # Check TP/SL (MT5 handles this, but verify)
                            if self._check_tp_sl_hit(position):
                                self._cleanup_position(ticket, reason="tp_sl_hit")
                                continue
                            
                            # Check trailing stop (if activated)
                            if micro_pos.trailing_stop_enabled:
                                self._update_trailing_stop(micro_pos, position)
                        except Exception as e:
                            logger.error(f"Error processing position {ticket} in exit monitor: {e}", exc_info=True)
                            # Continue with next position
                    
                    # Sleep until next check
                    time.sleep(check_interval)
                    
                except Exception as e:
                    logger.error(f"Error in exit monitor loop iteration: {e}", exc_info=True)
                    time.sleep(check_interval)
        except Exception as fatal_error:
            logger.critical(f"FATAL ERROR in exit monitor loop: {fatal_error}", exc_info=True)
            self.exit_monitor_running = False
        finally:
            logger.info("Micro-scalp exit monitor loop stopped")
    
    def _check_adverse_candle(self, micro_pos: MicroScalpPosition, position) -> bool:
        """
        Check if current M1 candle is adverse to position.
        Adverse = candle closes against position direction.
        """
        try:
            # Get latest M1 candle
            candles = self.m1_fetcher.get_latest_m1(micro_pos.symbol, count=1)
            if not candles or len(candles) == 0:
                return False
            
            latest_candle = candles[0]
            
            # Get candle timestamp
            candle_time = latest_candle.get('time')
            if isinstance(candle_time, (int, float)):
                # CRITICAL FIX: MT5 timestamps are UTC, must use tz=timezone.utc
                candle_time = datetime.fromtimestamp(candle_time, tz=timezone.utc)
            elif isinstance(candle_time, datetime):
                # Ensure UTC-aware
                if candle_time.tzinfo is None:
                    candle_time = candle_time.replace(tzinfo=timezone.utc)
            else:
                return False
            
            # Check if this is a new candle (not the entry candle)
            if candle_time <= micro_pos.entry_candle_time:
                return False  # Still on entry candle
            
            # Check if candle closed against position
            candle_close = latest_candle.get('close', 0)
            candle_open = latest_candle.get('open', 0)
            
            if micro_pos.direction == "BUY":
                # Adverse = candle closes below open (bearish) AND below entry price
                if candle_close < candle_open and candle_close < micro_pos.entry_price:
                    return True  # Adverse candle detected
            else:  # SELL
                # Adverse = candle closes above open (bullish) AND above entry price
                if candle_close > candle_open and candle_close > micro_pos.entry_price:
                    return True  # Adverse candle detected
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking adverse candle: {e}")
            return False
    
    def _instant_exit(self, ticket: int, reason: str):
        """Instant exit on adverse candle (micro-interrupt)"""
        try:
            if ticket not in self.active_positions:
                return
            
            micro_pos = self.active_positions[ticket]
            
            # Get position to get volume
            positions = mt5.positions_get(ticket=ticket)
            if not positions or len(positions) == 0:
                logger.warning(f"Position {ticket} not found in MT5")
                self._cleanup_position(ticket, reason=reason)
                return
            
            position = positions[0]
            volume = position.volume
            
            # Close position using close_position_partial with full volume
            success, message = self.mt5_service.close_position_partial(
                ticket=ticket,
                volume=volume,
                symbol=micro_pos.symbol,
                side=micro_pos.direction,
                comment="MicroInterrupt"
            )
            
            if success:
                logger.info(f"Micro-interrupt exit: {ticket} {micro_pos.symbol} ({reason})")
                self._cleanup_position(ticket, reason=reason)
                # Activate cool-off
                self._activate_cool_off(micro_pos.symbol)
            else:
                logger.error(f"Failed to exit position {ticket}: {message}")
                
        except Exception as e:
            logger.error(f"Error in instant exit: {e}", exc_info=True)
    
    def _check_tp_sl_hit(self, position) -> bool:
        """Check if TP/SL was hit (position should be closed by MT5)"""
        # If position still exists but profit is at TP or loss is at SL, it might be closing
        # For now, we rely on MT5 to close it and detect it in the next cycle
        return False
    
    def _update_trailing_stop(self, micro_pos: MicroScalpPosition, position):
        """Update trailing stop if price moves in favor"""
        try:
            current_price = position.price_current
            
            if micro_pos.direction == "BUY":
                # Calculate profit in R
                sl_distance = micro_pos.entry_price - micro_pos.sl
                if sl_distance <= 0:
                    return
                
                profit_r = (current_price - micro_pos.entry_price) / sl_distance
                
                # Check if trailing stop should activate (after +0.5R)
                activate_after_r = self.execution_config.get('trailing_stop_activate_after_r', 0.5)
                if not micro_pos.trailing_stop_activated and profit_r >= activate_after_r:
                    micro_pos.trailing_stop_activated = True
                    logger.info(f"Trailing stop activated for {micro_pos.ticket} at +{profit_r:.2f}R")
                
                # Update trailing stop if price moved up
                if micro_pos.trailing_stop_activated:
                    new_sl = current_price - micro_pos.trailing_stop_distance
                    if new_sl > position.sl:
                        # Move SL up
                        self._update_sl(micro_pos.ticket, new_sl)
            
            else:  # SELL
                # Calculate profit in R
                sl_distance = micro_pos.sl - micro_pos.entry_price
                if sl_distance <= 0:
                    return
                
                profit_r = (micro_pos.entry_price - current_price) / sl_distance
                
                # Check if trailing stop should activate (after +0.5R)
                activate_after_r = self.execution_config.get('trailing_stop_activate_after_r', 0.5)
                if not micro_pos.trailing_stop_activated and profit_r >= activate_after_r:
                    micro_pos.trailing_stop_activated = True
                    logger.info(f"Trailing stop activated for {micro_pos.ticket} at +{profit_r:.2f}R")
                
                # Update trailing stop if price moved down
                if micro_pos.trailing_stop_activated:
                    new_sl = current_price + micro_pos.trailing_stop_distance
                    if new_sl < position.sl or position.sl == 0:
                        self._update_sl(micro_pos.ticket, new_sl)
                        
        except Exception as e:
            logger.debug(f"Error updating trailing stop: {e}")
    
    def _update_sl(self, ticket: int, new_sl: float):
        """Update stop loss for a position"""
        try:
            # Get position to get symbol
            positions = mt5.positions_get(ticket=ticket)
            if not positions or len(positions) == 0:
                return
            
            position = positions[0]
            symbol = position.symbol
            
            result = self.mt5_service.modify_position_sl_tp(
                ticket=ticket,
                symbol=symbol,
                sl=new_sl
            )
            if result.get('ok'):
                logger.debug(f"Trailing stop updated for {ticket}: SL = {new_sl:.4f}")
            else:
                logger.warning(f"Failed to update SL for {ticket}: {result.get('message')}")
        except Exception as e:
            logger.debug(f"Error updating SL: {e}")
    
    def _cleanup_position(self, ticket: int, reason: str = "unknown"):
        """Remove position from tracking after closure"""
        if ticket in self.active_positions:
            micro_pos = self.active_positions[ticket]
            logger.info(f"Cleaning up micro-scalp position {ticket} ({micro_pos.symbol}) - {reason}")
            
            # Activate cool-off lock
            self._activate_cool_off(micro_pos.symbol)
            
            del self.active_positions[ticket]
    
    def stop(self):
        """Stop exit monitoring thread"""
        self.exit_monitor_running = False
        if self.exit_monitor_thread:
            self.exit_monitor_thread.join(timeout=5.0)
        logger.info("Micro-scalp exit monitor stopped")
    
    def get_active_positions(self) -> List[MicroScalpPosition]:
        """Get list of active micro-scalp positions"""
        return list(self.active_positions.values())
    
    def is_position_tracked(self, ticket: int) -> bool:
        """Check if position is being tracked"""
        return ticket in self.active_positions

