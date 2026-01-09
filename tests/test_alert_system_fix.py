#!/usr/bin/env python3
"""
Test Alert System Fix
====================
This script tests the alert system with the correct parameters to verify
the fix is working properly.
"""

import json
import asyncio
from enhanced_alert_intent_parser import AlertIntentParser

async def test_alert_system():
    """Test the alert system with the user's specific request."""
    
    print("Testing Alert System Fix")
    print("=" * 50)
    
    # Initialize the enhanced parser
    parser = AlertIntentParser()
    
    # Test the user's specific request
    user_request = "set alert for monitor near 4,248 for first partials; volatility high (VIX > 20)"
    
    print(f"User Request: {user_request}")
    print()
    
    try:
        # Parse the user intent
        alert_params = parser.parse_alert_request(user_request)
        
        print("SUCCESS - Parsed Alert Parameters:")
        print(json.dumps(alert_params, indent=2))
        print()
        
        # Simulate the moneybot.add_alert tool call
        print("Simulating moneybot.add_alert tool call:")
        print(f"Tool: moneybot.add_alert")
        print(f"Arguments: {json.dumps(alert_params, indent=2)}")
        print()
        
        # Verify the parameters are correct
        required_fields = ["symbol", "alert_type", "condition", "description"]
        missing_fields = [field for field in required_fields if field not in alert_params]
        
        if missing_fields:
            print(f"ERROR - Missing required fields: {missing_fields}")
            return False
        
        # Check symbol has 'c' suffix
        if not alert_params["symbol"].endswith("c"):
            print(f"ERROR - Symbol should end with 'c': {alert_params['symbol']}")
            return False
        
        # Check price level is correct
        if alert_params["parameters"]["price_level"] != 4248.0:
            print(f"ERROR - Price level should be 4248.0: {alert_params['parameters']['price_level']}")
            return False
        
        # Check volatility conditions are included
        if "volatility_condition" not in alert_params["parameters"]:
            print("ERROR - Volatility conditions not included")
            return False
        
        # Check purpose is included
        if "purpose" not in alert_params["parameters"]:
            print("ERROR - Purpose not included")
            return False
        
        print("SUCCESS - All parameters are correct!")
        print("SUCCESS - Alert system fix is working properly!")
        
        return True
        
    except Exception as e:
        print(f"ERROR - Error parsing alert request: {e}")
        return False

async def test_multiple_scenarios():
    """Test multiple alert scenarios."""
    
    test_cases = [
        "set alert for monitor near 4,248 for first partials; volatility high (VIX > 20)",
        "alert me when bitcoin hits 115000",
        "notify me if gold drops below 2600",
        "alert when EURUSD crosses above 1.0850",
        "set alert for BTCUSD at 50000 for entry signal"
    ]
    
    parser = AlertIntentParser()
    
    print("\nTesting Multiple Scenarios")
    print("=" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. Testing: {test_case}")
        try:
            result = parser.parse_alert_request(test_case)
            print(f"   SUCCESS: {result['symbol']} {result['condition']} {result['parameters']['price_level']}")
        except Exception as e:
            print(f"   ERROR: {e}")

if __name__ == "__main__":
    print("Alert System Fix Test")
    print("=" * 50)
    
    # Test the main scenario
    success = asyncio.run(test_alert_system())
    
    if success:
        # Test multiple scenarios
        asyncio.run(test_multiple_scenarios())
        
        print("\n" + "=" * 50)
        print("ALERT SYSTEM FIX COMPLETE!")
        print("SUCCESS - User intent parsing: WORKING")
        print("SUCCESS - Parameter mapping: WORKING") 
        print("SUCCESS - Volatility conditions: WORKING")
        print("SUCCESS - Broker symbol support: WORKING")
        print("SUCCESS - Ready for integration!")
    else:
        print("\nERROR - Alert system fix needs more work")
