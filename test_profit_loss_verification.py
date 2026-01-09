"""
Simple verification test for profit/loss implementation
Checks code structure without requiring imports
"""

import re
from pathlib import Path

def check_file_contains(file_path: Path, patterns: list, description: str) -> bool:
    """Check if file contains all patterns"""
    try:
        content = file_path.read_text(encoding='utf-8')
        for pattern in patterns:
            if not re.search(pattern, content, re.MULTILINE):
                print(f"  ❌ Missing: {pattern}")
                return False
        print(f"  ✅ {description}")
        return True
    except Exception as e:
        print(f"  ❌ Error reading file: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("PROFIT/LOSS IMPLEMENTATION VERIFICATION")
    print("="*60)
    
    results = []
    
    # Test 1: TradePlan dataclass
    print("\n1. Checking TradePlan dataclass...")
    if Path("auto_execution_system.py").exists():
        results.append(check_file_contains(
            Path("auto_execution_system.py"),
            [
                r"profit_loss.*Optional\[float\].*= None",
                r"exit_price.*Optional\[float\].*= None",
                r"close_time.*Optional\[str\].*= None",
                r"close_reason.*Optional\[str\].*= None"
            ],
            "TradePlan has all new fields"
        ))
    else:
        print("  ❌ auto_execution_system.py not found")
        results.append(False)
    
    # Test 2: Database loading handles new columns
    print("\n2. Checking database loading methods...")
    if Path("auto_execution_system.py").exists():
        results.append(check_file_contains(
            Path("auto_execution_system.py"),
            [
                r"row\[15\].*if len\(row\) > 15",
                r"row\[16\].*if len\(row\) > 16",
                r"row\[17\].*if len\(row\) > 17",
                r"row\[18\].*if len\(row\) > 18"
            ],
            "Database loading handles new columns with defensive checks"
        ))
    else:
        results.append(False)
    
    # Test 3: Migration script exists
    print("\n3. Checking migration script...")
    migration_file = Path("migrations/add_profit_loss_fields.py")
    if migration_file.exists():
        results.append(check_file_contains(
            migration_file,
            [
                r"ALTER TABLE trade_plans ADD COLUMN profit_loss",
                r"ALTER TABLE trade_plans ADD COLUMN exit_price",
                r"ALTER TABLE trade_plans ADD COLUMN close_time",
                r"ALTER TABLE trade_plans ADD COLUMN close_reason",
                r"with sqlite3.connect.*timeout=10.0"
            ],
            "Migration script exists and has all columns"
        ))
    else:
        print("  ❌ Migration script not found")
        results.append(False)
    
    # Test 4: Cache helper in main_api
    print("\n4. Checking cache helper function...")
    if Path("app/main_api.py").exists():
        results.append(check_file_contains(
            Path("app/main_api.py"),
            [
                r"async def get_cached_outcome",
                r"_cache_lock = asyncio.Lock",
                r"run_in_executor",
                r"PlanEffectivenessTracker"
            ],
            "Cache helper function is async and thread-safe"
        ))
    else:
        results.append(False)
    
    # Test 5: Web endpoint has profit/loss logic
    print("\n5. Checking web endpoint...")
    if Path("app/main_api.py").exists():
        results.append(check_file_contains(
            Path("app/main_api.py"),
            [
                r"trade_results.*=.*\{\}",
                r"summary_stats.*=.*\{",
                r"profit_loss.*plan.get",
                r"get_cached_outcome"
            ],
            "Web endpoint has profit/loss querying logic"
        ))
    else:
        results.append(False)
    
    # Test 6: HTML template has new columns
    print("\n6. Checking HTML template...")
    if Path("app/main_api.py").exists():
        results.append(check_file_contains(
            Path("app/main_api.py"),
            [
                r"<th>Profit/Loss</th>",
                r"<th>Exit Price</th>",
                r"<th>Close Time</th>",
                r"profit-positive|profit-negative|profit-open|profit-na"
            ],
            "HTML template has new columns and CSS classes"
        ))
    else:
        results.append(False)
    
    # Test 7: Outcome tracker exists
    print("\n7. Checking AutoExecutionOutcomeTracker...")
    tracker_file = Path("infra/auto_execution_outcome_tracker.py")
    if tracker_file.exists():
        results.append(check_file_contains(
            tracker_file,
            [
                r"class AutoExecutionOutcomeTracker",
                r"async def start",
                r"async def _check_and_update_outcomes",
                r"run_in_executor",
                r"with sqlite3.connect.*timeout=10.0"
            ],
            "AutoExecutionOutcomeTracker exists with async methods"
        ))
    else:
        print("  ❌ AutoExecutionOutcomeTracker not found")
        results.append(False)
    
    # Test 8: Integration in chatgpt_bot
    print("\n8. Checking integration in chatgpt_bot...")
    if Path("chatgpt_bot.py").exists():
        results.append(check_file_contains(
            Path("chatgpt_bot.py"),
            [
                r"AutoExecutionOutcomeTracker",
                r"auto_execution_outcome_tracker"
            ],
            "Background task integrated in chatgpt_bot"
        ))
    else:
        results.append(False)
    
    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for result in results if result)
    total = len(results)
    
    test_names = [
        "TradePlan Dataclass",
        "Database Loading",
        "Migration Script",
        "Cache Helper",
        "Web Endpoint Logic",
        "HTML Template",
        "Outcome Tracker",
        "Background Integration"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} verifications passed")
    
    if passed == total:
        print("\n🎉 All code structure checks passed!")
        print("\nNext steps:")
        print("1. Run migration: python migrations/add_profit_loss_fields.py")
        print("2. Test web interface: http://localhost:8000/auto-execution/view?status_filter=executed")
        print("3. Check logs for background task: 'Auto-execution outcome tracker scheduled'")
        return 0
    else:
        print(f"\n⚠️ {total - passed} verification(s) failed.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())

