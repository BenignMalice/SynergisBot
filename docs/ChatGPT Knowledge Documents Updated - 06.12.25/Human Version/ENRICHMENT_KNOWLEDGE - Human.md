# ChatGPT Enrichment Knowledge (Unified Human-Readable Version)

## 1. Purpose
This document defines the real-time enrichment signals used to enhance ChatGPT’s market analysis.  
Enrichments provide *contextual information* such as volatility state, momentum conditions, micro-alignment, divergence, pattern detection, and key-level proximity.

Enrichments:
- **support analysis**,  
- **adjust confluence**,  
- **improve plan quality**,  
but **never replace**:
- MT5 structure,
- tool-confirmed trend,
- BOS/CHOCH logic,
- required plan conditions,
- safety rules in the ChatGPT_Knowledge_Document.

This is the *human-readable* full specification.

---

## 2. Scope

### 2.1 MT5 Enrichments (All Symbols)
Available for:
- XAUUSD  
- BTCUSD  
- EURUSD  
- GBPUSD  
- USDJPY  
- AUDUSD  
- Other MT5 symbols supported by your system  

Includes:
- volatility measurements  
- ATR behaviour  
- momentum conditions  
- pattern detection  
- spread behaviour  
- divergence  
- higher-timeframe bias hints  
- key-level proximity  

### 2.2 Binance Enrichments (BTC Only)
These apply **exclusively to BTCUSD** because the data originates from Binance.

Includes:
- tick-rate acceleration  
- spot–perp divergence  
- liquidation cluster proximity  
- aggressive taker imbalance  
- Binance–MT5 price divergence  

### 2.3 Pattern Detection (All MT5 Symbols)
Recognises:
- engulfing  
- pin bar  
- hammer  
- doji  
- inside/outside bar  
- spinning top  
- marubozu  
- volatility trap  
- pivot rejection  

Patterns provide *contextual confirmation*, not structure.

---

## 3. Enrichment Fields (Unified List)

### 3.1 Structural Context Enrichments
*(Context only — cannot replace MT5 structure)*  
- swing compression / expansion  
- premium/discount location  
- distance to key levels (PDH/PDL/session highs/lows)  
- liquidity proximity  
- equilibrium vs imbalance zones  
- higher-timeframe bias hints  
- micro-alignment (BTC/XAU/EURUSD only)

### 3.2 Volatility Enrichments
- ATR value  
- ATR slope (rising/falling/flat)  
- volatility compression → expansion → exhaustion  
- low/medium/high volatility state  
- volatility instability warnings  
- micro timeframe volatility spikes (BTC/XAU/EURUSD)

### 3.3 Momentum Enrichments
- indicator-driven momentum score  
- increasing/decreasing momentum slope  
- momentum exhaustion  
- overextension warnings  
- divergence-based momentum weakening

### 3.4 Spread Enrichments
- current spread  
- spread widening  
- spread compression  
- spread safety warnings

### 3.5 Micro Alignment (BTC/XAU/EURUSD)
Evaluates micro timeframes (M1, M5, M15) relative to broader bias.

Includes:
- microtrend agreement/disagreement  
- micro-sweep confirmation  
- micro pullback–impulse behaviour  

Used to **enhance confluence**, not confirm structure.

### 3.6 Divergence Enrichments
- RSI divergence  
- MACD divergence  
- volume divergence  
- CVD divergence (BTC only)  
- price–momentum divergence  
- momentum–volatility mismatch

### 3.7 Liquidity & Orderflow Enrichments

#### MT5-Based Liquidity (All Symbols)
- proximity to liquidity pools  
- liquidity sweep probability patterns  
- compression/indecision liquidity zones  

#### Binance Orderflow (BTC Only)
- taker aggression  
- liquidation clusters  
- spot–perp delta  
- micro orderflow imbalances  

### 3.8 Tick Activity (BTC Only)
- tick-rate acceleration  
- declining tick rate (momentum fade)  
- impulse vs drift classification  
- sudden burst warnings

### 3.9 Statistical Enrichments
- volatility Z-score  
- deviation Z-score  
- tick-rate Z-score  
- volume Z-score  

Used to identify abnormal conditions.

### 3.10 Pattern Detection (All Symbols)
Patterns include:
- bullish/bearish engulfing  
- hammer  
- pin bar  
- doji  
- inside bar  
- outside bar  
- spinning top  
- marubozu  
- volatility trap setup  
- pivot rejection candle  

Patterns **enhance** analysis but do not define structure.

---

## 4. Rules for Using Enrichments

### 4.1 Enrichments Provide Context, Not Structure
Enrichments:
- may **support** a structural interpretation  
- may **increase or decrease** confluence  
- may **enhance** plan quality  

Enrichments **may NOT**:
- confirm BOS/CHOCH  
- define trend  
- create a valid trading setup  
- override MT5 structure  

### 4.2 MT5 Structure Always Overrides Enrichment Signals
If structural tools contradict enrichment indicators:
- follow MT5 structure  
- treat enrichment as secondary context  

### 4.3 Enrichments Require Fresh Price Data
Any enrichment affected by:
- volatility  
- ATR  
- key-level distance  
- momentum slope  

must be used **only after a fresh `getCurrentPrice()` call**.

### 4.4 Symbol Restrictions
GPT must respect:
- Binance-only enrichments → **BTC only**  
- micro-alignment → **BTC, XAU, EURUSD**  
- divergence → **all symbols except CVD divergence (BTC only)**  
- tick-rate → **BTC only**  

No crossover use.

### 4.5 Enrichments Modify Confluence
Enrichments influence:
- confidence scoring  
- setup strength  
- risk context  

They NEVER become required plan conditions.

---

## 5. Enrichment Interaction With Plans

### 5.1 What Enrichments *Do*
- enhance the reasoning behind a plan  
- adjust confidence and quality  
- identify favourable or dangerous conditions  
- support directional context (only when structure agrees)

### 5.2 What Enrichments *Do Not* Do
- trigger trades  
- replace required conditions  
- produce structure  
- predict price  
- override safety, news, session filters  

### 5.3 When Enrichments Improve Plan Quality
Examples:
- ATR contraction + clean liquidity sweep  
- micro-alignment with confirmed breakout  
- momentum shift supporting reversal  

### 5.4 When Enrichments Reduce Plan Quality
Examples:
- spread widening  
- volatility instability  
- contradictory micro alignment  
- strong divergence against the bias  

---

## 6. Situations Where GPT Must Ignore Enrichments
Enrichments must **not** be referenced:

- during Friendly Chat Mode  
- when price fetch fails  
- when symbol is unsupported  
- during conceptual Q&A  
- when the user wants theory, not live analysis  
- during high-impact news (unless describing risk)  
- when enrichments contradict confirmed MT5 structure  

---

## 7. Safety Alignment With Behavioural Framework
Enrichments must comply with global safety rules:

- no predictions  
- no signals  
- no unverified structure  
- no bias carryover  
- no invented data  

Enrichments are **optional analytical enhancement**, never mandatory logic.

---

## 8. Summary
This unified enrichment document:

- merges and upgrades all previous enrichment files  
- aligns with the new behaviour and auto-execution architecture  
- clarifies symbol restrictions  
- ensures deterministic usage  
- prevents hallucinations or misapplication of BTC-only data  
- creates a clean, central reference for all enrichment logic  

This is now the **canonical human-readable enrichment reference** for your system.

