# =====================================
# infra/pseudo_pendings.py
# =====================================
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

import MetaTrader5 as mt5

from config import settings
from infra.mt5_service import MT5Service
from infra.exposure_guard import ExposureGuard
from infra.circuit_breaker import CircuitBreaker  # type: ignore[unused-import]
from infra.journal_repo import JournalRepo  # drawdown-aware risk scaling via guard

logger = logging.getLogger(__name__)

guard = ExposureGuard()


@dataclass
class PendingTask:
    id: str
    chat_id: int
    symbol: str
    side: str  # 'buy' or 'sell'
    pending_type: str  # BUY_STOP, BUY_LIMIT, SELL_STOP, SELL_LIMIT
    entry: float
    sl: Optional[float]
    tp: Optional[float]
    lot: float
    expires_ts: Optional[int]  # unix seconds; None = never
    created_ts: int
    status: str = "armed"  # armed | filled | cancelled | expired
    filled_price: Optional[float] = None
    filled_ticket: Optional[int] = None
    note: str = ""
    oco_group: Optional[str] = None  # one-cancels-the-other group id
    regime: Optional[str] = None  # e.g., "TREND", "RANGE" — from plan
    sl_used: Optional[float] = None  # the SL actually sent on fill (after any widening)

    def to_dict(self) -> dict:
        return asdict(self)


class PseudoPendingManager:
    def __init__(self, store_path: str):
        self.path = Path(store_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._tasks: Dict[str, PendingTask] = {}
        self.load()

    # ----- persistence -----
    def load(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._tasks = {}
                try:
                    self.path.write_text("{}", "utf-8")
                except Exception:
                    pass
                return
            try:
                raw_text = self.path.read_text("utf-8")
                if not raw_text.strip():
                    logger.warning("Pendings store is empty; initialising fresh JSON.")
                    self._tasks = {}
                    self.path.write_text("{}", "utf-8")
                    return
                raw = json.loads(raw_text)
                if not isinstance(raw, dict):
                    raise ValueError("pendings.json root is not an object")
                self._tasks = {tid: PendingTask(**t) for tid, t in raw.items()}
            except Exception as e:
                logger.warning("Could not load pendings: %s", e)
                try:
                    bak = self.path.with_suffix(
                        self.path.suffix + f".bak.{int(time.time())}"
                    )
                    self.path.rename(bak)
                    logger.warning("Backed up bad pendings file to %s", bak)
                except Exception:
                    logger.debug("Backup of bad pendings file failed.", exc_info=True)
                self._tasks = {}
                try:
                    self.path.write_text("{}", "utf-8")
                except Exception:
                    pass

    def save(self) -> None:
        with self._lock:
            data = {tid: t.to_dict() for tid, t in self._tasks.items()}
            self.path.write_text(json.dumps(data, indent=2), "utf-8")

    # ----- CRUD -----
    def add(
        self,
        chat_id: int,
        symbol: str,
        side: str,
        pending_type: str,
        entry: float,
        sl: Optional[float],
        tp: Optional[float],
        lot: float,
        expires_ts: Optional[int],
        note: str = "",
        oco_group: Optional[str] = None,
        regime: Optional[str] = None,
    ) -> PendingTask:
        with self._lock:
            tid = uuid.uuid4().hex[:10]
            t = PendingTask(
                id=tid,
                chat_id=chat_id,
                symbol=symbol,
                side=side.lower(),
                pending_type=pending_type.upper(),
                entry=float(entry),
                sl=(None if sl is None else float(sl)),
                tp=(None if tp is None else float(tp)),
                lot=float(lot),
                expires_ts=expires_ts,
                created_ts=int(time.time()),
                note=note,
                oco_group=oco_group,
                regime=(regime.upper() if isinstance(regime, str) else regime),
            )

            self._tasks[tid] = t
            self.save()
            return t

    def cancel(self, task_id: str, chat_id: Optional[int] = None) -> bool:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return False
            if chat_id and t.chat_id != chat_id:
                return False
            if t.status not in ("armed",):
                return False
            t.status = "cancelled"
            self.save()
            return True

    def cancel_group(
        self, oco_group: str, exclude_task_id: Optional[str] = None
    ) -> int:
        n = 0
        with self._lock:
            for t in self._tasks.values():
                if (
                    t.status == "armed"
                    and t.oco_group
                    and t.oco_group == oco_group
                    and t.id != (exclude_task_id or "")
                ):
                    t.status = "cancelled"
                    n += 1
            if n:
                self.save()
        return n

    def list_for_chat(self, chat_id: int) -> List[PendingTask]:
        with self._lock:
            return [
                t
                for t in self._tasks.values()
                if t.chat_id == chat_id and t.status in ("armed",)
            ]

    # ----- Helpers: M1 closes & volatility spike detection -----
    @staticmethod
    def _last_closed_m1(symbol: str, need: int) -> List[dict]:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(minutes=max(10, need + 4))
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start_dt, end_dt)
        if rates is None or len(rates) == 0:
            return []
        now_s = time.time()
        closed = [r for r in rates if (r["time"] + 60) <= now_s]
        return closed[-need:]

    @staticmethod
    def _true_range(bar: dict, prev_close: float) -> float:
        return max(
            bar["high"] - bar["low"],
            abs(bar["high"] - prev_close),
            abs(bar["low"] - prev_close),
        )

    def _vol_spike_ratio(self, symbol: str) -> Optional[float]:
        bars = self._last_closed_m1(symbol, 21)
        if len(bars) < 3:
            return None
        trs = []
        prev_close = float(bars[0]["close"])
        for b in bars[1:]:
            tr = self._true_range(b, prev_close)
            trs.append(tr)
            prev_close = float(b["close"])
        if len(trs) < 2:
            return None
        last_tr = trs[-1]
        hist = trs[:-1]
        hist_sorted = sorted(hist)
        mid = len(hist_sorted) // 2
        median = (
            0.5 * (hist_sorted[mid - 1] + hist_sorted[mid])
            if len(hist_sorted) % 2 == 0
            else hist_sorted[mid]
        )
        if median <= 0:
            return None
        return float(last_tr / median)

    def _cooloff_passed(self, t: PendingTask) -> bool:
        base_n = int(getattr(settings, "PENDING_COOLDOWN_M1_CLOSES", 0))
        if base_n <= 0 or not t.pending_type.endswith("STOP"):
            return True

        extra = 0
        try:
            ratio = self._vol_spike_ratio(t.symbol)
            thr = float(getattr(settings, "PENDING_SPIKE_TR_MULT", 1.8))
            if ratio is not None and ratio >= thr:
                extra = int(getattr(settings, "PENDING_SPIKE_EXTRA_CLOSES", 1))
                logger.debug(
                    "Volatility spike detected (ratio=%.2f >= %.2f): requiring +%d closes",
                    ratio,
                    thr,
                    extra,
                )
        except Exception:
            pass

        need = base_n + extra
        bars = self._last_closed_m1(t.symbol, need)
        if len(bars) < need:
            return False

        buf_pct = float(getattr(settings, "PENDING_COOLDOWN_BUFFER_PCT", 0.0))
        if t.pending_type == "BUY_STOP":
            threshold = t.entry * (1.0 + buf_pct)
            return all(float(b["close"]) >= threshold for b in bars)
        if t.pending_type == "SELL_STOP":
            threshold = t.entry * (1.0 - buf_pct)
            return all(float(b["close"]) <= threshold for b in bars)
        return True

    # ----- quick M5 ATR for spread filter -----
    @staticmethod
    def _m5_atr(symbol: str, period: int = 14) -> Optional[float]:
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, period + 2)
            if rates is None or len(rates) < period + 1:
                return None
            trs: List[float] = []
            prev_close = float(rates[0]["close"])
            for r in rates[1:]:
                high = float(r["high"])
                low = float(r["low"])
                close = float(r["close"])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                trs.append(tr)
                prev_close = close
            if len(trs) < period:
                return None
            return float(sum(trs[-period:]) / period)
        except Exception:
            return None

    # ----- core: poll once -----
    def poll_once(
        self,
        mt5svc: MT5Service,
        notifier,
        journal_repo=None,
        poswatch=None,
        circuit: Optional[CircuitBreaker] = None,
    ) -> None:
        """
        Check all armed tasks; if trigger condition met (+ cool-off), send market order and notify.
        Also handles expiry and OCO cancellation.
        Journals both fills and exposure decisions.
        Registers filled tickets with PositionWatcher (meta: regime + strategy).
        """
        now = int(time.time())
        fired: List[PendingTask] = []
        expired: List[PendingTask] = []

        with self._lock:
            items = list(self._tasks.values())

        for t in items:
            if t.status != "armed":
                continue
            if t.expires_ts and now >= t.expires_ts:
                t.status = "expired"
                expired.append(t)
                continue

            try:
                mt5svc.ensure_symbol(t.symbol)
                q = mt5svc.get_quote(t.symbol)
                bid, ask = q.bid, q.ask
            except Exception as e:
                logger.debug("Quote error for %s: %s", t.symbol, e)
                continue

            pt = t.pending_type
            trig = (
                (pt == "BUY_STOP" and ask >= t.entry)
                or (pt == "BUY_LIMIT" and ask <= t.entry)
                or (pt == "SELL_STOP" and bid <= t.entry)
                or (pt == "SELL_LIMIT" and bid >= t.entry)
            )
            if not trig:
                continue

            if not self._cooloff_passed(t):
                logger.debug("Cool-off not met for %s %s @ %s", t.symbol, pt, t.entry)
                continue

            # Spread gate
            try:
                info = mt5svc.symbol_meta(t.symbol)
                point = float(info["point"])
                spread = abs(ask - bid)
                atr_m5 = self._m5_atr(t.symbol) or 0.0
                max_pct = float(getattr(settings, "SPREAD_MAX_ATR_PCT", 0.25))
                max_pts = float(getattr(settings, "SPREAD_MAX_POINTS", 0.0))
                spread_pts = spread / max(point, 1e-9)
                too_wide = (atr_m5 > 0 and spread >= atr_m5 * max_pct) or (
                    max_pts > 0 and spread_pts >= max_pts
                )
                if too_wide:
                    logger.debug(
                        "Spread gate: %s blocked (spread=%.1f pts).",
                        t.symbol,
                        spread_pts,
                    )
                    continue
            except Exception:
                pass

            # Optional SL widening on spike
            sl_send = t.sl
            try:
                ratio = self._vol_spike_ratio(t.symbol)
                thr = float(getattr(settings, "PENDING_SPIKE_TR_MULT", 1.8))
                widen = float(getattr(settings, "PENDING_SPIKE_WIDEN_SL_FACTOR", 1.10))
                if (
                    sl_send is not None
                    and ratio is not None
                    and ratio >= thr
                    and widen > 1.0
                ):
                    if t.side == "buy":
                        dist = abs(t.entry - sl_send)
                        sl_send = t.entry - (dist * widen)
                    else:
                        dist = abs(sl_send - t.entry)
                        sl_send = t.entry + (dist * widen)
                    logger.debug(
                        "Widened SL due to spike: factor=%.2f new_sl=%s", widen, sl_send
                    )
            except Exception:
                pass

            # ===== Circuit breaker (daily risk guard) =====
            if circuit:
                try:
                    allow, why = circuit.allow_order(journal_repo=journal_repo)
                except Exception:
                    allow, why = True, "cb-check-failed"
                    logger.debug(
                        "Circuit allow_order failed — allowing trade.", exc_info=True
                    )
                if not allow:
                    t.status = "cancelled"
                    t.note = f"circuit_block: {why}"
                    self._notify(
                        notifier,
                        t.chat_id,
                        f"🧯 Circuit breaker blocked {t.symbol} {t.side.upper()} ({t.pending_type}) — {why}.",
                    )
                    try:
                        if journal_repo and hasattr(journal_repo, "add_event"):
                            journal_repo.add_event(
                                "circuit_block",
                                symbol=t.symbol,
                                side=t.side.upper(),
                                reason=why,
                                extra={"pending_id": t.id},
                            )
                    except Exception:
                        pass
                    fired.append(t)
                    continue

            # ===== Exposure guard (correlation & currency caps + DD scaling) =====
            gr = None
            try:
                desired_risk_pct = float(getattr(settings, "RISK_DEFAULT_PCT", 1.0))
                gr = guard.evaluate(
                    symbol=t.symbol,
                    side=t.side.upper(),
                    desired_risk_pct=desired_risk_pct,
                    journal_repo=journal_repo,  # << pass repo so guard applies DD scaling
                )

                # Journal the check
                try:
                    if journal_repo and hasattr(journal_repo, "add_event"):
                        journal_repo.add_event(
                            "exposure_check",
                            symbol=t.symbol,
                            side=t.side.upper(),
                            reason=gr.reason,
                            extra={
                                "correlated_with": gr.correlated_with,
                                "desired_risk_pct": desired_risk_pct,
                                "adjusted": gr.adjusted_risk_pct,
                            },
                        )
                except Exception:
                    logger.debug("Journal exposure_check failed", exc_info=True)

                if not gr.allow:
                    # Block and cancel to avoid re-trigger loops
                    t.status = "cancelled"
                    t.note = f"exposure_block: {gr.reason}"
                    self._notify(
                        notifier,
                        t.chat_id,
                        f"🧯 Exposure guard blocked {t.symbol} {t.side.upper()} ({t.pending_type}): {gr.reason}\n"
                        f"Corr with: {', '.join(gr.correlated_with) if gr.correlated_with else '—'}",
                    )
                    try:
                        if journal_repo and hasattr(journal_repo, "add_event"):
                            journal_repo.add_event(
                                "exposure_block",
                                symbol=t.symbol,
                                side=t.side.upper(),
                                reason=gr.reason,
                                extra={"correlated_with": gr.correlated_with},
                            )
                    except Exception:
                        pass
                    fired.append(t)
                    continue
            except Exception:
                # If guard fails, don't block trading — just log.
                logger.debug(
                    "Exposure guard failed; proceeding without it.", exc_info=True
                )
                gr = None

            # ===== Execute: risk-sized or fixed-lot (guard already DD-scales) =====
            try:
                use_risk = bool(getattr(settings, "PENDINGS_USE_RISK_SIZING", True))
                risk_pct_to_use = float(getattr(settings, "RISK_DEFAULT_PCT", 1.0))
                lot_to_use = t.lot

                # Apply guard adjustments (includes DD factor if repo given)
                if gr:
                    if use_risk and sl_send is not None:
                        risk_pct_to_use = float(gr.adjusted_risk_pct)
                    else:
                        # Scale fixed lot proportionally to the trim factor if possible
                        try:
                            base = float(getattr(settings, "RISK_DEFAULT_PCT", 1.0))
                            factor = (gr.adjusted_risk_pct / base) if base > 0 else 1.0
                            lot_to_use = max(0.0, float(t.lot) * float(factor))
                        except Exception:
                            pass

                    # Notify if trimmed (but not blocked)
                    if gr.allow and gr.adjusted_risk_pct < float(
                        getattr(settings, "RISK_DEFAULT_PCT", 1.0)
                    ):
                        self._notify(
                            notifier,
                            t.chat_id,
                            f"🪙 Exposure trim: reducing risk on {t.symbol} {t.side.upper()} — {gr.reason}",
                        )
                        try:
                            if journal_repo and hasattr(journal_repo, "add_event"):
                                journal_repo.add_event(
                                    "exposure_trim",
                                    symbol=t.symbol,
                                    side=t.side.upper(),
                                    reason=gr.reason,
                                    extra={
                                        "adjusted_risk_pct": risk_pct_to_use,
                                        "lot_scaled_to": lot_to_use,
                                    },
                                )
                        except Exception:
                            pass

                # If guard surfaced dd info, keep a short note
                dd_note = ""
                try:
                    if gr and "dd-factor" in (gr.reason or ""):
                        # e.g. "…; dd-factor=0.72 (DD=12.34%)"
                        dd_part = gr.reason.split(";")[-1].strip()
                        dd_note = f" [{dd_part}]"
                except Exception:
                    pass

                # Send order
                if use_risk and sl_send is not None:
                    res = mt5svc.open_order(
                        symbol=t.symbol,
                        side=t.side,
                        lot=None,  # size by risk in service
                        sl=sl_send,
                        tp=t.tp,
                        comment=f"synthetic-{t.pending_type.lower()}",
                        risk_pct=risk_pct_to_use,
                    )
                else:
                    res = mt5svc.open_order(
                        symbol=t.symbol,
                        side=t.side,
                        lot=lot_to_use,
                        sl=sl_send,
                        tp=t.tp,
                        comment=f"synthetic-{t.pending_type.lower()}",
                    )

                # Extract details safely (prefer executed price if available)
                details = res.get("details", {}) if isinstance(res, dict) else {}
                fallback_px = ask if t.side == "buy" else bid
                fill_px = (
                    details.get("price_executed")
                    if details.get("price_executed") is not None
                    else details.get("price")
                )
                used_lot = float(details.get("volume") or lot_to_use or 0.0)

                # Persist what actually happened
                t.filled_price = (
                    float(fill_px) if fill_px is not None else float(fallback_px)
                )
                t.lot = used_lot  # overwrite with actual sent lot
                raw_ticket = (
                    details.get("ticket")
                    or details.get("order")
                    or details.get("deal")
                    or None
                )
                t.filled_ticket = int(raw_ticket) if raw_ticket is not None else None

                t.status = "filled"
                t.sl_used = sl_send
                if dd_note:
                    t.note = (t.note + dd_note).strip()
                fired.append(t)

                # OCO: cancel siblings
                if t.oco_group:
                    n = self.cancel_group(t.oco_group, exclude_task_id=t.id)
                    if n:
                        self._notify(
                            notifier,
                            t.chat_id,
                            f"🪄 OCO: cancelled {n} sibling pending(s) after fill.",
                        )

                # Register for position watcher with meta (regime + strategy hint)
                try:
                    if poswatch and t.filled_ticket:
                        strat_hint = (
                            "breakout"
                            if t.pending_type.endswith("STOP")
                            else "mean_reversion"
                        )
                        meta = {"regime": t.regime, "strategy": strat_hint}
                        try:
                            poswatch.register_ticket_chat(int(t.filled_ticket), int(t.chat_id), meta=meta)  # type: ignore[arg-type]
                        except TypeError:
                            poswatch.register_ticket_chat(
                                int(t.filled_ticket), int(t.chat_id)
                            )
                            try:
                                poswatch.ticket_meta[str(int(t.filled_ticket))] = meta  # type: ignore[attr-defined]
                                poswatch._save()
                            except Exception:
                                pass
                except Exception:
                    logger.debug("poswatch register failed", exc_info=True)

            except Exception as e:
                t.status = "cancelled"
                t.note = f"send_failed: {e}"
                fired.append(t)

        # Persist and notify/journal
        if fired or expired:
            with self._lock:
                for t in fired + expired:
                    self._tasks[t.id] = t
                self.save()

            for t in fired:
                if t.status == "filled":
                    msg = (
                        f"✅ Pending triggered: {t.symbol} {t.side.upper()} ({t.pending_type})\n"
                        f"• Trigger: {t.entry}\n"
                        f"• Fill: {t.filled_price if t.filled_price is not None else '—'}\n"
                        f"• SL: {t.sl_used if t.sl_used is not None else '—'} | TP: {t.tp or '—'}\n"
                        f"• Lot: {t.lot} • Ticket: {t.filled_ticket or '—'}"
                    )
                    if t.note:
                        msg += f"\n• Note: {t.note}"
                elif t.status == "cancelled" and t.note.startswith("exposure_block"):
                    msg = f"🧯 Exposure block: {t.symbol} {t.side.upper()} ({t.pending_type}) @ {t.entry}\n• {t.note}"
                elif t.status == "cancelled" and t.note.startswith("circuit_block"):
                    msg = f"🧯 Circuit block: {t.symbol} {t.side.upper()} ({t.pending_type}) @ {t.entry}\n• {t.note}"
                else:
                    msg = f"✖️ Pending cancelled: {t.symbol} {t.side.upper()} ({t.pending_type})"

                self._notify(notifier, t.chat_id, msg)

                # Journal fill (legacy & new)
                try:
                    if (
                        journal_repo
                        and hasattr(journal_repo, "write_exec")
                        and t.status == "filled"
                    ):
                        bal = eq = None
                        try:
                            bal, eq = mt5svc.account_bal_eq()
                        except Exception:
                            pass
                        row = {
                            "ts": datetime.utcnow().replace(microsecond=0).isoformat()
                            + "Z",
                            "symbol": t.symbol,
                            "side": t.side,
                            "entry": t.filled_price,
                            "sl": t.sl_used,
                            "tp": t.tp,
                            "lot": t.lot,
                            "ticket": t.filled_ticket,
                            "position": None,
                            "balance": bal,
                            "equity": eq,
                            "confidence": None,
                            "regime": t.regime,
                            "rr": None,
                            "notes": f"synthetic-{t.pending_type.lower()} (OCO={t.oco_group or '-'}) {t.note}".strip(),
                        }
                        journal_repo.write_exec(row)
                    elif (
                        journal_repo
                        and hasattr(journal_repo, "add_event")
                        and t.status == "filled"
                    ):
                        journal_repo.add_event(
                            "pending_fill",
                            symbol=t.symbol,
                            side=t.side.upper(),
                            price=t.filled_price,
                            sl=t.sl_used,
                            tp=t.tp,
                            volume=t.lot,
                            reason=f"synthetic-{t.pending_type.lower()}",
                            extra={
                                "ticket": t.filled_ticket,
                                "oco_group": t.oco_group,
                                "regime": t.regime,
                                "note": t.note,
                            },
                        )
                except Exception:
                    logger.debug(
                        "Journal write for pending fill failed.", exc_info=True
                    )

            for t in expired:
                msg = f"⌛️ Pending expired: {t.symbol} {t.side.upper()} ({t.pending_type}) @ {t.entry}"
                self._notify(notifier, t.chat_id, msg)

    @staticmethod
    def _notify(notifier, chat_id: int, text: str) -> None:
        try:
            r = notifier(chat_id, text)
            if asyncio.iscoroutine(r):
                asyncio.create_task(r)
        except Exception:
            logger.debug("Notify failed", exc_info=True)
