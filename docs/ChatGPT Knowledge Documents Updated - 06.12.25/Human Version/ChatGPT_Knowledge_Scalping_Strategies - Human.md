✅ ChatGPT_Knowledge_Scalping_Strategies.md (FULLY UPDATED)
(Human-friendly version for you — and clean enough for GPT to parse reliably)
# SCALPING STRATEGIES — UNIFIED & PROFESSIONAL VERSION
Aligned With the Professional Reasoning Layer, SMC, and Session Behaviour

This document defines all scalping behaviour for GPT and overrides ANY conflicting scalping logic in older files.

## 1. OVERARCHING RULES (MANDATORY)
✔ Scalping is only permitted when ALL of these are true:

Regime = Range, Chop, or Compression

Volatility = Stable or Contracting

Session is appropriate for the specific symbol (see Symbol Module)

Location = edge of range, VWAP deviation, liquidity sweep, or OB tap

Risk kept minimal (scalps = low conviction)

Trade must have a clear invalidation (tight SL)

✔ Scalping is forbidden when ANY invalidator is present (see section 7).
✔ Scalping trades are very short-term

Hold duration: minutes → rarely more than 30–45 minutes.

## 2. WHERE SCALPING FITS IN THE PROFESSIONAL REASONING LAYER

This scalping module fills the “Chop”, “Range”, and “Compression” regimes:

Regime	Valid Scalping Strategies
Range	VWAP reversion · MR scalps · Liquidity sweeps · Boundary fades
Compression	Inside-bar trap · Breakout prep · Tight-range fades
Chop	Micro-scalps ONLY (alternating CHOCH, unclear direction)

Not allowed for Trend or Breakout regimes.

Volatility overrides structure — if volatility expands, scalping becomes illegal even if structure looks favourable.

## 3. THE FOUR CORE SCALPING STRATEGIES (Unified)
### A. VWAP Reversion Scalps

Use when price deviates ±0.8–1.5 ATR from VWAP.

Conditions:

Volatility stable/contracting

No displacement candles

VWAP not steeply trending

Price returns toward VWAP magnet

Confirmation:

Micro-CHOCH

Wicks rejecting extremes

OB tap or sweep

### B. Mean Reversion (MR) Range Scalps

Use when the market oscillates between two stable boundaries.

Conditions:

Clear range boundaries

At least 2 touches on each side

No BOS on M5 or M15

RSI divergence helpful but optional

Entry:

Fade range edges

Scalp back to mid-range or VWAP

### C. Liquidity Sweep → Reversion Scalps

Your highest-probability scalp type.

Conditions:

Sweep of previous high/low

No follow-through

Micro-CHOCH back inside the range

Volatility not expanding

DO NOT scalp the sweep itself — only the reversion.

### D. Inside-Bar Compression / Volatility Trap Scalps

Use when volatility contracts tightly.

Conditions:

Tight consolidation (IB/IBS)

Wick compression

ATR contraction

No momentum expansion yet

Entry:

Fade extremes inside the compression

OR take breakout trap reversal

## 4. VOLATILITY KILL ZONES (SCALPING PROHIBITED)

Scalping is ILLEGAL in these time windows:

❌ 10 minutes before → 15 minutes after ANY high/medium USD news

(NFP, CPI, PCE, FOMC, etc.)

❌ NY Open volatility burst (14:30–15:00 UTC)

Applies to ALL symbols.

❌ If ATR > 1.5× baseline

Market too volatile for predictable scalp structure.

❌ BTC ETF inflow volume spikes

Volatility expands instantly → no scalps.

❌ Spread widening events

(Detected via your bot data)

❌ XAU during unexpected headlines (very sensitive)
## 5. SCALP QUALITY SCORE (0–100)
GPT MUST compute this before recommending any scalp.
Component	Weight	Description
Volatility Alignment	30%	Stable/contracting volatility yields high score.
Structure Clarity	20%	Mixed structure ideal for scalps; clear trend lowers score.
Location Quality	20%	Range edges, VWAP deviation, sweep levels, OB taps get highest score.
Confirmation	20%	Micro-CHOCH, wick rejection, compression support.
Session Fit	10%	Asian best; London OK; NY worst for scalps.
Interpretation:

80–100 → High-probability scalp

60–79 → Medium scalp → only with confirmation

< 60 → Reject scalp, recommend WAIT or alternative strategy

The score MUST accompany any scalp trade plan.

## 6. SYMBOL + SESSION BEHAVIOUR (ESSENTIAL)
### XAUUSD

✔ Best scalping asset

✔ Loves VWAP reversions + sweeps

✔ Asian + early London

❌ NY violent volatility

❌ News-sensitive

### BTCUSD

✔ Asian accumulation → OB scalps

✔ London fakeouts → sweep entries

❌ NY continuation kills scalps

❌ Avoid after displacement

### EURUSD

✔ Range & VWAP scalps

❌ Avoid LO unless sweep forms

❌ Avoid NY unless compressing

### GBPUSD

✔ Only scalp compression/VWAP

❌ Avoid everything else — too spiky

### USDJPY

✔ Asian OB scalps

✔ Range rotations

❌ Avoid NY

### AUDUSD

✔ Asian scalps

✔ VWAP deviations

❌ Avoid London session

GPT MUST align: symbol + session + volatility + regime.
## 7. SCALP INVALIDATOR SIGNALS (NO EXCEPTIONS)

When ANY of these triggers occur → GPT must immediately switch to WAIT.

❌ Displacement candle
❌ Strong BOS (M5 or higher)
❌ ATR expansion wave
❌ Volume spike
❌ Spread widening
❌ Mid-range location
❌ Failed sweep follow-through
❌ Price hugging VWAP without deviation
❌ Incoming news

These conditions automatically disqualify scalps.

## 8. RISK & EXECUTION RULES

Risk: ≤ 1% ideal

Use tight structural SL

TP = nearest logical magnet (VWAP, mid-range, opposing sweep)

Scalps MUST use:
✔ auto lot sizing
✔ short expiry (≤ 1 hour)
✔ clear invalidation

Partial profits encouraged only when liquidity has been hit.

## 9. HOW GPT SHOULD DECIDE WHETHER TO SCALP

GPT must run the following steps in this order:

Determine regime
If Trend or Breakout → NO scalp.

Check volatility state
If expanding → NO scalp.

Check news window
If in kill zone → NO scalp.

Check symbol/session alignment
If mismatch → NO scalp.

Check invalidators
If any present → NO scalp.

Check location
If mid-range → NO scalp.

Compute Scalp Quality Score
If < 60 → NO scalp.

Select one of the 4 valid scalp strategies
Based on best alignment.

Generate novice-friendly trade plan
As defined in UPDATED_GPT_INSTRUCTIONS_FIXED.md.

## 10. OVERRIDE & CONFLICT RESOLUTION RULES

If ANY scalping rule in ANY other document contradicts this one:

THIS DOCUMENT OVERRIDES ALL OTHER SCALPING LOGIC.

If conflict persists:

Professional Reasoning Layer wins

UPDATED_GPT_INSTRUCTIONS_FIXED.md wins

Then this document

Everything else is ignored