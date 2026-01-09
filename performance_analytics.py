#!/usr/bin/env python3
"""
Performance Analytics
====================

This module provides analytics on the performance of all three priorities.
"""

import json
import sqlite3
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PerformanceAnalytics:
    """Performance analytics for all three priorities"""
    
    def __init__(self):
        self.priority1_file = 'data/clean_scraped_economic_data.json'
        self.priority2_file = 'data/clean_breaking_news_data.json'
        self.priority3_db = 'data/clean_historical_database.sqlite'
    
    def analyze_priority1_performance(self):
        """Analyze Priority 1 performance"""
        try:
            with open(self.priority1_file, 'r') as f:
                data = json.load(f)
            
            analysis = {
                'total_events': len(data),
                'events_with_actual': sum(1 for e in data if e.get('actual')),
                'events_with_forecast': sum(1 for e in data if e.get('forecast')),
                'events_with_surprise': sum(1 for e in data if e.get('surprise_pct') is not None),
                'avg_surprise': sum(e.get('surprise_pct', 0) for e in data) / len(data) if data else 0,
                'max_surprise': max((e.get('surprise_pct', 0) for e in data), default=0),
                'min_surprise': min((e.get('surprise_pct', 0) for e in data), default=0)
            }
            
            logger.info(f"Priority 1 Analysis: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing Priority 1: {e}")
            return {}
    
    def analyze_priority2_performance(self):
        """Analyze Priority 2 performance"""
        try:
            with open(self.priority2_file, 'r') as f:
                data = json.load(f)
            
            analysis = {
                'total_news': len(data),
                'ultra_impact': sum(1 for n in data if n.get('impact') == 'ultra'),
                'high_impact': sum(1 for n in data if n.get('impact') == 'high'),
                'medium_impact': sum(1 for n in data if n.get('impact') == 'medium'),
                'crypto_news': sum(1 for n in data if n.get('category') == 'crypto'),
                'macro_news': sum(1 for n in data if n.get('category') == 'macro'),
                'geopolitical_news': sum(1 for n in data if n.get('category') == 'geopolitical'),
                'general_news': sum(1 for n in data if n.get('category') == 'general')
            }
            
            logger.info(f"Priority 2 Analysis: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing Priority 2: {e}")
            return {}
    
    def analyze_priority3_performance(self):
        """Analyze Priority 3 performance"""
        try:
            conn = sqlite3.connect(self.priority3_db)
            cursor = conn.cursor()
            
            # Get basic stats
            cursor.execute('SELECT COUNT(*) FROM historical_data')
            total_records = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT symbol) FROM historical_data')
            unique_symbols = cursor.fetchone()[0]
            
            # Get records by asset type
            cursor.execute('SELECT asset_type, COUNT(*) FROM historical_data GROUP BY asset_type')
            asset_counts = dict(cursor.fetchall())
            
            # Get date range
            cursor.execute('SELECT MIN(date), MAX(date) FROM historical_data')
            date_range = cursor.fetchone()
            
            conn.close()
            
            analysis = {
                'total_records': total_records,
                'unique_symbols': unique_symbols,
                'asset_types': asset_counts,
                'date_range': date_range
            }
            
            logger.info(f"Priority 3 Analysis: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing Priority 3: {e}")
            return {}
    
    def get_comprehensive_analysis(self):
        """Get comprehensive analysis of all priorities"""
        p1_analysis = self.analyze_priority1_performance()
        p2_analysis = self.analyze_priority2_performance()
        p3_analysis = self.analyze_priority3_performance()
        
        comprehensive = {
            'timestamp': datetime.now().isoformat(),
            'priority1': p1_analysis,
            'priority2': p2_analysis,
            'priority3': p3_analysis,
            'summary': {
                'total_data_points': p1_analysis.get('total_events', 0) + 
                                   p2_analysis.get('total_news', 0) + 
                                   p3_analysis.get('total_records', 0),
                'system_health': 'HEALTHY' if all([p1_analysis, p2_analysis, p3_analysis]) else 'ISSUES'
            }
        }
        
        logger.info("Comprehensive Analysis:")
        logger.info(f"  Total Data Points: {comprehensive['summary']['total_data_points']}")
        logger.info(f"  System Health: {comprehensive['summary']['system_health']}")
        
        return comprehensive
    
    def save_analysis(self, analysis, filename=None):
        """Save analysis to file"""
        try:
            if not filename:
                filename = f"data/performance_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(filename, 'w') as f:
                json.dump(analysis, f, indent=2)
            
            logger.info(f"Saved analysis to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error saving analysis: {e}")
            return None

def main():
    """Main function to test performance analytics"""
    logger.info("Testing performance analytics...")
    
    analytics = PerformanceAnalytics()
    analysis = analytics.get_comprehensive_analysis()
    
    if analysis:
        # Save analysis
        filename = analytics.save_analysis(analysis)
        if filename:
            logger.info(f"SUCCESS: Analysis saved to {filename}")
    
    logger.info("Performance Analytics Complete")

if __name__ == "__main__":
    main()
