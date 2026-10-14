#!/usr/bin/env python3
# iface_down.py — stop wg-quick@<iface> and remove uid→rt rules

from __future__ import annotations
import os, sys, sqlite3, subprocess
import incommon as ic  # provides open_db()

def sh(args: list[str], check: bool=False) -> subprocess.CompletedProcess:
  return subprocess.run(args, text=True, capture_output=True, check=check)

def get_rt_table_name(conn: sqlite3.Connection, iface: str) -> str:
  row = conn.execute(
    "SELECT rt_table_name_eff FROM v_client_effective WHERE iface=? LIMIT 1;",
    (iface,)
  ).fetchone()
  if not row:
    raise RuntimeError(f"Interface not found in DB: {iface}")
  return str(row[0])

def get_bound_uids(conn: sqlite3.Connection, iface: str) -> list[int]:
  rows = conn.execute(
    """SELECT ub.uid
         FROM User ub
         JOIN Iface c ON c.id = ub.iface_id
        WHERE c.iface=? AND ub.uid IS NOT NULL
        ORDER BY ub.uid;""",
    (iface,)
  ).fetchall()
  return [int(r[0]) for r in rows]

def iface_down(iface: str) -> str:
  if os.geteuid() != 0:
    raise PermissionError("This script must be run as root.")

  # Stop interface (ignore failure)
  sh(["systemctl", "stop", f"wg-quick@{iface}"])

  # DB lookups
  with ic.open_db() as conn:
    table = get_rt_table_name(conn, iface)
    uids  = get_bound_uids(conn, iface)

  # Snapshot rules once for existence checks
  rules = sh(["ip", "-4", "rule", "list"]).stdout

  removed = 0
  for uid in uids:
    needle = f"uidrange {uid}-{uid} "
    if needle in rules and f" lookup {table}" in rules:
      # Try to delete; ignore failure to keep idempotence
      sh(["ip", "-4", "rule", "del", "uidrange", f"{uid}-{uid}", "table", table])
      sh(["logger", f"iface_down: removed uid {uid} rule for table {table}"])
      removed += 1

  return f"✅ {iface} stopped; removed {removed} uid rules from table {table}."

def main(argv: list[str]) -> int:
  if len(argv) != 1:
    print(f"Usage: {os.path.basename(sys.argv[0])} <iface>", file=sys.stderr)
    return 2
  iface = argv[0]
  try:
    msg = iface_down(iface)
  except (PermissionError, FileNotFoundError, sqlite3.Error, RuntimeError) as e:
    print(f"❌ {e}", file=sys.stderr); return 1
  print(msg); return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
