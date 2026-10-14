"""
bpf.py

Compile/load the BPF program.

5.3.1 compile_bpf(source_path: str, output_path: str) -> None
5.3.2 load_bpf(obj_path: str) -> BpfHandle
"""

def attach_wg(subu_id: str, wg_id: str):
  ensure_mounts()
  sid = int(subu_id.split("_")[1]); wid = int(wg_id.split("_")[1])
  with closing(_db()) as db:
    r = db.execute("SELECT netns FROM subu WHERE id=?", (sid,)).fetchone()
    if not r: raise ValueError("subu not found")
    ns = r[0]
    w = db.execute("SELECT endpoint, local_ip, pubkey FROM wg WHERE id=?", (wid,)).fetchone()
    if not w: raise ValueError("WG not found")
    endpoint, local_ip, pubkey = w

  ifname = f"subu_{wid}"
  # make WG link in init ns, move to netns
  run(["ip", "link", "add", ifname, "type", "wireguard"])
  run(["ip", "link", "set", ifname, "netns", ns])
  run(["ip", "-n", ns, "addr", "add", local_ip, "dev", ifname], check=False)
  run(["ip", "-n", ns, "link", "set", "dev", ifname, "mtu", "1420"])
  run(["ip", "-n", ns, "link", "set", "dev", ifname, "down"])  # keep engine down until `network up`

  # install steering (MVP: make cgroup + attach bpf program)
  try:
    install_steering(subu_id, ns, ifname)
    print(f"{subu_id}: eBPF steering installed -> {ifname}")
  except BpfError as e:
    print(f"{subu_id}: steering warning: {e}")

  with closing(_db()) as db:
    db.execute("UPDATE subu SET wg_id=? WHERE id=?", (wid, sid))
    db.commit()
  print(f"attached {wg_id} to {subu_id} in {ns} as {ifname}")

def detach_wg(subu_id: str):
  ensure_mounts()
  sid = int(subu_id.split("_")[1])
  with closing(_db()) as db:
    r = db.execute("SELECT netns,wg_id FROM subu WHERE id=?", (sid,)).fetchone()
    if not r: print("not found"); return
    ns, wid = r
    if wid is None:
      print("nothing attached"); return
  ifname = f"subu_{wid}"
  run(["ip", "-n", ns, "link", "del", ifname], check=False)
  try:
    remove_steering(subu_id)
  except BpfError as e:
    print(f"steering remove warn: {e}")
  with closing(_db()) as db:
    db.execute("UPDATE subu SET wg_id=NULL WHERE id=?", (sid,))
    db.commit()
  print(f"detached WG_{wid} from {subu_id}")

