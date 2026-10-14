# domain/device.py
# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-

import os, sqlite3
from datetime import datetime
from pathlib import Path

from domain.subu import ensure_chain

def _utc_now() -> str:
  return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def _walk_subu_paths(subu_root: Path):
  """
  Yield subu component lists by descending the nested subu_data tree.
  e.g. ['developer'], ['developer','bolt'], ...
  """
  stack: list[tuple[Path, list[str]]] = [(subu_root, [])]
  while stack:
    base, prefix = stack.pop()
    try:
      entries = sorted(p for p in base.iterdir() if p.is_dir())
    except FileNotFoundError:
      continue
    for d in entries:
      name = d.name
      path = prefix + [name]
      yield path
      nxt = d / "subu_data"
      if nxt.is_dir():
        stack.append((nxt, path))

def _upsert_device(conn, mapname: str, mount_point: str, kind: str ="external") -> int:
  now = _utc_now()
  conn.row_factory = sqlite3.Row
  row = conn.execute("SELECT id FROM device WHERE mapname=?", (mapname,)).fetchone()
  if row:
    dev_id = row["id"]
    conn.execute(
      "UPDATE device SET mount_point=?, kind=?, state='online', last_seen=? WHERE id=?",
      (mount_point, kind, now, dev_id),
    )
    return int(dev_id)
  cur = conn.execute(
    "INSERT INTO device(mapname,mount_point,kind,state,last_seen) VALUES(?,?,?,'online',?)",
    (mapname, mount_point, kind, now),
  )
  return int(cur.lastrowid)

def _mark_missing_offline(conn, device_id: int, seen_keys: set[tuple[str,int]]):
  """
  Mark rows in subu_node for this device as offline if leaf id not seen.
  We compare by (owner_id, node_id) but since we don’t store owner ids,
  we key by (owner, id) indirectly via a select.
  """
  conn.row_factory = sqlite3.Row
  now = _utc_now()
  cur = conn.execute("SELECT id FROM subu_node WHERE device_id=?", (device_id,))
  for r in cur.fetchall():
    node_id = r["id"]
    # Seen set uses node ids only (device scoping suffices)
    if (device_id, node_id) in seen_keys:
      continue
    conn.execute(
      "UPDATE subu_node SET is_online=0, updated_at=? WHERE id=?",
      (now, node_id),
    )

def reconcile_device(conn, mapname: str, mount_point: str) -> int:
  """
  Reconcile a single already-mounted device (/mnt/<mapname>).
  Returns number of subu nodes (leaf count) discovered/refreshed.
  """
  user_data = Path(mount_point) / "user_data"
  if not user_data.is_dir():
    return 0

  device_id = _upsert_device(conn, mapname, mount_point)
  conn.row_factory = sqlite3.Row
  now = _utc_now()
  refreshed = 0
  seen: set[tuple[int,int]] = set()  # (device_id, node_id)

  for masu_dir in sorted(p for p in user_data.iterdir() if p.is_dir()):
    owner = masu_dir.name
    subu_root = masu_dir / "subu_data"
    if not subu_root.is_dir():
      continue
    for parts in _walk_subu_paths(subu_root):
      # Ensure the chain exists and is marked online on this device
      leaf = ensure_chain(conn, owner, parts, device_id, True)
      seen.add((device_id, int(leaf["id"])))
      refreshed += 1

  _mark_missing_offline(conn, device_id, seen)
  conn.commit()
  return refreshed

def scan_and_reconcile(conn, base_dir: str ="/mnt") -> int:
  """
  Scan /mnt/* for mapnames that contain a top-level user_data/ and reconcile each.
  Returns the number of devices processed.
  """
  root = Path(base_dir)
  if not root.is_dir():
    return 0
  processed = 0
  for mp in sorted(p for p in root.iterdir() if p.is_dir()):
    if not (mp / "user_data").is_dir():
      continue
    refreshed = reconcile_device(conn, mp.name, str(mp))
    # Count device even if zero subu (e.g. only user_data/ present)
    processed += 1
  return processed
