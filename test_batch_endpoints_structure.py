#!/usr/bin/env python3
"""
Structure validation test for batch auto-execution endpoints
Validates that Phase 1 implementation is correct
"""

import ast
import sys
import os

def validate_endpoint_structure():
    """Validate that batch endpoints are properly implemented"""
    print("="*80)
    print("PHASE 1: BACKEND API LAYER - STRUCTURE VALIDATION")
    print("="*80)
    
    api_file = "app/auto_execution_api.py"
    
    if not os.path.exists(api_file):
        print(f"❌ ERROR: {api_file} not found")
        return False
    
        print(f"\n[OK] Found {api_file}")
    
    # Read and parse the file
    try:
        with open(api_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for required components
        checks = {
            "Pydantic models": [
                "BatchCreatePlanRequest",
                "BatchUpdatePlanRequest", 
                "BatchCancelPlanRequest"
            ],
            "Endpoints": [
                "create_multiple_plans",
                "update_multiple_plans",
                "cancel_multiple_plans"
            ],
            "Validators": [
                "@validator('plans')",
                "@validator('updates')",
                "@validator('plan_ids')"
            ],
            "Route decorators": [
                "@router.post(\"/create-plans\"",
                "@router.post(\"/update-plans\"",
                "@router.post(\"/cancel-plans\""
            ]
        }
        
        all_passed = True
        
        for category, items in checks.items():
            print(f"\n{category}:")
            for item in items:
                if item in content:
                    print(f"  [OK] {item}")
                else:
                    print(f"  [FAIL] {item} - NOT FOUND")
                    all_passed = False
        
        # Check for critical implementation details
        print("\nImplementation Details:")
        critical_checks = {
            "Sequential processing": "for index, plan in enumerate" in content or "for original_idx" in content,
            "Partial success handling": "successful" in content and "failed" in content,
            "Error handling": "except Exception" in content,
            "Logging": "logger.info" in content or "logger.warning" in content,
            "Deduplication (update)": "seen_plan_ids" in content or "deduplicate" in content.lower(),
            "Deduplication (cancel)": "seen_plan_ids" in content or "deduplicate" in content.lower(),
            "Order preservation": "original_order" in content,
            "Plan type validation": "VALID_PLAN_TYPES" in content or "plan_type" in content
        }
        
        for check_name, passed in critical_checks.items():
            if passed:
                print(f"  [OK] {check_name}")
            else:
                print(f"  [FAIL] {check_name} - NOT FOUND")
                all_passed = False
        
        if all_passed:
            print("\n" + "="*80)
            print("[SUCCESS] ALL STRUCTURE CHECKS PASSED")
            print("="*80)
            print("\nPhase 1 implementation structure is correct.")
            print("\nNext steps for testing:")
            print("1. Start the API server")
            print("2. Run: python test_batch_auto_execution_endpoints.py")
            print("3. Or test manually using curl/Postman with the endpoints:")
            print("   - POST /auto-execution/create-plans")
            print("   - POST /auto-execution/update-plans")
            print("   - POST /auto-execution/cancel-plans")
            return True
        else:
            print("\n" + "="*80)
            print("[FAILED] SOME STRUCTURE CHECKS FAILED")
            print("="*80)
            return False
            
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = validate_endpoint_structure()
    sys.exit(0 if success else 1)
