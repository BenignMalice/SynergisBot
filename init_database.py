#!/usr/bin/env python3
"""
Database Initialization Script
Creates proper database schema for the Unified Tick Pipeline
"""

import sqlite3
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_database_schema():
    """Create the database schema for the Unified Tick Pipeline"""
    
    # Database file path
    db_path = 'unified_tick_pipeline.db'
    
    # Remove existing database if it exists and is empty
    if os.path.exists(db_path) and os.path.getsize(db_path) == 0:
        os.remove(db_path)
        logger.info(f"Removed empty database file: {db_path}")
    
    # Create database connection
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable WAL mode for better concurrency
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=10000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    
    logger.info("✅ Database connection established with WAL mode")
    
    # Create unified_ticks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unified_ticks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            volume REAL,
            timestamp DATETIME NOT NULL,
            source TEXT NOT NULL,
            bid REAL,
            ask REAL,
            spread REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes for unified_ticks
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_unified_ticks_symbol_timestamp ON unified_ticks (symbol, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_unified_ticks_timestamp ON unified_ticks (timestamp)")
    logger.info("✅ Created unified_ticks table")
    
    # Create m5_candles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS m5_candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            open_price REAL NOT NULL,
            high_price REAL NOT NULL,
            low_price REAL NOT NULL,
            close_price REAL NOT NULL,
            volume REAL,
            timestamp DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timestamp)
        )
    """)
    
    # Create indexes for m5_candles
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_m5_candles_symbol_timestamp ON m5_candles (symbol, timestamp)")
    logger.info("✅ Created m5_candles table")
    
    # Create dtms_actions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dtms_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            action_data TEXT,
            timestamp DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes for dtms_actions
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dtms_actions_trade_id ON dtms_actions (trade_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dtms_actions_timestamp ON dtms_actions (timestamp)")
    logger.info("✅ Created dtms_actions table")
    
    # Create chatgpt_analysis_history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chatgpt_analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            analysis_type TEXT NOT NULL,
            analysis_data TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes for chatgpt_analysis_history
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chatgpt_analysis_symbol_timestamp ON chatgpt_analysis_history (symbol, timestamp)")
    logger.info("✅ Created chatgpt_analysis_history table")
    
    # Create system_health table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_health (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component TEXT NOT NULL,
            status TEXT NOT NULL,
            metrics TEXT,
            timestamp DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes for system_health
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_health_component_timestamp ON system_health (component, timestamp)")
    logger.info("✅ Created system_health table")
    
    # Create data_retention table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_retention (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            retention_days INTEGER NOT NULL,
            last_cleanup DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    logger.info("✅ Created data_retention table")
    
    # Insert default retention policies
    retention_policies = [
        ('unified_ticks', 7, None),
        ('m5_candles', 30, None),
        ('dtms_actions', 90, None),
        ('chatgpt_analysis_history', 30, None),
        ('system_health', 7, None)
    ]
    
    for table_name, days, last_cleanup in retention_policies:
        cursor.execute("""
            INSERT OR IGNORE INTO data_retention (table_name, retention_days, last_cleanup)
            VALUES (?, ?, ?)
        """, (table_name, days, last_cleanup))
    
    logger.info("✅ Inserted data retention policies")
    
    # Commit changes
    conn.commit()
    
    # Verify tables were created
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    logger.info(f"✅ Database schema created successfully. Tables: {[table[0] for table in tables]}")
    
    # Close connection
    conn.close()
    
    return True

def verify_database():
    """Verify the database schema is correct"""
    
    db_path = 'unified_tick_pipeline.db'
    
    if not os.path.exists(db_path):
        logger.error(f"❌ Database file not found: {db_path}")
        return False
    
    if os.path.getsize(db_path) == 0:
        logger.error(f"❌ Database file is empty: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        expected_tables = ['unified_ticks', 'm5_candles', 'dtms_actions', 
                          'chatgpt_analysis_history', 'system_health', 'data_retention']
        
        existing_tables = [table[0] for table in tables]
        
        for table in expected_tables:
            if table not in existing_tables:
                logger.error(f"❌ Missing table: {table}")
                return False
        
        logger.info(f"✅ Database verification successful. Found {len(tables)} tables")
        
        # Check database size
        size = os.path.getsize(db_path)
        logger.info(f"✅ Database size: {size:,} bytes")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Database verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🗄️ INITIALIZING DATABASE SCHEMA")
    print("=" * 50)
    
    try:
        # Create database schema
        success = create_database_schema()
        
        if success:
            print("✅ Database schema created successfully")
            
            # Verify database
            if verify_database():
                print("✅ Database verification passed")
                print("🎉 DATABASE INITIALIZATION COMPLETE!")
            else:
                print("❌ Database verification failed")
        else:
            print("❌ Database schema creation failed")
            
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        logger.error(f"Database initialization error: {e}")
