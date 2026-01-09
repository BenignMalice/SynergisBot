"""
Quick test script to create a plan with all enhancements
"""
from chatgpt_auto_execution_integration import ChatGPTAutoExecution
from datetime import datetime

def main():
    print("=" * 60)
    print("Testing Enhanced Plan Creation")
    print("=" * 60)
    print()
    
    auto_exec = ChatGPTAutoExecution()
    
    # Create test plan with all recommended enhancements
    plan = auto_exec.create_trade_plan(
        symbol="BTCUSD",
        direction="BUY",
        entry_price=84000.0,
        stop_loss=83800.0,
        take_profit=84500.0,
        volume=0.01,
        conditions={
            "choch_bull": True,
            "timeframe": "M5",
            "price_near": 84000.0,
            "tolerance": 100.0,
            "m1_choch_bos_combo": True,  # ⭐ M1 validation
            "min_volatility": 0.5,        # ⭐ Volatility filter
            "bb_width_threshold": 2.5     # ⭐ BB width filter
        },
        expires_hours=1,  # Short expiry for testing
        notes="Test plan with all recommended enhancements"
    )
    
    print(f"[SUCCESS] Plan created successfully!")
    print(f"   Plan ID: {plan.get('plan_id', 'N/A')}")
    print(f"   Symbol: {plan.get('symbol', 'N/A')}")
    print(f"   Direction: {plan.get('direction', 'N/A')}")
    print(f"   Status: {plan.get('status', 'N/A')}")
    print()
    print("Plan Details:")
    import json
    print(json.dumps(plan, indent=2, default=str))
    print()
    print("=" * 60)
    print("[SUCCESS] Test complete - Check plan in database or web interface")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()

