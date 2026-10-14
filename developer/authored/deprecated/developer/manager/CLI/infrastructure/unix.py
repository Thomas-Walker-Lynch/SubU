# infrastructure/unix.py
# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-

import os, subprocess, pwd, grp

def _run(cmd: list[str]) -> int:
  return subprocess.run(cmd, check =False).returncode

def user_exists(name: str) -> bool:
  try:
    pwd.getpwnam(name); return True
  except KeyError:
    return False

def group_exists(name: str) -> bool:
  try:
    grp.getgrnam(name); return True
  except KeyError:
    return False

def ensure_group(name: str) -> None:
  if group_exists(name): return
  _run(["groupadd", "--force", name])

def ensure_unix_user(user: str, primary_group: str) -> None:
  """
  Ensure Unix user and primary group exist with matching names.
  """
  ensure_group(primary_group)
  if user_exists(user): return
  # Create with home disabled; your tooling manages home dirs.
  _run([
    "useradd",
    "--create-home",        # harmless if home already bind-mounted later
    "--shell", "/bin/bash",
    "--gid", primary_group,
    user,
  ])

def ensure_user_in_group(user: str, group: str) -> None:
  ensure_group(group)
  # usermod -a -G keeps existing supplementary groups
  _run(["usermod", "-a", "-G", group, user])

def remove_unix_user_and_group(user: str) -> None:
  # Remove user, then drop group if empty
  _run(["userdel", "-r", user])
  if group_exists(user):
    _run(["groupdel", user])

def incommon_set_for_subu(masu: str, parts: list[str]) -> None:
  """
  Grant g+rx on the subu home dir and add all sibling subu users
  under the same owner into this subu's group.
  """
  # Compute Unix names
  owner_group = masu
  subu_user   = "_".join([masu] + parts)
  subu_group  = subu_user
  # Directory path (owner’s subu_data path)
  if not parts:
    return
  home = f"/home/{masu}/subu_data"
  for seg in parts[:-1]:
    home = f"{home}/{seg}/subu_data"
  home = f"{home}/{parts[-1]}"
  # chmod g+rx on the incommon subu home
  _run(["chmod", "g+rx", home])
  # Add all other subu under the owner into this group
  # (simple, local discovery; DB-driven selection is also possible)
  base = f"/home/{masu}/subu_data"
  for entry in os.listdir(base):
    # first-level siblings only; deeper policies can be added later
    u = f"{masu}_{entry}"
    if u == subu_user:  # skip self
      continue
    if user_exists(u):
      ensure_user_in_group(u, subu_group)

def incommon_clear_for_subu(masu: str, parts: list[str]) -> None:
  """
  Revoke g+rx (set back to 700) and drop sibling subu from the group.
  """
  if not parts:
    return
  subu_user  = "_".join([masu] + parts)
  subu_group = subu_user
  home = f"/home/{masu}/subu_data"
  for seg in parts[:-1]:
    home = f"{home}/{seg}/subu_data"
  home = f"{home}/{parts[-1]}"
  _run(["chmod", "0700", home])
  # Remove siblings from the group
  base = f"/home/{masu}/subu_data"
  for entry in os.listdir(base):
    u = f"{masu}_{entry}"
    if u == subu_user:  # skip self
      continue
    if user_exists(u):
      _run(["gpasswd", "-d", u, subu_group])

def mark_device_offline(mapname: str) -> None:
  # reserved for later; actual DB write is done in dispatch.device_detach
  pass

