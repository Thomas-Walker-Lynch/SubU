#!/usr/bin/env python3
"""
stage_client.py

Given:
  - A SQLite DB via incommon.open_db()
  - A client machine name (for WG PrivateKey lookup under ./key/<client>)
  - One or more interface names (e.g., x6, US)

Does:
  1) Stage WireGuard confs for each iface
  2) Stage a unified IP apply script (addresses, routes, rules) + per-iface drop-ins

Returns:
  True on success, False on failure (prints progress)
"""

from __future__ import annotations
from pathlib import Path
from typing import Callable ,Optional ,Sequence ,Tuple
import argparse
import subprocess
import sys

import incommon as ic  # open_db()

ROOT = Path(__file__).resolve().parent
STAGE_ROOT = ROOT / "stage"


def _msg_wrapped_call(label: str ,fn: Callable[[], Tuple[Path ,Sequence[str]]]) -> bool:
  print(f"→ {label}")
  try:
    path ,notes = fn()
    for n in notes:
      print(n)
    if path:
      print(f"✔ {label}: staged: {path}")
    else:
      print(f"✔ {label}")
    return True
  except Exception as e:
    print(f"❌ {label}: {e}")
    return False


def _call_cli(argv: Sequence[str]) -> Tuple[Path ,Sequence[str]]:
  cp = subprocess.run(list(argv) ,text=True ,capture_output=True)
  if cp.returncode != 0:
    raise RuntimeError(cp.stderr.strip() or f"exit {cp.returncode}")
  notes = []
  staged_path: Optional[Path] = None
  for line in (cp.stdout or "").splitlines():
    notes.append(line)
    if line.startswith("staged: "):
      try:
        staged_path = Path(line.split("staged:",1)[1].strip())
      except Exception:
        pass
  return (staged_path or STAGE_ROOT ,notes)


def _stage_wg_conf_step(client_name: str ,ifaces: Sequence[str]) -> bool:
  def _do():
    try:
      from stage_wg_conf import stage_wg_conf  # type: ignore
      with ic.open_db() as conn:
        path ,notes = stage_wg_conf(
           conn
          ,ifaces
          ,client_name
          ,stage_root=STAGE_ROOT
          ,dry_run=False
        )
      return (path ,notes)
    except Exception:
      return _call_cli([str(ROOT / "stage_wg_conf.py") ,client_name ,*ifaces])
  return _msg_wrapped_call(f"stage_wg_conf ({client_name}; {','.join(ifaces)})" ,_do)


def _stage_apply_ip_state_step(ifaces: Sequence[str]) -> bool:
  def _do():
    try:
      from stage_IP_apply_script import stage_ip_apply_script  # type: ignore
      with ic.open_db() as conn:
        path ,notes = stage_ip_apply_script(
           conn
          ,ifaces
          ,stage_root=STAGE_ROOT
          ,script_name="apply_ip_state.sh"
          ,only_on_up=True
          ,dry_run=False
        )
      return (path ,notes)
    except Exception:
      return _call_cli([str(ROOT / "stage_IP_apply_script.py") ,*ifaces])
  return _msg_wrapped_call(f"stage_IP_apply_script ({','.join(ifaces)})" ,_do)


def stage_client_artifacts(
   client_name: str
  ,iface_names: Sequence[str]
  ,stage_root: Optional[Path] = None
) -> bool:
  if not iface_names:
    raise ValueError("no interfaces provided")
  if stage_root:
    global STAGE_ROOT
    STAGE_ROOT = stage_root

  STAGE_ROOT.mkdir(parents=True ,exist_ok=True)

  ok = True
  ok = _stage_wg_conf_step(client_name ,iface_names) and ok
  ok = _stage_apply_ip_state_step(iface_names) and ok
  return ok


def main(argv: Optional[Sequence[str]] = None) -> int:
  ap = argparse.ArgumentParser(description="Stage all artifacts for a client.")
  ap.add_argument("--client" ,required=True ,help="client machine name (for key lookup)")
  ap.add_argument("ifaces" ,nargs="+")
  args = ap.parse_args(argv)

  ok = stage_client_artifacts(
     args.client
    ,args.ifaces
  )
  return 0 if ok else 2


if __name__ == "__main__":
  sys.exit(main())
