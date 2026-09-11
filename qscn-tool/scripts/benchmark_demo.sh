#!/bin/sh
set -eu

api_base="${QSCN_BENCHMARK_API:-http://127.0.0.1:8000}"
output_dir="${QSCN_BENCHMARK_OUTPUT:-benchmarks}"
mkdir -p "$output_dir"

curl --fail --silent "$api_base/api/readiness" > "$output_dir/readiness.json"

project_json=$(curl --fail --silent -X POST \
  -F "archive=@demo_consortium/demo_consortium.zip" \
  "$api_base/api/projects?name=Q-SCOPE-benchmark")
project_id=$(printf '%s' "$project_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
curl --fail --silent -X POST -H 'Content-Type: application/json' \
  -d '{"input_kind":"protein"}' "$api_base/api/projects/$project_id/preflight" > /dev/null

databases=$(curl --fail --silent "$api_base/api/databases")
for database_id in qsp kegg-m02024; do
  version_id=$(printf '%s' "$databases" | python3 -c \
    'import json,sys; wanted=sys.argv[1]; print(next(x["version_id"] for x in json.load(sys.stdin) if x["database_id"] == wanted))' \
    "$database_id")
  started=$(date +%s)
  run_json=$(curl --fail --silent -X POST -H 'Content-Type: application/json' \
    -d "{\"input_kind\":\"protein\",\"database_version_id\":\"$version_id\"}" \
    "$api_base/api/projects/$project_id/runs")
  run_id=$(printf '%s' "$run_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
  while :; do
    status_json=$(curl --fail --silent "$api_base/api/runs/$run_id")
    status=$(printf '%s' "$status_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')
    case "$status" in
      complete) break ;;
      failed|cancelled) printf '%s\n' "$status_json"; exit 1 ;;
    esac
    sleep 5
  done
  interpretation_id=$(printf '%s' "$status_json" | python3 -c \
    'import json,sys; print(json.load(sys.stdin)["interpretations"][0]["id"])')
  curl --fail --silent \
    "$api_base/api/runs/$run_id/export?interpretation_id=$interpretation_id" \
    -o "$output_dir/$database_id.zip"
  elapsed=$(($(date +%s) - started))
  printf '{"database_id":"%s","run_id":"%s","wall_seconds_observed":%s,"export_bytes":%s}\n' \
    "$database_id" "$run_id" "$elapsed" "$(wc -c < "$output_dir/$database_id.zip")" \
    > "$output_dir/$database_id.summary.json"
done

printf 'Benchmark exports and summaries written to %s\n' "$output_dir"
