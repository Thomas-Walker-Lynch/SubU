#!/usr/bin/env bash
# 2025-09-05
# Debian 12 Setup: WireGuard egress server + one client (safe/idempotent)
set -euo pipefail
umask 0077
[[ $EUID -eq 0 ]] || { echo "❌ run as root"; exit 1; }
run(){ echo "+ $*"; eval "$@"; }

WG_IF="wg0"
WG_PORT="${WG_PORT:-51820}"
WG_DIR="/etc/wireguard"
CLIENT_DIR="/root/wireguard"
CLIENT_NAME="${CLIENT_NAME:-client1}"

SERVER_NET_V4="${SERVER_NET_V4:-10.8.0.0/24}"
SERVER_ADDR_V4="${SERVER_ADDR_V4:-10.8.0.1/24}"
CLIENT_ADDR_V4="${CLIENT_ADDR_V4:-10.8.0.2/32}"

# --- Packages ---
need_pkgs=()
for p in wireguard qrencode iproute2; do command -v ${p%% *} >/dev/null 2>&1 || need_pkgs+=("$p"); done
if ((${#need_pkgs[@]})); then
  DEBIAN_FRONTEND=noninteractive run apt-get update
  run apt-get install -y "${need_pkgs[@]}"
fi

install -d -m 0700 "$WG_DIR" "$CLIENT_DIR"

# --- Detect WAN IF + public IPv4 ---
WAN_IF=$(ip -o -4 route show to default | awk '{print $5; exit}')
[[ -n "${WAN_IF:-}" ]] || { echo "❌ Could not detect WAN interface"; exit 1; }
SERVER_IPv4=$(ip -o -4 addr show dev "$WAN_IF" | awk '{print $4}' | cut -d/ -f1 | head -n1)
[[ -n "${SERVER_IPv4:-}" ]] || SERVER_IPv4="<PASTE_PUBLIC_IP>"

# --- Keys (server) ---
if [[ ! -f "$WG_DIR/server.key" ]]; then
  (umask 077; wg genkey | tee "$WG_DIR/server.key" | wg pubkey > "$WG_DIR/server.pub")
  chmod 600 "$WG_DIR/server.key"
fi
SERVER_PRIV=$(cat "$WG_DIR/server.key")
SERVER_PUB=$(cat "$WG_DIR/server.pub")

# --- Keys (client) ---
if [[ ! -f "$CLIENT_DIR/${CLIENT_NAME}.key" ]]; then
  (umask 077; wg genkey | tee "$CLIENT_DIR/${CLIENT_NAME}.key" | wg pubkey > "$CLIENT_DIR/${CLIENT_NAME}.pub")
  chmod 600 "$CLIENT_DIR/${CLIENT_NAME}.key"
fi
CLIENT_PRIV=$(cat "$CLIENT_DIR/${CLIENT_NAME}.key")
CLIENT_PUB=$(cat "$CLIENT_DIR/${CLIENT_NAME}.pub")

# --- IPv4 forwarding ---
install -d -m 0755 /etc/sysctl.d
cat > /etc/sysctl.d/99-wireguard-forwarding.conf <<'EOF'
net.ipv4.ip_forward=1
# net.ipv6.conf.all.forwarding=1
EOF
sysctl --system >/dev/null

# --- Write server config (backup if existing) ---
CFG="$WG_DIR/${WG_IF}.conf"
if [[ -f "$CFG" ]]; then
  cp -a "$CFG" "$CFG.bak.$(date -u +%Y%m%dT%H%M%SZ)"
fi
cat > "$CFG" <<EOF
[Interface]
PrivateKey = $SERVER_PRIV
Address = $SERVER_ADDR_V4
ListenPort = $WG_PORT
SaveConfig = true

# NAT & forward for IPv4
PostUp   = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -m state --state RELATED,ESTABLISHED -j ACCEPT; iptables -t nat -A POSTROUTING -o $WAN_IF -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -m state --state RELATED,ESTABLISHED -j ACCEPT; iptables -t nat -D POSTROUTING -o $WAN_IF -j MASQUERADE

[Peer]
# $CLIENT_NAME
PublicKey = $CLIENT_PUB
AllowedIPs = $CLIENT_ADDR_V4
EOF
chmod 600 "$CFG"

# --- Client config ---
CLIENT_CFG="$CLIENT_DIR/${CLIENT_NAME}.conf"
cat > "$CLIENT_CFG" <<EOF
[Interface]
PrivateKey = $CLIENT_PRIV
Address = ${CLIENT_ADDR_V4%/*}/24
DNS = 1.1.1.1

[Peer]
PublicKey = $SERVER_PUB
Endpoint = ${SERVER_IPv4}:${WG_PORT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF
chmod 600 "$CLIENT_CFG"

# --- UFW allow if active ---
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw status | grep -q "^${WG_PORT}/udp" || ufw allow "${WG_PORT}/udp" || true
fi

# --- Enable interface ---
run systemctl enable --now wg-quick@"$WG_IF"

# --- Status + QR ---
echo
wg show "$WG_IF" || true
echo
echo "Client file: $CLIENT_CFG"
command -v qrencode >/dev/null 2>&1 && { echo "QR (WireGuard mobile import):"; qrencode -t ansiutf8 < "$CLIENT_CFG"; }
echo
echo "If Endpoint autodetection is wrong, edit it to your public IP or DNS."
