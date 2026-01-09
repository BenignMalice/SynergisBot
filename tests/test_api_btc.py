#!/usr/bin/env python3
"""
Test API data fetching for BTCUSD symbols
"""

import httpx
import asyncio
import json

async def test_btc_data():
    """Test fetching BTC data from the API"""
    
    print("🧪 Testing BTC data fetching from API...\n")
    
    symbols_to_test = [
        "BTCUSD",
        "BTCUSDC",
        "btcusdc",
        "BTCUSDc"
    ]
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        for symbol in symbols_to_test:
            print(f"\n{'='*60}")
            print(f"Testing symbol: {symbol}")
            print(f"{'='*60}\n")
            
            try:
                # Test price endpoint
                print(f"1. Price endpoint: /api/v1/price/{symbol}")
                price_response = await client.get(f"http://localhost:8000/api/v1/price/{symbol}")
                print(f"   Status: {price_response.status_code}")
                if price_response.status_code == 200:
                    price_data = price_response.json()
                    print(f"   Bid: {price_data.get('bid', 'N/A')}")
                    print(f"   Ask: {price_data.get('ask', 'N/A')}")
                    print(f"   Mid: {price_data.get('mid', 'N/A')}")
                else:
                    print(f"   Error: {price_response.text}")
                
                # Test multi-timeframe endpoint
                print(f"\n2. Multi-timeframe endpoint: /api/v1/multi_timeframe/{symbol}")
                mtf_response = await client.get(f"http://localhost:8000/api/v1/multi_timeframe/{symbol}")
                print(f"   Status: {mtf_response.status_code}")
                if mtf_response.status_code == 200:
                    mtf_data = mtf_response.json()
                    
                    # Check H4 data
                    h4_data = mtf_data.get('timeframes', {}).get('H4', {})
                    print(f"   H4 Bias: {h4_data.get('bias', 'N/A')}")
                    print(f"   H4 RSI: {h4_data.get('rsi', 'N/A')}")
                    print(f"   H4 ADX: {h4_data.get('adx', 'N/A')}")
                    print(f"   H4 EMA20: {h4_data.get('ema20', 'N/A')}")
                    print(f"   H4 ATR: {h4_data.get('atr', 'N/A')}")
                    
                    # Check M5 data
                    m5_data = mtf_data.get('timeframes', {}).get('M5', {})
                    print(f"   M5 RSI: {m5_data.get('rsi', 'N/A')}")
                    print(f"   M5 ADX: {m5_data.get('adx', 'N/A')}")
                    
                    # Check recommendation
                    rec = mtf_data.get('recommendation', {})
                    print(f"   Recommendation: {rec.get('action', 'N/A')}")
                    print(f"   Alignment Score: {rec.get('alignment_score', 'N/A')}")
                else:
                    print(f"   Error: {mtf_response.text}")
                
            except Exception as e:
                print(f"   ❌ Exception: {e}")
    
    print(f"\n{'='*60}")
    print("✅ Test complete!")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    print("Make sure the API server is running (python app/main_api.py)\n")
    asyncio.run(test_btc_data())

