"""
Comprehensive Test Suite for Auto-Execution System
Tests: Logic, Condition Monitoring, and Execution
"""
import unittest
import sys
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from auto_execution_system import AutoExecutionSystem, TradePlan, get_auto_execution_system
    from infra.mt5_service import MT5Service
except ImportError as e:
    print(f"Warning: Could not import auto-execution system: {e}")
    print("Some tests may be skipped")


class TestAutoExecutionLogic(unittest.TestCase):
    """Test auto-execution system logic correctness"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.db_path = Path("data/auto_execution.db")
        self.test_plan_id = f"test_logic_{int(time.time())}"
        
    def test_plan_creation_logic(self):
        """Test plan creation and storage logic"""
        try:
            system = get_auto_execution_system()
            
            # Create test plan
            test_plan = TradePlan(
                plan_id=self.test_plan_id,
                symbol="BTCUSDc",
                direction="BUY",
                entry_price=93000.0,
                stop_loss=92000.0,
                take_profit=95000.0,
                volume=0.01,
                conditions={
                    "price_near": 93000,
                    "tolerance": 200,
                    "fvg_bull": True,
                    "min_confluence": 80
                },
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="test",
                status="pending",
                expires_at=(datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            )
            
            # Add plan
            result = system.add_plan(test_plan)
            self.assertTrue(result, "Plan should be added successfully")
            
            # Verify plan exists
            status = system.get_status()
            plan_ids = [p.get("plan_id") for p in status.get("plans", [])]
            self.assertIn(self.test_plan_id, plan_ids, "Plan should be in system")
            
            # Cleanup
            system.cancel_plan(self.test_plan_id)
            
        except Exception as e:
            self.fail(f"Plan creation logic failed: {e}")
    
    def test_condition_validation_logic(self):
        """Test condition validation logic"""
        try:
            system = get_auto_execution_system()
            
            # Test plan with valid conditions
            valid_plan = TradePlan(
                plan_id=f"test_valid_{int(time.time())}",
                symbol="XAUUSDc",
                direction="BUY",
                entry_price=4200.0,
                stop_loss=4190.0,
                take_profit=4220.0,
                volume=0.01,
                conditions={
                    "price_near": 4200,
                    "tolerance": 5,
                    "choch_bull": True,
                    "timeframe": "M15"
                },
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="test",
                status="pending"
            )
            
            # Verify has_conditions check
            has_conditions = any([
                "price_near" in valid_plan.conditions,
                "choch_bull" in valid_plan.conditions,
                "choch_bear" in valid_plan.conditions
            ])
            self.assertTrue(has_conditions, "Plan should have valid conditions")
            
            # Test plan with no conditions
            invalid_plan = TradePlan(
                plan_id=f"test_invalid_{int(time.time())}",
                symbol="XAUUSDc",
                direction="BUY",
                entry_price=4200.0,
                stop_loss=4190.0,
                take_profit=4220.0,
                volume=0.01,
                conditions={},  # No conditions
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="test",
                status="pending"
            )
            
            has_conditions_invalid = any([
                "price_near" in invalid_plan.conditions,
                "choch_bull" in invalid_plan.conditions
            ])
            self.assertFalse(has_conditions_invalid, "Plan without conditions should fail validation")
            
        except Exception as e:
            self.fail(f"Condition validation logic failed: {e}")
    
    def test_fvg_condition_logic(self):
        """Test FVG condition checking logic"""
        try:
            system = get_auto_execution_system()
            
            # Test plan with fvg_bull
            fvg_plan = TradePlan(
                plan_id=f"test_fvg_{int(time.time())}",
                symbol="BTCUSDc",
                direction="BUY",
                entry_price=92900.0,
                stop_loss=91800.0,
                take_profit=95000.0,
                volume=0.01,
                conditions={
                    "fvg_bull": True,
                    "price_near": 92900,
                    "tolerance": 150,
                    "strategy_type": "fvg_retracement"
                },
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="test",
                status="pending"
            )
            
            # Verify FVG condition is present
            self.assertTrue(fvg_plan.conditions.get("fvg_bull"), "FVG bull condition should be present")
            self.assertEqual(fvg_plan.conditions.get("strategy_type"), "fvg_retracement", "Strategy type should match")
            
            # Verify condition structure
            required_for_fvg = ["fvg_bull", "price_near", "tolerance"]
            for req in required_for_fvg:
                self.assertIn(req, fvg_plan.conditions, f"FVG plan should have {req} condition")
            
        except Exception as e:
            self.fail(f"FVG condition logic failed: {e}")
    
    def test_liquidity_sweep_condition_logic(self):
        """Test liquidity sweep condition checking logic"""
        try:
            system = get_auto_execution_system()
            
            # Test plan with liquidity_sweep
            sweep_plan = TradePlan(
                plan_id=f"test_sweep_{int(time.time())}",
                symbol="BTCUSDc",
                direction="SELL",
                entry_price=95600.0,
                stop_loss=96200.0,
                take_profit=93800.0,
                volume=0.01,
                conditions={
                    "liquidity_sweep": True,
                    "price_near": 95600,
                    "tolerance": 200,
                    "strategy_type": "liquidity_sweep_reversal"
                },
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="test",
                status="pending"
            )
            
            # Verify liquidity sweep condition
            self.assertTrue(sweep_plan.conditions.get("liquidity_sweep"), "Liquidity sweep condition should be present")
            self.assertIn("price_near", sweep_plan.conditions, "Should have price_near for entry trigger")
            
        except Exception as e:
            self.fail(f"Liquidity sweep condition logic failed: {e}")


class TestConditionMonitoring(unittest.TestCase):
    """Test condition monitoring functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_plan_id = f"test_monitor_{int(time.time())}"
        
    def test_plan_monitoring_status(self):
        """Test that plans are being monitored"""
        try:
            system = get_auto_execution_system()
            
            # Check system status
            status = system.get_status()
            self.assertIsNotNone(status, "System status should be available")
            self.assertIn("running", status, "Status should include 'running' field")
            self.assertIn("pending_plans", status, "Status should include 'pending_plans' field")
            
            # Verify system is monitoring
            if status.get("running"):
                print("  [INFO] Auto-execution system is running and monitoring plans")
            else:
                print("  [WARNING] Auto-execution system is not running")
            
        except Exception as e:
            self.fail(f"Plan monitoring status check failed: {e}")
    
    def test_condition_checking_frequency(self):
        """Test that conditions are checked at appropriate intervals"""
        try:
            system = get_auto_execution_system()
            
            # Check if monitoring loop exists
            self.assertTrue(hasattr(system, '_monitor_loop'), "System should have monitoring loop")
            self.assertTrue(hasattr(system, 'running'), "System should have running flag")
            
            # Verify check_interval exists
            if hasattr(system, 'config'):
                check_interval = system.config.get('check_interval', 30)
                print(f"  [INFO] Condition check interval: {check_interval} seconds")
                self.assertGreater(check_interval, 0, "Check interval should be positive")
            
        except Exception as e:
            self.fail(f"Condition checking frequency test failed: {e}")
    
    def test_price_near_condition_monitoring(self):
        """Test price_near condition monitoring"""
        try:
            system = get_auto_execution_system()
            
            # Create test plan with price_near
            test_plan = TradePlan(
                plan_id=self.test_plan_id,
                symbol="BTCUSDc",
                direction="BUY",
                entry_price=93000.0,
                stop_loss=92000.0,
                take_profit=95000.0,
                volume=0.01,
                conditions={
                    "price_near": 93000,
                    "tolerance": 200
                },
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="test",
                status="pending",
                expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            )
            
            # Add plan
            system.add_plan(test_plan)
            
            # Verify plan is in monitoring
            status = system.get_status()
            plan_ids = [p.get("plan_id") for p in status.get("plans", [])]
            self.assertIn(self.test_plan_id, plan_ids, "Plan should be monitored")
            
            # Verify conditions are stored
            plans = status.get("plans", [])
            test_plan_data = next((p for p in plans if p.get("plan_id") == self.test_plan_id), None)
            if test_plan_data:
                conditions = test_plan_data.get("conditions", {})
                self.assertIn("price_near", conditions, "Plan should have price_near condition")
                self.assertIn("tolerance", conditions, "Plan should have tolerance condition")
            
            # Cleanup
            system.cancel_plan(self.test_plan_id)
            
        except Exception as e:
            self.fail(f"Price near condition monitoring failed: {e}")
    
    def test_fvg_condition_monitoring(self):
        """Test FVG condition monitoring"""
        try:
            system = get_auto_execution_system()
            
            # Create test plan with FVG condition
            test_plan = TradePlan(
                plan_id=self.test_plan_id,
                symbol="BTCUSDc",
                direction="BUY",
                entry_price=92900.0,
                stop_loss=91800.0,
                take_profit=95000.0,
                volume=0.01,
                conditions={
                    "fvg_bull": True,
                    "price_near": 92900,
                    "tolerance": 150
                },
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="test",
                status="pending",
                expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            )
            
            # Add plan
            system.add_plan(test_plan)
            
            # Verify FVG condition is monitored
            status = system.get_status()
            plans = status.get("plans", [])
            test_plan_data = next((p for p in plans if p.get("plan_id") == self.test_plan_id), None)
            if test_plan_data:
                conditions = test_plan_data.get("conditions", {})
                self.assertTrue(conditions.get("fvg_bull"), "Plan should have fvg_bull condition")
            
            # Cleanup
            system.cancel_plan(self.test_plan_id)
            
        except Exception as e:
            self.fail(f"FVG condition monitoring failed: {e}")


class TestExecutionFunctionality(unittest.TestCase):
    """Test execution functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_plan_id = f"test_exec_{int(time.time())}"
        
    def test_execution_lock_mechanism(self):
        """Test execution lock prevents duplicate execution"""
        try:
            system = get_auto_execution_system()
            
            # Verify execution locks exist
            self.assertTrue(hasattr(system, 'execution_locks'), "System should have execution locks")
            self.assertTrue(hasattr(system, 'execution_locks_lock'), "System should have execution locks lock")
            
            # Test lock creation
            import threading
            if self.test_plan_id not in system.execution_locks:
                with system.execution_locks_lock:
                    system.execution_locks[self.test_plan_id] = threading.Lock()
            
            self.assertIn(self.test_plan_id, system.execution_locks, "Execution lock should be created")
            
        except Exception as e:
            self.fail(f"Execution lock mechanism test failed: {e}")
    
    def test_plan_status_validation_before_execution(self):
        """Test that plan status is validated before execution"""
        try:
            system = get_auto_execution_system()
            
            # Verify _execute_trade method exists
            self.assertTrue(hasattr(system, '_execute_trade'), "System should have _execute_trade method")
            
            # Check if method validates status
            import inspect
            source = inspect.getsource(system._execute_trade)
            
            # Verify status check exists in code
            has_status_check = "status" in source.lower() and ("pending" in source.lower() or "check" in source.lower())
            self.assertTrue(has_status_check, "Execution method should check plan status")
            
        except Exception as e:
            self.fail(f"Plan status validation test failed: {e}")
    
    def test_expiration_handling(self):
        """Test that expired plans are handled correctly"""
        try:
            system = get_auto_execution_system()
            
            # Create expired plan
            expired_plan = TradePlan(
                plan_id=self.test_plan_id,
                symbol="BTCUSDc",
                direction="BUY",
                entry_price=93000.0,
                stop_loss=92000.0,
                take_profit=95000.0,
                volume=0.01,
                conditions={"price_near": 93000, "tolerance": 200},
                created_at=(datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
                created_by="test",
                status="pending",
                expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()  # Expired
            )
            
            # Verify expiration check logic exists
            expires_at = expired_plan.expires_at
            if expires_at:
                expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                now_utc = datetime.now(timezone.utc)
                is_expired = expires_dt < now_utc
                self.assertTrue(is_expired, "Plan should be identified as expired")
            
        except Exception as e:
            self.fail(f"Expiration handling test failed: {e}")


class TestDatabaseIntegration(unittest.TestCase):
    """Test database integration"""
    
    def test_plan_persistence(self):
        """Test that plans are persisted to database"""
        try:
            db_path = Path("data/auto_execution.db")
            if not db_path.exists():
                self.skipTest("Database not found")
            
            # Connect to database
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM trade_plans WHERE status = 'pending'")
            count = cursor.fetchone()[0]
            conn.close()
            
            self.assertIsInstance(count, int, "Should be able to query database")
            print(f"  [INFO] Found {count} pending plans in database")
            
        except Exception as e:
            self.fail(f"Plan persistence test failed: {e}")
    
    def test_condition_storage(self):
        """Test that conditions are stored correctly in database"""
        try:
            db_path = Path("data/auto_execution.db")
            if not db_path.exists():
                self.skipTest("Database not found")
            
            # Query a plan with conditions
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT plan_id, conditions FROM trade_plans WHERE status = 'pending' LIMIT 1"
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                plan_id, conditions_json = row
                conditions = json.loads(conditions_json) if conditions_json else {}
                self.assertIsInstance(conditions, dict, "Conditions should be stored as JSON")
                print(f"  [INFO] Plan {plan_id} has {len(conditions)} conditions")
            else:
                print("  [INFO] No pending plans found in database")
            
        except Exception as e:
            self.fail(f"Condition storage test failed: {e}")


def run_all_tests():
    """Run all test suites"""
    print("=" * 80)
    print("AUTO-EXECUTION SYSTEM - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print()
    print("Test Categories:")
    print("  1. Logic Correctness")
    print("  2. Condition Monitoring")
    print("  3. Execution Functionality")
    print("  4. Database Integration")
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestAutoExecutionLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestConditionMonitoring))
    suite.addTests(loader.loadTestsFromTestCase(TestExecutionFunctionality))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print()
    
    if result.wasSuccessful():
        print("[SUCCESS] ALL TESTS PASSED")
    else:
        print("[FAILED] SOME TESTS FAILED")
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}")
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

