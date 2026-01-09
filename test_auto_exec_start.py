"""Test auto-execution system start"""
from auto_execution_system import get_auto_execution_system
import time

s = get_auto_execution_system()
print(f'Before start - Running: {s.running}')
print(f'Monitor thread: {s.monitor_thread}')
print(f'Watchdog thread: {s.watchdog_thread}')
print(f'Has watchdog method: {hasattr(s, "_start_watchdog_thread")}')

if not s.running:
    print('\nStarting system...')
    s.start()
    time.sleep(2)
    
print(f'\nAfter start - Running: {s.running}')
print(f'Monitor thread: {s.monitor_thread}')
print(f'Monitor thread alive: {s.monitor_thread.is_alive() if s.monitor_thread else None}')
print(f'Watchdog thread: {s.watchdog_thread}')
print(f'Watchdog thread alive: {s.watchdog_thread.is_alive() if s.watchdog_thread else None}')

