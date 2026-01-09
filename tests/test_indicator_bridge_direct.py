#!/usr/bin/env python3
"""
Test indicator bridge directly to see what data it returns
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from infra.indicator_bridge import IndicatorBridge
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_indicator_bridge_direct():
    """Test indicator bridge directly"""
    print("Testing Indicator Bridge Directly...")
    print("=" * 50)
    
    try:
        # Initialize indicator bridge
        bridge = IndicatorBridge(None)
        print("OK Indicator bridge initialized")
        
        # Test get_multi for XAUUSDc
        print("\nTesting get_multi for XAUUSDc...")
        result = bridge.get_multi("XAUUSDc")
        
        print(f"Result type: {type(result)}")
        print(f"Result keys: {list(result.keys()) if result else 'None'}")
        
        if result:
            for tf, data in result.items():
                print(f"\n{tf}:")
                print(f"  Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                if isinstance(data, dict):
                    # Show some key indicators
                    for key in ['close', 'current_close', 'ema20', 'rsi', 'adx']:
                        if key in data:
                            print(f"  {key}: {data[key]}")
        else:
            print("ERROR No data returned from get_multi")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_indicator_bridge_direct()
