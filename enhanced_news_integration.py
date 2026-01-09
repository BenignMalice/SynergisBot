#!/usr/bin/env python3
"""
Enhanced News Integration
========================

This module integrates all three priorities with the existing news system.
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedNewsIntegration:
    """Enhanced news integration combining all three priorities"""
    
    def __init__(self):
        self.priority1_file = 'data/clean_scraped_economic_data.json'
        self.priority2_file = 'data/clean_breaking_news_data.json'
        self.priority3_db = 'data/clean_historical_database.sqlite'
    
    def load_priority1_data(self):
        """Load actual/expected data from Priority 1"""
        try:
            with open(self.priority1_file, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} economic events from Priority 1")
            return data
        except FileNotFoundError:
            logger.warning("Priority 1 data file not found")
            return []
    
    def load_priority2_data(self):
        """Load breaking news data from Priority 2"""
        try:
            with open(self.priority2_file, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} breaking news items from Priority 2")
            return data
        except FileNotFoundError:
            logger.warning("Priority 2 data file not found")
            return []
    
    def load_priority3_data(self, symbol: str = None, days: int = 30):
        """Load historical data from Priority 3"""
        try:
            conn = sqlite3.connect(self.priority3_db)
            cursor = conn.cursor()
            
            if symbol:
                cursor.execute('''
                    SELECT * FROM historical_data 
                    WHERE symbol = ? 
                    ORDER BY date DESC 
                    LIMIT ?
                ''', (symbol, days))
            else:
                cursor.execute('''
                    SELECT * FROM historical_data 
                    ORDER BY date DESC 
                    LIMIT ?
                ''', (days,))
            
            data = cursor.fetchall()
            conn.close()
            
            logger.info(f"Loaded {len(data)} historical records from Priority 3")
            return data
        except Exception as e:
            logger.error(f"Error loading Priority 3 data: {e}")
            return []
    
    def get_unified_analysis(self, symbol: str = None):
        """Get unified analysis combining all three priorities"""
        try:
            # Load data from all priorities
            economic_events = self.load_priority1_data()
            breaking_news = self.load_priority2_data()
            historical_data = self.load_priority3_data(symbol)
            
            # Create unified analysis
            unified_analysis = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'economic_events': economic_events,
                'breaking_news': breaking_news,
                'historical_data': historical_data,
                'summary': {
                    'total_economic_events': len(economic_events),
                    'total_breaking_news': len(breaking_news),
                    'total_historical_records': len(historical_data),
                    'ultra_impact_news': sum(1 for n in breaking_news if n.get('impact') == 'ultra'),
                    'high_impact_news': sum(1 for n in breaking_news if n.get('impact') == 'high'),
                    'crypto_news': sum(1 for n in breaking_news if n.get('category') == 'crypto'),
                    'macro_news': sum(1 for n in breaking_news if n.get('category') == 'macro')
                }
            }
            
            logger.info("Created unified analysis combining all three priorities")
            return unified_analysis
            
        except Exception as e:
            logger.error(f"Error creating unified analysis: {e}")
            return None
    
    def save_unified_analysis(self, analysis: Dict, filename: str = None):
        """Save unified analysis to file"""
        try:
            if not filename:
                filename = f"data/unified_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(filename, 'w') as f:
                json.dump(analysis, f, indent=2)
            
            logger.info(f"Saved unified analysis to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error saving unified analysis: {e}")
            return None

def main():
    """Main function to test enhanced news integration"""
    logger.info("Testing enhanced news integration...")
    
    # Initialize integration
    integration = EnhancedNewsIntegration()
    
    # Test unified analysis
    analysis = integration.get_unified_analysis('BTC')
    
    if analysis:
        logger.info("Unified Analysis Summary:")
        logger.info(f"  Economic Events: {analysis['summary']['total_economic_events']}")
        logger.info(f"  Breaking News: {analysis['summary']['total_breaking_news']}")
        logger.info(f"  Historical Records: {analysis['summary']['total_historical_records']}")
        logger.info(f"  Ultra Impact News: {analysis['summary']['ultra_impact_news']}")
        logger.info(f"  High Impact News: {analysis['summary']['high_impact_news']}")
        logger.info(f"  Crypto News: {analysis['summary']['crypto_news']}")
        logger.info(f"  Macro News: {analysis['summary']['macro_news']}")
        
        # Save unified analysis
        filename = integration.save_unified_analysis(analysis)
        if filename:
            logger.info(f"SUCCESS: Unified analysis saved to {filename}")
    else:
        logger.error("Failed to create unified analysis")

if __name__ == "__main__":
    main()
