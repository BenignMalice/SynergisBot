"""
Test script to request XAU analysis through the API and verify tick_metrics
"""
import requests
import json

def test_api_analysis():
    """Request XAU analysis through API and check for tick_metrics"""
    
    # API endpoint
    url = "http://localhost:8000/api/v1/analyse/XAUUSD/full"
    
    print("="*80)
    print("REQUESTING XAU ANALYSIS THROUGH API")
    print("="*80)
    print(f"URL: {url}\n")
    
    try:
        # Make GET request
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        print("OK: API Request Successful")
        print(f"Status Code: {response.status_code}\n")
        
        # Check tick_metrics in data object
        data = result.get("data", {})
        tick_metrics = data.get("tick_metrics")
        
        print("="*80)
        print("VERIFICATION: tick_metrics in data object")
        print("="*80)
        
        if tick_metrics is None:
            print("FAIL: tick_metrics is NULL in response.data")
            print("   The instance is not accessible through the API")
        else:
            print("PASS: tick_metrics IS PRESENT in response.data")
            metadata = tick_metrics.get("metadata", {})
            print(f"\n   Metadata:")
            print(f"   - symbol: {metadata.get('symbol')}")
            print(f"   - data_available: {metadata.get('data_available')}")
            print(f"   - market_status: {metadata.get('market_status')}")
            
            # Check M5
            m5 = tick_metrics.get("M5")
            if m5:
                print(f"\n   OK: M5 Metrics Present:")
                print(f"   - tick_count: {m5.get('tick_count', 'N/A')}")
                print(f"   - realized_volatility: {m5.get('realized_volatility', 'N/A')}")
                print(f"   - delta_volume: {m5.get('delta_volume', 'N/A')}")
                print(f"   - cvd_slope: {m5.get('cvd_slope', 'N/A')}")
        
        # Check TICK MICROSTRUCTURE in summary
        summary = result.get("summary", "")
        
        print("\n" + "="*80)
        print("VERIFICATION: TICK MICROSTRUCTURE in summary")
        print("="*80)
        
        if "TICK MICROSTRUCTURE" in summary:
            print("PASS: TICK MICROSTRUCTURE found in summary")
            # Extract the section
            lines = summary.split("\n")
            for i, line in enumerate(lines):
                if "TICK MICROSTRUCTURE" in line:
                    print(f"\n   Summary section (next 6 lines):")
                    # Print next 5 lines
                    for j in range(i, min(i+6, len(lines))):
                        print(f"   {lines[j]}")
                    break
        else:
            print("FAIL: TICK MICROSTRUCTURE NOT in summary")
            if tick_metrics:
                print("   BUT tick_metrics IS in data - formatting may have failed")
        
        # Overall result
        print("\n" + "="*80)
        print("OVERALL RESULT")
        print("="*80)
        if tick_metrics and "TICK MICROSTRUCTURE" in summary:
            print("SUCCESS: Both requirements met!")
            print("   - tick_metrics present in data object")
            print("   - TICK MICROSTRUCTURE section in summary")
        elif tick_metrics:
            print("PARTIAL: tick_metrics present but not in summary")
            print("   - Check format_tick_metrics_summary function")
        else:
            print("FAILED: tick_metrics not accessible")
            print("   - The fix needs further investigation")
        
        # Save full response to file
        output_file = "test_api_xau_response.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nFull response saved to: {output_file}")
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to API server")
        print("   Make sure the API server is running on http://localhost:8000")
        print("   Check if main_api.py is running")
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out")
        print("   The analysis is taking too long")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api_analysis()

