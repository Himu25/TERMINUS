#!/usr/bin/env bash
# Frontier-agent difficulty testing (wrapper for agent_test.py).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT/agent_test.py" "$@"
