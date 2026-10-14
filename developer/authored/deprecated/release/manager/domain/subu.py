# domain/subu.py
# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-

from infrastructure.unix import (
  ensure_unix_user,
  ensure_user_in_group,
  remove_unix_user_and_group,
  user_exists,
)


def _validate_token(label: str, token: str) -> str:
  """
  Validate a single path token (masu or subu).

  Rules:
    - must be non-empty after stripping whitespace
    - must not contain underscore '_'
  """
  token_stripped = token.strip()
  if not token_stripped:
    raise SystemExit(f"subu: {label} name must be non-empty")
  if "_" in token_stripped:
    raise SystemExit(
      f"subu: {label} name '{token_stripped}' must not contain underscore '_'"
    )
  # dashes are fine; acronyms and proper nouns are fine.
  return token_stripped


def subu_username(masu: str, path_components: list[str]) -> str:
  """
  Build the Unix username for a subu.

  Examples:
    masu = "Thomas", path = ["S0"]        -> "Thomas_S0"
    masu = "Thomas", path = ["S0","S1"]   -> "Thomas_S0_S1"

  The path is:
    masu subu subu ...
  """
  masu_s = _validate_token("masu", masu).replace(" ", "_")
  subu_parts: list[str] = []
  for s in path_components:
    subu_parts.append(_validate_token("subu", s).replace(" ", "_"))
  parts = [masu_s] + subu_parts
  return "_".join(parts)


def _parent_username(masu: str, path_components: list[str]) -> str | None:
  """
  Return the Unix username of the parent subu, or None if this is top-level.

  Examples:
    masu="Thomas", path=["S0"]        -> None (parent is just the masu)
    masu="Thomas", path=["S0","S1"]   -> "Thomas_S0"
  """
  if len(path_components) <= 1:
    return None
  # parent path is everything except last token
  parent_path = path_components[:-1]
  return subu_username(masu, parent_path)


def _ancestor_group_names(masu: str, path_components: list[str]) -> list[str]:
  """
  Compute ancestor groups that a subu must join for directory traversal.

  For path:
    [masu, s1, s2, ..., sk]

  we return:
    [masu,
     masu_s1,
     masu_s1_s2,
     ...,
     masu_s1_..._s{k-1}]

  The last element (full username) is NOT included, because that is
  the subu's own primary group.
  """
  groups: list[str] = []
  # masu group (allows traversal of /home/masu and /home/masu/subu_data)
  groups.append(_validate_token("masu", masu))

  # For deeper subu, add each ancestor subu's group
  for depth in range(1, len(path_components)):
    prefix = path_components[:depth]
    groups.append(subu_username(masu, prefix))

  return groups


def make_subu(masu: str, path_components: list[str]) -> str:
  """
  Make the Unix user and group for this subu.

  The subu path is:
    masu subu subu ...

  Rules:
    - len(path_components) >= 1
    - tokens must not contain '_'
    - parent must exist:
        * for first-level subu: Unix user 'masu' must exist
        * for deeper subu: parent subu unix user must exist

  Returns:
    Unix username, for example 'Thomas_S0' or 'Thomas_S0_S1'.
  """
  if not path_components:
    raise SystemExit("subu: make requires at least one subu component")

  # Normalize and validate tokens (this will raise SystemExit on error).
  # subu_username will call _validate_token internally.
  username = subu_username(masu, path_components)

  # Enforce parent existence
  parent_uname = _parent_username(masu, path_components)
  if parent_uname is None:
    # Top-level subu: require the masu Unix user to exist
    masu_name = _validate_token("masu", masu)
    if not user_exists(masu_name):
      raise SystemExit(
        f"subu: cannot make '{username}': "
        f"masu Unix user '{masu_name}' does not exist"
      )
  else:
    # Deeper subu: require parent subu Unix user to exist
    if not user_exists(parent_uname):
      raise SystemExit(
        f"subu: cannot make '{username}': "
        f"parent subu unix user '{parent_uname}' does not exist"
      )

  # For now, group and user share the same name.
  ensure_unix_user(username, username)

  # Add this subu to the ancestor groups so that directory traversal works:
  #   /home/masu
  #   /home/masu/subu_data
  #   /home/masu/subu_data/<parent>/subu_data/...
  ancestor_groups = _ancestor_group_names(masu, path_components)
  for gname in ancestor_groups:
    ensure_user_in_group(username, gname)

  return username


def remove_subu(masu: str, path_components: list[str]) -> str:
  """
  Remove the Unix user and group for this subu, if they exist.

  The subu path is:
    masu subu subu ...

  Returns:
    Unix username that was targeted.
  """
  if not path_components:
    raise SystemExit("subu: remove requires at least one subu component")

  username = subu_username(masu, path_components)
  remove_unix_user_and_group(username)
  return username
