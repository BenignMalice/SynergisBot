# =====================================
# domain/models.py
# =====================================
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class TradeRec:
    direction: str
    entry: float
    sl: float
    tp: float
    rr: Optional[float]
    regime: str
    reasoning: str


@dataclass
class ExecResult:
    ok: bool
    message: str
    ticket: Optional[int]
    position: Optional[int]
    entry: Optional[float]
    sl: Optional[float]
    tp: Optional[float]
    lot: Optional[float]
