# =====================================
# infra/memory_store.py
# =====================================
from __future__ import annotations

import json, os, time, math, sqlite3
from typing import Any, Dict, List, Optional, Tuple
import threading

_LOCK = threading.Lock()


def _safe_f(x, d=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(d)


def _one_hot_regime(regime: str) -> List[float]:
    r = (regime or "").upper()
    keys = ["TREND", "RANGE", "VOLATILE"]
    return [1.0 if r == k else 0.0 for k in keys]


def _vectorize(snapshot: Dict[str, Any]) -> List[float]:
    """
    Compact numeric embedding from your snapshot (+ light guards against None).
    Extend as you wish; keep ordering stable.
    """
    adx = _safe_f(snapshot.get("adx"), 0.0)
    atr = _safe_f(snapshot.get("atr_14"), 0.0)
    bbw = _safe_f(snapshot.get("bb_width"), 0.0)
    slope = _safe_f(snapshot.get("ema_slope_h1"), 0.0)
    rsi = _safe_f(snapshot.get("rsi_14"), 50.0)
    pat = _safe_f(snapshot.get("pattern_bias"), 0.0)

    # basic normalization guards
    def nz(x, s=1.0):
        try:
            xv = float(x)
            return xv / s if s != 0 else xv
        except:
            return 0.0

    feat = [
        nz(adx, 100.0),
        nz(atr, max(atr, 1.0)),  # self-scale if needed
        nz(bbw, 1.0),
        nz(slope, max(abs(slope), 1e-4)),
        nz(rsi, 100.0),
        nz(pat, 5.0),
    ]
    # regime one-hot (if present in snapshot)
    feat += _one_hot_regime(str(snapshot.get("regime") or ""))
    # session as light indicator
    sess = str(snapshot.get("session") or "").upper()
    feat += [
        1.0 if "US" in sess else 0.0,
        1.0 if "LDN" in sess else 0.0,
        1.0 if "ASIA" in sess else 0.0,
    ]
    return feat


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    import math

    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class MemoryStore:
    """
    SQLite-backed simple vector store for per-symbol past cases.
    - add_reco(...) to save snapshot+plan (optionally ticket)
    - add_outcome(...) to attach realized outcome
    - retrieve(symbol, snapshot, k) → K nearest prior cases
    """

    def __init__(self, db_path: str):
        self.db_path = db_path or "memory_store.sqlite"
        self._ensure()

    def _ensure(self):
        (
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            if os.path.dirname(self.db_path)
            else None
        )
        with _LOCK, sqlite3.connect(self.db_path) as cx:
            cx.execute(
                """
            CREATE TABLE IF NOT EXISTS cases(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts INTEGER NOT NULL,
              symbol TEXT NOT NULL,
              tf TEXT,
              regime TEXT,
              vec TEXT NOT NULL,            -- JSON array of floats
              snapshot_json TEXT NOT NULL,  -- JSON
              plan_json TEXT,               -- JSON (recommendation)
              ticket TEXT,                  -- MT5 ticket if known
              outcome_json TEXT             -- JSON (pnl, duration, hit_tp/sl, etc.)
            )"""
            )
            cx.execute(
                "CREATE INDEX IF NOT EXISTS idx_cases_symbol_ts ON cases(symbol, ts)"
            )
            cx.commit()

    def add_reco(
        self,
        *,
        symbol: str,
        snapshot: Dict[str, Any],
        plan: Dict[str, Any] | None,
        tf: str = "M5",
        ticket: str | None = None,
    ) -> int:
        vec = json.dumps(_vectorize(snapshot))
        payload_snapshot = dict(snapshot or {})
        if "regime" not in payload_snapshot:
            payload_snapshot["regime"] = str((plan or {}).get("regime") or "")
        with _LOCK, sqlite3.connect(self.db_path) as cx:
            cur = cx.cursor()
            cur.execute(
                "INSERT INTO cases(ts, symbol, tf, regime, vec, snapshot_json, plan_json, ticket, outcome_json) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    int(time.time()),
                    symbol,
                    tf,
                    str(payload_snapshot.get("regime") or ""),
                    vec,
                    json.dumps(payload_snapshot, ensure_ascii=False),
                    json.dumps(plan or {}, ensure_ascii=False),
                    str(ticket) if ticket else None,
                    None,
                ),
            )
            cid = int(cur.lastrowid)
            cx.commit()
            return cid

    def add_outcome(
        self,
        *,
        case_id: int | None = None,
        symbol: str | None = None,
        ticket: str | None = None,
        outcome: Dict[str, Any],
    ):
        with _LOCK, sqlite3.connect(self.db_path) as cx:
            if case_id is not None:
                cx.execute(
                    "UPDATE cases SET outcome_json=? WHERE id=?",
                    (json.dumps(outcome, ensure_ascii=False), int(case_id)),
                )
            elif ticket:
                cx.execute(
                    "UPDATE cases SET outcome_json=? WHERE ticket=? ORDER BY ts DESC LIMIT 1",
                    (json.dumps(outcome, ensure_ascii=False), str(ticket)),
                )
            elif symbol:
                # fallback: update the most recent case for this symbol
                cx.execute(
                    "UPDATE cases SET outcome_json=? WHERE symbol=? ORDER BY ts DESC LIMIT 1",
                    (json.dumps(outcome, ensure_ascii=False), str(symbol)),
                )
            cx.commit()

    def retrieve(
        self,
        symbol: str,
        snapshot: Dict[str, Any],
        k: int = 3,
        tf: Optional[str] = None,
        regime: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        qv = _vectorize(snapshot)
        rows: List[Tuple[int, str, str, str, str, str, str]] = []
        with _LOCK, sqlite3.connect(self.db_path) as cx:
            cur = cx.cursor()
            base = "SELECT id, ts, symbol, tf, regime, vec, snapshot_json, plan_json, outcome_json FROM cases WHERE symbol=?"
            args = [symbol]
            if tf:
                base += " AND (tf IS NULL OR tf=?)"
                args.append(tf)
            if regime:
                base += " AND (regime IS NULL OR regime=?)"
                args.append(regime)
            base += " ORDER BY ts DESC LIMIT 500"  # cap scan
            cur.execute(base, tuple(args))
            rows = cur.fetchall()

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for r in rows:
            _id, _ts, _sym, _tf, _rg, vec_s, snap_s, plan_s, out_s = r
            try:
                v = json.loads(vec_s or "[]")
                sc = _cosine(qv, v)
                scored.append(
                    (
                        sc,
                        {
                            "id": int(_id),
                            "ts": int(_ts),
                            "symbol": _sym,
                            "tf": _tf,
                            "regime": _rg,
                            "snapshot": json.loads(snap_s or "{}"),
                            "plan": json.loads(plan_s or "{}"),
                            "outcome": json.loads(out_s) if out_s else None,
                            "similarity": float(sc),
                        },
                    )
                )
            except Exception:
                continue
        scored.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in scored[: max(1, k)]]
