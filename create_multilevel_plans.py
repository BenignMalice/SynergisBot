"""
Create multi-level auto-execution plans for BTCUSD and XAUUSD
This creates plans at different price levels to capture moves across a wider range
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge

async def create_multilevel_plans():
    """Create multi-level plans for both symbols"""
    bridge = get_bridge()
    
    # Multi-level plans for BTCUSD
    btc_plans = [
        # BUY Levels (Support Zones)
        {
            "plan_type": "auto_trade",
            "symbol": "BTCUSDc",
            "direction": "BUY",
            "entry": 86500.0,  # Strong support level 1
            "stop_loss": 86300.0,
            "take_profit": 87000.0,
            "volume": 0.01,
            "conditions": {
                "price_near": 86500.0,
                "tolerance": 200.0,
                "confluence_min": 65,
                "order_block": True,
                "order_block_type": "bull"
            },
            "expires_hours": 24,
            "notes": "Multi-level BUY Level 1 - Strong Support Zone"
        },
        {
            "plan_type": "auto_trade",
            "symbol": "BTCUSDc",
            "direction": "BUY",
            "entry": 87000.0,  # Support level 2
            "stop_loss": 86800.0,
            "take_profit": 87500.0,
            "volume": 0.01,
            "conditions": {
                "price_near": 87000.0,
                "tolerance": 200.0,
                "confluence_min": 60,
                "choch_bull": True,
                "timeframe": "M15"
            },
            "expires_hours": 24,
            "notes": "Multi-level BUY Level 2 - CHOCH Support"
        },
        {
            "plan_type": "auto_trade",
            "symbol": "BTCUSDc",
            "direction": "BUY",
            "entry": 87500.0,  # Support level 3
            "stop_loss": 87300.0,
            "take_profit": 88000.0,
            "volume": 0.01,
            "conditions": {
                "price_near": 87500.0,
                "tolerance": 200.0,
                "confluence_min": 55,
                "liquidity_sweep": True
            },
            "expires_hours": 24,
            "notes": "Multi-level BUY Level 3 - Liquidity Sweep Zone"
        },
        # SELL Levels (Resistance Zones)
        {
            "plan_type": "order_block",
            "symbol": "BTCUSDc",
            "direction": "SELL",
            "entry": 88000.0,  # Resistance level 1
            "stop_loss": 88200.0,
            "take_profit": 87500.0,
            "volume": 0.01,
            "order_block_type": "bear",
            "min_validation_score": 60,
            "expires_hours": 24,
            "notes": "Multi-level SELL Level 1 - Order Block Resistance"
        },
        {
            "plan_type": "auto_trade",
            "symbol": "BTCUSDc",
            "direction": "SELL",
            "entry": 88200.0,  # Resistance level 2
            "stop_loss": 88400.0,
            "take_profit": 87600.0,
            "volume": 0.01,
            "conditions": {
                "price_near": 88200.0,
                "tolerance": 200.0,
                "confluence_min": 60,
                "bos_bear": True,
                "timeframe": "M15"
            },
            "expires_hours": 24,
            "notes": "Multi-level SELL Level 2 - BOS Bear Resistance"
        },
        {
            "plan_type": "auto_trade",
            "symbol": "BTCUSDc",
            "direction": "SELL",
            "entry": 88500.0,  # Resistance level 3
            "stop_loss": 88700.0,
            "take_profit": 87800.0,
            "volume": 0.01,
            "conditions": {
                "price_near": 88500.0,
                "tolerance": 200.0,
                "confluence_min": 55,
                "choch_bear": True,
                "timeframe": "M15"
            },
            "expires_hours": 24,
            "notes": "Multi-level SELL Level 3 - CHOCH Bear Resistance"
        }
    ]
    
    # Multi-level plans for XAUUSD
    xau_plans = [
        # BUY Levels (Support Zones)
        {
            "plan_type": "auto_trade",
            "symbol": "XAUUSDc",
            "direction": "BUY",
            "entry": 4465.0,  # Strong support level 1
            "stop_loss": 4460.0,
            "take_profit": 4480.0,
            "volume": 0.01,
            "conditions": {
                "price_near": 4465.0,
                "tolerance": 5.0,
                "confluence_min": 65,
                "order_block": True,
                "order_block_type": "bull"
            },
            "expires_hours": 24,
            "notes": "Multi-level BUY Level 1 - Strong Support Zone"
        },
        {
            "plan_type": "order_block",
            "symbol": "XAUUSDc",
            "direction": "BUY",
            "entry": 4470.0,  # Support level 2
            "stop_loss": 4465.0,
            "take_profit": 4485.0,
            "volume": 0.01,
            "order_block_type": "bull",
            "min_validation_score": 60,
            "expires_hours": 24,
            "notes": "Multi-level BUY Level 2 - Order Block Support"
        },
        {
            "plan_type": "auto_trade",
            "symbol": "XAUUSDc",
            "direction": "BUY",
            "entry": 4475.0,  # Support level 3
            "stop_loss": 4470.0,
            "take_profit": 4490.0,
            "volume": 0.01,
            "conditions": {
                "price_near": 4475.0,
                "tolerance": 5.0,
                "confluence_min": 55,
                "choch_bull": True,
                "timeframe": "M15"
            },
            "expires_hours": 24,
            "notes": "Multi-level BUY Level 3 - CHOCH Support"
        },
        # SELL Levels (Resistance Zones)
        {
            "plan_type": "auto_trade",
            "symbol": "XAUUSDc",
            "direction": "SELL",
            "entry": 4485.0,  # Resistance level 1
            "stop_loss": 4490.0,
            "take_profit": 4475.0,
            "volume": 0.01,
            "conditions": {
                "price_near": 4485.0,
                "tolerance": 5.0,
                "confluence_min": 60,
                "bos_bear": True,
                "timeframe": "M15"
            },
            "expires_hours": 24,
            "notes": "Multi-level SELL Level 1 - BOS Bear Resistance"
        },
        {
            "plan_type": "order_block",
            "symbol": "XAUUSDc",
            "direction": "SELL",
            "entry": 4490.0,  # Resistance level 2
            "stop_loss": 4495.0,
            "take_profit": 4475.0,
            "volume": 0.01,
            "order_block_type": "bear",
            "min_validation_score": 60,
            "expires_hours": 24,
            "notes": "Multi-level SELL Level 2 - Order Block Resistance"
        },
        {
            "plan_type": "auto_trade",
            "symbol": "XAUUSDc",
            "direction": "SELL",
            "entry": 4495.0,  # Resistance level 3
            "stop_loss": 4500.0,
            "take_profit": 4480.0,
            "volume": 0.01,
            "conditions": {
                "price_near": 4495.0,
                "tolerance": 5.0,
                "confluence_min": 55,
                "choch_bear": True,
                "timeframe": "M15"
            },
            "expires_hours": 24,
            "notes": "Multi-level SELL Level 3 - CHOCH Bear Resistance"
        }
    ]
    
    print("=" * 70)
    print("Creating Multi-Level Plans for BTCUSD and XAUUSD")
    print("=" * 70)
    
    # Create BTCUSD multi-level plans
    print("\n📊 Creating BTCUSD Multi-Level Plans (6 plans)...")
    btc_result = await bridge.registry.execute(
        "moneybot.create_multiple_auto_plans",
        {"plans": btc_plans}
    )
    
    print("\n=== BTCUSD Multi-Level Plans Result ===")
    print(json.dumps(btc_result, indent=2, default=str))
    
    # Create XAUUSD multi-level plans
    print("\n📊 Creating XAUUSD Multi-Level Plans (6 plans)...")
    xau_result = await bridge.registry.execute(
        "moneybot.create_multiple_auto_plans",
        {"plans": xau_plans}
    )
    
    print("\n=== XAUUSD Multi-Level Plans Result ===")
    print(json.dumps(xau_result, indent=2, default=str))
    
    # Summary
    print("\n" + "=" * 70)
    print("MULTI-LEVEL PLANS SUMMARY")
    print("=" * 70)
    
    btc_data = btc_result.get("data", {})
    xau_data = xau_result.get("data", {})
    
    btc_success = btc_data.get("successful", 0)
    btc_failed = btc_data.get("failed", 0)
    xau_success = xau_data.get("successful", 0)
    xau_failed = xau_data.get("failed", 0)
    
    print(f"\n✅ BTCUSD: {btc_success} plans created, {btc_failed} failed")
    print(f"✅ XAUUSD: {xau_success} plans created, {xau_failed} failed")
    print(f"\n📈 Total: {btc_success + xau_success} multi-level plans active")
    
    if btc_data.get("results"):
        print("\n📋 BTCUSD Plan IDs:")
        for i, res in enumerate(btc_data["results"], 1):
            if res.get("status") == "success":
                plan_id = res.get("plan_id", "N/A")
                notes = btc_plans[i-1].get("notes", "")
                print(f"   {i}. {plan_id} - {notes}")
    
    if xau_data.get("results"):
        print("\n📋 XAUUSD Plan IDs:")
        for i, res in enumerate(xau_data["results"], 1):
            if res.get("status") == "success":
                plan_id = res.get("plan_id", "N/A")
                notes = xau_plans[i-1].get("notes", "")
                print(f"   {i}. {plan_id} - {notes}")

if __name__ == "__main__":
    asyncio.run(create_multilevel_plans())
