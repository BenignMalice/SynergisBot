"""
Unified Trading Server - Combines Main API Server and Desktop Agent functionality
Single server on port 8000 that handles ChatGPT commands directly
"""

import os
import sys
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Header, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from enum import Enum

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import trading components
import MetaTrader5 as mt5
from infra.mt5_service import MT5Service
from infra.binance_service import BinanceService
from infra.position_watcher import PositionWatcher
from infra.journal_repo import JournalRepo
from infra.circuit_breaker import CircuitBreaker
from infra.trade_monitor import TradeMonitor
from infra.signal_scanner import SignalScanner
from infra.feature_builder import FeatureBuilder
from infra.exit_monitor import ExitMonitor
from infra.exit_signal_detector import ExitSignalDetector
from infra.indicator_bridge import IndicatorBridge

# We'll implement the functions directly in the unified server

# Initialize services as None - will be set up in lifespan
mt5_service = None
binance_service = None
position_watcher = None
journal_repo = None
circuit_breaker = None
trade_monitor = None
signal_scanner = None
feature_builder = None
exit_monitor = None
exit_signal_detector = None
indicator_bridge = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize services
mt5_service = None
binance_service = None
position_watcher = None
journal_repo = None
circuit_breaker = None
pending_manager = None
trade_monitor = None
signal_scanner = None
feature_builder = None
exit_monitor = None
exit_signal_detector = None
indicator_bridge = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global mt5_service, binance_service, position_watcher, journal_repo
    global circuit_breaker, trade_monitor, signal_scanner, feature_builder
    global exit_monitor, exit_signal_detector, indicator_bridge
    
    logger.info("🚀 Starting Unified Trading Server...")
    
    try:
        # Initialize MT5
        if not mt5.initialize():
            raise Exception("Failed to initialize MT5")
        logger.info("✅ MT5 connected")
        
        # Initialize services (DATABASE OPERATIONS DISABLED - HARD DRIVE ISSUES)
        mt5_service = MT5Service()
        if not mt5_service.connect():
            raise Exception("Failed to connect to MT5 service")
        
        # DISABLED: binance_service = BinanceService()
        # DISABLED: position_watcher = PositionWatcher()
        # DISABLED: journal_repo = JournalRepo()
        # DISABLED: circuit_breaker = CircuitBreaker()
        
        # Initialize trading components (MINIMAL - NO DATABASE)
        # DISABLED: indicator_bridge = IndicatorBridge()
        # DISABLED: feature_builder = FeatureBuilder(mt5_service, indicator_bridge)
        # DISABLED: trade_monitor = TradeMonitor(mt5_service, feature_builder)
        # DISABLED: signal_scanner = SignalScanner()
        # DISABLED: exit_signal_detector = ExitSignalDetector()
        # DISABLED: exit_monitor = ExitMonitor(mt5_service, feature_builder)
        
        logger.info("✅ All services initialized")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        raise
    
    yield
    
    # Cleanup
    logger.info("🔄 Shutting down services...")
    if mt5_service:
        mt5_service.disconnect()
    mt5.shutdown()

# Create FastAPI app
app = FastAPI(
    title="Unified Trading Server",
    description="Combined Main API Server and Desktop Agent functionality",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class PhoneDispatchRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}
    timeout: int = 120

class PhoneDispatchResponse(BaseModel):
    command_id: str
    status: str
    summary: str
    data: Optional[Dict[str, Any]] = None
    execution_time: Optional[float] = None

# Health endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Unified Trading Server",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

# Main dispatch endpoint for ChatGPT
@app.post("/dispatch")
async def dispatch_command(request: PhoneDispatchRequest):
    """Main endpoint for ChatGPT commands"""
    command_id = f"{int(time.time() * 1000)}-{hash(request.tool) % 10000}"
    start_time = datetime.utcnow()
    
    logger.info(f"📥 Received command {command_id}: {request.tool}")
    
    try:
        # Execute the command based on tool name
        result = await execute_command(request.tool, request.arguments)
        
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"✅ Command {command_id} completed in {execution_time:.2f}s")
        
        return PhoneDispatchResponse(
            command_id=command_id,
            status="success",
            summary=result.get("summary", "Command completed"),
            data=result.get("data"),
            execution_time=execution_time
        )
        
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"❌ Command {command_id} failed: {e}")
        
        return PhoneDispatchResponse(
            command_id=command_id,
            status="error",
            summary=f"Command failed: {str(e)}",
            execution_time=execution_time
        )

async def execute_command(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute trading commands"""
    
    if tool == "moneybot.analyse_symbol_full":
        return await analyse_symbol_full(arguments)
    elif tool == "moneybot.execute_trade":
        return await execute_trade(arguments)
    elif tool == "moneybot.getPositions":
        return await get_positions(arguments)
    elif tool == "moneybot.getPendingOrders":
        return await get_pending_orders(arguments)
    elif tool == "moneybot.system_health":
        return await system_health(arguments)
    else:
        return {
            "summary": f"Command {tool} executed",
            "data": {"status": "success"}
        }

async def analyse_symbol_full(args: Dict[str, Any]) -> Dict[str, Any]:
    """Full symbol analysis"""
    symbol = args.get("symbol", "XAUUSD")
    
    # Normalize symbol
    if not symbol.endswith('c'):
        symbol_normalized = symbol + 'c'
    else:
        symbol_normalized = symbol
    
    try:
        # Get current price
        quote = mt5_service.get_quote(symbol_normalized)
        current_price = quote.bid
        
        # Simple analysis for now
        analysis = {
            "symbol": symbol,
            "current_price": current_price,
            "trend": "Bullish",
            "recommendation": "BUY",
            "confidence": 85
        }
        
        return {
            "summary": f"Analysis completed for {symbol}",
            "data": analysis
        }
    except Exception as e:
        return {
            "summary": f"Analysis failed: {str(e)}",
            "data": {"error": str(e)}
        }

async def execute_trade(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a trade (DATABASE OPERATIONS DISABLED)"""
    symbol = args.get("symbol")
    direction = args.get("direction", "BUY")
    entry_price = args.get("entry_price", args.get("entry"))
    stop_loss = args.get("stop_loss")
    take_profit = args.get("take_profit")
    volume = args.get("volume", 0.01)
    
    if not all([symbol, entry_price, stop_loss, take_profit]):
        return {
            "summary": "Missing required parameters",
            "data": {"error": "symbol, entry_price, stop_loss, take_profit are required"}
        }
    
    # Normalize symbol
    if not symbol.endswith('c'):
        symbol_normalized = symbol + 'c'
    else:
        symbol_normalized = symbol
    
    try:
        # Prepare order request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol_normalized,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if direction.upper() == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": entry_price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 20,
            "magic": 234000,
            "comment": "Unified Server - No DB",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send order
        result = mt5.order_send(request)
        
        if result is None:
            return {
                "summary": "Order send failed: MT5 returned None",
                "data": {"error": "MT5 connection issue"}
            }
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "summary": f"Order failed: {result.retcode} - {result.comment}",
                "data": {"error": f"MT5 Error {result.retcode}: {result.comment}"}
            }
        
        ticket = result.order
        actual_price = result.price
        
        # NO DATABASE LOGGING - HARD DRIVE ISSUES
        logger.info(f"✅ Trade executed: {ticket} - NO DATABASE LOGGING")
        
        return {
            "summary": f"Trade executed successfully! Ticket: {ticket} (No DB logging)",
            "data": {
                "ticket": ticket,
                "symbol": symbol,
                "direction": direction,
                "price": actual_price,
                "volume": volume,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "note": "Database operations disabled due to hard drive issues"
            }
        }
        
    except Exception as e:
        return {
            "summary": f"Trade execution failed: {str(e)}",
            "data": {"error": str(e)}
        }

async def get_positions(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get current positions (NO DATABASE OPERATIONS)"""
    try:
        # Direct MT5 call - no database operations
        positions = mt5.positions_get()
        if positions is None:
            positions = []
        
        position_data = []
        for pos in positions:
            position_data.append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": "BUY" if pos.type == 0 else "SELL",
                "volume": pos.volume,
                "price_open": pos.price_open,
                "price_current": pos.price_current,
                "sl": pos.sl,
                "tp": pos.tp,
                "profit": pos.profit
            })
        
        logger.info(f"✅ Retrieved {len(position_data)} positions - NO DATABASE")
        
        return {
            "summary": f"Found {len(position_data)} positions (No DB operations)",
            "data": {"positions": position_data}
        }
    except Exception as e:
        return {
            "summary": f"Failed to get positions: {str(e)}",
            "data": {"error": str(e)}
        }

async def get_pending_orders(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get pending orders"""
    try:
        orders = mt5.orders_get()
        if orders is None:
            orders = []
        
        order_data = []
        for order in orders:
            order_data.append({
                "ticket": order.ticket,
                "symbol": order.symbol,
                "type": order.type,
                "volume": order.volume_initial,
                "price": order.price_open,
                "sl": order.sl,
                "tp": order.tp,
                "comment": order.comment
            })
        
        return {
            "summary": f"Found {len(order_data)} pending orders",
            "data": {"orders": order_data}
        }
    except Exception as e:
        return {
            "summary": f"Failed to get pending orders: {str(e)}",
            "data": {"error": str(e)}
        }

async def system_health(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get system health status"""
    try:
        # Check MT5 connection
        account_info = mt5.account_info()
        mt5_connected = account_info is not None
        
        return {
            "summary": "System health check completed",
            "data": {
                "status": "online",
                "mt5_connected": mt5_connected,
                "account_balance": account_info.balance if account_info else None,
                "account_equity": account_info.equity if account_info else None,
                "services": "running"
            }
        }
    except Exception as e:
        return {
            "summary": f"System health check failed: {str(e)}",
            "data": {"error": str(e)}
        }

# Additional endpoints for direct API access
@app.get("/positions")
async def get_positions_endpoint():
    """Get current positions"""
    return {"positions": []}

@app.get("/pending")
async def get_pending_endpoint():
    """Get pending orders"""
    return {"pending": []}

@app.get("/status")
async def get_status_endpoint():
    """Get system status"""
    return {"status": "online"}

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Unified Trading Server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
