"""
Check Phone Hub Connection Status
Diagnoses why phone hub connection is failing
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
print("PHONE HUB CONNECTION DIAGNOSTIC")
print("=" * 80)
print()

# Check 1: Phone Hub Server Status
print("1. Checking Phone Hub Server Status...")
try:
    import httpx
    
    try:
        response = httpx.get("http://localhost:8001/", timeout=2.0)
        if response.status_code == 200:
            print("   ✅ Phone hub server is running")
            print(f"   📊 Response: {response.text[:100]}")
        else:
            print(f"   ⚠️  Phone hub returned status {response.status_code}")
    except httpx.ConnectError:
        print("   ❌ Phone hub server is NOT running")
        print("   💡 To start: python -m uvicorn hub.command_hub:app --host 0.0.0.0 --port 8001")
    except Exception as e:
        print(f"   ❌ Error checking phone hub: {e}")
        
except Exception as e:
    print(f"   ❌ Could not check phone hub: {e}")

print()

# Check 2: AGENT_SECRET Configuration
print("2. Checking AGENT_SECRET Configuration...")
try:
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check desktop_agent.py
    desktop_agent_secret = os.getenv("AGENT_SECRET", "phone_control_bearer_token_2025_v1_secure")
    print(f"   📊 desktop_agent.py AGENT_SECRET: {desktop_agent_secret[:20]}...")
    
    # Check hub/command_hub.py (read from .env or default)
    hub_secret = os.getenv("AGENT_SECRET", "phone_control_bearer_token_2025_v1_secure")
    print(f"   📊 hub/command_hub.py AGENT_SECRET: {hub_secret[:20]}...")
    
    if desktop_agent_secret == hub_secret:
        print("   ✅ AGENT_SECRET matches!")
    else:
        print("   ❌ AGENT_SECRET MISMATCH!")
        print("   💡 Fix: Set AGENT_SECRET in .env file or ensure both use same default")
        
except Exception as e:
    print(f"   ❌ Error checking secrets: {e}")

print()

# Check 3: WebSocket Endpoint
print("3. Checking WebSocket Endpoint...")
try:
    import httpx
    
    # Try to connect to WebSocket endpoint (will fail but shows if server is there)
    try:
        # WebSocket upgrade request
        response = httpx.get("http://localhost:8001/agent/connect", timeout=2.0)
        print(f"   📊 WebSocket endpoint response: {response.status_code}")
        if response.status_code == 426:
            print("   ✅ WebSocket endpoint exists (426 = Upgrade Required, expected)")
        elif response.status_code == 403:
            print("   ❌ WebSocket endpoint rejected connection (403 Forbidden)")
            print("   💡 This suggests authentication issue or server configuration")
        else:
            print(f"   ⚠️  Unexpected status: {response.status_code}")
    except httpx.ConnectError:
        print("   ❌ Cannot connect to WebSocket endpoint (server not running)")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        
except Exception as e:
    print(f"   ❌ Could not check WebSocket endpoint: {e}")

print()

# Check 4: Environment Variables
print("4. Checking Environment Variables...")
try:
    phone_hub_enabled = os.getenv("PHONE_HUB_ENABLED", "false")
    phone_hub_url = os.getenv("PHONE_HUB_URL", "ws://localhost:8001/agent/connect")
    
    print(f"   📊 PHONE_HUB_ENABLED: {phone_hub_enabled}")
    print(f"   📊 PHONE_HUB_URL: {phone_hub_url}")
    
    if phone_hub_enabled.lower() == "false":
        print("   ℹ️  Phone hub is disabled (set PHONE_HUB_ENABLED=true to enable)")
    else:
        print("   ✅ Phone hub is enabled")
        
except Exception as e:
    print(f"   ❌ Error checking environment: {e}")

print()

# Check 5: Code Configuration
print("5. Checking Code Configuration...")
try:
    # Read desktop_agent.py to check HUB_URL and AGENT_SECRET
    desktop_agent_path = os.path.join(os.path.dirname(__file__), "desktop_agent.py")
    if os.path.exists(desktop_agent_path):
        with open(desktop_agent_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'HUB_URL' in content and 'AGENT_SECRET' in content:
            print("   ✅ HUB_URL and AGENT_SECRET found in desktop_agent.py")
            
            # Extract values
            import re
            hub_url_match = re.search(r'HUB_URL\s*=\s*os\.getenv\([^,]+,\s*"([^"]+)"', content)
            agent_secret_match = re.search(r'AGENT_SECRET\s*=\s*os\.getenv\([^,]+,\s*"([^"]+)"', content)
            
            if hub_url_match:
                print(f"   📊 HUB_URL default: {hub_url_match.group(1)}")
            if agent_secret_match:
                print(f"   📊 AGENT_SECRET default: {agent_secret_match.group(1)[:20]}...")
        else:
            print("   ⚠️  HUB_URL or AGENT_SECRET not found")
    else:
        print("   ⚠️  Could not find desktop_agent.py")
        
except Exception as e:
    print(f"   ❌ Error checking code: {e}")

print()

# Check 6: Hub Configuration
print("6. Checking Hub Configuration...")
try:
    hub_path = os.path.join(os.path.dirname(__file__), "hub", "command_hub.py")
    if os.path.exists(hub_path):
        with open(hub_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'AGENT_SECRET' in content:
            print("   ✅ AGENT_SECRET found in hub/command_hub.py")
            
            # Extract value
            import re
            agent_secret_match = re.search(r'AGENT_SECRET\s*=\s*os\.getenv\([^,]+,\s*"([^"]+)"', content)
            
            if agent_secret_match:
                print(f"   📊 AGENT_SECRET default: {agent_secret_match.group(1)[:20]}...")
        else:
            print("   ⚠️  AGENT_SECRET not found in hub")
    else:
        print("   ⚠️  Could not find hub/command_hub.py")
        
except Exception as e:
    print(f"   ❌ Error checking hub: {e}")

print()
print("=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
print()
print("💡 TROUBLESHOOTING:")
print("   1. If server not running: Start with 'python -m uvicorn hub.command_hub:app --host 0.0.0.0 --port 8001'")
print("   2. If AGENT_SECRET mismatch: Set AGENT_SECRET in .env file or ensure both use same default")
print("   3. If HTTP 403: Check that phone hub server is running and AGENT_SECRET matches")
print("   4. To disable phone hub: Set PHONE_HUB_ENABLED=false in environment")
print()

