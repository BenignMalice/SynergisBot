"""
Tick Metrics Module

Provides tick-derived microstructure analytics for analyse_symbol_full.
"""
from typing import Optional

# Lazy import to avoid circular dependencies
_instance = None

def get_tick_metrics_instance():
    """Get the global tick metrics generator instance."""
    global _instance
    return _instance

def set_tick_metrics_instance(instance):
    """Set the global instance (called by main_api startup)."""
    global _instance
    _instance = instance

def clear_tick_metrics_instance():
    """Clear the instance (for testing)."""
    global _instance
    _instance = None

