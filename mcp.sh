#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$SCRIPT_DIR/taskflow-mcp"
VERSION_FILE="$SCRIPT_DIR/.taskflow/version"
REPO="elpic/taskflow"

# ---------------------------------------------------------------------------
# Detect OS and architecture
# ---------------------------------------------------------------------------
_OS="$(uname -s)"
_ARCH="$(uname -m)"

case "$_OS" in
  Darwin) OS="Darwin" ;;
  Linux)  OS="Linux"  ;;
  *)
    echo "[taskflow] unsupported OS: $_OS" >&2
    exit 1
    ;;
esac

case "$_ARCH" in
  arm64|aarch64) ARCH="arm64" ;;
  x86_64)        ARCH="amd64" ;;
  *)
    echo "[taskflow] unsupported architecture: $_ARCH" >&2
    exit 1
    ;;
esac

# ---------------------------------------------------------------------------
# Resolve the latest release version via a HEAD request redirect
# ---------------------------------------------------------------------------
echo "[taskflow] checking for updates..." >&2

LATEST_URL=$(curl -sI \
  "https://github.com/$REPO/releases/latest/download/taskflow-mcp_latest_${OS}_${ARCH}.tar.gz" \
  2>/dev/null | grep -i '^location:' | tr -d '\r' | awk '{print $2}' || true)

if [ -z "$LATEST_URL" ]; then
  # GitHub unreachable — fall back to existing binary
  if [ -x "$BINARY" ]; then
    echo "[taskflow] could not reach GitHub, using existing binary" >&2
    exec "$BINARY" "$@"
  else
    echo "[taskflow] binary not found and download failed" >&2
    exit 1
  fi
fi

REMOTE_VERSION=$(echo "$LATEST_URL" | sed 's|.*/download/v\([^/]*\)/.*|\1|')

if [ -z "$REMOTE_VERSION" ]; then
  if [ -x "$BINARY" ]; then
    echo "[taskflow] could not parse remote version, using existing binary" >&2
    exec "$BINARY" "$@"
  else
    echo "[taskflow] binary not found and download failed" >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Compare against locally cached version (file read, no subprocess)
# ---------------------------------------------------------------------------
LOCAL_VERSION="none"
if [ -f "$VERSION_FILE" ] && [ -x "$BINARY" ]; then
  LOCAL_VERSION=$(cat "$VERSION_FILE" 2>/dev/null || echo "none")
fi

if [ "$LOCAL_VERSION" = "$REMOTE_VERSION" ]; then
  echo "[taskflow] up to date (v$REMOTE_VERSION)" >&2
  exec "$BINARY" "$@"
fi

# ---------------------------------------------------------------------------
# Download and extract the new binary
# ---------------------------------------------------------------------------
echo "[taskflow] downloading v$REMOTE_VERSION..." >&2

ARCHIVE_NAME="taskflow-mcp_${REMOTE_VERSION}_${OS}_${ARCH}.tar.gz"
DOWNLOAD_URL="https://github.com/$REPO/releases/download/v${REMOTE_VERSION}/$ARCHIVE_NAME"
TMPDIR_PATH="$(mktemp -d)"

cleanup() {
  rm -rf "$TMPDIR_PATH"
}
trap cleanup EXIT

if ! curl -fsSL "$DOWNLOAD_URL" -o "$TMPDIR_PATH/$ARCHIVE_NAME"; then
  echo "[taskflow] download failed" >&2
  if [ -x "$BINARY" ]; then
    echo "[taskflow] falling back to existing binary (v$LOCAL_VERSION)" >&2
    exec "$BINARY" "$@"
  else
    echo "[taskflow] binary not found and download failed" >&2
    exit 1
  fi
fi

tar -xzf "$TMPDIR_PATH/$ARCHIVE_NAME" -C "$TMPDIR_PATH"
chmod +x "$TMPDIR_PATH/taskflow-mcp"
mv "$TMPDIR_PATH/taskflow-mcp" "$BINARY"

# Persist version so next launch skips the download
mkdir -p "$(dirname "$VERSION_FILE")"
echo "$REMOTE_VERSION" > "$VERSION_FILE"

exec "$BINARY" "$@"
