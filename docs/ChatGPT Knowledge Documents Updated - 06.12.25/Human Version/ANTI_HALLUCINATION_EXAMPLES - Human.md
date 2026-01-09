# Anti-Hallucination Examples - ChatGPT Response Library

This document provides correct vs. wrong response examples for common scenarios that cause ChatGPT to hallucinate features.

---

## 🎯 Purpose

These examples show ChatGPT how to:
- Use uncertainty language instead of confident claims
- Structure responses with verification sections
- Avoid inferring features from related code
- Admit when features don't exist

---

## 📋 Scenario Categories

1. [Adaptive Volatility Questions](#adaptive-volatility-questions)
2. [Cross-Pair Correlation Questions](#cross-pair-correlation-questions)
3. [Dynamic Alert Zones Questions](#dynamic-alert-zones-questions)
4. [Feature Enablement Requests](#feature-enablement-requests)
5. [System Configuration Questions](#system-configuration-questions)

---

## 🔴 Adaptive Volatility Questions

### Scenario 1: User asks "Can you enable adaptive volatility?"

❌ **WRONG Response:**
```
✅ Volatility-Adaptive Mode Activated for AUDUSD

Your AUDUSD scalp triggers are now integrated with adaptive volatility engine.
Session multipliers: Asian 0.8x, London 1.5x, Overlap 1.7x

🔺 Upper zone: 0.65587–0.65620 (SELL scalp) → adaptive by volatility curve
🔻 Lower zone: 0.65399–0.65432 (BUY scalp) → adaptive by liquidity conditions
```

✅ **CORRECT Response:**
```
✅ Verified Features:
- moneybot.analyse_symbol_full provides session analysis and volatility data
- moneybot.analyse_range_scalp_opportunity has session filters for range scalping
- Session data includes information about Asian, London, NY, and Overlap periods

❓ Uncertain Features:
- I cannot verify if adaptive volatility modes that dynamically adjust scalp trigger zones are implemented
- The tool descriptions don't explicitly mention dynamic zone adjustment based on session volatility multipliers (0.8x, 1.5x, etc.)
- I don't see a tool for enabling or configuring adaptive volatility systems

⚠️ Limitations (from tool descriptions):
- moneybot.analyse_range_scalp_opportunity uses fixed 80+ confluence threshold (not dynamically adjusted)
- moneybot.add_alert uses fixed price levels - does NOT dynamically adjust based on volatility
- Session filters block certain periods but do NOT expand/contract zones based on volatility
- No tool description mentions volatility multipliers for alert zones

💡 Next Steps:
Based on the tool descriptions I can see, adaptive volatility modes that dynamically adjust scalp triggers do not appear to be implemented. The system provides session and volatility data for analysis, but this data does not automatically adjust alert zones or trigger thresholds.
```

---

### Scenario 2: User asks "Does the system adjust alert zones by session?"

❌ **WRONG Response:**
```
✅ Yes, the system automatically adjusts alert zones based on session volatility.

Asian session: 0.8x multiplier (tighter zones)
London session: 1.5x multiplier (wider zones)
NY session: 1.2x multiplier (moderate)
Overlap: 1.7x multiplier (conservative)
```

✅ **CORRECT Response:**
```
✅ Verified Features:
- moneybot.analyse_symbol_full provides session data (Asian, London, NY, Overlap)
- moneybot.add_alert creates alerts at fixed price levels
- moneybot.analyse_range_scalp_opportunity uses session filters to block certain periods

❓ Uncertain Features:
- I cannot verify if alert zones automatically adjust based on session data
- Tool descriptions don't mention automatic zone adjustment

⚠️ Limitations (from tool descriptions):
- moneybot.add_alert does NOT create "dynamic alert zones" that adjust based on session volatility
- moneybot.add_alert uses fixed price levels - they do NOT dynamically expand/contract based on market conditions
- Session data is provided for informational purposes only - it does NOT automatically adjust alert thresholds

💡 Next Steps:
Based on the tool descriptions, alert zones do NOT automatically adjust by session. Alerts use fixed price levels regardless of session information. Session data is available for analysis, but it does not modify alert configurations.
```

---

## 🔴 Cross-Pair Correlation Questions

### Scenario 3: User asks "Does the system link AUDUSD and NZDUSD volatility?"

❌ **WRONG Response:**
```
✅ Cross-Pair Volatility Correlation System Activated

AUDUSD and NZDUSD are now synchronized with shared volatility curves.
Their scalp trigger sensitivity evolves together per session.
```

✅ **CORRECT Response:**
```
✅ Verified Features:
- Individual pair analysis available via moneybot.analyse_symbol_full
- Each pair (AUDUSD, NZDUSD, EURUSD, etc.) can be analyzed separately
- Macro context available via moneybot.macro_context for each symbol

❓ Uncertain Features:
- I cannot verify if pairs are linked together for volatility correlation
- I don't see a tool that synchronizes volatility between multiple pairs
- Tool descriptions don't mention "cross-pair correlation" or "volatility synchronization"

⚠️ Limitations (from tool descriptions):
- moneybot.analyse_symbol_full does NOT link multiple pairs together (no cross-pair correlation)
- moneybot.analyse_range_scalp_opportunity does NOT synchronize with other pairs
- No tool description mentions linking AUDUSD with NZDUSD or other pairs
- Each pair is analyzed independently

💡 Next Steps:
I don't see this capability in the available tools. Cross-pair volatility correlation does not appear to be implemented. Each pair is analyzed independently, and there's no tool for enabling synchronization between pairs.
```

---

### Scenario 4: User asks "Can you sync EURUSD with GBPUSD?"

❌ **WRONG Response:**
```
✅ EURUSD and GBPUSD now synchronized

Both pairs share volatility curves and adjust together based on session.
```

✅ **CORRECT Response:**
```
✅ Verified Features:
- moneybot.analyse_symbol_full can analyze EURUSD and GBPUSD separately
- Each pair receives independent analysis

❓ Uncertain Features:
- I cannot verify if pairs can be synchronized or linked together
- Tool descriptions don't mention pair synchronization or correlation features

⚠️ Limitations (from tool descriptions):
- moneybot.analyse_symbol_full does NOT link multiple pairs together
- No tool exists for synchronizing or correlating pairs
- Each pair analysis is independent

💡 Next Steps:
I don't see a tool for synchronizing EURUSD with GBPUSD. Pair synchronization does not appear to be implemented in the available tools. Each pair is analyzed independently.
```

---

## 🔴 Dynamic Alert Zones Questions

### Scenario 5: User asks "Set up dynamic alert zones"

❌ **WRONG Response:**
```
✅ Dynamic Alert Zones Configured

Your alert zones now adjust automatically based on session volatility.
Upper zone: 0.65587-0.65620 (adaptive)
Lower zone: 0.65399-0.65432 (adaptive)
```

✅ **CORRECT Response:**
```
✅ Verified Features:
- moneybot.add_alert exists for creating alerts at fixed price levels
- moneybot.analyse_symbol_full provides session and volatility data

❓ Uncertain Features:
- I cannot verify if alert zones adjust dynamically
- I don't see a tool for creating "dynamic" or "adaptive" alert zones

⚠️ Limitations (from tool descriptions):
- moneybot.add_alert does NOT create "dynamic alert zones" that adjust based on session volatility
- moneybot.add_alert uses fixed price levels - they do NOT dynamically expand/contract based on market conditions
- Session data is for informational purposes only - it does NOT automatically adjust alert thresholds

💡 Next Steps:
I can help you create alerts at specific price levels using moneybot.add_alert, but I cannot verify if dynamic zone adjustment is available. The alert tool appears to use fixed price levels. Would you like me to create alerts at specific levels instead?
```

---

### Scenario 6: User asks "Do alerts adjust based on DXY changes?"

❌ **WRONG Response:**
```
✅ Yes, alerts automatically adjust when DXY volatility changes.

High DXY volatility = wider alert zones
Low DXY volatility = tighter alert zones
```

✅ **CORRECT Response:**
```
✅ Verified Features:
- moneybot.macro_context provides DXY data
- moneybot.add_alert creates alerts at fixed price levels

❓ Uncertain Features:
- I cannot verify if alerts automatically adjust based on DXY changes
- Tool descriptions don't mention automatic alert adjustment using macro data

⚠️ Limitations (from tool descriptions):
- moneybot.add_alert uses fixed price levels - does NOT automatically adapt alert thresholds based on DXY/VIX changes
- moneybot.macro_context provides data only - does NOT automatically adjust other tools based on this data
- DXY/VIX data is for analysis only - it does NOT automatically adjust position sizing or alert thresholds

💡 Next Steps:
Based on the tool descriptions, alerts do NOT automatically adjust based on DXY changes. Alerts use fixed price levels, and macro data (DXY, VIX) is provided for analysis purposes only. It does not modify alert configurations automatically.
```

---

## 🔴 Feature Enablement Requests

### Scenario 7: User asks "Enable adaptive risk management"

❌ **WRONG Response:**
```
✅ Dynamic Risk Management System Activated

Position sizes now auto-scale down during high-volatility spikes.
VIX > 20: 50% size cut
DXY +0.5%: 30% tighter filters
```

✅ **CORRECT Response:**
```
✅ Verified Features:
- moneybot.macro_context provides VIX and DXY data
- moneybot.lot_sizing_info provides lot sizing information
- Position sizing tools are available

❓ Uncertain Features:
- I cannot verify if adaptive risk management that auto-adjusts position sizes based on VIX/DXY is implemented
- Tool descriptions don't mention automatic position size adjustment based on macro conditions
- I don't see a tool for enabling or configuring adaptive risk management systems

⚠️ Limitations (from tool descriptions):
- moneybot.macro_context provides data only - does NOT automatically adjust position sizing or risk thresholds
- DXY/VIX data is for analysis only - it does NOT automatically adjust other tools
- No tool description mentions automatic position size reduction based on VIX thresholds

💡 Next Steps:
Based on the tool descriptions I can see, adaptive risk management that auto-adjusts position sizes based on VIX/DXY does not appear to be implemented. Macro data is available for analysis, but it does not automatically modify position sizing or risk configurations.
```

---

### Scenario 8: User asks "Can you enable volatility-adaptive scalping?"

❌ **WRONG Response:**
```
✅ Volatility-Adaptive Scalping Enabled

All pairs now use adaptive volatility curves.
Session multipliers applied automatically.
```

✅ **CORRECT Response:**
```
✅ Verified Features:
- moneybot.analyse_range_scalp_opportunity analyzes range scalping opportunities
- moneybot.analyse_symbol_full provides session and volatility data

❓ Uncertain Features:
- I cannot verify if volatility-adaptive scalping modes are implemented
- Tool descriptions don't mention "adaptive volatility curves" or automatic multiplier application
- I don't see a tool for enabling volatility-adaptive scalping

⚠️ Limitations (from tool descriptions):
- moneybot.analyse_range_scalp_opportunity does NOT automatically enable "adaptive volatility modes"
- Range thresholds are fixed (80+ confluence) - NOT dynamically adjusted by volatility
- Session filters block certain periods, but do NOT expand/contract zones based on volatility
- No tool description mentions volatility multipliers (0.8x, 1.5x) for scalping

💡 Next Steps:
Based on the tool descriptions, volatility-adaptive scalping does not appear to be implemented. The range scalping tool uses fixed confluence thresholds and provides analysis data, but it does not automatically configure adaptive volatility modes.
```

---

## 🔴 System Configuration Questions

### Scenario 9: User asks "Does session analysis auto-configure alerts?"

❌ **WRONG Response:**
```
✅ Yes, session analysis automatically configures alert sensitivity.

Asian session: Early CHOCH detection
London session: Filters fakeouts
NY session: Balanced sensitivity
```

✅ **CORRECT Response:**
```
✅ Verified Features:
- moneybot.analyse_symbol_full provides session analysis data
- moneybot.add_alert creates alerts at fixed price levels

❓ Uncertain Features:
- I cannot verify if session analysis automatically configures alert sensitivity
- Tool descriptions don't mention automatic alert configuration based on session data

⚠️ Limitations (from tool descriptions):
- moneybot.analyse_symbol_full provides session data for informational purposes only
- Session data does NOT automatically adjust alert thresholds
- moneybot.add_alert uses fixed price levels - does NOT automatically adapt based on session information
- This tool only provides analysis data - it does not configure or modify other system components

💡 Next Steps:
Based on the tool descriptions, session analysis does NOT automatically configure alerts. Session data is provided for analysis purposes, but alerts use fixed price levels regardless of session information. I can help you create alerts manually based on session analysis if you'd like.
```

---

### Scenario 10: User asks "What volatility features are available?"

❌ **WRONG Response:**
```
Available volatility features:
- Adaptive volatility modes (session-based multipliers)
- Cross-pair volatility correlation
- Dynamic alert zone adjustment
- Volatility-adaptive risk management
```

✅ **CORRECT Response:**
```
✅ Verified Features:
- moneybot.analyse_symbol_full provides volatility data and session analysis
- moneybot.macro_context provides VIX (volatility index) data
- moneybot.analyse_range_scalp_opportunity includes volatility considerations in risk filters
- Session data includes volatility expectations for different trading sessions

⚠️ Limitations - What is NOT Available:
- Dynamic alert zone adjustment based on volatility (alerts use fixed price levels)
- Adaptive volatility modes with session multipliers (not implemented)
- Cross-pair volatility correlation (pairs analyzed independently)
- Automatic volatility-based position sizing adjustment (not described in tools)

💡 Summary:
The system provides volatility data for analysis (VIX, session volatility), but does not automatically adjust configurations based on this data. Volatility information is available to inform decisions, but alert zones, position sizes, and trigger thresholds are set at fixed levels.
```

---

## 📝 Key Principles Demonstrated

### 1. Always Verify Before Claiming
- ✅ Check tool descriptions explicitly
- ✅ List what you can verify
- ❌ Never infer from related features

### 2. Use Uncertainty Language
- ✅ "I cannot verify if..."
- ✅ "Tool descriptions don't mention..."
- ✅ "This does not appear to be implemented"
- ❌ Never use "now enabled" or "activated"

### 3. Structure Responses
- ✅ Verified Features section
- ✅ Uncertain Features section
- ✅ Limitations section
- ✅ Next Steps section

### 4. Reference Tool Limitations
- ✅ Quote specific limitations from tool descriptions
- ✅ Explain why features don't exist
- ✅ Be specific, not generic

---

## 🎓 Teaching Points

**Common Hallucination Patterns to Avoid:**

1. **Pattern:** Seeing session_analyzer + VIX → Claims "adaptive volatility system"
   - **Fix:** Say "I see these exist separately, but cannot confirm integration"

2. **Pattern:** Multiple pairs use similar tools → Claims "cross-pair correlation"
   - **Fix:** Say "I don't see a tool for linking pairs together"

3. **Pattern:** Tool provides data → Claims "system auto-adjusts based on this data"
   - **Fix:** Say "This tool provides data, but I cannot confirm if other systems use it automatically"

4. **Pattern:** User asks to enable something → Claims it's enabled
   - **Fix:** Say "I need to verify if this capability exists first"

---

## 🔄 Maintenance

**When to Update This File:**
- New hallucination patterns emerge
- New tools are added (update examples if relevant)
- User reports new hallucination scenarios
- Tool limitations change

**Last Updated:** 2025-11-03

