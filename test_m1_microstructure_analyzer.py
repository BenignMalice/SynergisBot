"""
Diagnostic script for M1 Microstructure Analyzer.
Checks CHOCH detection, BOS detection, signal confidence calculation,
integration with auto execution, and data freshness checks.
"""

import sys
import os
import inspect
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("M1 MICROSTRUCTURE ANALYZER DIAGNOSTIC")
print("=" * 80)
print()

results = {
    "choch_detection": {"status": "unknown", "issues": [], "details": {}},
    "bos_detection": {"status": "unknown", "issues": [], "details": {}},
    "confidence_calculation": {"status": "unknown", "issues": [], "details": {}},
    "auto_execution_integration": {"status": "unknown", "issues": [], "details": {}},
    "data_freshness": {"status": "unknown", "issues": [], "details": {}}
}

# ============================================================================
# 1. CHOCH DETECTION
# ============================================================================
print("[1/5] Checking CHOCH Detection...")
print("-" * 80)

try:
    from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
    
    # Check class exists
    analyzer = M1MicrostructureAnalyzer()
    
    if not hasattr(analyzer, 'detect_choch_bos'):
        results["choch_detection"]["issues"].append("Missing detect_choch_bos method")
    else:
        results["choch_detection"]["details"]["method_exists"] = True
        
        # Check method signature
        sig = inspect.signature(analyzer.detect_choch_bos)
        required_params = ['candles']
        missing_params = []
        for param in required_params:
            if param not in sig.parameters:
                missing_params.append(param)
        
        if missing_params:
            results["choch_detection"]["issues"].append(f"Missing parameters: {missing_params}")
        else:
            results["choch_detection"]["details"]["method_signature"] = str(sig)
        
        # Check return value structure
        source = inspect.getsource(analyzer.detect_choch_bos)
        if 'has_choch' in source:
            results["choch_detection"]["details"]["returns_choch_flag"] = True
        else:
            results["choch_detection"]["issues"].append("detect_choch_bos doesn't return has_choch flag")
        
        # Check for confirmation logic
        if 'choch_confirmed' in source or 'require_confirmation' in source:
            results["choch_detection"]["details"]["confirmation_logic"] = True
        else:
            results["choch_detection"]["issues"].append("CHOCH confirmation logic not found")
        
        # Check for swing point detection
        if 'swing' in source.lower():
            results["choch_detection"]["details"]["swing_detection"] = True
        else:
            results["choch_detection"]["issues"].append("Swing point detection not found in CHOCH logic")
    
    if not results["choch_detection"]["issues"]:
        results["choch_detection"]["status"] = "PASS"
        print("  [OK] CHOCH detection method exists and properly structured")
    else:
        results["choch_detection"]["status"] = "FAIL"
        print(f"  [FAIL] Issues: {results['choch_detection']['issues']}")
        
except ImportError as e:
    results["choch_detection"]["status"] = "FAIL"
    results["choch_detection"]["issues"].append(f"Import error: {e}")
    print(f"  [FAIL] Could not import M1MicrostructureAnalyzer: {e}")
except Exception as e:
    results["choch_detection"]["status"] = "FAIL"
    results["choch_detection"]["issues"].append(f"Unexpected error: {e}")
    print(f"  [FAIL] Unexpected error: {e}")

print()

# ============================================================================
# 2. BOS DETECTION
# ============================================================================
print("[2/5] Checking BOS Detection...")
print("-" * 80)

try:
    from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
    
    analyzer = M1MicrostructureAnalyzer()
    
    # BOS detection is in the same method as CHOCH
    if hasattr(analyzer, 'detect_choch_bos'):
        source = inspect.getsource(analyzer.detect_choch_bos)
        
        # Check for BOS detection logic
        if 'has_bos' in source or 'bos' in source.lower():
            results["bos_detection"]["details"]["bos_detection_logic"] = True
        else:
            results["bos_detection"]["issues"].append("BOS detection logic not found")
        
        # Check for BOS confirmation
        if 'choch_bos_combo' in source:
            results["bos_detection"]["details"]["choch_bos_combo"] = True
        else:
            results["bos_detection"]["issues"].append("CHOCH/BOS combo detection not found")
        
        # Check return value includes BOS
        if 'has_bos' in source and 'return' in source:
            results["bos_detection"]["details"]["returns_bos_flag"] = True
        else:
            results["bos_detection"]["issues"].append("detect_choch_bos doesn't return has_bos flag")
    else:
        results["bos_detection"]["issues"].append("detect_choch_bos method not found")
    
    if not results["bos_detection"]["issues"]:
        results["bos_detection"]["status"] = "PASS"
        print("  [OK] BOS detection logic exists")
    else:
        results["bos_detection"]["status"] = "FAIL"
        print(f"  [FAIL] Issues: {results['bos_detection']['issues']}")
        
except Exception as e:
    results["bos_detection"]["status"] = "FAIL"
    results["bos_detection"]["issues"].append(f"Error: {e}")
    print(f"  [FAIL] Error: {e}")

print()

# ============================================================================
# 3. SIGNAL CONFIDENCE CALCULATION
# ============================================================================
print("[3/5] Checking Signal Confidence Calculation...")
print("-" * 80)

try:
    from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
    
    analyzer = M1MicrostructureAnalyzer()
    
    if hasattr(analyzer, 'detect_choch_bos'):
        source = inspect.getsource(analyzer.detect_choch_bos)
        
        # Check for confidence calculation
        if 'confidence' in source.lower():
            results["confidence_calculation"]["details"]["confidence_calculation"] = True
            
            # Check confidence levels
            confidence_levels = ['90', '85', '70', '60']
            found_levels = []
            for level in confidence_levels:
                if level in source:
                    found_levels.append(level)
            
            if len(found_levels) >= 2:
                results["confidence_calculation"]["details"]["confidence_levels"] = found_levels
            else:
                results["confidence_calculation"]["issues"].append("Insufficient confidence levels defined")
            
            # Check confidence is returned
            if "'confidence'" in source or '"confidence"' in source:
                results["confidence_calculation"]["details"]["confidence_returned"] = True
            else:
                results["confidence_calculation"]["issues"].append("Confidence not returned in result")
            
            # Check confidence calculation logic
            if 'choch_bos_combo' in source and 'confidence' in source:
                results["confidence_calculation"]["details"]["combo_confidence"] = True
            else:
                results["confidence_calculation"]["issues"].append("CHOCH/BOS combo confidence calculation not found")
        else:
            results["confidence_calculation"]["issues"].append("Confidence calculation not found")
    else:
        results["confidence_calculation"]["issues"].append("detect_choch_bos method not found")
    
    # Check analyze_microstructure also returns confidence
    if hasattr(analyzer, 'analyze_microstructure'):
        source_analyze = inspect.getsource(analyzer.analyze_microstructure)
        if 'confidence' in source_analyze.lower():
            results["confidence_calculation"]["details"]["analyze_confidence"] = True
    
    if not results["confidence_calculation"]["issues"]:
        results["confidence_calculation"]["status"] = "PASS"
        print("  [OK] Signal confidence calculation exists")
    else:
        results["confidence_calculation"]["status"] = "FAIL"
        print(f"  [FAIL] Issues: {results['confidence_calculation']['issues']}")
        
except Exception as e:
    results["confidence_calculation"]["status"] = "FAIL"
    results["confidence_calculation"]["issues"].append(f"Error: {e}")
    print(f"  [FAIL] Error: {e}")

print()

# ============================================================================
# 4. INTEGRATION WITH AUTO EXECUTION
# ============================================================================
print("[4/5] Checking Integration with Auto Execution...")
print("-" * 80)

try:
    from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
    
    # Check if used in auto_execution_system.py
    auto_exec_path = project_root / "auto_execution_system.py"
    if auto_exec_path.exists():
        with open(auto_exec_path, 'r', encoding='utf-8') as f:
            auto_exec_code = f.read()
        
        # Check for import
        if 'M1MicrostructureAnalyzer' in auto_exec_code or 'm1_microstructure_analyzer' in auto_exec_code:
            results["auto_execution_integration"]["details"]["imported"] = True
        else:
            results["auto_execution_integration"]["issues"].append("M1MicrostructureAnalyzer not imported in auto_execution_system.py")
        
        # Check for usage
        if 'm1_analyzer' in auto_exec_code or 'analyze_microstructure' in auto_exec_code:
            results["auto_execution_integration"]["details"]["used"] = True
        else:
            results["auto_execution_integration"]["issues"].append("M1MicrostructureAnalyzer not used in auto_execution_system.py")
        
        # Check for signal change detection
        if '_has_m1_signal_changed' in auto_exec_code or 'm1_signal' in auto_exec_code.lower():
            results["auto_execution_integration"]["details"]["signal_change_detection"] = True
        else:
            results["auto_execution_integration"]["issues"].append("M1 signal change detection not found")
        
        # Check for confidence calculation
        if '_calculate_m1_confidence' in auto_exec_code or 'm1_confidence' in auto_exec_code.lower():
            results["auto_execution_integration"]["details"]["confidence_calculation"] = True
        else:
            results["auto_execution_integration"]["issues"].append("M1 confidence calculation not found in auto execution")
    else:
        results["auto_execution_integration"]["issues"].append("auto_execution_system.py not found")
    
    if not results["auto_execution_integration"]["issues"]:
        results["auto_execution_integration"]["status"] = "PASS"
        print("  [OK] Integration with auto execution exists")
    else:
        results["auto_execution_integration"]["status"] = "WARN"
        print(f"  [WARN] Integration issues: {results['auto_execution_integration']['issues']}")
        
except Exception as e:
    results["auto_execution_integration"]["status"] = "FAIL"
    results["auto_execution_integration"]["issues"].append(f"Error: {e}")
    print(f"  [FAIL] Error: {e}")

print()

# ============================================================================
# 5. DATA FRESHNESS CHECKS
# ============================================================================
print("[5/5] Checking Data Freshness Checks...")
print("-" * 80)

try:
    from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
    
    analyzer = M1MicrostructureAnalyzer()
    
    # Check for cache mechanism (indicates freshness awareness)
    if hasattr(analyzer, '_cache_timestamps') or hasattr(analyzer, '_cache_ttl'):
        results["data_freshness"]["details"]["cache_mechanism"] = True
    else:
        results["data_freshness"]["issues"].append("Cache mechanism not found (no freshness tracking)")
    
    # Check analyze_microstructure for freshness checks
    if hasattr(analyzer, 'analyze_microstructure'):
        source = inspect.getsource(analyzer.analyze_microstructure)
        
        # Check for cache key generation
        if '_get_cache_key' in source or 'cache_key' in source:
            results["data_freshness"]["details"]["cache_key_generation"] = True
        else:
            results["data_freshness"]["issues"].append("Cache key generation not found")
        
        # Check for cached result retrieval
        if '_get_cached_result' in source or 'cached_result' in source:
            results["data_freshness"]["details"]["cached_result_retrieval"] = True
        else:
            results["data_freshness"]["issues"].append("Cached result retrieval not found")
        
        # Check for timestamp in analysis
        if 'timestamp' in source.lower():
            results["data_freshness"]["details"]["timestamp_tracking"] = True
        else:
            results["data_freshness"]["issues"].append("Timestamp tracking not found in analysis")
    
    # Check for minimum candle count (data quality check)
    if hasattr(analyzer, 'analyze_microstructure'):
        source = inspect.getsource(analyzer.analyze_microstructure)
        if 'len(candles)' in source or 'candle_count' in source:
            results["data_freshness"]["details"]["candle_count_check"] = True
        else:
            results["data_freshness"]["issues"].append("Candle count validation not found")
    
    if not results["data_freshness"]["issues"]:
        results["data_freshness"]["status"] = "PASS"
        print("  [OK] Data freshness checks exist")
    else:
        results["data_freshness"]["status"] = "WARN"
        print(f"  [WARN] Data freshness issues: {results['data_freshness']['issues']}")
        
except Exception as e:
    results["data_freshness"]["status"] = "FAIL"
    results["data_freshness"]["issues"].append(f"Error: {e}")
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

