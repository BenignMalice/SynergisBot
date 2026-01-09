"""
DTMS MT5 Adapter
Wrapper for MT5 service integration with DTMS
"""

import logging
from typing import Optional, Dict, Any, List
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

class DTMSMT5Adapter:
    """
    MT5 adapter for DTMS system.
    Provides enhanced MT5 functionality for defensive trade management.
    """
    
    def __init__(self, mt5_service):
        self.mt5_service = mt5_service
        
        logger.info("DTMSMT5Adapter initialized")
    
    def get_bars(self, symbol: str, timeframe: str, count: int) -> Optional[Any]:
        """Get historical bars for symbol"""
        try:
            # Convert timeframe string to MT5 constant
            tf_map = {
                'M1': mt5.TIMEFRAME_M1,
                'M5': mt5.TIMEFRAME_M5,
                'M15': mt5.TIMEFRAME_M15,
                'M30': mt5.TIMEFRAME_M30,
                'H1': mt5.TIMEFRAME_H1,
                'H4': mt5.TIMEFRAME_H4,
                'D1': mt5.TIMEFRAME_D1
            }
            
            tf = tf_map.get(timeframe.upper())
            if tf is None:
                logger.error(f"Unsupported timeframe: {timeframe}")
                return None
            
            # Get bars using MT5 service
            return self.mt5_service.get_bars(symbol, tf, count)
            
        except Exception as e:
            logger.error(f"Failed to get bars for {symbol} {timeframe}: {e}")
            return None
    
    def get_tick(self, symbol: str) -> Optional[Any]:
        """Get current tick for symbol"""
        try:
            return self.mt5_service.get_tick(symbol)
        except Exception as e:
            logger.error(f"Failed to get tick for {symbol}: {e}")
            return None
    
    def modify_position(self, ticket: int, sl: float = None, tp: float = None) -> bool:
        """Modify position SL/TP"""
        try:
            return self.mt5_service.modify_position(ticket, sl, tp)
        except Exception as e:
            logger.error(f"Failed to modify position {ticket}: {e}")
            return False
    
    def close_position(self, ticket: int) -> bool:
        """Close position"""
        try:
            return self.mt5_service.close_position(ticket)
        except Exception as e:
            logger.error(f"Failed to close position {ticket}: {e}")
            return False
    
    def close_position_partial(self, ticket: int, volume: float) -> bool:
        """Close position partially"""
        try:
            return self.mt5_service.close_position_partial(ticket, volume)
        except Exception as e:
            logger.error(f"Failed to close position {ticket} partially: {e}")
            return False
    
    def place_order(self, symbol: str, order_type: str, direction: str, volume: float, 
                   sl: float = None, tp: float = None, comment: str = "") -> Optional[int]:
        """Place order"""
        try:
            return self.mt5_service.place_order(
                symbol=symbol,
                order_type=order_type,
                direction=direction,
                volume=volume,
                sl=sl,
                tp=tp,
                comment=comment
            )
        except Exception as e:
            logger.error(f"Failed to place order for {symbol}: {e}")
            return None
    
    def get_position_info(self, ticket: int) -> Optional[Dict[str, Any]]:
        """Get position information"""
        try:
            positions = mt5.positions_get(ticket=ticket)
            if positions and len(positions) > 0:
                pos = positions[0]
                return {
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': pos.type,
                    'volume': pos.volume,
                    'price_open': pos.price_open,
                    'sl': pos.sl,
                    'tp': pos.tp,
                    'price_current': pos.price_current,
                    'profit': pos.profit,
                    'swap': pos.swap,
                    'time': pos.time
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get position info for {ticket}: {e}")
            return None
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get symbol information"""
        try:
            info = mt5.symbol_info(symbol)
            if info:
                return {
                    'symbol': info.name,
                    'point': info.point,
                    'digits': info.digits,
                    'spread': info.spread,
                    'trade_mode': info.trade_mode,
                    'trade_stops_level': info.trade_stops_level,
                    'trade_freeze_level': info.trade_freeze_level,
                    'volume_min': info.volume_min,
                    'volume_max': info.volume_max,
                    'volume_step': info.volume_step
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get symbol info for {symbol}: {e}")
            return None
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get account information"""
        try:
            account = mt5.account_info()
            if account:
                return {
                    'login': account.login,
                    'balance': account.balance,
                    'equity': account.equity,
                    'margin': account.margin,
                    'free_margin': account.margin_free,
                    'margin_level': account.margin_level,
                    'currency': account.currency,
                    'leverage': account.leverage
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return None
