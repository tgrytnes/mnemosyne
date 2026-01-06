#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK="${1:-dev}"

usage() {
  cat <<EOF
Usage: $0 [dev|staging]
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
*)
  usage
  ;;
esac

echo "Stopping Mnemosyne watchers (scheduler + ingest watch)..."
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

IMAGE_TAG_OVERRIDE="${IMAGE_TAG_OVERRIDE:-}"
if [[ -n "$IMAGE_TAG_OVERRIDE" ]]; then
  export IMAGE_TAG="$IMAGE_TAG_OVERRIDE"
elif [[ -n "${IMAGE_TAG:-}" ]]; then
  export IMAGE_TAG="$IMAGE_TAG"
else
  export IMAGE_TAG="latest"
fi

echo "Refreshing the $STACK stack with IMAGE_TAG=$IMAGE_TAG..."
docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" down --remove-orphans

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

docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" pull
docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" up -d

cat <<EOF
$STACK stack refreshed successfully.
Watcher processes restarted. If you prefer to run manually:
  cd $ROOT_DIR
  python -m mnemosyne.cli.scheduler &
  python -m mnemosyne.cli.ingest watch --vault-path "${OBSIDIAN_VAULT_PATH:-/data/vault}" &
EOF

echo "Restarting Mnemosyne watcher processes..."
(
  cd "$ROOT_DIR"
  python -m mnemosyne.cli.scheduler &
  scheduler_pid=$!
  echo "Started scheduler watcher (pid $scheduler_pid)"
  python -m mnemosyne.cli.ingest watch --vault-path "${OBSIDIAN_VAULT_PATH:-/data/vault}" &
  ingest_pid=$!
  echo "Started ingest watcher (pid $ingest_pid)"
)
