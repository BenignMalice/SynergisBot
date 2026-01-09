"""
Range Scalping Configuration Loader
Handles loading, validation, and versioning of range scalping configuration files.
"""

import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def validate_range_scalping_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate config for sane values before loading.
    
    Checks:
    - R:R ratios are positive and min < target < max
    - Thresholds are between 0-100 where applicable
    - ATR multipliers are positive
    - Session adjustments are valid
    - Confluence weights sum to 100
    """
    errors = []
    
    # Validate entry filters
    if "entry_filters" in config:
        entry_filters = config["entry_filters"]
        
        # Validate confluence score threshold
        threshold = entry_filters.get("min_confluence_score", 80)
        if not (0 <= threshold <= 100):
            errors.append(f"Invalid confluence threshold: {threshold} (must be 0-100)")
        
        # Validate confluence weights sum to 100
        if "confluence_weights" in entry_filters:
            weights = entry_filters["confluence_weights"]
            total = sum(weights.values())
            if total != 100:
                errors.append(f"Confluence weights sum to {total}, must sum to 100")
    
    # Validate position sizing
    if "position_sizing" in config:
        pos_sizing = config["position_sizing"]
        fixed_lot = pos_sizing.get("fixed_lot_size", 0.01)
        if fixed_lot <= 0:
            errors.append(f"Invalid fixed lot size: {fixed_lot} (must be > 0)")
    
    # Validate risk mitigation thresholds
    if "risk_mitigation" in config:
        risk = config["risk_mitigation"]
        
        # Volume threshold
        volume_pct = risk.get("min_volume_percent_of_1h_avg", 0.5)
        if not (0 < volume_pct <= 1.0):
            errors.append(f"Invalid min_volume_percent_of_1h_avg: {volume_pct} (must be 0-1)")
        
        # Price deviation
        price_dev = risk.get("min_price_deviation_atr", 0.5)
        if price_dev <= 0:
            errors.append(f"Invalid min_price_deviation_atr: {price_dev} (must be > 0)")
    
    # Validate range invalidation thresholds
    if "range_invalidation" in config:
        invalidation = config["range_invalidation"]
        
        vwap_threshold = invalidation.get("vwap_momentum_threshold_pct", 0.2)
        if not (0 <= vwap_threshold <= 1.0):
            errors.append(f"Invalid vwap_momentum_threshold_pct: {vwap_threshold} (must be 0-1)")
        
        bb_expansion = invalidation.get("bb_width_expansion_percent", 50)
        if bb_expansion < 0:
            errors.append(f"Invalid bb_width_expansion_percent: {bb_expansion} (must be >= 0)")
    
    # Validate false range detection thresholds
    if "false_range_detection" in config:
        false_range = config["false_range_detection"]
        
        volume_threshold = false_range.get("volume_increase_threshold", 0.15)
        if not (0 <= volume_threshold <= 1.0):
            errors.append(f"Invalid volume_increase_threshold: {volume_threshold} (must be 0-1)")
        
        vwap_threshold = false_range.get("vwap_momentum_threshold", 0.1)
        if not (0 <= vwap_threshold <= 1.0):
            errors.append(f"Invalid vwap_momentum_threshold: {vwap_threshold} (must be 0-1)")
        
        cvd_threshold = false_range.get("cvd_divergence_strength_threshold", 0.6)
        if not (0 <= cvd_threshold <= 1.0):
            errors.append(f"Invalid cvd_divergence_strength_threshold: {cvd_threshold} (must be 0-1)")
    
    # Validate VWAP momentum config
    if "vwap_momentum" in config:
        vwap = config["vwap_momentum"]
        threshold = vwap.get("threshold_pct", 0.2)
        if not (0 <= threshold <= 1.0):
            errors.append(f"Invalid vwap_momentum.threshold_pct: {threshold} (must be 0-1)")
    
    # Validate execution config
    if "execution" in config:
        exec_cfg = config["execution"]
        auto_threshold = exec_cfg.get("auto_execute_threshold", 85)
        if not (0 <= auto_threshold <= 100):
            errors.append(f"Invalid auto_execute_threshold: {auto_threshold} (must be 0-100)")
    
    # Validate strategy weights (must sum to ~1.0 per ADX level)
    if "dynamic_strategy_weighting" in config:
        weighting = config["dynamic_strategy_weighting"]
        if weighting.get("enabled", True):
            strategy_weights = weighting.get("strategy_weights", {})
            
            # Check low_adx weights
            low_adx_total = sum(w.get("low_adx", 0) for w in strategy_weights.values())
            if abs(low_adx_total - 1.0) > 0.01:
                errors.append(f"Strategy weights (low_adx) sum to {low_adx_total}, should be ~1.0")
            
            # Check normal weights
            normal_total = sum(w.get("normal", 0) for w in strategy_weights.values())
            if abs(normal_total - 1.0) > 0.01:
                errors.append(f"Strategy weights (normal) sum to {normal_total}, should be ~1.0")
    
    return len(errors) == 0, errors


def validate_rr_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate R:R configuration file.
    
    Checks:
    - R:R ratios are positive and min < target < max
    - ATR multipliers are positive
    - Session adjustments are valid
    """
    errors = []
    
    # Validate strategy R:R configs
    if "strategy_rr" in config:
        for strategy, rr_config in config["strategy_rr"].items():
            min_rr = rr_config.get("min", 0)
            target_rr = rr_config.get("target", 0)
            max_rr = rr_config.get("max", 0)
            
            if not (0 < min_rr < target_rr < max_rr):
                errors.append(
                    f"Invalid R:R for {strategy}: min ({min_rr}) < target ({target_rr}) < max ({max_rr}) required"
                )
            
            # Validate ATR multipliers
            stop_mult = rr_config.get("default_stop_atr_mult", 0)
            tp_mult = rr_config.get("default_tp_atr_mult", 0)
            
            if stop_mult <= 0:
                errors.append(f"Invalid default_stop_atr_mult for {strategy}: {stop_mult} (must be > 0)")
            if tp_mult <= 0:
                errors.append(f"Invalid default_tp_atr_mult for {strategy}: {tp_mult} (must be > 0)")
    
    # Validate session adjustments
    if "session_adjustments" in config:
        for session, adj in config["session_adjustments"].items():
            if not adj.get("enabled", True):
                continue  # Skip disabled sessions
            
            rr_mult = adj.get("rr_multiplier", 1.0)
            if rr_mult < 0:
                errors.append(f"Invalid rr_multiplier for {session}: {rr_mult} (must be >= 0)")
            
            stop_tight = adj.get("stop_tightener", 1.0)
            if stop_tight <= 0:
                errors.append(f"Invalid stop_tightener for {session}: {stop_tight} (must be > 0)")
            
            max_rr = adj.get("max_rr", 999)
            if max_rr <= 0:
                errors.append(f"Invalid max_rr for {session}: {max_rr} (must be > 0)")
    
    return len(errors) == 0, errors


def load_range_scalping_config(config_path: str = "config/range_scalping_config.json") -> Dict[str, Any]:
    """
    Load range scalping config with versioning and validation.
    
    Args:
        config_path: Path to config file
        
    Returns:
        Validated config dict
        
    Raises:
        ValueError: If config validation fails
        FileNotFoundError: If config file doesn't exist
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")
    
    # Load config
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Validate config
    is_valid, errors = validate_range_scalping_config(config)
    if not is_valid:
        error_msg = "; ".join(errors)
        raise ValueError(f"Config validation failed: {error_msg}")
    
    # Calculate version hash (if not present or placeholder)
    if "_config_hash" not in config or config["_config_hash"] == "auto-calculated-on-load":
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Remove version fields for hash calculation to avoid infinite loop
            content_for_hash = json.dumps(
                {k: v for k, v in config.items() if not k.startswith("_")},
                sort_keys=True
            )
            config["_config_hash"] = hashlib.sha256(content_for_hash.encode()).hexdigest()[:16]
        
        # Update version timestamp
        from datetime import timezone
        config["_config_version"] = datetime.now(timezone.utc).isoformat()
        
        # Save updated config
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    logger.info(
        f"Range Scalping Config loaded: version {config.get('_config_version', 'unknown')}, "
        f"hash {config.get('_config_hash', 'unknown')}"
    )
    
    return config


def load_rr_config(config_path: str = "config/range_scalping_rr_config.json") -> Dict[str, Any]:
    """
    Load R:R configuration file with validation.
    
    Args:
        config_path: Path to R:R config file
        
    Returns:
        Validated R:R config dict
        
    Raises:
        ValueError: If config validation fails
        FileNotFoundError: If config file doesn't exist
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"R:R config file not found: {config_file}")
    
    # Load config
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Validate config
    is_valid, errors = validate_rr_config(config)
    if not is_valid:
        error_msg = "; ".join(errors)
        raise ValueError(f"R:R config validation failed: {error_msg}")
    
    logger.info("R:R config loaded and validated")
    
    return config


def get_config_version_info(config_path: str = "config/range_scalping_config.json") -> Dict[str, str]:
    """
    Get version information for a config file without loading the entire config.
    
    Returns:
        Dict with version and hash info
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        return {"version": "unknown", "hash": "unknown", "exists": False}
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        return {
            "version": config.get("_config_version", "unknown"),
            "hash": config.get("_config_hash", "unknown"),
            "exists": True
        }
    except Exception as e:
        logger.warning(f"Error reading config version info: {e}")
        return {"version": "unknown", "hash": "unknown", "exists": True, "error": str(e)}

