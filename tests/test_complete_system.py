#!/usr/bin/env python3
"""
Test Complete System Functionality
Comprehensive test of all system components and data storage
"""

import asyncio
import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import os
import time

logger = logging.getLogger(__name__)

class CompleteSystemTest:
    """
    Comprehensive system test for all components
    """
    
    def __init__(self):
        self.test_results = {}
        self.db_path = 'unified_tick_pipeline.db'
        
        logger.info("CompleteSystemTest initialized")
    
    async def run_all_tests(self) -> bool:
        """Run all system tests"""
        try:
            logger.info("🧪 STARTING COMPLETE SYSTEM TEST")
            logger.info("=" * 50)
            
            # Test 1: Database initialization
            if not await self._test_database_initialization():
                logger.error("❌ Database initialization test failed")
                return False
            
            # Test 2: Data flow system
            if not await self._test_data_flow_system():
                logger.error("❌ Data flow system test failed")
                return False
            
            # Test 3: Desktop Agent integration
            if not await self._test_desktop_agent_integration():
                logger.error("❌ Desktop Agent integration test failed")
                return False
            
            # Test 4: Pipeline initialization
            if not await self._test_pipeline_initialization():
                logger.error("❌ Pipeline initialization test failed")
                return False
            
            # Test 5: System health monitoring
            if not await self._test_system_health():
                logger.error("❌ System health test failed")
                return False
            
            # Test 6: Data storage verification
            if not await self._test_data_storage():
                logger.error("❌ Data storage test failed")
                return False
            
            logger.info("✅ ALL SYSTEM TESTS PASSED!")
            return True
            
        except Exception as e:
            logger.error(f"❌ System test failed: {e}")
            return False
    
    async def _test_database_initialization(self) -> bool:
        """Test database initialization"""
        try:
            logger.info("🗄️ Testing database initialization...")
            
            # Check if database exists
            if not os.path.exists(self.db_path):
                logger.error(f"❌ Database file not found: {self.db_path}")
                return False
            
            # Check database size
            size = os.path.getsize(self.db_path)
            if size == 0:
                logger.error("❌ Database file is empty")
                return False
            
            # Test database connection
            conn = sqlite3.connect(self.db_path, timeout=30)
            cursor = conn.cursor()
            
            # Check if tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            expected_tables = ['unified_ticks', 'm5_candles', 'dtms_actions', 
                             'chatgpt_analysis_history', 'system_health', 'data_retention']
            
            existing_tables = [table[0] for table in tables]
            
            for table in expected_tables:
                if table not in existing_tables:
                    logger.error(f"❌ Missing table: {table}")
                    conn.close()
                    return False
            
            conn.close()
            
            self.test_results['database_initialization'] = {
                'status': 'PASS',
                'tables_found': len(tables),
                'database_size': size,
                'expected_tables': expected_tables,
                'existing_tables': existing_tables
            }
            
            logger.info("✅ Database initialization test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database initialization test failed: {e}")
            self.test_results['database_initialization'] = {'status': 'FAIL', 'error': str(e)}
            return False
    
    async def _test_data_flow_system(self) -> bool:
        """Test data flow system"""
        try:
            logger.info("📡 Testing data flow system...")
            
            # Import and test data flow manager
            from implement_data_flow import DataFlowManager
            
            manager = DataFlowManager()
            
            # Start system
            success = await manager.start()
            if not success:
                logger.error("❌ Data flow system startup failed")
                return False
            
            # Let it run for 10 seconds
            await asyncio.sleep(10)
            
            # Check status
            status = manager.get_status()
            if not status['is_running']:
                logger.error("❌ Data flow system not running")
                return False
            
            # Check database stats
            stats = manager.get_database_stats()
            if 'error' in stats:
                logger.error(f"❌ Database stats error: {stats['error']}")
                return False
            
            # Stop system
            await manager.stop()
            
            self.test_results['data_flow_system'] = {
                'status': 'PASS',
                'ticks_received': status['metrics']['ticks_received'],
                'ticks_stored': status['metrics']['ticks_stored'],
                'errors': status['metrics']['errors'],
                'database_stats': stats
            }
            
            logger.info("✅ Data flow system test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Data flow system test failed: {e}")
            self.test_results['data_flow_system'] = {'status': 'FAIL', 'error': str(e)}
            return False
    
    async def _test_desktop_agent_integration(self) -> bool:
        """Test Desktop Agent integration"""
        try:
            logger.info("🤖 Testing Desktop Agent integration...")
            
            # Import and test Desktop Agent integration
            from fix_desktop_agent_integration import initialize_desktop_agent_unified_pipeline, get_desktop_agent_unified_integration
            
            # Initialize integration
            success = await initialize_desktop_agent_unified_pipeline()
            if not success:
                logger.error("❌ Desktop Agent integration initialization failed")
                return False
            
            # Get integration instance
            integration = get_desktop_agent_unified_integration()
            if not integration:
                logger.error("❌ Desktop Agent integration instance not available")
                return False
            
            # Test enhanced symbol analysis
            analysis = await integration.get_enhanced_symbol_analysis('BTCUSDT')
            if 'error' in analysis:
                logger.warning(f"⚠️ Enhanced analysis warning: {analysis['error']}")
            
            # Test volatility analysis
            volatility = await integration.get_volatility_analysis('BTCUSDT')
            if 'error' in volatility:
                logger.warning(f"⚠️ Volatility analysis warning: {volatility['error']}")
            
            # Test system health
            health = await integration.get_system_health()
            if 'error' in health:
                logger.warning(f"⚠️ System health warning: {health['error']}")
            
            # Stop integration
            await integration.stop()
            
            self.test_results['desktop_agent_integration'] = {
                'status': 'PASS',
                'enhanced_analysis': analysis,
                'volatility_analysis': volatility,
                'system_health': health
            }
            
            logger.info("✅ Desktop Agent integration test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Desktop Agent integration test failed: {e}")
            self.test_results['desktop_agent_integration'] = {'status': 'FAIL', 'error': str(e)}
            return False
    
    async def _test_pipeline_initialization(self) -> bool:
        """Test pipeline initialization"""
        try:
            logger.info("🔧 Testing pipeline initialization...")
            
            # Import and test robust pipeline manager
            from fix_pipeline_initialization import RobustPipelineManager
            
            manager = RobustPipelineManager()
            
            # Start pipeline
            success = await manager.start_pipeline()
            if not success:
                logger.error("❌ Pipeline initialization failed")
                return False
            
            # Check status
            status = manager.get_status()
            if not status['is_running']:
                logger.error("❌ Pipeline not running")
                return False
            
            # Stop pipeline
            await manager.stop_pipeline()
            
            self.test_results['pipeline_initialization'] = {
                'status': 'PASS',
                'pipeline_status': status
            }
            
            logger.info("✅ Pipeline initialization test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Pipeline initialization test failed: {e}")
            self.test_results['pipeline_initialization'] = {'status': 'FAIL', 'error': str(e)}
            return False
    
    async def _test_system_health(self) -> bool:
        """Test system health monitoring"""
        try:
            logger.info("🏥 Testing system health monitoring...")
            
            # Check database health
            conn = sqlite3.connect(self.db_path, timeout=30)
            cursor = conn.cursor()
            
            # Get system health data
            cursor.execute("SELECT COUNT(*) FROM system_health")
            health_records = cursor.fetchone()[0]
            
            # Get tick data count
            cursor.execute("SELECT COUNT(*) FROM unified_ticks")
            tick_count = cursor.fetchone()[0]
            
            conn.close()
            
            self.test_results['system_health'] = {
                'status': 'PASS',
                'health_records': health_records,
                'tick_count': tick_count,
                'database_accessible': True
            }
            
            logger.info("✅ System health test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ System health test failed: {e}")
            self.test_results['system_health'] = {'status': 'FAIL', 'error': str(e)}
            return False
    
    async def _test_data_storage(self) -> bool:
        """Test data storage functionality"""
        try:
            logger.info("💾 Testing data storage...")
            
            # Check database for stored data
            conn = sqlite3.connect(self.db_path, timeout=30)
            cursor = conn.cursor()
            
            # Get tick data statistics
            cursor.execute("SELECT COUNT(*) FROM unified_ticks")
            total_ticks = cursor.fetchone()[0]
            
            # Get data by symbol
            cursor.execute("SELECT symbol, COUNT(*) FROM unified_ticks GROUP BY symbol")
            symbol_counts = dict(cursor.fetchall())
            
            # Get latest data
            cursor.execute("""
                SELECT symbol, price, timestamp, source 
                FROM unified_ticks 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            latest_data = cursor.fetchall()
            
            conn.close()
            
            self.test_results['data_storage'] = {
                'status': 'PASS',
                'total_ticks': total_ticks,
                'symbol_counts': symbol_counts,
                'latest_data': latest_data
            }
            
            logger.info("✅ Data storage test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Data storage test failed: {e}")
            self.test_results['data_storage'] = {'status': 'FAIL', 'error': str(e)}
            return False
    
    def generate_report(self) -> str:
        """Generate test report"""
        report = []
        report.append("🧪 COMPLETE SYSTEM TEST REPORT")
        report.append("=" * 50)
        report.append("")
        
        for test_name, result in self.test_results.items():
            status = result['status']
            if status == 'PASS':
                report.append(f"✅ {test_name}: PASS")
            else:
                report.append(f"❌ {test_name}: FAIL")
                if 'error' in result:
                    report.append(f"   Error: {result['error']}")
            
            # Add details for passed tests
            if status == 'PASS':
                for key, value in result.items():
                    if key != 'status':
                        report.append(f"   {key}: {value}")
            
            report.append("")
        
        # Summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['status'] == 'PASS')
        failed_tests = total_tests - passed_tests
        
        report.append("📊 SUMMARY")
        report.append(f"Total tests: {total_tests}")
        report.append(f"Passed: {passed_tests}")
        report.append(f"Failed: {failed_tests}")
        report.append(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")
        
        return "\n".join(report)

# Test the complete system
async def test_complete_system():
    """Test the complete system"""
    print("🧪 TESTING COMPLETE SYSTEM")
    print("=" * 50)
    
    # Create test instance
    tester = CompleteSystemTest()
    
    # Run all tests
    success = await tester.run_all_tests()
    
    # Generate report
    report = tester.generate_report()
    print(report)
    
    if success:
        print("\n🎉 ALL SYSTEM TESTS PASSED!")
        print("✅ System is fully operational!")
    else:
        print("\n❌ SOME SYSTEM TESTS FAILED!")
        print("⚠️ System needs attention!")

if __name__ == "__main__":
    asyncio.run(test_complete_system())
