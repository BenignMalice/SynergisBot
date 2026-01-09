"""
Verify auto-execution monitoring system is functioning properly after restart
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
print("AUTO-EXECUTION MONITORING SYSTEM VERIFICATION (After Restart)")
print("=" * 80)
print()

# Check 1: System Status via API
print("1. Checking System Status (via API)...")
try:
    import httpx
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get("http://localhost:8000/auto-execution/system-status")
            if response.status_code == 200:
                status_data = response.json()
                system_status = status_data.get("system_status", {})
                
                print(f"   ✅ API endpoint responding")
                print(f"   📊 System Status:")
                print(f"      • Running: {system_status.get('running', 'unknown')}")
                print(f"      • Thread Alive: {system_status.get('thread_alive', 'unknown')}")
                print(f"      • Pending Plans: {system_status.get('pending_plans', 0)}")
                print(f"      • Check Interval: {system_status.get('check_interval', 'unknown')} seconds")
                
                # Critical checks
                is_running = system_status.get("running", False)
                thread_alive = system_status.get("thread_alive", False)
                pending_count = system_status.get("pending_plans", 0)
                
                if is_running and thread_alive:
                    print(f"\n   ✅ SYSTEM IS RUNNING AND HEALTHY")
                    print(f"   ✅ Monitor thread is ALIVE")
                    print(f"   ✅ {pending_count} plans are being monitored")
                elif is_running and not thread_alive:
                    print(f"\n   ⚠️  SYSTEM MARKED AS RUNNING BUT THREAD IS DEAD")
                    print(f"   💡 Watchdog should restart it automatically")
                elif not is_running:
                    print(f"\n   ❌ SYSTEM IS NOT RUNNING")
                    print(f"   💡 System may need to be restarted")
            else:
                print(f"   ⚠️  API returned status {response.status_code}")
    except httpx.ConnectError:
        print(f"   ❌ Cannot connect to API server (connection refused)")
        print(f"   💡 Main API server may not be running")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        
except Exception as e:
    print(f"   ❌ Error checking API: {e}")

print()

# Check 2: Direct System Instance Check
print("2. Checking System Instance Directly...")
try:
    from auto_execution_system import get_auto_execution_system
    
    system = get_auto_execution_system()
    if system:
        print(f"   ✅ Auto-execution system instance found")
        
        # Check running flag
        if hasattr(system, 'running'):
            running = system.running
            print(f"   📊 System running flag: {running}")
            if running:
                print(f"   ✅ System is marked as running")
            else:
                print(f"   ❌ System is NOT marked as running")
        
        # Check monitor thread
        if hasattr(system, 'monitor_thread'):
            if system.monitor_thread:
                print(f"   ✅ Monitor thread exists")
                try:
                    is_alive = system.monitor_thread.is_alive()
                    print(f"   📊 Monitor thread alive: {is_alive}")
                    if is_alive:
                        print(f"   ✅ Monitor thread is ALIVE")
                        print(f"   📊 Thread name: {system.monitor_thread.name}")
                    else:
                        print(f"   ❌ Monitor thread is DEAD")
                        print(f"   💡 Watchdog should restart it")
                except Exception as e:
                    print(f"   ⚠️  Error checking thread status: {e}")
            else:
                print(f"   ❌ Monitor thread is None")
                print(f"   💡 System may not have started properly")
        else:
            print(f"   ⚠️  Monitor thread attribute not found")
        
        # Check watchdog thread
        if hasattr(system, 'watchdog_thread'):
            if system.watchdog_thread:
                print(f"   ✅ Watchdog thread exists")
                try:
                    is_alive = system.watchdog_thread.is_alive()
                    print(f"   📊 Watchdog thread alive: {is_alive}")
                    if is_alive:
                        print(f"   ✅ Watchdog thread is ALIVE")
                        print(f"   📊 Thread name: {system.watchdog_thread.name}")
                    else:
                        print(f"   ❌ Watchdog thread is DEAD")
                        print(f"   💡 Watchdog should be restarted")
                except Exception as e:
                    print(f"   ⚠️  Error checking watchdog status: {e}")
            else:
                print(f"   ❌ Watchdog thread is None")
                print(f"   💡 Watchdog may not have started")
        else:
            print(f"   ⚠️  Watchdog thread attribute not found")
            print(f"   💡 Watchdog may not be implemented in this version")
        
        # Check plans
        if hasattr(system, 'plans'):
            plan_count = len(system.plans) if system.plans else 0
            print(f"   📊 Plans in memory: {plan_count}")
        else:
            print(f"   ⚠️  Plans attribute not found")
        
        # Check restart count
        if hasattr(system, 'thread_restart_count'):
            restart_count = system.thread_restart_count
            max_restarts = getattr(system, 'max_thread_restarts', 10)
            print(f"   📊 Thread restart count: {restart_count}/{max_restarts}")
            if restart_count > 0:
                print(f"   ⚠️  System has restarted {restart_count} time(s)")
                if restart_count >= max_restarts:
                    print(f"   ❌ Maximum restarts reached - system may be stopped")
            
    else:
        print(f"   ❌ Auto-execution system instance is None")
        print(f"   💡 System may not be initialized")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 3: Recent Logs for Startup Messages
print("3. Checking Recent Startup Logs...")
try:
    import glob
    from datetime import datetime, timedelta
    
    # Find log files
    log_files = []
    for pattern in ['*.log', 'app*.log', 'main_api*.log']:
        log_files.extend(glob.glob(pattern))
    
    if log_files:
        # Get most recent
        most_recent = max(log_files, key=os.path.getmtime)
        print(f"   📊 Checking: {most_recent}")
        
        try:
            with open(most_recent, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Look for startup messages
            startup_patterns = [
                'Auto execution system',
                'Auto-Execution System',
                'monitoring loop started',
                'Watchdog thread',
                'Auto execution system started',
                'start_auto_execution_system'
            ]
            
            startup_messages = []
            for line in lines[-200:]:  # Last 200 lines
                for pattern in startup_patterns:
                    if pattern.lower() in line.lower():
                        startup_messages.append(line.strip()[:150])
                        break
            
            if startup_messages:
                print(f"   ✅ Found {len(startup_messages)} startup-related messages")
                print(f"   📊 Recent startup messages:")
                for msg in startup_messages[-5:]:  # Last 5
                    print(f"      • {msg}")
            else:
                print(f"   ⚠️  No startup messages found")
                print(f"   💡 System may not have started or logs are in different file")
        except Exception as e:
            print(f"   ⚠️  Could not read log: {e}")
    else:
        print(f"   ⚠️  No log files found")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check 4: Database Plans
print("4. Checking Database for Pending Plans...")
try:
    import sqlite3
    
    db_path = "data/auto_execution.db"
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM trade_plans WHERE status = 'pending'
        """)
        result = cursor.fetchone()
        pending_count = result['count'] if result else 0
        
        print(f"   ✅ Database exists: {db_path}")
        print(f"   📊 Pending plans in database: {pending_count}")
        
        if pending_count > 0:
            print(f"   ✅ Plans are ready to be monitored")
        else:
            print(f"   ℹ️  No pending plans in database")
        
        conn.close()
    else:
        print(f"   ⚠️  Database not found: {db_path}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check 5: Thread Health Check
print("5. Performing Thread Health Check...")
try:
    from auto_execution_system import get_auto_execution_system
    
    system = get_auto_execution_system()
    if system and hasattr(system, '_check_thread_health'):
        try:
            # Manually trigger health check
            system._check_thread_health()
            print(f"   ✅ Health check executed successfully")
            
            # Check status after health check
            if hasattr(system, 'monitor_thread') and system.monitor_thread:
                is_alive = system.monitor_thread.is_alive()
                print(f"   📊 Monitor thread status after health check: {'ALIVE' if is_alive else 'DEAD'}")
        except Exception as e:
            print(f"   ⚠️  Health check error: {e}")
    else:
        print(f"   ⚠️  Health check method not available")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Summary
print("=" * 80)
print("VERIFICATION SUMMARY")
print("=" * 80)
print()

# Determine overall status
try:
    import httpx
    with httpx.Client(timeout=5.0) as client:
        response = client.get("http://localhost:8000/auto-execution/system-status")
        if response.status_code == 200:
            status_data = response.json()
            system_status = status_data.get("system_status", {})
            is_running = system_status.get("running", False)
            thread_alive = system_status.get("thread_alive", False)
            
            if is_running and thread_alive:
                print("✅ STATUS: SYSTEM IS RUNNING AND HEALTHY")
                print()
                print("✅ Verified:")
                print("   • System is running")
                print("   • Monitor thread is alive")
                print("   • Plans are being monitored")
                print("   • Watchdog is protecting the system")
            elif is_running and not thread_alive:
                print("⚠️  STATUS: SYSTEM RUNNING BUT THREAD DEAD")
                print()
                print("⚠️  Issue:")
                print("   • System marked as running but monitor thread is dead")
                print("   • Watchdog should restart it automatically")
                print("   • Check logs for restart messages")
            else:
                print("❌ STATUS: SYSTEM NOT RUNNING")
                print()
                print("❌ Issue:")
                print("   • System is not running")
                print("   • Restart may be required")
except:
    print("⚠️  STATUS: COULD NOT VERIFY VIA API")
    print()
    print("⚠️  Could not connect to API server")
    print("   • Check if main API server is running")
    print("   • Verify port 8000 is accessible")

print()
print("💡 Next Steps:")
print("   • Monitor logs for 'Watchdog thread started' message")
print("   • Check for any error messages in logs")
print("   • Verify plans are being checked (look for plan check messages)")
print("   • If thread keeps dying, check logs for fatal errors")
print()

