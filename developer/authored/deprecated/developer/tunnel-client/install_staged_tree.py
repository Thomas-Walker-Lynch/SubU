#!/usr/bin/env python3
"""
install_staged_tree.py

A dumb installer: copy staged files into the target root with backups and
deterministic permissions. No systemd stop/start, no daemon-reload.

Given:
  - A staged tree (default: ./stage) containing any of:
      /usr/local/bin/apply_ip_state.sh
      /etc/wireguard/*.conf
      /etc/systemd/system/wg-quick@IFACE.service.d/*.conf
      /etc/iproute2/rt_tables
  - A destination root (default: /). Parent dirs may be created with --create-dirs.

Does:
  - For each whitelisted staged file:
      * if a target already exists, copy it back into the stage as a timestamped backup
      * atomically replace target with staged version
      * set root:root ownership (best-effort) and explicit permissions
  - Prints a summary and suggests next steps (e.g., ./start_iface.py <ifaces>)

Returns:
  - Exit 0 on success; non-zero on error
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import argparse
import datetime as dt
import hashlib
import os
import shutil
import sys

ROOT = Path(__file__).resolve().parent
DEFAULT_STAGE = ROOT / "stage"

# Whitelisted install targets → mode
# (These are *relative* to the stage root)
MODE_RULES: List[Tuple[str, int]] = [
  ("usr/local/bin",                 0o500),  # files under here (scripts)
  ("etc/wireguard",                 0o600),  # *.conf
  ("etc/systemd/system",            0o644),  # wg-quick@*.service.d/*.conf
  ("etc/iproute2",                  0o644),  # rt_tables
]

def _sha256(path: Path) -> str:
  h = hashlib.sha256()
  with path.open("rb") as f:
    for chunk in iter(lambda: f.read(1<<20), b""):
      h.update(chunk)
  return h.hexdigest()

def _ensure_parents(dest_root: Path, rel: Path, create: bool) -> None:
  parent = (dest_root / rel).parent
  if parent.exists():
    return
  if not create:
    raise RuntimeError(f"missing parent directory: {parent}")
  parent.mkdir(parents=True, exist_ok=True)

def _backup_existing_to_stage(stage_root: Path, dest_root: Path, rel: Path) -> Optional[Path]:
  """If target exists, copy it back into stage/_backups/<ts>/<rel> and return backup path."""
  target = dest_root / rel
  if not target.exists():
    return None
  ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
  backup = stage_root / "_backups" / ts / rel
  backup.parent.mkdir(parents=True, exist_ok=True)
  shutil.copy2(target, backup)
  return backup

def _atomic_install(src: Path, dst: Path, mode: int) -> None:
  tmp = dst.with_suffix(dst.suffix + ".tmp")
  shutil.copyfile(src, tmp)
  os.chmod(tmp, mode)
  try:
    os.chown(tmp, 0, 0)  # best-effort; may fail if not root
  except PermissionError:
    pass
  os.replace(tmp, dst)

def _mode_for_rel(rel: Path) -> Optional[int]:
  """Choose a mode based on the relative path bucket."""
  s = str(rel)
  if s.startswith("usr/local/bin/"):
    return 0o500
  if s.startswith("etc/wireguard/") and rel.suffix == ".conf":
    return 0o600
  if s == "etc/iproute2/rt_tables":
    return 0o644
  if s.startswith("etc/systemd/system/") and s.endswith(".conf"):
    return 0o644
  return None

def _iter_stage_targets(stage_root: Path) -> List[Path]:
  """Return a list of *relative* paths under stage that match our whitelist."""
  rels: List[Path] = []

  # /usr/local/bin/*
  bin_dir = stage_root / "usr" / "local" / "bin"
  if bin_dir.is_dir():
    for p in sorted(bin_dir.glob("*")):
      if p.is_file():
        rels.append(p.relative_to(stage_root))

  # /etc/wireguard/*.conf
  wg_dir = stage_root / "etc" / "wireguard"
  if wg_dir.is_dir():
    for p in sorted(wg_dir.glob("*.conf")):
      rels.append(p.relative_to(stage_root))

  # /etc/systemd/system/wg-quick@*.service.d/*.conf
  sysd_dir = stage_root / "etc" / "systemd" / "system"
  if sysd_dir.is_dir():
    for p in sorted(sysd_dir.rglob("wg-quick@*.service.d/*.conf")):
      rels.append(p.relative_to(stage_root))

  # /etc/iproute2/rt_tables
  rt = stage_root / "etc" / "iproute2" / "rt_tables"
  if rt.is_file():
    rels.append(rt.relative_to(stage_root))

  return rels

def _discover_ifaces_from_stage(stage_root: Path) -> List[str]:
  """Peek into staged artifacts to guess iface names (for friendly next-steps)."""
  names = set()

  # from /etc/wireguard/<iface>.conf
  wg_dir = stage_root / "etc" / "wireguard"
  if wg_dir.is_dir():
    for p in wg_dir.glob("*.conf"):
      names.add(p.stem)

  # from /etc/systemd/system/wg-quick@<iface>.service.d/
  sysd = stage_root / "etc" / "systemd" / "system"
  if sysd.is_dir():
    for d in sysd.glob("wg-quick@*.service.d"):
      name = d.name
      # name looks like: wg-quick@X.service.d
      at = name.find("@")
      dot = name.find(".service.d")
      if at != -1 and dot != -1 and dot > at:
        names.add(name[at+1:dot])

  return sorted(names)

def install_staged_tree(
   stage_root: Path,
   dest_root: Path,
   create_dirs: bool = False,
   skip_identical: bool = True,
) -> Tuple[List[str], List[str]]:
  """
  Copy files from stage_root to dest_root.
  Returns (logs, detected_ifaces).
  """
  old_umask = os.umask(0o077)
  logs: List[str] = []
  try:
    staged = _iter_stage_targets(stage_root)
    if not staged:
      raise RuntimeError("nothing to install (stage is empty or whitelist didn’t match)")

    for rel in staged:
      src = stage_root / rel
      dst = dest_root / rel

      mode = _mode_for_rel(rel)
      if mode is None:
        logs.append(f"skip (not whitelisted): {rel}")
        continue

      _ensure_parents(dest_root, rel, create_dirs)

      backup = _backup_existing_to_stage(stage_root, dest_root, rel)
      if backup:
        logs.append(f"backup: {dst} -> {backup}")

      if skip_identical and dst.exists():
        try:
          if _sha256(src) == _sha256(dst):
            logs.append(f"identical: skip {rel}")
            continue
        except Exception:
          pass

      _atomic_install(src, dst, mode)
      logs.append(f"install: {rel} (mode {oct(mode)})")

    ifaces = _discover_ifaces_from_stage(stage_root)
    return (logs, ifaces)
  finally:
    os.umask(old_umask)

def _require_root(allow_nonroot: bool) -> None:
  if not allow_nonroot and os.geteuid() != 0:
    raise RuntimeError("must run as root (use --force-nonroot to override)")

def main(argv: Optional[Sequence[str]] = None) -> int:
  ap = argparse.ArgumentParser(description="Install staged artifacts into a target root. No service control.")
  ap.add_argument("--stage", default=str(DEFAULT_STAGE))
  ap.add_argument("--root",  default="/")
  ap.add_argument("--create-dirs", action="store_true", help="create missing parent directories")
  ap.add_argument("--no-skip-identical", action="store_true", help="always replace even if content identical")
  ap.add_argument("--force-nonroot", action="store_true", help="allow non-root install (ownership may be wrong)")
  args = ap.parse_args(argv)

  try:
    _require_root(allow_nonroot=args.force_nonroot)
    logs, ifaces = install_staged_tree(
      stage_root=Path(args.stage),
      dest_root=Path(args.root),
      create_dirs=args.create_dirs,
      skip_identical=(not args.no_skip_identical),
    )
    for line in logs:
      print(line)

    # Summary + suggested next steps
    print("\n=== Summary ===")
    print(f"Installed {sum(1 for l in logs if l.startswith('install:'))} file(s).")
    if ifaces:
      lst = " ".join(ifaces)
      print(f"Detected interfaces from stage: {lst}")
      print(f"\nNext steps:")
      print(f"  # (optional) verify configs")
      print(f"  sudo wg-quick strip /etc/wireguard/{ifaces[0]}.conf >/dev/null 2>&1 || true")
      print(f"\n  # start interfaces")
      print(f"  sudo ./start_iface.py {lst}")
    else:
      print("No interfaces detected in staged artifacts.")
      print("\nNext steps:")
      print("  # start your interface(s)")
      print("  sudo ./start_iface.py <iface> [more ifaces]")
    return 0
  except Exception as e:
    print(f"❌ install failed: {e}", file=sys.stderr)
    return 2

if __name__ == "__main__":
  sys.exit(main())
