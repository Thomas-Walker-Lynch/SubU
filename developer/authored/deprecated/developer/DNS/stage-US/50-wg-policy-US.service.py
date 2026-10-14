# /etc/systemd/system/wg-policy-US.service — run after wg-quick@US to install policy rules
def configure(prov, planner, WriteFileMeta):
  content = """[Unit]
Description=Policy routing for Unbound egress (US)
After=wg-quick@US.service
Wants=wg-quick@US.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/wg-policy-US.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
  wfm = WriteFileMeta(dpath="/etc/systemd/system", fname="wg-policy-US.service", owner="root", mode="0644")
  planner.displace(wfm)
  planner.copy(wfm, content=content)
