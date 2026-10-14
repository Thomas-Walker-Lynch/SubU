#!/usr/bin/env python3
"""
db_init_ip_iface_addr_assign.py

Business API:
  reconcile_kernel_and_db_ipv4_addresses(conn ,pool_cidr="10.0.0.0/16" ,assign_prefix=32 ,reserve_first=0 ,dry_run=False)
    -> (updated_count ,notes)
"""

from __future__ import annotations
import argparse
import ipaddress
import json
import sqlite3
import subprocess
from typing import Dict ,Iterable ,List ,Optional ,Sequence ,Tuple

import incommon as ic


def fetch_ifaces(conn: sqlite3.Connection) -> List[Tuple[int ,str ,Optional[str]]]:
  sql = """
  SELECT id,
         iface,
         NULLIF(TRIM(local_address_cidr),'') AS local_address_cidr
  FROM Iface
  ORDER BY id;
  """
  cur = conn.execute(sql)
  rows = cur.fetchall()
  return [
    (int(r[0]) ,str(r[1]) ,(str(r[2]) if r[2] is not None else None))
    for r in rows
  ]


def update_iface_addresses(conn: sqlite3.Connection ,updates: Dict[int ,str]) -> int:
  if not updates:
    return 0
  with conn:
    for iface_id ,cidr in updates.items():
      conn.execute("UPDATE Iface SET local_address_cidr=? WHERE id=?" ,(cidr ,iface_id))
  return len(updates)


def kernel_ipv4_cidr_for(iface: str) -> Optional[str]:
  try:
    cp = subprocess.run(
      ["ip","-j","addr","show","dev",iface]
      ,check=False
      ,capture_output=True
      ,text=True
    )
  except Exception:
    return None
  if cp.returncode != 0 or not cp.stdout.strip():
    return None
  try:
    data = json.loads(cp.stdout)
  except json.JSONDecodeError:
    return None
  if not isinstance(data ,list) or not data:
    return None
  addr_info = data[0].get("addr_info") or []
  for a in addr_info:
    if a.get("family") == "inet" and a.get("scope") == "global":
      local = a.get("local"); plen = a.get("prefixlen")
      if local and isinstance(plen ,int):
        return f"{local}/{plen}"
  for a in addr_info:
    if a.get("family") == "inet":
      local = a.get("local"); plen = a.get("prefixlen")
      if local and isinstance(plen ,int):
        return f"{local}/{plen}"
  return None


def kernel_ipv4_map(ifaces: Sequence[str]) -> Dict[str ,Optional[str]]:
  return {name: kernel_ipv4_cidr_for(name) for name in ifaces}


def _host_ip_from_cidr(cidr: str):
  try:
    ipi = ipaddress.ip_interface(cidr)
  except ValueError:
    return None
  if isinstance(ipi.ip ,ipaddress.IPv4Address):
    return ipaddress.IPv4Address(int(ipi.ip))
  return None


def _collect_used_hosts_from(cidrs: Iterable[str] ,pool: ipaddress.IPv4Network) -> List[ipaddress.IPv4Address]:
  used: List[ipaddress.IPv4Address] = []
  for c in cidrs:
    hip = _host_ip_from_cidr(c)
    if hip is not None and hip in pool:
      used.append(hip)
  return used


def _first_free_hosts(
  count: int
  ,used_hosts: Iterable[ipaddress.IPv4Address]
  ,pool: ipaddress.IPv4Network
  ,reserve_first: int = 0
) -> List[ipaddress.IPv4Address]:
  used_set = {int(h) for h in used_hosts}
  result: List[ipaddress.IPv4Address] = []
  start = int(pool.network_address) + 1 + max(0 ,reserve_first)
  end = int(pool.broadcast_address) - 1
  for val in range(start ,end+1):
    if val not in used_set:
      result.append(ipaddress.IPv4Address(val))
      if len(result) >= count:
        break
  if len(result) < count:
    raise RuntimeError(f"address pool exhausted in {pool} (needed {count} more)")
  return result


def plan_address_updates(
  rows: Sequence[Tuple[int ,str ,Optional[str]]]
  ,pool_cidr: str
  ,assign_prefix: int
  ,reserve_first: int
  ,kmap: Dict[str ,Optional[str]]
) -> Tuple[Dict[int ,str] ,List[str]]:
  notes: List[str] = []
  pool = ipaddress.IPv4Network(pool_cidr ,strict=False)
  if pool.version != 4:
    raise ValueError("only IPv4 pools supported")

  kernel_present = [c for c in kmap.values() if c]
  db_present = [c for (_i ,_n ,c) in rows if c]
  used_hosts = (
    _collect_used_hosts_from(kernel_present ,pool)
    + _collect_used_hosts_from(db_present ,pool)
  )

  alloc_targets: List[Tuple[int ,str]] = []
  updates: Dict[int ,str] = {}

  for iface_id ,iface_name ,db_cidr in rows:
    k_cidr = kmap.get(iface_name)

    if k_cidr:
      if db_cidr != k_cidr:
        updates[iface_id] = k_cidr
        if db_cidr:
          notes.append(f"sync: iface '{iface_name}' DB {db_cidr} -> kernel {k_cidr}")
        else:
          notes.append(f"sync: iface '{iface_name}' set from kernel {k_cidr}")
      continue

    if db_cidr:
      notes.append(f"note: iface '{iface_name}' has DB {db_cidr} but no kernel IPv4")
      continue

    alloc_targets.append((iface_id ,iface_name))

  if alloc_targets:
    free = _first_free_hosts(len(alloc_targets) ,used_hosts ,pool ,reserve_first=reserve_first)
    for idx ,(iface_id ,iface_name) in enumerate(alloc_targets):
      cidr = f"{free[idx]}/{assign_prefix}"
      updates[iface_id] = cidr
      notes.append(f"assign: iface '{iface_name}' -> {cidr} (from pool {pool_cidr})")

  return (updates ,notes)


def reconcile_kernel_and_db_ipv4_addresses(
  conn: sqlite3.Connection
  ,pool_cidr: str = "10.0.0.0/16"
  ,assign_prefix: int = 32
  ,reserve_first: int = 0
  ,dry_run: bool = False
) -> Tuple[int ,List[str]]:
  rows = fetch_ifaces(conn)
  iface_names = [n for (_i ,n ,_c) in rows]
  kmap = kernel_ipv4_map(iface_names)

  updates ,notes = plan_address_updates(
    rows
    ,pool_cidr
    ,assign_prefix
    ,reserve_first
    ,kmap
  )
  if not updates:
    return (0 ,notes or ["noop: nothing to change"])
  if dry_run:
    return (0 ,notes)

  updated = update_iface_addresses(conn ,updates)
  return (updated ,notes)


# --- thin CLI ---

def main(argv=None) -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--pool" ,type=str ,default="10.0.0.0/16")
  ap.add_argument("--assign-prefix" ,type=int ,default=32)
  ap.add_argument("--reserve-first" ,type=int ,default=0)
  ap.add_argument("--dry-run" ,action="store_true")
  args = ap.parse_args(argv)
  with ic.open_db() as conn:
    updated ,notes = reconcile_kernel_and_db_ipv4_addresses(
      conn
      ,pool_cidr=args.pool
      ,assign_prefix=args.assign_prefix
      ,reserve_first=args.reserve_first
      ,dry_run=args.dry_run
    )
  if notes:
    print("\n".join(notes))
  if not args.dry_run:
    print(f"updated rows: {updated}")
  return 0


if __name__ == "__main__":
  import sys
  sys.exit(main())
