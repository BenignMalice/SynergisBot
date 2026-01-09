"""
Analyze computational requirements for enhanced MT5 streaming
"""

import psutil
import asyncio
from datetime import datetime, timezone
import json

def analyze_system_resources():
    """Analyze current system resources"""
    print('💻 SYSTEM RESOURCE ANALYSIS')
    print('=' * 60)
    
    # CPU Information
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    cpu_percent = psutil.cpu_percent(interval=1)
    
    print(f'🖥️ CPU Information:')
    print(f'   → Cores: {cpu_count} (Physical + Logical)')
    print(f'   → Frequency: {cpu_freq.current:.2f} MHz (Base: {cpu_freq.min:.2f} - Max: {cpu_freq.max:.2f})')
    print(f'   → Current Usage: {cpu_percent:.1f}%')
    
    # Memory Information
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    print(f'🧠 Memory Information:')
    print(f'   → Total RAM: {memory.total / (1024**3):.1f} GB')
    print(f'   → Available RAM: {memory.available / (1024**3):.1f} GB')
    print(f'   → Used RAM: {memory.used / (1024**3):.1f} GB ({memory.percent:.1f}%)')
    print(f'   → Swap Total: {swap.total / (1024**3):.1f} GB')
    print(f'   → Swap Used: {swap.used / (1024**3):.1f} GB ({swap.percent:.1f}%)')
    
    # Disk Information
    disk = psutil.disk_usage('/')
    
    print(f'💾 Disk Information:')
    print(f'   → Total Space: {disk.total / (1024**3):.1f} GB')
    print(f'   → Free Space: {disk.free / (1024**3):.1f} GB')
    print(f'   → Used Space: {disk.used / (1024**3):.1f} GB')
    
    return {
        'cpu_cores': cpu_count,
        'cpu_freq_mhz': cpu_freq.current,
        'cpu_usage_percent': cpu_percent,
        'ram_total_gb': memory.total / (1024**3),
        'ram_available_gb': memory.available / (1024**3),
        'ram_usage_percent': memory.percent,
        'disk_total_gb': disk.total / (1024**3),
        'disk_free_gb': disk.free / (1024**3),
        'disk_usage_percent': (disk.used / disk.total) * 100
    }

def calculate_data_requirements():
    """Calculate data requirements for enhanced streaming"""
    print('\n📊 DATA REQUIREMENTS CALCULATION')
    print('=' * 60)
    
    # Current system
    current_symbols = 29  # M1 streaming symbols
    current_timeframes = 1  # M1 only
    
    # Proposed enhanced system
    enhanced_symbols = 29  # Same symbols
    enhanced_timeframes = 6  # M1, M5, M15, M30, H1, H4
    
    # Data frequency estimates
    timeframe_frequencies = {
        'M1': 60,      # 60 updates per hour
        'M5': 12,      # 12 updates per hour  
        'M15': 4,      # 4 updates per hour
        'M30': 2,      # 2 updates per hour
        'H1': 1,       # 1 update per hour
        'H4': 0.25     # 0.25 updates per hour (every 4 hours)
    }
    
    # Data size estimates (bytes per update)
    data_size_per_update = 200  # bytes per candle/bar
    
    print(f'📈 Current System:')
    print(f'   → Symbols: {current_symbols}')
    print(f'   → Timeframes: {current_timeframes} (M1 only)')
    
    print(f'📈 Enhanced System:')
    print(f'   → Symbols: {enhanced_symbols}')
    print(f'   → Timeframes: {enhanced_timeframes} (M1, M5, M15, M30, H1, H4)')
    
    # Calculate data rates
    print(f'\n📊 Data Rate Calculations:')
    
    total_updates_per_hour = 0
    for timeframe, frequency in timeframe_frequencies.items():
        updates_per_hour = enhanced_symbols * frequency
        total_updates_per_hour += updates_per_hour
        data_per_hour = updates_per_hour * data_size_per_update
        print(f'   → {timeframe}: {updates_per_hour} updates/hour ({data_per_hour / 1024:.1f} KB/hour)')
    
    total_data_per_hour = total_updates_per_hour * data_size_per_update
    total_data_per_day = total_data_per_hour * 24
    total_data_per_month = total_data_per_day * 30
    
    print(f'\n📊 Total Data Requirements:')
    print(f'   → Updates per hour: {total_updates_per_hour:,}')
    print(f'   → Data per hour: {total_data_per_hour / 1024:.1f} KB')
    print(f'   → Data per day: {total_data_per_day / (1024**2):.1f} MB')
    print(f'   → Data per month: {total_data_per_month / (1024**3):.1f} GB')
    
    return {
        'updates_per_hour': total_updates_per_hour,
        'data_per_hour_kb': total_data_per_hour / 1024,
        'data_per_day_mb': total_data_per_day / (1024**2),
        'data_per_month_gb': total_data_per_month / (1024**3)
    }

def calculate_computational_load():
    """Calculate computational load requirements"""
    print('\n⚡ COMPUTATIONAL LOAD ANALYSIS')
    print('=' * 60)
    
    # Current system load
    current_components = [
        'Unified Tick Pipeline',
        'Binance WebSocket Feeds',
        'MT5 Bridge (Tick data)',
        'M1 Streaming (29 symbols)',
        'DTMS Enhancement',
        'Intelligent Exits',
        'ChatGPT Integration',
        'Risk & Performance Framework',
        'Database Integration',
        'Data Access Layer',
        'System Coordination',
        'Performance Optimization'
    ]
    
    print(f'🔧 Current System Components: {len(current_components)}')
    for component in current_components:
        print(f'   → {component}')
    
    # Enhanced system load
    enhanced_components = current_components + [
        'MT5 M5 Streaming',
        'MT5 M15 Streaming', 
        'MT5 M30 Streaming',
        'MT5 H1 Streaming',
        'MT5 H4 Streaming',
        'Enhanced Database Writing',
        'Multi-timeframe Analysis',
        'Enhanced Volatility Calculations',
        'Enhanced Structure Analysis'
    ]
    
    print(f'\n🚀 Enhanced System Components: {len(enhanced_components)}')
    for component in enhanced_components:
        print(f'   → {component}')
    
    # CPU load estimates
    print(f'\n💻 CPU Load Estimates:')
    print(f'   → Current System: ~15-25% CPU usage')
    print(f'   → Enhanced System: ~25-40% CPU usage')
    print(f'   → Additional Load: ~10-15% CPU usage')
    
    # Memory load estimates
    print(f'\n🧠 Memory Load Estimates:')
    print(f'   → Current System: ~500-800 MB RAM')
    print(f'   → Enhanced System: ~800-1200 MB RAM')
    print(f'   → Additional Load: ~300-400 MB RAM')
    
    # Database load estimates
    print(f'\n💾 Database Load Estimates:')
    print(f'   → Current Writes: ~100-200 writes/minute')
    print(f'   → Enhanced Writes: ~500-800 writes/minute')
    print(f'   → Additional Load: ~300-600 writes/minute')
    
    return {
        'current_cpu_percent': 20,
        'enhanced_cpu_percent': 35,
        'current_ram_mb': 650,
        'enhanced_ram_mb': 1000,
        'current_db_writes_per_min': 150,
        'enhanced_db_writes_per_min': 650
    }

def assess_feasibility(system_resources, data_requirements, computational_load):
    """Assess feasibility of enhanced system"""
    print('\n🎯 FEASIBILITY ASSESSMENT')
    print('=' * 60)
    
    # CPU Assessment
    cpu_available = 100 - system_resources['cpu_usage_percent']
    cpu_required = computational_load['enhanced_cpu_percent'] - computational_load['current_cpu_percent']
    
    print(f'💻 CPU Assessment:')
    print(f'   → Available CPU: {cpu_available:.1f}%')
    print(f'   → Required CPU: {cpu_required:.1f}%')
    print(f'   → Status: {"✅ SUFFICIENT" if cpu_available >= cpu_required else "❌ INSUFFICIENT"}')
    
    # Memory Assessment
    ram_available_gb = system_resources['ram_available_gb']
    ram_required_gb = (computational_load['enhanced_ram_mb'] - computational_load['current_ram_mb']) / 1024
    
    print(f'🧠 Memory Assessment:')
    print(f'   → Available RAM: {ram_available_gb:.1f} GB')
    print(f'   → Required RAM: {ram_required_gb:.1f} GB')
    print(f'   → Status: {"✅ SUFFICIENT" if ram_available_gb >= ram_required_gb else "❌ INSUFFICIENT"}')
    
    # Disk Assessment
    disk_available_gb = system_resources['disk_free_gb']
    disk_required_gb = data_requirements['data_per_month_gb'] * 3  # 3 months retention
    
    print(f'💾 Disk Assessment:')
    print(f'   → Available Disk: {disk_available_gb:.1f} GB')
    print(f'   → Required Disk: {disk_required_gb:.1f} GB (3 months)')
    print(f'   → Status: {"✅ SUFFICIENT" if disk_available_gb >= disk_required_gb else "❌ INSUFFICIENT"}')
    
    # Overall Assessment
    cpu_ok = cpu_available >= cpu_required
    ram_ok = ram_available_gb >= ram_required_gb
    disk_ok = disk_available_gb >= disk_required_gb
    
    print(f'\n🏁 OVERALL ASSESSMENT:')
    if cpu_ok and ram_ok and disk_ok:
        print('✅ FEASIBLE - System can handle enhanced streaming')
        print('')
        print('🚀 RECOMMENDED IMPLEMENTATION:')
        print('   → Implement M5, M15, M30, H1, H4 streaming')
        print('   → Enhance database writing capabilities')
        print('   → Add multi-timeframe analysis')
        print('   → Monitor system performance closely')
        return True
    else:
        print('⚠️ NEEDS OPTIMIZATION - System may struggle with enhanced load')
        print('')
        print('🔧 OPTIMIZATION RECOMMENDATIONS:')
        if not cpu_ok:
            print('   → CPU: Consider reducing update frequencies')
            print('   → CPU: Implement intelligent data sampling')
        if not ram_ok:
            print('   → RAM: Implement data compression')
            print('   → RAM: Use streaming data processing')
        if not disk_ok:
            print('   → Disk: Implement data archiving')
            print('   → Disk: Use compression for historical data')
        return False

def main():
    """Main analysis function"""
    print('🔍 COMPUTATIONAL CAPACITY ANALYSIS')
    print('Enhanced MT5 Streaming: M5, M15, M30, H1, H4 + Database Writing')
    print('=' * 80)
    
    # Analyze current system
    system_resources = analyze_system_resources()
    
    # Calculate data requirements
    data_requirements = calculate_data_requirements()
    
    # Calculate computational load
    computational_load = calculate_computational_load()
    
    # Assess feasibility
    feasible = assess_feasibility(system_resources, data_requirements, computational_load)
    
    print('\n📋 SUMMARY:')
    print('=' * 60)
    if feasible:
        print('✅ ENHANCED STREAMING IS FEASIBLE')
        print('Your system can handle the additional computational load')
        print('for M5, M15, M30, H1, H4 streaming with database writing.')
    else:
        print('⚠️ ENHANCED STREAMING NEEDS OPTIMIZATION')
        print('Consider the optimization recommendations above.')
    
    return feasible

if __name__ == "__main__":
    main()
