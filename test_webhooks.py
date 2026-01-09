import os
import sys
sys.path.insert(0, '.')

# Load .env manually
env_path = '.env'
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

crypto = os.getenv('DISCORD_WEBHOOK_CRYPTO')
gold = os.getenv('DISCORD_WEBHOOK_GOLD')
forex = os.getenv('DISCORD_WEBHOOK_FOREX')

print('Webhook Status:')
print(f'  CRYPTO: {"OK" if crypto else "NOT SET"}')
print(f'  GOLD: {"OK" if gold else "NOT SET"}')
print(f'  FOREX: {"OK" if forex else "NOT SET"}')

# Test send to gold channel
if gold:
    import requests
    data = {
        "embeds": [{
            "title": "Test Alert",
            "description": "Channel routing test - Gold",
            "color": 0xFFD700
        }]
    }
    r = requests.post(gold, json=data, timeout=10)
    print(f'\nTest message to GOLD channel: {r.status_code}')

