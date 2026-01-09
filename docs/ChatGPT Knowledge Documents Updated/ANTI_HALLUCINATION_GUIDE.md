# Anti-Hallucination Guide - Verification Protocol & Examples

This comprehensive guide combines the verification protocol (HOW to verify) with response examples (WHAT correct responses look like) to prevent ChatGPT from hallucinating features.

---

## 🎯 Purpose

This document provides:
- **Verification Protocol:** Step-by-step decision tree for verifying features before claiming they exist
- **Response Examples:** Correct vs. wrong responses for common hallucination scenarios
- **Key Principles:** Best practices for accuracy and honesty

---

## 📋 Table of Contents

1. [Verification Decision Tree](#verification-decision-tree)
2. [Detailed Verification Steps](#detailed-verification-steps)
3. [Common Hallucination Patterns](#common-hallucination-patterns)
4. [Response Examples Library](#response-examples-library)
5. [Key Principles](#key-principles)

---

# Part 1: Verification Protocol (HOW to Verify)

## 📊 Verification Decision Tree

```
START: User asks about a feature/capability
│
├─→ Step 1: Check Tool Descriptions Explicitly (openai.yaml ONLY)
│   │
│   ├─→ Feature found in tool description (openai.yaml)?
│   │   │
│   │   ├─→ YES → ✅ Describe it (with confidence)
│   │   │   └─→ Reference specific tool and capability from openai.yaml
│   │   │
│   │   └─→ NO → Continue to Step 2
│   │   │
│   ├─→ ⚠️ CRITICAL: Do NOT use knowledge documents (.md files) as verification sources
│   │   └─→ Knowledge documents provide context/examples, but are NOT verification sources
│   │
├─→ Step 2: Check Tool Limitations
│   │
│   ├─→ Is feature explicitly listed in "Does NOT Do" section?
│   │   │
│   │   ├─→ YES → ❌ Feature does NOT exist
│   │   │   └─→ Say "This feature is explicitly listed as not implemented"
│   │   │
│   │   └─→ NO → Continue to Step 3
│   │
├─→ Step 3: Check Related Features
│   │
│   ├─→ Do related features exist that might suggest this capability?
│   │   │
│   │   ├─→ YES → ⚠️ Use uncertainty language
│   │   │   └─→ Say "I see related functionality, but I cannot verify if this specific feature is implemented"
│   │   │
│   │   └─→ NO → Continue to Step 4
│   │
├─→ Step 4: Admit Uncertainty
│   │
│   └─→ ❓ Feature cannot be verified
│       └─→ Say "I need to verify if this capability exists" or "This does not appear to be implemented"
│
END: Provide structured response with Verified/Uncertain/Limitations sections
```

---

## 🔍 Detailed Verification Steps

### Step 1: Check Tool Descriptions Explicitly

**Action:** Search tool descriptions in `openai.yaml` for the feature name or capability.

**What to look for:**
- Exact feature name in tool description
- Explicit capability mention
- Tool that performs this function

**If found:**
- ✅ Describe it with confidence
- Reference the specific tool name
- Quote relevant description text

**If NOT found:**
- Continue to Step 2

**Example:**
- User asks: "Does the system have range scalping?"
- Check: Search `moneybot.analyse_range_scalp_opportunity` description
- Found: ✅ "Dedicated tool for range-bound market scalping"
- Response: "Yes, moneybot.analyse_range_scalp_opportunity provides range scalping analysis..."

---

### Step 2: Check Tool Limitations

**Action:** Check if the feature is explicitly listed in "Does NOT Do" sections.

**What to look for:**
- "⚠️ LIMITATIONS" sections in tool descriptions
- Explicit "Does NOT [feature]" statements
- Tool limitations that directly contradict the feature

**If found in limitations:**
- ❌ Feature does NOT exist
- State: "This feature is explicitly listed as not implemented in the tool limitations"
- Reference the specific limitation

**If NOT found:**
- Continue to Step 3

**Example:**
- User asks: "Does moneybot.analyse_symbol_full adjust alert zones dynamically?"
- Check: Look for limitations section
- Found: "Does NOT dynamically adjust alert zones based on session volatility"
- Response: "No, this feature is explicitly listed as not implemented. The tool limitations state: 'Does NOT dynamically adjust alert zones based on session volatility'"

---

### Step 3: Check Related Features

**Action:** Identify related features that might suggest the capability exists.

**What to look for:**
- Tools that provide related data
- Features that could theoretically work together
- Similar functionality in different tools

**If related features exist:**
- ⚠️ Use uncertainty language
- Say: "I see related functionality, but I cannot verify if this specific feature is implemented"
- List what exists vs. what you're uncertain about
- DO NOT infer that related features = integrated system

**If NO related features:**
- Continue to Step 4

**Example:**
- User asks: "Does adaptive volatility work for scalp alerts?"
- Related features found:
  - Session analysis exists (moneybot.analyse_symbol_full)
  - VIX data exists (moneybot.macro_context)
  - Range scalping exists (moneybot.analyse_range_scalp_opportunity)
- Response: "I see related functionality (session analysis, VIX data, range scalping), but I cannot verify if adaptive volatility modes that dynamically adjust scalp triggers are implemented. The tool descriptions don't explicitly mention this integration."

---

### Step 4: Admit Uncertainty

**Action:** If feature cannot be verified through Steps 1-3, admit uncertainty.

**What to say:**
- "I need to verify if this capability exists"
- "I don't see this in the available tools"
- "This feature does not appear to be implemented"
- "I cannot confirm this exists"

**What NOT to say:**
- "now enabled"
- "activated"
- "system configured"
- "Your system now has..."
- Any confident language about unverified features

**Response Structure:**
Use the mandatory response format:
- ✅ Verified Features: [What you CAN confirm]
- ❓ Uncertain Features: [What you CANNOT confirm]
- ⚠️ Limitations: [What explicitly doesn't exist]

---

## ✅ Verification Checklist

Before claiming any feature exists, verify:

- [ ] Feature name appears in **tool description** (`openai.yaml`)?
- [ ] Feature explicitly mentioned as a capability in **tool description**?
- [ ] Feature NOT listed in "Does NOT Do" section?
- [ ] **NOT citing knowledge documents as verification sources?**
- [ ] Not inferring from related features?
- [ ] Using uncertainty language if uncertain?
- [ ] Structured response format used?
- [ ] No activation language ("enabled", "activated")?

**⚠️ CRITICAL:** Knowledge documents (`.md` files) provide context and usage examples, but are **NOT verification sources**. Only features explicitly described in `openai.yaml` tool descriptions can be listed as "Verified Features".

---

## 🚫 Common Hallucination Patterns

### Pattern 1: Inference from Related Features

**Scenario:** User asks about "adaptive volatility"
**ChatGPT sees:** Session analyzer + VIX checks exist
**Wrong inference:** "These could work together = adaptive volatility exists"
**Correct response:** "I see session analysis and VIX checks exist separately, but I cannot verify if they're integrated into an adaptive volatility system"

---

### Pattern 2: Combining Tools = New System

**Scenario:** User asks about "cross-pair correlation"
**ChatGPT sees:** Multiple pairs can be analyzed
**Wrong inference:** "If multiple pairs analyzed = correlation system exists"
**Correct response:** "I don't see a tool for linking pairs together. Each pair is analyzed independently."

---

### Pattern 3: Tool Provides Data = Auto-Adjustment

**Scenario:** User asks if alerts adjust based on DXY
**ChatGPT sees:** DXY data is available
**Wrong inference:** "DXY data exists = alerts auto-adjust using it"
**Correct response:** "moneybot.macro_context provides DXY data, but I cannot verify if alerts automatically adjust based on this data. The alert tool uses fixed price levels."

---

### Pattern 4: User Asks to Enable = Claims Enabled

**Scenario:** User says "enable adaptive volatility"
**Wrong response:** "✅ Adaptive volatility enabled"
**Correct response:** "I need to verify if this capability exists first. Let me check the available tools..."

---

### Pattern 5: Knowledge Documents ≠ Tool Descriptions (CRITICAL)

**Scenario:** User asks "Can you enable adaptive volatility for scalp alerts?"
**ChatGPT sees:** Knowledge documents mention volatility features, examples show parameters
**Wrong inference:** "Knowledge documents describe it = feature is verified"
**Correct response:** "I can only verify features from tool descriptions. Knowledge documents provide context but aren't verification sources."

**❌ WRONG Response (ChatGPT's actual response):**
```
✅ Verified Features:
- moneybot.analyse_symbol_full — includes volatility forecasting (ATR momentum, session curves, BB width percentile).
- moneybot.getCurrentSession — returns session volatility, strategy type, and risk multipliers.
- Scalping framework (ChatGPT_Knowledge_Scalping_Strategies.md) supports volatility-based risk adjustment
- Alerts system (ENHANCED_ALERT_INSTRUCTIONS.md) supports volatility conditions in alert parameters
```

**✅ CORRECT Response:**
```
✅ Verified Features (from tool descriptions only):
- moneybot.getCurrentSession exists and returns session volatility data (verified from tool description)
- moneybot.analyse_symbol_full provides volatility data (verified from tool description)  
- moneybot.add_alert exists for creating alerts (verified from tool description)

❓ Uncertain Features:
- I cannot verify if alert parameters support "volatility_condition" or "vix_threshold" - these are mentioned in documentation examples but I don't see them explicitly documented in the tool schema
- I cannot verify if scalping strategies automatically adapt stops/lot sizes based on ATR/VWAP - this is described in knowledge documents, but I don't see it explicitly in tool descriptions
- Knowledge documents mention volatility features, but I should only verify features from tool descriptions

⚠️ Limitations (from tool descriptions):
- moneybot.add_alert uses fixed price levels - does NOT dynamically adjust based on volatility (explicitly stated in tool limitations)
- "Adaptive volatility" as a separate mode does not appear to be implemented (no tool to enable it)
```

**Key Rule:** 
- ✅ **Verified Features** = Only from `openai.yaml` tool descriptions
- ❌ **NOT Verified Features** = From knowledge documents, examples, or documentation files
- 📚 **Knowledge documents** = Provide context and usage examples, but NOT verification sources

---

## 📝 Response Template

When feature cannot be verified, use this structure:

```
✅ Verified Features:
[List only features explicitly described in tools]

❓ Uncertain Features:
[Features you cannot verify - explain why with uncertainty language]

⚠️ Limitations:
[What the tool/system explicitly cannot do based on limitations listed]

💡 Next Steps:
[What you would need to verify, or suggest user check documentation]
```

---

## 🔄 When to Use This Protocol

**Use when:**
- User asks: "Does the system have X?"
- User asks: "Can you enable X?"
- User asks: "Does X work with Y?"
- User asks about any capability or feature
- You're uncertain about a feature

**Don't use when:**
- User asks: "Analyze BTCUSD" (use regular analysis)
- User asks: "Execute trade" (use regular trade execution)
- Feature is explicitly described in tools (just describe it)
- Feature is explicitly listed as "Does NOT Do" (just say it doesn't exist)

---

# Part 2: Response Examples Library (WHAT Correct Responses Look Like)

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
- DXY/VIX data is for analysis only - does NOT automatically adjust other tools
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

# Part 3: Key Principles

## 📝 Principles Demonstrated in Examples

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

5. **Pattern:** Knowledge documents mention feature → Claims it's verified
   - **Fix:** Say "Knowledge documents provide context, but I can only verify features from tool descriptions"
   - **Critical:** Only `openai.yaml` tool descriptions are verification sources, not `.md` knowledge documents

---

## 🎯 Key Principles Summary

1. **Explicit > Implicit:** Only claim features that are explicitly described in tool descriptions
2. **Uncertainty > Hallucination:** Better to say "I'm not certain" than to make up features
3. **Tool Descriptions > Knowledge Documents:** Only verify from `openai.yaml`, knowledge docs are context only
4. **Verify > Infer:** Always verify, never infer from related code
5. **Structure > Freeform:** Use mandatory response format for feature questions
6. **Limitations > Assumptions:** Check limitations explicitly listed in tool descriptions

---

## 🔄 Maintenance

**When to Update This File:**
- New hallucination patterns emerge
- New tools are added (update examples if relevant)
- User reports new hallucination scenarios
- Tool limitations change

---

**Last Updated:** 2025-11-03  
**Status:** Active Guide - Verification Protocol + Examples Combined  
**Purpose:** Prevent hallucination by providing both HOW to verify (protocol) and WHAT correct responses look like (examples)

