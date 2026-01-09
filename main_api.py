"""
FastAPI server implementing the openai.yaml specification.
Provides comprehensive API for ChatGPT and external services to interact with MT5 trading bot.
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Header, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from enum import Enum
import logging
import MetaTrader5 as mt5
import asyncio

# Add parent directory to path to import bot modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.mt5_service import MT5Service
from infra.journal_repo import JournalRepo
from infra.indicator_bridge import IndicatorBridge
from config import settings
from app.services import oco_tracker
from infra.custom_alerts import CustomAlertManager
from chatgpt_auto_execution_integration import get_chatgpt_auto_execution
from app.auto_execution_api import router as auto_execution_router
from intelligent_exits_unified_pipeline_integration import (
    initialize_intelligent_exits_unified_pipeline,
    stop_intelligent_exits_unified_pipeline,
)
from dtms_unified_pipeline_integration import (
    initialize_dtms_unified_pipeline,
    stop_dtms_unified_pipeline,
)
from main_api_unified_pipeline_integration import initialize_main_api_unified_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MoneyBot v1.1 - Advanced AI Trading System API",
    description="Revolutionary AI-powered trading system for intelligent trade management",
    version="1.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auto execution router
app.include_router(auto_execution_router)

# ============================================================================
# ENUMS
# ============================================================================

class Direction(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    MARKET = "market"
    BUY_LIMIT = "buy_limit"
    SELL_LIMIT = "sell_limit"
    BUY_STOP = "buy_stop"
    SELL_STOP = "sell_stop"

class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class TradeSignal(BaseModel):
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSD, XAUUSD)")
    timeframe: Timeframe = Field(..., description="Chart timeframe")
    direction: Direction = Field(..., description="Trade direction")
    order_type: Optional[OrderType] = Field(OrderType.MARKET, description="Order type")
    entry_price: float = Field(..., description="Entry price level")
    stop_loss: float = Field(..., description="Stop loss price level")
    take_profit: float = Field(..., description="Take profit price level")
    confidence: Optional[int] = Field(80, ge=0, le=100, description="Confidence level")
    reasoning: Optional[str] = Field(None, description="Trading rationale")
    screenshot_url: Optional[str] = Field(None, description="Chart screenshot URL")

class SignalResponse(BaseModel):
    ok: bool
    message_id: Optional[int] = None
    status: str
    expires_at: Optional[datetime] = None

class ExecutionResponse(BaseModel):
    ok: bool
    order_id: Optional[int] = None
    deal_id: Optional[int] = None
    retcode: Optional[int] = None
    comment: Optional[str] = None

class ComponentHealth(BaseModel):
    mt5_connection: HealthStatus
    telegram_api: HealthStatus
    database: HealthStatus
    system_resources: HealthStatus

class HealthCheckResponse(BaseModel):
    ok: bool
    timestamp: datetime
    components: ComponentHealth

class DetailedHealthStatus(HealthCheckResponse):
    uptime: Optional[str] = None
    active_positions: Optional[int] = None
    pending_signals: Optional[int] = None

class MarketAnalysis(BaseModel):
    symbol: str
    volatility: float
    regime: str
    trend_strength: float
    liquidity_score: float
    is_tradeable: bool
    confidence: float

class AccountInfo(BaseModel):
    login: Optional[int] = None
    balance: Optional[float] = None
    equity: Optional[float] = None
    profit: Optional[float] = None
    margin: Optional[float] = None
    free_margin: Optional[float] = None
    currency: Optional[str] = "USD"

# ============================================================================
# GLOBAL SERVICES
# ============================================================================

mt5_service: Optional[MT5Service] = None
journal_repo: Optional[JournalRepo] = None
indicator_bridge: Optional[IndicatorBridge] = None
startup_time = datetime.now()
oco_monitor_task: Optional[asyncio.Task] = None
oco_monitor_running = False
custom_alerts_manager: Optional[CustomAlertManager] = None
auto_execution_system = None

# Discord Alert Dispatcher
from infra.discord_alert_dispatcher import DiscordAlertDispatcher
alert_dispatcher: Optional[DiscordAlertDispatcher] = None
alert_dispatcher_task: Optional[asyncio.Task] = None

# Micro-Scalp Monitor
micro_scalp_monitor = None

# ============================================================================
# AUTHENTICATION
# ============================================================================

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key for protected endpoints"""
    # For now, allow all requests (you can add API key validation here)
    # Expected header: X-API-Key: your-secret-key
    if x_api_key is None:
        # Allow requests without API key for now
        return True
    
    # TODO: Implement actual API key validation
    # expected_key = os.getenv("API_KEY", "your-secret-key")
    # if x_api_key != expected_key:
    #     raise HTTPException(status_code=401, detail="Invalid API key")
    
    return True

# ============================================================================
# STARTUP/SHUTDOWN
# ============================================================================

async def oco_monitor_loop():
    """Background task that monitors OCO pairs every 3 seconds"""
    global oco_monitor_running
    
    logger.info("OCO monitor starting...")
    oco_monitor_running = True
    
    while oco_monitor_running:
        try:
            if mt5_service:
                actions = oco_tracker.monitor_oco_pairs(mt5_service)
                if actions:
                    for oco_id, action in actions.items():
                        logger.info(f"OCO Monitor - {oco_id}: {action}")
        except Exception as e:
            logger.error(f"OCO monitor error: {e}", exc_info=True)
        
        await asyncio.sleep(3)  # Check every 3 seconds
    
    logger.info("OCO monitor stopped")


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global mt5_service, journal_repo, indicator_bridge, startup_time, oco_monitor_task, custom_alerts_manager, micro_scalp_monitor
    
    try:
        logger.info("Initializing services...")
        
        # Initialize MT5
        mt5_service = MT5Service()
        connected = mt5_service.connect()
        if connected:
            logger.info("MT5 connected successfully")
        else:
            logger.error("MT5 connection failed")
        
        # Initialize journal
        journal_repo = JournalRepo("data/journal.sqlite")
        logger.info("Journal repository initialized")
        
        # Initialize indicator bridge
        indicator_bridge = IndicatorBridge(settings.MT5_FILES_DIR)
        logger.info("Indicator bridge initialized")
        
        # Start OCO monitoring background task
        oco_monitor_task = asyncio.create_task(oco_monitor_loop())
        logger.info("OCO monitor task started")
        
        startup_time = datetime.now()

        # Initialize custom alerts manager
        custom_alerts_manager = CustomAlertManager("data/custom_alerts.json")
        logger.info("Custom alerts manager initialized")

        # ---------------------------------------
        # UNIFIED TICK PIPELINE - DISABLED FOR RESOURCE CONSERVATION
        # ---------------------------------------
        # DISABLED: The Unified Tick Pipeline with Binance WebSocket streams
        # is extremely resource-intensive (CPU ~10-20%, high RAM/SSD usage).
        # The system continues to function perfectly using:
        #   - Multi-Timeframe Streamer (lightweight MT5 candlestick data)
        #   - Direct MT5 calls (for ChatGPT analysis)
        #   - DTMS monitoring (if enabled separately)
        # 
        # If you need Binance tick-level data in the future, enable this
        # only on a dedicated server, not a personal laptop/desktop.
        # ---------------------------------------
        # try:
        #     logger.info("🚀 Initializing Unified Tick Pipeline for Main API...")
        #     pipeline_success = await initialize_main_api_unified_pipeline()
        #     if pipeline_success:
        #         logger.info("✅ Unified Tick Pipeline integration initialized")
        #         logger.info("   → Enhanced market data endpoints")
        #         logger.info("   → Real-time tick data access")
        #         logger.info("   → Multi-timeframe analysis")
        #         logger.info("   → Volatility monitoring")
        #         logger.info("   → Offset calibration")
        #         logger.info("   → System health monitoring")
        #     else:
        #         logger.warning("⚠️ Unified Tick Pipeline integration failed")
        #         logger.info("   → Main API will continue with existing data sources")
        # except Exception as e:
        #     logger.error(f"❌ Unified Tick Pipeline initialization error: {e}", exc_info=True)
        logger.info("ℹ️ Unified Tick Pipeline disabled for resource conservation")
        logger.info("   → Using lightweight Multi-Timeframe Streamer instead")
        
        # Initialize Micro-Scalp Monitor (Moved from app/main_api.py)
        try:
            logger.info("🔍 Initializing Micro-Scalp Monitor...")
            from infra.micro_scalp_monitor import MicroScalpMonitor
            from infra.micro_scalp_engine import MicroScalpEngine
            from infra.micro_scalp_execution import MicroScalpExecutionManager
            from infra.m1_data_fetcher import M1DataFetcher
            from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
            from infra.spread_tracker import SpreadTracker
            
            # Initialize M1 components for micro-scalp engine
            m1_data_fetcher = M1DataFetcher(
                data_source=mt5_service,
                max_candles=200,
                cache_ttl=300
            )
            
            m1_analyzer = M1MicrostructureAnalyzer(mt5_service=mt5_service)
            
            # Initialize spread tracker
            spread_tracker = SpreadTracker()
            
            # Initialize session manager (optional)
            session_manager = None
            try:
                from infra.m1_session_volatility_profile import SessionVolatilityProfile
                from infra.m1_asset_profiles import AssetProfileManager
                asset_profiles = AssetProfileManager("config/asset_profiles.json")
                session_manager = SessionVolatilityProfile(asset_profiles)
            except Exception as e:
                logger.debug(f"Session manager not available: {e}")
            
            # Initialize news service (optional)
            news_service = None
            try:
                from infra.news_service import NewsService
                news_service = NewsService()
            except Exception as e:
                logger.debug(f"News service not available: {e}")
            
            # NOTE: Multi-Timeframe Streamer is initialized in app/main_api.py
            # We'll try to get it from there, or initialize a minimal one here
            multi_tf_streamer = None
            try:
                # Try to import from app/main_api if it's running
                import sys
                if 'app.main_api' in sys.modules:
                    from app.main_api import multi_tf_streamer as app_streamer
                    multi_tf_streamer = app_streamer
                    logger.info("   → Using Multi-Timeframe Streamer from app/main_api.py")
            except Exception as e:
                logger.debug(f"Could not get streamer from app/main_api: {e}")
                # Could initialize a minimal streamer here if needed
                logger.warning("   → Micro-scalp will work without streamer (M5/M15 data may be limited)")
            
            # Initialize micro-scalp engine
            micro_scalp_engine = MicroScalpEngine(
                config_path="config/micro_scalp_config.json",
                mt5_service=mt5_service,
                m1_fetcher=m1_data_fetcher,
                streamer=multi_tf_streamer,  # May be None if app/main_api not running
                m1_analyzer=m1_analyzer,
                session_manager=session_manager,
                news_service=news_service
            )
            
            # Load micro-scalp config for execution manager
            micro_scalp_config = {}
            try:
                with open("config/micro_scalp_config.json", 'r') as f:
                    micro_scalp_config = json.load(f)
            except FileNotFoundError:
                logger.debug("Micro-scalp config not found, using defaults")
            except Exception as e:
                logger.debug(f"Error loading micro-scalp config: {e}")
            
            # Initialize micro-scalp execution manager
            micro_scalp_execution = MicroScalpExecutionManager(
                config=micro_scalp_config,
                mt5_service=mt5_service,
                spread_tracker=spread_tracker,
                m1_fetcher=m1_data_fetcher
            )
            
            # Initialize micro-scalp monitor
            global micro_scalp_monitor
            micro_scalp_monitor = MicroScalpMonitor(
                symbols=["BTCUSDc", "XAUUSDc"],  # Default symbols
                check_interval=5,
                micro_scalp_engine=micro_scalp_engine,
                execution_manager=micro_scalp_execution,
                streamer=multi_tf_streamer,  # May be None
                mt5_service=mt5_service,
                config_path="config/micro_scalp_automation.json",
                session_manager=session_manager,
                news_service=news_service
            )
            
            # Start monitoring (if enabled in config)
            if micro_scalp_monitor.enabled:
                micro_scalp_monitor.start()
                logger.info("✅ Micro-Scalp Monitor started")
                logger.info("   → Continuous monitoring for micro-scalp setups")
                logger.info("   → Independent from ChatGPT and auto-execution plans")
                logger.info("   → Immediate execution when conditions are met")
            else:
                logger.info("⏸️ Micro-Scalp Monitor disabled in config")
                # Ensure it's stopped if it was running before
                if micro_scalp_monitor.monitoring:
                    micro_scalp_monitor.stop()
                    logger.info("   → Stopped any running micro-scalp monitoring")
            
        except Exception as e:
            logger.warning(f"⚠️ Micro-Scalp Monitor initialization failed: {e}")
            logger.info("   → Root API will continue without micro-scalp automation")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")

        # ---------------------------------------
        # INTELLIGENT EXITS + DTMS - DISABLED (Require Unified Pipeline)
        # ---------------------------------------
        # DISABLED: These integrations require the Unified Tick Pipeline.
        # Since the pipeline is disabled for resource conservation, these
        # are also disabled. Intelligent Exits and DTMS continue to work
        # via their standard integrations (not unified pipeline).
        # ---------------------------------------
        # try:
        #     ie_ok, dtms_ok = await asyncio.gather(
        #         initialize_intelligent_exits_unified_pipeline(),
        #         initialize_dtms_unified_pipeline()
        #     )
        #     if ie_ok:
        #         logger.info("✅ Intelligent Exits initialized.")
        #     else:
        #         logger.error("❌ Intelligent Exits failed to initialize.")
        #
        #     if dtms_ok:
        #         logger.info("✅ DTMS initialized.")
        #     else:
        #         logger.error("❌ DTMS failed to initialize.")
        # except Exception as e_init:
        #     logger.error(f"Failed initializing IE/DTMS: {e_init}", exc_info=True)
        logger.info("ℹ️ Intelligent Exits/DTMS unified pipeline integrations disabled")
        logger.info("   → Standard Intelligent Exits and DTMS continue to work normally")
        
        # NOTE: Auto-Execution System is started in app/main_api.py (port 8000)
        # This server (main_api.py root, port 8010) does NOT start it to avoid duplicate instances
        # The webpage will check status from app/main_api.py via the API endpoint
        logger.info("ℹ️ Auto-Execution System runs on app/main_api.py (port 8000)")
        logger.info("   → This server (port 8010) does not start it to prevent duplicate instances")

        # ---------------------------------------
        # DISCORD ALERT DISPATCHER
        # ---------------------------------------
        try:
            global alert_dispatcher, alert_dispatcher_task
            
            alert_dispatcher = DiscordAlertDispatcher()
            await alert_dispatcher.start()
            
            # Create background task for detection loop (runs every 60 seconds)
            async def alert_detection_loop():
                cycle_count = 0
                while True:
                    try:
                        cycle_count += 1
                        logger.debug(f"Running alert detection cycle #{cycle_count}")
                        await alert_dispatcher.run_detection_cycle()
                        logger.debug(f"Alert detection cycle #{cycle_count} completed")
                    except Exception as e:
                        logger.error(f"Alert detection error in cycle #{cycle_count}: {e}", exc_info=True)
                    await asyncio.sleep(60)
            
            alert_dispatcher_task = asyncio.create_task(alert_detection_loop())
            logger.info("✅ Discord Alert Dispatcher started")
            logger.info("   → Monitoring BTCUSDc, XAUUSDc, GBPUSDc, EURUSDc")
            logger.info("   → Alerts: CHOCH, BOS, Sweeps, OB, VWAP, BB, Inside Bar")
        except Exception as e:
            logger.warning(f"⚠️ Discord Alert Dispatcher failed to start: {e}")
            logger.info("   → Alerts will not be sent to Discord")

    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown with timeouts to prevent hanging during reload"""
    global micro_scalp_monitor
    # Stop micro-scalp monitor if running
    if micro_scalp_monitor is not None and micro_scalp_monitor.monitoring:
        try:
            micro_scalp_monitor.stop()
            logger.info("⏹️ Micro-Scalp Monitor stopped")
        except Exception as e:
            logger.warning(f"Error stopping micro-scalp monitor: {e}")
    global oco_monitor_running, oco_monitor_task, alert_dispatcher_task, alert_dispatcher
    
    logger.info("Shutting down API server...")
    
    # Helper to stop async operations with timeout
    async def stop_with_timeout(coro, timeout=3.0, name="service"):
        try:
            await asyncio.wait_for(coro, timeout=timeout)
            logger.debug(f"{name} stopped")
        except asyncio.TimeoutError:
            logger.warning(f"{name} shutdown timed out after {timeout}s - continuing")
        except Exception as e:
            logger.debug(f"Error stopping {name}: {e}")
    
    # Stop OCO monitor (with timeout)
    oco_monitor_running = False
    if oco_monitor_task:
        oco_monitor_task.cancel()
        try:
            await asyncio.wait_for(oco_monitor_task, timeout=1.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        except Exception:
            pass

    # Stop Discord Alert Dispatcher (with timeout)
    if alert_dispatcher_task:
        alert_dispatcher_task.cancel()
        try:
            await asyncio.wait_for(alert_dispatcher_task, timeout=1.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        except Exception:
            pass
    if alert_dispatcher:
        await stop_with_timeout(alert_dispatcher.stop(), timeout=2.0, name="Discord Alert Dispatcher")

    # Stop Intelligent Exits + DTMS (disabled - unified pipeline not running)
    # try:
    #     await stop_intelligent_exits_unified_pipeline()
    #     await stop_dtms_unified_pipeline()
    #     logger.info("IE/DTMS stopped")
    # except Exception as e_stop:
    #     logger.error(f"Error while stopping IE/DTMS: {e_stop}", exc_info=True)
    logger.info("Unified pipeline integrations not running (disabled)")
    
    logger.info("Shutdown complete")

# ============================================================================
# SYSTEM ENDPOINTS
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with navigation dashboard"""
    html = (
        """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MoneyBot - Trading System Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #0b1220; color: #e6edf3; }
    h1 { margin-bottom: 8px; color: #e6edf3; }
    .sub { color: #9fb0c3; margin-bottom: 24px; }
    .dashboard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 24px; }
    .dashboard-card { background: #111a2e; border: 1px solid #213352; border-radius: 8px; padding: 20px; }
    .dashboard-card h3 { margin-top: 0; color: #e6edf3; }
    .dashboard-card p { color: #9fb0c3; margin: 12px 0; }
    .dashboard-card a { display: inline-block; margin-top: 12px; padding: 10px 16px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; color: #90c0ff; text-decoration: none; }
    .dashboard-card a:hover { background: #213352; color: #e6edf3; }
    .status-indicator { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }
    .status-active { background: #90ee90; }
    .status-inactive { background: #ff9090; }
    .api-info { background: #111a2e; border: 1px solid #213352; border-radius: 8px; padding: 20px; margin-bottom: 24px; }
    .api-info h2 { margin-top: 0; color: #e6edf3; }
    .api-info .info-item { margin: 8px 0; color: #9fb0c3; }
    .api-info .info-item strong { color: #e6edf3; }
  </style>
</head>
<body>
  <h1>MoneyBot v1.1 - Advanced AI Trading System</h1>
  <div class="sub">Comprehensive Trading Dashboard & API</div>
  
  <div class="api-info">
    <h2>API Information</h2>
    <div class="info-item"><strong>Service:</strong> MoneyBot v1.1 - Advanced AI Trading System API</div>
    <div class="info-item"><strong>Version:</strong> 1.1.0</div>
    <div class="info-item"><strong>Status:</strong> <span class="status-indicator status-active"></span>Running</div>
    <div class="info-item"><strong>API Docs:</strong> <a href="/docs" style="color: #90c0ff;">Swagger UI</a> | <a href="/redoc" style="color: #90c0ff;">ReDoc</a></div>
  </div>
  
  <div class="dashboard-grid">
    <div class="dashboard-card">
      <h3>📊 Volatility Regime Monitor</h3>
      <p>Real-time volatility regime detection and monitoring for all symbols. View current regime status, confidence levels, and regime change history.</p>
      <a href="/volatility-regime/monitor">Open Monitor →</a>
    </div>
    
    <div class="dashboard-card">
      <h3>🔔 Notifications Management</h3>
      <p>Manage Discord and Telegram notifications. View notification history, configure alert settings, and test notification channels.</p>
      <a href="/notifications/view">Manage Notifications →</a>
    </div>
    
    <div class="dashboard-card">
      <h3>⚠️ ChatGPT Alerts</h3>
      <p>View and manage active ChatGPT-configured alerts. Monitor alert triggers, expiration dates, and alert status.</p>
      <a href="/alerts/view">View Alerts →</a>
    </div>
    
    <div class="dashboard-card">
      <h3>🤖 Auto Execution Plans</h3>
      <p>Monitor and manage auto-execution trade plans. View pending plans, execution status, and trade conditions.</p>
      <a href="/auto-execution/view">View Plans →</a>
    </div>
    
    <div class="dashboard-card">
      <h3>🔍 Micro-Scalp Monitor</h3>
      <p>Continuous monitoring for micro-scalp setups. View real-time condition checks, regime detection, and strategy selection.</p>
      <a href="/micro-scalp/view">View Monitor →</a>
    </div>
    
    <div class="dashboard-card">
      <h3>🛡️ DTMS Status</h3>
      <p>Dynamic Trade Management System status. Monitor active trades, intelligent exits, and protection systems.</p>
      <a href="/dtms/status">View Status →</a>
    </div>
    
    <div class="dashboard-card">
      <h3>📋 DTMS Actions</h3>
      <p>View DTMS action history. Track intelligent exit actions, trade management events, and system decisions.</p>
      <a href="/dtms/actions">View Actions →</a>
    </div>
  </div>
</body>
</html>
        """
    )
    return HTMLResponse(content=html)

@app.get("/alerts")
async def list_active_alerts(enabled_only: bool = True):
    """List ChatGPT-configured alerts (from data/custom_alerts.json)."""
    try:
        if custom_alerts_manager is None:
            raise HTTPException(status_code=500, detail="Alerts manager not initialized")

        # Reload from disk to reflect external changes
        custom_alerts_manager.load_alerts()

        alerts = custom_alerts_manager.get_all_alerts(enabled_only=enabled_only)
        # Convert dataclasses/enums to plain dicts
        normalized = []
        for a in alerts:
            normalized.append({
                "alert_id": a.alert_id,
                "symbol": a.symbol,
                "alert_type": a.alert_type.value if hasattr(a.alert_type, "value") else a.alert_type,
                "condition": a.condition.value if hasattr(a.condition, "value") else a.condition,
                "description": a.description,
                "parameters": a.parameters,
                "created_at": a.created_at,
                "expires_at": a.expires_at,
                "enabled": a.enabled,
                "triggered_count": a.triggered_count,
                "last_triggered": a.last_triggered,
                "one_time": a.one_time
            })
        return {"ok": True, "count": len(normalized), "alerts": normalized}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str):
    """Delete an alert by ID."""
    try:
        if custom_alerts_manager is None:
            raise HTTPException(status_code=500, detail="Alerts manager not initialized")
        
        # Remove the alert (this saves to disk with atomic write and fsync)
        removed = custom_alerts_manager.remove_alert(alert_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        logger.info(f"✅ Successfully deleted alert: {alert_id}")
        return {"ok": True, "deleted": alert_id, "message": f"Alert {alert_id} permanently deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting alert {alert_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts/view", response_class=HTMLResponse)
async def view_alerts_page():
    """Simple HTML page to view active ChatGPT alerts."""
    html = (
        """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MoneyBot - Active ChatGPT Alerts</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #0b1220; color: #e6edf3; }
    h1 { margin-bottom: 8px; }
    .sub { color: #9fb0c3; margin-bottom: 16px; }
    .controls { margin-bottom: 16px; display: flex; gap: 8px; align-items: center; }
    input[type="text"] { padding: 8px; border-radius: 6px; border: 1px solid #24324a; background: #0f172a; color: #e6edf3; }
    button { padding: 8px 12px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; }
    button:hover { background: #213352; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid #213352; padding: 10px; text-align: left; }
    th { background: #111a2e; position: sticky; top: 0; }
    .pill { padding: 2px 8px; border-radius: 999px; font-size: 12px; border: 1px solid #2b3b57; background: #0f172a; }
    .muted { color: #9fb0c3; font-size: 12px; }
    .wrap { white-space: pre-wrap; word-break: break-word; }
    .nav { margin-bottom: 20px; }
    .nav a { color: #9fb0c3; text-decoration: none; margin-right: 20px; }
    .nav a:hover { color: #e6edf3; }
  </style>
  <script>
    async function loadAlerts() {
      const enabledOnly = document.getElementById('enabledOnly').checked;
      const res = await fetch(`/alerts?enabled_only=${enabledOnly}`);
      const data = await res.json();
      const q = document.getElementById('q').value.toLowerCase();
      const tbody = document.getElementById('tbody');
      tbody.innerHTML = '';
      (data.alerts || []).filter(a => {
        if (!q) return true;
        const blob = JSON.stringify(a).toLowerCase();
        return blob.includes(q);
      }).forEach(a => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><div class="wrap">${a.alert_id}</div><div class="muted">${a.created_at || ''}</div></td>
          <td>${a.symbol}</td>
          <td><span class="pill">${a.alert_type}</span></td>
          <td><span class="pill">${a.condition}</span></td>
          <td><div class="wrap">${a.description}</div><div class="muted">${a.expires_at ? ('expires ' + a.expires_at) : ''}</div></td>
          <td><div class="wrap">${JSON.stringify(a.parameters)}</div></td>
          <td>${a.enabled ? 'Yes' : 'No'}</td>
          <td>${a.triggered_count}</td>
          <td>
            <button onclick="deleteAlert('${a.alert_id}')">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
      document.getElementById('count').textContent = data.count || 0;
    }
    async function deleteAlert(id) {
      if (!confirm(`Delete alert ${id}?`)) return;
      const res = await fetch(`/alerts/` + encodeURIComponent(id), { method: 'DELETE' });
      if (res.ok) {
        await loadAlerts();
      } else {
        const data = await res.json().catch(() => ({}));
        alert('Error: ' + (data.detail || res.statusText));
      }
    }
    function init() {
      loadAlerts();
      setInterval(loadAlerts, 10000);
      document.getElementById('refresh').addEventListener('click', loadAlerts);
      document.getElementById('q').addEventListener('input', loadAlerts);
      document.getElementById('enabledOnly').addEventListener('change', loadAlerts);
    }
    window.addEventListener('load', init);
  </script>
  </head>
  <body>
    <div class="nav">
      <a href="/">Home</a>
      <a href="/volatility-regime/monitor">Volatility Monitor</a>
      <a href="/notifications/view">Notifications</a>
      <a href="/alerts/view">ChatGPT Alerts</a>
      <a href="/auto-execution/view">Auto Execution Plans</a>
      <a href="/micro-scalp/view">Micro-Scalp Monitor</a>
      <a href="/dtms/status">DTMS Status</a>
      <a href="/dtms/actions">DTMS Actions</a>
      <a href="/docs">API Docs</a>
    </div>
    <h1>Active ChatGPT Alerts</h1>
    <div class="sub">Viewing alerts from data/custom_alerts.json • Total: <span id="count">0</span></div>
    <div class="controls">
      <input id="q" type="text" placeholder="Search alerts..." />
      <label><input id="enabledOnly" type="checkbox" checked /> Enabled only</label>
      <button id="refresh">Refresh</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Symbol</th>
          <th>Type</th>
          <th>Condition</th>
          <th>Description</th>
          <th>Parameters</th>
          <th>Enabled</th>
          <th>Triggered</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </body>
</html>
        """
    )
    return HTMLResponse(content=html)

@app.get("/auto-execution/view", response_class=HTMLResponse)
async def view_auto_execution_plans():
    """Simple HTML page to view active auto execution trade plans."""
    html = (
        """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MoneyBot - Auto Execution Trade Plans</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #0b1220; color: #e6edf3; }
    h1 { margin-bottom: 8px; }
    .sub { color: #9fb0c3; margin-bottom: 16px; }
    .controls { margin-bottom: 16px; display: flex; gap: 8px; align-items: center; }
    input[type="text"] { padding: 8px; border-radius: 6px; border: 1px solid #24324a; background: #0f172a; color: #e6edf3; }
    button { padding: 8px 12px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; }
    button:hover { background: #213352; }
    button.danger { background: #5c1a1a; border-color: #7c1a1a; }
    button.danger:hover { background: #7c1a1a; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid #213352; padding: 10px; text-align: left; }
    th { background: #111a2e; position: sticky; top: 0; }
    .pill { padding: 2px 8px; border-radius: 999px; font-size: 12px; border: 1px solid #2b3b57; background: #0f172a; }
    .pill.pending { background: #1a3a1a; border-color: #2d5a2d; color: #90ee90; }
    .pill.executed { background: #1a1a3a; border-color: #2d2d5a; color: #90c0ff; }
    .pill.cancelled { background: #3a1a1a; border-color: #5a2d2d; color: #ff9090; }
    .pill.expired { background: #2a2a2a; border-color: #4a4a4a; color: #cccccc; }
    .muted { color: #9fb0c3; font-size: 12px; }
    .wrap { white-space: pre-wrap; word-break: break-word; }
    .price { font-family: monospace; }
    .direction { font-weight: bold; }
    .direction.buy { color: #90ee90; }
    .direction.sell { color: #ff9090; }
    .nav { margin-bottom: 20px; }
    .nav a { color: #9fb0c3; text-decoration: none; margin-right: 20px; }
    .nav a:hover { color: #e6edf3; }
    .conditions { font-family: monospace; font-size: 12px; color: #9fb0c3; background: #0f172a; padding: 6px; border-radius: 4px; max-width: 400px; }
    .conditions-key { color: #90c0ff; }
    .conditions-value { color: #90ee90; }
    .conditions-missing { color: #ff9090; }
    .conditions-section { margin-bottom: 8px; }
    .conditions-section-title { font-weight: bold; color: #90c0ff; margin-bottom: 4px; }
    select { padding: 8px; border-radius: 6px; border: 1px solid #24324a; background: #0f172a; color: #e6edf3; }
    .monitoring-status { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding: 12px; background: #0f172a; border-radius: 8px; border: 1px solid #24324a; }
    .status-indicator { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
    .status-indicator.active { background: #22c55e; box-shadow: 0 0 8px rgba(34, 197, 94, 0.5); }
    .status-indicator.inactive { background: #ef4444; box-shadow: 0 0 8px rgba(239, 68, 68, 0.5); }
    .status-text { color: #e6edf3; font-size: 14px; }
    .status-text.active { color: #22c55e; }
    .status-text.inactive { color: #ef4444; }
    .status-details { color: #9fb0c3; font-size: 12px; margin-left: 4px; }
  </style>
  <script>
    // Determine required conditions based on plan type
    function getRequiredConditions(conditions, notes) {
      const required = [];
      const notesLower = (notes || '').toLowerCase();
      const conds = conditions || {};
      
      // MICRO-SCALP PLANS - Check FIRST (highest priority)
      if (conds.plan_type === 'micro_scalp') {
        // Micro-scalp plans use 4-layer validation system, not traditional conditions
        // Show micro-scalp-specific status instead of generic condition checks
        required.push({key: 'plan_type: micro_scalp', present: true, microScalp: true});
        if (conds.timeframe) {
          required.push({key: 'timeframe: ' + conds.timeframe, present: true, microScalp: true});
        }
        // Micro-scalp plans may have optional conditions (choch_bull/bear, price_near, etc.)
        // but these are not required - the 4-layer system handles validation
        if (conds.choch_bull || conds.choch_bear) {
          required.push({key: 'CHOCH signal (optional)', present: true, microScalp: true});
        }
        if (conds.price_near) {
          required.push({key: 'price_near (optional)', present: true, microScalp: true});
        }
        // Return early - don't apply other validations
        return required;
      }
      
      // Check if there are other strategy types already identified
      const hasOtherStrategy = conds.rejection_wick || conds.choch_bull || conds.choch_bear || conds.liquidity_sweep || conds.vwap_deviation || conds.order_block;
      
      // CHOCH/BOS plans
      if (conds.choch_bull || conds.choch_bear || notesLower.includes('choch') || notesLower.includes('bos') || notesLower.includes('break of structure')) {
        if (conds.choch_bull || conds.choch_bear) {
          required.push({key: 'choch_bull or choch_bear', present: !!(conds.choch_bull || conds.choch_bear)});
        } else {
          required.push({key: 'choch_bull or choch_bear', present: false});
        }
        if (!conds.timeframe && !notesLower.includes('m1')) {
          required.push({key: 'timeframe', present: false});
        } else if (conds.timeframe) {
          required.push({key: 'timeframe', present: true});
        }
        // WARNING: price_near is recommended for CHOCH plans to ensure execution at intended entry
        // Without it, plan will execute at ANY price when CHOCH confirms
        if (!conds.price_near) {
          required.push({key: 'price_near (RECOMMENDED)', present: false, warning: true});
        } else {
          required.push({key: 'price_near (RECOMMENDED)', present: true});
        }
      }
      
      // Liquidity Sweep plans - only if explicitly a Liquidity Sweep strategy
      // Only require liquidity_sweep conditions if:
      // 1. liquidity_sweep is explicitly set in conditions, OR
      // 2. Notes explicitly say it's a Liquidity Sweep strategy (not just mentioned in passing)
      const isLiquiditySweepStrategy = conds.liquidity_sweep || 
                                      (notesLower.includes('liquidity sweep strategy') && !hasOtherStrategy) ||
                                      (notesLower.includes('liquidity sweep plan') && !hasOtherStrategy) ||
                                      (notesLower.includes('stop hunt strategy') && !hasOtherStrategy) ||
                                      (notesLower.includes('sweep strategy') && !hasOtherStrategy);
      
      if (isLiquiditySweepStrategy) {
        required.push({key: 'liquidity_sweep', present: !!conds.liquidity_sweep});
        if (!conds.price_below && !conds.price_above) {
          required.push({key: 'price_below or price_above', present: false});
        } else {
          required.push({key: 'price_below or price_above', present: true});
        }
        if (!conds.timeframe) {
          required.push({key: 'timeframe', present: false});
        } else {
          required.push({key: 'timeframe', present: true});
        }
      }
      
      // Rejection Wick plans
      if (conds.rejection_wick || notesLower.includes('rejection wick') || notesLower.includes('pin bar') || notesLower.includes('wick')) {
        required.push({key: 'rejection_wick', present: !!conds.rejection_wick});
        if (!conds.timeframe) {
          required.push({key: 'timeframe', present: false});
        } else {
          required.push({key: 'timeframe', present: true});
        }
        if (!conds.price_near) {
          required.push({key: 'price_near', present: false});
        } else {
          required.push({key: 'price_near', present: true});
        }
        if (!conds.tolerance) {
          required.push({key: 'tolerance', present: false});
        } else {
          required.push({key: 'tolerance', present: true});
        }
      }
      
      // VWAP Bounce/Fade plans - only if explicitly a VWAP strategy
      // Only require VWAP conditions if:
      // 1. vwap_deviation is explicitly set in conditions, OR
      // 2. Notes explicitly say it's a VWAP strategy (not just mentioned in passing)
      const isVwapStrategy = conds.vwap_deviation || 
                             (notesLower.includes('vwap bounce') && !hasOtherStrategy) || 
                             (notesLower.includes('vwap fade') && !hasOtherStrategy) ||
                             (notesLower.includes('vwap deviation strategy') && !hasOtherStrategy) ||
                             (notesLower.includes('vwap strategy') && !hasOtherStrategy);
      
      if (isVwapStrategy) {
        required.push({key: 'vwap_deviation', present: !!conds.vwap_deviation});
        if (!conds.vwap_deviation_direction) {
          required.push({key: 'vwap_deviation_direction', present: false});
        } else {
          required.push({key: 'vwap_deviation_direction', present: true});
        }
        if (!conds.price_near) {
          required.push({key: 'price_near', present: false});
        } else {
          required.push({key: 'price_near', present: true});
        }
        if (!conds.tolerance) {
          required.push({key: 'tolerance', present: false});
        } else {
          required.push({key: 'tolerance', present: true});
        }
      }
      
      // Order Block plans
      if (conds.order_block || notesLower.includes('order block') || notesLower.includes('ob')) {
        required.push({key: 'order_block', present: !!conds.order_block});
        if (!conds.order_block_type) {
          required.push({key: 'order_block_type', present: false});
        } else {
          required.push({key: 'order_block_type', present: true});
        }
      }
      
      return required;
    }
    
    async function loadPlans() {
      try {
        const res = await fetch('/auto-execution/status');
        const data = await res.json();
        const qEl = document.getElementById('q');
        const symbolFilterEl = document.getElementById('symbolFilter');
        const q = qEl ? qEl.value.toLowerCase() : '';
        const symbolFilter = symbolFilterEl ? symbolFilterEl.value : 'all';
        const tbody = document.getElementById('tbody');
        if (!tbody) {
          console.error('Table body element not found');
          return;
        }
        tbody.innerHTML = '';
        
        if (data.success && data.plans) {
          // Sort by created_at descending (newest first)
          let filteredPlans = data.plans
            .filter(plan => {
              // Text search filter
              if (q) {
                const blob = JSON.stringify(plan).toLowerCase();
                if (!blob.includes(q)) return false;
              }
              // Symbol filter
              if (symbolFilter && symbolFilter !== 'all') {
                if (plan.symbol.toLowerCase() !== symbolFilter.toLowerCase()) return false;
              }
              return true;
            })
            .sort((a, b) => {
              const dateA = new Date(a.created_at || 0);
              const dateB = new Date(b.created_at || 0);
              return dateB - dateA; // Descending order (newest first)
            });
          
          // Update symbol filter dropdown
          const uniqueSymbols = [...new Set(data.plans.map(p => p.symbol))].sort();
          const symbolSelect = document.getElementById('symbolFilter');
          if (symbolSelect) {
            const currentValue = symbolSelect.value;
            symbolSelect.innerHTML = '<option value="all">All Symbols</option>';
            uniqueSymbols.forEach(symbol => {
              const option = document.createElement('option');
              option.value = symbol;
              option.textContent = symbol;
              symbolSelect.appendChild(option);
            });
            symbolSelect.value = currentValue || 'all';
          }
          
          filteredPlans.forEach(plan => {
            const tr = document.createElement('tr');
            const statusClass = plan.status.toLowerCase();
            const directionClass = plan.direction.toLowerCase();
            
            // Format conditions for display with required vs actual
            function formatConditions(conditions, notes) {
              if (!conditions || Object.keys(conditions).length === 0) {
                return '<span class="muted">No conditions</span>';
              }
              
              const required = getRequiredConditions(conditions, notes);
              const isMicroScalp = required.some(r => r.microScalp);
              const hasMissing = required.some(r => !r.present && !r.microScalp);
              
              let html = '<div class="conditions-section">';
              
              // Micro-scalp plans - show special status
              if (isMicroScalp) {
                html += '<div class="conditions-section-title">Micro-Scalp Plan Status:</div>';
                html += '<div style="color: #90ee90; font-size: 12px; margin-bottom: 4px;">✓ Using 4-Layer Validation System</div>';
                html += '<div style="color: #9fb0c3; font-size: 11px; margin-bottom: 8px;">';
                html += '• Pre-Trade Filters (volatility, spread)<br>';
                html += '• Location Filter (must be at "EDGE")<br>';
                html += '• Candle Signal Checklist (primary + secondary)<br>';
                html += '• Confluence Score (≥5 to trade, ≥7 for A+ setup)';
                html += '</div>';
                
                // Show optional conditions if present
                const optionalConditions = required.filter(r => r.microScalp && r.key.includes('(optional)'));
                if (optionalConditions.length > 0) {
                  html += '<div class="conditions-section-title" style="margin-top: 8px;">Optional Conditions:</div>';
                  optionalConditions.forEach(req => {
                    html += `<div><span class="conditions-value">✓ ${req.key}</span></div>`;
                  });
                }
                
                html += '</div><div class="conditions-section"><div class="conditions-section-title">Actual Conditions:</div>';
              } else {
                // Show required conditions section for non-micro-scalp plans
                if (required.length > 0) {
                  html += '<div class="conditions-section-title">Required:</div>';
                  required.forEach(req => {
                    const status = req.present ? 'conditions-value' : (req.warning ? 'conditions-missing' : 'conditions-missing');
                    const icon = req.present ? '✓' : '✗';
                    const warningText = req.warning ? ' ⚠️' : '';
                    html += `<div><span class="${status}">${icon} ${req.key}${warningText}</span></div>`;
                  });
                }
                
                html += '</div><div class="conditions-section"><div class="conditions-section-title">Actual Conditions:</div>';
              }
              
              const parts = [];
              if (conditions.price_above) parts.push(`<span class="conditions-key">price_above</span>: <span class="conditions-value">${conditions.price_above}</span>`);
              if (conditions.price_below) parts.push(`<span class="conditions-key">price_below</span>: <span class="conditions-value">${conditions.price_below}</span>`);
              if (conditions.price_near) {
                const tolerance = conditions.tolerance || 0.001;
                parts.push(`<span class="conditions-key">price_near</span>: <span class="conditions-value">${conditions.price_near}</span> ±${tolerance}`);
              }
              if (conditions.choch_bull) parts.push(`<span class="conditions-key">choch_bull</span>: <span class="conditions-value">true</span>`);
              if (conditions.choch_bear) parts.push(`<span class="conditions-key">choch_bear</span>: <span class="conditions-value">true</span>`);
              if (conditions.rejection_wick) {
                const ratio = conditions.min_wick_ratio || 2.0;
                parts.push(`<span class="conditions-key">rejection_wick</span>: <span class="conditions-value">true</span> (ratio≥${ratio})`);
              }
              if (conditions.liquidity_sweep) parts.push(`<span class="conditions-key">liquidity_sweep</span>: <span class="conditions-value">true</span>`);
              if (conditions.vwap_deviation) parts.push(`<span class="conditions-key">vwap_deviation</span>: <span class="conditions-value">true</span>`);
              if (conditions.vwap_deviation_direction) parts.push(`<span class="conditions-key">vwap_deviation_direction</span>: <span class="conditions-value">${conditions.vwap_deviation_direction}</span>`);
              if (conditions.order_block) parts.push(`<span class="conditions-key">order_block</span>: <span class="conditions-value">true</span>`);
              if (conditions.order_block_type) parts.push(`<span class="conditions-key">order_block_type</span>: <span class="conditions-value">${conditions.order_block_type}</span>`);
              if (conditions.timeframe || conditions.structure_tf || conditions.tf) {
                const tf = conditions.timeframe || conditions.structure_tf || conditions.tf;
                parts.push(`<span class="conditions-key">timeframe</span>: <span class="conditions-value">${tf}</span>`);
              }
              if (conditions.m1_choch_bos_combo) parts.push(`<span class="conditions-key">m1_choch_bos_combo</span>: <span class="conditions-value">true</span>`);
              if (conditions.min_volatility) parts.push(`<span class="conditions-key">min_volatility</span>: <span class="conditions-value">${conditions.min_volatility}</span>`);
              if (conditions.bb_width_threshold) parts.push(`<span class="conditions-key">bb_width_threshold</span>: <span class="conditions-value">${conditions.bb_width_threshold}</span>`);
              if (conditions.time_after) parts.push(`<span class="conditions-key">time_after</span>: <span class="conditions-value">${conditions.time_after}</span>`);
              if (conditions.time_before) parts.push(`<span class="conditions-key">time_before</span>: <span class="conditions-value">${conditions.time_before}</span>`);
              if (conditions.execute_immediately) parts.push(`<span class="conditions-key">execute_immediately</span>: <span class="conditions-value">true</span>`);
              if (conditions.volatility_state) parts.push(`<span class="conditions-key">volatility_state</span>: <span class="conditions-value">${conditions.volatility_state}</span>`);
              if (conditions.strategy_type) parts.push(`<span class="conditions-key">strategy_type</span>: <span class="conditions-value">${conditions.strategy_type}</span>`);
              if (conditions.min_confluence) parts.push(`<span class="conditions-key">min_confluence</span>: <span class="conditions-value">${conditions.min_confluence}</span>`);
              if (conditions.min_validation_score) parts.push(`<span class="conditions-key">min_validation_score</span>: <span class="conditions-value">${conditions.min_validation_score}</span>`);
              // BB conditions
              if (conditions.bb_expansion) parts.push(`<span class="conditions-key">bb_expansion</span>: <span class="conditions-value">true</span>`);
              if (conditions.bb_squeeze) parts.push(`<span class="conditions-key">bb_squeeze</span>: <span class="conditions-value">true</span>`);
              if (conditions.bb_expansion_threshold) parts.push(`<span class="conditions-key">bb_expansion_threshold</span>: <span class="conditions-value">>${conditions.bb_expansion_threshold}</span>`);
              if (conditions.bb_expansion_check_both) parts.push(`<span class="conditions-key">bb_expansion_check_both</span>: <span class="conditions-value">true</span>`);
              // BOS conditions
              if (conditions.bos_bull) parts.push(`<span class="conditions-key">bos_bull</span>: <span class="conditions-value">true</span>`);
              if (conditions.bos_bear) parts.push(`<span class="conditions-key">bos_bear</span>: <span class="conditions-value">true</span>`);
              // FVG conditions
              if (conditions.fvg_bull) parts.push(`<span class="conditions-key">fvg_bull</span>: <span class="conditions-value">true</span>`);
              if (conditions.fvg_bear) parts.push(`<span class="conditions-key">fvg_bear</span>: <span class="conditions-value">true</span>`);
              if (conditions.fvg_filled_pct) {
                const filled = conditions.fvg_filled_pct;
                if (typeof filled === 'object' && filled.min !== undefined) {
                  parts.push(`<span class="conditions-key">fvg_filled_pct</span>: <span class="conditions-value">${filled.min * 100}%-${filled.max * 100}%</span>`);
                } else {
                  parts.push(`<span class="conditions-key">fvg_filled_pct</span>: <span class="conditions-value">>=${filled * 100}%</span>`);
                }
              }
              // Range scalping conditions
              if (conditions.range_scalp_confluence !== undefined) parts.push(`<span class="conditions-key">range_scalp_confluence</span>: <span class="conditions-value">>=${conditions.range_scalp_confluence}</span>`);
              if (conditions.structure_confirmation) parts.push(`<span class="conditions-key">structure_confirmation</span>: <span class="conditions-value">true</span>`);
              if (conditions.structure_timeframe) parts.push(`<span class="conditions-key">structure_timeframe</span>: <span class="conditions-value">${conditions.structure_timeframe}</span>`);
              // Other pattern conditions
              if (conditions.inside_bar) parts.push(`<span class="conditions-key">inside_bar</span>: <span class="conditions-value">true</span>`);
              if (conditions.equal_highs) parts.push(`<span class="conditions-key">equal_highs</span>: <span class="conditions-value">true</span>`);
              if (conditions.equal_lows) parts.push(`<span class="conditions-key">equal_lows</span>: <span class="conditions-value">true</span>`);
              // RSI divergence conditions
              if (conditions.rsi_div_bull) parts.push(`<span class="conditions-key">rsi_div_bull</span>: <span class="conditions-value">true</span>`);
              if (conditions.rsi_div_bear) parts.push(`<span class="conditions-key">rsi_div_bear</span>: <span class="conditions-value">true</span>`);
              // Volatility conditions
              if (conditions.atr_5m_threshold) parts.push(`<span class="conditions-key">atr_5m_threshold</span>: <span class="conditions-value">>${conditions.atr_5m_threshold}</span>`);
              if (conditions.vix_threshold) parts.push(`<span class="conditions-key">vix_threshold</span>: <span class="conditions-value">>${conditions.vix_threshold}</span>`);
              if (conditions.volatility_trigger_rule) {
                const rule = conditions.volatility_trigger_rule;
                parts.push(`<span class="conditions-key">volatility_rule</span>: <span class="conditions-value">${rule} of ${Object.keys(conditions).filter(k => k.includes('threshold')).length}</span>`);
              }
              // Plan type conditions
              if (conditions.plan_type === 'micro_scalp') {
                parts.push(`<span class="conditions-key">plan_type</span>: <span class="conditions-value">micro_scalp</span>`);
              }
              if (conditions.plan_type === 'range_scalp') {
                parts.push(`<span class="conditions-key">plan_type</span>: <span class="conditions-value">range_scalp</span>`);
              }
              html += parts.join('<br>') || '<span class="muted">No additional conditions</span>';
              html += '</div>';
              
              // Only show missing conditions warning for non-micro-scalp plans
              if (hasMissing && !isMicroScalp) {
                html += '<div style="margin-top: 4px; color: #ff9090; font-size: 11px;">⚠ Missing required conditions</div>';
              } else if (isMicroScalp) {
                html += '<div style="margin-top: 4px; color: #90ee90; font-size: 11px;">✓ Micro-scalp plan - 4-layer validation active</div>';
              }
              
              return html;
            }
            
            // Format created_at timestamp
            function formatDateTime(isoString) {
              if (!isoString) return '<span class="muted">N/A</span>';
              try {
                const date = new Date(isoString);
                if (isNaN(date.getTime())) return '<span class="muted">Invalid date</span>';
                // Format as YYYY-MM-DD HH:MM:SS
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                const seconds = String(date.getSeconds()).padStart(2, '0');
                return `${year}-${month}-${day}<br><span class="muted">${hours}:${minutes}:${seconds}</span>`;
              } catch (e) {
                return '<span class="muted">Invalid date</span>';
              }
            }
            
            // Extract strategy_type from conditions
            const strategyType = plan.conditions?.strategy_type || '';
            const strategyDisplay = strategyType ? 
              `<span class="pill" style="background: #1a2a4a; border-color: #3a5a8a; color: #90c0ff; font-size: 11px;">${strategyType.replace(/_/g, ' ')}</span>` : 
              '<span class="muted">-</span>';
            
            tr.innerHTML = `
              <td><div class="wrap">${plan.plan_id}</div></td>
              <td>${formatDateTime(plan.created_at)}</td>
              <td>${plan.symbol}</td>
              <td><span class="direction ${directionClass}">${plan.direction}</span></td>
              <td><span class="price">${plan.entry_price}</span></td>
              <td><span class="price">${plan.stop_loss}</span></td>
              <td><span class="price">${plan.take_profit}</span></td>
              <td><span class="price">${plan.volume}</span></td>
              <td>${strategyDisplay}</td>
              <td><span class="pill ${statusClass}">${plan.status}</span></td>
              <td><div class="conditions">${formatConditions(plan.conditions, plan.notes)}</div></td>
              <td><div class="wrap">${plan.notes || ''}</div></td>
              <td>
                <button class="danger" onclick="cancelPlan('${plan.plan_id}')">Cancel</button>
              </td>
            `;
            tbody.appendChild(tr);
          });
          const countEl = document.getElementById('count');
          if (countEl) countEl.textContent = filteredPlans.length || 0;
        } else {
          tbody.innerHTML = '<tr><td colspan="13" style="text-align: center; color: #9fb0c3;">No plans found or error loading data</td></tr>';
          const countEl = document.getElementById('count');
          if (countEl) countEl.textContent = '0';
        }
      } catch (error) {
        console.error('Error loading plans:', error);
        const tbody = document.getElementById('tbody');
        if (tbody) {
          tbody.innerHTML = '<tr><td colspan="12" style="text-align: center; color: #ff9090;">Error loading plans: ' + error.message + '</td></tr>';
        }
        const countEl = document.getElementById('count');
        if (countEl) countEl.textContent = '0';
      }
    }
    
    async function cancelPlan(planId) {
      if (!confirm(`Cancel plan ${planId}?`)) return;
      try {
        const res = await fetch(`/auto-execution/cancel-plan/${planId}`, { method: 'POST' });
        if (res.ok) {
          await loadPlans();
        } else {
          const data = await res.json().catch(() => ({}));
          alert('Error: ' + (data.detail || res.statusText));
        }
      } catch (error) {
        alert('Error cancelling plan: ' + error.message);
      }
    }
    
    async function checkMonitoringStatus() {
      try {
        // Check status from app/main_api.py (port 8000) where the system actually runs
        const res = await fetch('http://localhost:8000/auto-execution/system-status');
        const data = await res.json();
        const statusEl = document.getElementById('monitoringStatus');
        const indicatorEl = document.getElementById('statusIndicator');
        const statusTextEl = document.getElementById('statusText');
        const statusDetailsEl = document.getElementById('statusDetails');
        
        if (data.success && data.system_status) {
          const running = data.system_status.running || false;
          const pendingPlans = data.system_status.pending_plans || 0;
          
          if (running) {
            if (indicatorEl) {
              indicatorEl.className = 'status-indicator active';
            }
            if (statusTextEl) {
              statusTextEl.textContent = 'Active';
              statusTextEl.className = 'status-text active';
            }
            if (statusDetailsEl) {
              statusDetailsEl.textContent = `• Monitoring ${pendingPlans} pending plan${pendingPlans !== 1 ? 's' : ''} • Checking every 30 seconds`;
            }
          } else {
            if (indicatorEl) {
              indicatorEl.className = 'status-indicator inactive';
            }
            if (statusTextEl) {
              statusTextEl.textContent = 'Not Running';
              statusTextEl.className = 'status-text inactive';
            }
            if (statusDetailsEl) {
              statusDetailsEl.textContent = '• Plans will NOT be monitored or executed • Check server logs for errors';
            }
          }
        } else {
          // Error or unknown status
          if (indicatorEl) {
            indicatorEl.className = 'status-indicator inactive';
          }
          if (statusTextEl) {
            statusTextEl.textContent = 'Unknown';
            statusTextEl.className = 'status-text inactive';
          }
          if (statusDetailsEl) {
            statusDetailsEl.textContent = '• Could not determine status';
          }
        }
      } catch (error) {
        console.error('Error checking monitoring status:', error);
        const indicatorEl = document.getElementById('statusIndicator');
        const statusTextEl = document.getElementById('statusText');
        const statusDetailsEl = document.getElementById('statusDetails');
        
        if (indicatorEl) {
          indicatorEl.className = 'status-indicator inactive';
        }
        if (statusTextEl) {
          statusTextEl.textContent = 'Error';
          statusTextEl.className = 'status-text inactive';
        }
        if (statusDetailsEl) {
          statusDetailsEl.textContent = '• Could not connect to status endpoint';
        }
      }
    }
    
    function init() {
      loadPlans();
      checkMonitoringStatus();
      setInterval(loadPlans, 10000);
      setInterval(checkMonitoringStatus, 30000); // Check status every 30 seconds
      const refreshBtn = document.getElementById('refresh');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
          loadPlans();
          checkMonitoringStatus();
        });
      }
      const qInput = document.getElementById('q');
      if (qInput) qInput.addEventListener('input', loadPlans);
      const symbolFilter = document.getElementById('symbolFilter');
      if (symbolFilter) symbolFilter.addEventListener('change', loadPlans);
    }
    window.addEventListener('load', init);
  </script>
  </head>
  <body>
    <div class="nav">
      <a href="/">Home</a>
      <a href="/volatility-regime/monitor">Volatility Monitor</a>
      <a href="/notifications/view">Notifications</a>
      <a href="/alerts/view">ChatGPT Alerts</a>
      <a href="/auto-execution/view">Auto Execution Plans</a>
      <a href="/micro-scalp/view">Micro-Scalp Monitor</a>
      <a href="/dtms/status">DTMS Status</a>
      <a href="/dtms/actions">DTMS Actions</a>
      <a href="/docs">API Docs</a>
    </div>
    <h1>Auto Execution Trade Plans</h1>
    <div class="sub">Viewing trade plans from data/auto_execution.db • Total: <span id="count">0</span></div>
    
    <div class="monitoring-status">
      <span id="statusIndicator" class="status-indicator inactive"></span>
      <span id="statusText" class="status-text inactive">Checking...</span>
      <span id="statusDetails" class="status-details">• Loading status...</span>
    </div>
    
    <div class="tickers" style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px;">
      <div class="ticker-container" style="background: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #24324a;">
        <div class="ticker-label" style="color: #90c0ff; margin-bottom: 6px; font-weight: bold; font-size: 14px;">XAUUSD (Gold)</div>
        <div class="tradingview-widget-container">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
          {
          "symbol": "OANDA:XAUUSD",
          "width": "100%",
          "height": "250",
          "locale": "en",
          "dateRange": "1D",
          "colorTheme": "dark",
          "isTransparent": true,
          "autosize": true,
          "largeChartUrl": ""
          }
          </script>
        </div>
      </div>
      
      <div class="ticker-container" style="background: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #24324a;">
        <div class="ticker-label" style="color: #90c0ff; margin-bottom: 6px; font-weight: bold; font-size: 14px;">BTCUSD (Bitcoin)</div>
        <div class="tradingview-widget-container">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
          {
          "symbol": "BINANCE:BTCUSDT",
          "width": "100%",
          "height": "250",
          "locale": "en",
          "dateRange": "1D",
          "colorTheme": "dark",
          "isTransparent": true,
          "autosize": true,
          "largeChartUrl": ""
          }
          </script>
        </div>
      </div>
    </div>
    
    <div class="controls">
      <select id="symbolFilter">
        <option value="all">All Symbols</option>
      </select>
      <input id="q" type="text" placeholder="Search plans..." />
      <button id="refresh">Refresh</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>Plan ID</th>
          <th>Created At</th>
          <th>Symbol</th>
          <th>Direction</th>
          <th>Entry Price</th>
          <th>Stop Loss</th>
          <th>Take Profit</th>
          <th>Volume</th>
          <th>Strategy Type</th>
          <th>Status</th>
          <th>Conditions</th>
          <th>Notes</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </body>
</html>
        """
    )
    return HTMLResponse(content=html)

@app.get("/dtms/status", response_class=HTMLResponse)
async def view_dtms_status():
    """DTMS system status monitoring page."""
    html = (
        """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MoneyBot - DTMS Status</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #0b1220; color: #e6edf3; }
    h1 { margin-bottom: 8px; }
    .sub { color: #9fb0c3; margin-bottom: 16px; }
    .controls { margin-bottom: 16px; display: flex; gap: 8px; align-items: center; }
    button { padding: 8px 12px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; }
    button:hover { background: #213352; }
    .status-card { background: #111a2e; border: 1px solid #213352; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
    .status-card h3 { margin-top: 0; color: #e6edf3; }
    .status-indicator { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }
    .status-active { background: #90ee90; }
    .status-inactive { background: #ff9090; }
    .status-warning { background: #ffd700; }
    .nav { margin-bottom: 20px; }
    .nav a { color: #9fb0c3; text-decoration: none; margin-right: 20px; }
    .nav a:hover { color: #e6edf3; }
    .metric { display: flex; justify-content: space-between; margin: 8px 0; }
    .metric-label { color: #9fb0c3; }
    .metric-value { color: #e6edf3; font-weight: bold; }
    .trades-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; margin-top: 16px; }
    .trade-card { background: #111a2e; border: 1px solid #213352; border-radius: 8px; padding: 16px; }
    .trade-card h4 { margin-top: 0; color: #e6edf3; }
    .trade-ticket { font-family: monospace; background: #0f172a; padding: 4px 8px; border-radius: 4px; }
  </style>
  <script>
    async function loadDTMSStatus() {
      try {
        const res = await fetch('http://localhost:8001/dtms/status');
        const data = await res.json();
        
        if (data.success) {
          const status = data.dtms_status;
          
          // Update system status
          document.getElementById('system-status').innerHTML = `
            <span class="status-indicator ${status.system_active ? 'status-active' : 'status-inactive'}"></span>
            ${status.system_active ? 'Active' : 'Inactive'}
          `;
          
          // Update metrics
          document.getElementById('uptime').textContent = status.uptime || 'Unknown';
          document.getElementById('active-trades').textContent = status.active_trades || 0;
          document.getElementById('last-check').textContent = status.last_check || 'Unknown';
          
          // Update performance metrics
          const perf = status.performance || {};
          document.getElementById('fast-checks').textContent = perf.fast_checks_total || 0;
          document.getElementById('deep-checks').textContent = perf.deep_checks_total || 0;
          document.getElementById('actions-executed').textContent = perf.actions_executed || 0;
          document.getElementById('state-transitions').textContent = perf.state_transitions || 0;
          
          // Update trades by state
          const tradesByState = status.trades_by_state || {};
          const stateContainer = document.getElementById('trades-by-state');
          stateContainer.innerHTML = '';
          
          for (const [state, count] of Object.entries(tradesByState)) {
            const stateDiv = document.createElement('div');
            stateDiv.className = 'metric';
            stateDiv.innerHTML = `
              <span class="metric-label">${state}:</span>
              <span class="metric-value">${count}</span>
            `;
            stateContainer.appendChild(stateDiv);
          }
          
          // Load active trades
          await loadActiveTrades();
        } else {
          document.getElementById('system-status').innerHTML = '<span class="status-indicator status-warning"></span>Error loading status';
        }
      } catch (error) {
        console.error('Error loading DTMS status:', error);
        document.getElementById('system-status').innerHTML = '<span class="status-indicator status-inactive"></span>Connection Error';
      }
    }
    
    async function loadActiveTrades() {
      try {
        const res = await fetch('http://localhost:8001/dtms/engine');
        const data = await res.json();
        
        if (data.success) {
          const engine = data.engine_info;
          // Derive tickets from last_fast_check map (ticket -> timestamp)
          const tradeTickets = Object.keys(engine.last_fast_check || {});
          
          const tradesContainer = document.getElementById('active-trades');
          tradesContainer.innerHTML = '';
          
          for (const ticket of tradeTickets) {
            const tradeCard = document.createElement('div');
            tradeCard.className = 'trade-card';
            tradeCard.innerHTML = `
              <h4>Trade <span class="trade-ticket">${ticket}</span></h4>
              <div class="metric">
                <span class="metric-label">Last Fast Check:</span>
                <span class="metric-value">${new Date((engine.last_fast_check && engine.last_fast_check[ticket] ? engine.last_fast_check[ticket] : 0) * 1000).toLocaleTimeString()}</span>
              </div>
              <div class="metric">
                <span class="metric-label">Last Deep Check:</span>
                <span class="metric-value">${new Date((engine.last_deep_check && engine.last_deep_check[ticket] ? engine.last_deep_check[ticket] : 0) * 1000).toLocaleTimeString()}</span>
              </div>
              <div style="margin-top: 12px;">
                <a href="/dtms/trade/${ticket}" style="color: #90c0ff; text-decoration: none;">View Details →</a>
              </div>
            `;
            tradesContainer.appendChild(tradeCard);
          }
        }
      } catch (error) {
        console.error('Error loading active trades:', error);
      }
    }
    
    function init() {
      loadDTMSStatus();
      setInterval(loadDTMSStatus, 10000);
      document.getElementById('refresh').addEventListener('click', loadDTMSStatus);
    }
    window.addEventListener('load', init);
  </script>
  </head>
  <body>
    <div class="nav">
      <a href="/">Home</a>
      <a href="/volatility-regime/monitor">Volatility Monitor</a>
      <a href="/notifications/view">Notifications</a>
      <a href="/alerts/view">ChatGPT Alerts</a>
      <a href="/auto-execution/view">Auto Execution Plans</a>
      <a href="/micro-scalp/view">Micro-Scalp Monitor</a>
      <a href="/dtms/status">DTMS Status</a>
      <a href="/dtms/actions">DTMS Actions</a>
      <a href="/docs">API Docs</a>
    </div>
    <h1>DTMS System Status</h1>
    <div class="sub">Dynamic Trade Management System • Intelligent Exits Protection</div>
    <div class="controls">
      <button id="refresh">Refresh</button>
    </div>
    
    <div class="status-card">
      <h3>System Status</h3>
      <div class="metric">
        <span class="metric-label">Status:</span>
        <span class="metric-value" id="system-status">Loading...</span>
      </div>
      <div class="metric">
        <span class="metric-label">Uptime:</span>
        <span class="metric-value" id="uptime">Loading...</span>
      </div>
      <div class="metric">
        <span class="metric-label">Active Trades:</span>
        <span class="metric-value" id="active-trades">Loading...</span>
      </div>
      <div class="metric">
        <span class="metric-label">Last Check:</span>
        <span class="metric-value" id="last-check">Loading...</span>
      </div>
    </div>
    
    <div class="status-card">
      <h3>Performance Metrics</h3>
      <div class="metric">
        <span class="metric-label">Fast Checks Total:</span>
        <span class="metric-value" id="fast-checks">0</span>
      </div>
      <div class="metric">
        <span class="metric-label">Deep Checks Total:</span>
        <span class="metric-value" id="deep-checks">0</span>
      </div>
      <div class="metric">
        <span class="metric-label">Actions Executed:</span>
        <span class="metric-value" id="actions-executed">0</span>
      </div>
      <div class="metric">
        <span class="metric-label">State Transitions:</span>
        <span class="metric-value" id="state-transitions">0</span>
      </div>
    </div>
    
    <div class="status-card">
      <h3>Trades by State</h3>
      <div id="trades-by-state"></div>
    </div>
    
    <div class="status-card">
      <h3>Active Trades</h3>
      <div id="active-trades" class="trades-grid"></div>
    </div>
  </body>
</html>
        """
    )
    return HTMLResponse(content=html)

@app.get("/dtms/actions", response_class=HTMLResponse)
async def view_dtms_actions():
    """DTMS action history monitoring page."""
    html = (
        """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MoneyBot - DTMS Actions</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #0b1220; color: #e6edf3; }
    h1 { margin-bottom: 8px; }
    .sub { color: #9fb0c3; margin-bottom: 16px; }
    .controls { margin-bottom: 16px; display: flex; gap: 8px; align-items: center; }
    input[type="text"] { padding: 8px; border-radius: 6px; border: 1px solid #24324a; background: #0f172a; color: #e6edf3; }
    button { padding: 8px 12px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; }
    button:hover { background: #213352; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid #213352; padding: 10px; text-align: left; }
    th { background: #111a2e; position: sticky; top: 0; }
    .pill { padding: 2px 8px; border-radius: 999px; font-size: 12px; border: 1px solid #2b3b57; background: #0f172a; }
    .pill.breakeven { background: #1a3a1a; border-color: #2d5a2d; color: #90ee90; }
    .pill.partial { background: #1a1a3a; border-color: #2d2d5a; color: #90c0ff; }
    .pill.trailing { background: #3a1a1a; border-color: #5a2d2d; color: #ff9090; }
    .pill.exit { background: #2a2a2a; border-color: #4a4a4a; color: #cccccc; }
    .pill.hybridadjustment { background: #3a2a1a; border-color: #5a4a3a; color: #ffd700; }
    .pill.hybrid_adjustment { background: #3a2a1a; border-color: #5a4a3a; color: #ffd700; }
    .pill.ruleaddedv8 { background: #1a2a3a; border-color: #2a3a4a; color: #90c0ff; }
    .pill.ruleadded { background: #1a2a3a; border-color: #2a3a4a; color: #90c0ff; }
    .muted { color: #9fb0c3; font-size: 12px; }
    .wrap { white-space: pre-wrap; word-break: break-word; }
    .nav { margin-bottom: 20px; }
    .nav a { color: #9fb0c3; text-decoration: none; margin-right: 20px; }
    .nav a:hover { color: #e6edf3; }
    .action-details { background: #111a2e; border: 1px solid #213352; border-radius: 8px; padding: 16px; margin-top: 16px; }
    .action-details h3 { margin-top: 0; color: #e6edf3; }
  </style>
  <script>
    async function loadDTMSActions() {
      try {
        const tbody = document.getElementById('tbody');
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #9fb0c3;">Loading...</td></tr>';
        
        let errorMessages = [];
        
        // Fetch DTMS actions
        let dtmsActions = [];
        try {
          const dtmsRes = await fetch('http://localhost:8001/dtms/actions');
          if (!dtmsRes.ok) {
            throw new Error(`DTMS API returned ${dtmsRes.status}: ${dtmsRes.statusText}`);
          }
          const dtmsData = await dtmsRes.json();
          console.log('DTMS data:', dtmsData);
          if (dtmsData.success && dtmsData.action_history && dtmsData.action_history.length > 0) {
            dtmsActions = dtmsData.action_history.map(action => ({
              ...action,
              source: 'dtms',
              sortTime: new Date(action.timestamp || 0).getTime()
            }));
            console.log(`Loaded ${dtmsActions.length} DTMS actions`);
          } else {
            console.log('No DTMS actions found or empty response');
          }
        } catch (dtmsError) {
          console.error('Error loading DTMS actions:', dtmsError);
          errorMessages.push('DTMS: ' + dtmsError.message);
        }
        
        // Fetch Intelligent Exit actions
        let intelligentExitActions = [];
        try {
          const ieRes = await fetch('/mt5/intelligent_exits/recent?hours=168'); // Last 7 days
          if (!ieRes.ok) {
            throw new Error(`Intelligent Exits API returned ${ieRes.status}: ${ieRes.statusText}`);
          }
          const ieData = await ieRes.json();
          console.log('Intelligent Exits data:', ieData);
          if (ieData.ok && ieData.actions && Array.isArray(ieData.actions) && ieData.actions.length > 0) {
            intelligentExitActions = ieData.actions.map(action => {
              // Format intelligent exit action for display
              const timestamp = action.timestamp ? new Date(action.timestamp * 1000).toISOString().replace('T', ' ').substring(0, 19) : 'Unknown';
              let description = '';
              
              if (action.action_type === 'hybrid_adjustment') {
                description = `Hybrid ATR+VIX Adjustment`;
                if (action.old_sl && action.new_sl) {
                  description += ` - SL: ${parseFloat(action.old_sl).toFixed(5)} → ${parseFloat(action.new_sl).toFixed(5)}`;
                }
              } else if (action.action_type === 'breakeven') {
                description = `Breakeven - SL moved to entry`;
                if (action.old_sl && action.new_sl) {
                  description += ` (${parseFloat(action.old_sl).toFixed(5)} → ${parseFloat(action.new_sl).toFixed(5)})`;
                }
              } else if (action.action_type === 'partial_profit') {
                description = `Partial Profit`;
                if (action.volume_closed) {
                  description += ` - Closed ${parseFloat(action.volume_closed).toFixed(2)} lots`;
                }
                if (action.profit_realized) {
                  description += ` - Profit: $${parseFloat(action.profit_realized).toFixed(2)}`;
                }
              } else if (action.action_type === 'trailing_stop') {
                description = `Trailing Stop`;
                if (action.old_sl && action.new_sl) {
                  description += ` - SL: ${parseFloat(action.old_sl).toFixed(5)} → ${parseFloat(action.new_sl).toFixed(5)}`;
                }
              } else if (action.action_type === 'rule_added_v8' || action.action_type === 'rule_added') {
                description = `Intelligent Exit Rule Added`;
                // Try to parse details JSON if available
                let detailsObj = null;
                try {
                  if (typeof action.details === 'string') {
                    detailsObj = JSON.parse(action.details);
                  } else if (typeof action.details === 'object') {
                    detailsObj = action.details;
                  }
                } catch (e) {
                  // Details not JSON, ignore
                }
                
                if (detailsObj) {
                  const direction = detailsObj.direction ? detailsObj.direction.toUpperCase() : '';
                  const entryPrice = detailsObj.entry_price ? parseFloat(detailsObj.entry_price).toFixed(2) : '';
                  const breakevenPct = detailsObj.advanced_breakeven_pct || detailsObj.breakeven_profit_pct;
                  const partialPct = detailsObj.advanced_partial_pct || detailsObj.partial_profit_pct;
                  
                  if (direction && entryPrice) {
                    description += ` - ${direction} @ ${entryPrice}`;
                  }
                  
                  if (breakevenPct !== undefined && partialPct !== undefined) {
                    description += ` | Breakeven: ${parseFloat(breakevenPct).toFixed(0)}%, Partial: ${parseFloat(partialPct).toFixed(0)}%`;
                  }
                }
              } else {
                description = action.action_type ? action.action_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Unknown Action';
              }
              
              // Build details string
              let detailsParts = [];
              
              // For rule_added actions, show advanced reasoning or factors
              if (action.action_type === 'rule_added_v8' || action.action_type === 'rule_added') {
                let detailsObj = null;
                try {
                  if (typeof action.details === 'string') {
                    detailsObj = JSON.parse(action.details);
                  } else if (typeof action.details === 'object') {
                    detailsObj = action.details;
                  }
                } catch (e) {
                  // Details not JSON, ignore
                }
                
                if (detailsObj) {
                  if (detailsObj.advanced_reasoning) {
                    detailsParts.push(`Reasoning: ${detailsObj.advanced_reasoning}`);
                  }
                  if (detailsObj.advanced_factors && Array.isArray(detailsObj.advanced_factors) && detailsObj.advanced_factors.length > 0) {
                    detailsParts.push(`Factors: ${detailsObj.advanced_factors.join(', ')}`);
                  }
                  if (detailsObj.risk_reward_ratio !== null && detailsObj.risk_reward_ratio !== undefined) {
                    detailsParts.push(`R:R: ${parseFloat(detailsObj.risk_reward_ratio).toFixed(2)}`);
                  }
                  if (!detailsObj.advanced_reasoning && !detailsObj.advanced_factors) {
                    // Show basic info if no advanced data
                    if (detailsObj.initial_sl && detailsObj.initial_tp) {
                      detailsParts.push(`SL: ${parseFloat(detailsObj.initial_sl).toFixed(2)}, TP: ${parseFloat(detailsObj.initial_tp).toFixed(2)}`);
                    }
                  }
                }
              } else {
                // For other actions, show standard details
                if (action.atr_value !== null && action.atr_value !== undefined) detailsParts.push(`ATR: ${parseFloat(action.atr_value).toFixed(2)}`);
                if (action.vix_value !== null && action.vix_value !== undefined) detailsParts.push(`VIX: ${parseFloat(action.vix_value).toFixed(2)}`);
                if (action.r_achieved !== null && action.r_achieved !== undefined) detailsParts.push(`R: ${parseFloat(action.r_achieved).toFixed(2)}`);
                if (action.profit_pct !== null && action.profit_pct !== undefined) detailsParts.push(`Profit %: ${parseFloat(action.profit_pct).toFixed(1)}%`);
              }
              
              const details = detailsParts.length > 0 ? detailsParts.join(' | ') : 'No additional details';
              
              return {
                ticket: action.ticket,
                action_type: action.action_type ? action.action_type.toUpperCase() : 'UNKNOWN',
                description: description,
                timestamp: timestamp,
                status: action.success ? 'Success' : (action.success === false ? 'Failed' : 'Unknown'),
                details: details,
                source: 'intelligent_exit',
                sortTime: (action.timestamp || 0) * 1000
              };
            });
            console.log(`Loaded ${intelligentExitActions.length} Intelligent Exit actions`);
          } else {
            console.log('No Intelligent Exit actions found or empty response', ieData);
          }
        } catch (ieError) {
          console.error('Error loading Intelligent Exit actions:', ieError);
          errorMessages.push('Intelligent Exits: ' + ieError.message);
        }
        
        // Combine and sort by timestamp (newest first)
        const allActions = [...dtmsActions, ...intelligentExitActions].sort((a, b) => (b.sortTime || 0) - (a.sortTime || 0));
        
        tbody.innerHTML = '';
        
        if (allActions.length > 0) {
          allActions.forEach(action => {
            const tr = document.createElement('tr');
            const actionType = action.action_type || 'unknown';
            const actionClass = actionType.toLowerCase().replace('_', '').replace(/\s+/g, '');
            
            tr.innerHTML = `
              <td><div class="wrap">${action.ticket || 'N/A'}</div></td>
              <td><span class="pill ${actionClass}">${actionType}</span></td>
              <td><div class="wrap">${action.description || 'No description'}</div></td>
              <td><div class="wrap">${action.timestamp || 'Unknown'}</div></td>
              <td><div class="wrap">${action.status || 'Unknown'}</div></td>
              <td><div class="wrap">${action.details || 'No details'}</div></td>
            `;
            tbody.appendChild(tr);
          });
          document.getElementById('count').textContent = allActions.length;
        } else {
          let message = 'No actions found';
          if (errorMessages.length > 0) {
            message += ' (Errors: ' + errorMessages.join(', ') + ')';
          }
          tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #9fb0c3;">' + message + '</td></tr>';
          document.getElementById('count').textContent = '0';
        }
      } catch (error) {
        console.error('Error loading actions:', error);
        const tbody = document.getElementById('tbody');
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #ff9090;">Error loading actions: ' + error.message + '</td></tr>';
        document.getElementById('count').textContent = '0';
      }
    }
    
    function init() {
      loadDTMSActions();
      setInterval(loadDTMSActions, 10000);
      document.getElementById('refresh').addEventListener('click', loadDTMSActions);
    }
    window.addEventListener('load', init);
  </script>
  </head>
  <body>
    <div class="nav">
      <a href="/">Home</a>
      <a href="/volatility-regime/monitor">Volatility Monitor</a>
      <a href="/notifications/view">Notifications</a>
      <a href="/alerts/view">ChatGPT Alerts</a>
      <a href="/auto-execution/view">Auto Execution Plans</a>
      <a href="/micro-scalp/view">Micro-Scalp Monitor</a>
      <a href="/dtms/status">DTMS Status</a>
      <a href="/dtms/actions">DTMS Actions</a>
      <a href="/docs">API Docs</a>
    </div>
    <h1>DTMS Action History</h1>
    <div class="sub">Intelligent Exits Actions & Trade Management Events • Total: <span id="count">0</span></div>
    <div class="controls">
      <button id="refresh">Refresh</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>Ticket</th>
          <th>Action Type</th>
          <th>Description</th>
          <th>Timestamp</th>
          <th>Status</th>
          <th>Details</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
    
    <div class="action-details">
      <h3>Action Types</h3>
      <p><span class="pill ruleaddedv8">RULE_ADDED_V8</span> - Intelligent exit rule initialized for a new trade</p>
      <p><span class="pill breakeven">BREAKEVEN</span> - Move stop loss to entry price to protect capital</p>
      <p><span class="pill partial">PARTIAL_PROFIT</span> - Take partial profits at target levels</p>
      <p><span class="pill trailing">TRAILING_STOP</span> - Trail stop loss to maximize profit capture</p>
      <p><span class="pill hybridadjustment">HYBRID_ADJUSTMENT</span> - Adjust stop loss based on ATR+VIX market conditions</p>
      <p><span class="pill exit">EXIT</span> - Close position based on exit conditions</p>
    </div>
  </body>
</html>
        """
    )
    return HTMLResponse(content=html)

@app.get("/dtms/trade/{ticket}", response_class=HTMLResponse)
async def view_dtms_trade_details(ticket: int):
    """DTMS trade details page for a specific ticket."""
    html = (
        """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MoneyBot - DTMS Trade Details</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #0b1220; color: #e6edf3; }
    h1 { margin-bottom: 8px; }
    .sub { color: #9fb0c3; margin-bottom: 16px; }
    .controls { margin-bottom: 16px; display: flex; gap: 8px; align-items: center; }
    button { padding: 8px 12px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; }
    button:hover { background: #213352; }
    .status-card { background: #111a2e; border: 1px solid #213352; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
    .status-card h3 { margin-top: 0; color: #e6edf3; }
    .status-indicator { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }
    .status-active { background: #90ee90; }
    .status-inactive { background: #ff9090; }
    .status-warning { background: #ffd700; }
    .nav { margin-bottom: 20px; }
    .nav a { color: #9fb0c3; text-decoration: none; margin-right: 20px; }
    .nav a:hover { color: #e6edf3; }
    .metric { display: flex; justify-content: space-between; margin: 8px 0; }
    .metric-label { color: #9fb0c3; }
    .metric-value { color: #e6edf3; font-weight: bold; }
    .intelligent-exits { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin-top: 16px; }
    .exit-card { background: #111a2e; border: 1px solid #213352; border-radius: 8px; padding: 16px; }
    .exit-card h4 { margin-top: 0; color: #e6edf3; }
    .exit-status { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .exit-active { background: #1a3a1a; color: #90ee90; }
    .exit-inactive { background: #3a1a1a; color: #ff9090; }
  </style>
  <script>
    async function loadTradeDetails() {
      try {
        const ticket = window.location.pathname.split('/').pop();
        const res = await fetch(`http://localhost:8001/dtms/trade/${ticket}`);
        const data = await res.json();
        
        if (data.success) {
          const trade = data.trade_info;
          
          // Update trade info
          document.getElementById('ticket').textContent = ticket;
          document.getElementById('symbol').textContent = trade.symbol || 'Unknown';
          document.getElementById('type').textContent = trade.type || 'Unknown';
          document.getElementById('volume').textContent = trade.volume || 'Unknown';
          document.getElementById('open-price').textContent = trade.open_price || 'Unknown';
          document.getElementById('current-price').textContent = trade.current_price || 'Unknown';
          document.getElementById('profit').textContent = trade.profit || 'Unknown';
          document.getElementById('dtms-state').textContent = trade.state || 'Unknown';
          
          // Update protection status
          const protectionStatus = trade.protection_active ? 'Active' : 'Inactive';
          const protectionClass = trade.protection_active ? 'status-active' : 'status-inactive';
          document.getElementById('protection-status').innerHTML = `
            <span class="status-indicator ${protectionClass}"></span>
            ${protectionStatus}
          `;
          
          // Update intelligent exits
          const ie = trade.intelligent_exits || {};
          document.getElementById('breakeven-status').innerHTML = `
            <span class="exit-status ${ie.breakeven_triggered ? 'exit-active' : 'exit-inactive'}">
              ${ie.breakeven_triggered ? 'TRIGGERED' : 'PENDING'}
            </span>
          `;
          document.getElementById('partial-profit-status').innerHTML = `
            <span class="exit-status ${ie.partial_profit_triggered ? 'exit-active' : 'exit-inactive'}">
              ${ie.partial_profit_triggered ? 'TRIGGERED' : 'PENDING'}
            </span>
          `;
          document.getElementById('trailing-stop-status').innerHTML = `
            <span class="exit-status ${ie.trailing_stop_active ? 'exit-active' : 'exit-inactive'}">
              ${ie.trailing_stop_active ? 'ACTIVE' : 'INACTIVE'}
            </span>
          `;
        } else {
          document.getElementById('ticket').textContent = 'Error loading trade details';
        }
      } catch (error) {
        console.error('Error loading trade details:', error);
        document.getElementById('ticket').textContent = 'Connection Error';
      }
    }
    
    function init() {
      loadTradeDetails();
      setInterval(loadTradeDetails, 10000);
      document.getElementById('refresh').addEventListener('click', loadTradeDetails);
    }
    window.addEventListener('load', init);
  </script>
  </head>
  <body>
    <div class="nav">
      <a href="/">Home</a>
      <a href="/volatility-regime/monitor">Volatility Monitor</a>
      <a href="/notifications/view">Notifications</a>
      <a href="/alerts/view">ChatGPT Alerts</a>
      <a href="/auto-execution/view">Auto Execution Plans</a>
      <a href="/micro-scalp/view">Micro-Scalp Monitor</a>
      <a href="/dtms/status">DTMS Status</a>
      <a href="/dtms/actions">DTMS Actions</a>
      <a href="/docs">API Docs</a>
    </div>
    <h1>DTMS Trade Details</h1>
    <div class="sub">Trade Ticket: <span id="ticket">Loading...</span></div>
    <div class="controls">
      <a href="/dtms/status" style="color: #9fb0c3; text-decoration: none; padding: 8px 12px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; display: inline-block;">← Back to DTMS Status</a>
      <button id="refresh">Refresh</button>
    </div>
    
    <div class="status-card">
      <h3>Trade Information</h3>
      <div class="metric">
        <span class="metric-label">Symbol:</span>
        <span class="metric-value" id="symbol">Loading...</span>
      </div>
      <div class="metric">
        <span class="metric-label">Type:</span>
        <span class="metric-value" id="type">Loading...</span>
      </div>
      <div class="metric">
        <span class="metric-label">Volume:</span>
        <span class="metric-value" id="volume">Loading...</span>
      </div>
      <div class="metric">
        <span class="metric-label">Open Price:</span>
        <span class="metric-value" id="open-price">Loading...</span>
      </div>
      <div class="metric">
        <span class="metric-label">Current Price:</span>
        <span class="metric-value" id="current-price">Loading...</span>
      </div>
      <div class="metric">
        <span class="metric-label">Profit:</span>
        <span class="metric-value" id="profit">Loading...</span>
      </div>
      <div class="metric">
        <span class="metric-label">DTMS State:</span>
        <span class="metric-value" id="dtms-state">Loading...</span>
      </div>
      <div class="metric">
        <span class="metric-label">Protection:</span>
        <span class="metric-value" id="protection-status">Loading...</span>
      </div>
    </div>
    
    <div class="status-card">
      <h3>Intelligent Exits Status</h3>
      <div class="intelligent-exits">
        <div class="exit-card">
          <h4>Breakeven Protection</h4>
          <div id="breakeven-status">Loading...</div>
          <p style="margin-top: 8px; color: #9fb0c3; font-size: 12px;">
            Moves stop loss to entry price when trade reaches breakeven
          </p>
        </div>
        <div class="exit-card">
          <h4>Partial Profit</h4>
          <div id="partial-profit-status">Loading...</div>
          <p style="margin-top: 8px; color: #9fb0c3; font-size: 12px;">
            Takes partial profits at predetermined target levels
          </p>
        </div>
        <div class="exit-card">
          <h4>Trailing Stop</h4>
          <div id="trailing-stop-status">Loading...</div>
          <p style="margin-top: 8px; color: #9fb0c3; font-size: 12px;">
            Trails stop loss to maximize profit capture
          </p>
        </div>
      </div>
    </div>
  </body>
</html>
        """
    )
    return HTMLResponse(content=html)

# ============================================================================
# VOLATILITY REGIME MONITORING ENDPOINTS
# ============================================================================

@app.get("/volatility-regime/monitor", response_class=HTMLResponse)
async def view_volatility_regime_monitor():
    """Volatility regime real-time monitoring dashboard"""
    html = (
        """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MoneyBot - Volatility Regime Monitor</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #0b1220; color: #e6edf3; }
    h1 { margin-bottom: 8px; }
    .sub { color: #9fb0c3; margin-bottom: 16px; }
    .controls { margin-bottom: 16px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    input[type="text"] { padding: 8px; border-radius: 6px; border: 1px solid #24324a; background: #0f172a; color: #e6edf3; }
    button { padding: 8px 12px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; }
    button:hover { background: #213352; }
    .nav { margin-bottom: 20px; }
    .nav a { color: #9fb0c3; text-decoration: none; margin-right: 20px; }
    .nav a:hover { color: #e6edf3; }
    .regime-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 16px; margin-top: 16px; }
    .regime-card { background: #111a2e; border: 1px solid #213352; border-radius: 8px; padding: 16px; min-width: 400px; }
    .regime-card h3 { margin-top: 0; color: #e6edf3; font-size: 16px; }
    .regime-card h4 { font-size: 13px; margin-bottom: 8px; }
    .regime-badge { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 14px; font-weight: bold; margin-bottom: 12px; }
    .regime-stable { background: #1a3a1a; border: 1px solid #2d5a2d; color: #90ee90; }
    .regime-transitional { background: #3a3a1a; border: 1px solid #5a5a2d; color: #ffd700; }
    .regime-volatile { background: #3a1a1a; border: 1px solid #5a2d2d; color: #ff9090; }
    .metric { display: flex; justify-content: space-between; margin: 8px 0; }
    .metric-label { color: #9fb0c3; }
    .metric-value { color: #e6edf3; font-weight: bold; }
    .confidence-bar { width: 100%; height: 8px; background: #0f172a; border-radius: 4px; overflow: hidden; margin-top: 4px; }
    .confidence-fill { height: 100%; transition: width 0.3s; }
    .confidence-high { background: #90ee90; }
    .confidence-medium { background: #ffd700; }
    .confidence-low { background: #ff9090; }
    .events-table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 11px; }
    .events-table th, .events-table td { border-bottom: 1px solid #213352; padding: 6px 4px; text-align: left; }
    .events-table th { background: #111a2e; position: sticky; top: 0; font-size: 10px; }
    .events-table td { font-size: 10px; }
    .events-table .regime-badge { font-size: 9px; padding: 1px 4px; }
    .muted { color: #9fb0c3; font-size: 12px; }
    .wrap { white-space: pre-wrap; word-break: break-word; }
    .timestamp-cell { font-size: 9px; white-space: nowrap; }
    .metric-value { font-size: 13px; }
  </style>
  <script>
    const symbols = ['BTCUSDc', 'XAUUSDc', 'EURUSDc', 'GBPUSDc', 'USDJPYc'];
    let updateInterval = null;
    
    async function loadRegimeData(symbol) {
      try {
        const res = await fetch(`/volatility-regime/status/${symbol}`);
        const data = await res.json();
        return data;
      } catch (error) {
        console.error(`Error loading regime for ${symbol}:`, error);
        return null;
      }
    }
    
    async function loadRegimeEvents(symbol, limit = 10) {
      try {
        const res = await fetch(`/volatility-regime/events/${symbol}?limit=${limit}`);
        const data = await res.json();
        return data.events || [];
      } catch (error) {
        console.error(`Error loading events for ${symbol}:`, error);
        return [];
      }
    }
    
    function updateRegimeCard(symbol, data) {
      const card = document.getElementById(`card-${symbol}`);
      if (!card || !data || !data.success) return;
      
      const regime = data.regime_data || {};
      const regimeType = regime.regime || 'STABLE';
      const confidence = regime.confidence || 0;
      
      // Update badge
      const badge = card.querySelector('.regime-badge');
      badge.className = `regime-badge regime-${regimeType.toLowerCase()}`;
      badge.textContent = regimeType;
      
      // Update metrics
      card.querySelector('.confidence-value').textContent = `${confidence.toFixed(1)}%`;
      card.querySelector('.atr-ratio').textContent = (regime.atr_ratio || 0).toFixed(2);
      card.querySelector('.adx-value').textContent = (regime.adx_composite || 0).toFixed(1);
      
      // Update confidence bar
      const confidenceFill = card.querySelector('.confidence-fill');
      confidenceFill.style.width = `${confidence}%`;
      confidenceFill.className = `confidence-fill ${
        confidence >= 80 ? 'confidence-high' : 
        confidence >= 60 ? 'confidence-medium' : 'confidence-low'
      }`;
      
      // Update timestamp
      card.querySelector('.last-update').textContent = new Date().toLocaleTimeString();
    }
    
    function updateEventsTable(symbol, events) {
      const tbody = document.getElementById(`events-${symbol}`);
      if (!tbody) return;
      
      tbody.innerHTML = '';
      if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #9fb0c3;">No events found</td></tr>';
        return;
      }
      
      events.forEach(event => {
        const tr = document.createElement('tr');
        const date = new Date(event.timestamp);
        const timeStr = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        tr.innerHTML = `
          <td><span class="regime-badge regime-${event.new_regime.toLowerCase()}">${event.new_regime}</span></td>
          <td>${event.confidence ? event.confidence.toFixed(0) + '%' : 'N/A'}</td>
          <td>${event.atr_ratio ? event.atr_ratio.toFixed(2) : 'N/A'}</td>
          <td class="timestamp-cell">${dateStr}<br>${timeStr}</td>
          <td style="font-size: 9px;">${(event.transition || 'N/A').substring(0, 20)}</td>
        `;
        tbody.appendChild(tr);
      });
    }
    
    async function updateAllSymbols() {
      for (const symbol of symbols) {
        const regimeData = await loadRegimeData(symbol);
        updateRegimeCard(symbol, regimeData);
        
        const events = await loadRegimeEvents(symbol, 5);
        updateEventsTable(symbol, events);
      }
    }
    
    function createRegimeCards() {
      const grid = document.getElementById('regime-grid');
      if (!grid) return;
      
      symbols.forEach(symbol => {
        const card = document.createElement('div');
        card.className = 'regime-card';
        card.id = 'card-' + symbol;
        card.innerHTML = 
          '<h3>' + symbol + '</h3>' +
          '<div class="regime-badge regime-stable">STABLE</div>' +
          '<div class="metric">' +
            '<span class="metric-label">Confidence:</span>' +
            '<span class="metric-value confidence-value">0.0%</span>' +
          '</div>' +
          '<div class="confidence-bar">' +
            '<div class="confidence-fill confidence-low" style="width: 0%"></div>' +
          '</div>' +
          '<div class="metric">' +
            '<span class="metric-label">ATR Ratio:</span>' +
            '<span class="metric-value atr-ratio">0.00</span>' +
          '</div>' +
          '<div class="metric">' +
            '<span class="metric-label">ADX Composite:</span>' +
            '<span class="metric-value adx-value">0.0</span>' +
          '</div>' +
          '<div class="metric">' +
            '<span class="metric-label">Last Update:</span>' +
            '<span class="metric-value last-update muted">--:--:--</span>' +
          '</div>' +
          '<h4 style="margin-top: 16px; margin-bottom: 8px; color: #9fb0c3;">Recent Events</h4>' +
          '<div style="overflow-x: auto; max-height: 200px; overflow-y: auto;">' +
            '<table class="events-table">' +
              '<thead>' +
                '<tr>' +
                  '<th style="width: 80px;">Regime</th>' +
                  '<th style="width: 60px;">Conf</th>' +
                  '<th style="width: 60px;">ATR</th>' +
                  '<th style="width: 100px;">Time</th>' +
                  '<th style="width: 80px;">Type</th>' +
                '</tr>' +
              '</thead>' +
              '<tbody id="events-' + symbol + '">' +
                '<tr><td colspan="5" style="text-align: center; color: #9fb0c3;">Loading...</td></tr>' +
              '</tbody>' +
            '</table>' +
          '</div>';
        grid.appendChild(card);
      });
    }
    
    function init() {
      // Create cards first
      createRegimeCards();
      
      // Then start updating data
      updateAllSymbols();
      updateInterval = setInterval(updateAllSymbols, 30000); // Update every 30 seconds
      
      document.getElementById('refresh').addEventListener('click', () => {
        updateAllSymbols();
      });
      
      document.getElementById('auto-refresh').addEventListener('change', (e) => {
        if (e.target.checked) {
          if (!updateInterval) {
            updateInterval = setInterval(updateAllSymbols, 30000);
          }
        } else {
          if (updateInterval) {
            clearInterval(updateInterval);
            updateInterval = null;
          }
        }
      });
    }
    
    window.addEventListener('load', init);
  </script>
</head>
<body>
  <div class="nav">
    <a href="/">Home</a>
    <a href="/volatility-regime/monitor">Volatility Monitor</a>
    <a href="/notifications/view">Notifications</a>
    <a href="/alerts/view">ChatGPT Alerts</a>
    <a href="/auto-execution/view">Auto Execution Plans</a>
    <a href="/dtms/status">DTMS Status</a>
    <a href="/dtms/actions">DTMS Actions</a>
    <a href="/docs">API Docs</a>
  </div>
  <h1>Volatility Regime Monitor</h1>
  <div class="sub">Real-time volatility regime detection and monitoring • Updates every 30 seconds</div>
  <div class="controls">
    <button id="refresh">Refresh Now</button>
    <label><input type="checkbox" id="auto-refresh" checked /> Auto-refresh (30s)</label>
  </div>
  
  <div class="regime-grid" id="regime-grid">
    <!-- Cards will be populated by JavaScript -->
  </div>
</body>
</html>
        """
    )
    return HTMLResponse(content=html)

@app.get("/volatility-regime/status/{symbol}")
async def get_volatility_regime_status(symbol: str) -> Dict[str, Any]:
    """Get current volatility regime status for a symbol"""
    try:
        if not mt5_service or not indicator_bridge:
            raise HTTPException(status_code=500, detail="Services not initialized")
        
        # Normalize symbol (strip any existing 'c'/'C' suffix, then add lowercase 'c')
        symbol = symbol.upper().rstrip('cC')
        symbol = symbol + 'c'
        
        if not mt5_service.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        mt5_service.ensure_symbol(symbol)
        
        # Get timeframe data
        timeframe_data = indicator_bridge.get_multi(symbol)
        
        # Detect regime
        from infra.volatility_regime_detector import RegimeDetector
        detector = RegimeDetector()
        regime_data = detector.detect_regime(symbol, timeframe_data)
        
        return {
            "success": True,
            "symbol": symbol,
            "regime_data": regime_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting regime status for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/volatility-regime/events/{symbol}")
async def get_volatility_regime_events(
    symbol: str,
    limit: int = 50,
    hours: int = 24
) -> Dict[str, Any]:
    """Get volatility regime events for a symbol"""
    try:
        import sqlite3
        from pathlib import Path
        from datetime import datetime, timedelta
        
        db_path = Path("data/volatility_regime_events.sqlite")
        if not db_path.exists():
            return {"success": True, "events": [], "count": 0}
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Normalize symbol (strip any existing 'c'/'C' suffix, then add lowercase 'c')
        symbol = symbol.upper().rstrip('cC')
        symbol = symbol + 'c'
        
        # Query events within time window
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute("""
            SELECT * FROM regime_events
            WHERE symbol = ? AND timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (symbol, cutoff_time, limit))
        
        rows = cursor.fetchall()
        events = []
        for row in rows:
            events.append({
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "timestamp": row["timestamp"],
                "symbol": row["symbol"],
                "old_regime": row["old_regime"],
                "new_regime": row["new_regime"],
                "confidence": row["confidence"],
                "atr_ratio": row["atr_ratio"],
                "bb_width_ratio": row["bb_width_ratio"],
                "adx": row["adx"],
                "transition": row["transition"]
            })
        
        conn.close()
        
        return {
            "success": True,
            "symbol": symbol,
            "events": events,
            "count": len(events),
            "hours": hours
        }
        
    except Exception as e:
        logger.error(f"Error getting regime events for {symbol}: {e}", exc_info=True)
        return {"success": False, "events": [], "count": 0, "error": str(e)}

# ============================================================================
# ENHANCED NOTIFICATIONS ENDPOINTS
# ============================================================================

@app.get("/notifications/view", response_class=HTMLResponse)
async def view_notifications_management():
    """Enhanced notifications management dashboard"""
    html = (
        """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MoneyBot - Notifications Management</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #0b1220; color: #e6edf3; }
    h1 { margin-bottom: 8px; }
    .sub { color: #9fb0c3; margin-bottom: 16px; }
    .controls { margin-bottom: 16px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    button { padding: 8px 12px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; }
    button:hover { background: #213352; }
    button.success { background: #1a3a1a; border-color: #2d5a2d; }
    button.danger { background: #3a1a1a; border-color: #5a2d2d; }
    .nav { margin-bottom: 20px; }
    .nav a { color: #9fb0c3; text-decoration: none; margin-right: 20px; }
    .nav a:hover { color: #e6edf3; }
    .status-card { background: #111a2e; border: 1px solid #213352; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
    .status-card h3 { margin-top: 0; color: #e6edf3; }
    .status-indicator { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }
    .status-active { background: #90ee90; }
    .status-inactive { background: #ff9090; }
    .metric { display: flex; justify-content: space-between; margin: 8px 0; }
    .metric-label { color: #9fb0c3; }
    .metric-value { color: #e6edf3; font-weight: bold; }
    .test-section { margin-top: 24px; }
    .test-section h3 { color: #e6edf3; }
    .test-buttons { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
    .muted { color: #9fb0c3; font-size: 12px; }
  </style>
  <script>
    async function loadNotificationStatus() {
      try {
        const res = await fetch('/notifications/status');
        const data = await res.json();
        
        if (data.success) {
          // Update Discord status
          const discordStatus = data.discord || {};
          document.getElementById('discord-enabled').innerHTML = discordStatus.enabled 
            ? '<span class="status-indicator status-active"></span>Enabled'
            : '<span class="status-indicator status-inactive"></span>Disabled';
          document.getElementById('discord-webhook').textContent = discordStatus.webhook_configured ? 'Yes' : 'No';
          document.getElementById('discord-signals').textContent = discordStatus.signals_webhook_configured ? 'Yes' : 'No';
          
          // Update Telegram status
          const telegramStatus = data.telegram || {};
          document.getElementById('telegram-enabled').innerHTML = telegramStatus.enabled
            ? '<span class="status-indicator status-active"></span>Enabled'
            : '<span class="status-indicator status-inactive"></span>Disabled';
          document.getElementById('telegram-bot').textContent = telegramStatus.bot_configured ? 'Yes' : 'No';
        }
      } catch (error) {
        console.error('Error loading notification status:', error);
      }
    }
    
    async function testNotification(channel, type) {
      try {
        const res = await fetch(`/notifications/test/${channel}/${type}`, { method: 'POST' });
        const data = await res.json();
        
        if (data.success) {
          alert(`Test notification sent successfully to ${channel}!`);
        } else {
          alert(`Failed to send test notification: ${data.error || 'Unknown error'}`);
        }
      } catch (error) {
        alert(`Error: ${error.message}`);
      }
    }
    
    async function sendVolatilityAlert() {
      try {
        const symbol = prompt('Enter symbol (e.g., BTCUSDc):', 'BTCUSDc');
        const regime = prompt('Enter regime (STABLE/TRANSITIONAL/VOLATILE):', 'VOLATILE');
        const confidence = prompt('Enter confidence (0-100):', '85');
        
        if (!symbol || !regime || !confidence) return;
        
        const res = await fetch('/notifications/volatility-alert', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ symbol, regime, confidence: parseFloat(confidence) })
        });
        
        const data = await res.json();
        if (data.success) {
          alert('Volatility regime alert sent successfully!');
        } else {
          alert(`Failed: ${data.error || 'Unknown error'}`);
        }
      } catch (error) {
        alert(`Error: ${error.message}`);
      }
    }
    
    function init() {
      loadNotificationStatus();
      setInterval(loadNotificationStatus, 30000); // Refresh every 30 seconds
    }
    
    window.addEventListener('load', init);
  </script>
</head>
<body>
  <div class="nav">
    <a href="/">Home</a>
    <a href="/volatility-regime/monitor">Volatility Monitor</a>
    <a href="/notifications/view">Notifications</a>
    <a href="/alerts/view">ChatGPT Alerts</a>
    <a href="/auto-execution/view">Auto Execution Plans</a>
    <a href="/dtms/status">DTMS Status</a>
    <a href="/dtms/actions">DTMS Actions</a>
    <a href="/docs">API Docs</a>
  </div>
  <h1>Notifications Management</h1>
  <div class="sub">Manage Discord and Telegram notification channels • Test and monitor notification delivery</div>
  
  <div class="status-card">
    <h3>Discord Notifications</h3>
    <div class="metric">
      <span class="metric-label">Status:</span>
      <span class="metric-value" id="discord-enabled">Loading...</span>
    </div>
    <div class="metric">
      <span class="metric-label">Private Webhook:</span>
      <span class="metric-value" id="discord-webhook">Loading...</span>
    </div>
    <div class="metric">
      <span class="metric-label">Signals Webhook:</span>
      <span class="metric-value" id="discord-signals">Loading...</span>
    </div>
    <div class="test-buttons">
      <button onclick="testNotification('discord', 'system')">Test System Alert</button>
      <button onclick="testNotification('discord', 'trade')">Test Trade Alert</button>
      <button onclick="testNotification('discord', 'volatility')">Test Volatility Alert</button>
    </div>
  </div>
  
  <div class="status-card">
    <h3>Telegram Notifications</h3>
    <div class="metric">
      <span class="metric-label">Status:</span>
      <span class="metric-value" id="telegram-enabled">Loading...</span>
    </div>
    <div class="metric">
      <span class="metric-label">Bot Configured:</span>
      <span class="metric-value" id="telegram-bot">Loading...</span>
    </div>
    <div class="test-buttons">
      <button onclick="testNotification('telegram', 'system')">Test System Alert</button>
      <button onclick="testNotification('telegram', 'trade')">Test Trade Alert</button>
    </div>
  </div>
  
  <div class="test-section">
    <h3>Volatility Regime Alerts</h3>
    <p class="muted">Send a test volatility regime change alert to all configured channels.</p>
    <button class="success" onclick="sendVolatilityAlert()">Send Volatility Alert</button>
  </div>
</body>
</html>
        """
    )
    return HTMLResponse(content=html)

@app.get("/notifications/status")
async def get_notifications_status() -> Dict[str, Any]:
    """Get notification channel status"""
    try:
        import os
        
        # Check Discord
        discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
        discord_signals_webhook = os.getenv("DISCORD_SIGNALS_WEBHOOK_URL")
        
        # Check Telegram
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        
        return {
            "success": True,
            "discord": {
                "enabled": bool(discord_webhook),
                "webhook_configured": bool(discord_webhook),
                "signals_webhook_configured": bool(discord_signals_webhook)
            },
            "telegram": {
                "enabled": bool(telegram_token),
                "bot_configured": bool(telegram_token)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting notification status: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@app.post("/notifications/test/{channel}/{alert_type}")
async def test_notification(channel: str, alert_type: str) -> Dict[str, Any]:
    """Test notification delivery"""
    try:
        if channel == "discord":
            from discord_notifications import DiscordNotifier
            notifier = DiscordNotifier()
            
            if not notifier.enabled:
                return {"success": False, "error": "Discord not enabled"}
            
            if alert_type == "system":
                success = notifier.send_system_alert("TEST", "This is a test system alert from MoneyBot API")
            elif alert_type == "trade":
                success = notifier.send_trade_alert("TEST", "BUY", "100.00", "0.01", "TEST")
            elif alert_type == "volatility":
                success = notifier.send_message(
                    "**Volatility Regime Alert**\n\nSymbol: TEST\nRegime: VOLATILE\nConfidence: 85%\n\nThis is a test volatility alert.",
                    "VOLATILITY_ALERT",
                    0xff9900
                )
            else:
                return {"success": False, "error": "Invalid alert type"}
            
            return {"success": success, "channel": "discord", "alert_type": alert_type}
            
        elif channel == "telegram":
            # Telegram testing would require the bot instance
            return {"success": False, "error": "Telegram testing requires bot instance (not available in API)"}
        else:
            return {"success": False, "error": "Invalid channel"}
            
    except Exception as e:
        logger.error(f"Error testing notification: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@app.post("/notifications/volatility-alert")
async def send_volatility_alert(request: Request) -> Dict[str, Any]:
    """Send volatility regime change alert"""
    try:
        body = await request.json()
        symbol = body.get("symbol", "UNKNOWN")
        regime = body.get("regime", "STABLE")
        confidence = body.get("confidence", 0.0)
        
        # Send to Discord
        try:
            from discord_notifications import DiscordNotifier
            notifier = DiscordNotifier()
            
            if notifier.enabled:
                # Determine color based on regime
                if regime == "VOLATILE":
                    color = 0xff0000  # Red
                elif regime == "TRANSITIONAL":
                    color = 0xff9900  # Orange
                else:  # STABLE
                    color = 0x00ff00  # Green
                
                message = f"""**Volatility Regime Alert**

**Symbol:** {symbol}
**Regime:** {regime}
**Confidence:** {confidence:.1f}%

**Action Required:**
- Monitor price action closely
- Adjust position sizing if needed
- Review stop loss levels
- Consider strategy adjustments

**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                
                success = notifier.send_message(
                    message,
                    "VOLATILITY_REGIME_ALERT",
                    color
                )
                
                if success:
                    logger.info(f"Volatility regime alert sent to Discord: {symbol} {regime}")
        except Exception as e:
            logger.warning(f"Failed to send Discord volatility alert: {e}")
        
        return {
            "success": True,
            "symbol": symbol,
            "regime": regime,
            "confidence": confidence,
            "message": "Volatility alert sent to configured channels"
        }
        
    except Exception as e:
        logger.error(f"Error sending volatility alert: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

# ============================================================================
# AUTO EXECUTION ENDPOINTS
# ============================================================================

@app.get("/auto-execution/status")
async def get_auto_execution_status(include_all: bool = False):
    """Get status of auto execution trade plans (default: pending only)"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        result = auto_execution.get_plan_status(include_all_statuses=include_all)
        return result
    except Exception as e:
        logger.error(f"Error getting auto execution status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auto-execution/cancel-plan/{plan_id}")
async def cancel_auto_execution_plan(plan_id: str):
    """Cancel an auto execution trade plan"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        result = auto_execution.cancel_plan(plan_id)
        return result
    except Exception as e:
        logger.error(f"Error cancelling plan {plan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

class RangeScalpPlanRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float = 0.01
    min_confluence: int = 80
    price_tolerance: Optional[float] = None
    expires_hours: int = 8
    notes: Optional[str] = None

@app.post("/auto-execution/create-range-scalp-plan")
async def create_range_scalp_plan(request: RangeScalpPlanRequest):
    """Create a range scalping auto-execution plan"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        result = auto_execution.create_range_scalp_plan(
            symbol=request.symbol,
            direction=request.direction,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            min_confluence=request.min_confluence,
            price_tolerance=request.price_tolerance,
            expires_hours=request.expires_hours,
            notes=request.notes
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error creating range scalp plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create range scalp plan: {str(e)}")

@app.get("/auto-execution/system-status")
async def get_auto_execution_system_status():
    """Get auto execution system status"""
    try:
        from auto_execution_system import get_auto_execution_system
        auto_system = get_auto_execution_system()
        status = auto_system.get_status()
        return {
            "success": True,
            "system_status": status
        }
    except Exception as e:
        logger.error(f"Error getting system status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auto-execution/effectiveness")
async def get_plan_effectiveness(days: int = 30):
    """Get effectiveness report for auto-execution plans"""
    try:
        from infra.plan_effectiveness_tracker import PlanEffectivenessTracker
        tracker = PlanEffectivenessTracker()
        report = tracker.get_effectiveness_report(days)
        return {"success": True, "report": report}
    except Exception as e:
        logger.error(f"Error getting effectiveness report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Basic health check"""
    if not mt5_service:
        return {
            "ok": False,
            "status": "error",
            "message": "MT5 service not initialized"
        }
    
    try:
        if not mt5_service.connect():
            return {
                "ok": False,
                "status": "unhealthy",
                "error": "MT5 connection failed",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "mt5_connection": "critical",
                    "telegram_api": "healthy",
                    "database": "healthy" if journal_repo else "warning",
                    "system_resources": "healthy"
                }
            }
        balance, equity = mt5_service.account_bal_eq()
        
        return {
            "ok": True,
            "timestamp": datetime.now().isoformat(),
            "components": {
                "mt5_connection": "healthy" if balance is not None else "critical",
                "telegram_api": "healthy",
                "database": "healthy" if journal_repo else "warning",
                "system_resources": "healthy"
            }
        }
    except Exception as e:
        return {
            "ok": False,
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/health/status")
async def detailed_health_status() -> Dict[str, Any]:
    """Detailed health status"""
    basic_health = await health_check()
    
    uptime = datetime.now() - startup_time
    uptime_str = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m"
    
    # Get active positions count
    active_positions = 0
    if mt5_service:
        try:
            positions = mt5_service.list_positions()
            active_positions = len(positions) if positions else 0
        except Exception:
            pass
    
    return {
        **basic_health,
        "uptime": uptime_str,
        "active_positions": active_positions,
        "pending_signals": 0  # TODO: Implement signal tracking
    }

# ============================================================================
# TRADING ENDPOINTS
# ============================================================================

@app.post("/signal/send", dependencies=[Depends(verify_api_key)])
async def send_trade_signal(signal: TradeSignal) -> SignalResponse:
    """
    Send trade signal to Telegram for approval.
    This creates a recommendation that the user can approve/reject via Telegram.
    """
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        # Normalize symbol
        symbol = signal.symbol.upper()
        if not symbol.endswith('c'):
            symbol = symbol + 'c'
        
        logger.info(f"Trade signal received: {signal.direction.upper()} {symbol} @ {signal.entry_price}")
        
        # TODO: Send to Telegram bot for approval
        # For now, we'll just log it
        logger.info(f"Signal: {signal.direction.upper()} {symbol} Entry={signal.entry_price} SL={signal.stop_loss} TP={signal.take_profit}")
        
        return SignalResponse(
            ok=True,
            status="pending",
            message_id=None,  # Would be set by Telegram
            expires_at=None
        )
        
    except Exception as e:
        logger.error(f"Signal send error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mt5/execute", dependencies=[Depends(verify_api_key)])
async def execute_trade(signal: TradeSignal) -> ExecutionResponse:
    """
    Execute trade directly in MT5 (bypasses Telegram approval).
    """
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        logger.info(f"[/mt5/execute] Received signal: {signal.dict()}")
        
        # Normalize symbol
        symbol = signal.symbol.upper()
        if not symbol.endswith('c'):
            symbol = symbol + 'c'
        
        logger.info(f"Executing trade: {signal.direction.upper()} {symbol} @ {signal.entry_price}")
        
        # Connect to MT5
        logger.info(f"Attempting MT5 connection...")
        if not mt5_service.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        logger.info(f"MT5 connected successfully")
        
        # Check MT5 terminal info
        terminal_info = mt5.terminal_info()
        if terminal_info:
            logger.info(f"MT5 terminal connected: {terminal_info.connected}")
        else:
            logger.error("MT5 terminal_info() returned None - MT5 may not be initialized")
            raise HTTPException(status_code=500, detail="MT5 terminal not responding")
        
        # Ensure symbol is available
        mt5_service.ensure_symbol(symbol)
        logger.info(f"Symbol {symbol} ensured")
        
        # Get current MT5 price and validate entry price
        quote = mt5_service.get_quote(symbol)
        current_price = (quote.bid + quote.ask) / 2
        
        # Check if entry price is significantly different from current price
        price_diff_pct = abs(signal.entry_price - current_price) / current_price * 100
        if price_diff_pct > 50:  # More than 50% difference
            logger.warning(
                f"Large price discrepancy detected! Entry: {signal.entry_price}, "
                f"MT5 current: {current_price:.2f} (diff: {price_diff_pct:.1f}%)"
            )
            # Still allow the trade but log the warning
        
        # Validate levels
        if signal.direction == Direction.BUY:
            if signal.stop_loss >= signal.entry_price:
                raise HTTPException(status_code=400, detail="Stop loss must be below entry for BUY")
            if signal.take_profit <= signal.entry_price:
                raise HTTPException(status_code=400, detail="Take profit must be above entry for BUY")
        else:
            if signal.stop_loss <= signal.entry_price:
                raise HTTPException(status_code=400, detail="Stop loss must be above entry for SELL")
            if signal.take_profit >= signal.entry_price:
                raise HTTPException(status_code=400, detail="Take profit must be below entry for SELL")
        
        # Determine comment for order type
        # MT5Service.open_order() checks comment for order type
        order_type_comment = None
        if signal.order_type and signal.order_type != OrderType.MARKET:
            # Convert to format MT5Service expects
            order_type_comment = signal.order_type.value  # e.g., "buy_limit", "sell_limit"
        
        # Execute the trade
        result = mt5_service.open_order(
            symbol=symbol,
            side=signal.direction.value,
            entry=signal.entry_price,
            sl=signal.stop_loss,
            tp=signal.take_profit,
            lot=0.01,  # Fixed lot size for safety
            risk_pct=None,
            comment=order_type_comment or (signal.reasoning or "API Trade")[:50]  # Limit comment length
        )
        
        # Check if result is None (MT5 not connected or order failed)
        if result is None:
            logger.error(f"MT5 open_order returned None - MT5 might be disconnected")
            raise HTTPException(status_code=500, detail="MT5 service returned None - check connection")
        
        if result.get("ok"):
            details = result.get("details", {})
            ticket = details.get("ticket")
            
            order_type_str = signal.order_type.value if signal.order_type else "MARKET"
            logger.info(f"Trade executed successfully: {order_type_str} {signal.direction.upper()} {symbol} ticket={ticket}")
            
            # Log to journal
            if journal_repo:
                try:
                    bal, eq = mt5_service.account_bal_eq()
                    journal_repo.write_exec({
                        "symbol": symbol,
                        "side": signal.direction.value,
                        "entry": signal.entry_price,
                        "sl": signal.stop_loss,
                        "tp": signal.take_profit,
                        "lot": 0.01,
                        "ticket": ticket,
                        "position": details.get("position"),
                        "balance": bal,
                        "equity": eq,
                        "notes": f"API Trade ({order_type_str}): {signal.reasoning or 'External API'}"[:200]
                    })
                except Exception as e:
                    logger.warning(f"Failed to write to journal: {e}")
            
            # Log recommendation for performance tracking
            try:
                from infra.recommendation_tracker import RecommendationTracker
                tracker = RecommendationTracker()
                
                # Determine trade type based on order type
                if signal.order_type and signal.order_type != OrderType.MARKET:
                    trade_type = "pending"
                else:
                    trade_type = "scalp"  # Default to scalp for market orders
                
                # Log recommendation
                rec_id = tracker.log_recommendation(
                    symbol=symbol,
                    trade_type=trade_type,
                    direction=signal.direction.value,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                    confidence=signal.confidence or 70,
                    reasoning=signal.reasoning or "Custom GPT trade via API",
                    order_type=signal.order_type.value if signal.order_type else "market",
                    timeframe=signal.timeframe or "M5",
                    user_id=1  # Default user ID for API trades
                )
                
                # Mark as executed
                tracker.mark_executed(
                    recommendation_id=rec_id,
                    mt5_ticket=ticket
                )
                
                logger.info(f"Logged recommendation #{rec_id} for {symbol} {signal.direction.value} (ticket: {ticket})")
            except Exception as e:
                logger.warning(f"Failed to log recommendation: {e}")
            
            return ExecutionResponse(
                ok=True,
                order_id=ticket,
                deal_id=details.get("deal"),
                retcode=details.get("retcode", 10009),
                comment=f"{order_type_str} {signal.direction.upper()} {symbol} executed successfully"
            )
        else:
            error_msg = result.get("message", "Unknown error")
            error_details = result.get("details", {})
            logger.error(f"Trade execution failed: {error_msg} | Details: {error_details}")
            
            # Provide detailed error message
            detailed_error = f"{error_msg}"
            if error_details:
                retcode = error_details.get("retcode")
                if retcode:
                    detailed_error += f" (MT5 RetCode: {retcode})"
            
            raise HTTPException(status_code=400, detail=detailed_error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trade execution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mt5/execute_bracket", dependencies=[Depends(verify_api_key)])
async def execute_bracket_trade(
    symbol: str,
    buy_entry: float,
    buy_sl: float,
    buy_tp: float,
    sell_entry: float,
    sell_sl: float,
    sell_tp: float,
    reasoning: str = "Bracket trade via API"
) -> Dict[str, Any]:
    """
    Execute a bracket trade (OCO pair) with automatic cancellation.
    Places two pending orders: one BUY_LIMIT and one SELL_LIMIT.
    When one fills, the other is automatically cancelled.
    """
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        # Normalize symbol (ensure it ends with lowercase 'c')
        if not symbol.lower().endswith('c'):
            symbol_norm = symbol.upper() + 'c'
        else:
            symbol_norm = symbol.upper().rstrip('cC') + 'c'
        
        logger.info(f"Executing bracket trade for {symbol_norm}: BUY@{buy_entry} + SELL@{sell_entry}")
        
        # Connect to MT5
        if not mt5_service.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        
        mt5_service.ensure_symbol(symbol_norm)
        
        # Validate levels
        if buy_sl >= buy_entry:
            raise HTTPException(status_code=400, detail="BUY stop loss must be below entry")
        if buy_tp <= buy_entry:
            raise HTTPException(status_code=400, detail="BUY take profit must be above entry")
        if sell_sl <= sell_entry:
            raise HTTPException(status_code=400, detail="SELL stop loss must be above entry")
        if sell_tp >= sell_entry:
            raise HTTPException(status_code=400, detail="SELL take profit must be below entry")
        
        # Execute BUY order
        buy_result = mt5_service.open_order(
            symbol=symbol_norm,
            side="buy",
            entry=buy_entry,
            sl=buy_sl,
            tp=buy_tp,
            lot=0.01,
            risk_pct=None,
            comment="buy_limit"  # Force pending limit
        )
        
        if not buy_result.get("ok"):
            raise HTTPException(status_code=400, detail=f"BUY order failed: {buy_result.get('message')}")
        
        buy_ticket = buy_result.get("details", {}).get("ticket")
        
        # Execute SELL order
        sell_result = mt5_service.open_order(
            symbol=symbol_norm,
            side="sell",
            entry=sell_entry,
            sl=sell_sl,
            tp=sell_tp,
            lot=0.01,
            risk_pct=None,
            comment="sell_limit"  # Force pending limit
        )
        
        if not sell_result.get("ok"):
            # Cancel BUY order if SELL fails
            try:
                oco_tracker.cancel_order(mt5_service, buy_ticket, symbol_norm)
            except Exception:
                pass
            raise HTTPException(status_code=400, detail=f"SELL order failed: {sell_result.get('message')}")
        
        sell_ticket = sell_result.get("details", {}).get("ticket")
        
        # Link as OCO pair
        oco_group_id = oco_tracker.create_oco_pair(
            symbol=symbol_norm,
            order_a_ticket=buy_ticket,
            order_b_ticket=sell_ticket,
            order_a_side="BUY",
            order_b_side="SELL",
            order_a_entry=buy_entry,
            order_b_entry=sell_entry,
            comment=reasoning[:100]
        )
        
        logger.info(f"Bracket trade created: OCO {oco_group_id} (BUY:{buy_ticket} + SELL:{sell_ticket})")
        
        return {
            "ok": True,
            "oco_group_id": oco_group_id,
            "buy_order": {
                "ticket": buy_ticket,
                "entry": buy_entry,
                "sl": buy_sl,
                "tp": buy_tp
            },
            "sell_order": {
                "ticket": sell_ticket,
                "entry": sell_entry,
                "sl": sell_sl,
                "tp": sell_tp
            },
            "message": f"Bracket trade created with OCO monitoring"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bracket trade error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mt5/link_oco", dependencies=[Depends(verify_api_key)])
async def link_orders_as_oco(
    symbol: str,
    ticket_a: int,
    ticket_b: int
) -> Dict[str, Any]:
    """
    Link two existing MT5 orders as an OCO pair.
    When one fills, the other will be automatically cancelled.
    """
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        # Normalize symbol (ensure it ends with lowercase 'c')
        if not symbol.lower().endswith('c'):
            symbol_norm = symbol.upper() + 'c'
        else:
            symbol_norm = symbol.upper().rstrip('cC') + 'c'
        
        logger.info(f"Linking orders {ticket_a} + {ticket_b} as OCO for {symbol_norm}")
        
        oco_group_id = oco_tracker.link_existing_orders(
            mt5_service,
            symbol_norm,
            ticket_a,
            ticket_b
        )
        
        if not oco_group_id:
            raise HTTPException(status_code=400, detail="Failed to link orders (one or both not found)")
        
        return {
            "ok": True,
            "oco_group_id": oco_group_id,
            "message": f"Orders {ticket_a} and {ticket_b} linked as OCO pair",
            "symbol": symbol_norm
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Link OCO error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/oco/status")
async def get_oco_status() -> Dict[str, Any]:
    """Get status of all OCO pairs"""
    try:
        stats = oco_tracker.get_oco_stats()
        pairs = oco_tracker.get_active_oco_pairs()
        
        active_pairs = []
        for pair in pairs:
            active_pairs.append({
                "oco_group_id": pair.oco_group_id,
                "symbol": pair.symbol,
                "order_a": {
                    "ticket": pair.order_a_ticket,
                    "side": pair.order_a_side,
                    "entry": pair.order_a_entry
                },
                "order_b": {
                    "ticket": pair.order_b_ticket,
                    "side": pair.order_b_side,
                    "entry": pair.order_b_entry
                },
                "created_at": datetime.fromtimestamp(pair.created_at).isoformat()
            })
        
        return {
            "ok": True,
            "monitor_running": oco_monitor_running,
            "statistics": stats,
            "active_pairs": active_pairs
        }
        
    except Exception as e:
        logger.error(f"OCO status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MARKET ANALYSIS ENDPOINTS
# ============================================================================

@app.get("/market/analysis/{symbol}")
async def get_market_analysis(symbol: str) -> MarketAnalysis:
    """Get market analysis for symbol"""
    if not mt5_service or not indicator_bridge:
        raise HTTPException(status_code=500, detail="Services not initialized")
    
    try:
        # Normalize symbol
        symbol = symbol.upper()
        if not symbol.endswith('c'):
            symbol = symbol + 'c'
        
        if not mt5_service.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        mt5_service.ensure_symbol(symbol)
        
        # Get indicator data
        multi = indicator_bridge.get_multi(symbol)
        m5 = multi.get("M5", {})
        
        # Calculate basic metrics
        atr = m5.get("atr14", 0)
        adx = m5.get("adx", 0)
        
        # Determine regime (simplified)
        if adx > 25:
            regime = "TREND"
        elif adx < 20:
            regime = "RANGE"
        else:
            regime = "CHOP"
        
        # Calculate trend strength
        trend_strength = min(adx / 50.0, 1.0)
        
        # Simple tradeability check
        is_tradeable = adx > 20 and atr > 0
        
        return MarketAnalysis(
            symbol=symbol,
            volatility=atr,
            regime=regime,
            trend_strength=trend_strength,
            liquidity_score=0.8,  # Simplified
            is_tradeable=is_tradeable,
            confidence=0.7
        )
        
    except Exception as e:
        logger.error(f"Market analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ACCOUNT & PERFORMANCE ENDPOINTS
# ============================================================================

@app.get("/api/v1/account")
async def get_account_info() -> AccountInfo:
    """Get MT5 account information"""
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        if not mt5_service.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        info = mt5.account_info()
        
        if info:
            return AccountInfo(
                login=info.login,
                balance=info.balance,
                equity=info.equity,
                margin=info.margin,
                free_margin=info.margin_free,
                profit=info.profit,
                currency=info.currency
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to get account info")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting account info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/risk/metrics")
async def get_risk_metrics():
    """Get current risk metrics"""
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        if not mt5_service.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        account = mt5.account_info()
        positions = mt5_service.list_positions()
        
        portfolio_risk = 0.0
        if positions and account:
            for pos in positions:
                # Calculate risk as percentage of balance
                risk = abs(pos.get("profit", 0)) / account.balance * 100
                portfolio_risk += risk
        
        return {
            "portfolio_risk": round(portfolio_risk, 2),
            "daily_pnl": account.profit if account else 0,
            "max_drawdown": 0.0,  # TODO: Calculate from journal
            "sharpe_ratio": 0.0,  # TODO: Calculate from journal
            "active_positions": len(positions) if positions else 0,
            "risk_limits": {
                "max_daily_loss": 5.0,
                "max_position_size": 0.01,
                "max_correlation": 0.7
            }
        }
        
    except Exception as e:
        logger.error(f"Risk metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/performance/report")
async def get_performance_report():
    """Get trading performance report"""
    if not journal_repo:
        raise HTTPException(status_code=500, detail="Journal not initialized")
    
    try:
        # TODO: Implement proper performance metrics from journal
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "calmar_ratio": 0.0,
            "equity_curve": []
        }
        
    except Exception as e:
        logger.error(f"Performance report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# SYMBOLS & DATA ENDPOINTS
# ============================================================================

@app.get("/api/v1/symbols")
async def list_symbols():
    """List available trading symbols with current prices"""
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        if not mt5_service.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        symbols = ["XAUUSDc", "BTCUSDc", "ETHUSDc", "EURUSDc", "GBPUSDc", "USDJPYc"]
        
        available_symbols = []
        for sym in symbols:
            try:
                mt5_service.ensure_symbol(sym)
                quote = mt5_service.get_quote(sym)
                meta = mt5_service.symbol_meta(sym)
                
                if quote and meta:
                    digits = int(meta.get("digits", 5))
                    available_symbols.append({
                        "symbol": sym,
                        "description": sym,  # Simplified - broker doesn't provide description in meta
                        "bid": quote.bid,
                        "ask": quote.ask,
                        "spread": round(quote.ask - quote.bid, digits),
                        "digits": digits
                    })
            except Exception:
                continue
        
        return {"symbols": available_symbols}
        
    except Exception as e:
        logger.error(f"Error listing symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/price/{symbol}")
async def get_current_price(symbol: str):
    """Get current price for a specific symbol"""
    logger.info(f"========== PRICE REQUEST FOR: {symbol} ==========")
    logger.info(f"Symbol uppercase: {symbol.upper()}")
    logger.info(f"Checking if {symbol.upper()} is in ['DXY', 'DXYC', 'DX-Y.NYB']: {symbol.upper() in ['DXY', 'DXYC', 'DX-Y.NYB']}")
    
    # Special handling for DXY (not available in MT5 - fetch from Yahoo Finance)
    if symbol.upper() in ['DXY', 'DXYC', 'DX-Y.NYB']:
        logger.info(f"Routing {symbol} to Yahoo Finance (DXY)")
        try:
            from infra.market_indices_service import create_market_indices_service
            indices = create_market_indices_service()
            dxy_data = indices.get_dxy()
            
            if dxy_data['price'] is None:
                raise HTTPException(
                    status_code=503, 
                    detail="DXY data temporarily unavailable from Yahoo Finance"
                )
            
            price = dxy_data['price']
            logger.info(f"DXY price fetched successfully: {price}")
            return {
                "symbol": "DXY",
                "bid": price,
                "ask": price,
                "mid": price,
                "spread": 0.0,
                "timestamp": dxy_data['timestamp'],
                "digits": 3,
                "source": "Yahoo Finance (DX-Y.NYB)",
                "note": "Real DXY from Yahoo Finance - broker doesn't provide DXY"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching DXY from Yahoo Finance: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"DXY fetch error: {str(e)}")
    
    # Special handling for VIX (not available in MT5 - fetch from Yahoo Finance)
    if symbol.upper() in ['VIX', 'VIXC', '^VIX']:
        try:
            from infra.market_indices_service import create_market_indices_service
            indices = create_market_indices_service()
            vix_data = indices.get_vix()
            
            if vix_data['price'] is None:
                raise HTTPException(
                    status_code=503,
                    detail="VIX data temporarily unavailable from Yahoo Finance"
                )
            
            price = vix_data['price']
            return {
                "symbol": "VIX",
                "bid": price,
                "ask": price,
                "mid": price,
                "spread": 0.0,
                "timestamp": vix_data['timestamp'],
                "digits": 2,
                "source": "Yahoo Finance (^VIX)",
                "note": "Real VIX from Yahoo Finance - broker doesn't provide VIX"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching VIX from Yahoo Finance: {e}")
            raise HTTPException(status_code=500, detail=f"VIX fetch error: {str(e)}")
    
    # Special handling for US10Y (not available in MT5 - fetch from Yahoo Finance)
    if symbol.upper() in ['US10Y', 'US10YC', 'TNX', '^TNX']:
        try:
            from infra.market_indices_service import create_market_indices_service
            indices = create_market_indices_service()
            us10y_data = indices.get_us10y()
            
            if us10y_data['price'] is None:
                raise HTTPException(
                    status_code=503,
                    detail="US10Y data temporarily unavailable from Yahoo Finance"
                )
            
            price = us10y_data['price']
            return {
                "symbol": "US10Y",
                "bid": price,
                "ask": price,
                "mid": price,
                "spread": 0.0,
                "timestamp": us10y_data['timestamp'],
                "digits": 3,
                "source": "Yahoo Finance (^TNX)",
                "note": "Real US10Y from Yahoo Finance - broker doesn't provide US10Y",
                "gold_correlation": us10y_data['gold_correlation']
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching US10Y from Yahoo Finance: {e}")
            raise HTTPException(status_code=500, detail=f"US10Y fetch error: {str(e)}")
    
    # Normal MT5 symbols
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        # Normalize symbol
        symbol = symbol.upper()
        if not symbol.endswith('c'):
            symbol = symbol + 'c'
        
        if not mt5_service.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        mt5_service.ensure_symbol(symbol)
        
        quote = mt5_service.get_quote(symbol)
        meta = mt5_service.symbol_meta(symbol)
        
        if not quote:
            raise HTTPException(status_code=404, detail=f"Price not available for {symbol}")
        
        digits = int(meta.get("digits", 5))
        
        return {
            "symbol": symbol,
            "bid": quote.bid,
            "ask": quote.ask,
            "mid": round((quote.bid + quote.ask) / 2, digits),
            "spread": round(quote.ask - quote.bid, digits),
            "timestamp": datetime.now().isoformat(),
            "digits": digits
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MONITORING ENDPOINTS
# ============================================================================

@app.get("/api/v1/positions")
async def get_positions():
    """Get all open positions from MT5"""
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        if not mt5_service.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        positions = mt5_service.list_positions()
        
        if not positions:
            return {"positions": [], "count": 0}
        
        # Format positions with additional info
        formatted_positions = []
        for pos in positions:
            formatted_positions.append({
                "ticket": pos.get("ticket"),
                "symbol": pos.get("symbol"),
                "type": pos.get("type"),
                "volume": pos.get("volume"),
                "open_price": pos.get("price_open"),
                "current_price": pos.get("price_current"),
                "sl": pos.get("sl"),
                "tp": pos.get("tp"),
                "profit": pos.get("profit", 0),
                "pnl_percent": (pos.get("profit", 0) / 100) if pos.get("profit", 0) != 0 else 0,  # Rough estimate
                "comment": pos.get("comment", "")
            })
        
        return {
            "positions": formatted_positions,
            "count": len(formatted_positions)
        }
        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/monitor/status")
async def get_monitor_status():
    """Get live trade monitoring status"""
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        positions = mt5_service.list_positions()
        active_count = len(positions) if positions else 0
        
        return {
            "active_positions": active_count,
            "ai_managed_positions": active_count,  # All positions are AI-managed
            "last_check": datetime.now().isoformat(),
            "next_check": (datetime.now()).isoformat(),  # TODO: Calculate from scheduler
            "monitoring_features": [
                "ML Pattern Recognition",
                "Intelligent Exit Strategies",
                "Market Sentiment Analysis",
                "Volatility-Adjusted Trailing",
                "Correlation Risk Assessment",
                "Data Quality Validation"
            ],
            "system_status": "ACTIVE"
        }
        
    except Exception as e:
        logger.error(f"Monitor status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/monitor/run", dependencies=[Depends(verify_api_key)])
async def run_monitor():
    """Trigger manual monitoring cycle"""
    try:
        # TODO: Trigger actual monitoring cycle
        logger.info("Manual monitoring cycle triggered")
        
        return {
            "ok": True,
            "positions_analyzed": 0,
            "actions_taken": 0,
            "bracket_trades_monitored": 0
        }
        
    except Exception as e:
        logger.error(f"Monitor run error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# STUB ENDPOINTS (To be implemented)
# ============================================================================

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Telegram webhook endpoint (placeholder)"""
    return {"ok": True}

@app.get("/ai/analysis/{symbol}")
async def get_ai_analysis(symbol: str, timeframes: Optional[List[str]] = None):
    """Get AI-powered market analysis including ChatGPT insights"""
    if not mt5_service or not indicator_bridge:
        raise HTTPException(status_code=500, detail="Services not initialized")
    
    try:
        # Normalize symbol (add 'c' suffix)
        symbol = symbol.upper()
        if not symbol.endswith('c'):
            symbol = symbol + 'c'
        
        logger.info(f"AI analysis requested for {symbol}")
        
        # Connect and ensure symbol
        if not mt5_service.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        mt5_service.ensure_symbol(symbol)
        
        # Get indicator data
        multi = indicator_bridge.get_multi(symbol)
        m5 = multi.get("M5", {})
        m15 = multi.get("M15", {})
        h1 = multi.get("H1", {})
        
        # Helper to convert to scalar (handle arrays/Series from IndicatorBridge)
        def _to_scalar(val):
            import pandas as pd
            if isinstance(val, (list, tuple)) and len(val) > 0:
                return float(val[-1])
            elif isinstance(val, pd.Series):
                return float(val.iloc[-1]) if len(val) > 0 else 0.0
            else:
                return float(val) if val is not None else 0.0
        
        # Sanitize timeframe dictionaries
        def _sanitize_tf(tf_dict):
            sanitized = {}
            for k, v in tf_dict.items():
                import pandas as pd
                if isinstance(v, pd.Series):
                    sanitized[k] = v.tolist() if len(v) > 1 else (_to_scalar(v) if len(v) == 1 else 0.0)
                elif isinstance(v, (list, tuple)):
                    sanitized[k] = _to_scalar(v)
                else:
                    sanitized[k] = v
            return sanitized
        
        m5_clean = _sanitize_tf(m5)
        m15_clean = _sanitize_tf(m15)
        h1_clean = _sanitize_tf(h1)
        
        # Import OpenAI service
        from infra.openai_service import OpenAIService
        oai = OpenAIService(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)
        
        # Build tech dictionary (simplified version of what handlers/trading.py does)
        tech = {
            "symbol": symbol,
            "atr14": _to_scalar(m5.get("atr14", 0)),
            "adx": _to_scalar(m5.get("adx", 0)),
            "rsi": _to_scalar(m5.get("rsi", 50)),
            "ema20": _to_scalar(m5.get("ema20", 0)),
            "ema50": _to_scalar(m5.get("ema50", 0)),
            "ema200": _to_scalar(m5.get("ema200", 0)),
            "close": _to_scalar(m5.get("close", 0)),
            "regime": "VOLATILE",  # Simplified
            "_tf_M5": m5_clean,
            "_tf_M15": m15_clean,
            "_tf_H1": h1_clean,
        }
        
        # Get market regime (fast, no LLM)
        from app.engine.regime_classifier import classify_regime
        regime_label, regime_scores = classify_regime(tech)
        
        # Get current price
        quote = mt5_service.get_quote(symbol)
        current_price = (quote.bid + quote.ask) / 2
        
        # Simple technical analysis (no LLM call to avoid timeout)
        rsi = _to_scalar(m5.get("rsi", 50))
        adx = _to_scalar(m5.get("adx", 0))
        ema20 = _to_scalar(m5.get("ema20", 0))
        ema50 = _to_scalar(m5.get("ema50", 0))
        
        # Basic direction logic
        direction = "HOLD"
        reasoning = "Insufficient signal strength"
        confidence = 50
        
        if rsi < 30 and ema20 > ema50 and adx > 20:
            direction = "BUY"
            reasoning = f"Oversold (RSI={rsi:.1f}), bullish EMA crossover, strong trend (ADX={adx:.1f})"
            confidence = 65
        elif rsi > 70 and ema20 < ema50 and adx > 20:
            direction = "SELL"
            reasoning = f"Overbought (RSI={rsi:.1f}), bearish EMA crossover, strong trend (ADX={adx:.1f})"
            confidence = 65
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "current_price": {
                "bid": quote.bid,
                "ask": quote.ask,
                "mid": current_price
            },
            "technical_analysis": {
                "trade_recommendation": {
                    "direction": direction,
                    "order_type": "PENDING" if direction != "HOLD" else "MARKET",
                    "entry_price": current_price,
                    "confidence": confidence,
                    "reasoning": reasoning
                },
                "market_regime": regime_label,
                "indicators": {
                    "rsi": rsi,
                    "adx": adx,
                    "ema20": ema20,
                    "ema50": ema50,
                    "ema200": _to_scalar(m5.get("ema200", 0)),
                    "atr14": _to_scalar(m5.get("atr14", 0)),
                    # Additional metrics from IndicatorBridge
                    "macd_line": _to_scalar(m5.get("macd_line", 0)),
                    "macd_signal": _to_scalar(m5.get("macd_signal", 0)),
                    "macd_hist": _to_scalar(m5.get("macd_hist", 0)),
                    "stoch_k": _to_scalar(m5.get("stoch_k", 0)),
                    "stoch_d": _to_scalar(m5.get("stoch_d", 0)),
                    "obv": _to_scalar(m5.get("obv", 0)),
                }
            },
            "ml_insights": {
                "patterns": [],
                "price_direction_prediction": {
                    "direction": "NEUTRAL",
                    "confidence": 50
                }
            },
            "market_sentiment": {
                "fear_greed_index": {"value": 50, "classification": "Neutral"}
            },
            "note": "This endpoint provides fast technical analysis. For full ChatGPT-powered analysis, use the Telegram bot's /trade command."
        }
        
    except Exception as e:
        logger.error(f"AI analysis error for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ml/patterns/{symbol}")
async def get_ml_patterns(symbol: str):
    """Get ML pattern recognition and price prediction analysis"""
    if not mt5_service or not indicator_bridge:
        raise HTTPException(status_code=500, detail="Services not initialized")
    
    try:
        # Normalize symbol (add 'c' suffix)
        symbol = symbol.upper()
        if not symbol.endswith('c'):
            symbol = symbol + 'c'
        
        logger.info(f"ML patterns requested for {symbol}")
        
        # Connect and ensure symbol
        if not mt5_service.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        mt5_service.ensure_symbol(symbol)
        
        # Get indicator data
        multi = indicator_bridge.get_multi(symbol)
        m5 = multi.get("M5", {})
        
        # Detect candlestick patterns
        from domain.patterns import detect_patterns
        patterns_detected = []
        
        try:
            # Get pattern data from M5
            pattern_data = detect_patterns(
                open_prices=[m5.get("open", 0)] * 5,
                high_prices=[m5.get("high", 0)] * 5,
                low_prices=[m5.get("low", 0)] * 5,
                close_prices=[m5.get("close", 0)] * 5
            )
            
            # Convert to API format
            for pattern_name, detected in pattern_data.items():
                if detected:
                    patterns_detected.append({
                        "name": pattern_name.replace("_", " ").title(),
                        "type": "reversal" if "reversal" in pattern_name.lower() else "continuation",
                        "strength": 0.7,
                        "description": f"{pattern_name} pattern detected"
                    })
        except Exception as e:
            logger.warning(f"Pattern detection failed: {e}")
        
        # Simple price direction prediction based on indicators
        rsi = m5.get("rsi", 50)
        adx = m5.get("adx", 20)
        ema20 = m5.get("ema20", 0)
        ema50 = m5.get("ema50", 0)
        close = m5.get("close", 0)
        
        # Determine direction and confidence
        bullish_signals = 0
        bearish_signals = 0
        
        if rsi < 30:
            bullish_signals += 1
        elif rsi > 70:
            bearish_signals += 1
        
        if ema20 > ema50:
            bullish_signals += 1
        elif ema20 < ema50:
            bearish_signals += 1
        
        if close > ema20:
            bullish_signals += 1
        elif close < ema20:
            bearish_signals += 1
        
        total_signals = bullish_signals + bearish_signals
        if bullish_signals > bearish_signals:
            direction = "UP"
            prob_up = 50 + (bullish_signals / max(total_signals, 1)) * 30
            prob_down = 100 - prob_up
        elif bearish_signals > bullish_signals:
            direction = "DOWN"
            prob_down = 50 + (bearish_signals / max(total_signals, 1)) * 30
            prob_up = 100 - prob_down
        else:
            direction = "NEUTRAL"
            prob_up = 50
            prob_down = 50
        
        confidence = max(abs(bullish_signals - bearish_signals) / max(total_signals, 1) * 100, 50)
        
        # Volatility prediction based on ATR
        atr = m5.get("atr14", 0)
        atr_pct = (atr / close * 100) if close > 0 else 0
        
        if atr_pct > 2.0:
            volatility_level = "HIGH"
            vol_probs = {"low": 20, "medium": 30, "high": 50}
        elif atr_pct > 1.0:
            volatility_level = "MEDIUM"
            vol_probs = {"low": 30, "medium": 50, "high": 20}
        else:
            volatility_level = "LOW"
            vol_probs = {"low": 50, "medium": 40, "high": 10}
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "patterns": patterns_detected,
            "price_direction_prediction": {
                "direction": direction,
                "confidence": round(confidence, 2),
                "probability_up": round(prob_up, 2),
                "probability_down": round(prob_down, 2)
            },
            "volatility_prediction": {
                "volatility_level": volatility_level,
                "confidence": 70,
                "probabilities": vol_probs
            }
        }
        
    except Exception as e:
        logger.error(f"ML patterns error for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ai/exits/{symbol}")
async def get_intelligent_exits(symbol: str):
    """Get intelligent exit strategy recommendations"""
    if not mt5_service or not indicator_bridge:
        raise HTTPException(status_code=500, detail="Services not initialized")
    
    try:
        # Normalize symbol (add 'c' suffix)
        symbol = symbol.upper()
        if not symbol.endswith('c'):
            symbol = symbol + 'c'
        
        logger.info(f"Intelligent exits requested for {symbol}")
        
        # Connect and ensure symbol
        if not mt5_service.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        mt5_service.ensure_symbol(symbol)
        
        # Get indicator data
        multi = indicator_bridge.get_multi(symbol)
        m5 = multi.get("M5", {})
        m15 = multi.get("M15", {})
        
        # Get current positions for this symbol
        positions = mt5_service.list_positions()
        active_positions = [p for p in (positions or []) if p.get("symbol") == symbol]
        
        # Build exit signals based on technical indicators
        exit_signals = []
        
        # Get key indicators
        rsi = m5.get("rsi", 50)
        adx = m5.get("adx", 20)
        atr = m5.get("atr14", 0)
        close = m5.get("close", 0)
        ema20 = m5.get("ema20", 0)
        ema50 = m5.get("ema50", 0)
        
        # 1. Trailing Stop Strategy
        if adx > 25 and atr > 0:
            exit_signals.append({
                "strategy": "TRAILING_STOP",
                "action": "TRAILING_STOP",
                "confidence": min(adx, 100),
                "reason": f"Strong trend (ADX={adx:.1f}), trail stop at {atr:.2f} ATR"
            })
        
        # 2. Partial Profit Strategy
        if len(active_positions) > 0:
            for pos in active_positions:
                profit = pos.get("profit", 0)
                if profit > 0:
                    exit_signals.append({
                        "strategy": "PARTIAL_PROFIT",
                        "action": "PARTIAL_PROFIT",
                        "confidence": 70,
                        "reason": f"Position in profit (${profit:.2f}), consider taking 50%"
                    })
        
        # 3. RSI Overbought/Oversold Exit
        if rsi > 70:
            exit_signals.append({
                "strategy": "MOMENTUM_EXIT",
                "action": "EXIT",
                "confidence": min((rsi - 70) * 3, 100),
                "reason": f"RSI overbought at {rsi:.1f}, momentum weakening"
            })
        elif rsi < 30:
            exit_signals.append({
                "strategy": "MOMENTUM_EXIT",
                "action": "EXIT",
                "confidence": min((30 - rsi) * 3, 100),
                "reason": f"RSI oversold at {rsi:.1f}, reversal likely"
            })
        
        # 4. Breakeven Strategy
        if len(active_positions) > 0:
            exit_signals.append({
                "strategy": "BREAKEVEN",
                "action": "BREAKEVEN",
                "confidence": 60,
                "reason": "Move stop loss to breakeven to protect capital"
            })
        
        # 5. Support/Resistance Exit
        if abs(ema20 - close) / close < 0.001:  # Near EMA20
            exit_signals.append({
                "strategy": "SUPPORT_RESISTANCE_EXIT",
                "action": "HOLD",
                "confidence": 50,
                "reason": f"Price near EMA20 at {ema20:.2f}, key support/resistance"
            })
        
        # Determine best recommendation
        if exit_signals:
            # Sort by confidence
            exit_signals.sort(key=lambda x: x["confidence"], reverse=True)
            best_signal = exit_signals[0]
            
            best_recommendation = {
                "action": best_signal["action"],
                "confidence": best_signal["confidence"],
                "reason": best_signal["reason"],
                "total_signals": len(exit_signals),
                "all_signals": [s["strategy"] for s in exit_signals]
            }
        else:
            best_recommendation = {
                "action": "HOLD",
                "confidence": 50,
                "reason": "No strong exit signals detected, maintain position",
                "total_signals": 0,
                "all_signals": []
            }
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "exit_signals": exit_signals,
            "best_recommendation": best_recommendation
        }
        
    except Exception as e:
        logger.error(f"Intelligent exits error for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mt5/intelligent_exits/recent")
async def get_recent_intelligent_exits(
    hours: int = 24,
    action_type: Optional[str] = None,
    symbol: Optional[str] = None
) -> Dict[str, Any]:
    """Get recent intelligent exit actions within the specified time window"""
    try:
        from infra.intelligent_exit_logger import get_exit_logger
        
        exit_logger = get_exit_logger()
        actions = exit_logger.get_recent_actions(hours=hours, action_type=action_type, symbol=symbol)
        
        return {
            "ok": True,
            "hours": hours,
            "action_type": action_type or "all",
            "symbol": symbol or "all",
            "count": len(actions),
            "actions": actions
        }
        
    except Exception as e:
        logger.error(f"Error getting recent intelligent exits: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sentiment/market")
async def get_market_sentiment():
    """Market sentiment analysis (placeholder)"""
    raise HTTPException(status_code=501, detail="Market sentiment endpoint not yet implemented")

@app.get("/correlation/{symbol}")
async def get_correlation_analysis(symbol: str):
    """Correlation analysis (placeholder)"""
    raise HTTPException(status_code=501, detail="Correlation analysis endpoint not yet implemented")

@app.post("/bracket/analyze", dependencies=[Depends(verify_api_key)])
async def analyze_bracket_conditions(request: Request):
    """Analyze bracket trade conditions (placeholder)"""
    raise HTTPException(status_code=501, detail="Bracket analysis endpoint not yet implemented")

@app.get("/data/validate/{symbol}")
async def validate_data_quality(symbol: str):
    """Validate data quality (placeholder)"""
    raise HTTPException(status_code=501, detail="Data validation endpoint not yet implemented")

# ============================================================================
# MICRO-SCALP MONITOR ENDPOINTS
# ============================================================================

@app.get("/micro-scalp/status", tags=["micro-scalp"])
async def get_micro_scalp_status() -> Dict[str, Any]:
    """Get Micro-Scalp Monitor status and statistics"""
    try:
        if micro_scalp_monitor is None:
            return {
                "ok": False,
                "status": {
                    "monitoring": False,
                    "enabled": False,
                    "error": "Micro-Scalp Monitor not initialized"
                },
                "timestamp": datetime.now().isoformat()
            }
        
        status = micro_scalp_monitor.get_status()
        return {
            "ok": True,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting micro-scalp status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/micro-scalp/history", tags=["micro-scalp"])
async def get_micro_scalp_history(symbol: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """Get detailed check history for micro-scalp monitor"""
    try:
        if micro_scalp_monitor is None:
            return {
                "ok": False,
                "error": "Micro-Scalp Monitor not initialized",
                "checks": [],
                "timestamp": datetime.now().isoformat()
            }
        
        history_data = micro_scalp_monitor.get_detailed_history(symbol=symbol, limit=limit)
        
        # Flatten history if multiple symbols
        if symbol:
            checks = history_data.get('checks', [])
        else:
            checks = []
            for sym, sym_data in history_data.items():
                checks.extend(sym_data.get('checks', []))
            # Sort by timestamp (newest first)
            checks.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            checks = checks[:limit]
        
        return {
            "ok": True,
            "checks": checks,
            "count": len(checks),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting micro-scalp history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/micro-scalp/view", response_class=HTMLResponse, tags=["micro-scalp"])
async def micro_scalp_view(symbol: Optional[str] = None):
    """Micro-Scalp Monitor Dashboard"""
    try:
        if micro_scalp_monitor is None:
            return HTMLResponse(
                content="<h1>Micro-Scalp Monitor Not Initialized</h1><p>The monitor is not running.</p>",
                status_code=503
            )
        
        status = micro_scalp_monitor.get_status()
        history_data = micro_scalp_monitor.get_detailed_history(symbol=symbol, limit=100)
        
        # Flatten history if multiple symbols
        if symbol:
            checks = history_data.get('checks', [])
        else:
            checks = []
            for sym, sym_data in history_data.items():
                for check in sym_data.get('checks', []):
                    check['symbol'] = sym
                    checks.append(check)
            # Sort by timestamp (newest first)
            checks.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Get unique symbols for filter
        all_symbols = list(history_data.keys()) if not symbol else [symbol]
        
        # Generate HTML dashboard matching other pages' style
        symbol_filter_options = ''.join([f'<option value="{s}" {"selected" if s == symbol else ""}>{s}</option>' for s in all_symbols])
        symbol_filter_options = '<option value="">All Symbols</option>' + symbol_filter_options
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MoneyBot - Micro-Scalp Monitor</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; background: #0b1220; color: #e6edf3; }}
    h1 {{ margin-bottom: 8px; color: #e6edf3; }}
    .sub {{ color: #9fb0c3; margin-bottom: 16px; }}
    .nav {{ margin-bottom: 20px; }}
    .nav a {{ color: #9fb0c3; text-decoration: none; margin-right: 20px; }}
    .nav a:hover {{ color: #e6edf3; }}
    .controls {{ margin-bottom: 16px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    select, input[type="text"] {{ padding: 8px; border-radius: 6px; border: 1px solid #24324a; background: #0f172a; color: #e6edf3; }}
    button {{ padding: 8px 12px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; }}
    button:hover {{ background: #213352; }}
    .status-card {{ background: #111a2e; border: 1px solid #213352; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
    .status-card h2 {{ margin-top: 0; color: #e6edf3; }}
    .status-badge {{ display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 12px; border: 1px solid #2b3b57; background: #0f172a; margin-right: 8px; }}
    .status-badge.active {{ background: #1a3a1a; border-color: #2d5a2d; color: #90ee90; }}
    .status-badge.inactive {{ background: #3a1a1a; border-color: #5a2d2d; color: #ff9090; }}
    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 16px; }}
    .stat-item {{ background: #0f172a; border: 1px solid #24324a; border-radius: 6px; padding: 12px; text-align: center; }}
    .stat-value {{ font-size: 1.8em; font-weight: bold; color: #90ee90; }}
    .stat-label {{ color: #9fb0c3; font-size: 12px; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #213352; padding: 10px; text-align: left; }}
    th {{ background: #111a2e; position: sticky; top: 0; color: #e6edf3; }}
    tr:hover {{ background: #111a2e; }}
    .pill {{ padding: 2px 8px; border-radius: 999px; font-size: 12px; border: 1px solid #2b3b57; background: #0f172a; display: inline-block; margin: 2px; }}
    .pill.pass {{ background: #1a3a1a; border-color: #2d5a2d; color: #90ee90; }}
    .pill.fail {{ background: #3a1a1a; border-color: #5a2d2d; color: #ff9090; }}
    .pill.strategy {{ background: #1a1a3a; border-color: #2d2d5a; color: #90c0ff; }}
    .pill.regime {{ background: #3a2a1a; border-color: #5a3a2d; color: #ffc090; }}
    .muted {{ color: #9fb0c3; font-size: 12px; }}
    .wrap {{ white-space: pre-wrap; word-break: break-word; }}
    .conditions {{ font-family: monospace; font-size: 11px; color: #9fb0c3; background: #0f172a; padding: 6px; border-radius: 4px; max-width: 500px; }}
    .conditions-key {{ color: #90c0ff; }}
    .conditions-value {{ color: #90ee90; }}
    .conditions-section {{ margin-bottom: 8px; }}
    .conditions-section-title {{ font-weight: bold; color: #90c0ff; margin-bottom: 4px; }}
  </style>
  <script>
    function filterBySymbol() {{
      const symbol = document.getElementById('symbolFilter').value;
      const url = new URL(window.location.href);
      if (symbol) {{
        url.searchParams.set('symbol', symbol);
      }} else {{
        url.searchParams.delete('symbol');
      }}
      window.location.href = url.toString();
    }}
    
    // Auto-refresh every 10 seconds
    setTimeout(function() {{
      location.reload();
    }}, 10000);
  </script>
</head>
<body>
  <div class="nav">
    <a href="/">Home</a>
    <a href="/volatility-regime/monitor">Volatility Monitor</a>
    <a href="/notifications/view">Notifications</a>
    <a href="/alerts/view">ChatGPT Alerts</a>
    <a href="/auto-execution/view">Auto Execution Plans</a>
    <a href="/micro-scalp/view">Micro-Scalp Monitor</a>
    <a href="/dtms/status">DTMS Status</a>
    <a href="/dtms/actions">DTMS Actions</a>
    <a href="/docs">API Docs</a>
  </div>
  
  <h1>🔍 Micro-Scalp Monitor</h1>
  <div class="sub">Continuous monitoring for micro-scalp setups</div>
  
  <div class="status-card">
    <h2>Status</h2>
    <span class="status-badge {'active' if status.get('monitoring') else 'inactive'}">
      {'🟢 ACTIVE' if status.get('monitoring') else '🔴 NOT RUNNING'}
    </span>
    <span class="status-badge {'active' if status.get('enabled') else 'inactive'}">
      {'Enabled' if status.get('enabled') else 'Disabled'}
    </span>
    <span class="status-badge {'active' if status.get('thread_alive') else 'inactive'}">
      {'Thread: Alive' if status.get('thread_alive') else 'Thread: Dead'}
    </span>
  </div>
  
  <div class="status-card">
    <h2>Statistics</h2>
    <div class="stats-grid">
      <div class="stat-item">
        <div class="stat-value">{status.get('stats', {}).get('total_checks', 0)}</div>
        <div class="stat-label">Total Checks</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{status.get('stats', {}).get('conditions_met', 0)}</div>
        <div class="stat-label">Conditions Met</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{status.get('stats', {}).get('executions', 0)}</div>
        <div class="stat-label">Executions</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{status.get('stats', {}).get('skipped', {}).get('session', 0)}</div>
        <div class="stat-label">Skipped (Session)</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{status.get('stats', {}).get('skipped', {}).get('news', 0)}</div>
        <div class="stat-label">Skipped (News)</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{status.get('stats', {}).get('skipped', {}).get('rate_limit', 0)}</div>
        <div class="stat-label">Skipped (Rate Limit)</div>
      </div>
    </div>
  </div>
  
  <div class="status-card">
    <h2>Recent Checks</h2>
    <div class="controls">
      <label for="symbolFilter">Symbol:</label>
      <select id="symbolFilter" onchange="filterBySymbol()">
        {symbol_filter_options}
      </select>
      <button onclick="location.reload()">🔄 Refresh</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>Time</th>
          <th>Symbol</th>
          <th>Strategy</th>
          <th>Regime</th>
          <th>Regime Confidence</th>
          <th>Result</th>
          <th>Confluence</th>
          <th>Conditions</th>
          <th>Regime Details</th>
        </tr>
      </thead>
      <tbody>
"""
        
        for check in checks[:100]:
            timestamp = check.get('timestamp', 'N/A')
            sym = check.get('symbol', 'N/A')
            strategy = check.get('strategy', 'N/A')
            regime = check.get('regime', 'N/A')
            regime_confidence = check.get('regime_confidence', 0.0)
            passed = check.get('passed', False)
            confluence = check.get('confluence_score', check.get('condition_details', {}).get('confluence_score', 0.0))
            
            # Get condition details
            condition_details = check.get('condition_details', {})
            conditions_html = '<div class="conditions">'
            if condition_details:
                if condition_details.get('pre_trade_passed') is not None:
                    conditions_html += f'<div class="conditions-section"><span class="conditions-key">Pre-Trade:</span> <span class="conditions-value">{"✓" if condition_details.get("pre_trade_passed") else "✗"}</span></div>'
                if condition_details.get('location_passed') is not None:
                    conditions_html += f'<div class="conditions-section"><span class="conditions-key">Location:</span> <span class="conditions-value">{"✓" if condition_details.get("location_passed") else "✗"}</span></div>'
                primary_count = condition_details.get('primary_triggers', 0)
                secondary_count = condition_details.get('secondary_confluence', 0)
                conditions_html += f'<div class="conditions-section"><span class="conditions-key">Primary:</span> <span class="conditions-value">{primary_count}</span> <span class="conditions-key">Secondary:</span> <span class="conditions-value">{secondary_count}</span></div>'
                # Show failure reason if signals insufficient
                if primary_count < 1 or secondary_count < 1:
                    conditions_html += f'<div class="muted" style="font-size: 10px; margin-top: 2px; color: #ff9090;">Need ≥1 primary AND ≥1 secondary</div>'
                if condition_details.get('details'):
                    details = condition_details.get('details', {})
                    for key, value in list(details.items())[:2]:  # Show first 2 details
                        conditions_html += f'<div class="conditions-section"><span class="conditions-key">{key}:</span> <span class="conditions-value">{str(value)[:30]}</span></div>'
            else:
                conditions_html += '<div class="muted">No condition details</div>'
            conditions_html += '</div>'
            
            # Show failure reasons if available
            failure_reasons = check.get('failure_reasons', [])
            if failure_reasons and not passed:
                conditions_html += '<div class="conditions" style="margin-top: 4px; border-top: 1px solid #213352; padding-top: 4px;">'
                conditions_html += '<div class="conditions-section-title" style="color: #ff9090;">Failure Reasons:</div>'
                for reason in failure_reasons[:3]:  # Show first 3 reasons
                    conditions_html += f'<div class="muted" style="font-size: 10px;">• {str(reason)[:50]}</div>'
                conditions_html += '</div>'
            
            # Get regime detection details
            regime_detection = check.get('regime_detection', {})
            regime_details_html = '<div class="conditions">'
            if regime_detection:
                vwap = regime_detection.get('vwap_reversion', {})
                range_scalp = regime_detection.get('range_scalp', {})
                balanced = regime_detection.get('balanced_zone', {})
                
                vwap_conf = vwap.get('confidence', 0)
                vwap_thresh = vwap.get('threshold', 70)
                vwap_reason = vwap.get('reason', '')
                vwap_status = '✓' if vwap_conf >= vwap_thresh else '✗'
                vwap_color = 'conditions-value' if vwap_conf >= vwap_thresh else 'conditions-missing'
                
                range_conf = range_scalp.get('confidence', 0)
                range_thresh = range_scalp.get('threshold', 55)
                range_reason = range_scalp.get('reason', '')
                range_status = '✓' if range_conf >= range_thresh else '✗'
                range_color = 'conditions-value' if range_conf >= range_thresh else 'conditions-missing'
                
                balanced_conf = balanced.get('confidence', 0)
                balanced_thresh = balanced.get('threshold', 65)
                balanced_reason = balanced.get('reason', '')
                balanced_status = '✓' if balanced_conf >= balanced_thresh else '✗'
                balanced_color = 'conditions-value' if balanced_conf >= balanced_thresh else 'conditions-missing'
                
                regime_details_html += f'<div class="conditions-section"><div class="conditions-section-title">VWAP Reversion:</div>'
                regime_details_html += f'<div><span class="{vwap_color}">{vwap_status} {vwap_conf}%</span> / {vwap_thresh}%</div>'
                if vwap_reason:
                    regime_details_html += f'<div class="muted" style="font-size: 10px; margin-top: 2px;">{vwap_reason}</div>'
                regime_details_html += '</div>'
                
                regime_details_html += f'<div class="conditions-section"><div class="conditions-section-title">Range Scalp:</div>'
                regime_details_html += f'<div><span class="{range_color}">{range_status} {range_conf}%</span> / {range_thresh}%</div>'
                if range_reason:
                    regime_details_html += f'<div class="muted" style="font-size: 10px; margin-top: 2px;">{range_reason}</div>'
                regime_details_html += '</div>'
                
                regime_details_html += f'<div class="conditions-section"><div class="conditions-section-title">Balanced Zone:</div>'
                regime_details_html += f'<div><span class="{balanced_color}">{balanced_status} {balanced_conf}%</span> / {balanced_thresh}%</div>'
                if balanced_reason:
                    regime_details_html += f'<div class="muted" style="font-size: 10px; margin-top: 2px;">{balanced_reason}</div>'
                # Show detailed breakdown if available
                bb_comp = balanced.get('bb_compression', None)
                comp_block = balanced.get('compression_block', None)
                atr_drop = balanced.get('atr_dropping', None)
                equil = balanced.get('equilibrium_ok', None)
                if bb_comp is not None or comp_block is not None or atr_drop is not None or equil is not None:
                    details_parts = []
                    if bb_comp is not None:
                        details_parts.append(f'BB: {"✓" if bb_comp else "✗"}')
                    if comp_block is not None:
                        details_parts.append(f'Block: {"✓" if comp_block else "✗"}')
                    if atr_drop is not None:
                        details_parts.append(f'ATR: {"✓" if atr_drop else "✗"}')
                    if equil is not None:
                        details_parts.append(f'Eq: {"✓" if equil else "✗"}')
                    if details_parts:
                        regime_details_html += f'<div class="muted" style="font-size: 10px; margin-top: 2px;">{", ".join(details_parts)}</div>'
                regime_details_html += '</div>'
            else:
                regime_details_html += '<div class="muted">No regime detection data</div>'
            regime_details_html += '</div>'
            
            passed_pill = f'<span class="pill pass">PASS</span>' if passed else f'<span class="pill fail">FAIL</span>'
            strategy_pill = f'<span class="pill strategy">{strategy}</span>' if strategy and strategy != 'N/A' else '<span class="muted">N/A</span>'
            regime_pill = f'<span class="pill regime">{regime}</span>' if regime and regime != 'N/A' else '<span class="muted">N/A</span>'
            
            html_content += f"""
        <tr>
          <td><div class="wrap">{timestamp}</div></td>
          <td>{sym}</td>
          <td>{strategy_pill}</td>
          <td>{regime_pill}</td>
          <td>{regime_confidence:.1f}%</td>
          <td>{passed_pill}</td>
          <td>{confluence:.1f}</td>
          <td>{conditions_html}</td>
          <td>{regime_details_html}</td>
        </tr>
"""
        
        html_content += """
      </tbody>
    </table>
  </div>
</body>
</html>
"""
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"Error generating micro-scalp view: {e}", exc_info=True)
        return HTMLResponse(
            content=f"<h1>Error</h1><p>{str(e)}</p>",
            status_code=500
        )

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    # Note: Reload mode only works when running via uvicorn command line:
    #   python -m uvicorn main_api:app --host 0.0.0.0 --port 8010 --reload
    # 
    # Direct execution (python main_api.py) cannot use reload because uvicorn
    # needs the app as an import string, not a direct object.
    # 
    # For development with auto-reload, use the batch file or run:
    #   python -m uvicorn main_api:app --host 0.0.0.0 --port 8010 --reload
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8010, 
        log_level="info",
        reload=False  # Disabled - use uvicorn CLI for reload: python -m uvicorn main_api:app --reload
    )
