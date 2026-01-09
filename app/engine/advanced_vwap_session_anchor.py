"""
Advanced VWAP calculation with session anchoring for different asset types.
Implements FX session-based anchoring vs 24/7 crypto anchoring with 60-minute sigma windows.
"""

import numpy as np
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class AssetType(Enum):
    """Asset type classification for session anchoring."""
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    INDEX = "index"

class SessionType(Enum):
    """Trading session types."""
    ASIAN = "asian"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP = "overlap"
    CRYPTO_24_7 = "crypto_24_7"

@dataclass
class SessionConfig:
    """Configuration for trading sessions."""
    name: str
    start_hour: int  # UTC hour
    end_hour: int    # UTC hour
    timezone: str
    is_24_7: bool = False
    overlap_sessions: List[str] = None

@dataclass
class VWAPSessionAnchor:
    """VWAP session anchor data structure."""
    session_start_ms: int
    session_end_ms: int
    session_type: SessionType
    vwap_value: float
    volume_weighted_sum: float
    total_volume: float
    sigma_bands: Dict[str, float]  # 1σ, 2σ, 3σ bands
    is_active: bool
    tick_count: int
    last_update_ms: int

class AdvancedVWAPSessionAnchor:
    """
    Advanced VWAP calculator with session anchoring for different asset types.
    Supports FX session-based anchoring and 24/7 crypto anchoring.
    """
    
    def __init__(self, symbol: str, asset_type: AssetType):
        self.symbol = symbol
        self.asset_type = asset_type
        self.session_configs = self._initialize_session_configs()
        self.current_session: Optional[VWAPSessionAnchor] = None
        self.session_history: List[VWAPSessionAnchor] = []
        
        # Sigma window configuration (60 minutes)
        self.sigma_window_minutes = 60
        self.sigma_window_ms = self.sigma_window_minutes * 60 * 1000
        
        # Session detection
        self.last_session_check_ms = 0
        self.session_check_interval_ms = 60 * 1000  # Check every minute
        
        logger.info(f"AdvancedVWAPSessionAnchor initialized for {symbol} ({asset_type.value})")

    def _initialize_session_configs(self) -> Dict[SessionType, SessionConfig]:
        """Initialize session configurations for different asset types."""
        if self.asset_type == AssetType.FOREX:
            return {
                SessionType.ASIAN: SessionConfig(
                    name="Asian Session",
                    start_hour=0,  # 00:00 UTC
                    end_hour=9,    # 09:00 UTC
                    timezone="UTC"
                ),
                SessionType.LONDON: SessionConfig(
                    name="London Session", 
                    start_hour=8,  # 08:00 UTC
                    end_hour=17,  # 17:00 UTC
                    timezone="UTC"
                ),
                SessionType.NEW_YORK: SessionConfig(
                    name="New York Session",
                    start_hour=13, # 13:00 UTC
                    end_hour=22,  # 22:00 UTC
                    timezone="UTC"
                ),
                SessionType.OVERLAP: SessionConfig(
                    name="London-New York Overlap",
                    start_hour=13, # 13:00 UTC
                    end_hour=17,  # 17:00 UTC
                    timezone="UTC"
                )
            }
        elif self.asset_type == AssetType.CRYPTO:
            return {
                SessionType.CRYPTO_24_7: SessionConfig(
                    name="24/7 Crypto Session",
                    start_hour=0,
                    end_hour=24,
                    timezone="UTC",
                    is_24_7=True
                )
            }
        else:
            # Default to 24/7 for commodities and indices
            return {
                SessionType.CRYPTO_24_7: SessionConfig(
                    name="24/7 Session",
                    start_hour=0,
                    end_hour=24,
                    timezone="UTC",
                    is_24_7=True
                )
            }

    def _detect_current_session(self, timestamp_ms: int) -> Optional[SessionType]:
        """Detect the current trading session based on timestamp."""
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        current_hour = dt.hour
        
        if self.asset_type == AssetType.FOREX:
            # FX session detection
            if 0 <= current_hour < 8:
                return SessionType.ASIAN
            elif 8 <= current_hour < 13:
                return SessionType.LONDON
            elif 13 <= current_hour < 17:
                return SessionType.OVERLAP  # London-NY overlap
            elif 17 <= current_hour < 22:
                return SessionType.NEW_YORK
            else:
                # Outside main sessions (22-24), use Asian for next day
                return SessionType.ASIAN
                
        elif self.asset_type == AssetType.CRYPTO:
            # Crypto is 24/7
            return SessionType.CRYPTO_24_7
            
        else:
            # Default to 24/7 for other assets
            return SessionType.CRYPTO_24_7

    def _calculate_session_start_end(self, session_type: SessionType, timestamp_ms: int) -> Tuple[int, int]:
        """Calculate session start and end times."""
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        
        if session_type == SessionType.CRYPTO_24_7 or self.asset_type == AssetType.CRYPTO:
            # For 24/7 assets, use daily sessions (00:00 to 23:59 UTC)
            session_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            session_end = session_start + timedelta(days=1) - timedelta(microseconds=1)
        else:
            # For FX, calculate based on session hours
            config = self.session_configs[session_type]
            
            if config.start_hour <= config.end_hour:
                # Same day session
                session_start = dt.replace(hour=config.start_hour, minute=0, second=0, microsecond=0)
                session_end = dt.replace(hour=config.end_hour, minute=0, second=0, microsecond=0)
            else:
                # Cross-day session (e.g., Asian session)
                if dt.hour >= config.start_hour:
                    # Current day
                    session_start = dt.replace(hour=config.start_hour, minute=0, second=0, microsecond=0)
                    session_end = (dt + timedelta(days=1)).replace(hour=config.end_hour, minute=0, second=0, microsecond=0)
                else:
                    # Previous day
                    session_start = (dt - timedelta(days=1)).replace(hour=config.start_hour, minute=0, second=0, microsecond=0)
                    session_end = dt.replace(hour=config.end_hour, minute=0, second=0, microsecond=0)
        
        return int(session_start.timestamp() * 1000), int(session_end.timestamp() * 1000)

    def _calculate_sigma_bands(self, prices: np.ndarray, volumes: np.ndarray, vwap: float) -> Dict[str, float]:
        """Calculate sigma bands around VWAP."""
        if len(prices) == 0 or len(volumes) == 0:
            return {"1σ": 0.0, "2σ": 0.0, "3σ": 0.0}
        
        # Calculate volume-weighted standard deviation
        squared_deviations = (prices - vwap) ** 2
        volume_weighted_variance = np.sum(squared_deviations * volumes) / np.sum(volumes)
        volume_weighted_std = np.sqrt(volume_weighted_variance)
        
        return {
            "1σ": vwap + volume_weighted_std,
            "2σ": vwap + 2 * volume_weighted_std,
            "3σ": vwap + 3 * volume_weighted_std,
            "-1σ": vwap - volume_weighted_std,
            "-2σ": vwap - 2 * volume_weighted_std,
            "-3σ": vwap - 3 * volume_weighted_std
        }

    def update_vwap(self, price: float, volume: float, timestamp_ms: int) -> Optional[VWAPSessionAnchor]:
        """
        Update VWAP with session anchoring.
        Returns the current session anchor if updated.
        """
        # Check if we need to start a new session
        current_session_type = self._detect_current_session(timestamp_ms)
        
        # Check if session has changed or if we don't have an active session
        if (self.current_session is None or 
            self.current_session.session_type != current_session_type or
            timestamp_ms - self.last_session_check_ms > self.session_check_interval_ms):
            
            # Archive current session if it exists
            if self.current_session is not None:
                self.current_session.is_active = False
                self.session_history.append(self.current_session)
                logger.info(f"Archived {self.current_session.session_type.value} session for {self.symbol}")
            
            # Start new session
            session_start_ms, session_end_ms = self._calculate_session_start_end(current_session_type, timestamp_ms)
            
            self.current_session = VWAPSessionAnchor(
                session_start_ms=session_start_ms,
                session_end_ms=session_end_ms,
                session_type=current_session_type,
                vwap_value=price,  # Initialize with current price
                volume_weighted_sum=price * volume,
                total_volume=volume,
                sigma_bands={},
                is_active=True,
                tick_count=1,
                last_update_ms=timestamp_ms
            )
            
            self.last_session_check_ms = timestamp_ms
            logger.info(f"Started new {current_session_type.value} session for {self.symbol}")
        
        # Update current session VWAP
        if self.current_session is not None:
            # Update volume-weighted sum and total volume
            self.current_session.volume_weighted_sum += price * volume
            self.current_session.total_volume += volume
            
            # Calculate new VWAP
            if self.current_session.total_volume > 0:
                self.current_session.vwap_value = self.current_session.volume_weighted_sum / self.current_session.total_volume
            
            # Update metadata
            self.current_session.tick_count += 1
            self.current_session.last_update_ms = timestamp_ms
            
            # Calculate sigma bands every 60 minutes or when we have enough data
            if (timestamp_ms - self.current_session.session_start_ms) % self.sigma_window_ms < 1000:  # Within 1 second of window
                # Get recent data for sigma calculation (last 60 minutes)
                recent_prices, recent_volumes = self._get_recent_data_for_sigma(timestamp_ms)
                if len(recent_prices) > 0:
                    self.current_session.sigma_bands = self._calculate_sigma_bands(
                        recent_prices, recent_volumes, self.current_session.vwap_value
                    )
        
        return self.current_session

    def _get_recent_data_for_sigma(self, timestamp_ms: int) -> Tuple[np.ndarray, np.ndarray]:
        """Get recent price and volume data for sigma calculation."""
        # This is a simplified implementation
        # In a real system, you would maintain a rolling buffer of recent ticks
        # For now, return empty arrays - this would be implemented with the ring buffer system
        return np.array([]), np.array([])

    def get_current_vwap(self) -> Optional[float]:
        """Get the current VWAP value."""
        if self.current_session and self.current_session.is_active:
            return self.current_session.vwap_value
        return None

    def get_current_sigma_bands(self) -> Dict[str, float]:
        """Get current sigma bands."""
        if self.current_session and self.current_session.is_active:
            return self.current_session.sigma_bands
        return {}

    def get_session_statistics(self) -> Dict[str, Any]:
        """Get comprehensive session statistics."""
        stats = {
            "symbol": self.symbol,
            "asset_type": self.asset_type.value,
            "current_session": None,
            "session_history_count": len(self.session_history),
            "total_sessions": len(self.session_history) + (1 if self.current_session else 0)
        }
        
        if self.current_session:
            stats["current_session"] = {
                "session_type": self.current_session.session_type.value,
                "vwap_value": self.current_session.vwap_value,
                "total_volume": self.current_session.total_volume,
                "tick_count": self.current_session.tick_count,
                "is_active": self.current_session.is_active,
                "sigma_bands": self.current_session.sigma_bands
            }
        
        return stats

    def get_session_vwap_by_type(self, session_type: SessionType) -> Optional[float]:
        """Get VWAP for a specific session type from history."""
        for session in reversed(self.session_history):  # Most recent first
            if session.session_type == session_type:
                return session.vwap_value
        return None

    def get_all_session_vwaps(self) -> Dict[str, float]:
        """Get VWAP values for all session types."""
        vwaps = {}
        
        # Current session
        if self.current_session:
            vwaps[f"current_{self.current_session.session_type.value}"] = self.current_session.vwap_value
        
        # Historical sessions
        for session in self.session_history:
            vwaps[f"historical_{session.session_type.value}"] = session.vwap_value
        
        return vwaps

    def is_price_above_vwap(self, price: float, sigma_level: int = 1) -> bool:
        """Check if price is above VWAP by specified sigma level."""
        current_vwap = self.get_current_vwap()
        if current_vwap is None:
            return False
        
        sigma_bands = self.get_current_sigma_bands()
        sigma_key = f"{sigma_level}σ" if sigma_level > 0 else f"-{abs(sigma_level)}σ"
        
        if sigma_key in sigma_bands:
            return price > sigma_bands[sigma_key]
        
        # Fallback to simple VWAP comparison
        return price > current_vwap

    def is_price_below_vwap(self, price: float, sigma_level: int = 1) -> bool:
        """Check if price is below VWAP by specified sigma level."""
        current_vwap = self.get_current_vwap()
        if current_vwap is None:
            return False
        
        sigma_bands = self.get_current_sigma_bands()
        sigma_key = f"-{sigma_level}σ"
        
        if sigma_key in sigma_bands:
            return price < sigma_bands[sigma_key]
        
        # Fallback to simple VWAP comparison
        return price < current_vwap

    def get_vwap_distance(self, price: float) -> float:
        """Get the distance of price from VWAP as a percentage."""
        current_vwap = self.get_current_vwap()
        if current_vwap is None or current_vwap == 0:
            return 0.0
        
        return ((price - current_vwap) / current_vwap) * 100

    def cleanup_old_sessions(self, max_sessions: int = 10):
        """Clean up old session history to prevent memory bloat."""
        if len(self.session_history) > max_sessions:
            # Keep only the most recent sessions
            self.session_history = self.session_history[-max_sessions:]
            logger.info(f"Cleaned up session history for {self.symbol}, kept {max_sessions} sessions")

# Example usage and testing
if __name__ == "__main__":
    # Test with different asset types
    import time
    
    # Test FX VWAP
    fx_vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
    
    # Simulate some ticks
    current_time = int(time.time() * 1000)
    for i in range(10):
        price = 1.1000 + (i * 0.0001)
        volume = 1000 + (i * 100)
        session = fx_vwap.update_vwap(price, volume, current_time + (i * 1000))
        print(f"FX Tick {i}: Price={price}, VWAP={session.vwap_value if session else 'None'}")
    
    print(f"FX Session Stats: {fx_vwap.get_session_statistics()}")
    
    # Test Crypto VWAP
    crypto_vwap = AdvancedVWAPSessionAnchor("BTCUSDc", AssetType.CRYPTO)
    
    for i in range(10):
        price = 50000 + (i * 100)
        volume = 0.1 + (i * 0.01)
        session = crypto_vwap.update_vwap(price, volume, current_time + (i * 1000))
        print(f"Crypto Tick {i}: Price={price}, VWAP={session.vwap_value if session else 'None'}")
    
    print(f"Crypto Session Stats: {crypto_vwap.get_session_statistics()}")
