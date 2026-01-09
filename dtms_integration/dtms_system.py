"""
DTMS System Integration
Main integration functions for the Defensive Trade Management System
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from dtms_core.dtms_engine import DTMSEngine
from dtms_integration.mt5_adapter import DTMSMT5Adapter
from dtms_integration.binance_adapter import DTMSBinanceAdapter
from dtms_integration.telegram_adapter import DTMSTelegramAdapter

logger = logging.getLogger(__name__)

# Global DTMS engine instance
_dtms_engine: Optional[DTMSEngine] = None
_dtms_start_time: Optional[float] = None
_dtms_action_history: List[Dict[str, Any]] = []

# Global HTTP client for connection pooling (Phase 3)
_http_client: Optional[Any] = None  # httpx.AsyncClient
_client_lock = asyncio.Lock()

def initialize_dtms(mt5_service, binance_service=None, telegram_service=None, order_flow_service=None) -> bool:
    """
    Initialize the DTMS system with required services
    
    Args:
        mt5_service: MT5 service instance
        binance_service: Binance service instance (optional)
        telegram_service: Telegram service instance (optional)
        order_flow_service: OrderFlowService instance (optional, for BTCUSD order flow)
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    global _dtms_engine, _dtms_start_time
    
    try:
        logger.info("🛡️ Initializing DTMS (Defensive Trade Management System)...")
        
        # Create DTMS engine
        _dtms_engine = DTMSEngine(
            mt5_service=mt5_service,
            binance_service=binance_service,
            telegram_service=telegram_service,
            order_flow_service=order_flow_service  # NEW: Pass OrderFlowService for BTCUSD
        )
        
        # Record start time
        _dtms_start_time = time.time()
        
        logger.info("✅ DTMS initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize DTMS: {e}")
        return False

def start_dtms_monitoring() -> bool:
    """
    Start DTMS monitoring
    
    Returns:
        bool: True if monitoring started successfully, False otherwise
    """
    global _dtms_engine
    
    try:
        if _dtms_engine is None:
            logger.error("❌ DTMS not initialized. Call initialize_dtms() first.")
            return False
        
        logger.info("🛡️ Starting DTMS monitoring...")
        _dtms_engine.start_monitoring()
        
        logger.info("✅ DTMS monitoring started successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to start DTMS monitoring: {e}")
        return False

def stop_dtms_monitoring() -> bool:
    """
    Stop DTMS monitoring
    
    Returns:
        bool: True if monitoring stopped successfully, False otherwise
    """
    global _dtms_engine
    
    try:
        if _dtms_engine is None:
            logger.warning("⚠️ DTMS not initialized")
            return False
        
        logger.info("🛡️ Stopping DTMS monitoring...")
        _dtms_engine.stop_monitoring()
        
        logger.info("✅ DTMS monitoring stopped successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to stop DTMS monitoring: {e}")
        return False

async def run_dtms_monitoring_cycle(app=None) -> None:
    """
    Run a single DTMS monitoring cycle
    
    Args:
        app: Application instance (for context, optional)
    """
    global _dtms_engine
    
    try:
        if _dtms_engine is None:
            logger.warning("⚠️ DTMS not initialized, skipping monitoring cycle")
            return
        
        if not _dtms_engine.monitoring_active:
            logger.info("⚠️ DTMS monitoring not active, skipping cycle")
            return
        
        # Log that we're about to run the cycle
        active_count = len(_dtms_engine.state_machine.active_trades) if hasattr(_dtms_engine, 'state_machine') else 0
        logger.info(f"🔄 DTMS monitoring cycle called - {active_count} active trades, monitoring_active: {_dtms_engine.monitoring_active}")
        
        # Run monitoring cycle
        await _dtms_engine.run_monitoring_cycle()
        
    except Exception as e:
        logger.error(f"❌ Error in DTMS monitoring cycle: {e}", exc_info=True)

def get_dtms_system_status() -> Dict[str, Any]:
    """
    Get DTMS system status
    
    Returns:
        Dict containing system status information
    """
    global _dtms_engine, _dtms_start_time
    
    try:
        if _dtms_engine is None:
            return {
                "error": "DTMS not initialized",
                "monitoring_active": False,
                "active_trades": 0
            }
        
        # Calculate uptime
        uptime_human = "Unknown"
        if _dtms_start_time:
            uptime_seconds = time.time() - _dtms_start_time
            uptime_human = str(timedelta(seconds=int(uptime_seconds)))
        
        # Get engine status
        engine_status = _dtms_engine.get_system_status()
        
        # Get trades by state
        trades_by_state = {}
        for trade_data in _dtms_engine.state_machine.active_trades.values():
            state = trade_data.state.value
            trades_by_state[state] = trades_by_state.get(state, 0) + 1
        
        return {
            "monitoring_active": _dtms_engine.monitoring_active,
            "uptime_human": uptime_human,
            "active_trades": len(_dtms_engine.state_machine.active_trades),
            "trades_by_state": trades_by_state,
            "performance": engine_status.get("performance", {}),
            "last_check_human": datetime.now().strftime("%H:%M:%S"),
            "error": None
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting DTMS system status: {e}")
        return {
            "error": str(e),
            "monitoring_active": False,
            "active_trades": 0
        }

def get_dtms_trade_status(ticket: int) -> Dict[str, Any]:
    """
    Get DTMS status for a specific trade
    
    Args:
        ticket: Trade ticket number
    
    Returns:
        Dict containing trade status information
    """
    global _dtms_engine
    
    try:
        if _dtms_engine is None:
            return {"error": "DTMS not initialized"}
        
        # Get trade data from state machine
        trade_data = _dtms_engine.state_machine.active_trades.get(ticket)
        if trade_data is None:
            return {"error": "Trade not found in DTMS"}
        
        # Calculate state entry time
        state_entry_time_human = datetime.fromtimestamp(trade_data.state_entry_time).strftime("%H:%M:%S")
        
        return {
            "ticket": ticket,
            "symbol": trade_data.symbol,
            "state": trade_data.state.value,
            "current_score": trade_data.current_score,
            "state_entry_time_human": state_entry_time_human,
            "warnings": trade_data.warnings,
            "actions_taken": trade_data.actions_taken,
            "performance": {
                "score_history": len(trade_data.score_history),
                "warning_count": len(trade_data.warnings)
            },
            "error": None
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting DTMS trade status: {e}")
        return {"error": str(e)}

def get_dtms_action_history() -> List[Dict[str, Any]]:
    """
    Get DTMS action history
    
    Returns:
        List of action history entries
    """
    global _dtms_action_history
    
    try:
        # Return last 50 actions
        return _dtms_action_history[-50:] if _dtms_action_history else []
        
    except Exception as e:
        logger.error(f"❌ Error getting DTMS action history: {e}")
        return []

def add_trade_to_dtms(ticket: int, symbol: str, direction: str, entry_price: float, 
                     volume: float, stop_loss: float, take_profit: float) -> bool:
    """
    Add a trade to DTMS monitoring
    
    Args:
        ticket: Trade ticket number
        symbol: Trading symbol
        direction: Trade direction (BUY/SELL)
        entry_price: Entry price
        volume: Trade volume
        stop_loss: Stop loss price
        take_profit: Take profit price
    
    Returns:
        bool: True if trade added successfully, False otherwise
    """
    global _dtms_engine
    
    try:
        if _dtms_engine is None:
            logger.warning("⚠️ DTMS not initialized, cannot add trade")
            return False
        
        # Add trade to state machine
        success = _dtms_engine.add_trade_monitoring(
            ticket=ticket,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            volume=volume,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        if success:
            logger.info(f"✅ Trade {ticket} ({symbol}) added to DTMS monitoring")
        else:
            logger.warning(f"⚠️ Failed to add trade {ticket} to DTMS monitoring")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error adding trade to DTMS: {e}")
        return False

async def get_http_client():
    """
    Get or create global HTTP client for DTMS API calls (connection pooling).
    
    Returns:
        httpx.AsyncClient: Global HTTP client instance
    """
    global _http_client, _client_lock
    
    if _http_client is None:
        async with _client_lock:
            if _http_client is None:  # Double-check
                try:
                    import httpx
                    _http_client = httpx.AsyncClient(
                        timeout=5.0,
                        limits=httpx.Limits(
                            max_connections=10,
                            max_keepalive_connections=5
                        )
                    )
                    logger.debug("Created global HTTP client for DTMS API (connection pooling)")
                except ImportError:
                    logger.warning("httpx not available - cannot use connection pooling")
                    return None
    
    return _http_client


async def close_http_client():
    """Close global HTTP client (call on shutdown)"""
    global _http_client
    if _http_client:
        try:
            await _http_client.aclose()
            _http_client = None
            logger.debug("Closed global HTTP client for DTMS API")
        except Exception as e:
            logger.warning(f"Error closing HTTP client: {e}")


async def register_trade_with_dtms_api(
    ticket: int,
    trade_data: Dict[str, Any],
    retry_count: int = 3,
    timeout: float = 5.0,
    api_url: str = "http://127.0.0.1:8001"
) -> bool:
    """
    Register trade with DTMS via API with retry logic and connection pooling.
    
    Args:
        ticket: Trade ticket number
        trade_data: Dict containing symbol, direction, entry_price, volume, stop_loss, take_profit
        retry_count: Number of retry attempts (default: 3)
        timeout: Request timeout in seconds (default: 5.0)
        api_url: Base URL for DTMS API server (default: http://127.0.0.1:8001)
    
    Returns:
        bool: True if registered successfully, False otherwise
    
    Raises:
        None - All errors are logged, function never raises
    """
    try:
        import httpx
        
        # Get or create HTTP client (connection pooling)
        client = await get_http_client()
        if client is None:
            # Fallback to creating temporary client if pooling not available
            client = httpx.AsyncClient(timeout=timeout)
            use_temporary_client = True
        else:
            use_temporary_client = False
        
        # Format trade data for API endpoint
        # Endpoint expects: ticket, symbol, direction, entry, volume, stop_loss, take_profit
        api_payload = {
            "ticket": ticket,
            "symbol": trade_data.get("symbol"),
            "direction": trade_data.get("direction"),
            "entry": trade_data.get("entry_price") or trade_data.get("price_executed"),
            "volume": trade_data.get("volume", 0.01),
            "stop_loss": trade_data.get("stop_loss") or trade_data.get("sl"),
            "take_profit": trade_data.get("take_profit") or trade_data.get("tp")
        }
        
        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(retry_count):
            try:
                response = await client.post(
                    f"{api_url}/dtms/trade/enable",
                    json=api_payload
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("success"):
                    logger.info(f"✅ Trade {ticket} registered with DTMS via API")
                    if use_temporary_client:
                        await client.aclose()
                    return True
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.warning(f"⚠️ DTMS API returned success=False for ticket {ticket}: {error_msg}")
                    if attempt < retry_count - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    last_error = error_msg
                    break
            except httpx.TimeoutException:
                logger.warning(f"⚠️ DTMS API timeout for ticket {ticket} (attempt {attempt + 1}/{retry_count})")
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                last_error = "Timeout"
            except httpx.RequestError as e:
                logger.error(f"❌ DTMS API connection error for ticket {ticket}: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                last_error = str(e)
            except Exception as e:
                logger.error(f"❌ Unexpected error registering trade {ticket} with DTMS API: {e}", exc_info=True)
                last_error = str(e)
                break
        
        # Close temporary client if used
        if use_temporary_client:
            try:
                await client.aclose()
            except Exception:
                pass
        
        logger.error(f"❌ Failed to register trade {ticket} with DTMS after {retry_count} attempts: {last_error}")
        return False
        
    except ImportError:
        logger.error("❌ httpx library not available - cannot register trade with DTMS API")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error in register_trade_with_dtms_api for ticket {ticket}: {e}", exc_info=True)
        return False


def get_dtms_engine() -> Optional[DTMSEngine]:
    """
    Get the DTMS engine instance
    
    Returns:
        DTMSEngine instance or None if not initialized
    """
    return _dtms_engine
