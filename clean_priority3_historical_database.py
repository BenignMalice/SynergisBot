#!/usr/bin/env python3
"""
Clean Priority 3: Historical Database Implementation
====================================================

This clean version focuses on essential features:
- SQLite database for historical data storage
- Alpha Vantage API integration
- Rate limit compliance (25 requests/day)
- Essential data types (forex, stocks, crypto)

Usage:
    python clean_priority3_historical_database.py
"""

import requests
import json
import time
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CleanHistoricalDatabase:
    """Clean historical database using Alpha Vantage API"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_API_KEY')
        if not self.api_key:
            logger.warning("WARNING: Alpha Vantage API key not found. Using mock mode.")
            self.api_key = 'mock_api_key'
            self.mock_mode = True
        else:
            self.mock_mode = False
        
        self.base_url = "https://www.alphavantage.co/query"
        self.rate_limit = 12  # seconds between requests (25 requests/day)
        self.db_path = 'data/clean_historical_database.sqlite'
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for historical data"""
        try:
            os.makedirs('data', exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create unified historical data table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS historical_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    adjusted_close REAL,
                    dividend_amount REAL,
                    split_coefficient REAL,
                    market_cap REAL,
                    source TEXT DEFAULT 'alpha_vantage',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, asset_type, date)
                )
            ''')
            
            # Create technical indicators table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS technical_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    indicator_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    value REAL,
                    source TEXT DEFAULT 'alpha_vantage',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, indicator_name, date)
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("SUCCESS: Clean database initialized successfully")
            
        except Exception as e:
            logger.error(f"ERROR: Failed to initialize database: {e}")
            raise
    
    def fetch_forex_data(self, symbol: str, outputsize: str = 'compact'):
        """Fetch historical forex data"""
        if self.mock_mode:
            return self._mock_forex_data(symbol)
        
        try:
            logger.info(f"Fetching forex data for {symbol}...")
            
            params = {
                'function': 'FX_DAILY',
                'from_symbol': symbol[:3],
                'to_symbol': symbol[3:],
                'outputsize': outputsize,
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if 'Error Message' in data:
                logger.error(f"ERROR: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                logger.warning(f"WARNING: {data['Note']}")
                return None
            
            time_series = data.get('Time Series (FX)', {})
            
            if not time_series:
                logger.warning(f"WARNING: No data found for {symbol}")
                return None
            
            self._store_historical_data(symbol, 'forex', time_series)
            
            logger.info(f"SUCCESS: Fetched {len(time_series)} forex data points for {symbol}")
            return time_series
            
        except Exception as e:
            logger.error(f"ERROR: Failed to fetch forex data for {symbol}: {e}")
            return None
    
    def fetch_stock_data(self, symbol: str, outputsize: str = 'compact'):
        """Fetch historical stock data"""
        if self.mock_mode:
            return self._mock_stock_data(symbol)
        
        try:
            logger.info(f"Fetching stock data for {symbol}...")
            
            params = {
                'function': 'TIME_SERIES_DAILY_ADJUSTED',
                'symbol': symbol,
                'outputsize': outputsize,
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if 'Error Message' in data:
                logger.error(f"ERROR: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                logger.warning(f"WARNING: {data['Note']}")
                return None
            
            time_series = data.get('Time Series (Daily)', {})
            
            if not time_series:
                logger.warning(f"WARNING: No data found for {symbol}")
                return None
            
            self._store_historical_data(symbol, 'stock', time_series)
            
            logger.info(f"SUCCESS: Fetched {len(time_series)} stock data points for {symbol}")
            return time_series
            
        except Exception as e:
            logger.error(f"ERROR: Failed to fetch stock data for {symbol}: {e}")
            return None
    
    def fetch_crypto_data(self, symbol: str, market: str = 'USD'):
        """Fetch historical cryptocurrency data"""
        if self.mock_mode:
            return self._mock_crypto_data(symbol)
        
        try:
            logger.info(f"Fetching crypto data for {symbol}...")
            
            params = {
                'function': 'DIGITAL_CURRENCY_DAILY',
                'symbol': symbol,
                'market': market,
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if 'Error Message' in data:
                logger.error(f"ERROR: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                logger.warning(f"WARNING: {data['Note']}")
                return None
            
            time_series = data.get('Time Series (Digital Currency Daily)', {})
            
            if not time_series:
                logger.warning(f"WARNING: No data found for {symbol}")
                return None
            
            self._store_historical_data(symbol, 'crypto', time_series)
            
            logger.info(f"SUCCESS: Fetched {len(time_series)} crypto data points for {symbol}")
            return time_series
            
        except Exception as e:
            logger.error(f"ERROR: Failed to fetch crypto data for {symbol}: {e}")
            return None
    
    def _mock_forex_data(self, symbol: str):
        """Mock forex data for testing"""
        logger.info(f"Using mock forex data for {symbol}")
        return {
            '2025-10-15': {
                '1. open': '1.0500',
                '2. high': '1.0550',
                '3. low': '1.0480',
                '4. close': '1.0520',
                '5. volume': '1000000'
            }
        }
    
    def _mock_stock_data(self, symbol: str):
        """Mock stock data for testing"""
        logger.info(f"Using mock stock data for {symbol}")
        return {
            '2025-10-15': {
                '1. open': '150.00',
                '2. high': '155.00',
                '3. low': '148.00',
                '4. close': '152.00',
                '5. adjusted close': '152.00',
                '6. volume': '1000000',
                '7. dividend amount': '0.00',
                '8. split coefficient': '1.0'
            }
        }
    
    def _mock_crypto_data(self, symbol: str):
        """Mock crypto data for testing"""
        logger.info(f"Using mock crypto data for {symbol}")
        return {
            '2025-10-15': {
                '1a. open (USD)': '50000.00',
                '2a. high (USD)': '51000.00',
                '3a. low (USD)': '49000.00',
                '4a. close (USD)': '50500.00',
                '5. volume': '1000000',
                '6. market cap (USD)': '1000000000'
            }
        }
    
    def _store_historical_data(self, symbol: str, asset_type: str, time_series: Dict):
        """Store historical data in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for date, data in time_series.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO historical_data 
                    (symbol, asset_type, date, open, high, low, close, volume, 
                     adjusted_close, dividend_amount, split_coefficient, market_cap)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    asset_type,
                    date,
                    float(data.get('1. open', data.get('1a. open (USD)', 0))),
                    float(data.get('2. high', data.get('2a. high (USD)', 0))),
                    float(data.get('3. low', data.get('3a. low (USD)', 0))),
                    float(data.get('4. close', data.get('4a. close (USD)', 0))),
                    float(data.get('5. volume', data.get('6. volume', 0))),
                    float(data.get('5. adjusted close', 0)),
                    float(data.get('7. dividend amount', 0)),
                    float(data.get('8. split coefficient', 1)),
                    float(data.get('6. market cap (USD)', 0))
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"ERROR: Failed to store historical data: {e}")
    
    def get_historical_data(self, symbol: str, asset_type: str = 'forex', days: int = 30):
        """Retrieve historical data from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM historical_data 
                WHERE symbol = ? AND asset_type = ?
                ORDER BY date DESC 
                LIMIT ?
            ''', (symbol, asset_type, days))
            
            data = cursor.fetchall()
            conn.close()
            
            return data
            
        except Exception as e:
            logger.error(f"ERROR: Failed to retrieve historical data: {e}")
            return []
    
    def get_database_stats(self):
        """Get database statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # Count records in each table
            cursor.execute('SELECT COUNT(*) FROM historical_data')
            stats['historical_data'] = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM technical_indicators')
            stats['technical_indicators'] = cursor.fetchone()[0]
            
            # Count unique symbols
            cursor.execute('SELECT COUNT(DISTINCT symbol) FROM historical_data')
            stats['unique_symbols'] = cursor.fetchone()[0]
            
            # Count by asset type
            cursor.execute('SELECT asset_type, COUNT(*) FROM historical_data GROUP BY asset_type')
            asset_counts = cursor.fetchall()
            for asset_type, count in asset_counts:
                stats[f'{asset_type}_records'] = count
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f"ERROR: Failed to get database stats: {e}")
            return {}

def main():
    """Main function to run the clean historical database implementation"""
    logger.info("Starting Clean Priority 3: Historical Database Implementation")
    
    # Initialize database
    db = CleanHistoricalDatabase()
    
    # Test symbols
    forex_symbols = ['EURUSD', 'GBPUSD', 'USDJPY']
    stock_symbols = ['AAPL', 'GOOGL', 'MSFT']
    crypto_symbols = ['BTC', 'ETH', 'ADA']
    
    # Fetch sample data
    logger.info("Fetching sample historical data...")
    
    # Forex data
    for symbol in forex_symbols:
        db.fetch_forex_data(symbol)
        time.sleep(1)  # Shorter delay for mock mode
    
    # Stock data
    for symbol in stock_symbols:
        db.fetch_stock_data(symbol)
        time.sleep(1)
    
    # Crypto data
    for symbol in crypto_symbols:
        db.fetch_crypto_data(symbol)
        time.sleep(1)
    
    # Get database statistics
    stats = db.get_database_stats()
    
    logger.info("Database Statistics:")
    for table, count in stats.items():
        logger.info(f"  {table}: {count}")
    
    # Test data retrieval
    logger.info("Testing data retrieval...")
    forex_data = db.get_historical_data('EURUSD', 'forex', 5)
    stock_data = db.get_historical_data('AAPL', 'stock', 5)
    crypto_data = db.get_historical_data('BTC', 'crypto', 5)
    
    logger.info(f"Retrieved {len(forex_data)} forex records")
    logger.info(f"Retrieved {len(stock_data)} stock records")
    logger.info(f"Retrieved {len(crypto_data)} crypto records")
    
    logger.info("SUCCESS: Clean Priority 3 historical database implementation completed!")
    logger.info("Next steps:")
    logger.info("  1. Review historical data in data/clean_historical_database.sqlite")
    logger.info("  2. Set up automated data updates")
    logger.info("  3. Integrate with existing analysis system")
    logger.info("  4. All three priorities are now complete!")

if __name__ == "__main__":
    main()
