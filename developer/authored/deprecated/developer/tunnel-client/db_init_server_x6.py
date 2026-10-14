# db_init_server_x6.py
from db_init_server_incommon import upsert_server

def init_server_x6(conn):
  return upsert_server(
    conn,
    client_iface="x6",
    server_name="x6",
    server_public_key="pcbDlC1ZVoBYaN83/zAsvIvhgw0iQOL1YZKX5hcAqno=",
    endpoint_host="66.248.243.113",
    endpoint_port=51820,
    allowed_ips="0.0.0.0/0",
    keepalive_s=25,
    route_allowed_ips=0,
    priority=100,
  )
