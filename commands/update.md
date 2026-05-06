---
name: update
description: "Update the taskflow-mcp binary to the latest GitHub release"
---

Update the taskflow MCP binary. Follow these steps exactly:

## Step 1: Detect platform

Run `uname -s` and `uname -m` to get OS and architecture, then map:
- Darwin → Darwin, Linux → Linux
- arm64/aarch64 → arm64, x86_64 → amd64

## Step 2: Resolve latest version

Run:
```bash
curl -sI "https://github.com/elpic/taskflow/releases/latest/download/taskflow-mcp_latest_<OS>_<ARCH>.tar.gz" 2>/dev/null | grep -i '^location:' | tr -d '\r' | awk '{print $2}'
```
(substitute the actual OS/arch detected above)

Extract the version from the `Location` URL: the segment after `/download/v` and before the next `/`.

## Step 3: Check current version

Run `taskflow-mcp --version` if the binary exists. If the version matches the remote version, report "Already up to date (v<version>)" and stop.

## Step 4: Download and install

Install directory: `~/.local/bin` (create it if it doesn't exist).

Construct the download URL:
```
https://github.com/elpic/taskflow/releases/download/v<VERSION>/taskflow-mcp_<VERSION>_<OS>_<ARCH>.tar.gz
```

Download to a temp directory, extract `taskflow-mcp`, make it executable, move it to `~/.local/bin/taskflow-mcp`.

## Step 5: Check PATH

Check whether `~/.local/bin` is on the user's `$PATH`:
```bash
echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin"
```

If it is NOT on `$PATH`, print a warning:

```
⚠️  ~/.local/bin is not on your PATH.

Add this to your shell profile (~/.zshrc or ~/.bashrc):

    export PATH="$HOME/.local/bin:$PATH"

Then reload: source ~/.zshrc
```

## Step 6: Report

Print:
- What version was installed (or "already up to date")
- Where the binary is: `~/.local/bin/taskflow-mcp`
- If this was a fresh install: "Restart Claude Code to activate the MCP server."
- If this was an upgrade: "Restart Claude Code (or reload the MCP server) to use the new version."
