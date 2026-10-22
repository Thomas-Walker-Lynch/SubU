# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-
"""
common - what the work modules of SubU_admin share: the log, running a
command, reading accounts and mounts, and checking names and paths.

Each work function is given a log and a preview flag. Everything a function
does is decided the same way in a preview; the flag is tested only where a
change is made: a database transaction is rolled back, and a command that
would change the system is logged and not run.
"""

import re ,pwd ,grp ,socket ,subprocess
from pathlib import Path

HOME = Path("/home")
SEPARATOR = "·"
RESERVED_NAME = {"SubU"}


class Log:
  TAG_WIDTH = 22

  # the tag a preview prints for each action tag
  PREVIEW_TAG = {
    "made": "would make" ,"recorded": "would record" ,"mounted": "would mount",
    "unmounted": "would unmount" ,"adopted": "would adopt" ,"made account": "would make account",
    "set": "would set" ,"deleted": "would delete" ,"deleted account": "would delete account",
    "deleted group": "would delete group" ,"retired": "would retire" ,"mapped": "would map",
  }

  def __init__(self ,preview):
    self.preview = preview
    self.count = {}
    self.error_count = 0

  def line(self ,tag ,subject ,reason=None):
    self.count[tag] = self.count.get(tag ,0) + 1
    if self.preview:
      tag = self.PREVIEW_TAG.get(tag ,tag)
    text = f"  {tag:<{self.TAG_WIDTH}}{subject}"
    if reason: text += f"  ({reason})"
    print(text)

  def error(self ,subject ,reason):
    self.error_count += 1
    print(f"  {'error':<{self.TAG_WIDTH}}{subject}  ({reason})")

  def summary(self):
    print("summary:")
    for tag ,n in sorted(self.count.items()):
      if self.preview: tag = self.PREVIEW_TAG.get(tag ,tag)
      print(f"  {n:>4}  {tag}")
    if self.error_count:
      print(f"  {self.error_count:>4}  errors")
    if self.preview:
      print("preview only: nothing was changed.")
    return 1 if self.error_count else 0


def run(command ,log ,preview):
  """
  Run a command that changes the system; in a preview, only show it.
  """
  if preview:
    return True
  result = subprocess.run(command ,capture_output=True ,text=True)
  if result.returncode != 0:
    log.error(" ".join(command) ,result.stderr.strip() or f"exit {result.returncode}")
    return False
  return True

def host_name() -> str:
  return socket.gethostname()

def account(name):
  try:
    return pwd.getpwnam(name)
  except KeyError:
    return None

def account_by_system_uid(system_uid):
  try:
    return pwd.getpwuid(system_uid)
  except KeyError:
    return None

def group(name):
  try:
    return grp.getgrnam(name)
  except KeyError:
    return None

def login_defs_value(key ,default):
  try:
    for line in Path("/etc/login.defs").read_text(encoding="utf-8").splitlines():
      field = line.split()
      if len(field) >= 2 and field[0] == key and field[1].isdigit():
        return int(field[1])
  except OSError:
    pass
  return default

def uid_min() -> int:
  """
  The lowest uid of a person's account on this system; below it are the
  accounts of the system's own services.
  """
  return login_defs_value("UID_MIN" ,1000)

def is_mountpoint(path):
  return subprocess.run(["mountpoint" ,"-q" ,str(path)]).returncode == 0

def mount_point_list():
  """
  Every mount point on the system, from /proc/self/mountinfo, where a space
  and a few other characters in a path are written as three-digit octal escapes.
  """
  result = []
  for line in Path("/proc/self/mountinfo").read_bytes().split(b"\n"):
    field = line.split(b" ")
    if len(field) > 4:
      raw = re.sub(rb"\\([0-7]{3})" ,lambda m: bytes([int(m.group(1) ,8)]) ,field[4])
      result.append(raw.decode("utf-8" ,"replace"))
  return result

def session_system_uids():
  result = subprocess.run(["loginctl" ,"list-sessions" ,"--no-legend"] ,capture_output=True ,text=True)
  system_uid_set = set()
  for line in result.stdout.splitlines():
    field = line.split()
    if len(field) >= 2 and field[1].isdigit():
      system_uid_set.add(int(field[1]))
  return system_uid_set

def valid_name(name):
  if not name or len(name.encode("utf-8")) > 32:
    return "a user name is 1 to 32 bytes"
  if any(c in name for c in "/: \t\n") or name.startswith(("-" ,SEPARATOR)) or name.endswith(SEPARATOR):
    return "a user name may not contain '/', ':' or spaces, nor start with '-' or begin or end with '·'"
  if SEPARATOR * 2 in name:
    return "a user name may not contain an empty short name"
  if name in RESERVED_NAME:
    return f"'{name}' is reserved: /home/{name} holds SubU's own files"
  return None

def subu_dir_problem(subu_dir):
  """
  A SubU dir is <storage root>/home/SubU; every storage keeps the same layout.
  """
  path = Path(subu_dir)
  if path.name != "SubU" or path.parent.name != "home":
    return f"{subu_dir} is not a SubU dir; a SubU dir is <storage root>/home/SubU, such as /home/SubU"
  return None

def delete_mount_point(target ,log ,preview):
  """
  Delete a mount point only when it is one attach made: an empty directory
  owned by root, mode 0000. In a preview a home still mounted over it hides
  it, so the real run makes the check.
  """
  if not target.exists():
    return
  if preview and is_mountpoint(target):
    log.line("deleted" ,str(target) ,"mount point, once unmounted, if attach made it")
    return
  st = target.lstat()
  if is_mountpoint(target) or not target.is_dir() or st.st_uid != 0 or (st.st_mode & 0o7777) != 0 or any(target.iterdir()):
    log.line("kept" ,str(target) ,"not an empty mount point made by attach")
    return
  if not preview:
    subprocess.run(["chattr" ,"-i" ,str(target)] ,capture_output=True)
    target.rmdir()
  log.line("deleted" ,str(target) ,"mount point")
