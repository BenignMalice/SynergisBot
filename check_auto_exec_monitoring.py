"""
Check if auto-execution plan monitoring system is running properly
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure stdout encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

print("=" * 80)
print("AUTO-EXECUTION PLAN MONITORING SYSTEM CHECK")
print("=" * 80)
print()

# Check 1: System Status via API
print("1. Checking Auto-Execution System Status (via API)...")
try:
    import httpx
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get("http://localhost:8000/auto-execution/system-status")
            if response.status_code == 200:
                status_data = response.json()
                print(f"   ✅ System status endpoint responding")
                print(f"   📊 Status data:")
                for key, value in status_data.items():
                    if key == "pending_plans" and isinstance(value, list):
                        print(f"      • {key}: {len(value)} plans")
                    else:
                        print(f"      • {key}: {value}")
                
                # Check critical fields
                is_running = status_data.get("running", False)
                pending_count = len(status_data.get("pending_plans", []))
                check_interval = status_data.get("check_interval", "unknown")
                
                if is_running:
                    print(f"\n   ✅ System is RUNNING")
                else:
                    print(f"\n   ❌ System is NOT running")
                
                print(f"   📊 Pending plans: {pending_count}")
                print(f"   📊 Check interval: {check_interval} seconds")
                
            else:
                print(f"   ⚠️  API returned status {response.status_code}")
                print(f"   📊 Response: {response.text[:200]}")
    except httpx.ConnectError:
        print(f"   ❌ Cannot connect to API server (connection refused)")
        print(f"   💡 Main API server may not be running")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        
except Exception as e:
    print(f"   ❌ Error checking API: {e}")

print()

# Check 2: Check Database for Plans
print("2. Checking Database for Trade Plans...")
try:
    import sqlite3
    
    db_path = "data/auto_execution.db"
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all plans
        cursor.execute("""
            SELECT plan_id, symbol, direction, status, created_at, expires_at, executed_at
            FROM trade_plans
            ORDER BY created_at DESC
        """)
        all_plans = cursor.fetchall()
        
        print(f"   ✅ Database exists: {db_path}")
        print(f"   📊 Total plans: {len(all_plans)}")
        
        # Count by status
        status_counts = {}
        for plan in all_plans:
            status = plan['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"   📊 Plans by status:")
        for status, count in status_counts.items():
            print(f"      • {status}: {count}")
        
        # Show pending plans
        pending_plans = [p for p in all_plans if p['status'] == 'pending']
        print(f"\n   📊 Pending plans: {len(pending_plans)}")
        if pending_plans:
            print(f"   📊 Recent pending plans:")
            for plan in pending_plans[:5]:
                expires = plan['expires_at'] if plan['expires_at'] else 'No expiration'
                print(f"      • {plan['plan_id']}: {plan['symbol']} {plan['direction']} (expires: {expires})")
            if len(pending_plans) > 5:
                print(f"      ... and {len(pending_plans) - 5} more")
        
        # Check for expired plans that are still pending
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        expired_but_pending = []
        for plan in pending_plans:
            if plan['expires_at']:
                try:
                    expires_dt = datetime.fromisoformat(plan['expires_at'].replace('Z', '+00:00'))
                    if expires_dt.tzinfo is None:
                        expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                    if expires_dt < now_utc:
                        expired_but_pending.append(plan)
                except:
                    pass
        
        if expired_but_pending:
            print(f"\n   ⚠️  Found {len(expired_but_pending)} expired plans still marked as 'pending'")
            print(f"   💡 These should be marked as 'expired' by the monitoring system")
        
        conn.close()
    else:
        print(f"   ⚠️  Database not found: {db_path}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 3: Verify System Initialization
print("3. Checking System Initialization...")
try:
    # Check if start_auto_execution_system is called in main_api.py
    main_api_path = os.path.join(os.path.dirname(__file__), "app/main_api.py")
    if os.path.exists(main_api_path):
        with open(main_api_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "start_auto_execution_system" in content:
            print(f"   ✅ start_auto_execution_system() found in main_api.py")
            
            # Check if it's called in startup_event
            if "startup_event" in content and "start_auto_execution_system" in content:
                # Check if it's in the startup function
                startup_section = content[content.find("async def startup_event"):content.find("async def startup_event") + 2000]
                if "start_auto_execution_system" in startup_section:
                    print(f"   ✅ start_auto_execution_system() called in startup_event")
                else:
                    print(f"   ⚠️  start_auto_execution_system() not in startup_event")
        else:
            print(f"   ❌ start_auto_execution_system() NOT found in main_api.py")
    else:
        print(f"   ❌ main_api.py not found")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check 4: Check Monitoring Loop Implementation
print("4. Checking Monitoring Loop Implementation...")
try:
    auto_exec_path = os.path.join(os.path.dirname(__file__), "auto_execution_system.py")
    if os.path.exists(auto_exec_path):
        with open(auto_exec_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = {
            "_monitor_loop method": "_monitor_loop" in content,
            "self.running flag": "self.running" in content,
            "start() method": "def start(" in content,
            "threading.Thread": "threading.Thread" in content or "threading" in content,
            "Periodic plan reload": "_load_plans" in content or "reload" in content.lower(),
        }
        
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check}")
        
        # Check for monitoring interval
        if "check_interval" in content:
            print(f"   ✅ check_interval configuration found")
        else:
            print(f"   ⚠️  check_interval not found")
            
    else:
        print(f"   ❌ auto_execution_system.py not found")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check 5: Check for Recent Monitoring Activity
print("5. Checking for Recent Monitoring Activity...")
try:
    import glob
    from datetime import datetime, timedelta
    
    # Look for log files
    log_files = []
    for pattern in ['*.log', 'app*.log', 'main_api*.log']:
        log_files.extend(glob.glob(pattern))
    
    if log_files:
        # Get most recent log file
        most_recent = max(log_files, key=os.path.getmtime)
        print(f"   📊 Checking: {most_recent}")
        
        try:
            with open(most_recent, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Look for auto-execution monitoring messages
            monitoring_patterns = [
                'auto execution system',
                'monitoring loop',
                'monitor_loop',
                'checking plan',
                'plan.*condition',
                'executing plan',
                'plan.*executed'
            ]
            
            recent_activity = []
            for line in lines[-500:]:  # Last 500 lines
                for pattern in monitoring_patterns:
                    if pattern.lower() in line.lower():
                        recent_activity.append((line.strip()[:120], pattern))
                        break
            
            if recent_activity:
                print(f"   ✅ Found {len(recent_activity)} recent monitoring-related log entries")
                print(f"   📊 Recent entries:")
                for line, pattern in recent_activity[-5:]:  # Last 5
                    print(f"      • [{pattern}] {line}")
            else:
                print(f"   ⚠️  No recent monitoring activity found in logs")
                print(f"   💡 This may indicate monitoring is not running")
        except Exception as e:
            print(f"   ⚠️  Could not read log file: {e}")
    else:
        print(f"   ⚠️  No log files found")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check 6: Verify System Instance
print("6. Checking System Instance...")
try:
    # Try to get the system instance
    from auto_execution_system import get_auto_execution_system
    
    system = get_auto_execution_system()
    if system:
        print(f"   ✅ Auto-execution system instance found")
        
        # Check if running
        if hasattr(system, 'running'):
            print(f"   📊 System running flag: {system.running}")
            if system.running:
                print(f"   ✅ System is marked as running")
            else:
                print(f"   ❌ System is NOT running")
        
        # Check if monitor thread exists
        if hasattr(system, 'monitor_thread'):
            if system.monitor_thread:
                print(f"   ✅ Monitor thread exists")
                if system.monitor_thread.is_alive():
                    print(f"   ✅ Monitor thread is ALIVE")
                else:
                    print(f"   ❌ Monitor thread is NOT alive")
            else:
                print(f"   ❌ Monitor thread is None")
        else:
            print(f"   ⚠️  Monitor thread attribute not found")
        
        # Check pending plans count
        if hasattr(system, 'plans'):
            plan_count = len(system.plans) if system.plans else 0
            print(f"   📊 Plans in memory: {plan_count}")
        else:
            print(f"   ⚠️  Plans attribute not found")
            
    else:
        print(f"   ❌ Auto-execution system instance is None")
        print(f"   💡 System may not be initialized")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 7: Check Startup Event
print("7. Checking Startup Event Configuration...")
try:
    main_api_path = os.path.join(os.path.dirname(__file__), "app/main_api.py")
    if os.path.exists(main_api_path):
        with open(main_api_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find startup_event function
        if "async def startup_event" in content:
            # Extract startup_event section
            start_idx = content.find("async def startup_event")
            end_idx = content.find("async def shutdown_event", start_idx)
            if end_idx == -1:
                end_idx = start_idx + 5000  # Read next 5000 chars
            
            startup_section = content[start_idx:end_idx]
            
            if "start_auto_execution_system" in startup_section:
                print(f"   ✅ start_auto_execution_system() called in startup_event")
                
                # Check if it's properly imported
                if "from auto_execution_system import start_auto_execution_system" in content:
                    print(f"   ✅ start_auto_execution_system imported")
                elif "import start_auto_execution_system" in content:
                    print(f"   ✅ start_auto_execution_system imported (alternative)")
                else:
                    print(f"   ⚠️  start_auto_execution_system import not found")
            else:
                print(f"   ❌ start_auto_execution_system() NOT called in startup_event")
                print(f"   💡 System will not start automatically")
        else:
            print(f"   ⚠️  startup_event function not found")
            
    else:
        print(f"   ❌ main_api.py not found")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Summary
print("=" * 80)
print("AUTO-EXECUTION MONITORING STATUS SUMMARY")
print("=" * 80)
print()
print("✅ TO VERIFY:")
print("   1. Check system status via API: /auto-execution/system-status")
print("   2. Verify 'running' field is True")
print("   3. Check 'pending_plans' count matches database")
print("   4. Verify monitor thread is alive")
print()
print("⚠️  COMMON ISSUES:")
print("   • System not started: Check if start_auto_execution_system() is called")
print("   • Thread not alive: System may have crashed, check logs")
print("   • Plans not monitoring: Check if plans are loaded from database")
print("   • Expired plans: Should be marked as 'expired' automatically")
print()
print("🔧 IF SYSTEM NOT RUNNING:")
print("   1. Restart main API server (app/main_api.py)")
print("   2. Check logs for 'Auto execution system started' message")
print("   3. Verify no errors during startup")
print("   4. Check system status endpoint for details")
print()
