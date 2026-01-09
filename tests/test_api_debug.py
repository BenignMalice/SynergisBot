#!/usr/bin/env python3
"""
Test API endpoints with debug logging
"""
import requests
import json

def test_api_debug():
    """Test API endpoints with detailed debugging"""
    print("Testing API Endpoints with Debug...")
    print("=" * 50)
    
    # Test multi-timeframe endpoint
    print("\n1. Multi-Timeframe Analysis:")
    try:
        response = requests.get('http://localhost:8000/api/v1/multi_timeframe/XAUUSDc', timeout=15)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Symbol: {data.get('symbol', 'N/A')}")
            print(f"   Alignment Score: {data.get('alignment_score', 'N/A')}")
            print(f"   Timeframes: {list(data.get('timeframes', {}).keys())}")
            print(f"   Recommendation: {data.get('recommendation', {}).get('action', 'N/A')}")
            print(f"   Reason: {data.get('recommendation', {}).get('reason', 'N/A')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test confluence endpoint
    print("\n2. Confluence Analysis:")
    try:
        response = requests.get('http://localhost:8000/api/v1/confluence/XAUUSDc', timeout=15)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Symbol: {data.get('symbol', 'N/A')}")
            print(f"   Score: {data.get('confluence_score', 'N/A')}")
            print(f"   Grade: {data.get('grade', 'N/A')}")
            print(f"   Recommendation: {data.get('recommendation', 'N/A')}")
            factors = data.get('factors', {})
            if factors:
                print(f"   Factors: {factors}")
            else:
                print("   No factors data")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test direct indicator bridge endpoint (if it exists)
    print("\n3. Direct Indicator Bridge Test:")
    try:
        # Try to test the indicator bridge directly through a simple endpoint
        response = requests.get('http://localhost:8000/api/v1/price/XAUUSDc', timeout=10)
        print(f"   Price Status: {response.status_code}")
        if response.status_code == 200:
            price_data = response.json()
            print(f"   Price: {price_data.get('mid', 'N/A')}")
        else:
            print(f"   Price Error: {response.text}")
    except Exception as e:
        print(f"   Price Exception: {e}")

if __name__ == "__main__":
    test_api_debug()
