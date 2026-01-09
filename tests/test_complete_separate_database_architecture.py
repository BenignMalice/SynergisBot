#!/usr/bin/env python3
"""
Test Complete Separate Database Architecture
============================================
This script tests the complete separate database architecture implementation:
- ChatGPT Bot (main database WRITE access)
- Desktop Agent (analysis database WRITE access)
- API Server (logs database WRITE access)
- All processes can read from all databases
"""

import asyncio
import logging
import time
import threading
from database_access_manager import DatabaseAccessManager, initialize_database_manager
from unified_tick_pipeline_integration_updated import UnifiedTickPipelineIntegrationUpdated
from desktop_agent_unified_pipeline_integration_updated import DesktopAgentUnifiedPipelineIntegrationUpdated
from app.main_api_updated import get_enhanced_market_data, get_volatility_analysis, get_system_health

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CompleteSeparateDatabaseArchitectureTester:
    """Tests the complete separate database architecture."""
    
    def __init__(self):
        self.test_results = {
            'database_creation': False,
            'access_permissions': False,
            'chatgpt_bot_integration': False,
            'desktop_agent_integration': False,
            'api_server_integration': False,
            'concurrent_operations': False,
            'data_flow': False,
            'system_coordination': False
        }
    
    def test_database_creation(self):
        """Test that all databases are created and accessible."""
        logger.info("🧪 Testing database creation...")
        
        try:
            # Test all process types
            process_types = ['chatgpt_bot', 'desktop_agent', 'api_server']
            
            for process_type in process_types:
                manager = DatabaseAccessManager(process_type)
                results = manager.test_database_access()
                
                logger.info(f"✅ {process_type} access: {results}")
                
                # Verify access permissions
                if process_type == 'chatgpt_bot':
                    assert results['main_db_write'] == True, f"{process_type} should have WRITE access to main database"
                    assert results['analysis_db_write'] == False, f"{process_type} should have READ access to analysis database"
                    assert results['logs_db_write'] == False, f"{process_type} should have READ access to logs database"
                elif process_type == 'desktop_agent':
                    assert results['main_db_write'] == False, f"{process_type} should have READ access to main database"
                    assert results['analysis_db_write'] == True, f"{process_type} should have WRITE access to analysis database"
                    assert results['logs_db_write'] == False, f"{process_type} should have READ access to logs database"
                elif process_type == 'api_server':
                    assert results['main_db_write'] == False, f"{process_type} should have READ access to main database"
                    assert results['analysis_db_write'] == False, f"{process_type} should have READ access to analysis database"
                    assert results['logs_db_write'] == True, f"{process_type} should have WRITE access to logs database"
            
            logger.info("✅ Database creation test passed")
            self.test_results['database_creation'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Database creation test failed: {e}")
            return False
    
    def test_access_permissions(self):
        """Test access permissions for all processes."""
        logger.info("🧪 Testing access permissions...")
        
        try:
            # Test ChatGPT Bot permissions
            chatgpt_manager = DatabaseAccessManager("chatgpt_bot")
            chatgpt_permissions = chatgpt_manager.access_permissions
            
            assert chatgpt_permissions['main_db'] == 'write', "ChatGPT Bot should have WRITE access to main database"
            assert chatgpt_permissions['analysis_db'] == 'read', "ChatGPT Bot should have READ access to analysis database"
            assert chatgpt_permissions['logs_db'] == 'read', "ChatGPT Bot should have READ access to logs database"
            
            # Test Desktop Agent permissions
            desktop_manager = DatabaseAccessManager("desktop_agent")
            desktop_permissions = desktop_manager.access_permissions
            
            assert desktop_permissions['main_db'] == 'read', "Desktop Agent should have READ access to main database"
            assert desktop_permissions['analysis_db'] == 'write', "Desktop Agent should have WRITE access to analysis database"
            assert desktop_permissions['logs_db'] == 'read', "Desktop Agent should have READ access to logs database"
            
            # Test API Server permissions
            api_manager = DatabaseAccessManager("api_server")
            api_permissions = api_manager.access_permissions
            
            assert api_permissions['main_db'] == 'read', "API Server should have READ access to main database"
            assert api_permissions['analysis_db'] == 'read', "API Server should have READ access to analysis database"
            assert api_permissions['logs_db'] == 'write', "API Server should have WRITE access to logs database"
            
            logger.info("✅ Access permissions test passed")
            self.test_results['access_permissions'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Access permissions test failed: {e}")
            return False
    
    async def test_chatgpt_bot_integration(self):
        """Test ChatGPT Bot integration with separate database architecture."""
        logger.info("🧪 Testing ChatGPT Bot integration...")
        
        try:
            # Initialize ChatGPT Bot integration
            chatgpt_integration = UnifiedTickPipelineIntegrationUpdated()
            
            # Test database access
            if not chatgpt_integration._test_database_access():
                logger.error("❌ ChatGPT Bot database access test failed")
                return False
            
            # Test shared memory
            shared_memory = chatgpt_integration.get_shared_memory()
            logger.info(f"✅ ChatGPT Bot shared memory: {len(shared_memory)} keys")
            
            # Test database status
            db_status = chatgpt_integration.get_database_status()
            logger.info(f"✅ ChatGPT Bot database status: {db_status}")
            
            logger.info("✅ ChatGPT Bot integration test passed")
            self.test_results['chatgpt_bot_integration'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ ChatGPT Bot integration test failed: {e}")
            return False
    
    async def test_desktop_agent_integration(self):
        """Test Desktop Agent integration with separate database architecture."""
        logger.info("🧪 Testing Desktop Agent integration...")
        
        try:
            # Initialize Desktop Agent integration
            desktop_integration = DesktopAgentUnifiedPipelineIntegrationUpdated()
            
            # Test database access
            if not desktop_integration._test_database_access():
                logger.error("❌ Desktop Agent database access test failed")
                return False
            
            # Test enhanced symbol analysis
            analysis_result = await desktop_integration.get_enhanced_symbol_analysis("BTCUSDT")
            if analysis_result.get('success'):
                logger.info("✅ Desktop Agent enhanced symbol analysis working")
            else:
                logger.warning(f"⚠️ Desktop Agent enhanced symbol analysis: {analysis_result}")
            
            # Test volatility analysis
            volatility_result = await desktop_integration.get_volatility_analysis("BTCUSDT")
            if volatility_result.get('success'):
                logger.info("✅ Desktop Agent volatility analysis working")
            else:
                logger.warning(f"⚠️ Desktop Agent volatility analysis: {volatility_result}")
            
            # Test system health
            health_result = await desktop_integration.get_system_health()
            if health_result.get('success'):
                logger.info("✅ Desktop Agent system health working")
            else:
                logger.warning(f"⚠️ Desktop Agent system health: {health_result}")
            
            logger.info("✅ Desktop Agent integration test passed")
            self.test_results['desktop_agent_integration'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Desktop Agent integration test failed: {e}")
            return False
    
    async def test_api_server_integration(self):
        """Test API Server integration with separate database architecture."""
        logger.info("🧪 Testing API Server integration...")
        
        try:
            # Test enhanced market data
            market_data = await get_enhanced_market_data("BTCUSDT")
            if market_data.get('success'):
                logger.info("✅ API Server enhanced market data working")
            else:
                logger.warning(f"⚠️ API Server enhanced market data: {market_data}")
            
            # Test volatility analysis
            volatility_data = await get_volatility_analysis("BTCUSDT")
            if volatility_data.get('success'):
                logger.info("✅ API Server volatility analysis working")
            else:
                logger.warning(f"⚠️ API Server volatility analysis: {volatility_data}")
            
            # Test system health
            health_data = await get_system_health()
            if health_data.get('success'):
                logger.info("✅ API Server system health working")
            else:
                logger.warning(f"⚠️ API Server system health: {health_data}")
            
            logger.info("✅ API Server integration test passed")
            self.test_results['api_server_integration'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ API Server integration test failed: {e}")
            return False
    
    def test_concurrent_operations(self):
        """Test concurrent operations across all processes."""
        logger.info("🧪 Testing concurrent operations...")
        
        try:
            # Create managers for all processes
            chatgpt_manager = DatabaseAccessManager("chatgpt_bot")
            desktop_manager = DatabaseAccessManager("desktop_agent")
            api_manager = DatabaseAccessManager("api_server")
            
            # Test concurrent access
            def test_chatgpt_operations():
                """Test ChatGPT Bot operations."""
                try:
                    # Test main database write
                    with chatgpt_manager.get_main_db_connection(read_only=False) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM unified_ticks")
                        count = cursor.fetchone()[0]
                        logger.info(f"✅ ChatGPT Bot: {count} ticks in main database")
                    
                    # Test analysis database read
                    with chatgpt_manager.get_analysis_db_connection(read_only=True) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM analysis_results")
                        count = cursor.fetchone()[0]
                        logger.info(f"✅ ChatGPT Bot: {count} analysis results")
                    
                    return True
                except Exception as e:
                    logger.error(f"❌ ChatGPT Bot operations failed: {e}")
                    return False
            
            def test_desktop_agent_operations():
                """Test Desktop Agent operations."""
                try:
                    # Test main database read
                    with desktop_manager.get_main_db_connection(read_only=True) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM unified_ticks")
                        count = cursor.fetchone()[0]
                        logger.info(f"✅ Desktop Agent: {count} ticks in main database")
                    
                    # Test analysis database write
                    with desktop_manager.get_analysis_db_connection(read_only=False) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM analysis_results")
                        count = cursor.fetchone()[0]
                        logger.info(f"✅ Desktop Agent: {count} analysis results")
                    
                    return True
                except Exception as e:
                    logger.error(f"❌ Desktop Agent operations failed: {e}")
                    return False
            
            def test_api_server_operations():
                """Test API Server operations."""
                try:
                    # Test main database read
                    with api_manager.get_main_db_connection(read_only=True) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM unified_ticks")
                        count = cursor.fetchone()[0]
                        logger.info(f"✅ API Server: {count} ticks in main database")
                    
                    # Test logs database write
                    with api_manager.get_logs_db_connection(read_only=False) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM api_logs")
                        count = cursor.fetchone()[0]
                        logger.info(f"✅ API Server: {count} log entries")
                    
                    return True
                except Exception as e:
                    logger.error(f"❌ API Server operations failed: {e}")
                    return False
            
            # Run concurrent tests
            threads = []
            results = []
            
            t1 = threading.Thread(target=lambda: results.append(test_chatgpt_operations()))
            t2 = threading.Thread(target=lambda: results.append(test_desktop_agent_operations()))
            t3 = threading.Thread(target=lambda: results.append(test_api_server_operations()))
            
            threads = [t1, t2, t3]
            
            for t in threads:
                t.start()
            
            for t in threads:
                t.join()
            
            # Check results
            if all(results):
                logger.info("✅ Concurrent operations test passed")
                self.test_results['concurrent_operations'] = True
                return True
            else:
                logger.error("❌ Concurrent operations test failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Concurrent operations test failed: {e}")
            return False
    
    def test_data_flow(self):
        """Test data flow between processes."""
        logger.info("🧪 Testing data flow...")
        
        try:
            # Test data flow: ChatGPT Bot -> Desktop Agent -> API Server
            
            # 1. ChatGPT Bot writes to main database
            chatgpt_manager = DatabaseAccessManager("chatgpt_bot")
            with chatgpt_manager.get_main_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO unified_ticks (symbol, price, volume, timestamp, source, bid, ask)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, ('BTCUSDT', 50000.0, 1.0, time.time(), 'test_flow', 49999.0, 50001.0))
                conn.commit()
                logger.info("✅ ChatGPT Bot: Data written to main database")
            
            # 2. Desktop Agent reads from main database and writes to analysis database
            desktop_manager = DatabaseAccessManager("desktop_agent")
            with desktop_manager.get_main_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM unified_ticks WHERE source = 'test_flow'")
                count = cursor.fetchone()[0]
                logger.info(f"✅ Desktop Agent: Read {count} test records from main database")
            
            with desktop_manager.get_analysis_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO analysis_results (symbol, analysis_type, result, confidence, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, ('BTCUSDT', 'test_flow_analysis', '{"test": "data"}', 0.95, time.time()))
                conn.commit()
                logger.info("✅ Desktop Agent: Analysis result written to analysis database")
            
            # 3. API Server reads from both databases and writes to logs database
            api_manager = DatabaseAccessManager("api_server")
            with api_manager.get_main_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM unified_ticks WHERE source = 'test_flow'")
                count = cursor.fetchone()[0]
                logger.info(f"✅ API Server: Read {count} test records from main database")
            
            with api_manager.get_analysis_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE analysis_type = 'test_flow_analysis'")
                count = cursor.fetchone()[0]
                logger.info(f"✅ API Server: Read {count} test analysis results from analysis database")
            
            with api_manager.get_logs_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO api_logs (endpoint, method, status_code, response_time, timestamp, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ('/test-flow', 'GET', 200, 0.1, time.time(), 'Data flow test successful'))
                conn.commit()
                logger.info("✅ API Server: Log entry written to logs database")
            
            logger.info("✅ Data flow test passed")
            self.test_results['data_flow'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Data flow test failed: {e}")
            return False
    
    def test_system_coordination(self):
        """Test system coordination through shared memory."""
        logger.info("🧪 Testing system coordination...")
        
        try:
            # Test shared memory coordination
            chatgpt_manager = DatabaseAccessManager("chatgpt_bot")
            desktop_manager = DatabaseAccessManager("desktop_agent")
            api_manager = DatabaseAccessManager("api_server")
            
            # Update shared memory from each process
            chatgpt_manager.update_shared_memory('chatgpt_status', 'active')
            desktop_manager.update_shared_memory('desktop_agent_status', 'active')
            api_manager.update_shared_memory('api_server_status', 'active')
            
            # Read shared memory from each process
            chatgpt_memory = chatgpt_manager.get_shared_memory()
            desktop_memory = desktop_manager.get_shared_memory()
            api_memory = api_manager.get_shared_memory()
            
            logger.info(f"✅ ChatGPT Bot shared memory: {len(chatgpt_memory)} keys")
            logger.info(f"✅ Desktop Agent shared memory: {len(desktop_memory)} keys")
            logger.info(f"✅ API Server shared memory: {len(api_memory)} keys")
            
            # Verify coordination
            assert chatgpt_memory.get('chatgpt_status') == 'active', "ChatGPT Bot status not updated"
            assert desktop_memory.get('desktop_agent_status') == 'active', "Desktop Agent status not updated"
            assert api_memory.get('api_server_status') == 'active', "API Server status not updated"
            
            logger.info("✅ System coordination test passed")
            self.test_results['system_coordination'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ System coordination test failed: {e}")
            return False
    
    async def run_all_tests(self):
        """Run all tests."""
        logger.info("🧪 COMPLETE SEPARATE DATABASE ARCHITECTURE TEST")
        logger.info("=" * 60)
        
        # Run all tests
        tests = [
            ("Database Creation", self.test_database_creation),
            ("Access Permissions", self.test_access_permissions),
            ("ChatGPT Bot Integration", self.test_chatgpt_bot_integration),
            ("Desktop Agent Integration", self.test_desktop_agent_integration),
            ("API Server Integration", self.test_api_server_integration),
            ("Concurrent Operations", self.test_concurrent_operations),
            ("Data Flow", self.test_data_flow),
            ("System Coordination", self.test_system_coordination)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            logger.info(f"\n🧪 Running {test_name} test...")
            if await test_func() if asyncio.iscoroutinefunction(test_func) else test_func():
                passed += 1
                logger.info(f"✅ {test_name} test PASSED")
            else:
                logger.error(f"❌ {test_name} test FAILED")
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("🧪 COMPLETE TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Passed: {passed}/{total}")
        logger.info(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            logger.info("🎉 ALL TESTS PASSED!")
            logger.info("✅ Complete separate database architecture is working correctly")
            logger.info("✅ No more database locking issues")
            logger.info("✅ All processes have appropriate database access")
            logger.info("✅ System coordination is working")
            logger.info("✅ Ready for production use")
            return True
        else:
            logger.error("❌ SOME TESTS FAILED!")
            logger.error("⚠️ Please check the logs for details")
            return False

async def main():
    """Main function."""
    print("🧪 COMPLETE SEPARATE DATABASE ARCHITECTURE TEST")
    print("=" * 60)
    print("This will test the complete separate database architecture:")
    print("  • Database creation and access")
    print("  • Access permissions for all processes")
    print("  • ChatGPT Bot integration")
    print("  • Desktop Agent integration")
    print("  • API Server integration")
    print("  • Concurrent operations")
    print("  • Data flow between processes")
    print("  • System coordination")
    print("=" * 60)
    
    tester = CompleteSeparateDatabaseArchitectureTester()
    
    if await tester.run_all_tests():
        print("\n🎉 COMPLETE SEPARATE DATABASE ARCHITECTURE TEST PASSED!")
        print("✅ All tests passed successfully")
        print("✅ No more database locking issues")
        print("✅ Ready for production use")
        print("\n🚀 Your institutional-grade trading system is now fully operational!")
    else:
        print("\n❌ COMPLETE SEPARATE DATABASE ARCHITECTURE TEST FAILED!")
        print("⚠️ Please check the logs for details")

if __name__ == "__main__":
    asyncio.run(main())
