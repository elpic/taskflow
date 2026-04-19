from datetime import UTC, datetime

from mcp.server.fastmcp import FastMCP

from . import db
from .models import TaskStatus
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
    """
    try:
        task = await db.create_task(
            name=name,
            description=description,
            parent_id=parent_id,
            verification_criteria=verification_criteria,
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
async def task_complete(task_id: str) -> str:
    """Complete a task. Auto-creates verification subtask if criteria exist."""
    task = await db.get_task(task_id)
    if not task:
        return "error:not found"

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
async def task_types() -> str:
    """List all available task types and their workflow steps."""
    result = []
    for type_name, steps in WORKFLOWS.items():
        step_names = " → ".join(s.name for s in steps)
        result.append(f"{type_name}: {step_names}")
    return "\n".join(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")
