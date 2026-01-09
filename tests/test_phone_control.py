"""
Test script for Phone Control System
Tests all tools locally before trying via phone
"""

import asyncio
import sys
import codecs

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from desktop_agent import registry, tool_ping

async def test_ping():
    """Test 1: Ping tool"""
    print("\n" + "="*70)
    print("TEST 1: Ping Tool")
    print("="*70)
    try:
        result = await registry.execute("ping", {"message": "Test from script"})
        print(f"✅ PASS: {result['summary']}")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

async def test_monitor_status():
    """Test 2: Monitor status"""
    print("\n" + "="*70)
    print("TEST 2: Monitor Status")
    print("="*70)
    try:
        result = await registry.execute("moneybot.monitor_status", {})
        print(f"✅ PASS: Got status")
        print(result['summary'][:200] + "..." if len(result['summary']) > 200 else result['summary'])
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

async def test_macro_context():
    """Test 3: Macro context"""
    print("\n" + "="*70)
    print("TEST 3: Macro Context")
    print("="*70)
    try:
        result = await registry.execute("moneybot.macro_context", {"symbol": "XAUUSD"})
        print(f"✅ PASS: Got macro context")
        print(result['summary'])
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

async def test_analyse_symbol():
    """Test 4: Analyse symbol"""
    print("\n" + "="*70)
    print("TEST 4: Analyse Symbol (BTCUSD)")
    print("="*70)
    print("⏳ This may take 5-10 seconds (fetching MT5 data + Advanced features)...")
    try:
        result = await registry.execute("moneybot.analyse_symbol", {
            "symbol": "BTCUSD",
            "detail_level": "standard"
        })
        print(f"✅ PASS: Got analysis")
        print(result['summary'])
        
        # Check if we got actual data
        data = result.get('data', {})
        if data.get('direction') and data.get('confidence'):
            print(f"\n📊 Direction: {data['direction']}")
            print(f"📊 Confidence: {data['confidence']}%")
            print(f"📊 Entry: {data.get('entry', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("\n" + "="*70)
    print("🧪 PHONE CONTROL SYSTEM - LOCAL TEST SUITE")
    print("="*70)
    print("\nℹ️  This tests the desktop agent tools locally (no phone/hub needed)")
    print("ℹ️  Make sure MT5 is running and logged in!")
    print("\n" + "="*70)
    
    results = []
    
    # Test 1: Ping (should always work)
    results.append(("Ping", await test_ping()))
    
    # Test 2: Monitor Status (requires MT5)
    results.append(("Monitor Status", await test_monitor_status()))
    
    # Test 3: Macro Context (requires MT5 with DXY/US10Y/VIX)
    results.append(("Macro Context", await test_macro_context()))
    
    # Test 4: Analyse Symbol (full integration test)
    results.append(("Analyse Symbol", await test_analyse_symbol()))
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST RESULTS SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n{'='*70}")
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Your desktop agent is working correctly!")
        print("\n📱 Next Steps:")
        print("   1. Start ngrok: ngrok http 8001")
        print("   2. Start desktop agent: python desktop_agent.py")
        print("   3. Configure your phone's Custom GPT")
        print("   4. Test from phone!")
    else:
        print("\n⚠️  Some tests failed. Common issues:")
        print("   - MT5 not running or not logged in")
        print("   - Symbols not available (DXY, US10Y, VIX, BTCUSD)")
        print("   - Network/connection issues")
    
    print(f"{'='*70}\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Tests interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

