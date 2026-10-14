#!/usr/bin/env python3
"""
ls_server.py — list server from the DB

Default output: server names, one per line.

Options:
  -i, --iface IFACE   Filter to a single client interface (e.g., x6, US)
  -l, --long          Show a table with client, name, endpoint, allowed_ips, priority
  -h, --help          Show usage
"""

from __future__ import annotations
import sys
import sqlite3
import argparse
from typing import List, Tuple
import incommon as ic  # DB_PATH, open_db()

def parse_args(argv: List[str]) -> argparse.Namespace:
  ap = argparse.ArgumentParser(add_help=False, prog="ls_server.py", description="List server from the DB")
  ap.add_argument("-i","--iface", help="Filter by client interface")
  ap.add_argument("-l","--long", action="store_true", help="Long table output")
  ap.add_argument("-h","--help", action="help", help="Show this help and exit")
  return ap.parse_args(argv)

def fmt_table(headers: List[str], rows: List[Tuple]) -> str:
  if not rows: return ""
  cols = list(zip(*([headers] + [[("" if c is None else str(c)) for c in r] for r in rows])))
  widths = [max(len(x) for x in col) for col in cols]
  line = lambda r: "  ".join(f"{str(c):<{w}}" for c, w in zip(r, widths))
  out = [line(headers), line(tuple("-"*w for w in widths))]
  for r in rows: out.append(line(r))
  return "\n".join(out)

def list_names(conn: sqlite3.Connection, iface: str | None) -> int:
  if iface:
    rows = conn.execute("""
      SELECT s.name
        FROM server s
        JOIN Iface c ON c.id = s.iface_id
       WHERE c.iface = ?
       ORDER BY s.name
    """, (iface,)).fetchall()
  else:
    rows = conn.execute("SELECT name FROM server ORDER BY name").fetchall()
  for (name,) in rows:
    print(name)
  return 0

def list_long(conn: sqlite3.Connection, iface: str | None) -> int:
  if iface:
    rows = conn.execute("""
      SELECT c.iface,
             s.name,
             s.endpoint_host || ':' || CAST(s.endpoint_port AS TEXT) AS endpoint,
             s.allowed_ips,
             s.priority
        FROM server s
        JOIN Iface c ON c.id = s.iface_id
       WHERE c.iface = ?
       ORDER BY c.iface, s.priority, s.name
    """, (iface,)).fetchall()
  else:
    rows = conn.execute("""
      SELECT c.iface,
             s.name,
             s.endpoint_host || ':' || CAST(s.endpoint_port AS TEXT) AS endpoint,
             s.allowed_ips,
             s.priority
        FROM server s
        JOIN Iface c ON c.id = s.iface_id
       ORDER BY c.iface, s.priority, s.name
    """).fetchall()

  hdr = ["client","name","endpoint","allowed_ips","priority"]
  txt = fmt_table(hdr, rows)
  if txt: print(txt)
  return 0

def main(argv: List[str]) -> int:
  args = parse_args(argv)
  try:
    with ic.open_db() as conn:
      return list_long(conn, args.iface) if args.long else list_names(conn, args.iface)
  except (sqlite3.Error, FileNotFoundError) as e:
    print(f"❌ {e}", file=sys.stderr)
    return 2

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
