#!/usr/bin/env python3
"""
Test script for batch auto-execution endpoints
Tests Phase 1 implementation: Backend API Layer
"""

try:
    import httpx
    USE_HTTPX = True
except ImportError:
    try:
        import requests
        USE_HTTPX = False
    except ImportError:
        print("ERROR: Neither httpx nor requests module is available.")
        print("Please install one of them: pip install httpx or pip install requests")
        exit(1)

import json
from typing import Dict, Any, List

API_BASE_URL = "http://localhost:8000"
API_KEY = "test_key"  # Update if needed

def test_batch_create_endpoint():
    """Test batch create endpoint"""
    print("\n" + "="*80)
    print("TESTING: Batch Create Endpoint (POST /auto-execution/create-plans)")
    print("="*80)
    
    # Test 1: Valid plans (all succeed)
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
            },
            {
                "plan_type": "choch",
                "symbol": "XAUUSD",
                "direction": "SELL",
                "entry_price": 2000.0,
                "stop_loss": 2010.0,
                "take_profit": 1980.0,
                "volume": 0.01,
                "choch_type": "bear",
                "expires_hours": 24
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/auto-execution/create-plans",
            json=valid_plans,
            headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
            timeout=60
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Total: {data.get('total')}")
            print(f"   Successful: {data.get('successful')}")
            print(f"   Failed: {data.get('failed')}")
            print(f"   Results: {len(data.get('results', []))} items")
            for result in data.get('results', []):
                print(f"     - Index {result.get('index')}: {result.get('status')} - {result.get('plan_id', 'N/A')}")
        else:
            print(f"   Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ⚠ Connection error: API server may not be running")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 2: Invalid plan_type
    print("\n2. Test: Invalid plan_type")
    invalid_plan_type = {
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
        response = requests.post(
            f"{API_BASE_URL}/auto-execution/create-plans",
            json=invalid_plan_type,
            headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
            timeout=60
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Total: {data.get('total')}")
            print(f"   Successful: {data.get('successful')}")
            print(f"   Failed: {data.get('failed')}")
            if data.get('results'):
                print(f"   Error: {data['results'][0].get('error')}")
        else:
            print(f"   Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ⚠ Connection error: API server may not be running")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 3: Missing plan_type
    print("\n3. Test: Missing plan_type")
    missing_plan_type = {
        "plans": [
            {
                "symbol": "BTCUSD",
                "direction": "BUY",
                "entry_price": 50000.0,
                "stop_loss": 49500.0,
                "take_profit": 51000.0
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/auto-execution/create-plans",
            json=missing_plan_type,
            headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
            timeout=60
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Total: {data.get('total')}")
            print(f"   Successful: {data.get('successful')}")
            print(f"   Failed: {data.get('failed')}")
            if data.get('results'):
                print(f"   Error: {data['results'][0].get('error')}")
        else:
            print(f"   Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ⚠ Connection error: API server may not be running")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 4: Empty plans array (should fail Pydantic validation)
    print("\n4. Test: Empty plans array (Pydantic validation)")
    empty_plans = {
        "plans": []
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/auto-execution/create-plans",
            json=empty_plans,
            headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
            timeout=60
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 422:
            print(f"   ✓ Correctly rejected empty array (422)")
        else:
            print(f"   Response: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ⚠ Connection error: API server may not be running")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 5: Mixed valid/invalid (partial success)
    print("\n5. Test: Mixed valid/invalid (partial success)")
    mixed_plans = {
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
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/auto-execution/create-plans",
            json=mixed_plans,
            headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
            timeout=60
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Total: {data.get('total')}")
            print(f"   Successful: {data.get('successful')}")
            print(f"   Failed: {data.get('failed')}")
            for result in data.get('results', []):
                status = result.get('status')
                idx = result.get('index')
                if status == "created":
                    print(f"     ✓ Index {idx}: Created - {result.get('plan_id')}")
                else:
                    print(f"     ✗ Index {idx}: Failed - {result.get('error')}")
        else:
            print(f"   Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ⚠ Connection error: API server may not be running")
    except Exception as e:
        print(f"   Exception: {e}")

def test_batch_update_endpoint():
    """Test batch update endpoint"""
    print("\n" + "="*80)
    print("TESTING: Batch Update Endpoint (POST /auto-execution/update-plans)")
    print("="*80)
    
    # First, create some plans to update
    print("\n0. Creating test plans for update...")
    create_request = {
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
    
    created_plan_ids = []
    try:
        response = requests.post(
            f"{API_BASE_URL}/auto-execution/create-plans",
            json=create_request,
            headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            for result in data.get('results', []):
                if result.get('status') == 'created':
                    created_plan_ids.append(result.get('plan_id'))
            print(f"   Created {len(created_plan_ids)} plans: {created_plan_ids}")
    except requests.exceptions.ConnectionError:
        print("   ⚠ Connection error: API server may not be running")
        return
    except Exception as e:
        print(f"   Exception creating plans: {e}")
        return
    
    if not created_plan_ids:
        print("   ⚠ No plans created, skipping update tests")
        return
    
    # Test 1: Valid updates
    print("\n1. Test: Valid updates")
    valid_updates = {
        "updates": [
            {
                "plan_id": created_plan_ids[0] if created_plan_ids else "test_id_1",
                "entry_price": 50100.0,
                "stop_loss": 49600.0
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/auto-execution/update-plans",
            json=valid_updates,
            headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
            timeout=60
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Total: {data.get('total')}")
            print(f"   Successful: {data.get('successful')}")
            print(f"   Failed: {data.get('failed')}")
        else:
            print(f"   Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ⚠ Connection error: API server may not be running")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 2: Missing plan_id
    print("\n2. Test: Missing plan_id")
    missing_plan_id = {
        "updates": [
            {
                "entry_price": 50100.0
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/auto-execution/update-plans",
            json=missing_plan_id,
            headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
            timeout=60
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Total: {data.get('total')}")
            print(f"   Successful: {data.get('successful')}")
            print(f"   Failed: {data.get('failed')}")
            if data.get('results'):
                print(f"   Error: {data['results'][0].get('error')}")
        else:
            print(f"   Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ⚠ Connection error: API server may not be running")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 3: Duplicate plan_ids (should deduplicate)
    print("\n3. Test: Duplicate plan_ids (deduplication)")
    if created_plan_ids:
        duplicate_updates = {
            "updates": [
                {
                    "plan_id": created_plan_ids[0],
                    "entry_price": 50200.0
                },
                {
                    "plan_id": created_plan_ids[0],  # Duplicate
                    "entry_price": 50300.0  # This should be kept (last one)
                }
            ]
        }
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/auto-execution/update-plans",
                json=duplicate_updates,
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
                timeout=60
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Total: {data.get('total')}")
                print(f"   Successful: {data.get('successful')}")
                print(f"   Failed: {data.get('failed')}")
                print(f"   Results count: {len(data.get('results', []))}")
                print(f"   ✓ Deduplication should result in 1 result (not 2)")
        except requests.exceptions.ConnectionError:
            print("   ⚠ Connection error: API server may not be running")
        except Exception as e:
            print(f"   Exception: {e}")

def test_batch_cancel_endpoint():
    """Test batch cancel endpoint"""
    print("\n" + "="*80)
    print("TESTING: Batch Cancel Endpoint (POST /auto-execution/cancel-plans)")
    print("="*80)
    
    # First, create some plans to cancel
    print("\n0. Creating test plans for cancel...")
    create_request = {
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
    
    created_plan_ids = []
    try:
        response = requests.post(
            f"{API_BASE_URL}/auto-execution/create-plans",
            json=create_request,
            headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            for result in data.get('results', []):
                if result.get('status') == 'created':
                    created_plan_ids.append(result.get('plan_id'))
            print(f"   Created {len(created_plan_ids)} plans: {created_plan_ids}")
    except requests.exceptions.ConnectionError:
        print("   ⚠ Connection error: API server may not be running")
        return
    except Exception as e:
        print(f"   Exception creating plans: {e}")
        return
    
    if not created_plan_ids:
        print("   ⚠ No plans created, skipping cancel tests")
        return
    
    # Test 1: Valid cancellations
    print("\n1. Test: Valid cancellations")
    valid_cancels = {
        "plan_ids": created_plan_ids[:1] if created_plan_ids else ["test_id_1"]
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/auto-execution/cancel-plans",
            json=valid_cancels,
            headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
            timeout=60
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Total: {data.get('total')}")
            print(f"   Successful: {data.get('successful')}")
            print(f"   Failed: {data.get('failed')}")
            for result in data.get('results', []):
                print(f"     - {result.get('plan_id')}: {result.get('status')}")
        else:
            print(f"   Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ⚠ Connection error: API server may not be running")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 2: Duplicate plan_ids (should deduplicate)
    print("\n2. Test: Duplicate plan_ids (deduplication)")
    if created_plan_ids:
        duplicate_cancels = {
            "plan_ids": [
                created_plan_ids[0],
                created_plan_ids[0],  # Duplicate
                created_plan_ids[0]   # Duplicate
            ]
        }
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/auto-execution/cancel-plans",
                json=duplicate_cancels,
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
                timeout=60
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Total: {data.get('total')}")
                print(f"   Successful: {data.get('successful')}")
                print(f"   Failed: {data.get('failed')}")
                print(f"   Results count: {len(data.get('results', []))}")
                print(f"   ✓ Deduplication should result in 1 result (not 3)")
        except requests.exceptions.ConnectionError:
            print("   ⚠ Connection error: API server may not be running")
        except Exception as e:
            print(f"   Exception: {e}")
    
    # Test 3: Idempotent behavior (cancel already cancelled)
    print("\n3. Test: Idempotent behavior (cancel already cancelled)")
    if created_plan_ids:
        idempotent_cancel = {
            "plan_ids": [created_plan_ids[0]]  # Already cancelled in test 1
        }
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/auto-execution/cancel-plans",
                json=idempotent_cancel,
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
                timeout=60
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Total: {data.get('total')}")
                print(f"   Successful: {data.get('successful')}")
                print(f"   Failed: {data.get('failed')}")
                print(f"   ✓ Should count as success (idempotent)")
        except requests.exceptions.ConnectionError:
            print("   ⚠ Connection error: API server may not be running")
        except Exception as e:
            print(f"   Exception: {e}")
    
    # Test 4: Empty plan_ids array (should fail Pydantic validation)
    print("\n4. Test: Empty plan_ids array (Pydantic validation)")
    empty_cancels = {
        "plan_ids": []
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/auto-execution/cancel-plans",
            json=empty_cancels,
            headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
            timeout=60
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 422:
            print(f"   ✓ Correctly rejected empty array (422)")
        else:
            print(f"   Response: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ⚠ Connection error: API server may not be running")
    except Exception as e:
        print(f"   Exception: {e}")

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("BATCH AUTO-EXECUTION ENDPOINTS TEST SUITE")
    print("="*80)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Testing Phase 1: Backend API Layer")
    
    try:
        test_batch_create_endpoint()
        test_batch_update_endpoint()
        test_batch_cancel_endpoint()
        
        print("\n" + "="*80)
        print("TEST SUITE COMPLETE")
        print("="*80)
        print("\nNote: Some tests may fail if:")
        print("  - API server is not running")
        print("  - Database is not accessible")
        print("  - Required services are not initialized")
        print("\nReview the output above for test results.")
        
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
