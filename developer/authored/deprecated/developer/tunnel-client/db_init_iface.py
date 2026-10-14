#!/usr/bin/env python3
# Helpers to seed/update a row in client.

from __future__ import annotations
import sqlite3
from typing import Any, Optional, Dict
import incommon as ic  # provides DB_PATH, open_db

# Normally don't set the addr_cidr, the system will automically
# assign a free address, or reuse one that is already set.

def upsert_client(conn: sqlite3.Connection,
                  *,
                  iface: str,
                  addr_cidr: Optional[str] = None,
                  rt_table_name: Optional[str] = None,
                  rt_table_id: Optional[int] = None,
                  mtu: Optional[int] = None,
                  fwmark: Optional[int] = None,
                  dns_mode: Optional[str] = None,   # 'none' or 'static'
                  dns_servers: Optional[str] = None,
                  autostart: Optional[int] = None,  # 0 or 1
                  bound_user: Optional[str] = None,
                  bound_uid: Optional[int] = None
                 ) -> str:
  row = conn.execute(
    """SELECT id, iface, rt_table_id, rt_table_name, local_address_cidr,
                     mtu, fwmark, dns_mode, dns_servers, autostart,
                     bound_user, bound_uid
         FROM Iface WHERE iface=? LIMIT 1;""",
    (iface,)
  ).fetchone()

  defname = rt_table_name if rt_table_name is not None else iface
  desired: Dict[str, Any] = {"iface": iface, "local_address_cidr": addr_cidr}
  if rt_table_id   is not None: desired["rt_table_id"]   = rt_table_id
  if rt_table_name is not None: desired["rt_table_name"] = rt_table_name
  if mtu           is not None: desired["mtu"]           = mtu
  if fwmark        is not None: desired["fwmark"]        = fwmark
  if dns_mode      is not None: desired["dns_mode"]      = dns_mode
  if dns_servers   is not None: desired["dns_servers"]   = dns_servers
  if autostart     is not None: desired["autostart"]     = autostart
  if bound_user    is not None: desired["bound_user"]    = bound_user
  if bound_uid     is not None: desired["bound_uid"]     = bound_uid

  if row is None:
    fields = ["iface","local_address_cidr","rt_table_name"]
    vals   = [iface, addr_cidr, defname]
    for k in ("rt_table_id","mtu","fwmark","dns_mode","dns_servers","autostart","bound_user","bound_uid"):
      if k in desired: fields.append(k); vals.append(desired[k])
    q = f"INSERT INTO Iface ({','.join(fields)}) VALUES ({','.join('?' for _ in vals)});"
    cur = conn.execute(q, vals); conn.commit()
    return f"seeded: client(iface={iface}) id={cur.lastrowid} addr={addr_cidr} rt={defname}"
  else:
    cid, _, rt_id, rt_name, cur_addr, cur_mtu, cur_fwm, cur_dns_mode, cur_dns_srv, cur_auto, cur_buser, cur_buid = row
    current = {
      "local_address_cidr": cur_addr, "rt_table_id": rt_id, "rt_table_name": rt_name,
      "mtu": cur_mtu, "fwmark": cur_fwm, "dns_mode": cur_dns_mode, "dns_servers": cur_dns_srv,
      "autostart": cur_auto, "bound_user": cur_buser, "bound_uid": cur_buid
    }
    changes: Dict[str, Any] = {}
    for k, v in desired.items():
      if k == "iface": continue
      if current.get(k) != v: changes[k] = v
    if rt_name is None and "rt_table_name" not in changes:
      changes["rt_table_name"] = defname
    if not changes:
      return f"ok: client(iface={iface}) unchanged id={cid} addr={cur_addr} rt={rt_name or defname}"
    sets = ", ".join(f"{k}=?" for k in changes)
    vals = list(changes.values()) + [iface]
    conn.execute(f"UPDATE Iface SET {sets} WHERE iface=?;", vals); conn.commit()
    return f"updated: client(iface={iface}) id={cid} " + " ".join(f"{k}={changes[k]}" for k in changes)
