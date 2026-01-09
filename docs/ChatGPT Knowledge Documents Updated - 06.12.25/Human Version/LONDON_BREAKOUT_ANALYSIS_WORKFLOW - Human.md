LONDON_BREAKOUT_ANALYSIS_WORKFLOW (Updated – Human Readable Version)

(Fully aligned with new GPT behaviour + strategy + enrichment systems)

1. Purpose

The London Breakout Analysis Workflow defines how GPT evaluates the market around the London Open and determines whether a London Breakout plan is valid, invalid, or replaced by another strategy.

It ensures the breakout logic is:

regime-aligned

volatility-gated

structure-safe

enrichment-supported

session-correct

non-hallucinatory

tool-driven

It also enforces the required Professional Reasoning Layer before any breakout logic runs.

2. Workflow Overview (High-Level)

GPT must follow this sequence in order:

Fetch price (→ required for ALL logic).

Detect session and check time validity.

Apply news filter.

Run Market Regime Classification.

Decide if London Breakout is the correct strategy (Strategy Selector).

Validate Asian Range Structure (core requirement).

Validate Volatility Conditions.

Validate Structure + Liquidity Conditions.

Check for Sweep → Displacement Conditions (if present).

Run Auto-Execution Validation Layer.

If ALL checks pass → breakout analysis + plan allowed.

If ANY fail → choose alternative strategy or decline plan.

This workflow ensures GPT never forces a breakout in the wrong environment.

3. Session & Timing Rules

Breakout analysis is valid ONLY within:

07:00 – 10:00 London time

Timing behaviour:

07:00 – 07:30 → primary breakout window

07:30 – 08:15 → secondary window

After 08:15 → only valid if a clean sweep + displacement occurs

After 09:30 → breakout probability decreases drastically; treat with caution

After 10:00 → London Breakout Strategy becomes invalid

GPT MUST check these before performing breakout logic.

4. News Filter (Mandatory)

A London Breakout analysis is invalid if:

High-impact news is within ±30 minutes

For example:

CPI

NFP

FOMC

Central bank rate decisions

Major GBP or EUR macro events

If news filter fails:

No breakout analysis

Recommend waiting or using a volatility-aware strategy

5. Market Regime Classification (Professional Reasoning Layer Step 1)

GPT classifies regime using structure + volatility + enrichments:

Valid Regimes for Breakout

Trending

Ranging → expansion expected

Compression → expansion likely

Liquidity coil → breakout potential

Invalid Regimes

Chop

Volatility collapse

Volatility shock

Mid-trend exhaustion

Counter-trend dominance

If regime is invalid → stop breakout workflow.

6. Strategy Selection (Reasoning Layer Step 2)

London Breakout Strategy is chosen ONLY when all conditions match:

Asian range is clean

Liquidity at range edges intact

Volatility supportive

No HTF structure contradiction

No early breakout before London session

No news conflict

If another strategy fits better, GPT must choose instead:

Range Scalp

Sweep → Reversion

Trend Continuation (non-breakout)

Volatility Trap

Micro-Scalp (symbol-specific)

7. Asian Range Validation

GPT must validate using price + structure tools:

Required:

Clear Asian High

Clear Asian Low

Range formed BEFORE 06:30 London

No break or displacement of range before 07:00

No messy overlapping liquidity at extremes

No multi-hour drift without structure

Invalid Asian Sessions:

Wide + unstable range (high volatility)

Early breakout before London

No definable highs/lows

HTF rejection already formed at boundary

Trend already exhausted in Asia

If Asian range is invalid → no breakout.

8. Volatility Gating

The breakout is valid only if:

Volatility Supports Expansion

ATR rising or stable

Session volatility normal (not excessive)

Spread acceptable

No erratic pre-London spikes

Invalid Volatility Environments

ATR collapsing

Volatility shock already occurred

Spread widening

No energy in market

Volatility ↔ Structure conflict must be checked:

If volatility says “breakout” but structure says “absorption” → invalid

If structure says “breakout” but volatility collapsing → invalid

9. Structure & Liquidity Validation

GPT must confirm:

Structure Requirements

HTF trend not contradicting breakout direction

No opposite CHOCH in previous 3–5 candles

Liquidity positioned beyond Asian levels

No HTF absorption at boundary

Sweep → displacement logic consistent

Liquidity Requirements

Clean liquidity at Asian high/low

Clear destination (liquidity magnet) for breakout

No large midpoint imbalance stalling price

If structure contradicts → NO breakout.

10. Sweep → Displacement Evaluation

A breakout is significantly stronger when:

Liquidity sweep occurs at Asia high/low

Followed by displacement in opposite direction

Followed by a clean retest

Valid sweep-breakout combinations:

Bear sweep at Asian high → bearish breakout

Bull sweep at Asian low → bullish breakout

Invalid:

Sweep but no displacement

Sweep but retest fails

Sweep into HTF rejection

11. Auto-Execution Validation Layer (Mandatory)

GPT MUST PASS ALL 8 CHECKS:

Regime valid

Strategy selection = London Breakout

Structure bias aligned

Volatility supportive

Asian range valid

Session timing valid

News filter passed

Liquidity + displacement confirmed

If any fail → breakout plan cannot be generated.

12. Execution Timing Logic (Professional Layer)
Valid Timing:

During displacement

After sweep → retest

During first clean expansion leg

Invalid Timing:

Mid-range

Late breakout with no pullback

Breakout after consolidation stall

60 minutes after London Open with no displacement

13. Enrichment Integration

Boost Confidence When:

Volatility expansion

Momentum alignment

Micro-alignment agreement (BTC/XAU/EURUSD only)

Divergence supports breakout direction

BB compression before London

Clear engulfing candle forming breakout body

Reduce Confidence When:

Spread widening

Volatility instability

Opposite divergence

Conflicting micro-alignment

Momentum exhaustion

Enrichments NEVER override structure, volatility, or timing.

14. Breakout Failure Conditions

Breakout becomes invalid when:

Opposite CHOCH forms

Displacement fails

Sweep fails to produce follow-through

Volatility collapses mid-breakout

News event disrupts movement

Price drifts sideways at breakout level

If failure detected → retreat to range scalp or do nothing.

15. Output Requirements

GPT must:

Never predict direction without explicit user request

Never assume levels without tools

Must fetch live price before analysis

Must apply session, news, volatility, and structure gates

Must decline breakout plans when invalid

Must provide alternative strategies when breakout fails validation

16. Summary of Workflow

Fetch price

Confirm session + news

Run regime classification

Run strategy selection

Validate Asian range

Validate volatility

Validate structure

Validate liquidity

Check sweep → displacement

Run global validation layer

If all pass → breakout analysis allowed

If fail → alternative strategy