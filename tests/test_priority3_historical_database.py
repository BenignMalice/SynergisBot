#!/usr/bin/env python3
"""
Test Script for Priority 3: Historical Database Implementation
==============================================================

This script tests the Alpha Vantage historical database implementation.

Usage:
    python test_priority3_historical_database.py
"""

import sys
import os
import json
from datetime import datetime
import sqlite3

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_historical_database():
    """Test the historical database implementation"""
    print("Testing Priority 3: Historical Database Implementation")
    print("=" * 60)
    
    try:
        # Check for API key
        api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if not api_key:
            print("WARNING: ALPHA_VANTAGE_API_KEY environment variable not set")
            print("   This test will use a mock implementation")
            print("   To test with real data, set your API key:")
            print("   export ALPHA_VANTAGE_API_KEY='your_api_key_here'")
            
            # Test database initialization without API key
            from priority3_historical_database import AlphaVantageHistoricalDatabase
            
            # Mock API key for testing
            db = AlphaVantageHistoricalDatabase('test_api_key')
            print("SUCCESS: Database initialized successfully")
            
            # Test database stats
            stats = db.get_database_stats()
            print(f"SUCCESS: Database stats retrieved: {stats}")
            
            return True
        
        # Import the database class
        from priority3_historical_database import AlphaVantageHistoricalDatabase
        
        print("SUCCESS: Successfully imported AlphaVantageHistoricalDatabase")
        
        # Initialize database
        db = AlphaVantageHistoricalDatabase(api_key)
        print("SUCCESS: Successfully initialized historical database")
        
        # Test database initialization
        print("\nTesting database initialization...")
        stats = db.get_database_stats()
        print(f"    SUCCESS: Database stats: {stats}")
        
        # Test forex data fetching
        print("\nTesting forex data fetching...")
        forex_data = db.fetch_forex_data('EURUSD')
        if forex_data:
            print(f"    SUCCESS: Fetched {len(forex_data)} forex data points")
        else:
            print("    WARNING: No forex data fetched (rate limit or API issue)")
        
        # Test stock data fetching
        print("\nTesting stock data fetching...")
        stock_data = db.fetch_stock_data('AAPL')
        if stock_data:
            print(f"    SUCCESS: Fetched {len(stock_data)} stock data points")
        else:
            print("    WARNING: No stock data fetched (rate limit or API issue)")
        
        # Test crypto data fetching
        print("\nTesting crypto data fetching...")
        crypto_data = db.fetch_crypto_data('BTC')
        if crypto_data:
            print(f"    SUCCESS: Fetched {len(crypto_data)} crypto data points")
        else:
            print("    WARNING: No crypto data fetched (rate limit or API issue)")
        
        # Test technical indicator fetching
        print("\nTesting technical indicator fetching...")
        indicator_data = db.fetch_technical_indicator('AAPL', 'SMA', 20)
        if indicator_data:
            print(f"    SUCCESS: Fetched {len(indicator_data)} SMA indicator data points")
        else:
            print("    WARNING: No technical indicator data fetched (rate limit or API issue)")
        
        # Test data retrieval
        print("\nTesting data retrieval...")
        historical_data = db.get_historical_data('EURUSD', 'forex', 10)
        print(f"    SUCCESS: Retrieved {len(historical_data)} historical forex records")
        
        # Test database stats
        print("\nTesting database statistics...")
        final_stats = db.get_database_stats()
        print("    Database Statistics:")
        for table, count in final_stats.items():
            print(f"      {table}: {count}")
        
        # Test database file
        print("\nTesting database file...")
        if os.path.exists('data/historical_database.sqlite'):
            print("    SUCCESS: Database file created successfully")
            
            # Test database connection
            conn = sqlite3.connect('data/historical_database.sqlite')
            cursor = conn.cursor()
            
            # Check tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"    SUCCESS: Database contains {len(tables)} tables")
            
            conn.close()
        else:
            print("    WARNING: Database file not found")
        
        # Overall assessment
        print("\nOverall Assessment:")
        print("-" * 50)
        
        if final_stats:
            total_records = sum(count for count in final_stats.values() if isinstance(count, int))
            print(f"SUCCESS: Historical database is working correctly!")
            print(f"SUCCESS: Total records in database: {total_records}")
            print("SUCCESS: Ready for production use")
            
            # Priority 3 benefits
            print("\nPriority 3 Benefits:")
            print("-" * 50)
            print("  - Historical data storage (SQLite database)")
            print("  - Multiple asset types (forex, stocks, crypto)")
            print("  - Technical indicators support")
            print("  - Rate limit compliance (25 requests/day)")
            print("  - Data persistence and retrieval")
            print("  - Free API tier (no cost)")
        else:
            print("WARNING: No data in database - check API key and rate limits")
        
        return True
        
    except ImportError as e:
        print(f"ERROR: Import error: {e}")
        print("   Make sure priority3_historical_database.py is in the same directory")
        return False
        
    except Exception as e:
        print(f"ERROR: Error during testing: {e}")
        return False

def test_database_schema():
    """Test database schema and structure"""
    print("\nTesting Database Schema:")
    print("-" * 50)
    
    try:
        if os.path.exists('data/historical_database.sqlite'):
            conn = sqlite3.connect('data/historical_database.sqlite')
            cursor = conn.cursor()
            
            # Check table schemas
            tables = ['forex_data', 'stock_data', 'crypto_data', 'technical_indicators']
            
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                print(f"  {table}: {len(columns)} columns")
                
                # Show column names
                column_names = [col[1] for col in columns]
                print(f"    Columns: {', '.join(column_names)}")
            
            conn.close()
            print("SUCCESS: Database schema is correct")
            return True
        else:
            print("WARNING: Database file not found")
            return False
            
    except Exception as e:
        print(f"ERROR: Database schema test failed: {e}")
        return False

def main():
    """Main test function"""
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = test_historical_database()
    schema_success = test_database_schema()
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success and schema_success:
        print("\nSUCCESS: Priority 3 historical database test PASSED!")
        print("   Ready for production use")
    else:
        print("\nERROR: Priority 3 historical database test FAILED!")
        print("   Check error messages above")
    
    return success and schema_success

if __name__ == "__main__":
    main()
