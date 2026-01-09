#!/usr/bin/env python3
"""
News Sentiment Integration
Enhances existing Forex Factory data with sentiment analysis
"""

import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NewsSentimentEnhancer:
    def __init__(self):
        self.data_dir = "data"
        self.news_file = os.path.join(self.data_dir, "news_events.json")
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
    
    def load_existing_events(self):
        """Load existing events from Forex Factory"""
        if os.path.exists(self.news_file):
            try:
                with open(self.news_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Handle both array format and object format
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and 'events' in data:
                        return data.get('events', [])
                    else:
                        return []
            except Exception as e:
                logger.warning(f"Error loading existing events: {e}")
        return []
    
    def enhance_with_sentiment(self, events):
        """Add sentiment analysis to existing events"""
        enhanced_events = []
        
        for event in events:
            try:
                # Create enhanced event with sentiment fields
                enhanced_event = event.copy()
                
                # Add sentiment analysis fields
                enhanced_event.update({
                    'sentiment': self._analyze_event_sentiment(event),
                    'trading_implication': self._get_trading_implication(event),
                    'risk_level': self._assess_risk_level(event),
                    'enhanced_at': datetime.now().isoformat()
                })
                
                enhanced_events.append(enhanced_event)
                
            except Exception as e:
                logger.warning(f"Error enhancing event {event.get('description', 'Unknown')}: {e}")
                enhanced_events.append(event)  # Keep original if enhancement fails
        
        return enhanced_events
    
    def _analyze_event_sentiment(self, event):
        """Analyze sentiment based on event characteristics"""
        description = event.get('description', '').lower()
        impact = event.get('impact', '').lower()
        
        # Bullish keywords
        bullish_keywords = [
            'employment', 'payrolls', 'jobs', 'unemployment', 'gdp', 'growth',
            'manufacturing', 'retail', 'consumer', 'confidence', 'inflation',
            'rate hike', 'hawkish', 'strong', 'positive', 'increase'
        ]
        
        # Bearish keywords  
        bearish_keywords = [
            'unemployment', 'recession', 'decline', 'weak', 'negative',
            'rate cut', 'dovish', 'decrease', 'contraction', 'crisis'
        ]
        
        # Count sentiment indicators
        bullish_count = sum(1 for keyword in bullish_keywords if keyword in description)
        bearish_count = sum(1 for keyword in bearish_keywords if keyword in description)
        
        # Determine sentiment
        if bullish_count > bearish_count:
            return 'BULLISH'
        elif bearish_count > bullish_count:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def _get_trading_implication(self, event):
        """Get trading implication based on event type"""
        description = event.get('description', '').lower()
        impact = event.get('impact', '').lower()
        
        # High impact events
        if impact == 'high':
            if 'payrolls' in description or 'employment' in description:
                return 'Major USD volatility expected - watch for trend continuation'
            elif 'inflation' in description or 'cpi' in description:
                return 'Inflation data will drive Fed policy expectations'
            elif 'fomc' in description or 'fed' in description:
                return 'Central bank policy decision - expect significant moves'
            else:
                return 'High impact event - prepare for volatility'
        
        # Medium impact events
        elif impact == 'medium':
            return 'Moderate volatility expected - monitor for breakouts'
        
        # Low impact events
        else:
            return 'Low impact - minimal market movement expected'
    
    def _assess_risk_level(self, event):
        """Assess risk level based on event characteristics"""
        impact = event.get('impact', '').lower()
        description = event.get('description', '').lower()
        
        # Ultra high risk events
        if impact == 'ultra' or 'fomc' in description or 'fed' in description:
            return 'ULTRA_HIGH'
        
        # High risk events
        elif impact == 'high' or 'payrolls' in description or 'cpi' in description:
            return 'HIGH'
        
        # Medium risk events
        elif impact == 'medium':
            return 'MEDIUM'
        
        # Low risk events
        else:
            return 'LOW'
    
    def save_enhanced_events(self, events):
        """Save enhanced events to JSON file"""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'total_events': len(events),
                'enhanced_with_sentiment': True,
                'events': events
            }
            
            with open(self.news_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(events)} enhanced events to {self.news_file}")
            
            # Convert today's events to CSV for MT5 Guardian News Bot
            try:
                from convert_news_to_csv import convert_news_to_csv
                convert_news_to_csv(json_path=self.news_file)
            except Exception as e:
                logger.warning(f"Failed to convert to CSV: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving enhanced events: {e}")
            return False
    
    def run(self):
        """Main execution function"""
        logger.info("Starting news sentiment enhancement...")
        
        # Load existing events
        existing_events = self.load_existing_events()
        if not existing_events:
            logger.warning("No existing events found")
            return False
        
        logger.info(f"Loaded {len(existing_events)} existing events")
        
        # Enhance with sentiment analysis
        enhanced_events = self.enhance_with_sentiment(existing_events)
        logger.info(f"Enhanced {len(enhanced_events)} events with sentiment analysis")
        
        # Save enhanced events
        if self.save_enhanced_events(enhanced_events):
            logger.info("SUCCESS: News sentiment enhancement completed!")
            return True
        else:
            logger.error("ERROR: Failed to save enhanced events")
            return False

def main():
    """Main function"""
    try:
        enhancer = NewsSentimentEnhancer()
        success = enhancer.run()
        
        if success:
            print("SUCCESS: News sentiment enhancement completed!")
            print("Check data/news_events.json for enhanced events with sentiment analysis")
        else:
            print("ERROR: News sentiment enhancement failed")
            return 1
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"ERROR: Fatal error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
