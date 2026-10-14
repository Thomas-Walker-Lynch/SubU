#!/usr/bin/env python3
# inspect_client_public_key.py — show the client's WireGuard public key for one iface
# Sources checked (in this order): DB, staged conf, installed conf, kernel
# The “client public key” is generated locally from the client’s PrivateKey and must be
# copied to the **server** as the peer’s PublicKey in the server’s WireGuard config.

from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple
import argparse
import os
import subprocess
import sqlite3
import sys

# Project helper providing DB_PATH and open_db()
import incommon as ic

ROOT = Path(__file__).resolve().parent
DEFAULT_STAGE = ROOT / "stage"
LIVE_WG_DIR = Path("/etc/wireguard")

def _is_root() -> bool:
    return os.geteuid() == 0

def _format_table(headers: List[str], rows: List[Tuple]) -> str:
    if not rows:
        return "(none)"
    cols = list(zip(*([headers] + [[("" if c is None else str(c)) for c in r] for r in rows])))
    widths = [max(len(x) for x in col) for col in cols]
    def line(r): return "  ".join(f"{str(c):<{w}}" for c, w in zip(r, widths))
    out = [line(headers), line(tuple("-"*w for w in widths))]
    for r in rows:
        out.append(line(r))
    return "\n".join(out)

def _read_conf_private_key(conf_path: Path) -> Optional[str]:
    """Return the PrivateKey value from a wg conf (first [Interface] block), or None."""
    try:
        txt = conf_path.read_text()
    except FileNotFoundError:
        return None
    section = None
    for raw in txt.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if section == "Interface":
            if line.lower().startswith("privatekey"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    val = parts[1].strip()
                    return val if val else None
    return None

def _pub_from_private_key(priv: str) -> Optional[str]:
    """Compute public key from a WireGuard base64 private key using `wg pubkey`."""
    if not priv:
        return None
    try:
        cp = subprocess.run(
            ["wg", "pubkey"],
            input=(priv + "\n").encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        pub = cp.stdout.decode("utf-8", "replace").strip()
        return pub or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def _kernel_iface_public_key(iface: str) -> Optional[str]:
    try:
        cp = subprocess.run(
            ["wg", "show", iface, "public-key"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        k = cp.stdout.decode("utf-8", "replace").strip()
        return k or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def _db_client_public_key(conn: sqlite3.Connection, iface: str) -> Optional[str]:
    row = conn.execute("SELECT public_key FROM Iface WHERE iface=? LIMIT 1;", (iface,)).fetchone()
    if not row:
        return None
    k = row[0]
    return k if k else None

def _rel_from_stage(path: Path, stage_root: Path) -> str:
    """Return a short, stage-relative display path when under stage_root."""
    try:
        rel = path.relative_to(stage_root)
        return str(rel)
    except ValueError:
        return str(path)

def _gather(iface: str, stage_root: Path) -> Tuple[List[Tuple[str, str, str]], List[str]]:
    """
    Return (rows, notes)
    rows: list of (source, location, public_key or "(missing)")
    """
    notes: List[str] = []

    # DB
    db_pub: Optional[str] = None
    if ic.DB_PATH.exists():
        try:
            with ic.open_db() as conn:
                db_pub = _db_client_public_key(conn, iface)
        except sqlite3.Error as e:
            notes.append(f"DB error: {e}")
    else:
        notes.append(f"DB not found at {ic.DB_PATH}")

    # staged conf -> derive pub from PrivateKey
    staged_conf = stage_root / "etc" / "wireguard" / f"{iface}.conf"
    staged_priv = _read_conf_private_key(staged_conf)
    staged_pub = _pub_from_private_key(staged_priv) if staged_priv else None
    if staged_priv is None and staged_conf.exists():
        notes.append(f"staged conf present but PrivateKey missing: { _rel_from_stage(staged_conf, stage_root) }")

    # live conf -> derive pub from PrivateKey
    live_conf = LIVE_WG_DIR / f"{iface}.conf"
    live_priv = _read_conf_private_key(live_conf)
    live_pub = _pub_from_private_key(live_priv) if live_priv else None
    if live_conf.exists() and live_priv is None:
        notes.append(f"installed conf present but PrivateKey missing: {live_conf}")

    # kernel
    kern_pub = _kernel_iface_public_key(iface)

    rows: List[Tuple[str, str, str]] = []
    rows.append(("DB", f"Iface.public_key[{iface}]", db_pub or "(missing)"))
    rows.append(("Stage", _rel_from_stage(staged_conf, stage_root),
                 staged_pub or ("(missing)" if not staged_conf.exists() else "(could not derive)")))
    rows.append(("Installed", str(live_conf),
                 live_pub or ("(missing)" if not live_conf.exists() else "(could not derive)")))
    rows.append(("Kernel", f"wg show {iface} public-key", kern_pub or "(missing)"))

    # Quick consistency summary
    present = [v for _s, _loc, v in rows if not v.startswith("(")]
    if len(present) >= 2:
        all_same = all(v == present[0] for v in present[1:])
        if all_same:
            notes.append("All present sources agree.")
        else:
            notes.append("Mismatch detected between sources.")
    elif len(present) == 1:
        notes.append("Only one source has a key (cannot check consistency).")
    else:
        notes.append("No source has a client public key.")

    return (rows, notes)

def inspect_client_public_key(iface: str, stage_root: Optional[Path] = None) -> str:
    """
    Business function: returns a formatted report string.
    """
    sr = stage_root or DEFAULT_STAGE
    rows, notes = _gather(iface, sr)

    header = (
        f"Client public key inspection for iface '{iface}'\n"
        "This public key is generated locally from the client’s PrivateKey and must be\n"
        "installed on the *server* as the peer’s PublicKey in the server’s WireGuard config.\n"
    )
    table = _format_table(["source", "where", "public_key"], rows)
    if notes:
        note_block = "\nNotes:\n- " + "\n- ".join(notes)
    else:
        note_block = ""
    return f"{header}\n{table}\n{note_block}\n"

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Inspect the client’s WireGuard public key for a single interface."
    )
    # Make iface optional so we can aggregate errors ourselves
    ap.add_argument("iface", nargs="?", help="interface name (e.g., x6)")
    ap.add_argument("--stage-root", default=str(DEFAULT_STAGE), help="stage directory (default: ./stage)")
    args = ap.parse_args(argv)

    # Aggregate invocation errors
    errors: List[str] = []
    if not _is_root():
        errors.append("must run as root (needs access to /etc/wireguard and wg)")
    if not args.iface:
        errors.append("missing required positional argument: iface")
    if args.stage_root:
        sr = Path(args.stage_root)
        if not sr.exists():
            errors.append(f"--stage-root does not exist: {sr}")
        elif not sr.is_dir():
            errors.append(f"--stage-root is not a directory: {sr}")

    if errors:
        ap.print_usage(sys.stderr)
        print(f"{ap.prog}: error: " + "; ".join(errors), file=sys.stderr)
        return 2

    try:
        report = inspect_client_public_key(args.iface, Path(args.stage_root))
        print(report, end="")
        return 0
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
