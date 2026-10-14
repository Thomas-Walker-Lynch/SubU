#!/usr/bin/env python3
# key_server_set.py — set a server's public key by nickname
# Usage: ./key_server_set.py <server_name> <public_key>

from __future__ import annotations
import sys, sqlite3
from pathlib import Path
import incommon as ic  # DB_PATH, open_db()

def valid_pub(pub: str) -> bool:
  # wg public keys are base64-like and typically 44 chars; allow 43–45 as used elsewhere
  return isinstance(pub, str) and (43 <= len(pub.strip()) <= 45)

def set_server_pubkey(server_name: str, pubkey: str) -> int:
  if not ic.DB_PATH.exists():
    raise FileNotFoundError(f"DB not found: {ic.DB_PATH}")
  with ic.open_db() as conn:
    cur = conn.execute(
      "UPDATE server "
      "   SET public_key=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') "
      " WHERE name=?;",
      (pubkey.strip(), server_name)
    )
    conn.commit()
    return cur.rowcount or 0

def main(argv: list[str]) -> int:
  if len(argv) != 2:
    print(f"Usage: {Path(sys.argv[0]).name} <server_name> <public_key>", file=sys.stderr)
    return 2
  name, pub = argv
  if not valid_pub(pub):
    print(f"❌ public_key length looks wrong ({len(pub)})", file=sys.stderr)
    return 1
  try:
    n = set_server_pubkey(name, pub)
    if n == 0:
      print(f"⚠️  no matching server rows for name='{name}'")
    else:
      print(f"updated server.public_key for {n} row(s) where name='{name}'")
    return 0
  except (sqlite3.Error, FileNotFoundError) as e:
    print(f"❌ {e}", file=sys.stderr)
    return 1

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
