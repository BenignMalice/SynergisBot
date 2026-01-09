"""
Range Scalping Monitor
Background monitoring thread for range scalping trades.

Runs every 5 minutes to check all active trades for exit conditions.
"""

import threading
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List

import MetaTrader5 as mt5

from infra.range_scalping_exit_manager import RangeScalpingExitManager
from infra.range_boundary_detector import RangeStructure

logger = logging.getLogger(__name__)


class RangeScalpingMonitor:
    """
    Background monitoring thread for range scalping trades.
    
    Runs every 5 minutes to check all active trades for exit conditions.
    """
    
    def __init__(self, exit_manager: RangeScalpingExitManager, config: Dict):
        self.exit_manager = exit_manager
        self.config = config
        self.running = False
        self.check_interval = config.get("range_monitoring_during_trade", {}).get("check_interval_minutes", 5) * 60  # Convert to seconds
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Get MT5 service reference if available (for candle fetching)
        self.mt5_service = None  # Will be set if available
    
    def start(self):
        """Start monitoring in background thread"""
        if self.running:
            logger.warning("Range Scalping Monitor already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"✅ Range Scalping Monitor started (check interval: {self.check_interval/60:.0f} min)")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        logger.info("Range Scalping Monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop - runs in background thread"""
        while self.running:
            try:
                # Get all active trades (thread-safe)
                active_trades = self.exit_manager.get_active_trades_copy()
                
                if not active_trades:
                    time.sleep(self.check_interval)
                    continue
                
                logger.debug(f"Monitoring {len(active_trades)} active range scalp trades")
                
                # Check each trade for exit conditions
                for ticket, trade_data in active_trades.items():
                    try:
                        # Skip if trade not found in MT5 (may have been closed externally)
                        position = self._get_mt5_position(ticket)
                        if not position:
                            logger.warning(f"Trade {ticket} not found in MT5 - removing from monitoring")
                            self.exit_manager.unregister_trade(ticket)
                            continue
                        
                        # Get current market data
                        symbol = trade_data["symbol"]
                        current_price = position.price_current
                        entry_price = trade_data["entry_price"]
                        stop_loss = trade_data["sl"]
                        take_profit = trade_data["tp"]
                        
                        # Calculate time in trade
                        entry_time = datetime.fromisoformat(trade_data["entry_time"].replace('Z', '+00:00'))
                        time_in_trade = (datetime.now(timezone.utc) - entry_time).total_seconds() / 60
                        
                        # Reconstruct range data
                        range_data = RangeStructure.from_dict(trade_data["range_data"])
                        
                        # Get recent candles for range validation
                        recent_candles = self._get_recent_candles(symbol, timeframe="M5", count=20)
                        
                        # Check range invalidation during trade
                        is_invalidated, invalidation_signals = self.exit_manager.check_range_invalidation_during_trade(
                            range_data=range_data,
                            recent_candles=recent_candles,
                            current_price=current_price
                        )
                        
                        # Prepare market data for exit condition checks
                        market_data = {
                            "range_invalidated": is_invalidated,
                            "invalidation_signals": invalidation_signals,
                            "m15_bos_confirmed": "m15_bos_confirmed" in invalidation_signals,
                            "effective_atr": range_data.range_width_atr,
                            "cvd_divergence_strength": 0.0,  # Would need CVD calculation
                            "tape_pressure_shift": 0.0  # Would need order flow data
                        }
                        
                        # Check early exit conditions
                        exit_signal = self.exit_manager.check_early_exit_conditions(
                            trade=trade_data,
                            current_price=current_price,
                            entry_price=entry_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            time_in_trade=time_in_trade,
                            range_data=range_data,
                            market_data=market_data
                        )
                        
                        if exit_signal:
                            logger.info(
                                f"Exit signal for trade {ticket} ({symbol}): "
                                f"{exit_signal.priority} - {exit_signal.reason} - {exit_signal.message}"
                            )
                            
                            # Execute exit
                            success = self.exit_manager.execute_exit(ticket, exit_signal)
                            if success:
                                logger.info(f"✅ Successfully executed exit for trade {ticket}")
                            else:
                                logger.warning(f"⚠️ Failed to execute exit for trade {ticket}")
                    
                    except Exception as e:
                        logger.error(f"Error monitoring trade {ticket}: {e}", exc_info=True)
                        self.exit_manager.error_handler.handle_error("monitoring_error", {
                            "ticket": ticket,
                            "error": str(e)
                        })
                
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}", exc_info=True)
                self.exit_manager.error_handler.handle_error("monitoring_loop_crashed", {
                    "error": str(e),
                    "severity": "critical"
                })
                time.sleep(60)  # Wait 1 min before retrying
    
    def _get_mt5_position(self, ticket: int):
        """Get MT5 position by ticket"""
        try:
            positions = mt5.positions_get(ticket=ticket)
            if positions and len(positions) > 0:
                return positions[0]
            return None
        except Exception as e:
            logger.debug(f"Error getting MT5 position {ticket}: {e}")
            return None
    
    def _get_recent_candles(self, symbol: str, timeframe: str = "M5", count: int = 20) -> List[Dict]:
        """Get recent candles for analysis"""
        try:
            # Map timeframe string to MT5 constant
            tf_map = {
                "M1": mt5.TIMEFRAME_M1,
                "M5": mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15,
                "H1": mt5.TIMEFRAME_H1
            }
            
            mt5_tf = tf_map.get(timeframe, mt5.TIMEFRAME_M5)
            
            # Get candles
            rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
            if rates is None or len(rates) == 0:
                return []
            
            # Convert to list of dicts
            candles = []
            for rate in rates:
                candles.append({
                    "time": datetime.fromtimestamp(rate['time']),
                    "open": float(rate['open']),
                    "high": float(rate['high']),
                    "low": float(rate['low']),
                    "close": float(rate['close']),
                    "tick_volume": int(rate['tick_volume']),
                    "volume": int(rate.get('real_volume', rate['tick_volume']))
                })
            
            return candles
            
        except Exception as e:
            logger.debug(f"Error getting candles for {symbol}: {e}")
            return []
    
    def _calculate_time_in_trade(self, entry_time_str: str) -> float:
        """Calculate time in trade (minutes)"""
        try:
            entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            return (now - entry_time).total_seconds() / 60
        except Exception as e:
            logger.debug(f"Error calculating time in trade: {e}")
            return 0.0

