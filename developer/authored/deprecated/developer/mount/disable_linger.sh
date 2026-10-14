#!/usr/bin/env bash
# disable_linger_subu — turn off systemd --user lingering for all <masu>-* users
# Usage: sudo disable_linger_subu --masu Thomas

set -euo pipefail
MASU=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --masu) MASU="${2:-}"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
[[ -n "$MASU" ]] || { echo "usage: sudo $0 --masu <name>"; exit 2; }
[[ $EUID -eq 0 ]] || { echo "must run as root"; exit 1; }

mapfile -t SUBU_USERS < <(getent passwd | awk -F: -v pfx="^${MASU}-" '$1 ~ pfx {print $1}' | sort)
for u in "${SUBU_USERS[@]}"; do
  echo "loginctl disable-linger $u"
  loginctl disable-linger "$u" || true
done

echo "Current linger files (should be empty or only intentional users):"
ls -1 /var/lib/systemd/linger 2>/dev/null || echo "(none)"
echo "✅ linger disabled for ${#SUBU_USERS[@]} users"
