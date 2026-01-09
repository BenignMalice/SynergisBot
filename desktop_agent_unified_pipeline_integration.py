"""
Desktop Agent Unified Pipeline Integration
Enhanced desktop agent with Unified Tick Pipeline data feeds
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from unified_tick_pipeline_integration import get_unified_pipeline, get_pipeline_instance

logger = logging.getLogger(__name__)

class DesktopAgentUnifiedPipelineIntegration:
    """
    Enhanced Desktop Agent integration with Unified Tick Pipeline
    
    Features:
    - Real-time data from Unified Tick Pipeline
    - Multi-timeframe analysis integration
    - Enhanced volatility monitoring
    - Offset calibration integration
    - System coordination integration
    """
    
    def __init__(self):
        self.pipeline = None
        self.is_active = False
        
        # Desktop Agent state
        self.performance_metrics = {
            'analysis_requests': 0,
            'volatility_checks': 0,
            'offset_checks': 0,
            'system_health_checks': 0,
            'error_count': 0
        }
        
        logger.info("DesktopAgentUnifiedPipelineIntegration initialized")
    
    async def initialize(self) -> bool:
        """Initialize Desktop Agent with Unified Tick Pipeline"""
        try:
            logger.info("🔧 Initializing Desktop Agent with Unified Tick Pipeline...")
            
            # Get the unified pipeline (try both methods)
            self.pipeline = get_unified_pipeline() or get_pipeline_instance()
            if not self.pipeline:
                logger.error("❌ Unified Tick Pipeline not available")
                return False
            
            self.is_active = True
            logger.info("✅ Desktop Agent Unified Pipeline integration initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Desktop Agent Unified Pipeline integration: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop Desktop Agent integration"""
        try:
            logger.info("🛑 Stopping Desktop Agent Unified Pipeline integration...")
            self.is_active = False
            logger.info("✅ Desktop Agent Unified Pipeline integration stopped")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping Desktop Agent Unified Pipeline integration: {e}")
            return False
    
    # Enhanced analysis tools
    async def get_enhanced_symbol_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get enhanced symbol analysis using Unified Tick Pipeline data"""
        try:
            if not self.pipeline:
                return {'error': 'Unified Tick Pipeline not available'}
            
            # Get latest tick data
            tick_data = await self.pipeline.get_tick_data(symbol, limit=1)
            if not tick_data.get('success'):
                return {'error': 'Failed to get tick data'}
            
            # Get volatility analysis
            volatility_data = await self.pipeline.get_volatility_analysis(symbol)
            volatility_info = volatility_data.get('data', {}) if volatility_data.get('success') else {}
            
            # Get offset calibration
            offset_data = await self.pipeline.get_offset_calibration(symbol)
            offset_info = offset_data.get('data', {}) if offset_data.get('success') else {}
            
            # Get M5 candles
            m5_data = await self.pipeline.get_m5_candles(symbol, limit=10)
            m5_info = m5_data.get('data', []) if m5_data.get('success') else []
            
            # Get system health
            health_data = await self.pipeline.get_system_health()
            health_info = health_data.get('data', {}) if health_data.get('success') else {}
            
            # Compile enhanced analysis
            analysis = {
                'symbol': symbol,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'tick_data': tick_data.get('data', [])[0] if tick_data.get('data') else {},
                'volatility': volatility_info,
                'offset_calibration': offset_info,
                'm5_candles': m5_info,
                'system_health': health_info,
                'enhanced_features': {
                    'real_time_data': True,
                    'volatility_monitoring': volatility_info.get('is_high_volatility', False),
                    'offset_within_threshold': offset_info.get('within_threshold', True),
                    'system_status': health_info.get('system_coordination', {}).get('current_state', 'unknown')
                }
            }
            
            self.performance_metrics['analysis_requests'] += 1
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error getting enhanced symbol analysis for {symbol}: {e}")
            self.performance_metrics['error_count'] += 1
            return {'error': str(e)}
    
    async def get_volatility_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get volatility analysis for a symbol"""
        try:
            if not self.pipeline:
                return {'error': 'Unified Tick Pipeline not available'}
            
            volatility_data = await self.pipeline.get_volatility_analysis(symbol)
            if volatility_data.get('success'):
                self.performance_metrics['volatility_checks'] += 1
                return volatility_data
            else:
                return {'error': 'Failed to get volatility analysis'}
                
        except Exception as e:
            logger.error(f"❌ Error getting volatility analysis for {symbol}: {e}")
            self.performance_metrics['error_count'] += 1
            return {'error': str(e)}
    
    async def get_offset_calibration(self, symbol: str) -> Dict[str, Any]:
        """Get offset calibration for a symbol"""
        try:
            if not self.pipeline:
                return {'error': 'Unified Tick Pipeline not available'}
            
            offset_data = await self.pipeline.get_offset_calibration(symbol)
            if offset_data.get('success'):
                self.performance_metrics['offset_checks'] += 1
                return offset_data
            else:
                return {'error': 'Failed to get offset calibration'}
                
        except Exception as e:
            logger.error(f"❌ Error getting offset calibration for {symbol}: {e}")
            self.performance_metrics['error_count'] += 1
            return {'error': str(e)}
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get system health status"""
        try:
            if not self.pipeline:
                return {'error': 'Unified Tick Pipeline not available'}
            
            health_data = await self.pipeline.get_system_health()
            if health_data.get('success'):
                self.performance_metrics['system_health_checks'] += 1
                return health_data
            else:
                return {'error': 'Failed to get system health'}
                
        except Exception as e:
            logger.error(f"❌ Error getting system health: {e}")
            self.performance_metrics['error_count'] += 1
            return {'error': str(e)}
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get Unified Tick Pipeline status"""
        try:
            if not self.pipeline:
                return {'error': 'Unified Tick Pipeline not available'}
            
            status_data = self.pipeline.get_pipeline_status()
            return status_data
            
        except Exception as e:
            logger.error(f"❌ Error getting pipeline status: {e}")
            self.performance_metrics['error_count'] += 1
            return {'error': str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get Desktop Agent integration status"""
        return {
            'is_active': self.is_active,
            'pipeline_available': self.pipeline is not None,
            'performance_metrics': self.performance_metrics
        }

# Global instance
_desktop_agent_unified_integration: Optional[DesktopAgentUnifiedPipelineIntegration] = None

async def initialize_desktop_agent_unified_pipeline() -> bool:
    """Initialize Desktop Agent with Unified Tick Pipeline"""
    global _desktop_agent_unified_integration
    
    try:
        logger.info("🚀 Initializing Desktop Agent with Unified Tick Pipeline...")
        
        _desktop_agent_unified_integration = DesktopAgentUnifiedPipelineIntegration()
        success = await _desktop_agent_unified_integration.initialize()
        
        if success:
            logger.info("✅ Desktop Agent Unified Pipeline integration completed successfully")
            return True
        else:
            logger.error("❌ Desktop Agent Unified Pipeline integration failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error initializing Desktop Agent Unified Pipeline: {e}")
        return False

async def stop_desktop_agent_unified_pipeline() -> bool:
    """Stop Desktop Agent Unified Pipeline integration"""
    global _desktop_agent_unified_integration
    
    try:
        if _desktop_agent_unified_integration:
            return await _desktop_agent_unified_integration.stop()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error stopping Desktop Agent Unified Pipeline: {e}")
        return False

def get_desktop_agent_unified_integration() -> Optional[DesktopAgentUnifiedPipelineIntegration]:
    """Get the Desktop Agent Unified Pipeline integration instance"""
    return _desktop_agent_unified_integration

# Enhanced Desktop Agent tools that use the Unified Pipeline
async def tool_enhanced_symbol_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced symbol analysis using Unified Tick Pipeline data"""
    integration = get_desktop_agent_unified_integration()
    if not integration:
        return {'error': 'Desktop Agent Unified Pipeline integration not available'}
    
    symbol = args.get('symbol')
    if not symbol:
        return {'error': 'Symbol is required'}
    
    analysis = await integration.get_enhanced_symbol_analysis(symbol)
    return analysis

async def tool_volatility_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get volatility analysis using Unified Tick Pipeline data"""
    integration = get_desktop_agent_unified_integration()
    if not integration:
        return {'error': 'Desktop Agent Unified Pipeline integration not available'}
    
    symbol = args.get('symbol')
    if not symbol:
        return {'error': 'Symbol is required'}
    
    analysis = await integration.get_volatility_analysis(symbol)
    return analysis

async def tool_offset_calibration(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get offset calibration using Unified Tick Pipeline data"""
    integration = get_desktop_agent_unified_integration()
    if not integration:
        return {'error': 'Desktop Agent Unified Pipeline integration not available'}
    
    symbol = args.get('symbol')
    if not symbol:
        return {'error': 'Symbol is required'}
    
    calibration = await integration.get_offset_calibration(symbol)
    return calibration

async def tool_system_health(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get system health using Unified Tick Pipeline data"""
    integration = get_desktop_agent_unified_integration()
    if not integration:
        return {'error': 'Desktop Agent Unified Pipeline integration not available'}
    
    health = await integration.get_system_health()
    return health

async def tool_pipeline_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get Unified Tick Pipeline status"""
    integration = get_desktop_agent_unified_integration()
    if not integration:
        return {'error': 'Desktop Agent Unified Pipeline integration not available'}
    
    status = integration.get_pipeline_status()
    return status

async def tool_dtms_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get DTMS system status"""
    integration = get_desktop_agent_unified_integration()
    
    # Try unified pipeline first
    if integration and integration.pipeline:
        try:
            from dtms_unified_pipeline_integration import get_dtms_unified_integration
            dtms_integration = get_dtms_unified_integration()
            if dtms_integration:
                status = dtms_integration.get_status()
                return {
                    'success': True,
                    'data': status
                }
        except Exception as e:
            logger.warning(f"DTMS unified pipeline not available, falling back to API: {e}")
    
    # Fallback to API endpoints (accessible via ngrok)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try main API server first (port 8000 - accessible via ngrok)
            try:
                response = await client.get("http://127.0.0.1:8000/api/dtms/status")
                if response.status_code == 200:
                    api_data = response.json()
                    return {
                        "success": api_data.get("success", True),
                        "summary": api_data.get("summary", "DTMS status retrieved"),
                        "dtms_status": api_data.get("dtms_status", {}),
                        "error": api_data.get("error")
                    }
            except Exception:
                # Fallback to DTMS API server (port 8001 - local only)
                response = await client.get("http://127.0.0.1:8001/dtms/status")
                if response.status_code == 200:
                    api_data = response.json()
                    return {
                        "success": api_data.get("success", False),
                        "summary": api_data.get("summary", "DTMS status retrieved"),
                        "dtms_status": api_data.get("dtms_status", {}),
                        "error": api_data.get("error")
                    }
    except Exception as api_error:
        logger.warning(f"DTMS API not available, falling back to direct access: {api_error}")
    
    # Final fallback to direct access
    try:
        from dtms_integration import get_dtms_system_status
        status = get_dtms_system_status()
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
    except Exception as e:
        logger.error(f"DTMS direct access failed: {e}")
    
    return {'success': False, 'error': 'DTMS system not available'}

async def tool_dtms_trade_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get DTMS trade information"""
    ticket = args.get('ticket')
    if not ticket:
        return {
            "success": False,
            "summary": "Ticket number is required",
            "error": "Ticket number is required"
        }
    
    integration = get_desktop_agent_unified_integration()
    
    # Try unified pipeline first
    if integration and integration.pipeline:
        try:
            from dtms_unified_pipeline_integration import get_dtms_unified_integration
            dtms_integration = get_dtms_unified_integration()
            if dtms_integration:
                trade_info = dtms_integration.get_trade_status(ticket)
                if trade_info:
                    return {
                        'success': True,
                        'data': trade_info
                    }
        except Exception as e:
            logger.warning(f"DTMS unified pipeline not available, falling back to API: {e}")
    
    # Fallback to API endpoints (accessible via ngrok)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try main API server first (port 8000 - accessible via ngrok)
            try:
                response = await client.get(f"http://127.0.0.1:8000/api/dtms/trade/{ticket}")
                if response.status_code == 200:
                    api_data = response.json()
                    return {
                        "success": api_data.get("success", True),
                        "summary": api_data.get("summary", "DTMS trade info retrieved"),
                        "trade_info": api_data.get("trade_info"),
                        "error": api_data.get("error")
                    }
            except Exception:
                # Fallback to DTMS API server (port 8001 - local only)
                response = await client.get(f"http://127.0.0.1:8001/dtms/trade/{ticket}")
                if response.status_code == 200:
                    api_data = response.json()
                    return {
                        "success": api_data.get("success", False),
                        "summary": api_data.get("summary", "DTMS trade info retrieved"),
                        "trade_info": api_data.get("trade_info"),
                        "error": api_data.get("error")
                    }
    except Exception as api_error:
        logger.warning(f"DTMS API not available, falling back to direct access: {api_error}")
    
    # Final fallback to direct access
    try:
        from dtms_integration import get_dtms_trade_status
        trade_info = get_dtms_trade_status(int(ticket))
        if trade_info and not trade_info.get('error'):
            return {
                "success": True,
                "summary": f"Trade {ticket} is in {trade_info.get('state', 'Unknown')} state with score {trade_info.get('current_score', 0)}",
                "trade_info": {
                    "ticket": trade_info.get('ticket'),
                    "symbol": trade_info.get('symbol'),
                    "state": trade_info.get('state'),
                    "current_score": trade_info.get('current_score'),
                    "state_entry_time": trade_info.get('state_entry_time_human'),
                    "warnings": trade_info.get('warnings', {}),
                    "actions_taken": trade_info.get('actions_taken', []),
                    "performance": trade_info.get('performance', {})
                }
            }
    except Exception as e:
        logger.error(f"DTMS direct access failed: {e}")
    
    return {'success': False, 'error': 'DTMS trade info not available'}

async def tool_dtms_action_history(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get DTMS action history"""
    integration = get_desktop_agent_unified_integration()
    
    # Try unified pipeline first
    if integration and integration.pipeline:
        try:
            from dtms_unified_pipeline_integration import get_dtms_unified_integration
            dtms_integration = get_dtms_unified_integration()
            if dtms_integration:
                action_history = dtms_integration.get_action_history(args.get('ticket'))
                if action_history:
                    return {
                        'success': True,
                        'data': action_history
                    }
        except Exception as e:
            logger.warning(f"DTMS unified pipeline not available, falling back to API: {e}")
    
    # Fallback to API endpoints (accessible via ngrok)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try main API server first (port 8000 - accessible via ngrok)
            try:
                response = await client.get("http://127.0.0.1:8000/api/dtms/actions")
                if response.status_code == 200:
                    api_data = response.json()
                    return {
                        "success": api_data.get("success", True),
                        "summary": api_data.get("summary", "DTMS action history retrieved"),
                        "action_history": api_data.get("action_history", []),
                        "total_actions": api_data.get("total_actions", 0),
                        "error": api_data.get("error")
                    }
            except Exception:
                # Fallback to DTMS API server (port 8001 - local only)
                response = await client.get("http://127.0.0.1:8001/dtms/actions")
                if response.status_code == 200:
                    api_data = response.json()
                    return {
                        "success": api_data.get("success", False),
                        "summary": api_data.get("summary", "DTMS action history retrieved"),
                        "action_history": api_data.get("action_history", []),
                        "total_actions": api_data.get("total_actions", 0),
                        "error": api_data.get("error")
                    }
    except Exception as api_error:
        logger.warning(f"DTMS API not available, falling back to direct access: {api_error}")
    
    # Final fallback to direct access
    try:
        from dtms_integration import get_dtms_action_history
        history = get_dtms_action_history()
        if history:
            recent_actions = history[-10:] if len(history) > 10 else history
            return {
                "success": True,
                "summary": f"Retrieved {len(recent_actions)} recent DTMS actions from {len(history)} total actions",
                "action_history": [
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
                "total_actions": len(history)
            }
        else:
            return {
                "success": True,
                "summary": "No DTMS actions found in history",
                "action_history": [],
                "total_actions": 0
            }
    except Exception as e:
        logger.error(f"DTMS direct access failed: {e}")
    
    return {'success': False, 'error': 'DTMS action history not available'}
