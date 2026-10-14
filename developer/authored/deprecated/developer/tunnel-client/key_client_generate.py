#!/usr/bin/env python3
# key_client_generate.py — generate a machine-wide WG keypair
# Usage: ./key_client_generate.py <machine_name>
# - Writes private key to: key/<machine_name>
# - Updates ALL client.public_key in local DB (no private key stored in DB)

from __future__ import annotations
import sys, shutil, subprocess, sqlite3, os
from pathlib import Path
import incommon as ic  # ROOT_DIR, DB_PATH, open_db()

def generate_keypair() -> tuple[str, str]:
  if not shutil.which("wg"):
    raise RuntimeError("wg not found; install wireguard-tools")
  priv = subprocess.run(["wg","genkey"], check=True, text=True, capture_output=True).stdout.strip()
  pub  = subprocess.run(["wg","pubkey"], check=True, input=priv.encode(), capture_output=True).stdout.decode().strip()
  # quick sanity
  if not (43 <= len(pub) <= 45):
    raise RuntimeError(f"generated public key length looks wrong ({len(pub)})")
  return priv, pub

def write_private_key(machine: str, private_key: str) -> Path:
  key_dir = ic.ROOT_DIR / "key"
  key_dir.mkdir(parents=True, exist_ok=True)
  out_path = key_dir / machine
  if out_path.exists():
    raise FileExistsError(f"refusing to overwrite existing private key file: {out_path}")
  with open(out_path, "w", encoding="utf-8") as f:
    f.write(private_key + "\n")
  os.chmod(out_path, 0o600)
  return out_path

def update_client_public_keys(pub: str) -> int:
  if not ic.DB_PATH.exists():
    raise FileNotFoundError(f"DB not found: {ic.DB_PATH}")
  with ic.open_db() as conn:
    cur = conn.execute(
      "UPDATE Iface "
      "   SET public_key=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now');",
      (pub,)
    )
    conn.commit()
    return cur.rowcount or 0

def main(argv: list[str]) -> int:
  if len(argv) != 1:
    print(f"Usage: {Path(sys.argv[0]).name} <machine_name>", file=sys.stderr)
    return 2
  machine = argv[0]
  try:
    priv, pub = generate_keypair()
    out_path = write_private_key(machine, priv)
    n = update_client_public_keys(pub)
    print(f"wrote: {out_path.relative_to(ic.ROOT_DIR)} (600)")
    print(f"updated client.public_key for {n} row(s)")
    print(f"public_key: {pub}")
    return 0
  except (RuntimeError, FileExistsError, FileNotFoundError, sqlite3.Error, subprocess.CalledProcessError) as e:
    print(f"❌ {e}", file=sys.stderr)
    return 1

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
