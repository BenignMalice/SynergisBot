"""
Test Suite: Phase 4 - Re-evaluation Triggers
Tests automatic re-evaluation trigger system for auto-execution plans.
"""

import unittest
import sqlite3
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Mock MetaTrader5 before importing
sys.modules['MetaTrader5'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['numpy'] = MagicMock()

from auto_execution_system import AutoExecutionSystem, TradePlan

class TestPhase4ReEvaluationTriggers(unittest.TestCase):
    """Test Phase 4 re-evaluation trigger functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Use test database
        self.test_db = "data/test_auto_execution_phase4.db"
        
        # Remove existing test database
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass
        
        # Create test database directory
        os.makedirs("data", exist_ok=True)
        
        # Initialize system with test database
        self.system = AutoExecutionSystem(
            db_path=self.test_db,
            check_interval=30
        )
        
        # Mock MT5 service
        self.mock_mt5 = Mock()
        self.system.mt5_service = self.mock_mt5
        
        # Mock tick data
        self.mock_tick = Mock()
        self.mock_tick.bid = 50000.0
        self.mock_tick.ask = 50010.0
        self.mock_mt5.get_symbol_tick.return_value = self.mock_tick
        self.mock_mt5.connect.return_value = True
        
        # Load adaptive config
        self.system._adaptive_config = {
            're_evaluation_rules': {
                'enabled': True,
                'price_movement_threshold': 0.2,
                'time_based_trigger_hours': 4,
                'cooldown_minutes': 60,
                'daily_limit': 6
            }
        }
    
    def tearDown(self):
        """Clean up test environment"""
        try:
            # Stop system
            if hasattr(self.system, 'stop'):
                self.system.stop()
            
            # Close database connections
            if hasattr(self.system, 'db_write_queue') and self.system.db_write_queue:
                self.system.db_write_queue.stop()
            
            # Remove test database
            if os.path.exists(self.test_db):
                # Wait a bit for file locks to release
                import time
                time.sleep(0.1)
                try:
                    os.remove(self.test_db)
                except PermissionError:
                    # File may still be locked, try again
                    time.sleep(0.5)
                    try:
                        os.remove(self.test_db)
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error cleaning up test files: {e}")
    
    def create_test_plan(self, entry_price: float = 50000.0, direction: str = "BUY", 
                        created_hours_ago: float = 0.0, last_re_eval_hours_ago: Optional[float] = None,
                        re_eval_count: int = 0, re_eval_date: Optional[str] = None) -> TradePlan:
        """Create a test trade plan"""
        now = datetime.now(timezone.utc)
        created_at = (now - timedelta(hours=created_hours_ago)).isoformat()
        
        plan = TradePlan(
            plan_id="test_plan_001",
            symbol="BTCUSDc",
            direction=direction,
            entry_price=entry_price,
            stop_loss=entry_price * 0.98,
            take_profit=entry_price * 1.02,
            volume=0.01,
            conditions={"price_near": entry_price, "tolerance": 100.0},
            created_at=created_at,
            created_by="test",
            status="pending",
            last_re_evaluation=(now - timedelta(hours=last_re_eval_hours_ago)).isoformat() if last_re_eval_hours_ago is not None else None,
            re_evaluation_count_today=re_eval_count,
            re_evaluation_count_date=re_eval_date or now.date().isoformat()
        )
        
        # Add to system
        with self.system.plans_lock:
            self.system.plans[plan.plan_id] = plan
        
        return plan
    
    def test_1_price_movement_trigger(self):
        """Test 1: Price movement trigger fires when price moves >threshold"""
        print("\n=== Test 1: Price Movement Trigger ===")
        
        # Create plan at 50000
        plan = self.create_test_plan(entry_price=50000.0)
        
        # Set current price to 50100 (0.2% away - should trigger)
        self.mock_tick.bid = 50100.0
        self.mock_tick.ask = 50110.0
        
        # Check if trigger should fire
        should_trigger = self.system._should_trigger_re_evaluation(plan)
        
        self.assertTrue(should_trigger, "Should trigger re-evaluation when price moves >0.2%")
        print("✅ Price movement trigger works correctly")
    
    def test_2_price_movement_no_trigger(self):
        """Test 2: Price movement trigger does NOT fire when price moves <threshold"""
        print("\n=== Test 2: Price Movement No Trigger ===")
        
        # Create plan at 50000
        plan = self.create_test_plan(entry_price=50000.0)
        
        # Set current price to 50050 (0.1% away - should NOT trigger)
        self.mock_tick.bid = 50050.0
        self.mock_tick.ask = 50060.0
        
        # Check if trigger should fire
        should_trigger = self.system._should_trigger_re_evaluation(plan)
        
        self.assertFalse(should_trigger, "Should NOT trigger re-evaluation when price moves <0.2%")
        print("✅ Price movement threshold correctly prevents trigger")
    
    def test_3_time_based_trigger(self):
        """Test 3: Time-based trigger fires after 4 hours"""
        print("\n=== Test 3: Time-Based Trigger ===")
        
        # Create plan that was last re-evaluated 5 hours ago
        plan = self.create_test_plan(
            entry_price=50000.0,
            last_re_eval_hours_ago=5.0
        )
        
        # Set current price close to entry (no price movement trigger)
        self.mock_tick.bid = 50010.0
        self.mock_tick.ask = 50020.0
        
        # Check if trigger should fire
        should_trigger = self.system._should_trigger_re_evaluation(plan)
        
        self.assertTrue(should_trigger, "Should trigger re-evaluation after 4 hours")
        print("✅ Time-based trigger works correctly")
    
    def test_4_time_based_no_trigger(self):
        """Test 4: Time-based trigger does NOT fire before 4 hours"""
        print("\n=== Test 4: Time-Based No Trigger ===")
        
        # Create plan that was last re-evaluated 2 hours ago
        plan = self.create_test_plan(
            entry_price=50000.0,
            last_re_eval_hours_ago=2.0
        )
        
        # Set current price close to entry (no price movement trigger)
        self.mock_tick.bid = 50010.0
        self.mock_tick.ask = 50020.0
        
        # Check if trigger should fire
        should_trigger = self.system._should_trigger_re_evaluation(plan)
        
        self.assertFalse(should_trigger, "Should NOT trigger re-evaluation before 4 hours")
        print("✅ Time-based threshold correctly prevents trigger")
    
    def test_5_cooldown_enforcement(self):
        """Test 5: Cooldown prevents re-evaluation within 60 minutes"""
        print("\n=== Test 5: Cooldown Enforcement ===")
        
        # Create plan that was re-evaluated 30 minutes ago (within cooldown)
        plan = self.create_test_plan(
            entry_price=50000.0,
            last_re_eval_hours_ago=0.5  # 30 minutes
        )
        
        # Set current price to trigger price movement
        self.mock_tick.bid = 50100.0
        self.mock_tick.ask = 50110.0
        
        # Check if trigger should fire (should be blocked by cooldown)
        should_trigger = self.system._should_trigger_re_evaluation(plan)
        
        self.assertFalse(should_trigger, "Should NOT trigger re-evaluation during cooldown")
        print("✅ Cooldown correctly prevents re-evaluation")
    
    def test_6_daily_limit_enforcement(self):
        """Test 6: Daily limit prevents re-evaluation after 6 evaluations"""
        print("\n=== Test 6: Daily Limit Enforcement ===")
        
        # Create plan that has been re-evaluated 6 times today (at limit)
        today = datetime.now(timezone.utc).date().isoformat()
        plan = self.create_test_plan(
            entry_price=50000.0,
            last_re_eval_hours_ago=2.0,  # Outside cooldown
            re_eval_count=6,  # At daily limit
            re_eval_date=today
        )
        
        # Set current price to trigger price movement
        self.mock_tick.bid = 50100.0
        self.mock_tick.ask = 50110.0
        
        # Check if trigger should fire (should be blocked by daily limit)
        should_trigger = self.system._should_trigger_re_evaluation(plan)
        
        self.assertFalse(should_trigger, "Should NOT trigger re-evaluation at daily limit")
        print("✅ Daily limit correctly prevents re-evaluation")
    
    def test_7_re_evaluation_tracking(self):
        """Test 7: Re-evaluation updates tracking fields"""
        print("\n=== Test 7: Re-evaluation Tracking ===")
        
        # Create plan
        plan = self.create_test_plan(
            entry_price=50000.0,
            re_eval_count=2,
            re_eval_date=datetime.now(timezone.utc).date().isoformat()
        )
        
        # Set current price to trigger
        self.mock_tick.bid = 50100.0
        self.mock_tick.ask = 50110.0
        
        # Perform re-evaluation
        result = self.system._re_evaluate_plan(plan, force=True)
        
        # Check result
        self.assertEqual(result.get('action'), 'keep', "Re-evaluation should return action")
        self.assertIsNotNone(plan.last_re_evaluation, "last_re_evaluation should be set")
        self.assertEqual(plan.re_evaluation_count_today, 3, "re_evaluation_count_today should increment")
        print("✅ Re-evaluation tracking works correctly")
    
    def test_8_re_evaluation_status(self):
        """Test 8: Re-evaluation status method returns correct information"""
        print("\n=== Test 8: Re-evaluation Status ===")
        
        # Create plan re-evaluated 30 minutes ago
        plan = self.create_test_plan(
            entry_price=50000.0,
            last_re_eval_hours_ago=0.5,  # 30 minutes
            re_eval_count=3,
            re_eval_date=datetime.now(timezone.utc).date().isoformat()
        )
        
        # Get status
        status = self.system.get_plan_re_evaluation_status(plan)
        
        # Check status fields
        self.assertTrue(status.get('success'), "Status should be successful")
        self.assertIsNotNone(status.get('last_re_evaluation'), "Should have last_re_evaluation")
        self.assertEqual(status.get('re_evaluation_count_today'), 3, "Should have correct count")
        self.assertGreater(status.get('re_evaluation_cooldown_remaining', 0), 0, "Should have cooldown remaining")
        self.assertFalse(status.get('re_evaluation_available'), "Should not be available (in cooldown)")
        print("✅ Re-evaluation status method works correctly")
    
    def test_9_first_re_evaluation_trigger(self):
        """Test 9: First re-evaluation triggers after plan age >= 4 hours"""
        print("\n=== Test 9: First Re-evaluation Trigger ===")
        
        # Create plan created 5 hours ago, never re-evaluated
        plan = self.create_test_plan(
            entry_price=50000.0,
            created_hours_ago=5.0,
            last_re_eval_hours_ago=None  # Never re-evaluated
        )
        
        # Set current price close to entry (no price movement trigger)
        self.mock_tick.bid = 50010.0
        self.mock_tick.ask = 50020.0
        
        # Check if trigger should fire
        should_trigger = self.system._should_trigger_re_evaluation(plan)
        
        self.assertTrue(should_trigger, "Should trigger first re-evaluation after 4 hours")
        print("✅ First re-evaluation trigger works correctly")
    
    def test_10_multi_level_entry_price_distance(self):
        """Test 10: Price movement trigger uses closest entry level for multi-level plans"""
        print("\n=== Test 10: Multi-Level Entry Price Distance ===")
        
        # Create plan with multiple entry levels, created 5 hours ago (to allow time-based trigger)
        plan = self.create_test_plan(
            entry_price=50000.0,
            created_hours_ago=5.0,
            last_re_eval_hours_ago=5.0  # Re-evaluated 5 hours ago (outside cooldown)
        )
        plan.entry_levels = [
            {"price": 50000.0, "weight": 1.0},
            {"price": 50100.0, "weight": 0.5},
            {"price": 50200.0, "weight": 0.3}
        ]
        
        # Set current price to 50300 (0.4% from closest level 50100 - should trigger)
        # Distance: 50300 - 50100 = 200, Percentage: 200 / 50100 * 100 = 0.399% > 0.2% threshold
        self.mock_tick.bid = 50300.0
        self.mock_tick.ask = 50310.0
        
        # Check if trigger should fire
        should_trigger = self.system._should_trigger_re_evaluation(plan)
        
        self.assertTrue(should_trigger, "Should trigger using closest entry level")
        print("✅ Multi-level entry price distance calculation works correctly")

if __name__ == "__main__":
    # Set UTF-8 encoding for Windows
    import sys
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    # Set environment variable for encoding
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # Run tests
    unittest.main(verbosity=2)

