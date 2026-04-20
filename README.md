# Taskflow

Task orchestration plugin for [Claude Code](https://claude.com/claude-code). Turns Claude into a full development team with specialist agents, structured workflows, and continuous delivery.

## Quick Start

```bash
# Install the plugin
/plugin marketplace add elpic/taskflow
/plugin install taskflow@elpic-taskflow
```

Then just tell Claude what to build:

```
implement a REST API for user management
build a todo app with authentication
fix the login bug in auth.py
refactor the database layer
```

Taskflow runs **autonomously by default** — no flags needed. It breaks down your request, delegates to specialist agents, writes tests, reviews code, and ships via PR.

## How It Works

```
You: "implement a REST API"
                ↓
    Taskflow creates workflow steps
                ↓
    @tech-architect designs the solution
                ↓
    @developer implements following the design
                ↓
    @qa-engineer writes tests
                ↓
    @code-reviewer reviews everything
                ↓
    Branch → Commit → PR → CI → Merge
```

Each agent receives context from the previous step. The reviewer can loop back to the developer if issues are found (max 3 iterations).

## Workflow Types

| Command | What happens |
|---------|-------------|
| `implement X` | Design → Implement → Test → Review |
| `fix the bug in X` | Reproduce → Root cause → Fix → Verify → Review |
| `refactor X` | Plan → Implement → Verify unchanged → Review |
| `research X` | Define question → Explore → Evaluate → Recommend |
| `build a product` | Vision → Features → Prioritize → Ship all features |
| `sprint` | Pick up backlog → Prioritize → Ship → Retrospective |
| `discover this project` | Scan everything → Generate project profile |
| `setup a new project` | Init → Code quality → Tests → CI/CD → Docker |

## MCP Tools (21)

| Category | Tools |
|----------|-------|
| **CRUD** | `task_create`, `task_get`, `task_update`, `task_delete`, `task_reset` |
| **Lifecycle** | `task_start`, `task_complete`, `task_fail` |
| **Query** | `task_list`, `task_search`, `task_current` |
| **Organization** | `task_move`, `task_reorder` |
| **Session** | `task_resume`, `task_context`, `task_history` |
| **Orchestration** | `task_next` (server-side step enforcement) |
| **Analytics** | `task_stats` |
| **Meta** | `task_types` |

Key features: idempotent creation, blocked_by dependencies with cycle detection, agent output storage, audit trail, session recovery, position-based ordering.

## Permissions

Add to your project's `.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(*)",
      "Read(*)",
      "Write(*)",
      "Edit(*)",
      "mcp__taskflow__*",
      "mcp__mempalace__*"
    ]
  },
  "enableAllProjectMcpServers": true
}
```

## Project Discovery

Run `discover this project` to generate `.taskflow/project.json` — a profile of your project's tools, architecture, and conventions. All agents read this before working.

```json
{
  "languages": { "primary": "python", "versions": { "python": ">=3.12" } },
  "package_manager": { "tool": "uv" },
  "linter": { "tool": "ruff", "command": "uv run ruff check ." },
  "architecture": { "style": "hexagonal", "patterns": ["repository", "ports-adapters"] }
}
```

## Development

```bash
uv sync                          # Install dependencies
uv run ruff check .              # Lint
uv run ruff format .             # Format
uv run ty check                  # Type check
uv run pytest                    # Run 216 tests
uv run pytest --cov=src          # Coverage
uv build                         # Build wheel
```

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## License

MIT
