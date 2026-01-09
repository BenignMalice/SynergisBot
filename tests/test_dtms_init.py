#!/usr/bin/env python3
"""
Test DTMS Initialization
This script initializes the DTMS system via the API
"""

import requests
import json
import time

def initialize_dtms_via_api():
    """Initialize DTMS system via API"""
    try:
        print("Initializing DTMS system via API...")
        
        # Initialize DTMS system
        init_response = requests.post("http://localhost:8001/dtms/initialize", timeout=30)
        print(f"Init Status: {init_response.status_code}")
        print(f"Init Response: {init_response.json()}")
        
        if init_response.status_code == 200:
            print("\nDTMS system initialized successfully!")
            
            # Test DTMS status
            print("\nTesting DTMS status...")
            status_response = requests.get("http://localhost:8001/dtms/status", timeout=5)
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
                "ticket": 0,
                "action": "enable"
            }
            
            enable_response = requests.post(
                "http://localhost:8001/dtms/status",
                json=dtms_data,
                timeout=5
            )
            print(f"Enable Status: {enable_response.status_code}")
            print(f"Enable Response: {enable_response.json()}")
            
        else:
            print("Failed to initialize DTMS system")
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to DTMS API server on port 8001")
        print("Make sure the DTMS API server is running with: python dtms_api_server.py")
    except Exception as e:
        print(f"ERROR: Error initializing DTMS system: {e}")

if __name__ == "__main__":
    initialize_dtms_via_api()
