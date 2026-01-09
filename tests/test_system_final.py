"""
Final System Test
Tests the system without database locking and Binance connection issues
"""

import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def test_database_access():
    """Test database access without locking issues"""
    logger.info("🧪 Testing database access...")
    
    try:
        # Test database connection
        conn = sqlite3.connect('unified_tick_pipeline.db', timeout=60.0)
        cursor = conn.cursor()
        
        # Test basic operations
        cursor.execute("SELECT COUNT(*) FROM unified_ticks")
        count = cursor.fetchone()[0]
        logger.info(f"✅ Database accessible, {count} ticks stored")
        
        # Test concurrent access simulation
        for i in range(5):
            cursor.execute("SELECT COUNT(*) FROM unified_ticks WHERE symbol = ?", ('BTCUSDT',))
            result = cursor.fetchone()[0]
            logger.info(f"✅ Query {i+1}: {result} BTCUSDT ticks")
        
        conn.close()
        logger.info("✅ Database access test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database access test failed: {e}")
        return False

async def test_system_components():
    """Test system components"""
    logger.info("🧪 Testing system components...")
    
    try:
        # Test database initialization
        from init_database import initialize_database
        db_success = initialize_database()
        logger.info(f"✅ Database initialization: {'PASS' if db_success else 'FAIL'}")
        
        # Test data flow
        from implement_data_flow import BinanceDataFlow
        data_flow = BinanceDataFlow(['BTCUSDT', 'ETHUSDT'])
        await data_flow.start()
        await asyncio.sleep(5)  # Collect data for 5 seconds
        status = data_flow.get_status()
        await data_flow.stop()
        
        data_success = status['is_running'] and status['metrics']['ticks_stored'] > 0
        logger.info(f"✅ Data flow: {'PASS' if data_success else 'FAIL'}")
        
        return db_success and data_success
        
    except Exception as e:
        logger.error(f"❌ System components test failed: {e}")
        return False

async def test_complete_system():
    """Test complete system functionality"""
    logger.info("🧪 Testing complete system...")
    
    try:
        # Test database access
        db_success = await test_database_access()
        
        # Test system components
        components_success = await test_system_components()
        
        # Test API server
        import requests
        try:
            response = requests.get('http://localhost:8000/health', timeout=5)
            api_success = response.status_code == 200
        except:
            api_success = False
        logger.info(f"✅ API server: {'PASS' if api_success else 'FAIL'}")
        
        return db_success and components_success and api_success
        
    except Exception as e:
        logger.error(f"❌ Complete system test failed: {e}")
        return False

async def main():
    """Main test function"""
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 FINAL SYSTEM TEST")
    print("=" * 50)
    
    # Test complete system
    success = await test_complete_system()
    
    if success:
        print("🎉 ALL TESTS PASSED!")
        print("✅ System is ready for use")
    else:
        print("❌ SOME TESTS FAILED!")
        print("⚠️ System needs more fixes")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())
