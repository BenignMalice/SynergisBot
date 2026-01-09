# app/config/virt_pending.py
"""
Config-driven defaults for emulated pending orders.
Reads from environment (optionally) and allows per-symbol overrides.

ENV (optional):
  VIRT_DEFAULT_SLIPPAGE_POINTS=30
  VIRT_DEFAULT_EXPIRY_MINUTES=45
  VIRT_SYMBOL_OVERRIDES={"XAUUSDC":{"slippage_pts":60,"expiry_min":20},"BTCUSDC":{"slippage_pts":100}}
"""

from __future__ import annotations
import os, json
from dataclasses import dataclass
from typing import Dict, Any

_DEFAULT_SLIPPAGE = int(os.getenv("VIRT_DEFAULT_SLIPPAGE_POINTS", "30"))
_DEFAULT_EXPIRY_MIN = int(os.getenv("VIRT_DEFAULT_EXPIRY_MINUTES", "45"))
_OVERRIDES_RAW = os.getenv("VIRT_SYMBOL_OVERRIDES", "{}")

try:
    _OVERRIDES: Dict[str, Any] = json.loads(_OVERRIDES_RAW) if _OVERRIDES_RAW else {}
except Exception:
    _OVERRIDES = {}


@dataclass
class PendingDefaults:
    slippage_pts: int
    expiry_secs: int


def get_for_symbol(symbol: str) -> PendingDefaults:
    s = (symbol or "").upper()
    o = _OVERRIDES.get(s) or {}
    slip = int(o.get("slippage_pts", _DEFAULT_SLIPPAGE))
    exp_min = int(o.get("expiry_min", _DEFAULT_EXPIRY_MIN))
    return PendingDefaults(slippage_pts=slip, expiry_secs=exp_min * 60)
