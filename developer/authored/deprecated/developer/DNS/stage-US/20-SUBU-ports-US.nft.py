# write /etc/nftables.d/20-SUBU-ports.nft — DNS redirect + strict egress
def configure(prov, planner, WriteFileMeta):
    wfm = WriteFileMeta(
        dpath="/etc/nftables.d",
        fname="20-SUBU-ports.nft",
        owner="root",
        mode=0o644,
    )
    planner.displace(wfm)
    planner.copy(wfm, content="""\
# DNS per-UID redirect to local Unbound
table inet SUBU-DNS-REDIRECT {
  chain output {
    type nat hook output priority -100; policy accept;

    # US (uid 2017) -> 127.0.0.1:5301
    meta skuid 2017 udp dport 53 redirect to :5301
    meta skuid 2017 tcp dport 53 redirect to :5301
    # x6 (uid 2018) -> 127.0.0.1:5302
    meta skuid 2018 udp dport 53 redirect to :5302
    meta skuid 2018 tcp dport 53 redirect to :5302
  }
}

# Egress policy: subu UIDs must use their WireGuard iface; block exfil channels
table inet SUBU-PORT-EGRESS {
  chain output {
    type filter hook output priority 0; policy accept;

    # Always allow loopback
    oifname "lo" accept;

    # No IPv6 for subu (until you reintroduce v6)
    meta skuid {2017,2018} meta nfproto ipv6 counter comment "no IPv6 for subu" drop;

    ##### x6 (UID 2018)
    meta skuid 2018 tcp dport {25,465,587}  counter comment "block SMTP/Submission" drop;
    meta skuid 2018 udp dport {3478,5349,19302-19309} counter comment "block STUN/TURN" drop;
    meta skuid 2018 tcp dport 853            counter comment "block DoT (TCP/853)" drop;
    meta skuid 2018 oifname "x6" accept;
    meta skuid 2018 oifname != "x6" counter comment "x6 must use wg x6" drop;

    ##### US (UID 2017)
    meta skuid 2017 tcp dport {25,465,587}  counter comment "block SMTP/Submission" drop;
    meta skuid 2017 udp dport {3478,5349,19302-19309} counter comment "block STUN/TURN" drop;
    meta skuid 2017 tcp dport 853            counter comment "block DoT (TCP/853)" drop;
    meta skuid 2017 oifname "US" accept;
    meta skuid 2017 oifname != "US" counter comment "US must use wg US" drop;
  }
}
""")
