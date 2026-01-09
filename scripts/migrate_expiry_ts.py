#!/usr/bin/env python3
"""
Light migration helper: standardize expires_ts -> expiry_ts in SQLite schemas
and add CHECK constraint to virtual_pending.expiry_ts (> now).

Usage:
  python migrate_expiry_ts.py /path/to/database.sqlite

This script is idempotent and will no-op if nothing needs changing.
It preserves table data by creating shadow tables and renaming them.
"""

import sys, sqlite3, time, re, os
from datetime import datetime

def table_info(conn, table):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return cur.fetchall()  # cid, name, type, notnull, dflt_value, pk

def get_schema(conn, table):
    cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
    row = cur.fetchone()
    return row[0] if row else None

def list_tables(conn):
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return [r[0] for r in cur.fetchall()]

def recreate_with_column_rename(conn, table, old_col, new_col):
    schema = get_schema(conn, table)
    if not schema or old_col not in schema:
        return False, f"{table}: no column {old_col} in schema"
    # Build new schema with column rename
    new_schema = schema.replace(f"{old_col} ", f"{new_col} ")
    tmp_table = f"{table}__tmp_{int(time.time())}"
    conn.execute(new_schema.replace(f"CREATE TABLE {table}", f"CREATE TABLE {tmp_table}"))
    cols = [c[1] for c in table_info(conn, table)]
    new_cols = [new_col if c==old_col else c for c in cols]
    src_cols_sql = ", ".join(cols)
    dst_cols_sql = ", ".join(new_cols)
    conn.execute(f"INSERT INTO {tmp_table} ({dst_cols_sql}) SELECT {src_cols_sql} FROM {table}")
    conn.execute(f"DROP TABLE {table}")
    conn.execute(f"ALTER TABLE {tmp_table} RENAME TO {table}")
    return True, f"{table}: renamed {old_col} -> {new_col}"

def ensure_virtual_pending_check(conn):
    schema = get_schema(conn, 'virtual_pending')
    if not schema:
        return False, "virtual_pending: not found (skipping)"
    if "expiry_ts INTEGER" not in schema:
        return False, "virtual_pending: no expiry_ts column"
    if "CHECK(expiry_ts > strftime('%s','now'))" in schema:
        return False, "virtual_pending: CHECK already present"
    # Recreate with CHECK
    tmp_table = f"virtual_pending__tmp_{int(time.time())}"
    new_schema = re.sub(r"(expiry_ts\s+INTEGER\s+NOT NULL)",
                        r"\1 CHECK(expiry_ts > strftime('%s','now'))",
                        schema)
    conn.execute(new_schema.replace("CREATE TABLE virtual_pending", f"CREATE TABLE {tmp_table}"))
    cols = [c[1] for c in table_info(conn, 'virtual_pending')]
    col_sql = ", ".join(cols)
    conn.execute(f"INSERT INTO {tmp_table} ({col_sql}) SELECT {col_sql} FROM virtual_pending")
    conn.execute("DROP TABLE virtual_pending")
    conn.execute(f"ALTER TABLE {tmp_table} RENAME TO virtual_pending")
    return True, "virtual_pending: added CHECK(expiry_ts > now)"

def main():
    if len(sys.argv) < 2:
        print("Usage: python migrate_expiry_ts.py /path/to/database.sqlite")
        sys.exit(2)
    db = sys.argv[1]
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")
        changes = []
        # 1) Rename any 'expires_ts' columns to 'expiry_ts' across all tables
        for t in list_tables(conn):
            info = table_info(conn, t)
            colnames = [c[1] for c in info]
            if 'expires_ts' in colnames and 'expiry_ts' not in colnames:
                ok, msg = recreate_with_column_rename(conn, t, 'expires_ts', 'expiry_ts')
                changes.append(msg)
        # 2) Ensure virtual_pending has CHECK
        ok, msg = ensure_virtual_pending_check(conn)
        changes.append(msg)
        conn.execute("COMMIT")
        print("Migration complete.")
        for m in changes:
            print(" -", m)
    except Exception as e:
        conn.execute("ROLLBACK")
        print("Migration failed:", e)
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
