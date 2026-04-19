from datetime import UTC, datetime

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
    """
    try:
        if idempotency_key:
            existing = await db.find_task_by_idempotency_key(idempotency_key)
            if existing:
                return existing.id

        metadata = None
        if idempotency_key:
            metadata = {"idempotency_key": idempotency_key}

        task = await db.create_task(
            name=name,
            description=description,
            parent_id=parent_id,
            verification_criteria=verification_criteria,
            metadata=metadata,
        )

        if task_type:
            steps = get_workflow(task_type)
            step_info = []
            for step in steps:
                step_task = await db.create_task(
                    name=step.name,
                    description=step.description,
                    parent_id=task.id,
                    verification_criteria=step.verification_criteria,
                )
                agent_tag = f"@{step.agent}" if step.agent else "@self"
                step_info.append(f"{step_task.id}:{agent_tag}")

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

    if output:
        await db.update_task(task_id, agent_output=output)

    if task.status == TaskStatus.PENDING:
        task = await db.update_task(task_id, **compute_start_fields())

    children = await db.get_children(task_id)
    verify_children = [c for c in children if c.name.startswith("Verify: ")]
    non_verify_children = [c for c in children if not c.name.startswith("Verify: ")]

    if task.verification_criteria and not verify_children:
        incomplete = [c for c in non_verify_children if c.status != TaskStatus.DONE]
        if incomplete:
            return "error:children not done"

        verify_task = await db.create_task(
            name=f"Verify: {task.name}",
            description=task.verification_criteria,
            parent_id=task_id,
        )
        await db.update_task(task_id, status=TaskStatus.VERIFYING.value)
        return f"verify:{verify_task.id}"

    if task.status == TaskStatus.VERIFYING and verify_children:
        if not all(c.status == TaskStatus.DONE for c in verify_children):
            return "error:verification not done"
        now = datetime.now(UTC).isoformat()
        await db.update_task(task_id, status=TaskStatus.DONE.value, completed_at=now)
        return "ok"

    try:
        fields = compute_complete_fields(task, children)
        validate_transition(task.status, TaskStatus(fields["status"]))
    except TransitionError as e:
        return f"error:{e}"

    await db.update_task(task_id, **fields)
    return "ok"


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
async def task_list(
    status: str | None = None,
    parent_id: str | None = None,
) -> str:
    """List tasks as a rendered tree, optionally filtered.

    Args:
        status: Filter by status (pending, in_progress, verifying, done, failed)
        parent_id: Show only the subtree under this task
    """
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
async def task_types() -> str:
    """List all available task types and their workflow steps."""
    result = []
    for type_name, steps in WORKFLOWS.items():
        step_names = " → ".join(s.name for s in steps)
        result.append(f"{type_name}: {step_names}")
    return "\n".join(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")
