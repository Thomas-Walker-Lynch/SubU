# infrastructure/unix.py
# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-

import subprocess, pwd, grp


def run(cmd, check =True):
  """
  Run a Unix command, capturing output.

  Raises RuntimeError if check is True and the command fails.
  """
  r = subprocess.run(
    cmd,
    stdout =subprocess.PIPE,
    stderr =subprocess.PIPE,
    text =True,
  )
  if check and r.returncode != 0:
    raise RuntimeError(f"cmd failed: {' '.join(cmd)}\n{r.stderr}")
  return r


def group_exists(name: str) -> bool:
  try:
    grp.getgrnam(name)
    return True
  except KeyError:
    return False


def user_exists(name: str) -> bool:
  try:
    pwd.getpwnam(name)
    return True
  except KeyError:
    return False


def ensure_unix_group(name: str):
  """
  Ensure a Unix group with this name exists.
  """
  if not group_exists(name):
    run(["groupadd", name])


def ensure_unix_user(name: str, primary_group: str):
  """
  Ensure a Unix user with this name exists and has the given primary group.

  The primary group is made if needed.
  """
  ensure_unix_group(primary_group)
  if not user_exists(name):
    run(["useradd", "-m", "-g", primary_group, "-s", "/bin/bash", name])


def ensure_user_in_group(user: str, group: str):
  """
  Ensure 'user' is a member of supplementary group 'group'.

  No-op if already present.
  """
  if not user_exists(user):
    raise RuntimeError(f"ensure_user_in_group: user '{user}' does not exist")
  if not group_exists(group):
    raise RuntimeError(f"ensure_user_in_group: group '{group}' does not exist")

  g = grp.getgrnam(group)
  if user in g.gr_mem:
    return

  run(["usermod", "-a", "-G", group, user])


def remove_user_from_group(user: str, group: str):
  """
  Ensure 'user' is NOT a member of supplementary group 'group'.

  No-op if user or group is missing, or if user is not a member.
  """
  if not user_exists(user):
    return
  if not group_exists(group):
    return

  g = grp.getgrnam(group)
  if user not in g.gr_mem:
    return

  # gpasswd -d user group is the standard way on Debian/Ubuntu.
  # We treat failures as non-fatal.
  run(["gpasswd", "-d", user, group], check =False)


def remove_unix_user_and_group(name: str):
  """
  Remove a Unix user and group that match this name, if they exist.

  The user is removed first, then the group.
  """
  if user_exists(name):
    run(["userdel", name])
  if group_exists(name):
    run(["groupdel", name])
