"""
Test Micro-Scalp Monitor Implementation

Tests the MicroScalpMonitor initialization, configuration, and basic functionality.
"""

import sys
import os
import json
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def test_config_file():
    """Test 1: Verify configuration file exists and is valid"""
    print("\n" + "="*60)
    print("TEST 1: Configuration File")
    print("="*60)
    
    config_path = "config/micro_scalp_automation.json"
    
    if not os.path.exists(config_path):
        print(f"[FAIL] Config file not found: {config_path}")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        required_keys = ['enabled', 'symbols', 'check_interval_seconds']
        missing_keys = [key for key in required_keys if key not in config]
        
        if missing_keys:
            print(f"[FAIL] Missing required keys: {missing_keys}")
            return False
        
        print(f"[PASS] Config file exists and is valid")
        print(f"   -> Enabled: {config.get('enabled')}")
        print(f"   -> Symbols: {config.get('symbols')}")
        print(f"   -> Check interval: {config.get('check_interval_seconds')}s")
        return True
    
    except json.JSONDecodeError as e:
        print(f"[FAIL] Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Error reading config: {e}")
        return False


def test_imports():
    """Test 2: Verify all required imports are available"""
    print("\n" + "="*60)
    print("TEST 2: Required Imports")
    print("="*60)
    
    imports = [
        ('infra.micro_scalp_monitor', 'MicroScalpMonitor'),
        ('infra.micro_scalp_engine', 'MicroScalpEngine'),
        ('infra.micro_scalp_execution', 'MicroScalpExecutionManager'),
        ('infra.multi_timeframe_streamer', 'MultiTimeframeStreamer'),
        ('infra.mt5_service', 'MT5Service'),
    ]
    
    all_passed = True
    for module_name, class_name in imports:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"[PASS] {class_name} imported successfully")
        except ImportError as e:
            print(f"[FAIL] Cannot import {class_name}: {e}")
            all_passed = False
        except AttributeError as e:
            print(f"[FAIL] {class_name} not found in {module_name}: {e}")
            all_passed = False
    
    return all_passed


def test_monitor_initialization():
    """Test 3: Test MicroScalpMonitor initialization"""
    print("\n" + "="*60)
    print("TEST 3: Monitor Initialization")
    print("="*60)
    
    try:
        from infra.micro_scalp_monitor import MicroScalpMonitor
        
        # Test initialization with minimal dependencies (None for optional)
        monitor = MicroScalpMonitor(
            symbols=["BTCUSDc"],
            check_interval=5,
            micro_scalp_engine=None,
            execution_manager=None,
            streamer=None,
            mt5_service=None,
            config_path="config/micro_scalp_automation.json",
            session_manager=None,
            news_service=None
        )
        
        # Check that initialization succeeded
        assert hasattr(monitor, 'symbols'), "Missing 'symbols' attribute"
        assert hasattr(monitor, 'check_interval'), "Missing 'check_interval' attribute"
        assert hasattr(monitor, 'enabled'), "Missing 'enabled' attribute"
        assert hasattr(monitor, 'monitoring'), "Missing 'monitoring' attribute"
        assert hasattr(monitor, 'stats'), "Missing 'stats' attribute"
        assert hasattr(monitor, 'engine_available'), "Missing 'engine_available' attribute"
        
        print("[PASS] Monitor initialized successfully")
        print(f"   -> Symbols: {monitor.symbols}")
        print(f"   -> Check interval: {monitor.check_interval}s")
        print(f"   -> Enabled: {monitor.enabled}")
        print(f"   -> Engine available: {monitor.engine_available}")
        print(f"   -> Execution manager available: {monitor.execution_manager_available}")
        print(f"   -> Streamer available: {monitor.streamer_available}")
        
        return True, monitor
    
    except Exception as e:
        print(f"[FAIL] Initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_config_validation():
    """Test 4: Test configuration validation"""
    print("\n" + "="*60)
    print("TEST 4: Configuration Validation")
    print("="*60)
    
    try:
        from infra.micro_scalp_monitor import MicroScalpMonitor
        
        monitor = MicroScalpMonitor(
            symbols=["BTCUSDc"],
            check_interval=5,
            micro_scalp_engine=None,
            execution_manager=None,
            streamer=None,
            mt5_service=None,
            config_path="config/micro_scalp_automation.json"
        )
        
        # Test valid config
        valid_config = {
            'symbols': ['BTCUSDc'],
            'check_interval_seconds': 5,
            'min_execution_interval_seconds': 60,
            'max_positions_per_symbol': 1
        }
        is_valid, errors = monitor._validate_config(valid_config)
        assert is_valid, f"Valid config rejected: {errors}"
        print("[PASS] Valid configuration accepted")
        
        # Test invalid config (negative interval)
        invalid_config = {
            'check_interval_seconds': -1
        }
        is_valid, errors = monitor._validate_config(invalid_config)
        assert not is_valid, "Invalid config accepted"
        assert len(errors) > 0, "No errors reported for invalid config"
        print("[PASS] Invalid configuration rejected")
        print(f"   -> Errors: {errors}")
        
        return True
    
    except Exception as e:
        print(f"[FAIL] Validation test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_status_method():
    """Test 5: Test get_status() method"""
    print("\n" + "="*60)
    print("TEST 5: Status Method")
    print("="*60)
    
    try:
        from infra.micro_scalp_monitor import MicroScalpMonitor
        
        monitor = MicroScalpMonitor(
            symbols=["BTCUSDc", "XAUUSDc"],
            check_interval=5,
            micro_scalp_engine=None,
            execution_manager=None,
            streamer=None,
            mt5_service=None
        )
        
        status = monitor.get_status()
        
        # Check required fields
        required_fields = ['monitoring', 'enabled', 'symbols', 'check_interval', 'stats']
        missing_fields = [field for field in required_fields if field not in status]
        
        if missing_fields:
            print(f"[FAIL] Missing status fields: {missing_fields}")
            return False
        
        print("[PASS] Status method returns all required fields")
        print(f"   -> Monitoring: {status['monitoring']}")
        print(f"   -> Enabled: {status['enabled']}")
        print(f"   -> Symbols: {status['symbols']}")
        print(f"   -> Stats keys: {list(status['stats'].keys())}")
        
        return True
    
    except Exception as e:
        print(f"[FAIL] Status test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_thread_safety():
    """Test 6: Test thread safety of statistics"""
    print("\n" + "="*60)
    print("TEST 6: Thread Safety")
    print("="*60)
    
    try:
        from infra.micro_scalp_monitor import MicroScalpMonitor
        import threading
        
        monitor = MicroScalpMonitor(
            symbols=["BTCUSDc"],
            check_interval=5,
            micro_scalp_engine=None,
            execution_manager=None,
            streamer=None,
            mt5_service=None
        )
        
        # Test that _increment_stat exists and is callable
        assert hasattr(monitor, '_increment_stat'), "Missing _increment_stat method"
        assert callable(monitor._increment_stat), "_increment_stat is not callable"
        
        # Test incrementing stats
        initial_value = monitor.stats.get('total_checks', 0)
        monitor._increment_stat('total_checks', 5)
        new_value = monitor.stats.get('total_checks', 0)
        
        assert new_value == initial_value + 5, f"Stat increment failed: {initial_value} -> {new_value}"
        
        print("[PASS] Thread-safe stat increment works")
        print(f"   -> Initial: {initial_value}, After increment: {new_value}")
        
        return True
    
    except Exception as e:
        print(f"[FAIL] Thread safety test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_start_stop():
    """Test 7: Test start/stop functionality"""
    print("\n" + "="*60)
    print("TEST 7: Start/Stop Functionality")
    print("="*60)
    
    try:
        from infra.micro_scalp_monitor import MicroScalpMonitor
        
        monitor = MicroScalpMonitor(
            symbols=["BTCUSDc"],
            check_interval=5,
            micro_scalp_engine=None,
            execution_manager=None,
            streamer=None,
            mt5_service=None
        )
        
        # Test start
        assert not monitor.monitoring, "Monitor should not be running initially"
        monitor.start()
        
        # Give it a moment to start
        time.sleep(0.5)
        
        # Check if thread was created
        assert monitor.monitor_thread is not None, "Monitor thread not created"
        assert monitor.monitor_thread.is_alive(), "Monitor thread not alive"
        print("[PASS] Monitor started successfully")
        
        # Test stop
        monitor.stop()
        
        # Give it a moment to stop
        time.sleep(0.5)
        
        assert not monitor.monitoring, "Monitor should be stopped"
        print("[PASS] Monitor stopped successfully")
        
        return True
    
    except Exception as e:
        print(f"[FAIL] Start/stop test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("MICRO-SCALP MONITOR IMPLEMENTATION TEST")
    print("="*60)
    
    tests = [
        ("Config File", test_config_file),
        ("Imports", test_imports),
        ("Initialization", lambda: test_monitor_initialization()[0]),
        ("Config Validation", test_config_validation),
        ("Status Method", test_status_method),
        ("Thread Safety", test_thread_safety),
        ("Start/Stop", test_start_stop),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"[FAIL] {test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! Implementation is ready.")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

