# Taskflow — Task Orchestration

Taskflow (MCP) is the persistence layer. Native TaskCreate/TaskUpdate are the UI layer.

## Autonomous Mode

When the user's prompt contains `--auto` or `/auto`, run in **fully autonomous mode**:

1. **Skip clarifying questions entirely** — make reasonable assumptions based on context and mempalace knowledge
2. **Accept all agent recommendations** — do not pause for user confirmation at any step
3. **Run end-to-end without stopping** — design → implement → test → review, no human in the loop
4. **Handle review feedback automatically** — if the code reviewer or QA finds issues, loop back to the developer agent to fix them, then re-test and re-review. Keep looping until it passes
5. **Only stop for the user if**:
   - A task fails after 3 retry attempts
   - The request is fundamentally ambiguous (e.g., "build something cool" with no context)
6. **Report at the end** — when all tasks complete, give a brief summary of what was built, decisions made, and any issues encountered

### Without `--auto`:
- Ask clarifying questions when requirements are ambiguous
- Pause after architect designs to confirm direction
- Accept agent recommendations by default but inform the user of key decisions

## Continuous Delivery Loop (product/sprint with --auto)

When running `product` or `sprint` with `--auto`, taskflow enters a **continuous delivery loop** that picks up tickets one by one, implements them end-to-end including git workflow, and keeps going until the backlog is empty or the user stops it.

### The Loop

```
┌─────────────────────────────────────────────────────────────┐
│  1. Pick highest priority pending ticket from backlog       │
│  2. Create feature branch from main                        │
│  3. Run implement pipeline (architect → dev → QA → review) │
│  4. Commit with descriptive message                        │
│  5. Push branch + Create PR with full description          │
│  6. Wait for CI checks to pass                             │
│  7. Squash and merge to main                               │
│  8. Tech debt review — scan for issues introduced          │
│  9. Create backlog items for any tech debt found            │
│  10. Loop back to 1                                        │
│                                                            │
│  EXIT CONDITIONS:                                          │
│  - Backlog is empty (all items done) → report summary      │
│  - User invokes /stop → finish current ticket, then stop   │
│  - Task fails 3 times → stop and report                    │
└─────────────────────────────────────────────────────────────┘
```

### Progress Tracking (REQUIRED)

The sprint loop MUST show visible progress using native tasks (TaskCreate/TaskUpdate). Without this, the user sees a wall of tool calls with no indication of what's happening.

**Before the loop starts:**
- Create one native task per backlog ticket (e.g., "Ticket 1: Add task_list MCP tool")
- Chain them with `addBlockedBy` so they appear in priority order

**During each ticket:**
- `TaskUpdate(status=in_progress)` when starting the ticket
- The native task list shows the user: which tickets are done, which is active, which are pending

**After each ticket merges:**
- `TaskUpdate(status=completed)` on the finished ticket
- Previous tickets remain visible as completed — cumulative progress

This is NOT optional. The native task list IS the progress indicator for the user.

### Step Details

#### 1. Pick ticket
- Query taskflow for pending tasks under the root
- Select the first one (they're ordered by priority via addBlockedBy)

#### 2. Create feature branch
- Use `@git-workflow` agent to create a branch
- Branch naming: `feat/<ticket-name-slugified>` (e.g., `feat/add-task-filtering`)
- Ensure main is up to date first: `git pull origin main`

#### 3. Implement
- Run the full `implement` pipeline as child tasks under the ticket
- architect → developer → QA → docs → containerize → reviewer
- All the usual fix loops if review/QA finds issues

#### 4. Commit
- Stage all changed files
- Commit message format:
  ```
  feat: <short description of what was built>

  <ticket name>

  - <bullet point of key change 1>
  - <bullet point of key change 2>
  - <what problem this solves>

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
  ```
- The message must explain WHAT was done and WHY, not just "implement feature"

#### 5. Create PR
- Push branch with `git push -u origin <branch>`
- Create PR using `gh pr create`
- PR title: short, descriptive (under 70 chars)
- PR body format:
  ```markdown
  ## Summary
  <1-3 sentences explaining what this PR does and why>

  ## Changes
  - <bullet list of key changes>

  ## Acceptance Criteria
  - [x] <criteria from the ticket, checked off>

  ## Test Results
  - <summary of QA test results>

  ## Architecture Decisions
  - <any notable decisions made by the architect>

  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  ```

#### 6. Wait for CI
- Use `@integration-verifier` agent to monitor the CI run
- Wait for all checks to pass
- If CI fails: read the logs, fix the issue, push again, wait again
- Max 3 CI fix attempts before stopping

#### 7. Squash and merge
- Use `gh pr merge --squash --auto` to squash merge
- The squash commit message should be the PR title + body
- After merge: `git checkout main && git pull origin main`
- Clean up: `git branch -d <branch>`

#### 8. Tech debt review
- Use `@architecture-reviewer` agent to scan the codebase after the merge
- Look for:
  - Code duplication introduced
  - Missing test coverage for edge cases
  - Inconsistent patterns (new code doesn't match existing conventions)
  - Performance concerns
  - Missing error handling
  - Documentation gaps
  - Dead code or unused imports
- Also check: did we break the project profile? Do conventions still match `.taskflow/project.json`?

#### 9. Create tech debt backlog items
- For each issue found, `task_create` a new task under the root with lower priority
- Use appropriate task_type: `bugfix` for bugs, `refactor` for cleanup, `implement` for missing features
- These get added to the end of the backlog queue
- The product manager can reprioritize them in the next sprint

#### 10. Continue or stop
- Check if the user invoked `/stop`
- Check if there are pending tickets remaining
- If both clear: loop back to step 1 with the next ticket

### Stopping the Loop

The user can stop the continuous delivery loop by:
- Typing `/stop` — finishes the current ticket (through merge), then stops
- Saying "stop for now" or "pause" — same behavior
- The loop also stops naturally when the backlog is empty

After stopping, report:
- How many tickets were completed
- How many remain in the backlog
- Any tech debt items created
- Learnings stored in mempalace

## When to Use Taskflow

**USE taskflow** for work that requires planning, implementation, or multi-step execution:
- Implementing features or writing code
- Bug fixes
- Refactoring
- Research that involves exploration and a deliverable
- Any task with 2+ distinct steps

**DO NOT use taskflow** — just respond directly:
- Questions ("what does X do?", "how does Y work?", "explain Z")
- Simple one-shot actions ("rename this variable", "fix this typo")
- Conversations, opinions, advice
- Reading/explaining code
- Anything that doesn't require a plan

## Memory Integration (MemPalace)

If mempalace MCP is available, taskflow integrates with it for cross-session learning.

### Before starting work (Recall):
Before creating tasks, search mempalace for relevant knowledge:
1. `mempalace_search(query="<topic of the task>")` — find past learnings
2. `mempalace_kg_query(entity="<project or tool>")` — get known relationships
3. Use this context to inform your task plan — avoid repeating past mistakes, reuse known patterns

### After completing work (Store):
After the root task completes:
1. `mempalace_kg_add` — store facts about what was built
2. `mempalace_add_drawer(wing="taskflow", room="learnings")` — store non-obvious learnings
3. `mempalace_diary_write(agent_name="taskflow")` — log session summary

### What to store:
- Decisions and WHY they were made
- Gotchas or bugs encountered and how they were fixed
- Patterns that worked well
- User preferences discovered during the task
- DO NOT store obvious things (file paths, git history, code that's readable)

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
| **sprint** | Review backlog (@product-manager) → Prioritize & select (@product-manager) → Execute sprint (continuous delivery loop) → Retrospective (@product-manager) |
| **discover** | Scan (@Explore) → Languages (@Explore) → Packages (@Explore) → Quality tools (@Explore) → Tests (@Explore) → Architecture (@tech-architect) → Conventions (@code-reviewer) → CI/CD (@devops-engineer) → APIs (@tech-architect) → Review CI/CD (@devops-reviewer) → Improve CI/CD (@devops-engineer) → Generate profile (@developer) → Review (@code-reviewer) |
| **setup** | Define scope (@tech-architect) → Init project (@developer) → Code quality (@developer) → Testing (@qa-engineer) → CI/CD pipeline (@devops-engineer) → Containerize (@devops-engineer) → Docs (@developer) → Generate profile (@developer) → Review setup (@devops-reviewer) |

### Response format for typed tasks:
`<root_id>|<type>|<step1_id>:@<agent>,<step2_id>:@<agent>,...`

### Agent Delegation Protocol:

When a step has an agent assignment (`@tech-architect`, `@developer`, etc.):
1. Use the `Agent` tool with `subagent_type` matching the agent name
2. Give the agent a clear prompt with:
   - **Language standards** (loaded in step 0 — ALWAYS include these)
   - The task name and description
   - Context from previous steps (e.g., architect's design for the developer)
   - The verification criteria if any
   - The project path and relevant files
3. The agent works autonomously and returns its result
4. You process the result and complete the step

When a step has `@self`:
- You handle it directly (e.g., asking the user clarifying questions)

### Agent Context Chain:

Each agent builds on the previous agent's output:
- **@tech-architect** → produces a design/plan → passed as context to **@developer**
- **@developer** → produces code → passed as context to **@qa-engineer**
- **@qa-engineer** → produces test results → passed as context to **@code-reviewer**
- **@code-reviewer** → produces review feedback → if issues found, loop back to **@developer**

Store each agent's output so the next agent has full context.

### Git Workflow Agents:

These agents handle the git/GitHub operations in the continuous delivery loop:
- **@git-workflow** — creates branches, ensures main is up to date, manages safe git hygiene
- **@integration-verifier** — monitors CI runs, reports failures, reads logs
- **@architecture-reviewer** — reviews codebase for tech debt after each merge

### Product Workflow — Backlog as Tasks

The `product` type is a **meta-workflow**. The backlog IS the task tree — every feature is a persisted taskflow task.

**Step 1-2: Product-manager defines vision + features**

The @product-manager outputs a structured list of features. **Immediately** after receiving the list, create a taskflow task for EACH feature:

```
task_create(name="Feature: <name>", description="<description>", parent_id=<root_id>)
```

These are the backlog items. They persist in SQLite — if the session ends, the backlog survives.

**Step 3: Product-manager prioritizes**

The @product-manager orders the features by impact/effort. You then reorder the native tasks to match the priority using `addBlockedBy` chains. The priority order IS the execution order.

**Step 4: Execute backlog (Continuous Delivery Loop)**

In `--auto` mode, this enters the continuous delivery loop described above. Each ticket goes through:
branch → implement → commit → PR → CI → squash merge → tech debt review → next ticket

**Without --auto**: after prioritization, show the backlog and ask which features to implement. Still does the git workflow per feature, but pauses between tickets for user input.

**What gets persisted in taskflow:**
```
Root: "Build todo app" (product)
├── "Define product vision" (done)
├── "Break into features" (done)
├── "Prioritize backlog" (done)
├── "Feature: Add tasks" (done, merged via PR #1)
│   ├── Design solution (@tech-architect)
│   ├── Implement (@developer)
│   ├── Create tests (@qa-engineer)
│   ├── Documentation (@developer)
│   ├── Containerization (@devops-engineer)
│   └── Code review (@code-reviewer)
├── "Feature: Mark complete" (in_progress, PR #2 open)
├── "Feature: Delete tasks" (pending)
├── "Feature: Filter by status" (pending)
└── "Tech debt: Extract shared validation logic" (pending, added during tech debt review)
```

### Sprint Workflow — Working from an Existing Backlog

Use `task_type="sprint"` when a backlog already exists and you want to pick up items and execute them.

**Flow:**
1. **Review backlog** (@product-manager) — queries taskflow for pending tasks, presents current state
2. **Prioritize & select** (@product-manager) — orders by impact/effort, selects items for this sprint
3. **Execute sprint** — enters the continuous delivery loop for selected items
4. **Retrospective** (@product-manager) — reviews completed work, stores learnings in mempalace, updates backlog

**Use `product` for**: new products being defined from scratch
**Use `sprint` for**: picking up work from an existing backlog, continuing a previous product

## Navigation Model: One Level at a Time

The native task list shows **only one level** of the task tree at a time.

### Level Navigation:

**Entering a level**: Create native tasks for all items at that level, chained with `addBlockedBy`.

**Drilling into a task**: When a task has children:
1. Delete ALL native tasks at the current level
2. Create native tasks for the children with `addBlockedBy` chain
3. Work through them

**Returning to parent level**: When all children at a level are done:
1. Delete ALL native tasks at the current level
2. Recreate native tasks for the parent level with correct statuses

## Protocol

### 0. Load project profile (BEFORE everything else)

**Priority order — use the first one found:**

1. **Project profile** (`.taskflow/project.json` in the working directory)
   - If it exists, read it. This is the source of truth for THIS project's tools, patterns, and conventions.
   - Every agent prompt MUST include the relevant sections of this profile.

2. **Language standards** (fallback if no project profile exists)
   - Detect the language from the user's request
   - Read the matching file from the taskflow plugin: `skills/languages/{python,typescript,rust,go}.md`
   - Then **check for updates** via `context7` or web search
   - If anything changed, update the standards file AND store in mempalace.

3. **Suggest discovery** — if working in an existing project with no `.taskflow/project.json`:
   > "This project doesn't have a .taskflow/project.json yet. Want me to run a discovery first?"
   In `--auto` mode, run discovery automatically before proceeding.

**This context MUST be included in every agent's prompt.**

### Discover Workflow

Use `task_type="discover"` to analyze an existing project. The workflow:

1. **Scan project structure** (@Explore) — file tree, directories, key files
2. **Detect languages and runtimes** (@Explore) — languages, versions, constraints
3. **Detect package management** (@Explore) — tool, config, commands
4. **Detect code quality tools** (@Explore) — linter, formatter, type checker
5. **Detect testing setup** (@Explore) — test runner, patterns, coverage
6. **Detect architecture and patterns** (@tech-architect) — architecture style, design patterns, module boundaries
7. **Detect code conventions** (@code-reviewer) — naming, docstrings, style
8. **Detect CI/CD and infrastructure** (@devops-engineer) — pipelines, containers, deployment
9. **Detect API and integrations** (@tech-architect) — frameworks, databases, external services
10. **Review CI/CD pipeline** (@devops-reviewer) — check for missing stages, improvements
11. **Improve CI/CD pipeline** (@devops-engineer) — implement improvements
12. **Generate project profile** (@developer) — writes `.taskflow/project.json`
13. **Review project profile** (@code-reviewer) — verifies accuracy, tests commands

### 1. Recall (if mempalace available)
- Search mempalace for knowledge related to the user's request
- Use findings to inform task planning

### 2. Decompose
- `task_create(name, task_type="implement")` → returns `root_id|implement|id1:@agent,...`
- Parse step IDs and agent assignments
- Create native tasks for the workflow steps, chained with `addBlockedBy`

### 3. Work each step
- `task_start` + `TaskUpdate(in_progress)` on current step
- If step has `@agent`: spawn Agent with `subagent_type` and pass context
- If step has `@self`: handle directly
- `task_complete` + `TaskUpdate(completed)`

### 4. Verification (inline)
When `task_complete` returns `verify:<id>`:
- Keep native task as `in_progress`
- Actually verify (run code, check files)
- `task_start(verify_id)` + `task_complete(verify_id)` in taskflow only
- `task_complete(parent_id)` in taskflow
- `TaskUpdate(completed)` in native

### 5. Dynamic children (level switch)
When a step needs sub-work:
- `task_create` children in taskflow
- Delete current level native tasks
- Create native tasks for children with `addBlockedBy`
- When done: delete children, recreate parent level

### 6. Git workflow (for product/sprint continuous delivery)
After all implement steps complete for a ticket:
- `@git-workflow`: stage, commit, push, create PR
- `@integration-verifier`: wait for CI
- Squash merge via `gh pr merge --squash`
- Pull main, clean up branch

### 7. Tech debt review (between tickets)
After merge, before next ticket:
- `@architecture-reviewer`: scan for tech debt introduced
- Create backlog items for issues found

### 8. Store (if mempalace available)
After root task completes or loop stops:
- Store facts, learnings, and decisions in mempalace
- Write diary entry summarizing the session

## MCP Responses
- `<id>` — task created (no type)
- `<id>|<type>|<id1>:@agent1,<id2>:@agent2,...` — typed task with agent assignments
- `ok` — action succeeded
- `verify:<id>` — verify inline
- `error:<reason>` — something failed
