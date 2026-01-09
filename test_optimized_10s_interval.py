"""
Test Script for Optimized 10-Second Interval Implementation
Tests all phases of the optimized interval system
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Mock MetaTrader5 before importing auto_execution_system
try:
    import MetaTrader5 as mt5
except ImportError:
    # Create a mock MT5 module
    class MockMT5:
        @staticmethod
        def symbol_info_tick(symbol):
            class MockTick:
                def __init__(self):
                    self.bid = 90000.0
                    self.ask = 90001.0
            return MockTick()
    
    import sys
    sys.modules['MetaTrader5'] = MockMT5()
    mt5 = MockMT5()

try:
    from auto_execution_system import AutoExecutionSystem, TradePlan
except ImportError as e:
    print(f"ERROR: Could not import auto_execution_system: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


def print_section(title: str):
    """Print a section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_status(message: str, status: str = "INFO"):
    """Print a status message"""
    symbols = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARNING": "⚠️",
        "TEST": "🧪"
    }
    symbol = symbols.get(status, "•")
    print(f"{symbol} {message}")


def test_config_loading():
    """Test Phase 1.1: Config loading"""
    print_section("TEST 1: Config Loading")
    
    try:
        # Create test config file
        config_dir = Path("config")
        config_dir.mkdir(exist_ok=True)
        config_path = config_dir / "auto_execution_optimized_intervals.json"
        
        test_config = {
            "optimized_intervals": {
                "adaptive_intervals": {
                    "enabled": True,
                    "default_interval_seconds": 30,
                    "plan_type_intervals": {
                        "m1_micro_scalp": {
                            "base_interval_seconds": 10,
                            "far_interval_seconds": 30,
                            "close_interval_seconds": 5,
                            "price_proximity_multiplier": 2.0
                        }
                    }
                },
                "smart_caching": {
                    "enabled": True,
                    "m1_cache_ttl_seconds": 20,
                    "invalidate_on_candle_close": True,
                    "prefetch_seconds_before_expiry": 3
                },
                "conditional_checks": {
                    "enabled": True,
                    "price_proximity_filter": True,
                    "proximity_multiplier": 2.0,
                    "min_check_interval_seconds": 10
                },
                "batch_operations": {
                    "enabled": True,
                    "mt5_batch_size": 5,
                    "db_batch_size": 10
                }
            }
        }
        
        # Write test config
        with open(config_path, 'w') as f:
            json.dump(test_config, f, indent=2)
        print_status(f"Created test config file: {config_path}", "INFO")
        
        # Initialize system (should load config)
        system = AutoExecutionSystem()
        
        # Verify config was loaded
        opt_config = system.config.get('optimized_intervals', {})
        if not opt_config:
            print_status("FAILED: optimized_intervals config not found", "ERROR")
            return False
        
        # Verify adaptive intervals config
        adaptive = opt_config.get('adaptive_intervals', {})
        if not adaptive.get('enabled'):
            print_status("FAILED: adaptive_intervals not enabled in config", "ERROR")
            return False
        
        print_status("Config loaded successfully", "SUCCESS")
        print_status(f"  Adaptive intervals enabled: {adaptive.get('enabled')}", "INFO")
        print_status(f"  Smart caching enabled: {opt_config.get('smart_caching', {}).get('enabled')}", "INFO")
        print_status(f"  Conditional checks enabled: {opt_config.get('conditional_checks', {}).get('enabled')}", "INFO")
        
        # Cleanup
        if config_path.exists():
            config_path.unlink()
            print_status("Cleaned up test config file", "INFO")
        
        return True
        
    except Exception as e:
        print_status(f"ERROR: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


def test_plan_type_detection():
    """Test Phase 1.2: Plan type detection"""
    print_section("TEST 2: Plan Type Detection")
    
    try:
        system = AutoExecutionSystem()
        
        # Test M1 micro-scalp detection
        m1_plan = TradePlan(
            plan_id="test_m1",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90000.0,
            stop_loss=89900.0,
            take_profit=90100.0,
            volume=0.01,
            conditions={
                "timeframe": "M1",
                "liquidity_sweep": True,
                "price_near": 90000.0,
                "tolerance": 50.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        plan_type = system._detect_plan_type(m1_plan)
        if plan_type != "m1_micro_scalp":
            print_status(f"FAILED: Expected 'm1_micro_scalp', got '{plan_type}'", "ERROR")
            return False
        
        print_status(f"M1 micro-scalp detected correctly: {plan_type}", "SUCCESS")
        
        # Test M5 range scalp detection
        m5_plan = TradePlan(
            plan_id="test_m5",
            symbol="XAUUSDc",
            direction="SELL",
            entry_price=2400.0,
            stop_loss=2405.0,
            take_profit=2395.0,
            volume=0.01,
            conditions={
                "timeframe": "M5",
                "range_scalp_confluence": 70,
                "price_near": 2400.0,
                "tolerance": 5.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending",
            notes="Mean reversion range scalp"
        )
        
        plan_type = system._detect_plan_type(m5_plan)
        if plan_type != "m5_range_scalp":
            print_status(f"FAILED: Expected 'm5_range_scalp', got '{plan_type}'", "ERROR")
            return False
        
        print_status(f"M5 range scalp detected correctly: {plan_type}", "SUCCESS")
        
        # Test default plan type
        default_plan = TradePlan(
            plan_id="test_default",
            symbol="EURUSDc",
            direction="BUY",
            entry_price=1.1000,
            stop_loss=1.0990,
            take_profit=1.1010,
            volume=0.01,
            conditions={
                "timeframe": "M15",
                "price_near": 1.1000,
                "tolerance": 0.0005
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        plan_type = system._detect_plan_type(default_plan)
        if plan_type != "default":
            print_status(f"FAILED: Expected 'default', got '{plan_type}'", "ERROR")
            return False
        
        print_status(f"Default plan type detected correctly: {plan_type}", "SUCCESS")
        
        return True
        
    except Exception as e:
        print_status(f"ERROR: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


def test_adaptive_interval_calculation():
    """Test Phase 2.1: Adaptive interval calculation"""
    print_section("TEST 3: Adaptive Interval Calculation")
    
    try:
        system = AutoExecutionSystem()
        
        # Enable adaptive intervals in config
        system.config['optimized_intervals'] = {
            'adaptive_intervals': {
                'enabled': True,
                'plan_type_intervals': {
                    'm1_micro_scalp': {
                        'base_interval_seconds': 10,
                        'far_interval_seconds': 30,
                        'close_interval_seconds': 5,
                        'price_proximity_multiplier': 2.0
                    }
                }
            }
        }
        
        # Create M1 micro-scalp plan
        plan = TradePlan(
            plan_id="test_adaptive",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90000.0,
            stop_loss=89900.0,
            take_profit=90100.0,
            volume=0.01,
            conditions={
                "timeframe": "M1",
                "liquidity_sweep": True,
                "price_near": 90000.0,
                "tolerance": 50.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Test close interval (price within tolerance)
        current_price = 90000.0  # Exactly at entry
        interval = system._calculate_adaptive_interval(plan, current_price)
        if interval != 5:
            print_status(f"FAILED: Expected close interval 5s, got {interval}s", "ERROR")
            return False
        print_status(f"Close interval (price at entry): {interval}s", "SUCCESS")
        
        # Test base interval (price within 2× tolerance)
        current_price = 90050.0  # Within 2× tolerance (100)
        interval = system._calculate_adaptive_interval(plan, current_price)
        if interval != 10:
            print_status(f"FAILED: Expected base interval 10s, got {interval}s", "ERROR")
            return False
        print_status(f"Base interval (price within 2× tolerance): {interval}s", "SUCCESS")
        
        # Test far interval (price far from entry)
        current_price = 90200.0  # Far from entry (> 2× tolerance)
        interval = system._calculate_adaptive_interval(plan, current_price)
        if interval != 30:
            print_status(f"FAILED: Expected far interval 30s, got {interval}s", "ERROR")
            return False
        print_status(f"Far interval (price far from entry): {interval}s", "SUCCESS")
        
        # Test disabled adaptive intervals
        system.config['optimized_intervals']['adaptive_intervals']['enabled'] = False
        interval = system._calculate_adaptive_interval(plan, current_price)
        if interval != system.check_interval:
            print_status(f"FAILED: Expected default interval {system.check_interval}s when disabled, got {interval}s", "ERROR")
            return False
        print_status(f"Default interval when disabled: {interval}s", "SUCCESS")
        
        return True
        
    except Exception as e:
        print_status(f"ERROR: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


def test_conditional_checks():
    """Test Phase 4: Conditional checks"""
    print_section("TEST 4: Conditional Checks")
    
    try:
        system = AutoExecutionSystem()
        
        # Enable conditional checks
        system.config['optimized_intervals'] = {
            'conditional_checks': {
                'enabled': True,
                'price_proximity_filter': True,
                'proximity_multiplier': 2.0,
                'min_check_interval_seconds': 10
            }
        }
        
        plan = TradePlan(
            plan_id="test_conditional",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90000.0,
            stop_loss=89900.0,
            take_profit=90100.0,
            volume=0.01,
            conditions={
                "price_near": 90000.0,
                "tolerance": 50.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Test: Price within 2× tolerance (should check)
        current_price = 90050.0  # Within 2× tolerance (100)
        should_check = system._should_check_plan(plan, current_price)
        if not should_check:
            print_status("FAILED: Should check plan when price within 2× tolerance", "ERROR")
            return False
        print_status("Price within 2× tolerance: Should check ✓", "SUCCESS")
        
        # Test: Price far from entry (should skip)
        current_price = 90500.0  # Far from entry (> 2× tolerance)
        should_check = system._should_check_plan(plan, current_price)
        if should_check:
            print_status("FAILED: Should skip plan when price far from entry", "ERROR")
            return False
        print_status("Price far from entry: Should skip ✓", "SUCCESS")
        
        # Test: Conditional checks disabled (should always check)
        system.config['optimized_intervals']['conditional_checks']['enabled'] = False
        should_check = system._should_check_plan(plan, current_price)
        if not should_check:
            print_status("FAILED: Should always check when conditional checks disabled", "ERROR")
            return False
        print_status("Conditional checks disabled: Always check ✓", "SUCCESS")
        
        return True
        
    except Exception as e:
        print_status(f"ERROR: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


def test_tracking_dicts():
    """Test Phase 1.2: Tracking dictionaries"""
    print_section("TEST 5: Tracking Dictionaries")
    
    try:
        system = AutoExecutionSystem()
        
        # Verify tracking dicts are initialized
        if not hasattr(system, '_plan_types'):
            print_status("FAILED: _plan_types dict not initialized", "ERROR")
            return False
        print_status("_plan_types dict initialized", "SUCCESS")
        
        if not hasattr(system, '_plan_last_check'):
            print_status("FAILED: _plan_last_check dict not initialized", "ERROR")
            return False
        print_status("_plan_last_check dict initialized", "SUCCESS")
        
        if not hasattr(system, '_plan_last_price'):
            print_status("FAILED: _plan_last_price dict not initialized", "ERROR")
            return False
        print_status("_plan_last_price dict initialized", "SUCCESS")
        
        if not hasattr(system, '_m1_latest_candle_times'):
            print_status("FAILED: _m1_latest_candle_times dict not initialized", "ERROR")
            return False
        print_status("_m1_latest_candle_times dict initialized", "SUCCESS")
        
        if not hasattr(system, 'prefetch_thread'):
            print_status("FAILED: prefetch_thread not initialized", "ERROR")
            return False
        print_status("prefetch_thread initialized", "SUCCESS")
        
        # Test plan type caching
        plan = TradePlan(
            plan_id="test_tracking",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90000.0,
            stop_loss=89900.0,
            take_profit=90100.0,
            volume=0.01,
            conditions={
                "timeframe": "M1",
                "liquidity_sweep": True
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # First call should detect and cache
        plan_type1 = system._detect_plan_type(plan)
        if plan.plan_id not in system._plan_types:
            print_status("FAILED: Plan type not cached after detection", "ERROR")
            return False
        print_status("Plan type cached after detection", "SUCCESS")
        
        # Second call should use cache
        plan_type2 = system._detect_plan_type(plan)
        if plan_type1 != plan_type2:
            print_status("FAILED: Cached plan type doesn't match", "ERROR")
            return False
        print_status("Plan type retrieved from cache", "SUCCESS")
        
        return True
        
    except Exception as e:
        print_status(f"ERROR: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("  OPTIMIZED 10-SECOND INTERVAL IMPLEMENTATION - TEST SUITE")
    print("=" * 70)
    print("\nThis test suite verifies:")
    print("  1. Config loading and integration")
    print("  2. Plan type detection")
    print("  3. Adaptive interval calculation")
    print("  4. Conditional checks")
    print("  5. Tracking dictionaries")
    
    print("\nStarting tests in 2 seconds...")
    time.sleep(2)
    
    results = {}
    
    # Run tests
    results["config_loading"] = test_config_loading()
    results["plan_type_detection"] = test_plan_type_detection()
    results["adaptive_interval"] = test_adaptive_interval_calculation()
    results["conditional_checks"] = test_conditional_checks()
    results["tracking_dicts"] = test_tracking_dicts()
    
    # Summary
    print_section("TEST SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {total_tests - passed_tests} ❌")
    
    print("\nDetailed Results:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    if all(results.values()):
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n⚠️ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
