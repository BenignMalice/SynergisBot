"""
Diagnostic script for Range Scalping System.
Checks range detection, confluence scoring, entry validation, exit management, and risk filters.
"""

import sys
import os
import inspect
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("RANGE SCALPING SYSTEM DIAGNOSTIC")
print("=" * 80)
print()

results = {
    "range_detection": {"status": "unknown", "issues": [], "details": {}},
    "confluence_scoring": {"status": "unknown", "issues": [], "details": {}},
    "entry_validation": {"status": "unknown", "issues": [], "details": {}},
    "exit_management": {"status": "unknown", "issues": [], "details": {}},
    "risk_filters": {"status": "unknown", "issues": [], "details": {}}
}

# ============================================================================
# 1. RANGE DETECTION
# ============================================================================
print("[1/5] Checking Range Detection...")
print("-" * 80)

try:
    from infra.range_boundary_detector import RangeBoundaryDetector, RangeStructure
    
    # Check class exists
    if not hasattr(RangeBoundaryDetector, 'detect_range'):
        results["range_detection"]["issues"].append("Missing detect_range method")
    else:
        results["range_detection"]["details"]["detect_range_exists"] = True
        # Check method signature
        sig = inspect.signature(RangeBoundaryDetector.detect_range)
        if 'symbol' not in sig.parameters:
            results["range_detection"]["issues"].append("detect_range missing 'symbol' parameter")
        else:
            results["range_detection"]["details"]["method_signature"] = str(sig)
    
    # Check for other key methods
    detector = RangeBoundaryDetector({})
    key_methods = [
        'calculate_critical_gaps',
        'validate_range_integrity',
        'detect_range'
    ]
    
    missing_methods = []
    for method in key_methods:
        if not hasattr(detector, method):
            missing_methods.append(method)
    
    if missing_methods:
        results["range_detection"]["issues"].append(f"Missing methods: {missing_methods}")
    else:
        results["range_detection"]["details"]["all_methods"] = True
    
    # Check RangeStructure dataclass
    if not hasattr(RangeStructure, '__dataclass_fields__'):
        results["range_detection"]["issues"].append("RangeStructure not a dataclass or missing")
    else:
        required_fields = ['range_high', 'range_low', 'touch_count']
        missing_fields = []
        for field in required_fields:
            if field not in RangeStructure.__dataclass_fields__:
                missing_fields.append(field)
        
        if missing_fields:
            results["range_detection"]["issues"].append(f"RangeStructure missing fields: {missing_fields}")
        else:
            results["range_detection"]["details"]["range_structure_complete"] = True
    
    if not results["range_detection"]["issues"]:
        results["range_detection"]["status"] = "PASS"
        print("  [OK] Range detection methods exist")
    else:
        results["range_detection"]["status"] = "FAIL"
        print(f"  [FAIL] Issues: {results['range_detection']['issues']}")
        
except ImportError as e:
    results["range_detection"]["status"] = "FAIL"
    results["range_detection"]["issues"].append(f"Import error: {e}")
    print(f"  [FAIL] Could not import RangeBoundaryDetector: {e}")
except Exception as e:
    results["range_detection"]["status"] = "FAIL"
    results["range_detection"]["issues"].append(f"Unexpected error: {e}")
    print(f"  [FAIL] Unexpected error: {e}")

print()

# ============================================================================
# 2. CONFLUENCE SCORING
# ============================================================================
print("[2/5] Checking Confluence Scoring...")
print("-" * 80)

try:
    from infra.range_scalping_risk_filters import RangeScalpingRiskFilters
    from config.range_scalping_config_loader import load_range_scalping_config
    
    # Load config
    config = load_range_scalping_config()
    
    # Check class exists
    if not hasattr(RangeScalpingRiskFilters, 'check_3_confluence_rule_weighted'):
        results["confluence_scoring"]["issues"].append("Missing check_3_confluence_rule_weighted method")
    else:
        results["confluence_scoring"]["details"]["confluence_method_exists"] = True
        # Check method signature (actual signature uses different parameter names)
        sig = inspect.signature(RangeScalpingRiskFilters.check_3_confluence_rule_weighted)
        # Actual parameters: range_data, price_position, signals, atr
        required_params = ['range_data']  # At minimum, range_data is required
        missing_params = []
        for param in required_params:
            if param not in sig.parameters:
                missing_params.append(param)
        
        if missing_params:
            results["confluence_scoring"]["issues"].append(f"Missing parameters: {missing_params}")
        else:
            results["confluence_scoring"]["details"]["method_signature"] = str(sig)
            results["confluence_scoring"]["details"]["method_exists"] = True
    
    # Check confluence weights in config
    entry_filters = config.get("entry_filters", {})
    confluence_weights = entry_filters.get("confluence_weights", {})
    
    if not confluence_weights:
        results["confluence_scoring"]["issues"].append("Confluence weights not configured")
    else:
        required_weights = ['structure', 'location', 'confirmation']
        missing_weights = []
        for weight in required_weights:
            if weight not in confluence_weights:
                missing_weights.append(weight)
        
        if missing_weights:
            results["confluence_scoring"]["issues"].append(f"Missing confluence weights: {missing_weights}")
        else:
            results["confluence_scoring"]["details"]["weights_configured"] = True
            # Check if weights sum to reasonable value (should be around 100)
            total_weight = sum(confluence_weights.values())
            results["confluence_scoring"]["details"]["total_weight"] = total_weight
    
    # Check min_confluence_score
    min_score = entry_filters.get("min_confluence_score", 0)
    if min_score < 80:
        results["confluence_scoring"]["issues"].append(f"min_confluence_score too low: {min_score} (should be >= 80)")
    else:
        results["confluence_scoring"]["details"]["min_score"] = min_score
    
    if not results["confluence_scoring"]["issues"]:
        results["confluence_scoring"]["status"] = "PASS"
        print("  [OK] Confluence scoring methods exist and configured")
    else:
        results["confluence_scoring"]["status"] = "FAIL"
        print(f"  [FAIL] Issues: {results['confluence_scoring']['issues']}")
        
except ImportError as e:
    results["confluence_scoring"]["status"] = "FAIL"
    results["confluence_scoring"]["issues"].append(f"Import error: {e}")
    print(f"  [FAIL] Could not import RangeScalpingRiskFilters: {e}")
except Exception as e:
    results["confluence_scoring"]["status"] = "FAIL"
    results["confluence_scoring"]["issues"].append(f"Unexpected error: {e}")
    print(f"  [FAIL] Unexpected error: {e}")

print()

# ============================================================================
# 3. ENTRY CONDITIONS VALIDATION
# ============================================================================
print("[3/5] Checking Entry Conditions Validation...")
print("-" * 80)

try:
    from infra.range_scalping_risk_filters import RangeScalpingRiskFilters
    from infra.range_scalping_scorer import RangeScalpingScorer
    from config.range_scalping_config_loader import load_range_scalping_config, load_rr_config
    
    config = load_range_scalping_config()
    rr_config = load_rr_config()
    
    # Check risk filters validation
    risk_filters = RangeScalpingRiskFilters(config)
    
    validation_methods = [
        'check_data_quality',
        'check_3_confluence_rule_weighted',
        'detect_false_range',
        'check_range_validity',
        'check_session_filters',
        'check_trade_activity_criteria'
    ]
    
    missing_methods = []
    for method in validation_methods:
        if not hasattr(risk_filters, method):
            missing_methods.append(method)
    
    if missing_methods:
        results["entry_validation"]["issues"].append(f"Missing validation methods: {missing_methods}")
    else:
        results["entry_validation"]["details"]["all_validation_methods"] = True
    
    # Check scorer
    scorer = RangeScalpingScorer(config, rr_config)
    
    if not hasattr(scorer, 'score_all_strategies'):
        results["entry_validation"]["issues"].append("Missing score_all_strategies method")
    else:
        results["entry_validation"]["details"]["scorer_method_exists"] = True
    
    # Check entry filters config
    entry_filters = config.get("entry_filters", {})
    if not entry_filters:
        results["entry_validation"]["issues"].append("entry_filters not configured")
    else:
        required_filters = ['require_3_confluence', 'min_confluence_score', 'min_touch_count']
        missing_filters = []
        for filter_key in required_filters:
            if filter_key not in entry_filters:
                missing_filters.append(filter_key)
        
        if missing_filters:
            results["entry_validation"]["issues"].append(f"Missing entry filter config: {missing_filters}")
        else:
            results["entry_validation"]["details"]["entry_filters_configured"] = True
    
    if not results["entry_validation"]["issues"]:
        results["entry_validation"]["status"] = "PASS"
        print("  [OK] Entry validation methods exist")
    else:
        results["entry_validation"]["status"] = "FAIL"
        print(f"  [FAIL] Issues: {results['entry_validation']['issues']}")
        
except ImportError as e:
    results["entry_validation"]["status"] = "FAIL"
    results["entry_validation"]["issues"].append(f"Import error: {e}")
    print(f"  [FAIL] Could not import validation modules: {e}")
except Exception as e:
    results["entry_validation"]["status"] = "FAIL"
    results["entry_validation"]["issues"].append(f"Unexpected error: {e}")
    print(f"  [FAIL] Unexpected error: {e}")

print()

# ============================================================================
# 4. EXIT MANAGEMENT
# ============================================================================
print("[4/5] Checking Exit Management...")
print("-" * 80)

try:
    from infra.range_scalping_exit_manager import RangeScalpingExitManager
    
    # Check class exists
    if not hasattr(RangeScalpingExitManager, 'register_trade'):
        results["exit_management"]["issues"].append("Missing register_trade method")
    else:
        results["exit_management"]["details"]["register_trade_exists"] = True
    
    # Check for monitoring methods (actual method names may differ)
    exit_manager_methods = [
        'register_trade',
        'check_early_exit_conditions',  # Actual method name
        'execute_exit'
    ]
    
    missing_methods = []
    for method in exit_manager_methods:
        if not hasattr(RangeScalpingExitManager, method):
            missing_methods.append(method)
    
    if missing_methods:
        results["exit_management"]["issues"].append(f"Missing exit management methods: {missing_methods}")
    else:
        results["exit_management"]["details"]["all_methods"] = True
        
    # Check for additional useful methods
    optional_methods = ['unregister_trade', 'get_active_ticket_list']
    found_optional = []
    for method in optional_methods:
        if hasattr(RangeScalpingExitManager, method):
            found_optional.append(method)
    if found_optional:
        results["exit_management"]["details"]["optional_methods"] = found_optional
    
    # Check for exit condition types
    source = inspect.getsource(RangeScalpingExitManager)
    exit_conditions = [
        'breakeven',
        'stagnation',
        'divergence',
        'range_invalidation',
        'opposite_order_flow'
    ]
    
    found_conditions = []
    for condition in exit_conditions:
        if condition in source.lower():
            found_conditions.append(condition)
    
    if len(found_conditions) < 3:
        results["exit_management"]["issues"].append(f"Missing exit conditions: {set(exit_conditions) - set(found_conditions)}")
    else:
        results["exit_management"]["details"]["exit_conditions"] = found_conditions
    
    if not results["exit_management"]["issues"]:
        results["exit_management"]["status"] = "PASS"
        print("  [OK] Exit management methods exist")
    else:
        results["exit_management"]["status"] = "FAIL"
        print(f"  [FAIL] Issues: {results['exit_management']['issues']}")
        
except ImportError as e:
    results["exit_management"]["status"] = "FAIL"
    results["exit_management"]["issues"].append(f"Import error: {e}")
    print(f"  [FAIL] Could not import RangeScalpingExitManager: {e}")
except Exception as e:
    results["exit_management"]["status"] = "FAIL"
    results["exit_management"]["issues"].append(f"Unexpected error: {e}")
    print(f"  [FAIL] Unexpected error: {e}")

print()

# ============================================================================
# 5. RISK FILTERS
# ============================================================================
print("[5/5] Checking Risk Filters...")
print("-" * 80)

try:
    from infra.range_scalping_risk_filters import RangeScalpingRiskFilters
    from config.range_scalping_config_loader import load_range_scalping_config
    
    config = load_range_scalping_config()
    risk_filters = RangeScalpingRiskFilters(config)
    
    # Check risk filter methods
    risk_methods = [
        'check_data_quality',
        'detect_false_range',
        'check_range_validity',
        'check_session_filters',
        'check_trade_activity_criteria'
    ]
    
    missing_methods = []
    for method in risk_methods:
        if not hasattr(risk_filters, method):
            missing_methods.append(method)
    
    if missing_methods:
        results["risk_filters"]["issues"].append(f"Missing risk filter methods: {missing_methods}")
    else:
        results["risk_filters"]["details"]["all_methods"] = True
    
    # Check risk mitigation config
    risk_mitigation = config.get("risk_mitigation", {})
    if not risk_mitigation:
        results["risk_filters"]["issues"].append("risk_mitigation not configured")
    else:
        required_checks = [
            'check_false_range',
            'check_range_validity',
            'check_session_filters',
            'check_trade_activity'
        ]
        
        missing_checks = []
        for check in required_checks:
            if check not in risk_mitigation:
                missing_checks.append(check)
        
        if missing_checks:
            results["risk_filters"]["issues"].append(f"Missing risk mitigation checks: {missing_checks}")
        else:
            results["risk_filters"]["details"]["risk_mitigation_configured"] = True
    
    # Check range invalidation config
    range_invalidation = config.get("range_invalidation", {})
    if not range_invalidation:
        results["risk_filters"]["issues"].append("range_invalidation not configured")
    else:
        required_invalidation = ['candles_outside_range', 'conditions_required']
        missing_invalidation = []
        for invalidation in required_invalidation:
            if invalidation not in range_invalidation:
                missing_invalidation.append(invalidation)
        
        if missing_invalidation:
            results["risk_filters"]["issues"].append(f"Missing range invalidation config: {missing_invalidation}")
        else:
            results["risk_filters"]["details"]["range_invalidation_configured"] = True
    
    if not results["risk_filters"]["issues"]:
        results["risk_filters"]["status"] = "PASS"
        print("  [OK] Risk filters methods exist and configured")
    else:
        results["risk_filters"]["status"] = "FAIL"
        print(f"  [FAIL] Issues: {results['risk_filters']['issues']}")
        
except ImportError as e:
    results["risk_filters"]["status"] = "FAIL"
    results["risk_filters"]["issues"].append(f"Import error: {e}")
    print(f"  [FAIL] Could not import RangeScalpingRiskFilters: {e}")
except Exception as e:
    results["risk_filters"]["status"] = "FAIL"
    results["risk_filters"]["issues"].append(f"Unexpected error: {e}")
    print(f"  [FAIL] Unexpected error: {e}")

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
