#!/usr/bin/env python3
"""
Test DTMS System Status
This script tests the DTMS system status and functionality
"""

import requests
import json
import time

def test_dtms_status():
    """Test the DTMS system status"""
    try:
        # Test health endpoint
        print("Testing DTMS API server health...")
        health_response = requests.get("http://localhost:8002/health", timeout=5)
        print(f"Health Status: {health_response.status_code}")
        print(f"Health Response: {health_response.json()}")
        
        # Test DTMS status endpoint
        print("\nTesting DTMS system status...")
        status_response = requests.get("http://localhost:8002/dtms/status", timeout=5)
        print(f"Status Code: {status_response.status_code}")
        print(f"Status Response: {status_response.json()}")
        
        # Test DTMS enable for BTCUSD
        print("\nTesting DTMS enable for BTCUSD...")
        dtms_data = {
            "symbol": "BTCUSD",
            "direction": "BUY",
            "entry": 108400,
            "stop_loss": 0,
            "take_profit": 0,
            "volume": 0,
            "ticket": 12345,  # Use a real ticket number
            "action": "enable"
        }
        
        enable_response = requests.post(
            "http://localhost:8002/dtms/trade/enable",
            json=dtms_data,
            timeout=5
        )
        print(f"Enable Status: {enable_response.status_code}")
        print(f"Enable Response: {enable_response.json()}")
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to DTMS API server on port 8000")
        print("Make sure the DTMS API server is running with: python dtms_api_server.py")
    except Exception as e:
        print(f"ERROR: Error testing DTMS system: {e}")

if __name__ == "__main__":
    test_dtms_status()