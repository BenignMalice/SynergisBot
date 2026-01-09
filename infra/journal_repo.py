# =====================================
# infra/journal_repo.py
# =====================================
from __future__ import annotations

import csv
import json
import logging
import sqlite3
import threading
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple

from config import settings

logger = logging.getLogger(__name__)


def _now_ts() -> int:
    return int(time.time())


def _iso(ts: int) -> str:
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts)))
    except Exception:
        return str(ts)


def _to_json(v: Any) -> str:
    try:
        if is_dataclass(v):
            v = asdict(v)
        return json.dumps(v, default=str, ensure_ascii=False)
    except Exception:
        return json.dumps({"_repr": repr(v)}, ensure_ascii=False)


def _to_float(x: Any) -> Optional[float]:
    try:
        return float(x) if x is not None else None
    except Exception:
        return None


def _to_int(x: Any) -> Optional[int]:
    try:
        return int(x) if x is not None else None
    except Exception:
        return None


def _parse_dd_tiers(val: Any) -> List[Tuple[float, float]]:
    """
    Accepts either:
      - list of (threshold_pct, factor) pairs, e.g. [(0.05,0.75),(0.10,0.5)]
      - string "0.05:0.75,0.10:0.5"
    Returns a *sorted* list by threshold ascending.
    """
    if isinstance(val, (list, tuple)):
        try:
            pairs = [(float(a), float(b)) for a, b in val]
            return sorted(pairs, key=lambda t: t[0])
        except Exception:
            return []
    if isinstance(val, str):
        out: List[Tuple[float, float]] = []
        for chunk in val.split(","):
            if ":" in chunk:
                a, b = chunk.split(":", 1)
                try:
                    out.append((float(a.strip()), float(b.strip())))
                except Exception:
                    pass
        return sorted(out, key=lambda t: t[0])
    return []


class JournalRepo:
    """
    Structured journal with SQLite storage + optional CSV mirroring.

    Tables:
      • trades(ticket PRIMARY KEY): core lifecycle
      • events(id AUTOINCREMENT): general events (+ optional extended columns)
      • equity(ts PRIMARY KEY): equity/balance snapshots

    Extended events columns (optional; auto-migrated if missing):
      lot, position, balance, equity, confidence, regime, rr, notes
    """

    _EVENTS_BASE_COLS = [
        "ts",
        "event",
        "ticket",
        "symbol",
        "side",
        "price",
        "sl",
        "tp",
        "volume",
        "pnl",
        "r_multiple",
        "reason",
        "extra",
    ]
    _EVENTS_EXT_COLS = [
        "lot",
        "position",
        "balance",
        "equity",
        "confidence",
        "regime",
        "rr",
        "notes",
        "plan_id",  # NEW: Link to auto-execution plan
    ]

    def __init__(
        self,
        db_path: Optional[str] = None,
        csv_path: Optional[str] = None,
        csv_enable: Optional[bool] = None,
    ):
        base_dir = Path(getattr(settings, "DATA_DIR", "./data"))
        base_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = Path(
            db_path or getattr(settings, "JOURNAL_DB_PATH", base_dir / "journal.sqlite")
        )
        self.csv_path = Path(
            csv_path
            or getattr(settings, "JOURNAL_CSV_PATH", base_dir / "journal_events.csv")
        )
        self.csv_enable = bool(
            csv_enable
            if csv_enable is not None
            else getattr(settings, "JOURNAL_CSV_ENABLE", True)
        )

        # Use RLock to avoid self-deadlocks during nested schema calls
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA synchronous = NORMAL;")
        self._conn.execute("PRAGMA foreign_keys = ON;")

        self._ensure_schema()
        self._events_cols = self._get_table_columns("events")  # cache list of cols

    # --------- schema ---------
    def _get_table_columns(self, table: str) -> List[str]:
        """
        Return column names for a given table.
        Do NOT acquire self._lock here (callers may already hold it).
        """
        try:
            cur = self._conn.execute(f"PRAGMA table_info({table});")
            return [r[1] for r in cur.fetchall()]
        except Exception:
            return []

    def _ensure_schema(self):
        with self._lock, self._conn:
            # trades
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    ticket        INTEGER PRIMARY KEY,
                    symbol        TEXT NOT NULL,
                    side          TEXT CHECK(side IN ('BUY','SELL')) NOT NULL,
                    entry_price   REAL NOT NULL,
                    sl            REAL,
                    tp            REAL,
                    volume        REAL,
                    strategy      TEXT,
                    regime        TEXT,
                    chat_id       INTEGER,
                    opened_ts     INTEGER NOT NULL,
                    closed_ts     INTEGER,
                    exit_price    REAL,
                    close_reason  TEXT,
                    pnl           REAL,
                    r_multiple    REAL,
                    duration_sec  INTEGER
                );
                """
            )
            # events (base)
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts           INTEGER NOT NULL,
                    event        TEXT NOT NULL,
                    ticket       INTEGER,
                    symbol       TEXT,
                    side         TEXT,
                    price        REAL,
                    sl           REAL,
                    tp           REAL,
                    volume       REAL,
                    pnl          REAL,
                    r_multiple   REAL,
                    reason       TEXT,
                    extra        TEXT,
                    FOREIGN KEY(ticket) REFERENCES trades(ticket) ON DELETE SET NULL
                );
                """
            )
            # equity
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS equity (
                    ts      INTEGER PRIMARY KEY,
                    balance REAL,
                    equity  REAL
                );
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_event ON events(event);"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_ticket ON events(ticket);"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_equity_ts ON equity(ts);"
            )

            # --- extended columns (auto-migrate if missing) ---
            cols = self._get_table_columns("events")
            missing = [c for c in self._EVENTS_EXT_COLS if c not in cols]
            for c in missing:
                # NULL-able by default
                self._conn.execute(
                    f"ALTER TABLE events ADD COLUMN {c} "
                    f"{'REAL' if c in ('lot','balance','equity','rr') else ('INTEGER' if c in ('position','confidence') else 'TEXT')};"
                )
            
            # --- Add plan_id to trades table (migration) ---
            trades_cols = self._get_table_columns("trades")
            if "plan_id" not in trades_cols:
                self._conn.execute("ALTER TABLE trades ADD COLUMN plan_id TEXT;")
                self._conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_plan_id ON trades(plan_id);")

    # --------- ensure filesystem ---------
    def ensure(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self._ensure_schema()
        self._events_cols = self._get_table_columns("events")

    # --------- CSV mirroring ---------
    def _append_csv(self, row: Dict[str, Any]) -> None:
        try:
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            write_header = not self.csv_path.exists()
            # Flatten non-serializable values
            flat = {
                k: (
                    json.dumps(v, ensure_ascii=False)
                    if isinstance(v, (dict, list))
                    else v
                )
                for k, v in row.items()
            }
            fieldnames = sorted(flat.keys())
            with self.csv_path.open("a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                if write_header:
                    w.writeheader()
                # Ensure all keys exist for current header
                safe_row = {k: flat.get(k) for k in fieldnames}
                w.writerow(safe_row)
        except Exception:
            # Never block journaling on CSV problems
            pass

    # --------- generic events ---------
    def _insert_event_row(self, row: dict):
        """
        Insert a base row into events and stash everything else into `extra` JSON.
        Keeps schema stable; no ALTER TABLE required.
        """
        base = {
            "ts": row.get("ts"),
            "event": row.get("event"),
            "ticket": row.get("ticket"),
            "symbol": row.get("symbol"),
            "side": row.get("side"),
            "price": row.get("price"),
            "sl": row.get("sl"),
            "tp": row.get("tp"),
            "volume": row.get("volume"),
            "pnl": row.get("pnl"),
            "r_multiple": row.get("r_multiple"),
            "reason": row.get("reason"),
        }
        # Extract plan_id before building extra (for direct column storage)
        plan_id = row.get("plan_id")
        # everything not in base goes to extra (except plan_id if we store it in column)
        extra_obj = {k: v for k, v in row.items() if k not in base and k != "event" and k != "plan_id"}
        # Still include plan_id in extra for backward compatibility
        if plan_id:
            extra_obj["plan_id"] = plan_id
        extra_json = _to_json(extra_obj) if extra_obj else None

        # Check if plan_id column exists in events table
        events_cols = self._get_table_columns("events")
        has_plan_id_col = "plan_id" in events_cols
        
        if has_plan_id_col:
            sql = (
                "INSERT INTO events (ts,event,ticket,symbol,side,price,sl,tp,volume,pnl,r_multiple,reason,extra,plan_id) "
                "VALUES (:ts,:event,:ticket,:symbol,:side,:price,:sl,:tp,:volume,:pnl,:r_multiple,:reason,:extra,:plan_id)"
            )
            params = {**base, "extra": extra_json, "plan_id": plan_id}
        else:
            sql = (
                "INSERT INTO events (ts,event,ticket,symbol,side,price,sl,tp,volume,pnl,r_multiple,reason,extra) "
                "VALUES (:ts,:event,:ticket,:symbol,:side,:price,:sl,:tp,:volume,:pnl,:r_multiple,:reason,:extra)"
            )
            params = {**base, "extra": extra_json}
        
        with self._lock, self._conn:
            self._conn.execute(sql, params)
            self._conn.commit()

    def add_event(self, event: str, **data):
        row = dict(data or {})
        row["event"] = event
        row.setdefault("ts", _now_ts())

        if "side" not in row:
            side_alias = row.get("direction") or row.get("dir")
            row["side"] = side_alias if side_alias is not None else None

        # Write to DB
        self._insert_event_row(row)

        # CSV mirror (optional)
        if self.csv_enable:
            try:
                base_cols = [
                    "ts",
                    "event",
                    "ticket",
                    "symbol",
                    "side",
                    "price",
                    "sl",
                    "tp",
                    "volume",
                    "pnl",
                    "r_multiple",
                    "reason",
                ]
                base = {k: row.get(k) for k in base_cols}
                extras = {
                    k: v for k, v in row.items() if k not in base and k != "event"
                }
                flat = {**base, **extras}
                self._append_csv(flat)
            except Exception:
                pass

    # Aliases
    def log_event(self, event: str, **payload):
        self.add_event(event, **payload)

    def add(self, event: str, **payload):
        self.add_event(event, **payload)

    def write_event(self, event: str, **payload):
        self.add_event(event, **payload)

    def write(self, data: Dict[str, Any]):
        data = dict(data or {})
        event = str(data.pop("event", "generic"))
        self.add_event(event, **data)

    # --------- compatibility: write_exec / journal views ---------
    def write_exec(self, row: Dict[str, Any]) -> None:
        """
        Expected keys (optional except symbol/side/entry): ts, symbol, side, entry, sl, tp, lot, ticket,
        position, balance, equity, confidence, regime, rr, notes, plan_id
        """
        self.ensure()

        ts = _to_int(row.get("ts")) or _now_ts()
        symbol = str(row.get("symbol") or "")
        side = str(row.get("side") or "").upper()
        entry = _to_float(row.get("entry"))
        sl = _to_float(row.get("sl"))
        tp = _to_float(row.get("tp"))
        lot = _to_float(row.get("lot") or row.get("volume"))
        ticket = _to_int(row.get("ticket"))
        position = _to_int(row.get("position"))
        balance = _to_float(row.get("balance"))
        equity = _to_float(row.get("equity"))
        confidence = _to_int(row.get("confidence"))
        regime = row.get("regime")
        rr = _to_float(row.get("rr"))
        notes = row.get("notes")
        plan_id = row.get("plan_id")  # NEW: Auto-execution plan ID

        if (
            ticket is not None
            and entry is not None
            and symbol
            and side in ("BUY", "SELL")
        ):
            with self._lock, self._conn:
                # Check if plan_id column exists (for migration compatibility)
                trades_cols = self._get_table_columns("trades")
                if "plan_id" in trades_cols:
                    self._conn.execute(
                        """
                        INSERT OR REPLACE INTO trades
                        (ticket, symbol, side, entry_price, sl, tp, volume, regime, opened_ts, plan_id)
                        VALUES (:ticket, :symbol, :side, :entry_price, :sl, :tp, :volume, :regime, :opened_ts, :plan_id)
                        """,
                        {
                            "ticket": ticket,
                            "symbol": symbol,
                            "side": side,
                            "entry_price": entry,
                            "sl": sl,
                            "tp": tp,
                            "volume": lot,
                            "regime": regime,
                            "opened_ts": ts,
                            "plan_id": plan_id,
                        },
                    )
                else:
                    # Fallback for old schema
                    self._conn.execute(
                        """
                        INSERT OR REPLACE INTO trades
                        (ticket, symbol, side, entry_price, sl, tp, volume, regime, opened_ts)
                        VALUES (:ticket, :symbol, :side, :entry_price, :sl, :tp, :volume, :regime, :opened_ts)
                        """,
                        {
                            "ticket": ticket,
                            "symbol": symbol,
                            "side": side,
                            "entry_price": entry,
                            "sl": sl,
                            "tp": tp,
                            "volume": lot,
                            "regime": regime,
                            "opened_ts": ts,
                        },
                    )

        extra: Dict[str, Any] = {
            "position": position,
            "balance": balance,
            "equity": equity,
            "confidence": confidence,
            "regime": regime,
            "rr": rr,
            "notes": notes,
            "plan_id": plan_id,  # NEW: Include plan_id in extra for events table
        }
        self.add_event(
            "trade_exec",
            ts=ts,
            ticket=ticket,
            symbol=symbol,
            side=side,
            price=entry,
            sl=sl,
            tp=tp,
            volume=lot,
            reason="market",
            extra=extra,
        )

        # NEW: auto-snapshot equity if provided
        if balance is not None or equity is not None:
            try:
                self.record_equity_snapshot(balance=balance, equity=equity, ts=ts)
            except Exception:
                pass

    def _rows_from_events(
        self, where_sql: str, args: list, limit: int
    ) -> List[Dict[str, Any]]:
        # Fetch with base + (optionally) extended cols; extras decoded for fallback
        cols = self._get_table_columns("events")
        select_cols = [
            "ts",
            "event",
            "ticket",
            "symbol",
            "side",
            "price",
            "sl",
            "tp",
            "volume",
            "pnl",
            "r_multiple",
            "reason",
            "extra",
        ]
        # If extended exist, include them
        for c in self._EVENTS_EXT_COLS:
            if c in cols:
                select_cols.append(c)

        sql = (
            f"SELECT {','.join(select_cols)} FROM events WHERE ({where_sql}) "
            "ORDER BY ts DESC LIMIT ?"
        )
        args2 = list(args) + [int(limit)]
        with self._lock, self._conn:
            cur = self._conn.execute(sql, args2)
            rows = cur.fetchall()

        # Map column indexes
        idx = {name: i for i, name in enumerate(select_cols)}
        out: List[Dict[str, Any]] = []
        for r in rows:
            extra_obj: Dict[str, Any] = {}
            raw_extra = r[idx["extra"]] if "extra" in idx else None
            if raw_extra:
                try:
                    extra_obj = json.loads(raw_extra)
                except Exception:
                    extra_obj = {"_raw_extra": raw_extra}

            def _pick_extended(name, fallback=None):
                if name in idx and r[idx[name]] is not None:
                    return r[idx[name]]
                return extra_obj.get(name, fallback)

            out.append(
                {
                    "ts": _iso(r[idx["ts"]]),
                    "symbol": r[idx["symbol"]],
                    "side": (r[idx["side"]] or "").upper() if r[idx["side"]] else "",
                    "entry": _to_float(r[idx["price"]]),
                    "sl": _to_float(r[idx["sl"]]),
                    "tp": _to_float(r[idx["tp"]]),
                    "lot": _to_float(_pick_extended("lot", r[idx["volume"]])),
                    "ticket": _to_int(r[idx["ticket"]]),
                    "position": _to_int(_pick_extended("position")),
                    "balance": _to_float(_pick_extended("balance")),
                    "equity": _to_float(_pick_extended("equity")),
                    "confidence": _to_int(_pick_extended("confidence")),
                    "regime": _pick_extended("regime"),
                    "rr": _to_float(_pick_extended("rr", r[idx["r_multiple"]])),
                    "notes": _pick_extended("notes", r[idx["reason"]]),
                }
            )

        return out

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        self.ensure()
        where = "event IN ('trade_exec','trade_open')"
        return self._rows_from_events(where, [], limit)

    def by_symbol(self, symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
        self.ensure()
        where = "symbol = ? AND event IN ('trade_exec','trade_open')"
        return self._rows_from_events(where, [symbol], limit)

    # --------- equity snapshots & drawdown ---------
    def record_equity_snapshot(
        self,
        *,
        balance: Optional[float],
        equity: Optional[float],
        ts: Optional[int] = None,
    ) -> None:
        """
        Store (balance, equity) snapshot. Either may be None; we store what's given.
        Upserts by timestamp to avoid duplicates.
        """
        if balance is None and equity is None:
            return
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO equity (ts, balance, equity)
                VALUES (:ts, :balance, :equity)
                ON CONFLICT(ts) DO UPDATE SET
                    balance=COALESCE(excluded.balance, balance),
                    equity=COALESCE(excluded.equity, equity)
                """,
                {
                    "ts": int(ts or _now_ts()),
                    "balance": _to_float(balance),
                    "equity": _to_float(equity),
                },
            )
        # Also store an event for visibility (optional)
        try:
            self.add_event(
                "equity_snapshot",
                ts=int(ts or _now_ts()),
                pnl=None,
                reason="snapshot",
                extra={"balance": balance, "equity": equity},
            )
        except Exception:
            pass

    def _equity_series(self, lookback_days: int) -> List[Tuple[int, Optional[float]]]:
        """
        Return list of (ts, equity) within lookback. Falls back to balance if equity is NULL.
        """
        horizon = _now_ts() - int(lookback_days * 86400)
        with self._lock, self._conn:
            cur = self._conn.execute(
                "SELECT ts, COALESCE(equity, balance) AS eq FROM equity WHERE ts >= ? ORDER BY ts ASC",
                (int(horizon),),
            )
            rows = cur.fetchall()
        return [(int(ts), (None if eq is None else float(eq))) for ts, eq in rows]

    @staticmethod
    def _max_drawdown_pct(values: List[float]) -> Tuple[float, float, float]:
        """
        Compute max drawdown (%), returning (max_dd_pct, peak, trough).
        If <2 points or invalid data, returns (0.0, last, last).
        """
        clean = [float(v) for v in values if v is not None]
        if len(clean) < 2:
            last = clean[-1] if clean else 0.0
            return 0.0, last, last

        peak = clean[0]
        trough = clean[0]
        max_dd = 0.0
        local_peak = clean[0]

        for v in clean[1:]:
            if v > local_peak:
                local_peak = v
                trough = v
            dd = local_peak - v
            if dd > max_dd:
                max_dd = dd
                peak = local_peak
                trough = v

        if peak <= 0:
            return 0.0, peak, trough
        dd_pct = max(0.0, max_dd / peak)  # 0.12 == 12%
        return dd_pct, peak, trough

    def risk_scale_from_drawdown(
        self,
        *,
        lookback_days: int = None,
        tiers: Optional[List[Tuple[float, float]]] = None,
        min_factor: Optional[float] = None,
        max_factor: Optional[float] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Piecewise risk scaling from recent max drawdown.
        """
        lb = (
            int(lookback_days)
            if lookback_days is not None
            else int(getattr(settings, "RISK_DD_LOOKBACK_DAYS", 180))
        )
        tiers_cfg = tiers
        if tiers_cfg is None:
            tiers_cfg = _parse_dd_tiers(getattr(settings, "RISK_DD_TIERS", "")) or [
                (0.05, 0.75),
                (0.10, 0.50),
                (0.15, 0.25),
            ]
        f_min = (
            float(getattr(settings, "RISK_DD_MIN_FACTOR", 0.20))
            if min_factor is None
            else float(min_factor)
        )
        f_max = (
            float(getattr(settings, "RISK_DD_MAX_FACTOR", 1.00))
            if max_factor is None
            else float(max_factor)
        )

        series = self._equity_series(lb)
        # FIX: unpack (ts, equity) tuples
        vals = [v for _, v in series if v is not None]
        if len(vals) < 2:
            return 1.0, {
                "max_dd_pct": 0.0,
                "factor": 1.0,
                "tiers": tiers_cfg,
                "f_min": f_min,
                "f_max": f_max,
            }

        dd_pct, peak, trough = self._max_drawdown_pct(vals)
        factor = 1.0
        for thr, f in tiers_cfg:
            if dd_pct >= float(thr):
                factor = min(factor, float(f))

        # Clamp to global min/max
        factor = max(f_min, min(factor, f_max))

        info = {
            "max_dd_pct": float(dd_pct * 100.0),  # as %
            "peak": float(peak),
            "trough": float(trough),
            "last_equity": float(vals[-1]) if vals else None,
            "tiers": tiers_cfg,
            "f_min": f_min,
            "f_max": f_max,
        }
        return float(factor), info

    # --------- summaries ---------
    def count_events(
        self, event: Optional[str] = None, since_ts: Optional[int] = None
    ) -> int:
        q = "SELECT COUNT(1) FROM events WHERE 1=1"
        args: List[Any] = []
        if event:
            q += " AND event = ?"
            args.append(event)
        if since_ts:
            q += " AND ts >= ?"
            args.append(int(since_ts))
        with self._lock, self._conn:
            cur = self._conn.execute(q, args)
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def get_trades_summary(self) -> list[dict]:
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                SELECT ticket, symbol, side, entry_price, exit_price, pnl, r_multiple, (closed_ts - opened_ts) AS duration_sec
                  FROM trades
                 WHERE closed_ts IS NOT NULL
                 ORDER BY closed_ts DESC
                """
            )
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    
    def get_open_trades(self) -> list[dict]:
        """Get all currently open trades (closed_ts IS NULL)"""
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                SELECT ticket, symbol, side, entry_price, sl, tp, volume, 
                       strategy, regime, opened_ts
                  FROM trades
                 WHERE closed_ts IS NULL
                 ORDER BY opened_ts DESC
                """
            )
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    
    def _extract_strategy_name(self, ticket: int) -> Optional[str]:
        """
        Extract strategy name from trade record.
        
        Checks:
        1. strategy field in trades table (primary)
        2. events table notes field for [strategy:name] pattern (for auto-execution plans)
        """
        try:
            with self._lock, self._conn:
                # First, check strategy field in trades table
                cur = self._conn.execute(
                    "SELECT strategy FROM trades WHERE ticket = ?", (ticket,)
                )
                row = cur.fetchone()
                if row and row[0]:
                    strategy = str(row[0]).strip()
                    if strategy:
                        return strategy
                
                # Fallback: Check events table for notes with [strategy:name] pattern
                cur = self._conn.execute(
                    """
                    SELECT extra FROM events 
                    WHERE ticket = ? AND event IN ('trade_exec', 'trade_open')
                    ORDER BY ts DESC LIMIT 1
                    """,
                    (ticket,)
                )
                row = cur.fetchone()
                if row and row[0]:
                    try:
                        extra = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                        notes = extra.get("notes", "") if isinstance(extra, dict) else ""
                        if notes and "[strategy:" in notes:
                            import re
                            match = re.search(r'\[strategy:([^\]]+)\]', notes)
                            if match:
                                return match.group(1).strip()
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Failed to extract strategy name for ticket {ticket}: {e}")
        
        return None
    
    def close_trade(
        self, 
        ticket: int, 
        exit_price: float, 
        close_reason: str, 
        pnl: float = None, 
        r_multiple: float = None,
        closed_ts: int = None
    ) -> bool:
        """
        Update a trade to closed status
        
        Returns:
            True if trade was closed successfully, False if trade not found
        """
        import time
        if closed_ts is None:
            closed_ts = int(time.time())
        
        with self._lock, self._conn:
            # Get trade details for performance tracking
            cur = self._conn.execute(
                """
                SELECT opened_ts, symbol, entry_price, strategy 
                FROM trades WHERE ticket = ?
                """,
                (ticket,)
            )
            row = cur.fetchone()
            if not row:
                logger.debug(f"Trade {ticket} not found in database (already closed or never logged)")
                return False
            
            opened_ts, symbol, entry_price, strategy_field = row
            duration_sec = closed_ts - opened_ts if opened_ts else None
            
            # Update the trade
            self._conn.execute(
                """
                UPDATE trades 
                SET closed_ts = ?,
                    exit_price = ?,
                    close_reason = ?,
                    pnl = ?,
                    r_multiple = ?,
                    duration_sec = ?
                WHERE ticket = ?
                """,
                (closed_ts, exit_price, close_reason, pnl, r_multiple, duration_sec, ticket)
            )
            self._conn.commit()
            logger.debug(f"Trade {ticket} marked as closed in database")
        
        # Phase 0.5: Record to performance tracker (outside lock to avoid blocking)
        try:
            strategy_name = strategy_field or self._extract_strategy_name(ticket)
            if strategy_name and pnl is not None:
                from infra.strategy_performance_tracker import StrategyPerformanceTracker
                tracker = StrategyPerformanceTracker()
                
                # Determine result from close_reason and pnl
                if close_reason and "TP" in close_reason.upper():
                    result = "win"
                elif close_reason and "SL" in close_reason.upper():
                    result = "loss"
                elif pnl > 0:
                    result = "win"
                elif pnl < 0:
                    result = "loss"
                else:
                    result = "breakeven"
                
                # Format timestamps
                entry_time = _iso(opened_ts) if opened_ts else None
                exit_time = _iso(closed_ts) if closed_ts else None
                
                tracker.record_trade(
                    strategy_name=strategy_name,
                    symbol=str(symbol) if symbol else "UNKNOWN",
                    result=result,
                    pnl=float(pnl),
                    rr=float(r_multiple) if r_multiple is not None else None,
                    entry_price=float(entry_price) if entry_price is not None else None,
                    exit_price=float(exit_price) if exit_price is not None else None,
                    entry_time=entry_time,
                    exit_time=exit_time
                )
                logger.debug(f"Recorded trade {ticket} to performance tracker for strategy {strategy_name}")
        except Exception as e:
            logger.warning(f"Failed to record trade {ticket} to performance tracker: {e}", exc_info=True)
            # Don't fail trade close if tracking fails
        
        return True


# === Phase4: lightweight journal note helper ===
def note(event: str, payload: dict):
    try:
        # This is a stub; real implementation can append to CSV/SQLite if available
        pass
    except Exception:
        pass
