"""
Create Test Phase III Auto-Execution Plans
Creates 1-2 test plans demonstrating Phase III advanced conditions
"""

import sys
import json
import codecs
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# API Configuration
API_BASE_URL = "http://localhost:8000"
API_ENDPOINT = f"{API_BASE_URL}/auto-execution/create-plan"

def create_plan(plan_data: dict) -> dict:
    """Create a trade plan via API"""
    print(f"\n{'='*70}")
    print(f"Creating Plan: {plan_data.get('notes', 'Test Plan')}")
    print(f"{'='*70}")
    
    try:
        # Prepare request
        data = json.dumps(plan_data).encode('utf-8')
        req = urllib.request.Request(
            API_ENDPOINT,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        # Make request
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if result.get('success'):
                print(f"✅ Plan created successfully!")
                print(f"   Plan ID: {result.get('plan_id')}")
                print(f"   Symbol: {plan_data['symbol']}")
                print(f"   Direction: {plan_data['direction']}")
                print(f"   Entry: {plan_data['entry_price']}")
                print(f"   SL: {plan_data['stop_loss']}")
                print(f"   TP: {plan_data['take_profit']}")
                print(f"   Conditions: {json.dumps(plan_data['conditions'], indent=2)}")
                return result
            else:
                print(f"❌ Plan creation failed: {result.get('error', 'Unknown error')}")
                return result
                
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"❌ HTTP Error {e.code}: {error_body}")
        try:
            error_data = json.loads(error_body)
            print(f"   Detail: {error_data.get('detail', 'No detail')}")
        except:
            pass
        return {'success': False, 'error': str(e)}
    except Exception as e:
        print(f"❌ Error creating plan: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

def main():
    """Create test Phase III plans"""
    print("="*70)
    print("Creating Test Phase III Auto-Execution Plans")
    print("="*70)
    print(f"API Endpoint: {API_ENDPOINT}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    # Check if API is available
    try:
        urllib.request.urlopen(f"{API_BASE_URL}/health", timeout=5)
        print("✅ API server is running")
    except Exception as e:
        print(f"⚠️  Warning: Could not connect to API server: {e}")
        print("   Make sure the API server is running on http://localhost:8000")
        response = input("Continue anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled")
            return
    
    results = []
    
    # Plan 1: Multi-Timeframe Confluence (M5-M15 CHOCH Sync)
    print("\n" + "="*70)
    print("PLAN 1: Multi-Timeframe Confluence - M5-M15 CHOCH Sync")
    print("="*70)
    plan1 = {
        "symbol": "XAUUSDc",
        "direction": "BUY",
        "entry_price": 4480.0,
        "stop_loss": 4475.0,
        "take_profit": 4495.0,
        "volume": 0.01,
        "expires_hours": 24,
        "conditions": {
            "choch_bull_m5": True,
            "choch_bull_m15": True,
            "price_near": 4480.0,
            "tolerance": 2.0,
            "min_confluence": 75,
            "structure_tf": "M15"
        },
        "notes": "Phase III Test Plan 1: M5-M15 CHOCH Sync - Multi-timeframe structure alignment for higher probability entry"
    }
    
    result1 = create_plan(plan1)
    results.append(("Plan 1: M5-M15 CHOCH Sync", result1))
    
    # Plan 2: Volatility Pattern Recognition (Consecutive Inside Bars + Fractal Expansion)
    print("\n" + "="*70)
    print("PLAN 2: Volatility Pattern Recognition - Inside Bar Breakout")
    print("="*70)
    plan2 = {
        "symbol": "XAUUSDc",
        "direction": "BUY",
        "entry_price": 4482.0,
        "stop_loss": 4478.0,
        "take_profit": 4492.0,
        "volume": 0.01,
        "expires_hours": 24,
        "conditions": {
            "consecutive_inside_bars": 3,
            "volatility_fractal_expansion": True,
            "bb_expansion": True,
            "price_above": 4480.0,
            "price_near": 4482.0,
            "tolerance": 2.0,
            "min_confluence": 70,
            "timeframe": "M15"
        },
        "notes": "Phase III Test Plan 2: Volatility Fractal Expansion - Detects compression (inside bars) followed by expansion breakout"
    }
    
    result2 = create_plan(plan2)
    results.append(("Plan 2: Volatility Fractal Expansion", result2))
    
    # Summary
    print("\n" + "="*70)
    print("Creation Summary")
    print("="*70)
    
    success_count = sum(1 for _, r in results if r.get('success'))
    total_count = len(results)
    
    for name, result in results:
        status = "✅ SUCCESS" if result.get('success') else "❌ FAILED"
        plan_id = result.get('plan_id', 'N/A')
        print(f"{name:50s} {status:15s} ID: {plan_id}")
    
    print(f"\nTotal: {success_count}/{total_count} plans created successfully")
    
    if success_count == total_count:
        print("\n✅ All test plans created successfully!")
        print("\nNext steps:")
        print("1. Check plan status: http://localhost:8000/auto-execution/view")
        print("2. Monitor plan execution in auto-execution system logs")
        print("3. Verify conditions are being checked correctly")
    else:
        print("\n⚠️  Some plans failed to create. Review errors above.")
    
    return success_count == total_count

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

