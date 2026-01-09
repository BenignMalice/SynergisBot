"""
Helper function for calculating price tolerance based on symbol type.
Ensures consistent tolerance values across the codebase.
"""

def get_price_tolerance(symbol: str) -> float:
    """
    Get appropriate price tolerance for a symbol based on its type.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSD", "XAUUSD", "EURUSD")
    
    Returns:
        float: Appropriate tolerance value
        - BTCUSD: 100.0
        - ETHUSD: 10.0
        - XAUUSD/GOLD: 7.0 (updated 2026-01-08)
        - Forex pairs: 0.001
        - Other crypto: 10.0
        - Default: 0.001
    """
    symbol_upper = symbol.upper().rstrip('C')  # Remove 'c' suffix if present
    
    if "BTC" in symbol_upper:
        return 100.0
    elif "ETH" in symbol_upper:
        return 10.0
    elif "XAU" in symbol_upper or "GOLD" in symbol_upper:
        return 7.0  # Updated from 5.0 to 7.0 (2026-01-08) - provides slight flexibility while preventing excessive slippage
    elif any(crypto in symbol_upper for crypto in ["USDT", "USDC", "BNB", "ADA", "SOL", "DOT", "LINK", "MATIC"]):
        # Other major cryptocurrencies
        return 10.0
    else:
        # Forex pairs and other instruments
        return 0.001

