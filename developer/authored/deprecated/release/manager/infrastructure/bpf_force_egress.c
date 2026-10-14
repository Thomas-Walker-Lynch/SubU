// -*- mode: c; c-basic-offset: 2; indent-tabs-mode: nil; tab-width: 8 -*-
// bpf_force_egress.c — MVP scaffold to validate UID and prep metadata
/*
  bpf_force_egress.c

5.5.1 no callable Python API; compiled/used via bpf.py.
*/
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>


char LICENSE[] SEC("license") = "GPL";

struct {
  __uint(type, BPF_MAP_TYPE_HASH);
  __type(key, __u32);         // tgid
  __type(value, __u32);       // reserved (target ifindex placeholder)
  __uint(max_entries, 1024);
} subu_tgid2if SEC(".maps");

// Helper: return 0 = allow, <0 reject
static __always_inline int allow_uid(struct bpf_sock_addr *ctx) {
  // MVP: just accept everyone; you can gate on UID 2017 with bpf_get_current_uid_gid()
  // __u32 uid = (__u32)(bpf_get_current_uid_gid() & 0xffffffff);
  // if (uid != 2017) return -1;
  return 0;
}

// Hook: cgroup/connect4 — runs before connect(2) proceeds
SEC("cgroup/connect4")
int subu_connect4(struct bpf_sock_addr *ctx)
{
  if (allow_uid(ctx) < 0) return -1;
  // Future: read pinned map/meta, set SO_* via bpf_setsockopt when permitted
  return 0;
}

// Hook: cgroup/post_bind4 — runs after a local bind is chosen
SEC("cgroup/post_bind4")
int subu_post_bind4(struct bpf_sock *sk)
{
  // Future: enforce bound dev if kernel helper allows; record tgid->ifindex
  __u32 tgid = bpf_get_current_pid_tgid() >> 32;
  __u32 val = 0;
  bpf_map_update_elem(&subu_tgid2if, &tgid, &val, BPF_ANY);
  return 0;
}
