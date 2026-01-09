# =====================================
# File: infra/formatting.py
# =====================================
from __future__ import annotations
import MetaTrader5 as mt5


def fmt_price(symbol: str, value: float) -> str:
    """Format a price using the symbol's digits (EURGBPc -> 5 decimals, etc.)."""
    si = mt5.symbol_info(symbol)
    digits = int(getattr(si, "digits", 5) or 5)
    try:
        v = float(value)
    except Exception:
        return str(value)
    return f"{v:.{digits}f}"
