"""
4.4 domain/options.py

Per-subu options, backed by DB.

4.4.1 set_option(subu_id: str, name: str, value: str) -> None
4.4.2 get_option(subu_id: str, name: str) -> str | None
4.4.3 list_options(subu_id: str) -> dict[str, str]
"""
def option_set(subu_id: str, name: str, value: str):
  sid = int(subu_id.split("_")[1])
  with closing(_db()) as db:
    db.execute("INSERT INTO options (subu_id,name,value) VALUES(?,?,?) "
               "ON CONFLICT(subu_id,name) DO UPDATE SET value=excluded.value",
               (sid, name, value))
    db.commit()
  print("ok")

def option_get(subu_id: str, name: str):
  sid = int(subu_id.split("_")[1])
  with closing(_db()) as db:
    row = db.execute("SELECT value FROM options WHERE subu_id=? AND name=?", (sid,name)).fetchone()
  print(row[0] if row else "")

def option_list(subu_id: str):
  sid = int(subu_id.split("_")[1])
  with closing(_db()) as db:
    rows = db.execute("SELECT name,value FROM options WHERE subu_id=?", (sid,)).fetchall()
  for n,v in rows:
    print(f"{n}={v}")

