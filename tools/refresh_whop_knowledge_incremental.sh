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
failures=()

WHOP_URL="$(osascript <<'APPLESCRIPT' 2>/dev/null || true
tell application "Google Chrome"
  repeat with w from 1 to count of windows
    repeat with t from 1 to count of tabs of window w
      set tabUrl to URL of tab t of window w
      if tabUrl starts with "https://whop.com/" and tabUrl contains "/app/" then
        set active tab index of window w to t
        set index of window w to 1
        return tabUrl
      end if
    end repeat
  end repeat
  repeat with w from 1 to count of windows
    repeat with t from 1 to count of tabs of window w
      set tabUrl to URL of tab t of window w
      if tabUrl starts with "https://whop.com/" then
        set active tab index of window w to t
        set index of window w to 1
        return tabUrl
      end if
    end repeat
  end repeat
end tell
APPLESCRIPT
)"

if [[ "$WHOP_URL" != https://whop.com/* ]]; then
  printf '{"skipped":true,"reason":"no_open_whop_chrome_tab"}\n'
  exit 0
fi
printf '{"selected_whop_tab":"%s"}\n' "$WHOP_URL"

fetch_chat() {
  local name="$1"
  local experience_id="$2"
  local output="$RAW_DIR/auto_${STAMP}_${name}_chat_feed_api.json"

  python3 tools/fetch_whop_chat_feed_via_chrome.py \
    --experience-id "$experience_id" \
    --limit "$LIMIT" \
    --pages "$PAGES" \
    --output "$output" || return $?
  python3 tools/import_whop_chat_feed_api.py "$output" || return $?
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
    --output "$output" || return $?
  python3 tools/import_whop_forum_feed_api.py "$output" || return $?
  captures+=("$output")
}

run_fetch() {
  local kind="$1"
  local name="$2"
  local experience_id="$3"

  set +e
  if [[ "$kind" == "chat" ]]; then
    fetch_chat "$name" "$experience_id"
  else
    fetch_forum "$name" "$experience_id"
  fi
  local status=$?
  set -e

  if [[ "$status" -ne 0 ]]; then
    failures+=("${name}:${status}")
    printf '{"fetch_failed":true,"name":"%s","kind":"%s","exit_code":%s}\n' "$name" "$kind" "$status"
  fi
}

# Priority channels requested for the knowledge base.
run_fetch "chat" "market_cap_theory" "exp_100-50-B3kT9y4dyQGpgy"
run_fetch "chat" "release" "exp_GiWyN1ZTuUjwlG"
run_fetch "chat" "options" "exp_gZyq1MzOZAWO98"
run_fetch "forum" "history" "exp_JG1I58S5zTHbxs"
run_fetch "chat" "discussion" "exp_9vfxZgBNgXykNt"

if [[ "${#captures[@]}" -gt 0 ]]; then
  if [[ "$DOWNLOAD_IMAGES" == "true" ]]; then
    python3 tools/whop_image_pipeline.py import-api-captures --download "${captures[@]}"
  else
    python3 tools/whop_image_pipeline.py import-api-captures "${captures[@]}"
  fi
else
  printf '{"image_import_skipped":true,"reason":"no_successful_captures"}\n'
fi

python3 tools/build_whop_knowledge.py

python3 tools/whop_image_pipeline.py report

printf '{"completed":true,"successful_captures":%s,"failed_captures":%s}\n' "${#captures[@]}" "${#failures[@]}"
