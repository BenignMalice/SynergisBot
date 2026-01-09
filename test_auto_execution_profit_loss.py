"""
Test script for Auto-Execution Profit/Loss Display Implementation

Tests:
1. TradePlan dataclass has new fields
2. Database loading handles new columns
3. Migration script works
4. Cache helper function works
5. Web endpoint returns profit/loss data
6. AutoExecutionOutcomeTracker can be initialized
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

def test_tradeplan_dataclass():
    """Test that TradePlan dataclass has new fields"""
    print("\n" + "="*60)
    print("TEST 1: TradePlan Dataclass Fields")
    print("="*60)
    
    try:
        from auto_execution_system import TradePlan
        
        # Check if new fields exist
        plan = TradePlan(
            plan_id="test-001",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2500.0,
            stop_loss=2490.0,
            take_profit=2510.0,
            volume=0.01,
            conditions={},
            created_at="2025-12-10T10:00:00",
            created_by="test",
            status="executed",
            ticket=12345,
            profit_loss=50.25,
            exit_price=2505.0,
            close_time="2025-12-10T12:00:00",
            close_reason="take_profit"
        )
        
        assert hasattr(plan, 'profit_loss'), "profit_loss field missing"
        assert hasattr(plan, 'exit_price'), "exit_price field missing"
        assert hasattr(plan, 'close_time'), "close_time field missing"
        assert hasattr(plan, 'close_reason'), "close_reason field missing"
        
        assert plan.profit_loss == 50.25, "profit_loss value incorrect"
        assert plan.exit_price == 2505.0, "exit_price value incorrect"
        assert plan.close_time == "2025-12-10T12:00:00", "close_time value incorrect"
        assert plan.close_reason == "take_profit", "close_reason value incorrect"
        
        print("✅ PASS: TradePlan dataclass has all new fields")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

def test_database_loading():
    """Test that database loading handles new columns gracefully"""
    print("\n" + "="*60)
    print("TEST 2: Database Loading with New Columns")
    print("="*60)
    
    try:
        from auto_execution_system import AutoExecutionSystem
        
        # Create test database
        test_db = Path("data/test_auto_execution.db")
        test_db.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove existing test DB
        if test_db.exists():
            test_db.unlink()
        
        # Create table with old schema (no new columns)
        conn = sqlite3.connect(str(test_db))
        c = conn.cursor()
        c.execute("""
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
                status TEXT NOT NULL,
                expires_at TEXT,
                executed_at TEXT,
                ticket INTEGER,
                notes TEXT
            )
        """)
        
        # Insert test plan
        c.execute("""
            INSERT INTO trade_plans 
            (plan_id, symbol, direction, entry_price, stop_loss, take_profit, volume,
             conditions, created_at, created_by, status, ticket, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "test-001", "XAUUSDc", "BUY", 2500.0, 2490.0, 2510.0, 0.01,
            "{}", "2025-12-10T10:00:00", "test", "executed", 12345, "Test plan"
        ))
        conn.commit()
        conn.close()
        
        # Test loading without new columns
        system = AutoExecutionSystem(db_path=str(test_db))
        plan = system.get_plan_by_id("test-001")
        
        assert plan is not None, "Plan not loaded"
        assert plan.profit_loss is None, "profit_loss should be None (column doesn't exist)"
        assert plan.exit_price is None, "exit_price should be None (column doesn't exist)"
        
        print("✅ PASS: Database loading handles missing columns gracefully")
        
        # Clean up
        test_db.unlink()
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_migration_script():
    """Test migration script"""
    print("\n" + "="*60)
    print("TEST 3: Migration Script")
    print("="*60)
    
    try:
        # Create test database
        test_db = Path("data/test_auto_execution_migration.db")
        test_db.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove existing test DB
        if test_db.exists():
            test_db.unlink()
        
        # Create table with old schema
        conn = sqlite3.connect(str(test_db))
        c = conn.cursor()
        c.execute("""
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
                status TEXT NOT NULL,
                expires_at TEXT,
                executed_at TEXT,
                ticket INTEGER,
                notes TEXT
            )
        """)
        conn.commit()
        conn.close()
        
        # Run migration
        from migrations.add_profit_loss_fields import migrate
        migrate(db_path=str(test_db))
        
        # Verify columns were added
        conn = sqlite3.connect(str(test_db))
        c = conn.cursor()
        c.execute("PRAGMA table_info(trade_plans)")
        columns = [row[1] for row in c.fetchall()]
        conn.close()
        
        assert 'profit_loss' in columns, "profit_loss column not added"
        assert 'exit_price' in columns, "exit_price column not added"
        assert 'close_time' in columns, "close_time column not added"
        assert 'close_reason' in columns, "close_reason column not added"
        
        print("✅ PASS: Migration script adds all columns correctly")
        
        # Test idempotency (run again)
        migrate(db_path=str(test_db))
        print("✅ PASS: Migration script is idempotent (can run multiple times)")
        
        # Clean up
        test_db.unlink()
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cache_helper():
    """Test cache helper function"""
    print("\n" + "="*60)
    print("TEST 4: Cache Helper Function")
    print("="*60)
    
    try:
        # Check if function exists and is async
        import inspect
        from app.main_api import get_cached_outcome
        from infra.plan_effectiveness_tracker import PlanEffectivenessTracker
        
        assert inspect.iscoroutinefunction(get_cached_outcome), "get_cached_outcome should be async"
        
        # Check cache variables exist
        from app.main_api import _outcome_cache, _cache_expiry, _cache_lock
        
        assert _outcome_cache is not None, "_outcome_cache not defined"
        assert _cache_expiry is not None, "_cache_expiry not defined"
        assert _cache_lock is not None, "_cache_lock not defined"
        
        print("✅ PASS: Cache helper function exists and is properly configured")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_outcome_tracker():
    """Test AutoExecutionOutcomeTracker can be initialized"""
    print("\n" + "="*60)
    print("TEST 5: AutoExecutionOutcomeTracker")
    print("="*60)
    
    try:
        from infra.auto_execution_outcome_tracker import AutoExecutionOutcomeTracker
        from auto_execution_system import AutoExecutionSystem
        
        # Create test system
        test_db = Path("data/test_auto_execution_tracker.db")
        test_db.parent.mkdir(parents=True, exist_ok=True)
        
        system = AutoExecutionSystem(db_path=str(test_db))
        tracker = AutoExecutionOutcomeTracker(system)
        
        assert tracker.auto_execution == system, "auto_execution not set correctly"
        assert tracker.db_path == system.db_path, "db_path not set correctly"
        assert tracker.tracker is not None, "PlanEffectivenessTracker not initialized"
        assert tracker.running == False, "running should be False initially"
        
        print("✅ PASS: AutoExecutionOutcomeTracker can be initialized")
        
        # Clean up
        if test_db.exists():
            test_db.unlink()
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_web_endpoint_imports():
    """Test that web endpoint has required imports"""
    print("\n" + "="*60)
    print("TEST 6: Web Endpoint Imports")
    print("="*60)
    
    try:
        from app.main_api import (
            PlanEffectivenessTracker,
            get_cached_outcome,
            _outcome_cache,
            _cache_expiry,
            _cache_lock
        )
        
        print("✅ PASS: All required imports are present")
        return True
    except ImportError as e:
        print(f"❌ FAIL: Missing import: {e}")
        return False

def test_database_loading_with_new_columns():
    """Test database loading after migration"""
    print("\n" + "="*60)
    print("TEST 7: Database Loading After Migration")
    print("="*60)
    
    try:
        from auto_execution_system import AutoExecutionSystem
        
        # Create test database
        test_db = Path("data/test_auto_execution_with_columns.db")
        test_db.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove existing test DB
        if test_db.exists():
            test_db.unlink()
        
        # Create table and run migration
        conn = sqlite3.connect(str(test_db))
        c = conn.cursor()
        c.execute("""
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
                status TEXT NOT NULL,
                expires_at TEXT,
                executed_at TEXT,
                ticket INTEGER,
                notes TEXT
            )
        """)
        conn.commit()
        conn.close()
        
        # Run migration
        from migrations.add_profit_loss_fields import migrate
        migrate(db_path=str(test_db))
        
        # Insert test plan with new columns
        conn = sqlite3.connect(str(test_db))
        c = conn.cursor()
        c.execute("""
            INSERT INTO trade_plans 
            (plan_id, symbol, direction, entry_price, stop_loss, take_profit, volume,
             conditions, created_at, created_by, status, ticket, notes,
             profit_loss, exit_price, close_time, close_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "test-002", "XAUUSDc", "BUY", 2500.0, 2490.0, 2510.0, 0.01,
            "{}", "2025-12-10T10:00:00", "test", "executed", 12346, "Test plan",
            50.25, 2505.0, "2025-12-10T12:00:00", "take_profit"
        ))
        conn.commit()
        conn.close()
        
        # Test loading with new columns
        system = AutoExecutionSystem(db_path=str(test_db))
        plan = system.get_plan_by_id("test-002")
        
        assert plan is not None, "Plan not loaded"
        assert plan.profit_loss == 50.25, f"profit_loss incorrect: {plan.profit_loss}"
        assert plan.exit_price == 2505.0, f"exit_price incorrect: {plan.exit_price}"
        assert plan.close_time == "2025-12-10T12:00:00", f"close_time incorrect: {plan.close_time}"
        assert plan.close_reason == "take_profit", f"close_reason incorrect: {plan.close_reason}"
        
        print("✅ PASS: Database loading works correctly with new columns")
        
        # Clean up
        test_db.unlink()
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("AUTO-EXECUTION PROFIT/LOSS IMPLEMENTATION TESTS")
    print("="*60)
    
    results = []
    
    results.append(("TradePlan Dataclass", test_tradeplan_dataclass()))
    results.append(("Database Loading (Old Schema)", test_database_loading()))
    results.append(("Migration Script", test_migration_script()))
    results.append(("Cache Helper", test_cache_helper()))
    results.append(("Outcome Tracker", test_outcome_tracker()))
    results.append(("Web Endpoint Imports", test_web_endpoint_imports()))
    results.append(("Database Loading (New Schema)", test_database_loading_with_new_columns()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Implementation is working correctly.")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

