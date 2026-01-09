"""
Comprehensive Testing Suite for Unified Tick Pipeline Integration

This module provides comprehensive testing for all Unified Tick Pipeline integrations
including unit tests, integration tests, and performance tests.
"""

import asyncio
import pytest
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# TEST CONFIGURATION
# ============================================================================

class TestConfig:
    """Test configuration settings"""
    
    # Test symbols
    TEST_SYMBOLS = ['BTCUSDT', 'XAUUSDT', 'ETHUSDT', 'EURUSDc', 'GBPUSDc']
    
    # Test timeframes
    TEST_TIMEFRAMES = ['M1', 'M5', 'M15', 'H1', 'H4']
    
    # Test limits
    TICK_LIMIT = 100
    CANDLE_LIMIT = 50
    
    # Test timeouts
    INITIALIZATION_TIMEOUT = 30
    DATA_RETRIEVAL_TIMEOUT = 10
    PERFORMANCE_TIMEOUT = 60
    
    # Performance thresholds
    MAX_INITIALIZATION_TIME = 30
    MAX_DATA_RETRIEVAL_TIME = 5
    MAX_MEMORY_USAGE_MB = 500
    MAX_CPU_USAGE_PERCENT = 80

# ============================================================================
# UNIT TESTS
# ============================================================================

class TestUnifiedPipelineCore:
    """Unit tests for Unified Tick Pipeline core components"""
    
    @pytest.mark.asyncio
    async def test_pipeline_initialization(self):
        """Test Unified Tick Pipeline initialization"""
        try:
            from unified_tick_pipeline_integration import initialize_unified_pipeline
            
            start_time = time.time()
            result = await initialize_unified_pipeline()
            initialization_time = time.time() - start_time
            
            assert result is True, "Pipeline initialization failed"
            assert initialization_time < TestConfig.MAX_INITIALIZATION_TIME, f"Initialization took too long: {initialization_time}s"
            
            logger.info(f"✅ Pipeline initialization test passed ({initialization_time:.2f}s)")
            
        except Exception as e:
            pytest.fail(f"Pipeline initialization test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_pipeline_status(self):
        """Test pipeline status retrieval"""
        try:
            from unified_tick_pipeline_integration import get_pipeline_instance
            
            pipeline = get_pipeline_instance()
            assert pipeline is not None, "Pipeline instance not available"
            
            status = await pipeline.get_pipeline_status()
            assert isinstance(status, dict), "Status should be a dictionary"
            assert 'components' in status, "Status should contain components"
            
            logger.info("✅ Pipeline status test passed")
            
        except Exception as e:
            pytest.fail(f"Pipeline status test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_system_health(self):
        """Test system health retrieval"""
        try:
            from unified_tick_pipeline_integration import get_pipeline_instance
            
            pipeline = get_pipeline_instance()
            assert pipeline is not None, "Pipeline instance not available"
            
            # Check if get_system_health is async
            if asyncio.iscoroutinefunction(pipeline.get_system_health):
                health = await pipeline.get_system_health()
            else:
                health = pipeline.get_system_health()
            
            assert isinstance(health, dict), "Health should be a dictionary"
            
            logger.info("✅ System health test passed")
            
        except Exception as e:
            pytest.fail(f"System health test failed: {e}")

class TestChatGPTBotIntegration:
    """Unit tests for ChatGPT Bot integration"""
    
    @pytest.mark.asyncio
    async def test_chatgpt_bot_integration(self):
        """Test ChatGPT Bot integration"""
        try:
            from unified_tick_pipeline_integration import initialize_unified_pipeline
            
            # Test pipeline initialization
            result = await initialize_unified_pipeline()
            assert result is True, "ChatGPT Bot pipeline initialization failed"
            
            logger.info("✅ ChatGPT Bot integration test passed")
            
        except Exception as e:
            pytest.fail(f"ChatGPT Bot integration test failed: {e}")

class TestDTMSIntegration:
    """Unit tests for DTMS integration"""
    
    @pytest.mark.asyncio
    async def test_dtms_integration(self):
        """Test DTMS integration"""
        try:
            from dtms_unified_pipeline_integration import initialize_dtms_unified_pipeline
            
            result = await initialize_dtms_unified_pipeline()
            assert result is True, "DTMS integration failed"
            
            logger.info("✅ DTMS integration test passed")
            
        except Exception as e:
            pytest.fail(f"DTMS integration test failed: {e}")

class TestIntelligentExitsIntegration:
    """Unit tests for Intelligent Exits integration"""
    
    @pytest.mark.asyncio
    async def test_intelligent_exits_integration(self):
        """Test Intelligent Exits integration"""
        try:
            from intelligent_exits_unified_pipeline_integration import initialize_intelligent_exits_unified_pipeline
            
            result = await initialize_intelligent_exits_unified_pipeline()
            assert result is True, "Intelligent Exits integration failed"
            
            logger.info("✅ Intelligent Exits integration test passed")
            
        except Exception as e:
            pytest.fail(f"Intelligent Exits integration test failed: {e}")

class TestDesktopAgentIntegration:
    """Unit tests for Desktop Agent integration"""
    
    @pytest.mark.asyncio
    async def test_desktop_agent_integration(self):
        """Test Desktop Agent integration"""
        try:
            from desktop_agent_unified_pipeline_integration import initialize_desktop_agent_unified_pipeline
            
            result = await initialize_desktop_agent_unified_pipeline()
            assert result is True, "Desktop Agent integration failed"
            
            logger.info("✅ Desktop Agent integration test passed")
            
        except Exception as e:
            pytest.fail(f"Desktop Agent integration test failed: {e}")

class TestMainAPIIntegration:
    """Unit tests for Main API integration"""
    
    @pytest.mark.asyncio
    async def test_main_api_integration(self):
        """Test Main API integration"""
        try:
            from main_api_unified_pipeline_integration import initialize_main_api_unified_pipeline
            
            result = await initialize_main_api_unified_pipeline()
            assert result is True, "Main API integration failed"
            
            logger.info("✅ Main API integration test passed")
            
        except Exception as e:
            pytest.fail(f"Main API integration test failed: {e}")

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestDataFlow:
    """Integration tests for data flow"""
    
    @pytest.mark.asyncio
    async def test_tick_data_flow(self):
        """Test tick data flow through the pipeline"""
        try:
            from unified_tick_pipeline_integration import get_pipeline_instance
            
            pipeline = get_pipeline_instance()
            assert pipeline is not None, "Pipeline instance not available"
            
            # Test tick data retrieval for each symbol
            for symbol in TestConfig.TEST_SYMBOLS:
                start_time = time.time()
                ticks = pipeline.get_latest_ticks(symbol, TestConfig.TICK_LIMIT)
                retrieval_time = time.time() - start_time
                
                assert retrieval_time < TestConfig.MAX_DATA_RETRIEVAL_TIME, f"Tick retrieval took too long for {symbol}: {retrieval_time}s"
                assert isinstance(ticks, list), f"Ticks should be a list for {symbol}"
                
                logger.info(f"✅ Tick data flow test passed for {symbol} ({retrieval_time:.2f}s)")
            
        except Exception as e:
            pytest.fail(f"Tick data flow test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_m5_volatility_bridge(self):
        """Test M5 volatility bridge data flow"""
        try:
            from unified_tick_pipeline_integration import get_pipeline_instance
            
            pipeline = get_pipeline_instance()
            assert pipeline is not None, "Pipeline instance not available"
            
            # Test M5 volatility data for each symbol
            for symbol in TestConfig.TEST_SYMBOLS:
                if hasattr(pipeline, 'm5_volatility_bridge'):
                    start_time = time.time()
                    volatility_data = pipeline.m5_volatility_bridge.get_volatility_data(symbol)
                    retrieval_time = time.time() - start_time
                    
                    assert retrieval_time < TestConfig.MAX_DATA_RETRIEVAL_TIME, f"M5 volatility retrieval took too long for {symbol}: {retrieval_time}s"
                    assert isinstance(volatility_data, dict), f"Volatility data should be a dict for {symbol}"
                    
                    logger.info(f"✅ M5 volatility bridge test passed for {symbol} ({retrieval_time:.2f}s)")
            
        except Exception as e:
            pytest.fail(f"M5 volatility bridge test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_offset_calibration(self):
        """Test offset calibration data flow"""
        try:
            from unified_tick_pipeline_integration import get_pipeline_instance
            
            pipeline = get_pipeline_instance()
            assert pipeline is not None, "Pipeline instance not available"
            
            # Test offset calibration for each symbol
            for symbol in TestConfig.TEST_SYMBOLS:
                if hasattr(pipeline, 'offset_calibrator'):
                    start_time = time.time()
                    offset_data = pipeline.offset_calibrator.get_calibration_data(symbol)
                    retrieval_time = time.time() - start_time
                    
                    assert retrieval_time < TestConfig.MAX_DATA_RETRIEVAL_TIME, f"Offset calibration retrieval took too long for {symbol}: {retrieval_time}s"
                    assert isinstance(offset_data, dict), f"Offset data should be a dict for {symbol}"
                    
                    logger.info(f"✅ Offset calibration test passed for {symbol} ({retrieval_time:.2f}s)")
            
        except Exception as e:
            pytest.fail(f"Offset calibration test failed: {e}")

class TestSystemCoordination:
    """Integration tests for system coordination"""
    
    @pytest.mark.asyncio
    async def test_hierarchical_control_matrix(self):
        """Test hierarchical control matrix"""
        try:
            from unified_tick_pipeline_integration import get_pipeline_instance
            
            pipeline = get_pipeline_instance()
            assert pipeline is not None, "Pipeline instance not available"
            
            # Test system coordination
            if hasattr(pipeline, 'system_coordination'):
                coordination_status = pipeline.system_coordination.get_status()
                assert isinstance(coordination_status, dict), "Coordination status should be a dictionary"
                
                logger.info("✅ Hierarchical control matrix test passed")
            
        except Exception as e:
            pytest.fail(f"Hierarchical control matrix test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_performance_optimization(self):
        """Test performance optimization"""
        try:
            from unified_tick_pipeline_integration import get_pipeline_instance
            
            pipeline = get_pipeline_instance()
            assert pipeline is not None, "Pipeline instance not available"
            
            # Test performance optimization
            if hasattr(pipeline, 'performance_optimization'):
                perf_status = pipeline.performance_optimization.get_status()
                assert isinstance(perf_status, dict), "Performance status should be a dictionary"
                
                logger.info("✅ Performance optimization test passed")
            
        except Exception as e:
            pytest.fail(f"Performance optimization test failed: {e}")

class TestDatabaseIntegration:
    """Integration tests for database integration"""
    
    @pytest.mark.asyncio
    async def test_database_connection(self):
        """Test database connection"""
        try:
            from unified_tick_pipeline_integration import get_pipeline_instance
            
            pipeline = get_pipeline_instance()
            assert pipeline is not None, "Pipeline instance not available"
            
            # Test database integration
            if hasattr(pipeline, 'database_integration'):
                db_status = pipeline.database_integration.get_status()
                assert isinstance(db_status, dict), "Database status should be a dictionary"
                
                logger.info("✅ Database connection test passed")
            
        except Exception as e:
            pytest.fail(f"Database connection test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_data_access_layer(self):
        """Test data access layer"""
        try:
            from unified_tick_pipeline_integration import get_pipeline_instance
            
            pipeline = get_pipeline_instance()
            assert pipeline is not None, "Pipeline instance not available"
            
            # Test data access layer
            if hasattr(pipeline, 'data_access_layer'):
                data_access_status = pipeline.data_access_layer.get_status()
                assert isinstance(data_access_status, dict), "Data access status should be a dictionary"
                
                logger.info("✅ Data access layer test passed")
            
        except Exception as e:
            pytest.fail(f"Data access layer test failed: {e}")

# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance tests for the Unified Tick Pipeline"""
    
    @pytest.mark.asyncio
    async def test_memory_usage(self):
        """Test memory usage"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Initialize pipeline
            from unified_tick_pipeline_integration import initialize_unified_pipeline
            await initialize_unified_pipeline()
            
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_usage = memory_after - memory_before
            
            assert memory_usage < TestConfig.MAX_MEMORY_USAGE_MB, f"Memory usage too high: {memory_usage}MB"
            
            logger.info(f"✅ Memory usage test passed ({memory_usage:.2f}MB)")
            
        except Exception as e:
            pytest.fail(f"Memory usage test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_cpu_usage(self):
        """Test CPU usage"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            # Monitor CPU usage during pipeline operations
            cpu_usage = process.cpu_percent(interval=1)
            
            assert cpu_usage < TestConfig.MAX_CPU_USAGE_PERCENT, f"CPU usage too high: {cpu_usage}%"
            
            logger.info(f"✅ CPU usage test passed ({cpu_usage}%)")
            
        except Exception as e:
            pytest.fail(f"CPU usage test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_data_retrieval_performance(self):
        """Test data retrieval performance"""
        try:
            from unified_tick_pipeline_integration import get_pipeline_instance
            
            pipeline = get_pipeline_instance()
            assert pipeline is not None, "Pipeline instance not available"
            
            # Test data retrieval performance for each symbol
            for symbol in TestConfig.TEST_SYMBOLS:
                start_time = time.time()
                ticks = pipeline.get_latest_ticks(symbol, TestConfig.TICK_LIMIT)
                retrieval_time = time.time() - start_time
                
                assert retrieval_time < TestConfig.MAX_DATA_RETRIEVAL_TIME, f"Data retrieval too slow for {symbol}: {retrieval_time}s"
                
                logger.info(f"✅ Data retrieval performance test passed for {symbol} ({retrieval_time:.2f}s)")
            
        except Exception as e:
            pytest.fail(f"Data retrieval performance test failed: {e}")

# ============================================================================
# STRESS TESTS
# ============================================================================

class TestStress:
    """Stress tests for the Unified Tick Pipeline"""
    
    @pytest.mark.asyncio
    async def test_concurrent_data_retrieval(self):
        """Test concurrent data retrieval"""
        try:
            from unified_tick_pipeline_integration import get_pipeline_instance
            
            pipeline = get_pipeline_instance()
            assert pipeline is not None, "Pipeline instance not available"
            
            # Create concurrent tasks for data retrieval
            tasks = []
            for symbol in TestConfig.TEST_SYMBOLS:
                task = asyncio.create_task(
                    self._retrieve_data_concurrently(pipeline, symbol)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            start_time = time.time()
            results = await asyncio.gather(*tasks)
            total_time = time.time() - start_time
            
            # Verify all tasks completed successfully
            for i, result in enumerate(results):
                assert result is True, f"Concurrent data retrieval failed for {TestConfig.TEST_SYMBOLS[i]}"
            
            assert total_time < TestConfig.PERFORMANCE_TIMEOUT, f"Concurrent data retrieval took too long: {total_time}s"
            
            logger.info(f"✅ Concurrent data retrieval test passed ({total_time:.2f}s)")
            
        except Exception as e:
            pytest.fail(f"Concurrent data retrieval test failed: {e}")
    
    async def _retrieve_data_concurrently(self, pipeline, symbol):
        """Helper method for concurrent data retrieval"""
        try:
            ticks = pipeline.get_latest_ticks(symbol, TestConfig.TICK_LIMIT)
            return isinstance(ticks, list)
        except Exception:
            return False
    
    @pytest.mark.asyncio
    async def test_high_frequency_data_retrieval(self):
        """Test high frequency data retrieval"""
        try:
            from unified_tick_pipeline_integration import get_pipeline_instance
            
            pipeline = get_pipeline_instance()
            assert pipeline is not None, "Pipeline instance not available"
            
            # Perform high frequency data retrieval
            iterations = 100
            start_time = time.time()
            
            for i in range(iterations):
                symbol = TestConfig.TEST_SYMBOLS[i % len(TestConfig.TEST_SYMBOLS)]
                ticks = pipeline.get_latest_ticks(symbol, 10)
                assert isinstance(ticks, list), f"High frequency retrieval failed at iteration {i}"
            
            total_time = time.time() - start_time
            avg_time = total_time / iterations
            
            assert avg_time < 0.1, f"High frequency retrieval too slow: {avg_time}s per request"
            
            logger.info(f"✅ High frequency data retrieval test passed ({avg_time:.3f}s per request)")
            
        except Exception as e:
            pytest.fail(f"High frequency data retrieval test failed: {e}")

# ============================================================================
# TEST RUNNER
# ============================================================================

async def run_all_tests():
    """Run all tests"""
    logger.info("🚀 Starting Unified Tick Pipeline Integration Tests...")
    
    # Test categories
    test_categories = [
        "Unit Tests",
        "Integration Tests", 
        "Performance Tests",
        "Stress Tests"
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    try:
        # Run unit tests
        logger.info("📋 Running Unit Tests...")
        unit_tests = [
            TestUnifiedPipelineCore,
            TestChatGPTBotIntegration,
            TestDTMSIntegration,
            TestIntelligentExitsIntegration,
            TestDesktopAgentIntegration,
            TestMainAPIIntegration
        ]
        
        for test_class in unit_tests:
            test_instance = test_class()
            for method_name in dir(test_instance):
                if method_name.startswith('test_'):
                    total_tests += 1
                    try:
                        method = getattr(test_instance, method_name)
                        if asyncio.iscoroutinefunction(method):
                            await method()
                        else:
                            method()
                        passed_tests += 1
                        logger.info(f"✅ {method_name} passed")
                    except Exception as e:
                        failed_tests += 1
                        logger.error(f"❌ {method_name} failed: {e}")
        
        # Run integration tests
        logger.info("📋 Running Integration Tests...")
        integration_tests = [
            TestDataFlow,
            TestSystemCoordination,
            TestDatabaseIntegration
        ]
        
        for test_class in integration_tests:
            test_instance = test_class()
            for method_name in dir(test_instance):
                if method_name.startswith('test_'):
                    total_tests += 1
                    try:
                        method = getattr(test_instance, method_name)
                        if asyncio.iscoroutinefunction(method):
                            await method()
                        else:
                            method()
                        passed_tests += 1
                        logger.info(f"✅ {method_name} passed")
                    except Exception as e:
                        failed_tests += 1
                        logger.error(f"❌ {method_name} failed: {e}")
        
        # Run performance tests
        logger.info("📋 Running Performance Tests...")
        performance_tests = [TestPerformance]
        
        for test_class in performance_tests:
            test_instance = test_class()
            for method_name in dir(test_instance):
                if method_name.startswith('test_'):
                    total_tests += 1
                    try:
                        method = getattr(test_instance, method_name)
                        if asyncio.iscoroutinefunction(method):
                            await method()
                        else:
                            method()
                        passed_tests += 1
                        logger.info(f"✅ {method_name} passed")
                    except Exception as e:
                        failed_tests += 1
                        logger.error(f"❌ {method_name} failed: {e}")
        
        # Run stress tests
        logger.info("📋 Running Stress Tests...")
        stress_tests = [TestStress]
        
        for test_class in stress_tests:
            test_instance = test_class()
            for method_name in dir(test_instance):
                if method_name.startswith('test_'):
                    total_tests += 1
                    try:
                        method = getattr(test_instance, method_name)
                        if asyncio.iscoroutinefunction(method):
                            await method()
                        else:
                            method()
                        passed_tests += 1
                        logger.info(f"✅ {method_name} passed")
                    except Exception as e:
                        failed_tests += 1
                        logger.error(f"❌ {method_name} failed: {e}")
        
        # Test summary
        logger.info("📊 Test Summary:")
        logger.info(f"   Total Tests: {total_tests}")
        logger.info(f"   Passed: {passed_tests}")
        logger.info(f"   Failed: {failed_tests}")
        logger.info(f"   Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests == 0:
            logger.info("🎉 All tests passed!")
            return True
        else:
            logger.error(f"❌ {failed_tests} tests failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test runner failed: {e}")
        return False

if __name__ == "__main__":
    # Run tests
    result = asyncio.run(run_all_tests())
    exit(0 if result else 1)
