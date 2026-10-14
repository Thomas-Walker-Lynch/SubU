#!/usr/bin/env python3
# ls_keys.py — list WireGuard public keys only
# Usage:
#   ./ls_keys.py            # all client/server
#   ./ls_keys.py -i x6      # only iface x6

from __future__ import annotations
import sys, argparse, sqlite3
from pathlib import Path
from typing import List, Tuple
import incommon as ic  # DB_PATH, open_db()

def format_table(headers: List[str], rows: List[Tuple]) -> str:
  if not rows:
    return "(none)"
  cols = list(zip(*([headers] + [[("" if c is None else str(c)) for c in r] for r in rows])))
  widths = [max(len(x) for x in col) for col in cols]
  def line(r): return "  ".join(f"{str(c):<{w}}" for c, w in zip(r, widths))
  out = [line(headers), line(tuple("-"*w for w in widths))]
  for r in rows: out.append(line(r))
  return "\n".join(out)

def list_client_keys(conn: sqlite3.Connection, iface: str | None, banner=False) -> str:
  if banner:
    print("\n=== Public keys generated locally by client, probably by using `key_client_generate.py`===")
  rows = conn.execute(
    "SELECT iface, public_key AS client_public_key "
    "FROM Iface "
    + ("WHERE iface=? " if iface else "")
    + "ORDER BY iface;",
    ((iface,) if iface else tuple()),
  ).fetchall()
  return format_table(["iface","client_public_key"], rows)

def list_server_keys(conn: sqlite3.Connection, iface: str | None ,banner=False) -> str:
  if banner:
    print("\n=== Public keys imported from remote server, probably edited into db_init_server_<name>.py ===")
  rows = conn.execute(
    "SELECT c.iface AS client, s.name AS server, s.public_key AS server_public_key "
    "FROM server s JOIN Iface c ON c.id = s.iface_id "
    + ("WHERE c.iface=? " if iface else "")
    + "ORDER BY c.iface, s.name;",
    ((iface,) if iface else tuple()),
  ).fetchall()
  return format_table(["client","server","server_public_key"], rows)

def client_pub_for_iface(conn: sqlite3.Connection, iface: str) -> str | None:
  r = conn.execute("SELECT public_key FROM Iface WHERE iface=? LIMIT 1;", (iface,)).fetchone()
  return (r[0] if r and r[0] else None)

def main(argv: List[str]) -> int:
  ap = argparse.ArgumentParser(description="List WireGuard public keys from the local DB.")
  ap.add_argument("-i","--iface", help="filter for one iface (e.g., x6)")
  args = ap.parse_args(argv)

  try:
    # Ensure DB exists
    if not ic.DB_PATH.exists():
      print(f"❌ DB not found: {ic.DB_PATH}", file=sys.stderr)
      return 1
    with ic.open_db() as conn:
      print(list_client_keys(conn, args.iface, banner=True))
      print()
      print(list_server_keys(conn, args.iface, banner=True))
      if args.iface:
        cpub = client_pub_for_iface(conn, args.iface)
        if cpub:
          print()
          print("# Copy to server peer config if needed:")
          print(f'CLIENT_PUB="{cpub}"')
    return 0
  except (sqlite3.Error, FileNotFoundError) as e:
    print(f"❌ {e}", file=sys.stderr)
    return 1

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
