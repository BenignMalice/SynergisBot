"""
Check if registry services are accessible from bridge context
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def check_registry():
    """Check registry access"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("CHECKING REGISTRY ACCESS")
    print("=" * 70)
    print()
    
    # Try to access registry directly
    try:
        from desktop_agent import registry
        
        print("[1/3] Direct Registry Access:")
        print(f"   Has binance_service: {hasattr(registry, 'binance_service')}")
        if hasattr(registry, 'binance_service'):
            binance = registry.binance_service
            print(f"   binance_service value: {binance}")
            if binance:
                print(f"   binance_service.running: {hasattr(binance, 'running') and binance.running}")
        
        print(f"   Has order_flow_service: {hasattr(registry, 'order_flow_service')}")
        if hasattr(registry, 'order_flow_service'):
            ofs = registry.order_flow_service
            print(f"   order_flow_service value: {ofs}")
            if ofs:
                print(f"   order_flow_service.running: {hasattr(ofs, 'running') and ofs.running}")
        
    except Exception as e:
        print(f"   [ERROR] Failed to access registry: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Check via bridge tools
    print("[2/3] Bridge Tool Access:")
    try:
        result = await bridge.registry.execute("moneybot.binance_feed_status", {})
        print(f"   Binance status: {result.get('summary', 'No summary')}")
    except Exception as e:
        print(f"   [ERROR] Failed: {e}")
    
    try:
        result = await bridge.registry.execute("moneybot.order_flow_status", {"symbol": "BTCUSDc"})
        print(f"   Order Flow status: {result.get('summary', 'No summary')}")
    except Exception as e:
        print(f"   [ERROR] Failed: {e}")
    
    print()
    
    # Check via chatgpt_bot module
    print("[3/3] chatgpt_bot Module Access:")
    try:
        import chatgpt_bot
        print(f"   Has order_flow_service: {hasattr(chatgpt_bot, 'order_flow_service')}")
        if hasattr(chatgpt_bot, 'order_flow_service'):
            ofs = chatgpt_bot.order_flow_service
            print(f"   order_flow_service value: {ofs}")
            if ofs:
                print(f"   order_flow_service.running: {hasattr(ofs, 'running') and ofs.running}")
        
        print(f"   Has binance_service: {hasattr(chatgpt_bot, 'binance_service')}")
        if hasattr(chatgpt_bot, 'binance_service'):
            binance = chatgpt_bot.binance_service
            print(f"   binance_service value: {binance}")
            if binance:
                print(f"   binance_service.running: {hasattr(binance, 'running') and binance.running}")
    except Exception as e:
        print(f"   [ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(check_registry())
