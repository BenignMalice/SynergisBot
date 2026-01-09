#!/usr/bin/env python3
"""
Create XAUUSD Alert for Monitoring Near 4,248
============================================
This script creates a proper alert for monitoring XAUUSD near 4,248 for first partials
with high volatility (VIX > 20) using the correct alert parameters.
"""

import asyncio
import json
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def create_xauusd_alert():
    """Create the XAUUSD alert with proper parameters."""
    
    # Alert parameters for monitoring near 4,248 for first partials
    alert_params = {
        "symbol": "XAUUSD",
        "alert_type": "price",
        "condition": "crosses_above",
        "description": "XAUUSD crosses above 4248 for first partials - high volatility (VIX > 20)",
        "parameters": {
            "price_level": 4248.0,
            "volatility_condition": "high",
            "vix_threshold": 20.0,
            "purpose": "first_partials"
        },
        "expires_hours": 24,  # Alert expires in 24 hours
        "one_time": True  # One-time alert
    }
    
    logger.info("🔔 Creating XAUUSD alert for monitoring near 4,248...")
    logger.info(f"Alert parameters: {json.dumps(alert_params, indent=2)}")
    
    return alert_params

def create_alert_command():
    """Create the proper alert command for the system."""
    
    alert_params = {
        "symbol": "XAUUSD",
        "alert_type": "price", 
        "condition": "crosses_above",
        "description": "XAUUSD crosses above 4248 for first partials - high volatility (VIX > 20)",
        "parameters": {
            "price_level": 4248.0,
            "volatility_condition": "high",
            "vix_threshold": 20.0,
            "purpose": "first_partials"
        },
        "expires_hours": 24,
        "one_time": True
    }
    
    print("🔔 XAUUSD Alert Command")
    print("=" * 50)
    print("Tool: moneybot.add_alert")
    print("Arguments:")
    print(json.dumps(alert_params, indent=2))
    print("=" * 50)
    print("✅ This alert will:")
    print("  • Monitor XAUUSD price crossing above 4,248")
    print("  • Only trigger when VIX > 20 (high volatility)")
    print("  • Alert for first partials opportunity")
    print("  • Expire in 24 hours")
    print("  • One-time alert (removed after triggering)")
    
    return alert_params

if __name__ == "__main__":
    print("🔔 XAUUSD Alert Creator")
    print("=" * 50)
    
    # Create the alert command
    alert_command = create_alert_command()
    
    print("\n📋 To create this alert, use:")
    print("Tool: moneybot.add_alert")
    print("Arguments:", json.dumps(alert_command, indent=2))
    
    print("\n✅ Alert will monitor XAUUSD near 4,248 for first partials with high volatility!")
