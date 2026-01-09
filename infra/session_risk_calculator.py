"""
Session Risk Calculator
Calculates session risk flags (rollover window, news lock, session profile)
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def calculate_session_risk(
    news_service: Optional[Any] = None,
    symbol: str = "",
    current_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Calculate session risk flags and danger zones.
    
    Args:
        news_service: NewsService instance (optional)
        symbol: Trading symbol (optional, for future use)
        current_time: Current time in UTC (optional, defaults to now)
    
    Returns:
        {
            "is_rollover_window": False,  # True during daily rollover (00:00 UTC ±30min)
            "is_news_lock_active": False,  # True if high-impact news in ±30min window
            "minutes_to_next_high_impact": 75,  # Minutes until next HIGH/ULTRA event
            "is_in_high_impact_window": False,  # True if within ±30min of high-impact event
            "session_profile": "normal",  # "quiet" | "normal" | "explosive" (based on historical vol)
            "session_volatility_multiplier": 1.0,  # Historical vol multiplier for this session
            "rollover_window_start": "2025-12-11T00:00:00Z",  # Next rollover time
            "rollover_window_end": "2025-12-11T00:30:00Z"
        }
    """
    try:
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        else:
            # Ensure timezone-aware
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)
        
        # 1. Calculate rollover window (00:00 UTC ±30min)
        rollover_result = _calculate_rollover_window(current_time)
        
        # 2. Check news service for high-impact events
        news_result = _calculate_news_risk(news_service, current_time)
        
        # 3. Session profile (default to "normal" if historical data unavailable)
        session_profile = "normal"
        session_volatility_multiplier = 1.0
        
        return {
            "is_rollover_window": rollover_result["is_rollover_window"],
            "is_news_lock_active": news_result["is_news_lock_active"],
            "minutes_to_next_high_impact": news_result["minutes_to_next_high_impact"],
            "is_in_high_impact_window": news_result["is_in_high_impact_window"],
            "session_profile": session_profile,
            "session_volatility_multiplier": session_volatility_multiplier,
            "rollover_window_start": rollover_result["rollover_window_start"],
            "rollover_window_end": rollover_result["rollover_window_end"]
        }
        
    except Exception as e:
        logger.error(f"Error calculating session risk: {e}", exc_info=True)
        return _create_default_response(current_time or datetime.now(timezone.utc))


def _calculate_rollover_window(current_time: datetime) -> Dict[str, Any]:
    """Calculate rollover window (00:00 UTC ±30min)"""
    try:
        # Get today's midnight UTC
        today_midnight = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate rollover window for today (23:30 yesterday to 00:30 today)
        rollover_start_today = today_midnight - timedelta(minutes=30)
        rollover_end_today = today_midnight + timedelta(minutes=30)
        
        # Calculate rollover window for tomorrow (23:30 today to 00:30 tomorrow)
        tomorrow_midnight = today_midnight + timedelta(days=1)
        rollover_start_tomorrow = tomorrow_midnight - timedelta(minutes=30)
        rollover_end_tomorrow = tomorrow_midnight + timedelta(minutes=30)
        
        # Check if current time is in today's or tomorrow's rollover window
        is_rollover_window = (
            (rollover_start_today <= current_time <= rollover_end_today) or
            (rollover_start_tomorrow <= current_time <= rollover_end_tomorrow)
        )
        
        # Use tomorrow's window for the response (next rollover)
        next_rollover = tomorrow_midnight
        rollover_start = rollover_start_tomorrow
        rollover_end = rollover_end_tomorrow
        
        return {
            "is_rollover_window": is_rollover_window,
            "rollover_window_start": rollover_start.isoformat().replace('+00:00', 'Z'),
            "rollover_window_end": rollover_end.isoformat().replace('+00:00', 'Z')
        }
        
    except Exception as e:
        logger.error(f"Error calculating rollover window: {e}")
        return {
            "is_rollover_window": False,
            "rollover_window_start": "",
            "rollover_window_end": ""
        }


def _calculate_news_risk(news_service: Optional[Any], current_time: datetime) -> Dict[str, Any]:
    """Calculate news risk flags"""
    try:
        if news_service is None:
            return {
                "is_news_lock_active": False,
                "minutes_to_next_high_impact": None,
                "is_in_high_impact_window": False
            }
        
        # Get upcoming events
        try:
            upcoming_events = news_service.get_upcoming_events(limit=10, hours_ahead=24)
        except Exception as e:
            logger.debug(f"Error getting upcoming events: {e}")
            upcoming_events = []
        
        if not upcoming_events or len(upcoming_events) == 0:
            return {
                "is_news_lock_active": False,
                "minutes_to_next_high_impact": None,
                "is_in_high_impact_window": False
            }
        
        # Filter high-impact events
        high_impact_events = []
        for event in upcoming_events:
            impact = event.get("impact", "").upper()
            if impact in ["HIGH", "ULTRA"]:
                high_impact_events.append(event)
        
        if not high_impact_events:
            return {
                "is_news_lock_active": False,
                "minutes_to_next_high_impact": None,
                "is_in_high_impact_window": False
            }
        
        # Find next high-impact event
        next_event = None
        min_minutes = float('inf')
        
        for event in high_impact_events:
            event_time_str = event.get("time", "")
            if not event_time_str:
                continue
            
            try:
                # Parse event time
                if isinstance(event_time_str, str):
                    from dateutil import parser
                    event_time = parser.parse(event_time_str)
                    if event_time.tzinfo is None:
                        event_time = event_time.replace(tzinfo=timezone.utc)
                elif isinstance(event_time_str, datetime):
                    event_time = event_time_str
                    if event_time.tzinfo is None:
                        event_time = event_time.replace(tzinfo=timezone.utc)
                else:
                    continue
                
                # Calculate minutes until event
                time_diff = event_time - current_time
                minutes_until = time_diff.total_seconds() / 60.0
                
                # Only consider future events
                if minutes_until >= 0 and minutes_until < min_minutes:
                    min_minutes = minutes_until
                    next_event = event
                    
            except Exception as e:
                logger.debug(f"Error parsing event time: {e}")
                continue
        
        # Check if in high-impact window (±30min)
        is_in_window = False
        if next_event and min_minutes != float('inf'):
            is_in_window = abs(min_minutes) <= 30
        
        minutes_to_next = int(min_minutes) if min_minutes != float('inf') else None
        
        return {
            "is_news_lock_active": is_in_window,
            "minutes_to_next_high_impact": minutes_to_next,
            "is_in_high_impact_window": is_in_window
        }
        
    except Exception as e:
        logger.error(f"Error calculating news risk: {e}")
        return {
            "is_news_lock_active": False,
            "minutes_to_next_high_impact": None,
            "is_in_high_impact_window": False
        }


def _create_default_response(current_time: datetime) -> Dict[str, Any]:
    """Create default response for error cases"""
    try:
        next_rollover = (current_time.date() + timedelta(days=1))
        next_rollover = datetime.combine(next_rollover, datetime.min.time(), tzinfo=timezone.utc)
        rollover_start = next_rollover - timedelta(minutes=30)
        rollover_end = next_rollover + timedelta(minutes=30)
        
        return {
            "is_rollover_window": False,
            "is_news_lock_active": False,
            "minutes_to_next_high_impact": None,
            "is_in_high_impact_window": False,
            "session_profile": "normal",
            "session_volatility_multiplier": 1.0,
            "rollover_window_start": rollover_start.isoformat().replace('+00:00', 'Z'),
            "rollover_window_end": rollover_end.isoformat().replace('+00:00', 'Z')
        }
    except Exception:
        return {
            "is_rollover_window": False,
            "is_news_lock_active": False,
            "minutes_to_next_high_impact": None,
            "is_in_high_impact_window": False,
            "session_profile": "normal",
            "session_volatility_multiplier": 1.0,
            "rollover_window_start": "",
            "rollover_window_end": ""
        }

