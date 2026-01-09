# =====================================
# infra/position_watcher.py
# =====================================
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from domain.candle_stats import compute_candle_stats

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from config import settings
from infra.mt5_service import MT5Service  # <-- resolves type/name

# Bring in IndicatorBridge for multi-timeframe technical analysis. We avoid
# importing it at top level in environments without MT5 files, but if it's
# available we'll use it to sanity-check existing trades. Note: this import
# resides here rather than above to minimise circular dependencies.
try:
    from infra.indicator_bridge import IndicatorBridge  # type: ignore
except Exception:
    IndicatorBridge = None  # fallback if unavailable

logger = logging.getLogger(__name__)

# Try to use your dedicated regime classifier if available
try:
    # Expect a function that returns one of {"TREND","RANGE","VOLATILE"} given a DataFrame or (symbol, tf)
    from utils.market_regime import detect_market_regime as _external_detect_regime  # type: ignore
except Exception:  # pragma: no cover
    _external_detect_regime = None

# ---- numeric safety helpers -------------------------------------------------
_EPS = 1e-12


def _safe_div(a, b, fill: float = 0.0):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.true_divide(a, b)
        out[~np.isfinite(out)] = fill
    return out


@dataclass
class ManagedState:
    # Wick-based exit bookkeeping
    wick_stack: int = 0
    last_wick_ts: int = 0
    # Bookkeeping for automation
    tp1_done: bool = False
    be_done: bool = False
    tp2_done: bool = False
    last_sl: Optional[float] = None
    last_trail_ts: int = 0

    # Risk baseline (stable R math)
    base_entry: Optional[float] = None
    base_sl: Optional[float] = None
    base_volume: Optional[float] = None
    opened_ts: Optional[int] = None  # broker position time (epoch seconds)

    # Regime awareness (mid-trade adapt)
    current_regime: Optional[str] = None  # "TREND" | "RANGE" | "VOLATILE"
    last_regime_check_ts: int = 0
    regime_candidate: Optional[str] = None  # temp detection waiting for confirmation
    regime_streak: int = 0  # consecutive confirmations
    last_mode_switch_ts: int = 0  # hysteresis: avoid flapping

    # Adaptive TP
    tp_extended: bool = False  # once-off extension in strong trend/vol
    tp_tightened: bool = False  # once-off tighten in range
    last_tp: Optional[float] = None

    # Pyramiding bookkeeping (R thresholds that have been hit/used)
    pyr_done_steps: List[float] = field(default_factory=list)


class PositionWatcher:
    """
    Manages open positions:
      • TP1 partial close + move SL to BE(+buffer)
      • Trailing SL (ATR / Chandelier / R / Hybrid)
      • Time-based exit backstop
      • Mid-trade regime re-checks with hysteresis (AUTO trail mode)
      • Adaptive TP by regime (optional)
      • Optional pyramiding at +R steps with drawdown-aware risk scaling
      • Journal every action with reason codes
      • *NEW*: Multi-timeframe technical analysis to exit trades when the
        market regime flips or the original strategy no longer holds.
    """

    def __init__(self, store_path: str):
        self.path = Path(store_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ticket_to_chat: Dict[str, int] = {}
        self.ticket_meta: Dict[str, Dict] = {}
        self.tickets: Dict[str, ManagedState] = {}
        self._load()

        # Initialise a technical analysis helper if available. This helper
        # returns multi-timeframe indicator snapshots (EMA20/50/200, ATR, etc.)
        # so we can cross-check whether an open position still aligns with
        # prevailing trends. If the import failed above, self.ta will be None.
        self.ta = None
        try:
            if IndicatorBridge is not None:
                # settings.MT5_FILES_DIR holds the Common\Files path for MT5 EAs
                self.ta = IndicatorBridge(settings.MT5_FILES_DIR)
        except Exception:
            # Avoid hard failure if IndicatorBridge cannot be constructed
            self.ta = None

    # ------------- persistence -------------
    def _load(self):
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text())
                self.ticket_to_chat = data.get("ticket_to_chat", {}) or {}
                self.ticket_meta = data.get("ticket_meta", {}) or {}
                raw = data.get("tickets", {}) or {}
                out: Dict[str, ManagedState] = {}
                for k, v in raw.items():
                    st = ManagedState(**{**ManagedState().__dict__, **v})
                    out[str(k)] = st
                self.tickets = out
        except Exception:
            logger.debug("PositionWatcher failed to load state.", exc_info=True)

    # === ANCHOR: PW_NOTIFY_HELPERS_START ===
    def _should_notify(self, pos_id: str, now_ts: float, throttle_sec: int) -> bool:
        last = getattr(self, "_last_notify", {}).get(pos_id, 0)
        if (now_ts - last) >= throttle_sec:
            return True
        return False

    def _mark_notified(self, pos_id: str, now_ts: float):
        if not hasattr(self, "_last_notify"):
            self._last_notify = {}
        self._last_notify[pos_id] = now_ts

    def _notify_event(self, notifier, chat_id: int | None, text: str, pos_id: str):
        if not notifier or not chat_id:
            return
        try:
            notifier(chat_id, text)
        except Exception:
            import logging

            logging.getLogger(__name__).debug("poswatch notifier failed", exc_info=True)
        # === ANCHOR: PW_NOTIFY_HELPERS_END ===

    def _save(self):
        try:
            data = {
                "ticket_to_chat": self.ticket_to_chat,
                "ticket_meta": self.ticket_meta,
                "tickets": {k: asdict(v) for k, v in self.tickets.items()},
            }
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2))
            tmp.replace(self.path)
        except Exception:
            logger.debug("PositionWatcher failed to save state.", exc_info=True)

    # Public: allow handlers to register chats for position notifications
    def register_ticket_chat(self, ticket: int, chat_id: int):
        self.ticket_to_chat[str(int(ticket))] = int(chat_id)
        self._save()

    # ------------- helpers -------------
    @staticmethod
    def _round(price: float, digits: int) -> float:
        fmt = "{:0." + str(int(max(0, digits))) + "f}"
        return float(fmt.format(price))

    @staticmethod
    def _position_side_name(pos_type: int) -> str:
        return "BUY" if int(pos_type) == mt5.POSITION_TYPE_BUY else "SELL"

    def _modify_sl_tp(
        self,
        mt5svc: MT5Service,
        *,
        ticket: int,
        symbol: str,
        new_sl: Optional[float] = None,
        new_tp: Optional[float] = None,
    ) -> bool:
        res = mt5svc.modify_position_sl_tp(ticket, symbol=symbol, sl=new_sl, tp=new_tp)
        ok = bool(res and res.get("ok"))
        if not ok:
            logger.debug("modify_position_sl_tp failed: %s", res)
        return ok

    def _partial_close(self, mt5svc: MT5Service, pos, volume: float) -> bool:
        side = self._position_side_name(pos.type)
        res = mt5svc.close_position_partial(
            pos.ticket, volume, symbol=pos.symbol, side=side
        )
        ok = bool(res and res.get("ok"))
        if not ok:
            logger.debug("close_position_partial failed: %s", res)
        return ok

    @staticmethod
    def _tf_to_mt5(tf: str) -> int:
        t = (tf or "").upper()
        return {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
        }.get(t, mt5.TIMEFRAME_M15)

    @staticmethod
    def _tf_seconds(tf: str) -> int:
        t = (tf or "").upper()
        return {
            "M1": 60,
            "M5": 300,
            "M15": 900,
            "M30": 1800,
            "H1": 3600,
            "H4": 14400,
        }.get(t, 900)

    def _fetch_df(
        self,
        symbol: str,
        timeframe: int,
        bars: int = 400,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch candlestick data with streamer integration.
        Tries streamer first (fast, RAM-based), falls back to direct MT5.
        """
        # Map timeframe int to string
        tf_map = {
            mt5.TIMEFRAME_M1: "M1",
            mt5.TIMEFRAME_M5: "M5",
            mt5.TIMEFRAME_M15: "M15",
            mt5.TIMEFRAME_M30: "M30",
            mt5.TIMEFRAME_H1: "H1",
            mt5.TIMEFRAME_H4: "H4"
        }
        
        tf_string = tf_map.get(timeframe)
        
        # Try streamer if available and timeframe is supported
        if tf_string:
            try:
                from infra.streamer_data_access import get_candles
                candles = get_candles(symbol, tf_string, limit=bars)
                
                if candles and len(candles) > 0:
                    # Convert to DataFrame format
                    df = pd.DataFrame(candles)
                    df["time"] = pd.to_datetime(df["time"])
                    # Reverse to chronological order (oldest first) - streamer returns newest first
                    if len(df) > 1:
                        # Check if we need to reverse (newest first -> oldest first)
                        first_time = df.iloc[0]["time"]
                        last_time = df.iloc[-1]["time"]
                        if first_time > last_time:
                            # Streamer returns newest first, reverse to oldest first
                            df = df.iloc[::-1].reset_index(drop=True)
                    df = df.set_index("time")
                    # Ensure volume column exists
                    if "volume" not in df.columns:
                        df["volume"] = 0
                    logger.debug(f"Fetched {len(df)} {tf_string} candles for {symbol} from streamer")
                    return df[["open", "high", "low", "close", "volume"]]
            except Exception as e:
                logger.debug(f"Streamer fetch failed for {symbol} {tf_string}, using MT5: {e}")
        
        # Fallback to direct MT5
        # Ensure MT5 is initialized
        if not mt5.initialize():
            logger.warning(f"MT5 initialization failed, cannot fetch {symbol} {tf_string}")
            return None
        
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})
        return df[["time", "open", "high", "low", "close", "volume"]].set_index("time")

    # --- indicators (no TA-Lib dependency) ---
    def _atr(self, symbol: str, timeframe: int, period: int = 14) -> Optional[float]:
        """
        Calculate ATR with streamer integration.
        Tries streamer ATR calculation first (fast), falls back to manual calculation.
        """
        # Map timeframe int to string
        tf_map = {
            mt5.TIMEFRAME_M1: "M1",
            mt5.TIMEFRAME_M5: "M5",
            mt5.TIMEFRAME_M15: "M15",
            mt5.TIMEFRAME_M30: "M30",
            mt5.TIMEFRAME_H1: "H1",
            mt5.TIMEFRAME_H4: "H4"
        }
        
        tf_string = tf_map.get(timeframe)
        
        # Try streamer ATR calculation if available
        if tf_string:
            try:
                from infra.streamer_data_access import calculate_atr
                atr = calculate_atr(symbol, tf_string, period=period)
                if atr:
                    logger.debug(f"ATR for {symbol} {tf_string}: {atr:.2f} (from streamer)")
                    return atr
            except Exception as e:
                logger.debug(f"Streamer ATR calculation failed for {symbol} {tf_string}, using manual: {e}")
        
        # Fallback to manual calculation
        df = self._fetch_df(symbol, timeframe, bars=max(200, period * 4))
        if df is None or len(df) < period + 2:
            return None
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        prev_close = np.roll(close, 1)
        tr = np.maximum(
            high - low,
            np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
        )
        tr[0] = high[0] - low[0]
        atr = pd.Series(tr).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
        return float(atr)

    def _ema(self, series: pd.Series, period: int) -> pd.Series:
        return series.ewm(alpha=2 / (period + 1), adjust=False).mean()

    def _bollinger_width_frac(
        self,
        close: pd.Series,
        period: int = 20,
    ) -> Optional[float]:
        if len(close) < period + 2:
            return None
        ma = close.rolling(period).mean()
        sd = close.rolling(period).std(ddof=0)
        upper = ma + 2 * sd
        lower = ma - 2 * sd
        width = upper.iloc[-1] - lower.iloc[-1]
        denom = close.iloc[-1] if close.iloc[-1] != 0 else np.nan
        if pd.isna(width) or pd.isna(denom):
            return None
        return float(width / denom)

    def _adx(self, df: pd.DataFrame, period: int = 14) -> Optional[float]:
        """
        Wilder's ADX with numerically-safe division to avoid NaN/Inf warnings.
        """
        if len(df) < period + 2:
            return None

        high = df["high"].to_numpy(dtype=float)
        low = df["low"].to_numpy(dtype=float)
        close = df["close"].to_numpy(dtype=float)

        # Directional movement (length N-1)
        up_move = high[1:] - high[:-1]
        dn_move = low[:-1] - low[1:]

        plus_dm = np.where((up_move > dn_move) & (up_move > 0.0), up_move, 0.0)
        minus_dm = np.where((dn_move > up_move) & (dn_move > 0.0), dn_move, 0.0)

        # True range (length N-1)
        prev_close = close[:-1]
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - prev_close)
        tr3 = np.abs(low[1:] - prev_close)
        tr = np.maximum(tr1, np.maximum(tr2, tr3))

        # Not enough data to smooth
        if len(tr) < period:
            return None

        # Wilder smoothing
        def wilder_smooth(arr: np.ndarray, n: int) -> np.ndarray:
            arr = np.asarray(arr, dtype=float)
            out = np.zeros_like(arr)
            out[n - 1] = np.nansum(arr[:n])
            for i in range(n, len(arr)):
                out[i] = out[i - 1] - (out[i - 1] / n) + arr[i]
            return out

        tr_n = wilder_smooth(tr, period)
        plus_dm_n = wilder_smooth(plus_dm, period)
        minus_dm_n = wilder_smooth(minus_dm, period)

        # Guard zero TR to prevent divide-by-zero
        tr_n = np.where(tr_n <= _EPS, np.nan, tr_n)

        # DI and DX with safe division
        plus_di = 100.0 * _safe_div(plus_dm_n, tr_n, fill=0.0)
        minus_di = 100.0 * _safe_div(minus_dm_n, tr_n, fill=0.0)
        dx = 100.0 * _safe_div(
            np.abs(plus_di - minus_di), (plus_di + minus_di), fill=0.0
        )

        # ADX smoothing (seed + Wilder)
        if len(dx) < (2 * period - 1):
            return None

        adx = np.full_like(dx, np.nan)
        seed = np.nanmean(dx[:period])
        adx[period - 1] = 0.0 if not np.isfinite(seed) else seed
        for i in range(period, len(dx)):
            adx[i] = ((adx[i - 1] * (period - 1)) + dx[i]) / period

        # Final value, cleaned
        val = adx[-1]
        if not np.isfinite(val):
            val = 0.0
        return float(val)

    # --- regime detection ---
    def _detect_regime(self, symbol: str, tf_str: str) -> Optional[str]:
        """
        Use external detector if present, else a simple classifier:
          - TREND if ADX >= ADX_TREND && |EMA50 slope| >= EMA_SLOPE_THR
          - RANGE if BB width <= BB_RANGE_THR && ADX < ADX_RANGE
          - otherwise VOLATILE
        """
        timeframe = self._tf_to_mt5(tf_str)
        df = self._fetch_df(symbol, timeframe, bars=300)
        if df is None or len(df) < 60:
            return None

        if _external_detect_regime:
            try:
                return str(_external_detect_regime(df)).upper()
            except Exception:  # pragma: no cover
                logger.debug(
                    "External regime detector failed; using fallback.",
                    exc_info=True,
                )

        adx = (
            self._adx(df, period=int(getattr(settings, "POS_REGIME_ADX_PERIOD", 14)))
            or 0.0
        )
        bb_width = (
            self._bollinger_width_frac(
                df["close"],
                period=int(getattr(settings, "POS_REGIME_BB_PERIOD", 20)),
            )
            or 0.0
        )
        ema = self._ema(
            df["close"], period=int(getattr(settings, "POS_REGIME_EMA_PERIOD", 50))
        )
        slope_bars = int(getattr(settings, "POS_REGIME_EMA_SLOPE_BARS", 10))
        if len(ema) < slope_bars + 2:
            return None
        slope = float(ema.iloc[-1] - ema.iloc[-1 - slope_bars])
        slope_pct = abs(slope / (df["close"].iloc[-1] or 1.0))

        adx_trend = float(getattr(settings, "POS_REGIME_ADX_TREND", 25.0))
        adx_range = float(getattr(settings, "POS_REGIME_ADX_RANGE", 20.0))
        slope_thr = float(
            getattr(settings, "POS_REGIME_EMA_SLOPE_THR", 0.0015)
        )  # 0.15%
        bb_range_thr = float(
            getattr(settings, "POS_REGIME_BB_RANGE_THR", 0.0040)
        )  # 0.4%

        if adx >= adx_trend and slope_pct >= slope_thr:
            return "TREND"
        if bb_width <= bb_range_thr and adx < adx_range:
            return "RANGE"
        return "VOLATILE"

    def _highest_lowest(
        self,
        symbol: str,
        timeframe: int,
        lookback: int,
    ) -> Optional[Tuple[float, float]]:
        df = self._fetch_df(symbol, timeframe, bars=max(200, lookback + 5))
        if df is None or len(df) < lookback:
            return None
        hh = float(df["high"].iloc[-lookback:].max())
        ll = float(df["low"].iloc[-lookback:].min())
        return hh, ll

    def _compute_chandelier(
        self,
        symbol: str,
        is_buy: bool,
        *,
        tf_str: str,
        period: int,
        mult: float,
        atr_period: int,
    ) -> Optional[float]:
        timeframe = self._tf_to_mt5(tf_str)
        hl = self._highest_lowest(symbol, timeframe, lookback=period)
        if not hl:
            return None
        atr = self._atr(symbol, timeframe, period=atr_period)
        if atr is None:
            return None
        hh, ll = hl
        if is_buy:
            return hh - mult * atr
        return ll + mult * atr

    def _decide_trail_mode(self, regime: Optional[str]) -> str:
        """
        Returns one of: "ATR", "CHAND", "HYBRID_MAX", "HYBRID_MIN", "R"
        If settings.POS_TRAIL_MODE == "AUTO", map from regime using *_AUTO_* settings.
        """
        cfg = str(getattr(settings, "POS_TRAIL_MODE", "ATR")).upper()
        if cfg == "AUTO":
            rg = (regime or "").upper()
            if rg == "TREND":
                return str(
                    getattr(settings, "POS_AUTO_TRAIL_TREND", "HYBRID_MAX")
                ).upper()
            if rg == "RANGE":
                return str(getattr(settings, "POS_AUTO_TRAIL_RANGE", "R")).upper()
            # VOLATILE / default
            return str(getattr(settings, "POS_AUTO_TRAIL_VOL", "HYBRID_MAX")).upper()
        # Forced mode
        if cfg in {"ATR", "CHAND", "HYBRID_MAX", "HYBRID_MIN", "R"}:
            return cfg
        return "ATR"

    # ---- journal helper ------------------------------------------------------

    def _journal(self, journal_repo: Any, event: str, payload: Dict[str, Any]):
        """
        Try several method names so we play nicely with your JournalRepo.
        payload should be flat JSON-serialisable (we'll stringify anything weird).
        """
        try:
            if not journal_repo:
                return
            data = {
                k: (str(v) if isinstance(v, (pd.Timestamp,)) else v)
                for k, v in (payload or {}).items()
            }

            # >>> ADD: ensure `side` binding exists when JournalRepo expects it
            if not data.get("side"):
                # prefer the current position context, else map from direction/dir
                ctx_side = getattr(self, "_last_side_ctx", None)
                if ctx_side:
                    data["side"] = ctx_side
                else:
                    maybe = data.get("direction") or data.get("dir") or ""
                    data["side"] = str(maybe).lower() or None
            # <<<

            for method in ("add_event", "log_event", "add", "write_event"):
                if hasattr(journal_repo, method):
                    getattr(journal_repo, method)(event=event, **data)
                    return
            if hasattr(journal_repo, "write"):
                journal_repo.write({"event": event, **data})
        except Exception:
            logger.debug("Journal write failed for %s", event, exc_info=True)

    # ---------- drawdown-aware risk helper ----------
    @staticmethod
    def _scale_by_drawdown(
        journal_repo: Any,
        base_risk_pct: float,
    ) -> Tuple[float, dict]:
        """
        Returns (scaled_pct, info). Falls back to base on any issue.
        info contains {'factor', 'max_dd_pct', ...}
        """
        try:
            lookback = int(getattr(settings, "RISK_DD_LOOKBACK_DAYS", 180))
            if journal_repo is None or not hasattr(
                journal_repo, "risk_scale_from_drawdown"
            ):
                return float(base_risk_pct), {"factor": 1.0, "max_dd_pct": 0.0}
            factor, info = journal_repo.risk_scale_from_drawdown(lookback_days=lookback)
            scaled = max(0.01, float(base_risk_pct) * float(factor))
            return float(scaled), {"factor": float(factor), **info}
        except Exception:
            return float(base_risk_pct), {"factor": 1.0, "max_dd_pct": 0.0}

        # ------------- core logic -------------

    def poll_once(
        self,
        mt5svc,
        journal_repo=None,
        notifier=None,
        poswatch=None,
        circuit=None,
        default_chat_id: int | None = None,
    ):
        # === ANCHOR: PW_NOTIFY_SETTINGS_LOAD_START ===
        from config import settings as _settings

        notify_on = set(getattr(_settings, "POS_WATCH_NOTIFY_EVENTS", set()))
        notify_enabled = bool(getattr(_settings, "POS_WATCH_NOTIFY", True))
        throttle_sec = int(getattr(_settings, "POS_WATCH_NOTIFY_THROTTLE_SEC", 30))
        # === ANCHOR: PW_NOTIFY_SETTINGS_LOAD_END ===

        """
        Evaluate all open positions and apply:
        1) TP1 partial close at +R
        2) Move SL to BE(+buffer) at +R
        3) Trailing stop (ATR / Chandelier / R / Hybrid)
        4) Time-based exit backstop
        5) Mid-trade regime re-check (AUTO trail) with hysteresis
        6) Adaptive TP by regime (optional)
        7) Optional pyramiding at +R steps using drawdown-aware risk
        8) Journal every action
        9) *NEW*: Technical-analysis based exit of trades whose direction is no longer supported
        """
        try:
            if not bool(getattr(settings, "POS_WATCH_ENABLE", True)):
                return

            # --- knobs ---
            tp1_r = float(getattr(settings, "POS_TP1_R", 1.0))
            tp1_part = float(getattr(settings, "POS_TP1_PART_CLOSE", 0.5))
            be_enable = bool(getattr(settings, "POS_BE_ENABLE", True))
            tp2_r = float(getattr(settings, "POS_TP2_R", 2.0))
            tp2_part = float(getattr(settings, "POS_TP2_PART_CLOSE", 0.4))
            exit_min_remainder = float(getattr(settings, "POS_EXIT_MIN_REMAINDER", 0.1))
            be_buffer_pct = float(getattr(settings, "POS_BE_BUFFER_PCT", 0.0))

            trail_throttle_sec = int(getattr(settings, "POS_TRAIL_THROTTLE_SEC", 5))
            atr_tf = str(getattr(settings, "POS_TRAIL_ATR_TF", "M5"))
            atr_mult = float(getattr(settings, "POS_TRAIL_ATR_MULT", 1.5))
            atr_period = int(getattr(settings, "POS_TRAIL_ATR_PERIOD", 14))
            chand_period = int(getattr(settings, "POS_CHAND_PERIOD", 22))
            chand_mult = float(getattr(settings, "POS_CHAND_MULT", 3.0))
            trail_dist_r = float(getattr(settings, "POS_TRAIL_DIST_R", 0.75))

            # Session-specific overrides for BE buffer and ATR multiplier
            # Use local timestamp to determine trading session (Africa/Johannesburg)
            try:
                from datetime import datetime

                sess = settings.get_trading_session(
                    datetime.now(), tz="Africa/Johannesburg"
                )
                if sess:
                    # Override BE buffer if specified
                    try:
                        ses_overrides = (
                            getattr(settings, "POS_BE_BUFFER_PCT_BY_SESSION", {}) or {}
                        )
                        v = ses_overrides.get(sess)
                        if v is not None:
                            be_buffer_pct = float(v)
                    except Exception:
                        pass
                    # Override ATR multiplier if specified
                    try:
                        ses_mults = (
                            getattr(settings, "POS_TRAIL_ATR_MULT_BY_SESSION", {}) or {}
                        )
                        v2 = ses_mults.get(sess)
                        if v2 is not None:
                            atr_mult = float(v2)
                    except Exception:
                        pass
            except Exception:
                # ignore session override errors
                pass

            tb_enable = bool(getattr(settings, "POS_TIME_BACKSTOP_ENABLE", True))
            tb_tf = str(getattr(settings, "POS_TIME_BACKSTOP_TF", "M15"))
            tb_bars = int(getattr(settings, "POS_TIME_BACKSTOP_BARS", 8))

            reeval_enable = bool(getattr(settings, "POS_REGIME_REEVAL_ENABLE", True))
            reeval_tf = str(getattr(settings, "POS_REGIME_REEVAL_TF", "M15"))
            reeval_every_sec = int(
                getattr(settings, "POS_REGIME_REEVAL_EVERY_SEC", 120)
            )
            reeval_confirm = int(getattr(settings, "POS_REGIME_CONFIRM_BARS", 2))
            reeval_min_switch_min = int(
                getattr(settings, "POS_REGIME_MIN_SWITCH_MIN", 10)
            )

            adapt_tp_enable = bool(getattr(settings, "POS_ADAPTIVE_TP_ENABLE", True))
            # Trend/Vol defaults
            tp_trend_r = float(getattr(settings, "POS_TP_TREND_R", 2.0))
            tp_trend_atr_mult = float(getattr(settings, "POS_TP_TREND_ATR_MULT", 2.0))
            tp_vol_r = float(getattr(settings, "POS_TP_VOL_R", 2.5))
            tp_vol_atr_mult = float(getattr(settings, "POS_TP_VOL_ATR_MULT", 2.5))
            # Range defaults
            tp_range_r = float(getattr(settings, "POS_TP_RANGE_R", 1.0))
            bb_period = int(getattr(settings, "POS_TP_RANGE_BB_PERIOD", 20))
            bb_offset_frac = float(getattr(settings, "POS_TP_RANGE_BB_OFFSET", 0.15))
            tp_only_extend = bool(getattr(settings, "POS_TP_ONLY_EXTEND", True))
            tp_allow_tighten_in_range = bool(
                getattr(settings, "POS_TP_ALLOW_TIGHTEN_IN_RANGE", True)
            )

            # Pyramiding knobs (all optional; off by default)
            pyr_enable = bool(getattr(settings, "POS_PYR_ENABLE", False))
            pyr_steps_csv = str(getattr(settings, "POS_PYR_STEPS_CSV", "1.0,2.0"))
            pyr_risk_pct = float(getattr(settings, "POS_PYR_RISK_PCT", 0.5))
            pyr_max_adds = int(getattr(settings, "POS_PYR_MAX_ADDS", 2))
            pyr_use_current_sl = bool(getattr(settings, "POS_PYR_USE_CURRENT_SL", True))

            # Parse R step list safely
            def _parse_steps(csv: str) -> List[float]:
                out: List[float] = []
                for tok in (csv or "").split(","):
                    tok = tok.strip()
                    if not tok:
                        continue
                    try:
                        out.append(float(tok))
                    except Exception:
                        pass
                # Ensure ascending, unique
                out = sorted(list({round(x, 4) for x in out}))
                return out

            pyr_steps = _parse_steps(pyr_steps_csv)

            now = int(time.time())
            positions = mt5.positions_get()
            if not positions:
                return

            for pos in positions:
                try:
                    ticket = int(pos.ticket)
                    ticket_str = str(ticket)
                    symbol = str(pos.symbol)
                    digits = int(getattr(mt5.symbol_info(symbol), "digits", 2))
                    side = self._position_side_name(pos.type)
                    is_buy = side == "BUY"
                    side_l = side.lower()
                    self._last_side_ctx = side_l

                    # --- init state ---
                    st = self.tickets.get(ticket_str)
                    if st is None:
                        meta = self.ticket_meta.get(ticket_str, {})
                        initial_regime = (
                            (meta.get("regime") or "").upper()
                            if isinstance(meta, dict)
                            else None
                        )
                        st = ManagedState(
                            tp1_done=False,
                            be_done=False,
                            tp2_done=False,
                            last_sl=float(pos.sl) if getattr(pos, "sl", 0.0) else None,
                            last_trail_ts=0,
                            base_entry=float(pos.price_open),
                            base_sl=float(pos.sl) if getattr(pos, "sl", 0.0) else None,
                            base_volume=float(pos.volume),
                            opened_ts=int(getattr(pos, "time", now)),
                            current_regime=initial_regime or None,
                            last_regime_check_ts=0,
                            regime_candidate=None,
                            regime_streak=0,
                            last_mode_switch_ts=now,
                            tp_extended=False,
                            tp_tightened=False,
                            last_tp=float(pos.tp) if getattr(pos, "tp", 0.0) else None,
                            pyr_done_steps=[],
                        )
                        self.tickets[ticket_str] = st
                        self._save()
                    else:
                        if st.base_entry is None:
                            st.base_entry = float(pos.price_open)
                        if st.opened_ts is None:
                            st.opened_ts = int(getattr(pos, "time", now))
                        if st.base_sl is None and getattr(pos, "sl", 0.0):
                            st.base_sl = float(pos.sl)
                        if getattr(st, "base_volume", None) is None:
                            st.base_volume = float(pos.volume)
                        if st.last_tp is None and getattr(pos, "tp", 0.0):
                            st.last_tp = float(pos.tp)
                        if st.current_regime is None:
                            meta = self.ticket_meta.get(ticket_str, {})
                            st.current_regime = (
                                (meta.get("regime") or "").upper()
                                if isinstance(meta, dict)
                                else None
                            )

                    # Fresh quote
                    q = mt5svc.get_quote(symbol)
                    price = q.bid if is_buy else q.ask

                    # --- R-multiple calc ---
                    r_multiple = None
                    if st.base_sl is not None and st.base_sl != 0.0:
                        risk_pts = (
                            (st.base_entry - st.base_sl)
                            if is_buy
                            else (st.base_sl - st.base_entry)
                        )
                        if risk_pts and risk_pts > 0:
                            pnl_pts = (
                                (price - st.base_entry)
                                if is_buy
                                else (st.base_entry - price)
                            )
                            r_multiple = pnl_pts / risk_pts

                    # ---------- TA-based exit (pre-management) ----------
                    if getattr(settings, "POS_TA_EXIT_ENABLE", False) and self.ta:
                        open_mins = (now - (st.opened_ts or now)) / 60.0
                        min_mins = float(getattr(settings, "POS_TA_MIN_MINUTES", 5))
                        if open_mins >= min_mins:
                            try:
                                ta_multi = self.ta.get_multi(symbol)
                                support = 0
                                reasons_list: List[str] = []
                                for tf_name, data in ta_multi.items():
                                    ema20 = data.get("ema_20")
                                    ema50 = data.get("ema_50")
                                    ema200 = data.get("ema_200")
                                    close_px = data.get("close")
                                    if None in (ema20, ema50, ema200, close_px):
                                        continue
                                    if is_buy:
                                        bullish = (ema20 > ema50 > ema200) and (
                                            close_px > ema20
                                        )
                                        if bullish:
                                            support += 1
                                        else:
                                            reasons_list.append(f"{tf_name} downtrend")
                                    else:
                                        bearish = (ema20 < ema50 < ema200) and (
                                            close_px < ema20
                                        )
                                        if bearish:
                                            support += 1
                                        else:
                                            reasons_list.append(f"{tf_name} uptrend")
                                total_tf = len(ta_multi)
                                min_support = int(
                                    getattr(settings, "POS_TA_MIN_SUPPORT_TFS", 2)
                                )
                                if support < min_support and total_tf > 0:
                                    vol_to_close = float(pos.volume)
                                    if vol_to_close > 0 and self._partial_close(
                                        mt5svc, pos, vol_to_close
                                    ):
                                        if ticket_str in self.tickets:
                                            del self.tickets[ticket_str]
                                            self._save()
                                        self._journal(
                                            journal_repo,
                                            "ta_exit",
                                            dict(
                                                ticket=ticket,
                                                symbol=symbol,
                                                side=side,
                                                support=support,
                                                required=min_support,
                                                tf_count=total_tf,
                                                reasons=",".join(reasons_list),
                                                open_minutes=open_mins,
                                                ts=now,
                                            ),
                                        )
                                        # Map TA exit -> close_by_rule notify
                                        # === ANCHOR: PW_NOTIFY_ACTION_CLOSE ===
                                        if notify_enabled and (
                                            "close_by_rule" in notify_on
                                        ):
                                            pos_id = str(ticket)
                                            now_ts = time.time()
                                            if self._should_notify(
                                                pos_id, now_ts, throttle_sec
                                            ):
                                                ch = (
                                                    self.ticket_to_chat.get(ticket_str)
                                                    or default_chat_id
                                                )
                                                note_reason = ", ".join(reasons_list)
                                                txt = (
                                                    f"🛑 Position closed by rule: {symbol} #{pos_id}\n"
                                                    f"Reason: TA exit ({support}/{total_tf} TFs). {note_reason}"
                                                )
                                                self._notify_event(
                                                    notifier, ch, txt, pos_id
                                                )
                                                self._mark_notified(pos_id, now_ts)
                                        continue
                            except Exception:
                                logger.debug("TA exit evaluation failed", exc_info=True)

                    # ---------- Wick/Spike-based management (geometry) ----------
                    try:
                        if bool(getattr(settings, "WICK_EXIT_ENABLE", True)):
                            wick_tfs = list(
                                getattr(settings, "WICK_EXIT_TFS", ["M5", "M15"])
                            )

                            # Per-symbol spike & partial overrides (with safe fallback)
                            try:
                                spike_mult, wick_partial = (
                                    settings.get_wick_symbol_overrides(symbol)
                                )
                            except Exception:
                                spike_mult = float(
                                    getattr(settings, "CANDLE_SPIKE_ATR_MULT", 1.8)
                                )
                                wick_partial = float(
                                    getattr(settings, "WICK_EXIT_PARTIAL_PCT", 0.5)
                                )

                            wick_confirm = int(
                                getattr(settings, "WICK_STACK_CONFIRM_BARS", 2)
                            )
                            wick_mode = str(
                                getattr(settings, "WICK_EXIT_MODE", "tighten_then_exit")
                            ).upper()
                            wick_tighten_to = str(
                                getattr(settings, "WICK_TIGHTEN_TO", "BE_OR_ATR")
                            ).upper()
                            be_buf_pct = float(
                                getattr(settings, "WICK_BE_BUFFER_PCT", 0.05)
                            )

                            # helper: tighten SL toward BE(+buffer)
                            def _tighten_to_be_or_keep(
                                current_sl: Optional[float], is_buy: bool
                            ) -> Optional[float]:
                                be = st.base_entry or float(pos.price_open)
                                base_sl = st.base_sl or float(pos.sl or 0.0)
                                r_dist = abs(be - base_sl) if base_sl else 0.0
                                buf = r_dist * be_buf_pct if r_dist else 0.0
                                if is_buy:
                                    target = be + buf
                                    if current_sl is None or current_sl < target:
                                        return target
                                else:
                                    target = be - buf
                                    if current_sl is None or current_sl > target:
                                        return target
                                return None

                            # Evaluate wicks per configured TFs
                            against_signals = 0
                            spike_against = False
                            for tf in wick_tfs:
                                # Per-symbol/timeframe tuned thresholds
                                try:
                                    w_thr, body_thr, bb_thr = (
                                        settings.get_wick_geometry_for(symbol, tf)
                                    )
                                except Exception:
                                    w_thr = float(
                                        getattr(
                                            settings, "CANDLE_WICK_UP_EXH_FRAC", 0.60
                                        )
                                    )
                                    body_thr = float(
                                        getattr(
                                            settings, "CANDLE_BODY_MAX_PIN_FRAC", 0.35
                                        )
                                    )
                                    bb_thr = float(
                                        getattr(
                                            settings, "CANDLE_EDGE_BB_PROX_FRAC", 0.15
                                        )
                                    )
                                tf_code = self._tf_to_mt5(tf)
                                df_tf = self._fetch_df(symbol, tf_code, bars=100)
                                if df_tf is None or len(df_tf) < 20:
                                    continue
                                stats = compute_candle_stats(
                                    df_tf, bb_period=20, atr_period=14
                                )
                                body_frac = stats.get("body_frac", 0.0)
                                uw_frac = stats.get("uw_frac", 0.0)
                                lw_frac = stats.get("lw_frac", 0.0)
                                rng_mult = stats.get("rng_atr_mult", 0.0)
                                dbu = stats.get("bb_dist_upper_frac", 1.0)
                                dbl = stats.get("bb_dist_lower_frac", 1.0)

                                # near flags: smaller distance -> nearer band
                                near_upper = dbu <= float(bb_thr)
                                near_lower = dbl <= float(bb_thr)

                                if is_buy:
                                    wick_against = (
                                        (uw_frac >= float(w_thr))
                                        and (body_frac <= float(body_thr))
                                        and near_upper
                                    )
                                    spike_against = spike_against or (
                                        rng_mult >= float(spike_mult)
                                        and (
                                            float(df_tf.iloc[-1]["close"])
                                            < float(df_tf.iloc[-1]["open"])
                                        )
                                    )
                                else:
                                    wick_against = (
                                        (lw_frac >= float(w_thr))
                                        and (body_frac <= float(body_thr))
                                        and near_lower
                                    )
                                    spike_against = spike_against or (
                                        rng_mult >= float(spike_mult)
                                        and (
                                            float(df_tf.iloc[-1]["close"])
                                            > float(df_tf.iloc[-1]["open"])
                                        )
                                    )

                                if wick_against:
                                    against_signals += 1

                            if against_signals > 0 or spike_against:
                                st.wick_stack = (st.wick_stack or 0) + 1
                                st.last_wick_ts = now
                                self._save()

                                took_action = False

                                # 1) tighten step
                                if wick_mode == "TIGHTEN_THEN_EXIT":
                                    # choose target
                                    new_sl = None
                                    if wick_tighten_to in {"BE", "BE_OR_ATR"}:
                                        new_sl = _tighten_to_be_or_keep(
                                            float(getattr(pos, "sl", 0.0) or 0.0)
                                            or None,
                                            is_buy,
                                        )
                                    # Fallback: if no BE move, keep current SL (or later: consider ATR)
                                    if new_sl is not None:
                                        ok = self._modify_sl_tp(
                                            mt5svc,
                                            ticket=pos.ticket,
                                            symbol=symbol,
                                            new_sl=float(new_sl),
                                            new_tp=None,
                                        )
                                        if ok:
                                            took_action = True
                                            self._journal(
                                                journal_repo,
                                                "wick_tighten",
                                                dict(
                                                    ticket=pos.ticket,
                                                    symbol=symbol,
                                                    new_sl=float(new_sl),
                                                    stack=int(st.wick_stack),
                                                ),
                                            )
                                            # Notify as SL adjust
                                            # === ANCHOR: PW_NOTIFY_ACTION_SL_ADJUST_START ===
                                            if notify_enabled and (
                                                "sl_adjust" in notify_on
                                            ):
                                                pos_id = str(ticket)
                                                now_ts = time.time()
                                                if self._should_notify(
                                                    pos_id, now_ts, throttle_sec
                                                ):
                                                    ch = (
                                                        self.ticket_to_chat.get(
                                                            str(ticket)
                                                        )
                                                        or default_chat_id
                                                    )
                                                    new_sl_fmt = float(new_sl)
                                                    reason_short = f"wick tighten (stack {st.wick_stack})"
                                                    txt = (
                                                        f"🔧 SL adjusted: {symbol} #{pos_id}\n"
                                                        f"New SL: {new_sl_fmt}\nReason: {reason_short}"
                                                    )
                                                    self._notify_event(
                                                        notifier, ch, txt, pos_id
                                                    )
                                                    self._mark_notified(pos_id, now_ts)
                                            # === ANCHOR: PW_NOTIFY_ACTION_SL_ADJUST_END ===
                                    # optional partial on first detection (per-symbol %)
                                    if wick_partial > 0 and st.wick_stack == 1:
                                        try:
                                            vol_to_close = float(pos.volume) * max(
                                                0.0, min(1.0, float(wick_partial))
                                            )
                                            if vol_to_close > 0:
                                                ok2 = self._partial_close(
                                                    mt5svc, pos, volume=vol_to_close
                                                )
                                                if ok2:
                                                    took_action = True
                                                    self._journal(
                                                        journal_repo,
                                                        "wick_partial",
                                                        dict(
                                                            ticket=pos.ticket,
                                                            symbol=symbol,
                                                            volume=vol_to_close,
                                                        ),
                                                    )
                                                    # Notify partial TP
                                                    # === ANCHOR: PW_NOTIFY_ACTION_PARTIAL ===
                                                    if notify_enabled and (
                                                        "partial_tp" in notify_on
                                                    ):
                                                        pos_id = str(ticket)
                                                        now_ts = time.time()
                                                        if self._should_notify(
                                                            pos_id,
                                                            now_ts,
                                                            throttle_sec,
                                                        ):
                                                            ch = (
                                                                self.ticket_to_chat.get(
                                                                    str(ticket)
                                                                )
                                                                or default_chat_id
                                                            )
                                                            price_fmt = price
                                                            txt = (
                                                                f"✂️ Partial TP: {symbol} #{pos_id}\n"
                                                                f"Closed {vol_to_close:.2f} at {price_fmt}."
                                                            )
                                                            self._notify_event(
                                                                notifier,
                                                                ch,
                                                                txt,
                                                                pos_id,
                                                            )
                                                            self._mark_notified(
                                                                pos_id, now_ts
                                                            )
                                                    # === END PARTIAL NOTIFY ===
                                        except Exception:
                                            logger.debug(
                                                "partial close failed (wick)",
                                                exc_info=True,
                                            )

                                # 2) exit if confirmed
                                if st.wick_stack >= wick_confirm:
                                    try:
                                        vol_to_close = float(pos.volume)
                                        if vol_to_close > 0:
                                            ok3 = self._partial_close(
                                                mt5svc, pos, volume=vol_to_close
                                            )
                                            if ok3:
                                                self._journal(
                                                    journal_repo,
                                                    "wick_exit",
                                                    dict(
                                                        ticket=pos.ticket,
                                                        symbol=symbol,
                                                        stack=int(st.wick_stack),
                                                    ),
                                                )
                                                # Map wick exit -> close_by_rule notify
                                                # === ANCHOR: PW_NOTIFY_ACTION_CLOSE ===
                                                if notify_enabled and (
                                                    "close_by_rule" in notify_on
                                                ):
                                                    pos_id = str(ticket)
                                                    now_ts = time.time()
                                                    if self._should_notify(
                                                        pos_id,
                                                        now_ts,
                                                        throttle_sec,
                                                    ):
                                                        ch = (
                                                            self.ticket_to_chat.get(
                                                                ticket_str
                                                            )
                                                            or default_chat_id
                                                        )
                                                        txt = (
                                                            f"🛑 Position closed by rule: {symbol} #{pos_id}\n"
                                                            f"Reason: Wick exit confirmed ({st.wick_stack} bars)."
                                                        )
                                                        self._notify_event(
                                                            notifier, ch, txt, pos_id
                                                        )
                                                        self._mark_notified(
                                                            pos_id, now_ts
                                                        )
                                                continue  # to next position
                                    except Exception:
                                        logger.debug("wick exit failed", exc_info=True)

                            else:
                                # reset streak when conditions are no longer met
                                if st.wick_stack:
                                    st.wick_stack = 0
                                    self._save()
                    except Exception:
                        logger.debug("Wick/spike logic failed", exc_info=True)

                    # ---------- 7) Optional pyramiding (before TP1 actions) ----------
                    if pyr_enable and r_multiple is not None and pyr_steps:
                        if len(st.pyr_done_steps) < max(0, pyr_max_adds):
                            for step in pyr_steps:
                                if (step not in st.pyr_done_steps) and (
                                    r_multiple >= step
                                ):
                                    sl_for_add = None
                                    if pyr_use_current_sl and getattr(pos, "sl", 0.0):
                                        sl_for_add = float(pos.sl)
                                    elif st.base_sl is not None:
                                        sl_for_add = float(st.base_sl)

                                    if sl_for_add is None or sl_for_add <= 0.0:
                                        self._journal(
                                            journal_repo,
                                            "pyramid_skip_no_sl",
                                            dict(
                                                ticket=ticket, symbol=symbol, step=step
                                            ),
                                        )
                                        continue
                                    if (is_buy and sl_for_add >= price) or (
                                        (not is_buy) and sl_for_add <= price
                                    ):
                                        self._journal(
                                            journal_repo,
                                            "pyramid_skip_bad_sl_side",
                                            dict(
                                                ticket=ticket,
                                                symbol=symbol,
                                                step=step,
                                                sl=sl_for_add,
                                                px=price,
                                            ),
                                        )
                                        continue

                                    base_risk_pct = float(pyr_risk_pct)
                                    try:
                                        if hasattr(journal_repo, "map_risk_pct"):
                                            base_risk_pct = float(
                                                journal_repo.map_risk_pct(
                                                    context="pyramid",
                                                    base_pct=base_risk_pct,
                                                )
                                            )
                                    except Exception:
                                        pass

                                    scaled_risk_pct, dd_info = self._scale_by_drawdown(
                                        journal_repo,
                                        base_risk_pct,
                                    )

                                    try:
                                        res = mt5svc.open_order(
                                            symbol=symbol,
                                            side=("buy" if is_buy else "sell"),
                                            sl=sl_for_add,
                                            tp=None,
                                            lot=None,  # risk-size it
                                            risk_pct=scaled_risk_pct,
                                            comment=f"pyramid@{step:.2f}R",
                                        )
                                        ok = bool(res and res.get("ok"))
                                        if ok:
                                            st.pyr_done_steps.append(step)
                                            self._save()
                                            self._journal(
                                                journal_repo,
                                                "pyramid_add",
                                                dict(
                                                    ticket=ticket,
                                                    symbol=symbol,
                                                    step=step,
                                                    risk_pct=scaled_risk_pct,
                                                    dd_factor=float(
                                                        dd_info.get("factor", 1.0)
                                                    ),
                                                    max_dd_pct=float(
                                                        dd_info.get("max_dd_pct", 0.0)
                                                    ),
                                                    sl_used=sl_for_add,
                                                ),
                                            )
                                            # (Keeping pyramid notify as-is; not part of the gated set)
                                            if (
                                                notifier
                                                and ticket_str in self.ticket_to_chat
                                            ):
                                                try:
                                                    dd_line = (
                                                        f" | DD factor x{float(dd_info.get('factor', 1.0)):.2f}"
                                                        if dd_info
                                                        else ""
                                                    )
                                                    notifier(
                                                        self.ticket_to_chat[ticket_str],
                                                        f"➕ Pyramid add {symbol} @{step:.2f}R | risk {scaled_risk_pct:.2f}%{dd_line}",
                                                    )
                                                except Exception:
                                                    logger.debug(
                                                        "Notifier failed on pyramid add",
                                                        exc_info=True,
                                                    )
                                        else:
                                            self._journal(
                                                journal_repo,
                                                "pyramid_add_failed",
                                                dict(
                                                    ticket=ticket,
                                                    symbol=symbol,
                                                    step=step,
                                                    reason=(
                                                        res.get("message")
                                                        if isinstance(res, dict)
                                                        else "unknown"
                                                    ),
                                                ),
                                            )
                                    except Exception as e:
                                        self._journal(
                                            journal_repo,
                                            "pyramid_add_exception",
                                            dict(
                                                ticket=ticket,
                                                symbol=symbol,
                                                step=step,
                                                error=str(e),
                                            ),
                                        )
                                    break  # one add per poll per position

                    # ---------- 5) Regime re-check with hysteresis ----------
                    if (
                        reeval_enable
                        and (now - st.last_regime_check_ts) >= reeval_every_sec
                    ):
                        new_regime = self._detect_regime(symbol, reeval_tf)
                        st.last_regime_check_ts = now
                        if new_regime:
                            if new_regime == st.regime_candidate:
                                st.regime_streak += 1
                            else:
                                st.regime_candidate = new_regime
                                st.regime_streak = 1

                            min_elapsed_to_flip = (now - st.last_mode_switch_ts) >= (
                                reeval_min_switch_min * 60
                            )
                            if (
                                st.regime_streak >= reeval_confirm
                                and min_elapsed_to_flip
                            ):
                                if new_regime != st.current_regime:
                                    old = st.current_regime or "UNKNOWN"
                                    st.current_regime = new_regime
                                    st.last_mode_switch_ts = now
                                    self._save()
                                    self._journal(
                                        journal_repo,
                                        "regime_flip",
                                        dict(
                                            ticket=ticket,
                                            symbol=symbol,
                                            side=side_l,
                                            old_regime=old,
                                            new_regime=new_regime,
                                            ts=now,
                                        ),
                                    )
                                    # (left as direct notifier - not part of gated set)
                                    if notifier and ticket_str in self.ticket_to_chat:
                                        try:
                                            notifier(
                                                self.ticket_to_chat[ticket_str],
                                                f"🧭 Regime change {symbol}: {old} → {new_regime}. Adapting trail/TP.",
                                            )
                                        except Exception:
                                            logger.debug(
                                                "Notifier failed on regime flip",
                                                exc_info=True,
                                            )

                    # ---------- 1) + 2) TP1 & BE ----------
                    if (
                        (not st.tp1_done)
                        and r_multiple is not None
                        and r_multiple >= tp1_r
                    ):
                        vol_to_close = float(pos.volume) * max(0.0, min(1.0, tp1_part))
                        if vol_to_close > 0:
                            if self._partial_close(mt5svc, pos, vol_to_close):
                                self._journal(
                                    journal_repo,
                                    "tp1_partial_close",
                                    dict(
                                        ticket=ticket,
                                        symbol=symbol,
                                        r_hit=tp1_r,
                                        closed_ratio=tp1_part,
                                        price=price,
                                        ts=now,
                                    ),
                                )
                                # === ANCHOR: PW_NOTIFY_ACTION_PARTIAL ===
                                if notify_enabled and ("partial_tp" in notify_on):
                                    pos_id = str(ticket)
                                    now_ts = time.time()
                                    if self._should_notify(
                                        pos_id, now_ts, throttle_sec
                                    ):
                                        ch = (
                                            self.ticket_to_chat.get(str(ticket))
                                            or default_chat_id
                                        )
                                        txt = (
                                            f"✂️ Partial TP: {symbol} #{pos_id}\n"
                                            f"Closed {tp1_part*100:.0f}% at {price}."
                                        )
                                        self._notify_event(notifier, ch, txt, pos_id)
                                        self._mark_notified(pos_id, now_ts)
                        st.tp1_done = True

                        if be_enable:
                            be = st.base_entry
                            if be_buffer_pct:
                                buffer = be * be_buffer_pct
                                be = (
                                    be + buffer if not is_buy else be - buffer
                                )  # BUY SL below; SELL SL above
                            be = self._round(be, digits)
                            if self._modify_sl_tp(
                                mt5svc,
                                ticket=ticket,
                                symbol=symbol,
                                new_sl=be,
                                new_tp=None,
                            ):
                                st.be_done = True
                                st.last_sl = be
                                self._journal(
                                    journal_repo,
                                    "move_to_breakeven",
                                    dict(
                                        ticket=ticket,
                                        symbol=symbol,
                                        be=be,
                                        buffer_pct=be_buffer_pct,
                                        ts=now,
                                    ),
                                )
                                # === ANCHOR: PW_NOTIFY_ACTION_BREAKEVEN ===
                                if notify_enabled and ("breakeven_set" in notify_on):
                                    pos_id = str(ticket)
                                    now_ts = time.time()
                                    if self._should_notify(
                                        pos_id, now_ts, throttle_sec
                                    ):
                                        ch = (
                                            self.ticket_to_chat.get(str(ticket))
                                            or default_chat_id
                                        )
                                        txt = f"🟰 Breakeven set: {symbol} #{pos_id}"
                                        self._notify_event(notifier, ch, txt, pos_id)
                                        self._mark_notified(pos_id, now_ts)

                        
                    # ---------- 2b) TP2 partial close ----------
                    try:
                        if (
                            (not st.tp2_done)
                            and r_multiple is not None
                            and r_multiple >= tp2_r
                        ):
                            # Respect minimum remainder of position
                            base_vol = float(getattr(st, "base_volume", 0.0) or float(pos.volume))
                            if base_vol <= 0:
                                base_vol = float(pos.volume)
                            remaining_ratio = float(pos.volume) / base_vol if base_vol else 1.0

                            # Max additional ratio we can close while keeping remainder
                            min_rem = max(0.0, min(1.0, exit_min_remainder))
                            max_close_ratio = max(0.0, remaining_ratio - min_rem)

                            desired_close_ratio = max(0.0, min(tp2_part, max_close_ratio))
                            vol_to_close = float(pos.volume) * desired_close_ratio

                            if vol_to_close > 0:
                                if self._partial_close(mt5svc, pos, vol_to_close):
                                    self._journal(
                                        journal_repo,
                                        "tp2_partial_close",
                                        dict(
                                            ticket=ticket,
                                            symbol=symbol,
                                            r_hit=tp2_r,
                                            closed_ratio=desired_close_ratio,
                                            price=price,
                                            ts=now,
                                        ),
                                    )
                                    # === ANCHOR: PW_NOTIFY_ACTION_PARTIAL ===
                                    if notify_enabled and ("partial_tp" in notify_on):
                                        pos_id = str(ticket)
                                        now_ts = time.time()
                                        if self._should_notify(pos_id, now_ts, throttle_sec):
                                            ch = self.ticket_to_chat.get(str(ticket)) or default_chat_id
                                            txt = (
                                                f"✂️ Partial TP2: {symbol} #{pos_id}\n"
                                                f"Closed {desired_close_ratio*100:.0f}% at {price}."
                                            )
                                            self._notify_event(notifier, ch, txt, pos_id)
                                            self._mark_notified(pos_id, now_ts)
                            st.tp2_done = True
                            self._save()
                    except Exception:
                        logger.debug("TP2 partial block failed", exc_info=True)
                        
                    # Determine active trail mode (AUTO or forced)
                    active_trail_mode = self._decide_trail_mode(st.current_regime)

                    # ---------- 3) Trailing for runners ----------
                    if st.tp1_done:
                        desired_sl_candidates: list[float] = []

                        if active_trail_mode in {"ATR", "HYBRID_MAX", "HYBRID_MIN"}:
                            atr_val = self._atr(
                                symbol, self._tf_to_mt5(atr_tf), period=atr_period
                            )
                            if atr_val:
                                try:
                                    by_reg = getattr(settings, "POS_TRAIL_ATR_MULT_BY_REGIME", {}) or {}
                                    v3 = by_reg.get(regime)
                                    if v3 is not None:
                                        atr_mult = float(v3)
                                except Exception:
                                    pass
                                sl_atr = (
                                    price - atr_mult * atr_val
                                    if is_buy
                                    else price + atr_mult * atr_val
                                )
                                desired_sl_candidates.append(sl_atr)

                        if active_trail_mode in {"CHAND", "HYBRID_MAX", "HYBRID_MIN"}:
                            sl_ch = self._compute_chandelier(
                                symbol,
                                is_buy,
                                tf_str=atr_tf,
                                period=chand_period,
                                mult=chand_mult,
                                atr_period=atr_period,
                            )
                            if sl_ch:
                                desired_sl_candidates.append(sl_ch)

                        if active_trail_mode == "R" or (
                            not desired_sl_candidates and r_multiple is not None
                        ):
                            if st.base_sl is not None:
                                risk_pts = abs(st.base_entry - st.base_sl)
                                trail_pts = trail_dist_r * risk_pts
                                sl_r = (
                                    price - trail_pts if is_buy else price + trail_pts
                                )
                                desired_sl_candidates.append(sl_r)

                        if desired_sl_candidates:
                            if active_trail_mode == "HYBRID_MAX":
                                desired_sl = (
                                    max(desired_sl_candidates)
                                    if is_buy
                                    else min(desired_sl_candidates)
                                )
                            elif active_trail_mode == "HYBRID_MIN":
                                desired_sl = (
                                    min(desired_sl_candidates)
                                    if is_buy
                                    else max(desired_sl_candidates)
                                )
                            elif active_trail_mode in {"CHAND", "ATR", "R"}:
                                desired_sl = (
                                    desired_sl_candidates[-1]
                                    if active_trail_mode == "CHAND"
                                    else desired_sl_candidates[0]
                                )
                            else:
                                desired_sl = desired_sl_candidates[0]

                            current_sl = (
                                float(getattr(pos, "sl", 0.0))
                                if getattr(pos, "sl", 0.0)
                                else None
                            )
                            if current_sl is not None:
                                if is_buy:
                                    desired_sl = max(desired_sl, current_sl)
                                else:
                                    desired_sl = min(desired_sl, current_sl)

                            desired_sl = self._round(desired_sl, digits)
                            if (
                                st.last_sl is None
                                or (is_buy and desired_sl > st.last_sl)
                                or ((not is_buy) and desired_sl < st.last_sl)
                            ):
                                if (now - st.last_trail_ts) >= trail_throttle_sec:
                                    if self._modify_sl_tp(
                                        mt5svc,
                                        ticket=ticket,
                                        symbol=symbol,
                                        new_sl=desired_sl,
                                        new_tp=None,
                                    ):
                                        st.last_sl = desired_sl
                                        st.last_trail_ts = now
                                        self._save()
                                        self._journal(
                                            journal_repo,
                                            "trail_update",
                                            dict(
                                                ticket=ticket,
                                                symbol=symbol,
                                                mode=active_trail_mode,
                                                new_sl=desired_sl,
                                                ts=now,
                                            ),
                                        )
                                        # === ANCHOR: PW_NOTIFY_ACTION_TRAIL ===
                                        if notify_enabled and (
                                            "trail_update" in notify_on
                                        ):
                                            pos_id = str(ticket)
                                            now_ts = time.time()
                                            if self._should_notify(
                                                pos_id, now_ts, throttle_sec
                                            ):
                                                ch = (
                                                    self.ticket_to_chat.get(str(ticket))
                                                    or default_chat_id
                                                )
                                                txt = f"🏃‍♂️ Trailing update: {symbol} #{pos_id}\nSL trailed."
                                                self._notify_event(
                                                    notifier, ch, txt, pos_id
                                                )
                                                self._mark_notified(pos_id, now_ts)

                    # ---------- 6) Adaptive TP by regime ----------
                    if adapt_tp_enable:
                        current_tp = (
                            float(getattr(pos, "tp", 0.0))
                            if getattr(pos, "tp", 0.0)
                            else None
                        )
                        desired_tp: Optional[float] = None
                        regime = (st.current_regime or "").upper()

                        ok_to_adapt = st.tp1_done or current_tp is None

                        if ok_to_adapt and st.base_sl is not None:
                            risk_pts = abs(st.base_entry - st.base_sl)
                            atr_val = self._atr(
                                symbol, self._tf_to_mt5(atr_tf), period=atr_period
                            )

                            if regime == "TREND":
                                target_r = (
                                    st.base_entry + tp_trend_r * risk_pts
                                    if is_buy
                                    else st.base_entry - tp_trend_r * risk_pts
                                )
                                target_atr = None
                                if atr_val:
                                    offs = tp_trend_atr_mult * atr_val
                                    target_atr = (
                                        (price + offs) if is_buy else (price - offs)
                                    )
                                candidates = [target_r] + (
                                    [target_atr] if target_atr is not None else []
                                )
                                desired_tp = (
                                    max(candidates) if is_buy else min(candidates)
                                )
                                if tp_only_extend and current_tp is not None:
                                    if (is_buy and desired_tp <= current_tp) or (
                                        (not is_buy) and desired_tp >= current_tp
                                    ):
                                        desired_tp = None
                                    else:
                                        st.tp_extended = True
                                else:
                                    st.tp_extended = True

                            elif regime == "VOLATILE":
                                target_r = (
                                    st.base_entry + tp_vol_r * risk_pts
                                    if is_buy
                                    else st.base_entry - tp_vol_r * risk_pts
                                )
                                target_atr = None
                                if atr_val:
                                    offs = tp_vol_atr_mult * atr_val
                                    target_atr = (
                                        (price + offs) if is_buy else (price - offs)
                                    )
                                candidates = [target_r] + (
                                    [target_atr] if target_atr is not None else []
                                )
                                desired_tp = (
                                    max(candidates) if is_buy else min(candidates)
                                )
                                if tp_only_extend and current_tp is not None:
                                    if (is_buy and desired_tp <= current_tp) or (
                                        (not is_buy) and desired_tp >= current_tp
                                    ):
                                        desired_tp = None
                                    else:
                                        st.tp_extended = True
                                else:
                                    st.tp_extended = True

                            elif regime == "RANGE":
                                target_r = (
                                    st.base_entry + tp_range_r * risk_pts
                                    if is_buy
                                    else st.base_entry - tp_range_r * risk_pts
                                )
                                bb_snapshot = self._fetch_df(
                                    symbol,
                                    self._tf_to_mt5(tb_tf),
                                    bars=max(200, bb_period * 4),
                                )
                                bb_candidate = None
                                if (
                                    bb_snapshot is not None
                                    and len(bb_snapshot) >= bb_period
                                ):
                                    mb = (
                                        bb_snapshot["close"]
                                        .rolling(bb_period)
                                        .mean()
                                        .iloc[-1]
                                    )
                                    sd = (
                                        bb_snapshot["close"]
                                        .rolling(bb_period)
                                        .std(ddof=0)
                                        .iloc[-1]
                                    )
                                    upper = mb + 2 * sd
                                    lower = mb - 2 * sd
                                    band_width = upper - lower
                                    offset = bb_offset_frac * band_width
                                    bb_candidate = (
                                        upper - offset if is_buy else lower + offset
                                    )
                                candidates = [target_r]
                                if bb_candidate is not None:
                                    candidates.append(bb_candidate)
                                desired_tp = (
                                    max(candidates) if is_buy else min(candidates)
                                )
                                if (
                                    not tp_allow_tighten_in_range
                                    and current_tp is not None
                                ):
                                    if (is_buy and desired_tp < current_tp) or (
                                        (not is_buy) and desired_tp > current_tp
                                    ):
                                        desired_tp = None
                                    else:
                                        st.tp_tightened = True
                                else:
                                    st.tp_tightened = True

                            if desired_tp is not None:
                                desired_tp = self._round(desired_tp, digits)
                                if (
                                    current_tp is None
                                    or (is_buy and desired_tp > current_tp)
                                    or ((not is_buy) and desired_tp < current_tp)
                                ):
                                    if self._modify_sl_tp(
                                        mt5svc,
                                        ticket=ticket,
                                        symbol=symbol,
                                        new_sl=None,
                                        new_tp=desired_tp,
                                    ):
                                        st.last_tp = desired_tp
                                        self._save()
                                        self._journal(
                                            journal_repo,
                                            "tp_update",
                                            dict(
                                                ticket=ticket,
                                                symbol=symbol,
                                                regime=regime,
                                                new_tp=desired_tp,
                                                ts=now,
                                            ),
                                        )
                                        # === ANCHOR: PW_NOTIFY_ACTION_TP_ADJUST ===
                                        if notify_enabled and (
                                            "tp_adjust" in notify_on
                                        ):
                                            pos_id = str(ticket)
                                            now_ts = time.time()
                                            if self._should_notify(
                                                pos_id, now_ts, throttle_sec
                                            ):
                                                ch = (
                                                    self.ticket_to_chat.get(ticket_str)
                                                    or default_chat_id
                                                )
                                                txt = f"🎯 TP adjusted: {symbol} #{pos_id}\nNew TP: {desired_tp}"
                                                self._notify_event(
                                                    notifier, ch, txt, pos_id
                                                )
                                                self._mark_notified(pos_id, now_ts)

                except Exception:
                    # per-position guard
                    logger.debug("PositionWatcher position loop failed.", exc_info=True)

        except Exception:
            logger.debug("PositionWatcher poll_once failed.", exc_info=True)
