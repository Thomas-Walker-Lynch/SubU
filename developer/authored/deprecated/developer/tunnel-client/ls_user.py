#!/usr/bin/env python3
"""
ls_users.py — print "<username> <iface>" from DB (names only)

- Validates required tables exist (client, User)
- No side effects; read-only
"""

from __future__ import annotations
import sys
import sqlite3
import incommon as ic  # DB_PATH, open_db()

HELP = """Usage: ls_users.py
Prints one line per user binding as: "<username> <iface>".
"""

def tables_ok(conn: sqlite3.Connection) -> bool:
  row = conn.execute(
    """
    SELECT
      (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='client'),
      (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='User')
    """
  ).fetchone()
  return row == (1, 1)

def list_users(conn: sqlite3.Connection) -> None:
  cur = conn.execute(
    """
    SELECT ub.username, c.iface
      FROM User ub
      JOIN Iface c ON c.id = ub.iface_id
     ORDER BY c.iface, ub.username
    """
  )
  for username, iface in cur.fetchall():
    print(f"{username} {iface}")

def main(argv: list[str]) -> int:
  if argv and argv[0] in ("-h", "--help"):
    print(HELP.strip()); return 0
  try:
    with ic.open_db() as conn:
      if not tables_ok(conn):
        print("❌ Missing tables (client/User). Initialize the database first.", file=sys.stderr)
        return 1
      list_users(conn)
      return 0
  except (sqlite3.Error, FileNotFoundError) as e:
    print(f"❌ {e}", file=sys.stderr)
    return 2

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
