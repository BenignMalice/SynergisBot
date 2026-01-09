# =====================================
# infra/postmortem.py
# =====================================
from __future__ import annotations
from typing import Dict, Any


def build_postmortem_text(
    symbol: str, trade: Dict[str, Any], analysis: Dict[str, Any]
) -> str:
    """
    trade: row written by JournalRepo.write_exec(...) or your close payload
    analysis: LAST_REC[(chat_id, symbol)] snapshot: rec, regime, strategy, confidence, rr, etc.
    """
    rec = (analysis or {}).get("rec", {}) or {}
    rr = rec.get("rr")
    direction = rec.get("direction")
    strategy = analysis.get("strategy")
    conf = analysis.get("confidence")
    outcome = trade.get("outcome") or {}
    pnl = outcome.get("pnl") or trade.get("pnl")
    hit = outcome.get("hit")  # "TP"/"SL"/"MANUAL"
    dur = outcome.get("duration_min", "—")
    header = f"📘 Post-mortem — {symbol}\n"
    core = (
        f"Side: {direction} | Strategy: {strategy} | RR@plan: {rr}\n"
        f"Confidence: {conf}/99 | Outcome: {hit or '—'} | PnL: {pnl}\n"
        f"Duration: {dur} min\n"
    )
    prompts = (
        "\nQuick notes:\n"
        "1) Setup quality (1-5): \n"
        "2) What invalidated/validated the idea: \n"
        "3) Did S/R bands behave as expected? \n"
        "4) One thing to keep/avoid next time: \n"
    )
    return header + core + prompts
