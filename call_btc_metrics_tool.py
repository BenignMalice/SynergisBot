"""Call BTC order flow metrics tool directly"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def call_tool():
    """Call the BTC order flow metrics tool"""
    try:
        from desktop_agent import registry
        
        print("=" * 70)
        print("Calling moneybot.btc_order_flow_metrics")
        print("=" * 70)
        print()
        
        result = await registry.execute(
            "moneybot.btc_order_flow_metrics",
            {"symbol": "BTCUSDT"}
        )
        
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
                    for i, zone in enumerate(zones, 1):
                        print(f"   {i}. Price: ${zone.get('price_level', 0):,.2f}")
                        print(f"      Side: {zone.get('side', 'N/A')}")
                        print(f"      Strength: {zone.get('strength', 0):.2%}")
                        print(f"      Volume Absorbed: ${zone.get('volume_absorbed', 0):,.0f}")
                        print(f"      Net Volume: {zone.get('net_volume', 0):+,.0f}")
                        print(f"      Imbalance: {zone.get('imbalance_ratio', 1.0):.2f}x ({zone.get('imbalance_pct', 0):.1f}%)")
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
                print(f"Timestamp: {data.get('timestamp', 0)}")
                
            else:
                print(f"Status: {status}")
                print(f"Message: {data.get('message', data.get('error', 'No message'))}")
        
        print()
        print("=" * 70)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(call_tool())

