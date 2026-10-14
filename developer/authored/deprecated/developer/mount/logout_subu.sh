#!/usr/bin/env bash
# logout_subu — cleanly stop subu users, tear down bindfs, unbind /home, unmount device, close LUKS
# Usage:
#   sudo logout_subu --masu Thomas --device Eagle [--aggressive] [--dry-run]
#
# Notes:
# - Run from a directory NOT under /home/<masu> (we'll auto 'cd /' if needed).
# - --aggressive enables pkill -KILL fallback if user@ sessions don't exit.
# - --device is the mapname mounted at /mnt/<device> and /dev/mapper/<device>-crypt.

set -euo pipefail

MASU=""
DEVICE=""
AGGR=0
DRY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --masu)   MASU="${2:-}"; shift 2;;
    --device) DEVICE="${2:-}"; shift 2;;
    --aggressive) AGGR=1; shift;;
    --dry-run)   DRY=1; shift;;
    -h|--help)
      grep -E '^(# |#-)' "$0" | sed 's/^# \{0,1\}//'
      exit 0;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ -z "$MASU" ]]; then
  # best guess: current sudo user or login user
  MASU="${SUDO_USER:-${USER:-}}"
  [[ -n "$MASU" ]] || { echo "Set --masu <name>"; exit 2; }
fi

if [[ $EUID -ne 0 ]]; then
  echo "❌ must run as root (sudo)"; exit 1
fi

# If we’re under /home/<masu>, move away so unmount can succeed
if [[ "$(pwd -P)" == /home/${MASU}* ]]; then
  echo "cd /  (leaving $(pwd -P) so unmounts can proceed)"
  [[ $DRY -eq 1 ]] || cd /
fi

say() { printf '%s\n' "$*"; }
doit() { echo "+ $*"; [[ $DRY -eq 1 ]] || eval "$@"; }

# --- enumerate subu users and mountpoints
SUBU_ROOT="/home/${MASU}/subu"
SUBU_DATA="/home/${MASU}/subu_data"

# Users of the form MASU-something that actually exist
mapfile -t SUBU_USERS < <(getent passwd | awk -F: -v pfx="^${MASU}-" '$1 ~ pfx {print $1}' | sort)

# Bindfs targets (reverse depth for unmount)
mapfile -t SUBU_MPS < <(findmnt -Rn -S fuse.* -T "$SUBU_ROOT" -o TARGET 2>/dev/null | \
  awk -F/ '{print NF, $0}' | sort -rn | cut -d" " -f2-)

say "== stop subu systemd user managers =="
for u in "${SUBU_USERS[@]}"; do
  say "terminating user@ for $u"
  doit loginctl terminate-user "$u" || true
done

# wait a moment and optionally KILL leftovers
sleep 0.5
for u in "${SUBU_USERS[@]}"; do
  if loginctl list-users --no-legend | awk '{print $2}' | grep -qx "$u"; then
    if [[ $AGGR -eq 1 ]]; then
      uid="$(id -u "$u" 2>/dev/null || echo "")"
      if [[ -n "$uid" ]]; then
        say "aggressive kill of UID $uid ($u)"
        doit pkill -KILL -u "$uid" || true
      fi
    else
      say "⚠︎ $u still has a user@ manager; rerun with --aggressive to force-kill"
    fi
  fi
done

say "== unmount bindfs subu mounts under $SUBU_ROOT =="
for mp in "${SUBU_MPS[@]}"; do
  say "umount $mp"
  if [[ $DRY -eq 1 ]]; then
    echo "+ umount '$mp'"
  else
    if ! umount "$mp" 2>/dev/null; then
      echo "  (busy) trying lazy umount"
      umount -l "$mp" || true
    fi
  fi
done

# Unmount the MASU home if it is a bind of /mnt/<device>/user_data/<masu>
say "== unmount MASU home bind (if any) =="
if findmnt -n -T "/home/${MASU}" >/dev/null 2>&1; then
  src="$(findmnt -no SOURCE -T "/home/${MASU}")"
  say "/home/${MASU} source: ${src}"
  say "umount /home/${MASU}"
  doit umount "/home/${MASU}" || true
fi

# If a device mapname was provided, unmount and close it
if [[ -n "$DEVICE" ]]; then
  say "== unmount /mnt/${DEVICE} and close LUKS =="
  if findmnt -n "/mnt/${DEVICE}" >/dev/null 2>&1; then
    say "umount /mnt/${DEVICE}"
    doit umount "/mnt/${DEVICE}" || true
  fi
  if cryptsetup status "${DEVICE}-crypt" >/dev/null 2>&1; then
    say "cryptsetup close ${DEVICE}-crypt"
    doit cryptsetup close "${DEVICE}-crypt" || true
  else
    say "crypt mapping ${DEVICE}-crypt not active"
  fi
fi

say "sync disks"
[[ $DRY -eq 1 ]] || sync
say "✅ done"
