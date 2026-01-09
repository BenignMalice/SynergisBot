# =====================================
# File: infra/openai_service.py
# =====================================
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

# Optional import for risk simulation.  The critic uses this to estimate
# probabilities of hitting SL/TP and expected return before approving a
# trade.  If unavailable, the risk simulation check is skipped.
try:
    from infra.risk_simulation import simulate as _simulate_risk  # type: ignore
except Exception:
    _simulate_risk = None

import httpx

logger = logging.getLogger(__name__)


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _looks_float(s: Any) -> bool:
    try:
        float(s)
        return True
    except Exception:
        return False


def _norm_list_of_str(val: Any) -> List[str]:
    out: List[str] = []
    if isinstance(val, list):
        for item in val:
            if item is None:
                continue
            if isinstance(item, dict):
                try:
                    s = str(
                        item.get("name")
                        or item.get("id")
                        or json.dumps(item, ensure_ascii=False, sort_keys=True)
                    )
                except Exception:
                    s = str(item)
            else:
                s = str(item)
            s = s.strip()
            if s:
                out.append(s)
    elif isinstance(val, (str, int, float)):
        s = str(val).strip()
        if s:
            out.append(s)

    deduped: List[str] = []
    seen = set()
    for s in out:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped


def _coerce_candidate(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coerce raw LLM output into a normalised candidate dictionary.

    This function parses both legacy and new keys, merges guard
    indicators and checklist failures, and computes missing RR when
    possible.  It also supports aliasing 'side' to 'direction' and
    extracts confidence and reasoning from various fields.
    """
    guards = _norm_list_of_str(raw.get("guards", []))
    triggers = _norm_list_of_str(raw.get("triggers", []))
    # Checklist failures may be returned as a list or string; merge into guards
    cl_fail = raw.get("checklist_failures")
    if cl_fail:
        if isinstance(cl_fail, (list, tuple)):
            guards += _norm_list_of_str(cl_fail)
        elif isinstance(cl_fail, str):
            guards += _norm_list_of_str([cl_fail])
    # Reasoning: prefer 'why' over 'reasoning'
    reasoning = raw.get("why") or raw.get("reasoning") or ""
    # Direction: respect 'direction' but allow 'side' override when HOLD
    direction = str(raw.get("direction", "HOLD"))
    side = str(raw.get("side", "")).upper()
    if (not direction or direction.upper() == "HOLD") and side:
        direction = side
    direction = direction.upper() if direction else "HOLD"
    # Confidence: parse int 0-100; default 0
    conf_raw = raw.get("confidence")
    try:
        confidence = int(float(conf_raw)) if conf_raw is not None else None
    except Exception:
        confidence = None
    # what would change my mind
    wwcm = raw.get("what_would_change_my_mind")
    out: Dict[str, Any] = {
        "direction": direction,
        "entry": _safe_float(raw.get("entry")),
        "sl": _safe_float(raw.get("sl")),
        "tp": _safe_float(raw.get("tp")),
        "rr": _safe_float(raw.get("rr")),
        "regime": str(raw.get("regime", "RANGE")).upper(),
        "reasoning": str(reasoning),
        "mtf_label": raw.get("mtf_label"),
        "mtf_score": (
            _safe_float(raw.get("mtf_score"))
            if raw.get("mtf_score") is not None
            else None
        ),
        "pattern_m5": raw.get("pattern_m5"),
        "pattern_m15": raw.get("pattern_m15"),
        "guards": list(dict.fromkeys(guards)),
        "triggers": triggers,
    }
    if wwcm is not None:
        out["what_would_change_my_mind"] = str(wwcm)
    if confidence is not None:
        out["confidence"] = confidence
    # Copy strategy if provided
    strat = raw.get("strategy")
    if isinstance(strat, str) and strat.strip():
        out["strategy"] = strat.strip()
    # Include original checklist_failures separately if present
    if cl_fail:
        # normalised list
        out["checklist_failures"] = _norm_list_of_str(cl_fail)
    # Compute RR if missing or non-positive
    if (not out["rr"] or out["rr"] <= 0.0) and out["tp"] and out["sl"] and out["entry"]:
        dist_win = abs(out["tp"] - out["entry"])
        dist_lose = abs(out["entry"] - out["sl"])
        out["rr"] = round(dist_win / dist_lose, 2) if dist_lose > 0 else 0.0
    return out


def _object_to_dict(obj: Any) -> Dict[str, Any]:
    """
    Best-effort convert arbitrary object to a dict of public attributes.
    """
    out: Dict[str, Any] = {}
    try:
        for k in dir(obj):
            if k.startswith("_"):
                continue
            try:
                v = getattr(obj, k)
            except Exception:
                continue
            if callable(v):
                continue
            out[k] = v
    except Exception:
        pass
    return out


def _to_mapping(pending: Any) -> Dict[str, Any]:
    """
    Robustly convert 'pending' into a dict.
    Accepts:
      - dict
      - list/tuple of pairs: [(key, val), ...]
      - list/tuple positional: [direction?, entry, sl, tp, order_type?]
      - JSON string
      - pandas Series
      - generic object with attributes
      - plain string (treated as direction)
    """
    if pending is None:
        return {}

    # Already a dict
    if isinstance(pending, dict):
        return dict(pending)

    # JSON string?
    if isinstance(pending, str):
        s = pending.strip()
        # Try JSON first
        if (s.startswith("{") and s.endswith("}")) or (
            s.startswith("[") and s.endswith("]")
        ):
            try:
                js = json.loads(s)
                if isinstance(js, dict):
                    return js
                if isinstance(js, list):
                    pending = js  # fallthrough to list handler
                else:
                    return {}
            except Exception:
                # treat as "direction"
                return {"direction": s}
        else:
            # treat as "direction"
            return {"direction": s}

    # pandas Series support (optional)
    try:
        import pandas as pd  # type: ignore

        if isinstance(pending, pd.Series):  # pylint: disable=E1101
            try:
                return {str(k): pending[k] for k in pending.index}
            except Exception:
                return dict(pending.to_dict())
    except Exception:
        pass

    # Object with attributes
    if hasattr(pending, "__dict__") or not isinstance(pending, (list, tuple)):
        # Try attr extraction (but skip if it's a list/tuple)
        try:
            d = _object_to_dict(pending)
            if d:
                return d
        except Exception:
            pass

    # List/tuple
    if isinstance(pending, (list, tuple)):
        # list of pairs?
        try:
            if all(isinstance(x, (list, tuple)) and len(x) == 2 for x in pending):
                return {str(k): v for k, v in pending}
        except Exception:
            pass

        # positional: [direction?, entry, sl, tp, order_type?]
        vals = list(pending)
        out: Dict[str, Any] = {}

        # Optional first item: direction-like string
        if (
            vals
            and isinstance(vals[0], str)
            and vals[0].strip().upper() in {"BUY", "SELL", "HOLD"}
        ):
            out["direction"] = vals[0].strip().upper()
            vals = vals[1:]

        # Pull numeric-looking values in order: entry, sl, tp
        nums = [
            v
            for v in vals
            if isinstance(v, (int, float)) or (isinstance(v, str) and _looks_float(v))
        ]
        others = [v for v in vals if v not in nums]

        def as_float(x):
            try:
                return float(x)
            except Exception:
                return None

        if nums:
            out["entry"] = as_float(nums[0])
        if len(nums) >= 2:
            out["sl"] = as_float(nums[1])
        if len(nums) >= 3:
            out["tp"] = as_float(nums[2])
        if others:
            out["order_type"] = others[0]

        return out

    # Fallback
    return {}


class OpenAIService:
    def __init__(self, api_key: str, model: str = "gpt-5-thinking"):
        self.api_key = api_key
        self.model = model

    def _chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        seed: Optional[int] = None,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "n": 1,
            "response_format": {"type": "json_object"},
        }
        if seed is not None:
            payload["seed"] = seed

        try:
            with httpx.Client(timeout=30) as client:
                r = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                r.raise_for_status()
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                return content
        except Exception as e:
            return json.dumps(
                {
                    "direction": "HOLD",
                    "entry": 0.0,
                    "sl": 0.0,
                    "tp": 0.0,
                    "rr": 0.0,
                    "regime": "RANGE",
                    "reasoning": f"(fallback) API error: {e}",
                    "guards": ["llm_api_error"],
                    "triggers": [],
                }
            )

    def _build_recommend_messages(
        self, symbol: str, tech: Dict[str, Any], fundamentals: str
    ) -> List[Dict[str, str]]:
        """
        Build the chat messages instructing the LLM to propose a trade plan.

        The system prompt emphasises a structured snapshot and strict JSON output.  The
        model must return a single plan as JSON with the following keys (no prose):

          - direction (or side): BUY, SELL or HOLD
          - entry: float, proposed entry price
          - sl: float, stop loss price
          - tp: float, take profit price
          - rr: expected risk-reward (float)
          - regime: TREND, RANGE or VOLATILE
          - strategy: one of the strategies listed below
          - confidence: integer 0–100 representing subjective confidence
          - why: concise reasoning for the trade
          - checklist_failures: list of reasons the trade might fail (e.g. news embargo, overbought, etc.)
          - what_would_change_my_mind: conditions that would invalidate the plan
          - mtf_label, mtf_score: optional multi-timeframe labels and scores
          - pattern_m5, pattern_m15: optional candlestick patterns on M5/M15
          - guards: list of guard flags (e.g. 'news_block', 'exposure_limit')
          - triggers: list of conditions to monitor

        The user message passes a JSON payload with `symbol`, `tech` and
        `fundamentals`.  The `tech` dict contains structured features such as
        indicators, gate_strategy, suggested_strategy, strategy_plan (a pre-computed candidate with entry/SL/TP and entry_type),
        news_block flag, news_events, and similar_cases. The assistant should use this context, abide by
        news_block (must HOLD if true), compare gate_strategy/suggested_strategy with strategy_plan and either adopt the plan
        (if it meets guardrails and improves RR/structure) or propose a better alternative. Summarise similar_cases to calibrate aggressiveness.
        Avoid hallucinating unknown fields.


        """
        strategy_menu = (
            "* Breakout – trade momentum after a range breakout in the direction of the move.\n"
            "* Mean reversion – fade moves when price is extended far from its mean.\n"
            "* Pullback – enter on a retracement within a trend following the trend direction.\n"
            "* Range Expansion Fade – price overextends after a volatility expansion and snaps back to the mean; wait for Bollinger Band width expansion > X%, price closes beyond 2×ATR then closes back inside the band; then fade toward the mean (VWAP/EMA/Pivot).\n"
            "* News Fade – fade an initial spike from a high-impact news release when it fails and retraces (great for gold & crypto); avoid first 1–2 minutes after release.\n"
            "* Post-News Continuation – join strong momentum after a clean breakout on news; avoid first 1–2 minutes.\n"
            "* Liquidity Sweep – institutions hunt stops near obvious highs/lows (stop hunt) then reverse; wick > 1.5× candle body with volume spike and little follow-through; reverse toward range mid.\n"
            "* Order Block Flip – enter on retest of a supply/demand zone (last candle before opposite momentum move); confirm with divergence, VWAP rejection or lower-timeframe confluence.\n"
            "* Trend Exhaustion – end of a strong trend indicated by a climax bar (range > 2×ATR, RSI > 80/<20) followed by a reversal pattern (engulfing/pin bar).\n"
            "* Session Open Reversal – fade the first impulsive move after London/NY open if the push fails and closes back inside the pre-market range (watch the first 15–30 minutes).\n"
            "* Momentum Burst Scalping – capture quick moves inside strong trends: after 3–5 bar consolidation, breakout with volume surge; TP ~1–1.5×ATR, tight SL.\n"
            "* Correlation Play – use lead/lag behaviour of correlated assets; e.g. if silver breaks out first, gold follows.  Monitor correlation matrix; use leader’s signal as confirmation.\n"
            "* Market Regime Switch – detect when ATR/ADX/Bollinger width shifts from trend to range or vice-versa; change strategy accordingly with a cool-down timer to avoid whipsaw."
        )
        sys_prompt = (
            "You are a professional FX/CFD trade analyst specializing in scalp/intraday trading. Given comprehensive feature data and fundamentals, propose ONE clear trade plan.\n"
            "TRADING STYLE & CONSTRAINTS:\n"
            "- ONLY scalp or day trading setups - NO swing trades (close within the same session)\n"
            "- Maximum position size: 0.01 lots (strictly enforced)\n"
            "- Focus on lower timeframes: M5 and M15 for precise entries\n"
            "- Broker symbols end with 'c' (e.g., XAUUSDc, BTCUSDc, EURUSDc)\n"
            "\nENHANCED FEATURE-DRIVEN ANALYSIS:\n"
            "- Output MUST be strict JSON with the keys listed below and no additional text.\n"
            "- direction (or side) ∈ {BUY, SELL, HOLD}. Use side if you prefer, but direction will be read.\n"
            "- Provide entry, sl and tp as floats. Ensure tp > entry > sl for BUY and sl > entry > tp for SELL.\n"
            "- rr = expected risk:reward; compute if not obvious.\n"
            "- Include a concise 'why' field explaining the rationale.\n"
            "- Set confidence ∈ [0,100] reflecting subjective probability of success.\n"
            "- checklist_failures should list any rules violated or reasons to be cautious.\n"
            "- what_would_change_my_mind should describe conditions that would invalidate the plan.\n"
            "- Must respect tech.news_block: if true, return direction 'HOLD' and explain in checklist_failures.\n"
            "- Consider tech.suggested_strategy when selecting strategy but override if context suggests otherwise.\n"
            "- When similar_cases are provided, calibrate your aggressiveness and confidence accordingly.\n"
            "- Add any relevant guards (e.g. news_block, exposure_limit, risk_sim_negative).\n"
            "- Output keys: direction, entry, sl, tp, rr, regime, strategy, confidence, why, checklist_failures, what_would_change_my_mind, mtf_label, mtf_score, pattern_m5, pattern_m15, guards, triggers.\n"
            "\nFEATURE BUILDER ANALYSIS RULES:\n"
            "- Use cross_tf.trend_agreement and cross_tf.trend_consensus for multi-timeframe trend analysis\n"
            "- Leverage cross_tf.rsi_confluence and cross_tf.macd_confluence for momentum validation\n"
            "- Check cross_tf.vol_regime_consensus for volatility context (low/normal/high)\n"
            "- Analyze pattern_flags and candlestick_flags for entry timing and confirmation\n"
            "- Use swing_highs/swing_lows and support_levels/resistance_levels for structure analysis\n"
            "- Consider session context and news_blackout for timing decisions\n"
            "- Evaluate spread_atr_pct and execution_quality for trade feasibility\n"
            "\nTIMEFRAME PRIORITY (Feature Builder Enhanced):\n"
            "- H1 > M15 > M5 for trend direction (use cross_tf.trend_consensus)\n"
            "- Require cross_tf.trend_agreement > 0.6 for strong signals\n"
            "- Use cross_tf.rsi_confluence > 0.5 for momentum confirmation\n"
            "- Check individual timeframe data: M5 for entry timing, H1 for trend direction\n"
            "- Validate ADX strength: H1 or M15 ADX > 25 for trend trades\n"
            "\nPATTERN & STRUCTURE ANALYSIS:\n"
            "- Use pattern_flags for entry confirmation (bull_engulfing, hammer, pin_bar_bull, etc.)\n"
            "- Check candlestick_flags for single-bar patterns (marubozu, doji, shooting_star)\n"
            "- Analyze wick_metrics for rejection strength and asymmetry\n"
            "- Use swing_highs/swing_lows for structure breaks and continuations\n"
            "- Check range_position and near_range_high/low for breakout potential\n"
            "\nSTRATEGY SELECTION (Feature Builder Enhanced):\n"
            "- trend_pullback_ema: Use when cross_tf.trend_consensus='up' AND EMA alignment confirmed\n"
            "- range_fade_sr: Use when near_range_high/low AND rejection patterns present\n"
            "- liquidity_sweep_reversal: Use when pattern_flags show reversal patterns\n"
            "- Match strategy to cross_tf.vol_regime_consensus and session context\n"
            "\nORDER TYPE SELECTION:\n"
            "- MARKET: Use when entry is very close to current price (within spread + 0.1%) or immediate execution needed\n"
            "- PENDING (LIMIT): Use for range fades - entry into pullbacks, away from current price\n"
            "- PENDING (STOP): Use for breakout continuation - entry beyond current price\n"
            "- Suggest appropriate entry based on setup quality and current price distance\n"
            "\nBRACKET/OCO CRITERIA (Use Sparingly):\n"
            "- ONLY recommend OCO brackets for breakout situations:\n"
            "  * Price at key support/resistance zones\n"
            "  * Consolidation ranges (low ATR, tight Bollinger Bands)\n"
            "  * High-impact news events (NFP, CPI, FOMC)\n"
            "  * Volatility squeezes (Bollinger Band pinches, triangle patterns)\n"
            "- For normal setups: propose single directional entry\n"
            "- OCO requires clear breakout potential in BOTH directions\n"
            "\nEXECUTION QUALITY ASSESSMENT:\n"
            "- Check spread_atr_pct < 0.25 for good execution conditions\n"
            "- Evaluate execution_quality and wick_quality for trade feasibility\n"
            "- Consider session_strength and expected_liquidity for timing\n"
            "- Avoid trading during news_blackout periods\n"
            "\nSupport/Resistance handling:\n"
            "- Use support_levels and resistance_levels from feature builder\n"
            "- Check level_strength and nearest_support/resistance for key levels\n"
            "- Treat zones as bands (level±width), not points\n"
            "- Sessions differ: NY often overruns prior H/L slightly; allow small overrun tolerance\n"
            "\nStrategy Menu:\n" + strategy_menu
        )

        # --- Build the user JSON payload (unchanged) ---
        usr_payload = {
            "symbol": symbol,
            "tech": tech,
            "fundamentals": fundamentals,
        }

        # --- S/R context (zones as bands) ---------------------------------------
        sr = tech.get("sr") or {}
        zones = sr.get("zones") or []
        sr_lines: List[str] = []
        for z in zones[:10]:
            try:
                lvl = float(z.get("level"))
                w = float(z.get("width", 0.0))
                k = str(z.get("kind", "")).upper()
                s = float(z.get("strength", 0.0))
            except Exception:
                continue
            sr_lines.append(
                f"{k}: center={lvl:.5f}, band=[{(lvl - w):.5f}..{(lvl + w):.5f}], strength={s:.2f}"
            )

        sr_nearest = sr.get("nearest") or {}
        sr_nearest_line = ""
        if sr_nearest:
            try:
                k = str(sr_nearest.get("kind", "")).upper()
                lvl = float(sr_nearest.get("level"))
                w = float(sr_nearest.get("width", 0.0))
                dfa = sr_nearest.get("distance_frac_atr")
                dfa_txt = (
                    f" (~{float(dfa):.2f} ATR from edge)" if dfa is not None else ""
                )
                sr_nearest_line = (
                    f"Nearest: {k} @ band=[{(lvl - w):.5f}..{(lvl + w):.5f}]{dfa_txt}"
                )
            except Exception:
                sr_nearest_line = ""

        sr_prompt = "Support/Resistance snapshot:\n"
        if sr_lines:
            sr_prompt += "\n".join(sr_lines[:10]) + "\n"
        if sr_nearest_line:
            sr_prompt += sr_nearest_line + "\n"

        # Explicit instruction: anchor levels to the opposite band
        sr_prompt += (
            "\nRules for levels:"
            "\n- If recommending BUY: anchor TP near the next RESISTANCE band edge above; set SL just below the nearest SUPPORT band edge with a small pad."
            "\n- If recommending SELL: anchor TP near the next SUPPORT band edge below; set SL just above the nearest RESISTANCE band edge with a small pad."
            "\n- Prefer R:R >= 1.2 unless explicitly justified; avoid placing TP beyond strong bands."
        )

        # Include session note if available
        sess = sr.get("session") or tech.get("session")
        if isinstance(sess, str) and sess.strip():
            sr_prompt += (
                f"\n\nSession: {sess.strip()} (NY tends to overrun prior H/L slightly)."
            )

        # --- Return messages: system + (user JSON) + (user S/R snapshot text) ---
        return [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": json.dumps(usr_payload)},
            {"role": "user", "content": sr_prompt},
        ]

    # ------------- core HTTP -------------
    def _chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        seed: Optional[int] = None,
    ) -> str:
        """
        Call OpenAI Chat Completions. Returns the content string.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "n": 1,
            # Encourage JSON output. If the model ignores this, we still parse defensively.
            "response_format": {"type": "json_object"},
        }
        if seed is not None:
            payload["seed"] = seed

        try:
            with httpx.Client(timeout=30) as client:
                r = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                r.raise_for_status()
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                return content
        except Exception as e:
            # Fail-safe: return HOLD in JSON to keep the app running
            return json.dumps(
                {
                    "direction": "HOLD",
                    "entry": 0.0,
                    "sl": 0.0,
                    "tp": 0.0,
                    "rr": 0.0,
                    "regime": "RANGE",
                    "reasoning": f"(fallback) API error: {e}",
                    "guards": ["llm_api_error"],
                    "triggers": [],
                }
            )

    # ------------- prompts (legacy stub kept for backward compatibility) -------------
    def _build_recommend_messages_old(
        self, symbol: str, tech: Dict[str, Any], fundamentals: str
    ) -> List[Dict[str, str]]:
        """Legacy prompt builder retained for backward compatibility but unused."""
        sys = (
            "You are a professional FX/CFD trade analyst. "
            "Given technical context + fundamentals, propose ONE clear plan in strict JSON."
        )
        usr = {"symbol": symbol, "tech": tech, "fundamentals": fundamentals}
        return [
            {"role": "system", "content": sys},
            {"role": "user", "content": json.dumps(usr)},
        ]

    # ------------- analyst one-shot -------------

    def _recommend_once(
        self,
        symbol: str,
        tech: Dict[str, Any],
        fundamentals: str,
        temperature: float,
        seed: Optional[int],
    ) -> Dict[str, Any]:
        msgs = self._build_recommend_messages(symbol, tech, fundamentals)
        raw = self._chat(msgs, temperature=temperature, seed=seed)
        try:
            js = json.loads(raw)
        except Exception:
            try:
                start = raw.find("{")
                end = raw.rfind("}")
                js = json.loads(raw[start : end + 1])
            except Exception:
                js = {
                    "direction": "HOLD",
                    "rr": 0.0,
                    "reasoning": "(parse_fail)",
                    "guards": ["parse_fail"],
                }
        return _coerce_candidate(js)

    # ------------- public: recommend (majority + critic) -------------
    def recommend(
        self,
        symbol: str,
        tech: Dict[str, Any],
        fundamentals: str,
        samples: int = 3,
        temperature: float = 0.35,
    ) -> Dict[str, Any]:
        """
        IMPROVED: Use Prompt Router for regime-aware analysis.
        Routes to appropriate strategy template based on market conditions.
        """
        try:
            # IMPROVED: Try prompt router first (Phase 2) if enabled
            from config import settings
            if not settings.USE_PROMPT_ROUTER:
                logger.debug("Prompt router disabled, using fallback method")
                return self._recommend_fallback(symbol, tech, fundamentals, samples, temperature)
            
            from infra.prompt_router import create_prompt_router
            from config import settings
            router = create_prompt_router(session_rules_enabled=settings.SESSION_RULES_ENABLED)
            
            # Create guardrails context
            guardrails = {
                "news_block": tech.get("news_block", False),
                "spread_limit": tech.get("_live_spread", 0.0),
                "exposure_limit": tech.get("exposure_limit", False)
            }
            
            # Route to appropriate template - returns DecisionOutcome
            outcome = router.route_and_analyze(symbol, tech, guardrails)
            
            if outcome.status == "ok" and outcome.trade_spec:
                # Convert trade spec to expected format
                trade_spec = outcome.trade_spec
                direction_str = "BUY" if "buy" in trade_spec.order_type.lower() else "SELL" if "sell" in trade_spec.order_type.lower() else "HOLD"
                
                # IMPROVED Phase 4.4: Apply Structure-Aware SL and Adaptive TP
                entry = trade_spec.entry
                sl = trade_spec.sl
                tp = trade_spec.tp
                rr = trade_spec.rr
                
                sl_metadata = {}
                tp_metadata = {}
                
                try:
                    from config import settings
                    m5_features = tech.get("M5", {})
                    atr = m5_features.get("atr_14", 0)
                    
                    # Apply Structure SL if enabled and we have valid data
                    if settings.USE_STRUCTURE_SL and atr > 0 and entry > 0 and direction_str in ["BUY", "SELL"]:
                        from infra.structure_sl import calculate_structure_sl_for_buy, calculate_structure_sl_for_sell
                        
                        if direction_str == "BUY":
                            new_sl, anchor_type, distance_atr, sl_rationale = calculate_structure_sl_for_buy(
                                entry_price=entry,
                                atr=atr,
                                m5_features=m5_features
                            )
                            sl = new_sl
                            sl_metadata = {
                                "sl_anchor_type": anchor_type,
                                "sl_distance_atr": distance_atr,
                                "sl_rationale": sl_rationale
                            }
                            logger.info(f"Structure SL (BUY): {sl:.5f} (anchor={anchor_type}, {distance_atr:.2f}× ATR)")
                        else:  # SELL
                            new_sl, anchor_type, distance_atr, sl_rationale = calculate_structure_sl_for_sell(
                                entry_price=entry,
                                atr=atr,
                                m5_features=m5_features
                            )
                            sl = new_sl
                            sl_metadata = {
                                "sl_anchor_type": anchor_type,
                                "sl_distance_atr": distance_atr,
                                "sl_rationale": sl_rationale
                            }
                            logger.info(f"Structure SL (SELL): {sl:.5f} (anchor={anchor_type}, {distance_atr:.2f}× ATR)")
                    
                    # Apply Adaptive TP if enabled and we have valid data
                    if settings.USE_ADAPTIVE_TP and atr > 0 and entry > 0 and sl > 0 and direction_str in ["BUY", "SELL"]:
                        from infra.adaptive_tp import calculate_adaptive_tp
                        
                        # Calculate base RR from current SL/TP
                        base_rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 2.0
                        
                        direction_normalized = "buy" if direction_str == "BUY" else "sell"
                        result = calculate_adaptive_tp(
                            entry_price=entry,
                            stop_loss_price=sl,
                            base_rr=base_rr,
                            direction=direction_normalized,
                            m5_features=m5_features
                        )
                        
                        tp = result.new_tp
                        rr = result.adjusted_rr
                        tp_metadata = {
                            "tp_momentum_state": result.momentum_state,
                            "tp_adjusted_rr": result.adjusted_rr,
                            "tp_rationale": result.rationale
                        }
                        logger.info(f"Adaptive TP: {tp:.5f} (momentum={result.momentum_state}, RR {base_rr:.1f} → {rr:.1f})")
                
                except Exception as e:
                    logger.warning(f"Phase 4.4 execution upgrades failed: {e}")
                    # Continue with original values if Phase 4.4 fails
                
                return {
                    "direction": direction_str,
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "rr": rr,
                    "regime": trade_spec.strategy,
                    "strategy": trade_spec.strategy,
                    "confidence": trade_spec.confidence.get("overall", 50),
                    "why": trade_spec.rationale,
                    "checklist_failures": [],
                    "what_would_change_my_mind": "Price breaks key support/resistance levels",
                    "mtf_label": f"{trade_spec.template_version}",
                    "mtf_score": trade_spec.confidence.get("regime_fit", 50),
                    "pattern_m5": trade_spec.tags,
                    "pattern_m15": trade_spec.tags,
                    "guards": [],
                    "triggers": trade_spec.tags,
                    "critic_approved": True,
                    "critic_reasons": [],
                    "router_used": True,
                    "template_version": trade_spec.template_version,
                    "session_tag": outcome.session_tag,
                    "decision_tags": outcome.decision_tags,
                    "validation_score": outcome.validation_score,
                    **sl_metadata,  # Add SL metadata
                    **tp_metadata   # Add TP metadata
                }
            else:
                # Router skipped - log reasons and fallback
                skip_info = f"Router skipped: {', '.join(outcome.skip_reasons[:3])}" if outcome.skip_reasons else "Router returned no trade"
                logger.info(f"Prompt router skipped for {symbol}: {skip_info}")
                return self._recommend_fallback(symbol, tech, fundamentals, samples, temperature)
                
        except Exception as e:
            logger.warning(f"Prompt router integration failed for {symbol}: {e}")
            return self._recommend_fallback(symbol, tech, fundamentals, samples, temperature)
    
    def _recommend_fallback(
        self,
        symbol: str,
        tech: Dict[str, Any],
        fundamentals: str,
        samples: int = 3,
        temperature: float = 0.35,
    ) -> Dict[str, Any]:
        """
        Fallback recommendation method (original logic).
        Used when prompt router is unavailable or fails.
        """
        seeds = [11, 23, 37, 53, 71, 89][: max(1, samples)]
        cands: List[Dict[str, Any]] = []
        for sd in seeds:
            cand = self._recommend_once(
                symbol, tech, fundamentals, temperature=temperature, seed=sd
            )
            verdict = self.critique(cand, tech)
            cand["__critic__"] = verdict
            cands.append(cand)

        # Choose best approved: highest rr, then mtf_score
        def score(c: Dict[str, Any]) -> float:
            rr = _safe_float(c.get("rr"), 0.0)
            mtf = _safe_float(c.get("mtf_score"), 0.0)
            return rr * (1.0 + 0.15 * mtf)

        approved = [c for c in cands if c["__critic__"]["approved"]]
        best = sorted(approved or cands, key=score, reverse=True)[0]

        if not best["__critic__"]["approved"]:
            cur = _norm_list_of_str(best.get("guards", []))
            cur.append("critic_rejected")
            best["guards"] = list(dict.fromkeys(cur))  # dedupe keep order

        best["critic_approved"] = bool(best["__critic__"]["approved"])
        best["critic_reasons"] = best["__critic__"]["reasons"]
        best.pop("__critic__", None)
        best["router_used"] = False
        return best

    # ------------- public: recommend_pending -------------
    def recommend_pending(
        self,
        symbol: str,
        tech: Dict[str, Any],
        pending: Optional[Dict[str, Any]] = None,
        fundamentals: str = "",
        samples: int = 2,
        temperature: float = 0.3,
        **extra: Any,  # accepts current_bid/ask, digits, point, tick_size/value, spread, etc.
    ) -> Dict[str, Any]:
        """
        Pending-order aware recommendation.
        - Accepts a pending context in many shapes and normalizes it.
        - Namespaces pending hints into tech as 'pend_*' so the LLM can consider them.
        - Accepts extra live/meta fields and folds them into tech using critic-friendly keys.
        - Returns the SAME schema as recommend(): direction/entry/sl/tp/rr/...
        """
        merged_tech = dict(tech or {})
        pend = _to_mapping(pending)

        # Namespace common pending fields explicitly
        for k in (
            "direction",
            "side",
            "entry",
            "sl",
            "tp",
            "order_type",
            "timeframe",
            "valid_until",
        ):
            if k in pend and pend[k] is not None:
                merged_tech[f"pend_{k}"] = pend[k]

        # If caller provided an explicit entry, also surface it as a gate hint if blank
        if "entry" in pend and merged_tech.get("gate_entry") is None:
            merged_tech["gate_entry"] = pend["entry"]

        # ---- extras mapping (be generous with synonyms) ----
        keymap = {
            "current_bid": "_live_bid",
            "bid": "_live_bid",
            "current_ask": "_live_ask",
            "ask": "_live_ask",
            "spread": "_live_spread",
            "precision": "_digits",
            "digits": "_digits",
            "point": "_point",
            "tick_size": "_tick",
            "trade_tick_size": "_tick",
            "tick_value": "_tick_value",
            "trade_tick_value": "_tick_value",
        }
        for k, v in extra.items():
            if v is None:
                continue
            dst = keymap.get(k)
            if dst:
                merged_tech[dst] = v
            else:
                merged_tech[f"ctx_{k}"] = v  # keep unknown extras for debugging/context

        # If we have both bid & ask but not spread, compute it
        try:
            if "_live_spread" not in merged_tech:
                b = _safe_float(merged_tech.get("_live_bid"))
                a = _safe_float(merged_tech.get("_live_ask"))
                if a > 0 and b > 0 and a >= b:
                    merged_tech["_live_spread"] = a - b
        except Exception:
            pass

        # Reuse main pipeline (lighter sampling for pending)
        plan = self.recommend(
            symbol,
            merged_tech,
            fundamentals or "",
            samples=max(1, samples),
            temperature=temperature,
        )

        # If pending explicitly fixed direction, reflect it (only if LLM returned HOLD)
        pend_dir = str(pend.get("direction") or pend.get("side") or "").upper()
        if pend_dir in ("BUY", "SELL") and plan.get("direction", "HOLD") == "HOLD":
            plan["direction"] = pend_dir

        # If pending provided an explicit entry and the plan forgot to set one, use it
        if pend.get("entry") and not plan.get("entry"):
            try:
                plan["entry"] = float(pend["entry"])
            except Exception:
                pass

        return plan

    # ------------- public: critic -------------
    def critique(
        self,
        cand: Dict[str, Any],
        tech: Dict[str, Any],
        rules: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Hard checks: sides, ATR sanity, RR floor, spread%, EMA/ADX context, RSI/pattern bias.
        Plus: optional risk simulation, and guardrails (risk/exposure/news/slippage).
        """
        rules = rules or {}
        reasons: List[str] = []
        approved = True

        direction = str(cand.get("direction", "HOLD")).upper()
        entry = _safe_float(cand.get("entry"))
        sl = _safe_float(cand.get("sl"))
        tp = _safe_float(cand.get("tp"))
        rr = _safe_float(cand.get("rr"))

        adx = _safe_float(tech.get("adx"))
        atr = _safe_float(tech.get("atr_14"))

        min_rr = float(rules.get("min_rr", float(rules.get("MIN_RR_FOR_MARKET", 1.2))))
        min_atr_ticks = float(rules.get("min_atr_ticks", 2.0))
        max_spread_pct_atr = float(rules.get("max_spread_pct_atr", 0.35))

        # Live context
        spread = _safe_float(tech.get("_live_spread", 0.0))
        spread_pct_atr = (spread / atr) if (atr > 0) else 0.0
        tick = float(tech.get("_tick", 0.0)) or float(tech.get("_point", 0.0)) or 0.0

        # HOLD is never approved to execute
        if direction not in ("BUY", "SELL"):
            approved = False
            reasons.append("direction=HOLD")

        # SL/TP sides vs entry
        if direction == "BUY":
            if sl >= entry:
                approved, reasons = False, reasons + ["sl_not_below_entry"]
            if tp <= entry:
                approved, reasons = False, reasons + ["tp_not_above_entry"]
        elif direction == "SELL":
            if sl <= entry:
                approved, reasons = False, reasons + ["sl_not_above_entry"]
            if tp >= entry:
                approved, reasons = False, reasons + ["tp_not_below_entry"]

        # ATR sanity vs tick/point
        if atr <= max(2.0 * (tick or 0.0), 1e-9):
            approved = False
            reasons.append("atr_too_small")

        # R:R floor
        if rr < min_rr:
            approved = False
            reasons.append(f"rr_below_floor({rr:.2f}<{min_rr:.2f})")

        # Spread vs ATR
        if spread_pct_atr > max_spread_pct_atr:
            approved = False
            reasons.append(
                f"spread_pct_atr({spread_pct_atr:.2f})>limit({max_spread_pct_atr:.2f})"
            )

        # ADX / EMA hints (soft)
        if adx and adx < 14:
            reasons.append("adx_weak(<14)")
        if tech.get("ema_alignment") is False:
            reasons.append("ema_alignment_false")

        # IMPROVED: Enhanced pattern bias and timeframe validation
        try:
            pattern_bias = (
                int(tech.get("pattern_bias"))
                if tech.get("pattern_bias") is not None
                else None
            )
        except Exception:
            pattern_bias = None
        if pattern_bias is not None and direction in ("BUY", "SELL"):
            if direction == "BUY" and pattern_bias < 0:
                approved = False
                reasons.append("pattern_bias_bearish_vs_buy")
            if direction == "SELL" and pattern_bias > 0:
                approved = False
                reasons.append("pattern_bias_bullish_vs_sell")

        # IMPROVED: Timeframe confluence validation
        try:
            rsi_m5 = _safe_float(tech.get("_tf_M5", {}).get("rsi_14"), 50.0)
            rsi_m15 = _safe_float(tech.get("_tf_M15", {}).get("rsi_14"), 50.0)
            rsi_h1 = _safe_float(tech.get("_tf_H1", {}).get("rsi_14"), 50.0)
            
            adx_m5 = _safe_float(tech.get("_tf_M5", {}).get("adx_14"), 0.0)
            adx_m15 = _safe_float(tech.get("_tf_M15", {}).get("adx_14"), 0.0)
            adx_h1 = _safe_float(tech.get("_tf_H1", {}).get("adx_14"), 0.0)
            
            # Check for timeframe conflicts
            if direction == "BUY":
                rsi_bullish_count = sum([rsi_m5 > 50, rsi_m15 > 50, rsi_h1 > 50])
                if rsi_bullish_count < 2:  # Need at least 2 timeframes bullish
                    approved = False
                    reasons.append("insufficient_rsi_bullish_confluence")
            elif direction == "SELL":
                rsi_bearish_count = sum([rsi_m5 < 50, rsi_m15 < 50, rsi_h1 < 50])
                if rsi_bearish_count < 2:  # Need at least 2 timeframes bearish
                    approved = False
                    reasons.append("insufficient_rsi_bearish_confluence")
            
            # Check ADX strength on higher timeframes
            if direction in ("BUY", "SELL") and max(adx_m15, adx_h1) < 25:
                approved = False
                reasons.append("insufficient_adx_strength_higher_tf")
                
        except Exception:
            pass

        # ENHANCED: Feature Builder validation
        try:
            # Cross-timeframe analysis validation
            cross_tf = tech.get("cross_tf", {})
            trend_agreement = _safe_float(cross_tf.get("trend_agreement"), 0.0)
            trend_consensus = cross_tf.get("trend_consensus", "mixed")
            rsi_confluence = _safe_float(cross_tf.get("rsi_confluence"), 0.0)
            vol_regime = cross_tf.get("vol_regime_consensus", "normal")
            
            # Trend agreement validation
            if direction in ("BUY", "SELL") and trend_agreement < 0.6:
                reasons.append(f"weak_trend_agreement({trend_agreement:.2f})")
            
            # Trend consensus validation
            if direction == "BUY" and trend_consensus == "down":
                approved = False
                reasons.append("trend_consensus_bearish_vs_buy")
            elif direction == "SELL" and trend_consensus == "up":
                approved = False
                reasons.append("trend_consensus_bullish_vs_sell")
            
            # RSI confluence validation
            if direction in ("BUY", "SELL") and rsi_confluence < 0.5:
                reasons.append(f"weak_rsi_confluence({rsi_confluence:.2f})")
            
            # Volatility regime validation
            if vol_regime == "low" and direction in ("BUY", "SELL"):
                reasons.append("low_volatility_regime")
            elif vol_regime == "high" and direction == "HOLD":
                reasons.append("high_volatility_opportunity_missed")
                
        except Exception:
            pass

        # ENHANCED: Pattern and structure validation
        try:
            # Get M5 data for pattern analysis
            m5_data = tech.get("M5", {})
            pattern_flags = m5_data.get("pattern_flags", {})
            candlestick_flags = m5_data.get("candlestick_flags", {})
            
            # Pattern validation
            if direction == "BUY":
                bearish_patterns = [
                    "bear_engulfing", "shooting_star", "pin_bar_bear", 
                    "three_black_crows", "evening_star"
                ]
                active_bearish = any(pattern_flags.get(p, False) for p in bearish_patterns)
                if active_bearish:
                    reasons.append("bearish_patterns_present")
                    
            elif direction == "SELL":
                bullish_patterns = [
                    "bull_engulfing", "hammer", "pin_bar_bull",
                    "three_white_soldiers", "morning_star"
                ]
                active_bullish = any(pattern_flags.get(p, False) for p in bullish_patterns)
                if active_bullish:
                    reasons.append("bullish_patterns_present")
            
            # Candlestick validation
            if direction == "BUY" and candlestick_flags.get("shooting_star", False):
                reasons.append("shooting_star_candlestick")
            elif direction == "SELL" and candlestick_flags.get("hammer", False):
                reasons.append("hammer_candlestick")
                
        except Exception:
            pass

        # ENHANCED: Execution quality validation
        try:
            m5_data = tech.get("M5", {})
            spread_atr_pct = _safe_float(m5_data.get("spread_atr_pct"), 0.0)
            execution_quality = m5_data.get("execution_quality", "unknown")
            news_blackout = m5_data.get("news_blackout", False)
            
            # Spread validation
            if spread_atr_pct > 0.25:
                reasons.append(f"wide_spread({spread_atr_pct:.2f})")
            
            # Execution quality validation
            if execution_quality == "poor":
                reasons.append("poor_execution_quality")
            
            # News blackout validation
            if news_blackout and direction in ("BUY", "SELL"):
                approved = False
                reasons.append("news_blackout_active")
                
        except Exception:
            pass  # Don't fail on missing timeframe data

        # RSI overbought/oversold heuristics
        try:
            rsi = float(tech.get("rsi_14")) if tech.get("rsi_14") is not None else None
        except Exception:
            rsi = None
        if rsi is not None:
            if direction == "BUY" and rsi >= 70:
                reasons.append("rsi_overbought")
                if rsi >= 80:
                    approved = False
                    reasons.append("rsi_extreme_overbought")
            if direction == "SELL" and rsi <= 30:
                reasons.append("rsi_oversold")
                if rsi <= 20:
                    approved = False
                    reasons.append("rsi_extreme_oversold")

        # Optional risk simulation veto
        if _simulate_risk and approved and direction in ("BUY", "SELL"):
            try:
                if atr > 0 and sl > 0 and tp > 0 and entry > 0:
                    sim = _simulate_risk(
                        entry=float(entry), sl=float(sl), tp=float(tp), atr=float(atr)
                    )
                    p_sl = sim.get("p_hit_sl", 0.0)
                    p_tp = sim.get("p_hit_tp", 0.0)
                    expected_r = sim.get("expected_r", 0.0)
                    if (expected_r < 0.0) or (p_sl > p_tp):
                        approved = False
                        reasons.append(
                            f"risk_sim_negative(p_sl={p_sl:.2f},p_tp={p_tp:.2f},exp_r={expected_r:.2f})"
                        )
            except Exception:
                pass

        # Guardrails (hard rules)
        try:
            from infra.guardrails import risk_ok, exposure_ok, news_ok, slippage_ok

            if approved and direction in ("BUY", "SELL"):
                ok, why = risk_ok(cand)
                if not ok:
                    approved = False
                    reasons.append(f"risk_guard:{why}")
                ok, why = exposure_ok(
                    {"symbol": tech.get("symbol"), "direction": cand.get("direction")}
                )
                if not ok:
                    approved = False
                    reasons.append(f"exposure_guard:{why}")
                ok, why = news_ok(
                    tech.get("symbol"),
                )
                if not ok:
                    approved = False
                    reasons.append(f"news_guard:{why}")
                ok, why = slippage_ok(tech.get("symbol"))
                if not ok:
                    approved = False
                    reasons.append(f"spread_guard:{why}")
        except Exception:
            # guardrail import or call failed — don't crash the critic
            pass

        return {"approved": approved, "reasons": reasons}
