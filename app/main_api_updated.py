"""
Updated FastAPI server with separate database architecture
Uses logs database for WRITE access (API Server)
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request, Header, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from enum import Enum
import logging
import MetaTrader5 as mt5
import asyncio
import time
import json

# Add parent directory to path to import bot modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.mt5_service import MT5Service
from infra.journal_repo import JournalRepo
from infra.indicator_bridge import IndicatorBridge
from config import settings
from app.services import oco_tracker

# Import auto execution API
from app.auto_execution_api import router as auto_execution_router

# Import the new database access manager
from database_access_manager import DatabaseAccessManager, initialize_database_manager

# Import the updated unified pipeline integration
from unified_tick_pipeline_integration_updated import get_unified_pipeline_updated

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

# Initialize FastAPI app
app = FastAPI(
    title="MoneyBot v1.1 - Advanced AI Trading System API (Separate Database Architecture)",
    description="Revolutionary AI-powered trading system with separate database architecture",
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

# Initialize database access manager for API Server
db_manager = initialize_database_manager("api_server")

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
            del _idempotency_cache[k]
        
        # Return cached response if exists
        if key in _idempotency_cache:
            return _idempotency_cache[key]["response"]
    return None

async def _store_idempotent_response(key: str, response: Dict[str, Any]):
    async with _idempotency_lock:
        _idempotency_cache[key] = {
            "response": response,
            "ts": datetime.utcnow()
        }

# ============================================================================
# REQUEST LOGGING WITH SEPARATE DATABASE ARCHITECTURE
# ============================================================================

async def log_api_request(endpoint: str, method: str, status_code: int, response_time: float, details: Optional[str] = None):
    """Log API request to logs database (WRITE access)"""
    try:
        with db_manager.get_logs_db_connection(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_logs (endpoint, method, status_code, response_time, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (endpoint, method, status_code, response_time, time.time(), details))
            conn.commit()
            logger.info(f"✅ API request logged to logs database: {endpoint} {method} {status_code}")
    except Exception as e:
        logger.error(f"❌ Error logging API request: {e}")

async def log_system_health(component: str, status: str, details: Optional[str] = None):
    """Log system health to logs database (WRITE access)"""
    try:
        with db_manager.get_logs_db_connection(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO system_health (component, status, details, timestamp)
                VALUES (?, ?, ?, ?)
            """, (component, status, details, time.time()))
            conn.commit()
            logger.info(f"✅ System health logged: {component} - {status}")
    except Exception as e:
        logger.error(f"❌ Error logging system health: {e}")

# ============================================================================
# ENHANCED MARKET DATA WITH SEPARATE DATABASE ARCHITECTURE
# ============================================================================

async def get_enhanced_market_data(symbol: str) -> Dict[str, Any]:
    """Get enhanced market data using separate database architecture"""
    try:
        # Get tick data from main database (READ access)
        with db_manager.get_main_db_connection(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, price, volume, timestamp, source, bid, ask
                FROM unified_ticks 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (symbol,))
            
            row = cursor.fetchone()
            if row:
                tick_data = {
                    'symbol': row[0],
                    'price': row[1],
                    'volume': row[2],
                    'timestamp': row[3],
                    'source': row[4],
                    'bid': row[5],
                    'ask': row[6]
                }
            else:
                tick_data = {'error': 'No tick data found'}
        
        # Get M5 candles from main database (READ access)
        with db_manager.get_main_db_connection(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, open_price, high_price, low_price, close_price, volume, timestamp
                FROM m5_candles 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT 10
            """, (symbol,))
            
            rows = cursor.fetchall()
            m5_candles = []
            for row in rows:
                m5_candles.append({
                    'symbol': row[0],
                    'open': row[1],
                    'high': row[2],
                    'low': row[3],
                    'close': row[4],
                    'volume': row[5],
                    'timestamp': row[6]
                })
        
        # Get analysis data from analysis database (READ access)
        with db_manager.get_analysis_db_connection(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, analysis_type, result, confidence, timestamp
                FROM analysis_results 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT 5
            """, (symbol,))
            
            rows = cursor.fetchall()
            analysis_data = []
            for row in rows:
                analysis_data.append({
                    'symbol': row[0],
                    'analysis_type': row[1],
                    'result': json.loads(row[2]) if row[2] else {},
                    'confidence': row[3],
                    'timestamp': row[4]
                })
        
        return {
            'success': True,
            'data': {
                'tick_data': tick_data,
                'm5_candles': m5_candles,
                'analysis_data': analysis_data,
                'database_architecture': 'separate_databases',
                'access_info': {
                    'main_db': 'read',
                    'analysis_db': 'read',
                    'logs_db': 'write'
                }
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting enhanced market data: {e}")
        return {'error': str(e)}

async def get_volatility_analysis(symbol: str) -> Dict[str, Any]:
    """Get volatility analysis using separate database architecture"""
    try:
        # Get volatility analysis from analysis database (READ access)
        with db_manager.get_analysis_db_connection(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, analysis_type, result, confidence, timestamp
                FROM analysis_results 
                WHERE symbol = ? AND analysis_type = 'volatility_analysis'
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (symbol,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'success': True,
                    'data': {
                        'symbol': row[0],
                        'analysis_type': row[1],
                        'result': json.loads(row[2]) if row[2] else {},
                        'confidence': row[3],
                        'timestamp': row[4],
                        'database_architecture': 'separate_databases'
                    }
                }
            else:
                return {'error': 'No volatility analysis found'}
                
    except Exception as e:
        logger.error(f"❌ Error getting volatility analysis: {e}")
        return {'error': str(e)}

async def get_offset_calibration(symbol: str) -> Dict[str, Any]:
    """Get offset calibration using separate database architecture"""
    try:
        # Get offset calibration from analysis database (READ access)
        with db_manager.get_analysis_db_connection(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, analysis_type, result, confidence, timestamp
                FROM analysis_results 
                WHERE symbol = ? AND analysis_type = 'offset_calibration'
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (symbol,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'success': True,
                    'data': {
                        'symbol': row[0],
                        'analysis_type': row[1],
                        'result': json.loads(row[2]) if row[2] else {},
                        'confidence': row[3],
                        'timestamp': row[4],
                        'database_architecture': 'separate_databases'
                    }
                }
            else:
                return {'error': 'No offset calibration found'}
                
    except Exception as e:
        logger.error(f"❌ Error getting offset calibration: {e}")
        return {'error': str(e)}

async def get_system_health() -> Dict[str, Any]:
    """Get system health using separate database architecture"""
    try:
        # Get system health from logs database (READ access)
        with db_manager.get_logs_db_connection(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT component, status, details, timestamp
                FROM system_health 
                ORDER BY timestamp DESC 
                LIMIT 10
            """)
            
            rows = cursor.fetchall()
            health_data = []
            for row in rows:
                health_data.append({
                    'component': row[0],
                    'status': row[1],
                    'details': row[2],
                    'timestamp': row[3]
                })
        
        # Get database status
        db_status = db_manager.get_database_status()
        
        # Get shared memory
        shared_memory = db_manager.get_shared_memory()
        
        return {
            'success': True,
            'data': {
                'health_data': health_data,
                'database_status': db_status,
                'shared_memory': shared_memory,
                'database_architecture': 'separate_databases',
                'access_permissions': db_manager.access_permissions
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting system health: {e}")
        return {'error': str(e)}

async def get_pipeline_status() -> Dict[str, Any]:
    """Get pipeline status using separate database architecture"""
    try:
        # Get unified pipeline
        pipeline = get_unified_pipeline_updated()
        if not pipeline:
            return {'error': 'Unified Tick Pipeline not available'}
        
        # Get pipeline status
        pipeline_status = pipeline.get_pipeline_status()
        
        # Get database status
        db_status = db_manager.get_database_status()
        
        # Get shared memory
        shared_memory = db_manager.get_shared_memory()
        
        return {
            'success': True,
            'data': {
                'pipeline_status': pipeline_status,
                'database_status': db_status,
                'shared_memory': shared_memory,
                'database_architecture': 'separate_databases',
                'access_permissions': db_manager.access_permissions
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting pipeline status: {e}")
        return {'error': str(e)}

# ============================================================================
# API ENDPOINTS WITH SEPARATE DATABASE ARCHITECTURE
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint with separate database architecture"""
    try:
        # Get system health
        health_data = await get_system_health()
        
        # Log health check to logs database
        await log_api_request("/health", "GET", 200, 0.1, "Health check successful")
        
        return {
            "ok": True,
            "timestamp": datetime.utcnow().isoformat(),
            "database_architecture": "separate_databases",
            "components": {
                "database": "healthy" if health_data.get('success') else "unhealthy",
                "api_server": "healthy",
                "separate_databases": "active"
            },
            "access_permissions": db_manager.access_permissions
        }
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        await log_api_request("/health", "GET", 500, 0.1, f"Health check failed: {e}")
        return {
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/market-data/{symbol}")
async def get_market_data(symbol: str):
    """Get market data using separate database architecture"""
    start_time = time.time()
    
    try:
        # Get enhanced market data
        market_data = await get_enhanced_market_data(symbol)
        
        response_time = time.time() - start_time
        
        # Log API request
        await log_api_request(f"/market-data/{symbol}", "GET", 200, response_time, "Market data retrieved successfully")
        
        return market_data
        
    except Exception as e:
        response_time = time.time() - start_time
        logger.error(f"❌ Error getting market data for {symbol}: {e}")
        await log_api_request(f"/market-data/{symbol}", "GET", 500, response_time, f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/volatility/{symbol}")
async def get_volatility(symbol: str):
    """Get volatility analysis using separate database architecture"""
    start_time = time.time()
    
    try:
        # Get volatility analysis
        volatility_data = await get_volatility_analysis(symbol)
        
        response_time = time.time() - start_time
        
        # Log API request
        await log_api_request(f"/volatility/{symbol}", "GET", 200, response_time, "Volatility analysis retrieved successfully")
        
        return volatility_data
        
    except Exception as e:
        response_time = time.time() - start_time
        logger.error(f"❌ Error getting volatility analysis for {symbol}: {e}")
        await log_api_request(f"/volatility/{symbol}", "GET", 500, response_time, f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/offset-calibration/{symbol}")
async def get_offset_calibration_endpoint(symbol: str):
    """Get offset calibration using separate database architecture"""
    start_time = time.time()
    
    try:
        # Get offset calibration
        offset_data = await get_offset_calibration(symbol)
        
        response_time = time.time() - start_time
        
        # Log API request
        await log_api_request(f"/offset-calibration/{symbol}", "GET", 200, response_time, "Offset calibration retrieved successfully")
        
        return offset_data
        
    except Exception as e:
        response_time = time.time() - start_time
        logger.error(f"❌ Error getting offset calibration for {symbol}: {e}")
        await log_api_request(f"/offset-calibration/{symbol}", "GET", 500, response_time, f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/system-health")
async def get_system_health_endpoint():
    """Get system health using separate database architecture"""
    start_time = time.time()
    
    try:
        # Get system health
        health_data = await get_system_health()
        
        response_time = time.time() - start_time
        
        # Log API request
        await log_api_request("/system-health", "GET", 200, response_time, "System health retrieved successfully")
        
        return health_data
        
    except Exception as e:
        response_time = time.time() - start_time
        logger.error(f"❌ Error getting system health: {e}")
        await log_api_request("/system-health", "GET", 500, response_time, f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pipeline-status")
async def get_pipeline_status_endpoint():
    """Get pipeline status using separate database architecture"""
    start_time = time.time()
    
    try:
        # Get pipeline status
        pipeline_data = await get_pipeline_status()
        
        response_time = time.time() - start_time
        
        # Log API request
        await log_api_request("/pipeline-status", "GET", 200, response_time, "Pipeline status retrieved successfully")
        
        return pipeline_data
        
    except Exception as e:
        response_time = time.time() - start_time
        logger.error(f"❌ Error getting pipeline status: {e}")
        await log_api_request("/pipeline-status", "GET", 500, response_time, f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# STARTUP AND SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Startup event with separate database architecture"""
    try:
        logger.info("🚀 Starting API Server with separate database architecture...")
        
        # Test database access
        db_status = db_manager.get_database_status()
        logger.info(f"✅ Database status: {db_status}")
        
        # Log startup
        await log_system_health("api_server", "startup", "API Server started with separate database architecture")
        
        logger.info("✅ API Server started successfully with separate database architecture")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        await log_system_health("api_server", "startup_failed", f"Startup failed: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event with separate database architecture"""
    try:
        logger.info("🛑 Shutting down API Server...")
        
        # Log shutdown
        await log_system_health("api_server", "shutdown", "API Server shutting down")
        
        logger.info("✅ API Server shutdown completed")
        
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
