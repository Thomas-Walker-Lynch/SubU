# text.py
# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-
"""
text.py — user-facing text for the subu manager CLI.
"""

class _Text:
  def __init__(self, program_name: str):
    self.program_name = program_name
    self._version = "0.3.4"

  # ---- Public API expected by CLI.py ---------------------------------------

  def version(self) -> str:
    return f"{self._version}\n"

  def usage(self) -> str:
    p = self.program_name
    v = self._version
    return (
      f"{p} — Subu manager (v{v})\n"
      "\n"
      "Usage:\n"
      f"  {p}                   # usage\n"
      f"  {p} help              # detailed help\n"
      f"  {p} example           # example workflow\n"
      f"  {p} version           # print version\n"
      "\n"
      f"  {p} db load schema\n"
      f"  {p} db migrate subu->subu_node\n"
      "\n"
      f"  {p} device scan [--base-dir DIR]\n"
      f"  {p} device attach <mapname>\n"
      f"  {p} device detach <mapname>\n"
      "\n"
      f"  {p} subu make    <masu> <subu> [<subu> ...]\n"
      f"  {p} subu capture <masu> <subu> [<subu> ...]\n"
      f"  {p} subu list\n"
      f"  {p} subu info    subu_<id>\n"
      f"  {p} subu info    <masu> <subu> [<subu> ...]\n"
      f"  {p} subu remove  subu_<id>\n"
      f"  {p} subu remove  <masu> <subu> [<subu> ...]\n"
      f"  {p} subu option set   incommon subu_<id>\n"
      f"  {p} subu option set   incommon <masu> <subu> [<subu> ...]\n"
      f"  {p} subu option clear incommon subu_<id>\n"
      f"  {p} subu option clear incommon <masu> <subu> [<subu> ...]\n"
      "\n"
      f"  {p} lo up|down <Subu_ID>\n"
      "\n"
      f"  {p} WG global <BaseCIDR>\n"
      f"  {p} WG make <host:port>\n"
      f"  {p} WG server_provided_public_key <WG_ID> <Base64Key>\n"
      f"  {p} WG info|information <WG_ID>\n"
      f"  {p} WG up <WG_ID>\n"
      f"  {p} WG down <WG_ID>\n"
      "\n"
      f"  {p} attach WG <Subu_ID> <WG_ID>\n"
      f"  {p} detach WG <Subu_ID>\n"
      "\n"
      f"  {p} network up|down <Subu_ID>\n"
      "\n"
      f"  {p} option set  <Subu_ID> <name> <value>\n"
      f"  {p} option get  <Subu_ID> <name>\n"
      f"  {p} option list <Subu_ID>\n"
      "\n"
      f"  {p} exec <Subu_ID> -- <cmd> ...\n"
    )

  def help(self) -> str:
    p = self.program_name
    return (
      self.usage()
      + "\n"
      "Notes:\n"
      f"  * '{p} db load schema' must be run as root; it creates/updates the SQLite schema.\n"
      f"  * '{p} db migrate subu->subu_node' migrates legacy flat rows into the hierarchical table.\n"
      "  * Device commands work on already-mounted mapnames under /mnt (v1). 'scan' discovers\n"
      "    /mnt/<mapname>/user_data and captures all <masu>/subu_data trees into the DB.\n"
      "  * 'subu' commands manage both DB rows and their corresponding Unix users/groups.\n"
      "    You may address a subu by numeric ID (e.g. 'subu_3') or by path tokens:\n"
      "       <masu> <subu> [<subu> ...]\n"
      "    Path tokens must be non-empty and contain no underscore '_'. Proper nouns/acronyms\n"
      "    may be capitalized; hyphens are allowed inside tokens.\n"
      "  * 'subu option incommon' grants or revokes g+rx on the chosen subu home and adjusts\n"
      "    sibling subu group membership under the same <masu> (see policy in infrastructure/unix.py).\n"
      "  * WireGuard, attach/detach, network, option, and exec manage runtime properties of existing subu.\n"
      "\n"
    )

  def example(self) -> str:
    p = self.program_name
    return (
      "Example workflow:\n"
      "\n"
      f"  # 1) Initialize schema (root)\n"
      f"  sudo {p} db load schema\n"
      "\n"
      f"  # 2) Scan devices already mounted under /mnt (root)\n"
      f"  sudo {p} device scan\n"
      "\n"
      f"  # 3) Capture a legacy subu present in /home/<masu>/subu_data (root)\n"
      f"  sudo {p} subu capture Thomas developer\n"
      "\n"
      f"  # 4) List everything (any user)\n"
      f"  {p} subu list\n"
      "\n"
      f"  # 5) Make a nested subu and then mark a top-level as incommon (root)\n"
      f"  sudo {p} subu make Thomas developer bolt\n"
      f"  sudo {p} subu option set incommon Thomas developer\n"
      "\n"
      f"  # 6) Query by ID or by path (any user)\n"
      f"  {p} subu info subu_7\n"
      f"  {p} subu info Thomas developer bolt\n"
      "\n"
    )

def make_text(program_name: str) -> _Text:
  return _Text(program_name)
