#!/usr/bin/env python3
"""
Migrate pendings JSON: standardize keys from 'expires_ts' -> 'expiry_ts' and
(optionally) bump obviously-invalid expiry to now + default TTL.

Usage:
  python migrate_pendings_json.py C:\path\to\pendings.json [--ttl-min 60] [--dry-run]

- Makes a timestamped backup next to the original before writing changes.
- Idempotent: if keys are already 'expiry_ts', nothing else changes unless invalid.
"""
import sys, json, time, shutil, argparse
from pathlib import Path
from datetime import datetime

def migrate_json(path: Path, ttl_min: int, dry_run: bool = False):
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    raw = path.read_text(encoding='utf-8', errors='replace')
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse error in {path}: {e}")

    now = int(time.time())
    updated = False
    count_renamed = 0
    count_bumped = 0

    def fix_entry(entry: dict):
        nonlocal updated, count_renamed, count_bumped
        if not isinstance(entry, dict):
            return
        # Rename expires_ts -> expiry_ts
        if 'expires_ts' in entry and 'expiry_ts' not in entry:
            entry['expiry_ts'] = entry.pop('expires_ts')
            updated = True
            count_renamed += 1
        # Validate expiry_ts
        if 'expiry_ts' in entry:
            try:
                exp = int(float(entry['expiry_ts']))
            except Exception:
                exp = 0
            if exp <= now:
                # bump to now + ttl
                entry['expiry_ts'] = now + ttl_min * 60
                updated = True
                count_bumped += 1

    # Support either list of pendings or dict with nested lists
    if isinstance(data, list):
        for e in data:
            fix_entry(e)
    elif isinstance(data, dict):
        # Try common shapes: {"pendings":[...]} or per-symbol buckets
        if 'pendings' in data and isinstance(data['pendings'], list):
            for e in data['pendings']:
                fix_entry(e)
        else:
            for k, v in data.items():
                if isinstance(v, list):
                    for e in v:
                        fix_entry(e)
                elif isinstance(v, dict):
                    fix_entry(v)

    if not updated:
        return {"updated": False, "renamed": 0, "bumped": 0, "backup": None}

    if dry_run:
        return {"updated": True, "renamed": count_renamed, "bumped": count_bumped, "backup": None}

    # Backup
    backup = path.with_suffix(path.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, backup)

    # Write new content
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

    return {"updated": True, "renamed": count_renamed, "bumped": count_bumped, "backup": str(backup)}

def main():
    ap = argparse.ArgumentParser(description="Migrate pendings JSON to use expiry_ts and fix invalid expiries.")
    ap.add_argument("json_path", help="Path to pendings.json")
    ap.add_argument("--ttl-min", type=int, default=60, help="Default TTL minutes when bumping invalid expiry (default 60)")
    ap.add_argument("--dry-run", action="store_true", help="Don't write changes, just report what would change")
    args = ap.parse_args()

    res = migrate_json(Path(args.json_path), ttl_min=args.ttl_min, dry_run=args.dry_run)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
