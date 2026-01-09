# File: config/lot_sizing.py
# ---------------------------------------------
# Dynamic Lot Sizing Configuration
# ---------------------------------------------
"""
Symbol-specific lot sizing with risk-based calculations.

Usage:
    from config.lot_sizing import get_lot_size
    
    lot = get_lot_size(
        symbol="BTCUSDc",
        entry=65000,
        stop_loss=64800,
        equity=10000,
        risk_pct=1.0  # Optional, uses default if not provided
    )
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# SYMBOL-SPECIFIC LOT SIZE CONFIGURATION
# ============================================================================

# Maximum lot sizes per symbol (hard caps)
MAX_LOT_SIZES: Dict[str, float] = {
    # Crypto
    "BTCUSDc": 0.02,
    "BTCUSD": 0.02,
    
    # Metals
    "XAUUSDc": 0.02,
    "XAUUSD": 0.02,
    
    # Forex Majors
    "EURUSDc": 0.04,
    "EURUSD": 0.04,
    "GBPUSDc": 0.04,
    "GBPUSD": 0.04,
    "USDJPYc": 0.04,
    "USDJPY": 0.04,
    
    # Forex Crosses
    "GBPJPYc": 0.04,
    "GBPJPY": 0.04,
    "EURJPYc": 0.04,
    "EURJPY": 0.04,
    "EURGBPc": 0.04,
    "EURGBP": 0.04,
    
    # Default for unlisted symbols
    "_default": 0.01
}

# Default risk percentage per symbol (% of equity)
DEFAULT_RISK_PCT: Dict[str, float] = {
    # Crypto (higher volatility, lower risk %)
    "BTCUSDc": 0.75,
    "BTCUSD": 0.75,
    
    # Metals (medium volatility, medium risk %)
    "XAUUSDc": 1.0,
    "XAUUSD": 1.0,
    
    # Forex (lower volatility, higher risk %)
    "EURUSDc": 1.25,
    "EURUSD": 1.25,
    "GBPUSDc": 1.25,
    "GBPUSD": 1.25,
    "USDJPYc": 1.25,
    "USDJPY": 1.25,
    "GBPJPYc": 1.0,  # More volatile cross
    "GBPJPY": 1.0,
    "EURJPYc": 1.0,
    "EURJPY": 1.0,
    "EURGBPc": 1.25,
    "EURGBP": 1.25,
    
    # Default
    "_default": 1.0
}

# Minimum lot sizes (broker minimums)
MIN_LOT_SIZE = 0.01

# ============================================================================
# LOT SIZE CALCULATION FUNCTIONS
# ============================================================================

def get_max_lot_size(symbol: str) -> float:
    """
    Get maximum allowed lot size for a symbol.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDc", "EURUSD")
    
    Returns:
        Maximum lot size
    """
    # Normalize symbol (case-insensitive, with or without 'c')
    symbol_norm = symbol.upper()
    
    # Try exact match first
    if symbol_norm in MAX_LOT_SIZES:
        return MAX_LOT_SIZES[symbol_norm]
    
    # Try without 'c' suffix
    if symbol_norm.endswith('C'):
        symbol_base = symbol_norm[:-1]
        if symbol_base in MAX_LOT_SIZES:
            return MAX_LOT_SIZES[symbol_base]
    
    # Try with 'c' suffix
    symbol_with_c = symbol_norm + 'c' if not symbol_norm.endswith('C') else symbol_norm
    if symbol_with_c in MAX_LOT_SIZES:
        return MAX_LOT_SIZES[symbol_with_c]
    
    # Return default
    return MAX_LOT_SIZES["_default"]


def get_default_risk_pct(symbol: str) -> float:
    """
    Get default risk percentage for a symbol.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDc", "EURUSD")
    
    Returns:
        Risk percentage (e.g., 1.0 = 1% of equity)
    """
    # Normalize symbol
    symbol_norm = symbol.upper()
    
    # Try exact match first
    if symbol_norm in DEFAULT_RISK_PCT:
        return DEFAULT_RISK_PCT[symbol_norm]
    
    # Try without 'c' suffix
    if symbol_norm.endswith('C'):
        symbol_base = symbol_norm[:-1]
        if symbol_base in DEFAULT_RISK_PCT:
            return DEFAULT_RISK_PCT[symbol_base]
    
    # Try with 'c' suffix
    symbol_with_c = symbol_norm + 'c' if not symbol_norm.endswith('C') else symbol_norm
    if symbol_with_c in DEFAULT_RISK_PCT:
        return DEFAULT_RISK_PCT[symbol_with_c]
    
    # Return default
    return DEFAULT_RISK_PCT["_default"]


def calculate_lot_from_risk(
    symbol: str,
    entry: float,
    stop_loss: float,
    equity: float,
    risk_pct: Optional[float] = None,
    tick_value: float = 1.0,
    tick_size: float = 0.01,
    contract_size: float = 100000
) -> float:
    """
    Calculate lot size based on risk percentage.
    
    Formula:
        lot = (equity * risk_pct / 100) / (stop_distance_in_ticks * tick_value)
    
    Args:
        symbol: Trading symbol
        entry: Entry price
        stop_loss: Stop loss price
        equity: Account equity
        risk_pct: Risk percentage (if None, uses symbol default)
        tick_value: Value of one tick (from MT5 symbol info)
        tick_size: Size of one tick (from MT5 symbol info)
        contract_size: Contract size (from MT5 symbol info)
    
    Returns:
        Calculated lot size (capped by symbol max)
    """
    # Use default risk % if not provided
    if risk_pct is None:
        risk_pct = get_default_risk_pct(symbol)
    
    # Calculate risk amount in account currency
    risk_amount = equity * (risk_pct / 100.0)
    
    # Calculate stop distance
    stop_distance = abs(entry - stop_loss)
    
    if stop_distance <= 0:
        logger.warning(f"Invalid stop distance for {symbol}: {stop_distance}")
        return MIN_LOT_SIZE
    
    # Calculate stop distance in ticks
    if tick_size > 0:
        stop_distance_ticks = stop_distance / tick_size
    else:
        stop_distance_ticks = stop_distance / 0.01  # Fallback
    
    # Calculate lot size
    if tick_value > 0 and stop_distance_ticks > 0:
        lot = risk_amount / (stop_distance_ticks * tick_value)
    else:
        logger.warning(f"Invalid tick value or distance for {symbol}")
        return MIN_LOT_SIZE
    
    # Round to 2 decimal places (standard lot precision)
    # Most brokers support 0.01, 0.02, 0.03, etc.
    lot = round(lot, 2)
    
    # Apply minimum
    if lot < MIN_LOT_SIZE:
        lot = MIN_LOT_SIZE
    
    # Apply symbol-specific maximum
    max_lot = get_max_lot_size(symbol)
    if lot > max_lot:
        logger.info(f"Lot size {lot} capped to {max_lot} for {symbol}")
        lot = max_lot
    
    # Ensure lot size is in 0.01 increments (not 0.001)
    # Round to nearest 0.01
    lot = round(lot / 0.01) * 0.01
    lot = round(lot, 2)  # Clean up floating point errors
    
    return lot


def get_lot_size(
    symbol: str,
    entry: float,
    stop_loss: float,
    equity: float,
    risk_pct: Optional[float] = None,
    use_risk_based: bool = True,
    tick_value: Optional[float] = None,
    tick_size: Optional[float] = None,
    contract_size: Optional[float] = None
) -> float:
    """
    Get appropriate lot size for a trade.
    
    This is the main function to use for lot sizing.
    
    Args:
        symbol: Trading symbol
        entry: Entry price
        stop_loss: Stop loss price
        equity: Account equity
        risk_pct: Risk percentage (optional, uses symbol default)
        use_risk_based: If True, calculates based on risk; if False, uses max lot
        tick_value: MT5 tick value (optional, uses default if not provided)
        tick_size: MT5 tick size (optional, uses default if not provided)
        contract_size: MT5 contract size (optional, uses default if not provided)
    
    Returns:
        Lot size to use
    """
    if not use_risk_based:
        # Just return the maximum lot size for this symbol
        return get_max_lot_size(symbol)
    
    # Use defaults if MT5 info not provided
    if tick_value is None:
        tick_value = 1.0
    if tick_size is None:
        tick_size = 0.01
    if contract_size is None:
        contract_size = 100000
    
    # Calculate risk-based lot size
    lot = calculate_lot_from_risk(
        symbol=symbol,
        entry=entry,
        stop_loss=stop_loss,
        equity=equity,
        risk_pct=risk_pct,
        tick_value=tick_value,
        tick_size=tick_size,
        contract_size=contract_size
    )
    
    logger.info(
        f"Lot sizing for {symbol}: "
        f"Entry={entry}, SL={stop_loss}, "
        f"Risk={risk_pct or get_default_risk_pct(symbol)}%, "
        f"Equity={equity}, "
        f"Result={lot} lots"
    )
    
    return lot


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_symbol_category(symbol: str) -> str:
    """
    Get the category of a symbol (CRYPTO, METAL, FOREX).
    
    Args:
        symbol: Trading symbol
    
    Returns:
        Category string
    """
    symbol_norm = symbol.upper().rstrip('C')
    
    if 'BTC' in symbol_norm or 'ETH' in symbol_norm:
        return "CRYPTO"
    elif 'XAU' in symbol_norm or 'XAG' in symbol_norm:
        return "METAL"
    else:
        return "FOREX"


def get_lot_sizing_info(symbol: str) -> Dict[str, any]:
    """
    Get all lot sizing information for a symbol.
    
    Args:
        symbol: Trading symbol
    
    Returns:
        Dictionary with max_lot, default_risk_pct, category
    """
    return {
        "symbol": symbol,
        "max_lot": get_max_lot_size(symbol),
        "default_risk_pct": get_default_risk_pct(symbol),
        "category": get_symbol_category(symbol),
        "min_lot": MIN_LOT_SIZE
    }


def get_lot_size_for_range_scalp() -> float:
    """
    Get fixed lot size for range scalping trades.
    
    ALL range scalps use fixed 0.01 lots (no risk-based calculation).
    This is specified in the Range Scalping Master Plan V2.
    
    Returns:
        Fixed lot size: 0.01
    """
    return 0.01


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Test the configuration
    test_symbols = ["BTCUSDc", "XAUUSDc", "EURUSDc", "GBPJPYc"]
    
    print("=== Lot Sizing Configuration ===\n")
    
    for symbol in test_symbols:
        info = get_lot_sizing_info(symbol)
        print(f"{symbol}:")
        print(f"  Category: {info['category']}")
        print(f"  Max Lot: {info['max_lot']}")
        print(f"  Default Risk %: {info['default_risk_pct']}")
        print()
    
    print("\n=== Risk-Based Lot Calculation ===\n")
    
    # Example: BTCUSD with $10,000 equity
    equity = 10000
    entry = 65000
    stop_loss = 64800
    
    lot = get_lot_size(
        symbol="BTCUSDc",
        entry=entry,
        stop_loss=stop_loss,
        equity=equity,
        use_risk_based=True
    )
    
    print(f"BTCUSD: Entry={entry}, SL={stop_loss}, Equity=${equity}")
    print(f"Calculated Lot: {lot}")
    print(f"Risk Amount: ${equity * get_default_risk_pct('BTCUSDc') / 100}")

