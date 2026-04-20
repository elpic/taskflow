---
name: taskflow-orchestrate
description: "Automatically decompose any user request into tracked, verified subtasks with agent delegation and continuous delivery"
---

# Task Orchestration Protocol

**CRITICAL RULE: You are the ORCHESTRATOR, not the implementor.** Your job is to coordinate agents. NEVER write code directly — always delegate to the appropriate agent via `Agent(subagent_type=...)`. Every feature, bugfix, and refactor MUST go through a workflow pipeline with agent delegation.

For implementation/bugfix/refactor/research requests:

1. Load project profile (.taskflow/project.json) or language standards
2. Recall from mempalace (if available)
3. `task_create` with appropriate `task_type` — agents are auto-assigned per step
4. Create native tasks with `addBlockedBy` chains
5. Use `task_next` to get the next step + agent + context — **delegate to that agent**
6. Verify inline, store learnings in mempalace after completion

**The workflow per ticket:**
```
task_create(task_type="implement") → generates steps with agents
    ↓
task_next(root_id) → returns {step, agent, context}
    ↓
Agent(subagent_type=agent, prompt=context+task) → agent does the work
    ↓
task_complete(step_id, output=result) → stores output for next agent
    ↓
task_next(root_id) → next step... repeat until all_done
```

Do NOT shortcut this. Do NOT write code yourself. Delegate.

## Mode

Taskflow runs autonomously by default. No `--auto` flag needed. Skip clarifying questions, accept agent recommendations, run end-to-end.

Use `--interactive` only when user explicitly requests it.

## Continuous Delivery (product/sprint)

Enters a loop: pick ticket → branch → implement → commit → PR → CI → squash merge → next ticket.

## Skip taskflow for simple questions, explanations, or one-shot edits.

---

## Agent Pipeline Best Practices

### Context Chain (CRITICAL)

Every agent MUST receive context from the previous agent's output. Use `task_next` which provides this automatically, or `task_context` to fetch prior step outputs.

```
@tech-architect produces design
    ↓ (output stored via task_complete(output=...))
@developer receives: architect's design + project profile
    ↓ (output stored)
@qa-engineer receives: developer's implementation summary + architect's criteria
    ↓ (output stored)
@code-reviewer receives: ALL prior outputs (design + implementation + test results)
```

**Never delegate to an agent without context from prior steps.** The agent has no memory of what happened before — you MUST pass it.

### Latest Docs Lookup (BEFORE implementing)

Before any agent writes code, check for the latest documentation:

1. **Use `context7`** (resolve-library-id → query-docs) for any library, framework, or tool being used
2. **Even for well-known libraries** — APIs change. Don't rely on training data.
3. **When to look up**: installing packages, calling APIs, configuring tools, writing framework-specific code
4. **When NOT to look up**: pure business logic, internal code, project-specific patterns

This prevents outdated API calls, deprecated patterns, and wrong method signatures.

### Agent Prompts Must Include

1. **Project profile** — from `.taskflow/project.json` (language, tools, conventions)
2. **Prior step context** — from `task_next` response or `task_context`
3. **Task description + verification criteria** — from the task itself
4. **Specific files to read/modify** — don't make agents search blindly
5. **Whether to write code or just research** — agents don't know your intent
6. **Latest docs** — if using a library/framework, include relevant docs from context7

### Architecture Preference

When designing new features or refactoring, prefer **hexagonal architecture** (ports & adapters):
- Define ports (interfaces/protocols) at domain boundaries
- Implement adapters for external integrations (DB, APIs, CLI)
- Keep domain logic pure — no infrastructure imports in domain code
- Separate inbound adapters (API handlers, CLI) from outbound adapters (repositories, clients)

This applies to @tech-architect designs and @code-reviewer feedback.

### Agent Interaction Patterns

**Architect → Developer**: Architect's output should include: module boundaries, function signatures, key decisions, files to create/modify. Developer should follow the design, not redesign.

**Developer → QA**: Developer's output should include: what was changed, which files, what to test. QA should write tests that cover the acceptance criteria from the architect.

**QA → Reviewer**: QA's output should include: test count, coverage, any issues found. Reviewer evaluates the full chain: does the implementation match the design? Do tests cover the criteria?

**Reviewer → Developer (feedback loop)**: If reviewer finds issues, the loop is:
1. Reviewer outputs specific issues with file paths and line numbers
2. Developer receives reviewer feedback + original architect design
3. Developer fixes, QA re-tests, Reviewer re-reviews
4. Loop until clean (max 3 iterations)

### When to Skip Steps (ONLY these cases)

You may simplify the pipeline ONLY for:
- **Size S tasks**: Skip architect, but still delegate to @developer + @qa-engineer + @code-reviewer
- **Config/docs-only changes**: Skip QA, but still delegate to @developer + @code-reviewer
- **Bug fixes**: Use `task_type="bugfix"` which has its own pipeline

You may NEVER skip:
- **@developer delegation** — you must NOT write code yourself
- **@qa-engineer or @code-reviewer** — quality gates are not optional
- **task_create with task_type** — the workflow must be created in taskflow

---

## Claude UI Visibility (REQUIRED)

### Native Task Progress

The user MUST always see progress in the Claude UI task list. Without this, they see a wall of tool calls.

**Before starting any workflow:**
- Create native tasks (TaskCreate) for each step
- Chain with `addBlockedBy` to show the workflow order

**During each step:**
- `TaskUpdate(status=in_progress)` with `activeForm` showing what's happening
- Example: `activeForm: "Implementing authentication module"`

**After each step:**
- `TaskUpdate(status=completed)` immediately when done

### Drill-Down Navigation

When entering a sub-workflow (e.g., implement pipeline under a sprint ticket):
1. Delete ticket-level native tasks
2. Create step-level native tasks (Design → Implement → Tests → Review)
3. Work through them with visible progress
4. When done: delete step tasks, recreate ticket tasks with updated statuses

```
TICKET LEVEL:                    DRILL INTO TICKET 2:              BACK TO TICKET LEVEL:
✓ Ticket 1: task_list            ○ Design solution                 ✓ Ticket 1: task_list
◈ Ticket 2: task_get     →      ◈ Implement                  →    ✓ Ticket 2: task_get
○ Ticket 3: task_current         ○ Create tests                    ◈ Ticket 3: task_current
○ Ticket 4: task_update          ○ Code review                     ○ Ticket 4: task_update
```

---

## Git Workflow (Delegated to @git-workflow)

Git operations in the continuous delivery loop MUST be delegated to the `@git-workflow` agent — do NOT run git commands directly.

### Per-Ticket Git Flow

**Before implementing:**
```
Agent(subagent_type="git-workflow", prompt="Create a feature branch from main for: <ticket name>. 
Ensure main is up to date. Branch naming: feat/<ticket-slug> or fix/<ticket-slug>.")
```

**After all implement steps complete:**
```
Agent(subagent_type="git-workflow", prompt="Stage all changes, commit with this message: <message>.
Push the branch and create a PR with this description: <PR body>.
Wait for CI checks to pass. If CI fails, report the failure logs.")
```

**After PR is approved/CI passes:**
```
Agent(subagent_type="git-workflow", prompt="Squash merge PR #<number>. 
Pull main, delete the feature branch, verify clean state.")
```

### Why Delegate Git?
- The orchestrator can make mistakes with git (wrong branch, missing files, force pushes)
- `@git-workflow` is a specialist that follows safe git hygiene
- It reads the project's git configuration and respects branch protection
- It handles edge cases (conflicts, stale branches, hook failures)

---

### Sprint Progress Tracking

**Before the loop starts:**
- Create one native task per backlog ticket
- Chain them with `addBlockedBy`

**During each ticket:**
- Set `in_progress` when starting
- Drill down into implement steps
- Drill back up when done

**After each ticket merges:**
- Set `completed` — cumulative progress visible

**NEVER run a sprint without visible progress.** This is the #1 user complaint.
