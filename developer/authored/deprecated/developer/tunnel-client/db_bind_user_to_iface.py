#!/usr/bin/env python3
# db_bind_user_to_iface.py — bind ONE linux user to ONE interface in the DB (no schema writes)
# Usage: ./db_bind_user_to_iface.py <username> <iface>   # e.g. ./db_bind_user_to_iface.py Thomas-x6 x6

from __future__ import annotations
import sys, sqlite3, pwd
from pathlib import Path
from typing import Optional
import incommon as ic  # ROOT_DIR/DB_PATH, open_db()

def system_uid_or_none(username: str) -> Optional[int]:
  """Return the system UID for username, or None if the user doesn't exist locally."""
  try:
    return pwd.getpwnam(username).pw_uid
  except KeyError:
    return None

def bind_user_to_iface(conn: sqlite3.Connection, iface: str, username: str) -> str:
  """
  Given (iface, username):
    - Look up client.id by iface (table: client)
    - Upsert into User(iface_id, username, uid)
    - Update uid based on local /etc/passwd (None if user not found)
  Returns a concise status string.
  """
  row = conn.execute("SELECT id FROM Iface WHERE iface=? LIMIT 1;", (iface,)).fetchone()
  if not row:
    raise RuntimeError(f"Interface '{iface}' not found in client")

  iface_id = int(row[0])
  uid_val = system_uid_or_none(username)

  # Upsert binding
  conn.execute("""
    INSERT INTO User (iface_id, username, uid, created_at, updated_at)
    VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'), strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    ON CONFLICT(iface_id, username) DO UPDATE SET
      uid        = excluded.uid,
      updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now');
  """, (iface_id, username, uid_val))

  if uid_val is None:
    return f"bound {username} → {iface}  (uid=NULL; user not present on this system)"
  return f"bound {username} → {iface}  (uid={uid_val})"

def main(argv: list[str]) -> int:
  if len(argv) != 2:
    prog = Path(sys.argv[0]).name
    print(f"Usage: {prog} <username> <iface>", file=sys.stderr)
    return 2

  username, iface = argv
  try:
    with ic.open_db() as conn:
      msg = bind_user_to_iface(conn, iface, username)
      conn.commit()
  except FileNotFoundError as e:
    print(f"❌ {e}", file=sys.stderr); return 1
  except sqlite3.Error as e:
    print(f"❌ sqlite error: {e}", file=sys.stderr); return 1
  except RuntimeError as e:
    print(f"❌ {e}", file=sys.stderr); return 1

  print(f"✔ {msg}")
  return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
