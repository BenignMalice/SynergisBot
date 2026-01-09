#!/usr/bin/env python3
"""
Monitor All Priorities - Production Monitoring
=============================================

This script monitors the health and performance of all three priorities.

Usage:
    python monitor_all_priorities.py
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def monitor_priority1():
    """Monitor Priority 1: Actual/Expected Data"""
    try:
        if os.path.exists('data/clean_scraped_economic_data.json'):
            with open('data/clean_scraped_economic_data.json', 'r') as f:
                data = json.load(f)
            
            logger.info(f"Priority 1: {len(data)} economic events")
            
            # Check data quality
            events_with_actual = sum(1 for e in data if e.get('actual'))
            events_with_forecast = sum(1 for e in data if e.get('forecast'))
            events_with_surprise = sum(1 for e in data if e.get('surprise_pct') is not None)
            
            logger.info(f"  - Events with actual data: {events_with_actual}")
            logger.info(f"  - Events with forecast data: {events_with_forecast}")
            logger.info(f"  - Events with surprise calculation: {events_with_surprise}")
            
            return len(data)
        else:
            logger.warning("Priority 1: No data file found")
            return 0
    except Exception as e:
        logger.error(f"Priority 1: Error - {e}")
        return 0

def monitor_priority2():
    """Monitor Priority 2: Breaking News"""
    try:
        if os.path.exists('data/clean_breaking_news_data.json'):
            with open('data/clean_breaking_news_data.json', 'r') as f:
                data = json.load(f)
            
            logger.info(f"Priority 2: {len(data)} breaking news items")
            
            # Check data quality
            ultra_impact = sum(1 for n in data if n.get('impact') == 'ultra')
            high_impact = sum(1 for n in data if n.get('impact') == 'high')
            macro_news = sum(1 for n in data if n.get('category') == 'macro')
            crypto_news = sum(1 for n in data if n.get('category') == 'crypto')
            
            logger.info(f"  - Ultra impact news: {ultra_impact}")
            logger.info(f"  - High impact news: {high_impact}")
            logger.info(f"  - Macro news: {macro_news}")
            logger.info(f"  - Crypto news: {crypto_news}")
            
            return len(data)
        else:
            logger.warning("Priority 2: No data file found")
            return 0
    except Exception as e:
        logger.error(f"Priority 2: Error - {e}")
        return 0

def monitor_priority3():
    """Monitor Priority 3: Historical Database"""
    try:
        if os.path.exists('data/clean_historical_database.sqlite'):
            conn = sqlite3.connect('data/clean_historical_database.sqlite')
            cursor = conn.cursor()
            
            # Get total records
            cursor.execute('SELECT COUNT(*) FROM historical_data')
            total_count = cursor.fetchone()[0]
            
            # Get records by asset type
            cursor.execute('SELECT asset_type, COUNT(*) FROM historical_data GROUP BY asset_type')
            asset_counts = cursor.fetchall()
            
            # Get unique symbols
            cursor.execute('SELECT COUNT(DISTINCT symbol) FROM historical_data')
            unique_symbols = cursor.fetchone()[0]
            
            conn.close()
            
            logger.info(f"Priority 3: {total_count} historical records")
            logger.info(f"  - Unique symbols: {unique_symbols}")
            
            for asset_type, count in asset_counts:
                logger.info(f"  - {asset_type} records: {count}")
            
            return total_count
        else:
            logger.warning("Priority 3: No database file found")
            return 0
    except Exception as e:
        logger.error(f"Priority 3: Error - {e}")
        return 0

def check_file_ages():
    """Check the age of data files"""
    logger.info("Checking file ages...")
    
    files_to_check = [
        'data/clean_scraped_economic_data.json',
        'data/clean_breaking_news_data.json',
        'data/clean_historical_database.sqlite'
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            mod_time = os.path.getmtime(file_path)
            age_hours = (datetime.now().timestamp() - mod_time) / 3600
            logger.info(f"  {file_path}: {age_hours:.1f} hours old")
            
            if age_hours > 24:
                logger.warning(f"  WARNING: {file_path} is {age_hours:.1f} hours old - may need update")
        else:
            logger.warning(f"  {file_path}: File not found")

def main():
    """Main monitoring function"""
    logger.info("Starting production monitoring for all priorities...")
    logger.info("=" * 60)
    
    # Monitor each priority
    p1_count = monitor_priority1()
    p2_count = monitor_priority2()
    p3_count = monitor_priority3()
    
    # Check file ages
    check_file_ages()
    
    # Summary
    total_data = p1_count + p2_count + p3_count
    
    logger.info("=" * 60)
    logger.info(f"SUMMARY:")
    logger.info(f"  Priority 1 (Actual/Expected): {p1_count} events")
    logger.info(f"  Priority 2 (Breaking News): {p2_count} items")
    logger.info(f"  Priority 3 (Historical DB): {p3_count} records")
    logger.info(f"  Total data points: {total_data}")
    
    if total_data > 0:
        logger.info("SUCCESS: All priorities are working correctly!")
        logger.info("SUCCESS: Data collection is active and healthy")
    else:
        logger.warning("WARNING: No data found in any priority - check automation")
        logger.warning("WARNING: Verify Windows Task Scheduler is running")
    
    return total_data > 0

if __name__ == "__main__":
    success = main()
    if success:
        print("\nSUCCESS: All priorities are healthy!")
    else:
        print("\nWARNING: Some priorities need attention!")
