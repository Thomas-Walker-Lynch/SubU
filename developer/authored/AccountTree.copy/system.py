# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-
"""
system - the work functions for the system database

The system database, /var/lib/SubU/system.sqlite3, is this system's own record:
its system uuid, the range of system uids SubU gives out, the system map of
accounts that are the same users as users of storage databases, and the
limits on how many SubUs each account may make.
"""

import os
from pathlib import Path

import database
from database import Database ,DatabaseError
from common import host_name ,account_by_system_uid ,account

DEFAULT_SYSTEM_UID_FIRST = 2000
DEFAULT_SYSTEM_UID_LAST = 59999
# the lowest database uid, the floor of the band storage databases count down in
DATABASE_UID_FLOOR = 1_879_048_192


def open_system_database(log):
  """
  This system's database, or None with an error logged when there is none.
  """
  if not database.SYSTEM_DATABASE_PATH.is_file():
    log.error("system" ,f"no system database at {database.SYSTEM_DATABASE_PATH}; run 'system make' first")
    return None
  return Database.open(database.SYSTEM_DATABASE_PATH ,"system")


def system_make(system_uid_first ,system_uid_last ,log ,preview):
  path = database.SYSTEM_DATABASE_PATH
  if system_uid_last >= DATABASE_UID_FLOOR:
    log.error("system uid range" ,f"the range reaches {DATABASE_UID_FLOOR}, where database uids begin"); return
  if system_uid_first > system_uid_last:
    log.error("system uid range" ,f"{system_uid_first} is above {system_uid_last}"); return
  if path.exists():
    db = Database.open(path ,"system")
    log.line("kept" ,str(path) ,f"a system database exists, system uuid {db.uuid()}")
    return
  if not database.SYSTEM_DIR.is_dir():
    if not preview:
      database.SYSTEM_DIR.mkdir(mode=0o700 ,parents=True)
      os.chmod(database.SYSTEM_DIR ,0o700)
    log.line("made" ,str(database.SYSTEM_DIR) ,"root only, mode 0700")
  db = Database.make(path ,"system" ,preview)
  with db.transaction("set system uid range" ,preview) as t:
    t.execute("INSERT INTO system_uid_range(first ,last) VALUES (? ,?)" ,(system_uid_first ,system_uid_last))
  # a system uuid is drawn at random; the one drawn in a preview is thrown away
  log.line("made" ,str(path) ,"a new system uuid" if preview else f"system uuid {db.uuid()}")
  log.line("recorded" ,"system uid range" ,f"{system_uid_first} to {system_uid_last}")

def system_show():
  path = database.SYSTEM_DATABASE_PATH
  db = Database.open(path ,"system")
  d = db.identity()
  r = db.row("SELECT * FROM system_uid_range")
  print(f"system    {host_name()}  system uuid {d['system_uuid']}")
  print(f"file      {path}")
  print(f"series    {d['series']}  head {d['head_hash'][:16]}")
  print(f"made      {d['created']}")
  print(f"changed   {db.last_change()}")
  print("standard  " + " ".join(s["version"] for s in db.rows("SELECT version FROM standard")))
  print(f"range     system uids {r['first']} to {r['last']}")
  print("system map")
  for m in db.rows("SELECT * FROM system_map ORDER BY state ,system_uid"):
    entry = account_by_system_uid(m["system_uid"])
    present = "  (account missing)" if m["state"] == "in use" and not (entry and entry.pw_name == m["account_name"]) else ""
    print(f"  {m['account_name']:<26}system uid {m['system_uid']:<7}{m['account']:<8}{m['state']:<8}"
          f"database {m['database_uuid'][:8]} database uid {m['database_uid']}{present}")
  limit_row = db.rows("SELECT * FROM user_limit ORDER BY system_uid")
  if limit_row:
    print("limits")
    for l in limit_row:
      entry = account_by_system_uid(l["system_uid"])
      who = entry.pw_name if entry else f"system uid {l['system_uid']}"
      print(f"  {who:<26}{l['maximum']}")
  problem = db.verify()
  print("verify    " + ("ok" if not problem else "; ".join(problem)))
  return 1 if problem else 0

def system_delete(log ,preview):
  """
  Delete the system database. Refused while its system map has any row in
  use: those accounts would be left with no record, and their system uids
  could be given out again.
  """
  path = database.SYSTEM_DATABASE_PATH
  if not path.exists():
    log.line("kept" ,str(path) ,"no system database here; nothing to delete"); return
  db = Database.open(path ,"system")
  in_use = db.rows("SELECT * FROM system_map WHERE state = 'in use' ORDER BY account_name")
  if in_use:
    for m in in_use:
      log.error(str(path) ,f"{m['account_name']} is still the same user as database uid {m['database_uid']}"
                f" of database {m['database_uuid'][:8]}; run is-not-same-user, or storage delete, first")
    log.line("kept" ,str(path) ,"nothing was changed")
    return
  db.close()
  for entry in sorted(path.parent.iterdir()):
    if entry.name.startswith("system.sqlite3"):
      if not preview: entry.unlink()
      log.line("deleted" ,str(entry))
  if not preview and not any(path.parent.iterdir()):
    path.parent.rmdir()
    log.line("deleted" ,str(path.parent))
  elif preview:
    log.line("deleted" ,str(path.parent) ,"when nothing else is in it")

def limit_set(account_name ,maximum ,log ,preview):
  """
  Set how many SubUs an account may have below it on this system.
  """
  if maximum < 0:
    log.error(account_name ,"a limit is 0 or more"); return
  db = open_system_database(log)
  if db is None: return
  entry = account(account_name)
  if entry is None:
    log.error(account_name ,"no such account on this system"); return
  old = db.row("SELECT maximum FROM user_limit WHERE system_uid = ?" ,(entry.pw_uid,))
  if old and old["maximum"] == maximum:
    log.line("kept" ,f"{account_name} limit {maximum}" ,"already set"); return
  with db.transaction(f"set limit of {account_name} to {maximum}" ,preview) as t:
    t.execute("INSERT INTO user_limit(system_uid ,maximum) VALUES (? ,?)"
              " ON CONFLICT(system_uid) DO UPDATE SET maximum = excluded.maximum" ,(entry.pw_uid ,maximum))
  was = f"was {old['maximum']}" if old else "was unset, which counts as 0"
  log.line("set" ,f"{account_name} limit {maximum}" ,was)
