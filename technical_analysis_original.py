# File: technical_analysis.py
# --------------------------
# Reads indicator snapshots written by TG_IndicatorBridge.mq5 (MT5 EA) from Common\Files.
# Falls back to light Python-side calculations if snapshot not available in time.

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

import MetaTrader5 as mt5
import numpy as np
import pandas as pd


class TechnicalAnalysis:
    def __init__(self, common_files_dir: Path):
        self.common_dir = common_files_dir

    def request_snapshot(self, symbol: str, timeframes: list[str]) -> Path:
        """Write request file for the MQL5 EA to process."""
        self.common_dir.mkdir(parents=True, exist_ok=True)
        req = self.common_dir / "indicator_request.txt"
        text = (
            f"symbol={symbol}\n"
            f"timeframes={','.join(timeframes)}\n"
            f"requested_at={time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        req.write_text(text, encoding="utf-8")
        return req

    def load_snapshot(
        self, symbol: str, wait_seconds: float = 2.5
    ) -> Optional[Dict[str, Any]]:
        """Wait briefly for snapshot JSON file and return parsed dict."""
        snap = self.common_dir / f"indicator_snapshot_{symbol}.json"
        end = time.time() + wait_seconds
        while time.time() < end:
            if snap.exists() and snap.stat().st_size > 0:
                try:
                    return json.loads(snap.read_text(encoding="utf-8"))
                except Exception:
                    pass
            time.sleep(0.2)
        return None

    # ---- Fallback: quick Python TA from MT5 OHLCV ----
    def _fetch_df(
        self, symbol: str, timeframe: int, bars: int = 400
    ) -> Optional[pd.DataFrame]:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})
        df = df[["time", "open", "high", "low", "close", "volume"]].set_index("time")
        return df

    def _fallback_snapshot(self, symbol: str, timeframe: int) -> dict:
        df = self._fetch_df(symbol, timeframe, 200)
        if df is None or df.empty:
            raise RuntimeError(f"No MT5 data for {symbol} tf={timeframe}")

        close = df["close"].iloc[-1]

        # EMAs
        ema20 = df["close"].ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = df["close"].ewm(span=50, adjust=False).mean().iloc[-1]
        ema200 = df["close"].ewm(span=200, adjust=False).mean().iloc[-1]

        # ATR(14)
        prev_close = df["close"].shift(1)
        tr = np.maximum(
            df["high"] - df["low"],
            np.maximum((df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()),
        )
        atr14 = tr.rolling(14).mean().iloc[-1]

        # ADX(14) (quick approximation)
        up = df["high"].diff()
        dn = -df["low"].diff()
        plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
        minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
        tr_sm = tr.rolling(14).sum()
        plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(14).sum() / tr_sm
        minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(14).sum() / tr_sm
        dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).fillna(0)
        adx = dx.rolling(14).mean().iloc[-1]

        # Bollinger(20)
        ma20 = df["close"].rolling(20).mean().iloc[-1]
        std20 = df["close"].rolling(20).std(ddof=0).iloc[-1]
        bb_upper = ma20 + 2 * std20
        bb_lower = ma20 - 2 * std20
        bbw = (bb_upper - bb_lower) / close if close else None

        # regime
        bull = (ema20 > ema50 > ema200) and (close > ema20)
        bear = (ema20 < ema50 < ema200) and (close < ema20)
        if adx >= 25 and (bull or bear):
            regime = "TREND"
        elif close and atr14 and atr14 / close > 0.02:
            regime = "VOLATILE"
        else:
            regime = "RANGE"

        return {
            "close": float(close),
            "ema_20": float(ema20),
            "ema_50": float(ema50),
            "ema_200": float(ema200),
            "atr_14": float(atr14),
            "adx": float(adx),
            "bb_upper": float(bb_upper),
            "bb_middle": float(ma20),
            "bb_lower": float(bb_lower),
            "bb_width": float(bbw) if bbw is not None else None,
            "regime": regime,
        }

    # Public: get one timeframe (preferring MT5 EA snapshot)
    def get_tf(self, symbol: str, tf_name: str, tf_const: int) -> dict:
        snap = self.load_snapshot(symbol, wait_seconds=0.0)  # non-blocking first
        if snap and tf_name in snap and isinstance(snap[tf_name], dict):
            return snap[tf_name]
        # fallback calc
        return self._fallback_snapshot(symbol, tf_const)

    # Convenience: request and then read M5/M15/H1 from snapshot; fallback as needed
    def get_multi(self, symbol: str) -> dict:
        # ask EA for a fresh snapshot
        self.request_snapshot(symbol, ["M5", "M15", "M30", "H1"])
        snap = self.load_snapshot(symbol, wait_seconds=2.5)

        out: dict[str, dict] = {}

        if snap and isinstance(snap, dict):
            m5 = snap.get("M5")
            m15 = snap.get("M15")
            h1 = snap.get("H1")
            if isinstance(m5, dict):
                out["M5"] = m5
            if isinstance(m15, dict):
                out["M15"] = m15
            if isinstance(h1, dict):
                out["H1"] = h1

        # Top up with fallbacks if any missing
        if "M5" not in out:
            out["M5"] = self._fallback_snapshot(symbol, mt5.TIMEFRAME_M5)
        if "M15" not in out:
            out["M15"] = self._fallback_snapshot(symbol, mt5.TIMEFRAME_M15)
        if "H1" not in out:
            out["H1"] = self._fallback_snapshot(symbol, mt5.TIMEFRAME_H1)

        return out
