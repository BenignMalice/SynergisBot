"""
DTMS Integration
Main integration file for the Defensive Trade Management System
"""

import logging
import asyncio
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from dtms_core.dtms_engine import DTMSEngine
from dtms_integration.mt5_adapter import DTMSMT5Adapter
from dtms_integration.binance_adapter import DTMSBinanceAdapter
from dtms_integration.telegram_adapter import DTMSTelegramAdapter

logger = logging.getLogger(__name__)

# Global DTMS instance
_dtms_engine: Optional[DTMSEngine] = None
_dtms_mt5_adapter: Optional[DTMSMT5Adapter] = None
_dtms_binance_adapter: Optional[DTMSBinanceAdapter] = None
_dtms_telegram_adapter: Optional[DTMSTelegramAdapter] = None

def initialize_dtms(mt5_service, binance_service=None, telegram_service=None, order_flow_service=None) -> bool:
    """
    Initialize the DTMS system.
    
    Args:
        mt5_service: MT5 service instance
        binance_service: Binance service instance (optional)
        telegram_service: Telegram service instance (optional)
        order_flow_service: OrderFlowService instance (optional, for BTCUSD order flow)
        
    Returns:
        bool: True if initialization successful
    """
    global _dtms_engine, _dtms_mt5_adapter, _dtms_binance_adapter, _dtms_telegram_adapter
    
    try:
        logger.info("Initializing DTMS system...")
        
        # Initialize adapters
        _dtms_mt5_adapter = DTMSMT5Adapter(mt5_service)
        _dtms_binance_adapter = DTMSBinanceAdapter(binance_service) if binance_service else None
        _dtms_telegram_adapter = DTMSTelegramAdapter(telegram_service) if telegram_service else None
        
        # Initialize DTMS engine
        _dtms_engine = DTMSEngine(
            mt5_service=mt5_service,
            binance_service=binance_service,
            telegram_service=telegram_service,
            order_flow_service=order_flow_service  # NEW: Pass OrderFlowService for BTCUSD
        )
        
        logger.info("DTMS system initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize DTMS system: {e}")
        return False

def start_dtms_monitoring() -> bool:
    """Start DTMS monitoring"""
    global _dtms_engine
    
    try:
        if not _dtms_engine:
            logger.error("DTMS engine not initialized")
            return False
        
        return _dtms_engine.start_monitoring()
        
    except Exception as e:
        logger.error(f"Failed to start DTMS monitoring: {e}")
        return False

def stop_dtms_monitoring() -> bool:
    """Stop DTMS monitoring"""
    global _dtms_engine
    
    try:
        if not _dtms_engine:
            logger.error("DTMS engine not initialized")
            return False
        
        return _dtms_engine.stop_monitoring()
        
    except Exception as e:
        logger.error(f"Failed to stop DTMS monitoring: {e}")
        return False

def add_trade_to_dtms(
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
        
    Returns:
        bool: True if trade added successfully
    """
    global _dtms_engine
    
    try:
        if not _dtms_engine:
            logger.error("DTMS engine not initialized")
            return False
        
        return _dtms_engine.add_trade_monitoring(
            ticket=ticket,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            volume=volume,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
    except Exception as e:
        logger.error(f"Failed to add trade to DTMS: {e}")
        return False

def remove_trade_from_dtms(ticket: int) -> bool:
    """
    Remove a trade from DTMS monitoring.
    
    Args:
        ticket: Trade ticket number
        
    Returns:
        bool: True if trade removed successfully
    """
    global _dtms_engine
    
    try:
        if not _dtms_engine:
            logger.error("DTMS engine not initialized")
            return False
        
        return _dtms_engine.remove_trade_monitoring(ticket)
        
    except Exception as e:
        logger.error(f"Failed to remove trade from DTMS: {e}")
        return False

async def run_dtms_monitoring_cycle():
    """Run one DTMS monitoring cycle"""
    global _dtms_engine
    
    try:
        if not _dtms_engine:
            logger.error("DTMS engine not initialized")
            return
        
        await _dtms_engine.run_monitoring_cycle()
        
    except Exception as e:
        logger.error(f"Failed to run DTMS monitoring cycle: {e}")

def get_dtms_system_status() -> Dict[str, Any]:
    """Get DTMS system status"""
    global _dtms_engine
    
    try:
        if not _dtms_engine:
            return {'error': 'DTMS engine not initialized'}
        
        return _dtms_engine.get_system_status()
        
    except Exception as e:
        logger.error(f"Failed to get DTMS system status: {e}")
        return {'error': str(e)}

def get_dtms_trade_status(ticket: int) -> Optional[Dict[str, Any]]:
    """Get DTMS trade status"""
    global _dtms_engine
    
    try:
        if not _dtms_engine:
            logger.error("DTMS engine not initialized")
            return None
        
        return _dtms_engine.get_trade_status(ticket)
        
    except Exception as e:
        logger.error(f"Failed to get DTMS trade status for {ticket}: {e}")
        return None

def get_dtms_action_history(ticket: Optional[int] = None) -> list:
    """Get DTMS action history"""
    global _dtms_engine
    
    try:
        if not _dtms_engine:
            logger.error("DTMS engine not initialized")
            return []
        
        return _dtms_engine.get_action_history(ticket)
        
    except Exception as e:
        logger.error(f"Failed to get DTMS action history: {e}")
        return []

def is_dtms_initialized() -> bool:
    """Check if DTMS is initialized"""
    global _dtms_engine
    return _dtms_engine is not None

def is_dtms_monitoring() -> bool:
    """Check if DTMS monitoring is active"""
    global _dtms_engine
    
    try:
        if not _dtms_engine:
            return False
        
        return _dtms_engine.monitoring_active
        
    except Exception as e:
        logger.error(f"Failed to check DTMS monitoring status: {e}")
        return False

def get_dtms_engine() -> Optional[DTMSEngine]:
    """Get the global DTMS engine instance"""
    global _dtms_engine
    return _dtms_engine

# Convenience functions for common operations

def dtms_add_trade(ticket: int, symbol: str, direction: str, entry_price: float, volume: float) -> bool:
    """Convenience function to add trade to DTMS"""
    return add_trade_to_dtms(ticket, symbol, direction, entry_price, volume)


def auto_register_dtms(ticket: int, result_or_details: Dict[str, Any]) -> bool:
    """
    Auto-register trade to DTMS. Tries local engine first, falls back to API.
    
    Usage: auto_register_dtms(ticket, result_dict)  # where result_dict has symbol, direction, etc.
    
    Args:
        ticket: Trade ticket number (from MT5 order result)
        result_or_details: Dict from MT5Service.open_order() or similar, containing:
            - symbol: str
            - direction: str (BUY/SELL)
            - entry_price or price_executed: float
            - volume: float
            - stop_loss or sl or final_sl: float (optional)
            - take_profit or tp or final_tp: float (optional)
    
    Returns:
        bool: True if registered successfully, False otherwise
    """
    try:
        if not ticket:
            logger.warning(f"⚠️ Invalid ticket for DTMS registration: {ticket}")
            return False
        
        # Extract fields from result dict (handles various formats)
        symbol = result_or_details.get('symbol') or result_or_details.get('details', {}).get('symbol')
        direction = result_or_details.get('direction') or result_or_details.get('details', {}).get('direction')
        entry_price = (
            result_or_details.get('entry_price') or 
            result_or_details.get('price_executed') or 
            result_or_details.get('details', {}).get('price_executed') or
            result_or_details.get('price')
        )
        volume = (
            result_or_details.get('volume') or 
            result_or_details.get('details', {}).get('volume') or
            result_or_details.get('lot', 0.01)
        )
        stop_loss = (
            result_or_details.get('stop_loss') or 
            result_or_details.get('sl') or 
            result_or_details.get('final_sl') or
            result_or_details.get('details', {}).get('final_sl') or
            result_or_details.get('details', {}).get('sl')
        )
        take_profit = (
            result_or_details.get('take_profit') or 
            result_or_details.get('tp') or 
            result_or_details.get('final_tp') or
            result_or_details.get('details', {}).get('final_tp') or
            result_or_details.get('details', {}).get('tp')
        )
        
        if not all([symbol, direction, entry_price]):
            logger.warning(f"⚠️ Missing required fields for DTMS auto-registration: ticket={ticket}, symbol={symbol}, direction={direction}, entry_price={entry_price}")
            return False
        
        # Try local engine first (if available)
        from dtms_integration.dtms_system import get_dtms_engine, add_trade_to_dtms
        
        engine = get_dtms_engine()
        if engine is not None:
            # Use existing local registration
            try:
                success = add_trade_to_dtms(
                    ticket=ticket,
                    symbol=str(symbol),
                    direction=str(direction).upper(),
                    entry_price=float(entry_price),
                    volume=float(volume),
                    stop_loss=float(stop_loss) if stop_loss else None,
                    take_profit=float(take_profit) if take_profit else None
                )
                if success:
                    logger.info(f"✅ Trade {ticket} registered with DTMS (local engine)")
                    return True
                else:
                    logger.warning(f"⚠️ Local DTMS registration failed for {ticket}, trying API fallback")
                    # Fall through to API fallback
            except Exception as e:
                logger.warning(f"⚠️ Local DTMS registration failed for {ticket}, trying API: {e}")
                # Fall through to API fallback
        
        # Fallback to API registration
        try:
            from dtms_integration.dtms_system import register_trade_with_dtms_api
            
            # Prepare trade data for API
            trade_data = {
                "symbol": str(symbol),
                "direction": str(direction).upper(),
                "entry_price": float(entry_price),
                "volume": float(volume),
                "stop_loss": float(stop_loss) if stop_loss else None,
                "take_profit": float(take_profit) if take_profit else None
            }
            
            # Handle async in sync context properly
            try:
                loop = asyncio.get_running_loop()
                # Loop is running - use create_task (fire and forget)
                asyncio.create_task(register_trade_with_dtms_api(ticket, trade_data))
                logger.info(f"⏳ Trade {ticket} DTMS registration queued (async)")
                return True  # Assume success, will be logged asynchronously
            except RuntimeError:
                # No running loop - create new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        register_trade_with_dtms_api(ticket, trade_data)
                    )
                    return result
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"❌ DTMS API registration failed for ticket {ticket}: {e}", exc_info=True)
            return False
            
    except Exception as e:
        logger.error(f"❌ Error in auto_register_dtms for ticket {ticket}: {e}", exc_info=True)
        return False

def dtms_remove_trade(ticket: int) -> bool:
    """Convenience function to remove trade from DTMS"""
    return remove_trade_from_dtms(ticket)

def dtms_get_status() -> Dict[str, Any]:
    """Convenience function to get DTMS status"""
    return get_dtms_system_status()

def dtms_get_trade(ticket: int) -> Optional[Dict[str, Any]]:
    """Convenience function to get trade status"""
    return get_dtms_trade_status(ticket)

# Integration with existing bot systems

def integrate_with_existing_bot():
    """
    Integration guide for existing bot systems.
    
    This function provides guidance on how to integrate DTMS with existing
    trading bot infrastructure.
    """
    integration_guide = """
    DTMS Integration Guide:
    
    1. Initialize DTMS in your main bot startup:
       ```python
       from dtms_integration import initialize_dtms, start_dtms_monitoring
       
       # In your main() function
       initialize_dtms(mt5_service, binance_service, telegram_service)
       start_dtms_monitoring()
       ```
    
    2. Add trades to DTMS monitoring when opened:
       ```python
       from dtms_integration import add_trade_to_dtms
       
       # After placing a trade
       add_trade_to_dtms(ticket, symbol, direction, entry_price, volume)
       ```
    
    3. Run monitoring cycle in your main loop:
       ```python
       from dtms_integration import run_dtms_monitoring_cycle
       
       # In your main monitoring loop
       await run_dtms_monitoring_cycle()
       ```
    
    4. Remove trades when closed:
       ```python
       from dtms_integration import remove_trade_from_dtms
       
       # When closing a trade
       remove_trade_from_dtms(ticket)
       ```
    
    5. Get system status:
       ```python
       from dtms_integration import get_dtms_system_status
       
       status = get_dtms_system_status()
       print(f"Active trades: {status['active_trades']}")
       ```
    """
    
    logger.info(integration_guide)
    return integration_guide
