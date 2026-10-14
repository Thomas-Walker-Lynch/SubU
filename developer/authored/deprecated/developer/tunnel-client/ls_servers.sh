
# ls_server.sh
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DB="$DIR/db/store"
sqlite3 -noheader -batch "$DB" "SELECT name FROM server ORDER BY name;"
