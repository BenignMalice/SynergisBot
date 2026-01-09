"""
Weekend Profile Manager
Manages weekend trading profile activation and deactivation for BTCUSDc.

Active Window: Friday 23:00 UTC → Monday 03:00 UTC

NOTE: Existing code uses different weekend definition (Friday 21:00 UTC → Sunday 22:00 UTC)
in m1_refresh_manager.py and discord_alert_dispatcher.py. This manager uses
the weekend trading profile definition (Fri 23:00 → Mon 03:00) for BTC weekend trading.
"""

import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class WeekendProfileManager:
    """
    Manages weekend trading profile activation and deactivation.
    Active: Friday 23:00 UTC → Monday 03:00 UTC
    """
    
    WEEKEND_START_DAY = 4  # Friday
    WEEKEND_START_HOUR = 23  # 23:00 UTC
    WEEKEND_END_DAY = 0  # Monday
    WEEKEND_END_HOUR = 3  # 03:00 UTC
    
    def __init__(self):
        """Initialize Weekend Profile Manager"""
        self._last_transition_check: Optional[datetime] = None
    
    def is_weekend_active(self, check_time: Optional[datetime] = None) -> bool:
        """
        Check if weekend profile should be active.
        
        Args:
            check_time: Optional datetime to check (defaults to now UTC)
        
        Returns:
            True if weekend profile is active, False otherwise
        """
        if check_time is None:
            check_time = datetime.now(timezone.utc)
        
        weekday = check_time.weekday()
        hour = check_time.hour
        
        # Friday 23:00 UTC onwards
        if weekday == self.WEEKEND_START_DAY and hour >= self.WEEKEND_START_HOUR:
            return True
        
        # Saturday (all day)
        if weekday == 5:
            return True
        
        # Sunday (all day)
        if weekday == 6:
            return True
        
        # Monday before 03:00 UTC
        if weekday == self.WEEKEND_END_DAY and hour < self.WEEKEND_END_HOUR:
            return True
        
        return False
    
    def is_weekend_active_at_time(self, check_time: datetime) -> bool:
        """
        Check if weekend was active at a specific time.
        
        Args:
            check_time: Datetime to check (must be timezone-aware UTC)
        
        Returns:
            True if weekend was active at that time, False otherwise
        """
        return self.is_weekend_active(check_time)
    
    def get_weekend_subsession(self, check_time: Optional[datetime] = None) -> Optional[str]:
        """
        Get current weekend micro-session.
        
        Args:
            check_time: Optional datetime to check (defaults to now UTC)
        
        Returns:
            Sub-session name or None if not weekend
        """
        if check_time is None:
            check_time = datetime.now(timezone.utc)
        
        if not self.is_weekend_active(check_time):
            return None
        
        weekday = check_time.weekday()
        hour = check_time.hour
        
        if weekday == 4 and hour >= 23:  # Fri 23:00+
            return "ASIAN_RETAIL_BURST"
        elif weekday == 5:
            if hour < 6:  # Sat 00:00-06:00
                return "ASIAN_RETAIL_BURST"
            elif hour < 18:  # Sat 06:00-18:00
                return "LOW_LIQUIDITY_RANGE"
            else:  # Sat 18:00-24:00
                return "DEAD_ZONE"
        elif weekday == 6:
            if hour < 12:  # Sun 00:00-12:00
                return "DEAD_ZONE"
            elif hour < 22:  # Sun 12:00-22:00
                return "CME_ANTICIPATION"
            else:  # Sun 22:00-24:00
                return "CME_GAP_REVERSION"
        elif weekday == 0 and hour < 3:  # Mon 00:00-03:00
            return "CME_GAP_REVERSION"
        
        return None
    
    def get_time_until_weekend_ends(self) -> Optional[str]:
        """
        Get time until weekend ends (if weekend is active).
        
        Returns:
            Human-readable time string or None if not weekend
        """
        if not self.is_weekend_active():
            return None
        
        now = datetime.now(timezone.utc)
        weekday = now.weekday()
        hour = now.hour
        
        # Calculate time until Monday 03:00 UTC
        if weekday == 4:  # Friday
            hours_until = (24 - hour) + 48 + 3  # Remaining Friday + Saturday + Sunday + Monday until 03:00
        elif weekday == 5:  # Saturday
            hours_until = (24 - hour) + 24 + 3  # Remaining Saturday + Sunday + Monday until 03:00
        elif weekday == 6:  # Sunday
            hours_until = (24 - hour) + 3  # Remaining Sunday + Monday until 03:00
        else:  # Monday before 03:00
            hours_until = 3 - hour
        
        if hours_until < 1:
            return f"{int(hours_until * 60)} minutes"
        elif hours_until < 24:
            return f"{int(hours_until)} hours"
        else:
            days = hours_until // 24
            hours = hours_until % 24
            return f"{int(days)} days, {int(hours)} hours"
    
    def get_time_until_weekend_starts(self) -> Optional[str]:
        """
        Get time until weekend starts (if weekday).
        
        Returns:
            Human-readable time string or None if weekend is active
        """
        if self.is_weekend_active():
            return None
        
        now = datetime.now(timezone.utc)
        weekday = now.weekday()
        hour = now.hour
        
        # Calculate time until Friday 23:00 UTC
        if weekday == 0:  # Monday
            hours_until = (24 - hour) + (24 * 3) + 23  # Remaining Monday + Tue/Wed/Thu + Friday until 23:00
        elif weekday == 1:  # Tuesday
            hours_until = (24 - hour) + (24 * 2) + 23  # Remaining Tuesday + Wed/Thu + Friday until 23:00
        elif weekday == 2:  # Wednesday
            hours_until = (24 - hour) + 24 + 23  # Remaining Wednesday + Thursday + Friday until 23:00
        elif weekday == 3:  # Thursday
            hours_until = (24 - hour) + 23  # Remaining Thursday + Friday until 23:00
        else:  # Friday before 23:00
            hours_until = 23 - hour
        
        if hours_until < 1:
            return f"{int(hours_until * 60)} minutes"
        elif hours_until < 24:
            return f"{int(hours_until)} hours"
        else:
            days = hours_until // 24
            hours = hours_until % 24
            return f"{int(days)} days, {int(hours)} hours"

