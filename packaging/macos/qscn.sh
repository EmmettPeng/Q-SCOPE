#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
COMPOSE_FILE="$SCRIPT_DIR/compose.yml"
ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"
REDIS_IMAGE="redis:7.2.15-alpine@sha256:05a97a479bc73de66f087dc05b569010772880f778cc8671fa6b8aadee32e5c6"

initialize_env() {
  if [ ! -f "$ENV_FILE" ]; then
    [ ! -f "$ENV_EXAMPLE" ] || cp "$ENV_EXAMPLE" "$ENV_FILE"
    return
  fi
  grep -q '^QSCN_IMAGE=' "$ENV_FILE" || return
  backup="$ENV_FILE.v0.3.2.bak"
  [ -f "$backup" ] || cp "$ENV_FILE" "$backup"
  temporary="$ENV_FILE.tmp.$$"
  awk '!/^QSCN_IMAGE=/' "$ENV_FILE" > "$temporary"
  mv "$temporary" "$ENV_FILE"
  printf '%s\n' "Migrated the v0.3 QSCN_IMAGE setting; backup: $backup"
}

compose() {
  docker compose --project-directory "$SCRIPT_DIR" -f "$COMPOSE_FILE" "$@"
}

port() {
  value=""
  if [ -f "$ENV_FILE" ]; then
    value=$(awk -F= '$1 == "QSCN_PORT" {print $2; exit}' "$ENV_FILE" | tr -d '[:space:]')
  fi
  case "${value:-8000}" in
    *[!0-9]*|'') printf '%s\n' "Invalid QSCN_PORT in .env" >&2; exit 1 ;;
    *) printf '%s' "${value:-8000}" ;;
  esac
}

doctor() {
  command -v docker >/dev/null 2>&1 || {
    printf '%s\n' "Docker Desktop is required: https://docs.docker.com/desktop/setup/install/mac-install/" >&2
    exit 1
  }
  docker compose version >/dev/null 2>&1 || {
    printf '%s\n' "Docker Compose v2 is required." >&2
    exit 1
  }
  os_type=$(docker info --format '{{.OSType}}' 2>/dev/null || true)
  [ "$os_type" = "linux" ] || {
    printf '%s\n' "Docker Desktop is not running with a Linux container engine." >&2
    exit 1
  }
  case "$(uname -m)" in
    arm64|x86_64) ;;
    *) printf '%s\n' "Unsupported Mac CPU architecture: $(uname -m)" >&2; exit 1 ;;
  esac
  free_kb=$(df -Pk "$SCRIPT_DIR" | awk 'NR == 2 {print $4}')
  [ "${free_kb:-0}" -ge 41943040 ] || printf '%s\n' "Warning: less than 40 GB free disk space is available." >&2
  memory_bytes=$(sysctl -n hw.memsize 2>/dev/null || printf '0')
  [ "$memory_bytes" -ge 17179869184 ] || printf '%s\n' "Warning: 16 GB host memory is recommended." >&2
}

wait_ready() {
  qscn_port=$(port)
  attempt=0
  while [ "$attempt" -lt 120 ]; do
    if curl --fail --silent --max-time 2 "http://127.0.0.1:${qscn_port}/api/readiness" >/dev/null 2>&1; then
      printf '%s\n' "QSCN is ready at http://127.0.0.1:${qscn_port}"
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 1
  done
  printf '%s\n' "QSCN did not become ready within 120 seconds." >&2
  compose ps >&2 || true
  compose logs --tail=100 app worker redis >&2 || true
  return 1
}

start() {
  doctor
  qscn_port=$(port)
  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$qscn_port" -sTCP:LISTEN >/dev/null 2>&1; then
    if [ -z "$(compose ps -q app 2>/dev/null || true)" ]; then
      printf '%s\n' "Port ${qscn_port} is already in use. Change QSCN_PORT in .env." >&2
      exit 1
    fi
  fi
  compose pull
  compose up -d
  wait_ready
  if [ "${QSCN_NO_BROWSER:-0}" != "1" ]; then
    open "http://127.0.0.1:${qscn_port}"
  fi
}

backup() {
  doctor
  backup_root="${2:-$SCRIPT_DIR/backups}"
  timestamp=$(date -u +%Y%m%dT%H%M%SZ)
  target="$backup_root/qscn-$timestamp"
  mkdir -p "$target"
  compose stop app worker redis
  trap 'compose up -d >/dev/null 2>&1 || true' EXIT INT TERM
  docker run --rm -v qscn_qscn_v03_data:/source:ro -v "$target:/backup" "$REDIS_IMAGE" \
    sh -c 'tar -czf /backup/qscn-data.tar.gz -C /source .'
  docker run --rm -v qscn_qscn_v03_redis:/source:ro -v "$target:/backup" "$REDIS_IMAGE" \
    sh -c 'tar -czf /backup/qscn-redis.tar.gz -C /source .'
  (cd "$target" && shasum -a 256 qscn-data.tar.gz qscn-redis.tar.gz > SHA256SUMS)
  compose up -d
  trap - EXIT INT TERM
  printf '%s\n' "Backup written to $target"
}

restore() {
  doctor
  source_dir="${2:-}"
  [ -n "$source_dir" ] && [ -f "$source_dir/qscn-data.tar.gz" ] && [ -f "$source_dir/qscn-redis.tar.gz" ] || {
    printf '%s\n' "Usage: ./macos/qscn.sh restore /path/to/qscn-backup" >&2
    exit 1
  }
  printf '%s' "This replaces the current QSCN volumes. Type RESTORE to continue: "
  read -r confirmation
  [ "$confirmation" = "RESTORE" ] || { printf '%s\n' "Restore cancelled."; exit 1; }
  source_dir=$(CDPATH= cd -- "$source_dir" && pwd)
  compose down
  docker volume create qscn_qscn_v03_data >/dev/null
  docker volume create qscn_qscn_v03_redis >/dev/null
  docker run --rm -v qscn_qscn_v03_data:/target -v "$source_dir:/backup:ro" "$REDIS_IMAGE" \
    sh -c 'find /target -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -xzf /backup/qscn-data.tar.gz -C /target'
  docker run --rm -v qscn_qscn_v03_redis:/target -v "$source_dir:/backup:ro" "$REDIS_IMAGE" \
    sh -c 'find /target -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -xzf /backup/qscn-redis.tar.gz -C /target'
  compose up -d
  wait_ready
}

initialize_env
command_name="${1:-start}"
case "$command_name" in
  start) start ;;
  stop) compose stop ;;
  status) compose ps ;;
  logs) compose logs --follow --tail=200 app worker redis ;;
  update) doctor; compose pull; compose up -d; wait_ready ;;
  backup) backup "$@" ;;
  restore) restore "$@" ;;
  doctor) doctor; printf '%s\n' "Docker and host checks passed." ;;
  *) printf '%s\n' "Usage: $0 {start|stop|status|logs|update|backup [directory]|restore BACKUP_DIRECTORY|doctor}" >&2; exit 2 ;;
esac
