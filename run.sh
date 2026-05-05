#!/usr/bin/env bash
source ~/.bash_profile 2>/dev/null || source ~/.profile 2>/dev/null || true
source ~/.zprofile 2>/dev/null || true
export PATH="$HOME/.local/share/mise/shims:$PATH"

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
LOG_FILE="$SCRIPT_DIR/.taskflow/server.log"
mkdir -p "$(dirname "$LOG_FILE")"

echo "$(date '+%Y-%m-%dT%H:%M:%S') INFO  run.sh: starting" >> "$LOG_FILE"

if ! command -v uv >/dev/null 2>&1; then
    echo "$(date '+%Y-%m-%dT%H:%M:%S') ERROR run.sh: uv not found in PATH=$PATH" >> "$LOG_FILE"
    exit 1
fi

exec 2>>"$LOG_FILE"
exec uv run "$SCRIPT_DIR/run.py"
