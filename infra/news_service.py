"""
infra/news_service.py
=====================

NewsService provides news-awareness functionality for the trading bot.
It supports summarizing upcoming events, checking news blackout windows, and
finding the next event time.  Events are loaded from a JSON file whose path
is configured via `NEWS_EVENTS_PATH` in config/settings.py.

Each event record in the JSON file must have:
    - time: ISO timestamp (UTC) or epoch seconds
    - description: text describing the event
    - impact: "low", "medium", "high", "ultra", or "crypto"
    - category: "macro" or "crypto"
    - symbols: list of symbols (optional; use ["ALL"] to apply to all)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from config import settings


@dataclass
class NewsEvent:
    time: datetime  # UTC time
    description: str
    impact: str  # "low", "medium", "high", "ultra", "crypto"
    category: str  # "macro" or "crypto"
    symbols: List[str]
    # FMP fields (optional)
    actual: Optional[float] = None
    expected: Optional[float] = None
    previous: Optional[float] = None
    surprise_pct: Optional[float] = None
    source: Optional[str] = None


class NewsService:
    def __init__(self, events_path: Optional[str] = None):
        """
        Create a NewsService.  If events_path is not provided, it reads from
        settings.NEWS_EVENTS_PATH.  The events file should be JSON:
          [{"time": "2025-08-11T14:00:00Z", "description": "...", "impact": "high",
            "category": "macro", "symbols": ["USD"]}, ...]
        
        Also automatically loads breaking news from data/breaking_news_data.json
        and merges it with scheduled events.
        """
        self.events_path = events_path or getattr(settings, "NEWS_EVENTS_PATH", "")
        self.breaking_news_path = "data/breaking_news_data.json"
        self._events: List[NewsEvent] = []
        self._last_load_date: Optional[datetime.date] = None

    def _load_breaking_news(self) -> List[NewsEvent]:
        """
        Load breaking news from breaking_news_data.json and convert to NewsEvent format.
        Returns empty list if file doesn't exist or on error.
        """
        breaking_events = []
        if not os.path.isfile(self.breaking_news_path):
            return breaking_events
        
        try:
            with open(self.breaking_news_path, "r", encoding="utf-8") as f:
                breaking_news_raw = json.load(f)
                
            for news_item in breaking_news_raw:
                try:
                    # Parse timestamp (ISO format or current time if missing)
                    timestamp_str = news_item.get("timestamp") or news_item.get("scraped_at")
                    if timestamp_str:
                        if isinstance(timestamp_str, (int, float)):
                            dt = datetime.utcfromtimestamp(float(timestamp_str))
                        else:
                            dt = datetime.fromisoformat(str(timestamp_str).replace("Z", "+00:00"))
                            dt = dt.astimezone(tz=None).replace(tzinfo=None)
                    else:
                        # Use current time if no timestamp
                        dt = datetime.utcnow()
                    
                    # Get description from title
                    description = news_item.get("title", "Breaking News")
                    # Add link as part of description if available
                    link = news_item.get("link", "")
                    if link:
                        description = f"{description} ({link})"
                    
                    # Get impact and category
                    impact = str(news_item.get("impact", "high")).lower()
                    category = str(news_item.get("category", "macro")).lower()
                    # Map "general" to "macro" since NewsService only accepts "macro" or "crypto"
                    if category == "general" or category not in ("macro", "crypto"):
                        category = "macro"
                    
                    # Convert breaking news to NewsEvent
                    # Store original source name and mark as breaking news
                    original_source = news_item.get("source", "breaking_news")
                    ev = NewsEvent(
                        time=dt,
                        description=description,
                        impact=impact,
                        category=category,
                        symbols=["ALL"],  # Breaking news applies to all symbols
                        source=f"breaking_news:{original_source}",  # Mark as breaking news with source
                    )
                    breaking_events.append(ev)
                except Exception as e:
                    # Log but continue processing other items
                    continue
        except Exception:
            # File doesn't exist or invalid JSON - return empty list
            pass
        
        return breaking_events

    def _load_events_if_needed(self):
        """
        Lazy-load events from JSON if not loaded today.
        Also loads and merges breaking news data.
        """
        today = datetime.utcnow().date()
        if self._last_load_date == today:
            return
        self._events = []
        self._last_load_date = today
        
        # Load scheduled events from main events file
        path = self.events_path
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    for rec in raw:
                        try:
                            ts = rec.get("time")
                            if isinstance(ts, (int, float)):
                                dt = datetime.utcfromtimestamp(float(ts))
                            else:
                                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                                dt = dt.astimezone(tz=None).replace(tzinfo=None)
                            ev = NewsEvent(
                                time=dt,
                                description=str(rec.get("description", "")),
                                impact=str(rec.get("impact", "")).lower(),
                                category=str(rec.get("category", "macro")).lower(),
                                symbols=rec.get("symbols", []) or [],
                                # FMP fields
                                actual=rec.get("actual"),
                                expected=rec.get("expected"),
                                previous=rec.get("previous"),
                                surprise_pct=rec.get("surprise_pct"),
                                source=rec.get("source"),
                            )
                            self._events.append(ev)
                        except Exception:
                            continue
            except Exception:
                pass
        
        # Load and merge breaking news
        breaking_events = self._load_breaking_news()
        self._events.extend(breaking_events)
        
        # Sort events by time
        self._events.sort(key=lambda x: x.time)

    def summary_for_prompt(
        self,
        category: str,
        now: Optional[datetime] = None,
        hours_ahead: int = 12,
    ) -> str:
        """
        Return a brief summary of upcoming news events in the next hours_ahead for
        the given category ("macro" or "crypto").  Only high/ultra/crypto events
        are included.  Format: "18:00 CPI (ultra) | BREAKING: Fed Rate Cut (ultra)".
        Breaking news items are prefixed with "BREAKING: ".
        """
        self._load_events_if_needed()
        now = now or datetime.utcnow()
        horizon = now + timedelta(hours=hours_ahead)
        summary_events = []
        for ev in self._events:
            if ev.category != category:
                continue
            if ev.time < now or ev.time > horizon:
                continue
            impact = ev.impact.lower()
            if impact in {"high", "ultra", "crypto"}:
                time_str = ev.time.strftime("%H:%M")
                # Mark breaking news with source indicator
                is_breaking = ev.source and "breaking_news" in str(ev.source)
                prefix = "[BREAKING] " if is_breaking else ""
                description = ev.description[:60]  # Truncate long descriptions
                summary_events.append(f"{time_str} {prefix}{description} ({impact})")
        return " | ".join(summary_events)

    def is_blackout(self, category: str, now: Optional[datetime] = None) -> bool:
        """
        Determine if we are within a news blackout window for the given category.
        Returns True if there is a high/ultra/crypto event within the pre/post
        buffers (minutes before and after).  Buffers are defined in settings:
          NEWS_HIGH_IMPACT_BEFORE_MIN, NEWS_HIGH_IMPACT_AFTER_MIN,
          NEWS_ULTRA_HIGH_BEFORE_MIN, NEWS_ULTRA_HIGH_AFTER_MIN,
          NEWS_CRYPTO_BEFORE_MIN, NEWS_CRYPTO_AFTER_MIN.
        """
        self._load_events_if_needed()
        now = now or datetime.utcnow()
        before_high = int(getattr(settings, "NEWS_HIGH_IMPACT_BEFORE_MIN", 30))
        after_high = int(getattr(settings, "NEWS_HIGH_IMPACT_AFTER_MIN", 30))
        before_ultra = int(getattr(settings, "NEWS_ULTRA_HIGH_BEFORE_MIN", 60))
        after_ultra = int(getattr(settings, "NEWS_ULTRA_HIGH_AFTER_MIN", 90))
        before_crypto = int(getattr(settings, "NEWS_CRYPTO_BEFORE_MIN", 15))
        after_crypto = int(getattr(settings, "NEWS_CRYPTO_AFTER_MIN", 30))

        for ev in self._events:
            if ev.category != category:
                continue
            delta = (ev.time - now).total_seconds() / 60.0  # minutes
            impact = ev.impact.lower()
            if impact == "high":
                if -after_high <= delta <= before_high:
                    return True
            elif impact == "ultra":
                if -after_ultra <= delta <= before_ultra:
                    return True
            elif impact == "crypto":
                if -after_crypto <= delta <= before_crypto:
                    return True
        return False

    def next_event_time(
        self, category: str, now: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Return the next scheduled news event time for the given category, or None
        if no future events found.
        """
        self._load_events_if_needed()
        now = now or datetime.utcnow()
        future_events = [
            ev for ev in self._events if ev.category == category and ev.time > now
        ]
        if not future_events:
            return None
        return min(ev.time for ev in future_events)

    def summarise_events(
        self,
        category: str,
        now: Optional[datetime] = None,
        window_min: int = 30,
    ) -> List[dict]:
        """
        Return structured summaries of upcoming high-impact events within
        ±window_min minutes of now for the specified category.  Each
        summary is a dict with keys:

          - theme: a short label of the event (first few words of the description)
          - expected_vol: one of {"low","medium","high","ultra","crypto"}
          - surprise_bias: placeholder for actual surprise direction (LLM to fill)
          - side_risk: placeholder describing directional risk on instruments

        Events outside the window or with low impact are ignored.
        """
        self._load_events_if_needed()
        now = now or datetime.utcnow()
        summaries: List[dict] = []
        for ev in self._events:
            if ev.category != category:
                continue
            impact = ev.impact.lower()
            if impact not in {"high", "ultra", "crypto"}:
                continue
            delta_min = (ev.time - now).total_seconds() / 60.0
            if abs(delta_min) > window_min:
                continue
            desc = ev.description.strip()
            theme = " ".join(desc.split()[:5])
            summaries.append(
                {
                    "theme": theme,
                    "expected_vol": impact,
                    "surprise_bias": None,
                    "side_risk": None,
                }
            )
        return summaries
    
    def get_events_with_actual_data(
        self,
        category: str,
        now: Optional[datetime] = None,
        hours_ahead: int = 24,
    ) -> List[NewsEvent]:
        """
        Return events that have actual data (from FMP) within the specified time window.
        These are events that have already occurred and have actual vs expected data.
        Useful for news trading analysis.
        """
        self._load_events_if_needed()
        now = now or datetime.utcnow()
        horizon = now + timedelta(hours=hours_ahead)
        
        events_with_data = []
        for ev in self._events:
            if ev.category != category:
                continue
            if ev.time < now or ev.time > horizon:
                continue
            if ev.actual is not None and ev.expected is not None:
                events_with_data.append(ev)
        
        return events_with_data
    
    def get_surprise_events(
        self,
        category: str,
        min_surprise_pct: float = 10.0,
        now: Optional[datetime] = None,
        hours_ahead: int = 24,
    ) -> List[NewsEvent]:
        """
        Return events with significant surprise (actual vs expected deviation).
        Useful for identifying high-impact news that moved markets.
        """
        events_with_data = self.get_events_with_actual_data(category, now, hours_ahead)
        
        surprise_events = []
        for ev in events_with_data:
            if ev.surprise_pct is not None and abs(ev.surprise_pct) >= min_surprise_pct:
                surprise_events.append(ev)
        
        return surprise_events
    
    def get_upcoming_events(
        self,
        limit: int = 10,
        hours_ahead: int = 24,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming events as dictionaries for easy consumption.
        
        Args:
            limit: Maximum number of events to return
            hours_ahead: Hours ahead to look for events
            category: Filter by category ("macro" or "crypto"), or None for all
        
        Returns:
            List of event dictionaries with keys: time, event, impact, description, category
        """
        self._load_events_if_needed()
        now = datetime.utcnow()
        horizon = now + timedelta(hours=hours_ahead)
        
        upcoming = []
        for ev in self._events:
            # Filter by category if specified
            if category and ev.category != category:
                continue
            
            # Only future events
            if ev.time < now or ev.time > horizon:
                continue
            
            # Convert to dict format
            event_dict = {
                "time": ev.time.isoformat() + "Z" if ev.time.tzinfo is None else ev.time.isoformat(),
                "event": ev.description[:50],  # Truncate for brevity
                "impact": ev.impact.upper(),
                "description": ev.description,
                "category": ev.category
            }
            upcoming.append(event_dict)
        
        # Sort by time and limit
        upcoming.sort(key=lambda x: x["time"])
        return upcoming[:limit]


def get_news_service():
    """Get a NewsService instance"""
    return NewsService()
    
