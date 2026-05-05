#!/usr/bin/env bash
source ~/.bash_profile 2>/dev/null || source ~/.profile 2>/dev/null || true
source ~/.zprofile 2>/dev/null || true
export PATH="$HOME/.local/share/mise/shims:$PATH"
exec uv run "$(dirname "$(realpath "$0")")/run.py"
