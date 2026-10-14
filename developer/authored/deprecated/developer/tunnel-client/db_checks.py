#!/usr/bin/env python3
# db_checks.py — quick audit for common misconfigurations

from __future__ import annotations
import sys, sqlite3, ipaddress
import incommon as ic

def audit(conn: sqlite3.Connection) -> int:
  errs = 0

  # 1) client present?
  C = ic.rows(conn, """
    SELECT id, iface, local_address_cidr, rt_table_name_eff
      FROM v_client_effective
     ORDER BY iface;
  """)
  if not C:
    print("WARN: no client present"); return 1

  # 2) CIDR sanity
  for cid, iface, cidr, rtname in C:
    try:
      ipaddress.IPv4Interface(cidr)
    except Exception as e:
      print(f"ERR: client {iface} has invalid CIDR {cidr}: {e}")
      errs += 1

  # 3) server exist and map to client
  S = ic.rows(conn, """
    SELECT s.id, c.iface, s.name, s.public_key, s.endpoint_host, s.endpoint_port, s.allowed_ips
      FROM server s
      JOIN Iface c ON c.id = s.iface_id
     ORDER BY c.iface, s.name;
  """)
  if not S:
    print("WARN: no server present for any client")

  # 4) user bindings exist? (not required, but useful)
  UB = ic.rows(conn, """
    SELECT c.iface, ub.username, ub.uid
      FROM User ub
      JOIN Iface c ON c.id = ub.iface_id
     ORDER BY c.iface, ub.username;
  """)
  if not UB:
    print("WARN: no User present")

  # 5) duplicate tunnel IPs across client (/32 equality)
  tunnel_hosts = {}
  for _, iface, cidr, _ in C:
    try:
      host = str(ipaddress.IPv4Interface(cidr).ip)
      if host in tunnel_hosts and tunnel_hosts[host] != iface:
        print(f"ERR: duplicate tunnel host {host} on {tunnel_hosts[host]} and {iface}")
        errs += 1
      else:
        tunnel_hosts[host] = iface
    except Exception:
      pass

  # 6) Server AllowedIPs hygiene: warn when 0.0.0.0/0 appears in server table
  for sid, iface, sname, pub, host, port, allow in S:
    if allow.strip() == "0.0.0.0/0":
      # client-side full-tunnel is fine; server-side peer should use /32 entries
      print(f"NOTE: server(name={sname}, client={iface}) has AllowedIPs=0.0.0.0/0 (client-side full-tunnel). Ensure server peer uses /32(s).")

  # 7) meta.subu_cidr present?
  M = dict(ic.rows(conn, "SELECT key, value FROM meta;"))
  if "subu_cidr" not in M:
    print("WARN: meta.subu_cidr missing; default tooling may assume 10.0.0.0/24")

  print("OK: audit complete" if errs == 0 else f"FAIL: {errs} error(s)")
  return 1 if errs else 0

def main(argv: list[str]) -> int:
  try:
    with ic.open_db() as conn:
      return audit(conn)
  except (sqlite3.Error, FileNotFoundError) as e:
    print(f"❌ {e}", file=sys.stderr)
    return 2

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
