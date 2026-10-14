#!/usr/bin/env bash
# set_client_key.sh — replace/set a client's public key on the server
# Usage: set_client_key.sh <client-public-key> [allowed-ips=10.8.0.2/32] [iface=wg0]
# Example: set_client_key.sh 88gTdpESSwAc0iip6tVotc8/taZErY18n3lzrgAd+XY= 10.8.0.2/32 wg0

set -euo pipefail

PUB="${1:-}"
ALLOWED="${2:-10.8.0.2/32}"
IFACE="${3:-wg0}"
CFG="/etc/wireguard/${IFACE}.conf"

[[ $EUID -eq 0 ]] || { echo "❌ Must be run as root."; exit 1; }
command -v wg >/dev/null || { echo "❌ wg not found."; exit 1; }
command -v wg-quick >/dev/null || { echo "❌ wg-quick not found."; exit 1; }

[[ -n "$PUB" ]] || { echo "Usage: $0 <client-public-key> [allowed-ips] [iface]"; exit 2; }
# quick sanity on key length
kl=${#PUB}; [[ $kl -ge 43 && $kl -le 45 ]] || { echo "❌ Public key length looks wrong."; exit 2; }
[[ -f "$CFG" ]] || { echo "❌ Config not found: $CFG"; exit 1; }

# Require the interface to be up (simplest, reliable path)
if ! wg show "$IFACE" >/dev/null 2>&1; then
  echo "❌ Interface $IFACE is not up. Start it first: wg-quick up $IFACE"
  echo "   Or stop it and edit $CFG manually (replace the peer that has AllowedIPs = $ALLOWED)."
  exit 1
fi

# Remove any existing peer that currently owns the same AllowedIPs (typical /32 per client)
while read -r oldkey oldips; do
  if [[ "$oldips" == "$ALLOWED" ]]; then
    echo "→ Removing existing peer $oldkey with AllowedIPs $ALLOWED"
    wg set "$IFACE" peer "$oldkey" remove || true
  fi
done < <(wg show "$IFACE" allowed-ips | awk '{print $1, $2}')

# Add the new peer
wg set "$IFACE" peer "$PUB" allowed-ips "$ALLOWED"

# Persist runtime state back to the config (works great even if SaveConfig=true)
wg-quick save "$IFACE"

echo "✔ Updated $IFACE: set peer $PUB with AllowedIPs $ALLOWED and saved to $CFG"
wg show "$IFACE"
