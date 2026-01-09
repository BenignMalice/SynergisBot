"""Quick test of update endpoint"""
import httpx
import asyncio
import json

async def test():
    plan_id = "chatgpt_0ea79233"
    
    # Test both ports
    for port in [8000, 8010]:
        print(f"\nTesting port {port}...")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Test status endpoint
                r = await client.get(f'http://localhost:{port}/auto-execution/status?plan_id={plan_id}')
                print(f"  Status endpoint: {r.status_code}")
                
                # Test update endpoint
                r2 = await client.post(
                    f'http://localhost:{port}/auto-execution/update-plan/{plan_id}',
                    json={'notes': 'Test update'}
                )
                print(f"  Update endpoint: {r2.status_code}")
                if r2.status_code != 200:
                    print(f"  Response: {r2.text[:200]}")
                else:
                    print(f"  Success: {json.dumps(r2.json(), indent=2)[:200]}")
        except Exception as e:
            print(f"  Error on port {port}: {e}")

if __name__ == "__main__":
    asyncio.run(test())

