#!/usr/bin/env python3
"""
News Sentiment Analyzer using OpenAI GPT-4
Analyzes news events and provides trading sentiment analysis
"""

import os
import json
import openai
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NewsSentimentAnalyzer:
    def __init__(self):
        """Initialize the sentiment analyzer with OpenAI API key"""
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        openai.api_key = self.api_key
        self.client = openai.OpenAI(api_key=self.api_key)
        
        # News trading context for GPT-4
        self.system_prompt = """You are a professional forex news trading analyst. Your job is to analyze economic news events and determine their trading implications.

For each news event, provide:
1. **Sentiment Direction**: BULLISH, BEARISH, or NEUTRAL
2. **Confidence Level**: 1-10 (10 = very confident)
3. **Trading Implication**: Brief explanation of market impact
4. **Key Currency Pairs**: Which pairs will be most affected
5. **Risk Level**: LOW, MEDIUM, HIGH

Focus on:
- Actual vs Expected surprise magnitude
- Historical market reactions to similar events
- Currency-specific implications
- Volatility expectations

Be concise but comprehensive. Prioritize actionable insights for forex traders."""

    def analyze_single_event(self, event: Dict) -> Dict:
        """
        Analyze a single news event and return sentiment analysis
        """
        try:
            # Prepare event data for analysis
            event_data = {
                'description': event.get('description', ''),
                'actual': event.get('actual'),
                'expected': event.get('expected'),
                'previous': event.get('previous'),
                'surprise_pct': event.get('surprise_pct', 0),
                'impact': event.get('impact', ''),
                'symbols': event.get('symbols', []),
                'time': event.get('time', ''),
                'source': event.get('source', '')
            }
            
            # Create analysis prompt
            prompt = self._create_analysis_prompt(event_data)
            
            # Call OpenAI GPT-4
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            # Parse response
            analysis_text = response.choices[0].message.content
            parsed_analysis = self._parse_analysis_response(analysis_text)
            
            # Add metadata
            parsed_analysis.update({
                'analyzed_at': datetime.now().isoformat(),
                'event_id': f"{event.get('time', '')}_{event.get('description', '')}",
                'raw_analysis': analysis_text
            })
            
            return parsed_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing event {event.get('description', 'Unknown')}: {e}")
            return {
                'sentiment': 'NEUTRAL',
                'confidence': 1,
                'trading_implication': 'Analysis failed',
                'key_pairs': [],
                'risk_level': 'HIGH',
                'error': str(e)
            }
    
    def _create_analysis_prompt(self, event_data: Dict) -> str:
        """Create a structured prompt for GPT-4 analysis"""
        
        prompt = f"""
**NEWS EVENT ANALYSIS REQUEST**

**Event Details:**
- Description: {event_data['description']}
- Impact Level: {event_data['impact'].upper()}
- Time: {event_data['time']}
- Source: {event_data['source']}

**Economic Data:**
- Actual: {event_data['actual']}
- Expected: {event_data['expected']}
- Previous: {event_data['previous']}
- Surprise %: {event_data['surprise_pct']}%

**Affected Currencies:** {', '.join(event_data['symbols'])}

**ANALYSIS REQUIRED:**
Please analyze this news event and provide:

1. **Sentiment Direction**: BULLISH, BEARISH, or NEUTRAL
2. **Confidence Level**: 1-10
3. **Trading Implication**: What this means for forex markets
4. **Key Currency Pairs**: Which pairs will be most affected (e.g., EURUSD, GBPUSD)
5. **Risk Level**: LOW, MEDIUM, HIGH

Focus on the surprise magnitude and its implications for currency strength/weakness.
"""
        return prompt
    
    def _parse_analysis_response(self, response_text: str) -> Dict:
        """Parse GPT-4 response into structured data"""
        
        # Default values
        analysis = {
            'sentiment': 'NEUTRAL',
            'confidence': 5,
            'trading_implication': 'No clear direction',
            'key_pairs': [],
            'risk_level': 'MEDIUM'
        }
        
        try:
            lines = response_text.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # Extract sentiment
                if 'sentiment' in line.lower() or 'direction' in line.lower():
                    if 'bullish' in line.lower():
                        analysis['sentiment'] = 'BULLISH'
                    elif 'bearish' in line.lower():
                        analysis['sentiment'] = 'BEARISH'
                    elif 'neutral' in line.lower():
                        analysis['sentiment'] = 'NEUTRAL'
                
                # Extract confidence
                if 'confidence' in line.lower():
                    try:
                        # Look for numbers in the line
                        import re
                        numbers = re.findall(r'\d+', line)
                        if numbers:
                            analysis['confidence'] = min(int(numbers[0]), 10)
                    except:
                        pass
                
                # Extract risk level
                if 'risk' in line.lower():
                    if 'high' in line.lower():
                        analysis['risk_level'] = 'HIGH'
                    elif 'low' in line.lower():
                        analysis['risk_level'] = 'LOW'
                    elif 'medium' in line.lower():
                        analysis['risk_level'] = 'MEDIUM'
                
                # Extract key pairs
                if 'pairs' in line.lower() or 'currency' in line.lower():
                    # Look for currency pairs like EURUSD, GBPUSD, etc.
                    import re
                    pairs = re.findall(r'[A-Z]{6}', line)
                    if pairs:
                        analysis['key_pairs'] = pairs[:3]  # Limit to 3 pairs
            
            # Extract trading implication (usually the longest meaningful line)
            implication_lines = [line for line in lines if len(line) > 20 and 'implication' in line.lower()]
            if implication_lines:
                analysis['trading_implication'] = implication_lines[0]
            
        except Exception as e:
            logger.warning(f"Error parsing analysis response: {e}")
        
        return analysis
    
    def analyze_multiple_events(self, events: List[Dict]) -> List[Dict]:
        """Analyze multiple events and return list of analyses"""
        analyses = []
        
        for event in events:
            try:
                analysis = self.analyze_single_event(event)
                analyses.append(analysis)
                
                # Add small delay to avoid rate limiting
                import time
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error in batch analysis: {e}")
                continue
        
        return analyses
    
    def get_market_sentiment_summary(self, analyses: List[Dict]) -> Dict:
        """Generate overall market sentiment from multiple analyses"""
        
        if not analyses:
            return {
                'overall_sentiment': 'NEUTRAL',
                'confidence': 1,
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0,
                'high_risk_events': 0,
                'summary': 'No analyses available'
            }
        
        # Count sentiments
        bullish_count = sum(1 for a in analyses if a.get('sentiment') == 'BULLISH')
        bearish_count = sum(1 for a in analyses if a.get('sentiment') == 'BEARISH')
        neutral_count = sum(1 for a in analyses if a.get('sentiment') == 'NEUTRAL')
        
        # Calculate overall sentiment
        if bullish_count > bearish_count and bullish_count > neutral_count:
            overall_sentiment = 'BULLISH'
        elif bearish_count > bullish_count and bearish_count > neutral_count:
            overall_sentiment = 'BEARISH'
        else:
            overall_sentiment = 'NEUTRAL'
        
        # Calculate average confidence
        avg_confidence = sum(a.get('confidence', 5) for a in analyses) / len(analyses)
        
        # Count high-risk events
        high_risk_count = sum(1 for a in analyses if a.get('risk_level') == 'HIGH')
        
        # Generate summary
        summary_parts = []
        if bullish_count > 0:
            summary_parts.append(f"{bullish_count} bullish events")
        if bearish_count > 0:
            summary_parts.append(f"{bearish_count} bearish events")
        if neutral_count > 0:
            summary_parts.append(f"{neutral_count} neutral events")
        
        summary = f"Market sentiment: {overall_sentiment} ({', '.join(summary_parts)})"
        
        return {
            'overall_sentiment': overall_sentiment,
            'confidence': round(avg_confidence, 1),
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'neutral_count': neutral_count,
            'high_risk_events': high_risk_count,
            'total_events': len(analyses),
            'summary': summary
        }

def main():
    """Test the sentiment analyzer"""
    try:
        analyzer = NewsSentimentAnalyzer()
        
        # Test with sample event
        sample_event = {
            'description': 'Non-Farm Payrolls',
            'actual': 285.0,
            'expected': 175.0,
            'previous': 180.0,
            'surprise_pct': 62.9,
            'impact': 'high',
            'symbols': ['USD'],
            'time': '2025-01-17T08:30:00Z',
            'source': 'FMP'
        }
        
        print("Testing News Sentiment Analyzer...")
        analysis = analyzer.analyze_single_event(sample_event)
        
        print("\nAnalysis Result:")
        print(f"Sentiment: {analysis['sentiment']}")
        print(f"Confidence: {analysis['confidence']}/10")
        print(f"Risk Level: {analysis['risk_level']}")
        print(f"Key Pairs: {analysis['key_pairs']}")
        print(f"Implication: {analysis['trading_implication']}")
        
        print("\nSUCCESS: Sentiment analyzer is working!")
        
    except Exception as e:
        print(f"ERROR: Error testing sentiment analyzer: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
