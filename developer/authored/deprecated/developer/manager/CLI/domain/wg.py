"""
4.2 domain/wg.py

WireGuard objects, independent of subu.

4.2.1 set_global_pool(base_cidr: str) -> None
4.2.2 make_wg(endpoint: str) -> WG
4.2.3 set_server_public_key(wg_id: str, key: str) -> None
4.2.4 get_wg(wg_id: str) -> WG
4.2.5 bring_up(wg_id: str) -> None
4.2.6 bring_down(wg_id: str) -> None
"""

def wg_global(basecidr: str):
  WG_GLOBAL_FILE.write_text(basecidr.strip()+"\n")
  print(f"WG pool base = {basecidr}")

def _alloc_ip(idx: int, base: str) -> str:
  # simplistic /24 allocator: base must be x.y.z.0/24
  prefix = base.split("/")[0].rsplit(".", 1)[0]
  host = 2 + idx
  return f"{prefix}.{host}/32"

def wg_make(endpoint: str) -> str:
  if not WG_GLOBAL_FILE.exists():
    raise RuntimeError("set WG base with `subu WG global <CIDR>` first")
  base = WG_GLOBAL_FILE.read_text().strip()
  with closing(_db()) as db:
    c = db.cursor()
    idx = c.execute("SELECT COUNT(*) FROM wg").fetchone()[0]
    local_ip = _alloc_ip(idx, base)
    c.execute("INSERT INTO wg (endpoint, local_ip, allowed_ips) VALUES (?, ?, ?)",
              (endpoint, local_ip, "0.0.0.0/0"))
    wid = c.lastrowid
    db.commit()
  print(f"WG_{wid} endpoint={endpoint} ip={local_ip}")
  return f"WG_{wid}"

def wg_set_pubkey(wg_id: str, key: str):
  wid = int(wg_id.split("_")[1])
  with closing(_db()) as db:
    db.execute("UPDATE wg SET pubkey=? WHERE id=?", (key, wid))
    db.commit()
  print("ok")

def wg_info(wg_id: str):
  wid = int(wg_id.split("_")[1])
  with closing(_db()) as db:
    row = db.execute("SELECT * FROM wg WHERE id=?", (wid,)).fetchone()
    print(row if row else "not found")

def wg_up(wg_id: str):
  wid = int(wg_id.split("_")[1])
  # Admin-up of WG device handled via network_toggle once attached.
  print(f"{wg_id}: up (noop until attached)")

def wg_down(wg_id: str):
  wid = int(wg_id.split("_")[1])
  print(f"{wg_id}: down (noop until attached)")

