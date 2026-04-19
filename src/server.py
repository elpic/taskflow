import contextlib
import json
from datetime import UTC, datetime, timedelta

from mcp.server.fastmcp import FastMCP

from . import db
from .models import TaskStatus
from .tree import render_subtree, render_tree
from .verification import (
    TransitionError,
    compute_complete_fields,
    compute_fail_fields,
    compute_start_fields,
    validate_transition,
)
from .workflows import WORKFLOWS, get_workflow

mcp = FastMCP("taskflow")


@mcp.tool()
async def task_create(
    name: str,
    description: str = "",
    parent_id: str | None = None,
    verification_criteria: str | None = None,
    task_type: str | None = None,
    idempotency_key: str | None = None,
    blocked_by: list[str] | None = None,
) -> str:
    """Create a new task. If task_type is specified, auto-generates workflow subtasks.

    Args:
        name: Task name
        description: What needs to be done
        parent_id: Parent task ID for nesting
        verification_criteria: What to check before marking done
        task_type: Workflow type (simple, implement, bugfix, refactor, research,
            secure-implement, product, sprint, discover, setup).
            Auto-creates subtasks with agent assignments.
        idempotency_key: If provided and a task with this key exists,
            return the existing task instead of creating a duplicate.
        blocked_by: List of task IDs that must be DONE before this task can start.
    """
    try:
        if idempotency_key:
            existing = await db.find_task_by_idempotency_key(idempotency_key)
            if existing:
                return existing.id

        task = await db.create_task(
            name=name,
            description=description,
            parent_id=parent_id,
            verification_criteria=verification_criteria,
            idempotency_key=idempotency_key,
        )

        if blocked_by:
            try:
                await db.add_dependencies(task.id, blocked_by)
            except ValueError as e:
                await db.delete_task(task.id)
                return f"error:{e}"

        if task_type:
            steps = get_workflow(task_type)
            step_info = []
            prev_step_id: str | None = None
            for step in steps:
                step_task = await db.create_task(
                    name=step.name,
                    description=step.description,
                    parent_id=task.id,
                    verification_criteria=step.verification_criteria,
                )
                # Auto-chain: each step is blocked by the previous step
                if prev_step_id is not None:
                    await db.add_dependencies(step_task.id, [prev_step_id])
                agent_tag = f"@{step.agent}" if step.agent else "@self"
                step_info.append(f"{step_task.id}:{agent_tag}")
                prev_step_id = step_task.id

            return f"{task.id}|{task_type}|{','.join(step_info)}"

        return task.id
    except ValueError as e:
        return f"error:{e}"


@mcp.tool()
async def task_start(task_id: str) -> str:
    """Start a task. Sets it as current."""
    task = await db.get_task(task_id)
    if not task:
        return "error:not found"

    try:
        validate_transition(task.status, TaskStatus.IN_PROGRESS)
    except TransitionError as e:
        return f"error:{e}"

    blockers = await db.get_blockers(task_id)
    blocking = [b for b in blockers if b.status != TaskStatus.DONE]
    if blocking:
        parts = []
        for b in blocking:
            suffix = " (failed)" if b.status == TaskStatus.FAILED else ""
            parts.append(f"{b.id}{suffix}")
        return f"error:blocked by {','.join(parts)}"

    task = await db.update_task(task_id, **compute_start_fields())
    await db.set_current_task(task_id)
    return "ok"


@mcp.tool()
async def task_complete(task_id: str, output: str | None = None) -> str:
    """Complete a task. Auto-creates verification subtask if criteria exist.

    Args:
        task_id: The task ID to complete
        output: Optional agent output to store (design docs, code summary, etc.)
    """
    task = await db.get_task(task_id)
    if not task:
        return "error:not found"

    # Load children BEFORE any state modifications to avoid partial corruption
    children = await db.get_children(task_id)
    verify_children = [c for c in children if c.name.startswith("Verify: ")]
    non_verify_children = [c for c in children if not c.name.startswith("Verify: ")]

    # Validate completion preconditions before modifying state
    if task.verification_criteria and not verify_children:
        incomplete = [c for c in non_verify_children if c.status != TaskStatus.DONE]
        if incomplete:
            return "error:children not done"

    if (
        task.status == TaskStatus.VERIFYING
        and verify_children
        and not all(c.status == TaskStatus.DONE for c in verify_children)
    ):
        return "error:verification not done"

    if task.status not in (
        TaskStatus.PENDING,
        TaskStatus.IN_PROGRESS,
        TaskStatus.VERIFYING,
    ):
        try:
            validate_transition(task.status, TaskStatus.DONE)
        except TransitionError as e:
            return f"error:{e}"

    # All preconditions passed — now modify state
    if output:
        await db.update_task(task_id, agent_output=output)

    if task.status == TaskStatus.PENDING:
        task = await db.update_task(task_id, **compute_start_fields())

    if task.verification_criteria and not verify_children:
        verify_task = await db.create_task(
            name=f"Verify: {task.name}",
            description=task.verification_criteria,
            parent_id=task_id,
        )
        await db.update_task(task_id, status=TaskStatus.VERIFYING.value)
        return f"verify:{verify_task.id}"

    if task.status == TaskStatus.VERIFYING and verify_children:
        now = datetime.now(UTC).isoformat()
        await db.update_task(task_id, status=TaskStatus.DONE.value, completed_at=now)
        return await _append_unblocked(task_id, "ok")

    try:
        fields = compute_complete_fields(task, children)
        validate_transition(task.status, TaskStatus(fields["status"]))
    except TransitionError as e:
        return f"error:{e}"

    await db.update_task(task_id, **fields)
    # Only append unblocked info when the task actually reaches DONE
    if fields.get("status") == TaskStatus.DONE.value:
        return await _append_unblocked(task_id, "ok")
    return "ok"


async def _append_unblocked(completed_task_id: str, base: str) -> str:
    """Append |unblocked:<ids> to base string if dependents become unblocked."""
    dependents = await db.get_dependents(completed_task_id)
    newly_unblocked = []
    for dep in dependents:
        if dep.status != TaskStatus.PENDING:
            continue
        blockers = await db.get_blockers(dep.id)
        if all(b.status == TaskStatus.DONE for b in blockers):
            newly_unblocked.append(dep.id)
    if newly_unblocked:
        return f"{base}|unblocked:{','.join(newly_unblocked)}"
    return base


@mcp.tool()
async def task_fail(task_id: str, reason: str) -> str:
    """Mark a task as failed."""
    task = await db.get_task(task_id)
    if not task:
        return "error:not found"

    try:
        validate_transition(task.status, TaskStatus.FAILED)
    except TransitionError as e:
        return f"error:{e}"

    await db.update_task(task_id, **compute_fail_fields(reason))
    return "ok"


@mcp.tool()
async def task_delete(task_id: str) -> str:
    """Delete a task and all its descendants.

    Args:
        task_id: The task ID to delete
    """
    task = await db.get_task(task_id)
    if not task:
        return "error:not found"

    if task.status == TaskStatus.IN_PROGRESS:
        return "error:cannot delete in-progress task"

    await db.delete_task(task_id)
    return "ok"


@mcp.tool()
async def task_move(task_id: str, new_parent_id: str | None = None) -> str:
    """Move a task to a new parent (or make it a root task).

    Args:
        task_id: The task ID to move
        new_parent_id: New parent ID, or None to make it a root task
    """
    task = await db.get_task(task_id)
    if not task:
        return "error:not found"

    if new_parent_id:
        parent = await db.get_task(new_parent_id)
        if not parent:
            return "error:parent not found"

    try:
        await db.move_task(task_id, new_parent_id)
    except ValueError as e:
        return f"error:{e}"

    return "ok"


@mcp.tool()
async def task_get(task_id: str) -> str:
    """Get a task's details and its direct children.

    Args:
        task_id: The task ID to retrieve
    """
    task = await db.get_task(task_id)
    if not task:
        return "error:not found"

    children = await db.get_children(task_id)
    tree = render_subtree(task, children)

    parts = [tree]
    if task.description:
        parts.append(f"\nDescription: {task.description}")
    if task.verification_criteria:
        parts.append(f"Criteria: {task.verification_criteria}")
    if task.metadata and task.metadata != "{}":
        parts.append(f"Metadata: {task.metadata}")
    if task.agent_output:
        parts.append(f"Output: {task.agent_output}")

    blockers = await db.get_blockers(task_id)
    if blockers:
        blocker_strs = [f"{b.id} ({b.name}) [{b.status.value}]" for b in blockers]
        parts.append(f"Blocked by: {', '.join(blocker_strs)}")

    return "\n".join(parts)


@mcp.tool()
async def task_update(
    task_id: str,
    name: str | None = None,
    description: str | None = None,
    verification_criteria: str | None = None,
    metadata: str | None = None,
) -> str:
    """Update a task's fields (not status — use task_start/complete/fail for that).

    Args:
        task_id: The task ID to update
        name: New task name
        description: New description
        verification_criteria: New verification criteria
        metadata: New metadata JSON string
    """
    task = await db.get_task(task_id)
    if not task:
        return "error:not found"

    fields: dict[str, str] = {}
    if name is not None:
        fields["name"] = name
    if description is not None:
        fields["description"] = description
    if verification_criteria is not None:
        fields["verification_criteria"] = verification_criteria
    if metadata is not None:
        fields["metadata"] = metadata

    if not fields:
        return "error:no fields to update"

    await db.update_task(task_id, **fields)
    return "ok"


@mcp.tool()
async def task_reorder(task_id: str, position: int) -> str:
    """Set the display/priority position of a task among its siblings.

    Args:
        task_id: The task ID to reorder
        position: Integer position (lower = higher priority, 0-based)
    """
    task = await db.get_task(task_id)
    if not task:
        return "error:not found"

    await db.update_task(task_id, position=position)
    return "ok"


@mcp.tool()
async def task_current() -> str:
    """Get the currently active task and its context."""
    current_id = await db.get_current_task_id()
    if not current_id:
        return "No active task."

    task = await db.get_task(current_id)
    if not task:
        return "No active task."

    children = await db.get_children(current_id)
    tree = render_subtree(task, children)

    # Build parent breadcrumb
    breadcrumb = []
    parent_id = task.parent_id
    while parent_id:
        parent = await db.get_task(parent_id)
        if not parent:
            break
        breadcrumb.append(parent.name)
        parent_id = parent.parent_id
    breadcrumb.reverse()

    parts = []
    if breadcrumb:
        parts.append(f"Context: {' > '.join(breadcrumb)}")
    parts.append(tree)

    return "\n".join(parts)


@mcp.tool()
async def task_resume(root_id: str | None = None) -> str:
    """Resume a previous session by summarising active work for a root task.

    Finds the in-progress root task (or the one specified), shows what is
    currently being worked on, what is ready next, and outputs from completed
    sibling steps so the new session has full context.

    Args:
        root_id: ID of the root task to resume. If omitted, the most recent
            root task that has in-progress work is used automatically.
    """
    # Resolve the root task
    if root_id is not None:
        root = await db.get_task(root_id)
        if not root:
            return "error:not found"
        if root.parent_id is not None:
            return "error:task is not a root task"
    else:
        root = await db.find_active_root()
        if not root:
            return "No active work found."

    # Find the deepest in-progress task (the one actually being worked on)
    # by doing a BFS that prefers in-progress nodes
    in_progress_task = None
    queue: list[tuple] = [(root, [])]  # (task, breadcrumb_names)
    in_progress_crumb: list[str] = []

    while queue:
        current, crumb = queue.pop(0)
        if current.status == TaskStatus.IN_PROGRESS:
            # Prefer the deepest in-progress leaf we find
            in_progress_task = current
            in_progress_crumb = [*crumb, current.name]
        children = await db.get_children(current.id)
        for child in children:
            if child.status == TaskStatus.IN_PROGRESS:
                queue.append((child, [*crumb, current.name]))

    # Find next ready task under the root
    ready_tasks = await db.get_ready_tasks(parent_id=root.id)
    # If none at root level, find globally under root via all descendants
    if not ready_tasks and in_progress_task and in_progress_task.parent_id:
        ready_tasks = await db.get_ready_tasks(parent_id=in_progress_task.parent_id)

    # Collect completed sibling steps with agent output for context
    context_lines: list[str] = []
    sibling_parent_id = (
        in_progress_task.parent_id
        if in_progress_task and in_progress_task.parent_id
        else root.id
    )
    siblings = await db.get_children(sibling_parent_id)
    for sibling in siblings:
        if sibling.status == TaskStatus.DONE and sibling.agent_output:
            truncated = sibling.agent_output[:200]
            if len(sibling.agent_output) > 200:
                truncated += "…"
            context_lines.append(f"  - {sibling.name}: {truncated}")

    # Build output
    parts: list[str] = []
    parts.append(f"Resume: {root.name} [{root.status.value}]")

    if in_progress_task:
        crumb_str = " > ".join(in_progress_crumb)
        parts.append(f"Current: {in_progress_task.name} (path: {crumb_str})")
    else:
        parts.append("Current: (none)")

    if ready_tasks:
        next_task = ready_tasks[0]
        meta: dict = {}
        with contextlib.suppress(Exception):
            meta = json.loads(next_task.metadata) if next_task.metadata else {}
        agent = meta.get("agent", "")
        agent_str = f" ({agent})" if agent else ""
        parts.append(f"Next ready: {next_task.name}{agent_str}")
    else:
        parts.append("Next ready: (none)")

    if context_lines:
        parts.append("Context from completed steps:")
        parts.extend(context_lines)

    return "\n".join(parts)


@mcp.tool()
async def task_list(
    status: str | None = None,
    parent_id: str | None = None,
    ready: bool = False,
) -> str:
    """List tasks as a rendered tree, optionally filtered.

    Args:
        status: Filter by status (pending, in_progress, verifying, done, failed)
        parent_id: Show only the subtree under this task
        ready: If True, return only PENDING tasks whose blockers are all DONE
    """
    if ready:
        if parent_id:
            parent = await db.get_task(parent_id)
            if not parent:
                return "error:not found"
        tasks = await db.get_ready_tasks(parent_id=parent_id)
        return render_tree(tasks)

    if status:
        valid = {s.value for s in TaskStatus}
        if status not in valid:
            return f"error:invalid status '{status}'. Valid: {', '.join(sorted(valid))}"

    if status or parent_id:
        if parent_id:
            parent = await db.get_task(parent_id)
            if not parent:
                return "error:not found"
        tasks = await db.get_tasks_filtered(status=status, parent_id=parent_id)
    else:
        tasks = await db.get_all_tasks()

    return render_tree(tasks)


@mcp.tool()
async def task_search(query: str) -> str:
    """Search tasks by name or description.

    Args:
        query: Text to search for (case-insensitive)
    """
    if not query.strip():
        return "error:empty query"

    tasks = await db.search_tasks(query)
    if not tasks:
        return "No matching tasks."

    lines = []
    for task in tasks:
        status = task.status.value
        parent_info = f" (parent: {task.parent_id})" if task.parent_id else ""
        lines.append(f"[{task.id}] {task.name} [{status}]{parent_info}")
    return "\n".join(lines)


@mcp.tool()
async def task_stats(task_id: str) -> str:
    """Get timing statistics for a task and its subtree.

    Args:
        task_id: The root task ID to analyze
    """
    task = await db.get_task(task_id)
    if not task:
        return "error:not found"

    children = await db.get_children(task_id)
    lines = [f"Stats: {task.name} [{task.status.value}]"]

    # Task duration
    if task.started_at and task.completed_at:
        start = datetime.fromisoformat(task.started_at)
        end = datetime.fromisoformat(task.completed_at)
        duration = end - start
        lines.append(f"Duration: {_format_duration(duration)}")
    elif task.started_at:
        start = datetime.fromisoformat(task.started_at)
        elapsed = datetime.now(UTC) - start
        lines.append(f"Elapsed: {_format_duration(elapsed)} (in progress)")

    # Child stats
    if children:
        total = len(children)
        done = sum(1 for c in children if c.status == TaskStatus.DONE)
        failed = sum(1 for c in children if c.status == TaskStatus.FAILED)
        lines.append(f"Children: {done}/{total} done, {failed} failed")

        for child in children:
            status = child.status.value
            dur = ""
            if child.started_at and child.completed_at:
                s = datetime.fromisoformat(child.started_at)
                e = datetime.fromisoformat(child.completed_at)
                dur = f" ({_format_duration(e - s)})"
            lines.append(f"  - {child.name} [{status}]{dur}")

    return "\n".join(lines)


def _format_duration(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m"


@mcp.tool()
async def task_types() -> str:
    """List all available task types and their workflow steps."""
    result = []
    for type_name, steps in WORKFLOWS.items():
        step_names = " → ".join(s.name for s in steps)
        result.append(f"{type_name}: {step_names}")
    return "\n".join(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")
