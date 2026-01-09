"""
Incremental Testing Strategy for Unified Tick Pipeline

This module implements incremental testing with validation after each component
update and rollback capabilities.
"""

import asyncio
import logging
import time
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import shutil
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# INCREMENTAL TESTING CONFIGURATION
# ============================================================================

class IncrementalTestConfig:
    """Configuration for incremental testing"""
    
    # Test phases
    PHASES = [
        "core_pipeline",
        "data_feeds", 
        "offset_calibration",
        "m5_volatility_bridge",
        "data_retention",
        "dtms_enhancement",
        "chatgpt_integration",
        "system_coordination",
        "performance_optimization",
        "database_integration",
        "data_access_layer",
        "chatgpt_bot_integration",
        "dtms_system_integration",
        "intelligent_exits_integration",
        "desktop_agent_integration",
        "main_api_integration"
    ]
    
    # Rollback configuration
    BACKUP_DIR = "backups"
    ROLLBACK_TIMEOUT = 30
    
    # Validation thresholds
    MAX_INITIALIZATION_TIME = 30
    MAX_DATA_RETRIEVAL_TIME = 5
    MIN_SUCCESS_RATE = 0.8

# ============================================================================
# INCREMENTAL TESTING FRAMEWORK
# ============================================================================

class IncrementalTester:
    """Incremental testing framework with rollback capabilities"""
    
    def __init__(self):
        self.test_results = {}
        self.backup_files = {}
        self.current_phase = None
        self.rollback_available = False
        
    async def run_incremental_tests(self) -> bool:
        """Run incremental tests for all phases"""
        logger.info("🚀 Starting Incremental Testing Strategy...")
        
        try:
            # Create backup directory
            os.makedirs(IncrementalTestConfig.BACKUP_DIR, exist_ok=True)
            
            # Run tests for each phase
            for phase in IncrementalTestConfig.PHASES:
                logger.info(f"📋 Testing Phase: {phase}")
                
                # Backup current state
                await self._backup_phase_state(phase)
                
                # Run phase tests
                phase_result = await self._test_phase(phase)
                
                if phase_result:
                    logger.info(f"✅ Phase {phase} passed")
                    self.test_results[phase] = "passed"
                else:
                    logger.error(f"❌ Phase {phase} failed")
                    self.test_results[phase] = "failed"
                    
                    # Attempt rollback
                    if self.rollback_available:
                        logger.info(f"🔄 Attempting rollback for phase {phase}")
                        rollback_result = await self._rollback_phase(phase)
                        if rollback_result:
                            logger.info(f"✅ Rollback successful for phase {phase}")
                        else:
                            logger.error(f"❌ Rollback failed for phase {phase}")
                            return False
                    else:
                        logger.error(f"❌ No rollback available for phase {phase}")
                        return False
            
            # Final validation
            final_result = await self._final_validation()
            
            if final_result:
                logger.info("🎉 All incremental tests passed!")
                return True
            else:
                logger.error("❌ Final validation failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Incremental testing failed: {e}")
            return False
    
    async def _backup_phase_state(self, phase: str):
        """Backup current state before phase testing"""
        try:
            backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(IncrementalTestConfig.BACKUP_DIR, f"{phase}_{backup_timestamp}")
            
            # Backup relevant files for the phase
            files_to_backup = self._get_phase_files(phase)
            
            for file_path in files_to_backup:
                if os.path.exists(file_path):
                    backup_file_path = os.path.join(backup_path, os.path.basename(file_path))
                    os.makedirs(os.path.dirname(backup_file_path), exist_ok=True)
                    shutil.copy2(file_path, backup_file_path)
                    self.backup_files[phase] = backup_path
            
            self.rollback_available = True
            logger.info(f"✅ Backup created for phase {phase}")
            
        except Exception as e:
            logger.error(f"❌ Backup failed for phase {phase}: {e}")
            self.rollback_available = False
    
    def _get_phase_files(self, phase: str) -> List[str]:
        """Get files to backup for a specific phase"""
        phase_files = {
            "core_pipeline": [
                "unified_tick_pipeline_integration.py",
                "unified_tick_pipeline/core/pipeline_manager.py"
            ],
            "data_feeds": [
                "unified_tick_pipeline/core/binance_feeds.py",
                "unified_tick_pipeline/core/mt5_bridge.py"
            ],
            "offset_calibration": [
                "unified_tick_pipeline/core/offset_calibrator.py"
            ],
            "m5_volatility_bridge": [
                "unified_tick_pipeline/core/m5_volatility_bridge.py"
            ],
            "data_retention": [
                "unified_tick_pipeline/core/data_retention.py"
            ],
            "dtms_enhancement": [
                "unified_tick_pipeline/core/dtms_enhancement.py"
            ],
            "chatgpt_integration": [
                "unified_tick_pipeline/core/chatgpt_integration.py"
            ],
            "system_coordination": [
                "unified_tick_pipeline/core/system_coordination.py"
            ],
            "performance_optimization": [
                "unified_tick_pipeline/core/performance_optimization.py"
            ],
            "database_integration": [
                "unified_tick_pipeline/core/database_integration.py"
            ],
            "data_access_layer": [
                "unified_tick_pipeline/core/data_access_layer.py"
            ],
            "chatgpt_bot_integration": [
                "chatgpt_bot.py"
            ],
            "dtms_system_integration": [
                "dtms_unified_pipeline_integration.py"
            ],
            "intelligent_exits_integration": [
                "intelligent_exits_unified_pipeline_integration.py"
            ],
            "desktop_agent_integration": [
                "desktop_agent.py",
                "desktop_agent_unified_pipeline_integration.py"
            ],
            "main_api_integration": [
                "app/main_api.py",
                "main_api_unified_pipeline_integration.py"
            ]
        }
        
        return phase_files.get(phase, [])
    
    async def _test_phase(self, phase: str) -> bool:
        """Test a specific phase"""
        try:
            self.current_phase = phase
            
            # Phase-specific tests
            if phase == "core_pipeline":
                return await self._test_core_pipeline()
            elif phase == "data_feeds":
                return await self._test_data_feeds()
            elif phase == "offset_calibration":
                return await self._test_offset_calibration()
            elif phase == "m5_volatility_bridge":
                return await self._test_m5_volatility_bridge()
            elif phase == "data_retention":
                return await self._test_data_retention()
            elif phase == "dtms_enhancement":
                return await self._test_dtms_enhancement()
            elif phase == "chatgpt_integration":
                return await self._test_chatgpt_integration()
            elif phase == "system_coordination":
                return await self._test_system_coordination()
            elif phase == "performance_optimization":
                return await self._test_performance_optimization()
            elif phase == "database_integration":
                return await self._test_database_integration()
            elif phase == "data_access_layer":
                return await self._test_data_access_layer()
            elif phase == "chatgpt_bot_integration":
                return await self._test_chatgpt_bot_integration()
            elif phase == "dtms_system_integration":
                return await self._test_dtms_system_integration()
            elif phase == "intelligent_exits_integration":
                return await self._test_intelligent_exits_integration()
            elif phase == "desktop_agent_integration":
                return await self._test_desktop_agent_integration()
            elif phase == "main_api_integration":
                return await self._test_main_api_integration()
            else:
                logger.error(f"Unknown phase: {phase}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Phase {phase} test failed: {e}")
            return False
    
    async def _test_core_pipeline(self) -> bool:
        """Test core pipeline functionality"""
        try:
            from unified_tick_pipeline_integration import initialize_unified_pipeline
            
            start_time = time.time()
            result = await initialize_unified_pipeline()
            initialization_time = time.time() - start_time
            
            if result and initialization_time < IncrementalTestConfig.MAX_INITIALIZATION_TIME:
                logger.info(f"✅ Core pipeline test passed ({initialization_time:.2f}s)")
                return True
            else:
                logger.error(f"❌ Core pipeline test failed ({initialization_time:.2f}s)")
                return False
                
        except Exception as e:
            logger.error(f"❌ Core pipeline test failed: {e}")
            return False
    
    async def _test_data_feeds(self) -> bool:
        """Test data feeds functionality"""
        try:
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available")
                return False
            
            # Test Binance feeds
            if hasattr(pipeline, 'binance_feeds'):
                binance_status = pipeline.binance_feeds.get_status()
                if not binance_status.get('is_connected', False):
                    logger.error("❌ Binance feeds not connected")
                    return False
            
            # Test MT5 bridge
            if hasattr(pipeline, 'mt5_bridge'):
                mt5_status = pipeline.mt5_bridge.get_status()
                if not mt5_status.get('is_connected', False):
                    logger.error("❌ MT5 bridge not connected")
                    return False
            
            logger.info("✅ Data feeds test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Data feeds test failed: {e}")
            return False
    
    async def _test_offset_calibration(self) -> bool:
        """Test offset calibration functionality"""
        try:
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available")
                return False
            
            # Test offset calibrator
            if hasattr(pipeline, 'offset_calibrator'):
                offset_status = pipeline.offset_calibrator.get_status()
                if not offset_status.get('is_active', False):
                    logger.error("❌ Offset calibrator not active")
                    return False
            
            logger.info("✅ Offset calibration test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Offset calibration test failed: {e}")
            return False
    
    async def _test_m5_volatility_bridge(self) -> bool:
        """Test M5 volatility bridge functionality"""
        try:
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available")
                return False
            
            # Test M5 volatility bridge
            if hasattr(pipeline, 'm5_volatility_bridge'):
                m5_status = pipeline.m5_volatility_bridge.get_status()
                if not m5_status.get('is_active', False):
                    logger.error("❌ M5 volatility bridge not active")
                    return False
            
            logger.info("✅ M5 volatility bridge test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ M5 volatility bridge test failed: {e}")
            return False
    
    async def _test_data_retention(self) -> bool:
        """Test data retention functionality"""
        try:
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available")
                return False
            
            # Test data retention
            if hasattr(pipeline, 'data_retention'):
                retention_status = pipeline.data_retention.get_status()
                if not retention_status.get('is_active', False):
                    logger.error("❌ Data retention not active")
                    return False
            
            logger.info("✅ Data retention test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Data retention test failed: {e}")
            return False
    
    async def _test_dtms_enhancement(self) -> bool:
        """Test DTMS enhancement functionality"""
        try:
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available")
                return False
            
            # Test DTMS enhancement
            if hasattr(pipeline, 'dtms_enhancement'):
                dtms_status = pipeline.dtms_enhancement.get_status()
                if not dtms_status.get('is_active', False):
                    logger.error("❌ DTMS enhancement not active")
                    return False
            
            logger.info("✅ DTMS enhancement test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ DTMS enhancement test failed: {e}")
            return False
    
    async def _test_chatgpt_integration(self) -> bool:
        """Test ChatGPT integration functionality"""
        try:
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available")
                return False
            
            # Test ChatGPT integration
            if hasattr(pipeline, 'chatgpt_integration'):
                chatgpt_status = pipeline.chatgpt_integration.get_status()
                if not chatgpt_status.get('is_active', False):
                    logger.error("❌ ChatGPT integration not active")
                    return False
            
            logger.info("✅ ChatGPT integration test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ ChatGPT integration test failed: {e}")
            return False
    
    async def _test_system_coordination(self) -> bool:
        """Test system coordination functionality"""
        try:
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available")
                return False
            
            # Test system coordination
            if hasattr(pipeline, 'system_coordination'):
                system_status = pipeline.system_coordination.get_status()
                if not system_status.get('is_active', False):
                    logger.error("❌ System coordination not active")
                    return False
            
            logger.info("✅ System coordination test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ System coordination test failed: {e}")
            return False
    
    async def _test_performance_optimization(self) -> bool:
        """Test performance optimization functionality"""
        try:
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available")
                return False
            
            # Test performance optimization
            if hasattr(pipeline, 'performance_optimization'):
                perf_status = pipeline.performance_optimization.get_status()
                if not perf_status.get('is_active', False):
                    logger.error("❌ Performance optimization not active")
                    return False
            
            logger.info("✅ Performance optimization test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Performance optimization test failed: {e}")
            return False
    
    async def _test_database_integration(self) -> bool:
        """Test database integration functionality"""
        try:
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available")
                return False
            
            # Test database integration
            if hasattr(pipeline, 'database_integration'):
                db_status = pipeline.database_integration.get_status()
                if not db_status.get('is_active', False):
                    logger.error("❌ Database integration not active")
                    return False
            
            logger.info("✅ Database integration test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database integration test failed: {e}")
            return False
    
    async def _test_data_access_layer(self) -> bool:
        """Test data access layer functionality"""
        try:
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available")
                return False
            
            # Test data access layer
            if hasattr(pipeline, 'data_access_layer'):
                data_access_status = pipeline.data_access_layer.get_status()
                if not data_access_status.get('is_active', False):
                    logger.error("❌ Data access layer not active")
                    return False
            
            logger.info("✅ Data access layer test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Data access layer test failed: {e}")
            return False
    
    async def _test_chatgpt_bot_integration(self) -> bool:
        """Test ChatGPT Bot integration functionality"""
        try:
            from chatgpt_bot import initialize_unified_pipeline
            
            result = initialize_unified_pipeline()
            if not result:
                logger.error("❌ ChatGPT Bot integration failed")
                return False
            
            logger.info("✅ ChatGPT Bot integration test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ ChatGPT Bot integration test failed: {e}")
            return False
    
    async def _test_dtms_system_integration(self) -> bool:
        """Test DTMS system integration functionality"""
        try:
            from dtms_unified_pipeline_integration import initialize_dtms_unified_pipeline
            
            result = await initialize_dtms_unified_pipeline()
            if not result:
                logger.error("❌ DTMS system integration failed")
                return False
            
            logger.info("✅ DTMS system integration test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ DTMS system integration test failed: {e}")
            return False
    
    async def _test_intelligent_exits_integration(self) -> bool:
        """Test Intelligent Exits integration functionality"""
        try:
            from intelligent_exits_unified_pipeline_integration import initialize_intelligent_exits_unified_pipeline
            
            result = await initialize_intelligent_exits_unified_pipeline()
            if not result:
                logger.error("❌ Intelligent Exits integration failed")
                return False
            
            logger.info("✅ Intelligent Exits integration test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Intelligent Exits integration test failed: {e}")
            return False
    
    async def _test_desktop_agent_integration(self) -> bool:
        """Test Desktop Agent integration functionality"""
        try:
            from desktop_agent_unified_pipeline_integration import initialize_desktop_agent_unified_pipeline
            
            result = await initialize_desktop_agent_unified_pipeline()
            if not result:
                logger.error("❌ Desktop Agent integration failed")
                return False
            
            logger.info("✅ Desktop Agent integration test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Desktop Agent integration test failed: {e}")
            return False
    
    async def _test_main_api_integration(self) -> bool:
        """Test Main API integration functionality"""
        try:
            from main_api_unified_pipeline_integration import initialize_main_api_unified_pipeline
            
            result = await initialize_main_api_unified_pipeline()
            if not result:
                logger.error("❌ Main API integration failed")
                return False
            
            logger.info("✅ Main API integration test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Main API integration test failed: {e}")
            return False
    
    async def _rollback_phase(self, phase: str) -> bool:
        """Rollback a specific phase"""
        try:
            if phase not in self.backup_files:
                logger.error(f"❌ No backup available for phase {phase}")
                return False
            
            backup_path = self.backup_files[phase]
            files_to_restore = self._get_phase_files(phase)
            
            for file_path in files_to_restore:
                backup_file_path = os.path.join(backup_path, os.path.basename(file_path))
                if os.path.exists(backup_file_path):
                    shutil.copy2(backup_file_path, file_path)
                    logger.info(f"✅ Restored {file_path}")
            
            logger.info(f"✅ Rollback completed for phase {phase}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Rollback failed for phase {phase}: {e}")
            return False
    
    async def _final_validation(self) -> bool:
        """Perform final validation of all components"""
        try:
            # Check overall success rate
            total_phases = len(IncrementalTestConfig.PHASES)
            passed_phases = sum(1 for result in self.test_results.values() if result == "passed")
            success_rate = passed_phases / total_phases
            
            if success_rate < IncrementalTestConfig.MIN_SUCCESS_RATE:
                logger.error(f"❌ Final validation failed: Success rate {success_rate:.2f} below threshold {IncrementalTestConfig.MIN_SUCCESS_RATE}")
                return False
            
            # Test overall system functionality
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Final validation failed: Pipeline not available")
                return False
            
            # Test basic functionality
            status = await pipeline.get_pipeline_status()
            if not status:
                logger.error("❌ Final validation failed: Pipeline status not available")
                return False
            
            logger.info(f"✅ Final validation passed (Success rate: {success_rate:.2f})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Final validation failed: {e}")
            return False

# ============================================================================
# TEST RUNNER
# ============================================================================

async def run_incremental_tests():
    """Run incremental tests"""
    tester = IncrementalTester()
    result = await tester.run_incremental_tests()
    return result

if __name__ == "__main__":
    # Run incremental tests
    result = asyncio.run(run_incremental_tests())
    exit(0 if result else 1)
