---
name: taskflow-update
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
curl -sI "https://github.com/elpic/taskflow/releases/latest/download/taskflow-mcp_latest_Darwin_arm64.tar.gz" 2>/dev/null | grep -i '^location:' | tr -d '\r' | awk '{print $2}'
```
(substitute the actual OS/arch detected above)

Extract the version from the `Location` URL: the segment after `/download/v` and before the next `/`.

## Step 3: Check current version

Read the file `.taskflow/version` in the taskflow project directory (same directory as `mcp.sh`). If it exists and matches the remote version, report "Already up to date (v<version>)" and stop.

## Step 4: Download and install

Construct the download URL:
```
https://github.com/elpic/taskflow/releases/download/v<VERSION>/taskflow-mcp_<VERSION>_<OS>_<ARCH>.tar.gz
```

Download to a temp directory, extract `taskflow-mcp`, make it executable, move it to the taskflow project directory (replacing any existing binary).

Write the new version string to `.taskflow/version`.

## Step 5: Report

Print:
- What version was installed
- Where the binary lives
- "Restart Claude Code (or reload the MCP server) to use the new version."

## Project directory

The taskflow project directory is: `/Users/elpic/development/workspace/personal/taskflow`
