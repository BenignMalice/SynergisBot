"""
Feature Session News Module
Computes session tags, news timing, and calendar context
IMPROVED: Phase 4.2 - Added overlap detection and session strength
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, time, timedelta
from dataclasses import dataclass
import logging
import json
import os

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """
    Complete session context for trading decisions.
    IMPROVED: Phase 4.2 - Enhanced session detection.
    """
    primary_session: str  # "ASIA", "LONDON", "NY", "UNKNOWN"
    is_overlap: bool
    overlap_type: Optional[str]  # "LONDON_NY", "ASIA_LONDON", "NY_ASIA"
    minutes_into_session: int
    session_strength: float  # 0.0-1.0, reduced during transitions
    is_transition_period: bool  # First/last 30 minutes
    is_weekend: bool
    is_market_open: bool

class SessionNewsFeatures:
    """
    IMPROVED: Computes session and news features for market context.
    Focuses on session identification and news timing analysis.
    """
    
    def __init__(self):
        self.news_events = self._load_news_events()
        self.session_times = self._get_session_times()
    
    def compute(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Compute all session and news features for the given DataFrame."""
        try:
            features = {}
            
            # Session analysis
            features.update(self._compute_session_analysis(df))
            
            # News analysis
            features.update(self._compute_news_analysis(df))
            
            # Market hours analysis
            features.update(self._compute_market_hours_analysis(df))
            
            return features
            
        except Exception as e:
            logger.error(f"Session/News computation failed for {symbol} {timeframe}: {e}")
            return {}
    
    def _compute_session_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute session analysis features."""
        try:
            features = {}
            
            if df.empty:
                return {"session": "unknown", "session_minutes": 0, "session_strength": 0.0}
            
            # Get current time
            current_time = datetime.now(timezone.utc)
            features["current_time"] = current_time.isoformat()
            
            # Determine current session
            current_session = self._get_current_session(current_time)
            features["session"] = current_session
            
            # Calculate minutes since session open
            session_minutes = self._get_session_minutes(current_time, current_session)
            features["session_minutes"] = session_minutes
            
            # Session strength (based on typical volume patterns)
            features["session_strength"] = self._calculate_session_strength(current_session, session_minutes)
            
            # Session overlap analysis
            features["session_overlap"] = self._check_session_overlap(current_time)
            
            # Weekend analysis
            features["is_weekend"] = current_time.weekday() >= 5
            features["is_market_open"] = not features["is_weekend"] and current_session != "closed"
            
            return features
            
        except Exception as e:
            logger.error(f"Session analysis computation failed: {e}")
            return {"session": "unknown", "session_minutes": 0, "session_strength": 0.0}
    
    def _compute_news_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute news analysis features."""
        try:
            features = {}
            
            current_time = datetime.now(timezone.utc)
            
            # Find upcoming news events
            upcoming_news = self._find_upcoming_news(current_time)
            features["news_count"] = len(upcoming_news)
            
            if upcoming_news:
                # Next news event
                next_news = upcoming_news[0]
                features["next_news_time"] = next_news["time"].isoformat()
                features["next_news_impact"] = next_news["impact"]
                features["next_news_currency"] = next_news.get("currency", "USD")
                features["next_news_title"] = next_news.get("title", "Unknown Event")
                
                # Minutes to next news
                time_to_news = (next_news["time"] - current_time).total_seconds() / 60
                features["news_minutes"] = int(time_to_news)
                
                # News blackout window
                features["news_blackout"] = self._is_in_news_blackout(current_time, next_news)
                
                # High impact news count
                high_impact_count = sum(1 for news in upcoming_news if news["impact"] in ["High", "Medium-High"])
                features["high_impact_news_count"] = high_impact_count
                
                # News density (events per hour)
                if len(upcoming_news) > 1:
                    time_span = (upcoming_news[-1]["time"] - upcoming_news[0]["time"]).total_seconds() / 3600
                    features["news_density"] = len(upcoming_news) / max(time_span, 1)
                else:
                    features["news_density"] = 0.0
            else:
                features["next_news_time"] = None
                features["next_news_impact"] = "None"
                features["next_news_currency"] = "USD"
                features["next_news_title"] = "No Upcoming Events"
                features["news_minutes"] = None
                features["news_blackout"] = False
                features["high_impact_news_count"] = 0
                features["news_density"] = 0.0
            
            return features
            
        except Exception as e:
            logger.error(f"News analysis computation failed: {e}")
            return {"news_count": 0, "news_blackout": False}
    
    def _compute_market_hours_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute market hours analysis features."""
        try:
            features = {}
            
            current_time = datetime.now(timezone.utc)
            
            # Market hours status
            features["market_open"] = self._is_market_open(current_time)
            features["market_hours_remaining"] = self._get_market_hours_remaining(current_time)
            
            # Trading session quality
            features["trading_quality"] = self._assess_trading_quality(current_time)
            
            # Volatility expectations
            features["expected_volatility"] = self._get_expected_volatility(current_time)
            
            # Liquidity expectations
            features["expected_liquidity"] = self._get_expected_liquidity(current_time)
            
            return features
            
        except Exception as e:
            logger.error(f"Market hours analysis computation failed: {e}")
            return {"market_open": False, "trading_quality": "unknown"}
    
    def _get_current_session(self, current_time: datetime) -> str:
        """
        Determine current trading session.
        IMPROVED: Phase 4.2 - Standardized session names and UTC times.
        """
        try:
            utc_time = current_time.time()
            weekday = current_time.weekday()
            
            # Weekend check
            if weekday >= 5:  # Saturday or Sunday
                return "UNKNOWN"
            
            # Session times (UTC) - standardized for Phase 4.2
            asia_start = time(22, 0)  # 22:00 UTC (previous day)
            asia_end = time(8, 0)     # 08:00 UTC
            london_start = time(8, 0)   # 08:00 UTC
            london_end = time(16, 0)    # 16:00 UTC
            ny_start = time(13, 0)      # 13:00 UTC
            ny_end = time(21, 0)        # 21:00 UTC
            
            # Check sessions (handle wrap-around for Asia)
            hour = utc_time.hour
            
            if 8 <= hour < 16:
                return "LONDON"
            elif 13 <= hour < 21:  # Will overlap with London 13-16
                return "NY"
            elif hour >= 22 or hour < 8:
                return "ASIA"
            else:
                return "UNKNOWN"
                
        except Exception:
            return "UNKNOWN"
    
    def _get_session_minutes(self, current_time: datetime, session: str) -> int:
        """Calculate minutes since session open."""
        try:
            if session == "closed" or session == "unknown":
                return 0
            
            utc_time = current_time.time()
            
            # Session open times (UTC)
            session_opens = {
                "tokyo": time(0, 0),
                "london": time(7, 0),
                "new_york": time(12, 0)
            }
            
            if session in session_opens:
                session_open = session_opens[session]
                session_start = datetime.combine(current_time.date(), session_open)
                
                # Handle overnight sessions
                if session == "tokyo" and utc_time < time(9, 0):
                    # Tokyo session spans midnight
                    if utc_time >= time(0, 0):
                        # Same day
                        session_start = datetime.combine(current_time.date(), session_open)
                    else:
                        # Previous day
                        session_start = datetime.combine(current_time.date() - timedelta(days=1), session_open)
                
                minutes = int((current_time - session_start).total_seconds() / 60)
                return max(0, minutes)
            
            return 0
            
        except Exception:
            return 0
    
    def _calculate_session_strength(self, session: str, session_minutes: int) -> float:
        """Calculate session strength based on typical volume patterns."""
        try:
            if session == "closed" or session == "unknown":
                return 0.0
            
            # Session strength based on time within session
            if session == "tokyo":
                # Tokyo session is typically weaker
                if session_minutes < 60:
                    return 0.3
                elif session_minutes < 300:  # 5 hours
                    return 0.5
                else:
                    return 0.2
            elif session == "london":
                # London session is typically strong
                if session_minutes < 60:
                    return 0.4
                elif session_minutes < 300:  # 5 hours
                    return 0.8
                else:
                    return 0.6
            elif session == "new_york":
                # New York session is typically strong
                if session_minutes < 60:
                    return 0.5
                elif session_minutes < 300:  # 5 hours
                    return 0.9
                else:
                    return 0.7
            
            return 0.5
            
        except Exception:
            return 0.5
    
    def _check_session_overlap(self, current_time: datetime) -> bool:
        """Check if we're in a session overlap period."""
        try:
            utc_time = current_time.time()
            
            # London-NY overlap (12:00-16:00 UTC)
            london_ny_overlap = time(12, 0) <= utc_time < time(16, 0)
            
            # Tokyo-London overlap (7:00-9:00 UTC)
            tokyo_london_overlap = time(7, 0) <= utc_time < time(9, 0)
            
            return london_ny_overlap or tokyo_london_overlap
            
        except Exception:
            return False
    
    def _find_upcoming_news(self, current_time: datetime) -> List[Dict[str, Any]]:
        """Find upcoming news events."""
        try:
            if not self.news_events:
                return []
            
            upcoming = []
            for event in self.news_events:
                event_time = event.get("time")
                if event_time and event_time > current_time:
                    # Only include events within next 24 hours
                    if (event_time - current_time).total_seconds() <= 86400:
                        upcoming.append(event)
            
            # Sort by time
            upcoming.sort(key=lambda x: x.get("time", datetime.max))
            return upcoming
            
        except Exception:
            return []
    
    def _is_in_news_blackout(self, current_time: datetime, news_event: Dict[str, Any]) -> bool:
        """Check if we're in a news blackout window."""
        try:
            if not news_event or "time" not in news_event:
                return False
            
            event_time = news_event["time"]
            impact = news_event.get("impact", "Low")
            
            # Blackout windows based on impact
            if impact in ["High", "Medium-High"]:
                blackout_before = 60  # 1 hour before
                blackout_after = 90   # 1.5 hours after
            elif impact == "Medium":
                blackout_before = 30  # 30 minutes before
                blackout_after = 60   # 1 hour after
            else:
                blackout_before = 15  # 15 minutes before
                blackout_after = 30   # 30 minutes after
            
            time_to_event = (event_time - current_time).total_seconds() / 60
            time_after_event = (current_time - event_time).total_seconds() / 60
            
            return (0 <= time_to_event <= blackout_before) or (0 <= time_after_event <= blackout_after)
            
        except Exception:
            return False
    
    def _is_market_open(self, current_time: datetime) -> bool:
        """Check if market is currently open."""
        try:
            session = self._get_current_session(current_time)
            return session != "closed" and session != "unknown"
        except Exception:
            return False
    
    def _get_market_hours_remaining(self, current_time: datetime) -> int:
        """Get remaining market hours in minutes."""
        try:
            if not self._is_market_open(current_time):
                return 0
            
            session = self._get_current_session(current_time)
            session_minutes = self._get_session_minutes(current_time, session)
            
            # Session durations in minutes
            session_durations = {
                "tokyo": 540,    # 9 hours
                "london": 540,   # 9 hours
                "new_york": 540  # 9 hours
            }
            
            if session in session_durations:
                remaining = session_durations[session] - session_minutes
                return max(0, remaining)
            
            return 0
            
        except Exception:
            return 0
    
    def _assess_trading_quality(self, current_time: datetime) -> str:
        """Assess current trading quality."""
        try:
            if not self._is_market_open(current_time):
                return "closed"
            
            session = self._get_current_session(current_time)
            session_minutes = self._get_session_minutes(current_time, session)
            is_overlap = self._check_session_overlap(current_time)
            
            if is_overlap:
                return "excellent"
            elif session_minutes < 60:
                return "good"
            elif session_minutes < 300:
                return "very_good"
            else:
                return "fair"
                
        except Exception:
            return "unknown"
    
    def _get_expected_volatility(self, current_time: datetime) -> str:
        """Get expected volatility level."""
        try:
            if not self._is_market_open(current_time):
                return "low"
            
            session = self._get_current_session(current_time)
            is_overlap = self._check_session_overlap(current_time)
            
            if is_overlap:
                return "high"
            elif session == "london" or session == "new_york":
                return "medium"
            else:
                return "low"
                
        except Exception:
            return "medium"
    
    def _get_expected_liquidity(self, current_time: datetime) -> str:
        """Get expected liquidity level."""
        try:
            if not self._is_market_open(current_time):
                return "low"
            
            session = self._get_current_session(current_time)
            is_overlap = self._check_session_overlap(current_time)
            
            if is_overlap:
                return "high"
            elif session == "london" or session == "new_york":
                return "medium"
            else:
                return "low"
                
        except Exception:
            return "medium"
    
    def _load_news_events(self) -> List[Dict[str, Any]]:
        """Load news events from file."""
        try:
            news_path = os.path.join(os.path.dirname(__file__), "..", "data", "news_events.json")
            if os.path.exists(news_path):
                with open(news_path, 'r') as f:
                    data = json.load(f)
                    
                    # Handle both dict with "events" key and direct list format
                    if isinstance(data, dict):
                        events = data.get("events", [])
                    elif isinstance(data, list):
                        events = data
                    else:
                        logger.warning(f"Unexpected news events format: {type(data)}")
                        return []
                    
                    # Convert time strings to datetime objects
                    for event in events:
                        if "time" in event and isinstance(event["time"], str):
                            try:
                                event["time"] = datetime.fromisoformat(event["time"].replace('Z', '+00:00'))
                            except:
                                pass
                    
                    return events
            return []
            
        except Exception as e:
            logger.error(f"Failed to load news events: {e}")
            return []
    
    def _get_session_times(self) -> Dict[str, Dict[str, time]]:
        """Get session time definitions."""
        return {
            "tokyo": {"open": time(0, 0), "close": time(9, 0)},
            "london": {"open": time(7, 0), "close": time(16, 0)},
            "new_york": {"open": time(12, 0), "close": time(21, 0)}
        }
    
    # ========================================================================
    # IMPROVED: Phase 4.2 - Enhanced Session Detection Methods
    # ========================================================================
    
    def _detect_overlap(self, current_time: datetime) -> tuple:
        """
        Detect if current time is in a session overlap period.
        IMPROVED: Phase 4.2 - New overlap detection.
        
        Returns:
            (is_overlap: bool, overlap_type: Optional[str])
        """
        try:
            hour = current_time.hour
            
            # LONDON-NY overlap: 13:00-16:00 UTC (peak liquidity)
            if 13 <= hour < 16:
                return True, "LONDON_NY"
            
            # ASIA-LONDON overlap: 08:00-09:00 UTC (transitional)
            if 8 <= hour < 9:
                return True, "ASIA_LONDON"
            
            # NY-ASIA overlap: 21:00-22:00 UTC (thin, transitional)
            if 21 <= hour < 22:
                return True, "NY_ASIA"
            
            return False, None
            
        except Exception:
            return False, None
    
    def _is_transition_period(self, session: str, minutes_into: int) -> bool:
        """
        Check if currently in transition period (first/last 30 minutes).
        IMPROVED: Phase 4.2 - New transition detection.
        """
        try:
            # First 30 minutes
            if minutes_into < 30:
                return True
            
            # Last 30 minutes (approximate session durations)
            session_durations = {
                "ASIA": 10 * 60,  # 10 hours
                "LONDON": 8 * 60,  # 8 hours
                "NY": 8 * 60       # 8 hours
            }
            
            duration = session_durations.get(session, 480)  # Default 8 hours
            if minutes_into > (duration - 30):
                return True
            
            return False
            
        except Exception:
            return False
    
    def _calculate_session_strength_enhanced(
        self,
        session: str,
        minutes_into: int,
        is_overlap: bool,
        overlap_type: Optional[str]
    ) -> float:
        """
        Calculate session strength (0.0-1.0).
        IMPROVED: Phase 4.2 - Enhanced with overlap awareness.
        
        Returns:
            0.0-1.0 strength score (reduced during transitions and thin overlaps)
        """
        try:
            # Base strength by session
            base_strength = {
                "LONDON": 1.0,  # Highest liquidity
                "NY": 0.95,     # High liquidity
                "ASIA": 0.7,    # Lower liquidity
                "UNKNOWN": 0.5
            }.get(session, 0.5)
            
            # Overlap adjustments
            if is_overlap:
                if overlap_type == "LONDON_NY":
                    base_strength = 1.0  # Peak liquidity
                elif overlap_type in ["ASIA_LONDON", "NY_ASIA"]:
                    base_strength *= 0.7  # Transitional, thin
            
            # Time-based adjustment (ramp up/down)
            time_factor = 1.0
            if minutes_into < 30:
                # Ramp up in first 30 minutes
                time_factor = 0.6 + (minutes_into / 30) * 0.4
            elif minutes_into > 450:  # Last 30 minutes (assuming 8hr session)
                # Ramp down in last 30 minutes
                remaining = max(0, 480 - minutes_into)
                time_factor = 0.6 + (remaining / 30) * 0.4
            
            strength = base_strength * time_factor
            return max(0.0, min(1.0, strength))
            
        except Exception:
            return 0.7
    
    def get_session_info(self, current_time: Optional[datetime] = None) -> SessionInfo:
        """
        Get complete session information.
        IMPROVED: Phase 4.2 - New comprehensive session info method.
        
        Args:
            current_time: Time to evaluate (defaults to now UTC)
            
        Returns:
            SessionInfo dataclass with complete session context
        """
        try:
            if current_time is None:
                current_time = datetime.now(timezone.utc)
            
            # Detect session
            primary_session = self._get_current_session(current_time)
            
            # Detect overlap
            is_overlap, overlap_type = self._detect_overlap(current_time)
            
            # Calculate minutes into session
            minutes_into = self._get_session_minutes(current_time, primary_session)
            
            # Check if transition period
            is_transition = self._is_transition_period(primary_session, minutes_into)
            
            # Calculate session strength
            session_strength = self._calculate_session_strength_enhanced(
                primary_session, minutes_into, is_overlap, overlap_type
            )
            
            # Weekend and market open checks
            is_weekend = current_time.weekday() >= 5
            is_market_open = not is_weekend and primary_session != "UNKNOWN"
            
            return SessionInfo(
                primary_session=primary_session,
                is_overlap=is_overlap,
                overlap_type=overlap_type,
                minutes_into_session=minutes_into,
                session_strength=session_strength,
                is_transition_period=is_transition,
                is_weekend=is_weekend,
                is_market_open=is_market_open
            )
            
        except Exception as e:
            logger.error(f"Session info generation failed: {e}")
            # Return safe default
            return SessionInfo(
                primary_session="UNKNOWN",
                is_overlap=False,
                overlap_type=None,
                minutes_into_session=0,
                session_strength=0.5,
                is_transition_period=False,
                is_weekend=False,
                is_market_open=False
            )
