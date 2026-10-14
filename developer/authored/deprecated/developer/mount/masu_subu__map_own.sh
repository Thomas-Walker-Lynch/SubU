#!/usr/bin/env bash
# usage: sudo ./masu_subu__map_own.sh <masu> <subu> [--suid]
set -euo pipefail

masu="${1:?usage: $0 <masu> <subu> [--suid]}"
subu="${2:?usage: $0 <masu> <subu> [--suid]}"
want_suid=0; [[ "${3-}" == "--suid" ]] && want_suid=1

need(){ command -v "$1" >/dev/null 2>&1 || { echo "missing: $1" >&2; exit 1; }; }
need bindfs; need findmnt; need umount

src="/home/$masu/subu_data/$subu"
mp="/home/$masu/subu/$subu"
[[ -d "$src" ]] || { echo "❌ source not found: $src" >&2; exit 1; }
mkdir -p "$mp"

# mount options
base_opts="allow_other,default_permissions,exec"
opts="$base_opts,$([[ $want_suid -eq 1 ]] && echo suid || echo nosuid)"

# fully unstack any prior bindfs at the target
while findmnt -rn -T "$mp" -t fuse.bindfs >/dev/null 2>&1; do
  umount "$mp" 2>/dev/null || umount -l "$mp" || break
  sleep 0.1
done

echo "mounting $src -> $mp  (opts: $opts)"
bindfs -o "$opts" --map="${masu}-${subu}/${masu}:@${masu}-${subu}/@${masu}" "$src" "$mp"

# verify (single line, kernel-only)
findmnt -rn -T "$mp" -S "$src" -o TARGET,SOURCE,FSTYPE,OPTIONS | head -n1
echo "OK"
if [[ $want_suid -eq 1 ]]; then
  echo "note: suid enabled at $mp"
else
  echo "note: nosuid (default) — setuid will NOT take effect at $mp"
fi
