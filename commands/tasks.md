---
name: tasks
description: "Show the current taskflow task tree at the right focus level"
---

Show the taskflow task tree focused at the right level. Follow this logic exactly:

## Step 1: Get current task

Call `task_current` to find the active task (if any).

## Step 2: Determine focus level

**If there is an in-progress task** (status: in_progress or verifying):
- The in-progress task is a step inside a parent workflow (e.g. "Implement" inside "Build feature X")
- Show the **parent's subtree**: call `task_list(parent_id=<parent_id_of_current_task>)`
- This shows only the sibling steps of the active task — the current ticket's steps
- Label the output: "**Working on: <parent name>**"
- Highlight which step is currently active

**If there is no in-progress task** (nothing active):
- Show only **root-level tasks** (top-level items, no parent) that are pending or in-progress
- Call `task_list()` and filter to show only root tasks — omit their children
- Omit tasks that are `done` unless they are part of an active sprint/product
- Label the output: "**Sprint/backlog overview**"

## Step 3: Restore native tasks (Claude UI)

After displaying the taskflow tree, also restore the native Claude UI task list to match:

**If in-progress task exists** (showing step level):
- Delete any existing native tasks
- Create native tasks for each sibling step shown, with correct statuses:
  - done → `completed`
  - in_progress/verifying → `in_progress`
  - pending → `pending`
- Chain them with `addBlockedBy` in the same order

**If no in-progress task** (showing root level):
- Delete any existing native tasks
- Create one native task per root-level pending/active task shown
- Chain them with `addBlockedBy` in sprint order

## Step 4: Report

Print a clean summary of what's shown and why, so the user understands the current state at a glance.
