#!/usr/bin/env python3
"""
ls_client.py — list client from the DB

Default output: interface names, one per line.

Options:
  -i, --iface IFACE   Filter to a single interface (exact match)
  -l, --long          Show a table with iface, rt_table_name, rt_table_id, addr, autostart, updated_at
  -h, --help          Show usage
"""

from __future__ import annotations
import sys
import argparse
import sqlite3
from typing import List, Tuple
import incommon as ic  # DB_PATH, open_db()

def parse_args(argv: List[str]) -> argparse.Namespace:
  ap = argparse.ArgumentParser(add_help=False, prog="ls_client.py", description="List client from the DB")
  ap.add_argument("-i","--iface", help="Filter by interface (exact match)")
  ap.add_argument("-l","--long", action="store_true", help="Long table output")
  ap.add_argument("-h","--help", action="help", help="Show this help and exit")
  return ap.parse_args(argv)

def fmt_table(headers: List[str], rows: List[Tuple]) -> str:
  if not rows: return ""
  # normalize to strings; keep empty for None
  rows = [[("" if c is None else str(c)) for c in r] for r in rows]
  cols = list(zip(*([headers] + rows)))
  widths = [max(len(x) for x in col) for col in cols]
  line = lambda r: "  ".join(f"{str(c):<{w}}" for c, w in zip(r, widths))
  out = [line(headers), line(tuple("-"*w for w in widths))]
  out += [line(r) for r in rows]
  return "\n".join(out)

def list_names(conn: sqlite3.Connection, iface: str | None) -> int:
  if iface:
    rows = conn.execute("SELECT iface FROM Iface WHERE iface=? ORDER BY iface;", (iface,)).fetchall()
  else:
    rows = conn.execute("SELECT iface FROM Iface ORDER BY iface;").fetchall()
  for (name,) in rows:
    print(name)
  return 0

def list_long(conn: sqlite3.Connection, iface: str | None) -> int:
  if iface:
    rows = conn.execute("""
      SELECT c.iface,
             v.rt_table_name_eff AS rt_table_name,
             COALESCE(c.rt_table_id,'') AS rt_table_id,
             c.local_address_cidr,
             c.autostart,
             c.updated_at
        FROM Iface c
        JOIN v_client_effective v ON v.id = c.id
       WHERE c.iface = ?
       ORDER BY c.iface;
    """, (iface,)).fetchall()
  else:
    rows = conn.execute("""
      SELECT c.iface,
             v.rt_table_name_eff AS rt_table_name,
             COALESCE(c.rt_table_id,'') AS rt_table_id,
             c.local_address_cidr,
             c.autostart,
             c.updated_at
        FROM Iface c
        JOIN v_client_effective v ON v.id = c.id
       ORDER BY c.iface;
    """).fetchall()

  hdr = ["iface","rt_table_name","rt_table_id","addr","autostart","updated_at"]
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
