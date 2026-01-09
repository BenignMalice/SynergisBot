#!/usr/bin/env python3
"""
Clean Priority 2: Breaking News Scraper
=======================================

This clean version focuses on working sources:
- ForexLive.com (primary source - working)
- RSS feeds (more reliable than web scraping)
- Enhanced keyword detection

Usage:
    python clean_priority2_breaking_news.py
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
import os
import logging
import re
from typing import List, Dict, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CleanBreakingNewsScraper:
    """Clean scraper for breaking news from reliable sources only"""
    
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
        
        # Enhanced breaking news keywords
        self.breaking_keywords = [
            'BREAKING', 'FED', 'POWELL', 'NFP', 'CPI', 'FOMC',
            'EMERGENCY', 'RATE CUT', 'RATE HIKE', 'QUANTITATIVE EASING',
            'CRYPTO', 'BITCOIN', 'ETF', 'SEC', 'REGULATION',
            'WAR', 'SANCTIONS', 'TRADE WAR', 'TARIFFS',
            'UNEMPLOYMENT', 'GDP', 'INFLATION', 'RECESSION',
            'ALERT', 'URGENT', 'JUST IN', 'LIVE'
        ]
    
    def scrape_forexlive_breaking_news(self):
        """Scrape ForexLive for breaking news"""
        try:
            logger.info("Scraping ForexLive breaking news...")
            url = "https://www.forexlive.com/"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            breaking_news = []
            
            # Try multiple selectors for news articles
            selectors = [
                'article.post',
                'div.post',
                'div.news-item',
                'div[class*="news"]',
                'div[class*="post"]',
                'div[class*="article"]'
            ]
            
            articles = []
            for selector in selectors:
                articles = soup.select(selector)
                if articles:
                    logger.info(f"Found {len(articles)} articles with selector: {selector}")
                    break
            
            for article in articles:
                try:
                    # Extract title
                    title_elem = article.find(['h1', 'h2', 'h3', 'h4'], class_=['title', 'headline', 'post-title'])
                    if not title_elem:
                        title_elem = article.find('a', class_=['title', 'headline'])
                    if not title_elem:
                        title_elem = article.find(['h1', 'h2', 'h3', 'h4'])
                    
                    if title_elem:
                        title = title_elem.get_text().strip()
                        
                        # Check for breaking news keywords
                        if self._is_breaking_news(title):
                            # Extract additional info
                            link = self._extract_link(article)
                            timestamp = self._extract_timestamp(article)
                            description = self._extract_description(article)
                            
                            news_item = {
                                'title': title,
                                'link': link,
                                'timestamp': timestamp,
                                'description': description,
                                'source': 'forexlive.com',
                                'impact': self._assess_impact(title),
                                'category': self._categorize_news(title),
                                'scraped_at': datetime.now().isoformat()
                            }
                            breaking_news.append(news_item)
                            
                except Exception as e:
                    logger.debug(f"Error parsing ForexLive article: {e}")
                    continue
            
            logger.info(f"SUCCESS: Scraped {len(breaking_news)} breaking news items from ForexLive")
            return breaking_news
            
        except Exception as e:
            logger.error(f"ERROR: Error scraping ForexLive: {e}")
            return []
    
    def scrape_rss_feeds(self):
        """Scrape RSS feeds for breaking news"""
        try:
            logger.info("Scraping RSS feeds for breaking news...")
            rss_sources = [
                self._scrape_forexfactory_rss(),
                self._scrape_investing_rss(),
                self._scrape_marketwatch_rss()
            ]
            
            all_news = []
            for source_news in rss_sources:
                all_news.extend(source_news)
            
            logger.info(f"SUCCESS: Scraped {len(all_news)} news items from RSS feeds")
            return all_news
            
        except Exception as e:
            logger.error(f"ERROR: Error scraping RSS feeds: {e}")
            return []
    
    def _scrape_forexfactory_rss(self):
        """Scrape ForexFactory RSS feed"""
        try:
            url = "https://www.forexfactory.com/rss.php"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            news_items = []
            
            # Parse RSS items
            items = soup.find_all('item')
            
            for item in items:
                try:
                    title = item.find('title').text.strip()
                    description = item.find('description').text.strip()
                    pub_date = item.find('pubDate').text.strip()
                    link = item.find('link').text.strip()
                    
                    if self._is_breaking_news(title):
                        news_item = {
                            'title': title,
                            'link': link,
                            'timestamp': self._parse_rss_time(pub_date),
                            'description': description,
                            'source': 'forexfactory.com',
                            'impact': self._assess_impact(title),
                            'category': self._categorize_news(title),
                            'scraped_at': datetime.now().isoformat()
                        }
                        news_items.append(news_item)
                        
                except Exception as e:
                    logger.debug(f"Error parsing ForexFactory RSS item: {e}")
                    continue
            
            return news_items
            
        except Exception as e:
            logger.error(f"ERROR: Error scraping ForexFactory RSS: {e}")
            return []
    
    def _scrape_investing_rss(self):
        """Scrape Investing.com RSS feed"""
        try:
            url = "https://www.investing.com/rss/news.rss"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            news_items = []
            
            # Parse RSS items
            items = soup.find_all('item')
            
            for item in items:
                try:
                    title = item.find('title').text.strip()
                    description = item.find('description').text.strip()
                    pub_date = item.find('pubDate').text.strip()
                    link = item.find('link').text.strip()
                    
                    if self._is_breaking_news(title):
                        news_item = {
                            'title': title,
                            'link': link,
                            'timestamp': self._parse_rss_time(pub_date),
                            'description': description,
                            'source': 'investing.com',
                            'impact': self._assess_impact(title),
                            'category': self._categorize_news(title),
                            'scraped_at': datetime.now().isoformat()
                        }
                        news_items.append(news_item)
                        
                except Exception as e:
                    logger.debug(f"Error parsing Investing.com RSS item: {e}")
                    continue
            
            return news_items
            
        except Exception as e:
            logger.error(f"ERROR: Error scraping Investing.com RSS: {e}")
            return []
    
    def _scrape_marketwatch_rss(self):
        """Scrape MarketWatch RSS feed"""
        try:
            url = "https://feeds.marketwatch.com/marketwatch/marketpulse/"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            news_items = []
            
            # Parse RSS items
            items = soup.find_all('item')
            
            for item in items:
                try:
                    title = item.find('title').text.strip()
                    description = item.find('description').text.strip()
                    pub_date = item.find('pubDate').text.strip()
                    link = item.find('link').text.strip()
                    
                    if self._is_breaking_news(title):
                        news_item = {
                            'title': title,
                            'link': link,
                            'timestamp': self._parse_rss_time(pub_date),
                            'description': description,
                            'source': 'marketwatch.com',
                            'impact': self._assess_impact(title),
                            'category': self._categorize_news(title),
                            'scraped_at': datetime.now().isoformat()
                        }
                        news_items.append(news_item)
                        
                except Exception as e:
                    logger.debug(f"Error parsing MarketWatch RSS item: {e}")
                    continue
            
            return news_items
            
        except Exception as e:
            logger.error(f"ERROR: Error scraping MarketWatch RSS: {e}")
            return []
    
    def scrape_all_breaking_news(self):
        """Scrape all sources for breaking news"""
        logger.info("Starting clean breaking news scraping...")
        
        all_news = []
        
        # Scrape ForexLive (primary source)
        forexlive_news = self.scrape_forexlive_breaking_news()
        all_news.extend(forexlive_news)
        time.sleep(self.rate_limit)
        
        # Scrape RSS feeds
        rss_news = self.scrape_rss_feeds()
        all_news.extend(rss_news)
        
        # Deduplicate news items
        unique_news = self._deduplicate_news(all_news)
        
        logger.info(f"SUCCESS: Total unique breaking news items: {len(unique_news)}")
        return unique_news
    
    def _is_breaking_news(self, title):
        """Check if title contains breaking news keywords"""
        title_upper = title.upper()
        return any(keyword in title_upper for keyword in self.breaking_keywords)
    
    def _assess_impact(self, title):
        """Assess impact level based on title"""
        title_upper = title.upper()
        
        if any(word in title_upper for word in ['FED', 'POWELL', 'FOMC', 'RATE']):
            return 'ultra'
        elif any(word in title_upper for word in ['NFP', 'CPI', 'GDP', 'UNEMPLOYMENT']):
            return 'high'
        elif any(word in title_upper for word in ['BREAKING', 'EMERGENCY']):
            return 'ultra'
        else:
            return 'medium'
    
    def _categorize_news(self, title):
        """Categorize news type"""
        title_upper = title.upper()
        
        if any(word in title_upper for word in ['CRYPTO', 'BITCOIN', 'CRYPTOCURRENCY']):
            return 'crypto'
        elif any(word in title_upper for word in ['FED', 'FOMC', 'RATE', 'INFLATION']):
            return 'macro'
        elif any(word in title_upper for word in ['WAR', 'SANCTIONS', 'TRADE']):
            return 'geopolitical'
        else:
            return 'general'
    
    def _extract_link(self, article):
        """Extract link from article"""
        try:
            link_elem = article.find('a')
            if link_elem:
                href = link_elem.get('href', '')
                if href.startswith('/'):
                    return f"https://www.forexlive.com{href}"
                return href
            return ''
        except:
            return ''
    
    def _extract_timestamp(self, article):
        """Extract timestamp from article"""
        try:
            time_elem = article.find(['time', 'span'], class_=['time', 'timestamp', 'date'])
            if time_elem:
                return time_elem.get_text().strip()
            return datetime.now().isoformat()
        except:
            return datetime.now().isoformat()
    
    def _extract_description(self, article):
        """Extract description from article"""
        try:
            desc_elem = article.find(['p', 'div'], class_=['description', 'excerpt', 'summary'])
            if desc_elem:
                return desc_elem.get_text().strip()
            return ''
        except:
            return ''
    
    def _parse_rss_time(self, pub_date):
        """Parse RSS pubDate to ISO format"""
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(pub_date)
            return dt.isoformat() + 'Z'
        except:
            return datetime.now().isoformat() + 'Z'
    
    def _deduplicate_news(self, news_items):
        """Remove duplicate news items based on title similarity"""
        unique_news = []
        seen_titles = set()
        
        for item in news_items:
            # Create a normalized title for comparison
            normalized_title = re.sub(r'[^\w\s]', '', item['title'].lower())
            normalized_title = ' '.join(normalized_title.split())
            
            if normalized_title not in seen_titles:
                seen_titles.add(normalized_title)
                unique_news.append(item)
        
        return unique_news

def main():
    """Main function to run the clean breaking news scraper"""
    logger.info("Starting Clean Priority 2: Breaking News Scraper")
    
    # Initialize scraper
    scraper = CleanBreakingNewsScraper()
    
    # Scrape all breaking news
    breaking_news = scraper.scrape_all_breaking_news()
    
    # Save to file
    output_file = 'data/clean_breaking_news_data.json'
    os.makedirs('data', exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(breaking_news, f, indent=2)
    
    logger.info(f"SUCCESS: Saved {len(breaking_news)} breaking news items to {output_file}")
    
    # Display sample results
    if breaking_news:
        logger.info("Sample breaking news items:")
        for i, news in enumerate(breaking_news[:5]):  # Show first 5 items
            logger.info(f"  {i+1}. {news['title']}")
            logger.info(f"     Source: {news['source']}")
            logger.info(f"     Impact: {news['impact']}")
            logger.info(f"     Category: {news['category']}")
            logger.info(f"     Link: {news['link']}")
            logger.info()
    
    # Data analysis
    total_news = len(breaking_news)
    ultra_impact = sum(1 for n in breaking_news if n['impact'] == 'ultra')
    high_impact = sum(1 for n in breaking_news if n['impact'] == 'high')
    macro_news = sum(1 for n in breaking_news if n['category'] == 'macro')
    crypto_news = sum(1 for n in breaking_news if n['category'] == 'crypto')
    
    logger.info("Breaking News Analysis:")
    logger.info(f"  Total News Items: {total_news}")
    logger.info(f"  Ultra Impact: {ultra_impact} ({ultra_impact/total_news*100:.1f}%)")
    logger.info(f"  High Impact: {high_impact} ({high_impact/total_news*100:.1f}%)")
    logger.info(f"  Macro News: {macro_news} ({macro_news/total_news*100:.1f}%)")
    logger.info(f"  Crypto News: {crypto_news} ({crypto_news/total_news*100:.1f}%)")
    
    logger.info("SUCCESS: Clean Priority 2 breaking news scraper completed!")
    logger.info("Next steps:")
    logger.info("  1. Review breaking news data in data/clean_breaking_news_data.json")
    logger.info("  2. Set up real-time monitoring")
    logger.info("  3. Integrate with news system")
    logger.info("  4. Move to Priority 3: Historical Database")

if __name__ == "__main__":
    main()
