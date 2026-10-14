#!/usr/bin/env bash
# usage: sudo ./masu__map_own_all.sh <masu> [--suid=US,x6]
set -euo pipefail
masu="${1:?usage: $0 <masu> [--suid=a,b]}"
suid_list="${2-}"

want_suid_for() {
  [[ "$suid_list" =~ ^--suid= ]] || return 1
  IFS=',' read -r -a arr <<< "${suid_list#--suid=}"
  for n in "${arr[@]}"; do [[ "$n" == "$1" ]] && return 0; done
  return 1
}

subus="$(./masu__subu_data_dir_list.sh "$masu")"
[[ -n "$subus" ]] || { echo "No sub-users found for $masu"; exit 1; }

while IFS= read -r s; do
  [[ -n "$s" ]] || continue
  echo "Opening sub-user: $s"
  if want_suid_for "$s"; then
    sudo ./masu_subu__map_own.sh "$masu" "$s" --suid
  else
    sudo ./masu_subu__map_own.sh "$masu" "$s"
  fi
done <<< "$subus"
