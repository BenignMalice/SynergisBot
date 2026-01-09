"""
DTMS Configuration
Defensive Trade Management System - Configuration and Settings
"""

from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class DTMSConfig:
    """Main configuration class for DTMS system"""
    
    # Monitoring Configuration
    monitoring: Dict[str, Any] = None
    
    # Signal Thresholds
    thresholds: Dict[str, Any] = None
    
    # State Transition Rules
    state_transitions: Dict[str, Any] = None
    
    # Adaptive Multipliers
    adaptive_multipliers: Dict[str, Any] = None
    
    # Safety Rails
    safety_rails: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.monitoring is None:
            self.monitoring = {
                'start_conditions': {
                    'profit_threshold': 0.2,      # +0.2R to start monitoring
                    'time_threshold': 900,        # 15 minutes
                    'emergency_threshold': -0.5   # -0.5R emergency start
                },
                'fast_check_interval': 30,        # 30 seconds
                'deep_check_interval': 900,       # 15 minutes
                'cooldown_period': 600,          # 10 minutes between deep checks
                'high_vol_override': 15,         # 15 seconds in high volatility
                'flat_override': 60              # 60 seconds in flat markets
            }
        
        if self.thresholds is None:
            self.thresholds = {
                'vwap_base': {
                    'XAUUSD': 0.001,     # 0.10%
                    'BTCUSDT': 0.002,    # 0.20%
                    'EURUSD': 0.0005,    # 0.05%
                    'GBPUSD': 0.0005,    # 0.05%
                    'USDJPY': 0.0007,    # 0.07%
                    'GBPJPY': 0.0007,    # 0.07%
                    'EURJPY': 0.0007,    # 0.07%
                },
                'rsi_thresholds': {
                    'normal': 45,
                    'low_vol': 40
                },
                'volume_flip_thresholds': {
                    'normal': 0.65,      # 65% opposite volume
                    'low_vol': 0.72      # 72% opposite volume
                },
                'atr_ratio_thresholds': {
                    'low_vol': 0.7,      # Below 0.7 = low volatility
                    'high_vol': 1.3      # Above 1.3 = high volatility
                },
                'bb_width_threshold': 0.004,  # Below = RANGE, Above = TREND
                'spread_multiplier': 2.0,     # 2x median spread = too wide
                'conviction_bar': {
                    'body_ratio': 0.65,       # Body must be 65% of range
                    'range_atr': 0.8,         # Range must be 80% of ATR
                    'distance_to_vwap': 0.25  # Within 25% of ATR from VWAP
                }
            }
        
        if self.state_transitions is None:
            self.state_transitions = {
                'HEALTHY_to_WARNING_L1': -2,
                'WARNING_L1_to_WARNING_L2': -4,
                'WARNING_L2_to_HEDGED': -6,
                'hedge_confluence_trigger': -6,  # Score <= -6 OR (VWAP flip + volume flip)
                'recovery_hysteresis': {
                    'WARNING_L1_to_HEALTHY': 0,    # Need score >= 0
                    'WARNING_L2_to_WARNING_L1': -2  # Need score >= -2
                }
            }
        
        if self.adaptive_multipliers is None:
            self.adaptive_multipliers = {
                'session': {
                    'Asian': 1.5,        # Higher threshold (ignore noise)
                    'London': 1.0,       # Base sensitivity
                    'NY': 0.8,           # Faster reaction
                    'Overlap': 0.7       # Most sensitive
                },
                'volatility': {
                    'low': 1.4,          # Low vol → need stronger move
                    'normal': 1.0,       # Base multiplier
                    'high': 0.8          # High vol → react faster
                },
                'structure': {
                    'RANGE': 1.3,        # Require 30% more slope in ranges
                    'TREND': 1.0         # Base multiplier
                },
                'clamp_limits': {
                    'min_threshold': 0.5,    # 50% of base threshold
                    'max_threshold': 1.8     # 180% of base threshold
                }
            }
        
        if self.safety_rails is None:
            self.safety_rails = {
                'daily_loss_limit': 0.02,        # 2% daily loss
                'hourly_loss_limit': 0.01,       # 1% hourly loss
                'max_consecutive_stops': 3,      # 3 consecutive stops
                'news_blackout': {
                    'before_minutes': 30,        # 30 min before high impact
                    'after_minutes': 15          # 15 min after high impact
                },
                'spread_protection': {
                    'median_window_days': 30,    # 30-day rolling median
                    'spike_multiplier': 2.0      # 2x median = spike
                },
                'data_integrity': {
                    'max_bar_age_seconds': 300,  # 5 minutes max bar age
                    'partial_bar_delay': 5       # 5 second delay for bar confirmation
                }
            }

# Signal Weights for Hierarchical Scoring
SIGNAL_WEIGHTS = {
    'structure': 3.0,           # BOS/CHOCH - highest authority
    'vwap_volume': 2.0,         # VWAP flip + volume flip
    'momentum': 2.0,            # RSI + MACD momentum
    'ema_alignment': 1.5,       # EMA50 vs EMA200 slope
    'delta_pressure': 1.0,      # Order flow delta
    'candle_conviction': 1.0    # Conviction bar patterns
}

# Adaptive Signal Weights (adjust based on market regime)
ADAPTIVE_WEIGHTS = {
    'RANGE': {
        'structure': 0.7,       # Structure less reliable in ranges
        'vwap_volume': 1.3,     # VWAP more important in ranges
        'momentum': 1.0,
        'ema_alignment': 0.8,
        'delta_pressure': 1.2,
        'candle_conviction': 1.1
    },
    'HIGH_VOLATILITY': {
        'structure': 1.2,       # Structure more reliable in high vol
        'vwap_volume': 0.9,
        'momentum': 0.8,        # Momentum signals more noisy
        'ema_alignment': 1.0,
        'delta_pressure': 1.1,
        'candle_conviction': 0.9
    },
    'Asian_Session': {
        'structure': 0.8,       # Lower conviction overall
        'vwap_volume': 0.8,
        'momentum': 0.8,
        'ema_alignment': 0.8,
        'delta_pressure': 0.8,
        'candle_conviction': 0.8
    }
}

# State Machine Configuration
STATE_CONFIG = {
    'HEALTHY': {
        'allowed_actions': ['trail_sl', 'scale_in'],
        'exit_conditions': ['score <= -2', 'emergency'],
        'recovery_hysteresis': 0
    },
    'WARNING_L1': {
        'allowed_actions': ['tighten_sl', 'start_flat_timer'],
        'exit_conditions': ['score >= 0', 'score <= -4'],
        'recovery_hysteresis': 1
    },
    'WARNING_L2': {
        'allowed_actions': ['partial_close', 'move_sl_breakeven', 'arm_hedge'],
        'exit_conditions': ['score >= -2', 'score <= -6', 'confluence'],
        'recovery_hysteresis': 2
    },
    'HEDGED': {
        'allowed_actions': ['maintain_hedge', 'trail_both', 'suppress_new'],
        'exit_conditions': ['flat_timer_expire', 'bos_resume', 'choch_opposite'],
        'recovery_hysteresis': 0
    },
    'RECOVERING': {
        'allowed_actions': ['re_add_position', 'clear_hedge'],
        'exit_conditions': ['choch_opposite', 'recovery_timer_expire', 'score >= +1'],
        'recovery_hysteresis': 0
    },
    'CLOSED': {
        'allowed_actions': [],
        'exit_conditions': [],
        'recovery_hysteresis': 0
    }
}

# Default configuration instance
DEFAULT_CONFIG = DTMSConfig()

def get_config() -> DTMSConfig:
    """Get the default DTMS configuration"""
    return DEFAULT_CONFIG

def get_adaptive_weights(regime: str, session: str, volatility: str) -> Dict[str, float]:
    """Get adaptive signal weights based on market conditions"""
    weights = SIGNAL_WEIGHTS.copy()
    
    # Apply regime-based adjustments
    if regime in ADAPTIVE_WEIGHTS:
        for signal, multiplier in ADAPTIVE_WEIGHTS[regime].items():
            weights[signal] *= multiplier
    
    # Apply session-based adjustments
    if session == 'Asian' and 'Asian_Session' in ADAPTIVE_WEIGHTS:
        for signal, multiplier in ADAPTIVE_WEIGHTS['Asian_Session'].items():
            weights[signal] *= multiplier
    
    return weights

def get_vwap_threshold(symbol: str, session: str, volatility: str, structure: str) -> float:
    """Calculate adaptive VWAP threshold"""
    config = get_config()
    
    # Base threshold for symbol
    base_threshold = config.thresholds['vwap_base'].get(symbol, 0.001)
    
    # Apply multipliers
    session_mult = config.adaptive_multipliers['session'].get(session, 1.0)
    vol_mult = config.adaptive_multipliers['volatility'].get(volatility, 1.0)
    structure_mult = config.adaptive_multipliers['structure'].get(structure, 1.0)
    
    # Calculate final threshold
    adaptive_threshold = base_threshold * session_mult * vol_mult * structure_mult
    
    # Apply clamping
    min_threshold = base_threshold * config.adaptive_multipliers['clamp_limits']['min_threshold']
    max_threshold = base_threshold * config.adaptive_multipliers['clamp_limits']['max_threshold']
    
    return max(min_threshold, min(adaptive_threshold, max_threshold))