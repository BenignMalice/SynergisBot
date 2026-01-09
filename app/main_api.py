"""
FastAPI server implementing the openai.yaml specification.
Provides comprehensive API for ChatGPT and external services to interact with MT5 trading bot.
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Header, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from enum import Enum
import logging
import MetaTrader5 as mt5
import asyncio

# Optional imports for observability, config, shadow mode, decision traces
try:
    from infra.observability import HealthEndpoint, SystemHealthMonitor
    _observability_available = True
except Exception:
    _observability_available = False

try:
    from infra.config_management import get_config_manager
    _config_mgmt_available = True
except Exception:
    _config_mgmt_available = False

try:
    from infra.shadow_mode import get_shadow_mode_controller
    _shadow_mode_available = True
except Exception:
    _shadow_mode_available = False

try:
    from infra.decision_traces import get_decision_trace_manager
    _decision_traces_available = True
except Exception:
    _decision_traces_available = False

# Optional validation systems
try:
    from infra.structure_validation import StructureValidationSystem
    _structure_val_available = True
except Exception:
    _structure_val_available = False

try:
    from infra.latency_validation import LatencyValidator
    _latency_val_available = True
except Exception:
    _latency_val_available = False

try:
    from infra.database_performance_validation import DatabasePerformanceManager
    _db_val_available = True
except Exception:
    _db_val_available = False

# Add parent directory to path to import bot modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.mt5_service import MT5Service
from infra.journal_repo import JournalRepo
from infra.plan_effectiveness_tracker import PlanEffectivenessTracker
# PHASE 5: DTMS imports kept for endpoint fallback logic (get_dtms_system_status, etc.)
# DTMS initialization removed - using API server instead
from dtms_integration import get_dtms_system_status, get_dtms_trade_status, get_dtms_action_history  # Keep for endpoint fallback
# from dtms_integration import initialize_dtms, start_dtms_monitoring, stop_dtms_monitoring, run_dtms_monitoring_cycle  # OLD: Commented out
from infra.indicator_bridge import IndicatorBridge
from infra.multi_timeframe_streamer import MultiTimeframeStreamer, StreamerConfig
from infra.tick_metrics import set_tick_metrics_instance, get_tick_metrics_instance
from config import settings
from app.services import oco_tracker

# Import auto execution API
from app.auto_execution_api import router as auto_execution_router

# Separate database architecture manager (from updated API)
try:
    from database_access_manager import initialize_database_manager
except Exception:
    initialize_database_manager = None  # Fallback if not available

# Import Unified Tick Pipeline integration
from main_api_unified_pipeline_integration import (
    initialize_main_api_unified_pipeline,
    get_enhanced_market_data,
    get_volatility_analysis,
    get_offset_calibration,
    get_system_health,
    get_pipeline_status,
    get_multi_timeframe_analysis,
    get_real_time_ticks,
    get_enhanced_symbol_analysis,
    get_integration_status
)

def normalize_symbol(symbol: str) -> str:
    """Normalize symbol to ensure proper 'c' suffix without double 'c'"""
    symbol = symbol.upper()
    # Remove any existing 'c' or 'C' suffix first
    if symbol.endswith('c') or symbol.endswith('C'):
        symbol = symbol[:-1]
    # Add single 'c' suffix
    symbol = symbol + 'c'
    return symbol

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Cache for trade outcomes (5 minute expiry) - thread-safe for async operations
_outcome_cache: Dict[int, Optional[Dict]] = {}
_cache_expiry: Dict[int, datetime] = {}
_cache_lock = asyncio.Lock()

async def get_cached_outcome(tracker: PlanEffectivenessTracker, ticket: int, executed_at: Optional[str] = None) -> Optional[Dict]:
    """Get trade outcome with caching (5 minute expiry) - thread-safe for async"""
    now = datetime.now()
    
    # Check cache (thread-safe)
    async with _cache_lock:
        if ticket in _outcome_cache and ticket in _cache_expiry:
            if now < _cache_expiry[ticket]:
                return _outcome_cache[ticket]
    
    # Query MT5 using existing infrastructure (run in thread pool to avoid blocking)
    loop = asyncio.get_event_loop()
    outcome = await loop.run_in_executor(None, tracker._get_mt5_trade_outcome, ticket, executed_at)
    
    # Cache result (thread-safe)
    async with _cache_lock:
        _outcome_cache[ticket] = outcome
        _cache_expiry[ticket] = now + timedelta(minutes=5)
    
    return outcome

# Lifespan handler for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await startup_event()
    except Exception as e:
        logger.error(f"Startup error in lifespan: {e}", exc_info=True)
    
    try:
        yield
    except asyncio.CancelledError:
        # Framework-level cancellation during yield - this is normal on Ctrl+C
        # Don't log as error, just continue to shutdown
        logger.debug("Lifespan yield cancelled (normal shutdown)")
    except KeyboardInterrupt:
        # Keyboard interrupt during yield - also normal
        logger.debug("Lifespan yield interrupted (normal shutdown)")
    finally:
        # Shutdown - handle cancellation gracefully
        # Use finally to ensure cleanup runs even if yield is cancelled
        try:
            await shutdown_event()
        except asyncio.CancelledError:
            # Normal shutdown cancellation - suppress error, just log info
            logger.info("Shutdown cancelled (normal termination via Ctrl+C)")
        except KeyboardInterrupt:
            # Also handle KeyboardInterrupt gracefully
            logger.info("Shutdown interrupted (normal termination)")
        except Exception as e:
            # Only log unexpected errors, not cancellation errors
            if not isinstance(e, (asyncio.CancelledError, KeyboardInterrupt)):
                logger.error(f"Shutdown error: {e}", exc_info=True)
            else:
                logger.debug(f"Shutdown cancellation: {type(e).__name__}")

# Initialize FastAPI app
app = FastAPI(
    title="MoneyBot v1.1 - Advanced AI Trading System API",
    description="Revolutionary AI-powered trading system for intelligent trade management",
    version="1.1.0",
    lifespan=lifespan
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests for debugging"""
    start_time = time.time()
    logger.info(f"📥 Incoming request: {request.method} {request.url.path}")
    logger.info(f"   Headers: {dict(request.headers)}")
    logger.info(f"   Query params: {dict(request.query_params)}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"📤 Response: {response.status_code} (took {process_time:.2f}s)")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"❌ Request failed after {process_time:.2f}s: {e}", exc_info=True)
        raise

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

# Initialize Separate Database Architecture manager (write access to logs DB)
db_manager = None
if initialize_database_manager:
    try:
        db_manager = initialize_database_manager("api_server")
        logger.info("✅ Separate database architecture active for API server (logs DB writer)")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize database access manager: {e}")

# Optional: Basic health endpoint using observability system if available
_health_monitor = None
if _observability_available:
    try:
        _health_monitor = SystemHealthMonitor()
        logger.info("✅ System health monitor initialized")
    except Exception as e:
        logger.warning(f"⚠️ Health monitor initialization failed: {e}")

@app.get("/health", tags=["system"])
async def health() -> Dict[str, Any]:
    if _observability_available and _health_monitor:
        return _health_monitor._get_system_health()
    return {"status": "ok", "message": "Observability not enabled"}

# Optional: Config management endpoints
@app.get("/config/{symbol}", tags=["config"])
async def get_symbol_config(symbol: str) -> Dict[str, Any]:
    if not _config_mgmt_available:
        raise HTTPException(status_code=404, detail="Config management not available")
    mgr = get_config_manager()
    conf = mgr.get_config(symbol)
    if conf is None:
        raise HTTPException(status_code=404, detail="Config not found")
    return conf

@app.post("/config/{symbol}", tags=["config"])
async def set_symbol_config(symbol: str, body: Dict[str, Any]) -> Dict[str, Any]:
    if not _config_mgmt_available:
        raise HTTPException(status_code=404, detail="Config management not available")
    mgr = get_config_manager()
    ok = mgr.save_config(symbol, body)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save config")
    return {"success": True}

@app.post("/config/reload", tags=["config"])
async def reload_configs() -> Dict[str, Any]:
    """Manually trigger config reload for all symbols"""
    try:
        from config.symbol_config_loader import get_config_loader
        loader = get_config_loader()
        changed = loader.reload_if_changed()
        return {
            "success": True, 
            "reloaded_symbols": list(changed) if changed else [],
            "message": f"Reloaded {len(changed)} symbol configs" if changed else "No configs changed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Config reload failed: {str(e)}")

# ============================================================================
# STREAMER API ENDPOINTS
# ============================================================================

@app.get("/streamer/candles/{symbol}/{timeframe}", tags=["streamer"])
async def get_streamer_candles(
    symbol: str,
    timeframe: str,
    limit: int = 50,
    format: str = "dict"
) -> Dict[str, Any]:
    """
    Get candles from MultiTimeframeStreamer buffer.
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDc')
        timeframe: Timeframe ('M1', 'M5', 'M15', 'M30', 'H1', 'H4')
        limit: Number of candles to return (default: 50, max: 500)
        format: Response format ('dict' or 'raw') - currently only 'dict' supported
    
    Returns:
        JSON response with candles or error
    """
    # Validate limit
    limit = max(1, min(500, limit))
    
    # Check if streamer is available
    if multi_tf_streamer is None:
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "error": "Streamer not initialized",
                "error_code": "STREAMER_NOT_INITIALIZED"
            }
        )
    
    # Check if streamer is running
    if not hasattr(multi_tf_streamer, 'is_running') or not multi_tf_streamer.is_running:
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "error": "Streamer not running",
                "error_code": "STREAMER_NOT_RUNNING"
            }
        )
    
    # Normalize symbol
    symbol_norm = normalize_symbol(symbol)
    
    # Validate timeframe
    valid_timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4']
    if timeframe.upper() not in valid_timeframes:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": f"Invalid timeframe. Must be one of: {valid_timeframes}",
                "error_code": "INVALID_TIMEFRAME",
                "timeframe": timeframe
            }
        )
    
    try:
        # Get candles from streamer
        candles = multi_tf_streamer.get_candles(symbol_norm, timeframe.upper(), limit=limit)
        
        if candles is None or len(candles) == 0:
            return {
                "success": False,
                "error": f"Symbol '{symbol_norm}' not found in streamer or no candles available",
                "error_code": "SYMBOL_NOT_FOUND",
                "symbol": symbol_norm,
                "timeframe": timeframe.upper()
            }
        
        # Convert Candle objects to dicts
        candle_dicts = []
        for candle in candles:
            if hasattr(candle, 'to_dict'):
                candle_dict = candle.to_dict()
                # Convert datetime to timestamp for JSON serialization
                if 'time' in candle_dict and isinstance(candle_dict['time'], datetime):
                    candle_dict['time'] = int(candle_dict['time'].timestamp())
                elif 'time' in candle_dict and isinstance(candle_dict['time'], str):
                    # Already ISO format string, keep as is
                    pass
                candle_dicts.append(candle_dict)
            elif hasattr(candle, 'open'):
                # Manual conversion if to_dict() not available
                candle_dict = {
                    'time': int(candle.time.timestamp()) if hasattr(candle.time, 'timestamp') else candle.time,
                    'open': float(candle.open),
                    'high': float(candle.high),
                    'low': float(candle.low),
                    'close': float(candle.close),
                    'volume': int(candle.volume) if hasattr(candle, 'volume') else 0,
                    'spread': float(candle.spread) if hasattr(candle, 'spread') else 0.0
                }
                candle_dicts.append(candle_dict)
            else:
                # Already a dict
                candle_dicts.append(candle)
        
        return {
            "success": True,
            "symbol": symbol_norm,
            "timeframe": timeframe.upper(),
            "count": len(candle_dicts),
            "candles": candle_dicts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "streamer_buffer"
        }
        
    except Exception as e:
        logger.error(f"Error getting candles from streamer: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": f"Internal server error: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "symbol": symbol_norm,
                "timeframe": timeframe.upper()
            }
        )

@app.get("/streamer/status", tags=["streamer"])
async def get_streamer_status() -> Dict[str, Any]:
    """Get MultiTimeframeStreamer status and metrics"""
    if multi_tf_streamer is None:
        return {
            "success": False,
            "running": False,
            "error": "Streamer not initialized"
        }
    
    try:
        # Get streamer metrics
        metrics = getattr(multi_tf_streamer, 'metrics', {})
        
        # Get available symbols and timeframes
        symbols = []
        timeframes = []
        if hasattr(multi_tf_streamer, 'buffers'):
            symbols = list(multi_tf_streamer.buffers.keys())
            if symbols:
                # Get timeframes from first symbol
                first_symbol = symbols[0]
                if first_symbol in multi_tf_streamer.buffers:
                    timeframes = list(multi_tf_streamer.buffers[first_symbol].keys())
        
        return {
            "success": True,
            "running": getattr(multi_tf_streamer, 'is_running', False),
            "symbols": symbols,
            "timeframes": timeframes,
            "metrics": {
                "total_candles_buffered": metrics.get('total_candles_stored', 0),
                "last_update": metrics.get('last_update', None),
                "memory_usage_mb": metrics.get('memory_usage_mb', 0.0),
                "db_size_mb": metrics.get('db_size_mb', 0.0),
                "errors": metrics.get('errors', 0)
            }
        }
    except Exception as e:
        logger.error(f"Error getting streamer status: {e}", exc_info=True)
        return {
            "success": False,
            "running": False,
            "error": str(e)
        }

@app.get("/streamer/available", tags=["streamer"])
async def get_streamer_available() -> Dict[str, Any]:
    """Get available symbols and timeframes from streamer"""
    if multi_tf_streamer is None:
        return {
            "success": False,
            "symbols": {},
            "error": "Streamer not initialized"
        }
    
    try:
        symbols_data = {}
        if hasattr(multi_tf_streamer, 'buffers'):
            for symbol, timeframes_dict in multi_tf_streamer.buffers.items():
                symbols_data[symbol] = list(timeframes_dict.keys())
        
        return {
            "success": True,
            "symbols": symbols_data
        }
    except Exception as e:
        logger.error(f"Error getting available symbols: {e}", exc_info=True)
        return {
            "success": False,
            "symbols": {},
            "error": str(e)
        }

@app.get("/streamer/health", tags=["streamer"])
async def get_streamer_health() -> Dict[str, Any]:
    """Health check for streamer"""
    if multi_tf_streamer is None:
        return {
            "status": "unhealthy",
            "streamer_running": False,
            "buffer_status": "unknown",
            "last_check": datetime.now(timezone.utc).isoformat(),
            "error": "Streamer not initialized"
        }
    
    try:
        is_running = getattr(multi_tf_streamer, 'is_running', False)
        buffer_status = "ok" if is_running else "not_running"
        
        return {
            "status": "healthy" if is_running else "unhealthy",
            "streamer_running": is_running,
            "buffer_status": buffer_status,
            "last_check": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error checking streamer health: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "streamer_running": False,
            "buffer_status": "error",
            "last_check": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }

# Risk management endpoints
@app.get("/risk/go-nogo", tags=["risk"])
async def get_go_nogo_status() -> Dict[str, Any]:
    """Get current go/no-go criteria status"""
    try:
        from infra.go_nogo_criteria import get_go_nogo_criteria
        criteria = get_go_nogo_criteria()
        assessment = criteria.assess_system_status()
        return {
            "overall_status": assessment.overall_status,
            "violations": [v.dict() for v in assessment.violations],
            "timestamp": assessment.timestamp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Go/No-Go status check failed: {str(e)}")

@app.get("/risk/rollback", tags=["risk"])
async def get_rollback_status() -> Dict[str, Any]:
    """Get rollback mechanism status"""
    try:
        from infra.rollback_mechanism import get_rollback_mechanism
        mechanism = get_rollback_mechanism()
        should_rollback, reason = mechanism.check_rollback_criteria()
        return {
            "should_rollback": should_rollback,
            "reason": reason,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback status check failed: {str(e)}")

@app.post("/risk/rollback", tags=["risk"])
async def execute_rollback() -> Dict[str, Any]:
    """Manually trigger rollback"""
    try:
        from infra.rollback_mechanism import get_rollback_mechanism
        mechanism = get_rollback_mechanism()
        result = mechanism.execute_rollback()
        return {
            "success": result,
            "message": "Rollback executed" if result else "Rollback failed",
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback execution failed: {str(e)}")

@app.get("/risk/staged-activation", tags=["risk"])
async def get_staged_activation_status() -> Dict[str, Any]:
    """Get staged activation status"""
    try:
        from infra.staged_activation_system import get_staged_activation_system
        system = get_staged_activation_system()
        status = system.get_activation_status()
        return {
            "current_stage": status.current_stage,
            "activation_date": status.activation_date,
            "rollback_count": status.rollback_count,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Staged activation status check failed: {str(e)}")

@app.post("/risk/staged-activation/activate", tags=["risk"])
async def activate_next_stage() -> Dict[str, Any]:
    """Activate next stage in staged activation"""
    try:
        from infra.staged_activation_system import get_staged_activation_system
        system = get_staged_activation_system()
        success, message = system.activate_next_stage()
        return {
            "success": success,
            "message": message,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stage activation failed: {str(e)}")

# Multi-timeframe database endpoints
@app.get("/mtf/status", tags=["mtf"])
async def get_mtf_database_status() -> Dict[str, Any]:
    """Get multi-timeframe database status"""
    try:
        from infra.mtf_database_schema import MTFDatabaseSchema
        db = MTFDatabaseSchema("data/mtf_trading.db")
        db.connect()
        
        # Get table counts
        cursor = db.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM mtf_structure_analysis")
        structure_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM mtf_m1_filters")
        filters_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM mtf_trade_signals")
        signals_count = cursor.fetchone()[0]
        
        return {
            "status": "active",
            "tables": {
                "structure_analysis": structure_count,
                "m1_filters": filters_count,
                "trade_signals": signals_count
            },
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MTF database status check failed: {str(e)}")

@app.post("/mtf/cleanup", tags=["mtf"])
async def cleanup_mtf_database() -> Dict[str, Any]:
    """Manually trigger MTF database cleanup"""
    try:
        from infra.mtf_database_schema import MTFDatabaseSchema
        db = MTFDatabaseSchema("data/mtf_trading.db")
        db.connect()
        
        # Clean up data older than 30 days
        cutoff_timestamp = int((time.time() - (30 * 24 * 60 * 60)) * 1000)
        
        cursor = db.connection.cursor()
        cursor.execute("DELETE FROM mtf_structure_analysis WHERE timestamp_utc < ?", (cutoff_timestamp,))
        structure_deleted = cursor.rowcount
        
        cursor.execute("DELETE FROM mtf_m1_filters WHERE timestamp_utc < ?", (cutoff_timestamp,))
        filters_deleted = cursor.rowcount
        
        cursor.execute("DELETE FROM mtf_trade_signals WHERE timestamp_utc < ?", (cutoff_timestamp,))
        signals_deleted = cursor.rowcount
        
        db.connection.commit()
        
        return {
            "success": True,
            "deleted_records": {
                "structure_analysis": structure_deleted,
                "m1_filters": filters_deleted,
                "trade_signals": signals_deleted
            },
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MTF database cleanup failed: {str(e)}")

@app.get("/mtf/optimization", tags=["mtf"])
async def get_mtf_optimization_status() -> Dict[str, Any]:
    """Get MTF database optimization status"""
    try:
        from infra.database_optimization_validation import get_database_optimization_validator
        validator = get_database_optimization_validator()
        report = validator.generate_report()
        
        return {
            "optimization_score": report.overall_score,
            "status": report.status.value,
            "recommendations": report.recommendations,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MTF optimization status check failed: {str(e)}")

@app.get("/mtf/symbol-optimization/{symbol}", tags=["mtf"])
async def get_symbol_optimization_status(symbol: str) -> Dict[str, Any]:
    """Get symbol optimization status and history"""
    try:
        from infra.symbol_optimizer import get_symbol_optimizer
        optimizer = get_symbol_optimizer()
        
        # Get latest performance
        performance = optimizer.get_latest_performance(symbol)
        
        # Get optimization history
        history = optimizer.get_optimization_history(symbol, limit=10)
        
        return {
            "symbol": symbol,
            "latest_performance": performance.__dict__ if performance else None,
            "optimization_history": [h.__dict__ for h in history],
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Symbol optimization status check failed: {str(e)}")

@app.post("/mtf/symbol-optimization/{symbol}", tags=["mtf"])
async def optimize_symbol(symbol: str, metric: str) -> Dict[str, Any]:
    """Manually trigger symbol optimization"""
    try:
        from infra.symbol_optimizer import get_symbol_optimizer, OptimizationMetric
        optimizer = get_symbol_optimizer()
        
        # Parse metric
        try:
            opt_metric = OptimizationMetric(metric)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid metric: {metric}")
        
        # Run optimization
        result = optimizer.optimize_symbol(symbol, opt_metric)
        
        if result:
            return {
                "success": True,
                "result": result.__dict__,
                "timestamp": time.time()
            }
        else:
            return {
                "success": False,
                "message": "Optimization not possible (insufficient data or no improvement found)",
                "timestamp": time.time()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Symbol optimization failed: {str(e)}")

@app.get("/mtf/symbol-optimization/summary", tags=["mtf"])
async def get_optimization_summary() -> Dict[str, Any]:
    """Get overall symbol optimization summary"""
    try:
        from infra.symbol_optimizer import get_symbol_optimizer
        optimizer = get_symbol_optimizer()
        
        summary = optimizer.get_optimization_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization summary failed: {str(e)}")

# Optional: Shadow mode toggle
@app.post("/shadow-mode", tags=["shadow"])
async def toggle_shadow_mode(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _shadow_mode_available:
        raise HTTPException(status_code=404, detail="Shadow mode not available")
    controller = get_shadow_mode_controller()
    enabled = bool(payload.get("enabled", True))
    symbol = payload.get("symbol")
    if enabled:
        controller.enable(symbol)
    else:
        controller.disable(symbol)
    return {"enabled": enabled, "symbol": symbol}

# Optional: Decision trace fetch
@app.get("/decision-traces/{trace_id}", tags=["traces"])
async def get_decision_trace(trace_id: str) -> Dict[str, Any]:
    if not _decision_traces_available:
        raise HTTPException(status_code=404, detail="Decision traces not available")
    mgr = get_decision_trace_manager()
    trace = mgr.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace

# Validation trigger endpoint (optional)
@app.post("/validate", tags=["validation"])
async def run_validations(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    results: Dict[str, Any] = {"requested": payload or {}}

    # Structure validation
    try:
        if _structure_val_available:
            system = StructureValidationSystem()
            rep = system.run_validation({})
            results["structure"] = {
                "status": getattr(rep, "status", "unknown"),
                "accuracy": getattr(rep, "accuracy", None),
                "total_points": getattr(rep, "total_points", None),
            }
        else:
            results["structure"] = {"status": "unavailable"}
    except Exception as e:
        results["structure"] = {"status": "error", "error": str(e)}

    # Latency validation
    try:
        if _latency_val_available:
            validator = LatencyValidator()
            rep = validator.validate_latency()
            results["latency"] = {
                "status": getattr(rep, "status", "unknown"),
                "p95_ms": getattr(rep, "p95_ms", None),
                "meets_target": getattr(rep, "meets_target", None),
            }
        else:
            results["latency"] = {"status": "unavailable"}
    except Exception as e:
        results["latency"] = {"status": "error", "error": str(e)}

    # Database performance validation
    try:
        if _db_val_available:
            mgr = DatabasePerformanceManager()
            rep = mgr.run_validation()
            results["database"] = {
                "status": getattr(rep, "overall_status", "unknown"),
                "avg_time_ms": getattr(rep, "average_execution_time_ms", None),
                "passed": getattr(rep, "passed", None),
            }
        else:
            results["database"] = {"status": "unavailable"}
    except Exception as e:
        results["database"] = {"status": "error", "error": str(e)}

    # Overall
    results["ok"] = True
    return results

# ============================================================================
# IDEMPOTENCY SUPPORT
# ============================================================================

IDEMPOTENCY_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL", "600"))
_idempotency_cache: Dict[str, Dict[str, Any]] = {}
_idempotency_lock = asyncio.Lock()


async def _get_idempotent_response(key: Optional[str]) -> Optional[Dict[str, Any]]:
    if not key:
        return None
    async with _idempotency_lock:
        # Cleanup expired entries
        now = datetime.utcnow()
        expired = []
        for k, v in _idempotency_cache.items():
            ts = v.get("ts")
            if isinstance(ts, datetime) and now - ts > timedelta(seconds=IDEMPOTENCY_TTL_SECONDS):
                expired.append(k)
        for k in expired:
            _idempotency_cache.pop(k, None)

        entry = _idempotency_cache.get(key)
        if not entry:
            return None
        return entry.get("response")


async def _set_idempotent_response(key: Optional[str], response: Dict[str, Any]) -> None:
    if not key:
        return
    async with _idempotency_lock:
        _idempotency_cache[key] = {"response": response, "ts": datetime.utcnow()}

# ============================================================================
# REQUEST LOGGING (logs database)
# ============================================================================

async def _log_api_request(endpoint: str, method: str, status_code: int, response_time: float, details: Optional[str] = None):
    """Log API request to logs database when separate DB architecture is enabled."""
    if not db_manager:
        return
    try:
        with db_manager.get_logs_db_connection(read_only=False) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS api_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT,
                    method TEXT,
                    status_code INTEGER,
                    response_time REAL,
                    timestamp REAL,
                    details TEXT
                )
                """
            )
            cur.execute(
                """
                INSERT INTO api_logs (endpoint, method, status_code, response_time, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (endpoint, method, status_code, response_time, datetime.utcnow().timestamp(), details),
            )
            conn.commit()
    except Exception as e:
        logger.debug(f"Could not log API request: {e}")

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
multi_tf_streamer: Optional[MultiTimeframeStreamer] = None
server_exit_manager = None
startup_time = datetime.now()
oco_monitor_task: Optional[asyncio.Task] = None
oco_monitor_running = False
dtms_monitor_task: Optional[asyncio.Task] = None
dtms_monitor_running = False
tick_metrics_generator = None  # Tick metrics generator for analyse_symbol_full

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
    
    try:
        while oco_monitor_running:
            try:
                if mt5_service:
                    actions = oco_tracker.monitor_oco_pairs(mt5_service)
                    if actions:
                        for oco_id, action in actions.items():
                            logger.info(f"OCO Monitor - {oco_id}: {action}")
                            # Auto-enable Advanced exits for newly filled bracket legs
                            try:
                                if isinstance(action, dict) and action.get("event") == "filled":
                                    filled_ticket = int(action.get("filled_ticket")) if action.get("filled_ticket") else None
                                    symbol = str(action.get("symbol")) if action.get("symbol") else None
                                    if not filled_ticket or not symbol:
                                        continue
                                    import MetaTrader5 as mt5
                                    if not mt5_service.connect():
                                        continue
                                    pos = None
                                    positions = mt5.positions_get()
                                    if positions:
                                        pos = next((p for p in positions if p.ticket == filled_ticket), None)
                                    if not pos:
                                        continue
                                    direction = "buy" if pos.type == mt5.ORDER_TYPE_BUY else "sell"
                                    # Build Advanced features snapshot for gating
                                    adv = None
                                    try:
                                        from infra.feature_builder_advanced import build_features_advanced
                                        adv = build_features_advanced(
                                            symbol=pos.symbol,
                                            mt5svc=mt5_service,
                                            bridge=indicator_bridge,
                                            timeframes=["M15", "M5", "H1"],
                                        )
                                    except Exception:
                                        adv = None
                                    if server_exit_manager is not None:
                                        server_exit_manager.add_rule_advanced(
                                            ticket=pos.ticket,
                                            symbol=pos.symbol,
                                            entry_price=pos.price_open,
                                            direction=direction,
                                            initial_sl=pos.sl,
                                            initial_tp=pos.tp,
                                            advanced_features=adv,
                                        )
                                        logger.info(f"OCO auto-enabled Advanced exits for ticket {pos.ticket} ({pos.symbol})")
                            except Exception as e:
                                logger.warning(f"OCO auto-enable hook failed: {e}")
            except Exception as e:
                logger.error(f"OCO monitor error: {e}", exc_info=True)
                # Continue monitoring despite error
            
            try:
                await asyncio.sleep(3)  # Check every 3 seconds
            except asyncio.CancelledError:
                break
    except Exception as fatal_error:
        logger.critical(f"FATAL ERROR in OCO monitor loop: {fatal_error}", exc_info=True)
        oco_monitor_running = False
    finally:
        logger.info("OCO monitor stopped")

# PHASE 5: DTMS monitoring loop removed - using API server instead
# DTMS monitoring is now handled by dtms_api_server.py (port 8001)
# This function is kept for backward compatibility but does nothing
async def dtms_monitor_loop():
    """Background task that runs DTMS monitoring cycle - PHASE 5: Disabled (using API server)"""
    # DTMS monitoring is now handled by dtms_api_server.py
    # No local monitoring needed
    logger.info("ℹ️ DTMS monitor loop disabled - using API server (port 8001) instead")
    return
    
    # OLD CODE (commented out for rollback):
    # global dtms_monitor_running
    # 
    # logger.info("DTMS monitor starting...")
    # dtms_monitor_running = True
    # 
    # try:
    #     while dtms_monitor_running:
    #         try:
    #             # Run DTMS monitoring cycle for all active trades
    #             await run_dtms_monitoring_cycle()
    #         except Exception as e:
    #             logger.error(f"DTMS monitor error: {e}", exc_info=True)
    #             # Continue monitoring despite error
    #         
    #         try:
    #             await asyncio.sleep(30)  # Check every 30 seconds
    #         except asyncio.CancelledError:
    #             break
    # except Exception as fatal_error:
    #     logger.critical(f"FATAL ERROR in DTMS monitor loop: {fatal_error}", exc_info=True)
    #     dtms_monitor_running = False
    # finally:
    #     logger.info("DTMS monitor stopped")

async def startup_event():
    """Initialize services on startup"""
    global mt5_service, journal_repo, indicator_bridge, multi_tf_streamer, startup_time, oco_monitor_task, dtms_monitor_task, liquidity_sweep_engine, confluence_calculator, m1_analyzer_cached, m1_data_fetcher_cached, tick_metrics_generator
    
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
        
        # Initialize indicator bridge with mt5_service
        indicator_bridge = IndicatorBridge(mt5_service)
        logger.info("Indicator bridge initialized")
        
        # Fix 18: Initialize singleton ConfluenceCalculator instance
        from infra.confluence_calculator import ConfluenceCalculator
        confluence_calculator = ConfluenceCalculator(indicator_bridge)
        logger.info("ConfluenceCalculator singleton initialized")
        
        # Fix 19: Pre-initialize M1 components for caching
        m1_analyzer_cached = None
        m1_data_fetcher_cached = None
        try:
            from infra.m1_data_fetcher import M1DataFetcher
            from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
            
            if mt5_service and mt5_service.connect():
                m1_data_fetcher_cached = M1DataFetcher(
                    data_source=mt5_service,
                    max_candles=200,
                    cache_ttl=300
                )
                
                try:
                    from infra.m1_session_volatility_profile import SessionVolatilityProfile
                    from infra.m1_asset_profiles import AssetProfileManager
                    asset_profiles = AssetProfileManager("config/asset_profiles.json")
                    session_manager = SessionVolatilityProfile(asset_profiles)
                    m1_analyzer_cached = M1MicrostructureAnalyzer(
                        mt5_service=mt5_service,
                        session_manager=session_manager,
                        asset_profiles=asset_profiles
                    )
                    logger.info("M1 analyzer and fetcher cached (Fix 19)")
                except Exception as e:
                    logger.debug(f"M1 analyzer initialization with dependencies failed: {e}, trying fallback")
                    try:
                        m1_analyzer_cached = M1MicrostructureAnalyzer(mt5_service=mt5_service)
                        logger.info("M1 analyzer cached (fallback mode)")
                    except Exception as e2:
                        logger.debug(f"M1 analyzer fallback initialization failed: {e2}")
        except Exception as e:
            logger.debug(f"M1 components not available for caching: {e}")
        
        # Initialize a server-side exit manager to be used by OCO auto-enable
        try:
            from infra.intelligent_exit_manager import create_exit_manager as _create_exit_mgr
            global server_exit_manager
            server_exit_manager = _create_exit_mgr(
                mt5_service,
                advanced_provider=indicator_bridge,
            )
        except Exception as e:
            logger.warning(f"Server exit manager init failed: {e}")
        
        # Start OCO monitoring background task
        oco_monitor_task = asyncio.create_task(oco_monitor_loop())
        logger.info("OCO monitor task started")
        
        # ====================================================================
        # UNIFIED TICK PIPELINE - DISABLED FOR RESOURCE CONSERVATION
        # ====================================================================
        # DISABLED: The Unified Tick Pipeline with Binance WebSocket streams
        # is extremely resource-intensive (CPU ~10-20%, high RAM/SSD usage).
        # The system continues to function perfectly using:
        #   - Multi-Timeframe Streamer (lightweight MT5 candlestick data)
        #   - Direct MT5 calls (for ChatGPT analysis)
        #   - DTMS monitoring (already active)
        # 
        # If you need Binance tick-level data in the future, enable this
        # only on a dedicated server, not a personal laptop/desktop.
        # ====================================================================
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
        #     logger.warning(f"⚠️ Unified Tick Pipeline initialization failed: {e}")
        #     logger.info("   → Main API will continue with existing data sources")
        logger.info("ℹ️ Unified Tick Pipeline disabled for resource conservation")
        logger.info("   → Using lightweight Multi-Timeframe Streamer instead")
        
        # Initialize Liquidity Sweep Reversal Engine (Autonomous SMC Trading)
        try:
            logger.info("🔍 Initializing Liquidity Sweep Reversal Engine...")
            from infra.liquidity_sweep_reversal_engine import LiquiditySweepReversalEngine
            from discord_notifications import DiscordNotifier
            
            # Get intelligent exit manager if available
            liquidity_exit_manager = None
            if server_exit_manager:
                liquidity_exit_manager = server_exit_manager
                logger.info("   → Intelligent Exit Manager available for post-entry management")
            
            # Get Discord notifier
            discord_notifier = None
            try:
                discord_notifier = DiscordNotifier()
                if discord_notifier.enabled:
                    logger.info("   → Discord notifications enabled")
            except Exception as e:
                logger.debug(f"   → Discord notifications not available: {e}")
            
            # Initialize engine
            global liquidity_sweep_engine
            liquidity_sweep_engine = LiquiditySweepReversalEngine(
                mt5_service=mt5_service,
                intelligent_exit_manager=liquidity_exit_manager,
                discord_notifier=discord_notifier,
                config_path="config/liquidity_sweep_config.json"
            )
            
            # Start as background task
            await liquidity_sweep_engine.start()
            logger.info("✅ Liquidity Sweep Reversal Engine started")
            logger.info("   → Monitoring BTCUSD and XAUUSD for liquidity sweeps")
            logger.info("   → Three-layer confluence stack (Macro → Setup → Trigger)")
            logger.info("   → Automatic reversal trade execution when confluence ≥70%")
            
        except Exception as e:
            logger.warning(f"⚠️ Liquidity Sweep Reversal Engine initialization failed: {e}")
            logger.info("   → Main API will continue without autonomous sweep trading")
        
        # ========== TICK METRICS GENERATOR ==========
        global tick_metrics_generator
        try:
            logger.info("📊 Initializing Tick Metrics Generator...")
            from infra.tick_metrics.tick_snapshot_generator import TickSnapshotGenerator
            
            tick_metrics_generator = TickSnapshotGenerator(
                symbols=["BTCUSDc", "XAUUSDc", "EURUSDc", "USDJPYc", "GBPUSDc"],
                update_interval_seconds=60
                # Note: Uses direct MT5 calls internally, not mt5_service
            )
            await tick_metrics_generator.start()
            set_tick_metrics_instance(tick_metrics_generator)
            logger.info("✅ Tick Metrics Generator started")
            logger.info("   → Pre-aggregating M5/M15/H1 tick metrics every 60s")
            logger.info("   → Provides tick_metrics field for analyse_symbol_full")
        except Exception as e:
            logger.warning(f"⚠️ Tick Metrics Generator failed to start: {e}", exc_info=True)
            logger.info("   → Analysis will continue without tick_metrics field")
            tick_metrics_generator = None  # Ensure it's None if startup failed
            # Non-fatal - analysis continues without tick metrics
        
        # Initialize DTMS (Defensive Trade Management System)
        try:
            logger.info("🛡️ Initializing DTMS system...")
            # Initialize and start Binance service (required for order flow)
            binance_service = None
            try:
                from infra.binance_service import BinanceService
                logger.info("   → Initializing Binance service for order flow...")
                binance_service = BinanceService(interval="1m")
                binance_service.set_mt5_service(mt5_service)
                
                # Start Binance service automatically
                symbols_to_stream = ["btcusdt"]  # BTCUSD only
                await binance_service.start(symbols_to_stream, background=True)
                logger.info(f"   → Binance service started and streaming {len(symbols_to_stream)} symbol(s)")
                logger.info("   → Binance service available for order flow and DTMS")
                
                # Store in global registry for auto-execution system access
                try:
                    from desktop_agent import registry
                    registry.binance_service = binance_service
                    logger.info("   → Binance service registered in global registry")
                except Exception:
                    pass  # Registry not available, continue anyway
                    
            except Exception as e:
                logger.warning(f"   → Binance service initialization failed: {e}")
                logger.warning("   → Order flow conditions will not work until Binance service is running")
                binance_service = None
            
            # Initialize Order Flow Service (requires Binance service)
            order_flow_service = None
            try:
                # First try to get from registry (if desktop_agent has set it)
                try:
                    from desktop_agent import registry
                    order_flow_service = getattr(registry, 'order_flow_service', None)
                    if order_flow_service and hasattr(order_flow_service, 'running') and order_flow_service.running:
                        logger.info("   → Order Flow Service available from desktop_agent (BTCUSD only)")
                except Exception:
                    pass
                
                # If not available from registry, try to initialize here if Binance is running
                if not order_flow_service and binance_service and binance_service.running:
                    try:
                        from infra.order_flow_service import OrderFlowService
                        logger.info("   → Initializing Order Flow Service...")
                        order_flow_service = OrderFlowService()
                        
                        # Start order flow service
                        order_flow_symbols = ["btcusdt"]  # BTCUSD only
                        await order_flow_service.start(order_flow_symbols, background=True)
                        
                        logger.info("✅ Order Flow Service initialized and started")
                        logger.info("   📊 Order book depth: Active (20 levels @ 100ms)")
                        logger.info("   🐋 Whale detection: Active ($50k+ orders)")
                        logger.info(f"   ⚠️ Supported symbols: BTCUSD only (crypto pairs only)")
                        
                        # Store in global registry for auto-execution system access
                        try:
                            from desktop_agent import registry
                            registry.order_flow_service = order_flow_service
                            logger.info("   → Order Flow Service registered in global registry")
                        except Exception:
                            pass  # Registry not available, continue anyway
                            
                    except Exception as e:
                        logger.warning(f"   → Order Flow Service initialization failed: {e}")
                        logger.warning("   → Order flow conditions will not work until service is running")
                elif not binance_service or not binance_service.running:
                    logger.debug("   → Order Flow Service not initialized (Binance service not running)")
            except Exception as e:
                logger.debug(f"   → Order Flow Service check failed: {e}")
            
            # PHASE 5: DTMS initialization removed - using API server instead
            # DTMS is now initialized only in dtms_api_server.py (port 8001)
            # All DTMS operations route through API server
            logger.info("ℹ️ DTMS initialization skipped - using API server (port 8001) instead")
            logger.info("   → DTMS endpoints will fall back to API server if local engine unavailable")
            
            # OLD CODE (commented out for rollback):
            # dtms_init_success = initialize_dtms(
            #     mt5_service=mt5_service,
            #     binance_service=binance_service,
            #     telegram_service=None,  # No telegram service in main API
            #     order_flow_service=order_flow_service  # NEW: Pass OrderFlowService
            # )
            # 
            # if dtms_init_success:
            #     # Start DTMS monitoring
            #     dtms_monitoring_started = start_dtms_monitoring()
            #     if dtms_monitoring_started:
            #         # Start DTMS monitoring background task
            #         dtms_monitor_task = asyncio.create_task(dtms_monitor_loop())
            #         logger.info("✅ DTMS initialized and monitoring started")
            #         logger.info("   → Automatic hedge placement when trades go against you")
            #         logger.info("   → State machine: HEALTHY → WARNING_L1 → WARNING_L2 → HEDGED")
            #         logger.info("   → Score-based defensive actions")
            #         logger.info("   → Monitoring cycle: every 30 seconds")
            #     else:
            #         logger.warning("⚠️ DTMS initialized but monitoring failed to start")
            # else:
            #     logger.error("❌ DTMS initialization failed")
        except Exception as e:
            logger.error(f"❌ DTMS initialization error: {e}", exc_info=True)
        
        # Initialize Multi-Timeframe Streamer
        try:
            logger.info("📊 Initializing Multi-Timeframe Streamer...")
            
            # Load configuration
            config_path = Path("config/multi_tf_streamer_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                
                # Check if it's weekend (Saturday or Sunday) - only stream BTC on weekends
                current_day = datetime.now().weekday()  # 5 = Saturday, 6 = Sunday
                is_weekend = current_day >= 5
                
                all_symbols = config_data.get("symbols", ["BTCUSDc", "XAUUSDc"])
                if is_weekend:
                    # Filter to only BTC on weekends
                    symbols_to_stream = [s for s in all_symbols if "BTC" in s.upper()]
                    if not symbols_to_stream:
                        # Fallback if BTC not in config
                        symbols_to_stream = ["BTCUSDc"]
                    logger.info(f"   📅 Weekend detected - streaming BTC only: {symbols_to_stream}")
                else:
                    symbols_to_stream = all_symbols
                    logger.info(f"   📅 Weekday - streaming all symbols: {symbols_to_stream}")
                
                # Create StreamerConfig from loaded data
                streamer_config = StreamerConfig(
                    symbols=symbols_to_stream,
                    buffer_sizes=config_data.get("buffer_sizes", {
                        "M1": 1440, "M5": 300, "M15": 150, "M30": 100, "H1": 100, "H4": 50
                    }),
                    refresh_intervals=config_data.get("refresh_intervals", {
                        "M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400
                    }),
                    enable_database=config_data.get("enable_database", False),
                    db_path=config_data.get("db_path", "data/multi_tf_candles.db"),
                    retention_days=config_data.get("retention_days", 30),
                    max_memory_mb=config_data.get("max_memory_mb", 100.0),
                    max_db_size_mb=config_data.get("max_db_size_mb", 500.0),
                    batch_write_size=config_data.get("batch_write_size", 20)
                )
            else:
                # Default configuration if file doesn't exist
                logger.warning(f"Config file not found at {config_path}, using defaults")
                
                # Check if it's weekend (Saturday or Sunday) - only stream BTC on weekends
                current_day = datetime.now().weekday()  # 5 = Saturday, 6 = Sunday
                is_weekend = current_day >= 5
                
                if is_weekend:
                    default_symbols = ["BTCUSDc"]
                    logger.info(f"   📅 Weekend detected - streaming BTC only: {default_symbols}")
                else:
                    default_symbols = ["BTCUSDc", "XAUUSDc"]
                    logger.info(f"   📅 Weekday - streaming all symbols: {default_symbols}")
                
                streamer_config = StreamerConfig(
                    symbols=default_symbols,
                    enable_database=False  # RAM only for safety
                )
            
            # Create and start streamer
            multi_tf_streamer = MultiTimeframeStreamer(streamer_config, mt5_service=mt5_service)
            await multi_tf_streamer.start()
            
            logger.info("✅ Multi-Timeframe Streamer initialized and started")
            logger.info(f"   → Streaming {len(streamer_config.symbols)} symbols")
            
            # Register streamer with data access helper for Intelligent Exits & DTMS
            try:
                from infra.streamer_data_access import set_streamer
                set_streamer(multi_tf_streamer)
                logger.info("   → Streamer registered for Intelligent Exits & DTMS access")
            except Exception as e:
                logger.warning(f"   → Failed to register streamer: {e}")
            
            logger.info("   → Streamer API endpoints available at /streamer/*")
            logger.info(f"   → Timeframes: {', '.join(streamer_config.buffer_sizes.keys())}")
            logger.info(f"   → Database: {'enabled' if streamer_config.enable_database else 'disabled (RAM only)'}")
        except Exception as e:
            logger.error(f"❌ Multi-Timeframe Streamer initialization error: {e}", exc_info=True)
            logger.warning("   → Continuing without streamer (ChatGPT will use direct MT5 calls)")
        
        # NOTE: Micro-Scalp Monitor is initialized in root main_api.py (port 8010)
        # This server (app/main_api.py) focuses on Multi-Timeframe Streamer and other services
        logger.info("ℹ️ Micro-Scalp Monitor runs on root main_api.py (port 8010)")
        
        # Initialize and start Auto-Execution System
        try:
            logger.info("🤖 Initializing Auto-Execution System...")
            from auto_execution_system import start_auto_execution_system
            
            # Start the auto-execution system monitoring
            start_auto_execution_system()
            logger.info("✅ Auto-Execution System started")
            logger.info("   → Monitoring pending trade plans")
            logger.info("   → Checking conditions every 30 seconds")
            logger.info("   → Automatic execution when conditions are met")
        except Exception as e:
            logger.error(f"❌ Auto-Execution System initialization failed: {e}", exc_info=True)
            logger.warning("   → Auto-execution plans will not be monitored")
        
        startup_time = datetime.now()
        
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)

async def shutdown_event():
    """Cleanup on shutdown with timeouts to prevent hanging"""
    global oco_monitor_running, oco_monitor_task, dtms_monitor_running, dtms_monitor_task, multi_tf_streamer, liquidity_sweep_engine
    
    # Import stop function for auto-execution system
    try:
        from auto_execution_system import stop_auto_execution_system
    except ImportError:
        stop_auto_execution_system = None
    
    logger.info("Shutting down API server...")
    
    # Handle cancellation gracefully - wrap entire shutdown in try/except
    try:
        # Use asyncio.wait_for with timeout to prevent hanging
        async def stop_with_timeout(coro, timeout=5.0, name="service"):
            try:
                await asyncio.wait_for(coro, timeout=timeout)
                logger.info(f"{name} stopped")
            except asyncio.CancelledError:
                # Normal cancellation during shutdown
                logger.debug(f"{name} shutdown cancelled (normal)")
            except asyncio.TimeoutError:
                logger.warning(f"{name} shutdown timed out after {timeout}s - forcing continue")
            except Exception as e:
                logger.warning(f"Error stopping {name}: {e}")
        
        # Stop Liquidity Sweep Reversal Engine
        if 'liquidity_sweep_engine' in globals() and liquidity_sweep_engine:
            await stop_with_timeout(liquidity_sweep_engine.stop(), timeout=3.0, name="Liquidity Sweep Reversal Engine")
        
        # Stop Tick Metrics Generator
        if 'tick_metrics_generator' in globals() and tick_metrics_generator:
            await stop_with_timeout(tick_metrics_generator.stop(), timeout=3.0, name="Tick Metrics Generator")
        
        # Stop OCO monitor
        oco_monitor_running = False
        if oco_monitor_task:
            try:
                oco_monitor_task.cancel()
                try:
                    await asyncio.wait_for(oco_monitor_task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                except Exception as e:
                    logger.debug(f"OCO monitor cancellation: {e}")
            except Exception as e:
                logger.debug(f"Error cancelling OCO monitor: {e}")
        logger.info("OCO monitor stopped")
        
        # Stop DTMS monitor
        dtms_monitor_running = False
        if dtms_monitor_task:
            try:
                dtms_monitor_task.cancel()
                try:
                    await asyncio.wait_for(dtms_monitor_task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                except Exception as e:
                    logger.debug(f"DTMS monitor cancellation: {e}")
            except Exception as e:
                logger.debug(f"Error cancelling DTMS monitor: {e}")
        logger.info("DTMS monitor stopped")
        
        # Stop DTMS monitoring (DTMS is currently disabled)
        # try:
        #     import concurrent.futures
        #     loop = asyncio.get_event_loop()
        #     with concurrent.futures.ThreadPoolExecutor() as executor:
        #         await asyncio.wait_for(
        #             loop.run_in_executor(executor, stop_dtms_monitoring),
        #             timeout=3.0
        #         )
        #     logger.info("DTMS system stopped")
        # except asyncio.TimeoutError:
        #     logger.warning("DTMS system shutdown timed out - forcing continue")
        # except Exception as e:
        #     logger.warning(f"Error stopping DTMS system: {e}")
        
        # Stop Micro-Scalp Monitor (synchronous, wrap in executor)
        # NOTE: Micro-Scalp Monitor is stopped in root main_api.py (port 8010)
        
        # Stop Multi-Timeframe Streamer
        if multi_tf_streamer:
            await stop_with_timeout(multi_tf_streamer.stop(), timeout=3.0, name="Multi-Timeframe Streamer")
        
        # Stop Auto-Execution System (synchronous, wrap in executor)
        if stop_auto_execution_system:
            try:
                import concurrent.futures
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    await asyncio.wait_for(
                        loop.run_in_executor(executor, stop_auto_execution_system),
                        timeout=5.0
                    )
                logger.info("Auto-Execution System stopped")
            except asyncio.TimeoutError:
                logger.warning("Auto-Execution System shutdown timed out - forcing continue")
            except Exception as e:
                logger.warning(f"Error stopping Auto-Execution System: {e}")
    
    except asyncio.CancelledError:
        # Normal cancellation during shutdown - don't re-raise, just log
        logger.info("Shutdown process cancelled (normal termination via Ctrl+C)")
    except KeyboardInterrupt:
        # Keyboard interrupt during shutdown - also normal
        logger.info("Shutdown interrupted (normal termination)")
    except Exception as e:
        logger.error(f"Unexpected error during shutdown: {e}", exc_info=True)
    
    logger.info("Shutdown complete")

# ============================================================================
# SYSTEM ENDPOINTS
# ============================================================================

@app.get("/micro-scalp/status", tags=["micro-scalp"])
async def get_micro_scalp_status() -> Dict[str, Any]:
    """Get Micro-Scalp Monitor status and statistics"""
    try:
        # NOTE: Micro-Scalp Monitor status is available on root main_api.py (port 8010)
        return {
            "ok": False,
            "status": {
                "monitoring": False,
                "enabled": False,
                "error": "Micro-Scalp Monitor runs on root main_api.py (port 8010). Check http://localhost:8010/micro-scalp/status"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting micro-scalp status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/micro-scalp/history", tags=["micro-scalp"])
async def get_micro_scalp_history(symbol: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """Get detailed check history for micro-scalp monitor"""
    try:
        # NOTE: Micro-Scalp Monitor history is available on root main_api.py (port 8010)
        return {
            "ok": False,
            "error": "Micro-Scalp Monitor runs on root main_api.py (port 8010). Check http://localhost:8010/micro-scalp/history",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting micro-scalp history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/micro-scalp/view", response_class=HTMLResponse, tags=["micro-scalp"])
async def micro_scalp_view():
    """Micro-Scalp Monitor Dashboard - Redirects to port 8010 where monitor runs"""
    # Redirect to port 8010 where micro-scalp monitor actually runs
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="http://localhost:8010/micro-scalp/view", status_code=307)

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with TradingView tickers"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MoneyBot v1.1 - Advanced AI Trading System</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial, sans-serif; margin: 24px; background: #0b1220; color: #e6edf3; }
            .container { max-width: 1600px; margin: 0 auto; }
            h1 { margin-bottom: 8px; color: #e6edf3; }
            .nav { margin-bottom: 20px; }
            .nav a { color: #9fb0c3; text-decoration: none; margin-right: 20px; }
            .nav a:hover { color: #e6edf3; }
            .tickers { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin: 20px 0; }
            .ticker-container { background: #111a2e; border: 1px solid #213352; padding: 15px; border-radius: 8px; }
            .ticker-label { color: #9fb0c3; font-size: 12px; text-transform: uppercase; margin-bottom: 10px; }
            .info { margin-top: 20px; padding: 15px; background: #111a2e; border: 1px solid #213352; border-radius: 8px; }
            .info h2 { color: #e6edf3; font-size: 18px; margin-bottom: 10px; }
            .info p { color: #9fb0c3; margin: 5px 0; }
            .info a { color: #90c0ff; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 MoneyBot v1.1 - Advanced AI Trading System</h1>
            <div class="nav">
                <a href="/">Home</a>
                <a href="/alerts/view">Alerts</a>
                <a href="/auto-execution/view">Auto Execution</a>
                <a href="/volatility-regime/monitor">Volatility Monitor</a>
                <a href="/dtms/status">DTMS Status</a>
                <a href="/dtms/actions">DTMS Actions</a>
                <a href="/scalps/view">Automated Scalps</a>
                <a href="/docs">API Docs</a>
            </div>
            
            <div class="tickers">
                <div class="ticker-container">
                    <div class="ticker-label">XAUUSD (Gold)</div>
                    <!-- TradingView Widget BEGIN -->
                    <div class="tradingview-widget-container">
                        <div class="tradingview-widget-container__widget"></div>
                        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
                        {
                        "symbol": "FX_IDC:XAUUSD",
                        "width": "100%",
                        "height": "400",
                        "locale": "en",
                        "dateRange": "1D",
                        "colorTheme": "dark",
                        "isTransparent": true,
                        "autosize": true,
                        "largeChartUrl": ""
                        }
                        </script>
                    </div>
                    <!-- TradingView Widget END -->
                </div>
                
                <div class="ticker-container">
                    <div class="ticker-label">BTCUSD (Bitcoin)</div>
                    <!-- TradingView Widget BEGIN -->
                    <div class="tradingview-widget-container">
                        <div class="tradingview-widget-container__widget"></div>
                        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
                        {
                        "symbol": "BINANCE:BTCUSDT",
                        "width": "100%",
                        "height": "400",
                        "locale": "en",
                        "dateRange": "1D",
                        "colorTheme": "dark",
                        "isTransparent": true,
                        "autosize": true,
                        "largeChartUrl": ""
                        }
                        </script>
                    </div>
                    <!-- TradingView Widget END -->
                </div>
            </div>
            
            <div class="info">
                <h2>System Information</h2>
                <p><strong>Service:</strong> MoneyBot v1.1 - Advanced AI Trading System API</p>
                <p><strong>Version:</strong> 1.1.0</p>
                <p><strong>Status:</strong> Running</p>
                <p><strong>API Documentation:</strong> <a href="/docs" style="color: #90c0ff;">/docs</a></p>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check (merged with separate database architecture details)."""
    start = datetime.utcnow()
    mt5_ok = False
    try:
        if mt5_service:
            mt5_service.connect()
            bal, _ = mt5_service.account_bal_eq()
            mt5_ok = bal is not None
    except Exception:
        mt5_ok = False

    # Database status via separate DB architecture (if available)
    db_status = None
    access_permissions = None
    if db_manager:
        try:
            db_status = db_manager.get_database_status()
            access_permissions = db_manager.access_permissions
        except Exception as e:
            logger.debug(f"Health DB status error: {e}")

    resp = {
        "ok": True,
        "timestamp": datetime.utcnow().isoformat(),
        "database_architecture": "separate_databases" if db_manager else "single",
        "components": {
            "mt5_connection": "healthy" if mt5_ok else "warning",
            "telegram_api": "healthy",
            "database": "healthy" if (journal_repo or db_status) else "warning",
            "system_resources": "healthy",
        },
    }

    # Attach DB details when available
    if db_status is not None:
        resp["database_status"] = db_status
    if access_permissions is not None:
        resp["access_permissions"] = access_permissions

    # Log to logs DB (best-effort)
    try:
        elapsed = (datetime.utcnow() - start).total_seconds()
        await _log_api_request("/health", "GET", 200, elapsed, "Health check")
    except Exception:
        pass

    return resp

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
    Send trade signal to Discord for approval.
    This creates a recommendation that the user can approve/reject via Discord.
    """
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        # Normalize symbol
        symbol = signal.symbol.upper()
        if not symbol.endswith('c'):
            symbol = symbol + 'c'
        
        logger.info(f"Trade signal received: {signal.direction.upper()} {symbol} @ {signal.entry_price}")
        
        # TODO: Send to Discord bot for approval
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
async def execute_trade(
    signal: TradeSignal,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> ExecutionResponse:
    """
    Execute trade directly in MT5 (bypasses Discord approval).
    """
    # Check go/no-go criteria before executing trade
    try:
        from infra.go_nogo_criteria import get_go_nogo_criteria
        criteria = get_go_nogo_criteria()
        assessment = criteria.assess_system_status()
        if not assessment.overall_status:
            raise HTTPException(
                status_code=403, 
                detail=f"Trade blocked by Go/No-Go criteria: {[v.description for v in assessment.violations]}"
            )
    except Exception as e:
        logger.warning(f"⚠️ Go/No-Go criteria check failed: {e}")
        # Continue with trade execution if criteria check fails
    
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        # Idempotency: return cached response if this key was seen recently
        cached = await _get_idempotent_response(idempotency_key)
        if cached is not None:
            return cached  # type: ignore[return-value]
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
        
        # For MARKET orders, use current price; for LIMIT orders, use specified entry
        is_market_order = not signal.order_type or signal.order_type == OrderType.MARKET
        
        if is_market_order:
            # Check if entry price is significantly different from current price
            price_diff_pct = abs(signal.entry_price - current_price) / current_price * 100
            if price_diff_pct > 1:  # More than 1% difference
                logger.warning(
                    f"Price moved since analysis! ChatGPT entry: {signal.entry_price}, "
                    f"MT5 current: {current_price:.5f} (diff: {price_diff_pct:.2f}%)"
                )
                logger.info(f"Using current market price {current_price:.5f} for MARKET order")
            
            # Use current market price for market orders
            actual_entry = current_price
        else:
            # Use specified entry price for limit/stop orders
            actual_entry = signal.entry_price
            logger.info(f"Using specified entry {actual_entry:.5f} for {signal.order_type.value.upper()} order")
        
        # Validate levels against the actual entry price that will be used
        if signal.direction == Direction.BUY:
            if signal.stop_loss >= actual_entry:
                raise HTTPException(status_code=400, detail=f"Stop loss {signal.stop_loss} must be below entry {actual_entry:.5f} for BUY")
            if signal.take_profit <= actual_entry:
                raise HTTPException(status_code=400, detail=f"Take profit {signal.take_profit} must be above entry {actual_entry:.5f} for BUY")
        else:
            if signal.stop_loss <= actual_entry:
                raise HTTPException(status_code=400, detail=f"Stop loss {signal.stop_loss} must be above entry {actual_entry:.5f} for SELL")
            if signal.take_profit >= actual_entry:
                raise HTTPException(status_code=400, detail=f"Take profit {signal.take_profit} must be below entry {actual_entry:.5f} for SELL")
        
        # Determine comment for order type
        # MT5Service.open_order() checks comment for order type
        order_type_comment = None
        if signal.order_type and signal.order_type != OrderType.MARKET:
            # Convert to format MT5Service expects
            order_type_comment = signal.order_type.value  # e.g., "buy_limit", "sell_limit"
        
        # Calculate dynamic lot size based on risk
        from config.lot_sizing import calculate_lot_from_risk
        
        # Get account equity
        account_info = mt5.account_info()
        equity = float(account_info.equity) if account_info else 10000.0
        
        # Get symbol info for tick value/size
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info:
            tick_value = float(symbol_info.trade_tick_value)
            tick_size = float(symbol_info.trade_tick_size)
            contract_size = float(symbol_info.trade_contract_size)
        else:
            tick_value = 1.0
            tick_size = 0.01
            contract_size = 100000
        
        calculated_lot = calculate_lot_from_risk(
            symbol=symbol,
            entry=actual_entry,
            stop_loss=signal.stop_loss,
            equity=equity,
            risk_pct=None,  # Use symbol default
            tick_value=tick_value,
            tick_size=tick_size,
            contract_size=contract_size
        )
        
        stop_distance = abs(signal.stop_loss - actual_entry)
        logger.info(f"   Dynamic lot sizing: {calculated_lot} lots (stop distance: {stop_distance:.5f}, equity: ${equity:.2f})")
        
        # Execute the trade
        result = mt5_service.open_order(
            symbol=symbol,
            side=signal.direction.value,
            entry=actual_entry,  # Use actual_entry (current price for market, specified for limit)
            sl=signal.stop_loss,
            tp=signal.take_profit,
            lot=calculated_lot,  # Dynamic lot size based on risk
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
            
            # Auto-register to DTMS (one-liner wrapper)
            if ticket:
                try:
                    from dtms_integration import auto_register_dtms
                    result_copy = dict(result)
                    result_copy['symbol'] = symbol
                    result_copy['direction'] = signal.direction.value
                    auto_register_dtms(ticket, result_copy)
                except Exception:
                    pass  # Silent failure - DTMS registration shouldn't break trade execution
            
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
                        "lot": calculated_lot,
                        "ticket": ticket,
                        "position": details.get("position"),
                        "balance": bal,
                        "equity": eq,
                        "notes": f"API Trade ({order_type_str}): {signal.reasoning or 'External API'}"[:200]
                    })
                except Exception as e:
                    logger.warning(f"Failed to write to journal: {e}")
            
            # Auto-enable intelligent exits (if enabled in config and not a pending order)
            try:
                from config import settings as cfg_settings
                from infra.intelligent_exit_manager import create_exit_manager
                
                if cfg_settings.INTELLIGENT_EXITS_AUTO_ENABLE and order_type_str == "MARKET":
                    # Only auto-enable for market orders, not pending orders
                    # Provide indicator_bridge as advanced_provider so gates refresh live
                    exit_manager = create_exit_manager(
                        mt5_service,
                        advanced_provider=indicator_bridge,
                    )
                    
                    exit_manager.add_rule(
                        ticket=ticket,
                        symbol=symbol,
                        entry_price=signal.entry_price,
                        direction=signal.direction.value,
                        initial_sl=signal.stop_loss,
                        initial_tp=signal.take_profit,
                        breakeven_profit_pct=cfg_settings.INTELLIGENT_EXITS_BREAKEVEN_PCT,
                        partial_profit_pct=cfg_settings.INTELLIGENT_EXITS_PARTIAL_PCT,
                        partial_close_pct=cfg_settings.INTELLIGENT_EXITS_PARTIAL_CLOSE_PCT,
                        vix_threshold=cfg_settings.INTELLIGENT_EXITS_VIX_THRESHOLD,
                        use_hybrid_stops=cfg_settings.INTELLIGENT_EXITS_USE_HYBRID_STOPS,
                        trailing_enabled=cfg_settings.INTELLIGENT_EXITS_TRAILING_ENABLED
                    )
                    
                    logger.info(f"✅ Auto-enabled intelligent exits for ticket {ticket}")
            except Exception as e:
                logger.warning(f"Failed to auto-enable intelligent exits for ticket {ticket}: {e}")
            
            resp_model = ExecutionResponse(
                ok=True,
                order_id=ticket,
                deal_id=details.get("deal"),
                retcode=details.get("retcode", 10009),
                comment=f"{order_type_str} {signal.direction.upper()} {symbol} executed successfully",
            )
            # Cache idempotent response (success)
            await _set_idempotent_response(idempotency_key, resp_model.dict())
            return resp_model
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

@app.post("/mt5/modify_position", dependencies=[Depends(verify_api_key)])
async def modify_position(request: Request):
    """Modify an existing position's stop loss and/or take profit"""
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        body = await request.json()
        ticket = body.get("ticket")
        symbol = body.get("symbol", "").upper()
        new_sl = body.get("stop_loss")
        new_tp = body.get("take_profit")
        
        if not ticket:
            raise HTTPException(status_code=400, detail="ticket is required")
        
        # Normalize symbol
        if symbol and not symbol.endswith('c'):
            symbol = symbol + 'c'
        
        # Handle string "None" or empty strings (convert to actual None)
        if new_sl in ["None", "", "null"]:
            new_sl = None
        elif new_sl is not None:
            new_sl = float(new_sl)
        
        if new_tp in ["None", "", "null"]:
            new_tp = None
        elif new_tp is not None:
            new_tp = float(new_tp)
        
        logger.info(f"Modifying position {ticket}: SL={new_sl}, TP={new_tp}")
        
        # Validate that at least one modification is requested
        if new_sl is None and new_tp is None:
            raise HTTPException(status_code=400, detail="Must specify at least one of: stop_loss or take_profit")
        
        # Connect to MT5
        mt5_service.connect()
        
        # Get the position
        import MetaTrader5 as mt5
        positions = mt5.positions_get(ticket=ticket)
        
        if not positions or len(positions) == 0:
            raise HTTPException(status_code=404, detail=f"Position {ticket} not found")
        
        position = positions[0]
        
        # Use current values if not specified
        final_sl = new_sl if new_sl is not None else position.sl
        final_tp = new_tp if new_tp is not None else position.tp
        
        logger.info(f"   Current: SL={position.sl}, TP={position.tp}")
        logger.info(f"   New:     SL={final_sl}, TP={final_tp}")
        
        # Prepare modification request
        request_data = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": position.symbol,
            "sl": final_sl,
            "tp": final_tp,
        }
        
        # Send modification request
        result = mt5.order_send(request_data)
        
        if result is None:
            raise HTTPException(status_code=500, detail="MT5 order_send returned None")
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"✅ Position {ticket} modified successfully")
            
            # Log modification to database
            try:
                from infra.journal_repo import JournalRepo
                journal_repo = JournalRepo()
                
                journal_repo.add_event(
                    event="sl_tp_modified",
                    ticket=ticket,
                    symbol=position.symbol,
                    price=position.price_current,
                    sl=final_sl,
                    tp=final_tp,
                    reason="API modification via Custom GPT",
                    extra={
                        "old_sl": position.sl,
                        "new_sl": final_sl,
                        "old_tp": position.tp,
                        "new_tp": final_tp,
                        "source": "main_api",
                        "modification_type": "manual"
                    }
                )
                logger.info(f"📊 Modification logged to database")
            except Exception as e:
                logger.error(f"Failed to log modification to database: {e}")
            
            return {
                "ok": True,
                "message": "Position modified successfully",
                "ticket": ticket,
                "old_sl": position.sl,
                "old_tp": position.tp,
                "new_sl": final_sl,
                "new_tp": final_tp
            }
        else:
            error_msg = f"Failed to modify position: {result.comment} (RetCode: {result.retcode})"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        
    except HTTPException:
        raise
    except Exception as e:
        error_details = {
            "error": str(e),
            "error_type": type(e).__name__,
            "ticket": ticket if 'ticket' in locals() else None
        }
        logger.error(f"Position modification error: {error_details}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Position modification failed: {str(e)}")


@app.post("/mt5/enable_intelligent_exits", dependencies=[Depends(verify_api_key)])
async def enable_intelligent_exits(
    ticket: int,
    symbol: str,
    entry_price: float,
    direction: str,
    initial_sl: float,
    initial_tp: float,
    breakeven_profit_pct: float = 30.0,
    partial_profit_pct: float = 60.0,
    partial_close_pct: float = 50.0,
    vix_threshold: float = 18.0,
    vix_multiplier: float = 1.5,
    use_hybrid_stops: bool = True,
    trailing_enabled: bool = True
) -> Dict[str, Any]:
    """
    Enable intelligent exit management for a position.
    Automatically moves SL to breakeven, takes partial profits, and adjusts for VIX.
    """
    try:
        from infra.intelligent_exit_manager import create_exit_manager
        
        exit_manager = create_exit_manager(mt5_service)
        
        rule = exit_manager.add_rule(
            ticket=ticket,
            symbol=symbol,
            entry_price=entry_price,
            direction=direction,
            initial_sl=initial_sl,
            initial_tp=initial_tp,
            breakeven_profit_pct=breakeven_profit_pct,
            partial_profit_pct=partial_profit_pct,
            partial_close_pct=partial_close_pct,
            vix_threshold=vix_threshold,
            vix_multiplier=vix_multiplier,
            use_hybrid_stops=use_hybrid_stops,
            trailing_enabled=trailing_enabled
        )
        
        logger.info(f"Intelligent exits enabled for ticket {ticket} ({symbol})")
        
        return {
            "ok": True,
            "message": "Intelligent exit management enabled",
            "ticket": ticket,
            "symbol": symbol,
            "rules": {
                "breakeven_profit_pct": f"{breakeven_profit_pct}% of potential profit",
                "partial_profit_pct": f"{partial_profit_pct}% of potential profit (auto-skipped if volume < 0.02 lots)",
                "partial_close_pct": f"{partial_close_pct}%",
                "vix_threshold": vix_threshold,
                "vix_multiplier": vix_multiplier,
                "use_hybrid_stops": use_hybrid_stops,
                "stop_method": "Hybrid ATR+VIX" if use_hybrid_stops else "VIX-only (legacy)"
            }
        }
        
    except Exception as e:
        logger.error(f"Error enabling intelligent exits: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/mt5/disable_intelligent_exits/{ticket}", dependencies=[Depends(verify_api_key)])
async def disable_intelligent_exits(ticket: int) -> Dict[str, Any]:
    """Disable intelligent exit management for a position"""
    try:
        from infra.intelligent_exit_manager import create_exit_manager
        
        exit_manager = create_exit_manager(mt5_service)
        success = exit_manager.remove_rule(ticket)
        
        if success:
            logger.info(f"Intelligent exits disabled for ticket {ticket}")
            return {
                "ok": True,
                "message": f"Intelligent exit management disabled for ticket {ticket}"
            }
        else:
            raise HTTPException(status_code=404, detail=f"No exit rule found for ticket {ticket}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling intelligent exits: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mt5/intelligent_exits/status")
async def get_intelligent_exits_status() -> Dict[str, Any]:
    """Get status of all active intelligent exit rules (auto-cleans closed positions)"""
    try:
        from infra.intelligent_exit_manager import create_exit_manager
        import MetaTrader5 as mt5
        
        exit_manager = create_exit_manager(mt5_service)
        
        # CRITICAL: Clean up rules for closed positions before returning status
        # This prevents showing stale rules for positions that no longer exist
        all_rules = exit_manager.get_all_rules()
        if all_rules:
            # Get current open positions
            positions = mt5.positions_get()
            open_tickets = {p.ticket for p in positions} if positions else set()
            
            # Remove rules for closed positions
            closed_count = 0
            for rule in list(all_rules):
                if rule.ticket not in open_tickets:
                    logger.info(f"🧹 Cleaning up stale rule for closed position: ticket {rule.ticket} ({rule.symbol})")
                    exit_manager.remove_rule(rule.ticket)
                    closed_count += 1
            
            if closed_count > 0:
                logger.info(f"✅ Removed {closed_count} stale rule(s) for closed positions")
        
        # Get fresh list of rules (after cleanup)
        rules = exit_manager.get_all_rules()
        
        active_rules = []
        for rule in rules:
            active_rules.append({
                "ticket": rule.ticket,
                "symbol": rule.symbol,
                "direction": rule.direction,
                "entry_price": rule.entry_price,
                "breakeven_triggered": rule.breakeven_triggered,
                "partial_triggered": rule.partial_triggered,
                "vix_adjustment_active": rule.vix_adjustment_active,
                "actions_taken": rule.actions_taken,
                "created_at": rule.created_at,
                "last_check": rule.last_check,
                # V8-adjusted percentages
                "breakeven_pct": rule.breakeven_profit_pct,
                "partial_pct": rule.partial_profit_pct,
                "partial_close_pct": rule.partial_close_pct
            })
        
        return {
            "ok": True,
            "count": len(active_rules),
            "rules": active_rules
        }
        
    except Exception as e:
        logger.error(f"Error getting intelligent exits status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mt5/intelligent_exits/history/{ticket}")
async def get_intelligent_exits_history(ticket: int) -> Dict[str, Any]:
    """Get historical intelligent exit actions for a specific ticket"""
    try:
        from infra.intelligent_exit_logger import get_exit_logger
        
        exit_logger = get_exit_logger()
        actions = exit_logger.get_actions_for_ticket(ticket)
        
        return {
            "ok": True,
            "ticket": ticket,
            "count": len(actions),
            "actions": actions
        }
        
    except Exception as e:
        logger.error(f"Error getting intelligent exits history for ticket {ticket}: {e}", exc_info=True)
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


@app.get("/mt5/intelligent_exits/statistics")
async def get_intelligent_exits_statistics(
    symbol: Optional[str] = None,
    days: int = 30
) -> Dict[str, Any]:
    """Get statistics on intelligent exit actions"""
    try:
        from infra.intelligent_exit_logger import get_exit_logger
        
        exit_logger = get_exit_logger()
        stats = exit_logger.get_statistics(symbol=symbol, days=days)
        
        return {
            "ok": True,
            **stats
        }
        
    except Exception as e:
        logger.error(f"Error getting intelligent exits statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mt5/modify_order", dependencies=[Depends(verify_api_key)])
async def modify_pending_order(request: Request):
    """Modify an existing pending order's price, SL, and/or TP"""
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        body = await request.json()
        ticket = body.get("ticket")
        new_price = body.get("price")
        new_sl = body.get("stop_loss")
        new_tp = body.get("take_profit")
        
        if not ticket:
            raise HTTPException(status_code=400, detail="ticket is required")
        
        logger.info(f"Modifying pending order {ticket}: Price={new_price}, SL={new_sl}, TP={new_tp}")
        
        # Connect to MT5
        mt5_service.connect()
        
        # Get the order
        import MetaTrader5 as mt5
        orders = mt5.orders_get(ticket=ticket)
        
        if not orders or len(orders) == 0:
            raise HTTPException(status_code=404, detail=f"Pending order {ticket} not found")
        
        order = orders[0]
        
        # Prepare modification request
        request_data = {
            "action": mt5.TRADE_ACTION_MODIFY,
            "order": ticket,
            "symbol": order.symbol,
            "type": order.type,
            "volume": order.volume_current,
            "price": new_price if new_price is not None else order.price_open,
            "sl": new_sl if new_sl is not None else order.sl,
            "tp": new_tp if new_tp is not None else order.tp,
        }
        
        # Send modification request
        result = mt5.order_send(request_data)
        
        if result is None:
            raise HTTPException(status_code=500, detail="MT5 order_send returned None")
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Pending order {ticket} modified successfully")
            return {
                "ok": True,
                "message": "Pending order modified successfully",
                "ticket": ticket,
                "new_price": new_price,
                "new_sl": new_sl,
                "new_tp": new_tp
            }
        else:
            error_msg = f"Failed to modify order: {result.comment} (RetCode: {result.retcode})"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        
    except HTTPException:
        raise
    except Exception as e:
        error_details = {
            "error": str(e),
            "error_type": type(e).__name__,
            "ticket": ticket if 'ticket' in locals() else None
        }
        logger.error(f"Order modification error: {error_details}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Order modification failed: {str(e)}")

@app.post("/mt5/execute_bracket", dependencies=[Depends(verify_api_key)])
async def execute_bracket_trade(
    symbol: str,
    buy_entry: float,
    buy_sl: float,
    buy_tp: float,
    sell_entry: float,
    sell_sl: float,
    sell_tp: float,
    reasoning: str = "Bracket trade via API",
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> Dict[str, Any]:
    """
    Execute a bracket trade (OCO pair) with automatic cancellation.
    Places two pending orders: one BUY_LIMIT and one SELL_LIMIT.
    When one fills, the other is automatically cancelled.
    """
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        # Idempotency: return cached response if this key was seen recently
        cached = await _get_idempotent_response(idempotency_key)
        if cached is not None:
            return cached
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
        
        # Get current price to determine order type
        import MetaTrader5 as mt5
        symbol_info = mt5.symbol_info_tick(symbol_norm)
        if not symbol_info:
            raise HTTPException(status_code=400, detail=f"Could not get current price for {symbol_norm}")
        
        current_price = (symbol_info.ask + symbol_info.bid) / 2
        
        # Determine BUY order type
        # BUY_LIMIT: buy when price comes down (entry < current)
        # BUY_STOP: buy when price goes up (entry > current)
        buy_order_type = "buy_limit" if buy_entry < current_price else "buy_stop"
        
        # Determine SELL order type
        # SELL_LIMIT: sell when price goes up (entry > current)
        # SELL_STOP: sell when price comes down (entry < current)
        sell_order_type = "sell_limit" if sell_entry > current_price else "sell_stop"
        
        logger.info(f"Current price: {current_price:.2f} | BUY: {buy_order_type} @ {buy_entry} | SELL: {sell_order_type} @ {sell_entry}")
        
        # Execute BUY order
        buy_result = mt5_service.open_order(
            symbol=symbol_norm,
            side="buy",
            entry=buy_entry,
            sl=buy_sl,
            tp=buy_tp,
            lot=0.01,
            risk_pct=None,
            comment=buy_order_type  # Auto-detect limit vs stop
        )
        
        if not buy_result.get("ok"):
            error_msg = buy_result.get('message', 'Unknown error')
            error_details = buy_result.get('details', {})
            logger.error(f"BUY order failed: {error_msg} | Details: {error_details}")
            raise HTTPException(status_code=400, detail=f"BUY order failed: {error_msg}")
        
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
            comment=sell_order_type  # Auto-detect limit vs stop
        )
        
        if not sell_result.get("ok"):
            error_msg = sell_result.get('message', 'Unknown error')
            error_details = sell_result.get('details', {})
            logger.error(f"SELL order failed: {error_msg} | Details: {error_details}")
            # Cancel BUY order if SELL fails
            try:
                logger.info(f"Cancelling BUY order {buy_ticket} due to SELL order failure")
                oco_tracker.cancel_order(mt5_service, buy_ticket, symbol_norm)
            except Exception as e:
                logger.error(f"Failed to cancel BUY order: {e}")
            raise HTTPException(status_code=400, detail=f"SELL order failed: {error_msg}")
        
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
        
        resp_obj = {
            "ok": True,
            "oco_group_id": oco_group_id,
            "buy_order": {
                "ticket": buy_ticket,
                "entry": buy_entry,
                "sl": buy_sl,
                "tp": buy_tp,
            },
            "sell_order": {
                "ticket": sell_ticket,
                "entry": sell_entry,
                "sl": sell_sl,
                "tp": sell_tp,
            },
            "message": f"Bracket trade created with OCO monitoring",
        }
        await _set_idempotent_response(idempotency_key, resp_obj)
        return resp_obj
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bracket trade error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mt5/link_oco", dependencies=[Depends(verify_api_key)])
async def link_orders_as_oco(
    symbol: str,
    ticket_a: int,
    ticket_b: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> Dict[str, Any]:
    """
    Link two existing MT5 orders as an OCO pair.
    When one fills, the other will be automatically cancelled.
    """
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        # Idempotency: return cached response if this key was seen recently
        cached = await _get_idempotent_response(idempotency_key)
        if cached is not None:
            return cached
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
        
        resp_obj = {
            "ok": True,
            "oco_group_id": oco_group_id,
            "message": f"Orders {ticket_a} and {ticket_b} linked as OCO pair",
            "symbol": symbol_norm,
        }
        await _set_idempotent_response(idempotency_key, resp_obj)
        return resp_obj
        
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
        
        mt5_service.connect()
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
        mt5_service.connect()
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
        mt5_service.connect()
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
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        import MetaTrader5 as mt5
        from datetime import datetime, timedelta, timezone
        
        mt5_service.connect()
        
        # Get closed deals from history (last 30 days)
        now = datetime.now()
        from_date = now - timedelta(days=30)
        
        deals = mt5.history_deals_get(from_date, now)
        
        if not deals or len(deals) == 0:
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
                "equity_curve": [],
                "note": "No closed trades in last 30 days"
            }
        
        # Filter out entry deals (we only want exit deals for P&L)
        exit_deals = [d for d in deals if d.entry == 1]  # entry=1 means OUT
        
        if len(exit_deals) == 0:
            # Get open positions for current P&L
            positions = mt5_service.list_positions()
            open_count = len(positions) if positions else 0
            current_pnl = sum(p.get("profit", 0) for p in (positions or []))
            
            return {
                "total_trades": open_count,
                "winning_trades": sum(1 for p in (positions or []) if p.get("profit", 0) > 0),
                "losing_trades": sum(1 for p in (positions or []) if p.get("profit", 0) < 0),
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "average_win": 0.0,
                "average_loss": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "calmar_ratio": 0.0,
                "equity_curve": [],
                "current_open_trades": open_count,
                "current_unrealized_pnl": round(current_pnl, 2),
                "note": "No closed trades yet - showing open positions only"
            }
        
        # Calculate performance metrics from closed deals
        profits = [d.profit for d in exit_deals if d.profit > 0]
        losses = [d.profit for d in exit_deals if d.profit < 0]
        
        total_trades = len(exit_deals)
        winning_trades = len(profits)
        losing_trades = len(losses)
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        total_profit = sum(profits) if profits else 0
        total_loss = abs(sum(losses)) if losses else 0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else (total_profit if total_profit > 0 else 0)
        
        average_win = (sum(profits) / len(profits)) if profits else 0.0
        average_loss = (sum(losses) / len(losses)) if losses else 0.0
        
        # Calculate equity curve
        equity_curve = []
        cumulative_pnl = 0
        for deal in sorted(exit_deals, key=lambda x: x.time):
            cumulative_pnl += deal.profit
            equity_curve.append({
                "time": datetime.fromtimestamp(deal.time).isoformat(),
                "equity": round(cumulative_pnl, 2),
                "profit": round(deal.profit, 2)
            })
        
        # Calculate max drawdown
        peak = 0
        max_dd = 0
        for point in equity_curve:
            equity = point["equity"]
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_dd:
                max_dd = drawdown
        
        max_drawdown_pct = (max_dd / peak * 100) if peak > 0 else 0
        
        # Simple Sharpe ratio approximation (returns / std dev)
        returns = [d.profit for d in exit_deals]
        if len(returns) > 1:
            import statistics
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns)
            sharpe_ratio = (avg_return / std_return) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Calmar ratio (return / max drawdown)
        total_return = sum(returns)
        calmar_ratio = (total_return / max_dd) if max_dd > 0 else 0
        
        # Get current open positions
        positions = mt5_service.list_positions()
        open_count = len(positions) if positions else 0
        current_pnl = sum(p.get("profit", 0) for p in (positions or []))
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "average_win": round(average_win, 2),
            "average_loss": round(average_loss, 2),
            "max_drawdown": round(max_drawdown_pct, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "calmar_ratio": round(calmar_ratio, 2),
            "equity_curve": equity_curve[-20:],  # Last 20 trades
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "net_profit": round(total_profit + sum(losses), 2),
            "current_open_trades": open_count,
            "current_unrealized_pnl": round(current_pnl, 2),
            "period": "Last 30 days",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Performance report error: {e}", exc_info=True)
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
        mt5_service.connect()
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
    
    # Special handling for DXY (not available in MT5 - fetch from Yahoo Finance)
    if symbol.upper() in ['DXY', 'DXYC', 'DX-Y.NYB']:
        logger.info(f"Routing {symbol} to Yahoo Finance (DXY)")
        try:
            from infra.market_indices_service import create_market_indices_service
            indices = create_market_indices_service()
            dxy_data = indices.get_dxy()
            
            if dxy_data['price'] is None:
                raise HTTPException(status_code=503, detail="DXY data temporarily unavailable from Yahoo Finance")
            
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
        logger.info(f"Routing {symbol} to Yahoo Finance (VIX)")
        try:
            from infra.market_indices_service import create_market_indices_service
            indices = create_market_indices_service()
            vix_data = indices.get_vix()
            
            if vix_data['price'] is None:
                raise HTTPException(status_code=503, detail="VIX data temporarily unavailable from Yahoo Finance")
            
            price = vix_data['price']
            logger.info(f"VIX price fetched successfully: {price}")
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
            logger.error(f"Error fetching VIX from Yahoo Finance: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"VIX fetch error: {str(e)}")
    
    # Special handling for US10Y (not available in MT5 - fetch from Yahoo Finance)
    if symbol.upper() in ['US10Y', 'US10YC', 'TNX', '^TNX']:
        logger.info(f"Routing {symbol} to Yahoo Finance (US10Y)")
        try:
            from infra.market_indices_service import create_market_indices_service
            indices = create_market_indices_service()
            us10y_data = indices.get_us10y()
            
            if us10y_data['price'] is None:
                raise HTTPException(status_code=503, detail="US10Y data temporarily unavailable from Yahoo Finance")
            
            price = us10y_data['price']
            logger.info(f"US10Y price fetched successfully: {price}")
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
            logger.error(f"Error fetching US10Y from Yahoo Finance: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"US10Y fetch error: {str(e)}")
    
    # Normal MT5 symbols
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        # Normalize symbol (avoid double 'c' suffix)
        symbol_upper = symbol.upper()
        if not symbol_upper.endswith('C'):
            symbol = symbol_upper + 'c'
        else:
            # Already has 'c' or 'C' suffix, keep it lowercase
            symbol = symbol_upper[:-1] + 'c'
        
        mt5_service.connect()
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
# NEWS ENDPOINTS
# ============================================================================

@app.get("/news/status")
async def get_news_status(
    category: str = "both",
    hours_ahead: int = 12
):
    """Get news blackout status and upcoming events"""
    try:
        from infra.news_service import NewsService
        from datetime import timedelta
        
        ns = NewsService()
        now = datetime.utcnow()
        
        # Validate parameters
        if category not in ["macro", "crypto", "both"]:
            raise HTTPException(status_code=400, detail="category must be 'macro', 'crypto', or 'both'")
        if hours_ahead < 1 or hours_ahead > 168:
            raise HTTPException(status_code=400, detail="hours_ahead must be between 1 and 168")
        
        # Check macro
        macro_blackout = False
        macro_summary = ""
        next_macro = None
        if category in ["macro", "both"]:
            macro_blackout = ns.is_blackout(category="macro", now=now)
            macro_summary = ns.summary_for_prompt(category="macro", now=now, hours_ahead=hours_ahead)
            next_macro = ns.next_event_time(category="macro", now=now)
        
        # Check crypto
        crypto_blackout = False
        crypto_summary = ""
        next_crypto = None
        if category in ["crypto", "both"]:
            crypto_blackout = ns.is_blackout(category="crypto", now=now)
            crypto_summary = ns.summary_for_prompt(category="crypto", now=now, hours_ahead=hours_ahead)
            next_crypto = ns.next_event_time(category="crypto", now=now)
        
        # Determine risk level and recommendation
        if macro_blackout or crypto_blackout:
            risk_level = "CRITICAL"
            event_type = "macro" if macro_blackout else "crypto"
            recommendation = f"WAIT - High-impact {event_type} event nearby. Avoid trading until blackout clears."
        elif macro_summary or crypto_summary:
            risk_level = "MEDIUM"
            upcoming = macro_summary or crypto_summary
            recommendation = f"CAUTION - Upcoming events: {upcoming}. Consider tighter stops or smaller positions."
        else:
            risk_level = "LOW"
            recommendation = f"CLEAR - No major news events in next {hours_ahead} hours."
        
        return {
            "macro_blackout": macro_blackout,
            "crypto_blackout": crypto_blackout,
            "upcoming_macro_events": macro_summary,
            "upcoming_crypto_events": crypto_summary,
            "next_macro_event": next_macro.isoformat() + "Z" if next_macro else None,
            "next_crypto_event": next_crypto.isoformat() + "Z" if next_crypto else None,
            "recommendation": recommendation,
            "risk_level": risk_level,
            "timestamp": now.isoformat() + "Z"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting news status: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading news data: {str(e)}")


@app.get("/news/events")
async def get_news_events(
    category: Optional[str] = None,
    impact: Optional[str] = None,
    hours_ahead: int = 24,
    hours_behind: int = 0
):
    """Get list of upcoming news events"""
    try:
        from infra.news_service import NewsService
        from datetime import timedelta
        
        ns = NewsService()
        now = datetime.utcnow()
        
        # Validate parameters
        if category and category not in ["macro", "crypto"]:
            raise HTTPException(status_code=400, detail="category must be 'macro' or 'crypto'")
        if impact and impact not in ["low", "medium", "high", "ultra", "crypto"]:
            raise HTTPException(status_code=400, detail="impact must be 'low', 'medium', 'high', 'ultra', or 'crypto'")
        if hours_ahead < 1 or hours_ahead > 168:
            raise HTTPException(status_code=400, detail="hours_ahead must be between 1 and 168")
        if hours_behind < 0 or hours_behind > 24:
            raise HTTPException(status_code=400, detail="hours_behind must be between 0 and 24")
        
        # Get time window
        start_time = now - timedelta(hours=hours_behind)
        end_time = now + timedelta(hours=hours_ahead)
        
        # Get events using summarise_events
        window_min = int((end_time - start_time).total_seconds() / 60)
        
        events_list = []
        high_impact_count = 0
        blackout_active = False
        
        # Get events for requested category
        categories = [category] if category else ["macro", "crypto"]
        
        for cat in categories:
            # Check if in blackout for this category
            if ns.is_blackout(category=cat, now=now):
                blackout_active = True
            
            # Get all events (we'll filter by impact later)
            summary = ns.summarise_events(category=cat, now=start_time, window_min=window_min)
            
            # Parse events from summary (this is a simplified version)
            # In a real implementation, you'd want NewsService to return structured data
            # For now, we'll load events directly from the service
            ns._load_events_if_needed()
            
            for event in ns._events:
                if event.category != cat:
                    continue
                if event.time < start_time or event.time > end_time:
                    continue
                if impact and event.impact != impact:
                    # Filter by minimum impact level
                    impact_order = ["low", "medium", "high", "ultra", "crypto"]
                    if impact in impact_order and event.impact in impact_order:
                        if impact_order.index(event.impact) < impact_order.index(impact):
                            continue
                
                # Calculate time until event
                time_delta = event.time - now
                if time_delta.total_seconds() < 0:
                    time_until = f"{abs(int(time_delta.total_seconds() / 60))} minutes ago"
                else:
                    hours = int(time_delta.total_seconds() / 3600)
                    minutes = int((time_delta.total_seconds() % 3600) / 60)
                    if hours > 0:
                        time_until = f"{hours} hours {minutes} minutes"
                    else:
                        time_until = f"{minutes} minutes"
                
                # Check if in blackout for this specific event
                in_blackout = False
                if event.impact in ["high", "ultra", "crypto"]:
                    # Simple check: if event is within next hour, consider it in blackout
                    if 0 <= time_delta.total_seconds() <= 3600:
                        in_blackout = True
                
                events_list.append({
                    "time": event.time.isoformat() + "Z",
                    "description": event.description,
                    "impact": event.impact,
                    "category": event.category,
                    "symbols": event.symbols,
                    "time_until": time_until,
                    "in_blackout": in_blackout
                })
                
                if event.impact in ["high", "ultra", "crypto"]:
                    high_impact_count += 1
        
        # Sort by time
        events_list.sort(key=lambda x: x["time"])
        
        return {
            "events": events_list,
            "total_events": len(events_list),
            "high_impact_count": high_impact_count,
            "blackout_active": blackout_active,
            "timestamp": now.isoformat() + "Z"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting news events: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading news events: {str(e)}")

# ============================================================================
# MONITORING ENDPOINTS
# ============================================================================

@app.get("/api/v1/positions")
async def get_positions():
    """Get all open positions from MT5"""
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        mt5_service.connect()
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

@app.get("/api/v1/orders")
async def get_pending_orders():
    """Get all pending orders from MT5"""
    if not mt5_service:
        raise HTTPException(status_code=500, detail="MT5 service not initialized")
    
    try:
        import MetaTrader5 as mt5
        mt5_service.connect()
        
        # Get all pending orders
        orders = mt5.orders_get()
        
        if not orders or len(orders) == 0:
            return {"orders": [], "count": 0}
        
        # Format orders with additional info
        formatted_orders = []
        for order in orders:
            # Determine order type string
            order_type_map = {
                mt5.ORDER_TYPE_BUY_LIMIT: "buy_limit",
                mt5.ORDER_TYPE_SELL_LIMIT: "sell_limit",
                mt5.ORDER_TYPE_BUY_STOP: "buy_stop",
                mt5.ORDER_TYPE_SELL_STOP: "sell_stop",
                mt5.ORDER_TYPE_BUY_STOP_LIMIT: "buy_stop_limit",
                mt5.ORDER_TYPE_SELL_STOP_LIMIT: "sell_stop_limit"
            }
            
            order_type_str = order_type_map.get(order.type, "unknown")
            
            formatted_orders.append({
                "ticket": order.ticket,
                "symbol": order.symbol,
                "type": order_type_str,
                "volume": order.volume_current,
                "price_open": order.price_open,
                "sl": order.sl,
                "tp": order.tp,
                "price_current": order.price_current,
                "comment": order.comment,
                "time_setup": order.time_setup,
                "time_expiration": order.time_expiration if hasattr(order, 'time_expiration') else 0
            })
        
        return {
            "orders": formatted_orders,
            "count": len(formatted_orders)
        }
        
    except Exception as e:
        logger.error(f"Error getting pending orders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/positions/history")
async def get_positions_history(limit: int = 20) -> Dict[str, Any]:
    """Get trade history from journal"""
    if not journal_repo:
        return {"error": "Journal not available", "trades": []}

    try:
        # Get recent trades from journal
        trades = journal_repo.recent(limit)

        # Convert to format expected by frontend
        formatted_trades = []
        for trade in trades:
            formatted_trades.append({
                "ticket": trade.get("ticket"),
                "symbol": trade.get("symbol"),
                "profit": 0,  # These are open trades, no profit yet
                "side": trade.get("side", "unknown"),
                "entry_price": trade.get("entry"),
                "exit_price": None,  # These are open trades
                "r_multiple": None,  # Will be calculated when closed
                "duration_sec": None,  # Will be calculated when closed
                "timestamp": trade.get("ts"),
                "sl": trade.get("sl"),
                "tp": trade.get("tp"),
                "lot": trade.get("lot")
            })

        return {"trades": formatted_trades}
    except Exception as e:
        logger.error(f"Error getting positions history: {e}", exc_info=True)
        return {"error": str(e), "trades": []}


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
        logger.info("Manual monitoring cycle triggered")
        
        if not mt5_service:
            raise HTTPException(status_code=500, detail="MT5 service not initialized")
        
        # Connect to MT5
        mt5_service.connect()
        
        # Get all open positions
        positions = mt5_service.list_positions()
        positions_count = len(positions) if positions else 0
        
        # Get all pending orders (for bracket trades)
        import MetaTrader5 as mt5
        pending_orders = mt5.orders_get()
        pending_count = len(pending_orders) if pending_orders else 0
        
        # Get OCO pairs
        oco_pairs = oco_tracker.get_active_oco_pairs()
        bracket_count = len(oco_pairs)
        
        actions_taken = 0
        
        # Log monitoring results
        logger.info(f"Monitor cycle: {positions_count} positions, {pending_count} pending orders, {bracket_count} OCO pairs")
        
        # Build detailed response
        position_details = []
        if positions:
            for pos in positions:
                position_details.append({
                    "ticket": pos.get("ticket"),
                    "symbol": pos.get("symbol"),
                    "type": pos.get("type"),
                    "volume": pos.get("volume"),
                    "profit": pos.get("profit", 0),
                    "sl": pos.get("sl"),
                    "tp": pos.get("tp")
                })
        
        bracket_details = []
        if oco_pairs:
            for pair in oco_pairs:
                bracket_details.append({
                    "symbol": pair.symbol,
                    "order_a_ticket": pair.order_a_ticket,
                    "order_a_side": pair.order_a_side,
                    "order_b_ticket": pair.order_b_ticket,
                    "order_b_side": pair.order_b_side,
                    "status": pair.status,
                    "oco_group_id": pair.oco_group_id
                })
        
        return {
            "ok": True,
            "positions_analyzed": positions_count,
            "actions_taken": actions_taken,
            "bracket_trades_monitored": bracket_count,
            "pending_orders": pending_count,
            "timestamp": datetime.now().isoformat(),
            "details": {
                "positions": position_details,
                "bracket_trades": bracket_details
            }
        }
        
    except Exception as e:
        logger.error(f"Monitor run error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# UNIFIED TICK PIPELINE ENDPOINTS
# ============================================================================

@app.get("/pipeline/status")
async def get_unified_pipeline_status():
    """Get Unified Tick Pipeline status"""
    try:
        status = await get_pipeline_status()
        return status
    except Exception as e:
        logger.error(f"Pipeline status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pipeline/health")
async def get_unified_pipeline_health():
    """Get Unified Tick Pipeline system health"""
    try:
        health = await get_system_health()
        return health
    except Exception as e:
        logger.error(f"Pipeline health error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pipeline/integration/status")
async def get_pipeline_integration_status():
    """Get Unified Tick Pipeline integration status"""
    try:
        status = get_integration_status()
        return status
    except Exception as e:
        logger.error(f"Pipeline integration status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pipeline/market/{symbol}")
async def get_enhanced_market_data_endpoint(
    symbol: str,
    timeframe: str = "M1",
    limit: int = 100
):
    """Get enhanced market data from Unified Tick Pipeline"""
    try:
        data = await get_enhanced_market_data(symbol, timeframe, limit)
        return data
    except Exception as e:
        logger.error(f"Enhanced market data error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pipeline/volatility/{symbol}")
async def get_volatility_analysis_endpoint(symbol: str):
    """Get volatility analysis from Unified Tick Pipeline"""
    try:
        analysis = await get_volatility_analysis(symbol)
        return analysis
    except Exception as e:
        logger.error(f"Volatility analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pipeline/offset/{symbol}")
async def get_offset_calibration_endpoint(symbol: str):
    """Get offset calibration data from Unified Tick Pipeline"""
    try:
        calibration = await get_offset_calibration(symbol)
        return calibration
    except Exception as e:
        logger.error(f"Offset calibration error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pipeline/analysis/{symbol}")
async def get_enhanced_symbol_analysis_endpoint(symbol: str):
    """Get enhanced symbol analysis from Unified Tick Pipeline"""
    try:
        analysis = await get_enhanced_symbol_analysis(symbol)
        return analysis
    except Exception as e:
        logger.error(f"Enhanced symbol analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pipeline/ticks/{symbol}")
async def get_real_time_ticks_endpoint(
    symbol: str,
    limit: int = 50
):
    """Get real-time tick data from Unified Tick Pipeline"""
    try:
        ticks = await get_real_time_ticks(symbol, limit)
        return ticks
    except Exception as e:
        logger.error(f"Real-time ticks error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pipeline/multi-timeframe/{symbol}")
async def get_multi_timeframe_analysis_endpoint(
    symbol: str,
    timeframes: Optional[List[str]] = None
):
    """Get multi-timeframe analysis from Unified Tick Pipeline"""
    try:
        analysis = await get_multi_timeframe_analysis(symbol, timeframes)
        return analysis
    except Exception as e:
        logger.error(f"Multi-timeframe analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# STUB ENDPOINTS (To be implemented)
# ============================================================================

@app.post("/discord/webhook")
async def discord_webhook(request: Request):
    """Discord webhook endpoint (placeholder)"""
    return {"ok": True}

@app.get("/api/v1/analyse/{symbol}/full")
async def get_full_unified_analysis(symbol: str):
    """
    Get full unified analysis with all new features:
    - Stop cluster detection
    - Fed expectations tracking
    - Volatility forecasting
    - Order flow signals
    - Enhanced macro bias
    
    This endpoint uses the same analysis as Custom GPT (desktop_agent.tool_analyse_symbol_full)
    
    Returns the complete unified analysis with formatted summary for ChatGPT/Telegram
    """
    try:
        # Import desktop_agent to access the tool
        import desktop_agent
        from desktop_agent import registry
        
        # Ensure registry is initialized (tools are registered on module import)
        if not hasattr(desktop_agent, 'registry') or not desktop_agent.registry:
            raise HTTPException(status_code=500, detail="Desktop agent not initialized")
        
        # Ensure tick metrics instance is accessible to desktop_agent
        # (It's set in startup_event, but we always re-set it before calling tool to ensure access)
        from infra.tick_metrics import get_tick_metrics_instance, set_tick_metrics_instance
        if tick_metrics_generator:
            # Always re-set the instance to ensure desktop_agent can access it
            # This ensures the instance is accessible even if desktop_agent was imported before startup
            set_tick_metrics_instance(tick_metrics_generator)
            logger.debug("Ensured tick metrics instance is accessible to desktop_agent")
        
        # Initialize MT5 service if needed
        if not registry.mt5_service:
            from infra.mt5_service import MT5Service
            registry.mt5_service = MT5Service()
            if not registry.mt5_service.connect():
                raise HTTPException(status_code=500, detail="Failed to connect to MT5")
        
        # Get the registered tool function
        tool_func = registry.tools.get("moneybot.analyse_symbol_full")
        if not tool_func:
            raise HTTPException(status_code=500, detail="Analysis tool not registered")
        
        # Call the tool with symbol
        result = await tool_func({"symbol": symbol})
        
        # Convert numpy types to native Python types for JSON serialization
        if result and isinstance(result, dict):
            # Use existing convert_numpy_types function if available
            try:
                result = convert_numpy_types(result)
            except NameError:
                # Fallback: Recursive conversion helper
                def _convert_numpy(val):
                    import numpy as np
                    if isinstance(val, np.integer):
                        return int(val)
                    elif isinstance(val, np.floating):
                        return float(val)
                    elif isinstance(val, np.ndarray):
                        return val.tolist()
                    elif isinstance(val, dict):
                        return {k: _convert_numpy(v) for k, v in val.items()}
                    elif isinstance(val, list):
                        return [_convert_numpy(item) for item in val]
                    else:
                        return val
                
                result = _convert_numpy(result)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Full unified analysis error for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


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
        mt5_service.connect()
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
                # Check if the last element is a datetime string
                last_val = val[-1]
                if isinstance(last_val, str) and ('-' in last_val or ':' in last_val):
                    # Skip datetime strings, return 0.0
                    return 0.0
                try:
                    return float(last_val)
                except (ValueError, TypeError):
                    return 0.0
            elif isinstance(val, pd.Series):
                return float(val.iloc[-1]) if len(val) > 0 else 0.0
            else:
                try:
                    return float(val) if val is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0
        
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
        
        # Populate detection results (Phase 0.2.2: Tech Dict Integration)
        try:
            from infra.tech_dict_enricher import populate_detection_results
            populate_detection_results(tech, symbol, None, None)
        except Exception as e:
            logger.debug(f"Detection results population failed for {symbol}: {e}")
            # Continue without detection results - graceful degradation
        
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
                    "atr14": _to_scalar(m5.get("atr14", 0))
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
            "note": "This endpoint provides fast technical analysis. For full ChatGPT-powered analysis, use the Discord bot's /trade command."
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
        mt5_service.connect()
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
        rsi = float(m5.get("rsi", 50))
        adx = float(m5.get("adx", 20))
        ema20 = float(m5.get("ema20", 0))
        ema50 = float(m5.get("ema50", 0))
        
        # Get close price - handle both scalar and array formats
        close_data = m5.get("close", 0)
        if isinstance(close_data, list):
            close = float(close_data[-1]) if close_data else 0.0
        else:
            close = float(close_data) if close_data else 0.0
        close = float(m5.get("current_close", close))
        
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
        atr = float(m5.get("atr14", 0))
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
        mt5_service.connect()
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
        
        # Get key indicators - ensure all are floats
        rsi = float(m5.get("rsi", 50))
        adx = float(m5.get("adx", 20))
        atr = float(m5.get("atr14", 0))
        
        # Get close price - handle both scalar and array formats
        close_data = m5.get("close", 0)
        if isinstance(close_data, list):
            close = float(close_data[-1]) if close_data else 0.0
        else:
            close = float(close_data) if close_data else 0.0
        
        # Get current_close if available (preferred)
        close = float(m5.get("current_close", close))
        
        ema20 = float(m5.get("ema20", 0))
        ema50 = float(m5.get("ema50", 0))
        
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

@app.get("/sentiment/market")
async def get_market_sentiment():
    """Get market sentiment analysis"""
    try:
        logger.info("Market sentiment requested")
        
        # Calculate sentiment based on multiple factors
        sentiment_score = 50  # Neutral baseline (0-100 scale)
        sentiment_factors = []
        
        # Try to get VIX-like data from market conditions
        try:
            if mt5_service and indicator_bridge:
                mt5_service.connect()
                
                # Check major indices for risk sentiment
                # SPX proxy: check EURUSD volatility and trend
                multi = indicator_bridge.get_multi("EURUSDc")
                m15 = multi.get("M15", {})
                
                rsi = float(m15.get("rsi", 50))
                adx = float(m15.get("adx", 20))
                atr = float(m15.get("atr14", 0))
                
                # High RSI + Strong trend = Risk-on (bullish sentiment)
                if rsi > 55 and adx > 25:
                    sentiment_score += 15
                    sentiment_factors.append("Strong uptrend in major forex pairs (risk-on)")
                elif rsi < 45 and adx > 25:
                    sentiment_score -= 15
                    sentiment_factors.append("Strong downtrend in major forex pairs (risk-off)")
                
                # High volatility = Fear (bearish sentiment)
                close_data = m15.get("close", 0)
                if isinstance(close_data, list):
                    close = float(close_data[-1]) if close_data else 1.0
                else:
                    close = float(close_data) if close_data else 1.0
                close = float(m15.get("current_close", close))
                
                atr_percent = (atr / close * 100) if close > 0 else 0
                if atr_percent > 0.8:
                    sentiment_score -= 10
                    sentiment_factors.append("High volatility detected (increased fear)")
                elif atr_percent < 0.3:
                    sentiment_score += 5
                    sentiment_factors.append("Low volatility (complacency)")
                
        except Exception as e:
            logger.warning(f"Could not calculate market-based sentiment: {e}")
            sentiment_factors.append("Using baseline sentiment (market data unavailable)")
        
        # Check news events for sentiment impact
        try:
            from infra.news_service import NewsService
            ns = NewsService()
            now = datetime.utcnow()
            
            # Check if major news events are upcoming
            macro_blackout = ns.is_blackout(category="macro", now=now)
            crypto_blackout = ns.is_blackout(category="crypto", now=now)
            
            if macro_blackout or crypto_blackout:
                sentiment_score -= 20
                sentiment_factors.append("Major news event nearby (heightened uncertainty)")
        except Exception as e:
            logger.warning(f"Could not check news sentiment: {e}")
        
        # Clamp sentiment score to 0-100
        sentiment_score = max(0, min(100, sentiment_score))
        
        # Determine sentiment label and bias
        if sentiment_score >= 75:
            sentiment_label = "EXTREME GREED"
            bias = "bearish"
            bias_reason = "Extreme greed often precedes corrections"
            position_sizing = 0.5
        elif sentiment_score >= 60:
            sentiment_label = "GREED"
            bias = "neutral_bearish"
            bias_reason = "Elevated greed suggests caution"
            position_sizing = 0.75
        elif sentiment_score >= 45:
            sentiment_label = "NEUTRAL"
            bias = "neutral"
            bias_reason = "Balanced market conditions"
            position_sizing = 1.0
        elif sentiment_score >= 30:
            sentiment_label = "FEAR"
            bias = "neutral_bullish"
            bias_reason = "Fear creates buying opportunities"
            position_sizing = 0.75
        else:
            sentiment_label = "EXTREME FEAR"
            bias = "bullish"
            bias_reason = "Extreme fear often marks bottoms"
            position_sizing = 0.5
        
        # Build recommendation
        if sentiment_score >= 70:
            recommendation = "REDUCE RISK - Consider taking profits or tightening stops"
        elif sentiment_score >= 55:
            recommendation = "CAUTIOUS - Normal position sizing with careful entry selection"
        elif sentiment_score >= 45:
            recommendation = "NEUTRAL - Standard trading conditions"
        elif sentiment_score >= 30:
            recommendation = "OPPORTUNISTIC - Look for quality setups at good prices"
        else:
            recommendation = "CONTRARIAN - Extreme fear may present buying opportunities"
        
        return {
            "sentiment_score": sentiment_score,
            "sentiment_label": sentiment_label,
            "bias": bias,
            "bias_reason": bias_reason,
            "recommendation": recommendation,
            "position_sizing_multiplier": position_sizing,
            "factors": sentiment_factors,
            "timestamp": datetime.now().isoformat(),
            "notes": [
                "Sentiment score: 0-100 (0=Extreme Fear, 50=Neutral, 100=Extreme Greed)",
                "Position sizing multiplier: 0.5=Half size, 1.0=Full size",
                "Sentiment is derived from market volatility, trends, and news events",
                "Use as a contrarian indicator - extreme readings often signal reversals"
            ]
        }
        
    except Exception as e:
        logger.error(f"Market sentiment error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/correlation/{symbol}")
async def get_correlation_analysis(symbol: str):
    """Get correlation analysis with major instruments"""
    try:
        # Normalize symbol
        symbol = symbol.upper()
        if not symbol.endswith('c'):
            symbol = symbol + 'c'
        
        if not mt5_service:
            raise HTTPException(status_code=500, detail="MT5 service not initialized")
        
        logger.info(f"Correlation analysis requested for {symbol}")
        
        # Connect to MT5
        mt5_service.connect()
        mt5_service.ensure_symbol(symbol)
        
        # Define correlation pairs based on asset type
        correlation_pairs = []
        
        if "XAU" in symbol or "GOLD" in symbol:
            # Gold correlations
            correlation_pairs = [
                {"symbol": "DXY", "relationship": "inverse", "strength": 0.85, "description": "US Dollar Index - strong inverse correlation"},
                {"symbol": "USDJPYc", "relationship": "inverse", "strength": 0.65, "description": "USD/JPY - moderate inverse correlation"},
                {"symbol": "EURUSDc", "relationship": "positive", "strength": 0.70, "description": "EUR/USD - positive correlation"},
                {"symbol": "BTCUSDc", "relationship": "positive", "strength": 0.55, "description": "Bitcoin - moderate positive correlation (risk-on)"},
                {"symbol": "US10Y", "relationship": "inverse", "strength": 0.60, "description": "US 10-Year Yield - inverse correlation"}
            ]
        
        elif "BTC" in symbol or "ETH" in symbol:
            # Crypto correlations
            correlation_pairs = [
                {"symbol": "ETHUSDc" if "BTC" in symbol else "BTCUSDc", "relationship": "positive", "strength": 0.90, "description": "Major crypto correlation"},
                {"symbol": "XAUUSDc", "relationship": "positive", "strength": 0.55, "description": "Gold - moderate positive correlation (risk-on)"},
                {"symbol": "DXY", "relationship": "inverse", "strength": 0.70, "description": "US Dollar Index - inverse correlation"},
                {"symbol": "SPX", "relationship": "positive", "strength": 0.75, "description": "S&P 500 - risk-on correlation"},
                {"symbol": "VIX", "relationship": "inverse", "strength": 0.65, "description": "VIX - inverse correlation (fear gauge)"}
            ]
        
        elif "EUR" in symbol or "GBP" in symbol:
            # Forex major correlations
            correlation_pairs = [
                {"symbol": "DXY", "relationship": "inverse", "strength": 0.95, "description": "US Dollar Index - very strong inverse"},
                {"symbol": "XAUUSDc", "relationship": "positive", "strength": 0.70, "description": "Gold - positive correlation"},
                {"symbol": "USDJPYc", "relationship": "inverse", "strength": 0.60, "description": "USD/JPY - inverse correlation"},
                {"symbol": "US10Y", "relationship": "inverse", "strength": 0.50, "description": "US 10-Year Yield - moderate inverse"}
            ]
        
        elif "JPY" in symbol:
            # JPY correlations (safe haven)
            correlation_pairs = [
                {"symbol": "XAUUSDc", "relationship": "inverse", "strength": 0.65, "description": "Gold - inverse correlation"},
                {"symbol": "VIX", "relationship": "positive", "strength": 0.70, "description": "VIX - positive correlation (risk-off)"},
                {"symbol": "SPX", "relationship": "inverse", "strength": 0.60, "description": "S&P 500 - inverse correlation"},
                {"symbol": "US10Y", "relationship": "positive", "strength": 0.55, "description": "US 10-Year Yield - positive correlation"}
            ]
        
        else:
            # Generic forex correlations
            correlation_pairs = [
                {"symbol": "DXY", "relationship": "inverse", "strength": 0.70, "description": "US Dollar Index"},
                {"symbol": "XAUUSDc", "relationship": "positive", "strength": 0.50, "description": "Gold"},
                {"symbol": "EURUSDc", "relationship": "positive", "strength": 0.60, "description": "EUR/USD"}
            ]
        
        # Add current price context
        try:
            quote = mt5_service.get_quote(symbol)
            current_price = (quote.bid + quote.ask) / 2 if quote else None
        except:
            current_price = None
        
        # Build analysis summary
        strong_correlations = [p for p in correlation_pairs if p["strength"] >= 0.70]
        inverse_correlations = [p for p in correlation_pairs if p["relationship"] == "inverse"]
        
        summary = f"Found {len(correlation_pairs)} correlation pairs. "
        if strong_correlations:
            summary += f"{len(strong_correlations)} strong correlations (>0.70). "
        if inverse_correlations:
            summary += f"{len(inverse_correlations)} inverse relationships."
        
        return {
            "symbol": symbol,
            "current_price": current_price,
            "correlation_pairs": correlation_pairs,
            "summary": summary,
            "total_pairs": len(correlation_pairs),
            "strong_correlations": len(strong_correlations),
            "timestamp": datetime.now().isoformat(),
            "notes": [
                "Correlations are approximate and can change over time",
                "Strong correlation: >0.70, Moderate: 0.50-0.70, Weak: <0.50",
                "Use correlations for risk management and confirmation"
            ]
        }
        
    except Exception as e:
        logger.error(f"Correlation analysis error for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bracket/analyze", dependencies=[Depends(verify_api_key)])
async def analyze_bracket_conditions(request: Request):
    """Analyze bracket trade conditions"""
    try:
        body = await request.json()
        symbol = body.get("symbol", "").upper()
        timeframe = body.get("timeframe", "M15")
        
        if not symbol:
            raise HTTPException(status_code=400, detail="symbol is required")
        
        # Normalize symbol
        if not symbol.endswith('c'):
            symbol = symbol + 'c'
        
        if not mt5_service or not indicator_bridge:
            raise HTTPException(status_code=500, detail="Services not initialized")
        
        logger.info(f"Bracket analysis requested for {symbol} on {timeframe}")
        
        # Connect and ensure symbol
        mt5_service.connect()
        mt5_service.ensure_symbol(symbol)
        
        # Get indicator data
        multi = indicator_bridge.get_multi(symbol)
        tf_data = multi.get(timeframe, {})
        
        if not tf_data:
            raise HTTPException(status_code=404, detail=f"No data available for {symbol} on {timeframe}")
        
        # Extract key indicators
        rsi = float(tf_data.get("rsi", 50))
        adx = float(tf_data.get("adx", 20))
        atr = float(tf_data.get("atr14", 0))
        
        # Get close price
        close_data = tf_data.get("close", 0)
        if isinstance(close_data, list):
            close = float(close_data[-1]) if close_data else 0.0
        else:
            close = float(close_data) if close_data else 0.0
        close = float(tf_data.get("current_close", close))
        
        ema20 = float(tf_data.get("ema20", 0))
        ema50 = float(tf_data.get("ema50", 0))
        ema200 = float(tf_data.get("ema200", 0))
        
        # Analyze conditions
        conditions = {}
        
        # 1. Consolidation (price near EMAs, low ADX)
        price_near_ema20 = abs(close - ema20) / close < 0.002 if close > 0 else False
        price_near_ema50 = abs(close - ema50) / close < 0.002 if close > 0 else False
        conditions["has_consolidation"] = (price_near_ema20 or price_near_ema50) and adx < 25
        
        # 2. Volatility squeeze (low ATR relative to price)
        atr_percent = (atr / close * 100) if close > 0 else 0
        conditions["has_volatility_squeeze"] = atr_percent < 0.5
        
        # 3. Breakout conditions (price at key level, building momentum)
        at_ema200 = abs(close - ema200) / close < 0.003 if close > 0 and ema200 > 0 else False
        conditions["has_breakout_conditions"] = at_ema200 or (adx > 20 and adx < 30)
        
        # 4. Reversal conditions (RSI extreme, price at EMA)
        rsi_extreme = rsi > 70 or rsi < 30
        conditions["has_reversal_conditions"] = rsi_extreme and (price_near_ema20 or price_near_ema50)
        
        # 5. News events (check if in blackout)
        try:
            from infra.news_service import NewsService
            ns = NewsService()
            now = datetime.utcnow()
            
            # Determine category based on symbol
            category = "crypto" if ("BTC" in symbol or "ETH" in symbol) else "macro"
            conditions["has_news_events"] = ns.is_blackout(category=category, now=now)
        except Exception as e:
            logger.warning(f"Could not check news events: {e}")
            conditions["has_news_events"] = False
        
        # Determine recommendation
        appropriate = False
        confidence = 0.0
        recommendation = "NO_BRACKET"
        reasoning = ""
        
        if conditions["has_news_events"]:
            appropriate = False
            confidence = 0.0
            recommendation = "NO_BRACKET"
            reasoning = "News blackout active - avoid bracket trades during high-impact events"
        
        elif conditions["has_consolidation"] and not conditions["has_volatility_squeeze"]:
            appropriate = True
            confidence = 0.75
            recommendation = "BREAKOUT_BRACKET"
            reasoning = f"Consolidation detected (ADX={adx:.1f}, RSI={rsi:.1f}). Price coiling near EMA levels - ideal for breakout bracket trade"
        
        elif conditions["has_breakout_conditions"] and adx < 30:
            appropriate = True
            confidence = 0.65
            recommendation = "BREAKOUT_BRACKET"
            reasoning = f"Price at key level with building momentum (ADX={adx:.1f}). Breakout bracket trade recommended"
        
        elif conditions["has_reversal_conditions"]:
            appropriate = True
            confidence = 0.60
            recommendation = "REVERSAL_BRACKET"
            reasoning = f"RSI extreme ({rsi:.1f}) at support/resistance. Reversal bracket trade may capture bounce or breakdown"
        
        elif conditions["has_volatility_squeeze"]:
            appropriate = True
            confidence = 0.55
            recommendation = "BREAKOUT_BRACKET"
            reasoning = f"Volatility squeeze detected (ATR={atr_percent:.2f}%). Expansion likely - bracket trade can capture direction"
        
        else:
            appropriate = False
            confidence = 0.3
            recommendation = "NO_BRACKET"
            reasoning = f"No clear setup. ADX={adx:.1f}, RSI={rsi:.1f}. Wait for better conditions (consolidation or extreme RSI)"
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "appropriate": appropriate,
            "confidence": confidence,
            "conditions": conditions,
            "reasoning": reasoning,
            "recommendation": recommendation,
            "timestamp": datetime.now().isoformat(),
            "market_data": {
                "rsi": rsi,
                "adx": adx,
                "atr": atr,
                "close": close,
                "ema20": ema20,
                "ema50": ema50,
                "ema200": ema200
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bracket analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/recommendation_stats")
async def get_recommendation_stats(
    symbol: str = None,
    trade_type: str = None,
    timeframe: str = None,
    session: str = None,
    days_back: int = 30
):
    """Get historical recommendation performance statistics"""
    try:
        from infra.recommendation_tracker import RecommendationTracker
        
        tracker = RecommendationTracker()
        stats = tracker.get_stats(
            symbol=symbol,
            trade_type=trade_type,
            timeframe=timeframe,
            session=session,
            days_back=days_back
        )
        
        # Get best setups
        best_setups = tracker.get_best_setups(min_trades=3)
        
        # Get recent recommendations
        recent = tracker.get_recent_recommendations(limit=5, symbol=symbol, executed_only=True)
        
        return {
            "stats": stats,
            "best_setups": best_setups,
            "recent_recommendations": recent,
            "filters": {
                "symbol": symbol,
                "trade_type": trade_type,
                "timeframe": timeframe,
                "session": session,
                "days_back": days_back
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting recommendation stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/confluence/{symbol}")
async def get_confluence_score(symbol: str):
    """Get multi-timeframe confluence score for a symbol"""
    if not indicator_bridge:
        raise HTTPException(status_code=500, detail="Indicator bridge not initialized")
    
    try:
        from infra.confluence_calculator import ConfluenceCalculator
        
        # Normalize symbol
        symbol = normalize_symbol(symbol)
        
        logger.info(f"Calculating confluence for {symbol}")
        
        # Fix 18: Use singleton ConfluenceCalculator instance
        global confluence_calculator
        if 'confluence_calculator' not in globals() or confluence_calculator is None:
            confluence_calculator = ConfluenceCalculator(indicator_bridge)
        
        result = confluence_calculator.calculate_confluence(symbol)
        
        return result
        
    except Exception as e:
        logger.error(f"Error calculating confluence for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/confluence/multi-timeframe/{symbol}")
async def get_confluence_multi_timeframe(symbol: str):
    """Get multi-timeframe confluence scores for each timeframe separately"""
    if not indicator_bridge:
        raise HTTPException(status_code=500, detail="Indicator bridge not initialized")
    
    try:
        from infra.confluence_calculator import ConfluenceCalculator
        
        # Normalize symbol
        symbol = normalize_symbol(symbol)
        
        logger.info(f"Calculating per-timeframe confluence for {symbol}")
        
        # Fix 18: Use singleton ConfluenceCalculator instance
        # Fix 19: Use cached M1 components (initialized at startup)
        global confluence_calculator, m1_analyzer_cached, m1_data_fetcher_cached
        
        # Get singleton calculator instance (or create if not initialized)
        if 'confluence_calculator' not in globals() or confluence_calculator is None:
            from infra.confluence_calculator import ConfluenceCalculator
            confluence_calculator = ConfluenceCalculator(indicator_bridge)
        
        # Use cached M1 components (Fix 19: M1 Analyzer Caching)
        m1_analyzer = m1_analyzer_cached if 'm1_analyzer_cached' in globals() else None
        m1_data_fetcher = m1_data_fetcher_cached if 'm1_data_fetcher_cached' in globals() else None
        
        # If cached components not available, try to initialize (fallback)
        if not m1_analyzer or not m1_data_fetcher:
            try:
                from infra.m1_data_fetcher import M1DataFetcher
                from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
                
                global mt5_service
                if mt5_service and mt5_service.connect():
                    if not m1_data_fetcher:
                        m1_data_fetcher = M1DataFetcher(
                            data_source=mt5_service,
                            max_candles=200,
                            cache_ttl=300
                        )
                        # Cache for next time
                        m1_data_fetcher_cached = m1_data_fetcher
                    
                    if not m1_analyzer:
                        try:
                            from infra.m1_session_volatility_profile import SessionVolatilityProfile
                            from infra.m1_asset_profiles import AssetProfileManager
                            asset_profiles = AssetProfileManager("config/asset_profiles.json")
                            session_manager = SessionVolatilityProfile(asset_profiles)
                            m1_analyzer = M1MicrostructureAnalyzer(
                                mt5_service=mt5_service,
                                session_manager=session_manager,
                                asset_profiles=asset_profiles
                            )
                        except Exception:
                            # Fallback: initialize without optional dependencies
                            m1_analyzer = M1MicrostructureAnalyzer(mt5_service=mt5_service)
                        # Cache for next time
                        m1_analyzer_cached = m1_analyzer
            except Exception as e:
                logger.debug(f"M1 components not available for confluence calculation: {e}")
                # Continue without M1 - other timeframes will still work
        
        result = confluence_calculator.calculate_confluence_per_timeframe(
            symbol=symbol,
            m1_analyzer=m1_analyzer,
            m1_data_fetcher=m1_data_fetcher
        )
        
        # Add metadata
        from datetime import timezone
        response = {
            "symbol": symbol,
            "timeframes": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cache_age_seconds": 0
        }
        
        # Calculate cache age if available (using public method)
        cache_info = confluence_calculator.get_cache_info(symbol)
        if cache_info:
            response["cache_age_seconds"] = round(cache_info["cache_age_seconds"], 1)
        
        return response
        
    except Exception as e:
        logger.error(f"Error calculating per-timeframe confluence for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/confluence/debug/{symbol}")
async def debug_confluence_data(symbol: str):
    """Debug endpoint to check what data is available for confluence calculation"""
    if not indicator_bridge:
        return {"error": "Indicator bridge not initialized"}
    
    try:
        symbol = normalize_symbol(symbol)
        multi_data = indicator_bridge.get_multi(symbol)
        
        debug_info = {
            "symbol": symbol,
            "multi_data_keys": list(multi_data.keys()) if multi_data else [],
            "multi_data_empty": not multi_data,
            "timeframes": {}
        }
        
        for tf in ["M5", "M15", "H1"]:
            tf_data = multi_data.get(tf, {}) if multi_data else {}
            debug_info["timeframes"][tf] = {
                "exists": tf in multi_data if multi_data else False,
                "keys": list(tf_data.keys())[:20] if tf_data else [],  # First 20 keys
                "has_atr14": "atr14" in tf_data,
                "has_current_close": "current_close" in tf_data,
                "atr14_value": tf_data.get("atr14") if tf_data else None,
                "current_close_value": tf_data.get("current_close") if tf_data else None
            }
        
        return debug_info
    except Exception as e:
        logger.error(f"Error in debug endpoint for {symbol}: {e}", exc_info=True)
        return {"error": str(e)}


@app.get("/api/v1/session/current")
async def get_current_session():
    """Get current trading session with recommendations"""
    try:
        from infra.session_analyzer import SessionAnalyzer
        
        analyzer = SessionAnalyzer()
        session = analyzer.get_current_session()
        
        # Add trading suitability
        session["is_good_time_to_trade"] = analyzer.is_good_time_to_trade()
        session["optimal_symbols"] = analyzer.get_optimal_symbols()
        
        return session
        
    except Exception as e:
        logger.error(f"Error getting current session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/test_indicator_bridge/{symbol}")
async def test_indicator_bridge(symbol: str):
    """Test endpoint to verify indicator bridge is working"""
    if not indicator_bridge:
        raise HTTPException(status_code=500, detail="Indicator bridge not initialized")
    
    try:
        # Normalize symbol
        symbol = normalize_symbol(symbol)
        
        # Test indicator bridge directly
        multi_data = indicator_bridge.get_multi(symbol)
        
        return {
            "symbol": symbol,
            "multi_data_keys": list(multi_data.keys()) if multi_data else [],
            "multi_data_count": len(multi_data) if multi_data else 0,
            "has_data": bool(multi_data),
            "sample_data": {
                "M5": list(multi_data.get("M5", {}).keys())[:5] if multi_data.get("M5") else [],
                "H4": list(multi_data.get("H4", {}).keys())[:5] if multi_data.get("H4") else []
            } if multi_data else {}
        }
        
    except Exception as e:
        logger.error(f"Test indicator bridge error for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/features/advanced/{symbol}")
async def get_advanced_features(symbol: str):
    """
    Get Advanced Technical Features for a symbol

    Returns 11 institutional-grade indicators:
    - RMAG (Relative Moving Average Gap)
    - EMA Slope Strength
    - Bollinger-ADX Fusion
    - RSI-ADX Pressure Ratio
    - Candle Body-Wick Profile
    - Liquidity Targets (PDH/PDL, swings, equal levels)
    - Fair Value Gaps (FVG)
    - VWAP Deviation Zones
    - Momentum Acceleration
    - Multi-Timeframe Alignment Score
    - Volume Profile (HVN/LVN)
    """
    try:
        from infra.feature_builder_advanced import build_features_advanced
        
        if not mt5_service or not indicator_bridge:
            raise HTTPException(status_code=500, detail="Services not initialized")
        
        # Normalize symbol (add 'c' suffix for broker, preserve case)
        original_symbol = symbol
        if not symbol.endswith('c') and not symbol.endswith('C'):
            symbol = symbol + 'c'
        
        logger.info(f"Advanced features requested for {original_symbol} → normalized to {symbol}")
        
        # Build Advanced features
        advanced_features = build_features_advanced(
            symbol=symbol,
            mt5svc=mt5_service,
            bridge=indicator_bridge,
            timeframes=["M5", "M15", "H1"]
        )
        
        # Convert numpy types to Python native types for JSON serialization
        advanced_features = convert_numpy_types(advanced_features)
        
        return advanced_features
        
    except Exception as e:
        logger.error(f"Advanced features error for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    import numpy as np
    
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    # Handle numpy bool types (must come before other numpy checks)
    # Check for numpy bool types - handle different numpy versions
    elif hasattr(np, 'bool_') and isinstance(obj, np.bool_):
        return bool(obj)
    elif type(obj).__module__ == 'numpy' and type(obj).__name__ in ('bool_', 'bool8'):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return [convert_numpy_types(item) for item in obj.tolist()]
    elif hasattr(obj, '__class__') and 'numpy' in str(type(obj)):
        # Catch-all for other numpy types
        if hasattr(obj, 'item'):
            return convert_numpy_types(obj.item())
        elif hasattr(obj, '__bool__'):
            return bool(obj)
        elif hasattr(obj, '__int__'):
            return int(obj)
        elif hasattr(obj, '__float__'):
            return float(obj)
    return obj

@app.get("/api/v1/multi_timeframe/{symbol}")
async def get_multi_timeframe_analysis(symbol: str):
    """
    Get proper multi-timeframe analysis (H4 → H1 → M30 → M15 → M5)
    Enhanced with V8 Advanced Technical Features
    
    Returns top-down analysis:
    - H4: Macro bias (overall trend direction)
    - H1: Swing context (momentum confirmation)
    - M30: Setup frame (structure validation)
    - M15: Trigger frame (entry signals)
    - M5: Execution frame (precise timing)
    - V8: Institutional-grade indicators (RMAG, EMA Slope, MTF Alignment, etc.)
    """
    if not indicator_bridge:
        raise HTTPException(status_code=500, detail="Indicator bridge not initialized")
    
    try:
        from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
        
        # Normalize symbol
        symbol = normalize_symbol(symbol)
        
        logger.info(f"Multi-timeframe analysis (Advanced-enhanced) for {symbol}")
        
        # Debug: Check if indicator bridge has data
        multi_data = indicator_bridge.get_multi(symbol)
        logger.info(f"Indicator bridge data keys: {list(multi_data.keys()) if multi_data else 'None'}")
        
        # Initialize analyzer with V8 support
        analyzer = MultiTimeframeAnalyzer(indicator_bridge, mt5_service=mt5_service)
        result = analyzer.analyze(symbol)
        
        # Debug: Log result (truncated)
        logger.info(f"Multi-timeframe result: alignment={result.get('alignment_score')}, "
                   f"action={result.get('recommendation', {}).get('action')}, "
                   f"v8_summary={result.get('v8_summary', 'N/A')}")
        
        # Convert numpy types to native Python types for JSON serialization
        result = convert_numpy_types(result)
        
        return result
        
    except Exception as e:
        logger.error(f"Multi-timeframe analysis error for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/candles/{symbol}/{timeframe}")
async def get_streamer_candles(
    symbol: str,
    timeframe: str,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get candlestick data from Multi-Timeframe Streamer.
    
    This endpoint provides access to the continuously updated candlestick buffers.
    Note: For guaranteed fresh data (e.g., ChatGPT analysis), use IndicatorBridge
    which fetches directly from MT5.
    
    Parameters:
    - symbol: Trading symbol (e.g., BTCUSDc, XAUUSDc)
    - timeframe: One of M1, M5, M15, M30, H1, H4
    - limit: Maximum number of candles to return (default: all in buffer)
    
    Returns:
    - List of candles with OHLCV data
    - Latest candle information
    - Buffer statistics
    """
    if not multi_tf_streamer:
        raise HTTPException(
            status_code=503,
            detail="Multi-Timeframe Streamer not initialized"
        )
    
    try:
        # Normalize symbol
        symbol = normalize_symbol(symbol)
        
        # Validate timeframe
        timeframe = timeframe.upper()
        valid_timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4']
        if timeframe not in valid_timeframes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe. Must be one of: {', '.join(valid_timeframes)}"
            )
        
        # Check if streamer is running
        if not multi_tf_streamer.is_running:
            raise HTTPException(
                status_code=503,
                detail="Multi-Timeframe Streamer is not running"
            )
        
        # Check if symbol is being streamed (normalize config symbols the same way as input)
        streamed_symbols = [multi_tf_streamer._normalize_symbol(s) for s in multi_tf_streamer.config.symbols]
        if symbol not in streamed_symbols:
            raise HTTPException(
                status_code=404,
                detail=f"Symbol {symbol} is not being streamed. Available symbols: {', '.join(multi_tf_streamer.config.symbols)}"
            )
        
        # Get candles from streamer
        candles = multi_tf_streamer.get_candles(symbol, timeframe, limit=limit)
        
        if not candles:
            # Check if buffer exists (streamer initialized buffers)
            if symbol not in multi_tf_streamer.buffers:
                raise HTTPException(
                    status_code=404,
                    detail=f"Buffer not initialized for {symbol}. Streamer may still be starting up."
                )
            if timeframe not in multi_tf_streamer.buffers.get(symbol, {}):
                raise HTTPException(
                    status_code=404,
                    detail=f"Buffer not initialized for {symbol}/{timeframe}. Streamer may still be starting up."
                )
            # Buffer exists but empty - data hasn't been fetched yet
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "candles": [],
                "count": 0,
                "latest": None,
                "message": f"No candles available yet for {symbol}/{timeframe}. Streamer may still be fetching initial data. Check /api/v1/streamer/status for details."
            }
        
        # Get latest candle
        latest = multi_tf_streamer.get_latest_candle(symbol, timeframe)
        
        # Convert candles to dict format
        candles_data = [candle.to_dict() for candle in candles]
        
        # Get streamer metrics for context
        metrics = multi_tf_streamer.get_metrics()
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": candles_data,
            "count": len(candles_data),
            "latest": latest.to_dict() if latest else None,
            "buffer_size": len(candles_data),
            "streamer_status": {
                "running": multi_tf_streamer.is_running,
                "memory_usage_mb": metrics.get("memory_usage_mb", 0.0),
                "total_candles_fetched": metrics.get("total_candles_fetched", 0)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting streamer candles for {symbol} {timeframe}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/candles/{symbol}/{timeframe}/latest")
async def get_latest_streamer_candle(symbol: str, timeframe: str) -> Dict[str, Any]:
    """
    Get the latest candlestick from the streamer.
    
    Quick endpoint to get just the most recent candle without full history.
    """
    if not multi_tf_streamer:
        raise HTTPException(
            status_code=503,
            detail="Multi-Timeframe Streamer not initialized"
        )
    
    try:
        symbol = normalize_symbol(symbol)
        timeframe = timeframe.upper()
        
        # Check if streamer is running
        if not multi_tf_streamer.is_running:
            raise HTTPException(
                status_code=503,
                detail="Multi-Timeframe Streamer is not running"
            )
        
        # Check if symbol is being streamed (normalize config symbols the same way as input)
        streamed_symbols = [multi_tf_streamer._normalize_symbol(s) for s in multi_tf_streamer.config.symbols]
        if symbol not in streamed_symbols:
            raise HTTPException(
                status_code=404,
                detail=f"Symbol {symbol} is not being streamed. Available symbols: {', '.join(multi_tf_streamer.config.symbols)}"
            )
        
        # Check if timeframe is valid
        valid_timeframes = list(multi_tf_streamer.config.buffer_sizes.keys())
        if timeframe not in valid_timeframes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe {timeframe}. Valid timeframes: {', '.join(valid_timeframes)}"
            )
        
        latest = multi_tf_streamer.get_latest_candle(symbol, timeframe)
        
        if not latest:
            # Check if buffer exists (streamer initialized buffers)
            if symbol not in multi_tf_streamer.buffers:
                raise HTTPException(
                    status_code=404,
                    detail=f"Buffer not initialized for {symbol}. Streamer may still be starting up."
                )
            if timeframe not in multi_tf_streamer.buffers.get(symbol, {}):
                raise HTTPException(
                    status_code=404,
                    detail=f"Buffer not initialized for {symbol}/{timeframe}. Streamer may still be starting up."
                )
            # Buffer exists but empty - data hasn't been fetched yet
            metrics = multi_tf_streamer.get_metrics()
            raise HTTPException(
                status_code=404,
                detail=f"No candles available yet for {symbol}/{timeframe}. Streamer may still be fetching initial data. Check /api/v1/streamer/status for details."
            )
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "candle": latest.to_dict(),
            "timestamp": latest.time.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest candle for {symbol} {timeframe}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/streamer/status")
async def get_streamer_status() -> Dict[str, Any]:
    """
    Get Multi-Timeframe Streamer status and metrics.
    
    Returns information about what symbols are being streamed,
    buffer sizes, memory usage, and performance metrics.
    """
    if not multi_tf_streamer:
        return {
            "status": "not_initialized",
            "message": "Multi-Timeframe Streamer is not running"
        }
    
    try:
        metrics = multi_tf_streamer.get_metrics()
        
        # Get buffer status for each symbol/timeframe
        buffer_status = {}
        for symbol in multi_tf_streamer.config.symbols:
            buffer_status[symbol] = {}
            for tf in multi_tf_streamer.config.buffer_sizes.keys():
                candles = multi_tf_streamer.get_candles(symbol, tf)
                buffer_status[symbol][tf] = {
                    "count": len(candles),
                    "max_size": multi_tf_streamer.config.buffer_sizes[tf],
                    "has_data": len(candles) > 0
                }
        
        return {
            "status": "running" if multi_tf_streamer.is_running else "stopped",
            "symbols": multi_tf_streamer.config.symbols,
            "timeframes": list(multi_tf_streamer.config.buffer_sizes.keys()),
            "buffer_sizes": multi_tf_streamer.config.buffer_sizes,
            "refresh_intervals": multi_tf_streamer.config.refresh_intervals,
            "database_enabled": multi_tf_streamer.config.enable_database,
            "metrics": metrics,
            "buffer_status": buffer_status
        }
        
    except Exception as e:
        logger.error(f"Error getting streamer status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data/validate/{symbol}")
async def validate_data_quality(symbol: str):
    """Validate data quality and freshness"""
    try:
        # Normalize symbol
        symbol = symbol.upper()
        if not symbol.endswith('c'):
            symbol = symbol + 'c'
        
        if not mt5_service or not indicator_bridge:
            raise HTTPException(status_code=500, detail="Services not initialized")
        
        logger.info(f"Data validation requested for {symbol}")
        
        # Connect and ensure symbol
        mt5_service.connect()
        mt5_service.ensure_symbol(symbol)
        
        # Get multi-timeframe data
        multi = indicator_bridge.get_multi(symbol)
        
        timeframes = ["M1", "M5", "M15", "M30", "H1", "H4"]
        validation_results = []
        overall_quality = "GOOD"
        issues_found = []
        
        for tf in timeframes:
            tf_data = multi.get(tf, {})
            
            if not tf_data:
                validation_results.append({
                    "timeframe": tf,
                    "status": "MISSING",
                    "data_points": 0,
                    "freshness": "N/A",
                    "quality": "POOR"
                })
                issues_found.append(f"{tf}: No data available")
                overall_quality = "POOR"
                continue
            
            # Check data completeness
            required_fields = ["close", "rsi", "adx", "atr14", "ema20", "ema50"]
            missing_fields = [f for f in required_fields if f not in tf_data or tf_data[f] is None]
            
            # Count data points
            close_data = tf_data.get("close", [])
            data_points = len(close_data) if isinstance(close_data, list) else 1
            
            # Check freshness (if timestamp available)
            freshness = "FRESH"
            age_minutes = 0
            
            # Determine quality
            if missing_fields:
                quality = "POOR"
                overall_quality = "POOR"
                issues_found.append(f"{tf}: Missing fields: {', '.join(missing_fields)}")
            elif data_points < 50:
                quality = "FAIR"
                if overall_quality == "GOOD":
                    overall_quality = "FAIR"
                issues_found.append(f"{tf}: Insufficient data points ({data_points})")
            else:
                quality = "GOOD"
            
            validation_results.append({
                "timeframe": tf,
                "status": "OK",
                "data_points": data_points,
                "freshness": freshness,
                "quality": quality,
                "missing_fields": missing_fields,
                "has_indicators": len(missing_fields) == 0
            })
        
        # Overall assessment
        good_count = sum(1 for r in validation_results if r.get("quality") == "GOOD")
        poor_count = sum(1 for r in validation_results if r.get("quality") == "POOR")
        
        if poor_count > 0:
            overall_quality = "POOR"
            recommendation = "Data quality issues detected. Avoid trading until resolved."
        elif good_count < 3:
            overall_quality = "FAIR"
            recommendation = "Some data quality issues. Trade with caution."
        else:
            overall_quality = "GOOD"
            recommendation = "Data quality is good. Safe to trade."
        
        return {
            "symbol": symbol,
            "overall_quality": overall_quality,
            "recommendation": recommendation,
            "timeframes": validation_results,
            "issues_found": issues_found,
            "total_timeframes": len(timeframes),
            "good_timeframes": good_count,
            "timestamp": datetime.now().isoformat(),
            "notes": [
                "GOOD: All data present and fresh",
                "FAIR: Some missing data or indicators",
                "POOR: Critical data missing or stale"
            ]
        }
        
    except Exception as e:
        logger.error(f"Data validation error for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# PRICE ALERTS ENDPOINTS
# ============================================================================

@app.post("/api/v1/alerts/create")
async def create_price_alert(request: Request):
    """Create a new price alert"""
    try:
        body = await request.json()
        symbol = body.get("symbol", "").upper()
        alert_type = body.get("alert_type", "").lower()  # "above" or "below"
        target_price = float(body.get("target_price", 0))
        message = body.get("message", "")
        
        # Validate inputs
        if not symbol:
            raise HTTPException(status_code=400, detail="symbol is required")
        if alert_type not in ["above", "below"]:
            raise HTTPException(status_code=400, detail="alert_type must be 'above' or 'below'")
        if target_price <= 0:
            raise HTTPException(status_code=400, detail="target_price must be positive")
        
        # Remove 'c' suffix if present (alerts work with base symbols)
        if symbol.endswith('C'):
            symbol = symbol[:-1]
        
        # Create alert
        from infra.price_alerts import get_alert_manager
        alert_manager = get_alert_manager()
        alert = alert_manager.create_alert(
            symbol=symbol,
            alert_type=alert_type,
            target_price=target_price,
            message=message or f"Price alert: {symbol} {alert_type} ${target_price}"
        )
        
        logger.info(f"Created price alert: {symbol} {alert_type} {target_price}")
        
        return {
            "ok": True,
            "alert": alert.to_dict(),
            "message": f"✅ Alert created: {symbol} {alert_type} ${target_price:.2f}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating alert: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/alerts")
async def get_price_alerts(symbol: Optional[str] = None, active_only: bool = True):
    """Get price alerts, optionally filtered by symbol"""
    try:
        from infra.price_alerts import get_alert_manager
        alert_manager = get_alert_manager()
        
        if active_only:
            alerts = alert_manager.get_active_alerts(symbol=symbol)
        else:
            alerts = alert_manager.get_all_alerts()
            if symbol:
                symbol_upper = symbol.upper()
                if symbol_upper.endswith('C'):
                    symbol_upper = symbol_upper[:-1]
                alerts = [a for a in alerts if a.symbol.upper() == symbol_upper]
        
        return {
            "alerts": [alert.to_dict() for alert in alerts],
            "count": len(alerts),
            "active_count": len([a for a in alerts if not a.triggered]),
            "triggered_count": len([a for a in alerts if a.triggered])
        }
    
    except Exception as e:
        logger.error(f"Error getting alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/alerts/{alert_id}")
async def delete_price_alert(alert_id: str):
    """Delete a price alert"""
    try:
        from infra.price_alerts import get_alert_manager
        alert_manager = get_alert_manager()
        
        if alert_manager.delete_alert(alert_id):
            logger.info(f"Deleted price alert: {alert_id}")
            return {
                "ok": True,
                "message": f"✅ Alert {alert_id} deleted"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting alert: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/alerts/start_monitoring")
async def start_alert_monitoring(background_tasks: BackgroundTasks, check_interval: int = 60):
    """Start price alert monitoring in background"""
    try:
        from infra.price_alerts import get_alert_manager
        alert_manager = get_alert_manager()
        
        # Start monitoring with MT5 service and Discord bot
        # Note: Discord bot integration will be added via the monitoring service
        alert_manager.start_monitoring(
            mt5_service=mt5_service,
            discord_bot=None,  # Will be integrated with trade_bot
            check_interval=check_interval
        )
        
        logger.info(f"Started price alert monitoring (interval: {check_interval}s)")
        
        return {
            "ok": True,
            "message": f"✅ Price monitoring started (checks every {check_interval}s)",
            "check_interval": check_interval
        }
    
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/alerts/stop_monitoring")
async def stop_alert_monitoring():
    """Stop price alert monitoring"""
    try:
        from infra.price_alerts import get_alert_manager
        alert_manager = get_alert_manager()
        alert_manager.stop_monitoring()
        
        logger.info("Stopped price alert monitoring")
        
        return {
            "ok": True,
            "message": "✅ Price monitoring stopped"
        }
    
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts/view", response_class=HTMLResponse, tags=["alerts"])
async def view_alerts():
    """Display price alerts dashboard"""
    try:
        from infra.price_alerts import get_alert_manager
        alert_manager = get_alert_manager()
        all_alerts = alert_manager.get_all_alerts()
        
        # Sort by created_at (newest first)
        all_alerts.sort(key=lambda x: x.created_at if x.created_at else 0, reverse=True)
        
        # Build table rows
        table_rows = ""
        if not all_alerts:
            table_rows = '<tr><td colspan="7" class="empty">No alerts configured</td></tr>'
        else:
            for alert in all_alerts:
                alert_id = alert.alert_id
                symbol = alert.symbol
                alert_type = alert.alert_type
                target_price = alert.target_price
                triggered = alert.triggered
                created_at = alert.created_at
                message = alert.message or f"{symbol} {alert_type} ${target_price:.2f}"
                
                status_class = "status-triggered" if triggered else "status-active"
                status_text = "TRIGGERED" if triggered else "ACTIVE"
                created_display = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "N/A"
                
                table_rows += f"""
                <tr>
                    <td><div class="cell-text">{created_display}</div></td>
                    <td>{symbol}</td>
                    <td class="alert-type">{alert_type.upper()}</td>
                    <td><div class="price">{target_price:.2f}</div></td>
                    <td class="{status_class}">{status_text}</td>
                    <td><div class="cell-text">{message}</div></td>
                    <td><button onclick="deleteAlert('{alert_id}')" class="delete-btn">Delete</button></td>
                </tr>
                """
        
        active_count = len([a for a in all_alerts if not a.triggered])
        triggered_count = len([a for a in all_alerts if a.triggered])
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Price Alerts - Synergis Trading</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #0a0e27; color: #e0e6ed; }}
                .container {{ max-width: 1800px; margin: 0 auto; }}
                h1 {{ color: #4fc3f7; margin-bottom: 10px; font-size: 24px; }}
                .nav {{ margin-bottom: 20px; padding: 15px; background: #1a1f3a; border-radius: 8px; display: flex; flex-wrap: wrap; gap: 8px; }}
                .nav a {{ color: #9fb0c3; text-decoration: none; padding: 8px 12px; border-radius: 4px; transition: background 0.2s; font-size: 13px; white-space: nowrap; }}
                .nav a:hover {{ background: #2a3b57; }}
                .nav a.active {{ background: #2d5aa0; color: #e0e6ed; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 15px; margin: 20px 0; }}
                .stat-card {{ background: #1a1f3a; padding: 15px; border-radius: 8px; border-left: 4px solid #4fc3f7; }}
                .stat-label {{ color: #9fb0c3; font-size: 11px; text-transform: uppercase; margin-bottom: 8px; }}
                .stat-value {{ color: #e0e6ed; font-size: 20px; font-weight: 600; }}
                .controls {{ margin: 20px 0; display: flex; gap: 10px; }}
                button {{ padding: 10px 20px; background: #2d5aa0; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }}
                button:hover {{ background: #3d6ab0; }}
                .delete-btn {{ padding: 6px 12px; background: #f44336; font-size: 12px; }}
                .delete-btn:hover {{ background: #d32f2f; }}
                .table-wrapper {{ overflow-x: auto; margin-top: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); }}
                table {{ width: 100%; min-width: 1000px; border-collapse: collapse; background: #1a1f3a; border-radius: 8px; overflow: hidden; }}
                th {{ background: #2a3b57; padding: 12px 10px; text-align: left; color: #9fb0c3; font-weight: 600; font-size: 11px; text-transform: uppercase; }}
                td {{ padding: 12px 10px; border-top: 1px solid #2a3b57; font-size: 12px; }}
                tr:hover {{ background: #252b42; }}
                .status-active {{ color: #4caf50; font-weight: 600; }}
                .status-triggered {{ color: #9e9e9e; }}
                .alert-type {{ color: #4fc3f7; font-weight: 600; }}
                .price {{ font-family: monospace; font-size: 12px; color: #e0e6ed; }}
                .empty {{ text-align: center; padding: 40px; color: #6b7280; }}
                .cell-text {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 200px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔔 Price Alerts</h1>
                <div class="nav">
                    <a href="/">Home</a>
                    <a href="/auto-execution/view">Auto Execution</a>
                    <a href="/scalps/view">Automated Scalps</a>
                    <a href="/micro-scalp/view">Micro-Scalp Monitor</a>
                    <a href="/alerts/view" class="active">Alerts</a>
                </div>
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-label">Total Alerts</div>
                        <div class="stat-value">{len(all_alerts)}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Active</div>
                        <div class="stat-value">{active_count}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Triggered</div>
                        <div class="stat-value">{triggered_count}</div>
                    </div>
                </div>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Created</th>
                                <th>Symbol</th>
                                <th>Type</th>
                                <th>Target Price</th>
                                <th>Status</th>
                                <th>Message</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>
            </div>
            <script>
                async function deleteAlert(alertId) {{
                    if (!confirm('Delete this alert?')) return;
                    try {{
                        const response = await fetch(`/api/v1/alerts/${{alertId}}`, {{
                            method: 'DELETE'
                        }});
                        if (response.ok) {{
                            location.reload();
                        }} else {{
                            alert('Failed to delete alert');
                        }}
                    }} catch (error) {{
                        alert('Error deleting alert: ' + error);
                    }}
                }}
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Error loading alerts view: {e}", exc_info=True)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Price Alerts - Error</title>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #0a0e27; color: #e0e6ed; }}
                .container {{ max-width: 1400px; margin: 0 auto; }}
                h1 {{ color: #f44336; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⚠️ Error Loading Alerts</h1>
                <p>{str(e)}</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=500)

# ============================================================================
# PHONE CONTROL - Desktop Agent WebSocket & Command Dispatch
# ============================================================================

from fastapi import WebSocket, WebSocketDisconnect
import secrets
import uuid

# Phone control state
class PhoneControlState:
    def __init__(self):
        self.agent_ws: Optional[WebSocket] = None
        # Fixed tokens - these won't change on restart
        # Use API_SECRET to match desktop_agent.py which uses API_SECRET for main API connection
        self.agent_secret: str = os.getenv(
            "API_SECRET",
            "8j5Cg8aAYy8uujCpvOv6KA8pZRm7yqWjhI6m1euVvU4",
        )  # Matches desktop_agent.py API_SECRET default
        self.phone_token: str = os.getenv(
            "PHONE_BEARER_TOKEN",
            "phone_control_bearer_token_2025_v1_secure",
        )  # Used by Custom GPT Actions
        self.pending_commands: Dict[str, asyncio.Future] = {}
        self.command_history: List[Dict] = []
    
    def is_agent_online(self) -> bool:
        return self.agent_ws is not None
    
    def add_command(self, command_id: str) -> asyncio.Future:
        future = asyncio.Future()
        self.pending_commands[command_id] = future
        return future
    
    def complete_command(self, command_id: str, result: Dict[str, Any]):
        if command_id in self.pending_commands:
            self.pending_commands[command_id].set_result(result)
            del self.pending_commands[command_id]
    
    def fail_command(self, command_id: str, error: str):
        if command_id in self.pending_commands:
            try:
                self.pending_commands[command_id].set_exception(Exception(error))
            except Exception as e:
                logger.warning(f"Could not set exception for command {command_id}: {e}")
            finally:
                del self.pending_commands[command_id]
    
    def log_command(self, command_id: str, tool: str, arguments: Dict, result: Dict = None, error: str = None):
        self.command_history.append({
            "command_id": command_id,
            "tool": tool,
            "arguments": arguments,
            "result": result,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        })
        if len(self.command_history) > 100:
            self.command_history.pop(0)

phone_state = PhoneControlState()

logger.info(f"🔐 Phone Control Tokens Generated:")
logger.info(f"   Phone Bearer Token: {phone_state.phone_token}")
logger.info(f"   Agent Secret: {phone_state.agent_secret}")

# Phone control models
class PhoneDispatchRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}
    timeout: int = 120

class PhoneDispatchResponse(BaseModel):
    command_id: str
    status: str
    summary: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float

def verify_phone_token(authorization: str = Header(None)):
    """Verify phone bearer token"""
    logger.info(f"🔐 Phone token verification - Header present: {authorization is not None}")
    if not authorization:
        logger.error("❌ Missing Authorization header")
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    scheme, _, token = authorization.partition(" ")
    logger.info(f"🔐 Auth scheme: {scheme}, Token match: {token == phone_state.phone_token}")
    if scheme.lower() != "bearer" or token != phone_state.phone_token:
        logger.error(f"❌ Invalid bearer token. Expected: {phone_state.phone_token[:20]}..., Got: {token[:20] if token else 'None'}...")
        raise HTTPException(status_code=403, detail="Invalid bearer token")
    
    logger.info("✅ Phone token verified successfully")
    return True

def verify_agent_secret(secret: str):
    """Verify desktop agent secret"""
    if secret != phone_state.agent_secret:
        raise HTTPException(status_code=403, detail="Invalid agent secret")
    return True

@app.post("/dispatch", response_model=PhoneDispatchResponse)
async def dispatch_command(
    request: PhoneDispatchRequest,
    authorized: bool = Depends(verify_phone_token)
):
    """
    Dispatch command from phone to desktop agent
    """
    start_time = datetime.utcnow()
    command_id = str(uuid.uuid4())
    
    logger.info(f"📱 Phone command received: {request.tool}")
    logger.info(f"   Command ID: {command_id}")
    logger.info(f"   Arguments: {json.dumps(request.arguments, indent=2)}")
    logger.info(f"   Timeout: {request.timeout}s")
    logger.info(f"   Agent online: {phone_state.is_agent_online()}")
    
    # Check if agent is connected
    if not phone_state.is_agent_online():
        error_msg = "Desktop agent is offline. Please ensure the agent is running on your computer."
        logger.error(f"❌ {error_msg}")
        phone_state.log_command(command_id, request.tool, request.arguments, error=error_msg)
        
        return PhoneDispatchResponse(
            command_id=command_id,
            status="error",
            summary="❌ Desktop agent offline",
            error=error_msg,
            execution_time=0.0
        )
    
    # Register command and create future for result
    result_future = phone_state.add_command(command_id)
    
    # Send command to agent
    command_payload = {
        "command_id": command_id,
        "tool": request.tool,
        "arguments": request.arguments,
        "timeout": request.timeout
    }
    
    try:
        await phone_state.agent_ws.send_json(command_payload)
        logger.info(f"📤 Forwarded command {command_id} to desktop agent")
        
        # Wait for result with timeout
        try:
            result = await asyncio.wait_for(result_future, timeout=request.timeout)
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(f"✅ Command {command_id} completed in {execution_time:.2f}s")
            
            # Convert numpy types to native Python types for JSON serialization
            result = convert_numpy_types(result)
            
            phone_state.log_command(command_id, request.tool, request.arguments, result=result)
            
            return PhoneDispatchResponse(
                command_id=command_id,
                status="success",
                summary=result.get("summary", "Command completed"),
                data=result.get("data"),
                execution_time=execution_time
            )
            
        except asyncio.TimeoutError:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Command timed out after {request.timeout}s. The agent may still be processing it."
            
            logger.warning(f"⏱️ Command {command_id} timed out")
            phone_state.fail_command(command_id, error_msg)
            phone_state.log_command(command_id, request.tool, request.arguments, error=error_msg)
            
            return PhoneDispatchResponse(
                command_id=command_id,
                status="timeout",
                summary="⏱️ Command timed out",
                error=error_msg,
                execution_time=execution_time
            )
            
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Check if agent disconnected
        if not phone_state.is_agent_online():
            error_msg = "Desktop agent disconnected during command. Please ensure desktop_agent.py is running."
        else:
            error_msg = f"Failed to send command to agent: {str(e)}"
        
        logger.error(f"❌ {error_msg}", exc_info=True)
        phone_state.fail_command(command_id, error_msg)
        phone_state.log_command(command_id, request.tool, request.arguments, error=error_msg)
        
        return PhoneDispatchResponse(
            command_id=command_id,
            status="error",
            summary="❌ Command failed",
            error=error_msg,
            execution_time=execution_time
        )

@app.websocket("/agent/connect")
async def agent_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for desktop agent connection
    """
    await websocket.accept()
    
    try:
        # First message must be authentication
        auth_msg = await websocket.receive_json()
        
        # Verify authentication (don't use verify_agent_secret as it raises HTTPException)
        if auth_msg.get("type") != "auth" or auth_msg.get("secret") != phone_state.agent_secret:
            logger.error(f"❌ Agent authentication failed. Expected secret: {phone_state.agent_secret[:10]}..., Got: {auth_msg.get('secret', 'None')[:10] if auth_msg.get('secret') else 'None'}...")
            await websocket.send_json({"error": "Authentication failed"})
            await websocket.close()
            return
        
        # Register agent
        phone_state.agent_ws = websocket
        logger.info("✅ Desktop agent connected via WebSocket")
        
        await websocket.send_json({
            "type": "auth_success",
            "message": "Authentication successful"
        })
        
        # Handle messages from agent
        while True:
            try:
                message = await websocket.receive_json()
                message_type = message.get("type")
                
                if message_type == "result":
                    # Command result from agent
                    command_id = message.get("command_id")
                    result = message.get("result")
                    
                    logger.info(f"📥 Received result for command {command_id}")
                    phone_state.complete_command(command_id, result)
                
                elif message_type == "error":
                    # Command error from agent
                    command_id = message.get("command_id")
                    error = message.get("error")
                    
                    logger.error(f"❌ Agent reported error for {command_id}: {error}")
                    phone_state.fail_command(command_id, error)
                
                elif message_type == "heartbeat":
                    # Agent heartbeat
                    await websocket.send_json({"type": "heartbeat_ack"})
                
                else:
                    logger.warning(f"Unknown message type from agent: {message_type}")
            
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling agent message: {e}")
                break
    
    except Exception as e:
        logger.error(f"Agent WebSocket error: {e}")
    
    finally:
        # Unregister agent
        if phone_state.agent_ws == websocket:
            phone_state.agent_ws = None
            logger.warning("❌ Desktop agent disconnected")
            
            # Fail all pending commands
            for command_id in list(phone_state.pending_commands.keys()):
                phone_state.fail_command(command_id, "Agent disconnected")

@app.get("/phone/health")
async def phone_health():
    """Check phone control system health"""
    return {
        "hub": "healthy",
        "agent_status": "online" if phone_state.is_agent_online() else "offline",
        "pending_commands": len(phone_state.pending_commands),
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================================
# AUTOMATED SCALPS VIEW PAGE
# ============================================================================

@app.get("/scalps/view", response_class=HTMLResponse)
async def view_automated_scalps():
    """Display automated scalp trades (Liquidity Sweep Reversal Engine and other automated systems)"""
    try:
        if not journal_repo:
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Automated Scalps - Synergis Trading</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #0a0e27; color: #e0e6ed; }
                    .container { max-width: 1400px; margin: 0 auto; }
                    h1 { color: #4fc3f7; margin-bottom: 10px; }
                    .nav { margin-bottom: 20px; padding: 15px; background: #1a1f3a; border-radius: 8px; }
                    .nav a { color: #9fb0c3; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px; transition: background 0.2s; }
                    .nav a:hover { background: #2a3b57; }
                    .controls { margin: 20px 0; display: flex; gap: 10px; }
                    button { padding: 10px 20px; background: #2d5aa0; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
                    button:hover { background: #3d6ab0; }
                    table { width: 100%; border-collapse: collapse; margin-top: 20px; background: #1a1f3a; border-radius: 8px; overflow: hidden; }
                    th { background: #2a3b57; padding: 12px; text-align: left; color: #9fb0c3; font-weight: 600; font-size: 13px; text-transform: uppercase; }
                    td { padding: 12px; border-top: 1px solid #2a3b57; }
                    tr:hover { background: #252b42; }
                    .profit { color: #4caf50; }
                    .loss { color: #f44336; }
                    .status-open { color: #ff9800; }
                    .status-closed { color: #9e9e9e; }
                    .empty { text-align: center; padding: 40px; color: #6b7280; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>⚠️ Journal Repository Not Initialized</h1>
                    <p>Please restart the server to initialize the journal repository.</p>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)
        
        # Get all trade execution events
        all_events = journal_repo.recent(limit=500)
        
        # Filter for automated scalps (LSR trades, micro-scalp, and other automated systems)
        automated_scalps = []
        for event in all_events:
            # The recent() method returns events with these fields:
            # ts, symbol, side, entry, sl, tp, lot, ticket, position, balance, equity, confidence, regime, rr, notes
            notes = event.get('notes', '') or ''
            reason = event.get('reason', '') or ''
            
            # Combine notes and reason for checking
            combined_text = f"{notes} {reason}".lower()
            regime = (event.get('regime') or '').lower()
            
            # Check for automated trade markers (more inclusive)
            is_automated = (
                'lsr' in combined_text or 
                'liquidity sweep' in combined_text or 
                'liquiditysweep' in combined_text or
                'microscalp' in combined_text or
                'micro-scalp' in combined_text or
                'micro_scalp' in combined_text or
                'microscalp' in combined_text or
                'automated' in combined_text or 
                'auto' in combined_text or
                regime == 'lsr' or
                'liquidity' in combined_text or
                'sweep' in combined_text or
                # Also include trades with specific comment patterns
                'reversal' in combined_text or
                'reversal' in combined_text
            )
            
            if is_automated:
                automated_scalps.append({
                    'timestamp': event.get('ts', ''),
                    'ticket': event.get('ticket', 0),
                    'symbol': event.get('symbol', ''),
                    'side': event.get('side', ''),
                    'entry': event.get('entry', 0),  # Note: field is 'entry' not 'price'
                    'sl': event.get('sl'),
                    'tp': event.get('tp'),
                    'volume': event.get('lot', 0),  # Note: field is 'lot' not 'volume'
                    'pnl': event.get('pnl'),
                    'r_multiple': event.get('rr', event.get('r_multiple')),  # Note: field is 'rr' not 'r_multiple'
                    'reason': reason,
                    'notes': notes,
                    'regime': event.get('regime'),
                    'rr': event.get('rr')
                })
        
        # Sort by timestamp (newest first)
        automated_scalps.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Build HTML table rows
        table_rows = ""
        if automated_scalps:
            for scalp in automated_scalps[:100]:  # Limit to 100 most recent
                timestamp = scalp.get('timestamp', '')
                ticket = scalp.get('ticket', '')
                symbol = scalp.get('symbol', '')
                side = scalp.get('side', '')
                entry = scalp.get('entry', 0)
                sl = scalp.get('sl')
                tp = scalp.get('tp')
                volume = scalp.get('volume', 0)
                pnl = scalp.get('pnl')
                r_multiple = scalp.get('r_multiple')
                notes = scalp.get('notes', '')
                
                # Determine if trade is open or closed
                is_open = pnl is None
                pnl_class = ""
                pnl_display = ""
                if pnl is not None:
                    pnl_display = f"${pnl:.2f}" if pnl != 0 else "$0.00"
                    pnl_class = "profit" if pnl > 0 else "loss" if pnl < 0 else ""
                
                status_class = "status-open" if is_open else "status-closed"
                status_text = "OPEN" if is_open else "CLOSED"
                
                # Extract system type from notes
                system_type = "Unknown"
                if "LSR_" in notes:
                    if "Type 1" in notes:
                        system_type = "LSR Type 1"
                    elif "Type 2" in notes:
                        system_type = "LSR Type 2"
                    else:
                        system_type = "LSR"
                elif "auto" in notes.lower():
                    system_type = "Auto Execution"
                
                # Format timestamp
                timestamp_display = timestamp[:19].replace('T', ' ') if timestamp else 'N/A'
                
                table_rows += f"""
                <tr>
                    <td>{timestamp_display}</td>
                    <td>{ticket}</td>
                    <td>{symbol}</td>
                    <td>{side}</td>
                    <td>{entry:.5f if entry else 'N/A'}</td>
                    <td>{sl:.5f if sl else 'N/A'}</td>
                    <td>{tp:.5f if tp else 'N/A'}</td>
                    <td>{volume:.2f if volume else 'N/A'}</td>
                    <td class="{pnl_class}">{pnl_display if pnl_display else 'N/A'}</td>
                    <td>{r_multiple:.2f if r_multiple else 'N/A'}</td>
                    <td><span class="{status_class}">{status_text}</span></td>
                    <td>{system_type}</td>
                    <td title="{notes}">{notes[:50] + '...' if notes and len(notes) > 50 else notes or 'N/A'}</td>
                </tr>
                """
        else:
            if all_events:
                # There are events but none matched the filter
                table_rows = f'<tr><td colspan="13" class="empty">No automated scalps found (checked {len(all_events)} recent trades). Try checking notes/reason fields for automated markers.</td></tr>'
            else:
                # No events at all
                table_rows = '<tr><td colspan="13" class="empty">No trade events found in journal. Trades will appear here once executed.</td></tr>'
        
        # Calculate statistics
        closed_scalps = [s for s in automated_scalps if s.get('pnl') is not None]
        total_pnl = sum(s.get('pnl', 0) for s in closed_scalps)
        winning = len([s for s in closed_scalps if s.get('pnl', 0) > 0])
        losing = len([s for s in closed_scalps if s.get('pnl', 0) < 0])
        win_rate = (winning / len(closed_scalps) * 100) if closed_scalps else 0
        
        # Get micro scalp monitor status
        monitor_status = None
        monitor_checks = []
        try:
            # NOTE: Micro-Scalp Monitor data is available on root main_api.py (port 8010)
            # Skip micro-scalp data in this dashboard
            monitor_status = None
            history = {}
            # monitor_checks will remain empty since micro-scalp is on port 8010
            if False:  # Disabled - micro-scalp runs on port 8010
                for symbol, symbol_data in history.items():
                    for check in symbol_data.get('checks', [])[:10]:  # Last 10 per symbol
                        monitor_checks.append({
                            'symbol': symbol,
                            'timestamp': check.get('timestamp', ''),
                            'passed': check.get('passed', False),
                            'condition_details': check.get('condition_details', {}),
                            'failure_reasons': check.get('failure_reasons', []),
                            'block_reason': check.get('block_reason', ''),
                            'session': check.get('session_check', ''),
                            'news_blackout': check.get('news_blackout', False)
                        })
                # Sort by timestamp (newest first)
                monitor_checks.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        except Exception as e:
            logger.debug(f"Could not get micro scalp monitor status: {e}")
        
        # Build monitoring section HTML
        def build_monitoring_html(status, checks):
            if not status:
                return """
                <div class="section">
                    <h2>🔍 Monitoring Status</h2>
                    <div class="monitor-card">
                        <p style="color: #9fb0c3;">Micro-Scalp Monitor not initialized</p>
                    </div>
                </div>
                """
            
            stats = status.get('stats', {})
            skipped = stats.get('skipped', {})
            
            # Build indicators section
            indicators_html = f"""
            <div class="indicator-grid">
                <div class="indicator-item">
                    <div class="indicator-label">RSI (14)</div>
                    <div class="indicator-value">Momentum Analysis</div>
                </div>
                <div class="indicator-item">
                    <div class="indicator-label">VWAP</div>
                    <div class="indicator-value">Price Proximity & Slope</div>
                </div>
                <div class="indicator-item">
                    <div class="indicator-label">ATR(1)</div>
                    <div class="indicator-value">Volatility Filter</div>
                </div>
                <div class="indicator-item">
                    <div class="indicator-label">M1 Structure</div>
                    <div class="indicator-value">CHOCH/BOS Detection</div>
                </div>
                <div class="indicator-item">
                    <div class="indicator-label">Order Blocks</div>
                    <div class="indicator-value">Micro OB Retest</div>
                </div>
                <div class="indicator-item">
                    <div class="indicator-label">Liquidity Sweeps</div>
                    <div class="indicator-value">Micro Sweep Detection</div>
                </div>
                <div class="indicator-item">
                    <div class="indicator-label">Spread Tracker</div>
                    <div class="indicator-value">Spread Ratio Analysis</div>
                </div>
                <div class="indicator-item">
                    <div class="indicator-label">Session Filter</div>
                    <div class="indicator-value">{status.get('current_session', 'Unknown')}</div>
                </div>
            </div>
            """
            
            # Build conditions being checked
            conditions_html = """
            <div style="margin-top: 15px;">
                <h4 style="color: #4fc3f7; margin-bottom: 10px; font-size: 14px;">Conditions Being Checked:</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; font-size: 12px;">
                    <div><strong>Pre-Trade Filters:</strong> ATR(1), M1 Range, Spread</div>
                    <div><strong>Location Filter:</strong> VWAP Band, Session High/Low, OB Zone, Liquidity Cluster</div>
                    <div><strong>Primary Triggers:</strong> Long Wick Trap, Liquidity Sweep, VWAP Tap Rejection, Engulfing</div>
                    <div><strong>Secondary Confluence:</strong> OB Retest, Micro-CHOCH, Session Momentum, Volume</div>
                    <div><strong>Confluence Score:</strong> Wick Quality, VWAP Proximity, Edge Location, Volatility, Session</div>
                </div>
            </div>
            """
            
            # Build recent checks
            checks_html = ""
            if checks:
                checks_html = '<h4 style="color: #4fc3f7; margin-top: 20px; margin-bottom: 10px; font-size: 14px;">Recent Condition Checks:</h4>'
                for check in checks[:10]:  # Show last 10 checks
                    status_val = 'passed' if check.get('passed') else 'failed'
                    status_class = 'status-passed' if check.get('passed') else 'status-failed'
                    status_text = 'PASSED' if check.get('passed') else 'FAILED'
                    
                    timestamp = check.get('timestamp', '')
                    time_display = timestamp[:19].replace('T', ' ') if timestamp else 'N/A'
                    
                    condition_details = check.get('condition_details', {})
                    failure_reasons = check.get('failure_reasons', [])
                    block_reason = check.get('block_reason', '')
                    
                    details_html = ""
                    if condition_details:
                        details_html = f"""
                        <div class="condition-details">
                            <div class="detail-grid">
                                <div class="detail-item">
                                    <span class="detail-label">Pre-Trade:</span>
                                    <span class="detail-value {'status-passed' if condition_details.get('pre_trade_passed') else 'status-failed'}">
                                        {'✓' if condition_details.get('pre_trade_passed') else '✗'}
                                    </span>
                                </div>
                                <div class="detail-item">
                                    <span class="detail-label">Location:</span>
                                    <span class="detail-value {'status-passed' if condition_details.get('location_passed') else 'status-failed'}">
                                        {'✓' if condition_details.get('location_passed') else '✗'}
                                    </span>
                                </div>
                                <div class="detail-item">
                                    <span class="detail-label">Primary Triggers:</span>
                                    <span class="detail-value">{condition_details.get('primary_triggers', 0)}</span>
                                </div>
                                <div class="detail-item">
                                    <span class="detail-label">Secondary:</span>
                                    <span class="detail-value">{condition_details.get('secondary_confluence', 0)}</span>
                                </div>
                                <div class="detail-item">
                                    <span class="detail-label">Confluence Score:</span>
                                    <span class="detail-value">{condition_details.get('confluence_score', 0):.1f}</span>
                                </div>
                                <div class="detail-item">
                                    <span class="detail-label">A+ Setup:</span>
                                    <span class="detail-value {'status-passed' if condition_details.get('is_aplus_setup') else ''}">
                                        {'✓' if condition_details.get('is_aplus_setup') else '✗'}
                                    </span>
                                </div>
                            </div>
                        </div>
                        """
                    
                    reasons_html = ""
                    if failure_reasons:
                        reasons_html = f"""
                        <div class="reasons">
                            <strong>Failure Reasons:</strong>
                            <ul>
                                {''.join([f'<li>{reason}</li>' for reason in failure_reasons])}
                            </ul>
                        </div>
                        """
                    elif block_reason:
                        reasons_html = f"""
                        <div class="reasons">
                            <strong>Blocked:</strong> {block_reason}
                        </div>
                        """
                    
                    checks_html += f"""
                    <div class="condition-item {status_val}">
                        <div class="condition-header">
                            <div>
                                <strong>{check.get('symbol', 'N/A')}</strong> - {time_display}
                                {f'<span style="color: #9fb0c3; margin-left: 10px;">Session: {check.get("session", "N/A")}</span>' if check.get('session') else ''}
                                {f'<span style="color: #ff9800; margin-left: 10px;">News Blackout: Yes</span>' if check.get('news_blackout') else ''}
                            </div>
                            <span class="condition-status {status_class}">{status_text}</span>
                        </div>
                        {details_html}
                        {reasons_html}
                    </div>
                    """
            else:
                checks_html = '<p style="color: #9fb0c3; margin-top: 15px;">No recent checks available</p>'
            
            return f"""
            <div class="section">
                <h2>🔍 Monitoring Status</h2>
                <div class="monitor-card">
                    <h3>📊 Monitor Statistics</h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px;">
                        <div>
                            <div class="indicator-label">Total Checks</div>
                            <div class="indicator-value">{stats.get('total_checks', 0)}</div>
                        </div>
                        <div>
                            <div class="indicator-label">Conditions Met</div>
                            <div class="indicator-value">{stats.get('conditions_met', 0)}</div>
                        </div>
                        <div>
                            <div class="indicator-label">Executions</div>
                            <div class="indicator-value">{stats.get('executions', 0)}</div>
                        </div>
                        <div>
                            <div class="indicator-label">Skipped (Session)</div>
                            <div class="indicator-value">{skipped.get('session', 0)}</div>
                        </div>
                        <div>
                            <div class="indicator-label">Skipped (News)</div>
                            <div class="indicator-value">{skipped.get('news', 0)}</div>
                        </div>
                        <div>
                            <div class="indicator-label">Current Session</div>
                            <div class="indicator-value">{status.get('current_session', 'Unknown')}</div>
                        </div>
                    </div>
                    
                    <h3 style="margin-top: 20px;">📈 Indicators Being Monitored</h3>
                    {indicators_html}
                    
                    {conditions_html}
                    
                    {checks_html}
                </div>
            </div>
            """
        
        monitoring_html = build_monitoring_html(monitor_status, monitor_checks)
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Automated Scalps - Synergis Trading</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #0a0e27; color: #e0e6ed; }}
                .container {{ max-width: 1600px; margin: 0 auto; }}
                h1 {{ color: #4fc3f7; margin-bottom: 10px; }}
                .nav {{ margin-bottom: 20px; padding: 15px; background: #1a1f3a; border-radius: 8px; }}
                .nav a {{ color: #9fb0c3; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px; transition: background 0.2s; }}
                .nav a:hover {{ background: #2a3b57; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
                .stat-card {{ background: #1a1f3a; padding: 20px; border-radius: 8px; border-left: 4px solid #4fc3f7; }}
                .stat-label {{ color: #9fb0c3; font-size: 12px; text-transform: uppercase; margin-bottom: 8px; }}
                .stat-value {{ color: #e0e6ed; font-size: 24px; font-weight: 600; }}
                .stat-value.profit {{ color: #4caf50; }}
                .stat-value.loss {{ color: #f44336; }}
                .controls {{ margin: 20px 0; display: flex; gap: 10px; }}
                button {{ padding: 10px 20px; background: #2d5aa0; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }}
                button:hover {{ background: #3d6ab0; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background: #1a1f3a; border-radius: 8px; overflow: hidden; }}
                th {{ background: #2a3b57; padding: 12px; text-align: left; color: #9fb0c3; font-weight: 600; font-size: 13px; text-transform: uppercase; position: sticky; top: 0; }}
                td {{ padding: 12px; border-top: 1px solid #2a3b57; font-size: 13px; }}
                tr:hover {{ background: #252b42; }}
                .profit {{ color: #4caf50; }}
                .loss {{ color: #f44336; }}
                .status-open {{ color: #ff9800; font-weight: 600; }}
                .status-closed {{ color: #9e9e9e; }}
                .empty {{ text-align: center; padding: 40px; color: #6b7280; }}
                .section {{ margin-bottom: 40px; }}
                .section h2 {{ color: #4fc3f7; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #2a3b57; font-size: 18px; }}
                .monitor-card {{ background: #1a1f3a; border-radius: 8px; padding: 20px; margin-bottom: 20px; border-left: 4px solid #4fc3f7; }}
                .monitor-card h3 {{ color: #4fc3f7; margin-bottom: 15px; font-size: 16px; }}
                .indicator-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin-top: 15px; }}
                .indicator-item {{ background: #0a0e27; padding: 12px; border-radius: 6px; border: 1px solid #2a3b57; }}
                .indicator-label {{ color: #9fb0c3; font-size: 11px; text-transform: uppercase; margin-bottom: 5px; }}
                .indicator-value {{ color: #e0e6ed; font-size: 14px; font-weight: 600; }}
                .condition-item {{ background: #1a1f3a; border-radius: 6px; padding: 15px; margin-bottom: 15px; border-left: 4px solid #2a3b57; }}
                .condition-item.passed {{ border-left-color: #4caf50; }}
                .condition-item.failed {{ border-left-color: #f44336; }}
                .condition-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
                .condition-time {{ color: #9fb0c3; font-size: 12px; }}
                .condition-status {{ padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; }}
                .status-passed {{ background: rgba(76, 175, 80, 0.2); color: #4caf50; }}
                .status-failed {{ background: rgba(244, 67, 54, 0.2); color: #f44336; }}
                .condition-details {{ margin-top: 10px; padding: 10px; background: #0a0e27; border-radius: 4px; border: 1px solid #2a3b57; }}
                .detail-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; font-size: 12px; }}
                .detail-item {{ display: flex; justify-content: space-between; }}
                .detail-label {{ color: #9fb0c3; }}
                .detail-value {{ color: #e0e6ed; font-weight: 600; }}
                .reasons {{ margin-top: 10px; padding: 10px; background: #0a0e27; border-radius: 4px; border: 1px solid #2a3b57; }}
                .reasons ul {{ margin-left: 20px; color: #9fb0c3; font-size: 12px; }}
                .reasons li {{ margin: 5px 0; }}
                .expandable {{ cursor: pointer; }}
                .expandable:hover {{ background: #252b42; }}
                .expanded-content {{ display: none; margin-top: 10px; padding-top: 10px; border-top: 1px solid #2a3b57; }}
                .expanded-content.show {{ display: block; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 Automated Scalps</h1>
                <div class="nav">
                    <a href="/">Home</a>
                    <a href="/auto-execution/view">Auto Execution</a>
                    <a href="/scalps/view" class="active">Automated Scalps</a>
                    <a href="/micro-scalp/view">Micro-Scalp Monitor</a>
                    <a href="/alerts/view">Alerts</a>
                </div>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-label">Total Scalps</div>
                        <div class="stat-value">{len(automated_scalps)}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Closed Trades</div>
                        <div class="stat-value">{len(closed_scalps)}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Win Rate</div>
                        <div class="stat-value">{win_rate:.1f}%</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Total P&L</div>
                        <div class="stat-value {'profit' if total_pnl > 0 else 'loss' if total_pnl < 0 else ''}">${total_pnl:.2f}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Winning</div>
                        <div class="stat-value profit">{winning}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Losing</div>
                        <div class="stat-value loss">{losing}</div>
                    </div>
                </div>
                
                <div class="controls">
                    <button onclick="location.reload()">🔄 Refresh</button>
                </div>
                
                {monitoring_html}
                
                <div class="section">
                    <h2>📊 Trade History</h2>
                    <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Ticket</th>
                            <th>Symbol</th>
                            <th>Side</th>
                            <th>Entry</th>
                            <th>SL</th>
                            <th>TP</th>
                            <th>Volume</th>
                            <th>P&L</th>
                            <th>R Multiple</th>
                            <th>Status</th>
                            <th>System</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
            
            <script>
                // Auto-refresh every 30 seconds
                setTimeout(() => location.reload(), 30000);
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"Error loading automated scalps: {e}", exc_info=True)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error - Automated Scalps</title>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; background: #0a0e27; color: #e0e6ed; }}
                .error {{ color: #f44336; padding: 20px; background: #1a1f3a; border-radius: 8px; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h2>Error Loading Automated Scalps</h2>
                <p>{str(e)}</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=500)

# ============================================================================
# AUTO EXECUTION VIEW PAGE
# ============================================================================

@app.get("/auto-execution/view", response_class=HTMLResponse)
async def view_auto_execution_plans(status_filter: str = "pending"):
    """Display auto-execution trade plans with TradingView tickers
    
    Args:
        status_filter: Filter by status - 'all', 'pending', 'executed', 'cancelled', 'expired'
    """
    logger.info(f"📥 AUTO-EXECUTION VIEW: status_filter='{status_filter}'")
    try:
        from chatgpt_auto_execution_integration import get_chatgpt_auto_execution
        
        auto_execution = get_chatgpt_auto_execution()
        logger.info(f"✅ Got auto_execution instance")
        # Get all plans - ChatGPTAutoExecution has get_plan_status() wrapper
        status_result = auto_execution.get_plan_status(include_all_statuses=True)
        logger.info(f"✅ Got status_result: success={status_result.get('success')}, plans_count={len(status_result.get('plans', []))}")
        
        plans = []
        if status_result.get("success") and "plans" in status_result:
            all_plans = status_result["plans"]
            # Filter by status if not 'all'
            if status_filter.lower() == "all":
                plans = all_plans
            elif status_filter.lower() == "executed":
                # Include both "executed" and "closed" statuses when filtering for executed
                plans = [plan for plan in all_plans if plan.get("status", "").lower() in ["executed", "closed"]]
            elif status_filter.lower() == "pending":
                # Filter pending plans, but exclude expired ones
                now_utc = datetime.now(timezone.utc)
                plans = []
                for plan in all_plans:
                    plan_status = plan.get("status", "").lower()
                    if plan_status == "pending":
                        # Check if plan has expired
                        expires_at_str = plan.get("expires_at")
                        if expires_at_str:
                            try:
                                expires_at_dt = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                                if expires_at_dt.tzinfo is None:
                                    expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
                                if expires_at_dt < now_utc:
                                    # Plan has expired, skip it
                                    continue
                            except Exception as e:
                                logger.warning(f"Error parsing expires_at for plan {plan.get('plan_id')}: {e}")
                        plans.append(plan)
            else:
                plans = [plan for plan in all_plans if plan.get("status", "").lower() == status_filter.lower()]
        
        # Sort plans by created_at (newest first)
        plans.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        # Query MT5 for profit/loss data (only for executed plans)
        trade_results = {}
        summary_stats = {
            'total_pnl': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'avg_pnl': 0
        }
        
        # Query MT5 for profit/loss data for executed or closed plans
        if status_filter.lower() in ["executed", "closed"]:
            logger.info(f"🔍 Querying MT5 for {len(plans)} plans with status '{status_filter}'")
            # Reuse existing PlanEffectivenessTracker infrastructure
            tracker = PlanEffectivenessTracker()
            
            plans_with_tickets = [p for p in plans if p.get("ticket")]
            logger.info(f"📊 Found {len(plans_with_tickets)} plans with tickets (out of {len(plans)} total)")
            
            if len(plans_with_tickets) == 0:
                logger.warning(f"⚠️ No plans with tickets found! Cannot query MT5.")
            
            for plan in plans:
                ticket = plan.get("ticket")
                plan_id = plan.get("plan_id", "unknown")
                if not ticket:
                    logger.debug(f"⏭️ Skipping plan {plan_id} - no ticket")
                    continue
                
                logger.debug(f"🔍 Processing ticket {ticket} for plan {plan_id}")
                
                # Check database first (if Phase 2 implemented)
                # Note: plan.get("profit_loss") returns None if field doesn't exist (before migration)
                # This is safe - Phase 1 works without Phase 2 migration
                profit_loss = plan.get("profit_loss")
                if profit_loss is not None:
                    logger.debug(f"✅ Plan {plan_id} has profit_loss in DB: ${profit_loss:.2f}")
                    # Use database data (faster and more reliable)
                    trade_results[ticket] = {
                        'status': 'closed',
                        'profit': profit_loss,
                        'exit_price': plan.get('exit_price'),
                        'close_time': plan.get('close_time')
                    }
                else:
                    logger.info(f"🔍 Plan {plan_id} has no profit_loss in DB, querying MT5 for ticket {ticket}...")
                    # Fallback to MT5 query with caching (async)
                    try:
                        outcome = await get_cached_outcome(tracker, ticket, plan.get("executed_at"))
                        logger.info(f"📊 MT5 query completed for ticket {ticket}: outcome={'found' if outcome else 'None'}")
                        if outcome:
                            logger.info(f"✅ MT5 query successful for ticket {ticket} (plan {plan_id}): status={outcome.get('status')}, profit=${outcome.get('profit', 0):.2f}")
                            trade_results[ticket] = {
                                'status': outcome.get('status'),
                                'profit': outcome.get('profit', 0),
                                'exit_price': outcome.get('exit_price'),
                                'close_time': outcome.get('close_time')
                            }
                            # Format close_time: _get_mt5_trade_outcome returns datetime object
                            if trade_results[ticket]['close_time']:
                                if isinstance(trade_results[ticket]['close_time'], datetime):
                                    trade_results[ticket]['close_time'] = trade_results[ticket]['close_time'].isoformat()
                                elif isinstance(trade_results[ticket]['close_time'], (int, float)):
                                    trade_results[ticket]['close_time'] = datetime.fromtimestamp(trade_results[ticket]['close_time']).isoformat()
                            
                            # If trade is closed, update database immediately (don't wait for background task)
                            if outcome.get('status') == 'closed':
                                try:
                                    from infra.auto_execution_outcome_tracker import AutoExecutionOutcomeTracker
                                    
                                    # Get auto_execution system from the existing instance
                                    outcome_tracker = AutoExecutionOutcomeTracker(auto_execution)
                                    outcome_tracker._update_plan_with_outcome(plan.get("plan_id"), outcome, update_status=True)
                                    logger.info(f"✅ Updated plan {plan.get('plan_id')} with profit/loss: ${outcome.get('profit', 0):.2f}")
                                except Exception as e:
                                    logger.warning(f"Failed to update plan {plan.get('plan_id')} from web query: {e}")
                        else:
                            # No outcome found - trade might not exist in MT5 history or might be too old
                            logger.warning(f"⚠️ No MT5 outcome found for ticket {ticket} (plan {plan.get('plan_id')}, symbol {plan.get('symbol')})")
                            # Still show N/A in UI
                    except Exception as e:
                        logger.error(f"❌ Error querying MT5 for ticket {ticket} (plan {plan.get('plan_id')}): {e}", exc_info=True)
                        # Continue to next plan
            
            # Log summary of trade_results
            logger.info(f"📊 Trade results summary: {len(trade_results)} trades with data")
            for ticket, result in list(trade_results.items())[:5]:  # Log first 5
                logger.info(f"   Ticket {ticket}: status={result.get('status')}, profit=${result.get('profit', 0):.2f}")
            
            # Calculate summary statistics
            closed_trades = [r for r in trade_results.values() if r.get('status') == 'closed']
            if closed_trades:
                summary_stats['total_pnl'] = sum(r.get('profit', 0) for r in closed_trades)
                summary_stats['wins'] = sum(1 for r in closed_trades if r.get('profit', 0) > 0)
                summary_stats['losses'] = sum(1 for r in closed_trades if r.get('profit', 0) < 0)
                total_closed = summary_stats['wins'] + summary_stats['losses']
                if total_closed > 0:
                    summary_stats['win_rate'] = (summary_stats['wins'] / total_closed) * 100
                    summary_stats['avg_pnl'] = summary_stats['total_pnl'] / total_closed
        
        # Build table rows
        table_rows = ""
        if not plans:
            # Update colspan to 16 (was 13, now 3 new columns: profit/loss, exit price, close time)
            table_rows = '<tr><td colspan="16" class="empty">No auto-execution plans found</td></tr>'
        else:
            for plan in plans:
                plan_id = plan.get("plan_id", "N/A")
                symbol = plan.get("symbol", "N/A")
                direction = plan.get("direction") or plan.get("direction", None)
                entry_price = plan.get("entry_price", 0)
                stop_loss = plan.get("stop_loss", 0)
                take_profit = plan.get("take_profit", 0)
                
                # If direction is missing/None, infer from SL/TP relationship
                if not direction or direction == "N/A":
                    if entry_price and stop_loss and take_profit:
                        if stop_loss < entry_price and take_profit > entry_price:
                            direction = "BUY"
                        elif stop_loss > entry_price and take_profit < entry_price:
                            direction = "SELL"
                        else:
                            direction = "N/A"
                    else:
                        direction = "N/A"
                volume = plan.get("volume", 0)
                status = plan.get("status", "unknown")
                created_at = plan.get("created_at", "N/A")
                expires_at = plan.get("expires_at", "N/A")
                notes = plan.get("notes", "")
                conditions = plan.get("conditions", {})
                
                # Format conditions for display with color formatting (matching port 8010)
                conditions_display = ""
                if conditions:
                    parts = []
                    # Price conditions (most important - show first)
                    if conditions.get("price_above"):
                        parts.append(f'<span class="conditions-key">price_above</span>: <span class="conditions-value">{conditions["price_above"]}</span>')
                    if conditions.get("price_below"):
                        parts.append(f'<span class="conditions-key">price_below</span>: <span class="conditions-value">{conditions["price_below"]}</span>')
                    if conditions.get("price_near"):
                        tolerance = conditions.get("tolerance", 0.001)
                        parts.append(f'<span class="conditions-key">price_near</span>: <span class="conditions-value">{conditions["price_near"]}</span> ±{tolerance}')
                    if conditions.get("choch_bull"):
                        parts.append(f'<span class="conditions-key">choch_bull</span>: <span class="conditions-value">true</span>')
                    if conditions.get("choch_bear"):
                        parts.append(f'<span class="conditions-key">choch_bear</span>: <span class="conditions-value">true</span>')
                    if conditions.get("bos_bull"):
                        parts.append(f'<span class="conditions-key">bos_bull</span>: <span class="conditions-value">true</span>')
                    if conditions.get("bos_bear"):
                        parts.append(f'<span class="conditions-key">bos_bear</span>: <span class="conditions-value">true</span>')
                    if conditions.get("order_block"):
                        ob_type = conditions.get("order_block_type", "auto")
                        parts.append(f'<span class="conditions-key">order_block</span>: <span class="conditions-value">true</span> ({ob_type})')
                    if conditions.get("rejection_wick"):
                        ratio = conditions.get("min_wick_ratio", 2.0)
                        parts.append(f'<span class="conditions-key">rejection_wick</span>: <span class="conditions-value">true</span> (ratio≥{ratio})')
                    if conditions.get("liquidity_sweep"):
                        parts.append(f'<span class="conditions-key">liquidity_sweep</span>: <span class="conditions-value">true</span>')
                    if conditions.get("vwap_deviation"):
                        vwap_dir = conditions.get("vwap_deviation_direction", "N/A")
                        parts.append(f'<span class="conditions-key">vwap_deviation</span>: <span class="conditions-value">true</span> ({vwap_dir})')
                    if conditions.get("bb_expansion"):
                        parts.append(f'<span class="conditions-key">bb_expansion</span>: <span class="conditions-value">true</span>')
                    if conditions.get("bb_squeeze"):
                        parts.append(f'<span class="conditions-key">bb_squeeze</span>: <span class="conditions-value">true</span>')
                    if conditions.get("bb_expansion_threshold"):
                        parts.append(f'<span class="conditions-key">bb_expansion_threshold</span>: <span class="conditions-value">>{conditions["bb_expansion_threshold"]}</span>')
                    if conditions.get("bb_expansion_check_both"):
                        parts.append(f'<span class="conditions-key">bb_expansion_check_both</span>: <span class="conditions-value">true</span>')
                    if conditions.get("range_scalp_confluence") is not None:
                        parts.append(f'<span class="conditions-key">range_scalp_confluence</span>: <span class="conditions-value">>={conditions["range_scalp_confluence"]}</span>')
                    if conditions.get("min_confluence") is not None and "range_scalp_confluence" not in conditions:
                        parts.append(f'<span class="conditions-key">min_confluence</span>: <span class="conditions-value">>={conditions["min_confluence"]}</span>')
                    if conditions.get("structure_confirmation"):
                        parts.append(f'<span class="conditions-key">structure_confirmation</span>: <span class="conditions-value">true</span>')
                    if conditions.get("structure_timeframe"):
                        parts.append(f'<span class="conditions-key">structure_timeframe</span>: <span class="conditions-value">{conditions["structure_timeframe"]}</span>')
                    if conditions.get("inside_bar"):
                        parts.append(f'<span class="conditions-key">inside_bar</span>: <span class="conditions-value">true</span>')
                    if conditions.get("equal_highs"):
                        parts.append(f'<span class="conditions-key">equal_highs</span>: <span class="conditions-value">true</span>')
                    if conditions.get("equal_lows"):
                        parts.append(f'<span class="conditions-key">equal_lows</span>: <span class="conditions-value">true</span>')
                    if conditions.get("rsi_div_bull"):
                        parts.append(f'<span class="conditions-key">rsi_div_bull</span>: <span class="conditions-value">true</span>')
                    if conditions.get("rsi_div_bear"):
                        parts.append(f'<span class="conditions-key">rsi_div_bear</span>: <span class="conditions-value">true</span>')
                    if conditions.get("timeframe"):
                        parts.append(f'<span class="conditions-key">timeframe</span>: <span class="conditions-value">{conditions["timeframe"]}</span>')
                    elif conditions.get("structure_timeframe"):
                        parts.append(f'<span class="conditions-key">timeframe</span>: <span class="conditions-value">{conditions["structure_timeframe"]}</span>')
                    if conditions.get("plan_type"):
                        parts.append(f'<span class="conditions-key">plan_type</span>: <span class="conditions-value">{conditions["plan_type"]}</span>')
                    if conditions.get("strategy_type"):
                        parts.append(f'<span class="conditions-key">strategy_type</span>: <span class="conditions-value">{conditions["strategy_type"]}</span>')
                    if conditions.get("min_validation_score") is not None:
                        parts.append(f'<span class="conditions-key">min_validation_score</span>: <span class="conditions-value">>={conditions["min_validation_score"]}</span>')
                    if conditions.get("risk_filters"):
                        parts.append(f'<span class="conditions-key">risk_filters</span>: <span class="conditions-value">✅</span>')
                    if conditions.get("fvg_bull"):
                        parts.append(f'<span class="conditions-key">fvg_bull</span>: <span class="conditions-value">true</span>')
                    if conditions.get("fvg_bear"):
                        parts.append(f'<span class="conditions-key">fvg_bear</span>: <span class="conditions-value">true</span>')
                    if conditions.get("m1_choch_bos_combo"):
                        parts.append(f'<span class="conditions-key">m1_choch_bos_combo</span>: <span class="conditions-value">true</span>')
                    if conditions.get("min_volatility"):
                        parts.append(f'<span class="conditions-key">min_volatility</span>: <span class="conditions-value">{conditions["min_volatility"]}</span>')
                    if conditions.get("bb_width_threshold"):
                        parts.append(f'<span class="conditions-key">bb_width_threshold</span>: <span class="conditions-value">{conditions["bb_width_threshold"]}</span>')
                    if conditions.get("time_after"):
                        parts.append(f'<span class="conditions-key">time_after</span>: <span class="conditions-value">{conditions["time_after"]}</span>')
                    if conditions.get("time_before"):
                        parts.append(f'<span class="conditions-key">time_before</span>: <span class="conditions-value">{conditions["time_before"]}</span>')
                    if conditions.get("execute_immediately"):
                        parts.append(f'<span class="conditions-key">execute_immediately</span>: <span class="conditions-value">true</span>')
                    if conditions.get("volatility_state"):
                        parts.append(f'<span class="conditions-key">volatility_state</span>: <span class="conditions-value">{conditions["volatility_state"]}</span>')
                    if conditions.get("fvg_filled_pct"):
                        filled = conditions["fvg_filled_pct"]
                        if isinstance(filled, dict) and "min" in filled:
                            parts.append(f'<span class="conditions-key">fvg_filled_pct</span>: <span class="conditions-value">{filled["min"]*100}%-{filled["max"]*100}%</span>')
                        else:
                            parts.append(f'<span class="conditions-key">fvg_filled_pct</span>: <span class="conditions-value">>={filled*100}%</span>')
                    
                    # Add any remaining conditions that weren't already displayed
                    displayed_keys = {
                        "price_above", "price_below", "price_near", "tolerance",
                        "choch_bull", "choch_bear", "bos_bull", "bos_bear",
                        "order_block", "order_block_type", "rejection_wick",
                        "liquidity_sweep", "vwap_deviation", "vwap_deviation_direction",
                        "bb_expansion", "bb_squeeze", "bb_expansion_threshold",
                        "bb_expansion_check_both", "range_scalp_confluence",
                        "structure_confirmation", "structure_timeframe",
                        "inside_bar", "equal_highs", "equal_lows",
                        "rsi_div_bull", "rsi_div_bear", "timeframe",
                        "plan_type", "strategy_type", "min_confluence",
                        "min_validation_score", "risk_filters", "fvg_bull", "fvg_bear",
                        "m1_choch_bos_combo", "min_volatility", "bb_width_threshold",
                        "time_after", "time_before", "execute_immediately", "volatility_state",
                        "fvg_filled_pct"
                    }
                    
                    for key, value in conditions.items():
                        if key not in displayed_keys:
                            if isinstance(value, bool):
                                if value:
                                    parts.append(f'<span class="conditions-key">{key.replace("_", " ").title()}</span>: <span class="conditions-value">true</span>')
                            elif isinstance(value, (int, float)):
                                parts.append(f'<span class="conditions-key">{key.replace("_", " ").title()}</span>: <span class="conditions-value">{value}</span>')
                            elif isinstance(value, str):
                                parts.append(f'<span class="conditions-key">{key.replace("_", " ").title()}</span>: <span class="conditions-value">{value}</span>')
                            else:
                                parts.append(f'<span class="conditions-key">{key.replace("_", " ").title()}</span>: <span class="conditions-value">{value}</span>')
                    
                    if parts:
                        conditions_display = "<br>".join(parts)
                    else:
                        conditions_display = '<span class="muted">No conditions</span>'
                else:
                    conditions_display = '<span class="muted">No conditions</span>'
                
                status_class = f"status-{status.lower()}"
                direction_class = f"direction-{direction.lower()}"
                
                # Format dates
                created_display = created_at[:16].replace("T", " ") if created_at != "N/A" else "N/A"
                expires_display = expires_at[:16].replace("T", " ") if expires_at != "N/A" else "N/A"
                
                # Format prices safely
                entry_display = f"{entry_price:.2f}" if entry_price else "N/A"
                sl_display = f"{stop_loss:.2f}" if stop_loss else "N/A"
                tp_display = f"{take_profit:.2f}" if take_profit else "N/A"
                volume_display = f"{volume:.2f}" if volume else "N/A"
                
                # Get profit/loss data for executed plans
                ticket = plan.get("ticket")
                trade_result = trade_results.get(ticket) if ticket else None
                
                # Debug logging
                if ticket and not trade_result:
                    logger.debug(f"⚠️ No trade_result in dictionary for ticket {ticket} (plan {plan.get('plan_id')}) - trade_results has {len(trade_results)} entries")
                elif trade_result:
                    logger.debug(f"✅ Found trade_result for ticket {ticket}: status={trade_result.get('status')}, profit=${trade_result.get('profit', 0):.2f}")
                
                if trade_result and trade_result.get('status') == 'closed':
                    profit = trade_result.get('profit', 0)
                    profit_display = f"${profit:+.2f}"  # +$50.25 or -$25.00
                    profit_class = "profit-positive" if profit > 0 else "profit-negative"
                    exit_price = trade_result.get('exit_price', 'N/A')
                    if exit_price != 'N/A' and exit_price is not None:
                        exit_price = f"{exit_price:.2f}"
                    close_time = trade_result.get('close_time', 'N/A')
                    # Format close_time
                    if close_time != 'N/A' and close_time:
                        try:
                            # Handle ISO format string
                            if isinstance(close_time, str):
                                close_time = close_time[:16].replace('T', ' ')
                        except:
                            close_time = 'N/A'
                elif trade_result and trade_result.get('status') == 'open':
                    profit_display = "Open"
                    profit_class = "profit-open"
                    exit_price = "N/A"
                    close_time = "N/A"
                else:
                    profit_display = "N/A"
                    profit_class = "profit-na"
                    exit_price = "N/A"
                    close_time = "N/A"
                
                # Generate cancel button (only for pending plans)
                if status.lower() == "pending":
                    cancel_button = f'<button class="cancel-btn" onclick="cancelPlan(\'{plan_id}\', this)">❌ Cancel</button>'
                else:
                    cancel_button = '<span style="color: #6b7280; font-size: 10px;">-</span>'
                
                table_rows += f"""
                <tr>
                    <td><div class="cell-text">{created_display}</div></td>
                    <td><div class="plan-id">{plan_id}</div></td>
                    <td>{symbol}</td>
                    <td class="{direction_class}">{direction}</td>
                    <td><div class="price">{entry_display}</div></td>
                    <td><div class="price">{sl_display}</div></td>
                    <td><div class="price">{tp_display}</div></td>
                    <td>{volume_display}</td>
                    <td class="{status_class}">{status.upper()}</td>
                    <td><div class="cell-text">{expires_display}</div></td>
                    <td><div class="conditions-compact" style="font-family: monospace; font-size: 10px; line-height: 1.3; color: #9fb0c3; background: #0f172a; padding: 6px; border-radius: 4px; max-width: 400px;" title="{json.dumps(conditions, indent=2) if conditions else 'None'}">{conditions_display}</div></td>
                    <td><div class="notes-compact" style="white-space: normal; word-break: break-word; line-height: 1.3;">{notes}</div></td>
                    <td class="{profit_class}">{profit_display}</td>
                    <td><div class="price">{exit_price}</div></td>
                    <td><div class="cell-text">{close_time}</div></td>
                    <td>{cancel_button}</td>
                </tr>
                """
        
        # Get all plans for stats (not filtered)
        all_plans_for_stats = status_result.get("plans", []) if status_result.get("success") else []
        pending_count = len([p for p in all_plans_for_stats if p.get("status", "").lower() == "pending"])
        executed_count = len([p for p in all_plans_for_stats if p.get("status", "").lower() in ["executed", "closed"]])
        cancelled_count = len([p for p in all_plans_for_stats if p.get("status", "").lower() == "cancelled"])
        
        # Extract unique symbols from all plans (not filtered)
        unique_symbols = sorted(set([p.get("symbol", "N/A") for p in all_plans_for_stats if p.get("symbol")]))
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Auto Execution Plans - Synergis Trading</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 24px; background: #0b1220; color: #e6edf3; }}
                .container {{ max-width: 100%; margin: 0 auto; }}
                h1 {{ margin-bottom: 8px; color: #e6edf3; }}
                .nav {{ margin-bottom: 20px; }}
                .nav a {{ color: #9fb0c3; text-decoration: none; margin-right: 20px; }}
                .nav a:hover {{ color: #e6edf3; }}
                .tickers {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin: 10px 0; }}
                .ticker-container {{ background: #111a2e; border: 1px solid #213352; padding: 8px; border-radius: 6px; }}
                .ticker-label {{ color: #9fb0c3; font-size: 10px; text-transform: uppercase; margin-bottom: 6px; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 8px; margin: 10px 0; }}
                .stat-card {{ background: #111a2e; border: 1px solid #213352; padding: 10px; border-radius: 6px; border-left: 3px solid #90c0ff; }}
                .stat-label {{ color: #9fb0c3; font-size: 10px; text-transform: uppercase; margin-bottom: 5px; }}
                .stat-value {{ color: #e6edf3; font-size: 16px; font-weight: 600; }}
                .controls {{ margin: 10px 0; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
                button {{ padding: 8px 12px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; font-size: 12px; }}
                button:hover {{ background: #213352; }}
                .filter-control {{ display: flex; align-items: center; gap: 8px; }}
                .filter-control label {{ color: #9fb0c3; font-size: 12px; }}
                .filter-control select {{ padding: 8px; border-radius: 6px; border: 1px solid #24324a; background: #0f172a; color: #e6edf3; font-size: 12px; min-width: 120px; cursor: pointer; }}
                .filter-control select:focus {{ outline: none; border-color: #90c0ff; }}
                .filter-control select option {{ background: #0f172a; color: #e6edf3; }}
                .table-wrapper {{ overflow-x: auto; margin-top: 10px; -webkit-overflow-scrolling: touch; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); }}
                table {{ width: 100%; border-collapse: collapse; }}
                th {{ background: #111a2e; padding: 8px 6px; text-align: left; color: #9fb0c3; font-weight: 600; font-size: 10px; text-transform: uppercase; position: sticky; top: 0; z-index: 10; white-space: nowrap; }}
                td {{ padding: 8px 6px; border-bottom: 1px solid #213352; font-size: 11px; vertical-align: top; color: #e6edf3; }}
                tr:hover {{ background: #111a2e; }}
                .status-pending {{ color: #ff9800; font-weight: 600; }}
                .status-executed {{ color: #4caf50; font-weight: 600; }}
                .status-cancelled {{ color: #9e9e9e; }}
                .empty {{ text-align: center; padding: 20px; color: #6b7280; }}
                
                /* Column width constraints - more compact */
                th:nth-child(1), td:nth-child(1) {{ min-width: 110px; max-width: 110px; }} /* Created At */
                th:nth-child(2), td:nth-child(2) {{ min-width: 90px; max-width: 90px; }} /* Plan ID */
                th:nth-child(3), td:nth-child(3) {{ min-width: 65px; max-width: 65px; }} /* Symbol */
                th:nth-child(4), td:nth-child(4) {{ min-width: 60px; max-width: 60px; }} /* Direction */
                th:nth-child(5), td:nth-child(5) {{ min-width: 75px; max-width: 75px; }} /* Entry */
                th:nth-child(6), td:nth-child(6) {{ min-width: 75px; max-width: 75px; }} /* SL */
                th:nth-child(7), td:nth-child(7) {{ min-width: 75px; max-width: 75px; }} /* TP */
                th:nth-child(8), td:nth-child(8) {{ min-width: 55px; max-width: 55px; }} /* Volume */
                th:nth-child(9), td:nth-child(9) {{ min-width: 70px; max-width: 70px; }} /* Status */
                th:nth-child(10), td:nth-child(10) {{ min-width: 110px; max-width: 110px; }} /* Expires */
                th:nth-child(11), td:nth-child(11) {{ min-width: 180px; max-width: 180px; }} /* Conditions */
                th:nth-child(12), td:nth-child(12) {{ min-width: 150px; max-width: 150px; }} /* Notes */
                th:nth-child(13), td:nth-child(13) {{ min-width: 90px; max-width: 90px; }} /* Profit/Loss */
                th:nth-child(14), td:nth-child(14) {{ min-width: 75px; max-width: 75px; }} /* Exit Price */
                th:nth-child(15), td:nth-child(15) {{ min-width: 110px; max-width: 110px; }} /* Close Time */
                th:nth-child(16), td:nth-child(16) {{ min-width: 80px; max-width: 80px; }} /* Cancel */
                
                /* Text handling for long content */
                .cell-text {{ overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; line-height: 1.3; max-height: 2.6em; color: #e6edf3; }}
                .cell-text:hover {{ overflow: visible; display: block; position: relative; z-index: 20; background: #111a2e; padding: 6px; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); max-height: none; white-space: normal; word-break: break-word; }}
                .plan-id {{ font-family: monospace; font-size: 10px; color: #e6edf3; }}
                .price {{ font-family: monospace; font-size: 10px; color: #e6edf3; }}
                .direction-buy {{ color: #90ee90; font-weight: 600; }}
                .direction-sell {{ color: #ff9090; font-weight: 600; }}
                .conditions-compact {{ font-size: 10px; line-height: 1.2; color: #9fb0c3; }}
                .conditions-key {{ color: #90c0ff; }}
                .conditions-value {{ color: #90ee90; }}
                .conditions-missing {{ color: #ff9090; }}
                .conditions-section {{ margin-bottom: 8px; }}
                .conditions-section-title {{ font-weight: bold; color: #90c0ff; margin-bottom: 4px; }}
                .notes-compact {{ font-size: 10px; line-height: 1.3; color: #e6edf3; }}
                .cancel-btn {{ padding: 5px 10px; background: #f44336; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 11px; transition: background 0.2s; }}
                .cancel-btn:hover {{ background: #d32f2f; }}
                .cancel-btn:disabled {{ background: #6b7280; cursor: not-allowed; opacity: 0.6; }}
                .cancel-btn.cancelling {{ background: #ff9800; }}
                .profit-positive {{ color: #4caf50; font-weight: 600; }}
                .profit-negative {{ color: #f44336; font-weight: 600; }}
                .profit-open {{ color: #ff9800; font-weight: 600; }}
                .profit-na {{ color: #9e9e9e; }}
                .monitoring-status {{ display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding: 12px; background: #0f172a; border-radius: 8px; border: 1px solid #24324a; }}
                .status-indicator {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
                .status-indicator.active {{ background: #22c55e; box-shadow: 0 0 8px rgba(34, 197, 94, 0.5); }}
                .status-indicator.inactive {{ background: #ef4444; box-shadow: 0 0 8px rgba(239, 68, 68, 0.5); }}
                .status-text {{ color: #e6edf3; font-size: 14px; }}
                .status-text.active {{ color: #22c55e; }}
                .status-text.inactive {{ color: #ef4444; }}
                .status-details {{ color: #9fb0c3; font-size: 12px; margin-left: 4px; }}
                
                /* Responsive styles for smaller screens */
                @media (max-width: 1920px) {{
                    .tickers {{ grid-template-columns: repeat(2, 1fr); }}
                }}
                
                @media (max-width: 1400px) {{
                    .tickers {{ grid-template-columns: 1fr; }}
                }}
                
                @media (max-width: 768px) {{
                    body {{ padding: 8px; }}
                    h1 {{ font-size: 18px; }}
                    .nav a {{ padding: 5px 8px; font-size: 11px; }}
                    .stats {{ grid-template-columns: repeat(2, 1fr); gap: 8px; }}
                    .stat-card {{ padding: 8px; }}
                    .stat-value {{ font-size: 14px; }}
                    .ticker-container {{ padding: 6px; }}
                    .tradingview-widget-container {{ height: 120px !important; }}
                    th, td {{ font-size: 9px; padding: 6px 4px; }}
                }}
                
                /* Reduce widget height on medium screens */
                @media (max-width: 1400px) {{
                    .tradingview-widget-container {{ height: 140px !important; }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 Auto Execution Plans</h1>
                <div class="nav">
                    <a href="/">Home</a>
                    <a href="/alerts/view">Alerts</a>
                    <a href="/auto-execution/view">Auto Execution</a>
                    <a href="/volatility-regime/monitor">Volatility Monitor</a>
                    <a href="/dtms/status">DTMS Status</a>
                    <a href="/dtms/actions">DTMS Actions</a>
                    <a href="/dtms/status">DTMS Status</a>
                    <a href="/dtms/actions">DTMS Actions</a>
                    <a href="/scalps/view">Automated Scalps</a>
                    <a href="/docs">API Docs</a>
                </div>
                
                <div class="tickers">
                    <div class="ticker-container">
                        <div class="ticker-label">XAUUSD (Gold)</div>
                        <!-- TradingView Widget BEGIN -->
                        <div class="tradingview-widget-container">
                            <div class="tradingview-widget-container__widget"></div>
                            <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
                            {{
                            "symbol": "FX_IDC:XAUUSD",
                            "width": "100%",
                            "height": "140",
                            "locale": "en",
                            "dateRange": "1D",
                            "colorTheme": "dark",
                            "isTransparent": true,
                            "autosize": true,
                            "largeChartUrl": ""
                            }}
                            </script>
                        </div>
                        <!-- TradingView Widget END -->
                    </div>
                    
                    <div class="ticker-container">
                        <div class="ticker-label">BTCUSD (Bitcoin)</div>
                        <!-- TradingView Widget BEGIN -->
                        <div class="tradingview-widget-container">
                            <div class="tradingview-widget-container__widget"></div>
                            <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
                            {{
                            "symbol": "BINANCE:BTCUSDT",
                            "width": "100%",
                            "height": "140",
                            "locale": "en",
                            "dateRange": "1D",
                            "colorTheme": "dark",
                            "isTransparent": true,
                            "autosize": true,
                            "largeChartUrl": ""
                            }}
                            </script>
                        </div>
                        <!-- TradingView Widget END -->
                    </div>
                </div>
                
                <!-- Confluence Score Dashboard -->
                <div class="confluence-dashboard" style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #24324a; margin-bottom: 20px; margin-top: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <h3 style="margin: 0; color: #e6edf3; font-size: 18px;">Multi-Timeframe Confluence</h3>
                        <button id="refreshConfluence" style="padding: 6px 12px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer;">
                            Refresh
                        </button>
                    </div>
                    
                    <div class="confluence-symbols" style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                        <!-- XAUUSDc Block -->
                        <div class="confluence-symbol-block" data-symbol="XAUUSDc">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <span style="color: #90c0ff; font-weight: bold; font-size: 16px;">XAUUSDc</span>
                                <button class="show-confluence-btn" data-symbol="XAUUSDc" style="padding: 4px 8px; border-radius: 4px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; font-size: 12px;">
                                    Show Confluence
                                </button>
                            </div>
                            <div class="confluence-results" data-symbol="XAUUSDc" style="display: none; margin-top: 8px;">
                                <!-- Results table will be inserted here -->
                            </div>
                        </div>
                        
                        <!-- BTCUSDc Block -->
                        <div class="confluence-symbol-block" data-symbol="BTCUSDc">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <span style="color: #90c0ff; font-weight: bold; font-size: 16px;">BTCUSDc</span>
                                <button class="show-confluence-btn" data-symbol="BTCUSDc" style="padding: 4px 8px; border-radius: 4px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; font-size: 12px;">
                                    Show Confluence
                                </button>
                            </div>
                            <div class="confluence-results" data-symbol="BTCUSDc" style="display: none; margin-top: 8px;">
                                <!-- Results table will be inserted here -->
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="monitoring-status">
                    <span id="statusIndicator" class="status-indicator inactive"></span>
                    <span id="statusText" class="status-text inactive">Checking...</span>
                    <span id="statusDetails" class="status-details">• Loading status...</span>
                </div>
                
                {f'''
                <div class="stats" style="margin-top: 10px;">
                    <div class="stat-card" style="border-left-color: {"#4caf50" if summary_stats["total_pnl"] >= 0 else "#f44336"};">
                        <div class="stat-label">Total P&L</div>
                        <div class="stat-value" style="color: {"#4caf50" if summary_stats["total_pnl"] >= 0 else "#f44336"};">
                            ${summary_stats["total_pnl"]:+.2f}
                        </div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Wins</div>
                        <div class="stat-value" style="color: #4caf50;">{summary_stats["wins"]}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Losses</div>
                        <div class="stat-value" style="color: #f44336;">{summary_stats["losses"]}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Win Rate</div>
                        <div class="stat-value">{summary_stats["win_rate"]:.1f}%</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Avg P&L</div>
                        <div class="stat-value" style="color: {"#4caf50" if summary_stats["avg_pnl"] >= 0 else "#f44336"};">
                            ${summary_stats["avg_pnl"]:+.2f}
                        </div>
                    </div>
                </div>
                ''' if status_filter.lower() == "executed" and summary_stats["wins"] + summary_stats["losses"] > 0 else ''}
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-label">Showing</div>
                        <div class="stat-value">{len(plans)}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Pending</div>
                        <div class="stat-value">{pending_count}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Executed</div>
                        <div class="stat-value">{executed_count}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Cancelled</div>
                        <div class="stat-value">{cancelled_count}</div>
                    </div>
                </div>
                
                <div class="controls">
                    <button onclick="location.reload()">🔄 Refresh</button>
                    <div class="filter-control">
                        <label for="statusFilter">Filter by Status:</label>
                        <select id="statusFilter" onchange="filterByStatus()">
                            <option value="pending" {'selected' if status_filter.lower() == 'pending' else ''}>Pending</option>
                            <option value="executed" {'selected' if status_filter.lower() == 'executed' else ''}>Executed & Closed</option>
                            <option value="closed" {'selected' if status_filter.lower() == 'closed' else ''}>Closed Only</option>
                            <option value="cancelled" {'selected' if status_filter.lower() == 'cancelled' else ''}>Cancelled</option>
                            <option value="expired" {'selected' if status_filter.lower() == 'expired' else ''}>Expired</option>
                            <option value="all" {'selected' if status_filter.lower() == 'all' else ''}>All Statuses</option>
                        </select>
                    </div>
                    <div class="filter-control">
                        <label for="symbolFilter">Filter by Symbol:</label>
                        <select id="symbolFilter" onchange="filterTable()">
                            <option value="">All Symbols</option>
                            {''.join([f'<option value="{symbol}">{symbol}</option>' for symbol in unique_symbols])}
                        </select>
                    </div>
                    <div class="filter-control" style="margin-left: 20px; border-left: 1px solid #24324a; padding-left: 20px;">
                        <label style="color: #f44336; font-weight: bold;">Bulk Delete:</label>
                        <button id="deleteAllBtn" onclick="deleteAllPlans()" style="padding: 8px 16px; background: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; margin-right: 8px;">
                            Delete All Plans
                        </button>
                        <button id="deleteSymbolBtn" onclick="deletePlansBySymbol()" style="padding: 8px 16px; background: #ff9800; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">
                            Delete Plans for Selected Symbol
                        </button>
                    </div>
                </div>
                
                <div class="table-wrapper">
                    <table id="plansTable">
                        <thead>
                            <tr>
                                <th>Created At</th>
                                <th>Plan ID</th>
                                <th>Symbol</th>
                                <th>Direction</th>
                                <th>Entry Price</th>
                                <th>Stop Loss</th>
                                <th>Take Profit</th>
                                <th>Volume</th>
                                <th>Status</th>
                                <th>Expires At</th>
                                <th>Conditions</th>
                                <th>Notes</th>
                                <th>Profit/Loss</th>
                                <th>Exit Price</th>
                                <th>Close Time</th>
                                <th>Cancel</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <script>
                // Status filter function - reload page with new status filter
                function filterByStatus() {{
                    const select = document.getElementById('statusFilter');
                    const status = select.value;
                    const url = new URL(window.location);
                    url.searchParams.set('status_filter', status);
                    window.location.href = url.toString();
                }}
                
                // Symbol filter function
                function filterTable() {{
                    const select = document.getElementById('symbolFilter');
                    const filter = select.value.toUpperCase();
                    const table = document.getElementById('plansTable');
                    const tr = table.getElementsByTagName('tr');
                    
                    // Loop through all table rows (skip header row)
                    for (let i = 1; i < tr.length; i++) {{
                        const td = tr[i].getElementsByTagName('td')[2]; // Symbol is in 3rd column (index 2)
                        if (td) {{
                            const txtValue = td.textContent || td.innerText;
                            // If filter is empty (All Symbols), show all rows
                            if (filter === '' || txtValue.toUpperCase() === filter) {{
                                tr[i].style.display = '';
                            }} else {{
                                tr[i].style.display = 'none';
                            }}
                        }}
                    }}
                }}
                
                // Check monitoring status function
                async function checkMonitoringStatus() {{
                    try {{
                        const res = await fetch('/auto-execution/system-status');
                        const data = await res.json();
                        const statusEl = document.getElementById('monitoringStatus');
                        const indicatorEl = document.getElementById('statusIndicator');
                        const statusTextEl = document.getElementById('statusText');
                        const statusDetailsEl = document.getElementById('statusDetails');
                        
                        if (data.success && data.system_status) {{
                            const running = data.system_status.running || false;
                            const pendingPlans = data.system_status.pending_plans || 0;
                            
                            if (running) {{
                                if (indicatorEl) {{
                                    indicatorEl.className = 'status-indicator active';
                                }}
                                if (statusTextEl) {{
                                    statusTextEl.textContent = 'Active';
                                    statusTextEl.className = 'status-text active';
                                }}
                                if (statusDetailsEl) {{
                                    statusDetailsEl.textContent = `• Monitoring ${{pendingPlans}} pending plan${{pendingPlans !== 1 ? 's' : ''}} • Checking every 30 seconds`;
                                }}
                            }} else {{
                                if (indicatorEl) {{
                                    indicatorEl.className = 'status-indicator inactive';
                                }}
                                if (statusTextEl) {{
                                    statusTextEl.textContent = 'Not Running';
                                    statusTextEl.className = 'status-text inactive';
                                }}
                                if (statusDetailsEl) {{
                                    statusDetailsEl.textContent = '• Plans will NOT be monitored or executed • Check server logs for errors';
                                }}
                            }}
                        }} else {{
                            // Error or unknown status
                            if (indicatorEl) {{
                                indicatorEl.className = 'status-indicator inactive';
                            }}
                            if (statusTextEl) {{
                                statusTextEl.textContent = 'Unknown';
                                statusTextEl.className = 'status-text inactive';
                            }}
                            if (statusDetailsEl) {{
                                statusDetailsEl.textContent = '• Could not determine status';
                            }}
                        }}
                    }} catch (error) {{
                        console.error('Error checking monitoring status:', error);
                        const indicatorEl = document.getElementById('statusIndicator');
                        const statusTextEl = document.getElementById('statusText');
                        const statusDetailsEl = document.getElementById('statusDetails');
                        
                        if (indicatorEl) {{
                            indicatorEl.className = 'status-indicator inactive';
                        }}
                        if (statusTextEl) {{
                            statusTextEl.textContent = 'Error';
                            statusTextEl.className = 'status-text inactive';
                        }}
                        if (statusDetailsEl) {{
                            statusDetailsEl.textContent = '• Could not connect to status endpoint';
                        }}
                    }}
                }}
                
                // Cancel plan function
                async function cancelPlan(planId, buttonElement) {{
                    if (!confirm(`Are you sure you want to cancel plan ${{planId}}?`)) {{
                        return;
                    }}
                    
                    // Disable button and show loading state
                    buttonElement.disabled = true;
                    buttonElement.classList.add('cancelling');
                    buttonElement.textContent = 'Cancelling...';
                    
                    try {{
                        const response = await fetch(`/auto-execution/cancel-plan/${{planId}}`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }}
                        }});
                        
                        const data = await response.json();
                        
                        if (response.ok && data.success) {{
                            buttonElement.textContent = 'Cancelled';
                            buttonElement.style.background = '#6b7280';
                            
                            // Update status cell in the same row
                            const row = buttonElement.closest('tr');
                            const statusCell = row.querySelector('td.status-pending, td.status-executed, td.status-cancelled');
                            if (statusCell) {{
                                statusCell.textContent = 'CANCELLED';
                                statusCell.className = 'status-cancelled';
                            }}
                            
                            // Reload page after 1 second to show updated status
                            setTimeout(() => {{
                                location.reload();
                            }}, 1000);
                        }} else {{
                            alert(`Failed to cancel plan: ${{data.message || 'Unknown error'}}`);
                            buttonElement.disabled = false;
                            buttonElement.classList.remove('cancelling');
                            buttonElement.textContent = '❌ Cancel';
                        }}
                    }} catch (error) {{
                        alert(`Error cancelling plan: ${{error.message}}`);
                        buttonElement.disabled = false;
                        buttonElement.classList.remove('cancelling');
                        buttonElement.textContent = '❌ Cancel';
                    }}
                }}
                
                // Delete all plans function
                async function deleteAllPlans() {{
                    // First confirmation
                    const firstConfirm = confirm('WARNING: This will delete ALL plans in the system.\\n\\nAre you sure you want to continue?');
                    if (!firstConfirm) {{
                        return;
                    }}
                    
                    // Second confirmation (double confirmation)
                    const secondConfirm = confirm('FINAL CONFIRMATION: You are about to delete ALL plans.\\n\\nThis action cannot be undone.\\n\\nType OK to confirm deletion of all plans.');
                    if (!secondConfirm) {{
                        return;
                    }}
                    
                    const button = document.getElementById('deleteAllBtn');
                    if (button) {{
                        button.disabled = true;
                        button.textContent = 'Deleting...';
                        button.style.background = '#ff9800';
                    }}
                    
                    try {{
                        const response = await fetch('/auto-execution/delete-all-plans', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }}
                        }});
                        
                        const data = await response.json();
                        
                        if (response.ok && data.success) {{
                            alert(`Success: ${{data.message}}\\nDeleted: ${{data.deleted_count}} plan(s)`);
                            // Reload page after 1 second
                            setTimeout(() => {{
                                location.reload();
                            }}, 1000);
                        }} else {{
                            alert(`Failed to delete plans: ${{data.error || data.message || 'Unknown error'}}`);
                            if (button) {{
                                button.disabled = false;
                                button.textContent = 'Delete All Plans';
                                button.style.background = '#f44336';
                            }}
                        }}
                    }} catch (error) {{
                        alert(`Error deleting plans: ${{error.message}}`);
                        if (button) {{
                            button.disabled = false;
                            button.textContent = 'Delete All Plans';
                            button.style.background = '#f44336';
                        }}
                    }}
                }}
                
                // Delete plans by symbol function
                async function deletePlansBySymbol() {{
                    const symbolFilter = document.getElementById('symbolFilter');
                    const selectedSymbol = symbolFilter ? symbolFilter.value : '';
                    
                    if (!selectedSymbol) {{
                        alert('Please select a symbol from the filter dropdown first.');
                        return;
                    }}
                    
                    // First confirmation
                    const firstConfirm = confirm(`WARNING: This will delete ALL plans for symbol ${{selectedSymbol}}.\\n\\nAre you sure you want to continue?`);
                    if (!firstConfirm) {{
                        return;
                    }}
                    
                    // Second confirmation (double confirmation)
                    const secondConfirm = confirm(`FINAL CONFIRMATION: You are about to delete ALL plans for ${{selectedSymbol}}.\\n\\nThis action cannot be undone.\\n\\nType OK to confirm deletion.`);
                    if (!secondConfirm) {{
                        return;
                    }}
                    
                    const button = document.getElementById('deleteSymbolBtn');
                    if (button) {{
                        button.disabled = true;
                        button.textContent = 'Deleting...';
                        button.style.background = '#ff9800';
                    }}
                    
                    try {{
                        const response = await fetch(`/auto-execution/delete-all-plans?symbol=${{encodeURIComponent(selectedSymbol)}}`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }}
                        }});
                        
                        const data = await response.json();
                        
                        if (response.ok && data.success) {{
                            alert(`Success: ${{data.message}}\\nDeleted: ${{data.deleted_count}} plan(s) for ${{selectedSymbol}}`);
                            // Reload page after 1 second
                            setTimeout(() => {{
                                location.reload();
                            }}, 1000);
                        }} else {{
                            alert(`Failed to delete plans: ${{data.error || data.message || 'Unknown error'}}`);
                            if (button) {{
                                button.disabled = false;
                                button.textContent = 'Delete Plans for Selected Symbol';
                                button.style.background = '#ff9800';
                            }}
                        }}
                    }} catch (error) {{
                        alert(`Error deleting plans: ${{error.message}}`);
                        if (button) {{
                            button.disabled = false;
                            button.textContent = 'Delete Plans for Selected Symbol';
                            button.style.background = '#ff9800';
                        }}
                    }}
                }}
                
                // ============================================================================
                // CONFLUENCE DASHBOARD FUNCTIONS
                // ============================================================================
                
                // Debug: Log available buttons on page load
                document.addEventListener('DOMContentLoaded', function() {{
                    const buttons = document.querySelectorAll('.show-confluence-btn');
                    console.log(`Found ${{buttons.length}} confluence buttons:`, Array.from(buttons).map(btn => btn.dataset.symbol));
                }});
                
                // Fetch confluence data for a symbol
                async function fetchConfluenceData(symbol) {{
                    try {{
                        console.log(`Fetching confluence data for ${{symbol}}...`);
                        const response = await fetch(`/api/v1/confluence/multi-timeframe/${{symbol}}`);
                        if (!response.ok) {{
                            const errorText = await response.text();
                            console.error(`HTTP ${{response.status}} for ${{symbol}}:`, errorText);
                            throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                        }}
                        const data = await response.json();
                        console.log(`Successfully fetched data for ${{symbol}}:`, data);
                        return data;
                    }} catch (error) {{
                        console.error(`Error fetching confluence for ${{symbol}}:`, error);
                        return null;
                    }}
                }}
                
                // Render confluence table
                function renderConfluenceTable(symbol, data) {{
                    console.log(`Rendering confluence table for ${{symbol}} with data:`, data);
                    const resultsDiv = document.querySelector(`.confluence-results[data-symbol="${{symbol}}"]`);
                    if (!resultsDiv) {{
                        console.error(`Could not find results div for symbol ${{symbol}}`);
                        return;
                    }}
                    if (!data) {{
                        console.error(`No data provided for symbol ${{symbol}}`);
                        return;
                    }}
                    if (!data.timeframes) {{
                        console.error(`No timeframes in data for symbol ${{symbol}}:`, data);
                        return;
                    }}
                    
                    let html = '<table style="width: 100%; border-collapse: collapse; font-size: 13px;">';
                    html += '<thead><tr style="border-bottom: 1px solid #24324a;">';
                    html += '<th style="text-align: left; padding: 6px; color: #90c0ff;">Timeframe</th>';
                    html += '<th style="text-align: center; padding: 6px; color: #90c0ff;">Score</th>';
                    html += '<th style="text-align: center; padding: 6px; color: #90c0ff;">Grade</th>';
                    html += '<th style="text-align: left; padding: 6px; color: #90c0ff;">Visual</th>';
                    html += '</tr></thead><tbody>';
                    
                    const timeframes = ['M1', 'M5', 'M15', 'H1'];
                    timeframes.forEach(tf => {{
                        const tfData = data.timeframes[tf];
                        if (!tfData || !tfData.available) {{
                            html += `<tr><td>${{tf}}</td><td colspan="3" style="text-align: center; color: #9fb0c3;">N/A</td></tr>`;
                            return;
                        }}
                        
                        const score = Math.round(tfData.score);
                        const grade = tfData.grade;
                        const color = getScoreColor(score);
                        const gradeColor = getGradeColor(grade);
                        const barWidth = Math.round((score / 100) * 100);
                        
                        html += `<tr style="border-bottom: 1px solid #24324a;">`;
                        html += `<td style="padding: 6px; color: #e6edf3;">${{tf}}</td>`;
                        html += `<td style="text-align: center; padding: 6px; color: ${{color}}; font-weight: bold;">${{score}}</td>`;
                        html += `<td style="text-align: center; padding: 6px; color: ${{gradeColor}}; font-weight: bold;">${{grade}}</td>`;
                        html += `<td style="padding: 6px;"><div style="background: #0f172a; border: 1px solid #24324a; border-radius: 4px; height: 20px; position: relative;">`;
                        html += `<div style="background: ${{color}}; height: 100%; width: ${{barWidth}}%; border-radius: 4px; transition: width 0.3s;"></div></div></td>`;
                        html += `</tr>`;
                    }});
                    
                    html += '</tbody></table>';
                    html += `<div style="margin-top: 8px; font-size: 11px; color: #9fb0c3; text-align: right;">Updated: ${{new Date(data.timestamp).toLocaleTimeString()}}</div>`;
                    
                    resultsDiv.innerHTML = html;
                    resultsDiv.style.display = 'block';
                }}
                
                // Color coding helpers
                function getScoreColor(score) {{
                    if (score >= 80) return '#22c55e'; // Green
                    if (score >= 60) return '#eab308'; // Yellow
                    return '#ef4444'; // Red
                }}
                
                function getGradeColor(grade) {{
                    if (grade === 'A') return '#22c55e';
                    if (grade === 'B') return '#eab308';
                    if (grade === 'C') return '#f59e0b';
                    if (grade === 'D') return '#f97316';
                    return '#ef4444'; // F
                }}
                
                // Button click handler for Show/Hide Confluence
                document.addEventListener('click', async (e) => {{
                    if (e.target.classList.contains('show-confluence-btn')) {{
                        const symbol = e.target.dataset.symbol;
                        console.log(`Button clicked for symbol: ${{symbol}}`);
                        const resultsDiv = document.querySelector(`.confluence-results[data-symbol="${{symbol}}"]`);
                        const button = e.target;
                        
                        if (!resultsDiv) {{
                            console.error(`Could not find results div for symbol ${{symbol}}`);
                            return;
                        }}
                        
                        // Check if currently visible (handle both 'none' and empty string)
                        const isCurrentlyVisible = resultsDiv.style.display !== 'none' && resultsDiv.style.display !== '';
                        
                        // Toggle display
                        if (!isCurrentlyVisible) {{
                            // Show loading state
                            button.textContent = 'Loading...';
                            button.disabled = true;
                            resultsDiv.innerHTML = '<div style="text-align: center; color: #9fb0c3; padding: 12px;">Loading...</div>';
                            resultsDiv.style.display = 'block';
                            
                            // Fetch data
                            const data = await fetchConfluenceData(symbol);
                            
                            if (data && data.timeframes) {{
                                renderConfluenceTable(symbol, data);
                                button.textContent = 'Hide Confluence';
                            }} else {{
                                console.error(`Failed to load data for ${{symbol}}:`, data);
                                resultsDiv.innerHTML = '<div style="text-align: center; color: #ef4444; padding: 12px;">Error loading data. Check console for details.</div>';
                                button.textContent = 'Show Confluence';
                            }}
                            
                            button.disabled = false;
                        }} else {{
                            // Hide the results
                            resultsDiv.style.display = 'none';
                            button.textContent = 'Show Confluence';
                            console.log(`Hiding confluence for ${{symbol}}`);
                        }}
                    }}
                }});
                
                // Refresh all button handler
                document.addEventListener('click', async (e) => {{
                    if (e.target.id === 'refreshConfluence') {{
                        const buttons = document.querySelectorAll('.show-confluence-btn');
                        buttons.forEach(async (btn) => {{
                            if (btn.textContent === 'Hide Confluence') {{
                                const symbol = btn.dataset.symbol;
                                btn.textContent = 'Loading...';
                                btn.disabled = true;
                                
                                const data = await fetchConfluenceData(symbol);
                                if (data) {{
                                    renderConfluenceTable(symbol, data);
                                }}
                                
                                btn.disabled = false;
                            }}
                        }});
                    }}
                }});
                
                // Initialize monitoring status check
                checkMonitoringStatus();
                setInterval(checkMonitoringStatus, 30000); // Check status every 30 seconds
                
                // Auto-refresh every 30 seconds
                setTimeout(() => location.reload(), 30000);
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"Error loading auto-execution plans: {e}", exc_info=True)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error - Auto Execution Plans</title>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; background: #0a0e27; color: #e0e6ed; }}
                .error {{ color: #f44336; padding: 20px; background: #1a1f3a; border-radius: 8px; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h2>Error Loading Auto Execution Plans</h2>
                <p>{str(e)}</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=500)

# ============================================================================
# AUTO EXECUTION SYSTEM STATUS
# ============================================================================

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
        return {
            "success": False,
            "error": str(e),
            "system_status": {
                "running": False,
                "pending_plans": 0
            }
        }

@app.post("/auto-execution/delete-all-plans")
async def delete_all_plans(symbol: str = None):
    """Delete all plans (optionally filtered by symbol)"""
    try:
        from chatgpt_auto_execution_integration import get_chatgpt_auto_execution
        auto_execution = get_chatgpt_auto_execution()
        
        # Get all plans
        status_result = auto_execution.get_plan_status(include_all_statuses=True)
        all_plans = status_result.get("plans", []) if status_result.get("success") else []
        
        # Filter by symbol if provided
        if symbol:
            plans_to_delete = [p for p in all_plans if p.get("symbol", "").upper() == symbol.upper()]
        else:
            plans_to_delete = all_plans
        
        # Get plan IDs
        plan_ids = [p.get("plan_id") for p in plans_to_delete if p.get("plan_id")]
        
        if not plan_ids:
            return {
                "success": True,
                "message": f"No plans found to delete" + (f" for symbol {symbol}" if symbol else ""),
                "deleted_count": 0
            }
        
        # Cancel all plans
        deleted_count = 0
        failed_count = 0
        for plan_id in plan_ids:
            try:
                result = auto_execution.cancel_plan(plan_id)
                if result.get("success"):
                    deleted_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error cancelling plan {plan_id}: {e}")
                failed_count += 1
        
        message = f"Deleted {deleted_count} plan(s)" + (f" for symbol {symbol}" if symbol else " (all plans)")
        if failed_count > 0:
            message += f", {failed_count} failed"
        
        return {
            "success": True,
            "message": message,
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "total_plans": len(plan_ids)
        }
        
    except Exception as e:
        logger.error(f"Error deleting plans: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "deleted_count": 0
        }

# ============================================================================
# VOLATILITY REGIME MONITOR
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
        // Extract ticket from URL path
        const pathParts = window.location.pathname.split('/');
        const ticket = pathParts[pathParts.length - 1];
        
        // Use relative URL to fetch from same server
        const res = await fetch(`/api/dtms/trade/${ticket}`);
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

@app.get("/api/dtms/trade/{ticket}")
async def get_dtms_trade_info_api(ticket: int):
    """Get DTMS trade information as JSON (for webpage fetch) - Phase 6/7 Fix"""
    try:
        from dtms_integration import get_dtms_trade_status
        from infra.mt5_service import MT5Service
        import MetaTrader5 as mt5
        import httpx
        
        # Try to get DTMS trade status from local instance first
        trade_info = get_dtms_trade_status(ticket)
        
        # If not found locally, try DTMS API server (port 8001)
        if not trade_info or trade_info.get('error'):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"http://127.0.0.1:8001/dtms/trade/{ticket}")
                    if response.status_code == 200:
                        api_data = response.json()
                        if api_data.get("success") and api_data.get("trade_info"):
                            trade_info = {
                                "ticket": api_data["trade_info"].get("ticket"),
                                "symbol": api_data["trade_info"].get("symbol"),
                                "state": api_data["trade_info"].get("state"),
                                "current_score": api_data["trade_info"].get("current_score"),
                                "state_entry_time_human": api_data["trade_info"].get("state_entry_time"),
                                "warnings": api_data["trade_info"].get("warnings", {}),
                                "actions_taken": api_data["trade_info"].get("actions_taken", []),
                                "performance": api_data["trade_info"].get("performance", {}),
                                "error": None
                            }
            except Exception as api_error:
                logger.debug(f"DTMS API server not available for trade {ticket}: {api_error}")
        
        if trade_info and not trade_info.get('error'):
            # Enrich with MT5 position details
            mt5_details = {}
            try:
                mt5_service = MT5Service()
                if mt5_service.connect():
                    positions = mt5.positions_get(ticket=ticket)
                    if positions:
                        pos = positions[0]
                        mt5_details = {
                            "symbol": pos.symbol,
                            "type": "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                            "volume": pos.volume,
                            "open_price": pos.price_open,
                            "current_price": pos.price_current,
                            "profit": pos.profit,
                            "sl": pos.sl,
                            "tp": pos.tp
                        }
            except Exception:
                pass
            
            # Get intelligent exits status
            intelligent_exits = {}
            try:
                from chatgpt_bot import intelligent_exit_manager
                if intelligent_exit_manager:
                    rule = intelligent_exit_manager.rules.get(ticket)
                    if rule:
                        intelligent_exits = {
                            "breakeven_triggered": rule.breakeven_triggered,
                            "partial_profit_triggered": rule.partial_triggered,
                            "trailing_stop_active": rule.trailing_active
                        }
            except Exception:
                pass
            
            return {
                "success": True,
                "summary": f"Trade {ticket} is in {trade_info.get('state', 'Unknown')} state",
                "trade_info": {
                    "ticket": ticket,
                    "symbol": mt5_details.get('symbol') or trade_info.get('symbol'),
                    "type": mt5_details.get('type'),
                    "volume": mt5_details.get('volume'),
                    "open_price": mt5_details.get('open_price'),
                    "current_price": mt5_details.get('current_price'),
                    "profit": mt5_details.get('profit'),
                    "sl": mt5_details.get('sl'),
                    "tp": mt5_details.get('tp'),
                    "state": trade_info.get('state'),
                    "current_score": trade_info.get('current_score'),
                    "state_entry_time": trade_info.get('state_entry_time_human'),
                    "warnings": trade_info.get('warnings', {}),
                    "actions_taken": trade_info.get('actions_taken', []),
                    "performance": trade_info.get('performance', {}),
                    "protection_active": bool(trade_info.get('state') != 'CLOSED'),
                    "intelligent_exits": intelligent_exits
                }
            }
        else:
            error_msg = trade_info.get('error', 'Trade not found in DTMS') if trade_info else 'Trade not found in DTMS'
            return {
                "success": False,
                "summary": f"Could not get DTMS info for trade {ticket}: {error_msg}",
                "error": error_msg,
                "trade_info": None
            }
    except Exception as e:
        return {
            "success": False,
            "summary": f"Failed to get DTMS trade info: {str(e)}",
            "error": str(e)
        }

# ============================================================================
# TRADE REGISTRY ENDPOINT (for DTMS synergy)
# ============================================================================

@app.get("/trade-registry/{ticket}")
async def get_trade_registry_info(ticket: int):
    """Get trade ownership information from trade registry (for DTMS synergy)"""
    try:
        from infra.trade_registry import get_trade_state
        
        trade_state = get_trade_state(ticket)
        if trade_state:
            # Convert TradeState object to dict for JSON response
            return {
                "ticket": ticket,
                "managed_by": getattr(trade_state, 'managed_by', ''),
                "breakeven_triggered": getattr(trade_state, 'breakeven_triggered', False),
                "symbol": getattr(trade_state, 'symbol', ''),
                "direction": getattr(trade_state, 'direction', ''),
                "strategy_type": str(getattr(trade_state, 'strategy_type', None)) if hasattr(trade_state, 'strategy_type') and getattr(trade_state, 'strategy_type', None) else None
            }
        else:
            # Trade not in registry
            return {
                "ticket": ticket,
                "managed_by": "",
                "breakeven_triggered": False
            }
    except ImportError as e:
        logger.error(f"Error importing trade_registry: {e}")
        return {
            "ticket": ticket,
            "managed_by": "",
            "breakeven_triggered": False,
            "error": "Trade registry module not available"
        }
    except Exception as e:
        logger.error(f"Error getting trade registry info for {ticket}: {e}", exc_info=True)
        return {
            "ticket": ticket,
            "managed_by": "",
            "breakeven_triggered": False,
            "error": str(e)
        }

# ============================================================================
# DTMS STATUS
# ============================================================================

@app.get("/api/dtms/status")
async def get_dtms_status_api():
    """Get DTMS system status as JSON (for API access)"""
    try:
        from dtms_integration import get_dtms_system_status
        import httpx
        
        # Try to get DTMS status from local instance first
        status = get_dtms_system_status()
        
        # If not available locally, try DTMS API server (port 8001)
        if not status or status.get('error'):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get("http://127.0.0.1:8001/dtms/status")
                    if response.status_code == 200:
                        api_data = response.json()
                        if api_data.get("success") and api_data.get("dtms_status"):
                            status = {
                                "monitoring_active": api_data["dtms_status"].get("system_active", False),
                                "uptime_human": api_data["dtms_status"].get("uptime", "Unknown"),
                                "active_trades": api_data["dtms_status"].get("active_trades", 0),
                                "trades_by_state": api_data["dtms_status"].get("trades_by_state", {}),
                                "performance": api_data["dtms_status"].get("performance", {}),
                                "last_check_human": api_data["dtms_status"].get("last_check", "Unknown"),
                                "error": None
                            }
            except Exception as api_error:
                logger.debug(f"DTMS API server not available for status: {api_error}")
        
        if status and not status.get('error'):
            return {
                "success": True,
                "summary": f"DTMS system is active with {status.get('active_trades', 0)} trades monitored",
                "dtms_status": {
                    "system_active": status.get('monitoring_active', False),
                    "uptime": status.get('uptime_human', 'Unknown'),
                    "active_trades": status.get('active_trades', 0),
                    "trades_by_state": status.get('trades_by_state', {}),
                    "performance": status.get('performance', {}),
                    "last_check": status.get('last_check_human', 'Unknown')
                }
            }
        else:
            error_msg = status.get('error', 'DTMS system not available') if status else 'DTMS system not available'
            return {
                "success": False,
                "summary": f"DTMS system is not available: {error_msg}",
                "error": error_msg,
                "dtms_status": {
                    "system_active": False,
                    "error": error_msg
                }
            }
    except Exception as e:
        return {
            "success": False,
            "summary": f"Failed to get DTMS status: {str(e)}",
            "error": str(e)
        }

@app.get("/api/dtms/actions")
async def get_dtms_action_history_api():
    """Get DTMS action history as JSON (for API access)"""
    try:
        from dtms_integration import get_dtms_action_history
        import httpx
        
        # Try to get DTMS action history from local instance first
        history = get_dtms_action_history()
        
        # If not available locally, try DTMS API server (port 8001)
        if not history:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get("http://127.0.0.1:8001/dtms/actions")
                    if response.status_code == 200:
                        api_data = response.json()
                        if api_data.get("success") and api_data.get("action_history"):
                            history = api_data.get("action_history", [])
            except Exception as api_error:
                logger.debug(f"DTMS API server not available for action history: {api_error}")
        
        if history:
            return {
                "success": True,
                "summary": f"Retrieved {len(history)} DTMS actions",
                "action_history": history,
                "total_actions": len(history)
            }
        else:
            return {
                "success": True,
                "summary": "No DTMS actions found",
                "action_history": [],
                "total_actions": 0
            }
    except Exception as e:
        return {
            "success": False,
            "summary": f"Failed to get DTMS action history: {str(e)}",
            "error": str(e),
            "action_history": [],
            "total_actions": 0
        }

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
      <a href="/dtms/status">DTMS Status</a>
      <a href="/dtms/actions">DTMS Actions</a>
      <a href="/docs">API Docs</a>
    </div>
    <h1>DTMS Status</h1>
    <div class="sub">Dynamic Trade Management System • Updates every 10 seconds</div>
    <div class="controls">
      <button id="refresh">Refresh Now</button>
    </div>
    
    <div class="status-card">
      <h3>System Status</h3>
      <div id="system-status">Loading...</div>
    </div>
    
    <div class="status-card">
      <h3>Metrics</h3>
      <div class="metric">
        <span class="metric-label">Uptime:</span>
        <span class="metric-value" id="uptime">Unknown</span>
      </div>
      <div class="metric">
        <span class="metric-label">Active Trades:</span>
        <span class="metric-value" id="active-trades">0</span>
      </div>
      <div class="metric">
        <span class="metric-label">Last Check:</span>
        <span class="metric-value" id="last-check">Unknown</span>
      </div>
    </div>
    
    <div class="status-card">
      <h3>Performance</h3>
      <div class="metric">
        <span class="metric-label">Fast Checks:</span>
        <span class="metric-value" id="fast-checks">0</span>
      </div>
      <div class="metric">
        <span class="metric-label">Deep Checks:</span>
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
      <div id="trades-by-state">Loading...</div>
    </div>
    
    <div class="status-card">
      <h3>Active Trades</h3>
      <div class="trades-grid" id="active-trades">Loading...</div>
    </div>
  </body>
</html>
        """
    )
    return HTMLResponse(content=html)

# ============================================================================
# DTMS ACTIONS
# ============================================================================

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
      <a href="/dtms/status">DTMS Status</a>
      <a href="/dtms/actions">DTMS Actions</a>
      <a href="/docs">API Docs</a>
    </div>
    <h1>DTMS Actions</h1>
    <div class="sub">Action history from DTMS and Intelligent Exit systems • Total: <span id="count">0</span> actions</div>
    <div class="controls">
      <button id="refresh">Refresh Now</button>
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
      <tbody id="tbody">
        <tr><td colspan="6" style="text-align: center; color: #9fb0c3;">Loading...</td></tr>
      </tbody>
    </table>
  </body>
</html>
        """
    )
    return HTMLResponse(content=html)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Note: Reload mode only works when running via uvicorn command line:
    #   python -m uvicorn app.main_api:app --host 0.0.0.0 --port 8000 --reload
    # 
    # Direct execution (python app/main_api.py) cannot use reload because uvicorn
    # needs the app as an import string, not a direct object.
    # 
    # For development with auto-reload, use the batch file or run:
    #   python -m uvicorn app.main_api:app --host 0.0.0.0 --port 8000 --reload
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        log_level="info",
        reload=False  # Disabled - use uvicorn CLI for reload: python -m uvicorn app.main_api:app --reload
    )
