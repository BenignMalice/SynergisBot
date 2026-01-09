#!/usr/bin/env python3
"""
Test Script for Priority 2: Breaking News Scraper
================================================

This script tests the breaking news scraper implementation.

Usage:
    python test_priority2_breaking_news.py
"""

import sys
import os
import json
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_breaking_news_scraper():
    """Test the breaking news scraper"""
    print("Testing Priority 2: Breaking News Scraper")
    print("=" * 50)
    
    try:
        # Import the scraper
        from priority2_breaking_news_scraper import BreakingNewsScraper
        
        print("SUCCESS: Successfully imported BreakingNewsScraper")
        
        # Initialize scraper
        scraper = BreakingNewsScraper()
        print("SUCCESS: Successfully initialized breaking news scraper")
        
        # Test individual sources
        print("\nTesting individual sources...")
        
        # Test ForexLive
        print("  Testing ForexLive...")
        forexlive_news = scraper.scrape_forexlive_breaking_news()
        print(f"    SUCCESS: Scraped {len(forexlive_news)} breaking news items from ForexLive")
        
        # Test Alternative Sources
        print("  Testing Alternative Sources...")
        alternative_news = scraper.scrape_alternative_news_sources()
        print(f"    SUCCESS: Scraped {len(alternative_news)} news items from alternative sources")
        
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
        output_file = 'data/test_breaking_news_data.json'
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
            "FOMC meeting scheduled for next week"
        ]
        
        breaking_count = 0
        for title in test_titles:
            if scraper._is_breaking_news(title):
                breaking_count += 1
                print(f"    BREAKING: {title}")
            else:
                print(f"    Regular: {title}")
        
        print(f"    SUCCESS: Detected {breaking_count}/{len(test_titles)} breaking news items")
        
        # Overall assessment
        print("\nOverall Assessment:")
        print("-" * 50)
        
        if total_news > 0:
            print("SUCCESS: Breaking news scraper is working correctly!")
            print(f"SUCCESS: Successfully scraped {total_news} breaking news items")
            print("SUCCESS: Ready for real-time monitoring")
            
            # Priority 2 benefits
            print("\nPriority 2 Benefits:")
            print("-" * 50)
            print("  - Real-time breaking news detection")
            print("  - Multiple source redundancy")
            print("  - Impact assessment (ultra/high/medium)")
            print("  - News categorization (macro/crypto/geopolitical)")
            print("  - Keyword-based filtering")
        else:
            print("WARNING: No breaking news found - check network connection")
        
        return True
        
    except ImportError as e:
        print(f"ERROR: Import error: {e}")
        print("   Make sure priority2_breaking_news_scraper.py is in the same directory")
        return False
        
    except Exception as e:
        print(f"ERROR: Error during testing: {e}")
        return False

def main():
    """Main test function"""
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = test_breaking_news_scraper()
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success:
        print("\nSUCCESS: Priority 2 breaking news scraper test PASSED!")
        print("   Ready for real-time monitoring")
    else:
        print("\nERROR: Priority 2 breaking news scraper test FAILED!")
        print("   Check error messages above")
    
    return success

if __name__ == "__main__":
    main()
