#!/usr/bin/env python3
"""
Health Check for All Priorities
===============================

This script performs a comprehensive health check of all three priorities.

Usage:
    python health_check.py
"""

import os
import json
import sqlite3
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_priority1_health():
    """Check Priority 1 health"""
    try:
        if os.path.exists('data/clean_scraped_economic_data.json'):
            with open('data/clean_scraped_economic_data.json', 'r') as f:
                data = json.load(f)
            
            if len(data) > 0:
                logger.info("Priority 1: HEALTHY - Data file exists and contains data")
                return True
            else:
                logger.warning("Priority 1: WARNING - Data file exists but is empty")
                return False
        else:
            logger.warning("Priority 1: UNHEALTHY - Data file not found")
            return False
    except Exception as e:
        logger.error(f"Priority 1: ERROR - {e}")
        return False

def check_priority2_health():
    """Check Priority 2 health"""
    try:
        if os.path.exists('data/clean_breaking_news_data.json'):
            with open('data/clean_breaking_news_data.json', 'r') as f:
                data = json.load(f)
            
            if len(data) > 0:
                logger.info("Priority 2: HEALTHY - Data file exists and contains data")
                return True
            else:
                logger.warning("Priority 2: WARNING - Data file exists but is empty")
                return False
        else:
            logger.warning("Priority 2: UNHEALTHY - Data file not found")
            return False
    except Exception as e:
        logger.error(f"Priority 2: ERROR - {e}")
        return False

def check_priority3_health():
    """Check Priority 3 health"""
    try:
        if os.path.exists('data/clean_historical_database.sqlite'):
            conn = sqlite3.connect('data/clean_historical_database.sqlite')
            cursor = conn.cursor()
            
            # Check if tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            if len(tables) >= 2:  # Should have historical_data and technical_indicators
                # Check if there's data
                cursor.execute('SELECT COUNT(*) FROM historical_data')
                count = cursor.fetchone()[0]
                
                if count > 0:
                    logger.info(f"Priority 3: HEALTHY - Database exists with {count} records")
                    conn.close()
                    return True
                else:
                    logger.warning("Priority 3: WARNING - Database exists but is empty")
                    conn.close()
                    return False
            else:
                logger.warning("Priority 3: WARNING - Database exists but tables are missing")
                conn.close()
                return False
        else:
            logger.warning("Priority 3: UNHEALTHY - Database file not found")
            return False
    except Exception as e:
        logger.error(f"Priority 3: ERROR - {e}")
        return False

def check_environment():
    """Check environment setup"""
    logger.info("Checking environment setup...")
    
    # Check if .env file exists
    if os.path.exists('.env'):
        logger.info("Environment: .env file found")
    else:
        logger.warning("Environment: .env file not found")
    
    # Check if data directory exists
    if os.path.exists('data'):
        logger.info("Environment: data directory exists")
    else:
        logger.warning("Environment: data directory not found")
    
    # Check if required Python files exist
    required_files = [
        'clean_priority1_scraper.py',
        'clean_priority2_breaking_news.py',
        'clean_priority3_historical_database.py'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            logger.info(f"Environment: {file} found")
        else:
            logger.warning(f"Environment: {file} not found")

def main():
    """Main health check function"""
    logger.info("Starting comprehensive health check...")
    logger.info("=" * 60)
    
    # Check environment
    check_environment()
    
    # Check each priority
    p1_healthy = check_priority1_health()
    p2_healthy = check_priority2_health()
    p3_healthy = check_priority3_health()
    
    # Overall status
    logger.info("=" * 60)
    logger.info("HEALTH CHECK SUMMARY:")
    logger.info(f"  Priority 1 (Actual/Expected): {'HEALTHY' if p1_healthy else 'UNHEALTHY'}")
    logger.info(f"  Priority 2 (Breaking News): {'HEALTHY' if p2_healthy else 'UNHEALTHY'}")
    logger.info(f"  Priority 3 (Historical DB): {'HEALTHY' if p3_healthy else 'UNHEALTHY'}")
    
    all_healthy = p1_healthy and p2_healthy and p3_healthy
    
    if all_healthy:
        logger.info("SUCCESS: All priorities are healthy!")
        logger.info("SUCCESS: System is ready for production use")
        return True
    else:
        logger.warning("WARNING: Some priorities are unhealthy - check automation")
        logger.warning("WARNING: Verify Windows Task Scheduler is running")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\nSUCCESS: All priorities are healthy!")
        print("System is ready for production use")
    else:
        print("\nWARNING: Some priorities need attention!")
        print("Check automation and file permissions")
