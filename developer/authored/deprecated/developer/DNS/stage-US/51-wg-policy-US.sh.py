# /usr/local/sbin/wg-policy-US.sh — source-policy routing for Unbound's egress
def configure(prov, planner, WriteFileMeta):
  # EDIT if your interface/IP differ:
  WG_IFACE = "US"
  WG_SRC_IP = "10.0.0.1"
  TABLE = 100

  content = f"""#!/usr/bin/env bash
set -euo pipefail
WG_IFACE="{WG_IFACE}"
WG_SRC_IP="{WG_SRC_IP}"
TABLE={TABLE}

ip rule replace from "$WG_SRC_IP" lookup "$TABLE" priority 10010
ip route replace default dev "$WG_IFACE" table "$TABLE"
"""
  wfm = WriteFileMeta(dpath="/usr/local/sbin", fname="wg-policy-US.sh", owner="root", mode="0755")
  planner.displace(wfm)
  planner.copy(wfm, content=content)
