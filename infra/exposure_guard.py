# =====================================
# infra/exposure_guard.py
# =====================================
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional, Tuple, List, Any

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from config import settings

log = logging.getLogger(__name__)

# ---------- helpers ----------
_FX_RE = re.compile(r"([A-Z]{6})")


def _fx_base_quote(symbol: str) -> Optional[Tuple[str, str]]:
    """
    Try to extract a 6-letter FX pair out of broker symbols like 'EURUSD.m', 'GBPUSD-RAW', etc.
    Returns ('EUR','USD') or None if not a spot FX pair.
    """
    m = _FX_RE.search(symbol.upper())
    if not m:
        return None
    six = m.group(1)
    return six[:3], six[3:]


def _tf_to_mt5(tf: str) -> int:
    tf = (tf or "").upper()
    return {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
    }.get(tf, mt5.TIMEFRAME_M15)


def _fetch_df(symbol: str, timeframe: int, bars: int) -> Optional[pd.DataFrame]:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    return df[["time", "close"]].set_index("time")


def _corr(symbol_a: str, symbol_b: str, *, tf: str, lookback: int) -> Optional[float]:
    tf_mt5 = _tf_to_mt5(tf)
    da = _fetch_df(symbol_a, tf_mt5, bars=max(200, lookback + 5))
    db = _fetch_df(symbol_b, tf_mt5, bars=max(200, lookback + 5))
    if da is None or db is None or len(da) < lookback or len(db) < lookback:
        return None
    df = pd.concat(
        [da["close"].pct_change(), db["close"].pct_change()], axis=1
    ).dropna()
    if len(df) < lookback // 2:
        return None
    c = float(df.corr().iloc[0, 1])
    if np.isnan(c):
        return None
    return c


@dataclass
class GuardResult:
    allow: bool
    adjusted_risk_pct: float
    reason: str
    correlated_with: List[str]


class ExposureGuard:
    """
    Correlation & currency exposure guard + optional drawdown scaling:
      • Block or trim risk when the candidate symbol is highly correlated with open positions in the same direction.
      • Optional per-currency max open positions cap.
      • Optional drawdown-aware scaling (multiplies the trimmed risk by a factor from JournalRepo).

    Drawdown scaling is enabled when a JournalRepo is provided (either at construction
    or per evaluate(...) call). If no repo is provided, behavior is identical to before.
    """

    def __init__(self, journal_repo: Optional[Any] = None):
        # Correlation/Exposure knobs
        self.corr_thr = float(getattr(settings, "EXPO_CORR_THRESHOLD", 0.80))
        self.max_same_dir = int(getattr(settings, "EXPO_MAX_CORRELATED_SAME_DIR", 1))
        self.reduce_factor = float(
            getattr(settings, "EXPO_CORR_RISK_REDUCE_FACTOR", 0.50)
        )
        self.tf = str(getattr(settings, "EXPO_CORR_TF", "M15"))
        self.lookback = int(getattr(settings, "EXPO_CORR_LOOKBACK_BARS", 300))

        self.ccy_cap_enable = bool(getattr(settings, "EXPO_CCY_CAP_ENABLE", True))
        self.ccy_cap = int(getattr(settings, "EXPO_MAX_OPEN_PER_CCY", 3))

        # Drawdown scaling knobs
        self.journal_repo = journal_repo
        self.dd_scale_enable = bool(getattr(settings, "EXPO_USE_DD_SCALE", True))
        self.dd_lookback_days = int(getattr(settings, "RISK_DD_LOOKBACK_DAYS", 180))
        # Optional clamps for factor via settings (fallbacks live inside JournalRepo too)
        self.dd_min_factor = float(getattr(settings, "RISK_DD_MIN_FACTOR", 0.20))
        self.dd_max_factor = float(getattr(settings, "RISK_DD_MAX_FACTOR", 1.00))

    def set_journal_repo(self, repo: Any) -> None:
        self.journal_repo = repo

    def _dd_factor(self, repo: Any) -> tuple[float, dict]:
        """
        Ask JournalRepo for the drawdown factor. Returns (factor, info).
        Fails open (1.0) on any error.
        """
        try:
            factor, info = repo.risk_scale_from_drawdown(
                lookback_days=self.dd_lookback_days,
                min_factor=self.dd_min_factor,
                max_factor=self.dd_max_factor,
            )
            # Guard against nonsense
            if not np.isfinite(factor) or factor <= 0:
                return 1.0, {"_note": "non-finite dd factor"}
            return float(factor), info
        except Exception:
            return 1.0, {"_note": "dd-factor-error"}

    def evaluate(
        self,
        *,
        symbol: str,
        side: str,
        desired_risk_pct: float,
        journal_repo: Optional[Any] = None,
    ) -> GuardResult:
        """
        Look at current MT5 open positions, compute correlation with candidate, and decide.
        Optionally multiply the resulting risk by a drawdown factor from JournalRepo.
        """
        # Default outputs
        adjusted = float(desired_risk_pct)
        correlated_with: List[str] = []

        cand_fx = _fx_base_quote(symbol)
        try:
            positions = mt5.positions_get() or []
        except Exception:
            positions = []

        # --- 1) Per-currency cap ---
        if self.ccy_cap_enable and cand_fx:
            base, quote = cand_fx
            count = 0
            for p in positions:
                fx = _fx_base_quote(getattr(p, "symbol", "") or "")
                if not fx:
                    continue
                if base in fx or quote in fx:
                    count += 1
            if count >= self.ccy_cap:
                return GuardResult(
                    allow=False,
                    adjusted_risk_pct=0.0,
                    reason=f"currency-cap: already {count} open touching {base}/{quote}",
                    correlated_with=[],
                )

        # --- 2) Correlation vs. same-direction positions ---
        same_dir_syms: List[str] = []
        s_up = side.upper()
        for p in positions:
            try:
                p_side = "BUY" if int(p.type) == mt5.POSITION_TYPE_BUY else "SELL"
            except Exception:
                continue
            if p_side != s_up:
                continue
            same_dir_syms.append(getattr(p, "symbol", "") or "")

        if same_dir_syms:
            strong = []
            for s in same_dir_syms:
                try:
                    r = _corr(symbol, s, tf=self.tf, lookback=self.lookback)
                except Exception:
                    r = None
                if r is None:
                    continue
                if abs(r) >= self.corr_thr:
                    strong.append(s)

            if strong:
                correlated_with = strong
                if len(strong) >= self.max_same_dir:
                    return GuardResult(
                        allow=False,
                        adjusted_risk_pct=0.0,
                        reason=f"corr-cap: ≥{self.max_same_dir} same-dir (|r|≥{self.corr_thr:.2f})",
                        correlated_with=correlated_with,
                    )
                # Trim risk if correlated set but under cap
                adjusted = max(0.01, adjusted * self.reduce_factor)
                reason = f"risk-trim: {len(strong)} corr (|r|≥{self.corr_thr:.2f})"
            else:
                reason = "no-strong-correlation"
        else:
            reason = "no-conflict"

        # --- 3) Optional: Drawdown scaling (multiply) ---
        repo = journal_repo or self.journal_repo
        if self.dd_scale_enable and repo is not None:
            try:
                dd_factor, info = self._dd_factor(repo)
                adjusted = max(0.01, adjusted * dd_factor)
                reason = f"{reason}; dd-factor={dd_factor:.2f} (DD={info.get('max_dd_pct', 0.0):.2f}%)"
            except Exception:
                # fail-open: keep adjusted as-is
                pass

        return GuardResult(
            allow=True,
            adjusted_risk_pct=float(adjusted),
            reason=reason,
            correlated_with=correlated_with,
        )
