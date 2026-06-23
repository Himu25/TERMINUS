#!/usr/bin/env bash
# Prune stopped containers and unused images. Intended for launchd (every 15 min).

set -euo pipefail

LOG="${HOME}/Library/Logs/docker-prune-periodic.log"

if ! command -v docker >/dev/null 2>&1; then
  exit 0
fi

if ! docker info >/dev/null 2>&1; then
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') docker daemon not reachable; skipping" >>"${LOG}"
  exit 0
fi

{
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
  docker container prune -f
  docker image prune -a -f
} >>"${LOG}" 2>&1
