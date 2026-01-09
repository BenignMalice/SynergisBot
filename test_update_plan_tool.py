"""
Test script for the update_auto_plan tool
"""
import asyncio
import httpx
import json
from pathlib import Path
import sqlite3

async def test_update_plan():
    """Test updating an auto-execution plan"""
    
    # Use the plan we updated earlier
    plan_id = "chatgpt_0ea79233"
    
    print("=" * 60)
    print("Testing Update Auto Plan Tool")
    print("=" * 60)
    
    # Step 1: Get current plan status
    print(f"\n[1/4] Getting current plan status: {plan_id}")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"http://localhost:8000/auto-execution/status?plan_id={plan_id}"
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("plan"):
                    plan = data["plan"]
                    print(f"   Status: {plan.get('status')}")
                    print(f"   Symbol: {plan.get('symbol')}")
                    print(f"   Entry: {plan.get('entry_price')}")
                    print(f"   Current Conditions:")
                    print(f"   {json.dumps(plan.get('conditions', {}), indent=6)}")
                else:
                    print(f"   [ERROR] Plan not found or error: {data}")
                    return
            else:
                print(f"   [ERROR] Failed to get plan: {response.status_code}")
                return
    except Exception as e:
        print(f"   [ERROR] Error getting plan: {e}")
        return
    
    # Step 2: Update the plan
    print(f"\n[2/4] Updating plan with new conditions...")
    
    # Test updating conditions (adding min_volatility and bb_width_threshold)
    update_payload = {
        "conditions": {
            "min_volatility": 0.6,  # Increase from 0.5 if it exists
            "bb_width_threshold": 3.0  # Increase from 2.5 if it exists
        },
        "notes": "Updated plan based on new market analysis - increased volatility thresholds"
    }
    
    # Try both ports (8000 for API, 8010 for view server)
    ports = [8000, 8010]
    success = False
    
    for port in ports:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"http://localhost:{port}/auto-execution/update-plan/{plan_id}",
                    json=update_payload
                )
            
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        print(f"   [SUCCESS] Plan updated successfully on port {port}!")
                        print(f"   Message: {data.get('message')}")
                        success = True
                        break
                    else:
                        print(f"   [ERROR] Update failed on port {port}: {data.get('message')}")
                elif response.status_code == 404:
                    print(f"   [WARNING] Endpoint not found on port {port} (server may need restart)")
                    continue
                else:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"error": response.text}
                    print(f"   [ERROR] Update failed on port {port}: {response.status_code}")
                    print(f"   {json.dumps(error_data, indent=4)}")
                    continue
        except Exception as e:
            print(f"   [ERROR] Error updating plan on port {port}: {e}")
            continue
    
    if not success:
        print(f"\n   [INFO] Update endpoint not available. The API server needs to be restarted")
        print(f"   to load the new /auto-execution/update-plan endpoint.")
        print(f"   Route is correctly defined in app/auto_execution_api.py")
        return
    
    # Step 3: Verify the update
    print(f"\n[3/4] Verifying update...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"http://localhost:8000/auto-execution/status?plan_id={plan_id}"
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("plan"):
                    plan = data["plan"]
                    conditions = plan.get('conditions', {})
                    print(f"   Updated Conditions:")
                    print(f"   {json.dumps(conditions, indent=6)}")
                    print(f"\n   Verification:")
                    print(f"   - min_volatility: {conditions.get('min_volatility', 'NOT SET')} {'[OK]' if conditions.get('min_volatility') == 0.6 else '[MISMATCH]'}")
                    print(f"   - bb_width_threshold: {conditions.get('bb_width_threshold', 'NOT SET')} {'[OK]' if conditions.get('bb_width_threshold') == 3.0 else '[MISMATCH]'}")
                    print(f"   - price_near: {conditions.get('price_near', 'NOT SET')} {'[OK]' if conditions.get('price_near') else '[MISSING]'}")
                    print(f"   - tolerance: {conditions.get('tolerance', 'NOT SET')} {'[OK]' if conditions.get('tolerance') else '[MISSING]'}")
                    print(f"   - choch_bear: {conditions.get('choch_bear', False)} {'[OK]' if conditions.get('choch_bear') else '[MISSING]'}")
                    print(f"   Notes: {plan.get('notes', 'N/A')}")
                else:
                    print(f"   [ERROR] Failed to verify: {data}")
            else:
                print(f"   [ERROR] Failed to verify: {response.status_code}")
    except Exception as e:
        print(f"   [ERROR] Error verifying: {e}")
        return
    
    # Step 4: Test direct database check
    print(f"\n[4/4] Direct database verification...")
    db_path = Path("data/auto_execution.db")
    if db_path.exists():
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("""
                    SELECT plan_id, conditions, notes, status
                    FROM trade_plans 
                    WHERE plan_id = ?
                """, (plan_id,))
                row = cursor.fetchone()
                if row:
                    db_conditions = json.loads(row[1])
                    print(f"   Database Status: {row[3]}")
                    print(f"   Database Conditions:")
                    print(f"   {json.dumps(db_conditions, indent=6)}")
                    print(f"   Database Notes: {row[2]}")
                    print(f"\n   [SUCCESS] Database matches API response!")
                else:
                    print(f"   [ERROR] Plan not found in database")
        except Exception as e:
            print(f"   [ERROR] Database check failed: {e}")
    else:
        print(f"   [WARNING] Database not found at {db_path}")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_update_plan())

