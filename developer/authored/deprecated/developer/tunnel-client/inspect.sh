#!/usr/bin/env bash
# inspect.sh — prime sudo only if needed, then run inspect_1.py
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# If not primed, prompt via the tty (works inside Emacs shell without echoing)
if ! sudo -n true 2>/dev/null; then
  sudo echo -n
fi

sudo python3 "${SCRIPT_DIR}/inspect_1.py" "$@"
