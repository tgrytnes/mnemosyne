#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK="${1:-dev}"

usage() {
  cat <<EOF
Usage: $0 [dev|staging|prod]
Pulls the latest image for the chosen stack (defaults to dev), refreshes the compose stack,
and stops the Mnemosyne daemon processes so you can restart them cleanly afterward.
EOF
  exit 1
}

case "$STACK" in
dev)
  ENV_FILE="$ROOT_DIR/.env.dev"
  COMPOSE_FILES=(-f "$ROOT_DIR/docker-compose.yml" -f "$ROOT_DIR/docker-compose.dev.yml")
  ;;
staging)
  ENV_FILE="$ROOT_DIR/.env.staging"
  COMPOSE_FILES=(-f "$ROOT_DIR/docker-compose.yml" -f "$ROOT_DIR/docker-compose.staging.yml")
  ;;
prod)
  ENV_FILE="$ROOT_DIR/.env.prod"
  COMPOSE_FILES=(-f "$ROOT_DIR/docker-compose.yml" -f "$ROOT_DIR/docker-compose.prod.yml")
  ;;
*)
  usage
  ;;
esac

echo "Stopping host watcher processes (if any)..."
if scheduler_pids="$(pgrep -f "mnemosyne.cli.scheduler" || true)"; then
  if [[ -n "$scheduler_pids" ]]; then
    echo "Stopping scheduler watchers (pids: $scheduler_pids)"
  else
    echo "No scheduler watcher process found."
  fi
fi
pkill -f "mnemosyne.cli.scheduler" || true

if ingest_pids="$(pgrep -f "mnemosyne.cli.ingest watch" || true)"; then
  if [[ -n "$ingest_pids" ]]; then
    echo "Stopping ingest watchers (pids: $ingest_pids)"
  else
    echo "No ingest watcher process found."
  fi
fi
pkill -f "mnemosyne.cli.ingest watch" || true

compose() {
  docker compose --env-file "$ENV_FILE" --env-file "$LOCAL_ENV" "${COMPOSE_FILES[@]}" "$@"
}

RUNTIME_IMAGE_TAG_OVERRIDE="${IMAGE_TAG_OVERRIDE:-}"
RUNTIME_IMAGE_TAG="${IMAGE_TAG:-}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Environment file not found: $ENV_FILE" >&2
  exit 1
fi

echo "Loading environment variables from $ENV_FILE"
set -o allexport
source "$ENV_FILE"
set +o allexport

LOCAL_ENV="$ROOT_DIR/.env.${STACK}.local"
if [[ ! -f "$LOCAL_ENV" ]]; then
  echo "Creating missing local override file: $LOCAL_ENV"
  touch "$LOCAL_ENV"
fi
echo "Loading local overrides from $LOCAL_ENV"
set -o allexport
source "$LOCAL_ENV"
set +o allexport

if [[ -n "$RUNTIME_IMAGE_TAG_OVERRIDE" ]]; then
  export IMAGE_TAG="$RUNTIME_IMAGE_TAG_OVERRIDE"
elif [[ -n "$RUNTIME_IMAGE_TAG" ]]; then
  export IMAGE_TAG="$RUNTIME_IMAGE_TAG"
else
  export IMAGE_TAG="latest"
fi

if [[ -z "${COMPOSE_PROJECT_NAME:-}" ]]; then
  COMPOSE_PROJECT_NAME="mnemosyne-${STACK}"
  echo "COMPOSE_PROJECT_NAME not set; defaulting to $COMPOSE_PROJECT_NAME"
fi
export COMPOSE_PROJECT_NAME
echo "Using COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME"

echo "Refreshing the $STACK stack with IMAGE_TAG=$IMAGE_TAG..."
compose down --remove-orphans

check_port_conflicts() {
  local ports=()
  local -A seen=()
  local var val

  for var in WEAVIATE_HOST_PORT WEAVIATE_GRPC_HOST_PORT POSTGRES_HOST_PORT \
    NEO4J_HTTP_HOST_PORT NEO4J_BOLT_HOST_PORT; do
    val="${!var:-}"
    if [[ -n "$val" && -z "${seen[$val]+x}" ]]; then
      ports+=("$val")
      seen["$val"]=1
    fi
  done

  if [[ ${#ports[@]} -eq 0 ]]; then
    echo "No host ports defined for $STACK; skipping conflict checks."
    return 0
  fi

  echo "Checking for port conflicts on host ports: ${ports[*]}"
  mapfile -t docker_lines < <(docker ps --format '{{.ID}}\t{{.Names}}\t{{.Ports}}')

  CONFLICTS=()
  for line in "${docker_lines[@]}"; do
    local id name ports_str port
    id="${line%%$'\t'*}"
    name="${line#*$'\t'}"
    name="${name%%$'\t'*}"
    ports_str="${line#*$'\t'}"
    ports_str="${ports_str#*$'\t'}"
    for port in "${ports[@]}"; do
      if [[ "$ports_str" == *":${port}->"* ]]; then
        CONFLICTS+=("${id}|${name}|${ports_str}|${port}")
      fi
    done
  done
}

resolve_port_conflicts() {
  check_port_conflicts
  if [[ ${#CONFLICTS[@]} -eq 0 ]]; then
    echo "No port conflicts detected."
    return 0
  fi

  for conflict in "${CONFLICTS[@]}"; do
    IFS="|" read -r id name ports_str port <<< "$conflict"
    if [[ "$name" == *mnemosyne* ]]; then
      echo "Stopping conflicting Mnemosyne container: $name (port $port, ports: $ports_str)"
      docker rm -f "$id"
      continue
    fi

    echo "Port $port is in use by non-Mnemosyne container: $name (ports: $ports_str)"
    if [[ ! -t 0 ]]; then
      echo "Non-interactive shell; refusing to stop $name. Aborting."
      exit 1
    fi
    read -r -p "Stop this container? [y/N] " reply
    if [[ "$reply" =~ ^[Yy]$ ]]; then
      docker stop "$id"
    else
      echo "Aborting due to port conflict on $port."
      exit 1
    fi
  done

  check_port_conflicts
  if [[ ${#CONFLICTS[@]} -ne 0 ]]; then
    echo "Port conflicts remain after attempted resolution:"
    printf '  - %s\n' "${CONFLICTS[@]}"
    exit 1
  fi
}

resolve_port_conflicts

compose pull
compose up -d

report_container_status() {
  echo "Container status:"
  compose ps
}

check_watcher_process() {
  local container_id="$1"
  local pattern="$2"
  local label="$3"

  if docker exec "$container_id" pgrep -f "$pattern" >/dev/null 2>&1; then
    echo "$label watcher process detected."
    return 0
  fi

  if docker exec "$container_id" sh -c "ps aux | grep -F \"$pattern\" | grep -v grep" >/dev/null 2>&1; then
    echo "$label watcher process detected via ps."
    return 0
  fi

  echo "$label watcher process not detected."
  return 1
}

verify_watchers() {
  local scheduler_id ingestor_id
  scheduler_id="$(compose ps -q mnemosyne_scheduler)"
  ingestor_id="$(compose ps -q mnemosyne_ingestor)"

  if [[ -z "$scheduler_id" || -z "$ingestor_id" ]]; then
    echo "Watcher containers are not running; cannot verify processes." >&2
    return 1
  fi

  if check_watcher_process "$scheduler_id" "mnemosyne.cli.scheduler" "Scheduler" \
    && check_watcher_process "$ingestor_id" "mnemosyne.cli.ingest watch" "Ingest"; then
    return 0
  fi

  echo "Watcher processes missing; restarting scheduler/ingestor containers once..."
  compose restart mnemosyne_scheduler mnemosyne_ingestor
  sleep 2

  if check_watcher_process "$scheduler_id" "mnemosyne.cli.scheduler" "Scheduler" \
    && check_watcher_process "$ingestor_id" "mnemosyne.cli.ingest watch" "Ingest"; then
    return 0
  fi

  echo "Watcher processes are still missing after restart." >&2
  return 1
}

report_container_status
echo "Verifying watcher processes inside containers..."
if verify_watchers; then
  echo "$STACK stack refreshed successfully. Watchers are running in containers."
else
  echo "$STACK stack refreshed, but watcher validation failed." >&2
  exit 1
fi
