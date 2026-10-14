# infrastructure/db.py
# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-

import sqlite3
from pathlib import Path
import env


def schema_path_default():
  """
  Path to schema.sql, assumed to live next to this file.
  """
  return Path(__file__).with_name("schema.sql")


def open_db(path=None):
  """
  Return a sqlite3.Connection with sensible pragmas.
  Caller is responsible for closing.

  If path is None, the canonical manager DB path from env.db_path()
  is used. The parent directory is created if it does not exist.
  """
  if path is None:
    path = env.db_path()

  path_obj = Path(path)
  parent = path_obj.parent

  try:
    parent.mkdir(parents=True, exist_ok=True)
  except PermissionError as e:
    raise RuntimeError(f"cannot create DB directory '{parent}': {e}") from e

  conn = sqlite3.connect(str(path_obj))
  conn.row_factory = sqlite3.Row
  conn.execute("PRAGMA foreign_keys = ON")
  conn.execute("PRAGMA journal_mode = WAL")
  conn.execute("PRAGMA synchronous = NORMAL")
  return conn


def ensure_schema(conn):
  """
  Ensure the schema in schema.sql is applied.
  This is idempotent: executing the DDL again is acceptable.
  """
  sql = schema_path_default().read_text(encoding="utf-8")
  conn.executescript(sql)
  conn.commit()
