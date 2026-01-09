# app/services/pending_emulator.py
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict

import MetaTrader5 as mt5

from infra.mt5_service import MT5Service

DB_DEFAULT = "data/bot.sqlite"


@dataclass
class VirtualPending:
    id: Optional[int]
    symbol: str
    side: str  # "BUY"/"SELL"
    entry: float
    sl: Optional[float]
    tp: Optional[float]
    volume: float
    order_kind: str  # "STOP" or "LIMIT"
    slippage_pts: float
    expiry_ts: int
    comment: str = ""
    status: str = "OPEN"  # OPEN/TRIGGERED/CANCELLED/EXPIRED
    oco_group: Optional[str] = None  # ← NEW: one-cancels-other grouping


def _ensure_schema(db_path: str):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS virtual_pending (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        entry REAL NOT NULL,
        sl REAL,
        tp REAL,
        volume REAL NOT NULL,
        order_kind TEXT NOT NULL,
        slippage_pts REAL NOT NULL,
        expiry_ts INTEGER NOT NULL,
        comment TEXT,
        status TEXT NOT NULL DEFAULT 'OPEN',
        oco_group TEXT,
        created_ts INTEGER NOT NULL,
        updated_ts INTEGER NOT NULL
    )
    """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vp_status ON virtual_pending(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vp_oco ON virtual_pending(oco_group)")
    con.commit()
    con.close()


def create_virtual_pending(v: VirtualPending, db_path: str = DB_DEFAULT) -> int:
    _ensure_schema(db_path)
    now = int(time.time())
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """
    INSERT INTO virtual_pending
    (symbol, side, entry, sl, tp, volume, order_kind, slippage_pts, expiry_ts, comment, status, oco_group, created_ts, updated_ts)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,
        (
            v.symbol,
            v.side.upper(),
            float(v.entry),
            float(v.sl) if v.sl is not None else None,
            float(v.tp) if v.tp is not None else None,
            float(v.volume),
            v.order_kind.upper(),
            float(v.slippage_pts),
            int(v.expiry_ts),
            v.comment,
            v.status,
            v.oco_group,
            now,
            now,
        ),
    )
    pid = cur.lastrowid
    con.commit()
    con.close()
    return int(pid)


def create_oco_pair(
    a: VirtualPending, b: VirtualPending, oco_group: str, db_path: str = DB_DEFAULT
) -> Tuple[int, int]:
    a.oco_group = oco_group
    b.oco_group = oco_group
    return create_virtual_pending(a, db_path), create_virtual_pending(b, db_path)


def list_open(db_path: str = DB_DEFAULT) -> List[VirtualPending]:
    _ensure_schema(db_path)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "SELECT id,symbol,side,entry,sl,tp,volume,order_kind,slippage_pts,expiry_ts,comment,status,oco_group FROM virtual_pending WHERE status='OPEN' ORDER BY id DESC"
    )
    rows = cur.fetchall()
    con.close()
    out: List[VirtualPending] = []
    for r in rows:
        out.append(
            VirtualPending(
                id=r[0],
                symbol=r[1],
                side=r[2],
                entry=r[3],
                sl=r[4],
                tp=r[5],
                volume=r[6],
                order_kind=r[7],
                slippage_pts=r[8],
                expiry_ts=r[9],
                comment=r[10],
                status=r[11],
                oco_group=r[12],
            )
        )
    return out


def cancel_virtual_pending(
    pid: int, reason: str = "user_cancel", db_path: str = DB_DEFAULT
):
    _ensure_schema(db_path)
    now = int(time.time())
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "UPDATE virtual_pending SET status='CANCELLED', comment=COALESCE(comment,'')||?', '||?, updated_ts=? WHERE id=? AND status='OPEN'",
        (reason, "", now, pid),
    )
    con.commit()
    con.close()


def cancel_group(
    oco_group: str, reason: str = "group_cancel", db_path: str = DB_DEFAULT
) -> int:
    """Cancel all OPEN pendings in the group. Returns count affected."""
    if not oco_group:
        return 0
    _ensure_schema(db_path)
    now = int(time.time())
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "UPDATE virtual_pending SET status='CANCELLED', comment=COALESCE(comment,'')||?, updated_ts=? WHERE status='OPEN' AND oco_group=?",
        (f" [{reason}]", now, oco_group),
    )
    n = cur.rowcount
    con.commit()
    con.close()
    return int(n)


def _trigger(v: VirtualPending, mt5svc: MT5Service) -> Dict:
    """Execute the market order immediately (emulating the pending)."""
    side = v.side.lower()
    mt5svc.ensure_symbol(v.symbol)
    # Execute at market and attach SL/TP if provided
    res = mt5svc.open_order(v.symbol, side, float(v.entry), v.sl, v.tp, float(v.volume))
    return (
        res
        if isinstance(res, dict)
        else {"ok": False, "message": "open_order returned non-dict", "details": {}}
    )


def _price_touches(v: VirtualPending, tick) -> bool:
    """Decide if pending should fire given the latest tick."""
    bid = getattr(tick, "bid", None)
    ask = getattr(tick, "ask", None)
    if bid is None or ask is None:
        return False
    if v.order_kind.upper() == "STOP":
        if v.side.upper() == "BUY":
            return ask >= v.entry - v.slippage_pts * 0.0
        else:
            return bid <= v.entry + v.slippage_pts * 0.0
    else:  # LIMIT
        if v.side.upper() == "BUY":
            return ask <= v.entry + v.slippage_pts * 0.0
        else:
            return bid >= v.entry - v.slippage_pts * 0.0


def check_and_trigger(db_path: str = DB_DEFAULT, notify: bool = False) -> List[int]:
    """
    Sweep OPEN pendings:
      - Expire past expiry_ts
      - Trigger when price condition hit
      - OCO: when one triggers, cancel its OPEN siblings in the same oco_group
    Returns list of processed IDs.
    """
    _ensure_schema(db_path)
    now = int(time.time())
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    # Fetch OPEN
    cur.execute(
        "SELECT id,symbol,side,entry,sl,tp,volume,order_kind,slippage_pts,expiry_ts,comment,status,oco_group FROM virtual_pending WHERE status='OPEN'"
    )
    rows = cur.fetchall()
    processed: List[int] = []
    mt5svc = MT5Service()
    mt5svc.connect()

    for r in rows:
        v = VirtualPending(
            id=r[0],
            symbol=r[1],
            side=r[2],
            entry=r[3],
            sl=r[4],
            tp=r[5],
            volume=r[6],
            order_kind=r[7],
            slippage_pts=r[8],
            expiry_ts=r[9],
            comment=r[10],
            status=r[11],
            oco_group=r[12],
        )

        # Expiry?
        if now >= int(v.expiry_ts):
            cur.execute(
                "UPDATE virtual_pending SET status='EXPIRED', updated_ts=? WHERE id=? AND status='OPEN'",
                (now, v.id),
            )
            processed.append(int(v.id))
            continue

        # Price check
        tick = mt5.symbol_info_tick(v.symbol)
        if tick is None:
            continue
        if not _price_touches(v, tick):
            continue

        # Trigger this one
        res = _trigger(v, mt5svc)
        ok = bool(res.get("ok"))
        if ok:
            cur.execute(
                "UPDATE virtual_pending SET status='TRIGGERED', updated_ts=? WHERE id=? AND status='OPEN'",
                (now, v.id),
            )
            processed.append(int(v.id))
            # OCO: cancel siblings
            if v.oco_group:
                cur.execute(
                    "UPDATE virtual_pending SET status='CANCELLED', comment=COALESCE(comment,'')||' [oco_peer_triggered]', updated_ts=? WHERE status='OPEN' AND oco_group=? AND id<>?",
                    (now, v.oco_group, v.id),
                )
        else:
            # Keep it OPEN; optionally mark attempt in comment
            cur.execute(
                "UPDATE virtual_pending SET comment=COALESCE(comment,'')||' [trigger_error]', updated_ts=? WHERE id=?",
                (now, v.id),
            )

    con.commit()
    con.close()
    return processed
