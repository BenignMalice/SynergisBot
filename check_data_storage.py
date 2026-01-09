#!/usr/bin/env python3
"""
Check if streaming data is being saved to database/cache
"""

import sqlite3
import os
from datetime import datetime

def check_data_storage():
    print('🔍 CHECKING DATA STORAGE SYSTEM')
    print('=' * 50)

    # Check if database files exist
    db_files = [
        'unified_tick_pipeline.db',
        'trading_data.db', 
        'market_data.db',
        'tick_data.db'
    ]

    print('📊 Database Files:')
    for db_file in db_files:
        if os.path.exists(db_file):
            size = os.path.getsize(db_file)
            print(f'   ✅ {db_file}: {size:,} bytes')
        else:
            print(f'   ❌ {db_file}: Not found')

    print()
    print('🗄️ Checking unified_tick_pipeline.db...')
    try:
        conn = sqlite3.connect('unified_tick_pipeline.db')
        cursor = conn.cursor()
        
        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print('📋 Tables found:')
        for table in tables:
            table_name = table[0]
            cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
            count = cursor.fetchone()[0]
            print(f'   → {table_name}: {count:,} records')
        
        # Check recent ticks
        if 'unified_ticks' in [t[0] for t in tables]:
            cursor.execute('SELECT COUNT(*) FROM unified_ticks WHERE timestamp > datetime("now", "-1 hour")')
            recent_ticks = cursor.fetchone()[0]
            print(f'   📈 Recent ticks (last hour): {recent_ticks:,}')
            
            cursor.execute('SELECT symbol, COUNT(*) FROM unified_ticks GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 5')
            top_symbols = cursor.fetchall()
            print('   🏆 Top symbols by tick count:')
            for symbol, count in top_symbols:
                print(f'      → {symbol}: {count:,} ticks')
        
        conn.close()
        print('✅ Database connection successful')
        
    except Exception as e:
        print(f'❌ Database error: {e}')

    print()
    print('📁 Cache Directory Check:')
    cache_dirs = ['cache', 'data', 'logs', 'unified_tick_pipeline']
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            files = os.listdir(cache_dir)
            print(f'   ✅ {cache_dir}/: {len(files)} files')
        else:
            print(f'   ❌ {cache_dir}/: Not found')

    print()
    print('🔄 Checking for active data streams...')
    try:
        # Check if there are any running processes that might be writing data
        import psutil
        python_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'python' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if any(keyword in cmdline for keyword in ['chatgpt_bot', 'desktop_agent', 'unified_tick_pipeline']):
                        python_processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        print(f'   🐍 Python processes related to trading system: {len(python_processes)}')
        for proc in python_processes:
            print(f'      → PID {proc["pid"]}: {proc["name"]}')
            
    except ImportError:
        print('   ⚠️ psutil not available for process checking')
    except Exception as e:
        print(f'   ❌ Process check error: {e}')

if __name__ == '__main__':
    check_data_storage()
