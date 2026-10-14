# db_init_server_US.py
from db_init_server_incommon import upsert_server

def init_server_US(conn):
  # Endpoint from the historical config; adjust if needed
  return upsert_server(
    conn,
    client_iface="US",
    server_name="US",
    server_public_key="h8ZYEEVMForvv9p5Wx+9+eZ87t692hTN7sks5Noedw8=",  
    endpoint_host="35.194.71.194",
    endpoint_port=443,
    allowed_ips="0.0.0.0/0",
    keepalive_s=25,
    route_allowed_ips=0,
    priority=100,
  )
