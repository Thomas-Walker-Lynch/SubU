# systemd/unbound_at_template.py
def configure(prov, planner, WriteFileMeta):
    service = """[Unit]
Description=Unbound DNS (%i)
Documentation=man:unbound(8)
After=network-online.target wg-quick@%i.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/sbin/unbound -d -p -c /etc/unbound/unbound-%i.conf
Restart=on-failure
CapabilityBoundingSet=CAP_NET_BIND_SERVICE CAP_SETGID CAP_SETUID
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
"""
    wfm = WriteFileMeta(dpath="/etc/systemd/system", fname="unbound@.service",
                        owner="root", mode="0644")
    planner.copy(wfm, content=service)
