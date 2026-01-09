"""
Symbol Constraints Manager
Manages trading constraints per symbol (max trades, risk limits, allowed/banned strategies)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class SymbolConstraintsManager:
    """Manage symbol-specific trading constraints"""
    
    def __init__(self, config_path: str = "config/symbol_constraints.json"):
        """
        Initialize Symbol Constraints Manager.
        
        Args:
            config_path: Path to JSON configuration file
        """
        self.config_path = Path(config_path)
        self.constraints = self._load_constraints()
    
    def _load_constraints(self) -> Dict[str, Dict[str, Any]]:
        """Load constraints from JSON file"""
        if not self.config_path.exists():
            logger.info(f"Symbol constraints file not found at {self.config_path}, using defaults")
            return {}
        
        try:
            with open(self.config_path, 'r') as f:
                constraints = json.load(f)
            
            # Validate structure
            if not isinstance(constraints, dict):
                logger.warning(f"Invalid constraints file structure, using defaults")
                return {}
            
            # Validate each symbol's constraints
            validated_constraints = {}
            for symbol, symbol_constraints in constraints.items():
                if isinstance(symbol_constraints, dict):
                    validated_constraints[symbol] = symbol_constraints
                else:
                    logger.warning(f"Invalid constraints for {symbol}, skipping")
            
            logger.info(f"Loaded constraints for {len(validated_constraints)} symbols")
            return validated_constraints
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing constraints file: {e}, using defaults")
            return {}
        except Exception as e:
            logger.error(f"Error loading constraints file: {e}, using defaults")
            return {}
    
    def _get_default_constraints(self) -> Dict[str, Any]:
        """
        Get default constraints for a symbol.
        
        Returns:
            Default constraint values
        """
        return {
            "max_concurrent_trades_for_symbol": 2,
            "max_total_risk_on_symbol_pct": 3.0,
            "allowed_strategies": [],  # Empty = all allowed
            "risk_profile": "normal",
            "banned_strategies": [],
            "max_position_size_pct": 5.0
        }
    
    def get_symbol_constraints(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Get trading constraints for symbol.
        
        Args:
            symbol: Trading symbol (e.g., "XAUUSDc", "BTCUSDc")
        
        Returns:
            {
                "max_concurrent_trades_for_symbol": 2,
                "max_total_risk_on_symbol_pct": 3.0,  # Max % of account risk on this symbol
                "allowed_strategies": [
                    "INSIDE_BAR_VOLATILITY_TRAP",
                    "VOLATILITY_REVERSION_SCALP"
                ],
                "risk_profile": "normal",  # "aggressive" | "normal" | "conservative"
                "banned_strategies": ["SWING_TREND_FOLLOWING"],  # Strategies not allowed
                "max_position_size_pct": 5.0  # Max position size as % of account
            }
        """
        # Normalize symbol (remove 'c' suffix for lookup, but keep original for return)
        symbol_key = symbol.upper().rstrip('cC')
        
        # Try exact match first
        if symbol_key in self.constraints:
            constraints = self.constraints[symbol_key].copy()
            # Ensure all required fields are present
            return self._merge_with_defaults(constraints)
        
        # Try with 'c' suffix
        symbol_with_c = symbol_key + 'c'
        if symbol_with_c in self.constraints:
            constraints = self.constraints[symbol_with_c].copy()
            return self._merge_with_defaults(constraints)
        
        # Try original symbol
        if symbol in self.constraints:
            constraints = self.constraints[symbol].copy()
            return self._merge_with_defaults(constraints)
        
        # Return defaults if symbol not found
        logger.debug(f"No constraints found for {symbol}, using defaults")
        return self._get_default_constraints()
    
    def _merge_with_defaults(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge provided constraints with defaults to ensure all fields are present.
        
        Args:
            constraints: Partial constraints dict
        
        Returns:
            Complete constraints dict with defaults for missing fields
        """
        defaults = self._get_default_constraints()
        merged = defaults.copy()
        merged.update(constraints)
        return merged
    
    def is_strategy_allowed(
        self,
        symbol: str,
        strategy_name: str
    ) -> bool:
        """
        Check if a strategy is allowed for a symbol.
        
        Args:
            symbol: Trading symbol
            strategy_name: Strategy name to check
        
        Returns:
            True if strategy is allowed, False otherwise
        """
        constraints = self.get_symbol_constraints(symbol)
        
        # Check banned strategies first
        banned_strategies = constraints.get("banned_strategies", [])
        if strategy_name in banned_strategies:
            return False
        
        # Check allowed strategies (empty list = all allowed)
        allowed_strategies = constraints.get("allowed_strategies", [])
        if allowed_strategies and strategy_name not in allowed_strategies:
            return False
        
        return True
    
    def get_max_concurrent_trades(self, symbol: str) -> int:
        """
        Get maximum concurrent trades for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Maximum number of concurrent trades
        """
        constraints = self.get_symbol_constraints(symbol)
        return constraints.get("max_concurrent_trades_for_symbol", 2)
    
    def get_max_risk_pct(self, symbol: str) -> float:
        """
        Get maximum total risk percentage for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Maximum risk as percentage of account
        """
        constraints = self.get_symbol_constraints(symbol)
        return constraints.get("max_total_risk_on_symbol_pct", 3.0)
    
    def get_risk_profile(self, symbol: str) -> str:
        """
        Get risk profile for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Risk profile ("aggressive" | "normal" | "conservative")
        """
        constraints = self.get_symbol_constraints(symbol)
        return constraints.get("risk_profile", "normal")
    
    def reload_constraints(self):
        """Reload constraints from file (useful for hot-reload)"""
        self.constraints = self._load_constraints()
        logger.info("Symbol constraints reloaded")

