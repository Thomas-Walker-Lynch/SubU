"""
4.5 domain/exec.py

Run a command inside a subu’s namespace and UID.

4.5.1 run_in_subu(subu: Subu, cmd_argv: list[str]) -> int
"""
def exec_in_subu(subu_id: str, cmd: list):
  sid = int(subu_id.split("_")[1])
  with closing(_db()) as db:
    ns = db.execute("SELECT netns FROM subu WHERE id=?", (sid,)).fetchone()[0]
  os.execvp("ip", ["ip","netns","exec", ns] + cmd)
