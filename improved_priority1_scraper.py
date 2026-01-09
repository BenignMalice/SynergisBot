#!/usr/bin/env python3
"""
Improved Priority 1: Enhanced Economic Data Scraper
=================================================

This improved version adds more reliable sources and better error handling:
- TradingView Economic Calendar API
- Myfxbook Economic Calendar
- Enhanced Investing.com scraper
- Better error handling and fallbacks

Usage:
    python improved_priority1_scraper.py
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
import os
import logging
import re

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImprovedEconomicDataScraper:
    """Enhanced scraper for actual/expected economic data from multiple sources"""
    
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
        self.rate_limits = {
            'investing.com': 2,
            'tradingeconomics.com': 3,
            'tradingview.com': 2,
            'myfxbook.com': 3
        }
    
    def scrape_tradingview_calendar(self):
        """Scrape TradingView economic calendar using their API"""
        try:
            logger.info("Scraping TradingView economic calendar...")
            
            # Correct TradingView API endpoint
            url = "https://economic-calendar.tradingview.com/events"
            
            # Get current date range
            today = datetime.now()
            start_date = today.strftime('%Y-%m-%dT00:00:00.000Z')
            end_date = (today + timedelta(days=7)).strftime('%Y-%m-%dT00:00:00.000Z')
            
            headers = {
                'Origin': 'https://in.tradingview.com',
                'Referer': 'https://in.tradingview.com/',
                'Accept': 'application/json, text/plain, */*'
            }
            
            params = {
                'from': start_date,
                'to': end_date,
                'countries': 'US,GB,EU,JP,CA,AU,NZ'
            }
            
            response = self.session.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            events = []
            
            if 'result' in data:
                for event_data in data['result']:
                    try:
                        event = {
                            'time': self._parse_tradingview_time(event_data.get('time')),
                            'country': event_data.get('country', ''),
                            'event': event_data.get('title', ''),
                            'actual': self._parse_value(event_data.get('actual')),
                            'forecast': self._parse_value(event_data.get('forecast')),
                            'previous': self._parse_value(event_data.get('previous')),
                            'impact': self._parse_tradingview_impact(event_data.get('importance')),
                            'source': 'tradingview.com',
                            'scraped_at': datetime.now().isoformat()
                        }
                        
                        if event['actual'] and event['forecast']:
                            events.append(event)
                            
                    except Exception as e:
                        logger.debug(f"Error parsing TradingView event: {e}")
                        continue
            
            logger.info(f"SUCCESS: Scraped {len(events)} events from TradingView")
            return events
            
        except Exception as e:
            logger.error(f"ERROR: Error scraping TradingView: {e}")
            return []
    
    def scrape_forexfactory_rss(self):
        """Scrape ForexFactory using RSS feed (more reliable)"""
        try:
            logger.info("Scraping ForexFactory RSS feed...")
            url = "https://www.forexfactory.com/rss.php"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            events = []
            
            # Parse RSS items
            items = soup.find_all('item')
            
            for item in items:
                try:
                    title = item.find('title').text.strip()
                    description = item.find('description').text.strip()
                    pub_date = item.find('pubDate').text.strip()
                    
                    # Extract economic data from description
                    actual, forecast, previous = self._extract_economic_data_from_text(description)
                    
                    if actual and forecast:
                        event = {
                            'time': self._parse_rss_time(pub_date),
                            'event': title,
                            'actual': actual,
                            'forecast': forecast,
                            'previous': previous,
                            'source': 'forexfactory.com',
                            'scraped_at': datetime.now().isoformat()
                        }
                        events.append(event)
                        
                except Exception as e:
                    logger.debug(f"Error parsing ForexFactory RSS item: {e}")
                    continue
            
            logger.info(f"SUCCESS: Scraped {len(events)} events from ForexFactory RSS")
            return events
            
        except Exception as e:
            logger.error(f"ERROR: Error scraping ForexFactory RSS: {e}")
            return []
    
    def scrape_myfxbook_calendar(self):
        """Scrape Myfxbook economic calendar"""
        try:
            logger.info("Scraping Myfxbook economic calendar...")
            url = "https://www.myfxbook.com/economic-calendar"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            events = []
            
            # Try multiple selectors for the calendar table
            selectors = [
                'table#economic-calendar-table',
                'table.table',
                'table.calendar-table',
                'table[class*="calendar"]',
                'table[class*="economic"]'
            ]
            
            calendar_table = None
            for selector in selectors:
                calendar_table = soup.select_one(selector)
                if calendar_table:
                    break
            
            if calendar_table:
                rows = calendar_table.find_all('tr')[1:]  # Skip header
                
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 6:
                        try:
                            event = {
                                'time': self._parse_time(cells[0].text.strip()),
                                'country': cells[1].text.strip(),
                                'event': cells[2].text.strip(),
                                'actual': self._parse_value(cells[3].text.strip()),
                                'forecast': self._parse_value(cells[4].text.strip()),
                                'previous': self._parse_value(cells[5].text.strip()),
                                'source': 'myfxbook.com',
                                'scraped_at': datetime.now().isoformat()
                            }
                            
                            if event['actual'] and event['forecast']:
                                events.append(event)
                                
                        except Exception as e:
                            logger.debug(f"Error parsing Myfxbook row: {e}")
                            continue
            
            logger.info(f"SUCCESS: Scraped {len(events)} events from Myfxbook")
            return events
            
        except Exception as e:
            logger.error(f"ERROR: Error scraping Myfxbook: {e}")
            return []
    
    def scrape_enhanced_investing(self):
        """Enhanced Investing.com scraper with better parsing"""
        try:
            logger.info("Scraping Investing.com economic calendar (enhanced)...")
            url = "https://www.investing.com/economic-calendar/"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            events = []
            
            # Try multiple selectors for the calendar table
            calendar_table = soup.find('table', {'id': 'economicCalendarData'})
            if not calendar_table:
                calendar_table = soup.find('table', class_='genTbl')
            if not calendar_table:
                calendar_table = soup.find('table', class_='table')
            
            if calendar_table:
                rows = calendar_table.find_all('tr')[1:]  # Skip header
                
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 8:
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
                            
                            if event['actual'] and event['forecast']:
                                events.append(event)
                                
                        except Exception as e:
                            logger.debug(f"Error parsing Investing.com row: {e}")
                            continue
            
            logger.info(f"SUCCESS: Scraped {len(events)} events from Investing.com")
            return events
            
        except Exception as e:
            logger.error(f"ERROR: Error scraping Investing.com: {e}")
            return []
    
    def scrape_alternative_tradingeconomics(self):
        """Alternative approach to TradingEconomics scraping"""
        try:
            logger.info("Scraping TradingEconomics calendar (alternative method)...")
            
            # Try different URLs
            urls = [
                "https://tradingeconomics.com/calendar",
                "https://tradingeconomics.com/calendar/this-week",
                "https://tradingeconomics.com/calendar/today"
            ]
            
            events = []
            
            for url in urls:
                try:
                    response = self.session.get(url, timeout=30)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Try multiple selectors
                    selectors = [
                        'tr.calendar-event',
                        'tr[data-event]',
                        'table tr',
                        '.calendar-table tr'
                    ]
                    
                    for selector in selectors:
                        calendar_events = soup.select(selector)
                        if calendar_events:
                            logger.info(f"DEBUG: Found {len(calendar_events)} events with selector: {selector}")
                            
                            for event_row in calendar_events:
                                cells = event_row.find_all('td')
                                if len(cells) >= 6:
                                    try:
                                        event = {
                                            'time': self._parse_time(cells[0].text.strip()),
                                            'country': cells[1].text.strip(),
                                            'event': cells[2].text.strip(),
                                            'actual': self._parse_value(cells[3].text.strip()),
                                            'forecast': self._parse_value(cells[4].text.strip()),
                                            'previous': self._parse_value(cells[5].text.strip()),
                                            'source': 'tradingeconomics.com',
                                            'scraped_at': datetime.now().isoformat()
                                        }
                                        
                                        if event['actual'] and event['forecast']:
                                            events.append(event)
                                            
                                    except Exception as e:
                                        logger.debug(f"Error parsing TradingEconomics row: {e}")
                                        continue
                            break
                    
                    if events:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error with URL {url}: {e}")
                    continue
            
            logger.info(f"SUCCESS: Scraped {len(events)} events from TradingEconomics")
            return events
            
        except Exception as e:
            logger.error(f"ERROR: Error scraping TradingEconomics: {e}")
            return []
    
    def scrape_all_improved_sources(self):
        """Scrape all improved sources and return combined data"""
        logger.info("Starting improved economic data scraping...")
        
        all_events = []
        
        # Scrape TradingView (new source)
        tradingview_events = self.scrape_tradingview_calendar()
        all_events.extend(tradingview_events)
        time.sleep(2)  # Rate limiting
        
        # Scrape ForexFactory RSS (new reliable source)
        forexfactory_events = self.scrape_forexfactory_rss()
        all_events.extend(forexfactory_events)
        time.sleep(2)  # Rate limiting
        
        # Scrape Myfxbook (new source)
        myfxbook_events = self.scrape_myfxbook_calendar()
        all_events.extend(myfxbook_events)
        time.sleep(3)  # Rate limiting
        
        # Scrape enhanced Investing.com
        investing_events = self.scrape_enhanced_investing()
        all_events.extend(investing_events)
        time.sleep(2)  # Rate limiting
        
        # Scrape alternative TradingEconomics
        trading_events = self.scrape_alternative_tradingeconomics()
        all_events.extend(trading_events)
        
        # Deduplicate events
        unique_events = self._deduplicate_events(all_events)
        
        # Calculate surprise percentages
        unique_events = self.calculate_surprise_percentage(unique_events)
        
        logger.info(f"SUCCESS: Total unique events scraped: {len(unique_events)}")
        return unique_events
    
    def _parse_tradingview_time(self, time_data):
        """Parse TradingView time data"""
        try:
            if isinstance(time_data, (int, float)):
                return datetime.fromtimestamp(time_data).isoformat() + 'Z'
            elif isinstance(time_data, str):
                return datetime.fromisoformat(time_data.replace('Z', '+00:00')).isoformat() + 'Z'
            else:
                return datetime.now().isoformat() + 'Z'
        except:
            return datetime.now().isoformat() + 'Z'
    
    def _parse_tradingview_impact(self, importance):
        """Parse TradingView importance to impact level"""
        try:
            importance = int(importance)
            if importance >= 3:
                return 'high'
            elif importance >= 2:
                return 'medium'
            else:
                return 'low'
        except:
            return 'medium'
    
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
    
    def _deduplicate_events(self, events):
        """Remove duplicate events based on time and event name"""
        unique_events = {}
        
        for event in events:
            key = f"{event['time']}_{event['event']}"
            
            if key not in unique_events:
                unique_events[key] = event
            else:
                existing = unique_events[key]
                
                if not existing.get('actual') and event.get('actual'):
                    existing['actual'] = event['actual']
                if not existing.get('forecast') and event.get('forecast'):
                    existing['forecast'] = event['forecast']
                if not existing.get('previous') and event.get('previous'):
                    existing['previous'] = event['previous']
                
                existing['source'] = f"{existing['source']}, {event['source']}"
        
        return list(unique_events.values())
    
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
    
    def _extract_economic_data_from_text(self, text):
        """Extract actual/forecast/previous data from text description"""
        try:
            # Look for patterns like "Actual: 1.5, Forecast: 1.2, Previous: 1.0"
            actual = None
            forecast = None
            previous = None
            
            # Try to find actual value
            actual_match = re.search(r'Actual[:\s]+([+-]?\d+\.?\d*)', text, re.IGNORECASE)
            if actual_match:
                actual = float(actual_match.group(1))
            
            # Try to find forecast value
            forecast_match = re.search(r'Forecast[:\s]+([+-]?\d+\.?\d*)', text, re.IGNORECASE)
            if forecast_match:
                forecast = float(forecast_match.group(1))
            
            # Try to find previous value
            previous_match = re.search(r'Previous[:\s]+([+-]?\d+\.?\d*)', text, re.IGNORECASE)
            if previous_match:
                previous = float(previous_match.group(1))
            
            return actual, forecast, previous
            
        except Exception as e:
            logger.debug(f"Error extracting economic data from text: {e}")
            return None, None, None
    
    def _parse_rss_time(self, pub_date):
        """Parse RSS pubDate to ISO format"""
        try:
            # Parse RSS date format: "Wed, 15 Oct 2025 08:30:00 GMT"
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(pub_date)
            return dt.isoformat() + 'Z'
        except:
            return datetime.now().isoformat() + 'Z'

def main():
    """Main function to run the improved scraper"""
    logger.info("Starting Improved Priority 1: Enhanced Economic Data Scraper")
    
    # Initialize improved scraper
    scraper = ImprovedEconomicDataScraper()
    
    # Scrape all improved sources
    events = scraper.scrape_all_improved_sources()
    
    # Save to file
    output_file = 'data/improved_scraped_economic_data.json'
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
    
    logger.info("SUCCESS: Improved Priority 1 implementation completed!")
    logger.info("Next steps:")
    logger.info("  1. Review improved scraped data in data/improved_scraped_economic_data.json")
    logger.info("  2. Compare with original scraper results")
    logger.info("  3. Integrate with existing news system")
    logger.info("  4. Set up automation with Windows Task Scheduler")

if __name__ == "__main__":
    main()
