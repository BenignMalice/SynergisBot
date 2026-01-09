# infra/threshold_tuner.py
from __future__ import annotations
import json
import os
import threading
from typing import Any, Dict

_LOCK = threading.RLock()

# Defaults surfaced to the LLM; tweak as you like
DEFAULT_KNOBS: Dict[str, Any] = {
    "rr_floor": 1.20,  # min RR to accept
    "adx_min": 14.0,  # minimal ADX to consider trendy
    "atr_min_ticks": 2.0,  # minimal ATR in ticks
    "ema_alignment_required": False,  # require price >= EMA200 for longs, etc.
}


class ThresholdTuner:
    """
    Tiny adaptive 'knobs' store per (symbol, tf).
    - get_knob_state(symbol, tf) -> dict (surfaced to GPT)
    - update_with_outcome(symbol, tf, hit_tp, hit_sl) -> nudges rr_floor
    State is persisted to a JSON file.
    """

    def __init__(self, path: str = "threshold_tuner.json"):
        self.path = path or "threshold_tuner.json"
        self._state: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self) -> None:
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    def _bucket(self, symbol: str, tf: str) -> Dict[str, Any]:
        with _LOCK:
            sym = self._state.setdefault(symbol, {})
            bucket = sym.setdefault(
                tf, {"knobs": dict(DEFAULT_KNOBS), "stats": {"tp": 0, "sl": 0}}
            )
            # ensure new defaults appear over time
            for k, v in DEFAULT_KNOBS.items():
                bucket["knobs"].setdefault(k, v)
            return bucket

    def get_knob_state(self, symbol: str, tf: str = "M5") -> Dict[str, Any]:
        b = self._bucket(symbol, tf)
        stats = b["stats"]
        out = dict(b["knobs"])
        out.update(
            {
                "_symbol": symbol,
                "_tf": tf,
                "_tp": int(stats.get("tp", 0)),
                "_sl": int(stats.get("sl", 0)),
                "_n": int(stats.get("tp", 0)) + int(stats.get("sl", 0)),
            }
        )
        return out

    def update_with_outcome(
        self, symbol: str, tf: str, *, hit_tp: bool, hit_sl: bool
    ) -> None:
        b = self._bucket(symbol, tf)
        stats = b["stats"]
        if hit_tp:
            stats["tp"] = int(stats.get("tp", 0)) + 1
        if hit_sl:
            stats["sl"] = int(stats.get("sl", 0)) + 1

        # Simple adaptive rule: if losers > winners, tighten (raise rr_floor) a bit; if winners > losers, relax a bit.
        w = int(stats.get("tp", 0))
        l = int(stats.get("sl", 0))
        knobs = b["knobs"]
        rr = float(knobs.get("rr_floor", DEFAULT_KNOBS["rr_floor"]))
        delta = 0.02 if l > w else (-0.02 if w > l else 0.0)
        knobs["rr_floor"] = max(1.00, min(2.00, rr + delta))  # clamp

        with _LOCK:
            self._save()
