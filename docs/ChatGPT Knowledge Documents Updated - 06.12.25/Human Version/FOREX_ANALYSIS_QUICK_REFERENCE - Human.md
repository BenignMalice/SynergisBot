📘 FOREX_ANALYSIS_QUICK_REFERENCE.md
(EURUSD · GBPUSD · USDJPY · AUDUSD)
Fully Updated & Expanded Institutional Version
#️⃣ Global Notes (Applies to All Pairs)

Your GPT must use this document for:

Regime classification

Strategy selection

Symbol/session reasoning

Liquidity interpretation

Microstructure timing

SL/TP logic

Auto-execution validation

And MUST obey:

Professional Reasoning Layer (Overrides All)

UPDATED_GPT_INSTRUCTIONS_FIXED.md

Symbol/Session Behaviour Module

------------------------------
🇪🇺 EURUSD — Quick Reference (Primary Scalping Pair)
You have M1 data for this pair — microstructure precision is highest here.
1. Behaviour Profile

EURUSD is:

The cleanest and most technical major pair

Highly responsive to DXY & macro fundamentals

Least volatile of the majors

Best behaved in London session

Perfect for structured, low-noise scalping and SMC continuation

2. Microstructure Behaviour (HIGH PRECISION — M1 AVAILABLE)

Because you receive M1–M15 data, EURUSD becomes your “reference pair” for microstructure analysis.

Sweeps

5–12 pip sweeps are normal

Liquidity grabs are clean and shallow

Fakeouts usually retrace within 2–4 candles

CHOCH / BOS Timing

Best detection timeframe: M5

M1 → only for micro-sweeps, not structural BOS

M15 → confirms higher-quality continuation

Pullback Depth

Trend continuation: 20–40 pips

MR reversions: 8–15 pips

Breakouts: shallow retests (5–10 pips)

3. Volatility Profile (ATR)
Regime	Daily ATR	Interpretation
Low	30–45 pips	Avoid breakouts; scalping only
Normal	45–75 pips	Most reliable for structure trading
High	75–120 pips	Volatility expansions → breakout traps common
4. Structure Behaviour

BOS signals are clean and reliable

Equal highs/lows form frequently → liquidity magnets

Displacement candles almost always confirm direction

OB retests tend to be shallow and precise

5. Liquidity Behaviour

EURUSD hunts liquidity narrowly

Liquidity magnets include:

PDH/PDL

Equal highs/lows

Asian session range

Sweeps typically precede a structured move:

Sweep → 2–3 M1 candles → CHOCH → continuation

6. Bias Formula (Weighted)

(GPT uses this internally)

DXY direction: 40%

HTF structure: 30%

Session context: 20%

Microstructure momentum: 10%

7. SL / TP Guide
Setup Type	SL Placement	Notes
Trend continuation	1 × M15 swing	Structure is clean
Reversal trade	Below/above sweep wick	Sweeps are shallow
MR scalp	Outside VWAP deviation band	EURUSD respects VWAP
8. Auto-Execution Safety Filters

❌ Reject if ATR < 30 pips
❌ Reject breakouts in Asian session
❌ Reject trades with mixed structure on M5 + M15

✔ Allow micro-scalps during Asian
✔ Only allow continuation trades during London & NY

9. Example Scenarios
A. Sweep → CHOCH Reversal Example

Sweep below Asian low

M1 rejection wick

M5 CHOCH

Target → VWAP / PDH

B. Trend Continuation Example

BOS on M15

Retest OB (5–12 pip pullback)

Expansion candle entry

C. Failed VWAP Scalp

Price closes outside VWAP band + RSI > 65 → reject scalp.

D. Invalid FVG Continuation

If price returns into FVG deeper than 60% → invalidate trend continuation.

------------------------------
🇬🇧 GBPUSD (Cable) — Quick Reference
Volatile · Trap-Heavy · Best in London
1. Behaviour Profile

GBPUSD is:

Highly volatile

Loves fakeouts

Loves deep OB taps

Best traded during London

Worst traded during low-vol windows

2. Microstructure Behaviour

No M1 guarantee, so use:

M5 for sweeps

M15 for structure

H1 for bias

Sweeps:

Extremely large: 20–40 pips

Often two-stage → first sweep fails, second confirms

CHOCH:

M5 or M15 only (M1 too noisy)

3. Volatility Profile
Regime	Daily ATR
Low	50–70 pips
Normal	70–100 pips
High	100–150 pips
4. Structure Behaviour

BOS unreliable without volume confirmation

Deep mitigations common

Large displacement candles indicate true shift

OBs often retraced by 50–80%

5. Liquidity Behaviour

London killzone = double sweeps

NY session = continuation or V-reversals

6. Bias Formula

Session weighting (London) = 40%

Structure = 30%

USD strength = 20%

Volatility regime = 10%

7. SL / TP Guide
Setup	SL Rule
Continuation	1.5 × OB depth
Reversal	Beyond sweep wick (big wick tolerance)
MR scalp	Avoid except Asian
8. Auto-Execution Safety Filters

❌ Reject all MR scalps during London volatility
❌ Reject countertrend trades without CHOCH + volume

✔ Best trades occur after London fakeouts
✔ Breakout traps highly reliable

9. Example Scenarios

A. London Sweep Trap
Big wick through PDH → M5 CHOCH → sell continuation.

B. NY Reversal
Fast sweep → immediate impulse → trend change.

C. Failed Continuation
OB mitigated >80% → invalidate trend.

------------------------------
🇯🇵 USDJPY — Quick Reference
Yield-driven · Extends Trends · Loves Precision OBs
1. Behaviour Profile

USDJPY is:

Driven heavily by US10Y yields

One-directional trends are common

Pullbacks are shallow during strong USD periods

Liquidity often taken via candles, not wicks

2. Microstructure Behaviour

Sweeps:

Usually look like straight candles, not wick taps

CHOCH detection:

M1 not required — use M5 for reversals

M15 confirms major shifts

Pullbacks:

10–30 pips typically

3. Volatility Profile
Regime	ATR
Low	40–60
Normal	60–110
High	110–160
4. Structure Behaviour

BOS chains → strong trend continuation

OB retests extremely precise

Mitigations often occur during Asian session

5. Liquidity Behaviour

Liquidity grabs are forceful and directional

Sweeps often signal reversals only when yields agree

6. Bias Formula

US10Y direction (50%)

USD sentiment (30%)

Structure (20%)

7. SL / TP Guide
Setup	SL Rule
Continuation	Just beyond OB wick
Reversal	Beyond candle body (not wick)
MR scalp	Only during Asian
8. Auto-Execution Filters

❌ Reject reversals if US10Y trend contradicts
❌ Avoid late NY trades (erratic moves)

✔ Asian MR scalps reliable
✔ Trend continuation best in NY

------------------------------
🇦🇺 AUDUSD — Quick Reference
Commodity-linked · VWAP Respecter · Best in Asian Session
1. Behaviour Profile

AUDUSD is:

Very sensitive to commodity sentiment

Clean VWAP reversion structure

Range-bound during London

Trend-following in NY when USD drives

2. Microstructure Behaviour

Sweeps:

8–15 pips

Double-taps common

CHOCH:

M5 for reversals

M15 needed for trend confirmation

3. Volatility Profile
Regime	ATR
Low	25–40
Normal	40–60
High	60–90
4. Structure Behaviour

VWAP magnetism extremely strong

OBs shallow

FVG fills 60–80% frequently

5. Liquidity Behaviour

Asian session shapes the microstructure

London often produces chop

NY produces clean USD-driven moves

6. Bias Formula

Commodity sentiment (30%)

USD sentiment (30%)

Session behaviour (20%)

Structure (20%)

7. SL / TP Guide
Setup	SL Rule
Trend	Outside VWAP deviation band
Reversal	Beyond sweep wick
MR scalp	Tight SL; AUD respects levels
8. Auto-Execution Filters

❌ Avoid London trend plays
❌ Reject setups when commodities contradict price

✔ Best set-ups in Asian
✔ FX-proxy trades when DXY is directional