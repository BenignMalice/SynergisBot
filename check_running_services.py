"""
Check if Binance and Order Flow services are running via bridge
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def check_services():
    """Check service status via bridge"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("CHECKING SERVICE STATUS VIA BRIDGE")
    print("=" * 70)
    print()
    
    # Check Binance Service
    print("[1/2] Checking Binance Service...")
    try:
        result = await bridge.registry.execute("moneybot.binance_feed_status", {})
        summary = result.get("summary", "No summary")
        data = result.get("data", {})
        
        print(f"   Summary: {summary}")
        
        if data:
            status = data.get("status", "unknown")
            running = data.get("running", False)
            symbols = data.get("symbols", [])
            
            print(f"   Status: {status}")
            print(f"   Running: {running}")
            if symbols:
                print(f"   Symbols: {', '.join(symbols)}")
        
        if "running" in summary.lower() or "active" in summary.lower():
            print("   [OK] Binance service appears to be running")
        else:
            print("   [WARNING] Binance service may not be running")
            
    except Exception as e:
        print(f"   [ERROR] Failed to check Binance status: {e}")
    
    print()
    
    # Check Order Flow Service
    print("[2/2] Checking Order Flow Service...")
    try:
        result = await bridge.registry.execute("moneybot.order_flow_status", {})
        summary = result.get("summary", "No summary")
        data = result.get("data", {})
        
        print(f"   Summary: {summary}")
        
        if data:
            running = data.get("running", False)
            symbols = data.get("symbols", [])
            
            print(f"   Running: {running}")
            if symbols:
                print(f"   Symbols: {', '.join(symbols)}")
        
        if "running" in summary.lower() or "active" in summary.lower():
            print("   [OK] Order Flow service appears to be running")
        else:
            print("   [WARNING] Order Flow service may not be running")
            
    except Exception as e:
        print(f"   [ERROR] Failed to check Order Flow status: {e}")
    
    print()
    print("=" * 70)
    print()
    print("Note: If services show as not running, check:")
    print("  1. desktop_agent.log for initialization errors")
    print("  2. Ensure chatgpt_bot.py process is actually running")
    print("  3. Look for 'Binance Service initialized and started' in logs")
    print("  4. Look for 'Order Flow Service initialized' in logs")
    print()

if __name__ == "__main__":
    asyncio.run(check_services())
