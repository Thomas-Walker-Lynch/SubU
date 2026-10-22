# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-
"""
account - who the users are, and which are SubUs of which

Until the SubU database exists, the MasU to SubU relation is read from the
account names: a user named <MasU>·<SubU> is a SubU of <MasU>. root is the
MasU of every user whose name has no separator. Everything here only reads
/etc/passwd, so it runs with the privileges of whoever started the tool.

The separator is the middle dot, U+00B7, two bytes in UTF-8. It may not
appear inside a MasU or SubU name, so '_', '-' and '.' stay free for names.

While existing accounts still carry the old separator '_', READ_OLD_SEPARATOR
lets a name without a middle dot be split on its last '_'. Set it to False
once the accounts are renamed; until then, a person account whose own name
contains '_' would be misread as a SubU.
"""

import os ,pwd
from dataclasses import dataclass
from typing import Optional

SEPARATOR = "\u00b7"
OLD_SEPARATOR = "_"
READ_OLD_SEPARATOR = True
FIRST_PERSON_UID = 1000
NOBODY_UID = 65534


@dataclass
class Account:
  name: str
  uid: int
  home: str

  @property
  def home_exists(self) -> bool:
    return os.path.isdir(self.home)


def account(name: str) -> Optional[Account]:
  try:
    entry = pwd.getpwnam(name)
  except KeyError:
    return None
  return Account(entry.pw_name ,entry.pw_uid ,entry.pw_dir)

def acting_account() -> Account:
  entry = pwd.getpwuid(os.getuid())
  return Account(entry.pw_name ,entry.pw_uid ,entry.pw_dir)

def is_person(entry) -> bool:
  return FIRST_PERSON_UID <= entry.pw_uid != NOBODY_UID

def split_name(name: str) -> tuple[str ,str]:
  """
  (MasU ,short name) of an account name. The MasU of a name without a
  separator is root; root itself has no MasU.
  """
  if name == "root":
    return ("" ,"root")
  if SEPARATOR in name:
    masu ,short = name.rsplit(SEPARATOR ,1)
    return (masu ,short)
  if READ_OLD_SEPARATOR and OLD_SEPARATOR in name:
    masu ,short = name.rsplit(OLD_SEPARATOR ,1)
    return (masu ,short)
  return ("root" ,name)

def subu_list(masu: str) -> list[Account]:
  """
  The SubUs of masu: the accounts whose MasU is masu.
  """
  result = []
  for entry in pwd.getpwall():
    if not is_person(entry):
      continue
    if entry.pw_name != masu and split_name(entry.pw_name)[0] == masu:
      result.append(Account(entry.pw_name ,entry.pw_uid ,entry.pw_dir))
  return sorted(result ,key=lambda a: a.name)

def subu_name(masu: str ,short: str) -> str:
  """
  The account name for a new SubU. A short name may not hold the separator.
  """
  if SEPARATOR in short:
    raise ValueError(f"a SubU name may not contain '{SEPARATOR}': {short}")
  if masu == "root":
    return short
  return masu + SEPARATOR + short

def masu_of(name: str) -> str:
  return split_name(name)[0]

def short_name(name: str) -> str:
  return split_name(name)[1]


# --------------------------------------------------------------------------------
# state

STATE_LOGGED_IN = "logged in"
STATE_LOGGED_OUT = "logged out"
STATE_OFFLINE = "offline"

def session_uid_set() -> set[int]:
  """
  The uids that have at least one login session, as systemd-logind counts
  them: a desktop login, a console login, or a machinectl shell. A user
  whose services linger with no session open is not counted. Empty when
  loginctl cannot be run.
  """
  import subprocess
  try:
    result = subprocess.run(["loginctl" ,"list-sessions" ,"--no-legend"],
      capture_output=True ,text=True ,timeout=5)
  except (OSError ,subprocess.TimeoutExpired):
    return set()
  uid_set = set()
  for line in result.stdout.splitlines():
    field = line.split()
    if len(field) >= 2 and field[1].isdigit():
      uid_set.add(int(field[1]))
  return uid_set

def state(user: Account ,session_uids: set[int]) -> str:
  """
  logged in   the user has a login session
  logged out  no session, and the home directory is here
  offline     no session, and the home directory is not here: it lives on a
              storage that is not attached
  """
  if user.uid in session_uids:
    return STATE_LOGGED_IN
  if not user.home_exists:
    return STATE_OFFLINE
  return STATE_LOGGED_OUT
