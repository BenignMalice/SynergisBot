# Anti-Hallucination Implementation Plan

## 📋 Overview

This plan outlines a comprehensive strategy to prevent ChatGPT from hallucinating features that don't exist in the MoneyBot system. The plan is organized into 6 phases, prioritized by impact and effort.

---

## 🎯 Goal

Prevent ChatGPT from:
- Claiming features exist when they don't
- Inferring capabilities from related code/features
- Using confident language ("now enabled", "activated") for non-existent features
- Combining separate tools to describe "new systems"

---

## 📊 Phase Breakdown

### Phase 1: Foundation - System-Level Instructions (Priority: HIGH)

**Goal:** Add core anti-hallucination rules at the highest level where ChatGPT reads instructions.

**Tasks:**

1. **Add "CRITICAL: ACCURACY REQUIREMENTS" section to `openai.yaml`**
   - **Location:** Right after line 100 (after "CRITICAL RESPONSE FORMATTING REQUIREMENTS")
   - **Content:** Core rules preventing hallucination
   - **Format:** Clear, prominent warning section with examples

2. **Add to `docs/ChatGPT_Knowledge_Document.md`**
   - **Location:** After the "CRITICAL PRESENTATION RULE" section
   - **Content:** Detailed uncertainty handling protocol
   - **Format:** Step-by-step verification process

3. **Update `docs/CHATGPT_FORMATTING_INSTRUCTIONS.md`**
   - **Location:** After "CRITICAL FORMATTING REQUIREMENT" section
   - **Content:** Examples of correct vs. wrong responses about features
   - **Format:** Side-by-side comparison

**Dependencies:** None  
**Estimated Effort:** 2-3 hours  
**Impact:** ⭐⭐⭐ HIGH - Sets foundation for all other changes

---

### Phase 2: Tool Description Updates (Priority: HIGH)

**Goal:** Add explicit "Does NOT do" sections to each tool description to prevent inference.

**Tools to Update (in order of priority):**

1. **`moneybot.analyse_symbol_full`**
   - Current: Describes what it does
   - Add: Explicit list of what it does NOT do
   - Examples: "Does NOT adjust alert zones dynamically", "Does NOT link pairs together"

2. **`moneybot.analyse_range_scalp_opportunity`**
   - Current: Describes range scalping features
   - Add: Explicit limitations (e.g., "Does NOT auto-enable adaptive volatility modes")

3. **`moneybot.macro_context`**
   - Current: Describes macro data
   - Add: "Does NOT automatically adjust other tools based on this data"

4. **Session-related tools** (if any exist)
   - Add: "Does NOT dynamically adjust alert zones based on session"

5. **All other analysis tools**
   - Add: Standardized "Limitations" section

**Template for Each Tool:**
```
⚠️ LIMITATIONS - What This Tool Does NOT Do:
- Does NOT [specific capability that might be inferred]
- Does NOT [another inferred capability]
- Does NOT automatically enable/activate features
- This tool only [specific action], it does not [common misconception]
```

**Tasks:**

1. **Identify all tools in `openai.yaml`**
   - Check enum list (lines 312-345)
   - Check examples section (lines 700+)
   - Create complete list of all tools

2. **For each tool, identify potential hallucinations**
   - What might ChatGPT infer from related features?
   - What common misconceptions exist?
   - What capabilities are "close but not quite"?

3. **Add "Limitations" section to each tool description**
   - Use template above
   - Be specific, not generic
   - Include explicit "Does NOT" statements

4. **Add "Does NOT do" list to each tool's description field**
   - In the `arguments.properties` section
   - In the tool's main description
   - In examples where relevant

**Dependencies:** None  
**Estimated Effort:** 4-6 hours  
**Impact:** ⭐⭐⭐ HIGH - Prevents inference from tool descriptions

---

### Phase 3: Response Format Requirements (Priority: MEDIUM)

**Goal:** Require ChatGPT to structure responses with verification sections.

**Tasks:**

1. **Define standard response format in `openai.yaml`**
   - Add section: "MANDATORY RESPONSE STRUCTURE FOR FEATURE DESCRIPTIONS"
   - Include sections: ✅ Verified Features, ❓ Uncertain Features, ⚠️ Limitations
   - Make it prominent (near top of description)

2. **Add format template to `docs/CHATGPT_FORMATTING_INSTRUCTIONS.md`**
   - Show example responses using new format
   - Include when to use each section
   - Show nested structure if needed

3. **Create example library**
   - **File:** `docs/ANTI_HALLUCINATION_EXAMPLES.md`
   - **Content:** Good vs. bad examples for common scenarios
   - **Scenarios:** Feature claims, capability questions, "can you enable X?" questions

**Dependencies:** Phase 1 (needs system-level instructions first)  
**Estimated Effort:** 3-4 hours  
**Impact:** ⭐⭐ MEDIUM - Provides structure for accurate responses

---

### Phase 4: Verification Protocol (Priority: HIGH)

**Goal:** Teach ChatGPT a step-by-step verification process before claiming features exist.

**Tasks:**

1. **Create verification flowchart**
   - **File:** `docs/CHATGPT_VERIFICATION_PROTOCOL.md`
   - **Content:** Decision tree for feature verification
   - **Steps:** Check tool → Check description → Admit uncertainty → Never infer

2. **Add "Feature Discovery Protocol" to `openai.yaml`**
   - **Location:** In main description section
   - **Content:** Step-by-step process before claiming features
   - **Format:** Numbered list with clear decision points

3. **Add to `docs/ChatGPT_Knowledge_Document.md`**
   - **Location:** In prominent section
   - **Content:** "How to Verify Features Before Claiming They Exist"
   - **Format:** Checklist-style guide

**Dependencies:** Phase 1  
**Estimated Effort:** 2-3 hours  
**Impact:** ⭐⭐⭐ HIGH - Changes ChatGPT's decision process

---

### Phase 5: Negative Examples & Teaching (Priority: MEDIUM)

**Goal:** Use examples to train ChatGPT on correct behavior patterns.

**Tasks:**

1. **Create `docs/ANTI_HALLUCINATION_EXAMPLES.md`**
   - **Scenarios:**
     - User: "Can you enable adaptive volatility?"
     - User: "Does the system have cross-pair correlation?"
     - User: "Set up dynamic alert zones"
   - **For each:** ❌ Wrong response + ✅ Correct response with explanation

2. **Add negative examples to `openai.yaml`**
   - **Location:** After "CRITICAL: ACCURACY REQUIREMENTS"
   - **Content:** Real examples of hallucination with corrections
   - **Format:** Side-by-side comparison

3. **Update tool examples in `openai.yaml`**
   - Add "What NOT to do" examples alongside correct examples
   - Show common misconceptions

**Dependencies:** Phase 1, Phase 2  
**Estimated Effort:** 3-4 hours  
**Impact:** ⭐⭐ MEDIUM - Reinforces correct patterns through examples

---

### Phase 6: Tool Response Structure Updates (Priority: LOW - Future Enhancement)

**Goal:** Modify tool responses to include explicit capability flags.

**Tasks:**

1. **Identify tools that return capability information**
   - Check: `desktop_agent.py` tool implementations
   - Identify: Tools that could include `capabilities: {...}` in responses

2. **Design response schema**
   - Add: `capabilities` object with explicit true/false flags
   - Example: `{"session_analysis": true, "volatility_adjustment": false}`

3. **Update tool implementations** (if needed)
   - Modify: Tool response handlers to include capability flags
   - Add: Explicit "not_implemented" lists where relevant

**Dependencies:** None (optional enhancement)  
**Estimated Effort:** 8-12 hours (requires code changes)  
**Impact:** ⭐ LOW-MEDIUM - Helpful but not essential

**Note:** This phase requires code changes, so it's marked as optional. The other phases can be implemented with documentation-only changes.

---

## 📅 Implementation Order & Timeline

### Week 1: Critical Fixes
- **Day 1-2:** Phase 1 (System-level instructions)
- **Day 3-4:** Phase 2 (Tool description updates - high-priority tools first)
- **Day 5:** Phase 4 (Verification protocol)

### Week 2: Reinforcement
- **Day 1-2:** Phase 3 (Response format requirements)
- **Day 3-4:** Phase 5 (Negative examples)

### Week 3: Enhancement (Optional)
- **Phase 6** (Tool response structure updates) - if desired

---

## 🎯 Priority Matrix

| Phase | Priority | Impact | Effort | Dependencies |
|-------|----------|--------|--------|--------------|
| Phase 1 | **HIGH** | **HIGH** | Low | None |
| Phase 2 | **HIGH** | **HIGH** | Medium | None |
| Phase 4 | **HIGH** | **HIGH** | Low | Phase 1 |
| Phase 3 | Medium | Medium | Medium | Phase 1 |
| Phase 5 | Medium | Medium | Medium | Phase 1, 2 |
| Phase 6 | Low | Low-Medium | High | None (optional) |

---

## ✅ Success Metrics

After implementation, ChatGPT should:

1. ✅ Say "I need to verify" instead of claiming features exist
2. ✅ Use uncertainty language ("may exist", "would require verification")
3. ✅ Separate verified vs. inferred features in responses
4. ✅ Never use "now enabled" or "activated" without tool confirmation
5. ✅ Reference tool limitations when asked about capabilities

---

## 📁 Files to Modify

### Primary Files:
- `openai.yaml` (main tool descriptions)
- `docs/ChatGPT_Knowledge_Document.md` (main knowledge base)
- `docs/CHATGPT_FORMATTING_INSTRUCTIONS.md` (formatting guide)

### New Files to Create:
- `docs/ANTI_HALLUCINATION_EXAMPLES.md` (example library)
- `docs/CHATGPT_VERIFICATION_PROTOCOL.md` (verification flowchart)

### Optional (if doing Phase 6):
- `desktop_agent.py` (tool response handlers)

---

## ⚠️ Risk Mitigation

### Risk 1: Too Many Restrictions Make ChatGPT Too Cautious
**Mitigation:** Balance uncertainty language with helpful responses. Structure responses to show verified info prominently, uncertainty as footnote.

### Risk 2: Users Find Uncertainty Language Annoying
**Mitigation:** Make ChatGPT helpful by saying "I can check" and then actually checking, rather than just saying "I don't know".

### Risk 3: Some Tools Genuinely Combine Features
**Mitigation:** Explicitly document legitimate feature combinations vs. inferred ones. Make distinction clear.

---

## 🚀 Quick Win (Do First)

### Immediate Action (30 minutes):

1. Add "CRITICAL: ACCURACY REQUIREMENTS" section to `openai.yaml` (after line 100)
2. Add 3-5 core rules about never claiming features without verification
3. Add 2-3 examples of wrong vs. right responses

This provides immediate protection while full plan is implemented.

---

## 📝 Implementation Checklist

### Phase 1: System-Level Instructions
- [ ] Add "CRITICAL: ACCURACY REQUIREMENTS" to `openai.yaml`
- [ ] Add uncertainty handling to `ChatGPT_Knowledge_Document.md`
- [ ] Add examples to `CHATGPT_FORMATTING_INSTRUCTIONS.md`

### Phase 2: Tool Descriptions
- [x] Identify all tools in `openai.yaml`
- [x] Add limitations to `moneybot.analyse_symbol_full` (main description + example)
- [x] Add limitations to `moneybot.analyse_range_scalp_opportunity` (main description + example)
- [x] Add limitations to `moneybot.macro_context` (main description + example)
- [x] Add limitations to `moneybot.add_alert` (main description)
- [ ] Add limitations to all other analysis tools (optional - lower priority)

### Phase 3: Response Format
- [x] Define response structure in `openai.yaml` (mandatory template added)
- [x] Add format template to `CHATGPT_FORMATTING_INSTRUCTIONS.md` (with 3 examples)
- [x] Create `ANTI_HALLUCINATION_EXAMPLES.md` (10 comprehensive scenarios)

### Phase 4: Verification Protocol
- [x] Create `CHATGPT_VERIFICATION_PROTOCOL.md` (complete decision tree + examples)
- [x] Add protocol to `openai.yaml` (Feature Discovery Protocol with 4 steps)
- [x] Add verification guide to `ChatGPT_Knowledge_Document.md` (enhanced with 6-step flow)

### Phase 5: Negative Examples
- [x] Complete `ANTI_HALLUCINATION_EXAMPLES.md` (already created in Phase 3 with 10 scenarios)
- [x] Add examples to `openai.yaml` (4 comprehensive wrong vs. correct examples added)
- [x] Update tool examples in `openai.yaml` (added "What NOT to do" comments to high-priority tool examples)

### Phase 6: Tool Responses (Optional)
- [ ] Identify tools needing capability flags
- [ ] Design response schema
- [ ] Update tool implementations in `desktop_agent.py`

---

## 🎓 Key Principles

1. **Explicit > Implicit:** Always state what tools DON'T do explicitly
2. **Verify Before Claim:** Never claim features exist without verification
3. **Uncertainty is OK:** It's better to say "I'm not certain" than to hallucinate
4. **Structure Helps:** Formatting requirements help ChatGPT stay accurate
5. **Examples Teach:** Negative examples show ChatGPT what NOT to do

---

## 📚 Related Documentation

- `docs/CHATGPT_FORMATTING_INSTRUCTIONS.md` - Response formatting guide
- `docs/ChatGPT_Knowledge_Document.md` - Main ChatGPT knowledge base
- `openai.yaml` - Tool definitions and API schema
- `docs/CHATGPT_SETUP_GUIDE.md` - ChatGPT configuration guide

---

## 🔄 Maintenance

**Ongoing Tasks:**
- Review ChatGPT responses monthly for new hallucination patterns
- Update examples as new patterns emerge
- Add limitations to new tools as they're created
- Keep verification protocol up-to-date with system changes

---

**Last Updated:** 2025-11-03  
**Status:** Planning Phase  
**Next Step:** Begin Phase 1 implementation

