# File: technical_analysis_fixed.py
# --------------------------
# Fixed version that uses direct MT5 calls instead of file-based system
# No longer depends on TG_IndicatorBridge.mq5 EA

from __future__ import annotations
import logging
from typing import Optional, Dict, Any
import MetaTrader5 as mt5
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TechnicalAnalysis:
    def __init__(self, common_files_dir=None):
        # We don't need the common_files_dir for direct MT5 calls
        self.mt5_connected = False
        self._ensure_mt5_connection()

    def _ensure_mt5_connection(self):
        """Ensure MT5 is connected"""
        if not self.mt5_connected:
            if not mt5.initialize():
                logger.error("Failed to initialize MT5")
                return False
            self.mt5_connected = True
        return True

    def request_snapshot(self, symbol: str, timeframes: list[str]) -> None:
        """No-op for compatibility - we use direct MT5 calls now"""
        pass

    def load_snapshot(self, symbol: str, wait_seconds: float = 2.5) -> Optional[Dict[str, Any]]:
        """No-op for compatibility - we use direct MT5 calls now"""
        return None

    def _fetch_df(self, symbol: str, timeframe: int, bars: int = 400) -> Optional[pd.DataFrame]:
        """Get OHLCV data directly from MT5"""
        try:
            if not self._ensure_mt5_connection():
                return None
                
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
            if rates is None or len(rates) == 0:
                logger.warning(f"No rates data for {symbol} timeframe {timeframe}")
                return None
                
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df = df.rename(columns={"tick_volume": "volume"})
            df = df[["time", "open", "high", "low", "close", "volume"]].set_index("time")
            return df
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}", exc_info=True)
            return None

    def _fallback_snapshot(self, symbol: str, timeframe: int) -> dict:
        """Calculate indicators directly from MT5 data"""
        try:
            df = self._fetch_df(symbol, timeframe, 200)
            if df is None or df.empty:
                logger.error(f"No MT5 data for {symbol} tf={timeframe}")
                return self._empty_snapshot()

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

            # RSI
            rsi = self._calculate_rsi(df["close"])

            # MACD
            macd_line, macd_signal, macd_hist = self._calculate_macd(df["close"])

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
                "open": float(df["open"].iloc[-1]),
                "high": float(df["high"].iloc[-1]),
                "low": float(df["low"].iloc[-1]),
                "ema_20": float(ema20),
                "ema_50": float(ema50),
                "ema_200": float(ema200),
                "atr_14": float(atr14),
                "adx": float(adx),
                "rsi": float(rsi),
                "macd": float(macd_line),
                "macd_signal": float(macd_signal),
                "macd_histogram": float(macd_hist),
                "bb_upper": float(bb_upper),
                "bb_middle": float(ma20),
                "bb_lower": float(bb_lower),
                "bb_width": float(bbw) if bbw is not None else None,
                "regime": regime,
                "volume": float(df["volume"].iloc[-1]),
                "current_close": float(close),
                "current_high": float(df["high"].iloc[-1]),
                "current_low": float(df["low"].iloc[-1]),
                "current_open": float(df["open"].iloc[-1])
            }
        except Exception as e:
            logger.error(f"Error in _fallback_snapshot for {symbol}: {e}", exc_info=True)
            return self._empty_snapshot()

    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> float:
        """Calculate RSI"""
        try:
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi.iloc[-1])
        except:
            return 50.0

    def _calculate_macd(self, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """Calculate MACD"""
        try:
            ema_fast = close.ewm(span=fast).mean()
            ema_slow = close.ewm(span=slow).mean()
            macd_line = ema_fast - ema_slow
            macd_signal = macd_line.ewm(span=signal).mean()
            macd_histogram = macd_line - macd_signal
            return macd_line, macd_signal, macd_histogram
        except:
            return pd.Series([0]), pd.Series([0]), pd.Series([0])

    def _empty_snapshot(self) -> dict:
        """Return empty snapshot when data is not available"""
        return {
            "close": 0.0,
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "ema_20": 0.0,
            "ema_50": 0.0,
            "ema_200": 0.0,
            "atr_14": 0.0,
            "adx": 0.0,
            "rsi": 50.0,
            "macd": 0.0,
            "macd_signal": 0.0,
            "macd_histogram": 0.0,
            "bb_upper": 0.0,
            "bb_middle": 0.0,
            "bb_lower": 0.0,
            "bb_width": None,
            "regime": "UNKNOWN",
            "volume": 0.0,
            "current_close": 0.0,
            "current_high": 0.0,
            "current_low": 0.0,
            "current_open": 0.0
        }

    def get_tf(self, symbol: str, tf_name: str, tf_const: int) -> dict:
        """Get single timeframe data directly from MT5"""
        try:
            return self._fallback_snapshot(symbol, tf_const)
        except Exception as e:
            logger.error(f"Error getting {tf_name} for {symbol}: {e}", exc_info=True)
            return self._empty_snapshot()

    def get_multi(self, symbol: str) -> dict:
        """Get multi-timeframe data directly from MT5"""
        try:
            if not self._ensure_mt5_connection():
                return {}

            # Ensure symbol is available
            if not mt5.symbol_select(symbol, True):
                logger.warning(f"Symbol {symbol} not available in MT5")
                return {}

            out: dict[str, dict] = {}

            # Get data for each timeframe
            timeframes = {
                "M5": mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15,
                "M30": mt5.TIMEFRAME_M30,
                "H1": mt5.TIMEFRAME_H1,
                "H4": mt5.TIMEFRAME_H4
            }

            for tf_name, tf_const in timeframes.items():
                try:
                    tf_data = self._fallback_snapshot(symbol, tf_const)
                    if tf_data:
                        out[tf_name] = tf_data
                except Exception as e:
                    logger.error(f"Error getting {tf_name} for {symbol}: {e}")
                    continue

            return out

        except Exception as e:
            logger.error(f"Error in get_multi for {symbol}: {e}", exc_info=True)
            return {}
