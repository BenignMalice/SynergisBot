"""
Unified Tick Pipeline Integration for ChatGPT Bot
Integrates the Unified Tick Pipeline with the existing ChatGPT bot infrastructure
"""

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import os
from pathlib import Path

# Import the Unified Tick Pipeline
from unified_tick_pipeline.core.pipeline_manager import UnifiedTickPipeline

logger = logging.getLogger(__name__)

class UnifiedTickPipelineIntegration:
    """
    Integration layer between Unified Tick Pipeline and ChatGPT Bot
    
    Features:
    - Initializes and manages the Unified Tick Pipeline
    - Provides data access for ChatGPT analysis
    - Integrates with existing bot infrastructure
    - Handles error recovery and monitoring
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.pipeline: Optional[UnifiedTickPipeline] = None
        self.is_running = False
        self.background_thread: Optional[threading.Thread] = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Integration status
        self.integration_status = {
            'pipeline_initialized': False,
            'data_feeds_active': False,
            'database_connected': False,
            'error_count': 0,
            'last_error': None,
            'startup_time': None
        }
        
        logger.info("UnifiedTickPipelineIntegration initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for the integration"""
        return {
            'pipeline': {
                'binance': {
                    'symbols': ['BTCUSDT', 'ETHUSDT'],  # Removed XAUUSDT - not available on Binance
                    'primary_ws_url': 'wss://stream.binance.com:9443/stream?streams=',
                    'mirror_ws_url': 'wss://stream.binance.com:9443/stream?streams=',
                    'heartbeat_interval': 30,
                    'reconnect_delay': 5,
                    'max_reconnect_attempts': 10
                },
                'mt5': {
                    'symbols': ['EURUSDc', 'GBPUSDc', 'USDJPYc', 'GBPJPYc', 'EURJPYc', 'AUDUSDc', 'USDCADc', 'NZDUSDc', 'USDCHFc', 'AUDCADc', 'AUDCHFc', 'AUDJPYc', 'AUDNZDc', 'CADCHFc', 'CADJPYc', 'CHFJPYc', 'EURAUDc', 'EURCADc', 'EURCHFc', 'EURGBPc', 'EURNZDc', 'GBPAUDc', 'GBPCADc', 'GBPCHFc', 'GBPNZDc', 'NZDCADc', 'NZDCHFc', 'NZDJPYc', 'XAUUSDc'],  # Added XAUUSDc
                    'timeout': 10000,
                    'timeframes': ['M1', 'M5', 'M15', 'H1', 'H4'],
                    'update_interval': 1
                },
                'offset': {
                    'calibration_interval': 60,
                    'atr_threshold': 0.5,
                    'max_offset': 10.0,
                    'drift_threshold': 2.0,
                    'm5_structure_weight': 0.3,
                    'min_samples_for_calibration': 3,
                    'time_alignment_window': 30
                },
                'm5_volatility': {
                    'high_vol_threshold': 0.3,
                    'structure_weight': 0.4,
                    'volume_weight': 0.3,
                    'price_weight': 0.7,
                    'fusion_window': 300,
                    'volatility_periods': 14
                },
                'dtms_enhancement': {
                    'reevaluation_interval': 3,
                    'conflict_resolution': {
                        'adjust_stop_loss': 'dtms_override',
                        'adjust_take_profit': 'intelligent_exits_override',
                        'hedge_position': 'dtms_override',
                        'partial_close': 'intelligent_exits_override',
                        'trailing_stop': 'intelligent_exits_override'
                    },
                    'override_conditions': [
                        'emergency_stop_loss',
                        'high_volatility_stop',
                        'profit_target_reached',
                        'volatility_spike',
                        'structure_break',
                        'high_volatility_hedge',
                        'risk_reduction',
                        'trend_continuation',
                        'volatility_expansion'
                    ]
                },
                'chatgpt_integration': {
                    'default_access_level': 'read_only',
                    'authorization_timeout': 300,
                    'max_analysis_history': 1000,
                    'timeframe_data_retention': 24,
                    'analysis_engines': {
                        'market_structure': True,
                        'volatility_analysis': True,
                        'trend_analysis': True,
                        'support_resistance': True,
                        'momentum_analysis': True,
                        'risk_assessment': True
                    },
                    'parameter_change_authorization': {
                        'require_manual_approval': True,
                        'notification_method': 'telegram',
                        'approval_timeout': 600
                    }
                },
                'system_coordination': {
                    'resource_monitoring_interval': 5,
                    'task_processing_interval': 0.1,
                    'health_monitoring_interval': 30,
                    'resource_thresholds': {
                        'cpu_high': 80.0,
                        'cpu_critical': 95.0,
                        'memory_high': 85.0,
                        'memory_critical': 95.0,
                        'disk_high': 90.0,
                        'disk_critical': 98.0
                    },
                    'thread_limits': {
                        'critical': 4,
                        'high': 8,
                        'medium': 12,
                        'low': 6,
                        'deferred': 4
                    },
                    'defer_conditions': [
                        'cpu_high',
                        'memory_high',
                        'disk_high',
                        'network_issues'
                    ]
                },
                'performance_optimization': {
                    'optimization_level': 'balanced',
                    'enable_memory_tracking': True,
                    'sleep_detection_enabled': True,
                    'gap_fill_enabled': True,
                    'max_gap_duration_minutes': 30,
                    'cache_cleanup_threshold': 1000,
                    'memory_thresholds': {
                        'high': 80.0,
                        'critical': 90.0,
                        'recovery': 70.0
                    },
                    'cpu_thresholds': {
                        'high': 80.0,
                        'critical': 95.0
                    },
                    'optimization_intervals': {
                        'aggressive': 30,
                        'balanced': 60,
                        'conservative': 120
                    }
                },
                'database_integration': {
                    'database_path': 'data/unified_tick_pipeline',
                    'connection_pool_size': 10,
                    'query_timeout': 30,
                    'batch_size': 1000,
                    'cache_size': 10000,
                    'wal_mode': True,
                    'retention_policies': {
                        'tick_data': 7,
                        'm5_candles': 30,
                        'dtms_actions': 90,
                        'chatgpt_analysis': 30,
                        'system_metrics': 7,
                        'performance_logs': 14
                    },
                    'optimization': {
                        'enable_indexes': True,
                        'enable_vacuum': True,
                        'enable_analyze': True,
                        'enable_reindex': True
                    }
                },
                'data_access_layer': {
                    'database_path': 'data/unified_tick_pipeline',
                    'cache_ttl': 300,
                    'max_cache_size': 1000,
                    'query_timeout': 30,
                    'access_controls': {
                        'chatgpt': 'read_only',
                        'dtms': 'read_write',
                        'intelligent_exits': 'read_write',
                        'system': 'system',
                        'admin': 'admin'
                    },
                    'performance_monitoring': {
                        'enable_query_logging': True,
                        'enable_performance_tracking': True,
                        'enable_cache_monitoring': True
                    }
                },
                'data_retention': {
                    'tick_buffer_size': 10000,
                    'compression_threshold': 1000,
                    'retention_hours': 24,
                    'archive_format': 'parquet'
                },
                'mt5_m1_streaming': {
                    'symbols': ['EURUSDc', 'GBPUSDc', 'USDJPYc', 'GBPJPYc', 'EURJPYc', 'AUDUSDc', 'USDCADc', 'NZDUSDc', 'USDCHFc', 'AUDCADc', 'AUDCHFc', 'AUDJPYc', 'AUDNZDc', 'CADCHFc', 'CADJPYc', 'CHFJPYc', 'EURAUDc', 'EURCADc', 'EURCHFc', 'EURGBPc', 'EURNZDc', 'GBPAUDc', 'GBPCADc', 'GBPCHFc', 'GBPNZDc', 'NZDCADc', 'NZDCHFc', 'NZDJPYc', 'XAUUSDc'],
                    'update_interval': 1,
                    'buffer_size': 100,
                    'enable_volatility_analysis': True,
                    'enable_structure_analysis': True
                },
                'mt5_optimized_data_access': {
                    'symbols': ['EURUSDc', 'GBPUSDc', 'USDJPYc', 'GBPJPYc', 'EURJPYc', 'AUDUSDc', 'USDCADc', 'NZDUSDc', 'USDCHFc', 'AUDCADc', 'AUDCHFc', 'AUDJPYc', 'AUDNZDc', 'CADCHFc', 'CADJPYc', 'CHFJPYc', 'EURAUDc', 'EURCADc', 'EURCHFc', 'EURGBPc', 'EURNZDc', 'GBPAUDc', 'GBPCADc', 'GBPCHFc', 'GBPNZDc', 'NZDCADc', 'NZDCHFc', 'NZDJPYc', 'XAUUSDc'],
                    'cache_ttl_minutes': 15,
                    'max_cache_size': 1000,
                    'enable_smart_polling': True,
                    'on_demand_timeframes': ['M5', 'M15', 'M30', 'H1', 'H4']
                }
            },
            'integration': {
                'startup_timeout': 30,
                'health_check_interval': 60,
                'error_recovery_attempts': 3,
                'background_thread_daemon': True,
                'enable_monitoring': True
            }
        }
    
    async def initialize(self) -> bool:
        """Initialize the Unified Tick Pipeline integration"""
        try:
            logger.info("🔧 Initializing Unified Tick Pipeline integration...")
            
            # Create pipeline instance
            self.pipeline = UnifiedTickPipeline(self.config['pipeline'])
            
            # Start pipeline in background thread
            await self._start_pipeline_background()
            
            # Wait for initialization
            await self._wait_for_initialization()
            
            # Verify integration
            if await self._verify_integration():
                self.integration_status['pipeline_initialized'] = True
                self.integration_status['startup_time'] = datetime.now(timezone.utc)
                logger.info("✅ Unified Tick Pipeline integration initialized successfully")
                return True
            else:
                logger.error("❌ Unified Tick Pipeline integration verification failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Unified Tick Pipeline integration: {e}")
            self.integration_status['error_count'] += 1
            self.integration_status['last_error'] = str(e)
            return False
    
    async def _start_pipeline_background(self):
        """Start the pipeline in a background thread"""
        try:
            def run_pipeline():
                """Run the pipeline in a new event loop"""
                self.event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.event_loop)
                
                try:
                    # Start the pipeline
                    self.event_loop.run_until_complete(self.pipeline.start_pipeline())
                    
                    # Keep the loop running
                    self.event_loop.run_forever()
                    
                except Exception as e:
                    logger.error(f"❌ Error in pipeline background thread: {e}")
                    self.integration_status['error_count'] += 1
                    self.integration_status['last_error'] = str(e)
            
            # Start background thread
            self.background_thread = threading.Thread(
                target=run_pipeline,
                daemon=self.config['integration']['background_thread_daemon']
            )
            self.background_thread.start()
            
            logger.info("✅ Unified Tick Pipeline started in background thread")
            
        except Exception as e:
            logger.error(f"❌ Error starting pipeline background thread: {e}")
            raise
    
    async def _wait_for_initialization(self):
        """Wait for pipeline initialization to complete"""
        try:
            timeout = self.config['integration']['startup_timeout']
            start_time = datetime.now(timezone.utc)
            
            while (datetime.now(timezone.utc) - start_time).total_seconds() < timeout:
                if self.pipeline and self.pipeline.is_running:
                    logger.info("✅ Unified Tick Pipeline is running")
                    return
                
                await asyncio.sleep(1)
            
            raise Exception(f"Pipeline initialization timeout after {timeout} seconds")
            
        except Exception as e:
            logger.error(f"❌ Error waiting for pipeline initialization: {e}")
            raise
    
    async def _verify_integration(self) -> bool:
        """Verify that the integration is working correctly"""
        try:
            if not self.pipeline:
                return False
            
            # Check pipeline status
            status = self.pipeline.get_status()
            
            # Verify key components
            components = status.get('components', {})
            
            # Check database integration
            db_integration = components.get('database_integration', {})
            if not db_integration.get('is_active', False):
                logger.warning("⚠️ Database integration not active")
                return False
            
            # Check data access layer
            data_access = components.get('data_access_layer', {})
            if not data_access.get('is_active', False):
                logger.warning("⚠️ Data access layer not active")
                return False
            
            # Check system coordination
            system_coordination = components.get('system_coordination', {})
            if not system_coordination.get('is_active', False):
                logger.warning("⚠️ System coordination not active")
                return False
            
            self.integration_status['data_feeds_active'] = True
            self.integration_status['database_connected'] = True
            
            logger.info("✅ Integration verification completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error verifying integration: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the Unified Tick Pipeline integration"""
        try:
            logger.info("🛑 Stopping Unified Tick Pipeline integration...")
            
            if self.pipeline:
                await self.pipeline.stop_pipeline()
            
            if self.event_loop and not self.event_loop.is_closed():
                self.event_loop.stop()
            
            if self.background_thread and self.background_thread.is_alive():
                self.background_thread.join(timeout=10)
            
            self.is_running = False
            logger.info("✅ Unified Tick Pipeline integration stopped")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping Unified Tick Pipeline integration: {e}")
            return False
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get the current pipeline status"""
        try:
            if not self.pipeline:
                return {'error': 'Pipeline not initialized'}
            
            status = self.pipeline.get_status()
            return status
            
        except Exception as e:
            logger.error(f"❌ Error getting pipeline status: {e}")
            return {'error': str(e)}
    
    async def get_tick_data(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get tick data for a symbol"""
        try:
            if not self.pipeline:
                return {'error': 'Pipeline not initialized'}
            
            # Get data from pipeline
            tick_data = self.pipeline.get_latest_ticks(symbol, limit)
            return {'success': True, 'data': tick_data}
            
        except Exception as e:
            logger.error(f"❌ Error getting tick data for {symbol}: {e}")
            return {'error': str(e)}
    
    async def get_m5_candles(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get M5 candles for a symbol"""
        try:
            if not self.pipeline:
                return {'error': 'Pipeline not initialized'}
            
            # Get M5 data from volatility bridge
            m5_data = self.pipeline.m5_volatility_bridge.get_status()
            return {'success': True, 'data': m5_data}
            
        except Exception as e:
            logger.error(f"❌ Error getting M5 candles for {symbol}: {e}")
            return {'error': str(e)}
    
    async def get_volatility_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get volatility analysis for a symbol"""
        try:
            if not self.pipeline:
                return {'error': 'Pipeline not initialized'}
            
            # Get volatility data
            volatility_score = self.pipeline.m5_volatility_bridge.get_volatility_score(symbol)
            is_high_vol = self.pipeline.m5_volatility_bridge.is_high_volatility(symbol)
            
            return {
                'success': True,
                'data': {
                    'symbol': symbol,
                    'volatility_score': volatility_score,
                    'is_high_volatility': is_high_vol,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting volatility analysis for {symbol}: {e}")
            return {'error': str(e)}
    
    async def get_offset_calibration(self, symbol: str) -> Dict[str, Any]:
        """Get offset calibration data for a symbol"""
        try:
            if not self.pipeline:
                return {'error': 'Pipeline not initialized'}
            
            # Get offset data
            offset_value = self.pipeline.offset_calibrator.get_offset(symbol)
            atr = self.pipeline.offset_calibrator.get_atr(symbol)
            within_threshold = self.pipeline.offset_calibrator.is_offset_within_threshold(symbol, offset_value)
            
            return {
                'success': True,
                'data': {
                    'symbol': symbol,
                    'offset': offset_value,
                    'confidence': 1.0,  # Default confidence
                    'atr': atr,
                    'within_threshold': within_threshold,
                    'last_calibration': datetime.now(timezone.utc).isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting offset calibration for {symbol}: {e}")
            return {'error': str(e)}
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get system health status"""
        try:
            if not self.pipeline:
                return {'error': 'Pipeline not initialized'}
            
            # Get system coordination status
            system_status = self.pipeline.system_coordination.get_status()
            
            # Get performance optimization status
            perf_status = self.pipeline.performance_optimization.get_status()
            
            return {
                'success': True,
                'data': {
                    'system_coordination': system_status,
                    'performance_optimization': perf_status,
                    'integration_status': self.integration_status,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting system health: {e}")
            return {'error': str(e)}
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status"""
        return {
            'is_running': self.is_running,
            'pipeline_initialized': self.integration_status['pipeline_initialized'],
            'data_feeds_active': self.integration_status['data_feeds_active'],
            'database_connected': self.integration_status['database_connected'],
            'error_count': self.integration_status['error_count'],
            'last_error': self.integration_status['last_error'],
            'startup_time': self.integration_status['startup_time'].isoformat() if self.integration_status['startup_time'] else None,
            'background_thread_alive': self.background_thread.is_alive() if self.background_thread else False
        }

# Global instance for bot integration
unified_pipeline_integration: Optional[UnifiedTickPipelineIntegration] = None

async def initialize_unified_pipeline() -> bool:
    """Initialize the Unified Tick Pipeline for the bot"""
    global unified_pipeline_integration
    
    try:
        logger.info("🚀 Initializing Unified Tick Pipeline for ChatGPT Bot...")
        
        # Create integration instance
        unified_pipeline_integration = UnifiedTickPipelineIntegration()
        
        # Initialize the pipeline
        success = await unified_pipeline_integration.initialize()
        
        if success:
            logger.info("✅ Unified Tick Pipeline integration completed successfully")
            return True
        else:
            logger.error("❌ Unified Tick Pipeline integration failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error initializing Unified Tick Pipeline: {e}")
        return False

async def stop_unified_pipeline() -> bool:
    """Stop the Unified Tick Pipeline"""
    global unified_pipeline_integration
    
    try:
        if unified_pipeline_integration:
            return await unified_pipeline_integration.stop()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error stopping Unified Tick Pipeline: {e}")
        return False

def get_unified_pipeline() -> Optional[UnifiedTickPipelineIntegration]:
    """Get the Unified Tick Pipeline integration instance"""
    return unified_pipeline_integration

def get_pipeline_instance() -> Optional[UnifiedTickPipeline]:
    """Get the actual pipeline instance"""
    if unified_pipeline_integration and unified_pipeline_integration.pipeline:
        return unified_pipeline_integration.pipeline
    return None
