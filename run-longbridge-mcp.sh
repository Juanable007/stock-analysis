#!/usr/bin/env bash
set -euo pipefail

# Put Longbridge credentials in this file (not committed):
#   LONGBRIDGE_APP_KEY=...
#   LONGBRIDGE_APP_SECRET=...
#   LONGBRIDGE_ACCESS_TOKEN=...
#   LONGBRIDGE_REGION=hk   # optional, if your server expects it
ENV_FILE="${LONGBRIDGE_ENV_FILE:-/Volumes/samsung/hermes-secrets/longbridge.env}"
JAR="/Users/juanable/Documents/code/stock-analysis/target/hermes-longbridge-mcp-0.1.0.jar"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing credential env file: $ENV_FILE" >&2
  echo "Create it with chmod 600 and the LONGBRIDGE_* variables." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

export HERMES_WHOP_ARCHIVE_DIR="${HERMES_WHOP_ARCHIVE_DIR:-/Users/juanable/Documents/code/stock-analysis/data/whop_archive}"
export HERMES_WHOP_REBUILD_COMMAND="${HERMES_WHOP_REBUILD_COMMAND:-cd /Users/juanable/Documents/code/stock-analysis && python3 tools/build_whop_knowledge.py}"
export HERMES_WHOP_CAPTURE_COMMAND="${HERMES_WHOP_CAPTURE_COMMAND:-cd /Users/juanable/Documents/code/stock-analysis && tools/refresh_whop_knowledge_incremental.sh}"

exec /Users/juanable/.homebrew/opt/openjdk@21/bin/java -jar "$JAR"
