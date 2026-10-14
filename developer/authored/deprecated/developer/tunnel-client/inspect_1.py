#!/usr/bin/env python3
# inspect.py — deep health: DB + systemd/drop-in + wg + route + uid rules + DNS plug

from __future__ import annotations
import os, sys, re, time, shutil, sqlite3, subprocess
from pathlib import Path
from typing import List, Tuple, Optional
import incommon as ic  # open_db()

# ---------- small shell helpers ----------

def sh(args: List[str]) -> subprocess.CompletedProcess:
  """Run command; never raise; text mode; capture stdout/stderr."""
  return subprocess.run(args, text=True, capture_output=True)

def which(cmd: str) -> bool:
  return shutil.which(cmd) is not None

def print_block(title: str, body: str | None = None) -> None:
  print(f"=== {title} ===")
  if body: print(body.rstrip())
  print()

def format_table(headers: List[str], rows: List[Tuple]) -> str:
  cols = list(zip(*([headers] + [[str(c) for c in r] for r in rows]))) if rows else [headers]
  widths = [max(len(x) for x in col) for col in cols]
  line = lambda r: "  ".join(f"{str(c):<{w}}" for c, w in zip(r, widths))
  out = [line(headers), line(tuple("-"*w for w in widths))]
  for r in rows: out.append(line(tuple("" if c is None else str(c) for c in r)))
  return "\n".join(out)

# ---------- DB helpers ----------

def client_row(conn: sqlite3.Connection, iface: str):
  return conn.execute("""
    SELECT c.iface,
           v.rt_table_name_eff AS rt_table_name,
           c.bound_user, c.bound_uid,
           c.local_address_cidr,
           substr(c.public_key,1,10)||'…' AS pub,
           c.autostart, c.updated_at
      FROM Iface c
      JOIN v_client_effective v ON v.id=c.id
     WHERE c.iface=? LIMIT 1;
  """,(iface,)).fetchone()

def server_rows(conn: sqlite3.Connection, iface: str) -> List[tuple]:
  return conn.execute("""
    SELECT s.name,
           s.endpoint_host || ':' || s.endpoint_port AS endpoint,
           substr(s.public_key,1,10)||'…' AS pub,
           s.allowed_ips, s.keepalive_s, s.priority
      FROM server s
      JOIN Iface c ON c.id=s.iface_id
     WHERE c.iface=?
     ORDER BY s.priority, s.name;
  """,(iface,)).fetchall()

def rtname_and_cidr(conn: sqlite3.Connection, iface: str) -> Tuple[str, str]:
  row = conn.execute("SELECT rt_table_name_eff, local_address_cidr FROM v_client_effective WHERE iface=? LIMIT 1;",(iface,)).fetchone()
  if not row: raise RuntimeError(f"Interface not found in DB: {iface}")
  return str(row[0]), str(row[1])

def bound_uids(conn: sqlite3.Connection, iface: str) -> List[int]:
  rows = conn.execute("""
    SELECT ub.uid
      FROM User ub
      JOIN Iface c ON c.id=ub.iface_id
     WHERE c.iface=? AND ub.uid IS NOT NULL AND ub.uid!=''
     ORDER BY ub.uid;
  """,(iface,)).fetchall()
  return [int(r[0]) for r in rows]

def legacy_bound_uid(conn: sqlite3.Connection, iface: str) -> Optional[int]:
  r = conn.execute("SELECT bound_uid FROM Iface WHERE iface=? AND bound_uid IS NOT NULL AND bound_uid!='';",(iface,)).fetchone()
  return (int(r[0]) if r and r[0] is not None and str(r[0])!="" else None)

def primary_server_ep_and_allowed(conn: sqlite3.Connection, iface: str) -> Tuple[str,str]:
  ep = conn.execute("""
    SELECT s.endpoint_host||':'||s.endpoint_port
      FROM server s JOIN Iface c ON c.id=s.iface_id
     WHERE c.iface=? ORDER BY s.priority, s.name LIMIT 1;
  """,(iface,)).fetchone()
  allow = conn.execute("""
    SELECT s.allowed_ips
      FROM server s JOIN Iface c ON c.id=s.iface_id
     WHERE c.iface=? ORDER BY s.priority, s.name LIMIT 1;
  """,(iface,)).fetchone()
  return (str(ep[0]) if ep and ep[0] else ""), (str(allow[0]) if allow and allow[0] else "")

# ---------- file checks ----------

def check_file(path: str, mode_oct: int, user: str, group: str) -> str:
  p = Path(path)
  if not p.exists(): return f"WARN: missing {path}"
  try:
    st = p.stat()
    actual_mode = st.st_mode & 0o777
    import pwd, grp
    u = pwd.getpwuid(st.st_uid).pw_name
    g = grp.getgrgid(st.st_gid).gr_name
    want = f"{oct(mode_oct)[2:]} {user} {group}"
    got  = f"{oct(actual_mode)[2:]} {u} {g}"
    if actual_mode==mode_oct and u==user and g==group:
      return f"OK: {path} ({got})"
    else:
      return f"WARN: {path} perms/owner {got} (expected {want})"
  except Exception as e:
    return f"WARN: {path} stat error: {e}"

def rt_tables_has(table: str) -> bool:
  try:
    txt = Path("/etc/iproute2/rt_tables").read_text()
  except Exception:
    return False
  pat = re.compile(rf"^\s*\d+\s+{re.escape(table)}\s*$", re.M)
  return pat.search(txt) is not None

# ---------- wg helpers ----------

def wg_present(iface: str) -> bool:
  return Path(f"/sys/class/net/{iface}").exists()

def wg_handshake_age_sec(iface: str) -> Optional[int]:
  cp = sh(["sudo","-n","wg","show",iface,"latest-handshakes"])
  if cp.returncode != 0 or not cp.stdout.strip(): return None
  try:
    epoch = int(cp.stdout.split()[-1])
    if epoch<=0: return None
    return int(time.time()) - epoch
  except Exception:
    return None

def wg_endpoints_joined(iface: str) -> str:
  cp = sh(["sudo","-n","wg","show",iface,"endpoints"])
  if cp.returncode != 0: return ""
  vals = []
  for line in cp.stdout.splitlines():
    parts = line.split()
    if len(parts)>=2: vals.append(parts[1])
  return "".join(vals)

def wg_allowedips_csv(iface: str) -> str:
  cp = sh(["sudo","-n","wg","show",iface,"allowed-ips"])
  if cp.returncode != 0: return ""
  vals=[]
  for line in cp.stdout.splitlines():
    parts = line.split()
    if len(parts)>=2: vals.append(parts[1])
  return ",".join(vals)

# ---------- redact helpers ----------

def redact_conf(text: str) -> str:
  text = re.sub(r"^(PrivateKey\s*=\s*).+$", r"\1<redacted>", text, flags=re.M)
  text = re.sub(r"^(PresharedKey\s*=\s*).+$", r"\1<redacted>", text, flags=re.M)
  return text

def sudo_cat(path: str) -> Optional[str]:
  cp = sh(["sudo","-n","cat", path])
  if cp.returncode != 0: return None
  return cp.stdout

# ---------- main inspect ----------

def inspect_iface(iface: str) -> int:
  # DB open
  with ic.open_db() as conn:
    crow = client_row(conn, iface)
    if not crow:
      print(f"❌ client row not found for iface={iface}", file=sys.stderr); return 1
    srv_rows = server_rows(conn, iface)
    rtname, local_cidr = rtname_and_cidr(conn, iface)
    local_ip = local_cidr.split("/",1)[0]
    db_ep, db_allowed = primary_server_ep_and_allowed(conn, iface)
    uids = bound_uids(conn, iface)
    leg = legacy_bound_uid(conn, iface)
    if leg is not None: uids.append(leg)

  # DB snapshot
  print("=== DB: client '{}' ===".format(iface))
  headers = ["iface","rt_table_name","bound_user","bound_uid","local_address_cidr","pub","autostart","updated_at"]
  print(format_table(headers, [crow]))
  print()
  print(f"--- server for '{iface}' ---")
  if srv_rows:
    print(format_table(["name","endpoint","pub","allowed_ips","keepalive_s","priority"], srv_rows))
  else:
    print("(none)")
  print()

  # systemd + drop-in
  print(f"=== systemd: wg-quick@{iface} ===")
  if which("systemctl"):
    en = sh(["systemctl","is-enabled",f"wg-quick@{iface}"]).stdout.strip()
    ac = sh(["systemctl","is-active", f"wg-quick@{iface}"]).stdout.strip()
    if en: print(en)
    if ac: print(ac)
    drop_dir = f"/etc/systemd/system/wg-quick@{iface}.service.d"
    # common filenames: legacy 'restart.conf' or new '10-postup-IP-scripts.conf'
    candidates = [f"{drop_dir}/restart.conf", f"{drop_dir}/10-postup-IP-scripts.conf"]
    print(f"-- drop-in expected: {candidates[0]}")
    found = [p for p in candidates if Path(p).is_file()]
    if found:
      print("OK: drop-in file exists")
    else:
      print("WARN: drop-in file missing or unreadable")
    dpaths = sh(["systemctl","show",f"wg-quick@{iface}","-p","DropInPaths","--value"]).stdout.strip()
    if dpaths and any(p in dpaths for p in candidates):
      print("OK: drop-in is loaded by systemd")
    else:
      print("WARN: drop-in not reported by systemd (need daemon-reload?)")
  else:
    print("(systemctl not available)")
  print()

  # installed targets
  print("=== installed targets ===")
  print(check_file(f"/etc/wireguard/{iface}.conf", 0o600, "root", "root"))
  # check both possible drop-in names
  d1 = check_file(f"/etc/systemd/system/wg-quick@{iface}.service.d/restart.conf", 0o644, "root", "root")
  d2 = check_file(f"/etc/systemd/system/wg-quick@{iface}.service.d/10-postup-IP-scripts.conf", 0o644, "root", "root")
  # show OK if either exists
  if d1.startswith("OK") or d2.startswith("OK"):
    print(d1 if d1.startswith("OK") else d2)
  else:
    # print both warnings for clarity
    print(d1); print(d2)
  print(check_file("/usr/local/bin/IP_rule_add_UID.sh", 0o500, "root", "root"))
  print(check_file(f"/usr/local/bin/route_init_{iface}.sh", 0o500, "root", "root"))
  print("OK: rt_tables entry for '{}' present".format(rtname) if rt_tables_has(rtname)
        else f"WARN: rt_tables entry for '{rtname}' missing")
  print()

  # wg + addr
  print(f"=== wg + addr: {iface} ===")
  present = wg_present(iface)
  print("(present)" if present else "(interface down or not present)")
  if present:
    has_ip = sh(["ip","-4","addr","show","dev",iface]).stdout.find(f" {local_ip}/")>=0
    print(f"OK: {iface} has {local_ip}" if has_ip else f"WARN: {iface} missing {local_ip}")
    if which("wg"):
      age = wg_handshake_age_sec(iface)
      if age is None:
        print("latest-handshake: none")
      else:
        print(f"latest-handshake: {age}s ago")
        if age>600: print("WARN: handshake is stale (>600s)")
      # endpoint and allowed-ips comparison (requires sudo)
      wg_ep = wg_endpoints_joined(iface)
      if db_ep:
        if wg_ep == db_ep:
          print(f"OK: endpoint matches DB ({wg_ep})")
        else:
          print(f"WARN: endpoint mismatch (wg={wg_ep or 'n/a'} db={db_ep})")
      wg_allowed = wg_allowedips_csv(iface)
      if db_allowed:
        if wg_allowed == db_allowed:
          print(f"OK: allowed-ips match DB ({wg_allowed})")
        else:
          print(f"WARN: allowed-ips mismatch (wg={wg_allowed or 'n/a'} db={db_allowed})")
    else:
      prog = Path(sys.argv[0]).name
      print(f"⚠ need sudo for handshake/peer checks (try: sudo {prog} {iface})")
  print()

  # route table checks
  print(f"=== route: table {rtname} ===")
  rt = sh(["ip","-4","route","show","table",rtname]).stdout
  print(rt or "")
  def_ok = any(re.match(rf"^default\s+dev\s+{re.escape(iface)}\b", ln) for ln in rt.splitlines())
  bh_ok  = any(re.match(r"^blackhole\s+default\b", ln) for ln in rt.splitlines())
  print("OK: default -> {}".format(iface) if def_ok else f"WARN: default route not on {iface}")
  print("OK: blackhole guard present" if bh_ok else "WARN: blackhole guard missing")
  print()

  # uid rules
  print(f"=== ip rules for bound UIDs → table {rtname} ===")
  rules_txt = sh(["ip","-4","rule","show"]).stdout
  if uids:
    for u in uids:
      if re.search(rf"uidrange {u}-{u}.*lookup {re.escape(rtname)}", rules_txt):
        print(f"OK: uid {u} -> table {rtname}")
      else:
        print(f"WARN: missing rule for uid {u} -> table {rtname}")
  else:
    print("(no bound UIDs recorded)")
  print()
  print(f"=== ip rule lines targeting '{rtname}' (all) ===")
  hit_lines = [ln for ln in rules_txt.splitlines() if f"lookup {rtname}" in ln]
  print("\n".join(hit_lines) if hit_lines else "(none)")
  print()

  # DNS leak plug: iptables redirects
  print("=== iptables nat OUTPUT DNS redirect (→ 127.0.0.1:53) ===")
  if which("iptables"):
    nat = sh(["iptables","-t","nat","-S","OUTPUT"]).stdout
    r_udp = re.search(r"-A OUTPUT.*-p udp .* --dport 53 .* REDIRECT .*to-ports 53", nat or "")
    r_tcp = re.search(r"-A OUTPUT.*-p tcp .* --dport 53 .* REDIRECT .*to-ports 53", nat or "")
    print(r_udp.group(0) if r_udp else "WARN: no UDP:53 redirect")
    print(r_tcp.group(0) if r_tcp else "WARN: no TCP:53 redirect")
  else:
    print("(iptables not available)")
  print()

  # on-disk configs (redacted)
  conf = f"/etc/wireguard/{iface}.conf"
  drop_restart = f"/etc/systemd/system/wg-quick@{iface}.service.d/restart.conf"
  drop_postup  = f"/etc/systemd/system/wg-quick@{iface}.service.d/10-postup-IP-scripts.conf"

  print(f"=== file: {conf} (redacted) ===")
  txt = sudo_cat(conf)
  if txt is None:
    print("(missing or unreadable; need sudo to view)")
  else:
    print(redact_conf(txt))
  print()

  pick_drop = drop_restart if Path(drop_restart).exists() else drop_postup
  print(f"=== file: {pick_drop} (hooks) ===")
  txt = sudo_cat(pick_drop)
  if txt is None:
    print("(missing or unreadable; need sudo to view)")
  else:
    # Show only interesting service lines if present
    lines = [ln for ln in txt.splitlines()
             if ln.startswith(("ExecStart","Restart","RestartSec","ExecStartPre","ExecStartPost"))]
    print("\n".join(lines) if lines else txt)
  print()

  # summary verdict
  print("=== summary ===")
  ok = True
  ok &= def_ok
  ok &= bh_ok
  if uids:
    for u in uids:
      if not re.search(rf"uidrange {u}-{u}.*lookup {re.escape(rtname)}", rules_txt): ok = False
  ok &= rt_tables_has(rtname)
  ok &= Path(f"/etc/wireguard/{iface}.conf").exists()
  ok &= (Path(drop_restart).exists() or Path(drop_postup).exists())
  ok &= wg_present(iface)
  if db_ep and which("wg"):
    # If wg is present and sudo works, compare endpoint; otherwise skip
    wg_ep = wg_endpoints_joined(iface)
    if wg_ep and wg_ep != db_ep: ok = False
  print("✅ Looks consistent for '{}'.".format(iface) if ok else "⚠️  Something is off — check WARN lines above.")
  return 0 if ok else 1

# ---------- cli ----------

def main(argv: List[str]) -> int:
  if len(argv)!=1:
    print(f"Usage: {Path(sys.argv[0]).name} <iface>", file=sys.stderr)
    return 2
  try:
    return inspect_iface(argv[0])
  except (sqlite3.Error, FileNotFoundError, RuntimeError) as e:
    print(f"❌ {e}", file=sys.stderr); return 1

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
