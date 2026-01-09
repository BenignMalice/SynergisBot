#!/usr/bin/env python3
"""
Trade Monitoring Script for XAUUSD
Monitors Intelligent Exits and DTMS activity
"""

import time
import requests
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_trade_status():
    """Check current trade status"""
    try:
        # Try different possible endpoints
        endpoints = [
            "http://localhost:8000/mt5/positions",
            "http://localhost:8000/positions", 
            "http://localhost:8000/trades",
            "http://localhost:8000/mt5/trades",
            "http://localhost:8000/health"
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=5)
                if response.status_code == 200:
                    print(f"✅ {endpoint}: {response.json()}")
                    return True
                else:
                    print(f"❌ {endpoint}: {response.status_code}")
            except Exception as e:
                print(f"⚠️ {endpoint}: {e}")
        
        return False
    except Exception as e:
        print(f"❌ Error checking trade status: {e}")
        return False

def monitor_intelligent_exits():
    """Monitor Intelligent Exits activity"""
    try:
        # Check for intelligent exits log file
        log_files = [
            "data/intelligent_exits.json",
            "logs/intelligent_exits.log",
            "data/logs/intelligent_exits.json"
        ]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    data = json.load(f)
                    print(f"📊 Intelligent Exits Status: {data}")
                    return True
        
        print("⚠️ No Intelligent Exits log file found")
        return False
    except Exception as e:
        print(f"❌ Error monitoring Intelligent Exits: {e}")
        return False

def monitor_dtms():
    """Monitor DTMS activity"""
    try:
        # Check for DTMS status
        dtms_endpoints = [
            "http://localhost:8000/dtms/status",
            "http://localhost:8000/mt5/dtms",
            "http://localhost:8000/dtms"
        ]
        
        for endpoint in dtms_endpoints:
            try:
                response = requests.get(endpoint, timeout=5)
                if response.status_code == 200:
                    print(f"✅ DTMS {endpoint}: {response.json()}")
                    return True
            except:
                continue
        
        print("⚠️ DTMS endpoints not accessible")
        return False
    except Exception as e:
        print(f"❌ Error monitoring DTMS: {e}")
        return False

def main():
    """Main monitoring loop"""
    print("🔍 Starting XAUUSD Trade Monitoring...")
    print("=" * 50)
    
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{timestamp}] Monitoring Trade Status...")
        
        # Check trade status
        trade_ok = check_trade_status()
        
        # Monitor Intelligent Exits
        ie_ok = monitor_intelligent_exits()
        
        # Monitor DTMS
        dtms_ok = monitor_dtms()
        
        # Summary
        print(f"\n📊 Status Summary:")
        print(f"   Trade Status: {'✅' if trade_ok else '❌'}")
        print(f"   Intelligent Exits: {'✅' if ie_ok else '❌'}")
        print(f"   DTMS: {'✅' if dtms_ok else '❌'}")
        
        print("\n⏳ Waiting 30 seconds...")
        time.sleep(30)

if __name__ == "__main__":
    main()
