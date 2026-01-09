#!/usr/bin/env python3
"""
Test analyzer classes directly
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from infra.indicator_bridge import IndicatorBridge
from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
from infra.confluence_calculator import ConfluenceCalculator
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_analyzers_direct():
    """Test analyzer classes directly"""
    print("Testing Analyzer Classes Directly...")
    print("=" * 50)
    
    try:
        # Initialize indicator bridge
        bridge = IndicatorBridge(None)
        print("OK Indicator bridge initialized")
        
        # Test get_multi
        print("\nTesting get_multi...")
        multi_data = bridge.get_multi("XAUUSDc")
        print(f"Multi data keys: {list(multi_data.keys()) if multi_data else 'None'}")
        
        if multi_data:
            print("OK Multi data available")
            
            # Test MultiTimeframeAnalyzer
            print("\nTesting MultiTimeframeAnalyzer...")
            mtf_analyzer = MultiTimeframeAnalyzer(bridge)
            mtf_result = mtf_analyzer.analyze("XAUUSDc")
            print(f"MTF Result keys: {list(mtf_result.keys()) if mtf_result else 'None'}")
            print(f"MTF Timeframes: {list(mtf_result.get('timeframes', {}).keys()) if mtf_result else 'None'}")
            print(f"MTF Alignment Score: {mtf_result.get('alignment_score', 'None') if mtf_result else 'None'}")
            
            # Test ConfluenceCalculator
            print("\nTesting ConfluenceCalculator...")
            confluence_calc = ConfluenceCalculator(bridge)
            confluence_result = confluence_calc.calculate_confluence("XAUUSDc")
            print(f"Confluence Result keys: {list(confluence_result.keys()) if confluence_result else 'None'}")
            print(f"Confluence Score: {confluence_result.get('confluence_score', 'None') if confluence_result else 'None'}")
            print(f"Confluence Grade: {confluence_result.get('grade', 'None') if confluence_result else 'None'}")
        else:
            print("ERROR No multi data available")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_analyzers_direct()
