#!/usr/bin/env python3
# Helpers to upsert a row in server bound to a client iface.

from __future__ import annotations
import sqlite3
from typing import Optional, Any, Dict
import incommon as ic  # provides open_db, get_client_id

def upsert_server(conn: sqlite3.Connection,
                  *,
                  client_iface: str,
                  server_name: str,
                  server_public_key: str,
                  endpoint_host: str,
                  endpoint_port: int,
                  allowed_ips: str,
                  preshared_key: Optional[str] = None,
                  keepalive_s: Optional[int] = None,
                  route_allowed_ips: int = 0,
                  priority: int = 100) -> str:
  cid = ic.get_client_id(conn, client_iface)

  row = conn.execute(
    "SELECT id, public_key, preshared_key, endpoint_host, endpoint_port, allowed_ips, "
    "       keepalive_s, route_allowed_ips, priority "
    "FROM server WHERE iface_id=? AND name=? LIMIT 1;",
    (cid, server_name),
  ).fetchone()

  desired = {
    "public_key": server_public_key,
    "preshared_key": preshared_key,
    "endpoint_host": endpoint_host,
    "endpoint_port": endpoint_port,
    "allowed_ips": allowed_ips,
    "keepalive_s": keepalive_s,
    "route_allowed_ips": route_allowed_ips,
    "priority": priority,
  }

  if row is None:
    q = (
      "INSERT INTO server (iface_id,name,public_key,preshared_key,"
      " endpoint_host,endpoint_port,allowed_ips,keepalive_s,route_allowed_ips,priority,"
      " created_at,updated_at) "
      "VALUES (?,?,?,?,?,?,?,?,?,?, strftime('%Y-%m-%dT%H:%M:%SZ','now'), strftime('%Y-%m-%dT%H:%M:%SZ','now'));"
    )
    params = (cid, server_name, desired["public_key"], desired["preshared_key"],
              desired["endpoint_host"], desired["endpoint_port"], desired["allowed_ips"],
              desired["keepalive_s"], desired["route_allowed_ips"], desired["priority"])
    cur = conn.execute(q, params); conn.commit()
    return f"seeded: server(name={server_name}) client={client_iface} id={cur.lastrowid}"
  else:
    sid, pub, psk, host, port, allow, ka, route_ai, prio = row
    current = {
      "public_key": pub, "preshared_key": psk, "endpoint_host": host, "endpoint_port": port,
      "allowed_ips": allow, "keepalive_s": ka, "route_allowed_ips": route_ai, "priority": prio
    }
    changes: Dict[str, Any] = {k: v for k, v in desired.items() if v != current.get(k)}
    if not changes:
      return f"ok: server(name={server_name}) client={client_iface} unchanged id={sid}"
    sets = ", ".join(f"{k}=?" for k in changes)
    params = list(changes.values()) + [cid, server_name]
    conn.execute(
      f"UPDATE server SET {sets}, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') "
      "WHERE iface_id=? AND name=?;", params
    )
    conn.commit()
    return f"updated: server(name={server_name}) client={client_iface} id={sid} " + " ".join(f"{k}={changes[k]}" for k in changes)
