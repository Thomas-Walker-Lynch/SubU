# dispatch.py
# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-

import os, sys, sqlite3, stat
import env
from domain import subu as subu_domain
from infrastructure.db import open_db, ensure_schema
from infrastructure.options_store import set_option, get_option
from infrastructure.unix import (
  ensure_unix_group,
  ensure_unix_user,
  ensure_user_in_group,
  remove_user_from_group,
  user_exists,
)
# lo_toggle, WG, attach, network, exec stubs remain below.


def _require_root(action: str) -> bool:
  try:
    euid = os.geteuid()
  except AttributeError:
    return True
  if euid != 0:
    print(f"{action}: must be run as root", file=sys.stderr)
    return False
  return True


def _db_path() -> str:
  return env.db_path()


def _open_existing_db() -> sqlite3.Connection | None:
  path = _db_path()
  if not os.path.exists(path):
    print(
      f"subu: database does not exist at '{path}'.\n"
      f"       Run 'db load schema' as root first.",
      file=sys.stderr,
    )
    return None
  try:
    conn = open_db(path)
  except Exception as e:
    print(f"subu: unable to open database '{path}': {e}", file=sys.stderr)
    return None

  conn.row_factory = sqlite3.Row
  return conn


def db_load_schema() -> int:
  if not _require_root("db load schema"):
    return 1

  path = _db_path()
  db_dir = os.path.dirname(path) or "."

  try:
    os.makedirs(db_dir, mode=0o750, exist_ok=True)
  except PermissionError as e:
    print(f"subu: cannot create db directory '{db_dir}': {e}", file=sys.stderr)
    return 1

  try:
    conn = open_db(path)
  except Exception as e:
    print(f"subu: unable to open database '{path}': {e}", file=sys.stderr)
    return 1

  try:
    ensure_schema(conn)
  finally:
    conn.close()

  print(f"subu: schema loaded into {path}")
  return 0


def _insert_subu_row(conn, owner: str, subu_path: list[str], username: str) -> int | None:
  """Insert a row into subu table and return its id."""
  leaf_name = subu_path[-1]
  full_unix_name = username
  path_str = " ".join([owner] + subu_path)
  netns_name = full_unix_name

  from datetime import datetime, timezone

  now = datetime.now(timezone.utc).isoformat()

  try:
    cur = conn.execute(
      """INSERT INTO subu
            (owner, name, full_unix_name, path, netns_name, wg_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, NULL, ?, ?)""",
      (owner, leaf_name, full_unix_name, path_str, netns_name, now, now),
    )
    conn.commit()
    return cur.lastrowid
  except sqlite3.IntegrityError as e:
    print(
      f"subu: database already has an entry for '{full_unix_name}': {e}",
      file=sys.stderr,
    )
    return None
  except Exception as e:
    print(f"subu: error recording subu in database: {e}", file=sys.stderr)
    return None


def _maybe_add_to_incommon(conn, owner: str, new_username: str) -> None:
  """If owner has an incommon subu configured, add new_username to that group."""
  key = f"incommon.{owner}"
  spec = get_option(key, None)
  if not spec:
    return
  if not isinstance(spec, str) or not spec.startswith("subu_"):
    print(
      f"subu: warning: option {key} has unexpected value '{spec}', "
      "expected 'subu_<id>'",
      file=sys.stderr,
    )
    return
  try:
    subu_numeric_id = int(spec.split("_", 1)[1])
  except ValueError:
    print(
      f"subu: warning: option {key} has invalid Subu_ID '{spec}'",
      file=sys.stderr,
    )
    return

  row = conn.execute(
    "SELECT full_unix_name FROM subu WHERE id = ? AND owner = ?",
    (subu_numeric_id, owner),
  ).fetchone()
  if row is None:
    print(
      f"subu: warning: option {key} refers to missing subu id {subu_numeric_id}",
      file=sys.stderr,
    )
    return

  incommon_unix = row["full_unix_name"]
  ensure_user_in_group(new_username, incommon_unix)


def subu_make(path_tokens: list[str]) -> int:
  if not path_tokens or len(path_tokens) < 2:
    print(
      "subu: make requires at least <masu> and one <subu> component",
      file=sys.stderr,
    )
    return 2

  if not _require_root("subu make"):
    return 1

  masu = path_tokens[0]
  subu_path = path_tokens[1:]

  try:
    username = subu_domain.make_subu(masu, subu_path)
  except SystemExit as e:
    print(f"subu: {e}", file=sys.stderr)
    return 2
  except Exception as e:
    print(f"subu: error creating Unix user for {path_tokens}: {e}", file=sys.stderr)
    return 1

  conn = _open_existing_db()
  if conn is None:
    return 1

  subu_id = _insert_subu_row(conn, masu, subu_path, username)
  if subu_id is None:
    conn.close()
    return 1

  # If this owner has an incommon subu, join that group.
  _maybe_add_to_incommon(conn, masu, username)

  conn.close()
  print(f"subu_{subu_id}")
  return 0


def subu_capture(path_tokens: list[str]) -> int:
  """Handle: subu capture <masu> <subu> [<subu> ...]

  Capture an existing Unix user into the database and fix its groups.
  """
  if not path_tokens or len(path_tokens) < 2:
    print(
      "subu: capture requires at least <masu> and one <subu> component",
      file=sys.stderr,
    )
    return 2

  if not _require_root("subu capture"):
    return 1

  masu = path_tokens[0]
  subu_path = path_tokens[1:]

  # Compute expected Unix username.
  try:
    username = subu_domain.subu_username(masu, subu_path)
  except SystemExit as e:
    print(f"subu: {e}", file=sys.stderr)
    return 2

  if not user_exists(username):
    print(f"subu: capture: Unix user '{username}' does not exist", file=sys.stderr)
    return 1

  # Ensure the primary group exists (legacy systems should already have it).
  ensure_unix_group(username)

  # Ensure membership in ancestor groups for traversal.
  ancestor_groups = subu_domain._ancestor_group_names(masu, subu_path)
  for gname in ancestor_groups:
    ensure_user_in_group(username, gname)

  conn = _open_existing_db()
  if conn is None:
    return 1

  subu_id = _insert_subu_row(conn, masu, subu_path, username)
  if subu_id is None:
    conn.close()
    return 1

  # Honor any incommon config for this owner.
  _maybe_add_to_incommon(conn, masu, username)

  conn.close()
  print(f"subu_{subu_id}")
  return 0


def _resolve_subu(conn: sqlite3.Connection, target: str, rest: list[str]) -> sqlite3.Row | None:
  """Resolve a subu either by ID (subu_7) or by path."""
  if target.startswith("subu_") and not rest:
    try:
      subu_numeric_id = int(target.split("_", 1)[1])
    except ValueError:
      print(f"subu: invalid Subu_ID '{target}'", file=sys.stderr)
      return None

    row = conn.execute("SELECT * FROM subu WHERE id = ?", (subu_numeric_id,)).fetchone()
    if row is None:
      print(f"subu: no such subu with id {subu_numeric_id}", file=sys.stderr)
    return row

  path_tokens = [target] + list(rest)
  if len(path_tokens) < 2:
    print(
      "subu: path form requires at least <masu> and one <subu> component",
      file=sys.stderr,
    )
    return None

  owner = path_tokens[0]
  path_str = " ".join(path_tokens)

  row = conn.execute(
    "SELECT * FROM subu WHERE owner = ? AND path = ?",
    (owner, path_str),
  ).fetchone()

  if row is None:
    print(f"subu: no such subu with owner='{owner}' and path='{path_str}'", file=sys.stderr)
  return row


def subu_list() -> int:
  conn = _open_existing_db()
  if conn is None:
    return 1

  cur = conn.execute(
    "SELECT id, owner, path, full_unix_name, netns_name, wg_id FROM subu ORDER BY id"
  )
  rows = cur.fetchall()
  conn.close()

  if not rows:
    print("(no subu in database)")
    return 0

  for row in rows:
    subu_id = row[0]
    owner = row[1]
    path = row[2]
    full_unix_name = row[3]
    netns_name = row[4]
    wg_id = row[5]
    wg_display = "-" if wg_id is None else f"WG_{wg_id}"
    print(f"subu_{subu_id}\t{owner}\t{path}\t{full_unix_name}\t{netns_name}\t{wg_display}")

  return 0


def subu_info(target: str, rest: list[str]) -> int:
  conn = _open_existing_db()
  if conn is None:
    return 1

  row = _resolve_subu(conn, target, rest)
  if row is None:
    conn.close()
    return 1

  subu_id = row["id"]
  owner = row["owner"]
  name = row["name"]
  full_unix_name = row["full_unix_name"]
  path = row["path"]
  netns_name = row["netns_name"]
  wg_id = row["wg_id"]
  created_at = row["created_at"]
  updated_at = row["updated_at"]

  conn.close()

  print(f"Subu_ID:    subu_{subu_id}")
  print(f"Owner:      {owner}")
  print(f"Name:       {name}")
  print(f"Path:       {path}")
  print(f"Unix user:  {full_unix_name}")
  print(f"Netns:      {netns_name}")
  print(f"WG_ID:      {wg_id if wg_id is not None else '-'}")
  print(f"Created:    {created_at}")
  print(f"Updated:    {updated_at}")
  return 0


def subu_remove(target: str, rest: list[str]) -> int:
  if not _require_root("subu remove"):
    return 1

  conn = _open_existing_db()
  if conn is None:
    return 1

  row = _resolve_subu(conn, target, rest)
  if row is None:
    conn.close()
    return 1

  subu_id = row["id"]
  path_str = row["path"]
  path_tokens = path_str.split(" ")
  if len(path_tokens) < 2:
    print(f"subu: stored path is invalid for id {subu_id}: '{path_str}'", file=sys.stderr)
    conn.close()
    return 1

  masu = path_tokens[0]
  subu_path = path_tokens[1:]

  try:
    username = subu_domain.remove_subu(masu, subu_path)
  except SystemExit as e:
    print(f"subu: {e}", file=sys.stderr)
    conn.close()
    return 2
  except Exception as e:
    print(f"subu: error removing Unix user for id subu_{subu_id}: {e}", file=sys.stderr)
    conn.close()
    return 1

  try:
    conn.execute("DELETE FROM subu WHERE id = ?", (subu_id,))
    conn.commit()
  except Exception as e:
    print(f"subu: error removing database row for id subu_{subu_id}: {e}", file=sys.stderr)
    conn.close()
    return 1

  conn.close()
  print(f"removed subu_{subu_id} {username}")
  return 0


def _subu_home_path(owner: str, path_str: str) -> str:
  """Compute subu home dir from owner and path string."""
  tokens = path_str.split(" ")
  if not tokens or tokens[0] != owner:
    return ""
  subu_tokens = tokens[1:]
  path = os.path.join("/home", owner)
  for t in subu_tokens:
    path = os.path.join(path, "subu_data", t)
  return path


def _chmod_incommon(home: str) -> None:
  try:
    st = os.stat(home)
  except FileNotFoundError:
    print(f"subu: warning: incommon home '{home}' does not exist", file=sys.stderr)
    return

  mode = st.st_mode
  mode |= (stat.S_IRGRP | stat.S_IXGRP)
  mode &= ~(stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH)
  os.chmod(home, mode)


def _chmod_private(home: str) -> None:
  try:
    st = os.stat(home)
  except FileNotFoundError:
    print(f"subu: warning: home '{home}' does not exist for clear incommon", file=sys.stderr)
    return

  mode = st.st_mode
  mode &= ~(stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP)
  os.chmod(home, mode)


def subu_option_incommon(action: str, target: str, rest: list[str]) -> int:
  """Handle:

    subu option set   incommon <Subu_ID>|<masu> <subu> [<subu> ...]
    subu option clear incommon <Subu_ID>|<masu> <subu> [<subu> ...]
  """
  if not _require_root(f"subu option {action} incommon"):
    return 1

  conn = _open_existing_db()
  if conn is None:
    return 1

  row = _resolve_subu(conn, target, rest)
  if row is None:
    conn.close()
    return 1

  subu_id = row["id"]
  owner = row["owner"]
  full_unix_name = row["full_unix_name"]
  path_str = row["path"]

  key = f"incommon.{owner}"
  spec = f"subu_{subu_id}"

  if action == "set":
    # Record mapping.
    set_option(key, spec)

    # Make all subu of this owner members of this group.
    cur = conn.execute(
      "SELECT full_unix_name FROM subu WHERE owner = ?",
      (owner,),
    )
    rows = cur.fetchall()
    for r in rows:
      uname = r["full_unix_name"]
      if uname == full_unix_name:
        continue
      ensure_user_in_group(uname, full_unix_name)

    # Adjust directory permissions on incommon home.
    home = _subu_home_path(owner, path_str)
    if home:
      _chmod_incommon(home)

    conn.close()
    print(f"incommon for {owner} set to subu_{subu_id}")
    return 0

  # clear
  current = get_option(key, "")
  if current and current != spec:
    print(
      f"subu: incommon for owner '{owner}' is currently {current}, not {spec}",
      file=sys.stderr,
    )
    conn.close()
    return 1

  # Clear mapping.
  set_option(key, "")

  # Remove other subu from this group.
  cur = conn.execute(
    "SELECT full_unix_name FROM subu WHERE owner = ?",
    (owner,),
  )
  rows = cur.fetchall()
  for r in rows:
    uname = r["full_unix_name"]
    if uname == full_unix_name:
      continue
    remove_user_from_group(uname, full_unix_name)

  home = _subu_home_path(owner, path_str)
  if home:
    _chmod_private(home)

  conn.close()
  print(f"incommon for {owner} cleared from subu_{subu_id}")
  return 0


# --- existing stubs (unchanged) -------------------------------------------

def wg_global(arg1: str | None) -> int:
  print("WG global: not yet implemented", file=sys.stderr)
  return 1


def wg_make(arg1: str | None) -> int:
  print("WG make: not yet implemented", file=sys.stderr)
  return 1


def wg_server_public_key(arg1: str | None, arg2: str | None) -> int:
  print("WG server_provided_public_key: not yet implemented", file=sys.stderr)
  return 1


def wg_info(arg1: str | None) -> int:
  print("WG info: not yet implemented", file=sys.stderr)
  return 1


def wg_up(arg1: str | None) -> int:
  print("WG up: not yet implemented", file=sys.stderr)
  return 1


def wg_down(arg1: str | None) -> int:
  print("WG down: not yet implemented", file=sys.stderr)
  return 1


def attach_wg(subu_id: str, wg_id: str) -> int:
  print("attach WG: not yet implemented", file=sys.stderr)
  return 1


def detach_wg(subu_id: str) -> int:
  print("detach WG: not yet implemented", file=sys.stderr)
  return 1


def network_toggle(subu_id: str, state: str) -> int:
  print("network up/down: not yet implemented", file=sys.stderr)
  return 1


def lo_toggle(subu_id: str, state: str) -> int:
  print("lo up/down: not yet implemented", file=sys.stderr)
  return 1


def exec(subu_id: str, cmd_argv: list[str]) -> int:
  print("exec: not yet implemented", file=sys.stderr)
  return 1
