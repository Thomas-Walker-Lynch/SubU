#!/usr/bin/env python3
# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-
"""CLI.py — subu manager front-end.

Role: parse argv, choose command, call dispatch.

CLI should not do any work beyond:

  * figure out program_name (for example, manager/CLI.py or wrapper name)
  * call the right function in dispatch
  * print text from text.py when needed
  * exit with the returned status code
"""

import os, sys, argparse
from text import make_text
import dispatch


def register_db_commands(subparsers):
  """Register DB-related commands under 'db'.

  db load schema
  """
  ap_db = subparsers.add_parser("db")
  db_sub = ap_db.add_subparsers(dest="db_verb")

  ap = db_sub.add_parser("load")
  ap.add_argument("what", choices=["schema"])


def register_subu_commands(subparsers):
  """Register subu related commands under 'subu':

    subu make <masu> <subu> [<subu>]*
    subu capture <masu> <subu> [<subu>]*
    subu remove <Subu_ID> | <masu> <subu> [<subu>]*
    subu list
    subu info <Subu_ID> | <masu> <subu> [<subu>]*
    subu option set|clear incommon <Subu_ID> | <masu> <subu> [<subu>]*
  """
  ap_subu = subparsers.add_parser("subu")
  subu_sub = ap_subu.add_subparsers(dest="subu_verb")

  # make: path[0] is masu, remaining elements are the subu chain
  ap = subu_sub.add_parser("make")
  ap.add_argument("path", nargs="+")

  # capture: path[0] is masu, remaining elements are the subu chain
  ap = subu_sub.add_parser("capture")
  ap.add_argument("path", nargs="+")

  # remove: either ID or path
  ap = subu_sub.add_parser("remove")
  ap.add_argument("target")
  ap.add_argument("rest", nargs="*")

  # list
  subu_sub.add_parser("list")

  # info
  ap = subu_sub.add_parser("info")
  ap.add_argument("target")
  ap.add_argument("rest", nargs="*")

  # option incommon
  ap = subu_sub.add_parser("option")
  ap.add_argument("opt_action", choices=["set", "clear"])
  ap.add_argument("opt_name", choices=["incommon"])
  ap.add_argument("target")
  ap.add_argument("rest", nargs="*")


def register_wireguard_commands(subparsers):
  """Register WireGuard related commands, grouped under 'WG'."""
  ap = subparsers.add_parser("WG")
  ap.add_argument(
    "wg_verb",
    choices=[
      "global",
      "make",
      "server_provided_public_key",
      "info",
      "information",
      "up",
      "down",
    ],
  )
  ap.add_argument("arg1", nargs="?")
  ap.add_argument("arg2", nargs="?")


def register_attach_commands(subparsers):
  """Register attach and detach commands:

    attach WG <Subu_ID> <WG_ID>
    detach WG <Subu_ID>
  """
  ap = subparsers.add_parser("attach")
  ap.add_argument("what", choices=["WG"])
  ap.add_argument("subu_id")
  ap.add_argument("wg_id")

  ap = subparsers.add_parser("detach")
  ap.add_argument("what", choices=["WG"])
  ap.add_argument("subu_id")


def register_network_commands(subparsers):
  """Register network aggregate commands:

    network up|down <Subu_ID>
  """
  ap = subparsers.add_parser("network")
  ap.add_argument("state", choices=["up", "down"])
  ap.add_argument("subu_id")


def register_option_commands(subparsers):
  """Register global option commands (non-subu-specific for now):

    option set|get|list ...
  """
  ap = subparsers.add_parser("option")
  ap.add_argument("action", choices=["set", "get", "list"])
  ap.add_argument("subu_id")
  ap.add_argument("name", nargs="?")
  ap.add_argument("value", nargs="?")


def register_exec_commands(subparsers):
  """Register exec command:

    exec <Subu_ID> -- <cmd> ...
  """
  ap = subparsers.add_parser("exec")
  ap.add_argument("subu_id")
  ap.add_argument("--", dest="cmd", nargs=argparse.REMAINDER, default=[])


def register_lo_commands(subparsers):
  """Register lo command:

    lo up|down <Subu_ID>
  """
  ap = subparsers.add_parser("lo")
  ap.add_argument("state", choices=["up", "down"])
  ap.add_argument("subu_id")


def build_arg_parser(program_name: str) -> argparse.ArgumentParser:
  """Build the top level argument parser for the subu manager."""
  parser = argparse.ArgumentParser(prog=program_name, add_help=False)
  parser.add_argument("-V", "--Version", action="store_true", help="print version")

  subparsers = parser.add_subparsers(dest="verb")

  register_db_commands(subparsers)
  register_subu_commands(subparsers)
  register_lo_commands(subparsers)
  register_wireguard_commands(subparsers)
  register_attach_commands(subparsers)
  register_network_commands(subparsers)
  register_option_commands(subparsers)
  register_exec_commands(subparsers)

  return parser


def _collect_parse_errors(ns, program_name: str) -> list[str]:
  """Check for semantic argument problems and collect error strings."""
  errors: list[str] = []

  if ns.verb == "subu":
    sv = getattr(ns, "subu_verb", None)
    if sv in ("make", "capture"):
      if not ns.path or len(ns.path) < 2:
        errors.append(
          f"subu {sv} requires at least <masu> and one <subu> component"
        )
    elif sv in ("remove", "info"):
      if ns.target.startswith("subu_"):
        if ns.rest:
          errors.append(
            f"{program_name} subu {sv} with an ID form must not have extra path tokens"
          )
      else:
        if len([ns.target] + list(ns.rest)) < 2:
          errors.append(
            f"{program_name} subu {sv} <masu> <subu> [<subu> ...] requires at least two tokens"
          )
    elif sv == "option":
      # For incommon, same ID vs path rules as info/remove.
      if ns.opt_name == "incommon":
        if ns.target.startswith("subu_"):
          if ns.rest:
            errors.append(
              f"{program_name} subu option {ns.opt_action} incommon with an ID form "
              "must not have extra path tokens"
            )
        else:
          if len([ns.target] + list(ns.rest)) < 2:
            errors.append(
              f"{program_name} subu option {ns.opt_action} incommon "
              "<masu> <subu> [<subu> ...] requires at least two tokens"
            )

  return errors


def CLI(argv=None) -> int:
  """Top level entry point for the subu manager CLI."""
  if argv is None:
    argv = sys.argv[1:]

  prog_override = os.environ.get("SUBU_PROGNAME")
  if prog_override:
    program_name = prog_override
  else:
    raw0 = sys.argv[0] or "subu"
    program_name = os.path.basename(raw0) or "subu"

  text = make_text(program_name)

  # No arguments is the same as "usage".
  if not argv:
    print(text.usage(), end="")
    return 0

  simple = {
    "help": text.help,
    "--help": text.help,
    "-h": text.help,
    "usage": text.usage,
    "example": text.example,
    "version": text.version,
  }
  if argv[0] in simple:
    print(simple[argv[0]](), end="")
    return 0

  parser = build_arg_parser(program_name)
  ns = parser.parse_args(argv)

  if getattr(ns, "Version", False):
    print(text.version(), end="")
    return 0

  errors = _collect_parse_errors(ns, program_name)
  if errors:
    for msg in errors:
      print(f"error: {msg}", file=sys.stderr)
    return 2

  try:
    if ns.verb == "db":
      if ns.db_verb == "load" and ns.what == "schema":
        return dispatch.db_load_schema()

    if ns.verb == "subu":
      sv = ns.subu_verb
      if sv == "make":
        return dispatch.subu_make(ns.path)
      if sv == "capture":
        return dispatch.subu_capture(ns.path)
      if sv == "list":
        return dispatch.subu_list()
      if sv == "info":
        return dispatch.subu_info(ns.target, ns.rest)
      if sv == "remove":
        return dispatch.subu_remove(ns.target, ns.rest)
      if sv == "option":
        # For now only 'incommon' is supported.
        return dispatch.subu_option_incommon(ns.opt_action, ns.target, ns.rest)

    if ns.verb == "lo":
      return dispatch.lo_toggle(ns.subu_id, ns.state)

    if ns.verb == "WG":
      v = ns.wg_verb
      if v in ("info", "information") and ns.arg1 is None:
        print("WG info requires WG_ID", file=sys.stderr)
        return 2
      if v == "global":
        return dispatch.wg_global(ns.arg1)
      if v == "make":
        return dispatch.wg_make(ns.arg1)
      if v == "server_provided_public_key":
        return dispatch.wg_server_public_key(ns.arg1, ns.arg2)
      if v in ("info", "information"):
        return dispatch.wg_info(ns.arg1)
      if v == "up":
        return dispatch.wg_up(ns.arg1)
      if v == "down":
        return dispatch.wg_down(ns.arg1)

    if ns.verb == "attach":
      if ns.what == "WG":
        return dispatch.attach_wg(ns.subu_id, ns.wg_id)

    if ns.verb == "detach":
      if ns.what == "WG":
        return dispatch.detach_wg(ns.subu_id)

    if ns.verb == "network":
      return dispatch.network_toggle(ns.subu_id, ns.state)

    if ns.verb == "option":
      # global options still placeholder
      print("option: not yet implemented", file=sys.stderr)
      return 1

    if ns.verb == "exec":
      if not ns.cmd:
        print(f"{program_name} exec <Subu_ID> -- <cmd> ...", file=sys.stderr)
        return 2
      return dispatch.exec(ns.subu_id, ns.cmd)

    print(text.usage(), end="")
    return 2

  except Exception as e:
    print(f"error: {e}", file=sys.stderr)
    return 1


if __name__ == "__main__":
  sys.exit(CLI())
