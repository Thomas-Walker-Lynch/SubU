#!/usr/bin/env python3
"""
ls_server_settings.py — print server-side WireGuard [Peer] stanzas from the DB

Purpose:
  Emit configuration that belongs in a *server* wg conf (e.g., /etc/wireguard/wg0.conf).
  One [Peer] block per (client, server) row.

What is printed (per block):
  - PublicKey      = client's public key (from client.public_key)
  - AllowedIPs     = client's tunnel address(es) as seen by the server (from client.local_address_cidr)
                     (Use /32 per client. If multiple /32 per client are later added, enumerate them.)
  - PresharedKey   = server.preshared_key (only if present)

Notes:
  - Endpoint is NOT set on the server for client peers (client usually dials the server).
  - PersistentKeepalive is generally set on the client; server may omit it.

Usage:
  ./ls_server_settings.py                 # all client and their server entries
  ./ls_server_settings.py x6 us           # only for these client ifaces
  ./ls_server_settings.py --server x6     # filter by server.name
"""

from __future__ import annotations
import sys, sqlite3
from typing import Iterable, List, Optional, Sequence, Tuple
from pathlib import Path

# local helper import is optional; only used to locate db path if present
try:
  import incommon as ic
  DB_PATH = ic.DB_PATH
except Exception:
  DB_PATH = Path(__file__).resolve().parent / "db" / "store"

def die(msg: str, code: int = 1) -> None:
  print(f"❌ {msg}", file=sys.stderr); sys.exit(code)

def open_db(path: Path) -> sqlite3.Connection:
  if not path.exists(): die(f"DB not found: {path}")
  return sqlite3.connect(path.as_posix())

def parse_args(argv: Sequence[str]) -> Tuple[List[str], Optional[str]]:
  ifaces: List[str] = []
  server_filter: Optional[str] = None
  it = iter(argv)
  for a in it:
    if a == "--server":
      try: server_filter = next(it)
      except StopIteration: die("--server requires a value")
    else:
      ifaces.append(a)
  return ifaces, server_filter

def rows(conn: sqlite3.Connection, q: str, params: Iterable = ()) -> List[tuple]:
  cur = conn.execute(q, tuple(params))
  out = cur.fetchall()
  cur.close()
  return out

def collect(conn: sqlite3.Connection, ifaces: List[str], server_filter: Optional[str]) -> List[dict]:
  where = []
  args: List = []
  if ifaces:
    ph = ",".join("?" for _ in ifaces)
    where.append(f"c.iface IN ({ph})")
    args.extend(ifaces)
  if server_filter:
    where.append("s.name = ?")
    args.append(server_filter)
  w = ("WHERE " + " AND ".join(where)) if where else ""
  q = f"""
    SELECT c.id, c.iface, c.public_key, c.local_address_cidr,
           s.name, s.preshared_key, s.endpoint_host, s.endpoint_port
      FROM Iface c
 LEFT JOIN server s ON s.iface_id = c.id
      {w}
  ORDER BY s.name, c.iface, s.priority ASC, s.id ASC;
  """
  R = rows(conn, q, args)
  out: List[dict] = []
  for cid, iface, cpub, cidr, sname, psk, host, port in R:
    out.append({
      "iface_id": cid,
      "iface": iface or "",
      "client_pub": cpub or "",
      "client_cidr": cidr or "",
      "server_name": sname or "(unassigned)",
      "server_host": host or "",
      "server_port": port or None,
      "psk": psk or None,
    })
  return out

def print_header() -> None:
  print("# === Server-side WireGuard peer stanzas ===")
  print("# Place each [Peer] block into the server's wg conf (e.g., /etc/wireguard/wg0.conf).")
  print("# Endpoint is not set for client peers on the server.")
  print("# AllowedIPs must be /32 per client address; enumerate multiple /32 if a client uses several.")
  print()

def print_blocks(items: List[dict]) -> None:
  if not items:
    print("# (no rows matched)"); return
  print_header()
  # group by server_name for readability
  cur_group = None
  for r in items:
    grp = r["server_name"]
    if grp != cur_group:
      cur_group = grp
      ep = f" ({r['server_host']}:{r['server_port']})" if r["server_host"] and r["server_port"] else ""
      print(f"## Server: {grp}{ep}")
    # stanza
    print("[Peer]")
    print(f"# client iface={r['iface']}  tunnel={r['client_cidr']}")
    print(f"PublicKey = {r['client_pub']}")
    # AllowedIPs: prefer the exact CIDR stored for the client (typically /32)
    print(f"AllowedIPs = {r['client_cidr']}")
    if r["psk"]:
      print(f"PresharedKey = {r['psk']}")
    print()
  # end

def main(argv: Sequence[str]) -> int:
  ifaces, server_filter = parse_args(argv)
  try:
    with open_db(DB_PATH) as conn:
      items = collect(conn, ifaces, server_filter)
  except sqlite3.Error as e:
    die(f"sqlite error: {e}")
  print_blocks(items)
  return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
