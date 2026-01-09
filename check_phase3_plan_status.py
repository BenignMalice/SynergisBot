"""Check Phase III test plan status and condition checks"""
import sys
import json
import codecs
import sqlite3
from pathlib import Path
from datetime import datetime

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

def check_plans_in_database():
    """Check test plans in database"""
    print("="*70)
    print("Checking Test Plans in Database")
    print("="*70)
    
    db_path = "data/auto_execution.db"
    # Latest test plan IDs (created 2026-01-07 20:43)
    test_plan_ids = ["chatgpt_1d801fab", "chatgpt_be4af5f0"]
    
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            for plan_id in test_plan_ids:
                cursor.execute("""
                    SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
                           conditions, status, created_at, notes
                    FROM trade_plans
                    WHERE plan_id = ?
                """, (plan_id,))
                
                row = cursor.fetchone()
                if row:
                    print(f"\n✅ Plan {plan_id}:")
                    print(f"   Symbol: {row['symbol']}")
                    print(f"   Direction: {row['direction']}")
                    print(f"   Status: {row['status']}")
                    print(f"   Entry: {row['entry_price']}")
                    print(f"   SL: {row['stop_loss']} | TP: {row['take_profit']}")
                    print(f"   Created: {row['created_at']}")
                    
                    # Parse conditions
                    try:
                        conditions = json.loads(row['conditions'])
                        print(f"\n   Phase III Conditions:")
                        phase3_found = False
                        for key, value in conditions.items():
                            if any(phase3 in key.lower() for phase3 in ['choch', 'consecutive', 'volatility_fractal', 'm5', 'm15', 'm30']):
                                print(f"      ✅ {key}: {value}")
                                phase3_found = True
                        
                        if not phase3_found:
                            print(f"      ⚠️  No Phase III conditions found")
                            print(f"      All conditions: {list(conditions.keys())}")
                    except Exception as e:
                        print(f"   ⚠️  Error parsing conditions: {e}")
                        print(f"   Raw: {row['conditions'][:200]}")
                else:
                    print(f"\n❌ Plan {plan_id} not found in database")
            
            # Count total pending plans
            cursor.execute("SELECT COUNT(*) FROM trade_plans WHERE status = 'pending'")
            pending_count = cursor.fetchone()[0]
            print(f"\n📊 Total pending plans in database: {pending_count}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()
        return False

def search_logs_for_condition_checks():
    """Search logs for condition check messages"""
    print("\n" + "="*70)
    print("Searching Logs for Condition Check Messages")
    print("="*70)
    
    log_file = Path("data/logs/chatgpt_bot.log")
    # Latest test plan IDs (created 2026-01-07 20:43)
    test_plan_ids = ["chatgpt_1d801fab", "chatgpt_be4af5f0"]
    
    if not log_file.exists():
        print(f"❌ Log file not found: {log_file}")
        return False
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        print(f"📊 Checking last 500 lines of log file...")
        recent_lines = lines[-500:] if len(lines) > 500 else lines
        
        # Search for condition check patterns
        check_patterns = [
            "checking plan",
            "plan.*condition",
            "condition.*check",
            "choch_bull_m5",
            "choch_bull_m15",
            "consecutive_inside_bars",
            "volatility_fractal",
            "check_conditions"
        ]
        
        matches = []
        for i, line in enumerate(recent_lines):
            line_lower = line.lower()
            for pattern in check_patterns:
                if pattern.lower() in line_lower:
                    # Check if it's related to our test plans
                    for plan_id in test_plan_ids:
                        if plan_id in line:
                            matches.append((i + len(lines) - len(recent_lines) + 1, line.strip(), plan_id, pattern))
                            break
                    else:
                        # General condition check
                        if "auto_execution" in line_lower or "check_conditions" in line_lower:
                            matches.append((i + len(lines) - len(recent_lines) + 1, line.strip(), "general", pattern))
        
        if matches:
            print(f"\n✅ Found {len(matches)} condition check messages:")
            
            # Group by plan
            plan_groups = {}
            for line_num, line, plan_id, pattern in matches:
                if plan_id not in plan_groups:
                    plan_groups[plan_id] = []
                plan_groups[plan_id].append((line_num, line, pattern))
            
            for plan_id, entries in plan_groups.items():
                print(f"\n   {plan_id}:")
                for line_num, line, pattern in entries[-5:]:  # Last 5 per plan
                    print(f"      Line {line_num} [{pattern}]: {line[:120]}")
        else:
            print(f"\n⚠️  No condition check messages found for test plans")
            print(f"   This may mean:")
            print(f"   - Plans haven't been checked yet (checks every 30 seconds)")
            print(f"   - Condition checks don't log at INFO level")
            print(f"   - Logs are in a different location")
        
        # Check for general auto-execution activity
        auto_exec_matches = []
        for i, line in enumerate(recent_lines):
            if "auto_execution_system" in line.lower() and any(word in line.lower() for word in ["check", "monitor", "plan"]):
                auto_exec_matches.append((i + len(lines) - len(recent_lines) + 1, line.strip()))
        
        if auto_exec_matches:
            print(f"\n📊 General Auto-Execution Activity (last 5):")
            for line_num, line in auto_exec_matches[-5:]:
                print(f"   Line {line_num}: {line[:120]}")
        
        return len(matches) > 0
        
    except Exception as e:
        print(f"❌ Error reading log file: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_ui_accessibility():
    """Check if UI is accessible"""
    print("\n" + "="*70)
    print("Checking UI Accessibility")
    print("="*70)
    
    import urllib.request
    
    endpoint = "http://localhost:8000/auto-execution/view"
    
    try:
        with urllib.request.urlopen(endpoint, timeout=5) as response:
            if response.status == 200:
                print(f"✅ UI endpoint accessible: {endpoint}")
                print(f"   Status: {response.status}")
                print(f"   💡 Open in browser: {endpoint}")
                return True
            else:
                print(f"⚠️  UI endpoint returned status: {response.status}")
                return False
    except urllib.error.URLError as e:
        print(f"❌ Cannot connect to UI: {e}")
        print(f"   Make sure API server is running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("="*70)
    print("Phase III Test Plan Status Check")
    print("="*70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    # Check 1: Database
    db_ok = check_plans_in_database()
    
    # Check 2: Logs
    logs_ok = search_logs_for_condition_checks()
    
    # Check 3: UI
    ui_ok = check_ui_accessibility()
    
    # Summary
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    print(f"Database Check:  {'✅ PASS' if db_ok else '❌ FAIL'}")
    print(f"Logs Check:      {'✅ Activity Found' if logs_ok else '⚠️  No condition checks found yet'}")
    print(f"UI Accessibility: {'✅ ACCESSIBLE' if ui_ok else '❌ NOT ACCESSIBLE'}")
    
    print("\n💡 Recommendations:")
    if not logs_ok:
        print("   - Wait 30-60 seconds for next condition check cycle")
        print("   - Check API server console window for real-time logs")
        print("   - Condition checks may be at DEBUG level (not in logs)")
    if ui_ok:
        print(f"   - Visit http://localhost:8000/auto-execution/view in your browser to view plans")
    print("   - Plans will execute automatically when conditions are met")

