# Taskflow — Task Orchestration

Taskflow (MCP) is the persistence layer. Native TaskCreate/TaskUpdate are the UI layer.

## Autonomous Mode (DEFAULT)

Taskflow runs in **fully autonomous mode by default**:

1. **Skip clarifying questions** — make reasonable assumptions based on context and mempalace knowledge
2. **Accept all agent recommendations** — do not pause for user confirmation at any step
3. **Run end-to-end without stopping** — design → implement → test → review, no human in the loop
4. **Handle review feedback automatically** — if review/QA finds issues, loop back to fix, re-test, re-review until it passes
5. **Only stop for the user if**:
   - A task fails after 3 retry attempts
   - The request is fundamentally ambiguous (e.g., "build something cool" with no context)
6. **Report at the end** — brief summary of what was built, decisions made, and issues encountered

### Interactive mode (`--interactive` or `/interactive`):
Use only when the user explicitly requests it:
- Ask clarifying questions when requirements are ambiguous
- Pause after architect designs to confirm direction
- Accept agent recommendations by default but inform the user of key decisions

## When to Use Taskflow

**USE taskflow** for work that requires planning, implementation, or multi-step execution:
- Implementing features or writing code
- Bug fixes, refactoring, research with deliverables
- Any task with 2+ distinct steps

**DO NOT use taskflow** — just respond directly:
- Questions, explanations, simple one-shot edits, conversations

## Latest Docs (BEFORE implementing)

Before writing code that uses any library, framework, or external tool, look up the latest documentation via `context7` (resolve-library-id → query-docs). Training data may be outdated. This applies to ALL agents — architect, developer, QA, devops.

## Task Types & Agent Delegation

When creating a task with `task_type`, the server auto-generates workflow subtasks with **specialist agent assignments**.

| Type | Workflow (agent) |
|------|-----------------|
| **simple** | Plan → Execute (@developer) → Verify (@qa-engineer) |
| **implement** | Design (@tech-architect) → Clarify → Acceptance criteria (@tech-architect) → Implement (@developer) → Tests (@qa-engineer) → Docs (@developer) → Containerize (@devops-engineer) → Review (@code-reviewer) |
| **bugfix** | Reproduce (@qa-engineer) → Root cause (@developer) → Fix (@developer) → Verify fix (@qa-engineer) → Review (@code-reviewer) |
| **refactor** | Plan (@tech-architect) → Implement (@developer) → Verify unchanged (@qa-engineer) → Review (@code-reviewer) |
| **research** | Define question → Explore (@tech-architect) → Evaluate (@tech-architect) → Document recommendation |
| **secure-implement** | Design (@tech-architect) → Clarify → Criteria (@tech-architect) → Implement (@developer) → Tests (@qa-engineer) → Security (@security-reviewer) → Review (@code-reviewer) |
| **product** | Vision (@product-manager) → Features (@product-manager) → Prioritize (@product-manager) → Execute backlog (continuous delivery loop) |
| **discover** | Scan (@Explore) → Languages (@Explore) → Packages (@Explore) → Quality tools (@Explore) → Tests (@Explore) → Architecture (@tech-architect) → Conventions (@code-reviewer) → CI/CD (@devops-engineer) → APIs (@tech-architect) → Review CI/CD (@devops-reviewer) → Improve CI/CD (@devops-engineer) → Generate profile (@developer) → Review (@code-reviewer) |
| **setup** | Define scope (@tech-architect) → Init project (@developer) → Code quality (@developer) → Testing (@qa-engineer) → CI/CD pipeline (@devops-engineer) → Containerize (@devops-engineer) → Docs (@developer) → Generate profile (@developer) → Review setup (@devops-reviewer) |
| **sprint** | Review backlog (@product-manager) → Prioritize & select (@product-manager) → Execute sprint (continuous delivery loop) → Retrospective (@product-manager) |

### Response format for typed tasks:
`<root_id>|<type>|<step1_id>:@<agent>,<step2_id>:@<agent>,...`

## Memory Integration (MemPalace)

If mempalace MCP is available, taskflow integrates with it for cross-session learning.

### Before starting work (Recall):
1. `mempalace_search(query="<topic>")` — find past learnings
2. `mempalace_kg_query(entity="<project>")` — get known relationships

### After completing work (Store):
1. `mempalace_kg_add` — store facts about what was built
2. `mempalace_add_drawer(wing="taskflow", room="learnings")` — store non-obvious learnings
3. `mempalace_diary_write(agent_name="taskflow")` — log session summary

## MCP Responses
- `<id>` — task created (no type)
- `<id>|<type>|<id1>:@agent1,<id2>:@agent2,...` — typed task with agent assignments
- `ok` — action succeeded
- `ok|unblocked:<id1>,<id2>` — completed, dependents now ready
- `verify:<id>` — verify inline
- `error:<reason>` — something failed
