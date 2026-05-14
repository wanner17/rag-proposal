#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_DIR:?PROJECT_DIR is required}"
: "${PROJECT_SLUG:?PROJECT_SLUG is required}"
: "${SOURCE_INDEX_API_TOKEN:?SOURCE_INDEX_API_TOKEN is required}"

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8088}"
LOG_FILE="${LOG_FILE:-/opt/logs/svn-batch-update.log}"
SOURCE_INDEX_CALL_ON_NO_CHANGE="${SOURCE_INDEX_CALL_ON_NO_CHANGE:-1}"

UPDATE_OUTPUT="$(mktemp)"

cleanup() {
  rm -f "$UPDATE_OUTPUT"
}
trap cleanup EXIT

json_array() {
  if [ "$#" -eq 0 ]; then
    printf '[]'
    return
  fi
  printf '%s\0' "$@" | jq -Rs 'split("\u0000")[:-1]'
}

post_source_index() {
  local revision="$1"

  local changed_json deleted_json payload
  changed_json="$(json_array "${changed_files[@]}")"
  deleted_json="$(json_array "${deleted_files[@]}")"
  payload="$(
    jq -n \
      --arg revision "$revision" \
      --argjson changed "$changed_json" \
      --argjson deleted "$deleted_json" \
      '{
        changed_files: $changed,
        deleted_files: $deleted,
        svn_revision: (if $revision == "" then null else $revision end)
      }'
  )"

  curl -fsS \
    -H "Authorization: Bearer $SOURCE_INDEX_API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    "$BACKEND_URL/api/project-sources/$PROJECT_SLUG/source-index" \
    >> "$LOG_FILE" 2>&1
}

echo "[SVN] updating $PROJECT_DIR" >> "$LOG_FILE"
cd "$PROJECT_DIR"

svn update 2>&1 | tee -a "$LOG_FILE" > "$UPDATE_OUTPUT"

revision="$(
  sed -nE 's/.*revision ([0-9]+).*/\1/p; s/.*리비전 ([0-9]+).*/\1/p' "$UPDATE_OUTPUT" | tail -1
)"

changed_files=()
deleted_files=()
conflicted_files=()

while IFS= read -r line; do
  [ -n "$line" ] || continue
  [[ "$line" =~ ^[AUGRDC][[:space:]]+ ]] || continue

  status="${line:0:1}"
  path="${line:1}"
  path="${path#"${path%%[![:space:]]*}"}"
  [ -n "$path" ] || continue

  case "$status" in
    A|U|G|R)
      changed_files+=("$path")
      ;;
    D)
      deleted_files+=("$path")
      ;;
    C)
      conflicted_files+=("$path")
      ;;
  esac
done < "$UPDATE_OUTPUT"

if [ "${#conflicted_files[@]}" -gt 0 ]; then
  printf '[RAG] conflict requires manual resolution before indexing: %s\n' \
    "${conflicted_files[@]}" >> "$LOG_FILE"
fi

if [ "${#changed_files[@]}" -gt 0 ] || [ "${#deleted_files[@]}" -gt 0 ]; then
  echo "[RAG] indexing changed=${#changed_files[@]} deleted=${#deleted_files[@]} revision=${revision:-unknown}" >> "$LOG_FILE"
  post_source_index "$revision"
elif [ "$SOURCE_INDEX_CALL_ON_NO_CHANGE" = "1" ]; then
  echo "[RAG] no SVN changes; calling source-index endpoint for initial full-scan check" >> "$LOG_FILE"
  post_source_index "$revision"
else
  echo "[RAG] no changed or deleted source files" >> "$LOG_FILE"
fi

echo "[SVN] completed $PROJECT_DIR" >> "$LOG_FILE"
