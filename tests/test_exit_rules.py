"""
Quick harness to test Advanced Exits gating + trailing without a real MT5.

Run:
  python scripts/test_exit_rules.py

Expected timeline (logs + prints):
  - At ~0.2R: SL moves to breakeven; trailing remains gated.
  - At ~0.5R: Partial profit executes (if volume >= 0.02).
  - Gates pass -> trailing activates; later price steps trail SL forward.
"""

from __future__ import annotations

import os
import sys
import types
from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np

# Ensure repo root is on sys.path
THIS_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Import manager and then monkeypatch its mt5 reference
import infra.intelligent_exit_manager as iem


# ---- Fake MT5 surface -------------------------------------------------------

@dataclass
class FakePosition:
    ticket: int
    symbol: str
    volume: float
    price_open: float
    price_current: float
    sl: float
    tp: float
    comment: str = ""


class FakeMT5Module:
    # Minimal constants used by the code
    TIMEFRAME_M30 = 0
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 0
    TRADE_RETCODE_DONE = 10009
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    def __init__(self, pos: FakePosition):
        self._pos = pos

    # Module-level getters the manager uses
    def positions_get(self, ticket: Optional[int] = None):
        if ticket is not None and self._pos.ticket != ticket:
            return []
        return [self._pos]

    def symbol_info(self, symbol: str):
        class _Info:
            trade_contract_size = 100000  # generic FX-like
            spread = 10
            point = 0.01
        return _Info()

    def symbol_info_tick(self, symbol: str):
        if self._pos.symbol != symbol:
            return None
        class _Tick:
            ask = self._pos.price_current
            bid = self._pos.price_current
        return _Tick()

    def copy_rates_from_pos(self, symbol: str, tf: int, start: int, count: int):
        # Produce synthetic bars around current price; ATR ~ 0.20
        base = self._pos.price_current
        highs = base + 0.10 + (np.arange(50) * 0.0005)
        lows = base - 0.10
        closes = base + 0.02 + (np.arange(50) * 0.0002)
        arr = np.zeros(50, dtype=[("high", float), ("low", float), ("close", float)])
        arr["high"] = highs
        arr["low"] = lows
        arr["close"] = closes
        return arr

    # For partial profit path; return a done-like result
    class _OrderResult:
        def __init__(self, retcode: int):
            self.retcode = retcode

    def order_send(self, request: Dict[str, Any]):
        # Close partial volume from the single position
        vol = float(request.get("volume", 0))
        if vol > 0 and vol <= self._pos.volume:
            self._pos.volume = round(self._pos.volume - vol, 2)
            return FakeMT5Module._OrderResult(self.TRADE_RETCODE_DONE)
        return FakeMT5Module._OrderResult(0)

    # Unused in this harness
    def terminal_info(self):
        class _Info:
            connected = True
        return _Info()

    def last_error(self):
        return (0, "OK")


class FakeMt5Service:
    def __init__(self, pos: FakePosition):
        self._pos = pos
        self._connected = True

    def connect(self) -> bool:
        return self._connected

    def modify_position(self, ticket: int, new_sl: float, new_tp: float) -> bool:
        if ticket != self._pos.ticket:
            return False
        # Only move SL in favorable direction
        if self._pos.price_open <= self._pos.tp:  # BUY
            if new_sl <= self._pos.sl:
                return False
        else:  # SELL
            if new_sl >= self._pos.sl:
                return False
        self._pos.sl = new_sl
        self._pos.tp = new_tp
        return True

    # Simple helpers the manager sometimes calls
    def account_bal_eq(self):
        return (10000.0, 10000.0)


# ---- Fake Advanced provider -------------------------------------------------

class FakeAdvancedProvider:
    def __init__(self):
        self._features = {
            "M15": {
                "rmag": {"ema200_atr": 1.2},
                "ema_slope": {"ema50": 0.18, "ema200": 0.06},
                "vol_trend": {"state": "expansion_strong_trend"},
                "vwap": {"zone": "inside"},
            },
            # Top-level helpers
            "mtf_score": {"total": 2, "max": 3},
            "vp": {"hvn_dist_atr": 0.6},
        }

    def get_advanced_features(self, symbol: str) -> Dict[str, Any]:
        return {"features": self._features}


def main():
    # Initial position: BUY 0.05 lots at 100.00, SL 99.00, TP 101.00
    pos = FakePosition(
        ticket=1,
        symbol="XAUUSDc",
        volume=0.05,
        price_open=100.00,
        price_current=100.00,
        sl=99.00,
        tp=101.00,
    )

    # Create fake mt5 module and service, monkeypatch into manager module
    fake_mt5_mod = FakeMT5Module(pos)
    fake_mt5_svc = FakeMt5Service(pos)
    iem.mt5 = fake_mt5_mod  # Patch module-level mt5 used inside manager

    # Build IntelligentExitManager with our fake service
    mgr = iem.IntelligentExitManager(
        mt5_service=fake_mt5_svc,
        binance_service=None,
        order_flow_service=None,
    )
    # Provide live advanced data
    mgr.advanced_provider = FakeAdvancedProvider()

    # Add rule using Advanced-adjusted triggers
    add = mgr.add_rule_advanced(
        ticket=pos.ticket,
        symbol=pos.symbol,
        entry_price=pos.price_open,
        direction="buy",
        initial_sl=pos.sl,
        initial_tp=pos.tp,
        advanced_features=mgr.advanced_provider.get_advanced_features(pos.symbol),
        base_breakeven_pct=20.0,
        base_partial_pct=50.0,
        partial_close_pct=50.0,
    )
    print("Added rule:", {k: add[k] for k in ("success",)})

    def step_to(price: float, label: str):
        pos.price_current = price
        actions = mgr.check_exits(vix_price=15.0)
        print(f"\n== {label} price={price:.2f} ==")
        for a in actions:
            print("action:", a.get("action") or a.get("type"), a)
        print(f"state: breakeven={mgr.get_rule(pos.ticket).breakeven_triggered}, "
              f"partial={mgr.get_rule(pos.ticket).partial_triggered}, "
              f"trailing={mgr.get_rule(pos.ticket).trailing_active}, "
              f"SL={pos.sl:.5f}, TP={pos.tp:.5f}, Vol={pos.volume:.2f}")

    # 0.2R (breakeven expected; trailing gated)
    step_to(100.20, "+0.2R (breakeven)")

    # 0.5R (partial expected if vol >= 0.02)
    step_to(100.50, "+0.5R (partial)")

    # 0.7R (gates pass -> trailing activates; SL starts to trail)
    step_to(100.70, "+0.7R (trail)")

    # More steps to see explicit trailing_stop actions
    step_to(100.85, "+0.85R (trail again)")
    step_to(100.95, "+0.95R (trail again)")


if __name__ == "__main__":
    main()
