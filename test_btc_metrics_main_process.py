"""Test BTC Order Flow Metrics from main process context

This script should be run when chatgpt_bot.py is running,
or can be imported and called from within the main process.
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_btc_metrics():
    """Test BTC order flow metrics tool"""
    try:
        from desktop_agent import registry
        
        print("=" * 70)
        print("BTC Order Flow Metrics - Main Process Test")
        print("=" * 70)
        print()
        
        # Step 1: Check Binance service status
        print("[1/3] Checking Binance Service Status...")
        try:
            binance_status = await registry.execute(
                "moneybot.binance_feed_status",
                {}
            )
            print(f"   Result: {binance_status.get('summary', 'No summary')}")
            if binance_status.get('data', {}).get('running'):
                print("   [OK] Binance service is running")
            else:
                print("   [WARNING] Binance service may not be running")
        except Exception as e:
            print(f"   [ERROR] Failed to check Binance status: {e}")
        print()
        
        # Step 2: Check OrderFlowService status
        print("[2/3] Checking OrderFlowService Status...")
        try:
            order_flow_status = await registry.execute(
                "moneybot.order_flow_status",
                {}
            )
            print(f"   Result: {order_flow_status.get('summary', 'No summary')}")
            if order_flow_status.get('data', {}).get('running'):
                print("   [OK] OrderFlowService is running")
            else:
                print("   [WARNING] OrderFlowService may not be running")
        except Exception as e:
            print(f"   [ERROR] Failed to check OrderFlow status: {e}")
        print()
        
        # Step 3: Call BTC Order Flow Metrics tool
        print("[3/3] Calling moneybot.btc_order_flow_metrics...")
        print()
        
        result = await registry.execute(
            "moneybot.btc_order_flow_metrics",
            {"symbol": "BTCUSDT"}
        )
        
        print("=" * 70)
        print("Tool Response:")
        print("=" * 70)
        print()
        
        if result.get("summary"):
            print(result["summary"])
            print()
        
        if result.get("data"):
            data = result["data"]
            status = data.get("status", "unknown")
            
            if status == "success":
                print("✅ SUCCESS - Metrics calculated!")
                print()
                
                # Delta Volume
                delta = data.get("delta_volume", {})
                if delta:
                    print("💰 Delta Volume:")
                    print(f"   Buy Volume: {delta.get('buy_volume', 0):,.2f}")
                    print(f"   Sell Volume: {delta.get('sell_volume', 0):,.2f}")
                    print(f"   Net Delta: {delta.get('net_delta', 0):+,.2f}")
                    print(f"   Dominant Side: {delta.get('dominant_side', 'N/A')}")
                    print()
                
                # CVD
                cvd = data.get("cvd", {})
                if cvd:
                    print("📈 CVD (Cumulative Volume Delta):")
                    print(f"   Current: {cvd.get('current', 0):+,.2f}")
                    print(f"   Slope: {cvd.get('slope', 0):+,.2f} per bar")
                    print(f"   Bars Used: {cvd.get('bar_count', 0)}")
                    print()
                
                # CVD Divergence
                divergence = data.get("cvd_divergence", {})
                if divergence and divergence.get("strength", 0) > 0:
                    print("⚠️ CVD Divergence:")
                    print(f"   Type: {divergence.get('type', 'None')}")
                    print(f"   Strength: {divergence.get('strength', 0):.2%}")
                    print()
                
                # Absorption Zones
                zones = data.get("absorption_zones", [])
                if zones:
                    print(f"🎯 Absorption Zones: {len(zones)} detected")
                    for i, zone in enumerate(zones[:5], 1):  # Show first 5
                        print(f"   {i}. Price: ${zone.get('price_level', 0):,.2f}")
                        print(f"      Side: {zone.get('side', 'N/A')}")
                        print(f"      Strength: {zone.get('strength', 0):.2%}")
                        if zone.get('volume_absorbed'):
                            print(f"      Volume: ${zone.get('volume_absorbed', 0):,.0f}")
                        print()
                else:
                    print("🎯 Absorption Zones: None detected")
                    print()
                
                # Buy/Sell Pressure
                pressure = data.get("buy_sell_pressure", {})
                if pressure:
                    print("⚖️ Buy/Sell Pressure:")
                    print(f"   Ratio: {pressure.get('ratio', 1.0):.2f}x")
                    print(f"   Dominant Side: {pressure.get('dominant_side', 'N/A')}")
                    print()
                
                print(f"Window: {data.get('window_seconds', 30)} seconds")
                if data.get('timestamp'):
                    from datetime import datetime
                    ts = datetime.fromtimestamp(data['timestamp'])
                    print(f"Timestamp: {ts.strftime('%Y-%m-%d %H:%M:%S')}")
                
            elif status == "error":
                print(f"❌ ERROR")
                print(f"   Message: {data.get('message', data.get('error', 'No message'))}")
                print()
                print("   Possible reasons:")
                print("      - OrderFlowService not running")
                print("      - Insufficient trade data (wait 30-60 seconds)")
                print("      - Binance WebSocket connection issue")
            else:
                print(f"Status: {status}")
                print(f"Message: {data.get('message', 'No message')}")
        
        print()
        print("=" * 70)
        print("Test Complete!")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print()
    print("NOTE: This script should be run when chatgpt_bot.py is running,")
    print("      or imported and called from within the main process context.")
    print()
    success = asyncio.run(test_btc_metrics())
    sys.exit(0 if success else 1)

