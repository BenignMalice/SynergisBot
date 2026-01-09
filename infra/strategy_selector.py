# =====================================
# infra/strategy_selector.py
# =====================================
from __future__ import annotations  # optional but recommended
import json
import os
import time
import threading
import logging
from typing import Any, Dict, List, Tuple, Optional

from config import settings

_LOCK = threading.RLock()

logger = logging.getLogger("infra.strategy_selector")
logger.setLevel(logging.DEBUG)
logger.propagate = True

"""
Strategy selection module (stateful + bandit).

What this does now:
1) Keeps per-symbol regime memory (prev_regime + prev_scores) so classify_regime can smooth.
2) Calls app.engine.regime_classifier.classify_regime(...) using the previous scores.
3) Saves the new regime+scores for the next tick.
4) Injects regime + scores into `tech` and calls app.engine.strategy_logic.choose_and_build(...) to get a plan.
5) Retains a tiny linear UCB bandit that you can update after trades to learn per-symbol strategy priors.

Use:
    from infra.strategy_selector import select_strategy, bandit_update_from_trade

    plan, telemetry = select_strategy(symbol, tech, mode="pending")  # or "market"
    # telemetry -> {"regime": "TREND|RANGE|VOLATILE", "scores": {...}}

    # later, after a trade closes:
    bandit_update_from_trade(selector_json_path, symbol, plan.strategy, tech, reward)
"""

# Align bandit strategy keys with your actual strategy names from strategy_logic.py
# Phase 4.5: Updated to include all SMC strategies
STRATEGIES = [
    # Tier 1: Highest Confluence (Institutional Footprints)
    "order_block_rejection",
    "breaker_block",
    "market_structure_shift",
    # Tier 2: High Confluence (Smart Money Patterns)
    "fvg_retracement",
    "mitigation_block",
    "inducement_reversal",
    # Tier 3: Medium-High Confluence
    "liquidity_sweep_reversal",
    "session_liquidity_run",
    # Tier 4: Medium Confluence
    "trend_pullback_ema",
    "premium_discount_array",
    # Tier 5: Lower Priority
    "pattern_breakout_retest",
    "opening_range_breakout",
    "range_fade_sr",
    "hs_or_double_reversal",
    "kill_zone",
]


# ---------- tolerant numeric helpers ----------
def _safe_f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return float(d)


# ---------- feature vector (bandit learns on these) ----------
def _features_to_vec(feat: Dict[str, Any]) -> List[float]:
    """
    Stable order; extend as needed. Features should be normalized-ish.
    """
    adx = _safe_f(feat.get("adx"), 0.0)
    bbw = _safe_f(feat.get("bb_width"), 0.0)
    rsi_align = _safe_f(feat.get("rsi_align"), 0.0)  # -1..+1 if you compute it
    spike_up = 1.0 if feat.get("spike_up") else 0.0
    spike_dn = 1.0 if feat.get("spike_dn") else 0.0
    sess = str(feat.get("session") or "").upper()
    s_us = 1.0 if ("NEWYORK" in sess or "US" in sess or "NY" in sess) else 0.0
    s_ldn = 1.0 if ("LONDON" in sess or "LDN" in sess) else 0.0
    s_asia = 1.0 if ("ASIA" in sess or "TOKYO" in sess) else 0.0

    # Add regime probabilities if caller provided them
    rp = feat.get("regime_scores") or {}
    p_tr = _safe_f(rp.get("trend"), 0.0)
    p_rg = _safe_f(rp.get("range"), 0.0)
    p_vo = _safe_f(rp.get("volatile"), 0.0)

    return [
        adx / 100.0,  # [0,1]
        bbw,  # BB width (already fractional)
        (rsi_align + 1.0) / 2.0,  # map -1..+1 to 0..1 if provided
        spike_up,
        spike_dn,
        s_us,
        s_ldn,
        s_asia,
        p_tr,
        p_rg,
        p_vo,
    ]


# ---------- tiny persistent linear UCB bandit ----------
class StrategySelector:
    """
    Tiny linear UCB bandit per symbol.
    select(features) -> (strategy, debug)
    update(symbol, features, strategy, reward) -> online update
    """

    def __init__(self, path: str):
        self.path = path or "data/strategy_selector.json"
        self._state = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("StrategySelector load failed: %s", e)
        return {}

    def _save(self):
        dirn = os.path.dirname(self.path)
        if dirn:
            os.makedirs(dirn, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    def _get_sym(self, symbol: str) -> Dict[str, Any]:
        with _LOCK:
            self._state.setdefault(symbol, {"A": {}, "b": {}, "n": 0})
            # A[strategy] = Gram scalar (ridge), b[strategy] = weight vector
            for s in STRATEGIES:
                self._state[symbol]["A"].setdefault(s, 1.0)  # simple ridge scalar
                self._state[symbol]["b"].setdefault(
                    s, [0.0] * 11
                )  # length = len(_features_to_vec)
            return self._state[symbol]

    def select(
        self, symbol: str, features: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        sym = self._get_sym(symbol)
        x = _features_to_vec(features)
        alpha = 0.15  # exploration bonus
        best = None
        best_score = -1e9
        dbg: Dict[str, Any] = {}
        for s in STRATEGIES:
            A = float(sym["A"][s])
            w = sym["b"][s]
            # predicted reward
            mu = sum(wi * xi for wi, xi in zip(w, x))
            # UCB term ~ ||x|| / sqrt(A)
            ucb = alpha * (sum(xx * xx for xx in x) ** 0.5) / max(1.0, A**0.5)
            sc = mu + ucb
            dbg[s] = {"mu": mu, "ucb": ucb, "score": sc}
            if sc > best_score:
                best_score, best = sc, s
        dbg["picked"] = best
        return (best or STRATEGIES[0]), dbg

    def update(
        self, symbol: str, features: Dict[str, Any], strategy: str, reward: float
    ):
        if strategy not in STRATEGIES:
            return
        sym = self._get_sym(symbol)
        x = _features_to_vec(features)
        # simple SGD step on linear model
        lr = 0.1
        pred = sum(wi * xi for wi, xi in zip(sym["b"][strategy], x))
        err = float(reward) - pred
        sym["b"][strategy] = [
            wi + lr * err * xi for wi, xi in zip(sym["b"][strategy], x)
        ]
        sym["A"][strategy] = float(sym["A"][strategy]) + sum(
            xi * xi for xi in x
        )  # grow confidence
        sym["n"] = int(sym["n"]) + 1
        with _LOCK:
            self._save()


# ---------- regime memory (MemoryStore or RAM fallback) ----------
_MS_OK = True
try:
    from infra.memory_store import MemoryStore  # your project module
except Exception:
    _MS_OK = False
    MemoryStore = None  # type: ignore


class _FallbackRAMStore:
    """Very small in-process fallback if infra.memory_store is unavailable."""

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}

    def get(self, k: str, default=None):
        return self._data.get(k, default)

    def set(self, k: str, v: Dict[str, Any]) -> None:
        self._data[k] = v


def _get_store():
    if _MS_OK and MemoryStore is not None:
        path = getattr(settings, "MEMORY_STORE_PATH", None)
        try:
            return MemoryStore(path or "data/memory_store.json")
        except Exception as e:
            logger.warning("MemoryStore init failed (%s); using RAM fallback.", e)
            return _FallbackRAMStore()
    return _FallbackRAMStore()


_STORE = _get_store()


def _state_key(symbol: str) -> str:
    return f"regime_state::{symbol.upper()}"


def _load_prev_state(symbol: str) -> Tuple[Optional[str], Optional[Dict[str, float]]]:
    try:
        st = _STORE.get(_state_key(symbol)) or {}
        return st.get("prev_regime"), st.get("prev_scores")
    except Exception:
        return None, None


def _save_state(symbol: str, label: str, scores: Dict[str, float]) -> None:
    payload = {"prev_regime": label, "prev_scores": scores, "ts": int(time.time())}
    try:
        _STORE.set(_state_key(symbol), payload)
    except Exception as e:
        logger.debug("Failed to save regime state for %s: %s", symbol, e)


# ---------- glue to the classifier + builders ----------
try:
    from app.engine.regime_classifier import classify_regime  # upgraded version
except Exception as e:
    raise ImportError(f"Missing app.engine.regime_classifier.classify_regime: {e}")

try:
    from app.engine.strategy_logic import (
        choose_and_build,
    )  # returns StrategyPlan | None
except Exception as e:
    raise ImportError(f"Missing app.engine.strategy_logic.choose_and_build: {e}")


def classify_with_memory(
    symbol: str, tech: Dict[str, Any]
) -> Tuple[str, Dict[str, float]]:
    """
    Wrap classify_regime with smoothing state:
      - fetch prev_regime/prev_scores from store
      - call classifier with profile={'prev_scores': ...}
      - persist new label/scores
    """
    prev_label, prev_scores = _load_prev_state(symbol)
    profile = {"prev_scores": prev_scores} if prev_scores else {}
    try:
        label, scores = classify_regime(tech, prev_regime=prev_label, profile=profile)
    except Exception as e:
        logger.exception("classify_regime failed for %s: %s", symbol, e)
        # Defensive fallback
        label, scores = ("RANGE", {"trend": 0.33, "range": 0.34, "volatile": 0.33})
    _save_state(symbol, label, scores)
    return label, scores


def _features_from_tech(tech: Dict[str, Any]) -> Dict[str, Any]:
    """Extract a compact, tolerant features dict for the bandit."""

    def _get(tech: Dict[str, Any], tf: str | None, names: list[str]) -> float:
        containers = []
        if tf:
            containers += [
                tech.get(tf) or {},
                tech.get(f"_tf_{tf}") or {},
                tech.get(tf.upper()) or {},
            ]
        containers += [tech]
        for nm in names:
            for c in containers:
                if not isinstance(c, dict):
                    continue
                v = c.get(nm)
                if v is None:
                    continue
                try:
                    return float(v)
                except Exception:
                    try:
                        return float(str(v).replace(",", ""))
                    except Exception:
                        continue
        return 0.0

    feats: Dict[str, Any] = {}
    feats["adx"] = _get(tech, "M15", ["adx", "ADX", "adx_14", "ADX_14"])
    feats["bb_width"] = _get(tech, "M15", ["bb_width", "BBWidth", "bbwidth"])
    feats["rsi_align"] = _get(
        tech, None, ["rsi_bias", "RSI_BIAS", "rsi_align"]
    )  # optional
    feats["spike_up"] = bool(tech.get("spike_up"))
    feats["spike_dn"] = bool(tech.get("spike_dn"))
    feats["session"] = str(tech.get("session") or "").upper()
    feats["regime_scores"] = tech.get("regime_scores") or {}
    return feats


def select_strategy(symbol: str, tech: Dict[str, Any], mode: str = "pending"):
    """
    End-to-end selector:
      1) Classify regime with smoothing
      2) Attach regime & scores into `tech`
      3) Optionally consult bandit for insights (not used to override choose_and_build yet)
      4) Call choose_and_build to get a StrategyPlan (or preview)
    Returns (plan, telemetry)
    """
    label, scores = classify_with_memory(symbol, tech)

    # Attach telemetry for downstream
    tech = dict(tech or {})
    tech["regime"] = label
    tech["regime_scores"] = scores
    tech["prev_scores"] = scores  # carry-forward hint if caller persists tech

    # Bandit advisory (kept informational for now; we don't override builder choice yet)
    try:
        sel = StrategySelector(
            getattr(settings, "STRATEGY_SELECTOR_PATH", "data/strategy_selector.json")
        )
        bandit_features = _features_from_tech(tech)
        bandit_pick, bandit_dbg = sel.select(symbol, bandit_features)
    except Exception as e:
        bandit_pick, bandit_dbg = None, {"error": str(e)}

    logger.debug(
        "select_strategy: %s regime=%s scores=%s mode=%s bandit=%s",
        symbol,
        label,
        scores,
        mode,
        bandit_pick,
    )

    plan = None
    try:
        plan = choose_and_build(symbol, tech, mode=mode)  # StrategyPlan | None
    except Exception as e:
        logger.exception("choose_and_build failed for %s: %s", symbol, e)
        return None, {"regime": label, "scores": scores, "bandit": bandit_dbg}

    telemetry = {
        "regime": label,
        "scores": scores,
        "bandit": bandit_dbg,
        "bandit_pick": bandit_pick,
        "used_strategy": getattr(plan, "strategy", None) if plan else None,
    }
    return plan, telemetry


# ---------- convenience: update bandit after a trade closes ----------
def bandit_update_from_trade(
    selector_path: str,
    symbol: str,
    strategy_name: str,
    tech_snapshot: Dict[str, Any],
    reward: float,
):
    """
    Update bandit after a trade outcome.
    - strategy_name: plan.strategy used ("trend_pullback_ema", etc.)
    - reward: pick your metric (e.g., realized_R multiple, clipped to [-1, +2])
    """
    try:
        reward = float(reward)
    except Exception:
        reward = 0.0

    reward = max(-1.0, min(2.0, reward))  # simple clipping

    try:
        sel = StrategySelector(
            selector_path
            or getattr(
                settings, "STRATEGY_SELECTOR_PATH", "data/strategy_selector.json"
            )
        )
        feats = _features_from_tech(tech_snapshot or {})
        if strategy_name not in STRATEGIES:
            logger.debug(
                "bandit_update: unknown strategy '%s'; skipping.", strategy_name
            )
            return
        sel.update(symbol, feats, strategy_name, reward)
    except Exception as e:
        logger.warning("bandit_update failed: %s", e)
