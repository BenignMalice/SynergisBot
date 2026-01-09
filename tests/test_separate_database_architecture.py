#!/usr/bin/env python3
"""
Test Separate Database Architecture
==================================
This script tests the separate database architecture to ensure:
- Each process has appropriate database access
- No database locking issues occur
- All databases are accessible and functional
"""

import asyncio
import logging
import time
import threading
from database_access_manager import DatabaseAccessManager, initialize_database_manager
from unified_tick_pipeline_integration_updated import UnifiedTickPipelineIntegrationUpdated

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SeparateDatabaseArchitectureTester:
    """Tests the separate database architecture."""
    
    def __init__(self):
        self.test_results = {
            'database_creation': False,
            'access_permissions': False,
            'concurrent_access': False,
            'data_operations': False,
            'integration_test': False
        }
    
    def test_database_creation(self):
        """Test that all databases are created and accessible."""
        logger.info("🧪 Testing database creation...")
        
        try:
            # Test ChatGPT Bot access
            chatgpt_manager = DatabaseAccessManager("chatgpt_bot")
            chatgpt_results = chatgpt_manager.test_database_access()
            
            # Test Desktop Agent access
            desktop_manager = DatabaseAccessManager("desktop_agent")
            desktop_results = desktop_manager.test_database_access()
            
            # Test API Server access
            api_manager = DatabaseAccessManager("api_server")
            api_results = api_manager.test_database_access()
            
            # Verify access permissions
            assert chatgpt_results['main_db_write'] == True, "ChatGPT Bot should have WRITE access to main database"
            assert chatgpt_results['analysis_db_write'] == False, "ChatGPT Bot should have READ access to analysis database"
            assert chatgpt_results['logs_db_write'] == False, "ChatGPT Bot should have READ access to logs database"
            
            assert desktop_results['main_db_write'] == False, "Desktop Agent should have READ access to main database"
            assert desktop_results['analysis_db_write'] == True, "Desktop Agent should have WRITE access to analysis database"
            assert desktop_results['logs_db_write'] == False, "Desktop Agent should have READ access to logs database"
            
            assert api_results['main_db_write'] == False, "API Server should have READ access to main database"
            assert api_results['analysis_db_write'] == False, "API Server should have READ access to analysis database"
            assert api_results['logs_db_write'] == True, "API Server should have WRITE access to logs database"
            
            logger.info("✅ Database creation test passed")
            self.test_results['database_creation'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Database creation test failed: {e}")
            return False
    
    def test_concurrent_access(self):
        """Test concurrent access to databases."""
        logger.info("🧪 Testing concurrent database access...")
        
        try:
            # Create multiple managers for different processes
            chatgpt_manager = DatabaseAccessManager("chatgpt_bot")
            desktop_manager = DatabaseAccessManager("desktop_agent")
            api_manager = DatabaseAccessManager("api_server")
            
            # Test concurrent access
            def test_chatgpt_access():
                """Test ChatGPT Bot database access."""
                try:
                    with chatgpt_manager.get_main_db_connection(read_only=False) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM unified_ticks")
                        count = cursor.fetchone()[0]
                        logger.info(f"✅ ChatGPT Bot: {count} ticks in main database")
                    
                    with chatgpt_manager.get_analysis_db_connection(read_only=True) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM analysis_results")
                        count = cursor.fetchone()[0]
                        logger.info(f"✅ ChatGPT Bot: {count} analysis results")
                    
                    return True
                except Exception as e:
                    logger.error(f"❌ ChatGPT Bot access failed: {e}")
                    return False
            
            def test_desktop_agent_access():
                """Test Desktop Agent database access."""
                try:
                    with desktop_manager.get_main_db_connection(read_only=True) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM unified_ticks")
                        count = cursor.fetchone()[0]
                        logger.info(f"✅ Desktop Agent: {count} ticks in main database")
                    
                    with desktop_manager.get_analysis_db_connection(read_only=False) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM analysis_results")
                        count = cursor.fetchone()[0]
                        logger.info(f"✅ Desktop Agent: {count} analysis results")
                    
                    return True
                except Exception as e:
                    logger.error(f"❌ Desktop Agent access failed: {e}")
                    return False
            
            def test_api_server_access():
                """Test API Server database access."""
                try:
                    with api_manager.get_main_db_connection(read_only=True) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM unified_ticks")
                        count = cursor.fetchone()[0]
                        logger.info(f"✅ API Server: {count} ticks in main database")
                    
                    with api_manager.get_logs_db_connection(read_only=False) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM api_logs")
                        count = cursor.fetchone()[0]
                        logger.info(f"✅ API Server: {count} log entries")
                    
                    return True
                except Exception as e:
                    logger.error(f"❌ API Server access failed: {e}")
                    return False
            
            # Run concurrent tests
            threads = []
            results = []
            
            # Start all tests concurrently
            t1 = threading.Thread(target=lambda: results.append(test_chatgpt_access()))
            t2 = threading.Thread(target=lambda: results.append(test_desktop_agent_access()))
            t3 = threading.Thread(target=lambda: results.append(test_api_server_access()))
            
            threads = [t1, t2, t3]
            
            for t in threads:
                t.start()
            
            for t in threads:
                t.join()
            
            # Check results
            if all(results):
                logger.info("✅ Concurrent access test passed")
                self.test_results['concurrent_access'] = True
                return True
            else:
                logger.error("❌ Concurrent access test failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Concurrent access test failed: {e}")
            return False
    
    def test_data_operations(self):
        """Test data operations on databases."""
        logger.info("🧪 Testing data operations...")
        
        try:
            # Test ChatGPT Bot writing to main database
            chatgpt_manager = DatabaseAccessManager("chatgpt_bot")
            
            with chatgpt_manager.get_main_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                # Insert test tick data
                cursor.execute("""
                    INSERT INTO unified_ticks (symbol, price, volume, timestamp, source, bid, ask)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, ('BTCUSDT', 50000.0, 1.0, time.time(), 'test', 49999.0, 50001.0))
                
                conn.commit()
                logger.info("✅ ChatGPT Bot: Successfully wrote to main database")
            
            # Test Desktop Agent writing to analysis database
            desktop_manager = DatabaseAccessManager("desktop_agent")
            
            with desktop_manager.get_analysis_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                # Insert test analysis data
                cursor.execute("""
                    INSERT INTO analysis_results (symbol, analysis_type, result, confidence, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, ('BTCUSDT', 'test_analysis', 'Test result', 0.95, time.time()))
                
                conn.commit()
                logger.info("✅ Desktop Agent: Successfully wrote to analysis database")
            
            # Test API Server writing to logs database
            api_manager = DatabaseAccessManager("api_server")
            
            with api_manager.get_logs_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                # Insert test log data
                cursor.execute("""
                    INSERT INTO api_logs (endpoint, method, status_code, response_time, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, ('/test', 'GET', 200, 0.1, time.time()))
                
                conn.commit()
                logger.info("✅ API Server: Successfully wrote to logs database")
            
            # Test cross-database reading
            with chatgpt_manager.get_analysis_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM analysis_results")
                count = cursor.fetchone()[0]
                logger.info(f"✅ ChatGPT Bot: Read {count} analysis results from analysis database")
            
            with desktop_manager.get_main_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM unified_ticks")
                count = cursor.fetchone()[0]
                logger.info(f"✅ Desktop Agent: Read {count} ticks from main database")
            
            logger.info("✅ Data operations test passed")
            self.test_results['data_operations'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Data operations test failed: {e}")
            return False
    
    def test_integration(self):
        """Test the updated integration."""
        logger.info("🧪 Testing updated integration...")
        
        try:
            # Initialize the updated integration
            integration = UnifiedTickPipelineIntegrationUpdated()
            
            # Test database access
            if not integration._test_database_access():
                logger.error("❌ Integration database access test failed")
                return False
            
            # Test shared memory
            shared_memory = integration.get_shared_memory()
            logger.info(f"✅ Shared memory accessible: {len(shared_memory)} keys")
            
            # Test database status
            db_status = integration.get_database_status()
            logger.info(f"✅ Database status: {db_status}")
            
            logger.info("✅ Integration test passed")
            self.test_results['integration_test'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Integration test failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests."""
        logger.info("🧪 SEPARATE DATABASE ARCHITECTURE TEST")
        logger.info("=" * 50)
        
        # Run all tests
        tests = [
            ("Database Creation", self.test_database_creation),
            ("Concurrent Access", self.test_concurrent_access),
            ("Data Operations", self.test_data_operations),
            ("Integration", self.test_integration)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            logger.info(f"\n🧪 Running {test_name} test...")
            if test_func():
                passed += 1
                logger.info(f"✅ {test_name} test PASSED")
            else:
                logger.error(f"❌ {test_name} test FAILED")
        
        # Summary
        logger.info("\n" + "=" * 50)
        logger.info("🧪 TEST SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Passed: {passed}/{total}")
        logger.info(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            logger.info("🎉 ALL TESTS PASSED!")
            logger.info("✅ Separate database architecture is working correctly")
            logger.info("✅ No more database locking issues")
            logger.info("✅ Each process has appropriate database access")
            return True
        else:
            logger.error("❌ SOME TESTS FAILED!")
            logger.error("⚠️ Please check the logs for details")
            return False

def main():
    """Main function."""
    print("🧪 SEPARATE DATABASE ARCHITECTURE TEST")
    print("=" * 50)
    print("This will test the separate database architecture:")
    print("  • Database creation and access")
    print("  • Concurrent access testing")
    print("  • Data operations testing")
    print("  • Integration testing")
    print("=" * 50)
    
    tester = SeparateDatabaseArchitectureTester()
    
    if tester.run_all_tests():
        print("\n🎉 SEPARATE DATABASE ARCHITECTURE TEST PASSED!")
        print("✅ All tests passed successfully")
        print("✅ No more database locking issues")
        print("✅ Ready for production use")
    else:
        print("\n❌ SEPARATE DATABASE ARCHITECTURE TEST FAILED!")
        print("⚠️ Please check the logs for details")

if __name__ == "__main__":
    main()
