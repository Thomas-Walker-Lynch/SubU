#!/usr/bin/env python3
# Shared helpers (DB path + small SQLite utilities). No side effects on import.

from __future__ import annotations
from pathlib import Path
import sqlite3
from typing import Iterable, Sequence, Any, List, Tuple, Optional

# Base paths
ROOT_DIR: Path = Path(__file__).resolve().parent
DB_PATH: Path = ROOT_DIR / "db" / "store"   # default location

def open_db(path: Optional[Path]=None) -> sqlite3.Connection:
  p = path or DB_PATH
  if not p.exists():
    raise FileNotFoundError(f"DB not found: {p}")
  conn = sqlite3.connect(p.as_posix())
  # enforce FK; journal mode is set by schema, but enabling FK here is harmless and desired
  conn.execute("PRAGMA foreign_keys = ON;")
  return conn

def rows(conn: sqlite3.Connection, sql: str, params: Sequence[Any]=()) -> List[tuple]:
  cur = conn.execute(sql, tuple(params))
  out = cur.fetchall()
  cur.close()
  return out

def get_client_id(conn: sqlite3.Connection, iface: str) -> int:
  r = conn.execute("SELECT id FROM Iface WHERE iface=? LIMIT 1;", (iface,)).fetchone()
  if not r: raise RuntimeError(f"client iface not found: {iface}")
  return int(r[0])

# Tx helpers (optional but nice)
def begin_immediate(conn: sqlite3.Connection) -> None:
  conn.execute("BEGIN IMMEDIATE;")

def commit(conn: sqlite3.Connection) -> None:
  conn.commit()

