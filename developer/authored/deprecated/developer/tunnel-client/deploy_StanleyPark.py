#!/usr/bin/env python3
"""
deploy_StanleyPark.py — stop → install staged files → start (for selected ifaces)

- Requires root. Exits after reporting *all* detected CLI/import errors.
- Calls business functions directly:
    * stop_clean_iface.stop_clean_ifaces(ifaces)
    * install_staged_tree.install_staged_tree(stage_root, dest_root, create_dirs, skip_identical)
    * start_iface.start_ifaces(ifaces)
- If no ifaces provided on CLI, it discovers them from the stage tree.

Usage:
  sudo ./deploy_StanleyPark.py            # discover ifaces from stage, stop→install→start
  sudo ./deploy_StanleyPark.py x6 US      # explicit iface list
  sudo ./deploy_StanleyPark.py --no-stop  # skip stop step
  sudo ./deploy_StanleyPark.py --no-start # skip start step
  sudo ./deploy_StanleyPark.py --stage ./stage --root / --create-dirs
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Sequence, Tuple
import argparse
import os
import sys
import traceback

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))  # ensure sibling modules importable

# --- lightweight staged-iface discovery (duplicated here to avoid importing internals) ---
def _discover_ifaces_from_stage(stage_root: Path) -> List[str]:
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
      nm = d.name  # wg-quick@IFACE.service.d
      at = nm.find("@")
      dot = nm.find(".service.d")
      if at != -1 and dot != -1 and dot > at:
        names.add(nm[at+1:dot])
  return sorted(names)

def _is_root() -> bool:
  try:
    return os.geteuid() == 0
  except AttributeError:
    # Non-POSIX: best effort
    return False

def _validate_iface_name(n: str) -> bool:
  # conservative: letters, digits, dash, underscore (WireGuard allows more, but keep it safe)
  import re
  return bool(re.fullmatch(r"[A-Za-z0-9_-]{1,32}", n))

def _collect_errors(args) -> Tuple[List[str], List[str]]:
  """
  Return (errors, ifaces). Does *not* raise.
  """
  errors: List[str] = []

  # Root required
  if not _is_root():
    errors.append("must be run as root (sudo)")

  # Stage root
  stage_root = Path(args.stage)
  if not stage_root.exists():
    errors.append(f"stage path does not exist: {stage_root}")

  # Import modules
  inst_mod = None
  stop_mod = None
  start_mod = None
  try:
    import install_staged_tree as inst_mod  # type: ignore
  except Exception as e:
    errors.append(f"failed to import install_staged_tree: {e}")
  try:
    import stop_clean_iface as stop_mod  # type: ignore
  except Exception as e:
    errors.append(f"failed to import stop_clean_iface: {e}")
  try:
    import start_iface as start_mod  # type: ignore
  except Exception as e:
    errors.append(f"failed to import start_iface: {e}")

  # Business functions existence (only if imports worked)
  if inst_mod is not None and not hasattr(inst_mod, "install_staged_tree"):
    errors.append("install_staged_tree module missing function: install_staged_tree")
  if stop_mod is not None and not hasattr(stop_mod, "stop_clean_ifaces"):
    errors.append("stop_clean_iface module missing function: stop_clean_ifaces")
  if start_mod is not None and not hasattr(start_mod, "start_ifaces"):
    errors.append("start_iface module missing function: start_ifaces")

  # Ifaces
  ifaces: List[str]
  if args.ifaces:
    ifaces = list(dict.fromkeys(args.ifaces))  # dedup preserve order
  else:
    ifaces = _discover_ifaces_from_stage(stage_root)
  if not ifaces:
    errors.append("no interfaces provided and none discovered from stage")
  else:
    bad = [n for n in ifaces if not _validate_iface_name(n)]
    if bad:
      errors.append(f"invalid iface name(s): {', '.join(bad)}")

  return (errors, ifaces)

def deploy_StanleyPark(
  ifaces: Sequence[str],
  stage_root: Path,
  dest_root: Path,
  create_dirs: bool,
  skip_identical: bool,
  do_stop: bool,
  do_start: bool,
) -> int:
  """
  Orchestration: stop (optional) → install → start (optional).
  """
  # Late imports so unit tests can monkeypatch easily
  import install_staged_tree as inst
  import stop_clean_iface as stopm
  import start_iface as startm

  print(f"Deploy plan:\n  ifaces: {', '.join(ifaces)}\n  stage: {stage_root}\n  root:  {dest_root}\n")

  # Stop
  if do_stop:
    print(f"Stopping: {' '.join(ifaces)}")
    try:
      stop_logs = stopm.stop_clean_ifaces(ifaces)
      if isinstance(stop_logs, (list, tuple)):
        for line in stop_logs:
          print(line)
    except Exception:
      print("warn: stop_clean_ifaces raised an exception (continuing):")
      traceback.print_exc()

  # Install
  print("\nInstalling staged artifacts…")
  try:
    logs, detected = inst.install_staged_tree(
      stage_root=stage_root,
      dest_root=dest_root,
      create_dirs=create_dirs,
      skip_identical=skip_identical,
    )
    for line in logs:
      print(line)
  except Exception:
    print("❌ install failed with exception:", file=sys.stderr)
    traceback.print_exc()
    return 2

  # Start
  if do_start:
    # Prefer explicit ifaces; fall back to what installer detected
    start_list = list(ifaces) if ifaces else list(detected)
    if not start_list:
      print("\nNo interfaces to start (none detected).")
    else:
      print(f"\nStarting: {' '.join(start_list)}")
      try:
        start_logs = startm.start_ifaces(start_list)
        if isinstance(start_logs, (list, tuple)):
          for line in start_logs:
            print(line)
      except Exception:
        print("warn: start_ifaces raised an exception:", file=sys.stderr)
        traceback.print_exc()
        return 2

  print("\n✓ Deploy complete.")
  return 0

def main(argv: List[str] | None = None) -> int:
  ap = argparse.ArgumentParser(description="Deploy staged WG artifacts for StanleyPark (stop→install→start).")
  ap.add_argument("ifaces", nargs="*", help="interfaces to manage (default: discover from stage)")
  ap.add_argument("--stage", default=str(ROOT / "stage"), help="stage root (default: ./stage)")
  ap.add_argument("--root",  default="/", help="destination root (default: /)")
  ap.add_argument("--create-dirs", action="store_true", help="create missing parent directories")
  ap.add_argument("--no-skip-identical", action="store_true", help="always replace even if content identical")
  ap.add_argument("--no-stop",  action="store_true", help="do not stop interfaces before install")
  ap.add_argument("--no-start", action="store_true", help="do not start interfaces after install")
  args = ap.parse_args(argv)

  # Collect all errors up front
  errors, ifaces = _collect_errors(args)
  if errors:
    print("❌ deploy preflight found issue(s):", file=sys.stderr)
    for e in errors:
      print(f"  - {e}", file=sys.stderr)
    return 2

  # Proceed
  return deploy_StanleyPark(
    ifaces=ifaces,
    stage_root=Path(args.stage),
    dest_root=Path(args.root),
    create_dirs=args.create_dirs,
    skip_identical=(not args.no_skip_identical),
    do_stop=(not args.no_stop),
    do_start=(not args.no_start),
  )

if __name__ == "__main__":
  sys.exit(main())
