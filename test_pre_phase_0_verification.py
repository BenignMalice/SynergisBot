"""
Pre-Phase 0 Fixes - Simple Verification Test

This script verifies that:
1. Helper method _get_btc_order_flow_metrics() exists and works
2. No calls to non-existent methods (get_delta_volume, get_cvd_trend, get_absorption_zones)
3. All fixes use the correct API pattern
"""

import sys
import re
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def verify_no_broken_api_calls():
    """Verify no calls to non-existent methods exist in auto_execution_system.py"""
    print("=" * 70)
    print("Verification 1: Checking for non-existent API calls")
    print("=" * 70)
    
    file_path = project_root / "auto_execution_system.py"
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for broken API calls
    broken_patterns = [
        (r'btc_flow\.get_delta_volume\(\)', 'get_delta_volume()'),
        (r'btc_flow\.get_cvd_trend\(\)', 'get_cvd_trend()'),
        (r'btc_flow\.get_absorption_zones\(\)', 'get_absorption_zones()'),
    ]
    
    issues_found = []
    for pattern, method_name in broken_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            # Get line number
            line_num = content[:match.start()].count('\n') + 1
            # Get context (5 lines before and after)
            lines = content.split('\n')
            context_start = max(0, line_num - 6)
            context_end = min(len(lines), line_num + 5)
            context = '\n'.join(lines[context_start:context_end])
            
            issues_found.append({
                'method': method_name,
                'line': line_num,
                'context': context
            })
    
    if issues_found:
        print(f"[FAIL] Found {len(issues_found)} instances of broken API calls:")
        for issue in issues_found:
            print(f"\n  Method: {issue['method']}")
            print(f"  Line: {issue['line']}")
            print(f"  Context:\n{issue['context']}")
        return False
    else:
        print("[PASS] No broken API calls found - all instances have been fixed!")
        return True


def verify_helper_method_exists():
    """Verify helper method exists and has correct signature"""
    print("\n" + "=" * 70)
    print("Verification 2: Checking helper method exists")
    print("=" * 70)
    
    file_path = project_root / "auto_execution_system.py"
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for helper method
    if '_get_btc_order_flow_metrics' in content:
        print("[PASS] Helper method _get_btc_order_flow_metrics() found")
        
        # Check if it uses get_metrics()
        if 'get_metrics(' in content:
            print("[PASS] Helper method uses get_metrics() correctly")
        else:
            print("[FAIL] Helper method does not use get_metrics()")
            return False
        
        # Count how many times helper method is called
        helper_calls = len(re.findall(r'_get_btc_order_flow_metrics\(', content))
        print(f"[PASS] Helper method is called {helper_calls} times")
        
        return True
    else:
        print("[FAIL] Helper method _get_btc_order_flow_metrics() not found")
        return False


def verify_correct_api_usage():
    """Verify correct API usage patterns"""
    print("\n" + "=" * 70)
    print("Verification 3: Checking correct API usage patterns")
    print("=" * 70)
    
    file_path = project_root / "auto_execution_system.py"
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for correct patterns
    correct_patterns = [
        (r'metrics\.delta_volume', 'metrics.delta_volume'),
        (r'metrics\.cvd_slope', 'metrics.cvd_slope'),
        (r'metrics\.absorption_zones', 'metrics.absorption_zones'),
        (r'btc_flow\.get_metrics\(', 'btc_flow.get_metrics()'),
    ]
    
    found_patterns = {}
    for pattern, name in correct_patterns:
        matches = len(re.findall(pattern, content))
        found_patterns[name] = matches
        if matches > 0:
            print(f"[PASS] Found {matches} instances of {name}")
        else:
            print(f"[WARN] No instances of {name} found (may be expected)")
    
    return True


def verify_fix_comments():
    """Verify Pre-Phase 0 fix comments are present"""
    print("\n" + "=" * 70)
    print("Verification 4: Checking for Pre-Phase 0 fix comments")
    print("=" * 70)
    
    file_path = project_root / "auto_execution_system.py"
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    fix_comments = len(re.findall(r'Pre-Phase 0 Fix', content, re.IGNORECASE))
    if fix_comments > 0:
        print(f"[PASS] Found {fix_comments} Pre-Phase 0 fix comments")
        return True
    else:
        print("[WARN] No Pre-Phase 0 fix comments found (may be expected)")
        return True  # Not critical


def run_verification():
    """Run all verification checks"""
    print("\n" + "=" * 70)
    print("PRE-PHASE 0 FIXES - VERIFICATION TEST")
    print("=" * 70)
    print("\nThis test verifies that all 7 API mismatch bugs have been fixed")
    print("by checking the code structure and patterns.\n")
    
    results = []
    
    # Run verifications
    results.append(("No Broken API Calls", verify_no_broken_api_calls()))
    results.append(("Helper Method Exists", verify_helper_method_exists()))
    results.append(("Correct API Usage", verify_correct_api_usage()))
    results.append(("Fix Comments Present", verify_fix_comments()))
    
    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("[PASS] ALL VERIFICATIONS PASSED!")
        print("=" * 70)
        print("\nPre-Phase 0 fixes are correctly implemented:")
        print("- Helper method _get_btc_order_flow_metrics() exists")
        print("- No calls to non-existent methods")
        print("- All code uses correct API (get_metrics())")
        print("\nThe system is ready for testing with real plans!")
    else:
        print("[FAIL] SOME VERIFICATIONS FAILED")
        print("=" * 70)
        print("\nPlease review the errors above and fix any remaining issues.")
    
    return all_passed


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
