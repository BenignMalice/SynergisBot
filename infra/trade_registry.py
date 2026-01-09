"""
Global Trade Registry for Universal SL/TP Manager

Provides thread-safe access to trade ownership tracking across all managers.
"""

import threading
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from infra.universal_sl_tp_manager import TradeState

# Thread-safe registry
_trade_registry: Dict[int, 'TradeState'] = {}
_registry_lock = threading.Lock()

# For backward compatibility (direct access not recommended)
trade_registry = _trade_registry


def get_trade_state(ticket: int) -> Optional['TradeState']:
    """Get trade state from registry (thread-safe)."""
    with _registry_lock:
        return _trade_registry.get(ticket)


def set_trade_state(ticket: int, trade_state: 'TradeState'):
    """Set trade state in registry (thread-safe)."""
    with _registry_lock:
        _trade_registry[ticket] = trade_state


def remove_trade_state(ticket: int):
    """Remove trade state from registry (thread-safe)."""
    with _registry_lock:
        if ticket in _trade_registry:
            del _trade_registry[ticket]


def can_modify_position(ticket: int, manager_name: str) -> bool:
    """Check if manager can modify position (thread-safe)."""
    with _registry_lock:
        trade_state = _trade_registry.get(ticket)
        if not trade_state:
            return False
        return trade_state.managed_by == manager_name


def cleanup_registry():
    """Clear registry on shutdown (thread-safe)."""
    with _registry_lock:
        _trade_registry.clear()

