# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-
"""
same_user - the work functions that say which users are the same user

A user specifier names a user in one place:

  system <host name> <account>    an account on this system
  storage <SubU dir> <user>       a user of the storage database in that SubU dir

is-same-user is given two user specifiers. In 5.0 one names a system account
and the other a storage user; the correspondence is written into the system
map of the system database, which is the authority for which storage users
have accounts on this system. The storage database gets a note only.
"""

import os ,pwd ,grp
from pathlib import Path

import database
from database import Database ,DatabaseError
from common import (HOME ,run ,host_name ,account ,account_by_system_uid ,group ,uid_min ,is_mountpoint,
  session_system_uids ,valid_name ,subu_dir_problem ,delete_mount_point)
from system import open_system_database


# --------------------------------------------------------------------------------
# opening the two sides

def open_sides(system_spec ,storage_spec ,log):
  """
  Check the two user specifiers and open both databases. Returns
  (system_db ,storage_db) or None with errors logged.
  """
  if system_spec["host"] != host_name():
    log.error(f"system {system_spec['host']}" ,f"this system is {host_name()}; only its own accounts can be named")
    return None
  system_db = open_system_database(log)
  if system_db is None: return None
  problem = subu_dir_problem(storage_spec["subu_dir"])
  if problem:
    log.error(storage_spec["subu_dir"] ,problem); return None
  storage_db = Database.open(database.storage_database_path(storage_spec["subu_dir"]) ,"storage")
  return system_db ,storage_db

def mount_target(row):
  """
  Where the home of the account in a system map row is mounted: the account's
  home in /etc/passwd, which SubU requires to be /home/<account>.
  """
  entry = account_by_system_uid(row["system_uid"])
  return HOME / row["account_name"] ,entry

def is_mounted_from(target ,source):
  """
  Whether target is a mount of source: the root of a bind mount is the source
  directory itself, so the two have the same device and inode.
  """
  try:
    a ,b = os.stat(target) ,os.stat(source)
  except OSError:
    return False
  return is_mountpoint(target) and (a.st_dev ,a.st_ino) == (b.st_dev ,b.st_ino)


# --------------------------------------------------------------------------------
# is-same-user

def is_same_user(system_spec ,storage_spec ,make_account ,log ,preview):
  opened = open_sides(system_spec ,storage_spec ,log)
  if opened is None: return
  system_db ,storage_db = opened
  account_name ,user_name = system_spec["account"] ,storage_spec["user"]

  user = storage_db.row("SELECT * FROM user WHERE name = ?" ,(user_name,))
  if user is None:
    log.error(user_name ,f"no such user in database {storage_db.short()}"); return
  if user["state"] != "active":
    log.error(user_name ,f"the user is {user['state']}"); return
  database_uuid = storage_db.uuid()

  existing = system_db.row("SELECT * FROM system_map WHERE database_uuid = ? AND database_uid = ? AND state = 'in use'",
                           (database_uuid ,user["database_uid"]))
  if existing:
    if existing["account_name"] == account_name:
      log.line("kept" ,f"{account_name} is {user_name}" ,"already the same user"); return
    log.error(user_name ,f"already the same user as account {existing['account_name']}"); return

  entry = account(account_name)
  if entry is not None:
    if make_account:
      log.error(account_name ,"the account exists; --make-account is for an account that does not"); return
    if entry.pw_uid < uid_min():
      log.error(account_name ,f"system uid {entry.pw_uid} is below UID_MIN {uid_min()}, an account of the system's own services"); return
    taken = system_db.row("SELECT * FROM system_map WHERE system_uid = ? AND state = 'in use'" ,(entry.pw_uid,))
    if taken:
      log.error(account_name ,f"already the same user as database uid {taken['database_uid']} of database {taken['database_uuid'][:8]}"); return
    if entry.pw_dir != str(HOME / account_name):
      log.error(account_name ,f"its home is {entry.pw_dir}; SubU mounts a home only at /home/<account>"); return
    system_uid ,system_gid ,kind = entry.pw_uid ,entry.pw_gid ,"adopted"
    log.line("adopted" ,account_name ,f"existing account, system uid {system_uid}")
  else:
    if not make_account:
      log.error(account_name ,"no such account on this system; give --make-account to make it"); return
    problem = valid_name(account_name)
    if problem:
      log.error(account_name ,problem); return
    system_uid = free_system_uid(system_db)
    if system_uid is None:
      log.error(account_name ,"no free system uid in this system's range"); return
    command = ["useradd" ,"--badname" ,"-M" ,"-d" ,str(HOME / account_name) ,"-s" ,"/bin/bash",
               "-u" ,str(system_uid) ,"-U" ,account_name]
    if not run(command ,log ,preview): return
    system_gid = system_uid if preview else account(account_name).pw_gid
    kind = "made"
    log.line("made account" ,account_name ,f"system uid {system_uid}, gid {system_gid}")

  with system_db.transaction(f"{account_name} is the same user as {user_name} of database {storage_db.short()}" ,preview) as t:
    t.execute("INSERT INTO system_map(system_uid ,system_gid ,account_name ,database_uuid ,database_uid ,account ,state ,mapped)"
              " VALUES (? ,? ,? ,? ,? ,? ,'in use' ,?)",
              (system_uid ,system_gid ,account_name ,database_uuid ,user["database_uid"] ,kind ,database.now()))
  log.line("mapped" ,f"{account_name} is {user_name}",
           f"system uid {system_uid} is database uid {user['database_uid']} of database {storage_db.short()}")

  system_uuid = system_db.uuid()
  if not storage_db.row("SELECT 1 FROM system_note WHERE system_uuid = ?" ,(system_uuid,)):
    with storage_db.transaction(f"note system {system_uuid[:8]}" ,preview) as t:
      t.execute("INSERT INTO system_note(system_uuid ,noted) VALUES (? ,?)" ,(system_uuid ,database.now()))
    log.line("recorded" ,f"note of system {system_uuid[:8]}" ,"in the storage database, for its owner")

def free_system_uid(system_db):
  """
  The lowest system uid in the range that no account and no group has, and
  that the system map has never held, in use or retired.
  """
  r = system_db.row("SELECT * FROM system_uid_range")
  held = {m["system_uid"] for m in system_db.rows("SELECT system_uid FROM system_map")}
  for c in range(r["first"] ,r["last"] + 1):
    if c in held or account_by_system_uid(c) is not None: continue
    try:
      grp.getgrgid(c); continue
    except KeyError:
      return c
  return None


# --------------------------------------------------------------------------------
# is-not-same-user

def is_not_same_user(system_spec ,storage_spec ,log ,preview):
  opened = open_sides(system_spec ,storage_spec ,log)
  if opened is None: return
  system_db ,storage_db = opened
  account_name ,user_name = system_spec["account"] ,storage_spec["user"]
  user = storage_db.row("SELECT * FROM user WHERE name = ?" ,(user_name,))
  if user is None:
    log.error(user_name ,f"no such user in database {storage_db.short()}"); return
  row = system_db.row("SELECT * FROM system_map WHERE database_uuid = ? AND database_uid = ? AND state = 'in use'",
                      (storage_db.uuid() ,user["database_uid"]))
  if row is None:
    log.line("kept" ,user_name ,"not the same user as any account here; nothing to undo"); return
  if row["account_name"] != account_name:
    log.error(user_name ,f"is the same user as account {row['account_name']}, not {account_name}"); return
  if account_by_system_uid(row["system_uid"]) and row["system_uid"] in session_system_uids():
    log.error(account_name ,"is logged in; nothing was changed"); return
  end_same_user(row ,system_db ,storage_spec["subu_dir"] ,user_name ,log ,preview)

def end_same_user(row ,system_db ,subu_dir ,user_name ,log ,preview):
  """
  Undo one row of the system map: unmount the home if it is mounted from this
  storage, delete the mount point attach made, delete the account if SubU
  made it, and retire the row. Returns False when it had to stop.
  """
  target ,entry = mount_target(row)
  source = database.user_data_dir(subu_dir) / user_name
  if is_mounted_from(target ,source):
    if not run(["umount" ,str(target)] ,log ,preview):
      log.line("stopped" ,row["account_name"] ,"the home could not be unmounted; nothing further was changed")
      return False
    log.line("unmounted" ,str(target))
  delete_mount_point(target ,log ,preview)
  if row["account"] == "made" and entry is not None and entry.pw_name == row["account_name"]:
    group_entry = group(row["account_name"])
    if not run(["userdel" ,row["account_name"]] ,log ,preview): return False
    log.line("deleted account" ,row["account_name"] ,f"system uid {row['system_uid']}")
    if group_entry is not None and group_entry.gr_gid == row["system_gid"] and not group_entry.gr_mem:
      if not preview and group(row["account_name"]) is not None:
        if not run(["groupdel" ,row["account_name"]] ,log ,preview): return False
      log.line("deleted group" ,row["account_name"] ,f"gid {row['system_gid']}")
  elif row["account"] == "adopted":
    log.line("kept" ,f"account {row['account_name']}" ,"it existed before SubU adopted it")
  with system_db.transaction(f"{row['account_name']} is no longer the same user as database uid {row['database_uid']}"
                             f" of database {row['database_uuid'][:8]}" ,preview) as t:
    t.execute("UPDATE system_map SET state = 'retired' ,retired = ? WHERE id = ?" ,(database.now() ,row["id"]))
  log.line("retired" ,f"system uid {row['system_uid']}" ,"in the system map; it is not given out again")
  return True


# --------------------------------------------------------------------------------
# show and suggest

def same_user_show(storage_spec):
  """
  The accounts of this system that are the same users as storage users; with
  a storage, its users that are not, and the person accounts that are not.
  """
  system_db = Database.open(database.SYSTEM_DATABASE_PATH ,"system")
  storage_db = None
  if storage_spec:
    storage_db = Database.open(database.storage_database_path(storage_spec["subu_dir"]) ,"storage")
  in_use = system_db.rows("SELECT * FROM system_map WHERE state = 'in use' ORDER BY account_name")
  if storage_db:
    in_use = [m for m in in_use if m["database_uuid"] == storage_db.uuid()]
  print(f"same users on system {host_name()}")
  for m in in_use:
    user_name = "?"
    if storage_db:
      u = storage_db.row("SELECT name FROM user WHERE database_uid = ?" ,(m["database_uid"],))
      user_name = u["name"] if u else "(no such user)"
    print(f"  system {host_name()} {m['account_name']:<24} storage {m['database_uuid'][:8]}"
          f" {user_name if storage_db else 'database uid ' + str(m['database_uid'])}  ({m['account']})")
  if storage_db:
    mapped = {m["database_uid"] for m in in_use}
    print(f"users of database {storage_db.short()} that are not the same user as any account here")
    for u in storage_db.rows("SELECT * FROM user WHERE state = 'active' ORDER BY name"):
      if u["database_uid"] not in mapped:
        print(f"  {u['name']}")
  mapped_account = {m["account_name"] for m in system_db.rows("SELECT account_name FROM system_map WHERE state = 'in use'")}
  print("person accounts here that are not the same user as any storage user")
  for entry in sorted(pwd.getpwall() ,key=lambda e: e.pw_name):
    if uid_min() <= entry.pw_uid < 60000 and entry.pw_name not in mapped_account:
      print(f"  {entry.pw_name}")
  return 0

def same_user_suggest(storage_spec):
  """
  Print is-same-user commands for the storage users that are not yet the same
  user as any account, proposed by matching names. Changes nothing.
  """
  system_db = Database.open(database.SYSTEM_DATABASE_PATH ,"system")
  subu_dir = storage_spec["subu_dir"]
  storage_db = Database.open(database.storage_database_path(subu_dir) ,"storage")
  mapped = {m["database_uid"] for m in system_db.rows(
    "SELECT database_uid FROM system_map WHERE state = 'in use' AND database_uuid = ?" ,(storage_db.uuid(),))}
  taken = {m["system_uid"] for m in system_db.rows("SELECT system_uid FROM system_map WHERE state = 'in use'")}
  print("# proposed by matching names; read each line before running it")
  for u in storage_db.rows("SELECT * FROM user WHERE state = 'active' ORDER BY name"):
    if u["database_uid"] in mapped: continue
    entry = account(u["name"])
    line = f"SubU_admin is-same-user system {host_name()} '{u['name']}' storage {subu_dir} '{u['name']}'"
    if entry is None:
      print(line + " --make-account")
    elif entry.pw_uid in taken or entry.pw_uid < uid_min():
      print(f"# {u['name']}: the account of that name cannot be adopted (system uid {entry.pw_uid})")
    else:
      print(line + f"    # adopts the existing account, system uid {entry.pw_uid}")
  return 0
