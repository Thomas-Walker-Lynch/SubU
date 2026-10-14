# infrastructure/options_store.py
# -*- mode: python; coding: utf-8; python-indent-offset: 2; indent-tabs-mode: nil -*-

from pathlib import Path

# Options file lives next to CLI in the manager release tree.
# In dev it will be the same relative layout.
OPTIONS_FILE = Path("subu.options")


def load_options():
  """
  Load options from subu.options into a dictionary.

  Lines are of the form: key=value
  Lines starting with '#' or blank lines are ignored.
  """
  opts = {}
  if not OPTIONS_FILE.exists():
    return opts
  text = OPTIONS_FILE.read_text(encoding="utf-8")
  for line in text.splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
      continue
    if "=" not in line:
      continue
    k, v = line.split("=", 1)
    opts[k.strip()] = v.strip()
  return opts


def save_options(opts: dict):
  """
  Save a dictionary of options back to subu.options.
  """
  lines = []
  for k in sorted(opts.keys()):
    v = opts[k]
    lines.append(f"{k}={v}\n")
  OPTIONS_FILE.write_text("".join(lines), encoding="utf-8")


def set_option(name: str, value: str):
  """
  Set a single option key to a value.
  """
  opts = load_options()
  opts[name] = value
  save_options(opts)


def get_option(name: str, default=None):
  """
  Get an option value by name, or default if missing.
  """
  opts = load_options()
  return opts.get(name, default)
