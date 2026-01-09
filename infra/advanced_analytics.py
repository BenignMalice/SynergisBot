"""
V8 Feature Analytics & Performance Tracking
===========================================

Tracks V8 feature performance, importance, and predictive power.
Implements feature weighting based on win rates and contribution analysis.

Anchors:
    # === ANCHOR: IMPORTS ===
    # === ANCHOR: FEATURE_TRACKER ===
    # === ANCHOR: IMPORTANCE_CALCULATOR ===
    # === ANCHOR: WEIGHT_OPTIMIZER ===
    # === ANCHOR: DATABASE_SCHEMA ===
"""

from __future__ import annotations

# === ANCHOR: IMPORTS ===
import logging
import sqlite3
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json
from pathlib import Path

logger = logging.getLogger(__name__)

# === ANCHOR: DATABASE_SCHEMA ===
DB_PATH = Path("data/advanced_analytics.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS advanced_trade_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    sl REAL,
    tp REAL,
    timestamp TEXT NOT NULL,
    
    -- Advanced Features at trade time
    rmag_ema200_atr REAL,
    rmag_vwap_atr REAL,
    ema50_slope REAL,
    ema200_slope REAL,
    vol_trend_state TEXT,
    vol_trend_bb_width REAL,
    vol_trend_adx REAL,
    pressure_ratio REAL,
    pressure_rsi REAL,
    pressure_adx REAL,
    candle_type TEXT,
    candle_body_atr REAL,
    candle_w2b REAL,
    liquidity_pdl_dist_atr REAL,
    liquidity_pdh_dist_atr REAL,
    liquidity_equal_highs INTEGER,
    liquidity_equal_lows INTEGER,
    fvg_type TEXT,
    fvg_dist_atr REAL,
    vwap_dev_atr REAL,
    vwap_zone TEXT,
    accel_macd_slope REAL,
    accel_rsi_slope REAL,
    mtf_total INTEGER,
    mtf_max INTEGER,
    vp_hvn_dist_atr REAL,
    vp_lvn_dist_atr REAL,
    
    -- Trade outcome
    outcome TEXT,  -- 'win', 'loss', 'breakeven', 'open'
    exit_price REAL,
    profit_loss REAL,
    r_multiple REAL,
    exit_timestamp TEXT,
    duration_minutes INTEGER
);

CREATE INDEX IF NOT EXISTS idx_ticket ON advanced_trade_features(ticket);
CREATE INDEX IF NOT EXISTS idx_symbol ON advanced_trade_features(symbol);
CREATE INDEX IF NOT EXISTS idx_timestamp ON advanced_trade_features(timestamp);
CREATE INDEX IF NOT EXISTS idx_outcome ON advanced_trade_features(outcome);

CREATE TABLE IF NOT EXISTS advanced_feature_importance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_name TEXT NOT NULL UNIQUE,
    total_trades INTEGER DEFAULT 0,
    win_count INTEGER DEFAULT 0,
    loss_count INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    avg_r_when_present REAL DEFAULT 0.0,
    avg_r_when_absent REAL DEFAULT 0.0,
    importance_score REAL DEFAULT 0.0,
    weight REAL DEFAULT 1.0,
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS advanced_feature_combinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    combination_hash TEXT NOT NULL UNIQUE,
    feature_list TEXT NOT NULL,
    total_trades INTEGER DEFAULT 0,
    win_count INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    avg_r_multiple REAL DEFAULT 0.0,
    last_updated TEXT NOT NULL
);
"""

# === ANCHOR: FEATURE_TRACKER ===
@dataclass
class AdvancedTradeRecord:
    """Record of a trade with its Advanced features"""
    ticket: int
    symbol: str
    direction: str
    entry_price: float
    sl: Optional[float]
    tp: Optional[float]
    timestamp: str
    
    # Advanced Features
    rmag_ema200_atr: Optional[float] = None
    rmag_vwap_atr: Optional[float] = None
    ema50_slope: Optional[float] = None
    ema200_slope: Optional[float] = None
    vol_trend_state: Optional[str] = None
    vol_trend_bb_width: Optional[float] = None
    vol_trend_adx: Optional[float] = None
    pressure_ratio: Optional[float] = None
    pressure_rsi: Optional[float] = None
    pressure_adx: Optional[float] = None
    candle_type: Optional[str] = None
    candle_body_atr: Optional[float] = None
    candle_w2b: Optional[float] = None
    liquidity_pdl_dist_atr: Optional[float] = None
    liquidity_pdh_dist_atr: Optional[float] = None
    liquidity_equal_highs: Optional[int] = None
    liquidity_equal_lows: Optional[int] = None
    fvg_type: Optional[str] = None
    fvg_dist_atr: Optional[float] = None
    vwap_dev_atr: Optional[float] = None
    vwap_zone: Optional[str] = None
    accel_macd_slope: Optional[float] = None
    accel_rsi_slope: Optional[float] = None
    mtf_total: Optional[int] = None
    mtf_max: Optional[int] = None
    vp_hvn_dist_atr: Optional[float] = None
    vp_lvn_dist_atr: Optional[float] = None
    
    # Outcome (filled later)
    outcome: Optional[str] = None
    exit_price: Optional[float] = None
    profit_loss: Optional[float] = None
    r_multiple: Optional[float] = None
    exit_timestamp: Optional[str] = None
    duration_minutes: Optional[int] = None


class AdvancedFeatureTracker:
    """
    Tracks V8 feature values for each trade and their outcomes.
    Stores in SQLite for analysis and feature importance calculation.
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._init_database()
    
    def _init_database(self):
        """Initialize database with schema"""
        try:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            conn.executescript(SCHEMA)
            conn.commit()
            conn.close()
            
            logger.info("✅ V8 analytics database initialized")
        except Exception as e:
            logger.error(f"Error initializing V8 analytics database: {e}", exc_info=True)
    
    def record_trade_entry(
        self, 
        ticket: int, 
        symbol: str, 
        direction: str,
        entry_price: float,
        sl: Optional[float],
        tp: Optional[float],
        advanced_features: Optional[Dict[str, Any]]
    ) -> bool:
        """
        Record a trade entry with its Advanced features.
        
        Args:
            ticket: MT5 ticket number
            symbol: Trading symbol
            direction: "BUY" or "SELL"
            entry_price: Entry price
            sl: Stop loss price
            tp: Take profit price
            advanced_features: V8 feature dict from feature_builder_advanced
        
        Returns:
            True if recorded successfully
        """
        try:
            # Extract Advanced features from the dict
            record = self._extract_advanced_features(
                ticket=ticket,
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                sl=sl,
                tp=tp,
                advanced_features=advanced_features
            )
            
            # Insert into database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Convert record to dict for insertion
            record_dict = asdict(record)
            
            # Prepare SQL
            columns = list(record_dict.keys())
            placeholders = ["?" for _ in columns]
            
            sql = f"""
                INSERT INTO advanced_trade_features ({", ".join(columns)})
                VALUES ({", ".join(placeholders)})
            """
            
            cursor.execute(sql, list(record_dict.values()))
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Recorded Advanced features for trade #{ticket}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording trade entry: {e}", exc_info=True)
            return False
    
    def update_trade_outcome(
        self,
        ticket: int,
        outcome: str,
        exit_price: float,
        profit_loss: float,
        r_multiple: float
    ) -> bool:
        """
        Update trade outcome after closure.
        
        Args:
            ticket: MT5 ticket number
            outcome: "win", "loss", or "breakeven"
            exit_price: Exit price
            profit_loss: Profit/loss in currency
            r_multiple: R-multiple achieved
        
        Returns:
            True if updated successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get entry timestamp to calculate duration
            cursor.execute(
                "SELECT timestamp FROM advanced_trade_features WHERE ticket = ?",
                (ticket,)
            )
            row = cursor.fetchone()
            
            if not row:
                logger.warning(f"Trade #{ticket} not found in database")
                return False
            
            entry_time = datetime.fromisoformat(row[0])
            exit_time = datetime.now()
            duration_minutes = int((exit_time - entry_time).total_seconds() / 60)
            
            # Update outcome
            cursor.execute("""
                UPDATE advanced_trade_features
                SET outcome = ?,
                    exit_price = ?,
                    profit_loss = ?,
                    r_multiple = ?,
                    exit_timestamp = ?,
                    duration_minutes = ?
                WHERE ticket = ?
            """, (outcome, exit_price, profit_loss, r_multiple, exit_time.isoformat(), duration_minutes, ticket))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Updated outcome for trade #{ticket}: {outcome} ({r_multiple:.2f}R)")
            
            # Trigger feature importance recalculation
            self._update_feature_importance()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating trade outcome: {e}", exc_info=True)
            return False
    
    def _extract_advanced_features(
        self,
        ticket: int,
        symbol: str,
        direction: str,
        entry_price: float,
        sl: Optional[float],
        tp: Optional[float],
        advanced_features: Optional[Dict[str, Any]]
    ) -> AdvancedTradeRecord:
        """Extract Advanced features from the dict into a structured record"""
        record = AdvancedTradeRecord(
            ticket=ticket,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            sl=sl,
            tp=tp,
            timestamp=datetime.now().isoformat()
        )
        
        if not advanced_features or not isinstance(advanced_features, dict):
            return record
        
        # Get M5 features (primary timeframe)
        features = advanced_features.get("features", {})
        m5_features = features.get("M5", {})
        
        # Extract RMAG
        rmag = m5_features.get("rmag", {})
        record.rmag_ema200_atr = rmag.get("ema200_atr")
        record.rmag_vwap_atr = rmag.get("vwap_atr")
        
        # Extract EMA Slope
        ema_slope = m5_features.get("ema_slope", {})
        record.ema50_slope = ema_slope.get("ema50")
        record.ema200_slope = ema_slope.get("ema200")
        
        # Extract Vol Trend
        vol_trend = m5_features.get("vol_trend", {})
        record.vol_trend_state = vol_trend.get("state")
        record.vol_trend_bb_width = vol_trend.get("bb_width")
        record.vol_trend_adx = vol_trend.get("adx")
        
        # Extract Pressure
        pressure = m5_features.get("pressure", {})
        record.pressure_ratio = pressure.get("ratio")
        record.pressure_rsi = pressure.get("rsi")
        record.pressure_adx = pressure.get("adx")
        
        # Extract Candle Profile (last candle)
        candle_profile = m5_features.get("candle_profile", [])
        if candle_profile:
            last_candle = candle_profile[-1]
            record.candle_type = last_candle.get("type")
            record.candle_body_atr = last_candle.get("body_atr")
            record.candle_w2b = last_candle.get("w2b")
        
        # Extract Liquidity
        liquidity = m5_features.get("liquidity", {})
        record.liquidity_pdl_dist_atr = liquidity.get("pdl_dist_atr")
        record.liquidity_pdh_dist_atr = liquidity.get("pdh_dist_atr")
        record.liquidity_equal_highs = 1 if liquidity.get("equal_highs") else 0
        record.liquidity_equal_lows = 1 if liquidity.get("equal_lows") else 0
        
        # Extract FVG
        fvg = m5_features.get("fvg", {})
        record.fvg_type = fvg.get("type")
        record.fvg_dist_atr = fvg.get("dist_to_fill_atr")
        
        # Extract VWAP
        vwap = m5_features.get("vwap", {})
        record.vwap_dev_atr = vwap.get("dev_atr")
        record.vwap_zone = vwap.get("zone")
        
        # Extract Acceleration
        accel = m5_features.get("accel", {})
        record.accel_macd_slope = accel.get("macd_slope")
        record.accel_rsi_slope = accel.get("rsi_slope")
        
        # Extract MTF Score
        mtf_score = features.get("mtf_score", {})
        record.mtf_total = mtf_score.get("total")
        record.mtf_max = mtf_score.get("max")
        
        # Extract Volume Profile
        vp = features.get("vp", {})
        record.vp_hvn_dist_atr = vp.get("hvn_dist_atr")
        record.vp_lvn_dist_atr = vp.get("lvn_dist_atr")
        
        return record
    
    def _update_feature_importance(self):
        """
        Recalculate feature importance based on completed trades.
        Called after each trade closure.
        """
        try:
            calculator = FeatureImportanceCalculator(self.db_path)
            calculator.calculate_all_importance()
        except Exception as e:
            logger.error(f"Error updating feature importance: {e}", exc_info=True)
    
    def get_feature_weights(self) -> Dict[str, float]:
        """
        Get current feature weights for use in risk model.
        
        Returns:
            Dict mapping feature names to weights (0.5 to 1.5)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT feature_name, weight FROM advanced_feature_importance")
            weights = {row[0]: row[1] for row in cursor.fetchall()}
            
            conn.close()
            return weights
            
        except Exception as e:
            logger.error(f"Error getting feature weights: {e}", exc_info=True)
            return {}


# === ANCHOR: IMPORTANCE_CALCULATOR ===
class FeatureImportanceCalculator:
    """
    Calculates feature importance based on historical trade outcomes.
    Uses various metrics to determine which features are most predictive.
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
    
    def calculate_all_importance(self):
        """Calculate importance for all Advanced features"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all completed trades
            cursor.execute("""
                SELECT * FROM advanced_trade_features
                WHERE outcome IN ('win', 'loss', 'breakeven')
            """)
            
            trades = cursor.fetchall()
            if len(trades) < 10:
                logger.info(f"Insufficient data for importance calculation ({len(trades)} trades)")
                conn.close()
                return
            
            # Define features to analyze
            feature_definitions = [
                ("rmag_stretched", self._is_rmag_stretched),
                ("ema_slope_quality", self._is_ema_slope_quality),
                ("vol_trend_favorable", self._is_vol_trend_favorable),
                ("pressure_quality", self._is_pressure_quality),
                ("candle_conviction", self._is_candle_conviction),
                ("near_liquidity", self._is_near_liquidity),
                ("fvg_nearby", self._is_fvg_nearby),
                ("vwap_outer", self._is_vwap_outer),
                ("momentum_accelerating", self._is_momentum_accelerating),
                ("mtf_aligned", self._is_mtf_aligned),
                ("near_hvn", self._is_near_hvn)
            ]
            
            # Calculate importance for each feature
            for feature_name, feature_func in feature_definitions:
                importance = self._calculate_feature_importance(trades, feature_func)
                self._save_feature_importance(feature_name, importance)
            
            conn.close()
            logger.info(f"✅ Updated importance for {len(feature_definitions)} features")
            
        except Exception as e:
            logger.error(f"Error calculating feature importance: {e}", exc_info=True)
    
    def _calculate_feature_importance(
        self,
        trades: List[Tuple],
        feature_func: callable
    ) -> Dict[str, Any]:
        """
        Calculate importance metrics for a specific feature.
        
        Returns:
            Dict with win_rate, avg_r_when_present, avg_r_when_absent, importance_score
        """
        present_wins = 0
        present_total = 0
        present_r_sum = 0.0
        
        absent_wins = 0
        absent_total = 0
        absent_r_sum = 0.0
        
        for trade in trades:
            # Convert tuple to dict (simplified - actual column mapping would be more complex)
            trade_dict = self._trade_tuple_to_dict(trade)
            
            is_present = feature_func(trade_dict)
            is_win = trade_dict['outcome'] == 'win'
            r_multiple = trade_dict['r_multiple'] or 0.0
            
            if is_present:
                present_total += 1
                if is_win:
                    present_wins += 1
                present_r_sum += r_multiple
            else:
                absent_total += 1
                if is_win:
                    absent_wins += 1
                absent_r_sum += r_multiple
        
        # Calculate metrics
        win_rate = (present_wins / present_total * 100) if present_total > 0 else 0.0
        avg_r_present = present_r_sum / present_total if present_total > 0 else 0.0
        avg_r_absent = absent_r_sum / absent_total if absent_total > 0 else 0.0
        
        # Importance score: how much better is win rate and R when feature is present
        win_rate_diff = win_rate - (absent_wins / absent_total * 100 if absent_total > 0 else 0)
        r_diff = avg_r_present - avg_r_absent
        
        # Combined importance score (0-100)
        importance_score = (win_rate_diff * 0.6 + r_diff * 20) * (present_total / len(trades))
        importance_score = max(0, min(100, importance_score))
        
        return {
            "total_trades": present_total,
            "win_count": present_wins,
            "loss_count": present_total - present_wins,
            "win_rate": win_rate,
            "avg_r_when_present": avg_r_present,
            "avg_r_when_absent": avg_r_absent,
            "importance_score": importance_score,
            "weight": self._score_to_weight(importance_score)
        }
    
    def _score_to_weight(self, importance_score: float) -> float:
        """Convert importance score (0-100) to weight (0.5-1.5)"""
        # Linear mapping: 0 → 0.5, 50 → 1.0, 100 → 1.5
        return 0.5 + (importance_score / 100.0)
    
    def _save_feature_importance(self, feature_name: str, metrics: Dict[str, Any]):
        """Save feature importance to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO advanced_feature_importance
                (feature_name, total_trades, win_count, loss_count, win_rate,
                 avg_r_when_present, avg_r_when_absent, importance_score, weight, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feature_name,
                metrics['total_trades'],
                metrics['win_count'],
                metrics['loss_count'],
                metrics['win_rate'],
                metrics['avg_r_when_present'],
                metrics['avg_r_when_absent'],
                metrics['importance_score'],
                metrics['weight'],
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving feature importance: {e}", exc_info=True)
    
    # Feature detection functions
    def _trade_tuple_to_dict(self, trade_tuple: Tuple) -> Dict:
        """Convert trade tuple to dict (simplified version)"""
        # In production, map tuple indices to column names from database
        return {
            'outcome': trade_tuple[27],  # Index of outcome column
            'r_multiple': trade_tuple[30],  # Index of r_multiple column
            'rmag_ema200_atr': trade_tuple[8],
            'rmag_vwap_atr': trade_tuple[9],
            'ema50_slope': trade_tuple[10],
            'ema200_slope': trade_tuple[11],
            'vol_trend_state': trade_tuple[12],
            'pressure_rsi': trade_tuple[16],
            'pressure_adx': trade_tuple[17],
            'candle_type': trade_tuple[18],
            'liquidity_pdl_dist_atr': trade_tuple[21],
            'liquidity_pdh_dist_atr': trade_tuple[22],
            'fvg_dist_atr': trade_tuple[26],
            'vwap_zone': trade_tuple[28],
            'accel_macd_slope': trade_tuple[29],
            'accel_rsi_slope': trade_tuple[30],
            'mtf_total': trade_tuple[31],
            'vp_hvn_dist_atr': trade_tuple[33]
        }
    
    def _is_rmag_stretched(self, trade: Dict) -> bool:
        """Is price stretched (RMAG > 2σ)?"""
        return abs(trade.get('rmag_ema200_atr', 0) or 0) > 2.0
    
    def _is_ema_slope_quality(self, trade: Dict) -> bool:
        """Is EMA slope indicating quality trend?"""
        ema50 = abs(trade.get('ema50_slope', 0) or 0)
        ema200 = abs(trade.get('ema200_slope', 0) or 0)
        return ema50 > 0.15 and ema200 > 0.05
    
    def _is_vol_trend_favorable(self, trade: Dict) -> bool:
        """Is volatility trend favorable?"""
        state = trade.get('vol_trend_state', '')
        return state == 'expansion_strong_trend'
    
    def _is_pressure_quality(self, trade: Dict) -> bool:
        """Is RSI-ADX pressure indicating quality?"""
        rsi = trade.get('pressure_rsi', 50) or 50
        adx = trade.get('pressure_adx', 0) or 0
        return (rsi > 60 and adx > 30) or (rsi < 40 and adx > 30)
    
    def _is_candle_conviction(self, trade: Dict) -> bool:
        """Is candle showing conviction?"""
        ctype = trade.get('candle_type', '')
        return ctype == 'conviction'
    
    def _is_near_liquidity(self, trade: Dict) -> bool:
        """Is price near liquidity zone?"""
        pdl_dist = trade.get('liquidity_pdl_dist_atr', 999) or 999
        pdh_dist = trade.get('liquidity_pdh_dist_atr', 999) or 999
        return min(pdl_dist, pdh_dist) < 0.5
    
    def _is_fvg_nearby(self, trade: Dict) -> bool:
        """Is FVG nearby?"""
        fvg_dist = trade.get('fvg_dist_atr', 999) or 999
        return fvg_dist < 1.0
    
    def _is_vwap_outer(self, trade: Dict) -> bool:
        """Is price in VWAP outer zone?"""
        zone = trade.get('vwap_zone', '')
        return zone == 'outer'
    
    def _is_momentum_accelerating(self, trade: Dict) -> bool:
        """Is momentum accelerating?"""
        macd_slope = trade.get('accel_macd_slope', 0) or 0
        rsi_slope = trade.get('accel_rsi_slope', 0) or 0
        return macd_slope > 0.03 and rsi_slope > 2.0
    
    def _is_mtf_aligned(self, trade: Dict) -> bool:
        """Is MTF aligned?"""
        mtf_total = trade.get('mtf_total', 0) or 0
        return mtf_total >= 2
    
    def _is_near_hvn(self, trade: Dict) -> bool:
        """Is price near HVN?"""
        hvn_dist = trade.get('vp_hvn_dist_atr', 999) or 999
        return hvn_dist < 0.3


# === ANCHOR: WEIGHT_OPTIMIZER ===
def get_advanced_tracker() -> AdvancedFeatureTracker:
    """Get or create Advanced feature tracker instance"""
    return AdvancedFeatureTracker()


def get_feature_weights() -> Dict[str, float]:
    """Get current feature weights (convenience function)"""
    tracker = get_advanced_tracker()
    return tracker.get_feature_weights()

