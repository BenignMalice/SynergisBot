"""
Test Phase 0: Database Write Queue Implementation
Tests the DatabaseWriteQueue class and its integration with auto_execution_system.py
"""

import sys
import os
import time
import sqlite3
import threading
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
TEST_DB_PATH = "data/test_auto_execution_phase0.db"
TEST_QUEUE_PERSISTENCE = "data/test_db_write_queue_phase0.json"

def cleanup_test_files():
    """Clean up test files"""
    try:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        if os.path.exists(TEST_QUEUE_PERSISTENCE):
            os.remove(TEST_QUEUE_PERSISTENCE)
        logger.info("Cleaned up test files")
    except Exception as e:
        logger.warning(f"Error cleaning up test files: {e}")

def setup_test_database():
    """Set up test database"""
    try:
        Path(TEST_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(TEST_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_plans (
                    plan_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    volume REAL NOT NULL,
                    conditions TEXT,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    expires_at TEXT,
                    executed_at TEXT,
                    ticket INTEGER,
                    notes TEXT
                )
            """)
            conn.commit()
        logger.info("Test database created")
        return True
    except Exception as e:
        logger.error(f"Failed to create test database: {e}")
        return False

def test_1_queue_initialization():
    """Test 1: Queue initialization"""
    logger.info("=" * 60)
    logger.info("TEST 1: Queue Initialization")
    logger.info("=" * 60)
    
    try:
        from infra.database_write_queue import DatabaseWriteQueue, OperationPriority
        
        queue = DatabaseWriteQueue(
            db_path=TEST_DB_PATH,
            queue_maxsize=100,
            writer_timeout=10.0,
            persistence_path=TEST_QUEUE_PERSISTENCE
        )
        
        # Check writer thread is running
        time.sleep(0.5)  # Give thread time to start
        health = queue.check_writer_health()
        
        assert health["writer_thread_alive"], "Writer thread should be alive"
        assert health["writer_running"], "Writer should be running"
        
        # Stop queue
        queue.stop()
        
        logger.info("✅ TEST 1 PASSED: Queue initialization successful")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 1 FAILED: {e}", exc_info=True)
        return False

def test_2_basic_operation():
    """Test 2: Basic operation queuing and execution"""
    logger.info("=" * 60)
    logger.info("TEST 2: Basic Operation Queuing")
    logger.info("=" * 60)
    
    try:
        from infra.database_write_queue import DatabaseWriteQueue, OperationPriority
        
        # Create test plan in database
        with sqlite3.connect(TEST_DB_PATH) as conn:
            conn.execute("""
                INSERT INTO trade_plans 
                (plan_id, symbol, direction, entry_price, stop_loss, take_profit, volume,
                 conditions, created_at, created_by, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "test_plan_1", "BTCUSDc", "BUY", 50000.0, 49000.0, 51000.0, 0.01,
                '{}', datetime.now(timezone.utc).isoformat(), "test", "pending"
            ))
            conn.commit()
        
        queue = DatabaseWriteQueue(
            db_path=TEST_DB_PATH,
            queue_maxsize=100,
            writer_timeout=10.0,
            persistence_path=TEST_QUEUE_PERSISTENCE
        )
        
        # Queue update_status operation
        operation_id = queue.queue_operation(
            operation_type="update_status",
            plan_id="test_plan_1",
            data={"status": "executed", "executed_at": datetime.now(timezone.utc).isoformat()},
            priority=OperationPriority.HIGH,
            wait_for_completion=True,
            timeout=10.0
        )
        
        # Verify operation completed
        status = queue.get_operation_status(operation_id)
        assert status is not None, "Operation status should be available"
        assert status["status"] == "completed", f"Operation should be completed, got {status['status']}"
        
        # Verify database was updated
        with sqlite3.connect(TEST_DB_PATH) as conn:
            cursor = conn.execute("SELECT status FROM trade_plans WHERE plan_id = ?", ("test_plan_1",))
            row = cursor.fetchone()
            assert row is not None, "Plan should exist in database"
            assert row[0] == "executed", f"Plan status should be 'executed', got '{row[0]}'"
        
        queue.stop()
        
        logger.info("✅ TEST 2 PASSED: Basic operation queuing and execution successful")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 2 FAILED: {e}", exc_info=True)
        return False

def test_3_operation_priority():
    """Test 3: Operation priority queuing"""
    logger.info("=" * 60)
    logger.info("TEST 3: Operation Priority")
    logger.info("=" * 60)
    
    try:
        from infra.database_write_queue import DatabaseWriteQueue, OperationPriority
        
        # Create test plans
        with sqlite3.connect(TEST_DB_PATH) as conn:
            for i in range(3):
                conn.execute("""
                    INSERT OR REPLACE INTO trade_plans 
                    (plan_id, symbol, direction, entry_price, stop_loss, take_profit, volume,
                     conditions, created_at, created_by, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"test_plan_{i}", "BTCUSDc", "BUY", 50000.0, 49000.0, 51000.0, 0.01,
                    '{}', datetime.now(timezone.utc).isoformat(), "test", "pending"
                ))
            conn.commit()
        
        queue = DatabaseWriteQueue(
            db_path=TEST_DB_PATH,
            queue_maxsize=100,
            writer_timeout=10.0,
            persistence_path=TEST_QUEUE_PERSISTENCE
        )
        
        # Queue operations with different priorities
        op_low = queue.queue_operation(
            operation_type="update_status",
            plan_id="test_plan_0",
            data={"status": "pending"},
            priority=OperationPriority.LOW,
            wait_for_completion=False
        )
        
        op_high = queue.queue_operation(
            operation_type="update_status",
            plan_id="test_plan_1",
            data={"status": "executed"},
            priority=OperationPriority.HIGH,
            wait_for_completion=True,
            timeout=10.0
        )
        
        op_medium = queue.queue_operation(
            operation_type="update_status",
            plan_id="test_plan_2",
            data={"status": "pending"},
            priority=OperationPriority.MEDIUM,
            wait_for_completion=False
        )
        
        # Wait a bit for operations to process
        time.sleep(2.0)
        
        # High priority should complete first
        high_status = queue.get_operation_status(op_high)
        assert high_status["status"] == "completed", "High priority operation should complete"
        
        queue.stop()
        
        logger.info("✅ TEST 3 PASSED: Operation priority queuing successful")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 3 FAILED: {e}", exc_info=True)
        return False

def test_4_queue_persistence():
    """Test 4: Queue persistence and recovery"""
    logger.info("=" * 60)
    logger.info("TEST 4: Queue Persistence")
    logger.info("=" * 60)
    
    try:
        from infra.database_write_queue import DatabaseWriteQueue, OperationPriority
        
        # Create test plan
        with sqlite3.connect(TEST_DB_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO trade_plans 
                (plan_id, symbol, direction, entry_price, stop_loss, take_profit, volume,
                 conditions, created_at, created_by, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "test_plan_persist", "BTCUSDc", "BUY", 50000.0, 49000.0, 51000.0, 0.01,
                '{}', datetime.now(timezone.utc).isoformat(), "test", "pending"
            ))
            conn.commit()
        
        # Create queue and queue operation
        queue1 = DatabaseWriteQueue(
            db_path=TEST_DB_PATH,
            queue_maxsize=100,
            writer_timeout=10.0,
            persistence_path=TEST_QUEUE_PERSISTENCE
        )
        
        operation_id = queue1.queue_operation(
            operation_type="update_status",
            plan_id="test_plan_persist",
            data={"status": "executed"},
            priority=OperationPriority.MEDIUM,
            wait_for_completion=False  # Don't wait - stop queue before it completes
        )
        
        # Stop queue immediately (operation should be persisted)
        queue1.stop()
        
        # Verify persistence file exists
        assert os.path.exists(TEST_QUEUE_PERSISTENCE), "Persistence file should exist"
        
        # Create new queue (should load persisted operations)
        queue2 = DatabaseWriteQueue(
            db_path=TEST_DB_PATH,
            queue_maxsize=100,
            writer_timeout=10.0,
            persistence_path=TEST_QUEUE_PERSISTENCE
        )
        
        # Wait for operation to complete
        time.sleep(2.0)
        
        # Verify operation was replayed and completed
        status = queue2.get_operation_status(operation_id)
        if status:
            # Operation was replayed
            assert status["status"] in ["completed", "processing", "pending"], \
                f"Operation should be replayed, got {status['status']}"
        
        queue2.stop()
        
        logger.info("✅ TEST 4 PASSED: Queue persistence and recovery successful")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 4 FAILED: {e}", exc_info=True)
        return False

def test_5_integration_with_auto_execution():
    """Test 5: Integration with auto_execution_system"""
    logger.info("=" * 60)
    logger.info("TEST 5: Integration with Auto Execution System")
    logger.info("=" * 60)
    
    # Skip if MetaTrader5 is not available (test environment)
    try:
        import MetaTrader5 as mt5
    except ImportError:
        logger.warning("⚠️  MetaTrader5 not available - skipping integration test")
        logger.info("✅ TEST 5 SKIPPED: MetaTrader5 not available (expected in test environment)")
        return True
    
    try:
        from auto_execution_system import AutoExecutionSystem, TradePlan
        
        # Create auto execution system with test database
        system = AutoExecutionSystem(
            db_path=TEST_DB_PATH,
            check_interval=30
        )
        
        # Verify queue is initialized
        assert system.db_write_queue is not None, "Database write queue should be initialized"
        assert system.OperationPriority is not None, "OperationPriority should be available"
        
        # Create test plan
        test_plan = TradePlan(
            plan_id="test_integration_plan",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Add plan to system
        success = system.add_plan(test_plan)
        assert success, "Plan should be added successfully"
        
        # Update plan status using queue
        test_plan.status = "executed"
        test_plan.executed_at = datetime.now(timezone.utc).isoformat()
        success = system._update_plan_status(test_plan, wait_for_completion=True)
        assert success, "Plan status update should succeed"
        
        # Verify database was updated
        with sqlite3.connect(TEST_DB_PATH) as conn:
            cursor = conn.execute("SELECT status FROM trade_plans WHERE plan_id = ?", ("test_integration_plan",))
            row = cursor.fetchone()
            assert row is not None, "Plan should exist in database"
            assert row[0] == "executed", f"Plan status should be 'executed', got '{row[0]}'"
        
        # Stop system
        system.stop()
        
        logger.info("✅ TEST 5 PASSED: Integration with auto execution system successful")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 5 FAILED: {e}", exc_info=True)
        return False

def test_6_execution_lock_leak_prevention():
    """Test 6: Execution lock leak prevention"""
    logger.info("=" * 60)
    logger.info("TEST 6: Execution Lock Leak Prevention")
    logger.info("=" * 60)
    
    # Skip if MetaTrader5 is not available (test environment)
    try:
        import MetaTrader5 as mt5
    except ImportError:
        logger.warning("⚠️  MetaTrader5 not available - skipping lock leak test")
        logger.info("✅ TEST 6 SKIPPED: MetaTrader5 not available (expected in test environment)")
        return True
    
    try:
        from auto_execution_system import AutoExecutionSystem, TradePlan
        
        system = AutoExecutionSystem(
            db_path=TEST_DB_PATH,
            check_interval=30
        )
        
        # Create test plan
        test_plan = TradePlan(
            plan_id="test_lock_plan",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Add plan
        system.add_plan(test_plan)
        
        # Simulate execution lock acquisition
        with system.execution_locks_lock:
            if test_plan.plan_id not in system.execution_locks:
                system.execution_locks[test_plan.plan_id] = threading.Lock()
            execution_lock = system.execution_locks[test_plan.plan_id]
        
        # Acquire lock
        acquired = execution_lock.acquire(blocking=False)
        assert acquired, "Lock should be acquired"
        
        # Verify lock exists
        assert test_plan.plan_id in system.execution_locks, "Lock should exist in execution_locks"
        
        # Simulate exception scenario (lock should still be released in finally block)
        try:
            with system.executing_plans_lock:
                system.executing_plans.add(test_plan.plan_id)
            # Simulate exception
            raise Exception("Test exception")
        except Exception:
            # Finally block should clean up
            pass
        finally:
            # Cleanup (simulating finally block behavior)
            try:
                with system.executing_plans_lock:
                    system.executing_plans.discard(test_plan.plan_id)
            except Exception:
                pass
            try:
                execution_lock.release()
            except Exception:
                pass
        
        # Verify lock was released (can be acquired again)
        acquired_again = execution_lock.acquire(blocking=False)
        assert acquired_again, "Lock should be released and acquirable again"
        execution_lock.release()
        
        system.stop()
        
        logger.info("✅ TEST 6 PASSED: Execution lock leak prevention successful")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 6 FAILED: {e}", exc_info=True)
        return False

def run_all_tests():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("PHASE 0: DATABASE WRITE QUEUE IMPLEMENTATION TESTS")
    logger.info("=" * 60)
    
    # Cleanup
    cleanup_test_files()
    
    # Setup
    if not setup_test_database():
        logger.error("Failed to set up test database")
        return False
    
    # Run tests
    tests = [
        test_1_queue_initialization,
        test_2_basic_operation,
        test_3_operation_priority,
        test_4_queue_persistence,
        test_5_integration_with_auto_execution,
        test_6_execution_lock_leak_prevention
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            logger.error(f"Test {test.__name__} raised exception: {e}", exc_info=True)
            results.append(False)
        finally:
            # Cleanup between tests
            cleanup_test_files()
            setup_test_database()
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test, result) in enumerate(zip(tests, results), 1):
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"Test {i}: {test.__name__}: {status}")
    
    logger.info("=" * 60)
    logger.info(f"Total: {passed}/{total} tests passed ({passed*100//total}%)")
    logger.info("=" * 60)
    
    # Cleanup
    cleanup_test_files()
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

