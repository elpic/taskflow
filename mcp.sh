#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$SCRIPT_DIR/taskflow-mcp"

if [ ! -x "$BINARY" ]; then
  echo "[taskflow] binary not found: $BINARY" >&2
  echo "[taskflow] run /taskflow:update in Claude Code to download the latest binary" >&2
  exit 1
fi

exec "$BINARY" "$@"
