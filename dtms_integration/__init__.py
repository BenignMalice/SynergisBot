"""
DTMS Integration Module
Defensive Trade Management System - Integration Components
"""

from .mt5_adapter import DTMSMT5Adapter
from .binance_adapter import DTMSBinanceAdapter
from .telegram_adapter import DTMSTelegramAdapter
from .dtms_system import (
    initialize_dtms,
    start_dtms_monitoring,
    stop_dtms_monitoring,
    run_dtms_monitoring_cycle,
    get_dtms_system_status,
    get_dtms_trade_status,
    get_dtms_action_history,
    add_trade_to_dtms,
    get_dtms_engine
)

__all__ = [
    'DTMSMT5Adapter',
    'DTMSBinanceAdapter',
    'DTMSTelegramAdapter',
    'initialize_dtms',
    'start_dtms_monitoring',
    'stop_dtms_monitoring',
    'run_dtms_monitoring_cycle',
    'get_dtms_system_status',
    'get_dtms_trade_status',
    'get_dtms_action_history',
    'add_trade_to_dtms',
    'get_dtms_engine'
]
