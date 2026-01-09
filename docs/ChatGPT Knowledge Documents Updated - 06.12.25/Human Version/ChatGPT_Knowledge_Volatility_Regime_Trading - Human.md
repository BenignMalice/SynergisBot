ChatGPT_Knowledge_Volatility_Regime_Trading.md
📌 Purpose

This document defines volatility classification, behaviour interpretation, and strategy alignment for the Synergis Trading GPT.

It replaces and overrides all previous volatility-related rules in older documents.

Volatility interacts directly with:

Market Regime Classification

Strategy Selection

Session Behaviour

Trade Validation

Breakout vs Range Logic

Scalping vs Trend Strategy Logic

If conflict arises → follow:

Professional Reasoning Layer

UPDATED_GPT_INSTRUCTIONS_FIXED.md

🔥 1. Volatility Regime Classification (Final, Unified)

GPT must classify exactly one volatility regime at a time.

1️⃣ LOW VOLATILITY – Compression / Accumulation

Definition

ATR significantly below average

BB width contracting

Small candles, small wicks

Inside bars common

Volume declining

What it means

Market preparing for expansion

Liquidity builds up near highs/lows

Direction often unclear

Breakouts often fake → traps common

Allowed Strategies

Compression → Breakout Preparation

Inside Bar Trap

Sweep → CHOCH reversals

Micro-scalps only (VWAP reversion, tight range fades)

Avoid

Trend continuation (trend not validated)

Large breakout trades without confirmation

2️⃣ STABLE VOLATILITY – Range / Balanced Market

Definition

ATR near average

BB width stable

No major displacements

Balanced buying & selling pressure

What it means

Market is organised and tradable

Ranges behave cleanly

Mean reversion works well

Allowed Strategies

VWAP Mean Reversion

Range Sweeps (PDH/PDL manipulation)

OB/FVG boundary fades

Micro-scalps at extremes

Avoid

Aggressive breakout trading

Trend continuation entries without strong displacement

3️⃣ INCREASING VOLATILITY – Pre-Breakout / Expansion Signal

Definition

ATR rising

BB width expanding

Large impulsive candles

Increasing wick size

What it means

Market choosing a direction soon

Expansions may start any moment

Structure begins to favour trend continuation

Allowed Strategies

Breakout Anticipation

Trend Continuation Pullback

MSS Continuation

Breaker/FVG continuation setups

Avoid

Countertrend scalping

Mean reversion unless at high-quality liquidity zones

4️⃣ HIGH VOLATILITY – Breakout / Displacement Regime

Definition

ATR significantly above normal

Massive candles

Fast moves away from levels

Large imbalance / Fair Value Gaps forming

What it means

Market has chosen a direction

Clean structure follows after displacement

Ideal for momentum trades

Allowed Strategies

Breakout Momentum Trades

Displacement Continuation

Breaker/FVG Continuation

Pullback entries AFTER imbalance creation

Avoid

Reversions unless sweep → CHOCH confirms reversal

Micro-scalps (market too fast)

5️⃣ EXTREME VOLATILITY – Chaos / News-Driven

Definition

ATR spikes far beyond normal

VIX elevated (Gold/BTC)

DXY sharp movements

Large slippage expected

What it means

News event / liquidation cascade

Direction unreliable

Trend can flip violently

Stop losses slip frequently

Allowed Strategies

NO new trades except:

Post-news stabilization scalp

Sweep → CHOCH reversals at large liquidity pools

Avoid Completely

Breakouts

Trend continuation

Auto-exec trades

🔥 2. Volatility → Market Regime Mapping

GPT must always align volatility with regime classification.

Volatility	Likely Regime	Notes
Low	Compression	Do NOT treat as trend even if BOS exists
Stable	Range OR Chop	Scalping conditions optimal
Increasing	Pre-Breakout	Trend likely forming
High	Breakout / Trend	Use momentum strategies
Extreme	No Trade / Post-news only	Wait for stabilisation
⚠️ Conflict Rule

If structure (BOS/CHOCH) and volatility disagree:

Volatility always overrides structure.

Example:

BOS + stable vol → treat as range, not trend

BOS + expanding vol → treat as trend, not range

🔥 3. Strategy Selection Based on Volatility
LOW VOLATILITY

✔ Inside Bar Traps

✔ Sweep → CHOCH reversals

✔ Breakout preparation

✔ Micro-scalps

❌ Trend continuation

❌ Momentum breakouts

STABLE VOLATILITY

✔ VWAP Reversion

✔ Range Sweeps

✔ MR scalps

✔ OB/FVG boundary fades

❌ Breakouts

❌ High-momentum continuations

INCREASING VOLATILITY

✔ Breakout anticipation

✔ Trend continuation pullbacks

✔ MSS continuation

✔ Breaker/FVG continuation

❌ Micro-scalps at mid-range

❌ Countertrend scalps

HIGH VOLATILITY

✔ Momentum trades

✔ Displacement continuation

✔ Pullback after imbalance

❌ Reversions unless sweep → CHOCH

❌ Scalping

EXTREME VOLATILITY

✔ WAIT

✔ Post-news scalp only

❌ All auto-exec

❌ All trend and breakout trades

🔥 4. Session Interaction With Volatility
Asian Session

Most assets run low–stable volatility

MR/VWAP scalps best

Breakouts often fake

London Open

Volatility jump is normal

Sweeps → expansion common

Early signals unreliable

London Session

If increasing volatility → trend forms

If stable → range behaviour

Breakouts often directional

New York Open

Highest volatility

Cleanest displacements

Trend or reversal traps possible

NY Session

If volatility remains high → continuation

If stabilising → MR scalp opportunities return

🔥 5. Volatility-Based Validation Filters

Trade must be rejected if:

Volatility does NOT match chosen strategy

ATR is too low to hit TP targets

ATR is too high for scalps

High volatility but structure unclear

Extreme volatility around news

Example validation:

OB retest in low volatility → VALID (range conditions)

OB retest in high volatility → INVALID (displacement likely to break it)

🔥 6. Overriding Rules

Volatility Logic overrides:

Old volatility docs

Old regime definitions

Scalping doc regime text

London Breakout doc volatility notes

Any conflicting SMC content

If contradiction → obey:

Professional Reasoning Layer

UPDATED_GPT_INSTRUCTIONS_FIXED.md

This Volatility Regime Doc

🎯 7. Final Integration Summary

The model must always:

Classify volatility

Use volatility to determine regime

Use regime to choose eligible strategy family

Match strategy family with symbol/session behaviour

Validate using SMC + volatility alignment

Reject / WAIT if mismatched

This ensures:

No overfitting

No invalid setups

No misclassification

No contradictory strategy choices