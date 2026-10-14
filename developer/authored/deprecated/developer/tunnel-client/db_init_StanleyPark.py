#!/usr/bin/env python3
# db_init_StanleyPark.py — initialize the DB for the StanleyPark client

from __future__ import annotations
import sys, subprocess, sqlite3
from pathlib import Path
import incommon as ic

# Use existing business functions (no duplication)
from db_init_iface_x6 import init_iface_x6
from db_init_iface_US  import init_iface_US
from db_init_server_x6 import init_server_x6
from db_init_server_US  import init_server_US
from db_bind_user_to_iface import bind_user_to_iface
from db_init_ip_table_registration import assign_missing_rt_table_ids
from db_init_ip_iface_addr_assign import reconcile_kernel_and_db_ipv4_addresses
from db_init_route_defaults import seed_default_routes

ROOT = Path(__file__).resolve().parent
DB   = ic.DB_PATH

def msg_wrapped_call(title: str, fn=None, *args, **kwargs):
  """Print a before/after status line around calling `fn(*args, **kwargs)`.
  Returns the function’s return value."""
  print(f"→ {title}", flush=True)
  res = fn(*args, **kwargs) if fn else None
  print(f"✔ {title}" + (f": {res}" if res not in (None, "") else ""), flush=True)
  return res

def _run_local(script: str, *argv: str):
  subprocess.run([str(ROOT / script), *argv], check=True)

def db_init_StanleyPark() -> int:
  """
  Given the local SQLite DB at ic.DB_PATH, this:
    1) loads schema
    2) upserts ifaces (x6, US)
    3) upserts servers (x6, US)
    4) binds users (Thomas-x6→x6, Thomas-US→US)
    5) seeds per-iface default routes into Route
    6) assigns missing rt_table_id values from /etc/iproute2/rt_tables
    7) reconciles/assigns interface IPv4 addresses (kernel→DB, then pool)
    8) commits and prints status
  Returns 0 on success (raises on failure).
  """
  # 1) Schema
  msg_wrapped_call("db_schema_load.sh", _run_local, "db_schema_load.sh")

  # 2) DB work in one connection/commit
  with ic.open_db(DB) as conn:
    # ifaces + servers + user bindings
    msg_wrapped_call("db_init_iface_x6.py (init_iface_x6)", init_iface_x6, conn)
    msg_wrapped_call("db_init_server_x6.py (init_server_x6)", init_server_x6, conn)
    msg_wrapped_call("bind_user_to_iface: Thomas-x6 → x6", bind_user_to_iface, conn, "x6", "Thomas-x6")

    msg_wrapped_call("db_init_iface_US.py (init_iface_US)", init_iface_US, conn)
    msg_wrapped_call("db_init_server_US.py (init_server_US)", init_server_US, conn)
    msg_wrapped_call("bind_user_to_iface: Thomas-US → US", bind_user_to_iface, conn, "US", "Thomas-US")

    # 5) seed default routes for the selected ifaces (no duplicates; idempotent)
    msg_wrapped_call(
      "db_init_route_defaults (x6,US)",
      lambda: seed_default_routes(conn, iface_names=["x6","US"], overwrite=False)
    )

    # 6) assign rt_table_id from system tables (DB-only; no file writes)
    msg_wrapped_call(
      "db_init_ip_table_registration",
      lambda: assign_missing_rt_table_ids(conn, low=20000, high=29999, dry_run=False)
    )

    # 7) reconcile/assign interface IPv4 addresses (kernel → DB; pool for missing)
    msg_wrapped_call(
      "db_init_ip_iface_addr_assign",
      lambda: reconcile_kernel_and_db_ipv4_addresses(
        conn,
        pool_cidr="10.0.0.0/16",
        assign_prefix=32,
        reserve_first=0,
        dry_run=False
      )
    )

    # 8) commit
    conn.commit()
    print("✔ commit: database updated")

  return 0

def main(argv):
  if argv:
    print(f"Usage: {Path(sys.argv[0]).name}", file=sys.stderr)
    return 2
  try:
    return db_init_StanleyPark()
  except (subprocess.CalledProcessError, sqlite3.Error, FileNotFoundError) as e:
    print(f"❌ {e}", file=sys.stderr)
    return 1

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
