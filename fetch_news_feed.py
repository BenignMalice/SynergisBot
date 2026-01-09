# fetch_news_feed.py
"""
Fetch and parse a free economic calendar feed and save as news_events.json.

This example uses the Forex Factory weekly feed.  Adjust `FEED_URL` to point
to another feed (e.g. Financial Modeling Prep’s economic calendar API) if
Forex Factory is inaccessible in your environment.
"""

import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Adjust to match your environment.  If needed, prepend "view-source:".
FEED_URL = "http://nfs.faireconomy.media/ff_calendar_thisweek.xml"
# Save into the root-level data folder (relative to this script)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEWS_EVENTS_JSON = os.path.join(BASE_DIR, "data", "news_events.json")


# Keyword heuristics to promote certain high impact events to ultra
ULTRA_KEYWORDS = ["nfp", "non-farm", "non farm", "cpi", "core cpi", "rate decision"]


def fetch_feed(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},  # helps bypass 403 on some sites
    )
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode("utf-8", errors="ignore")
    return content


def parse_events(xml_text: str):
    root = ET.fromstring(xml_text)
    events = []
    for event_elem in root.findall(".//event"):
        title = event_elem.findtext("title") or ""
        country = (event_elem.findtext("country") or "").strip().upper()
        date_str = (event_elem.findtext("date") or "").strip()
        time_str = (event_elem.findtext("time") or "").strip()
        impact = (event_elem.findtext("impact") or "").strip().lower()

        # Some feeds include "PM/AM", remove extra whitespace
        time_str = re.sub(r"\s+", " ", time_str)
        date_str = date_str.replace("\u00a0", " ")  # non-breaking spaces

        # Skip holidays or bank holidays
        if impact == "holiday":
            continue

        # Parse date & time to UTC
        try:
            local_dt = datetime.strptime(
                f"{date_str} {time_str}", "%m-%d-%Y %I:%M%p"
            )  # e.g. 08-12-2025 4:30am
            event_time = local_dt  # Forex Factory times are typically UTC
        except Exception:
            # If parsing fails, skip event
            continue

        # Map impact level; promote to ultra if keywords match
        impact_level = (
            "high"
            if impact.startswith("high")
            else ("medium" if impact.startswith("medium") else "low")
        )
        if impact_level == "high":
            if any(kw in title.lower() for kw in ULTRA_KEYWORDS):
                impact_level = "ultra"

        # Build symbols list: derive from country code or default to ALL
        # For example, "USD" events apply to XAUUSD, BTCUSD etc.
        symbols = ["ALL"]
        if country and len(country) == 3:
            # map common currency codes (JPY->USDJPY, etc.) if desired
            symbols = [country]
        
        # Detect crypto-related events by keywords in title
        crypto_keywords = [
            "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain",
            "binance", "coinbase", "sec crypto", "etf", "defi", "nft",
            "altcoin", "stablecoin", "usdt", "usdc", "tether"
        ]
        title_lower = title.lower()
        is_crypto = any(keyword in title_lower for keyword in crypto_keywords)
        
        # Determine category
        category = "crypto" if is_crypto else "macro"
        
        # For crypto events, promote to "crypto" impact level if high
        if is_crypto and impact_level == "high":
            impact_level = "crypto"

        events.append(
            {
                "time": event_time.isoformat() + "Z",
                "description": title,
                "impact": impact_level,
                "category": category,
                "symbols": symbols,
            }
        )

    return sorted(events, key=lambda x: x["time"])


def save_events(events, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)
    print(f"Saved {len(events)} events to {path}")
    
    # Convert today's events to CSV for MT5 Guardian News Bot
    try:
        from convert_news_to_csv import convert_news_to_csv
        convert_news_to_csv(json_path=path)
    except Exception as e:
        print(f"Warning: Failed to convert to CSV: {e}")


def main():
    try:
        xml_text = fetch_feed(FEED_URL)
    except Exception as e:
        print(f"Error fetching feed: {e}")
        return
    events = parse_events(xml_text)
    save_events(events, NEWS_EVENTS_JSON)


if __name__ == "__main__":
    main()
