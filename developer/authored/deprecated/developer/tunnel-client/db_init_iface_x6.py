# db_init_iface_x6.py
from db_init_iface import upsert_client

def init_iface_x6(conn):
  # iface x6 with dedicated table 'x6' and host /32
  return upsert_client(conn, iface="x6", rt_table_name="x6")
