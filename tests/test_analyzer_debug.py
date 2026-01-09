#!/usr/bin/env python3
"""
Debug analyzer classes to see what's happening
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from infra.indicator_bridge import IndicatorBridge
from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
from infra.confluence_calculator import ConfluenceCalculator
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_analyzer_debug():
    """Debug analyzer classes"""
    print("Debugging Analyzer Classes...")
    print("=" * 50)
    
    try:
        # Initialize indicator bridge
        bridge = IndicatorBridge(None)
        print("OK Indicator bridge initialized")
        
        # Test get_multi directly
        print("\n1. Testing get_multi directly...")
        multi_data = bridge.get_multi("XAUUSDc")
        print(f"   Multi data keys: {list(multi_data.keys()) if multi_data else 'None'}")
        print(f"   Multi data type: {type(multi_data)}")
        
        if multi_data:
            print("   OK Multi data available")
            for tf, data in multi_data.items():
                print(f"   {tf}: {len(data) if isinstance(data, dict) else 'Not dict'} keys")
        else:
            print("   ERROR No multi data")
            return
        
        # Test MultiTimeframeAnalyzer with debug
        print("\n2. Testing MultiTimeframeAnalyzer...")
        mtf_analyzer = MultiTimeframeAnalyzer(bridge)
        
        # Check what get_multi returns in the analyzer
        print("   Testing get_multi in analyzer context...")
        analyzer_multi_data = bridge.get_multi("XAUUSDc")
        print(f"   Analyzer multi data keys: {list(analyzer_multi_data.keys()) if analyzer_multi_data else 'None'}")
        
        if analyzer_multi_data:
            print("   OK Analyzer has multi data")
            mtf_result = mtf_analyzer.analyze("XAUUSDc")
            print(f"   MTF Result: {mtf_result}")
        else:
            print("   ERROR Analyzer has no multi data")
        
        # Test ConfluenceCalculator with debug
        print("\n3. Testing ConfluenceCalculator...")
        confluence_calc = ConfluenceCalculator(bridge)
        
        # Check what get_multi returns in the calculator
        print("   Testing get_multi in calculator context...")
        calc_multi_data = bridge.get_multi("XAUUSDc")
        print(f"   Calculator multi data keys: {list(calc_multi_data.keys()) if calc_multi_data else 'None'}")
        
        if calc_multi_data:
            print("   OK Calculator has multi data")
            confluence_result = confluence_calc.calculate_confluence("XAUUSDc")
            print(f"   Confluence Result: {confluence_result}")
        else:
            print("   ERROR Calculator has no multi data")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_analyzer_debug()
