# write /etc/unbound/unbound-US.conf — local listener that egresses via US WG
def configure(prov, planner, WriteFileMeta):
    wfm = WriteFileMeta(
        dpath="/etc/unbound",
        fname="unbound-US.conf",
        owner="root",
        mode=0o644,
    )
    planner.displace(wfm)
    planner.copy(wfm, content="""\
server:
  verbosity: 1
  username: "unbound"
  directory: "/etc/unbound"
  chroot: ""

  do-ip6: no
  do-udp: yes
  do-tcp: yes
  prefer-ip6: no

  # Listen only on loopback (US instance)
  interface: 127.0.0.1@5301
  access-control: 127.0.0.0/8 allow

  # Egress via US tunnel address (policy rules ensure it leaves on wg US)
  outgoing-interface: 10.0.0.1

  # Hardening/cache
  hide-identity: yes
  hide-version: yes
  harden-referral-path: yes
  harden-dnssec-stripped: yes
  qname-minimisation: yes
  aggressive-nsec: yes
  prefetch: yes
  cache-min-ttl: 60
  cache-max-ttl: 86400

  # DNSSEC trust anchor
  auto-trust-anchor-file: "/var/lib/unbound/root.key"
""")
