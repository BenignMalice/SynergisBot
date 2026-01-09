"""
Quick test to verify the API server can import and initialize correctly.
Run this before starting the full server to catch any import/configuration errors.
"""

import sys
import os
from pathlib import Path

# Fix Unicode encoding on Windows
if os.name == 'nt':
    sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

print("Testing API server imports...")

try:
    from app.main_api import app, mt5_service, journal_repo
    print("[OK] API server imports successful")
except Exception as e:
    print(f"[ERROR] Import failed: {e}")
    sys.exit(1)

try:
    from infra.mt5_service import MT5Service
    print("[OK] MT5Service import successful")
except Exception as e:
    print(f"[ERROR] MT5Service import failed: {e}")
    sys.exit(1)

try:
    from infra.journal_repo import JournalRepo
    print("[OK] JournalRepo import successful")
except Exception as e:
    print(f"[ERROR] JournalRepo import failed: {e}")
    sys.exit(1)

try:
    from config import settings
    print("[OK] Settings import successful")
    print(f"   - MT5_FILES_DIR: {settings.MT5_FILES_DIR}")
except Exception as e:
    print(f"[ERROR] Settings import failed: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("[SUCCESS] All imports successful!")
print("="*60)
print("\nYou can now start the API server with:")
print("  python -m uvicorn app.main_api:app --reload --host 0.0.0.0 --port 8000")
print("\nOr use the startup script:")
print("  start_with_ngrok.bat")
print("\nAPI Documentation will be available at:")
print("  http://localhost:8000/docs")
print("="*60)

