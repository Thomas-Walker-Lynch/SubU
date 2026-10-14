#!/usr/bin/env python3
"""
stage_IP_apply_script.py

Given:
  - A SQLite DB (schema you’ve defined), with:
      * Iface(id, iface, local_address_cidr, rt_table_name, rt_table_id)
      * v_iface_effective(id, rt_table_name_eff, local_address_cidr)
      * Route(iface_id, cidr, via, table_name, metric, on_up, on_down)
      * "User"(iface_id, username, uid)  — table formerly User_Binding
      * Meta(key='subu_cidr', value)
  - A list of interface names to include (e.g., ["x6","US"]).

Does:
  - Reads DB once and *synthesizes a single* idempotent runtime script
    that, for the selected interfaces, on each `wg-quick@IFACE` start:
      1) resets IPv4 addresses on the iface (delete-if-present, then add)
      2) ensures all configured routes exist (using `ip -4 route replace`)
      3) resets policy rules by preference number (delete-by-pref, then add)
         with **per-iface prefs** to avoid collisions.
  - Stages that script under: stage/usr/local/bin/<script_name>
  - Stages per-iface systemd drop-ins:
      stage/etc/systemd/system/wg-quick@IFACE.service.d/<prio>-postup-IP-state.conf
    which call the script (default prio = 20).
  - Stages a merged copy of rt_tables (does not write the live /etc/iproute2/rt_tables).

Returns:
  (script_path, notes[list of strings])

Errors:
  - Raises RuntimeError if no interfaces provided or there’s nothing to emit.
  - Does not modify kernel state — this is staging only.

Notes:
  - Addresses: reset pattern (del → add) for deterministic convergence.
  - Routes:    `ip -4 route replace` (best-practice) with tolerant logging.
  - Rules:     reset by `pref` (del-by-pref → add). Prefs are unique per iface:
                 base = 17000 + Iface.id * 10
                 from_pref = base + 0
                 uid_pref  = base + 1
  - The runtime script accepts optional IFACE args to limit application.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import argparse
import sqlite3
import sys

import incommon as ic  # expected: open_db()

ROOT = Path(__file__).resolve().parent
STAGE_ROOT = ROOT / "stage"

RT_TABLES_PATH = Path("/etc/iproute2/rt_tables")


# ---------- helpers for notes ----------

def _stage_note(path: Path, stage_root: Path) -> str:
  """Return a short path like 'stage:/usr/local/bin/apply_IP_state.sh'."""
  try:
    rel = path.relative_to(stage_root)
    return f"stage:/{rel.as_posix()}"
  except ValueError:
    return str(path)


# ---------- rt_tables helpers ----------

def _parse_rt_tables(path: Path) -> Tuple[List[str], Dict[str, int], set[int]]:
  """
  Returns (lines, name_to_num, used_nums).
  Keeps original lines for a non-destructive merge.
  """
  text = path.read_text() if path.exists() else ""
  lines = text.splitlines()
  name_to_num: Dict[str, int] = {}
  used_nums: set[int] = set()
  for ln in lines:
    s = ln.strip()
    if not s or s.startswith("#"):
      continue
    parts = s.split()
    if len(parts) >= 2 and parts[0].isdigit():
      n = int(parts[0]); nm = parts[1]
      if nm not in name_to_num and n not in used_nums:
        name_to_num[nm] = n
        used_nums.add(n)
  return (lines, name_to_num, used_nums)


def _first_free_id(used_nums: Iterable[int], low: int, high: int) -> int:
  used = set(used_nums)
  for n in range(low, high + 1):
    if n not in used:
      return n
  raise RuntimeError(f"no free routing-table IDs in [{low},{high}]")


def _stage_rt_tables(
  stage_root: Path,
  meta: Dict[str, Tuple[int, Optional[int], str, Optional[str]]],
  low: int = 20000,
  high: int = 29999
) -> Tuple[Path, List[str]]:
  """
  Ensure entries for all effective table names present in `meta`.
  Prefer DB rt_table_id when available and not conflicting.
  Write merged file to stage/etc/iproute2/rt_tables.
  Returns (staged_path, notes)
  """
  lines, name_to_num, used_nums = _parse_rt_tables(RT_TABLES_PATH)

  # Build eff_name -> preferred_num mapping (first non-None rt_id wins)
  eff_to_preferred: Dict[str, Optional[int]] = {}
  for _n, (_iid, rtid, eff, _cidr) in meta.items():
    if eff not in eff_to_preferred:
      eff_to_preferred[eff] = rtid if rtid is not None else None

  additions: List[Tuple[int, str]] = []
  for eff_name, preferred_num in eff_to_preferred.items():
    if eff_name in name_to_num:
      continue  # already present
    if preferred_num is not None and preferred_num not in used_nums:
      num = preferred_num
    else:
      num = _first_free_id(used_nums, low, high)
    name_to_num[eff_name] = num
    used_nums.add(num)
    additions.append((num, eff_name))

  out = stage_root / "etc" / "iproute2" / "rt_tables"
  out.parent.mkdir(parents=True, exist_ok=True)

  if not additions:
    # still write a copy of current file so install step is uniform
    out.write_text("\n".join(lines) + ("\n" if lines else ""))
    return (out, ["rt_tables: no additions (kept existing map)"])

  new_lines = list(lines)
  for num, name in sorted(additions):
    new_lines.append(f"{num} {name}")

  out.write_text("\n".join(new_lines) + "\n")
  notes = [f"rt_tables: add {num} {name}" for num, name in sorted(additions)]
  return (out, notes)


# ---------- DB access ----------

def _fetch_meta_subu_cidr(conn: sqlite3.Connection, default="10.0.0.0/24") -> str:
  row = conn.execute("SELECT value FROM Meta WHERE key='subu_cidr' LIMIT 1;").fetchone()
  return str(row[0]) if row and row[0] else default


def _fetch_iface_meta(conn: sqlite3.Connection, iface_names: Sequence[str]) -> Dict[str, Tuple[int, Optional[int], str, Optional[str]]]:
  """
  Return {iface_name -> (iface_id, rt_table_id, rt_table_name_eff, local_address_cidr_or_None)}.
  """
  if not iface_names:
    return {}
  ph = ",".join("?" for _ in iface_names)
  sql = f"""
  SELECT i.id,
         i.iface,
         i.rt_table_id,
         v.rt_table_name_eff,
         NULLIF(TRIM(v.local_address_cidr),'') AS cidr
    FROM Iface i
    JOIN v_iface_effective v ON v.id = i.id
   WHERE i.iface IN ({ph})
   ORDER BY i.id;
  """
  rows = conn.execute(sql, tuple(iface_names)).fetchall()
  out: Dict[str, Tuple[int, Optional[int], str, Optional[str]]] = {}
  for r in rows:
    iface_id = int(r[0]); name = str(r[1])
    rt_id = (int(r[2]) if r[2] is not None else None)
    eff   = str(r[3])
    cidr  = (str(r[4]) if r[4] is not None else None)
    out[name] = (iface_id, rt_id, eff, cidr)
  return out


def _fetch_routes_by_iface_id(
  conn: sqlite3.Connection,
  iface_ids: Sequence[int],
  only_on_up: bool = True
) -> Dict[int, List[Tuple[str, Optional[str], Optional[str], Optional[int]]]]:
  """
  Return {iface_id -> [(cidr, via, table_name_or_None, metric_or_None), ...]}.
  """
  if not iface_ids:
    return {}
  ph = ",".join("?" for _ in iface_ids)
  sql = f"""
  SELECT iface_id,
         cidr,
         NULLIF(TRIM(via),'')        AS via,
         NULLIF(TRIM(table_name),'') AS table_name,
         metric,
         on_up
    FROM Route
   WHERE iface_id IN ({ph})
   ORDER BY id;
  """
  rows = conn.execute(sql, tuple(iface_ids)).fetchall()
  out: Dict[int, List[Tuple[str, Optional[str], Optional[str], Optional[int]]]] = {}
  for iface_id, cidr, via, tname, metric, on_up in rows:
    if only_on_up and int(on_up) != 1:
      continue
    out.setdefault(int(iface_id), []).append(
      (str(cidr),
       (str(via) if via is not None else None),
       (str(tname) if tname is not None else None),
       (int(metric) if metric is not None else None))
    )
  return out


def _fetch_uids_by_iface_id(conn: sqlite3.Connection, iface_ids: Sequence[int]) -> Dict[int, List[int]]:
  """
  Return {iface_id -> [uid, ...]} using table "User".
  """
  if not iface_ids:
    return {}
  ph = ",".join("?" for _ in iface_ids)
  sql = f"""
  SELECT iface_id,
         uid
    FROM "User"
   WHERE iface_id IN ({ph})
     AND uid IS NOT NULL
     AND CAST(uid AS TEXT) != ''
   ORDER BY iface_id, uid;
  """
  rows = conn.execute(sql, tuple(iface_ids)).fetchall()
  out: Dict[int, List[int]] = {}
  for iface_id, uid in rows:
    out.setdefault(int(iface_id), []).append(int(uid))
  return out


# ---------- rendering ----------

def _render_composite_script(
  plan_ifaces: List[str],
  meta: Dict[str, Tuple[int, Optional[int], str, Optional[str]]],
  routes_by_id: Dict[int, List[Tuple[str, Optional[str], Optional[str], Optional[int]]]],
  uids_by_id: Dict[int, List[int]],
  subu_cidr: str
) -> str:
  """
  Build a single bash script that ensures addresses → routes → rules.
  """
  lines: List[str] = [
    "#!/usr/bin/env bash",
    "# apply IP state for selected interfaces (addresses, routes, rules) — idempotent",
    "set -euo pipefail",
    "",
    "ALL_ARGS=(\"$@\")",
    "",
    "want_iface(){",
    "  local t=$1",
    "  if [ ${#ALL_ARGS[@]} -eq 0 ]; then return 0; fi",
    "  for a in \"${ALL_ARGS[@]}\"; do [ \"$a\" = \"$t\" ] && return 0; done",
    "  return 1",
    "}",
    "",
    "exists_iface(){ ip -o link show dev \"$1\" >/dev/null 2>&1; }",
    "",
    "# Reset address: delete the exact CIDR if present, then add it back.",
    "reset_addr(){",
    "  local iface=$1; local cidr=$2",
    "  ip -4 addr del \"$cidr\" dev \"$iface\" >/dev/null 2>&1 || true",
    "  if ip -4 addr add \"$cidr\" dev \"$iface\"; then",
    "    logger \"addr set: $iface $cidr\"",
    "  else",
    "    logger \"addr add failed (non-fatal): $iface $cidr\"",
    "  fi",
    "}",
    "",
    "# Ensure route using replace; log but do not fail the unit if kernel says 'exists'.",
    "ensure_route(){",
    "  local table=$1; local cidr=$2; local dev=$3; local via=${4:-}; local metric=${5:-}",
    "  if [ -n \"$via\" ] && [ -n \"$metric\" ]; then",
    "    if ip -4 route replace \"$cidr\" via \"$via\" dev \"$dev\" table \"$table\" metric \"$metric\" 2>/dev/null; then",
    "      logger \"route ensure: table=$table cidr=$cidr dev=$dev via=$via metric=$metric\"",
    "    else",
    "      logger \"route ensure (tolerated failure): table=$table cidr=$cidr dev=$dev via=$via metric=$metric\"",
    "    fi",
    "  elif [ -n \"$via\" ]; then",
    "    if ip -4 route replace \"$cidr\" via \"$via\" dev \"$dev\" table \"$table\" 2>/dev/null; then",
    "      logger \"route ensure: table=$table cidr=$cidr dev=$dev via=$via\"",
    "    else",
    "      logger \"route ensure (tolerated failure): table=$table cidr=$cidr dev=$dev via=$via\"",
    "    fi",
    "  elif [ -n \"$metric\" ]; then",
    "    if ip -4 route replace \"$cidr\" dev \"$dev\" table \"$table\" metric \"$metric\" 2>/dev/null; then",
    "      logger \"route ensure: table=$table cidr=$cidr dev=$dev metric=$metric\"",
    "    else",
    "      logger \"route ensure (tolerated failure): table=$table cidr=$cidr dev=$dev metric=$metric\"",
    "    fi",
    "  else",
    "    if ip -4 route replace \"$cidr\" dev \"$dev\" table \"$table\" 2>/dev/null; then",
    "      logger \"route ensure: table=$table cidr=$cidr dev=$dev\"",
    "    else",
    "      logger \"route ensure (tolerated failure): table=$table cidr=$cidr dev=$dev\"",
    "    fi",
    "  fi",
    "}",
    "",
    "# Reset a policy rule by numeric preference: delete-by-pref, then add.",
    "reset_IP_rule(){",
    "  # Usage: reset_IP_rule <pref> <rule-args...>",
    "  local pref=$1; shift",
    "  ip -4 rule del pref \"$pref\" >/dev/null 2>&1 || true",
    "  if ip -4 rule add \"$@\" pref \"$pref\"; then",
    "    logger \"rule set: pref=$pref $*\"",
    "  else",
    "    logger \"rule add failed (non-fatal): pref=$pref $*\"",
    "  fi",
    "}",
    "",
  ]

  any_action = False

  # 1) Addresses (reset)
  for name in plan_ifaces:
    _iid, _rtid, rtname, cidr = meta[name]
    if cidr:
      lines += [
        f'if want_iface {name}; then',
        f'  if exists_iface {name}; then reset_addr {name} {cidr}; else logger "skip: iface missing: {name}"; fi',
        'fi'
      ]
      any_action = True

  # 2) Routes
  for name in plan_ifaces:
    iid, _rtid, rtname, _cidr = meta[name]
    rows = routes_by_id.get(iid, [])
    for cidr, via, t_override, metric in rows:
      table_eff = t_override or rtname
      viastr = (via if via is not None else "")
      mstr = (str(metric) if metric is not None else "")
      lines += [
        f'if want_iface {name}; then',
        f'  if exists_iface {name}; then ensure_route "{table_eff}" "{cidr}" "{name}" "{viastr}" "{mstr}"; else logger "skip: iface missing: {name}"; fi',
        'fi'
      ]
      any_action = True

  # 3) Rules (reset by pref: src-cidr, uids, and one global prohibit)
  for name in plan_ifaces:
    iid, _rtid, rtname, cidr = meta[name]

    # Per-iface preference block (no collisions)
    base_pref = 17000 + iid * 10
    from_pref = base_pref + 0
    uid_pref  = base_pref + 1

    if cidr:
      lines += [
        f'if want_iface {name}; then',
        f'  reset_IP_rule {from_pref} from "{cidr}" lookup "{rtname}"',
        'fi'
      ]
      any_action = True

    uids = uids_by_id.get(iid, [])
    for u in uids:
      lines += [
        f'if want_iface {name}; then',
        f'  reset_IP_rule {uid_pref} uidrange "{u}-{u}" lookup "{rtname}"',
        'fi'
      ]
      any_action = True

  if subu_cidr:
    lines += [
      f'reset_IP_rule 18050 from "{subu_cidr}" prohibit'
    ]
    any_action = True

  if not any_action:
    raise RuntimeError("no IP state to emit for requested interfaces")

  lines += [""]
  return "\n".join(lines)


def _write_dropin_for_iface(stage_root: Path ,iface: str ,script_name: str ,priority: int) -> Path:
  # correct systemd path: /etc/systemd/system/wg-quick@IFACE.service.d/
  d = stage_root / "etc" / "systemd" / "system" / f"wg-quick@{iface}.service.d"
  d.mkdir(parents=True ,exist_ok=True)
  p = d / f"{priority}-postup-IP-state.conf"
  content = (
    "[Service]\n"
    f"ExecStartPost=+/usr/local/bin/{script_name} {iface}\n"
  )
  p.write_text(content)
  return p


# ---------- business ----------

def stage_IP_apply_script(
  conn: sqlite3.Connection,
  iface_names: Sequence[str],
  stage_root: Optional[Path] = None,
  script_name: str = "apply_IP_state.sh",
  dropin_priority: int = 20,
  only_on_up: bool = True,
  with_dropins: bool = True,
  dry_run: bool = False
) -> Tuple[Path, List[str]]:
  """
  Plan and stage the unified runtime script, a merged rt_tables, and per-iface drop-ins.
  """
  if not iface_names:
    raise RuntimeError("no interfaces provided")

  meta = _fetch_iface_meta(conn, iface_names)
  if not meta:
    raise RuntimeError("none of the requested interfaces exist in DB")

  # preserve caller order but skip unknowns (already handled above)
  ifaces_in_order = [n for n in iface_names if n in meta]
  iface_ids = [meta[n][0] for n in ifaces_in_order]

  routes_by_id = _fetch_routes_by_iface_id(conn, iface_ids, only_on_up=only_on_up)
  uids_by_id = _fetch_uids_by_iface_id(conn, iface_ids)
  subu_cidr = _fetch_meta_subu_cidr(conn, default="10.0.0.0/24")

  sr = stage_root or STAGE_ROOT
  out = sr / "usr" / "local" / "bin" / script_name
  out.parent.mkdir(parents=True, exist_ok=True)

  content = _render_composite_script(ifaces_in_order, meta, routes_by_id, uids_by_id, subu_cidr)

  notes: List[str] = []
  if dry_run:
    notes.append(f"dry-run: would write {_stage_note(out, sr)}")
    if with_dropins:
      for n in ifaces_in_order:
        notes.append(f"dry-run: would write {_stage_note(sr / 'etc' / 'systemd' / 'system' / f'wg-quick@{n}.service.d' / f'{dropin_priority}-postup-IP-state.conf', sr)}")
    rt_out = sr / "etc" / "iproute2" / "rt_tables"
    notes.append(f"dry-run: would write {_stage_note(rt_out, sr)}")
    return (out, notes)

  # ensure rt_tables entries for the effective names used by these ifaces
  rt_path, rt_notes = _stage_rt_tables(sr, meta)
  notes.extend(rt_notes)
  notes.append(f"staged: {_stage_note(rt_path, sr)}")

  out.write_text(content)
  out.chmod(0o500)
  notes.append(f"staged: {_stage_note(out, sr)}")

  if with_dropins:
    for n in ifaces_in_order:
      dp = _write_dropin_for_iface(sr, n, script_name, dropin_priority)
      notes.append(f"staged: {_stage_note(dp, sr)}")

  return (out, notes)

# Backwards-compatible alias for callers that still import the old name.
stage_ip_apply_script = stage_IP_apply_script


# ---------- CLI ----------

def main(argv=None) -> int:
  ap = argparse.ArgumentParser(description="Stage one script that applies IP addresses, routes, and rules for selected ifaces.")
  ap.add_argument("ifaces", nargs="+", help="interface names to include")
  ap.add_argument("--script-name", default="apply_IP_state.sh")
  ap.add_argument("--dropin-priority", type=int, default=20)
  ap.add_argument("--all", action="store_true", help="include routes where on_up=0 as well")
  ap.add_argument("--no-dropins", action="store_true", help="do not stage systemd drop-ins")
  ap.add_argument("--dry-run", action="store_true")
  args = ap.parse_args(argv)

  with ic.open_db() as conn:
    try:
      out, notes = stage_IP_apply_script(
        conn,
        args.ifaces,
        script_name=args.script_name,
        dropin_priority=args.dropin_priority,
        only_on_up=(not args.all),
        with_dropins=(not args.no_dropins),
        dry_run=args.dry_run
      )
    except Exception as e:
      print(f"error: {e}", file=sys.stderr)
      return 2

  if notes:
    print("\n".join(notes))
  return 0


if __name__ == "__main__":
  sys.exit(main())
