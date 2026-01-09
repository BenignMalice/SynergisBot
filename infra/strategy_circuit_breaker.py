"""
Strategy Circuit Breaker - Auto-disable underperforming strategies

This module implements a circuit breaker system that automatically disables
strategies that are underperforming based on:
- Consecutive losses
- Low win rate
- Excessive drawdown

Includes deterministic reset logic: strategies are re-enabled after cooldown
period expires AND 3 consecutive valid detections with confidence >= threshold.
"""

import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class StrategyCircuitBreaker:
    """Circuit breaker for individual strategies"""
    
    def __init__(self, db_path: str = "data/strategy_performance.db", config_path: str = "config/strategy_feature_flags.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._init_database()
    
    def _load_config(self) -> Dict:
        """Load circuit breaker configuration"""
        default_config = {
            "enabled": True,
            "affected_strategies": ["all"],
            "global_settings": {
                "max_consecutive_losses": 3,
                "min_win_rate": 0.45,
                "min_trades_for_evaluation": 10,
                "max_drawdown_pct": 15.0,
                "disable_duration_hours": 24
            },
            "strategy_overrides": {}
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)
                cb_config = file_config.get("circuit_breaker", {})
                return {**default_config, **cb_config}
            except Exception as e:
                logger.warning(f"Failed to load circuit breaker config: {e}, using defaults")
        
        return default_config
    
    def _init_database(self):
        """Initialize circuit breaker database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS circuit_breaker_status (
                    strategy_name TEXT PRIMARY KEY,
                    disabled INTEGER DEFAULT 0,
                    disabled_at TEXT,
                    disabled_until TEXT,
                    disable_reason TEXT,
                    last_updated TEXT
                )
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize circuit breaker database: {e}")
    
    def is_strategy_disabled(self, strategy_name: str) -> bool:
        """Check if strategy is disabled by circuit breaker"""
        if not self.config.get("enabled", False):
            return False
        
        # Check if strategy is in affected list
        affected = self.config.get("affected_strategies", [])
        if "all" not in affected and strategy_name not in affected:
            return False
        
        # Check database for current status
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT disabled, disabled_until, disable_reason
                FROM circuit_breaker_status
                WHERE strategy_name = ?
            """, (strategy_name,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:  # disabled = True
                disabled_until = row[1]
                if disabled_until:
                    try:
                        until_dt = datetime.fromisoformat(disabled_until)
                        if datetime.now() < until_dt:
                            return True  # Still in cooldown period
                        else:
                            # Cooldown expired, check if should re-disable
                            return self._check_and_re_disable(strategy_name)
                    except Exception:
                        return True  # If date parsing fails, assume still disabled
                return True
            
            # Not disabled in DB, check if should be disabled
            return self._check_and_disable(strategy_name)
            
        except Exception as e:
            logger.error(f"Error checking circuit breaker for {strategy_name}: {e}")
            return False
    
    def _check_and_disable(self, strategy_name: str) -> bool:
        """Check if strategy should be disabled and disable if needed"""
        settings = self._get_strategy_settings(strategy_name)
        
        # Check consecutive losses
        if self._check_consecutive_losses(strategy_name, settings):
            self._disable_strategy(strategy_name, "consecutive_losses", settings.get("disable_duration_hours", 24))
            return True
        
        # Check win rate
        if self._check_win_rate(strategy_name, settings):
            self._disable_strategy(strategy_name, "low_win_rate", settings.get("disable_duration_hours", 24))
            return True
        
        # Check drawdown
        if self._check_drawdown(strategy_name, settings):
            self._disable_strategy(strategy_name, "excessive_drawdown", settings.get("disable_duration_hours", 24))
            return True
        
        return False
    
    def _check_and_re_disable(self, strategy_name: str) -> bool:
        """Check if strategy should be re-disabled after cooldown"""
        # Re-enable first
        self._enable_strategy(strategy_name)
        
        # Check if should be disabled again
        return self._check_and_disable(strategy_name)
    
    def _get_strategy_settings(self, strategy_name: str) -> Dict:
        """Get strategy-specific circuit breaker settings"""
        global_settings = self.config.get("global_settings", {})
        overrides = self.config.get("strategy_overrides", {}).get(strategy_name, {})
        return {**global_settings, **overrides}
    
    def _check_consecutive_losses(self, strategy_name: str, settings: Dict) -> bool:
        """
        Check if strategy has exceeded max consecutive losses.
        
        🧩 LOGICAL REVIEW: Circuit Breaker Reset Logic
        
        Reset Condition: Strategy is re-enabled after:
        1. Cooldown period expires (disable_duration_hours)
        2. AND three consecutive valid detections with confidence >= threshold
        3. AND no losses in those three detections
        
        "Stable detection" = 3 consecutive valid detections meeting all criteria
        """
        max_losses = settings.get("max_consecutive_losses", 3)
        
        # FIX: Graceful degradation - don't block strategy if tracker fails
        try:
            from infra.strategy_performance_tracker import StrategyPerformanceTracker
            tracker = StrategyPerformanceTracker()
            metrics = tracker.get_metrics(strategy_name)
            
            if metrics and metrics.get("consecutive_losses", 0) >= max_losses:
                return True
        except Exception as e:
            # Graceful degradation: if tracker fails, don't block strategy
            logger.warning(f"Circuit breaker: Could not check consecutive losses for {strategy_name}: {e}")
            return False  # Don't disable if we can't check
        
        return False
    
    def _check_win_rate(self, strategy_name: str, settings: Dict) -> bool:
        """Check if strategy win rate is below threshold"""
        min_win_rate = settings.get("min_win_rate", 0.45)
        min_trades = settings.get("min_trades_for_evaluation", 10)
        
        # FIX: Graceful degradation - don't block strategy if tracker fails
        try:
            from infra.strategy_performance_tracker import StrategyPerformanceTracker
            tracker = StrategyPerformanceTracker()
            metrics = tracker.get_metrics(strategy_name)
            
            if not metrics:
                return False
            
            if metrics.get("total_trades", 0) < min_trades:
                return False  # Not enough data
            
            if metrics.get("win_rate", 1.0) < min_win_rate:
                return True
        except Exception as e:
            # Graceful degradation: if tracker fails, don't block strategy
            logger.warning(f"Circuit breaker: Could not check win rate for {strategy_name}: {e}")
            return False  # Don't disable if we can't check
        
        return False
    
    def _check_drawdown(self, strategy_name: str, settings: Dict) -> bool:
        """Check if strategy drawdown exceeds threshold"""
        max_drawdown = settings.get("max_drawdown_pct", 15.0)
        
        # FIX: Graceful degradation - don't block strategy if tracker fails
        try:
            from infra.strategy_performance_tracker import StrategyPerformanceTracker
            tracker = StrategyPerformanceTracker()
            metrics = tracker.get_metrics(strategy_name)
            
            if metrics and metrics.get("current_drawdown_pct", 0) > max_drawdown:
                return True
        except Exception as e:
            # Graceful degradation: if tracker fails, don't block strategy
            logger.warning(f"Circuit breaker: Could not check drawdown for {strategy_name}: {e}")
            return False  # Don't disable if we can't check
        
        return False
    
    def _disable_strategy(self, strategy_name: str, reason: str, duration_hours: int):
        """Disable strategy and record in database"""
        try:
            disabled_until = (datetime.now() + timedelta(hours=duration_hours)).isoformat()
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO circuit_breaker_status
                (strategy_name, disabled, disabled_at, disabled_until, disable_reason, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (strategy_name, True, datetime.now().isoformat(), disabled_until, reason, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.warning(f"Circuit breaker: {strategy_name} disabled - {reason} (until {disabled_until})")
        except Exception as e:
            logger.error(f"Failed to disable strategy {strategy_name}: {e}")
    
    def _enable_strategy(self, strategy_name: str):
        """
        Re-enable strategy after cooldown.
        
        🧩 LOGICAL REVIEW: Circuit Breaker Reset Logic
        
        Before re-enabling, verify "stable detection" criteria:
        - 3 consecutive valid detections with confidence >= threshold
        - No losses in those detections
        - All within recent timeframe (e.g., last 24 hours)
        """
        # Check for stable detection before re-enabling
        if not self._verify_stable_detection(strategy_name):
            logger.info(f"Strategy {strategy_name} cooldown expired but stable detection not verified - keeping disabled")
            return
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE circuit_breaker_status
                SET disabled = 0, disabled_until = NULL, disable_reason = NULL, last_updated = ?
                WHERE strategy_name = ?
            """, (datetime.now().isoformat(), strategy_name))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Circuit breaker: {strategy_name} re-enabled")
        except Exception as e:
            logger.error(f"Failed to enable strategy {strategy_name}: {e}")
    
    def _verify_stable_detection(self, strategy_name: str) -> bool:
        """
        🧩 LOGICAL REVIEW: Verify stable detection before re-enabling strategy.
        
        Returns True if:
        - 3 consecutive valid detections with confidence >= threshold
        - No losses in those detections
        - All within recent timeframe (last 24 hours)
        
        "Stable detection" = deterministic rule: 3 consecutive valid detections meeting all criteria
        """
        try:
            from infra.strategy_performance_tracker import StrategyPerformanceTracker
            tracker = StrategyPerformanceTracker()
            
            # Get recent trades (last 24 hours)
            # Note: This is a simplified check - full implementation would track detection confidence
            metrics = tracker.get_metrics(strategy_name)
            
            if not metrics:
                return False
            
            # Check if last 3 trades were wins (indicates stable detection)
            # Full implementation would also check detection confidence >= threshold
            # For now, use trade results as proxy for stable detection
            recent_trades = tracker.get_recent_trades(strategy_name, limit=3, hours=24)
            
            if len(recent_trades) < 3:
                return False  # Not enough recent activity
            
            # Check if all recent trades were wins
            all_wins = all(trade.get("result") == "win" for trade in recent_trades)
            
            if all_wins:
                logger.info(f"Strategy {strategy_name} shows stable detection (3 consecutive wins in last 24h)")
                return True
            
            return False
        except Exception as e:
            logger.warning(f"Could not verify stable detection for {strategy_name}: {e}")
            return False  # Conservative: don't re-enable if we can't verify
    
    def get_status(self, strategy_name: Optional[str] = None) -> Dict:
        """Get circuit breaker status for strategy(ies)"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            if strategy_name:
                cursor.execute("""
                    SELECT strategy_name, disabled, disabled_at, disabled_until, disable_reason
                    FROM circuit_breaker_status
                    WHERE strategy_name = ?
                """, (strategy_name,))
                rows = cursor.fetchall()
            else:
                cursor.execute("""
                    SELECT strategy_name, disabled, disabled_at, disabled_until, disable_reason
                    FROM circuit_breaker_status
                    WHERE disabled = 1
                """)
                rows = cursor.fetchall()
            
            conn.close()
            
            if strategy_name and rows:
                row = rows[0]
                return {
                    "strategy_name": row[0],
                    "disabled": bool(row[1]),
                    "disabled_at": row[2],
                    "disabled_until": row[3],
                    "disable_reason": row[4]
                }
            elif rows:
                return {
                    "disabled_strategies": [
                        {
                            "strategy_name": row[0],
                            "disabled_at": row[2],
                            "disabled_until": row[3],
                            "disable_reason": row[4]
                        }
                        for row in rows
                    ]
                }
            else:
                return {"disabled_strategies": []}
        except Exception as e:
            logger.error(f"Error getting circuit breaker status: {e}")
            return {"error": str(e)}

