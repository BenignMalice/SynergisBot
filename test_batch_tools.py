#!/usr/bin/env python3
"""
Test script for batch auto-execution tools (Phase 2)
Tests the ChatGPT tool functions
"""

import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chatgpt_auto_execution_tools import (
    tool_create_multiple_auto_plans,
    tool_update_multiple_auto_plans,
    tool_cancel_multiple_auto_plans
)

async def test_batch_create_tool():
    """Test batch create tool"""
    print("\n" + "="*80)
    print("TESTING: tool_create_multiple_auto_plans")
    print("="*80)
    
    test_results = {"passed": 0, "failed": 0}
    
    # Test 1: Valid plans
    print("\n[TEST 1] Valid plans")
    try:
        result = await tool_create_multiple_auto_plans({
            "plans": [
                {
                    "plan_type": "auto_trade",
                    "symbol": "BTCUSD",
                    "direction": "BUY",
                    "entry_price": 50000.0,
                    "stop_loss": 49500.0,
                    "take_profit": 51000.0,
                    "volume": 0.01
                }
            ]
        })
        
        if "summary" in result and "data" in result:
            print(f"   [PASS] Correct response format")
            print(f"   Summary: {result['summary']}")
            if "SUCCESS" in result['summary'] or "PARTIAL" in result['summary']:
                test_results["passed"] += 1
            else:
                test_results["failed"] += 1
        else:
            print(f"   [FAIL] Invalid response format: {result}")
            test_results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        test_results["failed"] += 1
    
    # Test 2: Missing plans parameter
    print("\n[TEST 2] Missing plans parameter")
    try:
        result = await tool_create_multiple_auto_plans({})
        
        if "summary" in result and "ERROR" in result["summary"]:
            print(f"   [PASS] Correctly rejected missing plans")
            test_results["passed"] += 1
        else:
            print(f"   [FAIL] Unexpected response: {result}")
            test_results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        test_results["failed"] += 1
    
    # Test 3: Empty plans array
    print("\n[TEST 3] Empty plans array")
    try:
        result = await tool_create_multiple_auto_plans({"plans": []})
        
        if "summary" in result and "ERROR" in result["summary"]:
            print(f"   [PASS] Correctly rejected empty array")
            test_results["passed"] += 1
        else:
            print(f"   [FAIL] Unexpected response: {result}")
            test_results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        test_results["failed"] += 1
    
    # Test 4: Invalid plans type
    print("\n[TEST 4] Invalid plans type (not array)")
    try:
        result = await tool_create_multiple_auto_plans({"plans": "not_an_array"})
        
        if "summary" in result and "ERROR" in result["summary"]:
            print(f"   [PASS] Correctly rejected invalid type")
            test_results["passed"] += 1
        else:
            print(f"   [FAIL] Unexpected response: {result}")
            test_results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        test_results["failed"] += 1
    
    print(f"\n[SUMMARY] Batch Create Tool Tests: {test_results['passed']} passed, {test_results['failed']} failed")
    return test_results

async def test_batch_update_tool():
    """Test batch update tool"""
    print("\n" + "="*80)
    print("TESTING: tool_update_multiple_auto_plans")
    print("="*80)
    
    test_results = {"passed": 0, "failed": 0}
    
    # First create a plan to update
    print("\n[SETUP] Creating plan for update test...")
    create_result = await tool_create_multiple_auto_plans({
        "plans": [{
            "plan_type": "auto_trade",
            "symbol": "BTCUSD",
            "direction": "BUY",
            "entry_price": 50000.0,
            "stop_loss": 49500.0,
            "take_profit": 51000.0,
            "volume": 0.01
        }]
    })
    
    plan_id = None
    if "data" in create_result and "results" in create_result["data"]:
        for result in create_result["data"]["results"]:
            if result.get("status") == "created":
                plan_id = result.get("plan_id")
                break
    
    if not plan_id:
        print("   [SKIP] Could not create plan for update test")
        return test_results
    
    print(f"   Created plan: {plan_id}")
    
    # Test 1: Valid update
    print("\n[TEST 1] Valid update")
    try:
        result = await tool_update_multiple_auto_plans({
            "updates": [{
                "plan_id": plan_id,
                "entry_price": 50100.0
            }]
        })
        
        if "summary" in result and "data" in result:
            print(f"   [PASS] Correct response format")
            print(f"   Summary: {result['summary']}")
            test_results["passed"] += 1
        else:
            print(f"   [FAIL] Invalid response format: {result}")
            test_results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        test_results["failed"] += 1
    
    # Test 2: Missing updates parameter
    print("\n[TEST 2] Missing updates parameter")
    try:
        result = await tool_update_multiple_auto_plans({})
        
        if "summary" in result and "ERROR" in result["summary"]:
            print(f"   [PASS] Correctly rejected missing updates")
            test_results["passed"] += 1
        else:
            print(f"   [FAIL] Unexpected response: {result}")
            test_results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        test_results["failed"] += 1
    
    # Test 3: Duplicate plan_ids (deduplication)
    print("\n[TEST 3] Duplicate plan_ids (deduplication)")
    try:
        result = await tool_update_multiple_auto_plans({
            "updates": [
                {"plan_id": plan_id, "entry_price": 50200.0},
                {"plan_id": plan_id, "entry_price": 50300.0}  # Duplicate
            ]
        })
        
        if "summary" in result and "data" in result:
            data = result["data"]
            if "results" in data and len(data["results"]) == 1:
                print(f"   [PASS] Deduplication working correctly")
                test_results["passed"] += 1
            else:
                print(f"   [FAIL] Expected 1 result after deduplication")
                test_results["failed"] += 1
        else:
            print(f"   [FAIL] Invalid response format: {result}")
            test_results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        test_results["failed"] += 1
    
    print(f"\n[SUMMARY] Batch Update Tool Tests: {test_results['passed']} passed, {test_results['failed']} failed")
    return test_results

async def test_batch_cancel_tool():
    """Test batch cancel tool"""
    print("\n" + "="*80)
    print("TESTING: tool_cancel_multiple_auto_plans")
    print("="*80)
    
    test_results = {"passed": 0, "failed": 0}
    
    # First create a plan to cancel
    print("\n[SETUP] Creating plan for cancel test...")
    create_result = await tool_create_multiple_auto_plans({
        "plans": [{
            "plan_type": "auto_trade",
            "symbol": "BTCUSD",
            "direction": "BUY",
            "entry_price": 50000.0,
            "stop_loss": 49500.0,
            "take_profit": 51000.0,
            "volume": 0.01
        }]
    })
    
    plan_id = None
    if "data" in create_result and "results" in create_result["data"]:
        for result in create_result["data"]["results"]:
            if result.get("status") == "created":
                plan_id = result.get("plan_id")
                break
    
    if not plan_id:
        print("   [SKIP] Could not create plan for cancel test")
        return test_results
    
    print(f"   Created plan: {plan_id}")
    
    # Test 1: Valid cancel
    print("\n[TEST 1] Valid cancel")
    try:
        result = await tool_cancel_multiple_auto_plans({
            "plan_ids": [plan_id]
        })
        
        if "summary" in result and "data" in result:
            print(f"   [PASS] Correct response format")
            print(f"   Summary: {result['summary']}")
            test_results["passed"] += 1
        else:
            print(f"   [FAIL] Invalid response format: {result}")
            test_results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        test_results["failed"] += 1
    
    # Test 2: Missing plan_ids parameter
    print("\n[TEST 2] Missing plan_ids parameter")
    try:
        result = await tool_cancel_multiple_auto_plans({})
        
        if "summary" in result and "ERROR" in result["summary"]:
            print(f"   [PASS] Correctly rejected missing plan_ids")
            test_results["passed"] += 1
        else:
            print(f"   [FAIL] Unexpected response: {result}")
            test_results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        test_results["failed"] += 1
    
    # Test 3: Duplicate plan_ids (deduplication)
    print("\n[TEST 3] Duplicate plan_ids (deduplication)")
    try:
        # Create another plan
        create_result2 = await tool_create_multiple_auto_plans({
            "plans": [{
                "plan_type": "auto_trade",
                "symbol": "XAUUSD",
                "direction": "SELL",
                "entry_price": 2000.0,
                "stop_loss": 2010.0,
                "take_profit": 1980.0,
                "volume": 0.01
            }]
        })
        
        plan_id2 = None
        if "data" in create_result2 and "results" in create_result2["data"]:
            for result in create_result2["data"]["results"]:
                if result.get("status") == "created":
                    plan_id2 = result.get("plan_id")
                    break
        
        if plan_id2:
            result = await tool_cancel_multiple_auto_plans({
                "plan_ids": [
                    plan_id2,
                    plan_id2,  # Duplicate
                    plan_id2   # Duplicate
                ]
            })
            
            if "summary" in result and "data" in result:
                data = result["data"]
                if "results" in data and len(data["results"]) == 1:
                    print(f"   [PASS] Deduplication working correctly")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Expected 1 result after deduplication, got {len(data.get('results', []))}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Invalid response format: {result}")
                test_results["failed"] += 1
        else:
            print("   [SKIP] Could not create plan for duplicate test")
            test_results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        test_results["failed"] += 1
    
    print(f"\n[SUMMARY] Batch Cancel Tool Tests: {test_results['passed']} passed, {test_results['failed']} failed")
    return test_results

async def main():
    """Run all tool tests"""
    print("="*80)
    print("BATCH AUTO-EXECUTION TOOLS TEST SUITE (Phase 2)")
    print("="*80)
    
    results = {
        "create": await test_batch_create_tool(),
        "update": await test_batch_update_tool(),
        "cancel": await test_batch_cancel_tool()
    }
    
    total_passed = sum(r["passed"] for r in results.values())
    total_failed = sum(r["failed"] for r in results.values())
    
    print("\n" + "="*80)
    print("OVERALL TEST SUMMARY")
    print("="*80)
    print(f"Batch Create Tool: {results['create']['passed']} passed, {results['create']['failed']} failed")
    print(f"Batch Update Tool: {results['update']['passed']} passed, {results['update']['failed']} failed")
    print(f"Batch Cancel Tool: {results['cancel']['passed']} passed, {results['cancel']['failed']} failed")
    print(f"\nTotal: {total_passed} passed, {total_failed} failed")
    
    if total_failed == 0:
        print("\n[SUCCESS] All tests passed!")
    else:
        print(f"\n[WARNING] {total_failed} test(s) failed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test suite error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
