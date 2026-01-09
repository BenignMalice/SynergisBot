"""
ML Training Data Exporter
Export recommendation data for machine learning analysis
"""

import sqlite3
import json
import csv
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MLExporter:
    """Export data for machine learning training"""
    
    def __init__(self, db_path: str = "data/journal.sqlite"):
        self.db_path = Path(db_path)
    
    def export_recommendations_csv(
        self,
        output_file: str = "data/ml_recommendations.csv",
        days: Optional[int] = None
    ) -> str:
        """
        Export AI recommendations to CSV for ML training
        
        Returns path to exported file
        """
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        # Build query
        if days:
            import time
            cutoff = int(time.time()) - (days * 86400)
            cur.execute("""
                SELECT 
                    symbol,
                    direction,
                    confidence,
                    entry_price,
                    stop_loss,
                    take_profit,
                    risk_reward,
                    market_regime,
                    executed,
                    result_pnl,
                    result_r,
                    created_at
                FROM ai_recommendations
                WHERE created_at > ?
                ORDER BY created_at DESC
            """, (cutoff,))
        else:
            cur.execute("""
                SELECT 
                    symbol,
                    direction,
                    confidence,
                    entry_price,
                    stop_loss,
                    take_profit,
                    risk_reward,
                    market_regime,
                    executed,
                    result_pnl,
                    result_r,
                    created_at
                FROM ai_recommendations
                ORDER BY created_at DESC
            """)
        
        rows = cur.fetchall()
        con.close()
        
        # Write CSV
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'symbol', 'direction', 'confidence', 'entry_price',
                'stop_loss', 'take_profit', 'risk_reward', 'regime',
                'executed', 'result_pnl', 'result_r', 'timestamp',
                'success'  # Binary target variable
            ])
            
            # Data
            for row in rows:
                # Add success column (1 if profitable, 0 if loss, None if not executed)
                success = None
                if row[8] == 1 and row[9] is not None:  # executed and has result
                    success = 1 if row[9] > 0 else 0
                
                writer.writerow(list(row) + [success])
        
        logger.info(f"Exported {len(rows)} recommendations to {output_path}")
        return str(output_path)
    
    def export_feature_matrix(
        self,
        output_file: str = "data/ml_features.json",
        days: Optional[int] = None
    ) -> str:
        """
        Export feature matrix with additional computed features
        
        Returns path to exported file
        """
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        # Build query
        if days:
            import time
            cutoff = int(time.time()) - (days * 86400)
            where_clause = f"WHERE created_at > {cutoff}"
        else:
            where_clause = ""
        
        cur.execute(f"""
            SELECT 
                id,
                symbol,
                direction,
                confidence,
                entry_price,
                stop_loss,
                take_profit,
                risk_reward,
                market_regime,
                executed,
                result_pnl,
                result_r,
                created_at
            FROM ai_recommendations
            {where_clause}
            ORDER BY created_at DESC
        """)
        
        rows = cur.fetchall()
        con.close()
        
        # Build feature matrix
        features = []
        for row in rows:
            rec_id, symbol, direction, confidence, entry, sl, tp, rr, regime, executed, pnl, r_mult, ts = row
            
            # Compute additional features
            risk_distance = abs(entry - sl) if entry and sl else None
            reward_distance = abs(tp - entry) if entry and tp else None
            
            # Binary outcome
            success = None
            if executed == 1 and pnl is not None:
                success = 1 if pnl > 0 else 0
            
            feature_dict = {
                "id": rec_id,
                "symbol": symbol,
                "direction": direction,
                "confidence": confidence,
                "risk_reward": rr,
                "regime": regime,
                "risk_distance": risk_distance,
                "reward_distance": reward_distance,
                "executed": executed,
                "result_pnl": pnl,
                "result_r": r_mult,
                "success": success,
                "timestamp": ts
            }
            
            features.append(feature_dict)
        
        # Write JSON
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "count": len(features),
                "features": features
            }, f, indent=2)
        
        logger.info(f"Exported {len(features)} feature vectors to {output_path}")
        return str(output_path)
    
    def export_time_series(
        self,
        symbol: str,
        output_file: str = "data/ml_timeseries.json",
        days: Optional[int] = None
    ) -> str:
        """
        Export time series data for a specific symbol
        
        Returns path to exported file
        """
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        # Get recommendations
        if days:
            import time
            cutoff = int(time.time()) - (days * 86400)
            cur.execute("""
                SELECT 
                    created_at,
                    direction,
                    confidence,
                    risk_reward,
                    market_regime,
                    executed,
                    result_pnl,
                    result_r
                FROM ai_recommendations
                WHERE symbol = ? AND created_at > ?
                ORDER BY created_at ASC
            """, (symbol, cutoff))
        else:
            cur.execute("""
                SELECT 
                    created_at,
                    direction,
                    confidence,
                    risk_reward,
                    market_regime,
                    executed,
                    result_pnl,
                    result_r
                FROM ai_recommendations
                WHERE symbol = ?
                ORDER BY created_at ASC
            """, (symbol,))
        
        rows = cur.fetchall()
        con.close()
        
        # Build time series
        series = []
        cumulative_pnl = 0.0
        cumulative_r = 0.0
        
        for row in rows:
            ts, direction, confidence, rr, regime, executed, pnl, r_mult = row
            
            if executed == 1 and pnl is not None:
                cumulative_pnl += pnl
            if executed == 1 and r_mult is not None:
                cumulative_r += r_mult
            
            series.append({
                "timestamp": ts,
                "direction": direction,
                "confidence": confidence,
                "risk_reward": rr,
                "regime": regime,
                "executed": executed,
                "result_pnl": pnl,
                "result_r": r_mult,
                "cumulative_pnl": cumulative_pnl,
                "cumulative_r": cumulative_r
            })
        
        # Write JSON
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "symbol": symbol,
                "count": len(series),
                "final_pnl": cumulative_pnl,
                "final_r": cumulative_r,
                "series": series
            }, f, indent=2)
        
        logger.info(f"Exported {len(series)} time series points for {symbol} to {output_path}")
        return str(output_path)
    
    def get_feature_statistics(self) -> Dict:
        """Get statistics about available features for ML"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        # Overall counts
        cur.execute("SELECT COUNT(*) FROM ai_recommendations")
        total = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM ai_recommendations WHERE executed = 1")
        executed = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*) FROM ai_recommendations 
            WHERE executed = 1 AND result_pnl IS NOT NULL
        """)
        with_results = cur.fetchone()[0]
        
        # By symbol
        cur.execute("""
            SELECT symbol, COUNT(*) 
            FROM ai_recommendations 
            GROUP BY symbol 
            ORDER BY COUNT(*) DESC
        """)
        by_symbol = {row[0]: row[1] for row in cur.fetchall()}
        
        # By regime
        cur.execute("""
            SELECT market_regime, COUNT(*) 
            FROM ai_recommendations 
            GROUP BY market_regime 
            ORDER BY COUNT(*) DESC
        """)
        by_regime = {row[0]: row[1] for row in cur.fetchall()}
        
        con.close()
        
        return {
            "total_recommendations": total,
            "executed": executed,
            "with_results": with_results,
            "training_samples_available": with_results,
            "by_symbol": by_symbol,
            "by_regime": by_regime
        }

