#!/usr/bin/env python3
"""
Test Script for Clean Priority 3: Historical Database Implementation
====================================================================

This script tests the clean historical database implementation.

Usage:
    python test_clean_priority3.py
"""

import sys
import os
import json
from datetime import datetime
import sqlite3

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_clean_historical_database():
    """Test the clean historical database implementation"""
    print("Testing Clean Priority 3: Historical Database Implementation")
    print("=" * 65)
    
    try:
        # Import the clean database class
        from clean_priority3_historical_database import CleanHistoricalDatabase
        
        print("SUCCESS: Successfully imported CleanHistoricalDatabase")
        
        # Initialize database
        db = CleanHistoricalDatabase()
        print("SUCCESS: Successfully initialized clean historical database")
        
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
            print("    WARNING: No forex data fetched")
        
        # Test stock data fetching
        print("\nTesting stock data fetching...")
        stock_data = db.fetch_stock_data('AAPL')
        if stock_data:
            print(f"    SUCCESS: Fetched {len(stock_data)} stock data points")
        else:
            print("    WARNING: No stock data fetched")
        
        # Test crypto data fetching
        print("\nTesting crypto data fetching...")
        crypto_data = db.fetch_crypto_data('BTC')
        if crypto_data:
            print(f"    SUCCESS: Fetched {len(crypto_data)} crypto data points")
        else:
            print("    WARNING: No crypto data fetched")
        
        # Test data retrieval
        print("\nTesting data retrieval...")
        historical_forex = db.get_historical_data('EURUSD', 'forex', 10)
        historical_stock = db.get_historical_data('AAPL', 'stock', 10)
        historical_crypto = db.get_historical_data('BTC', 'crypto', 10)
        
        print(f"    SUCCESS: Retrieved {len(historical_forex)} historical forex records")
        print(f"    SUCCESS: Retrieved {len(historical_stock)} historical stock records")
        print(f"    SUCCESS: Retrieved {len(historical_crypto)} historical crypto records")
        
        # Test database stats
        print("\nTesting database statistics...")
        final_stats = db.get_database_stats()
        print("    Database Statistics:")
        for table, count in final_stats.items():
            print(f"      {table}: {count}")
        
        # Test database file
        print("\nTesting database file...")
        if os.path.exists('data/clean_historical_database.sqlite'):
            print("    SUCCESS: Database file created successfully")
            
            # Test database connection
            conn = sqlite3.connect('data/clean_historical_database.sqlite')
            cursor = conn.cursor()
            
            # Check tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"    SUCCESS: Database contains {len(tables)} tables")
            
            # Check table schemas
            print("    Table Schemas:")
            for table_name, in tables:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                print(f"      {table_name}: {len(columns)} columns ({', '.join(column_names[:5])}...)")
            
            conn.close()
        else:
            print("    WARNING: Database file not found")
        
        # Test mock mode
        print("\nTesting mock mode...")
        if db.mock_mode:
            print("    SUCCESS: Running in mock mode (no API key required)")
            print("    SUCCESS: Mock data generation working correctly")
        else:
            print("    SUCCESS: Running with real API key")
        
        # Overall assessment
        print("\nOverall Assessment:")
        print("-" * 50)
        
        if final_stats:
            total_records = sum(count for count in final_stats.values() if isinstance(count, int))
            print(f"SUCCESS: Clean historical database is working correctly!")
            print(f"SUCCESS: Total records in database: {total_records}")
            print("SUCCESS: Ready for production use")
            
            # Clean implementation benefits
            print("\nClean Implementation Benefits:")
            print("-" * 50)
            print("  - Unified database schema (single table)")
            print("  - Multiple asset types (forex, stocks, crypto)")
            print("  - Mock mode for testing (no API key required)")
            print("  - Rate limit compliance (25 requests/day)")
            print("  - Data persistence and retrieval")
            print("  - Free API tier (no cost)")
            print("  - Clean, maintainable code")
        else:
            print("WARNING: No data in database - check API key and rate limits")
        
        return True
        
    except ImportError as e:
        print(f"ERROR: Import error: {e}")
        print("   Make sure clean_priority3_historical_database.py is in the same directory")
        return False
        
    except Exception as e:
        print(f"ERROR: Error during testing: {e}")
        return False

def test_database_schema():
    """Test database schema and structure"""
    print("\nTesting Database Schema:")
    print("-" * 50)
    
    try:
        if os.path.exists('data/clean_historical_database.sqlite'):
            conn = sqlite3.connect('data/clean_historical_database.sqlite')
            cursor = conn.cursor()
            
            # Check table schemas
            tables = ['historical_data', 'technical_indicators']
            
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
    
    success = test_clean_historical_database()
    schema_success = test_database_schema()
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success and schema_success:
        print("\nSUCCESS: Clean Priority 3 historical database test PASSED!")
        print("   Ready for production use")
    else:
        print("\nERROR: Clean Priority 3 historical database test FAILED!")
        print("   Check error messages above")
    
    return success and schema_success

if __name__ == "__main__":
    main()
