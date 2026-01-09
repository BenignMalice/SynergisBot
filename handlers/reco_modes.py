# handlers/reco_modes.py
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
from telegram import InlineKeyboardButton
from config import settings


def _f(x, dflt: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return dflt


def decide_order_mode_kind(final: Dict) -> Tuple[str, Optional[str]]:
    """
    Decide 'market' vs 'pending' and 'STOP' vs 'LIMIT'.
    Respect explicit fields if already set; otherwise use a simple heuristic:
      - TREND/BREAKOUT or ADX >= 25  -> PENDING STOP
      - RANGE or (ADX < 20 & BBWidth small) -> PENDING LIMIT
      - else MARKET
    """
    om = (final.get("order_mode") or "").lower()
    ok = (final.get("order_kind") or "").upper()
    if om in ("market", "pending"):
        return (om, ok or (None if om == "market" else "STOP"))

    regime = (final.get("regime") or "").upper()
    adx = _f(final.get("adx"))
    bbwidth = _f(final.get("bbwidth"))
    dirn = (final.get("direction") or "").lower()

    if dirn not in ("buy", "sell"):
        return "market", None
    if regime in ("BREAKOUT", "TREND") or adx >= 25:
        return "pending", "STOP"
    if regime in ("RANGE", "MEAN_REVERSION") or (adx < 20 and (0 < bbwidth < 0.01)):
        return "pending", "LIMIT"
    return "market", None


def add_buttons_for_both_flows(
    rows: List[List[InlineKeyboardButton]],
    *,
    sym: str,
    direction: str,  # "buy" / "sell"
    entry: float,
    sl: float | None,
    tp: float | None,
    order_kind: Optional[str] = None,  # "STOP" | "LIMIT" | None
) -> None:
    """
    Always show:
      1) ✅ Execute <side>  → market (exec|...)
      2) 🧭 Arm at Entry   → emulated pending (virt_arm|...), kind reflects order_kind
    """
    side = direction if direction in ("buy", "sell") else "buy"
    vol = float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01) or 0.01)
    e = float(entry)
    s = float(sl) if sl is not None else 0.0
    t = float(tp) if tp is not None else 0.0

    # Market now
    rows.append(
        [
            InlineKeyboardButton(
                f"✅ Execute {side.upper()}",
                callback_data=f"exec|{sym}|{side}|{e}|{s or ''}|{t or ''}|{vol}",
            ),
            InlineKeyboardButton("🧊 Ignore", callback_data="ignore"),
        ]
    )

    # Pending (emulated): choose S/L by recommendation (default STOP)
    k = "L" if (order_kind or "").upper().startswith("L") else "S"
    rows.append(
        [
            InlineKeyboardButton(
                "🧭 Arm at Entry (Emulated)",
                callback_data=f"virt_arm|{sym}|{'B' if side=='buy' else 'S'}|{e:.2f}|{s:.2f}|{t:.2f}|{vol:.2f}|{k}",
            )
        ]
    )
