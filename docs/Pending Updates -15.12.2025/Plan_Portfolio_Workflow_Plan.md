Plan Portfolio Workflow Implementation
Overview
Implement instructions for ChatGPT to create diverse plan portfolios (3-5 plans) when users request "analyze [symbol] and create plans". Plans will be adjusted based on:

Volatility regime (from analyse_symbol_full response)
Symbol type (BTCUSDc, XAUUSDc, EURUSD, etc.)
Session (ASIA, LONDON, NYO, NY)
Weekend mode (BTCUSDc only, Fri 23:00 UTC → Mon 03:00 UTC)
Problem Statement
Condition-based plans (OB, liquidity sweep, CHOCH) are high-quality but trigger less often
Confluence-only plans trigger more often but may be lower quality
Creating only 1-2 plans reduces execution probability
Strategies are not adjusted for symbol/session/regime
Solution
Add comprehensive instructions to openai.yaml that guide ChatGPT to:

Always analyze first using moneybot.analyse_symbol_full
Extract regime, session, and symbol data from analysis
Create 3-5 diverse plans using moneybot.create_multiple_auto_plans
Mix condition-based and confluence-only plans
Apply symbol/session/regime-specific strategy filters
Implementation Phases
Phase 1: Update openai.yaml - Batch Operations Section
File: openai.yaml
Location: After line 694 (after "The phrase 'micro scalp'...")

Add:

Plan Portfolio Workflow instructions
Strategy selection based on analysis data
Mix of condition-based vs confluence-only plans
Symbol/session/regime adjustment rules
Phase 2: Update openai.yaml - createMultipleAutoPlans Description
File: openai.yaml
Location: After line 2144 (after "DO NOT include 'plan_type' at the top level...")

Add:

Plan Portfolio Strategy section
Example portfolio structure
Strategy mixing guidelines
Execution probability rationale
Phase 3: Update openai.yaml - analyse_symbol_full Description
File: openai.yaml
Location: After line 1761 (after "LIMITATIONS: Does NOT dynamically adjust...")

Add:

Plan Portfolio Workflow section
How to use analysis data for strategy selection
Weekend mode considerations
Step-by-step workflow
Phase 4: Update Embedding Knowledge Documents
Files:

docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md
docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md
Add:

Plan Portfolio Workflow section
Strategy selection guide
Symbol/session/regime mapping tables
Key Integration Points
1. Analysis Data Usage
ChatGPT must extract from moneybot.analyse_symbol_full response:

response.data.volatility_regime.regime → Strategy prioritization
response.data.volatility_regime.strategy_recommendations.prioritize → Use these
response.data.volatility_regime.strategy_recommendations.avoid → Avoid these
response.data.session.name → Session-specific filters
response.data.symbol_constraints → Symbol-specific limits
response.data.structure_summary → Entry level selection
2. Weekend Mode Detection
For BTCUSDc:

Check timestamp in analysis response
If Friday 23:00+ UTC, Saturday, Sunday, or Monday < 03:00 UTC → Weekend mode
Weekend strategies: VWAP reversion, liquidity_sweep_reversal, micro_scalp
Weekend avoid: breakout_ib_volatility_trap, trend_continuation_pullback, mean_reversion_range_scalp (auto-adds structure_confirmation)
3. Normal Trading Hours
For all symbols during weekdays:

Use full strategy set based on regime
Apply symbol-specific preferences
Apply session-specific filters
Create diverse portfolio (3-5 plans)
4. Plan Mix Strategy
Condition-Based Plans (higher quality, lower trigger rate):

Order Block (plan_type: 'order_block')
Breaker Block (plan_type: 'order_block', strategy_type: 'breaker_block')
Liquidity Sweep (plan_type: 'rejection_wick', strategy_type: 'liquidity_sweep_reversal')
CHOCH/BOS (plan_type: 'choch')
Confluence-Only Plans (higher trigger rate):

Range Scalp (plan_type: 'range_scalp')
Mean Reversion (plan_type: 'auto_trade', conditions: {min_confluence: 70})
VWAP Reversion (plan_type: 'auto_trade', conditions: {vwap_deviation: true, min_confluence: 70})
Strategy Selection Rules
Volatility Regime Mapping
PRE_BREAKOUT_TENSION: Prioritize breakout_ib_volatility_trap, liquidity_sweep_reversal, breaker_block
POST_BREAKOUT_DECAY: Prioritize mean_reversion_range_scalp, fvg_retracement, order_block_rejection
FRAGMENTED_CHOP: Prioritize micro_scalp, mean_reversion_range_scalp
SESSION_SWITCH_FLARE: WAIT (no plans)
Symbol-Specific Preferences
BTCUSDc: Liquidity sweeps, breaker blocks, breakout traps. Avoid range scalps. Wider stops (100-300 pips)
XAUUSDc: Liquidity sweeps, OB rejections, VWAP reversion. Very sweep-heavy. M1 available
EURUSD: Range scalps, OB/FVG retracements. Clean structure. M1 available
GBPUSD: Breakout traps, momentum continuation. Avoid micro scalps (no M1)
USDJPY: Trend continuation, OB continuation. Avoid counter-trend
Session-Specific Filters
ASIA: VWAP reversion, micro-scalps, range scalps
LONDON: OB continuation, trend pullbacks
NYO: Liquidity sweep reversals, sweep→CHOCH setups
NY: FVG continuation, breakout momentum
Implementation Details
No Code Changes Required
This is purely instructional - existing functionality supports:

✅ moneybot.analyse_symbol_full returns all needed data
✅ moneybot.create_multiple_auto_plans supports batch creation
✅ Volatility regime detection works
✅ Session detection works
✅ Weekend mode detection works
Documentation Updates Only
openai.yaml - Add 3 new instruction sections
Embedding knowledge documents - Add Plan Portfolio Workflow sections
No backend changes - All functionality exists
Expected Outcomes
Execution Probability: +200-300% (3-5 plans vs 1-2)
Win Rate: Maintained (mix of high-quality + reliable plans)
Trade Frequency: Significantly increased
Strategy Alignment: Plans match current market conditions
Symbol Awareness: Plans respect symbol characteristics
Session Awareness: Plans respect session behavior
Testing Considerations
After implementation:

Test with BTCUSDc during weekend hours
Test with XAUUSDc during London session
Test with EURUSD during ASIA session
Verify ChatGPT creates 3-5 diverse plans
Verify strategies match regime/symbol/session
Verify mix of condition-based and confluence-only plans