"""
4.3 domain/network.py

Netns + device wiring, including aggregate “network up/down”.

4.3.1 lo_toggle(subu: Subu, state: str) -> None
4.3.2 attach_wg(subu: Subu, wg: WG) -> None
4.3.3 detach_wg(subu: Subu) -> None
4.3.4 network_toggle(subu: Subu, state: str) -> None
"""
def network_toggle(subu_id: str, state: str):
  sid = int(subu_id.split("_")[1])
  with closing(_db()) as db:
    ns, wid = db.execute("SELECT netns,wg_id FROM subu WHERE id=?", (sid,)).fetchone()
  # always make sure lo up on 'up'
  if state == "up":
    run(["ip", "netns", "exec", ns, "ip", "link", "set", "lo", "up"], check=False)
  if wid is not None:
    ifname = f"subu_{wid}"
    run(["ip", "-n", ns, "link", "set", "dev", ifname, state], check=False)
  with closing(_db()) as db:
    db.execute("UPDATE subu SET network_state=? WHERE id=?", (state, sid))
    db.commit()
  print(f"{subu_id}: network {state}")

def _make_netns_for_subu(subu_id_num: int, netns_name: str):
  """
  Create the network namespace & bring lo down.
  """
  # ip netns add ns-subu_<id>
  run(["ip", "netns", "add", netns_name])
  # ip netns exec ns-subu_<id> ip link set lo down
  run(["ip", "netns", "exec", netns_name, "ip", "link", "set", "lo", "down"])
