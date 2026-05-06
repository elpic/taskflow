---
name: tasks
description: "Sync and show the native Claude UI task list from taskflow state"
---

Sync the native Claude UI task list from taskflow. Execute ALL steps below without stopping.

## Step 1: Get current UI state

Call the MCP tool `task_ui_state`. Parse the JSON response — it contains `level`, `label`, `tasks[]`, and `blocked_by[]`.

## Step 2: Delete all existing native tasks

Call `TaskList` to get all current native tasks. For each task returned, call `TaskUpdate(taskId=<id>, status="deleted")`. Do this even if the list looks correct — always start fresh.

## Step 3: Create native tasks from the response

For each item in `tasks[]` from the `task_ui_state` response, call:
```
TaskCreate(subject=<task.name>, description=<label from response>)
```

Keep a mapping of `taskflow_id → native_task_id` for the next step.

## Step 4: Apply blocked_by relationships

For each entry in `blocked_by[]`, call:
```
TaskUpdate(taskId=<native_id of task_id>, addBlockedBy=[<native_id of blocked_by_id>])
```

## Step 5: Set statuses

For each task in `tasks[]`:
- `status = "done"` → `TaskUpdate(taskId=<native_id>, status="completed")`
- `status = "in_progress"` or `status = "verifying"` → `TaskUpdate(taskId=<native_id>, status="in_progress", activeForm=<task.name>)`
- `status = "pending"` → leave as-is (default)

## Step 6: Report

Print one line: the `label` from the response and how many tasks were synced.
Example: "Working on: Add language standards — 10 steps synced"
