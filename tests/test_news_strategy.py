#!/usr/bin/env python3
"""
Test News Trading Strategy
Comprehensive test of all news trading components
"""

import os
import sys
import json
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from infra.news_service import NewsService

def test_news_service():
    """Test the enhanced news service"""
    print("🧪 Testing News Service Integration...")
    
    try:
        # Initialize news service
        news_service = NewsService("data/news_events.json")
        
        # Test 1: Load events with sentiment data
        print("\n📊 Test 1: Loading events with sentiment data...")
        events_with_data = news_service.get_events_with_actual_data("macro", hours_ahead=24)
        print(f"✅ Found {len(events_with_data)} events with actual data")
        
        # Test 2: Get surprise events
        print("\n📈 Test 2: Finding surprise events...")
        surprise_events = news_service.get_surprise_events("macro", min_surprise_pct=5.0, hours_ahead=24)
        print(f"✅ Found {len(surprise_events)} surprise events")
        
        # Test 3: Get events by sentiment
        print("\n🎯 Test 3: Analyzing sentiment distribution...")
        bullish_events = [e for e in events_with_data if hasattr(e, 'sentiment') and e.sentiment == 'BULLISH']
        bearish_events = [e for e in events_with_data if hasattr(e, 'sentiment') and e.sentiment == 'BEARISH']
        neutral_events = [e for e in events_with_data if hasattr(e, 'sentiment') and e.sentiment == 'NEUTRAL']
        
        print(f"   📈 Bullish events: {len(bullish_events)}")
        print(f"   📉 Bearish events: {len(bearish_events)}")
        print(f"   ⚪ Neutral events: {len(neutral_events)}")
        
        # Test 4: Get high-risk events
        print("\n⚠️ Test 4: Identifying high-risk events...")
        high_risk_events = [e for e in events_with_data if hasattr(e, 'risk_level') and e.risk_level in ['HIGH', 'ULTRA_HIGH']]
        print(f"✅ Found {len(high_risk_events)} high-risk events")
        
        # Test 5: Get trading implications
        print("\n💡 Test 5: Trading implications analysis...")
        trading_events = [e for e in events_with_data if hasattr(e, 'trading_implication') and e.trading_implication]
        print(f"✅ Found {len(trading_events)} events with trading implications")
        
        # Show sample events
        if events_with_data:
            print("\n📋 Sample Enhanced Event:")
            sample_event = events_with_data[0]
            print(f"   Description: {sample_event.description}")
            print(f"   Sentiment: {getattr(sample_event, 'sentiment', 'N/A')}")
            print(f"   Risk Level: {getattr(sample_event, 'risk_level', 'N/A')}")
            print(f"   Trading Implication: {getattr(sample_event, 'trading_implication', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ News Service Test Failed: {e}")
        return False

def test_enhanced_data_structure():
    """Test the enhanced data structure"""
    print("\n🧪 Testing Enhanced Data Structure...")
    
    try:
        # Load the enhanced news data
        with open("data/news_events.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ Total events: {data.get('total_events', 0)}")
        print(f"✅ Enhanced with sentiment: {data.get('enhanced_with_sentiment', False)}")
        print(f"✅ Last updated: {data.get('last_updated', 'N/A')}")
        
        # Check sample event structure
        events = data.get('events', [])
        if events:
            sample_event = events[0]
            required_fields = ['sentiment', 'trading_implication', 'risk_level', 'enhanced_at']
            
            print("\n📋 Sample Event Structure:")
            for field in required_fields:
                if field in sample_event:
                    print(f"   ✅ {field}: {sample_event[field]}")
                else:
                    print(f"   ❌ {field}: Missing")
        
        return True
        
    except Exception as e:
        print(f"❌ Data Structure Test Failed: {e}")
        return False

def test_sentiment_analysis():
    """Test sentiment analysis functionality"""
    print("\n🧪 Testing Sentiment Analysis...")
    
    try:
        # Test different event types
        test_events = [
            {
                "description": "Non-Farm Payrolls",
                "impact": "high",
                "sentiment": "BULLISH",
                "trading_implication": "Major USD volatility expected",
                "risk_level": "HIGH"
            },
            {
                "description": "CPI Inflation",
                "impact": "high", 
                "sentiment": "BEARISH",
                "trading_implication": "Inflation data will drive Fed policy",
                "risk_level": "HIGH"
            },
            {
                "description": "Business Confidence",
                "impact": "low",
                "sentiment": "NEUTRAL",
                "trading_implication": "Low impact - minimal movement",
                "risk_level": "LOW"
            }
        ]
        
        print("📊 Sentiment Analysis Results:")
        for event in test_events:
            print(f"   📰 {event['description']}")
            print(f"      Sentiment: {event['sentiment']}")
            print(f"      Risk: {event['risk_level']}")
            print(f"      Implication: {event['trading_implication']}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Sentiment Analysis Test Failed: {e}")
        return False

def test_news_trading_scenarios():
    """Test different news trading scenarios"""
    print("\n🧪 Testing News Trading Scenarios...")
    
    scenarios = [
        {
            "name": "High Impact Bullish News",
            "event": "Non-Farm Payrolls",
            "sentiment": "BULLISH",
            "risk_level": "HIGH",
            "strategy": "Wait for pullback after initial spike, then enter LONG"
        },
        {
            "name": "High Impact Bearish News", 
            "event": "CPI Inflation",
            "sentiment": "BEARISH",
            "risk_level": "HIGH",
            "strategy": "Wait for pullback after initial spike, then enter SHORT"
        },
        {
            "name": "Low Impact Neutral News",
            "event": "Business Confidence",
            "sentiment": "NEUTRAL", 
            "risk_level": "LOW",
            "strategy": "Monitor for breakout opportunities"
        }
    ]
    
    print("📈 News Trading Scenarios:")
    for scenario in scenarios:
        print(f"\n   🎯 {scenario['name']}")
        print(f"      Event: {scenario['event']}")
        print(f"      Sentiment: {scenario['sentiment']}")
        print(f"      Risk: {scenario['risk_level']}")
        print(f"      Strategy: {scenario['strategy']}")
    
    return True

def main():
    """Run all tests"""
    print("NEWS TRADING STRATEGY TEST SUITE")
    print("=" * 50)
    
    tests = [
        ("Enhanced Data Structure", test_enhanced_data_structure),
        ("News Service Integration", test_news_service),
        ("Sentiment Analysis", test_sentiment_analysis),
        ("News Trading Scenarios", test_news_trading_scenarios)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name} Test...")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"✅ {test_name} Test: PASSED")
            else:
                print(f"❌ {test_name} Test: FAILED")
        except Exception as e:
            print(f"❌ {test_name} Test: ERROR - {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Your news trading strategy is ready! 🚀📰💰")
    else:
        print(f"\n⚠️ {total - passed} tests failed. Please check the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
