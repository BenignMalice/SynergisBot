# =====================================
# handlers/trading.py
# =====================================
from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from html import escape as _hesc
import re
import html
import math
import asyncio
from functools import partial
import pandas as pd
import MetaTrader5 as mt5
from telegram.constants import ParseMode
from config import settings

# Optional staged activation import
try:
    from infra.staged_activation_system import get_position_size_multiplier as _get_sa_multiplier
except Exception:
    _get_sa_multiplier = None

def _apply_staged_multiplier(lot: float) -> float:
    try:
        if _get_sa_multiplier:
            m = float(_get_sa_multiplier())
            if m > 0:
                return lot * m
    except Exception:
        pass
    return lot
from domain.rules import build_confidence, normalise_direction
from domain.candles import detect_recent_patterns
from infra.indicator_bridge import IndicatorBridge
from infra.mt5_service import MT5Service
from infra.openai_service import OpenAIService
from infra.chart_arranger import ChartArranger
from infra.journal_repo import JournalRepo
from infra.formatting import fmt_price
from infra.threshold_tuner import ThresholdTuner

# --- new infra modules for advanced decisioning ---
from infra.strategy_selector import StrategySelector
from infra.memory_store import MemoryStore
from infra.risk_simulation import simulate as simulate_risk
from infra.guardrails import risk_ok, exposure_ok, news_ok, slippage_ok
from infra.news_service import NewsService
from infra.confidence_calibrator import ConfidenceCalibrator
from infra.postmortem import build_postmortem_text
from decision_engine import decide_trade
from app.engine.risk_model import map_risk_pct  # << risk mapping
from app.engine.risk_model import ensure_orientation  # << orientation guard
try:
    from app.engine.strategy_logic import choose_and_build, compute_mtf_confluence
except Exception:
    from app.engine.strategy_logic import choose_and_build
    def compute_mtf_confluence(_tech: dict) -> dict:
        return {'score':0.0,'bias':None,'details':{}}

from infra.bandit_autoupdate import wire_bandit_updates

logger = logging.getLogger("handlers.trading")
logger.setLevel(logging.DEBUG)
logger.propagate = True
logger.info(
    "handlers.trading imported, eff=%s",
    logging.getLevelName(logger.getEffectiveLevel()),
)
print(
    f"[PRINT] handlers.trading import, eff={logging.getLevelName(logger.getEffectiveLevel())}"
)


LAST_REC: dict[tuple[int, str], dict] = {}
_DEF_SYMBOL = "XAUUSDc"

# Short-lived bucket for compact callback payloads
_CB_BUCKET = "cb_payloads"


def _to_scalar(val):
    """
    Helper to extract scalar from potential array (for IndicatorBridge fallback compatibility).
    When IndicatorBridge uses fallback, values may be arrays instead of scalars.
    """
    if val is None:
        return 0.0
    if isinstance(val, (list, tuple)):
        return float(val[-1]) if len(val) > 0 else 0.0
    return float(val)

# ---- auto-watch configuration ----
# When the critic suggests waiting for breakout or confluence, we start a
# background watcher job per (chat_id, symbol) that re-runs analysis at
# regular intervals until a valid trade emerges or a timeout occurs.  These
# values can be configured via settings (AUTO_WATCH_INTERVAL_SEC and
# AUTO_WATCH_TIMEOUT_SEC) and default to 300s interval and 3600s timeout.
try:
    AUTO_WATCH_INTERVAL_SEC = int(getattr(settings, "AUTO_WATCH_INTERVAL_SEC", 300))
    AUTO_WATCH_TIMEOUT_SEC = int(getattr(settings, "AUTO_WATCH_TIMEOUT_SEC", 3600))
except Exception:
    AUTO_WATCH_INTERVAL_SEC = 300
    AUTO_WATCH_TIMEOUT_SEC = 3600

# In-memory registry of active auto-watch jobs keyed by (chat_id, symbol).  Each
# entry holds a PTB Job instance so we can cancel and inspect it.  Jobs
# maintain their own data (start_time, attempts, reasons) via job.data.
_AUTO_WATCH_JOBS: dict[tuple[int, str], Any] = {}


async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /monitor
    - Lists active auto-watch jobs for this chat.
    - Usage: /monitor stop SYMBOL  (cancels one)
             /monitor stopall       (cancels all for this chat)
    """
    msg = update.message or (
        update.callback_query.message if update.callback_query else None
    )
    chat_id = update.effective_chat.id
    text = (update.message.text if update.message else "").strip() if update else ""

    # Parse subcommands
    args = text.split()[1:] if text else []
    if args:
        sub = args[0].lower()
        if sub == "stopall":
            # Cancel all jobs for this chat
            stopped = 0
            to_del = []
            for (cid, sym), job in list(_AUTO_WATCH_JOBS.items()):
                if cid == chat_id:
                    try:
                        job.schedule_removal()
                    except Exception:
                        pass
                    to_del.append((cid, sym))
                    stopped += 1
            for k in to_del:
                _AUTO_WATCH_JOBS.pop(k, None)
            if msg:
                await msg.reply_text(
                    f"🛑 Stopped {stopped} auto-watch job(s) for this chat."
                )
            return
        if sub == "stop" and len(args) >= 2:
            sym = normalise_symbol(args[1])
            job = _AUTO_WATCH_JOBS.pop((chat_id, sym), None)
            if job:
                try:
                    job.schedule_removal()
                except Exception:
                    pass
                if msg:
                    await msg.reply_text(f"🛑 Stopped auto-watch for {sym}.")
            else:
                if msg:
                    await msg.reply_text(f"ℹ️ No active auto-watch found for {sym}.")
            return

    # Otherwise: list active jobs
    # build list
    items = [
        (cid, sym, job)
        for (cid, sym), job in _AUTO_WATCH_JOBS.items()
        if cid == chat_id
    ]

    if not items:
        await msg.reply_text("😴 No active auto-watch jobs for this chat.")
        return

    lines = ["👀 Active auto-watch jobs:"]
    now = time.time()
    for _, sym, job in items:
        d = getattr(job, "data", {}) or {}
        started = float(d.get("start_time", now))
        age_s = int(now - started)

        expires = d.get("expires_at")
        exp_txt = ""
        if isinstance(expires, (int, float)):
            left = int(max(0, float(expires) - now))
            exp_txt = f" | expires in {_fmt_secs(left)}"

        reasons = d.get("reasons") or []
        lines.append(
            f"• {sym} | age {age_s}s{exp_txt} | reasons={', '.join(reasons[:3]) or '—'}"
        )

    await msg.reply_text("\n".join(lines))


def start_auto_watch(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    symbol: str,
    reasons: list[str] | None = None,
):
    """Start (or restart) an auto-watch job for (chat_id, symbol)."""
    try:
        symbol = normalise_symbol(symbol)
        # Cancel existing
        existing = _AUTO_WATCH_JOBS.pop((chat_id, symbol), None)
        if existing:
            try:
                existing.schedule_removal()
            except Exception:
                pass

        # Schedule new
        job = context.job_queue.run_repeating(
            _auto_watch_tick,
            interval=AUTO_WATCH_INTERVAL_SEC,
            first=AUTO_WATCH_INTERVAL_SEC,
            data={
                "chat_id": chat_id,
                "symbol": symbol,
                "start_time": time.time(),
                "expires_at": time.time() + float(AUTO_WATCH_TIMEOUT_SEC),  # <-- add
                "reasons": reasons or [],
            },
            name=f"watch:{chat_id}:{symbol}",
        )
        _AUTO_WATCH_JOBS[(chat_id, symbol)] = job
    except Exception as e:
        logger.debug("start_auto_watch failed: %s", e)


async def pending_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not query or not query.data:
        return

    try:
        _, cmd, token = query.data.split("|", 2)
    except ValueError:
        await query.message.reply_text("⚠️ Bad pending callback payload.")
        return

    chat_id = update.effective_chat.id
    payload = _pop_cb(context.application, token, chat_id)
    if not payload:
        await query.message.reply_text("⚠️ This action expired. Please /trade again.")
        return

    sym = normalise_symbol(payload.get("symbol") or _DEF_SYMBOL)

    # Fresh tech + plan
    try:
        _, tech = _extract_bridge_and_tech(sym)
    except Exception:
        tech = {}
    state = LAST_REC.get((chat_id, sym), {}) or {}
    plan_obj = tech.get("strategy_plan") or tech.get("strategy_plan_preview") or {}

    if cmd == "plan":
        rec = (state.get("rec") or {}) | {
            "direction": (payload.get("side") or "buy").upper(),
            "entry": payload.get("entry"),
            "sl": payload.get("sl"),
            "tp": payload.get("tp"),
            "regime": state.get("regime") or tech.get("regime") or "RANGE",
            "rr": state.get("rr"),
        }
        await _send_pending_plan_message(update, context, query.message, sym, rec, tech)
        return

    if cmd == "place":
        # --- Place a single pending (STOP/LIMIT inferred from entry vs bid/ask)
        try:
            side = (payload.get("side") or "buy").lower()
            entry = float(payload.get("entry") or 0.0)
            sl = payload.get("sl")
            tp = payload.get("tp")
            if not entry or sl is None or tp is None:
                await query.message.reply_text("❌ Levels missing for pending order.")
                return

            # Connect + ensure symbol
            mt5svc = MT5Service()
            await _in_thread(mt5svc.connect)
            await _in_thread(mt5svc.ensure_symbol, sym)

            # Live quote (also used to sanity-check side vs levels)
            try:
                q = await _in_thread(mt5svc.get_quote, sym)
                bid, ask = q.bid, q.ask
            except Exception:
                bid = ask = None

            # If levels imply the opposite side, correct it
            if not _levels_match_side_by_entry(side, entry, sl, tp):
                side_inferred = _infer_side_from_levels(entry, sl, tp)
                if side_inferred:
                    side = side_inferred

            # Risk→lot (risk_pct is stored in LAST_REC from your analysis)
            risk_pct = LAST_REC.get((chat_id, sym), {}).get("risk_pct_mapped")
            if not isinstance(risk_pct, (int, float)):
                risk_pct = float(getattr(settings, "RISK_DEFAULT_PCT", 1.0))

            if sl is None:
                lot = float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))
            else:
                lot = await _in_thread(
                    mt5svc.risk_to_lot, sym, entry, float(sl), risk_pct
                )
                lot = await _in_thread(mt5svc.normalise_lot, sym, lot)

            # Place pending (open_order decides STOP/LIMIT from entry vs. market)
            res = await asyncio.wait_for(
                _in_thread(
                    mt5svc.open_order,
                    sym,
                    side,
                    entry=entry,
                    sl=sl,
                    tp=tp,
                    lot=lot,
                    risk_pct=None,
                ),
                timeout=12,
            )
            if not res.get("ok"):
                await query.message.reply_text(
                    f"❌ Pending failed: {res.get('message') or 'unknown error'}"
                )
                return

            txt = _render_execution_message(sym, f"{side} (pending)", risk_pct, res)
            await query.message.reply_text(txt)

        except Exception as e:
            await query.message.reply_text(f"⚠️ Pending error: {type(e).__name__}: {e}")
        return

    if cmd == "arm_oco":
        try:
            await _place_oco_breakout(
                update, context, chat_id, sym, plan_obj, payload, tech
            )
        except Exception as e:
            await query.message.reply_text(f"❌ OCO error: {type(e).__name__}: {e}")
        return


async def _run_full_analysis_and_notify(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, sym: str
) -> bool:
    """
    Re-runs the full trade analysis (gate + LLM + critic + guardrails), updates LAST_REC,
    sends a fresh plan with buttons, and returns True if the plan is actionable
    (BUY/SELL and critic-approved), otherwise False.
    """
    logger.info("ENTER _run_full_analysis_and_notify chat_id=%s sym=%s", chat_id, sym)
    print(f"[PRINT] ENTER _run_full_analysis_and_notify chat_id={chat_id} sym={sym}")

    sym = normalise_symbol(sym)
    try:
        # Services
        mt5svc = MT5Service()
        mt5svc.connect()
        mt5svc.ensure_symbol(sym)
        bridge = IndicatorBridge(settings.MT5_FILES_DIR)
        oai = OpenAIService(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)

        multi = bridge.get_multi(sym)
        m5 = multi.get("M5", {})
        m15 = multi.get("M15", {})
        m30 = multi.get("M30", {})
        h1 = multi.get("H1", {})

        # IMPROVED: Use Feature Builder for enhanced analysis
        try:
            from infra.feature_builder import build_features
            feature_data = build_features(sym, mt5svc, bridge)
            if feature_data and feature_data.get("symbol") == sym:
                # Merge feature builder data into tech
                tech, m5_df, m15_df = _build_tech_from_bridge(multi, sym)
                tech.update(feature_data)  # Add feature builder data
                logger.info(f"Feature builder data integrated for {sym}")
            else:
                tech, m5_df, m15_df = _build_tech_from_bridge(multi, sym)
                logger.warning(f"Feature builder data not available for {sym}, using fallback")
        except Exception as e:
            logger.warning(f"Feature builder integration failed for {sym}: {e}")
            tech, m5_df, m15_df = _build_tech_from_bridge(multi, sym)
        # ---- Dynamic threshold knobs (surface to GPT)
        try:
            tuner = ThresholdTuner(
                getattr(settings, "THRESHOLD_TUNER_PATH", "threshold_tuner.json")
            )
            tech["knob_state"] = tuner.get_knob_state(sym, "M5")
        except Exception:
            pass

        # ---- Contextual bandit: choose playbook (deterministic; GPT explains in 'reasoning')
        try:
            selector = StrategySelector(
                getattr(settings, "STRATEGY_SELECTOR_PATH", "strategy_selector.json")
            )
            rsi_align = 0.0
            try:
                r5 = float(
                    tech.get("_tf_M5", {}).get("rsi_14") or tech.get("rsi_14") or 50.0
                )
                r15 = float(tech.get("_tf_M15", {}).get("rsi_14") or 50.0)
                rsi_align = (
                    1.0
                    if (r5 >= 55 and r15 >= 55)
                    else (-1.0 if (r5 <= 45 and r15 <= 45) else 0.0)
                )
            except Exception:
                pass
            feat = {
                "adx": tech.get("adx"),
                "bb_width": tech.get("bb_width"),
                "rsi_align": rsi_align,
                "spike_up": "SPIKE_UP" in (tech.get("triggers") or []),
                "spike_dn": "SPIKE_DOWN" in (tech.get("triggers") or []),
                "session": tech.get("session") or tech.get("_tf_M5", {}).get("session"),
            }
            sel = selector.select(sym, feat)
            if isinstance(sel, tuple):
                picked, dbg = sel
            else:
                picked, dbg = sel, {}
            if picked:
                tech["suggested_strategy"] = picked
            if dbg:
                tech["strategy_selector_debug"] = dbg
        except Exception:
            pass

        # Range state
        rs_all: dict = context.application.bot_data.get("range_state", {})
        rs_sym: dict = rs_all.get(sym, {})

        # 1) Gate (rule engine)
        gate_rec = decide_trade(
            sym, m5, m15, m30, h1, m5_df=m5_df, m15_df=m15_df, range_state=rs_sym
        )
        if "range_state" in gate_rec:
            rs_all[sym] = gate_rec["range_state"]
            context.application.bot_data["range_state"] = rs_all
            gate_rec.pop("range_state", None)

        tech["gate_strategy"] = gate_rec.get("strategy")

        # --- Strategy plan (rule-driven entries: STOP/LIMIT/OCO + SL/TP) ---
        try:
            logger.debug(
                "calling choose_and_build: sym=%s regime=%s",
                sym,
                gate_rec.get("regime"),
            )
            print(
                f"[PRINT] calling choose_and_build sym={sym} regime={gate_rec.get('regime')}"
            )
        except Exception:
            pass

        plan = choose_and_build(
            sym, {**tech, "regime": gate_rec.get("regime")}, mode="market"
        )

        try:
            logger.debug("choose_and_build returned: %s", "PLAN" if plan else "None")
            print(f"[PRINT] choose_and_build returned: {'PLAN' if plan else 'None'}")
        except Exception:
            pass

        if plan:
            order_side = "BUY" if str(plan.direction).upper() == "LONG" else "SELL"
            tech["strategy_plan"] = {
                "strategy": plan.strategy,
                "direction": plan.direction,
                "order_side": order_side,  # <-- add this
                "pending_type": plan.pending_type,
                "entry": plan.entry,
                "sl": plan.sl,
                "tp": plan.tp,
                "rr": plan.rr,
                "ttl_min": plan.ttl_min,
                "oco_companion": plan.oco_companion,
                "notes": plan.notes,
            }

            # --- Best-strategy PREVIEW (ignore spread/news so we can still show a candidate) ---
        if "strategy_plan" not in tech:
            try:
                tech_preview = dict(tech)
                # neutralise blockers for preview only
                tech_preview["minutes_to_next_news"] = 999
                tech_preview["_live_spread"] = 0.0
                tech_preview["spread_pts"] = 0.0
                preview = choose_and_build(
                    sym,
                    {**tech_preview, "regime": gate_rec.get("regime")},
                    mode="market",
                )

                if preview:
                    tech["strategy_plan_preview"] = {
                        "strategy": preview.strategy,
                        "direction": preview.direction,
                        "pending_type": preview.pending_type,
                        "entry": preview.entry,
                        "sl": preview.sl,
                        "tp": preview.tp,
                        "rr": preview.rr,
                        "ttl_min": preview.ttl_min,
                        "oco_companion": preview.oco_companion,
                        "notes": preview.notes,
                        "preview": True,
                        # blocked_by will be filled later once we know guard reasons
                    }
            except Exception:
                pass

        # --- Journal the strategy plan (optional) ---
        try:
            jr = context.application.bot_data.get("journal_repo")
            if jr and plan:
                import time as _t

                jr.write_event(
                    "strategy_plan",
                    ts=int(_t.time()),
                    symbol=sym,
                    strategy=plan.strategy,
                    direction=plan.direction,
                    pending_type=plan.pending_type,
                    entry=plan.entry,
                    sl=plan.sl,
                    tp=plan.tp,
                    rr=plan.rr,
                    ttl_min=plan.ttl_min,
                )
        except Exception:
            pass

        # ---- Retrieve similar past cases (after gate so we include regime/session/pattern_bias)
        try:
            ms = MemoryStore(
                getattr(settings, "MEMORY_STORE_PATH", "memory_store.sqlite")
            )
            snapshot = {
                "adx": float(tech.get("adx") or 0.0),
                "atr_14": float(tech.get("atr_14") or 0.0),
                "bb_width": float(tech.get("bb_width") or 0.0),
                "ema_slope_h1": float(tech.get("ema_slope_h1") or 0.0),
                "rsi_14": float(tech.get("rsi_14") or 0.0),
                "pattern_bias": int(tech.get("pattern_bias") or 0),
                "regime": str(gate_rec.get("regime") or tech.get("regime") or ""),
                "session": tech.get("session") or tech.get("_tf_M5", {}).get("session"),
            }
            cases = ms.retrieve(sym, snapshot, k=20)
            condensed = []
            for c in cases:
                snap = c.get("snapshot", {}) or {}
                outc = c.get("outcome", {}) or {}
                condensed.append(
                    {
                        "snapshot": {
                            "adx": snap.get("adx"),
                            "atr_14": snap.get("atr_14"),
                            "bb_width": snap.get("bb_width"),
                            "rsi_14": snap.get("rsi_14"),
                            "pattern_bias": snap.get("pattern_bias"),
                            "regime": snap.get("regime"),
                            "session": snap.get("session"),
                        },
                        "outcome": {
                            "hit": outc.get("hit"),
                            "pnl": outc.get("pnl"),
                            "duration_min": outc.get("duration_min"),
                        },
                    }
                )
            tech["similar_cases"] = condensed
        except Exception:
            pass

        try:
            wire_bandit_updates(journal_repo)  # NEW: auto-learn from closures
        except Exception:
            pass

        # 2) LLM recommend
        fundamentals = load_daily_fundamentals()
        llm_rec = oai.recommend(sym, tech, fundamentals)

        # 3) Merge
        final = _merge_gate_llm(gate_rec, llm_rec)

        # ===== 4) Post-merge Critic (final say) + S/R anchor validation
        verdict = oai.critique(
            final,
            tech,
            rules={
                "MIN_RR_FOR_MARKET": float(getattr(settings, "MIN_RR_FOR_MARKET", 1.2)),
                "max_spread_pct_atr": float(
                    getattr(settings, "MAX_SPREAD_PCT_ATR", 0.35)
                ),
            },
        )
        final["critic_approved"] = verdict["approved"]
        final["critic_reasons"] = verdict["reasons"]

        # S/R anchor validation (enforce band anchoring even if LLM skipped it)
        ok_anchor, anchor_reasons, final_adjusted = _validate_sr_anchor(final, tech)
        if not ok_anchor:
            final = final_adjusted
            rsn = [f"sr_anchor:{r}" for r in anchor_reasons]
            final["critic_approved"] = False
            final["critic_reasons"] = list(
                set((final.get("critic_reasons") or []) + rsn)
            )

        if not final.get("critic_approved"):
            final["direction"] = "HOLD"
            guards = set(final.get("guards", []))
            guards.update(
                [f"critic:{r}" for r in (final.get("critic_reasons") or [])[:3]]
            )
            final["guards"] = sorted(guards)

        # Tag critic reasons into guards for visibility
        try:
            guards = list(final.get("guards", []) or [])
            for r in final["critic_reasons"]:
                guards.append(f"critic:{r}")
            final["guards"] = sorted(set(guards))
        except Exception:
            pass

        # Guardrails
        try:
            ok, reason = risk_ok(final)
            if not ok:
                final["direction"] = "HOLD"
                gs = set(final.get("guards") or [])
                gs.add(f"risk_guard:{reason}")
                final["guards"] = sorted(gs)
        except Exception:
            pass
        try:
            ok, reason = exposure_ok(
                {
                    "symbol": sym,
                    "direction": final.get("direction"),
                    "journal_repo": context.application.bot_data.get("journal_repo"),
                }
            )
            if not ok:
                final["direction"] = "HOLD"
                gs = set(final.get("guards") or [])
                gs.add(f"exposure_guard:{reason}")
                final["guards"] = sorted(gs)
        except Exception:
            pass
        try:
            ok, reason = news_ok(sym)
            if not ok:
                final["direction"] = "HOLD"
                gs = set(final.get("guards") or [])
                gs.add(f"news_guard:{reason}")
                final["guards"] = sorted(gs)
        except Exception:
            pass
        try:
            ok, reason = slippage_ok(sym)
            if not ok:
                final["direction"] = "HOLD"
                gs = set(final.get("guards") or [])
                gs.add(f"spread_guard:{reason}")
                final["guards"] = sorted(gs)
        except Exception:
            pass
            # --- If we only had a PREVIEW plan, tag why it’s blocked (for display) ---
        try:
            if "strategy_plan" not in tech and "strategy_plan_preview" in tech:
                blocked = []
                if not final.get("critic_approved"):
                    blocked.append("critic")
                for g in final.get("guards") or []:
                    if str(g).startswith("news_guard:"):
                        blocked.append("news")
                    elif str(g).startswith("spread_guard:"):
                        blocked.append("spread")
                    elif str(g).startswith("risk_guard:"):
                        blocked.append("risk")
                    elif str(g).startswith("exposure_guard:"):
                        blocked.append("exposure")
                # If gate itself was idle / HOLD
                if str(final.get("direction", "")).upper() == "HOLD":
                    blocked.append("hold")
                tech["strategy_plan_preview"]["blocked_by"] = (
                    sorted(set(blocked)) or None
                )
        except Exception:
            pass

        # Confidence (+ calibration)
        base_conf = build_confidence(tech)
        try:
            rr_gate = float(gate_rec.get("rr", 1.0))
            rr_final = float(final.get("rr", 0.0))
            same_side = (
                str(gate_rec.get("direction", "")).upper() in ("BUY", "SELL")
                and str(final.get("direction", "")).upper()
                == str(gate_rec.get("direction", "")).upper()
            )
            bump = 4 if same_side and rr_final >= rr_gate else 0
        except Exception:
            bump = 0
        confidence = max(1, min(99, base_conf + bump))
        try:
            calibrator = ConfidenceCalibrator(settings.CALIBRATOR_PATH)
            calibrated = calibrator.calibrate(confidence)
            if calibrated is not None:
                confidence = int(min(99, max(1, calibrated)))
        except Exception:
            pass

        # Risk % mapping (save to state)
        atr_val = float(tech.get("atr_14") or 0.0)
        spread = float(tech.get("_live_spread") or 0.0)
        spread_pct_atr = (spread / atr_val) if atr_val > 0 else 0.0
        base_pct = float(getattr(settings, "RISK_DEFAULT_PCT", 1.0))
        risk_pct_mapped = map_risk_pct(
            base_pct=base_pct,
            confidence=confidence,
            adx=float(tech.get("adx") or 0.0),
            spread_pct_atr=spread_pct_atr,
            minutes_to_news=None,
            min_pct=float(getattr(settings, "RISK_MIN_PCT", 0.2)),
            max_pct=float(getattr(settings, "RISK_MAX_PCT", 2.0)),
        )

        # Save analysis to LAST_REC (used by /critic and by execution flow)
        LAST_REC[(chat_id, sym)] = {
            "rec": final,
            "symbol": sym,
            "confidence": confidence,
            "regime": final.get("regime") or tech.get("regime"),
            "rr": final.get("rr"),
            "notes": final.get("reasoning", ""),
            "strategy": gate_rec.get("strategy"),
            "risk_pct_mapped": risk_pct_mapped,
            # <-- add this:
            "rec_tech": {
                "adx": float(tech.get("adx") or 0.0),
                "atr_14": float(tech.get("atr_14") or 0.0),
                "bb_width": float(tech.get("bb_width") or 0.0),
                "ema_slope_h1": float(tech.get("ema_slope_h1") or 0.0),
                "rsi_14": float(tech.get("rsi_14") or 0.0),
                "pattern_bias": int(tech.get("pattern_bias") or 0),
                "session": tech.get("session") or tech.get("_tf_M5", {}).get("session"),
            },
        }

        # Pull a fresh quote for the live line
        live_bid = live_ask = None
        mk_closed = False
        try:
            q = mt5svc.get_quote(sym)
            live_bid, live_ask = q.bid, q.ask
            mk_closed = _market_looks_closed(sym)
        except Exception:
            pass

        # ---- MemoryStore: save this recommendation snapshot for future retrieval
        try:
            ms = MemoryStore(
                getattr(settings, "MEMORY_STORE_PATH", "memory_store.sqlite")
            )
            snapshot = {
                "adx": float(tech.get("adx") or 0.0),
                "atr_14": float(tech.get("atr_14") or 0.0),
                "bb_width": float(tech.get("bb_width") or 0.0),
                "ema_slope_h1": float(tech.get("ema_slope_h1") or 0.0),
                "rsi_14": float(tech.get("rsi_14") or 0.0),
                "pattern_bias": int(tech.get("pattern_bias") or 0),
                "regime": str(final.get("regime") or tech.get("regime") or ""),
                "session": tech.get("session") or tech.get("_tf_M5", {}).get("session"),
            }
            ms.add_reco(symbol=sym, snapshot=snapshot, plan=final, tf="M5", ticket=None)
        except Exception:
            pass

        # Compose message

        # ---- Defensive orientation guard (SL/TP vs Entry) ----
        try:
            d = (final.get("direction") or "").upper()
            e = final.get("entry")
            s = final.get("sl")
            t = final.get("tp")
            pt = float(tech.get("_point") or 0.0)
            if e is not None and s is not None and t is not None and d:
                s_fixed, t_fixed = ensure_orientation(float(e), float(s), float(t), d, pt)
                final["sl"], final["tp"] = s_fixed, t_fixed
                try:
                    # Recompute RR if present
                    if isinstance(final.get("rr"), (int, float)):
                        risk = abs(float(e) - float(s_fixed))
                        reward = abs(float(t_fixed) - float(e))
                        final["rr"] = round(reward / max(1e-9, risk), 2) if risk > 0 else final.get("rr")
                except Exception:
                    pass
        except Exception:
            pass

        text = fmt_trade_message(
            sym, final, tech, confidence, live_bid, live_ask, mk_closed
        )

        # Build buttons (same logic as trade_command)
        rows: list[list[InlineKeyboardButton]] = []
        cb_refresh = f"mkt|refresh|{sym}"
        entry_guess = final.get("entry")
        sl_guess = final.get("sl")
        tp_guess = final.get("tp")
        side_guess = None
        dir_norm = normalise_direction(final.get("direction"))
        can_execute = (dir_norm in ("buy", "sell")) and bool(
            final.get("critic_approved")
        )
        always = bool(getattr(settings, "ALWAYS_SHOW_EXEC", False))

        # IMPROVED: Block execution buttons for HOLD recommendations
        if final.get("direction", "").upper() == "HOLD":
            can_execute = False  # Override - never execute HOLD
        
        # Encode a compact exec payload (using the _stash_cb/_pop_cb helpers)
        try:
            # prefer explicit direction; else inferred; else BUY for testing
            side = dir_norm if dir_norm in ("buy", "sell") else (side_guess or "buy")
            payload = {
                "symbol": sym,
                "side": side,
                "sl": sl_guess,
                "tp": tp_guess,
                "entry": entry_guess,
                "risk_pct": risk_pct_mapped,
            }

            rows: list[list[InlineKeyboardButton]] = []
            cb_refresh = f"mkt|refresh|{sym}"

            if can_execute or always:
                # prefer explicit side; if always=True while HOLD, keep side from levels as a *fallback* label only
                side = (
                    dir_norm
                    if dir_norm in ("buy", "sell")
                    else (
                        _infer_side_from_levels(
                            final.get("entry"), final.get("sl"), final.get("tp")
                        )
                        or "buy"
                    )
                )

                btn_label_side = side.upper()

                token = _stash_cb(
                    context.application,
                    chat_id,
                    {
                        "symbol": sym,
                        "side": side,
                        "sl": sl_guess,
                        "tp": tp_guess,
                        "entry": entry_guess,
                        "risk_pct": risk_pct_mapped,
                    },
                    ttl_sec=900,
                )
                rows.append(
                    [
                        InlineKeyboardButton(
                            f"✅ Execute {btn_label_side} ({risk_pct_mapped:.2f}% risk)",
                            callback_data=f"exec2|{token}",
                        ),
                        InlineKeyboardButton(
                            "↻ Refresh price", callback_data=cb_refresh
                        ),
                        InlineKeyboardButton("🧊 Ignore", callback_data="ignore"),
                    ]
                )
            else:
                rows.append(
                    [
                        InlineKeyboardButton(
                            "↻ Refresh price", callback_data=cb_refresh
                        ),
                        InlineKeyboardButton("🧊 Ignore", callback_data="ignore"),
                    ]
                )
        except Exception:
            rows.append(
                [
                    InlineKeyboardButton("🔄 Refresh price", callback_data=cb_refresh),
                    InlineKeyboardButton("🧊 Ignore", callback_data="ignore"),
                ]
            )

            # --- Pending buttons (dynamic label, strategy-aware) ---
        try:
            plan_obj = tech.get("strategy_plan") or {}
            btn_text = (
                "⏳ Make pending (strategy plan)" if plan_obj else "⏳ Make pending"
            )
            # `pend|plan|{token}` is handled by pending_callbacks (plan view)
            rows.append(
                [InlineKeyboardButton(btn_text, callback_data=f"pend|plan|{token}")]
            )

            # If the plan is OCO-capable, show a one-tap arm for breakout OCO
            if plan_obj.get("pending_type") == "OCO_STOP" or plan_obj.get(
                "oco_companion"
            ):
                rows.append(
                    [
                        InlineKeyboardButton(
                            "⛓ Arm OCO breakout", callback_data=f"pend|arm_oco|{token}"
                        )
                    ]
                )

        except Exception:
            # Non-fatal: skip pending buttons if anything odd happens
            pass

        # Send it
        try:
            await context.application.bot.send_message(
                chat_id,
                text,
                reply_markup=InlineKeyboardMarkup(rows),
            )
        except Exception:
            # Fallback without parse mode
            await context.application.bot.send_message(
                chat_id, text, reply_markup=InlineKeyboardMarkup(rows)
            )

        # === ANCHOR: POSWATCH_SAVE_CHAT_TRADE_START ===
        try:
            context.application.bot_data["poswatch_last_chat_id"] = chat_id
        except Exception:
            pass
        # === ANCHOR: POSWATCH_SAVE_CHAT_TRADE_END ===

        # Actionable?
        actionable = (dir_norm in ("buy", "sell")) and bool(
            final.get("critic_approved")
        )
        return actionable
    except Exception as e:
        logger.debug("full re-analysis failed for %s: %s", sym, e)
        try:
            await context.application.bot.send_message(
                chat_id, f"⚠️ Re-analysis failed for {sym}: {e}"
            )
        except Exception:
            pass
        return False


async def _auto_watch_reanalyse(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, symbol: str
):
    """Coroutine that re-runs analysis and disarms the watch if a valid plan is ready."""
    try:
        actionable = await _run_full_analysis_and_notify(context, chat_id, symbol)
        if actionable:
            # Disarm on success to avoid spam
            _auto_watch_disarm(chat_id, symbol, "actionable")
    except Exception as e:
        logger.debug("auto_watch_reanalyse error: %s", e)


def _should_notify_ready(tech: dict, spread: float, atr: float) -> bool:
    """Very light gate: notify when spread is reasonable vs ATR (M15, floored) and ADX is decent."""
    try:
        max_pct = float(getattr(settings, "MAX_SPREAD_PCT_ATR", 0.35))
        adx_ok = float(tech.get("adx") or 0.0) >= 20.0

        point = float(tech.get("_point") or 0.0)
        atr_m15 = float(
            tech.get("_tf_M15", {}).get("atr_14") or tech.get("atr_14") or 0.0
        )
        min_ticks = float(getattr(settings, "ATR_FLOOR_TICKS", 3.0))
        atr_eff = max(atr_m15, min_ticks * point) if point else atr_m15

        pct = (float(spread) / max(1e-9, float(atr_eff))) if atr_eff else 1.0
        return adx_ok and pct <= max_pct
    except Exception:
        return False


def _auto_watch_expired(data: dict) -> bool:
    return (time.time() - float(data.get("start_time", time.time()))) >= float(
        AUTO_WATCH_TIMEOUT_SEC
    )


def _fmt_secs(s: int) -> str:
    m, sec = divmod(int(s), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {sec}s"
    if m:
        return f"{m}m {sec}s"
    return f"{sec}s"


def _extract_bridge_and_tech(symbol: str) -> tuple[dict, dict]:
    """Helper to pull fresh tech snapshot with IndicatorBridge. Returns (multi, tech_dict)."""
    bridge = IndicatorBridge(settings.MT5_FILES_DIR)
    bridge.ensure(symbol)
    multi = bridge.get_multi(symbol)
    tech, _, _ = _build_tech_from_bridge(multi, symbol)
    return multi, tech


def _current_spread(symbol: str) -> float:
    try:
        mt5svc = MT5Service()
        mt5svc.connect()
        mt5svc.ensure_symbol(symbol)
        q = mt5svc.get_quote(symbol)
        return max(0.0, (q.ask or 0.0) - (q.bid or 0.0))
    except Exception:
        return 0.0


def _atr_value(tech: dict) -> float:
    try:
        return float(tech.get("atr_14") or 0.0)
    except Exception:
        return 0.0


def _auto_watch_disarm(chat_id: int, symbol: str, reason: str = "expired"):
    job = _AUTO_WATCH_JOBS.pop((chat_id, symbol), None)
    if job:
        try:
            job.schedule_removal()
        except Exception:
            pass
    return reason


def _auto_watch_ready_msg(symbol: str, tech: dict, spread: float) -> str:
    atr = float(tech.get("_tf_M15", {}).get("atr_14") or tech.get("atr_14") or 0.0)
    point = float(tech.get("_point") or 0.0)
    atr_eff = (
        max(atr, float(getattr(settings, "ATR_FLOOR_TICKS", 3.0)) * point)
        if point
        else atr
    )
    adx = tech.get("adx")
    return (
        f"✅ Auto-watch: Conditions improved on {symbol} — ADX≈{_fmt_num(adx,2)}, ATR≈{_fmt_num(atr,2)}, "
        f"spread≈{fmt_price(symbol, spread)} ({_fmt_num(100.0*spread/max(1e-9,atr_eff),1)}% of ATR). "
        f"Run /trade {symbol} to re-check and execute."
    )


def _auto_watch_tick(context):
    try:
        data = context.job.data or {}
        chat_id = int(data.get("chat_id"))
        symbol = str(data.get("symbol"))

        # Expire?
        if _auto_watch_expired(data):
            try:
                context.application.bot.send_message(
                    chat_id,
                    f"⌛ Auto-watch expired for {symbol} after {_fmt_secs(AUTO_WATCH_TIMEOUT_SEC)}.",
                )
            except Exception:
                pass
            _auto_watch_disarm(chat_id, symbol, "expired")
            return

        # Run full re-analysis in the background (don't block the job thread)
        context.application.create_task(_auto_watch_reanalyse(context, chat_id, symbol))
        return
    except Exception as e:
        logger.debug("auto_watch_tick failed: %s", e)
        return


def normalise_symbol(sym: str | None) -> str:
    if not sym:
        return _DEF_SYMBOL
    s = sym.strip()
    base = s.rstrip("m").rstrip("c").rstrip("C").upper()
    return base + "c"


async def _in_thread(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


def infer_pending_type(direction: str, entry: float, bid: float, ask: float) -> str:
    d = (direction or "").upper()
    try:
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
    Pip = point*10 for 3/5-digit FX (e.g. 0.0001 or 0.01), else 1*point for others.
    """
    try:
        si = mt5.symbol_info(symbol)
        if not si:
            sp = max(0.0, float(ask) - float(bid))
            return f"{fmt_price(symbol, sp)}", 0.0
        point = float(getattr(si, "point", 0.0) or 0.0)
        digits = int(getattr(si, "digits", 5) or 5)
        pip = point * (10.0 if digits in (3, 5) else 1.0)
        spread = max(0.0, float(ask) - float(bid))
        spread_pips = (spread / pip) if pip > 0 else 0.0
        pretty = f"{fmt_price(symbol, spread)} (~{spread_pips:.1f} pips)"
        return pretty, spread_pips
    except Exception:
        sp = max(0.0, float(ask) - float(bid))
        return f"{fmt_price(symbol, sp)}", 0.0


def _fmt_num(x, d=2):
    try:
        return f"{float(x):.{d}f}"
    except Exception:
        return str(x)


def _esc_html(s) -> str:
    if s is None:
        return "—"
    try:
        return html.escape(str(s))
    except Exception:
        return "—"


def _level_or_dash(symbol: str, v) -> str:
    """
    Show '—' for None or 0.0 (invalid/placeholder), else format by symbol digits.
    """
    try:
        if v is None:
            return "—"
        f = float(v)
        if f == 0.0:
            return "—"
        return fmt_price(symbol, f)
    except Exception:
        return "—"


def _should_arm_pending(
    rec: dict, tech: dict, bid: float = None, ask: float = None
) -> tuple[bool, str]:
    # News blackout is the only hard "no"
    guards = [str(g).lower() for g in (rec.get("guards") or [])]
    if any(g.startswith("news_guard") for g in guards):
        return False, "news blackout window"

    # Levels present?
    try:
        entry, sl, tp = rec["entry"], rec["sl"], rec["tp"]
        if not all(isinstance(x, (int, float)) and x > 0 for x in [entry, sl, tp]):
            return False, "levels missing"
    except Exception:
        return False, "levels missing"

    d = normalise_direction(rec.get("direction"))
    if d not in ("buy", "sell"):
        return False, "direction=HOLD"

    # Current spread (prefer live snapshot)
    spread = float(
        tech.get("_live_spread")
        or ((float(ask) - float(bid)) if (bid is not None and ask is not None) else 0.0)
    )

    # --- M15 ATR with floor (min N ticks) ---
    point = float(tech.get("_point") or 0.0)
    atr_m15 = float(tech.get("_tf_M15", {}).get("atr_14") or 0.0)
    atr_m5 = float(tech.get("atr_14") or 0.0)
    atr = atr_m15 or atr_m5
    min_ticks = float(getattr(settings, "ATR_FLOOR_TICKS", 3.0))
    atr_eff = max(atr, min_ticks * point) if point else atr

    max_pct = float(getattr(settings, "MAX_SPREAD_PCT_ATR", 0.35))

    # Prefer arming even if spread is currently high; watcher will notify later.
    if atr_eff > 0 and (spread / atr_eff) > max_pct:
        return True, "waiting for spread to normalize"

    return True, ""


# Reuse this for both guards and reasons (already added earlier — keep it)
_guard_re_risk = re.compile(
    r"risk[_ ]?sim[_ ]?negative\((?:p_sl=)?([0-9.]+).*?(?:p_tp=)?([0-9.]+).*?(?:exp_r=)?(-?[0-9.]+)\)",
    re.I,
)
_guard_re_spread = re.compile(
    r"spread(?:_guard|[:_ ]?ratio)?[:_ ]?([0-9.]+).*?exceeds[:_ ]?([0-9.]+)", re.I
)


def _prettify_guards(guards: list[str]) -> list[str]:
    out = []
    for g in guards or []:
        gl = (g or "").lower()

        m = _guard_re_risk.search(gl)
        if m:
            psl, ptp, er = m.groups()
            out.append(
                f"Risk simulation negative — SL {psl}, TP {ptp}, expected R {er}."
            )
            continue

        m = _guard_re_spread.search(gl)
        if m:
            ratio, thr = m.groups()
            out.append(f"Spread too high — {ratio}× threshold ({thr}).")
            continue

        if gl.startswith("critic:rsi_oversold"):
            out.append("RSI oversold — wait for bounce confirmation.")
        elif gl.startswith("critic:rsi_overbought"):
            out.append("RSI overbought — wait for pullback confirmation.")
        elif "sr_anchor" in gl and "tp" in gl and "support" in gl:
            out.append("TP conflicts with nearest support (anchor rule).")
        elif "sr_anchor" in gl and "sl" in gl and "resistance" in gl:
            out.append("SL conflicts with nearest resistance (anchor rule).")
        elif gl.startswith("criticrejected") or gl.startswith("critic_rejected"):
            out.append("Critic rejected setup.")
        elif gl.startswith("news_guard"):
            out.append("High-impact news window — trading disabled.")
        elif gl.startswith("exposure_guard"):
            out.append("Exposure limit reached — reduce correlated positions.")
        elif gl.startswith("risk_guard"):
            reason = g.split(":", 1)[-1] if ":" in g else ""
            out.append(f"Risk limit: {reason}.")
        else:
            out.append(g.replace(":", " → ").replace("_", " "))

    seen, nice = set(), []
    for s in out:
        if s not in seen:
            nice.append(s)
            seen.add(s)
    return nice[:8]


# New: prettify Critic "reasons" list
def _prettify_reasons(
    reasons: list[str],
    *,
    min_rr: float,
    max_spread_pct_atr: float,
    atr_min_ticks: float,
) -> list[str]:
    out = []
    for r in reasons or []:
        rl = (r or "").lower()
        if rl.startswith("rr_below_floor"):
            out.append(f"Risk/reward below minimum (≥ {min_rr:.2f} required).")
        elif rl == "atr_too_small":
            out.append(
                f"ATR too small — widen SL/TP or wait for volatility (min ≈ {atr_min_ticks:.0f} ticks)."
            )
        elif rl.startswith("spread_pct_atr"):
            out.append(
                f"Spread too large vs ATR — keep it under {max_spread_pct_atr*100:.0f}%."
            )
        elif rl == "sl_not_below_entry":
            out.append("For BUY, SL must be below entry.")
        elif rl == "sl_not_above_entry":
            out.append("For SELL, SL must be above entry.")
        elif rl == "tp_not_above_entry":
            out.append("For BUY, TP must be above entry.")
        elif rl == "tp_not_below_entry":
            out.append("For SELL, TP must be below entry.")
        elif rl.startswith("direction=hold"):
            out.append("No clear setup — wait for breakout or stronger confluence.")
        elif rl.startswith("ema_alignment_false"):
            out.append("Weak EMA alignment — consider skipping or use lower risk.")
        elif rl.startswith("adx_weak"):
            out.append(
                "Trend strength low (ADX) — consider skipping or use lower risk."
            )
        else:
            out.append(r.replace("_", " "))
    # dedupe preserve order
    seen, nice = set(), []
    for s in out:
        if s not in seen:
            nice.append(s)
            seen.add(s)
    return nice[:8]


def _fmt_critic_report_html(
    sym: str,
    rec: dict,
    *,
    approved: bool,
    reasons: list[str],
    adx_val: float,
    atr_val: float,
    spread: float,
    ema_align: bool | None,
    gate_strategy: str | None,
    min_rr: float,
    max_spread_pct_atr: float,
    atr_min_ticks: float,
    bid: float | None,
    ask: float | None,
    risk_pct_mapped: float | None,
) -> str:
    spread_pct_atr = (spread / atr_val) * 100.0 if atr_val else 0.0

    entry_s = fmt_price(sym, rec.get("entry")) if rec.get("entry") is not None else "—"
    sl_s = fmt_price(sym, rec.get("sl")) if rec.get("sl") is not None else "—"
    tp_s = fmt_price(sym, rec.get("tp")) if rec.get("tp") is not None else "—"
    rr_s = (
        f"{float(rec.get('rr') or 0.0):.2f}"
        if isinstance(rec.get("rr"), (int, float))
        else str(rec.get("rr"))
    )

    status_chip = "✅ APPROVED" if approved else "❌ REJECTED"
    pretty_reasons = _prettify_reasons(
        reasons,
        min_rr=min_rr,
        max_spread_pct_atr=max_spread_pct_atr,
        atr_min_ticks=atr_min_ticks,
    )

    # Optional risk line
    risk_line = (
        f"\n🎚️ <b>Risk (mapped):</b> {risk_pct_mapped:.2f}%"
        if isinstance(risk_pct_mapped, (int, float))
        else ""
    )

    lines = []
    lines.append(f"🧠 <b>Critic report</b> — {_esc_html(sym)}")
    lines.append(f"• <b>Status:</b> {_esc_html(status_chip)}")
    if pretty_reasons:
        lines.append("• <b>Reasons:</b>")
        for r in pretty_reasons:
            lines.append(f"  • {_esc_html(r)}")
    else:
        lines.append("• <b>Reasons:</b> (no issues)")

    lines.append("")
    lines.append(
        f"🧾 <b>Plan:</b> { _esc_html(str(rec.get('direction','HOLD'))) } | Entry { _esc_html(entry_s) } | SL { _esc_html(sl_s) } | TP { _esc_html(tp_s) } | RR={ _esc_html(rr_s) }"
    )

    # metrics + rules
    lines.append(
        "📊 <b>Metrics:</b> "
        f"ADX={_esc_html(f'{adx_val:.2f}')} | ATR14={_esc_html(fmt_price(sym, atr_val))} | "
        f"Spread={_esc_html(fmt_price(sym, spread))} ({_esc_html(f'{spread_pct_atr:.1f}%')} of ATR) | "
        f"EMA_align={_esc_html(str(bool(ema_align)))} | Gate={_esc_html(str(gate_strategy))}"
    )
    lines.append(
        "📏 <b>Rules:</b> "
        f"min RR={_esc_html(f'{min_rr:.2f}')} | max spread%ATR={_esc_html(f'{max_spread_pct_atr:.2f}')} | ATR min ticks≈{_esc_html(f'{atr_min_ticks:.0f}')}"
    )

    # live
    bid_s = fmt_price(sym, bid) if bid is not None else "—"
    ask_s = fmt_price(sym, ask) if ask is not None else "—"
    lines.append(
        f"📡 <b>Live:</b> Bid={_esc_html(bid_s)} | Ask={_esc_html(ask_s)}{risk_line}"
    )

    return "\n".join(lines)


# escape user/dynamic content for Telegram MarkdownV2
def _esc_md2(x: object) -> str:
    if x is None:
        return ""
    s = str(x)
    # Telegram MDV2 special chars: _ * [ ] ( ) ~ ` > # + - = | { } . !
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", s)


def _market_looks_closed(symbol: str) -> bool:
    """
    Heuristic: market looks closed if session trading/deals off OR last tick is stale.
    We’re conservative — only say closed when it’s pretty clear.
    """
    try:
        info = mt5.symbol_info(symbol)
        if info is None:
            return False
        if hasattr(info, "session_trade") and hasattr(info, "session_deals"):
            if (not bool(info.session_trade)) or (not bool(info.session_deals)):
                return True
        tick = mt5.symbol_info_tick(symbol)
        if tick and hasattr(tick, "time"):
            if (time.time() - float(tick.time)) > 600:  # >10 min
                return True
    except Exception:
        pass
    return False


def _humanise_filters(rec: dict, tech: dict) -> str:
    bits = []
    gate = rec.get("strategy") or ""
    if gate.lower() == "idle":
        bits.append("No setup (range/vol regimes, strict filters)")
    elif gate.lower() == "breakout":
        bits.append("Vol breakout")
    elif gate.lower() == "trend_pullback":
        bits.append("Trend pullback")
    else:
        bits.append(gate)
    if not rec.get("critic_approved"):
        bits.append("Critic flagged risk")
    if rec.get("direction") == "HOLD":
        bits.append("Hold signal")
    return " | ".join(bits) if bits else "—"


def _fmt_range_meta(rec: dict) -> str:
    tg = rec.get("triggers") or []
    gd = rec.get("guards") or []
    return f"trigs={len(tg)}, guards={len(gd)}"


def _determine_optimal_order_type(
    symbol: str,
    rec: dict,
    tech: dict,
    live_bid: Optional[float] = None,
    live_ask: Optional[float] = None,
) -> dict:
    """
    IMPROVED: Determine optimal order type (Market, Pending, or OCO) based on market conditions.
    Returns dict with order_type, confidence, and reasoning.
    """
    try:
        # Get current market data
        current_price = (live_bid + live_ask) / 2 if live_bid and live_ask else None
        spread = (live_ask - live_bid) if live_bid and live_ask else None
        
        # Get trade parameters
        entry_price = rec.get("entry")
        direction = rec.get("direction", "HOLD")
        atr = tech.get("atr_14", 0.0)
        adx = tech.get("adx", 0.0)
        bb_width = tech.get("bb_width", 0.0)
        regime = tech.get("regime", "VOLATILE")
        
        # Get timeframe data for confluence
        m5_data = tech.get("_tf_M5", {})
        m15_data = tech.get("_tf_M15", {})
        h1_data = tech.get("_tf_H1", {})
        
        rsi_m5 = m5_data.get("rsi_14", 50.0)
        rsi_m15 = m15_data.get("rsi_14", 50.0)
        rsi_h1 = h1_data.get("rsi_14", 50.0)
        
        # Calculate distance from current price
        distance_pips = 0
        if entry_price and current_price:
            distance_pips = abs(entry_price - current_price)
        
        # Calculate spread as percentage of ATR
        spread_pct_atr = (spread / atr * 100) if spread and atr > 0 else 0
        
        # Scoring system for order type recommendation
        market_score = 0
        pending_score = 0
        oco_score = 0
        
        # Market Order Scoring
        if distance_pips < (atr * 0.1):  # Very close to current price
            market_score += 30
        if spread_pct_atr < 5:  # Low spread
            market_score += 20
        if adx > 25:  # Strong trend
            market_score += 15
        if regime == "TREND":  # Trending market
            market_score += 10
        # FIXED: Get confidence from recommendation dict
        rec_confidence = rec.get("confidence", 50)
        if rec_confidence > 70:  # High confidence
            market_score += 15
        if rsi_m5 > 30 and rsi_m5 < 70:  # Not oversold/overbought
            market_score += 10
        
        # Pending Order Scoring
        if distance_pips > (atr * 0.2):  # Reasonable distance
            pending_score += 25
        if spread_pct_atr > 10:  # High spread
            pending_score += 20
        if regime == "RANGE":  # Ranging market
            pending_score += 20
        if adx < 25:  # Weak trend
            pending_score += 15
        if (rsi_m5 < 30 or rsi_m5 > 70):  # Oversold/overbought
            pending_score += 15
        if bb_width < 0.01:  # Low volatility
            pending_score += 10
        
        # OCO Order Scoring
        if distance_pips > (atr * 0.5):  # Far from current price
            oco_score += 20
        if regime == "VOLATILE":  # Volatile market
            oco_score += 25
        if spread_pct_atr > 15:  # Very high spread
            oco_score += 20
        if adx > 30:  # Strong trend with volatility
            oco_score += 15
        if abs(rsi_m5 - 50) > 20:  # Strong momentum
            oco_score += 15
        if bb_width > 0.02:  # High volatility
            oco_score += 10
        
        # Determine winner
        scores = {
            "MARKET": market_score,
            "PENDING": pending_score,
            "OCO": oco_score
        }
        
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        total_score = sum(scores.values())
        confidence_pct = int((best_score / max(total_score, 1)) * 100)
        
        # Generate reasoning
        reasoning_parts = []
        
        if best_type == "MARKET":
            reasoning_parts.append("Immediate execution recommended")
            if distance_pips < (atr * 0.1):
                reasoning_parts.append("entry very close to current price")
            if spread_pct_atr < 5:
                reasoning_parts.append("low spread")
            if adx > 25:
                reasoning_parts.append("strong trend momentum")
                
        elif best_type == "PENDING":
            reasoning_parts.append("Pending order recommended")
            if distance_pips > (atr * 0.2):
                reasoning_parts.append("entry at better price")
            if regime == "RANGE":
                reasoning_parts.append("ranging market conditions")
            if spread_pct_atr > 10:
                reasoning_parts.append("high spread favors limit orders")
                
        elif best_type == "OCO":
            reasoning_parts.append("OCO order recommended")
            if regime == "VOLATILE":
                reasoning_parts.append("volatile market conditions")
            if distance_pips > (atr * 0.5):
                reasoning_parts.append("entry far from current price")
            if bb_width > 0.02:
                reasoning_parts.append("high volatility environment")
        
        reasoning = "; ".join(reasoning_parts)
        
        return {
            "order_type": best_type,
            "confidence": confidence_pct,
            "reasoning": reasoning,
            "scores": scores,
            "distance_pips": distance_pips,
            "spread_pct_atr": spread_pct_atr
        }
        
    except Exception as e:
        return {
            "order_type": "MARKET",
            "confidence": 50,
            "reasoning": f"Default to market order (error: {str(e)[:50]})",
            "scores": {"MARKET": 50, "PENDING": 30, "OCO": 20},
            "distance_pips": 0,
            "spread_pct_atr": 0
        }


def fmt_trade_message(
    symbol: str,
    rec: dict,
    tech: dict,
    confidence: int,
    live_bid: Optional[float] = None,
    live_ask: Optional[float] = None,
    market_closed_hint: bool = False,
) -> str:
    # Values (escaped for MDV2)
    entry_val = rec.get("entry")
    sl_val = rec.get("sl")
    tp_val = rec.get("tp")

    entry_s = _esc_md2(fmt_price(symbol, entry_val)) if entry_val is not None else "—"
    sl_s = _esc_md2(fmt_price(symbol, sl_val)) if sl_val is not None else "—"
    tp_s = _esc_md2(fmt_price(symbol, tp_val)) if tp_val is not None else "—"

    rr = rec.get("rr")
    rr_str = _esc_md2(_fmt_num(rr, 2) if isinstance(rr, (int, float)) else rr)

    adx = _esc_md2(_fmt_num(tech.get("adx", 0.0), 2))
    atr_s = _esc_md2(fmt_price(symbol, tech.get("atr_14", 0.0)))
    ema20_s = _esc_md2(fmt_price(symbol, tech.get("ema_20", 0.0)))
    ema50_s = _esc_md2(fmt_price(symbol, tech.get("ema_50", 0.0)))
    ema200_s = _esc_md2(fmt_price(symbol, tech.get("ema_200", 0.0)))
    bbw = _esc_md2(_fmt_num(tech.get("bb_width", 0.0), 6))

    regime = _esc_md2(str(rec.get("regime") or tech.get("regime") or "RANGE").upper())
    direction = _esc_md2(rec.get("direction", "HOLD"))

    filters_line = _esc_md2(_humanise_filters(rec, tech))

    # Live line
    live_line = ""
    if live_bid is not None and live_ask is not None:
        live_line = (
            "\n*Live:* "
            f"Bid={_esc_md2(fmt_price(symbol, live_bid))} | "
            f"Ask={_esc_md2(fmt_price(symbol, live_ask))} "
            f"(as of {_esc_md2(datetime.now().strftime('%H:%M:%S'))})"
        )

    mkthint = (
        "\n_Market appears closed; execution may be unavailable._"
        if market_closed_hint
        else ""
    )

    # --- Strategy selection lines (PLAIN TEXT) ---
    plan_obj = tech.get("strategy_plan") or tech.get("strategy_plan_preview") or {}
    gate_strat = tech.get("gate_strategy")
    sel_strat = plan_obj.get("strategy")

    # Normalise plan direction and compute a safe BUY/SELL alias
    plan_dir = (plan_obj.get("direction") or rec.get("direction") or "").upper()
    order_side = (
        plan_obj.get("order_side") or rec.get("order_side") or ""
    ).upper() or (
        "BUY"
        if plan_dir in ("LONG", "BUY")
        else ("SELL" if plan_dir in ("SHORT", "SELL") else "")
    )

    plan_entry = plan_obj.get("entry")
    ptype_hint = plan_obj.get("pending_type")
    plan_notes = plan_obj.get("notes")
    is_preview = bool(plan_obj.get("preview"))
    blocked_by = plan_obj.get("blocked_by") or []

    # Infer entry type from live prices if we can, else fall back to plan hint
    entry_type_text = ""
    side_for_infer = order_side or plan_dir  # prefer BUY/SELL, else LONG/SHORT
    if (
        side_for_infer in ("BUY", "SELL")
        and plan_entry is not None
        and (live_bid is not None)
        and (live_ask is not None)
    ):
        try:
            ptype_inferred = infer_pending_type(
                side_for_infer, float(plan_entry), float(live_bid), float(live_ask)
            )
            if ptype_inferred:
                entry_type_text = ptype_inferred.replace("_", " ")
        except Exception:
            pass
    if not entry_type_text and ptype_hint:
        entry_type_text = str(ptype_hint).replace("_", " ")

    strategy_lines = ""
    if gate_strat or sel_strat or entry_type_text or plan_notes:
        title = f"Strategy: {sel_strat or '—'}"
        if is_preview:
            title += " (preview)"
        gate_tail = (
            f" (gate: {gate_strat})"
            if gate_strat and (sel_strat != gate_strat or not sel_strat)
            else ""
        )
        dir_line = f"\nPlan Direction: {plan_dir or '—'}" if plan_dir else ""
        type_line = f"\nEntry Type: {entry_type_text}" if entry_type_text else ""
        notes_line = f"\nPlan Notes: {plan_notes}" if plan_notes else ""
        blocked_line = (
            f"\nBlocked by: {', '.join(blocked_by)}"
            if (is_preview and blocked_by)
            else ""
        )
        strategy_lines = (
            f"{title}{gate_tail}{dir_line}{type_line}{notes_line}{blocked_line}\n"
        )

    
    # Confluence breakdown
    try:
        conf = compute_mtf_confluence(tech)
        sc = int(100 * float(conf.get("score") or 0.0))
        det = conf.get("details") or {}
        ticks = []
        if det.get("ema_align", False):
            ticks.append("EMA align ✔")
        elif det.get("ema_partial", False):
            ticks.append("EMA partial")
        ticks.append("ADX M15 ✔" if "adx_m15" in det else "ADX M15 ✘")
        ticks.append("ADX H1 ✔" if "adx_h1" in det else "ADX H1 ✘")
        if det.get("ema_stack_primary"):
            ticks.append("M15 stack ✔")
        if det.get("ema200_same_side"):
            ticks.append("EMA200 same-side ✔")
        conf_line = f"Confluence: {sc}% (" + " | ".join(ticks) + ")"
        strategy_lines += conf_line + "\n"
    except Exception:
        pass

# Nearest S/R
    sr_line = ""
    try:
        sr_obj = rec.get("sr") or tech.get("sr")
        if isinstance(sr_obj, dict):
            nearest = sr_obj.get("nearest") or {}
            kind = nearest.get("kind")
            lvl = nearest.get("level")
            frac = nearest.get("distance_frac_atr")
            label = nearest.get("label") or ""
            if kind and (lvl is not None) and (frac is not None):
                lvl_s = _esc_md2(fmt_price(symbol, float(lvl)))
                pct = int(round(float(frac) * 100))
                sr_line = f"*Nearest S/R:* {_esc_md2(kind)} @ {lvl_s} (~{pct}% ATR) {_esc_md2(label)}\n"
    except Exception:
        sr_line = ""

    # Optional blocks
    patterns_block = ""
    if rec.get("patterns_summary"):
        patterns_block = f"*Patterns:* {_esc_md2(rec.get('patterns_summary'))}\n"

    # Guards & triggers
    guards_pretty = _prettify_guards(rec.get("guards") or [])
    trigs = rec.get("triggers") or []
    guards_line = (
        "🛡️ *Guards:* " + ", ".join(_esc_md2(g) for g in guards_pretty) + "\n"
        if guards_pretty
        else ""
    )
    triggers_line = (
        "🎯 *Triggers:* " + ", ".join(_esc_md2(t) for t in trigs) + "\n"
        if trigs
        else ""
    )

    # Make helper blocks plain (strip MarkdownV2 escapes and asterisks)
    def _plain(s):
        s = str(s or "")
        return s.replace("\\", "").replace("*", "").replace("_", "")

    sr_plain = _plain(sr_line)
    patterns_plain = _plain(patterns_block)
    guards_plain = _plain(guards_line)
    triggers_plain = _plain(triggers_line)
    live_plain = _plain(live_line)
    filters_plain = f"Filters: {filters_line}" if filters_line else ""

    why = _plain(rec.get("reasoning", ""))

    # IMPROVED: Add order type recommendation
    order_recommendation = ""
    try:
        order_analysis = _determine_optimal_order_type(symbol, rec, tech, live_bid, live_ask)
        order_type = order_analysis.get("order_type", "MARKET")
        order_confidence = order_analysis.get("confidence", 50)
        order_reasoning = order_analysis.get("reasoning", "")
        
        # Format order type with emoji
        order_emoji = {
            "MARKET": "⚡",
            "PENDING": "⏳", 
            "OCO": "🎯"
        }.get(order_type, "⚡")
        
        order_recommendation = (
            f"\n{order_emoji} *Order Type:* {order_type} "
            f"(Confidence: {order_confidence}%)\n"
            f"💡 *Reasoning:* {order_reasoning}\n"
        )
    except Exception:
        order_recommendation = "\n⚡ *Order Type:* MARKET (Default)\n"

    # IMPROVED Phase 4.4: Add execution upgrade metadata
    phase44_info = ""
    try:
        # Structure SL metadata
        sl_anchor = rec.get("sl_anchor_type")
        sl_dist_atr = rec.get("sl_distance_atr")
        if sl_anchor and sl_dist_atr is not None:
            sl_emoji = {"swing_low": "🎯", "swing_high": "🎯", "fvg": "📊", "equal": "⚖️", "sweep": "🌊", "fallback": "📏"}.get(sl_anchor, "📍")
            phase44_info += f"  {sl_emoji} SL Anchor: {sl_anchor}, {_fmt_num(sl_dist_atr, 2)}× ATR\n"
        
        # Adaptive TP metadata
        tp_momentum = rec.get("tp_momentum_state")
        tp_adj_rr = rec.get("tp_adjusted_rr")
        if tp_momentum:
            momentum_emoji = {"strong": "🔥", "normal": "➡️", "fading": "💤"}.get(tp_momentum, "➡️")
            tp_info = f"  {momentum_emoji} Momentum: {tp_momentum}"
            if tp_adj_rr is not None:
                tp_info += f", RR adjusted to {_fmt_num(tp_adj_rr, 2)}"
            phase44_info += tp_info + "\n"
        
        # OCO Bracket metadata
        if rec.get("oco_bracket"):
            phase44_info += f"\n🎯 OCO BRACKET DETECTED\n"
            phase44_info += f"  Buy Stop: {_esc_md2(fmt_price(symbol, rec.get('buy_stop')))}, "
            phase44_info += f"SL: {_esc_md2(fmt_price(symbol, rec.get('buy_sl')))}, "
            phase44_info += f"TP: {_esc_md2(fmt_price(symbol, rec.get('buy_tp')))} "
            phase44_info += f"(RR {_fmt_num(rec.get('buy_rr'), 2)})\n"
            phase44_info += f"  Sell Stop: {_esc_md2(fmt_price(symbol, rec.get('sell_stop')))}, "
            phase44_info += f"SL: {_esc_md2(fmt_price(symbol, rec.get('sell_sl')))}, "
            phase44_info += f"TP: {_esc_md2(fmt_price(symbol, rec.get('sell_tp')))} "
            phase44_info += f"(RR {_fmt_num(rec.get('sell_rr'), 2)})\n"
            phase44_info += f"  Range: {_esc_md2(fmt_price(symbol, rec.get('range_low')))} - {_esc_md2(fmt_price(symbol, rec.get('range_high')))}\n"
            phase44_info += f"  Expiry: {rec.get('expiry_minutes')} minutes\n"
    except Exception:
        pass

    msg = (
        "📈 Trade Recommendation\n"
        f"- Symbol: {symbol}\n"
        f"- Regime: {regime}\n"
        f"- Direction: {direction}\n"
        f"- Entry (suggested): {entry_s}\n"
        f"- SL: {sl_s}  (ATR-based)\n"
        f"- TP: {tp_s}  (ATR-based)\n"
        f"- R:R Ratio: {rr_str}\n"
        f"{phase44_info}\n"
        f"Why: {why}{mkthint}\n\n"
        f"{strategy_lines}"
        f"Snapshot: ADX={adx}, ATR14={atr_s}, EMA20/50/200={ema20_s}/{ema50_s}/{ema200_s}, BBWidth={bbw}\n"
        f"{sr_plain}\n"
        f"{patterns_plain}"
        f"Confidence: {confidence}/99\n"
        f"{filters_plain}\n"
        f"{guards_plain}"
        f"{triggers_plain}"
        f"{live_plain}"
        f"{order_recommendation}"
    )
    return msg


async def _send_pending_plan_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    reply,
    sym: str,
    rec: dict,
    tech: dict,
):
    # Live price (for type inference and spread pretty string)
    try:
        mt5svc = MT5Service()
        await _in_thread(mt5svc.connect)
        await _in_thread(mt5svc.ensure_symbol, sym)
        q = await _in_thread(mt5svc.get_quote, sym)
        bid, ask = q.bid, q.ask
    except Exception:
        bid = ask = None

    # Infer pending type (buy/sell stop/limit) if we have side+entry
    dir_norm = normalise_direction(rec.get("direction"))
    ptype = ""
    try:
        if dir_norm in ("buy", "sell") and rec.get("entry") is not None:
            ptype = infer_pending_type(
                dir_norm.upper(),
                float(rec["entry"]),
                float(bid or 0.0),
                float(ask or 0.0),
            )
    except Exception:
        ptype = ""

    # Decide whether to arm a watcher
    armed, reason = _should_arm_pending(rec, tech, bid=bid, ask=ask)
    if armed:
        start_auto_watch(
            context, update.effective_chat.id, sym, reasons=["pending_arm"]
        )

    # Build HTML and send
    text = _fmt_pending_plan_html(
        sym, rec, tech, bid=bid, ask=ask, armed=armed, arm_reason=reason, ptype=ptype
    )

    # Risk% from LAST_REC (fallback to default)
    chat_id = update.effective_chat.id
    risk_pct = LAST_REC.get((chat_id, sym), {}).get("risk_pct_mapped")
    if not isinstance(risk_pct, (int, float)):
        risk_pct = float(getattr(settings, "RISK_DEFAULT_PCT", 1.0))

    token2 = _stash_cb(
        context.application,
        chat_id,
        {
            "symbol": sym,
            "side": normalise_direction(rec.get("direction")),
            "sl": rec.get("sl"),
            "tp": rec.get("tp"),
            "entry": rec.get("entry"),
            "risk_pct": risk_pct,
        },
        ttl_sec=900,
    )

    # Buttons (include OCO if plan supports it)
    rows = [
        [InlineKeyboardButton("✅ Place pending", callback_data=f"pend|place|{token2}")]
    ]
    try:
        plan_obj = tech.get("strategy_plan") or tech.get("strategy_plan_preview") or {}
        if plan_obj.get("pending_type") == "OCO_STOP" or plan_obj.get("oco_companion"):
            rows.append(
                [
                    InlineKeyboardButton(
                        "⛓ Arm OCO breakout", callback_data=f"pend|arm_oco|{token2}"
                    )
                ]
            )
    except Exception:
        pass
    rows.append(
        [InlineKeyboardButton("↻ Refresh plan", callback_data=f"mkt|refresh|{sym}")]
    )

    
    # --- Phase3: append enforcement footnote + MTF/ADX/Regime lines ---
    try:
        extras = []
        if 'mtf_line' in locals():
            extras.append(mtf_line)
        if 'regime_line' in locals() and regime_line:
            extras.append(regime_line)
        extras.append("Enforced: Close+Retest; MTF Align; ADX gates; Reversal 2/3.")
        foot = "\n".join([f"_{e}_" for e in extras if e])
        text = f"{text}\n\n{foot}"
    except Exception:
        pass
    await reply.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows)
    )

    # === ANCHOR: AUTO_WATCH_BOTH_START ===
    # Always (re)start auto-watch for both XAU & BTC after any /trade,
    # so you receive automated actionable alerts for both.
    try:
        from config import settings as _settings

        if getattr(_settings, "AUTO_WATCH_BOOTSTRAP_ON_TRADE", True):
            watch_syms = list(
                getattr(_settings, "AUTO_WATCH_SYMBOLS", ["XAUUSDc", "BTCUSDc"])
            )
            for s in watch_syms:
                # idempotent: start_auto_watch replaces any existing watch:{chat_id}:{s}
                start_auto_watch(context, chat_id, s, reasons={"bootstrap_from_trade"})
            logger.info("Auto-watch bootstrapped for %s", watch_syms)
    except Exception:
        logger.debug("auto-watch bootstrap (trade) failed", exc_info=True)
    # === ANCHOR: AUTO_WATCH_BOTH_END ===


def _fmt_pending_plan_html(
    sym: str,
    rec: dict,
    tech: dict,
    *,
    bid: float | None,
    ask: float | None,
    armed: bool,
    arm_reason: str,
    ptype: str | None,
) -> str:
    entry_s = _level_or_dash(sym, rec.get("entry"))
    sl_s = _level_or_dash(sym, rec.get("sl"))
    tp_s = _level_or_dash(sym, rec.get("tp"))
    rr = rec.get("rr")
    rr_s = f"{float(rr):.2f}" if isinstance(rr, (int, float)) else "—"
    rr_floor = float(
        getattr(
            settings, "MIN_RR_FOR_PENDINGS", getattr(settings, "MIN_RR_FOR_MARKET", 1.2)
        )
    )

    regime = (rec.get("regime") or tech.get("regime") or "—").upper()
    typ_s = (ptype or "—").replace("_", " ").title()

    # Spread (prefer tech snapshot, else live bid/ask)
    try:
        spread = float(
            tech.get("_live_spread")
            or (
                (float(ask or 0.0) - float(bid or 0.0))
                if (bid is not None and ask is not None)
                else 0.0
            )
            or 0.0
        )
    except Exception:
        spread = 0.0

    # --- M15 ATR with floor (unified setting) ---
    point = float(tech.get("_point") or 0.0)
    atr = float(tech.get("_tf_M15", {}).get("atr_14") or tech.get("atr_14") or 0.0)
    min_ticks = float(getattr(settings, "ATR_FLOOR_TICKS", 3.0))
    atr_eff = max(atr, min_ticks * point) if point else atr

    max_pct = float(getattr(settings, "MAX_SPREAD_PCT_ATR", 0.35))
    pct = (spread / atr_eff * 100.0) if atr_eff > 0 else 0.0

    spread_note = ""
    if atr_eff > 0 and (spread / atr_eff) > max_pct:
        pretty_spread, _ = fmt_spread_readable(sym, bid or 0.0, ask or 0.0)
        spread_note = (
            "\n\n🚫 <b>Blocked by spread filter:</b> "
            f"spread {_esc_html(pretty_spread)} ({pct:.1f}% of ATR-eff). "
            "Tap <b>Refresh plan</b> when spreads settle."
        )

    # Arming line
    if armed:
        arm_line = "🟢 <b>Arming:</b> watcher will notify when price hits entry."
    else:
        why = f" — {_esc_html(arm_reason)}" if arm_reason else ""
        arm_line = f"⚪ <b>Not armed</b>{why}."

    # Strategy / notes
    plan_obj = tech.get("strategy_plan") or tech.get("strategy_plan_preview") or {}
    sel_strat = plan_obj.get("strategy")
    plan_dir = (plan_obj.get("direction") or rec.get("direction") or "").upper()
    order_side = (
        plan_obj.get("order_side")
        or ("BUY" if plan_dir == "LONG" else "SELL" if plan_dir == "SHORT" else "")
    ).upper()
    plan_entry = plan_obj.get("entry")
    ptype_hint = plan_obj.get("pending_type")
    plan_notes = (plan_obj.get("notes") or "").strip()  # <-- fix: define notes variable

    # Infer entry type from live prices if we can, else fall back to plan hint
    entry_type_text = ""
    side_for_infer = order_side or plan_dir
    if (
        side_for_infer in ("BUY", "SELL")
        and plan_entry is not None
        and (bid is not None)
        and (ask is not None)
    ):  # <-- use bid/ask, not live_bid/live_ask
        try:
            ptype_inferred = infer_pending_type(
                side_for_infer, float(plan_entry), float(bid), float(ask)
            )
            if ptype_inferred:
                entry_type_text = ptype_inferred.replace("_", " ")
        except Exception:
            pass
    if not entry_type_text and ptype_hint:
        entry_type_text = str(ptype_hint).replace("_", " ")

    strat_lines = ""
    if sel_strat or entry_type_text or plan_notes:
        strat_lines = (
            (f"• <b>Strategy:</b> {_esc_html(sel_strat)}\n" if sel_strat else "")
            + (
                f"• <b>Entry Type:</b> {_esc_html(entry_type_text)}\n"
                if entry_type_text
                else ""
            )
            + (f"• <b>Plan Notes:</b> {_esc_html(plan_notes)}\n" if plan_notes else "")
        )

    return (
        "📐 <b>Pending Order Plan</b>\n"
        f"• <b>Symbol:</b> {_esc_html(sym)}\n"
        f"• <b>Regime:</b> {_esc_html(regime)}\n"
        f"• <b>Type:</b> {_esc_html(typ_s)}\n"
        f"• <b>Direction:</b> {_esc_html(rec.get('direction','HOLD'))}\n"
        f"• <b>Entry:</b> {_esc_html(entry_s)}\n"
        f"• <b>SL:</b> {_esc_html(sl_s)}  (ATR/structure)\n"
        f"• <b>TP:</b> {_esc_html(tp_s)}  (ATR/structure)\n"
        f"• <b>R:R:</b> {_esc_html(rr_s)} (floor {rr_floor})\n" + strat_lines + "\n"
        f"• <b>Plan Notes:</b> {_esc_html(plan_notes)}\n"
        f"💡 <b>Why:</b> {_esc_html(rec.get('reasoning') or '—')}\n"
        f"{arm_line}"
        f"{spread_note}"
    )


# Fundamentals
from docx import Document


def load_daily_fundamentals() -> str:
    p = Path(settings.FUND_DOCX_PATH)
    if not p.exists():
        return "No fundamentals/sentiment document found today."
    try:
        doc = Document(str(p))
        chunks = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        full = "\n".join(chunks)
        return full[-1500:]
    except Exception:
        return "Unable to parse the fundamentals/sentiment document."


def register_trading_handlers(app, journal_repo: JournalRepo):
    # Commands (group 0)
    app.add_handler(CommandHandler("trade", trade_command), group=0)
    app.add_handler(CommandHandler("analyse", trade_command), group=0)
    app.add_handler(CommandHandler("critic", critic_command), group=0)  # << NEW
    app.add_handler(CommandHandler("monitor", monitor_command), group=0)

    # Exec-related callbacks only (group 1)
    exec_pattern = r"^(exec2\|.*|mkt\|refresh\|.*|retry\|.*|ignore)$"
    app.add_handler(CallbackQueryHandler(exec_callback, pattern=exec_pattern), group=1)
    pend_pattern = r"^(pend\|(plan|place|arm_oco)\|.*)$"
    app.add_handler(
        CallbackQueryHandler(pending_callbacks, pattern=pend_pattern), group=1
    )

    # Shared objects
    app.bot_data["journal_repo"] = journal_repo
    app.bot_data.setdefault("range_state", {})

    # Hook position watcher close -> post-mortem & online updates (unchanged)
    try:
        poswatch = app.bot_data.get("poswatch")
        logger.debug(
            "poswatch=%s attrs=%s", type(poswatch), dir(poswatch) if poswatch else None
        )
        if poswatch:

            def _on_close_glue(payload: dict):
                try:
                    chat_id = int(payload.get("chat_id") or 0)
                except Exception:
                    chat_id = 0
                on_position_closed_app(app, chat_id, payload or {})

            if hasattr(poswatch, "set_close_handler") and callable(
                getattr(poswatch, "set_close_handler")
            ):
                poswatch.set_close_handler(_on_close_glue)
                logger.info("poswatch: wired via set_close_handler")
            elif hasattr(poswatch, "on_close") and callable(
                getattr(poswatch, "on_close")
            ):
                poswatch.on_close(_on_close_glue)
                logger.info("poswatch: wired via on_close")
            elif hasattr(poswatch, "subscribe") and callable(
                getattr(poswatch, "subscribe")
            ):
                try:
                    poswatch.subscribe("close", _on_close_glue)
                    logger.info("poswatch: wired via subscribe('close', ...)")
                except Exception:
                    logger.warning(
                        "poswatch.subscribe exists but subscribe('close', cb) failed"
                    )
            else:
                logger.warning("poswatch found, but no close-handler API detected")
    except Exception:
        logger.exception("Failed to hook poswatch close handler")


def _fetch_series(symbol: str, tf: int, bars: int) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if rates is None:
        raise RuntimeError(f"No data returned for {symbol} tf={tf} (None)")
    try:
        n = len(rates)
    except TypeError:
        n = int(getattr(rates, "size", 0))
    if n == 0:
        raise RuntimeError(f"No data returned for {symbol} tf={tf} (empty)")
    df = pd.DataFrame(rates)
    if "time" in df.columns:
        try:
            df["time"] = pd.to_datetime(df["time"], unit="s")
        except Exception:
            pass
    return df


# ---- OCO helpers -------------------------------------------------------------


def _side_from_plan_dir(plan_dir: str) -> str:
    """Map plan.direction (LONG/SHORT/BUY/SELL/OCO) to order side."""
    d = (plan_dir or "").upper()
    if d in ("BUY", "LONG"):
        return "buy"
    if d in ("SELL", "SHORT"):
        return "sell"
    if d == "OCO":
        return None  # FIXED Bug #3: Signal OCO needs special handling
    return ""


async def _place_oco_breakout(
    update, context, chat_id: int, sym: str, plan_obj: dict, payload: dict, tech: dict
):
    """
    Places two pending orders (one each way) and starts a tiny watcher that cancels the opposite leg once one is filled.
    """
    if not plan_obj or not (plan_obj.get("pending_type") or "").startswith("OCO"):
        await update.callback_query.message.reply_text(
            "⚠️ No OCO plan available — re-run /trade."
        )
        return

    comp = plan_obj.get("oco_companion") or {}
    if not comp or comp.get("entry") is None or plan_obj.get("entry") is None:
        await update.callback_query.message.reply_text(
            "⚠️ OCO companion leg missing levels."
        )
        return

    # Primary leg (A)
    # FIXED Bug #3: Handle None return from _side_from_plan_dir for OCO
    side_a_raw = plan_obj.get("order_side") or _side_from_plan_dir(plan_obj.get("direction"))
    if side_a_raw is None:
        # OCO case - use explicit order_side or default to buy
        side_a = (plan_obj.get("order_side") or "buy").lower()
    else:
        side_a = (side_a_raw or payload.get("side") or "buy").lower()
    
    entry_a = float(plan_obj.get("entry"))
    sl_a = plan_obj.get("sl")
    tp_a = plan_obj.get("tp")

    # Companion leg (B)
    side_b_raw = comp.get("order_side") or _side_from_plan_dir(comp.get("direction"))
    if side_b_raw is None:
        # OCO case - use explicit order_side or opposite of A
        side_b = (comp.get("order_side") or ("sell" if side_a == "buy" else "buy")).lower()
    else:
        side_b = (side_b_raw or ("sell" if side_a == "buy" else "buy")).lower()
    
    entry_b = float(comp.get("entry"))
    sl_b = comp.get("sl")
    tp_b = comp.get("tp")

    mt5svc = MT5Service()
    try:
        await _in_thread(mt5svc.connect)
        await _in_thread(mt5svc.ensure_symbol, sym)
    except Exception as e:
        await update.callback_query.message.reply_text(f"❌ OCO error (connect): {e}")
        return

    # Risk% (risk realized on only one leg)
    risk_pct = float(
        payload.get("risk_pct") or getattr(settings, "RISK_DEFAULT_PCT", 1.0)
    )
    if sl_a is None or sl_b is None:
        lot_a = lot_b = float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))
    else:
        lot_a = await _in_thread(
            mt5svc.risk_to_lot, sym, entry_a, float(sl_a), risk_pct
        )
        lot_b = await _in_thread(
            mt5svc.risk_to_lot, sym, entry_b, float(sl_b), risk_pct
        )
    lot_a = await _in_thread(mt5svc.normalise_lot, sym, lot_a)
    lot_b = await _in_thread(mt5svc.normalise_lot, sym, lot_b)

    import time

    oco_id = f"oco{int(time.time())%100000}"

    # Leg A
    try:
        res_a = await asyncio.wait_for(
            _in_thread(
                mt5svc.open_order,
                sym,
                side_a,
                entry=entry_a,
                sl=sl_a,
                tp=tp_a,
                lot=lot_a,
                risk_pct=None,
                comment=f"{oco_id}:A",
            ),
            timeout=12,
        )
    except Exception as e:
        await update.callback_query.message.reply_text(
            f"❌ OCO A failed: {type(e).__name__}: {e}"
        )
        return

    if not res_a.get("ok"):
        await update.callback_query.message.reply_text(
            f"❌ OCO A failed: {res_a.get('message')}"
        )
        return

    # Leg B
    try:
        res_b = await asyncio.wait_for(
            _in_thread(
                mt5svc.open_order,
                sym,
                side_b,
                entry=entry_b,
                sl=sl_b,
                tp=tp_b,
                lot=lot_b,
                risk_pct=None,
                comment=f"{oco_id}:B",
            ),
            timeout=12,
        )
    except Exception as e:
        # Roll back A
        try:
            tk_a = res_a.get("details", {}).get("ticket")
            await _in_thread(_cancel_pending_by_ticket, mt5svc, tk_a)
        except Exception:
            pass
        await update.callback_query.message.reply_text(
            f"❌ OCO B failed: {type(e).__name__}: {e}"
        )
        return

    if not res_b.get("ok"):
        # Roll back A
        try:
            tk_a = res_a.get("details", {}).get("ticket")
            await _in_thread(_cancel_pending_by_ticket, mt5svc, tk_a)
        except Exception:
            pass
        await update.callback_query.message.reply_text(
            f"❌ OCO B failed: {res_b.get('message')}"
        )
        return

    # Confirm to user
    txt_a = _render_execution_message(sym, f"{side_a} (OCO:A)", risk_pct, res_a)
    txt_b = _render_execution_message(sym, f"{side_b} (OCO:B)", risk_pct, res_b)
    await update.callback_query.message.reply_text(txt_a + "\n" + txt_b)

    # Register OCO group + start watcher
    appdata = context.application.bot_data
    oco_groups = appdata.setdefault("oco_groups", {})
    tk_a = res_a.get("details", {}).get("ticket")
    tk_b = res_b.get("details", {}).get("ticket")
    oco_groups[oco_id] = {"symbol": sym, "a": int(tk_a), "b": int(tk_b), "active": True}

    job = context.job_queue.run_repeating(
        _oco_watch_tick,
        interval=2,
        first=2,
        data={"oco_id": oco_id, "chat_id": chat_id},
        name=f"oco:{oco_id}",
    )
    appdata.setdefault("oco_jobs", {})[oco_id] = job


def _cancel_pending_by_ticket(mt5svc: MT5Service, ticket: int) -> bool:
    # Prefer MT5Service.cancel_order if you have it; else raw MT5 call
    try:
        if hasattr(mt5svc, "cancel_order"):
            return bool(mt5svc.cancel_order(ticket))
    except Exception:
        pass
    import MetaTrader5 as mt5

    req = {"action": mt5.TRADE_ACTION_REMOVE, "order": int(ticket)}
    r = mt5.order_send(req)
    return bool(getattr(r, "retcode", 0) == mt5.TRADE_RETCODE_DONE)


def _ticket_in_open_orders(symbol: str, ticket: int) -> bool:
    try:
        import MetaTrader5 as mt5

        orders = mt5.orders_get(symbol=symbol)
        return any(getattr(o, "ticket", None) == int(ticket) for o in (orders or []))
    except Exception:
        return False


def _has_open_position_for_symbol(symbol: str) -> bool:
    try:
        import MetaTrader5 as mt5

        poss = mt5.positions_get(symbol=symbol)
        return bool(poss and len(poss) > 0)
    except Exception:
        return False


def _oco_disarm(context, oco_id: str, reason: str = "done"):
    jobs = context.application.bot_data.get("oco_jobs", {})
    job = jobs.pop(oco_id, None)
    if job:
        try:
            job.schedule_removal()
        except Exception:
            pass
    groups = context.application.bot_data.get("oco_groups", {})
    if oco_id in groups:
        groups[oco_id]["active"] = False
    return reason


def _oco_watch_tick(context):
    """Runs every 2s. If one leg disappears (filled/cancelled), cancel the other."""
    data = context.job.data or {}
    oco_id = data.get("oco_id")
    chat_id = data.get("chat_id")
    groups = context.application.bot_data.get("oco_groups", {})
    g = groups.get(oco_id)
    if not g or not g.get("active"):
        _oco_disarm(context, oco_id, "inactive")
        return

    sym = g["symbol"]
    a = int(g["a"])
    b = int(g["b"])
    a_open = _ticket_in_open_orders(sym, a)
    b_open = _ticket_in_open_orders(sym, b)

    # If one leg is gone (likely filled), cancel the other if still open
    if a_open and not b_open:
        try:
            mt5svc = MT5Service()
            mt5svc.connect()
            mt5svc.ensure_symbol(sym)
            _cancel_pending_by_ticket(mt5svc, a)
        except Exception:
            pass
        _oco_disarm(context, oco_id, "B filled; A cancelled")
        try:
            context.application.bot.send_message(
                chat_id, f"🔗 OCO {oco_id}: leg B triggered — cancelled A."
            )
        except Exception:
            pass
        return

    if b_open and not a_open:
        try:
            mt5svc = MT5Service()
            mt5svc.connect()
            mt5svc.ensure_symbol(sym)
            _cancel_pending_by_ticket(mt5svc, b)
        except Exception:
            pass
        _oco_disarm(context, oco_id, "A filled; B cancelled")
        try:
            context.application.bot.send_message(
                chat_id, f"🔗 OCO {oco_id}: leg A triggered — cancelled B."
            )
        except Exception:
            pass
        return

    # If neither is open anymore, disarm (user cancelled both)
    if (not a_open) and (not b_open):
        _oco_disarm(context, oco_id, "both gone")
        return

    # Optional: stop watcher once any position exists for symbol
    if _has_open_position_for_symbol(sym):
        _oco_disarm(context, oco_id, "position open")
        return


def _build_tech_from_bridge(
    multi: dict, symbol: str
) -> tuple[dict, pd.DataFrame | None, pd.DataFrame | None]:
    m5 = multi.get("M5", {})
    m15 = multi.get("M15", {})
    m30 = multi.get("M30", {})
    h1 = multi.get("H1", {})

    m5_df = None
    m15_df = None
    try:
        m5_df = _fetch_series(symbol, mt5.TIMEFRAME_M5, 120)
    except Exception as e:
        logger.debug("M5 series fetch failed: %s", e)
    try:
        m15_df = _fetch_series(symbol, mt5.TIMEFRAME_M15, 80)
    except Exception as e:
        logger.debug("M15 series fetch failed: %s", e)

    price_now = _to_scalar(m5.get("close") or h1.get("close") or 0.0)
    ema200_ref = _to_scalar(m5.get("ema_200") or h1.get("ema_200") or price_now)
    ema_alignment = bool(price_now >= ema200_ref)

    ema200_now = _to_scalar(h1.get("ema_200") or 0.0)
    ema200_prev = _to_scalar(h1.get("ema_200_prev") or 0.0)
    ema_slope_h1 = 0.0
    try:
        if ema200_prev and ema200_now:
            ema_slope_h1 = (ema200_now - ema200_prev) / max(1e-9, ema200_prev)
    except Exception:
        pass

    tech = {
        "symbol": symbol,
        "close": price_now,
        "atr_14": _to_scalar(m5.get("atr_14") or 0.0),
        "ema_20": _to_scalar(m5.get("ema_20") or 0.0),
        "ema_50": _to_scalar(m5.get("ema_50") or 0.0),
        "ema_200": ema200_ref,
        "adx": _to_scalar(m5.get("adx_14") or m5.get("adx") or 0.0),
        "bb_width": _to_scalar(m5.get("bb_width") or 0.0),
        "session": m5.get("session", "Mid"),
        "ema_alignment": ema_alignment,
        "ema_slope_h1": ema_slope_h1,
        "min_confidence": 0.62,
        "news_block": False,
    }

    # --------- additional TA: RSI & candlestick patterns ---------
    # Compute a 14-period RSI on the M5 close series if possible.  We use
    # simple moving averages for average gain/loss to keep it lightweight.
    rsi14 = None
    if m5_df is not None and len(m5_df) >= 15:
        try:
            close_series = m5_df["close"].astype(float)
            # Price differences
            diffs = close_series.diff().dropna()
            gains = diffs.clip(lower=0.0)
            losses = (-diffs).clip(lower=0.0)
            # Use rolling mean for the 14-bar window
            avg_gain = gains.rolling(14).mean().iloc[-1]
            avg_loss = losses.rolling(14).mean().iloc[-1]
            if avg_loss is not None and not math.isnan(avg_loss) and avg_loss > 1e-12:
                rs = avg_gain / avg_loss
                rsi14 = 100.0 - (100.0 / (1.0 + rs))
            elif avg_gain is not None and not math.isnan(avg_gain):
                rsi14 = 100.0

        except Exception:
            # guard against any misalignment
            rsi14 = None
    # Detect the most recent candlestick pattern and its bias on M5 and M15 data.
    pattern_m5_name = ""
    pattern_m5_bias = 0
    if m5_df is not None and len(m5_df) >= 2:
        try:
            pattern_m5_name, pattern_m5_bias = detect_recent_patterns(m5_df)
        except Exception:
            pattern_m5_name, pattern_m5_bias = "", 0
    pattern_m15_name = ""
    pattern_m15_bias = 0
    if m15_df is not None and len(m15_df) >= 2:
        try:
            pattern_m15_name, pattern_m15_bias = detect_recent_patterns(m15_df)
        except Exception:
            pattern_m15_name, pattern_m15_bias = "", 0

    # Add to tech dictionary
    tech["rsi_14"] = rsi14
    tech["pattern_m5"] = pattern_m5_name
    tech["pattern_m15"] = pattern_m15_name
    tech["pattern_bias"] = pattern_m5_bias  # use M5 bias as primary for critique

    # Sanitize nested timeframe dictionaries to handle array values from IndicatorBridge fallback
    def _sanitize_tf_dict(tf_dict):
        """Convert any array/Series values to scalars in a timeframe dictionary."""
        import pandas as pd
        import numpy as np
        
        sanitized = {}
        for key, value in tf_dict.items():
            # Handle pandas Series
            if isinstance(value, pd.Series):
                if len(value) > 0:
                    sanitized[key] = float(value.iloc[-1]) if not pd.isna(value.iloc[-1]) else 0.0
                else:
                    sanitized[key] = 0.0
            # Handle lists/tuples/arrays
            elif isinstance(value, (list, tuple, np.ndarray)):
                if len(value) > 0:
                    sanitized[key] = float(value[-1]) if value[-1] is not None else 0.0
                else:
                    sanitized[key] = 0.0
            # Handle None
            elif value is None:
                sanitized[key] = None
            # Try to convert to basic Python types for JSON serialization
            elif isinstance(value, (np.integer, np.floating)):
                sanitized[key] = float(value)
            elif isinstance(value, (int, float, str, bool)):
                sanitized[key] = value
            else:
                # For any other type, try to convert to string as last resort
                try:
                    sanitized[key] = float(value)
                except:
                    sanitized[key] = str(value)
        return sanitized
    
    tech["_tf_M5"] = _sanitize_tf_dict(m5)
    tech["_tf_M15"] = _sanitize_tf_dict(m15)

    # --- Phase3: derive UX strings for MTF/ADX/Regime ---
    try:
        conf = compute_mtf_confluence(tech)
    except Exception:
        conf = {"score": 0.0, "bias": None, "details": {}}
    try:
        adx_m15 = float(tech.get("_tf_M15", {}).get("adx") or tech.get("adx") or 0.0)
    except Exception:
        adx_m15 = 0.0
    regime_str = str(tech.get("regime") or tech.get("market_regime") or "").title()
    if not regime_str:
        regime_str = str(tech.get("regime_label") or "").title()
    mtf_bias = str(conf.get("bias") or "").upper() or "?"
    mtf_score = int(100 * float(conf.get("score") or 0.0))
    mtf_line = f"MTF: {mtf_bias} ({mtf_score}%), ADX(M15)={adx_m15:.1f}"
    regime_line = f"Regime: {regime_str}" if regime_str else ""

    tech["_tf_M30"] = _sanitize_tf_dict(m30)
    tech["_tf_H1"] = _sanitize_tf_dict(h1)

    # Populate detection results (Phase 0.2.2: Tech Dict Integration)
    try:
        from infra.tech_dict_enricher import populate_detection_results
        populate_detection_results(tech, symbol, m5_df, m15_df)
    except Exception as e:
        logger.debug(f"Detection results population failed for {symbol}: {e}")
        # Continue without detection results - graceful degradation
    
    return tech, m5_df, m15_df


# ---------- merge logic (RESTORED) ----------
def _merge_gate_llm(gate: dict, llm: dict) -> dict:
    g_side = str(gate.get("direction", "HOLD")).upper()
    l_side = str(llm.get("direction", "HOLD")).upper()

    # Agree → use LLM levels; tag gate info and carry diagnostics
    if g_side in ("BUY", "SELL") and l_side == g_side:
        out = dict(llm)
        reason = f"{llm.get('reasoning','')}\n(Gate agreed: {gate.get('strategy','')}, rr_gate={_fmt_num(gate.get('rr'),2)})"
        out["reasoning"] = reason.strip()
        out["regime"] = gate.get("regime", llm.get("regime"))
        for k in (
            "mtf_label",
            "mtf_score",
            "pattern_m5",
            "pattern_m15",
            "rsi5",
            "rsi15",
            "rsi30",
            "touches_hi",
            "touches_lo",
            "near_edge",
            "guards",
            "triggers",
        ):
            if k in gate and k not in out:
                out[k] = gate[k]
        return out

    # Disagree → prefer gate, include LLM dissent
    if g_side in ("BUY", "SELL") and l_side in ("BUY", "SELL") and g_side != l_side:
        out = dict(gate)
        dissent = (
            f"LLM suggested {l_side} due to: {llm.get('reasoning','(no reason)')[:220]}"
        )
        out["reasoning"] = f"{gate.get('reasoning','')}\n[{dissent}]"
        return out

    if g_side in ("BUY", "SELL") and l_side == "HOLD":
        out = dict(gate)
        out["reasoning"] = (
            f"{gate.get('reasoning','')}\n[LLM caution: {llm.get('reasoning','(no reason)')[:220]}]"
        )
        return out

    if g_side == "HOLD" and l_side in ("BUY", "SELL"):
        out = dict(llm)
        out["reasoning"] = (
            f"{llm.get('reasoning','')}\n[Gate warning: {gate.get('reasoning','HOLD')} — proceed carefully.]"
        )
        for k in (
            "mtf_label",
            "mtf_score",
            "pattern_m5",
            "pattern_m15",
            "rsi5",
            "rsi15",
            "rsi30",
            "touches_hi",
            "touches_lo",
            "near_edge",
            "guards",
            "triggers",
        ):
            if k in gate and k not in out:
                out[k] = gate[k]
        out["regime"] = gate.get("regime", llm.get("regime"))
        return out

    return llm


# ---------- tiny payload cache for short callback_data ----------
def _stash_cb(app, chat_id: int, payload: dict, ttl_sec: int = 900) -> str:
    bucket = app.bot_data.setdefault(_CB_BUCKET, {})
    token = (
        f"{int(time.time())%100000:05d}" + str(abs(hash((chat_id, time.time()))))[-5:]
    )
    bucket[token] = {
        "chat_id": chat_id,
        "payload": payload,
        "exp": time.time() + ttl_sec,
    }
    # cleanup
    now = time.time()
    for k in list(bucket.keys()):
        try:
            if bucket[k]["exp"] < now:
                del bucket[k]
        except Exception:
            del bucket[k]
    return token


def _pop_cb(app, token: str, chat_id: int) -> Optional[dict]:
    bucket = app.bot_data.get(_CB_BUCKET, {})
    item = bucket.pop(token, None)
    if not item:
        return None
    if item.get("chat_id") != chat_id:
        return None
    if item.get("exp", 0) < time.time():
        return None
    return item.get("payload")


# ---------- side inference / validation helpers ----------
def _infer_side_from_levels(entry, sl, tp):
    try:
        e, s, t = float(entry), float(sl), float(tp)
    except Exception:
        return None
    # SELL structure: SL above entry, TP below entry
    if s > e and t < e:
        return "sell"
    # BUY structure: SL below entry, TP above entry
    if s < e and t > e:
        return "buy"
    return None


def _levels_match_side_by_entry(side: str, entry, sl, tp) -> bool:
    try:
        e, s, t = float(entry), float(sl), float(tp)
    except Exception:
        return False
    return (s < e and t > e) if side == "buy" else (s > e and t < e)


def _levels_match_side_by_price(side: str, price, sl, tp) -> bool:
    """
    Sanity check at live price so MT5Service won't drop SL/TP as wrong-side.
    For BUY: SL must be < price and TP > price; for SELL: SL > price and TP < price.
    """
    try:
        p, s, t = float(price), float(sl), float(tp)
    except Exception:
        return False
    return (s < p and t > p) if side == "buy" else (s > p and t < p)


def _validate_sr_anchor(rec: dict, tech: dict) -> tuple[bool, list[str], dict]:
    """
    Ensure SL/TP are anchored to the nearest *opposite* S/R band with a small pad.
    Returns (ok, reasons, possibly_adjusted_rec).
    """
    out = dict(rec or {})
    reasons = []
    sr = tech.get("sr")
    if not isinstance(sr, dict):
        return True, reasons, out

    zones = sr.get("zones") or []
    if not zones:
        return True, reasons, out

    atr = float(tech.get("atr_14") or 0.0)
    if atr <= 0:
        return True, reasons, out

    def band_top(z):
        return float(z.get("level")) + float(z.get("width") or 0.0)

    def band_bot(z):
        return float(z.get("level")) - float(z.get("width") or 0.0)

    direction = (out.get("direction") or "").upper()
    e = float(out.get("entry") or tech.get("close") or 0.0)
    sl = out.get("sl")
    tp = out.get("tp")
    if direction not in ("BUY", "SELL") or sl is None or tp is None:
        return True, reasons, out

    above = sorted(
        [z for z in zones if float(z.get("level") or 0.0) >= e],
        key=lambda z: float(z.get("level")),
    )
    below = sorted(
        [z for z in zones if float(z.get("level") or 0.0) <= e],
        key=lambda z: float(z.get("level")),
        reverse=True,
    )
    z_above = above[0] if above else None
    z_below = below[0] if below else None

    keep = 0.05 * atr
    pad = 0.15 * atr

    changed = False
    if direction == "BUY" and z_above and z_below:
        sl_ok = float(sl) <= band_bot(z_below) - keep
        tp_ok = float(tp) <= band_top(z_above) + (0.20 * atr)
        if not sl_ok:
            reasons.append("llm_anchor_sl_support_violation")
            out["sl"] = min(float(sl), band_bot(z_below) - pad)
            changed = True
        if not tp_ok:
            reasons.append("llm_anchor_tp_resistance_violation")
            out["tp"] = min(float(tp), band_top(z_above))
            changed = True
    elif direction == "SELL" and z_above and z_below:
        sl_ok = float(sl) >= band_top(z_above) + keep
        tp_ok = float(tp) >= band_bot(z_below) - (0.20 * atr)
        if not sl_ok:
            reasons.append("llm_anchor_sl_resistance_violation")
            out["sl"] = max(float(sl), band_top(z_above) + pad)
            changed = True
        if not tp_ok:
            reasons.append("llm_anchor_tp_support_violation")
            out["tp"] = max(float(tp), band_bot(z_below))
            changed = True

    # re-compute RR if changed
    try:
        if changed:
            e = float(out.get("entry") or e)
            s = float(out.get("sl") or sl)
            t = float(out.get("tp") or tp)
            out["rr"] = abs(t - e) / max(1e-9, abs(e - s))
    except Exception:
        pass

    ok = len(reasons) == 0
    return ok, reasons, out


# ---------- execution message helper ----------
def _render_execution_message(
    symbol: str, side: str, risk_pct: float | None, result: dict
) -> str:
    """
    Build a human-friendly execution summary using the symbol's digits and actual fill price.
    Expects the dict returned by MT5Service.open_order()/market_order().
    """
    details = result.get("details", {}) or {}
    ticket = details.get("ticket") or "—"
    position = details.get("final_position") or details.get("position") or "—"

    # Prefer the *executed* price, then final SL/TP readback if available
    px_exec = (
        details.get("price_executed")
        or details.get("price")
        or details.get("price_requested")
    )
    sl_final = details.get("final_sl", details.get("sl"))
    tp_final = details.get("final_tp", details.get("tp"))

    # Format by symbol digits
    entry_s = fmt_price(symbol, px_exec) if px_exec is not None else "—"
    sl_s = fmt_price(symbol, sl_final) if sl_final else "—"
    tp_s = fmt_price(symbol, tp_final) if tp_final else "—"

    # Show risk% if you passed it in
    risk_txt = f"(risk {risk_pct:.2f}%)" if isinstance(risk_pct, (int, float)) else ""

    # Tickets from split fills
    parts = result.get("parts", []) if isinstance(result, dict) else []
    if parts:
        tickets = [
            str(p.get("details", {}).get("ticket"))
            for p in parts
            if p.get("details", {}).get("ticket") is not None
        ]
        ticket_display = ("#" + ", #".join(tickets)) if tickets else f"#{ticket}"
    else:
        ticket_display = f"#{ticket}"

    return (
        f"✅ Executed {symbol} {side.upper()} {risk_txt}\n"
        f"• Ticket(s): {ticket_display} | Position: {position}\n"
        f"• Lot: {_fmt_num(details.get('volume') or '—')}\n"
        f"• Entry: {entry_s}\n"
        f"• SL: {sl_s}\n"
        f"• TP: {tp_s}"
    )


# ---- position-close glue (updates memory, bandit, tuner, and sends post-mortem) ----
def on_position_closed_app(app, chat_id: int, close_payload: dict):
    """
    close_payload is expected to include:
      symbol, ticket, pnl, hit ("TP"/"SL"/"MANUAL"), duration_min, exit_price, entry_price, sl, tp
      (plus any extras you have; we handle missing keys defensively)
    """
    try:
        symbol = normalise_symbol(str(close_payload.get("symbol") or _DEF_SYMBOL))
        ticket = str(close_payload.get("ticket") or "")
        outcome = {
            "pnl": close_payload.get("pnl"),
            "hit": close_payload.get("hit"),
            "duration_min": close_payload.get("duration_min"),
            "exit_price": close_payload.get("exit_price"),
        }

        # 1) Persist outcome to MemoryStore
        try:
            ms = MemoryStore(
                getattr(settings, "MEMORY_STORE_PATH", "memory_store.sqlite")
            )
            if ticket:
                ms.add_outcome(ticket=ticket, outcome=outcome)
        except Exception:
            logger.debug("MemoryStore.add_outcome failed", exc_info=True)

        # 2) Online update: contextual bandit
        try:
            selector = StrategySelector(
                getattr(settings, "STRATEGY_SELECTOR_PATH", "strategy_selector.json")
            )
            st = LAST_REC.get((chat_id, symbol), {}) or {}
            chosen = (
                st.get("strategy")
                or st.get("rec", {}).get("strategy")
                or "trend_pullback"
            )
            feat = {
                "adx": close_payload.get("adx", 0.0),
                "bb_width": close_payload.get("bb_width", 0.0),
                "rsi_align": close_payload.get("rsi_align", 0.0),
                "spike_up": bool(close_payload.get("spike_up", False)),
                "spike_dn": bool(close_payload.get("spike_dn", False)),
                "session": close_payload.get("session"),
            }
            reward = (
                1.0
                if close_payload.get("hit") == "TP"
                else (-1.0 if close_payload.get("hit") == "SL" else 0.0)
            )
            selector.update(symbol, feat, chosen, reward)
        except Exception:
            logger.debug("StrategySelector.update failed", exc_info=True)

        # 3) Nudge dynamic thresholds
        try:
            tuner = ThresholdTuner(
                getattr(settings, "THRESHOLD_TUNER_PATH", "threshold_tuner.json")
            )
            tuner.update_with_outcome(
                symbol=symbol,
                tf="M5",
                hit_tp=(close_payload.get("hit") == "TP"),
                hit_sl=(close_payload.get("hit") == "SL"),
            )
        except Exception:
            logger.debug("ThresholdTuner.update_with_outcome failed", exc_info=True)

        # 3.5) Phase 0.5: Record to performance tracker
        try:
            if ticket:
                ticket_int = int(ticket) if ticket.isdigit() else None
                if ticket_int:
                    journal = JournalRepo()
                    strategy_name = journal._extract_strategy_name(ticket_int)
                    
                    if strategy_name:
                        from infra.strategy_performance_tracker import StrategyPerformanceTracker
                        tracker = StrategyPerformanceTracker()
                        
                        # Determine result from hit and pnl
                        hit = close_payload.get("hit", "")
                        pnl = close_payload.get("pnl", 0.0)
                        
                        if hit == "TP" or (pnl and pnl > 0):
                            result = "win"
                        elif hit == "SL" or (pnl and pnl < 0):
                            result = "loss"
                        else:
                            result = "breakeven"
                        
                        # Extract trade details
                        entry_price = close_payload.get("entry_price")
                        exit_price = close_payload.get("exit_price")
                        r_multiple = close_payload.get("r_multiple") or close_payload.get("rr")
                        
                        # Format timestamps (if available)
                        entry_time = None
                        exit_time = None
                        if "entry_time" in close_payload:
                            entry_time = close_payload["entry_time"]
                        if "exit_time" in close_payload:
                            exit_time = close_payload["exit_time"]
                        
                        tracker.record_trade(
                            strategy_name=strategy_name,
                            symbol=symbol,
                            result=result,
                            pnl=float(pnl) if pnl is not None else 0.0,
                            rr=float(r_multiple) if r_multiple is not None else None,
                            entry_price=float(entry_price) if entry_price is not None else None,
                            exit_price=float(exit_price) if exit_price is not None else None,
                            entry_time=entry_time,
                            exit_time=exit_time
                        )
                        logger.debug(f"Recorded trade {ticket} to performance tracker for strategy {strategy_name}")
        except Exception as e:
            logger.debug(f"Failed to record trade {ticket} to performance tracker: {e}", exc_info=True)
            # Don't fail position close if tracking fails

        # 4) Send the post-mortem template
        try:
            state = LAST_REC.get((chat_id, symbol), {}) or {}
            text = build_postmortem_text(
                symbol, {"outcome": outcome, **close_payload}, state
            )
            app.create_task(
                app.bot.send_message(chat_id, text)
            )  # <-- schedule instead of calling directly
        except Exception:
            logger.debug("post-mortem send failed", exc_info=True)

    except Exception:
        logger.exception("on_position_closed_app failed")


# --- helper: wire poswatch close-handler (best-effort, once) ---
def _wire_poswatch_close_handler(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    try:
        appdata = context.application.bot_data
        if appdata.get("poswatch_wired"):
            return
        poswatch = appdata.get("poswatch")
        if not poswatch:
            return

        def _cb(payload: dict | None):
            try:
                on_position_closed_app(context.application, chat_id, payload or {})
            except Exception:
                logger.exception("poswatch close-handler callback failed")

        wired = False
        try:
            if hasattr(poswatch, "set_close_handler"):
                poswatch.set_close_handler(_cb)
                wired = True
            elif hasattr(poswatch, "on_close"):
                poswatch.on_close(_cb)
                wired = True
            elif hasattr(poswatch, "subscribe"):
                # support subscribe("close", cb) or subscribe(cb)
                try:
                    poswatch.subscribe("close", _cb)
                    wired = True
                except TypeError:
                    poswatch.subscribe(_cb)
                    wired = True
        except Exception:
            logger.debug("Attempt to wire poswatch failed", exc_info=True)

        if wired:
            appdata["poswatch_wired"] = True
            logger.info("poswatch close-handler wired")
        else:
            logger.info(
                "poswatch found, but no close-handler API (set_close_handler/on_close/subscribe) detected"
            )
    except Exception:
        logger.debug("poswatch wiring error", exc_info=True)


# ---------- CRITIC COMMAND ----------
async def critic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /critic [SYMBOL?]
    Reports the last Critic verdict for the symbol in this chat, plus key metrics & hints.
    """
    reply = update.message if update.message else update.callback_query.message
    chat_id = update.effective_chat.id

    # Parse symbol (optional)
    arg_sym = None
    try:
        if update.message and update.message.text:
            parts = update.message.text.strip().split()
            if len(parts) >= 2:
                arg_sym = parts[1]
    except Exception:
        pass

    sym = normalise_symbol(arg_sym or _DEF_SYMBOL)
    state = LAST_REC.get((chat_id, sym))
    if not state:
        await reply.reply_text(
            f"ℹ️ No recent analysis for {sym}. Run /trade {sym} first."
        )
        return

    rec = state.get("rec", {}) or {}
    approved = rec.get("critic_approved")
    reasons = rec.get("critic_reasons", []) or []

    # Pull quick live context for metrics
    mt5svc = MT5Service()
    try:
        mt5svc.connect()
        mt5svc.ensure_symbol(sym)
    except Exception:
        pass

    live_bid = live_ask = None
    spread = 0.0
    tick = point = 0.0
    try:
        q = mt5svc.get_quote(sym)
        live_bid, live_ask = q.bid, q.ask
        spread = max(0.0, (live_ask or 0.0) - (live_bid or 0.0))
        si = mt5.symbol_info(sym)
        tick = float(
            getattr(si, "trade_tick_size", 0.0) or getattr(si, "point", 0.0) or 0.0
        )
        point = float(getattr(si, "point", 0.0) or tick)
    except Exception:
        pass

    # Get ATR/ADX quickly from bridge
    atr_val = adx_val = 0.0
    ema_align = None
    gate_strategy = None
    try:
        bridge = IndicatorBridge(settings.MT5_FILES_DIR)
        multi = bridge.get_multi(sym)
        m5 = multi.get("M5", {})
        h1 = multi.get("H1", {})
        atr_val = _to_scalar(m5.get("atr_14") or 0.0)
        adx_val = _to_scalar(m5.get("adx_14") or m5.get("adx") or 0.0)
        price_now = _to_scalar(m5.get("close") or h1.get("close") or 0.0)
        ema200_ref = _to_scalar(m5.get("ema_200") or h1.get("ema_200") or price_now)
        ema_align = bool(price_now >= ema200_ref)
        gate_strategy = state.get("strategy")
    except Exception:
        pass

    spread_pct_atr = (spread / atr_val) if atr_val > 0 else 0.0

    # Rules (from settings)
    min_rr = float(getattr(settings, "MIN_RR_FOR_MARKET", 1.2))
    max_spread_pct_atr = float(getattr(settings, "MAX_SPREAD_PCT_ATR", 0.35))
    atr_min_ticks = 2.0  # internal hard guard used by Critic

    # If no stored verdict (older analysis), do a quick local critique
    if approved is None:
        try:
            oai = OpenAIService(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)
            tech_for_critic = {
                "adx": adx_val,
                "atr_14": atr_val,
                "ema_alignment": ema_align,
                "_tick": tick,
                "_point": point,
                "_live_spread": spread,
            }
            verdict = oai.critique(
                rec,
                tech_for_critic,
                rules={
                    "MIN_RR_FOR_MARKET": min_rr,
                    "max_spread_pct_atr": max_spread_pct_atr,
                },
            )
            approved = verdict["approved"]
            reasons = verdict["reasons"]
            rec["critic_approved"] = approved
            rec["critic_reasons"] = reasons
            LAST_REC[(chat_id, sym)]["rec"] = rec
        except Exception:
            pass

    # Hints
    hints = []
    for r in reasons:
        if r.startswith("rr_below_floor"):
            hints.append(f"Increase TP or tighten SL to reach min RR ≥ {min_rr:.2f}.")
        elif r == "atr_too_small":
            if tick > 0:
                need = max(atr_min_ticks * tick, tick * 2)
                hints.append(
                    f"Wait for ATR to expand (>{need:.6f}) or use a wider SL/TP."
                )
            else:
                hints.append("Wait for ATR to expand or use a wider SL/TP.")
        elif r.startswith("spread_pct_atr"):
            hints.append(f"Wait for spread < {max_spread_pct_atr*100:.0f}% of ATR.")
        elif r == "sl_not_below_entry":
            hints.append("For BUY, SL must be below entry.")
        elif r == "sl_not_above_entry":
            hints.append("For SELL, SL must be above entry.")
        elif r == "tp_not_above_entry":
            hints.append("For BUY, TP must be above entry.")
        elif r == "tp_not_below_entry":
            hints.append("For SELL, TP must be below entry.")
        elif r == "direction=HOLD":
            hints.append("No clear setup — wait for breakout or better confluence.")
        elif r == "ema_alignment_false":
            hints.append("EMA alignment weak — consider skipping or using lower risk.")
        elif r == "adx_weak(<14)":
            hints.append("Trend energy low — consider skipping or using lower risk.")

    # Pretty values
    entry_s = fmt_price(sym, rec.get("entry")) if rec.get("entry") is not None else "—"
    sl_s = fmt_price(sym, rec.get("sl")) if rec.get("sl") is not None else "—"
    tp_s = fmt_price(sym, rec.get("tp")) if rec.get("tp") is not None else "—"
    spread_s = fmt_price(sym, spread) if spread else _fmt_num(spread, 6)
    atr_s = fmt_price(sym, atr_val) if atr_val else _fmt_num(atr_val, 6)
    bid_s = fmt_price(sym, live_bid) if live_bid is not None else "—"
    ask_s = fmt_price(sym, live_ask) if live_ask is not None else "—"

    status = "✅ APPROVED" if approved else "❌ REJECTED"
    reasons_line = _esc_html(", ".join(reasons) if reasons else "(no issues)")

    # Risk% from mapping (if available)
    state_key = LAST_REC.get((chat_id, sym), {})
    risk_pct_mapped = state_key.get("risk_pct_mapped")
    risk_line = (
        f"\n• Risk% (mapped): {risk_pct_mapped:.2f}%"
        if isinstance(risk_pct_mapped, (int, float))
        else ""
    )

    text = (
        f"🧠 Critic report for {sym}\n"
        f"Status: {status}\n"
        f"Reasons: {reasons_line}\n"
        f"\n"
        f"Plan: {rec.get('direction','HOLD')} | Entry {entry_s} | SL {sl_s} | TP {tp_s} | RR={_fmt_num(rec.get('rr'),2)}\n"
        f"Metrics: ADX={_fmt_num(adx_val,2)} | ATR14={atr_s} | Spread={spread_s} "
        f"({spread_pct_atr*100:.1f}% of ATR) | EMA_align={bool(ema_align)} | Gate={gate_strategy}\n"
        f"Rules: min RR={min_rr:.2f} | max spread%ATR={max_spread_pct_atr:.2f} | ATR min ticks≈{atr_min_ticks:.0f}\n"
        f"Live: Bid={bid_s} | Ask={ask_s}{risk_line}"
    )

    if hints:
        text += "\n\n💡 <b>Hints:</b>\n" + "\n".join(
            f"• {_esc_html(h)}" for h in hints[:6]
        )

    # Buttons
    rows = [
        [
            InlineKeyboardButton("🔁 Re-run analysis", callback_data=f"retry|{sym}"),
            InlineKeyboardButton("↻ Refresh price", callback_data=f"mkt|refresh|{sym}"),
        ]
    ]

    try:
        await reply.reply_text(
            text, reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML
        )
    except Exception:
        await reply.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))


# ---------- MAIN /trade ----------
async def trade_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, symbol: str | None = None
):
    chat_id = getattr(getattr(update, "effective_chat", None), "id", None)
    logger.info("ENTER trade_command chat_id=%s", chat_id)
    print(f"[PRINT] ENTER trade_command chat_id={chat_id}")
    reply = update.message if update.message else update.callback_query.message

    # Best-effort: wire poswatch close-handler the first time this command runs
    _wire_poswatch_close_handler(context, chat_id)

    sym = normalise_symbol(symbol or (context.args[0] if context.args else _DEF_SYMBOL))
    await reply.reply_text(f"🔄 Gathering analysis for {sym}…")

    try:
        # Services
        mt5svc = MT5Service()
        mt5svc.connect()
        mt5svc.ensure_symbol(sym)
        bridge = IndicatorBridge(settings.MT5_FILES_DIR)
        oai = OpenAIService(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)
        journal_repo: JournalRepo = context.application.bot_data["journal_repo"]

        if settings.AUTO_ARRANGE:
            try:
                ChartArranger().arrange()
            except Exception:
                pass

        multi = bridge.get_multi(sym)
        m5 = multi.get("M5", {})
        m15 = multi.get("M15", {})
        m30 = multi.get("M30", {})
        h1 = multi.get("H1", {})

        tech, m5_df, m15_df = _build_tech_from_bridge(multi, sym)

        # ---- Dynamic threshold knobs (surface to GPT)
        try:
            tuner = ThresholdTuner(
                getattr(settings, "THRESHOLD_TUNER_PATH", "threshold_tuner.json")
            )
            tech["knob_state"] = tuner.get_knob_state(sym, "M5")
        except Exception:
            pass

        # ---- Contextual bandit: choose playbook (deterministic; GPT explains in 'reasoning')
        try:
            selector = StrategySelector(
                getattr(settings, "STRATEGY_SELECTOR_PATH", "strategy_selector.json")
            )
            # crude RSI alignment from M5/M15
            rsi_align = 0.0
            try:
                r5 = float(
                    tech.get("_tf_M5", {}).get("rsi_14") or tech.get("rsi_14") or 50.0
                )
                r15 = float(tech.get("_tf_M15", {}).get("rsi_14") or 50.0)
                rsi_align = (
                    1.0
                    if (r5 >= 55 and r15 >= 55)
                    else (-1.0 if (r5 <= 45 and r15 <= 45) else 0.0)
                )
            except Exception:
                pass

            feat = {
                "adx": tech.get("adx"),
                "bb_width": tech.get("bb_width"),
                "rsi_align": rsi_align,
                "spike_up": "SPIKE_UP" in (tech.get("triggers") or []),
                "spike_dn": "SPIKE_DOWN" in (tech.get("triggers") or []),
                "session": tech.get("session") or tech.get("_tf_M5", {}).get("session"),
            }
            picked = None
            dbg = {}
            sel = selector.select(sym, feat)
            if isinstance(sel, tuple):
                picked, dbg = sel
            else:
                picked = sel
            if picked:
                tech["suggested_strategy"] = picked
            if dbg:
                tech["strategy_selector_debug"] = dbg
        except Exception:
            pass

        # ---- Enhanced context: news summaries, strategy suggestion, similar cases ----
        try:
            ns = NewsService()
            # Determine category by symbol: treat BTC/ETH pairs as crypto, others as macro
            category = "crypto" if ("BTC" in sym or "ETH" in sym) else "macro"
            now_dt = datetime.utcnow()
            tech["news_events"] = ns.summarise_events(
                category=category, now=now_dt, window_min=30
            )
            tech["news_summary"] = ns.summary_for_prompt(
                category=category, now=now_dt, hours_ahead=12
            )
            tech["news_block"] = ns.is_blackout(category=category, now=now_dt)
        except Exception:
            # if NewsService fails, leave news fields as defaults
            pass

            # ===== Live quote / micro context =====
        live_bid = live_ask = None
        try:
            q = mt5svc.get_quote(sym)
            live_bid, live_ask = q.bid, q.ask
            meta = mt5.symbol_info(sym)
            tick = float(
                getattr(meta, "trade_tick_size", 0.0)
                or getattr(meta, "point", 0.0)
                or 0.0
            )
            tech["_tick"] = tick
            tech["_point"] = float(getattr(meta, "point", 0.0) or tick)
            tech["_live_spread"] = float(
                max(0.0, (live_ask or 0.0) - (live_bid or 0.0))
            )
        except Exception:
            pass

        # ===== Range state (patience) =====
        rs_all: dict = context.application.bot_data.get("range_state", {})
        rs_sym: dict = rs_all.get(sym, {})

        # ===== 1) RULE ENGINE (gate) =====
        # Use sanitized timeframe dictionaries from tech (they're already cleaned by _build_tech_from_bridge)
        gate_rec = decide_trade(
            sym, 
            tech.get("_tf_M5", {}), 
            tech.get("_tf_M15", {}), 
            tech.get("_tf_M30", {}), 
            tech.get("_tf_H1", {}), 
            m5_df=m5_df, 
            m15_df=m15_df, 
            range_state=rs_sym
        )
        if "range_state" in gate_rec:
            rs_all[sym] = gate_rec["range_state"]
            context.application.bot_data["range_state"] = rs_all
            gate_rec.pop("range_state", None)

        tech["gate_strategy"] = gate_rec.get("strategy")

        # --- Strategy plan (rule-driven entries: STOP/LIMIT/OCO + SL/TP) ---
        try:
            logger.debug(
                "calling choose_and_build: sym=%s regime=%s",
                sym,
                gate_rec.get("regime"),
            )
            print(
                f"[PRINT] calling choose_and_build sym={sym} regime={gate_rec.get('regime')}"
            )
        except Exception:
            pass

        plan = choose_and_build(
            sym, {**tech, "regime": gate_rec.get("regime")}, mode="pending"
        )

        try:
            logger.debug("choose_and_build returned: %s", "PLAN" if plan else "None")
            print(f"[PRINT] choose_and_build returned: {'PLAN' if plan else 'None'}")
        except Exception:
            pass

        if plan:
            order_side = "BUY" if str(plan.direction).upper() == "LONG" else "SELL"
            tech["strategy_plan"] = {
                "strategy": plan.strategy,
                "direction": plan.direction,
                "order_side": order_side,
                "pending_type": plan.pending_type,  # BUY_STOP/SELL_STOP/BUY_LIMIT/SELL_LIMIT/OCO_STOP
                "entry": plan.entry,
                "sl": plan.sl,
                "tp": plan.tp,
                "rr": plan.rr,
                "ttl_min": plan.ttl_min,
                "oco_companion": plan.oco_companion,
                "notes": plan.notes,
            }

        # If no concrete plan, build a PREVIEW (ignore spread/news so we can still show a candidate)
        if "strategy_plan" not in tech:
            try:
                tech_preview = dict(tech)
                tech_preview["minutes_to_next_news"] = 999
                tech_preview["_live_spread"] = 0.0
                tech_preview["spread_pts"] = 0.0
                preview = choose_and_build(
                    sym,
                    {**tech_preview, "regime": gate_rec.get("regime")},
                    mode="pending",
                )

                if preview:
                    tech["strategy_plan_preview"] = {
                        "strategy": preview.strategy,
                        "direction": preview.direction,
                        "pending_type": preview.pending_type,
                        "entry": preview.entry,
                        "sl": preview.sl,
                        "tp": preview.tp,
                        "rr": preview.rr,
                        "ttl_min": preview.ttl_min,
                        "oco_companion": preview.oco_companion,
                        "notes": preview.notes,
                        "preview": True,
                    }
            except Exception:
                pass

        # ---- Retrieve similar past cases (now we have regime/session/pattern_bias)
        try:
            ms = MemoryStore(
                getattr(settings, "MEMORY_STORE_PATH", "memory_store.sqlite")
            )
            snapshot = {
                "adx": float(tech.get("adx") or 0.0),
                "atr_14": float(tech.get("atr_14") or 0.0),
                "bb_width": float(tech.get("bb_width") or 0.0),
                "ema_slope_h1": float(tech.get("ema_slope_h1") or 0.0),
                "rsi_14": float(tech.get("rsi_14") or 0.0),
                "pattern_bias": int(tech.get("pattern_bias") or 0),
                "regime": str(gate_rec.get("regime") or tech.get("regime") or ""),
                "session": tech.get("session") or tech.get("_tf_M5", {}).get("session"),
            }
            cases = ms.retrieve(sym, snapshot, k=20)
            condensed = []
            for c in cases:
                snap = c.get("snapshot", {}) or {}
                outc = c.get("outcome", {}) or {}
                condensed.append(
                    {
                        "snapshot": {
                            "adx": snap.get("adx"),
                            "atr_14": snap.get("atr_14"),
                            "bb_width": snap.get("bb_width"),
                            "rsi_14": snap.get("rsi_14"),
                            "pattern_bias": snap.get("pattern_bias"),
                            "regime": snap.get("regime"),
                            "session": snap.get("session"),
                        },
                        "outcome": {
                            "hit": outc.get("hit"),
                            "pnl": outc.get("pnl"),
                            "duration_min": outc.get("duration_min"),
                        },
                    }
                )
            tech["similar_cases"] = condensed
        except Exception:
            pass

        tech.update(
            {
                "gate_direction": gate_rec.get("direction"),
                "gate_entry": gate_rec.get("entry"),
                "gate_sl": gate_rec.get("sl"),
                "gate_tp": gate_rec.get("tp"),
                "gate_rr": gate_rec.get("rr"),
                "regime": gate_rec.get("regime", tech.get("regime", "VOLATILE")),
                "mtf_label": gate_rec.get("mtf_label", tech.get("mtf_label")),
                "mtf_score": gate_rec.get("mtf_score", tech.get("mtf_score")),
                "pattern_m5": gate_rec.get("pattern_m5", tech.get("pattern_m5")),
                "pattern_m15": gate_rec.get("pattern_m15", tech.get("pattern_m15")),
            }
        )

        # ---- Add S/R snapshot from the rule engine so GPT can use it
        if isinstance(gate_rec.get("sr"), dict):
            tech["sr"] = gate_rec["sr"]
            nearest = gate_rec["sr"].get("nearest") or {}
            tech["sr_nearest_kind"] = nearest.get("kind")
            tech["sr_nearest_label"] = nearest.get("label")
            tech["sr_nearest_distance_frac_atr"] = nearest.get("distance_frac_atr")

        # ---- Add structural chart patterns summary for GPT
        if gate_rec.get("patterns_summary"):
            tech["patterns_summary"] = gate_rec["patterns_summary"]

        # ===== 2) LLM (Analyst+Critic majority) =====
        fundamentals = load_daily_fundamentals()
        llm_rec = oai.recommend(sym, tech, fundamentals)  # includes critic fields

        # ===== 3) Merge gate with LLM
        final = _merge_gate_llm(gate_rec, llm_rec)

        # ===== 4) Post-merge Critic (final say) + S/R anchor validation
        verdict = oai.critique(
            final,
            tech,
            rules={
                "MIN_RR_FOR_MARKET": float(getattr(settings, "MIN_RR_FOR_MARKET", 1.2)),
                "max_spread_pct_atr": float(
                    getattr(settings, "MAX_SPREAD_PCT_ATR", 0.35)
                ),
            },
        )
        final["critic_approved"] = verdict["approved"]
        final["critic_reasons"] = verdict["reasons"]

        # S/R anchor validation (enforce band anchoring even if LLM skipped it)
        ok_anchor, anchor_reasons, final_adjusted = _validate_sr_anchor(final, tech)
        if not ok_anchor:
            final = final_adjusted
            rsn = [f"sr_anchor:{r}" for r in anchor_reasons]
            final["critic_approved"] = False
            final["critic_reasons"] = list(
                set((final.get("critic_reasons") or []) + rsn)
            )

        if not final.get("critic_approved"):
            final["direction"] = "HOLD"
            guards = set(final.get("guards", []))
            guards.update(
                [f"critic:{r}" for r in (final.get("critic_reasons") or [])[:3]]
            )
            final["guards"] = sorted(guards)

        # ---- Risk simulation (estimate SL/TP hit probabilities) ----
        try:
            if str(final.get("direction")).upper() in ("BUY", "SELL"):
                atr_val = float(tech.get("atr_14") or 0.0)
                sim = simulate_risk(
                    float(final.get("entry") or 0.0),
                    float(final.get("sl") or 0.0),
                    float(final.get("tp") or 0.0),
                    atr_val,
                )
                final["risk_sim"] = sim
                # If expected return is negative or SL hit prob high, block trade
                if sim.get("expected_r", 0.0) < 0.0 or sim.get("p_hit_sl", 0.0) > 0.70:
                    final["direction"] = "HOLD"
                    gset = set(final.get("guards", []))
                    gset.add("risk_sim_negative")
                    final["guards"] = sorted(gset)
        except Exception:
            pass
        # ---- Guardrail checks ----
        try:
            ok, reason = risk_ok(final)
            if not ok:
                final["direction"] = "HOLD"
                gset = set(final.get("guards", []))
                gset.add(f"risk_guard:{reason}")
                final["guards"] = sorted(gset)
        except Exception:
            pass
        try:
            # pass minimal plan info to exposure_ok
            ok, reason = exposure_ok(
                {
                    "symbol": sym,
                    "direction": final.get("direction"),
                    "journal_repo": context.application.bot_data.get("journal_repo"),
                }
            )
            if not ok:
                final["direction"] = "HOLD"
                gset = set(final.get("guards", []))
                gset.add(f"exposure_guard:{reason}")
                final["guards"] = sorted(gset)
        except Exception:
            pass
        try:
            ok, reason = news_ok(sym)
            if not ok:
                final["direction"] = "HOLD"
                gset = set(final.get("guards", []))
                gset.add(f"news_guard:{reason}")
                final["guards"] = sorted(gset)
        except Exception:
            pass
        try:
            ok, reason = slippage_ok(sym)
            if not ok:
                final["direction"] = "HOLD"
                gset = set(final.get("guards", []))
                gset.add(f"spread_guard:{reason}")
                final["guards"] = sorted(gset)
        except Exception:
            pass

            # If we only had a PREVIEW plan, tag why it’s blocked (for display)
        try:
            if "strategy_plan" not in tech and "strategy_plan_preview" in tech:
                blocked = []
                if not final.get("critic_approved"):
                    blocked.append("critic")
                for g in final.get("guards") or []:
                    gl = str(g)
                    if gl.startswith("news_guard:"):
                        blocked.append("news")
                    elif gl.startswith("spread_guard:"):
                        blocked.append("spread")
                    elif gl.startswith("risk_guard:"):
                        blocked.append("risk")
                    elif gl.startswith("exposure_guard:"):
                        blocked.append("exposure")
                if str(final.get("direction", "")).upper() == "HOLD":
                    blocked.append("hold")
                tech["strategy_plan_preview"]["blocked_by"] = (
                    sorted(set(blocked)) or None
                )
        except Exception:
            pass

        # ===== 5) Confidence
        base_conf = build_confidence(tech)
        try:
            rr_gate = float(gate_rec.get("rr", 1.0))
            rr_final = float(final.get("rr", 0.0))
            same_side = (
                str(gate_rec.get("direction", "")).upper() in ("BUY", "SELL")
                and str(final.get("direction", "")).upper()
                == str(gate_rec.get("direction", "")).upper()
            )
            bump = 4 if same_side and rr_final >= rr_gate else 0
        except Exception:
            bump = 0
        confidence = max(1, min(99, base_conf + bump))
        # Calibrate confidence using historical performance
        try:
            calibrator = ConfidenceCalibrator(settings.CALIBRATOR_PATH)
            calibrated = calibrator.calibrate(confidence)
            if calibrated is not None:
                confidence = int(min(99, max(1, calibrated)))
        except Exception:
            pass
        dir_norm = normalise_direction(final.get("direction"))
        can_execute = (dir_norm in ("buy", "sell")) and bool(
            final.get("critic_approved")
        )
        always = bool(getattr(settings, "ALWAYS_SHOW_EXEC", False))

        mk_closed = _market_looks_closed(sym)
        # ---- MemoryStore: save this recommendation snapshot for future retrieval
        try:
            ms = MemoryStore(
                getattr(settings, "MEMORY_STORE_PATH", "memory_store.sqlite")
            )
            snapshot = {
                "adx": float(tech.get("adx") or 0.0),
                "atr_14": float(tech.get("atr_14") or 0.0),
                "bb_width": float(tech.get("bb_width") or 0.0),
                "ema_slope_h1": float(tech.get("ema_slope_h1") or 0.0),
                "rsi_14": float(tech.get("rsi_14") or 0.0),
                "pattern_bias": int(tech.get("pattern_bias") or 0),
                "regime": str(final.get("regime") or tech.get("regime") or ""),
                "session": tech.get("session") or tech.get("_tf_M5", {}).get("session"),
            }
            ms.add_reco(symbol=sym, snapshot=snapshot, plan=final, tf="M5", ticket=None)
        except Exception:
            pass

        # ===== 6) Risk mapping (saved into payload)
        atr_val = float(tech.get("atr_14") or 0.0)
        spread = float(tech.get("_live_spread") or 0.0)
        spread_pct_atr = (spread / atr_val) if atr_val > 0 else 0.0
        base_pct = float(getattr(settings, "RISK_DEFAULT_PCT", 1.0))
        minutes_to_news = None  # wire your news service when ready
        risk_pct_mapped = map_risk_pct(
            base_pct=base_pct,
            confidence=confidence,
            adx=float(tech.get("adx") or 0.0),
            spread_pct_atr=spread_pct_atr,
            minutes_to_news=minutes_to_news,
            min_pct=float(getattr(settings, "RISK_MIN_PCT", 0.2)),
            max_pct=float(getattr(settings, "RISK_MAX_PCT", 2.0)),
        )
        try:
            jr = context.application.bot_data.get("journal_repo")
            from infra.exposure_guard import ExposureGuard

            eg = ExposureGuard(journal_repo=jr)
            side_for_eg = (normalise_direction(final.get("direction")) or "").upper()
            if side_for_eg in ("BUY", "SELL"):
                eg_res = eg.evaluate(
                    symbol=sym,
                    side=side_for_eg,
                    desired_risk_pct=risk_pct_mapped,
                    journal_repo=jr,
                )
                if eg_res.allow:
                    risk_pct_mapped = float(eg_res.adjusted_risk_pct)
                else:
                    # also reflect a hard block if you want:
                    final["direction"] = "HOLD"
                    guards = set(final.get("guards") or [])
                    guards.add(f"exposure_guard:{eg_res.reason}")
                    final["guards"] = sorted(guards)
        except Exception:
            pass
        text = fmt_trade_message(
            sym, final, tech, confidence, live_bid, live_ask, mk_closed
        )

        LAST_REC[(chat_id, sym)] = {
            "rec": final,
            "symbol": sym,
            "confidence": confidence,
            "regime": final.get("regime") or tech.get("regime"),
            "rr": final.get("rr"),
            "notes": final.get("reasoning", ""),
            "strategy": gate_rec.get("strategy"),
            "risk_pct_mapped": risk_pct_mapped,
            # <-- add this:
            "rec_tech": {
                "adx": float(tech.get("adx") or 0.0),
                "atr_14": float(tech.get("atr_14") or 0.0),
                "bb_width": float(tech.get("bb_width") or 0.0),
                "ema_slope_h1": float(tech.get("ema_slope_h1") or 0.0),
                "rsi_14": float(tech.get("rsi_14") or 0.0),
                "pattern_bias": int(tech.get("pattern_bias") or 0),
                "session": tech.get("session") or tech.get("_tf_M5", {}).get("session"),
            },
        }

        # ===== 7) Buttons (single final message)
        rows: list[list[InlineKeyboardButton]] = []
        cb_refresh = f"mkt|refresh|{sym}"

        entry_guess = final.get("entry")
        sl_guess = final.get("sl")
        tp_guess = final.get("tp")
        side_guess = None
        if dir_norm not in ("buy", "sell"):
            side_guess = _infer_side_from_levels(entry_guess, sl_guess, tp_guess)

        # priority: explicit direction → inferred from levels → default BUY (for testing)
        side = dir_norm if dir_norm in ("buy", "sell") else (side_guess or "buy")
        payload = {
            "symbol": sym,
            "side": side,
            "sl": sl_guess,
            "tp": tp_guess,
            "entry": entry_guess,  # for validation vs. entry
            "risk_pct": risk_pct_mapped,  # mapped risk passes through to exec
            "was_hold": dir_norm not in ("buy", "sell"),
            "side_inferred": bool(side_guess),
        }
        token = _stash_cb(
            context.application,
            chat_id,
            {
                "symbol": sym,
                "side": side,
                "sl": sl_guess,
                "tp": tp_guess,
                "entry": entry_guess,
                "risk_pct": risk_pct_mapped,
            },
            ttl_sec=900,
        )

        rows: list[list[InlineKeyboardButton]] = []
        cb_refresh = f"mkt|refresh|{sym}"

        if can_execute or always:
            # prefer explicit side; if always=True while HOLD, keep side from levels as a *fallback* label only
            side = (
                dir_norm
                if dir_norm in ("buy", "sell")
                else (
                    _infer_side_from_levels(
                        final.get("entry"), final.get("sl"), final.get("tp")
                    )
                    or "buy"
                )
            )
            btn_label_side = side.upper()
            
            # IMPROVED: Get order type recommendation for button labels
            try:
                order_analysis = _determine_optimal_order_type(sym, final, tech, live_bid, live_ask)
                recommended_order_type = order_analysis.get("order_type", "MARKET")
                order_confidence = order_analysis.get("confidence", 50)
                
                # Add order type emoji to button
                order_emoji = {
                    "MARKET": "⚡",
                    "PENDING": "⏳", 
                    "OCO": "🎯"
                }.get(recommended_order_type, "⚡")
                
                # Enhanced button label with order type recommendation
                if recommended_order_type == "MARKET":
                    btn_text = f"{order_emoji} Execute {btn_label_side} (Market)"
                elif recommended_order_type == "PENDING":
                    btn_text = f"{order_emoji} Execute {btn_label_side} (Pending)"
                else:  # OCO
                    btn_text = f"{order_emoji} Execute {btn_label_side} (OCO)"
                    
                btn_text += f" ({risk_pct_mapped:.2f}% risk)"
                
            except Exception:
                btn_text = f"✅ Execute {btn_label_side} ({risk_pct_mapped:.2f}% risk)"
            
            token = _stash_cb(
                context.application,
                chat_id,
                {
                    "symbol": sym,
                    "side": side,
                    "sl": sl_guess,
                    "tp": tp_guess,
                    "entry": entry_guess,
                    "risk_pct": risk_pct_mapped,
                },
                ttl_sec=900,
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        btn_text,
                        callback_data=f"exec2|{token}",
                    ),
                    InlineKeyboardButton("↻ Refresh price", callback_data=cb_refresh),
                    InlineKeyboardButton("🧊 Ignore", callback_data="ignore"),
                ]
            )
            
            # IMPROVED: Add order type selection buttons
            try:
                order_analysis = _determine_optimal_order_type(sym, final, tech, live_bid, live_ask)
                recommended_order_type = order_analysis.get("order_type", "MARKET")
                
                # Always show all available order type buttons
                order_type_buttons = []
                
                # Market order button
                market_label = "⚡ Market" if recommended_order_type == "MARKET" else "⚡ Market Order"
                order_type_buttons.append(
                    InlineKeyboardButton(
                        market_label,
                        callback_data=f"exec2|{token}|market"
                    )
                )
                
                # Pending order button
                pending_label = "⏳ Pending" if recommended_order_type == "PENDING" else "⏳ Pending Order"
                order_type_buttons.append(
                    InlineKeyboardButton(
                        pending_label,
                        callback_data=f"exec2|{token}|pending"
                    )
                )
                
                # OCO button (only if trade has OCO data)
                has_oco_data = final.get("oco_bracket") or final.get("oco_companion")
                if has_oco_data:
                    oco_label = "🎯 OCO" if recommended_order_type == "OCO" else "🎯 OCO Order"
                    order_type_buttons.append(
                        InlineKeyboardButton(
                            oco_label,
                            callback_data=f"exec2|{token}|oco"
                        )
                    )
                
                # Add order type buttons row
                if order_type_buttons:
                    rows.append(order_type_buttons)
                    
            except Exception:
                pass  # Skip order type buttons if there's an error
        else:
            rows.append(
                [
                    InlineKeyboardButton("↻ Refresh price", callback_data=cb_refresh),
                    InlineKeyboardButton("🧊 Ignore", callback_data="ignore"),
                ]
            )
        # Send a single message (MDV2, matches fmt_trade_message)
        try:
            await reply.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(rows),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception:
            await reply.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))

        # === ANCHOR: POSWATCH_SAVE_CHAT_TRADE_START ===
        try:
            context.application.bot_data["poswatch_last_chat_id"] = (
                update.effective_chat.id
            )
        except Exception:
            pass
        # === ANCHOR: POSWATCH_SAVE_CHAT_TRADE_END ===

        # === ANCHOR: POSWATCH_SAVE_CHAT_TRADE_START ===
        try:
            context.application.bot_data["poswatch_last_chat_id"] = (
                update.effective_chat.id
            )
        except Exception:
            pass
        # === ANCHOR: POSWATCH_SAVE_CHAT_TRADE_END ===

        # Show the main menu straight after analysis (lazy import to avoid circulars)
        try:
            from handlers.menu import main_menu_markup

            await reply.reply_text("What next?", reply_markup=main_menu_markup())
        except Exception:
            pass

        # ---- Journal this recommendation & maybe start auto-watch ----
        try:
            # Record trade plan into journal (non-execution stage)
            journal_repo: JournalRepo = context.application.bot_data.get("journal_repo")
            if journal_repo:
                try:
                    # IMPROVED: Compose extra payload with diagnostic info + router metadata
                    extra_payload = {
                        "confidence": confidence,
                        "regime": final.get("regime") or tech.get("regime"),
                        "rr": final.get("rr"),
                        "strategy": gate_rec.get("strategy"),
                        "critic_reasons": final.get("critic_reasons"),
                        "guards": final.get("guards"),
                        "triggers": final.get("triggers"),
                        # Router metadata for analytics
                        "router_used": final.get("router_used", False),
                        "template_version": final.get("template_version", ""),
                        "session_tag": final.get("session_tag", ""),
                        "decision_tags": final.get("decision_tags", []),
                        "validation_score": final.get("validation_score", 0.0),
                    }
                    journal_repo.add_event(
                        "trade_plan",
                        symbol=sym,
                        side=final.get("direction"),
                        price=final.get("entry"),
                        sl=final.get("sl"),
                        tp=final.get("tp"),
                        reason=final.get("reasoning"),
                        extra=extra_payload,
                    )
                except Exception:
                    pass

            # Auto-watch: if direction is HOLD due to transient conditions, schedule a monitor
            try:
                final_dir = str(final.get("direction", "")).upper()
                # Only consider hold signals
                if final_dir == "HOLD":
                    # Derive reasons that justify watching (critic reasons & guards)
                    watch_reasons = set()
                    # critic reasons
                    for r in final.get("critic_reasons") or []:
                        if (
                            r.startswith("direction=HOLD")
                            or r.startswith("rr_below_floor")
                            or r.startswith("ema_alignment_false")
                            or r.startswith("adx_weak")
                        ):
                            watch_reasons.add(r)
                    # guard reasons
                    for g in final.get("guards") or []:
                        if g.startswith("critic:"):
                            # e.g. critic:ema_alignment_false
                            _, crit = g.split(":", 1)
                            if (
                                crit.startswith("direction=HOLD")
                                or crit.startswith("rr_below_floor")
                                or crit.startswith("ema_alignment_false")
                                or crit.startswith("adx_weak")
                            ):
                                watch_reasons.add(crit)
                    # Do not start watch if news guard present
                    has_news_guard = any(
                        (g or "").startswith("news_guard")
                        for g in (final.get("guards") or [])
                    )
                    if watch_reasons and not has_news_guard:
                        # start auto-watch job
                        start_auto_watch(context, chat_id, sym, list(watch_reasons))
            except Exception:
                pass
        except Exception:
            pass

    except Exception as e:
        logger.exception("Trade analysis error")
        await reply.reply_text(f"⚠️ Could not analyse {sym}: {e}")


# ---------- EXECUTE (callback) ----------
async def exec_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not query or not query.data:
        return

    data = query.data

    # Try to wire poswatch (first time we execute)
    _wire_poswatch_close_handler(context, update.effective_chat.id)

    # ---------- one-tap guard (per-message lock) ----------
    lock_key = ("exec_lock", update.effective_chat.id, query.message.message_id)
    if data.startswith("exec2|"):
        if context.application.bot_data.get(lock_key):
            try:
                await query.answer("Already handled ✅", cache_time=1)
            except Exception:
                pass
            return
        context.application.bot_data[lock_key] = True
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
    # ------------------------------------------------------

    if data == "ignore":
        await query.message.reply_text("Noted — signal ignored.")
        return

    if data.startswith("retry|"):
        _, sym = data.split("|", 1)
        await query.message.reply_text("🔁 Re-running analysis…")
        await trade_command(update, context, symbol=sym)
        return

    if data.startswith("mkt|refresh|"):
        _, _, sym = data.split("|", 2)
        try:
            mt5svc = MT5Service()
            mt5svc.connect()
            mt5svc.ensure_symbol(sym)
            q = mt5svc.get_quote(sym)
            await query.message.reply_text(
                f"↻ Price refreshed for {sym}: Bid={fmt_price(sym, q.bid)} | "
                f"Ask={fmt_price(sym, q.ask)} ({datetime.now().strftime('%H:%M:%S')})"
            )
        except Exception as e:
            await query.message.reply_text(f"⚠️ Could not refresh price: {e}")
        return

    if data.startswith("exec2|"):
        # Parse: exec2|{token} or exec2|{token}|{order_type}
        parts = data.split("|")
        token = parts[1] if len(parts) > 1 else ""
        order_type_override = parts[2] if len(parts) > 2 else None  # "market", "pending", "oco"
        
        payload = _pop_cb(context.application, token, update.effective_chat.id)
        if not payload:
            await query.message.reply_text(
                "⚠️ This signal has expired. Please run /trade again."
            )
            return

        sym = payload["symbol"]
        side = payload["side"]
        sl = payload.get("sl")
        tp = payload.get("tp")
        entry_hint = payload.get("entry")
        risk_pct = float(
            payload.get("risk_pct", getattr(settings, "RISK_DEFAULT_PCT", 1.0))
        )

        # Require both SL and TP (and entry hint) to avoid naked orders during HOLD testing
        if sl is None or tp is None or entry_hint is None:
            await query.message.reply_text(
                "⚠️ SL/TP (or entry hint) missing or invalid; not sending a naked order. Please /trade again."
            )
            return

        # 1) Validate levels vs chosen side using suggested entry
        if not _levels_match_side_by_entry(side, entry_hint, sl, tp):
            other = "sell" if side == "buy" else "buy"
            if _levels_match_side_by_entry(other, entry_hint, sl, tp):
                side_prev = side
                side = other
                try:
                    await query.message.reply_text(
                        f"↔️ Auto-flipped to {side.upper()} — SL/TP structure fits {side.upper()} relative to suggested entry."
                    )
                except Exception:
                    pass
            else:
                await query.message.reply_text(
                    "⚠️ SL/TP don’t fit either BUY or SELL relative to the suggested entry; not sending. Please /trade again."
                )
                return

        # ===== Circuit breaker guard (manual send path) =====
        try:
            circuit = context.application.bot_data.get("circuit")
            journal_repo: JournalRepo = context.application.bot_data.get("journal_repo")
            if circuit:
                allow, why = circuit.allow_order(journal_repo=journal_repo)
                if not allow:
                    await query.message.reply_text(
                        f"🧯 Circuit breaker is active — {why}. Use /resume to override."
                    )
                    return
        except Exception:
            logger.debug(
                "Circuit check failed in manual path; proceeding.", exc_info=True
            )

        try:
            mt5svc = MT5Service()
            mt5svc.connect()
            mt5svc.ensure_symbol(sym)

            # Risk sizing from live price to SL
            q = mt5svc.get_quote(sym)
            bid, ask = q.bid, q.ask
            px = ask if side == "buy" else bid

            # FIXED: Check if entry is close enough to current price for MARKET execution
            # Allow small tolerance (within spread + 0.1% slippage) to execute immediately
            entry_close_enough = False
            if entry_hint is not None:
                entry_f = float(entry_hint)
                spread = abs(ask - bid)
                tolerance = spread + (px * 0.001)  # spread + 0.1%
                if abs(entry_f - px) <= tolerance:
                    entry_close_enough = True
            
            # Force pending order if user explicitly clicked "Pending" button
            force_pending = (order_type_override == "pending")
            force_market = (order_type_override == "market")
            
            # If levels don't fit the live price, consider a pending order at the suggested entry
            # OR if user explicitly requested a pending order
            if (not _levels_match_side_by_price(side, px, sl, tp) and not entry_close_enough) or force_pending:
                # If the levels *do* fit relative to the intended entry, place a pending instead
                # When user forces pending, skip the entry hint check
                if entry_hint is not None and (force_pending or _levels_match_side_by_entry(
                    side, entry_hint, sl, tp
                )):
                    ptype = infer_pending_type(
                        direction=side.upper(),
                        entry=float(entry_hint),
                        bid=bid,
                        ask=ask,
                    )
                    if ptype:
                        # Risk-size from entry -> SL (not live price)
                        if sl is None:
                            lot = float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))
                        else:
                            lot = mt5svc.risk_to_lot(
                                sym, float(entry_hint), float(sl), risk_pct
                            )
                        lot = mt5svc.normalise_lot(sym, lot)
                        lot = _apply_staged_multiplier(lot)

                        # Send as pending (comment conveys intent; see MT5Service note below)
                        res = mt5svc.open_order(
                            sym,
                            side,
                            entry=float(entry_hint),
                            sl=sl,
                            tp=tp,
                            lot=lot,
                            risk_pct=None,
                            comment=ptype.lower(),  # e.g. "sell_stop", "sell_limit", "buy_stop", "buy_limit"
                        )

                        if not res.get("ok"):
                            await query.message.reply_text(
                                f"❌ Pending order failed: {res.get('message')}"
                            )
                            return

                        text = _render_execution_message(
                            sym, side + f" ({ptype})", risk_pct, res
                        )
                        await query.message.reply_text(text)

                        # (keep the rest of your post-send flow: journal, menu, poswatch registration)
                        try:
                            from handlers.menu import main_menu_markup

                            await query.message.reply_text(
                                "What next?", reply_markup=main_menu_markup()
                            )
                        except Exception:
                            pass

                        # register ticket(s) for watcher (unchanged block)
                        try:
                            poswatch = context.application.bot_data.get("poswatch")
                            if poswatch:
                                state = LAST_REC.get(
                                    (update.effective_chat.id, sym), {}
                                )
                                meta = {
                                    "regime": state.get("regime"),
                                    "strategy": state.get("strategy"),
                                }
                                parts = (
                                    res.get("parts", [])
                                    if isinstance(res, dict)
                                    else []
                                )
                                if parts:
                                    for p in parts:
                                        tk = p.get("details", {}).get("ticket")
                                        if tk:
                                            poswatch.register_ticket_chat(
                                                int(tk),
                                                update.effective_chat.id,
                                                meta=meta,
                                            )
                                else:
                                    tk = res.get("details", {}).get("ticket")
                                    if tk:
                                        poswatch.register_ticket_chat(
                                            int(tk), update.effective_chat.id, meta=meta
                                        )
                        except Exception:
                            pass
                        return

                # Fallback: still wrong-side and cannot pend
                # Unless user explicitly forced market execution
                if not force_market:
                    await query.message.reply_text(
                        "⚠️ At the current price your SL/TP are on the wrong side. I can place a pending order at the suggested entry instead — re-run /trade or try again."
                    )
                    return

            if sl is None:
                lot = float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))
            else:
                lot = mt5svc.risk_to_lot(sym, px, float(sl), risk_pct)
            lot = mt5svc.normalise_lot(sym, lot)
            lot = _apply_staged_multiplier(lot)

            res = mt5svc.open_order(
                sym,
                side,
                entry=px,
                sl=sl,
                tp=tp,
                lot=lot,
                risk_pct=None,
                comment="market",
            )
            details = res.get("details", {}) if isinstance(res, dict) else {}

            # Derive actual lot from response (handles split fills)
            parts = res.get("parts", []) if isinstance(res, dict) else []
            if parts:
                actual_lot = sum(
                    float(p.get("details", {}).get("volume") or 0.0) for p in parts
                )
            else:
                actual_lot = float(details.get("volume") or lot)

            # Journal (use executed price + final SL/TP if available)
            try:
                journal_repo: JournalRepo = context.application.bot_data["journal_repo"]
                state = LAST_REC.get((update.effective_chat.id, sym), {})
                bal, eq = mt5svc.account_bal_eq()
                exec_px = details.get("price_executed", px)
                sl_final = details.get("final_sl", details.get("sl"))
                tp_final = details.get("final_tp", details.get("tp"))
                row = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "symbol": sym,
                    "side": side,
                    "entry": exec_px,
                    "sl": sl_final,
                    "tp": tp_final,
                    "lot": actual_lot,
                    "ticket": details.get("ticket"),
                    "position": details.get("final_position")
                    or details.get("position"),
                    "balance": bal,
                    "equity": eq,
                    "confidence": state.get("confidence"),
                    "regime": state.get("regime"),
                    "rr": state.get("rr"),
                    "notes": (state.get("notes", "") or "") + f" | risk={risk_pct}%",
                }
                try:
                    journal_repo.write_exec(row)
                except Exception:
                    pass
            except Exception:
                pass

            if not res.get("ok"):
                await query.message.reply_text(f"❌ Order failed: {res.get('message')}")
                return

            # Auto-register to DTMS (one-liner wrapper)
            try:
                details = res.get("details", {})
                ticket = details.get("ticket")
                if ticket:
                    from dtms_integration import auto_register_dtms
                    res_copy = dict(res)
                    res_copy['symbol'] = sym
                    res_copy['direction'] = side
                    auto_register_dtms(ticket, res_copy)
            except Exception:
                pass  # Silent failure

            # Build and send the clean execution message (symbol-precision, executed price)
            text = _render_execution_message(sym, side, risk_pct, res)
            await query.message.reply_text(text)
            # Persist executed plan to MemoryStore (ties to ticket)
            try:
                ms = MemoryStore(
                    getattr(settings, "MEMORY_STORE_PATH", "memory_store.sqlite")
                )
                st = LAST_REC.get((update.effective_chat.id, sym), {}) or {}
                rec_state = st.get("rec", {}) or {}
                rec_tech = st.get("rec_tech", {}) or {}
                details = res.get("details", {}) if isinstance(res, dict) else {}

                snapshot = {
                    "adx": float(rec_tech.get("adx") or 0.0),
                    "atr_14": float(rec_tech.get("atr_14") or 0.0),
                    "bb_width": float(rec_tech.get("bb_width") or 0.0),
                    "ema_slope_h1": float(rec_tech.get("ema_slope_h1") or 0.0),
                    "rsi_14": float(rec_tech.get("rsi_14") or 0.0),
                    "pattern_bias": int(rec_tech.get("pattern_bias") or 0),
                    "regime": str(st.get("regime") or rec_state.get("regime") or ""),
                    "session": rec_tech.get("session"),
                }

                ms.add_reco(
                    symbol=sym,
                    snapshot=snapshot,
                    plan=rec_state
                    or {
                        "direction": side.upper(),
                        "entry": details.get("price_executed"),
                        "sl": details.get("final_sl", details.get("sl")),
                        "tp": details.get("final_tp", details.get("tp")),
                    },
                    tf="M5",
                    ticket=str(details.get("ticket")),
                )

            except Exception:
                pass

            # Show main menu (lazy import to avoid circulars)
            try:
                from handlers.menu import main_menu_markup

                await query.message.reply_text(
                    "What next?", reply_markup=main_menu_markup()
                )
            except Exception:
                pass

            # Register ticket(s) for position watcher notifications w/ meta
            try:
                poswatch = context.application.bot_data.get("poswatch")
                if poswatch:
                    state = LAST_REC.get((update.effective_chat.id, sym), {})
                    meta = {
                        "regime": state.get("regime"),
                        "strategy": state.get("strategy"),
                    }
                    if parts:
                        for p in parts:
                            tk = p.get("details", {}).get("ticket")
                            if tk:
                                poswatch.register_ticket_chat(
                                    int(tk), update.effective_chat.id, meta=meta
                                )
                    else:
                        tk = details.get("ticket")
                        if tk:
                            poswatch.register_ticket_chat(
                                int(tk), update.effective_chat.id, meta=meta
                            )
            except Exception:
                pass

        except Exception as e:
            logger.exception("Execution error")
            await query.message.reply_text(f"❌ Execution error: {e}")
