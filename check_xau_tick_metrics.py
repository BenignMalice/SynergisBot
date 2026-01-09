"""Check XAUUSDc tick metrics to verify ChatGPT's output"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import urllib.request
import json

def check_tick_metrics():
    print("=" * 80)
    print("CHECKING XAUUSDc TICK METRICS")
    print("=" * 80)
    
    # Get full analysis from API
    try:
        url = "http://localhost:8000/api/v1/analyse/XAUUSDc/full"
        with urllib.request.urlopen(url, timeout=30) as response:
            if response.status != 200:
                print(f"ERROR: API returned {response.status}")
                return
            result = json.loads(response.read().decode())
    except urllib.error.URLError as e:
        print(f"ERROR: Could not connect to API: {e}")
        print("Is the server running on port 8000?")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    # Handle different response formats
    if 'success' in result and not result.get('success'):
        print(f"ERROR: {result.get('error', 'Unknown error')}")
        return
    
    # Response might be direct data or wrapped
    if 'data' in result:
        data = result.get('data', {})
    else:
        data = result
    tick_metrics = data.get('tick_metrics')
    
    if not tick_metrics:
        print("ERROR: No tick_metrics in response")
        return
    
    print("\n[1] TICK METRICS STRUCTURE:")
    print("-" * 80)
    print(f"Metadata: {tick_metrics.get('metadata', {})}")
    
    # Check M5 metrics
    m5 = tick_metrics.get('M5', {})
    print(f"\n[2] M5 METRICS:")
    print("-" * 80)
    print(f"  Delta Volume: {m5.get('delta_volume', 'N/A')}")
    print(f"  CVD: {m5.get('cvd', 'N/A')}")
    print(f"  CVD Slope: {m5.get('cvd_slope', 'N/A')}")
    print(f"  Dominant Side: {m5.get('dominant_side', 'N/A')}")
    print(f"  Volatility Ratio: {m5.get('volatility_ratio', 'N/A')}")
    print(f"  Spread Mean: {m5.get('spread', {}).get('mean', 'N/A')}")
    print(f"  Absorption Count: {m5.get('absorption', {}).get('count', 'N/A')}")
    print(f"  Tick Rate: {m5.get('tick_rate', 'N/A')}")
    print(f"  Tick Count: {m5.get('tick_count', 'N/A')}")
    
    # Check M15 metrics
    m15 = tick_metrics.get('M15', {})
    print(f"\n[3] M15 METRICS:")
    print("-" * 80)
    print(f"  Delta Volume: {m15.get('delta_volume', 'N/A')}")
    print(f"  CVD: {m15.get('cvd', 'N/A')}")
    print(f"  CVD Slope: {m15.get('cvd_slope', 'N/A')}")
    print(f"  Dominant Side: {m15.get('dominant_side', 'N/A')}")
    print(f"  Volatility Ratio: {m15.get('volatility_ratio', 'N/A')}")
    print(f"  Spread Mean: {m15.get('spread', {}).get('mean', 'N/A')}")
    print(f"  Absorption Count: {m15.get('absorption', {}).get('count', 'N/A')}")
    print(f"  Tick Rate: {m15.get('tick_rate', 'N/A')}")
    print(f"  Tick Count: {m15.get('tick_count', 'N/A')}")
    
    # Check H1 metrics
    h1 = tick_metrics.get('H1', {})
    print(f"\n[4] H1 METRICS:")
    print("-" * 80)
    print(f"  Delta Volume: {h1.get('delta_volume', 'N/A')}")
    print(f"  CVD: {h1.get('cvd', 'N/A')}")
    print(f"  CVD Slope: {h1.get('cvd_slope', 'N/A')}")
    print(f"  Dominant Side: {h1.get('dominant_side', 'N/A')}")
    print(f"  Volatility Ratio: {h1.get('volatility_ratio', 'N/A')}")
    print(f"  Spread Mean: {h1.get('spread', {}).get('mean', 'N/A')}")
    print(f"  Absorption Count: {h1.get('absorption', {}).get('count', 'N/A')}")
    print(f"  Tick Rate: {h1.get('tick_rate', 'N/A')}")
    print(f"  Tick Count: {h1.get('tick_count', 'N/A')}")
    
    # Compare with ChatGPT's output
    print("\n" + "=" * 80)
    print("COMPARISON WITH CHATGPT OUTPUT:")
    print("=" * 80)
    
    chatgpt_data = {
        'M5': {'delta_vol': 0, 'cvd_trend': 'flat', 'dominant_side': 'Neutral', 'vol_ratio': 0.97, 'spread': 0.16, 'absorption': 0, 'tick_rate': 4.0},
        'M15': {'delta_vol': 0, 'cvd_trend': 'flat', 'dominant_side': 'Neutral', 'vol_ratio': 0.98, 'spread': 0.16, 'absorption': 0, 'tick_rate': 3.9},
        'H1': {'delta_vol': 0, 'cvd_trend': 'flat', 'dominant_side': 'Neutral', 'vol_ratio': 0.98, 'spread': 0.16, 'absorption': 0, 'tick_rate': 4.1}
    }
    
    for tf in ['M5', 'M15', 'H1']:
        print(f"\n{tf}:")
        actual = tick_metrics.get(tf, {})
        expected = chatgpt_data[tf]
        
        # Delta Volume
        actual_delta = actual.get('delta_volume', 0)
        match = "OK" if abs(actual_delta - expected['delta_vol']) < 0.01 else "DIFF"
        print(f"  Delta Vol: {actual_delta} (ChatGPT: {expected['delta_vol']}) [{match}]")
        
        # CVD Slope
        actual_slope = actual.get('cvd_slope', '')
        match = "OK" if actual_slope.lower() == expected['cvd_trend'].lower() else "DIFF"
        print(f"  CVD Slope: {actual_slope} (ChatGPT: {expected['cvd_trend']}) [{match}]")
        
        # Dominant Side
        actual_dominant = actual.get('dominant_side', '')
        match = "OK" if actual_dominant.upper() == expected['dominant_side'].upper() else "DIFF"
        print(f"  Dominant Side: {actual_dominant} (ChatGPT: {expected['dominant_side']}) [{match}]")
        
        # Volatility Ratio
        actual_vol_ratio = actual.get('volatility_ratio', 0)
        match = "OK" if abs(actual_vol_ratio - expected['vol_ratio']) < 0.02 else "DIFF"
        print(f"  Vol Ratio: {actual_vol_ratio:.2f} (ChatGPT: {expected['vol_ratio']}) [{match}]")
        
        # Spread
        actual_spread = actual.get('spread', {}).get('mean', 0)
        match = "OK" if abs(actual_spread - expected['spread']) < 0.01 else "DIFF"
        print(f"  Spread: {actual_spread:.2f} (ChatGPT: {expected['spread']}) [{match}]")
        
        # Absorption
        actual_absorption = actual.get('absorption', {}).get('count', 0)
        match = "OK" if actual_absorption == expected['absorption'] else "DIFF"
        print(f"  Absorption: {actual_absorption} (ChatGPT: {expected['absorption']}) [{match}]")
        
        # Tick Rate
        actual_tick_rate = actual.get('tick_rate', 0)
        match = "OK" if abs(actual_tick_rate - expected['tick_rate']) < 0.5 else "DIFF"
        print(f"  Tick Rate: {actual_tick_rate:.1f} (ChatGPT: {expected['tick_rate']}) [{match}]")

if __name__ == "__main__":
    check_tick_metrics()

