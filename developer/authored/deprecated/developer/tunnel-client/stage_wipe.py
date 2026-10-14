#!/usr/bin/env python3
# stage_wipe.py — safely wipe ./stage (keeps hidden files unless --hard)

from __future__ import annotations
import argparse, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGE_ROOT = ROOT / "stage"

def wipe_stage(*, yes: bool=False, dry_run: bool=False, hard: bool=False) -> int:
  """Given flags, deletes staged output. Keeps dotfiles unless hard=True."""
  st = STAGE_ROOT
  if not st.exists():
    print(f"Nothing to wipe: {st} does not exist.")
    return 0

  # safety: only operate on ./stage relative to this repo folder
  if st.resolve() != (ROOT / "stage").resolve():
    print(f"Refusing: unsafe STAGE path: {st}", file=sys.stderr)
    return 1

  # quick stats
  try:
    count = sum(1 for _ in st.rglob("*"))
  except Exception:
    count = 0

  if dry_run:
    print(f"DRY RUN — would wipe: {st} (items: {count})")
    for p in sorted(st.iterdir()):
      print(f"  {p.name}")
    return 0

  if not yes:
    try:
      ans = input(f"Permanently delete contents of {st}? [y/N] ").strip()
    except EOFError:
      ans = ""
    if ans.lower() not in ("y","yes"):
      print("Aborted.")
      return 0

  if hard:
    shutil.rmtree(st, ignore_errors=True)
    print(f"Removed stage dir: {st}")
  else:
    # remove non-hidden entries only; keep dotfiles (e.g. .gitignore)
    for p in st.iterdir():
      if p.name.startswith("."):
        continue  # preserve hidden entries
      try:
        if p.is_dir():
          shutil.rmtree(p, ignore_errors=True)
        else:
          p.unlink(missing_ok=True)
      except Exception:
        pass
    print(f"Cleared contents of: {st} (hidden files preserved)")
  return 0

def main(argv):
  ap = argparse.ArgumentParser()
  ap.add_argument("--yes", action="store_true", help="do not prompt")
  ap.add_argument("--dry-run", action="store_true", help="show what would be removed")
  ap.add_argument("--hard", action="store_true", help="remove the stage dir itself")
  args = ap.parse_args(argv)
  return wipe_stage(yes=args.yes, dry_run=args.dry_run, hard=args.hard)

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
