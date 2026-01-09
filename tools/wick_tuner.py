
# =====================================
# tools/wick_tuner.py
# =====================================
# Quick grid-search for wick/spike thresholds using historical candles from MT5.
# Usage (from venv where MetaTrader5 is installed, MT5 running & logged in):
#   python tools/wick_tuner.py --symbols XAUUSDc BTCUSDc --tfs M5 M15 --days 14
#
# Output: CSV + console table with suggested thresholds per symbol/tf.
from __future__ import annotations

import argparse
import math
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except Exception as e:
    print("MetaTrader5 import failed. Ensure `pip install MetaTrader5` in your venv.", file=sys.stderr)
    raise

# --- Candle stats (copied minimally from domain/candle_stats to avoid project imports) ---
def _bbands(close: pd.Series, period: int = 20) -> Optional[tuple[float,float,float]]:
    if close is None or len(close) < period + 2:
        return None
    ma = close.rolling(period).mean()
    sd = close.rolling(period).std(ddof=0)
    upper = ma + 2 * sd
    lower = ma - 2 * sd
    u = float(upper.iloc[-1])
    l = float(lower.iloc[-1])
    m = float(ma.iloc[-1])
    return m, u, l

def _atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    if df is None or len(df) < period + 2:
        return None
    high = df["high"].astype(float).to_numpy()
    low = df["low"].astype(float).to_numpy()
    close = df["close"].astype(float).to_numpy()
    prev_close = close[:-1]
    tr1 = high[1:] - low[1:]
    tr2 = np.abs(high[1:] - prev_close)
    tr3 = np.abs(low[1:] - prev_close)
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    # Wilder smoothing
    n = period
    atr_arr = np.zeros_like(close, dtype=float)
    atr_arr[:n] = np.nan
    atr_arr[n] = np.nanmean(tr[:n])
    for i in range(n + 1, len(close)):
        atr_arr[i] = (atr_arr[i - 1] * (n - 1) + tr[i - 1]) / n
    val = atr_arr[-1]
    return float(val) if np.isfinite(val) else None

def compute_candle_stats(df: pd.DataFrame, bb_period: int = 20, atr_period: int = 14) -> Dict[str, float]:
    if df is None or df.empty:
        return {}
    o = float(df.iloc[-1]["open"])
    h = float(df.iloc[-1]["high"])
    l = float(df.iloc[-1]["low"])
    c = float(df.iloc[-1]["close"])
    rng = max(1e-9, h - l)
    body = abs(c - o)
    uw = h - max(o, c)
    lw = min(o, c) - l
    body_frac = float(body / rng)
    uw_frac = float(uw / rng)
    lw_frac = float(lw / rng)
    atr = _atr(df, period=atr_period) or 0.0
    rng_atr_mult = float((rng / atr) if atr else 0.0)
    mlu = _bbands(df["close"].astype(float), period=bb_period)
    bb_dist_upper_frac = bb_dist_lower_frac = 1.0
    if mlu:
        m,u,lwbb = mlu
        span = max(1e-9, (u - lwbb))
        bb_dist_upper_frac = float(abs(u - c) / span)
        bb_dist_lower_frac = float(abs(c - lwbb) / span)
    return {
        "body_frac": body_frac,
        "uw_frac": uw_frac,
        "lw_frac": lw_frac,
        "rng": float(rng),
        "atr": float(atr or 0.0),
        "rng_atr_mult": rng_atr_mult,
        "bb_dist_upper_frac": bb_dist_upper_frac,
        "bb_dist_lower_frac": bb_dist_lower_frac,
    }

# --- Simple EMA helper for context ---
def ema(arr: np.ndarray, n: int) -> np.ndarray:
    if arr.size < n: 
        return np.full_like(arr, np.nan, dtype=float)
    alpha = 2/(n+1)
    out = np.empty_like(arr, dtype=float)
    out[:] = np.nan
    out[n-1] = np.nanmean(arr[:n])
    for i in range(n, arr.size):
        out[i] = alpha*arr[i] + (1-alpha)*out[i-1]
    return out

def fetch_df(symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
    }
    tf = tf_map.get(timeframe.upper(), mt5.TIMEFRAME_M5)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    df = df[["time","open","high","low","close","volume"]].set_index("time")
    return df

@dataclass
class EvalResult:
    precision: float
    recall: float
    f1: float
    saved_mae_mean: float
    missed_upside_mean: float
    n_signals: int

def evaluate_thresholds(df: pd.DataFrame, wick_up: float, wick_lo: float, body_max: float, bb_near: float, spike_mult: float,
                        k_forward: int = 3, adverse_k: float = 0.5) -> EvalResult:
    """
    Evaluate: when a signal triggers (exhaustion wick near band),
    does price move against the 'trend context' within next k bars (good), or continue (bad)?
    Trend context inferred via EMA alignment (20/50/200).
    """
    close = df["close"].to_numpy(dtype=float)
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)
    bullish_ctx = (close > ema20) & (ema20 > ema50) & (ema50 > ema200)
    bearish_ctx = (close < ema20) & (ema20 < ema50) & (ema50 < ema200)

    # Precompute BB distances per bar
    # (reuse compute_candle_stats across rolling windows is expensive; compute on the fly per index)
    stats = []
    for i in range(len(df)):
        win = df.iloc[: i+1].tail(60)  # window for BB/ATR
        s = compute_candle_stats(win, bb_period=20, atr_period=14)
        stats.append(s if s else {})
    body_frac = np.array([s.get("body_frac", np.nan) for s in stats])
    uw_frac   = np.array([s.get("uw_frac", np.nan) for s in stats])
    lw_frac   = np.array([s.get("lw_frac", np.nan) for s in stats])
    dbu       = np.array([s.get("bb_dist_upper_frac", 1.0) for s in stats])
    dbl       = np.array([s.get("bb_dist_lower_frac", 1.0) for s in stats])
    atr_arr   = np.array([s.get("atr", np.nan) for s in stats])

    near_upper = dbu <= bb_near
    near_lower = dbl <= bb_near

    # Signal definitions (at bar close)
    wick_up_sig = (uw_frac >= wick_up) & (body_frac <= body_max) & near_upper  # exhaustion up
    wick_lo_sig = (lw_frac >= wick_lo) & (body_frac <= body_max) & near_lower  # exhaustion down

    # Context-aware "against" signals
    # If bullish context (think long), an UP exhaustion is against continuation (bearish risk)
    sig_against_long  = wick_up_sig & bullish_ctx
    sig_against_short = wick_lo_sig & bearish_ctx

    sig_idx = np.where(sig_against_long | sig_against_short)[0]
    n = int(sig_idx.size)
    if n == 0:
        return EvalResult(0,0,0,0,0,0)

    good = 0
    saved_mae = []
    missed_upside = []
    for t in sig_idx:
        end = min(len(close)-1, t + k_forward)
        window = close[t+1: end+1]
        if window.size == 0 or not np.isfinite(atr_arr[t]):
            continue
        # For a "good" exit: price moves against ctx by at least adverse_k * ATR
        if sig_against_long[t]:
            # move down is adverse to long
            mae = (np.nanmin(window) - close[t])  # negative is down
            good_flag = (mae <= -adverse_k * atr_arr[t])
            saved_mae.append(-mae)  # positive amount of adverse avoided
            # upside missed if price went up
            missed = (np.nanmax(window) - close[t])
            missed_upside.append(max(0.0, missed))
        else:
            # context short: adverse is up
            mae = (np.nanmax(window) - close[t])  # positive is up
            good_flag = (mae >= adverse_k * atr_arr[t])
            saved_mae.append(mae)  # amount of adverse avoided
            missed = (close[t] - np.nanmin(window))
            missed_upside.append(max(0.0, missed))
        good += int(bool(good_flag))

    precision = good / max(1, n)
    # "Recall" proxy: fraction of all large adverse moves that were signaled
    # Build adverse events set:
    adverse_events = 0
    caught = 0
    for t in range(len(close)-k_forward-1):
        end = t + k_forward
        if not np.isfinite(atr_arr[t]):
            continue
        if bullish_ctx[t]:
            mae = (np.nanmin(close[t+1:end+1]) - close[t])
            if mae <= -adverse_k * atr_arr[t]:
                adverse_events += 1
                if (wick_up_sig & bullish_ctx)[t]:
                    caught += 1
        elif bearish_ctx[t]:
            mae = (np.nanmax(close[t+1:end+1]) - close[t])
            if mae >= adverse_k * atr_arr[t]:
                adverse_events += 1
                if (wick_lo_sig & bearish_ctx)[t]:
                    caught += 1
    recall = caught / max(1, adverse_events)
    f1 = (2*precision*recall) / max(1e-9, (precision+recall))

    return EvalResult(
        precision=precision,
        recall=recall,
        f1=f1,
        saved_mae_mean=float(np.nanmean(saved_mae) if len(saved_mae)>0 else 0.0),
        missed_upside_mean=float(np.nanmean(missed_upside) if len(missed_upside)>0 else 0.0),
        n_signals=n
    )

def grid_search(df: pd.DataFrame, symbol: str, tf: str,
                wick_vals=(0.55,0.60,0.65),
                body_vals=(0.30,0.35,0.40),
                bb_vals=(0.10,0.15,0.20)) -> pd.DataFrame:
    rows = []
    for w in wick_vals:
        for b in body_vals:
            for bb in bb_vals:
                res = evaluate_thresholds(df, wick_up=w, wick_lo=w, body_max=b, bb_near=bb, spike_mult=1.8)
                score = res.f1 + 0.25*(res.saved_mae_mean / max(1e-9, res.missed_upside_mean + 1e-9))
                rows.append({
                    "symbol": symbol, "tf": tf,
                    "wick_exh_frac": w, "body_max_frac": b, "bb_near_frac": bb,
                    "precision": res.precision, "recall": res.recall, "f1": res.f1,
                    "saved_mae_mean": res.saved_mae_mean, "missed_upside_mean": res.missed_upside_mean,
                    "n_signals": res.n_signals,
                    "score": float(score),
                })
    return pd.DataFrame(rows).sort_values("score", ascending=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["XAUUSDc","BTCUSDc"], help="Symbols (use your broker suffix)")
    ap.add_argument("--tfs", nargs="+", default=["M5","M15"], help="Timeframes to test")
    ap.add_argument("--days", type=int, default=14, help="Lookback days (~ bars depend on tf)")
    ap.add_argument("--out", default="wick_tuning_results.csv")
    args = ap.parse_args()

    if not mt5.initialize():
        print("mt5.initialize failed", file=sys.stderr)
        sys.exit(2)

    try:
        all_rows = []
        for sym in args.symbols:
            # pre-load by checking symbol select
            mt5.symbol_select(sym, True)
            for tf in args.tfs:
                # rough bars estimate per day
                per_day = {"M5": 288, "M15": 96, "M30": 48, "H1":24}.get(tf.upper(), 288)
                bars = int(args.days * per_day) + 400  # extra for indicators warmup
                df = fetch_df(sym, tf, bars=bars)
                if df is None or len(df) < 400:
                    print(f"[warn] no data for {sym} {tf} (bars={bars})")
                    continue
                # drop warmup
                df = df.tail(int(args.days * per_day))
                resdf = grid_search(df, sym, tf)
                best = resdf.iloc[0].to_dict() if len(resdf)>0 else None
                if best:
                    print(f"\n=== {sym} {tf} — BEST ===")
                    for k in ["wick_exh_frac","body_max_frac","bb_near_frac","precision","recall","f1","saved_mae_mean","missed_upside_mean","n_signals","score"]:
                        print(f"{k:18s}: {best[k]}")
                all_rows.append(resdf)

        if len(all_rows)>0:
            out = pd.concat(all_rows, ignore_index=True)
            out.to_csv(args.out, index=False)
            print(f"\nSaved results to {args.out}")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()
