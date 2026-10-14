#!/usr/bin/env python3
"""
stage_wg_conf.py

Given:
  - SQLite DB reachable via incommon.open_db()
  - A list of interface names (e.g., x6 ,US)
  - client_machine_name used to locate the private key file under ./key/<client_machine_name>

Does:
  - For each iface, stage a minimal WireGuard config to stage/etc/wireguard/<iface>.conf:
      [Interface]
        PrivateKey = <from ./key/<client_machine_name>>
        Table = off
        ListenPort = <Iface.listen_port>  (if the column exists and value is not NULL)
        # ListenPort = 51820               (commented if value is absent)
      [Peer] (one per Server row for that iface)
        PublicKey = <Server.public_key>
        PresharedKey = <Server.preshared_key>     (only if present)
        AllowedIPs = <Server.allowed_ips>
        Endpoint = <Server.endpoint_host>:<Server.endpoint_port>
        PersistentKeepalive = <Server.keepalive_s>  (only if present)
  - Omits Address ,PostUp ,SaveConfig (your systemd drop-in + script handle L3 state)

Returns:
  - (list_of_staged_paths ,notes)

Errors:
  - Missing private key file
  - Iface not found
  - Server rows missing required fields for that iface
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict ,Iterable ,List ,Optional ,Sequence ,Tuple
import argparse
import sqlite3
import sys

import incommon as ic  # expected: open_db()

ROOT = Path(__file__).resolve().parent
STAGE_ROOT = ROOT / "stage"


# ---------- helpers ----------

def _has_column(conn: sqlite3.Connection ,table: str ,col: str) -> bool:
  cur = conn.execute(f"PRAGMA table_info({table});")
  cols = [str(r[1]) for r in cur.fetchall()]
  return col in cols


def _read_private_key(client_machine_name: str ,key_root: Optional[Path] = None) -> str:
  kr = key_root or (ROOT / "key")
  path = kr / client_machine_name
  if not path.exists():
    raise RuntimeError(f"private key file missing: {path}")
  text = path.read_text().strip()
  if not text:
    raise RuntimeError(f"private key file empty: {path}")
  # WireGuard private keys are base64 (typically 44 chars), but don't over-validate here.
  return text


# ---------- DB ----------

def _fetch_iface_ids_and_ports(
  conn: sqlite3.Connection
  ,iface_names: Sequence[str]
) -> Dict[str ,Tuple[int ,Optional[int]]]:
  """
  Return {iface_name -> (iface_id ,listen_port_or_None)} for requested names.
  If the listen_port column does not exist, value is None.
  """
  if not iface_names:
    return {}
  ph = ",".join("?" for _ in iface_names)
  has_lp = _has_column(conn ,"Iface" ,"listen_port")
  select_lp = ", i.listen_port" if has_lp else ", NULL as listen_port"
  sql = f"""
  SELECT i.id
       , i.iface
       {select_lp}
  FROM Iface i
  WHERE i.iface IN ({ph})
  ORDER BY i.id;
  """
  rows = conn.execute(sql ,tuple(iface_names)).fetchall()
  out: Dict[str ,Tuple[int ,Optional[int]]] = {}
  for iid ,name ,lp in rows:
    out[str(name)] = (int(iid) ,(int(lp) if lp is not None else None))
  return out


def _fetch_peers_for_iface(
  conn: sqlite3.Connection
  ,iface_id: int
) -> List[Tuple[str ,Optional[str] ,str ,int ,str ,Optional[int] ,int ,int]]:
  """
  Return peers as tuples:
    (public_key ,preshared_key ,endpoint_host ,endpoint_port ,allowed_ips ,keepalive_s ,priority ,id)
  """
  sql = """
  SELECT public_key
       , NULLIF(TRIM(preshared_key),'') as preshared_key
       , endpoint_host
       , endpoint_port
       , allowed_ips
       , keepalive_s
       , priority
       , id
  FROM Server
  WHERE iface_id = ?
  ORDER BY priority ASC , id ASC;
  """
  rows = conn.execute(sql ,(iface_id,)).fetchall()
  out: List[Tuple[str ,Optional[str] ,str ,int ,str ,Optional[int] ,int ,int]] = []
  for pub ,psk ,host ,port ,alips ,ka ,prio ,sid in rows:
    out.append((str(pub) ,(str(psk) if psk is not None else None) ,str(host) ,int(port) ,str(alips) ,(int(ka) if ka is not None else None) ,int(prio) ,int(sid)))
  return out


# ---------- rendering ----------

def _render_conf(
  iface_name: str
  ,private_key: str
  ,listen_port: Optional[int]
  ,peers: Sequence[Tuple[str ,Optional[str] ,str ,int ,str ,Optional[int] ,int ,int]]
) -> str:
  lines: List[str] = []
  lines += [
    "[Interface]"
   ,f"PrivateKey = {private_key}"
   ,"Table = off"
  ]
  if listen_port is not None:
    lines.append(f"ListenPort = {listen_port}")
  else:
    lines.append("# ListenPort = 51820")

  lines.append("")  # blank before peers

  if not peers:
    # You may choose to raise instead; keeping an empty peer set is valid but rarely useful.
    lines.append("# (no peers found for this interface)")

  for pub ,psk ,host ,port ,alips ,ka ,_prio ,_sid in peers:
    lines += [
      "[Peer]"
     ,f"PublicKey = {pub}"
    ]
    if psk is not None:
      lines.append(f"PresharedKey = {psk}")
    lines += [
      f"AllowedIPs = {alips}"
     ,f"Endpoint = {host}:{port}"
    ]
    if ka is not None:
      lines.append(f"PersistentKeepalive = {ka}")
    lines.append("")  # blank line between peers

  return "\n".join(lines).rstrip() + "\n"


# ---------- business ----------

def stage_wg_conf(
  conn: sqlite3.Connection
  ,iface_names: Sequence[str]
  ,client_machine_name: str
  ,stage_root: Optional[Path] = None
  ,dry_run: bool = False
) -> Tuple[List[Path] ,List[str]]:
  """
  Stage /etc/wireguard/<iface>.conf for selected ifaces under stage root.
  """
  if not iface_names:
    raise RuntimeError("no interfaces provided")
  priv = _read_private_key(client_machine_name)

  meta = _fetch_iface_ids_and_ports(conn ,iface_names)
  if not meta:
    raise RuntimeError("none of the requested interfaces exist in DB")

  staged: List[Path] = []
  notes: List[str] = []
  sr = stage_root or STAGE_ROOT
  outdir = sr / "etc" / "wireguard"
  outdir.mkdir(parents=True ,exist_ok=True)

  for name in iface_names:
    if name not in meta:
      notes.append(f"skip: iface '{name}' missing from DB")
      continue

    iface_id ,listen_port = meta[name]
    peers = _fetch_peers_for_iface(conn ,iface_id)

    # basic validation of required peer fields
    bad = []
    for pub ,_psk ,host ,port ,alips ,_ka ,_prio ,sid in peers:
      if not pub or not host or not alips or not (1 <= int(port) <= 65535):
        bad.append(sid)
    if bad:
      raise RuntimeError(f"iface '{name}': invalid peer rows id={bad}")

    conf_text = _render_conf(name ,priv ,listen_port ,peers)

    out = outdir / f"{name}.conf"
    if dry_run:
      notes.append(f"dry-run: would write {out}")
    else:
      out.write_text(conf_text)
      out.chmod(0o600)
      staged.append(out)
      notes.append(f"staged: {out}")

  if not staged and not dry_run:
    raise RuntimeError("nothing staged (all missing or skipped)")

  return (staged ,notes)


# ---------- CLI ----------

def main(argv=None) -> int:
  ap = argparse.ArgumentParser(description="Stage minimal WireGuard configs with Table=off and no Address.")
  ap.add_argument("client_machine_name" ,help="name used to read ./key/<client_machine_name>")
  ap.add_argument("ifaces" ,nargs="+" ,help="interface names to stage")
  ap.add_argument("--dry-run" ,action="store_true")
  args = ap.parse_args(argv)

  with ic.open_db() as conn:
    try:
      paths ,notes = stage_wg_conf(
        conn
       ,args.ifaces
       ,args.client_machine_name
       ,dry_run=args.dry_run
      )
    except Exception as e:
      print(f"error: {e}" ,file=sys.stderr)
      return 2

  if notes:
    print("\n".join(notes))
  return 0


if __name__ == "__main__":
  sys.exit(main())
