# unbound/unbound_US.py
def configure(prov, planner, WriteFileMeta):
    conf = """server:
  verbosity: 1
  username: "unbound"
  directory: "/etc/unbound"
  chroot: ""

  do-ip6: no
  do-udp: yes
  do-tcp: yes
  prefer-ip6: no

  interface: 127.0.0.1@5301
  access-control: 127.0.0.0/8 allow

  outgoing-interface: 10.0.0.1

  hide-identity: yes
  hide-version: yes
  harden-referral-path: yes
  harden-dnssec-stripped: yes
  qname-minimisation: yes
  aggressive-nsec: yes
  prefetch: yes
  cache-min-ttl: 60
  cache-max-ttl: 86400

  auto-trust-anchor-file: "/var/lib/unbound/root.key"
"""
    wfm = WriteFileMeta(dpath="/etc/unbound", fname="unbound-US.conf",
                        owner="root", mode="0644")
    planner.copy(wfm, content=conf)
