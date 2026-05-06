---
name: tasks
description: "Show the current taskflow task tree at the right focus level"
---

Show the taskflow task tree focused at the right level. Follow these steps exactly:

## Step 1: Get current task

Call `task_current` to find the active task (if any). Note its `id` and `parent_id`.

## Step 2: Determine what to show

### Case A — There is an in-progress task (has a parent_id)

The user is mid-sprint, drilling into a ticket. Show ONLY the steps of the ticket currently being worked on:

1. Call `task_list(parent_id=<parent_id of current task>)` to get all sibling steps
2. Do NOT show the sprint root or other tickets — only the steps of this one ticket
3. Label: "**Working on: <parent task name>**"

### Case B — No in-progress task (or current task has no parent — it IS a root)

Show ONLY the root-level pending/active tasks (the sprint backlog):

1. Call `task_list()` to get the full tree
2. From the result, extract ONLY the root-level tasks (those with no parent)
3. Show them as a flat list — do NOT expand their children
4. Omit tasks that are fully `done` unless the entire sprint is done
5. Label: "**Sprint overview**"

## Step 3: Recreate native Claude UI tasks to match

**Delete ALL existing native tasks first** (set each to `deleted`).

Then recreate native tasks to mirror exactly what was shown in Step 2:

- For Case A (steps): one native task per step shown, with statuses:
  - `done` → `completed`
  - `in_progress` or `verifying` → `in_progress` (mark activeForm with step name)
  - `pending` → `pending`
  - Chain with `addBlockedBy` in order
- For Case B (root tickets): one native task per root ticket shown, with statuses mapped the same way

**CRITICAL**: The native task list must show ONLY the same level as the taskflow tree above. Never mix levels.

## Step 4: Print summary

One short line: what is being shown and why. Example:
- "Showing 6 steps for **History filtering** — step 2/6 in progress"
- "Showing sprint backlog — 3 tickets pending, 2 completed"
