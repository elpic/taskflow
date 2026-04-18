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
5. Delegate each step to its assigned agent
6. Verify inline, store learnings in mempalace after completion

## Autonomous Mode (`--auto`)
Run fully end-to-end without human intervention. Skip clarifying questions, accept all agent recommendations, auto-fix issues found in review.

## Continuous Delivery (product/sprint with `--auto`)
Enters a loop: pick ticket → branch → implement → commit → PR → CI → squash merge → tech debt review → next ticket. Use `/stop` to halt between tickets.

## Git Workflow
Each ticket gets: feature branch → descriptive commit → PR with full description → wait for CI → squash merge → cleanup.

## Tech Debt Review
Between tickets: @architecture-reviewer scans for tech debt. New items go to backlog.

## Skip taskflow for simple questions, explanations, or one-shot edits.
