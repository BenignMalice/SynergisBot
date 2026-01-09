"""
Strategy Performance Tracker

Tracks performance metrics for each strategy:
- Win rate
- Average R:R
- Total trades
- Consecutive losses
- Current drawdown
- Equity curve

Integrates with JournalRepo to record trade results.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)


class StrategyPerformanceTracker:
    """Track performance metrics per strategy"""
    
    def __init__(self, db_path: str = "data/strategy_performance.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize performance tracking database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Strategy performance summary table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS strategy_performance (
                    strategy_name TEXT PRIMARY KEY,
                    total_trades INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    breakevens INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0.0,
                    avg_rr REAL DEFAULT 0.0,
                    total_pnl REAL DEFAULT 0.0,
                    max_equity REAL DEFAULT 0.0,
                    current_equity REAL DEFAULT 0.0,
                    current_drawdown_pct REAL DEFAULT 0.0,
                    consecutive_losses INTEGER DEFAULT 0,
                    consecutive_wins INTEGER DEFAULT 0,
                    last_trade_time TEXT,
                    last_updated TEXT
                )
            """)
            
            # Individual trade results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    symbol TEXT,
                    result TEXT,  -- 'win', 'loss', 'breakeven'
                    pnl REAL,
                    rr REAL,
                    entry_price REAL,
                    exit_price REAL,
                    entry_time TEXT,
                    exit_time TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    regime TEXT  -- Volatility regime at trade time
                )
            """)
            
            # Add regime column if it doesn't exist (migration)
            try:
                cursor.execute("ALTER TABLE trade_results ADD COLUMN regime TEXT")
            except sqlite3.OperationalError:
                # Column already exists, ignore
                pass
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_results_strategy 
                ON trade_results(strategy_name, created_at DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_results_time 
                ON trade_results(created_at DESC)
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize performance tracker database: {e}")
    
    def record_trade(
        self,
        strategy_name: str,
        symbol: str,
        result: str,  # 'win', 'loss', 'breakeven'
        pnl: float,
        rr: Optional[float] = None,
        entry_price: Optional[float] = None,
        exit_price: Optional[float] = None,
        entry_time: Optional[str] = None,
        exit_time: Optional[str] = None,
        regime: Optional[str] = None
    ):
        """Record a trade result"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Insert trade result
            cursor.execute("""
                INSERT INTO trade_results 
                (strategy_name, symbol, result, pnl, rr, entry_price, exit_price, entry_time, exit_time, regime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (strategy_name, symbol, result, pnl, rr, entry_price, exit_price, entry_time, exit_time, regime))
            
            # Update strategy performance metrics
            self._update_metrics(cursor, strategy_name, result, pnl, rr)
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Recorded trade for {strategy_name}: {result}, PnL: {pnl:.2f}")
        except Exception as e:
            logger.error(f"Failed to record trade for {strategy_name}: {e}")
    
    def _update_metrics(
        self,
        cursor: sqlite3.Cursor,
        strategy_name: str,
        result: str,
        pnl: float,
        rr: Optional[float]
    ):
        """Update strategy performance metrics"""
        try:
            # Get current metrics
            cursor.execute("""
                SELECT total_trades, wins, losses, breakevens, total_pnl, 
                       max_equity, current_equity, consecutive_losses, consecutive_wins
                FROM strategy_performance
                WHERE strategy_name = ?
            """, (strategy_name,))
            
            row = cursor.fetchone()
            timestamp = datetime.now().isoformat()
            
            if row:
                # Update existing
                total_trades = row[0] + 1
                wins = row[1] + (1 if result == "win" else 0)
                losses = row[2] + (1 if result == "loss" else 0)
                breakevens = row[3] + (1 if result == "breakeven" else 0)
                total_pnl = row[4] + pnl
                
                # Calculate win rate
                win_rate = wins / total_trades if total_trades > 0 else 0.0
                
                # Update consecutive losses/wins
                consecutive_losses = 0 if result == "win" else (row[7] + 1 if result == "loss" else row[7])
                consecutive_wins = 0 if result == "loss" else (row[8] + 1 if result == "win" else row[8])
                
                # Update equity
                # FIX: Use INITIAL_EQUITY from settings or fallback
                initial_equity = getattr(settings, "INITIAL_EQUITY", 10000.0)
                current_equity = initial_equity + total_pnl
                max_equity = max(row[5], current_equity) if row[5] else current_equity
                
                # Calculate drawdown
                current_drawdown_pct = ((max_equity - current_equity) / max_equity * 100) if max_equity > 0 else 0.0
                
                # Calculate average RR (if RR provided)
                # Get all RR values for this strategy
                cursor.execute("""
                    SELECT AVG(rr) FROM trade_results 
                    WHERE strategy_name = ? AND rr IS NOT NULL
                """, (strategy_name,))
                avg_rr_row = cursor.fetchone()
                avg_rr = avg_rr_row[0] if avg_rr_row and avg_rr_row[0] else 0.0
                
                cursor.execute("""
                    UPDATE strategy_performance
                    SET total_trades = ?, wins = ?, losses = ?, breakevens = ?,
                        win_rate = ?, avg_rr = ?, total_pnl = ?,
                        max_equity = ?, current_equity = ?, current_drawdown_pct = ?,
                        consecutive_losses = ?, consecutive_wins = ?,
                        last_trade_time = ?, last_updated = ?
                    WHERE strategy_name = ?
                """, (
                    total_trades, wins, losses, breakevens, win_rate, avg_rr, total_pnl,
                    max_equity, current_equity, current_drawdown_pct,
                    consecutive_losses, consecutive_wins, timestamp, timestamp,
                    strategy_name
                ))
            else:
                # Insert new strategy
                initial_equity = getattr(settings, "INITIAL_EQUITY", 10000.0)
                current_equity = initial_equity + pnl
                
                wins = 1 if result == "win" else 0
                losses = 1 if result == "loss" else 0
                breakevens = 1 if result == "breakeven" else 0
                win_rate = 1.0 if result == "win" else 0.0
                consecutive_losses = 1 if result == "loss" else 0
                consecutive_wins = 1 if result == "win" else 0
                avg_rr = rr if rr else 0.0
                
                cursor.execute("""
                    INSERT INTO strategy_performance
                    (strategy_name, total_trades, wins, losses, breakevens, win_rate,
                     avg_rr, total_pnl, max_equity, current_equity, current_drawdown_pct,
                     consecutive_losses, consecutive_wins, last_trade_time, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    strategy_name, 1, wins, losses, breakevens, win_rate,
                    avg_rr, pnl, current_equity, current_equity, 0.0,
                    consecutive_losses, consecutive_wins, timestamp, timestamp
                ))
        except Exception as e:
            logger.error(f"Failed to update metrics for {strategy_name}: {e}")
    
    def get_metrics(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get performance metrics for a strategy"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT total_trades, wins, losses, breakevens, win_rate, avg_rr,
                       total_pnl, max_equity, current_equity, current_drawdown_pct,
                       consecutive_losses, consecutive_wins, last_trade_time
                FROM strategy_performance
                WHERE strategy_name = ?
            """, (strategy_name,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "total_trades": row[0],
                    "wins": row[1],
                    "losses": row[2],
                    "breakevens": row[3],
                    "win_rate": row[4],
                    "avg_rr": row[5],
                    "total_pnl": row[6],
                    "max_equity": row[7],
                    "current_equity": row[8],
                    "current_drawdown_pct": row[9],
                    "consecutive_losses": row[10],
                    "consecutive_wins": row[11],
                    "last_trade_time": row[12]
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get metrics for {strategy_name}: {e}")
            return None
    
    def get_recent_trades(self, strategy_name: str, limit: int = 10, hours: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent trades for a strategy"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            if hours:
                cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
                cursor.execute("""
                    SELECT result, pnl, rr, symbol, entry_time, exit_time
                    FROM trade_results
                    WHERE strategy_name = ? AND created_at >= ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (strategy_name, cutoff_time, limit))
            else:
                cursor.execute("""
                    SELECT result, pnl, rr, symbol, entry_time, exit_time
                    FROM trade_results
                    WHERE strategy_name = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (strategy_name, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "result": row[0],
                    "pnl": row[1],
                    "rr": row[2],
                    "symbol": row[3],
                    "entry_time": row[4],
                    "exit_time": row[5]
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get recent trades for {strategy_name}: {e}")
            return []
    
    def get_all_strategies(self) -> List[str]:
        """Get list of all tracked strategies"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT strategy_name FROM strategy_performance
                ORDER BY strategy_name
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Failed to get strategy list: {e}")
            return []
    
    def get_strategy_stats_by_regime(
        self,
        symbol: str,
        strategy_name: str,
        current_regime: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get historical performance stats for strategy in similar regime.
        
        Args:
            symbol: Trading symbol (e.g., "XAUUSDc")
            strategy_name: Strategy name (e.g., "INSIDE_BAR_VOLATILITY_TRAP")
            current_regime: Current volatility regime (e.g., "STABLE", "VOLATILE", "stable_vol_range_compression")
        
        Returns:
            {
                "strategy": "INSIDE_BAR_VOLATILITY_TRAP",
                "regime": "stable_vol_range_compression",  # Matched regime
                "sample_size": 47,  # Number of trades in similar regime
                "win_rate": 0.62,  # 0.0 to 1.0
                "avg_rr": 1.9,  # Average risk:reward
                "max_drawdown_rr": -1.3,  # Worst case R:R
                "median_holding_time_minutes": 95,
                "confidence": "high",  # "high" | "medium" | "low" (based on sample size)
                "regime_match_quality": "exact"  # "exact" | "fuzzy" | "approximate"
            }
            OR None if no data available
        """
        try:
            # Define regime mapping for fuzzy matching
            REGIME_MAPPING = {
                "STABLE": ["STABLE", "stable", "low", "compression", "stable_vol_range_compression"],
                "VOLATILE": ["VOLATILE", "volatile", "high", "expansion", "volatile_expansion"],
                "TRANSITIONAL": ["TRANSITIONAL", "transitional", "medium", "increasing"],
                "PRE_BREAKOUT_TENSION": ["PRE_BREAKOUT_TENSION", "pre_breakout", "compression"],
                "POST_BREAKOUT_DECAY": ["POST_BREAKOUT_DECAY", "post_breakout", "expansion"],
                "FRAGMENTED_CHOP": ["FRAGMENTED_CHOP", "chop", "fragmented"],
                "SESSION_SWITCH_FLARE": ["SESSION_SWITCH_FLARE", "session_switch"]
            }
            
            # Find matching regimes
            matching_regimes = []
            regime_match_quality = "approximate"
            
            # 1. Try exact match
            matching_regimes = [current_regime]
            regime_match_quality = "exact"
            
            # 2. Try fuzzy match via mapping
            if not matching_regimes or len(matching_regimes) == 0:
                for key, values in REGIME_MAPPING.items():
                    if current_regime.upper() in [v.upper() for v in values] or any(
                        v.upper() in current_regime.upper() for v in values
                    ):
                        matching_regimes = values
                        regime_match_quality = "fuzzy"
                        break
            
            # 3. If still no match, try case-insensitive partial match
            if not matching_regimes or len(matching_regimes) == 0:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT regime FROM trade_results
                    WHERE strategy_name = ? AND symbol = ? AND regime IS NOT NULL
                """, (strategy_name, symbol))
                existing_regimes = [row[0] for row in cursor.fetchall()]
                conn.close()
                
                # Find closest match
                current_upper = current_regime.upper()
                for existing in existing_regimes:
                    if existing and (current_upper in existing.upper() or existing.upper() in current_upper):
                        matching_regimes = [existing]
                        regime_match_quality = "approximate"
                        break
            
            # Query trade results filtered by strategy + regime
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            if matching_regimes:
                placeholders = ",".join(["?"] * len(matching_regimes))
                cursor.execute(f"""
                    SELECT result, rr, entry_time, exit_time
                    FROM trade_results
                    WHERE strategy_name = ? AND symbol = ? AND regime IN ({placeholders})
                    ORDER BY created_at DESC
                """, (strategy_name, symbol) + tuple(matching_regimes))
            else:
                # No regime match, return None
                conn.close()
                return None
            
            rows = cursor.fetchall()
            conn.close()
            
            if len(rows) < 10:
                # Insufficient data
                return None
            
            # Calculate stats from filtered trades
            wins = sum(1 for row in rows if row[0] == "win")
            losses = sum(1 for row in rows if row[0] == "loss")
            sample_size = len(rows)
            win_rate = wins / sample_size if sample_size > 0 else 0.0
            
            # Calculate average RR
            rr_values = [row[1] for row in rows if row[1] is not None]
            avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0.0
            
            # Calculate max drawdown RR (worst case R:R)
            max_drawdown_rr = min(rr_values) if rr_values else 0.0
            
            # Calculate median holding time
            holding_times = []
            for row in rows:
                if row[2] and row[3]:  # entry_time and exit_time
                    try:
                        entry_dt = datetime.fromisoformat(row[2])
                        exit_dt = datetime.fromisoformat(row[3])
                        duration = (exit_dt - entry_dt).total_seconds() / 60  # minutes
                        holding_times.append(duration)
                    except (ValueError, TypeError):
                        pass
            
            median_holding_time_minutes = 0
            if holding_times:
                holding_times.sort()
                mid = len(holding_times) // 2
                median_holding_time_minutes = (
                    holding_times[mid] if len(holding_times) % 2 == 1
                    else (holding_times[mid - 1] + holding_times[mid]) / 2
                )
            
            # Determine confidence
            if (regime_match_quality in ["exact", "fuzzy"]) and sample_size >= 30:
                confidence = "high"
            elif sample_size >= 10:
                confidence = "medium"
            else:
                confidence = "low"
            
            # Use matched regime (first one if multiple)
            matched_regime = matching_regimes[0] if matching_regimes else current_regime
            
            return {
                "strategy": strategy_name,
                "regime": matched_regime,
                "sample_size": sample_size,
                "win_rate": round(win_rate, 3),
                "avg_rr": round(avg_rr, 2) if avg_rr else None,
                "max_drawdown_rr": round(max_drawdown_rr, 2) if max_drawdown_rr else None,
                "median_holding_time_minutes": round(median_holding_time_minutes, 1) if median_holding_time_minutes else None,
                "confidence": confidence,
                "regime_match_quality": regime_match_quality
            }
            
        except Exception as e:
            logger.error(f"Failed to get strategy stats by regime for {strategy_name} in {current_regime}: {e}")
            return None

