#!/usr/bin/env bash
# End-to-end smoke test of the Docker Compose stack (API + worker + Redis).
#
# Builds and starts the stack, generates the synthetic scenarios inside the API
# container, uploads them as one batch, waits for the worker and checks the report.
# Tears the stack down at the end (KEEP_STACK=1 keeps it running).
#
# Requires: docker (with Compose v2), curl, jq.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-90}"
WORK_DIR="$(mktemp -d)"

for tool in docker curl jq; do
  command -v "$tool" >/dev/null || { echo "missing required tool: $tool" >&2; exit 2; }
done

cleanup() {
  local exit_code=$?
  if [ "$exit_code" -ne 0 ]; then
    echo "--- smoke test failed; container logs follow ---" >&2
    docker compose logs --no-color --tail 200 >&2 || true
  fi
  if [ "${KEEP_STACK:-0}" != "1" ]; then
    docker compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "==> building and starting the stack"
docker compose up --build --detach --wait

echo "==> generating synthetic documents"
docker compose exec -T api nfse-audit generate --out /tmp/synthetic
docker compose cp api:/tmp/synthetic "$WORK_DIR/"
expected_documents="$(find "$WORK_DIR/synthetic" -name '*.xml' | wc -l | tr -d ' ')"
expected_scenarios="$(jq '.scenarios | length' "$WORK_DIR/synthetic/manifest.json")"
expected_malformed="$(jq '.malformed | length' "$WORK_DIR/synthetic/manifest.json")"

echo "==> uploading $expected_documents documents"
upload_args=()
for file in "$WORK_DIR"/synthetic/*.xml; do
  upload_args+=(-F "files=@${file};type=application/xml")
done
idempotency_key="smoke-$(date +%s)-$$"
accepted="$(curl -fsS -X POST -H "Idempotency-Key: $idempotency_key" "${upload_args[@]}" "$BASE_URL/batches")"
batch_id="$(jq -r '.batch_id' <<<"$accepted")"
echo "    batch $batch_id"

echo "==> retrying with the same Idempotency-Key"
retried="$(curl -fsS -X POST -H "Idempotency-Key: $idempotency_key" "${upload_args[@]}" "$BASE_URL/batches")"
[ "$(jq -r '.batch_id' <<<"$retried")" = "$batch_id" ] || fail "retry created a new batch"

echo "==> waiting for the worker"
deadline=$((SECONDS + TIMEOUT_SECONDS))
while :; do
  batch="$(curl -fsS "$BASE_URL/batches/$batch_id")"
  state="$(jq -r '.state' <<<"$batch")"
  case "$state" in
    done) break ;;
    failed) fail "batch failed: $(jq -r '.error' <<<"$batch")" ;;
  esac
  [ "$SECONDS" -lt "$deadline" ] || fail "batch still '$state' after ${TIMEOUT_SECONDS}s"
  sleep 1
done
echo "    $(jq -c '.summary' <<<"$batch")"

echo "==> checking the JSON report"
report="$(curl -fsS "$BASE_URL/batches/$batch_id/report")"
[ "$(jq '.summary.documents' <<<"$report")" -eq "$expected_documents" ] || fail "wrong document count"
[ "$(jq '.summary.invoices_audited' <<<"$report")" -eq "$expected_scenarios" ] || fail "wrong invoice count"
[ "$(jq '.summary.documents_with_errors' <<<"$report")" -eq "$expected_malformed" ] || fail "malformed documents not reported"
[ "$(jq '.summary.invoices_divergent' <<<"$report")" -gt 0 ] || fail "no divergence found in the error scenarios"

echo "==> checking the Excel report"
curl -fsS -o "$WORK_DIR/report.xlsx" "$BASE_URL/batches/$batch_id/report?format=xlsx"
[ "$(head -c 2 "$WORK_DIR/report.xlsx")" = "PK" ] || fail "Excel report is not a valid .xlsx (zip) file"

echo "==> smoke test passed"
