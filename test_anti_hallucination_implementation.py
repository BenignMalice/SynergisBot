"""
Test script to validate anti-hallucination implementation.

This script checks that all required sections are present in the implementation files.
It does NOT test ChatGPT directly - it validates that instructions are properly placed.
"""

import re
from pathlib import Path

def check_file_exists(filepath: str) -> tuple[bool, str]:
    """Check if file exists."""
    path = Path(filepath)
    if path.exists():
        return True, f"✅ {filepath} exists"
    return False, f"❌ {filepath} missing"

def check_section_exists(filepath: str, section_pattern: str, description: str) -> tuple[bool, str]:
    """Check if a section exists in a file."""
    path = Path(filepath)
    if not path.exists():
        return False, f"❌ File {filepath} not found"
    
    content = path.read_text(encoding='utf-8')
    
    if re.search(section_pattern, content, re.IGNORECASE | re.MULTILINE):
        return True, f"✅ {description} found in {filepath}"
    return False, f"❌ {description} NOT found in {filepath}"

def main():
    """Run all validation checks."""
    print("🔍 Anti-Hallucination Implementation Validation\n")
    print("=" * 70)
    
    results = []
    
    # Phase 1: System-Level Instructions
    print("\n📋 Phase 1: System-Level Instructions")
    print("-" * 70)
    
    results.append(check_section_exists(
        "openai.yaml",
        r"CRITICAL.*ACCURACY REQUIREMENTS.*PREVENT HALLUCINATION",
        "ACCURACY REQUIREMENTS section"
    ))
    
    results.append(check_section_exists(
        "openai.yaml",
        r"NEVER claim a feature exists unless",
        "Rule 1: Never claim without verification"
    ))
    
    results.append(check_section_exists(
        "openai.yaml",
        r"NEVER combine multiple tools",
        "Rule 2: Never combine tools"
    ))
    
    results.append(check_section_exists(
        "docs/ChatGPT Knowledge Documents/ChatGPT_Knowledge_Document.md",
        r"STEP-BY-STEP VERIFICATION PROTOCOL|CRITICAL.*ACCURACY REQUIREMENTS.*PREVENT HALLUCINATION",
        "Verification protocol in main knowledge doc"
    ))
    
    results.append(check_section_exists(
        "docs/ChatGPT Knowledge Documents Updated/CHATGPT_FORMATTING_AND_EXAMPLES.md",
        r"WRONG vs CORRECT Examples|PART 2.*ANTI-HALLUCINATION|Response Examples Library",
        "Formatting examples in consolidated file"
    ))
    
    # Phase 2: Tool Limitations
    print("\n📋 Phase 2: Tool Limitations")
    print("-" * 70)
    
    results.append(check_section_exists(
        "openai.yaml",
        r"LIMITATIONS.*moneybot\.analyse_symbol_full Does NOT Do",
        "analyse_symbol_full limitations"
    ))
    
    results.append(check_section_exists(
        "openai.yaml",
        r"LIMITATIONS.*moneybot\.analyse_range_scalp_opportunity Does NOT Do",
        "analyse_range_scalp_opportunity limitations"
    ))
    
    results.append(check_section_exists(
        "openai.yaml",
        r"LIMITATIONS.*moneybot\.macro_context Does NOT Do",
        "macro_context limitations"
    ))
    
    results.append(check_section_exists(
        "openai.yaml",
        r"LIMITATIONS.*moneybot\.add_alert Does NOT Do",
        "add_alert limitations"
    ))
    
    # Phase 3: Response Format
    print("\n📋 Phase 3: Response Format Requirements")
    print("-" * 70)
    
    results.append(check_section_exists(
        "openai.yaml",
        r"MANDATORY RESPONSE STRUCTURE FOR FEATURE DESCRIPTIONS",
        "Mandatory response structure"
    ))
    
    results.append(check_section_exists(
        "openai.yaml",
        r"Verified Features|Uncertain|Limitations|MANDATORY RESPONSE STRUCTURE",
        "Response template sections"
    ))
    
    results.append(check_file_exists("docs/ChatGPT Knowledge Documents Updated/ANTI_HALLUCINATION_GUIDE.md"))
    
    # Phase 4: Verification Protocol
    print("\n📋 Phase 4: Verification Protocol")
    print("-" * 70)
    
    results.append(check_section_exists(
        "docs/ChatGPT Knowledge Documents Updated/ANTI_HALLUCINATION_GUIDE.md",
        r"Verification Decision Tree|Verification Protocol",
        "Verification protocol in consolidated guide"
    ))
    
    results.append(check_section_exists(
        "openai.yaml",
        r"FEATURE DISCOVERY PROTOCOL.*STEP-BY-STEP VERIFICATION",
        "Feature Discovery Protocol"
    ))
    
    results.append(check_section_exists(
        "openai.yaml",
        r"Step 1.*Check Tool Descriptions",
        "Verification Step 1"
    ))
    
    results.append(check_section_exists(
        "openai.yaml",
        r"Step 2.*Check Tool Limitations",
        "Verification Step 2"
    ))
    
    # Phase 5: Negative Examples
    print("\n📋 Phase 5: Negative Examples")
    print("-" * 70)
    
    results.append(check_section_exists(
        "openai.yaml",
        r"EXAMPLES.*WRONG vs CORRECT",
        "Wrong vs. Correct examples"
    ))
    
    results.append(check_section_exists(
        "openai.yaml",
        r"Adaptive Volatility Hallucination",
        "Adaptive volatility example"
    ))
    
    results.append(check_section_exists(
        "openai.yaml",
        r"Cross-Pair Correlation Hallucination",
        "Cross-pair correlation example"
    ))
    
    # Print results
    print("\n" + "=" * 70)
    print("\n📊 Validation Results Summary")
    print("=" * 70)
    
    passed = sum(1 for success, _ in results if success)
    total = len(results)
    
    for success, message in results:
        print(message)
    
    print("\n" + "=" * 70)
    print(f"\n✅ Passed: {passed}/{total} checks")
    print(f"❌ Failed: {total - passed}/{total} checks")
    
    if passed == total:
        print("\n🎉 All validation checks passed! Implementation is complete.")
    else:
        print(f"\n⚠️  {total - passed} check(s) failed. Review the implementation.")
    
    print("\n" + "=" * 70)
    print("\n📝 Next Steps:")
    print("1. Review failed checks above")
    print("2. Update missing sections")
    print("3. Re-run this validation script")
    print("4. Use docs/ANTI_HALLUCINATION_TEST_PLAN.md to test with ChatGPT")
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()

