"""
Quick system health check for TelegramMoneyBot Phone Control
"""
import requests
import asyncio
import websockets
import sys
from colorama import init, Fore, Style

init(autoreset=True)

def check_command_hub():
    """Check if command hub is running"""
    try:
        response = requests.get("http://localhost:8001/health", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"{Fore.GREEN}✅ Command Hub: ONLINE")
            print(f"   Agent Status: {data.get('agent_status', 'unknown')}")
            print(f"   Pending Commands: {data.get('pending_commands', 0)}")
            return True
        else:
            print(f"{Fore.RED}❌ Command Hub: Responded with error {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"{Fore.RED}❌ Command Hub: OFFLINE")
        print(f"   Start with: python hub/command_hub.py")
        return False
    except Exception as e:
        print(f"{Fore.RED}❌ Command Hub: ERROR - {e}")
        return False

def check_mt5_connection():
    """Check if MT5 is connected"""
    try:
        from infra.mt5_service import MT5Service
        mt5 = MT5Service()
        if mt5.connect():
            info = mt5.mt5.account_info()
            print(f"{Fore.GREEN}✅ MT5: CONNECTED")
            if info:
                print(f"   Account: {info.login}")
                print(f"   Balance: ${info.balance:.2f}")
            mt5.disconnect()
            return True
        else:
            print(f"{Fore.RED}❌ MT5: NOT CONNECTED")
            print(f"   Make sure MT5 is running and logged in")
            return False
    except Exception as e:
        print(f"{Fore.RED}❌ MT5: ERROR - {e}")
        return False

def check_binance_service():
    """Check if Binance service would initialize"""
    try:
        from infra.binance_service import BinanceService
        print(f"{Fore.GREEN}✅ Binance Service: MODULE LOADED")
        print(f"   Will auto-start with desktop agent")
        return True
    except Exception as e:
        print(f"{Fore.RED}❌ Binance Service: ERROR - {e}")
        return False

def main():
    print("\n" + "="*70)
    print(f"{Fore.CYAN}{Style.BRIGHT}  TelegramMoneyBot Phone Control - System Health Check")
    print("="*70 + "\n")
    
    results = []
    
    print(f"{Fore.YELLOW}Checking Command Hub...")
    results.append(check_command_hub())
    print()
    
    print(f"{Fore.YELLOW}Checking MT5 Connection...")
    results.append(check_mt5_connection())
    print()
    
    print(f"{Fore.YELLOW}Checking Binance Service...")
    results.append(check_binance_service())
    print()
    
    print("="*70)
    if all(results):
        print(f"{Fore.GREEN}{Style.BRIGHT}✅ ALL SYSTEMS OPERATIONAL")
        print("\nYour phone control system is ready!")
        print("Start desktop agent with: python desktop_agent.py")
    else:
        print(f"{Fore.RED}{Style.BRIGHT}⚠️  SOME SYSTEMS NEED ATTENTION")
        print("\nReview the errors above and fix before proceeding.")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

