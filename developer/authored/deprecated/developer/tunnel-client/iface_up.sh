#!/usr/bin/env bash
# iface_up.sh — enable/start wg-quick@<iface>
set -euo pipefail

(( $# == 1 )) || { echo "Usage: $0 <iface>"; exit 2; }
IFACE="$1"

# Require root because systemd + net ops
if [[ $EUID -ne 0 ]]; then
  echo "❌ This script must be run as root." >&2
  exit 1
fi

# Sanity: config must exist
[[ -r "/etc/wireguard/${IFACE}.conf" ]] || {
  echo "❌ Missing: /etc/wireguard/${IFACE}.conf"; exit 1; }

# Bring it up
systemctl enable --now "wg-quick@${IFACE}"

# Quick confirmation
systemctl is-active --quiet "wg-quick@${IFACE}" \
  && echo "✅ ${IFACE} is active." \
  || { echo "⚠️ ${IFACE} failed to start."; exit 1; }
