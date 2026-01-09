"""
Main API Unified Pipeline Integration

This module integrates the main API with the Unified Tick Pipeline to provide
enhanced HTTP API endpoints with real-time data access and analysis capabilities.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

# Global pipeline instance
_pipeline = None
_pipeline_initialized = False

async def initialize_main_api_unified_pipeline() -> bool:
    """
    Initialize the Unified Tick Pipeline for Main API integration
    
    Returns:
        bool: True if successful, False otherwise
    """
    global _pipeline, _pipeline_initialized
    
    try:
        logger.info("🚀 Initializing Main API Unified Pipeline integration...")
        
        # Import and initialize the pipeline
        from unified_tick_pipeline_integration import initialize_unified_pipeline
        
        # Initialize the pipeline
        pipeline_success = await initialize_unified_pipeline()
        
        if pipeline_success:
            # Get the pipeline instance
            from unified_tick_pipeline_integration import get_unified_pipeline
            _pipeline = get_unified_pipeline()
            
            if _pipeline:
                _pipeline_initialized = True
                logger.info("✅ Main API Unified Pipeline integration initialized")
                logger.info("   → Enhanced market data endpoints")
                logger.info("   → Real-time tick data access")
                logger.info("   → Multi-timeframe analysis")
                logger.info("   → Volatility monitoring")
                logger.info("   → Offset calibration")
                logger.info("   → System health monitoring")
                return True
            else:
                logger.error("❌ Failed to get pipeline instance")
                return False
        else:
            logger.error("❌ Failed to initialize Unified Tick Pipeline")
            return False
            
    except Exception as e:
        logger.error(f"❌ Main API Unified Pipeline integration failed: {e}")
        return False

def get_pipeline() -> Optional[Any]:
    """Get the Unified Tick Pipeline instance"""
    return _pipeline

def is_pipeline_initialized() -> bool:
    """Check if the pipeline is initialized"""
    return _pipeline_initialized

# ============================================================================
# ENHANCED API ENDPOINTS
# ============================================================================

async def get_enhanced_market_data(symbol: str, timeframe: str = "M1", limit: int = 100) -> Dict[str, Any]:
    """
    Get enhanced market data from Unified Tick Pipeline
    
    Args:
        symbol: Trading symbol
        timeframe: Data timeframe (M1, M5, M15, H1, H4)
        limit: Number of data points to return
        
    Returns:
        Dict containing enhanced market data
    """
    try:
        if not _pipeline_initialized or not _pipeline:
            return {"error": "Unified Tick Pipeline not initialized"}
        
        # Get pipeline status
        pipeline_status = await _pipeline.get_pipeline_status()
        
        # Get real-time tick data
        tick_data = _pipeline.get_latest_ticks(symbol, limit)
        
        # Get M5 volatility data if available
        m5_data = None
        if hasattr(_pipeline, 'm5_volatility_bridge'):
            m5_data = _pipeline.m5_volatility_bridge.get_volatility_data(symbol)
        
        # Get offset calibration data
        offset_data = None
        if hasattr(_pipeline, 'offset_calibrator'):
            offset_data = _pipeline.offset_calibrator.get_calibration_data(symbol)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": datetime.now().isoformat(),
            "pipeline_status": pipeline_status,
            "tick_data": tick_data,
            "m5_volatility": m5_data,
            "offset_calibration": offset_data,
            "data_source": "unified_pipeline"
        }
        
    except Exception as e:
        logger.error(f"Error getting enhanced market data for {symbol}: {e}")
        return {"error": str(e)}

async def get_volatility_analysis(symbol: str) -> Dict[str, Any]:
    """
    Get volatility analysis from Unified Tick Pipeline
    
    Args:
        symbol: Trading symbol
        
    Returns:
        Dict containing volatility analysis
    """
    try:
        if not _pipeline_initialized or not _pipeline:
            return {"error": "Unified Tick Pipeline not initialized"}
        
        # Get M5 volatility data
        m5_data = None
        if hasattr(_pipeline, 'm5_volatility_bridge'):
            m5_data = _pipeline.m5_volatility_bridge.get_volatility_data(symbol)
        
        # Get system health for volatility context
        system_health = _pipeline.get_system_health()
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "m5_volatility": m5_data,
            "system_health": system_health,
            "analysis_type": "volatility"
        }
        
    except Exception as e:
        logger.error(f"Error getting volatility analysis for {symbol}: {e}")
        return {"error": str(e)}

async def get_offset_calibration(symbol: str) -> Dict[str, Any]:
    """
    Get offset calibration data from Unified Tick Pipeline
    
    Args:
        symbol: Trading symbol
        
    Returns:
        Dict containing offset calibration data
    """
    try:
        if not _pipeline_initialized or not _pipeline:
            return {"error": "Unified Tick Pipeline not initialized"}
        
        # Get offset calibration data
        offset_data = None
        if hasattr(_pipeline, 'offset_calibrator'):
            offset_data = _pipeline.offset_calibrator.get_calibration_data(symbol)
        
        # Get system health for calibration context
        system_health = _pipeline.get_system_health()
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "offset_calibration": offset_data,
            "system_health": system_health,
            "calibration_type": "binance_mt5_offset"
        }
        
    except Exception as e:
        logger.error(f"Error getting offset calibration for {symbol}: {e}")
        return {"error": str(e)}

async def get_system_health() -> Dict[str, Any]:
    """
    Get system health from Unified Tick Pipeline
    
    Returns:
        Dict containing system health information
    """
    try:
        if not _pipeline_initialized or not _pipeline:
            return {"error": "Unified Tick Pipeline not initialized"}
        
        # Get system health
        system_health = _pipeline.get_system_health()
        
        # Get pipeline status
        pipeline_status = await _pipeline.get_pipeline_status()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system_health": system_health,
            "pipeline_status": pipeline_status,
            "health_type": "unified_pipeline"
        }
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return {"error": str(e)}

async def get_pipeline_status() -> Dict[str, Any]:
    """
    Get Unified Tick Pipeline status
    
    Returns:
        Dict containing pipeline status
    """
    try:
        if not _pipeline_initialized or not _pipeline:
            return {"error": "Unified Tick Pipeline not initialized"}
        
        # Get pipeline status
        pipeline_status = await _pipeline.get_pipeline_status()
        
        # Get integration status
        integration_status = _pipeline.get_integration_status()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "pipeline_status": pipeline_status,
            "integration_status": integration_status,
            "status_type": "unified_pipeline"
        }
        
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        return {"error": str(e)}

async def get_multi_timeframe_analysis(symbol: str, timeframes: List[str] = None) -> Dict[str, Any]:
    """
    Get multi-timeframe analysis from Unified Tick Pipeline
    
    Args:
        symbol: Trading symbol
        timeframes: List of timeframes to analyze
        
    Returns:
        Dict containing multi-timeframe analysis
    """
    try:
        if not _pipeline_initialized or not _pipeline:
            return {"error": "Unified Tick Pipeline not initialized"}
        
        if timeframes is None:
            timeframes = ["M1", "M5", "M15", "H1", "H4"]
        
        # Get data for each timeframe
        timeframe_data = {}
        for tf in timeframes:
            try:
                # Get tick data for the timeframe
                tick_data = _pipeline.get_latest_ticks(symbol, 100)
                timeframe_data[tf] = {
                    "tick_count": len(tick_data) if tick_data else 0,
                    "latest_tick": tick_data[-1] if tick_data else None
                }
            except Exception as e:
                timeframe_data[tf] = {"error": str(e)}
        
        # Get M5 volatility data
        m5_data = None
        if hasattr(_pipeline, 'm5_volatility_bridge'):
            m5_data = _pipeline.m5_volatility_bridge.get_volatility_data(symbol)
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "timeframes": timeframe_data,
            "m5_volatility": m5_data,
            "analysis_type": "multi_timeframe"
        }
        
    except Exception as e:
        logger.error(f"Error getting multi-timeframe analysis for {symbol}: {e}")
        return {"error": str(e)}

async def get_real_time_ticks(symbol: str, limit: int = 50) -> Dict[str, Any]:
    """
    Get real-time tick data from Unified Tick Pipeline
    
    Args:
        symbol: Trading symbol
        limit: Number of ticks to return
        
    Returns:
        Dict containing real-time tick data
    """
    try:
        if not _pipeline_initialized or not _pipeline:
            return {"error": "Unified Tick Pipeline not initialized"}
        
        # Get real-time tick data
        tick_data = _pipeline.get_latest_ticks(symbol, limit)
        
        # Get system health for context
        system_health = _pipeline.get_system_health()
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "tick_data": tick_data,
            "tick_count": len(tick_data) if tick_data else 0,
            "system_health": system_health,
            "data_type": "real_time_ticks"
        }
        
    except Exception as e:
        logger.error(f"Error getting real-time ticks for {symbol}: {e}")
        return {"error": str(e)}

async def get_enhanced_symbol_analysis(symbol: str) -> Dict[str, Any]:
    """
    Get enhanced symbol analysis from Unified Tick Pipeline
    
    Args:
        symbol: Trading symbol
        
    Returns:
        Dict containing enhanced symbol analysis
    """
    try:
        if not _pipeline_initialized or not _pipeline:
            return {"error": "Unified Tick Pipeline not initialized"}
        
        # Get real-time tick data
        tick_data = _pipeline.get_latest_ticks(symbol, 100)
        
        # Get M5 volatility data
        m5_data = None
        if hasattr(_pipeline, 'm5_volatility_bridge'):
            m5_data = _pipeline.m5_volatility_bridge.get_volatility_data(symbol)
        
        # Get offset calibration data
        offset_data = None
        if hasattr(_pipeline, 'offset_calibrator'):
            offset_data = _pipeline.offset_calibrator.get_calibration_data(symbol)
        
        # Get system health
        system_health = _pipeline.get_system_health()
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "tick_data": tick_data,
            "m5_volatility": m5_data,
            "offset_calibration": offset_data,
            "system_health": system_health,
            "analysis_type": "enhanced_symbol"
        }
        
    except Exception as e:
        logger.error(f"Error getting enhanced symbol analysis for {symbol}: {e}")
        return {"error": str(e)}

# ============================================================================
# INTEGRATION STATUS
# ============================================================================

def get_integration_status() -> Dict[str, Any]:
    """Get the integration status"""
    return {
        "is_initialized": _pipeline_initialized,
        "pipeline_available": _pipeline is not None,
        "integration_type": "main_api_unified_pipeline",
        "timestamp": datetime.now().isoformat()
    }
