# =====================================
# handlers/pending.py
# =====================================
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

import MetaTrader5 as mt5
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, Application

from config import settings
from infra.indicator_bridge import IndicatorBridge
from infra.mt5_service import MT5Service
from infra.openai_service import OpenAIService
from infra.virt_pendings import VirtualPendingManager as PseudoPendingManager
from infra.journal_repo import JournalRepo
from infra.formatting import fmt_price
from infra.news_service import NewsService  # News/calendar integration
from infra.bandit_autoupdate import wire_bandit_updates

# === ANCHOR: PA20_IMPORTS_START ===
from domain.zones import compute_zones, find_swings, nearest_zones
from domain.liquidity import detect_sweeps
from domain.breakout_quality import latest_breakout_quality
from domain.market_structure import label_swings, structure_bias

from infra.strategy_map import (
    get_strategy_map,
    compute_adjusted_risk_pct,
    session_overrides_for,
    compute_session_rr_floor,
)

# === ANCHOR: PA20_IMPORTS_END ===

logger = logging.getLogger(__name__)

_DEF_SYMBOL = "XAUUSDc"
_CB_BUCKET = "cb_payloads"


def normalise_symbol(sym: str | None) -> str:
    if not sym:
        return _DEF_SYMBOL
    s = sym.strip()
    base = s.rstrip("m").rstrip("c").rstrip("C").upper()
    return base + "c"


def _fmt(x, d=2):
    try:
        return f"{float(x):.{d}f}"
    except Exception:
        return str(x)


def _size_lot_from_map(
    mt5svc: MT5Service,
    *,
    symbol: str,
    entry: float,
    sl: float | None,
    strategy_key: str,
    tech: dict,
    session: str | None,
    regime: str | None,
) -> tuple[float, float, list[str]]:
    """
    Returns (lot, risk_pct, reasons).
    risk_pct is percent-of-equity units (e.g., 0.25 = 0.25%).
    Falls back to DEFAULT_LOT_SIZE if SL is missing or any error occurs.
    """
    # Caps are % of equity, e.g. 0.10 = 0.10%, 1.50 = 1.50%
    risk_min = float(getattr(settings, "RISK_MIN_PCT", 0.10))
    risk_max = float(getattr(settings, "RISK_MAX_PCT", 1.50))

    mp = get_strategy_map()

    risk_pct, reasons = compute_adjusted_risk_pct(
        mp,
        strategy_key,
        tech,
        symbol=symbol,
        session=session,
        regime=regime,
        min_cap=risk_min,
        max_cap=risk_max,
    )

    # If no SL, we cannot compute risk-based lot size; use default.
    default_lot = float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))
    if sl in (None, 0, "0"):
        return default_lot, risk_pct, reasons

    try:
        lot = mt5svc.risk_to_lot(symbol, float(entry), float(sl), float(risk_pct))
        lot = mt5svc.normalise_lot(symbol, lot)
        return float(lot), float(risk_pct), reasons
    except Exception:
        return default_lot, float(risk_pct), reasons


def infer_pending_type(direction: str, entry: float, bid: float, ask: float) -> str:
    """
    BUY: entry above ask => BUY_STOP; below ask => BUY_LIMIT
    SELL: entry below bid => SELL_STOP; above bid => SELL_LIMIT
    """
    try:
        d = (direction or "").upper()
        e = float(entry)
        b = float(bid)
        a = float(ask)
    except Exception:
        return ""
    if d == "BUY":
        return "BUY_STOP" if e >= a else "BUY_LIMIT"
    if d == "SELL":
        return "SELL_STOP" if e <= b else "SELL_LIMIT"
    return ""


def fmt_spread_readable(symbol: str, bid: float, ask: float) -> tuple[str, float]:
    """
    Returns (pretty_string, spread_pips).
    Pip = point*10 for 3/5-digit FX, else 1*point for others.
    """
    try:
        si = mt5.symbol_info(symbol)
        spread = max(0.0, float(ask) - float(bid))
        if not si:
            return f"{fmt_price(symbol, spread)}", 0.0
        point = float(getattr(si, "point", 0.0) or 0.0)
        digits = int(getattr(si, "digits", 5) or 5)
        pip = point * (10.0 if digits in (3, 5) else 1.0)
        spread_pips = (spread / pip) if pip > 0 else 0.0
        pretty = f"{fmt_price(symbol, spread)} (~{spread_pips:.1f} pips)"
        return pretty, spread_pips
    except Exception:
        sp = max(0.0, float(ask) - float(bid))
        return f"{fmt_price(symbol, sp)}", 0.0


def _spread_pretty(
    symbol: str, bid: float | None, ask: float | None
) -> tuple[str, float]:
    """
    Returns (pretty_string, spread_pips). Uses MT5 symbol digits/point to compute pips.
    Pip = point*10 for 3/5-digit FX; otherwise 1*point.
    """
    try:
        if bid is None or ask is None:
            return ("—", 0.0)
        si = mt5.symbol_info(symbol)
        point = float(getattr(si, "point", 0.0) or 0.0) if si else 0.0
        digits = int(getattr(si, "digits", 5) or 5) if si else 5
        pip = point * (10.0 if digits in (3, 5) else 1.0) or 1e-9
        spread = max(0.0, float(ask) - float(bid))
        spread_pips = spread / pip
        return (f"{spread_pips:.1f} pips", spread_pips)
    except Exception:
        return ("—", 0.0)


# === ANCHOR: PA20_HELPERS_START ===
def _is_near_boundary(pa: dict | None, price: float, max_spans: float = 1.2) -> bool:
    """
    True if current price is within `max_spans` × span of the nearest zone above or below.
    """
    if not pa:
        return False
    nz = (pa or {}).get("nearest", {})
    for key in ("above", "below"):
        z = nz.get(key)
        if not z:
            continue
        try:
            if abs(price - float(z["level"])) <= max_spans * float(z["span"]):
                return True
        except Exception:
            pass
    return False


def _prefer_fade_side(pa: dict | None, price: float) -> str | None:
    """
    Choose 'long' (fade up from support) or 'short' (fade down from resistance)
    by whichever zone is closest.
    """
    if not pa:
        return None
    nz = pa.get("nearest", {})
    ab, bl = nz.get("above"), nz.get("below")
    best = None
    try:
        if ab:
            best = ("short", abs(price - float(ab["level"])))
        if bl:
            d = abs(price - float(bl["level"]))
            if best is None or d < best[1]:
                best = ("long", d)
    except Exception:
        return None
    return best[0] if best else None


# === ANCHOR: PA20_HELPERS_END ===


def _fetch_series(symbol: str, tf: int, bars: int) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if rates is None:
        raise RuntimeError(f"No data for {symbol} tf={tf}")
    df = pd.DataFrame(rates)
    if "time" in df.columns:
        try:
            df["time"] = pd.to_datetime(df["time"], unit="s")
        except Exception:
            pass
    return df


def _calc_m1_spike_hints(symbol: str) -> dict:
    """Compute simple M1 TR ratio (last vs median of prior 20) for LLM hints."""
    end = datetime.utcnow()
    start = end - timedelta(minutes=30)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, end)
    if rates is None or len(rates) < 5:
        return {}
    now_s = time.time()
    closed = [r for r in rates if (r["time"] + 60) <= now_s]
    if len(closed) < 5:
        return {}
    trs = []
    prev_close = float(closed[0]["close"])
    for b in closed[1:]:
        high = float(b["high"])
        low = float(b["low"])
        close = float(b["close"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
        prev_close = close
    if len(trs) < 3:
        return {}
    last = trs[-1]
    hist = trs[:-1]
    hist_sorted = sorted(hist)
    mid = len(hist_sorted) // 2
    median = (
        0.5 * (hist_sorted[mid - 1] + hist_sorted[mid])
        if len(hist_sorted) % 2 == 0
        else hist_sorted[mid]
    )
    if median <= 0:
        return {}
    ratio = float(last / median)
    thr = float(getattr(settings, "PENDING_SPIKE_TR_MULT", 1.8))
    return {"m1_tr_ratio": ratio, "vol_spike": bool(ratio >= thr)}


def build_retest_pending(plan: dict, side: str) -> dict:
    """
    For weak breakouts: place stop order on reclaim of zone (bullish: buy stop above zone).
    """
    pa = plan.get("pa", {})
    nz = pa.get("nearest", {})
    if side == "long" and nz.get("above"):
        z = nz["above"]
        entry = float(z["level"]) + float(z["span"]) * 0.2
        return {"type": "BUY_STOP", "entry": entry}
    if side == "short" and nz.get("below"):
        z = nz["below"]
        entry = float(z["level"]) - float(z["span"]) * 0.2
        return {"type": "SELL_STOP", "entry": entry}
    return {}


def build_fakeout_oco(plan: dict, prefer_side: str) -> tuple[dict, dict]:
    """
    OCO pair: one fade at boundary + protective stop in the breakout direction.
    """
    pa = plan.get("pa", {})
    nz = pa.get("nearest", {})
    if prefer_side == "long" and nz.get("below"):
        z = nz["below"]
        fade = {
            "type": "BUY_LIMIT",
            "entry": float(z["level"]) + float(z["span"]) * 0.1,
        }
        protect = {
            "type": "SELL_STOP",
            "entry": float(z["level"]) - float(z["span"]) * 0.4,
        }
        return fade, protect
    if prefer_side == "short" and nz.get("above"):
        z = nz["above"]
        fade = {
            "type": "SELL_LIMIT",
            "entry": float(z["level"]) - float(z["span"]) * 0.1,
        }
        protect = {
            "type": "BUY_STOP",
            "entry": float(z["level"]) + float(z["span"]) * 0.4,
        }
        return fade, protect
    return {}, {}


def _build_tech_from_bridge(
    multi: dict, symbol: str
) -> tuple[dict, pd.DataFrame | None, pd.DataFrame | None]:
    m5 = multi.get("M5", {})
    m15 = multi.get("M15", {})
    h1 = multi.get("H1", {})
    m5_df = m15_df = None
    try:
        m5_df = _fetch_series(symbol, mt5.TIMEFRAME_M5, 120)
    except Exception:
        pass
    try:
        m15_df = _fetch_series(symbol, mt5.TIMEFRAME_M15, 80)
    except Exception:
        pass

    price_now = float(m5.get("close") or h1.get("close") or 0.0)
    ema200_ref = float(m5.get("ema_200") or h1.get("ema_200") or price_now)
    ema_alignment = bool(price_now >= ema200_ref)

    ema200_now = float(h1.get("ema_200") or 0.0)
    ema200_prev = float(h1.get("ema_200_prev") or 0.0)
    ema_slope_h1 = 0.0
    try:
        if ema200_prev and ema200_now:
            ema_slope_h1 = (ema200_now - ema200_prev) / max(1e-9, ema200_prev)
    except Exception:
        pass

    tech = {
        "symbol": symbol,
        "close": price_now,
        "atr_14": m5.get("atr_14"),
        "ema_20": m5.get("ema_20"),
        "ema_50": m5.get("ema_50"),
        "ema_200": ema200_ref,
        "adx": m5.get("adx_14") or m5.get("adx"),
        "bb_width": m5.get("bb_width"),
        "ema_alignment": ema_alignment,
        "ema_slope_h1": ema_slope_h1,
        "min_confidence": 0.62,
        "news_block": False,
        "_snapshot_tf": "M5",
    }
    tech["_tf_M5"] = m5
    tech["_tf_M15"] = m15
    tech["_tf_H1"] = h1
    return tech, m5_df, m15_df


def _build_pending_message(
    sym: str, plan: dict, expires_ts: Optional[int], rr_floor: float, show_cooloff: bool
) -> str:
    rr = _fmt(plan.get("rr"), 2)
    pt = (plan.get("pending_type") or "").replace("_", " ").upper()

    entry_val = plan.get("entry")
    entry_line = (
        f"- Entry: {fmt_price(sym, entry_val)}"
        if entry_val is not None
        else "- Entry: —"
    )

    exp = (
        f" (expires {datetime.fromtimestamp(expires_ts).strftime('%H:%M')})"
        if expires_ts
        else ""
    )
    parts = [
        "### Pending Order Plan",
        f"- Symbol: {sym}",
        f"- Regime: {plan.get('regime','RANGE')}",
        f"- Type: {pt}",
        f"- Direction: {plan.get('direction','BUY')}",
        entry_line,
        (
            f"- SL: {fmt_price(sym, plan.get('sl'))}  (ATR/structure)"
            if plan.get("sl") is not None
            else "- SL: —"
        ),
        (
            f"- TP: {fmt_price(sym, plan.get('tp'))}  (ATR/structure)"
            if plan.get("tp") is not None
            else "- TP: —"
        ),
        f"- R:R: {rr} (floor {rr_floor})",
        "",
        f"**Why:** {plan.get('reasoning','')}",
    ]
    if expires_ts:
        parts.append(f"**Arming:** will watch and trigger when price hits entry{exp}.")
    if show_cooloff:
        n = int(getattr(settings, "PENDING_COOLDOWN_M1_CLOSES", 0))
        buf = float(getattr(settings, "PENDING_COOLDOWN_BUFFER_PCT", 0.0))
        if n > 0:
            buf_txt = f" + {buf*100:.2f}% buffer" if buf > 0 else ""
            parts.append(
                f"**Cool-off:** requires {n} closed M1 candle(s) beyond the trigger{buf_txt}; may auto-increase during spikes."
            )
    return "\n".join(parts)


# ---------- tiny payload cache for short callback_data ----------
def _stash_cb(
    app: Application, chat_id: int, payload: dict, ttl_sec: int = 1800
) -> str:
    bucket = app.bot_data.setdefault(_CB_BUCKET, {})
    token = uuid.uuid4().hex[:8]
    bucket[token] = {
        "chat_id": chat_id,
        "payload": payload,
        "exp": time.time() + ttl_sec,
    }
    # opportunistic cleanup
    now = time.time()
    for k in list(bucket.keys()):
        try:
            if bucket[k]["exp"] < now:
                del bucket[k]
        except Exception:
            del bucket[k]
    return token


def _pop_cb(app: Application, token: str, chat_id: int) -> Optional[dict]:
    bucket = app.bot_data.get(_CB_BUCKET, {})
    item = bucket.pop(token, None)
    if not item:
        return None
    if item.get("chat_id") != chat_id:
        return None
    if item.get("exp", 0) < time.time():
        return None
    return item.get("payload")


# ---------- registration ----------
def register_pending_handlers(
    app: Application, pending_manager: PseudoPendingManager, journal_repo: JournalRepo
) -> None:
    app.add_handler(CommandHandler("pending", pending_command))
    app.add_handler(CommandHandler("pendings", pendings_list_command))  # list & cancel

    # PRIORITY: route our callbacks first
    app.add_handler(
        CallbackQueryHandler(pending_callbacks, pattern=r"^pend\|", block=True),
        group=-10,
    )

    app.bot_data["pending_manager"] = pending_manager
    app.bot_data["journal_repo"] = journal_repo

    # Background poller — picks up poswatch from bot_data
    async def _pending_tick(context: ContextTypes.DEFAULT_TYPE):
        logger.info("[JOB _pending_tick] tick start")
        try:
            mt5svc = MT5Service()
            mt5svc.connect()

            async def _notify(chat_id, text):
                # First send the event text (fill/expiry)
                await context.application.bot.send_message(chat_id=chat_id, text=text)
                # Then show the main menu
                try:
                    from handlers.menu import main_menu_markup

                    await context.application.bot.send_message(
                        chat_id=chat_id,
                        text="What next?",
                        reply_markup=main_menu_markup(),
                    )
                except Exception:
                    pass

            poswatch = context.application.bot_data.get("poswatch")
            circuit = context.application.bot_data.get("circuit")
            pending_manager.poll_once(
                mt5svc,
                _notify,
                journal_repo=journal_repo,
                poswatch=poswatch,
                circuit=circuit,
            )
        except Exception:
            logger.debug("Pending tick failed", exc_info=True)
        finally:
            logger.info("[JOB _pending_tick] tick done")

    try:
        app.job_queue.run_repeating(
            _pending_tick, interval=10, first=7, name="_pending_tick"
        )
        logger.info("[JOB _pending_tick] scheduled: every %ss, first in %ss", 10, 7)
    except Exception:
        logger.info(
            "job_queue not available; ensure your scheduler calls pending_manager.poll_once(...) periodically."
        )

    try:
        wire_bandit_updates(journal_repo)  # NEW: auto-learn from closures
    except Exception:
        logger.debug("wire_bandit_updates failed", exc_info=True)


# NOTE: accepts optional symbol (so callbacks can pass it through)
async def pending_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, symbol: Optional[str] = None
):
    """Entry point: /pending <symbol> OR callback refresh with explicit symbol."""
    reply = update.message or update.callback_query.message
    chat_id = update.effective_chat.id
    sym = symbol or (
        context.args[0] if update.message and context.args else _DEF_SYMBOL
    )
    sym = normalise_symbol(sym)
    await reply.reply_text(f"🧪 Analysing pending-order setup for {sym}…")

    # --- helpers ----------------------------------------------------
    def _calc_rr(entry: float, sl: float, tp: float) -> float:
        try:
            entry = float(entry)
            sl = float(sl)
            tp = float(tp)
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            return 0.0 if risk <= 0 else (reward / risk)
        except Exception:
            return 0.0

    def _auto_tighten_limit_sl(
        plan: dict, tech: dict, m15_df: Optional[pd.DataFrame], rr_floor: float
    ) -> dict:
        """
        Tighten SL for LIMIT plans using M15 EMA50 / last swing (with buffers)
        to try meet RR floor without asking the moon from TP.
        """
        ptype = (plan.get("pending_type") or "").upper()
        if "LIMIT" not in ptype:
            return plan
        try:
            entry = float(plan["entry"])
            sl_old = float(plan["sl"])
            tp = float(plan["tp"])
        except Exception:
            return plan

        m15 = tech.get("_tf_M15", {}) or {}
        ema50 = float(m15.get("ema_50") or 0.0)
        atr_m15 = float(m15.get("atr_14") or tech.get("atr_14") or 0.0)

        lookback = int(getattr(settings, "STRUCT_SWING_LOOKBACK_M15", 20))
        buf_pct = float(getattr(settings, "PENDING_STRUCT_SL_BUFFER_PCT", 0.0007))
        buf_abs = entry * buf_pct
        min_risk_mult = float(
            getattr(settings, "PENDING_STRUCT_MIN_RISK_ATR_M15", 0.40)
        )
        min_risk = max(1e-6, atr_m15 * min_risk_mult) if atr_m15 > 0 else entry * 0.0008

        swing_lo = swing_hi = None
        try:
            if isinstance(m15_df, pd.DataFrame) and len(m15_df) >= (lookback + 2):
                closed = m15_df.iloc[:-1]
                window = closed.tail(lookback)
                swing_lo = float(window["low"].min())
                swing_hi = float(window["high"].max())
        except Exception:
            pass

        new_sl = None
        if ptype == "BUY_LIMIT":
            cands = []
            if ema50 and ema50 < entry:
                cands.append(ema50 - buf_abs)
            if swing_lo and swing_lo < entry:
                cands.append(swing_lo - buf_abs)
            cands = [c for c in cands if c < entry]
            if cands:
                new_sl = max(cands)
                if (entry - new_sl) < min_risk:
                    new_sl = entry - min_risk
        elif ptype == "SELL_LIMIT":
            cands = []
            if ema50 and ema50 > entry:
                cands.append(ema50 + buf_abs)
            if swing_hi and swing_hi > entry:
                cands.append(swing_hi + buf_abs)
            cands = [c for c in cands if c > entry]
            if cands:
                new_sl = min(cands)
                if (new_sl - entry) < min_risk:
                    new_sl = entry + min_risk

        if new_sl is not None:
            rr_new = _calc_rr(entry, new_sl, tp)
            if rr_new >= rr_floor and abs(new_sl - entry) < abs(sl_old - entry):
                plan = dict(plan)
                plan["sl"] = float(new_sl)
                plan["rr"] = float(rr_new)
                reason = str(plan.get("reasoning", "")).strip()
                note = " SL tightened to M15 structure (EMA50 / last swing) to meet RR floor."
                plan["reasoning"] = (reason + note) if reason else note
        return plan

    # ---------------------------------------------------------------

    try:
        mt5svc = MT5Service()
        mt5svc.connect()
        mt5svc.ensure_symbol(sym)
        bridge = IndicatorBridge(settings.MT5_FILES_DIR)
        oai = OpenAIService(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)

        # Live quote
        try:
            q = mt5svc.get_quote(sym)
            bid, ask = q.bid, q.ask
        except Exception:
            bid = ask = None

        multi = bridge.get_multi(sym)
        tech, _m5_df, _m15_df = _build_tech_from_bridge(multi, sym)
        tech.update(_calc_m1_spike_hints(sym))  # vol hints

        # === ANCHOR: PA20_PENDING_START ===
        # Compute PA context from M5 series (zones, sweeps, breakout quality, micro-structure).
        pa_ctx = {}
        if getattr(settings, "PA20_ENABLED", True):
            try:
                _df = _m5_df if (_m5_df is not None and not _m5_df.empty) else None
                if _df is not None:
                    zones = compute_zones(_df, left=3, right=3, lookback=800)
                    swings = find_swings(_df, left=3, right=3, lookback=800)
                    struct_pts = label_swings(swings)
                    struct_bias = structure_bias(struct_pts, lookback=6)

                    last_price = float(_df["close"].iloc[-1])
                    z_above, z_below = nearest_zones(last_price, zones)

                    bq = None
                    if z_above and (z_above.level - last_price) < (z_above.span * 2):
                        bq = latest_breakout_quality(_df, z_above, lookback=20)
                    elif z_below and (last_price - z_below.level) < (z_below.span * 2):
                        bq = latest_breakout_quality(_df, z_below, lookback=20)

                    sweeps = detect_sweeps(_df, zones, lookback=120, min_wick_ratio=1.5)

                    pa_ctx = {
                        "zones": [
                            {
                                "level": z.level,
                                "span": z.span,
                                "touches": z.touches,
                                "score": z.score,
                                "kind": z.kind,
                            }
                            for z in zones[:10]
                        ],
                        "nearest": {
                            "above": (
                                {"level": z_above.level, "span": z_above.span}
                                if z_above
                                else None
                            ),
                            "below": (
                                {"level": z_below.level, "span": z_below.span}
                                if z_below
                                else None
                            ),
                        },
                        "sweeps": [
                            {
                                "kind": s.kind,
                                "bar_index": s.bar_index,
                                "zone_level": s.zone_level,
                                "wick_ratio": s.wick_ratio,
                            }
                            for s in sweeps[-5:]
                        ],
                        "breakout_quality": bq,
                        "structure_bias": struct_bias,
                    }
            except Exception:
                pa_ctx = {}
        else:
            pa_ctx = {}
        # === ANCHOR: PA20_PENDING_END ===

        # News integration
        news_svc = NewsService(settings.NEWS_EVENTS_PATH)
        cat = "crypto" if sym.startswith("BTC") or sym.startswith("ETH") else "macro"
        now_utc = datetime.utcnow()
        news_summary = news_svc.summary_for_prompt(category=cat, now=now_utc)
        tech["news_block"] = news_svc.is_blackout(category=cat, now=now_utc)
        fundamentals = news_summary

        fundamentals_extra = ""
        if news_summary:
            fundamentals_extra = "\nNews: " + news_summary
        try:
            from handlers.trading import load_daily_fundamentals

            fundamentals += fundamentals_extra + " " + load_daily_fundamentals()
        except Exception:
            fundamentals += fundamentals_extra

        base_rr_floor = float(getattr(settings, "MIN_RR_FOR_PENDINGS", 1.2))

        # --- session + strategy map (needed BEFORE first plan to support prefer_breakout) ---
        mp = get_strategy_map()
        session = (
            str(
                tech.get("session") or (tech.get("_tf_M5") or {}).get("session") or ""
            ).upper()
            or None
        )

        gen_ov = session_overrides_for(mp, "generic_pending", session)
        rp_kwargs = {}
        if gen_ov.get("prefer_breakout"):
            rp_kwargs["prefer_style"] = (
                "STOP"  # bias LLM toward breakout in London/NY if configured
            )

        # ── Primary plan (with optional session bias) ─────────────────
        plan = oai.recommend_pending(
            sym, tech, fundamentals, current_bid=bid, current_ask=ask, **rp_kwargs
        )

        # Effective RR floor for this strategy+session (needed BEFORE any rr_floor checks)
        strat_key = str(plan.get("strategy") or "generic_pending")
        ov = session_overrides_for(mp, strat_key, session)
        if not ov.get("enabled", True):
            strat_key = "generic_pending"
        rr_floor = compute_session_rr_floor(mp, strat_key, session, base_rr_floor)

        # === ANCHOR: PA20_DECISIONS_START ===
        # Attach PA to plan (for journaling/explanations)
        if pa_ctx:
            plan["pa"] = pa_ctx

        # 4.a Retest Pending when breakout is weak
        bq = (pa_ctx or {}).get("breakout_quality")
        if getattr(settings, "PENDING_BQ_RETEST_ENABLED", True) and bq == "weak":
            side_dir = str(plan.get("direction", "BUY")).upper()
            side = "long" if side_dir == "BUY" else "short"
            ret = build_retest_pending({"pa": pa_ctx}, side)
            if ret and ret.get("type") and ret.get("entry") is not None:
                # keep SL/TP as computed, adapt entry/type
                plan["pending_type"] = ret["type"]
                plan["entry"] = float(ret["entry"])
                reason = str(plan.get("reasoning", "")).strip()
                note = " Using retest entry due to weak breakout quality."
                plan["reasoning"] = (reason + note) if reason else note

        # 4.b Fakeout OCO (fade+protect) option if near boundary and break is weak/failure
        fakeout_ok = False
        prefer_side = None
        try:
            price_now = float(tech.get("close", 0.0))
            fakeout_ok = (
                getattr(settings, "PENDING_ENABLE_FAKEOUT_OCO", True)
                and (bq in {"failure", "weak"})
                and _is_near_boundary(
                    pa_ctx,
                    price_now,
                    max_spans=float(
                        getattr(settings, "PENDING_FAKEOUT_MAX_SPANS", 1.2)
                    ),
                )
            )

            prefer_side = _prefer_fade_side(pa_ctx, price_now) if fakeout_ok else None
        except Exception:
            fakeout_ok = False
            prefer_side = None

        fakeout_payload = None
        if fakeout_ok and prefer_side:
            fade, protect = build_fakeout_oco({"pa": pa_ctx}, prefer_side)
            if fade and protect:
                # Normalise: ensure each leg has pending_type + regime
                for leg in (fade, protect):
                    if "pending_type" not in leg and "type" in leg:
                        leg["pending_type"] = leg["type"]
                    # copy regime from the primary plan if missing
                    leg.setdefault("regime", plan.get("regime"))

                # SL/TP inherit from primary plan if not provided by builder; then compute RR
                for leg in (fade, protect):
                    leg.setdefault("sl", plan.get("sl"))
                    leg.setdefault("tp", plan.get("tp"))
                    leg["rr"] = _calc_rr(leg.get("entry"), leg.get("sl"), leg.get("tp"))

                fakeout_payload = {
                    "buy": (
                        fade if prefer_side == "long" else protect
                    ),  # long fade vs. short protect
                    "sell": protect if prefer_side == "long" else fade,
                }

        # === ANCHOR: PA20_DECISIONS_END ===

        # Make sure type matches current market location
        try:
            if bid is not None and ask is not None:
                ptype = infer_pending_type(
                    plan.get("direction"), plan.get("entry"), bid, ask
                )
                if ptype:
                    plan["pending_type"] = ptype
        except Exception:
            pass

        # Server-side RR calculation
        try:
            plan["rr"] = _calc_rr(
                float(plan["entry"]), float(plan["sl"]), float(plan["tp"])
            )
        except Exception:
            plan["rr"] = float(plan.get("rr", 0.0))

        # Auto-tighten LIMIT SL if needed
        if float(plan.get("rr", 0.0)) < rr_floor:
            plan = _auto_tighten_limit_sl(plan, tech, _m15_df, rr_floor)

        # === ANCHOR: PA20_STOP_CALL_START ===
        # If still below floor and this is a STOP plan, try PA re-anchoring / retest conversion
        if (
            float(plan.get("rr", 0.0)) < rr_floor
            and "STOP" in str(plan.get("pending_type", "")).upper()
        ):
            plan = _auto_improve_stop_rr(plan, pa_ctx, rr_floor, tech)
        # === ANCHOR: PA20_STOP_CALL_END ===

        # === ANCHOR: PA20_PALIMIT_START ===
        # PA-aware re-anchor for LIMIT orders (entry towards zone, SL just beyond)
        if (
            float(plan.get("rr", 0.0)) < rr_floor
            and pa_ctx
            and "LIMIT" in str(plan.get("pending_type", "")).upper()
        ):
            nz = (pa_ctx or {}).get("nearest", {})
            side = str(plan.get("direction", "BUY")).upper()
            z = nz.get("above") if side == "SELL" else nz.get("below")
            try:
                if z:
                    entry_old = float(plan["entry"])
                    tp_old = float(plan["tp"])
                    sl_old = float(plan["sl"])
                    level = float(z["level"])
                    span = float(z["span"])
                    # Tunables (or put these in settings)
                    entry_k = float(
                        getattr(settings, "PENDING_LIMIT_ENTRY_OFFSET_SPANS", 0.20)
                    )
                    sl_k = float(
                        getattr(settings, "PENDING_LIMIT_SL_BEYOND_SPANS", 0.40)
                    )

                    if side == "SELL":
                        entry_new = max(
                            entry_old, level - entry_k * span
                        )  # closer to resistance
                        sl_new = max(level + sl_k * span, entry_new + 1e-6)
                    else:
                        entry_new = min(
                            entry_old, level + entry_k * span
                        )  # closer to support
                        sl_new = min(level - sl_k * span, entry_new - 1e-6)

                    # Keep TP; re-evaluate RR
                    def _rr(e, s, t):
                        r = abs(e - s)
                        w = abs(e - t)
                        return 0.0 if r <= 0 else (w / r)

                    rr_new = _rr(entry_new, sl_new, tp_old)
                    # Only apply if we actually improved to meet floor
                    if rr_new >= rr_floor:
                        plan = dict(plan)
                        plan["entry"] = entry_new
                        plan["sl"] = sl_new
                        plan["rr"] = rr_new
                        reason = str(plan.get("reasoning", "")).strip()
                        note = " Entry re-anchored at PA zone; SL set just beyond zone edge."
                        plan["reasoning"] = (reason + note) if reason else note
            except Exception:
                pass
        # === ANCHOR: PA20_PALIMIT_END ===

        ttl_min = int(getattr(settings, "PENDING_DEFAULT_EXPIRY_MIN", 360))
        expires_ts = int(time.time() + ttl_min * 60)
        show_cooloff = int(getattr(settings, "PENDING_COOLDOWN_M1_CLOSES", 0)) > 0

        # ---- Spread/volatility filter --------------------------------
        cb_refresh = f"pend|refresh|{sym}"
        cb_cancel_all = f"pend|cancel_all|{sym}"
        rows: list[list[InlineKeyboardButton]] = []
        try:
            meta = mt5svc.symbol_meta(sym)
            point = float(meta["point"])
            spread = (ask - bid) if (ask is not None and bid is not None) else None
            atr_m5 = float(tech.get("atr_14") or 0.0)
            spread_pts = (
                (spread / point) if (spread is not None and point > 0) else None
            )

            max_pct = float(getattr(settings, "SPREAD_MAX_ATR_PCT", 0.25))  # 25% ATR
            max_pts = float(getattr(settings, "SPREAD_MAX_POINTS", 0.0))  # 0=off

            blocked = False
            reason = ""
            pretty_spread = "—"
            if spread is not None and atr_m5 > 0:
                pretty_spread, _sp_pips = _spread_pretty(sym, bid, ask)
                pct = 100.0 * spread / atr_m5
                if spread >= atr_m5 * max_pct:
                    blocked = True
                    reason = f"{pretty_spread} ({pct:.1f}% of M5 ATR)"
                if max_pts > 0 and spread_pts is not None and spread_pts >= max_pts:
                    blocked = True
                    reason = f"{int(spread_pts)} pts (>{int(max_pts)} cap)"

            if blocked:
                text = _build_pending_message(
                    sym, plan, expires_ts, rr_floor, show_cooloff
                )
                text += (
                    f"\n\n**Blocked by spread filter:** spread {pretty_spread} "
                    f"(~{_fmt(100 * spread / atr_m5, 1)}% of M5 ATR). Tap **Refresh plan** when spreads settle."
                )
                rows = [
                    [InlineKeyboardButton("🔄 Refresh plan", callback_data=cb_refresh)],
                    [
                        InlineKeyboardButton(
                            "🗑 Cancel all (chat)", callback_data=cb_cancel_all
                        )
                    ],
                ]
                await reply.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))
                # show menu as well
                try:
                    from handlers.menu import main_menu_markup

                    await reply.reply_text(
                        "What next?", reply_markup=main_menu_markup()
                    )
                except Exception:
                    pass
                return
        except Exception:
            pass
        # --------------------------------------------------------------

        text = _build_pending_message(sym, plan, expires_ts, rr_floor, show_cooloff)
        key = ("pending_last", chat_id, sym)
        context.application.bot_data[key] = {"plan": plan, "expires_ts": expires_ts}

        # ---- Risk-based lot sizing (map-aware) ----
        # Strategy name may be absent in LLM plans; use a generic bucket that you define in strategy_map.json
        # (strat_key & session already computed above; rr_floor already effective)
        # Session/regime to let overrides kick in (safe fallbacks if missing)
        # (keep session as computed above)

        regime = str(plan.get("regime") or "").upper() or None

        # Primary leg lot (map-aware)
        lot_primary, risk_pct, risk_reasons = _size_lot_from_map(
            mt5svc,
            symbol=sym,
            entry=float(plan.get("entry")),
            sl=(None if plan.get("sl") in (None, 0, "0") else float(plan.get("sl"))),
            strategy_key=strat_key,
            tech=tech,
            session=session,
            regime=regime,
        )

        logger.info("risk_pct=%.3f reasons=%s", risk_pct, "; ".join(risk_reasons))

        # Single-arm payload (tokenised; include regime for watcher AUTO mode)
        payload_single = {
            "symbol": sym,
            "side": (plan.get("direction", "BUY") or "BUY").lower(),
            "ptype": plan.get("pending_type", "BUY_STOP"),
            "entry": float(plan.get("entry")),
            "sl": None if plan.get("sl") in (None, 0, "0") else float(plan.get("sl")),
            "tp": None if plan.get("tp") in (None, 0, "0") else float(plan.get("tp")),
            "lot": float(lot_primary),
            "expires_ts": int(expires_ts),
            "regime": (plan.get("regime") or None),
        }
        token_single = _stash_cb(context.application, chat_id, payload_single)
        cb_arm = f"pend|armk|{token_single}"

        # OCO plans (stops), with server-side RR and risk-based lots
        plan_buy = oai.recommend_pending(
            sym,
            tech,
            fundamentals,
            current_bid=bid,
            current_ask=ask,
            direction_bias="BUY",
            prefer_style="STOP",
        )
        plan_sell = oai.recommend_pending(
            sym,
            tech,
            fundamentals,
            current_bid=bid,
            current_ask=ask,
            direction_bias="SELL",
            prefer_style="STOP",
        )
        plan_buy["pending_type"] = "BUY_STOP"
        plan_sell["pending_type"] = "SELL_STOP"
        try:
            plan_buy["rr"] = _calc_rr(
                float(plan_buy["entry"]), float(plan_buy["sl"]), float(plan_buy["tp"])
            )
        except Exception:
            plan_buy["rr"] = float(plan_buy.get("rr", 0.0))
        try:
            plan_sell["rr"] = _calc_rr(
                float(plan_sell["entry"]),
                float(plan_sell["sl"]),
                float(plan_sell["tp"]),
            )
        except Exception:
            plan_sell["rr"] = float(plan_sell.get("rr", 0.0))

        both_ok = (
            float(plan_buy.get("rr", 0.0)) >= rr_floor
            and float(plan_sell.get("rr", 0.0)) >= rr_floor
        )

        # Risk lots for each OCO leg
        try:
            lot_buy = mt5svc.risk_to_lot(
                sym, float(plan_buy["entry"]), float(plan_buy["sl"]), risk_pct
            )
            lot_buy = mt5svc.normalise_lot(sym, lot_buy)
        except Exception:
            lot_buy = float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))

        try:
            lot_sell = mt5svc.risk_to_lot(
                sym, float(plan_sell["entry"]), float(plan_sell["sl"]), risk_pct
            )
            lot_sell = mt5svc.normalise_lot(sym, lot_sell)
        except Exception:
            lot_sell = float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))

        oco_key = ("pending_last_oco", chat_id, sym)
        context.application.bot_data[oco_key] = {
            "buy": plan_buy,
            "sell": plan_sell,
            "expires_ts": expires_ts,
            "lot_buy": float(lot_buy),
            "lot_sell": float(lot_sell),
        }

        # Buttons (NO manual level editing)
        rows.append([InlineKeyboardButton("✅ Arm pending", callback_data=cb_arm)])
        if both_ok:
            rows.append(
                [
                    InlineKeyboardButton(
                        "⛓ Arm OCO breakout (both stops)",
                        callback_data=f"pend|arm_oco|{sym}",
                    )
                ]
            )

        # === ANCHOR: PA20_FAKEOUT_CTA_START ===
        if fakeout_payload:
            # Lots using the same adjusted risk_pct as the primary plan
            def _lot_fk(leg: dict) -> float:
                try:
                    lot = mt5svc.risk_to_lot(
                        sym, float(leg["entry"]), float(leg["sl"]), risk_pct
                    )
                    return mt5svc.normalise_lot(sym, lot)
                except Exception:
                    return float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))

            lot_buy_fk = _lot_fk(fakeout_payload["buy"])
            lot_sell_fk = _lot_fk(fakeout_payload["sell"])

            oco_key_fake = ("pending_last_oco_fake", chat_id, sym)
            context.application.bot_data[oco_key_fake] = {
                "buy": fakeout_payload["buy"],  # now includes "regime"
                "sell": fakeout_payload["sell"],  # now includes "regime"
                "expires_ts": expires_ts,
                "lot_buy": float(lot_buy_fk),
                "lot_sell": float(lot_sell_fk),
            }

            rows.append(
                [
                    InlineKeyboardButton(
                        "⛓ Arm OCO fakeout (fade+protect)",
                        callback_data=f"pend|arm_oco_fakeout|{sym}",
                    )
                ]
            )
        # === ANCHOR: PA20_FAKEOUT_CTA_END ===

        rows.append(
            [
                InlineKeyboardButton("🔄 Refresh plan", callback_data=cb_refresh),
                InlineKeyboardButton(
                    "🗑 Cancel all (chat)", callback_data=cb_cancel_all
                ),
            ]
        )

        await reply.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))
        # show the main menu afterwards
        try:
            from handlers.menu import main_menu_markup

            await reply.reply_text("What next?", reply_markup=main_menu_markup())
        except Exception:
            pass

        # Journal plan
        try:
            journal_repo: JournalRepo = context.application.bot_data["journal_repo"]
            payload = {
                "ts": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "event": "pending_plan",
                "symbol": sym,
                "direction": plan.get("direction"),
                "pending_type": plan.get("pending_type"),
                "entry": plan.get("entry"),
                "sl": plan.get("sl"),
                "tp": plan.get("tp"),
                "rr": plan.get("rr"),
                "notes": plan.get("reasoning", ""),
            }
            if hasattr(journal_repo, "write_pending"):
                journal_repo.write_pending(payload)
            elif hasattr(journal_repo, "write_exec"):
                journal_repo.write_exec(payload)
        except Exception:
            logger.debug("Journal write for pending plan failed.", exc_info=True)

    except Exception as e:
        logger.exception("Pending analyse error")
        await reply.reply_text(f"⚠️ Could not prepare pending order for {sym}: {e}")


# === ANCHOR: PA20_STOP_HELPER_START ===
def _auto_improve_stop_rr(
    plan: dict,
    pa_ctx: dict | None,
    rr_floor: float,
    tech: dict,
) -> dict:
    """
    Improve RR for STOP plans using PA zones:
      - Entry anchored close to zone breakout offset (smaller buffer if needed).
      - SL placed just beyond the opposite side of the zone (with ATR floor).
      - If still < floor and allowed, convert to retest-stop using build_retest_pending(..).
      - Optional measured-move TP nudge.

    Returns possibly-modified plan; if no safe improvement found, returns the original plan.
    """
    try:
        ptype = (plan.get("pending_type") or "").upper()
        if "STOP" not in ptype:
            return plan
        if not pa_ctx:
            return plan

        side_dir = str(plan.get("direction", "BUY")).upper()
        side = "long" if side_dir == "BUY" else "short"

        # Zone selection: for breakouts, use the boundary we're crossing
        nz = (pa_ctx or {}).get("nearest", {})
        z = nz.get("above") if side == "long" else nz.get("below")
        if not z:
            return plan

        level = float(z["level"])
        span = float(z["span"])
        entry = float(plan["entry"])
        sl = float(plan["sl"]) if plan.get("sl") is not None else None
        tp = float(plan["tp"]) if plan.get("tp") is not None else None
        atr = float(tech.get("atr_14") or 0.0)

        # Tunables (can live in settings.py)
        entry_k = float(
            getattr(settings, "PENDING_STOP_ENTRY_OFFSET_SPANS", 0.20)
        )  # distance beyond zone
        sl_k = float(
            getattr(settings, "PENDING_STOP_SL_BEYOND_SPANS", 0.40)
        )  # SL beyond opposite side
        atr_floor_mult = float(getattr(settings, "PENDING_STOP_ATR_FLOOR_MULT", 0.80))
        allow_retest_conv = bool(
            getattr(settings, "PENDING_STOP_ALLOW_RETEST_CONVERSION", True)
        )
        use_measured_move = bool(
            getattr(settings, "PENDING_STOP_USE_MEASURED_MOVE", False)
        )
        mm_mult = float(
            getattr(settings, "PENDING_STOP_MEASURED_MOVE_MULT", 1.00)
        )  # e.g., range height * 1.0

        # 1) Compute PA-anchored entry target (reduce buffer if current is "too far")
        if side == "long":
            entry_target = level + entry_k * span
            if entry < entry_target:  # ensure STOP remains a stop (>= target)
                entry = entry_target
        else:
            entry_target = level - entry_k * span
            if entry > entry_target:
                entry = entry_target

        # 2) Structure stop just beyond zone with ATR floor
        atr_floor = atr * atr_floor_mult if atr > 0 else 0.0
        if side == "long":
            struct_sl = level - sl_k * span
            if sl is None:
                sl = struct_sl
            else:
                sl = min(
                    sl, struct_sl
                )  # don't keep a looser SL if structure allows tighter
            # ATR floor: don't be tighter than (entry - atr_floor)
            if atr_floor > 0 and (entry - sl) < atr_floor:
                sl = entry - atr_floor
        else:
            struct_sl = level + sl_k * span
            if sl is None:
                sl = struct_sl
            else:
                sl = max(sl, struct_sl)
            if atr_floor > 0 and (sl - entry) < atr_floor:
                sl = entry + atr_floor

        # 3) Optional measured-move TP nudge (only if TP missing or conservative boost requested)
        if use_measured_move:
            try:
                # a simple measured move: distance from level to the opposite nearest zone (if exists)
                opp = nz.get("below") if side == "long" else nz.get("above")
                if opp:
                    height = abs(level - float(opp["level"]))
                    mm = height * mm_mult
                    if side == "long":
                        tp_mm = entry + mm
                        if tp is None or tp_mm > tp:
                            tp = tp_mm
                    else:
                        tp_mm = entry - mm
                        if tp is None or tp_mm < tp:
                            tp = tp_mm
            except Exception:
                pass

        # 4) Recompute RR
        def _rr(e, s, t):
            r = abs(e - s)
            w = abs(e - t) if (t is not None) else 0.0
            return 0.0 if r <= 0 else (w / r)

        rr_new = _rr(entry, sl, tp)
        if rr_new >= rr_floor:
            out = dict(plan)
            out["entry"] = float(entry)
            out["sl"] = float(sl)
            if tp is not None:
                out["tp"] = float(tp)
            out["rr"] = float(rr_new)
            rsn = str(out.get("reasoning", "")).strip()
            note = " STOP plan re-anchored to PA zone (entry/SL adjusted)."
            out["reasoning"] = (rsn + note) if rsn else note
            return out

        # 5) If still below floor, convert to a retest stop (if allowed)
        if allow_retest_conv:
            ret = build_retest_pending({"pa": pa_ctx}, side)
            if ret and ret.get("type") and ret.get("entry") is not None:
                entry2 = float(ret["entry"])
                # keep current TP; recompute SL around zone again for the new entry
                if side == "long":
                    sl2 = (
                        max(entry2 - atr_floor, level - sl_k * span)
                        if atr_floor > 0
                        else (level - sl_k * span)
                    )
                else:
                    sl2 = (
                        min(entry2 + atr_floor, level + sl_k * span)
                        if atr_floor > 0
                        else (level + sl_k * span)
                    )

                rr2 = _rr(entry2, sl2, tp)
                if rr2 >= rr_floor:
                    out = dict(plan)
                    out["pending_type"] = ret["type"]
                    out["entry"] = float(entry2)
                    out["sl"] = float(sl2)
                    if tp is not None:
                        out["tp"] = float(tp)
                    out["rr"] = float(rr2)
                    rsn = str(out.get("reasoning", "")).strip()
                    note = " Converted to retest STOP to meet RR floor."
                    out["reasoning"] = (rsn + note) if rsn else note
                    return out

        # No safe improvement, return original
        return plan
    except Exception:
        return plan


# === ANCHOR: PA20_STOP_HELPER_END ===


async def pendings_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    pm: PseudoPendingManager = context.application.bot_data["pending_manager"]
    tasks = pm.list_for_chat(chat_id)
    if not tasks:
        await (update.message or update.callback_query.message).reply_text(
            "No armed pendings for this chat."
        )
        # show menu
        try:
            from handlers.menu import main_menu_markup

            await (update.message or update.callback_query.message).reply_text(
                "What next?", reply_markup=main_menu_markup()
            )
        except Exception:
            pass
        return

    rows = []
    lines = ["**Armed pendings:**"]
    for t in tasks:
        lines.append(
            f"- {t.symbol} {t.pending_type.replace('_',' ').upper()} @ {fmt_price(t.symbol, t.entry)} "
            f"(SL {fmt_price(t.symbol, t.sl) if t.sl is not None else '—'}, "
            f"TP {fmt_price(t.symbol, t.tp) if t.tp is not None else '—'}) "
            f"• id={t.id}"
        )
        rows.append(
            [
                InlineKeyboardButton(
                    f"❌ Cancel {t.id}", callback_data=f"pend|cancel|{t.id}"
                )
            ]
        )

    msg = await (update.message or update.callback_query.message).reply_text(
        "\n".join(lines), reply_markup=InlineKeyboardMarkup(rows)
    )
    # show menu too
    try:
        from handlers.menu import main_menu_markup

        await msg.reply_text("What next?", reply_markup=main_menu_markup())
    except Exception:
        pass


# === ANCHOR: PEND_CB_GUARDS_START ===
def _get_pm_journal(context: ContextTypes.DEFAULT_TYPE):
    """Safe accessors for bot_data items used by callbacks."""
    pm = context.application.bot_data.get("pending_manager")
    jr = context.application.bot_data.get("journal_repo")
    return pm, jr


# === ANCHOR: PEND_PM_ADD_COMPAT_START ===
def _pm_add_compat(pm, **kwargs):
    try:
        return pm.add(**kwargs)
    except TypeError as e:
        msg = str(e)
        if "unexpected keyword argument 'volume'" in msg and "volume" in kwargs:
            v = kwargs.pop("volume")
            kwargs["lot"] = v
            return pm.add(**kwargs)
        if "unexpected keyword argument 'lot'" in msg and "lot" in kwargs:
            v = kwargs.pop("lot")
            kwargs["volume"] = v
            return pm.add(**kwargs)
        raise


# === ANCHOR: PEND_PM_ADD_COMPAT_END ===


def _debug_payload_preview(p: dict | None) -> str:
    if not p:
        return "<none>"
    try:
        keys = [
            "symbol",
            "ptype",
            "side",
            "entry",
            "sl",
            "tp",
            "lot",
            "expires_ts",
            "regime",
        ]
        mini = {k: p.get(k) for k in keys}
        return str(mini)
    except Exception:
        return "<unprintable>"


# === ANCHOR: PEND_CB_GUARDS_END ===


async def pending_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Robust callback router for 'pend|...' actions with defensive error handling."""
    query = update.callback_query
    data = (query.data or "").strip()

    try:
        logger.debug("pending cb data=%r", data)
        # Always answer quickly so Telegram UI doesn't display a wobble on slow ops.
        try:
            await query.answer("Working…", cache_time=1)
        except Exception:
            # Non-fatal; proceed.
            logger.debug("query.answer() failed", exc_info=True)

        parts = data.split("|")
        if len(parts) < 2 or parts[0] != "pend":
            return

        action = parts[1]

        if action == "refresh":
            _sym = parts[2] if len(parts) > 2 else None
            if not _sym:
                await query.message.reply_text("⚠️ Missing symbol for refresh.")
                return
            await query.message.reply_text("🔄 Refreshing plan…")
            await pending_command(update, context, symbol=_sym)
            return

        if action == "cancel_all":
            _sym = parts[2] if len(parts) > 2 else None
            pm, _ = _get_pm_journal(context)
            if pm is None:
                await query.message.reply_text(
                    "⚠️ Not ready: pending manager unavailable."
                )
                return
            armed = pm.list_for_chat(query.message.chat_id)
            n = 0
            for t in armed:
                if pm.cancel(t.id, chat_id=query.message.chat_id):
                    n += 1
            m = await query.message.reply_text(
                f"🗑 Cancelled {n} armed pending(s) for this chat."
            )
            try:
                from handlers.menu import main_menu_markup

                await m.reply_text("What next?", reply_markup=main_menu_markup())
            except Exception:
                pass
            # === ANCHOR: POSWATCH_SAVE_CHAT_OCO_START ===
            try:
                context.application.bot_data["poswatch_last_chat_id"] = (
                    query.message.chat_id
                )
            except Exception:
                pass  # === ANCHOR: POSWATCH_SAVE_CHAT_OCO_END ===
            return

        if action == "cancel":
            _id = parts[2] if len(parts) > 2 else None
            if not _id:
                await query.message.reply_text("⚠️ Missing id for cancel.")
                return
            pm, _ = _get_pm_journal(context)
            if pm is None:
                await query.message.reply_text(
                    "⚠️ Not ready: pending manager unavailable."
                )
                return
            ok = pm.cancel(_id, chat_id=query.message.chat_id)
            m = await query.message.reply_text(
                "Cancelled." if ok else "Couldn’t cancel (maybe already gone)."
            )
            try:
                from handlers.menu import main_menu_markup

                await m.reply_text("What next?", reply_markup=main_menu_markup())
            except Exception:
                pass
            # === ANCHOR: POSWATCH_SAVE_CHAT_OCO_START ===
            try:
                context.application.bot_data["poswatch_last_chat_id"] = (
                    query.message.chat_id
                )
            except Exception:
                pass
                # === ANCHOR: POSWATCH_SAVE_CHAT_OCO_END ===
            return

        if action == "armk":
            # Best-effort to disable buttons immediately
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass

            token = parts[2] if len(parts) > 2 else ""
            payload = _pop_cb(context.application, token, query.message.chat_id)
            if not payload:
                await query.message.reply_text(
                    "⚠️ This plan has expired. Please run /pending again."
                )
                # === ANCHOR: POSWATCH_SAVE_CHAT_ARMK_START ===
                try:
                    context.application.bot_data["poswatch_last_chat_id"] = (
                        query.message.chat_id
                    )
                except Exception:
                    pass
                # === ANCHOR: POSWATCH_SAVE_CHAT_ARMK_END ===

                return

            pm, journal_repo = _get_pm_journal(context)
            if pm is None:
                logger.error(
                    "pending_manager missing in bot_data; payload=%s",
                    _debug_payload_preview(payload),
                )
                await query.message.reply_text(
                    "⚠️ Not ready to arm (service unavailable). Try /pending again."
                )
                # === ANCHOR: POSWATCH_SAVE_CHAT_ARMK_START ===
                try:
                    context.application.bot_data["poswatch_last_chat_id"] = (
                        query.message.chat_id
                    )
                except Exception:
                    pass
                # === ANCHOR: POSWATCH_SAVE_CHAT_ARMK_END ===

                return

            # Validate minimal payload before pm.add
            required = ["symbol", "side", "ptype", "entry", "lot", "expires_ts"]
            missing = [k for k in required if payload.get(k) in (None, "")]
            if missing:
                logger.error(
                    "payload missing fields: %s; payload=%s",
                    missing,
                    _debug_payload_preview(payload),
                )
                await query.message.reply_text(
                    "⚠️ Plan payload incomplete. Please run /pending again."
                )
                return

            try:
                vol = float(payload.get("volume", payload.get("lot")))
                t = _pm_add_compat(
                    pm,
                    chat_id=query.message.chat_id,
                    symbol=payload["symbol"],
                    side=str(payload["side"]).lower(),
                    pending_type=payload["ptype"],
                    entry=float(payload["entry"]),
                    sl=(None if payload.get("sl") is None else float(payload["sl"])),
                    tp=(None if payload.get("tp") is None else float(payload["tp"])),
                    volume=vol,
                    expires_ts=int(payload["expires_ts"]),
                    note="armed_via_telegram",
                    regime=(payload.get("regime") or None),
                )

            except Exception as e:
                logger.exception(
                    "pm.add failed; payload=%s", _debug_payload_preview(payload)
                )
                await query.message.reply_text(
                    f"⚠️ Could not arm: {e}. Please run /pending again."
                )
                return

            # Journal (best-effort)
            try:
                row = {
                    "ts": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                    "event": "pending_armed",
                    "symbol": payload["symbol"],
                    "direction": str(payload["side"]).upper(),
                    "pending_type": payload["ptype"],
                    "entry": float(payload["entry"]),
                    "sl": (None if payload.get("sl") is None else float(payload["sl"])),
                    "tp": (None if payload.get("tp") is None else float(payload["tp"])),
                    "lot": vol,
                    "id": getattr(t, "id", None),
                }
                if journal_repo is not None:
                    if hasattr(journal_repo, "write_pending"):
                        journal_repo.write_pending(row)
                    elif hasattr(journal_repo, "write_exec"):
                        journal_repo.write_exec(row)
            except Exception:
                logger.debug("Journal write for pending arming failed.", exc_info=True)

            disp_type = str(payload["ptype"]).replace("_", " ").upper()
            entry_s = fmt_price(payload["symbol"], payload["entry"])
            sl_s = (
                fmt_price(payload["symbol"], payload["sl"])
                if payload.get("sl") is not None
                else "—"
            )
            tp_s = (
                fmt_price(payload["symbol"], payload["tp"])
                if payload.get("tp") is not None
                else "—"
            )

            m = await query.message.reply_text(
                f"🕒 Armed {payload['symbol']} {disp_type} @ {entry_s} "
                f"(SL {sl_s}, TP {tp_s}, lot {vol}). "
                f"Expires at {datetime.fromtimestamp(int(payload['expires_ts'])).strftime('%H:%M')}.\n"
                f"id={getattr(t,'id','?')} • Use /pendings to manage."
            )
            try:
                from handlers.menu import main_menu_markup

                await m.reply_text("What next?", reply_markup=main_menu_markup())
            except Exception:
                pass

            # === ANCHOR: AUTO_WATCH_FROM_PENDING_START ===
            try:
                from config import settings as _settings

                if getattr(_settings, "AUTO_WATCH_BOOTSTRAP_ON_PENDING", True):
                    watch_syms = list(
                        getattr(_settings, "AUTO_WATCH_SYMBOLS", ["XAUUSDc", "BTCUSDc"])
                    )
                    for s in watch_syms:
                        # Reuse trading’s auto-watch (same job keying & idempotency)
                        from handlers.trading import start_auto_watch

                        start_auto_watch(
                            context,
                            query.message.chat_id,
                            s,
                            reasons={"bootstrap_from_pending"},
                        )
                    logger.info("Auto-watch bootstrapped (pending) for %s", watch_syms)
            except Exception:
                logger.debug("auto-watch bootstrap (pending) failed", exc_info=True)
                # === ANCHOR: AUTO_WATCH_FROM_PENDING_END ===

            # === ANCHOR: POSWATCH_SAVE_CHAT_ARMK_START ===
            try:
                context.application.bot_data["poswatch_last_chat_id"] = (
                    query.message.chat_id
                )
            except Exception:
                pass
            # === ANCHOR: POSWATCH_SAVE_CHAT_ARMK_END ===

            return

        # === ANCHOR: PA20_ARM_OCO_START ===
        if action == "arm_oco":
            # Best-effort to disable buttons immediately
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass

            # Parse symbol from callback data: "pend|arm_oco|{sym}"
            try:
                _, _, sym = parts
            except Exception:
                await query.message.reply_text("⚠️ Couldn’t parse OCO parameters.")
                return

            # Fetch the prepared OCO breakout plans (stored by pending_command)
            oco_key = ("pending_last_oco", query.message.chat_id, sym)
            payload = context.application.bot_data.get(oco_key)
            if not payload:
                await query.message.reply_text(
                    "⚠️ No OCO breakout plan found. Please run /pending again."
                )
                return

            pm, journal_repo = _get_pm_journal(context)
            if pm is None:
                await query.message.reply_text(
                    "⚠️ Not ready to arm (service unavailable)."
                )
                # === ANCHOR: POSWATCH_SAVE_CHAT_OCO_START ===
                try:
                    context.application.bot_data["poswatch_last_chat_id"] = (
                        query.message.chat_id
                    )
                except Exception:
                    pass
                # === ANCHOR: POSWATCH_SAVE_CHAT_OCO_END ===
                return

            # Ensure MT5 connection (needed if we must compute lots as a fallback)
            mt5svc = MT5Service()
            mt5svc.connect()
            mt5svc.ensure_symbol(sym)
            risk_pct = float(getattr(settings, "RISK_DEFAULT_PCT", 1.0))

            def _lot_from_payload_or_risk(plan_leg: dict, lot_key: str) -> float:
                # Prefer lots computed in pending_command, else risk-size now
                try:
                    if lot_key in payload and payload[lot_key] is not None:
                        return float(payload[lot_key])
                except Exception:
                    pass
                try:
                    lot = mt5svc.risk_to_lot(
                        sym, float(plan_leg["entry"]), float(plan_leg["sl"]), risk_pct
                    )
                    return mt5svc.normalise_lot(sym, lot)
                except Exception:
                    return float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))

            # Extract legs
            plan_buy = payload.get("buy") or {}
            plan_sell = payload.get("sell") or {}
            expires_ts = int(payload.get("expires_ts") or (time.time() + 60 * 60))

            # Normalise types (both are stops for breakout OCO)
            ptype1 = plan_buy.get("pending_type") or "BUY_STOP"
            ptype2 = plan_sell.get("pending_type") or "SELL_STOP"

            # Lots (prefer precomputed)
            lot_buy = _lot_from_payload_or_risk(plan_buy, "lot_buy")
            lot_sell = _lot_from_payload_or_risk(plan_sell, "lot_sell")

            # Group the two legs so the manager can cancel the opposite one on fill
            group_id = uuid.uuid4().hex[:8]

            # Arm the BUY leg
            t1 = _pm_add_compat(
                pm,
                chat_id=query.message.chat_id,
                symbol=sym,
                side="buy",
                pending_type=ptype1,
                entry=float(plan_buy.get("entry")),
                sl=(None if plan_buy.get("sl") is None else float(plan_buy.get("sl"))),
                tp=(None if plan_buy.get("tp") is None else float(plan_buy.get("tp"))),
                volume=float(lot_buy),
                expires_ts=int(expires_ts),
                note="armed_via_telegram_oco_breakout",
                oco_group=group_id,
                regime=(plan_buy.get("regime") or None),
            )

            # Arm the SELL leg  (NOTE: volume=lot_sell here)
            t2 = _pm_add_compat(
                pm,
                chat_id=query.message.chat_id,
                symbol=sym,
                side="sell",
                pending_type=ptype2,
                entry=float(plan_sell.get("entry")),
                sl=(
                    None if plan_sell.get("sl") is None else float(plan_sell.get("sl"))
                ),
                tp=(
                    None if plan_sell.get("tp") is None else float(plan_sell.get("tp"))
                ),
                volume=float(lot_sell),
                expires_ts=int(expires_ts),
                note="armed_via_telegram_oco_breakout",
                oco_group=group_id,
                regime=(plan_sell.get("regime") or None),
            )

            # Journal both legs
            lot1 = getattr(t1, "volume", getattr(t1, "lot", None))
            lot2 = getattr(t2, "volume", getattr(t2, "lot", None))
            try:
                if journal_repo is not None:
                    for t in (t1, t2):
                        row = {
                            "ts": datetime.utcnow().replace(microsecond=0).isoformat()
                            + "Z",
                            "event": "pending_armed_oco",
                            "symbol": t.symbol,
                            "direction": t.side.upper(),
                            "pending_type": t.pending_type,
                            "entry": t.entry,
                            "sl": t.sl,
                            "tp": t.tp,
                            "lot": getattr(t, "volume", getattr(t, "lot", None)),
                            "id": getattr(t, "id", None),
                            "oco_group": group_id,
                        }
                        if hasattr(journal_repo, "write_pending"):
                            journal_repo.write_pending(row)
                        elif hasattr(journal_repo, "write_exec"):
                            journal_repo.write_exec(row)
            except Exception:
                logger.debug(
                    "Journal write for OCO breakout arming failed.", exc_info=True
                )

            # User-facing confirmation
            m = await query.message.reply_text(
                "⛓ OCO (breakout) armed:\n"
                f"• {ptype1.replace('_',' ').upper()} @ {fmt_price(sym, t1.entry)} "
                f"(SL {fmt_price(sym, t1.sl) if t1.sl is not None else '—'}, "
                f"TP {fmt_price(sym, t1.tp) if t1.tp is not None else '—'}, "
                f"lot {getattr(t1, 'volume', getattr(t1, 'lot', '?'))})\n"
                f"• {ptype2.replace('_',' ').upper()} @ {fmt_price(sym, t2.entry)} "
                f"(SL {fmt_price(sym, t2.sl) if t2.sl is not None else '—'}, "
                f"TP {fmt_price(sym, t2.tp) if t2.tp is not None else '—'}, "
                f"lot {getattr(t2, 'volume', getattr(t2, 'lot', '?'))})\n"
                f"Group: {group_id}. First to trigger fills; the other is cancelled.\n"
                f"Use /pendings to cancel individually."
            )
            try:
                from handlers.menu import main_menu_markup

                await m.reply_text("What next?", reply_markup=main_menu_markup())
            except Exception:
                pass

            # Stash chat id for poswatch notifications
            # === ANCHOR: POSWATCH_SAVE_CHAT_OCO_START ===
            try:
                context.application.bot_data["poswatch_last_chat_id"] = (
                    query.message.chat_id
                )
            except Exception:
                pass
            # === ANCHOR: POSWATCH_SAVE_CHAT_OCO_END ===

            return
        # === ANCHOR: PA20_ARM_OCO_END ===

        # === ANCHOR: PA20_ARM_OCO_FAKE_START ===
        if action == "arm_oco_fakeout":
            # keep your existing body below unchanged
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
            try:
                _, _, sym = parts
            except Exception:
                await query.message.reply_text("⚠️ Couldn’t parse OCO parameters.")
                return
            oco_key_fake = ("pending_last_oco_fake", query.message.chat_id, sym)
            payload = context.application.bot_data.get(oco_key_fake)
            if not payload:
                await query.message.reply_text(
                    "⚠️ No fakeout OCO plan found. Please run /pending again."
                )
                return
            pm, journal_repo = _get_pm_journal(context)
            if pm is None:
                await query.message.reply_text(
                    "⚠️ Not ready to arm (service unavailable)."
                )
                # === ANCHOR: POSWATCH_SAVE_CHAT_OCO_START ===
                try:
                    context.application.bot_data["poswatch_last_chat_id"] = (
                        query.message.chat_id
                    )
                except Exception:
                    pass
                # === ANCHOR: POSWATCH_SAVE_CHAT_OCO_END ===

                return

            # Ensure MT5 for lot sizing
            mt5svc = MT5Service()
            mt5svc.connect()
            mt5svc.ensure_symbol(sym)

            def _lot_for(plan_leg: dict) -> float:
                try:
                    lot = mt5svc.risk_to_lot(
                        sym,
                        float(plan_leg["entry"]),
                        float(plan_leg["sl"]),
                        float(getattr(settings, "RISK_DEFAULT_PCT", 1.0)),
                    )
                    return mt5svc.normalise_lot(sym, lot)
                except Exception:
                    return float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))

            plan_buy = payload["buy"]
            plan_sell = payload["sell"]
            # Prefer lots computed in pending_command, else fallback sizing
            lot_buy = float(payload.get("lot_buy") or 0)
            lot_sell = float(payload.get("lot_sell") or 0)

            if not lot_buy:
                lot_buy = _lot_for(plan_buy)
            if not lot_sell:
                lot_sell = _lot_for(plan_sell)

            group_id = uuid.uuid4().hex[:8]
            ptype1 = plan_buy.get("pending_type") or "BUY_STOP"
            ptype2 = plan_sell.get("pending_type") or "SELL_STOP"

            t1 = _pm_add_compat(
                pm,
                chat_id=query.message.chat_id,
                symbol=sym,
                side="buy",
                pending_type=ptype1,
                entry=float(plan_buy.get("entry")),
                sl=(None if plan_buy.get("sl") is None else float(plan_buy.get("sl"))),
                tp=(None if plan_buy.get("tp") is None else float(plan_buy.get("tp"))),
                volume=float(lot_buy),
                expires_ts=int(payload["expires_ts"]),
                note="armed_via_telegram_oco_fakeout",
                oco_group=group_id,
                regime=(plan_buy.get("regime") or None),
            )

            t2 = _pm_add_compat(
                pm,
                chat_id=query.message.chat_id,
                symbol=sym,
                side="sell",
                pending_type=ptype2,
                entry=float(plan_sell.get("entry")),
                sl=(
                    None if plan_sell.get("sl") is None else float(plan_sell.get("sl"))
                ),
                tp=(
                    None if plan_sell.get("tp") is None else float(plan_sell.get("tp"))
                ),
                volume=float(lot_sell),
                expires_ts=int(payload["expires_ts"]),
                note="armed_via_telegram_oco_fakeout",
                oco_group=group_id,
                regime=(plan_sell.get("regime") or None),
            )

            try:
                lot1 = getattr(t1, "volume", getattr(t1, "lot", None))
                lot2 = getattr(t2, "volume", getattr(t2, "lot", None))
                if journal_repo is not None:
                    for t in (t1, t2):
                        row = {
                            "ts": datetime.utcnow().replace(microsecond=0).isoformat()
                            + "Z",
                            "event": "pending_armed_oco_fakeout",
                            "symbol": t.symbol,
                            "direction": t.side.upper(),
                            "pending_type": t.pending_type,
                            "entry": t.entry,
                            "sl": t.sl,
                            "tp": t.tp,
                            "lot": getattr(t, "volume", getattr(t, "lot", None)),
                            "id": t.id,
                            "oco_group": group_id,
                        }
                        if hasattr(journal_repo, "write_pending"):
                            journal_repo.write_pending(row)
                        elif hasattr(journal_repo, "write_exec"):
                            journal_repo.write_exec(row)
            except Exception:
                logger.debug(
                    "Journal write for OCO fakeout arming failed.", exc_info=True
                )

            m = await query.message.reply_text(
                "⛓ OCO (fakeout) armed:\n"
                f"• {ptype1.replace('_',' ').upper()} @ {fmt_price(sym, t1.entry)} "
                f"(SL {fmt_price(sym, t1.sl) if t1.sl is not None else '—'}, "
                f"TP {fmt_price(sym, t1.tp) if t1.tp is not None else '—'}, "
                f"lot {getattr(t1, 'volume', getattr(t1, 'lot', '?'))})\n"
                f"• {ptype2.replace('_',' ').upper()} @ {fmt_price(sym, t2.entry)} "
                f"(SL {fmt_price(sym, t2.sl) if t2.sl is not None else '—'}, "
                f"TP {fmt_price(sym, t2.tp) if t2.tp is not None else '—'}, "
                f"lot {getattr(t2, 'volume', getattr(t2, 'lot', '?'))})\n"
                f"Group: {group_id}. First to trigger fills; the other is cancelled.\n"
                f"Use /pendings to cancel individually."
            )

            try:
                from handlers.menu import main_menu_markup

                await m.reply_text("What next?", reply_markup=main_menu_markup())
            except Exception:
                pass
            # Stash chat id for poswatch notifications (fakeout variant too)
            # === ANCHOR: POSWATCH_SAVE_CHAT_OCO_START ===
            try:
                context.application.bot_data["poswatch_last_chat_id"] = (
                    query.message.chat_id
                )
            except Exception:
                pass
            # === ANCHOR: POSWATCH_SAVE_CHAT_OCO_END ===
            return
        # === ANCHOR: PA20_ARM_OCO_FAKE_END ===

    except Exception:
        # Final catch-all so Telegram never shows the wobble again
        logger.exception("pending_callbacks crashed; data=%r", data)
        try:
            await query.message.reply_text(
                "⚠️ Something went wrong while handling your action. Please run /pending again."
            )
        except Exception:
            pass
        return
