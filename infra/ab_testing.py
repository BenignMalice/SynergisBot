"""
A/B Testing Framework
Test and compare different recommendation strategies
"""

import sqlite3
import time
import random
import logging
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ABVariant:
    """A/B test variant configuration"""
    variant_id: str
    name: str
    description: str
    config: Dict
    is_control: bool = False


class ABTestFramework:
    """A/B testing for recommendation strategies"""
    
    def __init__(self, db_path: str = "data/journal.sqlite"):
        self.db_path = Path(db_path)
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Create A/B testing tables"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        # Experiments table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ab_experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                control_variant TEXT NOT NULL,
                started_at INTEGER NOT NULL,
                ended_at INTEGER,
                status TEXT CHECK(status IN ('active', 'paused', 'completed')) DEFAULT 'active'
            )
        """)
        
        # Variants table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ab_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                variant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                config TEXT NOT NULL,
                is_control BOOLEAN DEFAULT 0,
                traffic_pct REAL DEFAULT 50.0,
                FOREIGN KEY(experiment_id) REFERENCES ab_experiments(id) ON DELETE CASCADE,
                UNIQUE(experiment_id, variant_id)
            )
        """)
        
        # Assignments table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ab_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                variant_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                assigned_at INTEGER NOT NULL,
                FOREIGN KEY(experiment_id) REFERENCES ab_experiments(id) ON DELETE CASCADE,
                UNIQUE(experiment_id, user_id)
            )
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_assignment_user ON ab_assignments(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_assignment_exp ON ab_assignments(experiment_id)")
        
        con.commit()
        con.close()
        logger.info("A/B testing tables ensured")
    
    def create_experiment(
        self,
        name: str,
        description: str,
        variants: List[ABVariant]
    ) -> int:
        """Create a new A/B experiment"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        # Find control variant
        control = next((v for v in variants if v.is_control), variants[0])
        
        # Create experiment
        cur.execute("""
            INSERT INTO ab_experiments (name, description, control_variant, started_at, status)
            VALUES (?, ?, ?, ?, 'active')
        """, (name, description, control.variant_id, int(time.time())))
        
        exp_id = cur.lastrowid
        
        # Add variants
        import json
        for variant in variants:
            cur.execute("""
                INSERT INTO ab_variants 
                (experiment_id, variant_id, name, description, config, is_control, traffic_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                exp_id,
                variant.variant_id,
                variant.name,
                variant.description,
                json.dumps(variant.config),
                1 if variant.is_control else 0,
                100.0 / len(variants)  # Equal split by default
            ))
        
        con.commit()
        con.close()
        
        logger.info(f"Created A/B experiment '{name}' with {len(variants)} variants")
        return exp_id
    
    def assign_variant(self, experiment_name: str, user_id: int) -> Optional[str]:
        """Assign user to a variant (or return existing assignment)"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        # Get experiment ID
        cur.execute("""
            SELECT id FROM ab_experiments 
            WHERE name = ? AND status = 'active'
        """, (experiment_name,))
        
        row = cur.fetchone()
        if not row:
            con.close()
            logger.warning(f"No active experiment '{experiment_name}' found")
            return None
        
        exp_id = row[0]
        
        # Check existing assignment
        cur.execute("""
            SELECT variant_id FROM ab_assignments
            WHERE experiment_id = ? AND user_id = ?
        """, (exp_id, user_id))
        
        existing = cur.fetchone()
        if existing:
            con.close()
            return existing[0]
        
        # Get variants with traffic weights
        cur.execute("""
            SELECT variant_id, traffic_pct FROM ab_variants
            WHERE experiment_id = ?
        """, (exp_id,))
        
        variants = cur.fetchall()
        if not variants:
            con.close()
            return None
        
        # Weighted random selection
        total_weight = sum(v[1] for v in variants)
        r = random.uniform(0, total_weight)
        cumulative = 0.0
        
        selected_variant = variants[0][0]  # Default to first
        for variant_id, weight in variants:
            cumulative += weight
            if r <= cumulative:
                selected_variant = variant_id
                break
        
        # Record assignment
        cur.execute("""
            INSERT INTO ab_assignments (experiment_id, variant_id, user_id, assigned_at)
            VALUES (?, ?, ?, ?)
        """, (exp_id, selected_variant, user_id, int(time.time())))
        
        con.commit()
        con.close()
        
        logger.info(f"Assigned user {user_id} to variant '{selected_variant}' in experiment '{experiment_name}'")
        return selected_variant
    
    def get_variant_config(self, experiment_name: str, user_id: int) -> Optional[Dict]:
        """Get the config for user's assigned variant"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            SELECT v.config
            FROM ab_variants v
            JOIN ab_assignments a ON v.variant_id = a.variant_id AND v.experiment_id = a.experiment_id
            JOIN ab_experiments e ON e.id = a.experiment_id
            WHERE e.name = ? AND a.user_id = ?
        """, (experiment_name, user_id))
        
        row = cur.fetchone()
        con.close()
        
        if row:
            import json
            return json.loads(row[0])
        return None
    
    def get_experiment_results(self, experiment_name: str) -> Dict:
        """Get results for an experiment"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        # Get experiment ID
        cur.execute("SELECT id FROM ab_experiments WHERE name = ?", (experiment_name,))
        row = cur.fetchone()
        if not row:
            con.close()
            return {}
        
        exp_id = row[0]
        
        # Get variant results
        # Join with ai_recommendations to get performance
        cur.execute("""
            SELECT 
                v.variant_id,
                v.name,
                COUNT(DISTINCT a.user_id) as users,
                COUNT(r.id) as recommendations,
                SUM(CASE WHEN r.executed = 1 THEN 1 ELSE 0 END) as executed,
                SUM(CASE WHEN r.result_pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN r.result_pnl < 0 THEN 1 ELSE 0 END) as losses,
                AVG(r.result_pnl) as avg_pnl,
                AVG(r.result_r) as avg_r,
                AVG(r.confidence) as avg_confidence
            FROM ab_variants v
            LEFT JOIN ab_assignments a ON v.variant_id = a.variant_id AND v.experiment_id = a.experiment_id
            LEFT JOIN ai_recommendations r ON r.user_id = a.user_id
            WHERE v.experiment_id = ?
            GROUP BY v.variant_id, v.name
        """, (exp_id,))
        
        results = {}
        for row in cur.fetchall():
            variant_id, name, users, recs, executed, wins, losses, avg_pnl, avg_r, avg_conf = row
            
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            execution_rate = (executed / recs * 100) if recs > 0 else 0
            
            results[variant_id] = {
                "name": name,
                "users": users or 0,
                "recommendations": recs or 0,
                "executed": executed or 0,
                "execution_rate": execution_rate,
                "wins": wins or 0,
                "losses": losses or 0,
                "win_rate": win_rate,
                "avg_pnl": avg_pnl or 0,
                "avg_r": avg_r or 0,
                "avg_confidence": avg_conf or 0
            }
        
        con.close()
        return results
    
    def stop_experiment(self, experiment_name: str):
        """Stop an experiment"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            UPDATE ab_experiments 
            SET status = 'completed', ended_at = ?
            WHERE name = ?
        """, (int(time.time()), experiment_name))
        
        con.commit()
        con.close()
        logger.info(f"Stopped experiment '{experiment_name}'")
    
    def list_experiments(self) -> List[Dict]:
        """List all experiments"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        cur.execute("""
            SELECT id, name, description, status, started_at, ended_at
            FROM ab_experiments
            ORDER BY started_at DESC
        """)
        
        experiments = []
        for row in cur.fetchall():
            experiments.append({
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "status": row[3],
                "started_at": row[4],
                "ended_at": row[5]
            })
        
        con.close()
        return experiments

