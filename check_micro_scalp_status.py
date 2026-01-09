"""
Check Micro-Scalp Monitor Status
"""
import sys
import json

# Configure encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def check_config():
    """Check micro-scalp configuration"""
    print("=" * 80)
    print("MICRO-SCALP CONFIGURATION CHECK")
    print("=" * 80)
    print()
    
    try:
        with open('config/micro_scalp_automation.json', 'r') as f:
            config = json.load(f)
        
        print("Configuration File: config/micro_scalp_automation.json")
        print()
        print(f"  enabled: {config.get('enabled', 'not set')}")
        print(f"  symbols: {config.get('symbols', [])}")
        print(f"  check_interval_seconds: {config.get('check_interval_seconds', 'not set')}")
        print(f"  max_positions_per_symbol: {config.get('max_positions_per_symbol', 'not set')}")
        print()
        
        if config.get('enabled', False):
            print("✅ Micro-Scalp Monitor is ENABLED in config")
        else:
            print("❌ Micro-Scalp Monitor is DISABLED in config")
            print("   → Set 'enabled': true to activate")
        
        return config.get('enabled', False)
        
    except FileNotFoundError:
        print("❌ Config file not found: config/micro_scalp_automation.json")
        return False
    except Exception as e:
        print(f"❌ Error reading config: {e}")
        return False

def check_api_status():
    """Check micro-scalp status via API"""
    print("=" * 80)
    print("MICRO-SCALP API STATUS CHECK")
    print("=" * 80)
    print()
    
    try:
        import httpx
        
        base_url = "http://localhost:8010"
        
        # Try to get status
        print("Checking /micro-scalp/status endpoint...")
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{base_url}/micro-scalp/status")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ Status endpoint accessible")
                    print()
                    print("Status Details:")
                    status = data.get('status', {})
                    print(f"   Monitoring: {status.get('monitoring', 'N/A')}")
                    print(f"   Enabled: {status.get('enabled', 'N/A')}")
                    print(f"   Thread alive: {status.get('thread_alive', 'N/A')}")
                    
                    stats = status.get('stats', {})
                    print()
                    print("Statistics:")
                    print(f"   Total checks: {stats.get('total_checks', 0)}")
                    print(f"   Conditions met: {stats.get('conditions_met', 0)}")
                    print(f"   Executions: {stats.get('executions', 0)}")
                    print()
                    
                    skipped = stats.get('skipped', {})
                    print("Skipped:")
                    print(f"   Rate limit: {skipped.get('rate_limit', 0)}")
                    print(f"   Position limit: {skipped.get('position_limit', 0)}")
                    print(f"   Session: {skipped.get('session', 0)}")
                    print(f"   News: {skipped.get('news', 0)}")
                    
                    return True
                else:
                    print(f"   ❌ Status endpoint returned: {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
                    return False
        except Exception as e:
            print(f"   ❌ Error accessing status endpoint: {e}")
            return False
            
    except ImportError:
        print("   ❌ httpx not available")
        return False

def check_logs_hints():
    """Provide hints for checking logs"""
    print("=" * 80)
    print("HOW TO VERIFY MICRO-SCALP IS RUNNING")
    print("=" * 80)
    print()
    print("1. Check startup logs for:")
    print("   ✅ Micro-Scalp Monitor started")
    print("   → Continuous monitoring for micro-scalp setups")
    print()
    print("2. Check for heartbeat logs (every 60 seconds):")
    print("   Micro-Scalp Monitor heartbeat: {'total_checks': X, ...}")
    print()
    print("3. Check for condition check logs (every 5 seconds):")
    print("   [BTCUSDc] ✅ Check #X | Strategy: ... | Regime: ...")
    print()
    print("4. Check for errors:")
    print("   ⚠️ Micro-Scalp Monitor initialization failed")
    print("   ⚠️ No M1 candles available")
    print()
    print("5. Visit dashboard:")
    print("   http://localhost:8010/micro-scalp/view")
    print()

def main():
    """Run all checks"""
    print()
    print("=" * 80)
    print("MICRO-SCALP MONITOR STATUS CHECK")
    print("=" * 80)
    print()
    
    # Check config
    config_enabled = check_config()
    print()
    
    # Check API status
    api_accessible = check_api_status()
    print()
    
    # Provide hints
    check_logs_hints()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    if config_enabled:
        print("✅ Config: ENABLED")
    else:
        print("❌ Config: DISABLED - Set 'enabled': true in config file")
    
    if api_accessible:
        print("✅ API: Accessible")
    else:
        print("⚠️ API: Not accessible - Check if server is running on port 8010")
    
    print()

if __name__ == "__main__":
    main()

