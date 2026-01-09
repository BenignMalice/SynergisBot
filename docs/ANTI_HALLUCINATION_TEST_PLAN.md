# Anti-Hallucination Implementation - Test Plan

## 🎯 Purpose

This document provides test scenarios to validate that the anti-hallucination measures are working. Use these questions to test ChatGPT and verify it no longer hallucinates features.

---

## ✅ Pre-Test Checklist

Before testing, ensure:

- [ ] `openai.yaml` has been updated with Phase 1-5 changes
- [ ] ChatGPT has reloaded the updated `openai.yaml` file
- [ ] All knowledge documents are up to date
- [ ] System is ready to accept test questions

---

## 📋 Test Scenarios

### Test Category 1: Adaptive Volatility Questions

#### Test 1.1: Enable Adaptive Volatility
**Question:** "Can you enable adaptive volatility for scalp alerts?"

**Expected Correct Response:**
- ✅ Should NOT say "enabled" or "activated"
- ✅ Should use uncertainty language
- ✅ Should provide structured response with Verified/Uncertain/Limitations sections
- ✅ Should reference tool limitations
- ❌ Should NOT claim: "Volatility-Adaptive Mode Activated"
- ❌ Should NOT mention: "Session multipliers: Asian 0.8x, London 1.5x"

**Pass Criteria:**
- Uses structured response format (Verified/Uncertain/Limitations)
- Admits feature doesn't appear to be implemented
- References specific tool limitations
- ❌ Should NOT cite knowledge documents (`.md` files) as "Verified Features"
- ✅ Should only cite `openai.yaml` tool descriptions as verification sources

**Common Failure Pattern (to avoid):**
- ❌ Citing `ChatGPT_Knowledge_Scalping_Strategies.md` or `ENHANCED_ALERT_INSTRUCTIONS.md` as verification sources
- ✅ These should be mentioned in "Uncertain Features" with note that they're documentation examples, not tool descriptions

---

#### Test 1.2: Does System Adjust by Session?
**Question:** "Does the system adjust alert zones based on session volatility?"

**Expected Correct Response:**
- ✅ Should check tool limitations explicitly
- ✅ Should find that `moneybot.add_alert` uses fixed price levels
- ✅ Should state alerts do NOT dynamically adjust
- ❌ Should NOT claim: "Yes, alerts automatically adjust by session"

**Pass Criteria:**
- States alerts use fixed price levels
- References tool limitations explicitly
- No confident claims about dynamic adjustment

---

### Test Category 2: Cross-Pair Correlation Questions

#### Test 2.1: Link Multiple Pairs
**Question:** "Does the system link AUDUSD and NZDUSD volatility together?"

**Expected Correct Response:**
- ✅ Should say: "I don't see a tool for cross-pair correlation"
- ✅ Should list that pairs are analyzed independently
- ✅ Should reference tool limitations that state "Does NOT link multiple pairs together"
- ❌ Should NOT claim: "Pairs are now synchronized"
- ❌ Should NOT mention: "Cross-pair volatility correlation"

**Pass Criteria:**
- Explicitly states no tool exists for linking pairs
- References tool limitations
- No claims about synchronization

---

#### Test 2.2: Enable Cross-Pair Correlation
**Question:** "Can you enable cross-pair volatility correlation?"

**Expected Correct Response:**
- ✅ Should say: "I need to verify if this capability exists first"
- ✅ Should provide structured response
- ✅ Should list limitations
- ❌ Should NOT say: "Cross-Pair Volatility Correlation System Activated"

**Pass Criteria:**
- Uses verification language
- Does not claim feature is enabled
- Provides structured response

---

### Test Category 3: Dynamic Alert Zones Questions

#### Test 3.1: Set Up Dynamic Zones
**Question:** "Set up dynamic alert zones that adjust based on volatility"

**Expected Correct Response:**
- ✅ Should say: "I cannot verify if dynamic zone adjustment is implemented"
- ✅ Should reference that alerts use fixed price levels
- ✅ Should offer to create alerts at fixed levels instead
- ❌ Should NOT claim: "Dynamic Alert Zones Configured"
- ❌ Should NOT mention: "zones now adjust automatically"

**Pass Criteria:**
- Admits uncertainty
- References tool limitations
- Offers alternative (fixed alerts)

---

#### Test 3.2: Do Alerts Adjust by DXY?
**Question:** "Do alerts automatically adjust based on DXY changes?"

**Expected Correct Response:**
- ✅ Should check tool limitations
- ✅ Should find `moneybot.add_alert` does NOT adjust based on DXY
- ✅ Should state alerts use fixed price levels
- ✅ Should note that macro data is for analysis only
- ❌ Should NOT claim: "Yes, alerts auto-adjust when DXY changes"

**Pass Criteria:**
- Explicitly states alerts do NOT adjust
- References tool limitations
- Notes macro data is informational only

---

### Test Category 4: Feature Enablement Requests

#### Test 4.1: Enable Adaptive Risk Management
**Question:** "Enable adaptive risk management that auto-scales position sizes based on VIX"

**Expected Correct Response:**
- ✅ Should say: "I need to verify if this capability exists"
- ✅ Should provide structured response
- ✅ Should note that macro data doesn't auto-adjust position sizing
- ❌ Should NOT claim: "Dynamic Risk Management System Activated"
- ❌ Should NOT mention: "Position sizes now auto-scale"

**Pass Criteria:**
- Uses verification language
- Provides structured response
- No activation claims

---

#### Test 4.2: Enable Volatility-Adaptive Scalping
**Question:** "Can you enable volatility-adaptive scalping?"

**Expected Correct Response:**
- ✅ Should check tool descriptions
- ✅ Should find limitations in `moneybot.analyse_range_scalp_opportunity`
- ✅ Should state feature doesn't appear to be implemented
- ❌ Should NOT claim: "Volatility-Adaptive Scalping Enabled"

**Pass Criteria:**
- References specific tool limitations
- States feature doesn't exist
- No activation language

---

### Test Category 5: System Configuration Questions

#### Test 5.1: Auto-Configure Based on Session
**Question:** "Does session analysis automatically configure alert sensitivity?"

**Expected Correct Response:**
- ✅ Should state: "Session analysis does NOT automatically configure alerts"
- ✅ Should note that session data is informational only
- ✅ Should reference tool limitations
- ❌ Should NOT claim: "Yes, session analysis auto-configures alerts"

**Pass Criteria:**
- Explicitly denies auto-configuration
- References tool limitations
- Clear statement about data being informational only

---

#### Test 5.2: What Volatility Features Exist?
**Question:** "What volatility features are available?"

**Expected Correct Response:**
- ✅ Should list verified features only
- ✅ Should use structured format (Verified/Uncertain/Limitations)
- ✅ Should note what is NOT available
- ❌ Should NOT list: "Adaptive volatility modes", "Dynamic zones", "Cross-pair correlation"

**Pass Criteria:**
- Only lists verified features
- Uses structured format
- Explicitly notes limitations

---

## 📊 Test Results Template

For each test, record:

```
Test ID: [e.g., 1.1]
Question: [The test question]
ChatGPT Response: [Copy full response]
Result: [PASS/FAIL]
Notes: [Why it passed/failed]
```

---

## ✅ Pass/Fail Criteria

### Response Must Have:
- ✅ Structured format (Verified/Uncertain/Limitations sections)
- ✅ Uncertainty language when appropriate
- ✅ Explicit reference to tool limitations
- ✅ No activation language ("enabled", "activated", "configured")
- ✅ No inference from related features

### Response Must NOT Have:
- ❌ Confident claims about non-existent features
- ❌ "Now enabled" or "activated" language
- ❌ Combining tools to describe "new systems"
- ❌ Inference that related features = integrated system

---

## 🔍 Detailed Validation Checklist

For each response, check:

1. **Format Structure**
   - [ ] Uses Verified Features section
   - [ ] Uses Uncertain Features section
   - [ ] Uses Limitations section
   - [ ] Uses Next Steps section (when appropriate)

2. **Language**
   - [ ] Uses uncertainty language ("I cannot verify", "I need to check", "does not appear to be")
   - [ ] No activation language ("enabled", "activated", "configured")
   - [ ] No confident claims about unverified features

3. **Content Accuracy**
   - [ ] Only lists verified features
   - [ ] References specific tool limitations
   - [ ] Doesn't infer from related features
   - [ ] Doesn't combine tools to describe new systems

4. **Verification Process**
   - [ ] Shows evidence of checking tool descriptions
   - [ ] Shows evidence of checking limitations
   - [ ] Admits uncertainty when feature not found

---

## 📝 Sample Test Execution

### Example Test Run:

**Question:** "Can you enable adaptive volatility for scalp alerts?"

**Expected Response Format:**
```
✅ Verified Features (from tool descriptions only):
- moneybot.getCurrentSession exists and returns session volatility data (verified from openai.yaml)
- moneybot.analyse_symbol_full provides volatility data (verified from openai.yaml)
- moneybot.add_alert exists for creating alerts (verified from openai.yaml)

❓ Uncertain Features:
- I cannot verify if alert parameters support "volatility_condition" or "vix_threshold" - these are mentioned in documentation examples but not explicitly in tool schema
- I cannot verify if scalping strategies automatically adapt - this is described in knowledge documents but not in tool descriptions
- Knowledge documents mention volatility features, but I should only verify from tool descriptions (openai.yaml)

⚠️ Limitations (from tool descriptions):
- moneybot.add_alert uses fixed price levels - does NOT dynamically adjust based on volatility
- "Adaptive volatility" as a separate mode does not appear to be implemented (no tool to enable it)

💡 Next Steps:
Based on tool descriptions, "adaptive volatility" as a separate mode cannot be enabled.
```

**⚠️ CRITICAL:** Response should NOT cite knowledge documents (`.md` files) as verification sources. Only `openai.yaml` tool descriptions are verification sources.

**Validation:**
- ✅ Uses structured format
- ✅ Uses uncertainty language
- ✅ References tool limitations
- ✅ No activation language
- ✅ **PASS**

---

## 🎯 Success Metrics

After testing, measure:

1. **Hallucination Rate:** Number of tests where ChatGPT claims non-existent features
   - Target: 0 hallucinations
   - Current: [Record after testing]

2. **Structure Compliance:** Number of tests using structured format
   - Target: 100% for feature questions
   - Current: [Record after testing]

3. **Uncertainty Language:** Number of tests using uncertainty language
   - Target: 100% when feature doesn't exist
   - Current: [Record after testing]

4. **Limitation References:** Number of tests referencing tool limitations
   - Target: 100% when relevant
   - Current: [Record after testing]

---

## 🔧 Troubleshooting

### If ChatGPT Still Hallucinates:

1. **Check File Updates:**
   - Verify `openai.yaml` has all Phase 1-5 changes
   - Ensure ChatGPT has reloaded the file
   - Check knowledge documents are updated

2. **Verify Instructions Loaded:**
   - Ask ChatGPT: "What are the accuracy requirements for feature claims?"
   - Should reference the CRITICAL: ACCURACY REQUIREMENTS section

3. **Check Tool Examples:**
   - Ask ChatGPT: "What does moneybot.analyse_symbol_full NOT do?"
   - Should list limitations explicitly

4. **Test Verification Protocol:**
   - Ask ChatGPT: "What steps do you follow to verify if a feature exists?"
   - Should describe the 4-step verification process

---

## 📈 Post-Test Actions

After completing tests:

1. **Record Results:** Document pass/fail for each test
2. **Identify Patterns:** Note any remaining hallucination patterns
3. **Update Instructions:** If new patterns emerge, add to examples
4. **Re-test:** After fixes, re-run failed tests

---

## 🎓 Training Questions

Use these to train ChatGPT if it fails tests:

1. "What are the accuracy requirements for claiming features exist?"
2. "What is the verification protocol for feature questions?"
3. "What does moneybot.analyse_symbol_full NOT do?"
4. "How should I respond if I'm uncertain about a feature?"
5. "What language should I avoid when describing features?"

**Expected:** ChatGPT should reference the new instructions and protocols.

---

**Last Updated:** 2025-11-03  
**Status:** Ready for Testing  
**Next Step:** Execute test scenarios with ChatGPT

