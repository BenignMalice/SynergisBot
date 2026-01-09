# =====================================
# domain/rules.py
# =====================================
from __future__ import annotations
import numpy as np
import re

_WORDS = re.compile(r"[a-z]+")


def build_confidence(tech: dict) -> int:
    """
    Return 1..99. Heavier weighting to EMA alignment, ADX strength, pattern/structure,
    and a mild session/regime fit. Keeps your same signature so callers don’t change.
    """
    # Inputs (with forgiveness)
    adx = float(tech.get("adx", np.nan) or 0.0)
    close = float(tech.get("close", np.nan) or 0.0)
    ema20 = float(tech.get("ema_20", np.nan) or 0.0)
    ema50 = float(tech.get("ema_50", np.nan) or 0.0)
    ema200 = float(tech.get("ema_200", np.nan) or 0.0)
    atr = float(tech.get("atr_14", np.nan) or 0.0)
    bbw = float(tech.get("bb_width", np.nan) or 0.0)
    regime = str(tech.get("regime", "RANGE")).upper()
    session = str(tech.get("session", "Mid"))

    ema_align = 1.0 if (close and ema200 and close > ema200) else 0.0
    trendiness = 0.0
    if not np.isnan(adx):
        # Scale ADX 18..35 → 0..1
        trendiness = max(0.0, min(1.0, (adx - 18.0) / (35.0 - 18.0)))

    # Pattern/structure proxies (simple but helpful)
    pattern_ok = 1.0 if (close and ema20 and close > ema20) else 0.0
    structure = 1.0 if (ema20 and ema50 and ema20 > ema50) else 0.4

    # Session fit bias
    session_fit = 0.6
    if regime in ("TREND", "VOLATILE") and session in ("London", "NewYork"):
        session_fit = 1.0
    elif regime == "RANGE" and session in ("Asia", "Mid"):
        session_fit = 1.0

    # Volatility fitness: very narrow bands (range), very wide (breakouts)
    vol_fit = 0.7
    if bbw and not np.isnan(bbw):
        if regime == "RANGE":
            # narrower bands better up to ~1.2% of price
            vol_fit = 1.0 - max(0.0, min(1.0, (bbw - 0.008) / (0.02 - 0.008)))
        elif regime in ("TREND", "VOLATILE"):
            vol_fit = max(0.0, min(1.0, (bbw - 0.008) / (0.03 - 0.008)))

    # Weighted sum → 0..1
    s = (
        0.20 * ema_align
        + 0.15 * trendiness
        + 0.15 * pattern_ok
        + 0.10 * session_fit
        + 0.10 * vol_fit
        + 0.30 * structure
    )
    # Map to 1..99 with guardrails
    return int(max(1, min(99, round(1 + s * 98))))


# domain/rules.py
import re

_WORDS = re.compile(r"[a-z]+")


def normalise_direction(val) -> str:
    """
    Map various direction phrases to one of: 'buy', 'sell', 'hold'.
    Accepts LONG/SHORT, BUY/SELL, bull/bear variants, and neutral terms.
    Uses word-boundary matching to avoid accidental substring matches.
    """
    s = str(val or "").strip().lower()
    if not s:
        return "hold"

    # Tokenize to plain words so things like 'sell_limit' → ['sell', 'limit']
    tokens = _WORDS.findall(s)
    joined = " ".join(tokens)

    # Exact simple cases
    if joined in {"buy", "sell", "hold"}:
        return joined

    # Positive / long side
    if re.search(r"\b(long|buy|bull|bullish)\b", joined):
        return "buy"

    # Negative / short side
    if re.search(r"\b(short|sell|bear|bearish)\b", joined):
        return "sell"

    # Neutral / no-trade
    if re.search(r"\b(hold|flat|wait|idle|none|neutral)\b", joined):
        return "hold"

    # Default to hold if we can't tell
    return "hold"
