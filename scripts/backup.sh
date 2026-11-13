#!/usr/bin/env bash
# Full backup of the order's database to a dated file. Needs SUPABASE_DB_URL (Supabase > Project Settings > Database > Connection string).
# Run it from your own machine; the file holds members' data, so keep it off the repo.
set -euo pipefail
: "${SUPABASE_DB_URL:?Set SUPABASE_DB_URL first (see docs/SECRETS.md)}"
out="backup-$(date -u +%Y%m%d-%H%M).sql.gz"
pg_dump "$SUPABASE_DB_URL" --schema=public --schema=private --no-owner --no-privileges | gzip > "$out"
echo "Wrote $out"
