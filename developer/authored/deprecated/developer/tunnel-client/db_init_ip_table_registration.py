#!/usr/bin/env python3
"""
db_init_ip_table_registration.py

Business API:
  assign_missing_rt_table_ids(conn ,low=20000 ,high=29999 ,dry_run=False)
    -> (updated_count ,planned_map ,notes)

Policy:
- Effective table name per iface is COALESCE(rt_table_name ,iface).
- If that name exists in /etc/iproute2/rt_tables, reuse its number.
- Else allocate first free number in [low ,high].
- Writes DB only. Does NOT write rt_tables.
"""

from __future__ import annotations
import argparse
import sqlite3
from pathlib import Path
from typing import Dict ,Iterable ,List ,Optional ,Sequence ,Tuple

import incommon as ic  # for CLI path only

RT_TABLES_PATH = Path("/etc/iproute2/rt_tables")


def parse_rt_tables(path: Path) -> Tuple[List[str] ,Dict[str ,int] ,Dict[int ,str]]:
  text = path.read_text() if path.exists() else ""
  lines = text.splitlines()
  name_to_num: Dict[str ,int] = {}
  num_to_name: Dict[int ,str] = {}
  for ln in lines:
    s = ln.strip()
    if not s or s.startswith("#"):
      continue
    parts = s.split()
    if len(parts) >= 2 and parts[0].isdigit():
      n = int(parts[0]); name = parts[1]
      if name not in name_to_num and n not in num_to_name:
        name_to_num[name] = n
        num_to_name[n] = name
  return (lines ,name_to_num ,num_to_name)


def first_free_id(used: Iterable[int] ,low: int ,high: int) -> int:
  used_set = set(u for u in used if low <= u <= high)
  for n in range(low ,high+1):
    if n not in used_set:
      return n
  raise RuntimeError(f"no free routing-table IDs in [{low},{high}]")


def fetch_effective_ifaces(conn: sqlite3.Connection) -> List[Tuple[int ,str ,Optional[int]]]:
  sql = """
  SELECT i.id,
         COALESCE(i.rt_table_name, i.iface) AS eff_name,
         i.rt_table_id
  FROM Iface i
  ORDER BY i.id;
  """
  cur = conn.execute(sql)
  rows = cur.fetchall()
  return [
    (int(r[0]) ,str(r[1]) ,(int(r[2]) if r[2] is not None else None))
    for r in rows
  ]


def update_rt_ids(conn: sqlite3.Connection ,updates: Dict[int ,int]) -> int:
  if not updates:
    return 0
  with conn:
    for iface_id ,rt_id in updates.items():
      conn.execute("UPDATE Iface SET rt_table_id=? WHERE id=?" ,(rt_id ,iface_id))
  return len(updates)


def plan_rt_id_assignments(
  ifaces: Sequence[Tuple[int ,str ,Optional[int]]]
  ,name_to_num_sys: Dict[str ,int]
  ,existing_ids_in_db: Iterable[int]
  ,low: int
  ,high: int
) -> Dict[int ,int]:
  used_numbers = set(int(x) for x in existing_ids_in_db) | set(name_to_num_sys.values())
  planned: Dict[int ,int] = {}

  names_seen: Dict[str ,int] = {}
  for iface_id ,eff_name ,_ in ifaces:
    if eff_name in names_seen and names_seen[eff_name] != iface_id:
      raise RuntimeError(
        f"duplicate effective table name in DB: '{eff_name}' used by Iface.id {names_seen[eff_name]} and {iface_id}"
      )
    names_seen[eff_name] = iface_id

  for iface_id ,eff_name ,current_id in ifaces:
    if current_id is not None:
      used_numbers.add(int(current_id))
      continue
    if eff_name in name_to_num_sys:
      rt_id = int(name_to_num_sys[eff_name])
    else:
      rt_id = first_free_id(used_numbers ,low ,high)
    planned[iface_id] = rt_id
    used_numbers.add(rt_id)

  return planned


def assign_missing_rt_table_ids(
  conn: sqlite3.Connection
  ,low: int = 20000
  ,high: int = 29999
  ,dry_run: bool = False
) -> Tuple[int ,Dict[int ,int] ,List[str]]:
  _ ,name_to_num_sys ,_ = parse_rt_tables(RT_TABLES_PATH)
  notes: List[str] = []

  rows = fetch_effective_ifaces(conn)
  existing_ids = [r[2] for r in rows if r[2] is not None]
  planned = plan_rt_id_assignments(rows ,name_to_num_sys ,existing_ids ,low ,high)

  if not planned:
    return (0 ,{} ,["noop: all Iface.rt_table_id already set"])

  for iface_id ,eff_name ,current in rows:
    if iface_id in planned:
      notes.append(f"Iface.id={iface_id} name='{eff_name}' rt_table_id: {current} -> {planned[iface_id]}")

  if dry_run:
    return (0 ,planned ,notes)

  updated = update_rt_ids(conn ,planned)
  return (updated ,planned ,notes)


# --- thin CLI ---

def main(argv=None) -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--low" ,type=int ,default=20000)
  ap.add_argument("--high" ,type=int ,default=29999)
  ap.add_argument("--dry-run" ,action="store_true")
  args = ap.parse_args(argv)
  if args.low < 0 or args.high < args.low:
    print(f"error: invalid range [{args.low},{args.high}]")
    return 2
  with ic.open_db() as conn:
    updated ,_planned ,notes = assign_missing_rt_table_ids(conn ,low=args.low ,high=args.high ,dry_run=args.dry_run)
  if notes:
    print("\n".join(notes))
  if not args.dry_run:
    print(f"updated rows: {updated}")
  return 0


if __name__ == "__main__":
  import sys
  sys.exit(main())
