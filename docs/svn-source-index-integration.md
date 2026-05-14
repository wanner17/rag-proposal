# SVN Source Index Integration

The SVN update batch script should not embed files directly. Its job is to update the working copy, extract changed and deleted relative paths from `svn update`, then call the backend source-index automation endpoint.

Planned endpoint:

```text
POST /api/project-sources/{project_slug}/source-index
```

Payload:

```json
{
  "changed_files": ["src/main/java/App.java"],
  "deleted_files": ["src/main/java/Old.java"],
  "svn_revision": "12345"
}
```

Recommended script pattern:

```bash
export PROJECT_DIR="/opt/rag-projects/e-myjob/trunk"
PROJECT_SLUG="e-myjob-trunk"
BACKEND_URL="http://127.0.0.1:8088"
API_TOKEN="${SOURCE_INDEX_API_TOKEN:-}"
SOURCE_INDEX_CALL_ON_NO_CHANGE="${SOURCE_INDEX_CALL_ON_NO_CHANGE:-1}"

UPDATE_OUTPUT="$(mktemp)"
svn update | tee "$UPDATE_OUTPUT" >> "$LOG_FILE"

REVISION="$(
  sed -nE 's/.*revision ([0-9]+).*/\1/p; s/.*리비전 ([0-9]+).*/\1/p' "$UPDATE_OUTPUT" | tail -1
)"

changed_files=()
deleted_files=()

while IFS= read -r line; do
  status="${line:0:1}"
  path="${line:1}"
  path="${path#"${path%%[![:space:]]*}"}"

  case "$status" in
    A|U|G|R)
      changed_files+=("$path")
      ;;
    D)
      deleted_files+=("$path")
      ;;
    C)
      echo "[RAG] conflict requires manual resolution before indexing: $path" >> "$LOG_FILE"
      ;;
  esac
done < "$UPDATE_OUTPUT"

if [ "${#changed_files[@]}" -gt 0 ] || [ "${#deleted_files[@]}" -gt 0 ] || [ "$SOURCE_INDEX_CALL_ON_NO_CHANGE" = "1" ]; then
  payload="$(
    jq -n \
      --arg revision "$REVISION" \
      --argjson changed "$(printf '%s\n' "${changed_files[@]}" | jq -R . | jq -s .)" \
      --argjson deleted "$(printf '%s\n' "${deleted_files[@]}" | jq -R . | jq -s .)" \
      '{changed_files: $changed, deleted_files: $deleted, svn_revision: $revision}'
  )"

  curl -fsS \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    "$BACKEND_URL/api/project-sources/$PROJECT_SLUG/source-index" \
    >> "$LOG_FILE" 2>&1
else
  echo "[RAG] no changed or deleted source files" >> "$LOG_FILE"
fi

rm -f "$UPDATE_OUTPUT"
```

Notes:
- A reusable version of this pattern is available at `scripts/svn_update_and_index.sh`. Your VPN wrapper can call that script inside the existing `for PROJECT in ...` loop after setting `PROJECT_DIR`, `PROJECT_SLUG`, `BACKEND_URL`, `SOURCE_INDEX_API_TOKEN`, and `LOG_FILE`.
- Keep the backend responsible for path validation, include/exclude filtering, deletion of stale vectors, embedding, and SQLite state updates.
- The script should pass SVN paths relative to the working copy root.
- The endpoint should be called after each successful `svn update`.
- Source-index endpoints accept an admin JWT or `Authorization: Bearer $SOURCE_INDEX_API_TOKEN` when `SOURCE_INDEX_API_TOKEN` is configured on the backend. Use a long random token and keep it out of the script body.
- Let the backend decide initial vs incremental indexing. On the first call for a project, an empty `changed_files`/`deleted_files` request triggers a full source scan; after the project is indexed, empty requests are harmless no-op style maintenance calls.
- The backend container must mount the same source root at `/opt/rag-projects`; `docker-compose.yml` uses `RAG_SOURCE_BASE_PATH` for this.
- If `curl` fails, the script may log the failure and continue to cleanup; the backend repair/reindex endpoints handle later recovery.
- Install `jq` on the batch host, or replace the JSON construction with another safe JSON encoder.
