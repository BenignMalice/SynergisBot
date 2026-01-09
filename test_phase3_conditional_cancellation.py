"""
Test Suite: Phase 3 - Conditional Cancellation
Tests conditional cancellation logic for auto-execution plans.
"""

import json
import sqlite3
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Mock required modules before importing auto_execution_system
from unittest.mock import MagicMock
import sys

# Mock MetaTrader5
try:
    import MetaTrader5 as mt5
except ImportError:
    sys.modules['MetaTrader5'] = MagicMock()

# Mock requests
try:
    import requests
except ImportError:
    sys.modules['requests'] = MagicMock()

# Mock other potentially missing modules
for module_name in ['infra.mt5_service', 'infra.database_write_queue']:
    if module_name not in sys.modules:
        sys.modules[module_name] = MagicMock()

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestPhase3ConditionalCancellation(unittest.TestCase):
    """Test Phase 3 conditional cancellation functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_db_path = "data/test_auto_execution_phase3.db"
        self.test_config_path = "config/test_auto_execution_adaptive_config.json"
        
        # Clean up old test files (with retry for locked files)
        for _ in range(3):
            try:
                if Path(self.test_db_path).exists():
                    Path(self.test_db_path).unlink()
                if Path(self.test_config_path).exists():
                    Path(self.test_config_path).unlink()
                break
            except (PermissionError, OSError):
                time.sleep(0.1)
        
        # Create test config
        test_config = {
            "cancellation_rules": {
                "price_distance_thresholds": {
                    "BTCUSDc": 0.5,
                    "XAUUSDc": 0.3,
                    "default": 0.5
                },
                "price_distance_cancellation": {
                    "enabled": True,
                    "check_interval_minutes": 5
                },
                "time_based_cancellation": {
                    "enabled": True,
                    "max_age_hours": 24,
                    "price_distance_threshold": 0.3
                },
                "structure_cancellation": {
                    "enabled": True,
                    "check_interval_minutes": 60
                },
                "condition_invalidation": {
                    "enabled": True,
                    "check_interval_minutes": 15
                }
            }
        }
        
        Path(self.test_config_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.test_config_path, 'w') as f:
            json.dump(test_config, f, indent=2)
        
        # Mock MT5Service
        self.mock_mt5_service = Mock()
        self.mock_tick = Mock()
        self.mock_tick.bid = 50000.0
        self.mock_tick.ask = 50000.0
        # Return mock tick for any symbol
        self.mock_mt5_service.get_symbol_tick = Mock(return_value=self.mock_tick)
        
        # Create AutoExecutionSystem with test database
        self.system = AutoExecutionSystem(
            db_path=self.test_db_path,
            check_interval=30,
            mt5_service=self.mock_mt5_service
        )
        
        # Override config for testing - set to full config structure
        self.system._adaptive_config = test_config
    
    def tearDown(self):
        """Clean up test environment"""
        # Stop write queue first
        try:
            if hasattr(self.system, 'db_write_queue') and self.system.db_write_queue:
                self.system.db_write_queue.stop()
                time.sleep(0.2)  # Give time for queue to stop
        except:
            pass
        
        # Close all database connections
        try:
            # Force close any open connections by accessing the database one more time
            if Path(self.test_db_path).exists():
                try:
                    with sqlite3.connect(self.test_db_path, timeout=1.0) as conn:
                        conn.execute("SELECT 1")
                except:
                    pass
        except:
            pass
        
        # Wait a bit for connections to close
        time.sleep(0.2)
        
        # Delete test database
        try:
            if Path(self.test_db_path).exists():
                Path(self.test_db_path).unlink()
        except Exception as e:
            print(f"Warning: Could not delete test database: {e}")
        
        # Delete test config
        try:
            if Path(self.test_config_path).exists():
                Path(self.test_config_path).unlink()
        except:
            pass
    
    def test_1_price_distance_cancellation(self):
        """Test 1: Price distance cancellation - price moves too far from entry"""
        print("\n=== Test 1: Price Distance Cancellation ===")
        
        # Create a plan with entry at 50000
        plan = TradePlan(
            plan_id="test_price_distance_1",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49500.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"price_near": 50000.0, "tolerance": 100.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Set current price to 2% away (should trigger cancellation)
        self.mock_tick.bid = 51000.0  # 2% above entry
        self.mock_tick.ask = 51000.0
        
        result = self.system._check_plan_cancellation_conditions(plan)
        
        self.assertIsNotNone(result, "Should return cancellation result")
        self.assertTrue(result['should_cancel'], "Should cancel when price is too far")
        self.assertEqual(result['priority'], 'medium', "Price distance cancellation is medium priority")
        self.assertIn("Price moved", result['reason'], "Reason should mention price movement")
        print(f"Test 1 passed: {result['reason']}")
    
    def test_2_price_distance_within_threshold(self):
        """Test 2: Price distance within threshold - should not cancel"""
        print("\n=== Test 2: Price Distance Within Threshold ===")
        
        plan = TradePlan(
            plan_id="test_price_distance_2",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49500.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"price_near": 50000.0, "tolerance": 100.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Set current price to 0.3% away (within 0.5% threshold)
        self.mock_tick.bid = 50150.0  # 0.3% above entry
        self.mock_tick.ask = 50150.0
        
        result = self.system._check_plan_cancellation_conditions(plan)
        
        self.assertIsNone(result, "Should not cancel when price is within threshold")
        print("Test 2 passed: Plan not cancelled when price within threshold")
    
    def test_3_time_based_cancellation(self):
        """Test 3: Time-based cancellation - old plan with price far from entry"""
        print("\n=== Test 3: Time-Based Cancellation ===")
        
        # Create a plan that's 25 hours old
        created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        
        plan = TradePlan(
            plan_id="test_time_based_1",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49500.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"price_near": 50000.0, "tolerance": 100.0},
            created_at=created_at.isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Set current price to 0.5% away (above 0.3% threshold)
        self.mock_tick.bid = 50250.0  # 0.5% above entry
        self.mock_tick.ask = 50250.0
        
        result = self.system._check_plan_cancellation_conditions(plan)
        
        self.assertIsNotNone(result, "Should return cancellation result")
        self.assertTrue(result['should_cancel'], "Should cancel old plan with price far from entry")
        self.assertEqual(result['priority'], 'low', "Time-based cancellation is low priority")
        self.assertIn("old", result['reason'].lower(), "Reason should mention plan age")
        print(f"Test 3 passed: {result['reason']}")
    
    def test_4_time_based_within_threshold(self):
        """Test 4: Time-based cancellation - old plan but price near entry"""
        print("\n=== Test 4: Time-Based Cancellation - Price Near Entry ===")
        
        # Create a plan that's 25 hours old
        created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        
        plan = TradePlan(
            plan_id="test_time_based_2",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49500.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"price_near": 50000.0, "tolerance": 100.0},
            created_at=created_at.isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Set current price to 0.2% away (within 0.3% threshold)
        self.mock_tick.bid = 50100.0  # 0.2% above entry
        self.mock_tick.ask = 50100.0
        
        result = self.system._check_plan_cancellation_conditions(plan)
        
        # Should not cancel because price is near entry (even though plan is old)
        self.assertIsNone(result, "Should not cancel old plan when price is near entry")
        print("Test 4 passed: Old plan not cancelled when price near entry")
    
    def test_5_multi_level_entry_price_distance(self):
        """Test 5: Price distance cancellation with multi-level entry"""
        print("\n=== Test 5: Multi-Level Entry Price Distance ===")
        
        plan = TradePlan(
            plan_id="test_multi_level_distance",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,  # Primary entry
            stop_loss=49500.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"price_near": 50000.0, "tolerance": 100.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending",
            entry_levels=[
                {"price": 49900.0, "weight": 1.0},
                {"price": 50000.0, "weight": 1.0},
                {"price": 50100.0, "weight": 1.0}
            ]
        )
        
        # Set current price to 2% away from closest level (50100)
        self.mock_tick.bid = 51100.0  # 2% above closest level
        self.mock_tick.ask = 51100.0
        
        result = self.system._check_plan_cancellation_conditions(plan)
        
        self.assertIsNotNone(result, "Should return cancellation result")
        self.assertTrue(result['should_cancel'], "Should cancel when price is too far from closest entry level")
        print(f"Test 5 passed: {result['reason']}")
    
    def test_6_symbol_specific_threshold(self):
        """Test 6: Symbol-specific price distance threshold"""
        print("\n=== Test 6: Symbol-Specific Threshold ===")
        
        # XAUUSDc has 0.3% threshold (vs 0.5% default)
        plan = TradePlan(
            plan_id="test_symbol_threshold",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2650.0,
            stop_loss=2645.0,
            take_profit=2660.0,
            volume=0.01,
            conditions={"price_near": 2650.0, "tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Set current price to 0.4% away (above 0.3% threshold for XAUUSDc)
        # 2660.6 / 2650.0 - 1 = 0.004 = 0.4%
        self.mock_tick.bid = 2660.6
        self.mock_tick.ask = 2660.6
        
        # Ensure mock returns tick for any symbol (including XAUUSDc normalized)
        self.mock_mt5_service.get_symbol_tick = Mock(return_value=self.mock_tick)
        
        # Debug: Check adaptive config
        thresholds = self.system._adaptive_config.get('price_distance_thresholds', {})
        print(f"Debug: Thresholds in config: {thresholds}")
        print(f"Debug: Plan symbol: {plan.symbol}")
        print(f"Debug: Threshold for {plan.symbol}: {thresholds.get(plan.symbol.upper(), 'NOT FOUND')}")
        
        result = self.system._check_plan_cancellation_conditions(plan)
        
        # Debug: Check if tick was retrieved
        if result is None:
            # Check if tick retrieval failed
            calls = self.mock_mt5_service.get_symbol_tick.call_args_list
            print(f"Debug: get_symbol_tick called {len(calls)} times")
            if calls:
                print(f"Debug: Last call args: {calls[-1]}")
            print(f"Debug: Current price: {self.mock_tick.bid}, Entry: {plan.entry_price}")
            print(f"Debug: Distance: {abs(self.mock_tick.bid - plan.entry_price) / plan.entry_price * 100.0:.2f}%")
        
        self.assertIsNotNone(result, "Should return cancellation result")
        self.assertTrue(result['should_cancel'], "Should cancel XAUUSDc plan when price > 0.3% away")
        print(f"Test 6 passed: {result['reason']}")
    
    def test_7_last_cancellation_check_tracking(self):
        """Test 7: Last cancellation check timestamp tracking"""
        print("\n=== Test 7: Last Cancellation Check Tracking ===")
        
        plan = TradePlan(
            plan_id="test_check_tracking",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49500.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"price_near": 50000.0, "tolerance": 100.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending",
            last_cancellation_check=None
        )
        
        # First check - should update last_cancellation_check
        result1 = self.system._check_plan_cancellation_conditions(plan)
        
        # Check that last_cancellation_check was updated
        self.assertIsNotNone(plan.last_cancellation_check, "Should update last_cancellation_check timestamp")
        print(f"Test 7 passed: last_cancellation_check updated to {plan.last_cancellation_check}")
    
    def test_8_cancellation_reason_storage(self):
        """Test 8: Cancellation reason is stored in database"""
        print("\n=== Test 8: Cancellation Reason Storage ===")
        
        # Create and add a plan
        plan = TradePlan(
            plan_id="test_reason_storage",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49500.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"price_near": 50000.0, "tolerance": 100.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        self.system.add_plan(plan)
        
        # Cancel with reason
        cancellation_reason = "Test cancellation reason"
        
        # Temporarily disable write queue to test fallback path (which includes cancellation_reason)
        original_queue = self.system.db_write_queue
        self.system.db_write_queue = None
        
        result = self.system.cancel_plan(plan.plan_id, cancellation_reason)
        
        # Restore write queue
        self.system.db_write_queue = original_queue
        
        self.assertTrue(result, "Should successfully cancel plan")
        
        # Check database
        with sqlite3.connect(self.test_db_path) as conn:
            cursor = conn.execute(
                "SELECT status, cancellation_reason FROM trade_plans WHERE plan_id = ?",
                (plan.plan_id,)
            )
            row = cursor.fetchone()
            if row:
                status, stored_reason = row
                print(f"Debug: Plan status: {status}, cancellation_reason: {stored_reason}")
                self.assertEqual(stored_reason, cancellation_reason, "Cancellation reason should be stored")
                print(f"Test 8 passed: Cancellation reason stored: {stored_reason}")
            else:
                self.fail("Plan not found in database")


def run_tests():
    """Run all tests"""
    print("=" * 70)
    print("Phase 3: Conditional Cancellation - Test Suite")
    print("=" * 70)
    
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPhase3ConditionalCancellation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    if result.wasSuccessful():
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())

