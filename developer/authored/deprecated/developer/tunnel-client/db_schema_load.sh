#!/usr/bin/env bash
# db_init.sh — create/upgrade db/store by loading schema.sql (idempotent)

set -euo pipefail
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DB="$DIR/db/store"
SCHEMA="$DIR/db_schema.sql"

command -v sqlite3 >/dev/null || { echo "❌ sqlite3 not found"; exit 1; }
[[ -f "$SCHEMA" ]] || { echo "❌ schema file missing: $SCHEMA"; exit 1; }

if [[ -f "$DB" ]]; then
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  cp -f -- "$DB" "$DB.bak-$ts"
  echo "↩︎ Backed up existing DB to $DB.bak-$ts"
fi

sqlite3 -cmd '.bail on' "$DB" < "$SCHEMA"

ver="$(sqlite3 "$DB" 'PRAGMA user_version;')"
echo "✔ DB ready: $DB  (user_version=$ver)"
echo "   Tables:"
sqlite3 -noheader -list "$DB" "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
