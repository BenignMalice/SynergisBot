"""
Session Helper Functions for Auto-Execution Plans
Provides utilities for session-based time condition management
"""

from datetime import datetime, time, timedelta, timezone
from typing import Dict, Optional, Tuple


class SessionHelpers:
    """Helper functions for session-based time management"""
    
    # Session definitions (UTC-based)
    SESSION_TIMES = {
        "ASIAN": (0, 8),      # 00:00-08:00 UTC
        "LONDON": (8, 13),    # 08:00-13:00 UTC
        "OVERLAP": (13, 16),  # 13:00-16:00 UTC (London-NY overlap)
        "NY": (16, 21),       # 16:00-21:00 UTC
        "POST_NY": (21, 24),  # 21:00-24:00 UTC
    }
    
    @staticmethod
    def get_current_session(current_time: Optional[datetime] = None) -> str:
        """
        Get current trading session.
        
        Args:
            current_time: Time to evaluate (defaults to now UTC)
            
        Returns:
            Session name: "ASIAN" | "LONDON" | "NY" | "OVERLAP" | "POST_NY"
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        utc_hour = current_time.hour
        
        # Check overlap first (highest priority)
        if 13 <= utc_hour < 16:
            return "OVERLAP"
        elif 0 <= utc_hour < 8:
            return "ASIAN"
        elif 8 <= utc_hour < 13:
            return "LONDON"
        elif 16 <= utc_hour < 21:
            return "NY"
        elif 21 <= utc_hour < 24:
            return "POST_NY"
        else:
            return "ASIAN"  # Default fallback
    
    @staticmethod
    def get_session_time_range(session: str, date: Optional[datetime] = None) -> Tuple[datetime, datetime]:
        """
        Get start and end datetime for a specific session on a given date.
        
        Args:
            session: Session name ("ASIAN", "LONDON", "NY", "OVERLAP", "POST_NY")
            date: Date to use (defaults to today UTC)
            
        Returns:
            (start_datetime, end_datetime) in UTC
        """
        if date is None:
            date = datetime.now(timezone.utc)
        
        # Get session hours
        start_hour, end_hour = SessionHelpers.SESSION_TIMES.get(session.upper(), (0, 8))
        
        # Create start time
        start_time = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        
        # Create end time (handle next day if needed)
        if end_hour < start_hour:  # Overnight session
            end_time = (date + timedelta(days=1)).replace(hour=end_hour, minute=0, second=0, microsecond=0)
        else:
            end_time = date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        return start_time, end_time
    
    @staticmethod
    def get_time_conditions_for_session(
        session: str,
        date: Optional[datetime] = None,
        buffer_minutes: int = 0
    ) -> Dict[str, str]:
        """
        Get time_after and time_before conditions for a specific session.
        
        Args:
            session: Session name
            date: Date to use (defaults to today UTC)
            buffer_minutes: Minutes to add/subtract from session boundaries
            
        Returns:
            Dict with "time_after" and "time_before" ISO format strings
        """
        start_time, end_time = SessionHelpers.get_session_time_range(session, date)
        
        # Apply buffer
        if buffer_minutes > 0:
            start_time = start_time - timedelta(minutes=buffer_minutes)
            end_time = end_time + timedelta(minutes=buffer_minutes)
        
        return {
            "time_after": start_time.isoformat(),
            "time_before": end_time.isoformat()
        }
    
    @staticmethod
    def get_next_session_time(session: str, current_time: Optional[datetime] = None) -> datetime:
        """
        Get the next occurrence of a session.
        
        Args:
            session: Session name
            current_time: Current time (defaults to now UTC)
            
        Returns:
            Next session start datetime
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        start_time, end_time = SessionHelpers.get_session_time_range(session, current_time)
        
        # If session already started today, get next occurrence
        if current_time >= start_time:
            start_time, _ = SessionHelpers.get_session_time_range(session, current_time + timedelta(days=1))
        
        return start_time
    
    @staticmethod
    def is_session_active(session: str, current_time: Optional[datetime] = None) -> bool:
        """
        Check if a specific session is currently active.
        
        Args:
            session: Session name
            current_time: Current time (defaults to now UTC)
            
        Returns:
            True if session is active
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        current_session = SessionHelpers.get_current_session(current_time)
        return current_session.upper() == session.upper()
    
    @staticmethod
    def get_session_duration_hours(session: str) -> float:
        """
        Get duration of a session in hours.
        
        Args:
            session: Session name
            
        Returns:
            Duration in hours
        """
        start_hour, end_hour = SessionHelpers.SESSION_TIMES.get(session.upper(), (0, 8))
        
        if end_hour < start_hour:  # Overnight
            return (24 - start_hour) + end_hour
        else:
            return end_hour - start_hour


# Convenience functions for direct use
def get_session_time_conditions(session: str, buffer_minutes: int = 0) -> Dict[str, str]:
    """Get time conditions for a session (convenience function)"""
    return SessionHelpers.get_time_conditions_for_session(session, buffer_minutes=buffer_minutes)


def get_next_session_start(session: str) -> str:
    """Get next session start time as ISO string (convenience function)"""
    return SessionHelpers.get_next_session_time(session).isoformat()

