#!/usr/bin/env python3
"""
start_iface.py

Given:
  - One or more WireGuard interface names (e.g., x6, US).
  - Optional presence of systemd and wg-quick(8).
  - Expected config at /etc/wireguard/<iface>.conf.
  - Optional staged IP state script at /usr/local/bin/apply_ip_state.sh.

Does:
  - For each iface (best-effort, non-fatal steps):
      0) (optional) systemctl daemon-reload
      1) Start via systemd:  systemctl start wg-quick@IFACE.service   (unless --no-systemd)
         else via wg-quick:  wg-quick up IFACE                         (unless --no-wg-quick)
         If the iface already exists and --force is given, it will attempt a
         best-effort teardown then retry the start once.
      2) If started (or already present), optionally run IP state script:
           /usr/local/bin/apply_ip_state.sh IFACE  (unless --skip-ip-state)
  - Logs each action taken or skipped.

Returns:
  - Exit 0 on success (even if some steps were no-ops); 2 on argument/privilege errors.
  - Prints a concise, per-iface action log.

Errors:
  - If no ifaces are provided, or if not running as root (unless --force-nonroot).

Notes:
  - This does NOT edit config files or DB; it just brings the iface up cleanly.
  - Safe to re-run: “already up/exist” conditions are handled. Use --force to
    tear down and recreate if needed.
"""

from __future__ import annotations
from pathlib import Path
from typing import Iterable, List, Sequence
import argparse
import os
import shutil
import subprocess
import sys


# ---------- helpers ----------

def _run(cmd: Sequence[str]) -> tuple[int, str, str]:
  """Run a command, capture stdout/stderr, return (rc, out, err)."""
  try:
    cp = subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return (cp.returncode, cp.stdout.strip(), cp.stderr.strip())
  except FileNotFoundError:
    return (127, "", f"{cmd[0]}: not found")

def _exists_iface(name: str) -> bool:
  rc, _, _ = _run(["ip", "-o", "link", "show", "dev", name])
  return rc == 0

def _systemd_present() -> bool:
  return shutil.which("systemctl") is not None

def _wg_quick_present() -> bool:
  return shutil.which("wg-quick") is not None

def _conf_present(name: str) -> bool:
  return Path(f"/etc/wireguard/{name}.conf").is_file()

def _best_effort_teardown(name: str, logs: List[str]) -> None:
  """Try to bring an iface down using systemd/wg-quick, then delete link; non-fatal."""
  unit = f"wg-quick@{name}.service"
  if _systemd_present():
    rc, out, err = _run(["systemctl", "stop", unit])
    if rc == 0:
      logs.append(f"systemctl: stopped {unit}")
    else:
      logs.append(f"systemctl: stop {unit} (ignored): {err or out or f'rc={rc}'}")
  if _wg_quick_present():
    rc, out, err = _run(["wg-quick", "down", name])
    if rc == 0:
      logs.append("wg-quick: down ok")
    else:
      logs.append(f"wg-quick: down (ignored): {err or out or f'rc={rc}'}")
  if _exists_iface(name):
    rc, out, err = _run(["ip", "link", "del", "dev", name])
    if rc == 0:
      logs.append("ip link: deleted leftover device")
    else:
      logs.append(f"ip link: delete (ignored): {err or out or f'rc={rc}'}")


# ---------- business ----------

def start_ifaces(
  ifaces: Sequence[str],
  use_systemd: bool = True,
  use_wg_quick: bool = True,
  run_ip_state: bool = True,
  ip_state_path: str = "/usr/local/bin/apply_ip_state.sh",
  daemon_reload: bool = False,
  force: bool = False,
) -> List[str]:
  """
  Start the given WG ifaces and optionally apply IP state.
  Returns a list of log lines.
  """
  logs: List[str] = []

  if not ifaces:
    raise RuntimeError("no interfaces provided")

  have_systemd = _systemd_present()
  have_wgquick = _wg_quick_present()
  have_ipstate = Path(ip_state_path).is_file()

  if use_systemd and daemon_reload and have_systemd:
    rc, _out, err = _run(["systemctl", "daemon-reload"])
    if rc == 0:
      logs.append("systemctl: daemon-reload")
    else:
      logs.append(f"systemctl: daemon-reload (ignored): {err or f'rc={rc}'}")

  for name in ifaces:
    logs.append(f"== {name} ==")

    # Ensure config exists
    if not _conf_present(name):
      logs.append(f"config missing: /etc/wireguard/{name}.conf (skip start)")
      logs.append(f"status: absent")
      logs.append("")
      continue

    started = False
    already_present = _exists_iface(name)

    # Optionally force recreate if device already around
    if already_present and force:
      logs.append("iface exists, --force given: tearing down before start")
      _best_effort_teardown(name, logs)
      already_present = _exists_iface(name)

    # Start via systemd or wg-quick
    if use_systemd and have_systemd:
      unit = f"wg-quick@{name}.service"
      rc, out, err = _run(["systemctl", "start", unit])
      if rc == 0:
        logs.append(f"systemctl: started {unit}")
        started = True
      else:
        # If iface already exists, treat as running
        if _exists_iface(name):
          logs.append(f"systemctl: start {unit} reported error, but iface exists (continuing): {err or out or f'rc={rc}'}")
          started = True
        else:
          logs.append(f"systemctl: start {unit} failed: {err or out or f'rc={rc}'}")
    elif use_wg_quick and have_wgquick:
      if already_present:
        logs.append("wg-quick: iface already present")
        started = True
      else:
        rc, out, err = _run(["wg-quick", "up", name])
        if rc == 0:
          logs.append("wg-quick: up ok")
          started = True
        else:
          # If iface popped up anyway, continue
          if _exists_iface(name):
            logs.append(f"wg-quick: up reported error, but iface exists (continuing): {err or out or f'rc={rc}'}")
            started = True
          else:
            logs.append(f"wg-quick: up failed: {err or out or f'rc={rc}'}")

    else:
      logs.append("no start method available (systemd/wg-quick disabled or not found)")

    # If requested, apply IP state post-start (useful when not using systemd drop-ins)
    if run_ip_state and have_ipstate:
      if _exists_iface(name):
        rc, out, err = _run([ip_state_path, name])
        if rc == 0:
          logs.append(f"ip-state: applied ({ip_state_path} {name})")
        else:
          logs.append(f"ip-state: apply failed: {err or out or f'rc={rc}'}")
      else:
        logs.append("ip-state: skipped (iface not present)")

    # Final status
    logs.append(f"status: {'up' if _exists_iface(name) else 'down'}")
    logs.append("")  # spacer

  return logs


# ---------- CLI (wrapper only) ----------

def _require_root(allow_nonroot: bool) -> None:
  if not allow_nonroot and os.geteuid() != 0:
    raise RuntimeError("must run as root (use --force-nonroot to override)")

def main(argv: Sequence[str] | None = None) -> int:
  ap = argparse.ArgumentParser(description="Start one or more WireGuard interfaces safely.")
  ap.add_argument("ifaces", nargs="+", help="interface names to start (e.g., x6 US)")
  ap.add_argument("--no-systemd", action="store_true", help="do not call systemctl start wg-quick@IFACE")
  ap.add_argument("--no-wg-quick", action="store_true", help="do not call wg-quick up IFACE")
  ap.add_argument("--skip-ip-state", action="store_true", help="do not run apply_ip_state.sh after start")
  ap.add_argument("--ip-state-path", default="/usr/local/bin/apply_ip_state.sh", help="path to the IP state script")
  ap.add_argument("--daemon-reload", action="store_true", help="run systemctl daemon-reload before starts")
  ap.add_argument("--force", action="store_true", help="if iface exists, tear down first and retry start")
  ap.add_argument("--force-nonroot", action="store_true", help="allow running without root (best-effort)")
  args = ap.parse_args(argv)

  try:
    _require_root(allow_nonroot=args.force_nonroot)
    logs = start_ifaces(
      args.ifaces,
      use_systemd=(not args.no_systemd),
      use_wg_quick=(not args.no_wg_quick),
      run_ip_state=(not args.skip_ip_state),
      ip_state_path=args.ip_state_path,
      daemon_reload=args.daemon_reload,
      force=args.force,
    )
    for line in logs:
      print(line)
    return 0
  except Exception as e:
    print(f"error: {e}", file=sys.stderr)
    return 2

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
