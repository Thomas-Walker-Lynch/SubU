#!/usr/bin/env bash
# masu__subu_dir_list.sh

set -euo pipefail
user="${1:?usage: $0 <masu>}"

# Prefer the /home/<masu>/subu view; if empty/nonexistent, fall back to subu_data.
list_from_dir() { local d="$1"; [[ -d "$d" ]] && find "$d" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' || true; }

candidates="$(
  list_from_dir "/home/$user/subu"
  [[ -d "/home/$user/subu" && -n "$(ls -A /home/$user/subu 2>/dev/null || true)" ]] || list_from_dir "/home/$user/subu_data"
)"

# Unique, stable order
printf '%s\n' "$candidates" | LC_ALL=C sort -u
