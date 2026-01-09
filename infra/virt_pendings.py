# =====================================
# infra/virt_pendings.py  (TelegramMoneyBot.v7 — Phase 4)
# =====================================
# SQLite-backed Pending Manager (OCO-aware, Phase-4 compliant)
# API: add(), list_for_chat(), cancel(), poll_once(), get()

from __future__ import annotations

import asyncio
import sqlite3, time as _t, logging
import time
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

from config import settings
from infra.mt5_service import MT5Service

logger = logging.getLogger(__name__)
DB_FILE = Path(__file__).resolve().parent / "virtual_pendings.sqlite3"


# ---- utility -------------------------------------------------------

def _now_ts() -> int:
    return int(time.time())


def _mk_db_path(store_hint: Optional[str]) -> str:
    db_path = getattr(settings, "BOT_DB_PATH", None)
    if db_path:
        return str(db_path)

    if store_hint and "." in store_hint:
        import os
        base_dir = os.path.dirname(store_hint) or "."
        return os.path.join(base_dir, "bot.sqlite")

    try:
        import os
        jdb = getattr(settings, "JOURNAL_DB_PATH", "./data/journal.sqlite")
        base_dir = os.path.dirname(jdb) or "./data"
        return os.path.join(base_dir, "bot.sqlite")
    except Exception:
        return "./data/bot.sqlite"


# === Phase4: normalize plan metadata for pending records ===
def _normalize_plan_meta(meta: dict) -> dict:
    meta = dict(meta or {})
    # Standardize known fields with safe defaults
    ptype = str(meta.get("ptype", "")).upper()
    meta.setdefault("style", meta.get("style") or ("breakout" if "STOP" in ptype else "reversion"))
    meta.setdefault("retest_level", meta.get("retest_level"))
    meta.setdefault("buffer_pts", meta.get("buffer_pts"))
    meta.setdefault("mean_kind", meta.get("mean_kind"))       # 'EMA20'|'EMA50'|'EMA200'|VWAP|Pivot (VWAP/Pivot optional)
    meta.setdefault("trigger_rule", meta.get("trigger_rule")) # e.g., 'close+retest'
    meta.setdefault("adx_m15_at_plan", meta.get("adx_m15_at_plan"))
    meta.setdefault("session_tag", meta.get("session_tag"))
    return meta


# ---- data model ----------------------------------------------------

@dataclass
class VPendingTask:
    id: int
    chat_id: int
    symbol: str
    side: str  # "buy" | "sell"
    pending_type: str  # "BUY_STOP"|"SELL_STOP"|"BUY_LIMIT"|"SELL_LIMIT"
    entry: float
    sl: Optional[float]
    tp: Optional[float]
    volume: float  # canonical size
    expiry_ts: Optional[int]  # canonical timestamp (seconds)
    status: str  # "OPEN"|"CANCELLED"|"EXPIRED"|"FILLED"|"CANCELLED_OCO"|"ARMED"|"TRIGGERED"
    oco_group: Optional[str]
    note: str
    slippage_pts: float = 0.0  # legacy/compat column
    regime: Optional[str] = None

    # ---- Phase 4 meta (persisted) ----
    style: Optional[str] = None              # 'breakout'|'reversion'
    retest_level: Optional[float] = None     # breakout anchor or explicit level
    buffer_pts: Optional[float] = None       # buffer for retest/mean-tag
    mean_kind: Optional[str] = None          # 'EMA20'|'EMA50'|'EMA200'|VWAP|Pivot
    trigger_rule: Optional[str] = None       # 'close+retest' etc.
    session_tag: Optional[str] = None
    adx_m15_at_plan: Optional[float] = None
    armed_ts: Optional[int] = None
    group_id: Optional[str] = None           # alias/mirror for oco_group

    # Back-compat alias expected by older code paths
    @property
    def lot(self) -> float:
        return float(self.volume)


# ---- schema --------------------------------------------------------

def _ensure_schema(db_path: str) -> None:
    """
    Create/migrate 'virtual_pending' to include:
      - size columns: volume + lot
      - legacy 'order_kind', 'slippage_pts'
      - canonical 'expiry_ts' (and tolerate legacy 'expires_ts')
      - both 'pending_type' and 'ptype'
      - Phase-4 meta fields + armed_ts + group_id
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='virtual_pending'")
    exists = bool(cur.fetchone())

    desired_cols = {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "chat_id": "INTEGER",
        "symbol": "TEXT",
        "side": "TEXT",
        "pending_type": "TEXT",
        "ptype": "TEXT",
        "entry": "REAL",
        "sl": "REAL",
        "tp": "REAL",
        # size (support both names)
        "volume": "REAL",
        "lot": "REAL",
        # legacy/compat
        "order_kind": "TEXT",
        "slippage_pts": "REAL",
        # expiry (canonical + legacy)
        "expiry_ts": "INTEGER",
        "expires_ts": "INTEGER",
        # misc
        "status": "TEXT",
        "oco_group": "TEXT",
        "note": "TEXT",
        "created_ts": "INTEGER",
        "updated_ts": "INTEGER",
        "regime": "TEXT",
        # ---- Phase 4 additions ----
        "style": "TEXT",
        "retest_level": "REAL",
        "buffer_pts": "REAL",
        "mean_kind": "TEXT",
        "trigger_rule": "TEXT",
        "session_tag": "TEXT",
        "adx_m15_at_plan": "REAL",
        "armed_ts": "INTEGER",
        "group_id": "TEXT",
    }

    if not exists:
        cols_sql = ", ".join([f"{k} {v}" for k, v in desired_cols.items()])
        cur.execute(f"CREATE TABLE IF NOT EXISTS virtual_pending ({cols_sql});")
        # Indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_vpend_chat ON virtual_pending(chat_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_vpend_sym  ON virtual_pending(symbol, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_vpend_oco  ON virtual_pending(oco_group, status)")
        now = int(_t.time())
        # Defaults
        cur.execute("UPDATE virtual_pending SET status='OPEN' WHERE status IS NULL")
        cur.execute("UPDATE virtual_pending SET order_kind='pending' WHERE order_kind IS NULL")
        cur.execute("UPDATE virtual_pending SET slippage_pts=0.0 WHERE slippage_pts IS NULL")
        cur.execute(
            "UPDATE virtual_pending SET created_ts=?, updated_ts=? WHERE created_ts IS NULL OR updated_ts IS NULL",
            (now, now),
        )
        cur.execute("UPDATE virtual_pending SET armed_ts=created_ts WHERE armed_ts IS NULL AND created_ts IS NOT NULL")
        cur.execute("UPDATE virtual_pending SET group_id=oco_group WHERE group_id IS NULL AND oco_group IS NOT NULL")
        con.commit()
        con.close()
        return

    # Table exists: migrate columns as needed
    cur.execute("PRAGMA table_info(virtual_pending)")
    have_cols = {row["name"] for row in cur.fetchall()}

    to_add = [c for c in desired_cols.keys() if c not in have_cols]
    for c in to_add:
        cur.execute(f"ALTER TABLE virtual_pending ADD COLUMN {c} {desired_cols[c]}")

    # Backfill size aliases
    if "lot" in to_add and "volume" in have_cols:
        cur.execute("UPDATE virtual_pending SET lot=volume WHERE lot IS NULL")
    if "volume" in to_add and "lot" in have_cols:
        cur.execute("UPDATE virtual_pending SET volume=lot WHERE volume IS NULL")

    # Backfill ptype from legacy pending_type if needed
    if "ptype" in to_add and "pending_type" in have_cols:
        cur.execute(
            "UPDATE virtual_pending SET ptype=pending_type "
            "WHERE ptype IS NULL AND pending_type IS NOT NULL"
        )

    # Legacy backfills
    cur.execute("UPDATE virtual_pending SET order_kind='pending' WHERE order_kind IS NULL OR order_kind=''")
    cur.execute("UPDATE virtual_pending SET slippage_pts=0.0 WHERE slippage_pts IS NULL")

    # Mirror legacy expires_ts -> expiry_ts
    if "expires_ts" in have_cols and "expiry_ts" in have_cols:
        cur.execute(
            "UPDATE virtual_pending SET expiry_ts=expires_ts WHERE expiry_ts IS NULL AND expires_ts IS NOT NULL"
        )

    # Backfill other defaults
    now = int(_t.time())
    if "status" in to_add:
        cur.execute("UPDATE virtual_pending SET status='OPEN' WHERE status IS NULL")
    if "created_ts" in to_add:
        cur.execute("UPDATE virtual_pending SET created_ts=? WHERE created_ts IS NULL", (now,))
    if "updated_ts" in to_add:
        cur.execute("UPDATE virtual_pending SET updated_ts=? WHERE updated_ts IS NULL", (now,))
    if "note" in to_add:
        cur.execute("UPDATE virtual_pending SET note='' WHERE note IS NULL")

    # Phase-4 backfills
    cur.execute("UPDATE virtual_pending SET group_id=oco_group WHERE group_id IS NULL AND oco_group IS NOT NULL")
    cur.execute("UPDATE virtual_pending SET armed_ts=created_ts WHERE armed_ts IS NULL AND created_ts IS NOT NULL")

    # Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vpend_chat ON virtual_pending(chat_id, status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vpend_sym  ON virtual_pending(symbol, status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vpend_oco  ON virtual_pending(oco_group, status)")

    con.commit()
    con.close()


def _row_to_task(row: sqlite3.Row) -> VPendingTask:
    keys = set(row.keys())
    # size
    if "volume" in keys and row["volume"] is not None:
        vol = float(row["volume"])
    elif "lot" in keys and row["lot"] is not None:
        vol = float(row["lot"])
    else:
        vol = 0.0
    # slip
    slip = 0.0
    if "slippage_pts" in keys and row["slippage_pts"] is not None:
        slip = float(row["slippage_pts"])
    # expiry (prefer canonical)
    exp = None
    if "expiry_ts" in keys and row["expiry_ts"] is not None:
        exp = int(row["expiry_ts"])
    elif "expires_ts" in keys and row["expires_ts"] is not None:
        exp = int(row["expires_ts"])

    # prefer canonical pending_type; otherwise ptype
    if "pending_type" in keys and row["pending_type"]:
        ptype = row["pending_type"]
    elif "ptype" in keys:
        ptype = row["ptype"]
    else:
        ptype = None

    def _get(name, cast=None):
        if name not in keys:
            return None
        v = row[name]
        if v is None:
            return None
        return cast(v) if cast else v

    return VPendingTask(
        id=row["id"],
        chat_id=row["chat_id"],
        symbol=row["symbol"],
        side=str(row["side"]).lower(),
        pending_type=str(ptype).upper() if ptype else "",
        entry=float(row["entry"]),
        sl=None if row["sl"] is None else float(row["sl"]),
        tp=None if row["tp"] is None else float(row["tp"]),
        volume=vol,
        expiry_ts=exp,
        status=row["status"],
        oco_group=row["oco_group"],
        note=row["note"] or "",
        slippage_pts=slip,
        regime=_get("regime"),
        # Phase-4 meta
        style=_get("style"),
        retest_level=_get("retest_level", float),
        buffer_pts=_get("buffer_pts", float),
        mean_kind=_get("mean_kind"),
        trigger_rule=_get("trigger_rule"),
        session_tag=_get("session_tag"),
        adx_m15_at_plan=_get("adx_m15_at_plan", float),
        armed_ts=_get("armed_ts", int),
        group_id=_get("group_id"),
    )


def _triggered(t: VPendingTask, bid: Optional[float], ask: Optional[float]) -> bool:
    if bid is None or ask is None:
        return False
    pt = t.pending_type.upper()
    if pt == "BUY_STOP":
        return ask >= t.entry
    if pt == "SELL_STOP":
        return bid <= t.entry
    if pt == "BUY_LIMIT":
        return ask <= t.entry
    if pt == "SELL_LIMIT":
        return bid >= t.entry
    return False


# ---- manager -------------------------------------------------------

class VirtualPendingManager:
    """
    API mirror used by handlers:
      - add(...)
      - list_for_chat(chat_id)
      - cancel(id, chat_id=...)
      - poll_once(mt5svc, notify_async, journal_repo=None, poswatch=None, circuit=None)
      - get(id)
    """

    def __init__(self, store_path_hint: Optional[str] = None):
        self.db_path = _mk_db_path(store_path_hint)
        _ensure_schema(self.db_path)
        # Persistent connection (thread check off in case of callbacks)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    # ---------- public API ----------

    def add(self, **kwargs) -> VPendingTask:
        """
        Insert a virtual pending order.

        Accepts both 'expiry_ts' (canonical) and legacy 'expires_ts'.
        Guarantees an integer expiry_ts in SQL params (defaults to now + 60m if missing/invalid).
        Accepts 'ptype' or 'pending_type'; 'volume' or 'lot'.
        Sets default status to 'ARMED' (matches your v7 behavior).
        Persists Phase-4 meta fields when provided.
        """
        now = _now_ts()

        # --- Normalize expiry field robustly ---
        exp = kwargs.pop("expiry_ts", None)
        if exp in (None, ""):
            exp = kwargs.pop("expires_ts", None)
        try:
            expi = int(float(exp)) if exp is not None else now + 60 * 60
        except Exception:
            expi = now + 60 * 60
        if expi <= now:  # no past expiries
            expi = now + 60 * 60

        # --- Canonicalize pending type & side ---
        ptype = (
            str(kwargs.get("pending_type") or kwargs.get("ptype") or "")
            .strip()
            .upper()
            .replace(" ", "_")
        )
        side = str(kwargs.get("side") or "").strip().lower()  # 'buy'/'sell'

        # --- Map volume->lot if caller used volume ---
        if "lot" not in kwargs and "volume" in kwargs:
            kwargs["lot"] = kwargs.pop("volume")

        # Phase-4 meta (normalize and fold into params)
        plan_meta = _normalize_plan_meta({
            **kwargs,
            "ptype": ptype,
        })

        params = {
            # required fields
            "symbol": kwargs.get("symbol"),
            "ptype": ptype,                # store canonical in ptype
            "pending_type": ptype,         # keep legacy alias too
            "side": side,
            "entry": float(kwargs.get("entry")),
            "sl": float(kwargs.get("sl")) if kwargs.get("sl") is not None else None,
            "tp": float(kwargs.get("tp")) if kwargs.get("tp") is not None else None,
            "lot": float(kwargs.get("lot")),
            # expiry canonical + legacy mirror
            "expiry_ts": expi,
            "expires_ts": expi,
            # optional metadata
            "regime": kwargs.get("regime"),
            "note": kwargs.get("note"),
            "created_ts": now,
            "updated_ts": now,
            "status": "ARMED",
            "chat_id": int(kwargs.get("chat_id") or 0),
            "oco_group": kwargs.get("oco_group"),
            # compat
            "order_kind": "pending",
            "slippage_pts": float(kwargs.get("slippage_pts") or 0.0),
            # Phase-4 meta
            "style": plan_meta.get("style"),
            "retest_level": plan_meta.get("retest_level"),
            "buffer_pts": plan_meta.get("buffer_pts"),
            "mean_kind": plan_meta.get("mean_kind"),
            "trigger_rule": plan_meta.get("trigger_rule"),
            "session_tag": plan_meta.get("session_tag"),
            "adx_m15_at_plan": plan_meta.get("adx_m15_at_plan"),
            "armed_ts": now,
            "group_id": kwargs.get("group_id") or kwargs.get("oco_group"),
        }

        # Ensure volume alias sits too (for tables with NOT NULL)
        params["volume"] = float(params["lot"])

        # Build dynamic INSERT aligned to existing table columns
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(virtual_pending)")
        tbl_cols = cur.fetchall()

        cols, placeholders, bind = [], [], {}
        for col in tbl_cols:
            name = col["name"]
            if name == "id":
                continue
            val = params.get(name, None)

            # Fill required defaults
            if col["notnull"] and val is None:
                if name in ("status",):
                    val = "ARMED"
                elif name in ("order_kind",):
                    val = "pending"
                elif name in ("side",):
                    val = side
                elif name in ("ptype", "pending_type"):
                    val = ptype
                elif name in ("symbol", "regime", "note", "oco_group", "client_tag", "style", "mean_kind", "trigger_rule", "session_tag", "group_id"):
                    val = "" if name not in ("oco_group", "group_id") else None
                elif name in ("entry", "sl", "tp", "lot", "volume", "slippage_pts", "retest_level", "buffer_pts", "adx_m15_at_plan"):
                    if name == "volume":
                        val = float(params["lot"])
                    elif name in ("entry", "lot"):
                        val = float(params[name]) if params.get(name) is not None else 0.0
                    elif name in ("sl", "tp"):
                        # IMPROVED: Never allow 0.0 for SL/TP - use NULL if not provided
                        # This prevents silent execution without stops
                        val = None if params.get(name) is None else float(params[name])
                    else:
                        val = 0.0
                elif name in ("expiry_ts", "expires_ts", "created_ts", "updated_ts", "chat_id", "armed_ts"):
                    if name in ("created_ts", "updated_ts", "armed_ts"):
                        val = now
                    elif name == "chat_id":
                        val = int(params["chat_id"])
                    else:
                        val = expi
                else:
                    val = ""

            cols.append(name)
            placeholders.append(":" + name)
            bind[name] = val

        sql = "INSERT INTO virtual_pending (" + ", ".join(cols) + ") VALUES (" + ", ".join(placeholders) + ")"
        cur.execute(sql, bind)
        self.conn.commit()

        # Return rich task
        new_id = cur.lastrowid
        cur2 = self.conn.cursor()
        cur2.execute("SELECT * FROM virtual_pending WHERE id=?", (new_id,))
        row = cur2.fetchone()
        return (
            _row_to_task(row)
            if row
            else VPendingTask(
                id=new_id,
                chat_id=int(bind.get("chat_id") or 0),
                symbol=str(bind.get("symbol") or ""),
                side=str(bind.get("side") or "").lower(),
                pending_type=str(bind.get("pending_type") or bind.get("ptype") or "").upper(),
                entry=(float(bind.get("entry")) if bind.get("entry") is not None else 0.0),
                sl=None if bind.get("sl") is None else float(bind.get("sl")),
                tp=None if bind.get("tp") is None else float(bind.get("tp")),
                volume=float(bind.get("volume") or bind.get("lot") or 0.0),
                expiry_ts=int(bind.get("expiry_ts") or bind.get("expires_ts") or 0) or None,
                status=str(bind.get("status") or "ARMED"),
                oco_group=bind.get("oco_group"),
                note=str(bind.get("note") or ""),
                slippage_pts=float(bind.get("slippage_pts") or 0.0),
                regime=bind.get("regime"),
                style=bind.get("style"),
                retest_level=bind.get("retest_level"),
                buffer_pts=bind.get("buffer_pts"),
                mean_kind=bind.get("mean_kind"),
                trigger_rule=bind.get("trigger_rule"),
                session_tag=bind.get("session_tag"),
                adx_m15_at_plan=bind.get("adx_m15_at_plan"),
                armed_ts=bind.get("armed_ts"),
                group_id=bind.get("group_id"),
            )
        )

    def get(self, task_id: int) -> Optional[VPendingTask]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM virtual_pending WHERE id=?", (int(task_id),))
        row = cur.fetchone()
        return _row_to_task(row) if row else None

    def list_for_chat(self, chat_id: int) -> List[VPendingTask]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM virtual_pending
            WHERE chat_id=? AND status IN ('OPEN','ARMED')
            ORDER BY (COALESCE(expiry_ts, expires_ts) IS NULL) ASC,
                    COALESCE(expiry_ts, expires_ts) ASC,
                    id ASC
            """,
            (int(chat_id),),
        )
        return [_row_to_task(r) for r in cur.fetchall()]

    def cancel(self, task_id: int, chat_id: Optional[int] = None) -> bool:
        cur = self.conn.cursor()
        now = _now_ts()
        if chat_id is None:
            cur.execute(
                "UPDATE virtual_pending SET status='CANCELLED', updated_ts=? WHERE id=? AND status IN ('OPEN','ARMED')",
                (now, int(task_id)),
            )
            n = cur.rowcount
        else:
            cur.execute(
                "UPDATE virtual_pending SET status='CANCELLED', updated_ts=? WHERE id=? AND chat_id=? AND status IN ('OPEN','ARMED')",
                (now, int(task_id), int(chat_id)),
            )
            n = cur.rowcount
            if n == 0:
                cur.execute(
                    "UPDATE virtual_pending SET status='CANCELLED', updated_ts=? WHERE id=? AND status IN ('OPEN','ARMED')",
                    (now, int(task_id)),
                )
                n = cur.rowcount
        self.conn.commit()
        return n > 0

    def poll_once(
        self,
        mt5svc: MT5Service,
        notify_async,  # async fn(chat_id: int, text: str)
        *,
        journal_repo=None,
        poswatch=None,
        circuit=None,
    ) -> None:
        """
        - Expire overdue OPEN/ARMED tasks
        - Trigger market orders on touch/cross for OPEN or ARMED
        - Enforce Phase-4 gates (breakout retest / reversion mean-tag)
        - Enforce OCO: cancel siblings in same group on first fill
        - Notify & journal events
        """
        now = _now_ts()
        cur = self.conn.cursor()

        # 1) Expire overdue OPEN/ARMED
        cur.execute(
            """
            SELECT id, chat_id, symbol, COALESCE(expiry_ts, expires_ts) AS exp_ts
            FROM virtual_pending
            WHERE status IN ('OPEN','ARMED')
            AND COALESCE(expiry_ts, expires_ts) IS NOT NULL
            AND COALESCE(expiry_ts, expires_ts) < ?
            """,
            (now,),
        )

        to_expire = cur.fetchall()
        for r in to_expire:
            cur.execute(
                "UPDATE virtual_pending SET status='EXPIRED', updated_ts=? "
                "WHERE id=? AND status IN ('OPEN','ARMED')",
                (now, int(r["id"])),
            )
            try:
                asyncio.create_task(
                    notify_async(
                        int(r["chat_id"]),
                        f"⌛ Pending for {r['symbol']} expired.",
                    )
                )
            except Exception:
                pass
            if journal_repo is not None:
                try:
                    journal_repo.write_event(
                        "pending_expired",
                        ts=now,
                        symbol=r["symbol"],
                        pending_id=int(r["id"]),
                    )
                except Exception:
                    pass

        # IMPROVED: Auto-cleanup old pending orders (24 hours for ARMED/OPEN, 7 days for others)
        # This prevents stale orders from accumulating in the database
        age_limit_active = 24 * 3600  # 24 hours for active orders
        age_limit_completed = 7 * 24 * 3600  # 7 days for completed/cancelled orders
        
        # Clean up old ARMED/OPEN orders without expiry (safety net)
        cur.execute(
            """
            SELECT id, chat_id, symbol, status, created_ts
            FROM virtual_pending
            WHERE status IN ('ARMED', 'OPEN')
            AND created_ts < ?
            """,
            (now - age_limit_active,),
        )
        
        old_active = cur.fetchall()
        if old_active:
            logger.info(f"Auto-expiring {len(old_active)} old pending orders (>24h old)")
            for r in old_active:
                cur.execute(
                    "UPDATE virtual_pending SET status='EXPIRED', note=COALESCE(note,'')||' [auto_expired_24h]', updated_ts=? "
                    "WHERE id=? AND status IN ('ARMED', 'OPEN')",
                    (now, int(r["id"])),
                )
                try:
                    asyncio.create_task(
                        notify_async(
                            int(r["chat_id"]),
                            f"⌛ Old pending order for {r['symbol']} expired (>24h old).",
                        )
                    )
                except Exception:
                    pass
        
        # Clean up very old completed orders from database (reduce clutter)
        cur.execute(
            """
            DELETE FROM virtual_pending
            WHERE status IN ('FILLED', 'CANCELLED', 'EXPIRED', 'CANCELLED_OCO')
            AND updated_ts < ?
            """,
            (now - age_limit_completed,),
        )
        deleted_count = cur.rowcount
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old completed pending orders (>7 days old)")

        # 2) Load active (OPEN + ARMED)
        cur.execute(
            "SELECT * FROM virtual_pending WHERE status IN ('OPEN','ARMED') ORDER BY id ASC"
        )
        active = [_row_to_task(r) for r in cur.fetchall()]

        # 3) Try fills
        for t in active:
            try:
                mt5svc.ensure_symbol(t.symbol)
                q = mt5svc.get_quote(t.symbol)
                bid = getattr(q, "bid", None) if q is not None else None
                ask = getattr(q, "ask", None) if q is not None else None

                # ---- Phase-4 gates: breakout close+retest / reversion mean tag ----
                try:
                    style = (t.style or "").lower()
                    trig = (t.trigger_rule or "").lower()
                    level = (t.retest_level if t.retest_level is not None else t.entry)
                    buf = float(t.buffer_pts or 0.0)
                    need_retest = style == "breakout" and ("retest" in trig)
                    need_mean = style == "reversion"

                    tech = None
                    if need_retest or need_mean:
                        # lazy import to avoid hard dependency at module import
                        from infra.indicator_bridge import IndicatorBridge
                        bridge = IndicatorBridge(getattr(settings, "MT5_FILES_DIR", "./"))
                        tech = bridge.collect_quick(t.symbol)

                    if need_retest:
                        if not _retest_confirmed(t.symbol, "M15", float(level), tech or {}, float(buf)):
                            # wait until retest confirmed
                            continue

                    if need_mean:
                        # mean-tag: check proximity to selected mean on M15 (EMA/VWAP/Pivot levels)
                        mk = (t.mean_kind or "EMA20").upper()
                        tf_blob = (tech or {}).get("M15") or (tech or {}).get("_tf_M15") or {}
                        # if we have live quotes, use the active side; otherwise fall back to snapshot close
                        price = (
                            float(bid if t.side == "sell" else ask)
                            if (bid is not None and ask is not None)
                            else float(tf_blob.get("close") or 0.0)
                        )

                    key_map = {
                        # EMAs
                        "EMA": "ema20", "EMA20": "ema20", "EMA_20": "ema20",
                        "EMA50": "ema50", "EMA_50": "ema50",
                        "EMA200": "ema200", "EMA_200": "ema200",
                        # VWAP
                        "VWAP": "vwap",
                        # Pivots (classic)
                        "PIVOT": "pivot", "PP": "pivot",
                        "R1": "r1", "S1": "s1", "R2": "r2", "S2": "s2",
                    }
                    k = key_map.get(mk)
                    mean_val = tf_blob.get(k) if k else None

                    # Enforce tag proximity
                    if mean_val is not None and price:
                        if abs(float(price) - float(mean_val)) > float(buf):
                            continue  # not tagged yet

                except Exception:
                    # swallow gating errors to avoid stalling the monitor
                    pass

                # Price trigger check
                if not _triggered(t, bid, ask):
                    continue

                # Mark TRIGGERED before execution (Phase-4)
                try:
                    cur.execute(
                        "UPDATE virtual_pending SET status='TRIGGERED', updated_ts=? WHERE id=? AND status IN ('OPEN','ARMED')",
                        (now, int(t.id)),
                    )
                    
                    # CRITICAL: Cancel OCO siblings IMMEDIATELY when triggered (before execution)
                    # This prevents both legs from executing if they trigger simultaneously
                    oco_key = t.group_id or t.oco_group
                    if oco_key:
                        cur.execute(
                            "UPDATE virtual_pending SET status='CANCELLED_OCO', updated_ts=? "
                            "WHERE status IN ('OPEN','ARMED','TRIGGERED') AND (group_id=? OR oco_group=?) AND id<>?",
                            (now, str(oco_key), str(oco_key), int(t.id)),
                        )
                        cancelled_count = cur.rowcount
                        if cancelled_count > 0:
                            logger.info(f"OCO: Cancelled {cancelled_count} sibling(s) for group {oco_key} (triggered order {t.id})")
                        
                        # CRITICAL FIX: Commit immediately to persist the cancellation
                        # This ensures siblings are cancelled BEFORE execution continues
                        self.conn.commit()
                        
                        # CRITICAL FIX: Break out of the loop and re-fetch orders
                        # This prevents processing cancelled siblings in this same iteration
                        break
                        
                except Exception as e:
                    logger.warning(f"Failed to mark triggered or cancel OCO siblings: {e}")

                # IMPROVED: Safety check - never execute without valid SL/TP
                if t.sl is None or t.sl == 0.0 or t.tp is None or t.tp == 0.0:
                    logger.error(
                        f"CRITICAL: Pending order {t.id} has invalid SL/TP (sl={t.sl}, tp={t.tp}). "
                        f"Cancelling to prevent execution without stops."
                    )
                    cur.execute(
                        "UPDATE virtual_pending SET status='CANCELLED', note=COALESCE(note,'')||' [safety_block: invalid_sl_tp]', updated_ts=? WHERE id=?",
                        (now, int(t.id)),
                    )
                    self.conn.commit()
                    
                    # Notify user
                    if notify_async and t.chat_id:
                        try:
                            asyncio.create_task(
                                notify_async(
                                    int(t.chat_id),
                                    f"⚠️ Pending order {t.symbol} {t.pending_type} cancelled: Invalid SL/TP values (sl={t.sl}, tp={t.tp}). "
                                    f"Never trade without stops!"
                                )
                            )
                        except Exception:
                            pass
                    continue  # Skip execution
                
                # CRITICAL FIX: Validate SL/TP are on correct side of entry price
                is_buy = t.side.lower() == "buy"
                sl_invalid = (is_buy and t.sl >= t.entry) or (not is_buy and t.sl <= t.entry)
                tp_invalid = (is_buy and t.tp <= t.entry) or (not is_buy and t.tp >= t.entry)
                
                if sl_invalid or tp_invalid:
                    logger.error(
                        f"CRITICAL: Pending order {t.id} has SL/TP on WRONG SIDE of entry! "
                        f"{t.side.upper()} @ {t.entry}, SL={t.sl}, TP={t.tp}. Cancelling!"
                    )
                    cur.execute(
                        "UPDATE virtual_pending SET status='CANCELLED', note=COALESCE(note,'')||' [safety_block: wrong_side_sl_tp]', updated_ts=? WHERE id=?",
                        (now, int(t.id)),
                    )
                    self.conn.commit()
                    
                    # Notify user
                    if notify_async and t.chat_id:
                        try:
                            asyncio.create_task(
                                notify_async(
                                    int(t.chat_id),
                                    f"⚠️ CRITICAL: Pending order {t.symbol} {t.pending_type} cancelled!\n"
                                    f"SL/TP on WRONG SIDE of entry:\n"
                                    f"{t.side.upper()} @ {t.entry:.5f}\n"
                                    f"SL: {t.sl:.5f} (should be {'below' if is_buy else 'above'} entry)\n"
                                    f"TP: {t.tp:.5f} (should be {'above' if is_buy else 'below'} entry)\n"
                                    f"This order would have caused INSTANT LOSS!"
                                )
                            )
                        except Exception:
                            pass
                    continue  # Skip execution

                # Fill as MARKET (emulation / immediate)
                res = mt5svc.open_order(
                    symbol=t.symbol,
                    side=t.side,
                    sl=t.sl,
                    tp=t.tp,
                    lot=t.volume,  # canonical size
                    comment="virt_pending_fill",
                )

                # Tolerate various return shapes
                ticket = 0
                if isinstance(res, dict):
                    ticket = int(res.get("ticket") or 0)
                elif hasattr(res, "ticket"):
                    try:
                        ticket = int(res.ticket)
                    except Exception:
                        ticket = 0
                ok = bool(ticket)

                if ok:
                    # Mark filled
                    cur.execute(
                        "UPDATE virtual_pending SET status='FILLED', updated_ts=? WHERE id=?",
                        (now, int(t.id)),
                    )

                    # OCO cancel siblings (OPEN/ARMED/TRIGGERED -> CANCELLED_OCO)
                    oco_key = t.group_id or t.oco_group
                    if oco_key:
                        cur.execute(
                            "UPDATE virtual_pending SET status='CANCELLED_OCO', updated_ts=? "
                            "WHERE status IN ('OPEN','ARMED','TRIGGERED') AND (group_id=? OR oco_group=?) AND id<>?",
                            (now, str(oco_key), str(oco_key), int(t.id)),
                        )

                    # Notify & journal
                    try:
                        price_txt = (
                            f"{(ask if t.side=='buy' else bid):.2f}"
                            if (ask is not None and bid is not None)
                            else f"{t.entry:.2f}"
                        )
                        asyncio.create_task(
                            notify_async(
                                int(t.chat_id),
                                (
                                    "✅ Pending filled "
                                    f"({t.pending_type}) {t.symbol} {t.side.upper()} "
                                    f"@~{price_txt} "
                                    f"(plan {t.entry:.2f}; SL {t.sl if t.sl is not None else '—'}, "
                                    f"TP {t.tp if t.tp is not None else '—'})"
                                ),
                            )
                        )
                    except Exception:
                        pass

                    if journal_repo is not None:
                        try:
                            entry_px = ask if t.side == "buy" else bid
                            if entry_px is None:
                                entry_px = t.entry
                            journal_repo.write_event(
                                "pending_filled",
                                ts=now,
                                symbol=t.symbol,
                                side=t.side.upper(),
                                entry=entry_px,
                                plan_entry=t.entry,
                                sl=t.sl,
                                tp=t.tp,
                                lot=t.volume,
                                ticket=ticket,
                                pending_id=t.id,
                                oco_group=oco_key,
                                meta={
                                    "style": t.style,
                                    "retest_level": t.retest_level,
                                    "buffer_pts": t.buffer_pts,
                                    "mean_kind": t.mean_kind,
                                    "trigger_rule": t.trigger_rule,
                                    "session_tag": t.session_tag,
                                    "adx_m15_at_plan": t.adx_m15_at_plan,
                                },
                            )
                        except Exception:
                            pass
                else:
                    # Revert TRIGGERED back to ARMED on send failure
                    cur.execute(
                        "UPDATE virtual_pending SET status='ARMED', note=COALESCE(note,'')||' [trigger_error]', updated_ts=? WHERE id=?",
                        (now, int(t.id)),
                    )

            except Exception as e:
                logger.exception("Pending poll exception: %s", e)
                cur.execute(
                    "UPDATE virtual_pending SET note=COALESCE(note,'')||' [poll_exc]', updated_ts=? WHERE id=?",
                    (now, int(t.id)),
                )

        self.conn.commit()


# === Phase4: breakout retest confirmation ===
def _retest_confirmed(
    symbol: str,
    tf: str,
    level: float,
    tech: dict,
    buffer_pts: float = 0.0,
    tolerance_mult: float = 1.0,
    max_gap: int = 4,
) -> bool:
    """
    Return True if we have a 'close + retest' around `level` on `tf`.

    Heuristic:
      1) A candle closes beyond the breakout level (close > level or close < level)
      2) A subsequent candle closes back to (or through) the level within a small buffer
         within `max_gap` bars.

    Uses `tech['_tf_'+tf]` or `tech[tf]` dicts if present.
    """
    try:
        tf_blob = tech.get(f"_tf_{tf}") or tech.get(tf) or {}
        closes = tf_blob.get("closes") or tf_blob.get("close") or []
        highs = tf_blob.get("high") or tf_blob.get("highs") or []
        lows = tf_blob.get("low") or tf_blob.get("lows") or []
        if not closes or not highs or not lows:
            return False
        tol = abs(float(buffer_pts)) * float(tolerance_mult or 1.0)
        lev_hi = level + tol
        lev_lo = level - tol
        n = len(closes)
        start = max(0, n - 60)
        passed = False
        i_pass = None
        for i in range(start, n):
            c = float(closes[i])
            if not passed:
                if c > lev_hi or c < lev_lo:
                    passed = True
                    i_pass = i
                    continue
            else:
                if i_pass is not None and (i - i_pass) > int(max_gap):
                    break
                if lev_lo <= c <= lev_hi:
                    return True
        return False
    except Exception:
        return False
