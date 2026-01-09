#!/usr/bin/env python3
"""
Real-time Alerts System
=======================

This system monitors all three priorities for high-impact events and sends alerts.
"""

import json
import time
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RealTimeAlerts:
    """Real-time alerts system for high-impact events"""
    
    def __init__(self):
        self.alert_thresholds = {
            'ultra_impact': True,
            'high_impact': True,
            'surprise_threshold': 10.0,  # 10% surprise
            'crypto_news': True,
            'macro_news': True
        }
    
    def check_breaking_news_alerts(self):
        """Check for breaking news alerts"""
        try:
            with open('data/clean_breaking_news_data.json', 'r') as f:
                news_data = json.load(f)
            
            alerts = []
            for news in news_data:
                if news.get('impact') in ['ultra', 'high']:
                    alerts.append({
                        'type': 'breaking_news',
                        'title': news.get('title'),
                        'impact': news.get('impact'),
                        'category': news.get('category'),
                        'timestamp': news.get('scraped_at')
                    })
            
            if alerts:
                logger.info(f"Found {len(alerts)} breaking news alerts")
                return alerts
            else:
                logger.info("No breaking news alerts found")
                return []
                
        except Exception as e:
            logger.error(f"Error checking breaking news alerts: {e}")
            return []
    
    def check_economic_surprise_alerts(self):
        """Check for economic surprise alerts"""
        try:
            with open('data/clean_scraped_economic_data.json', 'r') as f:
                economic_data = json.load(f)
            
            alerts = []
            for event in economic_data:
                surprise_pct = event.get('surprise_pct', 0)
                if abs(surprise_pct) >= self.alert_thresholds['surprise_threshold']:
                    alerts.append({
                        'type': 'economic_surprise',
                        'event': event.get('event'),
                        'surprise_pct': surprise_pct,
                        'actual': event.get('actual'),
                        'forecast': event.get('forecast'),
                        'timestamp': event.get('scraped_at')
                    })
            
            if alerts:
                logger.info(f"Found {len(alerts)} economic surprise alerts")
                return alerts
            else:
                logger.info("No economic surprise alerts found")
                return []
                
        except Exception as e:
            logger.error(f"Error checking economic surprise alerts: {e}")
            return []
    
    def check_crypto_news_alerts(self):
        """Check for crypto-specific news alerts"""
        try:
            with open('data/clean_breaking_news_data.json', 'r') as f:
                news_data = json.load(f)
            
            alerts = []
            for news in news_data:
                if news.get('category') == 'crypto':
                    alerts.append({
                        'type': 'crypto_news',
                        'title': news.get('title'),
                        'impact': news.get('impact'),
                        'timestamp': news.get('scraped_at')
                    })
            
            if alerts:
                logger.info(f"Found {len(alerts)} crypto news alerts")
                return alerts
            else:
                logger.info("No crypto news alerts found")
                return []
                
        except Exception as e:
            logger.error(f"Error checking crypto news alerts: {e}")
            return []
    
    def get_all_alerts(self):
        """Get all active alerts"""
        breaking_news_alerts = self.check_breaking_news_alerts()
        economic_surprise_alerts = self.check_economic_surprise_alerts()
        crypto_news_alerts = self.check_crypto_news_alerts()
        
        all_alerts = breaking_news_alerts + economic_surprise_alerts + crypto_news_alerts
        
        if all_alerts:
            logger.info(f"Total active alerts: {len(all_alerts)}")
            return all_alerts
        else:
            logger.info("No active alerts")
            return []
    
    def save_alerts(self, alerts, filename=None):
        """Save alerts to file"""
        try:
            if not filename:
                filename = f"data/alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(filename, 'w') as f:
                json.dump(alerts, f, indent=2)
            
            logger.info(f"Saved alerts to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error saving alerts: {e}")
            return None

def main():
    """Main function to test real-time alerts"""
    logger.info("Testing real-time alerts system...")
    
    alerts_system = RealTimeAlerts()
    alerts = alerts_system.get_all_alerts()
    
    if alerts:
        logger.info("Active Alerts:")
        for i, alert in enumerate(alerts, 1):
            logger.info(f"  {i}. {alert['type']}: {alert.get('title', alert.get('event'))}")
        
        # Save alerts
        filename = alerts_system.save_alerts(alerts)
        if filename:
            logger.info(f"SUCCESS: Alerts saved to {filename}")
    else:
        logger.info("No active alerts")

if __name__ == "__main__":
    main()
