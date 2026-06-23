#!/usr/bin/env bash
# Stop Harbor/task Docker containers and prune build cache after packaging.
# Usage: ./scripts/cleanup-task-docker.sh [task-name]
#   task-name  optional kebab-case task id (e.g. session-gate-dashboard).
#              When omitted, stops all running containers and prunes builder cache.

set -euo pipefail

TASK_FILTER="${1:-}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found; nothing to clean up"
  exit 0
fi

if ! docker info >/dev/null 2>&1; then
  echo "docker daemon not reachable; skipping cleanup"
  exit 0
fi

stop_and_remove() {
  local ids="$1"
  if [[ -z "${ids}" ]]; then
    return 0
  fi
  # shellcheck disable=SC2086
  docker stop ${ids} >/dev/null 2>&1 || true
  # shellcheck disable=SC2086
  docker rm -f ${ids} >/dev/null 2>&1 || true
}

if [[ -n "${TASK_FILTER}" ]]; then
  ids="$(docker ps -aq --filter "name=${TASK_FILTER}" 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  if [[ -n "${ids}" ]]; then
    echo "Stopping and removing containers for ${TASK_FILTER}..."
    stop_and_remove "${ids}"
  fi
else
  ids="$(docker ps -q 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  if [[ -n "${ids}" ]]; then
    echo "Stopping all running containers..."
    # shellcheck disable=SC2086
    docker stop ${ids} >/dev/null 2>&1 || true
  fi
fi

if pgrep -x harbor >/dev/null 2>&1; then
  echo "Note: harbor process still running (not killed by this script)."
fi

echo "Pruning Docker builder cache..."
docker builder prune -f >/dev/null 2>&1 || true

echo "Docker cleanup done${TASK_FILTER:+ for ${TASK_FILTER}}."
