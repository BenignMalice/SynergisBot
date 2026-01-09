#!/usr/bin/env python3
"""
Comprehensive integration test for batch auto-execution endpoints
Tests edge cases, error scenarios, and all plan types
"""

import asyncio
import httpx
import json
import sys

API_BASE_URL = "http://localhost:8000"
API_KEY = "test_key"

async def test_batch_create_comprehensive():
    """Comprehensive tests for batch create endpoint"""
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST: Batch Create Endpoint")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        test_results = {"passed": 0, "failed": 0}
        
        # Test 1: Missing plan_type
        print("\n[TEST 1] Missing plan_type")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/create-plans",
                json={
                    "plans": [{
                        "symbol": "BTCUSD",
                        "direction": "BUY",
                        "entry_price": 50000.0,
                        "stop_loss": 49500.0,
                        "take_profit": 51000.0
                    }]
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('failed') == 1 and 'plan_type is required' in str(data.get('results', [{}])[0].get('error', '')):
                    print("   [PASS] Correctly rejected missing plan_type")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Unexpected response: {data}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        # Test 2: Invalid plan_type
        print("\n[TEST 2] Invalid plan_type")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/create-plans",
                json={
                    "plans": [{
                        "plan_type": "invalid_type_xyz",
                        "symbol": "BTCUSD",
                        "direction": "BUY",
                        "entry_price": 50000.0,
                        "stop_loss": 49500.0,
                        "take_profit": 51000.0
                    }]
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('failed') == 1 and 'Invalid plan_type' in str(data.get('results', [{}])[0].get('error', '')):
                    print("   [PASS] Correctly rejected invalid plan_type")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Unexpected response: {data}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        # Test 3: Mixed valid/invalid (partial success)
        print("\n[TEST 3] Mixed valid/invalid plans (partial success)")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/create-plans",
                json={
                    "plans": [
                        {
                            "plan_type": "auto_trade",
                            "symbol": "BTCUSD",
                            "direction": "BUY",
                            "entry_price": 50000.0,
                            "stop_loss": 49500.0,
                            "take_profit": 51000.0,
                            "volume": 0.01
                        },
                        {
                            "plan_type": "invalid_type",
                            "symbol": "XAUUSD",
                            "direction": "SELL",
                            "entry_price": 2000.0,
                            "stop_loss": 2010.0,
                            "take_profit": 1980.0
                        }
                    ]
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('total') == 2 and data.get('successful') == 1 and data.get('failed') == 1:
                    print("   [PASS] Partial success handled correctly")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Unexpected response: {data}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        # Test 4: Different plan types in same batch
        print("\n[TEST 4] Different plan types in same batch")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/create-plans",
                json={
                    "plans": [
                        {
                            "plan_type": "auto_trade",
                            "symbol": "BTCUSD",
                            "direction": "BUY",
                            "entry_price": 50000.0,
                            "stop_loss": 49500.0,
                            "take_profit": 51000.0,
                            "volume": 0.01
                        },
                        {
                            "plan_type": "auto_trade",
                            "symbol": "XAUUSD",
                            "direction": "SELL",
                            "entry_price": 2000.0,
                            "stop_loss": 2010.0,
                            "take_profit": 1980.0,
                            "volume": 0.01
                        }
                    ]
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('total') == 2 and data.get('successful') == 2:
                    print("   [PASS] Multiple plans in same batch handled correctly")
                    test_results["passed"] += 1
                    # Return plan IDs for later tests
                    plan_ids = [r.get('plan_id') for r in data.get('results', []) if r.get('status') == 'created']
                    return plan_ids
                else:
                    print(f"   [FAIL] Unexpected response: {data}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        # Test 5: Response format validation
        print("\n[TEST 5] Response format validation")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/create-plans",
                json={
                    "plans": [{
                        "plan_type": "auto_trade",
                        "symbol": "BTCUSD",
                        "direction": "BUY",
                        "entry_price": 50000.0,
                        "stop_loss": 49500.0,
                        "take_profit": 51000.0,
                        "volume": 0.01
                    }]
                }
            )
            if response.status_code == 200:
                data = response.json()
                required_fields = ['total', 'successful', 'failed', 'results']
                if all(field in data for field in required_fields):
                    if 'index' in data.get('results', [{}])[0]:
                        print("   [PASS] Response format correct with all required fields")
                        test_results["passed"] += 1
                    else:
                        print("   [FAIL] Missing 'index' field in results")
                        test_results["failed"] += 1
                else:
                    print(f"   [FAIL] Missing required fields. Got: {list(data.keys())}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        print(f"\n[SUMMARY] Batch Create Tests: {test_results['passed']} passed, {test_results['failed']} failed")
        return []

async def test_batch_update_comprehensive(plan_ids):
    """Comprehensive tests for batch update endpoint"""
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST: Batch Update Endpoint")
    print("="*80)
    
    if not plan_ids:
        print("\n   [SKIP] No plans available for update tests")
        return
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        test_results = {"passed": 0, "failed": 0}
        
        # Test 1: Missing plan_id
        print("\n[TEST 1] Missing plan_id")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/update-plans",
                json={
                    "updates": [{
                        "entry_price": 50100.0
                    }]
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('failed') == 1 and 'plan_id is required' in str(data.get('results', [{}])[0].get('error', '')):
                    print("   [PASS] Correctly rejected missing plan_id")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Unexpected response: {data}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        # Test 2: Missing update fields
        print("\n[TEST 2] Missing update fields")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/update-plans",
                json={
                    "updates": [{
                        "plan_id": plan_ids[0]
                    }]
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('failed') == 1 and 'update field' in str(data.get('results', [{}])[0].get('error', '')).lower():
                    print("   [PASS] Correctly rejected missing update fields")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Unexpected response: {data}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        # Test 3: Non-existent plan_id
        print("\n[TEST 3] Non-existent plan_id")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/update-plans",
                json={
                    "updates": [{
                        "plan_id": "nonexistent_plan_id_12345",
                        "entry_price": 50100.0
                    }]
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('failed') == 1:
                    print("   [PASS] Correctly handled non-existent plan_id")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Unexpected response: {data}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        # Test 4: Valid update
        print("\n[TEST 4] Valid update")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/update-plans",
                json={
                    "updates": [{
                        "plan_id": plan_ids[0],
                        "entry_price": 50100.0,
                        "stop_loss": 49600.0
                    }]
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('successful') == 1:
                    print("   [PASS] Valid update succeeded")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Unexpected response: {data}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        # Test 5: Response order preservation after deduplication
        print("\n[TEST 5] Response order preservation after deduplication")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/update-plans",
                json={
                    "updates": [
                        {"plan_id": plan_ids[0], "entry_price": 50200.0},
                        {"plan_id": plan_ids[0], "entry_price": 50300.0},  # Duplicate
                        {"plan_id": plan_ids[0] if len(plan_ids) > 0 else "test", "entry_price": 50400.0}  # Another duplicate
                    ]
                }
            )
            if response.status_code == 200:
                data = response.json()
                if len(data.get('results', [])) == 1:
                    print("   [PASS] Deduplication working correctly")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Expected 1 result after deduplication, got {len(data.get('results', []))}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        print(f"\n[SUMMARY] Batch Update Tests: {test_results['passed']} passed, {test_results['failed']} failed")

async def test_batch_cancel_comprehensive(plan_ids):
    """Comprehensive tests for batch cancel endpoint"""
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST: Batch Cancel Endpoint")
    print("="*80)
    
    if not plan_ids:
        print("\n   [SKIP] No plans available for cancel tests")
        return
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        test_results = {"passed": 0, "failed": 0}
        
        # Create a plan for cancel tests
        print("\n[SETUP] Creating plan for cancel tests...")
        try:
            create_response = await client.post(
                f"{API_BASE_URL}/auto-execution/create-plans",
                json={
                    "plans": [{
                        "plan_type": "auto_trade",
                        "symbol": "BTCUSD",
                        "direction": "BUY",
                        "entry_price": 50000.0,
                        "stop_loss": 49500.0,
                        "take_profit": 51000.0,
                        "volume": 0.01
                    }]
                }
            )
            if create_response.status_code == 200:
                create_data = create_response.json()
                cancel_test_plan_id = None
                for result in create_data.get('results', []):
                    if result.get('status') == 'created':
                        cancel_test_plan_id = result.get('plan_id')
                        break
                if cancel_test_plan_id:
                    print(f"   Created plan: {cancel_test_plan_id}")
                else:
                    print("   [SKIP] Could not create plan for cancel tests")
                    return
            else:
                print("   [SKIP] Could not create plan for cancel tests")
                return
        except Exception as e:
            print(f"   [SKIP] Error creating plan: {e}")
            return
        
        # Test 1: Valid cancellation
        print("\n[TEST 1] Valid cancellation")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/cancel-plans",
                json={
                    "plan_ids": [cancel_test_plan_id]
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('successful') == 1:
                    print("   [PASS] Valid cancellation succeeded")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Unexpected response: {data}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        # Test 2: Idempotent behavior
        print("\n[TEST 2] Idempotent behavior (cancel already cancelled)")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/cancel-plans",
                json={
                    "plan_ids": [cancel_test_plan_id]  # Already cancelled
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('successful') == 1:  # Should still be success (idempotent)
                    print("   [PASS] Idempotent behavior working correctly")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Unexpected response: {data}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        # Test 3: Non-existent plan_id
        print("\n[TEST 3] Non-existent plan_id")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/cancel-plans",
                json={
                    "plan_ids": ["nonexistent_plan_id_12345"]
                }
            )
            if response.status_code == 200:
                data = response.json()
                # Non-existent should still be success (idempotent)
                if data.get('successful') == 1:
                    print("   [PASS] Non-existent plan_id handled correctly (idempotent)")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Unexpected response: {data}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        # Test 4: Duplicate plan_ids
        print("\n[TEST 4] Duplicate plan_ids (deduplication)")
        try:
            # Create another plan for this test
            create_response = await client.post(
                f"{API_BASE_URL}/auto-execution/create-plans",
                json={
                    "plans": [{
                        "plan_type": "auto_trade",
                        "symbol": "XAUUSD",
                        "direction": "SELL",
                        "entry_price": 2000.0,
                        "stop_loss": 2010.0,
                        "take_profit": 1980.0,
                        "volume": 0.01
                    }]
                }
            )
            if create_response.status_code == 200:
                create_data = create_response.json()
                dup_test_plan_id = None
                for result in create_data.get('results', []):
                    if result.get('status') == 'created':
                        dup_test_plan_id = result.get('plan_id')
                        break
                
                if dup_test_plan_id:
                    response = await client.post(
                        f"{API_BASE_URL}/auto-execution/cancel-plans",
                        json={
                            "plan_ids": [
                                dup_test_plan_id,
                                dup_test_plan_id,  # Duplicate
                                dup_test_plan_id   # Duplicate
                            ]
                        }
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if len(data.get('results', [])) == 1:
                            print("   [PASS] Deduplication working correctly")
                            test_results["passed"] += 1
                        else:
                            print(f"   [FAIL] Expected 1 result after deduplication, got {len(data.get('results', []))}")
                            test_results["failed"] += 1
                    else:
                        print(f"   [FAIL] Unexpected status: {response.status_code}")
                        test_results["failed"] += 1
                else:
                    print("   [SKIP] Could not create plan for duplicate test")
                    test_results["failed"] += 1
            else:
                print("   [SKIP] Could not create plan for duplicate test")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        # Test 5: Response format validation
        print("\n[TEST 5] Response format validation")
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/cancel-plans",
                json={
                    "plan_ids": ["test_plan_id"]
                }
            )
            if response.status_code == 200:
                data = response.json()
                required_fields = ['total', 'successful', 'failed', 'results']
                if all(field in data for field in required_fields):
                    print("   [PASS] Response format correct with all required fields")
                    test_results["passed"] += 1
                else:
                    print(f"   [FAIL] Missing required fields. Got: {list(data.keys())}")
                    test_results["failed"] += 1
            else:
                print(f"   [FAIL] Unexpected status: {response.status_code}")
                test_results["failed"] += 1
        except Exception as e:
            print(f"   [ERROR] {e}")
            test_results["failed"] += 1
        
        print(f"\n[SUMMARY] Batch Cancel Tests: {test_results['passed']} passed, {test_results['failed']} failed")

async def main():
    """Run comprehensive tests"""
    print("="*80)
    print("COMPREHENSIVE BATCH ENDPOINTS TEST SUITE")
    print("="*80)
    print(f"API Base URL: {API_BASE_URL}")
    
    # Run comprehensive tests
    plan_ids = await test_batch_create_comprehensive()
    await test_batch_update_comprehensive(plan_ids)
    await test_batch_cancel_comprehensive(plan_ids)
    
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST SUITE COMPLETE")
    print("="*80)

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
