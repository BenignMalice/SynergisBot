"""
Test US10Y (10-Year Treasury Yield) Integration
"""

import asyncio
from infra.market_indices_service import create_market_indices_service


async def main():
    print("=" * 80)
    print("US10Y (10-Year Treasury Yield) Integration Test")
    print("=" * 80)
    print()
    
    # Create service
    indices = create_market_indices_service()
    
    # Test 1: Get US10Y data
    print("1. Testing US10Y fetch...")
    print("-" * 80)
    us10y_data = indices.get_us10y()
    
    if us10y_data['price']:
        print(f"   Price: {us10y_data['price']:.3f}%")
        print(f"   Trend: {us10y_data['trend']}")
        print(f"   Level: {us10y_data['level']}")
        print(f"   Interpretation: {us10y_data['interpretation']}")
        print(f"   Gold Correlation: {us10y_data['gold_correlation']}")
        print(f"   Source: {us10y_data['source']}")
        print(f"   Status: SUCCESS")
    else:
        print(f"   Error: {us10y_data['interpretation']}")
        print(f"   Status: FAILED")
    print()
    
    # Test 2: Get complete market context (DXY + VIX + US10Y)
    print("2. Testing complete market context (DXY + VIX + US10Y)...")
    print("-" * 80)
    context = indices.get_market_context()
    
    print(f"   DXY: {context['dxy']['price']:.3f} ({context['dxy']['trend']})")
    print(f"   VIX: {context['vix']['price']:.2f} ({context['vix']['level']})")
    print(f"   US10Y: {context['us10y']['price']:.3f}% ({context['us10y']['trend']})")
    print()
    print(f"   Gold Outlook: {context['gold_outlook']}")
    print()
    print(f"   Trading Implications:")
    for implication in context['implications']:
        print(f"     - {implication}")
    print()
    print(f"   Summary: {context['summary']}")
    print()
    
    # Test 3: Gold trade decision logic
    print("3. Gold Trade Decision Logic...")
    print("-" * 80)
    
    dxy_signal = "bearish" if context['dxy']['trend'] == 'down' else "bullish" if context['dxy']['trend'] == 'up' else "neutral"
    us10y_signal = context['us10y']['gold_correlation']
    
    print(f"   DXY Signal for Gold: {dxy_signal}")
    print(f"   US10Y Signal for Gold: {us10y_signal}")
    print()
    
    if dxy_signal == "bullish" and us10y_signal == "bullish":
        decision = "STRONG BUY - Both DXY and US10Y favor Gold"
        emoji = "🟢🟢"
    elif dxy_signal == "bearish" and us10y_signal == "bearish":
        decision = "STRONG SELL - Both DXY and US10Y against Gold"
        emoji = "🔴🔴"
    elif dxy_signal == "bullish" or us10y_signal == "bullish":
        decision = "WEAK BUY - Only one signal favors Gold"
        emoji = "🟢"
    elif dxy_signal == "bearish" or us10y_signal == "bearish":
        decision = "WEAK SELL - Only one signal against Gold"
        emoji = "🔴"
    else:
        decision = "NEUTRAL - Mixed/unclear signals"
        emoji = ""
    
    print(f"   {emoji} Decision: {decision}")
    print()
    
    # Test 4: Example scenarios
    print("4. Example Gold Trade Scenarios...")
    print("-" * 80)
    
    scenarios = [
        {
            "name": "Perfect Long Setup",
            "dxy_trend": "down",
            "us10y_trend": "down",
            "expected": "🟢🟢 STRONG BUY"
        },
        {
            "name": "Perfect Short Setup",
            "dxy_trend": "up",
            "us10y_trend": "up",
            "expected": "🔴🔴 STRONG SELL"
        },
        {
            "name": "Mixed Signals",
            "dxy_trend": "up",
            "us10y_trend": "down",
            "expected": "⚪ WAIT - Conflicting"
        }
    ]
    
    for scenario in scenarios:
        print(f"   Scenario: {scenario['name']}")
        print(f"     DXY: {scenario['dxy_trend']}")
        print(f"     US10Y: {scenario['us10y_trend']}")
        print(f"     Recommendation: {scenario['expected']}")
        print()
    
    print("=" * 80)
    print("Test Complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

