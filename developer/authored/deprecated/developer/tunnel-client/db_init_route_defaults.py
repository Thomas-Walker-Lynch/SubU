#!/usr/bin/env python3
"""
db_init_route_defaults.py

Business API:
  seed_default_routes(conn ,iface_names ,overwrite=False ,metric=None)
    -> (inserted_count ,notes[list])

What it does:
- For each iface in iface_names, ensure a default route "0.0.0.0/0"
  is present in the Route table (on_up=1, no via/metric/table override).
- If overwrite=True, it first deletes existing Route rows for those ifaces,
  then inserts the defaults.
- Writes **DB only**. It does not touch the kernel or /etc/iproute2/rt_tables.

Why:
- Your apply script reads Route rows and emits `ip -4 route replace … table <rtname>`.
  Seeding a per-iface default route makes policy-routed tables usable out of the box.
"""

from __future__ import annotations
import argparse
import sqlite3
from typing import Dict ,Iterable ,List ,Optional ,Sequence ,Tuple

# import helper to open DB when run as CLI; the business API accepts a conn
try:
  import incommon as ic  # type: ignore
except Exception:
  ic = None  # ok when used as a lib


def _iface_map(conn: sqlite3.Connection ,iface_names: Sequence[str]) -> Dict[str ,int]:
  """Return {iface_name -> iface_id} for provided names (must exist)."""
  if not iface_names:
    return {}
  ph = ",".join("?" for _ in iface_names)
  sql = f"""SELECT id ,iface FROM Iface WHERE iface IN ({ph}) ORDER BY id;"""
  rows = conn.execute(sql ,tuple(iface_names)).fetchall()
  found = {str(name): int(iid) for (iid ,name) in rows}
  missing = [n for n in iface_names if n not in found]
  if missing:
    raise RuntimeError(f"iface(s) not found: {', '.join(missing)}")
  return found


def _existing_defaults(conn: sqlite3.Connection ,iface_ids: Iterable[int]) -> Dict[int ,bool]:
  """Return {iface_id -> True/False} whether a default route row already exists (on_up=1)."""
  ids = list(iface_ids)
  if not ids:
    return {}
  ph = ",".join("?" for _ in ids)
  sql = f"""
  SELECT iface_id ,COUNT(1)
    FROM Route
   WHERE iface_id IN ({ph})
     AND cidr='0.0.0.0/0'
     AND on_up=1
   GROUP BY iface_id;
  """
  out: Dict[int ,bool] = {i: False for i in ids}
  for iid ,cnt in conn.execute(sql ,tuple(ids)).fetchall():
    out[int(iid)] = int(cnt) > 0
  return out


def seed_default_routes(
  conn: sqlite3.Connection
  ,iface_names: Sequence[str]
  ,overwrite: bool = False
  ,metric: Optional[int] = None
) -> Tuple[int ,List[str]]:
  """
  Upsert per-iface default routes into Route.

  Inserts rows:
    (iface_id ,cidr='0.0.0.0/0' ,via=NULL ,table_name=NULL ,metric=<metric or NULL> ,on_up=1 ,on_down=0)
  """
  if not iface_names:
    raise RuntimeError("no interfaces provided")

  id_map = _iface_map(conn ,iface_names)
  iface_ids = list(id_map.values())
  notes: List[str] = []
  inserted = 0

  with conn:
    if overwrite:
      ph = ",".join("?" for _ in iface_ids)
      conn.execute(f"DELETE FROM Route WHERE iface_id IN ({ph});" ,tuple(iface_ids))
      notes.append(f"cleared existing Route rows for: {', '.join(iface_names)}")

    exists = _existing_defaults(conn ,iface_ids)

    for name in iface_names:
      iid = id_map[name]
      if exists.get(iid):
        notes.append(f"keep: default route already present for {name}")
        continue
      conn.execute(
        """
        INSERT INTO Route(iface_id ,cidr ,via ,table_name ,metric ,on_up ,on_down
                         ,created_at ,updated_at)
        VALUES( ? ,'0.0.0.0/0' ,NULL ,NULL ,? ,1 ,0
               ,strftime('%Y-%m-%dT%H:%M:%SZ','now') ,strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        """
        ,(iid ,metric)
      )
      inserted += 1
      notes.append(f"add: default route 0.0.0.0/0 for {name}")

  return (inserted ,notes)


# ---- thin CLI for ad-hoc use ----

def main(argv: Optional[Sequence[str]] = None) -> int:
  ap = argparse.ArgumentParser(description="Seed per-iface default Route rows.")
  ap.add_argument("ifaces" ,nargs="+")
  ap.add_argument("--overwrite" ,action="store_true")
  ap.add_argument("--metric" ,type=int ,default=None)
  args = ap.parse_args(argv)

  if ic is None:
    print("error: cannot locate incommon.open_db() for CLI use")
    return 2

  with ic.open_db() as conn:
    n ,notes = seed_default_routes(conn ,args.ifaces ,overwrite=args.overwrite ,metric=args.metric)
  if notes:
    print("\n".join(notes))
  print(f"inserted: {n}")
  return 0


if __name__ == "__main__":
  import sys
  sys.exit(main())
