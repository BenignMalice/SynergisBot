#!/usr/bin/env python3
"""
Clean Priority 1: Reliable Economic Data Scraper
===============================================

This clean version only includes working sources:
- Investing.com (reliable, consistent)
- Enhanced error handling
- No blocked sources

Usage:
    python clean_priority1_scraper.py
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CleanEconomicDataScraper:
    """Clean scraper for actual/expected economic data from reliable sources only"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.rate_limit = 2  # seconds between requests
    
    def scrape_investing_calendar(self):
        """Scrape Investing.com economic calendar for actual/expected data"""
        try:
            logger.info("Scraping Investing.com economic calendar...")
            url = "https://www.investing.com/economic-calendar/"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            events = []
            
            # Try multiple selectors for the calendar table
            selectors = [
                'table#economicCalendarData',
                'table.genTbl',
                'table.table',
                'table[class*="calendar"]'
            ]
            
            calendar_table = None
            for selector in selectors:
                calendar_table = soup.select_one(selector)
                if calendar_table:
                    logger.info(f"Found calendar table with selector: {selector}")
                    break
            
            if not calendar_table:
                logger.warning("WARNING: Could not find economic calendar table on Investing.com")
                return events
            
            # Parse table rows
            rows = calendar_table.find_all('tr')[1:]  # Skip header row
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 8:  # Ensure we have enough columns
                    try:
                        event = {
                            'time': self._parse_time(cells[0].text.strip()),
                            'currency': cells[1].text.strip(),
                            'impact': self._parse_impact(cells[2]),
                            'event': cells[3].text.strip(),
                            'actual': self._parse_value(cells[4].text.strip()),
                            'forecast': self._parse_value(cells[5].text.strip()),
                            'previous': self._parse_value(cells[6].text.strip()),
                            'source': 'investing.com',
                            'scraped_at': datetime.now().isoformat()
                        }
                        
                        # Only include events with actual data
                        if event['actual'] and event['forecast']:
                            events.append(event)
                            
                    except Exception as e:
                        logger.debug(f"Error parsing row: {e}")
                        continue
            
            logger.info(f"SUCCESS: Scraped {len(events)} events from Investing.com")
            return events
            
        except Exception as e:
            logger.error(f"ERROR: Error scraping Investing.com: {e}")
            return []
    
    def scrape_all_sources(self):
        """Scrape all reliable sources and return combined data"""
        logger.info("Starting clean economic data scraping...")
        
        all_events = []
        
        # Scrape Investing.com (only reliable source)
        investing_events = self.scrape_investing_calendar()
        all_events.extend(investing_events)
        
        # Calculate surprise percentages
        all_events = self.calculate_surprise_percentage(all_events)
        
        logger.info(f"SUCCESS: Total events scraped: {len(all_events)}")
        return all_events
    
    def _parse_time(self, time_str):
        """Parse time string to ISO format"""
        try:
            if 'T' in time_str:
                return time_str
            else:
                dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                return dt.isoformat() + 'Z'
        except:
            return datetime.now().isoformat() + 'Z'
    
    def _parse_impact(self, impact_cell):
        """Parse impact level from HTML cell"""
        try:
            if impact_cell.find('span', class_='high'):
                return 'high'
            elif impact_cell.find('span', class_='medium'):
                return 'medium'
            elif impact_cell.find('span', class_='low'):
                return 'low'
            else:
                return 'medium'
        except:
            return 'medium'
    
    def _parse_value(self, value_str):
        """Parse actual/forecast/previous values"""
        if not value_str or value_str.strip() == '' or value_str.strip() == '-':
            return None
        
        try:
            cleaned = value_str.strip().replace(',', '').replace('%', '')
            
            if cleaned == 'N/A' or cleaned == '--':
                return None
            
            return float(cleaned)
        except:
            return None
    
    def calculate_surprise_percentage(self, events):
        """Calculate surprise percentage for events with actual/forecast data"""
        for event in events:
            if event.get('actual') and event.get('forecast'):
                try:
                    actual = float(event['actual'])
                    forecast = float(event['forecast'])
                    
                    if forecast != 0:
                        surprise_pct = ((actual - forecast) / abs(forecast)) * 100
                        event['surprise_pct'] = round(surprise_pct, 2)
                    else:
                        event['surprise_pct'] = 0
                except:
                    event['surprise_pct'] = 0
        
        return events

def main():
    """Main function to run the clean scraper"""
    logger.info("Starting Clean Priority 1: Reliable Economic Data Scraper")
    
    # Initialize clean scraper
    scraper = CleanEconomicDataScraper()
    
    # Scrape reliable sources
    events = scraper.scrape_all_sources()
    
    # Save to file
    output_file = 'data/clean_scraped_economic_data.json'
    os.makedirs('data', exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(events, f, indent=2)
    
    logger.info(f"SUCCESS: Saved {len(events)} events to {output_file}")
    
    # Display sample results
    if events:
        logger.info("Sample scraped events:")
        for i, event in enumerate(events[:5]):  # Show first 5 events
            logger.info(f"  {i+1}. {event['event']} - Actual: {event.get('actual')}, Forecast: {event.get('forecast')}, Surprise: {event.get('surprise_pct', 0)}%")
    
    # Data quality analysis
    total_events = len(events)
    events_with_actual = sum(1 for e in events if e.get('actual'))
    events_with_forecast = sum(1 for e in events if e.get('forecast'))
    events_with_previous = sum(1 for e in events if e.get('previous'))
    events_with_surprise = sum(1 for e in events if e.get('surprise_pct') is not None)
    
    logger.info("Data Quality Analysis:")
    logger.info(f"  Total Events: {total_events}")
    logger.info(f"  Events with Actual: {events_with_actual} ({events_with_actual/total_events*100:.1f}%)")
    logger.info(f"  Events with Forecast: {events_with_forecast} ({events_with_forecast/total_events*100:.1f}%)")
    logger.info(f"  Events with Previous: {events_with_previous} ({events_with_previous/total_events*100:.1f}%)")
    logger.info(f"  Events with Surprise: {events_with_surprise} ({events_with_surprise/total_events*100:.1f}%)")
    
    logger.info("SUCCESS: Clean Priority 1 implementation completed!")
    logger.info("Next steps:")
    logger.info("  1. Review clean scraped data in data/clean_scraped_economic_data.json")
    logger.info("  2. Integrate with existing news system")
    logger.info("  3. Set up automation with Windows Task Scheduler")
    logger.info("  4. Move to Priority 2: Breaking News Scraper")

if __name__ == "__main__":
    main()
