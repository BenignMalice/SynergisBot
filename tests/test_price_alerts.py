"""
Test script for Price Alerts system
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_create_alerts():
    """Test creating price alerts"""
    print("=" * 60)
    print("TEST 1: Creating Price Alerts")
    print("=" * 60)
    
    # Create bearish alert
    print("\n1. Creating BEARISH alert (below $3,950)...")
    response = requests.post(f"{BASE_URL}/api/v1/alerts/create", json={
        "symbol": "XAUUSD",
        "alert_type": "below",
        "target_price": 3950.0,
        "message": "🔴 Gold breakdown below $3,950 - Consider short entry"
    })
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    
    # Create bullish alert
    print("\n2. Creating BULLISH alert (above $3,975)...")
    response = requests.post(f"{BASE_URL}/api/v1/alerts/create", json={
        "symbol": "XAUUSD",
        "alert_type": "above",
        "target_price": 3975.0,
        "message": "🟢 Gold reversal above $3,975 - Consider long entry"
    })
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))


def test_list_alerts():
    """Test listing alerts"""
    print("\n" + "=" * 60)
    print("TEST 2: Listing Active Alerts")
    print("=" * 60)
    
    print("\nFetching all XAUUSD alerts...")
    response = requests.get(f"{BASE_URL}/api/v1/alerts?symbol=XAUUSD&active_only=true")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))


def test_current_price():
    """Check current Gold price"""
    print("\n" + "=" * 60)
    print("TEST 3: Current Gold Price")
    print("=" * 60)
    
    print("\nFetching current XAUUSD price...")
    response = requests.get(f"{BASE_URL}/api/v1/price/XAUUSD")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"\nCurrent Gold Price: ${data['mid']:.2f}")
    print(f"Bid: ${data['bid']:.2f}")
    print(f"Ask: ${data['ask']:.2f}")
    print(f"Spread: ${data['spread']:.2f}")


def test_start_monitoring():
    """Test starting alert monitoring"""
    print("\n" + "=" * 60)
    print("TEST 4: Start Alert Monitoring")
    print("=" * 60)
    
    print("\nStarting price monitoring (60s interval)...")
    response = requests.post(f"{BASE_URL}/api/v1/alerts/start_monitoring?check_interval=60")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    print("\n✅ Monitoring started! Alerts will be checked every 60 seconds.")
    print("   Telegram notifications will be sent when prices are hit.")


def main():
    print("\n" + "🔔" * 30)
    print("   PRICE ALERTS SYSTEM - TEST SUITE")
    print("🔔" * 30)
    
    try:
        # Test 1: Create alerts
        test_create_alerts()
        
        # Test 2: List alerts
        test_list_alerts()
        
        # Test 3: Current price
        test_current_price()
        
        # Test 4: Start monitoring
        test_start_monitoring()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED!")
        print("=" * 60)
        print("\n📋 Summary:")
        print("  • Price alerts created for Gold ($3,950 and $3,975)")
        print("  • Monitoring started (checks every 60 seconds)")
        print("  • Telegram notifications will be sent when prices hit")
        print("\n📁 Check: data/price_alerts.json for stored alerts")
        print("📊 Monitor: Server logs for alert triggers")
        print("\n🎯 Next: Ask Custom GPT to set alerts for you!")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to server!")
        print("   Make sure the API server is running:")
        print("   > python -m uvicorn app.main_api:app --reload --host 0.0.0.0 --port 8000")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")


if __name__ == "__main__":
    main()

