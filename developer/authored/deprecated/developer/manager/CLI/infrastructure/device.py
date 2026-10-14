# domain/device.py
# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-

"""
Device-aware reconciliation of subu state.

This module assumes:
  * Devices with user data are mounted as: /mnt/<mapname>
  * On each device, user data lives under: /mnt/<mapname>/user_data/<masu>
  * Subu home directories follow the pattern:

      /mnt/<mapname>/user_data/<masu>/subu_data/<subu0>/subu_data/<subu1>/...

    i.e., each subu directory may contain a 'subu_data' directory for children.

Given an open SQLite connection, scan_and_reconcile() will:

  * Discover all devices under a base directory (default: /mnt)
  * For each device that has 'user_data':
      - Upsert a row in the 'device' table.
      - Discover all subu paths for all masus on that device.
      - Upsert/refresh rows in 'subu' with device_id + is_online=1.
      - Mark any previously-known subu on that device that are not seen
        in the current scan as is_online=0.
"""

import os
from datetime import datetime
from pathlib import Path

from domain.subu import subu_username


def _utc_now() -> str:
  """
  Return a UTC timestamp string suitable for created_at/updated_at/last_seen.
  Example: '2025-11-11T05:30:12Z'
  """
  return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _walk_subu_paths(subu_root: Path):
  """
  Yield all subu paths under a root 'subu_data' directory.

  Layout assumption:

    subu_root/
      S0/
        ...files...
        subu_data/
          S1/
            ...
            subu_data/
              S2/
                ...

  For each logical path:
    ['S0']          (top-level)
    ['S0','S1']     (child)
    ['S0','S1','S2'] (grand-child)
    ...

  we yield the list of path components.
  """
  stack: list[tuple[Path, list[str]]] = [(subu_root, [])]

  while stack:
    current_root, prefix = stack.pop()
    try:
      entries = sorted(current_root.iterdir(), key =lambda p: p.name)
    except FileNotFoundError:
      continue

    for entry in entries:
      if not entry.is_dir():
        continue
      name = entry.name
      path_components = prefix + [name]
      yield path_components

      child_subu_data = entry / "subu_data"
      if child_subu_data.is_dir():
        stack.append((child_subu_data, path_components))


def _upsert_device(
  conn,
  mapname: str,
  mount_point: str,
  kind: str ="external",
) -> int:
  """
  Ensure a row exists for this device and return its id.

  We do NOT try to discover fs_uuid/luks_uuid here; those can be filled
  in later if desired.
  """
  now = _utc_now()

  cur = conn.execute(
    "SELECT id FROM device WHERE mapname = ?",
    (mapname,),
  )
  row = cur.fetchone()

  if row:
    device_id = row["id"]
    conn.execute(
      """
      UPDATE device
      SET mount_point = ?,
          kind        = ?,
          state       = 'online',
          last_seen   = ?
      WHERE id = ?
      """,
      (mount_point, kind, now, device_id),
    )
  else:
    cur = conn.execute(
      """
      INSERT INTO device (mapname, mount_point, kind, state, last_seen)
      VALUES (?, ?, ?, 'online', ?)
      """,
      (mapname, mount_point, kind, now),
    )
    device_id = cur.lastrowid

  return int(device_id)


def _ensure_subu_row(
  conn,
  device_id: int,
  owner: str,
  subu_path_components: list[str],
  full_path_str: str,
  now: str,
):
  """
  Upsert a row in 'subu' for (owner, subu_path_components) on device_id.

  full_path_str is the human-readable path, e.g. 'Thomas local' or
  'Thomas developer bolt'.
  """
  if not subu_path_components:
    return

  leaf_name = subu_path_components[-1]
  full_unix_name = subu_username(owner, subu_path_components)

  # For now, we simply reuse full_unix_name as netns_name.
  netns_name = full_unix_name

  # See if a row already exists for this owner + path.
  cur = conn.execute(
    "SELECT id FROM subu WHERE owner = ? AND path = ?",
    (owner, full_path_str),
  )
  row = cur.fetchone()

  if row:
    subu_id = row["id"]
    conn.execute(
      """
      UPDATE subu
      SET device_id = ?,
          is_online = 1,
          updated_at = ?
      WHERE id = ?
      """,
      (device_id, now, subu_id),
    )
    return

  # Insert new row
  conn.execute(
    """
    INSERT INTO subu (
      owner,
      name,
      full_unix_name,
      path,
      netns_name,
      wg_id,
      device_id,
      is_online,
      created_at,
      updated_at
    )
    VALUES (?, ?, ?, ?, ?, NULL, ?, 1, ?, ?)
    """,
    (
      owner,
      leaf_name,
      full_unix_name,
      full_path_str,
      netns_name,
      device_id,
      now,
      now,
    ),
  )


def _reconcile_device_for_mount(conn, device_id: int, user_data_dir: Path):
  """
  Reconcile all subu on a particular device.

  user_data_dir is a path like:

    /mnt/Eagle/user_data

  Under which we expect:

    /mnt/Eagle/user_data/<masu>/subu_data/...
  """
  now = _utc_now()
  discovered: set[tuple[str, str]] = set()

  try:
    owners = sorted(user_data_dir.iterdir(), key =lambda p: p.name)
  except FileNotFoundError:
    return

  for owner_entry in owners:
    if not owner_entry.is_dir():
      continue

    owner = owner_entry.name
    subu_root = owner_entry / "subu_data"
    if not subu_root.is_dir():
      # masu with no subu_data; skip
      continue

    for subu_components in _walk_subu_paths(subu_root):
      # Full logical path is: [owner] + subu_components
      path_tokens = [owner] + subu_components
      path_str = " ".join(path_tokens)
      discovered.add((owner, path_str))

      _ensure_subu_row(
        conn =conn,
        device_id =device_id,
        owner =owner,
        subu_path_components =subu_components,
        full_path_str =path_str,
        now =now,
      )

  # Mark any existing subu on this device that we did NOT see as offline.
  cur = conn.execute(
    "SELECT id, owner, path FROM subu WHERE device_id = ?",
    (device_id,),
  )
  existing = cur.fetchall()
  for row in existing:
    key = (row["owner"], row["path"])
    if key in discovered:
      continue
    conn.execute(
      """
      UPDATE subu
      SET is_online = 0,
          updated_at = ?
      WHERE id = ?
      """,
      (now, row["id"]),
    )


def scan_and_reconcile(conn, base_dir: str ="/mnt") -> int:
  """
  Scan all mounted devices under base_dir for 'user_data' trees and
  reconcile them into the database.

  For each directory 'base_dir/<mapname>':

    * If it contains 'user_data', it is treated as a device.
    * A 'device' row is upserted (mapname = basename).
    * All subu under the corresponding user_data tree are reconciled.

  Returns:
    Number of devices that were processed.
  """
  root = Path(base_dir)
  if not root.is_dir():
    return 0

  processed = 0

  for entry in sorted(root.iterdir(), key =lambda p: p.name):
    if not entry.is_dir():
      continue

    mapname = entry.name
    user_data_dir = entry / "user_data"
    if not user_data_dir.is_dir():
      continue

    mount_point = str(entry)
    device_id = _upsert_device(conn, mapname, mount_point)
    _reconcile_device_for_mount(conn, device_id, user_data_dir)
    processed += 1

  conn.commit()
  return processed
