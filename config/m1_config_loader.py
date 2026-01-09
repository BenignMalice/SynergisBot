# =====================================
# config/m1_config_loader.py
# =====================================
"""
M1 Configuration Loader

Loads M1 microstructure configuration from JSON file.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class M1ConfigLoader:
    """
    Loads and manages M1 configuration from JSON file.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize M1 Config Loader.
        
        Args:
            config_path: Path to config file (default: "config/m1_config.json")
        """
        if config_path is None:
            # Default to config/m1_config.json relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(project_root, "config", "m1_config.json")
        
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from JSON file."""
        try:
            if not self.config_path.exists():
                logger.warning(f"M1 config file not found: {self.config_path}, using defaults")
                self._set_defaults()
                return
            
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            
            logger.info(f"M1 config loaded from {self.config_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding M1 config JSON: {e}, using defaults")
            self._set_defaults()
        except Exception as e:
            logger.error(f"Error loading M1 config: {e}, using defaults")
            self._set_defaults()
    
    def _set_defaults(self):
        """Set default configuration values."""
        self.config = {
            "m1_data": {
                "enabled": True,
                "max_candles_per_symbol": 200,
                "refresh_interval_active_scalp": 30,
                "refresh_interval_active": 60,
                "refresh_interval_inactive": 300,
                "force_refresh_on_stale": True,
                "stale_threshold_seconds": 180,
                "skip_weekend_refresh": True,
                "weekend_start_utc": "21:00",
                "weekend_end_utc": "22:00",
                "symbols": {
                    "active_scalp": ["XAUUSD", "BTCUSD"],
                    "active": ["EURUSD", "GBPUSD", "USDJPY"]
                },
                "choch_detection": {
                    "require_3_candle_confirmation": True,
                    "require_choch_bos_combo": True,
                    "confidence_threshold": 70,
                    "debug_confidence_weights": False,
                    "include_m15_alignment": False,
                    "use_sigmoid_scaling": True,
                    "sigmoid_steepness": 0.1,
                    "use_rolling_mean": False,
                    "rolling_mean_window": 5,
                    "symbol_thresholds": {
                        "BTCUSD": 75,
                        "XAUUSD": 72,
                        "EURUSD": 70,
                        "GBPUSD": 70
                    },
                    "session_adjustments": {
                        "ASIAN": 5.0,
                        "LONDON": -5.0,
                        "NY": -2.0,
                        "OVERLAP": -8.0,
                        "POST_NY": 10.0
                    }
                },
                "cache": {
                    "enabled": True,
                    "ttl_seconds": 300,
                    "max_cached_symbols": 10
                },
                "snapshots": {
                    "enabled": True,
                    "interval": 1800,
                    "directory": "data/m1_snapshots",
                    "max_age_hours": 24,
                    "cleanup_enabled": True,
                    "validate_checksum": True,
                    "use_file_locking": True,
                    "use_compression": True,
                    "compression_level": 3
                }
            }
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated path.
        
        Args:
            key_path: Dot-separated path (e.g., "m1_data.enabled")
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def get_m1_config(self) -> Dict[str, Any]:
        """Get full M1 data configuration."""
        return self.config.get("m1_data", {})
    
    def is_enabled(self) -> bool:
        """Check if M1 data is enabled."""
        return self.get("m1_data.enabled", True)
    
    def get_refresh_interval(self, symbol: str) -> int:
        """
        Get refresh interval for a symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Refresh interval in seconds
        """
        m1_config = self.get_m1_config()
        symbols_config = m1_config.get("symbols", {})
        
        symbol_base = symbol.upper().rstrip('Cc')
        
        # Check active_scalp
        if symbol_base in symbols_config.get("active_scalp", []):
            return m1_config.get("refresh_interval_active_scalp", 30)
        
        # Check active
        if symbol_base in symbols_config.get("active", []):
            return m1_config.get("refresh_interval_active", 60)
        
        # Default to inactive
        return m1_config.get("refresh_interval_inactive", 300)
    
    def get_choch_config(self) -> Dict[str, Any]:
        """Get CHOCH detection configuration."""
        m1_config = self.get_m1_config()
        return m1_config.get("choch_detection", {})
    
    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration."""
        m1_config = self.get_m1_config()
        return m1_config.get("cache", {})
    
    def get_snapshot_config(self) -> Dict[str, Any]:
        """Get snapshot configuration."""
        m1_config = self.get_m1_config()
        return m1_config.get("snapshots", {})
    
    def get_symbol_threshold(self, symbol: str) -> Optional[int]:
        """
        Get symbol-specific threshold.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Threshold value or None if not configured
        """
        choch_config = self.get_choch_config()
        symbol_thresholds = choch_config.get("symbol_thresholds", {})
        
        symbol_base = symbol.upper().rstrip('Cc')
        
        # Direct match
        if symbol_base in symbol_thresholds:
            return symbol_thresholds[symbol_base]
        
        # Pattern matching
        if symbol_base.startswith("BTC"):
            return symbol_thresholds.get("BTC*")
        elif symbol_base.startswith("XAU"):
            return symbol_thresholds.get("XAU*")
        elif any(fx in symbol_base for fx in ["EUR", "GBP", "USD", "JPY"]):
            return symbol_thresholds.get("FOREX*")
        
        return None
    
    def get_session_adjustment(self, session: str) -> float:
        """
        Get session-based threshold adjustment.
        
        Args:
            session: Session name (ASIAN, LONDON, NY, OVERLAP, POST_NY)
            
        Returns:
            Adjustment value (percentage points)
        """
        choch_config = self.get_choch_config()
        session_adjustments = choch_config.get("session_adjustments", {})
        return session_adjustments.get(session.upper(), 0.0)
    
    def should_refresh_on_weekend(self, symbol: str) -> bool:
        """
        Check if symbol should refresh on weekends.
        
        Args:
            symbol: Symbol name
            
        Returns:
            True if should refresh on weekend, False otherwise
        """
        m1_config = self.get_m1_config()
        if not m1_config.get("skip_weekend_refresh", True):
            return True  # If weekend refresh not skipped, always refresh
        
        # BTCUSD trades 24/7
        symbol_base = symbol.upper().rstrip('Cc')
        if "BTC" in symbol_base:
            return True
        
        # Other symbols: skip weekend
        return False
    
    def reload(self):
        """Reload configuration from file."""
        self._load_config()
        logger.info("M1 config reloaded")

