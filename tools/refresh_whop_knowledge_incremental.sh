#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${HERMES_PROJECT_ROOT:-/Users/juanable/Documents/code/stock-analysis}"
cd "$ROOT_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RAW_DIR="data/whop_archive/raw_captures"
PAGES="${WHOP_INCREMENTAL_PAGES:-3}"
FORUM_PAGES="${WHOP_INCREMENTAL_FORUM_PAGES:-3}"
LIMIT="${WHOP_INCREMENTAL_LIMIT:-100}"
FORUM_LIMIT="${WHOP_INCREMENTAL_FORUM_LIMIT:-50}"
DOWNLOAD_IMAGES="${WHOP_REFRESH_DOWNLOAD_IMAGES:-true}"

mkdir -p "$RAW_DIR"
captures=()

ACTIVE_URL="$(osascript -e 'tell application "Google Chrome" to get URL of active tab of front window' 2>/dev/null || true)"
if [[ "$ACTIVE_URL" != https://whop.com/* ]]; then
  printf '{"skipped":true,"reason":"active_chrome_tab_is_not_whop","active_url":"%s"}\n' "$ACTIVE_URL"
  exit 0
fi

fetch_chat() {
  local name="$1"
  local experience_id="$2"
  local output="$RAW_DIR/auto_${STAMP}_${name}_chat_feed_api.json"

  python3 tools/fetch_whop_chat_feed_via_chrome.py \
    --experience-id "$experience_id" \
    --limit "$LIMIT" \
    --pages "$PAGES" \
    --output "$output"
  python3 tools/import_whop_chat_feed_api.py "$output"
  captures+=("$output")
}

fetch_forum() {
  local name="$1"
  local experience_id="$2"
  local output="$RAW_DIR/auto_${STAMP}_${name}_forum_feed_api.json"

  python3 tools/fetch_whop_forum_feed_via_chrome.py \
    --experience-id "$experience_id" \
    --limit "$FORUM_LIMIT" \
    --pages "$FORUM_PAGES" \
    --output "$output"
  python3 tools/import_whop_forum_feed_api.py "$output"
  captures+=("$output")
}

# Priority channels requested for the knowledge base.
fetch_chat "market_cap_theory" "exp_100-50-B3kT9y4dyQGpgy"
fetch_chat "release" "exp_GiWyN1ZTuUjwlG"
fetch_chat "options" "exp_gZyq1MzOZAWO98"
fetch_forum "history" "exp_JG1I58S5zTHbxs"
fetch_chat "discussion" "exp_9vfxZgBNgXykNt"

if [[ "$DOWNLOAD_IMAGES" == "true" ]]; then
  python3 tools/whop_image_pipeline.py import-api-captures --download "${captures[@]}"
else
  python3 tools/whop_image_pipeline.py import-api-captures "${captures[@]}"
fi

python3 tools/build_whop_knowledge.py

python3 tools/whop_image_pipeline.py report
