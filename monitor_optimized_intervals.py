"""
Monitor Optimized 10-Second Interval System
Monitors logs and verifies adaptive intervals and smart caching are working

Usage:
    # Activate venv first (Windows):
    .venv\Scripts\activate
    
    # Then run:
    python monitor_optimized_intervals.py
    
    # Or use PowerShell:
    .venv\Scripts\Activate.ps1
    python monitor_optimized_intervals.py
"""

import sys
import time
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Check if running in venv
if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    print("[INFO] Running in virtual environment")
else:
    print("[WARNING] Not running in virtual environment - some imports may fail")
    print("[INFO] Activate venv with: .venv\\Scripts\\activate (Windows) or source .venv/bin/activate (Linux/Mac)")


def print_section(title: str):
    """Print a section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_status(message: str, status: str = "INFO"):
    """Print a status message"""
    symbols = {
        "INFO": "[INFO]",
        "SUCCESS": "[OK]",
        "ERROR": "[FAIL]",
        "WARNING": "[WARN]"
    }
    symbol = symbols.get(status, "[*]")
    print(f"{symbol} {message}")


def find_log_files():
    """Find log files in common locations"""
    log_locations = [
        Path("logs"),
        Path("data/logs"),
        Path("."),
    ]
    
    log_files = []
    for location in log_locations:
        if location.exists():
            # Look for common log file patterns
            for pattern in ["*.log", "auto_execution*.log", "*.txt"]:
                log_files.extend(location.glob(pattern))
    
    return log_files


def monitor_adaptive_intervals():
    """Monitor for adaptive interval messages"""
    print_section("MONITORING ADAPTIVE INTERVALS")
    
    print_status("Looking for adaptive interval activity...", "INFO")
    print_status("Expected log messages:", "INFO")
    print_status("  - 'Error calculating adaptive interval' (debug)", "INFO")
    print_status("  - 'Skipping check for {plan_id}: price ... away' (conditional check)", "INFO")
    print_status("  - Interval calculations in _calculate_adaptive_interval", "INFO")
    
    # Check if config is loaded
    config_path = Path("config/auto_execution_optimized_intervals.json")
    if config_path.exists():
        print_status(f"Config file found: {config_path}", "SUCCESS")
        try:
            import json
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            adaptive = config.get('optimized_intervals', {}).get('adaptive_intervals', {})
            if adaptive.get('enabled'):
                print_status("Adaptive intervals: ENABLED", "SUCCESS")
                m1_config = adaptive.get('plan_type_intervals', {}).get('m1_micro_scalp', {})
                if m1_config:
                    print_status(f"  M1 Micro-Scalp Base Interval: {m1_config.get('base_interval_seconds')}s", "INFO")
                    print_status(f"  M1 Micro-Scalp Close Interval: {m1_config.get('close_interval_seconds')}s", "INFO")
                    print_status(f"  M1 Micro-Scalp Far Interval: {m1_config.get('far_interval_seconds')}s", "INFO")
            else:
                print_status("Adaptive intervals: DISABLED", "WARNING")
        except Exception as e:
            print_status(f"Error reading config: {e}", "ERROR")
    else:
        print_status("Config file not found - features disabled by default", "WARNING")
    
    print_status("\nTo verify adaptive intervals are working:", "INFO")
    print_status("  1. Check system logs for interval calculation messages", "INFO")
    print_status("  2. Monitor plan check frequency (should vary by price proximity)", "INFO")
    print_status("  3. Check _plan_last_check timestamps in memory (if accessible)", "INFO")


def monitor_smart_caching():
    """Monitor for smart caching messages"""
    print_section("MONITORING SMART CACHING")
    
    print_status("Looking for smart caching activity...", "INFO")
    print_status("Expected log messages:", "INFO")
    print_status("  - 'Invalidated M1 cache for {symbol} due to new candle close' (debug)", "INFO")
    print_status("  - 'Pre-fetching M1 data for {symbol} ({time}s until expiry)' (debug)", "INFO")
    print_status("  - 'Pre-fetch thread started' (info)", "INFO")
    
    # Check if config is loaded
    config_path = Path("config/auto_execution_optimized_intervals.json")
    if config_path.exists():
        try:
            import json
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            caching = config.get('optimized_intervals', {}).get('smart_caching', {})
            if caching.get('enabled'):
                print_status("Smart caching: ENABLED", "SUCCESS")
                print_status(f"  Cache TTL: {caching.get('m1_cache_ttl_seconds')}s", "INFO")
                print_status(f"  Candle-close invalidation: {caching.get('invalidate_on_candle_close')}", "INFO")
                print_status(f"  Pre-fetch before expiry: {caching.get('prefetch_seconds_before_expiry')}s", "INFO")
            else:
                print_status("Smart caching: DISABLED", "WARNING")
        except Exception as e:
            print_status(f"Error reading config: {e}", "ERROR")
    
    print_status("\nTo verify smart caching is working:", "INFO")
    print_status("  1. Check logs for cache invalidation messages on candle close", "INFO")
    print_status("  2. Monitor pre-fetch thread activity", "INFO")
    print_status("  3. Verify cache is being used (reduced MT5 API calls)", "INFO")


def check_system_status():
    """Check if auto-execution system is running and has optimized intervals enabled"""
    print_section("SYSTEM STATUS CHECK")
    
    try:
        # Try to import and check system
        from auto_execution_system import AutoExecutionSystem
        
        # Create a test instance to check config
        system = AutoExecutionSystem()
        
        opt_config = system.config.get('optimized_intervals', {})
        
        if not opt_config:
            print_status("Optimized intervals config not found in system", "WARNING")
            return False
        
        print_status("Optimized intervals config loaded in system", "SUCCESS")
        
        # Check each feature
        features = {
            'adaptive_intervals': 'Adaptive Intervals',
            'smart_caching': 'Smart Caching',
            'conditional_checks': 'Conditional Checks',
            'batch_operations': 'Batch Operations'
        }
        
        for key, name in features.items():
            feature_config = opt_config.get(key, {})
            if feature_config.get('enabled', False):
                print_status(f"{name}: ENABLED", "SUCCESS")
            else:
                print_status(f"{name}: DISABLED", "WARNING")
        
        return True
        
    except Exception as e:
        print_status(f"Error checking system: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


def verify_m1_intervals():
    """Verify M1 micro-scalp plans are using 10-second intervals"""
    print_section("VERIFYING M1 MICRO-SCALP INTERVALS")
    
    try:
        from auto_execution_system import AutoExecutionSystem, TradePlan
        
        system = AutoExecutionSystem()
        
        # Check config
        opt_config = system.config.get('optimized_intervals', {})
        adaptive = opt_config.get('adaptive_intervals', {})
        
        if not adaptive.get('enabled', False):
            print_status("Adaptive intervals are DISABLED", "WARNING")
            print_status("  Enable in config/auto_execution_optimized_intervals.json", "INFO")
            return False
        
        m1_config = adaptive.get('plan_type_intervals', {}).get('m1_micro_scalp', {})
        if not m1_config:
            print_status("M1 micro-scalp interval config not found", "WARNING")
            return False
        
        base_interval = m1_config.get('base_interval_seconds', 30)
        close_interval = m1_config.get('close_interval_seconds', 5)
        far_interval = m1_config.get('far_interval_seconds', 30)
        
        print_status(f"M1 Micro-Scalp Interval Configuration:", "INFO")
        print_status(f"  Base Interval: {base_interval}s (price within 2x tolerance)", "INFO")
        print_status(f"  Close Interval: {close_interval}s (price within tolerance)", "INFO")
        print_status(f"  Far Interval: {far_interval}s (price far from entry)", "INFO")
        
        if base_interval == 10:
            print_status("Base interval is correctly set to 10 seconds", "SUCCESS")
        else:
            print_status(f"Base interval is {base_interval}s (expected 10s)", "WARNING")
        
        # Test interval calculation with a sample plan
        test_plan = TradePlan(
            plan_id="test_verify",
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
        
        # Test different price scenarios
        test_cases = [
            (90000.0, "at entry", close_interval),
            (90025.0, "within tolerance", close_interval),
            (90050.0, "within 2x tolerance", base_interval),
            (90200.0, "far from entry", far_interval),
        ]
        
        print_status("\nTesting interval calculation:", "INFO")
        for price, description, expected_interval in test_cases:
            try:
                interval = system._calculate_adaptive_interval(test_plan, price)
                if interval == expected_interval:
                    print_status(f"  Price {price} ({description}): {interval}s [CORRECT]", "SUCCESS")
                else:
                    print_status(f"  Price {price} ({description}): {interval}s [Expected {expected_interval}s]", "WARNING")
            except Exception as e:
                print_status(f"  Price {price} ({description}): ERROR - {e}", "ERROR")
        
        return True
        
    except Exception as e:
        print_status(f"Error verifying intervals: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


def monitor_live_logs(duration_seconds=60):
    """Monitor live logs for a specified duration"""
    print_section("LIVE LOG MONITORING")
    
    print_status(f"Monitoring logs for {duration_seconds} seconds...", "INFO")
    print_status("Press Ctrl+C to stop early", "INFO")
    print_status("\nWatching for:", "INFO")
    print_status("  - Adaptive interval calculations", "INFO")
    print_status("  - Cache invalidation messages", "INFO")
    print_status("  - Pre-fetch activity", "INFO")
    print_status("  - Conditional check skips", "INFO")
    
    # Find log files
    log_files = find_log_files()
    if not log_files:
        print_status("No log files found in common locations", "WARNING")
        print_status("  Logs may be going to console or different location", "INFO")
        return
    
    print_status(f"\nFound {len(log_files)} log file(s):", "INFO")
    for log_file in log_files:
        print_status(f"  - {log_file}", "INFO")
    
    # Monitor log files (tail-like behavior)
    print_status("\nStarting log monitoring...", "INFO")
    print_status("(This is a basic monitor - use tail -f for better results)", "INFO")
    
    try:
        start_time = time.time()
        keywords = [
            'adaptive',
            'interval',
            'cache',
            'prefetch',
            'candle close',
            'invalidated',
            'skip',
            'proximity'
        ]
        
        seen_messages = set()
        
        while time.time() - start_time < duration_seconds:
            for log_file in log_files:
                try:
                    # Read last few lines
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        # Check last 50 lines
                        for line in lines[-50:]:
                            line_lower = line.lower()
                            for keyword in keywords:
                                if keyword in line_lower and line not in seen_messages:
                                    seen_messages.add(line)
                                    timestamp = datetime.now().strftime("%H:%M:%S")
                                    print_status(f"[{timestamp}] {line.strip()[:100]}", "INFO")
                except Exception as e:
                    pass  # Skip files that can't be read
            
            time.sleep(2)  # Check every 2 seconds
        
        print_status(f"\nMonitoring complete ({duration_seconds}s)", "INFO")
        if seen_messages:
            print_status(f"Found {len(seen_messages)} relevant log messages", "SUCCESS")
        else:
            print_status("No relevant log messages found", "WARNING")
            print_status("  System may not be running or features may be disabled", "INFO")
            
    except KeyboardInterrupt:
        print_status("\nMonitoring stopped by user", "WARNING")
    except Exception as e:
        print_status(f"Error monitoring logs: {e}", "ERROR")


def main():
    """Run monitoring checks"""
    print("\n" + "=" * 70)
    print("  OPTIMIZED 10-SECOND INTERVAL SYSTEM MONITOR")
    print("=" * 70)
    
    results = {}
    
    # Run checks
    results["system_status"] = check_system_status()
    results["m1_intervals"] = verify_m1_intervals()
    
    # Show monitoring info
    monitor_adaptive_intervals()
    monitor_smart_caching()
    
    # Summary
    print_section("MONITORING SUMMARY")
    
    print_status("System Status:", "INFO")
    for check_name, result in results.items():
        status = "[OK]" if result else "[FAIL]"
        print_status(f"  {check_name}: {status}", "INFO")
    
    print_status("\nNext Steps:", "INFO")
    print_status("  1. Start/restart auto-execution system to load config", "INFO")
    print_status("  2. Monitor logs for adaptive interval and caching messages", "INFO")
    print_status("  3. Check plan check frequencies match expected intervals", "INFO")
    print_status("  4. Verify M1 plans are checked every 10s when price is near entry", "INFO")
    
    # Ask if user wants to monitor live logs
    print_section("LIVE LOG MONITORING")
    try:
        response = input("Monitor live logs for 60 seconds? (y/n): ").strip().lower()
        if response == 'y':
            monitor_live_logs(60)
    except KeyboardInterrupt:
        print_status("\nSkipping live log monitoring", "INFO")
    except Exception:
        pass  # Input not available
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
