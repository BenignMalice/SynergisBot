"""
Diagnostic script for Exit Monitor system.
Checks exit signal detection, profit protection, stop loss monitoring,
integration with Intelligent Exit Manager, and thread safety.
"""

import sys
import os
import inspect
import threading
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("EXIT MONITOR SYSTEM DIAGNOSTIC")
print("=" * 80)
print()

results = {
    "exit_signal_detection": {"status": "unknown", "issues": [], "details": {}},
    "profit_protection": {"status": "unknown", "issues": [], "details": {}},
    "stop_loss_monitoring": {"status": "unknown", "issues": [], "details": {}},
    "intelligent_exit_integration": {"status": "unknown", "issues": [], "details": {}},
    "thread_safety": {"status": "unknown", "issues": [], "details": {}}
}

# ============================================================================
# 1. EXIT SIGNAL DETECTION
# ============================================================================
print("[1/5] Checking Exit Signal Detection...")
print("-" * 80)

try:
    from infra.exit_signal_detector import (
        ExitSignalDetector,
        ExitPhase,
        ExitUrgency,
        ExitAnalysis,
        ExitSignal
    )
    
    # Check class exists
    if not hasattr(ExitSignalDetector, 'analyze_exit_signals'):
        results["exit_signal_detection"]["issues"].append("Missing analyze_exit_signals method")
    else:
        # Check method signature
        sig = inspect.signature(ExitSignalDetector.analyze_exit_signals)
        required_params = ['direction', 'entry_price', 'current_price', 'features']
        for param in required_params:
            if param not in sig.parameters:
                results["exit_signal_detection"]["issues"].append(f"Missing parameter: {param}")
        
        results["exit_signal_detection"]["details"]["method_exists"] = True
        results["exit_signal_detection"]["details"]["signature"] = str(sig)
    
    # Check detection methods exist
    detector = ExitSignalDetector()
    detection_methods = [
        '_detect_momentum_exhaustion',
        '_detect_volume_divergence',
        '_detect_volatility_exhaustion',
        '_detect_bb_reentry',
        '_detect_vwap_exhaustion',
        '_detect_ema_break',
        '_detect_sar_flip',
        '_detect_structure_break'
    ]
    
    missing_methods = []
    for method in detection_methods:
        if not hasattr(detector, method):
            missing_methods.append(method)
    
    if missing_methods:
        results["exit_signal_detection"]["issues"].append(f"Missing detection methods: {missing_methods}")
    else:
        results["exit_signal_detection"]["details"]["all_detection_methods"] = True
    
    # Check ExitPhase and ExitUrgency enums
    if not hasattr(ExitPhase, 'EARLY_WARNING'):
        results["exit_signal_detection"]["issues"].append("ExitPhase.EARLY_WARNING missing")
    if not hasattr(ExitUrgency, 'CRITICAL'):
        results["exit_signal_detection"]["issues"].append("ExitUrgency.CRITICAL missing")
    
    if not results["exit_signal_detection"]["issues"]:
        results["exit_signal_detection"]["status"] = "PASS"
        print("  [OK] Exit signal detection methods exist")
    else:
        results["exit_signal_detection"]["status"] = "FAIL"
        print(f"  [FAIL] Issues: {results['exit_signal_detection']['issues']}")
        
except ImportError as e:
    results["exit_signal_detection"]["status"] = "FAIL"
    results["exit_signal_detection"]["issues"].append(f"Import error: {e}")
    print(f"  [FAIL] Could not import ExitSignalDetector: {e}")
except Exception as e:
    results["exit_signal_detection"]["status"] = "FAIL"
    results["exit_signal_detection"]["issues"].append(f"Unexpected error: {e}")
    print(f"  [FAIL] Unexpected error: {e}")

print()

# ============================================================================
# 2. PROFIT PROTECTION
# ============================================================================
print("[2/5] Checking Profit Protection...")
print("-" * 80)

try:
    from infra.exit_monitor import ExitMonitor
    
    # Check ExitMonitor class exists
    if not hasattr(ExitMonitor, 'check_exit_signals'):
        results["profit_protection"]["issues"].append("Missing check_exit_signals method")
    else:
        results["profit_protection"]["details"]["check_exit_signals_exists"] = True
    
    # Check min_profit_r logic
    if not hasattr(ExitMonitor, '__init__'):
        results["profit_protection"]["issues"].append("Missing __init__ method")
    else:
        sig = inspect.signature(ExitMonitor.__init__)
        if 'min_profit_r' not in sig.parameters:
            results["profit_protection"]["issues"].append("min_profit_r parameter missing")
        else:
            results["profit_protection"]["details"]["min_profit_r_parameter"] = True
    
    # Check profit calculation logic in check_exit_signals
    source = inspect.getsource(ExitMonitor.check_exit_signals)
    if 'unrealized_r' not in source:
        results["profit_protection"]["issues"].append("Profit calculation (unrealized_r) not found in check_exit_signals")
    if 'min_profit_r' not in source:
        results["profit_protection"]["issues"].append("min_profit_r check not found in check_exit_signals")
    else:
        results["profit_protection"]["details"]["profit_calculation"] = True
    
    # Check auto-exit execution
    if not hasattr(ExitMonitor, '_execute_exit_action'):
        results["profit_protection"]["issues"].append("Missing _execute_exit_action method")
    else:
        results["profit_protection"]["details"]["auto_exit_method"] = True
    
    if not results["profit_protection"]["issues"]:
        results["profit_protection"]["status"] = "PASS"
        print("  [OK] Profit protection logic exists")
    else:
        results["profit_protection"]["status"] = "FAIL"
        print(f"  [FAIL] Issues: {results['profit_protection']['issues']}")
        
except ImportError as e:
    results["profit_protection"]["status"] = "FAIL"
    results["profit_protection"]["issues"].append(f"Import error: {e}")
    print(f"  [FAIL] Could not import ExitMonitor: {e}")
except Exception as e:
    results["profit_protection"]["status"] = "FAIL"
    results["profit_protection"]["issues"].append(f"Unexpected error: {e}")
    print(f"  [FAIL] Unexpected error: {e}")

print()

# ============================================================================
# 3. STOP LOSS MONITORING
# ============================================================================
print("[3/5] Checking Stop Loss Monitoring...")
print("-" * 80)

try:
    from infra.exit_monitor import ExitMonitor
    
    # Check if SL is read from position
    source = inspect.getsource(ExitMonitor.check_exit_signals)
    if 'current_sl' not in source or 'position.sl' not in source:
        results["stop_loss_monitoring"]["issues"].append("Stop loss not being read from position")
    else:
        results["stop_loss_monitoring"]["details"]["sl_reading"] = True
    
    # Check if SL is used in risk calculation
    if 'risk' in source and ('current_sl' in source or 'position.sl' in source):
        results["stop_loss_monitoring"]["details"]["sl_in_risk_calc"] = True
    else:
        results["stop_loss_monitoring"]["issues"].append("SL not used in risk calculation")
    
    # Check if SL modification is implemented
    if hasattr(ExitMonitor, '_execute_exit_action'):
        source_exec = inspect.getsource(ExitMonitor._execute_exit_action)
        if 'sl' in source_exec.lower() and ('trail' in source_exec.lower() or 'tighten' in source_exec.lower()):
            results["stop_loss_monitoring"]["details"]["sl_modification"] = True
        else:
            results["stop_loss_monitoring"]["issues"].append("SL modification logic not found in _execute_exit_action")
    
    if not results["stop_loss_monitoring"]["issues"]:
        results["stop_loss_monitoring"]["status"] = "PASS"
        print("  [OK] Stop loss monitoring logic exists")
    else:
        results["stop_loss_monitoring"]["status"] = "FAIL"
        print(f"  [FAIL] Issues: {results['stop_loss_monitoring']['issues']}")
        
except Exception as e:
    results["stop_loss_monitoring"]["status"] = "FAIL"
    results["stop_loss_monitoring"]["issues"].append(f"Error: {e}")
    print(f"  [FAIL] Error: {e}")

print()

# ============================================================================
# 4. INTEGRATION WITH INTELLIGENT EXIT MANAGER
# ============================================================================
print("[4/5] Checking Integration with Intelligent Exit Manager...")
print("-" * 80)

try:
    from infra.exit_monitor import ExitMonitor
    from infra.intelligent_exit_manager import IntelligentExitManager
    
    # Check if ExitMonitor coordinates with IntelligentExitManager via trade_registry
    exit_monitor_source = inspect.getsourcefile(ExitMonitor)
    if exit_monitor_source:
        with open(exit_monitor_source, 'r', encoding='utf-8') as f:
            exit_monitor_code = f.read()
        
        # Check for trade_registry integration (preferred coordination pattern)
        if 'trade_registry' in exit_monitor_code and 'get_trade_state' in exit_monitor_code:
            if 'intelligent_exit_manager' in exit_monitor_code:
                results["intelligent_exit_integration"]["details"]["trade_registry_coordination"] = True
                results["intelligent_exit_integration"]["details"]["references_intelligent_exit"] = True
                results["intelligent_exit_integration"]["details"]["coordination_mechanism"] = True
                # Coordination is done internally in ExitMonitor - this is correct
            elif 'managed_by' in exit_monitor_code:
                # Check if managed_by includes intelligent_exit_manager
                if '"intelligent_exit_manager"' in exit_monitor_code or "'intelligent_exit_manager'" in exit_monitor_code:
                    results["intelligent_exit_integration"]["details"]["trade_registry_coordination"] = True
                    results["intelligent_exit_integration"]["details"]["references_intelligent_exit"] = True
                    results["intelligent_exit_integration"]["details"]["coordination_mechanism"] = True
                else:
                    results["intelligent_exit_integration"]["issues"].append("ExitMonitor uses trade_registry but doesn't check for intelligent_exit_manager in managed_by")
            else:
                results["intelligent_exit_integration"]["issues"].append("ExitMonitor uses trade_registry but doesn't check for intelligent_exit_manager")
        elif 'IntelligentExitManager' in exit_monitor_code or 'intelligent_exit' in exit_monitor_code.lower():
            results["intelligent_exit_integration"]["details"]["references_intelligent_exit"] = True
        else:
            results["intelligent_exit_integration"]["issues"].append("ExitMonitor does not coordinate with IntelligentExitManager (no trade_registry or direct reference)")
    
    # Check if they're used together in chatgpt_bot.py
    chatgpt_bot_path = project_root / "chatgpt_bot.py"
    if chatgpt_bot_path.exists():
        with open(chatgpt_bot_path, 'r', encoding='utf-8') as f:
            chatgpt_bot_code = f.read()
        
        has_exit_monitor = 'ExitMonitor' in chatgpt_bot_code or 'exit_monitor' in chatgpt_bot_code
        has_intelligent_exit = 'IntelligentExitManager' in chatgpt_bot_code or 'intelligent_exit_manager' in chatgpt_bot_code
        
        if has_exit_monitor and has_intelligent_exit:
            results["intelligent_exit_integration"]["details"]["both_initialized"] = True
            # Coordination can be done in ExitMonitor itself (preferred) or in chatgpt_bot.py
            # If ExitMonitor already has trade_registry coordination, that's sufficient
            if results["intelligent_exit_integration"]["details"].get("coordination_mechanism"):
                # Already detected coordination in ExitMonitor - this is correct
                pass
            elif 'trade_registry' in chatgpt_bot_code or 'managed_by' in chatgpt_bot_code:
                results["intelligent_exit_integration"]["details"]["coordination_mechanism"] = True
                # If trade_registry is used, this is the correct pattern (same as TradeMonitor)
                if 'trade_registry' in exit_monitor_code:
                    results["intelligent_exit_integration"]["details"]["uses_trade_registry"] = True
            else:
                # Only report as issue if coordination not found in ExitMonitor itself
                if not results["intelligent_exit_integration"]["details"].get("coordination_mechanism"):
                    results["intelligent_exit_integration"]["issues"].append("No coordination mechanism found between ExitMonitor and IntelligentExitManager")
        else:
            if not has_exit_monitor:
                results["intelligent_exit_integration"]["issues"].append("ExitMonitor not found in chatgpt_bot.py")
            if not has_intelligent_exit:
                results["intelligent_exit_integration"]["issues"].append("IntelligentExitManager not found in chatgpt_bot.py")
    else:
        results["intelligent_exit_integration"]["issues"].append("chatgpt_bot.py not found")
    
    if not results["intelligent_exit_integration"]["issues"]:
        results["intelligent_exit_integration"]["status"] = "PASS"
        print("  [OK] Integration with Intelligent Exit Manager exists")
    else:
        results["intelligent_exit_integration"]["status"] = "WARN"
        print(f"  [WARN] Integration issues: {results['intelligent_exit_integration']['issues']}")
        
except Exception as e:
    results["intelligent_exit_integration"]["status"] = "FAIL"
    results["intelligent_exit_integration"]["issues"].append(f"Error: {e}")
    print(f"  [FAIL] Error: {e}")

print()

# ============================================================================
# 5. THREAD SAFETY
# ============================================================================
print("[5/5] Checking Thread Safety...")
print("-" * 80)

try:
    from infra.exit_monitor import ExitMonitor
    import inspect
    
    # Check for thread synchronization
    source = inspect.getsource(ExitMonitor)
    
    has_lock = 'Lock' in source or 'lock' in source or 'threading.Lock' in source
    has_threading_import = 'import threading' in source or 'from threading import' in source
    
    # Check if shared state is protected
    if 'self.last_alert' in source:
        # Check if last_alert is accessed with locks
        if has_lock and ('with' in source or 'acquire' in source):
            results["thread_safety"]["details"]["last_alert_protected"] = True
        else:
            results["thread_safety"]["issues"].append("self.last_alert dictionary accessed without locks (potential race condition)")
    
    if 'self.analysis_history' in source:
        if has_lock and ('with' in source or 'acquire' in source):
            results["thread_safety"]["details"]["analysis_history_protected"] = True
        else:
            results["thread_safety"]["issues"].append("self.analysis_history dictionary accessed without locks (potential race condition)")
    
    # Check if check_exit_signals is called from multiple threads
    chatgpt_bot_path = project_root / "chatgpt_bot.py"
    if chatgpt_bot_path.exists():
        with open(chatgpt_bot_path, 'r', encoding='utf-8') as f:
            chatgpt_bot_code = f.read()
        
        # Check if check_exit_signals is scheduled/threaded
        if 'check_exit_signals' in chatgpt_bot_code:
            if 'scheduler' in chatgpt_bot_code or 'thread' in chatgpt_bot_code.lower() or 'asyncio' in chatgpt_bot_code:
                results["thread_safety"]["details"]["called_from_multiple_contexts"] = True
                if not has_lock:
                    results["thread_safety"]["issues"].append("check_exit_signals called from scheduler/async context but no locks found")
    
    if not results["thread_safety"]["issues"]:
        results["thread_safety"]["status"] = "PASS"
        print("  [OK] Thread safety mechanisms in place")
    else:
        results["thread_safety"]["status"] = "WARN"
        print(f"  [WARN] Thread safety issues: {results['thread_safety']['issues']}")
        
except Exception as e:
    results["thread_safety"]["status"] = "FAIL"
    results["thread_safety"]["issues"].append(f"Error: {e}")
    print(f"  [FAIL] Error: {e}")

print()

# ============================================================================
# SUMMARY
# ============================================================================
print("=" * 80)
print("SUMMARY")
print("=" * 80)

total_checks = len(results)
passed = sum(1 for r in results.values() if r["status"] == "PASS")
warned = sum(1 for r in results.values() if r["status"] == "WARN")
failed = sum(1 for r in results.values() if r["status"] == "FAIL")

print(f"Total Checks: {total_checks}")
print(f"Passed: {passed}")
print(f"Warnings: {warned}")
print(f"Failed: {failed}")
print()

if failed > 0 or warned > 0:
    print("ISSUES FOUND:")
    print("-" * 80)
    for check_name, check_result in results.items():
        if check_result["status"] != "PASS":
            print(f"\n{check_name.upper().replace('_', ' ')}: {check_result['status']}")
            for issue in check_result["issues"]:
                print(f"  - {issue}")
else:
    print("All checks passed!")

print()
print("=" * 80)

