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

## Continuous Delivery Loop (product/sprint)

The CD loop is the core automation pattern. Follow this EXACTLY — do not skip steps.

```
# Phase 1: Create ticket-level tasks (see Claude UI Phase 1)
for each ticket in backlog:
    TaskCreate(subject="Ticket N: <name>") with addBlockedBy chains

# Phase 2: Process each ticket
while tickets_remaining:
    # 2a. Pick next ticket
    result = task_next(root_id=sprint_id)  # returns next ready ticket
    ticket_id = result.step_id

    # 2b. Drill down (see Claude UI Phase 2)
    #     Delete current ticket's native task
    #     Create step-level native tasks for each workflow step
    #     Chain with addBlockedBy

    # 2c. Execute ALL steps (branch, design, implement, test, review, PR)
    #     task_next returns steps in order — including git steps
    while step = task_next(root_id=ticket_id):
        # Update Claude UI
        TaskUpdate(taskId=step_native, status="in_progress",
                   activeForm=step.step_name)

        # Delegate to the assigned agent with full context
        # step.context contains prior step outputs from task_next
        Agent(subagent_type=step.agent,
              prompt=step.context + project_profile + step.description)

        # Store output for downstream agents and mark done
        task_complete(step_id=step.id, output=agent_result)
        TaskUpdate(taskId=step_native, status="completed")

    # 2d. Merge PR (last step created the PR)
    Agent(subagent_type="git-workflow",
          prompt="Squash merge PR #N, pull main, delete branch")

    # 2e. Wait for release + merge version-sync PR (if exists)
    #     Check: gh pr list --state open | grep "sync version"
    #     If found: gh pr merge <N> --squash --delete-branch

    # 2f. Drill back up (see Claude UI Phase 4)
    #     Delete step tasks, recreate ticket task as completed

    # 2g. Complete the ticket in taskflow
    task_complete(step_id=ticket_id)
```

**Key rules:**
- NEVER skip the drill-down (2b) or drill-back-up (2h) — the user must see progress
- ALWAYS wait for merge + release before starting the next ticket
- ALWAYS pass context from prior steps to each agent (`task_next` provides this)

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

## Claude UI Visibility (MANDATORY — DO NOT SKIP)

The user MUST see progress in the Claude UI task list at all times. Without this, they see a wall of tool calls. This is the #1 user complaint.

### Phase 1: Ticket-Level Tasks (Sprint/Product)

Before entering the continuous delivery loop, create one native task per ticket:

```
# For each ticket in the sprint backlog:
TaskCreate(subject="Ticket 1: <name>", description="...")  → id=T1
TaskCreate(subject="Ticket 2: <name>", description="...")  → id=T2
TaskCreate(subject="Ticket 3: <name>", description="...")  → id=T3
TaskUpdate(taskId=T2, addBlockedBy=[T1])
TaskUpdate(taskId=T3, addBlockedBy=[T2])
```

### Phase 2: Drill Into a Ticket (REQUIRED for every ticket)

When starting work on a ticket, DELETE the ticket-level tasks and CREATE step-level tasks:

```
# 1. Delete ONLY the current ticket's task (keep others for overview)
TaskUpdate(taskId=T2, status="deleted")  # drilling into Ticket 2

# 2. Create step-level tasks for the current ticket's workflow
TaskCreate(subject="Create branch", ...)        → id=S1
TaskCreate(subject="Design solution", ...)      → id=S2
TaskCreate(subject="Implement", ...)            → id=S3
TaskCreate(subject="Create tests", ...)         → id=S4
TaskCreate(subject="Code review", ...)          → id=S5
TaskCreate(subject="Commit and create PR", ...) → id=S6

# 3. Chain them
TaskUpdate(taskId=S2, addBlockedBy=[S1])
TaskUpdate(taskId=S3, addBlockedBy=[S2])
TaskUpdate(taskId=S4, addBlockedBy=[S3])
TaskUpdate(taskId=S5, addBlockedBy=[S4])
TaskUpdate(taskId=S6, addBlockedBy=[S5])
```

### Phase 3: Work Through Steps

For EACH step, update its status before and after:

```
# Starting a step:
TaskUpdate(taskId=S3, status="in_progress", activeForm="Implementing feature X")

# ... delegate to agent ...

# After step completes:
TaskUpdate(taskId=S3, status="completed")
```

### Phase 4: Drill Back Up to Ticket Level

After the ticket is merged, DELETE step tasks and RECREATE ticket tasks with updated statuses:

```
# 1. Delete step-level tasks
TaskUpdate(taskId=S1, status="deleted")
TaskUpdate(taskId=S2, status="deleted")
# ... delete all step tasks ...

# 2. Recreate the completed ticket's task as done
TaskCreate(subject="Ticket 2: <name>", ...)  → id=T2_new
TaskUpdate(taskId=T2_new, status="completed")
# T1 was already completed, T3 is still pending — both untouched
```

### Checklist (verify before EACH agent delegation)

- [ ] Native tasks exist for the current workflow steps
- [ ] The current step is marked `in_progress` with `activeForm`
- [ ] The previous step is marked `completed`
- [ ] Agent prompt includes prior step outputs (`task_context`)

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

Sprint tracking follows the 4 phases above:
1. **Phase 1** at sprint start — create ticket-level tasks
2. **Phase 2** when entering each ticket — drill down to step tasks
3. **Phase 3** during each step — update in_progress/completed
4. **Phase 4** after each ticket merges — drill back up

**NEVER run a sprint without visible progress.** If you find yourself delegating to an agent without native tasks visible in the Claude UI, STOP and create them first.
