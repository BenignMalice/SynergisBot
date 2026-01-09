"""
Convert today's news events from news_events.json to CSV format for MT5 Guardian News Bot.

This script:
1. Reads news_events.json
2. Filters for today's events only
3. Converts to CSV format with columns: event_time_utc, impact, currencies, event_name
4. Saves to MT5 Common Files directory (guardian_news.csv)
"""

import json
import os
import csv
from datetime import datetime, timezone
from pathlib import Path


def get_today_utc():
    """Get today's date in UTC"""
    return datetime.now(timezone.utc).date()


def load_news_events(json_path: str):
    """Load news events from JSON file"""
    if not os.path.exists(json_path):
        print(f"Warning: {json_path} not found")
        return []
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Handle both array format and object format
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'events' in data:
                return data.get('events', [])
            else:
                return []
    except Exception as e:
        print(f"Error loading news events: {e}")
        return []


def filter_today_events(events):
    """Filter events to only include today's events (UTC)"""
    today = get_today_utc()
    today_events = []
    
    for event in events:
        try:
            # Parse the time field (ISO format: "2025-12-05T13:30:00Z")
            event_time_str = event.get('time', '')
            if not event_time_str:
                continue
            
            # Remove 'Z' if present and parse
            if event_time_str.endswith('Z'):
                event_time_str = event_time_str[:-1]
            
            event_dt = datetime.fromisoformat(event_time_str)
            # Ensure it's UTC
            if event_dt.tzinfo is None:
                event_dt = event_dt.replace(tzinfo=timezone.utc)
            else:
                event_dt = event_dt.astimezone(timezone.utc)
            
            # Check if event is today
            if event_dt.date() == today:
                today_events.append(event)
        except Exception as e:
            print(f"Warning: Skipping event due to parse error: {e}")
            continue
    
    return today_events


def normalize_impact(impact: str) -> str:
    """
    Normalize impact level to one of: low, medium, high, ultra
    Maps 'crypto' to 'high'
    """
    impact_lower = impact.lower().strip()
    
    if impact_lower in ['low', 'medium', 'high', 'ultra']:
        return impact_lower
    elif impact_lower == 'crypto':
        return 'high'  # Map crypto to high
    else:
        # Default to low if unknown
        return 'low'


def format_currencies(symbols):
    """
    Format symbols array to comma-separated string
    Handles 'ALL' case
    """
    if not symbols:
        return ""
    
    # Filter out empty strings and join
    filtered = [s.strip() for s in symbols if s and s.strip()]
    
    if not filtered:
        return ""
    
    # If 'ALL' is in the list, keep it as is
    if 'ALL' in filtered:
        return 'ALL'
    
    # Otherwise, return comma-separated list
    return ','.join(filtered)


def convert_to_csv_row(event):
    """Convert a single event to CSV row format"""
    # event_time_utc: ISO format with Z suffix
    event_time_str = event.get('time', '')
    if event_time_str and not event_time_str.endswith('Z'):
        # Ensure Z suffix for UTC
        if event_time_str.endswith('+00:00'):
            event_time_str = event_time_str.replace('+00:00', 'Z')
        elif '+' in event_time_str or event_time_str.count('-') > 2:
            # Has timezone, convert to Z
            try:
                dt = datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
                event_time_str = dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            except:
                pass
        else:
            event_time_str = event_time_str + 'Z'
    
    # impact: normalize to low/medium/high/ultra
    impact = normalize_impact(event.get('impact', 'low'))
    
    # currencies: comma-separated from symbols array
    currencies = format_currencies(event.get('symbols', []))
    
    # event_name: description field
    event_name = event.get('description', '').strip()
    
    return {
        'event_time_utc': event_time_str,
        'impact': impact,
        'currencies': currencies,
        'event_name': event_name
    }


def save_csv(events, csv_path: str):
    """Save events to CSV file"""
    # Ensure directory exists
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    
    # Convert events to CSV rows
    rows = []
    for event in events:
        row = convert_to_csv_row(event)
        rows.append(row)
    
    # Sort by event_time_utc
    rows.sort(key=lambda x: x['event_time_utc'])
    
    # Write CSV
    try:
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['event_time_utc', 'impact', 'currencies', 'event_name'])
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"Saved {len(rows)} today's events to {csv_path}")
        return True
    except Exception as e:
        print(f"Error saving CSV: {e}")
        return False


def convert_news_to_csv(json_path: str = None, csv_path: str = None):
    """
    Main function to convert today's news events to CSV
    
    Args:
        json_path: Path to news_events.json (default: data/news_events.json)
        csv_path: Path to output CSV (default: MT5 Common Files/guardian_news.csv)
    """
    # Default paths
    if json_path is None:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(BASE_DIR, "data", "news_events.json")
    
    if csv_path is None:
        # MT5 Common Files directory
        mt5_common_files = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "Common" / "Files"
        csv_path = str(mt5_common_files / "guardian_news.csv")
    
    # Load events
    all_events = load_news_events(json_path)
    if not all_events:
        print(f"Warning: No events found in {json_path}")
        return False
    
    # Filter for today
    today_events = filter_today_events(all_events)
    if not today_events:
        print(f"No events found for today ({get_today_utc()})")
        # Still create empty CSV with header
        save_csv([], csv_path)
        return True
    
    print(f"Found {len(today_events)} events for today ({get_today_utc()})")
    
    # Save to CSV
    return save_csv(today_events, csv_path)


if __name__ == "__main__":
    convert_news_to_csv()

