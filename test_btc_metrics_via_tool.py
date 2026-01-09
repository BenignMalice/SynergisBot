"""
Test BTC Order Flow Metrics via Desktop Agent Tool

Tests the actual tool registration and execution.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_via_tool():
    """Test via desktop agent tool"""
    print("=" * 70)
    print("BTC Order Flow Metrics - Tool Test")
    print("=" * 70)
    print()
    
    try:
        # Import desktop agent registry
        print("[1/3] Importing desktop agent...")
        from desktop_agent import registry
        
        # Check if tool is registered
        if "moneybot.btc_order_flow_metrics" not in registry.tools:
            print("   [ERROR] Tool 'moneybot.btc_order_flow_metrics' not found in registry")
            print(f"   Available tools: {sorted(registry.tools.keys())[:10]}...")
            return False
        
        print("   [OK] Tool 'moneybot.btc_order_flow_metrics' is registered")
        print()
        
        # Check if OrderFlowService is available
        print("[2/3] Checking OrderFlowService status...")
        # Try to access order_flow_service - it may be stored differently
        order_flow_service = None
        if hasattr(registry, 'order_flow_service'):
            order_flow_service = registry.order_flow_service
        else:
            # Try to get from chatgpt_bot module if available
            try:
                import chatgpt_bot
                if hasattr(chatgpt_bot, 'order_flow_service'):
                    order_flow_service = chatgpt_bot.order_flow_service
            except:
                pass
        
        if not order_flow_service:
            print("   [WARNING] OrderFlowService not found")
            print("   [INFO] OrderFlowService should be initialized in agent_main()")
            print("   [INFO] This is normal if desktop agent hasn't fully started")
            print("   [INFO] Tool will handle this gracefully")
        elif not order_flow_service.running:
            print("   [WARNING] OrderFlowService exists but is not running")
            print("   [INFO] Service needs to be started: await order_flow_service.start(['btcusdt'])")
        else:
            print("   [OK] OrderFlowService is running")
            print(f"   Symbols: {order_flow_service.symbols}")
        
        print()
        
        # Test tool execution
        print("[3/3] Testing tool execution...")
        print("   Calling moneybot.btc_order_flow_metrics...")
        
        result = await registry.execute(
            "moneybot.btc_order_flow_metrics",
            {"symbol": "BTCUSDT", "window_seconds": 30}
        )
        
        print()
        print("   Tool Response:")
        print("   " + "=" * 60)
        
        if result.get("summary"):
            print(f"   Summary: {result['summary']}")
        
        if result.get("data"):
            data = result["data"]
            status = data.get("status", "unknown")
            print(f"   Status: {status}")
            
            if status == "success":
                print()
                print("   [SUCCESS] Metrics calculated successfully!")
                print()
                
                # Delta Volume
                delta = data.get("delta_volume", {})
                if delta:
                    print(f"   Delta Volume:")
                    print(f"      Buy: {delta.get('buy_volume', 0):,.2f}")
                    print(f"      Sell: {delta.get('sell_volume', 0):,.2f}")
                    print(f"      Net: {delta.get('net_delta', 0):+,.2f} ({delta.get('dominant_side', 'N/A')})")
                
                # CVD
                cvd = data.get("cvd", {})
                if cvd:
                    print(f"   CVD:")
                    print(f"      Current: {cvd.get('current', 0):+,.2f}")
                    print(f"      Slope: {cvd.get('slope', 0):+,.2f} per bar")
                    print(f"      Bars: {cvd.get('bar_count', 0)}")
                
                # CVD Divergence
                divergence = data.get("cvd_divergence", {})
                if divergence:
                    strength = divergence.get("strength", 0)
                    if strength > 0:
                        print(f"   CVD Divergence:")
                        print(f"      Type: {divergence.get('type', 'None')}")
                        print(f"      Strength: {strength:.2%}")
                
                # Absorption Zones
                zones = data.get("absorption_zones", [])
                if zones:
                    print(f"   Absorption Zones: {len(zones)} detected")
                    for i, zone in enumerate(zones[:3], 1):
                        print(f"      {i}. ${zone.get('price_level', 0):,.2f} - {zone.get('side', 'N/A')} "
                              f"(Strength: {zone.get('strength', 0):.2%})")
                else:
                    print(f"   Absorption Zones: None detected")
                
                # Pressure
                pressure = data.get("buy_sell_pressure", {})
                if pressure:
                    print(f"   Buy/Sell Pressure:")
                    print(f"      Ratio: {pressure.get('ratio', 1.0):.2f}x")
                    print(f"      Dominant: {pressure.get('dominant_side', 'N/A')}")
                
            elif status == "error":
                error_msg = data.get("message", data.get("error", "Unknown error"))
                print(f"   [ERROR] {error_msg}")
                print()
                print("   Possible reasons:")
                print("      - OrderFlowService not running")
                print("      - Insufficient trade data (wait 30-60 seconds)")
                print("      - Binance WebSocket connection issue")
            else:
                print(f"   [INFO] Status: {status}")
                print(f"   Message: {data.get('message', 'No message')}")
        
        print("   " + "=" * 60)
        print()
        print("=" * 70)
        print("Test Complete!")
        print("=" * 70)
        
        return True
        
    except ImportError as e:
        print(f"   [ERROR] Import failed: {e}")
        print("   [INFO] Make sure desktop_agent.py is importable")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"   [ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print()
    success = asyncio.run(test_via_tool())
    sys.exit(0 if success else 1)

