# =====================================
# infra/indicator_bridge.py
# =====================================
from __future__ import annotations
from pathlib import Path
import time, json
import logging
from typing import Optional, Dict, Any
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class IndicatorBridge:
    def __init__(self, common_files_dir: Path):
        self.common_dir = Path(common_files_dir)

    def request_snapshot(self, symbol: str, timeframes: list[str]) -> Path:
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

    def _fetch_df(
        self, symbol: str, timeframe: int, bars: int = 400
    ) -> Optional[pd.DataFrame]:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})
        return df[["time", "open", "high", "low", "close", "volume"]].set_index("time")

    def _calculate_indicators(self, df: pd.DataFrame) -> dict:
        """Calculate technical indicators from OHLCV data"""
        try:
            close = df["close"].values
            high = df["high"].values
            low = df["low"].values
            
            # RSI (14 period)
            def calc_rsi(prices, period=14):
                deltas = np.diff(prices)
                seed = deltas[:period+1]
                up = seed[seed >= 0].sum() / period
                down = -seed[seed < 0].sum() / period
                rs = up / down if down != 0 else 0
                rsi = np.zeros_like(prices)
                rsi[:period] = 50  # Default for initial values
                rsi[period] = 100 - 100 / (1 + rs)
                
                for i in range(period + 1, len(prices)):
                    delta = deltas[i - 1]
                    if delta > 0:
                        upval = delta
                        downval = 0
                    else:
                        upval = 0
                        downval = -delta
                    
                    up = (up * (period - 1) + upval) / period
                    down = (down * (period - 1) + downval) / period
                    rs = up / down if down != 0 else 0
                    rsi[i] = 100 - 100 / (1 + rs)
                
                return rsi[-1] if len(rsi) > 0 else 50.0
            
            # ATR (14 period)
            def calc_atr(high, low, close, period=14):
                tr = np.maximum(high[1:] - low[1:], 
                               np.abs(high[1:] - close[:-1]),
                               np.abs(low[1:] - close[:-1]))
                atr = np.mean(tr[-period:]) if len(tr) >= period else 0
                return float(atr)
            
            # EMA
            def calc_ema(prices, period):
                if len(prices) < period:
                    return float(np.mean(prices)) if len(prices) > 0 else 0.0
                ema = pd.Series(prices).ewm(span=period, adjust=False).mean()
                return float(ema.iloc[-1]) if len(ema) > 0 else 0.0
            
            # ADX (14 period) - Simplified version
            def calc_adx(high, low, close, period=14):
                if len(close) < period + 1:
                    return 0.0
                
                # Calculate +DM and -DM
                up_move = high[1:] - high[:-1]
                down_move = low[:-1] - low[1:]
                
                plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
                minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
                
                # Calculate TR
                tr = np.maximum(high[1:] - low[1:],
                               np.abs(high[1:] - close[:-1]),
                               np.abs(low[1:] - close[:-1]))
                
                # Smooth with EMA
                atr = pd.Series(tr).ewm(span=period, adjust=False).mean()
                plus_di = 100 * pd.Series(plus_dm).ewm(span=period, adjust=False).mean() / atr
                minus_di = 100 * pd.Series(minus_dm).ewm(span=period, adjust=False).mean() / atr
                
                # Calculate DX and ADX
                dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
                adx = dx.ewm(span=period, adjust=False).mean()
                
                return float(adx.iloc[-1]) if len(adx) > 0 else 0.0
            
            # Calculate all indicators
            rsi = calc_rsi(close)
            atr14 = calc_atr(high, low, close)
            ema20 = calc_ema(close, 20)
            ema50 = calc_ema(close, 50)
            ema200 = calc_ema(close, 200)
            adx = calc_adx(high, low, close)
            
            return {
                "rsi": round(rsi, 2),
                "adx": round(adx, 2),
                "atr14": round(atr14, 5),
                "ema20": round(ema20, 5),
                "ema50": round(ema50, 5),
                "ema200": round(ema200, 5),
            }
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}", exc_info=True)
            return {
                "rsi": 50.0,
                "adx": 0.0,
                "atr14": 0.0,
                "ema20": 0.0,
                "ema50": 0.0,
                "ema200": 0.0,
            }
    
    def _fallback_snapshot(self, symbol: str, timeframe: int) -> dict:
        df = self._fetch_df(symbol, timeframe, 200)
        if df is None or df.empty:
            raise RuntimeError(f"No MT5 data for {symbol} tf={timeframe}")
        
        # Reset index to get time column
        df_reset = df.reset_index()
        
        # Calculate indicators
        indicators = self._calculate_indicators(df)
        
        # Return OHLCV arrays + indicators
        result = {
            "time": df_reset["time"].astype(np.int64) // 10**9,  # Convert to Unix timestamp
            "open": df_reset["open"].tolist(),
            "high": df_reset["high"].tolist(),
            "low": df_reset["low"].tolist(),
            "close": df_reset["close"].tolist(),
            "volume": df_reset["volume"].tolist(),
        }
        
        # Add calculated indicators
        result.update(indicators)
        
        # Add current OHLC values (last candle)
        if len(df_reset) > 0:
            last = df_reset.iloc[-1]
            result["current_close"] = float(last["close"])
            result["current_open"] = float(last["open"])
            result["current_high"] = float(last["high"])
            result["current_low"] = float(last["low"])
        
        return result

    def get_multi(self, symbol: str) -> dict:
        self.request_snapshot(symbol, ["M5", "M15", "M30", "H1", "H4"])
        snap = self.load_snapshot(symbol, wait_seconds=2.5)
        out: dict[str, dict] = {}
        if snap and isinstance(snap, dict):
            for k in ("M5", "M15", "M30", "H1", "H4"):
                if isinstance(snap.get(k), dict):
                    out[k] = snap[k]
        if "M5" not in out:
            out["M5"] = self._fallback_snapshot(symbol, mt5.TIMEFRAME_M5)
        if "M15" not in out:
            out["M15"] = self._fallback_snapshot(symbol, mt5.TIMEFRAME_M15)
        if "M30" not in out:
            out["M30"] = self._fallback_snapshot(symbol, mt5.TIMEFRAME_M30)
        if "H1" not in out:
            out["H1"] = self._fallback_snapshot(symbol, mt5.TIMEFRAME_H1)
        if "H4" not in out:
            out["H4"] = self._fallback_snapshot(symbol, mt5.TIMEFRAME_H4)
        return out

    def get_feature_builder_data(self, symbol: str) -> dict:
        """
        IMPROVED: Get data in format suitable for feature builder.
        Returns multi-timeframe data with proper OHLCV structure.
        """
        try:
            # Get multi-timeframe data
            multi = self.get_multi(symbol)
            
            # Convert to feature builder format
            feature_data = {}
            for tf, data in multi.items():
                if isinstance(data, dict):
                    # Convert to OHLCV arrays for feature builder
                    feature_data[tf] = {
                        "time": data.get("times", []),
                        "open": data.get("opens", []),
                        "high": data.get("highs", []),
                        "low": data.get("lows", []),
                        "close": data.get("closes", []),
                        "volume": data.get("volumes", [])
                    }
            
            return feature_data
            
        except Exception as e:
            logger.error(f"Feature builder data conversion failed for {symbol}: {e}")
            return {}


# ---- Phase-4: augmentation for mean_kind 'VWAP' and 'Pivot' ----
def _compute_vwap_from_blob(self, blob: dict) -> float | None:
    try:
        closes = blob.get("closes") or blob.get("close")
        highs  = blob.get("highs")  or blob.get("high")
        lows   = blob.get("lows")   or blob.get("low")
        vols   = blob.get("volumes") or blob.get("volume")
        times  = blob.get("times")  or blob.get("time")
        if not (isinstance(closes, (list, tuple)) and isinstance(highs, (list, tuple)) and isinstance(lows, (list, tuple))):
            return None
        n = min(len(closes), len(highs), len(lows))
        if n < 5:
            return None
        # typical price
        tp = [(float(highs[i]) + float(lows[i]) + float(closes[i])) / 3.0 for i in range(n)]
        if isinstance(vols, (list, tuple)) and len(vols) >= n:
            cum_pv = 0.0
            cum_v  = 0.0
            for i in range(n):
                v = float(vols[i]) if vols[i] is not None else 0.0
                cum_pv += tp[i] * v
                cum_v  += v
            if cum_v > 0:
                return cum_pv / cum_v
        # Fallback: simple average of typical price (no volume)
        return float(sum(tp) / len(tp))
    except Exception:
        return None

def _compute_daily_pivots_from_blob(self, blob_m15: dict) -> dict | None:
    """Classic floor pivots from previous day's H/L/C aggregated from M15 data."""
    try:
        closes = blob_m15.get("closes") or blob_m15.get("close")
        highs  = blob_m15.get("highs")  or blob_m15.get("high")
        lows   = blob_m15.get("lows")   or blob_m15.get("low")
        times  = blob_m15.get("times")  or blob_m15.get("time")
        if not (isinstance(closes, (list, tuple)) and isinstance(highs, (list, tuple)) and isinstance(lows, (list, tuple)) and isinstance(times, (list, tuple))):
            return None
        import datetime as _dt
        # Group by date (UTC) and take last two dates
        buckets = {}
        for i in range(min(len(closes), len(highs), len(lows), len(times))):
            t = int(times[i]) if times[i] is not None else None
            if t is None:
                continue
            d = _dt.datetime.utcfromtimestamp(t).date()
            b = buckets.setdefault(d, {"high": -1e18, "low": 1e18, "close": None})
            h = float(highs[i]); l = float(lows[i]); c = float(closes[i])
            if h > b["high"]: b["high"] = h
            if l < b["low"]:  b["low"] = l
            b["close"] = c  # last close of the day
        if len(buckets) < 2:
            return None
        days = sorted(buckets.keys())
        prev = buckets[days[-2]]
        H, L, C = float(prev["high"]), float(prev["low"]), float(prev["close"])
        P  = (H + L + C) / 3.0
        R1 = 2*P - L
        S1 = 2*P - H
        R2 = P + (H - L)
        S2 = P - (H - L)
        return {"pivot": P, "r1": R1, "s1": S1, "r2": R2, "s2": S2}
    except Exception:
        return None

def _augment_means(self, out: dict) -> None:
    """Add 'vwap' and 'pivot/r1/s1/r2/s2' to timeframes if data is available."""
    try:
        m15 = out.get("M15") or out.get("_tf_M15")
        if isinstance(m15, dict):
            piv = self._compute_daily_pivots_from_blob(m15)
            if piv:
                m15.update(piv)
        for tf in ("M5", "M15", "H1"):
            blob = out.get(tf) or out.get(f"_tf_{tf}")
            if isinstance(blob, dict):
                vwap = self._compute_vwap_from_blob(blob)
                if vwap is not None:
                    blob["vwap"] = float(vwap)
    except Exception:
        pass
