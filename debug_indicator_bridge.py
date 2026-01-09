#!/usr/bin/env python3
"""
Debug script to test indicator bridge functionality
"""
import requests
import json
import sys

def test_indicator_bridge():
    """Test if indicator bridge is working"""
    base_url = "http://localhost:8000"
    
    print("Testing Indicator Bridge...")
    print("=" * 50)
    
    # Test 1: Health check
    print("\n1. Health Check:")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            health = response.json()
            print(f"   OK Health: {health['ok']}")
            print(f"   MT5: {health['components']['mt5_connection']}")
        else:
            print(f"   ERROR Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ERROR Health check error: {e}")
        return False
    
    # Test 2: Price endpoint (should work)
    print("\n2. Price Endpoint:")
    try:
        response = requests.get(f"{base_url}/api/v1/price/XAUUSDc", timeout=10)
        if response.status_code == 200:
            price_data = response.json()
            print(f"   OK Price: {price_data.get('mid', 'N/A')}")
        else:
            print(f"   ERROR Price failed: {response.status_code}")
    except Exception as e:
        print(f"   ERROR Price error: {e}")
    
    # Test 3: Multi-timeframe analysis
    print("\n3. Multi-Timeframe Analysis:")
    try:
        response = requests.get(f"{base_url}/api/v1/multi_timeframe/XAUUSDc", timeout=15)
        if response.status_code == 200:
            mtf_data = response.json()
            print(f"   Symbol: {mtf_data.get('symbol', 'N/A')}")
            print(f"   Alignment Score: {mtf_data.get('alignment_score', 'N/A')}")
            print(f"   Recommendation: {mtf_data.get('recommendation', {}).get('action', 'N/A')}")
            print(f"   Reason: {mtf_data.get('recommendation', {}).get('reason', 'N/A')}")
            
            # Check if timeframes have data
            timeframes = mtf_data.get('timeframes', {})
            print(f"   Timeframes available: {list(timeframes.keys())}")
            
            if not timeframes:
                print("   WARNING: No timeframe data - this is the problem!")
            else:
                for tf, data in timeframes.items():
                    print(f"      {tf}: {data}")
        else:
            print(f"   ERROR Multi-timeframe failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   ERROR Multi-timeframe error: {e}")
    
    # Test 4: Confluence analysis
    print("\n4. Confluence Analysis:")
    try:
        response = requests.get(f"{base_url}/api/v1/confluence/XAUUSDc", timeout=15)
        if response.status_code == 200:
            confluence_data = response.json()
            print(f"   Symbol: {confluence_data.get('symbol', 'N/A')}")
            print(f"   Score: {confluence_data.get('confluence_score', 'N/A')}")
            print(f"   Grade: {confluence_data.get('grade', 'N/A')}")
            print(f"   Recommendation: {confluence_data.get('recommendation', 'N/A')}")
            
            factors = confluence_data.get('factors', {})
            if factors:
                print("   Factors:")
                for factor, score in factors.items():
                    print(f"      {factor}: {score}")
            else:
                print("   WARNING: No factor data - this is the problem!")
        else:
            print(f"   ERROR Confluence failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   ERROR Confluence error: {e}")
    
    # Test 5: Check if we can get raw indicator data
    print("\n5. Raw Indicator Data Test:")
    try:
        # Try to get some basic market data that should work
        response = requests.get(f"{base_url}/api/v1/price/BTCUSDc", timeout=10)
        if response.status_code == 200:
            btc_data = response.json()
            print(f"   OK BTC Price: {btc_data.get('mid', 'N/A')}")
        else:
            print(f"   ERROR BTC Price failed: {response.status_code}")
    except Exception as e:
        print(f"   ERROR BTC Price error: {e}")
    
    print("\n" + "=" * 50)
    print("DIAGNOSIS:")
    print("If you see 'No data available' or empty timeframes, the issue is:")
    print("1. Indicator bridge not properly initialized")
    print("2. Symbol data not loaded in MT5")
    print("3. Indicator bridge can't access MT5 data")
    print("4. Missing indicator calculations")
    
    return True

if __name__ == "__main__":
    test_indicator_bridge()
