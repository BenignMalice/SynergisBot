# ⚠️ IMPORTANT: Unicode Emoji Warning

## 🚨 **CRITICAL NOTE FOR FUTURE DEVELOPMENT**

### **DO NOT USE UNICODE EMOJIS IN PYTHON SCRIPTS**

**Problem:**
- Unicode emojis (🧪, ✅, ❌, 🔄, 📊, etc.) cause `UnicodeEncodeError: 'charmap' codec can't encode character` errors on Windows systems
- This breaks script execution and testing

**Solution:**
- Use plain text alternatives instead of emojis
- Examples:
  - ✅ → "SUCCESS:"
  - ❌ → "ERROR:"
  - ⚠️ → "WARNING:"
  - 🔄 → "Processing..."
  - 📊 → "Data:"
  - 🧪 → "Testing:"

**Examples of CORRECT usage:**
```python
print("SUCCESS: Scraper is working correctly!")
print("ERROR: Import error occurred")
print("WARNING: No events found")
print("Testing individual sources...")
print("Data Quality Analysis:")
```

**Examples of INCORRECT usage:**
```python
print("✅ Scraper is working correctly!")  # ❌ DON'T DO THIS
print("❌ Import error occurred")         # ❌ DON'T DO THIS
print("⚠️ No events found")              # ❌ DON'T DO THIS
print("🔄 Testing individual sources...") # ❌ DON'T DO THIS
print("📊 Data Quality Analysis:")        # ❌ DON'T DO THIS
```

**Remember:**
- Windows PowerShell/Command Prompt uses cp1252 encoding
- Unicode emojis are not supported in this encoding
- Always use plain ASCII text for cross-platform compatibility
- This applies to ALL Python scripts, test files, and logging

**Last Updated:** 2025-01-14
**Status:** ACTIVE WARNING
