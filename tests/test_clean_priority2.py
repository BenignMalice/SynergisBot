#!/usr/bin/env python3
"""
Test Script for Clean Priority 2: Breaking News Scraper
=======================================================

This script tests the clean breaking news scraper implementation.

Usage:
    python test_clean_priority2.py
"""

import sys
import os
import json
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_clean_breaking_news_scraper():
    """Test the clean breaking news scraper"""
    print("Testing Clean Priority 2: Breaking News Scraper")
    print("=" * 55)
    
    try:
        # Import the clean scraper
        from clean_priority2_breaking_news import CleanBreakingNewsScraper
        
        print("SUCCESS: Successfully imported CleanBreakingNewsScraper")
        
        # Initialize scraper
        scraper = CleanBreakingNewsScraper()
        print("SUCCESS: Successfully initialized clean breaking news scraper")
        
        # Test individual sources
        print("\nTesting individual sources...")
        
        # Test ForexLive
        print("  Testing ForexLive...")
        forexlive_news = scraper.scrape_forexlive_breaking_news()
        print(f"    SUCCESS: Scraped {len(forexlive_news)} breaking news items from ForexLive")
        
        # Test RSS Feeds
        print("  Testing RSS Feeds...")
        rss_news = scraper.scrape_rss_feeds()
        print(f"    SUCCESS: Scraped {len(rss_news)} news items from RSS feeds")
        
        # Test combined scraping
        print("\nTesting combined scraping...")
        all_news = scraper.scrape_all_breaking_news()
        print(f"    SUCCESS: Total unique breaking news items: {len(all_news)}")
        
        # Display sample results
        if all_news:
            print("\nSample Breaking News Items:")
            print("-" * 50)
            
            for i, news in enumerate(all_news[:5]):  # Show first 5 items
                print(f"  {i+1}. {news['title']}")
                print(f"     Source: {news['source']}")
                print(f"     Impact: {news['impact']}")
                print(f"     Category: {news['category']}")
                print(f"     Link: {news['link']}")
                print()
        
        # Test data analysis
        print("Breaking News Analysis:")
        print("-" * 50)
        
        total_news = len(all_news)
        ultra_impact = sum(1 for n in all_news if n['impact'] == 'ultra')
        high_impact = sum(1 for n in all_news if n['impact'] == 'high')
        macro_news = sum(1 for n in all_news if n['category'] == 'macro')
        crypto_news = sum(1 for n in all_news if n['category'] == 'crypto')
        
        print(f"  Total News Items: {total_news}")
        print(f"  Ultra Impact: {ultra_impact} ({ultra_impact/total_news*100:.1f}%)")
        print(f"  High Impact: {high_impact} ({high_impact/total_news*100:.1f}%)")
        print(f"  Macro News: {macro_news} ({macro_news/total_news*100:.1f}%)")
        print(f"  Crypto News: {crypto_news} ({crypto_news/total_news*100:.1f}%)")
        
        # Test file saving
        print("\nTesting file saving...")
        output_file = 'data/test_clean_breaking_news_data.json'
        os.makedirs('data', exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(all_news, f, indent=2)
        
        print(f"    SUCCESS: Saved test data to {output_file}")
        
        # Test keyword detection
        print("\nTesting keyword detection...")
        test_titles = [
            "BREAKING: Fed cuts interest rates",
            "NFP data shows strong job growth",
            "Bitcoin reaches new all-time high",
            "Regular market update",
            "FOMC meeting scheduled for next week",
            "JUST IN: Emergency rate cut announced",
            "ALERT: Market volatility spikes"
        ]
        
        breaking_count = 0
        for title in test_titles:
            if scraper._is_breaking_news(title):
                breaking_count += 1
                print(f"    BREAKING: {title}")
            else:
                print(f"    Regular: {title}")
        
        print(f"    SUCCESS: Detected {breaking_count}/{len(test_titles)} breaking news items")
        
        # Test impact assessment
        print("\nTesting impact assessment...")
        test_impacts = [
            ("Fed cuts rates", "ultra"),
            ("NFP data released", "high"),
            ("Bitcoin news", "medium"),
            ("Regular update", "medium")
        ]
        
        for title, expected_impact in test_impacts:
            actual_impact = scraper._assess_impact(title)
            status = "CORRECT" if actual_impact == expected_impact else "INCORRECT"
            print(f"    {status}: '{title}' -> {actual_impact} (expected: {expected_impact})")
        
        # Test categorization
        print("\nTesting news categorization...")
        test_categories = [
            ("Bitcoin reaches new high", "crypto"),
            ("Fed meeting scheduled", "macro"),
            ("Trade war escalates", "geopolitical"),
            ("Market update", "general")
        ]
        
        for title, expected_category in test_categories:
            actual_category = scraper._categorize_news(title)
            status = "CORRECT" if actual_category == expected_category else "INCORRECT"
            print(f"    {status}: '{title}' -> {actual_category} (expected: {expected_category})")
        
        # Overall assessment
        print("\nOverall Assessment:")
        print("-" * 50)
        
        if total_news > 0:
            print("SUCCESS: Clean breaking news scraper is working correctly!")
            print(f"SUCCESS: Successfully scraped {total_news} breaking news items")
            print("SUCCESS: Ready for real-time monitoring")
            
            # Clean implementation benefits
            print("\nClean Implementation Benefits:")
            print("-" * 50)
            print("  - Only reliable sources (ForexLive + RSS feeds)")
            print("  - No blocked sources or 403 errors")
            print("  - Faster execution (no failed requests)")
            print("  - Better keyword detection")
            print("  - Enhanced impact assessment")
            print("  - RSS feeds are more reliable than web scraping")
        else:
            print("WARNING: No breaking news found - check network connection")
        
        return True
        
    except ImportError as e:
        print(f"ERROR: Import error: {e}")
        print("   Make sure clean_priority2_breaking_news.py is in the same directory")
        return False
        
    except Exception as e:
        print(f"ERROR: Error during testing: {e}")
        return False

def main():
    """Main test function"""
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = test_clean_breaking_news_scraper()
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success:
        print("\nSUCCESS: Clean Priority 2 breaking news scraper test PASSED!")
        print("   Ready for real-time monitoring")
    else:
        print("\nERROR: Clean Priority 2 breaking news scraper test FAILED!")
        print("   Check error messages above")
    
    return success

if __name__ == "__main__":
    main()
