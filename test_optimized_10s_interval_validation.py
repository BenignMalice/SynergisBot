"""
Validation Test for Optimized 10-Second Interval Implementation
Validates code structure and method signatures without requiring full dependencies
"""

import sys
import ast
from pathlib import Path


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


def check_method_exists(source_code: str, class_name: str, method_name: str) -> bool:
    """Check if a method exists in a class"""
    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == method_name:
                        return True
        return False
    except Exception:
        return False


def check_dict_initialization(source_code: str, dict_name: str) -> bool:
    """Check if a dictionary is initialized in __init__"""
    # Simple string search - more reliable than AST for this
    if f"self.{dict_name}" in source_code or f"_{dict_name}" in source_code:
        # Check if it's in __init__ method (look for pattern)
        init_start = source_code.find("def __init__")
        if init_start == -1:
            return False
        
        # Find the next method definition after __init__
        next_method = source_code.find("\n    def ", init_start + 100)
        if next_method == -1:
            # No next method, check to end of class
            next_method = source_code.find("\nclass ", init_start + 100)
        
        init_section = source_code[init_start:next_method] if next_method > init_start else source_code[init_start:init_start+5000]
        
        return f"self.{dict_name}" in init_section
    return False


def test_code_structure():
    """Test that all required methods and structures exist"""
    print_section("CODE STRUCTURE VALIDATION")
    
    auto_exec_file = Path("auto_execution_system.py")
    if not auto_exec_file.exists():
        print_status(f"ERROR: {auto_exec_file} not found", "ERROR")
        return False
    
    source_code = auto_exec_file.read_text(encoding='utf-8')
    
    # Test 1: Check tracking dictionaries
    print_status("Checking tracking dictionaries...", "INFO")
    dicts_to_check = [
        '_plan_types',
        '_plan_last_check',
        '_plan_last_price',
        '_m1_latest_candle_times',
        'prefetch_thread'
    ]
    
    all_dicts_found = True
    for dict_name in dicts_to_check:
        if check_dict_initialization(source_code, dict_name):
            print_status(f"  {dict_name}: Found", "SUCCESS")
        else:
            print_status(f"  {dict_name}: NOT FOUND", "ERROR")
            all_dicts_found = False
    
    if not all_dicts_found:
        return False
    
    # Test 2: Check required methods
    print_status("\nChecking required methods...", "INFO")
    methods_to_check = [
        ('AutoExecutionSystem', '_detect_plan_type'),
        ('AutoExecutionSystem', '_calculate_adaptive_interval'),
        ('AutoExecutionSystem', '_should_check_plan'),
        ('AutoExecutionSystem', '_get_current_prices_batch'),
        ('AutoExecutionSystem', '_invalidate_cache_on_candle_close'),
        ('AutoExecutionSystem', '_prefetch_data_before_expiry'),
    ]
    
    all_methods_found = True
    for class_name, method_name in methods_to_check:
        if check_method_exists(source_code, class_name, method_name):
            print_status(f"  {method_name}: Found", "SUCCESS")
        else:
            print_status(f"  {method_name}: NOT FOUND", "ERROR")
            all_methods_found = False
    
    if not all_methods_found:
        return False
    
    # Test 3: Check config loading code
    print_status("\nChecking config loading integration...", "INFO")
    if 'optimized_intervals' in source_code and 'auto_execution_optimized_intervals.json' in source_code:
        print_status("  Config loading code: Found", "SUCCESS")
    else:
        print_status("  Config loading code: NOT FOUND", "ERROR")
        return False
    
    # Test 4: Check cleanup integration
    print_status("\nChecking cleanup integration...", "INFO")
    if '_plan_types' in source_code and '_cleanup_plan_resources' in source_code:
        # Check if cleanup code references tracking dicts
        if 'del self._plan_types' in source_code or 'del self._plan_last_check' in source_code:
            print_status("  Cleanup code: Found", "SUCCESS")
        else:
            print_status("  Cleanup code: May be incomplete", "WARNING")
    else:
        print_status("  Cleanup code: NOT FOUND", "ERROR")
        return False
    
    # Test 5: Check monitor loop integration
    print_status("\nChecking monitor loop integration...", "INFO")
    monitor_loop_checks = [
        '_get_current_prices_batch',
        '_calculate_adaptive_interval',
        '_should_check_plan',
        '_plan_last_check',
        '_invalidate_cache_on_candle_close'
    ]
    
    all_integrated = True
    for check in monitor_loop_checks:
        if check in source_code:
            print_status(f"  {check}: Integrated", "SUCCESS")
        else:
            print_status(f"  {check}: NOT INTEGRATED", "ERROR")
            all_integrated = False
    
    if not all_integrated:
        return False
    
    # Test 6: Check thread management
    print_status("\nChecking thread management...", "INFO")
    if 'prefetch_thread' in source_code and 'start()' in source_code and 'stop()' in source_code:
        if '_prefetch_data_before_expiry' in source_code:
            print_status("  Pre-fetch thread management: Found", "SUCCESS")
        else:
            print_status("  Pre-fetch thread management: Incomplete", "WARNING")
    else:
        print_status("  Thread management: NOT FOUND", "ERROR")
        return False
    
    return True


def test_config_file_structure():
    """Test config file structure"""
    print_section("CONFIG FILE STRUCTURE VALIDATION")
    
    config_path = Path("config/auto_execution_optimized_intervals.json")
    
    if config_path.exists():
        print_status(f"Config file exists: {config_path}", "INFO")
        try:
            import json
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Validate structure
            if 'optimized_intervals' not in config:
                print_status("ERROR: 'optimized_intervals' key not found", "ERROR")
                return False
            
            opt_config = config['optimized_intervals']
            required_sections = ['adaptive_intervals', 'smart_caching', 'conditional_checks', 'batch_operations']
            
            for section in required_sections:
                if section in opt_config:
                    print_status(f"  {section}: Present", "SUCCESS")
                else:
                    print_status(f"  {section}: Missing", "WARNING")
            
            return True
        except Exception as e:
            print_status(f"ERROR reading config: {e}", "ERROR")
            return False
    else:
        print_status("Config file does not exist (optional)", "INFO")
        print_status("  Create config/auto_execution_optimized_intervals.json to enable features", "INFO")
        return True  # Config file is optional


def main():
    """Run all validation tests"""
    print("\n" + "=" * 70)
    print("  OPTIMIZED 10-SECOND INTERVAL - CODE VALIDATION TEST")
    print("=" * 70)
    print("\nThis test validates:")
    print("  1. Code structure and method existence")
    print("  2. Config file structure")
    print("  3. Integration points")
    
    results = {}
    
    # Run tests
    results["code_structure"] = test_code_structure()
    results["config_structure"] = test_config_file_structure()
    
    # Summary
    print_section("VALIDATION SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    print(f"\nTotal Validations: {total_tests}")
    print(f"Passed: {passed_tests} [OK]")
    print(f"Failed: {total_tests - passed_tests} [FAIL]")
    
    print("\nDetailed Results:")
    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {test_name}: {status}")
    
    if all(results.values()):
        print("\n[SUCCESS] ALL VALIDATIONS PASSED!")
        print("\nNext Steps:")
        print("  1. Create config/auto_execution_optimized_intervals.json to enable features")
        print("  2. Test with actual auto-execution system")
        print("  3. Monitor performance and resource usage")
        return 0
    else:
        print("\n[WARNING] SOME VALIDATIONS FAILED")
        print("  Review the errors above and fix implementation issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())
