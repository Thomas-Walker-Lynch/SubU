# db_init_iface_US.py
from db_init_iface import upsert_client

def init_iface_US(conn):
  # iface US with dedicated table 'US' and a distinct host /32
  return upsert_client(conn, iface="US", rt_table_name="US")
