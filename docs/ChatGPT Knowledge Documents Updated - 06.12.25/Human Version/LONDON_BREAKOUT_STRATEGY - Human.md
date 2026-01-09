LONDON_BREAKOUT_STRATEGY.md (Updated – Human Readable Version)

(Contains both the Professional Strategy version and the Mechanical Strategy version)

# A. PROFESSIONAL STRATEGY VERSION (Human-Readable)
1. Purpose

The London Breakout Strategy exploits volatility expansion when London trading volume enters the market.
The strategy is valid only if Asian Session has formed a stable range, and if volatility, structure, and liquidity conditions support a breakout rather than a fake-out or sweep-reversion scenario.

This version is written for human understanding and training, while still following all strict GPT behavioural and safety rules.

2. Preconditions
2.1 Session Requirements

Time window: 07:00–10:00 London time

Asian Session range must be clearly defined

Avoid breakout trades during high-impact news within ±30 minutes

2.2 Structure Requirements

Asian range must be intact — no premature breaks

HTF (M15–H1) bias must NOT contradict breakout direction

No major HTF rejection candles at the boundaries

No counter-trend sweep immediately before London Open unless retested cleanly

2.3 Volatility Requirements

Volatility must support expansion:

ATR rising OR stable

No extreme compression (ATR collapse)

No excessive pre-London volatility spikes

Spread must be acceptable

2.4 Market Regime Requirements

Breakout strategy is valid ONLY in these regimes:

Trend → Continuation breakout

Range → Expansion breakout

Liquidity trap → Sweep into breakout

INVALID regimes:

Choppy compression

Volatility shock

Fully exhausted trend

Mid-range indecision

3. Professional Reasoning Layer Integration
3.1 Market Regime Classification

Run before ANY strategy logic:

Trending

Ranging

Expanding volatility

Contracting volatility

Chop

If Chop, Shock, or HTF bias conflict → No London Breakout Strategy.

3.2 Strategy Selection Logic

London Breakout is selected only when:

Asian Session range is clean

Liquidity at the edges is intact

Volatility supports breakout

Price is positioned at the top or bottom third of the Asian range

No conflict with HTF structure

If conditions fail → fallback to:

Range Scalp

Sweep → Reversion

Volatility Trap

Trend Continuation (non-breakout version)

3.3 Volatility ↔ Structure Conflict Rule

Breakout is INVALID when:

ATR rising but structure shows absorption

Structure supports breakout but volatility is collapsing

Liquidity sweep occurred but no displacement followed

HTF bearish + volatility spike + bullish breakout setup

If conflict exists → do NOT execute the breakout strategy.

3.4 Scalping vs Trend Classification

The London Breakout has two modes:

Mode 1 — Scalping Breakout (tight Asian range)

Reversion potential is high

Targets smaller

Requires fast execution

Must take partials quickly

Mode 2 — Trend Continuation Breakout

HTF trend is strong

Asian range is compression

Volatility expanding

RR profile is larger

GPT must classify which mode applies before generating a plan.

3.5 Auto-Execution Validation Layer

All of the following must be TRUE:

Market Regime valid

Strategy selection = London Breakout

Structure bias not contradictory

Volatility conditions supportive

Spread acceptable

News filter passed

Liquidity alignment confirmed

Retest or displacement conditions satisfied

If ANY fail → NO breakout plan generated.

3.6 Handling Choppy Markets

If chop detected:

No breakout strategy

Consider range scalp or sweep-reversion

Watch BB compression behaviour

Avoid trades until expansion confirmed

3.7 Institutional Internal Reasoning (Silent Layer)

(GPT uses this silently unless user asks)

Sweep → displacement → retest

Orderflow imbalance alignment

Liquidity magnet levels

Premium/discount evaluation

Asian liquidity placement

HTF liquidity interaction

Used internally for confidence scoring, not as plan conditions.

3.8 Execution Timing Logic
Ideal Entry Windows

07:00–07:30 London (primary)

07:30–08:15 (secondary)

After a sweep + displacement

Invalidation Timing

Avoid trading if:

Breakout occurs > 1 hour after LO

Liquidity sweep fails to create displacement

Price lingers too long at range high/low

Timing logic is strict for breakout strategies.

4. Trade Setups
4.1 Bullish London Breakout

Required:

Asian low intact

Price near Asian high

Sweeps liquidity → displacement

Volatility supportive

No HTF bearish rejection

Entry Types:

Breakout continuation

Sweep → displacement → retest

4.2 Bearish London Breakout

Same logic inverted:

Asian high intact

Price near Asian low

Bearish liquidity sweep

Volatility supportive

HTF not contradicting

5. Fail Conditions

Breakout becomes invalid when:

Sweep occurs with no displacement

Volatility collapses

Structure shifts (CHOCH) opposite to bias

News event creates fake expansion

Spread widens significantly

A failed breakout should not be traded.

6. What NOT To Do

Do NOT trade mid-range

Do NOT assume breakout without displacement

Do NOT trade if structure contradicts

Do NOT trade during high-impact news

Do NOT force the breakout in chop

End of Professional Version
# B. MECHANICAL STRATEGY VERSION (Strict Rules Only)

(This section is designed for deterministic system use — minimal interpretation, no prose.)

1. VALIDATION LAYERS
1.1 Market Regime (must be true)

trending OR

ranging → expansion OR

compression → expansion
NOT chop.
NOT volatility shock.

1.2 Structure Requirements

Asian range intact

No pre-London breakout

HTF bias not contradictory

No opposite CHOCH in last 3–5 candles

Sweep + displacement validated if using sweep variation

1.3 Volatility Requirements

ATR rising OR stable

No pre-London volatility spike

Spread within acceptable limits

Volatility ≠ collapsing

1.4 Session Requirements

Only valid 07:00–10:00 London

No high-impact news ±30 minutes

1.5 Liquidity Requirements

Clean Asian highs/lows

Liquidity pool intact

Clear target beyond breakout

2. STRATEGY SELECTION RULE

If all validation layers pass → Strategy = London Breakout
Else → NO breakout plan.

3. ENTRY LOGIC
3.1 Breakout Continuation

Trigger:

Break + displacement beyond Asian high/low

Candle body > 50% beyond range

Volume spike OR volatility alignment

Confirmation:

Retest OR immediate continuation

No HTF rejection

3.2 Sweep → Retest → Breakout

Trigger:

Sweep of Asian high/low

Displacement in opposite direction

Retest with rejection

4. EXCLUSION RULES

Do NOT trade breakout if:

HTF structure contradicts

ATR collapsing

Spread widening

Asian range already broken

Liquidity messy

Chop environment detected

5. EXECUTION TIMING

Valid:

07:00–08:15
Invalid:

1 hour after London Open

During news window

6. ENRICHMENT INTEGRATION

Increase confidence when:

volatility expansion

momentum alignment

micro-alignment matches bias (BTC/XAU/EURUSD only)

divergence supports direction

pattern detection confirms breakout (engulfing, OB break, etc.)

Decrease confidence when:

volatility instability

spread widening

divergence against direction

micro-alignment contradicts

7. INVALIDATION

Strategy invalid if:

structure shifts opposite

displacement fails

sweep has no follow-through

volatility collapses

HTF rejection appears