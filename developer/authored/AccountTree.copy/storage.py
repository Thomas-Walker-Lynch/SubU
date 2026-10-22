# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-
"""
storage - the work functions for storage databases

A storage is a persistent storage device that keeps users' data: the disk
inside the machine, or a drive plugged in. Its SubU dir is <storage root>/home/SubU,
which holds the storage database and user_data, the users' homes. On the disk a
system runs from, the SubU dir is /home/SubU.

Which storage users have accounts on this system is recorded in the system
map of the system database, and attach mounts exactly the users it lists.
"""

import os ,shutil ,subprocess
from pathlib import Path

import database
from database import Database ,DatabaseError
from common import (HOME ,SEPARATOR ,run ,account_by_system_uid ,is_mountpoint ,mount_point_list,
  session_system_uids ,valid_name ,subu_dir_problem)
from system import open_system_database ,DATABASE_UID_FLOOR
import same_user

# A storage database gives out database uids counting down from
# DATABASE_UID_FIRST, while systems give out system uids counting up from low
# numbers. See "Limits of uids" in the design document.
DATABASE_UID_FIRST = 1_999_999_999


def open_storage_database(subu_dir ,log):
  problem = subu_dir_problem(subu_dir)
  if problem:
    log.error(str(subu_dir) ,problem); return None
  return Database.open(database.storage_database_path(subu_dir) ,"storage")

def system_map_in_use(system_db ,storage_db):
  return system_db.rows("SELECT * FROM system_map WHERE database_uuid = ? AND state = 'in use' ORDER BY account_name",
                        (storage_db.uuid(),))


# --------------------------------------------------------------------------------
# storage make, show, delete

def storage_make(subu_dir ,log ,preview):
  problem = subu_dir_problem(subu_dir)
  if problem:
    log.error(str(subu_dir) ,problem); return
  subu_dir = Path(subu_dir)
  home = subu_dir.parent
  root = home.parent
  if not root.is_dir():
    log.error(str(root) ,"the storage root is not a directory"); return
  path = database.storage_database_path(subu_dir)
  if path.exists():
    db = Database.open(path ,"storage")
    log.line("kept" ,str(path) ,f"a storage database exists, database uuid {db.uuid()}")
  else:
    for directory ,mode in ((home ,0o755) ,(subu_dir ,0o700)):
      if not directory.is_dir():
        if not preview:
          directory.mkdir(mode=mode)
          os.chmod(directory ,mode)
        log.line("made" ,str(directory) ,f"mode {mode:04o}")
    db = Database.make(path ,"storage" ,preview)
    # a database uuid is drawn at random; the one drawn in a preview is thrown away
    log.line("made" ,str(path) ,"a new database uuid" if preview else f"database uuid {db.uuid()}")
  user_data = database.user_data_dir(subu_dir)
  if user_data.is_dir():
    log.line("kept" ,str(user_data))
  else:
    if not preview:
      user_data.mkdir(mode=0o700)
      os.chmod(user_data ,0o700)
    log.line("made" ,str(user_data) ,"root only, mode 0700")

def storage_show(subu_dir):
  problem = subu_dir_problem(subu_dir)
  if problem:
    print(f"Error: {problem}"); return 1
  db = Database.open(database.storage_database_path(subu_dir) ,"storage")
  d = db.identity()
  print(f"storage   database uuid {d['database_uuid']}")
  print(f"file      {db.path}")
  print(f"series    {d['series']}  head {d['head_hash'][:16]}")
  print(f"made      {d['created']}")
  print(f"changed   {db.last_change()}")
  print("standard  " + " ".join(r["version"] for r in db.rows("SELECT version FROM standard")))
  mapped = {}
  if database.SYSTEM_DATABASE_PATH.is_file():
    system_db = Database.open(database.SYSTEM_DATABASE_PATH ,"system")
    mapped = {m["database_uid"]: m for m in system_map_in_use(system_db ,db)}
  print("users")
  for u in db.rows("SELECT * FROM user ORDER BY name"):
    m = mapped.get(u["database_uid"])
    here = f"account {m['account_name']}, system uid {m['system_uid']}" if m else "no account on this system"
    print(f"  {u['name']:<28}database uid {u['database_uid']:<12}{u['state']:<10}{here}")
  for n in db.rows("SELECT * FROM system_note ORDER BY noted"):
    print(f"noted     system {n['system_uuid']}  {n['noted']}")
  problem = db.verify()
  print("verify    " + ("ok" if not problem else "; ".join(problem)))
  return 1 if problem else 0

def storage_delete(subu_dir ,user_data_too ,forget_other_systems ,log ,preview):
  """
  Undo on this system what SubU did for the storage database in subu_dir,
  then delete the SubU dir. Every check is made before anything is changed;
  a check that fails stops the command with nothing changed.
  """
  problem = subu_dir_problem(subu_dir)
  if problem:
    log.error(str(subu_dir) ,problem); return
  subu_dir = Path(subu_dir)
  user_data = database.user_data_dir(subu_dir)
  path = database.storage_database_path(subu_dir)
  if not path.is_file():
    log.line("kept" ,str(subu_dir) ,"no storage database here; nothing to delete"); return
  db = Database.open(path ,"storage")
  system_db = Database.open(database.SYSTEM_DATABASE_PATH ,"system") if database.SYSTEM_DATABASE_PATH.is_file() else None
  this_system_uuid = system_db.uuid() if system_db else None
  in_use = system_map_in_use(system_db ,db) if system_db else []
  user_name = {u["database_uid"]: u["name"] for u in db.rows("SELECT database_uid ,name FROM user")}

  # ---- checks
  problem = []
  if not forget_other_systems:
    for n in db.rows("SELECT * FROM system_note WHERE system_uuid IS NOT ?" ,(this_system_uuid,)):
      problem.append(f"system {n['system_uuid'][:8]} has accounts for users of this database, and its system map"
                     " would name a database that no longer exists; give --forget-other-systems to delete anyway")
  in_session = session_system_uids()
  for m in in_use:
    if m["system_uid"] in in_session:
      problem.append(f"{m['account_name']} is logged in")
  for target in mount_point_list():
    if target.startswith(str(subu_dir) + "/"):
      problem.append(f"{target} is a mount point inside {subu_dir}")
  for entry in sorted(subu_dir.iterdir()):
    if entry.name != "user_data" and not entry.name.startswith("database.sqlite3"):
      problem.append(f"{entry} is not SubU's")
  holding_file = []
  if user_data.is_dir():
    for entry in sorted(user_data.iterdir()):
      if entry.name not in user_name.values():
        problem.append(f"{entry} is not the home of a user of this database")
      elif entry.is_dir() and any(entry.iterdir()):
        holding_file.append(entry.name)
  if holding_file and not user_data_too:
    problem.append("these homes hold files: " + ", ".join(holding_file) + "; give --user-data to delete them too")
  if problem:
    for p in problem: log.error(str(subu_dir) ,p)
    log.line("kept" ,str(subu_dir) ,"nothing was changed")
    return

  # ---- this system's accounts for its users
  for m in in_use:
    if not same_user.end_same_user(m ,system_db ,subu_dir ,user_name.get(m["database_uid"] ,"?") ,log ,preview):
      log.line("stopped" ,str(subu_dir) ,"nothing further was changed"); return

  # ---- files
  if user_data.is_dir():
    home_count = sum(1 for _ in user_data.iterdir())
    if not preview:
      shutil.rmtree(user_data)
    log.line("deleted" ,str(user_data) ,f"{home_count} user home" + ("" if home_count == 1 else "s"))
  short = db.short()
  db.close()
  for entry in sorted(subu_dir.iterdir()):
    if entry.name.startswith("database.sqlite3"):
      if not preview: entry.unlink()
      log.line("deleted" ,str(entry) ,f"database {short}" if entry.name == "database.sqlite3" else None)
  if not preview:
    subu_dir.rmdir()
  log.line("deleted" ,str(subu_dir))


# --------------------------------------------------------------------------------
# user make

def user_make(subu_dir ,name ,database_uid ,masu ,log ,preview):
  problem = valid_name(name)
  if problem:
    log.error(name ,problem); return
  db = open_storage_database(subu_dir ,log)
  if db is None: return
  if db.row("SELECT 1 FROM user WHERE name = ?" ,(name,)):
    log.line("kept" ,f"user {name}" ,"already a user of this database"); return
  if masu is None and SEPARATOR in name:
    masu = name.rsplit(SEPARATOR ,1)[0]
  if masu is not None and not name.startswith(masu + SEPARATOR):
    log.error(name ,f"the name of a SubU of {masu} begins with '{masu}{SEPARATOR}'"); return
  masu_row = db.row("SELECT database_uid FROM user WHERE name = ?" ,(masu,)) if masu else None
  masu_database_uid = masu_row["database_uid"] if masu_row else None

  if database_uid is None:
    # the next database uid down from the lowest given out in the band; one
    # kept with --uid lies outside the band and does not move the count
    lowest = db.row("SELECT MIN(database_uid) AS m FROM database_uid WHERE database_uid >= ?",
                    (DATABASE_UID_FLOOR,))["m"]
    database_uid = DATABASE_UID_FIRST if lowest is None else lowest - 1
    if database_uid < DATABASE_UID_FLOOR:
      log.error(name ,"this database has given out every database uid in its band"); return
  elif db.row("SELECT 1 FROM database_uid WHERE database_uid = ?" ,(database_uid,)):
    log.error(name ,f"database uid {database_uid} has been given out before"); return

  home = database.user_data_dir(subu_dir) / name
  if home.exists() and home.stat().st_uid != database_uid:
    log.error(str(home) ,f"exists, owned by uid {home.stat().st_uid}, not database uid {database_uid}"); return

  stamp = database.now()
  with db.transaction(f"make user {name}" ,preview) as t:
    t.execute("INSERT INTO database_uid(database_uid ,state) VALUES (? ,'in use')" ,(database_uid,))
    t.execute("INSERT INTO user(database_uid ,name ,masu_database_uid ,masu_name ,state ,created ,changed)"
      " VALUES (? ,? ,? ,? ,'active' ,? ,?)" ,(database_uid ,name ,masu_database_uid ,masu ,stamp ,stamp))
  log.line("made" ,f"user {name}" ,f"database uid {database_uid}" + (f", SubU of {masu}" if masu else ""))
  if home.exists():
    log.line("kept" ,str(home) ,"existing home directory, owned by its database uid")
  else:
    if not preview:
      home.mkdir(mode=0o700)
      os.chown(home ,database_uid ,database_uid)
      os.chmod(home ,0o700)
    log.line("made" ,str(home) ,f"owned by database uid {database_uid}, mode 0700")


# --------------------------------------------------------------------------------
# attach and detach

def attach(subu_dir ,log ,preview):
  """
  Mount the home of each storage user that the system map makes the same
  user as an account here, at /home/<account>.
  """
  system_db = open_system_database(log)
  if system_db is None: return
  db = open_storage_database(subu_dir ,log)
  if db is None: return
  problem = db.verify()
  if problem:
    for p in problem: log.error(str(db.path) ,p)
    return
  log.line("found" ,f"database {db.short()}" ,f"series {db.identity()['series']}, chain verified")
  in_use = system_map_in_use(system_db ,db)
  mapped = {m["database_uid"] for m in in_use}
  for m in in_use:
    attach_user(subu_dir ,db ,m ,log ,preview)
  for u in db.rows("SELECT * FROM user WHERE state = 'active' ORDER BY name"):
    if u["database_uid"] not in mapped:
      log.line("skipped" ,f"user {u['name']}" ,"not the same user as any account on this system")

def attach_user(subu_dir ,db ,m ,log ,preview):
  user = db.row("SELECT * FROM user WHERE database_uid = ?" ,(m["database_uid"],))
  if user is None or user["state"] != "active":
    log.error(m["account_name"] ,f"the system map names database uid {m['database_uid']},"
              " which is not an active user of this database"); return
  target ,entry = same_user.mount_target(m)
  if entry is None or entry.pw_name != m["account_name"]:
    log.error(m["account_name"] ,f"no account {m['account_name']} with system uid {m['system_uid']}; it is to be made again"); return
  if entry.pw_dir != str(target):
    log.error(m["account_name"] ,f"its home is {entry.pw_dir}; SubU mounts a home only at {target}"); return
  source = database.user_data_dir(subu_dir) / user["name"]
  if not source.is_dir():
    log.error(str(source) ,"no such directory"); return
  if is_mountpoint(target):
    if same_user.is_mounted_from(target ,source):
      log.line("kept" ,str(target) ,"already mounted"); return
    log.error(str(target) ,"something else is mounted there"); return
  if target.exists():
    if not target.is_dir():
      log.error(str(target) ,"exists and is not a directory"); return
    if any(target.iterdir()):
      log.error(str(target) ,"not empty and not a mount point; nothing is mounted over it"); return
  else:
    if not preview:
      target.mkdir(mode=0o000)
      os.chmod(target ,0o000)
      subprocess.run(["chattr" ,"+i" ,str(target)] ,capture_output=True)
    log.line("made" ,str(target) ,"mount point, root, mode 0000, immutable")

  # nosuid and nodev: a storage may carry set-user-id programs and device files
  database_uid = m["database_uid"]
  if database_uid == m["system_uid"] and database_uid == m["system_gid"]:
    option = "nosuid,nodev"
    how = "bind mount, the database uid and system uid are the same"
  else:
    option = f"X-mount.idmap=u:{database_uid}:{m['system_uid']}:1 g:{database_uid}:{m['system_gid']}:1,nosuid,nodev"
    how = f"idmapped, database uid {database_uid} to system uid {m['system_uid']}"
  if run(["mount" ,"--bind" ,"-o" ,option ,str(source) ,str(target)] ,log ,preview):
    log.line("mounted" ,str(target) ,f"{how}; nosuid, nodev")

def detach(subu_dir ,log ,preview):
  system_db = open_system_database(log)
  if system_db is None: return
  db = open_storage_database(subu_dir ,log)
  if db is None: return
  in_session = session_system_uids()
  for m in system_map_in_use(system_db ,db):
    user = db.row("SELECT name FROM user WHERE database_uid = ?" ,(m["database_uid"],))
    target ,entry = same_user.mount_target(m)
    source = database.user_data_dir(subu_dir) / (user["name"] if user else "")
    if not same_user.is_mounted_from(target ,source):
      log.line("kept" ,str(target) ,"not mounted from this storage"); continue
    if m["system_uid"] in in_session:
      log.error(m["account_name"] ,"is logged in; not detached"); continue
    if run(["umount" ,str(target)] ,log ,preview):
      log.line("unmounted" ,str(target))
