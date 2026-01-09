#!/usr/bin/env python3
"""
Final test of API endpoints
"""
import requests
import json

def test_api_final():
    """Final test of API endpoints"""
    print("Final API Test...")
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
            
            # If we have timeframes, show them
            timeframes = data.get('timeframes', {})
            if timeframes:
                print("   Timeframe Details:")
                for tf, tf_data in timeframes.items():
                    print(f"     {tf}: {tf_data}")
            else:
                print("   No timeframe data - this is the problem!")
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
    
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print("If both endpoints return empty data, the issue is:")
    print("1. API server not using updated indicator bridge")
    print("2. Analyzer classes not working in API context")
    print("3. Some other issue with the API server")

if __name__ == "__main__":
    test_api_final()
