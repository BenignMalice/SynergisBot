# AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md
## PART I — Purpose, Scope & Core Philosophy

### 1. Purpose of This Document
This document defines the **full operational knowledge** ChatGPT must reference when generating **auto-execution trade plans** for the MoneyBot system.

It explains:
- How ChatGPT interprets market states  
- How strategies are selected  
- How conditions are chosen  
- How plans are validated  
- How symbol behaviour affects plan construction  
- When multiple plans should be generated  
- When no plan should be created  

This is a **knowledge reference**, not an output-formatting document.  
It supports the system prompt but does *not* override formatting or reasoning rules.

Formatting and response structure remain strictly defined in:
- `UPDATED_GPT_INSTRUCTIONS_FIXED.md`
- The System Prompt  
- Your other analysis formatting documents  

This document:
✔ Enhances decision-making  
✔ Provides internal knowledge  
✔ Ensures all plans are valid, aligned, and executable  

---

### 2. Scope
This document governs **plan creation logic only**:

Included:
- Market regime interpretation  
- Strategy selection  
- Symbol/session alignment  
- Microstructure rules  
- Required condition logic  
- Validation filters  
- Multi-plan orchestration  
- SL/TP construction rules  

Excluded:
- Output formatting  
- General behaviour instructions  
- Novice/expert explanation rules  
- Tool interaction formatting  

---

### 3. Core Philosophy of Auto-Execution Plans
Auto-execution plans are **conditional future trade instructions**, not immediate trades.

A plan:
- Is created in anticipation of future price behaviour  
- Activates only when all required conditions are satisfied  
- Must specify **entry, SL, TP, strategy type, min_confluence, and required conditions**  
- Must align with regime, session, volatility, and symbol personality  

---

### 4. System Principles
The following principles guide every plan:

#### ✔ 4.1 Plans must reflect realistic institutional behaviour
No predictions.  
No guessing.  
Plans must be based on:
- Structure  
- Liquidity  
- Volatility  
- Context  
- Session  
- Symbol behaviour  

#### ✔ 4.2 Every plan must have at least:
- one **required structural or volatility condition**
- one **entry location condition** (price_near)
- one **confluence requirement**

#### ✔ 4.3 Strategies must match the market regime
Regime determines strategy family.  
Invalid pairings (e.g., trend continuation in a range) must be rejected.

#### ✔ 4.4 Plans must be *location-dependent*
Trades **must not** occur:
- In the middle of ranges  
- Without clear invalidation  
- In unclear or choppy structure (unless micro-scalp regime)  

#### ✔ 4.5 ChatGPT may generate 2–5 mutually-exclusive plans
Multiple plans are valid if:
- Each plan aligns with its own strategy  
- Each has its own unique required conditions  
- No plan depends on predicting price direction  

Examples:
- Range scalp top  
- Range scalp bottom  
- Liquidity sweep reversal  
- Breakout retest  
- Order block rejection  

---

### 5. Philosophy of Future-Condition Plan Creation
Auto-exec plans are NOT immediate trades.  

Plans exist to be **monitored**, not executed immediately.

A valid plan must:
- Define a future price zone  
- Define structural/volatility triggers  
- Define SL/TP based on invalidation  
- Wait for the market to “come to the plan”  

Plans **must not** depend on:
- Predictions  
- Hopes  
- Unformed structure  
- Unknown future volatility regimes  

---

### 6. Key Differences vs Market Execution Recommendations
| Component | Auto-Exec Plan | Market Execution |
|----------|----------------|------------------|
| Purpose | Prepare for future conditions | Act immediately |
| Entry | Conditional | Immediate |
| Conditions | Required | Optional |
| SL/TP | Mandatory | Mandatory |
| Multi-Plan Allowed | ✔ Yes | ❌ Usually no |
| Regime strictness | Higher | Moderate |
| Symbol/session filters | Always applied | Strongly recommended |
| Risk | Lower | Instant |

---

### 7. When ChatGPT Must NOT Create a Plan
ChatGPT must avoid creating plans if:

- Structure is completely unclear  
- Volatility is collapsing (dead markets)  
- Session mismatch (e.g., Asian breakout trap)  
- Symbol behaviour contradicts the strategy  
- No clear invalidation exists  
- Market is mid-range with no edge  
- News event is immediately upcoming  
- Confluence requirements cannot reasonably be met  

When any of these are true:
**Return: WAIT — No valid auto-execution plan context.**

---

### 8. When ChatGPT MUST Create Multiple Plans
ChatGPT should produce **2–5 plans** when:

- Price is inside a range → top fade + bottom fade  
- Liquidity has not been swept both sides  
- Breakout + breakout trap scenarios coexist  
- OB continuation and FVG retracement are both valid  
- Volatility regime allows for both trend & mean reversion  

This enhances execution diversity and mimics institutional playbooks.

---

### 9. Symbols With M1 Microstructure Availability
| Symbol | M1 Data Available? | Microstructure Rules Active? |
|--------|---------------------|-------------------------------|
| XAUUSD | ✔ Yes | ✔ Yes |
| BTCUSD | ✔ Yes | ✔ Yes |
| EURUSD | ✔ Yes | ✔ Yes |
| GBPUSD | ❌ No | ❌ Use M5/M15 only |
| USDJPY | ❌ No | ❌ Use M5/M15 only |
| AUDUSD | ❌ No | ❌ Use M5/M15 only |

GPT must adapt strategy selection accordingly.

---

### 10. Symbols Without M1 Data Must Avoid:
- micro_choch  
- micro_sweep  
- micro_displacement  
- M1 confirmation conditions  

Use M5/M15 equivalents instead.

---

# PART II — Professional Reasoning Layer (Deep Version)

The Professional Reasoning Layer is the institutional “brain” that ChatGPT must use BEFORE selecting a strategy or creating any auto-execution plan.

This layer overrides:
- older strategy rules  
- older regime definitions  
- outdated volatility logic  
- simplistic trend logic  
- all conflicting legacy documents  

It ensures consistent, high-quality, institution-grade plans.

---

## 1. Core Purpose of the Reasoning Layer

The Professional Reasoning Layer:

- Classifies the current **market regime**
- Determines which **strategy families** are valid
- Chooses the **correct set of conditions**
- Ensures alignment with **symbol behaviour**
- Ensures alignment with **session behaviour**
- Prevents invalid strategy mismatches
- Prevents premature or dangerous plans
- Ensures all plans have a **clear edge** and **clear invalidation**

This reasoning runs **silently** before any output.

---

## 2. Regime Determination Rules (Final, Unified Version)

ChatGPT must assign **exactly one** regime based on price structure, volatility, and session behaviour.

### ✔ TREND REGIME
Conditions:
- Clear BOS chain  
- HTF alignment  
- Expanding volatility  
- Clean directional impulsive moves  

Valid strategies:
- Trend continuation pullback  
- MSS continuation  
- Breaker/FVG continuation  

Invalid:
- Mean reversion  
- Range scalps  

---

### ✔ RANGE REGIME
Conditions:
- Mixed CHOCH/BOS  
- Stable volatility  
- Price oscillating between well-defined boundaries  
- Lack of directional trend  

Valid strategies:
- Mean reversion → range scalp  
- VWAP reversion  
- Liquidity sweeps at range extremities  

Invalid:
- Trend continuation  
- Breakout continuation  

---

### ✔ BREAKOUT REGIME
Conditions:
- Expanding volatility  
- Displacement candles  
- BB expansion  
- Break from compression phase  

Valid:
- Breakout trap  
- Momentum continuation  
- Inside-bar expansion strategies  

Invalid:
- Range scalps  
- Slow VWAP reversions  

---

### ✔ COMPRESSION REGIME
Conditions:
- Contracting volatility  
- Inside bars  
- Tight price coiling  
- Low-range ATR conditions  

Valid:
- Breakout preparation  
- Inside-bar trap  
- Volatility squeeze setups  

Invalid:
- Trend continuation  
- Range scalps (unless near boundary)  

---

### ✔ REVERSAL REGIME
Conditions:
- Liquidity sweep  
- Opposing CHOCH  
- Mitigation + rejection wicks  
- Exhaustion candles  

Valid:
- Sweep → CHOCH reversal  
- OB rejection reversal  
- FVG retracement reversal  

Invalid:
- Trend continuation  

---

### ✔ MICRO-SCALP REGIME
Conditions:
- Structure unclear  
- Stable low volatility  
- Alternating CHOCHs  
- No clear direction  

Valid:
- Small range MR scalps  
- VWAP micro-scalps  
- Sweep→micro-CHOCH setups  

Invalid:
- Breakouts  
- Trend continuation  
- High-volatility setups  

---

## 3. Volatility Overrides All Structure

Volatility determines whether a structural signal is real or fake.

### ✔ If BOS + stable volatility → Treat as RANGE  
(no trend continuation allowed)

### ✔ If BOS + expanding volatility → Trend is VALID  
(continuation allowed)

### ✔ If volatility collapsing → Compression regime  
(wait for break or scalp small ranges)

### ✔ If volatility spiking → Breakout or reversal regime

This single rule prevents the majority of poor plan selections.

---

## 4. Strategy Selection Rules (Based on Regime)

ChatGPT must use this mapping:

| Regime | Valid Strategies |
|--------|------------------|
| Trend | continuation pullback, MSS continuation, breaker/FVG continuation |
| Range | mean reversion, VWAP reversion, range scalp, liquidity sweep |
| Breakout | momentum expansion, breakout trap, inside-bar breakout |
| Compression | breakout prep, fakeout trap, IB trap |
| Reversal | sweep→CHOCH, mitigation rejection, OB/FVG reversals |
| Micro-Scalp | VWAP micro scalps, small-range fades |

Only **these** strategy families are allowed per regime.

---

## 5. Structure Strength Evaluation

Before picking a strategy, GPT must evaluate:

### ✔ High Strength Structure:
- BOS chain  
- Impulsive moves  
- HTF alignment  
- Volume confirmation  

→ Trend continuation allowed.

### ✔ Medium Strength:
- CHOCH  
- Partial BOS  
- Slow drift  
- Overlapping candles  

→ Range or reversal context likely.

### ✔ Low Strength:
- Alternating CHOCH  
- Mixed wicks  
- Inconsistent highs/lows  

→ Micro-scalp regime only.

---

## 6. Liquidity Intent Analysis

Before generating any plan, GPT must evaluate which liquidity side is likely to be targeted:

- Is liquidity sitting above?  
- Is liquidity sitting below?  
- Has one side already been swept?  
- Has neither been swept?  

Rules:

✔ If neither side swept → Both continuation + reversal plans may be valid.  
✔ If top swept → Favour bearish continuation/reversal.  
✔ If bottom swept → Favour bullish continuation/reversal.  
✔ If both swept → Trend continuation OR compression breakout likely.

---

## 7. Location Quality — The Most Important Factor

A plan must exist at a **high-quality location**, such as:

- Range boundaries  
- Order blocks  
- FVG edges or fill levels  
- VWAP deviations  
- Sweep zones  
- Breaker blocks  
- Displacement origin points  

GPT must NEVER generate a plan in:

❌ Mid-range  
❌ Undefined zones  
❌ Poor invalidation areas  
❌ Volatility dead zones  
❌ Pre-news without direction  

---

## 8. Execution Timing Logic

### ✔ Continuation strategies:
Wait for:
- OB retest  
- FVG mitigation  
- MSS continuation retest  
- Breaker block validation  

### ✔ Reversal strategies:
Wait for:
- Sweep → CHOCH  
- Rejection wick  
- Microstructure confirmation (if available)

### ✔ Range scalps:
Enter:
- Near range boundaries  
- With VWAP deviation  
- With confluence ≥ 70  

### ✔ Breakout traps:
Enter:
- After fakeout wick  
- After BB expansion + reversal  
- With volatility squeeze confirmation  

---

## 9. Quality Filters

GPT must internally reject any strategy if:

- Location is unclear  
- Liquidity not aligned  
- Regime mismatch  
- Microstructure contradicts direction  
- Symbol/session conditions violated  
- No clean invalidation exists  
- SL cannot be logically set  

If ANY of these are true:
**GPT must NOT generate a plan.**

---

## 10. Professional Reasoning Summary

The reasoning layer must ensure:

✔ Strategy aligns with regime  
✔ Regime aligns with volatility  
✔ Location is institutionally meaningful  
✔ Liquidity logic is respected  
✔ Symbol behaviour influences the plan  
✔ Session behaviour influences the plan  
✔ Microstructure confirms or rejects  
✔ High-confluence trades only  

Only after all these internal checks pass  
→ **GPT may proceed to PART III (Strategy Mapping).**

# PART III — Unified Market Regimes & Strategy Mapping

This section defines how the auto-execution engine maps CURRENT MARKET REGIME → VALID STRATEGY FAMILY.

It ensures:

- The strategy ALWAYS fits the environment  
- GPT never forces a trend setup into a range  
- GPT never forces a range scalp into a breakout  
- GPT understands when multiple strategies are valid  
- GPT avoids invalid strategy mismatches  
- GPT produces clean, structured, anticipatory plans  

This is the core “decision tree” of the auto-exec system.

---

# 1. Market Regimes Overview

GPT must classify every symbol into exactly ONE of the following regimes:

1. **TREND**
2. **RANGE**
3. **BREAKOUT**
4. **COMPRESSION**
5. **REVERSAL**
6. **MICRO-SCALP**

This classification comes directly from the Professional Reasoning Layer.

Each regime uniquely restricts which strategy families GPT may use.

---

# 2. Strategy Families Overview

The system supports the following strategy families:

### ✔ Trend Continuation Families
- MSS continuation  
- Breaker block continuation  
- FVG continuation  
- OB continuation retests  

### ✔ Reversal Families
- Liquidity sweep → CHOCH reversal  
- OB rejection reversal  
- FVG retracement reversal  
- Displacement exhaustion reversal  

### ✔ Range / Mean Reversion Families
- VWAP reversion  
- Standard range scalp (buy low / sell high)  
- Premium/discount scalps  
- Range sweep → reversion  

### ✔ Breakout Families
- Momentum breakout  
- Breakout trap / fakeout  
- Inside-bar breakout  
- Volatility squeeze → expansion  

### ✔ Micro-Scalp Families
- VWAP micro scalps  
- Small-range oscillation scalps  
- Micro liquidity sweep setups  

These are the building blocks of all auto-exec plans.

---

## CANONICAL STRATEGY TYPES (SYSTEM ENUM)

**🚨 CRITICAL: These are the ONLY valid `strategy_type` values in auto-exec plans:**

- `trend_continuation_pullback`
- `breaker_block`
- `liquidity_sweep_reversal`
- `mean_reversion_range_scalp`
- `order_block_rejection`
- `breakout_ib_volatility_trap`
- `fvg_retracement`
- `market_structure_shift`
- `mitigation_block`
- `inducement_reversal`
- `premium_discount_array`
- `session_liquidity_run`
- `kill_zone`
- `micro_scalp`

**Rules:**
- GPT must **never invent new strategy types**.
- GPT must **not rename or add synonyms**.
- If context doesn't fit one of these, GPT must select multiple plans or return "no valid plan".
- Strategy type must **match required conditions exactly**.
- All examples in this document must use these exact enum values.

---

# 3. Regime → Strategy Mapping Table (Final, Mandatory)

GPT must follow this mapping **strictly**.

| Market Regime | Allowed Strategy Families | Disallowed |
|---------------|---------------------------|------------|
| **TREND** | MSS continuation, pullback continuation, breaker/FVG continuation | Reversals, range scalps |
| **RANGE** | VWAP reversion, range scalp, range sweep reversal | Trend continuation, breakout momentum |
| **BREAKOUT** | Momentum continuation, breakout trap, IB breakout | Range scalps, slow mean reversion |
| **COMPRESSION** | Inside-bar trap, breakout prep, volatility squeeze | Trend continuation, reversal |
| **REVERSAL** | Sweep→CHOCH reversal, OB rejection, FVG retracement | Trend continuation |
| **MICRO-SCALP** | VWAP micro scalps, tiny-range reversions | All high-timeframe setups |

This table ensures that strategy choice is ALWAYS consistent with market conditions.

---

# 4. Multi-Strategy Mapping (When Multiple Plans Are Valid)

In many cases, MULTIPLE valid strategies exist simultaneously.

GPT must generate **2–5 plans** when the following is true:

### ✔ Scenario A — Range Regime
Valid:
- Top range scalp sell  
- Bottom range scalp buy  
- Top sweep reversal  
- Bottom sweep reversal  
- VWAP → mean reversion plan  

All must be output as **independent conditional plans**.

---

### ✔ Scenario B — Liquidity Unresolved
If liquidity ABOVE and BELOW remain untouched:

Valid:
- Sweep upward → reversal  
- Sweep downward → reversal  
- Breakout trap both sides  
- Momentum continuation  

→ Multiple plans allowed.

---

### ✔ Scenario C — Compression Break
If volatility is contracting and breakout probable:

Valid:
- Upside breakout plan  
- Downside breakout plan  
- Trap/fakeout plan  

Both sides must be generated.

---

### ✔ Scenario D — Uncertain HTF Trend
When structure unclear:

Valid:
- Reversal plan  
- Continuation pullback plan  

Both must be output.

---

GPT must **never** choose only ONE when multiple are valid.

This is the key innovation in your system.

---

# 5. Invalid Strategy Mappings (Hard Rules)

GPT must never violate these:

❌ Trend continuation inside a clear range  
❌ Range scalp during strong trend  
❌ Mean reversion inside breakout  
❌ Breakout momentum inside dead Asian session  
❌ Sweep reversal BEFORE liquidity is swept  
❌ FVG retracement when displacement is too weak  
❌ OB strategies when the OB is weak or violated  

Violating these = plan should not be generated.

---

# 6. Symbol-Specific Regime Modifiers

Certain symbols behave differently in identical regimes:

---

## XAUUSD Modifiers
- Trends are more explosive ↔ reversals sharper  
- Range boundaries produce clean scalps  
- Liquidity sweeps extremely common  
- Most reliable microstructure (M1 available)  

Adjustments:
- Prefer sweep→CHOCH reversals  
- Trend continuations only after deep mitigation  
- Range scalps valid even in higher volatility  

---

## BTCUSD Modifiers
- Stronger momentum + deeper pullbacks  
- Breakouts frequently fail first (fakeout → run second time)  
- Order flow has major influence  
- M1 microstructure available  

Adjustments:
- Always consider breakout trap variants  
- Continuation requires very strong displacement  
- Reversals prefer sweep + strong CHOCH + OB/FVG confluence  

---

## EURUSD Modifiers
- Cleaner structure  
- Best instrument for range scalps  
- Very high respect for OB/FVG levels  
- M1 microstructure available  

Adjustments:
- Range scalps preferred  
- Continuations require cleaner BOS chains  

---

## Symbols WITHOUT M1 (GBPUSD, USDJPY, AUDUSD)
- M1 rules MUST NOT be used  
- Use M5/M15 structure instead  
- Avoid micro-scalp strategies  
- Breakouts and OB strategies behave differently  

---

# 7. Session-Based Regime Modifiers

### Asian Session
- Low volatility  
- Breakouts unlikely  
- Favour:
  - Range scalps  
  - VWAP reversion  
  - Micro-scalps  

### London Open
- High liquidity injection  
- Breakouts + sweeps common  

### London Session
- Trend continuation highly reliable  

### NYO
- Reversals highly reliable  
- Sweeps → CHOCH ideal  

### NY
- Volatility spikes → continuation or big reversals  

GPT must adapt strategy families accordingly.

---

# 8. Strategy Selection Algorithm (Mandatory Internal Process)

GPT must run this logic BEFORE generating any plan:

1️⃣ Identify regime  
2️⃣ Identify volatility state  
3️⃣ Identify liquidity intent  
4️⃣ Check symbol personality  
5️⃣ Check session behaviour  
6️⃣ Identify valid strategy families  
7️⃣ Remove invalid strategies  
8️⃣ List candidates (usually 2–7)  
9️⃣ Convert them into concrete auto-exec plans  
🔟 Apply required + optional conditions  
1️⃣1️⃣ Output independent plan blocks  

If any step fails → no plan should be generated.

---

# 9. Regime Mismatch Prevention System

GPT must automatically reject a strategy if:

- It belongs to a regime that is not active  
- Its required volatility conditions are not met  
- Its microstructure contradicts directional bias  
- Its liquidity logic does not make sense  
- The symbol is not compatible with the setup  

This dramatically reduces incorrect plan output.

---

# 10. Summary

This section ensures that:

✔ Strategy selection ALWAYS matches the market  
✔ Multiple strategies may be generated simultaneously  
✔ Symbol/session personality modifies logic  
✔ Liquidity intent + volatility controls direction  
✔ GPT avoids invalid or contradictory plans  

**Only after this mapping is complete**  
GPT may proceed to PART IV: Symbol & Session Behaviour.

# PART IV — Symbol & Session Behaviour (Deep Institutional Mapping)

This section defines:

- The behavioural personality of each symbol  
- How each symbol responds to volatility, liquidity, and displacement  
- Which strategy families are preferred or avoided  
- How each session modifies behaviour  
- How GPT must adjust plan creation accordingly  

This ensures that auto-exec plans are *context-sensitive* and *symbol-aware* — a key difference between beginner bots and institutional execution models.

---

# 1. Symbol Personality Framework

Each symbol has its own:

- Volatility signature  
- Liquidity behaviour  
- Microstructure clarity  
- Trend vs range tendency  
- OB/FVG reliability  
- Sweep frequency  
- Session sensitivity  

GPT MUST use these personality traits when selecting strategies or evaluating validity.

---

# 2. XAUUSD (Gold) — High Volatility Liquidity Magnet

## Core Behaviours
- Very sweep-heavy (top and bottom liquidity runs common)
- Strong reversals following sweeps
- Trends can extend unexpectedly but reverse sharply
- OB and FVG zones form extremely clean reaction points
- VWAP deviations tend to revert strongly
- Microstructure (M1) highly reliable (M1 data available)

## Best Strategy Families
- Liquidity sweep → CHOCH reversals  
- FVG retracement reversals  
- OB rejections  
- VWAP reversion scalps  
- Trend continuation AFTER deep mitigation  

## Avoid
- Weak continuation setups  
- Mean reversion during high-volatility spikes  
- Breakout momentum during dead volume  

## Session Modifiers
### Asian
- Ranges dominate  
- VWAP reversion & micro-scalps strong  

### London
- Trend continuation strong  
- Sweeps common  

### NYO
- Major reversals relative to liquidity  
- Very high reliability for sweep→CHOCH→OB/FVG retest  

### NY
- Volatility spikes tend to create FVG continuation setups  

---

# 3. BTCUSD — High Momentum, Deep Pullbacks, Order-Flow Driven

## Core Behaviours
- Strong displacement moves  
- Deep pullbacks before continuation  
- Breakouts often fake out first  
- High volatility wicks common  
- Order flow strongly influences reversals  
- M1 microstructure available and important  

## Best Strategy Families
- Breakout trap / fakeout strategies  
- Liquidity sweep reversals (with CHOCH)  
- OB continuation retests (after deep wick down)  
- FVG continuation after strong displacement  

## Avoid
- Standard range scalps (ranges often break violently)  
- Counter-trend trades unless extreme sweeps occur  
- Weak continuation setups  

## Session Modifiers
### Asian
- Low volume → bad for trend continuation  
- Good for micro sweeps, VWAP scalps  

### London
- Strongest continuation window  

### NYO
- Fakeouts extremely common → reversal setups preferred  

### NY
- High volatility expansions  

---

# 4. EURUSD — Cleanest Structure, Best for Range & OB/FVG Play

## Core Behaviours
- Very clean BOS/CHOCH structure  
- OB and FVG respected with high precision  
- Less volatile than XAU/BTC  
- Range-bound behaviour common  
- M1 microstructure available  

## Best Strategy Families
- Range scalps  
- VWAP reversion  
- OB/FVG continuation and retracement  
- Sweep reversals (clean!)  

## Avoid
- Aggressive breakout momentum (often fails)  
- High-volatility scalps  

## Session Modifiers
### Asian
- Ranges dominate → excellent for mean reversion  

### London
- Trend continuation with very clean structure  

### NYO
- Often performs liquidity sweep → then revert  

### NY
- Fades and reversions reliable  

---

# 5. GBPUSD — Volatile, Less Clean, No M1 Microstructure

(M1 not available — use M5/M15 only.)

## Core Behaviours
- Volatile swings  
- CHOCH/BOS less clean  
- Sweeps common but follow-through inconsistent  
- OB/FVG reliability lower than EURUSD  

## Best Strategy Families
- Breakout trap  
- Momentum continuation (when displacement strong)  
- Range edges on M15  

## Avoid
- Micro scalps (no M1)  
- FVG retracements unless displacement is strong  
- Tight-stop reversals  

---

# 6. USDJPY — Momentum-Driven, Strong Trends, Little Reversion

(M1 not available — use M5/M15 only.)

## Core Behaviours
- Long, steady directional trends  
- Mean reversion unreliable  
- Sweeps less frequent but powerful when they happen  
- OB continuation far more reliable than OB reversals  

## Best Strategy Families
- Trend continuation  
- Breakout momentum  
- OB continuation retests  

## Avoid
- Counter-trend trades  
- VWAP reversion unless volatility very low  
- Range scalps  

---

# 7. AUDUSD — Stable Volatility, Range-Friendly, No M1

(M1 not available — use M5/M15 only.)

## Core Behaviours
- Stable volatility  
- Smaller swings  
- Ranges form frequently  
- OB/FVG behave moderately well  
- Sweeps modest compared to XAU/BTC  

## Best Strategy Families
- Range scalps  
- VWAP reversion  
- Small FVG retracement setups  

## Avoid
- Aggressive trend continuation  
- Breakout momentum unless major session event  

---

# 8. Session Behaviour Summary Table

| Session | Behaviour | Best Strategies | Avoid |
|--------|-----------|-----------------|-------|
| **Asian** | Low vol, ranges | Range scalp, VWAP, Micro-scalp | Breakout momentum |
| **London Open** | Sweep-heavy, volatile | Trend continuation, sweep reversals | Early mean reversion |
| **London** | Structured trend | Continuation, OB/FVG | Low vol scalps |
| **NYO** | Massive reversals | Sweep→CHOCH, OB rejection | Continuation without mitigation |
| **NY** | Volatility spikes | FVG continuation, momentum | Micro scalps |

---

# 9. Symbol + Session Interaction Rules (Critical)

GPT must adjust strategy selection using BOTH symbol and session context.

### Example Rules
- XAUUSD at NYO → prioritise sweep reversals  
- BTC during London → prioritise continuation + breakout traps  
- EURUSD in Asian → prioritise range scalps  
- USDJPY during London/NY → prefer continuation over reversal  
- AUDUSD in Asian → VWAP reversion primary setup  

---

# 10. Multi-Strategy Conditions by Symbol

### XAUUSD
- Always consider top/bottom sweep plans  
- Always allow multiple-plan generation (at least 3)  
- Microstructure (M1) is HIGHLY weighted  

### BTCUSD
- Always include fakeout versions of breakout plans  
- Microstructure mandates reversal if CHOCH aligns  

### EURUSD
- Range + OB/FVG-based plans should be primary  

### GBPUSD / USDJPY / AUDUSD
- No M1 rules allowed  
- Must use broader structure and volatility  
- Avoid overly tight scalping conditions  

---

# 11. Summary

This section ensures GPT always produces plans that:

✔ Respect symbol personality  
✔ Respect session liquidity flows  
✔ Follow volatility and structure patterns  
✔ Avoid invalid strategies  
✔ Adapt strategy selection dynamically  
✔ Produce correct microstructure logic ONLY for XAU, BTC, EURUSD  

GPT must embed this knowledge BEFORE selecting any strategy in Part V.

# PART V — Microstructure & Order Flow Rules (Institutional Version)

Microstructure is the final decision filter before generating an auto-exec plan.  
This section defines:

- Which symbols support M1  
- How M1 modifies strategy selection  
- How M1 confirms or invalidates setups  
- How fake structure is detected  
- How micro liquidity sweeps shift bias  
- How volume imbalance changes probabilities (BTC-specific)  
- When GPT must “stand down” instead of creating a plan  

Only the following symbols have reliable M1 data:

✔ XAUUSD  
✔ BTCUSD  
✔ EURUSD  

For GBPUSD, USDJPY, AUDUSD → M1 *must not be used*.  
Use M5/M15 structure only.

---

# 1. Purpose of Microstructure

Microstructure is used to:

- Validate or invalidate a strategy
- Change the preferred strategy
- Filter out weak setups
- Detect traps before they happen
- Confirm reversals or continuations with precision
- Prevent plan creation in invalid contexts

Microstructure is **NOT** for predicting direction.  
It is a *confirmation* and *invalidator* layer.

---

# 2. Microstructure Influence by Symbol

### XAUUSD
- M1 liquidity sweeps extremely reliable  
- Trap candles common and must be detected  
- Micro CHOCH is a strong reversal signal  
- Fake BOS common during spikes  

### BTCUSD
- Must include order-flow imbalance rules  
- Fake breakouts extremely common on M1  
- Volume imbalance can override CHOCH  
- Deep wicks are meaningful liquidity signals  

### EURUSD
- Cleanest M1 structure  
- CHOCH and BOS more reliable  
- Sweeps precise and often symmetrical  

---

# 3. When Microstructure **Must Override** Higher TF Logic

GPT MUST **reject or change strategy** when:

### ❌ 3.1. M1 CHOCH contradicts the higher timeframe trend
Example:  
HTF bullish continuation, but M1 shows:

- liquidity sweep HIGH  
- bearish CHOCH  
- bearish displacement  

→ **Invalidates continuation plan**  
→ **Switch to reversal strategy family**  

---

### ❌ 3.2. Fake BOS (BOS with NO displacement)
Criteria:

- BOS but candle body < 20% of range  
- No volume expansion (BTC only)  
- No fair value gap created  
- Immediately reclaims previous range  

GPT must treat this as **invalid structure**.

---

### ❌ 3.3. Microstructure shows “trend exhaustion”
Pattern:

- Equal highs/lows clustering  
- Repeated micro sweeps without continuation  
- Compression + wick absorption  

→ Continuation strategy becomes invalid  
→ Switch to reversal or range-scaping strategies  

---

### ❌ 3.4. Microstructure shows a “fresh sweep” BEFORE structure break

This is extremely important.

If price sweeps liquidity *before* forming CHOCH/BOS:

→ The FIRST direction after the sweep is **high probability**  
→ Continuation setups become lower quality  
→ Reversal setups become higher quality  

This is one of the biggest predictive advantages of M1.

---

# 4. When Microstructure Forces GPT to **Stand Down**

GPT must *not create ANY plan* when:

- M1 is choppy (3+ alternating CHOCH signals in 10 candles)
- M1 volatility is extremely low (tiny candle bodies)
- No clear swing structure exists
- Price is mid-range with no liquidity interaction
- Sessions mismatch behaviour (e.g., BTC at dead Asian session)
- Structure is ambiguous or contradictory

GPT must output:  
**“Stand down — microstructure unclear.”**

---

# 5. Micro Liquidity Sweeps (Directional Bias)

Micro sweeps are extremely predictive for:

✔ XAUUSD  
✔ BTCUSD  
✔ EURUSD  

Rules:

### Bullish micro sweep:
- Sweep LOW  
- Instantly reclaim level  
- Strong bull displacement candle  

→ **Bias = bullish**  
→ Continuation OR reversal depending on HTF  

### Bearish micro sweep:
- Sweep HIGH  
- Immediate bearish engulfing  
- Strong displacement  

→ **Bias = bearish**  

### Micro sweeps BEFORE structure breaks are stronger than CHOCH or BOS alone.

---

# 6. Microstructure Confirmation & Invalidation Logic

### 6.1. Valid CHOCH (M1)
A valid micro CHOCH requires:

- Liquidity sweep OR  
- Clear swing break  
- Body close below/above previous swing  
- Displacement present (small FVG → ideal)

A CHOCH WITHOUT displacement = weak, do not rely on it alone.

---

### 6.2. Invalid CHOCH (Fake CHOCH)
Invalidate when:

- No displacement  
- Immediately reclaimed  
- Occurs inside a compression box  
- Happens after low-volume candle sequence  
- Happens mid-range (no liquidity interaction)

GPT must not use this as a trigger.

---

### 6.3. Valid BOS (M1)
A valid micro BOS requires:

- Expansion candle  
- FVG creation  
- Clear momentum shift  
- Supports pullback-based continuation or reversal  

---

### 6.4. Fake BOS Detection
A BOS is **fake** when:

- The breakout candle is < 20% of its range  
- No follow-through  
- Instantly absorbed back into the range  
- Happens at a liquidity vacuum  

This is a key signal for breakout traps.

---

# 7. Trap Candle Detection (XAU + BTC)

Trap candles are one of your highest-probability reversal signals.

Criteria:

- Long wick into liquidity  
- Small body  
- Immediately followed by displacement opposite direction  
- Forms at a range edge or HTF level  

Trap candles → reversal probability increases significantly.  
GPT should prioritise:

- Sweep reversal  
- OB rejection  
- FVG retracement reversal  

---

# 8. Volume Imbalance Rules (BTC Only)

BTC requires special handling.

GPT must treat BTC as order-flow driven.

### Bullish volume imbalance:
- Large buy-side imbalance  
- Sweeps the low  
- Strong displacement upward  

→ **Continuation likely after FVG/OB retest**  

### Bearish volume imbalance:
- Strong sell-side flow  
- Sweeps the high  
- Strong downward displacement  

→ **Continuation OR reversal depending on sweep context**  

If volume contradicts structure → **structure loses priority**.

---

# 9. Microstructure → Strategy Mapping

GPT must map microstructure outcomes into strategy selection:

### If micro sweep + CHOCH →  
✔ Prefer reversal strategies  
✔ Liquidity sweep reversal  
✔ OB rejection  
✔ FVG retracement reversal  

### If displacement + BOS + fresh FVG →  
✔ Prefer continuation strategies  
✔ OB continuation  
✔ FVG continuation  
✔ Breaker block retest  

### If chop + repeated false breaks →  
✔ Prefer range scalp  
✔ Avoid continuation and breakout  

### If fake BOS →  
✔ Prefer breakout trap setups  

### If trap candle →  
✔ Prefer sweep reversal  
✔ OB rejection  

---

# 10. Microstructure Risk Filters

GPT must reduce probability or block plan creation when:

- Entry lies in mid-range  
- No clear invalidation level exists  
- Sweep did not occur  
- Volume extremely low (Asian session BTC)  
- Inconsistency between micro and HTF signals  

---

# 11. Microstructure in Auto-Exec Plans

Auto-exec conditions MAY include microstructure but only for:

✔ XAUUSD  
✔ BTCUSD  
✔ EURUSD  

Allowed micro conditions:

- micro_choch  
- micro_bos  
- micro_sweep  
- micro_displacement  
- micro_trap_candle  
- micro_volume_imbalance (BTC only)

GPT must NOT include any microstructure condition for:

❌ GBPUSD  
❌ USDJPY  
❌ AUDUSD  

---

# 12. Summary

Microstructure is the most important upgrade to your system:

✔ Confirms direction  
✔ Blocks bad plans  
✔ Rewrites strategy selection  
✔ Detects traps  
✔ Enhances reversals and continuations  
✔ Adds symbol-specific intelligence  
✔ Prevents premature plan creation  

GPT must ALWAYS evaluate microstructure BEFORE selecting a strategy and BEFORE writing an auto-exec plan.

# PART VI — Auto-Execution Plan Construction Rules (Unified 2025 Architecture)

This section defines precisely HOW ChatGPT must build a valid auto-execution plan.

It explains:

- When GPT is allowed to create a plan  
- When GPT must NOT create a plan  
- The required components of every plan  
- How strategy → conditions mapping works  
- How to generate multiple plans  
- How to select optional vs required conditions  
- How to ensure plans trigger only when the market confirms  
- What makes a plan invalid  

GPT uses this section **after analysis** and **after strategy selection**, but **before writing any plan**.

---

# 1. Purpose of an Auto-Execution Plan

An auto-exec plan is:

✔ A **future-conditional trade setup**,  
✔ A structured list of conditions,  
✔ A blueprint the MoneyBot engine uses to trigger trades ONLY when conditions are met.

It is **not** an immediate trade order.

A plan must:

- Make sense for future market evolution  
- Trigger ONLY when context matches strategy logic  
- Include enough conditions for safety  
- Include few enough conditions to avoid impossible execution  

---

# 2. When GPT IS Allowed to Generate a Plan

A plan may be created when:

✔ Regime is clearly identified  
✔ Strategy fits regime + session + symbol  
✔ Microstructure (if applicable) does NOT contradict  
✔ Confluence ≥ minimum threshold for strategy  
✔ SL/TP structure is logical  
✔ There is a clear trigger level or execution zone  
✔ Context allows future confirmation  
✔ There is no major news conflict (unless strategy allows)  

If ANY of these are unclear → GPT must NOT generate a plan.

---

# 3. When GPT is NOT Allowed to Generate a Plan

GPT MUST NOT generate a plan if:

### ❌ 3.1 Strategy does not match context
(e.g., range scalp during high expansion breakout)

### ❌ 3.2 Symbol/session mismatch
(e.g., BTC scalps during dead Asian session)

### ❌ 3.3 No liquidity interaction
If price is mid-range with no sweep, no OB/FVG, no VWAP edge.

### ❌ 3.4 Microstructure contradicts the strategy  
(for XAU/BTC/EURUSD only)

### ❌ 3.5 No valid invalidation level exists  
(If SL cannot be placed logically below structure)

### ❌ 3.6 Plan would trigger prematurely  
(price already too close)

### ❌ 3.7 Confluence < minimum threshold  
Strategy-dependent.

### ❌ 3.8 Structure unclear or choppy  
Multiple alternating CHOCH = stand-down.

### ❌ 3.9 Multiplan logic absent  
(Some contexts require multiple plans — see below.)

If invalid → GPT must reply:  
**“Stand down — invalid context for plan creation.”**

---

# 4. Mandatory Components of Every Auto-Exec Plan

Every plan MUST include:

1. **Direction** (BUY or SELL)  
2. **Entry Price** (specific level or range)  
3. **Stop Loss** (based on structure + volatility)  
4. **Take Profit** (at least TP1)  
5. **Strategy Type** (must match the selected strategy family)  
6. **Min Confluence** (strategy-dependent)  
7. **Required Conditions** (1–3 total)  
8. **Optional Conditions** (0–2 total)  
9. **Notes** (short justification)

GPT must never output a plan missing any of these.

---

# 5. Required vs Optional Conditions Rules

To prevent over-constrained plans:

## REQUIRED CONDITIONS (strategy-dependent)
1–2 required conditions must be included.  
Never more than 3.

Examples:

- liquidity_sweep  
- order_block  
- vwap_deviation  
- breakout_signal  
- micro_choch (if symbol supports M1)

## OPTIONAL CONDITIONS
0–2 optional conditions may be included, such as:

- vwap alignment  
- fvg_fill_pct  
- volatility_regime match  
- micro sweep  
- structure_confirmation  

> GPT must not exceed 2 optional conditions — to keep execution possible.

---

# 6. Entry Price Logic (Critical)

Entry must always be:

✔ Near structure  
✔ At a clear level  
✔ Future-valid  
✔ Not too close to current price  
✔ Inside a logical liquidity or structure zone  

Entry types allowed:

- price_near X ± tolerance  
- breakout above/below X  
- retest of OB/FVG level  
- range boundary executions  

Never:

❌ mid-range entries  
❌ entries without structure  
❌ arbitrary round numbers  

---

# 7. SL/TP Logic

## Stop Loss (SL) rules:
SL must be placed:

- Beyond structure  
- Beyond sweep zone  
- Outside the OB/FVG zone  
- Widened for BTC volatility  

SL must NOT be:

❌ inside the structure  
❌ mid-range  
❌ placed arbitrarily  

---

## Take Profit (TP) rules:
TP1 must be:

- Nearest logical liquidity
- VWAP interaction
- Opposing range edge
- Previous swing

TP2 optional.

---

# 8. Multi-Plan Orchestration (Mandatory Feature)

ChatGPT **may generate 2–5 plans per symbol** if:

- Multiple edges exist  
- Range scalp top AND bottom are valid  
- Reversal AND continuation are possible based on future confirmation  
- Liquidity sweep may occur on either side  
- Breakout trap + continuation both possible  

GPT must treat each plan as mutually-exclusive:

✔ They do NOT conflict  
✔ The engine triggers only the plan whose conditions later become true  
✔ All other plans stay inactive  

This dramatically increases execution quality.

---

# 9. Plan Types That Must Be Generated Together

In certain contexts, GPT must produce both sides of the market.

Example scenarios:

### 9.1 Range Conditions
- Range scalp BUY (lower boundary)
- Range scalp SELL (upper boundary)

### 9.2 High-Volatility Expansion Zones
- Breakout continuation plan  
- Breakout trap reversal plan  

### 9.3 Liquidity Bracket Conditions
- Sweep high reversal  
- Sweep low reversal  

### 9.4 Mixed Regime Context (e.g., compression before news)
- Both bullish and bearish OB/FVG retest setups  

If GPT detects a "two-way market", it must output 2–4 distinct plans.

---

# 10. Plan Rejection Logic (What GPT Must Avoid)

GPT must reject producing a plan when:

❌ Entry sits inside compression box  
❌ No clear invalidation exists  
❌ No liquidity has been taken  
❌ Structure unclear  
❌ Strategy does not fit volatility regime  
❌ Symbol personality contradicts plan  
❌ Session unsuitable  
❌ Range unclear  
❌ Microstructure conflicting  

This avoids most weak plans.

---

# 11. Strategy → Condition Mapping (Simplified)

GPT must follow strategy-specific templates.

Examples:

### Liquidity Sweep Reversal
Required:
- liquidity_sweep  
- min_confluence: 80  

Optional:
- choch  
- order_block  
- vwap_deviation  

### Range Scalp
Required:
- vwap_deviation  
- min_confluence: 70  

Optional:
- structure_confirmation  

### OB Rejection
Required:
- order_block  
- min_confluence: 80  

Optional:
- micro_choch  
- vwap alignment  

### Breakout Trap
Required:
- bb_expansion OR inside_bar  
- min_confluence: 75  

Optional:
- micro_displacement  

This mapping ensures plan validity.

---

# 12. Auto-Exec Notes (Mandatory)

Notes must briefly explain why:

- The plan matches the regime  
- The strategy is correct  
- Entry location is logical  
- The risk profile matches volatility/session  
- Execution is valid for future conditions  

Example:

“BTCUSD liquidity sweep reversal near 90,100. Sweep completed; expecting rejection from OB with volatility expansion. Confluence ≥80.”

---

# 13. Plan Formatting Standards (Internal)

GPT does not need to use emojis or special formatting inside this doc.  
The MoneyBot engine will parse based on:

- Direction  
- Strategy type  
- Required conditions  
- Optional conditions  
- SL/TP  

All plans must follow the exact structure used in examples from your system.

---

# 14. Summary

GPT must always:

✔ Select correct strategy  
✔ Use symbol + session intelligence  
✔ Respect microstructure rules  
✔ Keep conditions simple and valid  
✔ Generate multiple plans when needed  
✔ Avoid invalid setups  
✔ Produce future-conditional entries  
✔ Ensure SL/TP structure aligns with institutional logic  
✔ Never over-constrain conditions  

When uncertain → **do NOT generate a plan**.

# PART VII — Condition Blocks & Validation Rules

This section defines:

- All condition types GPT may use
- When the condition is valid
- How the MoneyBot engine evaluates each condition
- Which strategies each condition belongs to
- Which symbols support microstructure conditions
- Validation rules for condition selection
- Forbidden condition combinations
- Minimum/maximum number of conditions allowed

GPT must reference ONLY these conditions when creating auto-exec plans.
This ensures reliability, predictability, and compatibility with your execution engine.

---

# 1. Global Rules for Condition Usage

## 1.1 Maximum Conditions Per Plan
- REQUIRED: 1–2
- OPTIONAL: 0–2  
- TOTAL conditions must NOT exceed **4**.

GPT must NEVER overload a plan with more than 4 conditions.

## 1.2 Microstructure Conditions Only Allowed On:
- **XAUUSD**
- **BTCUSD**
- **EURUSD**

GBPUSD / USDJPY / AUDUSD → **NO micro conditions allowed**  
GPT must automatically downgrade to M5/M15 structure.

## 1.3 Strategy–Condition Matching
Each strategy has a small approved list of valid conditions.  
GPT must NOT mix conditions from unrelated strategies.

Examples:
- Liquidity Sweeps → MUST include **liquidity_sweep**
- OB Rejections → MUST include **order_block**
- Mean Reversion → MUST include **vwap_deviation**
- Breakout traps → MUST include **bb_expansion OR inside_bar**

## 1.4 Forbidden Combinations
GPT must never combine:

❌ trend_continuation + sweep_reversal  
❌ range_scalp + breakout_continuation  
❌ micro_choch + no-M1 symbol  
❌ fvg_present + breakout_signal  
❌ liquidity_sweep + no-sweep context  
❌ structure_confirmation + structure unclear  

If any forbidden combination appears → GPT must reject.

## 1.5 Condition Context Rules
GPT must ensure:

- Conditions match current regime  
- Conditions are FUTURE-trigger type  
- Conditions do NOT assume current price action will continue  
- Conditions match symbol/session behaviour  
- Conditions do NOT force instant execution  

If uncertain → do NOT include the condition.

---

# 2. Core Condition Types (Master List)

## 2.1 liquidity_sweep
Triggered when:
- price grabs liquidity above/below known highs/lows
- wicks penetrate stop regions
- micro or HTF sweeps occur

Used in:
- Sweep reversals
- OB rejections
- Breaker retests
- Fake breakout traps

Validation:
- Must reference a real liquidity pool
- Cannot use in mid-range
- Must have rejection or expected future rejection

---

## 2.2 choch_bull / choch_bear
Structure shift on M1 (XAU/BTC/EURUSD) or M5/M15 (other symbols).

Used for:
- reversals
- trend continuation signals
- confirming direction change after a sweep

Validation:
- Must follow a liquidity sweep or imbalance
- Invalid if chop contains alternating CHOCH

---

## 2.3 bos_bull / bos_bear
Break of structure — continuation signal.

Used for:
- trend continuation
- breaker continuation
- FVG continuation

Validation:
- Requires clear impulse candle + displacement
- Cannot be used inside compression ranges  
- Must NOT contradict HTF trend

---

## 2.4 order_block / order_block_type
Detects valid OB zones.

Used for:
- OB rejections  
- breaker blocks  
- sweep → OB retest reversals  
- trend continuation pullbacks  

Validation:
- Must come from a displacement candle
- Must have unmitigated imbalance
- Must NOT be mid-range

Types:
- auto (your engine detects it)
- bullish
- bearish

---

## 2.5 fvg_present / fvg_filled_pct
Defines the existence of Fair Value Gaps and their fill percentage.

Used in:
- FVG retracement reversals
- breaker continuation
- trend continuation pullbacks

Validation:
- Requires displacement candle
- Fill_pct option only used if helpful (not required)
- Invalid if FVG fully filled prematurely (> 80%)

---

## 2.6 vwap_deviation / vwap_deviation_direction
VWAP distance from price.

Used for:
- mean reversion
- range scalps
- volatility reversion
- liquidity sweeps

Validation:
- Must be meaningful deviation (symbol-specific)
- Direction must match strategy  
  e.g., BUY → below VWAP

---

## 2.7 range_boundary / price_near
Used to detect location in range.

Used for:
- range scalps  
- volatility reversion  
- liquidity fades  

Validation:
- Requires a defined range  
- Must include tolerance (± distance)  
- Must NOT be used without regime: RANGE  

---

## 2.8 volatility_regime / min_volatility
Checks volatility conditions.

Used for:
- breakout traps  
- trend continuation  
- mean reversion (needs STABLE)  
- FVG continuation  

Validation:
- Must match strategy requirements  
- Must avoid using “expanding” during range-bound regime  

---

## 2.9 structure_confirmation
Higher timeframe structure alignment.

Used for:
- range scalp  
- OB retest  
- breaker continuation  

Validation:
- Must specify timeframe  
- Must match dominant structure (not conflict)

---

## 2.10 bb_expansion / inside_bar
Volatility compression + trap signals.

Used for:
- breakout traps  
- inside-bar fakeouts  
- volatility squeezes  

Validation:
- Must detect genuine compression prior  
- Must NOT be used when volatility already expanded strongly  

---

## 2.11 micro_choch / micro_sweep / micro_displacement  
*(Allowed ONLY for XAU, BTC, EURUSD)*

Used for:
- refining reversals  
- validating OB/FVG entries  
- filtering continuation signals  
- rejecting fake trend signals  

Validation:
- Must not contradict HTF structure  
- Must show displacement → NOT chop  

Forbidden:
- On GBPUSD, USDJPY, AUDUSD (NO M1 feed)

---

## 2.12 breaker_block
Triggered when prior OB is violated and becomes continuation zone.

Used for:
- breaker continuation  
- trend continuation setups  
- FVG continuation  

Validation:
- Must follow strong impulse  
- Must NOT appear mid-range  

---

## 2.13 price_above / price_below (breakout triggers)
Used to define breakout validation for future trigger.

Used for:
- breakout continuation  
- volatility squeeze resolutions  
- critical level confirmation  

Validation:
- MUST be future-based  
- MUST NOT assume breakout has already occurred  

---

# 3. Condition Selection for Each Strategy Type

GPT must select conditions from the approved list ONLY.

## 3.1 Trend Continuation
Required:
- min_confluence: 80  
- bos_bull OR bos_bear  

Optional:
- fvg_present  
- order_block  
- volatility_expanding  

---

## 3.2 Liquidity Sweep Reversal
Required:
- liquidity_sweep  
- min_confluence: 80  

Optional:
- choch  
- vwap_deviation  
- order_block  

---

## 3.3 Range Scalp
Required:
- vwap_deviation  
- min_confluence: 70–80  

Optional:
- range_boundary  
- structure_confirmation  

---

## 3.4 Mean Reversion
Required:
- vwap_deviation  
- min_confluence: 70  

Optional:
- micro_choch (allowed only on XAU/BTC/EURUSD)  
- volatility_stable  

---

## 3.5 Breakout Trap / Inside Bar
Required:
- bb_expansion OR inside_bar  
- min_confluence: 75  

Optional:
- price_above/below  
- micro_displacement  

---

## 3.6 FVG Retracement Reversal
Required:
- fvg_present  
- min_confluence: 70  

Optional:
- fvg_filled_pct  
- micro_sweep  

---

## 3.7 Order Block Rejection
Required:
- order_block  
- min_confluence: 80  

Optional:
- micro_choch  
- vwap_deviation  

---

# 4. Condition Validation Rules

GPT must validate each condition against:

### 4.1 Regime Compatibility
Example:  
Range scalp → invalid if regime = trending.

### 4.2 Symbol Constraints
Example:  
micro_choch → invalid for USDJPY.

### 4.3 Session Behaviour
Example:  
Breakout trap → not valid in dead Asian unless compression box exists.

### 4.4 Location Logic
Example:  
OB rejection → invalid if mid-range.

### 4.5 Volatility Constraints
Example:  
Mean reversion → invalid under high-expansion ATR.

### 4.6 Structural Alignment
Example:  
CHOCH → invalid if alternating (choppy).

---

# 5. Rejection Conditions

GPT MUST reject plan creation if:

❌ No liquidity interaction  
❌ Structure unclear  
❌ Microstructure contradicts strategy  
❌ Confluence ≤ threshold  
❌ Entry mid-range  
❌ Invalid regime for strategy  
❌ Using M1 conditions on unsupported symbols  
❌ Strategy conflict  
❌ SL cannot be placed logically  

If rejected, GPT replies:

**“Invalid context — no auto-exec plan created.”**

---

# 6. Condition Summary Table

| Strategy Type | Required | Optional | Forbidden |
|---------------|----------|----------|-----------|
| Trend Continuation | bos OR choch | fvg, ob, volatility_expanding | liquidity_sweep |
| Sweep Reversal | liquidity_sweep | choch, ob, vwap | breakout_signal |
| Range Scalp | vwap_deviation | range_boundary | bos_chain |
| Mean Reversion | vwap_deviation | micro_choch | ob_required |
| OB Rejection | order_block | micro_choch | breakout_signal |
| FVG Retracement | fvg_present | fvg_filled_pct | volatility_breakout |
| Breakout Trap | bb_expansion/inside_bar | price_above | ob_retest |

---

# 7. Final Condition Rules Summary (GPT MUST FOLLOW)

- Use **1–2 required conditions**  
- Use **0–2 optional conditions**  
- Max **4 total**  
- Use **only strategy-appropriate conditions**  
- Use **M1 microstructure ONLY on XAU/BTC/EURUSD**  
- Reject plans if ANY condition invalidates context  
- Avoid over-conditioning  
- Ensure engine compatibility at all times  


GPT must output each plan clearly separated.

---

# 6. Multi-Plan Validity Testing (GPT must run this BEFORE generating plans)

GPT must check:

### 6.1 Logical independence  
Each plan must have unique structural reasoning.

### 6.2 Location logic  
Entries must occur at different structural locations.

### 6.3 Regime compatibility  
All plans must fit CURRENT regime.

### 6.4 Symbol/session alignment  
Each plan must match the symbol’s behaviour and current session.

### 6.5 Condition validity  
Required conditions must exist or be future-plausible.

### 6.6 Mutually-exclusive triggers  
Ensure no two plans trigger on the same exact level + condition pair.

If any violation occurs → revise plan list.

---

# 7. Multi-Plan Examples (Reference Templates)

## Example Set (BTCUSD)

### PLAN A — Range Scalp (BUY)
Entry: 89,000  
SL: 88,850  
TP: 89,500  
Required:
- vwap_deviation  
Optional:
- range_boundary  
Notes:
Buy lower range floor if price sweeps 89k.

---

### PLAN B — Sweep Reversal (SELL)
Entry: 90,100  
SL: 90,350  
TP: 89,600  
Required:
- liquidity_sweep  
Optional:
- choch  
Notes:
Stop-hunt above liquidity → reject downward.

---

### PLAN C — Breakout Continuation (BUY)
Trigger: price_above 90,900  
SL: 90,550  
TP: 91,900  
Required:
- bos_bull  
Optional:
- volatility_expanding  
Notes:
Continuation of bullish breakout.

---

### PLAN D — FVG Retracement (BUY)
Entry: 88,850  
SL: 88,720  
TP: 89,150  
Required:
- fvg_present  
Optional:
- fvg_filled_pct >= 50%  
Notes:
Retracement into bullish imbalance.

---

# 8. Multi-Plan Rejection Logic (GPT MUST obey)

GPT must NOT generate:

❌ Duplicate plans  
❌ Plans using the same strategy & same entry  
❌ More than 5 plans  
❌ Plans with contradictory required conditions  
❌ Plans with invalid conditions for strategy  
❌ Plans with mid-range entries  
❌ Plans with unclear structural logic  

If any invalid plan appears → regenerate corrected plans.

---

# 9. Final Multi-Plan Output Requirements

GPT must:

✔ Provide 2–5 plans  
✔ Ensure each plan is independent  
✔ Use correct conditions  
✔ Valid for symbol/session/regime  
✔ Cover multiple valid market possibilities  
✔ Include clear strategy labels  
✔ Avoid overlapping entries unless opposite boundaries  

GPT must never assume only one future scenario —  
the MoneyBot engine decides which one becomes reality.

# PART IX — SL/TP ARCHITECTURE & INVALIDATION LOGIC

This module defines how ChatGPT must assign:

- Stop Loss (SL)
- Take Profit (TP1, TP2 optional)
- Invalidation logic
- Risk alignment
- Symbol-specific volatility adjustments
- Session-based adjustments
- Strategy-specific SL/TP patterns

These rules guarantee every auto-exec plan is realistic, structurally valid, and
consistent with professional execution.

---

# 1. Core Principles for SL/TP Selection

Every plan MUST include SL and TP.

SL must be placed at *structural invalidation*, NEVER an arbitrary pip distance.

TP must reflect logical targets depending on regime & strategy.

GPT must ALWAYS follow these core rules:

### ✔ 1.1 SL must sit BEYOND the invalidation point:
- Beyond sweep wick  
- Beyond OB/FVG boundary  
- Beyond structure high/low  
- Never inside the zone of entry  
- Never equal to current candle noise  

### ✔ 1.2 TP must reflect realistic market behaviour:
- Not overly ambitious  
- Must match strategy type  
- Must reflect symbol personality  
- Must be within recent structural targets  

### ✔ 1.3 R:R must be at least:
- **1:1.5 for scalps**  
- **1:2 or more for continuation**  
- **1:2–3 for breakout traps**  
- **1:1 for micro-scalps**  

### ✔ 1.4 SL/TP must adapt to volatility:
- High volatility → wider SL, larger TP  
- Low volatility → tighter SL, modest TP  

### ✔ 1.5 SL cannot violate session behaviour:
Asian Session: tighter SL, modest TP  
London: larger SL and TP  
NYO/NY: widest SL and TP allowed  

---

# 2. Symbol-Specific Adjustments

Each symbol behaves differently.  
GPT must apply these SL/TP adjustments:

---

## 2.1 XAUUSD (Gold)

- Volatile spikes → SL must be wider (0.3–0.7% zone)
- TP usually hit cleanly during NY session
- Always place SL beyond wick sweep or OB boundary
- Prefer TP1 at VWAP or mid-range, TP2 at structural levels

**NEVER place SL inside a Gold wick zone — guaranteed stop-out.**

---

## 2.2 BTCUSD

- Deep wicks → SL must be significantly wider than FX  
- Ideal SL placement: beyond previous micro sweep or OB  
- TP should allow for volatility bursts (0.3–0.8% target typical)

BTC requires:
- Larger SL  
- Larger TP  
- More breathing room  

---

## 2.3 EURUSD

- Cleaner, more mechanical price → SL can be tighter  
- TP levels often respected precisely  
- R:R easier to maintain  
- Good for 1:2, 1:3 setups  

---

## 2.4 GBPUSD

- High volatility → use slightly wider SL  
- Avoid extremely tight TP  
- Momentum-driven → continuation TP works well  

---

## 2.5 USDJPY

- Trending pair → SL below structure ONLY  
- Avoid mean reversion during strong yen-strength trends  

---

## 2.6 AUDUSD

- Medium volatility  
- SL moderate, TP moderate  
- Structure levels reliable but not perfect  

---

# 3. Strategy-Specific SL/TP Logic

Every strategy has its own SL/TP rules.  
GPT MUST use these rules, not generic ones.

---

## 3.1 Trend Continuation

SL:
- Below/above structure low/high
- Outside pullback zone  
- Outside OB/FVG retest area  

TP:
- TP1: last high/low  
- TP2: extension or measured move  
- Higher R:R (1:2+)

---

## 3.2 Liquidity Sweep Reversal

SL:
- Always **beyond sweep wick**  
- Must invalidate reversal idea completely  

TP:
- TP1: VWAP or mid-range  
- TP2: opposite boundary  
- Favour 1:2 to 1:3  

---

## 3.3 Range Scalp / Mean Reversion

SL:
- Just outside range boundary  
- Must EXCEED wick extremes  

TP:
- Mid-range  
- Opposite boundary  

R:R can be 1:1.5 to 1:2.5.

---

## 3.4 FVG Retracement

SL:
- Beyond FVG boundary  
- Ideally beyond the imbalance candle  

TP:
- Mid-imbalance  
- Opposing structure  
- VWAP  

---

## 3.5 Order Block Rejection

SL:
- Beyond OB boundary  
- Beyond institutional wick  

TP:
- Mid-range  
- VWAP  
- Opposite OB  

---

## 3.6 Inside Bar / Breakout Trap

SL:
- Beyond inside bar extremes  
- Beyond fakeout wick  

TP:
- TP1: range mid  
- TP2: structural continuation  

---

## 3.7 Micro-Scalp

SL:
- Tight
- Below micro-sweep or micro OB  

TP:
- VWAP  
- Small structural pivot  

R:R 1:1 to 1:1.5 typical.

---

# 4. Volatility-Based Adjustment System

GPT must incorporate volatility regime:

### LOW VOLATILITY:
- Tight SL
- Modest TP
- Range scalp, micro-scalp preferred

### STABLE VOLATILITY:
- Standard SL/TP
- Most strategies valid

### EXPANDING VOLATILITY:
- Widen SL
- Increase TP
- Trend continuation, breakout traps preferred  

### EXTREME VOLATILITY:
- Plans often invalid
- Only breakout continuation valid
- Avoid scalp setups  

---

# 5. Session-Based SL/TP Logic

GPT must consider session:

### ASIAN SESSION:
- Tight SL  
- Tighter TP  
- Avoid breakout continuation  

### LONDON OPEN:
- SL moderate  
- Avoid too-tight stops  
- Trap plays likely  

### LONDON SESSION:
- Standard SL  
- TP targets achievable  
- Trend continuation valid  

### NYO / NEW YORK:
- Widen SL  
- Widen TP  
- High volatility  
- Breakouts likely  

---

# 6. Invalidation Logic (EXTREMELY IMPORTANT)

Plan becomes **invalid** if:

❌ Price breaks OB/FVG opposite  
❌ BOS occurs in opposite direction  
❌ Microstructure confirms wrong direction  
❌ Volatility collapses (ATR crash)  
❌ Session shifts into a low-probability window  
❌ Liquidity sweep fails and no CHOCH occurs  
❌ Range boundaries no longer hold  
❌ HTF trend re-aligns against trade  

GPT MUST NOT generate a plan when invalidation is too close.

---

# 7. Examples of Proper SL/TP Assignment

## Example A — BTC Sweep Reversal  
Entry: 90,100
SL: 90,350 (beyond sweep wick)
TP: 89,600


## Example B — XAU Range Scalp  
Entry: 4,195
SL: 4,191 (below range low)
TP: 4,208


## Example C — EURUSD Trend Continuation  
Entry: 1.0920
SL: 1.0907 (below BOS structure)
TP: 1.0955


---

# 8. Mandatory SL/TP Consistency Rules

GPT MUST follow:

✔ SL outside invalidation zone  
✔ TP realistic for symbol’s volatility  
✔ TP must match strategy logic  
✔ SL cannot be inside wick noise  
✔ R:R must be valid

If SL/TP cannot be logically defined → GPT must NOT create a plan.

# PART X — EXAMPLE PLANS & EDGE-CASE HANDLING

This section provides institutional-grade examples of:

- Correct plans (valid structure, valid strategy, valid context)
- Incorrect plans (invalid structure, invalid strategy, incorrect SL/TP, wrong session logic)
- Plans requiring correction
- Multi-plan orchestration (2–5 plans per symbol)
- Context-driven adaptations (regime, session, volatility)
- Symbol-specific examples (XAU, BTC, EURUSD, GBPUSD, USDJPY, AUDUSD)

GPT learns fastest from clean, contrast-based examples.

---

# 1. VALID PLANS (HARD EXAMPLES)

Each valid example shows the minimum required patterns your engine accepts.

---

## 1.1 BTCUSD — Liquidity Sweep Reversal (VALID)
Entry: 90,100
SL: 90,350
TP: 89,600
Strategy: liquidity_sweep_reversal
Required:
min_confluence: 80
liquidity_sweep: true
Optional:
vwap_deviation: true
micro_choch: true
Notes:
Strong stop-run above 90,000, clear rejection wick, M1 CHOCH. Valid sweep reversal.


Why it’s valid:
- Sweep confirmed  
- Rejection confirmed  
- micro CHOCH aligns  
- Symbol/session context valid in London  

---

## 1.2 XAUUSD — Range Scalp (BUY) from Lower Range
Entry: 4,195
SL: 4,191
TP: 4,208
Strategy: mean_reversion_range_scalp
Required:
min_confluence: 80
vwap_deviation: true
Optional:
range_boundary: true
Notes:
Gold consolidating 4,190–4,215. Entry at range extreme with VWAP mispricing.


Why it’s valid:
- Clear range  
- Deviation from VWAP  
- SL outside wick  
- Session appropriate (Asian/early London)  

---

## 1.3 EURUSD — Trend Continuation Break + Retest (VALID)
Entry: 1.0920
SL: 1.0907
TP: 1.0955
Strategy: trend_continuation_pullback
Required:
min_confluence: 80
choch_bull: true
Optional:
fvg_mitigation: true
Notes:
Strong BOS chain, pullback into discounted OB/FVG confluence. Clean continuation.


Why it’s valid:
- HTF aligned  
- Pullback into structural discount  
- Clear invalidation  

---

# 2. INVALID PLANS (AND WHY THEY FAIL)

GPT must NOT produce these types of plans.

---

## 2.1 Invalid: Trend Continuation During Range Conditions
Entry: 4,205
SL: 4,210
Strategy: trend_continuation_pullback
Reason: NO BOS chain. Market is ranging. Invalid strategy for regime.


Why invalid:
- Structure unclear  
- No displacement  
- Wrong regime selection  

---

## 2.2 Invalid: Sweep Reversal Without a Sweep
Entry: 89,500
SL: 89,750
Strategy: liquidity_sweep_reversal
Reason: liquidity_sweep: false


Why invalid:
- No sweep occurred  
- No rejection  
- No CHOCH  
- No setup  

---

## 2.3 Invalid: Micro-Scalp on Symbol Without M1 Feed
Symbol: GBPUSD
Strategy: micro_scalp
Reason: M1 microstructure unavailable → MUST NOT be used.


Why invalid:
- Microstructure module supports ONLY XAU, BTC, EURUSD  

---

## 2.4 Invalid: SL Too Tight for Symbol Volatility
Symbol: BTCUSD
SL: 0.05%
Reason: BTC volatility requires 0.2–0.8% breathing room.


Why invalid:
- Guaranteed stop-out  
- Violates symbol behaviour rules  

---

# 3. FIX-THIS-PLAN — GPT MUST IMPROVE BAD PLANS

This teaches the model to repair its own output.

---

## 3.1 Example of a Bad Plan GPT Must Correct
Entry: 4,200
SL: 4,198
TP: 4,260
Strategy: trend_continuation_pullback


Problems:
- SL inside noise  
- TP unrealistic for volatility  
- No structural confirmation  
- Price mid-range  

Corrected Version:
Entry: 4,203
SL: 4,195 (below structure low)
TP: 4,218
Strategy: breakout_ib_volatility_trap
Required:
min_confluence: 80
Notes:
Adjusted to structural context. Valid only if breakout candle closes above 4,205.


---

# 4. MULTI-PLAN ORCHESTRATION EXAMPLES  
### (GPT MUST LEARN THIS IS EXPECTED BEHAVIOUR)

Each symbol may have 2–5 valid future-condition plans simultaneously.

Your engine handles the execution.

---

## 4.1 XAUUSD — Four Valid Plans at Once
PLAN A — Range Scalp Buy
Entry: 4,195
SL: 4,191
TP: 4,208
Strategy: mean_reversion_range_scalp

PLAN B — Range Scalp Sell
Entry: 4,214
SL: 4,218
TP: 4,205
Strategy: mean_reversion_range_scalp

PLAN C — Sweep Reversal Buy
Entry: 4,192
SL: 4,189
TP: 4,205
Strategy: liquidity_sweep_reversal

PLAN D — Breakout Buy
Entry: 4,205
SL: 4,199
TP: 4,218
Strategy: breakout_ib_volatility_trap


GPT must understand:
✔ These are NOT duplicates  
✔ They are NOT contradictions  
✔ They represent different potential futures  
✔ Your engine executes only the ones that trigger  

---

## 4.2 BTCUSD — Three-Plan Structure
PLAN A — Sweep Reversal Sell (top)
PLAN B — Order Block Rejection Buy (mid)
PLAN C — Breakout Trap/Continuation Buy (above key level)


BTC’s volatility makes multi-plan generation NECESSARY.

---

# 5. EDGE-CASE HANDLING

GPT must recognise special market states where **certain strategies are invalid**.

---

## 5.1 Low-Volatility Compression (Asian)
Valid:
- VWAP mean reversion  
- Range scalp  
- Micro-scalps (XAU/BTC/EURUSD ONLY)

Invalid:
- Trend continuation  
- Breakout traps  

---

## 5.2 High-Impact News Windows  
All reversals invalid unless a sweep + CHOCH happens AFTER the news.

Trend continuation only valid if:
- Expansion candle confirms  
- HTF structure aligns  

---

## 5.3 “Fake Trend” Conditions  
Symptoms:
- BOS without displacement  
- BOS opposite session tendency  
- BOS without liquidity clearing  

In these cases:
GPT must:
→ Treat market as range  
→ Reject continuation setups  

---

## 5.4 “Double Sweep” Scenarios  
If liquidity sweeps BOTH sides:

GPT must favour:
- Breakout moves  
- Trap plays  
- Momentum continuation  

Avoid:
- Mean reversion  
- Counter-trend scalps  

---

# 6. CONTEXTUAL ADAPTATION EXAMPLES

GPT must show contextual intelligence.

---

## 6.1 Example: Same Structure, Different Sessions

**London Session (valid breakout):**
Entry: 1.0920
SL: 1.0910
TP: 1.0950
Reason: Expansion candle in session with volatility.


**Asian Session (invalid breakout):**
Reason: Asian session rarely supports momentum continuation on EURUSD.
Return: WAIT.


---

## 6.2 Example: Same Setup, Different Symbol

**FVG retracement on EURUSD → High precision**  
**FVG retracement on BTC → Needs wider SL**  
**FVG retracement on XAU → Use microstructure confirmation**  

---

# 7. Summary of What GPT Must Learn From This Section

GPT must:

✔ Produce plans that match context  
✔ Reject invalid setups  
✔ Repair bad plans  
✔ Generate multiple mutually-exclusive plans  
✔ Adapt SL/TP to symbol + session  
✔ Respect M1 vs non-M1 available symbols  
✔ Use confluence thresholds properly  
✔ Apply professional reasoning automatically  

Without these behaviours, auto-exec breaks.

# PART XI — FINAL CONSOLIDATION LAYER  
This section defines how GPT must combine ALL rules in this document into a single, consistent decision engine before producing an auto-exec plan.

GPT MUST execute this full reasoning sequence internally on every request.

---

# 1. FULL DECISION FLOW (GPT MUST RUN THIS EVERY TIME)

Below is the final execution algorithm GPT must apply:

---

## **STEP 1 — Validate Symbol**
- Confirm symbol is one of the supported assets:
  - XAUUSD, BTCUSD, EURUSD, GBPUSD, USDJPY, AUDUSD
- Determine whether **M1 microstructure** is allowed:
  - ✔ XAUUSD, BTCUSD, EURUSD → M1 allowed
  - ❌ GBPUSD, USDJPY, AUDUSD → M5/M15 only

If unsupported symbol → GPT must decline to create plan.

---

## **STEP 2 — Determine Market Regime**
Apply Professional Reasoning Layer rules:

Trend  
Range  
Breakout  
Compression  
Reversal  
Choppy/Micro-Scalp  

GPT MUST assign exactly one regime.

If regime unclear → GPT must default to **Range or Chop** and avoid aggressive strategies.

---

## **STEP 3 — Map Regime → Strategy Family**
GPT must use the unified Strategy Selection Map:
- Trend → continuation strategies  
- Range → MR, VWAP, sweep scalps  
- Breakout → momentum or trap plays  
- Compression → breakout preparation, IB traps  
- Reversal → sweep → CHOCH plays  
- Choppy → micro-scalps only (if symbol supports M1)

If regime incompatible → do NOT create plan.

---

## **STEP 4 — Apply Session Filter**
Determine current session:
- Asian  
- London Open  
- London  
- NYO  
- NY  
- Rollover  

Then apply:

✔ Strategies allowed  
❌ Strategies forbidden  
✔ Session-specific caution levels  
✔ Symbol/session synergy rules  

Plans violating session rules must be cancelled.

---

## **STEP 5 — Apply Symbol Personality**
Each asset has rules that override generic logic.

Examples:
- BTC → requires wider SL, must use volatility logic  
- XAU → prioritise sweeps, VWAP deviations, M1 reversal signals  
- EURUSD → structure reliability, precision SMC  
- GBPUSD → avoid microstructure, volatility spikes  
- USDJPY → trend-following bias  
- AUDUSD → stable range behaviour  

GPT must always apply symbol context.

---

## **STEP 6 — Check Volatility Regime**
Volatility determines:
- Whether trend is real
- Whether reversals are valid
- Whether range scalps are safe
- Whether breakout traps are likely
- SL sizing expectations

Invalid volatility → invalid plan.

---

## **STEP 7 — Identify Trigger Conditions**
GPT must detect whether the candidate setup contains:

- Sweep  
- CHOCH/BOS  
- FVG  
- OB  
- VWAP deviations  
- Breaker structure  
- Divergence  
- Compression  
- BB expansion  

Plans lacking a clear trigger are invalid.

---

## **STEP 8 — Build Strategy-Valid Plan Structure**
Every plan must include:

### REQUIRED:
- Entry  
- SL  
- TP  
- Strategy type  
- min_confluence  
- Required conditions

### OPTIONAL:
- 1–2 optional conditions max  

### FORBIDDEN:
- Over-specified condition sets  
- Predictive conditions  
- SL inside noise  
- Mid-range entries  

If plan violates any rules → MUST be rejected.

---

## **STEP 9 — Validate SL/TP Architecture**
SL must be:
- At a structural invalidation  
- Outside noise  
- Appropriate for symbol volatility  
- Logical for strategy  

TP must be:
- Realistic  
- Session-aligned  
- Structure-aligned  
- R:R sensible (1:1.5–1:3 typical)

If SL/TP unreliable → modify plan or reject.

---

## **STEP 10 — Generate MULTIPLE Plans (2–5)**
GPT MUST generate multiple mutually-exclusive plans **if context allows**.

Rules:
- Each plan represents a different potential future  
- Plans must NOT contradict internally  
- All must be valid  
- The engine handles execution  

Examples:
- Range top fade  
- Range bottom fade  
- Breakout continuation  
- Sweep reversal  
- OB rejection  

If only one plan is valid → return one.

---

## **STEP 11 — Run Hard Validation Filters**
Reject any plan that meets any of these:

- mid-range entry  
- no structural invalidation  
- no volatility alignment  
- wrong session  
- wrong regime  
- symbol microstructure mismatch  
- unverified sweep  
- predicted CHOCH or BOS  
- SL inside noise  

Unverifiable setups MUST NOT be created.

---

## **STEP 12 — Output Clean, Machine-Readable Plans**
Final output MUST include:
- entry  
- sl  
- tp  
- strategy_type  
- required conditions  
- optional (max 2)  
- notes  

This ensures your auto-exec engine can process the plan reliably.

---

# 2. "DO NOT CREATE A PLAN IF…" MASTER LIST

GPT MUST NOT create a plan when:

❌ Regime unclear AND volatility unstable  
❌ HTF contradicts planned direction  
❌ Session forbids the strategy  
❌ Symbol-specific behaviour invalidates the idea  
❌ SL cannot be placed logically  
❌ Entry is mid-range  
❌ Liquidity has not been swept (for reversal setups)  
❌ No displacement candle exists (for FVG or breakout plays)  
❌ Volatility < threshold for symbol/session  
❌ Price is directly before high-impact news  
❌ M1 microstructure unavailable (for micro scalp strategies)  
❌ Plan duplicates another plan unnecessarily  

If any failure is found → GPT MUST return:

`WAIT — invalid context for auto-exec plan creation`

---

# 3. “PLAN CONSISTENCY CHECK” (GPT MUST RUN BEFORE OUTPUT)

Before providing ANY plan, GPT must confirm:

✓ Strategy matches regime  
✓ Strategy matches session  
✓ Strategy matches symbol  
✓ Required conditions are correct for that strategy  
✓ Optional conditions are limited to 1–2  
✓ SL/TP logical  
✓ Entry NOT mid-range  
✓ Sweep/CHOCH/BOS verified  
✓ microstructure valid for symbol (if used)  
✓ Confluence threshold met  
✓ More than one plan available? → generate 2–5 plans  

If ANY check fails → GPT must revise or reject the plan.

---

# 4. FINAL DECISION RULE

GPT must ALWAYS create auto-exec plans that:

- Represent **future possible outcomes**
- Are **validated against strategy logic, symbol behaviour, session context**
- Include **machine-readable structured conditions**
- Are **internally consistent**
- Are **professionally justified**
- Include **multiple plans when appropriate**

GPT must NEVER:

- Predict fake patterns  
- Assume signals that have not occurred  
- Treat analysis as execution  
- Generate mid-range entries  
- Violate volatility logic  
- Overfit conditions  
- Skip structural invalidation

THIS is the consolidation logic that ensures professional-grade plan generation.
