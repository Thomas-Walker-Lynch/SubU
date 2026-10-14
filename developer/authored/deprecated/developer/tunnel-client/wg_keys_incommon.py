#!/usr/bin/env python3
# wg_keys_incommon.py — predicates + actuators for WG keypairs

from __future__ import annotations
import shutil, subprocess, sqlite3

def wellformed_client_keypair(conn: sqlite3.Connection, iface: str) -> bool:
  """Predicate: True iff client IFACE has a syntactically valid WG keypair."""
  row = conn.execute(
    "SELECT private_key, public_key FROM Iface WHERE iface=? LIMIT 1;", (iface,)
  ).fetchone()
  if not row: return False
  priv, pub = (row[0] or ""), (row[1] or "")
  return (43 <= len(priv.strip()) <= 45) and (43 <= len(pub.strip()) <= 45)

def generate_client_keypair_if_missing(conn: sqlite3.Connection, iface: str) -> bool:
  """
  Actuator: if IFACE lacks a well-formed keypair, generate one with `wg`,
  store it in the DB, and return True. Return False if nothing changed.
  """
  if wellformed_client_keypair(conn, iface):
    return False
  if not shutil.which("wg"):
    raise RuntimeError("wg not found; cannot generate keys")
  gen = subprocess.run(["wg","genkey"], capture_output=True, text=True, check=True)
  priv = gen.stdout.strip()
  pubp = subprocess.run(["wg","pubkey"], input=priv.encode(), capture_output=True, check=True)
  pub = pubp.stdout.decode().strip()
  conn.execute(
    "UPDATE Iface SET private_key=?, public_key=?, "
    "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE iface=?",
    (priv, pub, iface),
  )
  return True
