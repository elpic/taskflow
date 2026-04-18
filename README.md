# Taskflow

Hierarchical task orchestration plugin for [Claude Code](https://claude.com/claude-code) with agent delegation, continuous delivery, and verification.

## Installation

Add to your `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "elpic-taskflow": {
      "source": {
        "source": "git",
        "url": "https://github.com/elpic/taskflow.git"
      }
    }
  },
  "enabledPlugins": {
    "taskflow@elpic-taskflow": true
  }
}
```

Then restart Claude Code. Verify with:

```bash
claude plugins list
```

You should see `taskflow@elpic-taskflow` with status `✔ enabled`.

### MCP Server Permissions

To allow the MCP tools to run without prompting, add to your settings:

```json
{
  "permissions": {
    "allow": [
      "mcp__taskflow__*"
    ]
  }
}
```

### Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

## What it does

Taskflow turns Claude Code into a full development team. When you give it a task, it:

1. **Breaks it down** into a structured workflow with specialist agents
2. **Delegates** each step to the right agent (architect, developer, QA, reviewer)
3. **Verifies** each step before moving on
4. **Learns** from past work via MemPalace integration
5. **Ships** via git workflow (branch, PR, CI, squash merge)

## Usage

```
implement a REST API in python          # interactive mode
implement a REST API in python --auto   # fully autonomous
build a todo app --auto                 # product mode — creates backlog, implements all features
discover this project --auto            # detect tools, patterns, CI/CD
```

### Commands

- `--auto` / `/auto` — run fully autonomous, no human in the loop
- `/stop` — stop the continuous delivery loop after current ticket finishes

## Workflow Types

| Type | Description |
|------|-------------|
| `simple` | Plan, execute, verify |
| `implement` | Full pipeline: design, implement, test, docs, containerize, review |
| `bugfix` | Reproduce, root cause, fix, verify, review |
| `refactor` | Analyze, implement, verify behavior unchanged, review |
| `research` | Define question, explore, evaluate, recommend |
| `secure-implement` | Like implement but with security review |
| `product` | Define vision, create backlog, prioritize, execute all features |
| `sprint` | Pick up existing backlog, prioritize, execute, retrospective |
| `discover` | Analyze existing project, detect tools/patterns, improve CI/CD |
| `setup` | Initialize new project with full tooling and CI/CD |

## Agent Pipeline

Each workflow delegates steps to specialist agents:

| Agent | Role |
|-------|------|
| `@tech-architect` | Design, architecture decisions, acceptance criteria |
| `@developer` | Implementation, documentation |
| `@qa-engineer` | Testing, verification |
| `@code-reviewer` | Code quality, correctness, security |
| `@devops-engineer` | CI/CD, containerization |
| `@security-reviewer` | Security audit |
| `@product-manager` | Vision, backlog, prioritization |
| `@architecture-reviewer` | Tech debt review between tickets |
| `@git-workflow` | Branch management, safe git hygiene |
| `@integration-verifier` | CI monitoring, failure reporting |

## Autonomous Mode

With `--auto`, taskflow runs end-to-end without stopping:

- Skips clarifying questions
- Accepts all agent recommendations
- Auto-fixes issues found in review (loops until passing)
- Runs full git workflow per ticket (branch, PR, CI, squash merge)
- Reviews for tech debt between tickets
- Creates backlog items for issues found
- Continues until backlog is empty or `/stop`

## Continuous Delivery Loop

For `product` and `sprint` with `--auto`:

```
Pick ticket → Branch → Implement → Commit → PR → CI → Squash Merge → Tech Debt Review → Next
```

## Project Discovery

Run `discover` on an existing project to generate `.taskflow/project.json`:

```json
{
  "name": "my-api",
  "languages": { "primary": "python", "versions": { "python": ">=3.12" } },
  "package_manager": { "tool": "uv", "add_command": "uv add" },
  "linter": { "tool": "ruff", "command": "uv run ruff check ." },
  "test_runner": { "tool": "pytest", "command": "uv run pytest" },
  "architecture": { "style": "hexagonal", "patterns": ["repository"] }
}
```

All agents read this profile before working, ensuring they use the project's actual tools.

## Language Standards

Built-in standards for Python, TypeScript, Rust, and Go. Used as fallback when no project profile exists.

| Language | Package Manager | Linter | Type Checker | Test Runner |
|----------|----------------|--------|-------------|-------------|
| Python | uv | ruff | ty | pytest |
| TypeScript | pnpm | biome | tsc | vitest |
| Rust | cargo | clippy | rustc | cargo test |
| Go | go mod | golangci-lint | go vet | go test |

## MCP Server

SQLite-backed task persistence with tools:

- `task_create` — create tasks with optional workflow type
- `task_start` — start a task
- `task_complete` — complete with auto-verification
- `task_fail` — mark failed
- `task_types` — list available workflow types

## License

MIT
