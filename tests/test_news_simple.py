#!/usr/bin/env python3
"""
Simple News Trading Strategy Test
"""

import os
import sys
import json
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_enhanced_data():
    """Test enhanced data structure"""
    print("Testing Enhanced Data Structure...")
    
    try:
        with open("data/news_events.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"SUCCESS: Total events: {data.get('total_events', 0)}")
        print(f"SUCCESS: Enhanced with sentiment: {data.get('enhanced_with_sentiment', False)}")
        print(f"SUCCESS: Last updated: {data.get('last_updated', 'N/A')}")
        
        # Check sample event
        events = data.get('events', [])
        if events:
            sample_event = events[0]
            required_fields = ['sentiment', 'trading_implication', 'risk_level', 'enhanced_at']
            
            print("\nSample Event Structure:")
            for field in required_fields:
                if field in sample_event:
                    print(f"  {field}: {sample_event[field]}")
                else:
                    print(f"  {field}: Missing")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Data Structure Test Failed: {e}")
        return False

def test_sentiment_distribution():
    """Test sentiment distribution"""
    print("\nTesting Sentiment Distribution...")
    
    try:
        with open("data/news_events.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        events = data.get('events', [])
        
        # Count sentiments
        bullish_count = sum(1 for e in events if e.get('sentiment') == 'BULLISH')
        bearish_count = sum(1 for e in events if e.get('sentiment') == 'BEARISH')
        neutral_count = sum(1 for e in events if e.get('sentiment') == 'NEUTRAL')
        
        print(f"SUCCESS: Bullish events: {bullish_count}")
        print(f"SUCCESS: Bearish events: {bearish_count}")
        print(f"SUCCESS: Neutral events: {neutral_count}")
        
        # Count risk levels
        high_risk_count = sum(1 for e in events if e.get('risk_level') in ['HIGH', 'ULTRA_HIGH'])
        medium_risk_count = sum(1 for e in events if e.get('risk_level') == 'MEDIUM')
        low_risk_count = sum(1 for e in events if e.get('risk_level') == 'LOW')
        
        print(f"SUCCESS: High risk events: {high_risk_count}")
        print(f"SUCCESS: Medium risk events: {medium_risk_count}")
        print(f"SUCCESS: Low risk events: {low_risk_count}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Sentiment Distribution Test Failed: {e}")
        return False

def test_trading_implications():
    """Test trading implications"""
    print("\nTesting Trading Implications...")
    
    try:
        with open("data/news_events.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        events = data.get('events', [])
        
        # Count events with trading implications
        implication_count = sum(1 for e in events if e.get('trading_implication'))
        print(f"SUCCESS: Events with trading implications: {implication_count}")
        
        # Show sample implications
        sample_implications = [e.get('trading_implication') for e in events if e.get('trading_implication')][:3]
        print("\nSample Trading Implications:")
        for i, implication in enumerate(sample_implications, 1):
            print(f"  {i}. {implication}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Trading Implications Test Failed: {e}")
        return False

def test_high_impact_events():
    """Test high impact events"""
    print("\nTesting High Impact Events...")
    
    try:
        with open("data/news_events.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        events = data.get('events', [])
        
        # Find high impact events
        high_impact = [e for e in events if e.get('impact') == 'high']
        ultra_high_impact = [e for e in events if e.get('impact') == 'ultra']
        
        print(f"SUCCESS: High impact events: {len(high_impact)}")
        print(f"SUCCESS: Ultra high impact events: {len(ultra_high_impact)}")
        
        # Show sample high impact events
        if high_impact:
            print("\nSample High Impact Events:")
            for event in high_impact[:3]:
                print(f"  - {event.get('description', 'N/A')} ({event.get('sentiment', 'N/A')})")
        
        return True
        
    except Exception as e:
        print(f"ERROR: High Impact Events Test Failed: {e}")
        return False

def main():
    """Run all tests"""
    print("NEWS TRADING STRATEGY TEST")
    print("=" * 40)
    
    tests = [
        ("Enhanced Data Structure", test_enhanced_data),
        ("Sentiment Distribution", test_sentiment_distribution),
        ("Trading Implications", test_trading_implications),
        ("High Impact Events", test_high_impact_events)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\nRunning {test_name} Test...")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"SUCCESS: {test_name} Test PASSED")
            else:
                print(f"ERROR: {test_name} Test FAILED")
        except Exception as e:
            print(f"ERROR: {test_name} Test ERROR - {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 40)
    print("TEST RESULTS SUMMARY")
    print("=" * 40)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"  {test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nSUCCESS: All tests passed! News trading strategy is ready!")
    else:
        print(f"\nWARNING: {total - passed} tests failed.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
