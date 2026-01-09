"""
Trade Data Integration for Separate Database Architecture
========================================================
This module ensures all trade recommendations, executions, and monitoring
are properly saved to the appropriate databases in the separate database architecture:
- Trade recommendations → Analysis database (Desktop Agent WRITE access)
- Trade executions → Main database (ChatGPT Bot WRITE access) 
- Trade monitoring → Logs database (API Server WRITE access)
"""

import sqlite3
import logging
import time
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pathlib import Path

# Import the database access manager
from database_access_manager import DatabaseAccessManager, initialize_database_manager

logger = logging.getLogger(__name__)

class TradeDataIntegrationSeparateDatabases:
    """
    Integrates trade data with separate database architecture.
    
    Features:
    - Trade recommendations saved to analysis database
    - Trade executions saved to main database
    - Trade monitoring saved to logs database
    - Eliminates database conflicts
    """
    
    def __init__(self, process_type: str = "unknown"):
        self.process_type = process_type
        self.db_manager = initialize_database_manager(process_type)
        
        # Initialize trade data tables in appropriate databases
        self._initialize_trade_tables()
        
        logger.info(f"TradeDataIntegrationSeparateDatabases initialized for {process_type}")
    
    def _initialize_trade_tables(self):
        """Initialize trade-related tables in appropriate databases."""
        try:
            # Initialize trade recommendations table in analysis database
            if self.process_type in ["desktop_agent", "chatgpt_bot"]:
                self._init_analysis_trade_tables()
            
            # Initialize trade executions table in main database
            if self.process_type in ["chatgpt_bot", "desktop_agent"]:
                self._init_main_trade_tables()
            
            # Initialize trade monitoring table in logs database
            if self.process_type in ["api_server", "desktop_agent"]:
                self._init_logs_trade_tables()
            
            logger.info("✅ Trade data tables initialized for separate database architecture")
            
        except Exception as e:
            logger.error(f"❌ Error initializing trade tables: {e}")
    
    def _init_analysis_trade_tables(self):
        """Initialize trade tables in analysis database."""
        try:
            with self.db_manager.get_analysis_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                # Trade recommendations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_recommendations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        stop_loss REAL NOT NULL,
                        take_profit REAL NOT NULL,
                        volume REAL NOT NULL,
                        confidence INTEGER NOT NULL,
                        reasoning TEXT,
                        market_regime TEXT,
                        timeframe TEXT,
                        session TEXT,
                        confluence_score REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        status TEXT DEFAULT 'pending',
                        executed_at TIMESTAMP,
                        ticket INTEGER,
                        outcome TEXT,
                        exit_price REAL,
                        profit_loss REAL,
                        risk_reward_achieved REAL
                    )
                """)
                
                # Trade analysis results table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_analysis (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        analysis_type TEXT NOT NULL,
                        result TEXT NOT NULL,
                        confidence REAL,
                        timestamp REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_symbol ON trade_recommendations(symbol)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_status ON trade_recommendations(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_symbol ON trade_analysis(symbol)")
                
                conn.commit()
                logger.info("✅ Analysis database trade tables initialized")
                
        except Exception as e:
            logger.error(f"❌ Error initializing analysis trade tables: {e}")
    
    def _init_main_trade_tables(self):
        """Initialize trade tables in main database."""
        try:
            with self.db_manager.get_main_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                # Trade executions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_executions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket INTEGER UNIQUE NOT NULL,
                        symbol TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        stop_loss REAL,
                        take_profit REAL,
                        volume REAL NOT NULL,
                        execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        execution_type TEXT,
                        source TEXT,
                        balance REAL,
                        equity REAL,
                        confidence INTEGER,
                        risk_reward REAL,
                        notes TEXT
                    )
                """)
                
                # Trade positions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_positions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket INTEGER UNIQUE NOT NULL,
                        symbol TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        current_price REAL,
                        stop_loss REAL,
                        take_profit REAL,
                        volume REAL NOT NULL,
                        unrealized_pnl REAL,
                        open_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'open'
                    )
                """)
                
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_executions_ticket ON trade_executions(ticket)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_executions_symbol ON trade_executions(symbol)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_ticket ON trade_positions(ticket)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_status ON trade_positions(status)")
                
                conn.commit()
                logger.info("✅ Main database trade tables initialized")
                
        except Exception as e:
            logger.error(f"❌ Error initializing main trade tables: {e}")
    
    def _init_logs_trade_tables(self):
        """Initialize trade tables in logs database."""
        try:
            with self.db_manager.get_logs_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                # Trade monitoring table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_monitoring (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket INTEGER NOT NULL,
                        symbol TEXT NOT NULL,
                        monitoring_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        details TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        source TEXT
                    )
                """)
                
                # Trade alerts table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket INTEGER NOT NULL,
                        symbol TEXT NOT NULL,
                        alert_type TEXT NOT NULL,
                        message TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        sent BOOLEAN DEFAULT FALSE
                    )
                """)
                
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_monitoring_ticket ON trade_monitoring(ticket)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_monitoring_type ON trade_monitoring(monitoring_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_ticket ON trade_alerts(ticket)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_type ON trade_alerts(alert_type)")
                
                conn.commit()
                logger.info("✅ Logs database trade tables initialized")
                
        except Exception as e:
            logger.error(f"❌ Error initializing logs trade tables: {e}")
    
    # Trade recommendation methods (Analysis database - Desktop Agent WRITE)
    def log_trade_recommendation(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        volume: float,
        confidence: int,
        reasoning: str = "",
        market_regime: str = "",
        timeframe: str = "",
        session: str = "",
        confluence_score: float = None,
        created_by: str = None
    ) -> int:
        """Log trade recommendation to analysis database."""
        try:
            with self.db_manager.get_analysis_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO trade_recommendations (
                        symbol, direction, entry_price, stop_loss, take_profit,
                        volume, confidence, reasoning, market_regime, timeframe,
                        session, confluence_score, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol.upper(),
                    direction.upper(),
                    entry_price,
                    stop_loss,
                    take_profit,
                    volume,
                    confidence,
                    reasoning,
                    market_regime,
                    timeframe,
                    session,
                    confluence_score,
                    created_by or self.process_type
                ))
                
                recommendation_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"✅ Trade recommendation logged: {symbol} {direction} @ {entry_price} (ID: {recommendation_id})")
                return recommendation_id
                
        except Exception as e:
            logger.error(f"❌ Error logging trade recommendation: {e}")
            return -1
    
    def update_recommendation_execution(
        self,
        recommendation_id: int,
        ticket: int,
        execution_time: datetime = None
    ) -> bool:
        """Update recommendation with execution details."""
        try:
            with self.db_manager.get_analysis_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE trade_recommendations
                    SET status = 'executed',
                        executed_at = ?,
                        ticket = ?
                    WHERE id = ?
                """, (
                    (execution_time or datetime.now(timezone.utc)).isoformat(),
                    ticket,
                    recommendation_id
                ))
                
                conn.commit()
                logger.info(f"✅ Recommendation {recommendation_id} marked as executed (ticket: {ticket})")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error updating recommendation execution: {e}")
            return False
    
    def update_recommendation_outcome(
        self,
        recommendation_id: int,
        outcome: str,
        exit_price: float = None,
        profit_loss: float = None,
        risk_reward_achieved: float = None
    ) -> bool:
        """Update recommendation with outcome details."""
        try:
            with self.db_manager.get_analysis_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE trade_recommendations
                    SET outcome = ?,
                        exit_price = ?,
                        profit_loss = ?,
                        risk_reward_achieved = ?
                    WHERE id = ?
                """, (outcome, exit_price, profit_loss, risk_reward_achieved, recommendation_id))
                
                conn.commit()
                logger.info(f"✅ Recommendation {recommendation_id} outcome updated: {outcome}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error updating recommendation outcome: {e}")
            return False
    
    # Trade execution methods (Main database - ChatGPT Bot WRITE)
    def log_trade_execution(
        self,
        ticket: int,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float = None,
        take_profit: float = None,
        volume: float = 0.01,
        execution_type: str = "market",
        source: str = None,
        balance: float = None,
        equity: float = None,
        confidence: int = 100,
        risk_reward: float = None,
        notes: str = ""
    ) -> bool:
        """Log trade execution to main database."""
        try:
            with self.db_manager.get_main_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO trade_executions (
                        ticket, symbol, direction, entry_price, stop_loss, take_profit,
                        volume, execution_type, source, balance, equity, confidence,
                        risk_reward, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticket,
                    symbol.upper(),
                    direction.upper(),
                    entry_price,
                    stop_loss,
                    take_profit,
                    volume,
                    execution_type,
                    source or self.process_type,
                    balance,
                    equity,
                    confidence,
                    risk_reward,
                    notes
                ))
                
                conn.commit()
                logger.info(f"✅ Trade execution logged: {symbol} {direction} ticket {ticket}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error logging trade execution: {e}")
            return False
    
    def update_trade_position(
        self,
        ticket: int,
        symbol: str,
        direction: str,
        entry_price: float,
        current_price: float,
        stop_loss: float = None,
        take_profit: float = None,
        volume: float = 0.01,
        unrealized_pnl: float = None
    ) -> bool:
        """Update trade position in main database."""
        try:
            with self.db_manager.get_main_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                # Check if position exists
                cursor.execute("SELECT id FROM trade_positions WHERE ticket = ?", (ticket,))
                if cursor.fetchone():
                    # Update existing position
                    cursor.execute("""
                        UPDATE trade_positions
                        SET current_price = ?, stop_loss = ?, take_profit = ?,
                            unrealized_pnl = ?, last_update = CURRENT_TIMESTAMP
                        WHERE ticket = ?
                    """, (current_price, stop_loss, take_profit, unrealized_pnl, ticket))
                else:
                    # Insert new position
                    cursor.execute("""
                        INSERT INTO trade_positions (
                            ticket, symbol, direction, entry_price, current_price,
                            stop_loss, take_profit, volume, unrealized_pnl
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ticket, symbol.upper(), direction.upper(), entry_price,
                        current_price, stop_loss, take_profit, volume, unrealized_pnl
                    ))
                
                conn.commit()
                logger.info(f"✅ Trade position updated: ticket {ticket}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error updating trade position: {e}")
            return False
    
    def close_trade_position(
        self,
        ticket: int,
        exit_price: float,
        realized_pnl: float
    ) -> bool:
        """Close trade position in main database."""
        try:
            with self.db_manager.get_main_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE trade_positions
                    SET status = 'closed',
                        current_price = ?,
                        unrealized_pnl = ?,
                        last_update = CURRENT_TIMESTAMP
                    WHERE ticket = ?
                """, (exit_price, realized_pnl, ticket))
                
                conn.commit()
                logger.info(f"✅ Trade position closed: ticket {ticket}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error closing trade position: {e}")
            return False
    
    # Trade monitoring methods (Logs database - API Server WRITE)
    def log_trade_monitoring(
        self,
        ticket: int,
        symbol: str,
        monitoring_type: str,
        status: str,
        details: str = "",
        source: str = None
    ) -> bool:
        """Log trade monitoring to logs database."""
        try:
            with self.db_manager.get_logs_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO trade_monitoring (
                        ticket, symbol, monitoring_type, status, details, source
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (ticket, symbol.upper(), monitoring_type, status, details, source or self.process_type))
                
                conn.commit()
                logger.info(f"✅ Trade monitoring logged: ticket {ticket} - {monitoring_type}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error logging trade monitoring: {e}")
            return False
    
    def log_trade_alert(
        self,
        ticket: int,
        symbol: str,
        alert_type: str,
        message: str
    ) -> bool:
        """Log trade alert to logs database."""
        try:
            with self.db_manager.get_logs_db_connection(read_only=False) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO trade_alerts (
                        ticket, symbol, alert_type, message
                    ) VALUES (?, ?, ?, ?)
                """, (ticket, symbol.upper(), alert_type, message))
                
                conn.commit()
                logger.info(f"✅ Trade alert logged: ticket {ticket} - {alert_type}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error logging trade alert: {e}")
            return False
    
    # Data retrieval methods (READ access from all databases)
    def get_trade_recommendations(
        self,
        symbol: str = None,
        status: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get trade recommendations from analysis database."""
        try:
            with self.db_manager.get_analysis_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM trade_recommendations WHERE 1=1"
                params = []
                
                if symbol:
                    query += " AND symbol = ?"
                    params.append(symbol.upper())
                
                if status:
                    query += " AND status = ?"
                    params.append(status)
                
                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to list of dicts
                columns = [description[0] for description in cursor.description]
                recommendations = [dict(zip(columns, row)) for row in rows]
                
                return recommendations
                
        except Exception as e:
            logger.error(f"❌ Error getting trade recommendations: {e}")
            return []
    
    def get_trade_executions(
        self,
        symbol: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get trade executions from main database."""
        try:
            with self.db_manager.get_main_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM trade_executions WHERE 1=1"
                params = []
                
                if symbol:
                    query += " AND symbol = ?"
                    params.append(symbol.upper())
                
                query += " ORDER BY execution_time DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to list of dicts
                columns = [description[0] for description in cursor.description]
                executions = [dict(zip(columns, row)) for row in rows]
                
                return executions
                
        except Exception as e:
            logger.error(f"❌ Error getting trade executions: {e}")
            return []
    
    def get_trade_positions(
        self,
        symbol: str = None,
        status: str = "open"
    ) -> List[Dict[str, Any]]:
        """Get trade positions from main database."""
        try:
            with self.db_manager.get_main_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM trade_positions WHERE status = ?"
                params = [status]
                
                if symbol:
                    query += " AND symbol = ?"
                    params.append(symbol.upper())
                
                query += " ORDER BY open_time DESC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to list of dicts
                columns = [description[0] for description in cursor.description]
                positions = [dict(zip(columns, row)) for row in rows]
                
                return positions
                
        except Exception as e:
            logger.error(f"❌ Error getting trade positions: {e}")
            return []
    
    def get_trade_monitoring(
        self,
        ticket: int = None,
        monitoring_type: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get trade monitoring from logs database."""
        try:
            with self.db_manager.get_logs_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM trade_monitoring WHERE 1=1"
                params = []
                
                if ticket:
                    query += " AND ticket = ?"
                    params.append(ticket)
                
                if monitoring_type:
                    query += " AND monitoring_type = ?"
                    params.append(monitoring_type)
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to list of dicts
                columns = [description[0] for description in cursor.description]
                monitoring = [dict(zip(columns, row)) for row in rows]
                
                return monitoring
                
        except Exception as e:
            logger.error(f"❌ Error getting trade monitoring: {e}")
            return []
    
    def get_trade_alerts(
        self,
        ticket: int = None,
        alert_type: str = None,
        sent: bool = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get trade alerts from logs database."""
        try:
            with self.db_manager.get_logs_db_connection(read_only=True) as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM trade_alerts WHERE 1=1"
                params = []
                
                if ticket:
                    query += " AND ticket = ?"
                    params.append(ticket)
                
                if alert_type:
                    query += " AND alert_type = ?"
                    params.append(alert_type)
                
                if sent is not None:
                    query += " AND sent = ?"
                    params.append(sent)
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to list of dicts
                columns = [description[0] for description in cursor.description]
                alerts = [dict(zip(columns, row)) for row in rows]
                
                return alerts
                
        except Exception as e:
            logger.error(f"❌ Error getting trade alerts: {e}")
            return []
    
    def get_trade_summary(self) -> Dict[str, Any]:
        """Get comprehensive trade summary from all databases."""
        try:
            summary = {
                'recommendations': {
                    'total': 0,
                    'pending': 0,
                    'executed': 0,
                    'completed': 0
                },
                'executions': {
                    'total': 0,
                    'today': 0
                },
                'positions': {
                    'open': 0,
                    'closed': 0
                },
                'monitoring': {
                    'active': 0,
                    'alerts': 0
                }
            }
            
            # Get recommendations summary
            recommendations = self.get_trade_recommendations(limit=1000)
            summary['recommendations']['total'] = len(recommendations)
            summary['recommendations']['pending'] = len([r for r in recommendations if r['status'] == 'pending'])
            summary['recommendations']['executed'] = len([r for r in recommendations if r['status'] == 'executed'])
            summary['recommendations']['completed'] = len([r for r in recommendations if r['outcome'] is not None])
            
            # Get executions summary
            executions = self.get_trade_executions(limit=1000)
            summary['executions']['total'] = len(executions)
            today = datetime.now().date()
            summary['executions']['today'] = len([e for e in executions if datetime.fromisoformat(e['execution_time']).date() == today])
            
            # Get positions summary
            open_positions = self.get_trade_positions(status='open')
            closed_positions = self.get_trade_positions(status='closed')
            summary['positions']['open'] = len(open_positions)
            summary['positions']['closed'] = len(closed_positions)
            
            # Get monitoring summary
            monitoring = self.get_trade_monitoring(limit=1000)
            alerts = self.get_trade_alerts(limit=1000)
            summary['monitoring']['active'] = len([m for m in monitoring if m['status'] == 'active'])
            summary['monitoring']['alerts'] = len(alerts)
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error getting trade summary: {e}")
            return {}

# Global instances for different processes
_trade_integration_instances = {}

def get_trade_integration(process_type: str = "unknown") -> TradeDataIntegrationSeparateDatabases:
    """Get trade integration instance for specific process type."""
    if process_type not in _trade_integration_instances:
        _trade_integration_instances[process_type] = TradeDataIntegrationSeparateDatabases(process_type)
    return _trade_integration_instances[process_type]

# Convenience functions for easy access
def log_trade_recommendation(process_type: str, **kwargs) -> int:
    """Log trade recommendation."""
    integration = get_trade_integration(process_type)
    return integration.log_trade_recommendation(**kwargs)

def log_trade_execution(process_type: str, **kwargs) -> bool:
    """Log trade execution."""
    integration = get_trade_integration(process_type)
    return integration.log_trade_execution(**kwargs)

def log_trade_monitoring(process_type: str, **kwargs) -> bool:
    """Log trade monitoring."""
    integration = get_trade_integration(process_type)
    return integration.log_trade_monitoring(**kwargs)

if __name__ == "__main__":
    # Test the trade data integration
    print("Testing Trade Data Integration for Separate Database Architecture...")
    
    # Test ChatGPT Bot integration
    chatgpt_integration = get_trade_integration("chatgpt_bot")
    print(f"ChatGPT Bot integration: {chatgpt_integration.process_type}")
    
    # Test Desktop Agent integration
    desktop_integration = get_trade_integration("desktop_agent")
    print(f"Desktop Agent integration: {desktop_integration.process_type}")
    
    # Test API Server integration
    api_integration = get_trade_integration("api_server")
    print(f"API Server integration: {api_integration.process_type}")
    
    print("Trade Data Integration test completed!")
