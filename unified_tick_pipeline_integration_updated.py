"""
Updated Unified Tick Pipeline Integration for ChatGPT Bot
Uses separate database architecture to eliminate locking issues
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import os
from pathlib import Path

# Import the Unified Tick Pipeline
from unified_tick_pipeline.core.pipeline_manager import UnifiedTickPipeline

# Import the new database access manager
from database_access_manager import DatabaseAccessManager, initialize_database_manager

logger = logging.getLogger(__name__)

class UnifiedTickPipelineIntegrationUpdated:
    """
    Updated integration layer with separate database architecture
    
    Features:
    - Uses separate databases for each process type
    - ChatGPT Bot has WRITE access to main database
    - Desktop Agent has WRITE access to analysis database
    - API Server has WRITE access to logs database
    - Eliminates all database locking issues
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.pipeline: Optional[UnifiedTickPipeline] = None
        self.is_running = False
        self.background_thread: Optional[threading.Thread] = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Initialize database access manager for ChatGPT Bot
        self.db_manager = initialize_database_manager("chatgpt_bot")
        
        # Integration status
        self.integration_status = {
            'pipeline_initialized': False,
            'data_feeds_active': False,
            'database_connected': False,
            'error_count': 0,
            'last_error': None,
            'startup_time': None
        }
        
        logger.info("UnifiedTickPipelineIntegrationUpdated initialized with separate database architecture")
    
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for the integration with separate databases"""
        return {
            'pipeline': {
                'binance': {
                    'symbols': ['btcusdt', 'xauusd', 'eurusd', 'gbpusd', 'usdjpy', 'gbpjpy', 'eurjpy'],
                    'primary_ws_url': 'wss://stream.binance.com:9443/stream?streams=',
                    'mirror_ws_url': 'wss://stream.binance.com:9443/stream?streams=',
                    'heartbeat_interval': 30,
                    'reconnect_delay': 5,
                    'max_reconnect_attempts': 10
                },
                'mt5': {
                    'symbols': ['EURUSDc', 'GBPUSDc', 'USDJPYc', 'GBPJPYc', 'EURJPYc', 'AUDUSDc', 'USDCADc', 'NZDUSDc', 'USDCHFc', 'AUDCADc', 'AUDCHFc', 'AUDJPYc', 'AUDNZDc', 'CADCHFc', 'CADJPYc', 'CHFJPYc', 'EURAUDc', 'EURCADc', 'EURCHFc', 'EURGBPc', 'EURNZDc', 'GBPAUDc', 'GBPCADc', 'GBPCHFc', 'GBPNZDc', 'NZDCADc', 'NZDCHFc', 'NZDJPYc', 'XAUUSDc'],
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
                        'risk_reduction'
                    ]
                },
                'intelligent_exits': {
                    'atr_multiplier': 2.0,
                    'vix_threshold': 25.0,
                    'volatility_gating': True,
                    'trailing_stop_activation': 0.5,
                    'partial_close_thresholds': [0.3, 0.6, 0.8],
                    'dynamic_stop_adjustment': True
                },
                'chatgpt_integration': {
                    'analysis_interval': 30,
                    'multi_timeframe_analysis': True,
                    'timeframes': ['M1', 'M5', 'M15', 'H1', 'H4'],
                    'read_only_default': True,
                    'manual_authorization_required': True,
                    'real_time_data_access': True,
                    'enhanced_analysis_capabilities': True
                },
                'system_coordination': {
                    'hierarchical_control_matrix': True,
                    'thread_prioritization': True,
                    'deferred_analysis': True,
                    'resource_management': True,
                    'system_health_monitoring': True
                },
                'performance_optimization': {
                    'memory_management': True,
                    'cpu_usage_optimization': True,
                    'sleep_recovery_engine': True,
                    'gap_fill_logic': True,
                    'resource_optimization': True
                }
            },
            'database_integration': {
                'main_database_path': 'unified_tick_pipeline.db',
                'analysis_database_path': 'analysis_data.db',
                'logs_database_path': 'system_logs.db',
                'connection_pool_size': 10,
                'query_timeout': 30,
                'batch_size': 1000,
                'cache_size': 10000,
                'wal_mode': True,
                'synchronous_mode': 'NORMAL',
                'busy_timeout': 60000,
                'cache_size_mb': 20,
                'temp_store': 'MEMORY',
                'foreign_keys': True,
                'wal_autocheckpoint': 1000,
                'journal_size_limit': 10000000,
                'performance_optimization': {
                    'enable_analyze': True,
                    'enable_reindex': True
                }
            },
            'data_access_layer': {
                'main_database_path': 'unified_tick_pipeline.db',
                'analysis_database_path': 'analysis_data.db',
                'logs_database_path': 'system_logs.db',
                'cache_ttl': 300,
                'max_cache_size': 1000,
                'query_timeout': 30,
                'access_controls': {
                    'chatgpt_bot': {
                        'main_db': 'write',
                        'analysis_db': 'read',
                        'logs_db': 'read'
                    },
                    'desktop_agent': {
                        'main_db': 'read',
                        'analysis_db': 'write',
                        'logs_db': 'read'
                    },
                    'api_server': {
                        'main_db': 'read',
                        'analysis_db': 'read',
                        'logs_db': 'write'
                    }
                }
            }
        }
    
    async def initialize_pipeline(self) -> bool:
        """Initialize the Unified Tick Pipeline with separate database architecture."""
        try:
            logger.info("🚀 Initializing Unified Tick Pipeline with separate database architecture...")
            
            # Test database access first
            if not self._test_database_access():
                logger.error("❌ Database access test failed")
                return False
            
            # Initialize the pipeline using its internal defaults to ensure all
            # required sub-configs (binance, mt5, data_retention, etc.) are present
            # and correctly shaped. We avoid passing a partial dict that could
            # omit required fields expected by dataclass configs.
            self.pipeline = UnifiedTickPipeline()
            
            # Start the pipeline
            await self.pipeline.start_pipeline()
            
            # Verify integration
            if not self._verify_integration():
                logger.error("❌ Integration verification failed")
                return False
            
            self.integration_status['pipeline_initialized'] = True
            self.integration_status['startup_time'] = datetime.now(timezone.utc)
            
            logger.info("✅ Unified Tick Pipeline initialized successfully with separate database architecture")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize pipeline: {e}")
            self.integration_status['error_count'] += 1
            self.integration_status['last_error'] = str(e)
            return False
    
    def _test_database_access(self) -> bool:
        """Test database access for ChatGPT Bot."""
        try:
            logger.info("🧪 Testing database access for ChatGPT Bot...")
            
            # Test main database (WRITE access)
            with self.db_manager.get_main_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM unified_ticks")
                count = cursor.fetchone()[0]
                logger.info(f"✅ Main database accessible: {count} ticks")
            
            # Test analysis database (READ access)
            with self.db_manager.get_analysis_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM analysis_results")
                count = cursor.fetchone()[0]
                logger.info(f"✅ Analysis database accessible: {count} analysis results")
            
            # Test logs database (READ access)
            with self.db_manager.get_logs_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM api_logs")
                count = cursor.fetchone()[0]
                logger.info(f"✅ Logs database accessible: {count} log entries")
            
            logger.info("✅ All database access tests passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database access test failed: {e}")
            return False
    
    def _verify_integration(self) -> bool:
        """Verify the integration is working correctly."""
        try:
            if not self.pipeline:
                logger.error("❌ Pipeline not initialized")
                return False
            
            # Get pipeline status
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
            logger.error(f"❌ Integration verification failed: {e}")
            return False
    
    def start_background_processing(self):
        """Start background processing in a separate thread."""
        if self.background_thread and self.background_thread.is_alive():
            logger.warning("⚠️ Background thread already running")
            return
        
        def background_worker():
            """Background worker function."""
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run the pipeline
                loop.run_until_complete(self._background_pipeline_loop())
                
            except Exception as e:
                logger.error(f"❌ Background processing error: {e}")
                self.integration_status['error_count'] += 1
                self.integration_status['last_error'] = str(e)
        
        self.background_thread = threading.Thread(target=background_worker, daemon=True)
        self.background_thread.start()
        self.is_running = True
        
        logger.info("✅ Background processing started")
    
    async def _background_pipeline_loop(self):
        """Background pipeline processing loop."""
        try:
            while self.is_running and self.pipeline:
                # Update shared memory
                self.db_manager.update_shared_memory('system_status', 'running')
                self.db_manager.update_shared_memory('last_update', time.time())
                
                # Get tick count from main database
                with self.db_manager.get_main_db_connection(read_only=True) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM unified_ticks")
                    tick_count = cursor.fetchone()[0]
                    self.db_manager.update_shared_memory('tick_count', tick_count)
                
                # Sleep for a bit
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"❌ Background pipeline loop error: {e}")
            self.integration_status['error_count'] += 1
            self.integration_status['last_error'] = str(e)
    
    def stop(self):
        """Stop the integration."""
        try:
            self.is_running = False
            
            if self.pipeline:
                # Stop the pipeline
                asyncio.run(self.pipeline.stop())
            
            if self.background_thread and self.background_thread.is_alive():
                self.background_thread.join(timeout=5)
            
            logger.info("✅ Integration stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping integration: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get integration status."""
        return {
            'is_running': self.is_running,
            'pipeline_initialized': self.integration_status['pipeline_initialized'],
            'data_feeds_active': self.integration_status['data_feeds_active'],
            'database_connected': self.integration_status['database_connected'],
            'error_count': self.integration_status['error_count'],
            'last_error': self.integration_status['last_error'],
            'startup_time': self.integration_status['startup_time'].isoformat() if self.integration_status['startup_time'] else None,
            'background_thread_alive': self.background_thread.is_alive() if self.background_thread else False,
            'database_architecture': 'separate_databases',
            'access_permissions': self.db_manager.access_permissions
        }
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get pipeline status."""
        if not self.pipeline:
            return {'error': 'Pipeline not initialized'}
        
        try:
            return self.pipeline.get_status()
        except Exception as e:
            logger.error(f"❌ Error getting pipeline status: {e}")
            return {'error': str(e)}
    
    def get_database_status(self) -> Dict[str, Any]:
        """Get database status."""
        return self.db_manager.get_database_status()
    
    def get_shared_memory(self) -> Dict[str, Any]:
        """Get shared memory data."""
        return self.db_manager.get_shared_memory()

# Global instance
_integration: Optional[UnifiedTickPipelineIntegrationUpdated] = None

def initialize_unified_pipeline_updated(config: Optional[Dict[str, Any]] = None) -> UnifiedTickPipelineIntegrationUpdated:
    """Initialize the updated unified pipeline integration."""
    global _integration
    _integration = UnifiedTickPipelineIntegrationUpdated(config)
    return _integration

def get_unified_pipeline_updated() -> Optional[UnifiedTickPipelineIntegrationUpdated]:
    """Get the updated unified pipeline integration."""
    return _integration

# Backward compatibility
def initialize_unified_pipeline(config: Optional[Dict[str, Any]] = None) -> UnifiedTickPipelineIntegrationUpdated:
    """Initialize the unified pipeline integration (backward compatibility)."""
    return initialize_unified_pipeline_updated(config)

def get_unified_pipeline() -> Optional[UnifiedTickPipelineIntegrationUpdated]:
    """Get the unified pipeline integration (backward compatibility)."""
    return get_unified_pipeline_updated()
