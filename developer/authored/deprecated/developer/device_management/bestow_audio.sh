#!/bin/bash
# give_audio.sh — run as master user "Thomas"
# Usage: ./give_audio.sh <USER>
# Example: ./give_audio.sh Thomas-US   # give card to subuser
#          ./give_audio.sh Thomas      # reclaim for master

set -euo pipefail

target="${1-}"
if [[ -z "$target" ]]; then
  echo "❌ usage: $0 <USER>"; exit 2
fi

master="Thomas"

# don't use sudo -v as it dumps the password into the emacs shell
sudo echo >& /dev/null

run() { echo "+ $*"; eval "$*"; }

# --- sanity checks ---
if ! id "$target" &>/dev/null; then
  echo "❌ user not found: $target"; exit 1
fi
if [[ "$(id -un)" != "$master" ]]; then
  echo "❌ must be run as master user '$master'"; exit 1
fi

# Gather all subusers (Thomas-*)
mapfile -t subusers < <(getent passwd | awk -F: '$1 ~ /^'"$master"'-/ {print $1}' | sort)

stop_master_audio() {
  run "systemctl --user stop pipewire pipewire-pulse wireplumber || true"
}

start_master_audio() {
  # start services (not only sockets) to avoid lazy-activation races
  run "systemctl --user start pipewire.service pipewire-pulse.service wireplumber.service"
}

stop_subu_audio() {
  local u="$1"
  run "sudo machinectl shell ${u}@ /bin/bash -lc 'systemctl --user stop pipewire pipewire-pulse wireplumber || true'"
}

start_subu_audio() {
  local u="$1"
  # Keep subuser from trying to bind to logind (not the active seat)
  run "sudo machinectl shell ${u}@ /bin/bash -lc 'export WIREPLUMBER_DISABLE_PLUGINS=logind; systemctl --user import-environment WIREPLUMBER_DISABLE_PLUGINS; systemctl --user start pipewire.service pipewire-pulse.service wireplumber.service'"
}

# --- stop everyone first (to release ALSA cleanly) ---
stop_master_audio
for u in "${subusers[@]}"; do
  stop_subu_audio "$u"
done

# Small settle time so ALSA reservation clears
sleep 0.5

# --- start only the target ---
if [[ "$target" == "$master" ]]; then
  start_master_audio
else
  # ensure linger for target so user services can run
  run "sudo loginctl enable-linger '$target' || true"
  start_subu_audio "$target"
fi

# --- quick verification (best-effort) ---
if [[ "$target" == "$master" ]]; then
  # Show default sink name (may require pipewire-pulse to be fully up)
  run "pactl info | sed -n 's/^Default Sink: /Default Sink: /p'"
else
  run "sudo machinectl shell ${target}@ /bin/bash -lc 'pactl info | sed -n \\\"s/^Default Sink: /Default Sink: /p\\\"'"
fi
