#!/usr/bin/env python3
"""
Enhanced Alert Intent Parser
============================
This module provides intelligent parsing of user alert requests and maps them
to the correct moneybot.add_alert parameters.
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

class AlertIntentParser:
    """Parses user intent for alerts and maps to correct parameters."""
    
    def __init__(self):
        self.symbol_patterns = {
            r'\b(btc|bitcoin)\b': 'BTCUSDc',
            r'\b(xau|gold)\b': 'XAUUSDc', 
            r'\b(eth|ethereum)\b': 'ETHUSDc',
            r'\b(eur|euro)\b': 'EURUSDc',
            r'\b(gbp|pound)\b': 'GBPUSDc',
            r'\b(jpy|yen)\b': 'USDJPYc',
            r'\b(usd|dollar)\b': 'USD',
            r'\b(btcusd|btc/usd)\b': 'BTCUSDc',
            r'\b(xauusd|xau/usd)\b': 'XAUUSDc',
            r'\b(eurusd|eur/usd)\b': 'EURUSDc',
            r'\b(gbpusd|gbp/usd)\b': 'GBPUSDc'
        }
        
        self.price_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:k|thousand)?',
            r'(\d+(?:\.\d+)?)\s*(?:m|million)?',
            r'(\d+(?:\.\d+)?)'
        ]
        
        self.condition_patterns = {
            'crosses_above': [r'cross(?:es)?\s+above', r'reach(?:es)?', r'hit(?:s)?', r'price\s+reaches', r'when\s+price\s+reaches'],
            'crosses_below': [r'cross(?:es)?\s+below', r'below\s+(\d+)', r'drop(?:s)?\s+below\s+(\d+)'],
            'greater_than': [r'greater\s+than', r'above\s+(\d+)', r'hit(?:s)?\s+(\d+)'],
            'less_than': [r'less\s+than', r'below\s+(\d+)', r'drop(?:s)?\s+below\s+(\d+)']
        }
        
        self.volatility_patterns = [
            r'volatility\s+(?:high|>20)',
            r'vix\s*>\s*20',
            r'high\s+volatility',
            r'volatile\s+conditions'
        ]
        
        self.purpose_patterns = {
            'first_partials': [r'first\s+partials', r'partial\s+profit', r'scale\s+out'],
            'entry': [r'entry\s+signal', r'enter\s+position', r'buy\s+signal'],
            'exit': [r'exit\s+signal', r'close\s+position', r'sell\s+signal']
        }
    
    def parse_alert_request(self, user_text: str) -> Dict[str, Any]:
        """
        Parse user alert request and return proper moneybot.add_alert parameters.
        
        Args:
            user_text: User's alert request text
            
        Returns:
            Dict with moneybot.add_alert parameters
        """
        user_text = user_text.lower().strip()
        
        # Extract symbol
        symbol = self._extract_symbol(user_text)
        if not symbol:
            raise ValueError("Could not identify trading symbol from request")
        
        # Extract price level
        price_level = self._extract_price_level(user_text)
        if price_level is None:
            raise ValueError("Could not identify price level from request")
        
        # Determine condition type
        condition = self._extract_condition(user_text, price_level)
        
        # Extract volatility conditions
        volatility_conditions = self._extract_volatility_conditions(user_text)
        
        # Extract purpose
        purpose = self._extract_purpose(user_text)
        
        # Build description
        description = self._build_description(symbol, price_level, condition, volatility_conditions, purpose)
        
        # Build parameters
        parameters = {
            "price_level": price_level
        }
        
        if volatility_conditions:
            parameters.update(volatility_conditions)
        
        if purpose:
            parameters["purpose"] = purpose
        
        return {
            "symbol": symbol,
            "alert_type": "price",
            "condition": condition,
            "description": description,
            "parameters": parameters,
            "expires_hours": 24,  # Default 24 hours
            "one_time": True  # Default one-time alert
        }
    
    def _extract_symbol(self, text: str) -> Optional[str]:
        """Extract trading symbol from text."""
        # First try explicit symbol patterns
        for pattern, symbol in self.symbol_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                return symbol
        
        # If no explicit symbol found, try context-based detection
        # Look for price levels that suggest specific symbols
        if re.search(r'4[0-9]{3}', text):  # 4000+ range suggests XAUUSD
            return 'XAUUSDc'
        elif re.search(r'1[0-9]{4,5}', text):  # 10000+ range suggests BTCUSD
            return 'BTCUSDc'
        elif re.search(r'1\.0[0-9]{3}', text):  # 1.0xxx range suggests EURUSD
            return 'EURUSDc'
        elif re.search(r'2[0-9]{3}', text):  # 2000+ range suggests XAUUSD
            return 'XAUUSDc'
        elif re.search(r'4,?248', text):  # Specific 4248 level suggests XAUUSD
            return 'XAUUSDc'
        
        return None
    
    def _extract_price_level(self, text: str) -> Optional[float]:
        """Extract price level from text."""
        # Look for price patterns with context
        price_patterns = [
            r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:k|thousand)',
            r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:m|million)',
            r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(',', '')  # Remove commas
                try:
                    price = float(price_str)
                    # Handle k/m suffixes only if explicitly mentioned
                    if 'k' in match.group(0).lower() or 'thousand' in match.group(0).lower():
                        price *= 1000
                    elif 'm' in match.group(0).lower() or 'million' in match.group(0).lower():
                        price *= 1000000
                    return price
                except ValueError:
                    continue
        return None
    
    def _extract_condition(self, text: str, price_level: float) -> str:
        """Extract condition type from text."""
        for condition, patterns in self.condition_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return condition
        
        # Default to crosses_above for price alerts
        return "crosses_above"
    
    def _extract_volatility_conditions(self, text: str) -> Dict[str, Any]:
        """Extract volatility conditions from text."""
        volatility_conditions = {}
        
        for pattern in self.volatility_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                volatility_conditions.update({
                    "volatility_condition": "high",
                    "vix_threshold": 20.0
                })
                break
        
        return volatility_conditions
    
    def _extract_purpose(self, text: str) -> Optional[str]:
        """Extract alert purpose from text."""
        for purpose, patterns in self.purpose_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return purpose
        return None
    
    def _build_description(self, symbol: str, price_level: float, condition: str, 
                          volatility_conditions: Dict[str, Any], purpose: Optional[str]) -> str:
        """Build human-readable description."""
        desc_parts = [f"{symbol} {condition.replace('_', ' ')} {price_level}"]
        
        if volatility_conditions:
            desc_parts.append("high volatility (VIX > 20)")
        
        if purpose:
            desc_parts.append(f"for {purpose.replace('_', ' ')}")
        
        return " - ".join(desc_parts)

def test_alert_parser():
    """Test the alert parser with various user inputs."""
    parser = AlertIntentParser()
    
    test_cases = [
        "set alert for monitor near 4,248 for first partials; volatility high (VIX > 20)",
        "alert me when bitcoin hits 115000",
        "notify me if gold drops below 2600",
        "alert when EURUSD crosses above 1.0850",
        "set alert for BTCUSD at 50000 for entry signal"
    ]
    
    print("Testing Alert Intent Parser")
    print("=" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. User Input: {test_case}")
        try:
            result = parser.parse_alert_request(test_case)
            print("SUCCESS - Parsed Result:")
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    test_alert_parser()
