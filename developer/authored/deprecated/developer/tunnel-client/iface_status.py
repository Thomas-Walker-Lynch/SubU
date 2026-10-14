#!/usr/bin/env python3
# iface_status.py — show unit/wg/route/uid-rule status for <iface>

from __future__ import annotations
import os, sys, shutil, sqlite3, subprocess, time
from pathlib import Path
import incommon as ic  # provides open_db()

# --- small shell helpers -----------------------------------------------------

def sh(args: list[str]) -> subprocess.CompletedProcess:
  """Run command; never raise; text mode; capture stdout/stderr."""
  return subprocess.run(args, text=True, capture_output=True)

def which(cmd: str) -> bool:
  return shutil.which(cmd) is not None

def print_block(title: str, body: str | None = None) -> None:
  print(f"=== {title} ===")
  if body is not None and body != "":
    print(body.rstrip())
  print()

# --- DB helpers ---------------------------------------------------------------

def get_rt_table_name(conn: sqlite3.Connection, iface: str) -> str:
  row = conn.execute(
    "SELECT rt_table_name_eff FROM v_client_effective WHERE iface=? LIMIT 1;",
    (iface,)
  ).fetchone()
  if not row:
    raise RuntimeError(f"Interface not found in DB: {iface}")
  return str(row[0])

def get_bound_users(conn: sqlite3.Connection, iface: str) -> list[tuple[str, int | None]]:
  rows = conn.execute(
    """SELECT ub.username, ub.uid
         FROM User ub
         JOIN Iface c ON c.id = ub.iface_id
        WHERE c.iface=?
        ORDER BY ub.username;""",
    (iface,)
  ).fetchall()
  return [(str(u), (None if v is None else int(v))) for (u, v) in rows]

# --- core --------------------------------------------------------------------

def iface_status(iface: str) -> int:
  # DB open + resolve table name early for helpful errors
  with ic.open_db() as conn:
    table = get_rt_table_name(conn, iface)

  # systemd status
  en = sh(["systemctl", "is-enabled", f"wg-quick@{iface}"])
  ac = sh(["systemctl", "is-active",  f"wg-quick@{iface}"])
  sys_body = "\n".join([
    (en.stdout.strip() if en.stdout.strip() else "").strip(),
    (ac.stdout.strip() if ac.stdout.strip() else "").strip(),
  ]).strip()
  print_block(f"systemd: wg-quick@{iface}", sys_body)

  # wg presence + handshake age
  wg_title = f"wg: {iface}"
  if which("wg"):
    if Path(f"/sys/class/net/{iface}").exists():
      lines: list[str] = ["(present)"]
      # Try sudo-less handshake read; if not permitted, show hint
      hs_try = sh(["sudo", "-n", "wg", "show", iface, "latest-handshakes"])
      if hs_try.returncode == 0 and hs_try.stdout.strip():
        # expected format: "<pubkey> <epoch>"
        epoch_part = hs_try.stdout.strip().split()[-1]
        try:
          hs = int(epoch_part)
          if hs > 0:
            age = int(time.time()) - hs
            lines.append(f"latest-handshake: {age}s ago")
          else:
            lines.append("latest-handshake: none")
        except ValueError:
          lines.append("latest-handshake: unknown")
      else:
        prog = Path(sys.argv[0]).name or "iface_status.py"
        lines.append(f"⚠ need sudo to read peers/handshake (try: sudo {prog} {iface})")
      print_block(wg_title, "\n".join(lines))
    else:
      print_block(wg_title, "(interface down or not present)")
  else:
    print_block(wg_title, "wg tool not found.")

  # route for table
  rt = sh(["ip", "-4", "route", "show", "table", table])
  print_block(f"route: table {table}", rt.stdout if rt.stdout else "")

  # uid rules targeting table
  rules = sh(["ip", "-4", "rule", "show"]).stdout.splitlines()
  hits = [ln for ln in rules if f"lookup {table}" in ln]
  print_block(f"uid rules → table {table}", "\n".join(hits) if hits else "(none)")

  # DB: bound users
  with ic.open_db() as conn:
    bound = get_bound_users(conn, iface)

  if not bound:
    print_block(f"DB: bound users for {iface}", "(none)")
  else:
    # simple column render
    header = ("username", "uid")
    rows = [(u, ("" if v is None else str(v))) for (u, v) in bound]
    w1 = max(len(header[0]), *(len(r[0]) for r in rows))
    w2 = max(len(header[1]), *(len(r[1]) for r in rows))
    body_lines = [f"{header[0]:<{w1}}  {header[1]:<{w2}}",
                  f"{'-'*w1}  {'-'*w2}"]
    body_lines += [f"{u:<{w1}}  {v:<{w2}}" for (u, v) in rows]
    print_block(f"DB: bound users for {iface}", "\n".join(body_lines))

  return 0

# --- cli ---------------------------------------------------------------------

def main(argv: list[str]) -> int:
  if len(argv) != 1:
    print(f"Usage: {Path(sys.argv[0]).name} <iface>", file=sys.stderr)
    return 2
  try:
    return iface_status(argv[0])
  except (sqlite3.Error, FileNotFoundError, RuntimeError) as e:
    print(f"❌ {e}", file=sys.stderr)
    return 1

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
