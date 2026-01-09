#!/usr/bin/env python3
"""
Check the unified tick pipeline database
"""

import sqlite3

def check_database():
    print('🔍 CHECKING UNIFIED TICK PIPELINE DATABASE')
    print('=' * 50)

    try:
        conn = sqlite3.connect('unified_tick_pipeline.db')
        cursor = conn.cursor()
        
        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        if tables:
            print('📋 Tables found:')
            for table in tables:
                table_name = table[0]
                cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
                count = cursor.fetchone()[0]
                print(f'   → {table_name}: {count:,} records')
                
                # Show table structure
                cursor.execute(f'PRAGMA table_info({table_name})')
                columns = cursor.fetchall()
                print(f'      Columns: {[col[1] for col in columns]}')
        else:
            print('❌ No tables found in database')
        
        conn.close()
        print('✅ Database connection successful')
        
    except Exception as e:
        print(f'❌ Database error: {e}')

if __name__ == '__main__':
    check_database()
