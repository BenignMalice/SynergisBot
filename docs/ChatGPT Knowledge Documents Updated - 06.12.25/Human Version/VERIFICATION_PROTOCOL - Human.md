# ChatGPT Verification Protocol

## 🎯 Purpose

This document provides a step-by-step decision tree for ChatGPT to verify features before claiming they exist. It prevents hallucination by requiring explicit verification.

---

## 📊 Verification Decision Tree

```
START: User asks about a feature/capability
│
├─→ Step 1: Check Tool Descriptions Explicitly
│   │
│   ├─→ Feature found in tool description?
│   │   │
│   │   ├─→ YES → ✅ Describe it (with confidence)
│   │   │   └─→ Reference specific tool and capability
│   │   │
│   │   └─→ NO → Continue to Step 2
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

## ✅ Verification Checklist

Before claiming any feature exists, verify:

- [ ] Feature name appears in tool description?
- [ ] Feature explicitly mentioned as a capability?
- [ ] Feature NOT listed in "Does NOT Do" section?
- [ ] Not inferring from related features?
- [ ] Using uncertainty language if uncertain?
- [ ] Structured response format used?
- [ ] No activation language ("enabled", "activated")?

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

## 🎓 Key Principles

1. **Explicit > Implicit:** Only claim features that are explicitly described
2. **Uncertainty > Hallucination:** Better to say "I'm not certain" than to make up features
3. **Verify > Infer:** Always verify, never infer from related code
4. **Structure > Freeform:** Use mandatory response format for feature questions
5. **Limitations > Assumptions:** Check limitations explicitly listed in tool descriptions

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

**Last Updated:** 2025-11-03  
**Status:** Active Protocol

