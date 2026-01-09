import requests

# Test if server is running updated code by checking for debug log
# The updated code should log "Price request for symbol: DXY"

print("Testing if server has updated code...")
print("Making request to http://localhost:8000/api/v1/price/DXY")
print("Check your server logs - you should see: 'Price request for symbol: DXY, uppercase: DXY'")
print()

try:
    response = requests.get('http://localhost:8000/api/v1/price/DXY')
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")

print()
print("Now check your server terminal logs.")
print()
print("IF YOU SEE: 'Price request for symbol: DXY, uppercase: DXY'")
print("  → Server has new code, there's a logic issue")
print()
print("IF YOU DON'T SEE that message:")
print("  → Server is still running old code!")
print("  → Solution: Kill the server process completely and restart")
print()
print("To kill all Python processes (Windows):")
print("  taskkill /F /IM python.exe")
print("Then restart:")
print("  python main_api.py")

