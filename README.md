# Taskflow

Hierarchical task orchestration plugin for [Claude Code](https://claude.com/claude-code) with agent delegation, continuous delivery, and verification.

## What it does

Taskflow turns Claude Code into a full development team. When you give it a task, it:

1. **Breaks it down** into a structured workflow with specialist agents
2. **Delegates** each step to the right agent (architect, developer, QA, reviewer)
3. **Verifies** each step before moving on
4. **Learns** from past work via MemPalace integration
5. **Ships** via git workflow (branch, PR, CI, squash merge)

## Workflow Types

| Type | Description |
|------|-------------|
| `simple` | Plan, execute, verify |
| `implement` | Full implementation pipeline with docs and containerization |
| `bugfix` | Reproduce, root cause, fix, verify, review |
| `refactor` | Analyze, implement, verify behavior unchanged, review |
| `research` | Define question, explore, evaluate, recommend |
| `secure-implement` | Like implement but with security review |
| `product` | Define vision, create backlog, prioritize, execute all features |
| `sprint` | Pick up existing backlog, prioritize, execute, retrospective |
| `discover` | Analyze existing project, detect tools/patterns, generate profile |
| `setup` | Initialize new project with full tooling and CI/CD |

## Agent Pipeline

Each workflow delegates steps to specialist agents:

- **@tech-architect** - Design, architecture decisions, acceptance criteria
- **@developer** - Implementation, documentation
- **@qa-engineer** - Testing, verification
- **@code-reviewer** - Code quality, correctness, security
- **@devops-engineer** - CI/CD, containerization
- **@security-reviewer** - Security audit
- **@product-manager** - Vision, backlog, prioritization
- **@architecture-reviewer** - Tech debt review between tickets

## Autonomous Mode

Add `--auto` to any request for fully autonomous execution:

```
implement a REST API in python --auto
```

In auto mode, taskflow:
- Skips clarifying questions
- Accepts all agent recommendations
- Auto-fixes issues found in review
- Runs the full git workflow (branch, PR, CI, squash merge)
- Reviews for tech debt between tickets
- Continues until the backlog is empty or you type `/stop`

## Continuous Delivery Loop

For `product` and `sprint` with `--auto`, taskflow enters a loop:

```
Pick ticket → Branch → Implement → Commit → PR → CI → Squash Merge → Tech Debt Review → Next
```

Each ticket gets a descriptive commit message and PR explaining what was built and why.

## Project Discovery

Run `discover` on an existing project to detect its tools and patterns:

```
discover this project --auto
```

Generates `.taskflow/project.json` which all agents read before working, ensuring they use the project's actual tools instead of defaults.

## Language Standards

Built-in standards for Python, TypeScript, Rust, and Go. For Python:
- `uv` (not pip), `ruff` (not flake8), `ty` (not mypy), `pytest`

## Installation

Add to your Claude Code settings:

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

## MCP Server

The plugin includes an MCP server (Python/FastMCP) for task persistence in SQLite:

- `task_create` - Create tasks with optional workflow type
- `task_start` - Start a task
- `task_complete` - Complete with auto-verification
- `task_fail` - Mark failed
- `task_types` - List available workflow types

## License

MIT
