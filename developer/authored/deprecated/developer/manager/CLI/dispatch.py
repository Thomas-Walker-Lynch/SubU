# dispatch.py (additions)
# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-

import os, sys, sqlite3, subprocess
import env
from infrastructure.db import open_db
from domain.subu import ensure_chain, find_by_path, subu_username
from domain import device as device_domain

def device_scan(base_dir: str ="/mnt") -> int:
  try:
    conn = open_db()
  except Exception as e:
    print(f"subu: cannot open database at '{env.db_path()}': {e}", file =sys.stderr)
    return 1
  try:
    n = device_domain.scan_and_reconcile(conn, base_dir)
    print(f"scanned {n} device(s) under {base_dir}")
    return 0
  finally:
    conn.close()

def subu_capture(path: list[str], device_mapname: str|None =None) -> int:
  """
  path: ['masu','s0','s1', ...]
  device_mapname: optional mapname to associate (must already be visible under /mnt)
  """
  if not path or len(path) < 2:
    print("subu: capture requires <masu> <subu> [.<subu>]*", file =sys.stderr)
    return 2
  owner, parts = path[0], path[1:]
  try:
    conn = open_db()
  except Exception as e:
    print(f"subu: cannot open database at '{env.db_path()}': {e}", file =sys.stderr)
    return 1
  try:
    device_id = None
    if device_mapname:
      conn.row_factory = sqlite3.Row
      row = conn.execute("SELECT id FROM device WHERE mapname=?", (device_mapname,)).fetchone()
      if not row:
        print(f"subu: device '{device_mapname}' not known; run 'device scan' first", file =sys.stderr)
        return 2
      device_id = int(row["id"])
    leaf = ensure_chain(conn, owner, parts, device_id, True)
    conn.commit()
    print(leaf["full_unix_name"])
    return 0
  finally:
    conn.close()

def subu_list() -> int:
  """
  Print a flat list: id owner full_path full_unix_name device online
  """
  try:
    conn = open_db()
  except Exception as e:
    print(f"subu: cannot open database at '{env.db_path()}': {e}", file =sys.stderr)
    return 1
  try:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
      """SELECT n.id, n.owner, n.full_path, n.full_unix_name, n.is_online, d.mapname AS device
         FROM subu_node n
         LEFT JOIN device d ON d.id = n.device_id
         ORDER BY n.owner, n.full_path"""
    ).fetchall()
    if not rows:
      print("(no subu in database)")
      return 0
    for r in rows:
      dev = r["device"] or "local"
      on  = "1" if int(r["is_online"] or 0) else "0"
      print(f'{r["id"]}\t{r["owner"]}\t{r["full_path"]}\t{r["full_unix_name"]}\t{dev}\t{on}')
    return 0
  finally:
    conn.close()

def subu_option_incommon_set(spec_owner: str, spec_parts: list[str]) -> int:
  """
  Make a subu 'incommon': grant g+rx on its home dir and add all sibling subu users
  under the same owner into its group. Unix work is delegated to infrastructure.unix.
  """
  from infrastructure.unix import incommon_set_for_subu  # keep import local
  try:
    conn = open_db()
  except Exception as e:
    print(f"subu: cannot open database: {e}", file =sys.stderr)
    return 1
  try:
    # Ensure the node exists in DB (don’t change device)
    leaf = find_by_path(conn, spec_owner, spec_parts)
    if not leaf:
      print("subu: specified subu not found in DB; capture or make it first", file =sys.stderr)
      return 2
    incommon_set_for_subu(spec_owner, spec_parts)
    return 0
  finally:
    conn.close()

def subu_option_incommon_clear(spec_owner: str, spec_parts: list[str]) -> int:
  """
  Reverse of set: remove g+rx and drop sibling subu users from its group.
  """
  from infrastructure.unix import incommon_clear_for_subu
  try:
    conn = open_db()
  except Exception as e:
    print(f"subu: cannot open database: {e}", file =sys.stderr)
    return 1
  try:
    leaf = find_by_path(conn, spec_owner, spec_parts)
    if not leaf:
      print("subu: specified subu not found in DB; capture or make it first", file =sys.stderr)
      return 2
    incommon_clear_for_subu(spec_owner, spec_parts)
    return 0
  finally:
    conn.close()

def device_attach(mapname: str) -> int:
  """
  Call your existing shell to open+mount /mnt/<mapname>, then reconcile.
  (No mid-session home swapping here; policy enforcement to be added around callers.)
  """
  # You can parameterize paths via env.py if preferred.
  opener = "/root/mount/device_mapname__open_mount.sh"
  if not os.path.exists(opener):
    print(f"subu: cannot find opener script at {opener}", file =sys.stderr)
    return 1
  # We don’t guess /dev/sdX here; you pass it in your wrapper.
  # For now just ensure /mnt/<mapname> is mounted by your own workflow,
  # then call reconcile:
  try:
    conn = open_db()
  except Exception as e:
    print(f"subu: cannot open database: {e}", file =sys.stderr); return 1
  try:
    processed = device_domain.scan_and_reconcile(conn, "/mnt")
    print(f"scanned {processed} device(s) under /mnt")
    return 0
  finally:
    conn.close()

def device_detach(mapname: str) -> int:
  """
  Delegate to your logout/unmount scripts, then mark DB offline.
  """
  from infrastructure.unix import mark_device_offline
  try:
    conn = open_db()
  except Exception as e:
    print(f"subu: cannot open database: {e}", file =sys.stderr); return 1
  try:
    # Your script already unmounts and closes; afterwards, mark offline in DB:
    conn.execute("UPDATE device SET state='offline' WHERE mapname=?", (mapname,))
    conn.execute(
      "UPDATE subu_node SET is_online=0, updated_at=datetime('now') "
      "WHERE device_id=(SELECT id FROM device WHERE mapname=?)",
      (mapname,),
    )
    conn.commit()
    print(f"device '{mapname}' marked offline")
    return 0
  finally:
    conn.close()
