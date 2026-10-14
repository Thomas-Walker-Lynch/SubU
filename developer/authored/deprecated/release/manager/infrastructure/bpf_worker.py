# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-
"""
bpf_worker.py

Cgroup + BPF orchestration for per-subu steering.

5.4.1 ensure_mounts() -> None
5.4.2 install_steering(subu: Subu, wg_iface: str) -> None
5.4.3 remove_steering(subu: Subu) -> None
5.4.4 class BpfError(Exception)
"""
import os, subprocess, json
from pathlib import Path

class BpfError(RuntimeError): pass

def run(cmd, check=True):
  r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
  if check and r.returncode != 0:
    raise BpfError(f"cmd failed: {' '.join(cmd)}\n{r.stderr}")
  return r.stdout.strip()

def ensure_mounts():
  # ensure bpf and cgroup v2 are mounted
  try:
    Path("/sys/fs/bpf").mkdir(parents=True, exist_ok=True)
    run(["mount","-t","bpf","bpf","/sys/fs/bpf"], check=False)
  except Exception:
    pass
  try:
    Path("/sys/fs/cgroup").mkdir(parents=True, exist_ok=True)
    run(["mount","-t","cgroup2","none","/sys/fs/cgroup"], check=False)
  except Exception:
    pass

def cgroup_path(subu_id: str) -> str:
  return f"/sys/fs/cgroup/{subu_id}"

def install_steering(subu_id: str, netns: str, ifname: str):
  ensure_mounts()
  cg = Path(cgroup_path(subu_id))
  cg.mkdir(parents=True, exist_ok=True)

  # compile BPF
  obj = Path("./bpf_force_egress.o")
  src = Path("./bpf_force_egress.c")
  if not src.exists():
    raise BpfError("bpf_force_egress.c missing next to manager")

  # Build object (requires clang/llc/bpftool)
  run(["clang","-O2","-g","-target","bpf","-c",str(src),"-o",str(obj)])

  # Load program into bpffs; attach to cgroup/inet4_connect + inet4_post_bind (MVP)
  pinned = f"/sys/fs/bpf/{subu_id}_egress"
  run(["bpftool","prog","loadall",str(obj),pinned], check=True)

  # Attach to hooks (MVP validation hooks)
  # NOTE: these are safe no-ops for now; they validate UID and stash ifindex map.
  for hook in ("cgroup/connect4","cgroup/post_bind4"):
    run(["bpftool","cgroup","attach",cgroup_path(subu_id),"attach",hook,"pinned",f"{pinned}/prog_0"], check=False)

  # Write metadata for ifname (saved for future prog versions)
  meta = {"ifname": ifname}
  Path(f"/sys/fs/bpf/{subu_id}_meta.json").write_text(json.dumps(meta))

def remove_steering(subu_id: str):
  cg = cgroup_path(subu_id)
  # Detach whatever is attached
  for hook in ("cgroup/connect4","cgroup/post_bind4"):
    subprocess.run(["bpftool","cgroup","detach",cg,"detach",hook], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
  # Remove pinned prog dir
  pinned = Path(f"/sys/fs/bpf/{subu_id}_egress")
  if pinned.exists():
    subprocess.run(["bpftool","prog","detach",str(pinned)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
      for p in pinned.glob("*"): p.unlink()
      pinned.rmdir()
    except Exception:
      pass
  # Remove cgroup dir
  try:
    Path(cg).rmdir()
  except Exception:
    pass
