"""
Monitor Auto-Execution System Logs for Phase III Condition Checks
Check /auto-execution/view to see plans in the UI
"""

import sys
import json
import codecs
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

def check_logs_for_phase3():
    """Check logs for Phase III condition checks"""
    print("="*70)
    print("Checking Auto-Execution System Logs for Phase III Condition Checks")
    print("="*70)
    
    log_file = Path("data/logs/chatgpt_bot.log")
    
    if not log_file.exists():
        print(f"❌ Log file not found: {log_file}")
        return False
    
    print(f"\n📊 Checking log file: {log_file}")
    print(f"   Last modified: {datetime.fromtimestamp(log_file.stat().st_mtime)}")
    
    # Phase III condition patterns to search for
    phase3_patterns = [
        "Phase III",
        "choch_bull_m5",
        "choch_bull_m15",
        "choch_bear_m5",
        "choch_bear_m15",
        "consecutive_inside_bars",
        "volatility_fractal_expansion",
        "dxy_change_pct",
        "imbalance_detected",
        "mitigation_cascade",
        "breaker_retest",
        "momentum_decay",
        "news_absorption",
        "m1_pullback",
        "fvg_bull_m30",
        "fvg_bear_m30"
    ]
    
    # Latest test plan IDs (update after creating new plans)
    test_plan_ids = ["chatgpt_1d801fab", "chatgpt_be4af5f0"]
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        print(f"\n📈 Total log lines: {len(lines)}")
        print(f"   Checking last 1000 lines for Phase III activity...")
        
        # Check last 1000 lines
        recent_lines = lines[-1000:] if len(lines) > 1000 else lines
        
        phase3_matches = []
        plan_matches = []
        
        for i, line in enumerate(recent_lines):
            line_lower = line.lower()
            
            # Check for Phase III patterns
            for pattern in phase3_patterns:
                if pattern.lower() in line_lower:
                    phase3_matches.append((i + len(lines) - len(recent_lines) + 1, line.strip()[:150], pattern))
            
            # Check for test plan IDs
            for plan_id in test_plan_ids:
                if plan_id in line:
                    plan_matches.append((i + len(lines) - len(recent_lines) + 1, line.strip()[:150], plan_id))
        
        # Report findings
        print(f"\n🔍 Phase III Condition Check Results:")
        print(f"   Found {len(phase3_matches)} Phase III-related log entries")
        print(f"   Found {len(plan_matches)} test plan-related log entries")
        
        if phase3_matches:
            print(f"\n✅ Phase III Activity Detected:")
            # Group by pattern
            pattern_groups = {}
            for line_num, line, pattern in phase3_matches[-10:]:  # Last 10
                if pattern not in pattern_groups:
                    pattern_groups[pattern] = []
                pattern_groups[pattern].append((line_num, line))
            
            for pattern, entries in list(pattern_groups.items())[:5]:  # Top 5 patterns
                print(f"\n   Pattern: {pattern}")
                for line_num, line in entries[-3:]:  # Last 3 per pattern
                    print(f"      Line {line_num}: {line}")
        else:
            print(f"\n⚠️  No Phase III condition checks found in recent logs")
            print(f"   This may mean:")
            print(f"   - Auto-execution system hasn't checked conditions yet")
            print(f"   - Plans were just created (checks happen every 30 seconds)")
            print(f"   - Logs are in a different location")
        
        if plan_matches:
            print(f"\n✅ Test Plan Activity Detected:")
            for line_num, line, plan_id in plan_matches[-5:]:  # Last 5
                print(f"   Plan {plan_id}:")
                print(f"      Line {line_num}: {line}")
        else:
            print(f"\n⚠️  No test plan activity found in recent logs")
        
        # Check for auto-execution monitoring messages
        monitoring_patterns = [
            "monitoring loop",
            "checking plan",
            "plan.*condition",
            "auto execution system",
            "monitor_loop"
        ]
        
        monitoring_matches = []
        for i, line in enumerate(recent_lines):
            line_lower = line.lower()
            for pattern in monitoring_patterns:
                if pattern.lower() in line_lower:
                    monitoring_matches.append((i + len(lines) - len(recent_lines) + 1, line.strip()[:150]))
                    break
        
        if monitoring_matches:
            print(f"\n✅ Auto-Execution Monitoring Active:")
            for line_num, line in monitoring_matches[-5:]:  # Last 5
                print(f"   Line {line_num}: {line}")
        else:
            print(f"\n⚠️  No monitoring activity found in recent logs")
        
        return len(phase3_matches) > 0 or len(plan_matches) > 0
        
    except Exception as e:
        print(f"❌ Error reading log file: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_ui_endpoint():
    """Check /auto-execution/view endpoint"""
    print("\n" + "="*70)
    print("Checking /auto-execution/view UI Endpoint")
    print("="*70)
    
    API_BASE_URL = "http://localhost:8000"
    endpoint = f"{API_BASE_URL}/auto-execution/view"
    
    print(f"\n🌐 Checking endpoint: {endpoint}")
    
    try:
        # Try to get the view page
        with urllib.request.urlopen(endpoint, timeout=10) as response:
            html = response.read().decode('utf-8')
            
            # Check if our test plans are in the HTML
            test_plan_ids = ["chatgpt_d05d9985", "chatgpt_0a116fe0"]
            
            print(f"✅ UI endpoint accessible (Status: {response.status})")
            
            found_plans = []
            for plan_id in test_plan_ids:
                if plan_id in html:
                    found_plans.append(plan_id)
                    print(f"   ✅ Plan {plan_id} found in UI")
            
            if not found_plans:
                print(f"   ⚠️  Test plans not found in UI HTML")
                print(f"   (They may be in a different format or loaded via JavaScript)")
            
            # Check for Phase III condition indicators
            phase3_indicators = [
                "choch_bull_m5",
                "choch_bull_m15",
                "consecutive_inside_bars",
                "volatility_fractal_expansion"
            ]
            
            found_indicators = []
            for indicator in phase3_indicators:
                if indicator in html:
                    found_indicators.append(indicator)
            
            if found_indicators:
                print(f"\n   ✅ Phase III conditions visible in UI:")
                for indicator in found_indicators:
                    print(f"      - {indicator}")
            
            return True
            
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error {e.code}: {e.reason}")
        if e.code == 404:
            print(f"   Endpoint may not exist or route is different")
        return False
    except urllib.error.URLError as e:
        print(f"❌ Connection Error: {e}")
        print(f"   Make sure API server is running on {API_BASE_URL}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_plans_via_api():
    """Check plans via API"""
    print("\n" + "="*70)
    print("Checking Plans via API")
    print("="*70)
    
    API_BASE_URL = "http://localhost:8000"
    
    # Try to get all plans
    try:
        url = f"{API_BASE_URL}/auto-execution/plans"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if isinstance(data, list):
                print(f"✅ Found {len(data)} plans via API")
                
                test_plan_ids = ["chatgpt_d05d9985", "chatgpt_0a116fe0"]
                
                for plan in data:
                    plan_id = plan.get('plan_id', '')
                    if plan_id in test_plan_ids:
                        print(f"\n✅ Test Plan {plan_id}:")
                        print(f"   Symbol: {plan.get('symbol')}")
                        print(f"   Direction: {plan.get('direction')}")
                        print(f"   Status: {plan.get('status')}")
                        print(f"   Entry: {plan.get('entry_price')}")
                        
                        conditions = plan.get('conditions', {})
                        if isinstance(conditions, str):
                            try:
                                conditions = json.loads(conditions)
                            except:
                                pass
                        
                        print(f"   Phase III Conditions:")
                        phase3_conds = []
                        for key in ['choch_bull_m5', 'choch_bull_m15', 'consecutive_inside_bars', 
                                   'volatility_fractal_expansion', 'bb_expansion']:
                            if key in conditions:
                                phase3_conds.append(f"{key}: {conditions[key]}")
                        
                        if phase3_conds:
                            for cond in phase3_conds:
                                print(f"      - {cond}")
                        else:
                            print(f"      (No Phase III conditions found in response)")
                
                return True
            else:
                print(f"⚠️  Unexpected API response format: {type(data)}")
                return False
                
    except urllib.error.HTTPError as e:
        print(f"⚠️  HTTP Error {e.code}: {e.reason}")
        print(f"   Endpoint may be different or require authentication")
        return False
    except urllib.error.URLError as e:
        print(f"⚠️  Connection Error: {e}")
        print(f"   API server may not be running")
        return False
    except Exception as e:
        print(f"⚠️  Error: {e}")
        return False

if __name__ == "__main__":
    print("="*70)
    print("Phase III Condition Monitoring & UI Check")
    print("="*70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Check 1: Logs
    logs_ok = check_logs_for_phase3()
    
    # Check 2: UI Endpoint
    ui_ok = check_ui_endpoint()
    
    # Check 3: API
    api_ok = check_plans_via_api()
    
    # Summary
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    print(f"Logs Check:     {'✅ PASS' if logs_ok else '⚠️  No Phase III activity found'}")
    print(f"UI Endpoint:    {'✅ ACCESSIBLE' if ui_ok else '❌ NOT ACCESSIBLE'}")
    print(f"API Check:      {'✅ PASS' if api_ok else '⚠️  FAILED'}")
    
    print("\n💡 Next Steps:")
    print("   1. If no Phase III activity in logs, wait 30-60 seconds for next check cycle")
    print("   2. Check API server console window for real-time condition checks")
    print("   3. Visit http://localhost:8000/auto-execution/view in browser")
    print("   4. Monitor logs in real-time: tail -f data/logs/chatgpt_bot.log")

