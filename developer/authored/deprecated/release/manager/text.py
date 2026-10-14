# text.py
# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-

"""
text.py — user-facing text for the subu manager CLI.
"""


class _Text:
  def __init__(self, program_name: str):
    self.program_name = program_name
    # Keep version string in one place here for now.
    self._version = "0.3.4"

  # ---- Public API expected by CLI.py ---------------------------------------

  def version(self) -> str:
    """
    Return a short version string suitable for 'PROG version'.
    """
    return f"{self._version}\n"

  def usage(self) -> str:
    """
    Return a short usage summary including the command surface.
    """
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
      "\n"

      f"  {p} subu make <masu> <subu> [<subu> ...]\n"
      f"  {p} subu capture <masu> <subu> [<subu> ...]\n"
      f"  {p} subu list\n"
      f"  {p} subu info subu_<id>\n"
      f"  {p} subu info <masu> <subu> [<subu> ...]\n"
      f"  {p} subu remove subu_<id>\n"
      f"  {p} subu remove <masu> <subu> [<subu> ...]\n"
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

      f"  {p} option set <Subu_ID> <name> <value>\n"
      f"  {p} option get <Subu_ID> <name>\n"
      f"  {p} option list <Subu_ID>\n"
      "\n"

      f"  {p} exec <Subu_ID> -- <cmd> ...\n"
    )

  def help(self) -> str:
    """
    Return a more detailed help text.

    For now this is usage plus a short explanatory block.
    """
    p = self.program_name
    return (
      self.usage()
      + "\n"
      "Notes:\n"
      f"  * '{p} db load schema' must be run as root and will create/update the\n"
      "    manager's SQLite database (schema only).\n"
      "  * 'subu' commands manage subu records and their corresponding Unix users.\n"
      "    They accept either a numeric Subu_ID (e.g. 'subu_3') or a path\n"
      "    (<masu> <subu> [<subu> ...]) where noted.\n"
      "  * WireGuard, attach/detach, network, option, and exec commands are\n"
      "    reserved for managing networking and runtime behavior of existing subu.\n"
      "\n"
    )

  def example(self) -> str:
    """
    Return an example workflow.
    """
    p = self.program_name
    return (
      f"Example workflow:\n"
      "\n"
      f"  # 1. As root, create or update the manager database schema\n"
      f"  sudo {p} db load schema\n"
      "\n"
      f"  # 2. As root, create a developer subu for Thomas\n"
      f"  sudo {p} subu make Thomas developer\n"
      "\n"
      f"  # 3. As root, create a nested subu 'bolt' under Thomas/developer\n"
      f"  sudo {p} subu make Thomas developer bolt\n"
      "\n"
      f"  # 4. As any user, list all known subu\n"
      f"  {p} subu list\n"
      "\n"
      f"  # 5. Show detailed info by path\n"
      f"  {p} subu info Thomas developer bolt\n"
      "\n"
      f"  # 6. Later, remove the nested subu by ID\n"
      f"  sudo {p} subu remove subu_3\n"
      "\n"
    )


def make_text(program_name: str) -> _Text:
  """
  Factory used by CLI.py to get a text provider for the given program name.
  """
  return _Text(program_name)
