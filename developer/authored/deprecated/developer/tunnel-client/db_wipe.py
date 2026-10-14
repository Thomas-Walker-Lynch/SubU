#!/usr/bin/env python3
"""
db_wipe.py

Remove regular (non-directory) files in ./db, keeping the directory.

Safety
- Refuses to run if the target directory does not exist or its basename is not exactly "db".
- Prints a plan, then asks "Are you sure? [y/N]" unless --force is used.
- --dry-run prints what would be removed without deleting.
- Hidden files (names starting with '.') are preserved by default; use --include-hidden to delete them too.

Usage
  ./db_wipe.py                 # plan + prompt, non-hidden files only, ./db next to this script
  ./db_wipe.py --force         # no prompt
  ./db_wipe.py --dry-run       # show what would be deleted
  ./db_wipe.py --include-hidden
  ./db_wipe.py --db /path/to/db
"""

from __future__ import annotations
from pathlib import Path
from typing import Iterable, List, Tuple
import argparse
import sys
import os

# ---------- business ----------

def plan_db_wipe(db_dir: Path, include_hidden: bool = False) -> List[Path]:
    """
    Return a sorted list of file Paths (depth=1) to delete from db_dir.
    """
    if not db_dir.exists():
        raise FileNotFoundError(f"not found: {db_dir}")
    if not db_dir.is_dir():
        raise NotADirectoryError(f"not a directory: {db_dir}")
    if db_dir.name != "db":
        raise RuntimeError(f"expected directory named 'db', got: {db_dir.name}")

    def _is_hidden(p: Path) -> bool:
        return p.name.startswith(".")

    files = [p for p in db_dir.iterdir() if p.is_file()]
    if not include_hidden:
        files = [p for p in files if not _is_hidden(p)]

    # Sort by name for stable output
    return sorted(files, key=lambda p: p.name)


def wipe_db(
    db_dir: Path,
    include_hidden: bool = False,
    dry_run: bool = False,
    assume_yes: bool = False,
    _prompt_fn=input,
) -> Tuple[int, List[str]]:
    """
    Delete planned files from db_dir. Returns (deleted_count, logs).
    Does not prompt if assume_yes=True or dry_run=True.
    """
    targets = plan_db_wipe(db_dir, include_hidden=include_hidden)

    logs: List[str] = []
    script_dir = Path(__file__).resolve().parent

    if not targets:
        logs.append(f"db_wipe: no matching files in: {db_dir.relative_to(script_dir)}")
        return (0, logs)

    logs.append("db_wipe: plan")
    for p in targets:
        # Show path relative to script directory like the original
        rel = p.resolve().relative_to(script_dir)
        logs.append(f"  delete: {rel}")

    if dry_run:
        logs.append("db_wipe: dry-run; no changes made")
        return (0, logs)

    if not assume_yes:
        print("\n".join(logs))
        try:
            ans = _prompt_fn("Are you sure? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans not in ("y", "yes"):
            logs.append("db_wipe: aborted")
            return (0, logs)

    deleted = 0
    for p in targets:
        try:
            p.unlink(missing_ok=True)  # py3.8+: if not available, catch FileNotFoundError
            deleted += 1
        except FileNotFoundError:
            # Equivalent to rm -f
            pass

    rel_db = db_dir.resolve().relative_to(script_dir)
    logs.append(f"db_wipe: deleted {deleted} file(s) from {rel_db}")
    return (deleted, logs)


# ---------- CLI wrapper ----------

def _default_db_dir() -> Path:
    return Path(__file__).resolve().parent / "db"

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Remove regular files in ./db, keeping the directory.")
    ap.add_argument("--db", default=str(_default_db_dir()), help="path to the db directory (default: ./db next to this script)")
    ap.add_argument("--force", action="store_true", help="do not prompt for confirmation")
    ap.add_argument("--dry-run", action="store_true", help="print what would be removed without deleting")
    ap.add_argument("--include-hidden", action="store_true", help="include dotfiles (e.g., .gitignore)")
    args = ap.parse_args(argv)

    db_dir = Path(args.db)

    try:
        deleted, logs = wipe_db(
            db_dir=db_dir,
            include_hidden=args.include_hidden,
            dry_run=args.dry_run,
            assume_yes=args.force or args.dry_run,
        )
        if logs:
            print("\n".join(logs))
        return 0
    except (FileNotFoundError, NotADirectoryError, RuntimeError) as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ unexpected error: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
