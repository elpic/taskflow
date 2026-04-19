from .models import Task, TaskStatus

STATUS_ICONS = {
    TaskStatus.PENDING: "○",
    TaskStatus.IN_PROGRESS: "◈",
    TaskStatus.VERIFYING: "◇",
    TaskStatus.DONE: "◉",
    TaskStatus.FAILED: "✗",
}

STATUS_LABELS = {
    TaskStatus.PENDING: "pending",
    TaskStatus.IN_PROGRESS: "in_progress",
    TaskStatus.VERIFYING: "verifying",
    TaskStatus.DONE: "done ✓",
    TaskStatus.FAILED: "failed",
}


def build_tree(tasks: list[Task]) -> list[Task]:
    """Build tree structure from flat task list.

    Returns root nodes with children populated.
    """
    by_id: dict[str, Task] = {}
    for t in tasks:
        t.children = []
        by_id[t.id] = t

    roots: list[Task] = []
    for t in tasks:
        if t.parent_id and t.parent_id in by_id:
            by_id[t.parent_id].children.append(t)
        else:
            roots.append(t)

    return roots


def render_task(
    task: Task, prefix: str = "", is_last: bool = True, is_root: bool = True
) -> str:
    """Render a single task and its children as a tree string."""
    icon = STATUS_ICONS[task.status]
    label = STATUS_LABELS[task.status]

    if is_root:
        connector = ""
        child_prefix = ""
    else:
        connector = "└── " if is_last else "├── "
        child_prefix = "    " if is_last else "│   "

    line = f"{prefix}{connector}{icon} {task.name} [{label}]"
    lines = [line]

    for i, child in enumerate(task.children):
        is_child_last = i == len(task.children) - 1
        lines.append(
            render_task(child, prefix + child_prefix, is_child_last, is_root=False)
        )

    return "\n".join(lines)


def render_tree(tasks: list[Task]) -> str:
    """Render full task tree from flat list."""
    if not tasks:
        return "No tasks found."

    roots = build_tree(tasks)
    rendered = []
    for root in roots:
        rendered.append(render_task(root))

    return "\n\n".join(rendered)


def render_subtree(task: Task, children: list[Task]) -> str:
    """Render a single task with its direct children."""
    task.children = children
    return render_task(task)
