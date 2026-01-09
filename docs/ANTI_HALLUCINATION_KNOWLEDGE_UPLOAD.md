# Anti-Hallucination Knowledge Documents - Upload Guide

## 📋 Summary

**NEW Knowledge Documents to Upload:** 2 files
**UPDATED Knowledge Documents (re-upload):** 2 files
**Actions Schema (update):** 1 file (openai.yaml)

---

## ✅ NEW Knowledge Documents (Upload These)

### 1. **`docs/ANTI_HALLUCINATION_EXAMPLES.md`** ⭐ NEW
**Purpose:** Example library showing correct vs. wrong responses for common hallucination scenarios

**Why Upload:**
- Contains 10 comprehensive examples of wrong vs. correct responses
- Covers: Adaptive Volatility, Cross-Pair Correlation, Dynamic Alert Zones, Feature Enablement, System Configuration
- Shows ChatGPT exactly how to respond correctly

**Upload Location:** Knowledge section in ChatGPT Custom GPT

---

### 2. **`docs/CHATGPT_VERIFICATION_PROTOCOL.md`** ⭐ NEW
**Purpose:** Step-by-step verification protocol with decision tree

**Why Upload:**
- Complete verification flowchart showing the 4-step process
- Decision tree for feature verification
- Common hallucination patterns with fixes
- Verification checklist

**Upload Location:** Knowledge section in ChatGPT Custom GPT

---

## 🔄 UPDATED Knowledge Documents (Re-Upload These)

If you already have these files uploaded, you need to **re-upload them** with the updated content:

### 3. **`docs/ChatGPT_Knowledge_Document.md`** 🔄 UPDATED
**What Changed:**
- Added "CRITICAL: ACCURACY REQUIREMENTS - PREVENT HALLUCINATION" section
- Enhanced verification protocol (6-step flow)
- Added uncertainty handling language guide
- Added common hallucination patterns

**Action:** Re-upload this file to replace the old version

---

### 4. **`docs/CHATGPT_FORMATTING_INSTRUCTIONS.md`** 🔄 UPDATED
**What Changed:**
- Added "MANDATORY RESPONSE STRUCTURE FOR FEATURE QUESTIONS" section
- Added 3 comprehensive examples (adaptive volatility, cross-pair correlation, dynamic alerts)
- Added key principles for feature questions

**Action:** Re-upload this file to replace the old version

---

## ⚙️ Actions Schema (Update This)

### 5. **`openai.yaml`** 🔄 UPDATED
**What Changed:**
- Added "CRITICAL: ACCURACY REQUIREMENTS - PREVENT HALLUCINATION" section (6 mandatory rules)
- Added "FEATURE DISCOVERY PROTOCOL" (4-step verification process)
- Added "MANDATORY RESPONSE STRUCTURE FOR FEATURE DESCRIPTIONS" (template)
- Added 4 comprehensive wrong vs. correct examples
- Added limitations to tool descriptions (analyse_symbol_full, analyse_range_scalp_opportunity, macro_context, add_alert)
- Added "What NOT to do" comments to tool examples

**Action:** Re-upload to Actions section (Import Schema) to replace the old version

**Note:** This is not a knowledge file - it's the Actions/API schema. Update it in the Actions section, not Knowledge section.

---

## 📝 Complete Upload Checklist

### Knowledge Section (Upload These 4 Files):

- [ ] **NEW:** `docs/ANTI_HALLUCINATION_EXAMPLES.md`
- [ ] **NEW:** `docs/CHATGPT_VERIFICATION_PROTOCOL.md`
- [ ] **UPDATED:** `docs/ChatGPT_Knowledge_Document.md` (re-upload to replace old version)
- [ ] **UPDATED:** `docs/CHATGPT_FORMATTING_INSTRUCTIONS.md` (re-upload to replace old version)

### Actions Section (Update This 1 File):

- [ ] **UPDATED:** `openai.yaml` (re-import schema to replace old version)

---

## 🎯 Quick Upload Instructions

### Step 1: Update Knowledge Files

1. Go to your Custom GPT configuration
2. Navigate to "Knowledge" section
3. **Add NEW files:**
   - Click "Upload" → Select `docs/ANTI_HALLUCINATION_EXAMPLES.md`
   - Click "Upload" → Select `docs/CHATGPT_VERIFICATION_PROTOCOL.md`
4. **Update existing files:**
   - Find `ChatGPT_Knowledge_Document.md` → Delete old version → Upload new version
   - Find `CHATGPT_FORMATTING_INSTRUCTIONS.md` → Delete old version → Upload new version

### Step 2: Update Actions Schema

1. Go to "Actions" section
2. Click "Import Schema"
3. Upload the updated `openai.yaml` file
4. This will replace the old schema with the new one

### Step 3: Verify

After uploading, test with ChatGPT:
- Ask: "What are the accuracy requirements for feature claims?"
- Should reference the new ACCURACY REQUIREMENTS section

---

## 📊 Files Not for Upload

These files are for development/testing, NOT for ChatGPT:

- ❌ `docs/ANTI_HALLUCINATION_IMPLEMENTATION_PLAN.md` - Developer documentation
- ❌ `docs/ANTI_HALLUCINATION_TEST_PLAN.md` - Testing documentation  
- ❌ `test_anti_hallucination_implementation.py` - Validation script

---

## 🔍 Verification After Upload

After uploading, test ChatGPT with these questions:

1. **"What are the accuracy requirements for claiming features exist?"**
   - Should reference CRITICAL: ACCURACY REQUIREMENTS section

2. **"What is the verification protocol for feature questions?"**
   - Should describe the 4-step verification process

3. **"What does moneybot.analyse_symbol_full NOT do?"**
   - Should list limitations explicitly

4. **"Can you enable adaptive volatility?"**
   - Should use uncertainty language and structured format
   - Should NOT claim it's enabled

If ChatGPT responds correctly to these, the implementation is working!

---

**Last Updated:** 2025-11-03  
**Status:** Ready for Upload

