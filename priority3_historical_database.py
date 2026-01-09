#!/usr/bin/env python3
"""
Priority 3: Historical Database Implementation
==============================================

This implementation uses Alpha Vantage API for historical data:
- Free API key (25 requests/day)
- Historical forex, stock, and crypto data
- Technical indicators
- Database storage and management

Usage:
    python priority3_historical_database.py
"""

import requests
import json
import time
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import pandas as pd

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AlphaVantageHistoricalDatabase:
    """Historical database using Alpha Vantage API"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_API_KEY')
        if not self.api_key:
            raise ValueError("Alpha Vantage API key not found. Set ALPHA_VANTAGE_API_KEY environment variable.")
        
        self.base_url = "https://www.alphavantage.co/query"
        self.rate_limit = 12  # seconds between requests (25 requests/day = 1 per 12 seconds)
        self.db_path = 'data/historical_database.sqlite'
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for historical data"""
        try:
            os.makedirs('data', exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create tables for different data types
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS forex_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    source TEXT DEFAULT 'alpha_vantage',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, date)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    adjusted_close REAL,
                    volume INTEGER,
                    dividend_amount REAL,
                    split_coefficient REAL,
                    source TEXT DEFAULT 'alpha_vantage',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, date)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crypto_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    market_cap REAL,
                    source TEXT DEFAULT 'alpha_vantage',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, date)
                )
            ''')
            
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
            
            logger.info("SUCCESS: Database initialized successfully")
            
        except Exception as e:
            logger.error(f"ERROR: Failed to initialize database: {e}")
            raise
    
    def fetch_forex_data(self, symbol: str, outputsize: str = 'compact'):
        """Fetch historical forex data"""
        try:
            logger.info(f"Fetching forex data for {symbol}...")
            
            params = {
                'function': 'FX_DAILY',
                'from_symbol': symbol[:3],  # e.g., 'USD' from 'USDJPY'
                'to_symbol': symbol[3:],    # e.g., 'JPY' from 'USDJPY'
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
            
            # Extract time series data
            time_series = data.get('Time Series (FX)', {})
            
            if not time_series:
                logger.warning(f"WARNING: No data found for {symbol}")
                return None
            
            # Process and store data
            self._store_forex_data(symbol, time_series)
            
            logger.info(f"SUCCESS: Fetched {len(time_series)} forex data points for {symbol}")
            return time_series
            
        except Exception as e:
            logger.error(f"ERROR: Failed to fetch forex data for {symbol}: {e}")
            return None
    
    def fetch_stock_data(self, symbol: str, outputsize: str = 'compact'):
        """Fetch historical stock data"""
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
            
            # Extract time series data
            time_series = data.get('Time Series (Daily)', {})
            
            if not time_series:
                logger.warning(f"WARNING: No data found for {symbol}")
                return None
            
            # Process and store data
            self._store_stock_data(symbol, time_series)
            
            logger.info(f"SUCCESS: Fetched {len(time_series)} stock data points for {symbol}")
            return time_series
            
        except Exception as e:
            logger.error(f"ERROR: Failed to fetch stock data for {symbol}: {e}")
            return None
    
    def fetch_crypto_data(self, symbol: str, market: str = 'USD'):
        """Fetch historical cryptocurrency data"""
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
            
            # Extract time series data
            time_series = data.get('Time Series (Digital Currency Daily)', {})
            
            if not time_series:
                logger.warning(f"WARNING: No data found for {symbol}")
                return None
            
            # Process and store data
            self._store_crypto_data(symbol, time_series)
            
            logger.info(f"SUCCESS: Fetched {len(time_series)} crypto data points for {symbol}")
            return time_series
            
        except Exception as e:
            logger.error(f"ERROR: Failed to fetch crypto data for {symbol}: {e}")
            return None
    
    def fetch_technical_indicator(self, symbol: str, indicator: str, time_period: int = 20):
        """Fetch technical indicator data"""
        try:
            logger.info(f"Fetching {indicator} for {symbol}...")
            
            params = {
                'function': indicator,
                'symbol': symbol,
                'interval': 'daily',
                'time_period': time_period,
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
            
            # Extract indicator data
            indicator_data = data.get(f'Technical Analysis: {indicator}', {})
            
            if not indicator_data:
                logger.warning(f"WARNING: No {indicator} data found for {symbol}")
                return None
            
            # Process and store data
            self._store_technical_indicator(symbol, indicator, indicator_data)
            
            logger.info(f"SUCCESS: Fetched {len(indicator_data)} {indicator} data points for {symbol}")
            return indicator_data
            
        except Exception as e:
            logger.error(f"ERROR: Failed to fetch {indicator} for {symbol}: {e}")
            return None
    
    def _store_forex_data(self, symbol: str, time_series: Dict):
        """Store forex data in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for date, data in time_series.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO forex_data 
                    (symbol, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    date,
                    float(data.get('1. open', 0)),
                    float(data.get('2. high', 0)),
                    float(data.get('3. low', 0)),
                    float(data.get('4. close', 0)),
                    int(data.get('5. volume', 0))
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"ERROR: Failed to store forex data: {e}")
    
    def _store_stock_data(self, symbol: str, time_series: Dict):
        """Store stock data in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for date, data in time_series.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_data 
                    (symbol, date, open, high, low, close, adjusted_close, volume, dividend_amount, split_coefficient)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    date,
                    float(data.get('1. open', 0)),
                    float(data.get('2. high', 0)),
                    float(data.get('3. low', 0)),
                    float(data.get('4. close', 0)),
                    float(data.get('5. adjusted close', 0)),
                    int(data.get('6. volume', 0)),
                    float(data.get('7. dividend amount', 0)),
                    float(data.get('8. split coefficient', 1))
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"ERROR: Failed to store stock data: {e}")
    
    def _store_crypto_data(self, symbol: str, time_series: Dict):
        """Store crypto data in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for date, data in time_series.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO crypto_data 
                    (symbol, date, open, high, low, close, volume, market_cap)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    date,
                    float(data.get('1a. open (USD)', 0)),
                    float(data.get('2a. high (USD)', 0)),
                    float(data.get('3a. low (USD)', 0)),
                    float(data.get('4a. close (USD)', 0)),
                    float(data.get('5. volume', 0)),
                    float(data.get('6. market cap (USD)', 0))
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"ERROR: Failed to store crypto data: {e}")
    
    def _store_technical_indicator(self, symbol: str, indicator: str, indicator_data: Dict):
        """Store technical indicator data in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for date, data in indicator_data.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO technical_indicators 
                    (symbol, indicator_name, date, value)
                    VALUES (?, ?, ?, ?)
                ''', (
                    symbol,
                    indicator,
                    date,
                    float(data.get(indicator, 0))
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"ERROR: Failed to store technical indicator: {e}")
    
    def get_historical_data(self, symbol: str, data_type: str = 'forex', days: int = 30):
        """Retrieve historical data from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if data_type == 'forex':
                cursor.execute('''
                    SELECT * FROM forex_data 
                    WHERE symbol = ? 
                    ORDER BY date DESC 
                    LIMIT ?
                ''', (symbol, days))
            elif data_type == 'stock':
                cursor.execute('''
                    SELECT * FROM stock_data 
                    WHERE symbol = ? 
                    ORDER BY date DESC 
                    LIMIT ?
                ''', (symbol, days))
            elif data_type == 'crypto':
                cursor.execute('''
                    SELECT * FROM crypto_data 
                    WHERE symbol = ? 
                    ORDER BY date DESC 
                    LIMIT ?
                ''', (symbol, days))
            
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
            tables = ['forex_data', 'stock_data', 'crypto_data', 'technical_indicators']
            for table in tables:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                count = cursor.fetchone()[0]
                stats[table] = count
            
            # Get unique symbols
            for table in tables:
                cursor.execute(f'SELECT COUNT(DISTINCT symbol) FROM {table}')
                count = cursor.fetchone()[0]
                stats[f'{table}_symbols'] = count
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f"ERROR: Failed to get database stats: {e}")
            return {}

def main():
    """Main function to run the historical database implementation"""
    logger.info("Starting Priority 3: Historical Database Implementation")
    
    # Check for API key
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    if not api_key:
        logger.error("ERROR: ALPHA_VANTAGE_API_KEY environment variable not set")
        logger.info("Please set your Alpha Vantage API key:")
        logger.info("  export ALPHA_VANTAGE_API_KEY='your_api_key_here'")
        return
    
    # Initialize database
    db = AlphaVantageHistoricalDatabase(api_key)
    
    # Test symbols
    forex_symbols = ['EURUSD', 'GBPUSD', 'USDJPY']
    stock_symbols = ['AAPL', 'GOOGL', 'MSFT']
    crypto_symbols = ['BTC', 'ETH', 'ADA']
    
    # Fetch sample data
    logger.info("Fetching sample historical data...")
    
    # Forex data
    for symbol in forex_symbols:
        db.fetch_forex_data(symbol)
        time.sleep(db.rate_limit)
    
    # Stock data
    for symbol in stock_symbols:
        db.fetch_stock_data(symbol)
        time.sleep(db.rate_limit)
    
    # Crypto data
    for symbol in crypto_symbols:
        db.fetch_crypto_data(symbol)
        time.sleep(db.rate_limit)
    
    # Technical indicators
    for symbol in stock_symbols:
        db.fetch_technical_indicator(symbol, 'SMA', 20)
        time.sleep(db.rate_limit)
    
    # Get database statistics
    stats = db.get_database_stats()
    
    logger.info("Database Statistics:")
    for table, count in stats.items():
        logger.info(f"  {table}: {count}")
    
    logger.info("SUCCESS: Priority 3 historical database implementation completed!")
    logger.info("Next steps:")
    logger.info("  1. Review historical data in data/historical_database.sqlite")
    logger.info("  2. Set up automated data updates")
    logger.info("  3. Integrate with existing analysis system")
    logger.info("  4. All three priorities are now complete!")

if __name__ == "__main__":
    main()
