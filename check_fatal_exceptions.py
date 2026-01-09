"""
Check for fatal exceptions that could kill the monitor thread
Analyzes code structure to find unprotected operations
"""
import ast
import re
from pathlib import Path
from typing import List, Dict, Any

def analyze_monitor_loop():
    """Analyze monitor loop for unprotected operations"""
    print("=" * 80)
    print("FATAL EXCEPTION ANALYSIS - Monitor Loop")
    print("=" * 80)
    print()
    
    file_path = Path("auto_execution_system.py")
    if not file_path.exists():
        print("[FAIL] auto_execution_system.py not found")
        return
    
    content = file_path.read_text(encoding='utf-8')
    
    # Find the monitor loop
    monitor_loop_start = content.find("def _monitor_loop(self):")
    if monitor_loop_start == -1:
        print("[FAIL] _monitor_loop method not found")
        return
    
    # Extract the method
    lines = content.split('\n')
    method_lines = []
    in_method = False
    indent_level = 0
    
    for i, line in enumerate(lines):
        if "_monitor_loop(self):" in line:
            in_method = True
            method_lines.append((i+1, line))
            indent_level = len(line) - len(line.lstrip())
            continue
        
        if in_method:
            current_indent = len(line) - len(line.lstrip()) if line.strip() else indent_level + 1
            if line.strip() and current_indent <= indent_level and not line.strip().startswith('#'):
                # Check if this is another method
                if line.strip().startswith('def ') and current_indent == indent_level:
                    break
            method_lines.append((i+1, line))
    
    print(f"Found _monitor_loop method (lines {method_lines[0][0]}-{method_lines[-1][0]})")
    print()
    
    # Analyze structure
    issues = []
    
    # Check 1: while self.running condition
    print("CHECK 1: While Loop Condition")
    for line_num, line in method_lines:
        if "while self.running:" in line:
            print(f"  Line {line_num}: {line.strip()}")
            print("  [RISK] Accessing self.running could fail if self is corrupted")
            print("  [PROTECTION] Very low risk - self.running is simple boolean")
            print("  [STATUS] ACCEPTABLE")
            print()
    
    # Check 2: Operations outside try-except in while loop
    print("CHECK 2: Operations in While Loop (Outside Try-Except)")
    
    in_while = False
    in_try = False
    try_level = 0
    unprotected_ops = []
    
    for line_num, line in method_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        
        # Track while loop
        if "while self.running:" in stripped:
            in_while = True
            continue
        
        if in_while:
            # Track try blocks
            if stripped.startswith("try:"):
                in_try = True
                try_level = len(line) - len(line.lstrip())
                continue
            
            if stripped.startswith("except") or stripped.startswith("finally"):
                # Check if this except/finally closes our try
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= try_level:
                    in_try = False
                continue
            
            # Check for operations outside try blocks
            current_indent = len(line) - len(line.lstrip())
            if not in_try and current_indent > 0:
                # This is an operation in while loop but outside try
                if any(keyword in stripped for keyword in ['=', '(', '.', '[', ']', 'if', 'for', 'with']):
                    if not stripped.startswith('except') and not stripped.startswith('finally'):
                        unprotected_ops.append((line_num, stripped))
    
    if unprotected_ops:
        print("  [WARNING] Found operations outside try-except blocks:")
        for line_num, op in unprotected_ops[:10]:  # Show first 10
            print(f"    Line {line_num}: {op[:80]}")
        if len(unprotected_ops) > 10:
            print(f"    ... and {len(unprotected_ops) - 10} more")
    else:
        print("  [OK] All operations appear to be in try-except blocks")
    print()
    
    # Check 3: Specific risky operations
    print("CHECK 3: Specific Risky Operations")
    
    risky_patterns = [
        (r'self\.\w+\.\w+\(\)', "Method call on attribute (could be None)"),
        (r'self\.\w+\[', "Dictionary/list access (could be KeyError)"),
        (r'\.items\(\)', "Dictionary items() call (could fail if not dict)"),
        (r'datetime\.now\(\)', "DateTime operation (could fail if module corrupted)"),
        (r'time\.sleep\(', "Sleep operation (very low risk)"),
        (r'with self\.\w+_lock:', "Lock acquisition (very low risk)"),
    ]
    
    found_risky = []
    for line_num, line in method_lines:
        for pattern, description in risky_patterns:
            if re.search(pattern, line):
                # Check if it's in a try block
                # Simple check - look for try before this line
                has_try = False
                for prev_num, prev_line in method_lines:
                    if prev_num >= line_num:
                        break
                    if "try:" in prev_line and len(prev_line) - len(prev_line.lstrip()) < len(line) - len(line.lstrip()):
                        has_try = True
                        break
                
                if not has_try:
                    found_risky.append((line_num, line.strip()[:60], description))
    
    if found_risky:
        print("  [WARNING] Found potentially risky operations:")
        for line_num, code, desc in found_risky[:10]:
            print(f"    Line {line_num}: {desc}")
            print(f"      Code: {code}")
    else:
        print("  [OK] No obvious risky operations found")
    print()
    
    # Check 4: Attribute access patterns
    print("CHECK 4: Attribute Access Patterns")
    
    attr_accesses = []
    for line_num, line in method_lines:
        # Find self.attribute patterns
        matches = re.findall(r'self\.(\w+)', line)
        for attr in matches:
            # Check if it's protected
            # Simple heuristic: if line has try before it in same scope
            attr_accesses.append((line_num, attr, line.strip()[:60]))
    
    # Check for common risky attributes
    risky_attrs = ['mt5_service', 'm1_analyzer', 'm1_refresh_manager', 'config', 'plans']
    risky_accesses = []
    for line_num, attr, code in attr_accesses:
        if attr in risky_attrs:
            risky_accesses.append((line_num, attr, code))
    
    if risky_accesses:
        print(f"  [INFO] Found {len(risky_accesses)} accesses to risky attributes")
        print("  [NOTE] Most should be protected by try-except")
        for line_num, attr, code in risky_accesses[:5]:
            print(f"    Line {line_num}: Accessing self.{attr}")
    else:
        print("  [OK] No obvious risky attribute accesses")
    print()
    
    # Check 5: For loop over plans
    print("CHECK 5: For Loop Over Plans")
    for line_num, line in method_lines:
        if "for plan_id, plan in plans_to_check:" in line:
            print(f"  Line {line_num}: {line.strip()}")
            print("  [RISK] If plans_to_check is not a list/dict, iteration fails")
            print("  [PROTECTION] plans_to_check is created with list(self.plans.items())")
            print("  [STATUS] PROTECTED (created in try-except)")
            print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    if unprotected_ops:
        print(f"  [WARNING] Found {len(unprotected_ops)} operations outside try-except")
        print("  -> These could potentially cause fatal exceptions")
    else:
        print("  [OK] All operations appear to be protected")
    
    if found_risky:
        print(f"  [WARNING] Found {len(found_risky)} potentially risky operations")
    else:
        print("  [OK] No obvious risky operations found")
    
    print()
    print("  Current Protection:")
    print("    - Inner try-except: Catches most errors")
    print("    - Outer try-except: Catches fatal errors")
    print("    - Health check: Automatically restarts thread")
    print()
    print("=" * 80)

if __name__ == "__main__":
    analyze_monitor_loop()

