"""
Session Analyzer - Detect current trading session and provide session-specific guidance
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List

logger = logging.getLogger(__name__)


class SessionAnalyzer:
    """Analyze current trading session and provide recommendations"""
    
    # Session definitions (UTC times)
    SESSIONS = {
        "asian": {
            "start": 0,  # 00:00 UTC
            "end": 8,    # 08:00 UTC
            "name": "Asian Session",
            "major_centers": ["Tokyo", "Singapore", "Hong Kong"],
            "volatility": "low",
            "typical_range_pips": {
                "forex": "20-40",
                "gold": "$1-$3",
                "bitcoin": "$50-$200"
            },
            "best_pairs": ["USDJPY", "AUDUSD", "NZDJPY", "AUDJPY"],
            "avoid_pairs": ["EURUSD", "GBPUSD"],
            "strategy": "range_trading",
            "characteristics": [
                "Lower volatility and tighter ranges",
                "Good for scalping and range-bound strategies",
                "Avoid breakout trades",
                "Tokyo open (00:00 UTC) can bring movement"
            ]
        },
        "london": {
            "start": 8,   # 08:00 UTC
            "end": 16,    # 16:00 UTC
            "name": "London Session",
            "major_centers": ["London", "Frankfurt", "Zurich"],
            "volatility": "high",
            "typical_range_pips": {
                "forex": "60-100",
                "gold": "$5-$15",
                "bitcoin": "$300-$800"
            },
            "best_pairs": ["EURUSD", "GBPUSD", "EURGBP", "XAUUSD"],
            "avoid_pairs": [],
            "strategy": "trend_following",
            "characteristics": [
                "Highest volatility and liquidity",
                "Strong trends often develop",
                "London open (08:00 UTC) is very volatile",
                "Best for breakout and trend trades"
            ]
        },
        "ny": {
            "start": 13,  # 13:00 UTC
            "end": 22,    # 22:00 UTC
            "name": "New York Session",
            "major_centers": ["New York", "Chicago", "Toronto"],
            "volatility": "high",
            "typical_range_pips": {
                "forex": "50-90",
                "gold": "$4-$12",
                "bitcoin": "$250-$700"
            },
            "best_pairs": ["EURUSD", "GBPUSD", "USDCAD", "XAUUSD", "BTCUSD"],
            "avoid_pairs": [],
            "strategy": "trend_following",
            "characteristics": [
                "High volatility, especially at open",
                "Major news releases (NFP, CPI, Fed)",
                "NY open (13:00 UTC) brings strong moves",
                "Good for continuation and reversal trades"
            ]
        },
        "overlap_london_ny": {
            "start": 13,  # 13:00 UTC
            "end": 16,    # 16:00 UTC
            "name": "London/NY Overlap",
            "major_centers": ["London", "New York"],
            "volatility": "very_high",
            "typical_range_pips": {
                "forex": "80-120",
                "gold": "$8-$20",
                "bitcoin": "$400-$1000"
            },
            "best_pairs": ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD"],
            "avoid_pairs": [],
            "strategy": "breakout_and_trend",
            "characteristics": [
                "Highest liquidity and volatility",
                "Best time for breakout trades",
                "Major institutional activity",
                "Widest stops recommended"
            ]
        },
        "late_ny": {
            "start": 20,  # 20:00 UTC
            "end": 24,    # 24:00 UTC (00:00)
            "name": "Late NY / Pre-Asian",
            "major_centers": ["New York (closing)"],
            "volatility": "low",
            "typical_range_pips": {
                "forex": "15-30",
                "gold": "$1-$2",
                "bitcoin": "$50-$150"
            },
            "best_pairs": [],
            "avoid_pairs": ["All pairs"],
            "strategy": "avoid_trading",
            "characteristics": [
                "Very low liquidity",
                "Erratic price movements",
                "Not recommended for trading",
                "Wait for Asian session open"
            ]
        }
    }
    
    def get_current_session(self, now: datetime = None) -> Dict:
        """
        Get current trading session with detailed information
        
        Returns:
            dict with session name, volatility, best pairs, strategy, etc.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        
        utc_hour = now.hour
        
        # Determine session
        if 13 <= utc_hour < 16:
            # London/NY overlap (most important)
            session_key = "overlap_london_ny"
        elif 20 <= utc_hour < 24:
            # Late NY
            session_key = "late_ny"
        elif 0 <= utc_hour < 8:
            # Asian
            session_key = "asian"
        elif 8 <= utc_hour < 13:
            # London only
            session_key = "london"
        else:  # 16 <= utc_hour < 20
            # NY only (after London close)
            session_key = "ny"
        
        session = self.SESSIONS[session_key].copy()
        
        # Add current time info
        session["current_utc_time"] = now.strftime("%H:%M UTC")
        session["current_utc_hour"] = utc_hour
        
        # Add session-specific recommendations
        session["recommendations"] = self._get_session_recommendations(session_key, session)
        
        # Add risk management adjustments
        session["risk_adjustments"] = self._get_risk_adjustments(session)
        
        # Add next session info
        session["next_session"] = self._get_next_session(utc_hour)
        
        return session
    
    def _get_session_recommendations(self, session_key: str, session: Dict) -> List[str]:
        """Get specific recommendations for the session"""
        recommendations = []
        
        if session_key == "overlap_london_ny":
            recommendations = [
                "✅ Best time to trade - highest liquidity",
                "✅ Excellent for breakout trades",
                "✅ Use wider stops (1.5-2x normal)",
                "✅ Watch for major news releases",
                "⚠️ Spreads may widen during high volatility"
            ]
        elif session_key == "london":
            recommendations = [
                "✅ High volatility - good for trend trades",
                "✅ London open (08:00 UTC) is very active",
                "✅ Focus on EUR and GBP pairs",
                "✅ Use normal to slightly wider stops",
                "⚠️ Avoid counter-trend trades"
            ]
        elif session_key == "ny":
            recommendations = [
                "✅ Good for continuation trades",
                "✅ Watch for US news releases (13:30-15:00 UTC)",
                "✅ Focus on USD pairs and gold",
                "✅ Use normal stops",
                "⚠️ Volatility decreases after 18:00 UTC"
            ]
        elif session_key == "asian":
            recommendations = [
                "✅ Good for range trading and scalping",
                "✅ Focus on JPY, AUD, NZD pairs",
                "✅ Use tighter stops (0.7-1x normal)",
                "⚠️ Avoid breakout trades - low volume",
                "⚠️ Ranges are typically 50% of London session"
            ]
        elif session_key == "late_ny":
            recommendations = [
                "❌ Not recommended for trading",
                "❌ Very low liquidity - erratic moves",
                "❌ Wide spreads",
                "✅ Good time to review and plan",
                "✅ Wait for Asian session (00:00 UTC)"
            ]
        
        return recommendations
    
    def _get_risk_adjustments(self, session: Dict) -> Dict:
        """Get risk management adjustments for the session"""
        volatility = session["volatility"]
        
        if volatility == "very_high":
            return {
                "stop_loss_multiplier": 1.5,
                "position_size_multiplier": 0.75,
                "confidence_adjustment": 0,
                "description": "Widen stops by 50%, reduce size by 25%"
            }
        elif volatility == "high":
            return {
                "stop_loss_multiplier": 1.2,
                "position_size_multiplier": 1.0,
                "confidence_adjustment": 5,
                "description": "Widen stops by 20%, normal size"
            }
        elif volatility == "low":
            return {
                "stop_loss_multiplier": 0.8,
                "position_size_multiplier": 1.0,
                "confidence_adjustment": -5,
                "description": "Tighten stops by 20%, normal size"
            }
        else:
            return {
                "stop_loss_multiplier": 1.0,
                "position_size_multiplier": 1.0,
                "confidence_adjustment": 0,
                "description": "Normal risk parameters"
            }
    
    def _get_next_session(self, current_hour: int) -> Dict:
        """Get information about the next session"""
        if current_hour < 8:
            return {
                "name": "London Session",
                "starts_in_hours": 8 - current_hour,
                "start_time": "08:00 UTC"
            }
        elif current_hour < 13:
            return {
                "name": "NY Session / London-NY Overlap",
                "starts_in_hours": 13 - current_hour,
                "start_time": "13:00 UTC"
            }
        elif current_hour < 16:
            return {
                "name": "NY Session (after London close)",
                "starts_in_hours": 16 - current_hour,
                "start_time": "16:00 UTC"
            }
        elif current_hour < 20:
            return {
                "name": "Late NY Session",
                "starts_in_hours": 20 - current_hour,
                "start_time": "20:00 UTC"
            }
        else:
            return {
                "name": "Asian Session",
                "starts_in_hours": 24 - current_hour,
                "start_time": "00:00 UTC"
            }
    
    def is_good_time_to_trade(self, now: datetime = None) -> bool:
        """Check if current time is good for trading"""
        session = self.get_current_session(now)
        return session["strategy"] != "avoid_trading"
    
    def get_optimal_symbols(self, now: datetime = None) -> List[str]:
        """Get optimal symbols for current session"""
        session = self.get_current_session(now)
        return session["best_pairs"]
    
    def adjust_confidence_for_session(
        self,
        base_confidence: int,
        symbol: str,
        now: datetime = None
    ) -> Dict:
        """
        Adjust confidence based on session suitability
        
        Returns:
            dict with adjusted_confidence and reasoning
        """
        session = self.get_current_session(now)
        
        # Base adjustment from session
        adjustment = session["risk_adjustments"]["confidence_adjustment"]
        
        # Additional adjustment based on symbol suitability
        best_pairs = session["best_pairs"]
        avoid_pairs = session["avoid_pairs"]
        
        if symbol in best_pairs:
            adjustment += 5
            reason = f"Optimal for {session['name']}"
        elif symbol in avoid_pairs:
            adjustment -= 15
            reason = f"Not recommended during {session['name']}"
        else:
            reason = f"Acceptable for {session['name']}"
        
        # Clamp confidence to 0-100
        adjusted_confidence = max(0, min(100, base_confidence + adjustment))
        
        return {
            "base_confidence": base_confidence,
            "adjusted_confidence": adjusted_confidence,
            "adjustment": adjustment,
            "reason": reason,
            "session": session["name"]
        }
