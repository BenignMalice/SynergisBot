#!/usr/bin/env python3
"""
Test Script for Priority 1: Actual/Expected Data Scraper
=======================================================

This script tests the economic data scraper implementation.
Run this to verify the scraper is working correctly.

Usage:
    python test_priority1_scraper.py
"""

import sys
import os
import json
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_scraper():
    """Test the economic data scraper"""
    print("Testing Priority 1: Actual/Expected Data Scraper")
    print("=" * 60)
    
    try:
        # Import the scraper
        from start_priority1_implementation import EconomicDataScraper
        
        print("SUCCESS: Successfully imported EconomicDataScraper")
        
        # Initialize scraper
        scraper = EconomicDataScraper()
        print("SUCCESS: Successfully initialized scraper")
        
        # Test individual sources
        print("\nTesting individual sources...")
        
        # Test Investing.com
        print("  Testing Investing.com...")
        investing_events = scraper.scrape_investing_calendar()
        print(f"    SUCCESS: Scraped {len(investing_events)} events from Investing.com")
        
        # Test TradingEconomics
        print("  Testing TradingEconomics...")
        trading_events = scraper.scrape_tradingeconomics()
        print(f"    SUCCESS: Scraped {len(trading_events)} events from TradingEconomics")
        
        # Test ForexFactory
        print("  Testing ForexFactory...")
        forex_events = scraper.scrape_forexfactory()
        print(f"    SUCCESS: Scraped {len(forex_events)} events from ForexFactory")
        
        # Test combined scraping
        print("\nTesting combined scraping...")
        all_events = scraper.scrape_all_sources()
        print(f"    SUCCESS: Total unique events: {len(all_events)}")
        
        # Test surprise calculation
        print("\nTesting surprise calculation...")
        events_with_surprise = scraper.calculate_surprise_percentage(all_events)
        surprise_count = sum(1 for e in events_with_surprise if e.get('surprise_pct') is not None)
        print(f"    SUCCESS: Calculated surprise for {surprise_count} events")
        
        # Display sample results
        if all_events:
            print("\nSample Results:")
            print("-" * 40)
            
            for i, event in enumerate(all_events[:5]):  # Show first 5 events
                print(f"  {i+1}. {event['event']}")
                print(f"     Time: {event['time']}")
                print(f"     Actual: {event.get('actual', 'N/A')}")
                print(f"     Forecast: {event.get('forecast', 'N/A')}")
                print(f"     Previous: {event.get('previous', 'N/A')}")
                print(f"     Surprise: {event.get('surprise_pct', 0)}%")
                print(f"     Source: {event['source']}")
                print()
        
        # Test data quality
        print("Data Quality Analysis:")
        print("-" * 40)
        
        total_events = len(all_events)
        events_with_actual = sum(1 for e in all_events if e.get('actual'))
        events_with_forecast = sum(1 for e in all_events if e.get('forecast'))
        events_with_previous = sum(1 for e in all_events if e.get('previous'))
        events_with_surprise = sum(1 for e in all_events if e.get('surprise_pct') is not None)
        
        print(f"  Total Events: {total_events}")
        print(f"  Events with Actual: {events_with_actual} ({events_with_actual/total_events*100:.1f}%)")
        print(f"  Events with Forecast: {events_with_forecast} ({events_with_forecast/total_events*100:.1f}%)")
        print(f"  Events with Previous: {events_with_previous} ({events_with_previous/total_events*100:.1f}%)")
        print(f"  Events with Surprise: {events_with_surprise} ({events_with_surprise/total_events*100:.1f}%)")
        
        # Test file saving
        print("\nTesting file saving...")
        output_file = 'data/test_scraped_data.json'
        os.makedirs('data', exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(all_events, f, indent=2)
        
        print(f"    SUCCESS: Saved test data to {output_file}")
        
        # Overall assessment
        print("\nOverall Assessment:")
        print("-" * 40)
        
        if total_events > 0:
            print("SUCCESS: Scraper is working correctly!")
            print(f"SUCCESS: Successfully scraped {total_events} economic events")
            print(f"SUCCESS: Data quality: {events_with_actual/total_events*100:.1f}% have actual data")
            print("SUCCESS: Ready for integration with news system")
        else:
            print("WARNING: No events scraped - check network connection and source availability")
        
        return True
        
    except ImportError as e:
        print(f"ERROR: Import error: {e}")
        print("   Make sure start_priority1_implementation.py is in the same directory")
        return False
        
    except Exception as e:
        print(f"ERROR: Error during testing: {e}")
        return False

def main():
    """Main test function"""
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = test_scraper()
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success:
        print("\nSUCCESS: Priority 1 scraper test PASSED!")
        print("   Ready to proceed with integration")
    else:
        print("\nERROR: Priority 1 scraper test FAILED!")
        print("   Check error messages above")
    
    return success

if __name__ == "__main__":
    main()
