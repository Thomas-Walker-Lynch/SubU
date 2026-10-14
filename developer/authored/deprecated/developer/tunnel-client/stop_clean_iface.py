#!/usr/bin/env python3
"""
stop_clean_iface.py

Stop one or more WireGuard interfaces and clean IP state (rules/routes/addresses).
"""

from __future__ import annotations
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Set
import argparse
import os
import re
import shutil
import subprocess
import sys

__VERSION__ = "1.1-agg-errors"

RT_TABLES_FILE = Path("/etc/iproute2/rt_tables")

# ---------- helpers (shell) ----------

def _run(cmd: Sequence[str], dry: bool=False) -> tuple[int, str, str]:
  if dry:
    return (0, "", "")
  try:
    cp = subprocess.run(cmd, check=False, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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

# ---------- helpers (routing tables & rules) ----------

def _rt_table_num_for_name(name: str) -> Optional[int]:
  if not RT_TABLES_FILE.exists():
    return None
  try:
    text = RT_TABLES_FILE.read_text()
  except Exception:
    return None
  for line in text.splitlines():
    s = line.strip()
    if not s or s.startswith("#"):
      continue
    parts = s.split()
    if len(parts) >= 2 and parts[0].isdigit():
      num = int(parts[0]); nm = parts[1]
      if nm == name:
        return num
  return None

_RULE_RE = re.compile(r"""^\s*(\d+):\s*(.+?)\s*$""")

def _current_rule_lines() -> List[Tuple[int,str]]:
  rc, out, _ = _run(["ip", "-4", "rule", "show"])
  if rc != 0 or not out:
    return []
  rows: List[Tuple[int,str]] = []
  for ln in out.splitlines():
    m = _RULE_RE.match(ln)
    if not m:
      continue
    pref = int(m.group(1))
    rest = m.group(2)
    rows.append((pref, rest))
  return rows

def _prefs_matching_lookups(lookups: Sequence[str]) -> Set[int]:
  toks = [t for t in lookups if t]
  prefs: Set[int] = set()
  if not toks:
    return prefs
  for pref, rest in _current_rule_lines():
    for t in toks:
      if re.search(rf"\blookup\s+{re.escape(t)}\b", rest):
        prefs.add(pref)
        break
  return prefs

def _rule_del_by_pref(pref: int, logs: List[str], dry: bool) -> None:
  rc, _out, err = _run(["ip", "-4", "rule", "del", "pref", str(pref)], dry=dry)
  if rc == 0:
    logs.append(f"ip rule: deleted pref {pref}")
  else:
    logs.append(f"ip rule: delete pref {pref} (ignored): {err or f'rc={rc}'}")

def _flush_routes_for_table(table: str, logs: List[str], dry: bool) -> None:
  rc, _out, err = _run(["ip", "-4", "route", "flush", "table", table], dry=dry)
  if rc == 0:
    logs.append(f"ip route: flushed table {table}")
  else:
    logs.append(f"ip route: flush table {table} (ignored): {err or f'rc={rc}'}")

def _addr_del_all_v4_on_iface(iface: str, logs: List[str], dry: bool) -> None:
  rc, out, err = _run(["ip", "-4", "-o", "addr", "show", "dev", iface], dry=dry)
  if rc != 0:
    logs.append(f"ip addr: list on {iface} (ignored): {err or f'rc={rc}'}")
    return
  cidrs: List[str] = []
  for ln in out.splitlines():
    parts = ln.split()
    if len(parts) >= 4:
      cidrs.append(parts[3])
  if not cidrs:
    logs.append("ip addr: none to remove")
    return
  for cidr in cidrs:
    rc2, _o2, e2 = _run(["ip", "-4", "addr", "del", cidr, "dev", iface], dry=dry)
    if rc2 == 0:
      logs.append(f"ip addr: deleted {cidr}")
    else:
      logs.append(f"ip addr: delete {cidr} (ignored): {e2 or f'rc={rc2}'}")

# ---------- business ----------

def _clean_iface_ip_state(name: str, logs: List[str], *, dry: bool=False, aggressive: bool=False) -> None:
  tokens: List[str] = [name]
  num = _rt_table_num_for_name(name)
  if num is not None:
    tokens.append(str(num))

  # Delete rules matching either numeric or named lookup tokens; loop to catch chains.
  deleted_any = True
  safety = 0
  while deleted_any and safety < 10:
    safety += 1
    prefs = sorted(_prefs_matching_lookups(tokens))
    if not prefs:
      deleted_any = False
      break
    for p in prefs:
      _rule_del_by_pref(p, logs, dry)
  if aggressive:
    for p in range(17000, 17060):
      _rule_del_by_pref(p, logs, dry)

  # Flush routes in the table by name and numeric (if known)
  _flush_routes_for_table(name, logs, dry)
  if num is not None:
    _flush_routes_for_table(str(num), logs, dry)

  # Remove all IPv4 addresses on the iface
  _addr_del_all_v4_on_iface(name, logs, dry)

def stop_clean_ifaces(
  ifaces: Sequence[str],
  use_systemd: bool = True,
  use_wg_quick: bool = True,
  do_clean: bool = True,
  aggressive: bool = False,
  dry_run: bool = False,
) -> List[str]:
  logs: List[str] = []
  if not ifaces:
    raise RuntimeError("no interfaces provided")

  have_systemd = _systemd_present()
  have_wgquick = _wg_quick_present()

  for name in ifaces:
    logs.append(f"== {name} ==")

    if use_systemd and have_systemd:
      unit = f"wg-quick@{name}.service"
      rc, out, err = _run(["systemctl", "stop", unit], dry=dry_run)
      if rc == 0:
        logs.append(f"systemctl: stopped {unit}")
      else:
        msg = err or out or f"rc={rc}"
        logs.append(f"systemctl: stop {unit} (ignored): {msg}")
    elif use_systemd and not have_systemd:
      logs.append("systemctl: not found; skipped")

    if use_wg_quick and have_wgquick:
      rc, out, err = _run(["wg-quick", "down", name], dry=dry_run)
      if rc == 0:
        logs.append("wg-quick: down ok")
      else:
        msg = err or out or f"rc={rc}"
        logs.append(f"wg-quick: down (ignored): {msg}")
    elif use_wg_quick and not have_wgquick:
      logs.append("wg-quick: not found; skipped")

    if do_clean:
      _clean_iface_ip_state(name, logs, dry=dry_run, aggressive=aggressive)
    else:
      logs.append("clean: skipped (--no-clean)")

    if _exists_iface(name):
      rc, out, err = _run(["ip", "link", "del", "dev", name], dry=dry_run)
      if rc == 0:
        logs.append("ip link: deleted device")
      else:
        msg = err or out or f"rc={rc}"
        logs.append(f"ip link: delete (ignored): {msg}")
    else:
      logs.append("ip link: device not present; nothing to delete")

    final_present = _exists_iface(name)
    logs.append(f"status: {'gone' if not final_present else 'still present'}")
    logs.append("")

  return logs

# ---------- CLI (wrapper with aggregated errors) ----------

def main(argv: Sequence[str] | None = None) -> int:
  ap = argparse.ArgumentParser(
    description="Stop one or more WireGuard interfaces and clean IP state.",
    add_help=True)
  ap.add_argument("ifaces", nargs="*", help="interface names to stop (e.g., x6 US)")
  ap.add_argument("--no-systemd", action="store_true", help="do not call systemctl stop wg-quick@IFACE")
  ap.add_argument("--no-wg-quick", action="store_true", help="do not call wg-quick down IFACE")
  ap.add_argument("--no-clean", action="store_true", help="skip IP cleanup (rules/routes/addresses)")
  ap.add_argument("--aggressive", action="store_true", help="also purge common rule pref window (17000-17059)")
  ap.add_argument("--dry-run", action="store_true", help="print what would be done without changing state")
  ap.add_argument("--force-nonroot", action="store_true", help="allow running without root (best-effort)")

  args = ap.parse_args(argv)

  # Aggregate invocation errors
  errors: List[str] = []
  if os.geteuid() != 0 and not args.force_nonroot:
    errors.append("must run as root (use --force-nonroot to override)")
  if not args.ifaces:
    errors.append("no interfaces provided")

  if errors:
    sys.stderr.write(ap.format_usage())
    prog = Path(sys.argv[0]).name or "stop_clean_iface.py"
    sys.stderr.write(f"{prog}: error: " + "; ".join(errors) + "\n")
    return 2

  try:
    logs = stop_clean_ifaces(
      args.ifaces,
      use_systemd=(not args.no_systemd),
      use_wg_quick=(not args.no_wg_quick),
      do_clean=(not args.no_clean),
      aggressive=args.aggressive,
      dry_run=args.dry_run,
    )
    for line in logs:
      print(line)
    return 0
  except Exception as e:
    print(f"error: {e}", file=sys.stderr)
    return 2

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
