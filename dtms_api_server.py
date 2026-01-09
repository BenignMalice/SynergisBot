"""
DTMS API Server
HTTP API server for accessing DTMS system from external processes
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import DTMS functions
from dtms_integration import (
    get_dtms_system_status,
    get_dtms_trade_status,
    get_dtms_action_history,
    get_dtms_engine,
    start_dtms_monitoring,
    run_dtms_monitoring_cycle
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="DTMS API Server",
    description="API server for accessing DTMS (Defensive Trade Management System)",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class DTMSStatusResponse(BaseModel):
    success: bool
    summary: str
    dtms_status: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class DTMSTradeInfoResponse(BaseModel):
    success: bool
    summary: str
    trade_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class DTMSActionHistoryResponse(BaseModel):
    success: bool
    summary: str
    action_history: Optional[list] = None
    total_actions: int = 0
    error: Optional[str] = None

# Background task for DTMS monitoring cycle
dtms_monitor_task = None

# DTMS initialization status flag
_dtms_initialized = False
_dtms_initialization_lock = asyncio.Lock()

# Registration lock for concurrent registrations (idempotency)
_registration_lock = asyncio.Lock()

async def dtms_monitor_background_task():
    """Background task that runs DTMS monitoring cycle every 30 seconds"""
    global _dtms_initialized
    
    logger.info("🛡️ DTMS background monitoring task started")
    
    # Wait up to 60 seconds for DTMS initialization before starting monitoring
    max_wait = 60
    wait_interval = 2
    waited = 0
    
    while not _dtms_initialized and waited < max_wait:
        await asyncio.sleep(wait_interval)
        waited += wait_interval
        if waited % 10 == 0:  # Log every 10 seconds
            logger.info(f"Waiting for DTMS initialization... ({waited}/{max_wait}s)")
    
    if not _dtms_initialized:
        logger.error("❌ DTMS not initialized after 60 seconds - monitoring task exiting")
        return
    
    # Periodic cleanup counter (clean up every 10 cycles = 5 minutes)
    cleanup_counter = 0
    
    try:
        while True:
            try:
                # Check initialization status before each cycle
                if not _dtms_initialized:
                    logger.warning("DTMS not initialized - skipping monitoring cycle")
                    await asyncio.sleep(30)
                    continue
                    
                await run_dtms_monitoring_cycle()
                
                # Periodic cleanup of closed trades (every 10 cycles = 5 minutes)
                cleanup_counter += 1
                if cleanup_counter >= 10:
                    cleanup_counter = 0
                    try:
                        from dtms_core.persistence import cleanup_closed_trades
                        from dtms_integration import get_dtms_engine
                        from infra.mt5_service import MT5Service
                        
                        engine = get_dtms_engine()
                        if engine:
                            active_tickets = list(engine.state_machine.active_trades.keys())
                            mt5_service = MT5Service()
                            # Try to connect if not connected
                            if not hasattr(mt5_service, '_connected') or not mt5_service._connected:
                                mt5_service.connect()
                            
                            if hasattr(mt5_service, '_connected') and mt5_service._connected:
                                cleanup_closed_trades(mt5_service, active_tickets)
                    except Exception as cleanup_error:
                        logger.warning(f"Error during periodic cleanup: {cleanup_error}")
                        # Don't break monitoring on cleanup errors
                        
            except Exception as e:
                logger.error(f"❌ Error in DTMS monitoring cycle: {e}", exc_info=True)
                # Continue monitoring despite error
            
            try:
                # Wait 30 seconds before next cycle
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
    except Exception as fatal_error:
        logger.critical(f"FATAL ERROR in DTMS background monitoring task: {fatal_error}", exc_info=True)
    finally:
        logger.info("DTMS background monitoring task stopped")

@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup"""
    global dtms_monitor_task
    try:
        # Start DTMS monitoring background task
        dtms_monitor_task = asyncio.create_task(dtms_monitor_background_task())
        logger.info("✅ DTMS background monitoring task started")
    except Exception as e:
        logger.error(f"❌ Failed to start DTMS background task: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop background tasks on shutdown"""
    global dtms_monitor_task
    if dtms_monitor_task:
        dtms_monitor_task.cancel()
        try:
            await dtms_monitor_task
        except asyncio.CancelledError:
            pass
        logger.info("🛑 DTMS background monitoring task stopped")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "DTMS API Server",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global _dtms_initialized
    
    try:
        # Check DTMS initialization status
        if not _dtms_initialized:
            from fastapi import status
            return {
                "status": "unhealthy",
                "dtms_initialized": False,
                "dtms_available": False,
                "error": "DTMS not initialized",
                "timestamp": datetime.now().isoformat()
            }, status.HTTP_503_SERVICE_UNAVAILABLE
        
        # Try to get DTMS status to verify system is working
        status_data = get_dtms_system_status()
        if status_data and not status_data.get('error'):
            return {
                "status": "healthy",
                "dtms_initialized": True,
                "dtms_available": True,
                "timestamp": datetime.now().isoformat()
            }
        else:
            from fastapi import status
            return {
                "status": "degraded",
                "dtms_initialized": _dtms_initialized,
                "dtms_available": False,
                "error": status_data.get('error', 'DTMS not available') if status_data else 'DTMS not available',
                "timestamp": datetime.now().isoformat()
            }, status.HTTP_503_SERVICE_UNAVAILABLE
    except Exception as e:
        from fastapi import status
        return {
            "status": "unhealthy",
            "dtms_initialized": _dtms_initialized,
            "dtms_available": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, status.HTTP_500_INTERNAL_SERVER_ERROR

@app.get("/dtms/health")
async def dtms_health_check():
    """DTMS-specific health check endpoint"""
    global _dtms_initialized
    from fastapi import status
    from dtms_integration import get_dtms_engine
    
    try:
        engine = get_dtms_engine()
        monitoring_active = engine.monitoring_active if engine else False
        active_trades = len(engine.state_machine.active_trades) if engine else 0
        
        if _dtms_initialized and engine:
            return {
                "dtms_initialized": True,
                "monitoring_active": monitoring_active,
                "active_trades": active_trades,
                "ready": True,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "dtms_initialized": _dtms_initialized,
                "monitoring_active": False,
                "active_trades": 0,
                "ready": False,
                "error": "DTMS not initialized" if not _dtms_initialized else "DTMS engine not available",
                "timestamp": datetime.now().isoformat()
            }, status.HTTP_503_SERVICE_UNAVAILABLE
    except Exception as e:
        return {
            "dtms_initialized": _dtms_initialized,
            "monitoring_active": False,
            "active_trades": 0,
            "ready": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, status.HTTP_500_INTERNAL_SERVER_ERROR

@app.get("/dtms/status", response_model=DTMSStatusResponse)
async def get_dtms_status():
    """Get DTMS system status"""
    global _dtms_initialized
    from fastapi import status as http_status
    
    # Check initialization status
    if not _dtms_initialized:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DTMS not initialized"
        )
    
    try:
        status = get_dtms_system_status()
        
        if status and not status.get('error'):
            # Derive monitoring flag more robustly using the live engine if needed
            monitoring_flag = status.get('monitoring_active', False)
            if not monitoring_flag:
                try:
                    engine = get_dtms_engine()
                    if engine:
                        monitoring_flag = bool(getattr(engine, 'monitoring_active', False))
                except Exception:
                    pass

            return DTMSStatusResponse(
                success=True,
                summary=f"DTMS system is active with {status.get('active_trades', 0)} trades monitored",
                dtms_status={
                    "system_active": monitoring_flag,
                    "uptime": status.get('uptime_human', 'Unknown'),
                    "active_trades": status.get('active_trades', 0),
                    "trades_by_state": status.get('trades_by_state', {}),
                    "performance": status.get('performance', {}),
                    "last_check": status.get('last_check_human', 'Unknown')
                }
            )
        else:
            error_msg = status.get('error', 'DTMS system not available') if status else 'DTMS system not available'
            return DTMSStatusResponse(
                success=False,
                summary=f"DTMS system is not available: {error_msg}",
                error=error_msg,
                dtms_status={
                    "system_active": False,
                    "error": error_msg
                }
            )
            
    except Exception as e:
        error_msg = f"Failed to get DTMS status: {str(e)}"
        return DTMSStatusResponse(
            success=False,
            summary=error_msg,
            error=error_msg
        )

@app.get("/dtms/trade/{ticket}", response_model=DTMSTradeInfoResponse)
async def get_dtms_trade_info(ticket: int):
    """Get DTMS information for a specific trade"""
    global _dtms_initialized
    from fastapi import status as http_status
    
    # Check initialization status
    if not _dtms_initialized:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DTMS not initialized"
        )
    
    try:
        logger.debug(f"Getting DTMS trade info for ticket {ticket}")
        trade_info = get_dtms_trade_status(ticket)
        
        # Log if trade not found for debugging
        if not trade_info or trade_info.get('error'):
            logger.warning(f"Trade {ticket} not found in DTMS: {trade_info.get('error', 'Unknown error') if trade_info else 'None returned'}")
            # Check if engine has any trades
            try:
                engine = get_dtms_engine()
                if engine:
                    active_count = len(getattr(engine, 'state_machine', {}).active_trades) if hasattr(engine, 'state_machine') else 0
                    logger.debug(f"DTMS engine has {active_count} active trades")
            except Exception as e:
                logger.debug(f"Could not check engine state: {e}")
        # Enrich with MT5 position details and protection status
        mt5_details = {}
        protection_active = False
        try:
            engine = get_dtms_engine()
            if engine:
                # Active if monitoring and ticket tracked
                protection_active = bool(getattr(engine, 'monitoring_active', False)) and (
                    str(ticket) in getattr(engine, 'state_machine').active_trades or
                    ticket in getattr(engine, 'state_machine').active_trades
                )
        except Exception:
            pass
        try:
            from infra.mt5_service import MT5Service
            mt5_service = MT5Service()
            if mt5_service.connect():
                pos_list = mt5_service.list_positions()
                for p in pos_list or []:
                    if int(p.get('ticket')) == int(ticket):
                        # Map MT5 numeric type to human-readable
                        order_type_val = p.get('type')
                        if isinstance(order_type_val, (int, float)):
                            order_type_str = 'BUY' if int(order_type_val) == 0 else 'SELL'
                        else:
                            order_type_str = str(order_type_val) if order_type_val is not None else None

                        mt5_details = {
                            "symbol": p.get('symbol'),
                            "type": order_type_str,
                            "volume": p.get('volume'),
                            "open_price": p.get('price_open'),
                            "current_price": p.get('price_current'),
                            "profit": p.get('profit'),
                            "sl": p.get('sl'),
                            "tp": p.get('tp')
                        }
                        break
        except Exception:
            pass
        
        if trade_info and not trade_info.get('error'):
            return DTMSTradeInfoResponse(
                success=True,
                summary=f"Trade {ticket} is in {trade_info.get('state', 'Unknown')} state with score {trade_info.get('current_score', 0)}",
                trade_info={
                    "ticket": trade_info.get('ticket'),
                    "symbol": mt5_details.get('symbol') or trade_info.get('symbol'),
                    "state": trade_info.get('state'),
                    "current_score": trade_info.get('current_score'),
                    "state_entry_time": trade_info.get('state_entry_time_human'),
                    "warnings": trade_info.get('warnings', {}),
                    "actions_taken": trade_info.get('actions_taken', []),
                    "performance": trade_info.get('performance', {}),
                    "type": mt5_details.get('type'),
                    "volume": mt5_details.get('volume'),
                    "open_price": mt5_details.get('open_price'),
                    "current_price": mt5_details.get('current_price'),
                    "profit": mt5_details.get('profit'),
                    "sl": mt5_details.get('sl'),
                    "tp": mt5_details.get('tp'),
                    "protection_active": protection_active
                }
            )
        else:
            error_msg = trade_info.get('error', 'Trade not found in DTMS') if trade_info else 'Trade not found in DTMS'
            return DTMSTradeInfoResponse(
                success=False,
                summary=f"Could not get DTMS info for trade {ticket}: {error_msg}",
                error=error_msg,
                trade_info=None
            )
            
    except Exception as e:
        error_msg = f"Failed to get DTMS trade info: {str(e)}"
        return DTMSTradeInfoResponse(
            success=False,
            summary=error_msg,
            error=error_msg
        )

@app.get("/dtms/actions", response_model=DTMSActionHistoryResponse)
async def get_dtms_action_history_endpoint():
    """Get DTMS action history"""
    try:
        history = get_dtms_action_history()
        
        if history and len(history) > 0:
            # Return last 10 actions
            recent_actions = history[-10:] if len(history) > 10 else history
            
            return DTMSActionHistoryResponse(
                success=True,
                summary=f"Retrieved {len(recent_actions)} recent DTMS actions from {len(history)} total actions",
                action_history=[
                    {
                        "action_type": action.get('action_type'),
                        "ticket": action.get('ticket'),
                        "symbol": action.get('symbol'),
                        "success": action.get('success'),
                        "timestamp": action.get('time_human'),
                        "details": action.get('details', {})
                    }
                    for action in recent_actions
                ],
                total_actions=len(history)
            )
        else:
            return DTMSActionHistoryResponse(
                success=True,
                summary="No DTMS actions found in history",
                action_history=[],
                total_actions=0
            )
            
    except Exception as e:
        error_msg = f"Failed to get DTMS action history: {str(e)}"
        return DTMSActionHistoryResponse(
            success=False,
            summary=error_msg,
            error=error_msg
        )

@app.post("/dtms/initialize")
async def initialize_dtms_system():
    """Initialize the DTMS system"""
    try:
        from infra.mt5_service import MT5Service
        from infra.binance_service import BinanceService
        from dtms_integration import initialize_dtms, start_dtms_monitoring
        
        logger.info("Initializing DTMS system via API...")
        
        # Initialize MT5 service
        mt5_service = MT5Service()
        if not mt5_service.connect():
            return {
                "success": False,
                "summary": "Failed to connect to MT5",
                "error": "MT5 connection failed"
            }
        
        # Initialize Binance service (optional)
        try:
            binance_service = BinanceService()
        except Exception as e:
            logger.warning(f"Binance service not available: {e}")
            binance_service = None
        
        # Initialize DTMS system
        success = initialize_dtms(
            mt5_service=mt5_service,
            binance_service=binance_service,
            telegram_service=None
        )
        
        if success:
            # Start DTMS monitoring
            monitoring_started = start_dtms_monitoring()
            
            return {
                "success": True,
                "summary": "DTMS system initialized and monitoring started successfully",
                "dtms_status": {
                    "system_active": monitoring_started,
                    "mt5_connected": True,
                    "binance_available": binance_service is not None
                }
            }
        else:
            return {
                "success": False,
                "summary": "Failed to initialize DTMS system",
                "error": "DTMS initialization failed"
            }
            
    except Exception as e:
        return {
            "success": False,
            "summary": f"Error initializing DTMS system: {str(e)}",
            "error": str(e)
        }

@app.post("/dtms/trade/enable")
async def enable_dtms_for_trade(trade_data: dict):
    """Enable DTMS protection for a specific trade (idempotent)"""
    global _dtms_initialized, _registration_lock
    from fastapi import status as http_status
    
    # Check initialization status
    if not _dtms_initialized:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DTMS not initialized"
        )
    
    # Use lock to prevent concurrent registrations
    async with _registration_lock:
        try:
            from dtms_integration import add_trade_to_dtms, get_dtms_engine
            
            # Extract trade data
            ticket = trade_data.get("ticket")
            symbol = trade_data.get("symbol")
            direction = trade_data.get("direction")
            entry_price = trade_data.get("entry")
            volume = trade_data.get("volume", 0)
            stop_loss = trade_data.get("stop_loss")
            take_profit = trade_data.get("take_profit")
            
            if not all([ticket, symbol, direction, entry_price]):
                return {
                    "success": False,
                    "summary": "Missing required trade data",
                    "error": "ticket, symbol, direction, and entry are required"
                }
            
            # Check if trade already registered (idempotency check)
            engine = get_dtms_engine()
            if engine and ticket in engine.state_machine.active_trades:
                # Trade already registered - return existing trade info (idempotent)
                existing_trade = engine.state_machine.active_trades[ticket]
                logger.info(f"Trade {ticket} already registered with DTMS - returning existing trade info")
                return {
                    "success": True,
                    "summary": f"Trade {ticket} already registered with DTMS",
                    "trade_info": {
                        "ticket": ticket,
                        "symbol": existing_trade.symbol if hasattr(existing_trade, 'symbol') else symbol,
                        "direction": existing_trade.direction if hasattr(existing_trade, 'direction') else direction,
                        "entry_price": existing_trade.entry_price if hasattr(existing_trade, 'entry_price') else entry_price,
                        "volume": existing_trade.volume if hasattr(existing_trade, 'volume') else volume,
                        "stop_loss": existing_trade.stop_loss if hasattr(existing_trade, 'stop_loss') else stop_loss,
                        "take_profit": existing_trade.take_profit if hasattr(existing_trade, 'take_profit') else take_profit,
                        "state": existing_trade.state.value if hasattr(existing_trade, 'state') and hasattr(existing_trade.state, 'value') else str(existing_trade.state) if hasattr(existing_trade, 'state') else None
                    },
                    "already_registered": True
                }
            
            # Trade not registered - add to DTMS monitoring
            success = add_trade_to_dtms(
                ticket=ticket,
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                volume=volume,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            if success:
                # Save to persistence database
                try:
                    from dtms_core.persistence import save_trade
                    save_trade(
                        ticket=ticket,
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry_price,
                        volume=volume,
                        stop_loss=stop_loss,
                        take_profit=take_profit
                    )
                except Exception as persist_error:
                    logger.warning(f"Failed to save trade {ticket} to persistence database: {persist_error}")
                    # Don't fail registration if persistence fails
                
                return {
                    "success": True,
                    "summary": f"DTMS protection enabled for ticket {ticket}",
                    "trade_info": {
                        "ticket": ticket,
                        "symbol": symbol,
                        "direction": direction,
                        "entry_price": entry_price,
                        "volume": volume,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit
                    },
                    "already_registered": False
                }
            else:
                return {
                    "success": False,
                    "summary": f"Failed to enable DTMS protection for ticket {ticket}",
                    "error": "DTMS add_trade_to_dtms returned False"
                }
                
        except Exception as e:
            logger.error(f"Error enabling DTMS protection for ticket {trade_data.get('ticket')}: {e}", exc_info=True)
            return {
                "success": False,
                "summary": f"Error enabling DTMS protection: {str(e)}",
                "error": str(e)
            }

@app.get("/dtms/engine")
async def get_dtms_engine_info():
    """Get DTMS engine information"""
    try:
        engine = get_dtms_engine()
        if engine:
            return {
                "success": True,
                "summary": "DTMS engine is available",
                "engine_info": {
                    "monitoring_active": engine.monitoring_active,
                    "active_trades_count": len(engine.state_machine.active_trades),
                    "last_fast_check": engine.last_fast_check,
                    "last_deep_check": engine.last_deep_check
                }
            }
        else:
            return {
                "success": False,
                "summary": "DTMS engine is not available",
                "error": "DTMS engine not initialized"
            }
    except Exception as e:
        return {
            "success": False,
            "summary": f"Failed to get DTMS engine info: {str(e)}",
            "error": str(e)
        }

def start_dtms_api_server(host: str = "127.0.0.1", port: int = 8001):
    """Start the DTMS API server"""
    logger.info(f"🚀 Starting DTMS API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")

async def auto_initialize_dtms():
    """Auto-initialize DTMS system on startup"""
    global _dtms_initialized
    
    async with _dtms_initialization_lock:
        if _dtms_initialized:
            logger.info("DTMS already initialized")
            return True
            
        try:
            logger.info("Auto-initializing DTMS system on startup...")
            
            # Initialize persistence database first
            try:
                from dtms_core.persistence import _init_database
                _init_database()
            except Exception as db_error:
                logger.warning(f"Failed to initialize persistence database: {db_error}")
                # Continue even if database init fails
            
            # Initialize MT5 service with retry logic
            from infra.mt5_service import MT5Service
            from infra.binance_service import BinanceService
            from dtms_integration import initialize_dtms
            import time
            
            mt5_service = MT5Service()
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                if mt5_service.connect():
                    break
                if attempt < max_retries - 1:
                    logger.warning(f"MT5 connection failed (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("❌ Failed to connect to MT5 after all retries during auto-initialization")
                    _dtms_initialized = False
                    return False
            
            # Initialize Binance service (optional)
            try:
                binance_service = BinanceService()
            except Exception as e:
                logger.warning(f"Binance service not available during auto-init: {e}")
                binance_service = None
            
            # Initialize DTMS system
            success = initialize_dtms(
                mt5_service=mt5_service,
                binance_service=binance_service,
                telegram_service=None
            )
            
            if success:
                try:
                    start_dtms_monitoring()
                    
                    # Recover trades from persistence database
                    try:
                        from dtms_core.persistence import recover_trades_from_database, _init_database
                        from dtms_integration import add_trade_to_dtms
                        
                        # Initialize database if needed
                        _init_database()
                        
                        recovered_trades = recover_trades_from_database(mt5_service)
                        
                        if recovered_trades:
                            logger.info(f"Recovering {len(recovered_trades)} trades from persistence database...")
                            for trade in recovered_trades:
                                try:
                                    add_trade_to_dtms(
                                        ticket=trade["ticket"],
                                        symbol=trade["symbol"],
                                        direction=trade["direction"],
                                        entry_price=trade["entry_price"],
                                        volume=trade["volume"],
                                        stop_loss=trade["stop_loss"],
                                        take_profit=trade["take_profit"]
                                    )
                                    logger.debug(f"✅ Recovered trade {trade['ticket']} from persistence database")
                                except Exception as recover_error:
                                    logger.warning(f"Failed to recover trade {trade['ticket']}: {recover_error}")
                        else:
                            logger.info("No trades to recover from persistence database")
                    except Exception as recover_error:
                        logger.warning(f"Failed to recover trades from persistence database: {recover_error}")
                        # Continue even if recovery fails
                    
                    # Set flag only after successful initialization AND monitoring started
                    _dtms_initialized = True
                    logger.info("✅ DTMS system auto-initialized and monitoring started on startup")
                    return True
                except Exception as e:
                    logger.error(f"❌ DTMS monitoring failed to start: {e}")
                    _dtms_initialized = False
                    return False
            else:
                logger.error("❌ Failed to auto-initialize DTMS system")
                _dtms_initialized = False
                return False
                
        except Exception as e:
            logger.error(f"❌ Error during DTMS auto-initialization: {e}", exc_info=True)
            _dtms_initialized = False
            return False

if __name__ == "__main__":
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Auto-initialize DTMS on startup - BLOCK until initialized
    import asyncio
    init_success = asyncio.run(auto_initialize_dtms())
    
    if not init_success:
        logger.critical("❌ DTMS initialization failed - server will not start")
        sys.exit(1)  # Exit if initialization fails
    
    # Only start server if initialization succeeded
    logger.info("✅ DTMS initialized successfully, starting API server...")
    start_dtms_api_server()
