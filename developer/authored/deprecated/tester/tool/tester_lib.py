#!/usr/bin/env -S python3 -B
# tester_lib.py — shared helpers for tester tools

import os, sys, subprocess
from dataclasses import dataclass
from typing import List, Tuple, Optional


DEV_BRANCH = "core_developer_branch"
TEST_CORE_BRANCH = "core_tester_branch"
RELEASE_PREFIX = "release_"
RELEASE_TEST_PREFIX = "release_tester_"

TESTER_ROOT_REL = "tester"
DEVELOPER_ROOT_REL = "developer"
RELEASE_ROOT_REL = "release"


class BranchKind:
  CORE_DEV = "core_developer"
  CORE_TEST = "core_tester"
  RELEASE = "release"
  RELEASE_TEST = "release_tester"
  OTHER = "other"


@dataclass
class BranchInfo:
  name: str
  kind: str
  major: Optional[int] = None
  minor: Optional[int] = None


def _run_git(args, capture_output=True, check=True) -> subprocess.CompletedProcess:
  cmd = ["git"] + list(args)
  if capture_output:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)
  return subprocess.run(cmd, text=True, check=check)


def get_repo_root() -> str:
  rh = os.environ.get("REPO_HOME")
  if rh:
    return os.path.abspath(rh)
  try:
    cp = _run_git(["rev-parse", "--show-toplevel"])
    return cp.stdout.strip()
  except Exception as e:
    print(f"tester_lib: cannot determine repo root: {e}", file=sys.stderr)
    sys.exit(1)


def chdir_repo_root() -> str:
  root = get_repo_root()
  os.chdir(root)
  return root


def get_current_branch() -> str:
  cp = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
  return cp.stdout.strip()


def _parse_version_from_name(name: str, prefix: str) -> Optional[Tuple[int, int]]:
  """
  Parse branch names like:
    prefix + "<major>" or prefix + "<major>.<minor>"

  Returns (major, minor) with minor defaulting to 0 if absent.
  """
  if not name.startswith(prefix):
    return None
  tail = name[len(prefix):]
  if not tail:
    return None
  if "." in tail:
    major_s, minor_s = tail.split(".", 1)
  else:
    major_s, minor_s = tail, "0"
  try:
    major = int(major_s)
    minor = int(minor_s)
  except ValueError:
    return None
  return (major, minor)


def classify_branch(name: str) -> BranchInfo:
  if name == DEV_BRANCH:
    return BranchInfo(name=name, kind=BranchKind.CORE_DEV)
  if name == TEST_CORE_BRANCH:
    return BranchInfo(name=name, kind=BranchKind.CORE_TEST)

  v = _parse_version_from_name(name, RELEASE_PREFIX)
  if v is not None:
    major, minor = v
    return BranchInfo(name=name, kind=BranchKind.RELEASE, major=major, minor=minor)

  v = _parse_version_from_name(name, RELEASE_TEST_PREFIX)
  if v is not None:
    major, minor = v
    return BranchInfo(name=name, kind=BranchKind.RELEASE_TEST, major=major, minor=minor)

  return BranchInfo(name=name, kind=BranchKind.OTHER)


def is_testing_branch(name: str) -> bool:
  info = classify_branch(name)
  return info.kind in (BranchKind.CORE_TEST, BranchKind.RELEASE_TEST)


def get_release_tester_branches() -> List[BranchInfo]:
  cp = _run_git(["branch", "--list", f"{RELEASE_TEST_PREFIX}*"])
  branches: List[BranchInfo] = []
  for line in cp.stdout.splitlines():
    line = line.strip()
    if not line:
      continue
    if line.startswith("* "):
      line = line[2:]
    info = classify_branch(line)
    if info.kind == BranchKind.RELEASE_TEST and info.major is not None:
      branches.append(info)
  return branches


def get_release_branches() -> List[BranchInfo]:
  cp = _run_git(["branch", "--list", f"{RELEASE_PREFIX}*"])
  branches: List[BranchInfo] = []
  for line in cp.stdout.splitlines():
    line = line.strip()
    if not line:
      continue
    if line.startswith("* "):
      line = line[2:]
    info = classify_branch(line)
    if info.kind == BranchKind.RELEASE and info.major is not None:
      branches.append(info)
  return branches


def choose_latest_release(branches: List[BranchInfo]) -> Optional[BranchInfo]:
  if not branches:
    return None
  sorted_br = sorted(
    branches,
    key=lambda b: (b.major if b.major is not None else -1,
                   b.minor if b.minor is not None else -1)
  )
  return sorted_br[-1]


def choose_latest_release_tester(branches: List[BranchInfo]) -> Optional[BranchInfo]:
  return choose_latest_release(branches)


def corresponding_developer_branch(test_branch: str) -> Optional[str]:
  info = classify_branch(test_branch)
  if info.kind == BranchKind.CORE_TEST:
    return DEV_BRANCH
  if info.kind == BranchKind.RELEASE_TEST and info.major is not None:
    if info.minor and info.minor != 0:
      return f"{RELEASE_PREFIX}{info.major}.{info.minor}"
    return f"{RELEASE_PREFIX}{info.major}"
  return None


def get_developer_ref_for_merge(test_branch: str) -> Optional[str]:
  dev_branch = corresponding_developer_branch(test_branch)
  if not dev_branch:
    return None
  return f"origin/{dev_branch}"


def get_upstream_ref_for_current_branch() -> Optional[str]:
  try:
    cp = _run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
  except subprocess.CalledProcessError:
    return None
  return cp.stdout.strip()


def git_diff_name_status(from_ref: str, to_ref: str, paths: Optional[List[str]] = None) -> List[Tuple[str, str]]:
  args = ["diff", "--name-status", f"{from_ref}..{to_ref}"]
  if paths:
    args.append("--")
    args.extend(paths)
  cp = _run_git(args)
  out: List[Tuple[str, str]] = []
  for line in cp.stdout.splitlines():
    if not line.strip():
      continue
    parts = line.split("\t", 1)
    if len(parts) != 2:
      continue
    status, path = parts
    out.append((status.strip(), path.strip()))
  return out


def list_executable_flags(paths: List[str], repo_root: str) -> List[str]:
  exec_paths: List[str] = []
  for p in paths:
    fs_path = os.path.join(repo_root, p)
    if os.path.exists(fs_path) and os.access(fs_path, os.X_OK):
      exec_paths.append(p)
  return exec_paths


def print_changes_with_exec_marker(changes: List[Tuple[str, str]], repo_root: str) -> None:
  if not changes:
    print("  (no changes)")
    return
  paths = [p for _s, p in changes]
  execs = set(list_executable_flags(paths, repo_root))
  for status, path in changes:
    mark = " [EXEC]" if path in execs else ""
    print(f"  {status}\t{path}{mark}")


def prompt_yes_no(msg: str, default: bool = False) -> bool:
  suffix = "[y/N]" if not default else "[Y/n]"
  while True:
    ans = input(f"{msg} {suffix} ").strip().lower()
    if not ans:
      return default
    if ans in ("y", "yes"):
      return True
    if ans in ("n", "no"):
      return False
    print("Please answer y or n.")


def is_under_tester_tree(rel_path: str) -> bool:
  parts = rel_path.split(os.sep)
  return bool(parts) and parts[0] == TESTER_ROOT_REL


def changes_outside_tester(changes: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
  return [(s, p) for (s, p) in changes if not is_under_tester_tree(p)]


def fetch_remote(remote: str = "origin") -> None:
  _run_git(["fetch", remote], capture_output=False, check=True)


def ensure_on_testing_branch_or_die() -> BranchInfo:
  name = get_current_branch()
  info = classify_branch(name)
  if info.kind not in (BranchKind.CORE_TEST, BranchKind.RELEASE_TEST):
    print(f"Error: current branch '{name}' is not a testing branch (core_tester or release_tester_*).", file=sys.stderr)
    sys.exit(1)
  return info
