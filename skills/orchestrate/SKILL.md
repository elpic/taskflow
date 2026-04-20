---
name: taskflow-orchestrate
description: "Automatically decompose any user request into tracked, verified subtasks with agent delegation and continuous delivery"
---

# Task Orchestration Protocol

For implementation/bugfix/refactor/research requests:

1. Load project profile (.taskflow/project.json) or language standards
2. Recall from mempalace (if available)
3. `task_create` with appropriate `task_type` — agents are auto-assigned per step
4. Create native tasks with `addBlockedBy` chains
5. Use `task_next` to get the next step + agent + context — delegate to assigned agent
6. Verify inline, store learnings in mempalace after completion

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

### Agent Prompts Must Include

1. **Project profile** — from `.taskflow/project.json` (language, tools, conventions)
2. **Prior step context** — from `task_next` response or `task_context`
3. **Task description + verification criteria** — from the task itself
4. **Specific files to read/modify** — don't make agents search blindly
5. **Whether to write code or just research** — agents don't know your intent

### Agent Interaction Patterns

**Architect → Developer**: Architect's output should include: module boundaries, function signatures, key decisions, files to create/modify. Developer should follow the design, not redesign.

**Developer → QA**: Developer's output should include: what was changed, which files, what to test. QA should write tests that cover the acceptance criteria from the architect.

**QA → Reviewer**: QA's output should include: test count, coverage, any issues found. Reviewer evaluates the full chain: does the implementation match the design? Do tests cover the criteria?

**Reviewer → Developer (feedback loop)**: If reviewer finds issues, the loop is:
1. Reviewer outputs specific issues with file paths and line numbers
2. Developer receives reviewer feedback + original architect design
3. Developer fixes, QA re-tests, Reviewer re-reviews
4. Loop until clean (max 3 iterations)

### When to Skip Steps

Not every ticket needs the full pipeline. Use judgment:
- **Size S tasks**: Skip architect, go straight to developer + tests + review
- **Config/docs changes**: Skip QA + containerization
- **Bug fixes**: Use `bugfix` type, not `implement`
- **Already designed**: If you have a clear design, skip architect step

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
