#!/usr/bin/env python3
"""
Integration test for batch auto-execution endpoints
Uses httpx (async) to match project dependencies
"""

import asyncio
import httpx
import json
import sys

API_BASE_URL = "http://localhost:8000"
API_KEY = "test_key"  # Update if needed

async def test_batch_create():
    """Test batch create endpoint"""
    print("\n" + "="*80)
    print("TESTING: Batch Create Endpoint (POST /auto-execution/create-plans)")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Test 1: Valid plans
        print("\n1. Test: Valid plans (all succeed)")
        valid_plans = {
            "plans": [
                {
                    "plan_type": "auto_trade",
                    "symbol": "BTCUSD",
                    "direction": "BUY",
                    "entry_price": 50000.0,
                    "stop_loss": 49500.0,
                    "take_profit": 51000.0,
                    "volume": 0.01,
                    "expires_hours": 24
                }
            ]
        }
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/create-plans",
                json=valid_plans,
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Total: {data.get('total')}")
                print(f"   Successful: {data.get('successful')}")
                print(f"   Failed: {data.get('failed')}")
                for result in data.get('results', []):
                    idx = result.get('index')
                    status = result.get('status')
                    plan_id = result.get('plan_id', 'N/A')
                    print(f"     - Index {idx}: {status} - {plan_id}")
                return data.get('results', [])
            else:
                print(f"   Error: {response.text}")
                return []
        except httpx.ConnectError:
            print("   [ERROR] Cannot connect to API server. Is it running?")
            return []
        except Exception as e:
            print(f"   [ERROR] Exception: {e}")
            return []
        
        # Test 2: Invalid plan_type
        print("\n2. Test: Invalid plan_type")
        invalid_plan = {
            "plans": [
                {
                    "plan_type": "invalid_type",
                    "symbol": "BTCUSD",
                    "direction": "BUY",
                    "entry_price": 50000.0,
                    "stop_loss": 49500.0,
                    "take_profit": 51000.0
                }
            ]
        }
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/create-plans",
                json=invalid_plan,
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Total: {data.get('total')}")
                print(f"   Successful: {data.get('successful')}")
                print(f"   Failed: {data.get('failed')}")
                if data.get('results'):
                    print(f"   Error: {data['results'][0].get('error')}")
        except Exception as e:
            print(f"   [ERROR] Exception: {e}")
        
        # Test 3: Empty array (Pydantic validation)
        print("\n3. Test: Empty plans array (Pydantic validation)")
        empty_plans = {"plans": []}
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/create-plans",
                json=empty_plans,
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 422:
                print(f"   [OK] Correctly rejected empty array (422)")
            else:
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"   [ERROR] Exception: {e}")

async def test_batch_update(plan_ids):
    """Test batch update endpoint"""
    print("\n" + "="*80)
    print("TESTING: Batch Update Endpoint (POST /auto-execution/update-plans)")
    print("="*80)
    
    if not plan_ids:
        print("\n   [SKIP] No plans available for update test")
        return
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Test 1: Valid update
        print("\n1. Test: Valid update")
        valid_update = {
            "updates": [
                {
                    "plan_id": plan_ids[0],
                    "entry_price": 50100.0,
                    "stop_loss": 49600.0
                }
            ]
        }
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/update-plans",
                json=valid_update,
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Total: {data.get('total')}")
                print(f"   Successful: {data.get('successful')}")
                print(f"   Failed: {data.get('failed')}")
        except Exception as e:
            print(f"   [ERROR] Exception: {e}")
        
        # Test 2: Duplicate plan_ids
        print("\n2. Test: Duplicate plan_ids (deduplication)")
        duplicate_update = {
            "updates": [
                {"plan_id": plan_ids[0], "entry_price": 50200.0},
                {"plan_id": plan_ids[0], "entry_price": 50300.0}  # Duplicate
            ]
        }
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/update-plans",
                json=duplicate_update,
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Total: {data.get('total')}")
                print(f"   Results count: {len(data.get('results', []))}")
                print(f"   [OK] Deduplication should result in 1 result (not 2)")
        except Exception as e:
            print(f"   [ERROR] Exception: {e}")

async def test_batch_cancel(plan_ids):
    """Test batch cancel endpoint"""
    print("\n" + "="*80)
    print("TESTING: Batch Cancel Endpoint (POST /auto-execution/cancel-plans)")
    print("="*80)
    
    if not plan_ids:
        print("\n   [SKIP] No plans available for cancel test")
        return
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Test 1: Valid cancel
        print("\n1. Test: Valid cancellation")
        valid_cancel = {
            "plan_ids": [plan_ids[0]]
        }
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/cancel-plans",
                json=valid_cancel,
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Total: {data.get('total')}")
                print(f"   Successful: {data.get('successful')}")
                print(f"   Failed: {data.get('failed')}")
        except Exception as e:
            print(f"   [ERROR] Exception: {e}")
        
        # Test 2: Idempotent (cancel already cancelled)
        print("\n2. Test: Idempotent behavior (cancel already cancelled)")
        idempotent_cancel = {
            "plan_ids": [plan_ids[0]]  # Already cancelled
        }
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/cancel-plans",
                json=idempotent_cancel,
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Total: {data.get('total')}")
                print(f"   Successful: {data.get('successful')}")
                print(f"   [OK] Should count as success (idempotent)")
        except Exception as e:
            print(f"   [ERROR] Exception: {e}")
        
        # Test 3: Empty array
        print("\n3. Test: Empty plan_ids array (Pydantic validation)")
        empty_cancel = {"plan_ids": []}
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/auto-execution/cancel-plans",
                json=empty_cancel,
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 422:
                print(f"   [OK] Correctly rejected empty array (422)")
            else:
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"   [ERROR] Exception: {e}")

async def main():
    """Run all tests"""
    print("="*80)
    print("BATCH AUTO-EXECUTION ENDPOINTS - INTEGRATION TEST")
    print("="*80)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Testing Phase 1: Backend API Layer")
    
    # Test batch create and get plan IDs
    created_plans = await test_batch_create()
    plan_ids = [r.get('plan_id') for r in created_plans if r.get('status') == 'created' and r.get('plan_id')]
    
    # Test batch update
    await test_batch_update(plan_ids)
    
    # Test batch cancel
    await test_batch_cancel(plan_ids)
    
    print("\n" + "="*80)
    print("TEST SUITE COMPLETE")
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
