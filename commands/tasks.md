---
name: tasks
description: "Show the current taskflow task tree at the right focus level"
---

Show the taskflow task tree focused at the right level. Follow these steps exactly:

## Step 1: Find any in-progress task

Call `task_list(status="in_progress")`. This is the authoritative signal for current level.

- If one or more tasks are returned: pick the first one. Note its `id` and `parent_id`.
- If nothing is returned: also try `task_list(status="verifying")` — a verifying task means work is active.
- If still nothing: no active work → go to **Case B**.

## Step 2: Determine what to show

### Case A — There is an in-progress or verifying task

The user is mid-sprint inside a ticket. Show ONLY the steps of that ticket:

1. Take the `parent_id` of the in-progress task
2. Call `task_list(parent_id=<parent_id>)` to get all sibling steps of that ticket
3. Do NOT show sprint root, other tickets, or any other level
4. Label: "**Working on: <parent task name>**"

### Case B — Nothing is in-progress

Show ONLY root-level pending/active tasks:

1. Call `task_list()` and extract only tasks with no parent (root level)
2. Show them as a flat list — do NOT expand their children
3. Omit tasks that are fully `done`
4. Label: "**Sprint overview**"

## Step 3: Recreate native Claude UI tasks

**Delete ALL existing native tasks first.**

Then recreate native tasks mirroring exactly what was shown:

- `done` → `completed`
- `in_progress` or `verifying` → `in_progress` (with activeForm = step name)
- `pending` → `pending`
- Chain with `addBlockedBy` in the same order as the taskflow tree

**Never mix levels in the native task list.**

## Step 4: Print one summary line

Example:
- "Showing 6 steps for **History filtering** — step 2 in progress"
- "Showing sprint backlog — 3 tickets pending"
