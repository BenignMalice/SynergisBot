"""
Updated Desktop Agent Unified Pipeline Integration
Uses separate database architecture for analysis database (WRITE access)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import json
import time

# Import the new database access manager
from database_access_manager import DatabaseAccessManager, initialize_database_manager

# Import the updated unified pipeline integration
from unified_tick_pipeline_integration_updated import get_unified_pipeline_updated

logger = logging.getLogger(__name__)

class DesktopAgentUnifiedPipelineIntegrationUpdated:
    """
    Updated Desktop Agent integration with separate database architecture
    
    Features:
    - Uses analysis database for WRITE access (Desktop Agent)
    - Reads from main database for tick data
    - Reads from logs database for system health
    - Eliminates database locking issues
    """
    
    def __init__(self):
        self.pipeline = None
        self.is_active = False
        
        # Initialize database access manager for Desktop Agent
        self.db_manager = initialize_database_manager("desktop_agent")
        
        # Desktop Agent state
        self.performance_metrics = {
            'analysis_requests': 0,
            'volatility_checks': 0,
            'offset_checks': 0,
            'system_health_checks': 0,
            'error_count': 0
        }
        
        logger.info("DesktopAgentUnifiedPipelineIntegrationUpdated initialized with separate database architecture")
    
    async def initialize(self) -> bool:
        """Initialize Desktop Agent with separate database architecture"""
        try:
            logger.info("🔧 Initializing Desktop Agent with separate database architecture...")
            
            # Test database access
            if not self._test_database_access():
                logger.error("❌ Database access test failed")
                return False
            
            # Get the updated unified pipeline; initialize it here if missing
            self.pipeline = get_unified_pipeline_updated()
            if not self.pipeline:
                logger.warning("⚠️ Updated Unified Tick Pipeline not available, initializing...")
                from unified_tick_pipeline_integration_updated import initialize_unified_pipeline_updated
                self.pipeline = initialize_unified_pipeline_updated()
                ok = await self.pipeline.initialize_pipeline()
                if ok: 
                    self.pipeline.start_background_processing()
                else: 
                    return False
            
            self.is_active = True
            logger.info("✅ Desktop Agent with separate database architecture initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Desktop Agent: {e}")
            return False
    
    def _test_database_access(self) -> bool:
        """Test database access for Desktop Agent."""
        try:
            logger.info("🧪 Testing database access for Desktop Agent...")
            
            # Test main database (READ access)
            with self.db_manager.get_main_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM unified_ticks")
                count = cursor.fetchone()[0]
                logger.info(f"✅ Main database accessible: {count} ticks")
            
            # Test analysis database (WRITE access)
            with self.db_manager.get_analysis_db_connection(read_only=False) as conn:
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
            
            logger.info("✅ All database access tests passed for Desktop Agent")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database access test failed: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop Desktop Agent integration"""
        try:
            logger.info("🛑 Stopping Desktop Agent integration...")
            self.is_active = False
            logger.info("✅ Desktop Agent integration stopped")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping Desktop Agent integration: {e}")
            return False
    
    # Enhanced analysis tools with separate database architecture
    async def get_enhanced_symbol_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get enhanced symbol analysis using separate database architecture"""
        try:
            if not self.pipeline:
                return {'error': 'Unified Tick Pipeline not available'}
            
            # Get latest tick data from main database (READ)
            tick_data = await self._get_tick_data_from_main_db(symbol)
            
            # Get volatility analysis
            volatility_data = await self._get_volatility_analysis(symbol)
            
            # Get offset calibration
            offset_data = await self._get_offset_calibration(symbol)
            
            # Get M5 candles from main database (READ)
            m5_data = await self._get_m5_candles_from_main_db(symbol)
            
            # Get system health from logs database (READ)
            health_data = await self._get_system_health_from_logs_db()
            
            # Store analysis result in analysis database (WRITE)
            analysis_result = {
                'symbol': symbol,
                'analysis_type': 'enhanced_symbol_analysis',
                'result': {
                    'tick_data': tick_data,
                    'volatility': volatility_data,
                    'offset': offset_data,
                    'm5_candles': m5_data,
                    'system_health': health_data
                },
                'confidence': 0.95,
                'timestamp': time.time()
            }
            
            await self._store_analysis_result(analysis_result)
            
            self.performance_metrics['analysis_requests'] += 1
            
            return {
                'success': True,
                'data': analysis_result,
                'database_architecture': 'separate_databases',
                'access_info': {
                    'main_db': 'read',
                    'analysis_db': 'write',
                    'logs_db': 'read'
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Enhanced symbol analysis failed: {e}")
            self.performance_metrics['error_count'] += 1
            return {'error': str(e)}
    
    async def get_volatility_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get volatility analysis using separate database architecture"""
        try:
            if not self.pipeline:
                return {'error': 'Unified Tick Pipeline not available'}
            
            # Get volatility data from main database (READ)
            volatility_data = await self._get_volatility_analysis(symbol)
            
            # Store volatility analysis in analysis database (WRITE)
            analysis_result = {
                'symbol': symbol,
                'analysis_type': 'volatility_analysis',
                'result': volatility_data,
                'confidence': 0.90,
                'timestamp': time.time()
            }
            
            await self._store_analysis_result(analysis_result)
            
            self.performance_metrics['volatility_checks'] += 1
            
            return {
                'success': True,
                'data': analysis_result,
                'database_architecture': 'separate_databases'
            }
            
        except Exception as e:
            logger.error(f"❌ Volatility analysis failed: {e}")
            self.performance_metrics['error_count'] += 1
            return {'error': str(e)}
    
    async def get_offset_calibration(self, symbol: str) -> Dict[str, Any]:
        """Get offset calibration using separate database architecture"""
        try:
            if not self.pipeline:
                return {'error': 'Unified Tick Pipeline not available'}
            
            # Get offset data from main database (READ)
            offset_data = await self._get_offset_calibration(symbol)
            
            # Store offset calibration in analysis database (WRITE)
            analysis_result = {
                'symbol': symbol,
                'analysis_type': 'offset_calibration',
                'result': offset_data,
                'confidence': 0.85,
                'timestamp': time.time()
            }
            
            await self._store_analysis_result(analysis_result)
            
            self.performance_metrics['offset_checks'] += 1
            
            return {
                'success': True,
                'data': analysis_result,
                'database_architecture': 'separate_databases'
            }
            
        except Exception as e:
            logger.error(f"❌ Offset calibration failed: {e}")
            self.performance_metrics['error_count'] += 1
            return {'error': str(e)}
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get system health using separate database architecture"""
        try:
            # Get system health from logs database (READ)
            health_data = await self._get_system_health_from_logs_db()
            
            # Get database status
            db_status = self.db_manager.get_database_status()
            
            # Get shared memory
            shared_memory = self.db_manager.get_shared_memory()
            
            # Store system health in analysis database (WRITE)
            analysis_result = {
                'symbol': 'SYSTEM',
                'analysis_type': 'system_health',
                'result': {
                    'health_data': health_data,
                    'database_status': db_status,
                    'shared_memory': shared_memory,
                    'performance_metrics': self.performance_metrics
                },
                'confidence': 1.0,
                'timestamp': time.time()
            }
            
            await self._store_analysis_result(analysis_result)
            
            self.performance_metrics['system_health_checks'] += 1
            
            return {
                'success': True,
                'data': analysis_result,
                'database_architecture': 'separate_databases'
            }
            
        except Exception as e:
            logger.error(f"❌ System health check failed: {e}")
            self.performance_metrics['error_count'] += 1
            return {'error': str(e)}
    
    async def get_pipeline_status(self) -> Dict[str, Any]:
        """Get pipeline status using separate database architecture"""
        try:
            if not self.pipeline:
                return {'error': 'Unified Tick Pipeline not available'}
            
            # Get pipeline status
            pipeline_status = self.pipeline.get_pipeline_status()
            
            # Get database status
            db_status = self.db_manager.get_database_status()
            
            # Get shared memory
            shared_memory = self.db_manager.get_shared_memory()
            
            return {
                'success': True,
                'data': {
                    'pipeline_status': pipeline_status,
                    'database_status': db_status,
                    'shared_memory': shared_memory,
                    'database_architecture': 'separate_databases',
                    'access_permissions': self.db_manager.access_permissions
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Pipeline status check failed: {e}")
            return {'error': str(e)}
    
    # Helper methods for database operations
    async def _get_tick_data_from_main_db(self, symbol: str) -> Dict[str, Any]:
        """Get tick data from main database (READ access)"""
        try:
            with self.db_manager.get_main_db_connection(read_only=True) as conn:
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
                    return {
                        'symbol': row[0],
                        'price': row[1],
                        'volume': row[2],
                        'timestamp': row[3],
                        'source': row[4],
                        'bid': row[5],
                        'ask': row[6]
                    }
                else:
                    return {'error': 'No tick data found'}
                    
        except Exception as e:
            logger.error(f"❌ Error getting tick data from main database: {e}")
            return {'error': str(e)}
    
    async def _get_m5_candles_from_main_db(self, symbol: str) -> List[Dict[str, Any]]:
        """Get M5 candles from main database (READ access)"""
        try:
            with self.db_manager.get_main_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT symbol, open_price, high_price, low_price, close_price, volume, timestamp
                    FROM m5_candles 
                    WHERE symbol = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 10
                """, (symbol,))
                
                rows = cursor.fetchall()
                candles = []
                for row in rows:
                    candles.append({
                        'symbol': row[0],
                        'open': row[1],
                        'high': row[2],
                        'low': row[3],
                        'close': row[4],
                        'volume': row[5],
                        'timestamp': row[6]
                    })
                
                return candles
                
        except Exception as e:
            logger.error(f"❌ Error getting M5 candles from main database: {e}")
            return []
    
    async def _get_system_health_from_logs_db(self) -> Dict[str, Any]:
        """Get system health from logs database (READ access)"""
        try:
            with self.db_manager.get_logs_db_connection(read_only=True) as conn:
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
                
                return {'health_data': health_data}
                
        except Exception as e:
            logger.error(f"❌ Error getting system health from logs database: {e}")
            return {'error': str(e)}
    
    async def _store_analysis_result(self, analysis_result: Dict[str, Any]) -> bool:
        """Store analysis result in analysis database (WRITE access)"""
        try:
            with self.db_manager.get_analysis_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO analysis_results (symbol, analysis_type, result, confidence, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    analysis_result['symbol'],
                    analysis_result['analysis_type'],
                    json.dumps(analysis_result['result']),
                    analysis_result['confidence'],
                    analysis_result['timestamp']
                ))
                
                conn.commit()
                logger.info(f"✅ Analysis result stored for {analysis_result['symbol']}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error storing analysis result: {e}")
            return False
    
    async def _get_volatility_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get volatility analysis (placeholder - implement based on your needs)"""
        return {
            'symbol': symbol,
            'volatility': 0.15,
            'atr': 50.0,
            'vix_level': 20.0,
            'timestamp': time.time()
        }
    
    async def _get_offset_calibration(self, symbol: str) -> Dict[str, Any]:
        """Get offset calibration (placeholder - implement based on your needs)"""
        return {
            'symbol': symbol,
            'offset': 0.5,
            'calibration_quality': 0.95,
            'timestamp': time.time()
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return {
            'performance_metrics': self.performance_metrics,
            'database_architecture': 'separate_databases',
            'access_permissions': self.db_manager.access_permissions,
            'is_active': self.is_active
        }

# Global instance
_desktop_agent_integration: Optional[DesktopAgentUnifiedPipelineIntegrationUpdated] = None

def initialize_desktop_agent_unified_pipeline_updated() -> DesktopAgentUnifiedPipelineIntegrationUpdated:
    """Initialize the updated desktop agent integration."""
    global _desktop_agent_integration
    _desktop_agent_integration = DesktopAgentUnifiedPipelineIntegrationUpdated()
    return _desktop_agent_integration

def get_desktop_agent_integration_updated() -> Optional[DesktopAgentUnifiedPipelineIntegrationUpdated]:
    """Get the updated desktop agent integration."""
    return _desktop_agent_integration

# Backward compatibility
def initialize_desktop_agent_unified_pipeline() -> DesktopAgentUnifiedPipelineIntegrationUpdated:
    """Initialize desktop agent integration (backward compatibility)."""
    return initialize_desktop_agent_unified_pipeline_updated()

# Tool functions for backward compatibility
async def tool_enhanced_symbol_analysis(symbol: str) -> Dict[str, Any]:
    """Enhanced symbol analysis tool"""
    integration = get_desktop_agent_integration_updated()
    if not integration:
        return {'error': 'Desktop Agent integration not available'}
    
    return await integration.get_enhanced_symbol_analysis(symbol)

async def tool_volatility_analysis(symbol: str) -> Dict[str, Any]:
    """Volatility analysis tool"""
    integration = get_desktop_agent_integration_updated()
    if not integration:
        return {'error': 'Desktop Agent integration not available'}
    
    return await integration.get_volatility_analysis(symbol)

async def tool_offset_calibration(symbol: str) -> Dict[str, Any]:
    """Offset calibration tool"""
    integration = get_desktop_agent_integration_updated()
    if not integration:
        return {'error': 'Desktop Agent integration not available'}
    
    return await integration.get_offset_calibration(symbol)

async def tool_system_health(args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """System health tool (args optional for registry compatibility)"""
    integration = get_desktop_agent_integration_updated()
    if not integration:
        return {'error': 'Desktop Agent integration not available'}
    
    return await integration.get_system_health()

async def tool_pipeline_status() -> Dict[str, Any]:
    """Pipeline status tool"""
    integration = get_desktop_agent_integration_updated()
    if not integration:
        return {'error': 'Desktop Agent integration not available'}
    
    return await integration.get_pipeline_status()
